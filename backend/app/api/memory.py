"""Honcho memory endpoints (optional — only active when HONCHO_API_KEY is set)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.api.auth import verify_api_key
from app.services import honcho_memory

router = APIRouter(prefix="/memory", tags=["memory"])


class UserInsightsRequest(BaseModel):
    user_id: str = "default"
    question: str = "What topics does this user care about most?"


class UserInsightsResponse(BaseModel):
    user_id: str
    question: str
    insights: Optional[str] = None
    honcho_enabled: bool


class SessionContextRequest(BaseModel):
    session_id: str
    tokens: int = 4000


class SessionContextResponse(BaseModel):
    session_id: str
    context: Optional[str] = None
    honcho_enabled: bool


class MemoryStatusResponse(BaseModel):
    enabled: bool
    workspace_id: str
    base_url: str


@router.get("/status", response_model=MemoryStatusResponse)
async def memory_status(owner_id: str = Depends(verify_api_key)):
    """Check if Honcho memory layer is configured."""
    from app.config import settings
    return MemoryStatusResponse(
        enabled=honcho_memory.is_enabled(),
        workspace_id=settings.honcho_workspace_id,
        base_url=settings.honcho_base_url or "https://api.honcho.dev",
    )


@router.post("/insights", response_model=UserInsightsResponse)
async def get_user_insights(
    body: UserInsightsRequest,
    owner_id: str = Depends(verify_api_key),
):
    """Query what Honcho knows about a user based on their conversation history."""
    if not honcho_memory.is_enabled():
        return UserInsightsResponse(
            user_id=body.user_id,
            question=body.question,
            insights=None,
            honcho_enabled=False,
        )

    insights = await honcho_memory.get_user_insights(body.user_id, body.question)
    return UserInsightsResponse(
        user_id=body.user_id,
        question=body.question,
        insights=insights,
        honcho_enabled=True,
    )


@router.post("/context", response_model=SessionContextResponse)
async def get_session_context(
    body: SessionContextRequest,
    owner_id: str = Depends(verify_api_key),
):
    """Get Honcho's memory context for a specific session."""
    if not honcho_memory.is_enabled():
        return SessionContextResponse(
            session_id=body.session_id,
            context=None,
            honcho_enabled=False,
        )

    context = await honcho_memory.get_session_context(body.session_id, body.tokens)
    return SessionContextResponse(
        session_id=body.session_id,
        context=context,
        honcho_enabled=True,
    )
