"""Processing pipeline: parse → chunk → embed on upload."""
from __future__ import annotations

import asyncio
import traceback
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source
from app.models.chunk import Chunk
from app.services.document_parser import detect_and_parse
from app.services.chunker import chunk_text
from app.services.embeddings import get_embedding_provider
from app.config import settings


async def process_source(source_id: str, notebook_id: str, db: AsyncSession) -> None:
    """Run the full pipeline for one source: parse \u2192 chunk \u2192 embed."""
    # Fetch source
    q = select(Source).where(Source.id == source_id)
    source = (await db.execute(q)).scalar_one_or_none()
    if not source:
        return

    try:
        # 1. Update status to parsing
        await _update_status(db, source_id, "parsing")

        # 2. Get text content
        #    Priority: raw_content (already extracted) > re-parse from original_content
        text = source.raw_content
        if (not text or not text.strip()) and source.original_content:
            # Re-parse from stored binary (e.g., if upload parsing failed)
            print(f"[pipeline] Re-parsing from original_content for {source.filename}")
            try:
                text = detect_and_parse(source.original_content, source.filename)
                # Store the parsed text for future use
                source.raw_content = text
                await db.flush()
            except Exception as e:
                print(f"[pipeline] Re-parse failed for {source.filename}: {e}")
                await _update_status(db, source_id, "error", f"Parse failed: {e}")
                await db.commit()
                return

        if not text or not text.strip():
            await _update_status(db, source_id, "empty")
            await db.commit()
            return

        # 3. Chunk
        await _update_status(db, source_id, "chunking")
        chunks = chunk_text(text)
        if not chunks:
            await _update_status(db, source_id, "empty")
            return

        # 4. Embed in batches (OpenAI limit: ~8191 tokens per input)
        await _update_status(db, source_id, "embedding")
        embedder = get_embedding_provider()

        # Delete any existing chunks for this source (re-upload case)
        from sqlalchemy import delete
        await db.execute(delete(Chunk).where(Chunk.source_id == source_id))
        await db.flush()

        # Process chunks in batches of 20 (to stay under token limits)
        batch_size = 20
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c["content"] for c in batch]

            try:
                embeddings = await embedder.embed(texts)
            except Exception as e:
                print(f"[pipeline] Embedding batch failed for {source_id}: {e}")
                # Store chunks without embeddings — they'll still be searchable via text
                embeddings = [None] * len(batch)

            for j, (chunk_data, embedding) in enumerate(zip(batch, embeddings)):
                chunk = Chunk(
                    source_id=source_id,
                    notebook_id=notebook_id,
                    chunk_index=i + j,
                    content=chunk_data["content"],
                    token_count=len(chunk_data["content"].split()),
                    metadata_=chunk_data.get("metadata", {}),
                    embedding=embedding,
                )
                db.add(chunk)

            await db.flush()

        # 5. Mark as ready
        await _update_status(db, source_id, "ready")
        await db.commit()
        print(f"[pipeline] Source {source_id} processed: {len(chunks)} chunks")

    except Exception as e:
        traceback.print_exc()
        await _update_status(db, source_id, "error", str(e))
        await db.commit()


async def process_source_background(source_id: str, notebook_id: str) -> None:
    """Fire-and-forget processing with its own DB session."""
    from app.database import async_session
    async with async_session() as db:
        await process_source(source_id, notebook_id, db)


async def _update_status(db: AsyncSession, source_id: str, status: str, error: str | None = None):
    await db.execute(
        update(Source).where(Source.id == source_id).values(status=status, error_message=error)
    )
    await db.flush()
