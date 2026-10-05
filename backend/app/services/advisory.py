"""Vernacular action plan from the top negative reason codes.

LLM (Gemini) when available → strict JSON → validated against guardrails → else deterministic templates (en/hi/mr, works offline).
"""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any

from app.adapters.interfaces import LLMClient
from app.adapters.llm.fallback import DeterministicFallbackClient
from app.adapters.llm.gemini import GeminiLLMClient
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.reason_codes import ReasonCatalog, get_catalog

log = get_logger("advisory")

# Names given to the LLM. Languages listed in policy.yaml but missing here are passed to the model by their code.
LANG_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)", "mr": "Marathi (Devanagari script)"}
DEVANAGARI_LANGS = {"hi", "mr"}  # languages validated for Devanagari script

SYSTEM_PROMPT = """You are a financial advisor writing a simple, encouraging action plan for a loan applicant in {language}. The applicant's name is {first_name}.

You will receive up to 3 areas where the applicant can improve, each with a suggested action. For each, write one clear, actionable step in simple everyday language that a person in a small town can understand.

Rules:
- Never reveal the score or any formula
- Never promise approval or guarantee any outcome
- Never invent numbers not provided to you
- Use a respectful, encouraging tone
- Maximum 3 steps
- Write ONLY in {language}
- Output strict JSON: {{"greeting": "...", "summary": "...", "steps": ["...", "...", "..."], "closing": "..."}}"""

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


@dataclass
class Plan:
    greeting: str
    summary: str
    steps: list[str]
    closing: str
    language: str
    source: str  # llm | fallback
    reason_codes: list[str] = field(default_factory=list)
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text.translate(_DEVANAGARI_DIGITS)))


def _devanagari_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters) if letters else 0.0


class AdvisoryService:
    def __init__(self, llm: LLMClient | None = None, catalog: ReasonCatalog | None = None):
        env = get_settings().env
        self.llm: LLMClient = llm or (GeminiLLMClient(env) if env.gemini_api_key and not env.llm_fallback_only else DeterministicFallbackClient())
        self.catalog = catalog or get_catalog()
        self._cache: OrderedDict[tuple, Plan] = OrderedDict()

    # ── deterministic ──
    def render_deterministic(self, negatives: list[dict], lang: str, sku: str, first_name: str) -> Plan:
        c = self.catalog
        steps = [c.action(d["feature"], lang) for d in negatives if c.action(d["feature"], lang)]
        steps = list(dict.fromkeys(steps))[: get_settings().policy.advisory.max_steps]
        if not steps:
            steps = [c.template("generic_step", lang)]
        return Plan(
            greeting=c.template("greeting", lang).format(name=first_name or "") .replace("  ", " ").replace(" ,", ","),
            summary=c.template("summary", lang).format(product=c.product_label(sku, lang)),
            steps=steps, closing=c.template("closing", lang), language=lang, source="fallback",
            reason_codes=[d["reason_code"] for d in negatives if d.get("reason_code")],
        )

    # ── LLM + guardrails ──
    def _validate(self, raw: str, lang: str, allowed_numbers: set[str]) -> dict[str, Any]:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        for k in ("greeting", "summary", "closing"):
            if not isinstance(data.get(k), str) or not data[k].strip():
                raise ValueError(f"missing/empty '{k}'")
        steps = data.get("steps")
        if not isinstance(steps, list) or not (1 <= len(steps) <= get_settings().policy.advisory.max_steps) or not all(isinstance(s, str) and s.strip() for s in steps):
            raise ValueError("steps must be 1-3 non-empty strings")
        blob = " ".join([data["greeting"], data["summary"], *steps, data["closing"]])
        low = blob.lower()
        for phrase in get_settings().policy.advisory.forbidden_phrases:
            if phrase.lower() in low:
                raise ValueError(f"forbidden phrase: {phrase!r}")
        invented = _numbers(blob) - allowed_numbers
        if invented:
            raise ValueError(f"invented numbers: {sorted(invented)}")
        ratio = _devanagari_ratio(blob)
        if lang in DEVANAGARI_LANGS and ratio < 0.4:
            raise ValueError("not written in Devanagari script")
        if lang == "en" and ratio > 0.1:
            raise ValueError("expected English")
        return {"greeting": data["greeting"].strip(), "summary": data["summary"].strip(), "steps": [s.strip() for s in steps], "closing": data["closing"].strip()}

    async def generate_plan(self, negatives: list[dict], lang: str, sku: str, first_name: str) -> Plan:
        lang = lang if lang in get_settings().policy.languages.supported else get_settings().policy.languages.default
        codes = tuple(d.get("reason_code") for d in negatives)
        key = (codes, lang, sku, first_name)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        plan = self.render_deterministic(negatives, lang, sku, first_name)
        if self.llm.available and negatives:
            areas = [{"area": self.catalog.label(d["feature"], lang), "problem": self.catalog.text(d["feature"], False, lang), "suggested_action": self.catalog.action(d["feature"], lang)} for d in negatives]
            user = json.dumps({"applicant_first_name": first_name, "loan_product": self.catalog.product_label(sku, lang), "areas_to_improve": areas}, ensure_ascii=False)
            try:
                raw = await self.llm.complete_json(SYSTEM_PROMPT.format(language=LANG_NAMES.get(lang, lang), first_name=first_name or "the applicant"), user)
                out = self._validate(raw, lang, _numbers(user))
                plan = Plan(**out, language=lang, source="llm", reason_codes=[c for c in codes if c])
            except Exception as exc:  # noqa: BLE001 — any failure → deterministic plan
                plan.fallback_reason = f"{type(exc).__name__}: {exc}"[:200]
                log.warning("LLM advisory fell back to templates: %s", plan.fallback_reason)
        elif not self.llm.available:
            plan.fallback_reason = "LLM not configured / fallback-only mode"

        self._cache[key] = plan
        while len(self._cache) > get_settings().policy.advisory.cache_size:
            self._cache.popitem(last=False)
        return plan

    def clear_cache(self) -> None:
        self._cache.clear()


def render_plan_message(plan: Plan, link: str | None, catalog: ReasonCatalog | None = None) -> str:
    c = catalog or get_catalog()
    lines = [plan.greeting, "", plan.summary, ""]
    lines += [f"{i}. {s}" for i, s in enumerate(plan.steps, 1)]
    lines += ["", plan.closing]
    if link:
        lines += ["", c.template("plan_link", plan.language).format(url=link)]
    return "\n".join(lines)


_service: AdvisoryService | None = None


def get_advisory() -> AdvisoryService:
    global _service
    if _service is None:
        _service = AdvisoryService()
    return _service


def reset_advisory() -> None:
    global _service
    _service = None
