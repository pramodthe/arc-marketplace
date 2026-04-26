# QA Test Suite (Seller + Marketplace)

This folder contains practical QA checks for seller onboarding and buyer invocation flows.

## Why this exists

The seller details in `seller.md` show public Cloud Run URLs but card endpoint fields that still reference localhost values. This QA suite validates that deployed metadata and runtime endpoints are internet-reachable and internally consistent.

## Prerequisites

- Backend running (local or deployed), for example:
  - local: `http://localhost:4021`
  - deployed: `https://<your-backend-domain>`
- Python environment with backend deps available (recommended from `backend/`):
  - `uv sync`
- Optional for direct provider auth checks:
  - `gcloud auth print-identity-token`

## Configure

Set environment variables before running:

```bash
export QA_BASE_URL="http://localhost:4021"
export QA_SELLER_PROVIDER_URL="https://hotel-agent-440657628054.us-central1.run.app"
export QA_USE_BUYER_ID="false"
```

Optional:

```bash
export QA_GCP_IDENTITY_TOKEN="<token>"   # for protected provider endpoints
export QA_BUYER_ID="<existing_buyer_id>"
```

## Run

From repo root:

```bash
uv run python QA_test/seller_marketplace_qa.py
```

### Buyer chatbot agent (BuyerMarketplaceSDK)

This script simulates an autonomous buyer agent that uses the same SDK path a chatbot integration would use:
discover → pick → invoke with `buyerId` (Arc settlement path).

```bash
cd backend
export QA_BASE_URL="http://localhost:4021"
export BUYER_ID="123"   # recommended: reuse an existing buyer
uv run python ../QA_test/buyer_agent_chatbot_sdk_qa.py
```

Optional flags:

```bash
uv run python ../QA_test/buyer_agent_chatbot_sdk_qa.py \
  --server-url "$QA_BASE_URL" \
  --buyer-id "$BUYER_ID" \
  --prompt "Plan a 3-day Tokyo trip under $1500." \
  --budget 0.05
```

Notes:

- The SDK does not implement x402 signing. Use `--no-buyer-id` only if you intentionally want to exercise the x402 challenge path (and you have a working x402 client/runtime).
- If you omit `--buyer-id`, the SDK creates a buyer with an empty wallet address (fine for QA listing/discovery; not fine for funded onchain settlement).

### UI-based QA (no frontend/backend code changes)

From `QA_test/` start a static file server and open the QA page:

```bash
cd QA_test
python3 -m http.server 8080
```

Open:

- `http://localhost:8080/buyer_test_ui.html` — full harness (sellers, x402, manual invoke)
- `http://localhost:8080/buyer_agent_chatbot_demo.html` — **demo** page: one-click **BuyerMarketplaceSDK-style** flow (discover → pick → invoke with `buyerId`) plus agent reply panel
- `http://localhost:8080/autonomous_buyer_chat_demo.html` — **chat UI** for the autonomous LLM buyer (calls **`examples/autonomous_marketplace_buyer/chat_server.py`**, not `arc-seller`; see that folder’s README)

The QA UI uses existing backend APIs directly and keeps all logic in `QA_test/`.

**Autonomous LLM buyer (not in this folder):** The HTML pages above only chain HTTP; they do not run an LLM. For a realistic agent that **calls discover/list/invoke as tools** with OpenAI (or similar), use the Python example [`../examples/autonomous_marketplace_buyer/README.md`](../examples/autonomous_marketplace_buyer/README.md) with `uv sync --group llm-buyer` from `backend/`. Reuse **`BUYER_ID`** there to avoid piling up extra buyer rows in SQLite.

## What it validates

1. Marketplace liveness and payment rail mode (`/health`, `/`).
2. Seller provider health (`/health` on provider origin).
3. Seller card reachability and key fields at `/.well-known/agent-card.json`.
4. Marketplace discovery/listing endpoint shape.
5. One invoke call:
   - x402 path: expects HTTP 402 challenge when `buyerId` is not supplied.
   - invalid `Payment-Signature` is rejected and creates failure evidence in `/transactions`.
   - buyer path: attempts invoke with `buyerId` (if provided).
6. Strict mode behavior:
   - if x402 runtime is unavailable, invoke fails closed (HTTP 503) and records failure in `/transactions`.

## UI QA acceptance checklist

1. Load `seller.md` and parse seller specs in the QA UI.
2. Register all seller agents into marketplace via QA UI (seller + agent API calls pass).
3. Create a buyer and select it in QA UI.
4. Discover returns at least one candidate.
5. Invoke tests from QA UI:
   - no signature returns expected x402 challenge behavior.
   - invalid signature is rejected.
   - optional buyerId invoke executes selected buyer path.
6. Load `/transactions` and confirm payment/failure evidence is visible in UI.

## Interpreting failures quickly

- Provider health/card failures -> deployment, auth, or URL mismatch issue.
- Marketplace tool/discovery failures -> listing not registered or DB state issue.
- Invoke 502 after payment challenge -> provider endpoint URL in seller listing likely unreachable/misconfigured.
- Invoke 503 with x402 mode disabled -> runtime missing `circlekit`; check deployment image/dependencies.
- Card endpoint points to localhost/private address -> update seller card to public endpoint before demo.
