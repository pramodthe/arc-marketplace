"""Repository helpers for multi-seller marketplace persistence."""

from __future__ import annotations

import re
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
    Skill,
    Tool,
    UsageRecord,
    ValidationRequest,
)


DEFAULT_TOOL_KEY = "invoke"
DEFAULT_RUNTIME_UNIT = "none"


def _slugify(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def list_sellers(db: Session) -> list[Seller]:
    return list(db.scalars(select(Seller).order_by(desc(Seller.created_at))))


def get_seller(db: Session, seller_id: int) -> Seller | None:
    return db.get(Seller, seller_id)


def update_seller_status(db: Session, *, seller_id: int, status: str) -> Seller | None:
    seller = get_seller(db, seller_id)
    if seller is None:
        return None
    seller.status = status
    db.commit()
    db.refresh(seller)
    return seller


def create_seller(
    db: Session,
    *,
    name: str,
    description: str,
    owner_wallet_address: str = "",
    validator_wallet_address: str = "",
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


def delete_agent_for_seller(db: Session, *, seller_id: int, agent_id: int) -> dict[str, Any] | None:
    agent = db.scalar(select(Agent).where(Agent.id == agent_id, Agent.seller_id == seller_id))
    if agent is None:
        return None
    tool_ids = [tool.id for tool in agent.tools]

    payment_where = PaymentEvent.agent_id == agent.id
    invocation_where = BuyerInvocation.agent_id == agent.id
    if tool_ids:
        payment_where = payment_where | PaymentEvent.tool_id.in_(tool_ids)
        invocation_where = invocation_where | BuyerInvocation.tool_id.in_(tool_ids)

    linked_payment_events = db.scalar(select(func.count(PaymentEvent.id)).where(payment_where)) or 0
    linked_invocations = db.scalar(select(func.count(BuyerInvocation.id)).where(invocation_where)) or 0
    linked_reputation = db.scalar(select(func.count(ReputationEvent.id)).where(ReputationEvent.agent_id == agent.id)) or 0
    linked_validation = (
        db.scalar(select(func.count(ValidationRequest.id)).where(ValidationRequest.agent_id == agent.id)) or 0
    )
    linked_usage = db.scalar(select(func.count(UsageRecord.id)).where(UsageRecord.tool_id.in_(tool_ids))) if tool_ids else 0
    linked_usage = linked_usage or 0

    has_linked_records = any(
        count > 0
        for count in (
            linked_payment_events,
            linked_invocations,
            linked_reputation,
            linked_validation,
            linked_usage,
        )
    )

    if has_linked_records:
        # Preserve historical rows that reference this agent/tool set.
        agent.status = "deleted"
        for tool in agent.tools:
            tool.enabled = False
        db.commit()
        db.refresh(agent)
        return {"deleted": True, "deletionMode": "soft", "reason": "linked_records_preserved"}

    db.delete(agent)
    db.commit()
    return {"deleted": True, "deletionMode": "hard"}


def create_agent(
    db: Session,
    *,
    seller_id: int,
    name: str,
    description: str,
    metadata_uri: str,
    icon_data_url: str,
    category: str,
    offering_type: str,
    protocol_type: str,
    endpoint_url: str,
    http_method: str,
    api_docs_url: str,
    price_usdc: float,
    capabilities: list[dict[str, Any]] | None = None,
) -> Agent:
    agent = Agent(
        seller_id=seller_id,
        name=name,
        description=description,
        metadata_uri=metadata_uri,
        icon_data_url=icon_data_url,
        category=category,
        offering_type=offering_type,
        protocol_type=protocol_type,
        endpoint_url=endpoint_url,
        http_method=http_method,
        api_docs_url=api_docs_url,
        health_status="unchecked",
        status="registering",
    )
    db.add(agent)
    db.flush()

    capability_rows = capabilities or [
        {
            "toolKey": DEFAULT_TOOL_KEY,
            "name": name,
            "description": description,
            "priceUSDC": float(price_usdc),
            "endpointUrl": endpoint_url,
            "httpMethod": http_method,
            "category": category,
            "runtimePriceUSDC": 0,
            "runtimeUnit": DEFAULT_RUNTIME_UNIT,
            "capabilityType": "tool",
            "skills": [],
        }
    ]

    for index, capability in enumerate(capability_rows):
        tool = Tool(
            agent_id=agent.id,
            tool_key=str(capability.get("toolKey") or capability.get("name") or f"tool-{index + 1}"),
            name=str(capability.get("name") or name),
            slug=_slugify(str(capability.get("slug") or capability.get("name") or f"tool-{index + 1}"), fallback=f"tool-{index + 1}"),
            description=str(capability.get("description") or description),
            price_usdc=float(capability.get("priceUSDC", price_usdc)),
            endpoint_url=str(capability.get("endpointUrl") or endpoint_url),
            http_method=str(capability.get("httpMethod") or http_method),
            category=str(capability.get("category") or category),
            runtime_price_usdc=float(capability.get("runtimePriceUSDC", 0)),
            runtime_unit=str(capability.get("runtimeUnit") or DEFAULT_RUNTIME_UNIT),
            capability_type=str(capability.get("capabilityType") or "tool"),
            config=capability.get("config") or {},
        )
        db.add(tool)
        db.flush()
        for skill in capability.get("skills", []) or []:
            db.add(
                Skill(
                    tool_id=tool.id,
                    skill_key=str(skill.get("skillKey") or skill.get("name") or f"skill-{tool.id}"),
                    name=str(skill.get("name") or "Unnamed Skill"),
                    description=str(skill.get("description") or ""),
                    price_usdc=float(skill.get("priceUSDC", 0)),
                    enabled=bool(skill.get("enabled", True)),
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
        .where(
            Tool.enabled.is_(True),
            Tool.price_usdc <= 0.01,
            Agent.status == "registered",
            Seller.status == "active",
        )
        .order_by(desc(Tool.updated_at))
    ).all()

    result: list[dict[str, Any]] = []
    for tool, agent, seller in rows:
        starting_price = float(tool.price_usdc) + float(tool.runtime_price_usdc)
        result.append(
            {
                "toolId": tool.id,
                "toolKey": tool.tool_key,
                "slug": tool.slug,
                "name": tool.name,
                "description": tool.description,
                "priceUSDC": starting_price,
                "runtimePriceUSDC": tool.runtime_price_usdc,
                "runtimeUnit": tool.runtime_unit,
                "capabilityType": tool.capability_type,
                "category": tool.category,
                "offeringType": agent.offering_type,
                "protocolType": agent.protocol_type,
                "endpointUrl": tool.endpoint_url or agent.endpoint_url,
                "httpMethod": tool.http_method or agent.http_method,
                "skills": [],
                "invokeUrl": f"/sellers/{seller.id}/agents/{agent.id}/tools/{tool.id}/invoke",
                "seller": {"id": seller.id, "name": seller.name, "walletAddress": seller.owner_wallet_address},
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "description": agent.description,
                    "metadataUri": agent.metadata_uri,
                    "arcAgentId": agent.arc_agent_id,
                    "identityTxHash": agent.identity_tx_hash,
                    "iconDataUrl": agent.icon_data_url,
                    "category": agent.category,
                    "endpointUrl": agent.endpoint_url,
                    "httpMethod": agent.http_method,
                    "apiDocsUrl": agent.api_docs_url,
                    "healthStatus": agent.health_status,
                    "lastHealthCheckAt": agent.last_health_check_at.isoformat()
                    if agent.last_health_check_at is not None
                    else None,
                    "status": agent.status,
                },
            }
        )
    return result


def list_agents_for_marketplace(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Agent, Seller)
        .join(Seller, Agent.seller_id == Seller.id)
        .where(Agent.status == "registered", Seller.status == "active")
        .order_by(desc(Agent.updated_at))
    ).all()

    cards: list[dict[str, Any]] = []
    for agent, seller in rows:
        tools = list(
            db.scalars(
                select(Tool).where(Tool.agent_id == agent.id, Tool.enabled.is_(True), Tool.price_usdc <= 0.01)
            )
        )
        prices = [float(tool.price_usdc) + float(tool.runtime_price_usdc) for tool in tools]
        min_price = min(prices) if prices else 0
        tool_payloads = [
            {
                "toolId": tool.id,
                "toolKey": tool.tool_key,
                "slug": tool.slug,
                "name": tool.name,
                "description": tool.description,
                "priceUSDC": float(tool.price_usdc) + float(tool.runtime_price_usdc),
                "runtimePriceUSDC": tool.runtime_price_usdc,
                "runtimeUnit": tool.runtime_unit,
                "capabilityType": tool.capability_type,
                "category": tool.category,
                "endpointUrl": tool.endpoint_url or agent.endpoint_url,
                "httpMethod": tool.http_method or agent.http_method,
                "skills": [],
                "invokePath": f"/sellers/{seller.id}/agents/{agent.id}/tools/{tool.id}/invoke",
            }
            for tool in tools
        ]
        endpoint_host = ""
        for tool in tools:
            endpoint = tool.endpoint_url or agent.endpoint_url
            if endpoint:
                endpoint_host = endpoint.split("/")[2] if "://" in endpoint else endpoint
                break
        cards.append(
            {
                "id": f"{seller.id}:{agent.id}",
                "sellerId": seller.id,
                "agentId": agent.id,
                "name": agent.name,
                "description": agent.description,
                "category": agent.category,
                "offeringType": agent.offering_type,
                "protocolType": agent.protocol_type,
                "endpointUrl": agent.endpoint_url,
                "endpointHost": endpoint_host,
                "httpMethod": agent.http_method,
                "apiDocsUrl": agent.api_docs_url,
                "metadataUri": agent.metadata_uri,
                "iconDataUrl": agent.icon_data_url,
                "status": agent.status,
                "healthStatus": agent.health_status,
                "lastHealthCheckAt": agent.last_health_check_at.isoformat()
                if agent.last_health_check_at is not None
                else None,
                "arc": {
                    "network": "Arc Testnet",
                    "agentId": agent.arc_agent_id,
                    "identityTxHash": agent.identity_tx_hash,
                    "registered": bool(agent.arc_agent_id and agent.identity_tx_hash),
                },
                "seller": {
                    "id": seller.id,
                    "name": seller.name,
                    "description": seller.description,
                    "walletAddress": seller.owner_wallet_address,
                    "validatorWalletAddress": seller.validator_wallet_address,
                    "status": seller.status,
                },
                "commerce": {
                    "pricingModel": "On-chain metered",
                    "paymentProtocol": "arc-usdc",
                    "network": "arcTestnet",
                    "minPriceUSDC": min_price,
                    "toolCount": len(tools),
                },
                "tools": tool_payloads,
            }
        )
    return cards


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


def list_skills_for_tool(db: Session, tool_id: int) -> list[Skill]:
    return list(db.scalars(select(Skill).where(Skill.tool_id == tool_id, Skill.enabled.is_(True)).order_by(Skill.created_at)))


def update_tool_pricing(
    db: Session,
    *,
    seller_id: int,
    agent_id: int,
    tool_id: int,
    tool_price_usdc: float | None = None,
    runtime_price_usdc: float | None = None,
    skill_prices: list[dict[str, Any]] | None = None,
) -> Tool | None:
    tool = get_tool_for_agent(db, seller_id=seller_id, agent_id=agent_id, tool_id=tool_id)
    if tool is None:
        return None
    if tool_price_usdc is not None:
        tool.price_usdc = min(max(float(tool_price_usdc), 0.000001), 0.01)
    if runtime_price_usdc is not None:
        tool.runtime_price_usdc = min(max(float(runtime_price_usdc), 0), 0.01)
    # Billable skill pricing is disabled for now.
    db.commit()
    db.refresh(tool)
    return tool


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

    normalized = min(max(float(base_price_usdc), 0.000001), 0.01)
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


def create_usage_records(
    db: Session,
    *,
    buyer_invocation_id: int | None,
    payment_event_id: int | None,
    tool_id: int | None,
    usage_components: list[dict[str, Any]],
) -> list[UsageRecord]:
    rows: list[UsageRecord] = []
    for component in usage_components:
        row = UsageRecord(
            buyer_invocation_id=buyer_invocation_id,
            payment_event_id=payment_event_id,
            tool_id=tool_id,
            skill_id=component.get("skillId"),
            component_type=str(component["componentType"]),
            component_key=str(component["componentKey"]),
            component_name=str(component["componentName"]),
            units=float(component["units"]),
            unit_price_usdc=float(component["unitPriceUSDC"]),
            subtotal_usdc=float(component["subtotalUSDC"]),
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


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
