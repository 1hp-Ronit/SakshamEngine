from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow
from app.models.application import new_id


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(8))  # OUTBOUND | INBOUND
    purpose: Mapped[str] = mapped_column(String(32), default="")  # consent_request | result | status_update | inbound
    provider: Mapped[str] = mapped_column(String(12), default="simulated")  # whatsapp | simulated
    message_type: Mapped[str] = mapped_column(String(10), default="text")  # template | text
    template_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recipient: Mapped[str] = mapped_column(String(32), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    delivery_status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|sent|delivered|read|failed|failed_real_send
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
