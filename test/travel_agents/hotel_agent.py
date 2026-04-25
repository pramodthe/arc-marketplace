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


app = FastAPI(title="Hotel Finder Agent", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/invoke")
async def invoke(body: InvokeBody) -> dict[str, Any]:
    return {
        "agent": "hotel_finder_agent",
        "promptReceived": body.prompt.strip(),
        "result": {
            "city": "Tokyo",
            "nights": 4,
            "hotelName": "Shibuya Green Stay",
            "roomType": "Queen Room",
            "estimatedTotalUSD": 620,
            "whyChosen": "Near transit, good reviews, flexible cancellation.",
        },
        "summary": "Hotel shortlist complete.",
    }


if __name__ == "__main__":
    uvicorn.run(
        "hotel_agent:app",
        host=os.getenv("TRAVEL_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("TRAVEL_AGENT_PORT", "5053")),
        reload=False,
        log_level="warning",
    )
