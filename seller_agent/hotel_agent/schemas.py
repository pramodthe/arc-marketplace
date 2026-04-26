from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InvokeBody(BaseModel):
    prompt: str
    buyerId: int | None = None
    selectedSkills: list[str] = Field(default_factory=list)
    billing: dict[str, Any] | None = None
