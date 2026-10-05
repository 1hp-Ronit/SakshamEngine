#!/usr/bin/env python
"""Validate external integrations BEFORE a demo: WhatsApp credentials, test message, public URL, Gemini key.

    make check-whatsapp                 # checks everything, sends the pre-approved template to DEMO_RECIPIENT_NUMBER
    make check-whatsapp ARGS=--no-send  # validate credentials only, send nothing

Never prints secrets.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import httpx  # noqa: E402

from app.adapters.llm.gemini import GeminiLLMClient  # noqa: E402
from app.adapters.messaging.whatsapp import WhatsAppCloudProvider, to_wa_number  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import mask_secret  # noqa: E402

OK, BAD, WARN = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[33m!\033[0m"


async def main(send: bool) -> int:
    env = get_settings().env
    failures = 0
    print("── Configuration (secrets masked)")
    print(f"   MESSAGING_MODE         {env.messaging_mode}")
    print(f"   WHATSAPP_ACCESS_TOKEN  {mask_secret(env.whatsapp_access_token) or '(not set)'}")
    print(f"   PHONE_NUMBER_ID        {env.whatsapp_phone_number_id or '(not set)'}   API {env.whatsapp_api_version}")
    print(f"   DEMO_RECIPIENT_NUMBER  {env.demo_recipient_number or '(not set)'}")
    print(f"   PUBLIC_BASE_URL        {env.public_base_url}")
    print(f"   CONSENT TEMPLATE       {env.whatsapp_consent_template} ({env.whatsapp_consent_template_lang})")

    print("\n── Public URL (the consent link must open on a real phone)")
    base = env.public_base_url.rstrip("/")
    if "localhost" in base or "127.0.0.1" in base:
        print(f" {WARN} PUBLIC_BASE_URL is localhost — a phone cannot open it. Run `ngrok http 8000` and set PUBLIC_BASE_URL to the https URL.")
    else:
        try:
            async with httpx.AsyncClient(timeout=6, follow_redirects=True) as c:
                r = await c.get(f"{base}/health")
            ok = r.status_code == 200 and r.json().get("status") == "ok"
            print(f" {OK if ok else BAD} GET {base}/health → {r.status_code}")
            failures += not ok
        except Exception as e:  # noqa: BLE001
            print(f" {BAD} {base} unreachable ({type(e).__name__}). Is the server running and the tunnel up?")
            failures += 1

    print("\n── WhatsApp Cloud API")
    wa = WhatsAppCloudProvider(env)
    ok, info = await wa.check_credentials()
    print(f" {OK if ok else BAD} credentials: {info}")
    days = await wa.token_expiry_days() if env.whatsapp_access_token else None
    if days is not None:
        hours = days * 24
        msg = f"token expires in {hours:.1f} h" if hours < 48 else f"token expires in {days:.0f} days"
        print(f" {WARN if hours < 24 else OK} {msg}" + (" — use a system-user token for anything longer than a quick test" if hours < 24 else ""))
    if not ok:
        failures += 1
    elif send:
        if not env.demo_recipient_number:
            print(f" {BAD} DEMO_RECIPIENT_NUMBER is not set — cannot send a test message")
            failures += 1
        else:
            res = await wa.send_template(env.demo_recipient_number, env.whatsapp_consent_template, env.whatsapp_consent_template_lang or "en_US")
            to = to_wa_number(env.demo_recipient_number)
            if res.ok:
                print(f" {OK} test message accepted by Meta → +{to[:2]}…{to[-4:]} (id {res.provider_message_id[:18]}…). Check the phone.")
            else:
                print(f" {BAD} send failed: {res.error}")
                failures += 1
    else:
        print(f" {WARN} --no-send: skipped sending a test message")

    print("\n── Gemini advisory LLM")
    llm = GeminiLLMClient(env)
    if env.llm_fallback_only:
        print(f" {WARN} LLM_FALLBACK_ONLY=true — deterministic templates only (offline mode)")
    elif not env.gemini_api_key:
        print(f" {WARN} GEMINI_API_KEY not set — deterministic templates will be used")
    else:
        try:
            out = await llm.complete_json('Reply with strict JSON {"ok": true}.', 'ping')
            print(f" {OK} {env.llm_model} responded: {out.strip()[:60]}")
        except Exception:  # noqa: BLE001
            print(f" {BAD} Gemini call failed: {llm.last_error}")
            failures += 1

    print("\n" + ("All checks passed." if not failures else f"{failures} check(s) failed."))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(send="--no-send" not in sys.argv)))
