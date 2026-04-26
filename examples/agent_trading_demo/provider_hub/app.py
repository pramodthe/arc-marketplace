"""Minimal HTTP tools for the agent trading demo (marketplace provider contract).

The marketplace seller preflights GET {origin}/health and POSTs JSON to each
registered endpointUrl with fields including prompt, buyerId, billing, marketplace.
Responses must be JSON with outputText or result for the seller proxy.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException

app = FastAPI(title="Agent Trading Demo Provider Hub", version="0.1.0")

_VALID_SLUGS = frozenset(
    {
        "weather",
        "sentiment",
        "quote",
        "planner",
        "reminder",
        "summarize",
        "translate",
        "news_digest",
        "code_review",
        "task_split",
        "json_format",
    }
)


def _coerce_prompt(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return str(raw)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent_trading_demo_provider_hub"}


def _output_for(slug: str, prompt: str) -> str:
    p = (prompt or "").strip() or "(empty prompt)"
    if slug == "weather":
        return f"[weather] Stub forecast for: {p[:200]!r} — Arc testnet demo conditions: mild, USDC-native gas."
    if slug == "sentiment":
        return f"[sentiment] Stub tone scan for: {p[:200]!r} — neutral-to-positive (demo heuristic)."
    if slug == "quote":
        return f"[quote] Stub price context for: {p[:200]!r} — illustrative only, not financial advice."
    if slug == "planner":
        return f"[planner] Stub 3-step plan for: {p[:200]!r} — (1) discover (2) pay (3) invoke."
    if slug == "reminder":
        return f"[reminder] Stub reminder for: {p[:200]!r} — set for next demo loop tick."
    if slug == "summarize":
        return f"[summarize] Stub TL;DR for: {p[:200]!r} — key points: demo scope, USDC settle, Arc testnet."
    if slug == "translate":
        return f"[translate] Stub EN→demo-lang for: {p[:200]!r} — (fictional) gloss for marketplace testing."
    if slug == "news_digest":
        return f"[news_digest] Stub headline pack for: {p[:200]!r} — synthetic items only, not live news."
    if slug == "code_review":
        return f"[code_review] Stub review notes for: {p[:200]!r} — suggest tests, narrow scope, check balances."
    if slug == "task_split":
        return f"[task_split] Stub work breakdown for: {p[:200]!r} — slice by API / wallet / provider / verify."
    if slug == "json_format":
        return f"[json_format] Stub JSON-shaped summary for: {p[:200]!r} — {{\"ok\": true, \"demo\": true}}."
    return f"[{slug}] Echo: {p[:300]}"


@app.post("/tools/{slug}")
def invoke_tool(slug: str, body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Accept any JSON the marketplace forwards (prompt, buyerId, billing, marketplace, …).

    Strict Pydantic models caused 422 when prompts were long or fields had loose JSON types;
    this hub only needs ``prompt`` for the stub response.
    """
    normalized = slug.strip().lower()
    if normalized not in _VALID_SLUGS:
        raise HTTPException(status_code=404, detail=f"Unknown tool slug: {slug}")
    prompt = _coerce_prompt(body.get("prompt"))
    buyer_raw = body.get("buyerId")
    buyer_id: int | None
    if buyer_raw is None or buyer_raw == "":
        buyer_id = None
    elif isinstance(buyer_raw, bool):
        buyer_id = None
    else:
        try:
            buyer_id = int(buyer_raw)
        except (TypeError, ValueError):
            buyer_id = None
    text = _output_for(normalized, prompt)
    return {
        "outputText": text,
        "result": text,
        "service": normalized,
        "buyerId": buyer_id,
        "receivedPromptChars": len(prompt),
    }
