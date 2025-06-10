import asyncio
import logging
from typing import Dict, Literal, Optional, Any, List

from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import AliasChoices, BaseModel, Field

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.sql.models import (
    SemanticsPreparationRequest,
    SemanticsPreparationResponse,
    SemanticsPreparationStatusRequest,
    SemanticsPreparationStatusResponse,
)
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")


class SemanticsPreparationService(BaseService[SemanticsPreparationRequest, SemanticsPreparationStatusResponse]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)

    @observe(name="Prepare Semantics")
    async def _process_request_impl(self, request: SemanticsPreparationRequest) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        results = {
            "metadata": {
                "error_type": "",
                "error_message": "",
            },
        }

        try:
            logger.info(f"MDL: {request.mdl}")

            input = {
                "mdl_str": request.mdl,
                "project_id": request.project_id,
            }

            # Define pipeline tasks
            pipeline_tasks = [
                self._execute_pipeline(name, **input)
                for name in [
                    "db_schema",
                    "historical_question",
                    "table_description",
                    "sql_pairs",
                    "project_meta",
                ]
            ]

            # Execute all tasks concurrently
            await asyncio.gather(*pipeline_tasks)

            return {
                "status": "finished",
                "mdl_hash": request.mdl_hash
            }

        except Exception as e:
            logger.exception(f"Failed to prepare semantics: {e}")
            results["metadata"]["error_type"] = "INDEXING_FAILED"
            results["metadata"]["error_message"] = str(e)
            
            return {
                "status": "failed",
                "mdl_hash": request.mdl_hash,
                "error": SemanticsPreparationStatusResponse.SemanticsPreparationError(
                    code="OTHERS",
                    message=f"Failed to prepare semantics: {e}",
                )
            }

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> SemanticsPreparationStatusResponse:
        """Create a response object from the processing result."""
        return SemanticsPreparationStatusResponse(
            status=result["status"],
            error=result.get("error"),
            trace_id=event_id
        )

    def get_prepare_semantics_status(
        self, prepare_semantics_status_request: SemanticsPreparationStatusRequest
    ) -> SemanticsPreparationStatusResponse:
        """Get the status of a semantics preparation request."""
        return self.get_request_status(prepare_semantics_status_request.mdl_hash)

    @observe(name="Delete Semantics Documents")
    async def delete_semantics(self, project_id: str, **kwargs):
        """Delete all semantics documents for a project."""
        logger.info(f"Project ID: {project_id}, Deleting semantics documents...")

        # Define pipeline tasks for deletion
        pipeline_tasks = [
            self._execute_pipeline(name, project_id=project_id)
            for name in [
                "db_schema",
                "historical_question",
                "table_description",
                "project_meta",
            ]
        ] + [
            self._execute_pipeline(
                name,
                project_id=project_id,
                delete_all=True,
            )
            for name in ["sql_pairs", "instructions"]
        ]

        # Execute all deletion tasks concurrently
        await asyncio.gather(*pipeline_tasks)
