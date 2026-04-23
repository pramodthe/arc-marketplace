# Agent Alpha (Demo)

Standalone demo AI agent with:

- FastAPI API endpoint (`POST /invoke`)
- OpenAI function tool-calling (basic math add tool)
- A2A-style metadata endpoints (`/.well-known/agent-card.json`, `/.well-known/ai-plugin.json`)

Pricing source of truth for this demo is the marketplace backend/frontend flow. Agent Alpha's A2A card does not publish a separate price field to avoid pricing drift.

## 1) Run agent_alpha

From `demo_agents/agent_alpha`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 5051
```

Set your OpenAI key in `.env`:

```bash
OPENAI_API_KEY=your_real_openai_key
```

Test:

```bash
curl -s http://localhost:5051/health
curl -s http://localhost:5051/.well-known/agent-card.json
curl -sX POST http://localhost:5051/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Add 20 and 22"}'
```

## 2) Connect it to marketplace discovery

Set this in `backend/.env`:

```bash
EXTERNAL_AGENT_CARDS=http://localhost:5051/.well-known/agent-card.json
```

Restart backend (`uv run arc-seller`) and test discovery:

```bash
curl -sX POST http://localhost:4021/marketplace/discover \
  -H "Content-Type: application/json" \
  -d '{"prompt":"add 2 and 3","budgetUSDC":1,"desiredTool":"auto","maxResults":5}'
```

## 3) Optional: register Agent Alpha in platform DB too

If you also want Alpha listed as an internal marketplace agent record:

```bash
curl -sX POST http://localhost:4021/sellers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AlphaAgent Labs",
    "description": "Demo seller for Agent Alpha",
    "ownerWalletAddress": "0x9789AD5776fD505C026148bB989A69A0DcaC9D28",
    "validatorWalletAddress": "0xaBB7D9CD054b1E78074c25f8E65c291015871847"
  }'
```

```bash
curl -sX POST http://localhost:4021/sellers/<SELLER_ID>/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Agent Alpha",
    "description": "OpenAI function-calling math agent",
    "metadataUri": "http://localhost:5051/.well-known/agent-card.json"
  }'
```

## 4) Run buyer agent

In `backend/.env`, set:

```bash
BUYER_PROMPT=Please add 14 and 29
BUYER_TASK=auto
BUYER_BUDGET_USDC=1.0
```

Then run:

```bash
uv run arc-buyer
```

Note: `agent_alpha` is intentionally a local demo endpoint and does not enforce x402 directly.
