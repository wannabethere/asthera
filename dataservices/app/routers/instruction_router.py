from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.instruction_service import (
    create_instruction,
    get_instruction,
    update_instruction,
    delete_instruction,
)
from app.schemas.instruction_schemas import (
    InstructionCreate,
    InstructionUpdate,
    InstructionRead,
)

router = APIRouter()


@router.post(
    "/instructions/",
    response_model=InstructionRead,
    summary="Create a new instructional record.",
)
async def create(data: InstructionCreate, db: Session = Depends(get_db)):
    """Create a new instructional record within a project."""
    return create_instruction(db, data)


@router.get(
    "/instructions/{instruction_id}",
    response_model=InstructionRead,
    summary="Retrieve an instructional record.",
)
async def read(instruction_id: str, db: Session = Depends(get_db)):
    """Retrieve an instructional record by its unique ID."""
    instr = get_instruction(db, instruction_id)
    if not instr:
        raise HTTPException(404, "Not found.")
    return instr


@router.patch(
    "/instructions/{instruction_id}",
    response_model=InstructionRead,
    summary="Update an instructional record.",
)
async def update(
    instruction_id: str, data: InstructionUpdate, db: Session = Depends(get_db)
):
    """Partially update an instructional record's details."""
    instr = update_instruction(db, instruction_id, data)
    if not instr:
        raise HTTPException(404, "Not found.")
    return instr


@router.delete(
    "/instructions/{instruction_id}", summary="Delete an instructional record."
)
async def delete(instruction_id: str, db: Session = Depends(get_db)):
    """Remove an instructional record from the database."""
    if not delete_instruction(db, instruction_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
