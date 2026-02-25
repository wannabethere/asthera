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
from app.agents.retrieval.retrieval_helper import STORE_TO_COLLECTION

logger = logging.getLogger("genieml-agents")
settings = get_settings()

# Use same collection names as retrieval_helper so indexing populates the collections retrieval queries.
# Keys = store names; values = full Qdrant collection names (core_db_schema, core_table_descriptions, etc).
COLLECTION_NAMES = STORE_TO_COLLECTION


class ProjectReaderQdrant(ProjectReader):
    """
    Indexes projects from sql_meta into Qdrant with core_* (or custom prefix) collections.
    Reuses all processors from ProjectReader; only document stores are Qdrant-backed.
    """

    def __init__(
        self,
        base_path: str = None,
        qdrant_client=None,
        host: Optional[str] = None,
        port: int = 6333,
        collection_prefix: str = "",
        embeddings: Optional[OpenAIEmbeddings] = None,
        preview: bool = False,
        ds_functions_base_path: str = None,
    ):
        base_path = base_path or str(settings.BASE_DIR / "data" / "sql_meta")
        ds_functions_base_path = ds_functions_base_path or str(settings.BASE_DIR / "data" / "sql_functions")
        self.base_path = Path(base_path)
        self.ds_functions_base_path = Path(ds_functions_base_path)
        self.collection_prefix = collection_prefix
        self._qdrant_client = qdrant_client
        self._qdrant_host = host or "localhost"
        self._qdrant_port = port
        self.preview = preview
        self.preview_data = {} if preview else None
        logger.info(
            "Initializing ProjectReaderQdrant with base_path=%s, ds_functions=%s, collection_prefix=%s, preview=%s",
            self.base_path,
            self.ds_functions_base_path,
            collection_prefix,
            preview,
        )

        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY,
        )

        self._init_document_stores()
        ds_stores = [k for k in ("core_ds_functions", "core_ds_function_examples", "core_ds_function_instructions") if k in self.document_stores]
        logger.info("Core DS document stores created: %s", ds_stores)
        self._init_components()
        self._init_alert_knowledge_base()
        self._init_column_metadata_store()
        self._init_sql_functions_store()
        logger.info("Indexing core DS function collections from %s", self.ds_functions_base_path)
        self._index_core_ds_functions()
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
        logger.info(f"Indexing project {project_key} into Qdrant with enriched metadata (queryPatterns, useCases)")
        result = await self.read_project(project_key)
        
        # Log summary of indexed tables with queryPatterns/useCases and columns
        if "tables" in result:
            tables_with_properties = 0
            total_columns_indexed = 0
            for table in result["tables"]:
                if "mdl" in table:
                    mdl = table["mdl"]
                    # Check if any models have queryPatterns or useCases
                    models = mdl.get("models", [])
                    for model in models:
                        props = model.get("properties", {})
                        if props.get("queryPatterns") or props.get("useCases"):
                            tables_with_properties += 1
                            logger.info(f"Table {model.get('name')} has queryPatterns/useCases in MDL")
                            break
                        
                        # Check columns in MDL
                        columns = model.get("columns", [])
                        if columns:
                            total_columns_indexed += len(columns)
                            logger.info(f"Table {model.get('name')} has {len(columns)} columns in MDL")
                            # Log sample column information
                            if columns:
                                sample_col = columns[0]
                                col_name = sample_col.get("name", "")
                                col_props = sample_col.get("properties", {})
                                col_display = col_props.get("displayName", "")
                                col_desc = col_props.get("description", "")
                                logger.debug(f"  Sample column '{col_name}': displayName='{col_display}', description='{col_desc[:50] if col_desc else 'None'}...'")
            
            logger.info(f"Indexed {len(result['tables'])} tables, {tables_with_properties} with queryPatterns/useCases from MDL")
            logger.info(f"Total columns found in MDL: {total_columns_indexed}")
        
        return result

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


async def main(
    base_path: str = None,
    ds_functions_base_path: str = None,
    host: str = None,
    port: int = None,
):
    """
    Index sql_meta projects and core DS functions into Qdrant.
    Uses ProjectReaderQdrant and core_* Qdrant collections.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    base_path = base_path or str(settings.BASE_DIR / "data" / "sql_meta")
    ds_functions_base_path = ds_functions_base_path or str(settings.BASE_DIR / "data" / "sql_functions")
    host = host or getattr(settings, "QDRANT_HOST", None) or "localhost"
    port = port or int(getattr(settings, "QDRANT_PORT", 6333))

    reader = ProjectReaderQdrant(
        base_path=base_path,
        ds_functions_base_path=ds_functions_base_path,
        host=host,
        port=port,
    )

    test_projects = [
        "csod_risk_attrition",
        "csodworkday",
        "cornerstone_learning",
        "cornerstone_talent",
        "cornerstone",
        "sumtotal_learn",
        "cve_data",
        "hr_compliance_risk",
    ]
    # Restrict to projects that exist on disk
    test_projects = [p for p in test_projects if (reader.base_path / p).exists()]
    if not test_projects:
        logger.warning("No test projects found under %s. Create sql_meta with project_metadata.json per project.", reader.base_path)
        return

    for project in test_projects:
        try:
            logger.info("\n%s", "=" * 50)
            logger.info("Processing project: %s", project)
            logger.info("%s", "=" * 50)

            # First, read project metadata to get project_id
            project_path = reader.base_path / project
            metadata = reader._read_project_metadata(project_path)
            project_id = metadata.get("project_id")
            
            if not project_id:
                logger.warning("Project %s does not have project_id in metadata, skipping", project)
                continue
            
            logger.info("Project ID: %s", project_id)
            
            # Delete existing project data from Qdrant
            logger.info("\nDeleting existing project data from Qdrant...")
            try:
                deletion_result = await reader.delete_project(project_id)
                logger.info("Deletion completed:")
                logger.info("  Components deleted: %s", deletion_result.get("components_deleted", {}))
                logger.info("  Total documents deleted: %s", deletion_result.get("total_documents_deleted", 0))
                if deletion_result.get("errors"):
                    logger.warning("  Deletion errors: %s", deletion_result["errors"])
            except Exception as e:
                logger.warning("Error during deletion (may not exist): %s", e)
            
            # Re-index the project
            logger.info("\nRe-indexing project into Qdrant...")
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


async def test_retrieval():
    """
    Test retrieval using RetrievalHelper with Qdrant to retrieve 5 tables
    for the query: "What percentage of users meet their role's required skill proficiency?"
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    logger.info("\n%s", "=" * 80)
    logger.info("RETRIEVAL TEST")
    logger.info("%s", "=" * 80)
    
    try:
        # Get vector store client using dependencies (will use settings to determine Qdrant vs Chroma)
        from app.storage.vector_store import get_vector_store_client
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        
        # Get vector store client from settings (should be Qdrant based on VECTOR_STORE_TYPE)
        vector_store_client = get_vector_store_client()
        await vector_store_client.initialize()
        
        logger.info("Vector store client initialized: %s", type(vector_store_client).__name__)
        logger.info("Vector store type from settings: %s", settings.VECTOR_STORE_TYPE)
        if hasattr(settings, "QDRANT_HOST"):
            logger.info("Qdrant host: %s, port: %d", settings.QDRANT_HOST, settings.QDRANT_PORT)
        
        # Initialize RetrievalHelper with Qdrant and core_ prefix
        retrieval_helper = RetrievalHelper(
            vector_store_client=vector_store_client,
            core_collection_prefix=""
        )
        logger.info("RetrievalHelper initialized with core_collection_prefix='core_'")
        
        # Test query
        test_query = "skill gap analysis comparing user proficiency to role requirements"#"What percentage of users meet their role's required skill proficiency?"
        test_project_id = "hr_compliance_risk"  # Using hr_compliance_risk as it likely has user/skill/role data
        
        logger.info("\n%s", "-" * 80)
        logger.info("Test Query: %s", test_query)
        logger.info("Project ID: %s", test_project_id)
        logger.info("%s", "-" * 80)
        
        # Table retrieval configuration
        # Set allow_using_db_schemas_without_pruning=True to skip column pruning (LLM calls) for retrieval tests
        table_retrieval_config = {
            "table_retrieval_size": 10,
            "table_column_retrieval_size": 100,
            "allow_using_db_schemas_without_pruning": True  # Skip column pruning for retrieval tests
        }
        
        # Use core retrievers if available (for Qdrant with core_ prefix), otherwise use default retrievers
        if retrieval_helper._core_retrievers.get("table_retrieval"):
            logger.info("Using core table_retrieval retriever (Qdrant with core_ prefix)")
            table_retriever = retrieval_helper._core_retrievers["table_retrieval"]
        else:
            logger.info("Using default table_retrieval retriever")
            table_retriever = retrieval_helper.retrievers["table_retrieval"]
        
        # Retrieve database schemas using the table retriever directly
        logger.info("\nRetrieving database schemas...")
        schema_result = await table_retriever.run(
            query=test_query,
            project_id=test_project_id,
            tables=None,
            histories=None
        )
        
        # Format results to match get_database_schemas format
        if not schema_result or "retrieval_results" not in schema_result:
            logger.warning("No schema information found")
            schema_results = {
                "error": "No schema information found",
                "schemas": []
            }
        else:
            schemas = []
            for result in schema_result.get("retrieval_results", []):
                if isinstance(result, dict):
                    schemas.append({
                        "table_name": result.get("table_name", ""),
                        "table_ddl": result.get("table_ddl", ""),
                        "relationships": result.get("relationships", [])
                    })
            
            schema_results = {
                "schemas": schemas,
                "total_schemas": len(schemas),
                "project_id": test_project_id,
                "query": test_query,
                "has_calculated_field": schema_result.get("has_calculated_field", False),
                "has_metric": schema_result.get("has_metric", False)
            }
        
        # Check results
        if "error" in schema_results:
            logger.error("Retrieval error: %s", schema_results["error"])
            return False
        
        schemas = schema_results.get("schemas", [])
        total_schemas = len(schemas)
        
        logger.info("\n%s", "=" * 80)
        logger.info("RETRIEVAL RESULTS")
        logger.info("%s", "=" * 80)
        logger.info("Total schemas retrieved: %d", total_schemas)
        
        # Verify we retrieved 5 tables
        if total_schemas >= 5:
            logger.info("✅ SUCCESS: Retrieved %d tables (target: 5)", total_schemas)
        else:
            logger.warning("⚠️  Retrieved only %d tables (target: 5)", total_schemas)
        
        # Log details of retrieved tables
        logger.info("\nRetrieved Tables:")
        for i, schema in enumerate(schemas, 1):
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            relationships = schema.get("relationships", [])
            
            logger.info("\n%d. Table: %s", i, table_name)
            if table_ddl:
                # Show first few lines of DDL
                ddl_lines = table_ddl.split("\n")[:5]
                logger.info("   DDL Preview:")
                for line in ddl_lines:
                    logger.info("     %s", line)
                if len(table_ddl.split("\n")) > 5:
                    logger.info("     ... (%d more lines)", len(table_ddl.split("\n")) - 5)
            if relationships:
                logger.info("   Relationships: %d", len(relationships))
                for rel in relationships[:2]:  # Show first 2 relationships
                    if isinstance(rel, dict):
                        rel_name = rel.get("name", "")
                        rel_models = rel.get("models", [])
                        logger.info("     - %s: %s", rel_name, rel_models)
        
        # Additional metadata
        logger.info("\nMetadata:")
        logger.info("  Has calculated fields: %s", schema_results.get("has_calculated_field", False))
        logger.info("  Has metrics: %s", schema_results.get("has_metric", False))
        logger.info("  Query: %s", schema_results.get("query", ""))
        
        # ========================================================================
        # COLUMN RETRIEVAL TEST
        # ========================================================================
        logger.info("\n%s", "=" * 80)
        logger.info("COLUMN RETRIEVAL TEST")
        logger.info("%s", "=" * 80)
        
        column_retrieval_results = {}
        if schemas:
            # Retrieve column metadata for the first few tables
            logger.info("\nRetrieving column metadata for retrieved tables...")
            for i, schema in enumerate(schemas[:3], 1):  # Test first 3 tables
                table_name = schema.get("table_name", "")
                if not table_name:
                    continue
                
                logger.info("\n%d. Retrieving columns for table: %s", i, table_name)
                try:
                    column_metadata = await retrieval_helper._get_column_metadata_for_table(
                        table_name=table_name,
                        project_id=test_project_id
                    )
                    column_retrieval_results[table_name] = column_metadata
                    logger.info("   ✅ Retrieved %d columns", len(column_metadata))
                    
                    # Show sample columns
                    if column_metadata:
                        logger.info("   Sample columns:")
                        for col in column_metadata[:5]:  # Show first 5 columns
                            col_name = col.get("column_name", "")
                            col_type = col.get("type", "")
                            col_desc = col.get("description", "")
                            logger.info("     - %s (%s): %s", col_name, col_type, col_desc[:50] if col_desc else "No description")
                except Exception as e:
                    logger.warning("   ⚠️  Error retrieving columns for %s: %s", table_name, e)
                    column_retrieval_results[table_name] = []
        
        # ========================================================================
        # SQL EXAMPLES (SQL PAIRS) RETRIEVAL TEST
        # ========================================================================
        logger.info("\n%s", "=" * 80)
        logger.info("SQL EXAMPLES (SQL PAIRS) RETRIEVAL TEST")
        logger.info("%s", "=" * 80)
        
        logger.info("\nRetrieving SQL pairs/examples...")
        try:
            sql_pairs_results = await retrieval_helper.get_sql_pairs(
                query=test_query,
                project_id=test_project_id,
                similarity_threshold=0.3,
                max_retrieval_size=10
            )
            
            if "error" in sql_pairs_results:
                logger.warning("SQL pairs retrieval error: %s", sql_pairs_results["error"])
                sql_pairs = []
            else:
                sql_pairs = sql_pairs_results.get("sql_pairs", [])
                logger.info("✅ Retrieved %d SQL pairs", len(sql_pairs))
                
                # Show sample SQL pairs
                if sql_pairs:
                    logger.info("\nSample SQL pairs:")
                    for i, pair in enumerate(sql_pairs[:3], 1):  # Show first 3 pairs
                        logger.info("\n%d. Question: %s", i, pair.get("question", "")[:100])
                        logger.info("   SQL: %s", pair.get("sql", "")[:150] + "..." if len(pair.get("sql", "")) > 150 else pair.get("sql", ""))
                        logger.info("   Score: %.3f", pair.get("score", 0.0))
                        if pair.get("instructions"):
                            logger.info("   Instructions: %s", pair.get("instructions", "")[:100])
        except Exception as e:
            logger.error("Error retrieving SQL pairs: %s", e)
            sql_pairs = []
        
        # ========================================================================
        # INSTRUCTIONS RETRIEVAL TEST
        # ========================================================================
        logger.info("\n%s", "=" * 80)
        logger.info("INSTRUCTIONS RETRIEVAL TEST")
        logger.info("%s", "=" * 80)
        
        logger.info("\nRetrieving instructions...")
        try:
            instructions_results = await retrieval_helper.get_instructions(
                query=test_query,
                project_id=test_project_id,
                similarity_threshold=0.7,
                top_k=10
            )
            
            if "error" in instructions_results:
                logger.warning("Instructions retrieval error: %s", instructions_results["error"])
                instructions = []
            else:
                instructions = instructions_results.get("instructions", [])
                logger.info("✅ Retrieved %d instructions", len(instructions))
                
                # Show sample instructions
                if instructions:
                    logger.info("\nSample instructions:")
                    for i, instruction in enumerate(instructions[:3], 1):  # Show first 3 instructions
                        logger.info("\n%d. Question: %s", i, instruction.get("question", "")[:100])
                        logger.info("   Instruction: %s", instruction.get("instruction", "")[:200] + "..." if len(instruction.get("instruction", "")) > 200 else instruction.get("instruction", ""))
                        if instruction.get("instruction_id"):
                            logger.info("   Instruction ID: %s", instruction.get("instruction_id"))
        except Exception as e:
            logger.error("Error retrieving instructions: %s", e)
            instructions = []
        
        # ========================================================================
        # SUMMARY
        # ========================================================================
        logger.info("\n%s", "=" * 80)
        logger.info("RETRIEVAL TEST SUMMARY")
        logger.info("%s", "=" * 80)
        
        logger.info("\n✅ Table Retrieval:")
        logger.info("   - Tables retrieved: %d", total_schemas)
        logger.info("   - Target: 5 tables")
        logger.info("   - Status: %s", "✅ PASSED" if total_schemas >= 5 else "⚠️  PARTIAL")
        
        logger.info("\n✅ Column Retrieval:")
        total_columns = sum(len(cols) for cols in column_retrieval_results.values())
        logger.info("   - Tables with columns retrieved: %d", len(column_retrieval_results))
        logger.info("   - Total columns retrieved: %d", total_columns)
        logger.info("   - Status: %s", "✅ PASSED" if total_columns > 0 else "⚠️  NO COLUMNS")
        
        logger.info("\n✅ SQL Examples (SQL Pairs):")
        logger.info("   - SQL pairs retrieved: %d", len(sql_pairs))
        logger.info("   - Status: %s", "✅ PASSED" if len(sql_pairs) > 0 else "⚠️  NO SQL PAIRS")
        
        logger.info("\n✅ Instructions:")
        logger.info("   - Instructions retrieved: %d", len(instructions))
        logger.info("   - Status: %s", "✅ PASSED" if len(instructions) > 0 else "⚠️  NO INSTRUCTIONS")
        
        logger.info("\n%s", "=" * 80)
        logger.info("RETRIEVAL TEST COMPLETED")
        logger.info("%s", "=" * 80)
        
        # Return True if we got at least 5 tables
        return total_schemas >= 5
        
    except Exception as e:
        logger.error("Error in retrieval test: %s", e)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        return False


if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(
        description="Index sql_meta projects and sql_functions into Qdrant. Run indexing, retrieval tests, or both."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="indexing",
        choices=["indexing", "retrieval", "indexing_and_retrieval"],
        help="indexing | retrieval | indexing_and_retrieval (default: indexing)",
    )
    parser.add_argument(
        "--base-path",
        default=None,
        help="Path to sql_meta directory (default: BASE_DIR/data/sql_meta)",
    )
    parser.add_argument(
        "--ds-functions-path",
        default=None,
        help="Path to sql_functions directory (default: BASE_DIR/data/sql_functions)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Qdrant host (default: localhost or QDRANT_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Qdrant port (default: 6333 or QDRANT_PORT)",
    )
    args = parser.parse_args()

    if args.mode == "retrieval":
        asyncio.run(test_retrieval())
    elif args.mode == "indexing":
        asyncio.run(main(
            base_path=args.base_path,
            ds_functions_base_path=args.ds_functions_path,
            host=args.host,
            port=args.port,
        ))
    elif args.mode == "indexing_and_retrieval":
        asyncio.run(main(
            base_path=args.base_path,
            ds_functions_base_path=args.ds_functions_path,
            host=args.host,
            port=args.port,
        ))
        logger.info("\n\n")
        asyncio.run(test_retrieval())
