# Frontend Backend Hookup Notes

This frontend is wired to the Arc marketplace backend through a thin API client and a view-model mapper.

## API boundary

- API client: `src/api/marketplaceClient.js`
- Base URL: `VITE_API_BASE_URL` (defaults to `http://localhost:4021`)
- Main marketplace endpoint: `GET /marketplace/agents`
- Mutation endpoints:
  - `POST /sellers`
  - `POST /sellers/{seller_id}/agents`
  - `PATCH /sellers/{seller_id}/agents/{agent_id}/pricing`

## Mapping strategy

- Mapper: `src/lib/agentMappers.js`
- Backend returns one card-ready object per provider listing from `/marketplace/agents`.
- The mapper only adapts backend field names into the existing UI shape; it does not add placeholder profile data.
- The registration form submits the MVP provider fields: name, description, category, endpoint URL, method, price, optional wallet, optional docs URL, optional metadata/A2A URL, and optional icon.
