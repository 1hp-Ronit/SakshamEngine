"""Train/serve parity: identical raw payloads must yield an IDENTICAL feature vector in both code paths.

  training path : generators called directly (in-process), as ml/generate_data.py does
  serving path  : the same payloads fetched over HTTP from /mock/* (JSON round-trip, consent enforced) by the adapters
"""
import pandas as pd
import pytest

from app.core.config import get_settings
from app.core.security import mobile_hash, tokenize_identifier, vendor_ref
from app.core.timeutil import utcnow
from app.mock_services import generators as g
from app.mock_services.personas import resolve_profile
from app.models import Application, ConsentSession
from app.services import consent as consent_service
from app.services.feature_pipeline import build_features
from app.services.ingestion import ingest_all_sources, to_raw_payloads
from datetime import timedelta

PERSONA_MOBILES = ["9000000001", "9000000002", "9000000003", "9000000004"]


def _training_path(mobile: str, emi: float, sku: str) -> pd.Series:
    s = get_settings()
    prof = resolve_profile(vendor_ref(mobile))
    as_of = s.policy.mock.resolve_as_of()
    gst, mandi = g.generate_gst_payload(prof, as_of), g.generate_mandi_payload(prof, as_of)
    raw = {"aa": g.generate_aa_payload(prof, as_of), "telecom": g.generate_telecom_payload(prof, as_of), "business": {"gst": gst, "mandi": mandi} if (gst or mandi) else None}
    return build_features(raw, emi, product_sku=sku)


@pytest.mark.parametrize("mobile", PERSONA_MOBILES)
async def test_same_payloads_same_features_in_training_and_serving(client, db, mobile):
    s = get_settings()
    sku = "TWO_WHEELER"
    emi = s.policy.products[sku].monthly_emi

    app = Application(mobile_number=mobile, mobile_number_hash=mobile_hash(mobile), pan_token_hash=tokenize_identifier("P", "pan"),
                      aadhaar_token_hash=tokenize_identifier("A", "aadhaar"), requested_product_sku=sku, requested_emi=emi, ticket_size=80000)
    db.add(app)
    await db.flush()
    sess = ConsentSession(application_id=app.id, expires_at=utcnow() + timedelta(minutes=15))
    db.add(sess)
    await db.flush()
    art = await consent_service.create_artifact(db, sess, {"aa": True, "telecom": True, "business": True}, "parity")
    await db.commit()

    results = await ingest_all_sources(vendor_ref(mobile), art)
    serving = build_features(to_raw_payloads(results), emi, product_sku=sku)
    training = _training_path(mobile, emi, sku)
    pd.testing.assert_series_equal(training, serving, check_exact=True)


def test_training_rows_come_from_build_features():
    """The training generator must produce rows via the shared pipeline — never by generating feature values directly."""
    from ml.generate_data import _make_row, make_payloads

    for i in range(5):
        ctx = make_payloads(i, 42)
        expected = build_features(ctx["raw"], ctx["emi"], product_sku=ctx["sku"], ticket_size=ctx["ticket"])
        row = _make_row(i, 42)
        got = pd.Series({k: row[k] for k in expected.index}, dtype="float64")
        pd.testing.assert_series_equal(expected, got, check_exact=True)
