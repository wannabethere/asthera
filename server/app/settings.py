from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, Dict, Any, List
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys

# Configure logger
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings with environment variable loading."""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # API Keys and Security
    OPENAI_API_KEY: Optional[str] = "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"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TITLE: str = "Data Science Logical Planner API"
    API_DESCRIPTION: str = "API for generating data science plans with real-time progress updates"
    API_VERSION: str = "1.0.0"
    CORS_ORIGINS: List[str] = ["*"]
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GenieML"
    
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
    #POSTGRES_HOST: str = "unedadevpostgresql.postgres.database.azure.com"
    #POSTGRES_PORT: int = 5432
    #POSTGRES_DB: str = "phenom_gen_ai"
    #POSTGRES_USER: str = "pixentia"
    #POSTGRES_PASSWORD: str = "FLc&dL@M9A5Q7wI;"
    #SQLALCHEMY_DATABASE_URI: Optional[str] = "postgresql://pixentia:FLc%26dL%40M9A5Q7wI%3B@unedadevpostgresql.postgres.database.azure.com:5432/phenom_gen_ai"
    POSTGRES_HOST: str = "genaipostgresqlserver.postgres.database.azure.com"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "phenom_gen_ai"
    POSTGRES_USER: str = "phegenaiadmin"
    POSTGRES_PASSWORD: str = "vwm8$S4VVpn%2J_"
    SQLALCHEMY_DATABASE_URI: Optional[str] = "postgresql://phegenaiadmin:vwm8%24S4VVpn%252J_@genaipostgresqlserver.postgres.database.azure.com:5432/phenom_gen_ai"
    ENABLE_DB_INIT: bool = os.getenv("ENABLE_DB_INIT", "False").lower() == "true"
    
    # Vector Store Settings
    VECTOR_STORE_PATH: str = "/data/vector_store"
    CHROMA_STORE_PATH: str = "/data/chroma_db"
    # ChromaDB Settings
    CHROMA_USE_LOCAL: bool = True
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "default"
    CHROMA_PERSIST_DIRECTORY: str = "chroma_db"
    
    # Okta Settings
    OKTA_ISSUER: Optional[str] = None
    OKTA_CLIENT_ID: Optional[str] = None
    
    # Embedding Settings
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    # KPI Strategy Map Settings
    KPI_PATTERNS_FILE: str = "../config/kpistrategies.yaml"  # Default patterns file
    KPI_EXTRACTION_ENABLED: bool = True
    KPI_EXTRACTION_MIN_CONFIDENCE: float = 0.7
    KPI_MAX_DOCUMENTS: int = 5
    KPI_USE_GPT: bool = True
    KPI_GPT_MODEL: str = "gpt-4o-mini"  # Default to the same model as the application
    KPI_GPT_TEMPERATURE: float = 0.2
    
    # Session Settings
    SESSION_TIMEOUT: int = 3600  # 1 hour in seconds
    MAX_SESSION_SIZE: int = 1000  # Maximum number of messages per session
    
    # Authentication Configuration
    USE_OKTA: bool = False
    SECRET_KEY: str = "your-secret-key-here"  # Change this in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
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

def get_postgres_url(settings: Settings) -> str:
    """
    Construct PostgreSQL database URL from settings.
    
    Args:
        settings: Application settings instance containing database configuration
        
    Returns:
        str: PostgreSQL connection URL
    """
    if not settings.SQLALCHEMY_DATABASE_URI:
        settings.SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}/{settings.POSTGRES_DB}"
        )
    return settings.SQLALCHEMY_DATABASE_URI

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
        
        # Authentication Configuration
        "USE_OKTA": str(settings.USE_OKTA).lower(),
        "SECRET_KEY": settings.SECRET_KEY,
        "ACCESS_TOKEN_EXPIRE_MINUTES": str(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        
        # Okta Configuration
        "OKTA_ISSUER": settings.OKTA_ISSUER,
        "OKTA_CLIENT_ID": settings.OKTA_CLIENT_ID,
        
        # SQLALCHEMY Configuration
        "SQLALCHEMY_DATABASE_URI": settings.SQLALCHEMY_DATABASE_URI,
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

# Set database URI if not provided
