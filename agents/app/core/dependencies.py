from fastapi import Depends, Request, HTTPException
from typing import Dict, Any, Optional
from app.storage.sessionmanager import get_session_manager
from app.settings import get_settings
from app.storage.documents import DocumentChromaStore, CHROMA_STORE_PATH
from langchain_openai import ChatOpenAI
import chromadb
from app.core.provider import DocumentStoreProvider

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
    """Get ChromaDB client based on configuration settings."""
    settings = get_settings()
    
    if settings.CHROMA_USE_LOCAL:
        # Use local persistent client
        return chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    else:
        # Use HTTP client (default)
        return chromadb.HttpClient(
            host=settings.CHROMA_HOST, 
            port=settings.CHROMA_PORT
        )


# Helper function to create LLM instances from settings
def create_llm_instances_from_settings(custom_settings: Optional[Dict[str, Any]] = None):
    """Create LLM instances from external settings configuration
    
    Args:
        custom_settings: Optional dictionary containing LLM configuration
                        Expected keys: model_name, sql_parser_temp, alert_generator_temp, 
                                      critic_temp, refiner_temp
                        If not provided, will use default settings from get_settings()
    
    Returns:
        Tuple of (sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm)
    """
    if custom_settings:
        settings = custom_settings
    else:
        settings = get_settings()
    model_name = settings.get("model_name", "gpt-4o-mini")
    from langchain_openai import ChatOpenAI
    sql_parser_llm = ChatOpenAI(
        model=model_name, 
        temperature=settings.get("sql_parser_temp", 0.0)
    )
    alert_generator_llm = ChatOpenAI(
        model=model_name, 
        temperature=settings.get("alert_generator_temp", 0.1)
    )
    critic_llm = ChatOpenAI(
        model=model_name, 
        temperature=settings.get("critic_temp", 0.0)
    )
    refiner_llm = ChatOpenAI(
        model=model_name, 
        temperature=settings.get("refiner_temp", 0.2)
    )
    
    return sql_parser_llm, alert_generator_llm, critic_llm, refiner_llm
def get_chromadb_wrapper():
    """Get ChromaDB wrapper instance using the configured client."""
    client = get_chromadb_client()
    from app.storage.chromadb import ChromaDB
    return ChromaDB(client=client)

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores."""
    
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
        )
    }
    # Create and return the document store provider
    return DocumentStoreProvider(
        stores=sql_stores,
        default_store="sql_pairs"
    )

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

"""
def get_ask_service() -> AskService:
    #Get AskService instance
    return AskService()

def get_question_recommendation_service() -> QuestionRecommendation:
    #Get QuestionRecommendation service instance
    pipeline_container = PipelineContainer.get_instance()
    return QuestionRecommendation(pipeline_container.get_all_pipelines())

"""