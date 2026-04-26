"""
Streamlit UI for the QA buyer (Google ADK + direct A2A tools to mock sellers).

Run from QA_test (with sellers on 5053–5055):

  set -a && source .env && set +a
  .venv/bin/streamlit run buyer_agent/streamlit_app.py --server.port 8501
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

from google.adk.runners import InMemoryRunner

QA_ROOT = Path(__file__).resolve().parents[1]
if str(QA_ROOT) not in sys.path:
    sys.path.insert(0, str(QA_ROOT))

load_dotenv(QA_ROOT / ".env")

_BUYER_AGENT_SOURCES = (
    QA_ROOT / "buyer_agent" / "qa_buyer_adk" / "agent.py",
    QA_ROOT / "buyer_agent" / "qa_buyer_adk" / "seller_a2a_tools.py",
)


def _buyer_source_mtime() -> float:
    return max(p.stat().st_mtime for p in _BUYER_AGENT_SOURCES if p.exists())


def _root_agent_for_ui() -> Any:
    """Reload buyer agent when source changes (Streamlit often keeps stale modules)."""
    mt = _buyer_source_mtime()
    if (
        st.session_state.get("_buyer_src_mtime") != mt
        or "cached_root_agent" not in st.session_state
    ):
        import buyer_agent.qa_buyer_adk.agent as agent_mod
        import buyer_agent.qa_buyer_adk.seller_a2a_tools as tools_mod

        importlib.reload(tools_mod)
        importlib.reload(agent_mod)
        st.session_state._buyer_src_mtime = mt
        st.session_state.cached_root_agent = agent_mod.root_agent
        st.session_state.pop("buyer_runner", None)
    return st.session_state.cached_root_agent

SELLER_HEALTH_URLS = [
    ("Hotel :5053", "http://127.0.0.1:5053/health"),
    ("Flight :5054", "http://127.0.0.1:5054/health"),
    ("Itinerary :5055", "http://127.0.0.1:5055/health"),
]


def _seller_pulse() -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    with httpx.Client(timeout=2.0) as client:
        for label, url in SELLER_HEALTH_URLS:
            try:
                r = client.get(url)
                ok = r.status_code == 200 and "ok" in r.text.lower()
            except httpx.HTTPError:
                ok = False
            except OSError:
                ok = False
            out.append((label, ok))
    return out


def _events_summary(events: list) -> str:
    lines: list[str] = []
    for ev in events:
        if not getattr(ev, "content", None) or not ev.content.parts:
            continue
        author = getattr(ev, "author", "?")
        for part in ev.content.parts:
            if part.text:
                lines.append(f"{author}: {part.text.strip()[:4000]}")
            if part.function_call:
                lines.append(
                    f"{author} [call] {part.function_call.name}({part.function_call.args})"
                )
            if part.function_response:
                r = part.function_response.response
                lines.append(f"{author} [result] {str(r)[:3000]}")
    return "\n\n".join(lines) if lines else "(no events)"


def _last_assistant_text(events: list) -> str:
    for ev in reversed(events):
        if not getattr(ev, "content", None) or not ev.content.parts:
            continue
        for part in reversed(ev.content.parts):
            if part.text and part.text.strip():
                return part.text.strip()
    return ""


async def _run_buyer(
    runner: InMemoryRunner, prompt: str, *, session_id: str, verbose: bool
) -> tuple[str, str, list[str]]:
    events = await runner.run_debug(
        prompt,
        user_id="streamlit-user",
        session_id=session_id,
        verbose=verbose,
    )
    reply = _last_assistant_text(events)
    if not reply:
        reply = _events_summary(events)[:8000]
        
    agents_called = []
    for ev in events:
        if not getattr(ev, "content", None) or not ev.content.parts:
            continue
        for part in ev.content.parts:
            if part.function_call:
                name = part.function_call.name
                if name == "query_hotel_seller":
                    agents_called.append("Hotel Agent (A2A)")
                elif name == "query_flight_seller":
                    agents_called.append("Flight Agent (A2A)")
                elif name == "query_itinerary_seller":
                    agents_called.append("Itinerary Agent (A2A)")
                elif name not in agents_called:
                    agents_called.append(name)
                    
    # Remove duplicates preserving order
    agents_called = list(dict.fromkeys(agents_called))
    
    return reply, _events_summary(events), agents_called


def run_buyer_sync(
    runner: InMemoryRunner, prompt: str, *, session_id: str, verbose: bool
) -> tuple[str, str, list[str]]:
    return asyncio.run(_run_buyer(runner, prompt, session_id=session_id, verbose=verbose))


def main() -> None:
    st.set_page_config(
        page_title="QA travel buyer",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    gkey = os.getenv("GOOGLE_API_KEY", "").strip()
    model = os.getenv("GOOGLE_ADK_MODEL", "gemini-2.5-flash")

    st.title("QA travel buyer")
    st.caption(
        "Google ADK + A2A tools (query_itinerary_seller, …). "
        "Run sellers on 5053–5055. If you still see transfer_to_agent, refresh the page "
        "or click New conversation so the app picks up the latest buyer code."
    )

    status = _seller_pulse()
    gemini_ok = bool(gkey and gkey != "your_google_api_key")
    c0, c1, c2, c3 = st.columns(4)
    for col, (label, ok) in zip(
        [c0, c1, c2, c3],
        list(status) + [("Gemini API key", gemini_ok)],
    ):
        with col:
            st.metric(label, "reachable" if ok else "unreachable")

    if not gemini_ok:
        st.warning("Set a valid `GOOGLE_API_KEY` in `QA_test/.env`.")

    if "adk_session_id" not in st.session_state:
        st.session_state.adk_session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    root_agent = _root_agent_for_ui()
    if "buyer_runner" not in st.session_state:
        st.session_state.buyer_runner = InMemoryRunner(
            agent=root_agent, app_name="streamlit_buyer"
        )

    with st.sidebar:
        st.subheader("Session")
        st.text(st.session_state.adk_session_id)
        if st.button("New conversation"):
            st.session_state.adk_session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.buyer_runner = InMemoryRunner(
                agent=_root_agent_for_ui(), app_name="streamlit_buyer"
            )
            st.rerun()
        st.subheader("Model")
        st.code(model, language=None)
        verbose = st.checkbox("Show tool trace", value=False)
        st.subheader("Seller A2A URLs")
        st.caption(
            "Itineraries: model should call query_itinerary_seller (not transfer_to_agent)."
        )
        st.caption("Optional: QA_HOTEL_A2A_URL, QA_FLIGHT_A2A_URL, QA_ITINERARY_A2A_URL")
        st.text(
            "\n".join(
                [
                    os.getenv("QA_HOTEL_A2A_URL", "http://127.0.0.1:5053/a2a/message"),
                    os.getenv("QA_FLIGHT_A2A_URL", "http://127.0.0.1:5054/a2a/message"),
                    os.getenv(
                        "QA_ITINERARY_A2A_URL", "http://127.0.0.1:5055/a2a/message"
                    ),
                ]
            )
        )

    prompt = st.chat_input("Ask for hotels, flights, or a day-by-day itinerary…")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if m.get("agents_called"):
                st.caption("🤖 Agents consulted via A2A Protocol:")
                cols = st.columns(min(len(m["agents_called"]), 4))
                for i, agent_name in enumerate(m["agents_called"]):
                    cols[i % 4].success(agent_name)
            st.markdown(m["content"])

    if prompt:
        with st.chat_message("assistant"):
            with st.spinner("Calling buyer agent…"):
                try:
                    reply, trace, agents_called = run_buyer_sync(
                        st.session_state.buyer_runner,
                        prompt,
                        session_id=st.session_state.adk_session_id,
                        verbose=verbose,
                    )
                except Exception as exc:
                    st.error(f"{type(exc).__name__}: {exc}")
                    reply = str(exc)
                    trace = ""
                    agents_called = []
            
            if agents_called:
                st.caption("🤖 Agents consulted via A2A Protocol:")
                cols = st.columns(min(len(agents_called), 4))
                for i, agent_name in enumerate(agents_called):
                    cols[i % 4].success(agent_name)
                    
            st.markdown(reply or "_Empty reply_")
            if verbose and trace:
                with st.expander("ADK event trace"):
                    st.code(trace, language=None)
        st.session_state.messages.append({"role": "assistant", "content": reply, "agents_called": agents_called})


if __name__ == "__main__":
    main()
