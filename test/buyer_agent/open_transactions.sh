#!/usr/bin/env bash
set -euo pipefail

# Opens explorer pages for buyer/seller wallets and latest transaction.
# Works best after running a buyer invocation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"
ROOT_ENV_FILE="${ROOT_ENV_FILE:-$SCRIPT_DIR/../../.env}"
BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://localhost:4022}"
EXPLORER_BASE_URL="${EXPLORER_BASE_URL:-https://testnet.arcscan.app}"

# Optional explicit overrides:
# BUYER_WALLET_ADDRESS=0x...
# SELLER_WALLET_ADDRESS=0x...

read_env_var() {
  local file_path="$1"
  local key="$2"
  python3 - "$file_path" "$key" <<'PY'
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
key = sys.argv[2]

if not env_file.exists():
    print("")
    raise SystemExit

for raw in env_file.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    if k.strip() != key:
        continue
    value = v.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    print(value)
    break
else:
    print("")
PY
}

read_root_seller_wallets() {
  python3 - "$ROOT_ENV_FILE" <<'PY'
import re
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
if not env_file.exists():
    raise SystemExit

pattern = re.compile(r"^AI_AGENT_\d+_ADDRESS$")
for raw in env_file.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    key = k.strip()
    if not pattern.match(key):
        continue
    value = v.strip().strip('"').strip("'")
    if value:
        print(value)
PY
}

BUYER_WALLET_ADDRESS="${BUYER_WALLET_ADDRESS:-}"
SELLER_WALLET_ADDRESS="${SELLER_WALLET_ADDRESS:-}"

if [[ -z "$BUYER_WALLET_ADDRESS" ]]; then
  BUYER_WALLET_ADDRESS="$(read_env_var "$ENV_FILE" "BUYER_WALLET_ADDRESS")"
fi
if [[ -z "$SELLER_WALLET_ADDRESS" ]]; then
  SELLER_WALLET_ADDRESS="$(read_env_var "$ENV_FILE" "SELLER_WALLET_ADDRESS")"
fi

if [[ -z "$BUYER_WALLET_ADDRESS" ]]; then
  BUYER_WALLET_ADDRESS="$(read_env_var "$ROOT_ENV_FILE" "CLIENT_ADDRESS")"
fi

get_latest_event_json() {
  local raw
  raw="$(curl -sS "${BACKEND_BASE_URL}/transactions" || true)"
  python3 - "$raw" <<'PY'
import json,sys
raw = sys.argv[1].strip() if len(sys.argv) > 1 else ""
if not raw:
    print("{}")
    raise SystemExit
try:
    data = json.loads(raw)
except Exception:
    print("{}")
    raise SystemExit
events = data.get("events", [])
for event in events:
    ref = (
        event.get("onchainTxHash")
        or event.get("transactionRef")
        or event.get("details", {}).get("onchainTxHash")
        or event.get("details", {}).get("transaction")
        or event.get("details", {}).get("transactionRef")
    )
    if ref:
        print(json.dumps(event))
        break
else:
    print(json.dumps(events[0]) if events else "{}")
PY
}

get_first_seller_wallet() {
  local raw
  raw="$(curl -sS "${BACKEND_BASE_URL}/marketplace/agents" || true)"
  python3 - "$raw" <<'PY'
import json,sys
raw = sys.argv[1].strip() if len(sys.argv) > 1 else ""
if not raw:
    print("")
    raise SystemExit
try:
    data = json.loads(raw)
except Exception:
    print("")
    raise SystemExit
agents = data.get("agents", [])
if not agents:
    print("")
    raise SystemExit
seller = agents[0].get("seller", {})
print(str(seller.get("walletAddress", "")))
PY
}

LATEST_EVENT="$(get_latest_event_json)"
LATEST_TX_HASH="$(python3 - "$LATEST_EVENT" <<'PY'
import json,sys
event=json.loads(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1] else {}
print(str(event.get("onchainTxHash","") or event.get("transactionRef","") or event.get("details",{}).get("onchainTxHash","") or event.get("details",{}).get("transaction","") or event.get("details",{}).get("transactionRef","")))
PY
)"

is_onchain_tx_hash() {
  local tx="$1"
  [[ "$tx" =~ ^0x[0-9a-fA-F]{64}$ ]]
}
LATEST_BUYER_ADDRESS="$(python3 - "$LATEST_EVENT" <<'PY'
import json,sys
event=json.loads(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1] else {}
print(str(event.get("details",{}).get("payer","") or event.get("details",{}).get("buyerAddress","")))
PY
)"

if [[ -z "$BUYER_WALLET_ADDRESS" && -n "$LATEST_BUYER_ADDRESS" ]]; then
  BUYER_WALLET_ADDRESS="$LATEST_BUYER_ADDRESS"
fi

if [[ -z "$SELLER_WALLET_ADDRESS" ]]; then
  SELLER_WALLET_ADDRESS="$(get_first_seller_wallet)"
fi

open_url() {
  local url="$1"
  echo "Opening: $url"
  open "$url"
}

echo "Explorer base: ${EXPLORER_BASE_URL}"
echo "Backend base:  ${BACKEND_BASE_URL}"

if [[ -n "$BUYER_WALLET_ADDRESS" ]]; then
  open_url "${EXPLORER_BASE_URL}/address/${BUYER_WALLET_ADDRESS}"
else
  echo "Buyer wallet address not found. Set BUYER_WALLET_ADDRESS in env."
fi

if [[ -n "$SELLER_WALLET_ADDRESS" ]]; then
  open_url "${EXPLORER_BASE_URL}/address/${SELLER_WALLET_ADDRESS}"
else
  echo "Seller wallet address not found. Set SELLER_WALLET_ADDRESS in env."
fi

if [[ -n "$LATEST_TX_HASH" ]] && is_onchain_tx_hash "$LATEST_TX_HASH"; then
  open_url "${EXPLORER_BASE_URL}/tx/${LATEST_TX_HASH}"
elif [[ -n "$LATEST_TX_HASH" ]]; then
  echo "Latest transaction ref is not an on-chain hash: ${LATEST_TX_HASH}"
  echo "Skipping tx explorer link (Arcscan expects a 0x-prefixed 64-byte hash)."
else
  echo "No latest tx hash found in ${BACKEND_BASE_URL}/transactions."
fi
