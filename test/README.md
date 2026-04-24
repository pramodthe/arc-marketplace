# Test Guide

This folder contains integration and demo-oriented tests for the Agents Market project.

## Current test suites

- `buyer_agent/test_external_buyers.py`
  - Validates external buyer onboarding and funding metadata.
  - Validates cross-network funding flow (`Ethereum_Sepolia`/`Base_Sepolia` -> `Arc_Testnet`) in mock mode.
  - Validates buyer invocation/payment flow after funding.
  - Includes scenario for a separate external source wallet paying for marketplace services.

- `buyer_agent/chatbot.py`
  - Demo buyer runner used for manual API/payment checks.

## Prerequisites

From `backend/`:

```bash
uv sync
```

For Node bridge worker development (only needed for real bridge execution, not mock tests):

```bash
npm install
```

## Run tests

Run the external buyer integration tests from `backend/`:

```bash
uv run pytest ../test/buyer_agent/test_external_buyers.py -q
```

Run all tests under `test/` (from `backend/`):

```bash
uv run pytest ../test -q
```

## Test modes

- **Mock mode (default for tests)**:
  - `ARC_BRIDGE_WORKER_MODE=mock`
  - Used by `test_external_buyers.py` to keep tests deterministic and CI-friendly.

- **Real bridge mode (manual/demo)**:
  - Unset `ARC_BRIDGE_WORKER_MODE` or set real mode in backend env.
  - Requires funded source-chain wallet with:
    - testnet USDC (for transfer + bridge fees),
    - native gas token (ETH on Sepolia/Base Sepolia).

## Manual demo flow (real bridge)

1. Start backend:

```bash
uv run arc-seller
```

2. Create external buyer:

```bash
curl -sX POST http://localhost:4021/external-buyers \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Buyer","organization":"Demo"}'
```

3. Estimate bridge:

```bash
curl -sX POST http://localhost:4021/external-buyers/<BUYER_ID>/funding/estimate \
  -H "Content-Type: application/json" \
  -d '{"sourceChain":"Ethereum_Sepolia","amountUSDC":"1.0","transferSpeed":"FAST"}'
```

4. Execute bridge:

```bash
curl -sX POST http://localhost:4021/external-buyers/<BUYER_ID>/funding/bridge \
  -H "Content-Type: application/json" \
  -d '{"sourceChain":"Ethereum_Sepolia","amountUSDC":"1.0","transferSpeed":"FAST"}'
```

5. Invoke service with funded buyer:

```bash
curl -sX POST http://localhost:4021/sellers/<SELLER_ID>/agents/<AGENT_ID>/tools/<TOOL_ID>/invoke \
  -H "Content-Type: application/json" \
  -d '{"buyerId":<BUYER_ID>,"prompt":"run analysis"}'
```

## Notes

- Bridge transport (CCTP/App Kit) and x402 nanopayment are different layers:
  - bridge moves USDC across networks,
  - invoke settlement/payment happens on Arc path after funding.
- Never commit real secrets from `.env` files.
