import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import asdict
import json
from pathlib import Path

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.agents.nodes.writers.dashboard_models import DashboardConfiguration
from app.services.servicebase import BaseService

# Import workflow models
try:
    from workflowservices.app.models.workflowmodels import (
        DashboardWorkflow, ThreadComponent, WorkflowState, ComponentType as WorkflowComponentType,
        AlertType, AlertSeverity, AlertStatus
    )
    WORKFLOW_MODELS_AVAILABLE = True
except ImportError:
    # Fallback if workflow models are not available
    WORKFLOW_MODELS_AVAILABLE = False
    logger = logging.getLogger("lexy-ai-service")
    logger.warning("Workflow models not available - using fallback models")

logger = logging.getLogger("lexy-ai-service")


class DashboardService(BaseService):
    """Enhanced dashboard service using PipelineContainer for all operations with workflow integration"""
    
    def __init__(self):
        """Initialize dashboard service with PipelineContainer and workflow support"""
        # Initialize BaseService with empty pipelines dict (we'll use PipelineContainer directly)
        super().__init__(pipelines={})
        
        self.pipeline_container = PipelineContainer.initialize()
        
        # Service registry for easy access
        try:
            self._services = {
                "dashboard_streaming": self.pipeline_container.get_pipeline("dashboard_streaming"),
                "conditional_formatting": self.pipeline_container.get_pipeline("conditional_formatting_generation"),
                "enhanced_dashboard": self.pipeline_container.get_pipeline("enhanced_dashboard_streaming")
            }
            
            # Validate that required services are available
            for service_name, service in self._services.items():
                if service is None:
                    logger.warning(f"Service '{service_name}' is not available - dashboard functionality may be limited")
                else:
                    logger.info(f"Service '{service_name}' initialized successfully")
                    
        except Exception as e:
            logger.error(f"Error initializing dashboard services: {e}")
            # Set all services to None to prevent crashes
            self._services = {
                "dashboard_streaming": None,
                "conditional_formatting": None,
                "enhanced_dashboard": None
            }
        
        # Configuration cache and execution history
        self._configuration_cache = {}
        self._execution_history = []
        self._workflow_cache = {}
        
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
        workflow_data: Union[Dict[str, Any], DashboardWorkflow, str],
        dashboard_queries: List[Dict[str, Any]],
        project_id: str,
        natural_language_query: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Process dashboard using workflow data from API or JSON file
        
        Args:
            workflow_data: Workflow data as dict, DashboardWorkflow object, or JSON file path
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
            # Parse workflow data
            workflow_info = self._parse_dashboard_workflow_data(workflow_data)
            
            if not workflow_info:
                raise ValueError("Invalid dashboard workflow data provided")
            
            # Extract dashboard configuration from workflow
            dashboard_config = self._extract_dashboard_config_from_workflow(workflow_info)
            thread_components = self._extract_thread_components_from_workflow(workflow_info)
            
            # Create enhanced dashboard context
            enhanced_context = self._create_enhanced_dashboard_context(
                workflow_info, dashboard_config, thread_components
            )
            
            # Send initial status update
            self._send_status_update(
                status_callback,
                "workflow_dashboard_processing_started",
                {
                    "project_id": project_id,
                    "workflow_id": workflow_info.get("id"),
                    "workflow_state": workflow_info.get("state"),
                    "total_components": len(thread_components),
                    "total_queries": len(dashboard_queries),
                    "dashboard_template": dashboard_config.get("template")
                }
            )
            
            # Process dashboard with workflow-driven configuration
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
                "components_processed": len(thread_components),
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
    
    def _parse_dashboard_workflow_data(
        self, 
        workflow_data: Union[Dict[str, Any], DashboardWorkflow, str]
    ) -> Optional[Dict[str, Any]]:
        """Parse dashboard workflow data from various input formats"""
        
        try:
            if isinstance(workflow_data, str):
                # Assume it's a file path
                if Path(workflow_data).exists():
                    return self._load_dashboard_workflow_from_json_file(workflow_data)
                else:
                    # Try to parse as JSON string
                    return json.loads(workflow_data)
            
            elif isinstance(workflow_data, dict):
                # Already a dictionary
                workflow_data["source"] = "dict_input"
                return workflow_data
            
            elif WORKFLOW_MODELS_AVAILABLE and isinstance(workflow_data, DashboardWorkflow):
                # SQLAlchemy model object
                return self._convert_dashboard_workflow_model_to_dict(workflow_data)
            
            else:
                logger.error(f"Unsupported dashboard workflow data type: {type(workflow_data)}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing dashboard workflow data: {e}")
            return None
    
    def _load_dashboard_workflow_from_json_file(self, file_path: str) -> Dict[str, Any]:
        """Load dashboard workflow data from JSON file"""
        try:
            with open(file_path, 'r') as f:
                workflow_data = json.load(f)
                workflow_data["source"] = "json_file"
                return workflow_data
        except Exception as e:
            logger.error(f"Error loading dashboard workflow from JSON file {file_path}: {e}")
            raise
    
    def _convert_dashboard_workflow_model_to_dict(self, workflow: DashboardWorkflow) -> Dict[str, Any]:
        """Convert SQLAlchemy dashboard workflow model to dictionary"""
        try:
            workflow_dict = {
                "id": str(workflow.id),
                "dashboard_id": str(workflow.dashboard_id),
                "user_id": str(workflow.user_id),
                "state": workflow.state.value if hasattr(workflow.state, 'value') else str(workflow.state),
                "current_step": workflow.current_step,
                "workflow_metadata": workflow.workflow_metadata or {},
                "error_message": workflow.error_message,
                "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
                "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
                "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
                "source": "workflow_model"
            }
            
            # Add thread components if available
            if hasattr(workflow, 'thread_components') and workflow.thread_components:
                workflow_dict["thread_components"] = [
                    self._convert_thread_component_to_dict(comp) 
                    for comp in workflow.thread_components
                ]
            
            return workflow_dict
            
        except Exception as e:
            logger.error(f"Error converting dashboard workflow model to dict: {e}")
            raise
    
    def _convert_thread_component_to_dict(self, component: ThreadComponent) -> Dict[str, Any]:
        """Convert SQLAlchemy thread component to dictionary"""
        try:
            component_dict = {
                "id": str(component.id),
                "workflow_id": str(component.workflow_id) if component.workflow_id else None,
                "report_workflow_id": str(component.report_workflow_id) if component.report_workflow_id else None,
                "thread_message_id": str(component.thread_message_id) if component.thread_message_id else None,
                "component_type": component.component_type.value if hasattr(component.component_type, 'value') else str(component.component_type),
                "sequence_order": component.sequence_order,
                "question": component.question,
                "description": component.description,
                "overview": component.overview,
                "chart_config": component.chart_config,
                "table_config": component.table_config,
                "alert_config": component.alert_config,
                "alert_status": component.alert_status.value if component.alert_status and hasattr(component.alert_status, 'value') else str(component.alert_status) if component.alert_status else None,
                "last_triggered": component.last_triggered.isoformat() if component.last_triggered else None,
                "trigger_count": component.trigger_count,
                "configuration": component.configuration or {},
                "is_configured": component.is_configured,
                "created_at": component.created_at.isoformat() if component.created_at else None,
                "updated_at": component.updated_at.isoformat() if component.updated_at else None
            }
            
            return component_dict
            
        except Exception as e:
            logger.error(f"Error converting thread component to dict: {e}")
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
    
    def _extract_thread_components_from_workflow(self, workflow_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract thread components from workflow data"""
        try:
            components = workflow_info.get("thread_components", [])
            
            # Sort by sequence order
            components.sort(key=lambda x: x.get("sequence_order", 0))
            
            return components
            
        except Exception as e:
            logger.error(f"Error extracting thread components from workflow: {e}")
            return []
    
    def _create_enhanced_dashboard_context(
        self,
        workflow_info: Dict[str, Any],
        dashboard_config: Dict[str, Any],
        thread_components: List[Dict[str, Any]]
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
            
            # Add component-specific configurations
            context["components"] = []
            for comp in thread_components:
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
        Process dashboard with conditional formatting using PipelineContainer
        
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
            
            # Step 1: Process conditional formatting if provided
            conditional_formatting_result = None
            chart_configurations = {}
            
            if natural_language_query and natural_language_query.strip():
                # Check if conditional formatting service is available
                if not self._services["conditional_formatting"]:
                    error_msg = "Conditional formatting service is not available"
                    logger.error(error_msg)
                    send_status_update("conditional_formatting_failed", {
                        "error": error_msg,
                        "project_id": project_id
                    })
                    # Continue without conditional formatting
                    chart_configurations = {}
                else:
                    send_status_update("conditional_formatting_started", {
                        "query": natural_language_query,
                        "project_id": project_id
                    })
                    
                    # Use the conditional formatting pipeline from PipelineContainer
                    conditional_formatting_result = await self._services["conditional_formatting"].run(
                        natural_language_query=natural_language_query,
                        dashboard_context=dashboard_context,
                        project_id=project_id,
                        additional_context=additional_context,
                        time_filters=time_filters,
                        status_callback=self._create_nested_status_callback(send_status_update, "conditional_formatting")
                    )
                
                if conditional_formatting_result and conditional_formatting_result.get("post_process", {}).get("success"):
                    chart_configurations = conditional_formatting_result.get("post_process", {}).get("chart_configurations", {})
                    send_status_update("conditional_formatting_completed", {
                        "total_chart_configs": len(chart_configurations),
                        "project_id": project_id
                    })
                else:
                    error_msg = conditional_formatting_result.get("post_process", {}).get("error") if conditional_formatting_result else "Conditional formatting failed"
                    send_status_update("conditional_formatting_failed", {
                        "error": error_msg,
                        "project_id": project_id
                    })
            
            # Step 2: Apply conditional formatting to dashboard queries
            enhanced_queries = self._apply_conditional_formatting_to_queries(
                dashboard_queries, 
                chart_configurations,
                send_status_update
            )
            
            # Step 3: Execute dashboard with enhanced queries
            if not self._services["dashboard_streaming"]:
                error_msg = "Dashboard streaming service is not available"
                logger.error(error_msg)
                send_status_update("dashboard_execution_failed", {
                    "error": error_msg,
                    "project_id": project_id
                })
                raise RuntimeError(error_msg)
            
            send_status_update("dashboard_execution_started", {
                "total_enhanced_queries": len(enhanced_queries),
                "project_id": project_id
            })
            
            dashboard_result = await self._services["dashboard_streaming"].run(
                queries=enhanced_queries,
                status_callback=self._create_nested_status_callback(status_callback, "dashboard"),
                configuration={
                    "concurrent_execution": True,
                    "max_concurrent_queries": 5,
                    "continue_on_error": True,
                    "stream_intermediate_results": True
                },
                project_id=project_id
            )
            
            # Step 4: Apply chart adjustments to results
            if chart_configurations and isinstance(chart_configurations, dict):
                send_status_update("chart_adjustments_started", {
                    "total_adjustments": len(chart_configurations),
                    "project_id": project_id
                })
                
                dashboard_result = await self._apply_chart_adjustments(
                    dashboard_result,
                    chart_configurations,
                    project_id,
                    send_status_update
                )
                
                send_status_update("chart_adjustments_completed", {
                    "project_id": project_id
                })
            
            # Step 5: Prepare final response
            final_result = {
                "success": dashboard_result.get("post_process", {}).get("success", True),
                "dashboard_data": dashboard_result.get("post_process", {}),
                "conditional_formatting": conditional_formatting_result.get("post_process", {}) if conditional_formatting_result else None,
                "chart_configurations": chart_configurations,
                "dashboard_config": dashboard_context,
                "metadata": {
                    "project_id": project_id,
                    "natural_language_query": natural_language_query,
                    "total_queries": len(dashboard_queries),
                    "total_enhanced_queries": len(enhanced_queries),
                    "conditional_formatting_applied": bool(chart_configurations),
                    "dashboard_template": dashboard_context.get("template"),
                    "workflow_id": dashboard_context.get("workflow_id"),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            send_status_update("processing_completed", {
                "success": final_result["success"],
                "project_id": project_id,
                "total_charts": len(dashboard_result.get("post_process", {}).get("results", {})) if dashboard_result and dashboard_result.get("post_process") else 0
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
        Execute dashboard without conditional formatting
        
        Args:
            dashboard_queries: List of SQL queries for dashboard charts
            project_id: Project identifier
            status_callback: Callback for streaming status updates
            
        Returns:
            Dashboard execution result
        """
        try:
            # Execute using dashboard streaming pipeline directly
            result = await self._services["dashboard_streaming"].run(
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
        Process only conditional formatting without executing dashboard
        
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
            result = await self._services["conditional_formatting"].run(
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
    
    def _apply_conditional_formatting_to_queries(
        self,
        dashboard_queries: List[Dict[str, Any]],
        chart_configurations: Dict[str, Dict[str, Any]],
        status_callback: Callable[[str, Dict[str, Any]], None]
    ) -> List[Dict[str, Any]]:
        """Apply conditional formatting configurations to dashboard queries"""
        enhanced_queries = []
        
        for i, query_data in enumerate(dashboard_queries):
            # Create a copy of the original query
            enhanced_query = query_data.copy()
            
            # Get chart configuration if available
            chart_id = query_data.get("chart_id", f"chart_{i}")
            chart_config = chart_configurations.get(chart_id, {})
            
            # Apply SQL expansion if configured
            if chart_config and "sql_expansion" in chart_config.get("actions", []):
                sql_expansion_config = chart_config.get("sql_expansion", {})
                enhanced_query = self._apply_sql_expansion(enhanced_query, sql_expansion_config)
                
                status_callback("sql_expansion_applied", {
                    "chart_id": chart_id,
                    "query_index": i,
                    "expansions": list(sql_expansion_config.keys())
                })
            
            # Add chart adjustment configuration for later processing
            if chart_config and "chart_adjustment" in chart_config.get("actions", []):
                enhanced_query["chart_adjustment_config"] = chart_config.get("chart_adjustment", {})
            
            # Add the enhanced query configuration metadata
            enhanced_query["conditional_formatting_applied"] = bool(chart_config)
            enhanced_query["chart_id"] = chart_id
            
            enhanced_queries.append(enhanced_query)
        
        return enhanced_queries
    
    def _apply_sql_expansion(
        self,
        query_data: Dict[str, Any],
        sql_expansion_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply SQL expansion configuration to a query"""
        original_sql = query_data.get("sql", "")
        
        if not original_sql:
            return query_data
        
        # Apply WHERE conditions
        where_conditions = sql_expansion_config.get("where_conditions", [])
        if where_conditions:
            # Check if SQL already has WHERE clause
            sql_lower = original_sql.lower()
            if "where" in sql_lower:
                # Add conditions with AND
                additional_conditions = " AND " + " AND ".join(where_conditions)
                # Find the position to insert (before ORDER BY, GROUP BY, etc.)
                insert_position = self._find_sql_insert_position(original_sql)
                modified_sql = original_sql[:insert_position] + additional_conditions + original_sql[insert_position:]
            else:
                # Add WHERE clause
                insert_position = self._find_sql_insert_position(original_sql)
                where_clause = " WHERE " + " AND ".join(where_conditions)
                modified_sql = original_sql[:insert_position] + where_clause + original_sql[insert_position:]
            
            query_data["sql"] = modified_sql
        
        # Apply time filters
        time_filters = sql_expansion_config.get("time_filters", {})
        if time_filters:
            query_data["sql"] = self._apply_time_filters_to_sql(query_data["sql"], time_filters)
        
        # Add metadata about applied expansions
        query_data["sql_expansions_applied"] = {
            "where_conditions_count": len(where_conditions),
            "time_filters_applied": bool(time_filters),
            "original_sql_length": len(original_sql),
            "modified_sql_length": len(query_data["sql"])
        }
        
        return query_data
    
    def _find_sql_insert_position(self, sql: str) -> int:
        """Find the position to insert WHERE conditions in SQL"""
        sql_lower = sql.lower()
        
        # Look for ORDER BY, GROUP BY, HAVING, LIMIT clauses
        keywords = ["order by", "group by", "having", "limit"]
        positions = []
        
        for keyword in keywords:
            pos = sql_lower.find(keyword)
            if pos != -1:
                positions.append(pos)
        
        if positions:
            return min(positions)
        else:
            return len(sql)
    
    def _apply_time_filters_to_sql(self, sql: str, time_filters: Dict[str, Any]) -> str:
        """Apply time filters to SQL query"""
        # This is a simplified implementation
        # In practice, you'd want more sophisticated date column detection and filtering
        
        start_date = time_filters.get("start_date")
        end_date = time_filters.get("end_date")
        period = time_filters.get("period")
        
        time_conditions = []
        
        if start_date and end_date:
            # Assume there's a date column (you'd want to detect this dynamically)
            date_column = self._detect_date_column(sql) or "date"
            time_conditions.append(f"{date_column} BETWEEN '{start_date}' AND '{end_date}'")
        elif period:
            date_column = self._detect_date_column(sql) or "date"
            if period == "last_30_days":
                time_conditions.append(f"{date_column} >= CURRENT_DATE - INTERVAL '30 days'")
            elif period == "current_year":
                time_conditions.append(f"EXTRACT(YEAR FROM {date_column}) = EXTRACT(YEAR FROM CURRENT_DATE)")
            elif period == "last_quarter":
                time_conditions.append(f"{date_column} >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')")
        
        if time_conditions:
            sql_lower = sql.lower()
            if "where" in sql_lower:
                insert_position = self._find_sql_insert_position(sql)
                additional_conditions = " AND " + " AND ".join(time_conditions)
                sql = sql[:insert_position] + additional_conditions + sql[insert_position:]
            else:
                insert_position = self._find_sql_insert_position(sql)
                where_clause = " WHERE " + " AND ".join(time_conditions)
                sql = sql[:insert_position] + where_clause + sql[insert_position:]
        
        return sql
    
    def _detect_date_column(self, sql: str) -> Optional[str]:
        """Detect date column in SQL query (simplified implementation)"""
        # This is a simplified implementation
        # In practice, you'd want to analyze the actual schema
        
        common_date_columns = ["date", "created_at", "updated_at", "timestamp", "time", "datetime"]
        sql_lower = sql.lower()
        
        for col in common_date_columns:
            if col in sql_lower:
                return col
        
        return None
    
    async def _apply_chart_adjustments(
        self,
        dashboard_result: Dict[str, Any],
        chart_configurations: Dict[str, Dict[str, Any]],
        project_id: str,
        status_callback: Callable[[str, Dict[str, Any]], None]
    ) -> Dict[str, Any]:
        """Apply chart adjustments to dashboard results"""
        try:
            results = dashboard_result.get("post_process", {}).get("results", {})
            chart_adjustment_pipeline = self.pipeline_container.get_pipeline("chart_adjustment")
            
            for chart_id, chart_config in chart_configurations.items():
                if "chart_adjustment" in chart_config.get("actions", []):
                    # Find corresponding result
                    chart_result_key = None
                    for key in results.keys():
                        if key.endswith(chart_id) or chart_id in key:
                            chart_result_key = key
                            break
                    
                    if chart_result_key and chart_result_key in results:
                        chart_result = results[chart_result_key]
                        
                        if chart_result.get("success", False):
                            # Get the chart data and schema
                            execution_result = chart_result.get("execution_result", {})
                            chart_data = execution_result.get("post_process", {})
                            
                            # Apply chart adjustment
                            adjustment_config = chart_config.get("chart_adjustment", {})
                            
                            try:
                                adjusted_result = await chart_adjustment_pipeline.run(
                                    query=chart_result.get("query_data", {}).get("query", ""),
                                    sql=chart_result.get("query_data", {}).get("sql", ""),
                                    adjustment_option=adjustment_config,
                                    chart_schema=chart_data.get("chart_schema", {}),
                                    data=chart_data.get("data", {}),
                                    language="English"
                                )
                                
                                # Update the result with adjusted chart
                                if adjusted_result.get("success", False):
                                    chart_data.update(adjusted_result.get("post_process", {}).get("results", {}))
                                    
                                    status_callback("chart_adjustment_applied", {
                                        "chart_id": chart_id,
                                        "adjustment_success": True
                                    })
                                else:
                                    status_callback("chart_adjustment_failed", {
                                        "chart_id": chart_id,
                                        "error": adjusted_result.get("error")
                                    })
                                    
                            except Exception as e:
                                logger.error(f"Error applying chart adjustment for {chart_id}: {e}")
                                status_callback("chart_adjustment_error", {
                                    "chart_id": chart_id,
                                    "error": str(e)
                                })
            
            return dashboard_result
            
        except Exception as e:
            logger.error(f"Error applying chart adjustments: {e}")
            return dashboard_result
    
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
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all dashboard services"""
        return {
            "dashboard_streaming": {
                "available": "dashboard_streaming" in self._services,
                "initialized": True
            },
            "conditional_formatting": {
                "available": "conditional_formatting" in self._services,
                "initialized": True
            },
            "enhanced_dashboard": {
                "available": "enhanced_dashboard" in self._services,
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


# Factory function for creating dashboard service
def create_dashboard_service() -> DashboardService:
    """
    Factory function to create a dashboard service
    
    Returns:
        DashboardService instance with all pipelines initialized
    """
    return DashboardService()


# Example usage
async def example_dashboard_service_usage():
    """Example of using the refactored dashboard service"""
    
    # Create dashboard service (automatically initializes PipelineContainer)
    dashboard_service = create_dashboard_service()
    
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
    
    # Process dashboard with conditional formatting
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
    print(f"Total charts: {result['metadata']['total_charts']}")
    print(f"Conditional formatting applied: {result['metadata']['conditional_formatting_applied']}")
    
    return result


if __name__ == "__main__":
    # Run example
    import asyncio
    asyncio.run(example_dashboard_service_usage())