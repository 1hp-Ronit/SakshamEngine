"""PD ↔ score. Standard scorecard scaling (not a linear PD×600 mapping):

    odds_good = (1 − PD) / PD        Score = Offset + Factor · ln(odds_good)        Factor = PDO / ln 2
"""
from __future__ import annotations

import math

from app.core.config import ScorecardPolicy

_EPS = 1e-6


class Scorecard:
    def __init__(self, policy: ScorecardPolicy):
        self.p = policy
        self.factor = policy.factor
        self.offset = policy.resolved_offset

    def pd_to_score(self, pd: float) -> float:
        pd = min(max(pd, _EPS), 1 - _EPS)
        score = self.offset + self.factor * math.log((1 - pd) / pd)
        return min(max(score, self.p.min_score), self.p.max_score)

    def score_to_pd(self, score: float) -> float:
        odds = math.exp((score - self.offset) / self.factor)
        return 1 / (1 + odds)
