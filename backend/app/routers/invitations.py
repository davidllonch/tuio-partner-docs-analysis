import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_analyst
from app.utils.rate_limit import limiter as _limiter
from app.config import Settings, get_settings
from app.database import get_db
from app.models.analyst import Analyst
from app.models.invitation import Invitation
from app.utils.audit import log_audit
from app.schemas.submission import (
    CreateInvitationRequest,
    InvitationCreateResponse,
    InvitationListItem,
    InvitationListResponse,
    InvitationPublic,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invitations"])


# ---------------------------------------------------------------------------
# POST /api/invitations  (JWT required)
# ---------------------------------------------------------------------------

@router.post("/invitations", response_model=InvitationCreateResponse, status_code=201)
async def create_invitation(
    body: CreateInvitationRequest,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
    settings: Settings = Depends(get_settings),
):
    """
    Create a new partner invitation.
    Returns the invitation record plus a ready-to-send URL.
    """
    now = datetime.now(timezone.utc)
    invitation = Invitation(
        id=uuid.uuid4(),
        provider_name=body.provider_name,
        provider_type=body.provider_type,
        entity_type=body.entity_type,
        country=body.country,
        created_by_analyst_id=current_analyst.id,
        created_at=now,
        expires_at=now + timedelta(days=30),
        status="pending",
    )
    db.add(invitation)
    await db.flush()

    await log_audit(
        db=db,
        action="invitation_created",
        analyst_id=current_analyst.id,
        metadata={
            "invitation_id": str(invitation.id),
            "provider_name": body.provider_name,
            "provider_type": body.provider_type,
            "analyst_email": current_analyst.email,
        },
    )
    await db.commit()
    await db.refresh(invitation)

    # Eagerly load the analyst relationship so the schema serialiser can read it
    await db.refresh(invitation, ["created_by_analyst"])

    invitation_url = f"{settings.FRONTEND_BASE_URL}/invite/{invitation.token}"

    logger.info(
        "Invitation %s created by analyst %s for partner '%s'",
        invitation.id,
        current_analyst.email,
        body.provider_name,
    )

    return InvitationCreateResponse(
        **InvitationListItem.model_validate(invitation).model_dump(),
        invitation_url=invitation_url,
    )


# ---------------------------------------------------------------------------
# GET /api/invitations  (JWT required)
# ---------------------------------------------------------------------------

@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    status_filter: str | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return a paginated list of all invitations (all analysts see all invitations).
    Optionally filter by status: pending | submitted | expired.
    """
    # S6: validate status_filter against the known set of valid values
    VALID_STATUSES = {"pending", "submitted", "expired", "cancelled"}
    if status_filter and status_filter not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status_filter value")

    if page < 1:
        page = 1
    if page > 10_000:
        page = 10_000
    if size < 1 or size > 100:
        size = 20

    offset = (page - 1) * size

    base_query = select(Invitation).options(
        selectinload(Invitation.created_by_analyst)
    )

    if status_filter:
        base_query = base_query.where(Invitation.status == status_filter)

    count_query = select(func.count(Invitation.id))
    if status_filter:
        count_query = count_query.where(Invitation.status == status_filter)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Invitation.created_at.desc()).offset(offset).limit(size)
    )
    invitations = result.scalars().all()

    return InvitationListResponse(
        items=invitations,
        total=total,
        page=page,
        size=size,
    )


# ---------------------------------------------------------------------------
# GET /api/invitations/{token}  (PUBLIC, rate limited)
# ---------------------------------------------------------------------------

@router.get("/invitations/{token}", response_model=InvitationPublic)
@_limiter.limit("20/minute")
async def get_invitation_by_token(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint used by the partner to load their invitation context.
    Rate limited to prevent token brute-forcing.
    Returns only non-sensitive fields — no token, no analyst details.
    """
    result = await db.execute(
        select(Invitation).where(Invitation.token == token)
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Auto-expire invitations that have passed their expiry date
    if invitation.status == "pending" and invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = "expired"
        await db.commit()

    if invitation.status == "submitted":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="already_used")

    if invitation.status == "expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="expired")

    return invitation


# ---------------------------------------------------------------------------
# DELETE /api/invitations/{id}  (JWT required)
# ---------------------------------------------------------------------------

@router.delete("/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Cancel a pending invitation (sets status to 'expired').
    Already-submitted or already-expired invitations cannot be cancelled.
    """
    result = await db.execute(
        select(Invitation).where(Invitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel an invitation with status '{invitation.status}'",
        )

    invitation.status = "cancelled"

    await log_audit(
        db=db,
        action="invitation_cancelled",
        analyst_id=current_analyst.id,
        metadata={
            "invitation_id": str(invitation_id),
            "provider_name": invitation.provider_name,
            "analyst_email": current_analyst.email,
        },
    )
    await db.commit()

    logger.info(
        "Invitation %s cancelled by analyst %s", invitation_id, current_analyst.email
    )
