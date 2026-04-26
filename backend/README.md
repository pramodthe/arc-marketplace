# Backend (`agents-market`)

Multi-seller Arc marketplace backend for hackathon demos:

- FastAPI service under `src/agents_market/arc/seller/app.py`
- Seller/agent/tool persistence with SQLAlchemy + Alembic
- [Circle Gateway Nanopayments](https://developers.circle.com/gateway/nanopayments): x402 via `circlekit` (`arcTestnet`) for external buyers
- [Arc](https://docs.arc.network/arc/references/connect-to-arc) USDC on ARC-TESTNET for registered buyers (`buyerId` + Circle developer-controlled wallets)
- `GET /` and successful `.../invoke` responses include `paymentRails` metadata linking both rails for integrations and demos
- Arc ERC-8004 identity/reputation/validation service endpoints
- Gateway demo treasury and `POST .../bridge/transfers` (persists a transfer row; orchestration is a hackathon stub, not live Bridge Kit execution)

## Project layout

- `src/agents_market/arc/seller/` - marketplace API
- `src/agents_market/arc/buyer/` - `BuyerMarketplaceSDK` client, `arc-buyer` runner, and related helpers
- `src/agents_market/arc/cli/` - CLI utilities (deposit, client, keygen, demo marketplace seed, and related helpers)
- `src/agents_market/arc/services/` - reusable Arc ERC-8004 integrations
- `src/agents_market/marketplace/` - DB models and repository helpers
- `alembic/` - Alembic config; versioned revisions under `alembic/versions/` (see Alembic section below)
- `src/agents_market/arc/cli/demo_marketplace.py` - seed 10 sellers + agents for demo

## Setup

From `backend/`:

```bash
uv sync
cp .env.example .env
```

Optional **LangChain** dependency group for the autonomous marketplace buyer example (Gemini and/or OpenAI; not required to run the API):

```bash
uv sync --group llm-buyer
```

Set **`GEMINI_API_KEY`** or **`GOOGLE_API_KEY`** (and optional **`GEMINI_API_BASE_URL`**) in `backend/.env` — see `backend/.env.example` and [`../examples/autonomous_marketplace_buyer/README.md`](../examples/autonomous_marketplace_buyer/README.md).

Default DB:

- `DATABASE_URL=sqlite:///./agents_market.db`

`circlekit` is required for x402 paid invoke. If it is unavailable, invoke requests fail closed and a `payment` event with `status=failed` is recorded in `payment_events` (visible via `GET /transactions`).

## Run

```bash
uv run arc-seller
```

Base URL defaults to `http://localhost:4021`.

## Docker deploy (demo prototype)

From the repo root:

```bash
docker compose up --build
```

- Backend: `http://localhost:4021`
- Frontend: `http://localhost:5173`

Ensure the backend image/runtime includes `circlekit`; otherwise x402 invokes will return failure and be logged to the transactions ledger.

## QA and smoke validation

```bash
# QA-only suites are maintained under ../QA_test (do not modify during backend cleanup).
# For deployment checks, run backend + frontend smoke flows:
uv run arc-seller
# then verify /health, /marketplace/agents, paid invoke paths, and /transactions
```

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
    "offeringType": "agent",
    "protocolType": "http",
    "endpointUrl": "https://your-agent-domain/api/invoke",
    "httpMethod": "POST",
    "priceUSDC": 0.01,
    "apiDocsUrl": "https://your-agent-domain/docs",
    "metadataUri": "https://your-agent-domain/.well-known/agent-card.json"
  }'
```

`offeringType` values: `agent`, `skill`, `mcp_service`  
`protocolType` values: `http`, `mcp`, `a2a`

3) Verify listing visibility:

```bash
curl -s http://localhost:4021/marketplace/agents
```

4) Buyers discover and pay to invoke:

- Discovery: `POST /marketplace/discover`
- Paid invoke: `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke`
- Ledger: `GET /transactions`

Paid invokes support two settlement modes:
- x402/Gateway: call without payment to receive `402 Payment Required`, then retry with `Payment-Signature`.
- Registered buyer: include `buyerId` to settle Arc USDC from the platform-managed buyer wallet.

Notes:
- Each MVP provider listing creates one paid `invoke` tool backed by the developer's endpoint URL.
- **x402:** the first unpaid request returns **402** only; after the client retries with `Payment-Signature`, the seller preflights `{origin}/health`, then verifies payment. **`buyerId`:** preflight runs before Arc USDC settlement and provider invoke.
- Endpoints resolving to localhost/private networks are blocked unless `ALLOW_PRIVATE_PROVIDER_ENDPOINTS=true` is set for local demos.
- If you want Circle dev-controlled wallets provisioned by the platform, call `POST /sellers/{seller_id}/wallets/provision`. All demo wallets are created under the same Circle developer account.
- For external interoperability, publish your own `/.well-known/agent-card.json`, `/.well-known/ai-plugin.json`, and `/openapi.yaml`.
- The backend `GET /.well-known/agent-card.json` is currently a marketplace-level aggregated compatibility document.

## Hackathon payment model

- One Circle developer account (`CIRCLE_API_KEY` + `CIRCLE_ENTITY_SECRET`) provisions all demo seller, buyer, owner, and validator wallets.
- Arc identity registration uses two `ARC-TESTNET` SCA wallets per registered agent or buyer: owner and validator.
- x402 paid invokes use each seller's `ownerWalletAddress` as the Gateway payment recipient.
- buyerId paid invokes transfer Arc USDC from the registered buyer wallet to the seller owner wallet.
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

Service:

- `GET /` — API metadata
- `GET /health` — liveness (also used as the default provider preflight target under `{origin}/health`)

Sellers and listings:

- `POST /sellers`
- `GET /sellers`
- `GET /sellers/{seller_id}`
- `PATCH /sellers/{seller_id}/status`
- `GET /sellers/{seller_id}/balances`
- `POST /sellers/{seller_id}/agents`
- `DELETE /sellers/{seller_id}/agents/{agent_id}`
- `PATCH /sellers/{seller_id}/agents/{agent_id}/pricing`
- `PATCH /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/pricing`

Buyers:

- `POST /buyers`
- `GET /buyers`
- `GET /buyers/{buyer_id}`
- `GET /buyers/{buyer_id}/balances`
- `POST /buyers/{buyer_id}/arc/register`

Marketplace and tools:

- `GET /marketplace/agents`
- `GET /marketplace/tools`
- `GET /tools` — legacy-shaped tool listing (invoke path, price string, seller/agent names)
- `POST /marketplace/discover` (autonomous ranked discovery by prompt+budget)
- `POST /sellers/{seller_id}/agents/{agent_id}/tools/{tool_id}/invoke` (paid invoke; x402 or `buyerId`)

Ledger:

- `GET /transactions`
- `GET /transactions/view` — HTML ledger view

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

## Buyer SDK (`BuyerMarketplaceSDK`)

Use [`src/agents_market/arc/buyer/sdk.py`](src/agents_market/arc/buyer/sdk.py) instead of re-implementing discovery, buyer registration, and invoke URL handling. The public entry point is `agents_market.arc.buyer` (re-exports `BuyerMarketplaceSDK`, `BuyerProfile`, `ToolCandidate`).

**What it covers**

- `ensure_buyer()` / `POST /buyers` when you omit `buyer_id` and call `invoke(..., include_buyer_id=True)`.
- `discover()` → `POST /marketplace/discover` returning `ToolCandidate` rows (absolute `invoke_url`, skills metadata).
- `list_tools()` → `GET /marketplace/tools` as a fallback catalog.
- `pick_best(...)` for budget- and task-aware selection (same heuristics as `uv run arc-buyer`).
- `invoke()` → `POST` to the tool’s invoke URL with JSON `prompt`, `selectedSkills`, and optional `buyerId` for registered Arc USDC settlement.
- `candidate_from_tool_dict(item)` builds a `ToolCandidate` from a discover/tool-listing dict (e.g. when your agent already picked a row and only needs to invoke).

**What it does not cover**

- x402 / `402` + `Payment-Signature` flows stay in your agent or in `circlekit`; the SDK only sends a plain JSON body.

### Example (async)

```python
from decimal import Decimal
import asyncio

from agents_market.arc.buyer import BuyerMarketplaceSDK


async def main() -> None:
    sdk = BuyerMarketplaceSDK(
        server_url="http://localhost:4021",
        buyer_name="My Buyer Agent",
        # optional: buyer_id=123 to reuse an existing buyer from POST /buyers
    )
    candidates = await sdk.discover(
        prompt="Find me a concise market summary.",
        budget_usdc=Decimal("0.01"),
        desired_tool="auto",
        max_results=5,
    )
    marketplace_tools = await sdk.list_tools()
    desired = sdk.desired_tool_from_prompt(task="auto", prompt="Find me a concise market summary.")
    tool, reason = sdk.pick_best(
        desired_tool=desired,
        budget_usdc=Decimal("0.01"),
        candidates=candidates,
        fallback_tools=marketplace_tools,
    )
    if tool is None:
        print("no tool:", reason)
        return
    result = await sdk.invoke(
        candidate=tool,
        prompt="Give me today's top 3 insights.",
        selected_skills=tool.first_skill_keys(limit=1),
        include_buyer_id=True,
    )
    print(result.get("outputText"))


asyncio.run(main())
```

### Using the SDK from another repo or a lightweight venv

If you depend on this package via `pip install -e .` / `uv sync` from `backend/`, imports work as above.

If you only want **source access** without installing the full backend wheel (which pulls `circle-titanoboa-sdk` and other seller dependencies), point `PYTHONPATH` at `backend/src` and install **`httpx`** in that environment; then `from agents_market.arc.buyer import BuyerMarketplaceSDK` resolves. Your agent code is responsible for any extra deps (e.g. LangChain, Google ADK, `circlekit` for x402).

### In-repo demo: test buyer chatbot

The interactive QA buyer under [`../QA_test/buyer_agent/`](../QA_test/buyer_agent/) uses the same SDK for marketplace discovery and for `simulate` / `onchain` invokes against marketplace URLs. The built-in CLI buyer (`uv run arc-buyer`, [`src/agents_market/arc/buyer/run.py`](src/agents_market/arc/buyer/run.py)) also uses `BuyerMarketplaceSDK` directly.

## Alembic migrations

Schema is evolved through multiple revisions under `alembic/versions/` (apply all with `upgrade head`). Current files, in order:

| Revision | File | Purpose (summary) |
| --- | --- | --- |
| `0001` | `0001_marketplace_schema.py` | Initial marketplace schema |
| `0002` | `0002_buyer_tables.py` | Buyer tables |
| `0003` | `0003_agent_icon_data_url.py` | Agent `icon_data_url` column |
| `0004` | `0004_provider_listing_fields.py` | Provider listing columns on `agents` (category, endpoint, health, etc.) |
| `0005` | `0005_onchain_capabilities.py` | Tool capability columns; `skills` and `usage_records` tables |
| `0006` | `0006_agent_offering_protocol.py` | Agent `offering_type` and `protocol_type` columns |

Example commands:

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "message"
```

## Deployment smoke checklist

Use this checklist before each deployment (SQLite and Arc testnet):

1. Start backend and confirm liveness:
   - `uv run arc-seller`
   - `GET /health` returns `status=ok`.
2. Seller onboarding:
   - `POST /sellers`
   - `POST /sellers/{seller_id}/agents` with capability endpoint + pricing.
3. Buyer SDK readiness:
   - Run `uv run arc-buyer` or a custom script using `BuyerMarketplaceSDK.discover()` and `invoke()`.
4. Payment rails:
   - x402 path: first invoke without `Payment-Signature` returns HTTP 402, retry with signature succeeds.
   - x402 strict mode: invalid signature or unavailable x402 runtime fails invoke and records `payment.status=failed` with `failureCode` in `/transactions`.
   - buyerId path: invoke with registered `buyerId` settles Arc USDC and returns output.
5. Ledger and UI:
   - `GET /transactions` includes payment + seller_output rows.
   - frontend loads from backend APIs only (`/marketplace/agents`, `/transactions`) and `npm run build` succeeds.
