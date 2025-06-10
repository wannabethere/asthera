import logging
from typing import Dict, List, Literal, Optional, Any

from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.sql.models import Instruction, Event, IndexRequest, Error
from app.services.servicebase import BaseService

logger = logging.getLogger("lexy-ai-service")


class InstructionsService(BaseService[IndexRequest, Event]):
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        # Get pipelines from PipelineContainer
        pipeline_container = PipelineContainer.get_instance()
        pipelines = pipeline_container.get_all_pipelines()
        
        super().__init__(pipelines=pipelines, maxsize=maxsize, ttl=ttl)

    @observe(name="Index Instructions")
    async def _process_request_impl(self, request: IndexRequest) -> Dict[str, Any]:
        """Implementation of request processing logic."""
        logger.info(f"Request {request.event_id}: Instructions Indexing process is running...")

        try:
            instructions = []
            for instruction in request.instructions:
                if instruction.is_default:
                    instructions.append(
                        Instruction(
                            id=instruction.id,
                            instruction=instruction.instruction,
                            question="",
                            is_default=True,
                        )
                    )
                else:
                    for question in instruction.questions:
                        instructions.append(
                            Instruction(
                                id=instruction.id,
                                instruction=instruction.instruction,
                                question=question,
                                is_default=False,
                            )
                        )

            await self._execute_pipeline(
                "instructions_indexing",
                project_id=request.project_id,
                instructions=instructions,
            )

            return {
                "status": "finished",
                "event_id": request.event_id
            }

        except Exception as e:
            error_message = f"An error occurred during instructions indexing: {str(e)}"
            logger.error(error_message)
            return {
                "status": "failed",
                "event_id": request.event_id,
                "error": Error(code="OTHERS", message=error_message)
            }

    def _create_response(self, event_id: str, result: Dict[str, Any]) -> Event:
        """Create a response object from the processing result."""
        return Event(
            event_id=event_id,
            status=result["status"],
            error=result.get("error"),
            trace_id=event_id
        )

    class DeleteRequest(BaseModel):
        event_id: str
        instruction_ids: List[str]
        project_id: Optional[str] = None

    @observe(name="Delete Instructions")
    async def delete(
        self,
        request: DeleteRequest,
        **kwargs,
    ):
        """Delete instructions from the index."""
        logger.info(f"Request {request.event_id}: Instructions Deletion process is running...")
        trace_id = kwargs.get("trace_id")

        try:
            instructions = [Instruction(id=id) for id in request.instruction_ids]
            await self._execute_pipeline(
                "instructions_indexing",
                clean=True,
                instructions=instructions,
                project_id=request.project_id
            )

            return Event(
                event_id=request.event_id,
                status="finished",
                trace_id=trace_id,
            )
        except Exception as e:
            error_message = f"Failed to delete instructions: {e}"
            logger.error(error_message)
            return Event(
                event_id=request.event_id,
                status="failed",
                error=Error(code="OTHERS", message=error_message),
                trace_id=trace_id,
            )

    def get_event(self, event_id: str) -> Event:
        """Get an event by ID."""
        return self.get_request_status(event_id)
