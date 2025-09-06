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

    async def generate_sql_data(
        self, 
        query_id: str, 
        sql: str,
        query: str, 
        project_id: str, 
        configuration: Optional[Dict[str, Any]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate SQL execution data with optional pagination
        
        Args:
            query_id: Unique identifier for the query
            sql: The SQL query to execute
            query: The original user query
            project_id: Project identifier
            configuration: Optional configuration parameters
            page: Page number for pagination (1-based, optional)
            page_size: Number of records per page (optional)
        """
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
            logger.info(f"sql in generate_sql_data: {sql}") 
            if not sql:
                return {
                    "success": False,
                    "error": {
                        "code": "SQL_EXECUTION_ERROR",
                        "message": "No SQL found in result"
                    }
                }

            # Prepare configuration with pagination
            execution_config = configuration or {}
            if page is not None and page_size is not None:
                execution_config.update({
                    "page": page,
                    "page_size": page_size,
                    "enable_pagination": True
                })

            # Execute SQL
            result = await sql_execution_pipeline.run(
                sql=sql,
                query=query,
                project_id=project_id,
                configuration=execution_config
            )

            if result.get("post_process"):
                data = result["post_process"]['data']
                
                # Add pagination metadata if pagination was used
                response = {
                    "success": True,
                    "data": data
                }
                
                # Add pagination info if available
                if "pagination" in result["post_process"]:
                    response["pagination"] = result["post_process"]["pagination"]
                elif page is not None and page_size is not None:
                    # Add basic pagination info if not provided by pipeline
                    total_records = len(data) if isinstance(data, list) else 0
                    response["pagination"] = {
                        "page": page,
                        "page_size": page_size,
                        "total_records": total_records,
                        "total_pages": (total_records + page_size - 1) // page_size if total_records > 0 else 0,
                        "has_next": page * page_size < total_records,
                        "has_previous": page > 1
                    }
                
                return response
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
    
   


        """
    This function is used to generate the SQL expansion using the SQL expansion pipeline.
    It is used to generate the SQL query from the user's query and to execute the SQL query.
    It is also used to get the data from the database.
    """
    async def generate_sql_correction(
        self,
        query_id: str,
        query: str,
        error_message: str,
        sql: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        schema_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate SQL correction using SQL correction pipeline
        
        Args:       
            query_id: Unique identifier for the query
            query: The user's query
            error_message: The error message from the original SQL execution
            sql: The original SQL that failed
            project_id: Project identifier
        """
        try:
            # Initialize the SQL correction pipeline
            sql_correction_pipeline = self._pipeline_container.get_pipeline("sql_correction")
            if not sql_correction_pipeline:
                raise RuntimeError("SQL correction pipeline not found")

            # Generate SQL correction
            correction_result = await sql_correction_pipeline.run(
                query=query,
                sql=sql,
                error_message=error_message,
                project_id=project_id,
                configuration=configuration,
                schema_context=schema_context
            )
            
            # Extract the actual data from the pipeline result
            # The SQL correction pipeline likely returns valid_generation_results and invalid_generation_results
            valid_results = correction_result.get("valid_generation_results", [])
            invalid_results = correction_result.get("invalid_generation_results", [])
            
            # Extract SQL from valid results
            corrected_sql_list = [result.get("sql", "") for result in valid_results if result.get("sql")]
            
            # Combine and analyze results
            combined_analysis = {
                "expansion_suggestions": {},
                "correction_suggestions": {
                    "corrected_sql": corrected_sql_list,
                    "valid_results": valid_results,
                    "invalid_results": invalid_results,
                    "total_valid": len(valid_results),
                    "total_invalid": len(invalid_results),
                    "original_error": error_message
                },
                "combined_analysis": {
                    "missing_elements": [],
                    "required_changes": [],
                    "suggested_improvements": []
                }
            }
            
            # Generate suggestions based on the results
            if corrected_sql_list:
                combined_analysis["combined_analysis"]["suggested_improvements"] = [
                    f"Use corrected SQL: {sql}" for sql in corrected_sql_list
                ]
            
            if invalid_results:
                error_messages = [result.get("error", "Unknown error") for result in invalid_results]
                combined_analysis["combined_analysis"]["required_changes"].extend(error_messages)
                combined_analysis["combined_analysis"]["suggested_improvements"].extend([
                    f"Fix SQL error: {error}" for error in error_messages
                ])

            return {
                "success": True,
                "data": combined_analysis,
                "error": None
            }
        
        except Exception as e:
            logger.error(f"Error generating SQL correction: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    """
    This function is used to generate the SQL expansion using the SQL expansion pipeline.
    It is used to generate the SQL query from the user's query and to execute the SQL query.
    It is also used to get the data from the database.
    """
    async def generate_sql_expansion(
        self,
        query_id: str,
        query: str,
        sql: str,
        original_query: str,
        original_reasoning: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        schema_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate SQL expansion using SQL expansion pipeline
        
        Args:       
            query_id: Unique identifier for the query
            query: The user's query
            project_id: Project identifier
        """
        try:
            # Initialize the SQL expansion pipeline
            sql_expansion_pipeline = self._pipeline_container.get_pipeline("sql_expansion")
            if not sql_expansion_pipeline:
                raise RuntimeError("SQL expansion pipeline not found")

            # Generate SQL expansion
            expansion_result = await sql_expansion_pipeline.run(
                query=query,
                sql=sql,
                original_query=original_query,
                original_reasoning=original_reasoning,
                project_id=project_id,
                configuration=configuration,
                schema_context=schema_context
            )
            
            # Extract the actual data from the pipeline result
            # The SQL expansion pipeline returns valid_generation_results and invalid_generation_results
            valid_results = expansion_result.get("valid_generation_results", [])
            invalid_results = expansion_result.get("invalid_generation_results", [])
            
            # Extract SQL from valid results
            expanded_sql_list = [result.get("sql", "") for result in valid_results if result.get("sql")]
            
            # Combine and analyze results
            combined_analysis = {
                "expansion_suggestions": {
                    "expanded_sql": expanded_sql_list,
                    "valid_results": valid_results,
                    "invalid_results": invalid_results,
                    "total_valid": len(valid_results),
                    "total_invalid": len(invalid_results)
                },
                "correction_suggestions": {},
                "combined_analysis": {
                    "missing_elements": [],
                    "required_changes": [],
                    "suggested_improvements": []
                }
            }
            
            # Generate suggestions based on the results
            if expanded_sql_list:
                combined_analysis["combined_analysis"]["suggested_improvements"] = [
                    f"Use expanded SQL: {sql}" for sql in expanded_sql_list
                ]
            
            if invalid_results:
                error_messages = [result.get("error", "Unknown error") for result in invalid_results]
                combined_analysis["combined_analysis"]["required_changes"].extend(error_messages)
                combined_analysis["combined_analysis"]["suggested_improvements"].extend([
                    f"Fix SQL error: {error}" for error in error_messages
                ])
            
            print("combined_analysis in generate_sql_expansion in sql_helper_services", combined_analysis)
            return {
                "success": True,
                "data": combined_analysis,
                "error": None
            }
        
        except Exception as e:
            logger.error(f"Error generating SQL expansion: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    """
    This function is used to analyze the query requirements using SQL expansion and correction pipelines.
    It is used to generate the SQL query from the user's query and to execute the SQL query.
    It is also used to get the data from the database.
    """
    async def analyze_query_requirements(
        self,
        query_id: str,
        query: str,
        project_id: str,
        sql: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        schema_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze query requirements using SQL expansion and correction pipelines
        
        Args:
            query_id: Unique identifier for the query
            sql: The SQL query to analyze
            user_query: The user's query to analyze
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

            # Extract data from expansion result (SQL expansion pipeline returns valid_generation_results and invalid_generation_results)
            valid_expansion_results = expansion_result.get("valid_generation_results", [])
            invalid_expansion_results = expansion_result.get("invalid_generation_results", [])
            expanded_sql_list = [result.get("sql", "") for result in valid_expansion_results if result.get("sql")]
            
            # Extract data from correction result (assuming it has a similar structure or different structure)
            correction_data = correction_result.get("data", {}) if correction_result.get("data") else {}
            if not correction_data and correction_result.get("valid_generation_results"):
                # If correction pipeline also uses the same structure
                valid_correction_results = correction_result.get("valid_generation_results", [])
                invalid_correction_results = correction_result.get("invalid_generation_results", [])
                correction_data = {
                    "valid_results": valid_correction_results,
                    "invalid_results": invalid_correction_results,
                    "corrected_sql": [result.get("sql", "") for result in valid_correction_results if result.get("sql")]
                }

            # Combine and analyze results
            combined_analysis = {
                "expansion_suggestions": {
                    "expanded_sql": expanded_sql_list,
                    "valid_results": valid_expansion_results,
                    "invalid_results": invalid_expansion_results,
                    "total_valid": len(valid_expansion_results),
                    "total_invalid": len(invalid_expansion_results)
                },
                "correction_suggestions": correction_data,
                "combined_analysis": {
                    "missing_elements": [],
                    "required_changes": [],
                    "suggested_improvements": []
                }
            }

            # Extract missing elements from expansion
            if expanded_sql_list:
                combined_analysis["combined_analysis"]["missing_elements"].extend([
                    f"Expanded SQL option: {sql}" for sql in expanded_sql_list
                ])

            # Extract required changes from correction
            if correction_data:
                if "corrected_sql" in correction_data and correction_data["corrected_sql"]:
                    combined_analysis["combined_analysis"]["required_changes"].extend([
                        f"Corrected SQL: {sql}" for sql in correction_data["corrected_sql"]
                    ])
                if "invalid_results" in correction_data and correction_data["invalid_results"]:
                    error_messages = [result.get("error", "Unknown error") for result in correction_data["invalid_results"]]
                    combined_analysis["combined_analysis"]["required_changes"].extend(error_messages)

            # Generate suggested improvements
            if expanded_sql_list or correction_data:
                combined_analysis["combined_analysis"]["suggested_improvements"] = [
                    f"Use expanded SQL: {sql}" for sql in expanded_sql_list
                ] + [
                    f"Apply correction: {change}" for change in combined_analysis["combined_analysis"]["required_changes"]
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
        sql: str,
        request: AskRequest,
        chart_config: Optional[Dict[str, Any]] = None,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """Generate SQL visualization with data, summary and chart generation
        
        Args:
            query_id: Unique identifier for the query
            query: The user's query
            sql: The SQL query
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
            sql_data_result = await self.generate_sql_data(
                query_id=query_id,
                sql=sql,
                query=query,
                project_id=request.project_id,
                configuration=request.configuration
            )

            if not sql_data_result.get("success"):
                return sql_data_result

            
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
                sql=sql,
                data=sql_data_result.get("data", {}),
                language=request.language,
                export_format=chart_config.get("export_format") if chart_config else None,
                **chart_config if chart_config else {}
            )

            # Combine all results
            combined_result = {
                "success": all([
                    sql_data_result.get("success", False),
                    chart_result.get("success", False)
                ]),
                "data": {
                    "sql_data": sql_data_result.get("data", {}),
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
                
                # Build comprehensive response data
                response_data = {
                    "executive_summary": post_process.get("executive_summary", ""),
                    "data_overview": post_process.get("data_overview", {}),
                    "visualization": post_process.get("visualization", {}),
                    "metadata": result.get("metadata", {}),
                    "sql_query": sql,  # Include the original SQL query
                    "query": query,  # Include the original user query
                    "project_id": project_id
                }
                
                # Add additional fields if available
                if "chart_schema" in post_process:
                    response_data["chart_schema"] = post_process["chart_schema"]
                if "reasoning" in post_process:
                    response_data["reasoning"] = post_process["reasoning"]
                if "data_count" in post_process:
                    response_data["data_count"] = post_process["data_count"]
                if "validation" in post_process:
                    response_data["validation_results"] = post_process["validation"]
                if "sample_data" in post_process:
                    response_data["sample_data"] = post_process["sample_data"]
                if "execution_config" in post_process:
                    response_data["execution_config"] = post_process["execution_config"]
                
                # Add chart format schemas if available
                if "plotly_schema" in post_process:
                    response_data["plotly_schema"] = post_process["plotly_schema"]
                if "powerbi_schema" in post_process:
                    response_data["powerbi_schema"] = post_process["powerbi_schema"]
                if "vega_lite_schema" in post_process:
                    response_data["vega_lite_schema"] = post_process["vega_lite_schema"]
                
                return {
                    "success": True,
                    "data": response_data,
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
                
                # Build comprehensive response data
                response_data = {
                    "executive_summary": post_process.get("executive_summary", ""),
                    "data_overview": post_process.get("data_overview", {}),
                    "visualization": post_process.get("visualization", {}),
                    "metadata": result.get("metadata", {}),
                    "sql_query": sql,  # Include the original SQL query
                    "query": query,  # Include the original user query
                    "project_id": project_id
                }
                
                # Add additional fields if available
                if "chart_schema" in post_process:
                    response_data["chart_schema"] = post_process["chart_schema"]
                if "reasoning" in post_process:
                    response_data["reasoning"] = post_process["reasoning"]
                if "data_count" in post_process:
                    response_data["data_count"] = post_process["data_count"]
                if "validation" in post_process:
                    response_data["validation_results"] = post_process["validation"]
                if "sample_data" in post_process:
                    response_data["sample_data"] = post_process["sample_data"]
                if "execution_config" in post_process:
                    response_data["execution_config"] = post_process["execution_config"]
                
                # Add chart format schemas if available
                if "plotly_schema" in post_process:
                    response_data["plotly_schema"] = post_process["plotly_schema"]
                if "powerbi_schema" in post_process:
                    response_data["powerbi_schema"] = post_process["powerbi_schema"]
                if "vega_lite_schema" in post_process:
                    response_data["vega_lite_schema"] = post_process["vega_lite_schema"]
                
                final_result = {
                    "status": "completed",
                    "data": response_data,
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

    async def generate_data_assistance(
        self,
        query_id: str,
        query: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        schema_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate data assistance using DataAssistance pipeline
        
        Args:
            query_id: Unique identifier for the query
            query: The user's query
            project_id: Project identifier
            configuration: Optional configuration parameters
            schema_context: Optional schema context
            
        Returns:
            Dict containing data assistance results including:
            - success: Whether the generation was successful
            - data: Results from the data assistance pipeline
            - error: Any error that occurred
        """
        if self._is_stopped(query_id):
            return {"success": False}

        try:
            # Get data assistance pipeline
            data_assistance_pipeline = self._pipeline_container.get_pipeline("data_assistance")
            if not data_assistance_pipeline:
                raise RuntimeError("Data assistance pipeline not found")

            # Update status
            self._update_cache_status(
                query_id,
                "understanding",
                AskResultResponse(
                    status="understanding",
                    type="GENERAL",
                    general_type="DATA_ASSISTANCE",
                    is_followup=False
                )
            )

            # Run data assistance pipeline
            result = await data_assistance_pipeline.run(
                query=query,
                project_id=project_id,
                schema_context=schema_context,
                configuration=configuration
            )

            # Process the result
            if result and result.get("success"):
                return {
                    "success": True,
                    "data": result.get("data", {}),
                    "metadata": result.get("metadata", {}),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to generate data assistance")
                }

        except Exception as e:
            logger.error(f"Error generating data assistance: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e)
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

    async def render_visualization(
        self,
        query_id: str,
        query: str,
        sql: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Render visualization by generating chart schema and executing it with full data
        
        This service combines chart generation and execution to provide a complete
        visualization solution. It first generates a chart schema using sample data,
        then executes the chart with the full dataset.
        
        Args:
            query_id: Unique identifier for the query
            query: The user's query
            sql: The SQL query to execute
            project_id: Project identifier
            configuration: Optional configuration parameters including:
                - chart_format: Chart format (vega_lite, plotly, powerbi)
                - include_other_formats: Whether to include other format conversions
                - use_multi_format: Whether to use multi-format chart generation
                - page_size: Page size for data pagination
                - max_rows: Maximum rows to process
                - enable_pagination: Whether to enable pagination
                - sort_by: Column to sort by
                - sort_order: Sort order (ASC/DESC)
                - timeout_seconds: Timeout for execution
                - cache_results: Whether to cache results
                - cache_ttl_seconds: Cache TTL in seconds
                - language: Language for chart generation
            status_callback: Optional callback function for status updates
            
        Returns:
            Dict containing visualization results including:
            - success: Whether the rendering was successful
            - data: Results including:
                - chart_schema: The executed chart schema with full data
                - chart_type: Type of chart generated
                - reasoning: Reasoning behind chart selection
                - chart_format: Format of the chart
                - data_count: Number of data points in the chart
                - validation: Validation results
                - execution_config: Configuration used for execution
                - sample_data: Sample data used for schema generation
                - plotly_schema: Plotly schema (if include_other_formats=True)
                - powerbi_schema: PowerBI schema (if include_other_formats=True)
                - vega_lite_schema: Vega-Lite schema (if include_other_formats=True)
            - error: Any error that occurred
        """
        if self._is_stopped(query_id):
            return {"success": False}

        try:
            # Update status for visualization rendering
            self._update_cache_status(
                query_id,
                "rendering_visualization",
                AskResultResponse(
                    status="rendering_visualization",
                    type="VISUALIZATION",
                    is_followup=False
                )
            )

            # Get chart execution pipeline
            chart_execution_pipeline = self._pipeline_container.get_pipeline("chart_execution")
            if not chart_execution_pipeline:
                raise RuntimeError("Chart execution pipeline not found")

            # Define status update function
            def send_status_update(status: str, details: Dict[str, Any] = None):
                """Send status update via callback if available"""
                if status_callback:
                    try:
                        status_callback(status, details or {})
                    except Exception as e:
                        logger.error(f"Error in status callback: {str(e)}")
                logger.info(f"Visualization Rendering Status - {status}: {details}")

            # Merge default configuration with provided configuration
            default_config = {
                "chart_format": "vega_lite",
                "include_other_formats": False,
                "use_multi_format": True,
                "page_size": 1000,
                "max_rows": 10000,
                "enable_pagination": True,
                "sort_by": None,
                "sort_order": "ASC",
                "timeout_seconds": 30,
                "cache_results": True,
                "cache_ttl_seconds": 300,
                "language": "English",
                "remove_data_from_chart_schema": True
            }
            
            if configuration:
                default_config.update(configuration)

            # Send initial status update
            send_status_update("started", {
                "project_id": project_id,
                "query": query,
                "sql": sql,
                "chart_format": default_config["chart_format"]
            })

            # Execute chart using the chart execution pipeline
            result = await chart_execution_pipeline.run(
                query=query,
                sql=sql,
                project_id=project_id,
                configuration=default_config,
                status_callback=send_status_update
            )

            # Process the result
            if result and result.get("post_process"):
                post_process = result["post_process"]
                
                # Prepare response
                response = {
                    "success": True,
                    "data": {
                        "chart_schema": post_process.get("chart_schema", {}),
                        "chart_type": post_process.get("chart_type", ""),
                        "reasoning": post_process.get("reasoning", ""),
                        "chart_format": post_process.get("chart_format", "vega_lite"),
                        "data_count": post_process.get("data_count", 0),
                        "validation": post_process.get("validation", {}),
                        "execution_config": post_process.get("execution_config", {}),
                        "sample_data": post_process.get("sample_data", {})
                    },
                    "metadata": result.get("metadata", {}),
                    "error": None
                }

                # Add other format schemas if available
                if "plotly_schema" in post_process:
                    response["data"]["plotly_schema"] = post_process["plotly_schema"]
                if "powerbi_schema" in post_process:
                    response["data"]["powerbi_schema"] = post_process["powerbi_schema"]
                if "vega_lite_schema" in post_process:
                    response["data"]["vega_lite_schema"] = post_process["vega_lite_schema"]

                # Send completion status update
                send_status_update("completed", {
                    "project_id": project_id,
                    "data_count": post_process.get("data_count", 0),
                    "chart_type": post_process.get("chart_type", ""),
                    "chart_format": post_process.get("chart_format", "vega_lite")
                })

                return response
            else:
                error_msg = "No data returned from chart execution pipeline"
                send_status_update("error", {"project_id": project_id, "error": error_msg})
                return {
                    "success": False,
                    "data": None,
                    "error": error_msg
                }

        except Exception as e:
            logger.error(f"Error rendering visualization: {e}")
            
            # Send error status update
            if status_callback:
                try:
                    status_callback("error", {"project_id": project_id, "error": str(e)})
                except Exception as callback_error:
                    logger.error(f"Error in status callback: {str(callback_error)}")
            
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    async def stream_visualization_rendering(
        self,
        query_id: str,
        query: str,
        sql: str,
        project_id: str,
        configuration: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream visualization rendering process with real-time updates
        
        Args:
            query_id: Unique identifier for the query
            query: The user's query
            sql: The SQL query to execute
            project_id: Project identifier
            configuration: Optional configuration parameters
            
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
            # Track streaming updates
            streaming_updates = []

            # Define status callback function for streaming
            def status_callback(status: str, details: Dict[str, Any] = None):
                """Status callback function that stores updates for streaming"""
                try:
                    # Update cache status
                    self._update_cache_status(
                        query_id,
                        status,
                        AskResultResponse(
                            status=status,
                            type="VISUALIZATION",
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
                    if status == "started":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "query": details.get("query"),
                            "chart_format": details.get("chart_format", "vega_lite")
                        }
                    elif status == "getting_sample_data":
                        update["data"] = {
                            "project_id": details.get("project_id")
                        }
                    elif status == "sample_data_ready":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "sample_size": details.get("sample_size", 0)
                        }
                    elif status == "generating_chart_schema":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "chart_format": details.get("chart_format", "vega_lite")
                        }
                    elif status == "chart_schema_ready":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "chart_type": details.get("chart_type", ""),
                            "chart_format": details.get("chart_format", "vega_lite")
                        }
                    elif status == "executing_chart":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "execution_config": details.get("execution_config", {})
                        }
                    elif status == "chart_execution_complete":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "data_count": details.get("data_count", 0),
                            "validation_success": details.get("validation_success", False)
                        }
                    elif status == "generating_other_formats":
                        update["data"] = {
                            "project_id": details.get("project_id")
                        }
                    elif status == "other_formats_ready":
                        update["data"] = {
                            "project_id": details.get("project_id")
                        }
                    elif status == "completed":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "data_count": details.get("data_count", 0),
                            "chart_type": details.get("chart_type", ""),
                            "chart_format": details.get("chart_format", "vega_lite")
                        }
                    elif status == "error":
                        update["data"] = {
                            "project_id": details.get("project_id"),
                            "error": details.get("error", "Unknown error")
                        }

                    # Store update for streaming
                    streaming_updates.append(update)

                except Exception as e:
                    logger.error(f"Error in status callback: {e}")

            # Call the render_visualization method with status callback
            result = await self.render_visualization(
                query_id=query_id,
                query=query,
                sql=sql,
                project_id=project_id,
                configuration=configuration,
                status_callback=status_callback
            )

            # Stream all status updates
            for update in streaming_updates:
                yield update

            # Stream final result
            if result.get("success"):
                final_result = {
                    "status": "completed",
                    "data": result.get("data", {}),
                    "metadata": result.get("metadata", {}),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                final_result = {
                    "status": "error",
                    "error": result.get("error", "Unknown error"),
                    "timestamp": datetime.now().isoformat()
                }

            yield final_result

        except Exception as e:
            logger.error(f"Error streaming visualization rendering: {e}")
            yield {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


