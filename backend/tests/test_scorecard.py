import math

import pytest

from app.core.config import ScorecardPolicy, get_settings
from app.domain.policy import evaluate_decision
from app.domain.scorecard import Scorecard
from app.domain.state_machine import ApplicationStatus as S
from app.domain.state_machine import can_transition, validate_transition
from app.core.errors import AppError


def test_anchor_650_is_7_percent_pd():
    sc = Scorecard(get_settings().policy.scorecard)
    assert sc.pd_to_score(0.07) == pytest.approx(650, abs=0.01)
    assert sc.score_to_pd(650) == pytest.approx(0.07, abs=1e-6)


def test_pdo_doubles_odds_every_60_points():
    sc = Scorecard(get_settings().policy.scorecard)
    odds = lambda s: (1 - sc.score_to_pd(s)) / sc.score_to_pd(s)  # noqa: E731
    assert odds(710) / odds(650) == pytest.approx(2.0, rel=1e-6)


def test_monotone_and_clamped():
    sc = Scorecard(get_settings().policy.scorecard)
    scores = [sc.pd_to_score(p) for p in (0.0001, 0.01, 0.07, 0.3, 0.9, 0.9999)]
    assert scores == sorted(scores, reverse=True)
    assert sc.pd_to_score(1e-9) == 900 and sc.pd_to_score(1 - 1e-9) == 300


def test_offset_override_is_respected():
    sc = Scorecard(ScorecardPolicy(offset=500.0))
    assert sc.offset == 500.0 and sc.pd_to_score(0.5) == pytest.approx(500.0)


def test_decision_bands():
    pol = get_settings().policy
    assert evaluate_decision(700, 0.04, "TWO_WHEELER", pol).outcome == S.APPROVED
    assert evaluate_decision(650, 0.07, "TWO_WHEELER", pol).outcome == S.APPROVED  # cutoff is inclusive
    cond = evaluate_decision(620, 0.1, "TWO_WHEELER", pol)
    assert cond.outcome == S.CONDITIONAL_APPROVAL and cond.suggested_ticket == pytest.approx(56000)
    assert evaluate_decision(599, 0.12, "TWO_WHEELER", pol).outcome == S.DECLINED_WITH_PLAN


def test_borderline_band_can_be_disabled_by_config():
    pol = get_settings().policy.model_copy(deep=True)
    pol.decision.borderline_enabled = False
    assert evaluate_decision(620, 0.1, "TWO_WHEELER", pol).outcome == S.DECLINED_WITH_PLAN


def test_state_machine_allows_only_declared_transitions():
    assert can_transition(S.CREATED, S.BUREAU_CHECKED)
    assert can_transition(S.AWAITING_CONSENT, S.CONSENT_GRANTED)
    assert not can_transition(S.CREATED, S.APPROVED)
    assert not can_transition(S.CONSENT_DENIED, S.CONSENT_GRANTED)  # terminal
    assert not can_transition(S.APPROVED, S.DECLINED_WITH_PLAN)
    with pytest.raises(AppError) as e:
        validate_transition("BYPASSED_TO_LOS", "AWAITING_CONSENT")
    assert e.value.code == "INVALID_TRANSITION"


def test_emi_formula_when_not_pinned():
    p = get_settings().policy.products["TWO_WHEELER"].model_copy(update={"emi": None})
    assert p.monthly_emi == pytest.approx(80000 * (1 + 0.14 * 2) / 24, abs=0.01)
