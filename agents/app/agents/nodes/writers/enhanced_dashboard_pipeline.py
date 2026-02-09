import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.core.engine_provider import EngineProvider

# Import our dashboard components
from app.agents.nodes.writers.dashboard_models import (
    FilterOperator, FilterType, ActionType,
    ControlFilter, ConditionalFormat, DashboardConfiguration
)

logger = logging.getLogger("lexy-ai-service")


class EnhancedDashboardPipeline(AgentPipeline):
    """Enhanced dashboard pipeline with streaming and conditional formatting capabilities"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        conditional_formatting_service: Optional[Any] = None,
        sql_execution_pipeline: Optional[Any] = None
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            retrieval_helper=retrieval_helper,
            engine=engine
        )
        
        # Pipeline configuration
        self._configuration = {
            "concurrent_execution": True,
            "max_concurrent_queries": 5,
            "timeout_per_query": 30,
            "include_execution_order": True,
            "stream_intermediate_results": True,
            "continue_on_error": True,
            "aggregate_results": True,
            "enable_conditional_formatting": True,
            "enable_chart_adjustments": True,
            "max_retries": 3,
            "retry_delay": 1.0
        }
        
        self._metrics = {}
        self._engine = engine
        
        # Initialize conditional formatting service (simple interface, not full pipeline)
        # 
        # IMPORTANT: Conditional formatting flows are kept separate from dashboard flows
        # to allow independent enhancement and evolution.
        # 
        # To use the full ConditionalFormattingPipeline with SQL expansion:
        #   from app.agents.pipelines.writers.conditional_formatting_pipeline import (
        #       create_conditional_formatting_pipeline, ConditionalFormattingPipelineAdapter
        #   )
        #   pipeline = create_conditional_formatting_pipeline(engine, llm, retrieval_helper)
        #   conditional_formatting_service = ConditionalFormattingPipelineAdapter(pipeline)
        #   Then pass it as conditional_formatting_service parameter
        #
        if conditional_formatting_service:
            self._conditional_formatting_service = conditional_formatting_service
        else:
            # Create a simple placeholder service that can be replaced with full pipeline if needed
            self._conditional_formatting_service = self._create_simple_conditional_formatting_service()
        
        # Initialize SQL execution pipeline
        if sql_execution_pipeline:
            self._sql_execution_pipeline = sql_execution_pipeline
        else:
            try:
                pipeline_container = PipelineContainer.get_instance()
                self._sql_execution_pipeline = pipeline_container.get_pipeline("data_summarization")
            except Exception as e:
                logger.warning(f"Failed to get data_summarization pipeline from container: {e}")
                # Fallback to direct instantiation
                from app.agents.pipelines.sql_execution import DataSummarizationPipeline
                self._sql_execution_pipeline = DataSummarizationPipeline(
                    name="sql_execution_internal",
                    version="1.0.0",
                    description="Internal SQL execution for enhanced dashboard",
                    llm=llm,
                    retrieval_helper=retrieval_helper,
                    engine=engine,
                )
        
        self._initialized = True

    def _create_simple_conditional_formatting_service(self):
        """Create a simple placeholder conditional formatting service"""
        class SimpleConditionalFormattingService:
            async def process_conditional_formatting_request(
                self,
                query: str,
                dashboard_context: Dict[str, Any],
                project_id: str = "default",
                additional_context: Optional[Dict[str, Any]] = None,
                time_filters: Optional[Dict[str, Any]] = None
            ) -> Dict[str, Any]:
                """Simple placeholder for conditional formatting processing"""
                logger.info(f"Processing conditional formatting request: {query}")
                
                # Return a basic configuration structure
                # Note: For full conditional formatting with SQL expansion,
                # use ConditionalFormattingPipeline separately
                return {
                    "success": True,
                    "chart_configurations": {},
                    "message": "Conditional formatting processing - use ConditionalFormattingPipeline for full processing"
                }
            
            def get_metrics(self) -> Dict[str, Any]:
                """Return empty metrics"""
                return {}
        
        return SimpleConditionalFormattingService()

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
        queries: List[Dict[str, Any]],
        natural_language_query: Optional[str] = None,
        dashboard_context: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
        additional_context: Optional[Dict[str, Any]] = None,
        time_filters: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute enhanced dashboard pipeline with streaming and conditional formatting
        
        Args:
            queries: List of query objects for dashboard charts
            natural_language_query: Natural language query for conditional formatting
            dashboard_context: Context about dashboard charts and columns
            project_id: Project identifier
            additional_context: Additional context for formatting
            time_filters: Time-based filters
            status_callback: Callback for streaming status updates
            configuration: Configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Complete dashboard result with conditional formatting and streaming
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
        
        # Update configuration if provided
        if configuration:
            self.update_configuration(configuration)
        
        # Validate input
        if not queries or not isinstance(queries, list):
            raise ValueError("Queries must be a non-empty list")
        
        # Initialize tracking variables
        start_time = datetime.now()
        total_queries = len(queries)
        completed_queries = 0
        failed_queries = 0
        results = {}
        execution_metadata = {
            "total_queries": total_queries,
            "start_time": start_time.isoformat(),
            "query_execution_order": [],
            "execution_summary": {},
            "errors": [],
            "conditional_formatting_applied": False,
            "chart_adjustments_applied": False
        }
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "enhanced_dashboard_started",
            {
                "total_queries": total_queries,
                "concurrent_execution": self._configuration["concurrent_execution"],
                "max_concurrent": self._configuration["max_concurrent_queries"],
                "conditional_formatting_enabled": self._configuration["enable_conditional_formatting"],
                "natural_language_query": bool(natural_language_query)
            }
        )
        
        try:
            # Step 1: Process conditional formatting if enabled and query provided
            chart_configurations = {}
            conditional_formatting_result = None
            
            if (self._configuration["enable_conditional_formatting"] and 
                natural_language_query and 
                natural_language_query.strip() and
                dashboard_context):
                
                self._send_status_update(
                    status_callback,
                    "conditional_formatting_started",
                    {"query": natural_language_query, "project_id": project_id}
                )
                
                try:
                    # Use the conditional formatting service interface
                    # This keeps the flows separate - ConditionalFormattingPipeline can be used independently
                    conditional_formatting_result = await self._conditional_formatting_service.process_conditional_formatting_request(
                        query=natural_language_query,
                        dashboard_context=dashboard_context,
                        project_id=project_id,
                        additional_context=additional_context,
                        time_filters=time_filters
                    )
                    
                    if conditional_formatting_result.get("success"):
                        chart_configurations = conditional_formatting_result.get("chart_configurations", {})
                        execution_metadata["conditional_formatting_applied"] = True
                        
                        self._send_status_update(
                            status_callback,
                            "conditional_formatting_completed",
                            {
                                "total_chart_configs": len(chart_configurations),
                                "project_id": project_id
                            }
                        )
                    else:
                        self._send_status_update(
                            status_callback,
                            "conditional_formatting_failed",
                            {
                                "error": conditional_formatting_result.get("error"),
                                "project_id": project_id
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Error in conditional formatting: {e}")
                    self._send_status_update(
                        status_callback,
                        "conditional_formatting_error",
                        {"error": str(e), "project_id": project_id}
                    )
            
            # Step 2: Apply conditional formatting to queries
            enhanced_queries = self._apply_conditional_formatting_to_queries(
                queries, chart_configurations, status_callback
            )
            
            # Step 3: Execute queries with streaming
            if self._configuration["concurrent_execution"]:
                results, execution_metadata = await self._execute_queries_concurrent(
                    enhanced_queries, status_callback, execution_metadata, **kwargs
                )
            else:
                results, execution_metadata = await self._execute_queries_sequential(
                    enhanced_queries, status_callback, execution_metadata, **kwargs
                )
            
            # Step 4: Apply chart adjustments if enabled
            if (self._configuration["enable_chart_adjustments"] and 
                chart_configurations and
                self._conditional_formatting_service):
                
                self._send_status_update(
                    status_callback,
                    "chart_adjustments_started",
                    {"total_adjustments": len(chart_configurations)}
                )
                
                try:
                    results = await self._apply_chart_adjustments(
                        results, chart_configurations, project_id, status_callback
                    )
                    execution_metadata["chart_adjustments_applied"] = True
                    
                    self._send_status_update(
                        status_callback,
                        "chart_adjustments_completed",
                        {"project_id": project_id}
                    )
                    
                except Exception as e:
                    logger.error(f"Error applying chart adjustments: {e}")
                    self._send_status_update(
                        status_callback,
                        "chart_adjustments_error",
                        {"error": str(e), "project_id": project_id}
                    )
            
            # Calculate final metrics
            end_time = datetime.now()
            total_execution_time = (end_time - start_time).total_seconds()
            
            completed_queries = len([r for r in results.values() if r.get("success", False)])
            failed_queries = total_queries - completed_queries
            
            execution_metadata.update({
                "end_time": end_time.isoformat(),
                "total_execution_time_seconds": total_execution_time,
                "completed_queries": completed_queries,
                "failed_queries": failed_queries,
                "success_rate": completed_queries / total_queries if total_queries > 0 else 0
            })
            
            # Update internal metrics
            self._metrics.update({
                "last_execution": {
                    "total_queries": total_queries,
                    "completed_queries": completed_queries,
                    "failed_queries": failed_queries,
                    "execution_time": total_execution_time,
                    "success_rate": execution_metadata["success_rate"],
                    "conditional_formatting_applied": execution_metadata["conditional_formatting_applied"],
                    "chart_adjustments_applied": execution_metadata["chart_adjustments_applied"]
                },
                "total_executions": self._metrics.get("total_executions", 0) + 1,
                "total_queries_processed": self._metrics.get("total_queries_processed", 0) + total_queries
            })
            
            # Send final status update
            self._send_status_update(
                status_callback,
                "enhanced_dashboard_completed",
                {
                    "total_queries": total_queries,
                    "completed_queries": completed_queries,
                    "failed_queries": failed_queries,
                    "execution_time": total_execution_time,
                    "success_rate": execution_metadata["success_rate"],
                    "conditional_formatting_applied": execution_metadata["conditional_formatting_applied"],
                    "chart_adjustments_applied": execution_metadata["chart_adjustments_applied"]
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "results": results,
                    "execution_metadata": execution_metadata,
                    "conditional_formatting": conditional_formatting_result,
                    "chart_configurations": chart_configurations,
                    "success": True
                },
                "metadata": {
                    "pipeline_name": self.name,
                    "pipeline_version": self.version,
                    "execution_timestamp": end_time.isoformat(),
                    "configuration_used": self._configuration.copy(),
                    "enhanced_features": {
                        "conditional_formatting": execution_metadata["conditional_formatting_applied"],
                        "chart_adjustments": execution_metadata["chart_adjustments_applied"],
                        "streaming": self._configuration["stream_intermediate_results"]
                    }
                }
            }
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error in enhanced dashboard pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "enhanced_dashboard_error",
                {
                    "error": str(e),
                    "completed_queries": completed_queries,
                    "total_queries": total_queries
                }
            )
            
            # Update metrics with error
            self._metrics.update({
                "last_error": str(e),
                "total_errors": self._metrics.get("total_errors", 0) + 1
            })
            
            raise

    def _apply_conditional_formatting_to_queries(
        self,
        queries: List[Dict[str, Any]],
        chart_configurations: Dict[str, Dict[str, Any]],
        status_callback: Optional[Callable]
    ) -> List[Dict[str, Any]]:
        """Apply conditional formatting configurations to dashboard queries"""
        enhanced_queries = []
        
        for i, query_data in enumerate(queries):
            # Create a copy of the original query
            enhanced_query = query_data.copy()
            
            # Get chart configuration if available
            chart_id = query_data.get("chart_id", f"chart_{i}")
            chart_config = chart_configurations.get(chart_id, {})
            
            # Apply SQL expansion if configured
            if chart_config and ActionType.SQL_EXPANSION.value in chart_config.get("actions", []):
                sql_expansion_config = chart_config.get("sql_expansion", {})
                enhanced_query = self._apply_sql_expansion(enhanced_query, sql_expansion_config)
                
                self._send_status_update(
                    status_callback,
                    "sql_expansion_applied",
                    {
                        "chart_id": chart_id,
                        "query_index": i,
                        "expansions": list(sql_expansion_config.keys())
                    }
                )
            
            # Add chart adjustment configuration for later processing
            if chart_config and ActionType.CHART_ADJUSTMENT.value in chart_config.get("actions", []):
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
                additional_conditions = " AND " + " ".join(time_conditions)
                sql = sql[:insert_position] + additional_conditions + sql[insert_position:]
            else:
                insert_position = self._find_sql_insert_position(sql)
                where_clause = " WHERE " + " ".join(time_conditions)
                sql = sql[:insert_position] + where_clause + sql[insert_position:]
        
        return sql

    def _detect_date_column(self, sql: str) -> Optional[str]:
        """Detect date column in SQL query (simplified implementation)"""
        common_date_columns = ["date", "created_at", "updated_at", "timestamp", "time", "datetime"]
        sql_lower = sql.lower()
        
        for col in common_date_columns:
            if col in sql_lower:
                return col
        
        return None

    async def _apply_chart_adjustments(
        self,
        results: Dict[str, Any],
        chart_configurations: Dict[str, Dict[str, Any]],
        project_id: str,
        status_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Apply chart adjustments to dashboard results"""
        try:
            # This is a placeholder for chart adjustment logic
            # In practice, you'd integrate with chart adjustment pipelines
            
            for chart_id, chart_config in chart_configurations.items():
                if ActionType.CHART_ADJUSTMENT.value in chart_config.get("actions", []):
                    # Find corresponding result
                    for result_key, result_data in results.items():
                        if (result_data.get("query_data", {}).get("chart_id") == chart_id or
                            chart_id in result_key):
                            
                            # Apply chart adjustment configuration
                            adjustment_config = chart_config.get("chart_adjustment", {})
                            result_data["chart_adjustment_applied"] = True
                            result_data["chart_adjustment_config"] = adjustment_config
                            
                            self._send_status_update(
                                status_callback,
                                "chart_adjustment_applied",
                                {"chart_id": chart_id, "result_key": result_key}
                            )
                            break
            
            return results
            
        except Exception as e:
            logger.error(f"Error applying chart adjustments: {e}")
            return results

    async def _execute_queries_concurrent(
        self,
        queries: List[Dict[str, Any]],
        status_callback: Optional[Callable],
        execution_metadata: Dict[str, Any],
        **kwargs
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute queries concurrently with controlled concurrency"""
        
        semaphore = asyncio.Semaphore(self._configuration["max_concurrent_queries"])
        results = {}
        
        async def execute_single_query(query_index: int, query_data: Dict[str, Any]):
            async with semaphore:
                return await self._execute_single_query(
                    query_index, query_data, status_callback, execution_metadata, **kwargs
                )
        
        # Create tasks for all queries
        tasks = [
            execute_single_query(i, query_data)
            for i, query_data in enumerate(queries)
        ]
        
        # Execute all tasks
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(query_results):
            if isinstance(result, Exception):
                error_message = str(result)
                logger.error(f"Query {i} failed with exception: {error_message}")
                
                results[f"query_{i}"] = {
                    "success": False,
                    "error": error_message,
                    "query_index": i,
                    "query_data": queries[i]
                }
                execution_metadata["errors"].append({
                    "query_index": i,
                    "error": error_message,
                    "query": queries[i].get("query", "")
                })
            else:
                results[f"query_{result['query_index']}"] = result
        
        return results, execution_metadata

    async def _execute_queries_sequential(
        self,
        queries: List[Dict[str, Any]],
        status_callback: Optional[Callable],
        execution_metadata: Dict[str, Any],
        **kwargs
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute queries sequentially"""
        
        results = {}
        
        for i, query_data in enumerate(queries):
            try:
                result = await self._execute_single_query(
                    i, query_data, status_callback, execution_metadata, **kwargs
                )
                results[f"query_{i}"] = result
                
            except Exception as e:
                error_message = str(e)
                logger.error(f"Query {i} failed: {error_message}")
                
                results[f"query_{i}"] = {
                    "success": False,
                    "error": error_message,
                    "query_index": i,
                    "query_data": query_data
                }
                execution_metadata["errors"].append({
                    "query_index": i,
                    "error": error_message,
                    "query": query_data.get("query", "")
                })
                
                # Continue or stop based on configuration
                if not self._configuration["continue_on_error"]:
                    break
        
        return results, execution_metadata

    async def _execute_single_query(
        self,
        query_index: int,
        query_data: Dict[str, Any],
        status_callback: Optional[Callable],
        execution_metadata: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a single query using the SQL execution pipeline"""
        
        query_start_time = datetime.now()
        
        # Send query start status
        self._send_status_update(
            status_callback,
            "query_execution_started",
            {
                "query_index": query_index,
                "query": query_data.get("query", ""),
                "project_id": query_data.get("project_id", ""),
                "start_time": query_start_time.isoformat()
            }
        )
        
        try:
            # Extract parameters from query_data
            sql = query_data.get("sql", "")
            project_id = query_data.get("project_id", "")
            query_configuration = query_data.get("configuration", {})
            
            # Merge with global timeout configuration
            merged_config = {
                **query_configuration,
                "timeout": self._configuration["timeout_per_query"]
            }
            
            # Execute query using SQL execution pipeline
            execution_result = await self._sql_execution_pipeline.run(
                sql=sql,
                project_id=project_id,
                configuration=merged_config,
                **kwargs
            )
            
            query_end_time = datetime.now()
            execution_time = (query_end_time - query_start_time).total_seconds()
            
            # Prepare result
            result = {
                "success": True,
                "query_index": query_index,
                "execution_time_seconds": execution_time,
                "query_data": query_data,
                "execution_result": execution_result,
                "start_time": query_start_time.isoformat(),
                "end_time": query_end_time.isoformat()
            }
            
            # Update execution metadata
            execution_metadata["query_execution_order"].append({
                "query_index": query_index,
                "start_time": query_start_time.isoformat(),
                "end_time": query_end_time.isoformat(),
                "execution_time": execution_time,
                "success": True
            })
            
            # Send query completion status
            self._send_status_update(
                status_callback,
                "query_execution_completed",
                {
                    "query_index": query_index,
                    "execution_time": execution_time,
                    "success": True,
                    "data_rows": len(execution_result.get("post_process", {}).get("data", [])) if execution_result.get("post_process") else 0
                }
            )
            
            # Stream intermediate result if configured
            if self._configuration["stream_intermediate_results"]:
                self._send_status_update(
                    status_callback,
                    "query_result_available",
                    {
                        "query_index": query_index,
                        "result": result
                    }
                )
            
            return result
            
        except Exception as e:
            query_end_time = datetime.now()
            execution_time = (query_end_time - query_start_time).total_seconds()
            error_message = str(e)
            
            logger.error(f"Query {query_index} execution failed: {error_message}")
            
            # Update execution metadata
            execution_metadata["query_execution_order"].append({
                "query_index": query_index,
                "start_time": query_start_time.isoformat(),
                "end_time": query_end_time.isoformat(),
                "execution_time": execution_time,
                "success": False,
                "error": error_message
            })
            
            # Send query error status
            self._send_status_update(
                status_callback,
                "query_execution_failed",
                {
                    "query_index": query_index,
                    "execution_time": execution_time,
                    "error": error_message
                }
            )
            
            result = {
                "success": False,
                "query_index": query_index,
                "execution_time_seconds": execution_time,
                "query_data": query_data,
                "error": error_message,
                "start_time": query_start_time.isoformat(),
                "end_time": query_end_time.isoformat()
            }
            
            return result

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
        logger.info(f"Enhanced Dashboard Status - {status}: {details}")

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get detailed execution statistics"""
        return {
            "pipeline_metrics": self._metrics.copy(),
            "configuration": self._configuration.copy(),
            "sql_execution_pipeline_metrics": self._sql_execution_pipeline.get_metrics() if hasattr(self._sql_execution_pipeline, 'get_metrics') else {},
            "conditional_formatting_metrics": self._conditional_formatting_service.get_metrics() if hasattr(self._conditional_formatting_service, 'get_metrics') else {},
            "timestamp": datetime.now().isoformat()
        }

    def set_concurrent_execution(self, enabled: bool, max_concurrent: int = 5) -> None:
        """Configure concurrent execution settings"""
        self._configuration["concurrent_execution"] = enabled
        self._configuration["max_concurrent_queries"] = max_concurrent
        logger.info(f"Concurrent execution {'enabled' if enabled else 'disabled'}, max concurrent: {max_concurrent}")

    def set_streaming_options(self, stream_intermediate: bool = True, continue_on_error: bool = True) -> None:
        """Configure streaming behavior"""
        self._configuration["stream_intermediate_results"] = stream_intermediate
        self._configuration["continue_on_error"] = continue_on_error
        logger.info(f"Streaming options updated - intermediate: {stream_intermediate}, continue on error: {continue_on_error}")

    def set_conditional_formatting_options(self, enable_formatting: bool = True, enable_adjustments: bool = True) -> None:
        """Configure conditional formatting options"""
        self._configuration["enable_conditional_formatting"] = enable_formatting
        self._configuration["enable_chart_adjustments"] = enable_adjustments
        logger.info(f"Conditional formatting options updated - formatting: {enable_formatting}, adjustments: {enable_adjustments}")


# Factory function for creating enhanced dashboard pipeline
def create_enhanced_dashboard_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    conditional_formatting_service: Optional[Any] = None,
    sql_execution_pipeline: Optional[Any] = None,
    **kwargs
) -> EnhancedDashboardPipeline:
    """
    Factory function to create an enhanced dashboard pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        conditional_formatting_service: Conditional formatting service (optional, will create default if not provided)
        sql_execution_pipeline: Existing SQL execution pipeline (optional, will create if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        EnhancedDashboardPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return EnhancedDashboardPipeline(
        name="enhanced_dashboard_pipeline",
        version="1.0.0",
        description="Enhanced dashboard pipeline with streaming and conditional formatting capabilities",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        conditional_formatting_service=conditional_formatting_service,
        sql_execution_pipeline=sql_execution_pipeline,
        **kwargs
    )
