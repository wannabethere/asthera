"""
Integration test for indexing (ProjectReaderQdrant) and retrieval (RetrievalHelper).

Uses app.settings and app.core.dependencies like demo_askandquestion_recommendation.
Tests: index sql_meta + sql_functions -> retrieve schemas and SQL functions by project_id.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from app.settings import get_settings
from app.core.dependencies import clear_chromadb_cache
from app.settings import VectorStoreType
from app.indexing.project_reader_qdrant import ProjectReaderQdrant
from app.agents.retrieval.retrieval_helper import RetrievalHelper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("lexy-ai-service")

# Reduce verbosity from storage/indexing
logging.getLogger("app.storage").setLevel(logging.WARNING)
logging.getLogger("app.indexing").setLevel(logging.WARNING)


class IndexingRetrievalIntegrationDemo:
    """Integration demo: index sql_meta + sql_functions, then retrieve by project_id."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IndexingRetrievalIntegrationDemo, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                settings = get_settings()
                base_path = str(settings.BASE_DIR / "data" / "sql_meta")
                ds_functions_path = str(settings.BASE_DIR / "data" / "sql_functions")
                host = getattr(settings, "QDRANT_HOST", None) or "localhost"
                port = int(getattr(settings, "QDRANT_PORT", 6333))

                self.reader = ProjectReaderQdrant(
                    base_path=base_path,
                    ds_functions_base_path=ds_functions_path,
                    host=host,
                    port=port,
                )
                self.retrieval_helper = RetrievalHelper()
                self._initialized = True
                logger.info("IndexingRetrievalIntegrationDemo initialized")
            except Exception as e:
                logger.error("Failed to initialize: %s", e)
                self._initialization_failed = True
                self._initialized = True

    async def index_projects(self, project_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Index projects from sql_meta. Core DS functions are indexed during reader init."""
        if getattr(self, "_initialization_failed", False):
            return {"status": "error", "error": "Initialization failed"}
        try:
            projects = self.reader.list_projects()
            if project_ids:
                projects = [p for p in projects if p in project_ids]
            results = []
            for project in projects:
                try:
                    data = await self.reader.index_project(project)
                    results.append({"project": project, "project_id": data.get("project_id"), "tables": len(data.get("tables", []))})
                except Exception as e:
                    logger.warning("Failed to index project %s: %s", project, e)
                    results.append({"project": project, "error": str(e)})
            return {"status": "success", "indexed": results, "total": len(results)}
        except Exception as e:
            logger.exception("Index failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def retrieve_schemas(self, query: str, project_id: str) -> Dict[str, Any]:
        """Retrieve table names and schema contexts for a project."""
        if getattr(self, "_initialization_failed", False):
            return {"status": "error", "error": "Initialization failed"}
        try:
            table_retrieval = {"table_retrieval_size": 10, "table_column_retrieval_size": 100}
            result = await self.retrieval_helper.get_table_names_and_schema_contexts(
                query=query,
                project_id=project_id,
                table_retrieval=table_retrieval,
            )
            return {"status": "success", "result": result}
        except Exception as e:
            logger.exception("Retrieve schemas failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def retrieve_sql_functions(self, query: str) -> Dict[str, Any]:
        """Retrieve SQL functions for a query."""
        if getattr(self, "_initialization_failed", False):
            return {"status": "error", "error": "Initialization failed"}
        try:
            result = await self.retrieval_helper.get_sql_functions(query=query)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.exception("Retrieve SQL functions failed: %s", e)
            return {"status": "error", "error": str(e)}


async def run_integration_test():
    """Run integration test: index -> retrieve."""
    settings = get_settings()
    if settings.VECTOR_STORE_TYPE != VectorStoreType.QDRANT:
        logger.warning(
            "VECTOR_STORE_TYPE=%s; ProjectReaderQdrant writes to Qdrant. "
            "RetrievalHelper uses %s. Set VECTOR_STORE_TYPE=qdrant for full integration.",
            settings.VECTOR_STORE_TYPE,
            settings.VECTOR_STORE_TYPE,
        )

    # Clear caches so we get fresh doc store provider
    clear_chromadb_cache()

    demo = IndexingRetrievalIntegrationDemo()
    if getattr(demo, "_initialization_failed", False):
        logger.error("Demo initialization failed, aborting")
        return

    base_path = settings.BASE_DIR / "data" / "sql_meta"
    if not base_path.exists():
        logger.warning("sql_meta path does not exist: %s. Skipping indexing.", base_path)
    else:
        logger.info("Step 1: Indexing projects from %s", base_path)
        index_result = await demo.index_projects(project_ids=["cornerstone", "hr_compliance_risk"])
        if index_result["status"] == "success":
            logger.info("Indexed: %s", index_result.get("indexed", []))
        else:
            logger.warning("Index result: %s", index_result)

    logger.info("Step 2: Retrieve schemas for project_id=cornerstone")
    schema_result = await demo.retrieve_schemas(
        query="Show completion rate by division",
        project_id="cornerstone",
    )
    if schema_result["status"] == "success":
        r = schema_result.get("result", {})
        tables = r.get("table_names", [])
        contexts = r.get("schema_contexts", [])
        logger.info("Retrieved %d tables: %s", len(tables), tables[:5] if tables else [])
        logger.info("Schema contexts count: %d", len(contexts))
    else:
        logger.warning("Schema retrieval: %s", schema_result)

    logger.info("Step 3: Retrieve SQL functions")
    func_result = await demo.retrieve_sql_functions(query="calculate moving average")
    if func_result["status"] == "success":
        r = func_result.get("result", {})
        funcs = r.get("sql_functions", [])
        logger.info("Retrieved %d SQL functions", len(funcs) if isinstance(funcs, list) else 0)
    else:
        logger.warning("SQL functions retrieval: %s", func_result)

    logger.info("Integration test complete")


if __name__ == "__main__":
    asyncio.run(run_integration_test())
