"""Load `.env` from the backend project root (parent of `src/`)."""

from pathlib import Path

from dotenv import load_dotenv


def load_backend_env() -> None:
    """Load env from `backend/.env`, fallback to default dotenv behavior."""
    backend_root = Path(__file__).resolve().parents[2]
    main_env = backend_root / ".env"
    if main_env.is_file():
        load_dotenv(main_env)
        return
    if not main_env.is_file():
        load_dotenv()
