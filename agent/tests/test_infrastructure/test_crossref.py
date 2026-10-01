"""The Crossref client: paced to the stated limit, patient with a 429."""

import httpx
import pytest

from src.infrastructure.crossref import CrossrefClient, CrossrefUnavailableError, Pace

_ITEM = {
    "DOI": "10.2307/2626876",
    "title": ["The Nature of the Firm"],
    "issued": {"date-parts": [[1937]]},
    "author": [{"family": "Coase"}],
    "container-title": ["Economica"],
    "type": "journal-article",
    "score": 80.0,
}
_PUBLIC_POOL = {"x-rate-limit-limit": "1", "x-rate-limit-interval": "1s"}


class _Time:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(round(seconds, 2))
        self.now += seconds


def _client(responses: list[httpx.Response], when: _Time) -> CrossrefClient:
    queue = iter(responses)
    http = httpx.Client(
        base_url="https://api.crossref.org",
        transport=httpx.MockTransport(lambda _: next(queue)),
    )
    return CrossrefClient(http, Pace(clock=when.clock, sleep=when.sleep))


def _found() -> httpx.Response:
    return httpx.Response(
        200, json={"message": {"items": [_ITEM]}}, headers=_PUBLIC_POOL
    )


def test_search_returns_the_records_trimmed_to_what_is_compared() -> None:
    work = _client([_found()], _Time()).search("Coase (1937)")[0]

    assert (work.doi, work.year, work.authors) == ("10.2307/2626876", 1937, ("Coase",))
    assert work.title == "The Nature of the Firm"


def test_requests_are_spaced_by_the_limit_the_responses_state() -> None:
    when = _Time()
    client = _client([_found(), _found(), _found()], when)

    for _ in range(3):
        client.search("x")

    # The first goes out at once and teaches the rest: one a second, a
    # little under the limit rather than exactly at it.
    assert when.slept == [1.1, 1.1]


def test_a_429_is_waited_out_and_asked_again() -> None:
    when = _Time()
    client = _client([httpx.Response(429), httpx.Response(429), _found()], when)

    assert len(client.search("x")) == 1
    assert when.slept == [2.0, 4.0]


def test_the_server_says_how_long_to_wait_when_it_knows() -> None:
    when = _Time()
    busy = httpx.Response(503, headers={"retry-after": "7"})

    _client([busy, _found()], when).search("x")

    assert when.slept == [7.0]


def test_an_entry_is_given_up_on_after_the_last_wait() -> None:
    when = _Time()
    client = _client([httpx.Response(429)] * 4, when)

    with pytest.raises(CrossrefUnavailableError, match="limit zapytań") as raised:
        client.search("x")

    assert raised.value.status == 429
    assert when.slept == [2.0, 4.0, 8.0]


def test_a_doi_crossref_does_not_have_is_not_an_outage() -> None:
    when = _Time()

    assert _client([httpx.Response(404)], when).lookup("10.1/none") is None
    # And it is not retried: asking again would get the same answer.
    assert when.slept == []


def test_no_connection_is_reported_without_the_request_in_the_message() -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    http = httpx.Client(
        base_url="https://api.crossref.org", transport=httpx.MockTransport(offline)
    )

    with pytest.raises(CrossrefUnavailableError, match="brak połączenia"):
        CrossrefClient(http, Pace(sleep=lambda _: None)).search("Coase")
