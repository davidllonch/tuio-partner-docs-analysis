import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


async def cleanup_old_documents(documents_base_path: str, database_url: str) -> None:
    """
    Delete documents (files on disk + database records) that are older than 90 days.

    This runs automatically every night at 2:00 AM. Think of it like a
    document shredder that automatically destroys files after their retention
    period expires — this is a legal/GDPR best practice.

    Args:
        documents_base_path: Root directory where submission folders are stored
        database_url:        PostgreSQL connection string (kept for scheduler API compat)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    logger.info(
        "Running document cleanup — removing documents uploaded before %s",
        cutoff.isoformat(),
    )

    try:
        # Q2: reuse the shared AsyncSessionLocal instead of creating a new engine
        # every time the job runs. This is the same pattern used by the routers.
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.submission import Document

        async with AsyncSessionLocal() as session:
            # Find all documents older than the cutoff date
            result = await session.execute(
                select(Document).where(Document.uploaded_at < cutoff)
            )
            old_documents = result.scalars().all()

            if not old_documents:
                logger.info("Cleanup: no documents found older than 90 days")
            else:
                deleted_count = 0
                error_count = 0

                for doc in old_documents:
                    # Delete the physical file from disk first.
                    # Wrapped in asyncio.to_thread() so the synchronous filesystem
                    # calls don't block the async event loop while files are being deleted.
                    try:
                        # Defense-in-depth: verify the path is inside the documents directory
                        # before deleting — guards against corrupted or tampered DB records.
                        real_doc_path = os.path.realpath(doc.file_path)
                        real_base = os.path.realpath(documents_base_path)
                        if not real_doc_path.startswith(real_base + os.sep):
                            logger.error(
                                "Cleanup: refusing to delete path outside base dir: %s",
                                doc.file_path,
                            )
                            error_count += 1
                            continue

                        file_exists = await asyncio.to_thread(os.path.exists, real_doc_path)
                        if file_exists:
                            await asyncio.to_thread(os.remove, real_doc_path)
                            logger.debug("Deleted file: %s", doc.file_path)
                    except OSError as exc:
                        logger.warning(
                            "Could not delete file %s: %s", doc.file_path, exc
                        )
                        error_count += 1
                        continue

                    # Delete DB record immediately after the file is gone.
                    # Done before directory cleanup so a directory-cleanup OSError
                    # does not leave an orphan DB record pointing to a missing file.
                    await session.delete(doc)
                    deleted_count += 1

                    # If the parent directory is now empty, remove it
                    try:
                        parent_dir = os.path.dirname(doc.file_path)
                        dir_exists = await asyncio.to_thread(os.path.isdir, parent_dir)
                        if dir_exists:
                            dir_contents = await asyncio.to_thread(os.listdir, parent_dir)
                            if not dir_contents:
                                await asyncio.to_thread(shutil.rmtree, parent_dir, True)
                                logger.debug("Removed empty directory: %s", parent_dir)
                    except OSError as exc:
                        logger.warning("Could not remove directory: %s", exc)

                await session.commit()
                logger.info(
                    "Cleanup complete: %d documents deleted, %d errors",
                    deleted_count,
                    error_count,
                )

            # GDPR data minimisation: anonymise personal data from submissions older
            # than 90 days that have no remaining documents.
            # partner_info and contract_data contain NIF, addresses, and other PII.
            from sqlalchemy import func
            from app.models.submission import Submission

            subs_result = await session.execute(
                select(Submission).where(
                    Submission.created_at < cutoff,
                    Submission.partner_info.isnot(None),
                )
            )
            old_submissions = subs_result.scalars().all()

            anonymized_count = 0
            for sub in old_submissions:
                docs_count_result = await session.execute(
                    select(func.count()).select_from(Document).where(
                        Document.submission_id == sub.id
                    )
                )
                if docs_count_result.scalar() == 0:
                    sub.partner_info = None
                    sub.contract_data = None
                    sub.ai_response = None
                    anonymized_count += 1

            if anonymized_count:
                await session.commit()
                logger.info(
                    "GDPR cleanup: anonymised personal data from %d old submissions",
                    anonymized_count,
                )

    except Exception as exc:
        logger.error("Document cleanup job failed: %s", exc, exc_info=True)


def create_cleanup_scheduler(documents_base_path: str, database_url: str) -> AsyncIOScheduler:
    """
    Create and configure the APScheduler that runs document cleanup every night at 2 AM.

    Returns a configured (but not yet started) scheduler instance.
    Call scheduler.start() to activate it.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        cleanup_old_documents,
        trigger="cron",
        hour=2,
        minute=0,
        args=[documents_base_path, database_url],
        id="document_cleanup",
        name="90-day document cleanup",
        replace_existing=True,
        misfire_grace_time=3600,  # If the server was down at 2 AM, run within 1 hour
    )
    logger.info("Document cleanup scheduler configured (runs daily at 02:00 UTC)")
    return scheduler
