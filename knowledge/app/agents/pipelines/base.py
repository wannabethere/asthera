"""
Base Pipeline class for extraction pipelines
Follows the pattern from agents/app/agents/pipelines/base.py
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ExtractionPipeline(ABC):
    """Base class for all extraction pipelines"""
    
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
        self._name = name
        self._version = version
        self._description = description
        self._llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self._is_initialized = False
        self._configuration = kwargs.get("configuration", {})
    
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
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        return self._configuration.copy()
    
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update the pipeline configuration"""
        self._configuration.update(config)
    
    @abstractmethod
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline with any required resources"""
        self._is_initialized = True
    
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
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up any resources used by the pipeline"""
        pass
    
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

