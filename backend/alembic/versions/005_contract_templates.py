"""add contract_templates table and contract_data column

Revision ID: 005
Revises: 004
Create Date: 2026-04-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(5), nullable=False, server_default="PJ"),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_analyst_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by_analyst_id"], ["analysts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_type", "entity_type", name="uq_contract_templates_provider_entity"),
    )
    op.add_column("submissions", sa.Column("contract_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "contract_data")
    op.drop_table("contract_templates")
