from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services import orchestrator, queries

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


@router.get("/{application_id}")
async def outbox(application_id: str, db: AsyncSession = Depends(get_session)):
    """Everything sent for this application, regardless of provider — feeds the dashboard's message log."""
    await orchestrator.load_application(db, application_id)
    return {"application_id": application_id, "messages": await queries.messages_view(db, application_id)}
