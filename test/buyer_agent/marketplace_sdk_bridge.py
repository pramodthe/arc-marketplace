"""Helpers to use BuyerMarketplaceSDK from the test buyer chatbot."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from agents_market.arc.buyer.sdk import BuyerMarketplaceSDK, ToolCandidate


def _buyer_sdk(
    *,
    server_url: str,
    buyer_id: str,
    buyer_name: str,
    timeout_seconds: float,
) -> BuyerMarketplaceSDK:
    bid = int(buyer_id) if buyer_id.strip().isdigit() else None
    return BuyerMarketplaceSDK(
        server_url=server_url,
        buyer_id=bid,
        buyer_name=buyer_name,
        timeout_seconds=timeout_seconds,
    )


def tool_candidate_to_service_row(candidate: ToolCandidate) -> dict[str, Any]:
    """Shape expected by chatbot purchase loop (invokeUrl, priceUSDC, seller/agent/toolId, etc.)."""
    row: dict[str, Any] = dict(candidate.raw) if isinstance(candidate.raw, dict) else {}
    row["invokeUrl"] = candidate.invoke_url
    row["priceUSDC"] = float(candidate.price_usdc)
    row["toolKey"] = candidate.tool_key
    row["source"] = candidate.source
    return row


def is_marketplace_invoke_url(server_url: str, invoke_url: str) -> bool:
    """True if invoke targets this marketplace seller API (buyerId / SDK path)."""
    if not invoke_url:
        return False
    base = urlparse(server_url.rstrip("/"))
    absolute = invoke_url if invoke_url.startswith("http") else f"{server_url.rstrip('/')}/{invoke_url.lstrip('/')}"
    parsed = urlparse(absolute)
    if parsed.netloc != base.netloc or parsed.scheme != base.scheme:
        return False
    path = parsed.path or ""
    return "/sellers/" in path and "/tools/" in path and path.rstrip("/").endswith("/invoke")


async def discover_marketplace_rows(
    *,
    server_url: str,
    buyer_id: str,
    buyer_name: str,
    timeout_seconds: float,
    prompt: str,
    budget_usdc: Decimal,
) -> list[dict[str, Any]]:
    sdk = _buyer_sdk(
        server_url=server_url,
        buyer_id=buyer_id,
        buyer_name=buyer_name,
        timeout_seconds=timeout_seconds,
    )
    candidates = await sdk.discover(
        prompt=prompt,
        budget_usdc=budget_usdc,
        desired_tool="auto",
        max_results=8,
    )
    return [tool_candidate_to_service_row(c) for c in candidates]


async def buy_marketplace_via_sdk(
    *,
    server_url: str,
    buyer_id: str,
    buyer_name: str,
    timeout_seconds: float,
    payment_mode: str,
    service_row: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    sdk = _buyer_sdk(
        server_url=server_url,
        buyer_id=buyer_id,
        buyer_name=buyer_name,
        timeout_seconds=timeout_seconds,
    )
    candidate = sdk.candidate_from_tool_dict(service_row)
    payload = await sdk.invoke(
        candidate=candidate,
        prompt=prompt,
        selected_skills=candidate.first_skill_keys(limit=1),
        include_buyer_id=True,
    )
    if payment_mode == "onchain":
        return {
            "paymentMode": "onchain",
            "transactionRef": str(payload.get("payment", {}).get("onchainTxHash", "")),
            "amountUSDC": str(payload.get("payment", {}).get("amountUSDC", "")),
            "responseData": payload,
        }
    return {
        "paymentMode": "simulate",
        "transactionRef": "",
        "amountUSDC": "",
        "responseData": payload,
    }
