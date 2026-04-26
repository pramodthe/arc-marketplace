"""ADK loads this file as the top-level `agent` module; expose `agent` submodule with `root_agent`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parent / "agent.py"
_spec = importlib.util.spec_from_file_location("qa_buyer_adk_agent_impl", _p)
_agent_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_agent_mod)
agent = _agent_mod
