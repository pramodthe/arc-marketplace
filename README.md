# Agents Market

Agents Market is a multi-seller agent marketplace demo focused on the Arc hackathon use case:
- monetize agent/tool invocations with sub-cent x402 payments,
- settle activity on Arc-compatible infrastructure,
- track usage and payment events for demo evidence.

The repository has:
- a **Python/FastAPI** backend for marketplace APIs, provider HTTP proxying, payment enforcement (x402 and Arc USDC), ERC-8004 lifecycle hooks, SQLAlchemy persistence, and CLI entry points.
- a **React (Vite)** frontend for browsing listings, registering agents, editing per-tool pricing, and viewing the payment ledger.

---

## What This App Implements

### Core implemented flows
- **Marketplace CRUD + discovery**: sellers, buyer records, agent listings (with `offeringType` / `protocolType`), tools and optional per-tool **skills**, ranked discovery via `POST /marketplace/discover`, and a legacy-shaped `GET /tools` catalog.
- **Paid invocation flow**: external buyers use **[Circle Gateway Nanopayments](https://developers.circle.com/gateway/nanopayments)** (HTTP **402** + **`Payment-Signature`**, `circlekit` on **`arcTestnet`**). Registered demo buyers use **[Arc](https://docs.arc.network/arc/references/connect-to-arc)** **USDC** on **ARC-TESTNET** via JSON **`buyerId`** and Circle **developer-controlled** wallets (no x402 on that path). Successful invoke responses and **`GET /`** include a stable **`paymentRails`** object describing both rails.
- **Provider safety**: outbound calls resolve provider hosts; **localhost/private IPs are rejected by default** (opt in with **`ALLOW_PRIVATE_PROVIDER_ENDPOINTS=true`** for local Docker demos). After x402 payment, the seller **preflights** `{provider-origin}/health` before calling the provider invoke URL.
- **Ledgering**: payment, usage, and seller-output events are stored for reporting; **`GET /transactions`** exposes JSON summaries and **`GET /transactions/view`** renders a simple HTML ledger.
- **Arc lifecycle endpoints**: ERC-8004-style **register**, **reputation**, and **validation request/response** for marketplace **agents** (by global `agent_id`) and optional **buyer** Arc registration under **`POST /buyers/{buyer_id}/arc/register`**.
- **Wallet / Gateway demo**: provision wallets, shared demo Gateway **deposit/balance** views (treasury key is **`SELLER_PRIVATE_KEY`** — hackathon-only pattern).
- **Buyer integration**: in-process **`BuyerMarketplaceSDK`** (`backend/src/agents_market/arc/buyer/sdk.py`) for discover → pick → **`buyerId`** invoke; the **`arc-buyer`** CLI uses it. x402 remains the caller’s responsibility (e.g. `circlekit`).
- **CLI utilities**: `arc-seller`, `arc-buyer`, `arc-client`, `arc-deposit`, `arc-keygen`, `arc-demo-marketplace`.

### Current limitations (important)
- **Bridge transfer endpoint is an orchestration stub** (records queued transfer metadata; does not execute a full bridge route yet).
- **Provider listings require Circle/Arc environment variables** because active listings are automatically registered on Arc ERC-8004.
- `circlekit` is required for x402 paid invokes; when unavailable, invoke requests fail closed and failures are logged in `payment_events`/`GET /transactions`.

---

## Repository Structure

```
agents_market/
├── backend/
│   ├── src/agents_market/
│   │   ├── arc/
│   │   │   ├── seller/          # FastAPI app (app.py) + arc-seller entry
│   │   │   ├── buyer/           # BuyerMarketplaceSDK (sdk.py), arc-buyer runner (run.py)
│   │   │   ├── cli/             # deposit, client, keygen, demo_marketplace, etc.
│   │   │   ├── services/        # Arc USDC transfers, ERC-8004 helpers
│   │   │   └── common/          # Shared tool catalog helpers
│   │   ├── marketplace/         # ORM models + repository
│   │   ├── db.py
│   │   └── _env.py              # backend/.env + workspace-root .env for unset keys
│   ├── alembic/versions/        # 0001–0007 (see backend/README.md for revision table)
│   ├── pyproject.toml           # uv; dev dependency group includes pytest
│   └── .env.example
├── frontend/                    # Vite + React + Tailwind + Radix
│   └── src/ (App.jsx, api/marketplaceClient.js, lib/agentMappers.js, components/ui/)
└── circle_scripts/              # Optional Circle ops (e.g. entity secret registration)
```

Longer API reference, `BuyerMarketplaceSDK` examples, and migration revision notes: [`backend/README.md`](backend/README.md).

---

## Tech Stack and Why It Is Implemented

## Backend (Python)

### Runtime + API
- **`fastapi`**: high-velocity API framework for marketplace + payment-gated routes.
- **`uvicorn[standard]`**: ASGI server used to run the FastAPI seller service.
- **`httpx`**: outbound HTTP calls for provider API proxying and client requests.
- **`python-dotenv`**: `.env` loading for local developer setup and secrets wiring.
- **`pyyaml`**: YAML/OpenAPI related serialization support used by compatibility endpoints.

### Data layer
- **`sqlalchemy`**: ORM for sellers, buyers, agents, tools, skills, usage records, payment events, reputation, validation, bridge rows, and buyer invocations. Money fields use **`Numeric(18, 6)`** (revision **0007**).
- **`alembic`**: versioned migrations under `backend/alembic/versions/` (apply with **`uv run alembic upgrade head`**).

### Arc/EVM and payments
- **`circle-titanoboa-sdk[x402]`** (via local editable source): provides `circlekit` client/middleware used for x402 + Gateway payment flow.
- **`circle-developer-controlled-wallets`**: provisions and operates Circle developer-controlled wallets.
- **`web3`**: direct Arc RPC calls for on-chain reads/event lookups (for ERC-8004 lifecycle status).
- **`eth-account`**: EVM account/key utilities required by blockchain transaction tooling.

### Packaging/tooling
- **`uv`**: dependency and script runner used across backend setup/run commands.
- **`hatchling`**: build backend declared in `pyproject.toml`.

## Frontend (React/Vite)

### App/UI runtime
- **`react` + `react-dom`**: component rendering and page state management.
- **`vite`**: fast local dev server + build pipeline for the UI.
- **`lucide-react`**: icon set used across marketplace screens.

### UI primitives and styling
- **`@radix-ui/react-*`**: accessible primitives (avatar, dialog, switch, separator, slot).
- **`tailwindcss` + `postcss` + `autoprefixer`**: utility-first styling pipeline.
- **`tailwindcss-animate`**: animation utilities for UI interactions.
- **`class-variance-authority` + `clsx` + `tailwind-merge`**: reusable variant-based styling and class composition.

### Code quality
- **`eslint` + React plugins**: frontend linting and best-practice checks.

---

## Environment Variables

Use `backend/.env.example` as the source of truth. If a **workspace-root** `.env` exists, keys that are **not** already set in the process environment are filled from it after `backend/.env` is loaded (see `_env.py`). Key variables:

- **Payment + runtime**
  - `PRIVATE_KEY`: buyer wallet private key.
  - `SELLER_PRIVATE_KEY`: shared hackathon Gateway treasury key for demo deposit/balance operations.
  - `SERVER_URL`, `PORT`, `PUBLIC_BASE_URL`.
  - `ALLOW_PRIVATE_PROVIDER_ENDPOINTS`: set to `true` only for local demos that register `localhost` or private-network provider URLs.
- **Database**
  - `DATABASE_URL` (default SQLite).
- **Buyer behavior** (`arc-buyer` / local demos)
  - `BUYER_PROMPT`, `BUYER_TASK`, `BUYER_BUDGET_USDC`, `BUYER_LOOP_SECONDS`, optional `BUYER_ID` (existing `POST /buyers` id).
- **Circle + Arc integration**
  - `CIRCLE_API_KEY`, `CIRCLE_ENTITY_SECRET`.
  - `ARC_RPC_URL` (default Arc testnet RPC; mostly needed for Arc lifecycle/read endpoints).

---

## Setup

## 1) Backend

From `backend/`:

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
```

Run API:

```bash
uv run arc-seller
```

Default base URL: `http://localhost:4021`

## One-command demo deploy

From repo root:

```bash
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:4021`

Useful backend commands:

```bash
uv run arc-demo-marketplace
uv run arc-client
uv run arc-buyer
uv run arc-deposit
uv run arc-keygen
```

## 2) Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

Point the UI at a non-default API host with **`VITE_API_BASE_URL`** (see `src/api/marketplaceClient.js`; default `http://localhost:4021`).

**Client-side routes** (history API, no React Router package): marketplace grid at **`/`**; agent detail **`/agents/{compositeId}`**; edit pricing **`/agents/{compositeId}/edit`**; seller onboarding **`/agents/register`**; ledger **`/transactions`**.

```bash
npm run build   # production bundle
```

---

## 3) Backend tests (optional)

From `backend/` (dev dependency group includes **pytest**; add tests under `backend/tests/` as needed):

```bash
uv sync --group dev
uv run pytest
```

---

## Seller Guide: Register and Sell an AI Agent

Use this flow if you are a developer who wants to sell an agent on this marketplace.

### Ownership model (important)

- You (the agent creator) should own and publish your protocol-level A2A `agent-card.json`.
- This platform backend stores marketplace records (seller, agent, tools, payments) and exposes invoke routes.
- The frontend renders marketplace cards for users; it is not the source of truth for A2A metadata.

### Step 1: Publish your own agent card

Host your card at your own domain (recommended): `https://your-agent-domain/.well-known/agent-card.json`.

Minimal example:

```json
{
  "name": "Arb Scout v1",
  "description": "Cross-chain opportunity analysis agent",
  "url": "https://your-agent-domain",
  "provider": {
    "organization": "AlphaAgent Labs",
    "url": "https://your-agent-domain"
  },
  "version": "1.0.0",
  "documentationUrl": "https://your-agent-domain/docs",
  "authentication": {
    "type": "x402-or-bearer",
    "instructions": "Use x402 Payment-Signature for paid invoke routes."
  },
  "skills": [
    {
      "id": "analyze",
      "name": "Analyze",
      "description": "Analyze a prompt and return structured output",
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    }
  ]
}
```

Recommended to also publish:
- `/.well-known/ai-plugin.json`
- `/openapi.yaml`

### Step 2: Register as a seller in this platform

```bash
curl -sX POST http://localhost:4021/sellers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AlphaAgent Labs",
    "description": "Autonomous trading and risk tools",
    "ownerWalletAddress": "0x9789AD5776fD505C026148bB989A69A0DcaC9D28",
    "validatorWalletAddress": "0xaBB7D9CD054b1E78074c25f8E65c291015871847"
  }'
```

### Step 3: Create your agent record

Register the developer-owned provider endpoint. The handler **reuses the seller’s Circle wallets**, runs **ERC-8004 registration** on Arc testnet, and returns **`warnings`** if the provider URL tripped SSRF rules (e.g. private IP without `ALLOW_PRIVATE_PROVIDER_ENDPOINTS`).

Minimal listing (one auto-created **`invoke`** tool) — `offeringType` / `protocolType` classify the listing for discovery and the UI:

```bash
curl -sX POST http://localhost:4021/sellers/<SELLER_ID>/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Arb Scout v1",
    "description": "Cross-chain opportunity analysis and execution plans",
    "category": "Analytics",
    "offeringType": "agent",
    "protocolType": "http",
    "endpointUrl": "https://your-agent-domain/api/invoke",
    "httpMethod": "POST",
    "priceUSDC": 0.01,
    "apiDocsUrl": "https://your-agent-domain/docs",
    "metadataUri": "https://your-agent-domain/.well-known/agent-card.json"
  }'
```

`offeringType`: `agent` | `skill` | `mcp_service`. `protocolType`: `http` | `mcp` | `a2a`.

For **multiple paid tools** on one agent, send a **`capabilities`** array (each entry: `toolKey`, `endpointUrl`, `priceUSDC`, optional `skills`, optional `runtimePriceUSDC` / `runtimeUnit`) instead of relying on the single-endpoint shorthand above; see `AgentCreateBody` in `backend/src/agents_market/arc/seller/app.py`.

### Step 4: Verify your listing and paid invoke path

- Marketplace cards: `GET /marketplace/agents`
- Tools: `GET /marketplace/tools` or `GET /tools` (legacy-shaped rows with `invokeUrl`)
- Ranked discovery: `POST /marketplace/discover`
- Paid invoke: `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke` with either x402 headers or JSON **`buyerId`**
- Invoke JSON may include **`usageUnits`** when the tool defines runtime metering (`runtimePriceUSDC` / `runtimeUnit`)
- Ledger: `GET /transactions` or open **`/transactions`** in the frontend

### Current platform compatibility endpoint

`GET /.well-known/agent-card.json` on this backend currently returns a marketplace-level aggregated card (not your individual external card). Keep your own agent card published and treat it as your canonical protocol metadata.

---

## API Highlights

Routes match `backend/src/agents_market/arc/seller/app.py` (prefix-free paths on the seller server).

### Service
- `GET /` — metadata + **`paymentRails`**
- `GET /health` — counts + timestamp (also the default **provider preflight** path pattern: `{origin}/health`)

### Sellers and listings
- `POST /sellers`, `GET /sellers`, `GET /sellers/{seller_id}`
- `PATCH /sellers/{seller_id}/status`
- `GET /sellers/{seller_id}/balances`
- `POST /sellers/{seller_id}/agents` (Arc register + tools)
- `DELETE /sellers/{seller_id}/agents/{agent_id}`
- `PATCH /sellers/{seller_id}/agents/{agent_id}/pricing`
- `PATCH /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/pricing`

### Buyers
- `POST /buyers`, `GET /buyers`, `GET /buyers/{buyer_id}` (includes recent invocations)
- `GET /buyers/{buyer_id}/balances`
- `POST /buyers/{buyer_id}/arc/register`

### Marketplace and invoke
- `GET /marketplace/agents`, `GET /marketplace/tools`, `POST /marketplace/discover`
- `GET /tools` — legacy tool listing
- `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke` — x402 **or** `buyerId`

### Ledger
- `GET /transactions`
- `GET /transactions/view` — HTML ledger

### Arc lifecycle (global `agent_id` as stored in the DB)
- `POST /agents/{agent_id}/arc/register`
- `POST /agents/{agent_id}/arc/reputation`
- `POST /agents/{agent_id}/arc/validation/request`
- `POST /agents/{agent_id}/arc/validation/respond`

### Wallet / Gateway / bridge
- `POST /sellers/{seller_id}/wallets/provision`
- `POST /sellers/{seller_id}/gateway/deposit`
- `GET /sellers/{seller_id}/gateway/balances`
- `GET /gateway/demo-treasury/balances`
- `POST /sellers/{seller_id}/bridge/transfers` — **stub** (persists intent; no live Bridge Kit execution)

### Compatibility / docs
- `GET /.well-known/agent-card.json`, `GET /.well-known/ai-plugin.json`, `GET /openapi.yaml`

---

## How Buyer/Seller Nanopayments Work (Current Implementation)

1. Buyer discovers target tool and invoke path.
2. Buyer uses a Gateway/x402-capable client to call the paid invoke endpoint.
3. On the **first** call without `Payment-Signature`, the seller returns **HTTP 402** with the Gateway payment challenge (no provider preflight yet).
4. Buyer signs the payment authorization and **retries the same invoke URL** with the `Payment-Signature` header.
5. On that **retry**, the seller preflights the provider at `{origin}/health`, then verifies and settles payment through Gateway middleware (`circlekit`, `arcTestnet`).
6. Seller executes the provider tool, returns the response with x402 payment confirmation, and logs transaction/payment events.
7. **Alternatively**, registered demo buyers send `buyerId` (no x402): the seller preflights `/health`, settles Arc USDC from the buyer wallet to the seller, then invokes the provider.

This design is what enables per-action monetization and high-frequency transaction logging for hackathon evidence.

---

## Hackathon Payment Model

- One Circle developer account (`CIRCLE_API_KEY` + `CIRCLE_ENTITY_SECRET`) provisions all demo seller, buyer, owner, and validator wallets.
- New **agent listings** register on Arc using the **seller’s** provisioned owner/validator wallet pair (`ARC-TESTNET`). **Buyers** can additionally register on Arc via **`POST /buyers/{buyer_id}/arc/register`** (separate owner/validator pair for the buyer record).
- x402 paid invokes use the seller's `ownerWalletAddress` as the payment recipient in the Gateway payment challenge.
- **`buyerId`** invokes settle **Arc USDC** from the buyer’s provisioned wallet to the **seller’s owner wallet** (then the provider is called).
- Provider endpoint URLs that resolve to localhost or private networks are blocked by default. For Docker/local demos, set `ALLOW_PRIVATE_PROVIDER_ENDPOINTS=true`.
- Gateway deposit and balance routes use `SELLER_PRIVATE_KEY` as a shared local demo treasury key. The seller-scoped Gateway endpoints are compatibility views that include seller context plus `mode: "shared_demo_treasury"`.
- This is acceptable for hackathon evidence and local demos. Production custody should replace the shared private key with seller-specific treasury/accounting controls.

---

## Hackathon Alignment Snapshot

- Arc + USDC + Circle Gateway x402: implemented (dual rail: external x402 + internal `buyerId` Arc settlement).
- Per-action priced tools (and optional per-skill selection metadata): implemented.
- Usage / payment event persistence: implemented (JSON + HTML ledger).
- Bridge endpoint: **stub only** (queued metadata, not a live cross-chain transfer).
- Frontend: marketplace browse, agent detail, **register** flow, **per-tool pricing** edits, **delete agent**, transactions view.

---

## Notes for Contributors

- Do not commit real private keys or `.env` files.
- If `circle-titanoboa-sdk` lives outside the default sibling path, update `[tool.uv.sources]` in `backend/pyproject.toml`.
- Run **`uv run alembic upgrade head`** before first API boot whenever the schema changes.
- Backend-focused conventions: [`backend/AGENTS.md`](backend/AGENTS.md); operational detail: [`backend/README.md`](backend/README.md).
