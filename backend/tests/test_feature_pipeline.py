"""Unit tests per feature group on small hand-built payloads (exact expectations)."""
import math
from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.services.feature_pipeline import FEATURE_NAMES, aa_features, build_features, gst_features, mandi_features, telecom_features

AS_OF = date(2026, 10, 1)
CFG = get_settings().policy.features


def _aa(balances, txns):
    start = AS_OF - timedelta(days=len(balances) - 1)
    return {
        "as_of": AS_OF.isoformat(),
        "balances": [{"date": (start + timedelta(days=i)).isoformat(), "balance": b} for i, b in enumerate(balances)],
        "transactions": txns,
    }


def _tx(days_ago, amount, type_, mode, narration="X"):
    return {"date": (AS_OF - timedelta(days=days_ago)).isoformat(), "amount": amount, "type": type_, "mode": mode, "narration": narration, "balance": 0}


def test_feature_vector_has_all_42_features_in_order():
    f = build_features({}, 4200, product_sku="TWO_WHEELER")
    assert list(f.index) == FEATURE_NAMES and len(f) == 42


def test_empty_payloads_give_nan_and_zero_flags_not_a_crash():
    f = build_features({}, 4200, product_sku="TWO_WHEELER")
    assert math.isnan(f["buffer_ratio"]) and math.isnan(f["est_monthly_income"]) and math.isnan(f["gst_avg_turnover"])
    assert f["n_sources_available"] == 0 and f["data_completeness_score"] == 0
    assert f["src_aa_available"] == f["src_telecom_available"] == f["src_business_available"] == 0
    assert f["requested_emi"] == 4200 and f["ticket_size"] == 80000


def test_aa_buffer_ratio_and_balance_days():
    f = aa_features(_aa([1000] * 90 + [100] * 90, []), AS_OF, emi=550, cfg=CFG)
    assert f["buffer_ratio"] == pytest.approx(550 / 550)  # avg balance 550 / emi 550
    assert f["min_balance_days"] == 90  # balances below ₹500
    assert f["balance_trend"] < 0  # falling


def test_aa_bounce_velocity_counts_only_last_90_days():
    txns = [_tx(10, 400, "DEBIT", "ECS_RETURN"), _tx(80, 400, "DEBIT", "ECS_RETURN"), _tx(120, 400, "DEBIT", "ECS_RETURN")]
    f = aa_features(_aa([5000] * 180, txns), AS_OF, 4200, CFG)
    assert f["bounce_velocity"] == 2


def test_aa_income_mix_and_regularity():
    txns = [_tx(5 + 30 * i, 10000, "CREDIT", "UPI", f"UPI/{i % 2}") for i in range(6)] + [_tx(7, 5000, "CREDIT", "CASH")]
    f = aa_features(_aa([5000] * 180, txns), AS_OF, 4200, CFG)
    assert f["distinct_upi_counterparties"] == 2
    assert f["cash_vs_digital_ratio"] == pytest.approx(5000 / 65000)
    assert f["digital_inflow_share"] == pytest.approx(60000 / 65000)
    assert f["avg_monthly_inflow"] == pytest.approx(65000 / 6)
    perfectly_regular = aa_features(_aa([5000] * 180, [_tx(5 + 30 * i, 10000, "CREDIT", "UPI") for i in range(6)]), AS_OF, 4200, CFG)
    assert perfectly_regular["income_regularity"] == pytest.approx(1.0)
    assert f["income_regularity"] < 1.0


def test_telecom_features():
    recharges = [{"date": (AS_OF - timedelta(days=d)).isoformat(), "amount": 200, "plan_type": "MONTHLY"} for d in (300, 270, 240, 210, 180, 150, 120, 90, 60, 30)]
    f = telecom_features({"sim_start_date": (AS_OF - timedelta(days=608)).isoformat(), "recharges": recharges}, AS_OF)
    assert f["recharge_frequency_regularity"] == pytest.approx(1.0)
    assert f["recharge_count_12m"] == 10
    assert f["avg_recharge_value"] == 200
    assert f["max_recharge_gap_days"] == 30
    assert f["sim_tenure_months"] == pytest.approx(608 / 30.4)


def test_telecom_open_gap_counts():
    recharges = [{"date": (AS_OF - timedelta(days=d)).isoformat(), "amount": 200, "plan_type": "MONTHLY"} for d in (200, 170, 140)]
    f = telecom_features({"sim_start_date": "2020-01-01", "recharges": recharges}, AS_OF)
    assert f["max_recharge_gap_days"] == 140  # still no recharge since 140 days ago


def test_gst_features():
    rets = [{"period": "2026-01", "turnover": 100, "filed_on": "2026-02-18"}, {"period": "2026-02", "turnover": 100, "filed_on": "2026-03-25"},
            {"period": "2026-03", "turnover": 100, "filed_on": "2026-04-20"}, {"period": "2026-04", "turnover": 100, "filed_on": "2026-05-10"}]
    f = gst_features({"returns": rets})
    assert f["gst_months_filed"] == 4 and f["gst_avg_turnover"] == 100
    assert f["gst_filing_consistency"] == pytest.approx(3 / 4)  # one late filing
    assert f["gst_turnover_volatility"] == 0 and f["gst_growth_trend"] == 0


def test_gst_december_period_due_date_rolls_year():
    f = gst_features({"returns": [{"period": "2025-12", "turnover": 10, "filed_on": "2026-01-20"}]})
    assert f["gst_filing_consistency"] == 1.0


def test_mandi_features():
    def r(d, crop, delay):
        dd = date.fromisoformat(d)
        return {"date": d, "crop": crop, "quantity": 10, "rate": 100, "settlement_amount": 1000, "settlement_date": (dd + timedelta(days=delay)).isoformat()}

    rec = [r("2025-11-01", "wheat", 3), r("2025-11-10", "gram", 5), r("2026-05-01", "wheat", 10)]
    f = mandi_features({"receipts": rec}, AS_OF)
    assert f["mandi_distinct_cycles"] == 2
    assert f["mandi_crop_diversity"] == 2
    assert f["mandi_avg_settlement_delay"] == pytest.approx(6.0)
    assert f["mandi_avg_monthly_settlement"] == pytest.approx(3000 / 24)
    assert f["mandi_settlement_frequency"] == pytest.approx(3 / 24)


def test_affordability_and_availability_flags():
    aa = _aa([20000] * 180, [_tx(5 + 30 * i, 30000, "CREDIT", "UPI") for i in range(6)])
    tel = {"as_of": AS_OF.isoformat(), "sim_start_date": "2020-01-01", "recharges": []}
    f = build_features({"aa": aa, "telecom": tel, "business": None}, 6000, product_sku="USED_CAR")
    assert f["est_monthly_income"] == pytest.approx(30000)
    assert f["emi_to_income_ratio"] == pytest.approx(0.2)
    assert f["product_type_encoded"] == 1 and f["ticket_size"] == 300000
    assert f["n_sources_available"] == 2 and f["data_completeness_score"] == pytest.approx(0.7)
    assert f["src_business_available"] == 0


def test_business_with_no_records_counts_as_unavailable_data():
    f = build_features({"business": {"gst": None, "mandi": None}}, 4200, product_sku="TWO_WHEELER")
    assert f["has_business_records"] == 0 and f["src_business_available"] == 0 and f["n_sources_available"] == 0
