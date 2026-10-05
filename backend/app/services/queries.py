"""Read-side views for the API (application state, pipeline trace, decision, plan)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.core.timeutil import iso, utcnow
from app.domain.state_machine import DECISIONS, TERMINAL, ApplicationStatus
from app.models import Application, AuditRecord, ConsentArtifact, ConsentLog, DataAccessLog, Loan, Message, TimelineEvent, Withdrawal
from app.services import consent as consent_service
from app.services import ladder
from app.domain.reason_codes import get_catalog
from app.services.advisory import get_advisory
from app.services.notifications import first_name

STATE_PREFIX = "STATE_"


def _loads(s: str | None, default: Any = None) -> Any:
    try:
        return json.loads(s) if s else default
    except Exception:  # noqa: BLE001
        return default


def _withdrawal(w: Withdrawal) -> dict[str, Any]:
    return {"reason": w.reason, "withdrawn_at": iso(w.withdrawn_at)}


def _event(e: TimelineEvent) -> dict[str, Any]:
    return {"stage": e.stage, "status": e.status, "latency_ms": e.latency_ms, "timestamp": iso(e.timestamp), "details": _loads(e.details)}


def mask_mobile(m: str) -> str:
    return f"{m[:2]}{'•' * 6}{m[-2:]}" if len(m) >= 4 else m


async def _messages(db: AsyncSession, app_id: str) -> list[Message]:
    res = await db.execute(select(Message).where(Message.application_id == app_id).order_by(Message.created_at, Message.id))
    return list(res.scalars())


def display_status(m: Message) -> str:
    """Simulated messages progress sent → delivered → read over a few seconds so simulated-mode demos still show delivery progress."""
    if m.provider != "simulated" or m.direction != "OUTBOUND" or m.delivery_status in ("failed_real_send", "failed"):
        return m.delivery_status
    age = (utcnow() - m.created_at).total_seconds()
    return "sent" if age < 0.8 else "delivered" if age < 3.5 else "read"


def message_view(m: Message) -> dict[str, Any]:
    return {
        "id": m.id, "application_id": m.application_id, "direction": m.direction, "purpose": m.purpose, "provider": m.provider, "message_type": m.message_type, "template_name": m.template_name,
        "recipient": mask_mobile(m.recipient), "body": m.body, "link_url": m.link_url, "delivery_status": display_status(m), "stored_status": m.delivery_status,
        "error": m.error, "created_at": iso(m.created_at), "whatsapp_message_id": bool(m.whatsapp_message_id),
    }


async def application_view(db: AsyncSession, app: Application) -> dict[str, Any]:
    events = (await db.execute(select(TimelineEvent).where(TimelineEvent.application_id == app.id).order_by(TimelineEvent.id))).scalars().all()
    art = await consent_service.latest_artifact_for_application(db, app.id)
    loan = (await db.execute(select(Loan).where(Loan.application_id == app.id))).scalars().first()
    status = ApplicationStatus(app.status)
    return {
        "application_id": app.id, "status": app.status, "outcome": app.outcome, "terminal": status in TERMINAL,
        "applicant_name": app.applicant_name, "mobile_masked": mask_mobile(app.mobile_number), "language": app.preferred_language,
        "product_sku": app.requested_product_sku, "product_label": get_settings().policy.products[app.requested_product_sku].label,
        "requested_emi": app.requested_emi, "ticket_size": app.ticket_size, "suggested_ticket": app.suggested_ticket,
        "tenure_months": get_settings().policy.products[app.requested_product_sku].tenure_months,
        "bureau": {"status": app.bureau_status, "score": app.bureau_score}, "session_id": app.session_id, "consent_url": app.consent_url,
        "consent": consent_service.artifact_view(art) if art else None, "score": app.score, "pd": app.pd, "persona_name": app.persona_name,
        "withdrawal": _withdrawal(w) if (w := (await db.execute(select(Withdrawal).where(Withdrawal.application_id == app.id))).scalars().first()) else None,
        "has_plan": bool(app.plan_json), "simulated_outage": _loads(app.demo_options_json, {}).get("simulate_outage", []), "loan": ladder.ladder_view(loan) if loan else None,
        "created_at": iso(app.created_at), "updated_at": iso(app.updated_at),
        "timeline": [_event(e) for e in events if not e.stage.startswith(STATE_PREFIX)],
        "transitions": [{"status": e.stage[len(STATE_PREFIX):], "timestamp": iso(e.timestamp), "from": (_loads(e.details) or {}).get("from")} for e in events if e.stage.startswith(STATE_PREFIX)],
    }


async def trace_view(db: AsyncSession, app: Application) -> dict[str, Any]:
    events = (await db.execute(select(TimelineEvent).where(TimelineEvent.application_id == app.id).order_by(TimelineEvent.id))).scalars().all()
    stages = [_event(e) for e in events if not e.stage.startswith(STATE_PREFIX)]
    by_stage = {e.stage: e for e in events}
    total = None
    start, end = by_stage.get("CONSENT_GRANTED"), by_stage.get("DECISION")
    if start and end:
        total = int((end.timestamp - start.timestamp).total_seconds() * 1000)
    msgs = [m for m in await _messages(db, app.id) if m.direction == "OUTBOUND"]
    delivery = {}
    for m in msgs:
        delivery["consent_request" if m.purpose == "consent_request" else "result_delivery"] = display_status(m)
    source_stages = {"AA_INGESTION": "aa", "TELECOM_INGESTION": "telecom", "BUSINESS_INGESTION": "business"}
    sources = {source_stages[e.stage]: {"status": e.status, "latency_ms": e.latency_ms, "detail": (_loads(e.details) or {}).get("detail")} for e in events if e.stage in source_stages}
    return {
        "application_id": app.id, "status": app.status, "stages": stages, "total_latency_ms": total, "sources": sources, "message_delivery": delivery,
        "transitions": [{"status": e.stage[len(STATE_PREFIX):], "timestamp": iso(e.timestamp)} for e in events if e.stage.startswith(STATE_PREFIX)],
    }


async def decision_view(db: AsyncSession, app: Application) -> dict[str, Any]:
    if ApplicationStatus(app.status) not in DECISIONS:
        raise AppError("DECISION_NOT_READY", f"No decision yet (status: {app.status}).", 409)
    audit = (await db.execute(select(AuditRecord).where(AuditRecord.application_id == app.id))).scalars().first()
    if audit is None:
        raise NotFound("Audit record not found")
    wf = _loads(audit.waterfall_json, {}) or {}
    # Affordability signals from the stored feature vector (None once consent is revoked and the vector is purged)
    fv = _loads(app.feature_vector_json, None) or {}
    afford = {k: fv[k] for k in ("est_monthly_income", "emi_to_income_ratio", "buffer_ratio", "bounce_velocity") if fv.get(k) is not None} or None
    return {
        "affordability": afford,
        "application_id": app.id, "score": audit.final_score, "pd": audit.calibrated_pd, "outcome": audit.outcome, "suggested_ticket": app.suggested_ticket,
        "approve_cutoff": get_settings().policy.decision.approve_cutoff,
        "shap_drivers": {"positive": _loads(audit.shap_top_positive, []), "negative": _loads(audit.shap_top_negative, [])},
        "waterfall": wf.get("items", []), "base_score": wf.get("base_score"),
        "audit_record_id": audit.id, "model_version": audit.model_version, "policy_version": audit.policy_version, "consent_id": audit.consent_id,
        "feature_vector_hash": audit.feature_vector_hash, "decided_at": iso(audit.created_at),
    }


async def plan_view(db: AsyncSession, app: Application, lang: str | None) -> dict[str, Any]:
    audit = (await db.execute(select(AuditRecord).where(AuditRecord.application_id == app.id))).scalars().first()
    if audit is None or app.outcome != "DECLINED_WITH_PLAN":
        raise AppError("NO_PLAN", "There is no action plan for this application.", 404)
    lang = lang if lang in get_settings().policy.languages.supported else app.preferred_language
    plan = await get_advisory().generate_plan(_loads(audit.shap_top_negative, []), lang, app.requested_product_sku, first_name(app))
    return {
        "application_id": app.id, "language": lang, "available_languages": get_settings().policy.languages.supported,
        "product_label": get_catalog().product_label(app.requested_product_sku, lang), "applicant_first_name": first_name(app), **plan.as_dict(),
    }


async def messages_view(db: AsyncSession, app_id: str) -> list[dict[str, Any]]:
    return [message_view(m) for m in await _messages(db, app_id)]


async def latest_consent(db: AsyncSession, app_id: str) -> ConsentArtifact | None:
    return await consent_service.latest_artifact_for_application(db, app_id)


async def ledger_view(db: AsyncSession, app: Application) -> dict[str, Any]:
    """Consent & data-rights ledger: every consent grant/revocation, every attempted data read, and what we still hold."""
    arts = (await db.execute(select(ConsentArtifact).where(ConsentArtifact.application_id == app.id).order_by(ConsentArtifact.granted_at))).scalars().all()
    events = (await db.execute(select(ConsentLog).where(ConsentLog.application_id == app.id).order_by(ConsentLog.timestamp, ConsentLog.id))).scalars().all()
    reads = (await db.execute(select(DataAccessLog).where(DataAccessLog.application_id == app.id).order_by(DataAccessLog.id))).scalars().all()
    audit = (await db.execute(select(AuditRecord).where(AuditRecord.application_id == app.id))).scalars().first()
    now = utcnow()
    return {
        "application_id": app.id,
        "applicant_name": app.applicant_name,
        "mobile_masked": mask_mobile(app.mobile_number),
        "consents": [{
            "consent_id": a.id, "grants": {"aa": a.grant_aa, "telecom": a.grant_telecom, "business": a.grant_business},
            "purpose": a.purpose, "granted_at": iso(a.granted_at), "expires_at": iso(a.expires_at),
            "revoked": a.revoked, "revoked_at": iso(a.revoked_at), "active": (not a.revoked) and a.expires_at > now,
        } for a in arts],
        "events": [{"event": e.event, "timestamp": iso(e.timestamp), "consent_id": e.consent_id, "details": _loads(e.details)} for e in events],
        "data_access": [{"source": r.source, "status": r.status, "accessed_at": iso(r.accessed_at), "latency_ms": r.latency_ms,
                         "consent_id": r.consent_id, "detail": r.detail} for r in reads],
        "holdings": {
            "mobile_number": "stored in clear — the messaging channel needs it",
            "identifiers": "PAN and Aadhaar stored only as keyed HMAC tokens",
            "raw_vendor_payloads": "never stored — discarded after feature extraction",
            "feature_vector": "stored" if app.feature_vector_json else ("purged on consent revocation" if arts and any(a.revoked for a in arts) else "not stored"),
            "feature_vector_hash": app.feature_vector_hash,
            "audit_record": audit.id if audit else None,
        },
    }


async def approved_loans_view(db: AsyncSession, outcome: str = "APPROVED", limit: int = 100) -> dict[str, Any]:
    """Applications with the given final outcome, newest decision first, with their LOS reference and loan state."""
    withdrawn_ids = select(Withdrawal.application_id)
    apps = (await db.execute(select(Application).where(Application.outcome == outcome, Application.id.not_in(withdrawn_ids))
                             .order_by(Application.updated_at.desc()).limit(limit))).scalars().all()
    rows = []
    for app in apps:
        audit = (await db.execute(select(AuditRecord).where(AuditRecord.application_id == app.id))).scalars().first()
        loan = (await db.execute(select(Loan).where(Loan.application_id == app.id))).scalars().first()
        los = (await db.execute(select(TimelineEvent).where(TimelineEvent.application_id == app.id, TimelineEvent.stage == "LOS_HANDOFF"))).scalars().first()
        art = await consent_service.latest_artifact_for_application(db, app.id)
        rows.append({
            "application_id": app.id, "applicant_name": app.applicant_name, "mobile_masked": mask_mobile(app.mobile_number),
            "product_label": get_settings().policy.products[app.requested_product_sku].label, "ticket_size": app.ticket_size,
            "requested_emi": app.requested_emi, "tenure_months": get_settings().policy.products[app.requested_product_sku].tenure_months,
            "score": app.score, "pd": app.pd, "outcome": app.outcome, "decided_at": iso(audit.created_at) if audit else None,
            "los_reference": (_loads(los.details, {}) or {}).get("reference") if los else None,
            "consent_active": bool(art and not art.revoked and art.expires_at > utcnow()),
            "loan": ladder.ladder_view(loan) if loan else None,
        })
    return {"outcome": outcome, "count": len(rows), "loans": rows}
