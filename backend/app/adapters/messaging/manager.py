"""Routes outgoing messages by MESSAGING_MODE. The outbox is ALWAYS written (dashboard message log + automatic fallback)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.interfaces import SendResult
from app.adapters.messaging.simulated import SimulatedProvider
from app.adapters.messaging.whatsapp import WhatsAppCloudProvider, to_wa_number
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.timeutil import utcnow
from app.models import Application, Message

log = get_logger("messaging")

_LANG_CODES = {"en": "en", "hi": "hi", "mr": "mr"}


def _fill_params(spec: str, ctx: dict[str, str]) -> list[str] | None:
    names = [p.strip() for p in spec.split(",") if p.strip()]
    return [ctx.get(n, "") for n in names] or None


class MessagingManager:
    def __init__(self, whatsapp: WhatsAppCloudProvider | None = None):
        self.whatsapp = whatsapp or WhatsAppCloudProvider(get_settings().env)
        self.env = self.whatsapp.env  # one source of truth for mode + credentials
        self.simulated = SimulatedProvider()

    @property
    def mode(self) -> str:
        return self.env.messaging_mode

    @property
    def real_enabled(self) -> bool:
        return self.mode in ("whatsapp", "both") and self.whatsapp.configured

    async def window_open(self, db: AsyncSession, app: Application) -> bool:
        """24h service window: open if the recipient messaged us within the last 24h.

        Keyed by the real recipient number (not just this application), so a presenter can open the window once by
        texting the business number before the demo — every later message then goes out as real free-form text."""
        hours = get_settings().policy.messaging.whatsapp_window_hours
        real_number = to_wa_number(self.env.demo_recipient_number or app.mobile_number)
        res = await db.execute(
            select(Message.id).where(
                Message.direction == "INBOUND", Message.created_at >= utcnow() - timedelta(hours=hours),
                or_(Message.application_id == app.id, Message.recipient == real_number),
            ).limit(1)
        )
        return res.first() is not None

    async def send(self, db: AsyncSession, app: Application, *, purpose: str, body: str, link_url: str | None = None, first_name: str = "") -> Message:
        """purpose: consent_request | result | status_update"""
        msg = Message(application_id=app.id, direction="OUTBOUND", purpose=purpose, provider="simulated", message_type="text",
                      recipient=app.mobile_number, body=body, link_url=link_url, delivery_status="queued")
        db.add(msg)
        await db.flush()  # outbox row exists before any network call

        if self.real_enabled:
            result, template_used, kind = await self._real_send(db, app, msg, purpose, first_name, link_url)
            if result is None:  # deliberately not sent for real (e.g. window closed, no status template)
                msg.delivery_status = "delivered"
                msg.error = "24h window closed — not sent via WhatsApp (recipient must message the business number first)"
            elif result.ok:
                msg.provider, msg.message_type, msg.template_name = "whatsapp", kind, template_used
                msg.whatsapp_message_id, msg.delivery_status = result.provider_message_id, "sent"
            else:
                msg.delivery_status, msg.error = "failed_real_send", result.error
                log.warning("real WhatsApp send failed for %s: %s", purpose, result.error)
        else:
            msg.delivery_status = "delivered"  # simulated delivery
        msg.status_updated_at = utcnow()
        await db.commit()
        return msg

    async def flush_pending(self, db: AsyncSession, app: Application) -> int:
        """The 24h window just opened (inbound message): deliver result messages that were held back as simulated-only."""
        if not self.real_enabled or not await self.window_open(db, app):
            return 0
        res = await db.execute(select(Message).where(
            Message.application_id == app.id, Message.direction == "OUTBOUND", Message.purpose == "result", Message.provider == "simulated",
            Message.error.like("24h window closed%"),
        ))
        sent = 0
        for msg in res.scalars():
            r = await self.whatsapp.send_text(app.mobile_number, msg.body)
            if r.ok:
                msg.provider, msg.message_type, msg.whatsapp_message_id, msg.delivery_status, msg.error = "whatsapp", "text", r.provider_message_id, "sent", None
                sent += 1
            else:
                msg.delivery_status, msg.error = "failed_real_send", r.error
            msg.status_updated_at = utcnow()
        await db.commit()
        return sent

    async def _real_send(self, db, app, msg, purpose, first_name, link_url) -> tuple[SendResult | None, str | None, str]:
        env = self.env
        ctx = {"name": first_name or app.applicant_name.split(" ")[0] or "there", "url": link_url or ""}
        lang = _LANG_CODES.get(app.preferred_language, "en")

        if purpose == "consent_request":
            if await self.window_open(db, app):  # window already open → the real message can carry the actual consent link
                return await self.whatsapp.send_text(app.mobile_number, msg.body), None, "text"
            tlang = lang if env.whatsapp_consent_template_lang == "auto" else env.whatsapp_consent_template_lang
            res = await self.whatsapp.send_template(app.mobile_number, env.whatsapp_consent_template, tlang, _fill_params(env.whatsapp_consent_template_params, ctx))
            return res, env.whatsapp_consent_template, "template"

        # Results: free text if the 24h window is open, else the optional status template, else simulated-only
        if await self.window_open(db, app):
            return await self.whatsapp.send_text(app.mobile_number, msg.body), None, "text"
        if env.whatsapp_status_template:
            tlang = lang if env.whatsapp_status_template_lang == "auto" else env.whatsapp_status_template_lang
            res = await self.whatsapp.send_template(app.mobile_number, env.whatsapp_status_template, tlang, _fill_params(env.whatsapp_status_template_params, ctx))
            return res, env.whatsapp_status_template, "template"
        return None, None, "text"


_manager: MessagingManager | None = None


def get_messaging() -> MessagingManager:
    global _manager
    if _manager is None:
        _manager = MessagingManager()
    return _manager


def reset_messaging() -> None:
    global _manager
    _manager = None
