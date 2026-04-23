from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

RUN_MODE = os.getenv("RUN_MODE", "chat").strip().lower()
BUYER_PROMPT = os.getenv("BUYER_PROMPT", "Add 18 and 24").strip()
BUYER_BUDGET_USDC = os.getenv("BUYER_BUDGET_USDC", "1.0").strip()
SERVICE_PRICE_USDC = os.getenv("SERVICE_PRICE_USDC", "0.01").strip()
REQUEST_TIMEOUT_SECONDS = os.getenv("REQUEST_TIMEOUT_SECONDS", "20").strip()
DEFAULT_AGENT_CARD_URL = "http://localhost:5051/.well-known/agent-card.json"
_raw_card_urls = os.getenv("AGENT_CARD_URLS", DEFAULT_AGENT_CARD_URL).strip()
AGENT_CARD_URLS = [item.strip() for item in _raw_card_urls.split(",") if item.strip()]
if not AGENT_CARD_URLS:
    AGENT_CARD_URLS = [DEFAULT_AGENT_CARD_URL]
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
BUYER_MODEL = os.getenv("BUYER_MODEL", "gpt-4o-mini").strip()
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "simulate").strip().lower()
X402_CHAIN = os.getenv("X402_CHAIN", "arcTestnet").strip()
X402_PRIVATE_KEY = os.getenv("X402_PRIVATE_KEY", "").strip()


def _parse_decimal(value: str, fallback: str) -> Decimal:
    try:
        parsed = Decimal(value)
        if parsed >= 0:
            return parsed
    except (InvalidOperation, ValueError):
        pass
    return Decimal(fallback)


def _parse_float(value: str, fallback: float) -> float:
    try:
        parsed = float(value)
        if parsed > 0:
            return parsed
    except ValueError:
        pass
    return fallback


def _build_invoke_url(base: str, path: str | None) -> str:
    if path and path.startswith("http"):
        return path
    if not path:
        return base
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _is_buy_intent(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in ("buy", "purchase", "invoke", "pay for", "find service", "discover"))


async def discover_services(timeout_seconds: float, default_price: Decimal) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for card_url in AGENT_CARD_URLS:
            try:
                card = (await client.get(card_url)).json()
            except Exception:
                continue

            base = str(card.get("url", "")).rstrip("/")
            provider = str(card.get("provider", {}).get("organization", card.get("name", "unknown-provider")))
            agent_name = str(card.get("name", "unknown-agent"))
            skills = card.get("skills", [])
            if not isinstance(skills, list):
                continue

            for skill in skills:
                if not isinstance(skill, dict):
                    continue
                invoke_url = _build_invoke_url(base, skill.get("path") or skill.get("endpoint"))
                price_raw = skill.get("x402PriceUSDC")
                try:
                    price_usdc = Decimal(str(price_raw)) if price_raw is not None else default_price
                except InvalidOperation:
                    price_usdc = default_price
                candidates.append(
                    {
                        "agentName": agent_name,
                        "provider": provider,
                        "skillId": str(skill.get("id", "unknown-skill")),
                        "skillName": str(skill.get("name", "Unknown Skill")),
                        "description": str(skill.get("description", "")),
                        "invokeUrl": invoke_url,
                        "priceUSDC": float(price_usdc),
                        "cardUrl": card_url,
                    }
                )
    return candidates


async def buy_service(invoke_url: str, prompt: str, timeout_seconds: float) -> dict[str, Any]:
    if PAYMENT_MODE == "x402":
        if not X402_PRIVATE_KEY:
            raise RuntimeError("X402_PRIVATE_KEY is required when PAYMENT_MODE=x402.")
        try:
            from circlekit import GatewayClient
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency 'circlekit'. Install circle-titanoboa-sdk with x402 support."
            ) from exc

        async with GatewayClient(chain=X402_CHAIN, private_key=X402_PRIVATE_KEY) as gateway:
            result = await gateway.pay(invoke_url, method="POST", body={"prompt": prompt})
            return {
                "paymentMode": "x402",
                "transactionRef": str(getattr(result, "transaction", "")),
                "amountUSDC": str(getattr(result, "formatted_amount", "")),
                "responseData": result.data if hasattr(result, "data") else {},
            }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(invoke_url, json={"prompt": prompt})
        response.raise_for_status()
        return {
            "paymentMode": "simulate",
            "transactionRef": "",
            "amountUSDC": "",
            "responseData": response.json(),
        }


async def _chat_completion(messages: list[dict[str, str]]) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required.")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": BUYER_MODEL,
                "temperature": 0.2,
                "messages": messages,
            },
        )
        response.raise_for_status()
        payload = response.json()
    choices = payload.get("choices", [])
    if not choices:
        raise RuntimeError("OpenAI returned no choices.")
    message = choices[0].get("message", {})
    return str(message.get("content", "")).strip() or "I have no response."


class BuyerChatbot:
    def __init__(self) -> None:
        self.default_price = _parse_decimal(SERVICE_PRICE_USDC, "0.01")
        self.remaining_budget = _parse_decimal(BUYER_BUDGET_USDC, "1.0")
        self.timeout_seconds = _parse_float(REQUEST_TIMEOUT_SECONDS, 20.0)
        self.history: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a buyer assistant chatbot. Answer questions clearly. "
                    "When service purchase context is provided, summarize what was discovered/bought and remaining budget."
                ),
            }
        ]

    async def handle_user_message(self, user_text: str) -> str:
        context_lines = [f"Remaining budget: {self.remaining_budget} USDC."]
        purchase_result: dict[str, Any] | None = None
        discovered: list[dict[str, Any]] = []

        if _is_buy_intent(user_text):
            discovered = await discover_services(self.timeout_seconds, self.default_price)
            affordable = [svc for svc in discovered if Decimal(str(svc["priceUSDC"])) <= self.remaining_budget]
            if affordable:
                selected = sorted(affordable, key=lambda item: Decimal(str(item["priceUSDC"])))[0]
                price = Decimal(str(selected["priceUSDC"]))
                response = await buy_service(str(selected["invokeUrl"]), user_text, self.timeout_seconds)
                self.remaining_budget -= price
                purchase_result = {
                    "status": "purchased",
                    "paymentMode": PAYMENT_MODE,
                    "service": selected,
                    "spentUSDC": float(price),
                    "remainingBudgetUSDC": float(self.remaining_budget),
                    "response": response,
                }
            else:
                purchase_result = {
                    "status": "skipped",
                    "reason": "No affordable discovered services",
                    "remainingBudgetUSDC": float(self.remaining_budget),
                }

            context_lines.append(
                "Discovery result: "
                + json.dumps(
                    {
                        "count": len(discovered),
                        "services": discovered[:5],
                        "purchaseResult": purchase_result,
                    },
                    ensure_ascii=True,
                )
            )

        self.history.append({"role": "user", "content": f"{user_text}\n\n" + "\n".join(context_lines)})
        reply = await _chat_completion(self.history[-10:])
        self.history.append({"role": "assistant", "content": reply})
        return reply


async def run_once_mode(chatbot: BuyerChatbot) -> None:
    reply = await chatbot.handle_user_message(BUYER_PROMPT)
    print(f"assistant: {reply}")
    print(f"remaining_budget_usdc={chatbot.remaining_budget}")


async def run_chat_mode(chatbot: BuyerChatbot) -> None:
    print("Buyer chatbot ready. Type a message, or 'exit' to quit.")
    print(f"Model: {BUYER_MODEL} | Remaining budget: {chatbot.remaining_budget} USDC")
    while True:
        user_text = (await asyncio.to_thread(input, "you> ")).strip()
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            print("bye.")
            break
        if user_text.lower() in {"/budget", "budget"}:
            print(f"assistant> Remaining budget: {chatbot.remaining_budget} USDC")
            continue
        try:
            reply = await chatbot.handle_user_message(user_text)
            print(f"assistant> {reply}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                print("assistant> OpenAI authentication failed (401). Check OPENAI_API_KEY in test/buyer_agent/.env")
                break
            print(f"assistant> HTTP error: {exc}")
        except Exception as exc:
            print(f"assistant> error: {exc}")


async def main() -> None:
    chatbot = BuyerChatbot()
    if RUN_MODE == "once":
        await run_once_mode(chatbot)
        return
    await run_chat_mode(chatbot)


if __name__ == "__main__":
    asyncio.run(main())
