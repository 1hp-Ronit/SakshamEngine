"""Shared raw-payload generators.

Used by BOTH the /mock/* HTTP services (live demo personas) and ml/generate_data.py (training), so the
model is trained on exactly the payload shapes it sees at inference. Pure functions: no I/O, no settings.

Everything is a deterministic function of (profile, as_of). A `Profile` carries a latent creditworthiness
`cw` in [0, 1] (higher = safer) and a latent true monthly income; payload statistics depend on them plus noise.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

import numpy as np

SEGMENTS = ("merchant", "gig", "farmer", "salaried")
SEGMENT_WEIGHTS = {"merchant": 0.32, "gig": 0.30, "farmer": 0.30, "salaried": 0.08}

# (median monthly income ₹, lognormal sigma)
INCOME_BY_SEGMENT = {"merchant": (45000, 0.35), "gig": (21000, 0.30), "farmer": (42000, 0.40), "salaried": (32000, 0.30)}
# Share of true income that flows through the bank account
AA_CAPTURE = {"merchant": 0.80, "gig": 0.92, "farmer": 0.35, "salaried": 1.0}
# Mean inflow transactions / month at full density
INFLOW_COUNT = {"merchant": 26, "gig": 38, "farmer": 5, "salaried": 5}
# P(mode) for inflows: UPI, CASH, NEFT, IMPS
INFLOW_MODES = {
    "gig": (0.78, 0.10, 0.05, 0.07),
    "merchant": (0.55, 0.20, 0.15, 0.10),
    "farmer": (0.15, 0.40, 0.30, 0.15),
    "salaried": (0.12, 0.00, 0.85, 0.03),
}
CROPS = {"wheat": 2275, "soybean": 4600, "cotton": 7000, "onion": 1800, "tur": 7550, "sugarcane": 340, "gram": 5440}
PLAN_CATALOG = [(19, "TOPUP"), (49, "TOPUP"), (149, "MONTHLY"), (199, "MONTHLY"), (239, "MONTHLY"), (299, "MONTHLY"), (399, "MONTHLY"), (599, "QUARTERLY")]


@dataclass(frozen=True)
class Profile:
    seed: int
    segment: str
    cw: float  # latent creditworthiness
    monthly_income: float  # latent true monthly income (₹)
    has_aa: bool = True
    has_telecom: bool = True
    has_gst: bool = False
    has_mandi: bool = False
    aa_sparsity: float = 1.0  # 1.0 = dense bank usage; <1 = sparse (few transactions)


def seed_from_hash(h: str) -> int:
    """Deterministic integer seed from a (hex) mobile hash."""
    return int(hashlib.sha256(h.encode()).hexdigest()[:8], 16)


def _rng(seed: int, stream: int) -> np.random.Generator:
    return np.random.default_rng([int(seed) & 0xFFFFFFFF, stream])


def build_profile(seed: int, segment: str | None = None, cw: float | None = None, monthly_income: float | None = None) -> Profile:
    rng = _rng(seed, 0)
    if segment is None:
        segment = str(rng.choice(list(SEGMENT_WEIGHTS), p=list(SEGMENT_WEIGHTS.values())))
    if cw is None:
        cw = float(rng.beta(2.0, 2.4))
    median, sigma = INCOME_BY_SEGMENT[segment]
    if monthly_income is None:
        monthly_income = float(median * rng.lognormal(0, sigma) * (0.75 + 0.5 * cw))
    has_aa = bool(rng.random() < (0.88 if segment == "farmer" else 0.97))
    has_telecom = bool(rng.random() < 0.97)
    has_gst = segment == "merchant" and bool(rng.random() < 0.90)
    has_mandi = segment == "farmer" and bool(rng.random() < 0.90)
    if segment == "farmer":
        sparsity = float(rng.uniform(0.25, 0.6))
    elif segment == "merchant":
        sparsity = 1.0 if rng.random() < 0.8 else float(rng.uniform(0.4, 0.7))
    else:
        sparsity = 1.0 if rng.random() < 0.9 else float(rng.uniform(0.4, 0.7))
    return Profile(seed, segment, float(np.clip(cw, 0.0, 1.0)), monthly_income, has_aa, has_telecom, has_gst, has_mandi, sparsity)


def with_availability(p: Profile, **kw: Any) -> Profile:
    return replace(p, **kw)


# ───────────────────────── AA bank statement ─────────────────────────
_MODES = ("UPI", "CASH", "NEFT", "IMPS")


def _mode_cdf(segment: str, cw: float) -> list[float]:
    upi, cash, neft, imps = INFLOW_MODES[segment]
    cash *= 1.5 - cw  # safer applicants lean digital
    tot = upi + cash + neft + imps
    c, acc = [], 0.0
    for x in (upi, cash, neft, imps):
        acc += x / tot
        c.append(acc)
    return c


def _choose_mode(rng: np.random.Generator, cdf: list[float]) -> str:
    r = rng.random()
    for mode, edge in zip(_MODES, cdf):
        if r < edge:
            return mode
    return _MODES[-1]


def generate_aa_payload(p: Profile, as_of: date, days: int = 180) -> dict[str, Any] | None:
    """180 days of balances + transactions. UPI activity appears only as `mode == "UPI"` transactions."""
    if not p.has_aa:
        return None
    rng = _rng(p.seed, 1)
    cw, seg = p.cw, p.segment
    start = as_of - timedelta(days=days - 1)
    capture = AA_CAPTURE[seg] * min(1.0, 0.35 + p.aa_sparsity)  # sparse accounts see less of the income
    n_months = days // 30 + 1

    # Counterparty pools: more distinct payers for safer applicants and busy segments
    pool_scale = {"merchant": 1.0, "gig": 0.55, "farmer": 0.25, "salaried": 0.1}[seg]
    n_payers = max(2, int((4 + 70 * cw) * pool_scale * p.aa_sparsity))
    payers = [f"UPI/{rng.integers(10**5, 10**6)}@ok{rng.choice(['hdfc', 'sbi', 'axis', 'icici'])}" for _ in range(n_payers)]
    payees = [f"UPI/SHOP{i:03d}@pay" for i in range(40)]

    events: dict[int, list[tuple[str, float, str, str]]] = {}  # day index → [(kind, amount, mode, narration)]

    def add(day: int, kind: str, amount: float, mode: str, narration: str) -> None:
        if 0 <= day < days and amount >= 1:
            events.setdefault(day, []).append((kind, float(round(amount, 2)), mode, narration))

    inc = p.monthly_income
    mode_cdf = _mode_cdf(seg, cw)
    month_totals = []
    has_recurring = seg == "salaried" or rng.random() < 0.22 * cw
    for m in range(n_months):
        factor = float(np.clip(1 + (1.15 - cw) * 0.5 * rng.normal(), 0.2, 2.2))
        total = inc * capture * factor
        month_totals.append(total)
        base = m * 30
        remaining = total
        if has_recurring:
            sal_day = int(np.clip(base + 2 + rng.normal(0, 0.5 + 3 * (1 - cw)), base, base + 28))
            if rng.random() > 0.3 * (1 - cw):  # safer people rarely miss the monthly credit
                sal = total * (0.55 if seg != "salaried" else 0.95) * rng.uniform(0.97, 1.03)
                add(sal_day, "CREDIT", sal, "NEFT", "NEFT-EMPLOYER-SALARY" if seg == "salaried" else "NEFT-DISTRIBUTOR-SETTLEMENT")
                remaining -= sal
        n_in = max(1, int(rng.poisson(INFLOW_COUNT[seg] * p.aa_sparsity * (0.6 + 0.8 * cw))))
        weights = rng.lognormal(0, 0.7, n_in)
        weights /= weights.sum()
        for w in weights:
            mode = _choose_mode(rng, mode_cdf)
            narr = {"UPI": str(rng.choice(payers)), "CASH": "CASH DEPOSIT", "NEFT": "NEFT-CR-CUSTOMER", "IMPS": "IMPS-CR-CUSTOMER"}[mode]
            add(base + int(rng.integers(0, 30)), "CREDIT", max(remaining, 0) * w, mode, narr)

    # Outflows: spending ratio rises as creditworthiness falls
    for m in range(n_months):
        ratio = float(np.clip(0.68 + 0.42 * (1 - cw) + rng.normal(0, 0.06), 0.5, 1.4))
        out_total = month_totals[m] * ratio
        n_out = int(rng.integers(14, 30))
        w = rng.lognormal(0, 0.8, n_out)
        w /= w.sum()
        for x in w:
            r = rng.random()
            mode, narr = ("UPI", str(rng.choice(payees))) if r < 0.6 else (("ATM", "ATM CASH WDL") if r < 0.85 else ("OTHER", "BILL PAYMENT"))
            add(m * 30 + int(rng.integers(0, 30)), "DEBIT", out_total * x, mode, narr)

    # Mandates (existing EMIs / insurance): the source of ECS_RETURN bounces
    mandates = []
    if rng.random() < 0.9:
        mandates.append((int(rng.integers(3, 8)), inc * rng.uniform(0.08, 0.2)))
    if rng.random() < 0.35:
        mandates.append((int(rng.integers(10, 20)), inc * rng.uniform(0.03, 0.08)))
    bounce_p = 0.62 * (1 - cw) ** 1.6

    balance = float(inc * (0.12 + 1.5 * cw) * rng.lognormal(0, 0.3))
    txns: list[dict[str, Any]] = []
    balances: list[dict[str, Any]] = []
    for d in range(days):
        day_date = start + timedelta(days=d)
        todays = events.get(d, [])
        for kind, amt, mode, narr in sorted(todays, key=lambda e: 0 if e[0] == "CREDIT" else 1):
            if kind == "CREDIT":
                balance += amt
            else:
                amt = min(amt, balance)  # no overdraft
                if amt < 1:
                    continue
                balance -= amt
            txns.append({"date": day_date.isoformat(), "amount": round(amt, 2), "type": kind, "mode": mode, "narration": narr, "balance": round(balance, 2)})
        dom = d % 30 + 1
        for due_day, emi in mandates:
            if dom == due_day and d >= 3:
                if rng.random() < bounce_p or balance < emi:
                    charge = min(balance, 400.0)
                    balance -= charge
                    txns.append({"date": day_date.isoformat(), "amount": round(charge, 2), "type": "DEBIT", "mode": "ECS_RETURN",
                                 "narration": "ECS RETURN - INSUFFICIENT FUNDS CHARGES", "balance": round(balance, 2)})
                else:
                    balance -= emi
                    txns.append({"date": day_date.isoformat(), "amount": round(emi, 2), "type": "DEBIT", "mode": "OTHER",
                                 "narration": "ECS DEBIT - LOAN EMI", "balance": round(balance, 2)})
        balances.append({"date": day_date.isoformat(), "balance": round(balance, 2)})

    return {
        "as_of": as_of.isoformat(),
        "account": {"type": "SAVINGS", "bank": "MOCK BANK", "currency": "INR", "from": start.isoformat(), "to": as_of.isoformat()},
        "balances": balances,
        "transactions": txns,
    }


# ───────────────────────── Telecom ─────────────────────────
def generate_telecom_payload(p: Profile, as_of: date) -> dict[str, Any] | None:
    if not p.has_telecom:
        return None
    rng = _rng(p.seed, 2)
    cw = p.cw
    tenure_months = int(np.clip(4 + 100 * cw * rng.uniform(0.3, 1.2) + rng.normal(0, 6), 2, 150))
    sim_start = as_of - timedelta(days=tenure_months * 30)
    window_start = as_of - timedelta(days=365)

    value_scale = np.clip(p.monthly_income / 30000, 0.5, 2.0)
    monthly_choices = [(a, t) for a, t in PLAN_CATALOG if t == "MONTHLY"]
    pref = monthly_choices[int(np.clip(round((len(monthly_choices) - 1) * min(1.0, 0.25 + 0.5 * value_scale * (0.5 + cw) / 1.5)), 0, len(monthly_choices) - 1))]

    recharges = []
    cursor = window_start + timedelta(days=int(rng.integers(0, 20)))
    first = max(window_start, sim_start)
    cursor = max(cursor, first)
    erratic = 1 - cw
    while cursor <= as_of:
        if rng.random() < 0.25 * erratic ** 1.3:  # small ad-hoc top-up instead of a proper plan
            amount, plan = [(19, "TOPUP"), (49, "TOPUP")][int(rng.integers(0, 2))]
        else:
            amount, plan = pref
            if rng.random() < 0.15:
                amount, plan = monthly_choices[int(rng.integers(0, len(monthly_choices)))]
        recharges.append({"date": cursor.isoformat(), "amount": amount, "plan_type": plan})
        valid_days = {"TOPUP": 7, "MONTHLY": 28, "QUARTERLY": 84}[plan]
        gap = valid_days + abs(rng.normal(0, 1 + 6 * erratic)) + (rng.exponential(18 * erratic ** 1.5) if rng.random() < 0.5 * erratic else 0)
        cursor += timedelta(days=max(1, int(round(gap))))
    return {"as_of": as_of.isoformat(), "sim_start_date": sim_start.isoformat(), "recharges": recharges}


# ───────────────────────── GST (merchants) ─────────────────────────
def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + months, 12)
    return date(y, m + 1, 1)


def generate_gst_payload(p: Profile, as_of: date, months: int = 12) -> dict[str, Any] | None:
    if not p.has_gst:
        return None
    rng = _rng(p.seed, 3)
    cw = p.cw
    base = p.monthly_income / 0.18 * rng.uniform(0.8, 1.2)
    growth = (cw - 0.4) * 0.05
    vol = 0.06 + 0.45 * (1 - cw)
    first_of_this_month = date(as_of.year, as_of.month, 1)
    returns = []
    for i in range(months, 0, -1):
        period_start = _add_months(first_of_this_month, -i)
        if rng.random() < 0.28 * (1 - cw) ** 1.5:  # unfiled month
            continue
        turnover = base * (1 + growth) ** (months - i) * rng.lognormal(0, vol)
        due = _add_months(period_start, 1) + timedelta(days=19)  # 20th of next month
        delay = int(rng.poisson(10 * (1 - cw) ** 1.5)) - int(rng.integers(0, 6))
        filed = due + timedelta(days=delay)
        if filed > as_of:  # not filed yet as of the payload date
            continue
        returns.append({"period": period_start.strftime("%Y-%m"), "turnover": round(float(turnover), 2), "filed_on": filed.isoformat()})
    gstin = "27" + hashlib.sha256(str(p.seed).encode()).hexdigest()[:10].upper() + "1Z5"
    return {"as_of": as_of.isoformat(), "gstin_token": gstin, "returns": returns}


# ───────────────────────── Mandi (farmers) ─────────────────────────
def generate_mandi_payload(p: Profile, as_of: date, months: int = 24) -> dict[str, Any] | None:
    if not p.has_mandi:
        return None
    rng = _rng(p.seed, 4)
    cw = p.cw
    cycles_per_year = 1.0 + 3.0 * cw + rng.uniform(-0.3, 0.6)
    n_cycles = max(1, int(round(cycles_per_year * months / 12)))
    n_crops = 1 + int(round(2.5 * cw * rng.uniform(0.5, 1.3)))
    crops = list(rng.choice(list(CROPS), size=min(n_crops, len(CROPS)), replace=False))
    capture = 0.45 + 0.5 * cw
    per_cycle_total = p.monthly_income * 12 / max(cycles_per_year, 0.5) * capture
    window_start = as_of - timedelta(days=int(months * 30.4))
    cycle_centres = sorted(window_start + timedelta(days=int(x)) for x in rng.uniform(10, months * 30.4 - 10, n_cycles))
    receipts = []
    for centre in cycle_centres:
        n_r = int(rng.integers(2, 6))
        weights = rng.dirichlet(np.ones(n_r))
        for w in weights:
            crop = str(rng.choice(crops))
            rate = CROPS[crop] * rng.lognormal(0, 0.08)  # ₹ per quintal
            gross = per_cycle_total * w * rng.uniform(0.85, 1.15)
            qty = gross / rate
            day = centre + timedelta(days=int(rng.integers(0, 20)))
            if day > as_of:
                continue
            delay = int(round(2 + (1 - cw) * 22 * rng.exponential(1.0) * 0.6 + rng.integers(0, 3)))
            receipts.append({
                "date": day.isoformat(), "crop": crop, "quantity": round(float(qty), 2), "rate": round(float(rate), 2),
                "settlement_amount": round(float(qty * rate * 0.975), 2), "settlement_date": (day + timedelta(days=delay)).isoformat(),
            })
    receipts.sort(key=lambda r: r["date"])
    return {"as_of": as_of.isoformat(), "receipts": receipts}


# ───────────────────────── Bureau ─────────────────────────
def generate_bureau_result(seed: int, hit_probability: float = 0.0) -> dict[str, Any]:
    """Derived bureau response for numbers that are not configured personas (default: always NO_HIT)."""
    rng = _rng(seed, 5)
    if rng.random() < hit_probability:
        return {"status": "HIT", "score": int(rng.integers(540, 830))}
    return {"status": "NO_HIT", "score": -1}
