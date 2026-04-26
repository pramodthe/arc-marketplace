# Seller APIs and A2A Cards

## Deployed API Endpoints

- Hotel Agent message endpoint: `https://hotel-agent-440657628054.us-central1.run.app/a2a/message`
- Flight Agent message endpoint: `https://flight-agent-440657628054.us-central1.run.app/a2a/message`
- Itinerary Agent message endpoint: `https://itinerary-agent-440657628054.us-central1.run.app/a2a/message`

## A2A Card URLs

- Hotel Agent card: `https://hotel-agent-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Flight Agent card: `https://flight-agent-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Itinerary Agent card: `https://itinerary-agent-440657628054.us-central1.run.app/.well-known/agent-card.json`

## A2A Card Summary

### Hotel Agent Card

- Name: `StayWise Hotel Intelligence Agent`
- Agent ID: `hotel_finder_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5053/a2a/message`
- Wallet Address: `0xaBB7D9CD054b1E78074c25f8E65c291015871847`
- Wallet Private Key: `0x9143a1192ab4adab447a835a88afbb663ecf06e89f00e3b635dbd509b545f141`
- Skills:
  - `hotel_recommendation` - Hotel Match and Justification

### Flight Agent Card

- Name: `SkyRoute Flight Planning Agent`
- Agent ID: `flight_booker_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5054/a2a/message`
- Wallet Address: `0x3E73EF530980C7fba1FBd18b99a92D03A4851C1a`
- Wallet Private Key: `0xc8237ffa551246bc183cd45ea4ea60904a01a6fb7f7d0479cef48458e5332618`
- Skills:
  - `flight_recommendation` - Cross-Border Flight Recommendation

### Itinerary Agent Card

- Name: `RouteCraft Itinerary Orchestrator`
- Agent ID: `itinerary_writer_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5055/a2a/message`
- Wallet Address: `0x687608B2529F88499007dB7964307286e89da84A`
- Wallet Private Key: `0xf6da20fe4b5820d1c13765587efd6020f48fd2766636437752dc11b1631d3a0a`
- Skills:
  - `itinerary_generation` - Constraint-Based Itinerary Generation

## What's inside?

Each `/.well-known/agent-card.json` includes:

- Agent metadata: `name`, `description`, `id`, `version`
- Connection details: `url`, `endpoint`, `preferredTransport`, `protocolVersion`
- Provider info: `provider.organization`, `provider.url`, `documentationUrl`
- Runtime capabilities: `capabilities.streaming`, `capabilities.stateHistory`
- Auth guidance: `authentication.type` and usage instructions
- Skill catalog: `skills[]` entries with `id`, `name`, `description`, `tags`, `examples`, I/O modes, and pricing fields like `x402PriceUSDC` + `x402Network`

## Authenticated cURL Example (Cloud Run)

```bash
TOKEN=$(gcloud auth print-identity-token)

curl -X POST "https://hotel-agent-440657628054.us-central1.run.app/a2a/message" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-hotel-1",
        "role": "user",
        "parts": [{"text": "I need a hotel in Shinjuku with a budget of $200 per night."}]
      }
    }
  }'
```
