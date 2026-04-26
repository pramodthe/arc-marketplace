"""Smoke test: balances, /tools, one paid summarize call, /health."""

import asyncio
import hmac
import json
import os
import sys
import time
from decimal import Decimal
from hashlib import sha256

import httpx

from agents_market._env import load_backend_env

try:
    from circlekit import GatewayClient
except ImportError:  # pragma: no cover
    GatewayClient = None


def _demo_signature(*, payer: str, nonce: str, path: str, seller: str, chain: str, amount_usdc: str, secret: str) -> str:
    amount_base_units = int((Decimal(str(amount_usdc)) * Decimal("1000000")).to_integral_value())
    message = f"{payer}|{path}|{amount_base_units}|{nonce}|{seller}|{chain}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()
    return f"demo:{payer}:{nonce}:{digest}"


async def _async_main() -> None:
    load_backend_env()
    private_key = os.getenv("PRIVATE_KEY")
    server_url = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
    buyer_id = os.getenv("BUYER_ID", "").strip()
    if GatewayClient is not None and not private_key:
        print("Error: PRIVATE_KEY is required in .env")
        sys.exit(1)

    if GatewayClient is not None:
        async with GatewayClient(chain="arcTestnet", private_key=private_key) as gateway:
            print(f"Wallet: {gateway.address}")

            balances = await gateway.get_balances()
            print(f"Wallet USDC: {balances.wallet.formatted}")
            print(f"Gateway available: {balances.gateway.formatted_available}")

            async with httpx.AsyncClient(timeout=180.0) as http:
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

            async with httpx.AsyncClient(timeout=180.0) as client:
                health = await client.get(f"{server_url}/health")
                print(f"\nHealth check: {health.status_code}")
        return

    print("circlekit not installed; using demo x402 signature flow")
    async with httpx.AsyncClient(timeout=180.0) as http:
        tools_res = await http.get(f"{server_url}/marketplace/tools")
        tools_res.raise_for_status()
        tools = tools_res.json().get("tools", [])
        print(f"Available tools: {len(tools)}")
        if not tools:
            print("No tools found. Create seller and agent first.")
            return
        chosen = next((t for t in tools if t["toolKey"] == "summarize"), tools[0])
        target_path = (
            f"/sellers/{chosen['seller']['id']}/agents/{chosen['agent']['id']}/tools/{chosen['toolId']}/invoke"
        )
        target_url = f"{server_url}{target_path}"
        prompt = "Give me a concise Arc ecosystem update for today."
        body = {"prompt": prompt}
        if buyer_id.isdigit():
            body["buyerId"] = int(buyer_id)
        first = await http.post(target_url, json=body)
        if first.status_code != 402:
            first.raise_for_status()
            print("Invoke succeeded without payment challenge (likely buyerId settlement path).")
            print(f"AI response: {first.json().get('outputText')}")
            return
        if body.get("buyerId") is not None:
            try:
                err_payload = first.json()
            except Exception:
                err_payload = {}
            detail = err_payload.get("detail", first.text)
            detail_text = detail if isinstance(detail, str) else json.dumps(detail, indent=2)
            print("Invoke failed with buyerId (Arc USDC settlement did not complete). Server said:")
            print(detail_text)
            print(
                "\nTip: fund the buyer on Arc testnet, confirm BUYER_ID matches `/buyers/<id>/balances`, "
                "and restart `arc-seller` after pulling payment helper fixes."
            )
            sys.exit(1)
        payload = first.json()
        required_header = first.headers.get("PAYMENT-REQUIRED", "")
        required_payload = {}
        if required_header:
            try:
                required_payload = json.loads(required_header)
            except Exception:
                required_payload = {}
        seller = required_payload.get("destination") or chosen["seller"].get("walletAddress", "")
        amount_usdc = payload.get("arcMarketplaceSettlement", {}).get("priceUSDC") or f"{chosen['priceUSDC']:.6f}"
        payer = os.getenv("DEMO_X402_PAYER", "demo-buyer")
        nonce = str(int(time.time()))
        signature = _demo_signature(
            payer=payer,
            nonce=nonce,
            path=target_path,
            seller=seller,
            chain="arcTestnet",
            amount_usdc=amount_usdc,
            secret=os.getenv("DEMO_X402_SECRET", "demo-x402-secret-change-me"),
        )
        second = await http.post(target_url, json=body, headers={"Payment-Signature": signature})
        second.raise_for_status()
        result = second.json()
        print("\nDemo nanopayment complete")
        print(f"Paid: {result.get('payment', {}).get('amountUSDC')} USDC")
        print(f"Transaction: {result.get('payment', {}).get('transaction')}")
        print(f"Tool: {result.get('toolKey')}")
        print(f"Prompt: {prompt}")
        print(f"AI response: {result.get('outputText')}")

        health = await http.get(f"{server_url}/health")
        print(f"\nHealth check: {health.status_code}")


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
