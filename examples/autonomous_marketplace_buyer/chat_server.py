#!/usr/bin/env python3
"""Example-only HTTP server for the autonomous buyer chat UI.

Does **not** modify ``arc-seller``. Run alongside the marketplace API:

  cd backend && uv sync --group llm-buyer
  uv run --group llm-buyer python ../examples/autonomous_marketplace_buyer/chat_server.py

Then open ``QA_test/autonomous_buyer_chat_demo.html`` (static server on ``QA_test/``) and set
**Chat / demo server URL** to ``http://localhost:9095`` (or ``AUTONOMOUS_BUYER_CHAT_PORT``).
Turns are capped by ``AUTONOMOUS_BUYER_REQUEST_TIMEOUT_SEC`` (default 180s) so the UI does not hang forever.

Env: ``backend/.env`` + repo ``.env`` + ``examples/autonomous_marketplace_buyer/.env`` (see ``autonomous_llm_runner``).
Marketplace URL for tool calls: ``SERVER_URL`` / ``PUBLIC_BASE_URL`` (default ``http://localhost:4021``).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Repo layout: .../agents_market/backend/src
_REPO = Path(__file__).resolve().parents[2]
_BACKEND_SRC = _REPO / "backend" / "src"
_EXAMPLE_DIR = Path(__file__).resolve().parent

if _BACKEND_SRC.is_dir():
    sys.path.insert(0, str(_BACKEND_SRC))
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))

from autonomous_llm_runner import run_autonomous_buyer_turn  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
import uvicorn  # noqa: E402


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    includeTrace: bool = False


app = FastAPI(title="Autonomous marketplace buyer (example chat server)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _chat_turn_timeout_sec() -> float:
    raw = os.getenv("AUTONOMOUS_BUYER_REQUEST_TIMEOUT_SEC", "180").strip()
    try:
        v = float(raw)
    except ValueError:
        return 180.0
    return max(30.0, min(v, 900.0))


@app.post("/demo/autonomous-llm-buyer/chat")
async def chat(body: ChatBody):
    timeout = _chat_turn_timeout_sec()
    try:
        return await asyncio.wait_for(
            run_autonomous_buyer_turn(body.message, include_trace=body.includeTrace),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": (
                    f"Autonomous buyer turn exceeded {timeout:.0f}s "
                    "(LLM + marketplace tools). Shorten the task, check API keys and "
                    f"{os.getenv('SERVER_URL', 'http://localhost:4021')}, or raise "
                    "AUTONOMOUS_BUYER_REQUEST_TIMEOUT_SEC."
                ),
            },
        ) from None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "autonomous_marketplace_buyer_chat_example"}


def main() -> None:
    port = int(os.getenv("AUTONOMOUS_BUYER_CHAT_PORT", "9095"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
