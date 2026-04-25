"""Load env from backend/.env and supplement with the workspace root .env when present."""

from pathlib import Path
import os

from dotenv import dotenv_values, load_dotenv


def load_backend_env() -> None:
    """Load backend env first, then fill any missing values from the repo root `.env`."""
    backend_root = Path(__file__).resolve().parents[2]
    backend_env = backend_root / ".env"
    workspace_env = backend_root.parent / ".env"

    loaded_any = False
    if backend_env.is_file():
        load_dotenv(backend_env, override=False)
        loaded_any = True
    if workspace_env.is_file():
        load_dotenv(workspace_env, override=False)
        for key, value in dotenv_values(workspace_env).items():
            if value is not None and not os.getenv(key):
                os.environ[key] = value
        loaded_any = True
    if not loaded_any:
        load_dotenv()
