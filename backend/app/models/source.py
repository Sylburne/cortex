from app.database import Base
from sqlalchemy import Column, String, Text, DateTime, Integer, BigInteger, LargeBinary, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notebook_id = Column(UUID(as_uuid=True), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=True)
    path = Column(Text, nullable=False, default="")
    filename = Column(String(512), nullable=False)
    file_type = Column(String(20), nullable=False, default="other")
    file_size = Column(BigInteger, nullable=False, default=0)
    content_hash = Column(String(64), nullable=False, default="")
    raw_content = Column(Text, nullable=True)  # Extracted text for chunking/embedding
    original_content = Column(LargeBinary, nullable=True)  # Original binary file (PDF/DOCX/etc)
    original_filename = Column(String(512), nullable=True)  # Original filename for download
    status = Column(String(30), nullable=False, default="uploaded")
    error_message = Column(Text, nullable=True)
    is_dir = Column(Integer, nullable=False, default=0)  # 0=file, 1=directory
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    notebook = relationship("Notebook", lazy="selectin")
    chunks = relationship("Chunk", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("notebook_id", "path", "filename", name="uq_source_path"),
    )
