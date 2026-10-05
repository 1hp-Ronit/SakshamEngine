"""Resolve a mobile hash → deterministic data profile / bureau response (personas.yaml, else derived from the hash)."""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.security import vendor_ref
from app.mock_services import generators as g


def persona_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in get_settings().personas:
        out.setdefault(vendor_ref(p["mobile_number"]), p)  # persona 7 shares persona 1's number → first wins
    return out


def resolve_profile(mob_hash: str) -> g.Profile:
    seed = g.seed_from_hash(mob_hash)
    persona = persona_map().get(mob_hash)
    if persona:
        prof = persona.get("profile", {})
        base = g.build_profile(seed, prof.get("segment"), prof.get("creditworthiness"), prof.get("monthly_income"))
        # Personas are demo fixtures: availability is pinned (not randomly drawn) unless personas.yaml overrides it.
        seg = base.segment
        return g.with_availability(
            base,
            has_aa=prof.get("has_aa", True),
            has_telecom=prof.get("has_telecom", True),
            has_gst=prof.get("has_gst", seg == "merchant"),
            has_mandi=prof.get("has_mandi", seg == "farmer"),
            aa_sparsity=prof.get("aa_sparsity", 0.4 if seg == "farmer" else 1.0),
        )
    return g.build_profile(seed)


def resolve_bureau(mob_hash: str) -> dict[str, Any]:
    persona = persona_map().get(mob_hash)
    if persona and "bureau" in persona:
        b = persona["bureau"]
        return {"status": b["status"], "score": int(b["score"])}
    return g.generate_bureau_result(g.seed_from_hash(mob_hash))
