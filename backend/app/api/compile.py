from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4, UUID as UUIDType
import asyncio

from app.database import get_db
from app.api.auth import verify_api_key
from app.models.knowledge_card import KnowledgeCard
from app.models.source import Source
from app.models.chunk import Chunk
from app.schemas.compile import (
    CompileRequest, CompileJobResponse, CompileStatusResponse,
    KnowledgeCardResponse, LintRequest, LintResponse, LintIssue,
)
from app.services.compiler import compile_source_to_card
from app.services.linter import lint_card

router = APIRouter(prefix="/notebooks/{notebook_id}", tags=["compile"])

# In-memory job tracking (replace with Redis/DB for production)
_compile_jobs: dict = {}


@router.post("/compile", response_model=CompileJobResponse)
async def trigger_compile(
    notebook_id: str,
    body: CompileRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Trigger async compilation of sources into knowledge cards."""
    job_id = uuid4()

    # Get sources to compile
    if body.source_ids:
        q = select(Source).where(
            Source.id.in_([str(sid) for sid in body.source_ids]),
            Source.notebook_id == notebook_id,
            Source.is_dir == 0,
            Source.status == "ready",
        )
    else:
        q = select(Source).where(
            Source.notebook_id == notebook_id,
            Source.is_dir == 0,
            Source.status == "ready",
        )
    sources = (await db.execute(q)).scalars().all()

    _compile_jobs[str(job_id)] = {
        "status": "processing", "progress": 0,
        "cards_created": 0, "error": None, "total": len(sources),
    }

    # Process in background (simplified - in production use ARQ/Celery)
    for i, source in enumerate(sources):
        try:
            chunks_q = select(Chunk).where(Chunk.source_id == source.id).order_by(Chunk.chunk_index)
            chunks = (await db.execute(chunks_q)).scalars().all()
            chunk_texts = [c.content for c in chunks]

            if chunk_texts:
                card_content = await compile_source_to_card(
                    source_filename=source.filename,
                    chunks=chunk_texts,
                    card_type=body.card_type,
                )
                card = KnowledgeCard(
                    notebook_id=notebook_id,
                    source_ids=[source.id],
                    title=source.filename,
                    content=card_content,
                    card_type=body.card_type,
                    status="compiled",
                )
                db.add(card)
                await db.commit()

            _compile_jobs[str(job_id)]["cards_created"] = i + 1
            _compile_jobs[str(job_id)]["progress"] = int((i + 1) / len(sources) * 100)
        except Exception as e:
            _compile_jobs[str(job_id)]["error"] = str(e)

    _compile_jobs[str(job_id)]["status"] = "completed"
    _compile_jobs[str(job_id)]["progress"] = 100

    return CompileJobResponse(job_id=job_id, status="processing", notebook_id=notebook_id, card_type=body.card_type)


@router.get("/compile/jobs/{job_id}", response_model=CompileStatusResponse)
async def get_compile_status(
    notebook_id: str,
    job_id: str,
    owner_id: str = Depends(verify_api_key),
):
    job = _compile_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return CompileStatusResponse(
        job_id=UUIDType(job_id), status=job["status"],
        progress=job["progress"], cards_created=job["cards_created"],
        error=job["error"],
    )


@router.get("/cards")
async def list_cards(
    notebook_id: str,
    page: int = 1,
    page_size: int = 20,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(KnowledgeCard).where(KnowledgeCard.notebook_id == notebook_id).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    cards = result.scalars().all()
    return {"cards": [KnowledgeCardResponse.model_validate(c) for c in cards], "total": len(cards)}


@router.get("/cards/{card_id}", response_model=KnowledgeCardResponse)
async def get_card(
    notebook_id: str,
    card_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(KnowledgeCard).where(KnowledgeCard.id == card_id, KnowledgeCard.notebook_id == notebook_id)
    card = (await db.execute(q)).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.post("/lint", response_model=LintResponse)
async def lint_notebook(
    notebook_id: str,
    body: LintRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    if body.card_id:
        q = select(KnowledgeCard).where(KnowledgeCard.id == body.card_id, KnowledgeCard.notebook_id == notebook_id)
        cards = [(await db.execute(q)).scalar_one_or_none()]
        cards = [c for c in cards if c]
    else:
        q = select(KnowledgeCard).where(KnowledgeCard.notebook_id == notebook_id)
        cards = (await db.execute(q)).scalars().all()

    all_issues = []
    for card in cards:
        issues = await lint_card(card.title, card.content, card.card_type)
        all_issues.extend(issues)

    return LintResponse(
        notebook_id=UUIDType(notebook_id),
        total_cards=len(cards),
        issues=all_issues,
        cards_checked=len(cards),
    )
