"""
Configuration settings for Self-RAG agentic and document retrieval.
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.document_schemas import DocumentSource


class ChromaDBCollections(BaseModel):
    """Collection names for ChromaDB collections."""
    
    # Main collections
    insights_collection: str = Field(default="insights", description="Collection for all insights (Gong and Salesforce)")
    chunks_collection: str = Field(default="chunks", description="Collection for all chunks (Gong and Salesforce)")
    documents_collection: str = Field(default="documents", description="Collection for complete documents")
    
    # CSOD collection
    csod_collection: str = Field(default="csod_datasets1", description="Collection for CSOD datasets")
    
    # Cache collection
    cache_collection: str = Field(default="cache", description="Collection for caching results")


class AgentConfig(BaseModel):
    """Configuration class for Self-RAG agent document retrieval counts."""
    
    # Multi-collection search limits
    multi_collection_search_limit: int = Field(default=100, description="Number of documents to retrieve in multi-collection search")
    
    # Real-time search limits (ExtractionBasedRetriever)
    realtime_search_limit: int = Field(default=300, description="Number of documents to retrieve in real-time extraction-based search")
    
    # Single collection search limits
    single_collection_search_limit: int = Field(default=25, description="Number of documents to retrieve in single collection search")
    
    # Document processing limits
    max_selected_documents: int = Field(default=300, description="Maximum number of documents to process for answer generation")
    
    # Citation and display limits
    max_citation_documents: int = Field(default=5, description="Maximum number of documents to show in citations")
    max_log_documents: int = Field(default=5, description="Maximum number of documents to log for debugging")
    
    # SFDC query limits
    sfdc_query_limit: int = Field(default=30, description="Maximum number of results from SFDC queries")
    
    # Relevance analysis limits
    relevance_analysis_limit: int = Field(default=300, description="Maximum number of documents to analyze for relevance")
    
    # Recursion and retry limits
    max_recursion_limit: int = Field(default=2, description="Maximum number of query refinement iterations")
    
    # Sleep delays (in seconds)
    llm_request_delay: float = Field(default=0.5, description="Delay between LLM requests to avoid rate limiting")


class DataSourceAgentConfig:
    """Factory class to get appropriate configuration based on document source."""
    
    # Configuration presets for different document sources
    _configs: Dict[DocumentSource, AgentConfig] = {
        DocumentSource.GONG: AgentConfig(
            multi_collection_search_limit=250,  # Increased
            realtime_search_limit=500,          # Increased
            single_collection_search_limit=100, # Increased
            max_selected_documents=250,         # Increased
            max_citation_documents=8,
            max_log_documents=3,
            sfdc_query_limit=3,
            relevance_analysis_limit=250,       # Increased
            max_recursion_limit=1,
            llm_request_delay=0.3
        ),
        
        DocumentSource.SALESFORCE: AgentConfig(
            multi_collection_search_limit=75,   # Lower for SFDC as data is more structured
            realtime_search_limit=300,          # Moderate for SFDC-related searches
            single_collection_search_limit=100,  # Lower for structured data
            max_selected_documents=200,         # Process fewer documents for SFDC
            max_citation_documents=5,           # Standard citation limit
            max_log_documents=5,                # Standard logging limit
            sfdc_query_limit=30,                # Higher for SFDC queries
            relevance_analysis_limit=200,       # Analyze fewer for structured data
            max_recursion_limit=2,              # Standard recursion limit
            llm_request_delay=0.5               # Standard delay
        ),
        
        DocumentSource.CSOD: AgentConfig(
            multi_collection_search_limit=100,  # Moderate for CSOD as data is structured
            realtime_search_limit=300,          # Moderate for CSOD-related searches
            single_collection_search_limit=300,  # Reduced from 500 to 300 to prevent context issues
            max_selected_documents=200,         # Reduced from 250 to 200 to prevent context issues
            max_citation_documents=5,           # Standard citation limit
            max_log_documents=5,                # Standard logging limit
            sfdc_query_limit=5,                 # Standard SFDC limit
            relevance_analysis_limit=300,       # Standard relevance analysis limit
            max_recursion_limit=2,              # Standard recursion limit
            llm_request_delay=0.5               # Standard delay
        ),
        
        DocumentSource.GENERIC: AgentConfig(
            multi_collection_search_limit=100,  # Default values
            realtime_search_limit=300,          # Default values
            single_collection_search_limit=25,  # Default values
            max_selected_documents=300,         # Default values
            max_citation_documents=5,           # Default values
            max_log_documents=5,                # Default values
            sfdc_query_limit=5,                 # Default values
            relevance_analysis_limit=300,       # Default values
            max_recursion_limit=2,              # Default values
            llm_request_delay=0.5               # Default values
        ),
        
        DocumentSource.PDF: AgentConfig(
            multi_collection_search_limit=80,   # Moderate for PDF documents
            realtime_search_limit=250,          # Moderate search limit
            single_collection_search_limit=20,  # Lower for document-based content
            max_selected_documents=250,         # Process moderate number of documents
            max_citation_documents=5,           # Standard citation limit
            max_log_documents=5,                # Standard logging limit
            sfdc_query_limit=5,                 # Standard SFDC limit
            relevance_analysis_limit=250,       # Moderate analysis limit
            max_recursion_limit=2,              # Standard recursion limit
            llm_request_delay=0.5               # Standard delay
        ),
        
        DocumentSource.SLACK: AgentConfig(
            multi_collection_search_limit=120,  # Higher for Slack conversations
            realtime_search_limit=280,          # High for conversational content
            single_collection_search_limit=25,  # Standard for conversational data
            max_selected_documents=280,         # Process more for conversation analysis
            max_citation_documents=6,           # Slightly higher for conversations
            max_log_documents=5,                # Standard logging limit
            sfdc_query_limit=5,                 # Standard SFDC limit
            relevance_analysis_limit=280,       # Higher analysis for conversations
            max_recursion_limit=2,              # Standard recursion limit
            llm_request_delay=0.5               # Standard delay
        )
    }
    
    @classmethod
    def get_config(cls, document_source: DocumentSource) -> AgentConfig:
        """
        Get the appropriate configuration for the given document source.
        
        Args:
            document_source: The document source type
            
        Returns:
            AgentConfig: Configuration object with appropriate limits
        """
        return cls._configs.get(document_source, cls._configs[DocumentSource.GENERIC])
    
    @classmethod
    def get_config_for_source_type(cls, source_type: str) -> AgentConfig:
        """
        Get configuration based on source type string.
        
        Args:
            source_type: String representation of source type
            
        Returns:
            AgentConfig: Configuration object with appropriate limits
        """
        # Map common source type strings to DocumentSource enum
        source_mapping = {
            "gong_transcript": DocumentSource.GONG,
            "gong": DocumentSource.GONG,
            "salesforce": DocumentSource.SALESFORCE,
            "sfdc": DocumentSource.SALESFORCE,
            "csod": DocumentSource.CSOD,  # Add CSOD mapping
            "cornerstone": DocumentSource.CSOD,  # Add alternative name
            "generic": DocumentSource.GENERIC,
            "pdf": DocumentSource.PDF,
            "slack": DocumentSource.SLACK,
            "documents": DocumentSource.GENERIC,
            "extensive_call": DocumentSource.EXTENSIVE_CALL,
            "docs_documentation": DocumentSource.DOCS_DOCUMENTATION
        }
        
        document_source = source_mapping.get(source_type.lower(), DocumentSource.GENERIC)
        return cls.get_config(document_source)
    
    @classmethod
    def get_config_for_topics(cls, topics: list) -> AgentConfig:
        """
        Get configuration based on the topics being searched.
        
        Args:
            topics: List of topics/categories
            
        Returns:
            AgentConfig: Configuration object with appropriate limits
        """
        if not topics:
            return cls.get_config(DocumentSource.GENERIC)
        
        # Analyze topics to determine best configuration
        gong_keywords = ["call", "meeting", "conversation", "transcript", "gong"]
        sfdc_keywords = ["opportunity", "account", "deal", "pipeline", "salesforce"]
        csod_keywords = ["learning", "training", "course", "cornerstone", "csod", "organizational unit"]
        slack_keywords = ["slack", "message", "channel", "thread"]
        pdf_keywords = ["document", "pdf", "contract", "agreement"]
        
        topics_str = " ".join(topics).lower()
        
        has_gong = any(keyword in topics_str for keyword in gong_keywords)
        has_sfdc = any(keyword in topics_str for keyword in sfdc_keywords)
        has_csod = any(keyword in topics_str for keyword in csod_keywords)
        has_slack = any(keyword in topics_str for keyword in slack_keywords)
        has_pdf = any(keyword in topics_str for keyword in pdf_keywords)
        
        # Priority order: CSOD > Gong > SFDC > Slack > PDF > Generic
        if has_csod:
            return cls.get_config(DocumentSource.CSOD)
        elif has_gong:
            return cls.get_config(DocumentSource.GONG)
        elif has_sfdc:
            return cls.get_config(DocumentSource.SALESFORCE)
        elif has_slack:
            return cls.get_config(DocumentSource.SLACK)
        elif has_pdf:
            return cls.get_config(DocumentSource.PDF)
        else:
            return cls.get_config(DocumentSource.GENERIC)


# Global ChromaDB collection names
chroma_collections = ChromaDBCollections()


# Convenience function for easy access
def get_agent_config(
    source_type: Optional[str] = None, 
    topics: Optional[list] = None, 
    document_source: Optional[DocumentSource] = None
) -> AgentConfig:
    """
    Get the appropriate agent configuration based on various inputs.
    
    Args:
        source_type: String representation of source type
        topics: List of topics/categories being searched
        document_source: Direct DocumentSource enum value
        
    Returns:
        AgentConfig: Configuration object with appropriate limits
    """
    if document_source:
        return DataSourceAgentConfig.get_config(document_source)
    elif topics:
        return DataSourceAgentConfig.get_config_for_topics(topics)
    elif source_type:
        return DataSourceAgentConfig.get_config_for_source_type(source_type)
    else:
        return DataSourceAgentConfig.get_config(DocumentSource.GENERIC)


class ModelType(Enum):
    """Enum for supported LLM model types."""

    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GEMINI_PRO = "gemini-2.5-pro-preview-06-05"
    GEMINI_FLASH = "gemini-2.0-flash" # "gemini-2.5-flash-preview-05-20"


class ModelProvider(Enum):
    """Enum for supported LLM providers."""

    OPENAI = "openai"
    GOOGLE = "google"


class ModelConfig(BaseModel):
    """Configuration for LLM model selection."""

    # Model selection
    provider: ModelProvider = Field(default=ModelProvider.OPENAI, description="LLM provider")
    model_type: ModelType = Field(default=ModelType.GPT_4O, description="LLM model type")

    # Model parameters
    temperature: float = Field(default=0.0, description="Temperature parameter for the LLM")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens for the LLM response")

    class Config:
        use_enum_values = True


class ModelTaskAssignment(BaseModel):
    """Assignment of different models to different tasks."""

    # Core tasks
    splitter: ModelConfig = Field(
        default=ModelConfig(provider=ModelProvider.GOOGLE, model_type=ModelType.GEMINI_PRO),
        description="Model for query splitting"
    )
    answer_generation: ModelConfig = Field(
        default=ModelConfig(provider=ModelProvider.GOOGLE, model_type=ModelType.GEMINI_PRO),
        description="Model for generating final answers"
    )

    # SQL Stat Retriever specific model
    sql_stat_retriever: ModelConfig = Field(
        default=ModelConfig(provider=ModelProvider.OPENAI, model_type=ModelType.GPT_4O_MINI),
        description="Model for SQL stat retriever tasks"
    )

    # Default model for other tasks
    default: ModelConfig = Field(
        default=ModelConfig(provider=ModelProvider.OPENAI, model_type=ModelType.GPT_4O),
        description="Default model for other tasks"
    )

# Add the ModelTaskAssignment to the bottom of the file along with other initialized objects
model_task_assignment = ModelTaskAssignment()
