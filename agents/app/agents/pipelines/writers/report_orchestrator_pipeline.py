import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.pipelines.writers.conditional_formatting_pipeline import ConditionalFormattingPipeline
from app.agents.pipelines.writers.simple_report_generation_pipeline import SimpleReportGenerationPipeline
from app.agents.pipelines.writers.dashboard_summary_pipeline import DashboardSummaryPipeline
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
        conditional_formatting_pipeline: Optional[ConditionalFormattingPipeline] = None,
        simple_report_pipeline: Optional[SimpleReportGenerationPipeline] = None,
        report_summary_pipeline: Optional[DashboardSummaryPipeline] = None
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
            "enable_report_summary": True,
            "enable_validation": True,
            "enable_metrics": True,
            "max_report_iterations": 3,
            "quality_threshold": 0.8
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
        
        if not simple_report_pipeline:
            from app.agents.pipelines.writers.simple_report_generation_pipeline import create_simple_report_generation_pipeline
            self._simple_report_pipeline = create_simple_report_generation_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        else:
            self._simple_report_pipeline = simple_report_pipeline
        
        if not report_summary_pipeline:
            from app.agents.pipelines.writers.dashboard_summary_pipeline import create_dashboard_summary_pipeline
            self._report_summary_pipeline = create_dashboard_summary_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        else:
            self._report_summary_pipeline = report_summary_pipeline
        
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
            # Skip if natural_language_query is None, empty, or just a placeholder
            has_valid_conditional_formatting_query = (
                natural_language_query and 
                natural_language_query.strip() and 
                natural_language_query.strip().lower() not in ["string", "none", "null", ""]
            )
            
            if (self._configuration["enable_conditional_formatting"] and 
                has_valid_conditional_formatting_query):
                
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
                
                # New pipeline returns result directly, not in post_process
                if conditional_formatting_result.get("success"):
                    # Create enhanced dashboard structure from new pipeline result
                    enhanced_report_context = self._create_enhanced_dashboard_from_result(
                        conditional_formatting_result,
                        report_context,
                        project_id
                    )
                    
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
                            "error": conditional_formatting_result.get("error", "Unknown error")
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
                
                # Add original report queries to enhanced context for fallback access
                enhanced_report_context["original_context"] = {
                    **enhanced_report_context.get("original_context", {}),
                    "queries": report_queries
                }
                
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
            
            # Step 2.5: Generate report summary and insights (similar to dashboard)
            report_summary_result = None
            if self._configuration["enable_report_summary"] and report_result.get("post_process", {}).get("success"):
                self._send_status_update(
                    status_callback,
                    "report_summary_generation_started",
                    {"project_id": project_id}
                )
                
                # Extract components from report result for summary generation
                report_components = self._extract_components_for_summary(
                    report_result, report_queries, report_context
                )
                
                if report_components and self._report_summary_pipeline:
                    report_summary_result = await self._report_summary_pipeline.run(
                        dashboard_components=report_components,  # Reuse dashboard summary pipeline
                        dashboard_context=report_context,  # Use report context as dashboard context
                        project_id=project_id,
                        additional_context=additional_context,
                        status_callback=self._create_nested_status_callback(status_callback, "report_summary")
                    )
                    
                    self._send_status_update(
                        status_callback,
                        "report_summary_generation_completed",
                        {"project_id": project_id}
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
                    "report_summary": report_summary_result,
                    "orchestration_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "conditional_formatting_applied": bool(enhanced_report_context and enhanced_report_context.get("conditional_formatting_rules")),
                        "comprehensive_report_generated": bool(comprehensive_report),
                        "report_summary_generated": bool(report_summary_result),
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

    def _create_enhanced_dashboard_from_result(
        self,
        conditional_formatting_result: Dict[str, Any],
        report_context: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Create enhanced dashboard structure from new conditional formatting pipeline result"""
        chart_configurations = conditional_formatting_result.get("chart_configurations", {})
        sql_expansions = conditional_formatting_result.get("sql_expansions", {})
        time_filters = conditional_formatting_result.get("time_filters")
        
        enhanced_dashboard = {
            "project_id": project_id,
            "generated_at": datetime.now().isoformat(),
            "original_context": report_context,
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

    def _extract_components_for_summary(
        self,
        report_result: Dict[str, Any],
        report_queries: List[Dict[str, Any]],
        report_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract components from report result for summary generation, including fallback data"""
        components = []
        
        try:
            # Extract query results from report result
            query_results = report_result.get("post_process", {}).get("query_results", {})
            
            for i, query_info in enumerate(report_queries):
                query_id = query_info.get("id", f"query_{i}")
                query_result = query_results.get(query_id, {})
                
                # Check if we have fallback data or successful SQL execution
                has_data = query_result.get("success", False) and query_result.get("data")
                is_fallback = query_result.get("fallback_used", False)
                data_source = query_result.get("data_source", "unknown")
                
                # Create component data for summary generation
                component = {
                    "id": query_id,
                    "type": "chart",  # Default type for summary generation
                    "question": query_info.get("name", f"Query {i+1}"),
                    "sql_query": query_info.get("sql", ""),
                    "data": query_result.get("data", []),
                    "columns": query_result.get("columns", []),
                    "row_count": query_result.get("row_count", 0),
                    "success": query_result.get("success", False),
                    "execution_time": query_result.get("execution_time", 0),
                    "error": query_result.get("error"),
                    "chart_schema": query_result.get("chart_schema", {}),
                    "chart_type": query_result.get("chart_type", ""),
                    "reasoning": query_result.get("reasoning", ""),
                    "data_source": data_source,
                    "fallback_used": is_fallback,
                    "metadata": {
                        "query_index": i,
                        "component_type": "sql_summary",
                        "data_source": data_source,
                        "fallback_used": is_fallback,
                        "has_data": has_data
                    }
                }
                
                # If we have data (either from SQL or fallback), add it to components
                if has_data:
                    components.append(component)
                    logger.info(f"Added component {query_id} with {len(query_result.get('data', []))} rows from {data_source}")
                else:
                    logger.warning(f"Skipping component {query_id} - no data available")
            
            logger.info(f"Extracted {len(components)} components for report summary generation")
            return components
            
        except Exception as e:
            logger.error(f"Error extracting components for summary: {e}")
            return []


# Factory function for creating report orchestrator pipeline
def create_report_orchestrator_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    conditional_formatting_pipeline: Optional[ConditionalFormattingPipeline] = None,
    simple_report_pipeline: Optional[SimpleReportGenerationPipeline] = None,
    report_summary_pipeline: Optional[DashboardSummaryPipeline] = None,
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
        report_summary_pipeline=report_summary_pipeline,
        **kwargs
    )
