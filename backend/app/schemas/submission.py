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
