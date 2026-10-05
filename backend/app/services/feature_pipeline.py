"""The ONE code path that turns raw source payloads into model input.

Training (ml/generate_data.py), tests and live inference all call `build_features`. Never add a second path.
One function per source group; every feature is a float, NaN when the source is absent or has no data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import FeaturePolicy, get_settings

NAN = float("nan")
BLOCK_DAYS = 30  # "months" are 30-day blocks counted back from as_of → stable regardless of calendar
MANDI_WINDOW_MONTHS = 24


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    group: str  # aa | telecom | gst | mandi | affordability | flags
    monotone: int  # on P(default): +1 ↑ feature → ↑ risk, -1 ↑ feature → ↓ risk, 0 unconstrained


_SPECS: list[tuple[str, str, int]] = [
    # Bank statement / AA
    ("buffer_ratio", "aa", -1), ("bounce_velocity", "aa", +1), ("income_regularity", "aa", -1), ("monthly_inflow_count", "aa", -1),
    ("distinct_upi_counterparties", "aa", -1), ("cash_vs_digital_ratio", "aa", 0), ("digital_inflow_share", "aa", -1),
    ("min_balance_days", "aa", +1), ("balance_trend", "aa", -1), ("avg_monthly_inflow", "aa", -1), ("max_monthly_outflow", "aa", 0),
    ("salary_regularity", "aa", -1), ("upi_txn_frequency", "aa", 0), ("balance_volatility", "aa", +1),
    # Telecom
    ("recharge_frequency_regularity", "telecom", -1), ("recharge_count_12m", "telecom", -1), ("avg_recharge_value", "telecom", -1),
    ("recharge_value_trend", "telecom", -1), ("sim_tenure_months", "telecom", -1), ("max_recharge_gap_days", "telecom", +1),
    # GST
    ("gst_avg_turnover", "gst", -1), ("gst_turnover_volatility", "gst", +1), ("gst_filing_consistency", "gst", -1),
    ("gst_growth_trend", "gst", -1), ("gst_months_filed", "gst", -1),
    # Mandi
    ("mandi_settlement_frequency", "mandi", -1), ("mandi_distinct_cycles", "mandi", -1), ("mandi_avg_monthly_settlement", "mandi", -1),
    ("mandi_avg_settlement_delay", "mandi", +1), ("mandi_crop_diversity", "mandi", -1), ("mandi_tenure_months", "mandi", -1),
    # Affordability / application
    ("requested_emi", "affordability", +1), ("est_monthly_income", "affordability", -1), ("emi_to_income_ratio", "affordability", +1),
    ("product_type_encoded", "affordability", 0), ("ticket_size", "affordability", 0),
    # Availability flags
    ("src_aa_available", "flags", -1), ("src_telecom_available", "flags", -1), ("src_business_available", "flags", 0),
    ("data_completeness_score", "flags", -1), ("n_sources_available", "flags", -1), ("has_business_records", "flags", 0),
]
FEATURE_SPECS = [FeatureSpec(*s) for s in _SPECS]
FEATURE_NAMES = [s.name for s in FEATURE_SPECS]
MONOTONE_CONSTRAINTS = [s.monotone for s in FEATURE_SPECS]


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _cv(x: np.ndarray) -> float:
    m = float(np.mean(x))
    return float(np.std(x) / m) if m > 0 else NAN


def _norm_slope(y: np.ndarray) -> float:
    """Slope per step of a series, as a fraction of its mean."""
    if len(y) < 2 or float(np.mean(y)) <= 0:
        return NAN
    return float(np.polyfit(np.arange(len(y)), y, 1)[0] / np.mean(y))


# ───────────────────────── AA ─────────────────────────
def aa_features(aa: dict[str, Any] | None, as_of: date, emi: float, cfg: FeaturePolicy) -> dict[str, float]:
    names = [s.name for s in FEATURE_SPECS if s.group == "aa"]
    out = dict.fromkeys(names, NAN)
    if not aa or not aa.get("balances"):
        return out
    bal = np.array([b["balance"] for b in aa["balances"]], dtype=float)
    tx = aa.get("transactions", [])
    n_blocks = max(1, len(bal) // BLOCK_DAYS)

    avg_bal = float(np.mean(bal))
    out["buffer_ratio"] = avg_bal / emi if emi > 0 else NAN
    out["min_balance_days"] = float(np.sum(bal < cfg.low_balance_threshold))
    out["balance_volatility"] = float(np.std(bal) / avg_bal) if avg_bal > 0 else 5.0
    # block-wise mean balance, oldest → newest
    blocks = [bal[len(bal) - (i + 1) * BLOCK_DAYS: len(bal) - i * BLOCK_DAYS] for i in range(n_blocks)][::-1]
    out["balance_trend"] = _norm_slope(np.array([b.mean() for b in blocks if len(b)]))

    cutoff = as_of - timedelta(days=cfg.bounce_window_days)
    out["bounce_velocity"] = float(sum(1 for t in tx if t["mode"] == "ECS_RETURN" and _d(t["date"]) > cutoff))

    credits = [t for t in tx if t["type"] == "CREDIT"]
    debits = [t for t in tx if t["type"] == "DEBIT"]
    in_block = np.zeros(n_blocks)
    out_block = np.zeros(n_blocks)
    for t in credits:
        i = (as_of - _d(t["date"])).days // BLOCK_DAYS
        if i < n_blocks:
            in_block[i] += t["amount"]
    for t in debits:
        i = (as_of - _d(t["date"])).days // BLOCK_DAYS
        if i < n_blocks:
            out_block[i] += t["amount"]
    total_in = float(in_block.sum())
    out["avg_monthly_inflow"] = total_in / n_blocks
    out["max_monthly_outflow"] = float(out_block.max())
    cv = _cv(in_block)
    out["income_regularity"] = 0.0 if math.isnan(cv) else float(np.clip(1 - cv, 0, 1))
    out["monthly_inflow_count"] = len(credits) / n_blocks
    upi_credits = [t for t in credits if t["mode"] == "UPI"]
    out["distinct_upi_counterparties"] = float(len({t["narration"] for t in upi_credits}))
    cash = sum(t["amount"] for t in credits if t["mode"] == "CASH")
    digital = sum(t["amount"] for t in credits if t["mode"] in ("UPI", "NEFT", "IMPS"))
    out["cash_vs_digital_ratio"] = cash / total_in if total_in > 0 else NAN
    out["digital_inflow_share"] = digital / total_in if total_in > 0 else NAN
    out["upi_txn_frequency"] = sum(1 for t in tx if t["mode"] == "UPI") / n_blocks

    # Regular large recurring credits: share of blocks with a large credit × timing consistency of the largest one
    avg_in = total_in / n_blocks
    large_threshold = 0.25 * avg_in
    days_of_largest, with_large = [], 0
    for b in range(n_blocks):
        in_b = [t for t in credits if (as_of - _d(t["date"])).days // BLOCK_DAYS == b and t["amount"] >= large_threshold > 0]
        if in_b:
            with_large += 1
            top = max(in_b, key=lambda t: t["amount"])
            days_of_largest.append((as_of - _d(top["date"])).days % BLOCK_DAYS)
    if with_large:
        timing = 1 - min(1.0, float(np.std(days_of_largest)) / 15) if len(days_of_largest) > 1 else 0.5
        out["salary_regularity"] = (with_large / n_blocks) * timing
    else:
        out["salary_regularity"] = 0.0
    return out


# ───────────────────────── Telecom ─────────────────────────
def telecom_features(tel: dict[str, Any] | None, as_of: date) -> dict[str, float]:
    names = [s.name for s in FEATURE_SPECS if s.group == "telecom"]
    out = dict.fromkeys(names, NAN)
    if not tel:
        return out
    rech = sorted(tel.get("recharges", []), key=lambda r: r["date"])
    out["sim_tenure_months"] = (as_of - _d(tel["sim_start_date"])).days / 30.4 if tel.get("sim_start_date") else NAN
    in_12m = [r for r in rech if (as_of - _d(r["date"])).days <= 365]
    out["recharge_count_12m"] = float(len(in_12m))
    if not rech:
        return out
    amounts = np.array([r["amount"] for r in rech], dtype=float)
    out["avg_recharge_value"] = float(amounts.mean())
    if len(amounts) >= 4:
        half = len(amounts) // 2
        out["recharge_value_trend"] = float((amounts[half:].mean() - amounts[:half].mean()) / amounts.mean())
    dates = [_d(r["date"]) for r in rech]
    gaps = np.array([(b - a).days for a, b in zip(dates, dates[1:])], dtype=float)
    open_gap = float((as_of - dates[-1]).days)
    out["max_recharge_gap_days"] = float(max([open_gap, *gaps.tolist()]))
    if len(gaps) >= 2 and gaps.mean() > 0:
        out["recharge_frequency_regularity"] = float(np.clip(1 - gaps.std() / gaps.mean(), 0, 1))
    return out


# ───────────────────────── GST ─────────────────────────
def gst_features(gst: dict[str, Any] | None) -> dict[str, float]:
    names = [s.name for s in FEATURE_SPECS if s.group == "gst"]
    out = dict.fromkeys(names, NAN)
    if not gst or not gst.get("returns"):
        return out
    rets = sorted(gst["returns"], key=lambda r: r["period"])
    turn = np.array([r["turnover"] for r in rets], dtype=float)
    out["gst_months_filed"] = float(len(rets))
    out["gst_avg_turnover"] = float(turn.mean())
    if len(turn) >= 3:
        pct = np.diff(turn) / np.maximum(turn[:-1], 1.0)
        out["gst_turnover_volatility"] = float(pct.std())
    if len(turn) >= 4:
        half = len(turn) // 2
        out["gst_growth_trend"] = float((turn[half:].mean() - turn[:half].mean()) / max(turn.mean(), 1.0))
    on_time = 0
    for r in rets:
        y, m = int(r["period"][:4]), int(r["period"][5:7])
        nxt = date(y + (m // 12), m % 12 + 1, 20)  # due: 20th of the following month
        on_time += _d(r["filed_on"]) <= nxt
    out["gst_filing_consistency"] = on_time / len(rets)
    return out


# ───────────────────────── Mandi ─────────────────────────
def mandi_features(mandi: dict[str, Any] | None, as_of: date) -> dict[str, float]:
    names = [s.name for s in FEATURE_SPECS if s.group == "mandi"]
    out = dict.fromkeys(names, NAN)
    if not mandi or not mandi.get("receipts"):
        return out
    rec = sorted(mandi["receipts"], key=lambda r: r["date"])
    dates = [_d(r["date"]) for r in rec]
    out["mandi_settlement_frequency"] = len(rec) / MANDI_WINDOW_MONTHS
    out["mandi_avg_monthly_settlement"] = sum(r["settlement_amount"] for r in rec) / MANDI_WINDOW_MONTHS
    cycles = 1 + sum(1 for a, b in zip(dates, dates[1:]) if (b - a).days > 45)
    out["mandi_distinct_cycles"] = float(cycles)
    out["mandi_avg_settlement_delay"] = float(np.mean([(_d(r["settlement_date"]) - _d(r["date"])).days for r in rec]))
    out["mandi_crop_diversity"] = float(len({r["crop"] for r in rec}))
    out["mandi_tenure_months"] = (as_of - dates[0]).days / 30.4
    return out


# ───────────────────────── Orchestration ─────────────────────────
def _infer_as_of(payloads: dict[str, Any]) -> date:
    found: list[date] = []

    def walk(p: Any) -> None:
        if isinstance(p, dict):
            if "as_of" in p and isinstance(p["as_of"], str):
                found.append(_d(p["as_of"]))
            for v in p.values():
                if isinstance(v, dict):
                    walk(v)

    walk(payloads)
    return max(found) if found else date.today()


def build_features(
    raw_payloads: dict[str, Any],
    requested_emi: float,
    *,
    product_sku: str | None = None,
    ticket_size: float | None = None,
    cfg: FeaturePolicy | None = None,
) -> pd.Series:
    """raw_payloads = {"aa": {...}|None, "telecom": {...}|None, "business": {"gst": {...}|None, "mandi": {...}|None}|None}
    → one feature row (pd.Series indexed by FEATURE_NAMES, float64)."""
    settings = get_settings()
    cfg = cfg or settings.policy.features
    aa = raw_payloads.get("aa") or None
    tel = raw_payloads.get("telecom") or None
    biz = raw_payloads.get("business") or {}
    gst = biz.get("gst") if isinstance(biz, dict) else None
    mandi = biz.get("mandi") if isinstance(biz, dict) else None
    as_of = _infer_as_of(raw_payloads)

    f: dict[str, float] = {}
    f.update(aa_features(aa, as_of, requested_emi, cfg))
    f.update(telecom_features(tel, as_of))
    f.update(gst_features(gst))
    f.update(mandi_features(mandi, as_of))

    # Affordability
    est: dict[str, float] = {}
    if not math.isnan(f["avg_monthly_inflow"]):
        est["aa"] = f["avg_monthly_inflow"]
    if not math.isnan(f["gst_avg_turnover"]):
        est["gst"] = f["gst_avg_turnover"] * cfg.gst_margin
    if not math.isnan(f["mandi_avg_monthly_settlement"]):
        est["mandi"] = f["mandi_avg_monthly_settlement"] * cfg.mandi_margin
    if est:
        w = {k: cfg.income_blend_weights.get(k, 0.0) for k in est}
        tw = sum(w.values()) or 1.0
        f["est_monthly_income"] = sum(est[k] * w[k] for k in est) / tw
    else:
        f["est_monthly_income"] = NAN
    f["requested_emi"] = float(requested_emi)
    f["emi_to_income_ratio"] = requested_emi / f["est_monthly_income"] if f["est_monthly_income"] and f["est_monthly_income"] > 0 else NAN
    products = list(settings.policy.products)
    f["product_type_encoded"] = float(products.index(product_sku)) if product_sku in products else NAN
    f["ticket_size"] = float(ticket_size) if ticket_size is not None else (settings.policy.products[product_sku].ticket if product_sku in products else NAN)

    # Availability
    has_aa = aa is not None and bool(aa.get("balances"))
    has_tel = tel is not None
    has_gst = gst is not None and bool(gst.get("returns"))
    has_mandi = mandi is not None and bool(mandi.get("receipts"))
    has_biz = bool(biz) and (gst is not None or mandi is not None)
    f["src_aa_available"] = float(has_aa)
    f["src_telecom_available"] = float(has_tel)
    f["src_business_available"] = float(has_biz)
    f["has_business_records"] = float(has_gst or has_mandi)
    f["n_sources_available"] = float(has_aa + has_tel + has_biz)
    f["data_completeness_score"] = 0.45 * has_aa + 0.25 * has_tel + 0.30 * has_biz

    return pd.Series({n: float(f[n]) for n in FEATURE_NAMES}, dtype="float64")
