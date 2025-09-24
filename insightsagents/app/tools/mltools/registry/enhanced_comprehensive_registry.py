"""
Enhanced Comprehensive Function Registry

This module provides an enhanced function registry that integrates comprehensive
function data including examples, usage patterns, code snippets, and instructions
for better code generation.
"""

import json
import logging
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import chromadb
from chromadb.config import Settings

from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from app.core.settings import get_settings
from langchain.schema import Document as LangchainDocument
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from pydantic import BaseModel, validator
from app.tools.mltools.registry.comprehensive_function_loader import (
    ComprehensiveFunctionLoader, 
    ComprehensiveFunctionData,
    load_comprehensive_functions
)
from app.tools.mltools.registry.llm_metadata_generator import (
    LLMMetadataGenerator, 
    LLMGeneratedMetadata,
    DynamicFunctionMatcher,
    create_llm_metadata_generator,
    create_dynamic_function_matcher
)
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.tools.mltools.registry.function_registry import MLFunctionRegistry, FunctionMetadata
from app.core.dependencies import get_llm

logger = logging.getLogger("enhanced-comprehensive-registry")
settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH + "/enhanced_comprehensive_registry"

class FunctionMatch(BaseModel):
    """Model for function match results with enhanced context"""
    function_name: str
    pipe_name: str
    description: str
    usage_description: str
    relevance_score: float
    reasoning: str
    category: str = "unknown"
    function_definition: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    instructions: Optional[List[Dict[str, Any]]] = None
    examples_store: Optional[List[Dict[str, Any]]] = None
    historical_rules: Optional[List[Dict[str, Any]]] = None
    insights: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        """Pydantic configuration for flexible validation"""
        extra = "allow"  # Allow extra fields
        validate_assignment = True  # Validate on assignment
        arbitrary_types_allowed = True  # Allow arbitrary types
    
    @validator('examples_store', pre=True)
    def convert_examples_store(cls, v):
        """Convert examples_store to proper format"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed] if parsed else []
            except (json.JSONDecodeError, TypeError):
                return [{"content": v, "type": "string"}]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, str):
                    try:
                        import json
                        parsed = json.loads(item)
                        if isinstance(parsed, dict):
                            result.append(parsed)
                        else:
                            result.append({"content": item, "type": "string"})
                    except (json.JSONDecodeError, TypeError):
                        result.append({"content": item, "type": "string"})
                else:
                    result.append({"content": str(item), "type": "unknown"})
            return result
        return []
    
    @validator('examples', pre=True)
    def convert_examples(cls, v):
        """Convert examples to proper format"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed] if parsed else []
            except (json.JSONDecodeError, TypeError):
                return [{"content": v, "type": "string"}]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(item)
                else:
                    result.append({"content": str(item), "type": "string"})
            return result
        return []
    
    @validator('instructions', pre=True)
    def convert_instructions(cls, v):
        """Convert instructions to proper format"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed] if parsed else []
            except (json.JSONDecodeError, TypeError):
                return [{"instruction": v, "type": "string"}]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(item)
                else:
                    result.append({"instruction": str(item), "type": "string"})
            return result
        return []
    
    @validator('historical_rules', pre=True)
    def convert_historical_rules(cls, v):
        """Convert historical_rules to proper format"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed] if parsed else []
            except (json.JSONDecodeError, TypeError):
                return [{"content": v, "type": "string"}]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(item)
                else:
                    result.append({"content": str(item), "type": "string"})
            return result
        return []
    
    @validator('insights', pre=True)
    def convert_insights(cls, v):
        """Convert insights to proper format"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed] if parsed else []
            except (json.JSONDecodeError, TypeError):
                return [{"content": v, "type": "string"}]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(item)
                else:
                    result.append({"content": str(item), "type": "string"})
            return result
        return []


class StepFunctionMatch(BaseModel):
    """Model for step-function matching results"""
    step_number: int
    step_title: str
    matched_functions: List[FunctionMatch]
    total_relevance_score: float
    
    class Config:
        """Pydantic configuration for flexible validation"""
        extra = "allow"  # Allow extra fields
        validate_assignment = True  # Validate on assignment
        arbitrary_types_allowed = True  # Allow arbitrary types


class EnhancedFunctionRetrievalResult(BaseModel):
    """Result model for enhanced function retrieval"""
    step_matches: Dict[int, List[Dict[str, Any]]]
    total_functions_retrieved: int
    total_steps_covered: int
    average_relevance_score: float
    confidence_score: float
    reasoning: str
    fallback_used: bool = False
    
    class Config:
        """Pydantic configuration for flexible validation"""
        extra = "allow"  # Allow extra fields
        validate_assignment = True  # Validate on assignment
        arbitrary_types_allowed = True  # Allow arbitrary types


class EnhancedComprehensiveRegistry(MLFunctionRegistry):
    """Enhanced registry that extends MLFunctionRegistry with comprehensive function data and AI-powered matching."""
    
    def __init__(
        self,
        collection_name: str = "comprehensive_ml_functions",
        toolspecs_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs",
        instructions_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions",
        usage_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/usage_examples",
        code_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples",
        chroma_path: str = None,
        llm=None,
        retrieval_helper: Optional[RetrievalHelper] = None,
        enable_separate_collections: bool = True
    ):
        """
        Initialize the enhanced comprehensive registry.
        
        Args:
            collection_name: Name of the collection to store function definitions
            toolspecs_path: Path to function specifications JSON files
            instructions_path: Path to instructions JSON files
            usage_examples_path: Path to usage examples JSON files
            code_examples_path: Path to code examples JSON files
            chroma_path: Path to ChromaDB storage (uses CHROMA_STORE_PATH if None)
            llm_model: LLM model to use for metadata generation
            llm: LangChain LLM instance for enhanced retrieval
            retrieval_helper: RetrievalHelper instance for comprehensive function retrieval
            enable_separate_collections: Whether to create separate collections for each data type
        """
        # Use default ChromaDB path if not provided
        if chroma_path is None:
            chroma_path = CHROMA_STORE_PATH
        
        # Initialize ChromaDB client
        try:
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            logger.info(f"ChromaDB client initialized successfully with path: {chroma_path}")
            print(f"DEBUG: ChromaDB client type: {type(chroma_client)}")
            print(f"DEBUG: ChromaDB version: {chromadb.__version__}")
            
            # Test collection creation to verify ChromaDB is working correctly
            test_collection_name = "test_collection_verification"
            try:
                test_collection = chroma_client.create_collection(name=test_collection_name)
                print(f"DEBUG: Test collection created with name: '{test_collection.name}'")
                if test_collection.name != test_collection_name:
                    logger.warning(f"ChromaDB test collection name mismatch: expected '{test_collection_name}', got '{test_collection.name}'")
                # Clean up test collection
                chroma_client.delete_collection(test_collection_name)
                logger.info("ChromaDB test collection created and deleted successfully")
            except Exception as test_error:
                logger.warning(f"ChromaDB test collection creation failed: {test_error}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
        
        # Call parent constructor
        super().__init__(chroma_client, collection_name)
        
        # Override the parent's document_store with one that has dimension checking
        # The parent's document_store was created without dimension checking
        self.document_store = DocumentChromaStore(
            persistent_client=chroma_client,
            collection_name=collection_name,
            tf_idf=True
        )
        
        # Store additional attributes
        self.chroma_path = chroma_path
        self.enable_separate_collections = enable_separate_collections
        
        # Define collection names for different data types
        self.collection_names = {
            'unified': collection_name,
            'toolspecs': f"{collection_name}_toolspecs",
            'instructions': f"{collection_name}_instructions", 
            'usage_examples': f"{collection_name}_usage_examples",
            'code_examples': f"{collection_name}_code_examples",
            'code': f"{collection_name}_code"
        }
        
        # Initialize separate document stores for each collection type (excluding unified)
        self.document_stores = {}
        if self.enable_separate_collections:
            for collection_type, collection_name in self.collection_names.items():
                if collection_type != 'unified':  # Skip unified collection, use parent's document_store
                    logger.info(f"Initializing document store for collection: {collection_name}")
                    try:
                        self.document_stores[collection_name] = DocumentChromaStore(
                            persistent_client=chroma_client,
                            collection_name=collection_name,
                            tf_idf=False  # Disable TF-IDF to avoid UUID collection issues
                        )
                        logger.info(f"Successfully initialized document store for: {collection_name}")
                    except Exception as e:
                        logger.error(f"Failed to initialize document store for {collection_name}: {e}")
                        raise
        
        # Initialize comprehensive loader
        self.loader = ComprehensiveFunctionLoader(
            toolspecs_path=toolspecs_path,
            instructions_path=instructions_path,
            usage_examples_path=usage_examples_path,
            code_examples_path=code_examples_path
        )
        
        # Initialize LLM components

        self.llm = llm if llm else get_llm()
        self.llm_metadata_generator = create_llm_metadata_generator(self.llm)
        self.dynamic_matcher = create_dynamic_function_matcher(self.llm_metadata_generator)
        
        # Initialize RetrievalHelper for enhanced function retrieval
        self.retrieval_helper = retrieval_helper or RetrievalHelper()
        
        # Cache for loaded functions
        self.functions_cache = {}
        self.initialized = False
    
    def _check_embedding_dimension_compatibility(self, collection_name: str) -> bool:
        """
        Check if the existing collection has compatible embedding dimensions.
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            True if compatible, False if incompatible
        """
        try:
            # Get the collection
            collection = self.chroma_client.get_collection(collection_name)
            
            # Get collection metadata to check embedding function
            metadata = collection.metadata or {}
            
            # Check if collection has any documents
            count = collection.count()
            if count == 0:
                logger.info(f"Collection '{collection_name}' is empty, compatible")
                return True
            
            # Try to get a sample document to check embedding dimensions
            try:
                # Get a sample document
                results = collection.get(limit=1)
                if results and 'embeddings' in results and results['embeddings']:
                    existing_dim = len(results['embeddings'][0])
                    
                    # Get current embedding dimension by creating a test embedding
                    test_embedding = self.document_store.embeddings_model.embed_query("test")
                    current_dim = len(test_embedding)
                    
                    logger.info(f"Collection '{collection_name}' embedding dimensions: existing={existing_dim}, current={current_dim}")
                    
                    if existing_dim != current_dim:
                        logger.warning(f"Embedding dimension mismatch in collection '{collection_name}': {existing_dim} vs {current_dim}")
                        return False
                    else:
                        logger.info(f"Embedding dimensions compatible for collection '{collection_name}'")
                        return True
                else:
                    logger.info(f"Collection '{collection_name}' has no embeddings, compatible")
                    return True
                    
            except Exception as e:
                logger.warning(f"Could not check embedding dimensions for collection '{collection_name}': {e}")
                # If we can't check, assume incompatible to be safe
                return False
                
        except Exception as e:
            logger.warning(f"Could not access collection '{collection_name}': {e}")
            return False

    def initialize_registry(self, force_recreate: bool = False) -> Dict[str, Any]:
        """
        Initialize the registry with comprehensive function data.
        
        Args:
            force_recreate: Whether to recreate the collection if it exists
            
        Returns:
            Dictionary with initialization results
        """
        logger.info("Initializing enhanced comprehensive registry...")
        
        try:
            # Check if collections already exist
            try:
                existing_collections = [col.name for col in self.chroma_client.list_collections()]
                logger.info(f"Found {len(existing_collections)} existing collections: {existing_collections}")
            except Exception as e:
                logger.warning(f"Failed to list existing collections: {e}")
                existing_collections = []
            
            # Handle collection recreation
            collections_to_recreate = []
            if self.enable_separate_collections:
                collections_to_recreate = list(self.collection_names.values())
            else:
                collections_to_recreate = [self.collection_name]
            
            for collection_name in collections_to_recreate:
                if collection_name in existing_collections:
                    # Check if we need to recreate due to embedding dimension mismatch
                    needs_recreation = force_recreate
                    
                    if not needs_recreation:
                        # Check embedding dimension compatibility
                        if not self._check_embedding_dimension_compatibility(collection_name):
                            logger.warning(f"Embedding dimension mismatch detected for collection '{collection_name}', will recreate")
                            needs_recreation = True
                    
                    if needs_recreation:
                        logger.info(f"Deleting existing collection: {collection_name}")
                        try:
                            self.chroma_client.delete_collection(collection_name)
                            logger.info(f"Successfully deleted collection: {collection_name}")
                        except Exception as e:
                            logger.error(f"Failed to delete collection {collection_name}: {e}")
                            raise
                else:
                    logger.info(f"Collection '{collection_name}' does not exist, will be created")
                    if not self.enable_separate_collections and not force_recreate:
                        return {"status": "exists", "collection_name": collection_name}
            
            # Load comprehensive function data
            logger.info("Loading comprehensive function data...")
            comprehensive_functions, documents = load_comprehensive_functions(
                toolspecs_path=self.loader.toolspecs_path,
                instructions_path=self.loader.instructions_path,
                usage_examples_path=self.loader.usage_examples_path,
                code_examples_path=self.loader.code_examples_path
            )
            
            print("I am here before documents after loading comprehensive functions") 
            if not documents:
                logger.error("No documents loaded")
                return {"status": "error", "error": "No documents loaded"}
            
            # Store documents in appropriate collections
            if self.enable_separate_collections:
                self._store_documents_in_separate_collections(comprehensive_functions, documents)
            else:
            # Store in unified collection
                logger.info(f"Storing {len(documents)} documents in unified ChromaDB collection...")
            print("documents", len(documents)) 
            print("self.document_store.collection_name", self.document_store.collection_name)   
            self.document_store.add_documents(documents)
            
            # Cache functions for quick access
            for func_data in comprehensive_functions:
                self.functions_cache[func_data.function_name] = func_data
            
            self.initialized = True
            
            # Get statistics
            stats = self.get_registry_statistics()
            
            logger.info(f"Registry initialized successfully with {len(comprehensive_functions)} functions")
            
            result = {
                "status": "success",
                "total_functions": len(comprehensive_functions),
                "total_documents": len(documents),
                "statistics": stats
            }
            
            if self.enable_separate_collections:
                result["collections"] = self.collection_names
            else:
                result["collection_name"] = self.collection_name
            
            return result
            
        except Exception as e:
            logger.error(f"Error initializing registry: {e}")
            return {"status": "error", "error": str(e)}
    
    def _store_documents_in_separate_collections(self, comprehensive_functions: List[ComprehensiveFunctionData], documents: List[Any]) -> None:
        """
        Store documents in separate collections based on their data type.
        
        Args:
            comprehensive_functions: List of comprehensive function data
            documents: List of documents to store
        """
        # Group documents by type
        documents_by_type = {
            'toolspecs': [],
            'instructions': [],
            'usage_examples': [],
            'code_examples': [],
            'code': [],
            'unified': documents  # Keep unified collection for cross-type search
        }
        
        # Create type-specific documents
        for func_data in comprehensive_functions:
            # Toolspecs documents
            toolspecs_doc = self._create_toolspecs_document(func_data)
            if toolspecs_doc:
                documents_by_type['toolspecs'].append(toolspecs_doc)
            
            # Instructions documents
            instructions_docs = self._create_instructions_documents(func_data)
            documents_by_type['instructions'].extend(instructions_docs)
            
            # Usage examples documents
            usage_docs = self._create_usage_examples_documents(func_data)
            documents_by_type['usage_examples'].extend(usage_docs)
            
            # Code examples documents
            code_examples_docs = self._create_code_examples_documents(func_data)
            documents_by_type['code_examples'].extend(code_examples_docs)
            
            # Code documents
            code_doc = self._create_code_document(func_data)
            if code_doc:
                documents_by_type['code'].append(code_doc)
        
        # Store in respective collections
        for collection_type, docs in documents_by_type.items():
            if docs:
                collection_name = self.collection_names[collection_type]
                logger.info(f"Storing {len(docs)} documents in {collection_type} collection ({collection_name})...")
                
                if collection_type == 'unified':
                    # Use parent's document_store for unified collection
                    self.document_store.add_documents(docs)
                else:
                    # Use separate document store for other collection types
                    self.document_stores[collection_name].add_documents(docs)
    
    def _create_toolspecs_document(self, func_data: ComprehensiveFunctionData) -> Optional[Any]:
        """Create a document focused on function specifications."""
        if not func_data.function_name:
            return None
            
        content_parts = [
            f"FUNCTION: {func_data.function_name}",
            f"PIPE: {func_data.pipe_name}",
            f"MODULE: {func_data.module}",
            f"CATEGORY: {func_data.category}",
            f"SUBCATEGORY: {func_data.subcategory}",
            f"COMPLEXITY: {func_data.complexity}",
            f"DESCRIPTION: {func_data.description}",
            "",
            "PARAMETERS:",
        ]
        
        # Add parameters
        if func_data.required_params:
            content_parts.append("Required:")
            for param in func_data.required_params:
                if isinstance(param, dict):
                    param_str = f"  - {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}"
                else:
                    param_str = f"  - {param}"
                content_parts.append(param_str)
        
        if func_data.optional_params:
            content_parts.append("Optional:")
            for param in func_data.optional_params:
                if isinstance(param, dict):
                    param_str = f"  - {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}"
                else:
                    param_str = f"  - {param}"
                content_parts.append(param_str)
        
        content_parts.extend([
            "",
            f"OUTPUTS: {func_data.outputs}",
            f"USE CASES: {', '.join(func_data.use_cases)}",
            f"DATA REQUIREMENTS: {', '.join(func_data.data_requirements)}",
            f"TAGS: {', '.join(func_data.tags)}",
            f"KEYWORDS: {', '.join(func_data.keywords)}"
        ])
        
        from langchain_core.documents import Document
        return Document(
            page_content="\n".join(content_parts),
            metadata={
                "function_name": func_data.function_name,
                "pipe_name": func_data.pipe_name,
                "module": func_data.module,
                "category": func_data.category,
                "subcategory": func_data.subcategory,
                "complexity": func_data.complexity,
                "confidence_score": func_data.confidence_score,
                "llm_generated": func_data.llm_generated,
                "type": "toolspecs",
                "source_files": ",".join(func_data.source_files)
            }
        )
    
    def _create_instructions_documents(self, func_data: ComprehensiveFunctionData) -> List[Any]:
        """Create documents focused on instructions and guidance."""
        documents = []
        
        if not func_data.instructions:
            return documents
        
        for i, instruction in enumerate(func_data.instructions):
            if isinstance(instruction, dict):
                title = instruction.get('title', f'Instruction {i+1}')
                content = instruction.get('content', '')
                context = instruction.get('context', '')
            else:
                title = f'Instruction {i+1}'
                content = str(instruction)
                context = ''
            
            content_parts = [
                f"FUNCTION: {func_data.function_name}",
                f"INSTRUCTION: {title}",
                "",
                f"CONTENT: {content}"
            ]
            
            if context:
                content_parts.extend(["", f"CONTEXT: {context}"])
            
            from langchain_core.documents import Document
            documents.append(Document(
                page_content="\n".join(content_parts),
                metadata={
                    "function_name": func_data.function_name,
                    "pipe_name": func_data.pipe_name,
                    "module": func_data.module,
                    "category": func_data.category,
                    "instruction_title": title,
                    "instruction_index": i,
                    "type": "instructions",
                    "source_files": ",".join(func_data.source_files)
                }
            ))
        
        return documents
    
    def _create_usage_examples_documents(self, func_data: ComprehensiveFunctionData) -> List[Any]:
        """Create documents focused on usage examples."""
        documents = []
        
        if not func_data.examples:
            return documents
        
        for i, example in enumerate(func_data.examples):
            if isinstance(example, dict):
                description = example.get('description', f'Example {i+1}')
                code = example.get('code', '')
                context = example.get('context', '')
            else:
                description = f'Example {i+1}'
                code = str(example)
                context = ''
            
            content_parts = [
                f"FUNCTION: {func_data.function_name}",
                f"EXAMPLE: {description}",
                "",
                f"CODE: {code}"
            ]
            
            if context:
                content_parts.extend(["", f"CONTEXT: {context}"])
            
            from langchain_core.documents import Document
            documents.append(Document(
                page_content="\n".join(content_parts),
                metadata={
                    "function_name": func_data.function_name,
                    "pipe_name": func_data.pipe_name,
                    "module": func_data.module,
                    "category": func_data.category,
                    "example_description": description,
                    "example_index": i,
                    "type": "usage_examples",
                    "source_files": ",".join(func_data.source_files)
                }
            ))
        
        return documents
    
    def _create_code_examples_documents(self, func_data: ComprehensiveFunctionData) -> List[Any]:
        """Create documents focused on code snippets."""
        documents = []
        
        if not func_data.code_snippets:
            return documents
        
        for i, snippet in enumerate(func_data.code_snippets):
            content_parts = [
                f"FUNCTION: {func_data.function_name}",
                f"CODE SNIPPET {i+1}:",
                "",
                snippet
            ]
            
            from langchain_core.documents import Document
            documents.append(Document(
                page_content="\n".join(content_parts),
                metadata={
                    "function_name": func_data.function_name,
                    "pipe_name": func_data.pipe_name,
                    "module": func_data.module,
                    "category": func_data.category,
                    "snippet_index": i,
                    "type": "code_examples",
                    "source_files": ",".join(func_data.source_files)
                }
            ))
        
        return documents
    
    def _create_code_document(self, func_data: ComprehensiveFunctionData) -> Optional[Any]:
        """Create a document focused on source code."""
        if not func_data.source_code:
            return None
        
        content_parts = [
            f"FUNCTION: {func_data.function_name}",
            f"PIPE: {func_data.pipe_name}",
            f"MODULE: {func_data.module}",
            f"FUNCTION SIGNATURE: {func_data.function_signature}",
            "",
            "SOURCE CODE:",
            func_data.source_code
        ]
        
        if func_data.docstring:
            content_parts.extend(["", "DOCSTRING:", func_data.docstring])
        
        from langchain_core.documents import Document
        return Document(
            page_content="\n".join(content_parts),
            metadata={
                "function_name": func_data.function_name,
                "pipe_name": func_data.pipe_name,
                "module": func_data.module,
                "category": func_data.category,
                "type": "code",
                "source_files": ",".join(func_data.source_files)
            }
        )
    
    def search_functions(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
        complexity: Optional[str] = None,
        has_examples: Optional[bool] = None,
        has_instructions: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for functions using semantic search with comprehensive context.
        Extends parent search_functions with additional filtering and comprehensive data.
        
        Args:
            query: Search query
            n_results: Number of results to return
            category: Optional category filter
            complexity: Optional complexity filter
            has_examples: Optional filter for functions with examples
            has_instructions: Optional filter for functions with instructions
            
        Returns:
            List of search results with comprehensive function data
        """
        try:
            # Use parent search_functions as base
            search_results = super().search_functions(query, n_results, category)
            
            # Apply additional filters and enhance with comprehensive data
            filtered_results = []
            for result in search_results:
                metadata = result.get('metadata', {})
                
                # Apply additional filters
                if complexity and metadata.get('complexity') != complexity:
                    continue
                if has_examples is not None:
                    if has_examples and not metadata.get('has_examples', False):
                        continue
                    if not has_examples and metadata.get('has_examples', False):
                        continue
                if has_instructions is not None:
                    if has_instructions and not metadata.get('has_instructions', False):
                        continue
                    if not has_instructions and metadata.get('has_instructions', False):
                        continue
                
                # Get comprehensive function data from cache
                function_name = metadata.get('function_name', '')
                if function_name in self.functions_cache:
                    comprehensive_data = self.functions_cache[function_name]
                    
                    # Create enhanced result
                    enhanced_result = {
                        'function_name': function_name,
                        'pipe_name': comprehensive_data.pipe_name,
                        'module': comprehensive_data.module,
                        'category': comprehensive_data.category,
                        'subcategory': comprehensive_data.subcategory,
                        'description': comprehensive_data.description,
                        'complexity': comprehensive_data.complexity,
                        'confidence_score': comprehensive_data.confidence_score,
                        'tags': comprehensive_data.tags,
                        'keywords': comprehensive_data.keywords,
                        'use_cases': comprehensive_data.use_cases,
                        'data_requirements': comprehensive_data.data_requirements,
                        'required_params': comprehensive_data.required_params,
                        'optional_params': comprehensive_data.optional_params,
                        'outputs': comprehensive_data.outputs,
                        'examples': comprehensive_data.examples,
                        'code_snippets': comprehensive_data.code_snippets,
                        'usage_patterns': comprehensive_data.usage_patterns,
                        'instructions': comprehensive_data.instructions,
                        'business_cases': comprehensive_data.business_cases,
                        'natural_language_questions': comprehensive_data.natural_language_questions,
                        'configuration_hints': comprehensive_data.configuration_hints,
                        'typical_parameters': comprehensive_data.typical_parameters,
                        'source_code': comprehensive_data.source_code,
                        'function_signature': comprehensive_data.function_signature,
                        'docstring': comprehensive_data.docstring,
                        'examples_count': len(comprehensive_data.examples),
                        'instructions_count': len(comprehensive_data.instructions),
                        'code_snippets_count': len(comprehensive_data.code_snippets),
                        'relevance_score': result.get('score', 0.0),
                        'content': result.get('content', '')
                    }
                    
                    filtered_results.append(enhanced_result)
                else:
                    # Use basic result if comprehensive data not available
                    filtered_results.append(result)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error searching functions: {e}")
            return []
    
    def get_function_by_name(self, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive function data by name.
        Extends parent get_function_by_name with comprehensive data.
        
        Args:
            function_name: Name of the function to retrieve
            
        Returns:
            Comprehensive function data if found, None otherwise
        """
        # First try to get from comprehensive cache
        if function_name in self.functions_cache:
            func_data = self.functions_cache[function_name]
            return {
                'function_name': func_data.function_name,
                'pipe_name': func_data.pipe_name,
                'module': func_data.module,
                'category': func_data.category,
                'subcategory': func_data.subcategory,
                'description': func_data.description,
                'complexity': func_data.complexity,
                'confidence_score': func_data.confidence_score,
                'tags': func_data.tags,
                'keywords': func_data.keywords,
                'use_cases': func_data.use_cases,
                'data_requirements': func_data.data_requirements,
                'required_params': func_data.required_params,
                'optional_params': func_data.optional_params,
                'outputs': func_data.outputs,
                'examples': func_data.examples,
                'code_snippets': func_data.code_snippets,
                'usage_patterns': func_data.usage_patterns,
                'usage_description': func_data.usage_description,
                'instructions': func_data.instructions,
                'business_cases': func_data.business_cases,
                'natural_language_questions': func_data.natural_language_questions,
                'configuration_hints': func_data.configuration_hints,
                'typical_parameters': func_data.typical_parameters,
                'source_code': func_data.source_code,
                'function_signature': func_data.function_signature,
                'docstring': func_data.docstring,
                'examples_count': len(func_data.examples),
                'instructions_count': len(func_data.instructions),
                'code_snippets_count': len(func_data.code_snippets),
                'source_files': func_data.source_files,
                'function_definition': self._create_function_definition(func_data)
            }
        
        # Fallback to parent method
        parent_result = super().get_function_by_name(function_name)
        if parent_result:
            # Convert FunctionMetadata to dict format
            return {
                'function_name': parent_result.name,
                'module': parent_result.module,
                'category': parent_result.category,
                'description': parent_result.description,
                'complexity': parent_result.complexity,
                'tags': parent_result.tags,
                'source_code': parent_result.source_code,
                'docstring': parent_result.docstring,
                'examples': parent_result.examples,
                'usage_patterns': parent_result.usage_patterns,
                'dependencies': parent_result.dependencies,
                'data_requirements': parent_result.data_requirements,
                'output_description': parent_result.output_description
            }
        
        return None
    
    def get_functions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all functions in a specific category.
        Extends parent get_functions_by_category with comprehensive data.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of functions in the category
        """
        # First try comprehensive cache
        comprehensive_results = []
        for func_data in self.functions_cache.values():
            if func_data.category == category:
                comprehensive_results.append(self.get_function_by_name(func_data.function_name))
        
        if comprehensive_results:
            return [r for r in comprehensive_results if r is not None]
        
        # Fallback to parent method
        parent_results = super().get_functions_by_category(category)
        return [self.get_function_by_name(func.name) for func in parent_results if func]
    
    def search_by_collection_type(
        self,
        query: str,
        collection_type: str,
        n_results: int = 5,
        category: Optional[str] = None,
        complexity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search functions in a specific collection type.
        
        Args:
            query: Search query
            collection_type: Type of collection to search ('toolspecs', 'instructions', 'usage_examples', 'code_examples', 'code')
            n_results: Number of results to return
            category: Optional category filter
            complexity: Optional complexity filter
            
        Returns:
            List of search results from the specified collection type
        """
        if not self.enable_separate_collections:
            logger.warning("Separate collections not enabled, falling back to unified search")
            return self.search_functions(query, n_results, category, complexity)
        
        if collection_type not in self.collection_names:
            logger.error(f"Invalid collection type: {collection_type}")
            return []
        
        collection_name = self.collection_names[collection_type]
        
        try:
            # Build filter for metadata
            where_filter = {}
            if category:
                where_filter["category"] = category
            if complexity:
                where_filter["complexity"] = complexity
            
            # Search in specific collection
            if collection_type == 'unified':
                # Use parent's document_store for unified collection
                if hasattr(self.document_store, 'tf_idf') and self.document_store.tf_idf:
                    results = self.document_store.semantic_search_with_tfidf(
                        query=query,
                        k=n_results,
                        where=where_filter if where_filter else None
                    )
                else:
                    results = self.document_store.semantic_search(
                        query=query,
                        k=n_results,
                        where=where_filter if where_filter else None
                    )
            else:
                # Use separate document store for other collection types
                if collection_name not in self.document_stores:
                    logger.error(f"Document store not found for collection: {collection_name}")
                    return []
                
                document_store = self.document_stores[collection_name]
                if hasattr(document_store, 'tf_idf') and document_store.tf_idf:
                    results = document_store.semantic_search_with_tfidf(
                        query=query,
                        k=n_results,
                        where=where_filter if where_filter else None
                    )
                else:
                    results = document_store.semantic_search(
                        query=query,
                        k=n_results,
                        where=where_filter if where_filter else None
                    )
            
            # Convert to expected format
            search_results = []
            for result in results:
                # Handle both TF-IDF results (dict format) and regular semantic search results (object format)
                if isinstance(result, dict):
                    # TF-IDF results are already in dict format
                    search_results.append({
                        'content': result.get('content', ''),
                        'metadata': result.get('metadata', {}),
                        'score': result.get('combined_score', result.get('score', 0.0))
                    })
                else:
                    # Regular semantic search results are objects with page_content and metadata attributes
                    search_results.append({
                        'content': getattr(result, 'page_content', ''),
                        'metadata': getattr(result, 'metadata', {}),
                        'score': getattr(result, 'score', 0.0)
                    })
            
            logger.info(f"Found {len(search_results)} results in {collection_type} collection")
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching {collection_type} collection: {e}")
            return []
    
    def search_unified(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
        complexity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across all collections and return unified results.
        
        Args:
            query: Search query
            n_results: Number of results to return per collection
            category: Optional category filter
            complexity: Optional complexity filter
            
        Returns:
            List of search results from all collections
        """
        if not self.enable_separate_collections:
            return self.search_functions(query, n_results, category, complexity)
        
        all_results = []
        
        # Search each collection type
        for collection_type in ['toolspecs', 'instructions', 'usage_examples', 'code_examples', 'code']:
            results = self.search_by_collection_type(
                query=query,
                collection_type=collection_type,
                n_results=n_results,
                category=category,
                complexity=complexity
            )
            
            # Add collection type to metadata
            for result in results:
                result['metadata']['collection_type'] = collection_type
            
            all_results.extend(results)
        
        # Sort by relevance score and return top results
        all_results.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        return all_results[:n_results * 2]  # Return more results since we're searching multiple collections
    
    def get_collection_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all collections.
        
        Returns:
            Dictionary with statistics for each collection
        """
        if not self.enable_separate_collections:
            return {"unified": self.get_registry_statistics()}
        
        stats = {}
        
        # Handle unified collection separately
        unified_collection_name = self.collection_names['unified']
        try:
            existing_collections = self.chroma_client.list_collections()
            if unified_collection_name not in existing_collections:
                stats['unified'] = {
                    "document_count": 0,
                    "status": "not_created",
                    "collection_name": unified_collection_name
                }
            else:
                collection = self.chroma_client.get_collection(unified_collection_name)
                count = collection.count()
                stats['unified'] = {
                    "document_count": count,
                    "collection_name": unified_collection_name,
                    "status": "active" if count > 0 else "empty"
                }
        except Exception as e:
            stats['unified'] = {
                "document_count": 0,
                "collection_name": unified_collection_name,
                "status": "error",
                "error": str(e)
            }
        
        # Handle separate collections
        for collection_name, document_store in self.document_stores.items():
            try:
                # Find the collection type for this collection name
                collection_type = None
                for ct, cn in self.collection_names.items():
                    if cn == collection_name:
                        collection_type = ct
                        break
                
                if collection_type is None:
                    logger.warning(f"Collection type not found for collection name: {collection_name}")
                    continue
                
                # Check if collection exists before trying to access it
                existing_collections = self.chroma_client.list_collections()
                if collection_name not in existing_collections:
                    stats[collection_type] = {
                        "document_count": 0,
                        "status": "not_created",
                        "collection_name": collection_name
                    }
                    continue
                
                collection = self.chroma_client.get_collection(collection_name)
                count = collection.count()
                
                stats[collection_type] = {
                    "document_count": count,
                    "collection_name": collection_name,
                    "status": "active" if count > 0 else "empty"
                }
            except Exception as e:
                stats[collection_type] = {
                    "document_count": 0,
                    "collection_name": collection_name,
                    "status": "error",
                    "error": str(e)
                }
        
        return stats
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        if not self.enable_separate_collections:
            # Use parent's get_function_statistics method and adapt it
            try:
                parent_stats = super().get_function_statistics()
                return {
                    "total_functions": parent_stats.get('total_functions', 0),
                    "total_documents": parent_stats.get('total_functions', 0),  # Use function count as document count
                    "collections": {"unified": {"document_count": parent_stats.get('total_functions', 0), "status": "active"}},
                    "initialized": self.initialized,
                    "separate_collections_enabled": False
                }
            except AttributeError:
                # Fallback if parent method doesn't exist
                return {
                    "total_functions": len(self.functions_cache),
                    "total_documents": len(self.functions_cache),
                    "collections": {"unified": {"document_count": len(self.functions_cache), "status": "active"}},
                    "initialized": self.initialized,
                    "separate_collections_enabled": False
                }
        
        # Get statistics for all collections
        collection_stats = self.get_collection_statistics()
        
        # Calculate totals
        total_documents = sum(stats.get('document_count', 0) for stats in collection_stats.values())
        total_functions = len(self.functions_cache)
        
        return {
            "total_functions": total_functions,
            "total_documents": total_documents,
            "collections": collection_stats,
            "initialized": self.initialized,
            "separate_collections_enabled": True
        }
    
    
    
    
    
    
    # ==================== AI-POWERED FUNCTION MATCHING METHODS ====================
    
    
    
    async def retrieve_and_match_functions(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> EnhancedFunctionRetrievalResult:
        """
        Main method to retrieve and match functions to analysis steps using AI.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            question: Original user question
            rephrased_question: Rephrased question from Step 1
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID
            
        Returns:
            EnhancedFunctionRetrievalResult with step-function matches
        """
        try:
            logger.info("Starting AI-powered function retrieval and matching...")
            
            # Step 1: Fetch relevant functions from ChromaDB
            relevant_functions = await self._fetch_relevant_functions_from_chromadb(
                reasoning_plan=reasoning_plan,
                question=question,
                rephrased_question=rephrased_question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                project_id=project_id
            )
            
            if not relevant_functions:
                logger.warning("No relevant functions found in ChromaDB")
                return self._create_empty_result("No relevant functions found")
            
            # Step 2: Enrich functions with context
            enriched_functions = []
            for func in relevant_functions:
                enriched_func = await self._enrich_function_with_context(
                    function_data=func,
                    question=question,
                    project_id=project_id
                )
                enriched_functions.append(enriched_func)
            
            # Step 3: Match functions to steps using AI
            step_function_matches = await self._match_functions_to_steps_with_ai(
                reasoning_plan=reasoning_plan,
                relevant_functions=enriched_functions,
                question=question,
                dataframe_description=dataframe_description,
                available_columns=available_columns
            )
            
            # Step 4: Calculate metrics and create result
            result = self._create_result_from_matches(
                step_function_matches=step_function_matches,
                total_functions=len(enriched_functions),
                reasoning_plan=reasoning_plan,
                fallback_used=False
            )
            
            logger.info(f"AI-powered function retrieval completed successfully")
            logger.info(f"  - Retrieved {len(relevant_functions)} functions")
            logger.info(f"  - Matched to {len(step_function_matches)} steps")
            logger.info(f"  - Average relevance score: {result.average_relevance_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI-powered function retrieval: {e}")
            return self._create_empty_result(f"Error: {str(e)}", fallback_used=True)
    
    async def _fetch_relevant_functions_from_chromadb(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch relevant functions from ChromaDB using comprehensive context."""
        try:
            if not self.retrieval_helper:
                logger.warning("RetrievalHelper not available")
                return []
            
            # Create a comprehensive query that includes the reasoning plan
            plan_context = "\n".join([
                f"Step {step.get('step_number', i+1)}: {step.get('step_title', '')} - {step.get('step_description', '')}"
                for i, step in enumerate(reasoning_plan)
            ])
            
            # Combine all context for a comprehensive search
            comprehensive_query = f"""
            User Question: {question}
            Rephrased Question: {rephrased_question}
            Dataframe Description: {dataframe_description}
            Available Columns: {', '.join(available_columns)}
            
            Analysis Plan:
            {plan_context}
            """
            
            logger.info(f"Fetching functions from ChromaDB with comprehensive query")
            
            # Fetch multiple relevant functions from ChromaDB
            relevant_functions = []
            
            # Try different search strategies to get comprehensive results
            search_queries = [
                comprehensive_query,
                rephrased_question,
                plan_context,
                question
            ]
            
            for query in search_queries:
                try:
                    # Use the retrieval helper to get function definitions
                    function_result = await self.retrieval_helper.get_function_definition_by_query(
                        query=query,
                        similarity_threshold=0.6,
                        top_k=10
                    )
                    
                    if function_result and function_result.get("function_definition"):
                        relevant_functions.append(function_result["function_definition"])
                        logger.info(f"Found function: {function_result['function_definition'].get('function_name', 'unknown')}")
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch functions with query '{query[:50]}...': {e}")
                    continue
            
            # Remove duplicates based on function name
            unique_functions = {}
            for func in relevant_functions:
                func_name = func.get("function_name", "")
                if func_name and func_name not in unique_functions:
                    unique_functions[func_name] = func
            
            logger.info(f"Retrieved {len(unique_functions)} unique functions from ChromaDB")
            return list(unique_functions.values())
            
        except Exception as e:
            logger.error(f"Error fetching functions from ChromaDB: {e}")
            return []
    
    async def _enrich_function_with_context(
        self,
        function_data: Dict[str, Any],
        question: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enrich function data with examples, instructions, and examples store"""
        if not self.retrieval_helper:
            return function_data
        
        function_name = function_data.get("function_name", "")
        if not function_name:
            return function_data
        
        try:
            # Retrieve examples, instructions, and examples store in parallel
            examples_task = self.retrieval_helper.get_function_examples(
                function_name=function_name,
                similarity_threshold=0.6,
                top_k=5
            )
            
            insights_task = self.retrieval_helper.get_function_insights(
                function_name=function_name,
                similarity_threshold=0.6,
                top_k=3
            )
            
            instructions_task = None
            if project_id:
                instructions_task = self.retrieval_helper.get_instructions(
                    query=question,
                    project_id=project_id,
                    similarity_threshold=0.7,
                    top_k=5
                )
            
            # Wait for all tasks to complete
            examples_result = await examples_task
            insights_result = await insights_task
            instructions_result = await instructions_task if instructions_task else {"instructions": []}
            
            # Extract examples
            examples = []
            if examples_result and not examples_result.get("error"):
                raw_examples = examples_result.get("examples", [])
                examples = self._clean_data_list(raw_examples, "example")
            
            # Extract insights (used as examples store for historical patterns)
            examples_store = []
            if insights_result and not insights_result.get("error"):
                raw_insights = insights_result.get("insights", [])
                examples_store = self._clean_data_list(raw_insights, "insight")
            
            # Extract instructions
            instructions = []
            if instructions_result and not instructions_result.get("error"):
                raw_instructions = instructions_result.get("instructions", [])
                instructions = self._clean_data_list(raw_instructions, "instruction")
            
            # Get historical rules from examples store
            historical_rules = await self._get_historical_rules(function_name, question)
            
            # Update function data
            enriched_data = function_data.copy()
            enriched_data.update({
                "examples": examples,
                "instructions": instructions,
                "examples_store": examples_store,
                "historical_rules": historical_rules
            })
            
            logger.info(f"Enriched {function_name} with {len(examples)} examples, {len(instructions)} instructions, {len(examples_store)} insights, {len(historical_rules)} historical rules")
            
            return enriched_data
            
        except Exception as e:
            logger.error(f"Error enriching function {function_name}: {e}")
            # Return original data if enrichment fails
            enriched_data = function_data.copy()
            enriched_data.update({
                "examples": [],
                "instructions": [],
                "examples_store": [],
                "historical_rules": []
            })
            return enriched_data
    
    async def _match_functions_to_steps_with_ai(
        self,
        reasoning_plan: List[Dict[str, Any]],
        relevant_functions: List[Dict[str, Any]],
        question: str,
        dataframe_description: str,
        available_columns: List[str]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Use AI to match functions to specific steps in the reasoning plan."""
        try:
            if not self.llm:
                logger.warning("LLM not available, using fallback matching")
                return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
            
            # Format functions for LLM prompt with enriched context
            function_descriptions = []
            for func in relevant_functions:
                desc = f"""
                Function: {func.get('function_name', 'unknown')}
                Pipeline: {func.get('pipe_name', 'unknown')}
                Description: {func.get('description', 'No description')}
                Usage: {func.get('usage_description', 'No usage info')}
                Category: {func.get('category', 'unknown')}
                """
                
                # Add examples if available
                examples = func.get('examples', [])
                if examples:
                    desc += f"\nExamples ({len(examples)} available):\n"
                    for i, example in enumerate(examples[:3], 1):
                        desc += f"  {i}. {str(example)[:200]}...\n"
                
                # Add instructions if available
                instructions = func.get('instructions', [])
                if instructions:
                    desc += f"\nInstructions ({len(instructions)} available):\n"
                    for i, instruction in enumerate(instructions[:2], 1):
                        desc += f"  {i}. {instruction.get('instruction', str(instruction))[:150]}...\n"
                
                function_descriptions.append(desc)
            
            # Format reasoning plan for LLM prompt
            plan_description = "\n".join([
                f"Step {step.get('step_number', i+1)}: {step.get('step_title', '')}\n"
                f"Description: {step.get('step_description', '')}\n"
                f"Data Requirements: {', '.join(step.get('data_requirements', []))}\n"
                for i, step in enumerate(reasoning_plan)
            ])
            
            # Create LLM prompt for function matching
            prompt = f"""
            You are an expert data analyst who matches analysis functions to specific analysis steps.
            
            USER QUESTION: {question}
            DATAFRAME DESCRIPTION: {dataframe_description}
            AVAILABLE COLUMNS: {', '.join(available_columns)}
            
            ANALYSIS PLAN:
            {plan_description}
            
            AVAILABLE FUNCTIONS (with examples and instructions):
            {chr(10).join(function_descriptions)}
            
            TASK: For each step in the analysis plan, identify which functions are most relevant and appropriate.
            
            INSTRUCTIONS:
            1. Analyze each step's requirements and data needs
            2. Consider function descriptions, examples, and instructions
            3. Match functions that can fulfill those requirements
            4. Score each function's relevance (0.0 to 1.0) for each step
            5. Provide detailed reasoning based on the function's capabilities
            6. Return results as JSON
            
            OUTPUT FORMAT:
            {{
                "step_matches": {{
                    "1": [
                        {{
                            "function_name": "function_name",
                            "pipe_name": "pipe_name", 
                            "relevance_score": 0.95,
                            "reasoning": "Detailed reasoning based on function capabilities",
                            "description": "function description",
                            "usage_description": "usage description",
                            "category": "category",
                            "function_definition": {{...}}
                        }}
                    ],
                    "2": [...],
                    ...
                }}
            }}
            
            Focus on functions that directly address each step's specific requirements.
            Return ONLY the JSON object, nothing else.
            """
            
            # Get LLM response
            llm_response = await self._classify_with_llm(prompt)
            
            # Parse the response
            try:
                cleaned_response = llm_response.strip()
                cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
                cleaned_response = re.sub(r'```\s*', '', cleaned_response)
                cleaned_response = cleaned_response.strip()
                
                if not cleaned_response or cleaned_response.isspace():
                    logger.warning("LLM returned empty response, using fallback")
                    return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
                response_data = json.loads(cleaned_response)
                step_matches = response_data.get("step_matches", {})
                
                # Convert string keys to integers and validate
                validated_matches = {}
                for step_key, functions in step_matches.items():
                    try:
                        step_num = int(step_key)
                        if step_num > 0:
                            validated_matches[step_num] = functions
                    except ValueError:
                        continue
                
                logger.info(f"AI matched functions to {len(validated_matches)} steps")
                return validated_matches
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
        except Exception as e:
            logger.error(f"Error in AI function matching: {e}")
            return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
    
    def _fallback_function_step_matching(
        self,
        reasoning_plan: List[Dict[str, Any]],
        relevant_functions: List[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Fallback function matching when AI matching fails."""
        step_matches = {}
        
        for step in reasoning_plan:
            step_num = step.get("step_number", 0)
            step_title = step.get("step_title", "").lower()
            step_desc = step.get("step_description", "").lower()
            
            matched_functions = []
            
            for func in relevant_functions:
                func_name = func.get("function_name", "").lower()
                func_desc = func.get("description", "").lower()
                func_usage = func.get("usage_description", "").lower()
                
                # Simple keyword matching
                relevance_score = 0.0
                reasoning = ""
                
                # Check for keyword matches
                keywords = step_title.split() + step_desc.split()
                for keyword in keywords:
                    if keyword in func_name or keyword in func_desc or keyword in func_usage:
                        relevance_score += 0.2
                
                # Normalize score
                relevance_score = min(1.0, relevance_score)
                
                if relevance_score > 0.3:  # Only include if reasonably relevant
                    matched_functions.append({
                        "function_name": func.get("function_name", ""),
                        "pipe_name": func.get("pipe_name", ""),
                        "relevance_score": relevance_score,
                        "reasoning": f"Keyword match with step: {step_title}",
                        "description": func.get("description", ""),
                        "usage_description": func.get("usage_description", ""),
                        "category": func.get("category", ""),
                        "function_definition": func,
                        "examples": func.get("examples", []),
                        "instructions": func.get("instructions", []),
                        "examples_store": func.get("examples_store", []),
                        "historical_rules": func.get("historical_rules", [])
                    })
            
            if matched_functions:
                step_matches[step_num] = matched_functions
        
        logger.info(f"Fallback matching assigned functions to {len(step_matches)} steps")
        return step_matches
    
    async def _classify_with_llm(self, prompt: str) -> str:
        """Classify using LLM with error handling"""
        try:
            # Create the chain with StrOutputParser
            chain = PromptTemplate.from_template("{prompt}") | self.llm | StrOutputParser()
            
            # Generate response with timeout
            try:
                response = await asyncio.wait_for(
                    chain.ainvoke({"prompt": prompt}),
                    timeout=30.0  # 30 second timeout
                )
                
                # Validate response
                if not response or not isinstance(response, str):
                    logger.warning(f"LLM returned invalid response type: {type(response)}")
                    return ""
                
                return response
                
            except asyncio.TimeoutError:
                logger.error("LLM call timed out after 30 seconds")
                return ""
                
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return ""
    
    def _create_result_from_matches(
        self,
        step_function_matches: Dict[int, List[Dict[str, Any]]],
        total_functions: int,
        reasoning_plan: List[Dict[str, Any]],
        fallback_used: bool = False
    ) -> EnhancedFunctionRetrievalResult:
        """Create result object from step-function matches"""
        # Calculate metrics
        total_steps_covered = len(step_function_matches)
        total_steps = len(reasoning_plan)
        
        # Calculate average relevance score
        all_scores = []
        for functions in step_function_matches.values():
            for func in functions:
                all_scores.append(func.get("relevance_score", 0.0))
        
        average_relevance_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        # Calculate confidence score
        coverage_ratio = total_steps_covered / total_steps if total_steps > 0 else 0.0
        confidence_score = (coverage_ratio + average_relevance_score) / 2
        
        reasoning = f"Matched {total_functions} functions to {total_steps_covered}/{total_steps} steps with average relevance {average_relevance_score:.2f}"
        if fallback_used:
            reasoning += " (using fallback matching)"
        
        return EnhancedFunctionRetrievalResult(
            step_matches=step_function_matches,
            total_functions_retrieved=total_functions,
            total_steps_covered=total_steps_covered,
            average_relevance_score=average_relevance_score,
            confidence_score=confidence_score,
            reasoning=reasoning,
            fallback_used=fallback_used
        )
    
    def _create_empty_result(self, reasoning: str, fallback_used: bool = True) -> EnhancedFunctionRetrievalResult:
        """Create empty result when no functions are found"""
        return EnhancedFunctionRetrievalResult(
            step_matches={},
            total_functions_retrieved=0,
            total_steps_covered=0,
            average_relevance_score=0.0,
            confidence_score=0.0,
            reasoning=reasoning,
            fallback_used=fallback_used
        )
    
    async def _get_historical_rules(
        self,
        function_name: str,
        question: str
    ) -> List[Dict[str, Any]]:
        """Get historical rules and patterns for the function"""
        if not self.retrieval_helper:
            return []
        
        try:
            # Get examples store for historical patterns
            examples_store_result = await self.retrieval_helper.get_function_examples(
                function_name=function_name,
                similarity_threshold=0.5,
                top_k=10
            )
            
            historical_rules = []
            if examples_store_result and not examples_store_result.get("error"):
                raw_examples = examples_store_result.get("examples", [])
                examples = self._clean_data_list(raw_examples, "example")
                
                # Filter for historical patterns and rules
                for example in examples:
                    if isinstance(example, dict):
                        # Look for rule-like patterns in the example
                        if any(keyword in str(example).lower() for keyword in ["rule", "pattern", "best_practice", "guideline", "convention"]):
                            historical_rules.append({
                                "type": "historical_pattern",
                                "content": example,
                                "source": "examples_store"
                            })
            
            # Add hardcoded rules based on function type
            hardcoded_rules = self._get_hardcoded_rules(function_name)
            historical_rules.extend(hardcoded_rules)
            
            return historical_rules
            
        except Exception as e:
            logger.error(f"Error getting historical rules for {function_name}: {e}")
            return []
    
    def _get_hardcoded_rules(self, function_name: str) -> List[Dict[str, Any]]:
        """Get hardcoded rules based on function type and name"""
        rules = []
        function_lower = function_name.lower()
        
        # Time series analysis rules
        if any(keyword in function_lower for keyword in ["variance", "rolling", "moving", "time_series"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For time series analysis, always ensure data is sorted by time column before applying rolling functions",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule", 
                    "content": "Use appropriate window sizes based on data frequency - daily data: 7-30 days, hourly data: 24-168 hours",
                    "source": "hardcoded"
                }
            ])
        
        # Cohort analysis rules
        if any(keyword in function_lower for keyword in ["cohort", "retention", "churn"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For cohort analysis, ensure user_id and date columns are properly formatted and contain no null values",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Use consistent time periods (monthly, weekly) for cohort calculations to ensure comparability",
                    "source": "hardcoded"
                }
            ])
        
        # Risk analysis rules
        if any(keyword in function_lower for keyword in ["var", "risk", "monte_carlo", "stress_test"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For risk analysis, use appropriate confidence levels (95% for VaR, 99% for stress testing)",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Ensure sufficient historical data (minimum 1 year) for reliable risk calculations",
                    "source": "hardcoded"
                }
            ])
        
        # Segmentation rules
        if any(keyword in function_lower for keyword in ["cluster", "segment", "dbscan", "kmeans"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For clustering, normalize numerical features before applying clustering algorithms",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Use appropriate distance metrics - Euclidean for continuous variables, Jaccard for categorical",
                    "source": "hardcoded"
                }
            ])
        
        # Funnel analysis rules
        if any(keyword in function_lower for keyword in ["funnel", "conversion", "step"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For funnel analysis, ensure event sequences are properly ordered by timestamp",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Handle duplicate events by keeping only the first occurrence in each funnel step",
                    "source": "hardcoded"
                }
            ])
        
        return rules
    
    def _create_function_definition(self, func_data: ComprehensiveFunctionData) -> Dict[str, Any]:
        """
        Create a properly formatted function definition from comprehensive function data.
        
        Args:
            func_data: Comprehensive function data
            
        Returns:
            Formatted function definition dictionary
        """
        function_definition = {}
        
        # Create parameters dictionary
        parameters = {}
        
        # Add required parameters
        for param in func_data.required_params:
            if isinstance(param, dict):
                param_name = param.get('name', 'unknown')
                parameters[param_name] = {
                    "type": param.get('type', 'Any'),
                    "description": param.get('description', ''),
                    "required": True
                }
            else:
                parameters[str(param)] = {
                    "type": "Any",
                    "description": str(param),
                    "required": True
                }
        
        # Add optional parameters
        for param in func_data.optional_params:
            if isinstance(param, dict):
                param_name = param.get('name', 'unknown')
                parameters[param_name] = {
                    "type": param.get('type', 'Any'),
                    "description": param.get('description', ''),
                    "required": False,
                    "default": param.get('default', None)
                }
            else:
                parameters[str(param)] = {
                    "type": "Any",
                    "description": str(param),
                    "required": False
                }
        
        function_definition['parameters'] = parameters
        
        # Add other function definition fields
        function_definition['outputs'] = func_data.outputs
        function_definition['data_requirements'] = func_data.data_requirements
        function_definition['use_cases'] = func_data.use_cases
        function_definition['tags'] = func_data.tags
        function_definition['keywords'] = func_data.keywords
        function_definition['complexity'] = func_data.complexity
        function_definition['confidence_score'] = func_data.confidence_score
        
        return function_definition
    
    def get_usage_data_for_function(self, function_name: str) -> Dict[str, Any]:
        """
        Get usage data for a specific function from the usage store.
        
        Args:
            function_name: Name of the function to get usage data for
            
        Returns:
            Dictionary containing usage data
        """
        try:
            if not self.enable_separate_collections:
                logger.warning("Separate collections not enabled, cannot fetch usage data")
                return {}
            
            # Debug: Log available collections
            logger.info(f"Available document stores: {list(self.document_stores.keys())}")
            logger.info(f"Collection names mapping: {self.collection_names}")
            
            # Get usage examples from the usage_examples collection
            usage_collection_name = self.collection_names.get("usage_examples")
            usage_collection = self.document_stores.get(usage_collection_name)
            
            # Fallback: try to find any collection with "usage" in the name
            if not usage_collection:
                for collection_key, collection_name in self.document_stores.items():
                    if "usage" in collection_key.lower():
                        usage_collection = collection_name
                        logger.info(f"Found usage collection by fallback: {collection_key}")
                        break
            
            if not usage_collection:
                logger.warning(f"Usage examples collection not found: {usage_collection_name}")
                logger.warning(f"Available collections: {list(self.document_stores.keys())}")
                return {}
            
            # Search for usage data for this function
            usage_results = usage_collection.semantic_search(
                query=function_name,
                k=10  # Get more results to find relevant usage data
            )
            
            usage_data = {
                "function_name": function_name,
                "usage_examples": [],
                "usage_patterns": [],
                "usage_descriptions": [],
                "total_examples": 0
            }
            
            for result in usage_results:
                if hasattr(result, 'page_content'):
                    content = result.page_content
                    metadata = result.metadata
                    
                    # Debug: Log the content and metadata
                    logger.info(f"Processing result for {function_name}:")
                    logger.info(f"  Content preview: {content[:200]}...")
                    logger.info(f"  Metadata: {metadata}")
                    
                    # Check if this result is for the target function
                    # Include results that match function name or contain the function name
                    is_relevant = (metadata.get('function_name') == function_name or 
                                 function_name in content or
                                 function_name.lower() in content.lower())
                    
                    if is_relevant:
                        
                        # Parse the content to extract usage information
                        try:
                            import json
                            content_data = json.loads(content)
                            logger.info(f"  Parsed JSON content: {list(content_data.keys())}")
                            
                            # Extract usage example - try multiple possible field names
                            example_text = None
                            description = ""
                            query = ""
                            
                            # Try different possible field names for examples
                            for field in ["example", "examples", "usage_example", "code", "code_example"]:
                                if field in content_data:
                                    if isinstance(content_data[field], list):
                                        example_text = content_data[field][0] if content_data[field] else None
                                    else:
                                        example_text = content_data[field]
                                    break
                            
                            # Try different possible field names for descriptions
                            for field in ["description", "desc", "summary", "explanation"]:
                                if field in content_data:
                                    description = content_data[field]
                                    break
                            
                            # Try different possible field names for queries
                            for field in ["query", "question", "prompt"]:
                                if field in content_data:
                                    query = content_data[field]
                                    break
                            
                            if example_text:
                                usage_data["usage_examples"].append({
                                    "example": example_text,
                                    "description": description,
                                    "query": query,
                                    "source": "usage_examples"
                                })
                                logger.info(f"  Added usage example: {example_text[:100]}...")
                            
                            # Extract description
                            if description:
                                usage_data["usage_descriptions"].append(description)
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"  JSON decode error: {e}")
                            # If not JSON, treat as plain text
                            usage_data["usage_examples"].append({
                                "example": content,
                                "description": metadata.get("description", ""),
                                "query": "",
                                "source": "usage_examples"
                            })
                            logger.info(f"  Added plain text example: {content[:100]}...")
                        except Exception as e:
                            logger.warning(f"  Error processing content: {e}")
                            # Fallback: add as plain text
                            usage_data["usage_examples"].append({
                                "example": content,
                                "description": metadata.get("description", ""),
                                "query": "",
                                "source": "usage_examples"
                            })
            
            # If no specific matches found, try to process all results
            if usage_data["total_examples"] == 0 and usage_results:
                logger.info(f"No specific matches found, processing all {len(usage_results)} results")
                for result in usage_results:
                    if hasattr(result, 'page_content'):
                        content = result.page_content
                        metadata = result.metadata
                        
                        # Try to parse as JSON first
                        try:
                            import json
                            content_data = json.loads(content)
                            
                            # Extract any example-like content
                            example_text = None
                            for field in ["example", "examples", "usage_example", "code", "code_example", "content", "text"]:
                                if field in content_data:
                                    if isinstance(content_data[field], list):
                                        example_text = content_data[field][0] if content_data[field] else None
                                    else:
                                        example_text = content_data[field]
                                    break
                            
                            if example_text:
                                usage_data["usage_examples"].append({
                                    "example": example_text,
                                    "description": content_data.get("description", ""),
                                    "query": content_data.get("query", ""),
                                    "source": "usage_examples"
                                })
                        except:
                            # Fallback: use content as example
                            usage_data["usage_examples"].append({
                                "example": content,
                                "description": metadata.get("description", ""),
                                "query": "",
                                "source": "usage_examples"
                            })
            
            # Remove duplicates and update counts
            usage_data["usage_examples"] = list({example["example"]: example for example in usage_data["usage_examples"]}.values())
            usage_data["total_examples"] = len(usage_data["usage_examples"])
            
            # Generate usage patterns from examples
            for example in usage_data["usage_examples"]:
                if "example" in example:
                    content = example["example"]
                    if function_name in content:
                        # Extract function call patterns
                        lines = content.split('\n')
                        for line in lines:
                            if function_name in line and '(' in line:
                                usage_data["usage_patterns"].append(line.strip())
                                break
            
            logger.info(f"Retrieved {usage_data['total_examples']} usage examples for {function_name}")
            return usage_data
            
        except Exception as e:
            logger.error(f"Error fetching usage data for {function_name}: {e}")
            return {
                "function_name": function_name,
                "usage_examples": [],
                "usage_patterns": [],
                "usage_descriptions": [],
                "total_examples": 0,
                "error": str(e)
            }
    
    def get_usage_data_for_functions(self, function_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get usage data for multiple functions from the usage store.
        
        Args:
            function_names: List of function names to get usage data for
            
        Returns:
            Dictionary mapping function names to their usage data
        """
        usage_data_map = {}
        
        for function_name in function_names:
            usage_data_map[function_name] = self.get_usage_data_for_function(function_name)
        
        return usage_data_map
    
    def get_all_usage_data(self) -> Dict[str, Any]:
        """
        Get usage data for all functions in the registry.
        
        Returns:
            Dictionary containing usage data for all functions
        """
        try:
            if not self.enable_separate_collections:
                logger.warning("Separate collections not enabled, cannot fetch usage data")
                return {}
            
            # Get all function names from the cache
            function_names = list(self.functions_cache.keys())
            
            if not function_names:
                logger.warning("No functions found in cache")
                return {}
            
            # Get usage data for all functions
            all_usage_data = self.get_usage_data_for_functions(function_names)
            
            # Calculate summary statistics
            total_examples = sum(data.get("total_examples", 0) for data in all_usage_data.values())
            functions_with_examples = sum(1 for data in all_usage_data.values() if data.get("total_examples", 0) > 0)
            
            return {
                "total_functions": len(function_names),
                "functions_with_examples": functions_with_examples,
                "total_examples": total_examples,
                "usage_data": all_usage_data
            }
            
        except Exception as e:
            logger.error(f"Error fetching all usage data: {e}")
            return {"error": str(e)}
    
    def _clean_data_list(self, data_list: List[Any], data_type: str) -> List[Dict[str, Any]]:
        """Clean and convert data list to proper format"""
        if not data_list:
            return []
        
        cleaned_list = []
        for item in data_list:
            if isinstance(item, dict):
                # Already a dictionary, use as is
                cleaned_list.append(item)
            elif isinstance(item, str):
                try:
                    # Try to parse as JSON
                    import json
                    parsed = json.loads(item)
                    if isinstance(parsed, dict):
                        cleaned_list.append(parsed)
                    elif isinstance(parsed, list):
                        # If it's a list, process each item
                        for sub_item in parsed:
                            if isinstance(sub_item, dict):
                                cleaned_list.append(sub_item)
                            else:
                                cleaned_list.append({data_type: str(sub_item), "type": "string"})
                    else:
                        cleaned_list.append({data_type: str(parsed), "type": "string"})
                except (json.JSONDecodeError, TypeError):
                    # If JSON parsing fails, create a simple dict
                    cleaned_list.append({data_type: item, "type": "string"})
            else:
                # Convert other types to string and create dict
                cleaned_list.append({data_type: str(item), "type": "unknown"})
        
        return cleaned_list


def initialize_enhanced_comprehensive_registry(
    collection_name: str = "comprehensive_ml_functions",
    force_recreate: bool = False,
    toolspecs_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs",
    instructions_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions",
    usage_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/usage_examples",
    code_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples",
    chroma_path: str = None,
    llm=None,
    retrieval_helper: Optional[RetrievalHelper] = None,
    enable_separate_collections: bool = True
) -> EnhancedComprehensiveRegistry:
    """
    Initialize the enhanced comprehensive registry.
    
    Args:
        collection_name: Name of the collection
        force_recreate: Whether to recreate existing collection
        toolspecs_path: Path to function specifications
        instructions_path: Path to instructions
        usage_examples_path: Path to usage examples
        code_examples_path: Path to code examples
        chroma_path: Path to ChromaDB storage (uses CHROMA_STORE_PATH if None)
        llm_model: LLM model to use for metadata generation
        llm: LangChain LLM instance for enhanced retrieval
        retrieval_helper: RetrievalHelper instance for comprehensive function retrieval
        enable_separate_collections: Whether to create separate collections for each data type
        
    Returns:
        Initialized EnhancedComprehensiveRegistry instance
    """
    registry = EnhancedComprehensiveRegistry(
        collection_name=collection_name,
        toolspecs_path=toolspecs_path,
        instructions_path=instructions_path,
        usage_examples_path=usage_examples_path,
        code_examples_path=code_examples_path,
        chroma_path=chroma_path,
        llm=llm,
        retrieval_helper=retrieval_helper,
        enable_separate_collections=enable_separate_collections
    )
    
    # Initialize the registry
    init_result = registry.initialize_registry(force_recreate=force_recreate)
    
    if init_result["status"] == "error":
        logger.error(f"Failed to initialize registry: {init_result['error']}")
        raise Exception(f"Registry initialization failed: {init_result['error']}")
    
    return registry


def main():
    """Demonstrate the enhanced registry with separate collections."""
    # Initialize registry with separate collections enabled
    print("Initializing Enhanced Comprehensive Registry with separate collections...")
    registry = initialize_enhanced_comprehensive_registry(
        collection_name="ml_functions_demo",
        enable_separate_collections=True,
        force_recreate=True
    )
    
    print(f"Registry initialized: {registry.initialized}")
    print("\n=== Collection Statistics ===")
    stats = registry.get_collection_statistics()
    for collection_type, info in stats.items():
        print(f"{collection_type}: {info['document_count']} documents - {info['status']}")
    
    # Example 1: Search in specific collection types
    print("\n=== Searching Toolspecs Collection ===")
    toolspecs_results = registry.search_by_collection_type(
        query="anomaly detection statistical methods",
        collection_type="toolspecs",
        n_results=3
    )
    print(f"Found {len(toolspecs_results)} results in toolspecs collection")
    for result in toolspecs_results[:2]:  # Show first 2 results
        print(f"- {result['metadata'].get('function_name', 'Unknown')}: {result['metadata'].get('category', 'Unknown')}")
    
    # Example 2: Search in instructions collection
    print("\n=== Searching Instructions Collection ===")
    instructions_results = registry.search_by_collection_type(
        query="how to configure parameters",
        collection_type="instructions",
        n_results=3
    )
    print(f"Found {len(instructions_results)} results in instructions collection")
    for result in instructions_results[:2]:
        print(f"- {result['metadata'].get('function_name', 'Unknown')}: {result['metadata'].get('instruction_title', 'Unknown')}")
    
    # Example 3: Search in code examples collection
    print("\n=== Searching Code Examples Collection ===")
    code_results = registry.search_by_collection_type(
        query="pandas dataframe operations",
        collection_type="code_examples",
        n_results=3
    )
    print(f"Found {len(code_results)} results in code_examples collection")
    for result in code_results[:2]:
        print(f"- {result['metadata'].get('function_name', 'Unknown')}: Snippet {result['metadata'].get('snippet_index', 'Unknown')}")
    
    # Example 4: Unified search across all collections
    print("\n=== Unified Search Across All Collections ===")
    unified_results = registry.search_unified(
        query="time series analysis forecasting",
        n_results=5
    )
    print(f"Found {len(unified_results)} results across all collections")
    for result in unified_results[:3]:
        collection_type = result['metadata'].get('collection_type', 'Unknown')
        function_name = result['metadata'].get('function_name', 'Unknown')
        print(f"- [{collection_type}] {function_name}")
    
    # Example 5: Search with filters
    print("\n=== Filtered Search (Complexity: intermediate) ===")
    filtered_results = registry.search_by_collection_type(
        query="data analysis",
        collection_type="toolspecs",
        n_results=3,
        complexity="intermediate"
    )
    print(f"Found {len(filtered_results)} intermediate complexity results")
    for result in filtered_results:
        print(f"- {result['metadata'].get('function_name', 'Unknown')}: {result['metadata'].get('complexity', 'Unknown')}")
    
    print("\n=== Demo Complete ===")
    print("The registry now supports:")
    print("1. Separate collections for different data types (toolspecs, instructions, usage_examples, code_examples, code)")
    print("2. Type-specific search with search_by_collection_type()")
    print("3. Unified search across all collections with search_unified()")
    print("4. Metadata filtering by category, complexity, etc.")
    print("5. Collection statistics and monitoring")


if __name__ == "__main__":
    main()