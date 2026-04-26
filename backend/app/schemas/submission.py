import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator


VALID_PROVIDER_TYPES = {
    "correduria_seguros",
    "agencia_seguros",
    "colaborador_externo",
    "generador_leads",
}

VALID_ENTITY_TYPES = {"PF", "PJ"}


class DocumentOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    user_label: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class AnalysisSummaryOut(BaseModel):
    id: uuid.UUID
    provider_type: str
    ai_model_used: Optional[str]
    triggered_by: str
    created_at: datetime
    email_sent_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SubmissionListItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    provider_name: str
    provider_type: str
    entity_type: str
    country: str
    status: str
    email_sent_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SubmissionDetail(BaseModel):
    id: uuid.UUID
    created_at: datetime
    provider_name: str
    provider_type: str
    entity_type: str
    country: str
    status: str
    ai_response: Optional[str]
    ai_model_used: Optional[str]
    email_sent_at: Optional[datetime]
    error_message: Optional[str]
    partner_info: Optional[str]
    contract_data: Optional[str] = None
    documents: List[DocumentOut]
    analyses: List[AnalysisSummaryOut]

    model_config = {"from_attributes": True}


class SubmissionListResponse(BaseModel):
    items: List[SubmissionListItem]
    total: int
    page: int
    size: int


class ReanalyseRequest(BaseModel):
    provider_type: str
    model: Optional[str] = None  # If None, uses the default model

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v: str) -> str:
        if v not in VALID_PROVIDER_TYPES:
            raise ValueError(
                f"provider_type must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}"
            )
        return v


class ReanalyseResponse(BaseModel):
    status: str
    analysis_id: str


# ── Invitation schemas ────────────────────────────────────────────────────────

class AnalystSummary(BaseModel):
    id: uuid.UUID
    full_name: Optional[str]

    model_config = {"from_attributes": True}


class CreateInvitationRequest(BaseModel):
    provider_name: str
    provider_type: str
    entity_type: str
    country: str

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v: str) -> str:
        if v not in VALID_PROVIDER_TYPES:
            raise ValueError(
                f"provider_type must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}"
            )
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError("entity_type must be 'PF' or 'PJ'")
        return v

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("provider_name is required")
        if len(v) > 255:
            raise ValueError("provider_name must not exceed 255 characters")
        return v

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("country is required")
        if len(v) > 100:
            raise ValueError("country must not exceed 100 characters")
        return v


class InvitationListItem(BaseModel):
    id: uuid.UUID
    token: str
    provider_name: str
    provider_type: str
    entity_type: str
    country: str
    status: str
    created_at: datetime
    expires_at: datetime
    submission_id: Optional[uuid.UUID]
    created_by_analyst: Optional[AnalystSummary]

    model_config = {"from_attributes": True}


class InvitationCreateResponse(InvitationListItem):
    invitation_url: str


class InvitationPublic(BaseModel):
    """Returned by the public GET /invitations/:token endpoint.
    Does NOT include the internal id, token, or analyst details."""
    provider_name: str
    provider_type: str
    entity_type: str
    country: str
    status: str

    model_config = {"from_attributes": True}


class InvitationListResponse(BaseModel):
    items: List[InvitationListItem]
    total: int
    page: int
    size: int
