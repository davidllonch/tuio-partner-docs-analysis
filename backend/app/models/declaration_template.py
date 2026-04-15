import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeclarationTemplate(Base):
    __tablename__ = "declaration_templates"
    __table_args__ = (
        UniqueConstraint(
            "provider_type",
            "entity_type",
            name="uq_declaration_templates_provider_entity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(5), nullable=False, default="PJ")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_analyst_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysts.id", ondelete="SET NULL"),
        nullable=True,
    )

    uploaded_by_analyst: Mapped[Optional["Analyst"]] = relationship(  # type: ignore[name-defined]
        "Analyst", foreign_keys=[uploaded_by_analyst_id]
    )
