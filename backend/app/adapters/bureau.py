from __future__ import annotations

import time

from app.adapters.interfaces import BureauAdapter, BureauResult
from app.core.http import http_client


class MockBureauAdapter(BureauAdapter):
    """Calls the mock bureau over HTTP. A real bureau client would replace only this class."""

    async def check(self, mobile_hash: str, pan_hash: str) -> BureauResult:
        t0 = time.perf_counter()
        resp = await http_client().post("/mock/bureau/check", json={"mobile_hash": mobile_hash, "pan_hash": pan_hash}, timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
        return BureauResult(status=data["status"], score=int(data["score"]), latency_ms=int((time.perf_counter() - t0) * 1000))
