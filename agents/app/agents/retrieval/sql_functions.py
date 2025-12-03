import logging
from typing import Any, Dict, List, Optional

import aiohttp
from cachetools import TTLCache


from app.storage.documents import DocumentChromaStore

logger = logging.getLogger("genieml-agents")


class SqlFunction:
    """Represents a SQL function with its parameters and return type."""
    
    _expr: str = None
    _definition: dict = None

    def __init__(self, definition: dict):
        """Initialize a SQL function from its definition.
        
        Args:
            definition: Dictionary containing function definition
        """
        # Store the original definition
        self._definition = definition
        
        def _extract() -> tuple[str, list, str]:
            name = definition["name"]

            _param_types = definition.get("param_types") or "any"
            param_types = _param_types.split(",") if _param_types else []

            return_type = definition.get("return_type") or "any"

            if return_type in ["same as input", "same as arg types"]:
                return_type = param_types

            return name, param_types, return_type

        def _param_expr(param_type: str, index: int) -> str:
            if param_type == "any":
                return "any"

            param_type = param_type.strip()
            param_name = f"${index}"
            return f"{param_name}: {param_type}"

        name, param_types, return_type = _extract()

        params = [_param_expr(type, index) for index, type in enumerate(param_types)]
        param_str = ", ".join(params)

        self._expr = f"{name}({param_str}) -> {return_type}"

    def __str__(self):
        return self._expr

    def __repr__(self):
        return self._expr


class SqlFunctions:
    """Manages SQL functions retrieval and caching."""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        engine_timeout: Optional[float] = 30.0,
        ttl: Optional[int] = 60 * 60 * 24,
    ) -> None:
        """Initialize the SQL functions manager.
        
        Args:
            document_store: The Chroma document store instance
            engine_timeout: Timeout for engine operations in seconds
            ttl: Time-to-live for cache in seconds
        """
        self._document_store = document_store
        self._cache = TTLCache(maxsize=100, ttl=ttl)
        self._engine_timeout = engine_timeout

   
    async def run(
        self,
        query: Optional[str] = None,
        data_source: Optional[str] = None,
        project_id: Optional[str] = None,
        k: int = 10,
        similarity_threshold: float = 0.7,
        max_results: int = 3
    ) -> List[SqlFunction]:
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
            List of SQL functions that meet the relevance threshold (up to max_results)
            
        Raises:
            Exception: If function retrieval fails
        """
        logger.info(
            f"SQL Functions Retrieval is running... (query: {query or 'all'}, data_source: {data_source or 'all'}, project_id: {project_id or 'all'}, threshold: {similarity_threshold}, max: {max_results})"
        )

        try:
            # Use cache key based on query, data_source, project_id, threshold, and max_results
            cache_key = f"{query or 'all'}_{data_source or 'all'}_{project_id or 'all'}_{similarity_threshold}_{max_results}"
            
            if cache_key in self._cache:
                logger.info(f"Hit cache of SQL Functions for {cache_key}")
                return self._cache[cache_key]

            # If query is provided, use semantic search
            if query:
                # Build where clause with proper ChromaDB operators
                # ChromaDB requires at least 2 conditions for $and, so handle single condition separately
                where_conditions = [
                    {"type": {"$eq": "SQL_FUNCTION"}}
                ]
                
                # Optionally filter by data_source if provided
                if data_source:
                    where_conditions.append({"data_source": {"$eq": data_source}})
                
                # Optionally filter by project_id if provided
                if project_id and project_id != "default":
                    where_conditions.append({"project_id": {"$eq": project_id}})
                
                # Build where clause - use $and only if we have 2+ conditions
                if len(where_conditions) > 1:
                    where_clause = {"$and": where_conditions}
                elif len(where_conditions) == 1:
                    where_clause = where_conditions[0]
                else:
                    where_clause = None
                
                # Use semantic search to find relevant functions
                # semantic_search is synchronous
                search_results = self._document_store.semantic_search(
                    query=query,
                    k=k,
                    where=where_clause
                )
                
                if not search_results:
                    logger.info(f"No SQL functions found for query: {query}")
                    return []
                
                # Filter by similarity threshold and convert to SqlFunction objects
                sql_functions = []
                for result in search_results:
                    # Get similarity score (lower is better in ChromaDB, so we check if score <= (1 - threshold))
                    score = result.get("score", 1.0)
                    # ChromaDB uses distance, so lower is better. Convert to similarity (higher is better)
                    similarity = 1.0 - score if score <= 1.0 else 0.0
                    
                    # Only include if similarity meets threshold
                    if similarity < similarity_threshold:
                        logger.debug(f"Skipping function with similarity {similarity:.3f} (threshold: {similarity_threshold})")
                        continue
                    
                    # Extract metadata from search result
                    metadata = result.get("metadata", {})
                    # Also try to parse content if it's JSON
                    content = result.get("content", "")
                    if not metadata and content:
                        try:
                            import json
                            content_dict = json.loads(content)
                            if isinstance(content_dict, dict):
                                metadata = content_dict
                        except:
                            pass
                    
                    if metadata:
                        try:
                            sql_function = SqlFunction(definition=metadata)
                            # Store similarity score in the function object for reference
                            sql_function._similarity = similarity
                            sql_functions.append(sql_function)
                            
                            # Stop if we've reached max_results
                            if len(sql_functions) >= max_results:
                                break
                        except Exception as e:
                            logger.warning(f"Error creating SqlFunction from metadata: {e}")
                            continue
                
                # Cache the results
                self._cache[cache_key] = sql_functions
                logger.info(f"Retrieved {len(sql_functions)} SQL functions for query: {query} (threshold: {similarity_threshold}, max: {max_results})")
                
                return sql_functions
            else:
                # No query provided, retrieve all functions with filtering
                # Build where clause with proper ChromaDB operators
                # ChromaDB requires at least 2 conditions for $and, so handle single condition separately
                where_conditions = [
                    {"type": {"$eq": "SQL_FUNCTION"}}
                ]
                
                # Optionally filter by data_source if provided
                if data_source:
                    where_conditions.append({"data_source": {"$eq": data_source}})
                
                # Optionally filter by project_id if provided
                if project_id and project_id != "default":
                    where_conditions.append({"project_id": {"$eq": project_id}})
                
                # Build where clause - use $and only if we have 2+ conditions
                if len(where_conditions) > 1:
                    where_clause = {"$and": where_conditions}
                elif len(where_conditions) == 1:
                    where_clause = where_conditions[0]
                else:
                    where_clause = None
                
                # Use get with proper where clause format
                results = await self._document_store.collection.get(
                    where=where_clause
                )

                if not results or not results.get("documents"):
                    logger.info(f"No SQL functions found for data_source: {data_source or 'all'}")
                    return []

                # Convert to SqlFunction objects
                sql_functions = []
                documents = results.get("documents", [])
                metadatas = results.get("metadatas", [])
                
                # Handle both formats: documents as list of dicts or separate metadatas list
                for i, doc in enumerate(documents):
                    # Stop if we've reached max_results
                    if len(sql_functions) >= max_results:
                        break
                    
                    # Try to get metadata from doc dict or from separate metadatas list
                    if isinstance(doc, dict):
                        metadata = doc.get("metadata", {})
                    else:
                        # If doc is just content string, get metadata from metadatas list
                        metadata = metadatas[i] if i < len(metadatas) else {}
                    
                    # Also try to parse content if it's JSON
                    if not metadata and isinstance(doc, dict):
                        content = doc.get("content", "")
                        if content:
                            try:
                                import json
                                content_dict = json.loads(content)
                                if isinstance(content_dict, dict):
                                    metadata = content_dict
                            except:
                                pass
                    
                    if metadata:
                        try:
                            sql_function = SqlFunction(definition=metadata)
                            sql_functions.append(sql_function)
                        except Exception as e:
                            logger.warning(f"Error creating SqlFunction from metadata: {e}")
                            continue
                
                # Cache the results
                self._cache[cache_key] = sql_functions
                logger.info(f"Retrieved {len(sql_functions)} SQL functions for data_source: {data_source or 'all'} (max: {max_results})")
                
                return sql_functions
            
        except Exception as e:
            logger.error(f"Error retrieving SQL functions: {str(e)}")
            raise


if __name__ == "__main__":
    # Example usage
    import chromadb
    from agents.app.settings import get_settings
    
    settings = get_settings()
    
    # Initialize document store
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    doc_store = DocumentChromaStore(
        persistent_client=persistent_client,
        collection_name="sql_functions"
    )
    
    # Initialize processor
    processor = SqlFunctions(
        document_store=doc_store,
        engine_timeout=30.0,
        ttl=60 * 60 * 24  # 24 hours
    )
    
    # Retrieve functions (no project_id needed)
    import asyncio
    functions = asyncio.run(processor.run(data_source="vulnerability_risk"))
    print(f"Retrieved functions: {functions}")
