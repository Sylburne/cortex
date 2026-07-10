from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
import hashlib
import unicodedata
import asyncio
from typing import Optional
from uuid import UUID
import mimetypes

from app.database import get_db
from app.api.auth import verify_api_key
from app.models.source import Source
from app.models.notebook import Notebook
from app.schemas.source import (
    SourceResponse, SourceListResponse, BatchPreflightRequest,
    BatchPreflightResult, SourceMoveRequest, MkdirRequest,
)
from app.services.pipeline import process_source_background
from app.services.document_parser import detect_and_parse

router = APIRouter(prefix="/notebooks/{notebook_id}/sources", tags=["sources"])


def _detect_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "docx": "word", "pdf": "pdf", "md": "markdown", "mdx": "markdown",
        "txt": "text", "pptx": "powerpoint", "png": "image", "jpg": "image",
        "jpeg": "image", "gif": "image", "svg": "image", "webp": "image",
    }
    return mapping.get(ext, "other")


def _normalize_path(path: str) -> str:
    """Normalize Unicode for cross-platform consistency."""
    return unicodedata.normalize("NFC", path)


@router.get("", response_model=SourceListResponse)
async def list_sources(
    notebook_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    path_prefix: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    # Verify notebook exists
    nb_q = select(Notebook).where(Notebook.id == notebook_id)
    if not (await db.execute(nb_q)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Notebook not found")

    q = select(Source).where(Source.notebook_id == notebook_id)
    if path_prefix:
        q = q.where(Source.path.like(f"{_normalize_path(path_prefix)}%"))
    if status_filter:
        q = q.where(Source.status == status_filter)

    count_q = select(func.count()).select_from(Source).where(Source.notebook_id == notebook_id)
    if path_prefix:
        count_q = count_q.where(Source.path.like(f"{_normalize_path(path_prefix)}%"))
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(Source.path, Source.filename)
    result = await db.execute(q)
    sources = result.scalars().all()

    items = []
    for s in sources:
        items.append(SourceResponse(
            id=s.id, notebook_id=s.notebook_id, parent_id=s.parent_id,
            path=s.path, filename=s.filename, file_type=s.file_type,
            file_size=s.file_size, content_hash=s.content_hash, status=s.status,
            error_message=s.error_message, is_dir=bool(s.is_dir),
            created_at=s.created_at, updated_at=s.updated_at,
        ))

    return SourceListResponse(sources=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SourceResponse)
async def upload_source(
    notebook_id: str,
    file: UploadFile = File(...),
    path: str = Form(""),
    parent_id: Optional[str] = Form(None),
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    nb_q = select(Notebook).where(Notebook.id == notebook_id)
    if not (await db.execute(nb_q)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Notebook not found")

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    norm_path = _normalize_path(path)
    filename = file.filename or "unknown"
    file_type = _detect_file_type(filename)
    
    # Store original binary for all non-text formats (preserves exact file)
    original_content = None
    if file_type in ("word", "pdf", "powerpoint"):
        original_content = content
    
    # Parse text from binary formats for chunking/embedding
    if file_type in ("word", "pdf", "powerpoint"):
        try:
            raw_text = detect_and_parse(content, filename)
            print(f"[upload] Parsed {file_type}: {filename} -> {len(raw_text)} chars text, {len(content)} bytes binary stored")
        except Exception as e:
            print(f"[upload] Parse failed for {filename}: {e}")
            raw_text = content.decode("utf-8", errors="replace")
    else:
        raw_text = content.decode("utf-8", errors="replace")

    # Idempotency: check if same path+filename+hash exists
    existing_q = select(Source).where(
        Source.notebook_id == notebook_id,
        Source.path == norm_path,
        Source.filename == _normalize_path(filename),
    )
    existing = (await db.execute(existing_q)).scalar_one_or_none()
    if existing and existing.content_hash == content_hash:
        return SourceResponse(
            id=existing.id, notebook_id=existing.notebook_id,
            parent_id=existing.parent_id, path=existing.path,
            filename=existing.filename, file_type=existing.file_type,
            file_size=existing.file_size, content_hash=existing.content_hash,
            status=existing.status, error_message=existing.error_message,
            is_dir=bool(existing.is_dir), created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
    if existing:
        # Replace: update content and reset status
        existing.raw_content = raw_text
        existing.content_hash = content_hash
        existing.file_size = len(content)
        existing.status = "uploaded"
        existing.error_message = None
        existing.original_content = original_content
        existing.original_filename = filename if original_content else None
        await db.commit()
        await db.refresh(existing)
        return SourceResponse(
            id=existing.id, notebook_id=existing.notebook_id,
            parent_id=existing.parent_id, path=existing.path,
            filename=existing.filename, file_type=existing.file_type,
            file_size=existing.file_size, content_hash=existing.content_hash,
            status=existing.status, error_message=existing.error_message,
            is_dir=bool(existing.is_dir), created_at=existing.created_at,
            updated_at=existing.updated_at,
        )

    source = Source(
        notebook_id=notebook_id,
        parent_id=UUID(parent_id) if parent_id else None,
        path=norm_path,
        filename=_normalize_path(filename),
        file_type=file_type,
        file_size=len(content),
        content_hash=content_hash,
        raw_content=raw_text,
        original_content=original_content,
        original_filename=filename if original_content else None,
        status="uploaded",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    # Trigger parse → chunk → embed pipeline in background
    asyncio.create_task(process_source_background(str(source.id), notebook_id))

    return SourceResponse(
        id=source.id, notebook_id=source.notebook_id, parent_id=source.parent_id,
        path=source.path, filename=source.filename, file_type=source.file_type,
        file_size=source.file_size, content_hash=source.content_hash,
        status=source.status, error_message=source.error_message,
        is_dir=bool(source.is_dir), created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.get("/{source_id}/content")
async def get_source_content(
    notebook_id: str,
    source_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(Source).where(Source.id == source_id, Source.notebook_id == notebook_id)
    source = (await db.execute(q)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"content": source.raw_content or "", "filename": source.filename, "status": source.status}


@router.get("/{source_id}/download")
async def download_source(
    notebook_id: str,
    source_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Download the original file (PDF/DOCX/etc) as stored in the notebook."""
    q = select(Source).where(Source.id == source_id, Source.notebook_id == notebook_id)
    source = (await db.execute(q)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if not source.original_content:
        raise HTTPException(status_code=404, detail="No original file stored for this source")
    
    # Determine media type from filename
    filename = source.original_filename or source.filename
    media_type, _ = mimetypes.guess_type(filename)
    if not media_type:
        media_type = "application/octet-stream"
    
    return Response(
        content=source.original_content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{source_id}")
async def delete_source(
    notebook_id: str,
    source_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(Source).where(Source.id == source_id, Source.notebook_id == notebook_id)
    source = (await db.execute(q)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"status": "deleted"}


@router.post("/mkdir", response_model=SourceResponse)
async def mkdir(
    notebook_id: str,
    body: MkdirRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    nb_q = select(Notebook).where(Notebook.id == notebook_id)
    if not (await db.execute(nb_q)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Notebook not found")

    norm_path = _normalize_path(body.path)
    norm_filename = _normalize_path(body.filename)

    # Check if dir already exists
    existing_q = select(Source).where(
        Source.notebook_id == notebook_id, Source.path == norm_path,
        Source.filename == norm_filename, Source.is_dir == 1,
    )
    existing = (await db.execute(existing_q)).scalar_one_or_none()
    if existing:
        return SourceResponse(
            id=existing.id, notebook_id=existing.notebook_id,
            parent_id=existing.parent_id, path=existing.path,
            filename=existing.filename, file_type="other",
            file_size=0, content_hash="", status="ready",
            error_message=None, is_dir=True,
            created_at=existing.created_at, updated_at=existing.updated_at,
        )

    source = Source(
        notebook_id=notebook_id,
        parent_id=body.parent_id,
        path=norm_path,
        filename=norm_filename,
        file_type="other",
        is_dir=1,
        status="ready",
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return SourceResponse(
        id=source.id, notebook_id=source.notebook_id, parent_id=source.parent_id,
        path=source.path, filename=source.filename, file_type="other",
        file_size=0, content_hash="", status="ready", error_message=None,
        is_dir=True, created_at=source.created_at, updated_at=source.updated_at,
    )


@router.post("/preflight", response_model=list[BatchPreflightResult])
async def batch_preflight(
    notebook_id: str,
    body: BatchPreflightRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Check which files need uploading vs skipping based on content hash."""
    results = []
    for item in body.files:
        norm_path = _normalize_path(item.path)
        norm_filename = _normalize_path(item.filename)
        q = select(Source).where(
            Source.notebook_id == notebook_id,
            Source.path == norm_path,
            Source.filename == norm_filename,
        )
        existing = (await db.execute(q)).scalar_one_or_none()
        if existing and existing.content_hash == item.content_hash:
            action = "skip"
        elif existing:
            action = "replace"
        else:
            action = "upload"
        results.append(BatchPreflightResult(path=item.path, filename=item.filename, action=action))
    return results


@router.post("/{source_id}/mv", response_model=SourceResponse)
async def move_source(
    notebook_id: str,
    source_id: str,
    body: SourceMoveRequest,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(Source).where(Source.id == source_id, Source.notebook_id == notebook_id)
    source = (await db.execute(q)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if body.parent_id is not None:
        source.parent_id = body.parent_id
    if body.new_filename:
        source.filename = _normalize_path(body.new_filename)
    await db.commit()
    await db.refresh(source)
    return SourceResponse(
        id=source.id, notebook_id=source.notebook_id, parent_id=source.parent_id,
        path=source.path, filename=source.filename, file_type=source.file_type,
        file_size=source.file_size, content_hash=source.content_hash,
        status=source.status, error_message=source.error_message,
        is_dir=bool(source.is_dir), created_at=source.created_at,
        updated_at=source.updated_at,
    )
