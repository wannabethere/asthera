"""
Retrieval Helper v2 - Using Unified Storage from Indexing2

This module provides a retrieval helper that uses the unified storage
system from indexing2, providing enhanced document retrieval capabilities.

Features:
- Unified document retrieval using StorageManager
- Natural language search capabilities
- Enhanced schema retrieval with business context
- Support for historical questions, SQL pairs, and instructions
- Column metadata retrieval with enhanced descriptions
"""

import asyncio
import logging
import hashlib
import json
from typing import Dict, Any, Optional, List

from langchain_openai import OpenAIEmbeddings

from app.indexing2.storage_manager import StorageManager
from app.indexing2.natural_language_search import NaturalLanguageSearch
from app.indexing2.sql_pairs import SqlPair
from app.indexing2.historical_question import ViewChunker
from app.indexing2.instructions import Instruction
from app.indexing2.retrieval2 import TableRetrieval2
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.core.dependencies import get_doc_store_provider
from app.utils.cache import InMemoryCache
from app.agents.nodes.sql.utils.sql_prompts import AskHistory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()


class RetrievalHelper2:
    """
    Retrieval Helper v2 using unified storage from indexing2.
    
    This class provides retrieval capabilities using the new unified storage
    system, offering enhanced document retrieval with business context.
    """
    
    def __init__(
        self,
        document_store: Optional[DocumentChromaStore] = None,
        embedder: Optional[Any] = None,
        similarity_threshold: float = 0.7
    ):
        """Initialize the retrieval helper with unified storage components.
        
        Args:
            document_store: Optional document store instance
            embedder: Optional embedder instance
            similarity_threshold: Minimum similarity threshold for retrieval
        """
        logger.info("Initializing Retrieval Helper v2")
        
        # Initialize embeddings
        self.embeddings = embedder or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Use provided document_store or get from provider
        if document_store:
            logger.info("Using provided document store")
            # Use the provided document store for all stores
            self.document_stores = {
                "table_description": document_store,
                "instructions": document_store,
                "historical_question": document_store,
                "sql_pairs": document_store,
                "db_schema": document_store
            }
        else:
            logger.info("Using document store from provider")
            # Get document stores from provider
            self.document_stores = get_doc_store_provider().stores
        
        # Initialize storage manager for unified storage access
        self.storage_manager = StorageManager(
            document_store=document_store or self.document_stores.get("table_description"),
            embedder=self.embeddings,
            enable_tfidf=True
        )
        
        # Initialize natural language search
        self.natural_language_search = NaturalLanguageSearch(
            similarity_threshold=similarity_threshold
        )
        
        # Initialize TableRetrieval2 for LLM-based table and column pruning
        self.table_retrieval = TableRetrieval2(
            document_store=document_store or self.document_stores.get("table_description"),
            embedder=self.embeddings,
            model_name="gpt-4o-mini",
            table_retrieval_size=10  # Default, will be overridden when used
        )
        
        # Cache for retrieval results
        self.cache = InMemoryCache()
        
        logger.info("Retrieval Helper v2 initialized successfully")
    
    async def get_database_schemas(
        self,
        project_id: str,
        table_retrieval: dict,
        query: str,
        histories: Optional[List[AskHistory]] = None,
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch database schemas using unified storage.
        
        Args:
            project_id: The project ID to fetch schemas for
            table_retrieval: Dictionary containing table retrieval configuration
            query: The query string to use for schema retrieval
            histories: Optional list of AskHistory objects for context
            tables: Optional list of specific tables to retrieve schemas for
            
        Returns:
            Dictionary containing database schemas and metadata
        """
        cache_key = hashlib.sha256(json.dumps({
            'method': 'get_database_schemas',
            'project_id': project_id,
            'table_retrieval': table_retrieval,
            'query': query,
            'histories': [h.__dict__ if hasattr(h, '__dict__') else h for h in histories] if histories else None,
            'tables': tables
        }, sort_keys=True, default=str).encode()).hexdigest()
        
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            logger.info(f"Retrieving database schemas for project: {project_id}")
            
            # Use TableRetrieval2 with LLM-based pruning to select relevant tables and columns
            # This will handle: fetching tables (or all tables if none found), then pruning with LLM
            logger.info("Using TableRetrieval2 for LLM-based table and column pruning")
            
            # Convert histories format for TableRetrieval2
            histories_for_retrieval = None
            if histories:
                histories_for_retrieval = [
                    {"question": h.question, "sql": h.sql, "chat_id": getattr(h, 'chat_id', None)}
                    for h in histories if hasattr(h, 'question')
                ]
            
            # Call TableRetrieval2 to get pruned results with LLM
            retrieval_result = await self.table_retrieval.run(
                query=query,
                tables=tables,
                project_id=project_id,
                histories=histories_for_retrieval
            )
            
            logger.info(f"TableRetrieval2 returned {len(retrieval_result.get('retrieval_results', []))} pruned tables")
            
            # Convert retrieval results to schema format
            schemas = []
            for result in retrieval_result.get('retrieval_results', []):
                schema_info = {
                    "table_name": result.get("table_name", ""),
                    "table_ddl": result.get("table_ddl", ""),
                    "column_metadata": result.get("column_metadata", []),
                    "relationships": result.get("relationships", []),
                    "has_calculated_field": retrieval_result.get('has_calculated_field', False),
                    "has_metric": retrieval_result.get('has_metric', False),
                    "relevance_score": result.get("relevance_score", 0.0)
                }
                schemas.append(schema_info)
            
            result = {
                "schemas": schemas,
                "total_schemas": len(schemas),
                "project_id": project_id,
                "query": query,
                "retrieval_config": table_retrieval,
                "tables": tables
            }
            
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
    
    async def _search_chromadb_for_tables(
        self,
        query: str,
        project_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search directly in ChromaDB for tables when natural language search is not available."""
        results = []
        
        try:
            # Get the document store - use unified storage
            table_store = self.document_stores.get("table_description")
            if not table_store:
                logger.warning("Table description store not available")
                return results
            
            logger.info("Searching directly in ChromaDB for tables")
            
            # Search for TABLE_SCHEMA documents in unified storage
            # Documents use 'type' field in metadata
            where_clause = {"type": {"$eq": "TABLE_SCHEMA"}}
            if project_id and project_id != "default":
                where_clause = {"$and": [{"project_id": {"$eq": project_id}}, {"type": {"$eq": "TABLE_SCHEMA"}}]}
            
            logger.info(f"Searching with where clause: {where_clause}")
            
            # If query is empty, use collection.get() directly instead of semantic_search
            if not query or not query.strip():
                logger.info("Empty query - using collection.get() to retrieve all documents")
                try:
                    all_docs = table_store.collection.get(
                        where=where_clause,
                        limit=limit
                    )
                    # Convert to the expected format
                    chroma_results = []
                    if all_docs.get('ids'):
                        for i, doc_id in enumerate(all_docs['ids']):
                            doc_content = all_docs.get('documents', [])[i] if all_docs.get('documents') else ""
                            doc_metadata = all_docs.get('metadatas', [])[i] if all_docs.get('metadatas') else {}
                            
                            result = {
                                'content': doc_content,
                                'metadata': doc_metadata or {},
                                'id': doc_id
                            }
                            chroma_results.append(result)
                    
                    logger.info(f"Found {len(chroma_results)} results using collection.get()")
                except Exception as e:
                    logger.warning(f"Error getting all documents: {str(e)}")
                    chroma_results = []
            else:
                # Perform semantic search with the query
                chroma_results = table_store.semantic_search(
                    query=query,
                    k=limit,
                    where=where_clause
                )
                
                logger.info(f"Found {len(chroma_results)} results from query-based ChromaDB search")
                
                # If no results from query-based search, get all tables without semantic search
                if not chroma_results:
                    logger.info("No results from query-based search, retrieving all tables using collection.get()")
                    # Use collection.get() instead of semantic_search to get all documents
                    try:
                        all_docs = table_store.collection.get(
                            where=where_clause,
                            limit=limit
                        )
                        # Convert to the expected format
                        chroma_results = []
                        if all_docs.get('ids'):
                            for i, doc_id in enumerate(all_docs['ids']):
                                doc_content = all_docs.get('documents', [])[i] if all_docs.get('documents') else ""
                                doc_metadata = all_docs.get('metadatas', [])[i] if all_docs.get('metadatas') else {}
                                
                                result = {
                                    'content': doc_content,
                                    'metadata': doc_metadata or {},
                                    'id': doc_id
                                }
                                chroma_results.append(result)
                        
                        logger.info(f"Found {len(chroma_results)} results using collection.get()")
                    except Exception as e:
                        logger.warning(f"Error getting all documents: {str(e)}")
                        chroma_results = []
            
            # Convert to our format
            for doc in chroma_results:
                try:
                    # Unified storage documents have content as a dictionary string
                    content = doc.get('content', '{}')
                    metadata = doc.get('metadata', {})
                    
                    # Try to parse content as JSON
                    try:
                        if isinstance(content, str):
                            content_dict = json.loads(content)
                        else:
                            content_dict = content
                    except:
                        content_dict = {}
                    
                    # Extract table information from unified storage format
                    # Unified storage has different structure
                    table_name = metadata.get('table_name', content_dict.get('name', ''))
                    display_name = metadata.get('display_name', content_dict.get('properties', {}).get('displayName', ''))
                    description = metadata.get('description', content_dict.get('properties', {}).get('description', ''))
                    business_purpose = content_dict.get('properties', {}).get('businessPurpose', '')
                    
                    # Extract columns and relationships
                    columns = content_dict.get('columns', [])
                    relationships = content_dict.get('relationships', [])
                    
                    result = {
                        "table_name": table_name,
                        "display_name": display_name,
                        "description": description,
                        "business_purpose": business_purpose,
                        "metadata": {
                            "columns": columns,
                            "relationships": relationships,
                            "type": "TABLE_SCHEMA"
                        },
                        "relevance_score": 1.0
                    }
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.warning(f"Error processing table result: {str(e)}")
                    continue
            
            logger.info(f"Found {len(results)} tables from direct ChromaDB search")
            
        except Exception as e:
            logger.error(f"Error in direct ChromaDB table search: {str(e)}")
        
        return results
    
    async def get_sql_pairs(
        self,
        query: str,
        project_id: str,
        similarity_threshold: float = 0.3,
        max_retrieval_size: int = 10
    ) -> Dict[str, Any]:
        """Fetch SQL pairs using unified storage.
        
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
            # Search for SQL pairs in the document store
            sql_pairs_store = self.document_stores.get("sql_pairs")
            if not sql_pairs_store:
                return {
                    "error": "SQL pairs store not available",
                    "sql_pairs": []
                }
            
            # Perform semantic search
            results = sql_pairs_store.semantic_search(
                query=query,
                k=max_retrieval_size,
                where={"project_id": {"$eq": project_id}} if project_id else None
            )
            
            sql_pairs = []
            for doc in results:
                try:
                    content = json.loads(doc.get('content', '{}'))
                    if content.get('type') == 'SQL_PAIR':
                        sql_pair = {
                            "question": content.get("question", ""),
                            "sql": content.get("sql", ""),
                            "instructions": content.get("instructions", ""),
                            "chain_of_thought": content.get("chain_of_thought", ""),
                            "score": doc.get("score", 0.0),
                            "raw_distance": doc.get("raw_distance", 0.0)
                        }
                        sql_pairs.append(sql_pair)
                except Exception as e:
                    logger.warning(f"Error parsing SQL pair: {str(e)}")
                    continue
            
            result = {
                "sql_pairs": sql_pairs,
                "total_pairs": len(sql_pairs),
                "project_id": project_id,
                "query": query
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
        """Fetch instructions using unified storage.
        
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
            # Search for instructions in the document store
            instructions_store = self.document_stores.get("instructions")
            if not instructions_store:
                return {
                    "error": "Instructions store not available",
                    "instructions": []
                }
            
            # Perform semantic search
            results = instructions_store.semantic_search(
                query=query,
                k=top_k,
                where={"project_id": {"$eq": project_id}} if project_id else None
            )
            
            instructions = []
            for doc in results:
                try:
                    content = json.loads(doc.get('content', '{}'))
                    if content.get('type') == 'INSTRUCTION':
                        instruction = {
                            "instruction": doc.get('metadata', {}).get('instruction', ''),
                            "question": content.get("question", ""),
                            "instruction_id": doc.get('metadata', {}).get('instruction_id', ''),
                            "sql": content.get("sql", ""),
                            "chain_of_thought": content.get("chain_of_thought", ""),
                            "is_default": content.get("is_default", False)
                        }
                        instructions.append(instruction)
                except Exception as e:
                    logger.warning(f"Error parsing instruction: {str(e)}")
                    continue
            
            result = {
                "instructions": instructions,
                "total_instructions": len(instructions),
                "project_id": project_id,
                "query": query
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
        """Fetch historical questions using unified storage.
        
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
            # Search for historical questions in the document store
            historical_store = self.document_stores.get("historical_question")
            if not historical_store:
                return {
                    "error": "Historical question store not available",
                    "historical_questions": []
                }
            
            # Perform semantic search
            results = historical_store.semantic_search(
                query=query,
                k=10,
                where={"project_id": {"$eq": project_id}} if project_id else None
            )
            
            historical_questions = []
            for doc in results:
                try:
                    content = json.loads(doc.get('content', '{}'))
                    if content.get('type') == 'HISTORY':
                        question = {
                            "question": content.get("question", ""),
                            "historical_queries": content.get("historical_queries", []),
                            "statement": content.get("statement", ""),
                            "summary": doc.get('metadata', {}).get('summary', ""),
                            "viewId": doc.get('metadata', {}).get('viewId', "")
                        }
                        historical_questions.append(question)
                except Exception as e:
                    logger.warning(f"Error parsing historical question: {str(e)}")
                    continue
            
            result = {
                "historical_questions": historical_questions,
                "total_questions": len(historical_questions),
                "project_id": project_id,
                "query": query
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
    
    async def get_table_names_and_schema_contexts(
        self,
        query: str,
        project_id: str,
        table_retrieval: dict,
        histories: Optional[List[AskHistory]] = None,
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
                for schema in schema_result["schemas"]:
                    if isinstance(schema, dict):
                        # Extract table name from schema
                        table_name = schema.get("table_name", "")
                        if table_name:
                            table_names.append(table_name)
                        
                        # Extract table DDL from schema
                        table_ddl = schema.get("table_ddl", "")
                        if table_ddl:
                            schema_contexts.append(table_ddl)
                        
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
    
    def _build_table_ddl_from_result(self, result: Dict[str, Any]) -> str:
        """Build table DDL from unified storage result."""
        try:
            table_name = result.get("table_name", "")
            display_name = result.get("display_name", "")
            description = result.get("description", "")
            business_purpose = result.get("business_purpose", "")
            
            # Build DDL with enhanced context
            ddl_parts = []
            
            # Add description comment
            if description:
                ddl_parts.append(f"-- {description}")
            
            # Add business purpose comment
            if business_purpose:
                ddl_parts.append(f"-- Purpose: {business_purpose}")
            
            # Add CREATE TABLE statement
            ddl_parts.append(f"CREATE TABLE {table_name} (")
            
            # Add column definitions
            columns = result.get("metadata", {}).get("columns", [])
            for i, column in enumerate(columns):
                col_def = self._build_column_definition(column)
                ddl_parts.append(f"  {col_def}{',' if i < len(columns) - 1 else ''}")
            
            ddl_parts.append(");")
            
            return "\n".join(ddl_parts)
            
        except Exception as e:
            logger.error(f"Error building DDL from result: {str(e)}")
            return ""
    
    def _build_column_definition(self, column: Dict[str, Any]) -> str:
        """Build column definition string."""
        try:
            logger.info(f"Building column definition for column: {json.dumps(column, indent=2)}")
            name = column.get("name", "")
            data_type = column.get("data_type", "VARCHAR")
            comment = column.get("comment", "") or column.get("comments", "")
            
            col_def = f"{name} {data_type}"
            
            if comment:
                col_def += f" -- {comment}"
            
            return col_def
            
        except Exception as e:
            logger.error(f"Error building column definition: {str(e)}")
            return ""
    
    def _check_has_calculated_field(self, result: Dict[str, Any]) -> bool:
        """Check if result has calculated fields."""
        try:
            columns = result.get("metadata", {}).get("columns", [])
            for column in columns:
                if column.get("is_calculated", False):
                    return True
            return False
        except Exception:
            return False


# Test function
async def main():
    """Test the RetrievalHelper2 functionality."""
    try:
        helper = RetrievalHelper2()
        
        test_project_id = "test_project"
        test_query = "Show me sales data"
        
        logger.info("Testing database schema retrieval")
        schema_results = await helper.get_database_schemas(
            project_id=test_project_id,
            table_retrieval={"table_retrieval_size": 10},
            query=test_query
        )
        logger.info(f"Schema results: {schema_results}")
        
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

