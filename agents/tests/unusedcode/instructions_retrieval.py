from typing import Dict, Any, Optional
import logging
from app.agents.pipelines.base import AgentPipeline
from app.storage.documents import DocumentChromaStore
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from langchain_openai import ChatOpenAI

logger = logging.getLogger("lexy-ai-service")

class InstructionsRetrievalPipeline(AgentPipeline):
    """Pipeline for retrieving instructions"""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        document_store: DocumentChromaStore,
        llm: ChatOpenAI,
        retrieval_helper: RetrievalHelper
    ):
        """Initialize the instructions retrieval pipeline
        
        Args:
            name: Pipeline name
            version: Pipeline version
            description: Pipeline description
            document_store: Document store instance
            llm: Language model instance
            retrieval_helper: Retrieval helper instance
        """
        super().__init__(
            name=name,
            version=version,
            description=description,
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store=document_store
        )
        self._configuration = {
            "similarity_threshold": 0.7,
            "top_k": 10
        }
        self._metrics = {}
        
    @property
    def is_initialized(self) -> bool:
        """Check if the pipeline has been initialized"""
        return self._initialized
        
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration"""
        return self._configuration.copy()
        
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update the configuration
        
        Args:
            config: New configuration parameters
        """
        self._configuration.update(config)
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return self._metrics.copy()
        
    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        self._metrics.clear()
        
    async def run(self, query: str, project_id: str, **kwargs) -> Dict[str, Any]:
        """Run the instructions retrieval pipeline
        
        Args:
            query: User query
            project_id: Project identifier
            **kwargs: Additional arguments
            
        Returns:
            Pipeline results containing instructions
        """
        if not self._initialized:
            raise RuntimeError("Pipeline must be initialized before running")
            
        try:
            # Get instructions using retrieval helper
            result = await self._retrieval_helper.get_instructions(
                query=query,
                project_id=project_id,
                similarity_threshold=self._configuration["similarity_threshold"],
                top_k=self._configuration["top_k"]
            )
            
            # Update metrics
            self._metrics.update({
                "last_query": query,
                "last_project_id": project_id,
                "results_count": len(result.get("instructions", [])),
                "success": True
            })
            
            return {
                "formatted_output": {
                    "documents": result.get("instructions", [])
                },
                "metadata": {
                    "total_instructions": result.get("total_instructions", 0),
                    "project_id": project_id,
                    "query": query
                }
            }
            
        except Exception as e:
            logger.error(f"Error in instructions retrieval pipeline: {str(e)}")
            self._metrics.update({
                "last_error": str(e),
                "success": False
            })
            raise 