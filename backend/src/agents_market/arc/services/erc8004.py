"""Reusable Arc ERC-8004 service helpers for identity/reputation/validation."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from circle.web3 import developer_controlled_wallets, utils
from web3 import Web3

IDENTITY_REGISTRY = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
REPUTATION_REGISTRY = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
VALIDATION_REGISTRY = "0x8004Cb1BF31DAf7788923b405b754f57acEB4272"
DEFAULT_METADATA_URI = "ipfs://bafkreibdi6623n3xpf7ymk62ckb4bo75o3qemwkpfvp5i25j66itxvsoei"


@dataclass
class ArcRegistrationResult:
    tx_hash: str
    agent_id: str | None
    owner_wallet_address: str
    validator_wallet_address: str
    owner_wallet_id: str | None
    validator_wallet_id: str | None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _wallets_client():
    return utils.init_developer_controlled_wallets_client(
        api_key=_required_env("CIRCLE_API_KEY"),
        entity_secret=_required_env("CIRCLE_ENTITY_SECRET"),
    )


def _wait_for_tx_hash(transactions_api: developer_controlled_wallets.TransactionsApi, tx_id: str) -> str:
    for _ in range(60):
        time.sleep(2)
        tx = transactions_api.get_transaction(id=tx_id).data.transaction
        if tx.state == "COMPLETE" and tx.tx_hash:
            return tx.tx_hash
        if tx.state == "FAILED":
            raise RuntimeError("Transaction failed")
    raise TimeoutError("Timed out waiting for transaction completion")


def _lookup_agent_id(owner_wallet_address: str, tx_hash: str) -> str | None:
    rpc_url = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    receipt = web3.eth.get_transaction_receipt(tx_hash)
    transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)").hex()
    owner_topic = "0x" + owner_wallet_address.lower().replace("0x", "").zfill(64)
    logs = web3.eth.get_logs(
        {
            "address": Web3.to_checksum_address(IDENTITY_REGISTRY),
            "fromBlock": receipt.blockNumber,
            "toBlock": receipt.blockNumber,
            "topics": [transfer_topic, None, owner_topic],
        }
    )
    if not logs:
        return None
    return str(int(logs[-1]["topics"][3].hex(), 16))


def _resolve_or_create_wallets(
    wallets_api: developer_controlled_wallets.WalletsApi,
    wallet_sets_api: developer_controlled_wallets.WalletSetsApi,
    *,
    owner_wallet_id: str | None,
    validator_wallet_id: str | None,
) -> tuple[str | None, str, str | None, str]:
    if owner_wallet_id and validator_wallet_id:
        owner_wallet = wallets_api.get_wallet(id=owner_wallet_id).data.wallet.actual_instance
        validator_wallet = wallets_api.get_wallet(id=validator_wallet_id).data.wallet.actual_instance
        return owner_wallet_id, owner_wallet.address, validator_wallet_id, validator_wallet.address

    wallet_set = wallet_sets_api.create_wallet_set(
        developer_controlled_wallets.CreateWalletSetRequest.from_dict(
            {"name": f"marketplace-wallet-set-{int(time.time())}"}
        )
    )
    wallet_set_id = wallet_set.data.wallet_set.actual_instance.id
    wallets = wallets_api.create_wallet(
        developer_controlled_wallets.CreateWalletRequest.from_dict(
            {
                "blockchains": ["ARC-TESTNET"],
                "count": 2,
                "walletSetId": wallet_set_id,
                "accountType": "SCA",
            }
        )
    ).data.wallets
    owner = wallets[0].actual_instance
    validator = wallets[1].actual_instance
    return owner.id, owner.address, validator.id, validator.address


def register_agent_identity(
    *,
    metadata_uri: str | None = None,
    owner_wallet_id: str | None = None,
    validator_wallet_id: str | None = None,
) -> ArcRegistrationResult:
    metadata = metadata_uri or DEFAULT_METADATA_URI
    client = _wallets_client()
    wallet_sets_api = developer_controlled_wallets.WalletSetsApi(client)
    wallets_api = developer_controlled_wallets.WalletsApi(client)
    transactions_api = developer_controlled_wallets.TransactionsApi(client)

    owner_id, owner_address, validator_id, validator_address = _resolve_or_create_wallets(
        wallets_api,
        wallet_sets_api,
        owner_wallet_id=owner_wallet_id,
        validator_wallet_id=validator_wallet_id,
    )

    request = developer_controlled_wallets.CreateContractExecutionTransactionForDeveloperRequest.from_dict(
        {
            "walletAddress": owner_address,
            "blockchain": "ARC-TESTNET",
            "contractAddress": IDENTITY_REGISTRY,
            "abiFunctionSignature": "register(string)",
            "abiParameters": [metadata],
            "feeLevel": "MEDIUM",
        }
    )
    response = transactions_api.create_developer_transaction_contract_execution(request)
    tx_hash = _wait_for_tx_hash(transactions_api, response.data.id)
    agent_id = _lookup_agent_id(owner_address, tx_hash)
    return ArcRegistrationResult(
        tx_hash=tx_hash,
        agent_id=agent_id,
        owner_wallet_address=owner_address,
        validator_wallet_address=validator_address,
        owner_wallet_id=owner_id,
        validator_wallet_id=validator_id,
    )


def record_reputation(
    *,
    validator_wallet_address: str,
    agent_id: str,
    score: int,
    tag: str,
    feedback_hash: str,
) -> str:
    client = _wallets_client()
    transactions_api = developer_controlled_wallets.TransactionsApi(client)
    request = developer_controlled_wallets.CreateContractExecutionTransactionForDeveloperRequest.from_dict(
        {
            "walletAddress": validator_wallet_address,
            "blockchain": "ARC-TESTNET",
            "contractAddress": REPUTATION_REGISTRY,
            "abiFunctionSignature": "giveFeedback(uint256,int128,uint8,string,string,string,string,bytes32)",
            "abiParameters": [agent_id, str(score), "0", tag, "", "", "", feedback_hash],
            "feeLevel": "MEDIUM",
        }
    )
    response = transactions_api.create_developer_transaction_contract_execution(request)
    return _wait_for_tx_hash(transactions_api, response.data.id)


def create_validation_request(
    *,
    owner_wallet_address: str,
    validator_wallet_address: str,
    agent_id: str,
    request_uri: str,
    request_hash: str,
) -> str:
    client = _wallets_client()
    transactions_api = developer_controlled_wallets.TransactionsApi(client)
    request = developer_controlled_wallets.CreateContractExecutionTransactionForDeveloperRequest.from_dict(
        {
            "walletAddress": owner_wallet_address,
            "blockchain": "ARC-TESTNET",
            "contractAddress": VALIDATION_REGISTRY,
            "abiFunctionSignature": "validationRequest(address,uint256,string,bytes32)",
            "abiParameters": [validator_wallet_address, agent_id, request_uri, request_hash],
            "feeLevel": "MEDIUM",
        }
    )
    response = transactions_api.create_developer_transaction_contract_execution(request)
    return _wait_for_tx_hash(transactions_api, response.data.id)


def submit_validation_response(
    *,
    validator_wallet_address: str,
    request_hash: str,
    response_code: int,
    response_tag: str,
) -> str:
    client = _wallets_client()
    transactions_api = developer_controlled_wallets.TransactionsApi(client)
    request = developer_controlled_wallets.CreateContractExecutionTransactionForDeveloperRequest.from_dict(
        {
            "walletAddress": validator_wallet_address,
            "blockchain": "ARC-TESTNET",
            "contractAddress": VALIDATION_REGISTRY,
            "abiFunctionSignature": "validationResponse(bytes32,uint8,string,bytes32,string)",
            "abiParameters": [request_hash, str(response_code), "", "0x" + "0" * 64, response_tag],
            "feeLevel": "MEDIUM",
        }
    )
    response = transactions_api.create_developer_transaction_contract_execution(request)
    return _wait_for_tx_hash(transactions_api, response.data.id)


def get_validation_status(request_hash: str) -> dict[str, Any]:
    rpc_url = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    abi = [
        {
            "inputs": [{"name": "requestHash", "type": "bytes32"}],
            "name": "getValidationStatus",
            "outputs": [
                {"name": "validatorAddress", "type": "address"},
                {"name": "agentId", "type": "uint256"},
                {"name": "response", "type": "uint8"},
                {"name": "responseHash", "type": "bytes32"},
                {"name": "tag", "type": "string"},
                {"name": "lastUpdate", "type": "uint256"},
            ],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    contract = web3.eth.contract(address=VALIDATION_REGISTRY, abi=abi)
    val_addr, agent_id, response, response_hash, tag, updated = contract.functions.getValidationStatus(
        bytes.fromhex(request_hash[2:] if request_hash.startswith("0x") else request_hash)
    ).call()
    return {
        "validatorAddress": val_addr,
        "agentId": str(agent_id),
        "response": int(response),
        "responseHash": response_hash.hex() if hasattr(response_hash, "hex") else str(response_hash),
        "tag": tag,
        "lastUpdate": int(updated),
    }
