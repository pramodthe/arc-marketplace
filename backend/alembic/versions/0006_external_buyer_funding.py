"""add external buyer funding attempts

Revision ID: 0006_external_buyer_funding
Revises: 0005_onchain_capabilities
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_external_buyer_funding"
down_revision = "0005_onchain_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_funding_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("buyers.id"), nullable=False),
        sa.Column("source_chain", sa.String(length=64), nullable=False),
        sa.Column("destination_chain", sa.String(length=64), nullable=False, server_default="Arc_Testnet"),
        sa.Column("amount_usdc", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="queued"),
        sa.Column("transfer_ref", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("bridge_result", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("tx_hashes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("explorer_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_external_funding_attempts_id", "external_funding_attempts", ["id"])
    op.create_index("ix_external_funding_attempts_buyer_id", "external_funding_attempts", ["buyer_id"])
    op.create_index("ix_external_funding_attempts_transfer_ref", "external_funding_attempts", ["transfer_ref"])
    op.create_index("ix_external_funding_attempts_created_at", "external_funding_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_table("external_funding_attempts")
