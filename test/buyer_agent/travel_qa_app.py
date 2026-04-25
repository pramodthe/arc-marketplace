from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
SNAPSHOT_PATH = RUNTIME_DIR / "travel_agent_wallets.json"
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:4021").rstrip("/")
TRAVEL_PROVIDER_HOST = os.getenv("TRAVEL_PROVIDER_HOST", "127.0.0.1").strip()
TIMEOUT_SECONDS = float(os.getenv("TRAVEL_DEMO_TIMEOUT_SECONDS", "20"))
DEFAULT_BUDGET = Decimal(os.getenv("TRAVEL_BUDGET_USDC", "0.08"))


@dataclass
class ProviderSpec:
    script_name: str
    port: str
    seller_name: str
    seller_description: str
    agent_name: str
    agent_description: str


PROVIDERS: list[ProviderSpec] = [
    ProviderSpec(
        script_name="hotel_agent.py",
        port="5053",
        seller_name="Travel Hotel Seller",
        seller_description="Hotel discovery specialist for travel planning.",
        agent_name="Travel Hotel Agent",
        agent_description="Finds hotels by city, stay length, and budget constraints.",
    ),
    ProviderSpec(
        script_name="flight_agent.py",
        port="5054",
        seller_name="Travel Flight Seller",
        seller_description="Flight recommendation specialist for travel routes.",
        agent_name="Travel Flight Agent",
        agent_description="Finds flight options with routing and timing constraints.",
    ),
    ProviderSpec(
        script_name="itinerary_agent.py",
        port="5055",
        seller_name="Travel Itinerary Seller",
        seller_description="Itinerary synthesis specialist for trip planning.",
        agent_name="Travel Itinerary Agent",
        agent_description="Builds day-by-day trip plans from upstream outputs.",
    ),
]


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class BootstrapBody(BaseModel):
    force: bool = False


class QaRuntime:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._agent_processes: list[subprocess.Popen[Any]] = []
        self._travel_agents_dir = BASE_DIR.parent / "travel_agents"
        self._session: dict[str, Any] = {
            "bootstrapped": False,
            "buyer": None,
            "providers": [],
            "chat": [],
            "hops": [],
            "lastUpdatedAt": None,
        }

    async def _ensure_runtime_dir(self) -> None:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    async def _start_provider_servers(self) -> None:
        await self._ensure_runtime_dir()
        for spec in PROVIDERS:
            script_path = self._travel_agents_dir / spec.script_name
            env = os.environ.copy()
            env["TRAVEL_AGENT_HOST"] = TRAVEL_PROVIDER_HOST
            env["TRAVEL_AGENT_PORT"] = spec.port
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                env=env,
                cwd=str(self._travel_agents_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._agent_processes.append(process)
        await asyncio.sleep(1.0)

    async def shutdown(self) -> None:
        for process in self._agent_processes:
            if process.poll() is None:
                process.terminate()
        for process in self._agent_processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        self._agent_processes.clear()

    async def _healthcheck_provider(self, client: httpx.AsyncClient, port: str) -> bool:
        url = f"http://{TRAVEL_PROVIDER_HOST}:{port}/health"
        try:
            response = await client.get(url)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def _ensure_provider_servers(self) -> None:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            healthy = await asyncio.gather(*(self._healthcheck_provider(client, spec.port) for spec in PROVIDERS))
        if all(healthy):
            return
        await self._start_provider_servers()
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            healthy_after = await asyncio.gather(
                *(self._healthcheck_provider(client, spec.port) for spec in PROVIDERS)
            )
        if not all(healthy_after):
            raise HTTPException(status_code=500, detail="Could not start all local travel provider agents.")

    def _provider_invoke_url(self, port: str) -> str:
        return f"http://{TRAVEL_PROVIDER_HOST}:{port}/invoke"

    def _provider_docs_url(self, port: str) -> str:
        return f"http://{TRAVEL_PROVIDER_HOST}:{port}/docs"

    async def _create_buyer(self, client: httpx.AsyncClient) -> int:
        response = await client.post(
            f"{SERVER_URL}/buyers",
            json={
                "name": "Travel QA Buyer",
                "organization": "Agents Market QA",
                "description": "Buyer used for travel multi-hop QA dashboard.",
                "walletAddress": "",
                "validatorWalletAddress": "",
            },
        )
        response.raise_for_status()
        return int(response.json()["buyer"]["id"])

    async def _create_seller(self, client: httpx.AsyncClient, name: str, description: str) -> int:
        response = await client.post(
            f"{SERVER_URL}/sellers",
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
    ) -> dict[str, Any]:
        response = await client.post(
            f"{SERVER_URL}/sellers/{seller_id}/agents",
            json={
                "name": name,
                "description": description,
                "category": "Travel",
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
        return response.json()

    async def _fetch_buyer(self, client: httpx.AsyncClient, buyer_id: int) -> dict[str, Any]:
        response = await client.get(f"{SERVER_URL}/buyers/{buyer_id}")
        response.raise_for_status()
        return response.json()

    async def _fetch_seller(self, client: httpx.AsyncClient, seller_id: int) -> dict[str, Any]:
        response = await client.get(f"{SERVER_URL}/sellers/{seller_id}")
        response.raise_for_status()
        return response.json()

    async def _persist_snapshot(self, payload: dict[str, Any]) -> None:
        await self._ensure_runtime_dir()
        SNAPSHOT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _extract_tasks(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text.strip())
        for pattern in (r"\band then\b", r"\bthen\b", r"\balso\b", r"\bnext\b", r"\bafter that\b"):
            normalized = re.sub(pattern, " || ", normalized, flags=re.IGNORECASE)
        tasks = [chunk.strip(" .,!") for chunk in normalized.split("||") if chunk.strip(" .,!?")]
        return tasks or [text.strip()]

    async def _discover_candidate(
        self,
        client: httpx.AsyncClient,
        *,
        prompt: str,
        remaining_budget: Decimal,
        exclude_agent_ids: set[int],
    ) -> dict[str, Any]:
        response = await client.post(
            f"{SERVER_URL}/marketplace/discover",
            json={
                "prompt": prompt,
                "budgetUSDC": float(remaining_budget),
                "desiredTool": "auto",
                "maxResults": 10,
            },
        )
        response.raise_for_status()
        rows = response.json().get("candidates", [])
        if not rows:
            raise HTTPException(status_code=400, detail=f"No marketplace candidates for task: {prompt}")
        for row in rows:
            candidate = row.get("candidate", {})
            agent_id = int(candidate.get("agent", {}).get("id", 0) or 0)
            if agent_id and agent_id not in exclude_agent_ids:
                return candidate
        return rows[0].get("candidate", {})

    async def _invoke_hop(
        self,
        client: httpx.AsyncClient,
        *,
        candidate: dict[str, Any],
        task: str,
        buyer_id: int,
    ) -> dict[str, Any]:
        invoke_url = (
            f"{SERVER_URL}/sellers/{candidate['seller']['id']}/agents/{candidate['agent']['id']}"
            f"/tools/{candidate['toolId']}/invoke"
        )
        response = await client.post(invoke_url, json={"prompt": task, "buyerId": buyer_id})
        response.raise_for_status()
        return {"invokeUrl": invoke_url, "response": response.json()}

    async def bootstrap(self, force: bool = False) -> dict[str, Any]:
        async with self._lock:
            if self._session["bootstrapped"] and not force:
                return self._session
            await self._ensure_provider_servers()
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                buyer_id = await self._create_buyer(client)
                buyer_payload = await self._fetch_buyer(client, buyer_id)

                providers_payload: list[dict[str, Any]] = []
                for spec in PROVIDERS:
                    seller_id = await self._create_seller(client, spec.seller_name, spec.seller_description)
                    created_agent = await self._create_agent(
                        client,
                        seller_id=seller_id,
                        name=spec.agent_name,
                        description=spec.agent_description,
                        endpoint_url=self._provider_invoke_url(spec.port),
                        api_docs_url=self._provider_docs_url(spec.port),
                    )
                    seller_payload = await self._fetch_seller(client, seller_id)
                    providers_payload.append(
                        {
                            "providerPort": spec.port,
                            "providerScript": spec.script_name,
                            "seller": seller_payload.get("seller", {}),
                            "agent": created_agent.get("agent", {}),
                        }
                    )

            snapshot = {
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "buyer": buyer_payload.get("buyer", {}),
                "buyerBalances": buyer_payload.get("balances", {}),
                "providers": providers_payload,
            }
            await self._persist_snapshot(snapshot)

            self._session.update(
                {
                    "bootstrapped": True,
                    "buyer": buyer_payload.get("buyer", {}),
                    "providers": providers_payload,
                    "chat": [],
                    "hops": [],
                    "lastUpdatedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
            return self._session

    async def handle_chat(self, user_message: str) -> dict[str, Any]:
        async with self._lock:
            if not self._session["bootstrapped"]:
                raise HTTPException(status_code=400, detail="Run bootstrap first.")
            buyer = self._session.get("buyer") or {}
            buyer_id = int(buyer.get("id", 0) or 0)
            if buyer_id <= 0:
                raise HTTPException(status_code=400, detail="Buyer not available in session.")

            tasks = self._extract_tasks(user_message)
            remaining = DEFAULT_BUDGET
            used_agent_ids: set[int] = set()
            hop_records: list[dict[str, Any]] = []
            previous_outputs: list[dict[str, Any]] = []

            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                for hop_index, task in enumerate(tasks, start=1):
                    context_suffix = ""
                    if previous_outputs:
                        context_suffix = (
                            "\n\nUse context from previous hops:\n"
                            + json.dumps(previous_outputs[-2:], ensure_ascii=True)
                        )
                    candidate = await self._discover_candidate(
                        client,
                        prompt=task + context_suffix,
                        remaining_budget=remaining,
                        exclude_agent_ids=used_agent_ids,
                    )
                    used_agent_ids.add(int(candidate["agent"]["id"]))
                    invoke = await self._invoke_hop(
                        client,
                        candidate=candidate,
                        task=task + context_suffix,
                        buyer_id=buyer_id,
                    )
                    invoke_payload = invoke["response"]
                    payment = invoke_payload.get("payment", {})
                    spent = Decimal(str(payment.get("amountUSDC", "0") or "0"))
                    if spent > 0:
                        remaining -= spent
                    hop_record = {
                        "hop": hop_index,
                        "task": task,
                        "candidate": candidate,
                        "invokeUrl": invoke["invokeUrl"],
                        "spentUSDC": float(spent),
                        "remainingBudgetUSDC": float(remaining),
                        "payment": payment,
                        "providerResponse": invoke_payload.get("providerResponse", {}),
                        "completedAt": datetime.now(timezone.utc).isoformat(),
                    }
                    hop_records.append(hop_record)
                    previous_outputs.append(invoke_payload.get("providerResponse", {}))

            assistant_text = (
                f"Completed {len(hop_records)} hop(s). "
                f"Remaining budget: {remaining:.6f} USDC. "
                "See Transactions page for live payment and seller output events."
            )
            chat_item = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user_message,
                "assistant": assistant_text,
                "hops": hop_records,
            }
            self._session["chat"].append(chat_item)
            self._session["hops"] = hop_records
            self._session["lastUpdatedAt"] = datetime.now(timezone.utc).isoformat()
            return chat_item

    async def fetch_transactions(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(f"{SERVER_URL}/transactions")
            response.raise_for_status()
            payload = response.json()
        events = payload.get("events", [])
        return {
            "summary": payload.get("summary", {}),
            "events": events[-80:],
            "buyers": payload.get("buyers", []),
        }

    def get_state(self) -> dict[str, Any]:
        state = dict(self._session)
        state["walletSnapshotPath"] = str(SNAPSHOT_PATH)
        return state


qa_runtime = QaRuntime()
app = FastAPI(title="Travel QA UI", version="0.1.0")


CHATBOT_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Travel Buyer Chatbot QA</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 24px; background: #0b1020; color: #e4e9ff; }
      .row { display: flex; gap: 12px; margin-bottom: 12px; }
      .btn { background: #355bff; color: #fff; border: none; border-radius: 8px; padding: 10px 14px; cursor: pointer; }
      .btn.secondary { background: #334155; }
      textarea { width: 100%; min-height: 96px; padding: 10px; border-radius: 8px; border: 1px solid #334155; background: #10172a; color: #e4e9ff; }
      #log { margin-top: 14px; background: #10172a; border: 1px solid #334155; border-radius: 10px; padding: 12px; max-height: 60vh; overflow: auto; }
      .item { border-bottom: 1px solid #1e293b; padding: 10px 0; }
      .muted { color: #93a0c7; font-size: 12px; }
      .tag { display: inline-block; border: 1px solid #334155; border-radius: 999px; padding: 2px 8px; margin-right: 6px; font-size: 12px; color: #a5b4fc; }
      a { color: #93c5fd; }
    </style>
  </head>
  <body>
    <h1>Travel Multi-Agent Buyer Chatbot</h1>
    <p>Run QA flows and open <a href="/transactions-ui" target="_blank">Transactions UI</a> to watch payment + output events update live.</p>
    <div class="row">
      <button id="bootstrapBtn" class="btn">Bootstrap Buyer + Travel Agents</button>
      <button id="refreshBtn" class="btn secondary">Refresh State</button>
    </div>
    <div id="state" class="muted"></div>
    <hr />
    <textarea id="message">Plan Tokyo travel: find hotel then find flight then create itinerary.</textarea>
    <div class="row">
      <button id="sendBtn" class="btn">Run Multi-Hop Purchase</button>
    </div>
    <div id="log"></div>
    <script>
      const stateEl = document.getElementById("state");
      const logEl = document.getElementById("log");

      function renderChat(items) {
        logEl.innerHTML = "";
        items.forEach((item) => {
          const div = document.createElement("div");
          div.className = "item";
          const hops = (item.hops || []).map((hop) =>
            `<div><span class="tag">Hop ${hop.hop}</span>${hop.candidate?.agent?.name || "agent"} | spent ${hop.spentUSDC} USDC</div>`
          ).join("");
          div.innerHTML = `
            <div class="muted">${item.timestamp || ""}</div>
            <div><strong>You:</strong> ${item.user || ""}</div>
            <div><strong>Assistant:</strong> ${item.assistant || ""}</div>
            <div>${hops}</div>
          `;
          logEl.appendChild(div);
        });
      }

      async function refreshState() {
        const res = await fetch("/api/state");
        const data = await res.json();
        stateEl.textContent = `bootstrapped=${data.bootstrapped} | buyer=${data.buyer?.id || "-"} | walletSnapshot=${data.walletSnapshotPath}`;
        renderChat(data.chat || []);
      }

      document.getElementById("bootstrapBtn").addEventListener("click", async () => {
        await fetch("/api/bootstrap", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: true }) });
        await refreshState();
      });

      document.getElementById("refreshBtn").addEventListener("click", refreshState);

      document.getElementById("sendBtn").addEventListener("click", async () => {
        const message = document.getElementById("message").value.trim();
        if (!message) return;
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || "Chat failed");
          return;
        }
        await refreshState();
      });

      refreshState();
    </script>
  </body>
</html>
"""


TRANSACTIONS_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Travel Transactions QA</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 24px; background: #050816; color: #e2e8f0; }
      table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
      th, td { border: 1px solid #1e293b; padding: 8px; text-align: left; vertical-align: top; }
      th { background: #0f172a; }
      pre { white-space: pre-wrap; margin: 0; color: #cbd5e1; }
      .muted { color: #94a3b8; font-size: 12px; }
      .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
      .card { border: 1px solid #1e293b; border-radius: 10px; padding: 10px; background: #0b1226; }
      a { color: #93c5fd; }
    </style>
  </head>
  <body>
    <h1>Transactions Live QA Dashboard</h1>
    <p class="muted">Auto-refresh every 2 seconds. Drive flows from <a href="/chatbot" target="_blank">Chatbot page</a>.</p>
    <div class="grid">
      <div class="card"><div class="muted">Total Events</div><div id="eventsCount">0</div></div>
      <div class="card"><div class="muted">Total Paid USDC</div><div id="totalPaid">0</div></div>
      <div class="card"><div class="muted">Last Refresh</div><div id="refreshedAt">-</div></div>
    </div>
    <h3>Current Hop Trace</h3>
    <div id="hops"></div>
    <h3>Recent Events</h3>
    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Event</th>
          <th>Status</th>
          <th>Reference</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
    <script>
      function safe(v) { return (v ?? "").toString(); }
      async function refresh() {
        const [txRes, stateRes] = await Promise.all([fetch("/api/transactions"), fetch("/api/state")]);
        const tx = await txRes.json();
        const state = await stateRes.json();
        const events = tx.events || [];
        document.getElementById("eventsCount").textContent = events.length;
        document.getElementById("totalPaid").textContent = safe(tx.summary?.totalPaidUSDC || tx.summary?.totalAmountUSDC || 0);
        document.getElementById("refreshedAt").textContent = new Date().toLocaleTimeString();

        const hops = state.hops || [];
        document.getElementById("hops").innerHTML = hops.length
          ? hops.map((h) => `<div>Hop ${h.hop}: ${safe(h.candidate?.agent?.name)} | spent ${safe(h.spentUSDC)} USDC</div>`).join("")
          : "<div class='muted'>No hops yet. Trigger a run on the Chatbot page.</div>";

        const rows = document.getElementById("rows");
        rows.innerHTML = "";
        events.slice().reverse().forEach((event) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${safe(event.createdAt || event.timestamp)}</td>
            <td>${safe(event.eventType)}</td>
            <td>${safe(event.status)}</td>
            <td>${safe(event.gatewayReference || event.onchainTxHash || "")}</td>
            <td><pre>${JSON.stringify(event.details || {}, null, 2)}</pre></td>
          `;
          rows.appendChild(tr);
        });
      }
      setInterval(refresh, 2000);
      refresh();
    </script>
  </body>
</html>
"""


@app.on_event("shutdown")
async def _shutdown() -> None:
    await qa_runtime.shutdown()


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return '<html><body><h2>Travel QA UI</h2><a href="/chatbot">Chatbot</a> | <a href="/transactions-ui">Transactions UI</a></body></html>'


@app.get("/chatbot", response_class=HTMLResponse)
async def chatbot_page() -> str:
    return CHATBOT_HTML


@app.get("/transactions-ui", response_class=HTMLResponse)
async def transactions_page() -> str:
    return TRANSACTIONS_HTML


@app.post("/api/bootstrap")
async def bootstrap_endpoint(body: BootstrapBody) -> dict[str, Any]:
    state = await qa_runtime.bootstrap(force=body.force)
    return {"ok": True, "state": state}


@app.post("/api/chat")
async def chat_endpoint(body: ChatBody) -> dict[str, Any]:
    item = await qa_runtime.handle_chat(body.message)
    return {"ok": True, "message": item}


@app.get("/api/state")
async def state_endpoint() -> dict[str, Any]:
    return qa_runtime.get_state()


@app.get("/api/transactions")
async def transactions_endpoint() -> dict[str, Any]:
    return await qa_runtime.fetch_transactions()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "travel_qa_app:app",
        host=os.getenv("TRAVEL_QA_UI_HOST", "127.0.0.1"),
        port=int(os.getenv("TRAVEL_QA_UI_PORT", "7070")),
        reload=False,
    )
