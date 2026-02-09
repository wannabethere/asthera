from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, Dict, Any, List, Union
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
import pandas as pd
from enum import Enum


class EngineType(str, Enum):
    """Supported engine types"""
    PANDAS = "pandas"
    POSTGRES = "postgres"
    SQLITE = "sqlite"


class VectorStoreType(str, Enum):
    """Supported vector store backends (Chroma or Qdrant)."""
    CHROMA = "chroma"
    QDRANT = "qdrant"

# Configure logger
logger = logging.getLogger(__name__)

class DataFrameConfig:
    """Configuration for DataFrame data sources"""
    def __init__(self, data_sources: Dict[str, Union[str, pd.DataFrame]] = None):
        self.data_sources = data_sources or {}
        self._loaded_dataframes = {}
        
    def load_dataframes(self) -> Dict[str, pd.DataFrame]:
        """Load all dataframes from configured sources"""
        for name, source in self.data_sources.items():
            if isinstance(source, pd.DataFrame):
                self._loaded_dataframes[name] = source
            elif isinstance(source, str):
                try:
                    # Try to load from file
                    if source.endswith('.csv'):
                        self._loaded_dataframes[name] = pd.read_csv(source)
                    elif source.endswith(('.xlsx', '.xls')):
                        self._loaded_dataframes[name] = pd.read_excel(source)
                    elif source.endswith('.parquet'):
                        self._loaded_dataframes[name] = pd.read_parquet(source)
                    else:
                        logger.warning(f"Unsupported file format for {source}")
                except Exception as e:
                    logger.error(f"Failed to load dataframe from {source}: {e}")
            else:
                logger.warning(f"Unsupported data source type for {name}")
                
        return self._loaded_dataframes

class Settings(BaseSettings):
    """Application settings with environment variable loading."""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # Engine Settings
    ENGINE_TYPE: str = EngineType.POSTGRES  # Default to postgres engine
    ENGINE_DATA_SOURCES: Dict[str, Any] = {}  # Default empty data sources
    ENGINE_CONNECTION_STRING: Optional[str] = None
    ENGINE_POSTGRES_CONFIG: Dict[str, Any] = {
        "host": "genaipostgresqlserver.postgres.database.azure.com",
        "port": 5432,
        "database": "phenom_egen_ai",
        "user": "phegenaiadmin",
        "password": "vwm8$S4VVpn%2J_",  # URL encoded version of FLc&dL@M9A5Q7wI;
        "sslmode": "require"  # Required for Azure PostgreSQL
    }
    
    # SQLite Settings
    SQLITE_DB_PATH: Optional[str] = None  # Path to SQLite database file
    SQLITE_USE_MEMORY: bool = False  # Whether to use in-memory SQLite database
    
    # API Keys and Security
    OPENAI_API_KEY: str = "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"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TITLE: str = "Data Science Logical Planner API"
    API_DESCRIPTION: str = "API for generating data science plans with real-time progress updates"
    API_VERSION: str = "1.0.0"
    CORS_ORIGINS: List[str] = ["*"]
    
    # OpenTelemetry Settings
    OPENTELEMETRY_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "crag-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "grpc"
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Model Configuration
    MODEL_NAME: str = "gpt-4o-mini"
    TEMPERATURE: float = 0.0
    
    # SQL Generation Model Settings
    SQL_GENERATION_TEMPERATURE: float = 0.0
    SQL_GENERATION_MAX_TOKENS: int = 1000
    SQL_GENERATION_TOP_P: float = 1.0
    SQL_GENERATION_FREQUENCY_PENALTY: float = 0.0
    SQL_GENERATION_PRESENCE_PENALTY: float = 0.0
    
    # RAG Settings
    MAX_DOCUMENTS: int = 4
    RELEVANCE_THRESHOLD: float = 0.7
    MAX_ATTEMPTS: int = 3
    
    # Environment
    ENV: str = "development"
    DEBUG: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    
    # Database Settings
    #POSTGRES_HOST: str = "localhost"
    #POSTGRES_PORT: int = 5432
    #POSTGRES_DB: str = "genimel"
    #POSTGRES_USER: str = "postgres"
    #POSTGRES_PASSWORD: str = "postgres"
    #POSTGRES_HOST: str = "unedadevpostgresql.postgres.database.azure.com"
    #POSTGRES_PORT: int = 5432
    #POSTGRES_USER: str = "pixentia"
    #POSTGRES_PASSWORD: str = "FLc%26dL%40M9A5Q7wI%3B"  # URL encoded version of FLc&dL@M9A5Q7wI;
    #POSTGRES_DB: str = "phenom_egen_ai"
    POSTGRES_HOST: str = "genaipostgresqlserver.postgres.database.azure.com"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "phenom_egen_ai"
    POSTGRES_USER: str = "phegenaiadmin"
    POSTGRES_PASSWORD: str = "vwm8$S4VVpn%2J_"
    
    # Vector Store Settings
    VECTOR_STORE_PATH: str = "../../data/vector_store"
    CHROMA_STORE_PATH: str = "../../data/chroma_db"
    
    # ChromaDB Settings
    CHROMA_USE_LOCAL: bool = False  # Default to HTTP client
    CHROMA_HOST: str = "100.26.125.159"#"ec2-107-21-151-224.compute-1.amazonaws.com"#"ec2-44-202-8-38.compute-1.amazonaws.com"  # Default EC2 host
    CHROMA_PORT: int = 8888  # Default EC2 port
    CHROMA_COLLECTION_NAME: str = "default"
    CHROMA_PERSIST_DIRECTORY: str = CHROMA_STORE_PATH
    
    # DataServices ChromaDB Settings (for document storage)
    DATASERVICES_CHROMA_PATH: str = "./chroma_db"  # Path used by DataServices document router
    DATASERVICES_CHROMA_COLLECTION: str = "documents"  # Collection name used by DataServices
    DATASERVICES_CHROMA_TFIDF_COLLECTION: str = "documents_tfidf"  # TF-IDF collection used by DataServices
    
    # Vector store backend (chroma | qdrant). When qdrant, retrieval uses Qdrant collections.
    VECTOR_STORE_TYPE: VectorStoreType = VectorStoreType.CHROMA
    # Qdrant (used when VECTOR_STORE_TYPE=qdrant or by ProjectReaderQdrant)
    QDRANT_HOST: Optional[str] = None
    QDRANT_PORT: int = 6333
    # Optional prefix for Qdrant collections populated by ProjectReaderQdrant (e.g. "core_")
    CORE_COLLECTION_PREFIX: Optional[str] = None

    # Embedding Settings
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Tavily search settings
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_SEARCH_DEPTH: str = "basic"  # basic, advanced
    TAVILY_MAX_RESULTS: int = 5
    
    # KPI Strategy Map Settings
    KPI_PATTERNS_FILE: str = "../config/kpistrategies.yaml"
    KPI_EXTRACTION_ENABLED: bool = True
    KPI_EXTRACTION_MIN_CONFIDENCE: float = 0.7
    KPI_MAX_DOCUMENTS: int = 5
    KPI_USE_GPT: bool = True
    KPI_GPT_MODEL: str = "gpt-4o-mini"
    KPI_GPT_TEMPERATURE: float = 0.2
    
    # Session Settings
    SESSION_TIMEOUT: int = 3600
    MAX_SESSION_SIZE: int = 1000
    
    def get_engine_config(self) -> Dict[str, Any]:
        """Get engine configuration based on settings"""
        config = {
            "engine_type": self.ENGINE_TYPE
        }
        
        if self.ENGINE_TYPE == EngineType.PANDAS:
            # Load dataframes from configured sources
            df_config = DataFrameConfig(self.ENGINE_DATA_SOURCES)
            config["data_sources"] = df_config.load_dataframes()
            
        elif self.ENGINE_TYPE == EngineType.POSTGRES:
            config["postgres_config"] = {
                "host": self.POSTGRES_HOST,
                "port": self.POSTGRES_PORT,
                "database": self.POSTGRES_DB,
                "username": self.POSTGRES_USER,
                "password": self.POSTGRES_PASSWORD
            }
            
        elif self.ENGINE_TYPE == EngineType.SQLITE:
            if self.SQLITE_USE_MEMORY:
                config["connection_string"] = ":memory:"
            else:
                config["connection_string"] = self.SQLITE_DB_PATH or ":memory:"
                
        return config

    def get_vector_store_config(self) -> Dict[str, Any]:
        """Get vector store configuration for VectorStoreClient (Chroma or Qdrant)."""
        config: Dict[str, Any] = {"type": self.VECTOR_STORE_TYPE}
        if self.VECTOR_STORE_TYPE == VectorStoreType.CHROMA:
            config.update({
                "use_local": self.CHROMA_USE_LOCAL,
                "host": self.CHROMA_HOST or "localhost",
                "port": self.CHROMA_PORT,
                "persist_directory": getattr(self, "CHROMA_PERSIST_DIRECTORY", None) or self.CHROMA_STORE_PATH,
            })
        elif self.VECTOR_STORE_TYPE == VectorStoreType.QDRANT:
            config.update({
                "host": self.QDRANT_HOST or "localhost",
                "port": self.QDRANT_PORT,
            })
        return config

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

def find_env_file() -> Optional[Path]:
    """
    Find the .env file in various possible locations.
    
    Returns:
        Optional[Path]: Path to the .env file if found, None otherwise
    """
    # Check current directory
    if os.path.exists(".env"):
        return Path(".env")
    
    # Check parent directory
    parent_env = Path("..") / ".env"
    if parent_env.exists():
        return parent_env
    
    # Check application root (3 levels up from this file)
    app_root = Path(__file__).resolve().parent.parent.parent
    app_env = app_root / ".env"
    if app_env.exists():
        return app_env
    
    # Check home directory
    home_env = Path.home() / ".env"
    if home_env.exists():
        return home_env
    
    return None

def debug_env_variables():
    """Print environment variables for debugging purposes."""
    logger.info("--- Environment Variables Debug ---")
    
    # List of variables to check
    critical_vars = [
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", 
        "POSTGRES_USER", "POSTGRES_PASSWORD", "OPENAI_API_KEY"
    ]
    
    for var in critical_vars:
        # Get from environment
        env_value = os.environ.get(var)
        # Log safely (mask passwords and keys)
        if var in ["POSTGRES_PASSWORD", "OPENAI_API_KEY"]:
            if env_value:
                masked = env_value[:3] + "*" * (len(env_value) - 6) + env_value[-3:]
                logger.info(f"{var}: {masked} (masked)")
            else:
                logger.warning(f"{var}: NOT SET")
        else:
            logger.info(f"{var}: {env_value}")
    
    logger.info("--- End Environment Debug ---")

def init_environment(env_file: Optional[str] = None) -> Settings:
    """
    Initialize environment variables from .env file with improved error handling.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        Settings: Initialized settings instance
    """
    # Try to find .env file if not specified
    if env_file is None:
        env_path = find_env_file()
        if env_path:
            env_file = str(env_path)
            logger.info(f"Found .env file at: {env_file}")
        else:
            logger.warning("No .env file found in any standard location")
    
    # Load .env file if it exists
    if env_file and os.path.exists(env_file):
        logger.info(f"Loading environment from: {env_file}")
        load_dotenv(env_file, override=True)
        logger.info("Environment file loaded successfully")
    else:
        logger.warning(f"Environment file not found: {env_file}")
    
    # Debug environment variables
    debug_env_variables()
    
    # Get settings instance
    settings = get_settings()
    
    # Validate required environment variables
    required_vars = [
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", 
        "POSTGRES_USER", "POSTGRES_PASSWORD", "OPENAI_API_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not getattr(settings, var, None)]
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise EnvironmentError(error_msg)
    
    # Set OS environment variables from settings
    set_os_environ(settings)
    
    # Initialize models
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    global llm, embeddings_model
    
    # Initialize OpenAI model
    try:
        llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=settings.TEMPERATURE
        )
        
        # Initialize embeddings
        embeddings_model = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY
        )
    except Exception as e:
        logger.error(f"Failed to initialize models: {str(e)}")
        raise
    
    logger.info("Settings and models initialized successfully")
    return settings

def set_os_environ(settings: Settings) -> None:
    """
    Set OS environment variables from settings.
    This ensures environment variables are consistent across the application
    and any subprocesses.
    
    Args:
        settings: Application settings instance
    """
    env_mappings = {
        # OpenAI
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        
        # OpenTelemetry
        "OTEL_SERVICE_NAME": settings.OTEL_SERVICE_NAME,
        "OTEL_EXPORTER_OTLP_ENDPOINT": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        "OTEL_EXPORTER_OTLP_PROTOCOL": settings.OTEL_EXPORTER_OTLP_PROTOCOL,
        "OTEL_TRACES_SAMPLER": "always_on",
        "OTEL_TRACES_SAMPLER_ARG": "1.0",
        
        # Redis
        "REDIS_HOST": settings.REDIS_HOST,
        "REDIS_PORT": str(settings.REDIS_PORT),
        "REDIS_DB": str(settings.REDIS_DB),
        
        # Postgres Settings
        "POSTGRES_HOST": settings.POSTGRES_HOST,
        "POSTGRES_PORT": str(settings.POSTGRES_PORT),
        "POSTGRES_DB": settings.POSTGRES_DB,
        "POSTGRES_USER": settings.POSTGRES_USER,
        "POSTGRES_PASSWORD": settings.POSTGRES_PASSWORD,

        # ChromaDB Settings
        "CHROMA_USE_LOCAL": str(settings.CHROMA_USE_LOCAL).lower(),
        "CHROMA_HOST": settings.CHROMA_HOST,
        "CHROMA_PORT": str(settings.CHROMA_PORT),
        "CHROMA_COLLECTION_NAME": settings.CHROMA_COLLECTION_NAME,
        "CHROMA_PERSIST_DIRECTORY": settings.CHROMA_PERSIST_DIRECTORY,
        
        # Python Settings
        "PYTHONPATH": str(settings.BASE_DIR),
        "PYTHONUNBUFFERED": "1",
        
        # Application Environment
        "APP_ENV": settings.ENV,
        "DEBUG": str(settings.DEBUG).lower(),
        
        # Model Settings
        "MODEL_NAME": settings.MODEL_NAME,
        "MODEL_TEMPERATURE": str(settings.TEMPERATURE),
        
        # Logging
        "LOG_LEVEL": settings.LOG_LEVEL,
        
        # RAG Settings
        "MAX_DOCUMENTS": str(settings.MAX_DOCUMENTS),
        "RELEVANCE_THRESHOLD": str(settings.RELEVANCE_THRESHOLD),
        "MAX_ATTEMPTS": str(settings.MAX_ATTEMPTS),
    }
    
    # Set environment variables
    for key, value in env_mappings.items():
        if value is not None:  # Only set if value exists
            os.environ[key] = str(value)
            logger.debug(f"Set environment variable: {key}")

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    The lru_cache decorator ensures we only create the settings object once.
    
    Returns:
        Settings: Application settings
    """
    logger.debug("Creating new Settings instance")
    settings = Settings()
    logger.info(f"Settings loaded - CHROMA_USE_LOCAL: {settings.CHROMA_USE_LOCAL}, CHROMA_HOST: {settings.CHROMA_HOST}, CHROMA_PORT: {settings.CHROMA_PORT}")
    return settings

def clear_settings_cache():
    """Clear the settings cache to force reload of settings."""
    get_settings.cache_clear()
    logger.info("Settings cache cleared")

def load_environment_variables(env_file=None):
    """
    Load environment variables from .env file with improved error handling and logging.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        bool: True if environment loaded successfully, False otherwise
    """
    # Try multiple possible locations for .env file
    if env_file is None:
        # Check current directory
        if os.path.exists(".env"):
            env_file = ".env"
        # Check parent directory
        elif os.path.exists(os.path.join("..", ".env")):
            env_file = os.path.join("..", ".env")
        # Check application root directory
        else:
            app_root = Path(__file__).resolve().parent.parent.parent
            env_file = app_root / ".env"
    
    # Convert to Path object if it's a string
    if isinstance(env_file, str):
        env_file = Path(env_file)
    
    # Check if the .env file exists
    if not env_file.exists():
        logger.warning(f"No .env file found at {env_file}")
        return False
    
    # Load the .env file
    logger.info(f"Loading environment variables from: {env_file}")
    load_dotenv(dotenv_path=env_file, override=True)
    
    # Verify some critical variables were loaded
    critical_vars = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing_vars = [var for var in critical_vars if os.getenv(var) is None]
    
    if missing_vars:
        logger.error(f"Missing critical environment variables: {', '.join(missing_vars)}")
        return False
    
    # Log successful loading
    logger.info("Environment variables loaded successfully")
    return True