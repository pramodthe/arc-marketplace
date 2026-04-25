import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal

from agents_market._env import load_backend_env
from agents_market.arc.buyer.sdk import BuyerMarketplaceSDK, ToolCandidate

load_backend_env()
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
LOOP_SECONDS = float(os.getenv("BUYER_LOOP_SECONDS", "0"))
BUYER_PROMPT = os.getenv("BUYER_PROMPT", "Give me a short crypto market update.")
BUYER_TASK = os.getenv("BUYER_TASK", "auto").strip().lower()
BUYER_BUDGET_USDC = os.getenv("BUYER_BUDGET_USDC", "999").strip()
BUYER_ID = os.getenv("BUYER_ID", "").strip()
BUYER_NAME = os.getenv("BUYER_NAME", "Marketplace Buyer").strip()


def _parse_budget() -> Decimal:
    try:
        return Decimal(BUYER_BUDGET_USDC)
    except Exception:
        return Decimal("999")


async def run_once(prompt: str, budget: Decimal) -> tuple[Decimal, str]:
    sdk = BuyerMarketplaceSDK(
        server_url=SERVER_URL,
        buyer_id=int(BUYER_ID) if BUYER_ID.isdigit() else None,
        buyer_name=BUYER_NAME,
        timeout_seconds=30,
    )
    desired = sdk.desired_tool_from_prompt(task=BUYER_TASK, prompt=prompt)
    candidates = await sdk.discover(
        prompt=prompt,
        budget_usdc=budget,
        desired_tool=BUYER_TASK if BUYER_TASK in ("summarize", "analyze", "plan", "response") else "auto",
        max_results=5,
    )
    marketplace_tools = await sdk.list_tools()
    if not marketplace_tools and not candidates:
        print("[buyer] no marketplace tools available")
        return Decimal("0"), "insufficient_budget_for_any_tool"

    top_candidate = candidates[0] if candidates else None
    tool = top_candidate
    reason = "autonomous_discovery"
    if tool is None:
        tool, reason = sdk.pick_best(
            desired_tool=desired,
            budget_usdc=budget,
            candidates=candidates,
            fallback_tools=marketplace_tools,
        )
    if tool is None:
        print(f"[buyer] skip: {reason} (budget={budget})")
        return Decimal("0"), reason

    selected_skills = tool.first_skill_keys(limit=1)
    assert isinstance(tool, ToolCandidate)
    print(
        f"[buyer] {reason} | source={tool.source} "
        f"| tool={tool.tool_key} | start_price=${tool.price_usdc:.4f} | url={tool.invoke_url}"
    )

    result = await sdk.invoke(
        candidate=tool,
        prompt=prompt,
        selected_skills=selected_skills,
        include_buyer_id=True,
    )
    spent = Decimal(str(result["payment"]["amountUSDC"]))
    output_text = result.get("outputText", "")

    print(
        f"[{datetime.now(timezone.utc).isoformat()}] paid {result['payment']['amountUSDC']} USDC "
        f"tx={result['payment']['onchainTxHash']}"
    )
    print(f"Prompt: {prompt}")
    print(f"AI output: {str(output_text)[:220]}")
    print("-" * 60)
    return spent, "ok"


async def main() -> None:
    session_budget = _parse_budget()
    prompt = BUYER_PROMPT

    if LOOP_SECONDS <= 0:
        await run_once(prompt, session_budget)
        return

    print(
        f"Buyer agent loop (every {LOOP_SECONDS}s). "
        f"Session budget: {session_budget} USDC. Ctrl+C to stop."
    )
    remaining = session_budget
    while True:
        try:
            spent, status = await run_once(prompt, remaining)
            if status == "insufficient_budget_for_any_tool":
                break
            remaining -= spent
            if remaining <= 0:
                print(f"[buyer] session budget exhausted (remaining={remaining})")
                break
        except Exception as exc:  # pragma: no cover
            print(f"Buyer run failed: {exc}")
        await asyncio.sleep(LOOP_SECONDS)
