# Travel Agent Marketplace (A2A Network)

This project demonstrates a multi-agent system using the **Agent-to-Agent (A2A) JSON-RPC protocol**. It consists of a central **Buyer Agent** (Streamlit UI) that intelligently orchestrates tasks by communicating with three specialized **Seller Agents** (Hotel, Flight, and Itinerary) behind the scenes.

## 🏗 Architecture

- **Buyer Agent** (Port `8501`): A Streamlit web application powered by `google-adk` and the Gemini API. It acts as the central orchestrator, breaking down user requests and delegating them to the specialized seller agents via the A2A protocol.
- **Seller Agents** (Ports `5053`, `5054`, `5055`): Independent micro-agents that provide specific travel services. They expose a `.well-known/agent-card.json` defining their capabilities and an `/a2a/message` endpoint for JSON-RPC communication.

---

## 🤖 Seller Agents Overview

### 1. StayWise Hotel Intelligence Agent
* **Port**: `5053`
* **ID**: `hotel_finder_agent`
* **Description**: A hospitality-focused planning agent that recommends hotels by neighborhood fit, transit access, cancellation flexibility, and target spend range for trip execution workflows.
* **Skill - Hotel Match and Justification**: Selects and explains hotel options using nightly budget, district preference, trip duration, and amenity priorities with clear booking trade-offs.

### 2. SkyRoute Flight Planning Agent
* **Port**: `5054`
* **ID**: `flight_booker_agent`
* **Description**: A specialized travel-planning agent for international and domestic flight search strategy, itinerary-fit recommendations, and fare-conscious routing decisions for budget-aware buyers.
* **Skill - Cross-Border Flight Recommendation**: Ranks flight options using route constraints, layover tolerance, departure windows, and budget guidance. Returns a concise rationale with practical trade-offs.

### 3. RouteCraft Itinerary Orchestrator
* **Port**: `5055`
* **ID**: `itinerary_writer_agent`
* **Description**: A planning agent that composes day-by-day travel itineraries from constraints such as budget, pace, arrival/departure windows, and preferred activity mix. Powered by Gemini.
* **Skill - Constraint-Based Itinerary Generation**: Builds practical multi-day plans with pacing, neighborhood sequencing, transit-aware grouping, and fallback options for schedule changes.

---

## 🚀 How to Run

1. Ensure your `.env` file has a valid `GOOGLE_API_KEY` and the `GOOGLE_ADK_MODEL` is set (e.g., `gemini-2.5-flash`).
2. Start the individual seller agents in the background:
   ```bash
   .venv/bin/python -m seller_agent.hotel_agent
   .venv/bin/python -m seller_agent.flight_agent
   .venv/bin/python -m seller_agent.itinerary_agent
   ```
3. Start the Streamlit Buyer UI:
   ```bash
   .venv/bin/python -m streamlit run buyer_agent/streamlit_app.py --server.port 8501
   ```
4. Open [http://localhost:8501](http://localhost:8501) and start planning your trip!

---

## 📄 Agent Card JSON Details (`agent-card.json`)

The A2A network relies on `agent-card.json` files to discover the capabilities and endpoints of each seller agent. You can find the original files at these locations:

### Hotel Agent (`seller_agent/hotel_agent/agent-card.json`)
```json
{
  "name": "StayWise Hotel Intelligence Agent",
  "description": "Hospitality-focused planning agent that recommends hotels by neighborhood fit, transit access, cancellation flexibility, and target spend range for trip execution workflows.",
  "url": "http://127.0.0.1:5053/a2a/message",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "supportsAuthenticatedExtendedCard": false,
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "provider": {
    "organization": "Arc Travel Seller Network",
    "url": "http://localhost:5053"
  },
  "version": "1.0.0",
  "documentationUrl": "http://localhost:5053/docs",
  "capabilities": {
    "streaming": false,
    "stateHistory": true
  },
  "authentication": {
    "type": "x402-or-buyer-id",
    "instructions": "Use marketplace buyerId settlement or x402 Payment-Signature when routed through paid marketplace invoke endpoints."
  },
  "id": "hotel_finder_agent",
  "endpoint": "http://localhost:5053/a2a/message",
  "skills": [
    {
      "id": "hotel_recommendation",
      "name": "Hotel Match and Justification",
      "description": "Selects and explains hotel options using nightly budget, district preference, trip duration, and amenity priorities with clear booking trade-offs.",
      "tags": ["travel", "hotels", "accommodation", "budget-planning", "arc-marketplace", "a2a"],
      "examples": [
        "Suggest 3 hotels in Tokyo for 4 nights under 700 USD total near major subway lines.",
        "Find business-friendly hotels in Shinjuku with flexible cancellation and late check-in."
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"],
      "x402PriceUSDC": 0.01,
      "x402Network": "arcTestnet",
      "category": "Travel"
    }
  ]
}
```

### Flight Agent (`seller_agent/flight_agent/agent-card.json`)
```json
{
  "name": "SkyRoute Flight Planning Agent",
  "description": "Specialized travel-planning agent for international and domestic flight search strategy, itinerary-fit recommendations, and fare-conscious routing decisions for budget-aware buyers.",
  "url": "http://127.0.0.1:5054/a2a/message",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "supportsAuthenticatedExtendedCard": false,
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "provider": {
    "organization": "Arc Travel Seller Network",
    "url": "http://localhost:5054"
  },
  "version": "1.0.0",
  "documentationUrl": "http://localhost:5054/docs",
  "capabilities": {
    "streaming": false,
    "stateHistory": true
  },
  "authentication": {
    "type": "x402-or-buyer-id",
    "instructions": "Use marketplace buyerId settlement or x402 Payment-Signature when routed through paid marketplace invoke endpoints."
  },
  "id": "flight_booker_agent",
  "endpoint": "http://localhost:5054/a2a/message",
  "skills": [
    {
      "id": "flight_recommendation",
      "name": "Cross-Border Flight Recommendation",
      "description": "Ranks flight options using route constraints, layover tolerance, departure windows, and budget guidance. Returns a concise rationale with practical trade-offs.",
      "tags": ["travel", "flights", "fare-optimization", "itinerary-planning", "arc-marketplace", "a2a"],
      "examples": [
        "Find round-trip flights from SFO to NRT in May under 1100 USD with max 1 stop.",
        "Recommend best outbound flight for a 4-day Tokyo trip prioritizing shortest total travel time."
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"],
      "x402PriceUSDC": 0.01,
      "x402Network": "arcTestnet",
      "category": "Travel"
    }
  ]
}
```

### Itinerary Agent (`seller_agent/itinerary_agent/agent-card.json`)
```json
{
  "name": "RouteCraft Itinerary Orchestrator",
  "description": "Planning agent that composes day-by-day travel itineraries from constraints such as budget, pace, arrival/departure windows, and preferred activity mix.",
  "url": "http://127.0.0.1:5055/a2a/message",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "supportsAuthenticatedExtendedCard": false,
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "provider": {
    "organization": "Arc Travel Seller Network",
    "url": "http://localhost:5055"
  },
  "version": "1.0.0",
  "documentationUrl": "http://localhost:5055/docs",
  "capabilities": {
    "streaming": false,
    "stateHistory": true
  },
  "authentication": {
    "type": "x402-or-buyer-id",
    "instructions": "Use marketplace buyerId settlement or x402 Payment-Signature when routed through paid marketplace invoke endpoints."
  },
  "id": "itinerary_writer_agent",
  "endpoint": "http://localhost:5055/a2a/message",
  "skills": [
    {
      "id": "itinerary_generation",
      "name": "Constraint-Based Itinerary Generation",
      "description": "Builds practical multi-day plans with pacing, neighborhood sequencing, transit-aware grouping, and fallback options for schedule changes.",
      "tags": ["travel", "itinerary", "trip-design", "logistics", "arc-marketplace", "a2a"],
      "examples": [
        "Create a 4-day Tokyo itinerary with one major attraction and one food district per day.",
        "Plan a relaxed family itinerary with minimal transfers and evening activities near the hotel."
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"],
      "x402PriceUSDC": 0.01,
      "x402Network": "arcTestnet",
      "category": "Travel"
    }
  ]
}
```
