"""Multi-seller Arc marketplace API with x402 paid tool execution."""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from json import JSONDecodeError
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from agents_market._env import load_backend_env
from agents_market.arc.services.erc8004 import (
    create_validation_request as arc_create_validation_request,
    get_validation_status as arc_get_validation_status,
    register_agent_identity,
    record_reputation as arc_record_reputation,
    submit_validation_response as arc_submit_validation_response,
)
from agents_market.arc.services.payments import (
    ARC_TESTNET_USDC,
    derive_wallet_id_by_address,
    get_wallet_balances,
    transfer_usdc_from_private_key,
    transfer_usdc,
)
from agents_market.db import Base, engine, get_db
from agents_market.marketplace.models import PaymentEvent, ReputationEvent
from agents_market.marketplace.repository import (
    create_agent,
    create_buyer,
    create_buyer_invocation,
    create_bridge_transfer,
    create_external_funding_attempt,
    create_payment_event,
    create_reputation_event,
    create_usage_records,
    create_seller,
    create_validation_request,
    get_agent,
    get_buyer,
    get_external_funding_attempt,
    get_seller,
    get_tool_for_agent,
    get_validation_request,
    list_agents,
    list_buyer_invocations,
    list_buyers,
    list_agents_for_marketplace,
    list_payment_events,
    list_skills_for_tool,
    list_sellers,
    list_tools_for_marketplace,
    payment_summary,
    set_validation_response,
    update_agent_tool_prices,
    update_tool_pricing,
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
    ownerWalletAddress: str = ""
    validatorWalletAddress: str = ""


class AgentCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=80, default="General")
    endpointUrl: str = ""
    httpMethod: str = "POST"
    priceUSDC: float = Field(gt=0, le=0.01, default=0.01)
    apiDocsUrl: str = ""
    metadataUri: str = ""
    iconDataUrl: str = ""
    capabilities: list["AgentCapabilityBody"] = Field(default_factory=list)


class CapabilitySkillBody(BaseModel):
    skillKey: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    priceUSDC: float = Field(ge=0, le=0.01, default=0)


class AgentCapabilityBody(BaseModel):
    toolKey: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    category: str = Field(min_length=1, max_length=80, default="General")
    endpointUrl: str = Field(min_length=8, max_length=500)
    httpMethod: str = "POST"
    priceUSDC: float = Field(gt=0, le=0.01)
    runtimePriceUSDC: float = Field(ge=0, le=0.01, default=0)
    runtimeUnit: str = Field(default="none")
    capabilityType: str = Field(default="tool")
    skills: list[CapabilitySkillBody] = Field(default_factory=list)


class BuyerCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization: str = ""
    description: str = ""
    walletAddress: str = ""
    validatorWalletAddress: str = ""


class ExternalBuyerCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization: str = ""
    description: str = ""


class InvokeBody(BaseModel):
    prompt: str = "Give me a short Arc ecosystem update."
    buyerId: int | None = None
    selectedSkills: list[str] = Field(default_factory=list)
    usageUnits: float | None = Field(default=None, ge=0)


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


DEMO_TREASURY_MODE = "shared_demo_treasury"
DEMO_TREASURY_CHAIN = "arcTestnet"
ARC_SETTLEMENT_CHAIN = "Arc_Testnet"
ARC_SETTLEMENT_CHAIN_ID = 5042002
ARC_USDC_DECIMALS = 6
FUNDING_RAIL = "circle-app-kit-bridge-cctp"
SUPPORTED_FUNDING_SOURCE_CHAINS = (
    "Ethereum_Sepolia",
    "Base_Sepolia",
    "Arbitrum_Sepolia",
    "Avalanche_Fuji",
    "Optimism_Sepolia",
    "Polygon_Amoy_Testnet",
)
ONCHAIN_TX_HASH_RE = re.compile(r"^(?:0x)?[a-fA-F0-9]{64}$")
ARCSCAN_TX_URL = "https://testnet.arcscan.app/tx/"


class WalletProvisionBody(BaseModel):
    walletSetName: str | None = None


class BridgeTransferBody(BaseModel):
    sourceChain: str = "arcTestnet"
    destinationChain: str
    amountUSDC: float = Field(gt=0)
    speed: str = "standard"


class ExternalFundingBody(BaseModel):
    sourceChain: str = Field(min_length=1, max_length=64)
    amountUSDC: str = Field(min_length=1, max_length=64)
    transferSpeed: str = "FAST"


class AgentPricingUpdateBody(BaseModel):
    basePriceUSDC: float = Field(gt=0, le=0.01)


class ToolPricingUpdateBody(BaseModel):
    toolPriceUSDC: float | None = Field(default=None, gt=0, le=0.01)
    runtimePriceUSDC: float | None = Field(default=None, ge=0, le=0.01)
    skillPrices: list[dict[str, Any]] = Field(default_factory=list)


AgentCreateBody.model_rebuild()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_http_method(method: str) -> str:
    normalized = method.strip().upper()
    if normalized not in {"GET", "POST"}:
        raise HTTPException(status_code=400, detail="Only GET and POST provider endpoints are supported")
    return normalized


def _validate_http_url(value: str, *, field_name: str) -> str:
    text = value.strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an absolute http(s) URL")
    return text


def _require_circle_arc_env() -> None:
    missing = [name for name in ("CIRCLE_API_KEY", "CIRCLE_ENTITY_SECRET") if not os.getenv(name)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"{', '.join(missing)} required for automatic Arc ERC-8004 registration",
        )


def _shared_demo_treasury_private_key() -> str:
    private_key = os.getenv("SELLER_PRIVATE_KEY")
    if not private_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "SELLER_PRIVATE_KEY is required for shared demo Gateway treasury operations. "
                "It is not a per-seller key."
            ),
        )
    return private_key


def _demo_treasury_gateway_payload(
    *,
    account: Any | None = None,
    seller: Any | None = None,
    treasury_wallet_address: str,
    wallet_balance_usdc: float,
    gateway_available_usdc: float,
    deposit_tx_hash: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": DEMO_TREASURY_MODE,
        "chain": DEMO_TREASURY_CHAIN,
        "treasuryWalletAddress": treasury_wallet_address,
        "walletAddress": treasury_wallet_address,
        "walletBalanceUSDC": wallet_balance_usdc,
        "gatewayAvailableUSDC": gateway_available_usdc,
        "lastSyncedAt": account.last_synced_at.isoformat() if account is not None else _utc_iso(),
    }
    if seller is not None:
        payload["sellerId"] = seller.id
        payload["sellerRecipientAddress"] = seller.owner_wallet_address
    if deposit_tx_hash is not None:
        payload["depositTxHash"] = deposit_tx_hash
    return payload


def _create_seller_wallets(seller: Any, *, wallet_set_name: str | None = None) -> dict[str, Any]:
    _require_circle_arc_env()
    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    circle_client = utils.init_developer_controlled_wallets_client(api_key=api_key, entity_secret=entity_secret)
    wallet_sets_api = developer_controlled_wallets.WalletSetsApi(circle_client)
    wallets_api = developer_controlled_wallets.WalletsApi(circle_client)

    wallet_set = wallet_sets_api.create_wallet_set(
        developer_controlled_wallets.CreateWalletSetRequest.from_dict(
            {"name": wallet_set_name or f"seller-{seller.id}-wallet-set"}
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
    return {
        "walletSetId": wallet_set_id,
        "ownerWallet": {"id": owner.id, "address": owner.address},
        "validatorWallet": {"id": validator.id, "address": validator.address},
    }


def _create_buyer_wallets(buyer: Any, *, wallet_set_name: str | None = None) -> dict[str, Any]:
    _require_circle_arc_env()
    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    circle_client = utils.init_developer_controlled_wallets_client(api_key=api_key, entity_secret=entity_secret)
    wallet_sets_api = developer_controlled_wallets.WalletSetsApi(circle_client)
    wallets_api = developer_controlled_wallets.WalletsApi(circle_client)

    wallet_set = wallet_sets_api.create_wallet_set(
        developer_controlled_wallets.CreateWalletSetRequest.from_dict(
            {"name": wallet_set_name or f"buyer-{buyer.id}-wallet-set"}
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
    buyer.owner_wallet_id = owner.id
    buyer.validator_wallet_id = validator.id
    buyer.wallet_address = owner.address
    buyer.validator_wallet_address = validator.address
    return {
        "walletSetId": wallet_set_id,
        "ownerWallet": {"id": owner.id, "address": owner.address},
        "validatorWallet": {"id": validator.id, "address": validator.address},
    }


def _ensure_seller_arc_wallets(seller: Any, db: Session) -> None:
    if seller.owner_wallet_id and seller.validator_wallet_id:
        return
    _create_seller_wallets(seller)
    db.commit()
    db.refresh(seller)


def _ensure_buyer_arc_wallets(buyer: Any, db: Session) -> None:
    if buyer.owner_wallet_id and buyer.validator_wallet_id and buyer.wallet_address:
        return
    if buyer.wallet_address and not buyer.owner_wallet_id:
        try:
            derived_wallet_id = derive_wallet_id_by_address(buyer.wallet_address)
        except Exception:
            derived_wallet_id = None
        if derived_wallet_id:
            buyer.owner_wallet_id = derived_wallet_id
            db.commit()
            db.refresh(buyer)
        return
    _create_buyer_wallets(buyer)
    db.commit()
    db.refresh(buyer)


def _wallet_balances_payload(*, wallet_id: str | None, wallet_address: str) -> dict[str, Any]:
    balances = get_wallet_balances(wallet_address, wallet_id=wallet_id)
    return {
        "walletId": wallet_id,
        "walletAddress": wallet_address,
        "usdcTokenAddress": ARC_TESTNET_USDC,
        "usdc": balances.get("usdc"),
        "tokens": balances.get("tokens", []),
        "network": "arcTestnet",
    }


def _lookup_private_key_for_address(address: str) -> str | None:
    normalized = address.lower()
    explicit_pairs = [
        (os.getenv("CLIENT_ADDRESS", ""), os.getenv("CLIENT_PRIVATE_KEY", "")),
        (os.getenv("SELLER_ADDRESS", ""), os.getenv("SELLER_PRIVATE_KEY", "")),
    ]
    for wallet_address, private_key in explicit_pairs:
        if wallet_address and wallet_address.lower() == normalized and private_key:
            return private_key

    for index in range(1, 20):
        wallet_address = os.getenv(f"AI_AGENT_{index}_ADDRESS", "")
        private_key = os.getenv(f"AI_AGENT_{index}_PRIVATE_KEY", "")
        if wallet_address and wallet_address.lower() == normalized and private_key:
            return private_key
    return None


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
        "iconDataUrl": agent.icon_data_url,
        "category": agent.category,
        "endpointUrl": agent.endpoint_url,
        "httpMethod": agent.http_method,
        "apiDocsUrl": agent.api_docs_url,
        "healthStatus": agent.health_status,
        "lastHealthCheckAt": agent.last_health_check_at.isoformat()
        if agent.last_health_check_at is not None
        else None,
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
    amount = Decimal(str(price_usdc)).quantize(Decimal("0.000001")).normalize()
    return f"${amount:f}"


def _tool_api_payload(tool: Any, db: Session, *, fallback_agent: Any | None = None) -> dict[str, Any]:
    endpoint_url = tool.endpoint_url or (fallback_agent.endpoint_url if fallback_agent is not None else "")
    http_method = tool.http_method or (fallback_agent.http_method if fallback_agent is not None else "POST")
    return {
        "toolId": tool.id,
        "toolKey": tool.tool_key,
        "slug": tool.slug,
        "name": tool.name,
        "description": tool.description,
        "priceUSDC": tool.price_usdc,
        "runtimePriceUSDC": tool.runtime_price_usdc,
        "runtimeUnit": tool.runtime_unit,
        "capabilityType": tool.capability_type,
        "category": tool.category,
        "endpointUrl": endpoint_url,
        "httpMethod": http_method,
        "skills": [
            {
                "skillId": skill.id,
                "skillKey": skill.skill_key,
                "name": skill.name,
                "description": skill.description,
                "priceUSDC": skill.price_usdc,
            }
            for skill in list_skills_for_tool(db, tool.id)
        ],
    }


def _normalize_runtime_unit(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"none", "per_request"}:
        raise HTTPException(status_code=400, detail="runtimeUnit must be 'none' or 'per_request'")
    return normalized


def _build_capabilities_payload(body: AgentCreateBody) -> list[dict[str, Any]]:
    capabilities = body.capabilities or []
    if capabilities:
        payloads = []
        for capability in capabilities:
            payloads.append(
                {
                    "toolKey": capability.toolKey.strip(),
                    "name": capability.name.strip(),
                    "description": capability.description.strip(),
                    "category": capability.category.strip(),
                    "endpointUrl": _validate_http_url(capability.endpointUrl, field_name="capabilities.endpointUrl"),
                    "httpMethod": _normalize_http_method(capability.httpMethod),
                    "priceUSDC": capability.priceUSDC,
                    "runtimePriceUSDC": capability.runtimePriceUSDC,
                    "runtimeUnit": _normalize_runtime_unit(capability.runtimeUnit),
                    "capabilityType": capability.capabilityType.strip() or "tool",
                    "skills": [
                        {
                            "skillKey": skill.skillKey.strip(),
                            "name": skill.name.strip(),
                            "description": skill.description.strip(),
                            "priceUSDC": skill.priceUSDC,
                        }
                        for skill in capability.skills
                    ],
                }
            )
        return payloads

    return [
        {
            "toolKey": "invoke",
            "name": body.name.strip(),
            "description": body.description.strip(),
            "category": body.category.strip(),
            "endpointUrl": _validate_http_url(body.endpointUrl, field_name="endpointUrl"),
            "httpMethod": _normalize_http_method(body.httpMethod),
            "priceUSDC": body.priceUSDC,
            "runtimePriceUSDC": 0,
            "runtimeUnit": "none",
            "capabilityType": "tool",
            "skills": [],
        }
    ]


def _pricing_breakdown(tool: Any, selected_skill_keys: list[str], *, db: Session) -> tuple[Decimal, list[dict[str, Any]], list[Any]]:
    components: list[dict[str, Any]] = []
    total = Decimal("0")

    tool_price = Decimal(str(tool.price_usdc))
    components.append(
        {
            "componentType": "tool",
            "componentKey": tool.tool_key,
            "componentName": tool.name,
            "units": 1,
            "unitPriceUSDC": float(tool_price),
            "subtotalUSDC": float(tool_price),
            "skillId": None,
        }
    )
    total += tool_price

    matched_skills = []
    selected = {item.strip().lower() for item in selected_skill_keys if item.strip()}
    for skill in list_skills_for_tool(db, tool.id):
        if skill.skill_key.lower() not in selected:
            continue
        price = Decimal(str(skill.price_usdc))
        matched_skills.append(skill)
        components.append(
            {
                "componentType": "skill",
                "componentKey": skill.skill_key,
                "componentName": skill.name,
                "units": 1,
                "unitPriceUSDC": float(price),
                "subtotalUSDC": float(price),
                "skillId": skill.id,
            }
        )
        total += price

    runtime_price = Decimal(str(tool.runtime_price_usdc))
    if tool.runtime_unit == "per_request" and runtime_price > 0:
        components.append(
            {
                "componentType": "runtime",
                "componentKey": "per_request",
                "componentName": "Agent runtime",
                "units": 1,
                "unitPriceUSDC": float(runtime_price),
                "subtotalUSDC": float(runtime_price),
                "skillId": None,
            }
        )
        total += runtime_price

    if total <= 0:
        raise HTTPException(status_code=400, detail="Capability total must be greater than zero")
    if total > Decimal("0.01"):
        raise HTTPException(status_code=400, detail="Total charge must be at or below 0.01 USDC")
    return total, components, matched_skills


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


def _funding_metadata() -> dict[str, Any]:
    base = _public_base_url()
    return {
        "paymentProtocol": "arc-usdc",
        "settlementNetwork": ARC_SETTLEMENT_CHAIN,
        "settlementChainId": ARC_SETTLEMENT_CHAIN_ID,
        "asset": "USDC",
        "assetDecimals": ARC_USDC_DECIMALS,
        "acceptedFundingRails": [FUNDING_RAIL],
        "acceptedSourceChains": list(SUPPORTED_FUNDING_SOURCE_CHAINS),
        "fundingEstimateUrl": f"{base}/external-buyers/{{buyerId}}/funding/estimate",
        "fundingBridgeUrl": f"{base}/external-buyers/{{buyerId}}/funding/bridge",
        "requiresBuyerArcRegistration": False,
    }


def _with_funding_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["payment"] = _funding_metadata()
    return enriched


def _normalize_source_chain(source_chain: str) -> str:
    normalized = source_chain.strip()
    if normalized not in SUPPORTED_FUNDING_SOURCE_CHAINS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported source chain for external buyer funding",
                "supportedSourceChains": list(SUPPORTED_FUNDING_SOURCE_CHAINS),
            },
        )
    return normalized


def _normalize_funding_amount(amount_usdc: str) -> str:
    try:
        amount = Decimal(str(amount_usdc).strip())
    except Exception:
        raise HTTPException(status_code=400, detail="amountUSDC must be a decimal string") from None
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amountUSDC must be greater than zero")
    if amount.as_tuple().exponent < -ARC_USDC_DECIMALS:
        raise HTTPException(status_code=400, detail="amountUSDC supports up to 6 decimal places")
    return f"{amount.normalize():f}"


def _normalize_transfer_speed(speed: str) -> str:
    normalized = speed.strip().upper()
    if normalized not in {"FAST", "SLOW"}:
        raise HTTPException(status_code=400, detail="transferSpeed must be FAST or SLOW")
    return normalized


def _bridge_worker_path() -> Path:
    return Path(__file__).resolve().parents[1] / "bridge" / "arc_app_kit_bridge_worker.mjs"


def _run_bridge_worker(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    worker_path = _bridge_worker_path()
    command = [os.getenv("NODE_BINARY", "node"), str(worker_path), action]
    env = {
        **os.environ,
        "ARC_BRIDGE_WORKER_PAYLOAD": json.dumps(payload),
    }
    try:
        completed = subprocess.run(
            command,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("ARC_BRIDGE_WORKER_TIMEOUT_SECONDS", "600")),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Node.js is required for Arc App Kit bridge worker") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Arc App Kit bridge worker timed out") from exc

    try:
        result = json.loads(completed.stdout.strip() or "{}")
    except JSONDecodeError as exc:
        stderr = completed.stderr.strip()
        raise HTTPException(
            status_code=502,
            detail=f"Arc App Kit bridge worker returned invalid JSON: {stderr[:300]}",
        ) from exc
    if completed.returncode != 0:
        message = result.get("error") or completed.stderr.strip() or "Arc App Kit bridge worker failed"
        raise HTTPException(status_code=502, detail=message)
    return result


def _bridge_step_strings(result: dict[str, Any], key: str) -> list[str]:
    values: list[str] = []
    for step in result.get("steps", []) if isinstance(result.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        candidate = step.get(key) or (step.get("data", {}) if isinstance(step.get("data"), dict) else {}).get(key)
        if candidate:
            values.append(str(candidate))
    return values


def _external_funding_payload(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "buyerId": row.buyer_id,
        "sourceChain": row.source_chain,
        "destinationChain": row.destination_chain,
        "amountUSDC": row.amount_usdc,
        "status": row.status,
        "transferRef": row.transfer_ref,
        "steps": row.steps,
        "txHashes": row.tx_hashes,
        "explorerUrls": row.explorer_urls,
        "error": row.error,
        "bridgeResult": row.bridge_result,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


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


async def _forward_to_provider(
    agent: Any,
    tool: Any,
    body: InvokeBody,
    *,
    buyer_id: int | None,
    billing_breakdown: list[dict[str, Any]],
) -> dict[str, Any]:
    endpoint_url = tool.endpoint_url or agent.endpoint_url
    payload = {
        "prompt": body.prompt,
        "buyerId": buyer_id,
        "selectedSkills": body.selectedSkills,
        "usageUnits": body.usageUnits,
        "billing": billing_breakdown,
        "marketplace": {
            "agentId": agent.id,
            "toolId": tool.id,
            "toolKey": tool.tool_key,
            "arcAgentId": agent.arc_agent_id,
            "network": "arcTestnet",
        },
    }
    method = _normalize_http_method(tool.http_method or agent.http_method)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if method == "GET":
                provider_response = await client.get(
                    endpoint_url,
                    params={"prompt": body.prompt, "selectedSkills": ",".join(body.selectedSkills)},
                )
            else:
                provider_response = await client.request(method, endpoint_url, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Provider endpoint request failed: {exc}") from exc

    content_type = provider_response.headers.get("content-type", "")
    try:
        data: Any = provider_response.json() if "application/json" in content_type else provider_response.text
    except JSONDecodeError:
        data = provider_response.text

    if provider_response.status_code >= 400:
        preview = data if isinstance(data, str) else str(data)
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Provider endpoint returned an error",
                "providerStatus": provider_response.status_code,
                "providerPreview": preview[:500],
            },
        )

    if isinstance(data, str):
        output_text = data
    elif isinstance(data, dict):
        output_text = data.get("outputText") or data.get("result") or str(data)
    else:
        output_text = str(data)
    return {
        "statusCode": provider_response.status_code,
        "contentType": content_type,
        "data": data,
        "outputText": str(output_text),
        "endpointUrl": endpoint_url,
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


def _payment_required_response(
    *,
    db: Session,
    seller: Any,
    agent: Any,
    tool: Any,
    invoke_path: str,
    buyer_id: int | None,
    total_amount_usdc: Decimal,
    billing_breakdown: list[dict[str, Any]],
) -> JSONResponse:
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
            "price": f"{total_amount_usdc:.6f}",
            "sellerId": seller.id,
            "agentId": agent.id,
            "toolId": tool.id,
            "buyerId": buyer_id,
            "billingBreakdown": billing_breakdown,
            "message": "buyerId is required for custodial on-chain settlement",
        },
    )
    return JSONResponse(
        status_code=402,
        content={
            "message": "Payment required",
            "required": {
                "buyerId": "Provide a registered buyerId so the platform can settle USDC on Arc.",
                "totalUSDC": f"{total_amount_usdc:.6f}",
                "billingBreakdown": billing_breakdown,
            },
            "x402": {
                "supported": True,
                "note": "x402 is retained for compatibility, but Arc on-chain settlement is the source of truth.",
            },
        },
    )


def _settle_onchain_payment(
    db: Session,
    *,
    seller: Any,
    buyer: Any,
    agent: Any,
    tool: Any,
    invoke_path: str,
    total_amount_usdc: Decimal,
    billing_breakdown: list[dict[str, Any]],
) -> tuple[PaymentEvent, dict[str, Any]]:
    if buyer.owner_wallet_id:
        payment = transfer_usdc(
            wallet_id=buyer.owner_wallet_id,
            wallet_address=buyer.wallet_address,
            destination_address=seller.owner_wallet_address,
            amount_usdc=total_amount_usdc,
            ref_id=f"agent-{agent.id}-tool-{tool.id}",
        )
    else:
        private_key = _lookup_private_key_for_address(buyer.wallet_address)
        if not private_key:
            raise RuntimeError(
                "Buyer wallet is not Circle-managed and no matching local private key is configured for direct settlement."
            )
        payment = transfer_usdc_from_private_key(
            private_key=private_key,
            source_wallet_address=buyer.wallet_address,
            destination_address=seller.owner_wallet_address,
            amount_usdc=total_amount_usdc,
            ref_id=f"agent-{agent.id}-tool-{tool.id}",
        )
    event = create_payment_event(
        db,
        seller_id=seller.id,
        agent_id=agent.id,
        tool_id=tool.id,
        event_type="payment",
        status="paid",
        buyer_address=buyer.wallet_address,
        transaction_ref=payment.tx_hash,
        amount_usdc=float(total_amount_usdc),
        details={
            "path": invoke_path,
            "payer": buyer.wallet_address,
            "payee": seller.owner_wallet_address,
            "amountUSDC": f"{total_amount_usdc:.6f}",
            "onchainTxHash": payment.tx_hash,
            "circleTransactionId": payment.tx_id,
            "billingBreakdown": billing_breakdown,
            "sellerId": seller.id,
            "agentId": agent.id,
            "toolId": tool.id,
            "buyerId": buyer.id,
        },
    )
    return event, {
        "amountUSDC": f"{total_amount_usdc:.6f}",
        "onchainTxHash": payment.tx_hash,
        "circleTransactionId": payment.tx_id,
        "payer": buyer.wallet_address,
        "payee": seller.owner_wallet_address,
    }


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
        if entry["lastTransaction"] is None:
            onchain_tx_hash = _event_onchain_tx_hash(event)
            if onchain_tx_hash:
                entry["lastTransaction"] = onchain_tx_hash
            elif event.transaction_ref:
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


def _classify_transaction_ref(transaction_ref: str | None) -> dict[str, str | None]:
    normalized = (transaction_ref or "").strip()
    if not normalized:
        return {
            "referenceType": "none",
            "gatewayReference": None,
            "onchainTxHash": None,
        }
    if ONCHAIN_TX_HASH_RE.fullmatch(normalized):
        if not normalized.startswith("0x"):
            normalized = f"0x{normalized.lower()}"
        return {
            "referenceType": "onchain",
            "gatewayReference": None,
            "onchainTxHash": normalized,
        }
    return {
        "referenceType": "gateway_reference",
        "gatewayReference": normalized,
        "onchainTxHash": None,
    }


def _event_onchain_tx_hash(event: PaymentEvent) -> str | None:
    details = event.details if isinstance(event.details, dict) else {}
    candidate = details.get("onchainTxHash") if isinstance(details, dict) else None
    if isinstance(candidate, str) and ONCHAIN_TX_HASH_RE.fullmatch(candidate.strip()):
        normalized = candidate.strip()
        return normalized if normalized.startswith("0x") else f"0x{normalized.lower()}"
    if event.transaction_ref and ONCHAIN_TX_HASH_RE.fullmatch(event.transaction_ref.strip()):
        normalized = event.transaction_ref.strip()
        return normalized if normalized.startswith("0x") else f"0x{normalized.lower()}"
    return None


def _serialize_payment_event(event: PaymentEvent) -> dict[str, Any]:
    details = event.details if isinstance(event.details, dict) else {}
    explicit_onchain_tx_hash = _event_onchain_tx_hash(event)
    ref_info = (
        {
            "referenceType": "onchain",
            "gatewayReference": None,
            "onchainTxHash": explicit_onchain_tx_hash,
        }
        if explicit_onchain_tx_hash
        else _classify_transaction_ref(event.transaction_ref)
    )
    return {
        "timestamp": event.created_at.isoformat(),
        "eventType": event.event_type,
        "status": event.status,
        "transactionRef": event.transaction_ref,
        "referenceType": ref_info["referenceType"],
        "gatewayReference": ref_info["gatewayReference"],
        "onchainTxHash": ref_info["onchainTxHash"],
        "details": details,
    }


def _transactions_html(payload: dict[str, Any]) -> str:
    event_rows = []
    for event in payload["events"]:
        details = html.escape(str(event["details"]))
        reference = event["gatewayReference"] or event["onchainTxHash"] or ""
        reference_html = html.escape(str(reference))
        if event["referenceType"] == "onchain" and event["onchainTxHash"]:
            reference_html = (
                f'<a href="{html.escape(ARCSCAN_TX_URL + str(event["onchainTxHash"]))}" '
                'target="_blank" rel="noreferrer">'
                f"{reference_html}</a>"
            )
        event_rows.append(
            "<tr>"
            f"<td>{html.escape(event['timestamp'])}</td>"
            f"<td>{html.escape(event['eventType'])}</td>"
            f"<td>{html.escape(event['status'])}</td>"
            f"<td>{html.escape(str(event['referenceType']))}</td>"
            f"<td>{reference_html}</td>"
            f"<td><pre>{details}</pre></td>"
            "</tr>"
        )
    buyer_rows = []
    for buyer in payload["buyers"]:
        buyer_rows.append(
            "<tr>"
            f"<td>{html.escape(str(buyer['buyerAddress']))}</td>"
            f"<td>{html.escape(str(buyer['paymentsCount']))}</td>"
            f"<td>{html.escape(str(buyer['totalAmountUSDC']))}</td>"
            f"<td>{html.escape(str(buyer['lastTransaction'] or ''))}</td>"
            "</tr>"
        )

    summary = payload["summary"]
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Arc Marketplace Transactions</title>
    <style>
      body {{ background: #0b0b0c; color: #e4e4e7; font-family: Inter, ui-sans-serif, system-ui, sans-serif; margin: 0; }}
      main {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 48px; }}
      h1, h2 {{ margin: 0 0 16px; }}
      p, li {{ color: #a1a1aa; }}
      a {{ color: #60a5fa; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      .grid {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin: 20px 0 28px; }}
      .metric {{ border: 1px solid #27272a; border-radius: 12px; padding: 14px; background: #111113; }}
      .metric .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #71717a; }}
      .metric .value {{ margin-top: 8px; font-size: 24px; font-weight: 600; color: #fafafa; }}
      .panel {{ border: 1px solid #27272a; border-radius: 14px; background: #111113; overflow: hidden; margin-top: 18px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ padding: 12px 14px; text-align: left; vertical-align: top; border-top: 1px solid #27272a; font-size: 13px; }}
      th {{ color: #a1a1aa; background: #0f0f10; font-weight: 600; border-top: none; }}
      pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; color: #d4d4d8; }}
      code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
      .note {{ border-left: 3px solid #3b82f6; padding-left: 12px; margin: 16px 0 0; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Arc Marketplace Transactions</h1>
      <p>This page shows live payment events from the local backend. Values marked <code>onchain</code> are real Arc transaction hashes and link to Arcscan.</p>
      <div class="grid">
        <div class="metric"><div class="label">Events</div><div class="value">{summary['total']}</div></div>
        <div class="metric"><div class="label">Paid</div><div class="value">{summary['paid']}</div></div>
        <div class="metric"><div class="label">Payment Required</div><div class="value">{summary['paymentRequired']}</div></div>
        <div class="metric"><div class="label">Total Paid USDC</div><div class="value">{summary['totalPaidAmountUSDC']}</div></div>
        <div class="metric"><div class="label">Unique Buyers</div><div class="value">{summary['uniqueBuyers']}</div></div>
      </div>
      <p class="note">Legacy rows may still show <code>gateway_reference</code> from the older x402-only flow. New on-chain settlement rows are labeled <code>onchain</code> and carry the actual transfer hash.</p>
      <section class="panel">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Event</th>
              <th>Status</th>
              <th>Reference Type</th>
              <th>Reference</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {''.join(event_rows) if event_rows else '<tr><td colspan="6">No events recorded.</td></tr>'}
          </tbody>
        </table>
      </section>
      <section class="panel">
        <table>
          <thead>
            <tr>
              <th>Buyer</th>
              <th>Payments</th>
              <th>Total Paid USDC</th>
              <th>Last Reference</th>
            </tr>
          </thead>
          <tbody>
            {''.join(buyer_rows) if buyer_rows else '<tr><td colspan="4">No buyers recorded.</td></tr>'}
          </tbody>
        </table>
      </section>
    </main>
  </body>
</html>"""


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
        "mode": "provider-proxy",
        "message": "Arc marketplace with ERC-8004 registered provider APIs and x402 paid invocation.",
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
    if not body.walletAddress.strip():
        _ensure_buyer_arc_wallets(buyer, db)
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
        "balances": _wallet_balances_payload(wallet_id=buyer.owner_wallet_id, wallet_address=buyer.wallet_address),
        "invocations": [
            {
                "id": i.id,
                "sellerId": i.seller_id,
                "agentId": i.agent_id,
                "toolId": i.tool_id,
                "amountUSDC": i.amount_usdc,
                "onchainTxHash": i.transaction_ref,
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
    _ensure_buyer_arc_wallets(buyer, db)
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


@app.get("/buyers/{buyer_id}/balances")
async def buyer_balances(buyer_id: int, db: Session = Depends(get_db)):
    buyer = get_buyer(db, buyer_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found")
    _ensure_buyer_arc_wallets(buyer, db)
    return {"balances": _wallet_balances_payload(wallet_id=buyer.owner_wallet_id, wallet_address=buyer.wallet_address)}


@app.post("/external-buyers")
async def create_external_buyer_endpoint(body: ExternalBuyerCreateBody, db: Session = Depends(get_db)):
    buyer = create_buyer(
        db,
        name=body.name,
        organization=body.organization,
        description=body.description,
        wallet_address="",
        validator_wallet_address="",
    )
    _ensure_buyer_arc_wallets(buyer, db)
    return {
        "buyer": _buyer_api_payload(buyer),
        "funding": {
            **_funding_metadata(),
            "destinationAddress": buyer.wallet_address,
            "destinationChain": ARC_SETTLEMENT_CHAIN,
        },
    }


@app.post("/external-buyers/{buyer_id}/funding/estimate")
async def estimate_external_buyer_funding(
    buyer_id: int,
    body: ExternalFundingBody,
    db: Session = Depends(get_db),
):
    buyer = get_buyer(db, buyer_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found")
    _ensure_buyer_arc_wallets(buyer, db)
    source_chain = _normalize_source_chain(body.sourceChain)
    amount_usdc = _normalize_funding_amount(body.amountUSDC)
    transfer_speed = _normalize_transfer_speed(body.transferSpeed)
    estimate = await run_in_threadpool(
        _run_bridge_worker,
        "estimate",
        {
            "sourceChain": source_chain,
            "destinationChain": ARC_SETTLEMENT_CHAIN,
            "destinationAddress": buyer.wallet_address,
            "amountUSDC": amount_usdc,
            "transferSpeed": transfer_speed,
        },
    )
    return {
        "buyer": _buyer_api_payload(buyer),
        "estimate": estimate,
        "funding": {
            **_funding_metadata(),
            "destinationAddress": buyer.wallet_address,
            "destinationChain": ARC_SETTLEMENT_CHAIN,
        },
    }


@app.post("/external-buyers/{buyer_id}/funding/bridge")
async def bridge_external_buyer_funding(
    buyer_id: int,
    body: ExternalFundingBody,
    db: Session = Depends(get_db),
):
    buyer = get_buyer(db, buyer_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found")
    _ensure_buyer_arc_wallets(buyer, db)
    source_chain = _normalize_source_chain(body.sourceChain)
    amount_usdc = _normalize_funding_amount(body.amountUSDC)
    transfer_speed = _normalize_transfer_speed(body.transferSpeed)
    transfer_ref = f"external_bridge_{uuid.uuid4().hex[:16]}"
    result = await run_in_threadpool(
        _run_bridge_worker,
        "bridge",
        {
            "sourceChain": source_chain,
            "destinationChain": ARC_SETTLEMENT_CHAIN,
            "destinationAddress": buyer.wallet_address,
            "amountUSDC": amount_usdc,
            "transferSpeed": transfer_speed,
            "transferRef": transfer_ref,
        },
    )
    bridge_result = result.get("bridgeResult") if isinstance(result.get("bridgeResult"), dict) else result
    status = str(bridge_result.get("state") or result.get("status") or "pending")
    error = str(result.get("error") or bridge_result.get("error") or "")
    row = create_external_funding_attempt(
        db,
        buyer_id=buyer.id,
        source_chain=source_chain,
        destination_chain=ARC_SETTLEMENT_CHAIN,
        amount_usdc=amount_usdc,
        status=status,
        transfer_ref=transfer_ref,
        bridge_result=bridge_result,
        steps=bridge_result.get("steps") if isinstance(bridge_result.get("steps"), list) else [],
        tx_hashes=_bridge_step_strings(bridge_result, "txHash"),
        explorer_urls=_bridge_step_strings(bridge_result, "explorerUrl"),
        error=error,
    )
    return {"fundingTransfer": _external_funding_payload(row), "buyer": _buyer_api_payload(buyer)}


@app.get("/external-buyers/{buyer_id}/funding/{transfer_id}")
async def get_external_buyer_funding(
    buyer_id: int,
    transfer_id: int,
    db: Session = Depends(get_db),
):
    row = get_external_funding_attempt(db, buyer_id=buyer_id, transfer_id=transfer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Funding transfer not found")
    return {"fundingTransfer": _external_funding_payload(row)}


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
    return {
        "seller": _seller_api_payload(seller),
        "balances": _wallet_balances_payload(wallet_id=seller.owner_wallet_id, wallet_address=seller.owner_wallet_address),
        "agents": [
            {
                **_agent_api_payload(a),
                "tools": [_tool_api_payload(tool, db, fallback_agent=a) for tool in a.tools],
            }
            for a in agents
        ],
    }


@app.post("/sellers/{seller_id}/agents")
async def create_agent_endpoint(seller_id: int, body: AgentCreateBody, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    capabilities = _build_capabilities_payload(body)
    endpoint_url = capabilities[0]["endpointUrl"]
    api_docs_url = _validate_http_url(body.apiDocsUrl, field_name="apiDocsUrl") if body.apiDocsUrl.strip() else ""
    http_method = capabilities[0]["httpMethod"]
    _ensure_seller_arc_wallets(seller, db)
    try:
        registration = register_agent_identity(
            metadata_uri=body.metadataUri or endpoint_url,
            owner_wallet_id=seller.owner_wallet_id,
            validator_wallet_id=seller.validator_wallet_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Arc ERC-8004 registration failed: {exc}") from exc

    seller.owner_wallet_id = registration.owner_wallet_id
    seller.validator_wallet_id = registration.validator_wallet_id
    seller.owner_wallet_address = registration.owner_wallet_address
    seller.validator_wallet_address = registration.validator_wallet_address
    agent = create_agent(
        db,
        seller_id=seller_id,
        name=body.name,
        description=body.description,
        metadata_uri=body.metadataUri,
        icon_data_url=body.iconDataUrl,
        category=body.category.strip(),
        endpoint_url=endpoint_url,
        http_method=http_method,
        api_docs_url=api_docs_url,
        price_usdc=body.priceUSDC,
        capabilities=capabilities,
    )
    agent.arc_agent_id = registration.agent_id
    agent.identity_tx_hash = registration.tx_hash
    agent.status = "registered"
    db.commit()
    db.refresh(agent)
    db.refresh(seller)
    return {
        "agent": {
            **_agent_api_payload(agent),
            "tools": [_tool_api_payload(tool, db, fallback_agent=agent) for tool in agent.tools],
        },
        "seller": _seller_api_payload(seller),
        "arc": {"txHash": registration.tx_hash, "agentId": registration.agent_id},
    }


@app.patch("/sellers/{seller_id}/agents/{agent_id}/pricing")
async def update_agent_pricing_endpoint(
    seller_id: int,
    agent_id: int,
    body: AgentPricingUpdateBody,
    db: Session = Depends(get_db),
):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    agent = get_agent(db, agent_id)
    if agent is None or agent.seller_id != seller_id:
        raise HTTPException(status_code=404, detail="Agent not found for seller")

    updated_count = update_agent_tool_prices(
        db,
        seller_id=seller_id,
        agent_id=agent_id,
        base_price_usdc=body.basePriceUSDC,
    )
    if updated_count == 0:
        raise HTTPException(status_code=404, detail="No tools found for agent")

    return {
        "sellerId": seller_id,
        "agentId": agent_id,
        "basePriceUSDC": body.basePriceUSDC,
        "updatedTools": updated_count,
    }


@app.patch("/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/pricing")
async def update_tool_pricing_endpoint(
    seller_id: int,
    agent_id: int,
    tool_id: int,
    body: ToolPricingUpdateBody,
    db: Session = Depends(get_db),
):
    tool = update_tool_pricing(
        db,
        seller_id=seller_id,
        agent_id=agent_id,
        tool_id=tool_id,
        tool_price_usdc=body.toolPriceUSDC,
        runtime_price_usdc=body.runtimePriceUSDC,
        skill_prices=body.skillPrices,
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found for agent")
    agent = get_agent(db, agent_id)
    return {"tool": _tool_api_payload(tool, db, fallback_agent=agent)}


@app.get("/sellers/{seller_id}/balances")
async def seller_balances(seller_id: int, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    _ensure_seller_arc_wallets(seller, db)
    return {"balances": _wallet_balances_payload(wallet_id=seller.owner_wallet_id, wallet_address=seller.owner_wallet_address)}


@app.get("/marketplace/tools")
async def marketplace_tools(db: Session = Depends(get_db)):
    return {"tools": [_with_funding_metadata(tool) for tool in list_tools_for_marketplace(db)]}


@app.get("/marketplace/agents")
async def marketplace_agents(db: Session = Depends(get_db)):
    agents = []
    for agent in list_agents_for_marketplace(db):
        enriched = _with_funding_metadata(agent)
        enriched["commerce"] = {**agent.get("commerce", {}), **_funding_metadata()}
        enriched["tools"] = [_with_funding_metadata(tool) for tool in agent.get("tools", [])]
        agents.append(enriched)
    return {"agents": agents}


@app.post("/marketplace/discover")
async def marketplace_discover(body: DiscoverBody, db: Session = Depends(get_db)):
    tools = [_with_funding_metadata(tool) for tool in list_tools_for_marketplace(db)]
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
                "tags": [
                    tool["toolKey"],
                    tool.get("category", tool["agent"].get("category", "General")),
                    "arc-usdc",
                    "arc-testnet",
                    "marketplace",
                    tool["seller"]["name"],
                ],
                "examples": [f"Use {tool['name']} for: summarize trading strategy risks."],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "x402PriceUSDC": tool["priceUSDC"],
                "x402Network": "arcTestnet",
                "paymentProtocol": "arc-usdc",
                "settlementNetwork": ARC_SETTLEMENT_CHAIN,
                "settlementChainId": ARC_SETTLEMENT_CHAIN_ID,
                "asset": "USDC",
                "assetDecimals": ARC_USDC_DECIMALS,
                "acceptedFundingRails": [FUNDING_RAIL],
                "acceptedSourceChains": list(SUPPORTED_FUNDING_SOURCE_CHAINS),
                "fundingEstimateUrl": f"{_public_base_url()}/external-buyers/{{buyerId}}/funding/estimate",
                "fundingBridgeUrl": f"{_public_base_url()}/external-buyers/{{buyerId}}/funding/bridge",
                "requiresBuyerArcRegistration": False,
                "category": tool.get("category", tool["agent"].get("category", "General")),
                "providerEndpointHost": (
                    urlparse(tool.get("endpointUrl", tool["agent"].get("endpointUrl", ""))).netloc
                    if tool.get("endpointUrl", tool["agent"].get("endpointUrl"))
                    else ""
                ),
                "billableSkills": tool.get("skills", []),
                "runtimePriceUSDC": tool.get("runtimePriceUSDC", 0),
                "arcAgentId": tool["agent"].get("arcAgentId"),
                "metadataUri": tool["agent"].get("metadataUri", ""),
                "path": f"/sellers/{tool['seller']['id']}/agents/{tool['agent']['id']}/tools/{tool['toolId']}/invoke",
            }
        )
    return {
        "name": "Arc Marketplace Agent",
        "description": "Multi-seller Arc marketplace for autonomous agent service discovery and real on-chain USDC invocation settlement.",
        "url": _public_base_url(),
        "provider": {"organization": "Agents Market", "url": _public_base_url()},
        "version": "0.1.0",
        "documentationUrl": f"{_public_base_url()}/docs",
        "capabilities": {"streaming": False, "stateHistory": True},
        "authentication": {
            "type": "buyer-id-or-x402",
            "instructions": "Preferred: send buyerId for custodial on-chain settlement. x402 headers remain compatibility-only.",
        },
        "payment": _funding_metadata(),
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
    buyer = None
    if buyer_id is not None:
        buyer = get_buyer(db, buyer_id)
        if buyer is None:
            raise HTTPException(status_code=404, detail="Buyer not found")
        _ensure_buyer_arc_wallets(buyer, db)

    invoke_path = f"/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke"
    total_amount_usdc, billing_breakdown, matched_skills = _pricing_breakdown(
        tool,
        body.selectedSkills,
        db=db,
    )
    if buyer is None:
        payment_header = request.headers.get("Payment-Signature")
        if payment_header:
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
            raise HTTPException(
                status_code=400,
                detail="x402-only invokes are no longer the settlement source of truth; provide buyerId for on-chain settlement",
            )
        return _payment_required_response(
            db=db,
            seller=seller,
            agent=agent,
            tool=tool,
            invoke_path=invoke_path,
            buyer_id=buyer_id,
            total_amount_usdc=total_amount_usdc,
            billing_breakdown=billing_breakdown,
        )

    try:
        payment_event, settled_payment = _settle_onchain_payment(
            db,
            seller=seller,
            buyer=buyer,
            agent=agent,
            tool=tool,
            invoke_path=invoke_path,
            total_amount_usdc=total_amount_usdc,
            billing_breakdown=billing_breakdown,
        )
    except Exception as exc:
        create_payment_event(
            db,
            seller_id=seller.id,
            agent_id=agent.id,
            tool_id=tool.id,
            event_type="payment",
            status="failed",
            buyer_address=buyer.wallet_address,
            transaction_ref=None,
            amount_usdc=float(total_amount_usdc),
            details={
                "path": invoke_path,
                "amountUSDC": f"{total_amount_usdc:.6f}",
                "buyerId": buyer.id,
                "error": str(exc),
                "billingBreakdown": billing_breakdown,
            },
        )
        raise HTTPException(status_code=402, detail=f"On-chain payment failed: {exc}") from exc

    provider_result = await _forward_to_provider(
        agent,
        tool,
        body,
        buyer_id=buyer_id,
        billing_breakdown=billing_breakdown,
    )
    create_payment_event(
        db,
        seller_id=seller.id,
        agent_id=agent.id,
        tool_id=tool.id,
        event_type="seller_output",
        status="completed",
        buyer_address=buyer.wallet_address,
        transaction_ref=settled_payment["onchainTxHash"],
        amount_usdc=0,
        details={
            "path": invoke_path,
            "promptPreview": body.prompt[:120],
            "responsePreview": provider_result["outputText"][:160],
            "providerEndpointHost": urlparse(provider_result["endpointUrl"]).netloc,
            "providerStatusCode": provider_result["statusCode"],
            "onchainTxHash": settled_payment["onchainTxHash"],
            "billingBreakdown": billing_breakdown,
            "selectedSkills": [skill.skill_key for skill in matched_skills],
            "buyerId": buyer_id,
        },
    )
    invocation = create_buyer_invocation(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        agent_id=agent.id,
        tool_id=tool.id,
        payment_event_id=payment_event.id,
        prompt=body.prompt,
        output_preview=provider_result["outputText"][:300],
        amount_usdc=float(total_amount_usdc),
        transaction_ref=settled_payment["onchainTxHash"],
        status="completed",
    )
    create_usage_records(
        db,
        buyer_invocation_id=invocation.id,
        payment_event_id=payment_event.id,
        tool_id=tool.id,
        usage_components=billing_breakdown,
    )

    response_body = {
        "sellerId": seller.id,
        "agentId": agent.id,
        "toolId": tool.id,
        "toolKey": tool.tool_key,
        "prompt": body.prompt,
        "outputText": provider_result["outputText"],
        "providerResponse": provider_result["data"],
        "payment": {
            "amountUSDC": settled_payment["amountUSDC"],
            "payer": settled_payment["payer"],
            "payee": settled_payment["payee"],
            "onchainTxHash": settled_payment["onchainTxHash"],
            "circleTransactionId": settled_payment["circleTransactionId"],
            "billingBreakdown": billing_breakdown,
        },
        "provider": {
            "endpointHost": urlparse(provider_result["endpointUrl"]).netloc,
            "statusCode": provider_result["statusCode"],
            "contentType": provider_result["contentType"],
        },
        "balances": {
            "buyer": _wallet_balances_payload(wallet_id=buyer.owner_wallet_id, wallet_address=buyer.wallet_address),
            "seller": _wallet_balances_payload(
                wallet_id=seller.owner_wallet_id,
                wallet_address=seller.owner_wallet_address,
            ),
        },
    }
    return JSONResponse(content=response_body)


@app.get("/transactions")
async def transactions(request: Request, db: Session = Depends(get_db)):
    events = list_payment_events(db)
    payload = {
        "events": [_serialize_payment_event(e) for e in events],
        "summary": payment_summary(db),
        "buyers": _buyer_breakdown(events),
    }
    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept:
        return HTMLResponse(_transactions_html(payload))
    return payload


@app.get("/transactions/view", response_class=HTMLResponse)
async def transactions_view(db: Session = Depends(get_db)):
    payload = {
        "events": [_serialize_payment_event(e) for e in list_payment_events(db)],
        "summary": payment_summary(db),
        "buyers": _buyer_breakdown(list_payment_events(db)),
    }
    return HTMLResponse(_transactions_html(payload))


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
    private_key = _shared_demo_treasury_private_key()

    async with GatewayClient(chain=DEMO_TREASURY_CHAIN, private_key=private_key) as gateway:
        result = await gateway.deposit(body.amount)
        balances = await gateway.get_balances()
        account = upsert_gateway_account(
            db,
            seller_id=seller.id,
            chain=DEMO_TREASURY_CHAIN,
            wallet_address=gateway.address,
            wallet_balance_usdc=float(balances.wallet.formatted),
            gateway_available_usdc=float(balances.gateway.formatted_available),
        )
    return {
        "gateway": _demo_treasury_gateway_payload(
            account=account,
            seller=seller,
            treasury_wallet_address=account.wallet_address,
            wallet_balance_usdc=account.wallet_balance_usdc,
            gateway_available_usdc=account.gateway_available_usdc,
            deposit_tx_hash=result.deposit_tx_hash,
        )
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

    wallets_payload = _create_seller_wallets(seller, wallet_set_name=body.walletSetName)
    db.commit()
    db.refresh(seller)
    return {
        "seller": _seller_api_payload(seller),
        "wallets": {
            "custodyModel": "circle_developer_controlled_shared_account",
            "note": "Created under the platform Circle developer account for this hackathon demo.",
            **wallets_payload,
        },
    }


@app.get("/sellers/{seller_id}/gateway/balances")
async def gateway_balances(seller_id: int, db: Session = Depends(get_db)):
    seller = get_seller(db, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Seller not found")
    private_key = _shared_demo_treasury_private_key()

    async with GatewayClient(chain=DEMO_TREASURY_CHAIN, private_key=private_key) as gateway:
        balances = await gateway.get_balances()
        account = upsert_gateway_account(
            db,
            seller_id=seller.id,
            chain=DEMO_TREASURY_CHAIN,
            wallet_address=gateway.address,
            wallet_balance_usdc=float(balances.wallet.formatted),
            gateway_available_usdc=float(balances.gateway.formatted_available),
        )
    return {
        "gateway": _demo_treasury_gateway_payload(
            account=account,
            seller=seller,
            treasury_wallet_address=account.wallet_address,
            wallet_balance_usdc=account.wallet_balance_usdc,
            gateway_available_usdc=account.gateway_available_usdc,
        )
    }


@app.get("/gateway/demo-treasury/balances")
async def demo_treasury_balances():
    private_key = _shared_demo_treasury_private_key()
    async with GatewayClient(chain=DEMO_TREASURY_CHAIN, private_key=private_key) as gateway:
        balances = await gateway.get_balances()
        return {
            "gateway": _demo_treasury_gateway_payload(
                treasury_wallet_address=gateway.address,
                wallet_balance_usdc=float(balances.wallet.formatted),
                gateway_available_usdc=float(balances.gateway.formatted_available),
            )
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
