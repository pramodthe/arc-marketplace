#!/usr/bin/env python3
"""Example-only HTTP server for the autonomous buyer chat UI.

Does **not** modify ``arc-seller``. Run alongside the marketplace API:

  cd backend && uv sync --group llm-buyer
  uv run --group llm-buyer python ../examples/autonomous_marketplace_buyer/chat_server.py

Then open ``QA_test/autonomous_buyer_chat_demo.html`` (static server on ``QA_test/``) and set
**Chat / demo server URL** to ``http://localhost:9095`` (or ``AUTONOMOUS_BUYER_CHAT_PORT``).

Env: ``backend/.env`` + repo ``.env`` + ``examples/autonomous_marketplace_buyer/.env`` (see ``autonomous_llm_runner``).
Marketplace URL for tool calls: ``SERVER_URL`` / ``PUBLIC_BASE_URL`` (default ``http://localhost:4021``).
"""

from __future__ import annotations

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

from fastapi import FastAPI  # noqa: E402
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


@app.post("/demo/autonomous-llm-buyer/chat")
async def chat(body: ChatBody):
    return await run_autonomous_buyer_turn(body.message, include_trace=body.includeTrace)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "autonomous_marketplace_buyer_chat_example"}


def main() -> None:
    port = int(os.getenv("AUTONOMOUS_BUYER_CHAT_PORT", "9095"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
