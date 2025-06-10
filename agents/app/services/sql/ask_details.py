import logging
from typing import Dict, List, Literal, Optional, Any

from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.nodes.sql.utils.sql import add_quotes
from app.agents.nodes.sql.utils.sql import Configuration
from app.agents.pipelines.base import Pipeline
from app.agents.pipelines.pipeline_container import PipelineContainer

# Import enhanced SQL pipeline components
from app.agents.pipelines.enhanced_sql_pipeline import (
    EnhancedSQLPipelineWrapper,
    PipelineRequest,
    PipelineType,
    SQLAdvancedRelevanceScorer
)
from app.services.sql.models import AskDetailsRequest, AskDetailsResultRequest, AskDetailsResultResponse, QualityScoring
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")

class AskDetailsService(BaseService[AskDetailsRequest, AskDetailsResultResponse]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
        # Added parameters for enhanced SQL pipeline
        enable_enhanced_sql: bool = True,
        sql_scoring_config_path: Optional[str] = None,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)
        
        # Enhanced SQL pipeline setup
        self._enable_enhanced_sql = enable_enhanced_sql
        self._sql_scoring_config_path = sql_scoring_config_path
        self._enhanced_sql_wrapper = None
        
        # Initialize enhanced SQL wrapper if enabled
        if enable_enhanced_sql and "sql_pipeline" in pipelines:
            self._relevance_scorer = SQLAdvancedRelevanceScorer(
                config_file_path=sql_scoring_config_path
            )
            self._enhanced_sql_wrapper = EnhancedSQLPipelineWrapper(
                sql_pipeline=pipelines["sql_pipeline"],
                relevance_scorer=self._relevance_scorer,
                enable_scoring=True
            )
            logger.info("Enhanced SQL pipeline initialized with scoring capabilities for SQL breakdown")

    async def _add_summary_to_sql(self, sql: str, query: str, language: str):
        sql_summary_results = await self._execute_pipeline(
            "sql_summary",
            query=query,
            sqls=[sql],
            language=language,
        )
        return sql_summary_results["post_process"]["sql_summary_results"]
    
    def _extract_quality_scoring(self, enhanced_result):
        """Extract quality scoring information from enhanced SQL result"""
        if not enhanced_result or not hasattr(enhanced_result, 'relevance_scoring'):
            return None
            
        scoring = enhanced_result.relevance_scoring
        return QualityScoring(
            final_score=scoring.final_score,
            quality_level=scoring.quality_level,
            improvement_recommendations=scoring.improvement_recommendations,
            processing_time_seconds=scoring.processing_time_seconds,
            explanation_quality=scoring.quality_level  # Use quality level for explanation quality
        )

    @observe(name="Ask Details(Breakdown SQL)")
    async def _process_request_impl(self, request: AskDetailsRequest) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        results = {
            "ask_details_result": {},
            "metadata": {
                "error_type": "",
                "error_message": "",
                "enhanced_sql_used": self._enable_enhanced_sql and request.enable_scoring,
            },
        }

        try:
            quality_scoring = None
            ask_details_result = None
            
            # Check if enhanced SQL pipeline should be used
            if self._enable_enhanced_sql and self._enhanced_sql_wrapper and request.enable_scoring:
                # Create schema context for enhanced SQL
                schema_context = {
                    "sql_query": request.sql,
                    "natural_language_query": request.query
                }
                
                # Configure enhanced SQL pipeline request for breakdown
                pipeline_request = PipelineRequest(
                    pipeline_type=PipelineType.SQL_BREAKDOWN,
                    query=request.query,
                    language=request.configurations.language,
                    project_id=request.project_id,
                    enable_scoring=True,
                    schema_context=schema_context,
                    additional_params={
                        "sql": request.sql,
                    }
                )
                
                # Use enhanced SQL breakdown with scoring
                enhanced_result = await self._enhanced_sql_wrapper.breakdown_sql_with_scoring(pipeline_request)
                
                # Extract results and quality scoring
                if enhanced_result.success and enhanced_result.data:
                    # Process breakdown into required format
                    breakdown_data = enhanced_result.data.get("breakdown", "")
                    
                    # Try to convert breakdown data to our expected format
                    try:
                        if isinstance(breakdown_data, dict) and "steps" in breakdown_data:
                            ask_details_result = breakdown_data
                        elif isinstance(breakdown_data, str):
                            # If it's a string, we need to create a simple breakdown
                            ask_details_result = {
                                "description": "SQL query breakdown",
                                "steps": [
                                    {
                                        "sql": request.sql,
                                        "summary": breakdown_data,
                                        "cte_name": "",
                                    }
                                ]
                            }
                    except Exception as e:
                        logger.error(f"Error processing enhanced breakdown result: {e}")
                        # We'll fall back to the standard approach
                        ask_details_result = None
                    
                    # Extract quality scoring
                    quality_scoring = self._extract_quality_scoring(enhanced_result)
            
            # Use standard breakdown if enhanced breakdown failed or isn't available
            if ask_details_result is None:
                generation_result = await self._execute_pipeline(
                    "sql_breakdown",
                    query=request.query,
                    sql=request.sql,
                    project_id=request.project_id,
                    language=request.configurations.language,
                )

                ask_details_result = generation_result["post_process"]["results"]

            # Fallback if no steps were generated
            if not ask_details_result or not ask_details_result.get("steps"):
                quoted_sql, error_message = add_quotes(request.sql)
                sql = quoted_sql if not error_message else request.sql

                sql_summary_results = await self._execute_pipeline(
                    "sql_summary",
                    query=request.query,
                    sqls=[sql],
                    language=request.configurations.language,
                )
                sql_summary_result = sql_summary_results["post_process"][
                    "sql_summary_results"
                ][0]

                ask_details_result = {
                    "description": "SQL query summary",
                    "steps": [
                        {
                            "sql": sql_summary_result["sql"],
                            "summary": sql_summary_result["summary"],
                            "cte_name": "",
                        }
                    ]
                }
                results["metadata"]["error_type"] = "SQL_BREAKDOWN_FAILED"

            results["ask_details_result"] = ask_details_result
            if quality_scoring:
                results["metadata"]["quality_scoring"] = {
                    "final_score": quality_scoring.final_score,
                    "quality_level": quality_scoring.quality_level,
                    "explanation_quality": quality_scoring.explanation_quality,
                    "recommendations": quality_scoring.improvement_recommendations
                }

            return results
        except Exception as e:
            logger.exception(f"ask-details pipeline - OTHERS: {e}")
            results["metadata"]["error_type"] = "OTHERS"
            results["metadata"]["error_message"] = str(e)
            return results

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> AskDetailsResultResponse:
        """Create a response object from the processing result."""
        if result.get("metadata", {}).get("error_type"):
            return AskDetailsResultResponse(
                status="failed",
                error=AskDetailsResultResponse.AskDetailsError(
                    code=result["metadata"]["error_type"],
                    message=result["metadata"]["error_message"],
                ),
                trace_id=event_id,
            )
            
        return AskDetailsResultResponse(
            status="finished",
            response=AskDetailsResultResponse.AskDetailsResponseDetails(
                **result["ask_details_result"]
            ),
            trace_id=event_id,
            quality_scoring=result.get("metadata", {}).get("quality_scoring"),
        )

    def get_ask_details_result(
        self,
        ask_details_result_request: AskDetailsResultRequest,
    ) -> AskDetailsResultResponse:
        """Get the result of an ask details request."""
        return self.get_request_status(ask_details_result_request.query_id)