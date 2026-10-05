from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow
from app.models.application import new_id


class Withdrawal(Base):
    """A dealer withdrew an approval. One per application, insert-only. The audit record and consent history are kept;
    the application simply stops appearing in the approved-loans list."""
    __tablename__ = "withdrawals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True)
    reason: Mapped[str] = mapped_column(String(64))  # one of policy.yaml → withdrawal.reasons
    withdrawn_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
