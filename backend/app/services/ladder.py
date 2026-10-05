"""Graduation ladder: repayment behaviour → behaviour score → tier → limits. All thresholds come from policy.yaml."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.models import Application, Loan, RepaymentEvent


def tier_for_score(score: int) -> str:
    lp = get_settings().policy.ladder
    current = lp.tier_order[0]
    for name in lp.tier_order:
        if score >= lp.tiers[name].min_behaviour_score:
            current = name
    return current


def limit_for(tier: str, sku: str, sanctioned: float = 0.0) -> float:
    """Pre-approved limit for the loan's product at `tier`; never below what was actually sanctioned."""
    return max(sanctioned, get_settings().policy.ladder.tiers[tier].limits.get(sku, 0.0))


def customer_id_for(mobile_hash: str) -> str:
    return "cust_" + mobile_hash[:12]


async def create_loan(db: AsyncSession, app: Application, amount: float, emi: float, tenure_months: int) -> Loan:
    lp = get_settings().policy.ladder
    tier = tier_for_score(lp.initial_score)
    loan = Loan(
        application_id=app.id, customer_id=customer_id_for(app.mobile_number_hash), product_sku=app.requested_product_sku,
        sanctioned_amount=amount, emi_amount=emi, tenure_months=tenure_months, behaviour_score=lp.initial_score,
        current_tier=tier, current_limit=limit_for(tier, app.requested_product_sku, amount),
    )
    db.add(loan)
    await db.flush()
    return loan


def _next_tier(tier: str) -> str | None:
    order = get_settings().policy.ladder.tier_order
    i = order.index(tier)
    return order[i + 1] if i + 1 < len(order) else None


def ladder_view(loan: Loan) -> dict[str, Any]:
    lp = get_settings().policy.ladder
    nxt = _next_tier(loan.current_tier)
    need = None
    if nxt:
        gap = lp.tiers[nxt].min_behaviour_score - loan.behaviour_score
        need = f"Behaviour score ≥ {lp.tiers[nxt].min_behaviour_score} (need {max(gap, 0)} more points)"
    limits_now = lp.tiers[loan.current_tier].limits
    limits_next = lp.tiers[nxt].limits if nxt else None
    unlocks = [sku for sku, v in (limits_next or {}).items() if v > limits_now.get(sku, 0)] if limits_next else []
    return {
        "loan_id": loan.id, "customer_id": loan.customer_id, "product_sku": loan.product_sku,
        "behaviour_score": loan.behaviour_score, "current_tier": loan.current_tier, "current_limit": loan.current_limit,
        "tier_limits": limits_now, "next_tier": nxt, "next_tier_requirement": need,
        "next_tier_min_score": lp.tiers[nxt].min_behaviour_score if nxt else None, "next_tier_limits": limits_next, "next_tier_unlocks": unlocks,
        "tiers": [{"name": n, "min_behaviour_score": lp.tiers[n].min_behaviour_score, "limits": lp.tiers[n].limits} for n in lp.tier_order],
        "max_score": lp.max_score,
    }


async def record_event(db: AsyncSession, loan_id: str, status: str) -> dict[str, Any]:
    lp = get_settings().policy.ladder
    if status not in lp.deltas:
        raise AppError("VALIDATION_ERROR", f"status must be one of {sorted(lp.deltas)}", 422)
    loan = await db.get(Loan, loan_id)
    if loan is None:
        raise NotFound("Loan not found", "LOAN_NOT_FOUND")
    prev_tier = loan.current_tier
    delta = lp.deltas[status]
    loan.behaviour_score = max(lp.min_score, min(lp.max_score, loan.behaviour_score + delta))
    loan.current_tier = tier_for_score(loan.behaviour_score)
    loan.current_limit = limit_for(loan.current_tier, loan.product_sku, loan.sanctioned_amount)
    db.add(RepaymentEvent(loan_id=loan.id, status=status, score_delta=delta, behaviour_score_after=loan.behaviour_score, tier_after=loan.current_tier))
    await db.commit()
    view = ladder_view(loan)
    return {"event_recorded": True, "score_delta": delta, "previous_tier": prev_tier, "tier_changed": prev_tier != loan.current_tier, **view}


async def get_ladder_for_customer(db: AsyncSession, customer_or_loan_id: str) -> dict[str, Any]:
    """Accepts a customer_id (latest loan) or a loan_id."""
    loan = await db.get(Loan, customer_or_loan_id)
    if loan is None:
        res = await db.execute(select(Loan).where(Loan.customer_id == customer_or_loan_id).order_by(Loan.created_at.desc()))
        loan = res.scalars().first()
    if loan is None:
        raise NotFound("No loan account found for this customer", "LOAN_NOT_FOUND")
    events = (await db.execute(select(RepaymentEvent).where(RepaymentEvent.loan_id == loan.id).order_by(RepaymentEvent.id))).scalars().all()
    view = ladder_view(loan)
    view["history"] = [{"status": e.status, "score_delta": e.score_delta, "behaviour_score_after": e.behaviour_score_after, "tier_after": e.tier_after} for e in events]
    return view
