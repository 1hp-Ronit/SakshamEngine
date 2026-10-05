"""Synthetic training data, built at the RAW-PAYLOAD level.

latent creditworthiness → raw source payloads (shared generators) → build_features (the serving code path) → default label.
Feature values are never generated directly. Run: `python -m ml.generate_data` (or `make train`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from app.core.config import get_settings
from app.mock_services import generators as g
from app.services.feature_pipeline import FEATURE_NAMES, build_features

DATA_DIR = Path(__file__).parent / "data"


def make_payloads(i: int, base_seed: int) -> dict:
    """Raw source payloads + request context for synthetic applicant `i` (no features, no label)."""
    pol = get_settings().policy
    seed = base_seed * 1_000_003 + i
    rng = np.random.default_rng([seed, 99])
    prof = g.build_profile(seed)

    mix = pol.ml.product_mix.get(prof.segment) or {"TWO_WHEELER": 1.0}
    sku = str(rng.choice(list(mix), p=np.array(list(mix.values())) / sum(mix.values())))
    product = pol.products[sku]

    as_of = pol.mock.resolve_as_of()
    aa = g.generate_aa_payload(prof, as_of)
    tel = g.generate_telecom_payload(prof, as_of)
    biz = None
    gst, mandi = g.generate_gst_payload(prof, as_of), g.generate_mandi_payload(prof, as_of)
    if gst is not None or mandi is not None:
        biz = {"gst": gst, "mandi": mandi}
    # Random source loss (outage / not consented), independent of the label
    drop = pol.ml.drop_source_prob
    if rng.random() < drop:
        aa = None
    if rng.random() < drop:
        tel = None
    if rng.random() < drop:
        biz = None
    return {"seed": seed, "profile": prof, "sku": sku, "emi": product.monthly_emi, "ticket": product.ticket,
            "raw": {"aa": aa, "telecom": tel, "business": biz}, "rng": rng}


def _make_row(i: int, base_seed: int) -> dict:
    pol = get_settings().policy
    ctx = make_payloads(i, base_seed)
    prof, rng = ctx["profile"], ctx["rng"]
    # The ONLY feature code path — identical to live inference.
    feats = build_features(ctx["raw"], ctx["emi"], product_sku=ctx["sku"], ticket_size=ctx["ticket"])

    lab = pol.ml.label
    burden = ctx["emi"] / max(prof.monthly_income, 1.0)
    core = (
        lab.cw_slope * (0.5 - prof.cw)
        + lab.burden_slope * (burden - 0.25)
        + lab.interaction * (1 - prof.cw) * max(0.0, burden - 0.30)
        + rng.normal(0, lab.noise_sd)
    )
    row = feats.to_dict()
    row.update({"_seed": ctx["seed"], "_segment": prof.segment, "_cw": prof.cw, "_product": ctx["sku"], "_core": float(core)})
    return row


def generate(n: int | None = None, seed: int | None = None, n_jobs: int = -1) -> pd.DataFrame:
    pol = get_settings().policy
    n = n or pol.ml.n_applicants
    seed = seed if seed is not None else pol.ml.seed
    # Workers inherit these at spawn: single-threaded BLAS per worker avoids heavy oversubscription.
    saved = {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}
    for k in saved:
        os.environ[k] = "1"
    try:
        rows = Parallel(n_jobs=n_jobs, batch_size=256)(delayed(_make_row)(i, seed) for i in range(n))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    df = pd.DataFrame(rows)

    # Calibrate the intercept so the average default rate hits the target, then draw labels reproducibly.
    target = pol.ml.target_default_rate
    lo, hi = -10.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if (1 / (1 + np.exp(-(mid + df["_core"])))).mean() > target:
            hi = mid
        else:
            lo = mid
    df["_p_default"] = 1 / (1 + np.exp(-(lo + df["_core"])))
    df["default"] = (np.random.default_rng(seed).random(len(df)) < df["_p_default"]).astype(int)
    return df


def load_or_generate(force: bool = False) -> pd.DataFrame:
    path = DATA_DIR / "training_data.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)
    df = generate()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return df


if __name__ == "__main__":
    df = load_or_generate(force="--force" in sys.argv)
    print(f"{len(df)} applicants · default rate {df['default'].mean():.3f} · features {len(FEATURE_NAMES)}")
    print(df.groupby("_segment")["default"].agg(["count", "mean"]))
