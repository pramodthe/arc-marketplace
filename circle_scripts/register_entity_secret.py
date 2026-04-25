#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Dict

from circle.web3 import utils


def load_env_file(env_path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not env_path.exists():
        return env

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_file = Path(
        os.getenv("ENV_FILE", str(repo_root / "circle-nanopayment-sample" / ".env"))
    )
    file_env = load_env_file(env_file)

    api_key = os.getenv("CIRCLE_API_KEY") or file_env.get("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET") or file_env.get("CIRCLE_ENTITY_SECRET")

    if not api_key:
        print(f"CIRCLE_API_KEY is missing in {env_file}.", file=sys.stderr)
        sys.exit(1)

    generated_new_secret = False
    if not entity_secret:
        generated = StringIO()
        with redirect_stdout(generated):
            returned_value = utils.generate_entity_secret()

        if isinstance(returned_value, str) and returned_value:
            entity_secret = returned_value
        else:
            output = generated.getvalue()
            match = re.search(r"ENTITY SECRET:\s*([0-9a-fA-F]{64})", output)
            if not match:
                print("Failed to generate Entity Secret with Circle SDK.", file=sys.stderr)
                sys.exit(1)
            entity_secret = match.group(1)

        generated_new_secret = True

    recovery_dir = env_file.parent / ".circle-recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)

    response = utils.register_entity_secret_ciphertext(
        api_key=api_key,
        entity_secret=entity_secret,
        recoveryFileDownloadPath=str(recovery_dir),
    )

    print("Entity Secret registration complete.")
    print(f"Env file: {env_file}")
    if generated_new_secret:
        print("\nAdd this to your .env (keep it secure):")
        print(f"CIRCLE_ENTITY_SECRET={entity_secret}")
    else:
        print("Used existing CIRCLE_ENTITY_SECRET from environment.")
    print(f"Recovery file directory: {recovery_dir}")
    print(f"Response: {response}")


if __name__ == "__main__":
    main()
