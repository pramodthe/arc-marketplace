"""Repository helpers for multi-seller marketplace persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from agents_market.marketplace.models import (
    Agent,
    Buyer,
    BuyerInvocation,
    BridgeTransfer,
    GatewayAccount,
    PaymentEvent,
    ReputationEvent,
    Seller,
    Tool,
    ValidationRequest,
)


DEFAULT_TOOLS: list[dict[str, Any]] = [
    {
        "tool_key": "summarize",
        "name": "Summarize",
        "slug": "summarize",
        "description": "Short summary of the prompt",
        "price_usdc": 0.01,
    },
    {
        "tool_key": "analyze",
        "name": "Analyze",
        "slug": "analyze",
        "description": "Deeper analysis and trade-offs",
        "price_usdc": 0.03,
    },
    {
        "tool_key": "plan",
        "name": "Plan",
        "slug": "plan",
        "description": "Structured plan output",
        "price_usdc": 0.05,
    },
    {
        "tool_key": "response",
        "name": "Response",
        "slug": "response",
        "description": "Generic response generation",
        "price_usdc": 0.01,
    },
]


def list_sellers(db: Session) -> list[Seller]:
    return list(db.scalars(select(Seller).order_by(desc(Seller.created_at))))


def get_seller(db: Session, seller_id: int) -> Seller | None:
    return db.get(Seller, seller_id)


def create_seller(
    db: Session,
    *,
    name: str,
    description: str,
    owner_wallet_address: str,
    validator_wallet_address: str,
    wallet_set_id: str | None = None,
    owner_wallet_id: str | None = None,
    validator_wallet_id: str | None = None,
) -> Seller:
    seller = Seller(
        name=name,
        description=description,
        owner_wallet_address=owner_wallet_address,
        validator_wallet_address=validator_wallet_address,
        wallet_set_id=wallet_set_id,
        owner_wallet_id=owner_wallet_id,
        validator_wallet_id=validator_wallet_id,
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


def list_buyers(db: Session) -> list[Buyer]:
    return list(db.scalars(select(Buyer).order_by(desc(Buyer.created_at))))


def get_buyer(db: Session, buyer_id: int) -> Buyer | None:
    return db.get(Buyer, buyer_id)


def create_buyer(
    db: Session,
    *,
    name: str,
    organization: str,
    description: str,
    wallet_address: str,
    validator_wallet_address: str = "",
) -> Buyer:
    buyer = Buyer(
        name=name,
        organization=organization,
        description=description,
        wallet_address=wallet_address,
        validator_wallet_address=validator_wallet_address,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


def list_agents(db: Session, seller_id: int | None = None) -> list[Agent]:
    query = select(Agent).order_by(desc(Agent.created_at))
    if seller_id is not None:
        query = query.where(Agent.seller_id == seller_id)
    return list(db.scalars(query))


def get_agent(db: Session, agent_id: int) -> Agent | None:
    return db.get(Agent, agent_id)


def create_agent(
    db: Session,
    *,
    seller_id: int,
    name: str,
    description: str,
    metadata_uri: str,
    icon_data_url: str,
    base_price_usdc: float | None = None,
) -> Agent:
    agent = Agent(
        seller_id=seller_id,
        name=name,
        description=description,
        metadata_uri=metadata_uri,
        icon_data_url=icon_data_url,
        status="created",
    )
    db.add(agent)
    db.flush()

    normalized_base_price = None
    if base_price_usdc is not None:
        normalized_base_price = max(float(base_price_usdc), 0.000001)

    for default_tool in DEFAULT_TOOLS:
        tool_price = (
            normalized_base_price
            if normalized_base_price is not None
            else float(default_tool["price_usdc"])
        )
        db.add(
            Tool(
                agent_id=agent.id,
                tool_key=default_tool["tool_key"],
                name=default_tool["name"],
                slug=default_tool["slug"],
                description=default_tool["description"],
                price_usdc=tool_price,
            )
        )
    db.commit()
    db.refresh(agent)
    return agent


def list_tools_for_marketplace(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Tool, Agent, Seller)
        .join(Agent, Tool.agent_id == Agent.id)
        .join(Seller, Agent.seller_id == Seller.id)
        .where(Tool.enabled.is_(True), Seller.status == "active")
        .order_by(desc(Tool.updated_at))
    ).all()

    result: list[dict[str, Any]] = []
    for tool, agent, seller in rows:
        result.append(
            {
                "toolId": tool.id,
                "toolKey": tool.tool_key,
                "slug": tool.slug,
                "name": tool.name,
                "description": tool.description,
                "priceUSDC": tool.price_usdc,
                "seller": {"id": seller.id, "name": seller.name, "walletAddress": seller.owner_wallet_address},
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "arcAgentId": agent.arc_agent_id,
                    "iconDataUrl": agent.icon_data_url,
                },
            }
        )
    return result


def get_tool(db: Session, tool_id: int) -> Tool | None:
    return db.get(Tool, tool_id)


def get_tool_for_agent(db: Session, *, seller_id: int, agent_id: int, tool_id: int) -> Tool | None:
    stmt = (
        select(Tool)
        .join(Agent, Tool.agent_id == Agent.id)
        .where(
            Tool.id == tool_id,
            Tool.agent_id == agent_id,
            Agent.seller_id == seller_id,
            Tool.enabled.is_(True),
        )
    )
    return db.scalar(stmt)


def update_agent_tool_prices(
    db: Session,
    *,
    seller_id: int,
    agent_id: int,
    base_price_usdc: float,
) -> int:
    agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.seller_id == seller_id))
    if agent is None:
        return 0

    tools = list(db.scalars(select(Tool).where(Tool.agent_id == agent_id)))
    if not tools:
        return 0

    normalized = max(float(base_price_usdc), 0.000001)
    for tool in tools:
        tool.price_usdc = normalized
    db.commit()
    return len(tools)


def create_payment_event(
    db: Session,
    *,
    seller_id: int | None,
    agent_id: int | None,
    tool_id: int | None,
    event_type: str,
    status: str,
    buyer_address: str | None,
    transaction_ref: str | None,
    amount_usdc: float,
    details: dict[str, Any],
) -> PaymentEvent:
    event = PaymentEvent(
        seller_id=seller_id,
        agent_id=agent_id,
        tool_id=tool_id,
        event_type=event_type,
        status=status,
        buyer_address=buyer_address,
        transaction_ref=transaction_ref,
        amount_usdc=amount_usdc,
        details=details,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_payment_events(db: Session, *, limit: int = 200) -> list[PaymentEvent]:
    return list(db.scalars(select(PaymentEvent).order_by(desc(PaymentEvent.created_at)).limit(limit)))


def create_reputation_event(
    db: Session,
    *,
    agent_id: int,
    validator_wallet_address: str,
    score: int,
    tag: str,
    feedback_hash: str,
    tx_hash: str | None,
) -> ReputationEvent:
    record = ReputationEvent(
        agent_id=agent_id,
        validator_wallet_address=validator_wallet_address,
        score=score,
        tag=tag,
        feedback_hash=feedback_hash,
        tx_hash=tx_hash,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_validation_request(
    db: Session,
    *,
    agent_id: int,
    validator_wallet_address: str,
    request_hash: str,
    request_uri: str,
    request_tx_hash: str | None,
) -> ValidationRequest:
    row = ValidationRequest(
        agent_id=agent_id,
        validator_wallet_address=validator_wallet_address,
        request_hash=request_hash,
        request_uri=request_uri,
        request_tx_hash=request_tx_hash,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_validation_request(db: Session, request_hash: str) -> ValidationRequest | None:
    return db.scalar(select(ValidationRequest).where(ValidationRequest.request_hash == request_hash))


def set_validation_response(
    db: Session,
    *,
    request_hash: str,
    response_code: int,
    response_tag: str,
    response_tx_hash: str | None,
) -> ValidationRequest | None:
    row = get_validation_request(db, request_hash)
    if row is None:
        return None
    row.response_code = response_code
    row.response_tag = response_tag
    row.response_tx_hash = response_tx_hash
    db.commit()
    db.refresh(row)
    return row


def upsert_gateway_account(
    db: Session,
    *,
    seller_id: int,
    chain: str,
    wallet_address: str,
    wallet_balance_usdc: float,
    gateway_available_usdc: float,
) -> GatewayAccount:
    existing = db.scalar(select(GatewayAccount).where(GatewayAccount.seller_id == seller_id))
    if existing is None:
        existing = GatewayAccount(
            seller_id=seller_id,
            chain=chain,
            wallet_address=wallet_address,
            wallet_balance_usdc=wallet_balance_usdc,
            gateway_available_usdc=gateway_available_usdc,
        )
        db.add(existing)
    else:
        existing.chain = chain
        existing.wallet_address = wallet_address
        existing.wallet_balance_usdc = wallet_balance_usdc
        existing.gateway_available_usdc = gateway_available_usdc
    db.commit()
    db.refresh(existing)
    return existing


def create_bridge_transfer(
    db: Session,
    *,
    seller_id: int,
    source_chain: str,
    destination_chain: str,
    amount_usdc: float,
    status: str,
    transfer_ref: str,
    metadata: dict[str, Any],
) -> BridgeTransfer:
    row = BridgeTransfer(
        seller_id=seller_id,
        source_chain=source_chain,
        destination_chain=destination_chain,
        amount_usdc=amount_usdc,
        status=status,
        transfer_ref=transfer_ref,
        transfer_metadata=metadata,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_buyer_invocation(
    db: Session,
    *,
    buyer_id: int,
    seller_id: int,
    agent_id: int,
    tool_id: int,
    payment_event_id: int | None,
    prompt: str,
    output_preview: str,
    amount_usdc: float,
    transaction_ref: str | None,
    status: str = "completed",
) -> BuyerInvocation:
    row = BuyerInvocation(
        buyer_id=buyer_id,
        seller_id=seller_id,
        agent_id=agent_id,
        tool_id=tool_id,
        payment_event_id=payment_event_id,
        prompt=prompt,
        output_preview=output_preview,
        amount_usdc=amount_usdc,
        transaction_ref=transaction_ref,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_buyer_invocations(db: Session, buyer_id: int, *, limit: int = 50) -> list[BuyerInvocation]:
    return list(
        db.scalars(
            select(BuyerInvocation)
            .where(BuyerInvocation.buyer_id == buyer_id)
            .order_by(desc(BuyerInvocation.created_at))
            .limit(limit)
        )
    )


def payment_summary(db: Session) -> dict[str, Any]:
    total = db.scalar(select(func.count(PaymentEvent.id))) or 0
    paid = db.scalar(select(func.count(PaymentEvent.id)).where(PaymentEvent.status == "paid")) or 0
    payment_required = (
        db.scalar(select(func.count(PaymentEvent.id)).where(PaymentEvent.status == "payment_required")) or 0
    )
    total_amount = db.scalar(
        select(func.coalesce(func.sum(PaymentEvent.amount_usdc), 0)).where(PaymentEvent.status == "paid")
    ) or 0
    unique_buyers = db.scalar(
        select(func.count(func.distinct(PaymentEvent.buyer_address))).where(PaymentEvent.buyer_address.is_not(None))
    ) or 0
    return {
        "total": int(total),
        "paid": int(paid),
        "paymentRequired": int(payment_required),
        "totalPaidAmountUSDC": f"{float(total_amount):.6f}",
        "uniqueBuyers": int(unique_buyers),
    }
