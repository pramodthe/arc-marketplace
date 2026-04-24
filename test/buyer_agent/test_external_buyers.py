from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("ARC_BRIDGE_WORKER_MODE", "mock")

from agents_market.arc.seller import app as app_module  # noqa: E402
from agents_market.db import Base  # noqa: E402
from agents_market.marketplace.repository import create_agent, create_payment_event, create_seller  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def fake_ensure_buyer_arc_wallets(buyer, db):
        buyer.owner_wallet_id = buyer.owner_wallet_id or f"wallet-{buyer.id}"
        buyer.validator_wallet_id = buyer.validator_wallet_id or f"validator-{buyer.id}"
        buyer.wallet_address = buyer.wallet_address or f"0x{buyer.id:040x}"
        buyer.validator_wallet_address = buyer.validator_wallet_address or f"0x{buyer.id + 1:040x}"
        db.commit()
        db.refresh(buyer)

    app_module.app.dependency_overrides[app_module.get_db] = override_get_db
    monkeypatch.setattr(app_module, "_ensure_buyer_arc_wallets", fake_ensure_buyer_arc_wallets)
    monkeypatch.setattr(
        app_module,
        "_wallet_balances_payload",
        lambda *, wallet_id, wallet_address: {
            "walletId": wallet_id,
            "walletAddress": wallet_address,
            "usdcTokenAddress": app_module.ARC_TESTNET_USDC,
            "usdc": {"amount": "0", "formatted": "0"},
            "tokens": [],
            "network": "arcTestnet",
        },
    )
    with TestClient(app_module.app) as test_client:
        yield test_client, TestingSessionLocal
    app_module.app.dependency_overrides.clear()


def test_external_buyer_creation_returns_arc_funding_metadata(client):
    test_client, _ = client

    response = test_client.post(
        "/external-buyers",
        json={"name": "Outside Buyer", "organization": "External Agent"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["buyer"]["walletAddress"].startswith("0x")
    assert payload["funding"]["settlementNetwork"] == "Arc_Testnet"
    assert payload["funding"]["settlementChainId"] == 5042002
    assert payload["funding"]["requiresBuyerArcRegistration"] is False
    assert "circle-app-kit-bridge-cctp" in payload["funding"]["acceptedFundingRails"]


def test_external_funding_bridge_persists_mock_bridge_result(client, monkeypatch):
    test_client, _ = client

    def fake_worker(action, payload):
        if action == "estimate":
            return {"amountUSDC": payload["amountUSDC"], "fees": [], "gas": []}
        return {
            "bridgeResult": {
                "state": "success",
                "steps": [
                    {
                        "name": "mockBridge",
                        "state": "success",
                        "txHash": "0x" + "a" * 64,
                        "explorerUrl": "https://testnet.arcscan.app/tx/0x" + "a" * 64,
                    }
                ],
            }
        }

    monkeypatch.setattr(app_module, "_run_bridge_worker", fake_worker)
    buyer = test_client.post("/external-buyers", json={"name": "Outside Buyer"}).json()["buyer"]

    estimate = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/estimate",
        json={"sourceChain": "Base_Sepolia", "amountUSDC": "1.25"},
    )
    assert estimate.status_code == 200
    assert estimate.json()["estimate"]["amountUSDC"] == "1.25"

    bridge = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/bridge",
        json={"sourceChain": "Base_Sepolia", "amountUSDC": "1.25"},
    )
    assert bridge.status_code == 200
    funding = bridge.json()["fundingTransfer"]
    assert funding["status"] == "success"
    assert funding["sourceChain"] == "Base_Sepolia"
    assert funding["destinationChain"] == "Arc_Testnet"
    assert funding["txHashes"] == ["0x" + "a" * 64]

    fetched = test_client.get(f"/external-buyers/{buyer['id']}/funding/{funding['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["fundingTransfer"]["transferRef"] == funding["transferRef"]


def test_rejects_unsupported_external_funding_source_chain(client):
    test_client, _ = client
    buyer = test_client.post("/external-buyers", json={"name": "Outside Buyer"}).json()["buyer"]

    response = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/estimate",
        json={"sourceChain": "Ethereum", "amountUSDC": "1"},
    )

    assert response.status_code == 400
    assert "Base_Sepolia" in response.json()["detail"]["supportedSourceChains"]


def test_marketplace_discovery_includes_external_funding_metadata(client):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        seller = create_seller(
            db,
            name="Seller",
            description="",
            owner_wallet_address="0x" + "b" * 40,
            validator_wallet_address="0x" + "c" * 40,
        )
        agent = create_agent(
            db,
            seller_id=seller.id,
            name="Risk Agent",
            description="Risk analysis",
            metadata_uri="https://seller.example/.well-known/agent-card.json",
            icon_data_url="",
            category="Analytics",
            endpoint_url="https://seller.example/invoke",
            http_method="POST",
            api_docs_url="",
            price_usdc=0.01,
        )
        agent.status = "registered"
        agent.arc_agent_id = "1"
        agent.identity_tx_hash = "0x" + "d" * 64
        db.commit()

    tools = test_client.get("/marketplace/tools").json()["tools"]
    assert tools[0]["payment"]["settlementNetwork"] == "Arc_Testnet"
    assert tools[0]["payment"]["acceptedSourceChains"]

    agents = test_client.get("/marketplace/agents").json()["agents"]
    assert agents[0]["commerce"]["paymentProtocol"] == "arc-usdc"
    assert agents[0]["tools"][0]["payment"]["requiresBuyerArcRegistration"] is False

    card = test_client.get("/.well-known/agent-card.json").json()
    assert card["payment"]["settlementChainId"] == 5042002
    assert card["skills"][0]["fundingEstimateUrl"].endswith("/external-buyers/{buyerId}/funding/estimate")


def test_external_buyer_can_invoke_after_mock_funding(client, monkeypatch):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        seller = create_seller(
            db,
            name="Seller",
            description="",
            owner_wallet_address="0x" + "b" * 40,
            validator_wallet_address="0x" + "c" * 40,
        )
        agent = create_agent(
            db,
            seller_id=seller.id,
            name="Risk Agent",
            description="Risk analysis",
            metadata_uri="https://seller.example/.well-known/agent-card.json",
            icon_data_url="",
            category="Analytics",
            endpoint_url="https://seller.example/invoke",
            http_method="POST",
            api_docs_url="",
            price_usdc=0.01,
        )
        agent.status = "registered"
        agent.arc_agent_id = "1"
        agent.identity_tx_hash = "0x" + "d" * 64
        seller_id = seller.id
        agent_id = agent.id
        tool_id = agent.tools[0].id
        db.commit()

    buyer = test_client.post("/external-buyers", json={"name": "Outside Buyer"}).json()["buyer"]

    def fake_settle(db, *, seller, buyer, agent, tool, invoke_path, total_amount_usdc, billing_breakdown):
        event = create_payment_event(
            db,
            seller_id=seller.id,
            agent_id=agent.id,
            tool_id=tool.id,
            event_type="payment",
            status="paid",
            buyer_address=buyer.wallet_address,
            transaction_ref="0x" + "e" * 64,
            amount_usdc=float(total_amount_usdc),
            details={
                "path": invoke_path,
                "payer": buyer.wallet_address,
                "payee": seller.owner_wallet_address,
                "amountUSDC": f"{Decimal(str(total_amount_usdc)):.6f}",
                "onchainTxHash": "0x" + "e" * 64,
                "circleTransactionId": "circle-tx",
                "billingBreakdown": billing_breakdown,
                "buyerId": buyer.id,
            },
        )
        return event, {
            "amountUSDC": f"{Decimal(str(total_amount_usdc)):.6f}",
            "onchainTxHash": "0x" + "e" * 64,
            "circleTransactionId": "circle-tx",
            "payer": buyer.wallet_address,
            "payee": seller.owner_wallet_address,
        }

    async def fake_provider(agent, tool, body, *, buyer_id, billing_breakdown):
        return {
            "statusCode": 200,
            "contentType": "application/json",
            "data": {"outputText": "analysis complete"},
            "outputText": "analysis complete",
            "endpointUrl": "https://seller.example/invoke",
        }

    monkeypatch.setattr(app_module, "_settle_onchain_payment", fake_settle)
    monkeypatch.setattr(app_module, "_forward_to_provider", fake_provider)

    response = test_client.post(
        f"/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke",
        json={"buyerId": buyer["id"], "prompt": "analyze risk"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outputText"] == "analysis complete"
    assert payload["payment"]["onchainTxHash"] == "0x" + "e" * 64


def test_external_network_buyer_bridges_then_invokes_marketplace_seller(client, monkeypatch):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        seller = create_seller(
            db,
            name="Crosschain Seller",
            description="",
            owner_wallet_address="0x" + "1" * 40,
            validator_wallet_address="0x" + "2" * 40,
        )
        agent = create_agent(
            db,
            seller_id=seller.id,
            name="Execution Agent",
            description="Cross-network execution",
            metadata_uri="https://seller.example/.well-known/agent-card.json",
            icon_data_url="",
            category="Execution",
            endpoint_url="https://seller.example/invoke",
            http_method="POST",
            api_docs_url="",
            price_usdc=0.01,
        )
        agent.status = "registered"
        agent.arc_agent_id = "agent-arc-1"
        agent.identity_tx_hash = "0x" + "3" * 64
        seller_id = seller.id
        agent_id = agent.id
        tool_id = agent.tools[0].id
        db.commit()

    def fake_worker(action, payload):
        assert payload["sourceChain"] == "Ethereum_Sepolia"
        assert payload["destinationChain"] == "Arc_Testnet"
        if action == "estimate":
            return {
                "mode": "mock",
                "amountUSDC": payload["amountUSDC"],
                "transferSpeed": payload.get("transferSpeed", "FAST"),
                "fees": [],
                "gas": [],
            }
        return {
            "mode": "mock",
            "bridgeResult": {
                "state": "success",
                "steps": [
                    {
                        "name": "approve",
                        "state": "success",
                        "txHash": "0x" + "4" * 64,
                        "explorerUrl": "https://sepolia.etherscan.io/tx/0x" + "4" * 64,
                    },
                    {
                        "name": "burn",
                        "state": "success",
                        "txHash": "0x" + "5" * 64,
                        "explorerUrl": "https://sepolia.etherscan.io/tx/0x" + "5" * 64,
                    },
                    {
                        "name": "mint",
                        "state": "success",
                        "txHash": "0x" + "6" * 64,
                        "explorerUrl": "https://testnet.arcscan.app/tx/0x" + "6" * 64,
                    },
                ],
            },
        }

    def fake_settle(db, *, seller, buyer, agent, tool, invoke_path, total_amount_usdc, billing_breakdown):
        event = create_payment_event(
            db,
            seller_id=seller.id,
            agent_id=agent.id,
            tool_id=tool.id,
            event_type="payment",
            status="paid",
            buyer_address=buyer.wallet_address,
            transaction_ref="0x" + "7" * 64,
            amount_usdc=float(total_amount_usdc),
            details={
                "path": invoke_path,
                "payer": buyer.wallet_address,
                "payee": seller.owner_wallet_address,
                "amountUSDC": f"{Decimal(str(total_amount_usdc)):.6f}",
                "onchainTxHash": "0x" + "7" * 64,
                "circleTransactionId": "circle-crosschain-invoke",
                "billingBreakdown": billing_breakdown,
                "buyerId": buyer.id,
            },
        )
        return event, {
            "amountUSDC": f"{Decimal(str(total_amount_usdc)):.6f}",
            "onchainTxHash": "0x" + "7" * 64,
            "circleTransactionId": "circle-crosschain-invoke",
            "payer": buyer.wallet_address,
            "payee": seller.owner_wallet_address,
        }

    async def fake_provider(agent, tool, body, *, buyer_id, billing_breakdown):
        return {
            "statusCode": 200,
            "contentType": "application/json",
            "data": {"outputText": "crosschain execution complete"},
            "outputText": "crosschain execution complete",
            "endpointUrl": "https://seller.example/invoke",
        }

    monkeypatch.setattr(app_module, "_run_bridge_worker", fake_worker)
    monkeypatch.setattr(app_module, "_settle_onchain_payment", fake_settle)
    monkeypatch.setattr(app_module, "_forward_to_provider", fake_provider)

    buyer = test_client.post(
        "/external-buyers",
        json={"name": "Crosschain Buyer", "organization": "External"},
    ).json()["buyer"]

    estimate = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/estimate",
        json={"sourceChain": "Ethereum_Sepolia", "amountUSDC": "1.5", "transferSpeed": "FAST"},
    )
    assert estimate.status_code == 200
    assert estimate.json()["funding"]["settlementNetwork"] == "Arc_Testnet"

    bridge = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/bridge",
        json={"sourceChain": "Ethereum_Sepolia", "amountUSDC": "1.5", "transferSpeed": "FAST"},
    )
    assert bridge.status_code == 200
    funding_transfer = bridge.json()["fundingTransfer"]
    assert funding_transfer["status"] == "success"
    assert len(funding_transfer["txHashes"]) == 3
    assert any("arcscan.app" in url for url in funding_transfer["explorerUrls"])

    invoke = test_client.post(
        f"/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke",
        json={"buyerId": buyer["id"], "prompt": "execute strategy"},
    )
    assert invoke.status_code == 200, invoke.text
    payload = invoke.json()
    assert payload["outputText"] == "crosschain execution complete"
    assert payload["payment"]["onchainTxHash"] == "0x" + "7" * 64


def test_separate_external_wallet_on_other_network_can_pay_marketplace_service(client, monkeypatch):
    test_client, SessionLocal = client
    with SessionLocal() as db:
        seller = create_seller(
            db,
            name="MultiNet Seller",
            description="",
            owner_wallet_address="0x" + "8" * 40,
            validator_wallet_address="0x" + "9" * 40,
        )
        agent = create_agent(
            db,
            seller_id=seller.id,
            name="Pricing Agent",
            description="Cross-network pricing",
            metadata_uri="https://seller.example/.well-known/agent-card.json",
            icon_data_url="",
            category="Pricing",
            endpoint_url="https://seller.example/invoke",
            http_method="POST",
            api_docs_url="",
            price_usdc=0.01,
        )
        agent.status = "registered"
        agent.arc_agent_id = "agent-arc-2"
        agent.identity_tx_hash = "0x" + "a" * 64
        seller_id = seller.id
        agent_id = agent.id
        tool_id = agent.tools[0].id
        db.commit()

    separate_external_wallet = "0xE0Db49E911B39a80CD23898B1Dc406eB37E17835"

    def fake_worker(action, payload):
        if action == "estimate":
            return {
                "mode": "mock",
                "source": {"chain": payload["sourceChain"]},
                "destination": {"chain": payload["destinationChain"], "address": payload["destinationAddress"]},
                "amountUSDC": payload["amountUSDC"],
                "fees": [{"type": "forwarder", "amount": "0.205"}],
            }
        return {
            "mode": "mock",
            "bridgeResult": {
                "state": "success",
                "source": {"chain": {"chain": payload["sourceChain"]}, "address": separate_external_wallet},
                "destination": {
                    "chain": {"chain": payload["destinationChain"]},
                    "address": payload["destinationAddress"],
                },
                "steps": [
                    {
                        "name": "approve",
                        "state": "success",
                        "txHash": "0x" + "b" * 64,
                        "explorerUrl": "https://sepolia.etherscan.io/tx/0x" + "b" * 64,
                    },
                    {
                        "name": "burn",
                        "state": "success",
                        "txHash": "0x" + "c" * 64,
                        "explorerUrl": "https://sepolia.etherscan.io/tx/0x" + "c" * 64,
                    },
                    {
                        "name": "mint",
                        "state": "success",
                        "txHash": "0x" + "d" * 64,
                        "explorerUrl": "https://testnet.arcscan.app/tx/0x" + "d" * 64,
                    },
                ],
            },
        }

    def fake_settle(db, *, seller, buyer, agent, tool, invoke_path, total_amount_usdc, billing_breakdown):
        event = create_payment_event(
            db,
            seller_id=seller.id,
            agent_id=agent.id,
            tool_id=tool.id,
            event_type="payment",
            status="paid",
            buyer_address=buyer.wallet_address,
            transaction_ref="0x" + "e" * 64,
            amount_usdc=float(total_amount_usdc),
            details={
                "path": invoke_path,
                "payer": buyer.wallet_address,
                "payee": seller.owner_wallet_address,
                "amountUSDC": f"{Decimal(str(total_amount_usdc)):.6f}",
                "onchainTxHash": "0x" + "e" * 64,
                "circleTransactionId": "circle-separate-wallet",
                "billingBreakdown": billing_breakdown,
                "buyerId": buyer.id,
                "sourceNetwork": "Ethereum_Sepolia",
                "sourceWallet": separate_external_wallet,
            },
        )
        return event, {
            "amountUSDC": f"{Decimal(str(total_amount_usdc)):.6f}",
            "onchainTxHash": "0x" + "e" * 64,
            "circleTransactionId": "circle-separate-wallet",
            "payer": buyer.wallet_address,
            "payee": seller.owner_wallet_address,
        }

    async def fake_provider(agent, tool, body, *, buyer_id, billing_breakdown):
        return {
            "statusCode": 200,
            "contentType": "application/json",
            "data": {"outputText": "separate external buyer paid successfully"},
            "outputText": "separate external buyer paid successfully",
            "endpointUrl": "https://seller.example/invoke",
        }

    monkeypatch.setattr(app_module, "_run_bridge_worker", fake_worker)
    monkeypatch.setattr(app_module, "_settle_onchain_payment", fake_settle)
    monkeypatch.setattr(app_module, "_forward_to_provider", fake_provider)

    buyer = test_client.post(
        "/external-buyers",
        json={"name": "Separate Wallet Buyer", "organization": "Demo"},
    ).json()["buyer"]

    estimate = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/estimate",
        json={"sourceChain": "Ethereum_Sepolia", "amountUSDC": "1.0", "transferSpeed": "FAST"},
    )
    assert estimate.status_code == 200

    bridge = test_client.post(
        f"/external-buyers/{buyer['id']}/funding/bridge",
        json={"sourceChain": "Ethereum_Sepolia", "amountUSDC": "1.0", "transferSpeed": "FAST"},
    )
    assert bridge.status_code == 200
    funding_transfer = bridge.json()["fundingTransfer"]
    assert funding_transfer["status"] == "success"
    assert funding_transfer["sourceChain"] == "Ethereum_Sepolia"
    assert funding_transfer["destinationChain"] == "Arc_Testnet"
    assert any("etherscan.io" in url for url in funding_transfer["explorerUrls"])
    assert any("arcscan.app" in url for url in funding_transfer["explorerUrls"])

    invoke = test_client.post(
        f"/sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke",
        json={"buyerId": buyer["id"], "prompt": "price this opportunity"},
    )
    assert invoke.status_code == 200, invoke.text
    payload = invoke.json()
    assert payload["outputText"] == "separate external buyer paid successfully"
    assert payload["payment"]["onchainTxHash"] == "0x" + "e" * 64
