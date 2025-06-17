from fastapi import Depends, Request
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

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores."""
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    #client = chromadb.HttpClient(host='ec2-54-161-71-105.compute-1.amazonaws.com', port=8888)
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
    
    # Get document store provider for SQL stores
    doc_store_provider = get_doc_store_provider()
    
    return {
        "session_manager": session_manager,
        "db_config": db_config,
        "vectorstore_examples": vectorstore_examples,
        "vectorstore_functions": vectorstore_functions,
        "vectorstore_insights": vectorstore_insights,
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