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
from app.services.workflow_integration import get_workflow_integration_service

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
                "conditional_formatting": self.pipeline_container.get_pipeline("conditional_formatting_generation"),  # Uses ConditionalFormattingPipeline
                "dashboard_streaming": self.pipeline_container.get_pipeline("dashboard_streaming"),
                "enhanced_dashboard": self.pipeline_container.get_pipeline("enhanced_dashboard_streaming"),
                "dashboard_summary": self.pipeline_container.get_pipeline("dashboard_summary"),
                "sql_refresh": self.pipeline_container.get_pipeline("sql_refresh")
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
                "enhanced_dashboard": None,
                "dashboard_summary": None,
                "sql_refresh": None
            }
        
        # Configuration cache and execution history
        self._configuration_cache = {}
        self._execution_history = []
        
        # Initialize workflow integration service
        self._workflow_integration = get_workflow_integration_service()
        
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
            
            # Validate dashboard queries before passing to pipeline
            if not dashboard_queries or not isinstance(dashboard_queries, list) or len(dashboard_queries) == 0:
                error_msg = f"No valid dashboard queries found. Workflow may not have completed query generation yet. Got {type(dashboard_queries)} with length: {len(dashboard_queries) if isinstance(dashboard_queries, list) else 'N/A'}"
                logger.error(error_msg)
                send_status_update("dashboard_processing_failed", {
                    "error": error_msg,
                    "project_id": project_id
                })
                raise ValueError(f"Dashboard queries must be a non-empty list. {error_msg}")
            
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
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Process only conditional formatting without executing dashboard using ConditionalFormattingPipeline
        
        This method uses the standalone ConditionalFormattingPipeline which processes
        conditional formatting requests independently from dashboard flows.
        
        Args:
            natural_language_query: Natural language query for conditional formatting
            dashboard_context: Context about dashboard charts and columns (supports both charts and thread_components)
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Optional callback for status updates
            
        Returns:
            Conditional formatting configuration result in standard format with post_process structure
        """
        try:
            # Use conditional formatting pipeline from container
            if not self._agent_pipelines["conditional_formatting"]:
                error_msg = "Conditional formatting pipeline is not available"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Normalize dashboard_context to handle thread_components structure
            normalized_context = self._normalize_dashboard_context_for_conditional_formatting(dashboard_context)
            
            # Call the ConditionalFormattingPipeline
            result = await self._agent_pipelines["conditional_formatting"].run(
                natural_language_query=natural_language_query,
                dashboard_context=normalized_context,
                project_id=project_id,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback
            )
            
            # Format result to match expected service response structure
            # ConditionalFormattingPipeline returns result directly, not in post_process
            configuration = result.get("configuration")
            
            # Helper function to convert Enum values to strings recursively
            def convert_enums_to_strings(obj):
                """Recursively convert Enum values to their string values"""
                from enum import Enum
                if isinstance(obj, Enum):
                    return obj.value
                elif isinstance(obj, dict):
                    return {k: convert_enums_to_strings(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_enums_to_strings(item) for item in obj]
                else:
                    return obj
            
            # Convert DashboardConfiguration object to dict if needed
            configuration_dict = None
            if configuration:
                if isinstance(configuration, dict):
                    configuration_dict = convert_enums_to_strings(configuration)
                else:
                    # It's a dataclass or object, convert to dict
                    from dataclasses import asdict, is_dataclass
                    if is_dataclass(configuration):
                        # Use asdict which handles nested dataclasses
                        configuration_dict = asdict(configuration)
                        # Convert all Enum values to strings recursively
                        configuration_dict = convert_enums_to_strings(configuration_dict)
                    else:
                        logger.warning(f"Unexpected configuration type: {type(configuration)}")
                        configuration_dict = None
            
            formatted_result = {
                "post_process": {
                    "success": result.get("success", False),
                    "configuration": configuration_dict,
                    "chart_configurations": result.get("chart_configurations", {}),
                    "sql_expansions": result.get("sql_expansions", {}),
                    "time_filters": result.get("time_filters"),
                    "metadata": result.get("metadata", {})
                },
                "metadata": {
                    "pipeline_name": "conditional_formatting_pipeline",
                    "execution_timestamp": result.get("metadata", {}).get("generated_at", datetime.now().isoformat()),
                    "project_id": project_id,
                    "natural_language_query": natural_language_query
                }
            }
            
            # Add error if present
            if not result.get("success", False):
                formatted_result["post_process"]["error"] = result.get("error", "Unknown error")
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error in conditional formatting only: {e}")
            # Return error in expected format
            return {
                "post_process": {
                    "success": False,
                    "error": str(e),
                    "chart_configurations": {},
                    "sql_expansions": {},
                    "time_filters": None
                },
                "metadata": {
                    "pipeline_name": "conditional_formatting_pipeline",
                    "execution_timestamp": datetime.now().isoformat(),
                    "project_id": project_id,
                    "error": str(e)
                }
            }
    
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
        
        # Check chart_schema
        if "chart_schema" not in query_data or not query_data.get("chart_schema"):
            validation["warnings"].append(f"Query {index}: Consider adding chart_schema for better visualization")
        
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
                    elif "chart_schema" not in chart or not chart.get("chart_schema"):
                        validation["warnings"].append(f"Chart {i}: Consider adding chart_schema")
        
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
            "dashboard_summary": {
                "available": self._agent_pipelines.get("dashboard_summary") is not None,
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
    
    async def render_dashboard_from_workflow_db(
        self,
        workflow_id: str,
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        render_options: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Render dashboard from workflow database model
        
        Args:
            workflow_id: Workflow ID from database
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting
            additional_context: Additional context for rendering
            time_filters: Time-based filters
            render_options: Options for rendering (preview, full, etc.)
            status_callback: Callback for status updates
            
        Returns:
            Complete dashboard result with workflow-driven configuration
        """
        try:
            # Use workflow integration service to render dashboard
            workflow_result = await self._workflow_integration.render_dashboard_from_workflow(
                workflow_id=workflow_id,
                project_id=project_id,
                natural_language_query=natural_language_query,
                additional_context=additional_context,
                time_filters=time_filters,
                render_options=render_options
            )
            
            if not workflow_result.get("success"):
                raise ValueError(workflow_result.get("error", f"Failed to render workflow {workflow_id}"))
            
            # Extract data from workflow result
            dashboard_queries = workflow_result["dashboard_queries"]
            dashboard_context = workflow_result["dashboard_context"]
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_dashboard_rendering_started",
                {
                    "workflow_id": workflow_id,
                    "project_id": project_id,
                    "total_queries": len(dashboard_queries),
                    "workflow_state": workflow_result.get("workflow_metadata", {}).get("state"),
                    "render_mode": render_options.get("mode", "full") if render_options else "full"
                }
            )
            
            # Process dashboard with conditional formatting
            orchestration_result = await self.process_dashboard_with_conditional_formatting(
                natural_language_query=natural_language_query,
                dashboard_queries=dashboard_queries,
                project_id=project_id,
                dashboard_context=dashboard_context,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback
            )
            
            # Transform orchestration result to the expected dashboard format
            formatted_result = self._format_dashboard_output(
                workflow_data=workflow_result,
                orchestration_result=orchestration_result,
                thread_components=workflow_result.get("thread_components", []),
                project_id=project_id
            )
            
            # Add workflow metadata to result
            formatted_result["workflow_metadata"] = {
                "workflow_id": workflow_id,
                "workflow_state": workflow_result.get("workflow_metadata", {}).get("state"),
                "workflow_type": "dashboard_workflow",
                "dashboard_template": dashboard_context.get("template"),
                "workflow_source": "database",
                "render_options": render_options or {},
                "transformed_at": workflow_result.get("transformed_at")
            }
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error rendering dashboard from workflow DB: {e}")
            self._send_status_update(
                status_callback,
                "workflow_dashboard_rendering_failed",
                {
                    "error": str(e),
                    "workflow_id": workflow_id,
                    "project_id": project_id
                }
            )
            raise
    
    async def render_dashboard_from_workflow_data(
        self,
        workflow_data: Dict[str, Any],
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        render_options: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Render dashboard from workflow data passed in request
        
        Args:
            workflow_data: Complete workflow data from request
            project_id: Project identifier
            natural_language_query: Natural language query for conditional formatting
            additional_context: Additional context for rendering
            time_filters: Time-based filters
            render_options: Options for rendering (preview, full, etc.)
            status_callback: Callback for status updates
            
        Returns:
            Complete dashboard result with workflow-driven configuration in the expected format
        """
        try:
            # Extract workflow information
            workflow_id = workflow_data.get("workflow_id")
            workflow_state = workflow_data.get("state")
            thread_components = workflow_data.get("thread_components", [])
            workflow_metadata = workflow_data.get("workflow_metadata", {})
            
            # TODO: Add workflow state validation in future
            # Check if workflow is in a state that allows dashboard rendering
            # if workflow_state in ["configuring", "pending", "initializing"]:
            #     error_msg = f"Workflow is in '{workflow_state}' state and not ready for dashboard rendering. Please wait for the workflow to complete query generation."
            #     logger.warning(error_msg)
            #     self._send_status_update(
            #         status_callback,
            #         "workflow_dashboard_rendering_failed",
            #         {
            #             "error": error_msg,
            #             "workflow_id": workflow_id,
            #             "project_id": project_id,
            #             "workflow_state": workflow_state
            #         }
            #     )
            #     raise ValueError(error_msg)
            
            # Transform workflow data to dashboard format
            logger.info(f"Extracting queries from {len(thread_components)} thread components")
            dashboard_queries = self._extract_queries_from_workflow_components(thread_components)
            logger.info(f"Extracted {len(dashboard_queries)} dashboard queries")
            
            # Refresh SQL queries with current date/time
            dashboard_queries = await self._refresh_sql_queries(
                dashboard_queries=dashboard_queries,
                project_id=project_id,
                status_callback=status_callback
            )
            
            dashboard_context = self._create_dashboard_context_from_workflow_data(workflow_data)
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_dashboard_rendering_started",
                {
                    "workflow_id": workflow_id,
                    "project_id": project_id,
                    "total_queries": len(dashboard_queries),
                    "workflow_state": workflow_state,
                    "render_mode": render_options.get("mode", "full") if render_options else "full",
                    "total_components": len(thread_components)
                }
            )
            
            # Process dashboard with conditional formatting
            orchestration_result = await self.process_dashboard_with_conditional_formatting(
                natural_language_query=natural_language_query,
                dashboard_queries=dashboard_queries,
                project_id=project_id,
                dashboard_context=dashboard_context,
                additional_context=additional_context,
                time_filters=time_filters,
                status_callback=status_callback
            )
            
            # Transform orchestration result to the expected dashboard format
            formatted_result = self._format_dashboard_output(
                workflow_data=workflow_data,
                orchestration_result=orchestration_result,
                thread_components=thread_components,
                project_id=project_id
            )
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"Error rendering dashboard from workflow data: {e}")
            self._send_status_update(
                status_callback,
                "workflow_dashboard_rendering_failed",
                {
                    "error": str(e),
                    "workflow_id": workflow_data.get("workflow_id"),
                    "project_id": project_id
                }
            )
            raise
    
    def _format_dashboard_output(
        self,
        workflow_data: Dict[str, Any],
        orchestration_result: Dict[str, Any],
        thread_components: List[Dict[str, Any]],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Format dashboard output in the expected format that preserves original workflow data
        and enriches it with orchestration results
        
        Args:
            workflow_data: Original workflow data from request
            orchestration_result: Result from dashboard orchestration pipeline
            thread_components: Thread components from workflow
            project_id: Project identifier
            
        Returns:
            Formatted dashboard output in the expected structure
        """
        try:
            # Extract orchestration results
            dashboard_data = orchestration_result.get("dashboard_data", {})
            enhanced_dashboard = orchestration_result.get("enhanced_dashboard", {})
            results = dashboard_data.get("results", {})
            
            # Build formatted components by enriching original components with orchestration results
            formatted_components = []
            component_positions = {}  # Track component positions for dashboard config
            
            for i, component in enumerate(thread_components):
                component_id = component.get("id")
                component_type = component.get("type", "question")
                
                # Find matching result from orchestration
                result_data = None
                for query_id, query_result in results.items():
                    # Skip if query_result is not a dictionary
                    if not isinstance(query_result, dict):
                        continue
                    if query_result.get("query_index") == i or query_result.get("component_id") == component_id:
                        result_data = query_result
                        break
                
                # Build enriched component preserving original data
                formatted_component = {
                    "id": component_id,
                    "type": component_type,
                    "chart": component.get("chart", {}),
                    "table": component.get("table", {}),
                    "metadata": component.get("metadata", {}),
                    "overview": component.get("overview", {}),
                    "question": component.get("question", ""),
                    "sequence": component.get("sequence", i + 1),
                    "reasoning": component.get("reasoning", ""),
                    "sql_query": component.get("sql_query", ""),
                    "data_count": component.get("data_count", 0),
                    "description": component.get("description", ""),
                    "sample_data": component.get("sample_data", {}),
                    "chart_schema": component.get("chart_schema", {}),
                    "configuration": component.get("configuration", {}),
                    "data_overview": component.get("data_overview"),
                    "is_configured": component.get("is_configured", False),
                    "executive_summary": component.get("executive_summary", ""),
                    "validation_results": component.get("validation_results", {}),
                    "visualization_data": component.get("visualization_data", {})
                }
                
                # Preserve metadata from orchestration results if original metadata is empty
                if not formatted_component["metadata"] and result_data and result_data.get("thread_metadata"):
                    formatted_component["metadata"] = result_data.get("thread_metadata", {})
                    logger.info(f"Restored metadata for component {component_id} from orchestration results")
                
                # Extract positioning information from metadata for dashboard config
                component_metadata = formatted_component.get("metadata", {})
                
                # Also check if metadata was preserved in orchestration results as thread_metadata
                if not component_metadata and result_data:
                    component_metadata = result_data.get("thread_metadata", {})
                    # Update the formatted component metadata as well
                    if component_metadata:
                        formatted_component["metadata"] = component_metadata
                
                # Check if component has thread_metadata in the original thread_components
                if not component_metadata:
                    # Look for thread_metadata in the original thread_components
                    for thread_comp in thread_components:
                        if thread_comp.get("id") == component_id and thread_comp.get("thread_metadata"):
                            component_metadata = thread_comp.get("thread_metadata", {})
                            logger.info(f"Found thread_metadata in original thread_components for component {component_id}")
                            break
                
                if component_metadata and "position" in component_metadata:
                    component_positions[component_id] = {
                        "position": component_metadata["position"],
                        "ui_visibility": component_metadata.get("ui_visibility", {}),
                        "project_id": component_metadata.get("project_id", project_id),
                        "data_description": component_metadata.get("data_description", ""),
                        "processing_stats": component_metadata.get("processing_stats", {})
                    }
                    logger.info(f"Extracted positioning for component {component_id}: {component_metadata.get('position', {})}")
                else:
                    logger.warning(f"No positioning metadata found for component {component_id}. Available metadata keys: {list(component_metadata.keys()) if component_metadata else 'None'}")
                    # Add a default position if no metadata is available
                    component_positions[component_id] = {
                        "position": {"x": 0, "y": 0, "width": 400, "height": 300},
                        "ui_visibility": {"visible": True, "collapsed": False},
                        "project_id": project_id,
                        "data_description": f"Component {component_id}",
                        "processing_stats": {}
                    }
                    logger.info(f"Added default positioning for component {component_id}")
                
                # Enrich with orchestration result if available
                if result_data:
                    # Update chart with execution info
                    if "chart" not in formatted_component or not formatted_component["chart"]:
                        formatted_component["chart"] = {}
                    
                    formatted_component["chart"]["execution_info"] = {
                        "data_count": result_data.get("row_count", 0),
                        "execution_config": result_data.get("execution_config", {}),
                        "validation_success": result_data.get("success", False)
                    }
                    
                    # Update with result data if available
                    if result_data.get("data"):
                        formatted_component["sample_data"] = {
                            "data": result_data.get("data", []),
                            "columns": result_data.get("columns", [])
                        }
                        formatted_component["data_count"] = len(result_data.get("data", []))
                    
                    # Update executive summary from orchestration result
                    if result_data.get("executive_summary"):
                        formatted_component["executive_summary"] = result_data.get("executive_summary")
                    
                    # Update overview with insights from orchestration
                    if result_data.get("insights") or result_data.get("summary"):
                        if "overview" not in formatted_component:
                            formatted_component["overview"] = {}
                        
                        if result_data.get("insights"):
                            formatted_component["overview"]["insights"] = result_data.get("insights")
                        
                        if result_data.get("summary"):
                            formatted_component["overview"]["summary"] = result_data.get("summary")
                    
                    # Update reasoning from orchestration result
                    if result_data.get("reasoning"):
                        formatted_component["reasoning"] = result_data.get("reasoning")
                    
                    # Update data overview from orchestration result
                    if result_data.get("data_overview"):
                        formatted_component["data_overview"] = result_data.get("data_overview")
                    
                    # Update visualization data from orchestration result
                    if result_data.get("visualization_data"):
                        formatted_component["visualization_data"] = result_data.get("visualization_data")
                    
                    # Update validation results from orchestration
                    if result_data.get("validation_results"):
                        formatted_component["validation_results"] = result_data.get("validation_results")
                    
                    # Apply conditional formatting if available
                    if enhanced_dashboard and enhanced_dashboard.get("conditional_formatting_rules"):
                        component_formatting = enhanced_dashboard["conditional_formatting_rules"].get(str(i))
                        if component_formatting:
                            formatted_component["conditional_formatting"] = component_formatting
                
                formatted_components.append(formatted_component)
            
            # Build final output in expected format
            formatted_output = {
                "dashboard_id": workflow_data.get("dashboard_id", workflow_data.get("workflow_id")),
                "dashboard_name": workflow_data.get("dashboard_name", "Dashboard"),
                "dashboard_description": workflow_data.get("dashboard_description", ""),
                "DashboardType": workflow_data.get("DashboardType", "Dynamic"),
                "content": {
                    "status": workflow_data.get("content", {}).get("status", "rendered"),
                    "components": formatted_components
                },
                "is_active": workflow_data.get("is_active", True),
                "version": workflow_data.get("version", "1.0"),
                "created_at": workflow_data.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
                "user_id": workflow_data.get("user_id", ""),
                "workflow_id": workflow_data.get("workflow_id", ""),
                "permissions": workflow_data.get("permissions", {"Action": "view"})
            }
            
            # Add global insights and summaries from enhanced dashboard if available
            if enhanced_dashboard:
                # Add global executive summary if available
                if enhanced_dashboard.get("global_executive_summary"):
                    formatted_output["global_executive_summary"] = enhanced_dashboard.get("global_executive_summary")
                
                # Add global insights if available
                if enhanced_dashboard.get("global_insights"):
                    formatted_output["global_insights"] = enhanced_dashboard.get("global_insights")
                
                # Add dashboard-level insights to content
                if enhanced_dashboard.get("dashboard_insights"):
                    formatted_output["content"]["dashboard_insights"] = enhanced_dashboard.get("dashboard_insights")
                
                # Add performance metrics if available
                if enhanced_dashboard.get("performance_metrics"):
                    formatted_output["performance_metrics"] = enhanced_dashboard.get("performance_metrics")
            
            # Generate overall dashboard summary if not present
            if not formatted_output.get("global_executive_summary") and formatted_components:
                # Create a concise dashboard-level summary instead of duplicating component details
                total_components = len(formatted_components)
                dashboard_name = formatted_output.get("dashboard_name", "Dashboard")
                workflow_id = formatted_output.get("workflow_id", "")
                
                # Extract key insights from the first component for a high-level overview
                first_component = formatted_components[0]
                component_question = first_component.get("question", "data analysis")
                data_count = first_component.get("data_count", 0)
                
                # Create a concise global summary
                formatted_output["global_executive_summary"] = f"**DASHBOARD OVERVIEW**\n\n**{dashboard_name}** (Workflow: {workflow_id})\n\nThis dashboard provides comprehensive analysis across {total_components} component(s), focusing on '{component_question}'. The analysis covers {data_count} data points and delivers actionable insights for organizational decision-making.\n\n**Key Focus Areas:**\n- Performance metrics and completion rates\n- Data-driven insights for strategic planning\n- Actionable recommendations for improvement"
            
            # Add dashboard summary results from orchestration if available
            dashboard_summary = orchestration_result.get("post_process", {}).get("dashboard_summary")
            if dashboard_summary and dashboard_summary.get("success"):
                summary_data = dashboard_summary
                
                # Add global executive summary from dashboard summary pipeline
                if summary_data.get("global_executive_summary"):
                    formatted_output["global_executive_summary"] = summary_data.get("global_executive_summary")
                
                # Add global insights from dashboard summary pipeline
                if summary_data.get("global_insights"):
                    formatted_output["global_insights"] = summary_data.get("global_insights")
                
                # Add trend analysis if available
                if summary_data.get("trend_analysis"):
                    formatted_output["trend_analysis"] = summary_data.get("trend_analysis")
                
                # Add correlation analysis if available
                if summary_data.get("correlation_analysis"):
                    formatted_output["correlation_analysis"] = summary_data.get("correlation_analysis")
                
                # Add recommendations if available
                if summary_data.get("recommendations"):
                    formatted_output["recommendations"] = summary_data.get("recommendations")
                
                # Add dashboard insights to content
                if summary_data.get("dashboard_insights"):
                    formatted_output["content"]["dashboard_insights"] = summary_data.get("dashboard_insights")
            
            # Add orchestration metadata
            if orchestration_result.get("metadata", {}).get("orchestration_metadata"):
                formatted_output["orchestration_metadata"] = orchestration_result["metadata"]["orchestration_metadata"]
            
            # Create dashboard configuration with component positioning
            dashboard_config = {
                "template": workflow_data.get("workflow_metadata", {}).get("dashboard_template", "default"),
                "layout": workflow_data.get("workflow_metadata", {}).get("dashboard_layout", "grid"),
                "refresh_rate": workflow_data.get("workflow_metadata", {}).get("refresh_rate", 300),
                "component_positions": component_positions,
                "total_components": len(formatted_components),
                "project_id": project_id,
                "workflow_id": workflow_data.get("workflow_id", ""),
                "created_at": datetime.now().isoformat()
            }
            
            # Return in the expected DashboardResponse format
            return {
                "success": True,
                "dashboard_data": formatted_output,
                "conditional_formatting": enhanced_dashboard.get("conditional_formatting_rules", {}),
                "chart_configurations": orchestration_result.get("dashboard_data", {}).get("chart_configurations", {}),
                "dashboard_config": dashboard_config,
                "metadata": orchestration_result.get("metadata", {}),
                "workflow_metadata": workflow_data.get("workflow_metadata", {}),
                "global_executive_summary": formatted_output.get("global_executive_summary"),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error formatting dashboard output: {e}")
            raise

    def _extract_queries_from_workflow_components(self, thread_components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract dashboard queries from workflow thread components"""
        queries = []
        
        try:
            logger.info(f"Processing {len(thread_components)} thread components")
            for i, component in enumerate(thread_components):
                component_type = component.get("type", "question").lower()
                has_sql_query = bool(component.get("sql_query"))
                
                logger.info(f"Component {i}: type='{component_type}', has_sql_query={has_sql_query}")
                logger.info(f"Component {i} sql_query: {component.get('sql_query', 'None')[:100]}...")
                
                # Only process components that have SQL queries
                if component.get("sql_query") and component_type in ["chart", "table", "metric", "sql_summary", "question"]:
                    logger.info(f"Processing component {i} as valid query component")
                    
                    # Extract project_id from component, checking multiple possible locations
                    component_project_id = component.get("project_id")
                    if not component_project_id:
                        # Check metadata field for backward compatibility
                        metadata = component.get("thread_metadata") or component.get("metadata") or {}
                        if isinstance(metadata, dict):
                            component_project_id = metadata.get("project_id")
                    
                    query_data = {
                        "chart_schema": component.get("chart", {}).get("chart_schema", {}),
                        "sql": component.get("sql_query", ""),
                        "query": component.get("question", ""),
                        "data_description": component.get("description", ""),
                        "component_type": component_type,
                        "component_id": component.get("id"),
                        "sequence_order": component.get("sequence", 0),
                        "configuration": component.get("configuration", {}),
                        "chart_config": component.get("chart", {}).get("chart_schema", {}),
                        "table_config": component.get("table", {}),
                        "alert_config": component.get("alert_config", {}),
                        "executive_summary": component.get("executive_summary"),
                        "data_overview": component.get("data_overview"),
                        "visualization_data": component.get("visualization_data", {}),
                        "sample_data": component.get("sample_data", {}),
                        "thread_metadata": component.get("metadata", {}),
                        "reasoning": component.get("reasoning"),
                        "data_count": component.get("data_count"),
                        "validation_results": component.get("validation_results", {}),
                        "project_id": component_project_id  # Include per-component project_id if available
                    }
                    queries.append(query_data)
                else:
                    logger.info(f"Skipping component {i}: type='{component_type}', has_sql_query={has_sql_query}")
            
            # Sort by sequence order
            queries.sort(key=lambda x: x.get("sequence_order", 0))
            
            logger.info(f"Extracted {len(queries)} dashboard queries from workflow components")
            return queries
            
        except Exception as e:
            logger.error(f"Error extracting queries from workflow components: {e}")
            return []
    
    def _create_dashboard_context_from_workflow_data(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create dashboard context from workflow data"""
        try:
            workflow_metadata = workflow_data.get("workflow_metadata", {})
            thread_components = workflow_data.get("thread_components", [])
            
            # Extract available columns from components
            available_columns = set()
            data_types = {}
            
            for component in thread_components:
                if component.get("data_overview"):
                    overview = component["data_overview"]
                    if "columns" in overview:
                        for col in overview["columns"]:
                            available_columns.add(col.get("name", ""))
                            data_types[col.get("name", "")] = col.get("type", "string")
                
                # Also extract from sample_data if available
                if component.get("sample_data", {}).get("columns"):
                    for col in component["sample_data"]["columns"]:
                        available_columns.add(col)
            
            # Create dashboard context
            context = {
                "title": workflow_data.get("dashboard_name", workflow_metadata.get("report_title", f"Dashboard from Workflow {workflow_data.get('workflow_id')}")),
                "description": workflow_data.get("dashboard_description", workflow_metadata.get("report_description", "Dashboard generated from workflow configuration")),
                "template": workflow_metadata.get("dashboard_template", "default"),
                "layout": workflow_metadata.get("dashboard_layout", "grid"),
                "refresh_rate": workflow_metadata.get("refresh_rate", 300),
                "available_columns": list(available_columns),
                "data_types": data_types,
                "workflow_id": workflow_data.get("workflow_id"),
                "workflow_state": workflow_data.get("state"),
                "workflow_metadata": workflow_metadata,
                "total_components": len(thread_components),
                "charts": [comp for comp in thread_components if comp.get("type") in ["chart", "sql_summary", "question"]],
                "tables": [comp for comp in thread_components if comp.get("type") == "table"],
                "metrics": [comp for comp in thread_components if comp.get("type") == "metric"],
                "alerts": [comp for comp in thread_components if comp.get("type") == "alert"]
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Error creating dashboard context from workflow data: {e}")
            # Return basic context
            return {
                "title": workflow_data.get("dashboard_name", "Dashboard from Workflow"),
                "description": workflow_data.get("dashboard_description", "Dashboard generated from workflow configuration"),
                "template": "default",
                "layout": "grid",
                "refresh_rate": 300,
                "available_columns": [],
                "data_types": {},
                "workflow_id": workflow_data.get("workflow_id", "unknown"),
                "workflow_state": workflow_data.get("state", "unknown"),
                "total_components": len(workflow_data.get("thread_components", []))
            }
    
    async def _fetch_workflow_from_db(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Fetch workflow data from database using workflow integration service"""
        try:
            # Use workflow integration service to fetch from database
            workflow_data = await self._workflow_integration.fetch_workflow_from_db(workflow_id)
            
            if workflow_data:
                logger.info(f"Successfully fetched workflow {workflow_id} from database")
            else:
                logger.warning(f"Workflow {workflow_id} not found in database")
            
            return workflow_data
            
        except Exception as e:
            logger.error(f"Error fetching workflow from database: {e}")
            return None
    
    async def get_workflow_components(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get workflow components for a specific workflow"""
        try:
            # Use workflow integration service to get components
            components = await self._workflow_integration.fetch_workflow_components(workflow_id)
            
            # Format components for API response
            formatted_components = []
            for comp in components:
                formatted_comp = {
                    "id": comp.get("id"),
                    "component_type": comp.get("component_type"),
                    "question": comp.get("question"),
                    "description": comp.get("description"),
                    "sequence_order": comp.get("sequence_order"),
                    "configuration": comp.get("configuration", {}),
                    "chart_config": comp.get("chart_config", {}),
                    "table_config": comp.get("table_config", {}),
                    "alert_config": comp.get("alert_config", {}),
                    "sql": comp.get("sql", ""),
                    "query": comp.get("query", ""),
                    "data_description": comp.get("data_description", "")
                }
                formatted_components.append(formatted_comp)
            
            return formatted_components
            
        except Exception as e:
            logger.error(f"Error getting workflow components: {e}")
            return []
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status and metadata"""
        try:
            # Use workflow integration service to get status
            status = await self._workflow_integration.get_workflow_status(workflow_id)
            return status
            
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": str(e)
            }
    
    async def preview_dashboard_from_workflow(
        self,
        workflow_id: str,
        preview_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Preview dashboard from workflow without full rendering"""
        try:
            # Fetch workflow data
            workflow_data = await self._fetch_workflow_from_db(workflow_id)
            
            if not workflow_data:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            # Extract queries (limited for preview)
            dashboard_queries = self._extract_queries_from_workflow_components(workflow_data)
            
            # Limit queries for preview
            max_preview_queries = preview_options.get("max_queries", 2) if preview_options else 2
            dashboard_queries = dashboard_queries[:max_preview_queries]
            
            # Create dashboard context
            dashboard_context = self._create_dashboard_context_from_workflow(workflow_data)
            
            # Execute limited dashboard (preview mode)
            result = await self.execute_dashboard_only(
                dashboard_queries=dashboard_queries,
                project_id="preview_project"
            )
            
            # Add preview metadata
            result["preview_metadata"] = {
                "workflow_id": workflow_id,
                "preview_mode": True,
                "total_queries_previewed": len(dashboard_queries),
                "preview_options": preview_options or {}
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error previewing dashboard from workflow: {e}")
            raise

    async def _refresh_sql_queries(
        self,
        dashboard_queries: List[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Refresh SQL queries with current date/time parameters
        
        Args:
            dashboard_queries: List of dashboard query dictionaries
            project_id: Project identifier
            status_callback: Optional callback for status updates
            
        Returns:
            List of refreshed dashboard queries
        """
        if not self._agent_pipelines.get("sql_refresh"):
            logger.warning("SQL refresh pipeline not available, skipping query refresh")
            return dashboard_queries
        
        refreshed_queries = []
        
        try:
            self._send_status_update(
                status_callback,
                "sql_refresh_started",
                {
                    "project_id": project_id,
                    "total_queries": len(dashboard_queries)
                }
            )
            
            for i, query_data in enumerate(dashboard_queries):
                sql = query_data.get("sql", "")
                original_question = query_data.get("query", "")
                existing_reasoning = query_data.get("reasoning", "")
                
                if not sql or not sql.strip():
                    logger.warning(f"Query {i} has no SQL, skipping refresh")
                    refreshed_queries.append(query_data)
                    continue
                
                try:
                    # Use per-query project_id if available, otherwise fall back to global project_id
                    query_project_id = query_data.get("project_id") or project_id
                    
                    # Refresh the SQL query with existing reasoning
                    refresh_result = await self._agent_pipelines["sql_refresh"].run(
                        sql_query=sql,
                        original_question=original_question,
                        project_id=query_project_id,
                        existing_reasoning=existing_reasoning,
                        status_callback=self._create_nested_status_callback(
                            status_callback, f"sql_refresh_query_{i}"
                        )
                    )
                    
                    if refresh_result.get("success") and refresh_result.get("refreshed_sql"):
                        # Update the query with refreshed SQL
                        updated_query = query_data.copy()
                        updated_query["sql"] = refresh_result["refreshed_sql"]
                        updated_query["original_sql"] = sql  # Keep original for reference
                        updated_query["refresh_metadata"] = refresh_result.get("metadata", {})
                        refreshed_queries.append(updated_query)
                        logger.info(f"Refreshed SQL query {i} successfully")
                    else:
                        logger.warning(f"SQL refresh failed for query {i}, using original")
                        refreshed_queries.append(query_data)
                        
                except Exception as e:
                    logger.error(f"Error refreshing SQL query {i}: {e}")
                    # Use original query on error
                    refreshed_queries.append(query_data)
            
            self._send_status_update(
                status_callback,
                "sql_refresh_completed",
                {
                    "project_id": project_id,
                    "total_queries": len(dashboard_queries),
                    "refreshed_queries": len([q for q in refreshed_queries if "refresh_metadata" in q])
                }
            )
            
            return refreshed_queries
            
        except Exception as e:
            logger.error(f"Error in SQL refresh process: {e}")
            self._send_status_update(
                status_callback,
                "sql_refresh_failed",
                {
                    "project_id": project_id,
                    "error": str(e)
                }
            )
            # Return original queries on error
            return dashboard_queries
    
    def _send_status_update(
        self,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]],
        status: str,
        details: Dict[str, Any] = None
    ):
        """Send status update via callback if provided"""
        if status_callback:
            try:
                status_callback(status, details or {})
            except Exception as e:
                logger.error(f"Error in status callback: {str(e)}")
        logger.info(f"Dashboard Service Status - {status}: {details}")

    async def generate_dashboard_summary(
        self,
        dashboard_components: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Generate overall executive summary and insights for dashboard components
        
        Args:
            dashboard_components: List of dashboard components with their data and summaries
            dashboard_context: Overall dashboard context and metadata
            project_id: Project identifier
            additional_context: Additional context for summary generation
            status_callback: Callback for status updates
            
        Returns:
            Dictionary containing overall executive summary and insights
        """
        try:
            # Use dashboard summary pipeline from container
            if not self._agent_pipelines["dashboard_summary"]:
                error_msg = "Dashboard summary pipeline is not available"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = await self._agent_pipelines["dashboard_summary"].run(
                dashboard_components=dashboard_components,
                dashboard_context=dashboard_context,
                project_id=project_id,
                additional_context=additional_context,
                status_callback=status_callback
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating dashboard summary: {e}")
            raise

    def _normalize_dashboard_context_for_conditional_formatting(
        self,
        dashboard_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize dashboard_context to handle both charts and thread_components structures.
        
        If thread_components are provided, convert them to charts format for the pipeline.
        This allows the conditional formatting API to work with the thread_components structure
        while maintaining compatibility with the existing charts structure.
        
        Args:
            dashboard_context: Dashboard context that may contain charts or thread_components
            
        Returns:
            Normalized dashboard context with charts array populated
        """
        normalized_context = dashboard_context.copy()
        
        # Check if thread_components are provided
        thread_components = normalized_context.get("thread_components", [])
        
        if thread_components and not normalized_context.get("charts"):
            # Convert thread_components to charts format
            charts = []
            
            for component in thread_components:
                component_id = component.get("id") or component.get("component_id")
                component_type = component.get("component_type", "question")
                
                # Only process components that have SQL queries (charts, tables, questions)
                if component.get("sql_query") and component_type in ["chart", "table", "metric", "sql_summary", "question"]:
                    chart_info = {
                        "chart_id": str(component_id) if component_id else f"chart_{len(charts)}",
                        "id": str(component_id) if component_id else f"chart_{len(charts)}",
                        "component_id": str(component_id) if component_id else None,
                        "type": component_type,
                        "query": component.get("question", ""),
                        "sql": component.get("sql_query", ""),
                        "columns": component.get("sample_data", {}).get("columns", []),
                        "chart_schema": component.get("chart_schema") or component.get("chart_config", {}).get("chart_schema", {}),
                        "data_description": component.get("description", ""),
                        "sequence_order": component.get("sequence_order", len(charts)),
                        "component_type": component_type
                    }
                    
                    # Add chart_config if available
                    if component.get("chart_config"):
                        chart_info["chart_config"] = component.get("chart_config")
                    
                    # Add sample_data if available
                    if component.get("sample_data"):
                        chart_info["sample_data"] = component.get("sample_data")
                    
                    charts.append(chart_info)
            
            # Update normalized context with charts
            normalized_context["charts"] = charts
            
            # Also preserve thread_components for reference
            normalized_context["thread_components"] = thread_components
            
            logger.info(f"Converted {len(thread_components)} thread_components to {len(charts)} charts for conditional formatting")
        
        return normalized_context

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
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "region", "type": "nominal"},
                        "y": {"field": "sales", "type": "quantitative"}
                    }
                },
                "title": "Sales by Region"
            },
            "sql": "SELECT region, SUM(sales_amount) as sales FROM sales_data GROUP BY region",
            "query": "Show sales by region",
            "data_description": "Sales data by region"
        },
        {
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "line",
                    "encoding": {
                        "x": {"field": "date", "type": "temporal"},
                        "y": {"field": "performance_score", "type": "quantitative"}
                    }
                },
                "title": "Performance Over Time"
            },
            "sql": "SELECT date, performance_score FROM performance_data ORDER BY date",
            "query": "Show performance over time",
            "data_description": "Performance trends over time"
        }
    ]
    
    # Dashboard context
    dashboard_context = {
        "charts": [
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "region", "type": "nominal"},
                            "y": {"field": "sales", "type": "quantitative"}
                        }
                    },
                    "title": "Sales by Region"
                },
                "type": "bar",
                "columns": ["region", "sales"],
                "query": "Show sales by region"
            },
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "line",
                        "encoding": {
                            "x": {"field": "date", "type": "temporal"},
                            "y": {"field": "performance_score", "type": "quantitative"}
                        }
                    },
                    "title": "Performance Over Time"
                },
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