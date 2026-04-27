import re
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr  # Q5: validate email format before attempting DB lookup
    # bcrypt silently truncates input at 72 bytes — characters beyond that have no effect
    # on the resulting hash. We cap at 72 to match bcrypt's actual behaviour and avoid
    # users believing long passwords beyond 72 chars add security.
    password: str = Field(max_length=72)


class AnalystOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_admin: bool

    model_config = {"from_attributes": True}


class AnalystListItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    analyst: AnalystOut


def _validate_password_complexity(value: str) -> str:
    """
    Passwords must be at least 8 characters and contain:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit")
    return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=72)
    new_password: str = Field(min_length=8, max_length=72, description="Minimum 8 characters, with uppercase, lowercase and digit")

    @field_validator("new_password")
    @classmethod
    def new_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class CreateAnalystRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72, description="Minimum 8 characters, with uppercase, lowercase and digit")

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)
