"""Settings: secrets/env from `.env`, business policy from `policy.yaml`, personas from `personas.yaml`.

Nothing business-relevant is hard-coded in code; change the YAML or env and restart.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), extra="ignore")

    secret_key: str = "dev-insecure-secret-change-me"
    # Absolute by default: a relative URL would resolve against the process's cwd, which depends
    # on how the server was launched (every Makefile target does `cd backend` first).
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_ROOT / 'data' / 'saksham.db'}"
    public_base_url: str = "http://localhost:8000"
    mock_services_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    log_level: str = "INFO"

    messaging_mode: str = "simulated"  # whatsapp | simulated | both
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_api_version: str = "v25.0"
    whatsapp_verify_token: str = "saksham-verify-token"
    whatsapp_app_secret: str = ""
    demo_recipient_number: str = ""
    whatsapp_business_number: str = ""
    whatsapp_consent_template: str = "hello_world"
    whatsapp_consent_template_lang: str = "en_US"  # or "auto" → en / hi / mr by applicant language
    whatsapp_consent_template_params: str = ""  # comma list of placeholders, e.g. "name,url" ("" for hello_world)
    whatsapp_status_template: str = ""  # optional: template for results when the 24h window is closed
    whatsapp_status_template_lang: str = "en_US"
    whatsapp_status_template_params: str = "name,url"

    gemini_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"
    llm_timeout_seconds: float = 6.0
    llm_fallback_only: bool = False

    demo_dealer_name: str = "dealer_01"
    ml_artifacts_dir: str = str(BACKEND_ROOT / "ml" / "artifacts")
    frontend_dist_dir: str = str(REPO_ROOT / "frontend" / "dist")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# ───────────── policy.yaml models ─────────────
class BureauPolicy(BaseModel):
    bypass_threshold: int = 700


class DecisionPolicy(BaseModel):
    approve_cutoff: float = 650
    borderline_enabled: bool = True
    borderline_floor: float = 600
    borderline_ticket_factor: float = 0.7
    min_sources_for_scoring: int = 2
    max_pd_for_approval: float | None = None
    comfortable_emi_ratio: float = 0.33


class ScorecardPolicy(BaseModel):
    pdo: float = 60
    target_score: float = 650
    target_pd: float = 0.07
    offset: float | None = None
    min_score: float = 300
    max_score: float = 900

    @property
    def factor(self) -> float:
        return self.pdo / math.log(2)

    @property
    def resolved_offset(self) -> float:
        if self.offset is not None:
            return self.offset
        odds = (1 - self.target_pd) / self.target_pd
        return self.target_score - self.factor * math.log(odds)


class IngestionPolicy(BaseModel):
    per_source_timeout_seconds: float = 3.0
    outage_sleep_seconds: float = 5.0


class SessionPolicy(BaseModel):
    ttl_minutes: int = 15


class ConsentPolicy(BaseModel):
    ttl_days: int = 182
    purpose_template: str = "Alternative credit assessment for {product} loan"
    groups: list[str] = Field(default_factory=lambda: ["aa", "telecom", "business"])


class ProductPolicy(BaseModel):
    label: str
    ticket: float
    tenure_months: int
    emi: float | None = None
    flat_rate: float = 0.14

    @property
    def monthly_emi(self) -> float:
        if self.emi is not None:
            return self.emi
        years = self.tenure_months / 12
        return round(self.ticket * (1 + self.flat_rate * years) / self.tenure_months, 2)


class LanguagePolicy(BaseModel):
    supported: list[str] = ["en", "hi", "mr"]
    default: str = "en"


class TierPolicy(BaseModel):
    min_behaviour_score: int
    limits: dict[str, float]


class LadderPolicy(BaseModel):
    initial_score: int = 50
    max_score: int = 100
    min_score: int = 0
    deltas: dict[str, int] = {"ON_TIME": 5, "LATE": -8, "MISSED": -15}
    tier_order: list[str] = ["STARTER", "GROWTH", "ESTABLISHED"]
    tiers: dict[str, TierPolicy]


class MessagingPolicy(BaseModel):
    whatsapp_window_hours: int = 24
    consent_prefill_text: str = "Hi Saksham, I have given my consent."


class AdvisoryPolicy(BaseModel):
    max_steps: int = 3
    forbidden_phrases: list[str] = []
    cache_size: int = 256


class MLLabelPolicy(BaseModel):
    cw_slope: float = 5.5          # logit points per unit of (0.5 - creditworthiness)
    burden_slope: float = 3.0      # logit points per unit of (true EMI/income - 0.25)
    interaction: float = 2.0       # extra risk when a low-cw applicant is also over-burdened
    noise_sd: float = 0.6          # unobservable idiosyncratic noise


class MLPolicy(BaseModel):
    n_applicants: int = 20000
    seed: int = 42
    target_default_rate: float = 0.10
    split: dict[str, float] = {"train": 0.70, "val": 0.15, "test": 0.15}
    drop_source_prob: float = 0.06  # chance a source is missing (outage / no consent) in a training row
    product_mix: dict[str, dict[str, float]] = {}
    label: MLLabelPolicy = MLLabelPolicy()


class MockPolicy(BaseModel):
    as_of_date: str = ""  # ISO date; empty → today

    def resolve_as_of(self):
        from datetime import date

        return date.fromisoformat(self.as_of_date) if self.as_of_date else date.today()


class FeaturePolicy(BaseModel):
    low_balance_threshold: float = 500
    bounce_window_days: int = 90
    gst_margin: float = 0.18
    mandi_margin: float = 0.45
    income_blend_weights: dict[str, float] = {"aa": 0.5, "gst": 0.3, "mandi": 0.3}


class WithdrawalPolicy(BaseModel):
    reasons: list[str] = []


class Policy(BaseModel):
    policy_version: str = "v1.0"
    bureau: BureauPolicy = BureauPolicy()
    decision: DecisionPolicy = DecisionPolicy()
    scorecard: ScorecardPolicy = ScorecardPolicy()
    ingestion: IngestionPolicy = IngestionPolicy()
    session: SessionPolicy = SessionPolicy()
    consent: ConsentPolicy = ConsentPolicy()
    products: dict[str, ProductPolicy]
    languages: LanguagePolicy = LanguagePolicy()
    ladder: LadderPolicy
    messaging: MessagingPolicy = MessagingPolicy()
    advisory: AdvisoryPolicy = AdvisoryPolicy()
    ml: MLPolicy = MLPolicy()
    mock: MockPolicy = MockPolicy()
    features: FeaturePolicy = FeaturePolicy()
    withdrawal: WithdrawalPolicy = WithdrawalPolicy()


class Settings:
    """Aggregate of env settings + policy + personas + reason codes."""

    def __init__(self, env: EnvSettings, policy: Policy, personas: list[dict[str, Any]], reason_codes: dict[str, Any]):
        self.env = env
        self.policy = policy
        self.personas = personas
        self.reason_codes = reason_codes

    def masked_dump(self) -> dict[str, Any]:
        """Config dump safe for logs/UI: secrets are masked."""
        from app.core.security import mask_secret

        d = self.env.model_dump()
        for k in ("secret_key", "whatsapp_access_token", "whatsapp_app_secret", "gemini_api_key", "whatsapp_verify_token"):
            d[k] = mask_secret(d.get(k, ""))
        return d


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = EnvSettings()
    policy = Policy.model_validate(_load_yaml(REPO_ROOT / "policy.yaml"))
    personas = _load_yaml(REPO_ROOT / "personas.yaml").get("personas", [])
    reason_codes = _load_yaml(REPO_ROOT / "reason_codes.yaml")
    return Settings(env, policy, personas, reason_codes)


def reset_settings_cache() -> None:
    get_settings.cache_clear()
