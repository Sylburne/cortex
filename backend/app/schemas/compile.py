from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class CompileRequest(BaseModel):
    source_ids: Optional[list[UUID]] = None
    card_type: str = "concept"


class CompileJobResponse(BaseModel):
    job_id: UUID
    status: str  # queued, processing, completed, error
    notebook_id: UUID
    card_type: str


class CompileStatusResponse(BaseModel):
    job_id: UUID
    status: str
    progress: int = 0  # percentage
    cards_created: int = 0
    error: Optional[str] = None


class KnowledgeCardResponse(BaseModel):
    id: UUID
    notebook_id: UUID
    title: str
    content: str
    card_type: str
    quality_score: Optional[float] = None
    lint_issues: list = []
    status: str
    compiled_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LintRequest(BaseModel):
    card_id: Optional[UUID] = None  # None = lint all cards


class LintIssue(BaseModel):
    type: str
    severity: str  # warning, error
    message: str
    location: Optional[str] = None


class LintResponse(BaseModel):
    notebook_id: UUID
    total_cards: int
    issues: list[LintIssue]
    cards_checked: int
