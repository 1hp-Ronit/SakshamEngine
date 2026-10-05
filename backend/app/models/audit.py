from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow
from app.models.application import new_id


class AuditRecord(Base):
    """Immutable: one per decision, never updated (see AuditRepository — insert only)."""
    __tablename__ = "audit_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True)
    model_version: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(32))
    consent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    feature_vector_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_pd: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32))
    shap_top_positive: Mapped[str] = mapped_column(Text, default="[]")
    shap_top_negative: Mapped[str] = mapped_column(Text, default="[]")
    reason_codes: Mapped[str] = mapped_column(Text, default="[]")
    waterfall_json: Mapped[str] = mapped_column(Text, default="[]")  # score-points waterfall for the UI
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | timeout | error | skipped | not_consented | no_data
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
