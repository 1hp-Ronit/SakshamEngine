"""Main flow: create → bureau → consent request → (consent) → ingest → features → score → decide → audit → notify.

Every step writes a timeline event (stage, status, latency) so the UI can render a live pipeline trace.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import timedelta
from typing import Any, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_bureau, get_lms, get_los
from app.core.config import get_settings
from app.core.database import session_factory
from app.core.errors import AppError, NotFound
from app.core.logging import get_logger
from app.core.security import mobile_hash, normalize_mobile, sha256_hex, tokenize_identifier, vendor_ref
from app.core.timeutil import utcnow
from app.domain.policy import evaluate_decision
from app.domain.reason_codes import get_catalog
from app.domain.state_machine import ApplicationStatus as S
from app.domain.state_machine import validate_transition
from app.models import Application, AuditRecord, ConsentArtifact, ConsentSession, DataAccessLog, TimelineEvent, Withdrawal
from app.services import consent as consent_service
from app.services import notifications
from app.services.advisory import get_advisory
from app.services.explainability import get_explainer
from app.services.feature_pipeline import build_features
from app.services.ingestion import ingest_all_sources, to_raw_payloads, usable_groups
from app.services.scoring import get_scoring_service

log = get_logger("orchestrator")

_tasks: set[asyncio.Task] = set()


def schedule(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """Run a coroutine in the background (no Celery: asyncio only)."""
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


async def drain() -> None:
    """Wait for all background pipelines (used by tests and /demo helpers)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


# ───────────── helpers ─────────────
def add_timeline(db: AsyncSession, app_id: str, stage: str, status: str = "ok", latency_ms: int | None = None, details: dict | None = None) -> None:
    db.add(TimelineEvent(application_id=app_id, stage=stage, status=status, latency_ms=latency_ms, details=json.dumps(details, default=str) if details else None))


def transition(db: AsyncSession, app: Application, dst: S, details: dict | None = None) -> None:
    dst = validate_transition(app.status, dst)
    prev = app.status
    app.status = dst.value
    if dst in (S.APPROVED, S.CONDITIONAL_APPROVAL, S.DECLINED_WITH_PLAN, S.INSUFFICIENT_DATA, S.CONSENT_DENIED, S.EXPIRED, S.BYPASSED_TO_LOS):
        app.outcome = dst.value
    add_timeline(db, app.id, f"STATE_{dst.value}", "ok", None, {"from": prev, **(details or {})})


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _clean_features(f) -> dict[str, float | None]:
    return {k: (None if math.isnan(v) else round(float(v), 6)) for k, v in f.items()}


def demo_outages(app: Application) -> set[str]:
    try:
        return set(json.loads(app.demo_options_json or "{}").get("simulate_outage", []))
    except Exception:  # noqa: BLE001
        return set()


# ───────────── 1. create application ─────────────
async def create_application(db: AsyncSession, req: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    sku = req["requested_product_sku"]
    if sku not in s.policy.products:
        raise AppError("INVALID_PRODUCT", f"Unknown product '{sku}'. Available: {', '.join(s.policy.products)}", 422)
    mobile = normalize_mobile(req["mobile_number"])
    if len(mobile) != 10:
        raise AppError("INVALID_MOBILE", "mobile_number must be a 10-digit Indian mobile number", 422)
    lang = req.get("preferred_language") or s.policy.languages.default
    if lang not in s.policy.languages.supported:
        raise AppError("INVALID_LANGUAGE", f"preferred_language must be one of {s.policy.languages.supported}", 422)

    product = s.policy.products[sku]
    mh = mobile_hash(mobile)
    app = Application(
        mobile_number=mobile, mobile_number_hash=mh, pan_token_hash=tokenize_identifier(req["pan_token"], "pan"),
        aadhaar_token_hash=tokenize_identifier(req["aadhaar_token"], "aadhaar"), applicant_name=req.get("applicant_name", "") or "",
        preferred_language=lang, requested_product_sku=sku, requested_emi=product.monthly_emi, ticket_size=product.ticket,
        persona_name=req.get("persona_name"), demo_options_json=json.dumps(req.get("demo_options") or {}),
    )
    db.add(app)
    await db.flush()
    add_timeline(db, app.id, "CREATED", "ok", 0, {"product": sku})

    # Bureau check (non-intrusive: Saksham only fires on NO_HIT)
    t0 = time.perf_counter()
    try:
        bureau = await get_bureau().check(vendor_ref(mobile), app.pan_token_hash)
        b_status, b_score, b_detail = bureau.status, bureau.score, {"result": bureau.status, "score": bureau.score}
        b_state = "ok"
    except Exception as exc:  # noqa: BLE001 — bureau outage → treat as thin file rather than blocking the customer
        log.warning("bureau check failed: %s", type(exc).__name__)
        b_status, b_score, b_detail, b_state = "NO_HIT", -1, {"result": "NO_HIT", "degraded": True, "error": type(exc).__name__}, "error"
    transition(db, app, S.BUREAU_CHECKED)
    app.bureau_status, app.bureau_score = b_status, b_score
    add_timeline(db, app.id, "BUREAU_CHECK", b_state, _ms(t0), b_detail)

    if b_status == "HIT":
        threshold = s.policy.bureau.bypass_threshold
        transition(db, app, S.BYPASSED_TO_LOS, {"reason": "bureau_score_sufficient" if b_score >= threshold else "bureau_hit_below_threshold_routed_unchanged"})
        t1 = time.perf_counter()
        ho = await get_los().handoff(app.id, {"route": "standard_bureau", "bureau_score": b_score})
        add_timeline(db, app.id, "LOS_HANDOFF", "ok", _ms(t1), {"reference": ho.reference, "detail": ho.detail})
        await db.commit()
        return {"application_id": app.id, "status": app.status, "bureau_result": "HIT", "bureau_score": b_score, "message": "Bureau score sufficient. Routed to standard LOS." if b_score >= threshold else "Bureau hit below threshold. Routed to standard LOS."}

    # NO_HIT → consent session + consent request message
    sess = ConsentSession(application_id=app.id, expires_at=utcnow() + timedelta(minutes=s.policy.session.ttl_minutes))
    db.add(sess)
    await db.flush()
    app.session_id = sess.id
    app.consent_url = f"{s.env.public_base_url.rstrip('/')}/consent/{sess.id}"
    t2 = time.perf_counter()
    msg = await notifications.send_consent_request(db, app, app.consent_url)
    add_timeline(db, app.id, "CONSENT_REQUEST_SENT", "ok" if msg.delivery_status != "failed_real_send" else "error", _ms(t2),
                 {"provider": msg.provider, "delivery_status": msg.delivery_status, "template": msg.template_name, **({"error": msg.error} if msg.error else {})})
    transition(db, app, S.AWAITING_CONSENT)
    await db.commit()
    via = "WhatsApp" if msg.provider == "whatsapp" else "the outbox only (simulated, not delivered to a phone)"
    return {
        "application_id": app.id, "status": app.status, "session_id": sess.id, "consent_url": app.consent_url, "bureau_result": "NO_HIT",
        "message": f"Consent request sent via {via}", "expires_at": sess.expires_at.isoformat() + "Z",
    }


# ───────────── 2. consent ─────────────
async def refresh_expiry(db: AsyncSession, app: Application) -> None:
    """TTL is enforced lazily on read: an open session past expires_at moves the application to EXPIRED."""
    if app.status != S.AWAITING_CONSENT.value or not app.session_id:
        return
    sess = await consent_service.get_open_session(db, app.session_id)
    if sess.status == "EXPIRED":
        transition(db, app, S.EXPIRED, {"reason": "consent session TTL elapsed"})
        add_timeline(db, app.id, "SESSION_EXPIRED", "ok", None, None)
        await db.commit()


async def _session_and_app(db: AsyncSession, session_id: str) -> tuple[ConsentSession, Application]:
    sess = await consent_service.get_open_session(db, session_id)
    app = await db.get(Application, sess.application_id)
    if app is None:
        raise NotFound("Application not found")
    await refresh_expiry(db, app)
    return sess, app


async def consent_session_view(db: AsyncSession, session_id: str) -> dict[str, Any]:
    sess, app = await _session_and_app(db, session_id)
    s = get_settings()
    from urllib.parse import quote

    prefill = f"{s.policy.messaging.consent_prefill_text} Ref {session_id[:8]}"
    wa = f"https://wa.me/{s.env.whatsapp_business_number}?text={quote(prefill)}" if s.env.whatsapp_business_number else None
    remaining = max(0, int((sess.expires_at - utcnow()).total_seconds()))
    return {
        "session_id": session_id, "application_id": app.id, "status": "EXPIRED" if sess.status == "EXPIRED" else sess.status,
        "applicant_name": app.applicant_name, "language": app.preferred_language, "product_sku": app.requested_product_sku,
        "product_label": s.policy.products[app.requested_product_sku].label,
        "product_labels": {l: get_catalog().product_label(app.requested_product_sku, l) for l in s.policy.languages.supported},
        "purpose": s.policy.consent.purpose_template.format(product=s.policy.products[app.requested_product_sku].label),
        "seconds_remaining": remaining, "expires_at": sess.expires_at.isoformat() + "Z", "groups": list(s.policy.consent.groups),
        "consent_valid_days": s.policy.consent.ttl_days, "whatsapp_link": wa,
    }


async def deny_consent(db: AsyncSession, session_id: str) -> dict[str, Any]:
    sess, app = await _session_and_app(db, session_id)
    if sess.status == "EXPIRED":
        raise AppError("SESSION_EXPIRED", "This consent link has expired.", 410)
    if sess.status != "OPEN":
        raise AppError("SESSION_CLOSED", f"This consent session is already {sess.status.lower()}.", 409)
    sess.status = "DENIED"
    await consent_service.log_event(db, app.id, "DENIED")
    transition(db, app, S.CONSENT_DENIED, {"data_requested": False})
    add_timeline(db, app.id, "CONSENT_DENIED", "ok", None, {"data_requested": False})
    await db.commit()
    return {"session_id": session_id, "status": "CONSENT_DENIED", "message": "No data was accessed."}


async def grant_consent(db: AsyncSession, session_id: str, grants: dict[str, bool], purpose: str | None) -> dict[str, Any]:
    sess, app = await _session_and_app(db, session_id)
    if sess.status == "EXPIRED":
        raise AppError("SESSION_EXPIRED", "This consent link has expired. Please ask the dealer to start again.", 410)
    if sess.status != "OPEN":
        raise AppError("SESSION_CLOSED", f"This consent session is already {sess.status.lower()}.", 409)
    groups = get_settings().policy.consent.groups
    if not any(grants.get(g) for g in groups):  # nothing granted == denial
        denial = await deny_consent(db, session_id)
        return {**denial, "consent_id": None, "denied": True, "application_id": app.id}
    purpose = purpose or get_settings().policy.consent.purpose_template.format(product=get_settings().policy.products[app.requested_product_sku].label)
    art = await consent_service.create_artifact(db, sess, {g: bool(grants.get(g)) for g in groups}, purpose)
    transition(db, app, S.CONSENT_GRANTED)
    add_timeline(db, app.id, "CONSENT_GRANTED", "ok", None, {"consent_id": art.id, "grants": {g: bool(grants.get(g)) for g in groups}})
    await db.commit()
    schedule(process_after_consent(app.id, art.id))  # ingestion runs in the background; the UI polls
    return {**consent_service.artifact_view(art), "application_id": app.id}


# ───────────── 3. ingest → score → decide ─────────────
async def process_after_consent(application_id: str, consent_id: str) -> None:
    async with session_factory()() as db:
        try:
            await _process(db, application_id, consent_id)
        except Exception as exc:  # noqa: BLE001 — never leave an application stuck mid-pipeline
            await db.rollback()
            log.exception("pipeline error for %s: %s", application_id, type(exc).__name__)
            app = await db.get(Application, application_id)
            if app is not None and app.status in (S.INGESTING.value, S.SCORED.value):
                add_timeline(db, app.id, "PIPELINE_ERROR", "error", None, {"error": type(exc).__name__})
                transition(db, app, S.INSUFFICIENT_DATA, {"reason": "pipeline error — referred to manual review"})
                await db.commit()


async def _process(db: AsyncSession, application_id: str, consent_id: str) -> None:
    s = get_settings()
    app = await db.get(Application, application_id)
    art = await db.get(ConsentArtifact, consent_id)
    transition(db, app, S.INGESTING)
    await db.commit()

    # Parallel ingestion, per-source timeout, graceful degradation
    results = await ingest_all_sources(vendor_ref(app.mobile_number), art, demo_outages(app))
    labels = {"aa": "AA_INGESTION", "telecom": "TELECOM_INGESTION", "business": "BUSINESS_INGESTION"}
    for r in results:
        status = {"ok": "ok", "timeout": "timeout", "not_consented": "not_consented", "no_data": "no_data"}.get(r.status, "error")
        add_timeline(db, app.id, labels[r.source], status, r.latency_ms,
                     {"degraded": not r.usable, "detail": r.detail, **({"simulated_outage": True} if r.source in demo_outages(app) else {})})
        db.add(DataAccessLog(application_id=app.id, consent_id=consent_id, source=r.source, status=status, latency_ms=r.latency_ms, detail=r.detail))
    await db.commit()

    # Sufficient-data gate: never score near-empty vectors
    if usable_groups(results) < s.policy.decision.min_sources_for_scoring:
        n = usable_groups(results)
        transition(db, app, S.INSUFFICIENT_DATA, {"usable_sources": n, "required": s.policy.decision.min_sources_for_scoring})
        db.add(AuditRecord(application_id=app.id, model_version=get_scoring_service().model_version, policy_version=s.policy.policy_version,
                           consent_id=consent_id, outcome=S.INSUFFICIENT_DATA.value))
        await db.commit()
        msg = await notifications.send_insufficient(db, app)
        add_timeline(db, app.id, "RESULT_MESSAGE_SENT", "ok", None, {"provider": msg.provider, "delivery_status": msg.delivery_status})
        await db.commit()
        return

    # Features (single pipeline code path)
    t0 = time.perf_counter()
    # CPU-bound work runs in a thread: the event loop must stay free (ingestion calls our own HTTP endpoints)
    features = await asyncio.to_thread(build_features, to_raw_payloads(results), app.requested_emi, product_sku=app.requested_product_sku, ticket_size=app.ticket_size)
    add_timeline(db, app.id, "FEATURE_BUILD", "ok", _ms(t0), {"n_features": int(features.notna().sum()), "of": len(features)})

    # Score + explain
    t1 = time.perf_counter()
    scoring = get_scoring_service()
    res = await asyncio.to_thread(scoring.predict, features)
    expl = await asyncio.to_thread(lambda: get_explainer().explain(features))
    add_timeline(db, app.id, "SCORING", "ok", _ms(t1), {"score": round(res.score), "model_version": scoring.model_version})

    # Consent may have been revoked while we were working → do not persist features
    await db.refresh(art)
    fv = _clean_features(features)
    app.feature_vector_hash = sha256_hex(json.dumps(fv, sort_keys=True))
    app.feature_vector_json = None if art.revoked else json.dumps(fv)
    app.score, app.pd = round(res.score, 1), res.pd
    transition(db, app, S.SCORED)

    decision = evaluate_decision(res.score, res.pd, app.requested_product_sku, s.policy)
    app.suggested_ticket = decision.suggested_ticket
    transition(db, app, decision.outcome, {"reason": decision.reason})
    add_timeline(db, app.id, "DECISION", "ok", 1, {"outcome": decision.outcome.value, "score": round(res.score)})

    # Immutable audit record (insert-only)
    db.add(AuditRecord(
        application_id=app.id, model_version=scoring.model_version, policy_version=s.policy.policy_version, consent_id=consent_id,
        feature_vector_hash=app.feature_vector_hash, raw_score=res.raw_margin, calibrated_pd=res.pd, final_score=round(res.score, 1),
        outcome=decision.outcome.value, shap_top_positive=json.dumps(expl.positive), shap_top_negative=json.dumps(expl.negative),
        reason_codes=json.dumps([d["reason_code"] for d in expl.negative + expl.positive if d.get("reason_code")]), waterfall_json=json.dumps({"base_score": expl.base_score, "items": expl.waterfall}),
    ))
    await db.commit()

    await _post_decision_actions(db, app, decision.outcome, decision.suggested_ticket, expl.negative)


async def _post_decision_actions(db: AsyncSession, app: Application, outcome: S, suggested_ticket: float | None, negatives: list[dict]) -> None:
    s = get_settings()
    if outcome == S.APPROVED:
        product = s.policy.products[app.requested_product_sku]
        t = time.perf_counter()
        ho = await get_los().handoff(app.id, {"route": "saksham_approved", "score": app.score, "product": app.requested_product_sku})
        add_timeline(db, app.id, "LOS_HANDOFF", "ok", _ms(t), {"reference": ho.reference, "detail": ho.detail})
        t = time.perf_counter()
        loan = await get_lms().create_loan_account(app.id, app.requested_product_sku, app.ticket_size, app.requested_emi, product.tenure_months)
        add_timeline(db, app.id, "LMS_ACCOUNT", "ok", _ms(t), {"loan_id": loan["loan_id"], "tier": loan["tier"]})
        msg = await notifications.send_approved(db, app)
    elif outcome == S.CONDITIONAL_APPROVAL:
        msg = await notifications.send_conditional(db, app, suggested_ticket or 0)
    elif outcome == S.DECLINED_WITH_PLAN:
        t = time.perf_counter()
        plan = await get_advisory().generate_plan(negatives, app.preferred_language, app.requested_product_sku, notifications.first_name(app))
        add_timeline(db, app.id, "ADVISORY", "ok", _ms(t), {"source": plan.source, "language": plan.language, **({"fallback_reason": plan.fallback_reason} if plan.fallback_reason else {})})
        app.plan_json = json.dumps(plan.as_dict(), ensure_ascii=False)
        msg = await notifications.send_plan(db, app, plan)
    else:
        return
    add_timeline(db, app.id, "RESULT_MESSAGE_SENT", "ok" if msg.delivery_status != "failed_real_send" else "error", None,
                 {"provider": msg.provider, "delivery_status": msg.delivery_status, **({"error": msg.error} if msg.error else {})})
    await db.commit()


# ───────────── revoke ─────────────
async def revoke_consent(db: AsyncSession, consent_id: str) -> dict[str, Any]:
    result = await consent_service.revoke(db, consent_id)
    art = await db.get(ConsentArtifact, consent_id)
    add_timeline(db, art.application_id, "CONSENT_REVOKED", "ok", None, {"features_purged": result["features_purged"]})
    await db.commit()
    return result


async def withdraw_approval(db: AsyncSession, application_id: str, reason: str) -> dict[str, Any]:
    """Dealer withdraws an approval. The audit record and consent history are kept; the loan drops off the approved list."""
    s = get_settings()
    if reason not in s.policy.withdrawal.reasons:
        raise AppError("INVALID_REASON", f"reason must be one of {', '.join(s.policy.withdrawal.reasons)}", 422)
    app = await load_application(db, application_id)
    if app.outcome != S.APPROVED.value:
        raise AppError("NOT_APPROVED", f"Only approved applications can be withdrawn (this one is {app.outcome or app.status}).", 409)
    if (await db.execute(select(Withdrawal).where(Withdrawal.application_id == application_id))).first():
        raise AppError("ALREADY_WITHDRAWN", "This approval has already been withdrawn.", 409)
    w = Withdrawal(application_id=app.id, reason=reason)
    db.add(w)
    add_timeline(db, app.id, "APPROVAL_WITHDRAWN", "ok", None, {"reason": reason})
    await db.commit()
    return {"application_id": app.id, "withdrawn": True, "reason": reason, "withdrawn_at": w.withdrawn_at.isoformat() + "Z"}


async def load_application(db: AsyncSession, application_id: str) -> Application:
    app = await db.get(Application, application_id)
    if app is None:
        raise NotFound("Application not found", "APPLICATION_NOT_FOUND")
    await refresh_expiry(db, app)
    return app


async def timeline_for(db: AsyncSession, application_id: str) -> list[TimelineEvent]:
    res = await db.execute(select(TimelineEvent).where(TimelineEvent.application_id == application_id).order_by(TimelineEvent.id))
    return list(res.scalars())
