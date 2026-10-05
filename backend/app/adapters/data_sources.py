"""Data-source adapters. Each fetch NEVER raises: failures become a typed SourceResult (graceful degradation)."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.adapters.interfaces import DataSourceAdapter, SourceResult
from app.core.config import get_settings
from app.core.http import http_client
from app.core.logging import get_logger
from app.core.security import mask_secrets

log = get_logger("sources")

_ERROR_STATUS = {
    "NO_DATA": "no_data",
    "CONSENT_REQUIRED": "not_consented", "CONSENT_REVOKED": "not_consented", "CONSENT_EXPIRED": "not_consented",
    "CONSENT_SCOPE": "not_consented", "CONSENT_INVALID": "not_consented", "CONSENT_MISMATCH": "not_consented",
}


async def _get(path: str, mobile_hash: str, consent_id: str, simulate_outage: bool) -> tuple[str, dict[str, Any] | None, str | None]:
    """→ (status, payload, detail). Applies the per-source timeout from policy."""
    timeout = get_settings().policy.ingestion.per_source_timeout_seconds
    params: dict[str, Any] = {"mobile_hash": mobile_hash}
    if simulate_outage:
        params["simulate_outage"] = "true"
    try:
        resp = await asyncio.wait_for(
            http_client().get(path, params=params, headers={"X-Consent-Token": consent_id}, timeout=timeout), timeout=timeout
        )
    except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
        base = str(http_client().base_url).rstrip("/")
        log.warning("source %s timed out after %gs (%s, base %s)", path, timeout, type(exc).__name__, base)
        return "timeout", None, f"No response within {timeout:g}s ({type(exc).__name__})"
    except Exception as exc:  # noqa: BLE001 — degrade, never crash
        base = str(http_client().base_url).rstrip("/")
        log.warning("source %s call failed: %s (base %s)", path, mask_secrets(f"{type(exc).__name__}: {exc}"), base)
        return "error", None, f"{type(exc).__name__} calling {base}{path}"
    if resp.status_code == 200:
        return "ok", resp.json(), None
    code = ""
    try:
        code = resp.json().get("error", {}).get("code", "")
    except Exception:  # noqa: BLE001
        pass
    return _ERROR_STATUS.get(code, "error"), None, code or f"HTTP {resp.status_code}"


class _SimpleSource(DataSourceAdapter):
    path: str

    async def fetch(self, mobile_hash: str, consent_id: str, simulate_outage: bool = False) -> SourceResult:
        t0 = time.perf_counter()
        status, payload, detail = await _get(self.path, mobile_hash, consent_id, simulate_outage)
        return SourceResult(self.name, status, payload, int((time.perf_counter() - t0) * 1000), detail)


class MockAAAdapter(_SimpleSource):
    name = "aa"
    path = "/mock/aa/bank-statement"


class MockTelecomAdapter(_SimpleSource):
    name = "telecom"
    path = "/mock/telecom/recharge"


class MockBusinessAdapter(DataSourceAdapter):
    """The `business` consent group maps to whichever record feed applies (GST for merchants, mandi for farmers).
    An applicant may have neither — that is the data-gap case (status no_data)."""

    name = "business"

    async def fetch(self, mobile_hash: str, consent_id: str, simulate_outage: bool = False) -> SourceResult:
        t0 = time.perf_counter()
        (gs, gp, gd), (ms, mp, md) = await asyncio.gather(
            _get("/mock/business/gst-returns", mobile_hash, consent_id, simulate_outage),
            _get("/mock/business/mandi-receipts", mobile_hash, consent_id, simulate_outage),
        )
        latency = int((time.perf_counter() - t0) * 1000)
        if gs == "ok" or ms == "ok":
            return SourceResult(self.name, "ok", {"gst": gp if gs == "ok" else None, "mandi": mp if ms == "ok" else None}, latency)
        # Prefer the most informative failure
        for status, detail in ((gs, gd), (ms, md)):
            if status in ("timeout", "not_consented", "error"):
                return SourceResult(self.name, status, None, latency, detail)
        return SourceResult(self.name, "no_data", None, latency, "No GST or mandi records")
