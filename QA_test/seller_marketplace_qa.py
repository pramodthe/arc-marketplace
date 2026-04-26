"""Seller + marketplace QA smoke checks for demo readiness."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _print(result: CheckResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"[{status}] {result.name}: {result.detail}")


def _pick_first_tool(tools_payload: dict[str, Any]) -> dict[str, Any] | None:
    tools = tools_payload.get("tools", [])
    if not tools:
        return None
    return tools[0]


async def check_marketplace(client: httpx.AsyncClient, base_url: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    health = await client.get(f"{base_url}/health")
    if health.status_code == 200:
        payload = health.json()
        results.append(
            CheckResult(
                "marketplace_health",
                True,
                f"status={payload.get('status')} sellers={payload.get('sellerCount')} buyers={payload.get('buyerCount')}",
            )
        )
    else:
        results.append(CheckResult("marketplace_health", False, f"http={health.status_code}"))

    root = await client.get(f"{base_url}/")
    if root.status_code == 200:
        payload = root.json()
        mode = payload.get("gatewayNanopaymentsMode")
        results.append(CheckResult("payment_rail_mode", True, f"gateway mode={mode}"))
    else:
        results.append(CheckResult("payment_rail_mode", False, f"http={root.status_code}"))

    tools = await client.get(f"{base_url}/marketplace/tools")
    if tools.status_code == 200:
        count = len(tools.json().get("tools", []))
        results.append(CheckResult("marketplace_tools", count > 0, f"tools={count}"))
    else:
        results.append(CheckResult("marketplace_tools", False, f"http={tools.status_code}"))

    discover = await client.post(
        f"{base_url}/marketplace/discover",
        json={
            "prompt": "Find best travel planning tool",
            "budgetUSDC": 0.05,
            "desiredTool": "auto",
            "maxResults": 3,
        },
    )
    if discover.status_code == 200:
        count = len(discover.json().get("candidates", []))
        results.append(CheckResult("marketplace_discover", count > 0, f"candidates={count}"))
    else:
        results.append(CheckResult("marketplace_discover", False, f"http={discover.status_code}"))

    return results


async def check_provider_card(client: httpx.AsyncClient, provider_url: str, token: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    health = await client.get(f"{provider_url.rstrip('/')}/health", headers=headers)
    results.append(
        CheckResult(
            "provider_health",
            health.status_code == 200,
            f"http={health.status_code}",
        )
    )

    card = await client.get(f"{provider_url.rstrip('/')}/.well-known/agent-card.json", headers=headers)
    if card.status_code != 200:
        results.append(CheckResult("provider_card_reachable", False, f"http={card.status_code}"))
        return results

    payload = card.json()
    endpoint = str(payload.get("endpoint", ""))
    endpoint_is_public = endpoint.startswith("https://") and "127.0.0.1" not in endpoint and "localhost" not in endpoint

    results.append(CheckResult("provider_card_reachable", True, "card loaded"))
    results.append(
        CheckResult(
            "provider_card_endpoint_public",
            endpoint_is_public,
            f"endpoint={endpoint or '<missing>'}",
        )
    )

    return results


async def check_invoke_flow(
    client: httpx.AsyncClient,
    base_url: str,
    buyer_id: str,
    use_buyer_id: bool,
    payment_mode: str,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    tools_resp = await client.get(f"{base_url}/marketplace/tools")
    if tools_resp.status_code != 200:
        return [CheckResult("invoke_prereq_tools", False, f"http={tools_resp.status_code}")]
    tool = _pick_first_tool(tools_resp.json())
    if not tool:
        return [CheckResult("invoke_prereq_tools", False, "no tools available")]

    invoke_url = (
        f"{base_url}/sellers/{tool['seller']['id']}/agents/{tool['agent']['id']}/tools/{tool['toolId']}/invoke"
    )
    body: dict[str, Any] = {"prompt": "QA probe: return a short status response."}
    if use_buyer_id and buyer_id:
        body["buyerId"] = int(buyer_id)

    resp = await client.post(invoke_url, json=body)
    if use_buyer_id:
        ok = resp.status_code in {200, 402, 502}
        detail = f"http={resp.status_code} buyerId={buyer_id}"
        results.append(CheckResult("invoke_buyer_path", ok, detail))
        return results

    if payment_mode == "disabled":
        results.append(
            CheckResult(
                "invoke_x402_runtime_unavailable",
                resp.status_code == 503,
                f"expected=503 actual={resp.status_code}",
            )
        )
        return results

    if resp.status_code == 402:
        results.append(CheckResult("invoke_x402_challenge", True, "received payment challenge"))
    else:
        results.append(CheckResult("invoke_x402_challenge", False, f"expected 402 got {resp.status_code}"))
        return results

    # Force explicit x402 verification failure to ensure strict logging works.
    bad_sig_resp = await client.post(
        invoke_url,
        json=body,
        headers={"Payment-Signature": "invalid-signature"},
    )
    results.append(
        CheckResult(
            "invoke_x402_invalid_signature_rejected",
            bad_sig_resp.status_code == 402,
            f"expected=402 actual={bad_sig_resp.status_code}",
        )
    )
    return results


async def check_transactions_failure_evidence(
    client: httpx.AsyncClient,
    base_url: str,
    expected_failure_code: str,
) -> CheckResult:
    response = await client.get(f"{base_url}/transactions")
    if response.status_code != 200:
        return CheckResult("transactions_failure_evidence", False, f"http={response.status_code}")
    payload = response.json()
    events = payload.get("events", [])
    found = False
    for event in events:
        details = event.get("details", {})
        if not isinstance(details, dict):
            continue
        if details.get("failureCode") == expected_failure_code:
            found = True
            break
    return CheckResult(
        "transactions_failure_evidence",
        found,
        f"failureCode={expected_failure_code}",
    )


async def main() -> int:
    base_url = env("QA_BASE_URL", "http://localhost:4021").rstrip("/")
    provider_url = env("QA_SELLER_PROVIDER_URL")
    token = env("QA_GCP_IDENTITY_TOKEN")
    buyer_id = env("QA_BUYER_ID")
    use_buyer_id = env("QA_USE_BUYER_ID", "false").lower() in {"1", "true", "yes", "on"}

    timeout = httpx.Timeout(20.0, connect=10.0)
    results: list[CheckResult] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            market_results = await check_marketplace(client, base_url)
            results.extend(market_results)
            payment_mode = "unknown"
            for item in market_results:
                if item.name == "payment_rail_mode":
                    # detail format: "gateway mode=<value>"
                    payment_mode = item.detail.split("gateway mode=")[-1]
                    break
            if provider_url:
                results.extend(await check_provider_card(client, provider_url, token))
            results.extend(await check_invoke_flow(client, base_url, buyer_id, use_buyer_id, payment_mode))

            if not use_buyer_id:
                expected_failure = "x402_runtime_unavailable" if payment_mode == "disabled" else "x402_verification_failed"
                results.append(await check_transactions_failure_evidence(client, base_url, expected_failure))
        except Exception as exc:
            results.append(CheckResult("qa_runner", False, f"unexpected_error={exc}"))

    for result in results:
        _print(result)

    failed = [r for r in results if not r.ok]
    print("\nSummary:")
    print(json.dumps({"total": len(results), "failed": len(failed)}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(__import__("asyncio").run(main()))
