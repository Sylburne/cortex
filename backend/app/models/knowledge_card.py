from app.database import Base
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    source_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=[])
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    card_type = Column(String(50), nullable=False, default="concept")
    quality_score = Column(Float, nullable=True)
    lint_issues = Column(JSONB, default=[])
    status = Column(String(30), nullable=False, default="pending")
    compiled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
