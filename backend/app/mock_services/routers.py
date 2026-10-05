"""/mock/* — stand-ins for bureau, Account Aggregator, telecom and business-record vendors.

Data endpoints REJECT requests without a valid, unrevoked consent token covering that source group.
`?simulate_outage=true` makes a source hang past the caller's timeout (graceful-degradation demo).
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.mock_services import generators as g
from app.mock_services.personas import resolve_bureau, resolve_profile
from app.services import consent as consent_service

router = APIRouter(prefix="/mock", tags=["mock"])


class BureauRequest(BaseModel):
    mobile_hash: str
    pan_hash: str | None = None


@router.post("/bureau/check")
async def bureau_check(body: BureauRequest, simulate_outage: bool = False):
    await _maybe_outage(simulate_outage)
    return resolve_bureau(body.mobile_hash)


def _guard(group: str):
    async def dep(
        mobile_hash: Annotated[str, Query()],
        x_consent_token: Annotated[str | None, Header()] = None,
        db: AsyncSession = Depends(get_session),
    ) -> str:
        await consent_service.verify_for_source(db, x_consent_token, group, mobile_hash)
        return mobile_hash

    return dep


async def _maybe_outage(flag: bool) -> None:
    if flag:
        await asyncio.sleep(get_settings().policy.ingestion.outage_sleep_seconds)


def _as_of():
    return get_settings().policy.mock.resolve_as_of()


def _or_no_data(payload):
    if payload is None:
        raise AppError("NO_DATA", "No records found for this customer at this source.", 404)
    return payload


@router.get("/aa/bank-statement")
async def aa_bank_statement(mobile_hash: str = Depends(_guard("aa")), simulate_outage: bool = False):
    await _maybe_outage(simulate_outage)
    return _or_no_data(g.generate_aa_payload(resolve_profile(mobile_hash), _as_of()))


@router.get("/telecom/recharge")
async def telecom_recharge(mobile_hash: str = Depends(_guard("telecom")), simulate_outage: bool = False):
    await _maybe_outage(simulate_outage)
    return _or_no_data(g.generate_telecom_payload(resolve_profile(mobile_hash), _as_of()))


@router.get("/business/gst-returns")
async def business_gst(mobile_hash: str = Depends(_guard("business")), simulate_outage: bool = False):
    await _maybe_outage(simulate_outage)
    return _or_no_data(g.generate_gst_payload(resolve_profile(mobile_hash), _as_of()))


@router.get("/business/mandi-receipts")
async def business_mandi(mobile_hash: str = Depends(_guard("business")), simulate_outage: bool = False):
    await _maybe_outage(simulate_outage)
    return _or_no_data(g.generate_mandi_payload(resolve_profile(mobile_hash), _as_of()))
