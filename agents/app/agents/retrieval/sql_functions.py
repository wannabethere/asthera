import logging
from typing import Any, Dict, List, Optional

import aiohttp
from cachetools import TTLCache


from app.storage.documents import DocumentChromaStore

logger = logging.getLogger("genieml-agents")


class SqlFunction:
    """Represents a SQL function with its parameters and return type."""
    
    _expr: str = None

    def __init__(self, definition: dict):
        """Initialize a SQL function from its definition.
        
        Args:
            definition: Dictionary containing function definition
        """
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
        data_source: Optional[str] = None,
    ) -> List[SqlFunction]:
        """Retrieve SQL functions globally (not tied to a project).
        
        Args:
            data_source: Optional data source identifier to filter functions.
                        If None, retrieves all SQL functions.
            
        Returns:
            List of SQL functions
            
        Raises:
            Exception: If function retrieval fails
        """
        logger.info(
            f"SQL Functions Retrieval is running... (data_source: {data_source or 'all'})"
        )

        try:
            # Use cache key based on data_source
            cache_key = data_source or "all"
            
            if cache_key in self._cache:
                logger.info(f"Hit cache of SQL Functions for {cache_key}")
                return self._cache[cache_key]

            # Get functions from document store (no project_id filter)
            where = {
                "type": "SQL_FUNCTION"
            }
            
            # Optionally filter by data_source if provided
            if data_source:
                where["data_source"] = data_source

            results = await self._document_store.collection.get(
                where=where
            )

            if not results or not results.get("documents"):
                logger.info(f"No SQL functions found for data_source: {cache_key}")
                return []

            # Convert to SqlFunction objects
            sql_functions = [
                SqlFunction(definition=doc["metadata"])
                for doc in results["documents"]
            ]
            
            # Cache the results
            self._cache[cache_key] = sql_functions
            logger.info(f"Retrieved {len(sql_functions)} SQL functions for data_source: {cache_key}")
            
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
