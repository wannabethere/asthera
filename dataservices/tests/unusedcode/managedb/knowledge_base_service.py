from sqlalchemy.orm import Session
from app.service.dbmodel import KnowledgeBase
from app.schemas.knowledge_base_schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseRead,
)


def create_knowledge_base(db: Session, data: KnowledgeBaseCreate) -> KnowledgeBase:
    """Create a new KnowledgeBase."""
    knowledge_base = KnowledgeBase(**data.model_dump())
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return KnowledgeBaseRead.model_validate(knowledge_base)


def get_knowledge_base(db: Session, knowledge_base_id: str) -> KnowledgeBase:
    """Retrieve a KnowledgeBase by its ID."""
    return (
        db.query(KnowledgeBase).filter_by(kb_id=knowledge_base_id).first()
    )


def update_knowledge_base(
    db: Session, knowledge_base_id: str, data: KnowledgeBaseUpdate
) -> KnowledgeBase:
    """Partially update a KnowledgeBase's attributes."""
    knowledge_base = get_knowledge_base(db, knowledge_base_id)
    if not knowledge_base:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(knowledge_base, field, value)

    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


def delete_knowledge_base(db: Session, knowledge_base_id: str) -> bool:
    """Remove a KnowledgeBase from the database."""
    knowledge_base = get_knowledge_base(db, knowledge_base_id)
    if knowledge_base:
        db.delete(knowledge_base)
        db.commit()
        return True
    return False
