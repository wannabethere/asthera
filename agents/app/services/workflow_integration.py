"""
Workflow Integration Service

This service handles integration with the workflow services database
to fetch workflow data and render dashboards based on workflow models.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
import httpx
import asyncio
from datetime import datetime

logger = logging.getLogger("lexy-ai-service")


class WorkflowIntegrationService:
    """Service for integrating with workflow services database"""
    
    def __init__(self, workflow_service_url: str = "http://workflowservices:8000"):
        """
        Initialize workflow integration service
        
        Args:
            workflow_service_url: URL of the workflow services API
        """
        self.workflow_service_url = workflow_service_url.rstrip('/')
        self.client = None
        
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self.client
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def fetch_workflow_from_db(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch workflow data from workflow services database
        
        Args:
            workflow_id: Workflow ID to fetch
            
        Returns:
            Workflow data dictionary or None if not found
        """
        try:
            client = await self._get_client()
            
            # Fetch workflow data from workflow services API
            response = await client.get(
                f"{self.workflow_service_url}/api/v1/workflows/{workflow_id}",
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                workflow_data = response.json()
                logger.info(f"Successfully fetched workflow {workflow_id} from database")
                return workflow_data
            elif response.status_code == 404:
                logger.warning(f"Workflow {workflow_id} not found in database")
                return None
            else:
                logger.error(f"Error fetching workflow {workflow_id}: {response.status_code} - {response.text}")
                return None
                
        except httpx.RequestError as e:
            logger.error(f"Network error fetching workflow {workflow_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching workflow {workflow_id}: {e}")
            return None
    
    async def fetch_workflow_components(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Fetch workflow components from workflow services database
        
        Args:
            workflow_id: Workflow ID to fetch components for
            
        Returns:
            List of workflow components
        """
        try:
            client = await self._get_client()
            
            # Fetch workflow components
            response = await client.get(
                f"{self.workflow_service_url}/api/v1/workflows/{workflow_id}/components",
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                components_data = response.json()
                components = components_data.get("components", [])
                logger.info(f"Successfully fetched {len(components)} components for workflow {workflow_id}")
                return components
            else:
                logger.error(f"Error fetching components for workflow {workflow_id}: {response.status_code} - {response.text}")
                return []
                
        except httpx.RequestError as e:
            logger.error(f"Network error fetching components for workflow {workflow_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching components for workflow {workflow_id}: {e}")
            return []
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow status from workflow services database
        
        Args:
            workflow_id: Workflow ID to get status for
            
        Returns:
            Workflow status dictionary
        """
        try:
            client = await self._get_client()
            
            # Get workflow status
            response = await client.get(
                f"{self.workflow_service_url}/api/v1/workflows/{workflow_id}/status",
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"Successfully fetched status for workflow {workflow_id}")
                return status_data
            else:
                logger.error(f"Error fetching status for workflow {workflow_id}: {response.status_code} - {response.text}")
                return {
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except httpx.RequestError as e:
            logger.error(f"Network error fetching status for workflow {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching status for workflow {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            }
    
    def transform_workflow_to_dashboard_data(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform workflow data to dashboard-compatible format
        
        Args:
            workflow_data: Raw workflow data from database
            
        Returns:
            Transformed data for dashboard rendering
        """
        try:
            # Extract basic workflow information
            workflow_id = workflow_data.get("id")
            state = workflow_data.get("state", "UNKNOWN")
            metadata = workflow_data.get("workflow_metadata", {})
            
            # Transform thread components to dashboard queries
            thread_components = workflow_data.get("thread_components", [])
            dashboard_queries = []
            
            for component in thread_components:
                if component.get("component_type") in ["chart", "table", "metric"]:
                    query_data = {
                        "chart_id": component.get("id", f"chart_{len(dashboard_queries)}"),
                        "sql": component.get("sql", ""),
                        "query": component.get("question", ""),
                        "data_description": component.get("description", ""),
                        "project_id": workflow_data.get("project_id", "default"),
                        "configuration": component.get("configuration", {}),
                        "chart_config": component.get("chart_config", {}),
                        "table_config": component.get("table_config", {}),
                        "alert_config": component.get("alert_config", {}),
                        "component_type": component.get("component_type"),
                        "sequence_order": component.get("sequence_order", 0)
                    }
                    dashboard_queries.append(query_data)
            
            # Create dashboard context
            dashboard_context = {
                "title": f"Dashboard from Workflow {workflow_id}",
                "description": f"Dashboard generated from workflow {workflow_id}",
                "template": metadata.get("dashboard_template", "operational_dashboard"),
                "layout": metadata.get("dashboard_layout", "grid_2x2"),
                "refresh_rate": metadata.get("refresh_rate", 300),
                "auto_refresh": metadata.get("auto_refresh", True),
                "responsive": metadata.get("responsive", True),
                "theme": metadata.get("theme", "default"),
                "custom_styling": metadata.get("custom_styling", {}),
                "interactive_features": metadata.get("interactive_features", []),
                "export_options": metadata.get("export_options", ["pdf", "png", "csv"]),
                "sharing_config": metadata.get("sharing_config", {}),
                "alert_config": metadata.get("alert_config", {}),
                "performance_config": metadata.get("performance_config", {}),
                "workflow_id": workflow_id,
                "workflow_state": state,
                "workflow_metadata": metadata,
                "components": thread_components,
                "charts": [
                    {
                        "chart_id": comp.get("id"),
                        "type": comp.get("chart_config", {}).get("type", "bar"),
                        "columns": ["category", "value"],  # Default columns
                        "query": comp.get("question")
                    }
                    for comp in thread_components
                    if comp.get("component_type") == "chart"
                ],
                "available_columns": ["category", "value", "date", "region"],  # Default columns
                "data_types": {
                    "category": "categorical",
                    "value": "numeric",
                    "date": "datetime",
                    "region": "categorical"
                }
            }
            
            return {
                "workflow_id": workflow_id,
                "workflow_state": state,
                "dashboard_queries": dashboard_queries,
                "dashboard_context": dashboard_context,
                "workflow_metadata": metadata,
                "transformed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error transforming workflow data: {e}")
            return {
                "workflow_id": workflow_data.get("id", "unknown"),
                "workflow_state": "error",
                "dashboard_queries": [],
                "dashboard_context": {},
                "error": str(e),
                "transformed_at": datetime.now().isoformat()
            }
    
    async def render_dashboard_from_workflow(
        self,
        workflow_id: str,
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        render_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Render dashboard from workflow database model
        
        Args:
            workflow_id: Workflow ID from database
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting
            additional_context: Additional context for rendering
            time_filters: Time-based filters
            render_options: Options for rendering
            
        Returns:
            Dashboard rendering result
        """
        try:
            # Fetch workflow data
            workflow_data = await self.fetch_workflow_from_db(workflow_id)
            
            if not workflow_data:
                return {
                    "success": False,
                    "error": f"Workflow {workflow_id} not found",
                    "workflow_id": workflow_id
                }
            
            # Transform workflow data to dashboard format
            transformed_data = self.transform_workflow_to_dashboard_data(workflow_data)
            
            if not transformed_data.get("dashboard_queries"):
                return {
                    "success": False,
                    "error": f"No dashboard queries found in workflow {workflow_id}",
                    "workflow_id": workflow_id
                }
            
            # Return transformed data for dashboard service
            return {
                "success": True,
                "workflow_id": workflow_id,
                "project_id": project_id,
                "dashboard_queries": transformed_data["dashboard_queries"],
                "dashboard_context": transformed_data["dashboard_context"],
                "workflow_metadata": transformed_data["workflow_metadata"],
                "natural_language_query": natural_language_query,
                "additional_context": additional_context or {},
                "time_filters": time_filters or {},
                "render_options": render_options or {},
                "transformed_at": transformed_data["transformed_at"]
            }
            
        except Exception as e:
            logger.error(f"Error rendering dashboard from workflow {workflow_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id,
                "project_id": project_id
            }


# Global instance for dependency injection
_workflow_integration_service = None

def get_workflow_integration_service() -> WorkflowIntegrationService:
    """Get global workflow integration service instance"""
    global _workflow_integration_service
    if _workflow_integration_service is None:
        _workflow_integration_service = WorkflowIntegrationService()
    return _workflow_integration_service

async def cleanup_workflow_integration_service():
    """Cleanup workflow integration service"""
    global _workflow_integration_service
    if _workflow_integration_service:
        await _workflow_integration_service.close()
        _workflow_integration_service = None
