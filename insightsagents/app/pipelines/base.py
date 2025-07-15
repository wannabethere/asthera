from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Awaitable, List, TYPE_CHECKING
import asyncio
import logging
from langchain_openai import ChatOpenAI
from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider

if TYPE_CHECKING:
    from app.agents.retrieval.retrieval_helper import RetrievalHelper

logger = logging.getLogger("lexy-ai-service")

class Pipeline(ABC):
    """Base class for all pipeline implementations"""
    
    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the pipeline with the given parameters
        
        Args:
            **kwargs: Pipeline-specific parameters
            
        Returns:
            Dict containing the pipeline results
        """
        pass
    
    @abstractmethod
    async def initialize(self, **kwargs) -> None:
        """
        Initialize the pipeline with any required resources
        
        Args:
            **kwargs: Initialization parameters
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up any resources used by the pipeline"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of the pipeline"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Get the version of the pipeline"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the description of the pipeline"""
        pass
    
    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if the pipeline has been initialized"""
        pass
    
    @abstractmethod
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        pass
    
    @abstractmethod
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """
        Update the pipeline configuration
        
        Args:
            config: New configuration parameters
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the pipeline"""
        pass
    
    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset the pipeline's performance metrics"""
        pass 




class AgentPipeline(ABC):
    """Base class for all agent pipelines"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: Optional["RetrievalHelper"] = None,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None
    ):
        """Initialize the pipeline
        
        Args:
            name: Pipeline name
            version: Pipeline version
            description: Pipeline description
            llm: Language model instance
            retrieval_helper: Optional retrieval helper instance
            document_store_provider: Optional document store provider instance
        """
        self.name = name
        self.version = version
        self.description = description
        self._llm = llm
        self._retrieval_helper = retrieval_helper
        self._document_store_provider = document_store_provider
        self._initialized = False
        self.engine = engine
        
    async def initialize(self) -> None:
        """Initialize the pipeline"""
        if self._initialized:
            return
            
        self._initialized = True
        logger.info(f"Pipeline {self.name} initialized successfully")
        
    async def cleanup(self) -> None:
        """Clean up the pipeline"""
        if not self._initialized:
            return
            
        self._initialized = False
        logger.info(f"Pipeline {self.name} cleaned up successfully")
        
    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the pipeline
        
        Args:
            **kwargs: Pipeline-specific arguments
            
        Returns:
            Pipeline results
        """
        pass
        
    def get_name(self) -> str:
        """Get pipeline name"""
        return self.name
        
    def get_version(self) -> str:
        """Get pipeline version"""
        return self.version
        
    def get_description(self) -> str:
        """Get pipeline description"""
        return self.description
    
    @property
    def is_initialized(self) -> bool:
        """Check if the pipeline has been initialized"""
        return self._initialized
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        pass
    
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """
        Update the pipeline configuration
        
        Args:
            config: New configuration parameters
        """
        pass
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the pipeline"""
        pass
    
    def reset_metrics(self) -> None:
        """Reset the pipeline's performance metrics"""
        pass 