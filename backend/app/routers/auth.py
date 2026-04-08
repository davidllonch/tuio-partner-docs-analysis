import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import verify_password, create_access_token, get_current_analyst
from app.config import get_settings, Settings
from app.database import get_db
from app.models.analyst import Analyst
from app.schemas.auth import LoginRequest, TokenResponse, AnalystOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Authenticate an analyst and return a JWT access token.

    The token works like a temporary VIP wristband: you prove who you are once
    (with your email + password), and then you show the wristband for all
    subsequent requests. It expires after the configured number of hours.
    """
    # Look up analyst by email
    result = await db.execute(select(Analyst).where(Analyst.email == body.email))
    analyst = result.scalar_one_or_none()

    # We check both "not found" and "wrong password" with the same error message.
    # This is intentional — telling an attacker which one is wrong would help them.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if analyst is None:
        logger.warning("Login attempt for unknown email: %s", body.email)
        raise invalid_credentials

    if not verify_password(body.password, analyst.hashed_password):
        logger.warning("Failed login attempt for email: %s", body.email)
        raise invalid_credentials

    if not analyst.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    token = create_access_token(
        data={"sub": str(analyst.id)},
        secret=settings.JWT_SECRET_KEY,
        expire_hours=settings.JWT_EXPIRE_HOURS,
    )

    logger.info("Analyst logged in: %s", analyst.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        analyst=AnalystOut.model_validate(analyst),
    )


@router.get("/me", response_model=AnalystOut)
async def get_me(current_analyst: Analyst = Depends(get_current_analyst)):
    """Return the currently authenticated analyst's profile."""
    return AnalystOut.model_validate(current_analyst)
