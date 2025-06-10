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

   
    async def _retrieve_metadata(self, project_id: str) -> dict[str, Any]:
        """Retrieve project metadata.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dictionary containing project metadata
        """
        where = {}
        if project_id:
            where["project_id"] = project_id

        results = await self._document_store.collection.get(
            where=where,
            limit=1
        )
        
        if results and results.get("documents"):
            return results["documents"][0].get("metadata", {})
        return {}

   
    async def run(
        self,
        project_id: Optional[str] = None,
    ) -> List[SqlFunction]:
        """Retrieve SQL functions for a project.
        
        Args:
            project_id: Optional project identifier
            
        Returns:
            List of SQL functions
            
        Raises:
            Exception: If function retrieval fails
        """
        logger.info(
            f"Project ID: {project_id} SQL Functions Retrieval is running..."
        )

        try:
            metadata = await self._retrieve_metadata(project_id or "")
            data_source = metadata.get("data_source", "local_file")

            if data_source in self._cache:
                logger.info(f"Hit cache of SQL Functions for {data_source}")
                return self._cache[data_source]

            # Get functions from document store
            where = {
                "type": "SQL_FUNCTION",
                "data_source": data_source
            }
            if project_id:
                where["project_id"] = project_id

            results = await self._document_store.collection.get(
                where=where
            )

            if not results or not results.get("documents"):
                return []

            # Convert to SqlFunction objects
            sql_functions = [
                SqlFunction(definition=doc["metadata"])
                for doc in results["documents"]
            ]
            
            # Cache the results
            self._cache[data_source] = sql_functions
            
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
    
    # Retrieve functions
    import asyncio
    functions = asyncio.run(processor.run(project_id="test"))
    print(f"Retrieved functions: {functions}")
