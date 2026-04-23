"""Register an Arc agent (ERC-8004) via reusable Arc service."""

import os

from agents_market._env import load_backend_env
from agents_market.arc.services.erc8004 import DEFAULT_METADATA_URI, register_agent_identity


def main() -> None:
    load_backend_env()
    metadata_uri = os.getenv("ARC_AGENT_METADATA_URI", DEFAULT_METADATA_URI)
    result = register_agent_identity(metadata_uri=metadata_uri)
    print("\nArc agent registration complete")
    print(f"Tx hash: {result.tx_hash}")
    print(f"Explorer: https://testnet.arcscan.app/tx/{result.tx_hash}")
    print(f"Owner wallet: {result.owner_wallet_address}")
    print(f"Validator wallet: {result.validator_wallet_address}")
    if result.agent_id:
        print(f"Agent ID (ERC-8004 tokenId): {result.agent_id}")
    else:
        print("Agent ID not found in Transfer logs at registration block.")


if __name__ == "__main__":
    main()
