"""
Integration tests for the invitation endpoints.

Endpoints covered:
- POST   /api/invitations          (JWT required)
- GET    /api/invitations          (JWT required)
- GET    /api/invitations/{token}  (public, rate-limited)
- DELETE /api/invitations/{id}     (JWT required)

All tests use the shared in-memory SQLite fixtures from conftest.
"""

import secrets
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import create_analyst_in_db, make_token_for
from app.models.invitation import Invitation, INVITATION_EXPIRY_DAYS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def create_invitation_in_db(
    db_session,
    analyst,
    provider_name: str = "Acme S.L.",
    provider_type: str = "correduria_seguros",
    entity_type: str = "PJ",
    country: str = "ES",
    status: str = "pending",
    days_offset: int = 0,  # negative = expires in the past
) -> Invitation:
    """Insert an Invitation directly into the in-memory DB."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=INVITATION_EXPIRY_DAYS + days_offset)
    invitation = Invitation(
        id=uuid.uuid4(),
        token=secrets.token_hex(32),
        provider_name=provider_name,
        provider_type=provider_type,
        entity_type=entity_type,
        country=country,
        status=status,
        created_at=now,
        expires_at=expires_at,
        created_by_analyst_id=analyst.id,
    )
    db_session.add(invitation)
    await db_session.commit()
    await db_session.refresh(invitation)
    return invitation


# ---------------------------------------------------------------------------
# POST /api/invitations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_invitation_unauthenticated_returns_401(client, db_session):
    """No auth header on POST /api/invitations → FastAPI HTTPBearer returns 401."""
    response = await client.post(
        "/api/invitations",
        json={
            "provider_name": "Acme S.L.",
            "provider_type": "correduria_seguros",
            "entity_type": "PJ",
            "country": "ES",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_invitation_returns_201_with_url(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="inv_creator@example.com")
    token = make_token_for(analyst)

    response = await client.post(
        "/api/invitations",
        json={
            "provider_name": "Acme S.L.",
            "provider_type": "correduria_seguros",
            "entity_type": "PJ",
            "country": "ES",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert "invitation_url" in body
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_create_invitation_url_contains_token(client, db_session):
    """The invitation_url returned must embed a 64-char hex token."""
    analyst = await create_analyst_in_db(db_session, email="inv_url@example.com")
    token = make_token_for(analyst)

    response = await client.post(
        "/api/invitations",
        json={
            "provider_name": "Beta Corp",
            "provider_type": "agencia_seguros",
            "entity_type": "PF",
            "country": "ES",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    url = body["invitation_url"]
    # The token is 64 hex chars — it must appear somewhere in the URL
    # Extract the last path segment
    path_segment = url.rstrip("/").split("/")[-1]
    assert len(path_segment) == 64
    assert path_segment.isalnum()


@pytest.mark.asyncio
async def test_create_invitation_admin_analyst_can_also_create(client, db_session):
    """Admin analysts are not blocked from creating invitations."""
    admin = await create_analyst_in_db(
        db_session, email="admin_inv@example.com", is_admin=True
    )
    token = make_token_for(admin)

    response = await client.post(
        "/api/invitations",
        json={
            "provider_name": "Admin Partner",
            "provider_type": "colaborador_externo",
            "entity_type": "PJ",
            "country": "FR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/invitations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_invitations_unauthenticated_returns_401(client, db_session):
    response = await client.get("/api/invitations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_invitations_returns_pagination_fields(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="list_inv@example.com")
    token = make_token_for(analyst)

    response = await client.get(
        "/api/invitations",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "size" in body


@pytest.mark.asyncio
async def test_list_invitations_invalid_status_filter_returns_422(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="filter_inv@example.com")
    token = make_token_for(analyst)

    response = await client.get(
        "/api/invitations?status_filter=invalid_value",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_invitations_pending_has_invitation_url(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="pending_url@example.com")
    token = make_token_for(analyst)
    await create_invitation_in_db(db_session, analyst, status="pending")

    response = await client.get(
        "/api/invitations?status_filter=pending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["invitation_url"] is not None


@pytest.mark.asyncio
async def test_list_invitations_submitted_has_null_invitation_url(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="submitted_url@example.com")
    token = make_token_for(analyst)
    await create_invitation_in_db(db_session, analyst, status="submitted")

    response = await client.get(
        "/api/invitations?status_filter=submitted",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["invitation_url"] is None


@pytest.mark.asyncio
async def test_list_invitations_expired_has_null_invitation_url(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="expired_url@example.com")
    token = make_token_for(analyst)
    await create_invitation_in_db(db_session, analyst, status="expired")

    response = await client.get(
        "/api/invitations?status_filter=expired",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["invitation_url"] is None


# ---------------------------------------------------------------------------
# GET /api/invitations/{token}  (public)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_invitation_by_valid_pending_token_returns_200(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="pub_token@example.com")
    invitation = await create_invitation_in_db(
        db_session,
        analyst,
        provider_name="PubCorp",
        provider_type="generador_leads",
        entity_type="PF",
        country="ES",
        status="pending",
    )

    response = await client.get(f"/api/invitations/{invitation.token}")

    assert response.status_code == 200
    body = response.json()
    assert body["provider_name"] == "PubCorp"
    assert body["provider_type"] == "generador_leads"
    assert body["entity_type"] == "PF"
    assert body["country"] == "ES"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_get_invitation_public_response_has_no_analyst_details(client, db_session):
    """The public endpoint must not leak analyst info or the raw invitation id/token."""
    analyst = await create_analyst_in_db(db_session, email="leak_test@example.com")
    invitation = await create_invitation_in_db(db_session, analyst, status="pending")

    response = await client.get(f"/api/invitations/{invitation.token}")

    assert response.status_code == 200
    body = response.json()
    # Must NOT include internal fields
    assert "id" not in body
    assert "token" not in body
    assert "created_by_analyst" not in body
    assert "created_by_analyst_id" not in body


@pytest.mark.asyncio
async def test_get_invitation_submitted_returns_404(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="sub_token@example.com")
    invitation = await create_invitation_in_db(db_session, analyst, status="submitted")

    response = await client.get(f"/api/invitations/{invitation.token}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_invitation_expired_returns_404(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="exp_token@example.com")
    invitation = await create_invitation_in_db(db_session, analyst, status="expired")

    response = await client.get(f"/api/invitations/{invitation.token}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_invitation_cancelled_returns_404(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="can_token@example.com")
    invitation = await create_invitation_in_db(db_session, analyst, status="cancelled")

    response = await client.get(f"/api/invitations/{invitation.token}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_invitation_wrong_length_token_returns_404(client, db_session):
    # Token is 63 chars — one short of the required 64
    short_token = "a" * 63
    response = await client.get(f"/api/invitations/{short_token}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_invitation_non_alnum_token_returns_404(client, db_session):
    # Token contains a hyphen — not alnum
    bad_token = "a" * 31 + "-" + "b" * 32
    response = await client.get(f"/api/invitations/{bad_token}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/invitations/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_invitation_unauthenticated_returns_401(client, db_session):
    fake_id = uuid.uuid4()
    response = await client.delete(f"/api/invitations/{fake_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cancel_pending_invitation_returns_204_and_status_cancelled(
    client, db_session
):
    analyst = await create_analyst_in_db(db_session, email="del_pending@example.com")
    token = make_token_for(analyst)
    invitation = await create_invitation_in_db(db_session, analyst, status="pending")

    response = await client.delete(
        f"/api/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify the status was actually updated in the DB
    from sqlalchemy import select
    from app.models.invitation import Invitation as InvModel
    result = await db_session.execute(
        select(InvModel).where(InvModel.id == invitation.id)
    )
    updated = result.scalar_one()
    assert updated.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_submitted_invitation_returns_409(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="del_submitted@example.com")
    token = make_token_for(analyst)
    invitation = await create_invitation_in_db(db_session, analyst, status="submitted")

    response = await client.delete(
        f"/api/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cancel_expired_invitation_returns_409(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="del_expired@example.com")
    token = make_token_for(analyst)
    invitation = await create_invitation_in_db(db_session, analyst, status="expired")

    response = await client.delete(
        f"/api/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cancel_nonexistent_invitation_returns_404(client, db_session):
    analyst = await create_analyst_in_db(db_session, email="del_none@example.com")
    token = make_token_for(analyst)

    response = await client.delete(
        f"/api/invitations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
