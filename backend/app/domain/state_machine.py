from __future__ import annotations

from enum import Enum

from app.core.errors import AppError


class ApplicationStatus(str, Enum):
    CREATED = "CREATED"
    BUREAU_CHECKED = "BUREAU_CHECKED"
    BYPASSED_TO_LOS = "BYPASSED_TO_LOS"
    AWAITING_CONSENT = "AWAITING_CONSENT"
    CONSENT_DENIED = "CONSENT_DENIED"
    EXPIRED = "EXPIRED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    INGESTING = "INGESTING"
    SCORED = "SCORED"
    APPROVED = "APPROVED"
    CONDITIONAL_APPROVAL = "CONDITIONAL_APPROVAL"  # borderline band
    DECLINED_WITH_PLAN = "DECLINED_WITH_PLAN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


S = ApplicationStatus

TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    S.CREATED: {S.BUREAU_CHECKED},
    S.BUREAU_CHECKED: {S.BYPASSED_TO_LOS, S.AWAITING_CONSENT},
    S.AWAITING_CONSENT: {S.CONSENT_DENIED, S.EXPIRED, S.CONSENT_GRANTED},
    S.CONSENT_GRANTED: {S.INGESTING},
    S.INGESTING: {S.SCORED, S.INSUFFICIENT_DATA},
    S.SCORED: {S.APPROVED, S.CONDITIONAL_APPROVAL, S.DECLINED_WITH_PLAN, S.INSUFFICIENT_DATA},
}

TERMINAL = {S.BYPASSED_TO_LOS, S.CONSENT_DENIED, S.EXPIRED, S.APPROVED, S.CONDITIONAL_APPROVAL, S.DECLINED_WITH_PLAN, S.INSUFFICIENT_DATA}
DECISIONS = {S.APPROVED, S.CONDITIONAL_APPROVAL, S.DECLINED_WITH_PLAN, S.INSUFFICIENT_DATA}


def can_transition(src: ApplicationStatus, dst: ApplicationStatus) -> bool:
    return dst in TRANSITIONS.get(src, set())


def validate_transition(src: str | ApplicationStatus, dst: str | ApplicationStatus) -> ApplicationStatus:
    src, dst = ApplicationStatus(src), ApplicationStatus(dst)
    if not can_transition(src, dst):
        raise AppError("INVALID_TRANSITION", f"Cannot move application from {src.value} to {dst.value}", 409)
    return dst
