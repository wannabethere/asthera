import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.pipelines.writers.dashboard_streaming_pipeline import DashboardStreamingPipeline

logger = logging.getLogger("lexy-ai-service")


class EnhancedDashboardStreamingPipeline(AgentPipeline):
    """Enhanced dashboard streaming pipeline that applies conditional formatting rules"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        dashboard_streaming_pipeline: Optional[DashboardStreamingPipeline] = None
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
            "concurrent_execution": True,
            "max_concurrent_queries": 5,
            "timeout_per_query": 30,
            "include_execution_order": True,
            "stream_intermediate_results": True,
            "continue_on_error": True,
            "apply_sql_expansions": True,
            "apply_chart_adjustments": True,
            "apply_conditional_formats": True
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize dashboard streaming pipeline if not provided
        if dashboard_streaming_pipeline:
            self._dashboard_streaming_pipeline = dashboard_streaming_pipeline
        else:
            from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
            self._dashboard_streaming_pipeline = create_dashboard_streaming_pipeline(
                engine=engine,
                llm=llm,
                retrieval_helper=retrieval_helper
            )
        
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
        enhanced_dashboard: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute enhanced dashboard with conditional formatting rules applied
        
        Args:
            dashboard_queries: List of SQL queries for dashboard charts
            enhanced_dashboard: Enhanced dashboard JSON with conditional formatting rules
            project_id: Project identifier
            status_callback: Callback function for streaming status updates
            configuration: Pipeline configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing all query results with conditional formatting applied
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not dashboard_queries or not isinstance(dashboard_queries, list):
            raise ValueError("Dashboard queries must be a non-empty list")
        
        if not enhanced_dashboard:
            raise ValueError("Enhanced dashboard configuration is required")
        
        # Initialize tracking variables
        start_time = datetime.now()
        total_queries = len(dashboard_queries)
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "enhanced_dashboard_streaming_started",
            {
                "project_id": project_id,
                "total_queries": total_queries,
                "has_conditional_formatting": bool(enhanced_dashboard.get("conditional_formatting_rules")),
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            # Step 1: Apply conditional formatting rules to queries
            enhanced_queries = await self._apply_conditional_formatting_rules(
                dashboard_queries, 
                enhanced_dashboard,
                status_callback
            )
            
            # Step 2: Execute enhanced queries using dashboard streaming pipeline
            dashboard_result = await self._dashboard_streaming_pipeline.run(
                queries=enhanced_queries,
                status_callback=self._create_nested_status_callback(status_callback, "dashboard_execution"),
                configuration={
                    "concurrent_execution": self._configuration["concurrent_execution"],
                    "max_concurrent_queries": self._configuration["max_concurrent_queries"],
                    "continue_on_error": self._configuration["continue_on_error"],
                    "stream_intermediate_results": self._configuration["stream_intermediate_results"]
                },
                project_id=project_id
            )
            
            # Step 3: Apply chart adjustments to results
            if self._configuration["apply_chart_adjustments"]:
                dashboard_result = await self._apply_chart_adjustments(
                    dashboard_result,
                    enhanced_dashboard,
                    project_id,
                    status_callback
                )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Update internal metrics
            self._update_metrics(
                total_queries=total_queries,
                execution_time=total_execution_time,
                project_id=project_id,
                conditional_formatting_applied=bool(enhanced_dashboard.get("conditional_formatting_rules"))
            )
            
            # Send final status update
            self._send_status_update(
                status_callback,
                "enhanced_dashboard_streaming_completed",
                {
                    "project_id": project_id,
                    "total_queries": total_queries,
                    "execution_time": total_execution_time,
                    "conditional_formatting_applied": bool(enhanced_dashboard.get("conditional_formatting_rules"))
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "results": dashboard_result.get("post_process", {}),
                    "enhanced_dashboard": enhanced_dashboard,
                    "execution_metadata": {
                        "pipeline_name": self.name,
                        "pipeline_version": self.version,
                        "total_execution_time_seconds": total_execution_time,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "project_id": project_id,
                        "conditional_formatting_applied": bool(enhanced_dashboard.get("conditional_formatting_rules")),
                        "chart_adjustments_applied": self._configuration["apply_chart_adjustments"]
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
            logger.error(f"Error in enhanced dashboard streaming pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "enhanced_dashboard_streaming_error",
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

    async def _apply_conditional_formatting_rules(
        self,
        dashboard_queries: List[Dict[str, Any]],
        enhanced_dashboard: Dict[str, Any],
        status_callback: Optional[Callable]
    ) -> List[Dict[str, Any]]:
        """Apply conditional formatting rules to dashboard queries"""
        
        enhanced_queries = []
        conditional_formatting_rules = enhanced_dashboard.get("conditional_formatting_rules", {})
        execution_instructions = enhanced_dashboard.get("execution_instructions", {})
        
        for i, query_data in enumerate(dashboard_queries):
            # Create a copy of the original query
            enhanced_query = query_data.copy()
            chart_id = query_data.get("chart_id", f"chart_{i}")
            
            # Get execution instructions for this chart
            chart_instructions = execution_instructions.get(chart_id, {})
            
            # Apply SQL expansions if configured
            if self._configuration["apply_sql_expansions"] and chart_instructions.get("sql_expansions"):
                enhanced_query = await self._apply_sql_expansions(
                    enhanced_query, 
                    chart_instructions["sql_expansions"],
                    status_callback
                )
            
            # Add chart adjustment configuration for later processing
            if self._configuration["apply_chart_adjustments"] and chart_instructions.get("chart_adjustments"):
                enhanced_query["chart_adjustment_config"] = chart_instructions["chart_adjustments"]
            
            # Add conditional format configuration
            if self._configuration["apply_conditional_formats"] and chart_instructions.get("conditional_formats"):
                enhanced_query["conditional_formats"] = chart_instructions["conditional_formats"]
            
            # Add metadata about applied enhancements
            enhanced_query["conditional_formatting_applied"] = bool(chart_instructions)
            enhanced_query["chart_id"] = chart_id
            enhanced_query["enhancement_metadata"] = {
                "sql_expansions_applied": len(chart_instructions.get("sql_expansions", [])),
                "chart_adjustments_applied": len(chart_instructions.get("chart_adjustments", [])),
                "conditional_formats_applied": len(chart_instructions.get("conditional_formats", []))
            }
            
            enhanced_queries.append(enhanced_query)
            
            # Send status update
            self._send_status_update(
                status_callback,
                "query_enhancement_applied",
                {
                    "chart_id": chart_id,
                    "query_index": i,
                    "enhancements_applied": enhanced_query["enhancement_metadata"]
                }
            )
        
        return enhanced_queries

    async def _apply_sql_expansions(
        self,
        query_data: Dict[str, Any],
        sql_expansions: List[Dict[str, Any]],
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Apply SQL expansions to a query"""
        
        original_sql = query_data.get("sql", "")
        if not original_sql:
            return query_data
        
        modified_sql = original_sql
        
        for expansion in sql_expansions:
            expansion_type = expansion.get("type")
            
            if expansion_type == "where_conditions":
                conditions = expansion.get("conditions", [])
                if conditions:
                    modified_sql = self._apply_where_conditions(modified_sql, conditions)
            
            elif expansion_type == "time_filters":
                filters = expansion.get("filters", {})
                if filters:
                    modified_sql = self._apply_time_filters(modified_sql, filters)
        
        # Update query with modified SQL
        query_data["sql"] = modified_sql
        query_data["sql_expansions_applied"] = {
            "original_sql_length": len(original_sql),
            "modified_sql_length": len(modified_sql),
            "expansions_count": len(sql_expansions)
        }
        
        return query_data

    def _apply_where_conditions(self, sql: str, conditions: List[str]) -> str:
        """Apply WHERE conditions to SQL query"""
        if not conditions:
            return sql
        
        sql_lower = sql.lower()
        
        # Check if SQL already has WHERE clause
        if "where" in sql_lower:
            # Add conditions with AND
            additional_conditions = " AND " + " AND ".join(conditions)
            # Find the position to insert (before ORDER BY, GROUP BY, etc.)
            insert_position = self._find_sql_insert_position(sql)
            modified_sql = sql[:insert_position] + additional_conditions + sql[insert_position:]
        else:
            # Add WHERE clause
            insert_position = self._find_sql_insert_position(sql)
            where_clause = " WHERE " + " AND ".join(conditions)
            modified_sql = sql[:insert_position] + where_clause + sql[insert_position:]
        
        return modified_sql

    def _apply_time_filters(self, sql: str, time_filters: Dict[str, Any]) -> str:
        """Apply time filters to SQL query"""
        start_date = time_filters.get("start_date")
        end_date = time_filters.get("end_date")
        period = time_filters.get("period")
        
        time_conditions = []
        
        if start_date and end_date:
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
            return self._apply_where_conditions(sql, time_conditions)
        
        return sql

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

    def _detect_date_column(self, sql: str) -> Optional[str]:
        """Detect date column in SQL query"""
        common_date_columns = ["date", "created_at", "updated_at", "timestamp", "time", "datetime"]
        sql_lower = sql.lower()
        
        for col in common_date_columns:
            if col in sql_lower:
                return col
        
        return None

    async def _apply_chart_adjustments(
        self,
        dashboard_result: Dict[str, Any],
        enhanced_dashboard: Dict[str, Any],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Apply chart adjustments to dashboard results"""
        
        try:
            results = dashboard_result.get("post_process", {}).get("results", {})
            execution_instructions = enhanced_dashboard.get("execution_instructions", {})
            
            for chart_id, chart_instructions in execution_instructions.items():
                chart_adjustments = chart_instructions.get("chart_adjustments", [])
                
                if not chart_adjustments:
                    continue
                
                # Find corresponding result
                chart_result_key = None
                for key in results.keys():
                    if key.endswith(chart_id) or chart_id in key:
                        chart_result_key = key
                        break
                
                if chart_result_key and chart_result_key in results:
                    chart_result = results[chart_result_key]
                    
                    if chart_result.get("success", False):
                        # Apply chart adjustments
                        for adjustment in chart_adjustments:
                            if adjustment["type"] == "chart_adjustment":
                                chart_result = await self._apply_single_chart_adjustment(
                                    chart_result, 
                                    adjustment["config"],
                                    chart_id,
                                    status_callback
                                )
                        
                        # Update the result
                        results[chart_result_key] = chart_result
            
            return dashboard_result
            
        except Exception as e:
            logger.error(f"Error applying chart adjustments: {e}")
            return dashboard_result

    async def _apply_single_chart_adjustment(
        self,
        chart_result: Dict[str, Any],
        adjustment_config: Dict[str, Any],
        chart_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Apply a single chart adjustment"""
        
        try:
            # Get the chart data
            execution_result = chart_result.get("execution_result", {})
            chart_data = execution_result.get("post_process", {})
            
            # Apply the adjustment (this would integrate with your chart adjustment pipeline)
            # For now, we'll just add metadata about the adjustment
            chart_result["chart_adjustments_applied"] = chart_result.get("chart_adjustments_applied", [])
            chart_result["chart_adjustments_applied"].append({
                "adjustment_type": adjustment_config.get("type", "unknown"),
                "config": adjustment_config,
                "applied_at": datetime.now().isoformat()
            })
            
            # Send status update
            self._send_status_update(
                status_callback,
                "chart_adjustment_applied",
                {
                    "chart_id": chart_id,
                    "adjustment_type": adjustment_config.get("type", "unknown")
                }
            )
            
            return chart_result
            
        except Exception as e:
            logger.error(f"Error applying chart adjustment for {chart_id}: {e}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "chart_adjustment_error",
                {
                    "chart_id": chart_id,
                    "error": str(e)
                }
            )
            
            return chart_result

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
        logger.info(f"Enhanced Dashboard Streaming Pipeline - {status}: {details}")

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
            "dashboard_streaming_pipeline_metrics": self._dashboard_streaming_pipeline.get_metrics() if hasattr(self._dashboard_streaming_pipeline, 'get_metrics') else {},
            "timestamp": datetime.now().isoformat()
        }

    def set_conditional_formatting_options(
        self, 
        apply_sql_expansions: bool = True,
        apply_chart_adjustments: bool = True,
        apply_conditional_formats: bool = True
    ) -> None:
        """Configure conditional formatting application options"""
        self._configuration["apply_sql_expansions"] = apply_sql_expansions
        self._configuration["apply_chart_adjustments"] = apply_chart_adjustments
        self._configuration["apply_conditional_formats"] = apply_conditional_formats
        logger.info(f"Conditional formatting options updated - SQL: {apply_sql_expansions}, Chart: {apply_chart_adjustments}, Formats: {apply_conditional_formats}")


# Factory function for creating enhanced dashboard streaming pipeline
def create_enhanced_dashboard_streaming_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    dashboard_streaming_pipeline: Optional[DashboardStreamingPipeline] = None,
    **kwargs
) -> EnhancedDashboardStreamingPipeline:
    """
    Factory function to create an enhanced dashboard streaming pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        dashboard_streaming_pipeline: Existing dashboard streaming pipeline (optional, will create if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        EnhancedDashboardStreamingPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return EnhancedDashboardStreamingPipeline(
        name="enhanced_dashboard_streaming_pipeline",
        version="1.0.0",
        description="Enhanced dashboard streaming pipeline that applies conditional formatting rules",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        dashboard_streaming_pipeline=dashboard_streaming_pipeline,
        **kwargs
    )
