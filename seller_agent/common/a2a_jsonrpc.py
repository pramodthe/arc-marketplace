"""A2A JSON-RPC helpers for sellers (Google ADK / a2a-sdk compatible).

The official client posts ``message/send`` with ``params.message`` (A2A Message) and
expects ``result`` to be a ``Message`` or ``Task`` — not a legacy custom envelope.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from a2a.types import Message, MessageSendParams, Part, Role, TextPart
from pydantic import ValidationError


def _jsonrpc_error(
    req_id: str | int | None, code: int, message: str
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def extract_user_text_from_message_send(body: dict[str, Any]) -> str:
    """Parse ``message/send`` body and return concatenated user text parts."""
    if body.get("method") != "message/send":
        raise ValueError(f"unsupported method: {body.get('method')!r}")
    params = MessageSendParams.model_validate(body.get("params") or {})
    chunks: list[str] = []
    for part in params.message.parts:
        root = part.root
        if isinstance(root, TextPart) and root.text:
            chunks.append(root.text)
    return "\n".join(chunks).strip()


def build_message_send_result(
    request_id: str | int | None, agent_text: str
) -> dict[str, Any]:
    """Successful ``message/send`` response with a single agent ``Message``."""
    from a2a.types import SendMessageSuccessResponse

    msg = Message(
        message_id=str(uuid.uuid4()),
        parts=[Part(root=TextPart(text=agent_text))],
        role=Role.agent,
    )
    return SendMessageSuccessResponse(id=request_id, result=msg).model_dump(
        mode="json",
        exclude_none=True,
    )


def handle_a2a_jsonrpc(
    body: dict[str, Any],
    *,
    run: Callable[[str], str],
    agent_label: str,
) -> dict[str, Any]:
    """Dispatch JSON-RPC methods for ``POST /a2a/message``."""
    req_id = body.get("id")
    if body.get("jsonrpc") != "2.0":
        return _jsonrpc_error(req_id, -32600, "Invalid Request: jsonrpc must be '2.0'")

    method = body.get("method")
    if method == "agent/getAuthenticatedExtendedCard":
        return _jsonrpc_error(
            req_id,
            -32007,
            "Authenticated Extended Card is not configured for this QA agent",
        )

    if method != "message/send":
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method!r}")

    try:
        prompt = extract_user_text_from_message_send(body)
    except ValidationError as exc:
        return _jsonrpc_error(req_id, -32602, f"Invalid params: {exc}")

    if not prompt:
        return _jsonrpc_error(req_id, -32602, "Empty user message (no text parts)")

    try:
        output = run(prompt)
    except Exception as exc:  # noqa: BLE001 — surface to client as agent failure
        output = f"{agent_label} failed: {exc}"

    return build_message_send_result(req_id, output)
