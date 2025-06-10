import logging
from typing import Any, Dict, Optional

import aiohttp


from app.core.engine import Engine

logger = logging.getLogger("genieml-agents")


class SQLExecutor:
    """Executes SQL queries and returns results."""
    
    def __init__(
        self,
        engine: Engine,
        engine_timeout: Optional[float] = 30.0,
    ) -> None:
        """Initialize the SQL executor.
        
        Args:
            engine: The database engine instance
            engine_timeout: Timeout for SQL execution in seconds
        """
        self._engine = engine
        self._engine_timeout = engine_timeout

    
    async def run(
        self,
        sql: str,
        project_id: str | None = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Execute SQL query and return results.
        
        Args:
            sql: The SQL query to execute
            project_id: Optional project ID for context
            limit: Maximum number of rows to return
            
        Returns:
            Dictionary containing query results
            
        Raises:
            Exception: If query execution fails
        """
        logger.info("SQL Execution is running...")
        
        try:
            async with aiohttp.ClientSession() as session:
                _, data, _ = await self._engine.execute_sql(
                    sql,
                    session,
                    project_id=project_id,
                    dry_run=False,
                    limit=limit,
                    timeout=self._engine_timeout,
                )
                
                return {"results": data}
                
        except Exception as e:
            logger.error(f"Error executing SQL: {str(e)}")
            raise


if __name__ == "__main__":
    # Example usage
    from app.core.engine import Engine
    
    # Initialize engine and executor
    engine = Engine()  # Add appropriate initialization parameters
    executor = SQLExecutor(
        engine=engine,
        engine_timeout=30.0
    )
    
    # Example query
    sql = "SELECT * FROM table"
    
    # Execute query
    import asyncio
    result = asyncio.run(executor.run(sql))
    print(f"Query results: {result}")
