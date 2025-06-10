import logging
from typing import Any, Dict, Literal, Optional

from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.nodes.sql.chart_generation import create_vega_lite_chart_generation_pipeline
from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.sql.models import (
    ChartRequest,
    ChartResult,
    ChartResultResponse,
    ChartResultRequest,
    ChartError,
    StopChartRequest,
)
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")


# POST /v1/charts

class ChartService(BaseService[ChartRequest, ChartResultResponse]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)
        
        # Initialize the chart generation pipeline
        self._chart_pipeline = create_vega_lite_chart_generation_pipeline()
        logger.info("Chart service initialized")

    @observe(name="Generate Chart")
    async def _process_request_impl(self, request: ChartRequest) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        results = {
            "chart_result": {},
            "metadata": {
                "error_type": "",
                "error_message": "",
            },
        }

        try:
            # Get SQL data if not provided
            if not request.data:
                sql_data = (
                    await self._execute_pipeline(
                        "sql_executor",
                        sql=request.sql,
                        project_id=request.project_id,
                    )
                )["execute_sql"]["results"]
            else:
                sql_data = request.data

            # Use the chart generation pipeline
            chart_result = await self._chart_pipeline.run(
                query=request.query,
                sql=request.sql,
                data=sql_data,
                language=request.configurations.language,
                remove_data_from_chart_schema=request.remove_data_from_chart_schema,
            )

            if not chart_result.get("chart_schema", {}) and not chart_result.get(
                "reasoning", ""
            ):
                results["metadata"]["error_type"] = "NO_CHART"
                results["metadata"]["error_message"] = "chart generation failed"
            else:
                results["chart_result"] = chart_result

            return results
        except Exception as e:
            logger.exception(f"chart pipeline - OTHERS: {e}")
            results["metadata"]["error_type"] = "OTHERS"
            results["metadata"]["error_message"] = str(e)
            return results

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> ChartResultResponse:
        """Create a response object from the processing result."""
        if result.get("metadata", {}).get("error_type"):
            return ChartResultResponse(
                status="failed",
                error=ChartError(
                    code=result["metadata"]["error_type"],
                    message=result["metadata"]["error_message"],
                ),
                trace_id=event_id,
            )
            
        return ChartResultResponse(
            status="finished",
            response=ChartResult(**result["chart_result"]),
            trace_id=event_id,
        )

    def get_chart_result(
        self,
        chart_result_request: ChartResultRequest,
    ) -> ChartResultResponse:
        """Get the result of a chart generation request."""
        return self.get_request_status(chart_result_request.query_id)

    def stop_chart(
        self,
        stop_chart_request: StopChartRequest,
    ):
        """Stop the chart generation process."""
        self.stop_request(stop_chart_request.query_id)
