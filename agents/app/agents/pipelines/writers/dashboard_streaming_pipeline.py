import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import aiohttp

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.dependencies import get_llm
# Removed circular import: from app.agents.pipelines.pipeline_container import PipelineContainer

logger = logging.getLogger("lexy-ai-service")


class DashboardStreamingPipeline(AgentPipeline):
    """Pipeline for streaming multiple SQL execution results for dashboard rendering"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Any,
        retrieval_helper: RetrievalHelper,
        engine: Engine,
        sql_execution_pipeline: Optional[Any] = None
    ):
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=get_llm(),
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
            "aggregate_results": True
        }
        self._metrics = {}
        self._engine = engine
        
        # Initialize SQL execution pipeline if not provided
        if sql_execution_pipeline:
            self._sql_execution_pipeline = sql_execution_pipeline
        else:
            # Create a data summarization pipeline directly to avoid circular imports
            from app.agents.pipelines.sql_execution import DataSummarizationPipeline
            self._sql_execution_pipeline = DataSummarizationPipeline(
                name="sql_execution_internal",
                version="1.0.0",
                description="Internal SQL execution for dashboard streaming",
                llm=llm,
                retrieval_helper=retrieval_helper,
                engine=engine,
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
        queries: List[Dict[str, Any]],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute multiple SQL queries for dashboard rendering with streaming results
        
        Args:
            queries: List of query objects, each containing:
                - sql: SQL query string
                - query: Natural language description
                - project_id: Project identifier
                - data_description: Description of the data
                - configuration: Query-specific configuration
            status_callback: Callback function for streaming status updates
            configuration: Global configuration overrides
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing all query results and execution metadata
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
            "errors": []
        }
        
        # Send initial status update
        self._send_status_update(
            status_callback,
            "dashboard_streaming_started",
            {
                "total_queries": total_queries,
                "concurrent_execution": self._configuration["concurrent_execution"],
                "max_concurrent": self._configuration["max_concurrent_queries"]
            }
        )
        
        try:
            # Debug logging to see what kwargs are received
            logger.debug(f"Dashboard streaming pipeline run method - kwargs keys: {list(kwargs.keys())}, kwargs values: {kwargs}")
            
            # Filter out project_id from kwargs to avoid duplicate parameter errors
            filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'project_id'}
            logger.debug(f"After filtering - filtered_kwargs keys: {list(filtered_kwargs.keys())}")
            
            # Process queries based on configuration
            if self._configuration["concurrent_execution"]:
                results, execution_metadata = await self._execute_queries_concurrent(
                    queries, status_callback, execution_metadata, **filtered_kwargs
                )
            else:
                results, execution_metadata = await self._execute_queries_sequential(
                    queries, status_callback, execution_metadata, **filtered_kwargs
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
                    "success_rate": execution_metadata["success_rate"]
                },
                "total_executions": self._metrics.get("total_executions", 0) + 1,
                "total_queries_processed": self._metrics.get("total_queries_processed", 0) + total_queries
            })
            
            # Send final status update
            self._send_status_update(
                status_callback,
                "dashboard_streaming_completed",
                {
                    "total_queries": total_queries,
                    "completed_queries": completed_queries,
                    "failed_queries": failed_queries,
                    "execution_time": total_execution_time,
                    "success_rate": execution_metadata["success_rate"]
                }
            )
            
            # Prepare final response
            final_response = {
                "post_process": {
                    "results": results,
                    "execution_metadata": execution_metadata,
                    "success": True
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
            logger.error(f"Error in dashboard streaming pipeline: {str(e)}")
            
            # Send error status update
            self._send_status_update(
                status_callback,
                "dashboard_streaming_error",
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

    async def _execute_queries_concurrent(
        self,
        queries: List[Dict[str, Any]],
        status_callback: Optional[Callable],
        execution_metadata: Dict[str, Any],
        **kwargs
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute queries concurrently with controlled concurrency"""
        
        # Debug logging
        logger.debug(f"_execute_queries_concurrent - kwargs keys: {list(kwargs.keys())}")
        
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
        
        # Debug logging
        logger.debug(f"_execute_queries_sequential - kwargs keys: {list(kwargs.keys())}")
        
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
        
        # Debug logging
        logger.debug(f"_execute_single_query - query_index: {query_index}, kwargs keys: {list(kwargs.keys())}")
        
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
            query = query_data.get("query", "")
            data_description = query_data.get("data_description", "")
            query_configuration = query_data.get("configuration", {})
            
            # Merge with global timeout configuration
            merged_config = {
                **query_configuration,
                "timeout": self._configuration["timeout_per_query"]
            }
            
            # Execute query using SQL execution pipeline
            # Filter out project_id from kwargs to avoid duplicate parameter error
            filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'project_id'}
            
            # Debug logging to see what's being passed
            logger.debug(f"SQL execution pipeline call - query: {query[:50]}..., sql: {sql[:50]}..., project_id: {project_id}, filtered_kwargs keys: {list(filtered_kwargs.keys())}")
            
            execution_result = await self._sql_execution_pipeline.run(
                query=query,
                sql=sql,
                data_description=data_description,
                project_id=project_id,
                configuration=merged_config,
                **filtered_kwargs
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
        logger.info(f"Dashboard Streaming Status - {status}: {details}")

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get detailed execution statistics"""
        return {
            "pipeline_metrics": self._metrics.copy(),
            "configuration": self._configuration.copy(),
            "sql_execution_pipeline_metrics": self._sql_execution_pipeline.get_metrics() if hasattr(self._sql_execution_pipeline, 'get_metrics') else {},
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


# Factory function for creating dashboard streaming pipeline
def create_dashboard_streaming_pipeline(
    engine: Engine,
    llm: Any = None,
    retrieval_helper: RetrievalHelper = None,
    sql_execution_pipeline: Optional[Any] = None,
    **kwargs
) -> DashboardStreamingPipeline:
    """
    Factory function to create a dashboard streaming pipeline
    
    Args:
        engine: Database engine instance
        llm: Language model instance (optional, will use default if not provided)
        retrieval_helper: Retrieval helper instance (optional, will create default if not provided)
        sql_execution_pipeline: Existing SQL execution pipeline (optional, will create if not provided)
        **kwargs: Additional configuration options
    
    Returns:
        DashboardStreamingPipeline instance
    """
    
    if not llm:
        llm = get_llm()
    
    if not retrieval_helper:
        retrieval_helper = RetrievalHelper()
    
    return DashboardStreamingPipeline(
        name="dashboard_streaming_pipeline",
        version="1.0.0",
        description="Pipeline for streaming multiple SQL execution results for dashboard rendering",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        sql_execution_pipeline=sql_execution_pipeline,
        **kwargs
    )