"""Smoke test: balances, /tools, one paid summarize call, /health."""

import asyncio
import os
import sys

import httpx

from agents_market._env import load_backend_env

try:
    from circlekit import GatewayClient
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'circlekit'. Install editable circle-titanoboa-sdk "
        "(see backend/README.md)."
    ) from exc


async def _async_main() -> None:
    load_backend_env()
    private_key = os.getenv("PRIVATE_KEY")
    server_url = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
    buyer_id = os.getenv("BUYER_ID", "").strip()
    if not private_key:
        print("Error: PRIVATE_KEY is required in .env")
        sys.exit(1)

    async with GatewayClient(chain="arcTestnet", private_key=private_key) as gateway:
        print(f"Wallet: {gateway.address}")

        balances = await gateway.get_balances()
        print(f"Wallet USDC: {balances.wallet.formatted}")
        print(f"Gateway available: {balances.gateway.formatted_available}")

        async with httpx.AsyncClient(timeout=10) as http:
            tools_res = await http.get(f"{server_url}/marketplace/tools")
            tools_res.raise_for_status()
            tools = tools_res.json().get("tools", [])
            print(f"Available tools: {len(tools)}")
            for t in tools:
                print(
                    f"  seller={t['seller']['name']} agent={t['agent']['name']} "
                    f"tool={t['toolKey']} price=${t['priceUSDC']:.2f}"
                )
            discover = await http.post(
                f"{server_url}/marketplace/discover",
                json={
                    "prompt": "Need concise Arc ecosystem summary with low budget",
                    "budgetUSDC": 0.05,
                    "desiredTool": "summarize",
                    "maxResults": 3,
                },
            )
            discover.raise_for_status()
            candidates = discover.json().get("candidates", [])
            print(f"Discovery candidates: {len(candidates)}")
            if candidates:
                top = candidates[0]
                print(
                    f"Top discovery: source={top['candidate'].get('source')} "
                    f"tool={top['candidate'].get('toolKey')} score={top.get('score')}"
                )
        if not tools:
            print("No tools found. Create seller and agent first.")
            return

        chosen = next((t for t in tools if t["toolKey"] == "summarize"), tools[0])
        target = (
            f"{server_url}/sellers/{chosen['seller']['id']}/agents/"
            f"{chosen['agent']['id']}/tools/{chosen['toolId']}/invoke"
        )
        prompt = "Give me a concise Arc ecosystem update for today."
        body = {"prompt": prompt}
        if buyer_id.isdigit():
            body["buyerId"] = int(buyer_id)
        result = await gateway.pay(target, method="POST", body=body)
        print("\nNanopayment complete")
        print(f"Paid: {result.formatted_amount} USDC")
        print(f"Transaction: {result.transaction}")
        print(f"Tool: {result.data.get('toolKey')}")
        print(f"Prompt: {prompt}")
        print(f"AI response: {result.data.get('outputText')}")

        async with httpx.AsyncClient(timeout=10) as client:
            health = await client.get(f"{server_url}/health")
            print(f"\nHealth check: {health.status_code}")


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
