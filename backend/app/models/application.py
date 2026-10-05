from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow


def new_id() -> str:
    return str(uuid.uuid4())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Contact number is kept because the messaging channel needs it; PAN/Aadhaar are stored only as HMAC tokens.
    mobile_number: Mapped[str] = mapped_column(String(20))
    mobile_number_hash: Mapped[str] = mapped_column(String(64), index=True)
    pan_token_hash: Mapped[str] = mapped_column(String(64))
    aadhaar_token_hash: Mapped[str] = mapped_column(String(64))
    applicant_name: Mapped[str] = mapped_column(String(120), default="")
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    requested_product_sku: Mapped[str] = mapped_column(String(40))
    requested_emi: Mapped[float] = mapped_column(Float)
    ticket_size: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)
    bureau_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bureau_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # -1 for NO_HIT
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    consent_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pd: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    suggested_ticket: Mapped[float | None] = mapped_column(Float, nullable=True)
    feature_vector_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # purged on revoke
    feature_vector_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # advisory plan for /plan page
    persona_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    demo_options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ConsentSession(Base):
    """One-time consent session. TTL lazily enforced on read."""
    __tablename__ = "consent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)  # = session_id
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")  # OPEN | GRANTED | DENIED | EXPIRED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
