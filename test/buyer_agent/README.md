# Buyer Agent Chatbot

Agentic chatbot that:

- answers normal questions conversationally
- discovers services via the marketplace API using [`BuyerMarketplaceSDK`](../../backend/src/agents_market/arc/buyer/sdk.py) (see [`marketplace_sdk_bridge.py`](marketplace_sdk_bridge.py)), or falls back to A2A agent cards from `AGENT_CARD_URLS` when discovery returns nothing
- decides whether to buy based on remaining budget
- executes purchase via the discovered invoke URL (marketplace `…/tools/{id}/invoke` or external agents such as `http://localhost:5051/invoke`)

## Setup

From `test/buyer_agent`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Importing `BuyerMarketplaceSDK` (required for `chatbot.py`)

The chatbot imports the backend SDK (`agents_market.arc.buyer`). Pick one approach:

**Lightweight (recommended):** add the backend source tree to `PYTHONPATH` so you do not need to install the full `agents-market` wheel (which pulls seller-only dependencies such as `circle-titanoboa-sdk`).

From `test/buyer_agent` (requires **Python 3.10+** for `agents_market`, same as the backend):

```bash
export PYTHONPATH="${PWD}/../../backend/src"
python3 chatbot.py
```

If your default `python3` is older than 3.10, run the chatbot with the backend toolchain:

```bash
cd ../../backend
PYTHONPATH="src:../test/buyer_agent" uv run python ../test/buyer_agent/chatbot.py
```

**Alternative:** install the backend package in editable mode from `backend/` (same `uv sync` / `circle-titanoboa-sdk` path as the main app), then run `python3 chatbot.py` from `test/buyer_agent` without `PYTHONPATH`.

`PAYMENT_MODE=x402` still uses the Gateway client in `chatbot.py`; the SDK covers marketplace HTTP discovery and `buyerId` invokes for `simulate` / `onchain` against marketplace URLs.

Set your OpenAI key in `.env`:

```bash
OPENAI_API_KEY=your_real_openai_key
```

## Run chatbot (interactive)

```bash
python chatbot.py
```

Commands:

- `exit` or `quit` to stop
- `/budget` to show remaining budget

## Run single task mode (non-interactive)

Set in `.env`:

```bash
RUN_MODE=once
BUYER_PROMPT=Add 18 and 24
```

Then run:

```bash
python chatbot.py
```

The chatbot uses tool-calling with:

- `discover_services` to read `AGENT_CARD_URLS`
- `buy_service` to invoke selected service endpoint

Budget is decremented only after a successful purchase.

## Travel multi-agent QA UI (interactive)

This launches a separate QA web app with two pages:

- `/chatbot`: run buyer prompts and trigger multi-hop purchases (hotel -> flight -> itinerary).
- `/transactions-ui`: live-refresh ledger view to observe payment/output events while hops are running.

The app automatically:

- starts local travel provider agents from `test/travel_agents/` when needed
- registers a buyer + travel sellers/agents in marketplace
- persists created wallet and registration metadata to `test/buyer_agent/runtime/travel_agent_wallets.json`

Run:

```bash
python travel_qa_app.py
```

Open:

- `http://127.0.0.1:7070/chatbot`
- `http://127.0.0.1:7070/transactions-ui`

## Payment modes

Default mode is simulated HTTP invoke:

```bash
PAYMENT_MODE=simulate
```

For real x402 paid invoke (requires paid endpoint + Circle kit setup):

```bash
PAYMENT_MODE=x402
X402_CHAIN=arcTestnet
X402_PRIVATE_KEY=0x_your_buyer_private_key
```

Note: `transactionRef` returned by x402 flows can be a gateway/provider reference and may not always be an Arcscan tx hash.

## Open wallet/tx explorer pages

After a buyer run, open Arcscan pages for buyer wallet, seller wallet, and latest tx:

```bash
./open_transactions.sh
```

Optional overrides:

```bash
BACKEND_BASE_URL=http://localhost:4022 \
EXPLORER_BASE_URL=https://testnet.arcscan.app \
BUYER_WALLET_ADDRESS=0x... \
SELLER_WALLET_ADDRESS=0x... \
./open_transactions.sh
```

Notes:

- `http://localhost:4022/transactions` is the JSON/API endpoint.
- `http://localhost:4022/transactions/view` is the browser-friendly ledger view.
- In x402 mode, `transactionRef` is often a Circle Gateway reference, not an Arc on-chain tx hash. Arcscan can only open values that look like `0x...` transaction hashes.
