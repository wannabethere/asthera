"""
Dependency injection for persistence services
"""

import os
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.session_manager import SessionManager
from app.storage.documents import DocumentChromaStore
from app.core.provider import DocumentStoreProvider
from app.core.settings import get_settings

settings = get_settings()


def get_session_manager() -> SessionManager:
    """Get the singleton session manager instance"""
    return SessionManager.get_instance()


def get_llm(temperature: float = 0.0, model: str = "gpt-4o-mini"):
    """Get LLM instance for AI operations"""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key
    )

def get_chromadb_client():
    """Get ChromaDB client based on configuration settings."""
    if settings.CHROMA_USE_LOCAL:
        # Use local persistent client
        return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY+"/enhanced_comprehensive_registry")
    else:
        # Use HTTP client (default)
        return chromadb.HttpClient(
            host=settings.CHROMA_HOST, 
            port=settings.CHROMA_PORT
        )

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores."""
    # Initialize ChromaDB client using configuration
    client = get_chromadb_client()
    
    # Create document stores for SQL-related collections
    # Use enhanced collection names that match the test file
    stores = {
        "usage_examples": DocumentChromaStore(persistent_client=client,collection_name="comprehensive_ml_functions_demo_usage_examples"),
        "function_spec": DocumentChromaStore(persistent_client=client,collection_name="comprehensive_ml_functions_demo_toolspecs"),
        "insights_store": DocumentChromaStore(persistent_client=client,collection_name="comprehensive_ml_functions_demo_instructions"), 
        "examples_store": DocumentChromaStore(persistent_client=client,collection_name="comprehensive_ml_functions_demo_code_examples"),
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
        stores=stores,
        default_store="function_spec"
    )


async def get_async_db_session():
    """Get async database session using session manager"""
    session_manager = get_session_manager()
    async with session_manager.get_async_db_session() as session:
        yield session


def get_embeddings():
    """Get OpenAI embeddings instance"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key
    )


