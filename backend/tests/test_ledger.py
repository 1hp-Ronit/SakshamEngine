"""Consent & data-rights ledger and the approved-loans list."""
import pytest

from app.core.config import get_settings
from tests.test_e2e_personas import PERSONAS, run_persona


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    ing = get_settings().policy.ingestion
    monkeypatch.setattr(ing, "per_source_timeout_seconds", 0.4)
    monkeypatch.setattr(ing, "outage_sleep_seconds", 1.5)


async def test_ledger_records_every_source_attempt_including_the_unconsented_one(client):
    created, _ = await run_persona(client, PERSONAS[1], grants={"aa": True, "telecom": True, "business": False})
    ledger = (await client.get(f"/api/v1/applications/{created['application_id']}/ledger")).json()
    by_source = {r["source"]: r["status"] for r in ledger["data_access"]}
    assert by_source["aa"] == "ok"
    assert by_source["telecom"] == "ok"
    assert by_source["business"] == "not_consented"  # evidence that nothing was read
    assert len(ledger["consents"]) == 1
    assert ledger["consents"][0]["grants"] == {"aa": True, "telecom": True, "business": False}
    assert ledger["consents"][0]["active"] is True
    assert [e["event"] for e in ledger["events"]] == ["GRANTED"]
    assert ledger["holdings"]["feature_vector"] == "stored"
    assert ledger["holdings"]["raw_vendor_payloads"].startswith("never stored")


async def test_ledger_after_revocation_shows_purge_and_blocked_access(client):
    created, _ = await run_persona(client, PERSONAS[1])
    aid = created["application_id"]
    consent_id = (await client.get(f"/api/v1/applications/{aid}")).json()["consent"]["consent_id"]
    r = await client.post("/api/v1/consent/revoke", json={"consent_id": consent_id})
    assert r.status_code == 200 and r.json()["features_purged"] is True

    ledger = (await client.get(f"/api/v1/applications/{aid}/ledger")).json()
    assert ledger["consents"][0]["revoked"] is True
    assert ledger["consents"][0]["active"] is False
    assert [e["event"] for e in ledger["events"]] == ["GRANTED", "REVOKED"]
    assert ledger["holdings"]["feature_vector"] == "purged on consent revocation"
    assert ledger["holdings"]["audit_record"] is not None  # the audit trail survives revocation


async def test_ledger_404_for_unknown_application(client):
    r = await client.get("/api/v1/applications/does-not-exist/ledger")
    assert r.status_code == 404


async def test_approved_list_contains_only_approved_applications(client):
    approved, _ = await run_persona(client, PERSONAS[1])          # APPROVED
    declined, _ = await run_persona(client, PERSONAS[2])          # DECLINED_WITH_PLAN

    body = (await client.get("/api/v1/applications")).json()
    ids = [row["application_id"] for row in body["loans"]]
    assert body["outcome"] == "APPROVED"
    assert approved["application_id"] in ids
    assert declined["application_id"] not in ids

    row = next(r for r in body["loans"] if r["application_id"] == approved["application_id"])
    assert row["los_reference"].startswith("LOS-")
    assert row["consent_active"] is True
    assert row["loan"]["current_tier"] == "STARTER"
    assert row["mobile_masked"] != PERSONAS[1]["mobile_number"]  # never the full number in a list


async def test_approved_list_can_filter_by_another_outcome(client):
    await run_persona(client, PERSONAS[2])
    body = (await client.get("/api/v1/applications", params={"outcome": "DECLINED_WITH_PLAN"})).json()
    assert body["count"] >= 1
    assert all(row["outcome"] == "DECLINED_WITH_PLAN" for row in body["loans"])
