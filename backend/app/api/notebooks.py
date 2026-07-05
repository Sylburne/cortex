from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db
from app.api.auth import verify_api_key
from app.models.notebook import Notebook
from app.schemas.notebook import NotebookCreate, NotebookResponse, NotebookListResponse

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.post("", response_model=NotebookResponse)
async def create_notebook(
    body: NotebookCreate,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    notebook = Notebook(name=body.name, description=body.description, owner_id=owner_id)
    db.add(notebook)
    await db.commit()
    await db.refresh(notebook)
    return notebook


@router.get("", response_model=NotebookListResponse)
async def list_notebooks(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notebook).where(Notebook.owner_id == owner_id).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    notebooks = result.scalars().all()

    count_q = select(func.count()).select_from(Notebook).where(Notebook.owner_id == owner_id)
    total = (await db.execute(count_q)).scalar() or 0

    return NotebookListResponse(notebooks=notebooks, total=total, page=page, page_size=page_size)


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notebook).where(Notebook.id == notebook_id, Notebook.owner_id == owner_id)
    result = await db.execute(q)
    notebook = result.scalar_one_or_none()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


@router.delete("/{notebook_id}")
async def delete_notebook(
    notebook_id: str,
    owner_id: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notebook).where(Notebook.id == notebook_id, Notebook.owner_id == owner_id)
    result = await db.execute(q)
    notebook = result.scalar_one_or_none()
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    await db.execute(delete(Notebook).where(Notebook.id == notebook_id))
    await db.commit()
    return {"status": "deleted"}
