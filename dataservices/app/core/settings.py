from dataclasses import dataclass
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
    """Vector database backend for document / RAG stores."""

    CHROMA = "chroma"
    QDRANT = "qdrant"

# Configure logger
logger = logging.getLogger(__name__)


def _dataservices_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _complianceskill_env_path() -> Path:
    """Sibling repo path: genieml/complianceskill/.env (same layout as complianceskill Settings)."""
    return _dataservices_root().parent / "complianceskill" / ".env"


def _dataservices_env_file_paths() -> tuple[str, ...]:
    """Pydantic env_file order: shared complianceskill first, then local dataservices (later wins on duplicate keys)."""
    paths: List[Path] = []
    shared = _complianceskill_env_path()
    if shared.is_file():
        paths.append(shared)
    local = _dataservices_root() / ".env"
    if local.is_file():
        paths.append(local)
    if not paths:
        return ()
    return tuple(str(p) for p in paths)


def load_dotenv_merged(*, final_override: bool = True) -> None:
    """Load complianceskill/.env then dataservices/.env so local keys override shared dev config."""
    shared = _complianceskill_env_path()
    local = _dataservices_root() / ".env"
    if shared.is_file():
        load_dotenv(shared, override=False)
        logger.info("Loaded shared env file: %s", shared)
    if local.is_file():
        load_dotenv(local, override=final_override)
        logger.info("Loaded dataservices env file: %s", local)

@dataclass
class ServiceConfig:
    """Configuration for the LLM Definition Service"""
    
    SQLALCHEMY_DATABASE_URI: Optional[str] = "postgresql+asyncpg://phegenaiadmin:vwm8%24S4VVpn%252J_@genaipostgresqlserver.postgres.database.azure.com:5432/phenom_gen_ai"
    SQLALCHEMY_DATA_SERVICES_DATABASE_URI: Optional[str] = "postgresql+asyncpg://phegenaiadmin:vwm8%24S4VVpn%252J_@genaipostgresqlserver.postgres.database.azure.com:5432/phenom_genai_dataservices"
    # Database configuration
    #database_url: str = "postgresql+asyncpg://pixentia:FLc%26dL%40M9A5Q7wI%3B@unedadevpostgresql.postgres.database.azure.com:5432/phenom_genai_dataservices"
    #genai_database_url: str = "postgresql+asyncpg://pixentia:FLc%26dL%40M9A5Q7wI%3B@unedadevpostgresql.postgres.database.azure.com:5432/phenom_gen_ai"
    database_url: str = SQLALCHEMY_DATA_SERVICES_DATABASE_URI
    genai_database_url: str = SQLALCHEMY_DATABASE_URI

    # LLM configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = "gpt-4"
    
    # MCP Server configuration
    mcp_server_url: str = "http://localhost:8000"
    
    # Service configuration
    log_level: str = "INFO"
    enable_cors: bool = True
    max_concurrent_requests: int = 10
    
    # Validation settings
    min_confidence_score: float = 0.7
    enable_sql_validation: bool = True
    
    # Generation settings
    llm_temperature: float = 0.1
    max_tokens: int = 2000
    
    @classmethod
    def from_env(cls) -> 'ServiceConfig':
        """Create configuration from environment variables"""
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            genai_database_url=os.getenv("GENAI_DATABASE_URL", cls.genai_database_url),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", cls.openai_model),
            mcp_server_url=os.getenv("MCP_SERVER_URL", cls.mcp_server_url),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            enable_cors=os.getenv("ENABLE_CORS", "true").lower() == "true",
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", cls.max_concurrent_requests)),
            min_confidence_score=float(os.getenv("MIN_CONFIDENCE_SCORE", cls.min_confidence_score)),
            enable_sql_validation=os.getenv("ENABLE_SQL_VALIDATION", "true").lower() == "true",
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", cls.llm_temperature)),
            max_tokens=int(os.getenv("MAX_TOKENS", cls.max_tokens))
        )
    
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
    POSTGRES_DB: str = "phenom_gen_ai"
    POSTGRES_USER: str = "phegenaiadmin"
    POSTGRES_PASSWORD: str = "vwm8$S4VVpn%2J_"
    
    # Vector Store Settings (.env — same keys as complianceskill; see complianceskill/.env)
    VECTOR_STORE_TYPE: VectorStoreType = VectorStoreType.QDRANT
    VECTOR_STORE_PATH: str = "../../data/vector_store"
    CHROMA_STORE_PATH: str = "../../data/chroma_db"
    CHROMA_USE_LOCAL: bool = True
    CHROMA_HOST: Optional[str] = None
    CHROMA_PORT: int = 8888
    CHROMA_COLLECTION_NAME: str = "default"
    CHROMA_PERSIST_DIRECTORY: Optional[str] = None

    # Qdrant (used when VECTOR_STORE_TYPE=qdrant)
    # Typical self-hosted: QDRANT_URL and/or QDRANT_HOST + QDRANT_PORT; API key only for Qdrant Cloud.
    QDRANT_HOST: Optional[str] = None
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "default"
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    
    # Embedding Settings
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
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
        """Connection details for the active vector store (Chroma or Qdrant)."""
        config: Dict[str, Any] = {"type": self.VECTOR_STORE_TYPE}
        if self.VECTOR_STORE_TYPE == VectorStoreType.CHROMA:
            config.update(
                {
                    "use_local": self.CHROMA_USE_LOCAL,
                    "host": self.CHROMA_HOST or "localhost",
                    "port": self.CHROMA_PORT,
                    "collection_name": self.CHROMA_COLLECTION_NAME,
                    "persist_directory": self.CHROMA_PERSIST_DIRECTORY or self.CHROMA_STORE_PATH,
                }
            )
        elif self.VECTOR_STORE_TYPE == VectorStoreType.QDRANT:
            config.update(
                {
                    "host": self.QDRANT_HOST or "localhost",
                    "port": self.QDRANT_PORT,
                    "collection_name": self.QDRANT_COLLECTION_NAME,
                    "url": self.QDRANT_URL,
                    "api_key": self.QDRANT_API_KEY,
                }
            )
        return config

    model_config = SettingsConfigDict(
        env_file=_dataservices_env_file_paths(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
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
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "OPENAI_API_KEY",
        "VECTOR_STORE_TYPE",
        "QDRANT_HOST",
        "QDRANT_PORT",
        "QDRANT_URL",
    ]
    
    for var in critical_vars:
        # Get from environment
        env_value = os.environ.get(var)
        # Log safely (mask passwords and keys)
        if var in ["POSTGRES_PASSWORD", "OPENAI_API_KEY", "QDRANT_URL", "QDRANT_API_KEY"]:
            if env_value:
                masked = env_value[:3] + "*" * (len(env_value) - 6) + env_value[-3:]
                logger.info(f"{var}: {masked} (masked)")
            else:
                logger.warning(f"{var}: NOT SET")
        else:
            logger.info(f"{var}: {env_value}")
    
    logger.info("--- End Environment Debug ---")

def init_environment(env_file: Optional[str] = None) -> tuple[Settings, ServiceConfig]:
    """
    Initialize environment variables from .env file with improved error handling.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        tuple[Settings, ServiceConfig]: Initialized settings and service config instances
    """
    # Load env: explicit path, or merged complianceskill + dataservices .env (local overrides shared)
    if env_file is not None and os.path.exists(env_file):
        logger.info("Loading environment from explicit path: %s", env_file)
        load_dotenv(env_file, override=True)
    else:
        if env_file is not None:
            logger.warning("Explicit env file not found: %s; loading merged default .env files", env_file)
        load_dotenv_merged(final_override=True)
    
    # Debug environment variables
    debug_env_variables()
    
    # Get settings instance
    
    
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from app.core.session_manager import SessionManager
    global llm, embeddings_model, service_config, session_manager,settings
    settings = get_settings()
    
    # Initialize ServiceConfig from environment
    service_config = ServiceConfig.from_env()
    logger.info("ServiceConfig initialized from environment variables")
    
    # Initialize SessionManager with ServiceConfig
    session_manager = SessionManager(service_config)
    logger.info("SessionManager initialized with ServiceConfig")
    
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
    
    logger.info("Settings, ServiceConfig and models initialized successfully")
    return settings, service_config

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
        "CHROMA_HOST": settings.CHROMA_HOST or "",
        "CHROMA_PORT": str(settings.CHROMA_PORT),
        "CHROMA_COLLECTION_NAME": settings.CHROMA_COLLECTION_NAME,
        "CHROMA_STORE_PATH": settings.CHROMA_STORE_PATH,
        "CHROMA_PERSIST_DIRECTORY": settings.CHROMA_PERSIST_DIRECTORY or "",
        "VECTOR_STORE_PATH": settings.VECTOR_STORE_PATH,
        "VECTOR_STORE_TYPE": settings.VECTOR_STORE_TYPE.value,
        "QDRANT_HOST": settings.QDRANT_HOST or "localhost",
        "QDRANT_PORT": str(settings.QDRANT_PORT),
        "QDRANT_URL": settings.QDRANT_URL or "",
        "QDRANT_API_KEY": settings.QDRANT_API_KEY or "",
        "QDRANT_COLLECTION_NAME": settings.QDRANT_COLLECTION_NAME,
        
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
    return Settings()


def log_active_vector_store_backend() -> None:
    """Log VECTOR_STORE_TYPE and non-sensitive connection hints once at process startup."""
    settings = get_settings()
    cfg = settings.get_vector_store_config()
    if settings.VECTOR_STORE_TYPE == VectorStoreType.QDRANT:
        url_set = bool(cfg.get("url"))
        api_key_set = bool(settings.QDRANT_API_KEY)
        logger.info(
            "Vector store backend: Qdrant (QDRANT_URL=%s; QDRANT_HOST=%s, QDRANT_PORT=%s; %s)",
            "set" if url_set else "unset",
            cfg.get("host"),
            cfg.get("port"),
            "QDRANT_API_KEY set" if api_key_set else "no Qdrant API key (URL/host+port only)",
        )
    elif settings.VECTOR_STORE_TYPE == VectorStoreType.CHROMA:
        if cfg.get("use_local"):
            logger.info(
                "Vector store backend: Chroma (local persist_directory=%s)",
                cfg.get("persist_directory"),
            )
        else:
            logger.info(
                "Vector store backend: Chroma (HTTP mode host=%s, port=%s)",
                cfg.get("host"),
                cfg.get("port"),
            )
    else:
        logger.info("Vector store backend: %s", settings.VECTOR_STORE_TYPE)

def load_environment_variables(env_file=None):
    """
    Load environment variables from .env file with improved error handling and logging.
    
    Args:
        env_file: Optional path to .env file
        
    Returns:
        bool: True if environment loaded successfully, False otherwise
    """
    if env_file is not None:
        env_path = Path(env_file)
        if not env_path.exists():
            logger.warning("No .env file found at %s", env_file)
            return False
        logger.info("Loading environment variables from: %s", env_file)
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv_merged(final_override=True)
        if not _complianceskill_env_path().is_file() and not (_dataservices_root() / ".env").is_file():
            logger.warning("No complianceskill or dataservices .env file found")
            return False
    
    # Verify some critical variables were loaded
    critical_vars = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing_vars = [var for var in critical_vars if os.getenv(var) is None]
    
    if missing_vars:
        logger.error(f"Missing critical environment variables: {', '.join(missing_vars)}")
        return False
    
    # Log successful loading
    logger.info("Environment variables loaded successfully")
    return True

