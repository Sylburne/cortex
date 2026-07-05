from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.api import notebooks, sources, search, rag, compile, memory
from app.services import honcho_memory


async def _ensure_pgvector(conn):
    """Enable the vector extension (Neon supports it natively)."""
    try:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as e:
        # Some hosts don't allow CREATE EXTENSION; skip if already present
        print(f"[startup] pgvector extension note: {e}")


async def _ensure_hnsw_index(conn, dim: int):
    """Create the HNSW index for the configured embedding dimension.

    SQLAlchemy's Vector(dim) in the model handles the column definition;
    we create the index explicitly in case the table was created without it.
    """
    try:
        await conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS ix_chunks_embedding_cosine "
            f"ON chunks USING hnsw ((embedding::vector({dim})) vector_cosine_ops)"
        ))
    except Exception as e:
        # Index may already exist with different params; log and continue
        print(f"[startup] HNSW index note: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # 1. Enable pgvector extension first (required before Vector columns)
        await _ensure_pgvector(conn)
        # 2. Create all tables (chunks.embedding uses Vector type)
        await conn.run_sync(Base.metadata.create_all)
        # 3. Create HNSW index for cosine similarity search
        await _ensure_hnsw_index(conn, settings.embedding_dimensions)
    print(f"[startup] DB ready | embeddings={settings.embedding_provider}/{settings.embedding_model} | dim={settings.embedding_dimensions}")
    print(f"[startup] Honcho: {'enabled' if honcho_memory.is_enabled() else 'disabled (set HONCHO_API_KEY to enable)'}")
    yield
    await engine.dispose()


app = FastAPI(
    title="QMind API",
    description="Personal knowledge base with RAG, vector search, and multi-provider AI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notebooks.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(compile.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"service": "qmind", "version": "0.1.0", "status": "running", "honcho": honcho_memory.is_enabled()}


@app.get("/health")
async def health():
    return {"status": "ok", "honcho": honcho_memory.is_enabled()}
