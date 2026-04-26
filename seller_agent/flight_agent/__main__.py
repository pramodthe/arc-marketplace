from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "seller_agent.flight_agent.api:app",
        host=os.getenv("TRAVEL_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("TRAVEL_FLIGHT_AGENT_PORT", "5054")),
        reload=False,
        log_level="warning",
    )
