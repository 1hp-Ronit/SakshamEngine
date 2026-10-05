from __future__ import annotations

import uuid
from typing import Any

from app.adapters.interfaces import MessagingProvider, SendResult, WebhookEvent


class SimulatedProvider(MessagingProvider):
    """Succeeds instantly. The outbox row (written by the manager) IS the delivery — the dashboard's message log shows it."""

    name = "simulated"

    async def send_template(self, to: str, template_name: str, language: str, params: list[str] | None = None) -> SendResult:
        return SendResult(True, "sim-" + uuid.uuid4().hex[:12])

    async def send_text(self, to: str, body: str) -> SendResult:
        return SendResult(True, "sim-" + uuid.uuid4().hex[:12])

    def parse_webhook(self, payload: dict[str, Any]) -> list[WebhookEvent]:
        return []
