from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MessagePart(BaseModel):
    type: str = "text"
    text: str


class A2AMessage(BaseModel):
    role: str = "user"
    parts: list[MessagePart] = Field(default_factory=list)


class A2ARequestParams(BaseModel):
    prompt: str | None = None
    message: A2AMessage | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ARequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str = "message/send"
    params: A2ARequestParams = Field(default_factory=A2ARequestParams)


class A2AResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: dict[str, Any]


def extract_prompt(params: A2ARequestParams) -> str:
    if params.prompt and params.prompt.strip():
        return params.prompt.strip()
    if params.message:
        text = " ".join(part.text for part in params.message.parts if part.type == "text").strip()
        if text:
            return text
    return ""
