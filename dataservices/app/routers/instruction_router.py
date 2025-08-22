"""
Instruction Router for managing instructions in domains

This router provides endpoints for creating, reading, updating, and deleting
instructions that contain questions, SQL queries, and chain of thought reasoning.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging

from app.service.instruction_service import (
    create_instruction,
    get_instruction,
    update_instruction,
    delete_instruction,
    list_instructions,
    create_instructions_batch,
    get_instruction_summary
)
from app.service.models import (
    InstructionCreate,
    InstructionUpdate,
    InstructionRead
)
from app.core.dependencies import get_db_session
from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instructions", tags=["instructions"])

# ============================================================================
# CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=InstructionRead, status_code=status.HTTP_201_CREATED)
async def create_instruction_endpoint(
    instruction_data: InstructionCreate,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Create a new instruction
    
    Creates an instruction with a question, detailed instructions, SQL query,
    and optional chain of thought reasoning.
    """
    try:
        instruction = create_instruction(db, instruction_data, current_user)
        logger.info(f"Created instruction {instruction.instruction_id} for domain {instruction.domain_id}")
        return instruction
    except Exception as e:
        logger.error(f"Error creating instruction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create instruction: {str(e)}"
        )

@router.get("/{instruction_id}", response_model=InstructionRead)
async def get_instruction_endpoint(
    instruction_id: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get an instruction by ID
    
    Retrieves a specific instruction with all its details including
    question, instructions, SQL query, and chain of thought.
    """
    try:
        instruction = get_instruction(db, instruction_id)
        if not instruction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction {instruction_id} not found"
            )
        return instruction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve instruction: {str(e)}"
        )

@router.put("/{instruction_id}", response_model=InstructionRead)
async def update_instruction_endpoint(
    instruction_id: str,
    instruction_data: InstructionUpdate,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Update an instruction
    
    Updates an existing instruction with new values for question,
    instructions, SQL query, or chain of thought.
    """
    try:
        instruction = update_instruction(db, instruction_id, instruction_data, current_user)
        if not instruction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction {instruction_id} not found"
            )
        logger.info(f"Updated instruction {instruction_id} by user {current_user}")
        return instruction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update instruction: {str(e)}"
        )

@router.delete("/{instruction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instruction_endpoint(
    instruction_id: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Delete an instruction
    
    Permanently removes an instruction from the system.
    """
    try:
        success = delete_instruction(db, instruction_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction {instruction_id} not found"
            )
        logger.info(f"Deleted instruction {instruction_id} by user {current_user}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete instruction: {str(e)}"
        )

# ============================================================================
# LISTING AND SEARCH ENDPOINTS
# ============================================================================

@router.get("/", response_model=List[InstructionRead])
async def list_instructions_endpoint(
    domain_id: Optional[str] = Query(None, description="Filter by domain ID"),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    List instructions
    
    Retrieves a list of instructions, optionally filtered by domain.
    If no domain_id is provided, returns all instructions (use with caution).
    """
    try:
        instructions = list_instructions(db, domain_id)
        logger.info(f"Retrieved {len(instructions)} instructions for domain {domain_id or 'all'}")
        return instructions
    except Exception as e:
        logger.error(f"Error listing instructions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list instructions: {str(e)}"
        )

@router.get("/domain/{domain_id}", response_model=List[InstructionRead])
async def list_instructions_by_domain(
    domain_id: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    List instructions by domain
    
    Retrieves all instructions for a specific domain.
    """
    try:
        instructions = list_instructions(db, domain_id)
        logger.info(f"Retrieved {len(instructions)} instructions for domain {domain_id}")
        return instructions
    except Exception as e:
        logger.error(f"Error listing instructions for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list instructions for domain: {str(e)}"
        )

# ============================================================================
# BATCH OPERATIONS
# ============================================================================

@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def create_instructions_batch_endpoint(
    instructions_data: List[Dict[str, Any]],
    domain_id: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Create multiple instructions in batch
    
    Creates multiple instructions at once for efficient bulk operations.
    Each instruction in the list should have: question, instructions, sql_query,
    and optionally chain_of_thought and metadata.
    """
    try:
        if not instructions_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Instructions data list cannot be empty"
            )
        
        instruction_ids = create_instructions_batch(db, instructions_data, domain_id, current_user)
        logger.info(f"Created {len(instruction_ids)} instructions in batch for domain {domain_id}")
        
        return {
            "message": f"Successfully created {len(instruction_ids)} instructions",
            "instruction_ids": instruction_ids,
            "domain_id": domain_id,
            "created_by": current_user
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating instructions batch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create instructions batch: {str(e)}"
        )

# ============================================================================
# ANALYTICS AND SUMMARY ENDPOINTS
# ============================================================================

@router.get("/domain/{domain_id}/summary")
async def get_instruction_summary_endpoint(
    domain_id: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get instruction summary for a domain
    
    Provides analytics and summary information about instructions
    in a specific domain including counts, types, and recent activity.
    """
    try:
        summary = get_instruction_summary(db, domain_id)
        logger.info(f"Retrieved instruction summary for domain {domain_id}")
        return summary
    except Exception as e:
        logger.error(f"Error getting instruction summary for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instruction summary: {str(e)}"
        )

# ============================================================================
# SEARCH AND FILTER ENDPOINTS
# ============================================================================

@router.get("/search/", response_model=List[InstructionRead])
async def search_instructions(
    query: str = Query(..., description="Search query for questions or instructions"),
    domain_id: Optional[str] = Query(None, description="Filter by domain ID"),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Search instructions
    
    Searches through instruction questions and content for matching text.
    Optionally filters by domain.
    """
    try:
        # Get all instructions for the domain (or all if no domain specified)
        all_instructions = list_instructions(db, domain_id)
        
        # Simple text search (in production, you might want to use full-text search)
        query_lower = query.lower()
        matching_instructions = []
        
        for instruction in all_instructions:
            if (query_lower in instruction.question.lower() or
                query_lower in instruction.instructions.lower() or
                (instruction.chain_of_thought and query_lower in instruction.chain_of_thought.lower())):
                matching_instructions.append(instruction)
        
        logger.info(f"Found {len(matching_instructions)} instructions matching query '{query}'")
        return matching_instructions
    except Exception as e:
        logger.error(f"Error searching instructions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search instructions: {str(e)}"
        )

@router.get("/types/{instruction_type}")
async def get_instructions_by_type(
    instruction_type: str,
    domain_id: Optional[str] = Query(None, description="Filter by domain ID"),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get instructions by type
    
    Retrieves instructions filtered by their type (e.g., 'sql_query', 'instructions').
    """
    try:
        all_instructions = list_instructions(db, domain_id)
        
        # Filter by instruction type
        # Note: This assumes instruction_type is stored in metadata or can be derived
        # You may need to adjust this based on your actual data structure
        filtered_instructions = []
        
        for instruction in all_instructions:
            # Check if instruction matches the type
            # This is a simple implementation - you might want to enhance this
            if instruction.json_metadata and instruction.json_metadata.get("type") == instruction_type:
                filtered_instructions.append(instruction)
            elif instruction_type == "sql_query" and instruction.sql_query:
                filtered_instructions.append(instruction)
            elif instruction_type == "instructions" and instruction.instructions:
                filtered_instructions.append(instruction)
        
        logger.info(f"Found {len(filtered_instructions)} instructions of type '{instruction_type}'")
        return filtered_instructions
    except Exception as e:
        logger.error(f"Error getting instructions by type {instruction_type}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instructions by type: {str(e)}"
        )

# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================

@router.get("/health")
async def instruction_health_check():
    """
    Health check for instruction service
    
    Returns the status of the instruction service.
    """
    return {
        "status": "healthy",
        "service": "instruction_service",
        "endpoints": [
            "POST / - Create instruction",
            "GET /{id} - Get instruction",
            "PUT /{id} - Update instruction",
            "DELETE /{id} - Delete instruction",
            "GET / - List instructions",
            "POST /batch - Create instructions batch",
            "GET /domain/{id}/summary - Get domain summary",
            "GET /search/ - Search instructions",
            "GET /types/{type} - Get by type"
        ]
    }
