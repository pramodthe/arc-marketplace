from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx


@dataclass
class RegisteredTool:
    seller_id: int
    agent_id: int
    tool_id: int
    invoke_url: str
    label: str


class TravelHopDemo:
    def __init__(self) -> None:
        self.marketplace_url = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
        self.provider_host = os.getenv("TRAVEL_PROVIDER_HOST", "127.0.0.1").strip()
        self.timeout = float(os.getenv("TRAVEL_DEMO_TIMEOUT_SECONDS", "20"))
        self.budget_usdc = Decimal(os.getenv("TRAVEL_BUDGET_USDC", "0.03"))
        self._agent_processes: list[subprocess.Popen[Any]] = []
        self._agents_dir = Path(__file__).resolve().parents[1] / "travel_agents"
        self._agent_specs = [
            ("hotel_agent.py", "5053"),
            ("flight_agent.py", "5054"),
            ("itinerary_agent.py", "5055"),
        ]

    async def start_provider_servers(self) -> None:
        for script_name, port in self._agent_specs:
            script_path = self._agents_dir / script_name
            env = os.environ.copy()
            env["TRAVEL_AGENT_HOST"] = self.provider_host
            env["TRAVEL_AGENT_PORT"] = port
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                env=env,
                cwd=str(self._agents_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._agent_processes.append(process)
        await asyncio.sleep(1.0)

    async def stop_provider_servers(self) -> None:
        for process in self._agent_processes:
            if process.poll() is None:
                process.terminate()
        for process in self._agent_processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    async def _ensure_provider_health(self) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for _script_name, port in self._agent_specs:
                health_url = f"http://{self.provider_host}:{port}/health"
                response = await client.get(health_url)
                response.raise_for_status()

    def _provider_docs_url(self, port: str) -> str:
        return f"http://{self.provider_host}:{port}/docs"

    def _provider_invoke_url(self, port: str) -> str:
        return f"http://{self.provider_host}:{port}/invoke"

    async def _discover_top_candidate(
        self,
        client: httpx.AsyncClient,
        *,
        prompt: str,
        exclude_agent_ids: set[int],
    ) -> dict[str, Any]:
        response = await client.post(
            f"{self.marketplace_url}/marketplace/discover",
            json={
                "prompt": prompt,
                "budgetUSDC": float(self.budget_usdc),
                "desiredTool": "auto",
                "maxResults": 10,
            },
        )
        response.raise_for_status()
        rows = response.json().get("candidates", [])
        if not rows:
            raise RuntimeError(f"No discovery candidates for: {prompt}")

        print(f"\nDiscovery prompt: {prompt}")
        for idx, row in enumerate(rows[:5], start=1):
            candidate = row.get("candidate", {})
            agent = candidate.get("agent", {})
            seller = candidate.get("seller", {})
            print(
                f"  {idx}. seller={seller.get('name')} agent={agent.get('name')} "
                f"tool={candidate.get('toolName')} score={row.get('score')}"
            )

        for row in rows:
            candidate = row.get("candidate", {})
            agent_id = int(candidate.get("agent", {}).get("id", 0) or 0)
            if agent_id and agent_id not in exclude_agent_ids:
                return candidate
        return rows[0]["candidate"]

    async def _create_seller(self, client: httpx.AsyncClient, name: str, description: str) -> int:
        response = await client.post(
            f"{self.marketplace_url}/sellers",
            json={
                "name": name,
                "description": description,
                "ownerWalletAddress": "",
                "validatorWalletAddress": "",
            },
        )
        response.raise_for_status()
        return int(response.json()["seller"]["id"])

    async def _create_agent(
        self,
        client: httpx.AsyncClient,
        *,
        seller_id: int,
        name: str,
        description: str,
        endpoint_url: str,
        api_docs_url: str,
        category: str,
    ) -> RegisteredTool:
        response = await client.post(
            f"{self.marketplace_url}/sellers/{seller_id}/agents",
            json={
                "name": name,
                "description": description,
                "category": category,
                "offeringType": "agent",
                "protocolType": "http",
                "endpointUrl": endpoint_url,
                "httpMethod": "POST",
                "priceUSDC": 0.01,
                "apiDocsUrl": api_docs_url,
                "metadataUri": "",
            },
        )
        response.raise_for_status()
        payload = response.json()
        agent = payload["agent"]
        tool = agent["tools"][0]
        return RegisteredTool(
            seller_id=int(payload["seller"]["id"]),
            agent_id=int(agent["id"]),
            tool_id=int(tool["toolId"]),
            invoke_url=(
                f"{self.marketplace_url}/sellers/{payload['seller']['id']}/agents/"
                f"{agent['id']}/tools/{tool['toolId']}/invoke"
            ),
            label=f"{payload['seller']['name']}::{agent['name']}",
        )

    async def _create_buyer(self, client: httpx.AsyncClient) -> int:
        response = await client.post(
            f"{self.marketplace_url}/buyers",
            json={
                "name": "Travel Buyer Agent",
                "organization": "Agents Market Demo",
                "description": "Orchestrates multi-seller travel planning workflows.",
                "walletAddress": "",
                "validatorWalletAddress": "",
            },
        )
        response.raise_for_status()
        return int(response.json()["buyer"]["id"])

    async def _invoke_with_buyer(
        self, client: httpx.AsyncClient, invoke_url: str, prompt: str, buyer_id: int
    ) -> dict[str, Any]:
        response = await client.post(
            invoke_url,
            json={"prompt": prompt, "buyerId": buyer_id},
        )
        response.raise_for_status()
        return response.json()

    async def run(self) -> None:
        await self.start_provider_servers()
        try:
            await self._ensure_provider_health()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                print("Registering buyer + sellers + agents...")
                buyer_id = await self._create_buyer(client)

                hotel_seller_id = await self._create_seller(
                    client,
                    "Hotel Finder Seller",
                    "Specialized in hotel discovery and selection.",
                )
                flight_seller_id = await self._create_seller(
                    client,
                    "Flight Booker Seller",
                    "Specialized in flight selection and booking recommendations.",
                )
                itinerary_seller_id = await self._create_seller(
                    client,
                    "Itinerary Writer Seller",
                    "Specialized in writing practical day-by-day itineraries.",
                )

                hotel_tool = await self._create_agent(
                    client,
                    seller_id=hotel_seller_id,
                    name="Hotel Finder Agent",
                    description="Travel hotel specialist. Finds hotels by city, nights, and budget.",
                    endpoint_url=self._provider_invoke_url("5053"),
                    api_docs_url=self._provider_docs_url("5053"),
                    category="Travel",
                )
                flight_tool = await self._create_agent(
                    client,
                    seller_id=flight_seller_id,
                    name="Flight Booker Agent",
                    description="Travel flight specialist. Finds flight options by route and date.",
                    endpoint_url=self._provider_invoke_url("5054"),
                    api_docs_url=self._provider_docs_url("5054"),
                    category="Travel",
                )
                itinerary_tool = await self._create_agent(
                    client,
                    seller_id=itinerary_seller_id,
                    name="Itinerary Writer Agent",
                    description="Travel itinerary specialist. Writes day-by-day plans from trip context.",
                    endpoint_url=self._provider_invoke_url("5055"),
                    api_docs_url=self._provider_docs_url("5055"),
                    category="Travel",
                )

                print(f"Buyer registered: {buyer_id}")
                print(f"Registered seller agents: {hotel_tool.label}, {flight_tool.label}, {itinerary_tool.label}")

                print("\nStarting multi-hop travel orchestration...")
                used_agent_ids: set[int] = set()

                hotel_candidate = await self._discover_top_candidate(
                    client,
                    prompt="I need a hotel recommendation in Tokyo for 4 nights near transit.",
                    exclude_agent_ids=used_agent_ids,
                )
                used_agent_ids.add(int(hotel_candidate["agent"]["id"]))
                hotel_invoke_url = (
                    f"{self.marketplace_url}/sellers/{hotel_candidate['seller']['id']}/agents/"
                    f"{hotel_candidate['agent']['id']}/tools/{hotel_candidate['toolId']}/invoke"
                )
                hotel_response = await self._invoke_with_buyer(
                    client,
                    hotel_invoke_url,
                    "Need hotel options in Tokyo for 4 nights, under 700 USD total.",
                    buyer_id,
                )
                print(f"Hop 1 complete: {hotel_candidate['agent']['name']} invoked.")

                flight_candidate = await self._discover_top_candidate(
                    client,
                    prompt="I need flight options from SFO to Tokyo with good timing.",
                    exclude_agent_ids=used_agent_ids,
                )
                used_agent_ids.add(int(flight_candidate["agent"]["id"]))
                flight_invoke_url = (
                    f"{self.marketplace_url}/sellers/{flight_candidate['seller']['id']}/agents/"
                    f"{flight_candidate['agent']['id']}/tools/{flight_candidate['toolId']}/invoke"
                )
                flight_response = await self._invoke_with_buyer(
                    client,
                    flight_invoke_url,
                    "Need SFO to Tokyo round-trip flights, May 14-18, with max one stop.",
                    buyer_id,
                )
                print(f"Hop 2 complete: {flight_candidate['agent']['name']} invoked.")

                itinerary_candidate = await self._discover_top_candidate(
                    client,
                    prompt="Build a complete day-by-day travel itinerary using selected hotel and flights.",
                    exclude_agent_ids=used_agent_ids,
                )
                itinerary_invoke_url = (
                    f"{self.marketplace_url}/sellers/{itinerary_candidate['seller']['id']}/agents/"
                    f"{itinerary_candidate['agent']['id']}/tools/{itinerary_candidate['toolId']}/invoke"
                )
                itinerary_prompt = (
                    "Create a 4-day itinerary using the context below.\n"
                    f"Hotel output: {json.dumps(hotel_response.get('providerResponse', {}), ensure_ascii=True)}\n"
                    f"Flight output: {json.dumps(flight_response.get('providerResponse', {}), ensure_ascii=True)}"
                )
                itinerary_response = await self._invoke_with_buyer(
                    client,
                    itinerary_invoke_url,
                    itinerary_prompt,
                    buyer_id,
                )
                print(f"Hop 3 complete: {itinerary_candidate['agent']['name']} invoked.")

                print("\n=== DEMO RESULT ===")
                print("Hotel Response:")
                print(json.dumps(hotel_response, indent=2, ensure_ascii=True))
                print("\nFlight Response:")
                print(json.dumps(flight_response, indent=2, ensure_ascii=True))
                print("\nItinerary Response:")
                print(json.dumps(itinerary_response, indent=2, ensure_ascii=True))

                print(
                    "\nDone: single buyer agent discovered and invoked hotel + flight + itinerary "
                    "seller agents in a multi-hop flow."
                )
        finally:
            await self.stop_provider_servers()


async def main() -> None:
    demo = TravelHopDemo()
    try:
        await demo.run()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        print(f"HTTP error {exc.response.status_code}: {body}")
        print(
            "\nIf this fails on local endpoints, ensure backend env sets "
            "ALLOW_PRIVATE_PROVIDER_ENDPOINTS=true and Circle/Arc env variables are configured."
        )
        raise


if __name__ == "__main__":
    asyncio.run(main())
