import logging
from typing import Dict, Literal, Optional,Any

from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.sql.models import (
    ChartAdjustmentRequest,
    ChartAdjustmentResult,
    ChartAdjustmentResultRequest,
    ChartAdjustmentResultResponse,
    ChartAdjustmentError,
    StopChartAdjustmentRequest,
)
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")


# POST /v1/chart-adjustments

class ChartAdjustmentService(BaseService[ChartAdjustmentRequest, ChartAdjustmentResultResponse]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)

    @observe(name="Adjust Chart")
    async def _process_request_impl(self, request: ChartAdjustmentRequest) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        results = {
            "chart_adjustment_result": {},
            "metadata": {
                "error_type": "",
                "error_message": "",
            },
        }

        try:
            # Execute SQL to get data
            sql_data = (
                await self._execute_pipeline(
                    "sql_executor",
                    sql=request.sql,
                    project_id=request.project_id,
                )
            )["execute_sql"]["results"]

            # Generate chart adjustment
            chart_adjustment_result = await self._execute_pipeline(
                "chart_adjustment",
                query=request.query,
                sql=request.sql,
                adjustment_option=request.adjustment_option,
                chart_schema=request.chart_schema,
                data=sql_data,
                language=request.configurations.language,
            )
            chart_result = chart_adjustment_result["post_process"]["results"]

            if not chart_result.get("chart_schema", {}) and not chart_result.get(
                "reasoning", ""
            ):
                results["metadata"]["error_type"] = "NO_CHART"
                results["metadata"]["error_message"] = "chart generation failed"
            else:
                results["chart_adjustment_result"] = chart_result

            return results
        except Exception as e:
            logger.exception(f"chart adjustment pipeline - OTHERS: {e}")
            results["metadata"]["error_type"] = "OTHERS"
            results["metadata"]["error_message"] = str(e)
            return results

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> ChartAdjustmentResultResponse:
        """Create a response object from the processing result."""
        if result.get("metadata", {}).get("error_type"):
            return ChartAdjustmentResultResponse(
                status="failed",
                error=ChartAdjustmentError(
                    code=result["metadata"]["error_type"],
                    message=result["metadata"]["error_message"],
                ),
                trace_id=event_id,
            )
            
        return ChartAdjustmentResultResponse(
            status="finished",
            response=ChartAdjustmentResult(**result["chart_adjustment_result"]),
            trace_id=event_id,
        )

    def get_chart_adjustment_result(
        self,
        chart_adjustment_result_request: ChartAdjustmentResultRequest,
    ) -> ChartAdjustmentResultResponse:
        """Get the result of a chart adjustment request."""
        return self.get_request_status(chart_adjustment_result_request.query_id)

    def stop_chart_adjustment(
        self,
        stop_chart_adjustment_request: StopChartAdjustmentRequest,
    ):
        """Stop the chart adjustment process."""
        self.stop_request(stop_chart_adjustment_request.query_id)
