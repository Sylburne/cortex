from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class NotebookCreate(BaseModel):
    name: str
    description: str = ""


class NotebookResponse(BaseModel):
    id: UUID
    name: str
    description: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotebookListResponse(BaseModel):
    notebooks: list[NotebookResponse]
    total: int
    page: int
    page_size: int
