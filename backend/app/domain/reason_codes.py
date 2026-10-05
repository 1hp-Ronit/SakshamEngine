"""Reason-code catalog backed by reason_codes.yaml."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings



class ReasonCatalog:
    def __init__(self, raw: dict[str, Any]):
        self.codes: dict[str, dict[str, Any]] = raw.get("reason_codes", {})
        self.by_feature = {v["feature"]: (k, v) for k, v in self.codes.items()}
        self.templates: dict[str, Any] = raw.get("advisory_templates", {})

    def code_for(self, feature: str) -> str | None:
        hit = self.by_feature.get(feature)
        return hit[0] if hit else None

    def entry(self, feature: str) -> dict[str, Any] | None:
        hit = self.by_feature.get(feature)
        return hit[1] if hit else None

    def reportable(self, feature: str) -> bool:
        e = self.entry(feature)
        return bool(e) and e.get("reportable", True)

    def text(self, feature: str, positive: bool, lang: str = "en") -> str:
        e = self.entry(feature)
        if not e:
            return feature.replace("_", " ")
        block = e["positive" if positive else "negative"]
        return block.get(lang) or block["en"]

    def label(self, feature: str, lang: str = "en") -> str:
        e = self.entry(feature)
        return (e["label"].get(lang) or e["label"]["en"]) if e else feature.replace("_", " ")

    def texts(self, feature: str, positive: bool) -> dict[str, str]:
        return {lang: self.text(feature, positive, lang) for lang in get_settings().policy.languages.supported}

    def action(self, feature: str, lang: str = "en") -> str:
        e = self.entry(feature)
        if not e:
            return ""
        return e["action"].get(lang) or e["action"]["en"]

    def template(self, key: str, lang: str) -> str:
        t = self.templates[key]
        return t.get(lang) or t["en"]

    def product_label(self, sku: str, lang: str) -> str:
        labels = self.templates.get("product_labels", {}).get(sku)
        return (labels.get(lang) or labels["en"]) if labels else sku.replace("_", " ").title()


@lru_cache(maxsize=1)
def get_catalog() -> ReasonCatalog:
    return ReasonCatalog(get_settings().reason_codes)
