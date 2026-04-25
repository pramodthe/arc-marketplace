# Repository Guidelines

## Project Structure & Module Organization

- `backend/src/agents_market/`: FastAPI API, buyer/seller runners, Arc services, marketplace models, and CLI entry points.
- `backend/alembic/`: database migration environment and versioned schema changes.
- `frontend/src/`: Vite React app, API client, mappers, styles, and reusable UI primitives under `components/ui/`.
- `demo_agents/`: sample external agents used for local marketplace demos.
- `test/buyer_agent/`: buyer-agent scripts and environment template for manual integration testing.

Keep new code inside the existing domain area it extends. Backend schema changes belong in Alembic migrations; frontend shared UI should live under `frontend/src/components/ui/`.

## Build, Test, and Development Commands

Run backend commands from `backend/`:

- `uv sync`: install Python 3.12 dependencies.
- `cp .env.example .env`: create local config.
- `uv run alembic upgrade head`: apply database migrations.
- `uv run arc-seller`: start the marketplace API on `http://localhost:4021`.
- `uv run arc-demo-marketplace`: seed or verify demo sellers and agents.
- `uv run arc-buyer` or `uv run arc-client`: run buyer-side demo flows.

Run frontend commands from `frontend/`:

- `npm install`: install Vite/React dependencies.
- `npm run dev`: start the local frontend dev server.
- `npm run build`: produce a production build.
- `npm run lint`: run ESLint over the frontend.

## Coding Style & Naming Conventions

Python uses 4-space indentation, type hints where useful, `snake_case` modules/functions, and `PascalCase` ORM or schema classes. Follow existing FastAPI and SQLAlchemy patterns.

Frontend code uses ES modules, React function components, Tailwind utilities, and shadcn-style primitives. Name components in `PascalCase`, helper files in `camelCase.js`, and keep API access in `frontend/src/api/`.

## Testing Guidelines

No full automated test suite is currently established. Add backend tests under `backend/tests/` with names like `test_repository.py` or `test_seller_api.py`, then run `uv run pytest`. For frontend changes, run `npm run lint` and `npm run build`; add component tests when introducing test tooling.

## Commit & Pull Request Guidelines

Recent commits use short, imperative subjects such as `Implement on-chain Arc agent commerce MVP` and `Update UI`. Pull requests should include a summary, linked issue or context, migration/env changes, commands run, and screenshots or API examples for user-facing changes.

## Security & Configuration Tips

Do not commit `.env`, private keys, wallet secrets, or generated local databases. Use `backend/.env.example` and `test/buyer_agent/.env.example` as templates. The backend references a local `circle-titanoboa-sdk` path in `backend/pyproject.toml`; avoid hardcoding machine-specific paths elsewhere.
