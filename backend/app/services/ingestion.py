"""Parallel, consent-gated, timeout-bounded ingestion from all source groups. Never raises."""
from __future__ import annotations

import asyncio
from typing import Any

from app.adapters.interfaces import SourceResult
from app.adapters.registry import get_data_sources
from app.models import ConsentArtifact


async def ingest_all_sources(mobile_hash: str, consent: ConsentArtifact, outages: set[str] | None = None) -> list[SourceResult]:
    """One adapter call per consented group, all in parallel (asyncio.gather). Groups without consent are NOT called."""
    outages = outages or set()
    adapters = get_data_sources()

    async def one(name: str) -> SourceResult:
        if not getattr(consent, f"grant_{name}", False):
            return SourceResult(name, "not_consented", None, 0, "Customer did not grant this source")
        return await adapters[name].fetch(mobile_hash, consent.id, simulate_outage=name in outages)

    return list(await asyncio.gather(*(one(n) for n in adapters)))


def to_raw_payloads(results: list[SourceResult]) -> dict[str, Any]:
    """SourceResults → the dict `build_features` expects."""
    return {r.source: (r.payload if r.usable else None) for r in results}


def usable_groups(results: list[SourceResult]) -> int:
    return sum(1 for r in results if r.usable)
