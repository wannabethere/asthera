import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.pipelines.writers.conditional_formatting_generation_pipeline import ConditionalFormattingGenerationPipeline
from app.agents.pipelines.writers.simple_report_generation_pipeline import SimpleReportGenerationPipeline
from app.agents.nodes.writers.report_writing_agent import (
    ReportWritingAgent, 
    ReportWorkflowData, 
    ThreadComponentData, 
    WriterActorType, 
    BusinessGoal,
    ComponentType
)

logger = logging.getLogger("lexy-ai-service")


class ReportOrchestratorPipeline(AgentPipeline):
    """Orchestrator pipeline that coordinates between conditional formatting generation and report writing"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        conditional_formatting_pipeline: Optional[ConditionalFormattingGenerationPipeline] = None,
        simple_report_pipeline: Optional[SimpleReportGenerationPipeline] = None
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
            "enable_report_generation": True,
            "enable_validation": True,
            "enable_metrics": True,
            "max_report_iterations": 3,
            "quality_threshold": 0.8
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
        
        if not simple_report_pipeline:
            from app.agents.pipelines.writers.simple_report_generation_pipeline import create_simple_report_generation_pipeline
            self._simple_report_pipeline = create_simple_report_generation_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        else:
            self._simple_report_pipeline = simple_report_pipeline
        
        # Initialize report writing agent
        self._report_writing_agent = ReportWritingAgent(llm=llm)
        
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
        report_queries: List[Dict[str, Any]],
        natural_language_query: Optional[str],
        report_context: Dict[str, Any],
        project_id: str,
        thread_components: Optional[List[ThreadComponentData]] = None,
        writer_actor: Optional[WriterActorType] = None,
        business_goal: Optional[BusinessGoal] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Orchestrate the complete report processing workflow
        
        Args:
            report_queries: List of SQL queries for report data
            natural_language_query: Natural language query for conditional formatting (optional)
            report_context: Context about report structure and requirements
            project_id: Project identifier
            thread_components: Thread components for report generation (optional)
            writer_actor: Writer actor type for report generation (optional)
            business_goal: Business goal configuration (optional)
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback function for status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing complete report results with conditional formatting applied
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not report_queries or not isinstance(report_queries, list):
            raise ValueError("Report queries must be a non-empty list")
        
        if not report_context:
            raise ValueError("Report context is required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "report_orchestration_started",
            {
                "project_id": project_id,
                "total_queries": len(report_queries),
                "has_conditional_formatting": bool(natural_language_query),
                "has_report_generation": bool(thread_components and writer_actor and business_goal),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            enhanced_report_context = None
            
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
                    dashboard_context=report_context,  # Reuse dashboard context structure
                    project_id=project_id,
                    additional_context=additional_context,
                    time_filters=time_filters,
                    status_callback=self._create_nested_status_callback(status_callback, "conditional_formatting")
                )
                
                if conditional_formatting_result.get("post_process", {}).get("success"):
                    enhanced_report_context = conditional_formatting_result.get("post_process", {}).get("enhanced_dashboard")
                    
                    self._send_status_update(
                        status_callback,
                        "conditional_formatting_generation_completed",
                        {
                            "project_id": project_id,
                            "enhanced_context_generated": True
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
            
            # Step 2: Execute simple report generation
            if self._configuration["enable_report_generation"]:
                self._send_status_update(
                    status_callback,
                    "simple_report_generation_started",
                    {"project_id": project_id}
                )
                
                # If no enhanced context was generated, create a basic one
                if not enhanced_report_context:
                    enhanced_report_context = self._create_basic_enhanced_context(
                        report_context, project_id
                    )
                
                report_result = await self._simple_report_pipeline.run(
                    report_queries=report_queries,
                    enhanced_context=enhanced_report_context,
                    project_id=project_id,
                    status_callback=self._create_nested_status_callback(status_callback, "simple_report")
                )
                
                self._send_status_update(
                    status_callback,
                    "simple_report_generation_completed",
                    {"project_id": project_id}
                )
            else:
                # Fallback to basic execution if report generation is disabled
                report_result = await self._execute_basic_report(
                    report_queries, project_id, status_callback
                )
            
            # Step 3: Generate comprehensive report using report writing agent (if components provided)
            comprehensive_report = None
            
            # Debug logging for comprehensive report generation conditions
            logger.info(f"Comprehensive report generation conditions:")
            logger.info(f"  - thread_components: {bool(thread_components)} (count: {len(thread_components) if thread_components else 0})")
            logger.info(f"  - writer_actor: {bool(writer_actor)} (type: {type(writer_actor)})")
            logger.info(f"  - business_goal: {bool(business_goal)} (type: {type(business_goal)})")
            logger.info(f"  - enable_report_generation: {self._configuration.get('enable_report_generation', 'NOT_SET')}")
            
            if (thread_components and writer_actor and business_goal and 
                self._configuration["enable_report_generation"]):
                
                self._send_status_update(
                    status_callback,
                    "comprehensive_report_generation_started",
                    {"project_id": project_id}
                )
                
                # Create workflow data
                workflow_data = ReportWorkflowData(
                    id=f"workflow-{project_id}-{datetime.now().isoformat()}",
                    state="active",
                    current_step=1
                )
                
                comprehensive_report = self._report_writing_agent.generate_report(
                    workflow_data=workflow_data,
                    thread_components=thread_components,
                    writer_actor=writer_actor,
                    business_goal=business_goal
                )
                
                self._send_status_update(
                    status_callback,
                    "comprehensive_report_generation_completed",
                    {"project_id": project_id}
                )
            else:
                logger.info("Comprehensive report generation skipped due to missing requirements")
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_queries=len(report_queries),
                execution_time=total_execution_time,
                project_id=project_id,
                conditional_formatting_applied=bool(enhanced_report_context and enhanced_report_context.get("conditional_formatting_rules")),
                comprehensive_report_generated=bool(comprehensive_report)
            )
            
            # Send completion status
            self._send_status_update(
                status_callback,
                "report_orchestration_completed",
                {
                    "project_id": project_id,
                    "execution_time": total_execution_time,
                    "conditional_formatting_applied": bool(enhanced_report_context and enhanced_report_context.get("conditional_formatting_rules")),
                    "comprehensive_report_generated": bool(comprehensive_report)
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "success": True,
                    "report_results": report_result.get("post_process", {}),
                    "enhanced_context": enhanced_report_context,
                    "comprehensive_report": comprehensive_report,
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "conditional_formatting_applied": bool(enhanced_report_context and enhanced_report_context.get("conditional_formatting_rules")),
                        "comprehensive_report_generated": bool(comprehensive_report),
                        "report_generation_enabled": self._configuration["enable_report_generation"]
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
            logger.error(f"Error in report orchestration pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "report_orchestration_error",
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

    def _create_basic_enhanced_context(
        self,
        report_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Create a basic enhanced context when no conditional formatting is requested"""
        
        return {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "original_context": report_context,
            "conditional_formatting_rules": {},
            "execution_instructions": {},
            "basic_context": True
        }

    async def _execute_basic_report(
        self,
        report_queries: List[Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Execute basic report without enhanced features"""
        
        # This would integrate with your basic report execution pipeline
        # For now, return a basic structure
        return {
            "post_process": {
                "success": True,
                "results": {},
                "basic_execution": True
            },
            "metadata": {
                "pipeline_name": "basic_report",
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
        logger.info(f"Report Orchestrator Pipeline - {status}: {details}")

    def _update_metrics(
        self,
        total_queries: int,
        execution_time: float,
        project_id: str,
        conditional_formatting_applied: bool,
        comprehensive_report_generated: bool
    ) -> None:
        """Update internal metrics"""
        self._metrics.update({
            "last_execution": {
                "total_queries": total_queries,
                "execution_time": execution_time,
                "project_id": project_id,
                "conditional_formatting_applied": conditional_formatting_applied,
                "comprehensive_report_generated": comprehensive_report_generated,
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
            "simple_report_pipeline_metrics": self._simple_report_pipeline.get_metrics() if hasattr(self._simple_report_pipeline, 'get_metrics') else {},
            "timestamp": datetime.now().isoformat()
        }

    def enable_conditional_formatting(self, enabled: bool) -> None:
        """Enable or disable conditional formatting"""
        self._configuration["enable_conditional_formatting"] = enabled
        logger.info(f"Conditional formatting {'enabled' if enabled else 'disabled'}")

    def enable_report_generation(self, enabled: bool) -> None:
        """Enable or disable report generation"""
        self._configuration["enable_report_generation"] = enabled
        logger.info(f"Report generation {'enabled' if enabled else 'disabled'}")

    def set_quality_threshold(self, threshold: float) -> None:
        """Set quality threshold for report generation"""
        self._configuration["quality_threshold"] = max(0.0, min(1.0, threshold))
        logger.info(f"Quality threshold set to: {self._configuration['quality_threshold']}")


# Factory function for creating report orchestrator pipeline
def create_report_orchestrator_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    conditional_formatting_pipeline: Optional[ConditionalFormattingGenerationPipeline] = None,
    simple_report_pipeline: Optional[SimpleReportGenerationPipeline] = None,
    **kwargs
) -> ReportOrchestratorPipeline:
    """
    Factory function to create a report orchestrator pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        conditional_formatting_pipeline: Conditional formatting generation pipeline (optional)
        simple_report_pipeline: Simple report generation pipeline (optional)
        **kwargs: Additional configuration options
    
    Returns:
        ReportOrchestratorPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return ReportOrchestratorPipeline(
        name="report_orchestrator_pipeline",
        version="1.0.0",
        description="Orchestrator pipeline that coordinates between conditional formatting generation and report writing",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        conditional_formatting_pipeline=conditional_formatting_pipeline,
        simple_report_pipeline=simple_report_pipeline,
        **kwargs
    )
