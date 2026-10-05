"""Demo helpers: reset, personas, public (secret-free) config, bulk repayment simulation."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.messaging.manager import get_messaging, reset_messaging
from app.api.schemas import SimulateRepaymentsRequest
from app.core import database
from app.core.config import get_settings
from app.core.database import get_session
from app.services import ladder, orchestrator
from app.services.advisory import get_advisory, reset_advisory
from app.services.scoring import get_scoring_service

router = APIRouter(prefix="/demo", tags=["demo"])


async def _recent_inbound() -> list[dict]:
    """Inbound WhatsApp messages inside the 24h service window. They record a fact about the real world (the recipient messaged us),
    not demo state — wiping them would make us think the window is closed and downgrade real sends to templates."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.timeutil import utcnow
    from app.models import Message

    hours = get_settings().policy.messaging.whatsapp_window_hours
    async with database.session_factory()() as db:
        rows = (await db.execute(select(Message).where(Message.direction == "INBOUND", Message.created_at >= utcnow() - timedelta(hours=hours)))).scalars().all()
        return [{"recipient": m.recipient, "body": m.body, "whatsapp_message_id": m.whatsapp_message_id, "created_at": m.created_at} for m in rows]


async def _restore_inbound(rows: list[dict]) -> None:
    from app.models import Message

    if not rows:
        return
    async with database.session_factory()() as db:
        for r in rows:
            db.add(Message(application_id=None, direction="INBOUND", purpose="inbound", provider="whatsapp", message_type="text", delivery_status="delivered", **r))
        await db.commit()


@router.post("/reset")
async def reset():
    """Wipe demo state and clear caches (recent inbound WhatsApp messages are kept — see _recent_inbound). Personas live in personas.yaml."""
    await orchestrator.drain()
    keep = await _recent_inbound()
    await database.drop_and_create_all()
    await _restore_inbound(keep)
    reset_advisory()
    reset_messaging()
    return {"ok": True, "personas": len(get_settings().personas)}


@router.get("/personas")
async def personas():
    s = get_settings()
    return {"personas": [{**p, "product_label": s.policy.products[p["product_sku"]].label, "emi": s.policy.products[p["product_sku"]].monthly_emi,
                          "ticket": s.policy.products[p["product_sku"]].ticket} for p in s.personas]}


@router.get("/config")
async def public_config():
    """What the UI needs to know about the running system. Never includes secrets."""
    s = get_settings()
    env = s.env
    m = get_messaging()
    try:
        svc = get_scoring_service()
        model = {"loaded": True, "version": svc.model_version, "metrics": svc.schema.get("metrics")}
    except Exception:  # noqa: BLE001
        model = {"loaded": False, "version": None, "metrics": None}
    return {
        "dealer": env.demo_dealer_name, "public_base_url": env.public_base_url,
        "messaging": {"mode": env.messaging_mode, "whatsapp_configured": m.whatsapp.configured, "real_sends_enabled": m.real_enabled, "demo_recipient_set": bool(env.demo_recipient_number)},
        "llm": {"provider": "gemini", "available": get_advisory().llm.available, "model": env.llm_model, "fallback_only": env.llm_fallback_only},
        "model": model, "policy": {"version": s.policy.policy_version, "approve_cutoff": s.policy.decision.approve_cutoff, "borderline_floor": s.policy.decision.borderline_floor if s.policy.decision.borderline_enabled else None,
                                   "bureau_bypass_threshold": s.policy.bureau.bypass_threshold, "comfortable_emi_ratio": s.policy.decision.comfortable_emi_ratio, "session_ttl_minutes": s.policy.session.ttl_minutes},
        "products": {k: {"label": v.label, "ticket": v.ticket, "emi": v.monthly_emi, "tenure_months": v.tenure_months} for k, v in s.policy.products.items()},
        "languages": s.policy.languages.supported, "withdrawal_reasons": s.policy.withdrawal.reasons,
    }


@router.post("/simulate-repayments")
async def simulate_repayments(body: SimulateRepaymentsRequest, db: AsyncSession = Depends(get_session)):
    last = {}
    steps = []
    for _ in range(body.count):
        last = await ladder.record_event(db, body.loan_id, body.status)
        steps.append({"behaviour_score": last["behaviour_score"], "tier": last["current_tier"]})
    return {**last, "steps": steps}
