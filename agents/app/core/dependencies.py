from fastapi import Depends, Request, HTTPException
from typing import Dict, Any, Optional
from app.storage.sessionmanager import get_session_manager
from app.settings import get_settings
from app.storage.documents import DocumentChromaStore, CHROMA_STORE_PATH
from langchain_openai import ChatOpenAI
import chromadb
from app.core.provider import DocumentStoreProvider
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Global cache for ChromaDB client and document store provider
_chromadb_client_cache = None
_doc_store_provider_cache = None

def get_app_state(request: Request):
    """Get the FastAPI app state."""
    return request.app.state

def get_analysis_agent(app_state=Depends(get_app_state)):
    """Get the initialized analysis agent."""
    return app_state.analysis_agent

def get_recommendation_system(app_state=Depends(get_app_state)):
    """Get the initialized recommendation system."""
    return app_state.recommendation_system

# Configuration
def get_llm(temperature: float = 0.0, model: str = "gpt-4o-mini"):
    """Get the LLM with specified temperature and model."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature
    )

def get_chromadb_client():
    """Get ChromaDB client based on configuration settings with caching."""
    global _chromadb_client_cache
    
    if _chromadb_client_cache is not None:
        logger.info("Returning cached ChromaDB client (no re-initialization needed)")
        return _chromadb_client_cache
    
    # Clear settings cache to ensure we get the latest settings
    from app.settings import clear_settings_cache
    clear_settings_cache()
    
    settings = get_settings()
    
    logger.info(f"ChromaDB configuration: CHROMA_USE_LOCAL={settings.CHROMA_USE_LOCAL}, CHROMA_STORE_PATH={settings.CHROMA_STORE_PATH}")
    
    if settings.CHROMA_USE_LOCAL:
        # Use local persistent client
        logger.info(f"Creating local PersistentClient with path: {settings.CHROMA_STORE_PATH}")
        _chromadb_client_cache = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    else:
        # Use HTTP client (default)
        logger.info(f"Creating HTTP client with host: {settings.CHROMA_HOST}, port: {settings.CHROMA_PORT}")
        try:
            _chromadb_client_cache = chromadb.HttpClient(
                host=settings.CHROMA_HOST, 
                port=settings.CHROMA_PORT,
                settings=chromadb.Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception as e:
            logger.error(f"Failed to create HTTP client: {e}")
            raise
    
    return _chromadb_client_cache


# Helper function to create LLM instances from settings
def create_llm_instances_from_settings(custom_settings: Optional[Dict[str, Any]] = None):
    """Create LLM instances from external settings configuration
    
    Args:
        custom_settings: Optional dictionary containing LLM configuration
                        Expected keys: model_name, sql_parser_temp, alert_generator_temp, 
                                      critic_temp, refiner_temp
                        If not provided, will use default settings
    
    Returns:
        Tuple of (sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm)
    """
    if custom_settings:
        # Use custom settings dictionary
        model_name = custom_settings.get("model_name", "gpt-4o-mini")
        sql_parser_temp = custom_settings.get("sql_parser_temp", 0.0)
        alert_generator_temp = custom_settings.get("alert_generator_temp", 0.1)
        critic_temp = custom_settings.get("critic_temp", 0.0)
        refiner_temp = custom_settings.get("refiner_temp", 0.2)
    else:
        # Use default settings
        model_name = "gpt-4o-mini"
        sql_parser_temp = 0.0
        alert_generator_temp = 0.1
        critic_temp = 0.0
        refiner_temp = 0.2
    
    from langchain_openai import ChatOpenAI
    sql_parser_llm = ChatOpenAI(
        model=model_name, 
        temperature=sql_parser_temp
    )
    alert_generator_llm = ChatOpenAI(
        model=model_name, 
        temperature=alert_generator_temp
    )
    critic_llm = ChatOpenAI(
        model=model_name, 
        temperature=critic_temp
    )
    refiner_llm = ChatOpenAI(
        model=model_name, 
        temperature=refiner_temp
    )
    
    return sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm
def get_chromadb_wrapper():
    """Get ChromaDB wrapper instance using the configured client."""
    client = get_chromadb_client()
    from app.storage.chromadb import ChromaDB
    return ChromaDB(client=client)

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores with caching."""
    global _doc_store_provider_cache
    
    if _doc_store_provider_cache is not None:
        logger.info("Returning cached document store provider (no re-initialization needed)")
        return _doc_store_provider_cache
    
    logger.info("Creating new document store provider (first time initialization)")
    
    # Initialize ChromaDB client using configuration
    client = get_chromadb_client()
    
    # Create document stores for SQL-related collections
    sql_stores = {
        "db_schema": DocumentChromaStore(
            persistent_client=client,
            collection_name="db_schema"
        ),
        "sql_pairs": DocumentChromaStore(
            persistent_client=client,
            collection_name="sql_pairs"
        ),
        "instructions": DocumentChromaStore(
            persistent_client=client,
            collection_name="instructions"
        ),
        "historical_question": DocumentChromaStore(
            persistent_client=client,
            collection_name="historical_question"
        ),
        "table_description": DocumentChromaStore(
            persistent_client=client,
            collection_name="table_description"
        ),
        "project_meta": DocumentChromaStore(
            persistent_client=client,
            collection_name="project_meta"
        ),
        "document_insights": DocumentChromaStore(
            persistent_client=client,
            collection_name="document_insights"
        ),
        "document_planning": DocumentChromaStore(
            persistent_client=client,   
            collection_name="document_planning"
        )

    }
    # Create and return the document store provider
    _doc_store_provider_cache = DocumentStoreProvider(
        stores=sql_stores,
        default_store="sql_pairs"
    )
    
    return _doc_store_provider_cache

def clear_chromadb_cache():
    """Clear the ChromaDB client and document store provider cache."""
    global _chromadb_client_cache, _doc_store_provider_cache
    _chromadb_client_cache = None
    _doc_store_provider_cache = None
    logger.info("Cleared ChromaDB client and document store provider cache")

def get_alert_service(app_state=Depends(get_app_state)):
    """Get the alert service instance."""
    if not hasattr(app_state, 'alert_service') or app_state.alert_service is None:
        raise HTTPException(
            status_code=503,
            detail="Alert service is not available. Please ensure the service is properly configured."
        )
    return app_state.alert_service

def get_alert_compatibility_service(app_state=Depends(get_app_state)):
    """Get the alert compatibility service instance."""
    if not hasattr(app_state, 'alert_compatibility_service') or app_state.alert_compatibility_service is None:
        raise HTTPException(
            status_code=503,
            detail="Alert compatibility service is not available. Please ensure the service is properly configured."
        )
    return app_state.alert_compatibility_service

def get_dependencies():
    """Get all dependencies for the API."""
    # Get settings
    settings = get_settings()
    
    # Create DB config from settings
    db_config = {
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
        "database": settings.POSTGRES_DB,
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD
    }
    
    # Get or create session manager with the DB config
    session_manager = get_session_manager(db_config)
        
   # Initialize ChromaDB client using configuration
    client = get_chromadb_client()
    
    
    
    # Get document store provider for SQL stores
    doc_store_provider = get_doc_store_provider()
    
    return {
        "session_manager": session_manager,
        "db_config": db_config,
        "doc_store_provider": doc_store_provider
    }

def get_document_service(app_state=Depends(get_app_state)):
    """Get the document persistence service from app state."""
    if not hasattr(app_state, 'document_persistence_service') or app_state.document_persistence_service is None:
        raise HTTPException(
            status_code=503,
            detail="Document persistence service is not available. Please ensure the service is properly configured."
        )
    return app_state.document_persistence_service

