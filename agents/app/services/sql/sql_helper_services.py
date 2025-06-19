import asyncio
import logging
from typing import Dict, List, Literal, Optional, Any, AsyncGenerator, Callable
import json
from aiohttp import web
from aiohttp.web import Response
from aiohttp.web_request import Request
import pandas as pd
import numpy as np
from datetime import datetime

from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import AliasChoices, BaseModel, Field

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.services.sql import SSEEvent
from app.services.sql.models import (
    AskRequest,
    StopAskRequest,
    AskResult,
    AskError,
    AskResultRequest,
    QualityScoring,
    AskResultResponse,
    AskFeedbackRequest,
    StopAskFeedbackRequest,
    AskFeedbackResultRequest,
    AskFeedbackResultResponse,
)
from app.services.servicebase import BaseService
from app.core.engine_provider import EngineProvider
from app.core.dependencies import get_llm
# Import enhanced SQL pipeline components
from app.agents.pipelines.enhanced_sql_pipeline import (
    EnhancedSQLPipelineWrapper,
    PipelineRequest,
    PipelineType,
    SQLAdvancedRelevanceScorer,
    RetrievalHelper,
)
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.core.dependencies import get_doc_store_provider
from app.agents.pipelines.enhanced_sql_pipeline import EnhancedPipelineFactory
from app.utils.streaming import streaming_manager
from app.agents.pipelines.sql_execution import SQLExecutionPipeline
logger = logging.getLogger("lexy-ai-service")

#from app.agents.pipelines.sql_data_summarization import SQLDataSummarizationPipeline
#from app.agents.pipelines.sql_visualization import SQLVisualizationPipeline
#from app.agents.pipelines.sql_expansion import SQLExpansionPipeline
"""
This service is used to help with the SQL execution, data summarization and sql expansion pipelines.
SQL execution pipeline: will run against the real db, paginate the data from the db.
SQL data summarization pipeline: will run against the real db, will chunk the data send to LLMs and will return the summarized answers
SQL Visualization pipeline: will run against the real db will perform the chart generation for Vegalite or plotly

SQL Expansion pipeline: will run against the real db, will be used to identify whats missing in the current question and what needs to be added.
It is used to generate the SQL query from the user's query and to execute the SQL query.
It is also used to get the data from the database.
"""

class SQLHelperService(BaseService[AskRequest, AskResultResponse]):
    def __init__(
        self,
        pipeline_container: Optional[PipelineContainer] = None,
        allow_intent_classification: bool = True,
        allow_sql_generation_reasoning: bool = True,
        max_histories: int = 10,
        maxsize: int = 1_000_000,
        ttl: int = 120,
        # Added parameters for enhanced SQL pipeline
        enable_enhanced_sql: bool = True,
        sql_scoring_config_path: Optional[str] = None,
    ):
        # Use provided pipeline container or get the singleton instance
        self._pipeline_container = pipeline_container or PipelineContainer.get_instance()
        super().__init__(self._pipeline_container.get_all_pipelines(), maxsize=maxsize, ttl=ttl)
        
        self._allow_sql_generation_reasoning = allow_sql_generation_reasoning
        self._allow_intent_classification = allow_intent_classification
        self._max_histories = max_histories
        
        # Enhanced SQL pipeline setup
        self._enable_enhanced_sql = enable_enhanced_sql
        self._sql_scoring_config_path = sql_scoring_config_path
        self._enhanced_sql_system = None
        engine = EngineProvider.get_engine()

        # Initialize enhanced SQL system if enabled
        if enable_enhanced_sql:
            try:
                self._enhanced_sql_system = EnhancedPipelineFactory.create_enhanced_unified_system(
                    engine=engine,
                    document_store_provider=get_doc_store_provider(),
                    use_rag=True,
                    enable_sql_scoring=True,
                    scoring_config_path=sql_scoring_config_path
                )
                logger.info("Enhanced SQL pipeline unified system initialized")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced SQL pipeline: {e}")
                self._enable_enhanced_sql = False
                self._enhanced_sql_system = None

        self._streaming_clients: Dict[str, List[web.WebSocketResponse]] = {}

    async def _generate_sql_data(self, query_id: str, sql_result: Dict[str, Any], project_id: str, configuration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate SQL execution data"""
        if self._is_stopped(query_id):
            return {"success": False}

        self._update_cache_status(
            query_id,
            "executing_sql",
            AskResultResponse(
                status="executing_sql",
                type="TEXT_TO_SQL",
                is_followup=True
            )
        )

        try:
            # Get SQL execution pipeline
            sql_execution_pipeline = self._pipeline_container.get_pipeline("sql_execution")
            if not sql_execution_pipeline:
                raise RuntimeError("SQL execution pipeline not found")

            # Get SQL from result
            sql = ""
            if sql_result.get("api_results"):
                sql = sql_result["api_results"][0].sql
            logger.info(f"sql in generate_sql_data: {sql}") 
            if not sql:
                return {
                    "success": False,
                    "error": {
                        "code": "SQL_EXECUTION_ERROR",
                        "message": "No SQL found in result"
                    }
                }

            # Execute SQL
            result = await sql_execution_pipeline.run(
                sql=sql,
                project_id=project_id,
                configuration=configuration
            )

            if result.get("post_process"):
                return {
                    "success": True,
                    "data": result["post_process"]['data']
                }
            else:
                return {
                    "success": False,
                    "error": {
                        "code": "SQL_EXECUTION_ERROR",
                        "message": "No data returned from SQL execution"
                    }
                }

        except Exception as e:
            logger.exception(f"Error in SQL data generation: {e}")
            return {
                "success": False,
                "error": {
                    "code": "SQL_EXECUTION_ERROR",
                    "message": str(e)
                }
            }
    
    async def _generate_sql_summary(
        self,
        query_id: str,
        user_query: str,
        sql_result: Dict[str, Any],
        request: AskRequest,
    ) -> Dict[str, Any]:
        """Generate a summary of the SQL query and its results"""
        if self._is_stopped(query_id):
            return {"success": False}

        self._update_cache_status(
            query_id,
            "generating",
            AskResultResponse(
                status="generating",
                type="TEXT_TO_SQL",
                is_followup=True if request.histories else False,
            )
        )

        try:
            # Get SQL summary pipeline
            summary_pipeline = self._pipeline_container.get_pipeline("sql_summary")
            if not summary_pipeline:
                logger.warning("SQL summary pipeline not found")
                return {"success": False, "error": "SQL summary pipeline not available"}
            
            # Prepare the SQL for summary
            sql_to_summarize = ""
            if sql_result.get("api_results"):
                sql_to_summarize = sql_result["api_results"][0].sql

            # Generate summary using the updated pipeline interface
            summary_result = await summary_pipeline.run(
                query=user_query,
                sql=sql_to_summarize,
                project_id=request.project_id,
                schema_context=request.schema_context if hasattr(request, 'schema_context') else None
            )
            print("summary_result in ask service", summary_result)
            # Handle the new response format
            if summary_result.get("success"):
                return {
                    "success": True,
                    "summary": summary_result.get("data", {}).get("summary", ""),
                    "metadata": summary_result.get("data", {}).get("metadata", {})
                }
            else:
                return {
                    "success": False,
                    "error": summary_result.get("error", "Failed to generate summary")
                }

        except Exception as e:
            logger.error(f"Error generating SQL summary: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_query_requirements(
        self,
        query_id: str,
        query: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        schema_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze query requirements using SQL expansion and correction pipelines
        
        Args:
            query_id: Unique identifier for the query
            query: The user's query to analyze
            project_id: Project identifier
            configuration: Optional configuration parameters
            schema_context: Optional schema context
            
        Returns:
            Dict containing analysis results including:
            - success: Whether the analysis was successful
            - data: Analysis results including:
                - expansion_suggestions: Suggestions from SQL expansion
                - correction_suggestions: Suggestions from SQL correction
                - combined_analysis: Combined analysis of what's needed
            - error: Any error that occurred
        """
        if self._is_stopped(query_id):
            return {"success": False}

        try:
            # Get required pipelines
            expansion_pipeline = self._pipeline_container.get_pipeline("sql_expansion")
            correction_pipeline = self._pipeline_container.get_pipeline("sql_correction")
            
            if not expansion_pipeline or not correction_pipeline:
                raise RuntimeError("Required pipelines not found")

            # Run SQL expansion analysis
            expansion_result = await expansion_pipeline.run(
                query=query,
                project_id=project_id,
                schema_context=schema_context,
                configuration=configuration
            )

            # Run SQL correction analysis
            correction_result = await correction_pipeline.run(
                query=query,
                project_id=project_id,
                schema_context=schema_context,
                configuration=configuration
            )

            # Combine and analyze results
            combined_analysis = {
                "expansion_suggestions": expansion_result.get("data", {}),
                "correction_suggestions": correction_result.get("data", {}),
                "combined_analysis": {
                    "missing_elements": [],
                    "required_changes": [],
                    "suggested_improvements": []
                }
            }

            # Extract missing elements from expansion
            if expansion_result.get("success"):
                expansion_data = expansion_result.get("data", {})
                if "missing_elements" in expansion_data:
                    combined_analysis["combined_analysis"]["missing_elements"].extend(
                        expansion_data["missing_elements"]
                    )

            # Extract required changes from correction
            if correction_result.get("success"):
                correction_data = correction_result.get("data", {})
                if "required_changes" in correction_data:
                    combined_analysis["combined_analysis"]["required_changes"].extend(
                        correction_data["required_changes"]
                    )

            # Generate suggested improvements
            if expansion_result.get("success") and correction_result.get("success"):
                combined_analysis["combined_analysis"]["suggested_improvements"] = [
                    f"Add {element}" for element in combined_analysis["combined_analysis"]["missing_elements"]
                ] + [
                    f"Modify {change}" for change in combined_analysis["combined_analysis"]["required_changes"]
                ]

            return {
                "success": True,
                "data": combined_analysis,
                "error": None
            }

        except Exception as e:
            logger.error(f"Error analyzing query requirements: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    async def generate_sql_visualization(
        self,
        query_id: str,
        query: str,
        sql_result: Dict[str, Any],
        request: AskRequest,
        chart_config: Optional[Dict[str, Any]] = None,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """Generate SQL visualization with data, summary and chart generation
        
        Args:
            query_id: Unique identifier for the query
            query: The user's query
            sql_result: The SQL query result
            request: The original AskRequest
            chart_config: Optional chart configuration
            streaming: Whether to stream the results
            
        Returns:
            Dict containing visualization results including:
            - success: Whether the generation was successful
            - data: Results including:
                - sql_data: The SQL execution data
                - summary: The SQL summary
                - chart: The generated chart
            - error: Any error that occurred
        """
        if self._is_stopped(query_id):
            return {"success": False}

        try:
            # Get required pipelines
            chart_pipeline = self._pipeline_container.get_pipeline("chart_generation")
            if not chart_pipeline:
                raise RuntimeError("Chart generation pipeline not found")

            # Generate SQL data
            sql_data_result = await self._generate_sql_data(
                query_id=query_id,
                sql_result=sql_result,
                project_id=request.project_id,
                configuration=request.configuration
            )

            if not sql_data_result.get("success"):
                return sql_data_result

            # Generate SQL summary
            summary_result = await self._generate_sql_summary(
                query_id=query_id,
                user_query=query,
                sql_result=sql_result,
                request=request
            )

            if not summary_result.get("success"):
                return summary_result

            # Update status for chart generation
            self._update_cache_status(
                query_id,
                "generating_chart",
                AskResultResponse(
                    status="generating_chart",
                    type="CHART_GENERATION",
                    is_followup=True if request.histories else False,
                )
            )

            # Generate chart
            chart_result = await chart_pipeline.run(
                query=query,
                sql=sql_result.get("api_results", [{}])[0].get("sql", ""),
                data=sql_data_result.get("data", {}),
                language=request.language,
                export_format=chart_config.get("export_format") if chart_config else None,
                **chart_config if chart_config else {}
            )

            # Combine all results
            combined_result = {
                "success": all([
                    sql_data_result.get("success", False),
                    summary_result.get("success", False),
                    chart_result.get("success", False)
                ]),
                "data": {
                    "sql_data": sql_data_result.get("data", {}),
                    "summary": summary_result.get("summary", ""),
                    "summary_metadata": summary_result.get("metadata", {}),
                    "chart": chart_result.get("data", {})
                },
                "error": None
            }

            # Handle streaming if enabled
            if streaming:
                await self._stream_visualization_results(
                    query_id=query_id,
                    results=combined_result
                )

            return combined_result

        except Exception as e:
            logger.error(f"Error generating SQL visualization: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    async def _stream_visualization_results(
        self,
        query_id: str,
        results: Dict[str, Any]
    ) -> None:
        """Stream visualization results to connected clients
        
        Args:
            query_id: Unique identifier for the query
            results: The visualization results to stream
        """
        try:
            # Get streaming clients for this query
            clients = self._streaming_clients.get(query_id, [])
            if not clients:
                return

            # Prepare streaming events
            events = [
                SSEEvent(
                    event="sql_data",
                    data=json.dumps(results["data"]["sql_data"])
                ),
                SSEEvent(
                    event="summary",
                    data=json.dumps({
                        "summary": results["data"]["summary"],
                        "metadata": results["data"]["summary_metadata"]
                    })
                ),
                SSEEvent(
                    event="chart",
                    data=json.dumps(results["data"]["chart"])
                )
            ]

            # Stream events to all connected clients
            for client in clients:
                try:
                    for event in events:
                        await client.send_str(event.to_sse())
                except Exception as e:
                    logger.error(f"Error streaming to client: {e}")
                    # Remove failed client
                    clients.remove(client)

            # Clean up if no clients left
            if not clients:
                del self._streaming_clients[query_id]

        except Exception as e:
            logger.error(f"Error in streaming visualization results: {e}")

    def register_streaming_client(
        self,
        query_id: str,
        client: web.WebSocketResponse
    ) -> None:
        """Register a new streaming client for a query
        
        Args:
            query_id: Unique identifier for the query
            client: The WebSocket client to register
        """
        if query_id not in self._streaming_clients:
            self._streaming_clients[query_id] = []
        self._streaming_clients[query_id].append(client)

    def unregister_streaming_client(
        self,
        query_id: str,
        client: web.WebSocketResponse
    ) -> None:
        """Unregister a streaming client for a query
        
        Args:
            query_id: Unique identifier for the query
            client: The WebSocket client to unregister
        """
        if query_id in self._streaming_clients:
            if client in self._streaming_clients[query_id]:
                self._streaming_clients[query_id].remove(client)
            if not self._streaming_clients[query_id]:
                del self._streaming_clients[query_id]

    async def generate_sql_summary_and_visualization(
        self,
        query_id: str,
        sql: str,
        query: str,
        project_id: str,
        data_description: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate SQL summary and visualization using DataSummarizationPipeline
        
        Args:
            query_id: Unique identifier for the query
            sql: The SQL query to execute and summarize
            query: The user's original query
            project_id: Project identifier
            data_description: Optional description of the data being analyzed
            configuration: Optional configuration parameters for the pipeline
            
        Returns:
            Dict containing summary and visualization results including:
            - success: Whether the generation was successful
            - data: Results including:
                - executive_summary: The generated summary
                - data_overview: Overview of the data processed
                - visualization: The generated chart/visualization
            - error: Any error that occurred
        """
        if self._is_stopped(query_id):
            return {"success": False}

        try:
            # Get data summarization pipeline
            data_summarization_pipeline = self._pipeline_container.get_pipeline("data_summarization")
            if not data_summarization_pipeline:
                raise RuntimeError("Data summarization pipeline not found")

            # Update status
            self._update_cache_status(
                query_id,
                "generating_summary",
                AskResultResponse(
                    status="generating_summary",
                    type="DATA_SUMMARIZATION",
                    is_followup=False
                )
            )

            # Prepare data description if not provided
            if not data_description:
                data_description = f"Data from SQL query: {sql[:100]}..."

            # Merge default configuration with provided configuration
            default_config = {
                "batch_size": 1000,
                "chunk_size": 150,
                "language": "English",
                "enable_chart_generation": True,
                "chart_format": "vega_lite",
                "include_other_formats": False,
                "use_multi_format": True
            }
            
            if configuration:
                default_config.update(configuration)

            # Run the data summarization pipeline
            result = await data_summarization_pipeline.run(
                query=query,
                sql=sql,
                data_description=data_description,
                project_id=project_id,
                configuration=default_config
            )

            # Process the result
            if result and result.get("post_process"):
                post_process = result["post_process"]
                
                return {
                    "success": True,
                    "data": {
                        "executive_summary": post_process.get("executive_summary", ""),
                        "data_overview": post_process.get("data_overview", {}),
                        "visualization": post_process.get("visualization", {}),
                        "metadata": result.get("metadata", {})
                    },
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": "No data returned from summarization pipeline"
                }

        except Exception as e:
            logger.error(f"Error generating SQL summary and visualization: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    async def stream_sql_summary_and_visualization(
        self,
        query_id: str,
        sql: str,
        query: str,
        project_id: str,
        data_description: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream SQL summary and visualization using DataSummarizationPipeline with callbacks
        
        Args:
            query_id: Unique identifier for the query
            sql: The SQL query to execute and summarize
            query: The user's original query
            project_id: Project identifier
            data_description: Optional description of the data being analyzed
            configuration: Optional configuration parameters for the pipeline
            
        Yields:
            Dict containing streaming updates including:
            - status: Current status of the operation
            - data: Partial or complete results
            - error: Any error that occurred
        """
        if self._is_stopped(query_id):
            yield {"status": "stopped", "error": "Query was stopped"}
            return

        try:
            # Get data summarization pipeline
            data_summarization_pipeline = self._pipeline_container.get_pipeline("data_summarization")
            if not data_summarization_pipeline:
                yield {"status": "error", "error": "Data summarization pipeline not found"}
                return

            # Prepare data description if not provided
            if not data_description:
                data_description = f"Data from SQL query: {sql[:100]}..."

            # Merge default configuration with provided configuration
            default_config = {
                "batch_size": 1000,
                "chunk_size": 150,
                "language": "English",
                "enable_chart_generation": True,
                "chart_format": "vega_lite",
                "include_other_formats": True,
                "use_multi_format": True
            }
            
            if configuration:
                default_config.update(configuration)

            # Track final result
            final_result = None

            # Define status callback function for streaming
            def status_callback(status: str, details: Dict[str, Any] = None):
                """Status callback function that yields updates"""
                nonlocal final_result
                
                try:
                    # Update cache status
                    self._update_cache_status(
                        query_id,
                        status,
                        AskResultResponse(
                            status=status,
                            type="DATA_SUMMARIZATION",
                            is_followup=False
                        )
                    )

                    # Prepare streaming update
                    update = {
                        "status": status,
                        "details": details or {},
                        "timestamp": datetime.now().isoformat()
                    }

                    # Add specific data based on status
                    if status == "fetch_data_complete":
                        update["data"] = {
                            "total_count": details.get("total_count", 0),
                            "total_batches": details.get("total_batches", 0),
                            "batch_size": details.get("batch_size", 0)
                        }
                    elif status == "summarization_begin":
                        update["data"] = {
                            "batch_number": details.get("batch_number", 0),
                            "total_batches": details.get("total_batches", 0),
                            "batch_size": details.get("batch_size", 0)
                        }
                    elif status == "summarization_complete":
                        update["data"] = {
                            "batch_number": details.get("batch_number", 0),
                            "total_batches": details.get("total_batches", 0),
                            "is_last_batch": details.get("is_last_batch", False)
                        }
                    elif status == "chart_generation_begin":
                        update["data"] = {
                            "chart_format": details.get("chart_format", "vega_lite"),
                            "total_batches": details.get("total_batches", 0)
                        }
                    elif status == "chart_generation_complete":
                        update["data"] = {
                            "success": details.get("success", False),
                            "chart_format": details.get("chart_format", "vega_lite"),
                            "error": details.get("error")
                        }

                    # Yield the update (this will be handled by the async generator)
                    # Note: We can't directly yield here, so we'll store it for later processing
                    if hasattr(self, '_streaming_updates'):
                        self._streaming_updates.append(update)
                    else:
                        self._streaming_updates = [update]

                except Exception as e:
                    logger.error(f"Error in status callback: {e}")

            # Initialize streaming updates list
            self._streaming_updates = []

            # Run the data summarization pipeline with status callback
            result = await data_summarization_pipeline.run(
                query=query,
                sql=sql,
                data_description=data_description,
                project_id=project_id,
                configuration=default_config,
                status_callback=status_callback
            )

            # Process streaming updates
            for update in self._streaming_updates:
                yield update

            # Process the final result
            if result and result.get("post_process"):
                post_process = result["post_process"]
                final_result = {
                    "status": "completed",
                    "data": {
                        "executive_summary": post_process.get("executive_summary", ""),
                        "data_overview": post_process.get("data_overview", {}),
                        "visualization": post_process.get("visualization", {}),
                        "metadata": result.get("metadata", {})
                    },
                    "timestamp": datetime.now().isoformat()
                }
            else:
                final_result = {
                    "status": "error",
                    "error": "No data returned from summarization pipeline",
                    "timestamp": datetime.now().isoformat()
                }

            # Yield final result
            yield final_result

            # Clean up streaming updates
            if hasattr(self, '_streaming_updates'):
                del self._streaming_updates

        except Exception as e:
            logger.error(f"Error streaming SQL summary and visualization: {e}")
            yield {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def stop_query(self, query_id: str) -> None:
        """Stop an ongoing query process.
        
        Args:
            query_id: Unique identifier for the query to stop
        """
        try:
            # Mark the query as stopped in the cache
            self._stop_query(query_id)
            logger.info(f"Query {query_id} stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping query {query_id}: {e}")
            raise

    def get_query_status(self, query_id: str) -> Dict[str, Any]:
        """Get the status of a query.
        
        Args:
            query_id: Unique identifier for the query
            
        Returns:
            Dict containing the query status information
        """
        try:
            # Get the cached status for the query
            cached_result = self._get_cached_result(query_id)
            if cached_result:
                return {
                    "query_id": query_id,
                    "status": cached_result.status,
                    "type": cached_result.type,
                    "is_followup": cached_result.is_followup,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "query_id": query_id,
                    "status": "not_found",
                    "message": "Query not found in cache",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting status for query {query_id}: {e}")
            return {
                "query_id": query_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


