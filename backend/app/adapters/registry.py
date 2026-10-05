"""Wiring: which concrete adapter backs each port. Swap an implementation here (or override in tests); nothing else changes."""
from __future__ import annotations

from app.adapters.bureau import MockBureauAdapter
from app.adapters.data_sources import MockAAAdapter, MockBusinessAdapter, MockTelecomAdapter
from app.adapters.interfaces import BureauAdapter, DataSourceAdapter, LMSAdapter, LOSAdapter
from app.adapters.los import MockLMSAdapter, MockLOSAdapter

_bureau: BureauAdapter | None = None
_sources: dict[str, DataSourceAdapter] | None = None
_los: LOSAdapter | None = None
_lms: LMSAdapter | None = None


def get_bureau() -> BureauAdapter:
    global _bureau
    if _bureau is None:
        _bureau = MockBureauAdapter()
    return _bureau


def get_data_sources() -> dict[str, DataSourceAdapter]:
    global _sources
    if _sources is None:
        _sources = {"aa": MockAAAdapter(), "telecom": MockTelecomAdapter(), "business": MockBusinessAdapter()}
    return _sources


def get_los() -> LOSAdapter:
    global _los
    if _los is None:
        _los = MockLOSAdapter()
    return _los


def get_lms() -> LMSAdapter:
    global _lms
    if _lms is None:
        _lms = MockLMSAdapter()
    return _lms


def override(*, bureau: BureauAdapter | None = None, sources: dict[str, DataSourceAdapter] | None = None) -> None:
    global _bureau, _sources
    if bureau is not None:
        _bureau = bureau
    if sources is not None:
        _sources = sources
