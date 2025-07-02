
from fastapi import FastAPI
from app.routers.project_router import router as project_router
from app.routers.dataset_router import router as dataset_router
from app.routers.table_router import router as table_router
from app.routers.column_router import router as column_router
from app.routers.calculated_column_router import router as calculated_column_router
from app.routers.metric_router import router as metric_router
from app.routers.view_router import router as view_router
from app.routers.instruction_router import router as instruction_router
from app.routers.example_router import router as example_router
from app.routers.knowledge_base_router import router as knowledge_base_router
from app.routers.project_history_router import router as project_history_router
from app.routers.project_version_history_router import (
    router as project_version_history_router,
)
from app.routers.sql_functions_routers import router as sql_functions_router

from app.service.database import Base, engine
from app.service import dbmodel  

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Data Services API", version="1.0.0")


app.include_router(project_router, prefix="/projects", tags=["Projects"])
app.include_router(dataset_router, prefix="/datasets", tags=["Datasets"])
app.include_router(table_router, prefix="/tables", tags=["Tables"])
app.include_router(column_router, prefix="/columns", tags=["Columns"])
app.include_router(
    calculated_column_router, prefix="/calculated-columns", tags=["Calculated Columns"]
)
app.include_router(metric_router, prefix="/metrics", tags=["Metrics"])
app.include_router(view_router, prefix="/views", tags=["Views"])
app.include_router(instruction_router, prefix="/instructions", tags=["Instructions"])
app.include_router(example_router, prefix="/examples", tags=["Examples"])
app.include_router(
    knowledge_base_router, prefix="/knowledge-bases", tags=["Knowledge Base"]
)
app.include_router(
    project_history_router, prefix="/project-histories", tags=["Project History"]
)
app.include_router(
    project_version_history_router,
    prefix="/project-versions",
    tags=["Project Version History"],
)
app.include_router(sql_functions_router, prefix="/sql-functions", tags=["SQL Functions"])

@app.get("/")
def health():
    """Health Check to confirm API is up and running."""
    return {"status": "API is up and running"}
