from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class SourceResponse(BaseModel):
    id: UUID
    notebook_id: UUID
    parent_id: Optional[UUID] = None
    path: str
    filename: str
    file_type: str
    file_size: int
    content_hash: str
    status: str
    error_message: Optional[str] = None
    is_dir: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]
    total: int
    page: int
    page_size: int


class BatchPreflightItem(BaseModel):
    path: str
    filename: str
    content_hash: str
    file_size: int
    file_type: str


class BatchPreflightRequest(BaseModel):
    files: list[BatchPreflightItem]


class BatchPreflightResult(BaseModel):
    path: str
    filename: str
    action: str  # "upload" | "skip" | "replace"


class SourceMoveRequest(BaseModel):
    parent_id: Optional[UUID] = None
    new_filename: Optional[str] = None


class MkdirRequest(BaseModel):
    path: str
    filename: str
    parent_id: Optional[UUID] = None
