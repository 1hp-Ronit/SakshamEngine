"""Consent is enforced by the mock data services on every call."""
from datetime import timedelta

import pytest

from app.core.security import mobile_hash, tokenize_identifier, vendor_ref
from app.core.timeutil import utcnow
from app.models import Application, ConsentSession
from app.services import consent as consent_service

MOBILE = "9000000001"  # persona 1 (merchant)


async def _make_consent(db, grants, mobile=MOBILE, expired=False):
    app = Application(
        mobile_number=mobile, mobile_number_hash=mobile_hash(mobile), pan_token_hash=tokenize_identifier("P", "pan"),
        aadhaar_token_hash=tokenize_identifier("A", "aadhaar"), requested_product_sku="TWO_WHEELER", requested_emi=4200, ticket_size=80000,
    )
    db.add(app)
    await db.flush()
    sess = ConsentSession(application_id=app.id, expires_at=utcnow() + timedelta(minutes=15))
    db.add(sess)
    await db.flush()
    art = await consent_service.create_artifact(db, sess, grants, "test purpose")
    if expired:
        art.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    return app, art


async def test_no_token_is_rejected(client):
    r = await client.get("/mock/aa/bank-statement", params={"mobile_hash": vendor_ref(MOBILE)})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CONSENT_REQUIRED"


async def test_valid_consent_returns_data(client, db):
    _, art = await _make_consent(db, {"aa": True, "telecom": True, "business": True})
    h = vendor_ref(MOBILE)
    for path in ("/mock/aa/bank-statement", "/mock/telecom/recharge", "/mock/business/gst-returns"):
        r = await client.get(path, params={"mobile_hash": h}, headers={"X-Consent-Token": art.id})
        assert r.status_code == 200, (path, r.text)


async def test_scope_is_per_source_group(client, db):
    _, art = await _make_consent(db, {"aa": True, "telecom": False, "business": False})
    h = vendor_ref(MOBILE)
    ok = await client.get("/mock/aa/bank-statement", params={"mobile_hash": h}, headers={"X-Consent-Token": art.id})
    denied = await client.get("/mock/telecom/recharge", params={"mobile_hash": h}, headers={"X-Consent-Token": art.id})
    assert ok.status_code == 200
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "CONSENT_SCOPE"


async def test_revoked_consent_blocks_access_and_purges_features(client, db):
    app, art = await _make_consent(db, {"aa": True, "telecom": True, "business": True})
    app.feature_vector_json = '{"x": 1}'
    await db.commit()
    result = await consent_service.revoke(db, art.id)
    assert result == {"consent_id": art.id, "revoked": True, "features_purged": True}
    await db.refresh(app)
    assert app.feature_vector_json is None
    r = await client.get("/mock/aa/bank-statement", params={"mobile_hash": vendor_ref(MOBILE)}, headers={"X-Consent-Token": art.id})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REVOKED"


async def test_expired_consent_is_rejected(client, db):
    _, art = await _make_consent(db, {"aa": True, "telecom": True, "business": True}, expired=True)
    r = await client.get("/mock/aa/bank-statement", params={"mobile_hash": vendor_ref(MOBILE)}, headers={"X-Consent-Token": art.id})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_EXPIRED"


async def test_tampered_signature_is_rejected(client, db):
    _, art = await _make_consent(db, {"aa": True, "telecom": False, "business": False})
    art.grant_telecom = True  # privilege escalation attempt without re-signing
    await db.commit()
    r = await client.get("/mock/telecom/recharge", params={"mobile_hash": vendor_ref(MOBILE)}, headers={"X-Consent-Token": art.id})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_INVALID"


async def test_token_cannot_be_used_for_another_customer(client, db):
    _, art = await _make_consent(db, {"aa": True, "telecom": True, "business": True})
    r = await client.get("/mock/aa/bank-statement", params={"mobile_hash": vendor_ref("9000000002")}, headers={"X-Consent-Token": art.id})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_MISMATCH"


async def test_bureau_needs_no_consent(client):
    r = await client.post("/mock/bureau/check", json={"mobile_hash": vendor_ref("9000000005")})
    assert r.json() == {"status": "HIT", "score": 760}
    r = await client.post("/mock/bureau/check", json={"mobile_hash": vendor_ref(MOBILE)})
    assert r.json() == {"status": "NO_HIT", "score": -1}


async def test_no_data_for_gig_worker_business_feed(client, db):
    _, art = await _make_consent(db, {"aa": True, "telecom": True, "business": True}, mobile="9000000002")
    r = await client.get("/mock/business/gst-returns", params={"mobile_hash": vendor_ref("9000000002")}, headers={"X-Consent-Token": art.id})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_DATA"


@pytest.mark.parametrize("path", ["/mock/aa/bank-statement"])
async def test_outage_flag_triggers_adapter_timeout(client, db, path, monkeypatch):
    from app.adapters.data_sources import MockAAAdapter
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings().policy.ingestion, "per_source_timeout_seconds", 0.2)
    monkeypatch.setattr(get_settings().policy.ingestion, "outage_sleep_seconds", 1.0)
    _, art = await _make_consent(db, {"aa": True, "telecom": True, "business": True})
    res = await MockAAAdapter().fetch(vendor_ref(MOBILE), art.id, simulate_outage=True)
    assert res.status == "timeout" and not res.usable
    ok = await MockAAAdapter().fetch(vendor_ref(MOBILE), art.id)
    assert ok.status == "ok" and ok.usable
