import asyncio
import logging
from typing import Dict, Literal, Optional, Any, List

import orjson
from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.services.sql.models import Resource, Error, GenerateRequest
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")


class SemanticsDescription(BaseService[GenerateRequest, Resource]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)

    def _handle_exception(
        self,
        id: str,
        error_message: str,
        code: str = "OTHERS",
        trace_id: Optional[str] = None,
    ):
        self[id] = self.Resource(
            id=id,
            status="failed",
            error=Error(code=code, message=error_message),
            trace_id=trace_id,
        )
        logger.error(error_message)

    

    def _chunking(
        self, mdl_dict: dict, request: GenerateRequest, chunk_size: int = 50
    ) -> list[dict]:
        """Split the MDL into smaller chunks for processing."""
        template = {
            "user_prompt": request.user_prompt,
            "language": request.configuration.language,
        }

        chunks = [
            {
                **model,
                "columns": model["columns"][i : i + chunk_size],
            }
            for model in mdl_dict["models"]
            if model["name"] in request.selected_models
            for i in range(0, len(model["columns"]), chunk_size)
        ]

        return [
            {
                **template,
                "mdl": {"models": [chunk]},
                "selected_models": [chunk["name"]],
            }
            for chunk in chunks
        ]

    async def _generate_task(self, request_id: str, chunk: dict) -> Dict[str, Any]:
        """Process a single chunk of the MDL."""
        resp = await self._execute_pipeline("semantics_description", **chunk)
        return resp.get("output", {})

    @observe(name="Generate Semantics Description")
    async def _process_request_impl(self, request: GenerateRequest) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        logger.info("Generate Semantics Description pipeline is running...")

        try:
            mdl_dict = orjson.loads(request.mdl)
            chunks = self._chunking(mdl_dict, request)
            
            # Process all chunks concurrently
            chunk_results = await asyncio.gather(
                *[self._generate_task(request.id, chunk) for chunk in chunks]
            )
            
            # Combine results from all chunks
            combined_response = {}
            for output in chunk_results:
                for key in output.keys():
                    if key not in combined_response:
                        combined_response[key] = output[key]
                        continue
                    combined_response[key]["columns"].extend(output[key]["columns"])

            return {
                "status": "finished",
                "id": request.id,
                "response": combined_response
            }
            
        except orjson.JSONDecodeError as e:
            error_message = f"Failed to parse MDL: {str(e)}"
            logger.error(error_message)
            return {
                "status": "failed",
                "id": request.id,
                "error": Error(code="MDL_PARSE_ERROR", message=error_message)
            }
            
        except Exception as e:
            error_message = f"An error occurred during semantics description generation: {str(e)}"
            logger.error(error_message)
            return {
                "status": "failed",
                "id": request.id,
                "error": Error(code="OTHERS", message=error_message)
            }

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> Resource:
        """Create a response object from the processing result."""
        return Resource(
            id=result["id"],
            status=result["status"],
            response=result.get("response"),
            error=result.get("error"),
            trace_id=event_id
        )

    def get_description(self, id: str) -> Resource:
        """Get a semantics description by ID."""
        return self.get_request_status(id)
