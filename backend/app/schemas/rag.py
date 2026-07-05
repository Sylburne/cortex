from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class RagSessionCreate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: str = ""


class RagSessionResponse(BaseModel):
    id: UUID
    notebook_id: UUID
    provider: str
    model: str
    system_prompt: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RagMessageRequest(BaseModel):
    content: str


class Citation(BaseModel):
    chunk_id: UUID
    source_id: UUID
    source_filename: str
    source_path: str
    content: str
    score: float


class RagMessageResponse(BaseModel):
    message_id: UUID
    content: str
    citations: list[Citation]
    provider: str
    model: str
