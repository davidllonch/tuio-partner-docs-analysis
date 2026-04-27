"""Add indexes on uploaded_at and created_at for cleanup query performance

Revision ID: 008
Revises: 007
Create Date: 2026-04-27

The nightly cleanup job queries:
  - Document.uploaded_at < cutoff
  - Submission.created_at < cutoff

Without indexes these do full table scans. As the tables grow this becomes
progressively slower and could cause the cleanup job to run into its misfire
grace time.
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_uploaded_at",
        "documents",
        ["uploaded_at"],
    )
    op.create_index(
        "ix_submissions_created_at",
        "submissions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_created_at", table_name="submissions")
    op.drop_index("ix_documents_uploaded_at", table_name="documents")
