"""Google Gemini via the REST API (httpx) — one small dependency, hard timeout, key sent in a header (never in the URL)."""
from __future__ import annotations

import httpx

from app.adapters.interfaces import LLMClient
from app.core.config import EnvSettings
from app.core.logging import get_logger
from app.core.security import mask_secrets

log = get_logger("gemini")


class GeminiLLMClient(LLMClient):
    name = "gemini"

    def __init__(self, env: EnvSettings, client: httpx.AsyncClient | None = None):
        self.env = env
        self._client = client
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.env.gemini_api_key) and not self.env.llm_fallback_only

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.env.llm_model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4, "maxOutputTokens": 2048},
        }
        timeout = self.env.llm_timeout_seconds
        client = self._client or httpx.AsyncClient()
        try:
            resp = await client.post(url, json=body, headers={"x-goog-api-key": self.env.gemini_api_key}, timeout=timeout)
            if resp.status_code != 200:
                try:
                    msg = resp.json().get("error", {}).get("message", "")
                except Exception:  # noqa: BLE001
                    msg = ""
                self.last_error = mask_secrets(f"HTTP {resp.status_code}: {msg}")
                raise RuntimeError(self.last_error)
            data = resp.json()
            self.last_error = None
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:  # noqa: BLE001
            self.last_error = self.last_error or mask_secrets(f"{type(exc).__name__}: {exc}")
            raise
        finally:
            if self._client is None:
                await client.aclose()
