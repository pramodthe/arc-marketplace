# Buyer Agent Chatbot

Agentic chatbot that:

- answers normal questions conversationally
- discovers services from A2A agent cards when needed
- decides whether to buy based on remaining budget
- executes purchase via discovered invoke URL (for Agent Alpha, `http://localhost:5051/invoke`)

## Setup

From `test/buyer_agent`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

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
