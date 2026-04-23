"""CLI entry: run the Arc buyer agent."""

import asyncio

from agents_market._env import load_backend_env
from agents_market.arc.buyer import run as buyer_run


def main() -> None:
    load_backend_env()
    asyncio.run(buyer_run.main())
