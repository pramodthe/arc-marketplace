from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx


@dataclass(slots=True)
class BuyerProfile:
    id: int
    name: str
    wallet_address: str


@dataclass(slots=True)
class ToolCandidate:
    tool_key: str
    price_usdc: Decimal
    invoke_url: str
    source: str
    seller_id: int | None = None
    agent_id: int | None = None
    tool_id: int | None = None
    skills: list[dict[str, Any]] | None = None
    raw: dict[str, Any] | None = None

    def first_skill_keys(self, *, limit: int = 1) -> list[str]:
        items = self.skills or []
        return [str(skill.get("skillKey")) for skill in items[:limit] if skill.get("skillKey")]


class BuyerMarketplaceSDK:
    """Small SDK wrapper for marketplace buyer integrations.

    Provides one client with predictable flow:
    1) discover marketplace candidates
    2) pick best candidate for budget/task
    3) invoke seller tool with optional buyer identity
    """

    def __init__(
        self,
        *,
        server_url: str,
        buyer_id: int | None = None,
        buyer_name: str = "Marketplace Buyer",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self._buyer_id = buyer_id
        self.buyer_name = buyer_name
        self.timeout_seconds = timeout_seconds

    async def ensure_buyer(self) -> BuyerProfile:
        if self._buyer_id is not None:
            profile = await self.get_buyer(self._buyer_id)
            return BuyerProfile(
                id=int(profile["id"]),
                name=str(profile.get("name", self.buyer_name)),
                wallet_address=str(profile.get("walletAddress", "")),
            )

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
            response = await http.post(
                f"{self.server_url}/buyers",
                json={
                    "name": self.buyer_name,
                    "organization": "Agents Market",
                    "description": "Autonomous buyer for marketplace integrations",
                    "walletAddress": "",
                },
            )
            response.raise_for_status()
            buyer = response.json()["buyer"]
        self._buyer_id = int(buyer["id"])
        return BuyerProfile(
            id=self._buyer_id,
            name=str(buyer.get("name", self.buyer_name)),
            wallet_address=str(buyer.get("walletAddress", "")),
        )

    async def get_buyer(self, buyer_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
            response = await http.get(f"{self.server_url}/buyers/{buyer_id}")
            response.raise_for_status()
        return dict(response.json()["buyer"])

    async def discover(
        self,
        *,
        prompt: str,
        budget_usdc: Decimal,
        desired_tool: str = "auto",
        max_results: int = 5,
    ) -> list[ToolCandidate]:
        payload = {
            "prompt": prompt,
            "budgetUSDC": float(budget_usdc),
            "desiredTool": desired_tool,
            "maxResults": max_results,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
            response = await http.post(f"{self.server_url}/marketplace/discover", json=payload)
            response.raise_for_status()
            candidates = response.json().get("candidates", [])
        return [self._candidate_from_discover_row(row) for row in candidates if isinstance(row, dict)]

    async def list_tools(self) -> list[ToolCandidate]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
            response = await http.get(f"{self.server_url}/marketplace/tools")
            response.raise_for_status()
            tools = response.json().get("tools", [])
        return [self._candidate_from_marketplace_tool(tool) for tool in tools if isinstance(tool, dict)]

    def pick_best(
        self,
        *,
        desired_tool: str,
        budget_usdc: Decimal,
        candidates: list[ToolCandidate],
        fallback_tools: list[ToolCandidate] | None = None,
    ) -> tuple[ToolCandidate | None, str]:
        preferred_keys = {
            "plan": ["plan", "analyze", "summarize", "response"],
            "analyze": ["analyze", "summarize", "response", "plan"],
            "summarize": ["summarize", "response", "analyze", "plan"],
            "response": ["response", "summarize", "analyze", "plan"],
        }.get(desired_tool, ["summarize", "response", "analyze", "plan"])

        by_key = {item.tool_key: item for item in candidates}
        for key in preferred_keys:
            candidate = by_key.get(key)
            if candidate and budget_usdc >= candidate.price_usdc:
                if key == desired_tool:
                    return candidate, f"selected={key} (matches task)"
                return candidate, f"downgraded_to={key} (budget or preference)"

        for candidate in sorted(candidates, key=lambda item: item.price_usdc):
            if budget_usdc >= candidate.price_usdc:
                return candidate, f"downgraded_to={candidate.tool_key} (fallback)"

        for tool in sorted(fallback_tools or [], key=lambda item: item.price_usdc):
            if budget_usdc >= tool.price_usdc:
                return tool, f"downgraded_to={tool.tool_key} (marketplace fallback)"
        return None, "insufficient_budget_for_any_tool"

    async def invoke(
        self,
        *,
        candidate: ToolCandidate,
        prompt: str,
        selected_skills: list[str] | None = None,
        include_buyer_id: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"prompt": prompt, "selectedSkills": selected_skills or []}
        if include_buyer_id:
            buyer = await self.ensure_buyer()
            payload["buyerId"] = buyer.id

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
            response = await http.post(candidate.invoke_url, json=payload)
            response.raise_for_status()
        return dict(response.json())

    def desired_tool_from_prompt(self, *, task: str, prompt: str) -> str:
        normalized_task = task.strip().lower()
        if normalized_task in ("summarize", "analyze", "plan", "response"):
            return normalized_task
        lowered = prompt.lower()
        if any(token in lowered for token in ("roadmap", "milestone", "step-by-step", "sprint plan", "project plan")):
            return "plan"
        if any(token in lowered for token in ("analyze", "compare", "deep dive", "trade-off", "risk of")):
            return "analyze"
        return "summarize"

    def _candidate_from_discover_row(self, row: dict[str, Any]) -> ToolCandidate:
        candidate = row.get("candidate", row)
        return self._to_candidate(candidate)

    def _candidate_from_marketplace_tool(self, tool: dict[str, Any]) -> ToolCandidate:
        return self._to_candidate(tool)

    def _to_candidate(self, item: dict[str, Any]) -> ToolCandidate:
        tool_key = str(item.get("toolKey", "response"))
        price = Decimal(str(item.get("priceUSDC", 0)))
        invoke_url = str(item.get("invokeUrl", "")).strip()
        seller = item.get("seller", {}) if isinstance(item.get("seller"), dict) else {}
        agent = item.get("agent", {}) if isinstance(item.get("agent"), dict) else {}
        tool_id = item.get("toolId")
        seller_id = item.get("sellerId", seller.get("id"))
        agent_id = item.get("agentId", agent.get("id"))

        if invoke_url.startswith("/"):
            invoke_url = f"{self.server_url}{invoke_url}"
        if not invoke_url and seller_id and agent_id and tool_id:
            invoke_url = f"{self.server_url}/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke"
        if not invoke_url:
            raise ValueError(f"Could not resolve invoke URL for candidate {tool_key}")

        return ToolCandidate(
            tool_key=tool_key,
            price_usdc=price,
            invoke_url=invoke_url,
            source=str(item.get("source", "internal")),
            seller_id=int(seller_id) if isinstance(seller_id, int) else None,
            agent_id=int(agent_id) if isinstance(agent_id, int) else None,
            tool_id=int(tool_id) if isinstance(tool_id, int) else None,
            skills=item.get("skills") if isinstance(item.get("skills"), list) else [],
            raw=item,
        )
