"""
Engine Provider for Knowledge App
Similar to genieml/agents/app/core/engine_provider.py
Provides database engines for query execution
"""
from typing import Dict, Any, Optional
from enum import Enum
import logging
import asyncpg

from app.core.settings import get_settings, DatabaseType

logger = logging.getLogger(__name__)


class EngineType(str, Enum):
    """Types of database engines"""
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLITE = "sqlite"


class DatabaseEngine:
    """Base database engine for query execution"""
    
    def __init__(
        self,
        engine_type: EngineType,
        pool: Optional[asyncpg.Pool] = None,
        connection_string: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize database engine.
        
        Args:
            engine_type: Type of engine
            pool: Optional asyncpg connection pool
            connection_string: Optional connection string
            **kwargs: Additional engine-specific arguments
        """
        self.engine_type = engine_type
        self.pool = pool
        self.connection_string = connection_string
        self.config = kwargs
    
    async def execute_query(self, query: str, *args) -> Any:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Query results
        """
        if self.pool is None:
            raise ValueError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def execute_query_row(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single row.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Single row as dictionary or None
        """
        if self.pool is None:
            raise ValueError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def execute_query_value(self, query: str, *args) -> Any:
        """
        Execute a query and return a single value.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Single value or None
        """
        if self.pool is None:
            raise ValueError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def execute(self, query: str, *args) -> str:
        """
        Execute a query (INSERT, UPDATE, DELETE) and return result.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Execution result
        """
        if self.pool is None:
            raise ValueError("Database pool not initialized")
        
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


class EngineProvider:
    """Provider for different types of database engines"""
    
    @staticmethod
    async def get_engine(
        engine_type: Optional[str] = None,
        pool: Optional[asyncpg.Pool] = None,
        connection_string: Optional[str] = None,
        postgres_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> DatabaseEngine:
        """
        Get an engine instance based on the specified type and configuration.
        
        Args:
            engine_type: Type of engine to create (defaults to settings)
            pool: Optional asyncpg connection pool
            connection_string: Connection string for database engines
            postgres_config: PostgreSQL specific configuration
            **kwargs: Additional engine-specific arguments
            
        Returns:
            DatabaseEngine: Configured engine instance
        """
        settings = get_settings()
        engine_type = engine_type or settings.DATABASE_TYPE.value or EngineType.POSTGRES
        
        try:
            if engine_type == EngineType.POSTGRES:
                # If pool is provided, use it directly
                if pool is not None:
                    return DatabaseEngine(
                        engine_type=EngineType.POSTGRES,
                        pool=pool,
                        **kwargs
                    )
                
                # Otherwise, create pool from config
                if postgres_config is None:
                    postgres_config = {
                        "host": settings.POSTGRES_HOST,
                        "port": settings.POSTGRES_PORT,
                        "database": settings.POSTGRES_DB,
                        "user": settings.POSTGRES_USER,
                        "password": settings.POSTGRES_PASSWORD,
                        "min_size": settings.POSTGRES_POOL_MIN_SIZE,
                        "max_size": settings.POSTGRES_POOL_MAX_SIZE,
                        "ssl": settings.POSTGRES_SSL_MODE == "require"
                    }
                
                # Create pool
                pool = await asyncpg.create_pool(
                    host=postgres_config["host"],
                    port=postgres_config["port"],
                    database=postgres_config["database"],
                    user=postgres_config["user"],
                    password=postgres_config["password"],
                    min_size=postgres_config.get("min_size", 5),
                    max_size=postgres_config.get("max_size", 20),
                    ssl=postgres_config.get("ssl", False)
                )
                
                return DatabaseEngine(
                    engine_type=EngineType.POSTGRES,
                    pool=pool,
                    **kwargs
                )
            elif engine_type == EngineType.MYSQL:
                # MySQL support would require a different async library (aiomysql)
                raise NotImplementedError("MySQL engine not yet implemented. Use PostgreSQL.")
            elif engine_type == EngineType.SQLITE:
                # SQLite support would require aiosqlite
                raise NotImplementedError("SQLite engine not yet implemented. Use PostgreSQL.")
            else:
                raise ValueError(f"Unsupported engine type: {engine_type}")
                
        except Exception as e:
            logger.error(f"Error creating engine of type {engine_type}: {str(e)}")
            raise


# Example usage:
async def example_engine_usage():
    """Example of how to use the engine provider"""
    # Get engine with default settings (PostgreSQL)
    default_engine = await EngineProvider.get_engine()
    
    # Execute a query
    results = await default_engine.execute_query("SELECT * FROM controls LIMIT 10")
    
    # Get engine with custom PostgreSQL configuration
    custom_postgres_engine = await EngineProvider.get_engine(
        engine_type=EngineType.POSTGRES,
        postgres_config={
            "host": "custom-host",
            "port": 5432,
            "database": "custom-db",
            "user": "custom-user",
            "password": "custom-password"
        }
    )
    
    # Get engine with existing pool
    import asyncpg
    pool = await asyncpg.create_pool("postgresql://user:pass@localhost/db")
    engine_with_pool = await EngineProvider.get_engine(
        engine_type=EngineType.POSTGRES,
        pool=pool
    )

