"""
Standalone settings for API to MDL converter with agent integration
Simplified version that works independently
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings for API to MDL converter with agent integration"""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    
    # OpenAI API Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # LLM Configuration
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "openai")
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # Environment
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Agent Configuration
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "120"))  # seconds
    AGENT_MAX_RETRIES: int = int(os.getenv("AGENT_MAX_RETRIES", "3"))
    
    # ChromaDB Configuration (optional, for document storage)
    CHROMA_USE_LOCAL: bool = os.getenv("CHROMA_USE_LOCAL", "false").lower() == "true"
    CHROMA_STORE_PATH: str = os.getenv("CHROMA_STORE_PATH", "./chroma_db")
    CHROMA_HOST: Optional[str] = os.getenv("CHROMA_HOST")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8888"))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )
    
    def validate_openai_key(self) -> bool:
        """Validate that OpenAI API key is set"""
        if not self.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not set. LLM features will not work.")
            return False
        
        # Basic validation - should start with 'sk-'
        if not self.OPENAI_API_KEY.startswith('sk-'):
            logger.warning(f"OPENAI_API_KEY format may be invalid. Key starts with: {self.OPENAI_API_KEY[:5]}...")
        
        return True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    logger.debug("Creating new Settings instance")
    settings = Settings()
    
    # Validate OpenAI key
    settings.validate_openai_key()
    
    # Set environment variables for compatibility
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    
    logger.info(f"Settings loaded - Model: {settings.LLM_MODEL}, Temperature: {settings.LLM_TEMPERATURE}")
    return settings


def init_environment():
    """Initialize environment variables from settings"""
    settings = get_settings()
    
    # Set critical environment variables
    env_vars = {
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "LLM_MODEL": settings.LLM_MODEL,
        "LLM_TEMPERATURE": str(settings.LLM_TEMPERATURE),
        "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
        "PYTHONUNBUFFERED": "1",
    }
    
    for key, value in env_vars.items():
        if value:
            os.environ[key] = str(value)
            logger.debug(f"Set environment variable: {key}")
    
    logger.info("Environment initialized")


def clear_settings_cache():
    """Clear the settings cache to force reload"""
    get_settings.cache_clear()
    logger.info("Settings cache cleared")

