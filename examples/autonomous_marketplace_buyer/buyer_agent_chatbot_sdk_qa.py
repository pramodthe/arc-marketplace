#!/usr/bin/env python3
"""QA: simulate an AI chatbot buyer agent using BuyerMarketplaceSDK.

Run from ``backend/`` (so ``agents_market`` imports resolve):

  cd backend && uv run python ../examples/autonomous_marketplace_buyer/buyer_agent_chatbot_sdk_qa.py

Env (optional):
  SERVER_URL / QA_BASE_URL — marketplace API base (default http://localhost:4021)
  BUYER_ID — reuse existing buyer (recommended for your wallet-backed buyer)
  BUYER_NAME — name when creating new buyer (if BUYER_ID unset)
  BUYER_WALLET_ADDRESS — optional; passed to POST /buyers when creating
  CHATBOT_PROMPT — user message for invoke
  CHATBOT_BUDGET_USDC — discovery budget (default 0.05)
  CHATBOT_TASK — summarize|analyze|plan|response|auto (default auto)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

# Repo root: .../agents_market (this file lives under examples/autonomous_marketplace_buyer/)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_SRC = _REPO_ROOT / "backend" / "src"
if _BACKEND_SRC.is_dir() and str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from agents_market.arc.buyer import BuyerMarketplaceSDK


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _parse_buyer_id(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        return None


async def _fetch_transactions_json(server_url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as http:
        r = await http.get(f"{server_url.rstrip('/')}/transactions")
        r.raise_for_status()
        return dict(r.json())


def _summarize_events(payload: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in (payload.get("events") or [])[:limit]:
        details = ev.get("details") if isinstance(ev.get("details"), dict) else {}
        out.append(
            {
                "timestamp": ev.get("timestamp"),
                "eventType": ev.get("eventType"),
                "status": ev.get("status"),
                "failureCode": details.get("failureCode"),
            }
        )
    return out


async def main_async(args: argparse.Namespace) -> int:
    server_url = args.server_url.rstrip("/")
    buyer_id = _parse_buyer_id(args.buyer_id) if args.buyer_id else _parse_buyer_id(_env("BUYER_ID"))

    sdk = BuyerMarketplaceSDK(
        server_url=server_url,
        buyer_id=buyer_id,
        buyer_name=args.buyer_name or _env("BUYER_NAME", "QA Chatbot Buyer"),
    )

    before = await _fetch_transactions_json(server_url)
    before_n = len(before.get("events") or [])

    budget = Decimal(str(args.budget))
    prompt = args.prompt

    candidates = await sdk.discover(
        prompt=prompt,
        budget_usdc=budget,
        desired_tool=args.task,
        max_results=args.max_results,
    )
    fallback = await sdk.list_tools()
    desired = sdk.desired_tool_from_prompt(task=args.task, prompt=prompt)
    tool, reason = sdk.pick_best(
        desired_tool=desired,
        budget_usdc=budget,
        candidates=candidates,
        fallback_tools=fallback,
    )
    if tool is None:
        print(json.dumps({"ok": False, "step": "pick", "reason": reason}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "step": "pick",
                "reason": reason,
                "invokeUrl": tool.invoke_url,
                "toolKey": tool.tool_key,
                "priceUSDC": str(tool.price_usdc),
            },
            indent=2,
        )
    )

    try:
        result = await sdk.invoke(
            candidate=tool,
            prompt=prompt,
            selected_skills=tool.first_skill_keys(limit=2),
            include_buyer_id=not args.no_buyer_id,
        )
    except httpx.HTTPStatusError as exc:
        after = await _fetch_transactions_json(server_url)
        after_n = len(after.get("events") or [])
        print(
            json.dumps(
                {
                    "ok": False,
                    "step": "invoke",
                    "httpStatus": exc.response.status_code,
                    "body": exc.response.text[:800],
                    "transactionsBefore": before_n,
                    "transactionsAfter": after_n,
                    "latestEvents": _summarize_events(after),
                },
                indent=2,
            )
        )
        return 1
    except RuntimeError as exc:
        after = await _fetch_transactions_json(server_url)
        after_n = len(after.get("events") or [])
        print(
            json.dumps(
                {
                    "ok": False,
                    "step": "invoke",
                    "error": str(exc)[:1200],
                    "transactionsBefore": before_n,
                    "transactionsAfter": after_n,
                    "latestEvents": _summarize_events(after),
                },
                indent=2,
            )
        )
        return 1

    after = await _fetch_transactions_json(server_url)
    after_n = len(after.get("events") or [])

    print(
        json.dumps(
            {
                "ok": True,
                "step": "invoke",
                "outputPreview": (result.get("outputText") or "")[:400],
                "payment": result.get("payment"),
                "transactionsBefore": before_n,
                "transactionsAfter": after_n,
                "delta": after_n - before_n,
                "latestEvents": _summarize_events(after),
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="QA chatbot buyer agent using BuyerMarketplaceSDK")
    default_url = _env("SERVER_URL") or _env("QA_BASE_URL", "http://localhost:4021")
    p.add_argument("--server-url", default=default_url, help="Marketplace base URL")
    p.add_argument("--buyer-id", default="", help="Existing buyer id (recommended)")
    p.add_argument("--buyer-name", default=_env("BUYER_NAME", "QA Chatbot Buyer"))
    p.add_argument(
        "--buyer-wallet",
        default=_env("BUYER_WALLET_ADDRESS", ""),
        help="Optional wallet when creating buyer (only if no buyer-id)",
    )
    p.add_argument("--prompt", default=_env("CHATBOT_PROMPT", "Plan a 3-day Tokyo trip under $1500."))
    p.add_argument("--budget", default=_env("CHATBOT_BUDGET_USDC", "0.05"))
    p.add_argument("--task", default=_env("CHATBOT_TASK", "auto"))
    p.add_argument("--max-results", type=int, default=5)
    p.add_argument(
        "--no-buyer-id",
        action="store_true",
        help="Invoke without buyerId (hits x402 path; SDK does not sign x402)",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    # Optional: create buyer with wallet if no buyer id (SDK default creates empty wallet)
    if not args.buyer_id.strip() and args.buyer_wallet.strip():

        async def _create() -> int:
            async with httpx.AsyncClient(timeout=30.0) as http:
                r = await http.post(
                    f"{args.server_url.rstrip('/')}/buyers",
                    json={
                        "name": args.buyer_name,
                        "organization": "QA",
                        "description": "Chatbot buyer QA",
                        "walletAddress": args.buyer_wallet.strip(),
                        "validatorWalletAddress": "",
                    },
                )
                r.raise_for_status()
                return int(r.json()["buyer"]["id"])

        buyer_id = asyncio.run(_create())
        args.buyer_id = str(buyer_id)
        print(json.dumps({"ok": True, "step": "create_buyer", "buyerId": buyer_id}, indent=2))

    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
