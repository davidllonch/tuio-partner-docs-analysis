"""Initial migration — create all tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

This migration creates all five tables that the KYC/KYB application needs:
- submissions: partner document submission requests
- documents: individual files attached to a submission
- analysts: internal team members who review submissions
- analyses: history of AI analysis runs per submission
- audit_log: track what analysts did and when
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── analysts table ────────────────────────────────────────────────────────
    # Created first because submissions/analyses reference it via foreign keys.
    op.create_table(
        "analysts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_analysts_email", "analysts", ["email"], unique=True)

    # ── submissions table ─────────────────────────────────────────────────────
    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("ai_model_used", sa.String(100), nullable=True),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_submissions_created_at", "submissions", ["created_at"], unique=False
    )
    op.create_index(
        "ix_submissions_status", "submissions", ["status"], unique=False
    )

    # ── documents table ───────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("user_label", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_submission_id", "documents", ["submission_id"], unique=False
    )
    op.create_index(
        "ix_documents_uploaded_at", "documents", ["uploaded_at"], unique=False
    )

    # ── analyses table ────────────────────────────────────────────────────────
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("ai_model_used", sa.String(100), nullable=True),
        sa.Column("triggered_by", sa.String(20), nullable=False),
        sa.Column("analyst_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["analyst_id"], ["analysts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analyses_submission_id", "analyses", ["submission_id"], unique=False
    )

    # ── audit_log table ───────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analyst_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["analyst_id"], ["analysts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_log_analyst_id", "audit_log", ["analyst_id"], unique=False
    )
    op.create_index(
        "ix_audit_log_timestamp", "audit_log", ["timestamp"], unique=False
    )


def downgrade() -> None:
    """
    Drop all tables in reverse dependency order.
    WARNING: This will permanently delete ALL data in the database.
    Only use this in development/testing — never in production.
    """
    op.drop_table("audit_log")
    op.drop_table("analyses")
    op.drop_table("documents")
    op.drop_table("submissions")
    op.drop_table("analysts")
