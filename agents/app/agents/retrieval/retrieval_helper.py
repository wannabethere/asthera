import asyncio
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import hashlib
import json

import chromadb
from langchain_openai import OpenAIEmbeddings

from app.indexing.orchestrator import IndexingOrchestrator
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.agents.retrieval.instructions import Instructions
from app.agents.retrieval.historical_question_retrieval import HistoricalQuestionRetrieval
from app.agents.retrieval.sql_pairs_retrieval import SqlPairsRetrieval
from app.agents.retrieval.retrieval import TableRetrieval
from app.agents.retrieval.preprocess_sql_data import PreprocessSqlData
from app.agents.nodes.sql.utils.sql_prompts import AskHistory
from app.agents.retrieval.sql_functions import SqlFunctions
from app.agents.retrieval.dummy_knowledge_handler import DummyKnowledgeHandler
from app.core.dependencies import get_doc_store_provider, get_vector_store_client
from app.utils.cache import InMemoryCache

if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()

# Store name -> Qdrant collection name.
# Collections are always named with 'core_' prefix (e.g., 'core_db_schema').
# Matches the collection names used in dependencies.py COLLECTION_NAMES.
# Shared with project_reader_qdrant so indexing populates the same collections retrieval queries.
STORE_TO_COLLECTION = {
    "db_schema": "core_db_schema",
    "table_description": "core_table_descriptions",
    "historical_question": "core_historical_question",
    "instructions": "core_instructions",
    "project_meta": "core_project_meta",
    "sql_pairs": "core_sql_pairs",
    "alert_knowledge_base": "core_alert_knowledge_base",
    "column_metadata": "core_column_metadata",
    "sql_functions": "core_sql_functions",
    "core_ds_functions": "core_ds_functions",
    "core_ds_function_examples": "core_ds_function_examples",
    "core_ds_function_instructions": "core_ds_function_instructions",
}


def _get_collection_name(store_name: str) -> str:
    return STORE_TO_COLLECTION.get(store_name, store_name)


class RetrievalHelper:
    def __init__(
        self,
        vector_store_client: Optional["VectorStoreClient"] = None,
        core_collection_prefix: Optional[str] = None,
    ):
        """Initialize retrieval with document stores from VectorStoreClient (Chroma/Qdrant) or doc_store_provider.

        Args:
            vector_store_client: If set, document stores are created from this client (like knowledge app).
                                Enables Qdrant when settings.VECTOR_STORE_TYPE=qdrant.
            core_collection_prefix: Optional prefix for Qdrant collections (e.g. 'core_' for ProjectReaderQdrant).
                                   When set with Qdrant, core_* stores and retrievers are created for schema retrieval.
        """
        self.core_collection_prefix = core_collection_prefix
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY,
        )

        if vector_store_client is not None:
            logger.info("Creating document stores from VectorStoreClient")
            self.vector_store_client = vector_store_client
            self.document_stores = self._create_document_stores_from_vector_client(
                vector_store_client, collection_prefix=None
            )
        else:
            self.vector_store_client = None
            self.document_stores = get_doc_store_provider().stores

        self._core_document_stores = {}
        self._core_retrievers = {}
        if core_collection_prefix and self.vector_store_client is not None:
            from app.storage.vector_store import QdrantVectorStoreClient
            if isinstance(self.vector_store_client, QdrantVectorStoreClient):
                self._core_document_stores = self._create_document_stores_from_vector_client(
                    self.vector_store_client, collection_prefix=core_collection_prefix
                )
                if self._core_document_stores.get("table_description"):
                    self._core_retrievers["table_retrieval"] = TableRetrieval(
                        document_store=self._core_document_stores["table_description"],
                        embedder=self.embeddings,
                        model_name="gpt-4o-mini",
                        table_retrieval_size=5,
                        table_column_retrieval_size=100,
                        allow_using_db_schemas_without_pruning=True,
                        table_store=self._core_document_stores.get("table_description"),
                        schema_store=self._core_document_stores.get("db_schema"),
                    )
                    if self._core_document_stores.get("db_schema"):
                        self._core_retrievers["db_schema"] = TableRetrieval(
                            document_store=self._core_document_stores["db_schema"],
                            embedder=self.embeddings,
                            model_name="gpt-4o-mini",
                            table_retrieval_size=5,
                            table_column_retrieval_size=100,
                            table_store=self._core_document_stores.get("table_description"),
                            schema_store=self._core_document_stores.get("db_schema"),
                        )
                # Add core retrievers for sql_pairs and instructions if available
                if self._core_document_stores.get("sql_pairs"):
                    self._core_retrievers["sql_pairs"] = SqlPairsRetrieval(
                        document_store=self._core_document_stores["sql_pairs"],
                        embedder=self.embeddings,
                        similarity_threshold=0.1,
                        max_retrieval_size=10
                    )
                if self._core_document_stores.get("instructions"):
                    self._core_retrievers["instructions"] = Instructions(
                        document_store=self._core_document_stores["instructions"],
                        embedder=self.embeddings,
                        similarity_threshold=0.1,
                        top_k=30
                    )
                logger.info("Core document stores and retrievers initialized (prefix=%s)", core_collection_prefix)

        # Initialize retrievers (default stores)
        self.retrievers = {
            "instructions": Instructions(
                document_store=self.document_stores["instructions"],
                embedder=self.embeddings,
                similarity_threshold=0.1,
                top_k=30
            ),
            "historical_question": HistoricalQuestionRetrieval(
                document_store=self.document_stores["historical_question"],
                embedder=self.embeddings,
                similarity_threshold=0.7  # Lowered threshold for testing
            ),
            "sql_pairs": SqlPairsRetrieval(
                document_store=self.document_stores["sql_pairs"],
                embedder=self.embeddings,
                similarity_threshold=0.1,
                max_retrieval_size=10
            ),
            "table_retrieval": TableRetrieval(
                document_store=self.document_stores["table_description"],
                embedder=self.embeddings,
                model_name="gpt-4",
                table_retrieval_size=5,
                table_column_retrieval_size=100,
                allow_using_db_schemas_without_pruning=False,
                table_store=self.document_stores.get("table_description"),
                schema_store=self.document_stores.get("db_schema"),
            ),
            "db_schema": TableRetrieval(
                document_store=self.document_stores["db_schema"],
                embedder=self.embeddings,
                model_name="gpt-4",
                table_retrieval_size=5,
                table_column_retrieval_size=100,
                table_store=self.document_stores.get("table_description"),
                schema_store=self.document_stores.get("db_schema"),
            )
        }
        
        # Initialize SQL data preprocessor
        self.sql_preprocessor = PreprocessSqlData(
            model="gpt-4",
            max_tokens=100_000,
            max_iterations=1000,
            reduction_step=50
        )
        
        # Initialize SQL functions retriever (uses core_ds_* when available for combined retrieval)
        ds_stores = {
            k: v for k, v in self.document_stores.items()
            if k in ("core_ds_functions", "core_ds_function_examples", "core_ds_function_instructions")
        } if self.document_stores else {}
        primary_store = ds_stores.get("core_ds_functions") or self.document_stores.get("sql_functions")
        if primary_store or "sql_functions" in (self.document_stores or {}):
            self.sql_functions_retriever = SqlFunctions(
                document_store=primary_store or self.document_stores["sql_functions"],
                document_stores=ds_stores if ds_stores else None,
                engine_timeout=30.0,
                ttl=60 * 60 * 24  # 24 hours
            )
        else:
            # Create SQL functions store if not available - use same backend as vector_store_client
            logger.warning("SQL functions store not in provider, creating fallback store")
            try:
                if self.vector_store_client is not None:
                    # Use vector_store_client to create SQL functions store (Qdrant or Chroma)
                    from app.storage.vector_store import QdrantVectorStoreClient
                    if isinstance(self.vector_store_client, QdrantVectorStoreClient):
                        from app.storage.qdrant_store import DocumentQdrantStore
                        sql_functions_store = DocumentQdrantStore(
                            qdrant_client=self.vector_store_client._client,
                            collection_name="sql_functions",
                            embeddings_model=self.embeddings,
                        )
                        logger.info("Created Qdrant SQL functions store as fallback")
                    else:
                        # ChromaVectorStoreClient - use _get_document_store
                        sql_functions_store = self.vector_store_client._get_document_store("sql_functions")
                        logger.info("Created Chroma SQL functions store as fallback")
                else:
                    # Fallback to ChromaDB provider if no vector_store_client
                    from app.storage.documents import DocumentChromaStore
                    from app.core.dependencies import get_chromadb_client
                    sql_functions_store = DocumentChromaStore(
                        persistent_client=get_chromadb_client(),
                        collection_name="sql_functions",
                        embeddings_model=self.embeddings,
                        tf_idf=True
                    )
                    logger.info("Created ChromaDB SQL functions store from provider")
                
                # Add it to document stores for consistency
                self.document_stores["sql_functions"] = sql_functions_store
                ds_stores = {k: v for k, v in (self.document_stores or {}).items()
                            if k in ("core_ds_functions", "core_ds_function_examples", "core_ds_function_instructions")}
                self.sql_functions_retriever = SqlFunctions(
                    document_store=sql_functions_store,
                    document_stores=ds_stores if ds_stores else None,
                    engine_timeout=30.0,
                    ttl=60 * 60 * 24  # 24 hours
                )
                logger.info("SQL functions store created successfully")
            except Exception as e:
                logger.error(f"Failed to create SQL functions store: {e}")
                self.sql_functions_retriever = None

        self.cache = InMemoryCache()
        
        # Initialize dummy knowledge handler
        self.knowledge_handler = DummyKnowledgeHandler()

    def _extract_enriched_metadata(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Extract enriched metadata (query_patterns, use_cases) from document if available.
        
        Args:
            doc: Document dictionary with metadata
            
        Returns:
            Dictionary with enriched metadata fields
        """
        metadata = doc.get("metadata", {})
        enriched = {}
        
        if metadata.get("query_patterns"):
            enriched["query_patterns"] = metadata.get("query_patterns")
        if metadata.get("use_cases"):
            enriched["use_cases"] = metadata.get("use_cases")
        
        return enriched

    def _create_document_stores_from_vector_client(
        self,
        vector_store_client: "VectorStoreClient",
        collection_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build document stores from VectorStoreClient (Chroma or Qdrant), like knowledge app."""
        from app.storage.vector_store import ChromaVectorStoreClient, QdrantVectorStoreClient
        from app.storage.qdrant_store import DocumentQdrantStore

        stores = {}
        store_names = [
            "instructions",
            "historical_question",
            "sql_pairs",
            "table_description",
            "db_schema",
            "column_metadata",
            "sql_functions",
        ]
        if isinstance(vector_store_client, ChromaVectorStoreClient):
            for store_name in store_names:
                try:
                    doc_store = vector_store_client._get_document_store(store_name)
                    stores[store_name] = doc_store
                    logger.info("Created document store from VectorStoreClient: %s", store_name)
                except Exception as e:
                    logger.warning("Failed to create document store %s: %s", store_name, e)
        elif isinstance(vector_store_client, QdrantVectorStoreClient):
            if collection_prefix:
                logger.info("Creating Qdrant document stores with prefix=%s", collection_prefix)
            for store_name in store_names:
                try:
                    coll_name = _get_collection_name(store_name)
                    # Collections are always 'core_*' - if prefix is provided, add it to the existing core_ prefix
                    # Otherwise, use the collection name directly (which already includes 'core_')
                    if collection_prefix:
                        # If prefix is provided, add it before the collection name
                        # e.g., if prefix is "test_" and coll_name is "core_db_schema", result is "test_core_db_schema"
                        collection_name = collection_prefix + coll_name
                    else:
                        # Use the collection name directly (already includes 'core_' prefix)
                        collection_name = coll_name
                    doc_store = DocumentQdrantStore(
                        qdrant_client=vector_store_client._client,
                        collection_name=collection_name,
                        embeddings_model=self.embeddings,
                    )
                    stores[store_name] = doc_store
                    logger.info("Created Qdrant document store: %s -> %s", store_name, collection_name)
                except Exception as e:
                    logger.warning("Failed to create Qdrant document store %s: %s", store_name, e)
        else:
            logger.warning("VectorStoreClient type %s not supported for document stores", type(vector_store_client).__name__)
        return stores

    async def get_database_schemas(
        self, 
        project_id: str, 
        table_retrieval: dict, 
        query: str, 
        histories: Optional[list[AskHistory]] = None,
        tables: Optional[List[str]] = None,
        reasoning: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch database schemas for a given project.
        
        Args:
            project_id: The project ID to fetch schemas for
            table_retrieval: Dictionary containing table retrieval configuration
            query: The query string to use for schema retrieval
            histories: Optional list of AskHistory objects for context
            tables: Optional list of specific tables to retrieve schemas for
            reasoning: Optional reasoning result to help with column selection
            
        Returns:
            Dictionary containing database schemas and metadata
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_database_schemas',
            'project_id': project_id,
            'table_retrieval': table_retrieval,
            'query': query,
            'histories': [h.__dict__ if hasattr(h, '__dict__') else h for h in histories] if histories else None,
            'tables': tables,
            'reasoning': reasoning
        }, sort_keys=True, default=str).encode()).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Initialize empty history_dicts
            history_dicts = []
            
            # Only process histories if they exist and are not empty
            if histories and len(histories) > 0:
                history_dicts = [
                    {
                        "question": history.query if hasattr(history, 'query') else history.question if hasattr(history, 'question') else "",
                        "sql": history.sql if hasattr(history, 'sql') else ""
                    } for history in histories
                ]
            
            
          
            
            # Use core retriever if available (for Qdrant with core_ prefix), otherwise use default retriever
            table_retriever = self._core_retrievers.get("table_retrieval") or self.retrievers["table_retrieval"]
            if self._core_retrievers.get("table_retrieval"):
                logger.info("Using core table_retrieval retriever (Qdrant with core_ prefix)")
            else:
                logger.info("Using default table_retrieval retriever")
            
            # Use the table retrieval to get schema information
            schema_result = await table_retriever.run(
                query=query,
                project_id=project_id,
                tables=tables,
                histories=history_dicts,
                reasoning=reasoning
            )
            #logger.info(f"schema_result: {schema_result}")
            if not schema_result or "retrieval_results" not in schema_result:
                logger.warning(f"No schema information found for project {project_id}")
                result = {
                    "error": "No schema information found",
                    "schemas": []
                }
                return result
            
            # ADD COLUMN METADATA RETRIEVAL
            print(f"=== RETRIEVING COLUMN METADATA ===")
            if "retrieval_results" in schema_result:
                for result in schema_result["retrieval_results"]:
                    if isinstance(result, dict):
                        table_name = result.get("table_name", "")
                        if table_name:
                            # Retrieve column metadata for this table
                            try:
                                column_metadata = await self._get_column_metadata_for_table(
                                    table_name=table_name,
                                    project_id=project_id
                                )
                                result["column_metadata"] = column_metadata
                                print(f"Retrieved {len(column_metadata)} columns for table {table_name}")
                            except Exception as e:
                                logger.warning(f"Failed to retrieve column metadata for table {table_name}: {e}")
                                result["column_metadata"] = []

            # Process and format the schema information
            schemas = []
            print(f"=== PROCESSING SCHEMA RESULTS ===")
            print(f"Number of retrieval_results: {len(schema_result['retrieval_results'])}")
            
            # Enforce maximum of 5 tables regardless of request
            MAX_TABLES = 5
            retrieval_results = schema_result["retrieval_results"][:MAX_TABLES]
            logger.info(f"Limiting retrieval results to {MAX_TABLES} tables (requested: {len(schema_result['retrieval_results'])})")
            
            for i, result in enumerate(retrieval_results):
                print(f"Processing result {i}: {type(result)}")
                if isinstance(result, dict):
                    table_name = result.get("table_name", "")
                    table_ddl = result.get("table_ddl", "")
                    column_metadata = result.get("column_metadata", [])  # Get column metadata
                    
                    print(f"Result {i} - table_name: {table_name}")
                    print(f"Result {i} - column_metadata_count: {len(column_metadata)}")
                    
                    if table_ddl:
                        print(f"Result {i} - Full DDL:")
                        print(f"{table_ddl}")
                        print(f"=== END DDL for {table_name} ===")
                    
                    # Use the DDL as-is since it already contains the necessary column information
                    # The _build_table_ddl method in retrieval.py already processes COLUMN_METADATA
                    schema_info = {
                        "table_name": table_name,
                        "table_ddl": table_ddl,  # Use DDL directly without enhancement
                        "column_metadata": column_metadata,  # Include column metadata for reference
                        "relationships": result.get("relationships", []),
                        "has_calculated_field": schema_result.get("has_calculated_field", False),
                        "has_metric": schema_result.get("has_metric", False)
                    }
                    schemas.append(schema_info)
                    print(f"Added schema {i} to schemas list with {len(column_metadata)} columns")
                else:
                    print(f"Result {i} is not a dict, skipping")
            
            result = {
                "schemas": schemas,
                "total_schemas": len(schemas),
                "project_id": project_id,
                "query": query,
                "retrieval_config": table_retrieval,
                "tables": tables,
                "has_calculated_field": schema_result.get("has_calculated_field", False),
                "has_metric": schema_result.get("has_metric", False)
            }
            
            print(f"=== FINAL SCHEMA RESULT ===")
            print(f"Total schemas: {len(schemas)}")
            for i, schema in enumerate(schemas):
                print(f"Schema {i}: table_name={schema['table_name']}, table_ddl_length={len(schema['table_ddl']) if schema['table_ddl'] else 0}")
                if schema['table_ddl']:
                    print(f"Schema {i} DDL preview: {schema['table_ddl'][:150]}...")
            
            if schemas:
                await self.cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Error fetching database schemas: {str(e)}")
            result = {
                "error": str(e),
                "schemas": [],
                "project_id": project_id,
                "query": query,
                "tables": tables
            }
            await self.cache.set(cache_key, result, ttl=300)
            return result
    
    async def get_sql_pairs(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.3,
        max_retrieval_size: int = 3
    ) -> Dict[str, Any]:
        """Fetch SQL pairs for a given query.
        
        Args:
            query: The query string to search for similar SQL pairs
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            max_retrieval_size: Maximum number of documents to retrieve
            
        Returns:
            Dictionary containing SQL pairs and metadata
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_sql_pairs',
            'query': query,
            'project_id': project_id,
            'similarity_threshold': similarity_threshold,
            'max_retrieval_size': max_retrieval_size
        }, sort_keys=True, default=str).encode()).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Use core retriever if available (for Qdrant with core_ prefix), otherwise use default retriever
            sql_pairs_retriever = self._core_retrievers.get("sql_pairs") or self.retrievers["sql_pairs"]
            if self._core_retrievers.get("sql_pairs"):
                logger.info("Using core sql_pairs retriever (Qdrant with core_ prefix)")
            
            # Use the SQL pairs retriever to get similar queries and their SQL
            sql_pairs_result = await sql_pairs_retriever.run(
                query=query,
                project_id=project_id
            )
            
            if not sql_pairs_result or "documents" not in sql_pairs_result:
                logger.warning(f"No SQL pairs found for project {project_id}")
                result = {
                    "error": "No SQL pairs found",
                    "sql_pairs": []
                }
                return result
            
            # Process and format the SQL pairs
            logger.info(f"sql_pairs_result in retrieval_helper {query}: {sql_pairs_result}")
            sql_pairs = []
            for doc in sql_pairs_result["documents"]:
                if isinstance(doc, dict):
                    sql_pair = {
                        "question": doc.get("question", ""),
                        "sql": doc.get("sql", ""),
                        "instructions": doc.get("instructions", ""),
                        "score": doc.get("score", 0.0),
                        "raw_distance": doc.get("raw_distance", 0.0)
                    }
                    # Add enriched metadata if available
                    enriched = self._extract_enriched_metadata(doc)
                    sql_pair.update(enriched)
                    sql_pairs.append(sql_pair)
            
            result = {
                "sql_pairs": sql_pairs,
                "total_pairs": len(sql_pairs),
                "project_id": project_id,
                "query": query,
                "similarity_threshold": similarity_threshold,
                "max_retrieval_size": max_retrieval_size
            }
            if sql_pairs:
                await self.cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Error fetching SQL pairs: {str(e)}")
            result = {
                "error": str(e),
                "sql_pairs": [],
                "project_id": project_id,
                "query": query
            }
            await self.cache.set(cache_key, result, ttl=300)
            return result

    async def get_instructions(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.7,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """Fetch instructions for a given query.
        
        Args:
            query: The query string to search for similar instructions
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            top_k: Maximum number of documents to retrieve
            
        Returns:
            Dictionary containing instructions and metadata
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_instructions',
            'query': query,
            'project_id': project_id,
            'similarity_threshold': similarity_threshold,
            'top_k': top_k
        }, sort_keys=True, default=str).encode()).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Use core retriever if available (for Qdrant with core_ prefix), otherwise use default retriever
            instructions_retriever = self._core_retrievers.get("instructions") or self.retrievers["instructions"]
            if self._core_retrievers.get("instructions"):
                logger.info("Using core instructions retriever (Qdrant with core_ prefix)")
            
            # Use the instructions retriever to get similar instructions
            instructions_result = await instructions_retriever.run(
                query=query,
                project_id=project_id
            )
            logger.info(f"instructions_result in retrieval_helper {query}: {instructions_result}")
            if not instructions_result or "documents" not in instructions_result:
                logger.warning(f"No instructions found for project {project_id}")
                result = {
                    "error": "No instructions found",
                    "instructions": []
                }
                return result
            
            # Process and format the instructions
            instructions = []
            for doc in instructions_result["documents"]:
                if isinstance(doc, dict):
                    instruction = {
                        "instruction": doc.get("instruction", ""),
                        "question": doc.get("question", ""),
                        "instruction_id": doc.get("instruction_id", "")
                    }
                    # Add enriched metadata if available
                    enriched = self._extract_enriched_metadata(doc)
                    instruction.update(enriched)
                    instructions.append(instruction)
            
            result = {
                "instructions": instructions,
                "total_instructions": len(instructions),
                "project_id": project_id,
                "query": query,
                "similarity_threshold": similarity_threshold,
                "top_k": top_k
            }
            if instructions:
                await self.cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Error fetching instructions: {str(e)}")
            result = {
                "error": str(e),
                "instructions": [],
                "project_id": project_id,
                "query": query
            }
            await self.cache.set(cache_key, result, ttl=300)
            return result

    async def get_historical_questions(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.9
    ) -> Dict[str, Any]:
        """Fetch historical questions for a given query.
        
        Args:
            query: The query string to search for similar historical questions
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            
        Returns:
            Dictionary containing historical questions and metadata
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_historical_questions',
            'query': query,
            'project_id': project_id,
            'similarity_threshold': similarity_threshold
        }, sort_keys=True, default=str).encode()).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Generate embedding for the query
            embedding = await self.embeddings.aembed_query(query)
            if not embedding:
                logger.warning("Failed to generate embedding for query")
                result = {
                    "error": "Failed to generate embedding",
                    "historical_questions": []
                }
                return result

            # Use the historical question retriever to get similar questions
            historical_result = await self.retrievers["historical_question"].run(
                query=query,
                project_id=project_id
            )
            
            if not historical_result or "documents" not in historical_result:
                logger.warning(f"No historical questions found for project {project_id}")
                result = {
                    "error": "No historical questions found",
                    "historical_questions": []
                }
                return result
            
            # Process and format the historical questions
            historical_questions = []
            for doc in historical_result["documents"]:
                if isinstance(doc, dict):
                    question = {
                        "question": doc.get("question", ""),
                        "summary": doc.get("summary", ""),
                        "statement": doc.get("statement", ""),
                        "viewId": doc.get("viewId", "")
                    }
                    # Add enriched metadata if available
                    enriched = self._extract_enriched_metadata(doc)
                    question.update(enriched)
                    historical_questions.append(question)
            
            result = {
                "historical_questions": historical_questions,
                "total_questions": len(historical_questions),
                "project_id": project_id,
                "query": query,
                "similarity_threshold": similarity_threshold
            }
            if historical_questions:
                await self.cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Error fetching historical questions: {str(e)}")
            result = {
                "error": str(e),
                "historical_questions": [],
                "project_id": project_id,
                "query": query
            }
            await self.cache.set(cache_key, result, ttl=300)
            return result

    async def get_views(
        self,
        query: str,
        project_id: str,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch all views for a given query and project."""
        try:
            schema_result = await self.retrievers["table_retrieval"].run(
                query=query,
                project_id=project_id,
                tables=tables
            )
            if not schema_result or "retrieval_results" not in schema_result:
                logger.warning(f"No schema information found for project {project_id}")
                return {
                    "error": "No schema information found",
                    "views": []
                }
            views = []
            for result in schema_result["retrieval_results"]:
                if isinstance(result, dict) and result.get("type") == "VIEW":
                    views.append(result)
            return {
                "views": views,
                "total_views": len(views),
                "project_id": project_id,
                "query": query,
                "tables": tables
            }
        except Exception as e:
            logger.error(f"Error fetching views: {str(e)}")
            return {
                "error": str(e),
                "views": [],
                "project_id": project_id,
                "query": query,
                "tables": tables
            }

    async def get_metrics(
        self,
        query: str,
        project_id: str,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch all metrics for a given query and project."""
        try:
            schema_result = await self.retrievers["table_retrieval"].run(
                query=query,
                project_id=project_id,
                tables=tables
            )
            if not schema_result or "retrieval_results" not in schema_result:
                logger.warning(f"No schema information found for project {project_id}")
                return {
                    "error": "No schema information found",
                    "metrics": []
                }
            metrics = []
            for result in schema_result["retrieval_results"]:
                if isinstance(result, dict) and result.get("type") == "METRICS":
                    metrics.append(result)
            return {
                "metrics": metrics,
                "total_metrics": len(metrics),
                "project_id": project_id,
                "query": query,
                "tables": tables
            }
        except Exception as e:
            logger.error(f"Error fetching metrics: {str(e)}")
            return {
                "error": str(e),
                "metrics": [],
                "project_id": project_id,
                "query": query,
                "tables": tables
            }

    async def get_table_names_and_schema_contexts(
        self,
        query: str,
        project_id: str,
        table_retrieval: dict,
        histories: Optional[list[AskHistory]] = None,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract table names and schema contexts from database schemas.
        
        Args:
            query: The query string to use for schema retrieval
            project_id: The project ID to fetch schemas for
            table_retrieval: Dictionary containing table retrieval configuration
            histories: Optional list of AskHistory objects for context
            tables: Optional list of specific tables to retrieve schemas for
            
        Returns:
            Dictionary containing table names, schema contexts, and metadata
        """
        try:
            # Get database schemas first
            schema_result = await self.get_database_schemas(
                project_id=project_id,
                table_retrieval=table_retrieval,
                query=query,
                histories=histories,
                tables=tables
            )
            
            table_names = []
            schema_contexts = []
            all_relationships = []
            
            if schema_result and "schemas" in schema_result:
                print(f"Found {len(schema_result['schemas'])} schemas in schema_result")
                for i, schema in enumerate(schema_result["schemas"]):
                    print(f"Processing schema {i}: {type(schema)}, keys: {list(schema.keys()) if isinstance(schema, dict) else 'Not a dict'}")
                    if isinstance(schema, dict):
                        # Extract table name from schema
                        table_name = schema.get("table_name", "")
                        if table_name:
                            table_names.append(table_name)
                        
                        # Extract table DDL from schema
                        table_ddl = schema.get("table_ddl", "")
                        print(f"table_ddl in get_table_names_and_schema_contexts: table_name={table_name}, table_ddl_length={len(table_ddl) if table_ddl else 0}")
                        if table_ddl:
                            schema_contexts.append(table_ddl)
                            print(f"Added table_ddl to schema_contexts: {table_ddl[:100]}...")
                        else:
                            print(f"No table_ddl found for table: {table_name}")
                        # Extract relationships from schema
                        relationships = schema.get("relationships", [])
                        if relationships:
                            all_relationships.extend(relationships)
            
            return {
                "table_names": table_names,
                "schema_contexts": schema_contexts,
                "relationships": all_relationships,
                "total_tables": len(table_names),
                "total_contexts": len(schema_contexts),
                "total_relationships": len(all_relationships),
                "project_id": project_id,
                "query": query,
                "has_calculated_field": schema_result.get("has_calculated_field", False),
                "has_metric": schema_result.get("has_metric", False),
                "error": schema_result.get("error", None)
            }
            
        except Exception as e:
            logger.error(f"Error extracting table names and schema contexts: {str(e)}")
            return {
                "table_names": [],
                "schema_contexts": [],
                "relationships": [],
                "total_tables": 0,
                "total_contexts": 0,
                "total_relationships": 0,
                "project_id": project_id,
                "query": query,
                "has_calculated_field": False,
                "has_metric": False,
                "error": str(e)
            }

    async def search(
        self,
        query: str,
        collection_name: str,
        project_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generic search method for different collection types
        
        Args:
            query: Search query
            collection_name: Name of the collection to search
            project_id: Project identifier
            top_k: Number of results to return
            
        Returns:
            List of search results
        """
        try:
            # Map collection names to appropriate retrieval methods
            if collection_name == "conditional_formatting_history":
                # Use historical questions for conditional formatting history
                result = await self.get_historical_questions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.7
                )
                return result.get("historical_questions", [])[:top_k]
                
            elif collection_name == "filter_examples":
                # Use instructions for filter examples
                result = await self.get_instructions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.7
                )
                return result.get("instructions", [])[:top_k]
                
            elif collection_name == "sql_pairs":
                # Use SQL pairs for SQL examples
                result = await self.get_sql_pairs(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.7,
                    max_retrieval_size=top_k
                )
                return result.get("sql_pairs", [])[:top_k]
                
            else:
                # Default to historical questions for unknown collections
                logger.warning(f"Unknown collection name: {collection_name}, using historical questions")
                result = await self.get_historical_questions(
                    query=query,
                    project_id=project_id,
                    similarity_threshold=0.7
                )
                return result.get("historical_questions", [])[:top_k]
                
        except Exception as e:
            logger.error(f"Error in search method: {e}")
            return []

    async def _get_column_metadata_for_table(self, table_name: str, project_id: str) -> List[Dict[str, Any]]:
        """Retrieve column metadata for a specific table from column_metadata store.
        
        Simplified to query with just project_id filter, then filter by table_name in Python.
        """
        try:
            # Use core column_metadata store if available (for Qdrant with core_ prefix), otherwise use default store
            if "column_metadata" in self._core_document_stores:
                column_store = self._core_document_stores["column_metadata"]
                logger.info("Using core column_metadata store (Qdrant with core_ prefix)")
            elif "column_metadata" in self.document_stores:
                column_store = self.document_stores["column_metadata"]
            else:
                logger.warning("Column metadata store not available")
                return []
            
            # Simplified: query with just project_id filter
            where_clause = {"project_id": {"$eq": project_id}}
            logger.info(f"DEBUG: Column metadata search - using filter: project_id={project_id}")
            logger.debug(f"Searching for column metadata for project_id={project_id}, will filter by table_name={table_name}")
            
            results = column_store.semantic_search(
                query="",
                k=1000,  # Get all columns for the project
                where=where_clause
            )
            
            logger.info(f"Found {len(results)} results from column metadata store for project_id={project_id}")
            
            # Parse results and filter by table_name
            column_metadata = []
            for i, result in enumerate(results):
                try:
                    # Try to get table_name from metadata first
                    meta = result.get("metadata", {})
                    result_table_name = meta.get("table_name", "")
                    
                    # If not in metadata, try to parse from content
                    if not result_table_name and "content" in result:
                        try:
                            import json
                            content = json.loads(result["content"])
                            result_table_name = content.get("table_name", "")
                        except:
                            pass
                    
                    # Filter by table_name
                    if result_table_name != table_name:
                        continue
                    
                    # Parse column info from content or metadata
                    if isinstance(result, dict) and "content" in result:
                        try:
                            import json
                            content = json.loads(result["content"])
                        except:
                            # If content is already a dict or not JSON, use metadata
                            content = meta
                    else:
                        content = meta
                    
                    column_info = {
                        "column_name": content.get("column_name", meta.get("column_name", "")),
                        "type": content.get("type", meta.get("type", "")),
                        "display_name": content.get("display_name", meta.get("display_name", "")),
                        "description": content.get("description", meta.get("description", "")),
                        "is_calculated": content.get("is_calculated", meta.get("is_calculated", False)),
                        "is_primary_key": content.get("is_primary_key", meta.get("is_primary_key", False)),
                        "is_foreign_key": content.get("is_foreign_key", meta.get("is_foreign_key", False))
                    }
                    column_metadata.append(column_info)
                    logger.debug(f"Parsed column info: {column_info}")
                    
                    # Debug logging for active column specifically
                    if column_info["column_name"] == "active":
                        logger.debug(f"Found active column metadata:")
                        logger.debug(f"  Column name: {column_info['column_name']}")
                        logger.debug(f"  Data type: {column_info['type']}")
                        logger.debug(f"  Raw content: {content}")
                except Exception as e:
                    logger.warning(f"Error parsing column metadata: {e}")
                    continue
            
            logger.info(f"Returning {len(column_metadata)} column metadata entries for table {table_name}")
            return column_metadata
            
        except Exception as e:
            logger.error(f"Error retrieving column metadata for table {table_name}: {e}")
            return []

    async def get_sql_functions(
        self,
        query: Optional[str] = None,
        data_source: Optional[str] = None,
        project_id: Optional[str] = None,
        k: int = 10,
        similarity_threshold: float = 0.7,
        max_results: int = 3
    ) -> Dict[str, Any]:
        """Retrieve SQL functions using semantic search or filtering.
        
        Args:
            query: Optional natural language query to search for relevant functions.
                   If provided, uses semantic search. If None, retrieves all functions.
            data_source: Optional data source identifier to filter functions.
                        If None, retrieves all SQL functions.
            project_id: Optional project ID to filter functions by project.
                       If None, retrieves all SQL functions regardless of project.
            k: Number of results to retrieve from semantic search (default: 10)
            similarity_threshold: Minimum similarity score to include (0-1, default: 0.7)
            max_results: Maximum number of functions to return (default: 3)
            
        Returns:
            Dictionary containing SQL functions and metadata (only functions meeting relevance threshold, up to max_results)
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_sql_functions',
            'query': query,
            'data_source': data_source,
            'project_id': project_id,
            'k': k,
            'similarity_threshold': similarity_threshold,
            'max_results': max_results
        }, sort_keys=True, default=str).encode()).hexdigest()
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self.sql_functions_retriever:
                logger.warning("SQL functions retriever not available")
                result = {
                    "error": "SQL functions retriever not available",
                    "sql_functions": []
                }
                return result
            
            # Retrieve SQL functions using semantic search if query provided
            sql_functions = await self.sql_functions_retriever.run(
                query=query,
                data_source=data_source,
                project_id=project_id,
                k=k,
                similarity_threshold=similarity_threshold,
                max_results=max_results
            )
            
            # Convert SqlFunction objects to dictionaries with full metadata
            functions_list = []
            for func in sql_functions:
                # Try to get full metadata from the document store if available
                func_dict = {
                    "name": func._expr.split('(')[0] if func._expr else "",
                    "expression": str(func),
                    "definition": func._expr if hasattr(func, '_expr') else str(func)
                }
                
                # Add similarity score if available
                if hasattr(func, '_similarity'):
                    func_dict["similarity_score"] = func._similarity
                
                # If we have access to the original metadata, include it
                if hasattr(func, '_definition'):
                    func_dict.update({
                        "description": func._definition.get("description", ""),
                        "parameters": func._definition.get("parameters", []),
                        "returns": func._definition.get("returns", ""),
                        "usage": func._definition.get("usage", "")
                    })
                # Add examples and instructions from core_ds_* collections when available
                if hasattr(func, '_examples') and func._examples:
                    func_dict["examples"] = func._examples
                if hasattr(func, '_instructions') and func._instructions:
                    func_dict["instructions"] = func._instructions

                functions_list.append(func_dict)
            
            result = {
                "sql_functions": functions_list,
                "total_functions": len(functions_list),
                "query": query or "all",
                "data_source": data_source or "all",
                "project_id": project_id or "all",
                "similarity_threshold": similarity_threshold,
                "max_results": max_results
            }
            
            if functions_list:
                await self.cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving SQL functions: {str(e)}")
            result = {
                "error": str(e),
                "sql_functions": [],
                "query": query or "all",
                "data_source": data_source or "all",
                "project_id": project_id or "all",
                "similarity_threshold": similarity_threshold,
                "max_results": max_results
            }
            await self.cache.set(cache_key, result, ttl=300)
            return result

    async def get_knowledge_documents(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
        framework: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve knowledge documents for feature engineering context.
        
        Args:
            query: Search query to match against knowledge documents
            project_id: Optional project ID (kept for API consistency)
            top_k: Number of documents to return
            framework: Optional framework filter (e.g., "SOC2", "PCI-DSS", "HIPAA")
            category: Optional category filter (e.g., "compliance", "exploitability", "sla_compliance")
            
        Returns:
            Dictionary containing knowledge documents and metadata
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_knowledge_documents',
            'query': query,
            'project_id': project_id,
            'top_k': top_k,
            'framework': framework,
            'category': category
        }, sort_keys=True, default=str).encode()).hexdigest()
        
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Use dummy knowledge handler to retrieve documents
            documents = self.knowledge_handler.get_knowledge_documents(
                query=query,
                project_id=project_id,
                top_k=top_k,
                framework=framework,
                category=category
            )
            
            result = {
                "documents": documents,
                "total_documents": len(documents),
                "query": query,
                "project_id": project_id,
                "framework": framework,
                "category": category
            }
            
            if documents:
                await self.cache.set(cache_key, result, ttl=300)
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge documents: {str(e)}")
            result = {
                "error": str(e),
                "documents": [],
                "total_documents": 0,
                "query": query,
                "project_id": project_id
            }
            await self.cache.set(cache_key, result, ttl=300)
            return result


async def main():
    """Main function to test the RetrievalHelper functionality."""
    try:
        # Initialize settings and ensure environment variables are set
        from app.settings import get_settings, set_os_environ
        from app.core.dependencies import clear_chromadb_cache
        settings = get_settings()
        set_os_environ(settings)
        logger.info("Settings initialized and environment variables set")
        
        # Clear ChromaDB cache to ensure we get the latest document store provider with sql_functions
        clear_chromadb_cache()
        logger.info("ChromaDB cache cleared to ensure latest stores are available")
        
        # Initialize helper
        helper = RetrievalHelper()
        
        # Test configuration
        test_project_id = "cornerstone"  # Replace with your project ID
        test_query = "Show me all tables and their columns"
        test_table_retrieval = {
            "table_retrieval_size": 10,
            "table_column_retrieval_size": 100,
            "allow_using_db_schemas_without_pruning": False
        }
        test_tables = ["users", "orders", "products"]  # Example tables to test with
        
        logger.info("=" * 80)
        logger.info("STARTING RETRIEVAL HELPER TEST")
        logger.info("=" * 80)
        
        # Test database schema retrieval
        logger.info(f"\n🔍 Testing database schema retrieval with query: '{test_query}'")
        logger.info(f"Project ID: {test_project_id}")
        logger.info(f"Table retrieval config: {test_table_retrieval}")
        logger.info(f"Test tables: {test_tables}")
        
        try:
            schema_results = await helper.get_database_schemas(
                project_id=test_project_id,
                table_retrieval=test_table_retrieval,
                query=test_query,
                tables=test_tables
            )
            logger.info(f"✅ Database schema retrieval completed")
        except Exception as e:
            logger.error(f"❌ Database schema retrieval failed: {str(e)}")
            schema_results = {"error": str(e)}
        
        # Test SQL pairs retrieval
        logger.info(f"\n🔍 Testing SQL pairs retrieval with query: '{test_query}'")
        try:
            sql_pairs_results = await helper.get_sql_pairs(
                query=test_query,
                project_id=test_project_id
            )
            logger.info(f"✅ SQL pairs retrieval completed")
        except Exception as e:
            logger.error(f"❌ SQL pairs retrieval failed: {str(e)}")
            sql_pairs_results = {"error": str(e)}
        
        # Test instructions retrieval
        logger.info(f"\n🔍 Testing instructions retrieval with query: '{test_query}'")
        try:
            instructions_results = await helper.get_instructions(
                query=test_query,
                project_id=test_project_id
            )
            logger.info(f"✅ Instructions retrieval completed")
        except Exception as e:
            logger.error(f"❌ Instructions retrieval failed: {str(e)}")
            instructions_results = {"error": str(e)}
        
        # Test historical questions retrieval
        logger.info(f"\n🔍 Testing historical questions retrieval with query: '{test_query}'")
        try:
            historical_results = await helper.get_historical_questions(
                query=test_query,
                project_id=test_project_id
            )
            logger.info(f"✅ Historical questions retrieval completed")
        except Exception as e:
            logger.error(f"❌ Historical questions retrieval failed: {str(e)}")
            historical_results = {"error": str(e)}
        
        # Test views retrieval
        logger.info(f"\n🔍 Testing views retrieval with query: '{test_query}'")
        try:
            views_results = await helper.get_views(
                query=test_query,
                project_id=test_project_id,
                tables=test_tables
            )
            logger.info(f"✅ Views retrieval completed")
        except Exception as e:
            logger.error(f"❌ Views retrieval failed: {str(e)}")
            views_results = {"error": str(e)}
        
        # Test metrics retrieval
        logger.info(f"\n🔍 Testing metrics retrieval with query: '{test_query}'")
        try:
            metrics_results = await helper.get_metrics(
                query=test_query,
                project_id=test_project_id,
                tables=test_tables
            )
            logger.info(f"✅ Metrics retrieval completed")
        except Exception as e:
            logger.error(f"❌ Metrics retrieval failed: {str(e)}")
            metrics_results = {"error": str(e)}
        
        # Test SQL functions retrieval
        logger.info(f"\n🔍 Testing SQL functions retrieval")
        try:
            # Test with natural language query, relevance threshold, and max 3 results
            sql_functions_results = await helper.get_sql_functions(
                query="Create a remediation priority list combining risk score, asset criticality, and breach method likelihood",
                similarity_threshold=0.7,
                max_results=3
            )
            logger.info(f"Retrieved Functions: {sql_functions_results}")
            logger.info(f"✅ SQL functions retrieval completed")
        except Exception as e:
            logger.error(f"❌ SQL functions retrieval failed: {str(e)}")
            sql_functions_results = {"error": str(e)}
        
        # Test table names and schema contexts extraction
        logger.info(f"\n🔍 Testing table names and schema contexts extraction")
        try:
            table_contexts_results = await helper.get_table_names_and_schema_contexts(
                query=test_query,
                project_id=test_project_id,
                table_retrieval=test_table_retrieval,
                tables=test_tables
            )
            logger.info(f"✅ Table names and schema contexts extraction completed")
        except Exception as e:
            logger.error(f"❌ Table names and schema contexts extraction failed: {str(e)}")
            table_contexts_results = {"error": str(e)}
        
        # Print detailed results
        logger.info("\n" + "=" * 80)
        logger.info("DETAILED RESULTS")
        logger.info("=" * 80)
        
        # Print database schema results
        logger.info("\n📊 Database Schema Retrieval Results:")
        if "error" in schema_results:
            logger.error(f"❌ Error: {schema_results['error']}")
        else:
            logger.info(f"✅ Total schemas found: {schema_results.get('total_schemas', 0)}")
            schemas = schema_results.get('schemas', [])
            for i, schema in enumerate(schemas, 1):
                logger.info(f"\n📋 Schema {i}:")
                logger.info(f"   Table Name: {schema.get('table_name', 'N/A')}")
                
                # Extract description from table_ddl if it exists
                table_ddl = schema.get('table_ddl', '')
                if table_ddl and table_ddl.startswith('--'):
                    description = table_ddl.split('\n')[0].replace('--', '').strip()
                    if description:
                        logger.info(f"   Description: {description}")
                
                # Extract columns from table_ddl
                if table_ddl:
                    logger.info("   Columns:")
                    lines = table_ddl.split('\n')
                    for line in lines:
                        if line.strip() and not line.startswith('--') and not line.startswith('CREATE'):
                            col_def = line.strip().rstrip(',').strip()
                            if col_def:
                                logger.info(f"     - {col_def}")
                
                # Log additional metadata
                logger.info(f"   Has Calculated Field: {schema.get('has_calculated_field', False)}")
                logger.info(f"   Has Metric: {schema.get('has_metric', False)}")
                
                # Log if it's a view
                if 'CREATE VIEW' in table_ddl:
                    logger.info("   Type: View")
                else:
                    logger.info("   Type: Table")
        
        # Print SQL pairs results
        logger.info("\n📊 SQL Pairs Retrieval Results:")
        if "error" in sql_pairs_results:
            logger.error(f"❌ Error: {sql_pairs_results['error']}")
        else:
            logger.info(f"✅ Total SQL pairs found: {sql_pairs_results.get('total_pairs', 0)}")
            sql_pairs = sql_pairs_results.get('sql_pairs', [])
            for i, pair in enumerate(sql_pairs, 1):
                logger.info(f"\n💬 SQL Pair {i}:")
                logger.info(f"   Question: {pair.get('question', 'N/A')}")
                logger.info(f"   SQL: {pair.get('sql', 'N/A')}")
                if pair.get('instructions'):
                    logger.info(f"   Instructions: {pair['instructions']}")
                logger.info(f"   Similarity Score: {pair.get('score', 0.0)}")
        
        # Print instructions results
        logger.info("\n📊 Instructions Retrieval Results:")
        if "error" in instructions_results:
            logger.error(f"❌ Error: {instructions_results['error']}")
        else:
            logger.info(f"✅ Total instructions found: {instructions_results.get('total_instructions', 0)}")
            instructions = instructions_results.get('instructions', [])
            for i, instruction in enumerate(instructions, 1):
                logger.info(f"\n📝 Instruction {i}:")
                logger.info(f"   Question: {instruction.get('question', 'N/A')}")
                logger.info(f"   Instruction: {instruction.get('instruction', 'N/A')}")
                if instruction.get('instruction_id'):
                    logger.info(f"   Instruction ID: {instruction['instruction_id']}")
        
        # Print historical questions results
        logger.info("\n📊 Historical Questions Retrieval Results:")
        if "error" in historical_results:
            logger.error(f"❌ Error: {historical_results['error']}")
        else:
            logger.info(f"✅ Total historical questions found: {historical_results.get('total_questions', 0)}")
            historical_questions = historical_results.get('historical_questions', [])
            for i, question in enumerate(historical_questions, 1):
                logger.info(f"\n🕒 Historical Question {i}:")
                logger.info(f"   Question: {question.get('question', 'N/A')}")
                if question.get('summary'):
                    logger.info(f"   Summary: {question['summary']}")
                if question.get('statement'):
                    logger.info(f"   Statement: {question['statement']}")
                if question.get('viewId'):
                    logger.info(f"   View ID: {question['viewId']}")
        
        # Print views results
        logger.info("\n📊 Views Retrieval Results:")
        if "error" in views_results:
            logger.error(f"❌ Error: {views_results['error']}")
        else:
            logger.info(f"✅ Total views found: {views_results.get('total_views', 0)}")
            views = views_results.get('views', [])
            for i, view in enumerate(views, 1):
                logger.info(f"\n👁️ View {i}:")
                logger.info(f"   Table Name: {view.get('table_name', 'N/A')}")
                logger.info(f"   Table DDL: {view.get('table_ddl', 'N/A')}")
        
        # Print metrics results
        logger.info("\n📊 Metrics Retrieval Results:")
        if "error" in metrics_results:
            logger.error(f"❌ Error: {metrics_results['error']}")
        else:
            logger.info(f"✅ Total metrics found: {metrics_results.get('total_metrics', 0)}")
            metrics = metrics_results.get('metrics', [])
            for i, metric in enumerate(metrics, 1):
                logger.info(f"\n📈 Metric {i}:")
                logger.info(f"   Metric Name: {metric.get('metric_name', 'N/A')}")
                logger.info(f"   Metric Value: {metric.get('metric_value', 'N/A')}")
        
        # Print SQL functions results
        logger.info("\n📊 SQL Functions Retrieval Results:")
        if "error" in sql_functions_results:
            logger.error(f"❌ Error: {sql_functions_results['error']}")
        else:
            logger.info(f"✅ Query used: {sql_functions_results.get('query', 'N/A')}")
            logger.info(f"✅ Similarity threshold: {sql_functions_results.get('similarity_threshold', 'N/A')}")
            logger.info(f"✅ Max results: {sql_functions_results.get('max_results', 'N/A')}")
            logger.info(f"✅ Total SQL functions found: {sql_functions_results.get('total_functions', 0)}")
            logger.info(f"✅ Data source: {sql_functions_results.get('data_source', 'N/A')}")
            sql_functions = sql_functions_results.get('sql_functions', [])
            if not sql_functions:
                logger.warning("⚠️  No SQL functions found matching the relevance threshold")
            for i, func in enumerate(sql_functions, 1):
                logger.info(f"\n🔧 SQL Function {i}:")
                logger.info(f"   Name: {func.get('name', 'N/A')}")
                logger.info(f"   Expression: {func.get('expression', 'N/A')}")
                if func.get('similarity_score') is not None:
                    logger.info(f"   Similarity Score: {func.get('similarity_score', 0):.3f}")
                if func.get('description'):
                    logger.info(f"   Description: {func.get('description', 'N/A')[:150]}...")
                if func.get('usage'):
                    logger.info(f"   Usage: {func.get('usage', 'N/A')[:150]}...")
                if func.get('definition'):
                    logger.info(f"   Definition: {func.get('definition', 'N/A')[:200]}...")
        
        # Print table names and schema contexts results
        logger.info("\n📊 Table Names and Schema Contexts Results:")
        if "error" in table_contexts_results:
            logger.error(f"❌ Error: {table_contexts_results['error']}")
        else:
            logger.info(f"✅ Total tables: {table_contexts_results.get('total_tables', 0)}")
            logger.info(f"✅ Total contexts: {table_contexts_results.get('total_contexts', 0)}")
            logger.info(f"✅ Total relationships: {table_contexts_results.get('total_relationships', 0)}")
            logger.info(f"✅ Has Calculated Field: {table_contexts_results.get('has_calculated_field', False)}")
            logger.info(f"✅ Has Metric: {table_contexts_results.get('has_metric', False)}")
            
            table_names = table_contexts_results.get('table_names', [])
            if table_names:
                logger.info(f"   Table Names: {', '.join(table_names)}")
        
        logger.info("\n" + "=" * 80)
        logger.info("RETRIEVAL HELPER TEST COMPLETED")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Critical error in main: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise



if __name__ == "__main__":
    asyncio.run(main())

