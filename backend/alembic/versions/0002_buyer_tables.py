"""add buyer tables

Revision ID: 0002_buyer_tables
Revises: 0001_marketplace_schema
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_buyer_tables"
down_revision = "0001_marketplace_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buyers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("organization", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("wallet_address", sa.String(length=66), nullable=False),
        sa.Column("validator_wallet_address", sa.String(length=66), nullable=False),
        sa.Column("owner_wallet_id", sa.String(length=128), nullable=True),
        sa.Column("validator_wallet_id", sa.String(length=128), nullable=True),
        sa.Column("arc_agent_id", sa.String(length=128), nullable=True),
        sa.Column("identity_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_buyers_id", "buyers", ["id"])
    op.create_index("ix_buyers_wallet_address", "buyers", ["wallet_address"])
    op.create_index("ix_buyers_arc_agent_id", "buyers", ["arc_agent_id"])

    op.create_table(
        "buyer_invocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("buyers.id"), nullable=False),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("payment_event_id", sa.Integer(), sa.ForeignKey("payment_events.id"), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("output_preview", sa.Text(), nullable=False),
        sa.Column("amount_usdc", sa.Float(), nullable=False),
        sa.Column("transaction_ref", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_buyer_invocations_id", "buyer_invocations", ["id"])
    op.create_index("ix_buyer_invocations_buyer_id", "buyer_invocations", ["buyer_id"])
    op.create_index("ix_buyer_invocations_seller_id", "buyer_invocations", ["seller_id"])
    op.create_index("ix_buyer_invocations_agent_id", "buyer_invocations", ["agent_id"])
    op.create_index("ix_buyer_invocations_tool_id", "buyer_invocations", ["tool_id"])
    op.create_index("ix_buyer_invocations_created_at", "buyer_invocations", ["created_at"])
    op.create_index("ix_buyer_invocations_transaction_ref", "buyer_invocations", ["transaction_ref"])


def downgrade() -> None:
    op.drop_table("buyer_invocations")
    op.drop_table("buyers")
