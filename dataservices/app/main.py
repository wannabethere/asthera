from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

#from app.routers.instruction_router import router as instruction_router
from app.routers.example_router import router as example_router
from app.routers.knowledge_base_router import router as knowledge_base_router
from app.routers.project_workflow import router as project_workflow_router
from app.routers.sql_functions_routers import router as sql_functions_router
from app.routers.semantics import router as semantics_router
from app.routers.relationships import router as relationships_router
from app.routers.recommendations import router as recommendations_router


 
from app.utils.sse import add_subscriber, remove_subscriber
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig

# Initialize session manager at startup
session_manager = SessionManager(ServiceConfig())
session_manager.create_tables()

app = FastAPI(title="Data Services API", version="1.0.0")



#app.include_router(instruction_router, prefix="/instructions", tags=["Instructions"])
app.include_router(example_router, prefix="/examples", tags=["Examples"])
app.include_router(
    knowledge_base_router, prefix="/knowledge-bases", tags=["Knowledge Base"]
)
app.include_router(project_workflow_router, prefix="/projects/workflow", tags=["Project Workflow"])

app.include_router(sql_functions_router, prefix="/sql-functions", tags=["SQL Functions"])
app.include_router(semantics_router, prefix="/semantics", tags=["Semantics"])
app.include_router(relationships_router, prefix="/relationships", tags=["Relationships"])
app.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"])

@app.get("/")
def health():
    """Health Check to confirm API is up and running."""
    return {"status": "API is up and running"}

@app.get("/workflow/stream/{user_id}")
async def workflow_stream(user_id: str, session_id: str = "default", request: Request = None):
    async def event_generator():
        queue = asyncio.Queue()
        add_subscriber(user_id, session_id, queue)
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    # Send a keep-alive comment every 15 seconds
                    yield ":\n\n"
                    continue
                yield f"data: {json.dumps(data)}\n\n"
                if await request.is_disconnected():
                    break
        finally:
            remove_subscriber(user_id, session_id, queue)
    return StreamingResponse(event_generator(), media_type='text/event-stream')
