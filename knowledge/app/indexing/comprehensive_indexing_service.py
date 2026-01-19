"""
Comprehensive Indexing Service
Indexes API docs, help docs, product descriptions, schema definitions, and column metadata
with support for ChromaDB and Qdrant, domain filtering, and comprehensive pipeline integration.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document

from app.storage.documents import DocumentChromaStore, DocumentQdrantStore, sanitize_collection_name
from app.core.dependencies import get_chromadb_client, get_doc_store_provider
from app.core.settings import get_settings
from app.agents.pipelines import (
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
    ProductProcessor
)
from app.indexing.processors.compliance_document_processor import ComplianceDocumentProcessor
from app.indexing.storage.file_storage import FileStorage


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
        pipeline_batch_size: int = 50
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
        if enable_pipeline_processing:
            self._init_pipelines()
        else:
            self.pipelines = {}
            self._pipelines_initialized = {}
        
        # Initialize processors
        self.table_description_processor = TableDescriptionProcessor()
        self.db_schema_processor = DBSchemaProcessor()
        self.domain_processor = DomainProcessor()
        self.product_processor = ProductProcessor()
        self.compliance_processor = ComplianceDocumentProcessor(
            llm=self.llm,
            enable_extraction=True
        )
        
        logger.info(f"ComprehensiveIndexingService initialized with {vector_store_type}, preview_mode={preview_mode}, pipeline_processing={enable_pipeline_processing}")
    
    def _init_document_stores(self, persistent_client, qdrant_client):
        """Initialize document stores based on vector store type."""
        self.stores = {}
        
        if self.vector_store_type == "chroma":
            if persistent_client is None:
                persistent_client = get_chromadb_client()
            self.persistent_client = persistent_client
            
            # Create stores for different content types
            store_configs = {
                "api_docs": {"tf_idf": True},
                "help_docs": {"tf_idf": True},
                "product_descriptions": {"tf_idf": True},
            "product_purpose": {"tf_idf": True},  # Product purpose
            "product_docs": {"tf_idf": True},  # Product documentation links
            "product_key_concepts": {"tf_idf": True},  # Product key concepts
            "extendable_entities": {"tf_idf": True},  # Extendable entities
            "extendable_docs": {"tf_idf": True},  # Extendable documentation
            "table_definitions": {"tf_idf": True},
            "table_descriptions": {"tf_idf": True},  # Store using TableDescription structure
            "db_schema": {"tf_idf": True},  # DB schema documents in DBSchema format
            "column_definitions": {"tf_idf": True},
            "schema_descriptions": {"tf_idf": True},
            "data_types": {"tf_idf": True},
            "domain_knowledge": {"tf_idf": True},
            # Unified policy/compliance collections - framework stored in metadata for filtering
            "policy_documents": {"tf_idf": True},  # Policy documents (all frameworks, filter by metadata.framework)
            "policy_entities": {"tf_idf": True},  # Policy entities (all frameworks, filter by metadata.framework)
            "policy_context": {"tf_idf": True},  # Policy context (all frameworks, filter by metadata.framework)
            "policy_requirements": {"tf_idf": True},  # Policy requirements (all frameworks, filter by metadata.framework)
            "policy_evidence": {"tf_idf": True},  # Policy evidence (all frameworks, filter by metadata.framework)
            "policy_fields": {"tf_idf": True},  # Policy fields (all frameworks, filter by metadata.framework)
            "compliance_controls": {"tf_idf": True},  # Compliance controls (all frameworks, filter by metadata.framework)
            # General collections (use metadata.type for filtering)
            "entities": {"tf_idf": True},  # General entities (use metadata.type to distinguish)
            "evidence": {"tf_idf": True},  # General evidence (use metadata.type to distinguish)
            "fields": {"tf_idf": True},  # General fields (use metadata.type to distinguish)
            "controls": {"tf_idf": True},  # General controls (use metadata.type to distinguish)
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
            store_configs = {
                "api_docs": {"tf_idf": False},  # Qdrant TF-IDF support may vary
                "help_docs": {"tf_idf": False},
                "product_descriptions": {"tf_idf": False},
                "product_purpose": {"tf_idf": False},  # Product purpose
                "product_docs": {"tf_idf": False},  # Product documentation links
                "product_key_concepts": {"tf_idf": False},  # Product key concepts
                "extendable_entities": {"tf_idf": False},  # Extendable entities
                "extendable_docs": {"tf_idf": False},  # Extendable documentation
                "table_definitions": {"tf_idf": False},
                "table_descriptions": {"tf_idf": False},  # Store using TableDescription structure
                "db_schema": {"tf_idf": False},  # DB schema documents in DBSchema format
                "column_definitions": {"tf_idf": False},
                "schema_descriptions": {"tf_idf": False},
                "data_types": {"tf_idf": False},
                "domain_knowledge": {"tf_idf": False},
                # Unified policy/compliance collections - framework stored in metadata for filtering
                "policy_documents": {"tf_idf": False},  # Policy documents (all frameworks, filter by metadata.framework)
                "policy_entities": {"tf_idf": False},  # Policy entities (all frameworks, filter by metadata.framework)
                "policy_context": {"tf_idf": False},  # Policy context (all frameworks, filter by metadata.framework)
                "policy_requirements": {"tf_idf": False},  # Policy requirements (all frameworks, filter by metadata.framework)
                "policy_evidence": {"tf_idf": False},  # Policy evidence (all frameworks, filter by metadata.framework)
                "policy_fields": {"tf_idf": False},  # Policy fields (all frameworks, filter by metadata.framework)
                "compliance_controls": {"tf_idf": False},  # Compliance controls (all frameworks, filter by metadata.framework)
                "risk_controls": {"tf_idf": False}  # Risk controls (all frameworks, filter by metadata.framework)
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
        
        # Group documents by content type and store in appropriate stores
        results = {
            "product_purpose": 0,
            "product_docs": 0,
            "product_key_concepts": 0,
            "extendable_entities": 0,
            "extendable_docs": 0
        }
        
        # Group documents by content type
        by_content_type = {}
        for doc in processed_docs:
            content_type = doc.metadata.get("content_type", "unknown")
            if content_type not in by_content_type:
                by_content_type[content_type] = []
            by_content_type[content_type].append(doc)
        
        # Store in appropriate stores
        store_mapping = {
            "product_purpose": "product_purpose",
            "product_docs_link": "product_docs",
            "product_key_concepts": "product_key_concepts",
            "product_key_concept": "product_key_concepts",
            "extendable_entity": "extendable_entities",
            "extendable_doc": "extendable_docs"
        }
        
        for content_type, docs in by_content_type.items():
            store_name = store_mapping.get(content_type)
            if store_name and store_name in self.stores:
                try:
                    store = self.stores[store_name]
                    result = store.add_documents(docs)
                    results[store_name] = len(docs)
                    logger.info(f"Indexed {len(docs)} documents to {store_name}")
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
            
            # Create table definition document
            table_content = {
                "table_name": table_name,
                "schema": mdl_dict.get("schema", "public"),
                "description": description,
                "columns": columns,
                "column_count": len(columns)
            }
            
            table_doc = Document(
                page_content=json.dumps(table_content, indent=2),
                metadata={
                    "content_type": "table_definition",
                    "table_name": table_name,
                    "schema": mdl_dict.get("schema", "public"),
                    "product_name": product_name,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "column_count": len(columns),
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
        
        # Index schema-level description
        schema_description = {
            "catalog": mdl_dict.get("catalog", ""),
            "schema": mdl_dict.get("schema", ""),
            "models_count": len(mdl_dict.get("models", [])),
            "enums_count": len(mdl_dict.get("enums", [])),
            "metrics_count": len(mdl_dict.get("metrics", [])),
            "views_count": len(mdl_dict.get("views", []))
        }
        
        schema_doc = Document(
            page_content=json.dumps(schema_description, indent=2),
            metadata={
                "content_type": "schema_description",
                "product_name": product_name,
                "schema": mdl_dict.get("schema", ""),
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
                **({"domain": domain} if domain else {})
            }
        )
        
        # Preview mode: save schema doc to files
        if self.preview_mode:
            schema_file_result = self.file_storage.save_documents(
                documents=[schema_doc],
                content_type="schema_descriptions",
                domain=domain,
                product_name=product_name,
                metadata={**(metadata or {}), "source": "mdl"}
            )
            results["preview_mode"] = True
            results["schema_file_storage"] = schema_file_result
        else:
            store = self.stores["schema_descriptions"]
            try:
                store.add_documents([schema_doc])
            except Exception as e:
                logger.error(f"Error adding schema document: {e}")
        
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
            return {
                "success": True,
                "documents_indexed": len(processed_docs),
                "store": "compliance_controls",
                "framework": framework,
                "domain": domain,
                "file_path": str(file_path),
                "result": result
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
        documents_by_type = {
            "context": [],
            "entities": [],
            "requirement": [],
            "full_content": [],
            "evidence": [],
            "fields": []
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
                    "fields": len(documents_by_type["fields"])
                }
            }
        
        # Store documents in unified collections based on extraction type
        # Framework is stored in metadata for filtering
        results = {}
        total_indexed = 0
        
        # Store mapping (extraction_type -> unified store name)
        store_mapping = {
            "context": "policy_context",
            "entities": "policy_entities",
            "requirement": "policy_requirements",
            "full_content": "policy_documents",
            "evidence": "policy_evidence",
            "fields": "policy_fields"
        }
        
        for doc_type, docs in documents_by_type.items():
            if not docs:
                continue
            
            store_name = store_mapping.get(doc_type, "policy_documents")
            store = self.stores.get(store_name)
            
            if not store:
                logger.warning(f"Store '{store_name}' not available for {doc_type}")
                results[doc_type] = {"error": f"Store not available"}
                continue
            
            try:
                result = store.add_documents(docs)
                indexed_count = len(docs)
                total_indexed += indexed_count
                logger.info(f"Indexed {indexed_count} {doc_type} documents to {store_name} (framework: {framework})")
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
        
        return {
            "success": True,
            "documents_indexed": total_indexed,
            "framework": framework,
            "domain": domain,
            "file_path": str(file_path),
            "breakdown": results
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
        
        # Process through pipelines
        processed_docs = await self._process_through_pipelines(
            documents=documents,
            content_type="risk_controls",
            product_name=framework,
            domain=domain
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
        
        # Store documents in unified risk_controls collection
        # Framework is stored in metadata for filtering
        store = self.stores.get("risk_controls")
        if not store:
            logger.warning("Risk controls store not available")
            return {"documents_indexed": 0, "error": "Store not available", "framework": framework}
        
        # Ensure all documents have framework in metadata
        for doc in processed_docs:
            if "framework" not in doc.metadata:
                doc.metadata["framework"] = framework
        
        try:
            result = store.add_documents(processed_docs)
            logger.info(f"Indexed {len(processed_docs)} risk control documents to risk_controls (framework: {framework})")
            return {
                "success": True,
                "documents_indexed": len(processed_docs),
                "store": "risk_controls",
                "framework": framework,
                "domain": domain,
                "file_path": str(file_path),
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding risk control documents: {e}")
            return {
                "success": False,
                "documents_indexed": 0,
                "error": str(e),
                "framework": framework
            }
    
    def _content_type_to_store(self, content_type: str) -> str:
        """Map content type to store name."""
        mapping = {
            "api_doc": "api_docs",
            "help_doc": "help_docs",
            "product_description": "product_descriptions",
            "product_purpose": "product_purpose",
            "product_docs_link": "product_docs",
            "product_key_concepts": "product_key_concepts",
            "product_key_concept": "product_key_concepts",
            "extendable_entity": "extendable_entities",
            "extendable_doc": "extendable_docs",
            "table_definition": "table_definitions",
            "table_description": "table_descriptions",  # TableDescription structure
            "column_definition": "column_definitions",
            "schema_description": "schema_descriptions",
            "domain_knowledge": "domain_knowledge"
            # Framework-specific stores are created dynamically
            # Use _get_or_create_framework_store() for framework-based content
        }
        return mapping.get(content_type, content_type)
    
    def _store_to_content_type(self, store_name: str) -> str:
        """Map store name to content type."""
        return store_name.replace("_definitions", "_definition").replace("_descriptions", "_description").replace("_docs", "_doc")
    
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

