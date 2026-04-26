import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_audit(
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
