from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AuthorizeRequest, DenyRequest, RevokeRequest
from app.core.database import get_session
from app.services import orchestrator

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


@router.get("/session/{session_id}")
async def session_info(session_id: str, db: AsyncSession = Depends(get_session)):
    """What the mobile consent page renders (applicant, purpose, TTL countdown, wa.me link)."""
    return await orchestrator.consent_session_view(db, session_id)


@router.post("/authorize")
async def authorize(body: AuthorizeRequest, db: AsyncSession = Depends(get_session)):
    return await orchestrator.grant_consent(db, body.session_id, body.grants.model_dump(), body.purpose)


@router.post("/deny")
async def deny(body: DenyRequest, db: AsyncSession = Depends(get_session)):
    return await orchestrator.deny_consent(db, body.session_id)


@router.post("/revoke")
async def revoke(body: RevokeRequest, db: AsyncSession = Depends(get_session)):
    return await orchestrator.revoke_consent(db, body.consent_id)
