"""Decision policy. Pure function of (score, pd, product) + config."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Policy
from app.domain.state_machine import ApplicationStatus


@dataclass(frozen=True)
class Decision:
    outcome: ApplicationStatus
    suggested_ticket: float | None = None  # set for the borderline band
    reason: str = ""


def evaluate_decision(score: float, pd: float, product_sku: str, policy: Policy) -> Decision:
    d = policy.decision
    ticket = policy.products[product_sku].ticket
    pd_ok = d.max_pd_for_approval is None or pd <= d.max_pd_for_approval
    if score >= d.approve_cutoff and pd_ok:
        return Decision(ApplicationStatus.APPROVED, reason=f"score {score:.0f} ≥ cutoff {d.approve_cutoff:.0f}")
    if d.borderline_enabled and d.borderline_floor <= score < d.approve_cutoff:
        return Decision(
            ApplicationStatus.CONDITIONAL_APPROVAL, round(ticket * d.borderline_ticket_factor, -3),
            f"borderline band {d.borderline_floor:.0f}–{d.approve_cutoff:.0f}",
        )
    return Decision(ApplicationStatus.DECLINED_WITH_PLAN, reason=f"score {score:.0f} < cutoff {d.approve_cutoff:.0f}")
