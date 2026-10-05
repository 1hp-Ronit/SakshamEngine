from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import RepaymentEventRequest
from app.core.database import get_session
from app.services import ladder

router = APIRouter(prefix="/api/v1", tags=["lms"])


@router.post("/lms/repayment-event")
async def repayment_event(body: RepaymentEventRequest, db: AsyncSession = Depends(get_session)):
    return await ladder.record_event(db, body.loan_id, body.status)


@router.get("/customers/{customer_id}/ladder")
async def customer_ladder(customer_id: str, db: AsyncSession = Depends(get_session)):
    return await ladder.get_ladder_for_customer(db, customer_id)
