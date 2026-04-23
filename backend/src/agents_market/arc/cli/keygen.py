"""Generate demo buyer/seller keypairs for Arc."""

from eth_account import Account

from agents_market._env import load_backend_env


def main() -> None:
    load_backend_env()
    buyer = Account.create()
    seller = Account.create()

    print("Generated Arc demo keys:\n")
    print(f"PRIVATE_KEY={buyer.key.hex()}")
    print(f"BUYER_ADDRESS={buyer.address}\n")
    print(f"SELLER_PRIVATE_KEY={seller.key.hex()}")
    print(f"SELLER_ADDRESS={seller.address}")


if __name__ == "__main__":
    main()
