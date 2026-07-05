from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    source_ids: Optional[list[UUID]] = None


class ChunkResult(BaseModel):
    chunk_id: UUID
    source_id: UUID
    source_filename: str
    source_path: str
    content: str
    chunk_index: int
    score: float
    metadata: dict = {}


class SearchResponse(BaseModel):
    results: list[ChunkResult]
    query: str
    total: int


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5


class SourceGroup(BaseModel):
    source_id: UUID
    source_filename: str
    source_path: str
    chunks: list[ChunkResult]
    max_score: float


class RetrieveResponse(BaseModel):
    groups: list[SourceGroup]
    query: str
    total: int
