from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow


class DataAccessLog(Base):
    """One row per attempted read of a data source, written by the ingestion step.

    Rows are written for sources the customer did NOT consent to too (status `not_consented`): that is evidence
    that nothing was read. Append-only, like the consent log."""
    __tablename__ = "data_access_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    consent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(16))  # aa | telecom | business
    status: Mapped[str] = mapped_column(String(16))  # ok | timeout | error | not_consented | no_data
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
