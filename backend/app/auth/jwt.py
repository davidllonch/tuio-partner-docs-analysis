import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against its stored hash."""
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, secret: str, expire_hours: int, algorithm: str = "HS256") -> str:
    """
    Create a signed JWT token.
    Think of it like a tamper-proof wristband for a concert:
    it proves who you are and when it expires.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    payload["exp"] = expire
    payload["iat"] = datetime.now(timezone.utc)
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token


async def get_current_analyst(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    FastAPI dependency: verify the Bearer token and return the matching Analyst.
    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    # Import here to avoid circular imports
    from app.models.analyst import Analyst

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        analyst_id: Optional[str] = payload.get("sub")
        if analyst_id is None:
            raise credentials_exception
    except (ExpiredSignatureError, InvalidTokenError):
        logger.warning("JWT validation failed")
        raise credentials_exception

    try:
        analyst_uuid = uuid.UUID(analyst_id)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(Analyst).where(Analyst.id == analyst_uuid))
    analyst = result.scalar_one_or_none()

    if analyst is None:
        raise credentials_exception
    if not analyst.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst account is inactive",
        )

    return analyst


async def require_admin(
    current_analyst: "Analyst" = Depends(get_current_analyst),
) -> "Analyst":
    """
    Like get_current_analyst but also checks is_admin == True.
    Raises HTTP 403 if the authenticated analyst does not have admin privileges.
    """
    if not current_analyst.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_analyst
