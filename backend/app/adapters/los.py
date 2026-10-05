"""Mock LOS (loan origination) + LMS (loan management) — in-process adapters behind the real ports."""
from __future__ import annotations

import uuid
from typing import Any

from app.adapters.interfaces import LMSAdapter, LOSAdapter, LOSHandoff
from app.core.database import session_factory
from app.models import Application
from app.services import ladder


class MockLOSAdapter(LOSAdapter):
    async def handoff(self, application_id: str, summary: dict[str, Any]) -> LOSHandoff:
        ref = "LOS-" + uuid.uuid4().hex[:8].upper()
        extra = " · e-NACH mandate registered (mock)" if summary.get("route") == "saksham_approved" else ""
        return LOSHandoff(ref, f"Handed to TVS LOS ({summary.get('route', 'standard')}){extra}")


class MockLMSAdapter(LMSAdapter):
    async def create_loan_account(self, application_id: str, product_sku: str, amount: float, emi: float, tenure_months: int) -> dict[str, Any]:
        async with session_factory()() as db:
            app = await db.get(Application, application_id)
            loan = await ladder.create_loan(db, app, amount, emi, tenure_months)
            await db.commit()
            return {"loan_id": loan.id, "customer_id": loan.customer_id, "tier": loan.current_tier, "behaviour_score": loan.behaviour_score}

    async def record_repayment(self, loan_id: str, status: str) -> dict[str, Any]:
        async with session_factory()() as db:
            return await ladder.record_event(db, loan_id, status)
