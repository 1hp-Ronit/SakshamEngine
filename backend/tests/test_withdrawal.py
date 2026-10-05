"""Withdrawing an approval: removes it from the approved list, keeps the audit trail, and enforces the rules."""
import pytest

from app.core.config import get_settings
from tests.test_e2e_personas import PERSONAS, run_persona


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    ing = get_settings().policy.ingestion
    monkeypatch.setattr(ing, "per_source_timeout_seconds", 0.4)
    monkeypatch.setattr(ing, "outage_sleep_seconds", 1.5)


REASON = get_settings().policy.withdrawal.reasons[0]


async def test_withdrawn_loan_leaves_the_approved_list_but_keeps_its_audit_record(client):
    created, _ = await run_persona(client, PERSONAS[1])
    aid = created["application_id"]

    r = await client.post(f"/api/v1/applications/{aid}/withdraw", json={"reason": REASON})
    assert r.status_code == 200, r.text
    assert r.json()["withdrawn"] is True

    ids = [row["application_id"] for row in (await client.get("/api/v1/applications")).json()["loans"]]
    assert aid not in ids

    app = (await client.get(f"/api/v1/applications/{aid}")).json()
    assert app["withdrawal"]["reason"] == REASON
    assert app["outcome"] == "APPROVED"  # the decision itself is unchanged
    assert (await client.get(f"/api/v1/applications/{aid}/decision")).status_code == 200  # audit record still readable
    stages = [e["stage"] for e in app["timeline"]]
    assert "APPROVAL_WITHDRAWN" in stages


async def test_a_withdrawal_can_only_happen_once(client):
    created, _ = await run_persona(client, PERSONAS[1])
    aid = created["application_id"]
    await client.post(f"/api/v1/applications/{aid}/withdraw", json={"reason": REASON})
    r = await client.post(f"/api/v1/applications/{aid}/withdraw", json={"reason": REASON})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_WITHDRAWN"


async def test_only_approved_applications_can_be_withdrawn(client):
    created, _ = await run_persona(client, PERSONAS[2])  # DECLINED_WITH_PLAN
    r = await client.post(f"/api/v1/applications/{created['application_id']}/withdraw", json={"reason": REASON})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NOT_APPROVED"


async def test_reason_must_come_from_policy(client):
    created, _ = await run_persona(client, PERSONAS[1])
    r = await client.post(f"/api/v1/applications/{created['application_id']}/withdraw", json={"reason": "BECAUSE_I_SAID_SO"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_REASON"


async def test_withdrawal_does_not_revoke_consent_or_purge_data(client):
    created, _ = await run_persona(client, PERSONAS[1])
    aid = created["application_id"]
    await client.post(f"/api/v1/applications/{aid}/withdraw", json={"reason": REASON})
    ledger = (await client.get(f"/api/v1/applications/{aid}/ledger")).json()
    assert ledger["consents"][0]["revoked"] is False
    assert ledger["holdings"]["feature_vector"] == "stored"


async def test_reasons_are_served_to_the_dashboard(client):
    cfg = (await client.get("/demo/config")).json()
    assert cfg["withdrawal_reasons"] == get_settings().policy.withdrawal.reasons
