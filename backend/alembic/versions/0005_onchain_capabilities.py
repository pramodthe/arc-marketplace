"""add capability pricing and usage records

Revision ID: 0005_onchain_capabilities
Revises: 0004_provider_listing_fields
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_onchain_capabilities"
down_revision = "0004_provider_listing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tools", sa.Column("endpoint_url", sa.String(length=500), nullable=False, server_default=""))
    op.add_column("tools", sa.Column("http_method", sa.String(length=12), nullable=False, server_default="POST"))
    op.add_column("tools", sa.Column("category", sa.String(length=80), nullable=False, server_default="General"))
    op.add_column("tools", sa.Column("runtime_price_usdc", sa.Float(), nullable=False, server_default="0"))
    op.add_column("tools", sa.Column("runtime_unit", sa.String(length=32), nullable=False, server_default="none"))
    op.add_column("tools", sa.Column("capability_type", sa.String(length=32), nullable=False, server_default="tool"))
    op.add_column("tools", sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("skill_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skills_id", "skills", ["id"])
    op.create_index("ix_skills_tool_id", "skills", ["tool_id"])
    op.create_index("ix_skills_skill_key", "skills", ["skill_key"])

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("buyer_invocation_id", sa.Integer(), sa.ForeignKey("buyer_invocations.id"), nullable=True),
        sa.Column("payment_event_id", sa.Integer(), sa.ForeignKey("payment_events.id"), nullable=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=True),
        sa.Column("component_type", sa.String(length=32), nullable=False),
        sa.Column("component_key", sa.String(length=64), nullable=False),
        sa.Column("component_name", sa.String(length=120), nullable=False),
        sa.Column("units", sa.Float(), nullable=False, server_default="1"),
        sa.Column("unit_price_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("subtotal_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_records_id", "usage_records", ["id"])
    op.create_index("ix_usage_records_buyer_invocation_id", "usage_records", ["buyer_invocation_id"])
    op.create_index("ix_usage_records_payment_event_id", "usage_records", ["payment_event_id"])
    op.create_index("ix_usage_records_tool_id", "usage_records", ["tool_id"])
    op.create_index("ix_usage_records_skill_id", "usage_records", ["skill_id"])
    op.create_index("ix_usage_records_created_at", "usage_records", ["created_at"])


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("skills")
    op.drop_column("tools", "config")
    op.drop_column("tools", "capability_type")
    op.drop_column("tools", "runtime_unit")
    op.drop_column("tools", "runtime_price_usdc")
    op.drop_column("tools", "category")
    op.drop_column("tools", "http_method")
    op.drop_column("tools", "endpoint_url")
