# Seller APIs and A2A Cards

Travel agents below use `*-agent` Cloud Run services; blog through marketing match [`seller_agents.md`](../seller_agents.md) (`agent-*` hostnames). Both URL styles are live for the overlapping travel skills.

## Deployed API Endpoints

- Hotel Agent message endpoint: `https://hotel-agent-440657628054.us-central1.run.app/a2a/message`
- Flight Agent message endpoint: `https://flight-agent-440657628054.us-central1.run.app/a2a/message`
- Itinerary Agent message endpoint: `https://itinerary-agent-440657628054.us-central1.run.app/a2a/message`
- Blog Agent message endpoint: `https://agent-blog-440657628054.us-central1.run.app/a2a/message`
- Image Agent message endpoint: `https://agent-image-440657628054.us-central1.run.app/a2a/message`
- Coding Agent message endpoint: `https://agent-coding-440657628054.us-central1.run.app/a2a/message`
- Finance Agent message endpoint: `https://agent-finance-440657628054.us-central1.run.app/a2a/message`
- Marketing Agent message endpoint: `https://agent-marketing-440657628054.us-central1.run.app/a2a/message`

## A2A Card URLs

- Hotel Agent card: `https://hotel-agent-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Flight Agent card: `https://flight-agent-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Itinerary Agent card: `https://itinerary-agent-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Blog Agent card: `https://agent-blog-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Image Agent card: `https://agent-image-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Coding Agent card: `https://agent-coding-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Finance Agent card: `https://agent-finance-440657628054.us-central1.run.app/.well-known/agent-card.json`
- Marketing Agent card: `https://agent-marketing-440657628054.us-central1.run.app/.well-known/agent-card.json`

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

### Blog Agent Card

- Name: `Expert Blog Writer Agent`
- Agent ID: `blog_writer_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5056/a2a/message`
- Wallet Address: `0x9789AD5776fD505C026148bB989A69A0DcaC9D28` (`AI_AGENT_4_ADDRESS` in root `.env`)
- Wallet Private Key: `0x95a1e8d575889fe32a0b86c6d34fdd809dce8d4a4aa0dc39b318b4b705e98522` (`AI_AGENT_4_PRIVATE_KEY`)
- Skills:
  - `blog_writing` - High-Quality Blog Writing

### Image Agent Card

- Name: `Descriptive Image Prompt Agent`
- Agent ID: `image_prompt_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5057/a2a/message`
- Wallet Address: `0xf2042aa1F2B6e0A89577397FB3CF9Efd0BcFdf14` (`AI_AGENT_5_ADDRESS` in root `.env`)
- Wallet Private Key: `0x11ff73c14fd46d6beff92b7a88e5b9615dbbb4ced12cfc53b2f934b2e2a47092` (`AI_AGENT_5_PRIVATE_KEY`)
- Skills:
  - `image_prompt_generation` - Artistic Image Prompt Generation

### Coding Agent Card

- Name: `Senior Coding Assistant Agent`
- Agent ID: `coding_assistant_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5058/a2a/message`
- Wallet Address: `0x9523e7F4fdE698f0960aCF178dC3F6274ac40fF8` (`AI_AGENT_6_ADDRESS` in root `.env`)
- Wallet Private Key: `0x80580c3c8f7f12dad725145bd251da40efe16faa0930eb78e56dba005b02a813` (`AI_AGENT_6_PRIVATE_KEY`)
- Skills:
  - `coding_assistance` - Expert Software Engineering

### Finance Agent Card

- Name: `WealthWay Finance Planner`
- Agent ID: `finance_planner_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5059/a2a/message`
- Wallet Address: `0x359eFDE8f61C1D70AE742f9c9B70402889714aCd` (`AI_AGENT_7_ADDRESS` in root `.env`; same address as `SELLER_ADDRESS` when expanded)
- Wallet Private Key: `0x2340f4496709ba3c87d93c6d2f650e0381c627a46ca4d1c5304c105492c6e0da` (`AI_AGENT_7_PRIVATE_KEY`)
- Skills:
  - `financial_planning` - Personal & Business Financial Planning

### Marketing Agent Card

- Name: `BuzzBoost Marketing Specialist`
- Agent ID: `marketing_seo_agent`
- Protocol: `JSONRPC` (`0.3.0`)
- Card endpoint field: `http://127.0.0.1:5060/a2a/message`
- Wallet Address: `0x2bb6bD2631Ff9975F2D1E0bFB12E7690A6aff178` (`AI_AGENT_8_ADDRESS` in root `.env`)
- Wallet Private Key: `0x53f1b749ccbbb1f441206b7a9b1bd36365f61dfd2101b92f77bb26be28b9a1e8` (`AI_AGENT_8_PRIVATE_KEY`)
- Skills:
  - `marketing_strategy` - SEO & Marketing Content Generation

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
