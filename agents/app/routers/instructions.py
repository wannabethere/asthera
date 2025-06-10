from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional

from app.services.sql.models import (
    IndexRequest,
    Event,
    Instruction
)
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/instructions", tags=["instructions"])

def get_instructions_service():
    """Get the InstructionsService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("instructions_service")

@router.post("/index")
async def index_instructions(request: IndexRequest) -> Event:
    """Index new instructions."""
    service = get_instructions_service()
    return await service.process_request(request)

@router.post("/delete")
async def delete_instructions(
    event_id: str,
    instruction_ids: List[str],
    project_id: Optional[str] = None
) -> Event:
    """Delete instructions from the index."""
    service = get_instructions_service()
    request = service.DeleteRequest(
        event_id=event_id,
        instruction_ids=instruction_ids,
        project_id=project_id
    )
    return await service.delete(request)

@router.get("/{event_id}")
def get_event(event_id: str) -> Event:
    """Get an event by ID."""
    service = get_instructions_service()
    return service.get_event(event_id) 