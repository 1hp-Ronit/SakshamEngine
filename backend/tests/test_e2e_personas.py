"""All 7 demo personas, end to end through the public API, messaging in simulated mode."""
import pytest

from app.core.config import get_settings
from app.services import orchestrator

PERSONAS = {p["id"]: p for p in get_settings().personas}


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    ing = get_settings().policy.ingestion
    monkeypatch.setattr(ing, "per_source_timeout_seconds", 0.4)
    monkeypatch.setattr(ing, "outage_sleep_seconds", 1.5)


def create_body(p):
    body = {"mobile_number": p["mobile_number"], "pan_token": p["pan_token"], "aadhaar_token": p["aadhaar_token"], "requested_product_sku": p["product_sku"],
            "applicant_name": p["name"], "preferred_language": p["language"], "persona_name": p["key"]}
    if p.get("simulate_outage"):
        body["demo_options"] = {"simulate_outage": p["simulate_outage"]}
    return body


async def run_persona(client, p, grants=None):
    r = await client.post("/api/v1/applications/create", json=create_body(p))
    assert r.status_code == 200, r.text
    created = r.json()
    if created["status"] == "AWAITING_CONSENT":
        sid = created["session_id"]
        info = (await client.get(f"/api/v1/consent/session/{sid}")).json()
        assert info["seconds_remaining"] > 0 and info["groups"] == ["aa", "telecom", "business"]
        if p.get("consent_behaviour") == "deny":
            r = await client.post("/api/v1/consent/deny", json={"session_id": sid})
            assert r.status_code == 200
        else:
            r = await client.post("/api/v1/consent/authorize", json={"session_id": sid, "grants": grants or {"aa": True, "telecom": True, "business": True}})
            assert r.status_code == 200, r.text
        await orchestrator.drain()
    return created, (await client.get(f"/api/v1/applications/{created['application_id']}")).json()


@pytest.mark.parametrize("pid", sorted(PERSONAS))
async def test_persona_outcome(client, pid):
    p = PERSONAS[pid]
    created, app = await run_persona(client, p)
    assert app["status"] == p["expected_outcome"], (pid, app["status"], app.get("score"))
    assert app["terminal"]


async def test_consent_url_is_built_from_public_base_url_never_localhost(client):
    created, _ = await run_persona(client, PERSONAS[1])
    assert created["consent_url"].startswith("https://test.example.com/consent/")


async def test_persona1_approved_full_trace_and_audit(client):
    created, app = await run_persona(client, PERSONAS[1])
    aid = created["application_id"]
    trace = (await client.get(f"/api/v1/applications/{aid}/trace")).json()
    stages = [s["stage"] for s in trace["stages"]]
    for expected in ("CREATED", "BUREAU_CHECK", "CONSENT_REQUEST_SENT", "CONSENT_GRANTED", "AA_INGESTION", "TELECOM_INGESTION", "BUSINESS_INGESTION",
                     "FEATURE_BUILD", "SCORING", "DECISION", "LOS_HANDOFF", "LMS_ACCOUNT", "RESULT_MESSAGE_SENT"):
        assert expected in stages, expected
    assert all(trace["sources"][k]["status"] == "ok" for k in ("aa", "telecom", "business"))
    assert trace["total_latency_ms"] is not None and trace["total_latency_ms"] < 2000
    dec = (await client.get(f"/api/v1/applications/{aid}/decision")).json()
    assert dec["outcome"] == "APPROVED" and dec["score"] >= get_settings().policy.decision.approve_cutoff
    assert dec["audit_record_id"] and dec["model_version"].startswith("v1-lgbm") and dec["policy_version"] == "v1.0" and dec["consent_id"]
    assert dec["shap_drivers"]["positive"] and dec["waterfall"]
    assert app["loan"]["current_tier"] == "STARTER"
    # raw payloads are never stored; only the feature vector (+hash)
    assert dec["feature_vector_hash"]
    msgs = (await client.get(f"/api/v1/messages/{aid}")).json()["messages"]
    assert [m["purpose"] for m in msgs] == ["consent_request", "result"]


async def test_persona2_declined_with_hindi_plan(client):
    created, app = await run_persona(client, PERSONAS[2])
    aid = created["application_id"]
    plan = (await client.get(f"/api/v1/applications/{aid}/plan")).json()
    assert plan["language"] == "hi" and 1 <= len(plan["steps"]) <= 3 and plan["source"] == "fallback"
    assert any("ऀ" <= ch <= "ॿ" for ch in plan["greeting"] + "".join(plan["steps"]))
    dec = (await client.get(f"/api/v1/applications/{aid}/decision")).json()
    assert dec["outcome"] == "DECLINED_WITH_PLAN" and dec["shap_drivers"]["negative"]
    result = [m for m in (await client.get(f"/api/v1/messages/{aid}")).json()["messages"] if m["purpose"] == "result"][0]
    assert "/plan/" in result["body"]
    # language toggle on the plan page
    assert (await client.get(f"/api/v1/applications/{aid}/plan", params={"lang": "en"})).json()["language"] == "en"


async def test_persona4_marathi_plan_without_llm_key(client):
    created, _ = await run_persona(client, PERSONAS[4])
    plan = (await client.get(f"/api/v1/applications/{created['application_id']}/plan")).json()
    assert plan["language"] == "mr" and plan["source"] == "fallback"
    assert "नमस्कार" in plan["greeting"]


async def test_persona5_bypass_never_asks_for_consent(client):
    created, app = await run_persona(client, PERSONAS[5])
    assert created["status"] == "BYPASSED_TO_LOS" and "session_id" not in created and app["bureau"] == {"status": "HIT", "score": 760}


async def test_persona6_denied_requests_no_data(client):
    created, app = await run_persona(client, PERSONAS[6])
    stages = [s["stage"] for s in app["timeline"]]
    assert app["status"] == "CONSENT_DENIED"
    assert not any(s.endswith("_INGESTION") for s in stages), "no data may be requested after a denial"
    assert (await client.get(f"/api/v1/applications/{created['application_id']}/decision")).status_code == 409


async def test_persona7_outage_degrades_gracefully_and_is_still_approved(client):
    created, app = await run_persona(client, PERSONAS[7])
    trace = (await client.get(f"/api/v1/applications/{created['application_id']}/trace")).json()
    assert trace["sources"]["aa"]["status"] == "timeout"
    assert trace["sources"]["telecom"]["status"] == "ok" and trace["sources"]["business"]["status"] == "ok"
    assert app["status"] == "APPROVED"


async def test_partial_consent_leaves_unconsented_sources_uncalled(client):
    created, app = await run_persona(client, PERSONAS[1], grants={"aa": True, "telecom": True, "business": False})
    trace = (await client.get(f"/api/v1/applications/{created['application_id']}/trace")).json()
    assert trace["sources"]["business"]["status"] == "not_consented"
    assert app["status"] in ("APPROVED", "CONDITIONAL_APPROVAL", "DECLINED_WITH_PLAN")


async def test_single_source_is_insufficient_data(client):
    created, app = await run_persona(client, PERSONAS[1], grants={"aa": True, "telecom": False, "business": False})
    assert app["status"] == "INSUFFICIENT_DATA"
    assert (await client.get(f"/api/v1/applications/{created['application_id']}")).json()["score"] is None


async def test_revocation_purges_features_and_blocks_further_access(client, db):
    from app.models import Application

    created, app = await run_persona(client, PERSONAS[1])
    cid = app["consent"]["consent_id"]
    row = await db.get(Application, created["application_id"])
    assert row.feature_vector_json is not None
    r = await client.post("/api/v1/consent/revoke", json={"consent_id": cid})
    assert r.json() == {"consent_id": cid, "revoked": True, "features_purged": True}
    await db.refresh(row)
    assert row.feature_vector_json is None
    from app.core.security import vendor_ref
    r = await client.get("/mock/aa/bank-statement", params={"mobile_hash": vendor_ref(PERSONAS[1]["mobile_number"])}, headers={"X-Consent-Token": cid})
    assert r.status_code == 403


async def test_session_expiry_is_lazy(client, db):
    from datetime import timedelta
    from app.core.timeutil import utcnow
    from app.models import ConsentSession

    r = await client.post("/api/v1/applications/create", json=create_body(PERSONAS[1]))
    created = r.json()
    sess = await db.get(ConsentSession, created["session_id"])
    sess.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    assert (await client.get(f"/api/v1/applications/{created['application_id']}")).json()["status"] == "EXPIRED"
    r = await client.post("/api/v1/consent/authorize", json={"session_id": created["session_id"], "grants": {"aa": True, "telecom": True, "business": True}})
    assert r.status_code == 410 and r.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_authorize_twice_is_rejected(client):
    r = await client.post("/api/v1/applications/create", json=create_body(PERSONAS[1]))
    sid = r.json()["session_id"]
    ok = await client.post("/api/v1/consent/authorize", json={"session_id": sid, "grants": {"aa": True, "telecom": True, "business": True}})
    again = await client.post("/api/v1/consent/authorize", json={"session_id": sid, "grants": {"aa": True, "telecom": True, "business": True}})
    await orchestrator.drain()
    assert ok.status_code == 200 and again.status_code == 409


async def test_validation_errors_use_the_error_shape(client):
    r = await client.post("/api/v1/applications/create", json={"mobile_number": "123", "pan_token": "x", "aadhaar_token": "y", "requested_product_sku": "BOAT"})
    assert r.status_code == 422 and set(r.json()["error"]) >= {"code", "message"}
    r = await client.post("/api/v1/applications/create", json={**create_body(PERSONAS[1]), "requested_product_sku": "BOAT"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_PRODUCT"
    assert (await client.get("/api/v1/applications/nope")).json()["error"]["code"] == "APPLICATION_NOT_FOUND"


async def test_decision_exposes_affordability_until_consent_is_revoked(client):
    created, app = await run_persona(client, PERSONAS[1])
    aid = created["application_id"]
    assert app["tenure_months"] == 24
    dec = (await client.get(f"/api/v1/applications/{aid}/decision")).json()
    aff = dec["affordability"]
    assert aff["est_monthly_income"] > 0 and 0 < aff["emi_to_income_ratio"] < 1
    cfg = (await client.get("/demo/config")).json()
    assert cfg["policy"]["comfortable_emi_ratio"] == 0.33
    await client.post("/api/v1/consent/revoke", json={"consent_id": app["consent"]["consent_id"]})
    assert (await client.get(f"/api/v1/applications/{aid}/decision")).json()["affordability"] is None
