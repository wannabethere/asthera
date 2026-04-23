from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

#from app.routers.instruction_router import router as instruction_router
from app.routers.workflow_routers import router as workflow_router
from app.routers.project_router import router as project_router

from app.utils.cache import set_cache_provider, InMemoryCacheProvider
from contextlib import asynccontextmanager
from dotenv import load_dotenv
 
from app.utils.sse import add_subscriber, remove_subscriber
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig, log_active_vector_store_backend

load_dotenv()
log_active_vector_store_backend()

# Initialize session manager at startup
session_manager = SessionManager(ServiceConfig())
#asyncio.run()


@asynccontextmanager
async def lifespan(app: FastAPI):  
    set_cache_provider(InMemoryCacheProvider())
    await session_manager.create_tables()
    yield

app = FastAPI(title="Data Services API", version="1.0.0",
              docs_url="/docs",
              redoc_url="/redoc",
              openapi_url="/openapi.json",
            lifespan=lifespan)

# Include routers
app.include_router(workflow_router)
app.include_router(project_router)


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
