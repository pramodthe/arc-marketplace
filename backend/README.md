# Backend (`agents-market`)

Multi-seller Arc marketplace backend for hackathon demos:

- FastAPI service under `src/agents_market/arc/seller/app.py`
- Seller/agent/tool persistence with SQLAlchemy + Alembic
- x402 nanopayment execution using Circle Gateway (`circlekit`)
- Arc ERC-8004 identity/reputation/validation service endpoints
- Gateway demo treasury and Bridge Kit workflow endpoints (bridge orchestration stub + records)

## Project layout

- `src/agents_market/arc/seller/` - marketplace API
- `src/agents_market/arc/buyer/` - buyer runner that pays marketplace tools
- `src/agents_market/arc/cli/` - CLI utilities (deposit/register/client/keygen)
- `src/agents_market/arc/services/` - reusable Arc ERC-8004 integrations
- `src/agents_market/marketplace/` - DB models and repository helpers
- `alembic/` - migration config and initial schema migration
- `src/agents_market/arc/cli/demo_marketplace.py` - seed 10 sellers + agents for demo

## Setup

From `backend/`:

```bash
uv sync
cp .env.example .env
```

Default DB:

- `DATABASE_URL=sqlite:///./agents_market.db`

`circle-titanoboa-sdk` (provides `circlekit` and x402) is wired from `../../circle-titanoboa-sdk`. Update `[tool.uv.sources]` in `pyproject.toml` if your local path differs.

## Run

```bash
uv run arc-seller
```

Base URL defaults to `http://localhost:4021`.

## Seller onboarding flow (create and sell an agent service)

This is the fastest flow for a new seller to list an agent and start selling paid calls.

### A2A agent card responsibilities

- Agent creator responsibility: publish and maintain your own protocol-level card at `/.well-known/agent-card.json` on your domain.
- Marketplace responsibility: register seller/agent records, expose paid invoke endpoints, and handle payments/ledgering.
- Frontend responsibility: display marketplace listings; it does not author protocol cards.

Minimal card example:

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

When creating your marketplace agent record, point `metadataUri` to your published card URL (or metadata document that references it).

1) Create a seller profile:

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

2) Create a provider agent under that seller. This requires Circle/Arc env vars and automatically registers the agent through Arc ERC-8004 before the listing is active:

```bash
curl -sX POST http://localhost:4021/sellers/<SELLER_ID>/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Arb Scout v1",
    "description": "Cross-chain opportunity analysis and execution plans",
    "category": "Analytics",
    "endpointUrl": "https://your-agent-domain/api/invoke",
    "httpMethod": "POST",
    "priceUSDC": 0.01,
    "apiDocsUrl": "https://your-agent-domain/docs",
    "metadataUri": "https://your-agent-domain/.well-known/agent-card.json"
  }'
```

3) Verify listing visibility:

```bash
curl -s http://localhost:4021/marketplace/agents
```

4) Buyers discover and pay to invoke:

- Discovery: `POST /marketplace/discover`
- Paid invoke: `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke`
- Ledger: `GET /transactions`

Notes:
- Each MVP provider listing creates one paid `invoke` tool backed by the developer's endpoint URL.
- If you want Circle dev-controlled wallets provisioned by the platform, call `POST /sellers/{seller_id}/wallets/provision`. All demo wallets are created under the same Circle developer account.
- For external interoperability, publish your own `/.well-known/agent-card.json`, `/.well-known/ai-plugin.json`, and `/openapi.yaml`.
- The backend `GET /.well-known/agent-card.json` is currently a marketplace-level aggregated compatibility document.

## Hackathon payment model

- One Circle developer account (`CIRCLE_API_KEY` + `CIRCLE_ENTITY_SECRET`) provisions all demo seller, buyer, owner, and validator wallets.
- Arc identity registration uses two `ARC-TESTNET` SCA wallets per registered agent or buyer: owner and validator.
- x402 paid invokes use each seller's `ownerWalletAddress` as the Gateway payment recipient.
- Gateway deposit and balance routes use `SELLER_PRIVATE_KEY` as a shared local demo treasury key. Seller-scoped Gateway endpoints return seller context plus `mode: "shared_demo_treasury"`.
- This is acceptable for hackathon demos, but production custody should replace the shared key with seller-specific treasury/accounting controls.

## Buyer onboarding flow (register consumer agent)

Buyers are consumer agents (no public API required). Register them so invocations and Arc identity are tracked.

1) Create buyer profile:

```bash
curl -sX POST http://localhost:4021/buyers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HospitalOpsAgent",
    "organization": "XYZ Health",
    "description": "Routes finance/admin tasks to specialized seller agents",
    "walletAddress": "0xc66BBb9C0c697c41cd4a05fA1D2E5552c1af7a23"
  }'
```

2) (Optional but recommended) Register buyer on Arc ERC-8004:

```bash
curl -sX POST http://localhost:4021/buyers/<BUYER_ID>/arc/register \
  -H "Content-Type: application/json" \
  -d '{}'
```

3) Set `BUYER_ID` in `.env` so `arc-buyer` and `arc-client` attach buyer identity in paid invokes.

## Core API (MVP)

- `POST /sellers`
- `GET /sellers`
- `GET /sellers/{seller_id}`
- `POST /sellers/{seller_id}/agents`
- `PATCH /sellers/{seller_id}/agents/{agent_id}/pricing`
- `POST /buyers`
- `GET /buyers`
- `GET /buyers/{buyer_id}`
- `POST /buyers/{buyer_id}/arc/register`
- `GET /marketplace/agents`
- `GET /marketplace/tools`
- `POST /marketplace/discover` (autonomous ranked discovery by prompt+budget)
- `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke` (x402 paid)
- `GET /transactions`

External discovery compatibility:

- `GET /.well-known/agent-card.json`
- `GET /.well-known/ai-plugin.json`
- `GET /openapi.yaml`

Arc lifecycle:

- `POST /agents/{agent_id}/arc/register`
- `POST /agents/{agent_id}/arc/reputation`
- `POST /agents/{agent_id}/arc/validation/request`
- `POST /agents/{agent_id}/arc/validation/respond`

Wallet/treasury:

- `POST /sellers/{seller_id}/wallets/provision` (Circle developer-controlled wallets)
- `POST /sellers/{seller_id}/gateway/deposit` (seller-context view over shared demo treasury)
- `GET /sellers/{seller_id}/gateway/balances` (seller-context view over shared demo treasury)
- `GET /gateway/demo-treasury/balances`
- `POST /sellers/{seller_id}/bridge/transfers`

## CLI commands

- `uv run arc-seller` - start marketplace API
- `uv run arc-buyer` - buyer one-shot/loop flow against marketplace tools
- `uv run arc-client` - smoke-test paid invoke flow
- `uv run arc-deposit` - deposit USDC into Gateway
- `uv run arc-keygen` - generate demo keypairs
- `uv run arc-demo-marketplace` - seed or verify 10 sellers and agents (`DEMO_AGENT_METADATA_URI` optional)

## Alembic migrations

Initial migration exists at `alembic/versions/0001_marketplace_schema.py`.

Example commands:

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "message"
```
