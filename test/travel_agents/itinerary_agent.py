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


app = FastAPI(title="Itinerary Writer Agent", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/invoke")
async def invoke(body: InvokeBody) -> dict[str, Any]:
    return {
        "agent": "itinerary_writer_agent",
        "promptReceived": body.prompt.strip(),
        "result": {
            "title": "Tokyo 4-Day Efficient Itinerary",
            "days": [
                "Day 1: Arrival, check-in, evening local walk.",
                "Day 2: Temple + market + museum route.",
                "Day 3: Neighborhood exploration + reservation dinner.",
                "Day 4: Buffer block + departure plan.",
            ],
            "travelStyle": "Balanced pace with practical transit planning.",
        },
        "summary": "Itinerary generated from upstream hotel and flight context.",
    }


if __name__ == "__main__":
    uvicorn.run(
        "itinerary_agent:app",
        host=os.getenv("TRAVEL_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("TRAVEL_AGENT_PORT", "5055")),
        reload=False,
        log_level="warning",
    )
