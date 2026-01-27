"""
Comprehensive Indexing Service
Indexes API docs, help docs, product descriptions, schema definitions, and column metadata
with support for ChromaDB and Qdrant, domain filtering, and comprehensive pipeline integration.
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.storage.documents import DocumentChromaStore, DocumentQdrantStore, sanitize_collection_name
from app.core.dependencies import get_chromadb_client, get_doc_store_provider
from app.core.settings import get_settings
from app.pipelines import (
    EntitiesExtractionPipeline,
    EvidenceExtractionPipeline,
    FieldsExtractionPipeline,
    MetadataGenerationPipeline,
    PatternRecognitionPipeline
)
from app.indexing.processors import (
    TableDescriptionProcessor,
    DBSchemaProcessor,
    DomainProcessor,
    ProductProcessor,
    CategoryMappingProcessor
)
from app.indexing.processors.compliance_document_processor import ComplianceDocumentProcessor
from app.indexing.storage.file_storage import FileStorage
from app.services.contextual_graph_storage import (
    ContextualGraphStorage,
    ContextualEdge,
    ContextDefinition,
    ControlContextProfile
)
from app.core.dependencies import get_vector_store_client


logger = logging.getLogger(__name__)


class ComprehensiveIndexingService:
    """Comprehensive indexing service for API docs, schemas, and product information."""
    
    def __init__(
        self,
        vector_store_type: str = "chroma",
        persistent_client=None,
        qdrant_client=None,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        llm: Optional[ChatOpenAI] = None,
        collection_prefix: str = "comprehensive_index",
        preview_mode: bool = False,
        preview_output_dir: str = "indexing_preview",
        enable_pipeline_processing: bool = True,
        pipeline_batch_size: int = 50,
        split_extractions: bool = True
    ):
        """
        Initialize the comprehensive indexing service.
        
        Args:
            vector_store_type: "chroma" or "qdrant"
            persistent_client: ChromaDB persistent client (for chroma)
            qdrant_client: Qdrant client (for qdrant)
            embeddings_model: Embeddings model instance
            llm: LLM instance for pipelines
            collection_prefix: Prefix for collection names (default: "comprehensive_index")
                              Creates prefixed collections like "comprehensive_index_table_definitions"
                              These are SEPARATE from project-based collections (unprefixed) used by
                              project_reader.py (e.g., "table_descriptions", "column_metadata").
                              Exception: "db_schema" is unprefixed (shared between both systems).
            preview_mode: If True, saves to files instead of indexing to database
            preview_output_dir: Directory for preview files
            enable_pipeline_processing: If True, processes documents through extraction pipelines.
                                       Set to False for structured data (schema/columns) to skip LLM calls.
            pipeline_batch_size: Batch size for pipeline processing when enabled (default: 50)
            split_extractions: If True, splits documents with combined extraction results into separate
                             documents (one per extraction type: control, entities, fields, etc.)
        """
        self.vector_store_type = vector_store_type.lower()
        self.collection_prefix = collection_prefix
        settings = get_settings()
        
        # Initialize embeddings
        self.embeddings_model = embeddings_model or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize LLM
        self.llm = llm or ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize file storage for preview mode
        self.preview_mode = preview_mode
        self.file_storage = FileStorage(output_dir=preview_output_dir) if preview_mode else None
        
        # Skip store initialization in preview mode to avoid ChromaDB access
        if preview_mode:
            self.stores = {}
            logger.info("Preview mode: Skipping document store initialization (no ChromaDB access)")
        else:
            # Initialize document stores only when not in preview mode
            self._init_document_stores(persistent_client, qdrant_client)
        
        # Initialize extraction pipelines (only if enabled)
        self.enable_pipeline_processing = enable_pipeline_processing
        self.pipeline_batch_size = pipeline_batch_size
        self.split_extractions = split_extractions
        if enable_pipeline_processing:
            self._init_pipelines()
        else:
            self.pipelines = {}
            self._pipelines_initialized = {}
        
        # Initialize extraction splitter if enabled
        if split_extractions:
            from app.indexing.utils import ExtractionSplitter
            self.extraction_splitter = ExtractionSplitter()
        else:
            self.extraction_splitter = None
        
        # Initialize processors
        self.table_description_processor = TableDescriptionProcessor()
        self.db_schema_processor = DBSchemaProcessor()
        self.domain_processor = DomainProcessor()
        self.product_processor = ProductProcessor()
        self.compliance_processor = ComplianceDocumentProcessor(
            llm=self.llm,
            enable_extraction=True
        )
        self.category_mapping_processor = CategoryMappingProcessor()
        
        # Initialize contextual graph storage (for edge creation and storage)
        # Only initialize if not in preview mode
        self.contextual_graph_storage = None
        if not preview_mode:
            try:
                vector_store_client = get_vector_store_client(
                    embeddings_model=self.embeddings_model
                )
                self.contextual_graph_storage = ContextualGraphStorage(
                    vector_store_client=vector_store_client,
                    embeddings_model=self.embeddings_model,
                    collection_prefix=collection_prefix
                )
                logger.info(f"Initialized contextual graph storage with prefix: {collection_prefix}")
            except Exception as e:
                logger.warning(f"Could not initialize contextual graph storage: {e}. Edge creation will be skipped.")
        
        logger.info(f"ComprehensiveIndexingService initialized with {vector_store_type}, preview_mode={preview_mode}, pipeline_processing={enable_pipeline_processing}")
    
    def _init_document_stores(self, persistent_client, qdrant_client):
        """Initialize document stores based on vector store type."""
        self.stores = {}
        
        if self.vector_store_type == "chroma":
            if persistent_client is None:
                persistent_client = get_chromadb_client()
            self.persistent_client = persistent_client
            
            # Create stores for different content types
            # Consolidated stores: use metadata.type to distinguish between content types (policy, product, risk, etc.)
            store_configs = {
                # API/Help docs (keep separate for now)
                "api_docs": {"tf_idf": True},
                "help_docs": {"tf_idf": True},
                "product_descriptions": {"tf_idf": True},
                # Schema collections (keep separate - used by project_reader.py)
                "table_definitions": {"tf_idf": True},
                "table_descriptions": {"tf_idf": True},  # Store using TableDescription structure
                "db_schema": {"tf_idf": True},  # DB schema documents in DBSchema format
                "category_mapping": {"tf_idf": True},  # Category mappings with grouped table descriptions
                "column_definitions": {"tf_idf": True},
                "schema_descriptions": {"tf_idf": True},
                "data_types": {"tf_idf": True},
                # Compliance collections (framework in metadata, not collection name)
                "compliance_controls": {"tf_idf": True},  # Compliance controls (all frameworks, filter by metadata.framework)
                # General collections (use metadata.type for filtering - e.g., type="policy", type="product", type="risk_control")
                "entities": {"tf_idf": True},  # General entities (metadata.type: policy, product, risk_entities, etc.)
                "evidence": {"tf_idf": True},  # General evidence (metadata.type: policy, risk_evidence, etc.)
                "fields": {"tf_idf": True},  # General fields (metadata.type: policy, risk_fields, etc.)
                "controls": {"tf_idf": True},  # General controls (metadata.type: policy, risk_control, compliance, etc.)
                "domain_knowledge": {"tf_idf": True},  # Domain knowledge (metadata.type: policy, product, risk, etc.)
            }
            
            for store_name, config in store_configs.items():
                # Special cases: schema-related collections should not use prefix (retrieval expects unprefixed names)
                # These collections are used by project_reader.py and retrieval_helper.py
                unprefixed_collections = {
                    "db_schema": "db_schema",
                    "table_descriptions": "table_descriptions",
                    "column_definitions": "column_metadata",  # Map to column_metadata to match project_reader
                }
                if store_name in unprefixed_collections:
                    collection_name = unprefixed_collections[store_name]
                elif self.collection_prefix:
                    collection_name = f"{self.collection_prefix}_{store_name}"
                else:
                    collection_name = store_name
                collection_name = sanitize_collection_name(collection_name)
                self.stores[store_name] = DocumentChromaStore(
                    persistent_client=self.persistent_client,
                    collection_name=collection_name,
                    embeddings_model=self.embeddings_model,
                    tf_idf=config.get("tf_idf", False)
                )
                logger.info(f"Initialized ChromaDB store: {collection_name}")
        
        elif self.vector_store_type == "qdrant":
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError("Qdrant dependencies not installed. Install with: pip install qdrant-client langchain-qdrant")
            
            if qdrant_client is None:
                qdrant_config = get_settings().get_vector_store_config()
                qdrant_client = QdrantClient(
                    host=qdrant_config.get("host", "localhost"),
                    port=qdrant_config.get("port", 6333)
                )
            self.qdrant_client = qdrant_client
            
            # Create stores for different content types
            # Consolidated stores: use metadata.type to distinguish between content types (policy, product, risk, etc.)
            store_configs = {
                # API/Help docs (keep separate for now)
                "api_docs": {"tf_idf": False},  # Qdrant TF-IDF support may vary
                "help_docs": {"tf_idf": False},
                "product_descriptions": {"tf_idf": False},
                # Schema collections (keep separate - used by project_reader.py)
                "table_definitions": {"tf_idf": False},
                "table_descriptions": {"tf_idf": False},  # Store using TableDescription structure
                "db_schema": {"tf_idf": False},  # DB schema documents in DBSchema format
                "column_definitions": {"tf_idf": False},
                "schema_descriptions": {"tf_idf": False},
                "data_types": {"tf_idf": False},
                # Compliance collections (framework in metadata, not collection name)
                "compliance_controls": {"tf_idf": False},  # Compliance controls (all frameworks, filter by metadata.framework)
                # General collections (use metadata.type for filtering - e.g., type="policy", type="product", type="risk_control")
                "entities": {"tf_idf": False},  # General entities (metadata.type: policy, product, risk_entities, etc.)
                "evidence": {"tf_idf": False},  # General evidence (metadata.type: policy, risk_evidence, etc.)
                "fields": {"tf_idf": False},  # General fields (metadata.type: policy, risk_fields, etc.)
                "controls": {"tf_idf": False},  # General controls (metadata.type: policy, risk_control, compliance, etc.)
                "domain_knowledge": {"tf_idf": False},  # Domain knowledge (metadata.type: policy, product, risk, etc.)
            }
            
            for store_name, config in store_configs.items():
                # Special cases: schema-related collections should not use prefix (retrieval expects unprefixed names)
                # These collections are used by project_reader.py and retrieval_helper.py
                unprefixed_collections = {
                    "db_schema": "db_schema",
                    "table_descriptions": "table_descriptions",
                    "column_definitions": "column_metadata",  # Map to column_metadata to match project_reader
                }
                if store_name in unprefixed_collections:
                    collection_name = unprefixed_collections[store_name]
                elif self.collection_prefix:
                    collection_name = f"{self.collection_prefix}_{store_name}"
                else:
                    collection_name = store_name
                collection_name = sanitize_collection_name(collection_name)
                self.stores[store_name] = DocumentQdrantStore(
                    qdrant_client=self.qdrant_client,
                    collection_name=collection_name,
                    embeddings_model=self.embeddings_model,
                    tf_idf=config.get("tf_idf", False)
                )
                logger.info(f"Initialized Qdrant store: {collection_name}")
        
        else:
            raise ValueError(f"Unsupported vector_store_type: {self.vector_store_type}")
    
    def _normalize_framework_name(self, framework: str) -> str:
        """
        Normalize framework name to a consistent format for collection names.
        
        Examples:
            "SOC 2" -> "soc2"
            "SOC2" -> "soc2"
            "ISO 27001" -> "iso27001"
            "HIPAA" -> "hipaa"
            "PCI-DSS" -> "pcidss"
        
        Args:
            framework: Framework name (case-insensitive, may contain spaces/special chars)
            
        Returns:
            Normalized framework name (lowercase, no spaces/special chars)
        """
        if not framework:
            return "unknown"
        
        # Convert to lowercase
        normalized = framework.lower().strip()
        
        # Remove spaces, hyphens, underscores, and other special characters
        normalized = "".join(c for c in normalized if c.isalnum())
        
        return normalized if normalized else "unknown"
    
    def _get_or_create_framework_store(
        self,
        framework: str,
        content_type: str,
        tf_idf: bool = True
    ):
        """
        Get or create a store for a specific framework and content type.
        
        Creates stores dynamically with pattern: {framework}_{content_type}
        Examples:
            - soc2_documents
            - hipaa_entities
            - iso27001_requirements
        
        Args:
            framework: Framework name (will be normalized)
            content_type: Content type (documents, entities, context, requirements, evidence, fields)
            tf_idf: Whether to enable TF-IDF (default: True for ChromaDB)
            
        Returns:
            Document store instance
        """
        normalized_framework = self._normalize_framework_name(framework)
        store_name = f"{normalized_framework}_{content_type}"
        
        # Check if store already exists
        if store_name in self.stores:
            return self.stores[store_name]
        
        # Create store dynamically
        if self.collection_prefix:
            collection_name = f"{self.collection_prefix}_{store_name}"
        else:
            collection_name = store_name
        collection_name = sanitize_collection_name(collection_name)
        
        if self.vector_store_type == "chroma":
            store = DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name=collection_name,
                embeddings_model=self.embeddings_model,
                tf_idf=tf_idf
            )
            logger.info(f"Created ChromaDB store dynamically: {collection_name} (tf_idf={tf_idf})")
        elif self.vector_store_type == "qdrant":
            from app.storage.documents import DocumentQdrantStore
            store = DocumentQdrantStore(
                qdrant_client=self.qdrant_client,
                collection_name=collection_name,
                embeddings_model=self.embeddings_model,
                tf_idf=tf_idf
            )
            logger.info(f"Created Qdrant store dynamically: {collection_name} (tf_idf={tf_idf})")
        else:
            raise ValueError(f"Unsupported vector_store_type: {self.vector_store_type}")
        
        # Cache the store
        self.stores[store_name] = store
        return store
    
    def _init_pipelines(self):
        """Initialize extraction pipelines (lazy initialization on first use)."""
        self.pipelines = {
            "entities": EntitiesExtractionPipeline(llm=self.llm),
            "evidence": EvidenceExtractionPipeline(llm=self.llm),
            "fields": FieldsExtractionPipeline(llm=self.llm),
            "metadata": MetadataGenerationPipeline(llm=self.llm),
            "patterns": PatternRecognitionPipeline(llm=self.llm)
        }
        self._pipelines_initialized = {}  # Track which pipelines have been initialized
        
        logger.info("Pipelines created (will be initialized on first use)")
    
    async def _ensure_pipeline_initialized(self, pipeline_name: str):
        """Ensure a pipeline is initialized (lazy initialization)."""
        if pipeline_name not in self.pipelines:
            return
        
        if pipeline_name in self._pipelines_initialized:
            return
        
        pipeline = self.pipelines[pipeline_name]
        try:
            await pipeline.initialize()
            self._pipelines_initialized[pipeline_name] = True
            logger.info(f"Initialized pipeline: {pipeline_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize pipeline {pipeline_name}: {e}")
            self._pipelines_initialized[pipeline_name] = False
    
    async def index_api_docs(
        self,
        api_docs: Union[str, Dict, List[Dict]],
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index API documentation.
        
        Args:
            api_docs: API documentation (string, dict, or list of dicts)
            product_name: Name of the product
            domain: Optional domain filter (e.g., "Assets")
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Indexing API docs for product: {product_name}, domain: {domain}")
        
        # Convert to list of documents
        documents = self._prepare_documents(api_docs, "api_doc")
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="api_docs",
            product_name=product_name,
            domain=domain
        )
        
        # Add metadata
        for doc in processed_docs:
            doc.metadata.update({
                "content_type": "api_doc",
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
                **({"domain": domain} if domain else {})
            })
        
        # Store documents
        store = self.stores["api_docs"]
        try:
            # add_documents is synchronous for both ChromaDB and Qdrant
            result = store.add_documents(processed_docs)
        except Exception as e:
            logger.error(f"Error adding documents to store: {e}")
            result = None
        
        logger.info(f"Indexed {len(processed_docs)} API documents")
        return {
            "success": True,
            "documents_indexed": len(processed_docs),
            "store": "api_docs",
            "product_name": product_name,
            "domain": domain,
            "result": result
        }
    
    async def index_help_docs(
        self,
        help_docs: Union[str, Dict, List[Dict]],
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Index help documentation."""
        logger.info(f"Indexing help docs for product: {product_name}, domain: {domain}")
        
        documents = self._prepare_documents(help_docs, "help_doc")
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="help_docs",
            product_name=product_name,
            domain=domain
        )
        
        for doc in processed_docs:
            doc.metadata.update({
                "content_type": "help_doc",
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
                **({"domain": domain} if domain else {})
            })
        
        store = self.stores["help_docs"]
        try:
            result = store.add_documents(processed_docs)
        except Exception as e:
            logger.error(f"Error adding documents to store: {e}")
            result = None
        
        logger.info(f"Indexed {len(processed_docs)} help documents")
        return {
            "success": True,
            "documents_indexed": len(processed_docs),
            "store": "help_docs",
            "product_name": product_name,
            "domain": domain,
            "result": result
        }
    
    async def index_product_description(
        self,
        description: str,
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Index product description."""
        logger.info(f"Indexing product description for: {product_name}, domain: {domain}")
        
        doc = Document(
            page_content=description,
            metadata={
                "content_type": "product_description",
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
                **({"domain": domain} if domain else {})
            }
        )
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=[doc],
            content_type="product_descriptions",
            product_name=product_name,
            domain=domain
        )
        
        store = self.stores["product_descriptions"]
        try:
            result = store.add_documents(processed_docs)
        except Exception as e:
            logger.error(f"Error adding documents to store: {e}")
            result = None
        
        logger.info(f"Indexed product description for {product_name}")
        return {
            "success": True,
            "documents_indexed": len(processed_docs),
            "store": "product_descriptions",
            "product_name": product_name,
            "domain": domain,
            "result": result
        }
    
    async def index_product_info(
        self,
        product_name: str,
        product_purpose: Optional[str] = None,
        product_docs_link: Optional[str] = None,
        key_concepts: Optional[List[str]] = None,
        extendable_entities: Optional[List[Dict[str, Any]]] = None,
        extendable_docs: Optional[List[Dict[str, Any]]] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index comprehensive product information including purpose, docs, key concepts, and entities.
        
        Args:
            product_name: Name of the product (e.g., "Snyk")
            product_purpose: What the product does
            product_docs_link: Link to product documentation
            key_concepts: List of key concepts for the product
            extendable_entities: List of extendable entities (e.g., APIs, integrations)
            extendable_docs: List of extendable documentation references
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Indexing product information for: {product_name}, domain: {domain}")
        
        # Use ProductProcessor to create documents
        documents = self.product_processor.process_product_info(
            product_name=product_name,
            product_purpose=product_purpose,
            product_docs_link=product_docs_link,
            key_concepts=key_concepts,
            extendable_entities=extendable_entities,
            extendable_docs=extendable_docs,
            domain=domain,
            metadata=metadata
        )
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="product_info",
            product_name=product_name,
            domain=domain
        )
        
        # Route documents to general stores with type="product" in metadata
        # Mapping: product content types -> general stores
        results = {
            "domain_knowledge": 0,
            "entities": 0
        }
        
        # Group documents by content type and route to general stores
        by_store = {
            "domain_knowledge": [],
            "entities": []
        }
        
        for doc in processed_docs:
            content_type = doc.metadata.get("content_type", "unknown")
            
            # Set type="product" in metadata for filtering
            doc.metadata["type"] = "product"
            
            # Route to appropriate general store
            if content_type in ["product_purpose", "product_docs_link", "extendable_doc"]:
                # Purpose, docs, and extendable docs go to domain_knowledge
                by_store["domain_knowledge"].append(doc)
            elif content_type in ["product_key_concepts", "product_key_concept", "extendable_entity"]:
                # Key concepts and extendable entities go to entities store
                by_store["entities"].append(doc)
            else:
                # Default fallback to domain_knowledge
                by_store["domain_knowledge"].append(doc)
        
        # Store in general stores
        for store_name, docs in by_store.items():
            if docs and store_name in self.stores:
                try:
                    store = self.stores[store_name]
                    result = store.add_documents(docs)
                    results[store_name] = len(docs)
                    logger.info(f"Indexed {len(docs)} product documents to {store_name} (type=product)")
                except Exception as e:
                    logger.error(f"Error adding documents to {store_name}: {e}")
        
        total_indexed = sum(results.values())
        logger.info(f"Indexed {total_indexed} product information documents for {product_name}")
        
        return {
            "success": True,
            "documents_indexed": total_indexed,
            "product_name": product_name,
            "domain": domain,
            "breakdown": results
        }
    
    async def index_product_from_dict(
        self,
        product_data: Dict[str, Any],
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index product information from a dictionary.
        
        Args:
            product_data: Dictionary containing product information with keys:
                - product_name: Name of the product
                - product_purpose: What the product does
                - product_docs_link: Link to documentation
                - key_concepts: List of key concepts
                - extendable_entities: List of extendable entities
                - extendable_docs: List of extendable documentation
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        return await self.index_product_info(
            product_name=product_data.get("product_name", ""),
            product_purpose=product_data.get("product_purpose"),
            product_docs_link=product_data.get("product_docs_link"),
            key_concepts=product_data.get("key_concepts"),
            extendable_entities=product_data.get("extendable_entities"),
            extendable_docs=product_data.get("extendable_docs"),
            domain=domain,
            metadata=metadata
        )
    
    async def index_table_definition(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        description: Optional[str] = None,
        schema: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index table definition with columns.
        
        Args:
            table_name: Name of the table
            columns: List of column definitions (dict with name, type, description, etc.)
            description: Table description
            schema: Schema name
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
        """
        logger.info(f"Indexing table definition: {table_name}, domain: {domain}")
        
        # Create table definition document
        table_content = {
            "table_name": table_name,
            "schema": schema,
            "description": description,
            "columns": columns,
            "column_count": len(columns)
        }
        
        doc = Document(
            page_content=json.dumps(table_content, indent=2),
            metadata={
                "content_type": "table_definition",
                "table_name": table_name,
                "schema": schema,
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                "column_count": len(columns),
                **(metadata or {}),
                **({"domain": domain} if domain else {})
            }
        )
        
        # Skip pipeline processing for structured table definitions
        # They're already structured and don't need entity/field extraction
        processed_docs = [doc]
        
        # Preview mode: save to files instead of database
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=processed_docs,
                content_type="table_definitions",
                domain=domain,
                product_name=product_name,
                metadata={**(metadata or {}), "source": "mdl"}
            )
            result = {"preview_mode": True, "file_storage": file_result}
        else:
            store = self.stores["table_definitions"]
            try:
                result = store.add_documents(processed_docs)
            except Exception as e:
                logger.error(f"Error adding documents to store: {e}")
                result = None
        
        # Also index individual columns
        column_results = await self.index_column_definitions(
            table_name=table_name,
            columns=columns,
            schema=schema,
            product_name=product_name,
            domain=domain,
            metadata=metadata
        )
        
        logger.info(f"Indexed table definition: {table_name} with {len(columns)} columns")
        return {
            "success": True,
            "documents_indexed": len(processed_docs),
            "store": "table_definitions",
            "table_name": table_name,
            "columns_indexed": column_results.get("documents_indexed", 0),
            "domain": domain,
            "result": result,
            "preview_mode": self.preview_mode
        }
    
    async def index_column_definitions(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        schema: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Index column definitions."""
        logger.info(f"Indexing {len(columns)} columns for table: {table_name}, domain: {domain}")
        
        documents = []
        for column in columns:
            column_name = column.get("name", "")
            column_type = column.get("type", "")
            column_description = column.get("description", "")
            column_properties = column.get("properties", {})
            
            column_content = {
                "column_name": column_name,
                "table_name": table_name,
                "schema": schema,
                "type": column_type,
                "description": column_description,
                "properties": column_properties
            }
            
            doc = Document(
                page_content=json.dumps(column_content, indent=2),
                metadata={
                    "content_type": "column_definition",
                    "column_name": column_name,
                    "table_name": table_name,
                    "schema": schema,
                    "data_type": column_type,
                    "product_name": product_name,
                    "indexed_at": datetime.utcnow().isoformat(),
                    **(metadata or {}),
                    **({"domain": domain} if domain else {})
                }
            )
            documents.append(doc)
        
        # Skip pipeline processing for structured column definitions
        # They're already structured and don't need entity/field extraction
        processed_docs = documents
        
        # Preview mode: save to files instead of database
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=processed_docs,
                content_type="column_definitions",
                domain=domain,
                product_name=product_name,
                metadata={**(metadata or {}), "source": "mdl"}
            )
            result = {"preview_mode": True, "file_storage": file_result}
        else:
            store = self.stores["column_definitions"]
            try:
                result = store.add_documents(processed_docs)
            except Exception as e:
                logger.error(f"Error adding documents to store: {e}")
                result = None
        
        logger.info(f"Indexed {len(processed_docs)} column definitions")
        return {
            "success": True,
            "documents_indexed": len(processed_docs),
            "store": "column_definitions",
            "table_name": table_name,
            "domain": domain,
            "result": result,
            "preview_mode": self.preview_mode
        }
    
    async def _generate_schema_description(
        self,
        mdl_dict: Dict[str, Any],
        product_name: str,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive schema description using LLM.
        
        Args:
            mdl_dict: MDL dictionary
            product_name: Product name
            domain: Optional domain
            
        Returns:
            Dictionary with schema_description and categories
        """
        models = mdl_dict.get("models", [])
        if not models:
            return {
                "schema_description": "No tables found in schema.",
                "categories": []
            }
        
        # Collect table information for LLM analysis
        # Include all tables with full descriptions
        table_details = []
        for model in models:
            table_name = model.get("name", "")
            if not table_name:
                continue
                
            description = model.get("description", "")
            properties = model.get("properties", {})
            semantic_desc = properties.get("semantic_description", "")
            table_purpose = properties.get("table_purpose", "")
            business_context = properties.get("business_context", "")
            
            # Use the best available description
            full_description = description or semantic_desc or table_purpose or business_context or "No description available"
            
            table_details.append({
                "name": table_name,
                "description": full_description,
                "columns_count": len(model.get("columns", []))
            })
        
        # Create prompt for schema description generation
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a database schema analyst. Analyze the provided schema and generate:
1. A comprehensive schema description that includes:
   - An overview explaining what this schema is used for
   - A list of ALL tables with their descriptions
   - Key capabilities and use cases
2. Categories that best describe the types of data and entities in this schema (e.g., "assets", "groups", "projects", "users", "security", "compliance", "vulnerabilities", "dependencies", etc.)

The schema description should:
- Start with 2-3 paragraphs explaining the overall purpose and structure
- Then list ALL tables with their names and descriptions in a structured format
- End with key capabilities and use cases
- Format tables as: "Table Name: [description]"

Categories should be:
- Lowercase, plural nouns (e.g., "assets", "groups", "projects")
- Based on table names and their purposes
- Relevant for search and retrieval
- Return as a list (can be empty if no clear categories)

Return a JSON object with:
{{
    "schema_description": "Overview paragraphs...\\n\\nTables:\\nTable Name 1: [description]\\nTable Name 2: [description]\\n...\\n\\nKey capabilities...",
    "categories": ["category1", "category2", ...]
}}"""),
            ("human", """Analyze this schema:

Product: {product_name}
Schema: {schema}
Catalog: {catalog}
Total Tables: {total_tables}

Table Details:
{table_details}

Generate the schema description with all tables listed and categories.""")
        ])
        
        try:
            chain = prompt | self.llm | JsonOutputParser()
            result = await chain.ainvoke({
                "product_name": product_name,
                "schema": mdl_dict.get("schema", "public"),
                "catalog": mdl_dict.get("catalog", ""),
                "total_tables": len(models),
                "table_details": json.dumps(table_details, indent=2)
            })
            
            return {
                "schema_description": result.get("schema_description", ""),
                "categories": result.get("categories", [])
            }
        except Exception as e:
            logger.warning(f"Error generating schema description with LLM: {e}. Using fallback.")
            # Fallback: generate basic description with all tables listed
            categories = self._detect_categories_from_tables(models)
            
            # Build fallback description with all tables
            description_parts = [
                f"This schema contains {len(models)} tables for {product_name}, managing various data entities and relationships.",
                "",
                "Tables:"
            ]
            
            for model in models:
                table_name = model.get("name", "")
                if not table_name:
                    continue
                description = model.get("description", "")
                properties = model.get("properties", {})
                semantic_desc = properties.get("semantic_description", "")
                table_purpose = properties.get("table_purpose", "")
                
                table_desc = description or semantic_desc or table_purpose or "No description available"
                description_parts.append(f"{table_name}: {table_desc}")
            
            return {
                "schema_description": "\n".join(description_parts),
                "categories": categories
            }
    
    def _detect_categories_from_tables(self, models: List[Dict[str, Any]]) -> List[str]:
        """
        Detect categories from table names and descriptions.
        
        Args:
            models: List of table/model dictionaries
            
        Returns:
            List of detected categories (lowercase, plural)
        """
        # Common category keywords
        category_keywords = {
            "asset": ["asset", "resource", "item", "entity"],
            "group": ["group", "team", "organization", "org"],
            "project": ["project", "workspace", "space"],
            "user": ["user", "account", "member", "person"],
            "security": ["security", "vulnerability", "threat", "risk", "issue", "finding", "scan"],
            "compliance": ["compliance", "policy", "control", "audit"],
            "dependency": ["dependency", "package", "library", "component"],
            "scan": ["scan", "test", "check", "analysis"],
            "license": ["license", "licensing", "legal"],
            "notification": ["notification", "alert", "event", "log"],
            "integration": ["integration", "app", "connection", "link"],
            "report": ["report", "dashboard", "analytics", "metric"]
        }
        
        detected_categories = set()
        table_names = [m.get("name", "").lower() for m in models]
        descriptions = []
        
        for model in models:
            desc = (model.get("description", "") + " " + 
                   model.get("properties", {}).get("semantic_description", "")).lower()
            descriptions.append(desc)
        
        # Check each category
        for category, keywords in category_keywords.items():
            # Check table names
            if any(keyword in name for name in table_names for keyword in keywords):
                detected_categories.add(category)
            # Check descriptions
            if any(keyword in desc for desc in descriptions for keyword in keywords):
                detected_categories.add(category)
        
        return sorted(list(detected_categories))
    
    def _detect_table_categories(
        self,
        table_name: str,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
        columns: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Detect categories for a single table based on its name, description, and columns.
        
        Args:
            table_name: Name of the table
            description: Table description
            properties: Table properties dictionary
            columns: List of column definitions
            
        Returns:
            List of detected categories (lowercase, plural)
        """
        # Common category keywords - ordered by specificity (more specific first)
        # Use word boundaries for more precise matching where possible
        category_keywords = {
            # Access/permission related - check first as it's very specific
            "access": ["access request", "access control", "access management", "permission", "authorization", "access right"],
            # Asset related - be more specific to avoid false positives
            "asset": ["asset management", "asset attribute", "asset data", "software asset", "asset tracking"],
            # Group/organization related
            "group": ["group", "team", "organization", "org"],
            # Project related
            "project": ["project", "workspace", "space"],
            # User related
            "user": ["user", "account", "member", "person"],
            # Security related
            "security": ["security", "vulnerability", "threat", "risk", "issue", "finding", "scan"],
            # Compliance related
            "compliance": ["compliance", "policy", "control", "audit"],
            # Dependency related
            "dependency": ["dependency", "package", "library", "component"],
            # Scan related
            "scan": ["scan", "test", "check", "analysis"],
            # License related
            "license": ["license", "licensing", "legal"],
            # Notification related
            "notification": ["notification", "alert", "event", "log"],
            # Integration related
            "integration": ["integration", "app", "connection", "link"],
            # Report related
            "report": ["report", "dashboard", "analytics", "metric"]
        }
        
        detected_categories = set()
        table_name_lower = table_name.lower()
        
        # Combine all text to search
        search_text = table_name_lower + " "
        if description:
            search_text += description.lower() + " "
        if properties:
            semantic_desc = properties.get("semantic_description", "").lower()
            table_purpose = properties.get("table_purpose", "").lower()
            business_context = properties.get("business_context", "").lower()
            search_text += semantic_desc + " " + table_purpose + " " + business_context + " "
        if columns:
            column_names = " ".join([col.get("name", "").lower() for col in columns])
            search_text += column_names
        
        # Priority check: If table name contains "access", add access category first
        # This prevents false positives from generic words like "resource" in descriptions
        if "access" in table_name_lower:
            detected_categories.add("access")
        
        # Check each category - use more precise matching
        for category, keywords in category_keywords.items():
            # Skip access if already detected from table name (to avoid re-checking)
            if category == "access" and "access" in detected_categories:
                continue
            
            # Check multi-word phrases first (more specific, less false positives)
            multi_word_keywords = [kw for kw in keywords if " " in kw]
            single_word_keywords = [kw for kw in keywords if " " not in kw]
            
            # Check multi-word phrases first
            matched = False
            for keyword in multi_word_keywords:
                if keyword in search_text:
                    detected_categories.add(category)
                    matched = True
                    break
            
            # Check single-word keywords only if multi-word didn't match
            # Use word boundaries to avoid substring matches
            if not matched:
                for keyword in single_word_keywords:
                    # Match whole word only (not substring) using word boundaries
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, search_text):
                        detected_categories.add(category)
                        break
        
        return sorted(list(detected_categories))
    
    async def index_schema_from_mdl(
        self,
        mdl_data: Union[str, Dict],
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None,
        use_table_description_structure: bool = True
    ) -> Dict[str, Any]:
        """
        Index schema from MDL (Model Definition Language) file.
        
        Args:
            mdl_data: MDL data as string (JSON) or dict
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            use_table_description_structure: If True, uses TableDescription structure from table_description.py
        """
        logger.info(f"Indexing schema from MDL for product: {product_name}, domain: {domain}")
        
        # Parse MDL if string
        if isinstance(mdl_data, str):
            mdl_dict = json.loads(mdl_data)
        else:
            mdl_dict = mdl_data
        
        results = {
            "tables_indexed": 0,
            "columns_indexed": 0,
            "tables": [],
            "table_descriptions_indexed": 0
        }
        
        # Index using TableDescription structure if requested
        if use_table_description_structure:
            table_desc_result = await self._index_table_descriptions_from_mdl(
                mdl_dict=mdl_dict,
                product_name=product_name,
                domain=domain,
                metadata=metadata
            )
            results["table_descriptions_indexed"] = table_desc_result.get("documents_written", 0)
        
        # Collect all table and column definitions for batch saving in preview mode
        all_table_definitions = []
        all_column_definitions = []
        
        # Process each model/table
        for model in mdl_dict.get("models", []):
            table_name = model.get("name", "")
            if not table_name:
                continue
            
            columns = model.get("columns", [])
            description = model.get("description", "")
            properties = model.get("properties", {})
            
            # Detect categories for this table
            table_categories = self._detect_table_categories(
                table_name=table_name,
                description=description,
                properties=properties,
                columns=columns
            )
            
            # Create table definition document in the same format as project_reader.py TableDescription
            # Extract column names as comma-separated string
            column_names = [col.get("name", "") for col in columns if col.get("name")]
            columns_str = ', '.join(column_names)
            
            # Use the same format as TableDescription: stringified dict with name, mdl_type, type, description, columns
            content_dict = {
                "name": table_name,
                "mdl_type": "TABLE_SCHEMA",  # All models are TABLE_SCHEMA
                "type": "TABLE_DESCRIPTION",
                "description": description,
                "columns": columns_str  # Comma-separated string, not list
            }
            
            table_doc = Document(
                page_content=str(content_dict),  # Stringified dict, not JSON
                metadata={
                    "type": "TABLE_DESCRIPTION",  # Match project_reader.py format
                    "mdl_type": "TABLE_SCHEMA",
                    "name": table_name,
                    "description": description,
                    "content_type": "table_definition",
                    "table_name": table_name,  # Keep for backward compatibility
                    "schema": mdl_dict.get("schema", "public"),
                    "product_name": product_name,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "column_count": len(columns),
                    "categories": table_categories,  # Add categories to metadata
                    **(metadata or {}),
                    "mdl_catalog": mdl_dict.get("catalog", ""),
                    "mdl_schema": mdl_dict.get("schema", ""),
                    "table_properties": properties,
                    **({"domain": domain} if domain else {})
                }
            )
            all_table_definitions.append(table_doc)
            
            # Create column definition documents
            for column in columns:
                column_name = column.get("name", "")
                column_type = column.get("type", "")
                column_description = column.get("description", "")
                column_properties = column.get("properties", {})
                
                column_content = {
                    "column_name": column_name,
                    "table_name": table_name,
                    "schema": mdl_dict.get("schema", "public"),
                    "type": column_type,
                    "description": column_description,
                    "properties": column_properties
                }
                
                column_doc = Document(
                    page_content=json.dumps(column_content, indent=2),
                    metadata={
                        "content_type": "column_definition",
                        "column_name": column_name,
                        "table_name": table_name,
                        "schema": mdl_dict.get("schema", "public"),
                        "data_type": column_type,
                        "product_name": product_name,
                        "indexed_at": datetime.utcnow().isoformat(),
                        **(metadata or {}),
                        "mdl_catalog": mdl_dict.get("catalog", ""),
                        "mdl_schema": mdl_dict.get("schema", ""),
                        **({"domain": domain} if domain else {})
                    }
                )
                all_column_definitions.append(column_doc)
            
            results["tables_indexed"] += 1
            results["columns_indexed"] += len(columns)
            results["tables"].append({
                "table_name": table_name,
                "columns_count": len(columns),
                "indexed": True
            })
        
        # Save all table and column definitions in batch if in preview mode
        if self.preview_mode:
            if all_table_definitions:
                table_file_result = self.file_storage.save_documents(
                    documents=all_table_definitions,
                    content_type="table_definitions",
                    domain=domain,
                    product_name=product_name,
                    metadata={**(metadata or {}), "source": "mdl"}
                )
                results["table_definitions_file_storage"] = table_file_result
            
            if all_column_definitions:
                column_file_result = self.file_storage.save_documents(
                    documents=all_column_definitions,
                    content_type="column_definitions",
                    domain=domain,
                    product_name=product_name,
                    metadata={**(metadata or {}), "source": "mdl"}
                )
                results["column_definitions_file_storage"] = column_file_result
        else:
            # In database mode, add all documents directly to stores
            if all_table_definitions:
                store = self.stores["table_definitions"]
                try:
                    store.add_documents(all_table_definitions)
                    logger.info(f"Indexed {len(all_table_definitions)} table definitions to database")
                except Exception as e:
                    logger.error(f"Error adding table definitions to store: {e}")
            
            if all_column_definitions:
                store = self.stores["column_definitions"]
                try:
                    store.add_documents(all_column_definitions)
                    logger.info(f"Indexed {len(all_column_definitions)} column definitions to database")
                except Exception as e:
                    logger.error(f"Error adding column definitions to store: {e}")
        
        # Note: Schema descriptions are now handled by project_reader.py via table_description component
        # No need to index schema_descriptions here - project_reader.py handles this through db_schema and table_description components
        
        logger.info(f"Indexed schema with {results['tables_indexed']} tables, {results['columns_indexed']} columns, and {results['table_descriptions_indexed']} table descriptions")
        return {
            "success": True,
            **results,
            "product_name": product_name,
            "domain": domain
        }
    
    async def index_db_schema_from_mdl(
        self,
        mdl_data: Union[str, Dict],
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index DB schema from MDL using DBSchemaProcessor.
        
        Args:
            mdl_data: MDL data as string (JSON) or dict
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Indexing DB schema from MDL for product: {product_name}, domain: {domain}")
        
        # Parse MDL if string
        if isinstance(mdl_data, str):
            mdl_dict = json.loads(mdl_data)
        else:
            mdl_dict = mdl_data
        
        # Use DBSchemaProcessor
        try:
            documents = await self.db_schema_processor.process_mdl(
                mdl=mdl_dict,
                project_id=product_name,
                product_name=product_name,
                domain=domain,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error processing DB schema: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e)
            }
        
        # Preview mode: save to files
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=documents,
                content_type="db_schema",
                domain=domain,
                product_name=product_name,
                metadata={**(metadata or {}), "source": "mdl"}
            )
            return {
                "success": True,
                "preview_mode": True,
                "documents_indexed": len(documents),
                "file_storage": file_result,
                "product_name": product_name,
                "domain": domain
            }
        
        # Store documents in db_schema store (preferred) or table_definitions as fallback
        store = self.stores.get("db_schema") or self.stores.get("table_definitions")
        if not store:
            logger.warning("No store available for DB schema, skipping")
            return {"documents_indexed": 0}
        
        store_name = "db_schema" if "db_schema" in self.stores else "table_definitions"
        try:
            result = store.add_documents(documents)
            logger.info(f"Indexed {len(documents)} DB schema documents to {store_name} store")
            return {
                "success": True,
                "documents_indexed": len(documents),
                "store": store_name,
                "product_name": product_name,
                "domain": domain,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding DB schema documents: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e)
            }
    
    async def index_category_mappings_from_mdl(
        self,
        mdl_data: Union[str, Dict],
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index category mappings from MDL.
        Creates documents grouped by category, each containing a list of table descriptions.
        This enables efficient category-based search to identify relevant tables.
        
        Args:
            mdl_data: MDL data as string (JSON) or dict
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Indexing category mappings from MDL for product: {product_name}, domain: {domain}")
        
        # Parse MDL if string
        if isinstance(mdl_data, str):
            mdl_dict = json.loads(mdl_data)
        else:
            mdl_dict = mdl_data
        
        # Use CategoryMappingProcessor
        try:
            documents = await self.category_mapping_processor.process_mdl(
                mdl=mdl_dict,
                project_id=product_name,
                product_name=product_name,
                domain=domain,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error processing category mappings: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e)
            }
        
        # Preview mode: save to files
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=documents,
                content_type="category_mapping",
                domain=domain,
                product_name=product_name,
                metadata={**(metadata or {}), "source": "mdl"}
            )
            return {
                "success": True,
                "preview_mode": True,
                "documents_indexed": len(documents),
                "file_storage": file_result,
                "product_name": product_name,
                "domain": domain
            }
        
        # Store documents in category_mapping store
        store = self.stores.get("category_mapping")
        if not store:
            logger.warning("category_mapping store not available, skipping")
            return {"documents_indexed": 0}
        
        try:
            result = store.add_documents(documents)
            logger.info(f"Indexed {len(documents)} category mapping documents")
            return {
                "success": True,
                "documents_indexed": len(documents),
                "store": "category_mapping",
                "product_name": product_name,
                "domain": domain,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding category mapping documents: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e)
            }
    
    async def _index_table_descriptions_from_mdl(
        self,
        mdl_dict: Dict[str, Any],
        product_name: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index table descriptions using TableDescription structure from table_description.py.
        
        This creates documents in the same format as TableDescriptionChunker.
        """
        logger.info("Indexing table descriptions using TableDescription structure")
        
        # Use TableDescriptionProcessor
        try:
            documents = await self.table_description_processor.process_mdl(
                mdl=mdl_dict,
                project_id=product_name,
                product_name=product_name,
                domain=domain,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error processing table descriptions: {e}")
            return {"documents_written": 0, "error": str(e)}
        
        # Preview mode: save to files
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=documents,
                content_type="table_descriptions",
                domain=domain,
                product_name=product_name,
                metadata={**(metadata or {}), "source": "mdl"}
            )
            return {
                "documents_written": len(documents),
                "preview_mode": True,
                "file_storage": file_result
            }
        
        # Store documents
        store = self.stores.get("table_descriptions")
        if not store:
            logger.warning("table_descriptions store not available, skipping")
            return {"documents_written": 0}
        
        try:
            result = store.add_documents(documents)
            logger.info(f"Indexed {len(documents)} table descriptions using TableDescription structure")
            return {
                "documents_written": len(documents),
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding table description documents: {e}")
            return {"documents_written": 0, "error": str(e)}
    
    async def index_domain_knowledge(
        self,
        knowledge: Union[str, Dict, List[Dict]],
        domain: str,
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Index domain-specific knowledge."""
        logger.info(f"Indexing domain knowledge for domain: {domain}")
        
        # Use DomainProcessor for domain knowledge
        if isinstance(knowledge, str):
            doc = self.domain_processor.process_domain_knowledge(
                knowledge=knowledge,
                domain=domain,
                product_name=product_name,
                metadata=metadata
            )
            documents = [doc]
        else:
            # For dict/list, use prepare_documents
            documents = self._prepare_documents(knowledge, "domain_knowledge")
            for doc in documents:
                doc.metadata.update({
                    "content_type": "domain_knowledge",
                    "domain": domain,
                    "product_name": product_name,
                    "indexed_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                })
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="domain_knowledge",
            product_name=product_name,
            domain=domain
        )
        
        store = self.stores["domain_knowledge"]
        try:
            result = store.add_documents(processed_docs)
        except Exception as e:
            logger.error(f"Error adding documents to store: {e}")
            result = None
        
        logger.info(f"Indexed {len(processed_docs)} domain knowledge documents")
        return {
            "success": True,
            "documents_indexed": len(processed_docs),
            "store": "domain_knowledge",
            "domain": domain,
            "product_name": product_name,
            "result": result
        }
    
    async def index_domain_config(
        self,
        domain_config: Dict[str, Any],
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index domain configuration using DomainProcessor.
        
        Args:
            domain_config: Domain configuration dictionary (from domain_config.py)
            product_name: Product name
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Indexing domain config: {domain_config.get('domain_name', 'unknown')}")
        
        # Use DomainProcessor
        documents = self.domain_processor.process_domain_config(
            domain_config=domain_config,
            product_name=product_name,
            metadata=metadata
        )
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="domain_knowledge",
            product_name=product_name,
            domain=domain_config.get("domain_name")
        )
        
        # Store in domain_knowledge store
        store = self.stores["domain_knowledge"]
        try:
            result = store.add_documents(processed_docs)
            logger.info(f"Indexed {len(processed_docs)} domain config documents")
            return {
                "success": True,
                "documents_indexed": len(processed_docs),
                "store": "domain_knowledge",
                "domain": domain_config.get("domain_name"),
                "product_name": product_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding domain config documents: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e)
            }
    
    def _prepare_documents(
        self,
        content: Union[str, Dict, List[Dict]],
        content_type: str
    ) -> List[Document]:
        """Prepare documents from various input formats."""
        documents = []
        
        if isinstance(content, str):
            # Single string document
            documents.append(Document(
                page_content=content,
                metadata={"content_type": content_type}
            ))
        elif isinstance(content, dict):
            # Single dict document
            page_content = content.get("content", content.get("text", json.dumps(content)))
            metadata = content.get("metadata", {})
            metadata["content_type"] = content_type
            documents.append(Document(
                page_content=page_content,
                metadata=metadata
            ))
        elif isinstance(content, list):
            # List of documents
            for item in content:
                if isinstance(item, str):
                    documents.append(Document(
                        page_content=item,
                        metadata={"content_type": content_type}
                    ))
                elif isinstance(item, dict):
                    page_content = item.get("content", item.get("text", json.dumps(item)))
                    metadata = item.get("metadata", {})
                    metadata["content_type"] = content_type
                    documents.append(Document(
                        page_content=page_content,
                        metadata=metadata
                    ))
        
        return documents
    
    async def _process_single_document(
        self,
        doc: Document,
        content_type: str
    ) -> Document:
        """Process a single document through extraction pipelines."""
        try:
            # Extract entities
            entities_result = await self.pipelines["entities"].run(
                inputs={
                    "text": doc.page_content,
                    "context_id": f"{content_type}_{uuid4()}",
                    "context_metadata": doc.metadata
                }
            )
            
            # Extract fields
            fields_result = await self.pipelines["fields"].run(
                inputs={
                    "text": doc.page_content,
                    "context_id": f"{content_type}_{uuid4()}",
                    "context_metadata": doc.metadata
                }
            )
            
            # Enhance document with extracted information
            enhanced_content = doc.page_content
            if entities_result.get("success"):
                entities = entities_result.get("data", {}).get("entities", [])
                if entities:
                    enhanced_content += f"\n\nExtracted Entities: {json.dumps(entities, indent=2)}"
            
            if fields_result.get("success"):
                fields = fields_result.get("data", {}).get("extracted_fields", [])
                if fields:
                    enhanced_content += f"\n\nExtracted Fields: {json.dumps(fields, indent=2)}"
            
            # Create enhanced document
            enhanced_doc = Document(
                page_content=enhanced_content,
                metadata={
                    **doc.metadata,
                    "entities_extracted": entities_result.get("data", {}).get("entities_count", 0),
                    "fields_extracted": fields_result.get("data", {}).get("edges_count", 0)
                }
            )
            return enhanced_doc
            
        except Exception as e:
            logger.warning(f"Error processing document through pipelines: {e}")
            # Use original document if pipeline processing fails
            return doc
    
    async def _process_through_pipelines(
        self,
        documents: List[Document],
        content_type: str,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        batch_size: Optional[int] = None
    ) -> List[Document]:
        """
        Process documents through extraction pipelines in batches for parallel processing.
        
        Args:
            documents: List of documents to process
            content_type: Content type identifier
            product_name: Optional product name
            domain: Optional domain
            batch_size: Number of documents to process concurrently. 
                       If None, uses self.pipeline_batch_size (default: 50 when enabled)
        """
        # Skip pipeline processing if disabled
        if not self.enable_pipeline_processing:
            logger.debug(f"Skipping pipeline processing for {len(documents)} documents (pipeline processing disabled)")
            return documents
        
        # Use configured batch size if not provided
        if batch_size is None:
            batch_size = self.pipeline_batch_size
        
        # Ensure pipelines are initialized (lazy initialization)
        await self._ensure_pipeline_initialized("entities")
        await self._ensure_pipeline_initialized("fields")
        
        if not documents:
            return []
        
        processed_docs = []
        total_docs = len(documents)
        
        # Process in batches
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_docs + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} documents)")
            
            # Process batch concurrently
            batch_tasks = [
                self._process_single_document(doc, content_type)
                for doc in batch
            ]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Handle results and exceptions
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.warning(f"Error in batch processing: {result}")
                        # Add original document if processing failed
                        # We can't identify which doc failed, so we'll skip it
                        continue
                    processed_docs.append(result)
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                # Fallback: add original documents if batch fails
                processed_docs.extend(batch)
        
        logger.info(f"Processed {len(processed_docs)}/{total_docs} documents through pipelines")
        
        # Split extractions into separate documents if enabled
        if self.split_extractions and self.extraction_splitter:
            logger.info("Splitting extraction results into separate documents")
            split_docs = self.extraction_splitter.split_documents(processed_docs)
            logger.info(f"Split {len(processed_docs)} documents into {len(split_docs)} separate documents")
            return split_docs
        
        return processed_docs
    
    async def search(
        self,
        query: str,
        content_types: Optional[List[str]] = None,
        domain: Optional[str] = None,
        product_name: Optional[str] = None,
        framework: Optional[str] = None,
        k: int = 5,
        search_type: str = "semantic"
    ) -> Dict[str, Any]:
        """
        Search across indexed content.
        
        Args:
            query: Search query
            content_types: List of content types to search (None = all)
            domain: Domain filter
            product_name: Product name filter
            framework: Framework filter (e.g., "SOC2", "HIPAA", "ISO 27001") - filters by metadata.framework
            k: Number of results
            search_type: "semantic", "bm25", "tfidf", "tfidf_only"
        """
        logger.info(f"Searching with query: {query}, domain: {domain}, framework: {framework}, content_types: {content_types}")
        
        all_results = []
        
        # Determine which stores to search
        stores_to_search = []
        if content_types:
            for content_type in content_types:
                store_name = self._content_type_to_store(content_type)
                if store_name in self.stores:
                    stores_to_search.append((store_name, content_type))
        else:
            # Search all stores
            for store_name, store in self.stores.items():
                stores_to_search.append((store_name, self._store_to_content_type(store_name)))
        
        # Search each store
        for store_name, content_type in stores_to_search:
            store = self.stores[store_name]
            
            # Build where clause for filtering
            where_clause = {}
            if domain:
                where_clause["domain"] = domain
            if product_name:
                where_clause["product_name"] = product_name
            if framework:
                # Filter by framework stored in metadata
                where_clause["framework"] = framework
            
            try:
                if search_type == "semantic":
                    results = store.semantic_search(query, k=k, where=where_clause if where_clause else None)
                elif search_type == "bm25":
                    results = store.semantic_search_with_bm25(query, k=k, where=where_clause if where_clause else None)
                elif search_type == "tfidf":
                    results = store.semantic_search_with_tfidf(query, k=k, where=where_clause if where_clause else None)
                elif search_type == "tfidf_only":
                    results = store.tfidf_search(query, k=k, where=where_clause if where_clause else None)
                else:
                    results = store.semantic_search(query, k=k, where=where_clause if where_clause else None)
                
                # Add content type to results
                for result in results:
                    result["content_type"] = content_type
                    result["store"] = store_name
                
                all_results.extend(results)
                
            except Exception as e:
                logger.warning(f"Error searching store {store_name}: {e}")
        
        # Sort by score and limit to k
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_results = all_results[:k]
        
        logger.info(f"Found {len(all_results)} results")
        return {
            "success": True,
            "results": all_results,
            "count": len(all_results),
            "query": query,
            "domain": domain,
            "product_name": product_name,
            "framework": framework
        }
    
    async def index_soc2_controls(
        self,
        file_path: Union[str, Path],
        domain: Optional[str] = "compliance",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index SOC2 controls from PDF or Excel file.
        
        Note: This is a convenience method that uses framework="SOC2".
        For other frameworks, use index_compliance_controls() with framework parameter.
        
        Args:
            file_path: Path to PDF or Excel file containing SOC2 controls
            domain: Domain filter (default: "compliance")
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        # Use the generic compliance controls indexing with SOC2 framework
        return await self.index_compliance_controls(
            file_path=file_path,
            framework="SOC2",
            domain=domain,
            metadata=metadata
        )
    
    async def index_compliance_controls(
        self,
        file_path: Union[str, Path],
        framework: str,
        domain: Optional[str] = "compliance",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index compliance controls from PDF or Excel file for any framework.
        
        Args:
            file_path: Path to PDF or Excel file containing compliance controls
            framework: Compliance framework name (e.g., "SOC2", "HIPAA", "ISO 27001")
            domain: Domain filter (default: "compliance")
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Indexing {framework} controls from: {file_path}")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine file type
        file_ext = file_path.suffix.lower()
        
        # Update metadata with framework
        if metadata is None:
            metadata = {}
        metadata["framework"] = framework
        
        if file_ext == ".pdf":
            documents = await self.compliance_processor.process_pdf_document(
                pdf_path=file_path,
                document_type="controls",
                domain=domain,
                metadata=metadata
            )
        elif file_ext in [".xlsx", ".xls"]:
            documents = await self.compliance_processor.process_excel_document(
                excel_path=file_path,
                document_type="controls",
                domain=domain,
                metadata=metadata
            )
        else:
            raise ValueError(f"Unsupported file type: {file_ext}. Supported: .pdf, .xlsx, .xls")
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="controls",
            product_name=framework,
            domain=domain
        )
        
        # Preview mode: save to files
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=processed_docs,
                content_type=f"{self._normalize_framework_name(framework)}_controls",
                domain=domain,
                product_name=framework,
                metadata={**(metadata or {}), "source_file": str(file_path)}
            )
            return {
                "success": True,
                "preview_mode": True,
                "documents_indexed": len(processed_docs),
                "file_storage": file_result,
                "framework": framework,
                "domain": domain,
                "file_path": str(file_path)
            }
        
        # Store documents in unified compliance_controls collection
        # Framework is stored in metadata for filtering
        store = self.stores.get("compliance_controls")
        if not store:
            logger.warning("Compliance controls store not available")
            return {"documents_indexed": 0, "error": "Store not available", "framework": framework}
        
        # Ensure all documents have framework in metadata
        for doc in processed_docs:
            if "framework" not in doc.metadata:
                doc.metadata["framework"] = framework
        
        try:
            result = store.add_documents(processed_docs)
            logger.info(f"Indexed {len(processed_docs)} {framework} control documents to compliance_controls")
            
            # Create contextual edges for compliance controls
            edges_created = 0
            if self.contextual_graph_storage and not self.preview_mode:
                try:
                    edges = await self._create_contextual_edges_for_compliance_controls(
                        processed_docs=processed_docs,
                        framework=framework,
                        domain=domain
                    )
                    if edges:
                        edge_ids = await self.contextual_graph_storage.save_contextual_edges(edges)
                        # Save to postgres as well
                        await self.contextual_graph_storage.save_edges_to_postgres(edges)
                        edges_created = len(edge_ids)
                        logger.info(f"Created {edges_created} contextual edges for compliance controls")
                except Exception as e:
                    logger.warning(f"Error creating contextual edges for compliance controls: {e}")
            
            return {
                "success": True,
                "documents_indexed": len(processed_docs),
                "store": "compliance_controls",
                "framework": framework,
                "domain": domain,
                "file_path": str(file_path),
                "result": result,
                "contextual_edges_created": edges_created
            }
        except Exception as e:
            logger.error(f"Error adding {framework} control documents: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e),
                "framework": framework
            }
    
    async def index_policy_document(
        self,
        file_path: Union[str, Path],
        framework: Optional[str] = None,
        domain: Optional[str] = "compliance",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index policy document from PDF file.
        
        Args:
            file_path: Path to PDF file containing policy document
            framework: Compliance framework name (e.g., "SOC2", "HIPAA", "ISO 27001")
                      If not provided, will attempt to extract from document metadata
            domain: Domain filter (default: "compliance")
            metadata: Additional metadata (may contain "framework" key)
            
        Returns:
            Dictionary with indexing results
        """
        # Determine framework from parameter, metadata, or default
        framework = framework or (metadata or {}).get("framework") or "policy"
        
        logger.info(f"Indexing policy document from: {file_path} (framework: {framework})")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Policy documents must be PDF files. Got: {file_path.suffix}")
        
        # Update metadata with framework for filtering
        if metadata is None:
            metadata = {}
        metadata["framework"] = framework
        
        # Process PDF
        documents = await self.compliance_processor.process_pdf_document(
            pdf_path=file_path,
            document_type="policy",
            domain=domain,
            metadata=metadata
        )
        
        # Ensure all documents have framework in metadata
        for doc in documents:
            if "framework" not in doc.metadata:
                doc.metadata["framework"] = framework
        
        # Check if documents are already split by policy sections or pages
        # Policy sections have policy_name or policy_section in metadata
        # Page splits have page_number in metadata
        is_policy_split = any(doc.metadata.get("policy_name") is not None or doc.metadata.get("policy_section") is not None for doc in documents)
        is_page_split = any(doc.metadata.get("page_number") is not None for doc in documents)
        
        if is_policy_split:
            # Documents are already split by policy sections with extraction types - use them as-is
            # These documents already have extraction_type set (context, entities, evidence, fields, control, requirement, full_content)
            processed_docs = documents
            logger.info(f"Policy documents are split by policy sections ({len(documents)} documents) - using pre-extracted documents")
        elif is_page_split:
            # Documents are already split by page - use them as-is without pipeline processing
            # This preserves the one-document-per-page structure
            processed_docs = documents
            logger.info(f"Policy documents are split by page ({len(documents)} pages) - skipping pipeline processing")
        else:
            # Process through pipelines (only for full_content documents, not for pre-extracted ones)
            # Documents from compliance_processor already have extraction_type set
            processed_docs = []
            for doc in documents:
                # Only process full_content through pipelines to avoid double-processing
                if doc.metadata.get("extraction_type") == "full_content" or "extraction_type" not in doc.metadata:
                    pipeline_docs = await self._process_through_pipelines(
                        documents=[doc],
                        content_type="policy_documents",
                        product_name="Policy",
                        domain=domain
                    )
                    processed_docs.extend(pipeline_docs)
                else:
                    # Pre-extracted documents (context, entities, requirements) don't need pipeline processing
                    processed_docs.append(doc)
        
        # Separate documents by extraction type for different collections
        # Policy-split documents have multiple extraction types (context, entities, evidence, fields, control, requirement, full_content)
        documents_by_type = {
            "context": [],
            "entities": [],
            "requirement": [],
            "full_content": [],
            "evidence": [],
            "fields": [],
            "control": []
        }
        
        for doc in processed_docs:
            extraction_type = doc.metadata.get("extraction_type", "full_content")
            # Map extraction types to collection names
            if extraction_type == "context":
                documents_by_type["context"].append(doc)
            elif extraction_type == "entities":
                documents_by_type["entities"].append(doc)
            elif extraction_type == "requirement":
                documents_by_type["requirement"].append(doc)
            elif extraction_type == "full_content":
                documents_by_type["full_content"].append(doc)
            elif extraction_type == "evidence":
                documents_by_type["evidence"].append(doc)
            elif extraction_type == "fields":
                documents_by_type["fields"].append(doc)
            elif extraction_type == "control":
                documents_by_type["control"].append(doc)
            else:
                # Default to full_content for unknown types
                documents_by_type["full_content"].append(doc)
        
        # Preview mode: save to files
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=processed_docs,
                content_type="policy_documents",
                domain=domain,
                product_name="Policy",
                metadata={**(metadata or {}), "source_file": str(file_path)}
            )
            return {
                "success": True,
                "preview_mode": True,
                "documents_indexed": len(processed_docs),
                "file_storage": file_result,
                "domain": domain,
                "file_path": str(file_path),
                "breakdown": {
                    "context": len(documents_by_type["context"]),
                    "entities": len(documents_by_type["entities"]),
                    "requirements": len(documents_by_type["requirement"]),
                    "full_content": len(documents_by_type["full_content"]),
                    "evidence": len(documents_by_type["evidence"]),
                    "fields": len(documents_by_type["fields"]),
                    "controls": len(documents_by_type["control"])
                }
            }
        
        # Store documents in general collections based on extraction type
        # Framework and type="policy" are stored in metadata for filtering
        results = {}
        total_indexed = 0
        
        # Store mapping (extraction_type -> general store name)
        # Matches pattern from ingest_preview_files.py EXTRACTION_TYPE_TO_POLICY_STORE
        store_mapping = {
            "context": "domain_knowledge",
            "entities": "entities",
            "requirement": "domain_knowledge",
            "full_content": "domain_knowledge",
            "evidence": "evidence",
            "fields": "fields",
            "control": "controls"  # Controls go to general controls store with type="policy"
        }
        
        for doc_type, docs in documents_by_type.items():
            if not docs:
                continue
            
            store_name = store_mapping.get(doc_type, "domain_knowledge")
            store = self.stores.get(store_name)
            
            if not store:
                logger.warning(f"Store '{store_name}' not available for {doc_type}")
                results[doc_type] = {"error": f"Store not available"}
                continue
            
            # Set type="policy" in metadata for all policy documents
            for doc in docs:
                doc.metadata["type"] = "policy"
                # Ensure framework is in metadata
                if "framework" not in doc.metadata:
                    doc.metadata["framework"] = framework
            
            try:
                result = store.add_documents(docs)
                indexed_count = len(docs)
                total_indexed += indexed_count
                logger.info(f"Indexed {indexed_count} {doc_type} documents to {store_name} (type=policy, framework: {framework})")
                results[doc_type] = {
                    "success": True,
                    "count": indexed_count,
                    "store": store_name,
                    "framework": framework
                }
            except Exception as e:
                logger.error(f"Error adding {doc_type} documents to {store_name}: {e}")
                results[doc_type] = {
                    "success": False,
                    "error": str(e),
                    "framework": framework
                }
        
        # Create contextual edges for indexed policy documents
        edges_created = 0
        if self.contextual_graph_storage and not self.preview_mode:
            try:
                edges = await self._create_contextual_edges_for_policy_documents(
                    processed_docs=processed_docs,
                    framework=framework,
                    domain=domain
                )
                if edges:
                    edge_ids = await self.contextual_graph_storage.save_contextual_edges(edges)
                    # Save to postgres as well
                    await self.contextual_graph_storage.save_edges_to_postgres(edges)
                    edges_created = len(edge_ids)
                    logger.info(f"Created {edges_created} contextual edges for policy documents")
            except Exception as e:
                logger.warning(f"Error creating contextual edges for policy documents: {e}")
        
        return {
            "success": True,
            "documents_indexed": total_indexed,
            "framework": framework,
            "domain": domain,
            "file_path": str(file_path),
            "breakdown": results,
            "contextual_edges_created": edges_created
        }
    
    async def index_risk_controls(
        self,
        file_path: Union[str, Path],
        framework: Optional[str] = None,
        domain: Optional[str] = "compliance",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Index risk controls from PDF or Excel file.
        
        Args:
            file_path: Path to PDF or Excel file containing risk controls
            framework: Optional framework name (e.g., "SOC2", "HIPAA")
                      If not provided, uses "Risk Management" as generic framework
            domain: Domain filter (default: "compliance")
            metadata: Additional metadata
            
        Returns:
            Dictionary with indexing results
        """
        # Use framework from parameter, metadata, or default to "Risk Management"
        framework = framework or (metadata or {}).get("framework") or "Risk Management"
        
        logger.info(f"Indexing risk controls from: {file_path} (framework: {framework})")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine file type
        file_ext = file_path.suffix.lower()
        
        # Update metadata with framework
        if metadata is None:
            metadata = {}
        metadata["framework"] = framework
        
        if file_ext == ".pdf":
            documents = await self.compliance_processor.process_pdf_document(
                pdf_path=file_path,
                document_type="risk_controls",
                domain=domain,
                metadata=metadata
            )
        elif file_ext in [".xlsx", ".xls"]:
            documents = await self.compliance_processor.process_excel_document(
                excel_path=file_path,
                document_type="risk_controls",
                domain=domain,
                metadata=metadata
            )
        else:
            raise ValueError(f"Unsupported file type: {file_ext}. Supported: .pdf, .xlsx, .xls")
        
        # Process through pipelines with smaller batch size for risk controls (10 instead of default 50)
        # This is more efficient for Excel rows which are processed individually
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="risk_controls",
            product_name=framework,
            domain=domain,
            batch_size=10  # Use smaller batch size for risk controls from Excel
        )
        
        # Preview mode: save to files
        if self.preview_mode:
            file_result = self.file_storage.save_documents(
                documents=processed_docs,
                content_type=f"{self._normalize_framework_name(framework)}_risk_controls",
                domain=domain,
                product_name=framework,
                metadata={**(metadata or {}), "source_file": str(file_path)}
            )
            return {
                "success": True,
                "preview_mode": True,
                "documents_indexed": len(processed_docs),
                "file_storage": file_result,
                "framework": framework,
                "domain": domain,
                "file_path": str(file_path)
            }
        
        # Route documents to general stores based on extraction_type
        # Framework and type="risk_*" are stored in metadata for filtering
        # Mapping matches EXTRACTION_TYPE_TO_RISK_STORE from ingest_preview_files.py
        EXTRACTION_TYPE_TO_RISK_STORE = {
            "control": "controls",
            "entities": "entities",
            "fields": "fields",
            "evidence": "evidence",
            "requirements": "domain_knowledge",
            "context": "domain_knowledge",
            "base": "domain_knowledge",
        }
        
        # Group documents by extraction_type and route to general stores
        by_store = {}
        results = {}
        total_indexed = 0
        
        for doc in processed_docs:
            # Ensure framework is in metadata
            if "framework" not in doc.metadata:
                doc.metadata["framework"] = framework
            
            # Check if this is a split document (has extraction_type in metadata)
            extraction_type = doc.metadata.get("extraction_type", "base")
            
            if extraction_type and extraction_type != "base":
                # This is a split document - route based on extraction_type
                store_name = EXTRACTION_TYPE_TO_RISK_STORE.get(
                    extraction_type,
                    "domain_knowledge"  # Default fallback
                )
                # Set type in metadata for filtering (e.g., "risk_control", "risk_entities")
                doc.metadata["type"] = f"risk_{extraction_type}"
            else:
                # Non-split or base document - route to domain_knowledge
                store_name = "domain_knowledge"
                doc.metadata["type"] = "risk" if extraction_type == "base" else "risk_base"
            
            if store_name not in by_store:
                by_store[store_name] = []
            by_store[store_name].append(doc)
        
        # Store in general stores
        for store_name, docs in by_store.items():
            store = self.stores.get(store_name)
            if not store:
                logger.warning(f"Store '{store_name}' not available for risk controls")
                results[store_name] = {"error": "Store not available"}
                continue
            
            try:
                result = store.add_documents(docs)
                indexed_count = len(docs)
                total_indexed += indexed_count
                logger.info(f"Indexed {indexed_count} risk control documents to {store_name} (framework: {framework})")
                results[store_name] = {
                    "success": True,
                    "count": indexed_count,
                    "framework": framework
                }
            except Exception as e:
                logger.error(f"Error adding risk control documents to {store_name}: {e}")
                results[store_name] = {
                    "success": False,
                    "error": str(e),
                    "framework": framework
                }
        
        # Create contextual edges for indexed risk controls
        edges_created = 0
        if self.contextual_graph_storage and not self.preview_mode:
            try:
                edges = await self._create_contextual_edges_for_risk_controls(
                    processed_docs=processed_docs,
                    framework=framework,
                    domain=domain
                )
                if edges:
                    edge_ids = await self.contextual_graph_storage.save_contextual_edges(edges)
                    # Save to postgres as well
                    await self.contextual_graph_storage.save_edges_to_postgres(edges)
                    edges_created = len(edge_ids)
                    logger.info(f"Created {edges_created} contextual edges for risk controls")
            except Exception as e:
                logger.warning(f"Error creating contextual edges for risk controls: {e}")
        
        return {
            "success": True,
            "documents_indexed": total_indexed,
            "framework": framework,
            "domain": domain,
            "file_path": str(file_path),
            "breakdown": results,
            "contextual_edges_created": edges_created
        }
    
    def _content_type_to_store(self, content_type: str) -> str:
        """
        Map content type to store name.
        
        Note: Product and policy content types are routed to general stores
        (entities, domain_knowledge) with type="product" or type="policy" in metadata.
        This method returns the general store name for search purposes.
        """
        mapping = {
            # API/Help docs (keep separate)
            "api_doc": "api_docs",
            "help_doc": "help_docs",
            "product_description": "product_descriptions",
            # Product content types -> general stores (use type="product" in metadata)
            "product_purpose": "domain_knowledge",  # Routes to domain_knowledge with type="product"
            "product_docs_link": "domain_knowledge",  # Routes to domain_knowledge with type="product"
            "product_key_concepts": "entities",  # Routes to entities with type="product"
            "product_key_concept": "entities",  # Routes to entities with type="product"
            "extendable_entity": "entities",  # Routes to entities with type="product"
            "extendable_doc": "domain_knowledge",  # Routes to domain_knowledge with type="product"
            # Schema collections (keep separate)
            "table_definition": "table_definitions",
            "table_description": "table_descriptions",  # TableDescription structure
            "column_definition": "column_definitions",
            "schema_description": "schema_descriptions",
            # General collections
            "domain_knowledge": "domain_knowledge",
            "entities": "entities",
            "evidence": "evidence",
            "fields": "fields",
            "controls": "controls",
            # Policy content types -> general stores (use type="policy" in metadata)
            "policy_documents": "domain_knowledge",  # Routes to domain_knowledge with type="policy"
            # Compliance collections
            "compliance_controls": "compliance_controls",
            # Risk controls -> general stores (use type="risk_*" in metadata)
            "risk_controls": "domain_knowledge",  # Default route, but split docs go to various stores
            # Framework-specific stores are created dynamically
            # Use _get_or_create_framework_store() for framework-based content
        }
        return mapping.get(content_type, content_type)
    
    def _store_to_content_type(self, store_name: str) -> str:
        """Map store name to content type."""
        return store_name.replace("_definitions", "_definition").replace("_descriptions", "_description").replace("_docs", "_doc")
    
    # ============================================================================
    # Contextual Graph Edge Creation Methods
    # ============================================================================
    
    async def _create_contextual_edges_for_policy_documents(
        self,
        processed_docs: List[Document],
        framework: str,
        domain: str
    ) -> List[ContextualEdge]:
        """
        Create contextual edges for policy documents.
        
        Creates edges between:
        - Policy context -> Controls
        - Controls -> Requirements
        - Requirements -> Evidence
        - Controls -> Entities
        - Entities -> Fields
        
        Args:
            processed_docs: List of processed policy documents
            framework: Framework name
            domain: Domain name
            
        Returns:
            List of ContextualEdge objects
        """
        edges = []
        
        # Group documents by extraction type
        by_type = {
            "context": [],
            "control": [],
            "requirement": [],
            "evidence": [],
            "entities": [],
            "fields": []
        }
        
        for doc in processed_docs:
            extraction_type = doc.metadata.get("extraction_type", "full_content")
            if extraction_type in by_type:
                by_type[extraction_type].append(doc)
        
        # Create edges following the hierarchy from vector_store_prompts.json
        # Context -> Controls -> Requirements -> Evidence
        # Controls -> Entities -> Fields
        
        context_id = f"policy_{framework}_{domain}_{datetime.utcnow().timestamp()}"
        
        # Context -> Controls edges
        for context_doc in by_type["context"][:10]:  # Limit to avoid too many edges
            context_id_from_doc = context_doc.metadata.get("context_id") or context_doc.metadata.get("id") or context_id
            for control_doc in by_type["control"][:5]:
                control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{context_id_from_doc}_{control_id}",
                    document=f"Policy context relates to control in {framework} framework",
                    source_entity_id=context_id_from_doc,
                    source_entity_type="context",
                    target_entity_id=control_id,
                    target_entity_type="control",
                    edge_type="HAS_CONTROL_IN_CONTEXT",
                    context_id=context_id_from_doc,
                    relevance_score=0.8,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Controls -> Requirements edges
        for control_doc in by_type["control"][:10]:
            control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
            for req_doc in by_type["requirement"][:5]:
                req_id = req_doc.metadata.get("id") or req_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{control_id}_{req_id}",
                    document=f"Control has requirement in {framework} framework",
                    source_entity_id=control_id,
                    source_entity_type="control",
                    target_entity_id=req_id,
                    target_entity_type="context",  # Requirements stored in domain_knowledge
                    edge_type="HAS_REQUIREMENT_IN_CONTEXT",
                    context_id=context_id,
                    relevance_score=0.9,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Requirements -> Evidence edges
        for req_doc in by_type["requirement"][:10]:
            req_id = req_doc.metadata.get("id") or req_doc.metadata.get("document_id") or str(uuid4())
            for evidence_doc in by_type["evidence"][:5]:
                evidence_id = evidence_doc.metadata.get("id") or evidence_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{req_id}_{evidence_id}",
                    document=f"Requirement is proved by evidence in {framework} framework",
                    source_entity_id=req_id,
                    source_entity_type="context",
                    target_entity_id=evidence_id,
                    target_entity_type="evidence",
                    edge_type="PROVED_BY",
                    context_id=context_id,
                    relevance_score=0.85,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Controls -> Entities edges
        for control_doc in by_type["control"][:10]:
            control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
            for entity_doc in by_type["entities"][:5]:
                entity_id = entity_doc.metadata.get("id") or entity_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{control_id}_{entity_id}",
                    document=f"Control involves entity in {framework} framework",
                    source_entity_id=control_id,
                    source_entity_type="control",
                    target_entity_id=entity_id,
                    target_entity_type="entities",
                    edge_type="RELATED_TO_IN_CONTEXT",
                    context_id=context_id,
                    relevance_score=0.75,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Entities -> Fields edges
        for entity_doc in by_type["entities"][:10]:
            entity_id = entity_doc.metadata.get("id") or entity_doc.metadata.get("document_id") or str(uuid4())
            for field_doc in by_type["fields"][:5]:
                field_id = field_doc.metadata.get("id") or field_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{entity_id}_{field_id}",
                    document=f"Entity has field in {framework} framework",
                    source_entity_id=entity_id,
                    source_entity_type="entities",
                    target_entity_id=field_id,
                    target_entity_type="fields",
                    edge_type="HAS_FIELD_IN_CONTEXT",
                    context_id=context_id,
                    relevance_score=0.7,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        logger.info(f"Created {len(edges)} contextual edges for policy documents")
        return edges
    
    async def _create_contextual_edges_for_risk_controls(
        self,
        processed_docs: List[Document],
        framework: str,
        domain: str
    ) -> List[ContextualEdge]:
        """
        Create contextual edges for risk controls.
        
        Creates edges between:
        - Risk context -> Risk controls
        - Risk controls -> Evidence
        - Risk controls -> Entities
        - Risk controls -> Fields
        
        Args:
            processed_docs: List of processed risk control documents
            framework: Framework name
            domain: Domain name
            
        Returns:
            List of ContextualEdge objects
        """
        edges = []
        
        # Group documents by extraction type
        by_type = {
            "control": [],
            "evidence": [],
            "entities": [],
            "fields": [],
            "context": [],
            "base": []
        }
        
        for doc in processed_docs:
            extraction_type = doc.metadata.get("extraction_type", "base")
            if extraction_type in by_type:
                by_type[extraction_type].append(doc)
        
        context_id = f"risk_{framework}_{domain}_{datetime.utcnow().timestamp()}"
        
        # Risk context -> Risk controls edges
        for context_doc in by_type["context"][:10]:
            context_id_from_doc = context_doc.metadata.get("context_id") or context_doc.metadata.get("id") or context_id
            for control_doc in by_type["control"][:5]:
                control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{context_id_from_doc}_{control_id}",
                    document=f"Risk context relates to risk control in {framework} framework",
                    source_entity_id=context_id_from_doc,
                    source_entity_type="context",
                    target_entity_id=control_id,
                    target_entity_type="control",
                    edge_type="HAS_RISK_CONTROL_IN_CONTEXT",
                    context_id=context_id_from_doc,
                    relevance_score=0.8,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Risk controls -> Evidence edges
        for control_doc in by_type["control"][:10]:
            control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
            for evidence_doc in by_type["evidence"][:5]:
                evidence_id = evidence_doc.metadata.get("id") or evidence_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{control_id}_{evidence_id}",
                    document=f"Risk control requires evidence in {framework} framework",
                    source_entity_id=control_id,
                    source_entity_type="control",
                    target_entity_id=evidence_id,
                    target_entity_type="evidence",
                    edge_type="REQUIRES_EVIDENCE",
                    context_id=context_id,
                    relevance_score=0.85,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Risk controls -> Entities edges
        for control_doc in by_type["control"][:10]:
            control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
            for entity_doc in by_type["entities"][:5]:
                entity_id = entity_doc.metadata.get("id") or entity_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{control_id}_{entity_id}",
                    document=f"Risk control involves entity in {framework} framework",
                    source_entity_id=control_id,
                    source_entity_type="control",
                    target_entity_id=entity_id,
                    target_entity_type="entities",
                    edge_type="RELATED_TO_IN_CONTEXT",
                    context_id=context_id,
                    relevance_score=0.75,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        # Risk controls -> Fields edges
        for control_doc in by_type["control"][:10]:
            control_id = control_doc.metadata.get("id") or control_doc.metadata.get("document_id") or str(uuid4())
            for field_doc in by_type["fields"][:5]:
                field_id = field_doc.metadata.get("id") or field_doc.metadata.get("document_id") or str(uuid4())
                edge = ContextualEdge(
                    edge_id=f"edge_{control_id}_{field_id}",
                    document=f"Risk control uses field in {framework} framework",
                    source_entity_id=control_id,
                    source_entity_type="control",
                    target_entity_id=field_id,
                    target_entity_type="fields",
                    edge_type="USES_FIELD_IN_CONTEXT",
                    context_id=context_id,
                    relevance_score=0.7,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        logger.info(f"Created {len(edges)} contextual edges for risk controls")
        return edges
    
    async def _create_contextual_edges_for_compliance_controls(
        self,
        processed_docs: List[Document],
        framework: str,
        domain: str
    ) -> List[ContextualEdge]:
        """
        Create contextual edges for compliance controls.
        
        Creates edges connecting compliance controls to related entities.
        
        Args:
            processed_docs: List of processed compliance control documents
            framework: Framework name
            domain: Domain name
            
        Returns:
            List of ContextualEdge objects
        """
        edges = []
        context_id = f"compliance_{framework}_{domain}_{datetime.utcnow().timestamp()}"
        
        # Create edges between compliance controls and other entities
        # This is a simplified version - can be enhanced based on extracted relationships
        for i, doc1 in enumerate(processed_docs[:20]):  # Limit to avoid too many edges
            control_id1 = doc1.metadata.get("id") or doc1.metadata.get("document_id") or doc1.metadata.get("control_id") or str(uuid4())
            
            # Create edges to other controls (if they're related)
            for doc2 in processed_docs[i+1:i+6]:  # Connect to next 5 controls
                control_id2 = doc2.metadata.get("id") or doc2.metadata.get("document_id") or doc2.metadata.get("control_id") or str(uuid4())
                
                edge = ContextualEdge(
                    edge_id=f"edge_{control_id1}_{control_id2}",
                    document=f"Compliance controls {control_id1} and {control_id2} are related in {framework} framework",
                    source_entity_id=control_id1,
                    source_entity_type="control",
                    target_entity_id=control_id2,
                    target_entity_type="control",
                    edge_type="RELATED_TO_IN_CONTEXT",
                    context_id=context_id,
                    relevance_score=0.6,
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                edges.append(edge)
        
        logger.info(f"Created {len(edges)} contextual edges for compliance controls")
        return edges
    
    async def delete_by_domain(self, domain: str) -> Dict[str, Any]:
        """Delete all documents for a specific domain."""
        logger.info(f"Deleting all documents for domain: {domain}")
        
        results = {}
        for store_name, store in self.stores.items():
            try:
                # Use where clause to filter by domain
                # Note: This may require store-specific implementation
                if hasattr(store, "delete_by_project_id"):
                    # Use project_id as a workaround if domain deletion not directly supported
                    result = store.delete_by_project_id(domain)
                    results[store_name] = result
                else:
                    logger.warning(f"Store {store_name} does not support deletion by domain")
                    results[store_name] = {"error": "Deletion not supported"}
            except Exception as e:
                logger.error(f"Error deleting from store {store_name}: {e}")
                results[store_name] = {"error": str(e)}
        
        return {
            "success": True,
            "domain": domain,
            "results": results
        }

