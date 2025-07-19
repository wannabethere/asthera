import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Simple loading of .env file if it exists
# In Docker/K8s this will do nothing since .env won't exist
try:
    load_dotenv()
    logger.info("Loaded environment variables from .env file")
except Exception:
    logger.info("No .env file found, using environment variables")

class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]  # Default to allow all origins
    
    # API Keys and Security
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: Optional[str] = None
    GROK_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # LLM Provider Settings
    DEFAULT_LLM_PROVIDER: str = "openai"  # Options: "openai", "google", "anthropic", "grok"
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_MODEL: str = "claude-3-opus"
    GROK_MODEL: str = "grok-1"
    GOOGLE_GEMINI_MODEL: str = "gemini-2.5-pro-preview-06-05"
    GOOGLE_GEMINI_FLASH_MODEL: str = "gemini-2.0-flash" # "gemini-2.5-flash-preview-05-20"

    # Model Configuration
    MODEL_NAME: str = "gpt-4o"
    TEMPERATURE: float = 0.0
    MAX_TOKENS: Optional[int] = None
    TOP_P: Optional[float] = None
    FREQUENCY_PENALTY: float = 0.0
    PRESENCE_PENALTY: float = 0.0
    
    # OpenTelemetry Settings
    OPENTELEMETRY_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "crag-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL: str = "grpc"
    
    # RAG Settings
    MAX_DOCUMENTS: int = 4
    RELEVANCE_THRESHOLD: float = 0.7
    MAX_ATTEMPTS: int = 3
    
    # Debug Setting
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # PostgreSQL Settings - using DB_* variables as provided in the K8s deployment
    DB_HOST: str = os.getenv("DB_HOST", "postgres-service")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "postgres")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    # For compatibility with newer naming conventions - these use the DB_* variables
    @property
    def POSTGRES_USER(self) -> str:
        return self.DB_USER
        
    @property
    def POSTGRES_PASSWORD(self) -> str:
        return self.DB_PASSWORD
        
    @property
    def POSTGRES_HOST(self) -> str:
        return self.DB_HOST
        
    @property
    def POSTGRES_PORT(self) -> str:
        return str(self.DB_PORT)
        
    @property
    def POSTGRES_DB(self) -> str:
        return self.DB_NAME

    # ChromaDB Settings - using variables as provided in the K8s deployment
    CHROMA_DB_HOST: str = os.getenv("CHROMA_HOST", "vector-db-service") 
    CHROMA_DB_PORT: int = int(os.getenv("CHROMA_PORT", "8000"))
    CHROMA_DB_USER: Optional[str] = None
    CHROMA_DB_PASSWORD: Optional[str] = None
    
    # For compatibility with env.py
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "vector-db-service")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8000"))

    @property
    def chromadb_connection_string(self) -> str:
        # For remote ChromaDB instance
        auth = f"{self.CHROMA_DB_USER}:{self.CHROMA_DB_PASSWORD}@" if self.CHROMA_DB_USER and self.CHROMA_DB_PASSWORD else ""
        return f"http://{auth}{self.CHROMA_DB_HOST}:{self.CHROMA_DB_PORT}"
    
    # Redis Settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis-service")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    
    @property
    def postgres_connection_string(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def redis_connection_string(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else "@"
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Returns:
        Settings: Application settings
    """
    return Settings()


def print_settings_summary(mask_secrets: bool = True) -> None:
    """
    Print a summary of the current settings configuration.
    
    Args:
        mask_secrets: If True, mask sensitive values like API keys and passwords
    """
    settings = get_settings()
    
    print("\n=== SETTINGS SUMMARY ===\n")
    
    # Helper function to format sensitive values
    def format_value(name: str, value: Any) -> str:
        if mask_secrets and any(secret in name.lower() for secret in ["key", "password", "secret", "token"]):
            if value and isinstance(value, str) and len(value) > 6:
                return f"****{value[-6:]}"
            return "****"
        return str(value)
    
    # Environment and Base Settings
    print("Environment:")
    print(f"  DEBUG: {settings.DEBUG}")
    
    # LLM Settings
    print("\nLLM Settings:")
    print(f"  OPENAI_API_KEY: {format_value('OPENAI_API_KEY', settings.OPENAI_API_KEY)}")
    print(f"  DEFAULT_LLM_PROVIDER: {settings.DEFAULT_LLM_PROVIDER}")
    print(f"  OPENAI_MODEL: {settings.OPENAI_MODEL}")
    print(f"  TEMPERATURE: {settings.TEMPERATURE}")
    
    # Database Settings
    print("\nDatabase Settings:")
    print(f"  DB_HOST: {settings.DB_HOST}")
    print(f"  DB_PORT: {settings.DB_PORT}")
    print(f"  DB_NAME: {settings.DB_NAME}")
    print(f"  DB_USER: {settings.DB_USER}")
    print(f"  DB_PASSWORD: {format_value('DB_PASSWORD', settings.DB_PASSWORD)}")
    
    # ChromaDB Settings
    print("\nChromaDB Settings:")
    print(f"  CHROMA_HOST: {settings.CHROMA_HOST}")
    print(f"  CHROMA_PORT: {settings.CHROMA_PORT}")
    
    # Connection Strings
    print("\nConnection Strings:")
    print(f"  postgres_connection_string: {format_value('postgres_connection_string', settings.postgres_connection_string)}")
    print(f"  chromadb_connection_string: {settings.chromadb_connection_string}")
    print(f"  redis_connection_string: {settings.redis_connection_string}")


if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Load settings and print summary
    try:
        print("\n=== Loading Settings ===")
        settings = get_settings()
        print("Settings loaded successfully")
        
        print_settings_summary()
        
        print("\n=== Settings Loaded Successfully ===")
    except Exception as e:
        print(f"\nERROR loading settings: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)