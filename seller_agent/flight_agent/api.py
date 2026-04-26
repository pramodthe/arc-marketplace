from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from seller_agent.common.a2a_jsonrpc import handle_a2a_jsonrpc

from .agent import FlightBookingAgent
from .schemas import InvokeBody

app = FastAPI(title="Flight Booker Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
agent = FlightBookingAgent()
AGENT_CARD_PATH = Path(__file__).with_name("agent-card.json")
SAMPLE_TOOL_CALLS_PATH = Path(__file__).with_name("sample_tool_calls.json")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/.well-known/agent-card.json")
async def agent_card() -> dict[str, Any]:
    return json.loads(AGENT_CARD_PATH.read_text(encoding="utf-8"))


@app.get("/samples/tool-calls")
async def sample_tool_calls() -> dict[str, Any]:
    return json.loads(SAMPLE_TOOL_CALLS_PATH.read_text(encoding="utf-8"))


@app.post("/invoke")
async def invoke(body: InvokeBody) -> dict[str, Any]:
    prompt = body.prompt.strip()
    try:
        recommendation = agent.run(prompt)
    except Exception as exc:
        recommendation = f"Flight recommendation failed: {exc}"

    return {
        "agent": "flight_booker_agent",
        "promptReceived": prompt,
        "result": {"recommendation": recommendation},
        "summary": "Flight options generated from internal mock simulation data.",
    }


@app.post("/a2a/message")
async def a2a_message(
    body: Annotated[dict[str, Any], Body()],
) -> dict[str, Any]:
    return handle_a2a_jsonrpc(
        body,
        run=agent.run,
        agent_label="Flight recommendation",
    )


@app.post("/a2s/invoke")
async def a2s_invoke(
    body: Annotated[dict[str, Any], Body()],
) -> dict[str, Any]:
    return await a2a_message(body)
