"""
MDL Builder Router
API endpoints for building MDL definitions from PostgreSQL objects
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.session_manager import SessionManager
from app.services.mdl_builder_service import mdl_builder_service
from app.schemas.project_json_schemas import ProjectJSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mdl-builder", tags=["MDL Builder"])


async def get_db_session() -> AsyncSession:
    """Get database session"""
    session_manager = SessionManager.get_instance()
    async with session_manager.get_async_db_session() as session:
        yield session


@router.get(
    "/domains/{domain_id}/mdl",
    summary="Get MDL definition for a domain"
)
async def get_domain_mdl(
    domain_id: str,
    include_llm_definitions: bool = Query(True, description="Include LLM-generated definitions"),
    db: AsyncSession = Depends(get_db_session)
):
    """Get complete MDL definition for a domain (read-only)"""
    try:
        logger.info(f"Getting MDL for domain {domain_id}")
        
        # Build MDL
        mdl_data = await mdl_builder_service.build_domain_mdl(
            domain_id=domain_id,
            db=db,
            include_llm_definitions=include_llm_definitions
        )
        
        return {
            "success": True,
            "domain_id": domain_id,
            "mdl_data": mdl_data,
            "message": "MDL retrieved successfully"
        }
        
    except ValueError as e:
        raise HTTPException(404, f"Domain not found: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting MDL for domain {domain_id}: {str(e)}")
        raise HTTPException(500, f"Error getting MDL: {str(e)}")


@router.get(
    "/tables/{table_id}/mdl",
    summary="Get MDL definition for a single table"
)
async def get_table_mdl(
    table_id: str,
    include_llm_definitions: bool = Query(True, description="Include LLM-generated definitions"),
    db: AsyncSession = Depends(get_db_session)
):
    """Get MDL definition for a single table (read-only)"""
    try:
        logger.info(f"Getting MDL for table {table_id}")
        
        # Build table MDL
        table_mdl = await mdl_builder_service.build_table_mdl(
            table_id=table_id,
            db=db,
            include_llm_definitions=include_llm_definitions
        )
        
        return {
            "success": True,
            "table_id": table_id,
            "table_mdl": table_mdl,
            "message": "Table MDL retrieved successfully"
        }
        
    except ValueError as e:
        raise HTTPException(404, f"Table not found: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting MDL for table {table_id}: {str(e)}")
        raise HTTPException(500, f"Error getting table MDL: {str(e)}")


@router.get(
    "/domains/{domain_id}/mdl/summary",
    summary="Get MDL summary for a domain"
)
async def get_domain_mdl_summary(
    domain_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get summary of MDL structure for a domain"""
    try:
        logger.info(f"Getting MDL summary for domain {domain_id}")
        
        # Build MDL without LLM definitions for faster processing
        mdl_data = await mdl_builder_service.build_domain_mdl(
            domain_id=domain_id,
            db=db,
            include_llm_definitions=False
        )
        
        # Extract summary information
        summary = {
            "domain_id": mdl_data["domain_id"],
            "domain_name": mdl_data["domain_name"],
            "version": mdl_data["version"],
            "status": mdl_data["status"],
            "generated_at": mdl_data["generated_at"],
            "statistics": {
                "total_tables": len(mdl_data.get("tables", [])),
                "total_columns": sum(len(table.get("columns", [])) for table in mdl_data.get("tables", [])),
                "total_metrics": len(mdl_data.get("metrics", [])),
                "total_views": len(mdl_data.get("views", [])),
                "total_calculated_columns": len(mdl_data.get("calculated_columns", [])),
                "total_functions": len(mdl_data.get("functions", [])),
                "total_relationships": len(mdl_data.get("relationships", [])),
                "total_enums": len(mdl_data.get("enums", []))
            },
            "tables": [
                {
                    "table_id": table["table_id"],
                    "name": table["name"],
                    "display_name": table["display_name"],
                    "table_type": table["table_type"],
                    "column_count": len(table.get("columns", [])),
                    "metric_count": len(table.get("metrics", [])),
                    "view_count": len(table.get("views", []))
                }
                for table in mdl_data.get("tables", [])
            ]
        }
        
        return {
            "success": True,
            "domain_id": domain_id,
            "summary": summary,
            "message": "MDL summary retrieved successfully"
        }
        
    except ValueError as e:
        raise HTTPException(404, f"Domain not found: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting MDL summary for domain {domain_id}: {str(e)}")
        raise HTTPException(500, f"Error getting MDL summary: {str(e)}")


@router.get(
    "/domains/{domain_id}/mdl/validate",
    summary="Validate MDL structure for a domain"
)
async def validate_domain_mdl(
    domain_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Validate MDL structure and return validation results (read-only)"""
    try:
        logger.info(f"Validating MDL for domain {domain_id}")
        
        # Build MDL
        mdl_data = await mdl_builder_service.build_domain_mdl(
            domain_id=domain_id,
            db=db,
            include_llm_definitions=True
        )
        
        # Perform validation
        validation_results = {
            "domain_id": domain_id,
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {
                "tables_without_description": 0,
                "columns_without_description": 0,
                "tables_without_columns": 0,
                "metrics_without_sql": 0,
                "views_without_sql": 0
            }
        }
        
        # Validate tables
        for table in mdl_data.get("tables", []):
            if not table.get("description"):
                validation_results["warnings"].append(f"Table '{table['name']}' has no description")
                validation_results["statistics"]["tables_without_description"] += 1
            
            if not table.get("columns"):
                validation_results["warnings"].append(f"Table '{table['name']}' has no columns")
                validation_results["statistics"]["tables_without_columns"] += 1
            
            # Validate columns
            for column in table.get("columns", []):
                if not column.get("description"):
                    validation_results["warnings"].append(f"Column '{table['name']}.{column['name']}' has no description")
                    validation_results["statistics"]["columns_without_description"] += 1
        
        # Validate metrics
        for metric in mdl_data.get("metrics", []):
            if not metric.get("metric_sql"):
                validation_results["errors"].append(f"Metric '{metric['name']}' has no SQL definition")
                validation_results["statistics"]["metrics_without_sql"] += 1
                validation_results["is_valid"] = False
        
        # Validate views
        for view in mdl_data.get("views", []):
            if not view.get("view_sql"):
                validation_results["errors"].append(f"View '{view['name']}' has no SQL definition")
                validation_results["statistics"]["views_without_sql"] += 1
                validation_results["is_valid"] = False
        
        return {
            "success": True,
            "domain_id": domain_id,
            "validation": validation_results,
            "message": "MDL validation completed"
        }
        
    except ValueError as e:
        raise HTTPException(404, f"Domain not found: {str(e)}")
    except Exception as e:
        logger.error(f"Error validating MDL for domain {domain_id}: {str(e)}")
        raise HTTPException(500, f"Error validating MDL: {str(e)}")


@router.get(
    "/domains/{domain_id}/mdl/export",
    summary="Get MDL export data for a domain"
)
async def get_domain_mdl_export(
    domain_id: str,
    include_llm_definitions: bool = Query(True, description="Include LLM-generated definitions"),
    db: AsyncSession = Depends(get_db_session)
):
    """Get domain MDL data for export (read-only)"""
    try:
        logger.info(f"Getting MDL export data for domain {domain_id}")
        
        # Build MDL
        mdl_data = await mdl_builder_service.build_domain_mdl(
            domain_id=domain_id,
            db=db,
            include_llm_definitions=include_llm_definitions
        )
        
        return {
            "success": True,
            "domain_id": domain_id,
            "mdl_data": mdl_data,
            "export_info": {
                "generated_at": mdl_data.get("generated_at"),
                "version": mdl_data.get("version"),
                "total_tables": len(mdl_data.get("tables", [])),
                "total_metrics": len(mdl_data.get("metrics", [])),
                "total_views": len(mdl_data.get("views", [])),
                "total_calculated_columns": len(mdl_data.get("calculated_columns", []))
            },
            "message": "MDL export data retrieved successfully"
        }
        
    except ValueError as e:
        raise HTTPException(404, f"Domain not found: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting MDL export data for domain {domain_id}: {str(e)}")
        raise HTTPException(500, f"Error getting MDL export data: {str(e)}")


# Import datetime for timestamp generation
from datetime import datetime 