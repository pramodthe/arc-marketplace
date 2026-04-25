from fastapi import HTTPException

from agents_market.arc.seller import app as seller_app


def test_private_provider_endpoint_rejected_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_PROVIDER_ENDPOINTS", raising=False)

    try:
        seller_app._validate_provider_endpoint("http://127.0.0.1:8000/invoke", field_name="endpointUrl")
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "ALLOW_PRIVATE_PROVIDER_ENDPOINTS" in str(exc.detail)
    else:
        raise AssertionError("Expected private endpoint to be rejected")


def test_private_provider_endpoint_allowed_for_local_demos(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_PROVIDER_ENDPOINTS", "true")

    endpoint, warning = seller_app._validate_provider_endpoint(
        "http://127.0.0.1:8000/invoke",
        field_name="endpointUrl",
    )

    assert endpoint == "http://127.0.0.1:8000/invoke"
    assert warning["code"] == "private_provider_endpoint_allowed"


def test_blank_wallet_balance_is_unavailable():
    payload = seller_app._safe_wallet_balances_payload(wallet_id=None, wallet_address="")

    assert payload["status"] == "unavailable"
    assert payload["reason"] == "wallet_address_missing"
    assert payload["tokens"] == []

