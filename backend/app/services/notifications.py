"""Builds applicant-facing message bodies (en/hi/mr, from reason_codes.yaml) and hands them to the messaging manager."""
from __future__ import annotations

from app.adapters.messaging.manager import get_messaging
from app.core.config import get_settings
from app.domain.reason_codes import get_catalog
from app.models import Application, Message
from app.services.advisory import Plan, render_plan_message


def first_name(app: Application) -> str:
    return (app.applicant_name or "").strip().split(" ")[0]


def _lang(app: Application) -> str:
    return app.preferred_language if app.preferred_language in get_settings().policy.languages.supported else get_settings().policy.languages.default


def plan_url(app: Application) -> str:
    return f"{get_settings().env.public_base_url.rstrip('/')}/plan/{app.id}"


async def send_consent_request(db, app: Application, url: str) -> Message:
    c, lang = get_catalog(), _lang(app)
    body = c.template("consent_request", lang).format(name=first_name(app) or "", url=url, product=c.product_label(app.requested_product_sku, lang))
    return await get_messaging().send(db, app, purpose="consent_request", body=body, link_url=url, first_name=first_name(app))


async def send_approved(db, app: Application) -> Message:
    c, lang = get_catalog(), _lang(app)
    body = c.template("approved", lang).format(name=first_name(app) or "", product=c.product_label(app.requested_product_sku, lang))
    return await get_messaging().send(db, app, purpose="result", body=body, link_url=plan_url(app), first_name=first_name(app))


async def send_conditional(db, app: Application, amount: float) -> Message:
    c, lang = get_catalog(), _lang(app)
    body = c.template("conditional", lang).format(name=first_name(app) or "", product=c.product_label(app.requested_product_sku, lang), amount=f"{amount:,.0f}")
    return await get_messaging().send(db, app, purpose="result", body=body, link_url=plan_url(app), first_name=first_name(app))


async def send_insufficient(db, app: Application) -> Message:
    c, lang = get_catalog(), _lang(app)
    body = c.template("insufficient", lang).format(name=first_name(app) or "", product=c.product_label(app.requested_product_sku, lang))
    return await get_messaging().send(db, app, purpose="result", body=body, first_name=first_name(app))


async def send_plan(db, app: Application, plan: Plan) -> Message:
    url = plan_url(app)
    return await get_messaging().send(db, app, purpose="result", body=render_plan_message(plan, url), link_url=url, first_name=first_name(app))
