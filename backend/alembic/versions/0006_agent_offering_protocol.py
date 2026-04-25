"""add agent offering and protocol type fields

Revision ID: 0006_agent_offering_protocol
Revises: 0005_onchain_capabilities
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_agent_offering_protocol"
down_revision = "0005_onchain_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("offering_type", sa.String(length=32), nullable=False, server_default="agent"),
    )
    op.add_column(
        "agents",
        sa.Column("protocol_type", sa.String(length=32), nullable=False, server_default="http"),
    )


def downgrade() -> None:
    op.drop_column("agents", "protocol_type")
    op.drop_column("agents", "offering_type")
