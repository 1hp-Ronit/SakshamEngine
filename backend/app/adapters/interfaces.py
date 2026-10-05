"""Ports. The core never talks to a vendor directly — swap an adapter and nothing else changes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ───────────── Bureau ─────────────
@dataclass
class BureauResult:
    status: str  # HIT | NO_HIT
    score: int  # -1 for NO_HIT
    latency_ms: int = 0


class BureauAdapter(ABC):
    @abstractmethod
    async def check(self, mobile_hash: str, pan_hash: str) -> BureauResult: ...


# ───────────── Data sources ─────────────
@dataclass
class SourceResult:
    source: str  # aa | telecom | business
    status: str  # ok | timeout | error | not_consented | no_data
    payload: dict[str, Any] | None = None
    latency_ms: int = 0
    detail: str | None = None

    @property
    def usable(self) -> bool:
        return self.status == "ok" and bool(self.payload)


class DataSourceAdapter(ABC):
    name: str  # aa | telecom | business  (also the consent group it needs)

    @abstractmethod
    async def fetch(self, mobile_hash: str, consent_id: str, simulate_outage: bool = False) -> SourceResult: ...


# ───────────── LOS / LMS ─────────────
@dataclass
class LOSHandoff:
    reference: str
    detail: str


class LOSAdapter(ABC):
    @abstractmethod
    async def handoff(self, application_id: str, summary: dict[str, Any]) -> LOSHandoff: ...


class LMSAdapter(ABC):
    @abstractmethod
    async def create_loan_account(self, application_id: str, product_sku: str, amount: float, emi: float, tenure_months: int) -> dict[str, Any]: ...

    @abstractmethod
    async def record_repayment(self, loan_id: str, status: str) -> dict[str, Any]: ...


# ───────────── Messaging ─────────────
@dataclass
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None


@dataclass
class WebhookEvent:
    kind: str  # inbound | status
    sender: str | None = None
    text: str | None = None
    message_id: str | None = None
    status: str | None = None  # sent | delivered | read | failed
    recipient: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class MessagingProvider(ABC):
    name: str

    @abstractmethod
    async def send_template(self, to: str, template_name: str, language: str, params: list[str] | None = None) -> SendResult: ...

    @abstractmethod
    async def send_text(self, to: str, body: str) -> SendResult: ...

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any]) -> list[WebhookEvent]: ...


# ───────────── LLM ─────────────
class LLMClient(ABC):
    name: str

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw model text (expected to be JSON). Raise on error/timeout."""
