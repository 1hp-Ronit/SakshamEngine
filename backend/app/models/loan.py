from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow
from app.models.application import new_id


class Loan(Base):
    """Mock LMS loan account."""
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)  # = loan_id
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(40), index=True)
    product_sku: Mapped[str] = mapped_column(String(40))
    sanctioned_amount: Mapped[float] = mapped_column(Float)
    emi_amount: Mapped[float] = mapped_column(Float)
    tenure_months: Mapped[int] = mapped_column(Integer)
    behaviour_score: Mapped[int] = mapped_column(Integer)
    current_tier: Mapped[str] = mapped_column(String(16))
    current_limit: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RepaymentEvent(Base):
    __tablename__ = "repayment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.id"), index=True)
    status: Mapped[str] = mapped_column(String(10))  # ON_TIME | LATE | MISSED
    score_delta: Mapped[int] = mapped_column(Integer)
    behaviour_score_after: Mapped[int] = mapped_column(Integer)
    tier_after: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
