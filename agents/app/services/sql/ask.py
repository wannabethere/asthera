import asyncio
import logging
from typing import Dict, List, Literal, Optional, Any, AsyncGenerator, Callable
import json
from aiohttp import web
from aiohttp.web import Response
from aiohttp.web_request import Request
import pandas as pd
import numpy as np

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

logger = logging.getLogger("lexy-ai-service")

class PandasJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle pandas and numpy types"""
    def default(self, obj):
        if pd.isna(obj) or isinstance(obj, (pd.NaT, np.datetime64)):
            return None
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.float, np.float64)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        return super().default(obj)

class AskService(BaseService[AskRequest, AskResultResponse]):
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

    def _extract_quality_scoring(self, enhanced_result):
        """Extract quality scoring information from enhanced SQL result"""
        if not enhanced_result or not hasattr(enhanced_result, 'relevance_scoring'):
            return QualityScoring(
                final_score=0.0,
                quality_level="unknown",
                improvement_recommendations=[],
                processing_time_seconds=0.0
            )
            
        scoring = enhanced_result.relevance_scoring
        return QualityScoring(
            final_score=scoring.final_score,
            quality_level=scoring.quality_level,
            improvement_recommendations=scoring.improvement_recommendations,
            processing_time_seconds=scoring.processing_time_seconds
        )

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


    async def _run_ask_pipeline_steps(
        self,
        query_id: str,
        user_query: str,
        histories: list,
        request: AskRequest,
        stream_update: callable = None
    ) -> dict:
        """Optimized pipeline steps with unified data retrieval and shared context."""
        logger.info(f"Starting optimized ask pipeline steps for {query_id}")
        
        # Step 3: Retrieve relevant data (currently stub)
        retrieval_result = {}
        retrieval_result["success"] = True
        retrieval_result["data"] = {
            "table_names": [],
            "table_ddls": [],
            "has_calculated_field": False,
            "has_metric": False
        }
        if stream_update:
            await stream_update(query_id, "retrieving_data", {"query": user_query})

        # Step 4: Generate SQL
        if stream_update:
            await stream_update(query_id, "generating_sql", {"query": user_query})
        logger.info(f"Generating SQL for {query_id}")
        sql_result = await self._generate_sql(
            query_id, user_query, histories, request, retrieval_result["data"]
        )
        reasoning_result = None
        
        logger.info(f"SQL generation completed for {query_id}, success: {sql_result.get('success')}")
        print("sql_result in ask service", sql_result)
        # Step 5: Generate SQL data
        if stream_update:
            await stream_update(query_id, "generating_sql_data", {"query": user_query})
        logger.info(f"Generating SQL data for {query_id}")
        sql_data_result = await self._generate_sql_data(
            query_id, sql_result, retrieval_result["data"]
        )

        # Step 6: Generate SQL answer
        if stream_update:
            await stream_update(query_id, "generating_sql_answer", {"query": user_query})
        logger.info(f"Generating SQL answer for {query_id}")
        answer_result = await self._generate_sql_answer(
            query_id, sql_data_result, user_query, sql_result, request
        )
        logger.info(f"SQL answer generation completed for {query_id}, success: {answer_result.get('success')}")

        # Step 7: Process final results with answer
        if stream_update:
            await stream_update(query_id, "processing_results", {"query": user_query})
        logger.info(f"Processing final results for {query_id}")
        final_result = await self._process_final_results(
            query_id, sql_result, reasoning_result, retrieval_result["data"]
        )
        logger.info(f"Final results processed for {query_id}, status: {final_result.get('status')}")
        #print("final_result in ask service", answer_result)
        # Add answer to the final result
        if answer_result.get("success"):
            final_result["answer"] = answer_result.get("answer")
            final_result["explanation"] = answer_result.get("explanation")
            final_result["metadata"]["answer_metadata"] = answer_result.get("metadata", {})
            logger.info(f"Added answer to final result for {query_id}")
            logger.info(f"Answer added: {final_result.get('answer')}")
            logger.info(f"Explanation added: {final_result.get('explanation')}")

        # Include sql_data and answer_result in the metadata to preserve AskResultResponse structure
        final_result["metadata"]["sql_data"] = sql_data_result
        final_result["metadata"]["answer_result"] = answer_result

        logger.info(f"Returning final result for {query_id}, status: {final_result.get('status')}, api_results: {len(final_result.get('api_results', []))}")
        logger.info(f"Final result answer: {final_result.get('answer')}")
        logger.info(f"Final result explanation: {final_result.get('explanation')}")
        logger.info(f"Final result keys: {list(final_result.keys())}")
        logger.info(f"Final result full: {final_result}")
        return final_result



    async def _process_request_impl(self, request: AskRequest) -> Dict[str, Any]:
        """Implementation of request processing logic"""
        query_id = request.query_id
        histories = request.histories[: self._max_histories]
        user_query = request.query

        try:
            logger.info(f"Processing request for {query_id}: {user_query}")
            
            # Step 1: Check historical questions
            logger.info(f"Checking historical questions for {query_id}")
            historical_result = await self._check_historical_questions(query_id, user_query, request.project_id, histories)
            if historical_result:
                logger.info(f"Found historical result for {query_id}")
                return historical_result

            # Step 2: Process intent classification
            logger.info(f"Processing intent classification for {query_id}")
            intent_result = await self._process_intent_classification(query_id, user_query, histories, request)
            if intent_result:
                logger.info(f"Found intent result for {query_id}")
                return intent_result

            # Shared pipeline steps
            logger.info(f"Running pipeline steps for {query_id}")
            final_result = await self._run_ask_pipeline_steps(
                query_id, user_query, histories, request, stream_update=None
            )
            logger.info(f"Pipeline steps completed for {query_id}, status: {final_result.get('status')}")
            return final_result

        except Exception as e:
            logger.exception(f"ask pipeline - OTHERS: {e}")
            return self._handle_error(query_id, e, histories)

    async def _check_historical_questions(
        self, query_id: str, user_query: str, project_id: str, histories: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Check for historical questions and return results if found"""
        if self._is_stopped(query_id):
            return None

        self._update_cache_status(query_id, "understanding")

        historical_question = await self._pipeline_container.get_pipeline("historical_question").run(
            retrieval_type="historical_questions",
            query=user_query,
            project_id=project_id,
        )

        historical_question_result = historical_question.get(
            "formatted_output", {}
        ).get("documents", [])[:1]

        if historical_question_result:
            api_results = [
                AskResult(
                    **{
                        "sql": result.get("statement"),
                        "type": "view" if result.get("viewId") else "llm",
                        "viewId": result.get("viewId"),
                    }
                )
                for result in historical_question_result
            ]

            self._update_cache_status(
                query_id,
                "finished",
                AskResultResponse(
                    status="finished",
                    type="TEXT_TO_SQL",
                    response=api_results,
                    is_followup=True if histories else False,
                )
            )

            return {
                "ask_result": api_results,
                "metadata": {"type": "TEXT_TO_SQL"},
            }

        return None

    async def _process_intent_classification(
        self, query_id: str, user_query: str, histories: List[Dict], request: AskRequest
    ) -> Optional[Dict[str, Any]]:
        """Process intent classification and handle special intents"""
        if not self._allow_intent_classification:
            return None

        try:
            # Get intent classification pipeline
            intent_pipeline = self._pipeline_container.get_pipeline("intent_classification")
            if not intent_pipeline:
                logger.error("Intent classification pipeline not found")
                return None

            # Get SQL samples and instructions
            db_schemas, sql_samples_task, instructions_task = await asyncio.gather(
                self._pipeline_container.get_pipeline("database_schemas").run(
                    retrieval_type="database_schemas",
                    query=user_query,
                    project_id=request.project_id
                ),
                self._pipeline_container.get_pipeline("sql_pairs").run(
                    retrieval_type="sql_pairs",
                    query=user_query,
                    project_id=request.project_id,
                ),
                self._pipeline_container.get_pipeline("instructions").run(
                    retrieval_type="instructions",
                    query=user_query,
                    project_id=request.project_id,
                ),
            )

            sql_samples = sql_samples_task["formatted_output"].get("documents", [])
            instructions = instructions_task["formatted_output"].get("documents", [])
            
            # Convert configuration to dict if it exists
            config_dict = request.configurations.dict() if request.configurations else {}
            
            # Run intent classification
            intent_classification_result = (
                await intent_pipeline.run(
                    query=user_query,
                    histories=histories,
                    sql_samples=sql_samples,
                    instructions=instructions,
                    project_id=request.project_id,
                    configuration=config_dict,
                )
            )
            
            
            intent = intent_classification_result.get("intent")
            rephrased_question = intent_classification_result.get("rephrased_question")
            intent_reasoning = intent_classification_result.get("reasoning")

            if rephrased_question:
                user_query = rephrased_question
            print("intent in ask service", intent_classification_result, intent, rephrased_question, intent_reasoning)
            # Handle different intents
            if intent == "MISLEADING_QUERY":
                return await self._handle_misleading_query(
                    query_id, user_query, histories, request, db_schemas, rephrased_question, intent_reasoning
                )
            elif intent == "GENERAL":
                return await self._handle_general_query(
                    query_id, user_query, histories, request, db_schemas, rephrased_question, intent_reasoning
                )
            elif intent == "USER_GUIDE":
                return await self._handle_user_guide(
                    query_id, user_query, request, rephrased_question, intent_reasoning
                )
            elif intent == "ANALYSIS_HELPER":
                return await self._handle_analysis_helper(
                    query_id, user_query, histories, request, db_schemas, rephrased_question, intent_reasoning
                )
            elif intent == "QUESTION_SUGGESTION":
                return await self._handle_question_suggestion(
                    query_id, user_query, histories, request, db_schemas, rephrased_question, intent_reasoning
                )

            return None

        except Exception as e:
            logger.error(f"Error in intent classification: {e}")
            return None

    async def _retrieve_relevant_data(
        self, query_id: str, user_query: str, histories: List[Dict], request: AskRequest
    ) -> Dict[str, Any]:
        """Retrieve relevant data for SQL generation"""
        if self._is_stopped(query_id):
            return {"success": False, "results": None}

        # Serialize histories if they contain AskHistory objects
        serialized_histories = []
        for history in histories:
            if hasattr(history, 'dict'):  # Check if it's a Pydantic model
                serialized_histories.append(history.dict())
            else:
                serialized_histories.append(history)

        self._update_cache_status(
            query_id,
            "searching",
            AskResultResponse(
                status="searching",
                type="TEXT_TO_SQL",
                is_followup=True if histories else False,
            )
        )

        logger.info(f"DEBUG: About to call database_schemas pipeline with project_id: {request.project_id}")
        logger.info(f"DEBUG: request.project_id type: {type(request.project_id)}")
        logger.info(f"DEBUG: request.project_id value: {repr(request.project_id)}")
        
        retrieval_result = await self._pipeline_container.get_pipeline("database_schemas").run(
            retrieval_type="database_schemas",
            query=user_query,
            histories=serialized_histories,
            project_id=request.project_id,
        )

        _retrieval_result = retrieval_result.get("formatted_output", {})
        logger.info("Table retrieval result: ", _retrieval_result)
        
        # Process schema results from RetrievalHelper
        schemas = retrieval_result.get("metadata", {}).get("schemas", [])
        table_names = [schema.get("table_name") for schema in schemas]
        table_ddls = [schema.get("table_ddl") for schema in schemas]
        
        if not schemas:
            logger.exception(f"ask pipeline - NO_RELEVANT_DATA: {user_query}")
            if not self._is_stopped(query_id):
                self._update_cache_status(
                    query_id,
                    "failed",
                    AskResultResponse(
                        status="failed",
                        type="TEXT_TO_SQL",
                        error=AskError(
                            code="NO_RELEVANT_DATA",
                            message="No relevant data",
                        ),
                        is_followup=True if histories else False,
                    )
                )
            return {
                "success": False,
                "results": {
                    "metadata": {
                        "error_type": "NO_RELEVANT_DATA",
                        "type": "TEXT_TO_SQL",
                    }
                },
            }

        return {
            "success": True,
            "data": {
                "table_names": table_names,
                "table_ddls": table_ddls,
                "has_calculated_field": _retrieval_result.get("has_calculated_field", False),
                "has_metric": _retrieval_result.get("has_metric", False),
            },
        }

    async def _generate_sql_reasoning(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        retrieval_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate SQL reasoning based on the query and retrieved data"""
        if (
            not self._is_stopped(query_id)
            and self._allow_sql_generation_reasoning
        ):
            self._update_cache_status(
                query_id,
                "planning",
                AskResultResponse(
                    status="planning",
                    type="TEXT_TO_SQL",
                    retrieved_tables=retrieval_data["table_names"],
                    is_followup=True if histories else False,
                )
            )

            # Convert configuration to dict
            config_dict = request.configurations.dict() if request.configurations else {}

            if histories:
                sql_generation_reasoning = (
                    await self._pipeline_container.get_pipeline("followup_sql_reasoning").run(
                        query=user_query,
                        contexts=retrieval_data["table_ddls"],
                        histories=histories,
                        configuration=config_dict,
                        query_id=query_id,
                    )
                )
            else:
                sql_generation_reasoning = (
                    await self._pipeline_container.get_pipeline("sql_reasoning").run(
                        query=user_query,
                        contexts=retrieval_data["table_ddls"],
                        configuration=config_dict,
                        query_id=query_id,
                    )
                )

            print("sql_generation_reasoning in ask generate sql reasoning", sql_generation_reasoning)
            # Extract the content from the reasoning result
            reasoning_content = sql_generation_reasoning.get("data", {}).get("reasoning", "")

            self._update_cache_status(
                query_id,
                "planning",
                AskResultResponse(
                    status="planning",
                    type="TEXT_TO_SQL",
                    retrieved_tables=retrieval_data["table_names"],
                    sql_generation_reasoning=reasoning_content,
                    is_followup=True if histories else False,
                )
            )

            return sql_generation_reasoning

        return {}

    async def _generate_sql(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        retrieval_data: Dict[str, Any],
        reasoning_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate SQL based on the query, retrieved data, and reasoning"""
        if self._is_stopped(query_id):
            return {"success": False}

        self._update_cache_status(
            query_id,
            "generating",
            AskResultResponse(
                status="generating",
                type="TEXT_TO_SQL",
                retrieved_tables=retrieval_data["table_names"],
                sql_generation_reasoning=reasoning_result,
                is_followup=True if histories else False,
            )
        )

        # Get SQL functions if available, otherwise use empty dict
        try:
            sql_functions = await self._pipeline_container.get_pipeline("sql_functions").run(
                project_id=request.project_id,
            )
        except KeyError:
            logger.warning("SQL functions pipeline not found, proceeding without project-specific SQL functions")
            sql_functions = {}

        if self._enable_enhanced_sql and self._enhanced_sql_system and request.enable_scoring:
            result = await self._generate_enhanced_sql(
                query_id, user_query, histories, request, retrieval_data, reasoning_result, sql_functions
            )
            #print("result in ask generate enhanced sql", result)
            return result
        else:
            result = await self._generate_standard_sql(
                query_id, user_query, histories, request, retrieval_data, reasoning_result, sql_functions
            )
            #print("result in ask generate standard sql", result)
            return result

    async def _generate_enhanced_sql(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        retrieval_data: Dict[str, Any],
        reasoning_result: Optional[Dict[str, Any]] = None,
        sql_functions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate SQL using enhanced pipeline with scoring"""
        try:
            schema_context = {
                "tables": {
                    table_name: {"ddl": ddl}
                    for table_name, ddl in zip(retrieval_data["table_names"], retrieval_data["table_ddls"])
                    if table_name
                }
            }

            # Create pipeline request
            pipeline_request = PipelineRequest(
                pipeline_type=PipelineType.SQL_GENERATION,
                query=user_query,
                language=request.configurations.language if request.configurations else "English",
                contexts=retrieval_data["table_ddls"],
                project_id=request.project_id,
                enable_scoring=True,
                quality_threshold=0.6,
                schema_context=schema_context,
                max_improvement_attempts=3,
                additional_params={
                    "sql_generation_reasoning": reasoning_result,
                    "histories": histories,
                    "has_calculated_field": retrieval_data["has_calculated_field"],
                    "has_metric": retrieval_data["has_metric"],
                    "sql_functions": sql_functions,
                }
            )

            # Execute using unified system
            enhanced_result = await self._enhanced_sql_system.execute_pipeline(pipeline_request)
            
            #print("enhanced_result in ask service", enhanced_result)
            if enhanced_result.success and enhanced_result.data:
                # Extract all relevant data from the enhanced result
                result_data = enhanced_result.data
                sql = result_data.get("sql", "")
                parsed_entities = result_data.get("parsed_entities", {})

                reasoning = result_data.get("reasoning", "")
                operation_type = result_data.get("operation_type", "generation")
                
                # Create the response with all available data
                return {
                    "success": True,
                    "api_results": [
                        AskResult(
                            **{
                                "sql": sql,
                                "type": "llm",
                            }
                        )
                    ],
                    "quality_scoring": self._extract_quality_scoring(enhanced_result),
                    "metadata": {
                        "operation_type": operation_type,
                        "reasoning": reasoning,
                        "processing_time_seconds": enhanced_result.relevance_scoring.processing_time_seconds,
                        "timestamp": enhanced_result.timestamp,
                        "parsed_entities": parsed_entities
                    }
                }
            else:
                logger.error(f"Enhanced SQL generation failed: {enhanced_result.error}")
                return {
                    "success": False,
                    "error_message": enhanced_result.error or "Failed to generate SQL with enhanced pipeline",
                    "invalid_sql": enhanced_result.data.get("invalid_sql") if enhanced_result.data else None,
                }
        except Exception as e:
            logger.error(f"Error in enhanced SQL generation: {e}")
            return {
                "success": False,
                "error_message": f"Error in enhanced SQL generation: {str(e)}",
            }

    async def _generate_standard_sql(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        retrieval_data: Dict[str, Any],
        reasoning_result: Optional[Dict[str, Any]] = None,
        sql_functions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate SQL using standard pipeline"""
        # Convert configuration to dict
        config_dict = request.configurations.dict() if request.configurations else {}

        if histories:
            text_to_sql_generation_results = await self._pipeline_container.get_pipeline("followup_sql_generation").run(
                query=user_query,
                contexts=retrieval_data["table_ddls"],
                sql_generation_reasoning=reasoning_result,
                histories=histories,
                project_id=request.project_id,
                configuration=config_dict,
                has_calculated_field=retrieval_data["has_calculated_field"],
                has_metric=retrieval_data["has_metric"],
                sql_functions=sql_functions,
            )
        else:
            text_to_sql_generation_results = await self._pipeline_container.get_pipeline("sql_generation").run(
                query=user_query,
                contexts=retrieval_data["table_ddls"],
                sql_generation_reasoning=reasoning_result,
                project_id=request.project_id,
                configuration=config_dict,
                has_calculated_field=retrieval_data["has_calculated_field"],
                has_metric=retrieval_data["has_metric"],
                sql_functions=sql_functions,
            )
       
        if sql_valid_results := text_to_sql_generation_results["post_process"][
            "valid_generation_results"
        ]:
            # Extract parsed entities from the first valid result
            parsed_entities = sql_valid_results[0].get("parsed_entities", {})
            
            return {
                "success": True,
                "api_results": [
                    AskResult(
                        **{
                            "sql": result.get("sql"),
                            "type": "llm",
                            "metadata": {
                                "operation_type": "generation",
                                "reasoning": reasoning_result.get("reasoning", "") if reasoning_result else "",
                                "processing_time_seconds": text_to_sql_generation_results.get("processing_time_seconds", 0.0),
                                "timestamp": text_to_sql_generation_results.get("timestamp", ""),
                                "parsed_entities": parsed_entities
                            }
                        }
                    )
                    for result in sql_valid_results
                ][:1],
            }
        elif failed_dry_run_results := text_to_sql_generation_results[
            "post_process"
        ]["invalid_generation_results"]:
            if failed_dry_run_results[0]["type"] != "TIME_OUT":
                return await self._handle_sql_correction(
                    query_id, user_query, request, retrieval_data, failed_dry_run_results
                )
            else:
                return {
                    "success": False,
                    "error_message": failed_dry_run_results[0]["error"],
                    "invalid_sql": failed_dry_run_results[0]["sql"],
                }

        return {"success": False}

    async def _handle_sql_correction(
        self,
        query_id: str,
        user_query: str,
        request: AskRequest,
        retrieval_data: Dict[str, Any],
        failed_dry_run_results: List[Dict],
    ) -> Dict[str, Any]:
        """Handle SQL correction for failed generations"""
        self._update_cache_status(
            query_id,
            "correcting",
            AskResultResponse(
                status="correcting",
                type="TEXT_TO_SQL",
                retrieved_tables=retrieval_data["table_names"],
                is_followup=True if request.histories else False,
            )
        )

        if self._enable_enhanced_sql and self._enhanced_sql_system and request.enable_scoring:
            return await self._handle_enhanced_sql_correction(
                query_id, user_query, request, retrieval_data, failed_dry_run_results
            )
        else:
            return await self._handle_standard_sql_correction(
                query_id, request, retrieval_data, failed_dry_run_results
            )

    async def _handle_standard_sql_correction(
        self,
        query_id: str,
        request: AskRequest,
        retrieval_data: Dict[str, Any],
        failed_dry_run_results: List[Dict],
    ) -> Dict[str, Any]:
        """Handle SQL correction using standard pipeline"""
        # Convert configuration to dict
        config_dict = request.configurations.dict() if request.configurations else {}

        sql_correction_results = await self._pipeline_container.get_pipeline("sql_correction").run(
            contexts=[],
            invalid_generation_results=failed_dry_run_results,
            project_id=request.project_id,
            configuration=config_dict,
        )

        if valid_generation_results := sql_correction_results[
            "post_process"
        ]["valid_generation_results"]:
            return {
                "success": True,
                "api_results": [
                    AskResult(
                        **{
                            "sql": valid_generation_result.get("sql"),
                            "type": "llm",
                        }
                    )
                    for valid_generation_result in valid_generation_results
                ][:1],
            }
        elif failed_dry_run_results := sql_correction_results[
            "post_process"
        ]["invalid_generation_results"]:
            return {
                "success": False,
                "error_message": failed_dry_run_results[0]["error"],
                "invalid_sql": failed_dry_run_results[0]["sql"],
            }

        return {"success": False}

    async def _process_final_results(
        self,
        query_id: str,
        sql_result: Dict[str, Any],
        reasoning_result: Optional[Dict[str, Any]] = {},
        retrieval_data: Optional[Dict[str, Any]] = {},
    ) -> Dict[str, Any]:
        """Process and format the final results from SQL generation and reasoning.
        
        Args:
            query_id: The ID of the query
            sql_result: The SQL generation result
            reasoning_result: The reasoning result (can be None)
            retrieval_data: Additional retrieval data
            
        Returns:
            Formatted results dictionary
        """
       
        
        # Extract quality scoring from sql_result
        quality_scoring = sql_result.get('quality_scoring', {})
        
        # Create AskResult with quality scoring
        ask_results = []
        for api_result in sql_result.get('api_results', []):
            # Handle both dict and AskResult objects
            if isinstance(api_result, dict):
                ask_result = AskResult(
                    sql=api_result.get('sql', ''),
                    type=api_result.get('type', 'llm'),
                    viewId=api_result.get('viewId'),
                    reasoning=api_result.get('metadata', {}).get('reasoning', '').get('content', ''),
                    quality_scoring=quality_scoring
                )
            else:
                # If it's already an AskResult, just add quality scoring
                ask_result = AskResult(
                    sql=api_result.sql,
                    type=api_result.type,
                    viewId=api_result.viewId,
                    reasoning=api_result.reasoning if hasattr(api_result, 'reasoning') else '',
                    quality_scoring=quality_scoring
                )
            ask_results.append(ask_result)
            
        return {
            'status': 'finished',  # Add required status field
            'success': sql_result.get('success', False),
            'api_results': ask_results,
            'quality_scoring': quality_scoring,
            'metadata': sql_result.get('metadata', {}),
            'processing_time_seconds': sql_result.get('processing_time_seconds', 0.0),
            'timestamp': sql_result.get('timestamp', ''),
            'answer': sql_result.get('answer', ''),  # Use existing answer if available
            'explanation': sql_result.get('explanation', '')  # Use existing explanation if available
        }

    def _handle_error(self, query_id: str, error: Exception, histories: List[Dict]) -> Dict[str, Any]:
        """Handle errors in request processing"""
        self._update_cache_status(
            query_id,
            "failed",
            AskResultResponse(
                status="failed",
                type="TEXT_TO_SQL",
                error=AskError(
                    code="OTHERS",
                    message=str(error),
                ),
                is_followup=True if histories else False,
            )
        )

        return {
            "metadata": {
                "error_type": "OTHERS",
                "error_message": str(error),
                "type": "TEXT_TO_SQL",
            }
        }

    async def _handle_misleading_query(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        db_schemas: Dict[str, Any],
        rephrased_question: str,
        intent_reasoning: str,
    ) -> Dict[str, Any]:
        """Handle misleading query intent"""
       
        result = await self._pipeline_container.get_pipeline("misleading_assistance").run(
            query=user_query,
            histories=histories,
            db_schemas=db_schemas,
            language=request.configurations.language,
            query_id=request.query_id,
        )
        print("misleading query result", result)

        self._update_cache_status(
            query_id,
            "finished",
            AskResultResponse(
                status="finished",
                type="GENERAL",
                rephrased_question=rephrased_question,
                intent_reasoning=intent_reasoning,
                is_followup=True if histories else False,
                general_type="MISLEADING_QUERY",
            )
        )

        return {
            "metadata": {"type": "MISLEADING_QUERY",
                         "assistance": result.get("data", {}).get("assistance", "")
                         },
        }

    async def _handle_general_query(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        db_schemas: Dict[str, Any],
        rephrased_question: str,
        intent_reasoning: str,
    ) -> Dict[str, Any]:
        """Handle general query intent"""
        try:
            # Run data assistance pipeline
            result = await self._pipeline_container.get_pipeline("data_assistance").run(
                query=user_query,
                histories=histories,
                db_schemas=db_schemas,
                language=request.configurations.language,
                query_id=request.query_id,
            )
            logger.info(f"general query handling result I am here {result}")
            # Parse the content if it's a JSON string
            self._update_cache_status(
                query_id,
                "finished",
                AskResultResponse(
                    status="finished",
                    type="GENERAL",
                    rephrased_question=rephrased_question,
                    intent_reasoning=intent_reasoning,
                    is_followup=True if histories else False,
                    general_type="DATA_ASSISTANCE",
                    metadata={"type": "GENERAL", "data": result.get("data", {})}
                )
            )

            return {
                "status": "finished",
                "type": "GENERAL",
                "rephrased_question": rephrased_question,
                "intent_reasoning": intent_reasoning,
                "is_followup": True if histories else False,
                "metadata": {"type": "GENERAL","data": result.get("data", {})}
            }
        except Exception as e:
            logger.error(f"Error in general query handling: {e}")
            return {
                "metadata": {"type": "GENERAL", "error": str(e)},
                "data": {
                    "questions": [],
                    "reasoning": [intent_reasoning] if intent_reasoning else [],
                    "categories": []
                }
            }

    async def _handle_user_guide(
        self,
        query_id: str,
        user_query: str,
        request: AskRequest,
        rephrased_question: str,
        intent_reasoning: str,
    ) -> Dict[str, Any]:
        """Handle user guide intent"""
        asyncio.create_task(
            self._pipeline_container.get_pipeline("user_guide").run(
                query=user_query,
                language=request.configurations.language,
                query_id=request.query_id,
            )
        )

        self._update_cache_status(
            query_id,
            "finished",
            AskResultResponse(
                status="finished",
                type="GENERAL",
                rephrased_question=rephrased_question,
                intent_reasoning=intent_reasoning,
                is_followup=True if request.histories else False,
                general_type="USER_GUIDE",
            )
        )

        return {
            "metadata": {"type": "GENERAL"},
        }

    async def _handle_analysis_helper(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        db_schemas: Dict[str, Any],
        rephrased_question: str,
        intent_reasoning: str,
    ) -> Dict[str, Any]:
        """Handle analysis helper intent"""
        try:
            # Run analysis assistance pipeline
            result = await self._pipeline_container.get_pipeline("analysis_assistance").run(
                query=user_query,
                histories=histories,
                db_schemas=db_schemas,
                language=request.configurations.language,
                query_id=request.query_id,
            )
            logger.info(f"analysis helper handling result: {result}")
            
            self._update_cache_status(
                query_id,
                "finished",
                AskResultResponse(
                    status="finished",
                    type="GENERAL",
                    rephrased_question=rephrased_question,
                    intent_reasoning=intent_reasoning,
                    is_followup=True if histories else False,
                    general_type="ANALYSIS_HELPER",
                    metadata={"type": "GENERAL", "data": result.get("data", {})}
                )
            )

            return {
                "status": "finished",
                "type": "GENERAL",
                "rephrased_question": rephrased_question,
                "intent_reasoning": intent_reasoning,
                "is_followup": True if histories else False,
                "metadata": {"type": "GENERAL", "data": result.get("data", {})}
            }
        except Exception as e:
            logger.error(f"Error in analysis helper handling: {e}")
            return {
                "metadata": {"type": "GENERAL", "error": str(e)},
                "data": {
                    "analysis_suggestions": [],
                    "reasoning": [intent_reasoning] if intent_reasoning else [],
                    "metrics": []
                }
            }

    async def _handle_question_suggestion(
        self,
        query_id: str,
        user_query: str,
        histories: List[Dict],
        request: AskRequest,
        db_schemas: Dict[str, Any],
        rephrased_question: str,
        intent_reasoning: str,
    ) -> Dict[str, Any]:
        """Handle question suggestion intent"""
        try:
            # Run question suggestion pipeline
            result = await self._pipeline_container.get_pipeline("question_suggestion").run(
                query=user_query,
                histories=histories,
                db_schemas=db_schemas,
                language=request.configurations.language,
                query_id=request.query_id,
            )
            logger.info(f"question suggestion handling result: {result}")
            
            self._update_cache_status(
                query_id,
                "finished",
                AskResultResponse(
                    status="finished",
                    type="GENERAL",
                    rephrased_question=rephrased_question,
                    intent_reasoning=intent_reasoning,
                    is_followup=True if histories else False,
                    general_type="QUESTION_SUGGESTION",
                    metadata={"type": "GENERAL", "data": result.get("data", {})}
                )
            )

            return {
                "status": "finished",
                "type": "GENERAL",
                "rephrased_question": rephrased_question,
                "intent_reasoning": intent_reasoning,
                "is_followup": True if histories else False,
                "metadata": {"type": "GENERAL", "data": result.get("data", {})}
            }
        except Exception as e:
            logger.error(f"Error in question suggestion handling: {e}")
            return {
                "metadata": {"type": "GENERAL", "error": str(e)},
                "data": {
                    "suggested_questions": [],
                    "reasoning": [intent_reasoning] if intent_reasoning else [],
                    "categories": []
                }
            }

    def _convert_to_ask_result_response(self, result: Dict[str, Any]) -> AskResultResponse:
        """Convert a result dictionary to AskResultResponse format"""
        try:
            # Handle different result types
            if result.get("status") == "finished":
                # Check if this is a SQL result (has api_results) or general result
                if result.get("api_results") is not None:
                    # Handle SQL results - this is the main case for our pipeline
                    api_results = result.get("api_results", [])
                    quality_scoring = result.get("quality_scoring")
                    
                    # Convert QualityScoring object to dict if it exists
                    quality_scoring_dict = None
                    if quality_scoring:
                        if hasattr(quality_scoring, 'dict'):
                            quality_scoring_dict = quality_scoring.dict()
                        elif isinstance(quality_scoring, dict):
                            quality_scoring_dict = quality_scoring
                        else:
                            quality_scoring_dict = quality_scoring
                    
                    metadata = result.get("metadata", {})
                    logger.info(f"DEBUG: metadata in _convert_to_ask_result_response: {metadata}")
                    ask_result = AskResultResponse(
                        status="finished",
                        type="TEXT_TO_SQL",
                        response=api_results,
                        quality_scoring=quality_scoring_dict,
                        is_followup=result.get("is_followup", False),
                        retrieved_tables=result.get("retrieved_tables"),
                        sql_generation_reasoning=result.get("sql_generation_reasoning") or result.get("metadata", {}).get("reasoning"),
                        metadata=metadata,
                        answer=result.get("answer", ""),
                        explanation=result.get("explanation", "")
                    )
                    logger.info(f"DEBUG: ask_result.metadata after creation: {ask_result.metadata}")
                    return ask_result
                elif result.get("type") == "GENERAL":
                    # Handle general results
                    return AskResultResponse(
                        status="finished",
                        type="GENERAL",
                        rephrased_question=result.get("rephrased_question"),
                        intent_reasoning=result.get("intent_reasoning"),
                        is_followup=result.get("is_followup", False),
                        general_type=result.get("general_type"),
                        metadata=result.get("metadata", {}),
                        answer=result.get("answer", ""),
                        explanation=result.get("explanation", "")
                    )
                else:
                    # Handle other finished results - default to TEXT_TO_SQL
                    return AskResultResponse(
                        status="finished",
                        type="TEXT_TO_SQL",
                        response=result.get("api_results", []),
                        is_followup=result.get("is_followup", False),
                        metadata=result.get("metadata", {}),
                        answer=result.get("answer", ""),
                        explanation=result.get("explanation", "")
                    )
            elif result.get("status") == "failed":
                # Handle failed results
                return AskResultResponse(
                    status="failed",
                    type="TEXT_TO_SQL",  # Default to TEXT_TO_SQL for failed results
                    error=AskError(
                        code=result.get("error_type", "OTHERS"),
                        message=result.get("error_message", "Unknown error")
                    ),
                    is_followup=result.get("is_followup", False)
                )
            else:
                # Handle other statuses - ensure we use valid status values
                status = result.get("status", "finished")
                # Map invalid statuses to valid ones
                if status not in ["understanding", "searching", "planning", "generating", "correcting", "finished", "failed", "stopped", "summarizing", "reasoning", "executing_sql", "generating_answer", "generating_summary"]:
                    status = "finished"  # Default to finished for invalid statuses
                
                return AskResultResponse(
                    status=status,
                    type="TEXT_TO_SQL",  # Default to TEXT_TO_SQL for unknown types
                    is_followup=result.get("is_followup", False),
                    metadata=result.get("metadata", {})
                )
        except Exception as e:
            logger.error(f"Error converting result to AskResultResponse: {e}")
            return AskResultResponse(
                status="failed",
                error=AskError(
                    code="OTHERS",  # Use valid error code
                    message=f"Error converting result: {str(e)}"
                )
            )

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> AskResultResponse:
        """Create a response object from the processing result"""
        # Use the provided result directly instead of checking cache
        # This ensures we return the fresh result even if there are cache issues
        print(f"DEBUG: result in _create_response: {result}")
        if result and isinstance(result, dict):
            # Convert the dictionary result to AskResultResponse using the existing method
            return self._convert_to_ask_result_response(result)
        
        # Fallback to cache if result is not in expected format
        cached_result = self._results_cache.get(event_id)
        if not cached_result:
            logger.warning(f"Cache miss for event_id: {event_id}")
            return AskResultResponse(
                status="failed",
                error=AskError(
                    code="OTHERS",
                    message="Result not found in cache"
                )
            )
        return cached_result.get("result")

    def stop_ask(self, stop_ask_request: StopAskRequest):
        """Stop processing of an ask request"""
        self.stop_request(stop_ask_request.query_id)

    def get_ask_result(self, ask_result_request: AskResultRequest) -> AskResultResponse:
        """Get the result of an ask request"""
        return self.get_request_status(ask_result_request.query_id).get("result")

    async def get_ask_streaming_result(self, query_id: str):
        """Get streaming results for an ask request"""
        if result := self._results_cache.get(query_id):
            _pipeline_name = ""
            if result.get("result", {}).get("type") == "GENERAL":
                if result.get("result", {}).get("general_type") == "USER_GUIDE":
                    _pipeline_name = "user_guide_assistance"
                elif result.get("result", {}).get("general_type") == "DATA_ASSISTANCE":
                    _pipeline_name = "data_assistance"
                elif result.get("result", {}).get("general_type") == "MISLEADING_QUERY":
                    _pipeline_name = "misleading_assistance"
                elif result.get("result", {}).get("general_type") == "ANALYSIS_HELPER":
                    _pipeline_name = "analysis_assistance"
                elif result.get("result", {}).get("general_type") == "QUESTION_SUGGESTION":
                    _pipeline_name = "question_suggestion"
            elif result.get("result", {}).get("status") == "planning":
                if result.get("result", {}).get("is_followup"):
                    _pipeline_name = "followup_sql_generation_reasoning"
                else:
                    _pipeline_name = "sql_generation_reasoning"

            if _pipeline_name:
                async for chunk in self._pipeline_container.get_pipeline(_pipeline_name).get_streaming_results(query_id):
                    event = SSEEvent(
                        data=SSEEvent.SSEEventMessage(message=chunk),
                    )
                    yield event.serialize()

    @observe(name="Ask Feedback")
    async def ask_feedback(self, ask_feedback_request: AskFeedbackRequest, **kwargs):
        """Process an ask feedback request"""
        results = {
            "ask_feedback_result": {},
            "metadata": {
                "error_type": "",
                "error_message": "",
                "enhanced_sql_used": self._enable_enhanced_sql and ask_feedback_request.enable_scoring,
            },
        }

        query_id = ask_feedback_request.query_id
        api_results = []
        error_message = ""
        quality_scoring = None

        try:
            if not self._is_stopped(query_id):
                self._update_cache_status(
                    query_id,
                    "searching",
                    AskFeedbackResultResponse(
                        status="searching",
                    )
                )

                retrieval_result = await self._pipeline_container.get_pipeline("table").run(
                    tables=ask_feedback_request.tables,
                    project_id=ask_feedback_request.project_id,
                )
                _retrieval_result = retrieval_result.get(
                    "construct_retrieval_results", {}
                )
                documents = _retrieval_result.get("retrieval_results", [])
                table_ddls = [document.get("table_ddl") for document in documents]
                table_names = [document.get("table_name") for document in documents]

            if not self._is_stopped(query_id):
                self._update_cache_status(
                    query_id,
                    "generating",
                    AskFeedbackResultResponse(
                        status="generating",
                    )
                )

                # Check if enhanced SQL pipeline should be used
                if self._enable_enhanced_sql and self._enhanced_sql_system and ask_feedback_request.enable_scoring:
                    # Create enhanced pipeline request
                    schema_context = {
                        "tables": {table_name: {"ddl": ddl} for table_name, ddl in zip(table_names, table_ddls) if table_name}
                    }
                    
                    correction_request = PipelineRequest(
                        pipeline_type=PipelineType.SQL_CORRECTION,
                        query="", # No query needed for regeneration
                        language=ask_feedback_request.configurations.language,
                        contexts=table_ddls,
                        project_id=ask_feedback_request.project_id,
                        enable_scoring=True,
                        schema_context=schema_context,
                        additional_params={
                            "sql": ask_feedback_request.sql,
                            "sql_generation_reasoning": ask_feedback_request.sql_generation_reasoning,
                            "regenerate": True
                        }
                    )
                    
                    enhanced_result = await self._enhanced_sql_system.execute_pipeline(correction_request)
                    
                    if enhanced_result.success and enhanced_result.data:
                        api_results = [
                            AskResult(
                                **{
                                    "sql": enhanced_result.data.get("sql", ""),
                                    "type": "llm",
                                }
                            )
                        ]
                        # Extract quality scoring
                        quality_scoring = self._extract_quality_scoring(enhanced_result)
                    else:
                        error_message = enhanced_result.error or "Failed to regenerate SQL with enhanced pipeline"
                    
                else:
                    # Use standard regeneration
                    text_to_sql_generation_results = await self._pipeline_container.get_pipeline("sql_generation").run(
                        contexts=table_ddls,
                        sql_generation_reasoning=ask_feedback_request.sql_generation_reasoning,
                        sql=ask_feedback_request.sql,
                        project_id=ask_feedback_request.project_id,
                        configuration=ask_feedback_request.configurations,
                    )

                    if sql_valid_results := text_to_sql_generation_results["post_process"][
                        "valid_generation_results"
                    ]:
                        api_results = [
                            AskResult(
                                **{
                                    "sql": result.get("sql"),
                                    "type": "llm",
                                }
                            )
                            for result in sql_valid_results
                        ][:1]
                    elif failed_dry_run_results := text_to_sql_generation_results[
                        "post_process"
                    ]["invalid_generation_results"]:
                        if failed_dry_run_results[0]["type"] != "TIME_OUT":
                            self._update_cache_status(
                                query_id,
                                "correcting",
                                AskFeedbackResultResponse(
                                    status="correcting",
                                )
                            )
                            
                            # Try enhanced correction if enabled
                            if self._enable_enhanced_sql and self._enhanced_sql_system and ask_feedback_request.enable_scoring:
                                correction_request = PipelineRequest(
                                    pipeline_type=PipelineType.SQL_CORRECTION,
                                    query="",
                                    language=ask_feedback_request.configurations.language,
                                    contexts=table_ddls,
                                    project_id=ask_feedback_request.project_id,
                                    enable_scoring=True,
                                    schema_context={
                                        "tables": {table_name: {"ddl": ddl} for table_name, ddl in zip(table_names, table_ddls) if table_name}
                                    },
                                    additional_params={
                                        "sql": failed_dry_run_results[0]["sql"],
                                        "error_message": failed_dry_run_results[0]["error"],
                                    }
                                )
                                
                                enhanced_correction = await self._enhanced_sql_system.execute_pipeline(correction_request)
                                
                                if enhanced_correction.success and enhanced_correction.data:
                                    api_results = [
                                        AskResult(
                                            **{
                                                "sql": enhanced_correction.data.get("sql", ""),
                                                "type": "llm",
                                            }
                                        )
                                    ]
                                    # Extract quality scoring
                                    quality_scoring = self._extract_quality_scoring(enhanced_correction)
                                else:
                                    error_message = enhanced_correction.error or failed_dry_run_results[0]["error"]
                            else:
                                # Use standard correction
                                sql_correction_results = await self._pipeline_container.get_pipeline("sql_correction").run(
                                    contexts=[],
                                    invalid_generation_results=failed_dry_run_results,
                                    project_id=ask_feedback_request.project_id,
                                )

                                if valid_generation_results := sql_correction_results[
                                    "post_process"
                                ]["valid_generation_results"]:
                                    api_results = [
                                        AskResult(
                                            **{
                                                "sql": valid_generation_result.get("sql"),
                                                "type": "llm",
                                            }
                                        )
                                        for valid_generation_result in valid_generation_results
                                    ][:1]
                                elif failed_dry_run_results := sql_correction_results[
                                    "post_process"
                                ]["invalid_generation_results"]:
                                    error_message = failed_dry_run_results[0]["error"]
                        else:
                            error_message = failed_dry_run_results[0]["error"]

            if api_results:
                if not self._is_stopped(query_id):
                    self._update_cache_status(
                        query_id,
                        "finished",
                        AskFeedbackResultResponse(
                            status="finished",
                            response=api_results,
                            quality_scoring=quality_scoring,
                        )
                    )
                results["ask_feedback_result"] = api_results
                if quality_scoring:
                    results["metadata"]["quality_scoring"] = quality_scoring.dict()
            else:
                logger.exception("ask feedback pipeline - NO_RELEVANT_SQL")
                if not self._is_stopped(query_id):
                    self._update_cache_status(
                        query_id,
                        "failed",
                        AskFeedbackResultResponse(
                            status="failed",
                            error=AskError(
                                code="NO_RELEVANT_SQL",
                                message=error_message or "No relevant SQL",
                            ),
                        )
                    )
                results["metadata"]["error_type"] = "NO_RELEVANT_SQL"
                results["metadata"]["error_message"] = error_message

            return results

        except Exception as e:
            logger.exception(f"ask feedback pipeline - OTHERS: {e}")

            self._update_cache_status(
                query_id,
                "failed",
                AskFeedbackResultResponse(
                    status="failed",
                    error=AskError(
                        code="OTHERS",
                        message=str(e),
                    ),
                )
            )

            results["metadata"]["error_type"] = "OTHERS"
            results["metadata"]["error_message"] = str(e)
            return results

    def stop_ask_feedback(self, stop_ask_feedback_request: StopAskFeedbackRequest):
        """Stop processing of an ask feedback request"""
        self.stop_request(stop_ask_feedback_request.query_id)

    def get_ask_feedback_result(self, ask_feedback_result_request: AskFeedbackResultRequest) -> AskFeedbackResultResponse:
        """Get the result of an ask feedback request"""
        return self.get_request_status(ask_feedback_result_request.query_id).get("result")

    async def process_request(self, request: AskRequest) -> AskResultResponse:
        """Process an ask request"""
        # Use the query_id from the request instead of generating a new one
        event_id = request.query_id
        self._cache_request(event_id, request)
        
        try:
            # Execute the request processing logic
            result = await self._process_request_impl(request)
            
            # Update cache with success
            self._update_cache_status(event_id, "finished", result)
            
            # Create and return response
            return self._create_response(event_id, result)
            
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            self._update_cache_status(event_id, "failed", str(e))
            raise

    async def _stream_update(self, query_id: str, status: str, data: Dict[str, Any] = None):
        """Send streaming update to all connected clients for a query"""
        if query_id in self._streaming_clients:
            message = {
                "status": status,
                "data": data or {},
                "timestamp": asyncio.get_event_loop().time()
            }
            for client in self._streaming_clients[query_id]:
                try:
                    print(f"[DEBUG] [ask.py] Sending streaming update to client: {message}")
                    await client.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending streaming update: {e}")
                    # Remove failed client
                    self._streaming_clients[query_id].remove(client)

    async def process_request_with_streaming(self, request: AskRequest, stream_update: Optional[Callable[[Dict[str, Any]], None]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a request with streaming updates. If stream_update is provided, call it for each update; otherwise, yield the update."""
        query_id = request.query_id
        request.query_id = query_id  # Ensure the property is cached and stable
        print(f"[DEBUG] [ask.py] Registering stream for {query_id}")
        self._cache_request(query_id, request)
        try:
            def send(update):
                if stream_update:
                    return stream_update(update)
                else:
                    return update
            # Send initial status to ensure stream is ready
            update = {"status": "starting", "data": {"query": request.query}}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            print(f"[DEBUG] [ask.py] Put 'starting' status for {query_id}")
            # Step 1: Check historical questions
            update = {"status": "checking_history", "data": {"query": request.query}}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            print(f"[DEBUG] [ask.py] Put 'checking_history' status for {query_id}")
            historical_result = await self._check_historical_questions(query_id, request.query, request.project_id, request.histories)
            update = {"status": "checking_history", "data": {"query": request.query}}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            if historical_result:
                update = {"status": "finished", "data": historical_result}
                if stream_update:
                    await stream_update(update)
                else:
                    yield update
                print(f"[DEBUG] [ask.py] Put 'finished' status (history) for {query_id}")
                return
            # Step 2: Process intent classification
            update = {"status": "classifying_intent", "data": {"query": request.query}}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            print(f"[DEBUG] [ask.py] Put 'classifying_intent' status for {query_id}")
            intent_result = await self._process_intent_classification(query_id, request.query, request.histories, request)
            update = {"status": "classifying_intent", "data": {"query": request.query}}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            if intent_result:
                update = {"status": "finished", "data": intent_result}
                if stream_update:
                    await stream_update(update)
                else:
                    yield update
                print(f"[DEBUG] [ask.py] Put 'finished' status (intent) for {query_id}")
                return
            # Shared pipeline steps with streaming
            update = {"status": "running_pipeline_steps", "data": {"query": request.query}}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            print(f"[DEBUG] [ask.py] Running pipeline steps for {query_id}")
            final_result = await self._run_ask_pipeline_steps(
                query_id, request.query, request.histories, request, 
                stream_update=None
            )
            print(f"[DEBUG] [ask.py] Pipeline steps complete for {query_id}, final_result: {final_result}")
            # Send final update
            update = {"status": "finished", "data": final_result}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            print(f"[DEBUG] [ask.py] Put 'finished' status (final) for {query_id}")
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            print(f"[DEBUG] [ask.py] Error processing request: {e}")
            error_result = self._handle_error(query_id, e, request.histories or [])
            self._update_cache_status(query_id, "failed", error_result)
            update = {"status": "error", "data": error_result}
            if stream_update:
                await stream_update(update)
            else:
                yield update
            print(f"[DEBUG] [ask.py] Put 'error' status for {query_id}: {e}")
        finally:
            try:
                print(f"[DEBUG] [ask.py] Closed stream for {query_id}")
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
                print(f"[DEBUG] [ask.py] Error closing stream for {query_id}: {e}")

    async def execute_sql_with_streaming(self, request: AskRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute SQL and stream results with human-readable answer"""
        try:
            # First generate SQL
            async for sql_update in self.process_request_with_streaming(request):
                yield sql_update

                # If we have a successful SQL generation, execute it
                if sql_update.get("status") == "finished" and sql_update.get("api_results"):
                    # The SQL data and answer are already included in the final result
                    # from process_request_with_streaming, so we don't need to do anything else
                    break

        except Exception as e:
            logger.error(f"Error in SQL execution streaming: {e}")
            yield {
                "status": "error",
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": str(e)
                }
            }

    async def websocket_handler(self, request: Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for streaming updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        try:
            # Get query_id from request
            query_id = request.query.get('query_id')
            if not query_id:
                await ws.close(code=1008, message=b'Missing query_id')
                return ws
                
            # Add client to streaming clients
            if query_id not in self._streaming_clients:
                self._streaming_clients[query_id] = []
            self._streaming_clients[query_id].append(ws)
            
            # Wait for the initial request
            request_data = await ws.receive_json()
            ask_request = AskRequest(**request_data)
            
            # Process the request with streaming
            try:
                # Check if this is an execution request
                is_execution = request_data.get("execute_sql", False)
                
                if is_execution:
                    # Use execution streaming
                    async for update in self.execute_sql_with_streaming(ask_request):
                        await ws.send_json(update)
                        if update.get("status") in ["finished", "error"]:
                            break
                else:
                    # Use regular streaming
                    async for update in self.process_request_with_streaming(ask_request):
                        await ws.send_json(update)
                        if update.get("status") in ["finished", "error"]:
                            break
                        
            except Exception as e:
                logger.error(f"Error processing streaming request: {e}")
                error_response = {
                    "status": "error",
                    "error": {
                        "code": "PROCESSING_ERROR",
                        "message": str(e)
                    }
                }
                await ws.send_json(error_response)
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            if not ws.closed:
                await ws.send_json({
                    "status": "error",
                    "error": {
                        "code": "WEBSOCKET_ERROR",
                        "message": str(e)
                    }
                })
        finally:
            # Clean up client
            if query_id in self._streaming_clients:
                if ws in self._streaming_clients[query_id]:
                    self._streaming_clients[query_id].remove(ws)
                if not self._streaming_clients[query_id]:
                    del self._streaming_clients[query_id]
            if not ws.closed:
                await ws.close()
            
        return ws

    def stop_streaming(self, query_id: str):
        """Stop streaming for a specific query and close all connections"""
        if query_id in self._streaming_clients:
            for client in self._streaming_clients[query_id]:
                asyncio.create_task(client.close())
            del self._streaming_clients[query_id]

    async def _generate_sql_data(self, query_id: str, sql_result: Dict[str, Any], project_id: str, configuration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate SQL execution data"""
        if self._is_stopped(query_id):
            return {"success": False}
        ### This is only a dry run we get atmost 1000 rows back. 
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

            logger.info(f"result in generate_sql_data post process: {result}")
            if result.get("post_process"):
                post_process = result["post_process"]
                return {
                    "success": True,
                    "data": post_process.get('data', []),
                    "columns": post_process.get('columns', []),
                    "row_count": post_process.get('row_count', 0)
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

    async def _generate_sql_answer(self, query_id: str, sql_data: Dict[str, Any], user_query: str, sql_result: Dict[str, Any], request: AskRequest) -> Dict[str, Any]:
        """Generate SQL answer using sql_answer pipeline"""
        if self._is_stopped(query_id):
            return {"success": False}

        self._update_cache_status(
            query_id,
            "generating_answer",
            AskResultResponse(
                status="generating_answer",
                type="TEXT_TO_SQL",
                is_followup=True if request.histories else False,
            )
        )

        try:
            # Get SQL answer pipeline
            answer_pipeline = self._pipeline_container.get_pipeline("sql_answer")
            if not answer_pipeline:
                logger.warning("SQL answer pipeline not found")
                return {"success": False, "error": "SQL answer pipeline not available"}
            
            # Get SQL from result
            sql = ""
            if sql_result.get("api_results"):
                sql = sql_result["api_results"][0].sql

            if not sql:
                return {
                    "success": False,
                    "error": "No SQL found in result"
                }

            if not sql_data.get("success"):
                return {
                    "success": False,
                    "error": "SQL execution failed"
                }
            
            # Check if data exists (even if empty)
            if "data" not in sql_data:
                return {
                    "success": False,
                    "error": "No SQL execution data available"
                }

            # Format SQL data for the answer pipeline
            if sql_data["data"] and len(sql_data["data"]) > 0:
                formatted_sql_data = {
                    "columns": list(sql_data["data"][0].keys()),
                    "rows": sql_data["data"],
                    "row_count": len(sql_data["data"])
                }
            else:
                # Handle case where SQL returns no results
                formatted_sql_data = {
                    "columns": sql_data.get("columns", []),
                    "rows": [],
                    "row_count": 0
                }

            # Generate answer using the pipeline
            logger.info(f"Calling answer pipeline with sql_data: {formatted_sql_data}")
            answer_result = await answer_pipeline.run(
                query=user_query,
                sql=sql,
                sql_data=formatted_sql_data,
                project_id=request.project_id,
                language=request.configurations.language if request.configurations else "English",
                schema_context=request.schema_context if hasattr(request, 'schema_context') else None
            )

            logger.info(f"SQL answer generation result: {answer_result}")
            if not answer_result.get("success", False):
                logger.error(f"SQL answer generation failed: {answer_result.get('error', 'Unknown error')}")
                logger.error(f"Full answer_result: {answer_result}")
            else:
                logger.info(f"SQL answer generation successful: {answer_result.get('data', {})}")

            # Handle the response format
            if answer_result.get("success"):
                return {
                    "success": True,
                    "answer": answer_result.get("data",{}).get("answer", ""),
                    "explanation": answer_result.get("data",{}).get("reasoning", ""),
                    "metadata": answer_result.get("metadata", {})
                }
            else:
                error_msg = answer_result.get("error", "Failed to generate answer")
                logger.error(f"SQL answer generation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }

        except Exception as e:
            logger.error(f"Error generating SQL answer: {e}")
            return {
                "success": False,
                "error": str(e)
            }