"""CLI entry: run uvicorn for the Arc seller API."""

import os

import uvicorn

from agents_market._env import load_backend_env


def main() -> None:
    load_backend_env()
    port = int(os.getenv("PORT", "4021"))
    print(f"Arc marketplace API (FastAPI): http://0.0.0.0:{port}")
    print("Core: POST /sellers, POST /sellers/{id}/agents, GET /marketplace/tools")
    print("Paid invoke: POST /sellers/{sid}/agents/{aid}/tools/{tid}/invoke")
    print("Ledger: GET /transactions")
    from agents_market.arc.seller.app import app as seller_app

    uvicorn.run(seller_app, host="0.0.0.0", port=port)
