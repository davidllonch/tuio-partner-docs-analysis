import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_analyst
from app.config import Settings, get_settings
from app.database import get_db
from app.models.analyst import Analyst
from app.models.audit import AuditLog
from app.models.declaration_template import DeclarationTemplate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["declaration-templates"])

VALID_PROVIDER_TYPES = {
    "correduria_seguros",
    "agencia_seguros",
    "colaborador_externo",
    "generador_leads",
}

PROVIDER_TYPE_LABELS = {
    "correduria_seguros": "Correduría de Seguros",
    "agencia_seguros": "Agencia de Seguros",
    "colaborador_externo": "Colaborador Externo",
    "generador_leads": "Generador de Leads",
}


class DeclarationTemplateInfo(BaseModel):
    provider_type: str
    provider_type_label: str
    original_filename: str
    uploaded_at: datetime
    uploaded_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AllTemplatesResponse(BaseModel):
    templates: list[DeclarationTemplateInfo]


async def _log_audit(
    db: AsyncSession,
    action: str,
    analyst_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    log_entry = AuditLog(
        id=uuid.uuid4(),
        analyst_id=analyst_id,
        action=action,
        timestamp=datetime.now(timezone.utc),
        metadata_=metadata,
    )
    db.add(log_entry)
    await db.flush()


def _sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = filename.replace(" ", "_")
    filename = re.sub(r"[^\w\-.]", "", filename)
    if not filename:
        filename = "declaration"
    return filename


def _get_template_dir(documents_base_path: str) -> str:
    template_dir = os.path.join(documents_base_path, "declaration_templates")
    os.makedirs(template_dir, exist_ok=True)
    return template_dir


# ---------------------------------------------------------------------------
# GET /api/declaration-templates  (JWT required — list all for admin)
# ---------------------------------------------------------------------------

@router.get("/declaration-templates", response_model=AllTemplatesResponse)
async def list_all_templates(
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return the current declaration template for each provider type.
    Used by the admin UI to show what has been uploaded.
    """
    result = await db.execute(
        select(DeclarationTemplate).options(
            selectinload(DeclarationTemplate.uploaded_by_analyst)
        )
    )
    templates = result.scalars().all()

    template_map = {t.provider_type: t for t in templates}

    items = []
    for pt in VALID_PROVIDER_TYPES:
        t = template_map.get(pt)
        if t:
            items.append(
                DeclarationTemplateInfo(
                    provider_type=t.provider_type,
                    provider_type_label=PROVIDER_TYPE_LABELS.get(t.provider_type, t.provider_type),
                    original_filename=t.original_filename,
                    uploaded_at=t.uploaded_at,
                    uploaded_by_name=(
                        t.uploaded_by_analyst.full_name
                        if t.uploaded_by_analyst
                        else None
                    ),
                )
            )

    return AllTemplatesResponse(templates=items)


# ---------------------------------------------------------------------------
# GET /api/declaration-templates/{provider_type}  (PUBLIC — metadata check)
# ---------------------------------------------------------------------------

@router.get("/declaration-templates/{provider_type}")
async def get_template_info(
    provider_type: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint: returns metadata about a declaration template if it exists.
    Used by the partner invite page to decide whether to show a download button.
    Returns 404 if no template has been uploaded for this provider type.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )

    result = await db.execute(
        select(DeclarationTemplate).where(DeclarationTemplate.provider_type == provider_type)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No template uploaded")

    return {
        "provider_type": template.provider_type,
        "original_filename": template.original_filename,
        "uploaded_at": template.uploaded_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/declaration-templates/{provider_type}/download  (PUBLIC)
# ---------------------------------------------------------------------------

@router.get("/declaration-templates/{provider_type}/download")
async def download_template(
    provider_type: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Public endpoint: download the declaration template PDF for a provider type.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid provider_type",
        )

    result = await db.execute(
        select(DeclarationTemplate).where(DeclarationTemplate.provider_type == provider_type)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No template found")

    if not os.path.exists(template.file_path):
        logger.error(
            "Declaration template file missing on disk: %s (provider_type=%s)",
            template.file_path,
            provider_type,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found on disk",
        )

    return FileResponse(
        path=template.file_path,
        media_type="application/pdf",
        filename=template.original_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{template.original_filename}"'
        },
    )


# ---------------------------------------------------------------------------
# PUT /api/declaration-templates/{provider_type}  (JWT required)
# ---------------------------------------------------------------------------

@router.put("/declaration-templates/{provider_type}", response_model=DeclarationTemplateInfo)
async def upload_template(
    provider_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
    settings: Settings = Depends(get_settings),
):
    """
    Upload or replace the declaration template PDF for a given provider type.
    Only PDF files are accepted. Any analyst can upload/replace a template.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted for declaration templates",
        )

    # Read content to check size (max 20 MB)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File exceeds the 20 MB size limit",
        )
    await file.seek(0)

    # Save to disk — fixed path: declaration_templates/{provider_type}.pdf
    template_dir = _get_template_dir(settings.DOCUMENTS_BASE_PATH)
    file_path = os.path.join(template_dir, f"{provider_type}.pdf")

    with open(file_path, "wb") as f:
        f.write(content)

    safe_original = _sanitize_filename(file.filename or f"{provider_type}_declaraciones.pdf")

    # Upsert in DB — if row exists, update it; otherwise insert
    result = await db.execute(
        select(DeclarationTemplate).where(DeclarationTemplate.provider_type == provider_type)
    )
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        existing.file_path = file_path
        existing.original_filename = safe_original
        existing.uploaded_at = now
        existing.uploaded_by_analyst_id = current_analyst.id
        template = existing
    else:
        template = DeclarationTemplate(
            id=uuid.uuid4(),
            provider_type=provider_type,
            file_path=file_path,
            original_filename=safe_original,
            uploaded_at=now,
            uploaded_by_analyst_id=current_analyst.id,
        )
        db.add(template)

    await _log_audit(
        db=db,
        action="declaration_template_uploaded",
        analyst_id=current_analyst.id,
        metadata={
            "provider_type": provider_type,
            "original_filename": safe_original,
            "analyst_email": current_analyst.email,
        },
    )
    await db.commit()
    await db.refresh(template, ["uploaded_by_analyst"])

    return DeclarationTemplateInfo(
        provider_type=template.provider_type,
        provider_type_label=PROVIDER_TYPE_LABELS.get(template.provider_type, template.provider_type),
        original_filename=template.original_filename,
        uploaded_at=template.uploaded_at,
        uploaded_by_name=(
            template.uploaded_by_analyst.full_name if template.uploaded_by_analyst else None
        ),
    )
