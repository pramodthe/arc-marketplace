"""QA travel buyer: Google ADK LlmAgent + A2A tools (direct ``message/send`` to mock sellers).

Run from QA_test (after `uv pip install 'google-adk[a2a]' httpx` and sellers on 5053–5055):

  export GOOGLE_API_KEY=...
  set -a && source .env && set +a
  .venv/bin/adk web buyer_agent --port 8080

Streamlit: `.venv/bin/streamlit run buyer_agent/streamlit_app.py --server.port 8501`

Sellers speak JSON-RPC at ``/a2a/message``. Optional env overrides: ``QA_HOTEL_A2A_URL``,
``QA_FLIGHT_A2A_URL``, ``QA_ITINERARY_A2A_URL`` (defaults ``http://127.0.0.1:5053–5055/a2a/message``).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.function_tool import FunctionTool

from buyer_agent.qa_buyer_adk.seller_a2a_tools import (
    query_flight_seller,
    query_hotel_seller,
    query_itinerary_seller,
)

_env = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env)

_model = os.getenv("GOOGLE_ADK_MODEL", "gemini-2.5-flash")

_instruction = """You are the travel buyer agent for local QA.
You MUST NOT invent hotels, flights, or itineraries. Use the provided tools only.

- query_hotel_seller: lodging, neighborhoods, nightly budget, hotel shortlists.
- query_flight_seller: routes, airports, dates, fares, layovers (mock data).
- query_itinerary_seller: multi-day plans, pacing, day-by-day schedules, "create an itinerary",
  trip timelines. Prefer this tool whenever the user wants a written itinerary or full trip plan.

You may call more than one tool if the user asks for hotels and flights together, etc.
After tool results return, summarize clearly for the user (headings or bullets when helpful)."""

root_agent = LlmAgent(
    name="qa_travel_buyer",
    model=_model,
    instruction=_instruction,
    tools=[
        FunctionTool(query_hotel_seller),
        FunctionTool(query_flight_seller),
        FunctionTool(query_itinerary_seller),
    ],
)
