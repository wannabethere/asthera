"""
Database Abstraction
Supports PostgreSQL and MySQL backends
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import asyncpg

from app.core.settings import get_settings, DatabaseType

logger = logging.getLogger(__name__)


class DatabaseClient(ABC):
    """Abstract base class for database clients"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Create connection pool"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection pool"""
        pass
    
    @abstractmethod
    async def execute(self, query: str, *args) -> str:
        """Execute a query (INSERT, UPDATE, DELETE)"""
        pass
    
    @abstractmethod
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        pass
    
    @abstractmethod
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        pass
    
    @abstractmethod
    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value"""
        pass
    
    @abstractmethod
    def acquire(self):
        """Get a connection from the pool (context manager)"""
        pass


class PostgresDatabaseClient(DatabaseClient):
    """PostgreSQL implementation of database client"""
    
    def __init__(self, config: dict):
        """Initialize PostgreSQL client"""
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Create connection pool"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
                min_size=self.config.get("pool_min_size", 5),
                max_size=self.config.get("pool_max_size", 20),
                ssl=self.config.get("ssl_mode") == "require"
            )
            logger.info("PostgreSQL connection pool created")
    
    async def disconnect(self) -> None:
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query (INSERT, UPDATE, DELETE)"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            result = await conn.execute(query, *args)
            return result
    
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    def acquire(self):
        """Get a connection from the pool (context manager)"""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool.acquire()
    
    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool (for backward compatibility)"""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool


class MySQLDatabaseClient(DatabaseClient):
    """MySQL implementation of database client (placeholder)"""
    
    def __init__(self, config: dict):
        """Initialize MySQL client"""
        self.config = config
        # TODO: Implement MySQL client using aiomysql or similar
        raise NotImplementedError("MySQL client not yet implemented")
    
    async def connect(self) -> None:
        raise NotImplementedError
    
    async def disconnect(self) -> None:
        raise NotImplementedError
    
    async def execute(self, query: str, *args) -> str:
        raise NotImplementedError
    
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        raise NotImplementedError
    
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
    
    async def fetchval(self, query: str, *args) -> Any:
        raise NotImplementedError
    
    def acquire(self):
        raise NotImplementedError


def get_database_client(config: Optional[dict] = None) -> DatabaseClient:
    """
    Factory function to get a database client based on settings
    
    Args:
        config: Optional configuration override
        
    Returns:
        DatabaseClient instance
    """
    settings = get_settings()
    config = config or settings.get_database_config()
    
    database_type = config.get("type", DatabaseType.POSTGRES)
    
    if database_type == DatabaseType.POSTGRES:
        return PostgresDatabaseClient(config)
    elif database_type == DatabaseType.MYSQL:
        return MySQLDatabaseClient(config)
    else:
        raise ValueError(f"Unsupported database type: {database_type}")

