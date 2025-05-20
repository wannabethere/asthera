from fastapi import Depends, Request
from typing import Dict, Any
from app.storage.sessionmanager import get_session_manager
from app.settings import get_settings
from genimel.services.documents import DocumentChromaStore, CHROMA_STORE_PATH
import chromadb

def get_app_state(request: Request):
    """Get the FastAPI app state."""
    return request.app.state

def get_analysis_agent(app_state=Depends(get_app_state)):
    """Get the initialized analysis agent."""
    return app_state.analysis_agent

def get_recommendation_system(app_state=Depends(get_app_state)):
    """Get the initialized recommendation system."""
    return app_state.recommendation_system

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
    
    
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)

    # Initialize vector stores
    vectorstore_examples = DocumentChromaStore(
        persistent_client=client,
        collection_name="tools_examples_collection"
    )

    vectorstore_functions = DocumentChromaStore(
        persistent_client=client,
        collection_name="tools_spec_collection"
    )

    vectorstore_insights = DocumentChromaStore(
        persistent_client=client,
        collection_name="tools_insights_collection"
    )
    
    
    return {
        "session_manager": session_manager,
        "db_config": db_config,
        "vectorstore_examples": vectorstore_examples,
        "vectorstore_functions": vectorstore_functions,
        "vectorstore_insights": vectorstore_insights
    }