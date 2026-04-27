"""
Tests for /api/auth/* endpoints.

Covers:
- POST /api/auth/login
- GET  /api/auth/me
- POST /api/auth/change-password

All tests use fakes (in-memory SQLite + HTTPX ASGI transport).
No mocks of internal functions — we exercise the full request path.
"""

import pytest
import pytest_asyncio

from tests.conftest import create_analyst_in_db, make_token_for


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_token(client, db_session):
    """
    A valid email and password must yield HTTP 200 and a non-empty access token.
    This is the happy-path baseline every other auth test depends on.
    """
    await create_analyst_in_db(
        db_session,
        email="analyst@example.com",
        password="correctpassword",
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "analyst@example.com", "password": "correctpassword"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert len(body["access_token"]) > 0
    assert body["token_type"] == "bearer"
    assert body["analyst"]["email"] == "analyst@example.com"


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client, db_session):
    """
    A correct email paired with a wrong password must return HTTP 401.

    Security note: the error message must NOT reveal whether the email exists
    or whether only the password is wrong (avoids enumeration attacks).
    """
    await create_analyst_in_db(
        db_session,
        email="analyst@example.com",
        password="correctpassword",
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "analyst@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_with_unknown_email_returns_401(client, db_session):
    """
    An email that does not exist in the database must return HTTP 401.

    The error message must be identical to the wrong-password case so
    callers cannot tell the difference (constant-time-style messaging).
    """
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "anypassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_with_inactive_account_returns_401(client, db_session):
    """
    A disabled (is_active=False) account must be rejected even if the password
    is correct.

    Security note: the response must be identical to the wrong-password
    case — revealing that the account exists but is disabled is an info leak.
    """
    await create_analyst_in_db(
        db_session,
        email="inactive@example.com",
        password="correctpassword",
        is_active=False,
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "correctpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_response_does_not_expose_hashed_password(client, db_session):
    """
    The login response body must never include the hashed_password field.
    If it appeared, any successful login would leak a bcrypt hash.
    """
    await create_analyst_in_db(
        db_session,
        email="analyst@example.com",
        password="mypassword123",
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "analyst@example.com", "password": "mypassword123"},
    )

    assert response.status_code == 200
    body_text = response.text
    assert "hashed_password" not in body_text
    assert "$2b$" not in body_text  # bcrypt hash prefix


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_analyst_profile(client, db_session):
    """
    An authenticated request to /api/auth/me must return the analyst's own profile.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="me@example.com",
        full_name="Alice Smith",
    )
    token = make_token_for(analyst)

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"
    assert body["full_name"] == "Alice Smith"


@pytest.mark.asyncio
async def test_get_me_without_token_returns_403(client, db_session):
    """
    /api/auth/me must reject requests with no Authorization header.
    FastAPI's HTTPBearer returns 403 (not 401) when the header is absent.
    """
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_invalid_token_returns_401(client, db_session):
    """
    A tampered or garbage Bearer token must be rejected with HTTP 401.
    """
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/change-password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_with_correct_current_password_returns_204(client, db_session):
    """
    Providing the correct current password and a valid new password must
    return HTTP 204 (No Content) — the standard success response for this endpoint.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="changer@example.com",
        password="OldPassword1",
    )
    token = make_token_for(analyst)

    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": "OldPassword1", "new_password": "NewPassword2"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_password_with_wrong_current_password_returns_400(client, db_session):
    """
    Supplying an incorrect current password must return HTTP 400.
    This prevents an attacker who steals a token from silently changing the password.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="changer@example.com",
        password="RealPassword1",
    )
    token = make_token_for(analyst)

    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongPassword!", "new_password": "NewPassword2"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "incorrect" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_without_auth_returns_403(client, db_session):
    """
    Change-password is a protected endpoint and must reject unauthenticated requests.
    """
    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": "any", "new_password": "NewPassword2"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_new_password_too_short_returns_422(client, db_session):
    """
    The schema enforces a minimum of 8 characters for new_password.
    Sending fewer must return HTTP 422 (validation error) before hitting business logic.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="changer@example.com",
        password="RealPassword1",
    )
    token = make_token_for(analyst)

    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": "RealPassword1", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_changed_password_is_persisted_and_old_password_no_longer_works(
    client, db_session
):
    """
    After a successful password change, the old password must be rejected on login.
    This verifies the hash is actually written to the database, not just accepted
    in-memory.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="changer@example.com",
        password="OldPassword1",
    )
    token = make_token_for(analyst)

    # Step 1: change the password
    change_resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "OldPassword1", "new_password": "NewPassword99"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert change_resp.status_code == 204

    # Step 2: the old password must now be rejected
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "changer@example.com", "password": "OldPassword1"},
    )
    assert login_resp.status_code == 401

    # Step 3: the new password must be accepted
    login_resp2 = await client.post(
        "/api/auth/login",
        json={"email": "changer@example.com", "password": "NewPassword99"},
    )
    assert login_resp2.status_code == 200
