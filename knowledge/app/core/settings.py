"""
Settings for Knowledge App
Similar to genieml/agents/app/settings.py
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class VectorStoreType(str, Enum):
    """Supported vector store types"""
    CHROMA = "chroma"
    QDRANT = "qdrant"
    PINECONE = "pinecone"


class CacheType(str, Enum):
    """Supported cache types"""
    MEMORY = "memory"
    REDIS = "redis"


class DatabaseType(str, Enum):
    """Supported database types"""
    POSTGRES = "postgres"
    MYSQL = "mysql"


class Settings(BaseSettings):
    """Application settings with environment variable loading."""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # ============================================================================
    # Vector Store Settings
    # ============================================================================
    VECTOR_STORE_TYPE: VectorStoreType = VectorStoreType.CHROMA
    VECTOR_STORE_PATH: str = "../../data/vector_store"
    CHROMA_STORE_PATH: str = "../../data/chroma_db"
    CHROMA_USE_LOCAL: bool = True  # Using local ChromaDB
    CHROMA_HOST: Optional[str] = "localhost"  # Localhost for local ChromaDB
    CHROMA_PORT: int = 8888
    CHROMA_COLLECTION_NAME: str = "default"
    CHROMA_PERSIST_DIRECTORY: str = CHROMA_STORE_PATH
    
    # Qdrant Settings
    QDRANT_HOST: Optional[str] = None
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "default"
    
    # Pinecone Settings
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    PINECONE_INDEX_NAME: str = "default"
    
    # ============================================================================
    # Cache Settings
    # ============================================================================
    CACHE_TYPE: CacheType = CacheType.MEMORY
    CACHE_TTL: int = 120  # Time to live in seconds
    CACHE_MAXSIZE: int = 1_000_000
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    
    # ============================================================================
    # Database Settings
    # ============================================================================
    DATABASE_TYPE: DatabaseType = DatabaseType.POSTGRES
    
    # PostgreSQL Settings (copied from genieml/agents/app/settings.py)
    POSTGRES_HOST: str = "genaipostgresqlserver.postgres.database.azure.com"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "phenom_egen_ai"
    POSTGRES_USER: str = "phegenaiadmin"
    POSTGRES_PASSWORD: str = "vwm8$S4VVpn%2J_"
    POSTGRES_POOL_MIN_SIZE: int = 5
    POSTGRES_POOL_MAX_SIZE: int = 20
    POSTGRES_SSL_MODE: str = "require"  # Required for Azure PostgreSQL
    
    # MySQL Settings
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "knowledge_db"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_POOL_MIN_SIZE: int = 5
    MYSQL_POOL_MAX_SIZE: int = 20
    
    # ============================================================================
    # Embedding Settings
    # ============================================================================
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: str = "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"
    
    # ============================================================================
    # LLM Settings
    # ============================================================================
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    
    # ============================================================================
    # Environment
    # ============================================================================
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )
    
    def get_vector_store_config(self) -> Dict[str, Any]:
        """Get vector store configuration based on type"""
        config = {"type": self.VECTOR_STORE_TYPE}
        
        if self.VECTOR_STORE_TYPE == VectorStoreType.CHROMA:
            config.update({
                "use_local": self.CHROMA_USE_LOCAL,
                "host": self.CHROMA_HOST,
                "port": self.CHROMA_PORT,
                "collection_name": self.CHROMA_COLLECTION_NAME,
                "persist_directory": self.CHROMA_PERSIST_DIRECTORY
            })
        elif self.VECTOR_STORE_TYPE == VectorStoreType.QDRANT:
            config.update({
                "host": self.QDRANT_HOST or "localhost",
                "port": self.QDRANT_PORT,
                "collection_name": self.QDRANT_COLLECTION_NAME
            })
        elif self.VECTOR_STORE_TYPE == VectorStoreType.PINECONE:
            config.update({
                "api_key": self.PINECONE_API_KEY,
                "environment": self.PINECONE_ENVIRONMENT,
                "index_name": self.PINECONE_INDEX_NAME
            })
        
        return config
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration based on type"""
        config = {"type": self.CACHE_TYPE}
        
        if self.CACHE_TYPE == CacheType.REDIS:
            config.update({
                "host": self.REDIS_HOST,
                "port": self.REDIS_PORT,
                "db": self.REDIS_DB,
                "password": self.REDIS_PASSWORD,
                "ssl": self.REDIS_SSL
            })
        elif self.CACHE_TYPE == CacheType.MEMORY:
            config.update({
                "ttl": self.CACHE_TTL,
                "maxsize": self.CACHE_MAXSIZE
            })
        
        return config
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration based on type"""
        config = {"type": self.DATABASE_TYPE}
        
        if self.DATABASE_TYPE == DatabaseType.POSTGRES:
            config.update({
                "host": self.POSTGRES_HOST,
                "port": self.POSTGRES_PORT,
                "database": self.POSTGRES_DB,
                "user": self.POSTGRES_USER,
                "password": self.POSTGRES_PASSWORD,
                "pool_min_size": self.POSTGRES_POOL_MIN_SIZE,
                "pool_max_size": self.POSTGRES_POOL_MAX_SIZE,
                "ssl_mode": self.POSTGRES_SSL_MODE
            })
        elif self.DATABASE_TYPE == DatabaseType.MYSQL:
            config.update({
                "host": self.MYSQL_HOST,
                "port": self.MYSQL_PORT,
                "database": self.MYSQL_DB,
                "user": self.MYSQL_USER,
                "password": self.MYSQL_PASSWORD,
                "pool_min_size": self.MYSQL_POOL_MIN_SIZE,
                "pool_max_size": self.MYSQL_POOL_MAX_SIZE
            })
        
        return config


def set_os_environ(settings: Settings) -> None:
    """
    Set OS environment variables from settings.
    This ensures environment variables are consistent across the application
    and any subprocesses (including integration tests).
    
    Args:
        settings: Application settings instance
    """
    env_mappings = {
        # OpenAI API Key (critical for integration tests)
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        
        # PostgreSQL Settings
        "POSTGRES_HOST": settings.POSTGRES_HOST,
        "POSTGRES_PORT": str(settings.POSTGRES_PORT),
        "POSTGRES_DB": settings.POSTGRES_DB,
        "POSTGRES_USER": settings.POSTGRES_USER,
        "POSTGRES_PASSWORD": settings.POSTGRES_PASSWORD,
        
        # ChromaDB Settings
        "CHROMA_USE_LOCAL": str(settings.CHROMA_USE_LOCAL).lower(),
        "CHROMA_HOST": settings.CHROMA_HOST or "localhost",
        "CHROMA_PORT": str(settings.CHROMA_PORT),
        "CHROMA_COLLECTION_NAME": settings.CHROMA_COLLECTION_NAME,
        "CHROMA_STORE_PATH": settings.CHROMA_STORE_PATH,
        "CHROMA_PERSIST_DIRECTORY": settings.CHROMA_PERSIST_DIRECTORY,
        
        # Embedding Settings
        "EMBEDDING_PROVIDER": settings.EMBEDDING_PROVIDER,
        "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
        
        # LLM Settings
        "LLM_MODEL": settings.LLM_MODEL,
        "LLM_TEMPERATURE": str(settings.LLM_TEMPERATURE),
        
        # Python Settings
        "PYTHONPATH": str(settings.BASE_DIR),
        "PYTHONUNBUFFERED": "1",
        
        # Application Environment
        "APP_ENV": settings.ENV,
        "DEBUG": str(settings.DEBUG).lower(),
        
        # Logging
        "LOG_LEVEL": settings.LOG_LEVEL,
    }
    
    # Set environment variables
    for key, value in env_mappings.items():
        if value is not None:  # Only set if value exists
            os.environ[key] = str(value)
            logger.debug(f"Set environment variable: {key}")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance and set OS environment variables"""
    logger.debug("Creating new Settings instance")
    settings = Settings()
    
    # Set OS environment variables (including OPENAI_API_KEY for integration tests)
    set_os_environ(settings)
    
    logger.info(f"Settings loaded - VectorStore: {settings.VECTOR_STORE_TYPE}, "
                f"Cache: {settings.CACHE_TYPE}, Database: {settings.DATABASE_TYPE}")
    logger.info(f"OPENAI_API_KEY set in os.environ: {bool(os.environ.get('OPENAI_API_KEY'))}")
    return settings


def clear_settings_cache():
    """Clear the settings cache to force reload of settings"""
    get_settings.cache_clear()
    logger.info("Settings cache cleared")

