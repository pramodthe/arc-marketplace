# Repository Guidelines

## Project Structure & Module Organization

This backend is a Python 3.12 service managed with `uv`. Application code lives under `src/agents_market/`. Key areas:

- `src/agents_market/arc/seller/`: FastAPI seller API and entrypoint.
- `src/agents_market/arc/buyer/`: buyer-side runner for paid tool execution.
- `src/agents_market/arc/cli/`: operational CLIs such as `deposit.py`, `client.py`, and demo seed scripts.
- `src/agents_market/arc/services/`: reusable Arc and ERC-8004 integrations.
- `src/agents_market/marketplace/`: SQLAlchemy models and repository helpers.
- `alembic/versions/`: schema migrations.

Keep new modules inside the existing domain package they extend. Put database schema changes in Alembic, not inline startup code.

## Build, Test, and Development Commands

- `uv sync`: install project dependencies from `pyproject.toml` and `uv.lock`.
- `cp .env.example .env`: create local configuration before running the app.
- `uv run arc-seller`: start the FastAPI marketplace API on `http://localhost:4021`.
- `uv run arc-buyer`: run the buyer demo flow against the marketplace.
- `uv run arc-demo-marketplace`: seed or verify demo sellers, agents, and tools.
- `uv run alembic upgrade head`: apply all database migrations.
- `uv run alembic revision --autogenerate -m "add foo"`: generate a migration after model changes.

## Coding Style & Naming Conventions

Follow the existing code style: 4-space indentation, type hints, `from __future__ import annotations`, and short module docstrings. Use `snake_case` for functions, variables, and filenames, `PascalCase` for ORM models, and clear REST-oriented names for API handlers. Keep environment access centralized in `_env.py` or similar helpers.

## Testing Guidelines

A dedicated `tests/` tree is not present yet, but `pytest` is available in the lockfile. Add tests under `tests/` using names like `test_repository.py` or `test_seller_api.py`. Prefer focused unit tests for repository and service logic, plus API tests for critical endpoints. Run tests with `uv run pytest` once the suite is in place.

## Commit & Pull Request Guidelines

This branch does not have commit history yet, so no repository-specific convention is established. Use short, imperative commit subjects such as `Add bridge transfer repository methods`. For pull requests, include a concise summary, note any schema or env changes, list the commands you ran, and attach request/response examples for API-facing changes when relevant.

## Security & Configuration Tips

Do not commit `.env` or wallet secrets. `circle-titanoboa-sdk` is sourced from `../../circle-titanoboa-sdk`; update `[tool.uv.sources]` in `pyproject.toml` if your local path differs. Default local persistence uses `sqlite:///./agents_market.db`; treat production database and Circle credentials as required deployment configuration.
