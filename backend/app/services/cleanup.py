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
        database_url:        PostgreSQL connection string (sync format for this job)
    """
    # Convert async URL to sync for use in this background job
    # asyncpg URL → psycopg2 URL  (replace the driver prefix only)
    sync_db_url = database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    ).replace(
        "postgresql+asyncpg:", "postgresql:"
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    logger.info(
        "Running document cleanup — removing documents uploaded before %s",
        cutoff.isoformat(),
    )

    try:
        from sqlalchemy import create_engine, select, delete, text
        from sqlalchemy.orm import Session

        # Use a synchronous engine here because APScheduler's AsyncIOScheduler
        # runs the job in the event loop but the job itself is async —
        # we use asyncpg-compatible async engine instead.
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

        # Re-use the async URL directly
        async_url = database_url
        engine = create_async_engine(async_url, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        from app.models.submission import Document

        async with async_session() as session:
            # Find all documents older than the cutoff date
            result = await session.execute(
                select(Document).where(Document.uploaded_at < cutoff)
            )
            old_documents = result.scalars().all()

            if not old_documents:
                logger.info("Cleanup: no documents found older than 90 days")
                await engine.dispose()
                return

            deleted_count = 0
            error_count = 0

            for doc in old_documents:
                # Delete the physical file from disk first
                try:
                    if os.path.exists(doc.file_path):
                        os.remove(doc.file_path)
                        logger.debug("Deleted file: %s", doc.file_path)

                    # If the parent directory (submission folder) is now empty, remove it
                    parent_dir = os.path.dirname(doc.file_path)
                    if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                        shutil.rmtree(parent_dir, ignore_errors=True)
                        logger.debug("Removed empty directory: %s", parent_dir)

                except OSError as exc:
                    logger.warning(
                        "Could not delete file %s: %s", doc.file_path, exc
                    )
                    error_count += 1
                    continue

                # Delete the database record
                await session.delete(doc)
                deleted_count += 1

            await session.commit()
            logger.info(
                "Cleanup complete: %d documents deleted, %d errors",
                deleted_count,
                error_count,
            )

        await engine.dispose()

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
