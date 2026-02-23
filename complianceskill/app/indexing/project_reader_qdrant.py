"""
Project reader that indexes sql_meta projects into Qdrant using knowledge's indexing
processors (DBSchemaProcessor, TableDescriptionProcessor) with collection names prefixed
by collection_prefix (e.g. core_db_schema, core_table_descriptions). Keeps transform
logic in existing processors; only the store backend and project discovery live here.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_openai import OpenAIEmbeddings

from app.core.settings import get_settings
from app.storage.documents import DocumentQdrantStore
from app.storage.query.collection_factory import CORE_COLLECTION_NAMES, get_core_collection_name
from app.indexing.processors import DBSchemaProcessor, TableDescriptionProcessor, ColumnMetadataProcessor
from app.indexing.ddl_utils import generate_and_log_table_ddl

logger = logging.getLogger(__name__)
settings = get_settings()


class ProjectReaderQdrant:
    """
    Indexes projects from sql_meta into Qdrant with core_* (or custom prefix) collections.
    Uses knowledge's DBSchemaProcessor and TableDescriptionProcessor; only document
    stores are Qdrant-backed with the given prefix.
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
        self._init_processors()
        logger.info("ProjectReaderQdrant initialization complete")

    def _get_qdrant_client(self):
        if self._qdrant_client is not None:
            return self._qdrant_client
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            raise ImportError(
                "qdrant-client is required for ProjectReaderQdrant. "
                "Install with: pip install qdrant-client langchain-qdrant"
            )
        return QdrantClient(host=self._qdrant_host, port=self._qdrant_port)

    def _init_document_stores(self):
        """Build Qdrant document stores for each core collection (names from collection_factory)."""
        logger.info("Setting up Qdrant document stores with prefix %s", self.collection_prefix)
        client = self._get_qdrant_client()
        self.document_stores = {}
        for store_key in CORE_COLLECTION_NAMES:
            collection_name = get_core_collection_name(store_key, prefix=self.collection_prefix)
            try:
                store = DocumentQdrantStore(
                    qdrant_client=client,
                    collection_name=collection_name,
                    embeddings_model=self.embeddings,
                )
                self.document_stores[store_key] = store
            except Exception as e:
                logger.warning("Failed to create Qdrant store %s: %s", collection_name, e)
        logger.info("Qdrant document stores initialized: %s", list(self.document_stores.keys()))

    def _init_processors(self):
        """Initialize knowledge's schema, table description, and column metadata processors."""
        self.db_schema_processor = DBSchemaProcessor(column_batch_size=200)
        self.table_description_processor = TableDescriptionProcessor()
        self.column_metadata_processor = ColumnMetadataProcessor()

    async def read_project(self, project_key: str) -> Dict[str, Any]:
        """
        Read project metadata and file summaries from disk (no indexing).
        Returns structure aligned with agents ProjectReader.read_project for testing/logging.
        """
        project_path = self.base_path / project_key
        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")

        metadata = self._read_project_metadata(project_path)
        project_id = metadata.get("project_id") or project_key

        tables = []
        for table_meta in metadata.get("tables", []):
            table_data = {
                "name": table_meta.get("name", ""),
                "display_name": table_meta.get("display_name", ""),
                "description": table_meta.get("description", ""),
            }
            mdl_file = table_meta.get("mdl_file")
            if mdl_file:
                mdl_path = project_path / mdl_file
                if mdl_path.exists():
                    try:
                        with open(mdl_path, "r") as f:
                            mdl_dict = json.load(f)
                        table_data["mdl"] = {
                            "catalog": mdl_dict.get("catalog"),
                            "schema": mdl_dict.get("schema"),
                            "models": mdl_dict.get("models", []),
                            "enums": mdl_dict.get("enums", []),
                            "metrics": mdl_dict.get("metrics", []),
                            "views": mdl_dict.get("views", []),
                        }
                    except (json.JSONDecodeError, OSError) as e:
                        logger.warning("Could not read MDL %s: %s", mdl_path, e)
            tables.append(table_data)

        knowledge_base = []
        for kb_meta in metadata.get("knowledge_base", []):
            knowledge_base.append({
                "name": kb_meta.get("name", ""),
                "display_name": kb_meta.get("display_name", ""),
                "description": kb_meta.get("description", ""),
            })

        examples = []
        for ex_meta in metadata.get("examples", []):
            examples.append({
                "name": ex_meta.get("name", ""),
                "display_name": ex_meta.get("display_name", ""),
                "description": ex_meta.get("description", ""),
            })

        return {
            "project_id": project_id,
            "tables": tables,
            "knowledge_base": knowledge_base,
            "examples": examples,
        }

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

    def _read_project_metadata(self, project_path: Path) -> Dict:
        """Read project_metadata.json."""
        metadata_path = project_path / "project_metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Project metadata not found: {metadata_path}")
        with open(metadata_path, "r") as f:
            return json.load(f)

    async def index_project(self, project_key: str) -> Dict[str, Any]:
        """
        Read project from sql_meta and index into Qdrant (db_schema, table_descriptions).
        Returns a summary dict with project_id, tables_indexed, and per-store counts.
        """
        project_path = self.base_path / project_key
        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")

        metadata = self._read_project_metadata(project_path)
        project_id = metadata.get("project_id") or project_key
        tables_meta = metadata.get("tables", [])

        result = {
            "project_id": project_id,
            "project_key": project_key,
            "tables_indexed": 0,
            "db_schema_documents": 0,
            "table_descriptions_documents": 0,
            "column_metadata_documents": 0,
            "errors": [],
        }

        for table_meta in tables_meta:
            mdl_file = table_meta.get("mdl_file")
            if not mdl_file:
                continue
            mdl_path = project_path / mdl_file
            if not mdl_path.exists():
                logger.warning("MDL file not found: %s", mdl_path)
                result["errors"].append(f"mdl not found: {mdl_file}")
                continue

            with open(mdl_path, "r") as f:
                mdl_str = f.read()
            try:
                mdl_dict = json.loads(mdl_str)
            except json.JSONDecodeError as e:
                result["errors"].append(f"invalid json {mdl_file}: {e}")
                continue

            # Generate and log DDL for each table (same logs as agents _build_table_ddl / _generate_table_ddl)
            logger.info("Generating DDL for tables in project %s", project_id)
            table_ddl_map = generate_and_log_table_ddl(mdl_dict, project_id=project_id)
            logger.info("DDL generation complete: %s tables processed", len(table_ddl_map))

            # Index DB schema (include full DDL in table definitions/comment for retrieval)
            db_store = self.document_stores.get("db_schema")
            if db_store:
                try:
                    docs = await self.db_schema_processor.process_mdl(
                        mdl=mdl_dict,
                        project_id=project_id,
                        product_name=project_id,
                        table_ddl_map=table_ddl_map,
                    )
                    if docs:
                        db_store.add_documents(docs)
                        result["db_schema_documents"] += len(docs)
                except Exception as e:
                    logger.exception("DB schema processing failed for %s: %s", mdl_file, e)
                    result["errors"].append(f"db_schema {mdl_file}: {e}")

            # Index table descriptions (key matches agents: table_description; include DDL in content)
            td_store = self.document_stores.get("table_description")
            if td_store:
                try:
                    docs = await self.table_description_processor.process_mdl(
                        mdl=mdl_dict,
                        project_id=project_id,
                        product_name=project_id,
                        table_ddl_map=table_ddl_map,
                    )
                    if docs:
                        td_store.add_documents(docs)
                        result["table_descriptions_documents"] += len(docs)
                except Exception as e:
                    logger.exception("Table description processing failed for %s: %s", mdl_file, e)
                    result["errors"].append(f"table_descriptions {mdl_file}: {e}")

            # Index column metadata (same logging as agents _process_column_metadata)
            col_store = self.document_stores.get("column_metadata")
            if col_store:
                try:
                    logger.info("Processing column metadata with MDL for project: %s", project_id)
                    col_docs, col_result = await self.column_metadata_processor.process_mdl(
                        mdl=mdl_dict,
                        project_id=project_id,
                        product_name=project_id,
                    )
                    if col_docs:
                        col_store.add_documents(col_docs)
                        result["column_metadata_documents"] += col_result.get("documents_written", len(col_docs))
                    logger.info(
                        "Column metadata processing complete: documents_written=%s, total_columns=%s",
                        col_result.get("documents_written", 0),
                        col_result.get("total_columns", 0),
                    )
                except Exception as e:
                    logger.exception("Column metadata processing failed for %s: %s", mdl_file, e)
                    result["errors"].append(f"column_metadata {mdl_file}: {e}")

            result["tables_indexed"] += 1

        logger.info(
            "Indexed project %s: %s tables, %s db_schema docs, %s table_description docs, %s column_metadata docs",
            project_id,
            result["tables_indexed"],
            result["db_schema_documents"],
            result["table_descriptions_documents"],
            result["column_metadata_documents"],
        )
        return result

    async def index_all_core_projects(
        self, project_name_prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all projects (optionally filtered by project_name_prefix), then index each into Qdrant.
        Returns list of per-project result dicts.
        """
        projects = self.list_projects(project_name_prefix=project_name_prefix)
        logger.info("Indexing %s projects into Qdrant", len(projects))
        results = []
        for key in projects:
            try:
                data = await self.index_project(key)
                results.append(data)
            except Exception as e:
                logger.exception("Failed to index project %s: %s", key, e)
                results.append({"project_key": key, "error": str(e), "tables_indexed": 0})
        return results

    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete all documents for the given project_id from core_* Qdrant collections."""
        logger.info("Deleting project from Qdrant: %s", project_id)
        deletion_results = {
            "project_id": project_id,
            "components_deleted": {},
            "total_documents_deleted": 0,
            "errors": [],
        }
        for store_name, store in self.document_stores.items():
            try:
                result = store.delete_by_project_id(project_id)
                n = result.get("documents_deleted", 0)
                deletion_results["components_deleted"][store_name] = result
                deletion_results["total_documents_deleted"] += n
            except Exception as e:
                deletion_results["errors"].append(f"{store_name}: {e}")
                deletion_results["components_deleted"][store_name] = {"error": str(e)}
        logger.info(
            "Deleted project %s from Qdrant: %s documents",
            project_id,
            deletion_results["total_documents_deleted"],
        )
        return deletion_results


def _resolve_sql_meta_path(settings) -> str:
    """
    Resolve SQL_META_PATH for project discovery.
    - If SQL_META_PATH is absolute (e.g. /Users/you/flowharmonicai/data/sql_meta), it is used as-is.
    - If relative (e.g. ../../data/sql_meta), it is resolved against settings.BASE_DIR.
    Set SQL_META_PATH to the full path in .env to avoid any resolution issues.
    """
    raw = getattr(settings, "SQL_META_PATH", "") or "../../data/sql_meta"
    p = Path(raw)
    if p.is_absolute():
        resolved = str(p)
        logger.info("Using SQL_META_PATH as absolute: %s", resolved)
        return resolved
    resolved = str((settings.BASE_DIR / raw).resolve())
    logger.info("Resolved relative SQL_META_PATH (BASE_DIR=%s): %s", settings.BASE_DIR, resolved)
    return resolved


# Default test project list (override or use list_projects() for live list)
TEST_PROJECTS = [
    "csod_risk_attrition",
    "csodworkday",
    "cornerstone_learning",
    "cornerstone_talent",
    "cornerstone",
    "sumtotal_learn",
    "cve_data",
]

SEARCH_QUERIES = [
    "What are the main tables in this project?",
    "Show me the data models and schemas",
    "What are the key metrics and KPIs?",
    "Explain the business logic and rules",
]


def _log_project_summary(project_data: Dict[str, Any]) -> None:
    """Log project summary in same style as agents project_reader test block."""
    logger.info("Project ID: %s", project_data["project_id"])
    logger.info("Tables:")
    for table in project_data["tables"]:
        logger.info("  - %s (%s)", table["name"], table["display_name"])
        logger.info("    Description: %s", table.get("description", ""))
        logger.info("    Has MDL: %s", "mdl" in table)
        if "mdl" in table:
            mdl = table["mdl"]
            logger.info("    MDL Catalog: %s", mdl.get("catalog"))
            logger.info("    MDL Schema: %s", mdl.get("schema"))
            logger.info("    MDL Models: %s", len(mdl.get("models", [])))
            logger.info("    MDL Enums: %s", len(mdl.get("enums", [])))
            logger.info("    MDL Metrics: %s", len(mdl.get("metrics", [])))
            logger.info("    MDL Views: %s", len(mdl.get("views", [])))
    logger.info("Knowledge Base:")
    for kb in project_data["knowledge_base"]:
        logger.info("  - %s (%s)", kb["name"], kb["display_name"])
        logger.info("    Description: %s", kb.get("description", ""))
    logger.info("Examples:")
    for example in project_data["examples"]:
        logger.info("  - %s (%s)", example["name"], example["display_name"])
        logger.info("    Description: %s", example.get("description", ""))


def _run_qdrant_search_tests(reader: "ProjectReaderQdrant", project_id: str) -> None:
    """Run semantic (and optional BM25/TF-IDF) search tests against core_* stores filtered by project_id."""
    project_filter = {"project_id": project_id}
    for store_name, doc_store in reader.document_stores.items():
        logger.info("Testing Qdrant store '%s' for project_id=%s", store_name, project_id)
        # Semantic search
        for query in SEARCH_QUERIES[:2]:
            try:
                results = doc_store.semantic_search(query, k=3, where=project_filter)
                logger.info("  Query: %s -> %s results", query, len(results))
                for i, result in enumerate(results[:2], 1):
                    content = result.get("content", result.get("data", "")) or ""
                    score = result.get("score", 0)
                    logger.info("    Result %s: score=%.4f content=%s...", i, score, (content[:80] + "..." if len(content) > 80 else content))
            except Exception as e:
                logger.error("  Error semantic_search: %s", e)
        # Optional: BM25 / TF-IDF if the store supports them (e.g. Chroma); QdrantStore may only have semantic_search
        bm25_fn = getattr(doc_store, "semantic_search_with_bm25", None)
        if callable(bm25_fn):
            try:
                bm25_results = bm25_fn("What are the main tables and their relationships?", k=3, where=project_filter)
                logger.info("  BM25 search: %s results", len(bm25_results))
            except Exception as e:
                logger.error("  Error BM25: %s", e)
        tfidf_fn = getattr(doc_store, "semantic_search_with_tfidf", None)
        if callable(tfidf_fn):
            try:
                tfidf_results = tfidf_fn("What are the data models and business rules?", k=3, where=project_filter)
                logger.info("  TF-IDF search: %s results", len(tfidf_results))
            except Exception as e:
                logger.error("  Error TF-IDF: %s", e)
        tfidf_only_fn = getattr(doc_store, "tfidf_search", None)
        if callable(tfidf_only_fn):
            try:
                tfidf_only_results = tfidf_only_fn("data models tables", k=3, where=project_filter)
                logger.info("  TF-IDF only search: %s results", len(tfidf_only_results))
            except Exception as e:
                logger.error("  Error TF-IDF only: %s", e)
        # Metadata filter (e.g. by type/category if present)
        try:
            filtered = doc_store.semantic_search("table structure and schema", k=3, where=project_filter)
            logger.info("  Filtered (project_id) search: %s results", len(filtered))
        except Exception as e:
            logger.error("  Error filtered search: %s", e)


def _parse_run_mode() -> str:
    """Run mode: 'index' = build schemas only, 'test' = read+search only, 'both' = index then test. Env RUN_MODE or argv."""
    import os
    import sys
    mode = (os.environ.get("RUN_MODE") or "").strip().lower()
    if not mode and len(sys.argv) > 1:
        mode = sys.argv[1].strip().lower()
    if mode not in ("index", "test", "both"):
        mode = "both"
    return mode


async def _main():
    """
    Build all schemas (db_schema, table_descriptions, column_metadata) and optionally run read+search tests.
    Uses .env: SQL_META_PATH, QDRANT_HOST, QDRANT_PORT, OPENAI_API_KEY. Optional: RUN_MODE.

    Run modes (env RUN_MODE or first arg):
      index  - Index all projects into Qdrant (builds all schemas; you'll see column metadata etc. logs).
      test   - Only list projects, read from disk, run Qdrant search tests (no indexing).
      both   - Default: index all projects first, then run tests.

    To build all schemas and see all logging:
      cd knowledge && RUN_MODE=index python -m app.indexing.project_reader_qdrant
      or
      cd knowledge && python -m app.indexing.project_reader_qdrant index
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    s = get_settings()
    base_path = _resolve_sql_meta_path(s)
    reader = ProjectReaderQdrant(
        base_path=base_path,
        host=s.QDRANT_HOST or "localhost",
        port=s.QDRANT_PORT,
        collection_prefix="core_",
    )
    projects = reader.list_projects()
    logger.info("Projects under %s: %s", base_path, projects)
    if not projects:
        logger.warning("No projects found. Put sql_meta dir at %s with project_metadata.json per project.", base_path)
        return

    run_mode = _parse_run_mode()
    logger.info("Run mode: %s (set RUN_MODE=index|test|both or pass as first arg)", run_mode)

    if run_mode in ("index", "both"):
        logger.info("Indexing all projects into Qdrant (db_schema, table_descriptions, column_metadata)...")
        index_results = await reader.index_all_core_projects()
        logger.info("Indexed %s projects: %s", len(index_results), index_results)

    if run_mode in ("test", "both"):
        test_projects = projects
        for project in test_projects:
            try:
                logger.info("%s", "=" * 50)
                logger.info("Testing project: %s", project)
                logger.info("%s", "=" * 50)
                project_data = await reader.read_project(project)
                _log_project_summary(project_data)
                logger.info("%s", "=" * 50)
                logger.info("Testing Qdrant reading for project: %s", project)
                logger.info("%s", "=" * 50)
                _run_qdrant_search_tests(reader, project_data["project_id"])
            except Exception as e:
                logger.exception("Error processing project %s: %s", project, e)


if __name__ == "__main__":
    asyncio.run(_main())
