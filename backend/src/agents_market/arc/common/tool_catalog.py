"""Shared paid-tool catalog for seller and buyer agents (keep in sync with x402 prices)."""

from decimal import Decimal
from typing import Any

AI_TOOLS: list[dict[str, Any]] = [
    {
        "id": "summarize",
        "path": "/ai-summarize",
        "price": "$0.01",
        "usd": Decimal("0.01"),
        "description": "Short summary of the prompt (cheapest)",
    },
    {
        "id": "analyze",
        "path": "/ai-analyze",
        "price": "$0.03",
        "usd": Decimal("0.03"),
        "description": "Deeper analysis and trade-offs",
    },
    {
        "id": "plan",
        "path": "/ai-plan",
        "price": "$0.05",
        "usd": Decimal("0.05"),
        "description": "Structured plan or roadmap style output",
    },
    {
        "id": "response",
        "path": "/ai-response",
        "price": "$0.01",
        "usd": Decimal("0.01"),
        "description": "Generic LLM text (same price as summarize)",
    },
]


def tool_by_id(tool_id: str) -> dict[str, Any] | None:
    for t in AI_TOOLS:
        if t["id"] == tool_id:
            return t
    return None


def tools_for_api() -> list[dict[str, Any]]:
    """Strip Decimal for JSON."""
    return [
        {"id": t["id"], "path": t["path"], "price": t["price"], "description": t["description"]}
        for t in AI_TOOLS
    ]
