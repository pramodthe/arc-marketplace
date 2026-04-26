# Autonomous LLM marketplace buyer

This example runs a **real LLM** with **tool calling** against your marketplace HTTP API: **discover**, optional **list tools**, then **invoke** with `buyerId` (same settlement path as [`BuyerMarketplaceSDK`](../../backend/src/agents_market/arc/buyer/sdk.py)).

**Providers:** this script expects **`GEMINI_API_KEY`** or **`GOOGLE_API_KEY`** for **Gemini**. Optional **`GEMINI_API_BASE_URL`** sets LangChain’s `ChatGoogleGenerativeAI.base_url`. **`OPENAI_API_KEY`** is supported only if you explicitly want OpenAI; other `.env` keys like **`LLM_API_KEY`** are **not** read by `run_agent.py` (they may be used elsewhere in the repo).

It is the right place for **reasoning and planning**. The marketplace still **routes and settles**; the **provider** behind each tool may return stub or template text unless you point tools at a model-backed endpoint.

## Prerequisites

- Backend marketplace running (for example `http://localhost:4021`).
- At least one registered seller/agent/tool (for example `uv run arc-demo-marketplace` from `backend/`, or your own `POST /sellers` / agents / capabilities flow).
- **Gemini or OpenAI** keys: see [Where to put API keys](#where-to-put-api-keys) below.
- Optional: a **funded buyer** on Arc for paid invokes; set **`BUYER_ID`** to **reuse one buyer** and avoid creating duplicate buyer rows.

## Where to put API keys

The script is **run from `backend/`** so `import agents_market` works, but env can live in **two** places (both are loaded):

1. **`agents_market/backend/.env`** and then **`agents_market/.env`** (repo root) — same files the FastAPI backend uses (`load_backend_env()`).
2. **`agents_market/examples/autonomous_marketplace_buyer/.env`** — optional **sidecar** next to `run_agent.py`. Loaded **after** (1); it only sets variables that are **still unset** (`override=False`), so you can keep **Gemini only** here while the backend `.env` holds Circle / Arc / DB.

Template: copy [`env.example`](env.example) to **`.env` in this same folder**:

```bash
cd examples/autonomous_marketplace_buyer
cp env.example .env
# edit .env — set GEMINI_API_KEY, BUYER_ID, SERVER_URL if needed
```

Then run from `backend/` as usual. The sidecar **`.env`** is the file in **this example folder** (loaded after `backend/.env`).

## Browser chat (example-only server)

This does **not** add routes to **`arc-seller`**. A small FastAPI app in **`chat_server.py`** (same folder) exposes **`POST /demo/autonomous-llm-buyer/chat`** on port **9095** by default. The HTML page talks to **that** server; keys stay in **`.env`** files, not in the browser.

1. **`uv sync --group llm-buyer`** (from `backend/`).
2. Set **`GEMINI_API_KEY`** / **`GOOGLE_API_KEY`** (or **`OPENAI_API_KEY`**) in **`backend/.env`** and/or **`examples/autonomous_marketplace_buyer/.env`**.
3. Keep **`arc-seller`** running on **4021** (marketplace). In another terminal:

```bash
cd backend
uv run --group llm-buyer python ../examples/autonomous_marketplace_buyer/chat_server.py
```

4. From **`QA_test/`**: `python3 -m http.server 8080` → open **`http://localhost:8080/autonomous_buyer_chat_demo.html`**. Set **Chat server URL** to **`http://localhost:9095`** (or your **`AUTONOMOUS_BUYER_CHAT_PORT`**).

## Install (LangChain deps are optional on the main wheel)

From `backend/`:

```bash
uv sync --group llm-buyer
```

## Run (Gemini)

```bash
cd backend
export GEMINI_API_KEY="..."   # or GOOGLE_API_KEY
# optional:
# export GEMINI_API_BASE_URL="https://generativelanguage.googleapis.com"
export BUYER_ID="3"
export MARKETPLACE_AGENT_NAME_SUBSTRING="Demo Multi-Tool Hub"   # optional
uv run --group llm-buyer python ../examples/autonomous_marketplace_buyer/run_agent.py \
  "I need a quick stub weather-style line for a demo slide."
```

## Run (OpenAI)

```bash
cd backend
export OPENAI_API_KEY="sk-..."
export BUYER_ID="3"
uv run --group llm-buyer python ../examples/autonomous_marketplace_buyer/run_agent.py \
  "I need a quick stub weather-style line for a demo slide."
```

Pipe a goal on stdin:

```bash
echo "Compare summarize vs weather tools for a one-line update." | uv run --group llm-buyer python ../examples/autonomous_marketplace_buyer/run_agent.py
```

### Environment

| Variable | Purpose |
|----------|---------|
| `SERVER_URL` | Marketplace base URL (default `http://localhost:4021`) |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini (Google AI Studio); required unless you only set `OPENAI_API_KEY`. |
| `GEMINI_API_BASE_URL` / `GOOGLE_API_BASE_URL` | Optional `base_url` for the Gemini HTTP client (override default Google endpoint). |
| `OPENAI_API_KEY` | Optional ChatGPT/OpenAI — only if set; not inferred from `LLM_API_KEY`. |
| `OPENAI_BASE_URL` / `OPENAI_API_BASE` | Optional OpenAI-compatible API base. |
| `LLM_BUYER_MODEL` | Model id (default `gemini-2.0-flash`; with OpenAI path default `gpt-4o-mini`). |
| `BUYER_ID` | Reuse existing buyer (recommended). |
| `BUYER_NAME` | Display name when creating a new buyer (only if `BUYER_ID` unset). |
| `MARKETPLACE_AGENT_NAME_SUBSTRING` | Filter discover/list results to agents whose name contains this substring (case-insensitive). |

### Flags

- `--verbose` — print the full LangChain message list to stderr.

## Relation to other demos

- **[`QA_test/buyer_agent_chatbot_demo.html`](../../QA_test/buyer_agent_chatbot_demo.html)** — browser-only **orchestration** (no LLM). Good for click-through demos of HTTP flow.
- **This script** — **LLM + tools** for a realistic autonomous buyer story.
- Stub **provider** endpoints (fixed `outputText` templates) are fine for integration testing; this agent supplies the **autonomous** layer on the buyer side.
