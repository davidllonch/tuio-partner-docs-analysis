import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import asyncio
import html as html_lib
import markdown as md_lib
import weasyprint
import nh3

from pydantic import BaseModel

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_analyst
from app.config import Settings, get_settings
from app.database import get_db, AsyncSessionLocal
from app.models.analysis import Analysis
from app.models.analyst import Analyst
from app.models.audit import AuditLog
from app.models.invitation import Invitation
from app.models.submission import Document, Submission
from app.schemas.submission import (
    ReanalyseRequest,
    ReanalyseResponse,
    SubmissionDetail,
    SubmissionListResponse,
    VALID_ENTITY_TYPES,
    VALID_PROVIDER_TYPES,
)
from app.services.ai_analysis import run_analysis
from app.services.email_service import send_submission_notification
from app.services.extraction import extract_documents

logger = logging.getLogger(__name__)

router = APIRouter(tags=["submissions"])

# HTML tags that are safe to include in a generated PDF.
# Any other tags produced by the Markdown→HTML conversion are stripped by nh3.
_PDF_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li",
    "strong", "em", "b", "i",
    "table", "thead", "tbody", "tr", "th", "td",
    "hr", "blockquote", "code", "pre", "br",
}

# Module-level limiter for the public submission endpoint.
_limiter = Limiter(key_func=get_remote_address)

# File type allowlist — only these MIME types are accepted
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB per file
MAX_TOTAL_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB total


def _sanitize_filename(filename: str) -> str:
    """
    Make a filename safe for storage:
    - Replace spaces with underscores
    - Remove characters that could cause path traversal attacks
    - Keep the extension
    """
    filename = os.path.basename(filename)
    filename = filename.replace(" ", "_")
    filename = re.sub(r"[^\w\-.]", "", filename)
    if not filename:
        filename = "document"
    return filename


async def _write_file_to_disk(upload_file: UploadFile, dest_path: str) -> int:
    """Write an UploadFile to disk and return the number of bytes written."""
    total_bytes = 0
    with open(dest_path, "wb") as f:
        while True:
            chunk = await upload_file.read(1024 * 64)  # 64KB chunks
            if not chunk:
                break
            f.write(chunk)
            total_bytes += len(chunk)
    return total_bytes


async def _log_audit(
    db: AsyncSession,
    action: str,
    analyst_id: Optional[uuid.UUID] = None,
    submission_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Write an entry to the audit log."""
    log_entry = AuditLog(
        id=uuid.uuid4(),
        analyst_id=analyst_id,
        action=action,
        submission_id=submission_id,
        timestamp=datetime.now(timezone.utc),
        metadata_=metadata,
    )
    db.add(log_entry)
    await db.flush()


# ---------------------------------------------------------------------------
# Background task: AI analysis + email notification
# ---------------------------------------------------------------------------


async def _background_analyse(
    submission_id: uuid.UUID,
    provider_name: str,
    provider_type: str,
    entity_type: str,
    country: str,
    extraction_inputs: list[dict],
    settings: Settings,
) -> None:
    """
    Background task that runs AFTER the HTTP response is returned to the partner.

    Flow:
      1. Extract text/images from the saved documents
      2. Run AI analysis (Anthropic Claude, with OpenAI fallback)
      3. Store the analysis result in the database
      4. Send a brief notification email to the compliance team
      5. Mark the submission as 'complete'

    Uses its own database session because the request session is already closed.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Re-fetch the submission in this new session
            result = await db.execute(
                select(Submission).where(Submission.id == submission_id)
            )
            submission = result.scalar_one()

            # Step 1: Extract text / images from documents
            logger.info("Background: extracting docs for submission %s", submission_id)
            extracted_docs = await extract_documents(extraction_inputs)

            # Step 2: Run AI analysis
            logger.info("Background: running AI analysis for submission %s", submission_id)
            ai_response, model_used = await run_analysis(
                provider_name=provider_name,
                provider_type=provider_type,
                entity_type=entity_type,
                country=country,
                extracted_docs=extracted_docs,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                openai_api_key=settings.OPENAI_API_KEY,
            )

            # Step 3: Store analysis record
            analysis_id = uuid.uuid4()
            analysis = Analysis(
                id=analysis_id,
                submission_id=submission_id,
                provider_type=provider_type,
                ai_response=ai_response,
                ai_model_used=model_used,
                triggered_by="partner",
                analyst_id=None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(analysis)

            # Step 4: Commit analysis + submission to DB first
            submission.status = "complete"
            submission.ai_response = ai_response
            submission.ai_model_used = model_used
            await db.commit()

            # Step 5: Send notification email AFTER commit, so DB is consistent
            # even if the email send fails
            logger.info(
                "Background: sending notification email for submission %s", submission_id
            )
            await send_submission_notification(
                provider_name=provider_name,
                provider_type=provider_type,
                recipient=settings.REPORT_EMAIL_RECIPIENT,
                from_address=settings.EMAIL_FROM_ADDRESS,
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                smtp_user=settings.SMTP_USER,
                smtp_password=settings.SMTP_PASSWORD,
            )
            email_sent_at = datetime.now(timezone.utc)
            analysis.email_sent_at = email_sent_at
            submission.email_sent_at = email_sent_at
            await db.commit()
            logger.info("Background: submission %s completed successfully", submission_id)

        except Exception as exc:
            logger.error(
                "Background analysis failed for submission %s: %s",
                submission_id,
                exc,
                exc_info=True,
            )
            # Roll back any dirty state before attempting the error-state write
            try:
                await db.rollback()
                result = await db.execute(
                    select(Submission).where(Submission.id == submission_id)
                )
                submission = result.scalar_one_or_none()
                if submission:
                    submission.status = "error"
                    submission.error_message = str(exc)
                    await db.commit()
            except Exception as db_exc:
                logger.error("Could not save error state for submission %s: %s", submission_id, db_exc)
                await db.rollback()


# ---------------------------------------------------------------------------
# Public endpoint: partner submits documents
# ---------------------------------------------------------------------------


@router.post("/submissions", status_code=200)
@_limiter.limit("20/hour")
async def create_submission(
    request: Request,
    background_tasks: BackgroundTasks,
    provider_name: str = Form(...),
    provider_type: str = Form(...),
    entity_type: str = Form(...),
    country: str = Form(...),
    files: List[UploadFile] = File(...),
    labels: List[str] = Form(...),
    invitation_token: Optional[str] = Form(None),
    not_applicable_slots: Optional[str] = Form(None),
    partner_info: Optional[str] = Form(None),
    contract_data: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Public endpoint: a partner submits their KYC/KYB documents for review.

    Returns immediately after saving documents to disk and database.
    AI analysis and email notification run in the background — the partner
    does not have to wait for them.

    Rate limited to 20 requests per hour per IP address.
    """
    # ── 1. Input validation ──────────────────────────────────────────────────

    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"provider_type must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )

    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_type must be 'PF' (persona física) or 'PJ' (persona jurídica)",
        )

    if len(provider_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider_name must not exceed 255 characters",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required",
        )

    if len(labels) != len(files):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Number of labels ({len(labels)}) must match number of files ({len(files)})",
        )

    # Validate each file's MIME type and size
    file_sizes: list[int] = []
    for i, upload_file in enumerate(files):
        if upload_file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"File '{upload_file.filename}' has unsupported type '{upload_file.content_type}'. "
                    f"Allowed: PDF, JPEG, PNG, DOCX"
                ),
            )
        content = await upload_file.read()
        size = len(content)
        await upload_file.seek(0)

        if size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{upload_file.filename}' exceeds the 20 MB size limit",
            )
        file_sizes.append(size)

    total_size = sum(file_sizes)
    if total_size > MAX_TOTAL_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Total upload size ({total_size // 1024 // 1024} MB) exceeds the 100 MB limit",
        )

    # ── 1b. If invitation_token provided, validate and load invitation data ───
    invitation: Optional[Invitation] = None
    if invitation_token:
        inv_result = await db.execute(
            select(Invitation).where(Invitation.token == invitation_token)
        )
        invitation = inv_result.scalar_one_or_none()

        if invitation is None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invitation not found or has expired",
            )
        if invitation.status == "submitted":
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="already_used",
            )
        if invitation.status == "expired" or invitation.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="expired",
            )

        # Override form values with invitation data (security: partner cannot modify these)
        provider_name = invitation.provider_name
        provider_type = invitation.provider_type
        entity_type = invitation.entity_type
        country = invitation.country

    # ── 2. Create submission record ──────────────────────────────────────────

    submission_id = uuid.uuid4()
    submission = Submission(
        id=submission_id,
        created_at=datetime.now(timezone.utc),
        provider_name=provider_name,
        provider_type=provider_type,
        entity_type=entity_type,
        country=country,
        status="pending",
        invitation_id=invitation.id if invitation else None,
        not_applicable_slots=not_applicable_slots,
        partner_info=partner_info,
        contract_data=contract_data,
    )
    db.add(submission)
    await db.flush()

    # ── 3. Create storage directory ──────────────────────────────────────────

    submission_dir = os.path.join(settings.DOCUMENTS_BASE_PATH, str(submission_id))
    os.makedirs(submission_dir, exist_ok=True)

    # ── 4. Save files to disk + create Document records ──────────────────────

    document_records: list[Document] = []
    extraction_inputs: list[dict] = []

    for i, upload_file in enumerate(files):
        safe_filename = _sanitize_filename(upload_file.filename or f"document_{i}")
        file_path = os.path.join(submission_dir, safe_filename)

        if os.path.exists(file_path):
            name, ext = os.path.splitext(safe_filename)
            safe_filename = f"{name}_{i}{ext}"
            file_path = os.path.join(submission_dir, safe_filename)

        size_bytes = await _write_file_to_disk(upload_file, file_path)

        doc = Document(
            id=uuid.uuid4(),
            submission_id=submission_id,
            original_filename=upload_file.filename or safe_filename,
            user_label=labels[i],
            file_path=file_path,
            mime_type=upload_file.content_type,
            size_bytes=size_bytes,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        document_records.append(doc)

        extraction_inputs.append(
            {
                "filename": safe_filename,
                "label": labels[i],
                "file_path": file_path,
                "mime_type": upload_file.content_type,
            }
        )

    # ── 5. Commit to DB and schedule background analysis ─────────────────────

    submission.status = "analysing"
    await db.commit()

    # Mark invitation as used (atomic with the submission commit above)
    if invitation:
        invitation.status = "submitted"
        invitation.submission_id = submission_id
        await db.commit()

    # Schedule AI analysis + email as a background task.
    # The partner receives a success response immediately — no waiting.
    background_tasks.add_task(
        _background_analyse,
        submission_id=submission_id,
        provider_name=provider_name,
        provider_type=provider_type,
        entity_type=entity_type,
        country=country,
        extraction_inputs=extraction_inputs,
        settings=settings,
    )

    logger.info(
        "Submission %s saved. AI analysis scheduled as background task.", submission_id
    )
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Protected endpoints (analyst JWT required)
# ---------------------------------------------------------------------------


@router.get("/models")
async def list_models(
    current_analyst: Analyst = Depends(get_current_analyst),
    settings: Settings = Depends(get_settings),
):
    """
    Return the list of available Claude models from Anthropic.
    Analysts use this to choose which model to use for re-analysis.
    """
    import anthropic as anthropic_lib

    client = anthropic_lib.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        models_page = client.models.list()
        claude_models = [
            {
                "id": m.id,
                "display_name": getattr(m, "display_name", m.id),
            }
            for m in models_page.data
            if m.id.startswith("claude-")
        ]
        return {"models": claude_models}
    except Exception as exc:
        logger.error("Failed to fetch models from Anthropic: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve model list from Anthropic.",
        )


@router.get("/submissions", response_model=SubmissionListResponse)
async def list_submissions(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return a paginated list of all submissions.
    Analysts use this to browse all incoming partner document requests.
    """
    if page < 1:
        page = 1
    if size < 1 or size > 100:
        size = 20

    offset = (page - 1) * size

    count_result = await db.execute(select(func.count(Submission.id)))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Submission)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    submissions = result.scalars().all()

    return SubmissionListResponse(
        items=submissions,
        total=total,
        page=page,
        size=size,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
async def get_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return full detail for a single submission, including documents and analysis history.
    Also records a 'submission_viewed' audit log entry.
    """
    result = await db.execute(
        select(Submission)
        .options(
            selectinload(Submission.documents),
            selectinload(Submission.analyses),
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    await _log_audit(
        db=db,
        action="submission_viewed",
        analyst_id=current_analyst.id,
        submission_id=submission_id,
        metadata={"analyst_email": current_analyst.email},
    )
    await db.commit()

    return submission


@router.get("/submissions/{submission_id}/documents/{doc_id}")
async def download_document(
    submission_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Stream a document file to the analyst's browser.
    Records a 'document_downloaded' audit log entry.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.submission_id == submission_id,
        )
    )
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not os.path.exists(document.file_path):
        logger.error(
            "File not found on disk: %s (doc_id=%s)", document.file_path, doc_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File no longer exists on disk",
        )

    await _log_audit(
        db=db,
        action="document_downloaded",
        analyst_id=current_analyst.id,
        submission_id=submission_id,
        metadata={
            "document_id": str(doc_id),
            "filename": document.original_filename,
            "analyst_email": current_analyst.email,
        },
    )
    await db.commit()

    def iter_file():
        with open(document.file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 64)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=document.mime_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document.original_filename.replace(chr(34), "_")}"'
            ),
            "Content-Length": str(document.size_bytes),
        },
    )


@router.post("/submissions/{submission_id}/reanalyse", response_model=ReanalyseResponse)
async def reanalyse_submission(
    submission_id: uuid.UUID,
    body: ReanalyseRequest,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
    settings: Settings = Depends(get_settings),
):
    """
    Re-run AI analysis on an existing submission, optionally correcting the provider type.
    Analysts use this when a partner selected the wrong provider category.
    """
    result = await db.execute(
        select(Submission)
        .options(selectinload(Submission.documents))
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    if not submission.documents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot reanalyse: submission has no documents",
        )

    extraction_inputs: list[dict] = []
    for doc in submission.documents:
        if not os.path.exists(doc.file_path):
            logger.warning(
                "Document file missing on disk during reanalysis: %s", doc.file_path
            )
            continue
        extraction_inputs.append(
            {
                "filename": doc.original_filename,
                "label": doc.user_label,
                "file_path": doc.file_path,
                "mime_type": doc.mime_type,
            }
        )

    if not extraction_inputs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot reanalyse: no document files found on disk",
        )

    try:
        logger.info("Re-extracting documents for submission %s (reanalysis)", submission_id)
        extracted_docs = await extract_documents(extraction_inputs)

        logger.info(
            "Running reanalysis for submission %s with provider_type=%s",
            submission_id,
            body.provider_type,
        )
        ai_response, model_used = await run_analysis(
            provider_name=submission.provider_name,
            provider_type=body.provider_type,
            entity_type=submission.entity_type,
            country=submission.country,
            extracted_docs=extracted_docs,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            openai_api_key=settings.OPENAI_API_KEY,
            model=body.model or "claude-sonnet-4-6",
        )

        analysis_id = uuid.uuid4()
        analysis = Analysis(
            id=analysis_id,
            submission_id=submission_id,
            provider_type=body.provider_type,
            ai_response=ai_response,
            ai_model_used=model_used,
            triggered_by="analyst",
            analyst_id=current_analyst.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(analysis)

        submission.ai_response = ai_response
        submission.ai_model_used = model_used
        submission.status = "complete"
        submission.error_message = None

        await _log_audit(
            db=db,
            action="reanalysis_triggered",
            analyst_id=current_analyst.id,
            submission_id=submission_id,
            metadata={
                "analyst_email": current_analyst.email,
                "new_provider_type": body.provider_type,
                "analysis_id": str(analysis_id),
                "model_used": model_used,
            },
        )

        await db.commit()

        logger.info(
            "Reanalysis completed for submission %s (analysis_id=%s)", submission_id, analysis_id
        )
        return ReanalyseResponse(status="ok", analysis_id=str(analysis_id))

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Reanalysis failed for submission %s: %s", submission_id, exc, exc_info=True
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reanalysis failed. Please try again or contact support.",
        )


# ---------------------------------------------------------------------------
# PATCH /submissions/{submission_id}/contract-data  (JWT required)
# ---------------------------------------------------------------------------


class ContractDataUpdate(BaseModel):
    contract_data: str


@router.patch("/submissions/{submission_id}/contract-data")
async def update_contract_data(
    submission_id: uuid.UUID,
    body: ContractDataUpdate,
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Save or update the contract data (fields + commissions) for a submission.
    Analysts call this after configuring commission tiers for the partner contract.
    """
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    submission.contract_data = body.contract_data
    await db.commit()
    return {"ok": True}


# ── PDF Report Download ───────────────────────────────────────────────────────

@router.get("/submissions/{submission_id}/report.pdf")
async def download_report_pdf(
    submission_id: uuid.UUID,
    current_analyst: Analyst = Depends(get_current_analyst),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download the KYC/KYB report for a submission as a PDF.
    The PDF contains real selectable text (not an image), generated from the
    AI Markdown response using weasyprint.
    """
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if not submission.ai_response:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report available for this submission")

    # Convert Markdown → HTML (tables extension for the semaphore table),
    # then sanitize to remove any unexpected tags from the AI output (C1).
    html_body = md_lib.markdown(submission.ai_response, extensions=["tables", "extra"])
    html_body = nh3.clean(html_body, tags=_PDF_ALLOWED_TAGS)

    # Escape values that go into the HTML template
    safe_provider = html_lib.escape(submission.provider_name or "Unknown")
    safe_date = html_lib.escape(submission.created_at.strftime("%d/%m/%Y"))

    full_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    @page {{ size: A4; margin: 2cm 2.2cm; }}
    body {{ font-family: "Liberation Sans", Arial, sans-serif; font-size: 11pt; line-height: 1.6; color: #1a1a1a; }}
    .doc-header {{ border-bottom: 2px solid #4f46e5; padding-bottom: 10px; margin-bottom: 20px; }}
    .doc-header h1 {{ font-size: 14pt; color: #4f46e5; margin: 0 0 4px 0; }}
    .doc-header p {{ font-size: 9pt; color: #6b7280; margin: 0; }}
    .page-footer {{ position: fixed; bottom: 0.8cm; right: 0; left: 0; font-size: 8pt; color: #9ca3af; text-align: right; padding-right: 2.2cm; border-top: 1px solid #e5e7eb; padding-top: 3px; }}
    h1 {{ font-size: 13pt; font-weight: bold; border-bottom: 1px solid #e5e7eb; padding-bottom: 5px; margin: 20px 0 10px; }}
    h2 {{ font-size: 12pt; font-weight: bold; margin: 16px 0 8px; color: #1f2937; }}
    h3 {{ font-size: 11pt; font-weight: bold; margin: 12px 0 6px; color: #374151; }}
    p {{ margin: 0 0 8px 0; }}
    ul, ol {{ margin: 0 0 8px 18px; padding: 0; }}
    li {{ margin-bottom: 3px; }}
    hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 10pt; }}
    th {{ background-color: #f3f4f6; font-weight: bold; text-align: left; padding: 6px 8px; border: 1px solid #d1d5db; font-size: 9pt; text-transform: uppercase; }}
    td {{ padding: 5px 8px; border: 1px solid #d1d5db; vertical-align: top; }}
    tr:nth-child(even) td {{ background-color: #f9fafb; }}
    code {{ background: #f3f4f6; padding: 1px 4px; font-family: "Liberation Mono", monospace; font-size: 9pt; }}
    blockquote {{ border-left: 3px solid #c7d2fe; margin: 0 0 8px 0; padding-left: 12px; color: #6b7280; font-style: italic; }}
    strong {{ font-weight: bold; }}
  </style>
</head>
<body>
  <div class="doc-header">
    <h1>Informe KYC/KYB — {safe_provider}</h1>
    <p>Generat el {safe_date} · Tuio Partners</p>
  </div>
  <div class="page-footer">Informe KYC/KYB — {safe_provider} · {safe_date}</div>
  {html_body}
</body>
</html>"""

    # Run weasyprint in a thread pool — it's synchronous and would block the event loop
    pdf_bytes = await asyncio.to_thread(
        lambda: weasyprint.HTML(string=full_html).write_pdf()
    )

    # Build a strictly ASCII-only filename (C2).
    # re.ASCII ensures \w only matches [a-zA-Z0-9_], excluding any Unicode letters.
    safe_name = re.sub(r"[^\w\s\-]", "", submission.provider_name or "", flags=re.ASCII).strip().replace(" ", "_")
    filename = f"Informe_KYC_{safe_name}.pdf" if safe_name else "Informe_KYC.pdf"

    # Record PDF download in the audit log (W2)
    await _log_audit(
        db=db,
        action="report_pdf_downloaded",
        analyst_id=current_analyst.id,
        submission_id=submission_id,
        metadata={
            "analyst_email": current_analyst.email,
            "filename": filename,
        },
    )
    await db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
