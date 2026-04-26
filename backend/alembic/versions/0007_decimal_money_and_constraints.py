"""harden money columns and uniqueness/index constraints

Revision ID: 0007_decimal_money_and_constraints
Revises: 0006_agent_offering_protocol
Create Date: 2026-04-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_decimal_money_and_constraints"
down_revision = "0006_agent_offering_protocol"
branch_labels = None
depends_on = None


def _to_numeric(table: str, column: str) -> None:
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(column, type_=sa.Numeric(18, 6), existing_nullable=False)


def upgrade() -> None:
    _to_numeric("tools", "price_usdc")
    _to_numeric("tools", "runtime_price_usdc")
    _to_numeric("skills", "price_usdc")
    _to_numeric("payment_events", "amount_usdc")
    _to_numeric("gateway_accounts", "wallet_balance_usdc")
    _to_numeric("gateway_accounts", "gateway_available_usdc")
    _to_numeric("bridge_transfers", "amount_usdc")
    _to_numeric("buyer_invocations", "amount_usdc")
    _to_numeric("usage_records", "units")
    _to_numeric("usage_records", "unit_price_usdc")
    _to_numeric("usage_records", "subtotal_usdc")

    # Normalize duplicates before applying strict uniqueness constraints.
    op.execute(
        sa.text(
            """
            UPDATE sellers
            SET owner_wallet_address = COALESCE(NULLIF(TRIM(owner_wallet_address), ''), 'seller-wallet-' || id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, owner_wallet_address,
                       ROW_NUMBER() OVER (PARTITION BY owner_wallet_address ORDER BY id) AS rn
                FROM sellers
            )
            UPDATE sellers
            SET owner_wallet_address = owner_wallet_address || '-' || id
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE buyers
            SET wallet_address = COALESCE(NULLIF(TRIM(wallet_address), ''), 'buyer-wallet-' || id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, wallet_address,
                       ROW_NUMBER() OVER (PARTITION BY wallet_address ORDER BY id) AS rn
                FROM buyers
            )
            UPDATE buyers
            SET wallet_address = wallet_address || '-' || id
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, tool_id, skill_key,
                       ROW_NUMBER() OVER (PARTITION BY tool_id, skill_key ORDER BY id) AS rn
                FROM skills
            )
            UPDATE skills
            SET skill_key = skill_key || '-' || id
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )

    with op.batch_alter_table("sellers") as batch_op:
        batch_op.create_unique_constraint("uq_sellers_owner_wallet_address", ["owner_wallet_address"])
    with op.batch_alter_table("buyers") as batch_op:
        batch_op.create_unique_constraint("uq_buyers_wallet_address", ["wallet_address"])
    with op.batch_alter_table("skills") as batch_op:
        batch_op.create_unique_constraint("uq_skills_tool_id_skill_key", ["tool_id", "skill_key"])

    op.create_index("ix_agents_status_updated_at", "agents", ["status", "updated_at"], unique=False)
    op.create_index("ix_tools_enabled_price_updated_at", "tools", ["enabled", "price_usdc", "updated_at"], unique=False)
    op.create_index("ix_payment_events_status_created_at", "payment_events", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_events_status_created_at", table_name="payment_events")
    op.drop_index("ix_tools_enabled_price_updated_at", table_name="tools")
    op.drop_index("ix_agents_status_updated_at", table_name="agents")

    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_constraint("uq_skills_tool_id_skill_key", type_="unique")
    with op.batch_alter_table("buyers") as batch_op:
        batch_op.drop_constraint("uq_buyers_wallet_address", type_="unique")
    with op.batch_alter_table("sellers") as batch_op:
        batch_op.drop_constraint("uq_sellers_owner_wallet_address", type_="unique")

    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.alter_column("subtotal_usdc", type_=sa.Float(), existing_nullable=False)
        batch_op.alter_column("unit_price_usdc", type_=sa.Float(), existing_nullable=False)
        batch_op.alter_column("units", type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("buyer_invocations") as batch_op:
        batch_op.alter_column("amount_usdc", type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("bridge_transfers") as batch_op:
        batch_op.alter_column("amount_usdc", type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("gateway_accounts") as batch_op:
        batch_op.alter_column("gateway_available_usdc", type_=sa.Float(), existing_nullable=False)
        batch_op.alter_column("wallet_balance_usdc", type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("payment_events") as batch_op:
        batch_op.alter_column("amount_usdc", type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("skills") as batch_op:
        batch_op.alter_column("price_usdc", type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("tools") as batch_op:
        batch_op.alter_column("runtime_price_usdc", type_=sa.Float(), existing_nullable=False)
        batch_op.alter_column("price_usdc", type_=sa.Float(), existing_nullable=False)
