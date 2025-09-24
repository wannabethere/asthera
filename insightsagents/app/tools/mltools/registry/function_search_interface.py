"""
Function Search Interface

This module provides a high-level interface for searching and retrieving
ML tool function definitions from the ChromaDB registry.
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import json
from datetime import datetime

from app.tools.mltools.registry.function_registry import MLFunctionRegistry, FunctionMetadata
from app.tools.mltools.registry.llm_metadata_generator import create_llm_metadata_generator, create_dynamic_function_matcher
import chromadb
from chromadb.config import Settings


@dataclass
class SearchResult:
    """Structured search result for function queries."""
    function_name: str
    module: str
    category: str
    description: str
    relevance_score: float
    complexity: str
    tags: List[str]
    parameters: Dict[str, Any]
    examples: List[str]
    usage_patterns: List[str]
    data_requirements: List[str]
    output_description: str
    source_code: str
    docstring: str


class FunctionSearchInterface:
    """High-level interface for searching ML tool functions."""
    
    def __init__(self, registry: MLFunctionRegistry, llm_model: str = "gpt-3.5-turbo"):
        """Initialize the search interface.
        
        Args:
            registry: Initialized MLFunctionRegistry instance
            llm_model: LLM model to use for semantic matching
        """
        self.registry = registry
        self.search_history = []
        
        # Initialize LLM components
        self.llm_metadata_generator = create_llm_metadata_generator(llm_model)
        self.dynamic_matcher = create_dynamic_function_matcher(self.llm_metadata_generator)
        
        # Register functions with dynamic matcher
        self._register_functions_with_matcher()
    
    def _register_functions_with_matcher(self):
        """Register all functions with the dynamic matcher."""
        all_functions = self.registry.get_all_functions()
        function_list = []
        
        for func_metadata in all_functions:
            function_dict = {
                "name": func_metadata.name,
                "description": func_metadata.description,
                "category": func_metadata.category,
                "use_cases": getattr(func_metadata, 'use_cases', []),
                "tags": func_metadata.tags,
                "keywords": getattr(func_metadata, 'keywords', [])
            }
            function_list.append(function_dict)
        
        self.dynamic_matcher.register_functions(function_list)
    
    def search_functions(
        self, 
        query: str, 
        n_results: int = 5,
        category: Optional[str] = None,
        complexity: Optional[str] = None,
        tags: Optional[List[str]] = None,
        include_source_code: bool = False
    ) -> List[SearchResult]:
        """Search for functions with advanced filtering.
        
        Args:
            query: Search query
            n_results: Number of results to return
            category: Filter by category
            complexity: Filter by complexity level
            tags: Filter by tags
            include_source_code: Whether to include source code in results
            
        Returns:
            List of SearchResult objects
        """
        # Perform semantic search
        search_results = self.registry.search_functions(
            query=query,
            n_results=n_results * 2,  # Get more results for filtering
            category=category
        )
        
        # Convert to SearchResult objects
        results = []
        for result in search_results:
            metadata = result['metadata']
            content = result.get('content', '')
            
            # Apply additional filters
            if complexity and metadata.get('complexity') != complexity:
                continue
            
            if tags:
                result_tags = metadata.get('tags', '').split(',')
                if not any(tag.strip() in result_tags for tag in tags):
                    continue
            
            # Get full function metadata
            function_metadata = self.registry.get_function_by_name(metadata['function_name'])
            if not function_metadata:
                continue
            
            search_result = SearchResult(
                function_name=metadata['function_name'],
                module=metadata['module'],
                category=metadata['category'],
                description=function_metadata.description,
                relevance_score=result.get('score', 0.0),
                complexity=metadata.get('complexity', 'unknown'),
                tags=function_metadata.tags,
                parameters=function_metadata.parameters,
                examples=function_metadata.examples,
                usage_patterns=function_metadata.usage_patterns,
                data_requirements=function_metadata.data_requirements,
                output_description=function_metadata.output_description,
                source_code=function_metadata.source_code if include_source_code else "",
                docstring=function_metadata.docstring
            )
            
            results.append(search_result)
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Limit results
        results = results[:n_results]
        
        # Record search history
        self.search_history.append({
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'results_count': len(results),
            'filters': {
                'category': category,
                'complexity': complexity,
                'tags': tags
            }
        })
        
        return results
    
    def find_functions_by_use_case(self, use_case: str) -> List[SearchResult]:
        """Find functions suitable for a specific use case using LLM.
        
        Args:
            use_case: Description of the use case
            
        Returns:
            List of relevant functions
        """
        # Use dynamic matcher for LLM-powered use case matching
        matches = self.dynamic_matcher.find_functions_by_use_case(use_case, n_results=10)
        
        # Convert to SearchResult objects
        results = []
        for match in matches:
            function_name = match.get("function_name", "")
            function_metadata = self.registry.get_function_by_name(function_name)
            
            if function_metadata:
                search_result = SearchResult(
                    function_name=function_name,
                    module=function_metadata.module,
                    category=function_metadata.category,
                    description=function_metadata.description,
                    relevance_score=match.get("relevance_score", 0.0),
                    complexity=getattr(function_metadata, 'complexity', 'unknown'),
                    tags=function_metadata.tags,
                    parameters=function_metadata.parameters,
                    examples=getattr(function_metadata, 'examples', []),
                    usage_patterns=getattr(function_metadata, 'usage_patterns', []),
                    data_requirements=getattr(function_metadata, 'data_requirements', []),
                    output_description=getattr(function_metadata, 'output_description', ''),
                    source_code=getattr(function_metadata, 'source_code', ''),
                    docstring=function_metadata.docstring
                )
                results.append(search_result)
        
        return results
    
    def get_function_recommendations(self, function_name: str, n_recommendations: int = 5) -> List[SearchResult]:
        """Get function recommendations based on a given function.
        
        Args:
            function_name: Name of the function to get recommendations for
            n_recommendations: Number of recommendations to return
            
        Returns:
            List of recommended functions
        """
        # Get the function metadata
        function_metadata = self.registry.get_function_by_name(function_name)
        if not function_metadata:
            return []
        
        # Search for similar functions
        query_parts = [
            function_metadata.category,
            function_metadata.complexity,
            ' '.join(function_metadata.tags[:3])
        ]
        
        query = ' '.join(filter(None, query_parts))
        
        # Get recommendations excluding the original function
        results = self.search_functions(query, n_results=n_recommendations + 1)
        
        # Filter out the original function
        recommendations = [r for r in results if r.function_name != function_name]
        
        return recommendations[:n_recommendations]
    
    def get_functions_by_data_requirements(self, data_columns: List[str]) -> List[SearchResult]:
        """Find functions that work with specific data columns using LLM.
        
        Args:
            data_columns: List of available data columns
            
        Returns:
            List of suitable functions
        """
        # Use dynamic matcher for LLM-powered data requirement matching
        matches = self.dynamic_matcher.find_functions_by_data_requirements(data_columns, n_results=10)
        
        # Convert to SearchResult objects
        results = []
        for match in matches:
            function_name = match.get("function_name", "")
            function_metadata = self.registry.get_function_by_name(function_name)
            
            if function_metadata:
                search_result = SearchResult(
                    function_name=function_name,
                    module=function_metadata.module,
                    category=function_metadata.category,
                    description=function_metadata.description,
                    relevance_score=match.get("relevance_score", 0.0),
                    complexity=getattr(function_metadata, 'complexity', 'unknown'),
                    tags=function_metadata.tags,
                    parameters=function_metadata.parameters,
                    examples=getattr(function_metadata, 'examples', []),
                    usage_patterns=getattr(function_metadata, 'usage_patterns', []),
                    data_requirements=getattr(function_metadata, 'data_requirements', []),
                    output_description=getattr(function_metadata, 'output_description', ''),
                    source_code=getattr(function_metadata, 'source_code', ''),
                    docstring=function_metadata.docstring
                )
                results.append(search_result)
        
        return results
    
    def get_function_signature(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed function signature information.
        
        Args:
            function_name: Name of the function
            
        Returns:
            Dictionary with signature information
        """
        function_metadata = self.registry.get_function_by_name(function_name)
        if not function_metadata:
            return None
        
        return {
            'name': function_metadata.name,
            'module': function_metadata.module,
            'parameters': function_metadata.parameters,
            'return_type': function_metadata.return_type,
            'description': function_metadata.description,
            'examples': function_metadata.examples,
            'usage_patterns': function_metadata.usage_patterns,
            'data_requirements': function_metadata.data_requirements,
            'output_description': function_metadata.output_description
        }
    
    def get_available_categories(self) -> List[Dict[str, str]]:
        """Get all available function categories.
        
        Returns:
            List of category information
        """
        categories = []
        for category, info in self.registry.categories.items():
            categories.append({
                'name': category,
                'description': info['description'],
                'keywords': info['keywords']
            })
        return categories
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get search statistics and history.
        
        Returns:
            Dictionary with search statistics
        """
        if not self.search_history:
            return {'total_searches': 0, 'recent_searches': []}
        
        # Get recent searches
        recent_searches = self.search_history[-10:]
        
        # Count searches by category
        category_counts = {}
        for search in self.search_history:
            category = search['filters'].get('category', 'all')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            'total_searches': len(self.search_history),
            'recent_searches': recent_searches,
            'searches_by_category': category_counts,
            'most_common_queries': self._get_most_common_queries()
        }
    
    def _get_most_common_queries(self) -> List[Dict[str, Any]]:
        """Get most common search queries.
        
        Returns:
            List of common queries with counts
        """
        query_counts = {}
        for search in self.search_history:
            query = search['query']
            query_counts[query] = query_counts.get(query, 0) + 1
        
        # Sort by count and return top 5
        sorted_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)
        return [{'query': query, 'count': count} for query, count in sorted_queries[:5]]
    
    def export_search_results(self, results: List[SearchResult], format: str = 'json') -> str:
        """Export search results to various formats.
        
        Args:
            results: List of SearchResult objects
            format: Export format ('json', 'csv', 'markdown')
            
        Returns:
            Exported data as string
        """
        if format == 'json':
            data = []
            for result in results:
                data.append({
                    'function_name': result.function_name,
                    'module': result.module,
                    'category': result.category,
                    'description': result.description,
                    'relevance_score': result.relevance_score,
                    'complexity': result.complexity,
                    'tags': result.tags,
                    'parameters': result.parameters,
                    'examples': result.examples,
                    'usage_patterns': result.usage_patterns,
                    'data_requirements': result.data_requirements,
                    'output_description': result.output_description
                })
            return json.dumps(data, indent=2)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'function_name', 'module', 'category', 'description', 
                'relevance_score', 'complexity', 'tags', 'parameters_count',
                'examples_count', 'data_requirements'
            ])
            
            # Write data
            for result in results:
                writer.writerow([
                    result.function_name,
                    result.module,
                    result.category,
                    result.description,
                    result.relevance_score,
                    result.complexity,
                    ','.join(result.tags),
                    len(result.parameters),
                    len(result.examples),
                    ','.join(result.data_requirements)
                ])
            
            return output.getvalue()
        
        elif format == 'markdown':
            markdown = "# Function Search Results\n\n"
            
            for i, result in enumerate(results, 1):
                markdown += f"## {i}. {result.function_name}\n\n"
                markdown += f"**Module:** {result.module}  \n"
                markdown += f"**Category:** {result.category}  \n"
                markdown += f"**Complexity:** {result.complexity}  \n"
                markdown += f"**Relevance Score:** {result.relevance_score:.3f}  \n\n"
                
                markdown += f"**Description:** {result.description}\n\n"
                
                if result.tags:
                    markdown += f"**Tags:** {', '.join(result.tags)}\n\n"
                
                if result.parameters:
                    markdown += "**Parameters:**\n"
                    for param_name, param_info in result.parameters.items():
                        required = "Required" if param_info['required'] else "Optional"
                        markdown += f"- `{param_name}`: {param_info['type']} ({required})\n"
                    markdown += "\n"
                
                if result.examples:
                    markdown += "**Examples:**\n"
                    for example in result.examples:
                        markdown += f"```python\n{example}\n```\n"
                    markdown += "\n"
                
                if result.data_requirements:
                    markdown += f"**Data Requirements:** {', '.join(result.data_requirements)}\n\n"
                
                markdown += "---\n\n"
            
            return markdown
        
        else:
            raise ValueError(f"Unsupported format: {format}")


def create_search_interface(chroma_client: chromadb.PersistentClient) -> FunctionSearchInterface:
    """Create a function search interface with initialized registry.
    
    Args:
        chroma_client: ChromaDB persistent client
        
    Returns:
        Initialized FunctionSearchInterface
    """
    from .function_registry import initialize_function_registry
    
    registry = initialize_function_registry(chroma_client)
    return FunctionSearchInterface(registry)


if __name__ == "__main__":
    # Example usage
    import chromadb
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path="./chroma_db")
    
    # Create search interface
    search_interface = create_search_interface(client)
    
    # Example searches
    print("=== Function Search Examples ===\n")
    
    # Search for anomaly detection functions
    results = search_interface.search_functions("detect anomalies in time series data", n_results=3)
    print("Anomaly Detection Functions:")
    for result in results:
        print(f"- {result.function_name} ({result.category}): {result.description}")
    
    print("\n" + "="*50 + "\n")
    
    # Find functions by use case
    results = search_interface.find_functions_by_use_case("customer segmentation")
    print("Customer Segmentation Functions:")
    for result in results:
        print(f"- {result.function_name} ({result.complexity}): {result.description}")
    
    print("\n" + "="*50 + "\n")
    
    # Get function recommendations
    if results:
        recommendations = search_interface.get_function_recommendations(results[0].function_name)
        print(f"Recommendations for {results[0].function_name}:")
        for rec in recommendations:
            print(f"- {rec.function_name}: {rec.description}")
    
    print("\n" + "="*50 + "\n")
    
    # Get search statistics
    stats = search_interface.get_search_statistics()
    print(f"Search Statistics:")
    print(f"Total searches: {stats['total_searches']}")
    print(f"Categories: {list(stats['searches_by_category'].keys())}")
