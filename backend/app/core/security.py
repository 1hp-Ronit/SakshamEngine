"""HMAC signing, identifier tokenization and secret masking."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any

from app.core.config import get_settings


def _key() -> bytes:
    return get_settings().env.secret_key.encode()


def hmac_hex(value: str, purpose: str = "") -> str:
    """Deterministic keyed hash. `purpose` namespaces tokens (pan / aadhaar / mobile)."""
    return hmac.new(_key(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def tokenize_identifier(value: str, kind: str) -> str:
    return hmac_hex(value.strip().upper(), kind)


def normalize_mobile(mobile: str) -> str:
    """Last 10 digits (drops +91, spaces, dashes)."""
    digits = re.sub(r"\D", "", mobile or "")
    return digits[-10:]


def mobile_hash(mobile: str) -> str:
    return hmac_hex(normalize_mobile(mobile), "mobile")


def vendor_ref(mobile: str) -> str:
    """Stable pseudonymous customer reference sent to data vendors (bureau/AA/telecom/business mocks).

    Deliberately NOT keyed by SECRET_KEY: vendor-side data must not change when the server secret is rotated,
    so the demo personas stay deterministic. (The keyed `mobile_hash` is what we store in our own DB.)"""
    return hashlib.sha256(("saksham-vendor-ref-v1:" + normalize_mobile(mobile)).encode()).hexdigest()


def sign_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(_key(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: dict[str, Any], signature: str) -> bool:
    return hmac.compare_digest(sign_payload(payload), signature)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def mask_secret(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}…{'*' * 4}"


_SECRET_PATTERNS = [
    re.compile(r"(access_token=)[^&\s]+", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I),
    re.compile(r"(key=)[^&\s]+", re.I),
    re.compile(r"(EAA[A-Za-z0-9]{10,})"),
    re.compile(r"(AIza[0-9A-Za-z_\-]{20,})"),
]


def mask_secrets(text: str) -> str:
    """Scrub tokens/keys out of arbitrary text (error messages, URLs) before logging or storing."""
    out = text
    env = get_settings().env
    for secret in (env.whatsapp_access_token, env.gemini_api_key, env.secret_key, env.whatsapp_app_secret):
        if secret and len(secret) >= 6:
            out = out.replace(secret, "****")
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: (m.group(1) if m.lastindex and m.group(1) and not m.group(1).startswith(("EAA", "AIza")) else "") + "****", out)
    return out
