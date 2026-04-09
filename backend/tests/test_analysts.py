"""
Tests for /api/analysts endpoints.

Covers:
- GET  /api/analysts  (list)
- POST /api/analysts  (create)

All tests use fakes (in-memory SQLite + HTTPX ASGI transport).
"""

import pytest

from tests.conftest import create_analyst_in_db, make_token_for


# ---------------------------------------------------------------------------
# GET /api/analysts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_analysts_requires_auth(client, db_session):
    """
    Listing analysts is a protected endpoint.
    Requests without an Authorization header must be rejected (HTTP 403
    because FastAPI HTTPBearer returns 403 when the header is absent).
    """
    response = await client.get("/api/analysts")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_analysts_with_invalid_token_returns_401(client, db_session):
    """
    A garbage JWT must be rejected before the DB query runs.
    """
    response = await client.get(
        "/api/analysts",
        headers={"Authorization": "Bearer garbage.jwt.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_analysts_returns_all_analysts(client, db_session):
    """
    An authenticated analyst receives a list that includes every analyst stored.
    We create two and verify both appear.
    """
    analyst_a = await create_analyst_in_db(
        db_session, email="alpha@example.com", full_name="Alpha"
    )
    await create_analyst_in_db(
        db_session, email="beta@example.com", full_name="Beta"
    )
    token = make_token_for(analyst_a)

    response = await client.get(
        "/api/analysts",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    emails = [item["email"] for item in response.json()]
    assert "alpha@example.com" in emails
    assert "beta@example.com" in emails


@pytest.mark.asyncio
async def test_list_analysts_does_not_expose_hashed_password(client, db_session):
    """
    The analyst list response must never include hashed_password.
    Exposing bcrypt hashes in a list endpoint would be a critical data leak.
    """
    analyst = await create_analyst_in_db(db_session, email="analyst@example.com")
    token = make_token_for(analyst)

    response = await client.get(
        "/api/analysts",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "hashed_password" not in response.text
    assert "$2b$" not in response.text


# ---------------------------------------------------------------------------
# POST /api/analysts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_analyst_without_auth_returns_403(client, db_session):
    """
    Account creation is a protected endpoint — it must not be publicly accessible.
    An unauthenticated request must be refused so random users cannot create accounts.
    """
    response = await client.post(
        "/api/analysts",
        json={
            "email": "new@example.com",
            "full_name": "New Person",
            "password": "SecurePass1",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_analyst_with_invalid_token_returns_401(client, db_session):
    """
    A tampered token must not be able to create accounts.
    """
    response = await client.post(
        "/api/analysts",
        json={
            "email": "new@example.com",
            "full_name": "New Person",
            "password": "SecurePass1",
        },
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_analyst_succeeds_with_valid_auth(client, db_session):
    """
    An authenticated analyst can create a new analyst account.
    The response must return HTTP 201 and the new analyst's profile.
    """
    creator = await create_analyst_in_db(db_session, email="creator@example.com")
    token = make_token_for(creator)

    response = await client.post(
        "/api/analysts",
        json={
            "email": "newanalyst@example.com",
            "full_name": "New Analyst",
            "password": "ValidPass99",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newanalyst@example.com"
    assert body["full_name"] == "New Analyst"


@pytest.mark.asyncio
async def test_create_analyst_response_never_contains_hashed_password(client, db_session):
    """
    The create-analyst response must not include the hashed_password field.
    """
    creator = await create_analyst_in_db(db_session, email="creator@example.com")
    token = make_token_for(creator)

    response = await client.post(
        "/api/analysts",
        json={
            "email": "newanalyst@example.com",
            "full_name": "New Analyst",
            "password": "ValidPass99",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert "hashed_password" not in response.text
    assert "$2b$" not in response.text


@pytest.mark.asyncio
async def test_create_analyst_with_duplicate_email_returns_409(client, db_session):
    """
    Attempting to register a second analyst with the same email must return
    HTTP 409 Conflict.

    This is a data-integrity guard — the database has a UNIQUE constraint on
    the email column, but the application must catch the duplicate before
    hitting it (which is what the 409 response confirms).
    """
    creator = await create_analyst_in_db(
        db_session, email="creator@example.com"
    )
    # Create the first analyst with the target email
    await create_analyst_in_db(
        db_session, email="duplicate@example.com"
    )
    token = make_token_for(creator)

    # Attempt to create a second analyst with the same email
    response = await client.post(
        "/api/analysts",
        json={
            "email": "duplicate@example.com",
            "full_name": "Second Person",
            "password": "AnotherPass1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_analyst_with_invalid_email_format_returns_422(client, db_session):
    """
    Pydantic validates the email field. A syntactically invalid email must
    return HTTP 422 without reaching the database.
    """
    creator = await create_analyst_in_db(db_session, email="creator@example.com")
    token = make_token_for(creator)

    response = await client.post(
        "/api/analysts",
        json={
            "email": "not-an-email",
            "full_name": "Someone",
            "password": "ValidPass99",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_analyst_with_short_password_returns_422(client, db_session):
    """
    The schema enforces a minimum of 8 characters for the password field.
    Sending fewer must return HTTP 422 before any DB write happens.
    """
    creator = await create_analyst_in_db(db_session, email="creator@example.com")
    token = make_token_for(creator)

    response = await client.post(
        "/api/analysts",
        json={
            "email": "newanalyst@example.com",
            "full_name": "New Analyst",
            "password": "short",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_analyst_password_is_stored_hashed_not_plaintext(client, db_session):
    """
    After creating an analyst, verify the database row stores a bcrypt hash,
    not the plaintext password.

    This test reaches directly into the DB session — it is verifying a
    security property, not an HTTP behaviour.
    """
    from sqlalchemy import select
    from app.models.analyst import Analyst

    creator = await create_analyst_in_db(db_session, email="creator@example.com")
    token = make_token_for(creator)

    plain_password = "PlainTextPass1"
    response = await client.post(
        "/api/analysts",
        json={
            "email": "stored@example.com",
            "full_name": "Storage Test",
            "password": plain_password,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    result = await db_session.execute(
        select(Analyst).where(Analyst.email == "stored@example.com")
    )
    saved = result.scalar_one()

    assert saved.hashed_password != plain_password
    assert saved.hashed_password.startswith("$2b$")  # bcrypt signature
