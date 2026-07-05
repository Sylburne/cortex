from app.database import Base
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid


class RagSession(Base):
    __tablename__ = "rag_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(String(255), nullable=False, default="default")
    system_prompt = Column(Text, default="")
    provider = Column(String(50), nullable=False, default="openai")
    model = Column(String(100), nullable=False, default="gpt-4o")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RagMessage(Base):
    __tablename__ = "rag_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("rag_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    source_chunk_ids = Column(ARRAY(UUID(as_uuid=True)), default=[])
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
