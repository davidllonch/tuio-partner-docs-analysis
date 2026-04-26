import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_analyst, require_admin, hash_password
from app.database import get_db
from app.models.analyst import Analyst
from app.schemas.auth import AnalystListItem, AnalystOut, CreateAnalystRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysts", tags=["analysts"])


@router.get("", response_model=list[AnalystListItem])
async def list_analysts(
    current_analyst: Analyst = Depends(get_current_analyst),
    db: AsyncSession = Depends(get_db),
):
    """Return all analyst accounts, ordered by creation date."""
    result = await db.execute(select(Analyst).order_by(Analyst.created_at))
    analysts = result.scalars().all()
    return [AnalystListItem.model_validate(a) for a in analysts]


@router.post("", response_model=AnalystOut, status_code=status.HTTP_201_CREATED)
async def create_analyst(
    body: CreateAnalystRequest,
    current_analyst: Analyst = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new analyst account. Any authenticated analyst can do this.
    Returns HTTP 409 if the email is already registered.
    """
    result = await db.execute(select(Analyst).where(Analyst.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An analyst with this email already exists",
        )

    new_analyst = Analyst(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        is_active=True,
    )
    db.add(new_analyst)
    await db.commit()
    await db.refresh(new_analyst)

    logger.info(
        "Analyst %s created new analyst account: %s",
        current_analyst.email,
        body.email,
    )
    return AnalystOut.model_validate(new_analyst)
