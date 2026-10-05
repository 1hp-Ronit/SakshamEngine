"""Deterministic fallback: no network, no key. The advisory service renders templates itself when the LLM is unavailable."""
from __future__ import annotations

from app.adapters.interfaces import LLMClient


class DeterministicFallbackClient(LLMClient):
    name = "deterministic"

    @property
    def available(self) -> bool:
        return False  # tells the advisory service to use its template renderer

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("DeterministicFallbackClient does not call a model")
