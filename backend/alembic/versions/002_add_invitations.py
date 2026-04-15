"""Add invitations table and invitation_id to submissions

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── invitations table ──────────────────────────────────────────────────────
    # submission_id column is added here but its FK constraint is added later
    # (after invitation_id is added to submissions) to avoid circular dependency.
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("created_by_analyst_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_name", sa.String(255), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(5), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_analyst_id"], ["analysts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_invitations_token"),
    )
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)
    op.create_index("ix_invitations_status", "invitations", ["status"], unique=False)
    op.create_index(
        "ix_invitations_created_by_analyst_id",
        "invitations",
        ["created_by_analyst_id"],
        unique=False,
    )

    # ── Add invitation_id to submissions ───────────────────────────────────────
    op.add_column(
        "submissions",
        sa.Column("invitation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_submissions_invitation_id",
        "submissions",
        "invitations",
        ["invitation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── Add FK from invitations.submission_id → submissions ────────────────────
    # Added after submissions.invitation_id exists (both tables are fully set up).
    op.create_foreign_key(
        "fk_invitations_submission_id",
        "invitations",
        "submissions",
        ["submission_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_invitations_submission_id", "invitations", type_="foreignkey")
    op.drop_constraint("fk_submissions_invitation_id", "submissions", type_="foreignkey")
    op.drop_column("submissions", "invitation_id")
    op.drop_index("ix_invitations_created_by_analyst_id", table_name="invitations")
    op.drop_index("ix_invitations_status", table_name="invitations")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_table("invitations")
