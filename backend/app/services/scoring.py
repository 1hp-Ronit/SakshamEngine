"""Load the trained model + Platt calibrator, predict PD, map to score."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.domain.scorecard import Scorecard

log = get_logger("scoring")


@dataclass
class ScoreResult:
    raw_margin: float
    pd: float
    score: float
    latency_ms: float


class ScoringService:
    def __init__(self, artifacts_dir: str | Path):
        self.dir = Path(artifacts_dir)
        self.model = None
        self.calibrator = None
        self.schema: dict = {}
        self.scorecard = Scorecard(get_settings().policy.scorecard)

    @property
    def loaded(self) -> bool:
        return self.model is not None

    @property
    def model_version(self) -> str:
        return self.schema.get("model_version", "untrained")

    @property
    def platt_slope(self) -> float:
        return float(self.calibrator.coef_[0][0])

    def load(self) -> "ScoringService":
        files = [self.dir / n for n in ("model.joblib", "calibrator.joblib", "feature_schema.json")]
        missing = [f.name for f in files if not f.exists()]
        if missing:
            raise AppError("MODEL_NOT_TRAINED", f"Model artifacts missing ({', '.join(missing)}). Run `make train`.", 503)
        self.model = joblib.load(files[0])
        self.calibrator = joblib.load(files[1])
        self.schema = json.loads(files[2].read_text())
        trained_with = self.schema.get("feature_policy")
        current = get_settings().policy.features.model_dump()
        if trained_with and trained_with != current:
            log.warning("features: section of policy.yaml differs from the one the model was trained with — re-run `make train`")
        return self

    def predict(self, features: pd.Series) -> ScoreResult:
        if not self.loaded:
            self.load()
        t0 = time.perf_counter()
        x = features[self.schema["features"]].to_numpy(dtype=float).reshape(1, -1)
        margin = float(self.model.booster_.predict(x, raw_score=True)[0])
        pd_cal = float(self.calibrator.predict_proba(np.array([[margin]]))[0, 1])
        return ScoreResult(margin, pd_cal, self.scorecard.pd_to_score(pd_cal), (time.perf_counter() - t0) * 1000)


_service: ScoringService | None = None


def get_scoring_service() -> ScoringService:
    global _service
    if _service is None:
        _service = ScoringService(get_settings().env.ml_artifacts_dir)
    if not _service.loaded:
        _service.load()
    return _service


def reset_scoring_service() -> None:
    global _service
    _service = None
