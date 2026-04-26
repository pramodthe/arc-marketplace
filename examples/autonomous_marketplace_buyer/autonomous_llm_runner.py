"""LLM + marketplace-tools buyer loop (example-only; lives next to ``run_agent.py``).

Requires ``uv sync --group llm-buyer`` from ``backend/``. Imports ``agents_market`` from
``backend/src`` when that path is on ``PYTHONPATH`` (``uv run`` from ``backend/`` does this).
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from pydantic import Field

from agents_market._env import load_backend_env
from agents_market.arc.buyer.sdk import BuyerMarketplaceSDK, ToolCandidate


def load_autonomous_buyer_sidecar_env() -> None:
    """Load ``.env`` in this example directory (optional)."""
    side = Path(__file__).resolve().parent / ".env"
    if side.is_file():
        load_dotenv(side, override=False)


def load_envs_for_autonomous_buyer() -> None:
    load_backend_env()
    load_autonomous_buyer_sidecar_env()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _gemini_api_key() -> str:
    return _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")


def _gemini_base_url() -> str | None:
    u = _env("GEMINI_API_BASE_URL") or _env("GOOGLE_API_BASE_URL")
    return u or None


def _build_chat_model() -> tuple[Any, str]:
    from langchain_openai import ChatOpenAI

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        ChatGoogleGenerativeAI = None  # type: ignore[misc, assignment]

    gemini_key = _gemini_api_key()

    if gemini_key:
        if ChatGoogleGenerativeAI is None:
            raise RuntimeError("Gemini requested but langchain-google-genai is missing. Run: uv sync --group llm-buyer")
        model_name = _env("LLM_BUYER_MODEL", "gemini-2.0-flash")
        base = _gemini_base_url()
        kwargs: dict[str, Any] = {
            "model": model_name,
            "google_api_key": gemini_key,
            "temperature": 0.2,
            "convert_system_message_to_human": True,
        }
        if base:
            kwargs["base_url"] = base.rstrip("/")
        return ChatGoogleGenerativeAI(**kwargs), f"google_genai:{model_name}"

    openai_key = _env("OPENAI_API_KEY")
    if openai_key:
        model_name = _env("LLM_BUYER_MODEL") or _env("LLM_MODEL") or "gpt-4o-mini"
        openai_base = _env("OPENAI_BASE_URL") or _env("OPENAI_API_BASE")
        oa_kwargs: dict[str, Any] = {"model": model_name, "api_key": openai_key, "temperature": 0.2}
        if openai_base:
            oa_kwargs["base_url"] = openai_base.rstrip("/")
        return ChatOpenAI(**oa_kwargs), f"openai:{model_name}"

    raise RuntimeError(
        "No LLM API key for autonomous buyer. Set GEMINI_API_KEY or GOOGLE_API_KEY (Gemini), "
        "or OPENAI_API_KEY (OpenAI)."
    )


def _parse_buyer_id(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        return None


def _agent_name(candidate: ToolCandidate) -> str:
    raw = candidate.raw or {}
    agent = raw.get("agent") if isinstance(raw.get("agent"), dict) else {}
    return str(agent.get("name", ""))


def _compact_candidate(c: ToolCandidate) -> dict[str, Any]:
    return {
        "toolKey": c.tool_key,
        "priceUSDC": str(c.price_usdc),
        "invokeUrl": c.invoke_url,
        "agentName": _agent_name(c),
        "sellerId": c.seller_id,
        "agentId": c.agent_id,
        "toolId": c.tool_id,
    }


def _filter_by_agent_name(candidates: list[ToolCandidate], substring: str | None) -> list[ToolCandidate]:
    if not substring:
        return candidates
    sub = substring.strip().lower()
    return [c for c in candidates if sub in _agent_name(c).lower()]


def build_tools(
    sdk: BuyerMarketplaceSDK,
    *,
    agent_name_substring: str | None,
) -> list[Any]:
    from langchain_core.tools import tool

    @tool
    async def discover_marketplace(
        intent: Annotated[str, Field(description="User goal in natural language for marketplace discovery.")],
        budget_usdc: Annotated[float, Field(description="Max budget in USDC for listing prices.", ge=0.000001, le=1.0)] = 0.05,
        desired_tool: Annotated[
            str,
            Field(description="Tool family hint for the discover API: auto, summarize, analyze, plan, response."),
        ] = "auto",
        max_results: Annotated[int, Field(description="Max candidates from discover.", ge=1, le=20)] = 8,
    ) -> str:
        """Discover marketplace tools matching an intent and budget. Call before invoke."""
        budget = Decimal(str(budget_usdc))
        rows = await sdk.discover(
            prompt=intent,
            budget_usdc=budget,
            desired_tool=desired_tool.strip() or "auto",
            max_results=max_results,
        )
        filtered = _filter_by_agent_name(rows, agent_name_substring)
        compact = [_compact_candidate(c) for c in filtered]
        payload = {
            "count": len(compact),
            "agentFilter": agent_name_substring,
            "candidates": compact,
        }
        return json.dumps(payload, indent=2)

    @tool
    async def list_marketplace_tools() -> str:
        """List all tools on the marketplace (fallback if discover returns nothing)."""
        tools = await sdk.list_tools()
        filtered = _filter_by_agent_name(tools, agent_name_substring)
        compact = [_compact_candidate(c) for c in filtered]
        return json.dumps({"count": len(compact), "tools": compact}, indent=2)

    @tool
    async def invoke_marketplace(
        invoke_url: Annotated[str, Field(description="Full invoke URL from discover or list_marketplace_tools.")],
        prompt: Annotated[str, Field(description="Prompt sent to the seller tool / provider.")],
        selected_skills: Annotated[
            str,
            Field(
                description='JSON array of skill keys, e.g. [] or ["skillA"]. Empty string means [].',
            ),
        ] = "",
    ) -> str:
        """Invoke a marketplace tool with buyerId settlement. Use the exact invokeUrl from discover/list output."""
        skills: list[str] = []
        raw = selected_skills.strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    skills = [str(x) for x in parsed]
            except json.JSONDecodeError:
                return json.dumps({"ok": False, "error": "selected_skills must be a JSON array string"})

        url = invoke_url.strip()
        if url.startswith("/"):
            url = f"{sdk.server_url}{url}"

        candidate = ToolCandidate(
            tool_key="invoke",
            price_usdc=Decimal("0"),
            invoke_url=url,
            source="agent_tool",
            raw=None,
        )
        try:
            result = await sdk.invoke(
                candidate=candidate,
                prompt=prompt,
                selected_skills=skills or None,
                include_buyer_id=True,
            )
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "invokeUrl": url})

        out = result.get("outputText") or result.get("result") or ""
        return json.dumps(
            {
                "ok": True,
                "outputText": out,
                "payment": result.get("payment"),
                "toolKey": result.get("toolKey"),
            },
            indent=2,
        )

    return [discover_marketplace, list_marketplace_tools, invoke_marketplace]


SYSTEM_PROMPT = """You are an autonomous buyer agent for a USDC-priced agent marketplace (Arc testnet settlement via buyerId).

Workflow:
1) Call discover_marketplace with the user's intent and a sensible budget_usdc (default 0.05 if unspecified).
2) If no suitable candidate appears, call list_marketplace_tools once, then pick again.
3) Choose one tool whose description fits the user request and whose priceUSDC is within the user's budget.
4) Call invoke_marketplace with the exact invokeUrl from your chosen candidate and a concise prompt for that tool.
5) Reply to the user with a short natural-language summary, including key facts from outputText.

Rules:
- Always discover (or list) before invoke unless the user only asked about marketplace health.
- Use only invoke URLs returned by the tools; do not invent URLs.
- If every tool exceeds budget, say so and suggest raising budget or narrowing the task.
"""


def _serialize_messages_for_trace(messages: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        d: dict[str, Any] = {"type": m.__class__.__name__}
        content = getattr(m, "content", None)
        if isinstance(content, str):
            d["content_preview"] = content[:500]
        elif content is not None:
            d["content_preview"] = str(content)[:500]
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            d["tool_calls"] = tool_calls
        out.append(d)
    return out


async def run_autonomous_buyer_turn(
    user_message: str,
    *,
    include_trace: bool = False,
) -> dict[str, Any]:
    """Run one agent turn: discover → tools → invoke → final assistant text."""
    from langchain.agents import create_agent

    load_envs_for_autonomous_buyer()

    user = user_message.strip()
    if not user:
        return {"ok": False, "error": "empty_message"}

    public = _env("PUBLIC_BASE_URL") or _env("SERVER_URL", "http://localhost:4021")
    server_url = public.rstrip("/")
    buyer_id = _parse_buyer_id(_env("BUYER_ID"))
    buyer_name = _env("BUYER_NAME", "LLM Marketplace Buyer")
    agent_filter = _env("MARKETPLACE_AGENT_NAME_SUBSTRING") or None

    sdk = BuyerMarketplaceSDK(
        server_url=server_url,
        buyer_id=buyer_id,
        buyer_name=buyer_name,
    )
    profile = await sdk.ensure_buyer()

    try:
        model, model_label = _build_chat_model()
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc), "buyerId": profile.id}

    tools = build_tools(sdk, agent_name_substring=agent_filter)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT
        + (f"\n\nPrefer tools from agents whose name contains: {agent_filter!r}." if agent_filter else ""),
    )

    result = await agent.ainvoke({"messages": [{"role": "user", "content": user}]})
    messages = result.get("messages") or []
    last = messages[-1] if messages else None
    content = getattr(last, "content", str(last)) if last is not None else ""
    if isinstance(content, list):
        text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        content = "".join(text_parts) if text_parts else json.dumps(content)

    payload: dict[str, Any] = {
        "ok": True,
        "reply": content,
        "buyerId": profile.id,
        "model": model_label,
    }
    if include_trace:
        payload["trace"] = _serialize_messages_for_trace(messages)
    return payload
