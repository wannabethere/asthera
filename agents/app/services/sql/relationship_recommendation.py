import logging
from typing import Dict, Literal, Optional, Any

import orjson
from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.sql.models import Input, Resource
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")


class RelationshipRecommendation(BaseService[Input, Resource]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)

    @observe(name="Generate Relationship Recommendation")
    async def _process_request_impl(self, request: Input) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        logger.info("Generate Relationship Recommendation pipeline is running...")

        try:
            mdl_dict = orjson.loads(request.mdl)

            input = {
                "mdl": mdl_dict,
                "language": request.configuration.language,
            }

            resp = await self._execute_pipeline("relationship_recommendation", **input)
            logger.debug(f"Response: {resp}")
            
            return {
                "status": "finished",
                "id": request.id,
                "response": resp.get("validated")
            }
            
        except orjson.JSONDecodeError as e:
            error_message = f"Failed to parse MDL: {str(e)}"
            logger.error(error_message)
            return {
                "status": "failed",
                "id": request.id,
                "error": Resource.Error(code="MDL_PARSE_ERROR", message=error_message)
            }
            
        except Exception as e:
            error_message = f"An error occurred during relationship recommendation generation: {str(e)}"
            logger.error(error_message)
            return {
                "status": "failed",
                "id": request.id,
                "error": Resource.Error(code="OTHERS", message=error_message)
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

    def get_recommendation(self, id: str) -> Resource:
        """Get a relationship recommendation by ID."""
        return self.get_request_status(id)
