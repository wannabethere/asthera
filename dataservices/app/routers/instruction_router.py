"""
FastAPI router for instruction management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from app.service.instruction_service import (
    create_instruction, get_instruction, update_instruction, 
    delete_instruction, list_instructions, create_instructions_batch,
    get_instruction_summary
)
from app.service.models import (
    InstructionCreate, InstructionUpdate, InstructionRead
)
from app.core.dependencies import get_current_user,get_async_db_session
import logging
import traceback
from app.routers.project_workflow import get_token
from app.service.share_permissions import SharePermissions
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instructions", tags=["instructions"])


@router.post("/", response_model=InstructionRead, status_code=status.HTTP_201_CREATED)
async def create_instruction_endpoint(
    instruction_data: InstructionCreate,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Create a new instruction.
    
    - **question**: The question/prompt for the instruction
    - **instructions**: The instruction text/guidelines
    - **sql_query**: Associated SQL query (optional)
    - **chain_of_thought**: Chain of thought reasoning (optional)
    - **domain_id**: Domain ID to associate with
    - **metadata**: Additional metadata (optional)
    """
    try:
        user=await SharePermissions()._validate_user(token)
        instruction = await create_instruction(db, instruction_data, user['id'],token)
        logger.info(f"Created instruction {instruction.instruction_id} by user {user['id']}")
        return instruction
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Failed to create instruction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create instruction: {str(e)}"
        )


@router.get("/{instruction_id}", response_model=InstructionRead)
async def get_instruction_endpoint(
    instruction_id: str,
    db: AsyncSession = Depends(get_async_db_session),
    token: str = Depends(get_token)
):
    """
    Retrieve a specific instruction by ID.
    
    - **instruction_id**: UUID of the instruction to retrieve
    """
    user=await SharePermissions()._validate_user(token)

    instruction = await get_instruction(db, instruction_id,token)
    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instruction with ID {instruction_id} not found"
        )
    return instruction


@router.put("/{instruction_id}", response_model=InstructionRead)
async def update_instruction_endpoint(
    instruction_id: str,
    instruction_data: InstructionUpdate,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Update an existing instruction.
    
    - **instruction_id**: UUID of the instruction to update
    - **question**: Updated question/prompt (optional)
    - **instructions**: Updated instruction text (optional)
    - **sql_query**: Updated SQL query (optional)
    - **chain_of_thought**: Updated chain of thought (optional)
    - **metadata**: Updated metadata (optional)
    """
    try:
        user=await SharePermissions()._validate_user(token)
        instruction = await update_instruction(db, instruction_id, instruction_data, user['id'],token)
        if not instruction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction with ID {instruction_id} not found"
            )
        logger.info(f"Updated instruction {instruction_id} by user {user['id']}")
        return instruction
    except Exception as e:
        logger.error(f"Failed to update instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update instruction: {str(e)}"
        )


@router.delete("/{instruction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instruction_endpoint(
    instruction_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Delete an instruction.
    
    - **instruction_id**: UUID of the instruction to delete
    """
    try:
        user=await SharePermissions()._validate_user(token)
        success = await delete_instruction(db, instruction_id,token)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction with ID {instruction_id} not found"
            )
        logger.info(f"Deleted instruction {instruction_id} by user {user['id']}")
    except Exception as e:
        logger.error(f"Failed to delete instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete instruction: {str(e)}"
        )


@router.get("/", response_model=List[InstructionRead])
async def list_instructions_endpoint(
    domain_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db_session),
    token: str = Depends(get_token)
):
    """
    List instructions, optionally filtered by domain.
    
    - **domain_id**: Optional domain ID to filter instructions
    """
    try:
        user=await SharePermissions()._validate_user(token)
        instructions = await list_instructions(db,domain_id,token)
        return instructions
    except Exception as e:
        logger.error(f"Failed to list instructions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list instructions: {str(e)}"
        )


@router.post("/batch", response_model=List[str], status_code=status.HTTP_201_CREATED)
async def create_instructions_batch_endpoint(
    instructions_data: List[Dict[str, Any]],
    domain_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Create multiple instructions in batch.
    
    - **instructions_data**: List of instruction data dictionaries
    - **domain_id**: Domain ID to associate all instructions with
    
    Each instruction data dictionary should contain:
    - **question**: The question/prompt
    - **instructions**: The instruction text
    - **sql_query**: SQL query (optional)
    - **chain_of_thought**: Chain of thought (optional)
    - **metadata**: Additional metadata (optional)
    """
    try:
        user=await SharePermissions()._validate_user(token)
        # Validate required fields for each instruction
        for i, data in enumerate(instructions_data):
            if 'question' not in data or 'instructions' not in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Instruction {i} missing required fields 'question' or 'instructions'"
                )
        
        instruction_ids = await create_instructions_batch(db, instructions_data, domain_id, user['id'])
        logger.info(f"Created {len(instruction_ids)} instructions in batch by user {user['id']}")
        return instruction_ids
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create instructions batch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create instructions batch: {str(e)}"
        )


@router.get("/domain/{domain_id}/summary", response_model=Dict[str, Any])
async def get_instruction_summary_endpoint(
    domain_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Get summary statistics for instructions in a domain.
    
    - **domain_id**: Domain ID to get summary for
    
    Returns:
    - **total_instructions**: Total number of instructions
    - **recent_instructions**: List of 5 most recent instructions
    - **instruction_types**: Breakdown by instruction type
    - **total_sql_queries**: Number of instructions with SQL queries
    - **instructions_with_chain_of_thought**: Number with chain of thought
    """
    try:
        user=await SharePermissions()._validate_user(token)
        summary = await get_instruction_summary(db, domain_id)
        return summary
    except Exception as e:
        logger.error(f"Failed to get instruction summary for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instruction summary: {str(e)}"
        )


@router.get("/domain/{domain_id}", response_model=List[InstructionRead])
async def get_instructions_by_domain_endpoint(
    domain_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Get all instructions for a specific domain.
    
    - **domain_id**: Domain ID to get instructions for
    """
    try:
        user=await SharePermissions()._validate_user(token)
        instructions = await list_instructions(db, domain_id)
        return instructions
    except Exception as e:
        logger.error(f"Failed to get instructions for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instructions for domain: {str(e)}"
        )


@router.patch("/{instruction_id}", response_model=InstructionRead)
async def patch_instruction_endpoint(
    instruction_id: str,
    updates: Dict[str, Any],
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Partially update an instruction with specific fields.
    
    - **instruction_id**: UUID of the instruction to update
    - **updates**: Dictionary of fields to update
    
    Allowed update fields:
    - **question**: New question/prompt
    - **instructions**: New instruction text
    - **sql_query**: New SQL query
    - **chain_of_thought**: New chain of thought
    - **metadata**: New metadata
    """
    try:
        user=await SharePermissions()._validate_user(token)
        # Convert updates dict to InstructionUpdate model
        update_data = InstructionUpdate(**updates)
        print(f"Updating instruction {instruction_id} with data: {update_data}")
        instruction = await update_instruction(db, instruction_id, update_data, user['id'],token)
        
        if not instruction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction with ID {instruction_id} not found"
            )
        
        logger.info(f"Patched instruction {instruction_id} by user {user['id']}")
        return instruction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to patch instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to patch instruction: {str(e)}"
        )


@router.post("/search", response_model=List[InstructionRead])
async def search_instructions_endpoint(
    search_params: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Search instructions based on various criteria.
    
    - **search_params**: Dictionary containing search criteria
    
    Supported search parameters:
    - **domain_id**: Filter by domain ID
    - **question_contains**: Search in question text
    - **instruction_contains**: Search in instruction text
    - **has_sql_query**: Filter by presence of SQL query (boolean)
    - **has_chain_of_thought**: Filter by presence of chain of thought (boolean)
    """
    try:
        domain_id = search_params.get('domain_id')
        question_filter = search_params.get('question_contains', '').lower()
        instruction_filter = search_params.get('instruction_contains', '').lower()
        has_sql_query = search_params.get('has_sql_query')
        has_chain_of_thought = search_params.get('has_chain_of_thought')
        
        # Get base list of instructions
        instructions = await list_instructions(db, domain_id)
        
        # Apply filters
        filtered_instructions = []
        for instruction in instructions:
            # Filter by question content
            if question_filter and question_filter not in instruction.question.lower():
                continue
            
            # Filter by instruction content
            if instruction_filter and instruction_filter not in instruction.instructions.lower():
                continue
            
            # Filter by SQL query presence
            if has_sql_query is not None:
                has_sql = bool(instruction.sql_query and instruction.sql_query.strip())
                if has_sql_query != has_sql:
                    continue
            
            # Filter by chain of thought presence
            if has_chain_of_thought is not None:
                has_cot = bool(instruction.chain_of_thought and instruction.chain_of_thought.strip())
                if has_chain_of_thought != has_cot:
                    continue
            
            filtered_instructions.append(instruction)
        
        return filtered_instructions
    except Exception as e:
        logger.error(f"Failed to search instructions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search instructions: {str(e)}"
        )


@router.post("/{instruction_id}/duplicate", response_model=InstructionRead, status_code=status.HTTP_201_CREATED)
async def duplicate_instruction_endpoint(
    instruction_id: str,
    duplicate_params: Optional[Dict[str, Any]] = None,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Duplicate an existing instruction with optional modifications.
    
    - **instruction_id**: UUID of the instruction to duplicate
    - **duplicate_params**: Optional parameters to override in the duplicate
    
    Supported duplicate parameters:
    - **question**: New question for the duplicate
    - **instructions**: New instruction text for the duplicate
    - **domain_id**: New domain ID for the duplicate
    - **name_suffix**: Suffix to add to the duplicated instruction name
    """
    try:
        # Get the original instruction
        original = await get_instruction(db, instruction_id)
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction with ID {instruction_id} not found"
            )
        
        # Prepare data for the duplicate
        duplicate_params = duplicate_params or {}
        name_suffix = duplicate_params.get('name_suffix', ' (Copy)')
        
        duplicate_data = InstructionCreate(
            question=duplicate_params.get('question', original.question),
            instructions=duplicate_params.get('instructions', original.instructions),
            sql_query=original.sql_query,
            chain_of_thought=original.chain_of_thought,
            domain_id=duplicate_params.get('domain_id', original.domain_id),
            metadata={
                **(original.metadata or {}),
                'duplicated_from': str(original.instruction_id),
                'original_question': original.question
            }
        )
        
        # Create the duplicate
        duplicate = await create_instruction(db, duplicate_data, current_user)
        logger.info(f"Duplicated instruction {instruction_id} to {duplicate.instruction_id} by user {current_user}")
        return duplicate
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to duplicate instruction {instruction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate instruction: {str(e)}"
        )


@router.get("/domain/{domain_id}/stats", response_model=Dict[str, Any])
async def get_domain_instruction_stats_endpoint(
    domain_id: str,
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Get detailed statistics for instructions in a domain.
    
    - **domain_id**: Domain ID to get statistics for
    """
    try:
        summary = await get_instruction_summary(db, domain_id)
        
        # Add additional statistics
        instructions = await list_instructions(db, domain_id)
        
        # Calculate average lengths
        total_question_length = sum(len(inst.question) for inst in instructions)
        total_instruction_length = sum(len(inst.instructions) for inst in instructions)
        
        summary.update({
            'average_question_length': total_question_length / len(instructions) if instructions else 0,
            'average_instruction_length': total_instruction_length / len(instructions) if instructions else 0,
            'instructions_by_created_date': {},
            'top_keywords': []
        })
        
        # Group by creation date (simplified)
        for instruction in instructions:
            if instruction.created_at:
                date_key = instruction.created_at.strftime('%Y-%m-%d')
                summary['instructions_by_created_date'][date_key] = \
                    summary['instructions_by_created_date'].get(date_key, 0) + 1
        
        return summary
    except Exception as e:
        logger.error(f"Failed to get instruction stats for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instruction statistics: {str(e)}"
        )


@router.post("/validate", response_model=Dict[str, Any])
async def validate_instruction_endpoint(
    instruction_data: InstructionCreate,
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Validate instruction data without creating it.
    
    - **instruction_data**: Instruction data to validate
    
    Returns validation results including:
    - **is_valid**: Whether the instruction is valid
    - **warnings**: List of validation warnings
    - **suggestions**: List of improvement suggestions
    """
    try:
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'suggestions': []
        }
        
        # Basic validation checks
        if not instruction_data.question or not instruction_data.question.strip():
            validation_result['is_valid'] = False
            validation_result['warnings'].append("Question is required and cannot be empty")
        
        if not instruction_data.instructions or not instruction_data.instructions.strip():
            validation_result['is_valid'] = False
            validation_result['warnings'].append("Instructions are required and cannot be empty")
        
        # Check for domain existence if provided
        if instruction_data.domain_id:
            # This would require a domain service call to validate domain exists
            # For now, we'll assume it's valid
            pass
        
        # Content quality suggestions
        if len(instruction_data.question) < 10:
            validation_result['suggestions'].append("Consider making the question more descriptive")
        
        if len(instruction_data.instructions) < 20:
            validation_result['suggestions'].append("Consider providing more detailed instructions")
        
        if instruction_data.sql_query and 'SELECT' not in instruction_data.sql_query.upper():
            validation_result['warnings'].append("SQL query should typically contain a SELECT statement")
        
        return validation_result
    except Exception as e:
        logger.error(f"Failed to validate instruction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate instruction: {str(e)}"
        )


@router.post("/export", response_model=Dict[str, Any])
async def export_instructions_endpoint(
    export_params: Dict[str, Any],
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Export instructions in various formats.
    
    - **export_params**: Export configuration
    
    Supported export parameters:
    - **domain_id**: Domain ID to export from (optional)
    - **format**: Export format ('json', 'csv', 'yaml')
    - **include_metadata**: Whether to include metadata (boolean)
    - **instruction_ids**: Specific instruction IDs to export (optional)
    """
    try:
        domain_id = export_params.get('domain_id')
        export_format = export_params.get('format', 'json')
        include_metadata = export_params.get('include_metadata', True)
        instruction_ids = export_params.get('instruction_ids')
        
        if instruction_ids:
            # Export specific instructions
            instructions = []
            for inst_id in instruction_ids:
                instruction = await get_instruction(db, inst_id)
                if instruction:
                    instructions.append(instruction)
        else:
            # Export all instructions for domain
            instructions = await list_instructions(db, domain_id)
        
        # Prepare export data
        export_data = []
        for instruction in instructions:
            item = {
                'instruction_id': str(instruction.instruction_id),
                'question': instruction.question,
                'instructions': instruction.instructions,
                'sql_query': instruction.sql_query,
                'chain_of_thought': instruction.chain_of_thought,
                'domain_id': str(instruction.domain_id),
                'created_at': instruction.created_at.isoformat() if instruction.created_at else None,
                'updated_at': instruction.updated_at.isoformat() if instruction.updated_at else None
            }
            
            if include_metadata:
                item['metadata'] = instruction.metadata
                item['created_by'] = instruction.created_by
                item['modified_by'] = instruction.modified_by
            
            export_data.append(item)
        
        result = {
            'format': export_format,
            'total_instructions': len(export_data),
            'export_timestamp': datetime.utcnow().isoformat(),
            'exported_by': current_user,
            'data': export_data
        }
        
        # Format-specific processing could be added here
        if export_format == 'csv':
            result['note'] = 'CSV format would flatten nested structures'
        elif export_format == 'yaml':
            result['note'] = 'YAML format preserves structure and readability'
        
        logger.info(f"Exported {len(export_data)} instructions in {export_format} format by user {current_user}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to export instructions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export instructions: {str(e)}"
        )


@router.post("/import", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def import_instructions_endpoint(
    import_data: Dict[str, Any],
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Import instructions from external data.
    
    - **import_data**: Import configuration and data
    
    Required import parameters:
    - **domain_id**: Target domain ID
    - **instructions**: List of instruction data to import
    
    Optional parameters:
    - **overwrite_existing**: Whether to overwrite existing instructions (boolean)
    - **validate_before_import**: Whether to validate before importing (boolean)
    """
    try:
        domain_id = import_data.get('domain_id')
        instructions_data = import_data.get('instructions', [])
        overwrite_existing = import_data.get('overwrite_existing', False)
        validate_before_import = import_data.get('validate_before_import', True)
        
        if not domain_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="domain_id is required for import"
            )
        
        if not instructions_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="instructions data is required for import"
            )
        
        import_result = {
            'total_provided': len(instructions_data),
            'successfully_imported': 0,
            'skipped': 0,
            'errors': [],
            'imported_ids': []
        }
        
        for i, instruction_data in enumerate(instructions_data):
            try:
                # Basic validation
                if validate_before_import:
                    if 'question' not in instruction_data or 'instructions' not in instruction_data:
                        import_result['errors'].append(f"Instruction {i}: Missing required fields")
                        continue
                
                # Check for existing instruction if overwrite is disabled
                if not overwrite_existing:
                    # This is a simplified check - in practice, you might want more sophisticated duplicate detection
                    existing_instructions = await list_instructions(db, domain_id)
                    duplicate_found = any(
                        inst.question == instruction_data['question'] 
                        for inst in existing_instructions
                    )
                    if duplicate_found:
                        import_result['skipped'] += 1
                        continue
                
                # Create the instruction
                create_data = InstructionCreate(
                    question=instruction_data['question'],
                    instructions=instruction_data['instructions'],
                    sql_query=instruction_data.get('sql_query'),
                    chain_of_thought=instruction_data.get('chain_of_thought'),
                    domain_id=domain_id,
                    metadata=instruction_data.get('metadata', {})
                )
                
                created_instruction = await create_instruction(db, create_data, current_user)
                import_result['successfully_imported'] += 1
                import_result['imported_ids'].append(str(created_instruction.instruction_id))
                
            except Exception as e:
                import_result['errors'].append(f"Instruction {i}: {str(e)}")
        
        logger.info(f"Imported {import_result['successfully_imported']} instructions by user {current_user}")
        return import_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import instructions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import instructions: {str(e)}"
        )