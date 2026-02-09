import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any, List

import chromadb
from langchain_openai import OpenAIEmbeddings

from app.indexing.db_schema import DBSchema
from app.indexing.table_description import TableDescription
from app.indexing.historical_question import HistoricalQuestion
from app.indexing.instructions import Instructions, Instruction
from app.indexing.project_meta import ProjectMeta
from app.indexing.sql_pairs import SqlPairs
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_doc_store_provider
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()

class PreviewDocumentStore:
    """Wrapper around DocumentChromaStore that collects documents for preview instead of writing."""
    def __init__(self, store, collection_name: str, preview_data: Dict):
        self._store = store
        self._collection_name = collection_name
        self._preview_data = preview_data
        
    def _collect_documents(self, docs: List[Any]):
        """Collect documents for preview format."""
        preview_docs = []
        for doc in docs:
            if hasattr(doc, 'page_content') and hasattr(doc, 'metadata'):
                preview_docs.append({
                    "page_content": doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                    "metadata": doc.metadata
                })
            elif isinstance(doc, dict):
                # Handle both LangchainDocument-like dicts and metadata/data dicts
                if 'page_content' in doc and 'metadata' in doc:
                    preview_docs.append({
                        "page_content": doc['page_content'][:500] + "..." if len(doc['page_content']) > 500 else doc['page_content'],
                        "metadata": doc['metadata']
                    })
                else:
                    preview_docs.append({
                        "data": doc.get("data", "")[:500] + "..." if len(str(doc.get("data", ""))) > 500 else doc.get("data", ""),
                        "metadata": doc.get("metadata", {})
                    })
            else:
                preview_docs.append({"content": str(doc)[:500]})
        
        # Store in preview data
        if self._collection_name not in self._preview_data:
            self._preview_data[self._collection_name] = []
        self._preview_data[self._collection_name].extend(preview_docs)
        
        # Return mock IDs
        return [f"preview_id_{i}" for i in range(len(preview_docs))]
        
    def add_documents(self, docs: List[Any]):
        """Collect documents for preview instead of writing.
        
        Returns:
            List of mock document IDs (for sync compatibility)
        """
        return self._collect_documents(docs)
    
    async def add_documents_async(self, docs: List[Any]):
        """Collect documents for preview instead of writing (async version).
        
        Returns:
            Dict with 'documents_written' key for compatibility with async callers
        """
        ids = self._collect_documents(docs)
        return {"documents_written": len(ids), "ids": ids}
    
    def __call__(self, *args, **kwargs):
        """Make the store callable - delegate to wrapped store."""
        return self._store(*args, **kwargs)
    
    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped store."""
        return getattr(self._store, name)

class ProjectReader:
    def __init__(self, base_path: str = "../../data/sql_meta", persistent_client: chromadb.PersistentClient = None, embeddings: OpenAIEmbeddings = None, preview: bool = False):
        logger.info(f"Initializing IndexingOrchestrator with base path: {base_path}, preview={preview}")
        self.base_path = Path(base_path)
        self.preview = preview
        print(f"Initializing IndexingOrchestrator with base path: {base_path}, preview={preview}")

        # Initialize preview data structure if in preview mode
        self.preview_data = {} if preview else None

        # Use provided client or get one from dependencies
        if persistent_client is not None:
            self.persistent_client = persistent_client
        else:
            from app.core.dependencies import get_chromadb_client
            self.persistent_client = get_chromadb_client()
            
        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        
        # Initialize document stores for each component
        logger.info("Initializing document stores")
        self._init_document_stores()
        
        # Initialize indexing components
        logger.info("Initializing indexing components")
        self._init_components()
        
        # Initialize alert knowledge base
        logger.info("Initializing alert knowledge base")
        self._init_alert_knowledge_base()
        
        # Initialize column metadata store
        logger.info("Initializing column metadata store")
        self._init_column_metadata_store()
        
        # Initialize SQL functions store
        logger.info("Initializing SQL functions store")
        self._init_sql_functions_store()
        
        logger.info("IndexingOrchestrator initialization complete")

    def _init_document_stores(self):
        """Initialize document stores for each component."""
        logger.info("Setting up document stores for each component")
        stores = get_doc_store_provider().stores
        
        # Wrap stores with preview wrapper if in preview mode
        if self.preview:
            self.document_stores = {}
            for name, store in stores.items():
                self.document_stores[name] = PreviewDocumentStore(store, name, self.preview_data)
            logger.info("Document stores initialized in PREVIEW mode")
        else:
            self.document_stores = stores
            logger.info("Document stores initialized successfully")

    def _init_components(self):
        """Initialize all indexing components."""
        logger.info("Setting up indexing components")
        self.components = {
            "db_schema": DBSchema(
                document_store=self.document_stores["db_schema"],
                embedder=self.embeddings
            ),
            "table_description": TableDescription(
                document_store=self.document_stores["table_description"],
                embedder=self.embeddings
            ),
            "historical_question": HistoricalQuestion(
                document_store=self.document_stores["historical_question"],
                embedder=self.embeddings
            ),
            "instructions": Instructions(
                document_store=self.document_stores["instructions"],
                embedder=self.embeddings
            ),
            "project_meta": ProjectMeta(
                document_store=self.document_stores["project_meta"]
            ),
            "sql_pairs": SqlPairs(
                document_store=self.document_stores["sql_pairs"],
                embedder=self.embeddings
            )
        }
        logger.info("All components initialized successfully")

    def _init_alert_knowledge_base(self):
        """Initialize alert knowledge base with domain-specific knowledge."""
        logger.info("Setting up alert knowledge base")
        
        try:
            # Use the document store provider to get the alert knowledge store
            # This ensures it uses the same path and configuration as other stores
            logger.info("Getting alert knowledge store from document store provider")
            
            # Check if alert_knowledge_base store exists in the provider
            if "alert_knowledge_base" in self.document_stores:
                self.alert_knowledge_store = self.document_stores["alert_knowledge_base"]
                logger.info("Using existing alert knowledge store from document store provider")
            else:
                # Create the alert knowledge store using the same pattern as other stores
                logger.info("Creating alert knowledge store using document store provider pattern")
                store = DocumentChromaStore(
                    persistent_client=self.persistent_client,
                    collection_name="alert_knowledge_base",
                    embeddings_model=self.embeddings,
                    tf_idf=True  # Enable TF-IDF for better search
                )
                # Wrap with preview wrapper if in preview mode
                if self.preview:
                    self.alert_knowledge_store = PreviewDocumentStore(store, "alert_knowledge_base", self.preview_data)
                else:
                    self.alert_knowledge_store = store
                # Add it to the document stores for consistency
                self.document_stores["alert_knowledge_base"] = self.alert_knowledge_store
            
            # Initialize with alert domain knowledge
            self._populate_alert_knowledge_base()
            
            logger.info("Alert knowledge base initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize alert knowledge base: {e}")
            # Create a minimal fallback store without TF-IDF
            logger.warning("Creating fallback alert knowledge store without TF-IDF")
            try:
                store = DocumentChromaStore(
                    persistent_client=self.persistent_client,
                    collection_name="alert_knowledge_base",
                    embeddings_model=self.embeddings,
                    tf_idf=False  # Disable TF-IDF to avoid collection creation issues
                )
                # Wrap with preview wrapper if in preview mode
                if self.preview:
                    self.alert_knowledge_store = PreviewDocumentStore(store, "alert_knowledge_base", self.preview_data)
                else:
                    self.alert_knowledge_store = store
                # Add it to the document stores for consistency
                self.document_stores["alert_knowledge_base"] = self.alert_knowledge_store
                logger.info("Fallback alert knowledge store created successfully")
            except Exception as fallback_error:
                logger.error(f"Fallback initialization also failed: {fallback_error}")
                self.alert_knowledge_store = None

    def _init_column_metadata_store(self):
        """Initialize column metadata store for storing detailed column information."""
        logger.info("Setting up column metadata store")
        
        try:
            # Create the column metadata store
            store = DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="column_metadata",
                embeddings_model=self.embeddings,
                tf_idf=True  # Enable TF-IDF for better search
            )
            # Wrap with preview wrapper if in preview mode
            if self.preview:
                self.column_metadata_store = PreviewDocumentStore(store, "column_metadata", self.preview_data)
            else:
                self.column_metadata_store = store
            # Add it to the document stores for consistency
            self.document_stores["column_metadata"] = self.column_metadata_store
            logger.info("Column metadata store initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize column metadata store: {e}")
            # Create a minimal fallback store without TF-IDF
            logger.warning("Creating fallback column metadata store without TF-IDF")
            try:
                store = DocumentChromaStore(
                    persistent_client=self.persistent_client,
                    collection_name="column_metadata",
                    embeddings_model=self.embeddings,
                    tf_idf=False  # Disable TF-IDF to avoid collection creation issues
                )
                # Wrap with preview wrapper if in preview mode
                if self.preview:
                    self.column_metadata_store = PreviewDocumentStore(store, "column_metadata", self.preview_data)
                else:
                    self.column_metadata_store = store
                # Add it to the document stores for consistency
                self.document_stores["column_metadata"] = self.column_metadata_store
                logger.info("Fallback column metadata store created successfully")
            except Exception as fallback_error:
                logger.error(f"Fallback initialization also failed: {fallback_error}")
                self.column_metadata_store = None

    def _init_sql_functions_store(self):
        """Initialize SQL functions store for storing SQL function definitions."""
        logger.info("Setting up SQL functions store")
        
        try:
            # Create the SQL functions store
            store = DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name="sql_functions",
                embeddings_model=self.embeddings,
                tf_idf=True  # Enable TF-IDF for better search
            )
            # Wrap with preview wrapper if in preview mode
            if self.preview:
                self.sql_functions_store = PreviewDocumentStore(store, "sql_functions", self.preview_data)
            else:
                self.sql_functions_store = store
            # Add it to the document stores for consistency
            self.document_stores["sql_functions"] = self.sql_functions_store
            logger.info("SQL functions store initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SQL functions store: {e}")
            # Create a minimal fallback store without TF-IDF
            logger.warning("Creating fallback SQL functions store without TF-IDF")
            try:
                store = DocumentChromaStore(
                    persistent_client=self.persistent_client,
                    collection_name="sql_functions",
                    embeddings_model=self.embeddings,
                    tf_idf=False  # Disable TF-IDF to avoid collection creation issues
                )
                # Wrap with preview wrapper if in preview mode
                if self.preview:
                    self.sql_functions_store = PreviewDocumentStore(store, "sql_functions", self.preview_data)
                else:
                    self.sql_functions_store = store
                # Add it to the document stores for consistency
                self.document_stores["sql_functions"] = self.sql_functions_store
                logger.info("Fallback SQL functions store created successfully")
            except Exception as fallback_error:
                logger.error(f"Fallback initialization also failed: {fallback_error}")
                self.sql_functions_store = None

    def _populate_alert_knowledge_base(self):
        """Populate the alert knowledge base with domain-specific knowledge."""
        logger.info("Populating alert knowledge base with domain knowledge")
        
        # Alert domain knowledge documents
        knowledge_docs = [
            # SQL Analysis Knowledge
            {
                "metadata": {
                    "type": "sql_analysis",
                    "category": "sql_patterns",
                    "domain": "alert_generation"
                },
                "data": "SELECT statements with GROUP BY indicate dimensions for alert breakdowns"
            },
            {
                "metadata": {
                    "type": "sql_analysis", 
                    "category": "aggregation_functions",
                    "domain": "alert_generation"
                },
                "data": "COUNT, SUM, AVG, MIN, MAX are common aggregation functions in metrics"
            },
            {
                "metadata": {
                    "type": "sql_analysis",
                    "category": "calculated_metrics", 
                    "domain": "alert_generation"
                },
                "data": "CASE WHEN statements often create calculated percentage metrics"
            },
            {
                "metadata": {
                    "type": "sql_analysis",
                    "category": "filters",
                    "domain": "alert_generation"
                },
                "data": "WHERE clauses define filters that should be preserved in alerts"
            },
            {
                "metadata": {
                    "type": "sql_analysis",
                    "category": "naming",
                    "domain": "alert_generation"
                },
                "data": "Column aliases with AS define meaningful metric names"
            },
            
            # Alert Pattern Knowledge
            {
                "metadata": {
                    "type": "alert_patterns",
                    "category": "percentage_metrics",
                    "domain": "alert_generation"
                },
                "data": "Percentage metrics often need threshold alerts when they exceed normal ranges"
            },
            {
                "metadata": {
                    "type": "alert_patterns",
                    "category": "status_metrics",
                    "domain": "alert_generation"
                },
                "data": "Status-based metrics (Completed, Assigned, Expired) indicate operational health"
            },
            {
                "metadata": {
                    "type": "alert_patterns",
                    "category": "training_metrics",
                    "domain": "alert_generation"
                },
                "data": "Training completion rates below 90% typically indicate issues"
            },
            {
                "metadata": {
                    "type": "alert_patterns",
                    "category": "expiry_metrics",
                    "domain": "alert_generation"
                },
                "data": "Expiry rates above 10% suggest timing or engagement problems"
            },
            {
                "metadata": {
                    "type": "alert_patterns",
                    "category": "assignment_metrics",
                    "domain": "alert_generation"
                },
                "data": "Assignment rates above 20% may indicate capacity issues"
            },
            
            # Lexy Feed Knowledge
            {
                "metadata": {
                    "type": "lexy_feed",
                    "category": "arima_conditions",
                    "domain": "alert_generation"
                },
                "data": "ARIMA conditions work best for time-series data with seasonal patterns"
            },
            {
                "metadata": {
                    "type": "lexy_feed",
                    "category": "threshold_conditions",
                    "domain": "alert_generation"
                },
                "data": "Threshold-based conditions are better for business rule violations"
            },
            {
                "metadata": {
                    "type": "lexy_feed",
                    "category": "percent_change",
                    "domain": "alert_generation"
                },
                "data": "Percent change alerts are ideal for detecting relative performance shifts"
            },
            {
                "metadata": {
                    "type": "lexy_feed",
                    "category": "value_thresholds",
                    "domain": "alert_generation"
                },
                "data": "Value-based thresholds work well for operational SLA monitoring"
            },
            {
                "metadata": {
                    "type": "lexy_feed",
                    "category": "resolution_frequency",
                    "domain": "alert_generation"
                },
                "data": "Daily resolution works for operational metrics, weekly for strategic KPIs"
            },
            
            # Business Context
            {
                "metadata": {
                    "type": "business_context",
                    "category": "training_metrics",
                    "domain": "alert_generation"
                },
                "data": "Training metrics should alert on completion rates, expiry trends, assignment backlogs"
            },
            {
                "metadata": {
                    "type": "business_context",
                    "category": "alert_frequency",
                    "domain": "alert_generation"
                },
                "data": "Operational alerts need immediate notification, strategic alerts can be weekly"
            },
            {
                "metadata": {
                    "type": "business_context",
                    "category": "breakdown_strategies",
                    "domain": "alert_generation"
                },
                "data": "Percentage-based metrics benefit from breakdown by training type or department"
            },
            {
                "metadata": {
                    "type": "business_context",
                    "category": "completion_tracking",
                    "domain": "alert_generation"
                },
                "data": "Completion tracking should include both absolute counts and percentages"
            }
        ]
        
        # Add knowledge documents to the store
        self.alert_knowledge_store.add_documents(knowledge_docs)
        logger.info(f"Added {len(knowledge_docs)} knowledge documents to alert knowledge base")

    def search_alert_knowledge(self, query: str, k: int = 5, search_type: str = "semantic") -> List[Dict]:
        """Search the alert knowledge base for relevant information.
        
        Args:
            query: Search query string
            k: Number of results to return
            search_type: Type of search ("semantic", "bm25", "tfidf", "tfidf_only")
            
        Returns:
            List of search results with content and metadata
        """
        try:
            # Check if alert knowledge store is available
            if self.alert_knowledge_store is None:
                logger.warning("Alert knowledge store is not available, returning empty results")
                return []
                
            if search_type == "semantic":
                results = self.alert_knowledge_store.semantic_search(query, k=k)
            elif search_type == "bm25":
                results = self.alert_knowledge_store.semantic_search_with_bm25(query, k=k)
            elif search_type == "tfidf":
                results = self.alert_knowledge_store.semantic_search_with_tfidf(query, k=k)
            elif search_type == "tfidf_only":
                results = self.alert_knowledge_store.tfidf_search(query, k=k)
            else:
                logger.warning(f"Unknown search type: {search_type}, falling back to semantic search")
                results = self.alert_knowledge_store.semantic_search(query, k=k)
            
            logger.info(f"Found {len(results)} knowledge base results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching alert knowledge base: {str(e)}")
            return []

    def get_alert_knowledge_store(self) -> DocumentChromaStore:
        """Get the alert knowledge base document store.
        
        Returns:
            DocumentChromaStore instance for alert knowledge
        """
        return self.alert_knowledge_store

    async def read_project(self, project_key: str) -> Dict:
        """Read all project files and organize the data.
        
        Args:
            project_key: The project directory name/key
            
        Returns:
            Dictionary containing project data. If preview=True, includes 'preview_data' key
            with all documents that would be written to ChromaDB.
        """
        logger.info(f"Reading project: {project_key} (preview={self.preview})")
        project_path = self.base_path / project_key
        
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        # Read project metadata
        metadata = self._read_project_metadata(project_path)
        
        # Extract the actual project_id from metadata
        project_id = metadata.get("project_id")
        if not project_id:
            raise ValueError(f"Project metadata does not contain 'project_id' field for project: {project_key}")
        
        logger.info(f"Using project_id from metadata: {project_id}")
        
        # Reset preview data if in preview mode
        if self.preview:
            self.preview_data = {}
        
        # Process each table's files
        tables = []
        for table_meta in metadata["tables"]:
            table_data = await self._process_table_files(project_path, table_meta, project_id)
            tables.append(table_data)
        
        # Process knowledge base files
        knowledge_base = await self._process_knowledge_base_files(project_path, metadata.get("knowledge_base", []), project_id)
        
        # Process example files
        examples = await self._process_example_files(project_path, metadata.get("examples", []), project_id)
        
        # Process SQL function files
        sql_functions = await self._process_sql_functions_files(project_path, metadata.get("sql_functions", []), project_id)

        result = {
            "project_id": project_id,
            "tables": tables,
            "knowledge_base": knowledge_base,
            "examples": examples,
            "sql_functions": sql_functions
        }
        
        # Add preview data if in preview mode
        if self.preview:
            result["preview_data"] = self.preview_data
            # Add summary statistics
            result["preview_summary"] = {
                "collections": list(self.preview_data.keys()),
                "total_documents": sum(len(docs) for docs in self.preview_data.values()),
                "documents_by_collection": {name: len(docs) for name, docs in self.preview_data.items()}
            }
            logger.info(f"Preview mode: Collected {result['preview_summary']['total_documents']} documents across {len(self.preview_data)} collections")

        return result

    def _read_project_metadata(self, project_path: Path) -> Dict:
        """Read project metadata file."""
        metadata_path = project_path / "project_metadata.json"
        if not metadata_path.exists():
            raise ValueError(f"Project metadata not found: {metadata_path}")
        
        with open(metadata_path, "r") as f:
            return json.load(f)

    async def _process_table_files(self, project_path: Path, table_meta: Dict, project_id: str) -> Dict:
        """Process MDL and DDL files for a table."""
        table_data = {
            "name": table_meta["name"],
            "display_name": table_meta["display_name"],
            "description": table_meta["description"]
        }
        
        # Process MDL file
        mdl_data = await self._process_mdl_file(project_path, table_meta["mdl_file"], project_id)
        if mdl_data:
            table_data["mdl"] = mdl_data
        
        """
        # Process DDL file if it exists
        ddl_data = self._process_ddl_file(project_path, table_meta["ddl_file"])
        if ddl_data:
            table_data["ddl"] = ddl_data
        """
        return table_data

    async def _process_mdl_file(self, project_path: Path, mdl_file: str, project_id: str) -> Optional[Dict]:
        """Process MDL file using DbSchema."""
        mdl_path = project_path / mdl_file
        if not mdl_path.exists():
            logger.warning(f"MDL file not found: {mdl_path}")
            return None
            
        logger.info(f"Processing MDL file: {mdl_path}")
        with open(mdl_path, "r") as f:
            mdl_str = f.read()
            
        try:
            # Parse MDL to verify columns are present before processing
            import json
            mdl_dict = json.loads(mdl_str) if isinstance(mdl_str, str) else mdl_str
            total_columns_in_mdl = 0
            for model in mdl_dict.get("models", []):
                columns = model.get("columns", [])
                total_columns_in_mdl += len(columns)
                if columns:
                    logger.info(f"MDL model '{model.get('name')}' has {len(columns)} columns before processing")
            logger.info(f"Total columns in MDL before processing: {total_columns_in_mdl}")
            
            # Use DbSchema to process the MDL file
            results = await self.components["db_schema"].run(
                mdl_str=mdl_str,
                project_id=project_id
            )
            
            logger.info(f"Processing Table Descriptions with MDL {project_id}")
            logger.info(f"MDL string length: {len(mdl_str)}, contains 'columns': {'columns' in mdl_str}")
            results["table_description"] = await self.components["table_description"].run(
                mdl=mdl_str,
                project_id=project_id
            )
            logger.info(f"Table Descriptions processing complete: {results['table_description']}")
            
            # Verify columns were processed
            if "table_description" in results:
                td_result = results["table_description"]
                if isinstance(td_result, dict):
                    documents_count = len(td_result.get("documents", []))
                    logger.info(f"Table Description created {documents_count} documents")
                    # Check if documents have columns in metadata
                    if documents_count > 0:
                        sample_doc = td_result["documents"][0]
                        if hasattr(sample_doc, "metadata"):
                            sample_meta = sample_doc.metadata
                            if "columns" in sample_meta:
                                cols = sample_meta["columns"]
                                logger.info(f"Sample document has {len(cols) if isinstance(cols, list) else 'N/A'} columns in metadata")
                            else:
                                logger.warning(f"Sample document does NOT have 'columns' in metadata. Keys: {list(sample_meta.keys())}")
            
            # Process column metadata
            logger.info(f"Processing Column Metadata with MDL {project_id}")
            results["column_metadata"] = await self._process_column_metadata(
                mdl_str=mdl_str,
                project_id=project_id
            )
            logger.info(f"Column Metadata processing complete: {results['column_metadata']}")
            
            # Process relationships
            logger.info(f"Processing Relationships with MDL {project_id}")
            results["relationships"] = await self._process_relationships(
                mdl_str=mdl_str,
                project_id=project_id
            )
            logger.info(f"Relationships processing complete: {results['relationships']}")
            
            # Generate DDL for each table
            logger.info(f"Generating DDL for tables in project {project_id}")
            results["table_ddl"] = await self._generate_table_ddl(
                mdl_str=mdl_str,
                project_id=project_id
            )
            logger.info(f"DDL generation complete: {len(results['table_ddl'])} tables processed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing MDL file {mdl_path}: {str(e)}")
            return None
   
    def _build_table_ddl(self, table_name, description, columns):
        try:
            logger.debug(f"Building DDL for table {table_name}")
            logger.debug(f"Description: {description[:100] if description else 'None'}...")
            logger.debug(f"Columns type: {type(columns)}, length: {len(columns) if columns else 0}")
            logger.debug(f"Columns sample: {columns[:2] if columns else 'None'}")
            
            col_defs = self._build_column_defs(columns)
            logger.debug(f"Generated column definitions: {col_defs}")
            
            # Clean description for SQL comment
            if description:
                # Remove problematic characters and limit length
                clean_description = description.replace('\n', ' ').replace('\r', ' ').strip()
                # Remove or replace problematic characters that could cause SQL issues
                clean_description = clean_description.replace('(', '[').replace(')', ']')
                # Limit comment length to avoid issues
                if len(clean_description) > 200:
                    clean_description = clean_description[:200] + "..."
                table_comment = f"-- {clean_description}\n"
            else:
                table_comment = ""
            
            # Ensure we have valid table name and column definitions
            if not table_name:
                logger.warning("No table name provided, skipping DDL generation")
                return ""
            
            if not col_defs:
                logger.warning(f"No column definitions for table {table_name}, skipping DDL generation")
                return ""
            
            ddl = f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"
            logger.info(f"Generated DDL for {table_name}: {ddl}")
            print(f"Generated DDL for {table_name}: {ddl}")
            
            # Validate the generated DDL
            if not self._validate_ddl_syntax(ddl):
                logger.error(f"Generated DDL failed syntax validation for table {table_name}")
                logger.error(f"Problematic DDL: {repr(ddl)}")
                logger.error(f"DDL length: {len(ddl)}")
                logger.error(f"DDL first 200 chars: {ddl[:200]}")
                return ""
            
            return ddl
        except Exception as e:
            logger.error(f"Error building table DDL for {table_name}: {str(e)}")
            logger.error(f"Columns that caused error: {columns}")
            return ""

    def _build_column_defs(self, columns, default_type="VARCHAR"):
        """Build column definitions for DDL generation."""
        col_defs = []
        if not columns:
            return []
        
        print(f"DEBUG: _build_column_defs called with {len(columns)} columns")
        print(f"DEBUG: Default type: {default_type}")
        print(f"DEBUG: First few columns: {columns[:3] if columns else 'None'}")
            
        for i, col in enumerate(columns):
            try:
                logger.debug(f"Processing column {i}: {col}")
                
                # Handle different column formats
                if isinstance(col, dict):
                    name = col.get('name', '')
                    # Use 'type' field consistently
                    dtype = col.get('type', default_type)
                    
                    # Debug logging for specific columns
                    if name in ['jobtemplatefk', 'personfk', 'isprimary', 'active', 'personfk', 'manager1fk', 'createddate_ts']:
                        print(f"DEBUG: Processing column {name} in _build_column_defs:")
                        print(f"  Raw column object: {col}")
                        print(f"  Extracted type: {col.get('type')}")
                        print(f"  Final dtype: {dtype}")
                        print(f"  Default type: {default_type}")
                    
                    # Get comment and description from properties or direct fields
                    comment = col.get('comment', '')
                    description = col.get('description', '')
                    
                    if 'properties' in col and isinstance(col['properties'], dict):
                        # Get display name as comment if available
                        if not comment:
                            comment = col['properties'].get('displayName', '')
                        # Get description if not already set
                        if not description:
                            description = col['properties'].get('description', '')
                        
                        # Enhanced logging for debugging
                        logger.info(f"DEBUG: Column {col.get('name', '')} properties in _build_column_defs: {col['properties']}")
                        logger.info(f"DEBUG: Column {col.get('name', '')}: comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                    
                    # If no comment is available, generate one from the column name
                    if not comment:
                        # Convert column name to a more readable format
                        comment = name.replace('_', ' ').title()
                        logger.info(f"DEBUG: Generated comment for column {name}: '{comment}'")
                    
                    # Handle notNull constraint
                    not_null = col.get('notNull', False)
                    if not_null and dtype.upper() != 'PRIMARY KEY':
                        dtype += ' NOT NULL'
                    
                    # Log final comment and description
                    logger.info(f"DEBUG: Final column {name}: comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                    logger.debug(f"Column {i}: name='{name}', type='{dtype}', comment='{comment[:50] if comment else 'None'}...', description='{description[:50] if description else 'None'}...'")
                else:
                    name = str(col) if col is not None else ''
                    dtype = default_type
                    comment = ''
                
                # Skip empty column names
                if not name or not name.strip():
                    logger.warning("Skipping column with empty name")
                    continue
                
                # Validate column name doesn't contain problematic characters
                if any(char in name for char in ['(', ')', ';', '\n', '\r']):
                    logger.warning(f"Column name contains problematic characters, skipping: {name}")
                    continue
                    
                col_def = f"{name} {dtype}"
                
                # Add comment and description in the format: -- comment -- Description
                comment_parts = []
                if comment:
                    clean_comment = comment.strip().replace('\n', ' ').replace('\r', ' ')
                    if clean_comment and not clean_comment.startswith("--"):
                        comment_parts.append(clean_comment)
                
                if description:
                    clean_description = description.strip().replace('\n', ' ').replace('\r', ' ')
                    if clean_description and not clean_description.startswith("--"):
                        comment_parts.append(clean_description)
                
                if comment_parts:
                    col_def += f" -- {' -- '.join(comment_parts)}"
                
                logger.info(f"DEBUG: Generated column definition: {col_def}")
                col_defs.append(col_def)
            except Exception as e:
                logger.warning(f"Error processing column {i} ({col}): {str(e)}")
                continue
                
        return col_defs

    def _validate_ddl_syntax(self, ddl: str) -> bool:
        """Validate DDL syntax."""
        try:
            # Basic validation - check for common issues
            if not ddl or not ddl.strip():
                return False
            
            # Check for balanced parentheses
            if ddl.count('(') != ddl.count(')'):
                logger.error("Unbalanced parentheses in DDL")
                return False
            
            # Check for basic SQL structure - handle DDL that starts with comments
            ddl_upper = ddl.upper()
            # Remove leading comments and whitespace to check for CREATE TABLE
            lines = ddl.split('\n')
            create_table_found = False
            for line in lines:
                line = line.strip()
                if line and not line.startswith('--'):
                    if line.upper().startswith('CREATE TABLE'):
                        create_table_found = True
                        break
                    else:
                        break  # Stop at first non-comment line that doesn't start with CREATE TABLE
            
            if not create_table_found:
                logger.error("DDL does not contain CREATE TABLE statement")
                return False
            
            # Check for semicolon at the end
            if not ddl.strip().endswith(';'):
                logger.error("DDL does not end with semicolon")
                return False
            
            # Check for empty column list
            if '()' in ddl:
                logger.error("DDL contains empty column list")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating DDL syntax: {str(e)}")
            return False

    async def _generate_table_ddl(self, mdl_str: str, project_id: str) -> Dict[str, str]:
        """Generate DDL for each table in the MDL."""
        logger.info(f"Starting DDL generation for project: {project_id}")
        
        try:
            # Parse MDL string
            import json
            mdl = json.loads(mdl_str)
            logger.info("MDL string parsed successfully for DDL generation")
            
            table_ddl_map = {}
            
            # Process each model
            for model in mdl.get("models", []):
                table_name = model.get("name", "")
                if not table_name:
                    continue
                    
                logger.info(f"Generating DDL for table: {table_name}")
                
                # Get table description
                table_description = model.get("description", "")
                if not table_description:
                    # Try to get description from properties
                    properties = model.get("properties", {})
                    table_description = properties.get("description", "")
                
                # Process columns for DDL generation
                columns = model.get("columns", [])
                processed_columns = []
                
                for column in columns:
                    column_name = column.get("name", "")
                    if not column_name:
                        continue
                    
                    # Extract column metadata
                    properties = column.get("properties", {})
                    display_name = properties.get("displayName", "")
                    description = properties.get("description", "")
                    
                    # Create column structure for DDL generation
                    # Use the actual type from the MDL column
                    column_type = column.get("type", "VARCHAR")
                    
                    processed_column = {
                        "name": column_name,
                        "type": column_type,  # Use the actual type from MDL
                        "comment": display_name,  # Use display name as comment
                        "description": description,
                        "is_primary_key": column.get("name", "") == model.get("primaryKey", ""),
                        "is_foreign_key": "relationship" in column,
                        "notNull": column.get("notNull", False),
                        "isCalculated": column.get("isCalculated", False),
                        "expression": column.get("expression", ""),
                        "properties": properties
                    }
                    
                    processed_columns.append(processed_column)
                    
                    # Log column processing
                    logger.info(f"  Column {column_name}: type={processed_column['type']}, display_name='{display_name}', description='{description[:50] if description else 'None'}...'")
                
                # Generate DDL for this table
                ddl = self._build_table_ddl(
                    table_name=table_name,
                    description=table_description,
                    columns=processed_columns
                )
                
                if ddl:
                    table_ddl_map[table_name] = ddl
                    logger.info(f"Generated DDL for {table_name}: {len(ddl)} characters")
                    logger.info(f"DDL preview: {ddl[:200]}...")
                else:
                    logger.warning(f"Failed to generate DDL for table {table_name}")
            
            logger.info(f"DDL generation completed: {len(table_ddl_map)} tables processed")
            return table_ddl_map
            
        except Exception as e:
            logger.error(f"Error generating table DDL: {str(e)}")
            return {}

    async def _process_column_metadata(self, mdl_str: str, project_id: str) -> Dict[str, Any]:
        """Process column metadata from MDL and store in column metadata store."""
        logger.info(f"Starting column metadata processing for project: {project_id}")
        
        try:
            # Parse MDL string
            import json
            mdl = json.loads(mdl_str)
            logger.info("MDL string parsed successfully for column metadata")
            
            # Process each model's columns
            documents = []
            total_columns = 0
            
            for model in mdl.get("models", []):
                table_name = model.get("name", "")
                if not table_name:
                    continue
                    
                logger.info(f"Processing columns for table: {table_name}")
                
                for column in model.get("columns", []):
                    column_name = column.get("name", "")
                    if not column_name:
                        continue
                    
                    # Extract column metadata
                    properties = column.get("properties", {})
                    display_name = properties.get("displayName", "")
                    description = properties.get("description", "")
                    
                    # Create column metadata document
                    column_type = column.get("type", "VARCHAR")
                    
                    # Debug logging for active column specifically
                    if column_name == "active":
                        print(f"DEBUG: Processing active column in project reader:")
                        print(f"  Column name: {column_name}")
                        print(f"  Raw type from MDL: {column.get('type')}")
                        print(f"  Final data_type: {column_type}")
                        print(f"  Full column object: {column}")
                    
                    # Use the existing helper function to create properly formatted comments
                    # This ensures consistency with the TABLE_COLUMNS format
                    from app.indexing.utils.helper import _properties_comment
                    
                    # Create a column object with properties for the helper function
                    column_for_helper = {
                        "properties": {
                            "displayName": display_name,
                            "description": description
                        }
                    }
                    
                    # Use the helper function to create the comment
                    formatted_comment = _properties_comment(column_for_helper).strip()
                    
                    # If the helper function doesn't generate a comment (empty properties), create a simple one
                    if not formatted_comment or formatted_comment == "-- {}":
                        if display_name or description:
                            comment_parts = []
                            if display_name:
                                comment_parts.append(display_name)
                            if description and description != display_name:
                                comment_parts.append(description)
                            formatted_comment = ' -- '.join(comment_parts)
                        else:
                            # Generate comment from column name as fallback
                            formatted_comment = column_name.replace('_', ' ').title()
                            logger.info(f"DEBUG: Generated comment for column {column_name}: '{formatted_comment}'")
                    
                    column_metadata = {
                        "column_name": column_name,
                        "table_name": table_name,
                        "type": column_type,
                        "display_name": display_name,
                        "description": description,
                        "comment": formatted_comment,  # Add comment field for consistency
                        "is_calculated": column.get("isCalculated", False),
                        "expression": column.get("expression", ""),
                        "is_primary_key": column.get("name", "") == model.get("primaryKey", ""),
                        "is_foreign_key": "relationship" in column,
                        "relationship": column.get("relationship", {}),
                        "properties": properties,
                        "not_null": column.get("notNull", False)
                    }
                    logger.info(f"DEBUG: Column metadata: {column_metadata}")
                    logger.info(f"DEBUG: Final comment for {column_name}: '{formatted_comment}'")
                    # Create document for storage
                    doc_content = json.dumps(column_metadata)
                    doc_metadata = {
                        "type": "COLUMN_METADATA",
                        "project_id": project_id,
                        "table_name": table_name,
                        "column_name": column_name,
                        "data_type": column.get("type", "VARCHAR"),
                        "display_name": display_name,
                        "description": description[:100] if description else "",
                        "comment": formatted_comment[:100] if formatted_comment else "",  # Add comment to metadata
                        "is_calculated": column.get("isCalculated", False),
                        "is_primary_key": column.get("name", "") == model.get("primaryKey", ""),
                        "is_foreign_key": "relationship" in column
                    }
                    
                    document = Document(
                        page_content=doc_content,
                        metadata=doc_metadata
                    )
                    documents.append(document)
                    total_columns += 1
                    
                    # Log column metadata for debugging
                    logger.info(f"Column {table_name}.{column_name}: display_name='{display_name}', description='{description[:50] if description else 'None'}...'")
            
            # Store documents in column metadata store
            if documents and self.column_metadata_store:
                logger.info(f"Storing {len(documents)} column metadata documents")
                if self.preview and hasattr(self.column_metadata_store, 'add_documents_async'):
                    write_result = await self.column_metadata_store.add_documents_async(documents)
                else:
                    write_result = await self.column_metadata_store.add_documents(documents)
                # Handle both dict and list return types
                if isinstance(write_result, dict):
                    documents_written = write_result.get('documents_written', 0)
                else:
                    documents_written = len(write_result) if write_result else 0
                logger.info(f"Successfully stored {documents_written} column metadata documents")
            else:
                logger.warning("No column metadata documents to store or store not available")
            
            result = {
                "documents_written": len(documents),
                "total_columns": total_columns,
                "project_id": project_id
            }
            
            logger.info(f"Column metadata processing completed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing column metadata: {str(e)}")
            return {
                "documents_written": 0,
                "total_columns": 0,
                "project_id": project_id,
                "error": str(e)
            }

    async def get_column_metadata(self, table_name: str, project_id: str) -> List[Dict[str, Any]]:
        """Retrieve column metadata for a specific table.
        
        Args:
            table_name: Name of the table
            project_id: Project identifier
            
        Returns:
            List of column metadata dictionaries
        """
        try:
            if not self.column_metadata_store:
                logger.warning("Column metadata store not available")
                return []
            
            # Search for column metadata for this table
            where_clause = {
                "$and": [
                    {"project_id": {"$eq": project_id}},
                    {"table_name": {"$eq": table_name}},
                    {"type": {"$eq": "COLUMN_METADATA"}}
                ]
            }
            
            results = self.column_metadata_store.semantic_search(
                query="",
                k=100,  # Get all columns for the table
                where=where_clause
            )
            
            # Parse results
            column_metadata = []
            for result in results:
                try:
                    content = json.loads(result['content'])
                    column_metadata.append(content)
                    logger.info(f"Retrieved metadata for column {table_name}.{content.get('column_name', 'Unknown')}: display_name='{content.get('display_name', 'None')}', description='{content.get('description', 'None')[:50]}...'")
                except Exception as e:
                    logger.warning(f"Error parsing column metadata: {e}")
                    continue
            
            logger.info(f"Retrieved {len(column_metadata)} column metadata records for table {table_name}")
            return column_metadata
            
        except Exception as e:
            logger.error(f"Error retrieving column metadata for table {table_name}: {str(e)}")
            return []

    async def _process_relationships(self, mdl_str: str, project_id: str) -> Dict[str, Any]:
        """Process relationships from MDL and store in db_schema store as separate documents.
        
        Args:
            mdl_str: MDL JSON string
            project_id: Project identifier
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting relationship processing for project: {project_id}")
        
        try:
            # Parse MDL string
            import json
            mdl = json.loads(mdl_str)
            logger.info("MDL string parsed successfully for relationship processing")
            
            # Get relationships from MDL
            relationships = mdl.get("relationships", [])
            logger.info(f"Found {len(relationships)} relationships in MDL")
            
            if not relationships:
                logger.info("No relationships found in MDL")
                return {
                    "documents_written": 0,
                    "total_relationships": 0,
                    "project_id": project_id
                }
            
            # Get models to build primary keys map
            models = mdl.get("models", [])
            primary_keys_map = {model["name"]: model.get("primaryKey", "") for model in models}
            
            # Process each relationship
            documents = []
            total_relationships = 0
            
            for relationship in relationships:
                try:
                    relationship_name = relationship.get("name", "")
                    models_in_relationship = relationship.get("models", [])
                    join_type = relationship.get("joinType", "")
                    condition = relationship.get("condition", "")
                    properties = relationship.get("properties", {})
                    
                    if len(models_in_relationship) != 2:
                        logger.warning(f"Skipping relationship {relationship_name}: expected 2 models, got {len(models_in_relationship)}")
                        continue
                    
                    table1_name = models_in_relationship[0]
                    table2_name = models_in_relationship[1]
                    
                    # Create relationship metadata
                    relationship_metadata = {
                        "relationship_name": relationship_name,
                        "table1": table1_name,
                        "table2": table2_name,
                        "join_type": join_type,
                        "condition": condition,
                        "properties": properties,
                        "purpose": properties.get("purpose", "")
                    }
                    
                    # Create searchable content for the relationship
                    # Include both directions for better searchability
                    purpose_text = properties.get('purpose', '')
                    content_parts = [
                        f"Relationship between {table1_name} and {table2_name}",
                        f"Relationship name: {relationship_name}",
                        f"Join type: {join_type}",
                        f"Join condition: {condition}",
                        f"Purpose: {purpose_text}" if purpose_text else "",
                        f"This relationship connects {table1_name} to {table2_name}",
                        f"Use this relationship to join {table1_name} with {table2_name}",
                        f"Link {table1_name} to {table2_name} using {condition}"
                    ]
                    content = "\n".join(filter(None, content_parts))
                    
                    # Create document for storage in db_schema store
                    doc_content = json.dumps(relationship_metadata)
                    doc_metadata = {
                        "type": "RELATIONSHIP",
                        "project_id": project_id,
                        "relationship_name": relationship_name,
                        "table1": table1_name,
                        "table2": table2_name,
                        "join_type": join_type,
                        "purpose": properties.get("purpose", "")[:100] if properties.get("purpose") else ""
                    }
                    
                    document = Document(
                        page_content=content,
                        metadata=doc_metadata
                    )
                    documents.append(document)
                    total_relationships += 1
                    
                    logger.info(f"Processed relationship: {relationship_name} ({table1_name} <-> {table2_name})")
                    
                except Exception as e:
                    logger.warning(f"Error processing relationship {relationship.get('name', 'unknown')}: {str(e)}")
                    continue
            
            # Store documents in db_schema store
            if documents and self.document_stores.get("db_schema"):
                logger.info(f"Storing {len(documents)} relationship documents in db_schema store")
                db_schema_store = self.document_stores["db_schema"]
                if self.preview and hasattr(db_schema_store, 'add_documents_async'):
                    write_result = await db_schema_store.add_documents_async(documents)
                else:
                    write_result = await db_schema_store.add_documents(documents)
                # Handle both dict and list return types
                if isinstance(write_result, dict):
                    documents_written = write_result.get('documents_written', 0)
                else:
                    documents_written = len(write_result) if write_result else 0
                logger.info(f"Successfully stored {documents_written} relationship documents")
            else:
                logger.warning("No relationship documents to store or db_schema store not available")
            
            result = {
                "documents_written": len(documents),
                "total_relationships": total_relationships,
                "project_id": project_id
            }
            
            logger.info(f"Relationship processing completed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing relationships: {str(e)}")
            return {
                "documents_written": 0,
                "total_relationships": 0,
                "project_id": project_id,
                "error": str(e)
            }

    def _process_ddl_file(self, project_path: Path, ddl_file: str) -> Optional[Dict]:
        """Process DDL file and extract relevant information."""
        ddl_path = project_path / ddl_file
        if not ddl_path.exists():
            logger.warning(f"DDL file not found: {ddl_path}")
            return None
            
        logger.info(f"Processing DDL file: {ddl_path}")
        with open(ddl_path, "r") as f:
            ddl_data = json.load(f)
            
        # Extract relevant DDL information
        processed_ddl = {
            "tables": ddl_data.get("tables", []),
            "views": ddl_data.get("views", []),
            "functions": ddl_data.get("functions", [])
        }
        
        return processed_ddl

    async def _process_knowledge_base_files(self, project_path: Path, knowledge_base_metadata: List[Dict], project_id: str) -> List[Dict]:
        """Process knowledge base files."""
        knowledge_base = []
        for kb_meta in knowledge_base_metadata:
            kb_data = await self._process_instructions_file(project_path, kb_meta["file_path"], project_id)
            if kb_data:
                knowledge_base.append({
                    "name": kb_meta["name"],
                    "display_name": kb_meta["display_name"],
                    "description": kb_meta["description"],
                    "content": kb_data
                })
        return knowledge_base

    async def _process_instructions_file(self, project_path: Path, file_path: str, project_id: str) -> Optional[Dict]:
        """Process instructions file and extract relevant information."""
        instructions_path = project_path / file_path
        if not instructions_path.exists():
            logger.warning(f"Instructions file not found: {instructions_path}")
            return None
            
        logger.info(f"Processing instructions file: {instructions_path}")
        
        try:
            # Check if file is empty
            if instructions_path.stat().st_size == 0:
                logger.warning(f"Instructions file is empty: {instructions_path}")
                return None
            
            with open(instructions_path, "r") as f:
                content = f.read().strip()
                
            # Check if content is empty after stripping whitespace
            if not content:
                logger.warning(f"Instructions file contains only whitespace: {instructions_path}")
                return None
                
            # Try to parse JSON
            try:
                instructions_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in instructions file {instructions_path}: {str(e)}")
                logger.error(f"File content preview: {content[:200]}...")
                return None
            
            # Validate that we have valid data
            if not isinstance(instructions_data, list):
                logger.warning(f"Instructions file does not contain a list: {instructions_path}")
                return None
                
            # Check if list is empty
            if len(instructions_data) == 0:
                logger.warning(f"Instructions file contains empty list: {instructions_path}")
                return None
            
            # Create Instruction objects
            instructions = [
                Instruction(**instruction)
                for instruction in instructions_data
            ]
            logger.info(f"Loaded {len(instructions)} instructions")
            
            # Process instructions using the Instructions component
            results = await self.components["instructions"].run(
                instructions=instructions,
                project_id=project_id
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing instructions file {instructions_path}: {str(e)}")
            return None

    async def _process_example_files(self, project_path: Path, examples_metadata: List[Dict], project_id: str) -> List[Dict]:
        """Process example files."""
        examples = []
        for example_meta in examples_metadata:
            example_data = await self._process_sql_pairs_file(project_path, example_meta["file_path"], project_id)
            if example_data:
                examples.append({
                    "name": example_meta["name"],
                    "display_name": example_meta["display_name"],
                    "description": example_meta["description"],
                    "content": example_data
                })
        return examples

    async def _process_sql_functions_files(
        self, 
        project_path: Path, 
        sql_functions_metadata: List[Dict], 
        project_id: str
    ) -> List[Dict]:
        """Process SQL function files.
        
        Args:
            project_path: Base path of the project
            sql_functions_metadata: List of SQL function file metadata
            project_id: Project identifier
            
        Returns:
            List of processed SQL function file results
        """
        sql_functions = []
        for func_meta in sql_functions_metadata:
            file_path = func_meta.get("file_path", "")
            data_source = func_meta.get("data_source", "local_file")
            
            if not file_path:
                logger.warning("SQL function metadata missing file_path, skipping")
                continue
            
            func_data = await self._process_sql_functions_file(
                project_path, 
                file_path, 
                project_id,
                data_source
            )
            if func_data:
                sql_functions.append({
                    "name": func_meta.get("name", ""),
                    "display_name": func_meta.get("display_name", ""),
                    "description": func_meta.get("description", ""),
                    "data_source": data_source,
                    "content": func_data
                })
        return sql_functions
#/home/ec2-user/sql_meta_new/
    async def _process_sql_pairs_file(self, project_path: Path, file_path: str, project_id: str) -> Optional[Dict]:
        """Process SQL pairs file and extract relevant information."""
        sql_pairs_path = project_path / file_path
        if not sql_pairs_path.exists():
            logger.warning(f"SQL pairs file not found: {sql_pairs_path}")
            return None
            
        logger.info(f"Processing SQL pairs file: {sql_pairs_path}")
        
        try:
            # Check if file is empty
            if sql_pairs_path.stat().st_size == 0:
                logger.warning(f"SQL pairs file is empty: {sql_pairs_path}")
                return None
            
            with open(sql_pairs_path, "r") as f:
                content = f.read().strip()
                
            # Check if content is empty after stripping whitespace
            if not content:
                logger.warning(f"SQL pairs file contains only whitespace: {sql_pairs_path}")
                return None
                
            # Try to parse JSON
            try:
                sql_pairs_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in SQL pairs file {sql_pairs_path}: {str(e)}")
                logger.error(f"File content preview: {content[:200]}...")
                return None
            
            # Validate that we have valid data
            if not isinstance(sql_pairs_data, (list, dict)):
                logger.warning(f"SQL pairs file does not contain valid data structure: {sql_pairs_path}")
                return None
                
            # If it's a list, check if it's empty
            if isinstance(sql_pairs_data, list) and len(sql_pairs_data) == 0:
                logger.warning(f"SQL pairs file contains empty list: {sql_pairs_path}")
                return None
                
            # If it's a dict, check if it has meaningful content
            if isinstance(sql_pairs_data, dict) and not sql_pairs_data:
                logger.warning(f"SQL pairs file contains empty dictionary: {sql_pairs_path}")
                return None
            
            # Process SQL pairs using the SqlPairs component
            results_str = await self.components["sql_pairs"].run(
                sql_pairs=sql_pairs_data,
                project_id=project_id
            )
            
            # Parse the JSON string response back into a dictionary
            if isinstance(results_str, str):
                results = json.loads(results_str)
            else:
                results = results_str
                
            return results
            
        except Exception as e:
            logger.error(f"Error processing SQL pairs file {sql_pairs_path}: {str(e)}")
            return None

    async def _process_sql_functions_file(
        self, 
        project_path: Path, 
        file_path: str, 
        project_id: str,
        data_source: str = "local_file"
    ) -> Optional[Dict]:
        """Process SQL functions file and index function definitions.
        
        Supports multiple formats:
        1. JSON with 'function_reference' key containing function definitions
        2. JSON array of function definitions
        3. JSON object with function names as keys
        
        Args:
            project_path: Base path of the project
            file_path: Relative path to the SQL functions file
            project_id: Project identifier
            data_source: Data source identifier (default: 'local_file')
            
        Returns:
            Dictionary with processing results or None if error
        """
        sql_functions_path = project_path / file_path
        if not sql_functions_path.exists():
            logger.warning(f"SQL functions file not found: {sql_functions_path}")
            return None
            
        logger.info(f"Processing SQL functions file: {sql_functions_path}")
        
        try:
            # Check if file is empty
            if sql_functions_path.stat().st_size == 0:
                logger.warning(f"SQL functions file is empty: {sql_functions_path}")
                return None
            
            with open(sql_functions_path, "r") as f:
                content = f.read().strip()
                
            # Check if content is empty after stripping whitespace
            if not content:
                logger.warning(f"SQL functions file contains only whitespace: {sql_functions_path}")
                return None
                
            # Try to parse JSON
            try:
                functions_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in SQL functions file {sql_functions_path}: {str(e)}")
                logger.error(f"File content preview: {content[:200]}...")
                return None
            
            # Extract function_reference if it exists (vulnerability_instructions.json format)
            if isinstance(functions_data, dict) and "function_reference" in functions_data:
                functions_dict = functions_data["function_reference"]
            elif isinstance(functions_data, dict):
                # Assume the dict itself contains function definitions
                functions_dict = functions_data
            elif isinstance(functions_data, list):
                # Convert list to dict with function names as keys
                functions_dict = {func.get("name", f"func_{i}"): func for i, func in enumerate(functions_data)}
            else:
                logger.warning(f"SQL functions file has unsupported format: {sql_functions_path}")
                return None
            
            if not functions_dict:
                logger.warning(f"SQL functions file contains no function definitions: {sql_functions_path}")
                return None
            
            # Process and index functions
            documents = []
            for func_name, func_def in functions_dict.items():
                try:
                    # Convert function definition to SqlFunctions format
                    # Expected format: { name, param_types, return_type }
                    # Input format: { description, parameters: [...], returns, usage }
                    
                    # Extract parameter types from parameters list
                    parameters = func_def.get("parameters", [])
                    param_types = []
                    for param in parameters:
                        if isinstance(param, str):
                            # Format: "param_name: type" or just "type"
                            if ":" in param:
                                param_type = param.split(":")[-1].strip()
                            else:
                                param_type = param.strip()
                        elif isinstance(param, dict):
                            param_type = param.get("type", "any")
                        else:
                            param_type = "any"
                        param_types.append(param_type)
                    
                    # Extract return type
                    return_type = func_def.get("returns", func_def.get("return_type", "any"))
                    if isinstance(return_type, str):
                        # Clean up return type string
                        return_type = return_type.strip()
                    else:
                        return_type = "any"
                    
                    # Create function definition in SqlFunctions format
                    sql_function_def = {
                        "name": func_name,
                        "param_types": ",".join(param_types) if param_types else "any",
                        "return_type": return_type
                    }
                    
                    # Create document content with full function information
                    doc_content = json.dumps({
                        "name": func_name,
                        "description": func_def.get("description", ""),
                        "parameters": parameters,
                        "returns": return_type,
                        "usage": func_def.get("usage", ""),
                        "param_types": sql_function_def["param_types"],
                        "return_type": return_type
                    })
                    
                    # Create document metadata
                    doc_metadata = {
                        "type": "SQL_FUNCTION",
                        "project_id": project_id,
                        "data_source": data_source,
                        "name": func_name,
                        "param_types": sql_function_def["param_types"],
                        "return_type": return_type,
                        "description": func_def.get("description", "")[:200] if func_def.get("description") else "",
                        "category": func_def.get("category", ""),
                        "domain": func_def.get("domain", "")
                    }
                    
                    document = Document(
                        page_content=doc_content,
                        metadata=doc_metadata
                    )
                    documents.append(document)
                    
                    logger.debug(f"Processed function: {func_name} with {len(param_types)} parameters")
                    
                except Exception as e:
                    logger.warning(f"Error processing function {func_name}: {str(e)}")
                    continue
            
            # Store documents in SQL functions store
            if documents and self.sql_functions_store:
                logger.info(f"Storing {len(documents)} SQL function documents")
                if self.preview and hasattr(self.sql_functions_store, 'add_documents_async'):
                    write_result = await self.sql_functions_store.add_documents_async(documents)
                else:
                    write_result = await self.sql_functions_store.add_documents(documents)
                # Handle both dict and list return types
                if isinstance(write_result, dict):
                    documents_written = write_result.get('documents_written', 0)
                else:
                    documents_written = len(write_result) if write_result else 0
                logger.info(f"Successfully stored {documents_written} SQL function documents")
            else:
                logger.warning("No SQL function documents to store or store not available")
            
            result = {
                "documents_written": len(documents),
                "total_functions": len(documents),
                "project_id": project_id,
                "data_source": data_source
            }
            
            logger.info(f"SQL functions processing completed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing SQL functions file {sql_functions_path}: {str(e)}")
            return {
                "documents_written": 0,
                "total_functions": 0,
                "project_id": project_id,
                "data_source": data_source,
                "error": str(e)
            }

    async def index_sql_functions_from_file(
        self,
        file_path: str,
        project_id: str,
        data_source: str = "local_file"
    ) -> Dict[str, Any]:
        """Index SQL functions from a file path directly.
        
        This is a convenience method to index SQL functions without going through
        the full project reading process.
        
        Args:
            file_path: Absolute or relative path to the SQL functions JSON file
            project_id: Project identifier
            data_source: Data source identifier (default: 'local_file')
            
        Returns:
            Dictionary with indexing results
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.is_absolute():
            # If relative, assume it's relative to base_path
            file_path_obj = self.base_path / file_path
        
        # Extract relative path from base_path for processing
        try:
            relative_path = file_path_obj.relative_to(self.base_path)
        except ValueError:
            # If not relative to base_path, use the file name
            relative_path = file_path_obj.name
        
        result = await self._process_sql_functions_file(
            project_path=self.base_path,
            file_path=str(relative_path),
            project_id=project_id,
            data_source=data_source
        )
        
        return result or {
            "documents_written": 0,
            "total_functions": 0,
            "project_id": project_id,
            "data_source": data_source,
            "error": "Failed to process file"
        }

    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete all data associated with a project from all document stores.
        
        Args:
            project_id: The project ID to delete
            
        Returns:
            Dictionary containing deletion results for each component
        """
        logger.info(f"Starting deletion of project: {project_id}")
        
        deletion_results = {
            "project_id": project_id,
            "components_deleted": {},
            "total_documents_deleted": 0,
            "errors": []
        }
        
        try:
            # Delete from each component/document store
            for component_name, component in self.components.items():
                try:
                    logger.info(f"Deleting {component_name} data for project: {project_id}")
                    print(f"DEBUG: Processing component: {component_name}")
                    print(f"DEBUG: Component type: {type(component)}")
                    print(f"DEBUG: Component has clean method: {hasattr(component, 'clean')}")
                    print(f"DEBUG: Component has _document_store: {hasattr(component, '_document_store')}")
                    
                    # Use the clean method if available
                    if hasattr(component, 'clean'):
                        print(f"DEBUG: Using clean method for {component_name}")
                        await component.clean(project_id=project_id)
                        deletion_results["components_deleted"][component_name] = "cleaned"
                        logger.info(f"Successfully cleaned {component_name} for project: {project_id}")
                    else:
                        # Fallback to direct document store deletion
                        if hasattr(component, '_document_store'):
                            print(f"DEBUG: Using _document_store.delete_by_project_id for {component_name}")
                            result = component._document_store.delete_by_project_id(project_id)
                            print(f"DEBUG: Delete result for {component_name}: {result}")
                            deletion_results["components_deleted"][component_name] = result
                            deletion_results["total_documents_deleted"] += result.get("documents_deleted", 0)
                            logger.info(f"Successfully deleted {result.get('documents_deleted', 0)} documents from {component_name}")
                        else:
                            logger.warning(f"Component {component_name} has no clean method or document store")
                            deletion_results["components_deleted"][component_name] = "no_clean_method"
                            
                except Exception as e:
                    error_msg = f"Error deleting {component_name} for project {project_id}: {str(e)}"
                    logger.error(error_msg)
                    deletion_results["errors"].append(error_msg)
                    deletion_results["components_deleted"][component_name] = f"error: {str(e)}"
            
            # Also delete from any project-specific collections
            try:
                project_collection_name = f"project_{project_id}"
                project_doc_store = DocumentChromaStore(
                    persistent_client=self.persistent_client,
                    collection_name=project_collection_name,
                    tf_idf=True
                )
                project_result = project_doc_store.delete_by_project_id(project_id)
                deletion_results["components_deleted"]["project_collection"] = project_result
                deletion_results["total_documents_deleted"] += project_result.get("documents_deleted", 0)
                logger.info(f"Successfully deleted {project_result.get('documents_deleted', 0)} documents from project collection")
            except Exception as e:
                error_msg = f"Error deleting project collection for {project_id}: {str(e)}"
                logger.warning(error_msg)
                deletion_results["errors"].append(error_msg)
            
            logger.info(f"Project deletion completed for {project_id}. Total documents deleted: {deletion_results['total_documents_deleted']}")
            return deletion_results
            
        except Exception as e:
            error_msg = f"Error during project deletion for {project_id}: {str(e)}"
            logger.error(error_msg)
            deletion_results["errors"].append(error_msg)
            return deletion_results

async def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Use the dependency injection pattern for consistency
    from app.core.dependencies import get_chromadb_client
    persistent_client = get_chromadb_client()

    # Set up base path
    base_path = Path("../../data/sql_meta")
    
    # Initialize reader
    reader = ProjectReader(base_path, persistent_client)
    
    # Test projects
    #test_projects = ["csod_risk_attrition","csodworkday","cornerstone_learning", "cornerstone_talent", "cornerstone","sumtotal_learn","cve_data"] #, "cornerstone_talent"]
    test_projects = ["hr_compliance_risk"]

    #test_projects = ["cve_data"]
    
    for project in test_projects:
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing project: {project}")
            logger.info(f"{'='*50}")
            
            # Read project
            project_data = await reader.read_project(project)
            
            # Print summary
            logger.info(f"\nProject ID: {project_data['project_id']}")
            
            # Print tables summary
            logger.info("\nTables:")
            for table in project_data['tables']:
                logger.info(f"- {table['name']} ({table['display_name']})")
                logger.info(f"  Description: {table['description']}")
                logger.info(f"  Has MDL: {'mdl' in table}")
                logger.info(f"  Has DDL: {'ddl' in table}")
                
                # Print MDL details if available
                if 'mdl' in table:
                    mdl = table['mdl']
                    logger.info(f"  MDL Catalog: {mdl.get('catalog')}")
                    logger.info(f"  MDL Schema: {mdl.get('schema')}")
                    logger.info(f"  MDL Models: {len(mdl.get('models', []))}")
                    logger.info(f"  MDL Enums: {len(mdl.get('enums', []))}")
                    logger.info(f"  MDL Metrics: {len(mdl.get('metrics', []))}")
                    logger.info(f"  MDL Views: {len(mdl.get('views', []))}")
                
                # Print DDL details if available
                if 'ddl' in table:
                    ddl = table['ddl']
                    logger.info(f"  DDL Tables: {len(ddl.get('tables', []))}")
                    logger.info(f"  DDL Views: {len(ddl.get('views', []))}")
                    logger.info(f"  DDL Functions: {len(ddl.get('functions', []))}")
            
            # Print knowledge base summary
            logger.info("\nKnowledge Base:")
            for kb in project_data['knowledge_base']:
                logger.info(f"- {kb['name']} ({kb['display_name']})")
                logger.info(f"  Description: {kb['description']}")
                if 'content' in kb:
                    content = kb['content']
                    logger.info(f"  Knowledge Base Items: {len(content.get('knowledge_base', []))}")
                    logger.info(f"  Examples: {len(content.get('examples', []))}")
                    logger.info(f"  Tags: {len(content.get('tags', []))}")
            
            # Print examples summary
            logger.info("\nExamples:")
            for example in project_data['examples']:
                logger.info(f"- {example['name']} ({example['display_name']})")
                logger.info(f"  Description: {example['description']}")
                if 'content' in example:
                    content = example['content']
                    logger.info(f"  SQL Pairs: {len(content.get('pairs', []))}")
                    logger.info(f"  Metadata Fields: {len(content.get('metadata', {}))}")
            
            # Test reading from ChromaDB using DocumentChromaStore
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing ChromaDB Reading for project: {project}")
            logger.info(f"{'='*50}")
            
            # Import DocumentChromaStore
            from app.storage.documents import DocumentChromaStore
            
            # Create DocumentChromaStore instance for the project
            project_collection_name = f"project_{project}"
            doc_store = DocumentChromaStore(
                persistent_client=persistent_client,
                collection_name=project_collection_name,
                tf_idf=True  # Enable TF-IDF for enhanced search
            )
            
            # Test semantic search
            logger.info("\nTesting semantic search...")
            search_queries = [
                "What are the main tables in this project?",
                "Show me the data models and schemas",
                "What are the key metrics and KPIs?",
                "Explain the business logic and rules"
            ]
            
            for query in search_queries:
                logger.info(f"\nQuery: {query}")
                try:
                    # Basic semantic search
                    results = doc_store.semantic_search(query, k=3)
                    logger.info(f"Found {len(results)} results:")
                    
                    for i, result in enumerate(results[:2], 1):  # Show top 2 results
                        logger.info(f"  Result {i}:")
                        logger.info(f"    Score: {result['score']:.4f}")
                        logger.info(f"    Content: {result['content'][:100]}...")
                        logger.info(f"    ID: {result['id']}")
                        
                except Exception as e:
                    logger.error(f"Error in semantic search: {str(e)}")
            
            # Test semantic search with BM25 ranking
            logger.info("\nTesting semantic search with BM25 ranking...")
            bm25_query = "What are the main tables and their relationships?"
            try:
                bm25_results = doc_store.semantic_search_with_bm25(bm25_query, k=3)
                logger.info(f"Found {len(bm25_results)} BM25 results:")
                
                for i, result in enumerate(bm25_results[:2], 1):
                    logger.info(f"  Result {i}:")
                    logger.info(f"    Combined Score: {result['combined_score']:.4f}")
                    logger.info(f"    Vector Score: {result['vector_score']:.4f}")
                    logger.info(f"    BM25 Score: {result['bm25_score']:.4f}")
                    logger.info(f"    Content: {result['content'][:100]}...")
                    
            except Exception as e:
                logger.error(f"Error in BM25 search: {str(e)}")
            
            # Test semantic search with TF-IDF
            logger.info("\nTesting semantic search with TF-IDF...")
            tfidf_query = "What are the data models and business rules?"
            try:
                tfidf_results = doc_store.semantic_search_with_tfidf(tfidf_query, k=3)
                logger.info(f"Found {len(tfidf_results)} TF-IDF results:")
                
                for i, result in enumerate(tfidf_results[:2], 1):
                    logger.info(f"  Result {i}:")
                    logger.info(f"    Combined Score: {result['combined_score']:.4f}")
                    logger.info(f"    Semantic Score: {result['semantic_score']:.4f}")
                    logger.info(f"    TF-IDF Score: {result['tfidf_score']:.4f}")
                    logger.info(f"    Content: {result['content'][:100]}...")
                    
            except Exception as e:
                logger.error(f"Error in TF-IDF search: {str(e)}")
            
            # Test metadata filtering
            logger.info("\nTesting search with metadata filters...")
            try:
                # Search for documents with specific metadata
                filtered_results = doc_store.semantic_search(
                    "table structure and schema",
                    k=3,
                    where={"type": "table"}  # Adjust based on your actual metadata structure
                )
                logger.info(f"Found {len(filtered_results)} filtered results:")
                
                for i, result in enumerate(filtered_results[:2], 1):
                    logger.info(f"  Result {i}:")
                    logger.info(f"    Score: {result['score']:.4f}")
                    logger.info(f"    Content: {result['content'][:100]}...")
                    logger.info(f"    Metadata: {result['metadata']}")
                    
            except Exception as e:
                logger.error(f"Error in filtered search: {str(e)}")
            
            # Test TF-IDF only search
            logger.info("\nTesting TF-IDF only search...")
            try:
                tfidf_only_results = doc_store.tfidf_search("data models tables", k=3)
                logger.info(f"Found {len(tfidf_only_results)} TF-IDF only results:")
                
                for i, result in enumerate(tfidf_only_results[:2], 1):
                    logger.info(f"  Result {i}:")
                    logger.info(f"    Score: {result['score']:.4f}")
                    logger.info(f"    Content: {result['content'][:100]}...")
                    
            except Exception as e:
                logger.error(f"Error in TF-IDF only search: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing project {project}: {str(e)}")

async def test_delete_project():
    """Test function to demonstrate project deletion functionality."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Use the dependency injection pattern for consistency
    from app.core.dependencies import get_chromadb_client
    persistent_client = get_chromadb_client()

    # Set up base path
    base_path = Path("../../data/sql_meta")
    
    # Initialize reader
    reader = ProjectReader(base_path, persistent_client)
    
    test_projects = ["hr_compliance_risk"] #["csodworkday","cornerstone_learning", "cornerstone_talent", "cornerstone","sumtotal_learn_v3","cve_data","csod_risk_attrition"] #, "cornerstone_talent"]
    # Test project deletion
    for project in test_projects:
        test_project_id = project  # Use the actual project_id from metadata
        
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing project deletion for: {test_project_id}")
            logger.info(f"{'='*50}")
            
            # Delete the project
            deletion_result = await reader.delete_project(test_project_id)
            
            # Print deletion results
            logger.info(f"\nDeletion Results for project {test_project_id}:")
            logger.info(f"Total documents deleted: {deletion_result.get('total_documents_deleted', 0)}")
            logger.info(f"Components processed: {len(deletion_result.get('components_deleted', {}))}")
            
            logger.info("\nComponent deletion results:")
            for component, result in deletion_result.get('components_deleted', {}).items():
                logger.info(f"  {component}: {result}")
            
            if deletion_result.get('errors'):
                logger.info(f"\nErrors encountered: {len(deletion_result['errors'])}")
                for error in deletion_result['errors']:
                    logger.error(f"  {error}")
            else:
                logger.info("\nNo errors encountered during deletion")
                
        except Exception as e:
            logger.error(f"Error during project deletion test: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_delete_project()) 
    asyncio.run(main())    
    
    # Uncomment the line below to test project deletion
    # asyncio.run(test_delete_project()) 