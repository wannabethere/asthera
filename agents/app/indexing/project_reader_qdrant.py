"""
Project reader that indexes sql_meta projects into Qdrant using the same processors
as ProjectReader (DBSchema, TableDescription, etc.) with collection names prefixed
by collection_prefix (e.g. core_db_schema, core_sql_pairs). Transform logic stays
in the shared processors; only the store backend and project discovery differ.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from langchain_openai import OpenAIEmbeddings

from app.indexing.project_reader import ProjectReader
from app.indexing.db_schema import DBSchema
from app.indexing.table_description import TableDescription
from app.indexing.historical_question import HistoricalQuestion
from app.indexing.instructions import Instructions
from app.indexing.project_meta import ProjectMeta
from app.indexing.sql_pairs import SqlPairs
from app.storage.qdrant_store import DocumentQdrantStore
from app.settings import get_settings

logger = logging.getLogger("genieml-agents")
settings = get_settings()

# Collection name mapping: same keys as get_doc_store_provider().stores
# value = Qdrant collection name (without prefix). table_description -> table_descriptions to match Chroma.
# Relationships: (1) DBSchema docs include metadata.relationships per table; (2) TableDescription docs
# include metadata.relationships per table; (3) standalone RELATIONSHIP docs are written to db_schema by
# ProjectReader._process_relationships (inherited, so they go to this Qdrant db_schema store).
COLLECTION_NAMES = {
    "db_schema": "db_schema",
    "table_description": "table_descriptions",
    "historical_question": "historical_question",
    "instructions": "instructions",
    "project_meta": "project_meta",
    "sql_pairs": "sql_pairs",
    "alert_knowledge_base": "alert_knowledge_base",
    "column_metadata": "column_metadata",
    "sql_functions": "sql_functions",
}


class ProjectReaderQdrant(ProjectReader):
    """
    Indexes projects from sql_meta into Qdrant with core_* (or custom prefix) collections.
    Reuses all processors from ProjectReader; only document stores are Qdrant-backed.
    """

    def __init__(
        self,
        base_path: str = "../../data/sql_meta",
        qdrant_client=None,
        host: Optional[str] = None,
        port: int = 6333,
        collection_prefix: str = "core_",
        embeddings: Optional[OpenAIEmbeddings] = None,
    ):
        self.base_path = Path(base_path)
        self.collection_prefix = collection_prefix
        self._qdrant_client = qdrant_client
        self._qdrant_host = host or "localhost"
        self._qdrant_port = port
        logger.info(
            "Initializing ProjectReaderQdrant with base_path=%s, collection_prefix=%s",
            self.base_path,
            collection_prefix,
        )

        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY,
        )

        self._init_document_stores()
        self._init_components()
        self._init_alert_knowledge_base()
        self._init_column_metadata_store()
        self._init_sql_functions_store()
        logger.info("ProjectReaderQdrant initialization complete")

    def _get_qdrant_client(self):
        if self._qdrant_client is not None:
            return self._qdrant_client
        from app.storage.qdrant_store import QDRANT_AVAILABLE, QdrantClient
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client and langchain-qdrant are required for ProjectReaderQdrant")
        return QdrantClient(host=self._qdrant_host, port=self._qdrant_port)

    def _init_document_stores(self):
        """Build Qdrant document stores for each collection with collection_prefix."""
        logger.info("Setting up Qdrant document stores with prefix %s", self.collection_prefix)
        client = self._get_qdrant_client()
        self.document_stores = {}
        for key, name in COLLECTION_NAMES.items():
            collection_name = f"{self.collection_prefix}{name}"
            try:
                store = DocumentQdrantStore(
                    qdrant_client=client,
                    collection_name=collection_name,
                    embeddings_model=self.embeddings,
                )
                self.document_stores[key] = store
            except Exception as e:
                logger.warning("Failed to create Qdrant store %s: %s", collection_name, e)
        logger.info("Qdrant document stores initialized: %s", list(self.document_stores.keys()))

    def _init_components(self):
        """Same components as ProjectReader but using self.document_stores (Qdrant)."""
        logger.info("Setting up indexing components (Qdrant-backed)")
        self.components = {
            "db_schema": DBSchema(
                document_store=self.document_stores["db_schema"],
                embedder=self.embeddings,
            ),
            "table_description": TableDescription(
                document_store=self.document_stores["table_description"],
                embedder=self.embeddings,
            ),
            "historical_question": HistoricalQuestion(
                document_store=self.document_stores["historical_question"],
                embedder=self.embeddings,
            ),
            "instructions": Instructions(
                document_store=self.document_stores["instructions"],
                embedder=self.embeddings,
            ),
            "project_meta": ProjectMeta(
                document_store=self.document_stores["project_meta"],
            ),
            "sql_pairs": SqlPairs(
                document_store=self.document_stores["sql_pairs"],
                embedder=self.embeddings,
            ),
        }
        logger.info("All components initialized successfully")

    def _init_alert_knowledge_base(self):
        if "alert_knowledge_base" in self.document_stores:
            self.alert_knowledge_store = self.document_stores["alert_knowledge_base"]
            self._populate_alert_knowledge_base()
        else:
            self.alert_knowledge_store = None

    def _init_column_metadata_store(self):
        self.column_metadata_store = self.document_stores.get("column_metadata")

    def _init_sql_functions_store(self):
        self.sql_functions_store = self.document_stores.get("sql_functions")

    def list_projects(self, project_name_prefix: Optional[str] = None) -> List[str]:
        """
        List project keys under base_path (sql_meta) that have project_metadata.json.
        If project_name_prefix is set (e.g. "core_"), only include dirs whose name starts with that prefix.
        """
        projects = []
        if not self.base_path.exists():
            logger.warning("Base path does not exist: %s", self.base_path)
            return projects
        for path in self.base_path.iterdir():
            if not path.is_dir():
                continue
            if project_name_prefix and not path.name.startswith(project_name_prefix):
                continue
            if (path / "project_metadata.json").exists():
                projects.append(path.name)
        return sorted(projects)

    async def index_project(self, project_key: str) -> Dict[str, Any]:
        """Read and index a single project into Qdrant. Returns project data from read_project."""
        return await self.read_project(project_key)

    async def index_all_core_projects(
        self, project_name_prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all projects (optionally filtered by project_name_prefix), then read/index each.
        Returns list of project data dicts.
        """
        projects = self.list_projects(project_name_prefix=project_name_prefix)
        logger.info("Indexing %s projects into Qdrant", len(projects))
        results = []
        for key in projects:
            try:
                data = await self.read_project(key)
                results.append(data)
            except Exception as e:
                logger.exception("Failed to index project %s: %s", key, e)
        return results

    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete project from Qdrant stores only (no Chroma project collection)."""
        logger.info("Starting deletion of project from Qdrant: %s", project_id)
        deletion_results = {
            "project_id": project_id,
            "components_deleted": {},
            "total_documents_deleted": 0,
            "errors": [],
        }
        try:
            for component_name, component in self.components.items():
                try:
                    if hasattr(component, "clean"):
                        await component.clean(project_id=project_id)
                        deletion_results["components_deleted"][component_name] = "cleaned"
                    elif hasattr(component, "_document_store"):
                        result = component._document_store.delete_by_project_id(project_id)
                        deletion_results["components_deleted"][component_name] = result
                        deletion_results["total_documents_deleted"] += result.get(
                            "documents_deleted", 0
                        )
                except Exception as e:
                    deletion_results["errors"].append(
                        f"{component_name}: {e}"
                    )
                    deletion_results["components_deleted"][component_name] = f"error: {e}"

            for store_name in ("column_metadata", "sql_functions"):
                store = getattr(self, f"{store_name}_store", None)
                if store is not None:
                    try:
                        result = store.delete_by_project_id(project_id)
                        deletion_results["components_deleted"][store_name] = result
                        deletion_results["total_documents_deleted"] += result.get(
                            "documents_deleted", 0
                        )
                    except Exception as e:
                        deletion_results["errors"].append(f"{store_name}: {e}")

            logger.info(
                "Qdrant project deletion completed for %s. Total deleted: %s",
                project_id,
                deletion_results["total_documents_deleted"],
            )
        except Exception as e:
            deletion_results["errors"].append(str(e))
        return deletion_results


async def main():
    """
    Same flow as project_reader.main(): read each test project, log summary, then run search tests.
    Uses ProjectReaderQdrant and core_* Qdrant collections with project_id filter instead of Chroma project_* collections.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    base_path = Path("../../data/sql_meta")
    host = getattr(settings, "QDRANT_HOST", None) or "localhost"
    port = int(getattr(settings, "QDRANT_PORT", 6333))

    reader = ProjectReaderQdrant(base_path=base_path, host=host, port=port)

    test_projects = [
        "csod_risk_attrition",
        "csodworkday",
        "cornerstone_learning",
        "cornerstone_talent",
        "cornerstone",
        "sumtotal_learn",
        "cve_data",
    ]
    # Restrict to projects that exist on disk
    test_projects = [p for p in test_projects if (reader.base_path / p).exists()]
    if not test_projects:
        logger.warning("No test projects found under %s. Create sql_meta with project_metadata.json per project.", reader.base_path)
        return

    for project in test_projects:
        try:
            logger.info("\n%s", "=" * 50)
            logger.info("Testing project: %s", project)
            logger.info("%s", "=" * 50)

            project_data = await reader.read_project(project)

            logger.info("\nProject ID: %s", project_data["project_id"])

            logger.info("\nTables:")
            for table in project_data["tables"]:
                logger.info("- %s (%s)", table["name"], table["display_name"])
                logger.info("  Description: %s", table["description"])
                logger.info("  Has MDL: %s", "mdl" in table)
                logger.info("  Has DDL: %s", "ddl" in table)
                if "mdl" in table:
                    mdl = table["mdl"]
                    logger.info("  MDL Catalog: %s", mdl.get("catalog"))
                    logger.info("  MDL Schema: %s", mdl.get("schema"))
                    logger.info("  MDL Models: %s", len(mdl.get("models", [])))
                    logger.info("  MDL Enums: %s", len(mdl.get("enums", [])))
                    logger.info("  MDL Metrics: %s", len(mdl.get("metrics", [])))
                    logger.info("  MDL Views: %s", len(mdl.get("views", [])))
                if "ddl" in table:
                    ddl = table["ddl"]
                    logger.info("  DDL Tables: %s", len(ddl.get("tables", [])))
                    logger.info("  DDL Views: %s", len(ddl.get("views", [])))
                    logger.info("  DDL Functions: %s", len(ddl.get("functions", [])))

            logger.info("\nKnowledge Base:")
            for kb in project_data["knowledge_base"]:
                logger.info("- %s (%s)", kb["name"], kb["display_name"])
                logger.info("  Description: %s", kb["description"])
                if "content" in kb:
                    content = kb["content"]
                    logger.info("  Knowledge Base Items: %s", len(content.get("knowledge_base", [])))
                    logger.info("  Examples: %s", len(content.get("examples", [])))
                    logger.info("  Tags: %s", len(content.get("tags", [])))

            logger.info("\nExamples:")
            for example in project_data["examples"]:
                logger.info("- %s (%s)", example["name"], example["display_name"])
                logger.info("  Description: %s", example["description"])
                if "content" in example:
                    content = example["content"]
                    logger.info("  SQL Pairs: %s", len(content.get("pairs", [])))
                    logger.info("  Metadata Fields: %s", len(content.get("metadata", {})))

            logger.info("\n%s", "=" * 50)
            logger.info("Testing Qdrant reading for project: %s", project)
            logger.info("%s", "=" * 50)

            project_id = project_data["project_id"]
            where_project = {"project_id": project_id}
            doc_store = reader.document_stores.get("db_schema") or next(iter(reader.document_stores.values()), None)
            if not doc_store:
                logger.error("No Qdrant document store available for search tests.")
                continue

            logger.info("\nTesting semantic search...")
            search_queries = [
                "What are the main tables in this project?",
                "Show me the data models and schemas",
                "What are the key metrics and KPIs?",
                "Explain the business logic and rules",
            ]
            for query in search_queries:
                logger.info("\nQuery: %s", query)
                try:
                    results = doc_store.semantic_search(query, k=3, where=where_project)
                    logger.info("Found %s results:", len(results))
                    for i, result in enumerate(results[:2], 1):
                        logger.info("  Result %s:", i)
                        logger.info("    Score: %s", result.get("score", 0))
                        content = result.get("content", "") or result.get("data", "")
                        logger.info("    Content: %s...", (content[:100] + "..." if len(content) > 100 else content))
                        logger.info("    ID: %s", result.get("id"))
                except Exception as e:
                    logger.error("Error in semantic search: %s", e)

            logger.info("\nTesting semantic search with BM25 ranking...")
            bm25_query = "What are the main tables and their relationships?"
            try:
                bm25_fn = getattr(doc_store, "semantic_search_with_bm25", None)
                if callable(bm25_fn):
                    bm25_results = bm25_fn(bm25_query, k=3, where=where_project)
                    logger.info("Found %s BM25 results:", len(bm25_results))
                    for i, result in enumerate(bm25_results[:2], 1):
                        logger.info("  Result %s:", i)
                        logger.info("    Combined Score: %s", result.get("combined_score", result.get("score")))
                        logger.info("    Vector Score: %s", result.get("vector_score"))
                        logger.info("    BM25 Score: %s", result.get("bm25_score"))
                        content = result.get("content", "") or result.get("data", "")
                        logger.info("    Content: %s...", (content[:100] + "..." if len(content) > 100 else content))
                else:
                    logger.info("BM25 not available on this store, skipping.")
            except Exception as e:
                logger.error("Error in BM25 search: %s", e)

            logger.info("\nTesting semantic search with TF-IDF...")
            tfidf_query = "What are the data models and business rules?"
            try:
                tfidf_fn = getattr(doc_store, "semantic_search_with_tfidf", None)
                if callable(tfidf_fn):
                    tfidf_results = tfidf_fn(tfidf_query, k=3, where=where_project)
                    logger.info("Found %s TF-IDF results:", len(tfidf_results))
                    for i, result in enumerate(tfidf_results[:2], 1):
                        logger.info("  Result %s:", i)
                        logger.info("    Combined Score: %s", result.get("combined_score", result.get("semantic_score")))
                        logger.info("    Semantic Score: %s", result.get("semantic_score"))
                        logger.info("    TF-IDF Score: %s", result.get("tfidf_score"))
                        content = result.get("content", "") or result.get("data", "")
                        logger.info("    Content: %s...", (content[:100] + "..." if len(content) > 100 else content))
                else:
                    logger.info("TF-IDF not available on this store, skipping.")
            except Exception as e:
                logger.error("Error in TF-IDF search: %s", e)

            logger.info("\nTesting search with metadata filters...")
            try:
                filtered_results = doc_store.semantic_search(
                    "table structure and schema",
                    k=3,
                    where=where_project,
                )
                logger.info("Found %s filtered results:", len(filtered_results))
                for i, result in enumerate(filtered_results[:2], 1):
                    logger.info("  Result %s:", i)
                    logger.info("    Score: %s", result.get("score", 0))
                    content = result.get("content", "") or result.get("data", "")
                    logger.info("    Content: %s...", (content[:100] + "..." if len(content) > 100 else content))
                    logger.info("    Metadata: %s", result.get("metadata"))
            except Exception as e:
                logger.error("Error in filtered search: %s", e)

            logger.info("\nTesting TF-IDF only search...")
            try:
                tfidf_only_fn = getattr(doc_store, "tfidf_search", None)
                if callable(tfidf_only_fn):
                    tfidf_only_results = tfidf_only_fn("data models tables", k=3, where=where_project)
                    logger.info("Found %s TF-IDF only results:", len(tfidf_only_results))
                    for i, result in enumerate(tfidf_only_results[:2], 1):
                        logger.info("  Result %s:", i)
                        logger.info("    Score: %s", result.get("score", 0))
                        content = result.get("content", "") or result.get("data", "")
                        logger.info("    Content: %s...", (content[:100] + "..." if len(content) > 100 else content))
                else:
                    logger.info("TF-IDF only not available on this store, skipping.")
            except Exception as e:
                logger.error("Error in TF-IDF only search: %s", e)

        except Exception as e:
            logger.error("Error processing project %s: %s", project, e)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
