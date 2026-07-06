from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class RagSessionCreate(BaseModel):
    provider: Optional[str] = None  # openai | anthropic | ollama | gemini | huggingface | qwen
    model: Optional[str] = None  # e.g. gpt-4o, gemini-2.0-flash, qwen-plus
    system_prompt: str = ""
    # Optional: override provider/model mid-conversation
    switch_provider: Optional[str] = None
    switch_model: Optional[str] = None


class RagSessionUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None


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
    # Optional: switch provider/model for this specific message
    provider: Optional[str] = None  # Override session provider for this message
    model: Optional[str] = None  # Override session model for this message


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
