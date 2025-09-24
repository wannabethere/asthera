"""
Function Retrieval Service

This service provides a simple interface for ML agents to retrieve
function definitions and metadata from the ChromaDB registry.
"""

from typing import Dict, List, Any, Optional, Union
import json
from datetime import datetime

import chromadb
from chromadb.config import Settings

from app.tools.mltools.registry.function_search_interface import FunctionSearchInterface, SearchResult
from app.tools.mltools.registry.enhanced_function_retrieval_service import EnhancedFunctionRetrievalService


class FunctionRetrievalService:
    """Service for retrieving ML function definitions for agents."""
    
    def __init__(self, retrieval_helper, llm_model: str = "gpt-3.5-turbo"):
        """Initialize the retrieval service.
        
        Args:
            retrieval_helper: RetrievalHelper instance for accessing ChromaDB stores
            llm_model: LLM model to use for semantic matching
        """
        self.retrieval_helper = retrieval_helper
        self.llm_model = llm_model
        self.enhanced_function_service = None
        self._initialize_enhanced_service()
    
    def _initialize_enhanced_service(self):
        """Initialize the enhanced function retrieval service."""
        try:
            self.enhanced_function_service = EnhancedFunctionRetrievalService(
                retrieval_helper=self.retrieval_helper,
                llm_model=self.llm_model
            )
        except Exception as e:
            print(f"Warning: Could not initialize enhanced function service: {e}")
            self.enhanced_function_service = None
    
    
    async def search_functions_for_agent(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for functions with agent-specific context.
        
        Args:
            query: Search query from the agent
            context: Additional context about the agent's task
            max_results: Maximum number of results to return
            
        Returns:
            List of function information dictionaries
        """
        if not self.enhanced_function_service:
            return []
        
        try:
            # Use the retrieval helper to get function definitions
            function_result = await self.retrieval_helper.get_function_definition_by_query(
                query=query,
                similarity_threshold=0.6,
                top_k=max_results
            )
            
            if not function_result or function_result.get("error"):
                return []
            
            # Get the function definition
            function_def = function_result.get("function_definition", {})
            if not function_def:
                return []
            
            # Convert to agent-friendly format
            agent_result = {
                "function_name": function_def.get("function_name", ""),
                "module": function_def.get("module", ""),
                "category": function_def.get("category", ""),
                "description": function_def.get("description", ""),
                "relevance_score": function_result.get("score", 0.0),
                "complexity": function_def.get("complexity", "unknown"),
                "parameters": self._format_parameters_for_agent(function_def.get("parameters", {})),
                "examples": function_def.get("examples", []),
                "usage_patterns": function_def.get("usage_patterns", []),
                "data_requirements": function_def.get("data_requirements", []),
                "output_description": function_def.get("output_description", ""),
                "tags": function_def.get("tags", [])
            }
            
            return [agent_result]
            
        except Exception as e:
            print(f"Error searching functions: {e}")
            return []
    
    def _enhance_query_with_context(self, query: str, context: Optional[Dict[str, Any]]) -> str:
        """Enhance search query with agent context.
        
        Args:
            query: Original query
            context: Agent context
            
        Returns:
            Enhanced query string
        """
        if not context:
            return query
        
        enhanced_parts = [query]
        
        # Add context-based enhancements
        if context.get('data_columns'):
            columns = context['data_columns']
            if any('date' in col.lower() or 'time' in col.lower() for col in columns):
                enhanced_parts.append("time series")
            if any('user' in col.lower() or 'customer' in col.lower() for col in columns):
                enhanced_parts.append("cohort analysis")
            if any('value' in col.lower() or 'amount' in col.lower() for col in columns):
                enhanced_parts.append("aggregation statistics")
        
        if context.get('task_type'):
            task_type = context['task_type'].lower()
            if 'anomaly' in task_type:
                enhanced_parts.append("anomaly detection")
            elif 'forecast' in task_type:
                enhanced_parts.append("forecasting time series")
            elif 'segment' in task_type:
                enhanced_parts.append("segmentation clustering")
            elif 'cohort' in task_type:
                enhanced_parts.append("cohort retention analysis")
        
        if context.get('complexity_level'):
            complexity = context['complexity_level'].lower()
            if complexity in ['simple', 'basic']:
                enhanced_parts.append("basic statistics mean sum count")
            elif complexity in ['advanced', 'complex']:
                enhanced_parts.append("advanced statistical analysis")
        
        return ' '.join(enhanced_parts)
    
    def _format_parameters_for_agent(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Format parameters in a way that's useful for agents.
        
        Args:
            parameters: Function parameters
            
        Returns:
            Formatted parameters dictionary
        """
        formatted = {}
        for param_name, param_info in parameters.items():
            formatted[param_name] = {
                "type": param_info.get('type', 'Any'),
                "required": param_info.get('required', False),
                "default": param_info.get('default'),
                "description": f"Parameter of type {param_info.get('type', 'Any')}"
            }
        return formatted
    
    async def get_function_by_name(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific function.
        
        Args:
            function_name: Name of the function
            
        Returns:
            Function information dictionary or None
        """
        if not self.retrieval_helper:
            return None
        
        try:
            function_result = await self.retrieval_helper.get_function_definition(
                function_name=function_name,
                similarity_threshold=0.7,
                top_k=1
            )
            
            if not function_result or function_result.get("error"):
                return None
            
            function_def = function_result.get("function_definition", {})
            if not function_def:
                return None
            
            return {
                "function_name": function_def.get("function_name", ""),
                "module": function_def.get("module", ""),
                "category": function_def.get("category", ""),
                "description": function_def.get("description", ""),
                "complexity": function_def.get("complexity", "unknown"),
                "parameters": self._format_parameters_for_agent(function_def.get("parameters", {})),
                "return_type": function_def.get("return_type", ""),
                "examples": function_def.get("examples", []),
                "usage_patterns": function_def.get("usage_patterns", []),
                "data_requirements": function_def.get("data_requirements", []),
                "output_description": function_def.get("output_description", ""),
                "tags": function_def.get("tags", []),
                "dependencies": function_def.get("dependencies", []),
                "docstring": function_def.get("docstring", "")
            }
            
        except Exception as e:
            print(f"Error getting function by name: {e}")
            return None
    
    async def get_functions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all functions in a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of function information dictionaries
        """
        # Use search with category context
        return await self.search_functions_for_agent(
            query=f"category:{category}",
            max_results=20
        )
    
    def get_available_categories(self) -> List[str]:
        """Get list of available function categories.
        
        Returns:
            List of category names
        """
        # Return common categories - in a real implementation, this could be
        # retrieved from the ChromaDB metadata
        return [
            "statistics", "time_series", "cohort_analysis", "risk_analysis",
            "segmentation", "funnel_analysis", "anomaly_detection", "forecasting",
            "clustering", "classification", "regression", "data_processing"
        ]
    
    async def get_function_recommendations(
        self, 
        function_name: str, 
        max_recommendations: int = 5
    ) -> List[Dict[str, Any]]:
        """Get function recommendations based on a given function.
        
        Args:
            function_name: Name of the function to get recommendations for
            max_recommendations: Maximum number of recommendations
            
        Returns:
            List of recommended function information
        """
        # Use the function name as a search query to find similar functions
        return await self.search_functions_for_agent(
            query=function_name,
            max_results=max_recommendations
        )
    
    async def search_functions_by_use_case(self, use_case: str) -> List[Dict[str, Any]]:
        """Search for functions suitable for a specific use case.
        
        Args:
            use_case: Description of the use case
            
        Returns:
            List of suitable function information
        """
        return await self.search_functions_for_agent(
            query=use_case,
            max_results=10
        )
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get the current status of the service.
        
        Returns:
            Dictionary with service status information
        """
        status = {
            "initialized": self.enhanced_function_service is not None,
            "retrieval_helper_available": self.retrieval_helper is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.enhanced_function_service:
            status.update({
                "enhanced_function_service_available": True,
                "llm_model": self.llm_model
            })
        else:
            status["enhanced_function_service_available"] = False
        
        return status


def create_function_retrieval_service(retrieval_helper, llm_model: str = "gpt-3.5-turbo") -> FunctionRetrievalService:
    """Create a function retrieval service with LLM integration.
    
    Args:
        retrieval_helper: RetrievalHelper instance for accessing ChromaDB stores
        llm_model: LLM model to use for semantic matching
        
    Returns:
        Initialized FunctionRetrievalService
    """
    return FunctionRetrievalService(retrieval_helper, llm_model=llm_model)


if __name__ == "__main__":
    # Example usage
    print("=== Function Retrieval Service Example ===\n")
    
    # Note: This requires a RetrievalHelper instance
    print("This service requires a RetrievalHelper instance to be passed in.")
    print("Example usage:")
    print("  from app.agents.retrieval.retrieval_helper import RetrievalHelper")
    print("  from app.tools.mltools.registry.function_retrieval_service import create_function_retrieval_service")
    print("")
    print("  retrieval_helper = RetrievalHelper()")
    print("  service = create_function_retrieval_service(retrieval_helper)")
    print("")
    print("  # Then use the service:")
    print("  results = await service.search_functions_for_agent('anomaly detection')")
    print("")
    print("Please run the initialization script first to populate ChromaDB with function data.")
