"""add agent icon data url

Revision ID: 0003_agent_icon_data_url
Revises: 0002_buyer_tables
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_agent_icon_data_url"
down_revision = "0002_buyer_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("icon_data_url", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("agents", "icon_data_url")
