from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DemoOptions(BaseModel):
    simulate_outage: list[Literal["aa", "telecom", "business"]] = Field(default_factory=list)


class CreateApplicationRequest(BaseModel):
    mobile_number: str = Field(min_length=10, max_length=16)
    pan_token: str = Field(min_length=1, max_length=64)
    aadhaar_token: str = Field(min_length=1, max_length=64)
    requested_product_sku: str
    applicant_name: str = Field(default="", max_length=120)
    preferred_language: str = "en"
    persona_name: str | None = None
    demo_options: DemoOptions | None = None


class Grants(BaseModel):
    aa: bool = False
    telecom: bool = False
    business: bool = False


class AuthorizeRequest(BaseModel):
    session_id: str
    grants: Grants
    purpose: str | None = None


class DenyRequest(BaseModel):
    session_id: str


class WithdrawRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=64)


class RevokeRequest(BaseModel):
    consent_id: str


class RepaymentEventRequest(BaseModel):
    loan_id: str
    status: Literal["ON_TIME", "LATE", "MISSED"]


class SimulateRepaymentsRequest(BaseModel):
    loan_id: str
    count: int = Field(default=6, ge=1, le=60)
    status: Literal["ON_TIME", "LATE", "MISSED"] = "ON_TIME"
