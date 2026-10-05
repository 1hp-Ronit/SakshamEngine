from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow
from app.models.application import new_id


class ConsentArtifact(Base):
    __tablename__ = "consent_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)  # = consent_id
    session_id: Mapped[str] = mapped_column(ForeignKey("consent_sessions.id"), index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    grant_aa: Mapped[bool] = mapped_column(Boolean, default=False)
    grant_telecom: Mapped[bool] = mapped_column(Boolean, default=False)
    grant_business: Mapped[bool] = mapped_column(Boolean, default=False)
    purpose: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(String(64))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConsentLog(Base):
    __tablename__ = "consent_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    consent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # null for DENIED (no artifact)
    event: Mapped[str] = mapped_column(String(12))  # GRANTED | DENIED | REVOKED
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
