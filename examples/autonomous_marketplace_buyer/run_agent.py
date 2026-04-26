#!/usr/bin/env python3
"""CLI entry for the autonomous LLM marketplace buyer (example folder only).

Implementation: ``autonomous_llm_runner.py`` in this directory. Chat UI: ``chat_server.py`` +
``autonomous_buyer_chat_demo.html`` (same folder).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Same-directory module when run as ``python ../examples/.../run_agent.py`` from ``backend/``
_EX = Path(__file__).resolve().parent
if str(_EX) not in sys.path:
    sys.path.insert(0, str(_EX))

from autonomous_llm_runner import run_autonomous_buyer_turn


def _user_message(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.message:
        return " ".join(args.message).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    parser.error("Provide the user goal as arguments or pipe it on stdin (non-TTY).")
    return ""


async def async_main() -> int:
    parser = argparse.ArgumentParser(description="LLM buyer agent over the marketplace")
    parser.add_argument(
        "message",
        nargs="*",
        help="User goal (optional if piping stdin)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print full agent message trace to stderr")
    args = parser.parse_args()

    user = _user_message(args, parser)
    if not user:
        print("Empty user message.", file=sys.stderr)
        return 1

    out = await run_autonomous_buyer_turn(user, include_trace=args.verbose)
    if not out.get("ok"):
        print(out.get("error", "unknown_error"), file=sys.stderr)
        return 1

    print(f"Using buyer id={out.get('buyerId')}", file=sys.stderr)
    print(f"LLM: {out.get('model')}", file=sys.stderr)
    if args.verbose and out.get("trace"):
        print(json.dumps(out["trace"], indent=2), file=sys.stderr)
    print(out.get("reply", ""))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
