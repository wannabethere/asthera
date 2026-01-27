"""
Base Pipeline classes for all pipelines
Follows the pattern from agents/app/agents/pipelines/base.py
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List, TYPE_CHECKING
import logging
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from app.agents.data.retrieval_helper import RetrievalHelper

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """Base class for all pipelines with common functionality
    
    Provides shared functionality for:
    - Initialization and cleanup
    - Configuration management
    - Metrics tracking
    - Name, version, description properties
    - LLM handling
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        **kwargs
    ):
        """Initialize the base pipeline
        
        Args:
            name: Pipeline name
            version: Pipeline version
            description: Pipeline description
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            **kwargs: Additional pipeline-specific parameters
        """
        self._name = name
        self._version = version
        self._description = description
        self._llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self._is_initialized = False
        self._configuration = kwargs.get("configuration", {})
        self._metrics = kwargs.get("metrics", {})
    
    @property
    def name(self) -> str:
        """Get the name of the pipeline"""
        return self._name
    
    @property
    def version(self) -> str:
        """Get the version of the pipeline"""
        return self._version
    
    @property
    def description(self) -> str:
        """Get the description of the pipeline"""
        return self._description
    
    @property
    def is_initialized(self) -> bool:
        """Check if the pipeline has been initialized"""
        return self._is_initialized
    
    @property
    def llm(self) -> ChatOpenAI:
        """Get the LLM instance"""
        return self._llm
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        return self._configuration.copy()
    
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update the pipeline configuration
        
        Args:
            config: New configuration parameters
        """
        self._configuration.update(config)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the pipeline"""
        return self._metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset the pipeline's performance metrics"""
        self._metrics.clear()
    
    @abstractmethod
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline with any required resources
        
        Args:
            **kwargs: Initialization parameters
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up any resources used by the pipeline"""
        pass
    
    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the pipeline
        
        Args:
            **kwargs: Pipeline-specific arguments
            
        Returns:
            Pipeline results
        """
        pass


class ExtractionPipeline(BasePipeline):
    """Base class for all extraction pipelines
    
    Extends BasePipeline with extraction-specific functionality:
    - Batch processing support
    - Input-based run() method signature
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        **kwargs
    ):
        """Initialize the extraction pipeline"""
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            model_name=model_name,
            **kwargs
        )
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline with any required resources"""
        if self._is_initialized:
            return
        self._is_initialized = True
        logger.info(f"Pipeline {self.name} initialized successfully")
    
    @abstractmethod
    async def run(
        self,
        inputs: Any,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the pipeline with the given inputs
        
        Args:
            inputs: Pipeline-specific input data
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional pipeline-specific parameters
            
        Returns:
            Dict containing the pipeline results
        """
        pass
    
    async def cleanup(self) -> None:
        """Clean up any resources used by the pipeline"""
        if not self._is_initialized:
            return
        self._is_initialized = False
        logger.info(f"Pipeline {self.name} cleaned up successfully")
    
    async def run_batch(
        self,
        inputs_list: List[Any],
        max_concurrent: int = 5,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute the pipeline on multiple inputs in batch with controlled concurrency.
        
        Args:
            inputs_list: List of input data for each execution
            max_concurrent: Maximum number of concurrent executions
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional pipeline-specific parameters
            
        Returns:
            List of results for each input
        """
        import asyncio
        
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def process_single(input_data: Any, index: int):
            async with semaphore:
                try:
                    if status_callback:
                        status_callback("processing", {
                            "index": index,
                            "total": len(inputs_list),
                            "status": "processing"
                        })
                    
                    result = await self.run(
                        inputs=input_data,
                        status_callback=status_callback,
                        configuration=configuration,
                        **kwargs
                    )
                    
                    if status_callback:
                        status_callback("completed", {
                            "index": index,
                            "total": len(inputs_list),
                            "status": "completed"
                        })
                    
                    return {
                        "index": index,
                        "success": True,
                        "result": result
                    }
                except Exception as e:
                    logger.error(f"Error processing input {index}: {str(e)}", exc_info=True)
                    if status_callback:
                        status_callback("error", {
                            "index": index,
                            "total": len(inputs_list),
                            "status": "error",
                            "error": str(e)
                        })
                    return {
                        "index": index,
                        "success": False,
                        "error": str(e),
                        "input": input_data
                    }
        
        # Create tasks for all inputs
        tasks = [process_single(input_data, i) for i, input_data in enumerate(inputs_list)]
        
        # Execute all tasks
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for task_result in task_results:
            if isinstance(task_result, Exception):
                results.append({
                    "success": False,
                    "error": str(task_result)
                })
            else:
                results.append(task_result)
        
        # Sort by index
        results.sort(key=lambda x: x.get("index", 0))
        
        return results


class AgentPipeline(BasePipeline):
    """Base class for all agent pipelines
    
    Extends BasePipeline with agent-specific functionality:
    - RetrievalHelper integration
    - Direct run() method signature (no inputs parameter)
    
    Similar to agents/app/agents/pipelines/base.py but adapted for knowledge project.
    Used for pipelines that work with RetrievalHelper and document stores.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        llm: ChatOpenAI,
        retrieval_helper: Optional["RetrievalHelper"] = None,
        **kwargs
    ):
        """Initialize the pipeline
        
        Args:
            name: Pipeline name
            version: Pipeline version
            description: Pipeline description
            llm: Language model instance (required for AgentPipeline)
            retrieval_helper: Optional retrieval helper instance
            **kwargs: Additional pipeline-specific parameters
        """
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,  # LLM is required for AgentPipeline
            **kwargs
        )
        self._retrieval_helper = retrieval_helper
        
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        if self._is_initialized:
            return
        self._is_initialized = True
        logger.info(f"Pipeline {self.name} initialized successfully")
        
    async def cleanup(self) -> None:
        """Clean up the pipeline"""
        if not self._is_initialized:
            return
        self._is_initialized = False
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
        """Get pipeline name (alias for name property)"""
        return self.name
        
    def get_version(self) -> str:
        """Get pipeline version (alias for version property)"""
        return self.version
        
    def get_description(self) -> str:
        """Get pipeline description (alias for description property)"""
        return self.description

