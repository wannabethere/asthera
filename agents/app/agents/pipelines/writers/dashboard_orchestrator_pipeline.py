import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.pipelines.writers.conditional_formatting_pipeline import ConditionalFormattingPipeline
from app.agents.pipelines.writers.enhanced_dashboard_streaming_pipeline import EnhancedDashboardStreamingPipeline
from app.agents.pipelines.writers.dashboard_summary_pipeline import DashboardSummaryPipeline

logger = logging.getLogger("lexy-ai-service")


class DashboardOrchestratorPipeline(AgentPipeline):
    """Orchestrator pipeline that coordinates between conditional formatting generation and enhanced streaming"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        conditional_formatting_pipeline: Optional[ConditionalFormattingPipeline] = None,
        enhanced_streaming_pipeline: Optional[EnhancedDashboardStreamingPipeline] = None,
        dashboard_summary_pipeline: Optional[DashboardSummaryPipeline] = None
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            retrieval_helper=retrieval_helper,
            engine=engine
        )
        
        self._configuration = {
            "enable_conditional_formatting": True,
            "enable_streaming": True,
            "enable_validation": True,
            "enable_metrics": True,
            "enable_dashboard_summary": True
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize pipelines if not provided
        if not conditional_formatting_pipeline:
            from app.agents.pipelines.writers.conditional_formatting_pipeline import create_conditional_formatting_pipeline
            self._conditional_formatting_pipeline = create_conditional_formatting_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        else:
            self._conditional_formatting_pipeline = conditional_formatting_pipeline
        
        if not enhanced_streaming_pipeline:
            from app.agents.pipelines.writers.enhanced_dashboard_streaming_pipeline import create_enhanced_dashboard_streaming_pipeline
            self._enhanced_streaming_pipeline = create_enhanced_dashboard_streaming_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        else:
            self._enhanced_streaming_pipeline = enhanced_streaming_pipeline
        
        if not dashboard_summary_pipeline:
            from app.agents.pipelines.writers.dashboard_summary_pipeline import create_dashboard_summary_pipeline
            self._dashboard_summary_pipeline = create_dashboard_summary_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        else:
            self._dashboard_summary_pipeline = dashboard_summary_pipeline
        
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def get_configuration(self) -> Dict[str, Any]:
        return self._configuration.copy()

    def update_configuration(self, config: Dict[str, Any]) -> None:
        self._configuration.update(config)

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        self._metrics.clear()

    async def run(
        self,
        dashboard_queries: List[Dict[str, Any]],
        natural_language_query: Optional[str],
        dashboard_context: Dict[str, Any],
        project_id: str,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Orchestrate the complete dashboard processing workflow
        
        Args:
            dashboard_queries: List of SQL queries for dashboard charts
            natural_language_query: Natural language query for conditional formatting (optional)
            dashboard_context: Context about dashboard charts and columns
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing complete dashboard results with conditional formatting applied
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not dashboard_queries or not isinstance(dashboard_queries, list):
            raise ValueError("Dashboard queries must be a non-empty list")
        
        if not dashboard_context:
            raise ValueError("Dashboard context is required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "dashboard_orchestration_started",
            {
                "project_id": project_id,
                "total_queries": len(dashboard_queries),
                "has_conditional_formatting": bool(natural_language_query),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            enhanced_dashboard = None
            
            # Step 1: Generate conditional formatting if requested
            if (self._configuration["enable_conditional_formatting"] and 
                natural_language_query and 
                natural_language_query.strip()):
                
                self._send_status_update(
                    status_callback,
                    "conditional_formatting_generation_started",
                    {"project_id": project_id}
                )
                
                conditional_formatting_result = await self._conditional_formatting_pipeline.run(
                    natural_language_query=natural_language_query,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    additional_context=additional_context,
                    time_filters=time_filters,
                    status_callback=self._create_nested_status_callback(status_callback, "conditional_formatting")
                )
                
                # New pipeline returns result directly, not in post_process
                if conditional_formatting_result.get("success"):
                    # Create enhanced dashboard structure from new pipeline result
                    enhanced_dashboard = self._create_enhanced_dashboard_from_result(
                        conditional_formatting_result,
                        dashboard_context,
                        project_id
                    )
                    
                    self._send_status_update(
                        status_callback,
                        "conditional_formatting_generation_completed",
                        {
                            "project_id": project_id,
                            "enhanced_dashboard_generated": True
                        }
                    )
                else:
                    self._send_status_update(
                        status_callback,
                        "conditional_formatting_generation_failed",
                        {
                            "project_id": project_id,
                            "error": conditional_formatting_result.get("error", "Unknown error")
                        }
                    )
            
            # Step 2: Execute enhanced dashboard streaming
            if self._configuration["enable_streaming"]:
                self._send_status_update(
                    status_callback,
                    "enhanced_dashboard_streaming_started",
                    {"project_id": project_id}
                )
                
                # If no enhanced dashboard was generated, create a basic one
                if not enhanced_dashboard:
                    enhanced_dashboard = self._create_basic_enhanced_dashboard(
                        dashboard_context, project_id
                    )
                
                dashboard_result = await self._enhanced_streaming_pipeline.run(
                    dashboard_queries=dashboard_queries,
                    enhanced_dashboard=enhanced_dashboard,
                    project_id=project_id,
                    status_callback=self._create_nested_status_callback(status_callback, "enhanced_streaming")
                )
                
                self._send_status_update(
                    status_callback,
                    "enhanced_dashboard_streaming_completed",
                    {"project_id": project_id}
                )
            else:
                # Fallback to basic execution if streaming is disabled
                dashboard_result = await self._execute_basic_dashboard(
                    dashboard_queries, project_id, status_callback
                )
            
            # Step 3: Generate overall dashboard summary and insights
            dashboard_summary_result = None
            if self._configuration["enable_dashboard_summary"]:
                self._send_status_update(
                    status_callback,
                    "dashboard_summary_generation_started",
                    {"project_id": project_id}
                )
                
                # Extract components from dashboard result for summary generation
                dashboard_components = self._extract_components_for_summary(
                    dashboard_result, dashboard_queries, dashboard_context
                )
                
                dashboard_summary_result = await self._dashboard_summary_pipeline.run(
                    dashboard_components=dashboard_components,
                    dashboard_context=dashboard_context,
                    project_id=project_id,
                    additional_context=additional_context,
                    status_callback=self._create_nested_status_callback(status_callback, "dashboard_summary")
                )
                
                self._send_status_update(
                    status_callback,
                    "dashboard_summary_generation_completed",
                    {"project_id": project_id}
                )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_queries=len(dashboard_queries),
                execution_time=total_execution_time,
                project_id=project_id,
                conditional_formatting_applied=bool(enhanced_dashboard and enhanced_dashboard.get("conditional_formatting_rules"))
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "dashboard_orchestration_completed",
                {
                    "project_id": project_id,
                    "execution_time": total_execution_time,
                    "conditional_formatting_applied": bool(enhanced_dashboard and enhanced_dashboard.get("conditional_formatting_rules"))
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "dashboard_results": dashboard_result.get("post_process", {}),
                    "enhanced_dashboard": enhanced_dashboard,
                    "dashboard_summary": dashboard_summary_result.get("post_process", {}) if dashboard_summary_result else None,
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "conditional_formatting_applied": bool(enhanced_dashboard and enhanced_dashboard.get("conditional_formatting_rules")),
                        "streaming_enabled": self._configuration["enable_streaming"],
                        "dashboard_summary_enabled": self._configuration["enable_dashboard_summary"],
                        "dashboard_summary_generated": bool(dashboard_summary_result and dashboard_summary_result.get("post_process", {}).get("success"))
                    }
                },
                "metadata": {
                    "pipeline_name": self.name,
                    "pipeline_version": self.version,
                    "execution_timestamp": end_time.isoformat(),
                    "configuration_used": self._configuration.copy()
                }
            }
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error in dashboard orchestration pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "dashboard_orchestration_error",
                {
                    "error": str(e),
                    "project_id": project_id
                }
            )
            
            # Update metrics with error
            self._metrics.update({
                "last_error": str(e),
                "total_errors": self._metrics.get("total_errors", 0) + 1
            })
            
            raise

    def _create_enhanced_dashboard_from_result(
        self,
        conditional_formatting_result: Dict[str, Any],
        dashboard_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Create enhanced dashboard structure from conditional formatting pipeline result"""
        chart_configurations = conditional_formatting_result.get("chart_configurations", {})
        sql_expansions = conditional_formatting_result.get("sql_expansions", {})
        time_filters = conditional_formatting_result.get("time_filters")
        
        enhanced_dashboard = {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "original_context": dashboard_context,
            "conditional_formatting_rules": chart_configurations,
            "execution_instructions": {}
        }
        
        # Generate execution instructions for each chart
        for chart_id, config in chart_configurations.items():
            chart_instructions = {
                "chart_id": chart_id,
                "sql_expansions": [],
                "chart_adjustments": [],
                "conditional_formats": []
            }
            
            # Extract SQL expansion instructions
            if "sql_expansion" in config:
                sql_expansion = config["sql_expansion"]
                if "where_conditions" in sql_expansion:
                    chart_instructions["sql_expansions"].append({
                        "type": "where_conditions",
                        "conditions": sql_expansion["where_conditions"]
                    })
                
                if "time_filters" in sql_expansion:
                    chart_instructions["sql_expansions"].append({
                        "type": "time_filters",
                        "filters": sql_expansion["time_filters"]
                    })
                
                if "expanded_sql" in sql_expansion:
                    chart_instructions["sql_expansions"].append({
                        "type": "expanded_sql",
                        "sql": sql_expansion["expanded_sql"]
                    })
            
            # Extract chart adjustment instructions
            if "chart_adjustment" in config:
                chart_instructions["chart_adjustments"].append({
                    "type": "chart_adjustment",
                    "config": config["chart_adjustment"]
                })
            
            enhanced_dashboard["execution_instructions"][chart_id] = chart_instructions
        
        return enhanced_dashboard

    def _create_basic_enhanced_dashboard(
        self,
        dashboard_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Create a basic enhanced dashboard when no conditional formatting is requested"""
        
        return {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "original_context": dashboard_context,
            "conditional_formatting_rules": {},
            "execution_instructions": {},
            "basic_dashboard": True
        }

    async def _execute_basic_dashboard(
        self,
        dashboard_queries: List[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Execute basic dashboard without enhanced features"""
        
        # This would integrate with your basic dashboard execution pipeline
        # For now, return a basic structure
        return {
            "post_process": {
                "success": True,
                "results": {},
                "basic_execution": True
            },
            "metadata": {
                "pipeline_name": "basic_dashboard",
                "execution_timestamp": datetime.now().isoformat()
            }
        }

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

    def _send_status_update(
        self,
        status_callback: Optional[Callable],
        status: str,
        details: Dict[str, Any]
    ) -> None:
        """Send status update via callback if available"""
        if status_callback:
            try:
                status_callback(status, details)
            except Exception as e:
                logger.error(f"Error in status callback: {str(e)}")
        
        # Also log the status update
        logger.info(f"Dashboard Orchestrator Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        total_queries: int,
        execution_time: float,
        project_id: str,
        conditional_formatting_applied: bool
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "total_queries": total_queries,
                "execution_time": execution_time,
                "project_id": project_id,
                "conditional_formatting_applied": conditional_formatting_applied,
                "timestamp": datetime.now().isoformat()
            },
            "total_executions": self._metrics.get("total_executions", 0) + 1,
            "total_queries_processed": self._metrics.get("total_queries_processed", 0) + total_queries,
            "total_execution_time": self._metrics.get("total_execution_time", 0) + execution_time
        })
        
        # Calculate average execution time
        total_executions = self._metrics["total_executions"]
        if total_executions > 0:
            self._metrics["average_execution_time"] = self._metrics["total_execution_time"] / total_executions

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get detailed execution statistics"""
        return {
            "pipeline_metrics": self._metrics.copy(),
            "configuration": self._configuration.copy(),
            "conditional_formatting_pipeline_metrics": self._conditional_formatting_pipeline.get_metrics() if hasattr(self._conditional_formatting_pipeline, 'get_metrics') else {},
            "enhanced_streaming_pipeline_metrics": self._enhanced_streaming_pipeline.get_metrics() if hasattr(self._enhanced_streaming_pipeline, 'get_metrics') else {},
            "timestamp": datetime.now().isoformat()
        }

    def enable_conditional_formatting(self, enabled: bool) -> None:
        """Enable or disable conditional formatting"""
        self._configuration["enable_conditional_formatting"] = enabled
        logger.info(f"Conditional formatting {'enabled' if enabled else 'disabled'}")

    def enable_streaming(self, enabled: bool) -> None:
        """Enable or disable streaming"""
        self._configuration["enable_streaming"] = enabled
        logger.info(f"Streaming {'enabled' if enabled else 'disabled'}")

    def enable_dashboard_summary(self, enabled: bool) -> None:
        """Enable or disable dashboard summary generation"""
        self._configuration["enable_dashboard_summary"] = enabled
        logger.info(f"Dashboard summary {'enabled' if enabled else 'disabled'}")

    def _extract_components_for_summary(
        self,
        dashboard_result: Dict[str, Any],
        dashboard_queries: List[Dict[str, Any]],
        dashboard_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract components from dashboard result for summary generation"""
        components = []
        
        try:
            # Extract results from dashboard execution
            results = dashboard_result.get("post_process", {}).get("results", {})
            
            for i, query_data in enumerate(dashboard_queries):
                component = {
                    "id": query_data.get("component_id", f"component_{i}"),
                    "type": query_data.get("component_type", "question"),
                    "question": query_data.get("query", ""),
                    "executive_summary": query_data.get("executive_summary", ""),
                    "reasoning": query_data.get("reasoning", ""),
                    "data_count": 0,
                    "sequence": query_data.get("sequence_order", i + 1),
                    "chart_type": query_data.get("chart_config", {}).get("type", ""),
                    "sample_data": {"data": [], "columns": []},
                    "columns": [],
                    "insights": "",
                    "validation_success": False
                }
                
                # Find matching result data
                result_data = None
                for query_id, query_result in results.items():
                    # Skip if query_result is not a dictionary
                    if not isinstance(query_result, dict):
                        continue
                    if query_result.get("query_index") == i or query_result.get("component_id") == query_data.get("component_id"):
                        result_data = query_result
                        break
                
                # Update component with result data
                if result_data:
                    component["data_count"] = result_data.get("row_count", 0)
                    component["sample_data"] = {
                        "data": result_data.get("data", [])[:5],  # First 5 rows
                        "columns": result_data.get("columns", [])
                    }
                    component["columns"] = result_data.get("columns", [])
                    component["validation_success"] = result_data.get("success", False)
                    
                    # Add insights if available
                    if result_data.get("insights"):
                        component["insights"] = result_data.get("insights")
                
                components.append(component)
            
            return components
            
        except Exception as e:
            logger.error(f"Error extracting components for summary: {e}")
            return []


# Factory function for creating dashboard orchestrator pipeline
def create_dashboard_orchestrator_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    conditional_formatting_pipeline: Optional[ConditionalFormattingPipeline] = None,
    enhanced_streaming_pipeline: Optional[EnhancedDashboardStreamingPipeline] = None,
    dashboard_summary_pipeline: Optional[DashboardSummaryPipeline] = None,
    **kwargs
) -> DashboardOrchestratorPipeline:
    """
    Factory function to create a dashboard orchestrator pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        conditional_formatting_pipeline: Conditional formatting generation pipeline (optional)
        enhanced_streaming_pipeline: Enhanced dashboard streaming pipeline (optional)
        dashboard_summary_pipeline: Dashboard summary generation pipeline (optional)
        **kwargs: Additional configuration options
    
    Returns:
        DashboardOrchestratorPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return DashboardOrchestratorPipeline(
        name="dashboard_orchestrator_pipeline",
        version="1.0.0",
        description="Orchestrator pipeline that coordinates between conditional formatting generation and enhanced streaming",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        conditional_formatting_pipeline=conditional_formatting_pipeline,
        enhanced_streaming_pipeline=enhanced_streaming_pipeline,
        dashboard_summary_pipeline=dashboard_summary_pipeline,
        **kwargs
    )
