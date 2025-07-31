from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from app.core.session_manager import SessionManager
from app.service.persistence_service import SQLFunctionPersistenceService
from app.utils.history import DomainManager
from app.schemas.sql_functions_schemas import (
    SQLFunctionCreate,
    SQLFunctionUpdate,
    SQLFunctionRead,
    SQLFunctionSummary,
    SQLFunctionSearchRequest,
    SQLFunctionBatchCreate,
    SQLFunctionCopyRequest,
    SQLFunctionListResponse,
)

router = APIRouter()

async def get_sql_function_service() -> SQLFunctionPersistenceService:
    """Get SQL function persistence service with SessionManager and DomainManager"""
    session_manager = SessionManager.get_instance()
    # DomainManager doesn't need a session for initialization
    domain_manager = DomainManager(None)
    return SQLFunctionPersistenceService(session_manager, domain_manager)


@router.post(
    "/sql-functions/",
    response_model=SQLFunctionRead,
    summary="Create a new SQL function.",
)
async def create(
    data: SQLFunctionCreate, 
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Create a new SQL function with optional domain association."""
    try:
        # Convert Pydantic model to dict
        function_data = data.model_dump(exclude={'domain_id'})
        
        # Create function using persistence service
        function_id = await service.persist_sql_function(
            function_data=function_data,
            created_by='api_user',  # TODO: Get from auth context
            domain_id=data.domain_id
        )
        
        # Retrieve and return the created function
        sql_function = await service.get_sql_function(function_id)
        if not sql_function:
            raise HTTPException(500, "Failed to retrieve created function")
        
        return SQLFunctionRead.model_validate(sql_function)
        
    except Exception as e:
        raise HTTPException(400, f"Failed to create SQL function: {str(e)}")


@router.post(
    "/sql-functions/batch",
    response_model=List[SQLFunctionRead],
    summary="Create multiple SQL functions in batch.",
)
async def create_batch(
    data: SQLFunctionBatchCreate,
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Create multiple SQL functions in batch."""
    try:
        function_ids = []
        
        for function_data in data.functions:
            # Use batch domain_id if individual function doesn't have one
            domain_id = function_data.domain_id or data.domain_id
            
            # Convert Pydantic model to dict
            function_dict = function_data.model_dump(exclude={'domain_id'})
            
            # Create function
            function_id = await service.persist_sql_function(
                function_data=function_dict,
                created_by='api_user',  # TODO: Get from auth context
                domain_id=domain_id
            )
            function_ids.append(function_id)
        
        # Retrieve and return all created functions
        functions = []
        for function_id in function_ids:
            sql_function = await service.get_sql_function(function_id)
            if sql_function:
                functions.append(SQLFunctionRead.model_validate(sql_function))
        
        return functions
        
    except Exception as e:
        raise HTTPException(400, f"Failed to create SQL functions batch: {str(e)}")


@router.get(
    "/sql-functions/",
    response_model=SQLFunctionListResponse,
    summary="List SQL functions with optional filtering.",
)
async def list_functions(
    domain_id: Optional[str] = Query(None, description="Filter by domain ID"),
    name: Optional[str] = Query(None, description="Filter by function name"),
    return_type: Optional[str] = Query(None, description="Filter by return type"),
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """List SQL functions with optional filtering."""
    try:
        # Get functions based on filters
        if name:
            functions = await service.get_sql_functions_by_name(name, domain_id)
        else:
            functions = await service.get_sql_functions(domain_id)
        
        # Filter by return type if specified
        if return_type:
            functions = [f for f in functions if f.return_type == return_type]
        
        # Convert to response models
        function_reads = [SQLFunctionRead.model_validate(f) for f in functions]
        
        return SQLFunctionListResponse(
            functions=function_reads,
            total_count=len(function_reads),
            domain_id=domain_id
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to list SQL functions: {str(e)}")


@router.get(
    "/sql-functions/global",
    response_model=SQLFunctionListResponse,
    summary="List global SQL functions (not associated with any domain).",
)
async def list_global_functions(
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """List global SQL functions."""
    try:
        functions = await service.get_global_sql_functions()
        function_reads = [SQLFunctionRead.model_validate(f) for f in functions]
        
        return SQLFunctionListResponse(
            functions=function_reads,
            total_count=len(function_reads),
            domain_id=None
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to list global SQL functions: {str(e)}")


@router.post(
    "/sql-functions/search",
    response_model=SQLFunctionListResponse,
    summary="Search SQL functions by name or description.",
)
async def search_functions(
    request: SQLFunctionSearchRequest,
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Search SQL functions by name or description."""
    try:
        functions = await service.search_sql_functions(
            search_term=request.search_term,
            domain_id=request.domain_id
        )
        
        # Filter by return type if specified
        if request.return_type:
            functions = [f for f in functions if f.return_type == request.return_type]
        
        # Apply limit
        if request.limit:
            functions = functions[:request.limit]
        
        function_reads = [SQLFunctionRead.model_validate(f) for f in functions]
        
        return SQLFunctionListResponse(
            functions=function_reads,
            total_count=len(function_reads),
            domain_id=request.domain_id
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to search SQL functions: {str(e)}")


@router.get(
    "/sql-functions/{function_id}",
    response_model=SQLFunctionRead,
    summary="Retrieve a SQL function by its ID.",
)
async def read(
    function_id: str, 
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Retrieve a SQL function by its unique ID."""
    try:
        sql_function = await service.get_sql_function(function_id)
        if not sql_function:
            raise HTTPException(404, "SQL function not found.")
        
        return SQLFunctionRead.model_validate(sql_function)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to retrieve SQL function: {str(e)}")


@router.get(
    "/sql-functions/summary",
    response_model=SQLFunctionSummary,
    summary="Get summary statistics for SQL functions.",
)
async def get_summary(
    function_id: Optional[str] = Query(None, description="Function ID (optional)"),
    domain_id: Optional[str] = Query(None, description="Domain ID (optional)"),
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Get summary statistics for SQL functions."""
    try:
        summary = await service.get_sql_function_summary(domain_id)
        return SQLFunctionSummary.model_validate(summary)
        
    except Exception as e:
        raise HTTPException(400, f"Failed to get SQL function summary: {str(e)}")


@router.patch(
    "/sql-functions/{function_id}",
    response_model=SQLFunctionRead,
    summary="Update a SQL function.",
)
async def update(
    function_id: str,
    data: SQLFunctionUpdate,
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Partially update a SQL function's details."""
    try:
        # Convert Pydantic model to dict, excluding None values
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        
        if not updates:
            raise HTTPException(400, "No valid updates provided")
        
        sql_function = await service.update_sql_function(
            function_id=function_id,
            updates=updates,
            modified_by='api_user'  # TODO: Get from auth context
        )
        
        return SQLFunctionRead.model_validate(sql_function)
        
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, f"Failed to update SQL function: {str(e)}")


@router.post(
    "/sql-functions/{function_id}/copy",
    response_model=SQLFunctionRead,
    summary="Copy a SQL function to another domain.",
)
async def copy_function(
    function_id: str,
    request: SQLFunctionCopyRequest,
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Copy a SQL function to another domain."""
    try:
        copied_function_id = await service.copy_sql_function_to_domain(
            function_id=function_id,
            target_domain_id=request.target_domain_id,
            created_by='api_user'  # TODO: Get from auth context
        )
        
        # Retrieve and return the copied function
        sql_function = await service.get_sql_function(copied_function_id)
        if not sql_function:
            raise HTTPException(500, "Failed to retrieve copied function")
        
        return SQLFunctionRead.model_validate(sql_function)
        
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, f"Failed to copy SQL function: {str(e)}")


@router.delete(
    "/sql-functions/{function_id}",
    summary="Delete a SQL function."
)
async def delete(
    function_id: str,
    service: SQLFunctionPersistenceService = Depends(get_sql_function_service)
):
    """Remove a SQL function from the database."""
    try:
        success = await service.delete_sql_function(function_id)
        if not success:
            raise HTTPException(404, "SQL function not found.")
        
        return {"message": "SQL function deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to delete SQL function: {str(e)}")
