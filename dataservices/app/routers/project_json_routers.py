"""
Router for project JSON storage operations with ChromaDB integration
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.core.session_manager import SessionManager
from app.service.project_json_service import ProjectJSONService
from app.utils.history import ProjectManager
from app.schemas.project_json_schemas import (
    ProjectJSONResponse,
    ProjectJSONSearchRequest,
    ProjectJSONSearchResponse,
    ProjectJSONUpdateRequest
)

router = APIRouter()

async def get_project_json_service() -> ProjectJSONService:
    """Get project JSON service with SessionManager and ProjectManager"""
    session_manager = SessionManager.get_instance()
    project_manager = ProjectManager(None)
    return ProjectJSONService(session_manager, project_manager)


@router.post(
    "/projects/{project_id}/json/tables",
    response_model=ProjectJSONResponse,
    summary="Store project tables JSON in ChromaDB and PostgreSQL."
)
async def store_project_tables_json(
    project_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Store project tables JSON with all columns and calculated columns."""
    try:
        chroma_doc_id = await service.store_project_tables_json(project_id, updated_by)
        return ProjectJSONResponse(
            project_id=project_id,
            json_type="tables",
            chroma_document_id=chroma_doc_id,
            message="Tables JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store tables JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/metrics",
    response_model=ProjectJSONResponse,
    summary="Store project metrics JSON in ChromaDB and PostgreSQL."
)
async def store_project_metrics_json(
    project_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Store project metrics JSON."""
    try:
        chroma_doc_id = await service.store_project_metrics_json(project_id, updated_by)
        return ProjectJSONResponse(
            project_id=project_id,
            json_type="metrics",
            chroma_document_id=chroma_doc_id,
            message="Metrics JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store metrics JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/views",
    response_model=ProjectJSONResponse,
    summary="Store project views JSON in ChromaDB and PostgreSQL."
)
async def store_project_views_json(
    project_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Store project views JSON."""
    try:
        chroma_doc_id = await service.store_project_views_json(project_id, updated_by)
        return ProjectJSONResponse(
            project_id=project_id,
            json_type="views",
            chroma_document_id=chroma_doc_id,
            message="Views JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store views JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/calculated-columns",
    response_model=ProjectJSONResponse,
    summary="Store project calculated columns JSON in ChromaDB and PostgreSQL."
)
async def store_project_calculated_columns_json(
    project_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Store project calculated columns JSON."""
    try:
        chroma_doc_id = await service.store_project_calculated_columns_json(project_id, updated_by)
        return ProjectJSONResponse(
            project_id=project_id,
            json_type="calculated_columns",
            chroma_document_id=chroma_doc_id,
            message="Calculated columns JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store calculated columns JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/summary",
    response_model=ProjectJSONResponse,
    summary="Store project summary JSON in ChromaDB and PostgreSQL."
)
async def store_project_summary_json(
    project_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Store complete project summary JSON."""
    try:
        chroma_doc_id = await service.store_project_summary_json(project_id, updated_by)
        return ProjectJSONResponse(
            project_id=project_id,
            json_type="project_summary",
            chroma_document_id=chroma_doc_id,
            message="Project summary JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store project summary JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/update-all",
    response_model=List[ProjectJSONResponse],
    summary="Update all project JSON stores."
)
async def update_all_project_json(
    project_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Update all project JSON stores (tables, metrics, views, calculated columns, summary)."""
    try:
        # Update all JSON types
        tables_doc_id = await service.store_project_tables_json(project_id, updated_by)
        metrics_doc_id = await service.store_project_metrics_json(project_id, updated_by)
        views_doc_id = await service.store_project_views_json(project_id, updated_by)
        calc_columns_doc_id = await service.store_project_calculated_columns_json(project_id, updated_by)
        summary_doc_id = await service.store_project_summary_json(project_id, updated_by)
        
        return [
            ProjectJSONResponse(
                project_id=project_id,
                json_type="tables",
                chroma_document_id=tables_doc_id,
                message="Tables JSON updated"
            ),
            ProjectJSONResponse(
                project_id=project_id,
                json_type="metrics",
                chroma_document_id=metrics_doc_id,
                message="Metrics JSON updated"
            ),
            ProjectJSONResponse(
                project_id=project_id,
                json_type="views",
                chroma_document_id=views_doc_id,
                message="Views JSON updated"
            ),
            ProjectJSONResponse(
                project_id=project_id,
                json_type="calculated_columns",
                chroma_document_id=calc_columns_doc_id,
                message="Calculated columns JSON updated"
            ),
            ProjectJSONResponse(
                project_id=project_id,
                json_type="project_summary",
                chroma_document_id=summary_doc_id,
                message="Project summary JSON updated"
            )
        ]
    except Exception as e:
        raise HTTPException(400, f"Failed to update all project JSON: {str(e)}")


@router.get(
    "/projects/{project_id}/json/{json_type}",
    summary="Get project JSON data by type."
)
async def get_project_json(
    project_id: str,
    json_type: str,
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Get project JSON data by type (tables, metrics, views, calculated_columns, project_summary)."""
    try:
        json_data = await service.get_project_json(project_id, json_type)
        if not json_data:
            raise HTTPException(404, f"No JSON data found for project {project_id}, type {json_type}")
        
        return {
            "project_id": project_id,
            "json_type": json_type,
            "data": json_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to get project JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/search",
    response_model=ProjectJSONSearchResponse,
    summary="Search project JSON data using ChromaDB."
)
async def search_project_json(
    project_id: str,
    request: ProjectJSONSearchRequest,
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Search project JSON data using vector search in ChromaDB."""
    try:
        search_results = await service.search_project_json(
            project_id=project_id,
            search_query=request.search_query,
            json_type=request.json_type,
            n_results=request.n_results
        )
        
        return ProjectJSONSearchResponse(
            project_id=project_id,
            search_query=request.search_query,
            json_type=request.json_type,
            results=search_results,
            total_results=len(search_results)
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to search project JSON: {str(e)}")


@router.post(
    "/projects/{project_id}/json/update-on-change",
    response_model=List[ProjectJSONResponse],
    summary="Update project JSON stores when entities change."
)
async def update_project_json_on_change(
    project_id: str,
    request: ProjectJSONUpdateRequest,
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Update relevant project JSON stores when project entities change."""
    try:
        updated_doc_ids = await service.update_project_json_on_change(
            project_id=project_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            updated_by=request.updated_by
        )
        
        # Map document IDs to response objects
        responses = []
        json_types = []
        
        # Determine which JSON types were updated based on entity type
        if request.entity_type in ['table', 'column']:
            json_types.extend(['tables', 'project_summary'])
        elif request.entity_type == 'metric':
            json_types.extend(['metrics', 'project_summary'])
        elif request.entity_type == 'view':
            json_types.extend(['views', 'project_summary'])
        elif request.entity_type == 'calculated_column':
            json_types.extend(['calculated_columns', 'tables', 'project_summary'])
        
        for i, doc_id in enumerate(updated_doc_ids):
            if i < len(json_types):
                responses.append(ProjectJSONResponse(
                    project_id=project_id,
                    json_type=json_types[i],
                    chroma_document_id=doc_id,
                    message=f"{json_types[i]} JSON updated due to {request.entity_type} change"
                ))
        
        return responses
    except Exception as e:
        raise HTTPException(400, f"Failed to update project JSON on change: {str(e)}")


@router.get(
    "/projects/{project_id}/json/status",
    summary="Get project JSON storage status."
)
async def get_project_json_status(
    project_id: str,
    service: ProjectJSONService = Depends(get_project_json_service)
):
    """Get the status of all JSON stores for a project."""
    try:
        # Check which JSON types exist
        json_types = ['tables', 'metrics', 'views', 'calculated_columns', 'project_summary']
        status = {
            "project_id": project_id,
            "json_stores": {}
        }
        
        for json_type in json_types:
            try:
                json_data = await service.get_project_json(project_id, json_type)
                status["json_stores"][json_type] = {
                    "exists": True,
                    "last_updated": json_data.get("updated_at") if json_data else None
                }
            except:
                status["json_stores"][json_type] = {
                    "exists": False,
                    "last_updated": None
                }
        
        return status
    except Exception as e:
        raise HTTPException(400, f"Failed to get project JSON status: {str(e)}") 