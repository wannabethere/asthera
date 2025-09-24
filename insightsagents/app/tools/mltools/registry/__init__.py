"""
ML Function Registry

This module provides a comprehensive registry system for storing and retrieving
ML tool function definitions in ChromaDB using DocumentChromaStore.
"""

from app.tools.mltools.registry.function_registry import (
    MLFunctionRegistry,
    FunctionMetadata,
    initialize_function_registry
)

from app.tools.mltools.registry.function_search_interface import (
    FunctionSearchInterface,
    SearchResult,
    create_search_interface
)

from app.tools.mltools.registry.function_retrieval_service import (
    FunctionRetrievalService,
    create_function_retrieval_service
)

# Enhanced LLM-powered components
from app.tools.mltools.registry.llm_metadata_generator import (
    LLMMetadataGenerator,
    LLMGeneratedMetadata,
    DynamicFunctionMatcher,
    create_llm_metadata_generator,
    create_dynamic_function_matcher
)

from app.tools.mltools.registry.enhanced_comprehensive_registry import (
    EnhancedComprehensiveRegistry,
    FunctionMatch,
    StepFunctionMatch,
    EnhancedFunctionRetrievalResult,
    initialize_enhanced_comprehensive_registry
)

from app.tools.mltools.registry.enhanced_function_retrieval_service import (
    EnhancedFunctionRetrievalService,
    create_enhanced_function_retrieval_service
)

__all__ = [
    # Core Registry
    'MLFunctionRegistry',
    'FunctionMetadata',
    'initialize_function_registry',
    
    # Search Interface
    'FunctionSearchInterface',
    'SearchResult',
    'create_search_interface',
    
    # Retrieval Service
    'FunctionRetrievalService',
    'create_function_retrieval_service',
    
    # Enhanced LLM-powered components
    'LLMMetadataGenerator',
    'LLMGeneratedMetadata',
    'DynamicFunctionMatcher',
    'create_llm_metadata_generator',
    'create_dynamic_function_matcher',
    'EnhancedComprehensiveRegistry',
    'FunctionMatch',
    'StepFunctionMatch',
    'EnhancedFunctionRetrievalResult',
    'initialize_enhanced_comprehensive_registry',
    
    # Enhanced Function Retrieval Service
    'EnhancedFunctionRetrievalService',
    'create_enhanced_function_retrieval_service'
]
