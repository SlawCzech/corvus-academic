"""The terms of service in front of student data.

The terms carry the data processing agreement: a promoter who has not
accepted the version in force reaches none of the mentoring routes, and
accepting it is recorded per version.
"""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.terms import CURRENT_TERMS_VERSION, TERMS_NOT_ACCEPTED
from src.identity.infrastructure.models import TermsAcceptanceModel
from tests.test_mentoring.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    PROMOTOR_EMAIL,
    PROMOTOR_PASSWORD,
    PROMOTOR_UUID,
    login,
)


async def _forget_acceptance(session: AsyncSession) -> None:
    await session.execute(
        delete(TermsAcceptanceModel).where(
            TermsAcceptanceModel.user_id == PROMOTOR_UUID
        )
    )
    await session.commit()


async def test_a_promoter_without_the_terms_reaches_no_student_data(
    client: TestClient, db_session: AsyncSession
) -> None:
    await _forget_acceptance(db_session)
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    for path in ("/students", "/reviews", "/dashboard/summary"):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 403, path
        assert resp.json()["detail"] == TERMS_NOT_ACCEPTED, path


async def test_accepting_the_terms_opens_the_way(
    client: TestClient, db_session: AsyncSession
) -> None:
    await _forget_acceptance(db_session)
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    before: dict[str, Any] = client.get("/users/me/terms", headers=headers).json()
    accepted = client.post(
        "/users/me/terms", json={"version": CURRENT_TERMS_VERSION}, headers=headers
    )

    assert before == {"current_version": CURRENT_TERMS_VERSION, "accepted_at": None}
    assert accepted.status_code == 200
    assert accepted.json()["accepted_at"] is not None
    assert client.get("/students", headers=headers).status_code == 200


async def test_accepting_again_keeps_the_first_date(
    client: TestClient, db_session: AsyncSession
) -> None:
    await _forget_acceptance(db_session)
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)
    body = {"version": CURRENT_TERMS_VERSION}

    first = client.post("/users/me/terms", json=body, headers=headers).json()
    second = client.post("/users/me/terms", json=body, headers=headers).json()

    assert first["accepted_at"] == second["accepted_at"]


async def test_a_text_that_changed_meanwhile_is_not_accepted(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The page was open before a new version came in."""
    await _forget_acceptance(db_session)
    headers = login(client, PROMOTOR_EMAIL, PROMOTOR_PASSWORD)

    resp = client.post(
        "/users/me/terms", json={"version": "2020-01-01"}, headers=headers
    )

    assert resp.status_code == 409
    assert client.get("/students", headers=headers).status_code == 403


def test_an_admin_is_not_asked(client: TestClient) -> None:
    """An admin never sees student data (ADR 0008), so has nothing to agree to."""
    headers = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    resp = client.get("/students", headers=headers)

    assert resp.json().get("detail") != TERMS_NOT_ACCEPTED
