from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
from uuid import uuid4

from app.database import get_db
from app.api.auth import verify_api_key
from app.config import settings
from app.models.rag import RagSession, RagMessage
from app.models.chunk import Chunk
from app.schemas.rag import RagSessionCreate, RagSessionResponse, RagMessageRequest, RagMessageResponse, Citation
from app.services.embeddings import get_embedding_provider
from app.services.rag_engine import generate_answer
from app.services import honcho_memory

router = APIRouter(prefix="/notebooks/{notebook_id}/rag", tags=["rag"])


@router.post("/sessions", response_model=RagSessionResponse)
async def create_session(
    notebook_id: str,
    body: RagSessionCreate,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    session = RagSession(
        notebook_id=notebook_id,
        owner_id=owner_id,
        provider=body.provider or settings.default_llm_provider,
        model=body.model or settings.default_llm_model,
        system_prompt=body.system_prompt,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=RagSessionResponse)
async def get_session(
    notebook_id: str,
    session_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(RagSession).where(RagSession.id == session_id, RagSession.notebook_id == notebook_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    notebook_id: str,
    session_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(RagSession).where(RagSession.id == session_id, RagSession.notebook_id == notebook_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    notebook_id: str,
    session_id: str,
    body: RagMessageRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get RAG answer (non-streaming for simplicity)."""
    # Get session
    q = select(RagSession).where(RagSession.id == session_id, RagSession.notebook_id == notebook_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    user_msg = RagMessage(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)

    # Store in Honcho (long-term memory)
    if honcho_memory.is_enabled():
        await honcho_memory.store_message(owner_id, session_id, "user", body.content)

    # Get conversation history
    history_q = select(RagMessage).where(RagMessage.session_id == session_id).order_by(RagMessage.created_at)
    history_rows = (await db.execute(history_q)).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    # Retrieve relevant chunks
    embedder = get_embedding_provider()
    query_embedding = await embedder.embed([body.content])

    from sqlalchemy import text as sql_text
    vec_str = "[" + ",".join(str(x) for x in query_embedding[0]) + "]"
    search_sql = sql_text("""
        SELECT c.id as chunk_id, c.source_id, c.chunk_index, c.content, c.metadata,
               s.filename as source_filename, s.path as source_path,
               1 - (c.embedding <=> :vec::vector) as score
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        WHERE c.notebook_id = :nb_id AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :vec::vector
        LIMIT :top_k
    """)
    result = await db.execute(search_sql, {
        "vec": vec_str, "nb_id": notebook_id, "top_k": settings.rag_top_k
    })
    rows = result.fetchall()

    citations = []
    context_chunks = []
    chunk_ids = []
    for row in rows:
        if row.score >= settings.rag_similarity_threshold:
            context_chunks.append(row.content)
            chunk_ids.append(row.chunk_id)
            citations.append(Citation(
                chunk_id=row.chunk_id, source_id=row.source_id,
                source_filename=row.source_filename, source_path=row.source_path,
                content=row.content[:200], score=float(row.score),
            ))

    # Generate answer
    system_prompt = session.system_prompt or "You are a helpful knowledge base assistant. Answer based on the provided context."

    # Inject Honcho user insights into system prompt if available
    if honcho_memory.is_enabled():
        user_context = await honcho_memory.get_session_context(session_id, tokens=2000)
        if user_context:
            system_prompt += f"\n\nUser context from memory: {user_context}"

    answer = await generate_answer(
        provider=session.provider, model=session.model,
        system_prompt=system_prompt, history=history,
        context_chunks=context_chunks, question=body.content,
    )

    # Save assistant message
    assistant_msg = RagMessage(
        session_id=session_id, role="assistant", content=answer,
        source_chunk_ids=chunk_ids,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # Store assistant response in Honcho
    if honcho_memory.is_enabled():
        await honcho_memory.store_message(owner_id, session_id, "assistant", answer)

    return RagMessageResponse(
        message_id=assistant_msg.id, content=answer,
        citations=citations, provider=session.provider, model=session.model,
    )
