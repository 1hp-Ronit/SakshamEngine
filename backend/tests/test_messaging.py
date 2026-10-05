"""WhatsApp provider request shape / error handling (mock transport) + manager fallback + webhooks."""
import json

import httpx
import pytest

from app.adapters.messaging.manager import MessagingManager
from app.adapters.messaging.whatsapp import WhatsAppCloudProvider, to_wa_number
from app.core.config import EnvSettings, get_settings
from app.core.security import mask_secrets
from app.models import Application, Message
from app.services import orchestrator

TOKEN = "EAAB-fake-token-1234567890abcdef"


def env(**kw) -> EnvSettings:
    base = dict(whatsapp_access_token=TOKEN, whatsapp_phone_number_id="129924074327097", whatsapp_api_version="v25.0", demo_recipient_number="+91 70700 02780", messaging_mode="both")
    return EnvSettings(**{**base, **kw})


def provider(handler, **kw) -> WhatsAppCloudProvider:
    return WhatsAppCloudProvider(env(**kw), httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def ok_handler(captured):
    def h(request: httpx.Request):
        captured.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.ABC"}]})
    return h


def test_number_normalisation():
    assert to_wa_number("9876543210") == "919876543210"
    assert to_wa_number("+91-70700-02780") == "917070002780"
    assert to_wa_number("+1 (555) 669-7571") == "15556697571"


async def test_template_request_shape_and_recipient_override():
    seen = []
    res = await provider(ok_handler(seen)).send_template("9000000001", "hello_world", "en_US")
    assert res.ok and res.provider_message_id == "wamid.ABC"
    req = seen[0]
    assert str(req.url) == "https://graph.facebook.com/v25.0/129924074327097/messages"  # version comes from config
    assert req.headers["authorization"] == f"Bearer {TOKEN}"
    body = json.loads(req.content)
    assert body["to"] == "917070002780"  # persona number overridden by DEMO_RECIPIENT_NUMBER
    assert body["type"] == "template" and body["template"] == {"name": "hello_world", "language": {"code": "en_US"}}


async def test_template_variables_are_sanitised():
    seen = []
    await provider(ok_handler(seen)).send_template("9000000001", "saksham_consent_request", "hi", ["Ramesh\nKumar", "https://x/consent/1\t"])
    params = json.loads(seen[0].content)["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["Ramesh Kumar", "https://x/consent/1"]


async def test_free_text_utf8_devanagari_roundtrip():
    seen = []
    await provider(ok_handler(seen)).send_text("9000000001", "नमस्ते रमेश जी")
    assert json.loads(seen[0].content)["text"]["body"] == "नमस्ते रमेश जी"


async def test_graph_errors_are_typed_hinted_and_never_leak_the_token():
    def h(request):
        return httpx.Response(401, json={"error": {"message": f"Invalid OAuth access token {TOKEN}", "code": 190, "fbtrace_id": "x"}})

    res = await provider(h).send_text("9000000001", "hi")
    assert not res.ok and "190" in res.error and "refresh" in res.error
    assert TOKEN not in res.error


async def test_network_failure_is_a_result_not_an_exception():
    def h(request):
        raise httpx.ConnectError("boom")

    res = await provider(h).send_text("9000000001", "hi")
    assert not res.ok and "ConnectError" in res.error


async def test_unconfigured_provider_does_not_call_out():
    called = []
    p = provider(lambda r: called.append(r) or httpx.Response(200), whatsapp_access_token="")
    res = await p.send_text("9000000001", "hi")
    assert not res.ok and not called


def test_mask_secrets_scrubs_tokens_and_urls():
    assert TOKEN not in mask_secrets(f"error calling ?access_token={TOKEN}&x=1 with Bearer {TOKEN}")
    assert "AIzaSyA1234567890abcdefghijklmnop" not in mask_secrets("key=AIzaSyA1234567890abcdefghijklmnop")


def test_parse_webhook_payload():
    payload = {"entry": [{"changes": [{"value": {
        "messages": [{"from": "917070002780", "id": "wamid.IN1", "text": {"body": "Hi Saksham, I have given my consent. Ref abcd1234"}}],
        "statuses": [{"id": "wamid.ABC", "status": "delivered", "recipient_id": "917070002780"}]}}]}]}
    evs = provider(lambda r: httpx.Response(200)).parse_webhook(payload)
    assert [e.kind for e in evs] == ["inbound", "status"]
    assert evs[0].text.endswith("Ref abcd1234") and evs[1].status == "delivered"


# ───────────── manager: outbox always written; real failure degrades to the mirror ─────────────
async def _make_app(db, mobile="9000000001"):
    from app.core.security import mobile_hash, tokenize_identifier

    app = Application(mobile_number=mobile, mobile_number_hash=mobile_hash(mobile), pan_token_hash=tokenize_identifier("P", "pan"), aadhaar_token_hash=tokenize_identifier("A", "aadhaar"),
                      requested_product_sku="TWO_WHEELER", requested_emi=4200, ticket_size=80000, applicant_name="Ramesh Gupta")
    db.add(app)
    await db.commit()
    return app


async def test_simulated_mode_writes_outbox_only(db):
    app = await _make_app(db)
    mgr = MessagingManager(provider(lambda r: pytest.fail("must not call WhatsApp in simulated mode")))
    mgr.env = env(messaging_mode="simulated")
    msg = await mgr.send(db, app, purpose="consent_request", body="hello")
    assert msg.provider == "simulated" and msg.delivery_status == "delivered"


async def test_real_send_failure_is_marked_and_flow_continues(db):
    app = await _make_app(db)
    mgr = MessagingManager(provider(lambda r: httpx.Response(401, json={"error": {"code": 190, "message": "expired"}})))
    msg = await mgr.send(db, app, purpose="consent_request", body="hello", link_url="https://x/consent/1")
    assert msg.delivery_status == "failed_real_send" and msg.provider == "simulated" and "190" in msg.error
    rows = (await db.execute(Message.__table__.select())).all()
    assert len(rows) == 1  # still in the outbox → phone mirror shows it


async def test_consent_request_uses_configured_template(db):
    seen = []
    app = await _make_app(db)
    mgr = MessagingManager(provider(ok_handler(seen)))
    msg = await mgr.send(db, app, purpose="consent_request", body="body shown in mirror", link_url="https://x/consent/1")
    assert msg.provider == "whatsapp" and msg.message_type == "template" and msg.template_name == "hello_world" and msg.whatsapp_message_id == "wamid.ABC"
    assert json.loads(seen[0].content)["template"]["name"] == "hello_world"


async def test_window_opened_beforehand_by_the_recipient_sends_real_consent_link(db):
    """Presenter texts the business number once before the demo → even the FIRST message of a new application is real free text."""
    seen = []
    app = await _make_app(db)
    db.add(Message(application_id=None, direction="INBOUND", purpose="inbound", provider="whatsapp", recipient="917070002780", body="Hi"))
    await db.commit()
    mgr = MessagingManager(provider(ok_handler(seen)))
    msg = await mgr.send(db, app, purpose="consent_request", body="Please consent: https://x/consent/1", link_url="https://x/consent/1")
    body = json.loads(seen[0].content)
    assert msg.provider == "whatsapp" and msg.message_type == "text" and body["type"] == "text" and "https://x/consent/1" in body["text"]["body"]


async def test_window_of_another_number_does_not_count(db):
    seen = []
    app = await _make_app(db)
    db.add(Message(application_id=None, direction="INBOUND", purpose="inbound", provider="whatsapp", recipient="919999999999", body="Hi"))
    await db.commit()
    mgr = MessagingManager(provider(ok_handler(seen)))
    await mgr.send(db, app, purpose="consent_request", body="x")
    assert json.loads(seen[0].content)["type"] == "template"


async def test_result_is_free_text_only_inside_the_24h_window(db):
    seen = []
    app = await _make_app(db)
    mgr = MessagingManager(provider(ok_handler(seen)))
    closed = await mgr.send(db, app, purpose="result", body="decision text")
    assert not seen and closed.provider == "simulated" and "window closed" in closed.error

    db.add(Message(application_id=app.id, direction="INBOUND", purpose="inbound", provider="whatsapp", recipient="917070002780", body="Hi"))
    await db.commit()
    opened = await mgr.send(db, app, purpose="result", body="decision text 2")
    assert opened.provider == "whatsapp" and opened.message_type == "text"
    assert json.loads(seen[-1].content)["text"]["body"] == "decision text 2"


async def test_status_template_is_used_when_window_closed_if_configured(db):
    seen = []
    app = await _make_app(db)
    mgr = MessagingManager(provider(ok_handler(seen), whatsapp_status_template="saksham_status_update", whatsapp_status_template_params="name,url"))
    msg = await mgr.send(db, app, purpose="result", body="x", link_url="https://x/plan/1")
    t = json.loads(seen[0].content)["template"]
    assert msg.template_name == "saksham_status_update" and [p["text"] for p in t["components"][0]["parameters"]] == ["Ramesh", "https://x/plan/1"]


# ───────────── webhooks ─────────────
async def test_webhook_verification_challenge(client):
    tok = get_settings().env.whatsapp_verify_token
    ok = await client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": tok, "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = await client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"})
    assert bad.status_code == 403


async def test_webhook_signature_enforced_when_app_secret_set(client, monkeypatch):
    import hashlib, hmac

    monkeypatch.setattr(get_settings().env, "whatsapp_app_secret", "s3cret")
    body = json.dumps({"entry": []}).encode()
    bad = await client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=deadbeef"})
    good = await client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()})
    assert bad.status_code == 403 and good.status_code == 200


async def test_inbound_message_opens_window_and_status_updates_apply(client, db):
    from tests.test_e2e_personas import PERSONAS, create_body

    created = (await client.post("/api/v1/applications/create", json=create_body(PERSONAS[1]))).json()
    aid, sid = created["application_id"], created["session_id"]
    mgr = orchestrator.get_messaging() if hasattr(orchestrator, "get_messaging") else None  # noqa: F841
    # inbound with the wa.me prefill → attributed to this application via "Ref <session[:8]>"
    payload = {"entry": [{"changes": [{"value": {"messages": [{"from": "917070002780", "id": "wamid.IN1", "text": {"body": f"Hi Saksham, I have given my consent. Ref {sid[:8]}"}}]}}]}]}
    assert (await client.post("/webhooks/whatsapp", json=payload)).status_code == 200
    inbound = (await db.execute(Message.__table__.select().where(Message.direction == "INBOUND"))).all()
    assert len(inbound) == 1 and inbound[0].application_id == aid

    # delivery status update for a real outbound message
    out = (await db.execute(Message.__table__.select().where(Message.application_id == aid, Message.direction == "OUTBOUND"))).first()
    await db.execute(Message.__table__.update().where(Message.id == out.id).values(whatsapp_message_id="wamid.OUT1", provider="whatsapp"))
    await db.commit()
    st = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.OUT1", "status": "read", "recipient_id": "917070002780"}]}}]}]}
    await client.post("/webhooks/whatsapp", json=st)
    await db.close()
    trace = (await client.get(f"/api/v1/applications/{aid}/trace")).json()
    assert trace["message_delivery"]["consent_request"] == "read"


async def test_demo_reset_keeps_the_open_whatsapp_window(client, db):
    from sqlalchemy import select

    from app.core import database

    db.add(Message(application_id=None, direction="INBOUND", purpose="inbound", provider="whatsapp", recipient="917070002780", body="Hi"))
    await db.commit()
    assert (await client.post("/demo/reset")).status_code == 200
    async with database.session_factory()() as s2:
        rows = (await s2.execute(select(Message))).scalars().all()
    assert [(m.direction, m.recipient) for m in rows] == [("INBOUND", "917070002780")]
