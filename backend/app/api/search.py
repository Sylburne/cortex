from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.database import get_db
from app.api.auth import verify_api_key
from app.models.chunk import Chunk
from app.models.source import Source
from app.schemas.chunk import SearchRequest, SearchResponse, ChunkResult, RetrieveRequest, RetrieveResponse, SourceGroup
from app.services.embeddings import get_embedding_provider

router = APIRouter(prefix="/notebooks/{notebook_id}", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    notebook_id: str,
    body: SearchRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Vector similarity search across chunks in a notebook."""
    embedder = get_embedding_provider()
    query_embedding = await embedder.embed([body.query])
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    vec_str = "[" + ",".join(str(x) for x in query_embedding[0]) + "]"

    sql = text("""
        SELECT c.id as chunk_id, c.source_id, c.chunk_index, c.content, c.metadata,
               s.filename as source_filename, s.path as source_path,
               1 - (c.embedding <=> :vec::vector) as score
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        WHERE c.notebook_id = :nb_id AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :vec::vector
        LIMIT :top_k
    """)
    result = await db.execute(sql, {"vec": vec_str, "nb_id": notebook_id, "top_k": body.top_k})
    rows = result.fetchall()

    results = []
    for row in rows:
        results.append(ChunkResult(
            chunk_id=row.chunk_id, source_id=row.source_id,
            source_filename=row.source_filename, source_path=row.source_path,
            content=row.content, chunk_index=row.chunk_index,
            score=float(row.score), metadata=row.metadata or {},
        ))

    return SearchResponse(results=results, query=body.query, total=len(results))


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    notebook_id: str,
    body: RetrieveRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Semantic retrieval grouped by source document."""
    embedder = get_embedding_provider()
    query_embedding = await embedder.embed([body.query])
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    vec_str = "[" + ",".join(str(x) for x in query_embedding[0]) + "]"

    sql = text("""
        SELECT c.id as chunk_id, c.source_id, c.chunk_index, c.content, c.metadata,
               s.filename as source_filename, s.path as source_path,
               1 - (c.embedding <=> :vec::vector) as score
        FROM chunks c
        JOIN sources s ON c.source_id = s.id
        WHERE c.notebook_id = :nb_id AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :vec::vector
        LIMIT :top_k
    """)
    result = await db.execute(sql, {"vec": vec_str, "nb_id": notebook_id, "top_k": body.top_k * 3})
    rows = result.fetchall()

    # Group by source
    source_map: dict = {}
    for row in rows:
        sid = row.source_id
        if sid not in source_map:
            source_map[sid] = {
                "source_id": sid, "source_filename": row.source_filename,
                "source_path": row.source_path, "chunks": [], "max_score": 0.0,
            }
        chunk_result = ChunkResult(
            chunk_id=row.chunk_id, source_id=sid,
            source_filename=row.source_filename, source_path=row.source_path,
            content=row.content, chunk_index=row.chunk_index,
            score=float(row.score), metadata=row.metadata or {},
        )
        source_map[sid]["chunks"].append(chunk_result)
        source_map[sid]["max_score"] = max(source_map[sid]["max_score"], float(row.score))

    groups = [SourceGroup(**v) for v in sorted(source_map.values(), key=lambda x: x["max_score"], reverse=True)][:body.top_k]

    return RetrieveResponse(groups=groups, query=body.query, total=len(groups))


@router.get("/list")
async def list_all(
    notebook_id: str,
    type_filter: str = "source",
    page: int = 1,
    page_size: int = 20,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List sources or compiled knowledge cards."""
    if type_filter == "card":
        from app.models.knowledge_card import KnowledgeCard
        q = select(KnowledgeCard).where(KnowledgeCard.notebook_id == notebook_id).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        cards = result.scalars().all()
        return {"type": "card", "items": [{"id": str(c.id), "title": c.title, "card_type": c.card_type, "status": c.status} for c in cards]}
    else:
        q = select(Source).where(Source.notebook_id == notebook_id, Source.is_dir == 0).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        sources = result.scalars().all()
        return {"type": "source", "items": [{"id": str(s.id), "filename": s.filename, "path": s.path, "status": s.status, "file_type": s.file_type} for s in sources]}
