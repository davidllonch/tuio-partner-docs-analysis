import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_analyst
from app.config import Settings, get_settings
from app.database import get_db
from app.models.analysis import Analysis
from app.models.analyst import Analyst
from app.models.audit import AuditLog
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
from app.services.email_service import send_kyc_report
from app.services.extraction import extract_documents

logger = logging.getLogger(__name__)

router = APIRouter(tags=["submissions"])

# Module-level limiter for the public submission endpoint.
# This instance reads the rate-limit state from the app's shared limiter via the Request.
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
    # Remove any directory separators (security: prevent path traversal)
    filename = os.path.basename(filename)
    # Replace spaces with underscores
    filename = filename.replace(" ", "_")
    # Remove characters that are not alphanumeric, underscore, hyphen, or dot
    filename = re.sub(r"[^\w\-.]", "", filename)
    # Prevent empty filenames
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
    # We flush but don't commit here — the caller handles the transaction
    await db.flush()


# ---------------------------------------------------------------------------
# Public endpoint: partner submits documents
# ---------------------------------------------------------------------------


@router.post("/submissions", status_code=200)
@_limiter.limit("20/hour")
async def create_submission(
    request: Request,
    provider_name: str = Form(...),
    provider_type: str = Form(...),
    entity_type: str = Form(...),
    country: str = Form(...),
    files: List[UploadFile] = File(...),
    labels: List[str] = Form(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Public endpoint: a partner submits their KYC/KYB documents for review.

    This is a synchronous pipeline — the request stays open until the AI
    analysis is complete and the email has been sent. Partners are expected
    to wait (typically 30–60 seconds depending on document size).

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
        # Read file size without loading entire file into memory
        content = await upload_file.read()
        size = len(content)
        await upload_file.seek(0)  # Reset for later reading

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

        # Handle duplicate filenames in the same submission
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

    # ── 5. Update status to 'analysing' ──────────────────────────────────────

    submission.status = "analysing"
    await db.commit()

    # ── 6-9. Extract → AI → Email (wrapped in try/except) ───────────────────

    try:
        # Step 6: Extract text / images from documents
        logger.info("Extracting documents for submission %s", submission_id)
        extracted_docs = await extract_documents(extraction_inputs)

        # Step 7: Run AI analysis
        logger.info("Running AI analysis for submission %s", submission_id)
        ai_response, model_used = await run_analysis(
            provider_name=provider_name,
            provider_type=provider_type,
            entity_type=entity_type,
            country=country,
            extracted_docs=extracted_docs,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            openai_api_key=settings.OPENAI_API_KEY,
        )

        # Step 8: Store AI response + create analysis record
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

        # Step 9: Send email
        logger.info("Sending KYC report email for submission %s", submission_id)
        await send_kyc_report(
            provider_name=provider_name,
            provider_type=provider_type,
            ai_response=ai_response,
            recipient=settings.REPORT_EMAIL_RECIPIENT,
            from_address=settings.EMAIL_FROM_ADDRESS,
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
        )
        email_sent_at = datetime.now(timezone.utc)
        analysis.email_sent_at = email_sent_at

        # Step 10: Mark complete
        submission.status = "complete"
        submission.ai_response = ai_response
        submission.ai_model_used = model_used
        submission.email_sent_at = email_sent_at
        await db.commit()

        logger.info("Submission %s completed successfully", submission_id)
        return {"status": "ok"}

    except Exception as exc:
        logger.error("Submission %s failed: %s", submission_id, exc, exc_info=True)
        # Update submission to error state
        try:
            submission.status = "error"
            submission.error_message = str(exc)
            await db.commit()
        except Exception as db_exc:
            logger.error(
                "Could not save error state for submission %s: %s", submission_id, db_exc
            )
            await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document analysis failed. Please try again or contact support.",
        )


# ---------------------------------------------------------------------------
# Protected endpoints (analyst JWT required)
# ---------------------------------------------------------------------------


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

    # Count total records
    count_result = await db.execute(select(func.count(Submission.id)))
    total = count_result.scalar_one()

    # Fetch page of results, newest first
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

    # Log this view in the audit trail
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

    # Log download in audit trail
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
                chunk = f.read(1024 * 64)  # 64KB chunks
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=document.mime_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document.original_filename}"'
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

    Analysts use this when a partner selected the wrong provider category, or when
    new information warrants a fresh AI review.
    """
    # Load submission with documents
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

    # Verify all document files still exist on disk
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
        # Re-extract text from existing files
        logger.info("Re-extracting documents for submission %s (reanalysis)", submission_id)
        extracted_docs = await extract_documents(extraction_inputs)

        # Run AI with the (possibly corrected) provider type
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
        )

        # Send updated report email
        await send_kyc_report(
            provider_name=submission.provider_name,
            provider_type=body.provider_type,
            ai_response=ai_response,
            recipient=settings.REPORT_EMAIL_RECIPIENT,
            from_address=settings.EMAIL_FROM_ADDRESS,
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
        )
        email_sent_at = datetime.now(timezone.utc)

        # Create new analysis history record
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
            email_sent_at=email_sent_at,
        )
        db.add(analysis)

        # Update the submission with the latest analysis result
        submission.ai_response = ai_response
        submission.ai_model_used = model_used
        submission.email_sent_at = email_sent_at
        submission.status = "complete"
        submission.error_message = None

        # Audit log
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
