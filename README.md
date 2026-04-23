# Agents Market

Agents Market is a multi-seller agent marketplace demo focused on the Arc hackathon use case:
- monetize agent/tool invocations with sub-cent x402 payments,
- settle activity on Arc-compatible infrastructure,
- track usage and payment events for demo evidence.

The repository has:
- a Python backend for marketplace APIs, payment enforcement, Arc lifecycle flows, and CLI runners.
- a React frontend that currently provides a polished marketplace UI shell (mostly static/mock data).

---

## What This App Implements

### Core implemented flows
- **Marketplace CRUD + discovery**: create sellers/agents, list tools, and rank tools by prompt + budget.
- **Paid invocation flow**: buyer pays via x402/Gateway before calling seller tool endpoints.
- **Ledgering**: payment and output events are persisted for transaction/frequency reporting.
- **Arc lifecycle endpoints**: ERC-8004 style register/reputation/validation request/response flows.
- **Wallet/gateway operations**: provision Circle developer-controlled wallets and deposit/check Gateway balances.
- **CLI utilities**: buyer/seller client runs, deposit, keygen, registration, demo data seeding.

### Current limitations (important)
- **Bridge transfer endpoint is an orchestration stub** (records queued transfer metadata; does not execute a full bridge route yet).
- **Frontend is not fully wired to backend APIs**; most screen content is static demo data.

---

## Repository Structure

```
agents_market/
├── backend/
│   ├── src/agents_market/
│   │   ├── arc/
│   │   │   ├── seller/          # FastAPI marketplace + payment-gated endpoints
│   │   │   ├── buyer/           # Buyer runner logic
│   │   │   ├── cli/             # CLI entry points (deposit, client, register, keygen, seed)
│   │   │   ├── services/        # ERC-8004 integration helpers
│   │   │   └── common/          # Shared tool catalog
│   │   ├── marketplace/         # SQLAlchemy models + repository methods
│   │   ├── db.py                # Engine/session wiring
│   │   └── _env.py              # backend/.env loader
│   ├── alembic/                 # DB migration config and versions
│   ├── pyproject.toml
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx              # Main UI shell
    │   └── components/ui/       # Reusable UI primitives
    └── package.json
```

---

## Tech Stack and Why It Is Implemented

## Backend (Python)

### Runtime + API
- **`fastapi`**: high-velocity API framework for marketplace + payment-gated routes.
- **`uvicorn[standard]`**: ASGI server used to run the FastAPI seller service.
- **`httpx`**: outbound HTTP calls (LLM/provider integrations and client requests).
- **`python-dotenv`**: `.env` loading for local developer setup and secrets wiring.
- **`pyyaml`**: YAML/OpenAPI related serialization support used by compatibility endpoints.

### Data layer
- **`sqlalchemy`**: ORM and database models for sellers, agents, tools, payments, reputation, and transfers.
- **`alembic`**: schema migrations (`0001_marketplace_schema.py`) to keep DB changes controlled.

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

Use `backend/.env.example` as the source of truth. Key variables:

- **Payment + runtime**
  - `PRIVATE_KEY`: buyer wallet private key.
  - `SELLER_PRIVATE_KEY`: seller-side wallet key for Gateway ops.
  - `SERVER_URL`, `PORT`, `PUBLIC_BASE_URL`.
- **Database**
  - `DATABASE_URL` (default SQLite).
- **Buyer behavior**
  - `BUYER_PROMPT`, `BUYER_TASK`, `BUYER_BUDGET_USDC`, `BUYER_LOOP_SECONDS`.
- **LLM integration (optional)**
  - `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`.
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

Set `metadataUri` to your published card (or metadata document that points to it).

```bash
curl -sX POST http://localhost:4021/sellers/<SELLER_ID>/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Arb Scout v1",
    "description": "Cross-chain opportunity analysis and execution plans",
    "metadataUri": "https://your-agent-domain/.well-known/agent-card.json"
  }'
```

### Step 4: Register on Arc (optional but recommended)

```bash
curl -sX POST http://localhost:4021/agents/<AGENT_ID>/arc/register \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Step 5: Verify your listing and paid invoke path

- Check marketplace visibility: `GET /marketplace/tools`
- Invoke route pattern: `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke`
- Check ledger events: `GET /transactions`

### Current platform compatibility endpoint

`GET /.well-known/agent-card.json` on this backend currently returns a marketplace-level aggregated card (not your individual external card). Keep your own agent card published and treat it as your canonical protocol metadata.

---

## API Highlights

### Marketplace
- `POST /sellers`
- `GET /sellers`
- `GET /sellers/{seller_id}`
- `POST /sellers/{seller_id}/agents`
- `PATCH /sellers/{seller_id}/agents/{agent_id}/pricing`
- `GET /marketplace/tools`
- `POST /marketplace/discover`
- `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke` (payment-gated)
- `GET /transactions`

### Arc lifecycle
- `POST /agents/{agent_id}/arc/register`
- `POST /agents/{agent_id}/arc/reputation`
- `POST /agents/{agent_id}/arc/validation/request`
- `POST /agents/{agent_id}/arc/validation/respond`

### Wallet/Gateway/Bridge
- `POST /sellers/{seller_id}/wallets/provision`
- `POST /sellers/{seller_id}/gateway/deposit`
- `GET /sellers/{seller_id}/gateway/balances`
- `POST /sellers/{seller_id}/bridge/transfers` (currently recorded as queued orchestration stub)

### Compatibility/discovery metadata
- `GET /.well-known/agent-card.json`
- `GET /.well-known/ai-plugin.json`
- `GET /openapi.yaml`

---

## How Buyer/Seller Nanopayments Work (Current Implementation)

1. Buyer discovers target tool and invoke path.
2. Buyer uses Gateway client to call paid endpoint.
3. Seller returns payment challenge when no valid payment signature is present.
4. Buyer signs payment authorization and retries with payment header.
5. Seller verifies payment through Gateway middleware.
6. Seller executes tool, returns response, and logs transaction/payment events.

This design is what enables per-action monetization and high-frequency transaction logging for hackathon evidence.

---

## Hackathon Alignment Snapshot

- Arc + USDC + Circle nanopayment infrastructure: implemented.
- Per-action low-cost priced tools: implemented.
- Transaction event persistence for frequency reporting: implemented.
- Bridge/liquidity advanced workflow execution: partially implemented (bridge endpoint currently stubbed).
- End-to-end polished frontend integration: partial.

---

## Notes for Contributors

- Do not commit real private keys or `.env`.
- If `circle-titanoboa-sdk` is in a different local path, update `backend/pyproject.toml` under `[tool.uv.sources]`.
- Run migrations before first API boot to avoid schema mismatches.
