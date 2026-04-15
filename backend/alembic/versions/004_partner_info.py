"""Add entity_type to declaration_templates and partner_info to submissions

Revision ID: 004
Revises: 003
Create Date: 2026-04-15 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Step 1: Add entity_type column with a default so existing rows get 'PJ' ──
    op.add_column(
        "declaration_templates",
        sa.Column(
            "entity_type",
            sa.String(5),
            nullable=False,
            server_default="PJ",
        ),
    )

    # ── Step 2: Remove old unique constraint and index on provider_type alone ──
    op.drop_index(
        "ix_declaration_templates_provider_type",
        table_name="declaration_templates",
    )
    op.drop_constraint(
        "uq_declaration_templates_provider_type",
        table_name="declaration_templates",
        type_="unique",
    )

    # ── Step 3: Create new composite unique constraint (provider_type, entity_type) ──
    op.create_unique_constraint(
        "uq_declaration_templates_provider_entity",
        "declaration_templates",
        ["provider_type", "entity_type"],
    )

    # ── Step 4: Add partner_info column to submissions ─────────────────────────
    op.add_column(
        "submissions",
        sa.Column("partner_info", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("submissions", "partner_info")

    op.drop_constraint(
        "uq_declaration_templates_provider_entity",
        table_name="declaration_templates",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_declaration_templates_provider_type",
        "declaration_templates",
        ["provider_type"],
    )
    op.create_index(
        "ix_declaration_templates_provider_type",
        "declaration_templates",
        ["provider_type"],
        unique=True,
    )

    op.drop_column("declaration_templates", "entity_type")
