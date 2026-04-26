#!/usr/bin/env python3
"""Continuous buyerId invokes (real Arc testnet USDC) across seeded demo tools.

Run from backend/:  uv run python ../examples/agent_trading_demo/buyer_trader.py

Environment:
  SERVER_URL           Marketplace base URL (default http://localhost:4021)
  TRADER_BUDGET_USDC   Total USDC budget for the session (default 0.05)
  TRADER_LOOP_SECONDS  Sleep between successful trades (default 12)
  BUYER_ID             Optional existing buyer id
  BUYER_NAME           Buyer display name when creating a new buyer
  AGENT_NAME_PREFIX     If set, only tools whose agent name starts with this (overrides prefixes list).
  AGENT_NAME_PREFIXES   Comma-separated prefixes (default: all demo seed agents).
  TRADER_MAX_TRADES     Stop after this many successful invokes (default: unlimited).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

from agents_market._env import load_backend_env
from agents_market.arc.buyer.sdk import BuyerMarketplaceSDK, ToolCandidate

load_backend_env()

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
LOOP_SECONDS = float(os.getenv("TRADER_LOOP_SECONDS", "12"))
BUDGET = Decimal(os.getenv("TRADER_BUDGET_USDC", "0.05"))
BUYER_ID_RAW = os.getenv("BUYER_ID", "").strip()
BUYER_NAME = os.getenv("BUYER_NAME", "Arc Trading Demo Buyer").strip()
AGENT_PREFIX_LEGACY = os.getenv("AGENT_NAME_PREFIX", "").strip()
_DEFAULT_PREFIXES = "Demo Multi-Tool,Arc Analytics,Arc Dev"
AGENT_PREFIXES_RAW = os.getenv("AGENT_NAME_PREFIXES", _DEFAULT_PREFIXES).strip()
MAX_TRADES_RAW = os.getenv("TRADER_MAX_TRADES", "").strip()
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))


def _parse_buyer_id() -> int | None:
    if not BUYER_ID_RAW or not BUYER_ID_RAW.isdigit():
        return None
    return int(BUYER_ID_RAW, 10)


def _demo_prefixes() -> list[str]:
    if AGENT_PREFIX_LEGACY:
        return [AGENT_PREFIX_LEGACY]
    return [p.strip() for p in AGENT_PREFIXES_RAW.split(",") if p.strip()]


def _filter_demo_tools(tools: list[ToolCandidate]) -> list[ToolCandidate]:
    prefixes = _demo_prefixes()
    out: list[ToolCandidate] = []
    for t in tools:
        raw = t.raw or {}
        agent = raw.get("agent") if isinstance(raw.get("agent"), dict) else {}
        name = str(agent.get("name", ""))
        if any(name.startswith(p) for p in prefixes):
            out.append(t)
    return out


def _prompt_for_tool(tool: ToolCandidate) -> str:
    key = tool.tool_key.lower()
    templates = {
        "weather": "Weather check for Arc testnet demo trade.",
        "sentiment": "Sentiment scan: the team shipped the trading demo on time.",
        "quote": "Quote request: USDC gas demo pair.",
        "planner": "Planner: three steps to validate buyerId payments on Arc.",
        "reminder": "Reminder: log tx hash after each invoke.",
        "summarize": "Summarize: what buyerId settlement does on Arc testnet.",
        "translate": "Translate: one sentence about USDC gas on Arc.",
        "news_digest": "News digest: fictional headlines for marketplace QA.",
        "code_review": "Code review: async httpx invoke loop with budget guard.",
        "task_split": "Task split: verify explorer tx after each paid invoke.",
        "json_format": "JSON format: return a tiny status object for logging.",
    }
    return templates.get(key, f"Demo invoke for tool {tool.tool_key}.")


async def run_session() -> None:
    sdk = BuyerMarketplaceSDK(
        server_url=SERVER_URL,
        buyer_id=_parse_buyer_id(),
        buyer_name=BUYER_NAME,
        timeout_seconds=TIMEOUT,
    )
    profile = await sdk.ensure_buyer()
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] buyer id={profile.id} "
        f"name={profile.name!r} wallet={profile.wallet_address!r}"
    )

    tools = await sdk.list_tools()
    demo_tools = _filter_demo_tools(tools)
    if not demo_tools:
        shown = AGENT_PREFIX_LEGACY or AGENT_PREFIXES_RAW
        print(
            f"No tools matched agent name prefix(es) {shown!r}. "
            "Run seed_demo.py or adjust AGENT_NAME_PREFIX / AGENT_NAME_PREFIXES.",
            file=sys.stderr,
        )
        sys.exit(1)

    demo_tools.sort(key=lambda x: (x.agent_id or 0, x.price_usdc, x.tool_key))
    prefix_note = AGENT_PREFIX_LEGACY or AGENT_PREFIXES_RAW
    max_trades = int(MAX_TRADES_RAW, 10) if MAX_TRADES_RAW.isdigit() else None
    print(
        f"Using {len(demo_tools)} tools across seeded agents (prefixes={prefix_note!r}), "
        f"loop every {LOOP_SECONDS}s, budget={BUDGET} USDC"
        + (f", max_trades={max_trades}" if max_trades is not None else "")
    )

    remaining = BUDGET
    index = 0
    success_count = 0
    while remaining > 0:
        if max_trades is not None and success_count >= max_trades:
            print(f"[trader] reached TRADER_MAX_TRADES={max_trades}; stopping.")
            break
        tool = demo_tools[index % len(demo_tools)]
        index += 1
        prompt = _prompt_for_tool(tool)
        if remaining < tool.price_usdc:
            print(f"[trader] remaining {remaining} < price {tool.price_usdc} for {tool.tool_key}; stopping.")
            break
        try:
            result = await sdk.invoke(
                candidate=tool,
                prompt=prompt,
                selected_skills=tool.first_skill_keys(limit=1),
                include_buyer_id=True,
            )
        except Exception as exc:  # pragma: no cover
            print(f"[trader] invoke failed: {exc}", file=sys.stderr)
            await asyncio.sleep(LOOP_SECONDS)
            continue

        pay = result.get("payment") or {}
        amount = Decimal(str(pay.get("amountUSDC", "0")))
        tx = pay.get("onchainTxHash") or pay.get("transaction") or ""
        out = str(result.get("outputText", ""))[:180]
        remaining -= amount
        success_count += 1
        aid = tool.agent_id
        print(
            f"[{datetime.now(timezone.utc).isoformat()}] agent_id={aid} tool={tool.tool_key} "
            f"paid={amount} USDC tx={tx} remaining={remaining} USDC"
        )
        print(f"  output: {out}")
        await asyncio.sleep(LOOP_SECONDS)

    print("Session finished (budget exhausted or below minimum tool price).")


def main() -> None:
    try:
        asyncio.run(run_session())
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
