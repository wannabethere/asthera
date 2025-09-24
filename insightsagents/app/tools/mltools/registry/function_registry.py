"""
Function Registry for ML Tools

This module provides a comprehensive registry system for storing and retrieving
ML tool function definitions in ChromaDB using DocumentChromaStore.
"""

import inspect
import ast
import re
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from langchain.schema import Document as LangchainDocument
import chromadb
from chromadb.config import Settings


@dataclass
class FunctionMetadata:
    """Metadata structure for ML tool functions."""
    name: str
    module: str
    description: str
    docstring: str
    parameters: Dict[str, Any]
    return_type: str
    examples: List[str]
    category: str
    tags: List[str]
    source_code: str
    usage_patterns: List[str]
    dependencies: List[str]
    complexity: str  # 'simple', 'intermediate', 'advanced'
    data_requirements: List[str]
    output_description: str


class MLFunctionRegistry:
    """Registry for storing and retrieving ML tool function definitions in ChromaDB."""
    
    def __init__(self, chroma_client: chromadb.PersistentClient, collection_name: str = "ml_function_definitions"):
        """Initialize the function registry.
        
        Args:
            chroma_client: ChromaDB persistent client
            collection_name: Name of the collection to store function definitions
        """
        self.chroma_client = chroma_client
        self.collection_name = collection_name
        self.document_store = DocumentChromaStore(
            persistent_client=chroma_client,
            collection_name=collection_name,
            tf_idf=True
        )
        self.functions_metadata = {}
        self._initialize_categories()
    
    def _initialize_categories(self):
        """Initialize function categories for better organization."""
        self.categories = {
            'anomaly_detection': {
                'description': 'Functions for detecting anomalies in data',
                'keywords': ['anomaly', 'outlier', 'detection', 'statistical', 'contextual', 'collective']
            },
            'time_series': {
                'description': 'Functions for time series analysis and forecasting',
                'keywords': ['time', 'series', 'forecast', 'trend', 'seasonal', 'decomposition']
            },
            'cohort_analysis': {
                'description': 'Functions for cohort and retention analysis',
                'keywords': ['cohort', 'retention', 'conversion', 'lifetime', 'value', 'behavioral']
            },
            'segmentation': {
                'description': 'Functions for customer and data segmentation',
                'keywords': ['segmentation', 'clustering', 'kmeans', 'dbscan', 'hierarchical', 'rule_based']
            },
            'metrics': {
                'description': 'Functions for calculating various metrics and statistics',
                'keywords': ['metrics', 'statistics', 'mean', 'sum', 'count', 'correlation', 'variance']
            },
            'operations': {
                'description': 'Functions for data operations and transformations',
                'keywords': ['operations', 'transform', 'filter', 'group', 'aggregate', 'pivot']
            },
            'moving_averages': {
                'description': 'Functions for moving averages and rolling calculations',
                'keywords': ['moving', 'rolling', 'average', 'window', 'smoothing', 'trend']
            },
            'risk_analysis': {
                'description': 'Functions for risk analysis and financial metrics',
                'keywords': ['risk', 'var', 'cvar', 'volatility', 'monte', 'carlo', 'stress', 'test']
            },
            'funnel_analysis': {
                'description': 'Functions for funnel and conversion analysis',
                'keywords': ['funnel', 'conversion', 'path', 'step', 'user', 'journey']
            },
            'trend_analysis': {
                'description': 'Functions for trend analysis and forecasting',
                'keywords': ['trend', 'growth', 'forecast', 'decomposition', 'statistical', 'comparison']
            },
            'group_aggregation': {
                'description': 'Functions for group-based aggregation operations',
                'keywords': ['group', 'aggregation', 'mean', 'sum', 'count', 'statistical', 'advanced']
            }
        }
    
    def extract_function_metadata(self, func: Callable, module_name: str) -> FunctionMetadata:
        """Extract comprehensive metadata from a function.
        
        Args:
            func: The function to extract metadata from
            module_name: Name of the module containing the function
            
        Returns:
            FunctionMetadata object with extracted information
        """
        # Get basic function information
        name = func.__name__
        docstring = inspect.getdoc(func) or ""
        
        # Parse function signature
        sig = inspect.signature(func)
        parameters = {}
        for param_name, param in sig.parameters.items():
            param_info = {
                'name': param_name,
                'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
                'default': param.default if param.default != inspect.Parameter.empty else None,
                'required': param.default == inspect.Parameter.empty
            }
            parameters[param_name] = param_info
        
        # Extract return type
        return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else 'Any'
        
        # Get source code
        try:
            source_code = inspect.getsource(func)
        except:
            source_code = ""
        
        # Extract description from docstring
        description = self._extract_description(docstring)
        
        # Determine category based on function name and module
        category = self._determine_category(name, module_name, docstring)
        
        # Extract examples from docstring
        examples = self._extract_examples(docstring)
        
        # Generate tags
        tags = self._generate_tags(name, module_name, docstring, category)
        
        # Determine complexity
        complexity = self._determine_complexity(source_code, parameters, docstring)
        
        # Extract data requirements
        data_requirements = self._extract_data_requirements(docstring, parameters)
        
        # Generate usage patterns
        usage_patterns = self._generate_usage_patterns(name, parameters, examples)
        
        # Extract dependencies
        dependencies = self._extract_dependencies(source_code)
        
        # Generate output description
        output_description = self._generate_output_description(name, return_type, docstring)
        
        return FunctionMetadata(
            name=name,
            module=module_name,
            description=description,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            examples=examples,
            category=category,
            tags=tags,
            source_code=source_code,
            usage_patterns=usage_patterns,
            dependencies=dependencies,
            complexity=complexity,
            data_requirements=data_requirements,
            output_description=output_description
        )
    
    def _extract_description(self, docstring: str) -> str:
        """Extract description from docstring."""
        if not docstring:
            return ""
        
        lines = docstring.strip().split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('Parameters:', 'Returns:', 'Examples:', 'Raises:', 'Note:', 'Warning:')):
                description_lines.append(line)
            else:
                break
        
        return ' '.join(description_lines).strip()
    
    def _extract_examples(self, docstring: str) -> List[str]:
        """Extract examples from docstring."""
        examples = []
        if not docstring:
            return examples
        
        # Look for example sections
        example_patterns = [
            r'Examples?:\s*\n(.*?)(?=\n\w+:|$)',
            r'Example:\s*\n(.*?)(?=\n\w+:|$)',
            r'Usage:\s*\n(.*?)(?=\n\w+:|$)',
            r'```python\s*\n(.*?)\n```',
            r'```\s*\n(.*?)\n```'
        ]
        
        for pattern in example_patterns:
            matches = re.findall(pattern, docstring, re.DOTALL | re.IGNORECASE)
            for match in matches:
                example_lines = [line.strip() for line in match.split('\n') if line.strip()]
                examples.extend(example_lines)
        
        return examples
    
    def _determine_category(self, name: str, module_name: str, docstring: str) -> str:
        """Determine the category of a function based on its name, module, and docstring."""
        text_to_analyze = f"{name} {module_name} {docstring}".lower()
        
        # Score each category
        category_scores = {}
        for category, info in self.categories.items():
            score = 0
            for keyword in info['keywords']:
                if keyword in text_to_analyze:
                    score += 1
            category_scores[category] = score
        
        # Return category with highest score, default to 'general'
        if category_scores:
            return max(category_scores, key=category_scores.get)
        return 'general'
    
    def _generate_tags(self, name: str, module_name: str, docstring: str, category: str) -> List[str]:
        """Generate tags for the function."""
        tags = [category]
        
        # Add module-based tags
        if 'anomaly' in module_name:
            tags.append('anomaly_detection')
        elif 'cohort' in module_name:
            tags.append('cohort_analysis')
        elif 'segmentation' in module_name:
            tags.append('segmentation')
        elif 'trend' in module_name:
            tags.append('trend_analysis')
        elif 'moving' in module_name:
            tags.append('moving_averages')
        elif 'risk' in module_name:
            tags.append('risk_analysis')
        elif 'funnel' in module_name:
            tags.append('funnel_analysis')
        elif 'metrics' in module_name:
            tags.append('metrics')
        elif 'operations' in module_name:
            tags.append('operations')
        
        # Add complexity tags
        if any(word in name.lower() for word in ['simple', 'basic', 'mean', 'sum', 'count']):
            tags.append('basic')
        elif any(word in name.lower() for word in ['advanced', 'complex', 'statistical', 'regression']):
            tags.append('advanced')
        
        # Add data type tags
        if any(word in name.lower() for word in ['time', 'date', 'temporal']):
            tags.append('time_series')
        if any(word in name.lower() for word in ['group', 'cohort', 'segment']):
            tags.append('grouped_data')
        if any(word in name.lower() for word in ['anomaly', 'outlier', 'detection']):
            tags.append('anomaly_detection')
        
        return list(set(tags))
    
    def _determine_complexity(self, source_code: str, parameters: Dict, docstring: str) -> str:
        """Determine the complexity of a function."""
        complexity_indicators = {
            'simple': ['mean', 'sum', 'count', 'max', 'min', 'basic'],
            'intermediate': ['rolling', 'moving', 'group', 'aggregate', 'filter'],
            'advanced': ['regression', 'clustering', 'monte', 'carlo', 'statistical', 'anomaly', 'forecast']
        }
        
        text_to_analyze = f"{source_code} {docstring}".lower()
        
        for complexity, indicators in complexity_indicators.items():
            if any(indicator in text_to_analyze for indicator in indicators):
                return complexity
        
        # Default based on parameter count
        if len(parameters) <= 3:
            return 'simple'
        elif len(parameters) <= 6:
            return 'intermediate'
        else:
            return 'advanced'
    
    def _extract_data_requirements(self, docstring: str, parameters: Dict) -> List[str]:
        """Extract data requirements from docstring and parameters."""
        requirements = []
        
        # Common data requirements based on parameter names
        param_requirements = {
            'time_column': 'Time/Date column',
            'date_column': 'Date column',
            'user_id_column': 'User ID column',
            'cohort_column': 'Cohort identifier column',
            'metric_column': 'Metric column',
            'value_column': 'Value column',
            'group_columns': 'Grouping columns',
            'columns': 'Data columns'
        }
        
        for param_name, param_info in parameters.items():
            if param_name in param_requirements:
                requirements.append(param_requirements[param_name])
        
        # Extract from docstring
        if docstring:
            docstring_lower = docstring.lower()
            if 'time' in docstring_lower or 'date' in docstring_lower:
                requirements.append('Time series data')
            if 'group' in docstring_lower or 'cohort' in docstring_lower:
                requirements.append('Grouped data')
            if 'anomaly' in docstring_lower or 'outlier' in docstring_lower:
                requirements.append('Numerical data for anomaly detection')
        
        return list(set(requirements))
    
    def _generate_usage_patterns(self, name: str, parameters: Dict, examples: List[str]) -> List[str]:
        """Generate usage patterns for the function."""
        patterns = []
        
        # Basic usage pattern
        param_names = list(parameters.keys())
        if param_names:
            basic_pattern = f"{name}({', '.join(param_names[:3])}{'...' if len(param_names) > 3 else ''})"
            patterns.append(basic_pattern)
        
        # Add patterns from examples
        for example in examples:
            if name in example:
                patterns.append(example)
        
        return patterns
    
    def _extract_dependencies(self, source_code: str) -> List[str]:
        """Extract dependencies from source code."""
        dependencies = []
        
        # Common ML and data science libraries
        common_deps = ['pandas', 'numpy', 'scipy', 'sklearn', 'statsmodels', 'matplotlib', 'seaborn']
        
        for dep in common_deps:
            if dep in source_code.lower():
                dependencies.append(dep)
        
        return dependencies
    
    def _generate_output_description(self, name: str, return_type: str, docstring: str) -> str:
        """Generate output description for the function."""
        if 'Returns:' in docstring:
            # Extract from docstring
            returns_section = docstring.split('Returns:')[1].split('\n')[0].strip()
            return returns_section
        
        # Generate based on function name and return type
        if 'detect' in name.lower():
            return f"Detection results with anomaly flags and scores"
        elif 'forecast' in name.lower():
            return f"Forecasted values with confidence intervals"
        elif 'aggregate' in name.lower():
            return f"Aggregated data with calculated metrics"
        elif 'segment' in name.lower():
            return f"Segmentation results with cluster assignments"
        else:
            return f"Results of type {return_type}"
    
    def register_function(self, func: Callable, module_name: str) -> str:
        """Register a single function in the registry.
        
        Args:
            func: The function to register
            module_name: Name of the module containing the function
            
        Returns:
            Document ID of the registered function
        """
        metadata = self.extract_function_metadata(func, module_name)
        self.functions_metadata[metadata.name] = metadata
        
        # Create document for ChromaDB
        doc_id = f"{module_name}_{metadata.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Prepare document content
        content = self._create_function_document_content(metadata)
        
        # Create metadata for ChromaDB
        chroma_metadata = {
            'function_name': metadata.name,
            'module': metadata.module,
            'category': metadata.category,
            'complexity': metadata.complexity,
            'tags': ','.join(metadata.tags),
            'parameters_count': len(metadata.parameters),
            'has_examples': len(metadata.examples) > 0,
            'dependencies': ','.join(metadata.dependencies),
            'data_requirements': ','.join(metadata.data_requirements)
        }
        
        # Create Langchain document
        doc, doc_id = create_langchain_doc_util(chroma_metadata, {'content': content})
        
        # Store in ChromaDB
        self.document_store.add_documents([doc])
        
        return doc_id
    
    def _create_function_document_content(self, metadata: FunctionMetadata) -> str:
        """Create comprehensive document content for a function."""
        content_parts = [
            f"Function: {metadata.name}",
            f"Module: {metadata.module}",
            f"Category: {metadata.category}",
            f"Complexity: {metadata.complexity}",
            "",
            f"Description: {metadata.description}",
            "",
            f"Parameters:",
        ]
        
        for param_name, param_info in metadata.parameters.items():
            required = "Required" if param_info['required'] else "Optional"
            default = f" (default: {param_info['default']})" if param_info['default'] is not None else ""
            content_parts.append(f"  - {param_name}: {param_info['type']} - {required}{default}")
        
        content_parts.extend([
            "",
            f"Returns: {metadata.return_type}",
            f"Output: {metadata.output_description}",
            "",
            f"Data Requirements: {', '.join(metadata.data_requirements)}",
            "",
            f"Tags: {', '.join(metadata.tags)}",
            "",
            f"Dependencies: {', '.join(metadata.dependencies)}",
        ])
        
        if metadata.examples:
            content_parts.extend([
                "",
                "Examples:",
            ])
            for example in metadata.examples:
                content_parts.append(f"  {example}")
        
        if metadata.usage_patterns:
            content_parts.extend([
                "",
                "Usage Patterns:",
            ])
            for pattern in metadata.usage_patterns:
                content_parts.append(f"  {pattern}")
        
        if metadata.docstring:
            content_parts.extend([
                "",
                "Full Documentation:",
                metadata.docstring
            ])
        
        return "\n".join(content_parts)
    
    def register_module_functions(self, module) -> List[str]:
        """Register all functions from a module.
        
        Args:
            module: The module to register functions from
            
        Returns:
            List of document IDs for registered functions
        """
        doc_ids = []
        module_name = module.__name__.split('.')[-1]
        
        # Get all functions from the module
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith('_'):
                try:
                    doc_id = self.register_function(obj, module_name)
                    doc_ids.append(doc_id)
                except Exception as e:
                    print(f"Error registering function {name}: {e}")
        
        return doc_ids
    
    def search_functions(self, query: str, n_results: int = 5, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for functions using semantic search.
        
        Args:
            query: Search query
            n_results: Number of results to return
            category: Optional category filter
            
        Returns:
            List of search results with function information
        """
        # Prepare where clause for category filtering
        where_clause = None
        if category:
            where_clause = {"category": category}
        
        # Perform semantic search
        results = self.document_store.semantic_search_with_bm25(
            query=query,
            k=n_results,
            where=where_clause
        )
        
        return results
    
    def get_function_by_name(self, function_name: str) -> Optional[FunctionMetadata]:
        """Get function metadata by name.
        
        Args:
            function_name: Name of the function to retrieve
            
        Returns:
            FunctionMetadata object if found, None otherwise
        """
        return self.functions_metadata.get(function_name)
    
    def get_functions_by_category(self, category: str) -> List[FunctionMetadata]:
        """Get all functions in a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of FunctionMetadata objects
        """
        return [metadata for metadata in self.functions_metadata.values() 
                if metadata.category == category]
    
    def get_all_functions(self) -> List[FunctionMetadata]:
        """Get all registered functions.
        
        Returns:
            List of all FunctionMetadata objects
        """
        return list(self.functions_metadata.values())
    
    def get_function_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered functions.
        
        Returns:
            Dictionary with function statistics
        """
        total_functions = len(self.functions_metadata)
        
        # Count by category
        category_counts = {}
        complexity_counts = {}
        module_counts = {}
        
        for metadata in self.functions_metadata.values():
            category_counts[metadata.category] = category_counts.get(metadata.category, 0) + 1
            complexity_counts[metadata.complexity] = complexity_counts.get(metadata.complexity, 0) + 1
            module_counts[metadata.module] = module_counts.get(metadata.module, 0) + 1
        
        return {
            'total_functions': total_functions,
            'by_category': category_counts,
            'by_complexity': complexity_counts,
            'by_module': module_counts,
            'categories': list(self.categories.keys())
        }


def initialize_function_registry(chroma_client: chromadb.PersistentClient) -> MLFunctionRegistry:
    """Initialize the function registry with all ML tool functions.
    
    Args:
        chroma_client: ChromaDB persistent client
        
    Returns:
        Initialized MLFunctionRegistry instance
    """
    registry = MLFunctionRegistry(chroma_client)
    
    # Import all ML tool modules
    from app.tools.mltools import (
        anomalydetection, cohortanalysistools, segmentationtools, 
        trendanalysistools, funnelanalysis, timeseriesanalysis,
        metrics_tools, operations_tools, movingaverages, riskanalysis,
        group_aggregation_functions
    )
    
    modules = [
        anomalydetection, cohortanalysistools, segmentationtools,
        trendanalysistools, funnelanalysis, timeseriesanalysis,
        metrics_tools, operations_tools, movingaverages, riskanalysis,
        group_aggregation_functions
    ]
    
    print("Registering ML tool functions...")
    total_registered = 0
    
    for module in modules:
        try:
            doc_ids = registry.register_module_functions(module)
            total_registered += len(doc_ids)
            print(f"Registered {len(doc_ids)} functions from {module.__name__}")
        except Exception as e:
            print(f"Error registering functions from {module.__name__}: {e}")
    
    print(f"Total functions registered: {total_registered}")
    return registry


if __name__ == "__main__":
    # Example usage
    import chromadb
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path="./chroma_db")
    
    # Initialize function registry
    registry = initialize_function_registry(client)
    
    # Search for functions
    results = registry.search_functions("detect anomalies in time series data", n_results=3)
    print("\nSearch Results:")
    for result in results:
        print(f"- {result['metadata']['function_name']}: {result['metadata']['category']}")
    
    # Get statistics
    stats = registry.get_function_statistics()
    print(f"\nRegistry Statistics:")
    print(f"Total functions: {stats['total_functions']}")
    print(f"Categories: {stats['by_category']}")
