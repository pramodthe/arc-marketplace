"""Deposit USDC into Circle Gateway (Arc testnet)."""

import argparse
import asyncio
import os
import sys

from agents_market._env import load_backend_env

try:
    from circlekit import GatewayClient
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'circlekit'. Install editable circle-titanoboa-sdk "
        "(see backend/README.md)."
    ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deposit USDC into Gateway")
    parser.add_argument(
        "--amount",
        "-a",
        default=os.getenv("DEPOSIT_AMOUNT", "1"),
        help="USDC amount to deposit",
    )
    return parser.parse_args()


async def _async_main() -> None:
    load_backend_env()
    args = parse_args()
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("Error: PRIVATE_KEY is required in .env")
        sys.exit(1)

    async with GatewayClient(chain="arcTestnet", private_key=private_key) as gateway:
        before = await gateway.get_balances()
        print(f"Wallet USDC: {before.wallet.formatted}")
        print(f"Gateway available: {before.gateway.formatted_available}")

        result = await gateway.deposit(args.amount)
        print(f"Deposit tx: {result.deposit_tx_hash}")

        after = await gateway.get_balances()
        print(f"Updated wallet USDC: {after.wallet.formatted}")
        print(f"Updated gateway available: {after.gateway.formatted_available}")


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
