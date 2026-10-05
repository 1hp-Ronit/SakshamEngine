"""WhatsApp Cloud API (Meta Graph API) provider. Never logs the token; errors are scrubbed and typed."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.adapters.interfaces import MessagingProvider, SendResult, WebhookEvent
from app.core.config import EnvSettings
from app.core.logging import get_logger
from app.core.security import mask_secrets

log = get_logger("whatsapp")

# Graph API error codes worth explaining to a developer
_HINTS = {
    190: "access token expired/invalid — refresh it (or use a long-lived system-user token)",
    10: "permission denied — check app permissions / token scope",
    131030: "recipient not in the allowed list — add the number under 'Send and receive messages → To' in Meta's API setup",
    131047: "24-hour customer-service window closed — only approved templates can be sent",
    131026: "message undeliverable (number not on WhatsApp?)",
    132000: "template parameter count mismatch",
    132001: "template does not exist in this language / not approved",
    100: "invalid parameter (check phone number ID / payload)",
}


def to_wa_number(number: str, default_country_code: str = "91") -> str:
    """E.164 digits without '+' (WhatsApp Cloud API format). 10-digit Indian numbers get +91."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) == 10:
        digits = default_country_code + digits
    return digits


class WhatsAppCloudProvider(MessagingProvider):
    name = "whatsapp"

    def __init__(self, env: EnvSettings, client: httpx.AsyncClient | None = None):
        self.env = env
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.env.whatsapp_access_token and self.env.whatsapp_phone_number_id)

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.env.whatsapp_api_version}/{self.env.whatsapp_phone_number_id}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.env.whatsapp_access_token}", "Content-Type": "application/json"}

    def _recipient(self, to: str) -> str:
        # Test numbers can only message verified recipients → real sends are redirected to DEMO_RECIPIENT_NUMBER
        return to_wa_number(self.env.demo_recipient_number or to)

    async def _post(self, payload: dict[str, Any]) -> SendResult:
        if not self.configured:
            return SendResult(False, error="WhatsApp credentials not configured")
        client = self._client or httpx.AsyncClient()
        try:
            resp = await client.post(f"{self.base_url}/messages", json=payload, headers=self._headers(), timeout=6.0)
        except Exception as exc:  # noqa: BLE001
            err = self._scrub(f"{type(exc).__name__}: {exc}")
            log.error("WhatsApp send failed (network): %s", err)
            return SendResult(False, error=err)
        finally:
            if self._client is None:
                await client.aclose()
        if resp.status_code // 100 == 2:
            try:
                return SendResult(True, resp.json()["messages"][0]["id"])
            except Exception:  # noqa: BLE001
                return SendResult(False, error="Unexpected response shape from WhatsApp API")
        return SendResult(False, error=self._describe_error(resp))

    def _scrub(self, text: str) -> str:
        """Remove THIS provider's own credential (Meta sometimes echoes the token in error text), then generic patterns."""
        tok = self.env.whatsapp_access_token
        return mask_secrets(text.replace(tok, "****") if tok else text)

    def _describe_error(self, resp: httpx.Response) -> str:
        try:
            e = resp.json().get("error", {})
            code = e.get("code")
            detail = (e.get("error_data") or {}).get("details") or e.get("message", "")
            hint = _HINTS.get(code, "")
            return self._scrub(f"HTTP {resp.status_code} code={code}: {detail}" + (f" → {hint}" if hint else ""))
        except Exception:  # noqa: BLE001
            return f"HTTP {resp.status_code}"

    async def send_template(self, to: str, template_name: str, language: str, params: list[str] | None = None) -> SendResult:
        template: dict[str, Any] = {"name": template_name, "language": {"code": language}}
        if params:
            clean = [re.sub(r"[\n\t]+", " ", p).strip() for p in params]  # variables must be free of newlines/tabs
            template["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in clean]}]
        return await self._post({"messaging_product": "whatsapp", "to": self._recipient(to), "type": "template", "template": template})

    async def send_text(self, to: str, body: str) -> SendResult:
        return await self._post({"messaging_product": "whatsapp", "to": self._recipient(to), "type": "text", "text": {"preview_url": True, "body": body}})

    async def check_credentials(self) -> tuple[bool, str]:
        """GET the phone-number object — validates token + phone number id without sending anything."""
        if not self.configured:
            return False, "WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID not set"
        client = self._client or httpx.AsyncClient()
        try:
            resp = await client.get(self.base_url, params={"fields": "display_phone_number,verified_name,quality_rating"}, headers=self._headers(), timeout=6.0)
        except Exception as exc:  # noqa: BLE001
            return False, self._scrub(f"{type(exc).__name__}: {exc}")
        finally:
            if self._client is None:
                await client.aclose()
        if resp.status_code == 200:
            d = resp.json()
            return True, f"{d.get('verified_name', '?')} · {d.get('display_phone_number', '?')}"
        return False, self._describe_error(resp)

    async def token_expiry_days(self) -> float | None:
        """Days until the access token expires (None = never / unknown). Temporary tokens last ~1 day."""
        import time

        client = self._client or httpx.AsyncClient()
        try:
            r = await client.get(f"https://graph.facebook.com/{self.env.whatsapp_api_version}/debug_token", params={"input_token": self.env.whatsapp_access_token},
                                 headers=self._headers(), timeout=6.0)
            exp = r.json().get("data", {}).get("expires_at") if r.status_code == 200 else None
            return (exp - time.time()) / 86400 if exp else None
        except Exception:  # noqa: BLE001
            return None
        finally:
            if self._client is None:
                await client.aclose()

    def parse_webhook(self, payload: dict[str, Any]) -> list[WebhookEvent]:
        events: list[WebhookEvent] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for m in value.get("messages", []):
                    text = (m.get("text") or {}).get("body") or (m.get("button") or {}).get("text") or ""
                    events.append(WebhookEvent("inbound", sender=m.get("from"), text=text, message_id=m.get("id"), raw=m))
                for st in value.get("statuses", []):
                    events.append(WebhookEvent("status", message_id=st.get("id"), status=st.get("status"), recipient=st.get("recipient_id"), raw=st))
        return events
