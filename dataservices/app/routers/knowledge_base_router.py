from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.knowledge_base_service import (
    create_knowledge_base,
    get_knowledge_base,
    update_knowledge_base,
    delete_knowledge_base,
)
from app.schemas.knowledge_base_schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseRead,
)

router = APIRouter()


@router.post(
    "/knowledge-bases/",
    response_model=KnowledgeBaseRead,
    summary="Create a new knowledge base.",
)
async def create(data: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    """Create a new knowledge base entry within a project."""
    return create_knowledge_base(db, data)


@router.get(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBaseRead,
    summary="Retrieve a knowledge base.",
)
async def read(kb_id: str, db: Session = Depends(get_db)):
    """Retrieve a knowledge base by its unique ID."""
    kb = get_knowledge_base(db, kb_id)
    if not kb:
        raise HTTPException(404, "Not found.")
    return kb


@router.patch(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBaseRead,
    summary="Update a knowledge base.",
)
async def update(kb_id: str, data: KnowledgeBaseUpdate, db: Session = Depends(get_db)):
    """Partially update a knowledge base's details."""
    kb = update_knowledge_base(db, kb_id, data)
    if not kb:
        raise HTTPException(404, "Not found.")
    return kb


@router.delete("/knowledge-bases/{kb_id}", summary="Delete a knowledge base.")
async def delete(kb_id: str, db: Session = Depends(get_db)):
    """Remove a knowledge base from the database."""
    if not delete_knowledge_base(db, kb_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
