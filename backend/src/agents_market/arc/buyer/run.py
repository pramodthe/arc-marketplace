import asyncio
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from agents_market._env import load_backend_env

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


def desired_tool_from_task(task: str, prompt: str) -> str:
    if task in ("summarize", "analyze", "plan", "response"):
        return task
    p = prompt.lower()
    if any(
        w in p
        for w in (
            "roadmap",
            "milestone",
            "step-by-step",
            "sprint plan",
            "project plan",
            "three-step",
            "3-step",
        )
    ):
        return "plan"
    if any(
        w in p
        for w in (
            "analyze",
            "compare",
            "deep dive",
            "trade-off",
            "tradeoff",
            "risk of",
            "pros and cons",
        )
    ):
        return "analyze"
    return "summarize"


def pick_tool(desired_id: str, budget: Decimal, tools: list[dict]) -> tuple[dict, str] | tuple[None, str]:
    preference_chains: dict[str, list[str]] = {
        "plan": ["plan", "analyze", "summarize", "response"],
        "analyze": ["analyze", "summarize", "response", "plan"],
        "summarize": ["summarize", "response", "analyze", "plan"],
        "response": ["response", "summarize", "analyze", "plan"],
    }
    chain = preference_chains.get(desired_id, preference_chains["summarize"])
    by_key = {t["toolKey"]: t for t in tools}
    for tid in chain:
        row = by_key.get(tid)
        if row and budget >= Decimal(str(row["priceUSDC"])):
            if tid == desired_id:
                return row, f"selected={tid} (matches task)"
            return row, f"downgraded_to={tid} (budget or preference)"

    cheapest = sorted(tools, key=lambda t: Decimal(str(t["priceUSDC"])))
    for row in cheapest:
        if budget >= Decimal(str(row["priceUSDC"])):
            return row, f"downgraded_to={row['toolKey']} (fallback)"

    return None, "insufficient_budget_for_any_tool"


async def _ensure_buyer_id(http: httpx.AsyncClient) -> int:
    if BUYER_ID.isdigit():
        return int(BUYER_ID)
    response = await http.post(
        f"{SERVER_URL}/buyers",
        json={
            "name": BUYER_NAME,
            "organization": "Agents Market",
            "description": "Autonomous buyer for on-chain marketplace tests",
            "walletAddress": "",
        },
    )
    response.raise_for_status()
    return int(response.json()["buyer"]["id"])


async def run_once(prompt: str, budget: Decimal) -> tuple[Decimal, str]:

    async with httpx.AsyncClient(timeout=10) as http:
        buyer_id = await _ensure_buyer_id(http)
        discover_payload = {
            "prompt": prompt,
            "budgetUSDC": float(budget),
            "desiredTool": BUYER_TASK if BUYER_TASK in ("summarize", "analyze", "plan", "response") else "auto",
            "maxResults": 5,
        }
        discovery = (await http.post(f"{SERVER_URL}/marketplace/discover", json=discover_payload)).json()
        candidates = discovery.get("candidates", [])
        marketplace_tools = (await http.get(f"{SERVER_URL}/marketplace/tools")).json().get("tools", [])
    if not marketplace_tools and not candidates:
        print("[buyer] no marketplace tools available")
        return Decimal("0"), "insufficient_budget_for_any_tool"

    desired = desired_tool_from_task(BUYER_TASK, prompt)
    top_candidate = candidates[0]["candidate"] if candidates else None
    tool = top_candidate
    reason = f"autonomous_discovery score={candidates[0]['score']:.3f}" if candidates else "fallback"
    if tool is None:
        tool, reason = pick_tool(desired, budget, marketplace_tools)
    if tool is None:
        print(f"[buyer] skip: {reason} (budget={budget})")
        return Decimal("0"), reason

    if tool.get("invokeUrl"):
        url = str(tool["invokeUrl"])
    else:
        invoke_path = f"/sellers/{tool['seller']['id']}/agents/{tool['agent']['id']}/tools/{tool['toolId']}/invoke"
        url = f"{SERVER_URL}{invoke_path}"
    selected_skills = [skill["skillKey"] for skill in (tool.get("skills") or [])[:1]]
    print(
        f"[buyer] {reason} | source={tool.get('source','internal')} "
        f"| tool={tool['toolKey']} | start_price=${Decimal(str(tool['priceUSDC'])):.4f} | url={url}"
    )

    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            url,
            json={
                "prompt": prompt,
                "buyerId": buyer_id,
                "selectedSkills": selected_skills,
            },
        )
        response.raise_for_status()
        result = response.json()
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
