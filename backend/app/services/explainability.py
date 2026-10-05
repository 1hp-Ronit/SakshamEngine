"""SHAP explanations → reason codes. Contributions are expressed in SCORE POINTS so a waterfall adds up to the score.

TreeExplainer runs on the raw LightGBM margin (log-odds of DEFAULT). To speak in terms of the applicant's score:
    points_i = −shap_i · platt_slope · Factor          (positive = pushes the score up / helps)
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import shap

from app.domain.reason_codes import ReasonCatalog, get_catalog
from app.services.scoring import ScoringService



@dataclass
class Explanation:
    base_score: float
    final_score: float
    positive: list[dict[str, Any]] = field(default_factory=list)
    negative: list[dict[str, Any]] = field(default_factory=list)
    waterfall: list[dict[str, Any]] = field(default_factory=list)  # top items + "other"
    all_points: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"base_score": self.base_score, "final_score": self.final_score, "positive": self.positive, "negative": self.negative, "waterfall": self.waterfall}


class Explainer:
    def __init__(self, scoring: ScoringService, catalog: ReasonCatalog | None = None):
        self.scoring = scoring
        self.catalog = catalog or get_catalog()
        self.tree = shap.TreeExplainer(scoring.model.booster_)
        ev = self.tree.expected_value
        self.expected_margin = float(np.ravel(ev)[-1])

    def explain(self, features: pd.Series, top_n: int = 3, waterfall_n: int = 6) -> Explanation:
        names = self.scoring.schema["features"]
        x = features[names].to_numpy(dtype=float).reshape(1, -1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # shap warns that LightGBM binary output changed shape; handled just below
            sv = self.tree.shap_values(x)
        sv = np.asarray(sv[-1] if isinstance(sv, list) else sv).reshape(-1, len(names))[0]
        factor = self.scoring.scorecard.factor
        slope = self.scoring.platt_slope
        points = -sv * slope * factor
        # score implied by the expected margin → base of the waterfall
        base_pd = float(self.scoring.calibrator.predict_proba(np.array([[self.expected_margin]]))[0, 1])
        base_score = self.scoring.scorecard.offset + factor * math.log((1 - base_pd) / base_pd)

        rows = []
        for name, pts, shap_v in zip(names, points, sv):
            val = float(features[name])
            positive = pts > 0
            rows.append({
                "feature": name, "label": self.catalog.label(name), "value": None if math.isnan(val) else round(val, 4),
                "points": round(float(pts), 2), "shap_value": round(float(-shap_v * slope), 4),  # log-odds toward approval
                "reason_code": self.catalog.code_for(name), "reason_text": self.catalog.text(name, positive),
                "reason_texts": self.catalog.texts(name, positive), "positive": bool(positive), "_missing": math.isnan(val),
            })

        # Reason lists: only reportable features that actually have a value (a missing GST feed is not an "action")
        usable = [r for r in rows if self.catalog.reportable(r["feature"]) and not r["_missing"]]
        pos = sorted((r for r in usable if r["points"] > 0), key=lambda r: -r["points"])[:top_n]
        neg = sorted((r for r in usable if r["points"] < 0), key=lambda r: r["points"])[:top_n]

        top = sorted(rows, key=lambda r: -abs(r["points"]))[:waterfall_n]
        other = float(sum(r["points"] for r in rows) - sum(r["points"] for r in top))
        waterfall = [{k: v for k, v in r.items() if k in ("feature", "label", "points", "value", "positive")} for r in top]
        final = base_score + float(points.sum())
        clean = lambda lst: [{k: v for k, v in r.items() if not k.startswith("_")} for r in lst]  # noqa: E731
        return Explanation(round(base_score, 1), round(final, 1), clean(pos), clean(neg), waterfall + [{"feature": "other", "label": "All other factors", "points": round(other, 2), "value": None, "positive": other > 0}], {r["feature"]: r["points"] for r in rows})


_explainer: Explainer | None = None


def get_explainer() -> Explainer:
    global _explainer
    from app.services.scoring import get_scoring_service

    svc = get_scoring_service()
    if _explainer is None or _explainer.scoring is not svc:
        _explainer = Explainer(svc)
    return _explainer


def reset_explainer() -> None:
    global _explainer
    _explainer = None


