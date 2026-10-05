from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CreateApplicationRequest, WithdrawRequest
from app.core.database import get_session
from app.services import orchestrator, queries

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("/create")
async def create(body: CreateApplicationRequest, db: AsyncSession = Depends(get_session)):
    return await orchestrator.create_application(db, body.model_dump())


@router.get("")
async def list_applications(outcome: str = "APPROVED", limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_session)):
    """Decided applications with the given outcome (default APPROVED): the dashboard's approved-loans list."""
    return await queries.approved_loans_view(db, outcome=outcome, limit=limit)


@router.post("/{application_id}/withdraw")
async def withdraw(application_id: str, body: WithdrawRequest, db: AsyncSession = Depends(get_session)):
    """Withdraw an approval (recorded with a reason; audit and consent history are kept)."""
    return await orchestrator.withdraw_approval(db, application_id, body.reason)


@router.get("/{application_id}/ledger")
async def get_ledger(application_id: str, db: AsyncSession = Depends(get_session)):
    """Consent and data-rights ledger for one application."""
    app = await orchestrator.load_application(db, application_id)
    return await queries.ledger_view(db, app)


@router.get("/{application_id}")
async def get_application(application_id: str, db: AsyncSession = Depends(get_session)):
    app = await orchestrator.load_application(db, application_id)
    return await queries.application_view(db, app)


@router.get("/{application_id}/trace")
async def get_trace(application_id: str, db: AsyncSession = Depends(get_session)):
    app = await orchestrator.load_application(db, application_id)
    return await queries.trace_view(db, app)


@router.get("/{application_id}/decision")
async def get_decision(application_id: str, db: AsyncSession = Depends(get_session)):
    app = await orchestrator.load_application(db, application_id)
    return await queries.decision_view(db, app)


@router.get("/{application_id}/plan")
async def get_plan(application_id: str, lang: str | None = None, db: AsyncSession = Depends(get_session)):
    app = await orchestrator.load_application(db, application_id)
    return await queries.plan_view(db, app, lang)
