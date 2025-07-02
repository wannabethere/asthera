from sqlalchemy.orm import Session
from app.service.dbmodel import Example
from app.schemas.example_schemas import ExampleCreate, ExampleUpdate, ExampleRead


def create_example(db: Session, data: ExampleCreate) -> Example:
    """Create a new Example."""
    example = Example(**data.model_dump())
    db.add(example)
    db.commit()
    db.refresh(example)
    return ExampleRead.model_validate(example)


def get_example(db: Session, example_id: str) -> Example:
    """Retrieve an Example by its ID."""
    return db.query(Example).filter_by(example_id=example_id).first()


def update_example(db: Session, example_id: str, data: ExampleUpdate) -> Example:
    """Partially update an Example's attributes."""
    example = get_example(db, example_id)
    if not example:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(example, field, value)

    db.commit()
    db.refresh(example)
    return ExampleRead.model_validate(example)


def delete_example(db: Session, example_id: str) -> bool:
    """Remove an Example from the database."""
    example = get_example(db, example_id)
    if example:
        db.delete(example)
        db.commit()
        return True
    return False
