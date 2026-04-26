"""Add token_version to analysts for JWT invalidation on password change

Revision ID: 007
Revises: 006
Create Date: 2026-04-26

When an analyst changes their password, we increment token_version.
All JWTs contain the token_version at the time of login. If they don't match
the current DB value, the token is rejected — effectively logging out all
devices after a password change.
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysts",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("analysts", "token_version")
