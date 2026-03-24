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
    
    # Base paths (knowledge repo root)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"

    # ============================================================================
    # Vector Store Settings (.env)
    # ============================================================================
    VECTOR_STORE_TYPE: VectorStoreType = VectorStoreType.QDRANT
    VECTOR_STORE_PATH: str = "../../data/vector_store"
    CHROMA_STORE_PATH: str = "../../data/chroma_db"
    CHROMA_USE_LOCAL: bool = True
    CHROMA_HOST: Optional[str] = None
    CHROMA_PORT: int = 8888
    CHROMA_COLLECTION_NAME: str = "default"
    CHROMA_PERSIST_DIRECTORY: Optional[str] = None

    # Qdrant
    QDRANT_HOST: Optional[str] = None
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "default"
    QDRANT_URL: Optional[str] = None  # Override: full URL (e.g. http://host:6333)
    QDRANT_API_KEY: Optional[str] = None  # For cloud/authenticated Qdrant

    # LMS causal graph (Qdrant) — four collections; names overrideable for legacy (e.g. cce_causal_*)
    LMS_CAUSAL_NODES_COLLECTION: str = "lms_causal_nodes"
    LMS_CAUSAL_EDGES_COLLECTION: str = "lms_causal_edges"
    LMS_FOCUS_AREA_TAXONOMY_COLLECTION: str = "lms_focus_area_taxonomy"
    LMS_USE_CASE_GROUPS_COLLECTION: str = "lms_use_case_groups"
    LMS_CAUSAL_NODES_SEED_PATH: str = "lms_causal_nodes_seed.json"
    LMS_CAUSAL_EDGES_PATH: str = "lms_causal_edges_v2.json"
    LMS_FOCUS_AREA_TAXONOMY_PATH: str = "lms_focus_area_taxonomy.json"
    LMS_METRIC_USE_CASE_GROUPS_PATH: str = "lms_metric_use_case_groups_v2.json"
    LMS_CAUSAL_EDGE_MIN_CONFIDENCE_DEFAULT: float = 0.65

    # ATT&CK ingestion: vector store collection for techniques (semantic search)
    ATTACK_TECHNIQUES_COLLECTION: str = "attack_techniques"
    # ATT&CK → control mapping vectors (scenario ingest, multi-framework mappings)
    ATTACK_CONTROL_MAPPINGS_COLLECTION: str = "attack_control_mappings"
    # CWE/CAPEC → ATT&CK mapping vectors (cwe_capec_attack_vector_ingest)
    THREAT_INTEL_CWE_CAPEC_ATTACK_COLLECTION: str = "threat_intel_cwe_capec_attack_mappings"

    # Project reader Qdrant (sql_meta path for indexing)
    SQL_META_PATH: str = "../../data/sql_meta"
    # When set (e.g. "core_"), RetrievalHelper uses core_* Qdrant collections for table/schema retrieval (ProjectReaderQdrant).
    CORE_COLLECTION_PREFIX: Optional[str] = None

    # Pinecone
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    PINECONE_INDEX_NAME: str = "default"

    # ============================================================================
    # Cache Settings (.env)
    # ============================================================================
    # When False, cache is disabled (no Redis, no in-memory); use when Redis is unavailable.
    CACHE_ENABLED: bool = False
    CACHE_TYPE: CacheType = CacheType.MEMORY
    CACHE_TTL: int = 120
    CACHE_MAXSIZE: int = 1_000_000

    # Redis
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False

    # ============================================================================
    # Database Settings (.env)
    # ============================================================================
    DATABASE_TYPE: DatabaseType = DatabaseType.POSTGRES

    # PostgreSQL
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_POOL_MIN_SIZE: int = 5
    POSTGRES_POOL_MAX_SIZE: int = 20
    POSTGRES_SSL_MODE: str = "require"

    # MySQL
    MYSQL_HOST: Optional[str] = None
    MYSQL_PORT: int = 3306
    MYSQL_DB: Optional[str] = None
    MYSQL_USER: Optional[str] = None
    MYSQL_PASSWORD: Optional[str] = None
    MYSQL_POOL_MIN_SIZE: int = 5
    MYSQL_POOL_MAX_SIZE: int = 20
    
    # ============================================================================
    # Security Intelligence Database Connections (.env)
    # ============================================================================
    # Optional: Separate database connections for different security intelligence sources
    # If not specified, uses the default database connection above
    
    # CVE/ATT&CK Mappings Database
    SEC_INTEL_CVE_ATTACK_DB_HOST: Optional[str] = None
    SEC_INTEL_CVE_ATTACK_DB_PORT: Optional[int] = None
    SEC_INTEL_CVE_ATTACK_DB_NAME: Optional[str] = None
    SEC_INTEL_CVE_ATTACK_DB_USER: Optional[str] = None
    SEC_INTEL_CVE_ATTACK_DB_PASSWORD: Optional[str] = None
    
    # CPE Dictionary Database
    SEC_INTEL_CPE_DB_HOST: Optional[str] = None
    SEC_INTEL_CPE_DB_PORT: Optional[int] = None
    SEC_INTEL_CPE_DB_NAME: Optional[str] = None
    SEC_INTEL_CPE_DB_USER: Optional[str] = None
    SEC_INTEL_CPE_DB_PASSWORD: Optional[str] = None
    
    # Exploit Intelligence Database (Exploit-DB, Metasploit, Nuclei)
    SEC_INTEL_EXPLOIT_DB_HOST: Optional[str] = None
    SEC_INTEL_EXPLOIT_DB_PORT: Optional[int] = None
    SEC_INTEL_EXPLOIT_DB_NAME: Optional[str] = None
    SEC_INTEL_EXPLOIT_DB_USER: Optional[str] = None
    SEC_INTEL_EXPLOIT_DB_PASSWORD: Optional[str] = None
    
    # Compliance Database (CIS Benchmarks, Sigma Rules)
    SEC_INTEL_COMPLIANCE_DB_HOST: Optional[str] = None
    SEC_INTEL_COMPLIANCE_DB_PORT: Optional[int] = None
    SEC_INTEL_COMPLIANCE_DB_NAME: Optional[str] = None
    SEC_INTEL_COMPLIANCE_DB_USER: Optional[str] = None
    SEC_INTEL_COMPLIANCE_DB_PASSWORD: Optional[str] = None
    
    # ============================================================================
    # Embedding Settings
    # ============================================================================
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: Optional[str] = None  # Set via .env; do not check in
    ANTHROPIC_API_KEY: Optional[str] = None  # Set via .env when LLM_PROVIDER=anthropic
    
    # ============================================================================
    # External API Keys (.env)
    # ============================================================================
    TAVILY_API_KEY: Optional[str] = None  # Set via .env for tavily_search tool
    NVD_API_KEY: Optional[str] = None  # Set via .env for NVD API (optional, increases rate limit)
    EPSS_CSV_PATH: Optional[str] = None  # Local EPSS CSV path (skips download when set)

    # ============================================================================
    # LLM Settings (.env: OPENAI_API_KEY; config/llm_models.yaml: per-type models)
    # ============================================================================
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    LLM_PROVIDER: str = "openai"  # openai | anthropic

    # ============================================================================
    # Environment
    # ============================================================================
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Demo: synthetic gold SQL + insights for assembler/UI (no warehouse; see demo_sql_insight_agent)
    DEMO_FAKE_SQL_AND_INSIGHTS: bool = False
    # Cap per-metric demo SQL/insight rows per assembly pass (CSOD + DT)
    DEMO_PER_METRIC_SQL_INSIGHTS_MAX: int = 25
    
    # ============================================================================
    # OpenTelemetry Settings (.env)
    # ============================================================================
    # Enable/disable OpenTelemetry tracing and monitoring
    OPENTELEMETRY_ENABLED: bool = False  # Set to True to enable OTEL tracing
    OTEL_SERVICE_NAME: str = "compliance-skill-api"  # Service name for traces
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None  # OTLP collector endpoint (default: http://localhost:4317)
    OTEL_EXPORTER_OTLP_INSECURE: bool = True  # Use insecure connection (set False for TLS in production)
    OTEL_CONSOLE_EXPORTER_ENABLED: bool = False  # Enable console exporter for debugging
    OTEL_INSTRUMENT_FASTAPI: bool = True  # Automatically instrument FastAPI
    OTEL_INSTRUMENT_ASYNCPG: bool = False  # Automatically instrument asyncpg (only if using asyncpg)
    
    # ============================================================================
    # API Settings
    # ============================================================================
    API_HOST: str = "0.0.0.0"

    API_PORT: int = 8002

    # JWT / auth: when True, skip JWT verification and use default permissive claims (for local/dev).
    JWT_AUTH_DISABLED: bool = True

    # API security: when enabled, requests must include a provisioned token
    API_SECURITY_ENABLED: bool = False
    # List of allowed tokens: comma-separated and/or newline-separated (e.g. token1,token2,token3)
    API_PROVISIONED_TOKENS: str = ""
    # Optional: path to file with one token per line (merged with API_PROVISIONED_TOKENS)
    API_PROVISIONED_TOKENS_FILE: Optional[str] = None

    # Gateway (when complianceskill acts as agent server for Agent Gateway)
    GATEWAY_JWT_SECRET: Optional[str] = None  # Verify gateway JWTs; uses API key if unset
    GATEWAY_CTX_SECRET: Optional[str] = None  # Verify ctx_token HMAC when fetching context from Redis

    def get_provisioned_tokens(self) -> List[str]:
        """Return list of provisioned tokens (from env and optional file), stripped and deduplicated."""
        tokens: List[str] = []
        if self.API_PROVISIONED_TOKENS:
            for part in self.API_PROVISIONED_TOKENS.replace("\n", ",").split(","):
                t = part.strip()
                if t and t not in tokens:
                    tokens.append(t)
        if self.API_PROVISIONED_TOKENS_FILE:
            path = Path(self.API_PROVISIONED_TOKENS_FILE)
            if not path.is_absolute():
                path = self.BASE_DIR / path
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                    for line in text.splitlines():
                        t = line.strip()
                        if t and not t.startswith("#") and t not in tokens:
                            tokens.append(t)
                except Exception as e:
                    logger.warning("Could not read API_PROVISIONED_TOKENS_FILE %s: %s", path, e)
        return tokens

    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
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
                "host": self.CHROMA_HOST or "localhost",
                "port": self.CHROMA_PORT,
                "collection_name": self.CHROMA_COLLECTION_NAME,
                "persist_directory": self.CHROMA_PERSIST_DIRECTORY or self.CHROMA_STORE_PATH
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
                "host": self.REDIS_HOST or "localhost",
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
                "host": self.POSTGRES_HOST or "localhost",
                "port": self.POSTGRES_PORT,
                "database": self.POSTGRES_DB or "",
                "user": self.POSTGRES_USER or "",
                "password": self.POSTGRES_PASSWORD or "",
                "pool_min_size": self.POSTGRES_POOL_MIN_SIZE,
                "pool_max_size": self.POSTGRES_POOL_MAX_SIZE,
                "ssl_mode": self.POSTGRES_SSL_MODE
            })
        elif self.DATABASE_TYPE == DatabaseType.MYSQL:
            config.update({
                "host": self.MYSQL_HOST or "localhost",
                "port": self.MYSQL_PORT,
                "database": self.MYSQL_DB or "",
                "user": self.MYSQL_USER or "",
                "password": self.MYSQL_PASSWORD or "",
                "pool_min_size": self.MYSQL_POOL_MIN_SIZE,
                "pool_max_size": self.MYSQL_POOL_MAX_SIZE
            })

        return config
    
    def get_attack_db_dsn(self) -> str:
        """
        Build PostgreSQL DSN for ATT&CK/CVE database.
        Uses SEC_INTEL_CVE_ATTACK_DB_* if set, otherwise default POSTGRES_*.
        """
        from urllib.parse import quote_plus
        config = self.get_security_intel_db_config("cve_attack")
        host = config.get("host") or "localhost"
        port = config.get("port") or 5432
        database = config.get("database") or ""
        user = config.get("user") or ""
        password = config.get("password") or ""
        if password:
            safe = quote_plus(password)
            return f"postgresql://{user}:{safe}@{host}:{port}/{database}"
        return f"postgresql://{user}@{host}:{port}/{database}"

    def get_security_intel_db_config(self, source: str) -> Dict[str, Any]:
        """
        Get database configuration for a specific security intelligence source.
        
        Args:
            source: One of "cve_attack", "cpe", "exploit", "compliance"
        
        Returns:
            Database configuration dict. If source-specific config not set,
            returns default database config.
        """
        # Default to main database config
        default_config = self.get_database_config()
        
        # Map source to environment variable prefixes
        source_map = {
            "cve_attack": {
                "host": self.SEC_INTEL_CVE_ATTACK_DB_HOST,
                "port": self.SEC_INTEL_CVE_ATTACK_DB_PORT,
                "database": self.SEC_INTEL_CVE_ATTACK_DB_NAME,
                "user": self.SEC_INTEL_CVE_ATTACK_DB_USER,
                "password": self.SEC_INTEL_CVE_ATTACK_DB_PASSWORD,
            },
            "cpe": {
                "host": self.SEC_INTEL_CPE_DB_HOST,
                "port": self.SEC_INTEL_CPE_DB_PORT,
                "database": self.SEC_INTEL_CPE_DB_NAME,
                "user": self.SEC_INTEL_CPE_DB_USER,
                "password": self.SEC_INTEL_CPE_DB_PASSWORD,
            },
            "exploit": {
                "host": self.SEC_INTEL_EXPLOIT_DB_HOST,
                "port": self.SEC_INTEL_EXPLOIT_DB_PORT,
                "database": self.SEC_INTEL_EXPLOIT_DB_NAME,
                "user": self.SEC_INTEL_EXPLOIT_DB_USER,
                "password": self.SEC_INTEL_EXPLOIT_DB_PASSWORD,
            },
            "compliance": {
                "host": self.SEC_INTEL_COMPLIANCE_DB_HOST,
                "port": self.SEC_INTEL_COMPLIANCE_DB_PORT,
                "database": self.SEC_INTEL_COMPLIANCE_DB_NAME,
                "user": self.SEC_INTEL_COMPLIANCE_DB_USER,
                "password": self.SEC_INTEL_COMPLIANCE_DB_PASSWORD,
            },
        }
        
        if source not in source_map:
            logger.warning(f"Unknown security intelligence source: {source}, using default database")
            return default_config
        
        source_config = source_map[source]
        
        # If any source-specific config is set, use it (otherwise fall back to default)
        if any([
            source_config["host"],
            source_config["port"],
            source_config["database"],
            source_config["user"],
            source_config["password"],
        ]):
            # Build config with source-specific values, falling back to defaults
            config = default_config.copy()
            
            if source_config["host"]:
                config["host"] = source_config["host"]
            if source_config["port"]:
                config["port"] = source_config["port"]
            if source_config["database"]:
                config["database"] = source_config["database"]
            if source_config["user"]:
                config["user"] = source_config["user"]
            if source_config["password"]:
                config["password"] = source_config["password"]
            
            logger.info(f"Using source-specific database config for {source}: {config.get('host')}:{config.get('port')}/{config.get('database')}")
            return config
        
        # No source-specific config, use default
        logger.debug(f"No source-specific config for {source}, using default database")
        return default_config

    def get_llm_model_for_type(self, llm_type: str) -> str:
        """Return model for LLM type from config/llm_models.yaml; fallback to LLM_MODEL."""
        llm_path = self.CONFIG_DIR / "llm_models.yaml"
        if llm_path.exists():
            try:
                import yaml
                with open(llm_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                default = data.get("default_model") or self.LLM_MODEL
                models = data.get("models") or {}
                model = models.get(llm_type.upper())
                if model:
                    return model
                return default
            except Exception as e:
                logger.debug("Could not load llm_models.yaml: %s", e)
        return self.LLM_MODEL


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
        
        # External API Keys
        "TAVILY_API_KEY": settings.TAVILY_API_KEY,
        "NVD_API_KEY": settings.NVD_API_KEY,
        
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
        
        # Qdrant Settings
        "QDRANT_HOST": settings.QDRANT_HOST or "localhost",
        "QDRANT_PORT": str(settings.QDRANT_PORT),
        "QDRANT_COLLECTION_NAME": settings.QDRANT_COLLECTION_NAME,
        "VECTOR_STORE_TYPE": settings.VECTOR_STORE_TYPE.value,
        
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
        
        # OpenTelemetry Settings
        "OPENTELEMETRY_ENABLED": str(settings.OPENTELEMETRY_ENABLED).lower(),
        "OTEL_SERVICE_NAME": settings.OTEL_SERVICE_NAME,
        "OTEL_EXPORTER_OTLP_ENDPOINT": settings.OTEL_EXPORTER_OTLP_ENDPOINT or "http://localhost:4317",
        "OTEL_EXPORTER_OTLP_INSECURE": str(settings.OTEL_EXPORTER_OTLP_INSECURE).lower(),
        "OTEL_CONSOLE_EXPORTER_ENABLED": str(settings.OTEL_CONSOLE_EXPORTER_ENABLED).lower(),
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

