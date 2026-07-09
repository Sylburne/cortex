"""Review API - AI-powered file comparison and update generation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.api.auth import verify_api_key
from app.config import settings
from app.models.source import Source
from app.models.notebook import Notebook
from app.services.review import generate_review

router = APIRouter(prefix="/notebooks/{notebook_id}/review", tags=["review"])


class ReviewRequest(BaseModel):
    """Request to review files from a notebook."""
    updated_notebook_id: Optional[str] = None  # Optional second notebook for comparison
    instructions: Optional[str] = None  # User instructions for the review
    provider: Optional[str] = None  # AI provider (gemini, openai, etc.)
    model: Optional[str] = None  # AI model name


class ReviewFileResult(BaseModel):
    """Result of reviewing a single file."""
    filename: str
    content: str
    changes: str


class ReviewResponse(BaseModel):
    """Response from a review operation."""
    summary: str
    updated_files: list[ReviewFileResult]
    original_count: int
    updated_count: int


@router.post("", response_model=ReviewResponse)
async def review_notebook(
    notebook_id: str,
    body: ReviewRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Review files in a notebook using AI.
    
    If updated_notebook_id is provided, compares files from both notebooks
    and generates updated versions.
    
    If only notebook_id is provided, reviews and suggests improvements.
    """
    # Verify original notebook exists
    nb_q = select(Notebook).where(Notebook.id == notebook_id)
    notebook = (await db.execute(nb_q)).scalar_one_or_none()
    if not notebook:
        raise HTTPException(status_code=404, detail="Original notebook not found")
    
    # Get all source files from original notebook (non-directory, ready status)
    sources_q = select(Source).where(
        Source.notebook_id == notebook_id,
        Source.is_dir == 0,
        Source.status == "ready"
    )
    original_sources = (await db.execute(sources_q)).scalars().all()
    
    if not original_sources:
        raise HTTPException(status_code=400, detail="No ready files found in original notebook")
    
    original_files = [
        {"filename": s.filename, "content": s.raw_content or ""}
        for s in original_sources
    ]
    
    # If updated_notebook_id provided, get those files too
    updated_files = []
    if body.updated_notebook_id:
        # Verify updated notebook exists
        updated_nb_q = select(Notebook).where(Notebook.id == body.updated_notebook_id)
        updated_nb = (await db.execute(updated_nb_q)).scalar_one_or_none()
        if not updated_nb:
            raise HTTPException(status_code=404, detail="Updated notebook not found")
        
        # Get all source files from updated notebook
        updated_sources_q = select(Source).where(
            Source.notebook_id == body.updated_notebook_id,
            Source.is_dir == 0,
            Source.status == "ready"
        )
        updated_sources = (await db.execute(updated_sources_q)).scalars().all()
        
        updated_files = [
            {"filename": s.filename, "content": s.raw_content or ""}
            for s in updated_sources
        ]
    
    # Determine provider and model
    provider = body.provider or settings.default_llm_provider
    model = body.model or settings.default_llm_model
    
    # Run the review
    try:
        result = await generate_review(
            provider=provider,
            model=model,
            original_files=original_files,
            updated_files=updated_files,
            instructions=body.instructions or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI review failed: {str(e)}")
    
    # Format the response
    updated_file_results = []
    for f in result.get("updated_files", []):
        updated_file_results.append(ReviewFileResult(
            filename=f.get("filename", "unknown"),
            content=f.get("content", ""),
            changes=f.get("changes", "No changes description"),
        ))
    
    return ReviewResponse(
        summary=result.get("summary", "Review completed"),
        updated_files=updated_file_results,
        original_count=len(original_files),
        updated_count=len(updated_files),
    )


@router.post("/upload-updated/{target_notebook_id}")
async def upload_reviewed_files(
    notebook_id: str,
    target_notebook_id: str,
    body: ReviewResponse,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload the reviewed/updated files to a target notebook.
    
    This creates new source entries in the target notebook with the
    AI-generated updated content.
    """
    import hashlib
    import asyncio
    from app.services.pipeline import process_source_background
    
    # Verify target notebook exists
    nb_q = select(Notebook).where(Notebook.id == target_notebook_id)
    notebook = (await db.execute(nb_q)).scalar_one_or_none()
    if not notebook:
        raise HTTPException(status_code=404, detail="Target notebook not found")
    
    uploaded = []
    for file_result in body.updated_files:
        content = file_result.content.encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Check if file already exists
        existing_q = select(Source).where(
            Source.notebook_id == target_notebook_id,
            Source.filename == file_result.filename,
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()
        
        if existing:
            # Update existing file
            existing.raw_content = file_result.content
            existing.content_hash = content_hash
            existing.file_size = len(content)
            existing.status = "uploaded"
            source = existing
        else:
            # Create new source
            source = Source(
                notebook_id=target_notebook_id,
                path="",
                filename=file_result.filename,
                file_type="text",
                file_size=len(content),
                content_hash=content_hash,
                raw_content=file_result.content,
                status="uploaded",
            )
            db.add(source)
        
        await db.flush()
        await db.refresh(source)
        
        # Trigger processing pipeline
        asyncio.create_task(process_source_background(str(source.id), target_notebook_id))
        
        uploaded.append({
            "filename": file_result.filename,
            "source_id": str(source.id),
            "status": "uploaded"
        })
    
    await db.commit()
    
    return {"uploaded": uploaded, "total": len(uploaded)}
