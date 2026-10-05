"""Consent artifacts: signed, granular, revocable, with TTL. Verified on EVERY data access."""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConsentError, NotFound
from app.core.security import sign_payload, vendor_ref, verify_signature
from app.core.timeutil import iso, utcnow
from app.models import Application, ConsentArtifact, ConsentLog, ConsentSession
from app.models.application import new_id

GROUPS = ("aa", "telecom", "business")


def _signed_fields(a: ConsentArtifact) -> dict[str, Any]:
    return {
        "consent_id": a.id, "session_id": a.session_id, "application_id": a.application_id,
        "grants": {"aa": a.grant_aa, "telecom": a.grant_telecom, "business": a.grant_business},
        "purpose": a.purpose, "granted_at": iso(a.granted_at), "expires_at": iso(a.expires_at),
    }


def artifact_view(a: ConsentArtifact) -> dict[str, Any]:
    return {
        "consent_id": a.id, "session_id": a.session_id,
        "grants": {"aa": a.grant_aa, "telecom": a.grant_telecom, "business": a.grant_business},
        "granted_at": iso(a.granted_at), "expires_at": iso(a.expires_at),
        "revocable": not a.revoked, "revoked": a.revoked, "signature": a.signature,
    }


async def get_open_session(db: AsyncSession, session_id: str) -> ConsentSession:
    """Load a session and lazily expire it (TTL enforced on read)."""
    sess = await db.get(ConsentSession, session_id)
    if sess is None:
        raise NotFound("Consent session not found", "SESSION_NOT_FOUND")
    if sess.status == "OPEN" and sess.expires_at <= utcnow():
        sess.status = "EXPIRED"
        await db.commit()
    return sess


async def log_event(db: AsyncSession, application_id: str, event: str, consent_id: str | None = None, details: dict | None = None) -> None:
    db.add(ConsentLog(application_id=application_id, consent_id=consent_id, event=event, details=json.dumps(details) if details else None))


async def create_artifact(db: AsyncSession, sess: ConsentSession, grants: dict[str, bool], purpose: str) -> ConsentArtifact:
    policy = get_settings().policy.consent
    now = utcnow()
    art = ConsentArtifact(
        session_id=sess.id, application_id=sess.application_id,
        grant_aa=bool(grants.get("aa")), grant_telecom=bool(grants.get("telecom")), grant_business=bool(grants.get("business")),
        purpose=purpose, granted_at=now, expires_at=now + timedelta(days=policy.ttl_days), signature="",
    )
    art.id = new_id()  # the id is part of the signed payload, so assign it before signing
    art.signature = sign_payload(_signed_fields(art))
    db.add(art)
    sess.status = "GRANTED"
    await log_event(db, sess.application_id, "GRANTED", art.id, {"grants": {g: getattr(art, f"grant_{g}") for g in GROUPS}})
    await db.flush()
    return art


async def verify_for_source(db: AsyncSession, consent_id: str | None, group: str, customer_ref: str | None = None) -> ConsentArtifact:
    """Raise ConsentError unless the artifact is valid, unrevoked, unexpired, correctly signed and covers `group`."""
    if not consent_id:
        raise ConsentError("CONSENT_REQUIRED", "A valid consent token is required to access this data source.")
    art = await db.get(ConsentArtifact, consent_id)
    if art is None:
        raise ConsentError("CONSENT_REQUIRED", "Unknown consent token.")
    if art.revoked:
        raise ConsentError("CONSENT_REVOKED", "Consent has been revoked by the customer.")
    if art.expires_at <= utcnow():
        raise ConsentError("CONSENT_EXPIRED", "Consent has expired.")
    if not verify_signature(_signed_fields(art), art.signature):
        raise ConsentError("CONSENT_INVALID", "Consent signature verification failed.")
    if not getattr(art, f"grant_{group}", False):
        raise ConsentError("CONSENT_SCOPE", f"Consent does not cover the '{group}' data source.")
    if customer_ref is not None:
        app = await db.get(Application, art.application_id)
        if app is None or vendor_ref(app.mobile_number) != customer_ref:
            raise ConsentError("CONSENT_MISMATCH", "Consent token was not issued for this customer.")
    return art


async def revoke(db: AsyncSession, consent_id: str) -> dict[str, Any]:
    art = await db.get(ConsentArtifact, consent_id)
    if art is None:
        raise NotFound("Consent not found", "CONSENT_NOT_FOUND")
    purged = False
    if not art.revoked:
        art.revoked = True
        art.revoked_at = utcnow()
        app = await db.get(Application, art.application_id)
        if app is not None and app.feature_vector_json is not None:
            app.feature_vector_json = None  # purge stored features; the hash stays in the audit record
            purged = True
        await log_event(db, art.application_id, "REVOKED", art.id, {"features_purged": purged})
    await db.commit()
    return {"consent_id": art.id, "revoked": True, "features_purged": purged}


async def latest_artifact_for_application(db: AsyncSession, application_id: str) -> ConsentArtifact | None:
    res = await db.execute(select(ConsentArtifact).where(ConsentArtifact.application_id == application_id).order_by(ConsentArtifact.granted_at.desc()))
    return res.scalars().first()
