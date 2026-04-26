# Agent trading demo (Arc testnet)

This folder demonstrates **repeatable paid marketplace invokes** where each trade settles **real USDC on ARC-TESTNET** using the marketplace `buyerId` path (Circle developer-controlled wallets), plus lightweight HTTP “seller” tools.

## What you get

1. **`provider_hub/`** — FastAPI app: `GET /health` (marketplace preflight) and `POST /tools/{slug}` for all seeded slugs (weather, sentiment, quote, planner, reminder, summarize, translate, news_digest, code_review, task_split, json_format) returning JSON `outputText`.
2. **`seed_demo.py`** — Registers one seller and **three** marketplace agents (**eleven** priced tools total, three Arc ERC-8004 registrations).
3. **`buyer_trader.py`** — Async loop: `BuyerMarketplaceSDK` + `buyerId`, round-robin invokes across all seeded agents, session budget, logs `onchainTxHash` (one USDC transfer per successful invoke on Arc testnet when the buyer wallet is funded).

## Prerequisites

- Python **3.12+**
- Backend dependencies installed from `backend/` (`uv sync` per root [README](../../README.md)).
- **`CIRCLE_API_KEY`** and **`CIRCLE_ENTITY_SECRET`** in `backend/.env` (wallet provisioning + transfers).
- Database migrated: from `backend/`, run `uv run alembic upgrade head`.
- **Arc testnet USDC** on the **buyer** wallet after it is created (see below). Without balance, invokes fail during on-chain settlement.

## Local networking (important)

If the provider hub runs on `http://127.0.0.1:9090`, the marketplace process must be allowed to call it:

- Set **`ALLOW_PRIVATE_PROVIDER_ENDPOINTS=true`** in `backend/.env` for local demos only (see root README).

If the API runs in Docker and the hub on your host, use a URL the container can reach (e.g. `http://host.docker.internal:9090`) and the same flag if that resolves to a private address.

## 1) Start the marketplace API

From `backend/`:

```bash
uv run arc-seller
```

Default API: `http://localhost:4021`.

## 2) Start the provider hub

In a second terminal (repo root or this folder):

```bash
cd examples/agent_trading_demo/provider_hub
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 9090
```

Use **`PROVIDER_BASE_URL`** in step 3 that matches how the **seller server** resolves the host (often `http://127.0.0.1:9090`).

## 3) Seed the marketplace listing

From **`backend/`** (so `agents_market` imports work if you extend scripts later; `seed_demo.py` only needs `httpx`):

```bash
export PROVIDER_BASE_URL=http://127.0.0.1:9090
export SERVER_URL=http://localhost:4021
uv run python ../examples/agent_trading_demo/seed_demo.py
```

Note the printed **seller id**, **agent id**, and **tool** rows.

## 4) Fund the buyer wallet (Arc testnet USDC)

1. Run the buyer once with a tiny budget so a buyer record is created, **or** `POST /buyers` manually.
2. Open `GET http://localhost:4021/buyers/{id}` (or `GET .../balances`) and copy the buyer **wallet address**.
3. Send **testnet USDC** on **ARC-TESTNET** to that address (faucet / internal workflow your team uses).

## 5) Run the trading loop

From `backend/`:

```bash
export SERVER_URL=http://localhost:4021
export TRADER_BUDGET_USDC=0.05
export TRADER_LOOP_SECONDS=15
export BUYER_NAME="Arc Trading Demo Buyer"
uv run python ../examples/agent_trading_demo/buyer_trader.py
```

Optional:

- **`BUYER_ID`** — reuse an existing buyer from `POST /buyers`.
- **`AGENT_NAME_PREFIX`** — if set, only tools whose agent name starts with this single prefix are used (overrides the list below).
- **`AGENT_NAME_PREFIXES`** — comma-separated prefixes; default matches all seeded agents (`Demo Multi-Tool`, `Arc Analytics`, `Arc Dev`).
- **`TRADER_MAX_TRADES`** — stop after N successful paid invokes (handy to burn a small fixed number of on-chain txs, e.g. `TRADER_MAX_TRADES=11` hits each tool once at default prices within a large enough budget).

Stop with **Ctrl+C**.

## Alternative buyer

The built-in CLI buyer (`uv run arc-buyer`) also performs `buyerId` invokes; configure `BUYER_LOOP_SECONDS`, `BUYER_BUDGET_USDC`, and prompts via env vars in `backend/.env`.

## Layout

```text
examples/agent_trading_demo/
├── README.md
├── seed_demo.py
├── buyer_trader.py
└── provider_hub/
    ├── app.py
    └── requirements.txt
```
