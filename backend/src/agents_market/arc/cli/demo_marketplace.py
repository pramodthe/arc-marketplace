"""Seed and exercise a multi-seller marketplace demo for hackathon walkthroughs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request

from agents_market._env import load_backend_env

BASE_URL = "http://localhost:4021"


@dataclass
class SellerSeed:
    name: str
    description: str
    owner_wallet: str
    validator_wallet: str
    agent_name: str


def http_get(path: str) -> dict:
    with request.urlopen(f"{BASE_URL}{path}", timeout=20) as res:
        return json.loads(res.read().decode())


def http_post(path: str, payload: dict) -> dict:
    req = request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode())


def ensure_seller_and_agent(seed: SellerSeed) -> tuple[int, int]:
    sellers = http_get("/sellers")["sellers"]
    existing = next((s for s in sellers if s["name"] == seed.name), None)
    if existing is None:
        existing = http_post(
            "/sellers",
            {
                "name": seed.name,
                "description": seed.description,
                "ownerWalletAddress": seed.owner_wallet,
                "validatorWalletAddress": seed.validator_wallet,
            },
        )["seller"]
    seller_id = existing["id"]
    seller_details = http_get(f"/sellers/{seller_id}")
    agents = seller_details["agents"]
    match = next((a for a in agents if a["name"] == seed.agent_name), None)
    if match is None:
        match = http_post(
            f"/sellers/{seller_id}/agents",
            {
                "name": seed.agent_name,
                "description": "Hackathon marketplace demo agent",
                "metadataUri": "ipfs://bafkreibdi6623n3xpf7ymk62ckb4bo75o3qemwkpfvp5i25j66itxvsoei",
            },
        )["agent"]
    return seller_id, match["id"]


def main() -> None:
    load_backend_env()
    seeds = [
        SellerSeed(
            name=f"Seller-{idx:02d}",
            description=f"Mock-open marketplace seller {idx}",
            owner_wallet="0x9789AD5776fD505C026148bB989A69A0DcaC9D28",
            validator_wallet="0xaBB7D9CD054b1E78074c25f8E65c291015871847",
            agent_name=f"Agent-{idx:02d}",
        )
        for idx in range(1, 11)
    ]
    created = [ensure_seller_and_agent(seed) for seed in seeds]
    tools = http_get("/marketplace/tools")["tools"]
    print(f"Seeded/verified sellers+agents: {len(created)}")
    print(f"Marketplace tools available: {len(tools)}")
    if tools:
        sample = tools[0]
        print(
            "Sample invoke path: "
            f"/sellers/{sample['seller']['id']}/agents/{sample['agent']['id']}/tools/{sample['toolId']}/invoke"
        )


if __name__ == "__main__":
    main()
