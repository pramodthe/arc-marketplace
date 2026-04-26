#!/usr/bin/env python3
"""Register one seller + several marketplace agents for the trading demo.

Run from backend/:  uv run python ../examples/agent_trading_demo/seed_demo.py

Environment:
  SERVER_URL          Marketplace base URL (default http://localhost:4021)
  PROVIDER_BASE_URL   Provider hub origin (default http://127.0.0.1:9090)
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx


def _cap(provider: str, tool_key: str, **kwargs: Any) -> dict[str, Any]:
    row = {
        "toolKey": tool_key,
        "endpointUrl": f"{provider}/tools/{tool_key}",
        "httpMethod": "POST",
        **kwargs,
    }
    return row


def _agent_specs(provider: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "Demo Multi-Tool Hub",
            "description": "Five low-cost demo tools behind one Arc-registered listing for trading-loop demos.",
            "category": "Demo",
            "capabilities": [
                _cap(
                    provider,
                    "weather",
                    name="Weather stub",
                    description="Short fictional weather-style lines for demo prompts.",
                    category="Utilities",
                    priceUSDC=0.001,
                ),
                _cap(
                    provider,
                    "sentiment",
                    name="Sentiment stub",
                    description="Lightweight sentiment-style summary for any text.",
                    category="Analytics",
                    priceUSDC=0.002,
                ),
                _cap(
                    provider,
                    "quote",
                    name="Quote stub",
                    description="Illustrative market-style one-liner (not real prices).",
                    category="Finance",
                    priceUSDC=0.002,
                ),
                _cap(
                    provider,
                    "planner",
                    name="Planner stub",
                    description="Step-by-step plan outline for tasks and roadmaps.",
                    category="Productivity",
                    priceUSDC=0.003,
                ),
                _cap(
                    provider,
                    "reminder",
                    name="Reminder stub",
                    description="Reminder-style confirmation for short notes.",
                    category="Utilities",
                    priceUSDC=0.001,
                ),
            ],
        },
        {
            "name": "Arc Analytics Bot",
            "description": "Summaries, faux translation, and digest-style stubs for multi-agent discovery.",
            "category": "Analytics",
            "capabilities": [
                _cap(
                    provider,
                    "summarize",
                    name="Summarize stub",
                    description="Bullet-style summary for arbitrary prompts (demo).",
                    category="Analytics",
                    priceUSDC=0.001,
                ),
                _cap(
                    provider,
                    "translate",
                    name="Translate stub",
                    description="Illustrative translation gloss (not a real translator).",
                    category="Localization",
                    priceUSDC=0.002,
                ),
                _cap(
                    provider,
                    "news_digest",
                    name="News digest stub",
                    description="Synthetic headline list for integration testing only.",
                    category="Media",
                    priceUSDC=0.002,
                ),
            ],
        },
        {
            "name": "Arc Dev Helper",
            "description": "Developer-oriented stubs: review notes, task splits, JSON-shaped replies.",
            "category": "Developer Tools",
            "capabilities": [
                _cap(
                    provider,
                    "code_review",
                    name="Code review stub",
                    description="High-level review checklist style output (demo).",
                    category="Developer Tools",
                    priceUSDC=0.002,
                ),
                _cap(
                    provider,
                    "task_split",
                    name="Task split stub",
                    description="Break a goal into ordered subtasks (demo).",
                    category="Productivity",
                    priceUSDC=0.001,
                ),
                _cap(
                    provider,
                    "json_format",
                    name="JSON format stub",
                    description="Returns a short JSON-flavored string for parser demos.",
                    category="Utilities",
                    priceUSDC=0.001,
                ),
            ],
        },
    ]


def main() -> None:
    server = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
    provider = os.getenv("PROVIDER_BASE_URL", "http://127.0.0.1:9090").rstrip("/")

    timeout = float(os.getenv("HTTP_TIMEOUT", "120"))

    with httpx.Client(timeout=timeout) as client:
        seller_resp = client.post(
            f"{server}/sellers",
            json={
                "name": "Trading Demo Seller",
                "description": "Seeded seller for examples/agent_trading_demo",
            },
        )
        if seller_resp.status_code >= 400:
            print(seller_resp.text, file=sys.stderr)
            seller_resp.raise_for_status()
        seller = seller_resp.json()["seller"]
        seller_id = int(seller["id"])
        print(f"Seller id={seller_id} name={seller.get('name')!r}\n")

        for spec in _agent_specs(provider):
            agent_body = {
                "name": spec["name"],
                "description": spec["description"],
                "category": spec["category"],
                "offeringType": "agent",
                "protocolType": "http",
                "capabilities": spec["capabilities"],
            }
            agent_resp = client.post(f"{server}/sellers/{seller_id}/agents", json=agent_body)
            if agent_resp.status_code >= 400:
                print(agent_resp.text, file=sys.stderr)
                agent_resp.raise_for_status()
            data = agent_resp.json()
            agent = data["agent"]
            agent_id = int(agent["id"])
            warnings = data.get("warnings") or []
            if warnings:
                print("Warnings from API:", warnings)

            print(f"Agent id={agent_id} name={agent.get('name')!r} status={agent.get('status')!r}")
            if data.get("arc"):
                print("Arc:", data["arc"])
            for tool in agent.get("tools") or []:
                tid = tool.get("id")
                tkey = tool.get("toolKey")
                price = tool.get("priceUSDC")
                url = tool.get("endpointUrl") or tool.get("invokeUrl") or ""
                print(f"  tool id={tid} key={tkey!r} priceUSDC={price} endpoint={url}")
            print()

    print("Next: fund buyer Arc USDC, then run buyer_trader.py (see README).")


if __name__ == "__main__":
    main()
