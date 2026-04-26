"""Arc USDC wallet balance and transfer helpers."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from circle.web3 import developer_controlled_wallets, utils
from circle.web3.developer_controlled_wallets import TransferBlockchain
from circle.web3.developer_controlled_wallets.models.create_transfer_transaction_for_developer_request_blockchain import (
    CreateTransferTransactionForDeveloperRequestBlockchain,
)
from eth_account import Account
from web3 import Web3

ARC_TESTNET = "ARC-TESTNET"
ARC_TESTNET_CHAIN_ID = 5042002
ARC_TESTNET_USDC = "0x3600000000000000000000000000000000000000"
ARC_RPC_URL = "https://rpc.testnet.arc.network"
USDC_DECIMALS = Decimal("1000000")
USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


@dataclass
class OnchainPaymentResult:
    tx_id: str
    tx_hash: str
    amount_usdc: str
    source_wallet_address: str
    destination_wallet_address: str


def _normalize_tx_hash(tx_hash: str) -> str:
    normalized = (tx_hash or "").strip()
    if normalized.startswith("0x"):
        return normalized.lower()
    if len(normalized) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in normalized):
        return f"0x{normalized.lower()}"
    return normalized


def _web3() -> Web3:
    web3 = Web3(Web3.HTTPProvider(os.getenv("ARC_RPC_URL", ARC_RPC_URL)))
    chain_id = int(web3.eth.chain_id)
    if chain_id != ARC_TESTNET_CHAIN_ID:
        raise RuntimeError(
            f"ARC RPC chain mismatch: expected {ARC_TESTNET_CHAIN_ID}, got {chain_id}. "
            "Refusing to continue to avoid wrong-network transfers."
        )
    return web3


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def wallets_client():
    return utils.init_developer_controlled_wallets_client(
        api_key=_required_env("CIRCLE_API_KEY"),
        entity_secret=_required_env("CIRCLE_ENTITY_SECRET"),
    )


def derive_wallet_id_by_address(wallet_address: str) -> str | None:
    if not wallet_address:
        return None
    client = wallets_client()
    wallets_api = developer_controlled_wallets.WalletsApi(client)
    request = developer_controlled_wallets.DeriveWalletByAddressRequest(
        sourceBlockchain=ARC_TESTNET,
        walletAddress=wallet_address,
        targetBlockchain=ARC_TESTNET,
    )
    response = wallets_api.derive_wallet_by_address(request)
    payload = response.to_dict() if hasattr(response, "to_dict") else {}
    wallet = payload.get("data", {}).get("wallet") or {}
    wallet_id = wallet.get("id")
    return str(wallet_id) if wallet_id else None


def wait_for_transaction_hash(
    transactions_api: developer_controlled_wallets.TransactionsApi,
    tx_id: str,
    *,
    timeout_seconds: int = 180,
) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        tx = transactions_api.get_transaction(id=tx_id).data.transaction
        if tx.state == "COMPLETE" and tx.tx_hash:
            return _normalize_tx_hash(tx.tx_hash)
        if tx.state in {"FAILED", "DENIED", "CANCELLED"}:
            raise RuntimeError(f"Transaction failed with state={tx.state}")
        time.sleep(3)
    raise TimeoutError("Timed out waiting for transaction completion")


def transfer_usdc(
    *,
    wallet_id: str | None,
    wallet_address: str,
    destination_address: str,
    amount_usdc: Decimal,
    ref_id: str,
) -> OnchainPaymentResult:
    client = wallets_client()
    transactions_api = developer_controlled_wallets.TransactionsApi(client)
    blockchain = CreateTransferTransactionForDeveloperRequestBlockchain(TransferBlockchain.ARC_MINUS_TESTNET)
    # Circle API: walletId XOR walletAddress — never send both.
    wid = (wallet_id or "").strip()
    waddr = (wallet_address or "").strip()
    if not wid and not waddr:
        raise ValueError("transfer_usdc requires wallet_id or wallet_address")
    kwargs: dict[str, Any] = {
        "idempotencyKey": str(uuid.uuid4()),
        "blockchain": blockchain,
        "destinationAddress": destination_address,
        "amounts": [f"{amount_usdc.quantize(Decimal('0.000001')):f}"],
        "tokenAddress": ARC_TESTNET_USDC,
        "feeLevel": "MEDIUM",
        "refId": ref_id,
    }
    if wid:
        kwargs["walletId"] = wid
    else:
        kwargs["walletAddress"] = waddr
    request = developer_controlled_wallets.CreateTransferTransactionForDeveloperRequest(**kwargs)
    response = transactions_api.create_developer_transaction_transfer(request)
    tx_id = response.data.id
    tx_hash = wait_for_transaction_hash(transactions_api, tx_id)
    return OnchainPaymentResult(
        tx_id=tx_id,
        tx_hash=tx_hash,
        amount_usdc=f"{amount_usdc.quantize(Decimal('0.000001')):f}",
        source_wallet_address=wallet_address,
        destination_wallet_address=destination_address,
    )


def transfer_usdc_from_private_key(
    *,
    private_key: str,
    source_wallet_address: str,
    destination_address: str,
    amount_usdc: Decimal,
    ref_id: str,
) -> OnchainPaymentResult:
    """Local / non-custodial fallback: raw ERC-20 transfer on Arc. Prefer ``transfer_usdc`` with a Circle wallet id."""
    web3 = _web3()
    account = Account.from_key(private_key)
    source_address = Web3.to_checksum_address(source_wallet_address)
    destination = Web3.to_checksum_address(destination_address)
    contract = web3.eth.contract(address=Web3.to_checksum_address(ARC_TESTNET_USDC), abi=USDC_ABI)
    amount_base_units = int((amount_usdc.quantize(Decimal("0.000001")) * USDC_DECIMALS).to_integral_value())
    nonce = web3.eth.get_transaction_count(source_address)
    gas_price = web3.eth.gas_price
    tx = contract.functions.transfer(destination, amount_base_units).build_transaction(
        {
            "from": source_address,
            "nonce": nonce,
            "chainId": web3.eth.chain_id,
            "gasPrice": gas_price,
        }
    )
    if "gas" not in tx:
        tx["gas"] = web3.eth.estimate_gas(tx)
    signed = account.sign_transaction(tx)
    tx_hash = _normalize_tx_hash(web3.eth.send_raw_transaction(signed.raw_transaction).hex())
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status != 1:
        raise RuntimeError("On-chain transfer reverted")
    return OnchainPaymentResult(
        tx_id=ref_id,
        tx_hash=tx_hash,
        amount_usdc=f"{amount_usdc.quantize(Decimal('0.000001')):f}",
        source_wallet_address=source_wallet_address,
        destination_wallet_address=destination_address,
    )


def assert_sufficient_usdc_balance(wallet_address: str, minimum_usdc: Decimal) -> Decimal:
    """Raise RuntimeError with a clear funding message if on-chain USDC is below ``minimum_usdc``."""
    if not (wallet_address or "").strip():
        raise RuntimeError("Wallet address is missing; cannot check USDC balance.")
    balances = get_wallet_balances(wallet_address.strip(), wallet_id=None)
    usdc = Decimal(str(balances.get("usdc", "0")))
    need = minimum_usdc.quantize(Decimal("0.000001"))
    if usdc < need:
        raise RuntimeError(
            f"Insufficient Arc testnet USDC: balance {usdc} < required {need}. "
            f"Fund this buyer wallet on ARC-TESTNET (USDC contract {ARC_TESTNET_USDC}): {wallet_address.strip()}"
        )
    return usdc


def get_wallet_balances(wallet_address: str, wallet_id: str | None = None) -> dict[str, Any]:
    checksum_address = Web3.to_checksum_address(wallet_address)
    web3 = _web3()
    contract = web3.eth.contract(address=Web3.to_checksum_address(ARC_TESTNET_USDC), abi=USDC_ABI)
    usdc_raw = contract.functions.balanceOf(checksum_address).call()
    usdc_amount = (Decimal(usdc_raw) / USDC_DECIMALS).quantize(Decimal("0.000001"))
    return {
        "walletId": wallet_id,
        "tokens": [
            {
                "symbol": "USDC",
                "amount": f"{usdc_amount:f}",
                "tokenAddress": ARC_TESTNET_USDC.lower(),
            }
        ],
        "usdc": f"{usdc_amount:f}",
    }
