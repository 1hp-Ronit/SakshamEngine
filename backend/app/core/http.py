"""Shared httpx client. Overridable so tests can route "HTTP" calls to the in-process ASGI app."""
from __future__ import annotations

import httpx

from app.core.config import get_settings

_client: httpx.AsyncClient | None = None
_override: httpx.AsyncClient | None = None


def http_client() -> httpx.AsyncClient:
    global _client
    if _override is not None:
        return _override
    if _client is None:
        # keep-alive off: these are calls to ourselves, and a stale pooled connection must never be able to stall a source fetch
        _client = httpx.AsyncClient(base_url=get_settings().env.mock_services_base_url, timeout=10.0, limits=httpx.Limits(max_keepalive_connections=0))
    return _client


def override_http_client(client: httpx.AsyncClient | None) -> None:
    global _override
    _override = client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
