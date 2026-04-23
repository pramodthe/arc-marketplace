from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

DEFAULT_MODEL = os.getenv("ALPHA_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


class InvokeBody(BaseModel):
    prompt: str = Field(..., min_length=1, description="Natural-language prompt for the math agent")


def add_numbers(a: float, b: float) -> dict:
    """Adds two numbers and returns the result."""
    result = a + b
    return {"operation": "add", "a": a, "b": b, "result": result}


def _fallback_math_response(prompt: str) -> str:
    numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", prompt)]
    if len(numbers) >= 2:
        result = numbers[0] + numbers[1]
        return f"The sum of {numbers[0]} and {numbers[1]} is {result}."
    return (
        "I could not call the OpenAI model and also could not find two numbers in your prompt. "
        "Try a prompt like: Add 20 and 22."
    )


def _public_base_url() -> str:
    return os.getenv("ALPHA_PUBLIC_BASE_URL", "http://localhost:5051").rstrip("/")


app = FastAPI(title="Agent Alpha", version="0.1.0")


async def _openai_chat_completion(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    payload: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("OpenAI returned no choices.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("OpenAI returned malformed message payload.")
    return message


async def _run_openai(prompt: str) -> str:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_numbers",
                "description": "Adds two numbers and returns the result.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"},
                    },
                    "required": ["a", "b"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are Agent Alpha, a precise math assistant. "
                "For addition tasks, call add_numbers and then respond concisely with the computed result."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    first_message = await _openai_chat_completion(messages, tools=tools)
    tool_calls = first_message.get("tool_calls") or []
    if not tool_calls:
        content = first_message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        raise RuntimeError("OpenAI returned no tool call or text response.")

    messages.append(first_message)
    for tool_call in tool_calls:
        if tool_call.get("type") != "function":
            continue
        function_data = tool_call.get("function") or {}
        if function_data.get("name") != "add_numbers":
            continue
        arguments_text = function_data.get("arguments", "{}")
        arguments = json.loads(arguments_text) if isinstance(arguments_text, str) else {}
        tool_result = add_numbers(float(arguments["a"]), float(arguments["b"]))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.get("id"),
                "content": json.dumps(tool_result),
            }
        )

    second_message = await _openai_chat_completion(messages)
    content = second_message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    raise RuntimeError("OpenAI follow-up response did not include content.")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "agent": "agent_alpha"}


@app.post("/invoke")
async def invoke(body: InvokeBody) -> dict:
    provider = "openai-chat-completions"
    try:
        output = await _run_openai(body.prompt)
    except Exception as exc:
        output = _fallback_math_response(body.prompt)
        provider = f"fallback ({exc.__class__.__name__})"

    return {
        "agent": "agent_alpha",
        "tool": "add_numbers",
        "model": DEFAULT_MODEL,
        "provider": provider,
        "outputText": output,
    }


@app.get("/.well-known/agent-card.json")
async def agent_card() -> dict:
    base = _public_base_url()
    return {
        "name": "Agent Alpha",
        "description": "Demo A2A math agent powered by OpenAI function tool calling.",
        "url": base,
        "provider": {"organization": "Agent Alpha Demo", "url": base},
        "version": "0.1.0",
        "documentationUrl": f"{base}/docs",
        "capabilities": {"streaming": False, "stateHistory": False},
        "authentication": {"type": "none", "instructions": "Local demo endpoint; no auth required."},
        "skills": [
            {
                "id": "alpha-math-add",
                "name": "Math Add",
                "description": "Adds numbers from a natural-language prompt.",
                "tags": ["math", "add", "openai", "function-calling", "a2a", "demo"],
                "examples": ["Add 12 and 30", "What is 11.5 + 9?"],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "path": "/invoke",
            }
        ],
    }


@app.get("/.well-known/ai-plugin.json")
async def ai_plugin_manifest() -> dict:
    base = _public_base_url()
    return {
        "schema_version": "v1",
        "name_for_human": "Agent Alpha",
        "name_for_model": "agent_alpha",
        "description_for_human": "Demo math agent with A2A-style metadata.",
        "description_for_model": "Send a prompt to /invoke and return computed math response.",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": f"{base}/openapi.yaml"},
        "logo_url": f"{base}/favicon.ico",
        "contact_email": "dev@localhost",
        "legal_info_url": base,
    }


@app.get("/openapi.yaml", response_class=Response)
async def openapi_yaml() -> Response:
    schema = app.openapi()
    content = yaml.safe_dump(schema, sort_keys=False)
    return Response(content=content, media_type="application/yaml")
