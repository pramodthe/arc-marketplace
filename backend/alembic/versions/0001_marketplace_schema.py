"""initial marketplace schema

Revision ID: 0001_marketplace_schema
Revises:
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_marketplace_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sellers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_wallet_address", sa.String(length=66), nullable=False),
        sa.Column("validator_wallet_address", sa.String(length=66), nullable=False),
        sa.Column("wallet_set_id", sa.String(length=128), nullable=True),
        sa.Column("owner_wallet_id", sa.String(length=128), nullable=True),
        sa.Column("validator_wallet_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sellers_id", "sellers", ["id"])
    op.create_index("ix_sellers_owner_wallet_address", "sellers", ["owner_wallet_address"])

    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_uri", sa.String(length=255), nullable=False),
        sa.Column("arc_agent_id", sa.String(length=128), nullable=True),
        sa.Column("identity_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agents_id", "agents", ["id"])
    op.create_index("ix_agents_seller_id", "agents", ["seller_id"])
    op.create_index("ix_agents_arc_agent_id", "agents", ["arc_agent_id"])

    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("tool_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_usdc", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tools_id", "tools", ["id"])
    op.create_index("ix_tools_agent_id", "tools", ["agent_id"])
    op.create_index("ix_tools_slug", "tools", ["slug"])

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sellers.id"), nullable=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("buyer_address", sa.String(length=66), nullable=True),
        sa.Column("transaction_ref", sa.String(length=128), nullable=True),
        sa.Column("amount_usdc", sa.Float(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_events_id", "payment_events", ["id"])
    op.create_index("ix_payment_events_created_at", "payment_events", ["created_at"])
    op.create_index("ix_payment_events_seller_id", "payment_events", ["seller_id"])
    op.create_index("ix_payment_events_agent_id", "payment_events", ["agent_id"])
    op.create_index("ix_payment_events_tool_id", "payment_events", ["tool_id"])
    op.create_index("ix_payment_events_buyer_address", "payment_events", ["buyer_address"])
    op.create_index("ix_payment_events_transaction_ref", "payment_events", ["transaction_ref"])

    op.create_table(
        "reputation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("validator_wallet_address", sa.String(length=66), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=128), nullable=False),
        sa.Column("feedback_hash", sa.String(length=130), nullable=False),
        sa.Column("tx_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reputation_events_id", "reputation_events", ["id"])
    op.create_index("ix_reputation_events_agent_id", "reputation_events", ["agent_id"])

    op.create_table(
        "validation_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("validator_wallet_address", sa.String(length=66), nullable=False),
        sa.Column("request_hash", sa.String(length=130), nullable=False),
        sa.Column("request_uri", sa.String(length=255), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_tag", sa.String(length=128), nullable=False),
        sa.Column("request_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("response_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_hash"),
    )
    op.create_index("ix_validation_requests_id", "validation_requests", ["id"])
    op.create_index("ix_validation_requests_agent_id", "validation_requests", ["agent_id"])

    op.create_table(
        "gateway_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("chain", sa.String(length=64), nullable=False),
        sa.Column("wallet_address", sa.String(length=66), nullable=False),
        sa.Column("wallet_balance_usdc", sa.Float(), nullable=False),
        sa.Column("gateway_available_usdc", sa.Float(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("seller_id"),
    )
    op.create_index("ix_gateway_accounts_id", "gateway_accounts", ["id"])
    op.create_index("ix_gateway_accounts_seller_id", "gateway_accounts", ["seller_id"])

    op.create_table(
        "bridge_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("source_chain", sa.String(length=64), nullable=False),
        sa.Column("destination_chain", sa.String(length=64), nullable=False),
        sa.Column("amount_usdc", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("transfer_ref", sa.String(length=128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bridge_transfers_id", "bridge_transfers", ["id"])
    op.create_index("ix_bridge_transfers_seller_id", "bridge_transfers", ["seller_id"])


def downgrade() -> None:
    op.drop_table("bridge_transfers")
    op.drop_table("gateway_accounts")
    op.drop_table("validation_requests")
    op.drop_table("reputation_events")
    op.drop_table("payment_events")
    op.drop_table("tools")
    op.drop_table("agents")
    op.drop_table("sellers")
