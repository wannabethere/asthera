import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.pipelines.writers.conditional_formatting_generation_pipeline import ConditionalFormattingGenerationPipeline
from app.agents.pipelines.writers.enhanced_dashboard_streaming_pipeline import EnhancedDashboardStreamingPipeline

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
        conditional_formatting_pipeline: Optional[ConditionalFormattingGenerationPipeline] = None,
        enhanced_streaming_pipeline: Optional[EnhancedDashboardStreamingPipeline] = None
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
            "enable_metrics": True
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize pipelines if not provided
        if not conditional_formatting_pipeline:
            from app.agents.pipelines.writers.conditional_formatting_generation_pipeline import create_conditional_formatting_generation_pipeline
            self._conditional_formatting_pipeline = create_conditional_formatting_generation_pipeline(
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
                
                if conditional_formatting_result.get("post_process", {}).get("success"):
                    enhanced_dashboard = conditional_formatting_result.get("post_process", {}).get("enhanced_dashboard")
                    
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
                            "error": conditional_formatting_result.get("post_process", {}).get("error")
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
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "conditional_formatting_applied": bool(enhanced_dashboard and enhanced_dashboard.get("conditional_formatting_rules")),
                        "streaming_enabled": self._configuration["enable_streaming"]
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


# Factory function for creating dashboard orchestrator pipeline
def create_dashboard_orchestrator_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    conditional_formatting_pipeline: Optional[ConditionalFormattingGenerationPipeline] = None,
    enhanced_streaming_pipeline: Optional[EnhancedDashboardStreamingPipeline] = None,
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
        **kwargs
    )
