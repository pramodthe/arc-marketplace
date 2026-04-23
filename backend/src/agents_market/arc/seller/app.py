"""Multi-seller Arc marketplace API with x402 paid tool execution."""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents_market._env import load_backend_env
from agents_market.arc.services.erc8004 import (
    create_validation_request as arc_create_validation_request,
    get_validation_status as arc_get_validation_status,
    register_agent_identity,
    record_reputation as arc_record_reputation,
    submit_validation_response as arc_submit_validation_response,
)
from agents_market.db import Base, engine, get_db
from agents_market.marketplace.models import PaymentEvent, ReputationEvent
from agents_market.marketplace.repository import (
    create_agent,
    create_buyer,
    create_buyer_invocation,
    create_bridge_transfer,
    create_payment_event,
    create_reputation_event,
    create_seller,
    create_validation_request,
    get_agent,
    get_buyer,
    get_seller,
    get_tool_for_agent,
    get_validation_request,
    list_agents,
    list_buyer_invocations,
    list_buyers,
    list_payment_events,
    list_sellers,
    list_tools_for_marketplace,
    payment_summary,
    set_validation_response,
    upsert_gateway_account,
)

load_backend_env()

try:
    from circlekit import GatewayClient, create_gateway_middleware
    from circlekit.x402 import PaymentInfo
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'circlekit'. Install editable circle-titanoboa-sdk (see backend/README.md)."
    ) from exc

from circle.web3 import developer_controlled_wallets, utils


class SellerCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    ownerWalletAddress: str
    validatorWalletAddress: str = ""


class AgentCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    metadataUri: str = ""


class BuyerCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization: str = ""
    description: str = ""
    walletAddress: str
    validatorWalletAddress: str = ""


class InvokeBody(BaseModel):
    prompt: str = "Give me a short Arc ecosystem update."
    buyerId: int | None = None


class DiscoverBody(BaseModel):
    prompt: str
    budgetUSDC: float = Field(gt=0, default=1.0)
    desiredTool: str = "auto"
    maxResults: int = Field(default=5, ge=1, le=20)


class RegisterBody(BaseModel):
    metadataUri: str | None = None


class ReputationBody(BaseModel):
    score: int = 95
    tag: str = "successful_trade"
    feedbackHash: str = ""


class ValidationRequestBody(BaseModel):
    requestUri: str = "ipfs://bafkreiexamplevalidationrequest"
    requestHash: str | None = None
    validatorWalletAddress: str | None = None


class ValidationResponseBody(BaseModel):
    requestHash: str
    responseCode: int = 100
    responseTag: str = "kyc_verified"


class GatewayDepositBody(BaseModel):
    amount: str = "1"


class WalletProvisionBody(BaseModel):
    walletSetName: str | None = None


class BridgeTransferBody(BaseModel):
    sourceChain: str = "arcTestnet"
    destinationChain: str
    amountUSDC: float = Field(gt=0)
    speed: str = "standard"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seller_api_payload(seller: Any) -> dict[str, Any]:
    return {
        "id": seller.id,
        "name": seller.name,
        "description": seller.description,
        "ownerWalletAddress": seller.owner_wallet_address,
        "validatorWalletAddress": seller.validator_wallet_address,
        "walletSetId": seller.wallet_set_id,
        "ownerWalletId": seller.owner_wallet_id,
        "validatorWalletId": seller.validator_wallet_id,
        "status": seller.status,
        "createdAt": seller.created_at.isoformat(),
        "updatedAt": seller.updated_at.isoformat(),
    }


def _agent_api_payload(agent: Any) -> dict[str, Any]:
    return {
        "id": agent.id,
        "sellerId": agent.seller_id,
        "name": agent.name,
        "description": agent.description,
        "metadataUri": agent.metadata_uri,
        "arcAgentId": agent.arc_agent_id,
        "identityTxHash": agent.identity_tx_hash,
        "status": agent.status,
        "createdAt": agent.created_at.isoformat(),
        "updatedAt": agent.updated_at.isoformat(),
    }


def _buyer_api_payload(buyer: Any) -> dict[str, Any]:
    return {
        "id": buyer.id,
        "name": buyer.name,
        "organization": buyer.organization,
        "description": buyer.description,
        "walletAddress": buyer.wallet_address,
        "validatorWalletAddress": buyer.validator_wallet_address,
        "ownerWalletId": buyer.owner_wallet_id,
        "validatorWalletId": buyer.validator_wallet_id,
        "arcAgentId": buyer.arc_agent_id,
        "identityTxHash": buyer.identity_tx_hash,
        "status": buyer.status,
        "createdAt": buyer.created_at.isoformat(),
        "updatedAt": buyer.updated_at.isoformat(),
    }


def _tool_price_string(price_usdc: float) -> str:
    return f"${Decimal(str(price_usdc)):.2f}"


def _tool_system_instruction(tool_key: str) -> str:
    instructions = {
        "summarize": "You are a concise summarizer. Reply in under 120 words.",
        "analyze": "Provide deeper analysis with concise trade-offs and risks.",
        "plan": "Produce a crisp 3-step execution plan with milestones.",
        "response": "Give a practical direct answer with short rationale.",
    }
    return instructions.get(tool_key, "Give a concise helpful response.")


def _tokenize(text: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {token for token in normalized.split() if len(token) > 2}


def _discover_score(
    candidate: dict[str, Any],
    prompt_tokens: set[str],
    desired_tool: str,
    budget_usdc: Decimal,
    rep_by_agent: dict[int, float],
) -> tuple[Decimal, list[str]]:
    score = Decimal("0")
    reasons: list[str] = []
    tool_key = candidate["toolKey"]
    tool_price = Decimal(str(candidate["priceUSDC"]))
    text_blob = " ".join(
        [
            candidate.get("name", ""),
            candidate.get("description", ""),
            candidate.get("sellerName", ""),
            candidate.get("agentName", ""),
        ]
    )
    overlap = len(prompt_tokens.intersection(_tokenize(text_blob)))
    if overlap:
        score += Decimal(overlap) * Decimal("0.7")
        reasons.append(f"keyword_overlap={overlap}")

    if desired_tool != "auto" and tool_key == desired_tool:
        score += Decimal("4.0")
        reasons.append("matches_desired_tool")

    if tool_price <= budget_usdc:
        score += Decimal("1.2")
        reasons.append("within_budget")
    else:
        score -= Decimal("3.0")
        reasons.append("over_budget")

    if tool_price > 0:
        score += Decimal("0.01") / tool_price
        reasons.append("price_efficiency")

    agent_id = candidate.get("agentId")
    if isinstance(agent_id, int) and agent_id in rep_by_agent:
        rep = Decimal(str(rep_by_agent[agent_id]))
        score += rep / Decimal("100")
        reasons.append(f"reputation={rep_by_agent[agent_id]:.1f}")

    return score, reasons


def _public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:4021").rstrip("/")


def _external_agent_card_urls() -> list[str]:
    raw = os.getenv("EXTERNAL_AGENT_CARDS", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _internal_discovery_candidates(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for tool in tools:
        sid = tool["seller"]["id"]
        aid = tool["agent"]["id"]
        tid = tool["toolId"]
        candidates.append(
            {
                "source": "internal",
                "toolKey": tool["toolKey"],
                "priceUSDC": tool["priceUSDC"],
                "name": tool["name"],
                "description": tool["description"],
                "sellerId": sid,
                "sellerName": tool["seller"]["name"],
                "agentId": aid,
                "agentName": tool["agent"]["name"],
                "invokePath": f"/sellers/{sid}/agents/{aid}/tools/{tid}/invoke",
                "invokeUrl": f"{_public_base_url()}/sellers/{sid}/agents/{aid}/tools/{tid}/invoke",
                "raw": tool,
            }
        )
    return candidates


def _to_float_price(value: Any, default: float = 0.01) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "")
    try:
        return float(text)
    except ValueError:
        return default


def _infer_tool_key(skill: dict[str, Any]) -> str:
    joined = " ".join(
        [
            str(skill.get("id", "")),
            str(skill.get("name", "")),
            str(skill.get("description", "")),
            " ".join(str(t) for t in skill.get("tags", [])),
        ]
    ).lower()
    if "plan" in joined or "roadmap" in joined:
        return "plan"
    if "analy" in joined or "risk" in joined or "trade" in joined:
        return "analyze"
    if "summar" in joined:
        return "summarize"
    return "response"


async def _fetch_external_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    card_urls = _external_agent_card_urls()
    if not card_urls:
        return candidates

    async with httpx.AsyncClient(timeout=10) as client:
        for card_url in card_urls:
            try:
                card = (await client.get(card_url)).json()
            except Exception:
                continue
            skills = card.get("skills", [])
            base_api_url = str(card.get("url", "")).rstrip("/")
            provider_name = str(card.get("provider", {}).get("organization", card.get("name", "external-agent")))
            for skill in skills:
                path = skill.get("path") or skill.get("endpoint")
                invoke_url = skill.get("invokeUrl")
                if not invoke_url and base_api_url and path:
                    if str(path).startswith("http"):
                        invoke_url = str(path)
                    else:
                        invoke_url = f"{base_api_url}/{str(path).lstrip('/')}"

                price_usdc = _to_float_price(
                    skill.get("x402PriceUSDC") or skill.get("priceUSDC") or skill.get("price"),
                    default=0.01,
                )
                skill_id = str(skill.get("id", "external-skill"))
                candidates.append(
                    {
                        "source": "external",
                        "toolKey": _infer_tool_key(skill),
                        "priceUSDC": price_usdc,
                        "name": str(skill.get("name", skill_id)),
                        "description": str(skill.get("description", "")),
                        "sellerId": None,
                        "sellerName": provider_name,
                        "agentId": None,
                        "agentName": str(card.get("name", "ExternalAgent")),
                        "invokePath": None,
                        "invokeUrl": invoke_url,
                        "raw": {
                            "cardUrl": card_url,
                            "skillId": skill_id,
                            "tags": skill.get("tags", []),
                            "examples": skill.get("examples", []),
                        },
                    }
                )
    return candidates


def _generate_llm_text(prompt: str, system_instruction: str) -> dict[str, str]:
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if not api_key:
        return {
            "text": (
                f"[Mock {system_instruction[:40]}...] Prompt: {prompt}\n"
                "No LLM key configured - deterministic demo output."
            ),
            "provider": "mock",
            "model": "mock-model",
        }
    with httpx.Client(timeout=20) as client:
        response = client.post(
            f"{api_base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
        )
        response.raise_for_status()
        data = response.json()
        return {
            "text": data["choices"][0]["message"]["content"],
            "provider": "openai-compatible",
            "model": model,
        }


async def _ensure_gateway_middleware(app: FastAPI, seller_address: str):
    middleware = app.state.gateway_by_seller.get(seller_address)
    if middleware is None:
        middleware = create_gateway_middleware(seller_address=seller_address, chain="arcTestnet")
        app.state.gateway_by_seller[seller_address] = middleware
    return middleware


async def _process_payment(
    request: Request,
    db: Session,
    *,
    seller: Any,
    agent: Any,
    tool: Any,
    invoke_path: str,
    buyer_id: int | None = None,
):
    payment_header = request.headers.get("Payment-Signature")
    middleware = await _ensure_gateway_middleware(request.app, seller.owner_wallet_address)
    result = await middleware.process_request(
        payment_header=payment_header,
        path=invoke_path,
        price=_tool_price_string(tool.price_usdc),
    )

    if isinstance(result, PaymentInfo):
        amount_usdc = Decimal(str(result.amount)) / Decimal("1000000")
        create_payment_event(
            db,
            seller_id=seller.id,
            agent_id=agent.id,
            tool_id=tool.id,
            event_type="payment",
            status="paid",
            buyer_address=result.payer,
            transaction_ref=result.transaction,
            amount_usdc=float(amount_usdc),
            details={
                "path": invoke_path,
                "price": _tool_price_string(tool.price_usdc),
                "payer": result.payer,
                "amountBaseUnits": str(result.amount),
                "amountUSDC": f"{amount_usdc:.6f}",
                "transaction": result.transaction,
                "sellerId": seller.id,
                "agentId": agent.id,
                "toolId": tool.id,
                "buyerId": buyer_id,
            },
        )
        return result

    create_payment_event(
        db,
        seller_id=seller.id,
        agent_id=agent.id,
        tool_id=tool.id,
        event_type="payment",
        status="payment_required",
        buyer_address=None,
        transaction_ref=None,
        amount_usdc=0,
        details={
            "path": invoke_path,
            "price": _tool_price_string(tool.price_usdc),
            "httpStatus": result.get("status", 402),
            "sellerId": seller.id,
            "agentId": agent.id,
            "toolId": tool.id,
            "buyerId": buyer_id,
        },
    )
    response = JSONResponse(content=result.get("body", result), status_code=result.get("status", 402))
    for header_name, header_value in result.get("headers", {}).items():
        response.headers[header_name] = header_value
    return response


def _buyer_breakdown(events: list[PaymentEvent]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"buyerAddress": "", "paymentsCount": 0, "totalAmountUSDC": Decimal("0"), "lastTransaction": None}
    )
    for event in events:
        if event.status != "paid" or not event.buyer_address:
            continue
        entry = stats[event.buyer_address]
        entry["buyerAddress"] = event.buyer_address
        entry["paymentsCount"] += 1
        entry["totalAmountUSDC"] += Decimal(str(event.amount_usdc))
        if event.transaction_ref:
            entry["lastTransaction"] = event.transaction_ref
    result = []
    for row in stats.values():
        result.append(
            {
                "buyerAddress": row["buyerAddress"],
                "paymentsCount": row["paymentsCount"],
                "totalAmountUSDC": f"{row['totalAmountUSDC']:.6f}",
                "lastTransaction": row["lastTransaction"],
            }
        )
    result.sort(key=lambda item: item["paymentsCount"], reverse=True)
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.gateway_by_seller = {}
    yield
    for middleware in app.state.gateway_by_seller.values():
        try:
            await middleware.close()
        except Exception:
            pass


app = FastAPI(title="Arc Marketplace API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "ok": True,
        "service": "arc-marketplace",
        "mode": "mock-open",
        "message": "Multi-seller Arc marketplace with x402 paid invocation.",
    }


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "sellerCount": len(list_sellers(db)),
        "buyerCount": len(list_buyers(db)),
        "timestamp": _utc_iso(),
    }


@app.post("/buyers")
async def create_buyer_endpoint(body: BuyerCreateBody, db: Session = Depends(get_db)):
    buyer = create_buyer(
        db,
        name=body.name,
        organization=body.organization,
        description=body.description,
        wallet_address=body.walletAddress,
        validator_wallet_address=body.validatorWalletAddress,
    )
    return {"buyer": _buyer_api_payload(buyer)}


@app.get("/buyers")
async def list_buyers_endpoint(db: Session = Depends(get_db)):
    return {"buyers": [_buyer_api_payload(b) for b in list_buyers(db)]}


@app.get("/buyers/{buyer_id}")
async def get_buyer_endpoint(buyer_id: int, db: Session = Depends(get_db)):
    buyer = get_buyer(db, buyer_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found")
    invocations = list_buyer_invocations(db, buyer_id=buyer_id, limit=50)
    return {
        "buyer": _buyer_api_payload(buyer),
        "invocations": [
            {
                "id": i.id,
                "sellerId": i.seller_id,
                "agentId": i.agent_id,
                "toolId": i.tool_id,
                "amountUSDC": i.amount_usdc,
                "transactionRef": i.transaction_ref,
                "status": i.status,
                "createdAt": i.created_at.isoformat(),
            }
            for i in invocations
        ],
    }


@app.post("/buyers/{buyer_id}/arc/register")
async def arc_register_buyer(buyer_id: int, body: RegisterBody, db: Session = Depends(get_db)):
    buyer = get_buyer(db, buyer_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found")
    registration = register_agent_identity(
        metadata_uri=body.metadataUri,
        owner_wallet_id=buyer.owner_wallet_id,
        validator_wallet_id=buyer.validator_wallet_id,
    )
    buyer.owner_wallet_id = registration.owner_wallet_id
    buyer.validator_wallet_id = registration.validator_wallet_id
    buyer.wallet_address = registration.owner_wallet_address
    buyer.validator_wallet_address = registration.validator_wallet_address
    buyer.arc_agent_id = registration.agent_id
    buyer.identity_tx_hash = registration.tx_hash
    buyer.status = "registered"
    db.commit()
    db.refresh(buyer)
    return {"buyer": _buyer_api_payload(buyer), "arc": {"txHash": registration.tx_hash, "agentId": registration.agent_id}}


@app.post("/sellers")
async def create_seller_endpoint(body: SellerCreateBody, db: Session = Depends(get_db)):
    seller = create_seller(
        db,
        name=body.name,
        description=body.description,
        owner_wallet_address=body.ownerWalletAddress,
        validator_wallet_address=body.validatorWalletAddress,
    )
    return {"seller": _seller_api_payload(seller)}


@app.get("/sellers")
async def list_sellers_endpoint(db: Session = Depends(get_db)):
    return {"sellers": [_seller_api_payload(s) for s in list_sellers(db)]}


@app.get("/sellers/{seller_id}")
async def get_seller_endpoint(seller_id: int, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    agents = list_agents(db, seller_id=seller_id)
    return {"seller": _seller_api_payload(seller), "agents": [_agent_api_payload(a) for a in agents]}


@app.post("/sellers/{seller_id}/agents")
async def create_agent_endpoint(seller_id: int, body: AgentCreateBody, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    agent = create_agent(
        db,
        seller_id=seller_id,
        name=body.name,
        description=body.description,
        metadata_uri=body.metadataUri,
    )
    return {"agent": _agent_api_payload(agent)}


@app.get("/marketplace/tools")
async def marketplace_tools(db: Session = Depends(get_db)):
    return {"tools": list_tools_for_marketplace(db)}


@app.post("/marketplace/discover")
async def marketplace_discover(body: DiscoverBody, db: Session = Depends(get_db)):
    tools = list_tools_for_marketplace(db)
    internal_candidates = _internal_discovery_candidates(tools)
    external_candidates = await _fetch_external_candidates()
    all_candidates = internal_candidates + external_candidates
    prompt_tokens = _tokenize(body.prompt)
    budget = Decimal(str(body.budgetUSDC))
    desired = body.desiredTool.strip().lower()

    reputation_rows = db.execute(
        select(ReputationEvent.agent_id, func.avg(ReputationEvent.score)).group_by(ReputationEvent.agent_id)
    ).all()
    rep_by_agent = {agent_id: float(avg_score or 0) for agent_id, avg_score in reputation_rows}

    ranked: list[dict[str, Any]] = []
    for candidate in all_candidates:
        score, reasons = _discover_score(candidate, prompt_tokens, desired, budget, rep_by_agent)
        ranked.append(
            {
                "score": float(score),
                "reasons": reasons,
                "invokePath": candidate.get("invokePath"),
                "invokeUrl": candidate.get("invokeUrl"),
                "candidate": candidate,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    selected = [item for item in ranked if Decimal(str(item["candidate"]["priceUSDC"])) <= budget][
        : body.maxResults
    ]
    if not selected:
        selected = ranked[: body.maxResults]

    return {
        "query": {
            "prompt": body.prompt,
            "budgetUSDC": body.budgetUSDC,
            "desiredTool": body.desiredTool,
            "maxResults": body.maxResults,
        },
        "candidates": selected,
    }


@app.get("/.well-known/agent-card.json")
async def agent_card(db: Session = Depends(get_db)):
    tools = list_tools_for_marketplace(db)
    skills = []
    for tool in tools[:50]:
        skills.append(
            {
                "id": f"tool-{tool['toolId']}",
                "name": tool["name"],
                "description": tool["description"],
                "tags": [tool["toolKey"], "x402", "arc", "marketplace", tool["seller"]["name"]],
                "examples": [f"Use {tool['name']} for: summarize trading strategy risks."],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "x402PriceUSDC": tool["priceUSDC"],
                "path": f"/sellers/{tool['seller']['id']}/agents/{tool['agent']['id']}/tools/{tool['toolId']}/invoke",
            }
        )
    return {
        "name": "Arc Marketplace Agent",
        "description": "Multi-seller Arc x402 marketplace for autonomous agent service discovery and invocation.",
        "url": _public_base_url(),
        "provider": {"organization": "Agents Market", "url": _public_base_url()},
        "version": "0.1.0",
        "documentationUrl": f"{_public_base_url()}/docs",
        "capabilities": {"streaming": False, "stateHistory": True},
        "authentication": {"type": "x402-or-bearer", "instructions": "Use x402 Payment-Signature for paid invoke routes."},
        "skills": skills,
    }


@app.get("/.well-known/ai-plugin.json")
async def ai_plugin_manifest():
    base = _public_base_url()
    return {
        "schema_version": "v1",
        "name_for_human": "Arc Marketplace",
        "name_for_model": "arc_marketplace",
        "description_for_human": "Discover and invoke paid agent services on Arc.",
        "description_for_model": "Discover skills via /marketplace/discover and invoke paid tools via seller-scoped endpoints.",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": f"{base}/openapi.yaml"},
        "logo_url": f"{base}/favicon.ico",
        "contact_email": "dev@localhost",
        "legal_info_url": f"{base}/",
    }


@app.get("/openapi.yaml", response_class=Response)
async def openapi_yaml():
    schema = app.openapi()
    content = yaml.safe_dump(schema, sort_keys=False)
    return Response(content=content, media_type="application/yaml")


@app.get("/tools")
async def tools_compat(db: Session = Depends(get_db)):
    tools = list_tools_for_marketplace(db)
    return {
        "tools": [
            {
                "id": t["toolKey"],
                "path": f"/sellers/{t['seller']['id']}/agents/{t['agent']['id']}/tools/{t['toolId']}/invoke",
                "price": f"${Decimal(str(t['priceUSDC'])):.2f}",
                "description": t["description"],
                "sellerName": t["seller"]["name"],
                "agentName": t["agent"]["name"],
            }
            for t in tools
        ]
    }


@app.post("/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke")
async def invoke_tool(
    seller_id: int,
    agent_id: int,
    tool_id: int,
    body: InvokeBody,
    request: Request,
    db: Session = Depends(get_db),
):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    agent = get_agent(db, agent_id)
    if agent is None or agent.seller_id != seller_id:
        raise HTTPException(status_code=404, detail="Agent not found for seller")
    tool = get_tool_for_agent(db, seller_id=seller_id, agent_id=agent_id, tool_id=tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found for seller/agent")

    buyer_id = body.buyerId
    buyer_id_header = request.headers.get("X-Buyer-Id")
    if buyer_id is None and buyer_id_header:
        try:
            buyer_id = int(buyer_id_header)
        except ValueError:
            raise HTTPException(status_code=400, detail="X-Buyer-Id must be an integer") from None
    if buyer_id is not None:
        buyer = get_buyer(db, buyer_id)
        if buyer is None:
            raise HTTPException(status_code=404, detail="Buyer not found")

    invoke_path = f"/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke"
    paid = await _process_payment(
        request,
        db,
        seller=seller,
        agent=agent,
        tool=tool,
        invoke_path=invoke_path,
        buyer_id=buyer_id,
    )
    if isinstance(paid, JSONResponse):
        return paid

    llm_result = _generate_llm_text(body.prompt, _tool_system_instruction(tool.tool_key))
    create_payment_event(
        db,
        seller_id=seller.id,
        agent_id=agent.id,
        tool_id=tool.id,
        event_type="seller_output",
        status="completed",
        buyer_address=paid.payer,
        transaction_ref=paid.transaction,
        amount_usdc=0,
        details={
            "path": invoke_path,
            "promptPreview": body.prompt[:120],
            "responsePreview": llm_result["text"][:160],
            "provider": llm_result["provider"],
            "model": llm_result["model"],
            "transaction": paid.transaction,
            "buyerId": buyer_id,
        },
    )
    if buyer_id is not None:
        create_buyer_invocation(
            db,
            buyer_id=buyer_id,
            seller_id=seller.id,
            agent_id=agent.id,
            tool_id=tool.id,
            payment_event_id=None,
            prompt=body.prompt,
            output_preview=llm_result["text"][:300],
            amount_usdc=float(Decimal(str(paid.amount)) / Decimal("1000000")),
            transaction_ref=paid.transaction,
            status="completed",
        )

    response_body = {
        "sellerId": seller.id,
        "agentId": agent.id,
        "toolId": tool.id,
        "toolKey": tool.tool_key,
        "prompt": body.prompt,
        "outputText": llm_result["text"],
        "payment": {
            "amountBaseUnits": str(paid.amount),
            "amountUSDC": f"{(Decimal(str(paid.amount)) / Decimal('1000000')):.6f}",
            "payer": paid.payer,
            "transaction": paid.transaction,
        },
        "llm": {"provider": llm_result["provider"], "model": llm_result["model"]},
    }
    response = JSONResponse(content=response_body)
    for header_name, header_value in paid.response_headers.items():
        response.headers[header_name] = header_value
    return response


@app.get("/transactions")
async def transactions(db: Session = Depends(get_db)):
    events = list_payment_events(db)
    return {
        "events": [
            {
                "timestamp": e.created_at.isoformat(),
                "eventType": e.event_type,
                "status": e.status,
                "details": e.details,
            }
            for e in events
        ],
        "summary": payment_summary(db),
        "buyers": _buyer_breakdown(events),
    }


@app.post("/agents/{agent_id}/arc/register")
async def arc_register(agent_id: int, body: RegisterBody, db: Session = Depends(get_db)):
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    seller = get_seller(db, agent.seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    registration = register_agent_identity(
        metadata_uri=body.metadataUri or agent.metadata_uri,
        owner_wallet_id=seller.owner_wallet_id,
        validator_wallet_id=seller.validator_wallet_id,
    )
    seller.owner_wallet_id = registration.owner_wallet_id
    seller.validator_wallet_id = registration.validator_wallet_id
    seller.owner_wallet_address = registration.owner_wallet_address
    seller.validator_wallet_address = registration.validator_wallet_address
    agent.arc_agent_id = registration.agent_id
    agent.identity_tx_hash = registration.tx_hash
    agent.status = "registered"
    db.commit()
    db.refresh(agent)
    db.refresh(seller)
    return {
        "agent": _agent_api_payload(agent),
        "seller": _seller_api_payload(seller),
        "arc": {"txHash": registration.tx_hash, "agentId": registration.agent_id},
    }


@app.post("/agents/{agent_id}/arc/reputation")
async def arc_reputation(agent_id: int, body: ReputationBody, db: Session = Depends(get_db)):
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    seller = get_seller(db, agent.seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not agent.arc_agent_id:
        raise HTTPException(status_code=400, detail="Agent is not Arc-registered yet")

    feedback_hash = body.feedbackHash or ("0x" + os.urandom(32).hex())
    tx_hash = arc_record_reputation(
        validator_wallet_address=seller.validator_wallet_address,
        agent_id=agent.arc_agent_id,
        score=body.score,
        tag=body.tag,
        feedback_hash=feedback_hash,
    )
    event = create_reputation_event(
        db,
        agent_id=agent.id,
        validator_wallet_address=seller.validator_wallet_address,
        score=body.score,
        tag=body.tag,
        feedback_hash=feedback_hash,
        tx_hash=tx_hash,
    )
    return {
        "reputation": {
            "id": event.id,
            "agentId": agent.id,
            "score": event.score,
            "tag": event.tag,
            "feedbackHash": event.feedback_hash,
            "txHash": event.tx_hash,
        }
    }


@app.post("/agents/{agent_id}/arc/validation/request")
async def arc_validation_request(agent_id: int, body: ValidationRequestBody, db: Session = Depends(get_db)):
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    seller = get_seller(db, agent.seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    if not agent.arc_agent_id:
        raise HTTPException(status_code=400, detail="Agent is not Arc-registered yet")

    validator_wallet = body.validatorWalletAddress or seller.validator_wallet_address
    request_hash = body.requestHash or ("0x" + uuid.uuid4().hex.ljust(64, "0")[:64])
    tx_hash = arc_create_validation_request(
        owner_wallet_address=seller.owner_wallet_address,
        validator_wallet_address=validator_wallet,
        agent_id=agent.arc_agent_id,
        request_uri=body.requestUri,
        request_hash=request_hash,
    )
    row = create_validation_request(
        db,
        agent_id=agent.id,
        validator_wallet_address=validator_wallet,
        request_hash=request_hash,
        request_uri=body.requestUri,
        request_tx_hash=tx_hash,
    )
    return {
        "validationRequest": {
            "id": row.id,
            "agentId": row.agent_id,
            "requestHash": row.request_hash,
            "requestUri": row.request_uri,
            "validatorWalletAddress": row.validator_wallet_address,
            "requestTxHash": row.request_tx_hash,
        }
    }


@app.post("/agents/{agent_id}/arc/validation/respond")
async def arc_validation_respond(agent_id: int, body: ValidationResponseBody, db: Session = Depends(get_db)):
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    seller = get_seller(db, agent.seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    row = get_validation_request(db, body.requestHash)
    if row is None:
        raise HTTPException(status_code=404, detail="Validation request not found")

    tx_hash = arc_submit_validation_response(
        validator_wallet_address=row.validator_wallet_address or seller.validator_wallet_address,
        request_hash=body.requestHash,
        response_code=body.responseCode,
        response_tag=body.responseTag,
    )
    updated = set_validation_response(
        db,
        request_hash=body.requestHash,
        response_code=body.responseCode,
        response_tag=body.responseTag,
        response_tx_hash=tx_hash,
    )
    status = arc_get_validation_status(body.requestHash)
    return {
        "validationResponse": {
            "requestHash": body.requestHash,
            "responseCode": body.responseCode,
            "responseTag": body.responseTag,
            "responseTxHash": tx_hash,
            "dbRecordId": updated.id if updated else None,
            "onChainStatus": status,
        }
    }


@app.post("/sellers/{seller_id}/gateway/deposit")
async def gateway_deposit(seller_id: int, body: GatewayDepositBody, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    private_key = os.getenv("SELLER_PRIVATE_KEY")
    if not private_key:
        raise HTTPException(status_code=400, detail="SELLER_PRIVATE_KEY is required in .env")

    async with GatewayClient(chain="arcTestnet", private_key=private_key) as gateway:
        result = await gateway.deposit(body.amount)
        balances = await gateway.get_balances()
        account = upsert_gateway_account(
            db,
            seller_id=seller.id,
            chain="arcTestnet",
            wallet_address=gateway.address,
            wallet_balance_usdc=float(balances.wallet.formatted),
            gateway_available_usdc=float(balances.gateway.formatted_available),
        )
    return {
        "gateway": {
            "sellerId": seller.id,
            "depositTxHash": result.deposit_tx_hash,
            "walletAddress": account.wallet_address,
            "walletBalanceUSDC": account.wallet_balance_usdc,
            "gatewayAvailableUSDC": account.gateway_available_usdc,
        }
    }


@app.post("/sellers/{seller_id}/wallets/provision")
async def provision_circle_wallets(
    seller_id: int,
    body: WalletProvisionBody,
    db: Session = Depends(get_db),
):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    if not api_key or not entity_secret:
        raise HTTPException(status_code=400, detail="CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET are required")

    circle_client = utils.init_developer_controlled_wallets_client(api_key=api_key, entity_secret=entity_secret)
    wallet_sets_api = developer_controlled_wallets.WalletSetsApi(circle_client)
    wallets_api = developer_controlled_wallets.WalletsApi(circle_client)

    wallet_set = wallet_sets_api.create_wallet_set(
        developer_controlled_wallets.CreateWalletSetRequest.from_dict(
            {"name": body.walletSetName or f"seller-{seller.id}-wallet-set"}
        )
    )
    wallet_set_id = wallet_set.data.wallet_set.actual_instance.id

    wallets = wallets_api.create_wallet(
        developer_controlled_wallets.CreateWalletRequest.from_dict(
            {
                "blockchains": ["ARC-TESTNET"],
                "count": 2,
                "walletSetId": wallet_set_id,
                "accountType": "SCA",
            }
        )
    ).data.wallets

    owner = wallets[0].actual_instance
    validator = wallets[1].actual_instance
    seller.wallet_set_id = wallet_set_id
    seller.owner_wallet_id = owner.id
    seller.validator_wallet_id = validator.id
    seller.owner_wallet_address = owner.address
    seller.validator_wallet_address = validator.address
    db.commit()
    db.refresh(seller)
    return {
        "seller": _seller_api_payload(seller),
        "wallets": {
            "walletSetId": wallet_set_id,
            "ownerWallet": {"id": owner.id, "address": owner.address},
            "validatorWallet": {"id": validator.id, "address": validator.address},
        },
    }


@app.get("/sellers/{seller_id}/gateway/balances")
async def gateway_balances(seller_id: int, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    private_key = os.getenv("SELLER_PRIVATE_KEY")
    if not private_key:
        raise HTTPException(status_code=400, detail="SELLER_PRIVATE_KEY is required in .env")

    async with GatewayClient(chain="arcTestnet", private_key=private_key) as gateway:
        balances = await gateway.get_balances()
        account = upsert_gateway_account(
            db,
            seller_id=seller.id,
            chain="arcTestnet",
            wallet_address=gateway.address,
            wallet_balance_usdc=float(balances.wallet.formatted),
            gateway_available_usdc=float(balances.gateway.formatted_available),
        )
    return {
        "gateway": {
            "sellerId": seller.id,
            "chain": account.chain,
            "walletAddress": account.wallet_address,
            "walletBalanceUSDC": account.wallet_balance_usdc,
            "gatewayAvailableUSDC": account.gateway_available_usdc,
            "lastSyncedAt": account.last_synced_at.isoformat(),
        }
    }


@app.post("/sellers/{seller_id}/bridge/transfers")
async def bridge_transfer(seller_id: int, body: BridgeTransferBody, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")

    transfer_ref = f"bridge_{uuid.uuid4().hex[:16]}"
    row = create_bridge_transfer(
        db,
        seller_id=seller.id,
        source_chain=body.sourceChain,
        destination_chain=body.destinationChain,
        amount_usdc=body.amountUSDC,
        status="queued",
        transfer_ref=transfer_ref,
        metadata={
            "speed": body.speed,
            "note": "Bridge Kit orchestration stub for hackathon flow.",
            "requestedAt": _utc_iso(),
        },
    )
    return {
        "bridgeTransfer": {
            "id": row.id,
            "sellerId": row.seller_id,
            "sourceChain": row.source_chain,
            "destinationChain": row.destination_chain,
            "amountUSDC": row.amount_usdc,
            "status": row.status,
            "transferRef": row.transfer_ref,
            "metadata": row.transfer_metadata,
        }
    }
