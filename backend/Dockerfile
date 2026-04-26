FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

# Install project metadata first for better layer caching.
COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

# Create environment and install locked dependencies.
RUN uv sync --frozen --no-dev

ENV PORT=4021
EXPOSE 4021

# Apply schema migrations at startup, then run API.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run arc-seller"]
