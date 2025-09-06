import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import asdict
import json
from pathlib import Path

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.agents.pipelines.writers.dashboard_orchestrator_pipeline import DashboardOrchestratorPipeline, create_dashboard_orchestrator_pipeline
from app.agents.nodes.writers.dashboard_models import DashboardConfiguration
from app.services.servicebase import BaseService
from app.core.engine_provider import EngineProvider
from app.core.dependencies import get_llm

logger = logging.getLogger("lexy-ai-service")


class DashboardService(BaseService):
    """Pure API service for dashboard operations that delegates to agent pipelines"""
    
    def __init__(self):
        """Initialize dashboard service as a pure API layer"""
        # Initialize BaseService with empty pipelines dict (we'll use PipelineContainer directly)
        super().__init__(pipelines={})
        
        self._engine = EngineProvider.get_engine()
        self._llm = get_llm()
        
        # Initialize the dashboard orchestrator pipeline
        try:
            self._dashboard_orchestrator = create_dashboard_orchestrator_pipeline(
                engine=self._engine,
                llm=self._llm
            )
            logger.info("Dashboard Orchestrator Pipeline initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Dashboard Orchestrator Pipeline: {e}")
            self._dashboard_orchestrator = None
        
        self.pipeline_container = PipelineContainer.initialize()
        
        # Agent pipeline registry for dashboard operations
        try:
            self._agent_pipelines = {
                "dashboard_orchestrator": self.pipeline_container.get_pipeline("dashboard_orchestrator"),
                "conditional_formatting": self.pipeline_container.get_pipeline("conditional_formatting_generation"),
                "dashboard_streaming": self.pipeline_container.get_pipeline("dashboard_streaming"),
                "enhanced_dashboard": self.pipeline_container.get_pipeline("enhanced_dashboard_streaming")
            }
            
            # Validate that required agent pipelines are available
            for pipeline_name, pipeline in self._agent_pipelines.items():
                if pipeline is None:
                    logger.warning(f"Agent pipeline '{pipeline_name}' is not available - dashboard functionality may be limited")
                else:
                    logger.info(f"Agent pipeline '{pipeline_name}' initialized successfully")
                    
        except Exception as e:
            logger.error(f"Error initializing dashboard agent pipelines: {e}")
            # Set all pipelines to None to prevent crashes
            self._agent_pipelines = {
                "dashboard_orchestrator": None,
                "conditional_formatting": None,
                "dashboard_streaming": None,
                "enhanced_dashboard": None
            }
        
        # Configuration cache and execution history
        self._configuration_cache = {}
        self._execution_history = []
        
        # Initialize default dashboard templates
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Initialize default dashboard templates"""
        self._dashboard_templates = {
            "executive_dashboard": {
                "name": "Executive Dashboard",
                "description": "High-level dashboard for executives and stakeholders",
                "components": [
                    "overview_metrics",
                    "kpi_summary",
                    "trend_charts",
                    "alert_summary"
                ],
                "layout": "grid_2x2",
                "refresh_rate": 300
            },
            "operational_dashboard": {
                "name": "Operational Dashboard",
                "description": "Detailed operational metrics and real-time data",
                "components": [
                    "real_time_metrics",
                    "performance_charts",
                    "status_indicators",
                    "detailed_tables"
                ],
                "layout": "grid_3x3",
                "refresh_rate": 60
            },
            "analytical_dashboard": {
                "name": "Analytical Dashboard",
                "description": "Deep analytical insights with interactive visualizations",
                "components": [
                    "interactive_charts",
                    "drill_down_tables",
                    "correlation_analysis",
                    "forecasting_charts"
                ],
                "layout": "flexible",
                "refresh_rate": 600
            },
            "monitoring_dashboard": {
                "name": "Monitoring Dashboard",
                "description": "System and performance monitoring with alerts",
                "components": [
                    "system_metrics",
                    "performance_monitors",
                    "alert_panels",
                    "log_summaries"
                ],
                "layout": "grid_2x3",
                "refresh_rate": 30
            }
        }
    
    async def process_dashboard_from_workflow(
        self,
        workflow_data: Union[Dict[str, Any], str],
        dashboard_queries: List[Dict[str, Any]],
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Process dashboard using workflow data - delegates to agent pipelines
        
        Args:
            workflow_data: Workflow data as dict or JSON file path
            dashboard_queries: List of SQL queries for dashboard charts
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting (optional)
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback for status updates
            
        Returns:
            Complete dashboard result with workflow-driven configuration
        """
        try:
            # Parse workflow data (simplified - no database models)
            workflow_info = self._parse_workflow_data(workflow_data)
            
            if not workflow_info:
                raise ValueError("Invalid dashboard workflow data provided")
            
            # Extract dashboard configuration from workflow
            dashboard_config = self._extract_dashboard_config_from_workflow(workflow_info)
            
            # Create enhanced dashboard context
            enhanced_context = self._create_enhanced_dashboard_context(
                workflow_info, dashboard_config
            )
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_dashboard_processing_started",
                {
                    "project_id": project_id,
                    "workflow_id": workflow_info.get("id"),
                    "workflow_state": workflow_info.get("state"),
                    "total_queries": len(dashboard_queries),
                    "dashboard_template": dashboard_config.get("template")
                }
            )
            
            # Delegate to agent pipeline for processing
            result = await self.process_dashboard_with_conditional_formatting(
                natural_language_query=natural_language_query,
                dashboard_queries=dashboard_queries,
                project_id=project_id,
                dashboard_context=enhanced_context,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback
            )
            
            # Add workflow metadata to result
            result["workflow_metadata"] = {
                "workflow_id": workflow_info.get("id"),
                "workflow_state": workflow_info.get("state"),
                "workflow_type": "dashboard_workflow",
                "dashboard_template": dashboard_config.get("template"),
                "workflow_source": workflow_info.get("source", "unknown")
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in workflow-based dashboard processing: {e}")
            self._send_status_update(
                status_callback,
                "workflow_dashboard_processing_failed",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            raise
    
    def _parse_workflow_data(
        self, 
        workflow_data: Union[Dict[str, Any], str]
    ) -> Optional[Dict[str, Any]]:
        """Parse workflow data from various input formats (no database dependencies)"""
        
        try:
            if isinstance(workflow_data, str):
                # Assume it's a file path
                if Path(workflow_data).exists():
                    return self._load_workflow_from_json_file(workflow_data)
                else:
                    # Try to parse as JSON string
                    return json.loads(workflow_data)
            
            elif isinstance(workflow_data, dict):
                # Already a dictionary
                workflow_data["source"] = "dict_input"
                return workflow_data
            
            else:
                logger.error(f"Unsupported workflow data type: {type(workflow_data)}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing workflow data: {e}")
            return None
    
    def _load_workflow_from_json_file(self, file_path: str) -> Dict[str, Any]:
        """Load workflow data from JSON file"""
        try:
            with open(file_path, 'r') as f:
                workflow_data = json.load(f)
                workflow_data["source"] = "json_file"
                return workflow_data
        except Exception as e:
            logger.error(f"Error loading workflow from JSON file {file_path}: {e}")
            raise
    

    
    def _extract_dashboard_config_from_workflow(self, workflow_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract dashboard configuration from workflow data"""
        try:
            metadata = workflow_info.get("workflow_metadata", {})
            
            # Extract dashboard configuration
            dashboard_config = {
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
                "performance_config": metadata.get("performance_config", {})
            }
            
            # Override with template defaults if template exists
            template_name = dashboard_config["template"]
            if template_name in self._dashboard_templates:
                template = self._dashboard_templates[template_name]
                for key, value in template.items():
                    if key not in dashboard_config or dashboard_config[key] is None:
                        dashboard_config[key] = value
            
            return dashboard_config
            
        except Exception as e:
            logger.error(f"Error extracting dashboard config from workflow: {e}")
            return self._dashboard_templates.get("operational_dashboard", {})
    
    def _create_enhanced_dashboard_context(
        self,
        workflow_info: Dict[str, Any],
        dashboard_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create enhanced dashboard context from workflow data"""
        try:
            metadata = workflow_info.get("workflow_metadata", {})
            
            # Create base dashboard context
            context = {
                "title": metadata.get("dashboard_title", f"Dashboard from Workflow {workflow_info.get('id', 'Unknown')}"),
                "description": metadata.get("dashboard_description", "Dashboard generated from workflow configuration"),
                "template": dashboard_config.get("template"),
                "layout": dashboard_config.get("layout"),
                "refresh_rate": dashboard_config.get("refresh_rate"),
                "auto_refresh": dashboard_config.get("auto_refresh"),
                "responsive": dashboard_config.get("responsive"),
                "theme": dashboard_config.get("theme"),
                "custom_styling": dashboard_config.get("custom_styling"),
                "interactive_features": dashboard_config.get("interactive_features"),
                "export_options": dashboard_config.get("export_options"),
                "sharing_config": dashboard_config.get("sharing_config"),
                "alert_config": dashboard_config.get("alert_config"),
                "performance_config": dashboard_config.get("performance_config"),
                "workflow_id": workflow_info.get("id"),
                "workflow_state": workflow_info.get("state"),
                "workflow_metadata": metadata
            }
            
            # Add component-specific configurations if available
            components = workflow_info.get("thread_components", [])
            context["components"] = []
            for comp in components:
                component_config = {
                    "id": comp.get("id"),
                    "type": comp.get("component_type"),
                    "title": comp.get("question"),
                    "description": comp.get("description"),
                    "sequence_order": comp.get("sequence_order"),
                    "configuration": comp.get("configuration", {}),
                    "chart_config": comp.get("chart_config"),
                    "table_config": comp.get("table_config"),
                    "alert_config": comp.get("alert_config")
                }
                context["components"].append(component_config)
            
            return context
            
        except Exception as e:
            logger.error(f"Error creating enhanced dashboard context: {e}")
            # Return basic context
            return {
                "title": "Dashboard from Workflow",
                "description": "Dashboard generated from workflow configuration",
                "template": "operational_dashboard",
                "layout": "grid_2x2",
                "workflow_id": workflow_info.get("id", "unknown")
            }
    
    async def process_dashboard_with_conditional_formatting(
        self,
        natural_language_query: str,
        dashboard_queries: List[Dict[str, Any]],
        project_id: str,
        dashboard_context: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Process dashboard with conditional formatting using agent pipelines
        
        Args:
            natural_language_query: Natural language query for conditional formatting
            dashboard_queries: List of SQL queries for dashboard charts
            project_id: Project identifier
            dashboard_context: Context about dashboard charts and columns
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback for status updates
            
        Returns:
            Complete dashboard result with conditional formatting applied
        """
        try:
            def send_status_update(status: str, details: Dict[str, Any] = None):
                if status_callback:
                    try:
                        status_callback(status, details or {})
                    except Exception as e:
                        logger.error(f"Error in status callback: {str(e)}")
                logger.info(f"Dashboard Service Status - {status}: {details}")
            
            send_status_update("processing_started", {
                "project_id": project_id,
                "total_queries": len(dashboard_queries),
                "has_conditional_formatting": bool(natural_language_query),
                "dashboard_template": dashboard_context.get("template"),
                "workflow_id": dashboard_context.get("workflow_id")
            })
            
            # Use dashboard orchestrator pipeline for complete processing
            if not self._agent_pipelines["dashboard_orchestrator"]:
                error_msg = "Dashboard orchestrator pipeline is not available"
                logger.error(error_msg)
                send_status_update("dashboard_processing_failed", {
                    "error": error_msg,
                    "project_id": project_id
                })
                raise RuntimeError(error_msg)
            
            send_status_update("dashboard_orchestration_started", {
                "project_id": project_id,
                "total_queries": len(dashboard_queries)
            })
            
            # Delegate to dashboard orchestrator pipeline
            result = await self._agent_pipelines["dashboard_orchestrator"].run(
                dashboard_queries=dashboard_queries,
                        natural_language_query=natural_language_query,
                        dashboard_context=dashboard_context,
                        project_id=project_id,
                        additional_context=additional_context,
                        time_filters=time_filters,
                status_callback=self._create_nested_status_callback(send_status_update, "orchestrator")
            )
            
            # Extract results from pipeline response
            if result.get("post_process", {}).get("success"):
                dashboard_results = result.get("post_process", {}).get("dashboard_results", {})
                enhanced_dashboard = result.get("post_process", {}).get("enhanced_dashboard", {})
                orchestration_metadata = result.get("post_process", {}).get("orchestration_metadata", {})
                
                # Prepare final response
                final_result = {
                    "success": True,
                    "dashboard_data": dashboard_results,
                    "enhanced_dashboard": enhanced_dashboard,
                    "dashboard_config": dashboard_context,
                    "metadata": {
                        "project_id": project_id,
                        "natural_language_query": natural_language_query,
                        "total_queries": len(dashboard_queries),
                        "conditional_formatting_applied": bool(enhanced_dashboard.get("conditional_formatting_rules")),
                        "dashboard_template": dashboard_context.get("template"),
                        "workflow_id": dashboard_context.get("workflow_id"),
                        "timestamp": datetime.now().isoformat(),
                        "orchestration_metadata": orchestration_metadata
                    }
                }
                
                send_status_update("processing_completed", {
                    "success": final_result["success"],
                    "project_id": project_id,
                    "total_charts": len(dashboard_results.get("results", {})) if dashboard_results else 0
                })
                
                # Store execution history
                self._store_execution_history(
                    project_id=project_id,
                    natural_language_query=natural_language_query,
                    total_queries=len(dashboard_queries),
                    result=final_result,
                    workflow_id=dashboard_context.get("workflow_id"),
                    dashboard_template=dashboard_context.get("template")
                )
                
                return final_result
            else:
                error_msg = result.get("post_process", {}).get("error", "Dashboard orchestration failed")
                send_status_update("dashboard_processing_failed", {
                    "error": error_msg,
                    "project_id": project_id
                })
                raise RuntimeError(error_msg)
            
        except Exception as e:
            logger.error(f"Error in dashboard processing: {e}")
            send_status_update("processing_failed", {
                "error": str(e),
                "project_id": project_id
            })
            raise
    
    async def execute_dashboard_only(
        self,
        dashboard_queries: List[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute dashboard without conditional formatting using agent pipelines
        
        Args:
            dashboard_queries: List of SQL queries for dashboard charts
            project_id: Project identifier
            status_callback: Callback for streaming status updates
            
        Returns:
            Dashboard execution result
        """
        try:
            # Use dashboard streaming pipeline directly
            if not self._agent_pipelines["dashboard_streaming"]:
                error_msg = "Dashboard streaming pipeline is not available"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = await self._agent_pipelines["dashboard_streaming"].run(
                queries=dashboard_queries,
                status_callback=status_callback,
                configuration={
                    "concurrent_execution": True,
                    "max_concurrent_queries": 5,
                    "continue_on_error": True,
                    "stream_intermediate_results": True
                },
                project_id=project_id
            )
            
            # Store execution history
            self._store_execution_history(
                project_id=project_id,
                natural_language_query=None,
                total_queries=len(dashboard_queries),
                result=result
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in dashboard-only execution: {e}")
            raise
    
    async def process_conditional_formatting_only(
        self,
        natural_language_query: str,
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process only conditional formatting without executing dashboard using agent pipelines
        
        Args:
            natural_language_query: Natural language query for conditional formatting
            dashboard_context: Context about dashboard charts and columns
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            
        Returns:
            Conditional formatting configuration result
        """
        try:
            # Use conditional formatting pipeline directly
            if not self._agent_pipelines["conditional_formatting"]:
                error_msg = "Conditional formatting pipeline is not available"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = await self._agent_pipelines["conditional_formatting"].run(
                natural_language_query=natural_language_query,
                dashboard_context=dashboard_context,
                project_id=project_id,
                additional_context=additional_context,
                time_filters=time_filters
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in conditional formatting only: {e}")
            raise
    
    async def validate_dashboard_configuration(
        self,
        dashboard_queries: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        natural_language_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate dashboard configuration and queries
        
        Args:
            dashboard_queries: List of SQL queries to validate
            dashboard_context: Dashboard context to validate
            natural_language_query: Optional natural language query to validate
            
        Returns:
            Validation result with any issues found
        """
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        try:
            # Validate dashboard queries
            for i, query_data in enumerate(dashboard_queries):
                query_validation = self._validate_single_query(query_data, i)
                if not query_validation["valid"]:
                    validation_result["valid"] = False
                    validation_result["issues"].extend(query_validation["issues"])
                
                if query_validation["warnings"]:
                    validation_result["warnings"].extend(query_validation["warnings"])
                
                if query_validation["recommendations"]:
                    validation_result["recommendations"].extend(query_validation["recommendations"])
            
            # Validate dashboard context
            context_validation = self._validate_dashboard_context(dashboard_context)
            if not context_validation["valid"]:
                validation_result["valid"] = False
                validation_result["issues"].extend(context_validation["issues"])
            
            # Validate natural language query if provided
            if natural_language_query:
                query_validation = self._validate_natural_language_query(natural_language_query)
                if not query_validation["valid"]:
                    validation_result["valid"] = False
                    validation_result["issues"].extend(query_validation["issues"])
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error in dashboard configuration validation: {e}")
            validation_result["valid"] = False
            validation_result["issues"].append(f"Validation error: {str(e)}")
            return validation_result
    
    def _validate_single_query(self, query_data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Validate a single dashboard query"""
        validation = {"valid": True, "issues": [], "warnings": [], "recommendations": []}
        
        # Check required fields
        required_fields = ["sql", "query"]
        for field in required_fields:
            if field not in query_data or not query_data[field]:
                validation["valid"] = False
                validation["issues"].append(f"Query {index}: Missing required field '{field}'")
        
        # Check SQL syntax (basic validation)
        if "sql" in query_data and query_data["sql"]:
            sql = query_data["sql"].strip()
            if not sql.endswith(";"):
                validation["warnings"].append(f"Query {index}: SQL should end with semicolon")
            
            if "select" not in sql.lower():
                validation["valid"] = False
                validation["issues"].append(f"Query {index}: SQL must contain SELECT statement")
        
        # Check chart_id
        if "chart_id" not in query_data:
            validation["warnings"].append(f"Query {index}: Consider adding chart_id for better organization")
        
        return validation
    
    def _validate_dashboard_context(self, dashboard_context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dashboard context structure"""
        validation = {"valid": True, "issues": [], "warnings": [], "recommendations": []}
        
        # Check required fields
        if "charts" not in dashboard_context:
            validation["valid"] = False
            validation["issues"].append("Missing 'charts' field in dashboard context")
        
        if "available_columns" not in dashboard_context:
            validation["warnings"].append("Missing 'available_columns' field in dashboard context")
        
        # Validate charts structure
        if "charts" in dashboard_context:
            charts = dashboard_context["charts"]
            if not isinstance(charts, list):
                validation["valid"] = False
                validation["issues"].append("'charts' field must be a list")
            else:
                for i, chart in enumerate(charts):
                    if not isinstance(chart, dict):
                        validation["valid"] = False
                        validation["issues"].append(f"Chart {i} must be a dictionary")
                    elif "chart_id" not in chart:
                        validation["warnings"].append(f"Chart {i}: Consider adding chart_id")
        
        return validation
    
    def _validate_natural_language_query(self, query: str) -> Dict[str, Any]:
        """Validate natural language query"""
        validation = {"valid": True, "issues": [], "warnings": [], "recommendations": []}
        
        if not query or not query.strip():
            validation["valid"] = False
            validation["issues"].append("Natural language query cannot be empty")
        
        if len(query.strip()) < 10:
            validation["warnings"].append("Natural language query seems too short, consider providing more detail")
        
        return validation
    
    
    def _create_nested_status_callback(
        self,
        parent_callback: Optional[Callable[[str, Dict[str, Any]], None]],
        prefix: str
    ) -> Callable[[str, Dict[str, Any]], None]:
        """Create a nested status callback with prefix"""
        def nested_callback(status: str, details: Dict[str, Any] = None):
            if parent_callback:
                try:
                    parent_callback(f"{prefix}_{status}", details or {})
                except Exception as e:
                    logger.error(f"Error in nested status callback: {e}")
        
        return nested_callback
    
    def _store_execution_history(
        self,
        project_id: str,
        natural_language_query: Optional[str],
        total_queries: int,
        result: Dict[str, Any],
        workflow_id: Optional[str] = None,
        dashboard_template: Optional[str] = None
    ):
        """Store execution history for analytics"""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "natural_language_query": natural_language_query,
            "total_queries": total_queries,
            "success": result.get("success", False),
            "conditional_formatting_applied": bool(result.get("chart_configurations")),
            "total_charts": len(result.get("dashboard_data", {}).get("results", {}))
        }
        
        if workflow_id:
            history_entry["workflow_id"] = workflow_id
        if dashboard_template:
            history_entry["dashboard_template"] = dashboard_template
            
        self._execution_history.append(history_entry)
        
        # Keep only last 100 entries
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]
    
    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent execution history"""
        return self._execution_history[-limit:] if self._execution_history else []
    
    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available dashboard templates"""
        return self._dashboard_templates.copy()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all dashboard agent pipelines"""
        return {
            "dashboard_orchestrator": {
                "available": self._dashboard_orchestrator is not None,
                "initialized": self._dashboard_orchestrator.is_initialized if self._dashboard_orchestrator else False
            },
            "pipeline_container_orchestrator": {
                "available": self._agent_pipelines.get("dashboard_orchestrator") is not None,
                "initialized": True
            },
            "conditional_formatting": {
                "available": self._agent_pipelines.get("conditional_formatting") is not None,
                "initialized": True
            },
            "dashboard_streaming": {
                "available": self._agent_pipelines.get("dashboard_streaming") is not None,
                "initialized": True
            },
            "enhanced_dashboard": {
                "available": self._agent_pipelines.get("enhanced_dashboard") is not None,
                "initialized": True
            },
            "pipeline_container": {
                "available": self.pipeline_container is not None,
                "pipeline_count": len(self.pipeline_container._pipelines) if self.pipeline_container else 0
            },
            "execution_history": {
                "total_entries": len(self._execution_history),
                "recent_entries": len(self._execution_history[-10:]) if self._execution_history else 0
            }
        }
    
    def clear_cache(self):
        """Clear configuration and execution caches"""
        self._configuration_cache.clear()
        self._execution_history.clear()
        # Also clear the BaseService cache
        super().clear_cache()


# Note: Factory function moved to SQLServiceContainer.create_dashboard_service()


# Example usage
async def example_dashboard_service_usage():
    """Example of using the refactored dashboard service as a pure API layer"""
    
    # Get dashboard service from service container
    # Note: In production, this would be injected via dependency injection
    # For this example, we'll create the service directly
    dashboard_service = DashboardService()
    
    # Sample dashboard queries
    dashboard_queries = [
        {
            "chart_id": "sales_chart",
            "sql": "SELECT region, SUM(sales_amount) as sales FROM sales_data GROUP BY region",
            "query": "Show sales by region",
            "data_description": "Sales data by region"
        },
        {
            "chart_id": "performance_chart",
            "sql": "SELECT date, performance_score FROM performance_data ORDER BY date",
            "query": "Show performance over time",
            "data_description": "Performance trends over time"
        }
    ]
    
    # Dashboard context
    dashboard_context = {
        "charts": [
            {
                "chart_id": "sales_chart",
                "type": "bar",
                "columns": ["region", "sales"],
                "query": "Show sales by region"
            },
            {
                "chart_id": "performance_chart",
                "type": "line",
                "columns": ["date", "performance_score"],
                "query": "Show performance over time"
            }
        ],
        "available_columns": ["date", "region", "sales", "quantity", "profit", "category", "status"],
        "data_types": {
            "date": "datetime",
            "region": "categorical",
            "sales": "numeric",
            "quantity": "numeric",
            "profit": "numeric",
            "category": "categorical",
            "status": "categorical"
        }
    }
    
    # Natural language formatting query
    natural_language_query = """
    Highlight sales amounts greater than $50,000 in green and less than $10,000 in red.
    Filter to show only data from the last quarter.
    Make the performance chart show only scores above 80.
    """
    
    # Status callback
    def status_callback(status: str, details: Dict[str, Any]):
        print(f"Status: {status} - {details}")
    
    # Process dashboard with conditional formatting (delegates to agent pipelines)
    result = await dashboard_service.process_dashboard_with_conditional_formatting(
        natural_language_query=natural_language_query,
        dashboard_queries=dashboard_queries,
        project_id="example_project",
        dashboard_context=dashboard_context,
        additional_context={"user_id": "user123"},
        time_filters={"period": "last_quarter"},
        status_callback=status_callback
    )
    
    print("Dashboard Service Result:")
    print(f"Success: {result['success']}")
    print(f"Total charts: {len(result['dashboard_data'].get('results', {}))}")
    print(f"Conditional formatting applied: {result['metadata']['conditional_formatting_applied']}")
    print(f"Orchestration metadata: {result['metadata'].get('orchestration_metadata', {})}")
    
    return result


if __name__ == "__main__":
    # Run example
    import asyncio
    asyncio.run(example_dashboard_service_usage())