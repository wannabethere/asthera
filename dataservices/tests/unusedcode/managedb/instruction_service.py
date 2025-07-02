from sqlalchemy.orm import Session
from app.service.dbmodel import Instruction
from app.schemas.instruction_schemas import (
    InstructionCreate,
    InstructionUpdate,
    InstructionRead,
)


def create_instruction(db: Session, data: InstructionCreate) -> Instruction:
    """Create a new Instruction."""
    instr = Instruction(**data.model_dump())
    db.add(instr)
    db.commit()
    db.refresh(instr)
    return InstructionRead.model_validate(instr)


def get_instruction(db: Session, instr_id: str) -> Instruction:
    """Retrieve an Instruction by its ID."""
    return db.query(Instruction).filter_by(instruction_id=instr_id).first()


def update_instruction(
    db: Session, instr_id: str, data: InstructionUpdate
) -> Instruction:
    """Partially update an Instruction's attributes."""
    instr = get_instruction(db, instr_id)
    if not instr:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(instr, field, value)

    db.commit()
    db.refresh(instr)
    return  InstructionRead.model_validate(instr)


def delete_instruction(db: Session, instr_id: str) -> bool:
    """Remove an Instruction from the database."""
    instr = get_instruction(db, instr_id)
    if instr:
        db.delete(instr)
        db.commit()
        return True
    return False
