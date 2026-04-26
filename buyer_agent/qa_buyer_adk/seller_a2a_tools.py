"""Direct A2A ``message/send`` calls to QA mock sellers (reliable vs transfer + RemoteA2aAgent).

``transfer_to_agent`` returns no payload by design; the model must still run follow-up
steps. Tool calls return full seller text in one turn, which works better with Gemini
here.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx

_DEFAULT_HOTEL = "http://127.0.0.1:5053/a2a/message"
_DEFAULT_FLIGHT = "http://127.0.0.1:5054/a2a/message"
_DEFAULT_ITINERARY = "http://127.0.0.1:5055/a2a/message"


def _a2a_url(env_key: str, default: str) -> str:
    return (os.getenv(env_key) or default).strip()


def _message_send_body(user_text: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": user_text}],
            }
        },
    }


def _extract_reply_text(data: dict[str, Any]) -> str:
    if err := data.get("error"):
        return f"A2A JSON-RPC error: {err}"
    result = data.get("result")
    if not result:
        return f"Empty A2A result: {json.dumps(data)[:500]}"
        
    # Handle modern a2a-sdk format where result has a "message" key
    if isinstance(result, dict):
        message = result.get("message")
        
        # Fallback to checking if result itself is the message (legacy)
        if not message and result.get("role") in ["agent", "user"]:
            message = result
            
        if message:
            parts = message.get("parts") or []
            chunks: list[str] = []
            for p in parts:
                if isinstance(p, dict):
                    # a2a.types uses "type" or "kind" depending on version
                    text = p.get("text")
                    if text:
                        chunks.append(str(text))
            if chunks:
                return "\n".join(chunks)

    # Task or unknown shape — return compact JSON for debugging
    return json.dumps(result, indent=2)[:12000]


def _post_a2a(url: str, user_text: str, *, timeout: float = 120.0) -> str:
    body = _message_send_body(user_text)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        return f"HTTP error calling {url}: {exc}"
    except json.JSONDecodeError as exc:
        return f"Invalid JSON from {url}: {exc}"
    return _extract_reply_text(data)


def query_hotel_seller(user_request: str) -> str:
    """Return mock hotel recommendations for the user's question (local seller :5053)."""
    url = _a2a_url("QA_HOTEL_A2A_URL", _DEFAULT_HOTEL)
    return _post_a2a(url, user_request.strip())


def query_flight_seller(user_request: str) -> str:
    """Return mock flight options for the user's question (local seller :5054)."""
    url = _a2a_url("QA_FLIGHT_A2A_URL", _DEFAULT_FLIGHT)
    return _post_a2a(url, user_request.strip())


def query_itinerary_seller(user_request: str) -> str:
    """Return a day-by-day itinerary from the LLM-backed seller (:5055). Use for 'create an itinerary' requests."""
    url = _a2a_url("QA_ITINERARY_A2A_URL", _DEFAULT_ITINERARY)
    return _post_a2a(url, user_request.strip())
