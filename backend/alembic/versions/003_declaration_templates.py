"""Add declaration_templates table and not_applicable_slots to submissions

Revision ID: 003
Revises: 002
Create Date: 2026-04-15 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── declaration_templates table ────────────────────────────────────────────
    op.create_table(
        "declaration_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_analyst_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["uploaded_by_analyst_id"], ["analysts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_type", name="uq_declaration_templates_provider_type"),
    )
    op.create_index(
        "ix_declaration_templates_provider_type",
        "declaration_templates",
        ["provider_type"],
        unique=True,
    )

    # ── Add not_applicable_slots to submissions ────────────────────────────────
    op.add_column(
        "submissions",
        sa.Column("not_applicable_slots", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("submissions", "not_applicable_slots")
    op.drop_index("ix_declaration_templates_provider_type", table_name="declaration_templates")
    op.drop_table("declaration_templates")
