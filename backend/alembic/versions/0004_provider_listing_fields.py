"""add provider listing fields

Revision ID: 0004_provider_listing_fields
Revises: 0003_agent_icon_data_url
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_provider_listing_fields"
down_revision = "0003_agent_icon_data_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("category", sa.String(length=80), nullable=False, server_default="General"))
    op.add_column("agents", sa.Column("endpoint_url", sa.String(length=500), nullable=False, server_default=""))
    op.add_column("agents", sa.Column("http_method", sa.String(length=12), nullable=False, server_default="POST"))
    op.add_column("agents", sa.Column("api_docs_url", sa.String(length=500), nullable=False, server_default=""))
    op.add_column("agents", sa.Column("health_status", sa.String(length=32), nullable=False, server_default="unknown"))
    op.add_column("agents", sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "last_health_check_at")
    op.drop_column("agents", "health_status")
    op.drop_column("agents", "api_docs_url")
    op.drop_column("agents", "http_method")
    op.drop_column("agents", "endpoint_url")
    op.drop_column("agents", "category")
