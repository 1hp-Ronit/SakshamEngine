"""Train LightGBM (monotone-constrained) → Platt-calibrate → evaluate → write artifacts + report.md.

Run: `python -m ml.train` (or `make train`). Artifacts land in ml/artifacts/.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.domain.scorecard import Scorecard
from ml.generate_data import load_or_generate
from app.services.feature_pipeline import FEATURE_NAMES, MONOTONE_CONSTRAINTS

ARTIFACTS = Path(__file__).parent / "artifacts"

PARAMS = dict(
    n_estimators=800, learning_rate=0.03, num_leaves=15, min_child_samples=60, subsample=0.8, subsample_freq=1,
    colsample_bytree=0.8, reg_lambda=5.0, monotone_constraints=MONOTONE_CONSTRAINTS, monotone_constraints_method="advanced",
    objective="binary", verbose=-1,
)


def ks_stat(y: np.ndarray, p: np.ndarray) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def main(force_data: bool = False) -> None:
    s = get_settings()
    pol = s.policy
    df = load_or_generate(force=force_data)
    df = df[df["n_sources_available"] >= pol.decision.min_sources_for_scoring].reset_index(drop=True)  # near-empty vectors are never scored
    X, y = df[FEATURE_NAMES], df["default"].to_numpy()

    split = pol.ml.split
    seed = pol.ml.seed
    X_tr, X_tmp, y_tr, y_tmp, seg_tr, seg_tmp = train_test_split(X, y, df["_segment"], test_size=1 - split["train"], stratify=y, random_state=seed)
    rel_test = split["test"] / (split["val"] + split["test"])
    X_val, X_te, y_val, y_te, seg_val, seg_te = train_test_split(X_tmp, y_tmp, seg_tmp, test_size=rel_test, stratify=y_tmp, random_state=seed)

    model = lgb.LGBMClassifier(random_state=seed, **PARAMS)
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], eval_metric="auc", callbacks=[lgb.early_stopping(50, verbose=False)])

    # Platt scaling on held-out raw scores (margins)
    m_val = model.predict(X_val, raw_score=True).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e6).fit(m_val, y_val)
    m_te = model.predict(X_te, raw_score=True).reshape(-1, 1)
    p_te = calibrator.predict_proba(m_te)[:, 1]
    p_raw_te = model.predict_proba(X_te)[:, 1]

    sc = Scorecard(pol.scorecard)
    version = f"v1-lgbm-{datetime.now():%Y%m%d}"
    metrics = {
        "auc": float(roc_auc_score(y_te, p_te)), "ks": ks_stat(y_te, p_te), "brier": float(brier_score_loss(y_te, p_te)),
        "brier_uncalibrated": float(brier_score_loss(y_te, p_raw_te)), "default_rate_test": float(y_te.mean()),
        "n_train": int(len(X_tr)), "n_val": int(len(X_val)), "n_test": int(len(X_te)), "best_iteration": int(model.best_iteration_ or PARAMS["n_estimators"]),
    }
    per_segment = {}
    for seg in sorted(set(seg_te)):
        mask = (seg_te == seg).to_numpy()
        if mask.sum() > 50 and 0 < y_te[mask].sum() < mask.sum():
            per_segment[seg] = {"n": int(mask.sum()), "default_rate": float(y_te[mask].mean()), "auc": float(roc_auc_score(y_te[mask], p_te[mask]))}
    # Partial-data slices
    partial = {}
    for name, mask in {
        "AA missing": X_te["src_aa_available"] == 0, "Telecom missing": X_te["src_telecom_available"] == 0,
        "No business records": X_te["src_business_available"] == 0, "All 3 sources": X_te["n_sources_available"] == 3,
    }.items():
        m = mask.to_numpy()
        if m.sum() > 50 and 0 < y_te[m].sum() < m.sum():
            partial[name] = {"n": int(m.sum()), "auc": float(roc_auc_score(y_te[m], p_te[m]))}

    # Calibration table (deciles of predicted PD)
    cal = pd.DataFrame({"p": p_te, "y": y_te})
    cal["bin"] = pd.qcut(cal["p"], 10, duplicates="drop")
    cal_tbl = cal.groupby("bin", observed=True).agg(mean_pred=("p", "mean"), observed=("y", "mean"), n=("y", "size")).reset_index(drop=True)

    scores = np.array([sc.pd_to_score(p) for p in p_te])
    approve_rate = float((scores >= pol.decision.approve_cutoff).mean())
    importance = pd.Series(model.booster_.feature_importance("gain"), index=FEATURE_NAMES).sort_values(ascending=False)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACTS / "model.joblib")
    joblib.dump(calibrator, ARTIFACTS / "calibrator.joblib")
    schema = {
        "model_version": version, "trained_at": datetime.now().isoformat(timespec="seconds"), "features": FEATURE_NAMES,
        "monotone_constraints": MONOTONE_CONSTRAINTS, "feature_policy": pol.features.model_dump(),
        "calibration": {"coef": float(calibrator.coef_[0][0]), "intercept": float(calibrator.intercept_[0])},
        "scorecard": {"pdo": sc.p.pdo, "offset": sc.offset, "factor": sc.factor},
        "metrics": metrics, "synthetic": True,
    }
    (ARTIFACTS / "feature_schema.json").write_text(json.dumps(schema, indent=2))
    write_report(version, metrics, per_segment, partial, cal_tbl, sc, importance, approve_rate, pol)
    print(f"model {version}: AUC={metrics['auc']:.3f} KS={metrics['ks']:.3f} Brier={metrics['brier']:.4f} approve-rate@{pol.decision.approve_cutoff:.0f}={approve_rate:.1%}")
    print("per segment AUC:", {k: round(v["auc"], 3) for k, v in per_segment.items()})


def write_report(version, metrics, per_segment, partial, cal_tbl, sc: Scorecard, importance, approve_rate, pol) -> None:
    L = [f"# Saksham Engine — Model Report ({version})", "",
         "> ⚠️ **Trained on synthetic data.** Production would start in shadow mode on real repayment outcomes.", "",
         "## Headline metrics (held-out test set)", "",
         "| Metric | Value |", "|---|---|",
         f"| AUC | {metrics['auc']:.3f} |", f"| KS | {metrics['ks']:.3f} |", f"| Brier (calibrated) | {metrics['brier']:.4f} |",
         f"| Brier (uncalibrated) | {metrics['brier_uncalibrated']:.4f} |", f"| Test default rate | {metrics['default_rate_test']:.1%} |",
         f"| Rows (train / val / test) | {metrics['n_train']} / {metrics['n_val']} / {metrics['n_test']} |",
         f"| Boosting rounds (early stopping) | {metrics['best_iteration']} |",
         f"| Approval rate at cutoff {pol.decision.approve_cutoff:.0f} | {approve_rate:.1%} |", "",
         "## AUC per segment", "", "| Segment | n | default rate | AUC |", "|---|---|---|---|"]
    L += [f"| {k} | {v['n']} | {v['default_rate']:.1%} | {v['auc']:.3f} |" for k, v in per_segment.items()]
    L += ["", "## AUC on partial-data slices", "", "| Slice | n | AUC |", "|---|---|---|"]
    L += [f"| {k} | {v['n']} | {v['auc']:.3f} |" for k, v in partial.items()]
    L += ["", "## Calibration (deciles of predicted PD)", "", "| Predicted PD | Observed default rate | n |", "|---|---|---|"]
    L += [f"| {r.mean_pred:.3f} | {r.observed:.3f} | {r.n} |" for r in cal_tbl.itertuples()]
    L += ["", "## Score ↔ PD lookup", "",
          f"`Score = Offset + Factor · ln((1−PD)/PD)`, PDO = {sc.p.pdo:g}, Factor = {sc.factor:.3f}, Offset = {sc.offset:.3f} "
          f"(anchored so score {sc.p.target_score:g} ↔ PD {sc.p.target_pd:.0%}); clamped to [{sc.p.min_score:g}, {sc.p.max_score:g}].", "",
          "| Score | PD |", "|---|---|"]
    L += [f"| {sc_} | {sc.score_to_pd(sc_):.2%} |" for sc_ in range(300, 901, 50)]
    L += ["", f"Check: score {sc.p.target_score:g} → PD {sc.score_to_pd(sc.p.target_score):.2%}; PD {sc.p.target_pd:.0%} → score {sc.pd_to_score(sc.p.target_pd):.1f}.", "",
          "## Top features (gain)", "", "| Feature | Gain |", "|---|---|"]
    L += [f"| {k} | {v:,.0f} |" for k, v in importance.head(15).items()]
    (ARTIFACTS / "report.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main(force_data="--force-data" in sys.argv)
