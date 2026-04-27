"""
Security tests: token_version invalidation.

After a password change the token_version on the Analyst row is incremented.
Any token minted with the old version must be rejected even if the JWT
signature is still valid and the expiry has not passed.

Also tests require_admin blocking non-admin analysts.
"""

import pytest

from app.auth.jwt import create_access_token
from app.models.analyst import Analyst
from tests.conftest import create_analyst_in_db, make_token_for, make_test_settings


# ---------------------------------------------------------------------------
# Helper: mint a token with arbitrary extra claims
# ---------------------------------------------------------------------------


def make_token_with_claims(analyst: Analyst, extra_claims: dict, settings=None) -> str:
    """Mint a JWT for analyst with additional/override claims injected."""
    if settings is None:
        settings = make_test_settings()
    data = {"sub": str(analyst.id), "token_ver": analyst.token_version}
    data.update(extra_claims)
    return create_access_token(
        data=data,
        secret=settings.JWT_SECRET_KEY,
        expire_hours=settings.JWT_EXPIRE_HOURS,
        algorithm=settings.JWT_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# token_version invalidation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_minted_before_password_change_is_rejected(client, db_session):
    """
    A token issued BEFORE a password change must be rejected with 401
    on any subsequent protected request.

    The mechanism: password change increments token_version in the DB;
    the old token carries the stale version so get_current_analyst rejects it.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="stale_token@example.com",
        password="OldPassword1",
    )
    stale_token = make_token_for(analyst)

    # Change the password — this increments token_version
    change_resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "OldPassword1", "new_password": "NewPassword99"},
        headers={"Authorization": f"Bearer {stale_token}"},
    )
    assert change_resp.status_code == 204

    # The old token must now be rejected
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {stale_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_minted_after_password_change_is_accepted(client, db_session):
    """
    A token issued AFTER a password change (via login) must be accepted.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="fresh_token@example.com",
        password="OldPassword1",
    )
    old_token = make_token_for(analyst)

    # Change the password
    await client.post(
        "/api/auth/change-password",
        json={"current_password": "OldPassword1", "new_password": "NewPassword99"},
        headers={"Authorization": f"Bearer {old_token}"},
    )

    # Login to get a fresh token that carries the updated token_version
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "fresh_token@example.com", "password": "NewPassword99"},
    )
    assert login_resp.status_code == 200
    fresh_token = login_resp.json()["access_token"]

    # The fresh token must work
    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {fresh_token}"},
    )
    assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_token_with_missing_token_ver_claim_returns_401(client, db_session):
    """
    A JWT that has no token_ver claim at all must be rejected.
    get_current_analyst treats a missing claim the same as a mismatched one.
    """
    analyst = await create_analyst_in_db(
        db_session,
        email="no_ver@example.com",
    )
    # Mint a token WITHOUT token_ver
    settings = make_test_settings()
    token_without_ver = create_access_token(
        data={"sub": str(analyst.id)},
        secret=settings.JWT_SECRET_KEY,
        expire_hours=settings.JWT_EXPIRE_HOURS,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token_without_ver}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_with_stale_version_integer_is_rejected(client, db_session):
    """
    A token carrying token_ver=0 is rejected when the DB has token_version=1.

    This covers the case where an attacker kept a token from before a
    password change and tries to replay it.

    We increment token_version directly in the DB to avoid the rate-limiter
    on the change-password endpoint firing when many tests run together.
    """
    from sqlalchemy import select, update
    from app.models.analyst import Analyst as AnalystModel

    analyst = await create_analyst_in_db(
        db_session,
        email="stale_ver@example.com",
    )
    # Mint a token with version 0 (the initial value)
    stale_token = make_token_with_claims(analyst, {"token_ver": 0})

    # Simulate a password change by incrementing token_version directly in the DB
    await db_session.execute(
        update(AnalystModel)
        .where(AnalystModel.id == analyst.id)
        .values(token_version=1)
    )
    await db_session.commit()

    # Now stale_token has token_ver=0 but DB has token_version=1 → rejected
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {stale_token}"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# require_admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_admin_blocks_non_admin_analyst(client, db_session):
    """
    A regular (non-admin) analyst with a valid token must receive 403
    when calling an admin-only endpoint (POST /api/analysts).
    """
    regular = await create_analyst_in_db(
        db_session,
        email="regular@example.com",
        is_admin=False,
    )
    token = make_token_for(regular)

    # POST /api/analysts requires require_admin
    response = await client.post(
        "/api/analysts",
        json={
            "email": "new_analyst@example.com",
            "full_name": "New Person",
            "password": "AnyPassword1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_allows_admin_analyst(client, db_session):
    """
    An admin analyst with a valid token must be allowed through the
    require_admin gate.
    """
    admin = await create_analyst_in_db(
        db_session,
        email="admin@example.com",
        is_admin=True,
    )
    token = make_token_for(admin)

    response = await client.post(
        "/api/analysts",
        json={
            "email": "brand_new@example.com",
            "full_name": "Brand New",
            "password": "AnyPassword1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_require_admin_rejects_unauthenticated_request(client, db_session):
    """No token on an admin endpoint → 401 from HTTPBearer."""
    response = await client.post(
        "/api/analysts",
        json={
            "email": "any@example.com",
            "full_name": "Any",
            "password": "AnyPassword1",
        },
    )
    assert response.status_code == 401
