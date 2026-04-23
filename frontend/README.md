# Frontend Backend Hookup Notes

This frontend is wired to the Arc marketplace backend through a thin API client and a view-model mapper.

## API boundary

- API client: `src/api/marketplaceClient.js`
- Base URL: `VITE_API_BASE_URL` (defaults to `http://localhost:4021`)
- Used endpoints:
  - `GET /marketplace/tools`
  - `GET /sellers`
  - `GET /sellers/{seller_id}`
  - `POST /sellers`
  - `POST /sellers/{seller_id}/agents`

## Mapping strategy

- Mapper: `src/lib/agentMappers.js`
- Current backend is tool-centric (`/marketplace/tools`), while UI is agent-card-centric.
- Frontend groups tools by `(seller.id, agent.id)`, then enriches with seller detail payloads.
- Derived UI fields (fallback-based):
  - `tags` from `toolKey`
  - `categoryBadges` from tool count and min price
  - `paymentProtocol` from tool availability
  - `rawMetadata` from aggregated API payloads

## Why this is temporary

This mapping avoids immediate backend changes, but it requires client-side joins and can become N+1 as seller count grows.

Recommended backend contract for long-term stability:

- Add `GET /marketplace/agents` that returns one aggregated card-ready object per agent:
  - identity (`agentId`, `sellerId`, `name`, `description`, `status`)
  - commerce (`toolCount`, `toolKeys`, `minPriceUSDC`, `maxPriceUSDC`)
  - seller context (`sellerName`, `walletAddress`)
  - optional stats (`recentPaidCount`, `recentPaidAmountUSDC`, reputation summary)

When that endpoint is added, swap mapper input to this server-aggregated response and keep UI unchanged.
