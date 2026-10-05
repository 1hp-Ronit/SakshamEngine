"""WhatsApp Cloud API webhooks: Meta verification challenge, inbound messages (24h window) and delivery statuses."""
from __future__ import annotations

import hashlib
import hmac
import re

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.messaging.manager import get_messaging
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.timeutil import utcnow
from app.models import Application, ConsentSession, Message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger("webhook")


@router.get("/whatsapp")
async def verify(hub_mode: str = Query("", alias="hub.mode"), hub_verify_token: str = Query("", alias="hub.verify_token"), hub_challenge: str = Query("", alias="hub.challenge")):
    if hub_mode == "subscribe" and hmac.compare_digest(hub_verify_token, get_settings().env.whatsapp_verify_token):
        return PlainTextResponse(hub_challenge)
    raise AppError("FORBIDDEN", "Webhook verification failed", 403)


def _signature_ok(secret: str, body: bytes, header: str | None) -> bool:
    if not secret:
        return True  # signature checks are optional (WHATSAPP_APP_SECRET)
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


async def _application_for_inbound(db: AsyncSession, text: str) -> Application | None:
    """The consent page's wa.me link prefills 'Ref <first 8 chars of session id>' — use it to attribute the message."""
    m = re.search(r"Ref\s+([0-9a-f]{8})", text or "", re.I)
    if m:
        sess = (await db.execute(select(ConsentSession).where(ConsentSession.id.like(m.group(1).lower() + "%")))).scalars().first()
        if sess:
            return await db.get(Application, sess.application_id)
    # Fallback: single demo recipient → most recent application
    return (await db.execute(select(Application).order_by(Application.created_at.desc()))).scalars().first()


@router.post("/whatsapp")
async def receive(request: Request, db: AsyncSession = Depends(get_session)):
    raw = await request.body()
    if not _signature_ok(get_settings().env.whatsapp_app_secret, raw, request.headers.get("X-Hub-Signature-256")):
        raise AppError("FORBIDDEN", "Invalid webhook signature", 403)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {"ok": True}
    manager = get_messaging()
    events = manager.whatsapp.parse_webhook(payload)
    inbound = statuses = 0
    for ev in events:
        if ev.kind == "inbound":
            app = await _application_for_inbound(db, ev.text or "")
            db.add(Message(application_id=app.id if app else None, direction="INBOUND", purpose="inbound", provider="whatsapp", message_type="text",
                           recipient=ev.sender or "", body=ev.text or "", whatsapp_message_id=ev.message_id, delivery_status="delivered"))
            await db.commit()
            inbound += 1
            if app is not None:  # window just opened → deliver any result that was waiting for it
                await manager.flush_pending(db, app)
        elif ev.kind == "status" and ev.message_id:
            msg = (await db.execute(select(Message).where(Message.whatsapp_message_id == ev.message_id))).scalars().first()
            if msg and ev.status:
                msg.delivery_status = ev.status
                msg.status_updated_at = utcnow()
                if ev.status == "failed":
                    errs = (ev.raw or {}).get("errors") or []
                    msg.error = (errs[0].get("title") or errs[0].get("message")) if errs else "delivery failed"
                await db.commit()
                statuses += 1
    log.info("webhook: %d inbound, %d status updates", inbound, statuses)
    return {"ok": True}
