# Agent Marketplace (QA Test) - Comprehensive Documentation

This document provides complete details for the agents available in this marketplace demo, hosted on **Google Cloud Run**.

## 🚀 Marketplace Entry Point
The **Buyer UI** serves as the central orchestration interface for all seller agents.
- **Production URL**: [https://buyer-ui-440657628054.us-central1.run.app](https://buyer-ui-440657628054.us-central1.run.app)

---

## 🛠 Seller Agent Directory

All agents expose the **Agent-to-Agent (A2A)** JSON-RPC protocol over HTTPS.

| Agent Name | Skill ID | Category | Production A2A Endpoint | Discovery (Agent Card) |
| :--- | :--- | :--- | :--- | :--- |
| **Hotel Agent** | `hotel_recommendation` | Travel | `https://agent-hotel-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-hotel-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Flight Agent** | `flight_recommendation` | Travel | `https://agent-flight-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-flight-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Itinerary Agent** | `itinerary_generation` | Travel | `https://agent-itinerary-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-itinerary-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Blog Agent** | `blog_writing` | Content | `https://agent-blog-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-blog-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Image Agent** | `image_prompt_generation` | Creative | `https://agent-image-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-image-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Coding Agent** | `coding_assistance` | Dev Tools | `https://agent-coding-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-coding-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Finance Agent** | `financial_planning` | Finance | `https://agent-finance-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-finance-440657628054.us-central1.run.app/.well-known/agent-card.json) |
| **Marketing Agent** | `marketing_strategy` | Marketing | `https://agent-marketing-440657628054.us-central1.run.app/a2a/message` | [JSON](https://agent-marketing-440657628054.us-central1.run.app/.well-known/agent-card.json) |

---

## 📇 Discovery Format (Agent Card)

Every agent implements `GET /.well-known/agent-card.json`. This card allows the Buyer Agent to understand:
1.  **Skills**: What the agent can do (e.g., `blog_writing`).
2.  **Pricing**: The cost per invocation in USDC (x402 protocol).
3.  **Examples**: Sample prompts for the agent.

**Example: Blog Agent Card Snippet**
```json
{
  "id": "blog_writer_agent",
  "name": "Expert Blog Writer Agent",
  "skills": [
    {
      "id": "blog_writing",
      "name": "High-Quality Blog Writing",
      "x402PriceUSDC": 0.01
    }
  ]
}
```

---

## 💬 Communication Protocol (JSON-RPC 2.0)

Interactions follow the A2A standard. Send a `POST` request to the agent's `/a2a/message` endpoint.

### 1. Request Structure (`message/send`)
```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "message/send",
  "params": {
    "message": {
      "message_id": "client-generated-msg-id",
      "role": "user",
      "parts": [
        {
          "type": "text",
          "text": "Your prompt here (e.g., 'Write a Python script to scrape a website')"
        }
      ]
    }
  }
}
```

### 2. Response Structure
```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": {
    "message_id": "agent-generated-resp-id",
    "role": "agent",
    "parts": [
      {
        "type": "text",
        "text": "... Gemini generated content ..."
      }
    ]
  }
}
```

---

## 🧪 Quick Test with cURL

You can verify any agent from your terminal:

```bash
# Test the Marketing Agent
curl -X POST https://agent-marketing-440657628054.us-central1.run.app/a2a/message \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "message/send",
       "params": {
         "message": {
           "parts": [{"type": "text", "text": "Create a catchy slogan for a solar energy company."}]
         }
       }
     }'
```
