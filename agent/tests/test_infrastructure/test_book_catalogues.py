"""The library catalogues, read into the shape a reference is compared with."""

import httpx

from src.infrastructure.book_catalogues import (
    NationalLibraryClient,
    OpenLibraryClient,
    main_title,
)
from src.infrastructure.paced_http import Pace

_QUIET = {"sleep": lambda _: None}


def _http(
    base_url: str, body: dict[str, object], seen: list[httpx.Request]
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    return httpx.Client(base_url=base_url, transport=httpx.MockTransport(handler))


def test_a_catalogue_title_is_compared_without_its_subtitle() -> None:
    isbd = "Ludowa historia Polski : historia wyzysku i oporu / Adam Leszczyński."

    assert main_title(isbd) == "Ludowa historia Polski"
    assert main_title("Gospodarka polska a europejska w XVI-XVIII wieku /") == (
        "Gospodarka polska a europejska w XVI-XVIII wieku"
    )


def test_the_national_library_record_becomes_a_work() -> None:
    seen: list[httpx.Request] = []
    body = {
        "bibs": [
            {
                "author": "Hagen, William W. (1942- )",
                "title": "Ordinary Prussians : Brandenburg Junkers and Villagers /",
                "publicationYear": "2005",
                "publisher": "Cambridge University Press,",
                "kind": "książka",
            }
        ]
    }
    client = NationalLibraryClient(
        _http("https://data.bn.org.pl", body, seen), Pace(**_QUIET)
    )

    work = client.search("Ordinary Prussians", "Hagen")[0]

    assert (work.title, work.authors, work.year) == (
        "Ordinary Prussians",
        ("Hagen",),
        2005,
    )
    assert work.venue == "Cambridge University Press"
    assert work.doi == ""
    # Only what the reference says of itself is sent.
    assert dict(seen[0].url.params) == {
        "title": "Ordinary Prussians",
        "limit": "5",
        "author": "Hagen",
    }


def test_open_library_gives_the_surname_and_the_first_year() -> None:
    seen: list[httpx.Request] = []
    body = {
        "docs": [
            {
                "title": "The Economic Institutions of Capitalism",
                "author_name": ["Oliver E. Williamson"],
                "first_publish_year": 1985,
                "publisher": ["Free Press"],
            }
        ]
    }
    client = OpenLibraryClient(
        _http("https://openlibrary.org", body, seen), Pace(**_QUIET)
    )

    work = client.search("The economic institutions of capitalism", "Williamson")[0]

    assert (work.authors, work.year, work.venue) == (
        ("Williamson",),
        1985,
        "Free Press",
    )
    assert seen[0].url.path == "/search.json"


def test_an_empty_answer_is_no_records_not_an_error() -> None:
    client = NationalLibraryClient(
        _http("https://data.bn.org.pl", {"bibs": []}, []), Pace(**_QUIET)
    )

    assert client.search("Nie ma takiej książki") == []
