from __future__ import annotations

import os
from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel


class InvokeBody(BaseModel):
    prompt: str
    buyerId: int | None = None
    selectedSkills: list[str] = []
    billing: dict[str, Any] | None = None


app = FastAPI(title="Flight Booker Agent", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/invoke")
async def invoke(body: InvokeBody) -> dict[str, Any]:
    return {
        "agent": "flight_booker_agent",
        "promptReceived": body.prompt.strip(),
        "result": {
            "origin": "SFO",
            "destination": "NRT",
            "airline": "ANA",
            "departureDate": "2026-05-14",
            "returnDate": "2026-05-18",
            "estimatedTotalUSD": 980,
            "whyChosen": "Balanced timing with one short layover.",
        },
        "summary": "Flight options evaluated and best option selected.",
    }


if __name__ == "__main__":
    uvicorn.run(
        "flight_agent:app",
        host=os.getenv("TRAVEL_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("TRAVEL_AGENT_PORT", "5054")),
        reload=False,
        log_level="warning",
    )
