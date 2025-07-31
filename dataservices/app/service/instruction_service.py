"""
Instruction service using the new persistence services
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.service.persistence_service import PersistenceServiceFactory
from app.service.models import (
    InstructionCreate, InstructionUpdate, InstructionRead
)
from app.utils.history import DomainManager
from app.schemas.dbmodels import Instruction


def create_instruction(db: Session, data: InstructionCreate, created_by: str) -> InstructionRead:
    """Create a new instruction using persistence service."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Convert to instruction data format
    instruction_data = {
        'question': data.question,
        'instructions': data.instructions,
        'sql_query': data.sql_query,
        'chain_of_thought': data.chain_of_thought,
        'metadata': data.metadata or {}
    }
    
    # Persist using the service
    instruction_id = instruction_service.persist_instruction(instruction_data, data.domain_id, created_by)
    
    # Get the created instruction
    instruction = instruction_service.get_instruction_by_id(instruction_id)
    
    return InstructionRead.model_validate(instruction)


def get_instruction(db: Session, instruction_id: str) -> Optional[InstructionRead]:
    """Retrieve an instruction by its ID using persistence service."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Get instruction by ID directly
    instruction = instruction_service.get_instruction_by_id(instruction_id)
    
    if instruction:
        return InstructionRead.model_validate(instruction)
    return None


def update_instruction(db: Session, instruction_id: str, data: InstructionUpdate, modified_by: str) -> Optional[InstructionRead]:
    """Update an instruction using persistence service."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Get the instruction by ID
    instruction = instruction_service.get_instruction_by_id(instruction_id)
    
    if not instruction:
        return None
    
    # Prepare updates
    updates = {}
    if data.question is not None:
        updates['question'] = data.question
    if data.instructions is not None:
        updates['instructions'] = data.instructions
    if data.sql_query is not None:
        updates['sql_query'] = data.sql_query
    if data.chain_of_thought is not None:
        updates['chain_of_thought'] = data.chain_of_thought
    if data.metadata is not None:
        updates['metadata'] = data.metadata
    
    # Update using the service
    updated_instruction = instruction_service.update_instruction(instruction_id, updates, modified_by)
    
    return InstructionRead.model_validate(updated_instruction)


def delete_instruction(db: Session, instruction_id: str) -> bool:
    """Delete an instruction using persistence service."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Delete using the service
    return instruction_service.delete_instruction(instruction_id)


def list_instructions(db: Session, domain_id: Optional[str] = None) -> List[InstructionRead]:
    """List instructions using persistence service."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Get instructions
    if domain_id:
        instructions = instruction_service.get_instructions(domain_id)
    else:
        # Get all instructions (not recommended for large datasets)
        instructions = instruction_service.get_instructions("")
    
    return [InstructionRead.model_validate(instruction) for instruction in instructions]


def create_instructions_batch(db: Session, instructions_data: List[Dict[str, Any]], 
                            domain_id: str, created_by: str) -> List[str]:
    """Create multiple instructions in batch using persistence service."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Prepare instruction data
    formatted_instructions = []
    for data in instructions_data:
        formatted_instructions.append({
            'question': data['question'],
            'instructions': data['instructions'],
            'sql_query': data['sql_query'],
            'chain_of_thought': data.get('chain_of_thought'),
            'metadata': data.get('metadata', {})
        })
    
    # Persist using the service
    instruction_ids = instruction_service.persist_instructions_batch(formatted_instructions, domain_id, created_by)
    
    return instruction_ids


def get_instruction_summary(db: Session, domain_id: str) -> Dict[str, Any]:
    """Get summary of instructions for a domain."""
    # Initialize services
    domain_manager = DomainManager(db)
    factory = PersistenceServiceFactory(db, domain_manager)
    instruction_service = factory.get_instruction_service()
    
    # Get all instructions for the domain
    instructions = instruction_service.get_instructions(domain_id)
    
    summary = {
        'total_instructions': len(instructions),
        'recent_instructions': [],
        'instruction_types': {},
        'total_sql_queries': 0,
        'instructions_with_chain_of_thought': 0
    }
    
    for instruction in instructions:
        # Count instructions with chain of thought
        if instruction.chain_of_thought:
            summary['instructions_with_chain_of_thought'] += 1
        
        # Count SQL queries
        if instruction.sql_query:
            summary['total_sql_queries'] += 1
        
        # Get recent instructions (last 5)
        if len(summary['recent_instructions']) < 5:
            summary['recent_instructions'].append({
                'instruction_id': str(instruction.instruction_id),
                'question': instruction.question,
                'created_at': instruction.created_at.isoformat() if instruction.created_at else None
            })
        
        # Categorize by question type (simple categorization)
        question_type = 'general'
        if 'calculate' in instruction.question.lower():
            question_type = 'calculation'
        elif 'find' in instruction.question.lower() or 'get' in instruction.question.lower():
            question_type = 'query'
        elif 'create' in instruction.question.lower() or 'build' in instruction.question.lower():
            question_type = 'creation'
        
        summary['instruction_types'][question_type] = summary['instruction_types'].get(question_type, 0) + 1
    
    return summary 