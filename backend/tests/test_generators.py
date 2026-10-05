from datetime import date

import numpy as np

from app.mock_services import generators as g

AS_OF = date(2026, 10, 1)


def test_payloads_are_deterministic():
    p = g.build_profile(123, "merchant", 0.6)
    assert g.generate_aa_payload(p, AS_OF) == g.generate_aa_payload(p, AS_OF)
    assert g.generate_telecom_payload(p, AS_OF) == g.generate_telecom_payload(p, AS_OF)
    assert g.generate_gst_payload(p, AS_OF) == g.generate_gst_payload(p, AS_OF)


def test_different_seeds_differ():
    a = g.generate_aa_payload(g.build_profile(1, "gig", 0.5), AS_OF)
    b = g.generate_aa_payload(g.build_profile(2, "gig", 0.5), AS_OF)
    assert a != b


def test_aa_payload_shape_and_upi_is_a_mode_not_a_source():
    p = g.build_profile(5, "gig", 0.5)
    aa = g.generate_aa_payload(p, AS_OF)
    assert set(aa) >= {"account", "balances", "transactions"}
    assert len(aa["balances"]) == 180
    modes = {t["mode"] for t in aa["transactions"]}
    assert "UPI" in modes and modes <= {"UPI", "NEFT", "IMPS", "CASH", "ATM", "ECS_RETURN", "OTHER"}
    assert all(t["type"] in ("CREDIT", "DEBIT") for t in aa["transactions"])
    assert min(b["balance"] for b in aa["balances"]) >= 0  # no overdraft


def test_segment_data_availability():
    gig = g.build_profile(11, "gig", 0.5)
    assert g.generate_gst_payload(gig, AS_OF) is None and g.generate_mandi_payload(gig, AS_OF) is None
    # find a farmer & a merchant that have their business feed
    farmer = next(p for p in (g.build_profile(s, "farmer", 0.5) for s in range(50)) if p.has_mandi)
    merchant = next(p for p in (g.build_profile(s, "merchant", 0.5) for s in range(50)) if p.has_gst)
    assert g.generate_mandi_payload(farmer, AS_OF)["receipts"]
    assert g.generate_gst_payload(merchant, AS_OF)["returns"]
    assert g.generate_gst_payload(farmer, AS_OF) is None


def test_creditworthiness_moves_the_statistics():
    def stats(cw):
        bounces, balances = [], []
        for s in range(60):
            p = g.build_profile(s, "gig", cw, 20000)
            if not p.has_aa:
                continue
            aa = g.generate_aa_payload(p, AS_OF)
            bounces.append(sum(t["mode"] == "ECS_RETURN" for t in aa["transactions"]))
            balances.append(np.mean([b["balance"] for b in aa["balances"]]))
        return np.mean(bounces), np.mean(balances)

    low_b, low_bal = stats(0.1)
    high_b, high_bal = stats(0.9)
    assert low_b > high_b
    assert high_bal > low_bal


def test_bureau_default_is_no_hit():
    assert g.generate_bureau_result(1) == {"status": "NO_HIT", "score": -1}


def test_persona_data_does_not_depend_on_secret_key(monkeypatch):
    """Rotating SECRET_KEY must not change the demo personas' data (and therefore their outcomes)."""
    from app.core.config import get_settings
    from app.core.security import mobile_hash, vendor_ref
    from app.mock_services.personas import resolve_profile

    before = g.generate_aa_payload(resolve_profile(vendor_ref("9000000002")), AS_OF)
    stored_before = mobile_hash("9000000002")
    monkeypatch.setattr(get_settings().env, "secret_key", "a-completely-different-secret")
    assert g.generate_aa_payload(resolve_profile(vendor_ref("9000000002")), AS_OF) == before
    assert mobile_hash("9000000002") != stored_before  # …while the keyed hash we STORE does depend on the secret
