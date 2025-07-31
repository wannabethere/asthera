"""
Router for domain JSON storage operations with ChromaDB integration
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.core.session_manager import SessionManager
from app.service.project_json_service import DomainJSONService
from app.utils.history import DomainManager
from app.schemas.project_json_schemas import (
    ProjectJSONResponse,
    ProjectJSONSearchRequest,
    ProjectJSONSearchResponse,
    ProjectJSONUpdateRequest
)

router = APIRouter()

async def get_domain_json_service() -> DomainJSONService:
    """Get domain JSON service with SessionManager and DomainManager"""
    session_manager = SessionManager.get_instance()
    domain_manager = DomainManager(None)
    return DomainJSONService(session_manager, domain_manager)


@router.post(
    "/domains/{domain_id}/json/tables",
    response_model=ProjectJSONResponse,
    summary="Store domain tables JSON in ChromaDB and PostgreSQL."
)
async def store_domain_tables_json(
    domain_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Store domain tables JSON with all columns and calculated columns."""
    try:
        chroma_doc_id = await service.store_domain_tables_json(domain_id, updated_by)
        return ProjectJSONResponse(
            project_id=domain_id,
            json_type="tables",
            chroma_document_id=chroma_doc_id,
            message="Tables JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store tables JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/metrics",
    response_model=ProjectJSONResponse,
    summary="Store domain metrics JSON in ChromaDB and PostgreSQL."
)
async def store_domain_metrics_json(
    domain_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Store domain metrics JSON."""
    try:
        chroma_doc_id = await service.store_domain_metrics_json(domain_id, updated_by)
        return ProjectJSONResponse(
            project_id=domain_id,
            json_type="metrics",
            chroma_document_id=chroma_doc_id,
            message="Metrics JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store metrics JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/views",
    response_model=ProjectJSONResponse,
    summary="Store domain views JSON in ChromaDB and PostgreSQL."
)
async def store_domain_views_json(
    domain_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Store domain views JSON."""
    try:
        chroma_doc_id = await service.store_domain_views_json(domain_id, updated_by)
        return ProjectJSONResponse(
            project_id=domain_id,
            json_type="views",
            chroma_document_id=chroma_doc_id,
            message="Views JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store views JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/calculated-columns",
    response_model=ProjectJSONResponse,
    summary="Store domain calculated columns JSON in ChromaDB and PostgreSQL."
)
async def store_domain_calculated_columns_json(
    domain_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Store domain calculated columns JSON."""
    try:
        chroma_doc_id = await service.store_domain_calculated_columns_json(domain_id, updated_by)
        return ProjectJSONResponse(
            project_id=domain_id,
            json_type="calculated_columns",
            chroma_document_id=chroma_doc_id,
            message="Calculated columns JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store calculated columns JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/summary",
    response_model=ProjectJSONResponse,
    summary="Store domain summary JSON in ChromaDB and PostgreSQL."
)
async def store_domain_summary_json(
    domain_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Store complete domain summary JSON."""
    try:
        chroma_doc_id = await service.store_domain_summary_json(domain_id, updated_by)
        return ProjectJSONResponse(
            project_id=domain_id,
            json_type="domain_summary",
            chroma_document_id=chroma_doc_id,
            message="Domain summary JSON stored successfully"
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to store domain summary JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/update-all",
    response_model=List[ProjectJSONResponse],
    summary="Update all domain JSON stores."
)
async def update_all_domain_json(
    domain_id: str,
    updated_by: str = Query('system', description="User who triggered the update"),
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Update all domain JSON stores (tables, metrics, views, calculated columns, summary)."""
    try:
        # Update all JSON types
        tables_doc_id = await service.store_domain_tables_json(domain_id, updated_by)
        metrics_doc_id = await service.store_domain_metrics_json(domain_id, updated_by)
        views_doc_id = await service.store_domain_views_json(domain_id, updated_by)
        calc_columns_doc_id = await service.store_domain_calculated_columns_json(domain_id, updated_by)
        summary_doc_id = await service.store_domain_summary_json(domain_id, updated_by)
        
        return [
            ProjectJSONResponse(
                project_id=domain_id,
                json_type="tables",
                chroma_document_id=tables_doc_id,
                message="Tables JSON updated"
            ),
            ProjectJSONResponse(
                project_id=domain_id,
                json_type="metrics",
                chroma_document_id=metrics_doc_id,
                message="Metrics JSON updated"
            ),
            ProjectJSONResponse(
                project_id=domain_id,
                json_type="views",
                chroma_document_id=views_doc_id,
                message="Views JSON updated"
            ),
            ProjectJSONResponse(
                project_id=domain_id,
                json_type="calculated_columns",
                chroma_document_id=calc_columns_doc_id,
                message="Calculated columns JSON updated"
            ),
            ProjectJSONResponse(
                project_id=domain_id,
                json_type="domain_summary",
                chroma_document_id=summary_doc_id,
                message="Domain summary JSON updated"
            )
        ]
    except Exception as e:
        raise HTTPException(400, f"Failed to update all domain JSON: {str(e)}")


@router.get(
    "/domains/{domain_id}/json/{json_type}",
    summary="Get domain JSON data by type."
)
async def get_domain_json(
    domain_id: str,
    json_type: str,
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Get domain JSON data by type (tables, metrics, views, calculated_columns, domain_summary)."""
    try:
        json_data = await service.get_domain_json(domain_id, json_type)
        if not json_data:
            raise HTTPException(404, f"No JSON data found for domain {domain_id}, type {json_type}")
        
        return {
            "domain_id": domain_id,
            "json_type": json_type,
            "data": json_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to get domain JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/search",
    response_model=ProjectJSONSearchResponse,
    summary="Search domain JSON data using ChromaDB."
)
async def search_domain_json(
    domain_id: str,
    request: ProjectJSONSearchRequest,
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Search domain JSON data using vector search in ChromaDB."""
    try:
        search_results = await service.search_domain_json(
            domain_id=domain_id,
            search_query=request.search_query,
            json_type=request.json_type,
            n_results=request.n_results
        )
        
        return ProjectJSONSearchResponse(
            project_id=domain_id,
            search_query=request.search_query,
            json_type=request.json_type,
            results=search_results,
            total_results=len(search_results)
        )
    except Exception as e:
        raise HTTPException(400, f"Failed to search domain JSON: {str(e)}")


@router.post(
    "/domains/{domain_id}/json/update-on-change",
    response_model=List[ProjectJSONResponse],
    summary="Update domain JSON stores when entities change."
)
async def update_domain_json_on_change(
    domain_id: str,
    request: ProjectJSONUpdateRequest,
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Update relevant domain JSON stores when domain entities change."""
    try:
        updated_doc_ids = await service.update_domain_json_on_change(
            domain_id=domain_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            updated_by=request.updated_by
        )
        
        # Map document IDs to response objects
        responses = []
        json_types = []
        
        # Determine which JSON types were updated based on entity type
        if request.entity_type in ['table', 'column']:
            json_types.extend(['tables', 'domain_summary'])
        elif request.entity_type == 'metric':
            json_types.extend(['metrics', 'domain_summary'])
        elif request.entity_type == 'view':
            json_types.extend(['views', 'domain_summary'])
        elif request.entity_type == 'calculated_column':
            json_types.extend(['calculated_columns', 'tables', 'domain_summary'])
        
        for i, doc_id in enumerate(updated_doc_ids):
            if i < len(json_types):
                responses.append(ProjectJSONResponse(
                    project_id=domain_id,
                    json_type=json_types[i],
                    chroma_document_id=doc_id,
                    message=f"{json_types[i]} JSON updated due to {request.entity_type} change"
                ))
        
        return responses
    except Exception as e:
        raise HTTPException(400, f"Failed to update domain JSON on change: {str(e)}")


@router.get(
    "/domains/{domain_id}/json/status",
    summary="Get domain JSON storage status."
)
async def get_domain_json_status(
    domain_id: str,
    service: DomainJSONService = Depends(get_domain_json_service)
):
    """Get the status of all JSON stores for a domain."""
    try:
        # Check which JSON types exist
        json_types = ['tables', 'metrics', 'views', 'calculated_columns', 'domain_summary']
        status = {
            "domain_id": domain_id,
            "json_stores": {}
        }
        
        for json_type in json_types:
            try:
                json_data = await service.get_domain_json(domain_id, json_type)
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
        raise HTTPException(400, f"Failed to get domain JSON status: {str(e)}") 