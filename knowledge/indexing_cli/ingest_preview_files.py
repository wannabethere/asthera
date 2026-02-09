"""
CLI utility to ingest preview files into ChromaDB stores without re-running pipelines.

This script loads all preview JSON files from the indexing_preview directory
and ingests them directly into ChromaDB stores, skipping pipeline processing
since the documents are already processed.

IMPORTANT: Collection Naming and Separation
--------------------------------------------
This script uses PREFIXED collections (e.g., "comprehensive_index_table_definitions")
which are SEPARATE from project-based collections used by project_reader.py:

Project-based collections (unprefixed, used by project_reader.py/retrieval_helper.py):
- db_schema (unprefixed - special case, also used by comprehensive indexing)
- table_descriptions (unprefixed)
- column_metadata (unprefixed)
- sql_functions (unprefixed)
- instructions, historical_question, sql_pairs, etc. (unprefixed)

Comprehensive indexing collections (prefixed, used by this script):
- comprehensive_index_table_definitions (prefixed)
- comprehensive_index_table_descriptions (prefixed)
- comprehensive_index_column_definitions (prefixed)
- comprehensive_index_schema_descriptions (prefixed)
- comprehensive_index_policy_*, comprehensive_index_domain_knowledge, etc. (prefixed)

The two systems are completely separate and do not interfere with each other.

Usage:
    # Ingest all preview files
    python -m indexing_cli.ingest_preview_files \
        --preview-dir indexing_preview \
        --collection-prefix comprehensive_index

    # Ingest specific content types only (schema-related)
    python -m indexing_cli.ingest_preview_files \
        --preview-dir indexing_preview \
        --content-types table_definitions table_descriptions column_definitions schema_descriptions

    # Dry run (show what would be ingested)
    python -m indexing_cli.ingest_preview_files \
        --preview-dir indexing_preview \
        --dry-run

    # Skip contextual graph extraction (only ingest to vector stores)
    python -m indexing_cli.ingest_preview_files \
        --preview-dir indexing_preview \
        --skip-contextual-graph

    # Ingest metrics collection (kb-dump-utility preview/metrics/collection.json) into Qdrant
    python -m indexing_cli.ingest_preview_files \
        --preview-dir /path/to/kb-dump-utility/preview \
        --content-types metrics \
        --vector-store qdrant

    # Ingest Snyk schema (column_definitions, table_*, contextual_edges) AND product KB (policies/narratives edges)
    # Use multiple --preview-dir so column_definitions and contextual_edges from both sources are merged
    python -m indexing_cli.ingest_preview_files \
        --preview-dir /path/to/flowharmonicai/knowledge/indexing_preview \
        /path/to/kb-dump-utility/preview_product_kb

    # Ingest ONLY policy preview (controls_new, risks_new, key_concepts_new, etc.) from kb-dump-utility/preview_policy
    python -m indexing_cli.ingest_preview_files \
        --preview-dir /path/to/kb-dump-utility/preview_policy \
        --policy-preview-only \
        --collection-prefix comprehensive_index
"""
import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
import uuid
from uuid import uuid4, UUID

from langchain_core.documents import Document

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.indexing.storage.file_storage import FileStorage
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm, get_database_pool, get_database_client
from app.storage.documents import sanitize_collection_name
from app.services.contextual_graph_storage import (
    ContextualGraphStorage,
    ContextDefinition,
    ContextualEdge,
    ControlContextProfile
)
from app.storage.vector_store import ChromaVectorStoreClient, QdrantVectorStoreClient
from app.storage.models import Control
from app.services.storage.control_service import ControlStorageService
from app.storage.query.collection_factory import CollectionFactory

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PreviewFileIngester:
    """Ingests preview files into ChromaDB stores without pipeline processing."""
    
    # Mapping from preview content_type to store names
    # Using fixed collections only - framework/type info goes in metadata
    CONTENT_TYPE_TO_STORE = {
        # Schema collections (use type in metadata to distinguish)
        "table_definitions": "table_definitions",
        "table_descriptions": "table_descriptions",
        "column_definitions": "column_definitions",
        "schema_descriptions": "schema_descriptions",
        # Knowledge base (features, metrics, instructions, examples)
        # Handled specially - routes based on entity_type in metadata
        "knowledgebase": "knowledgebase",  # Routes to entities, instructions, or sql_pairs based on entity_type
        # Metrics collection (preview/metrics/collection.json from kb-dump-utility)
        "metrics": "knowledgebase",  # Routes to entities by featureType (metric, feature, aggregation)
        # Policy collections (routed to general stores with type="policy" in metadata)
        "policy_documents": "policy_documents",  # Handled specially - routes to general stores with type="policy"
        # Risk controls go to domain_knowledge with type="risk" in metadata
        "riskmanagement_risk_controls": "domain_knowledge",  # Will add type="risk" to metadata
        "risk_controls": "domain_knowledge",  # Will add type="risk" to metadata
        # Compliance collections (framework in metadata, not collection name)
        "compliance_controls": "compliance_controls",
        "soc2_controls": "compliance_controls",  # SOC2 controls route to compliance_controls with framework="SOC2"
        # General collections (use metadata.type for filtering - e.g., type="policy", type="risk_control")
        "entities": "entities",  # General entities (metadata.type: policy, risk_entities, etc.)
        "evidence": "evidence",  # General evidence (metadata.type: policy, risk_evidence, etc.)
        "fields": "fields",  # General fields (metadata.type: policy, risk_fields, etc.)
        "controls": "controls",  # General controls (metadata.type: policy, risk_control, compliance, etc.)
        # Product/Connector content types (routed to general stores with type="product" in metadata)
        "product_purpose": "product_purpose",  # Handled specially - routes to domain_knowledge with type="product"
        "product_docs_link": "product_docs",  # Handled specially - routes to domain_knowledge with type="product"
        "product_key_concepts": "product_key_concepts",  # Handled specially - routes to entities with type="product"
        "product_key_concept": "product_key_concepts",  # Handled specially - routes to entities with type="product"
        "extendable_entity": "extendable_entities",  # Handled specially - routes to entities with type="product"
        "extendable_doc": "extendable_docs",  # Handled specially - routes to domain_knowledge with type="product"
        # Domain knowledge (for policies, risks, etc. - use type in metadata)
        "domain_knowledge": "domain_knowledge",
        # Policy preview (kb-dump-utility preview_policy) -> dedicated _new collections for query use
        "policy_controls": "controls_new",
        "policy_risks": "risks_new",
        "policy_key_concepts": "key_concepts_new",
        "policy_identifiers": "identifiers_new",
        "policy_framework_docs": "framework_docs_new",
        "policy_edges": "edges_new",
        # MDL contextual preview (index_mdl_preview_contextual.py) - category-mapped edges for query fixing
        "mdl_key_concepts": "mdl_key_concepts",
        "mdl_patterns": "mdl_patterns",
        "mdl_evidences": "mdl_evidences",
        "mdl_fields": "mdl_fields",
        "mdl_metrics": "mdl_metrics",
        "mdl_edges_table": "mdl_edges_table",
        "mdl_edges_column": "mdl_edges_column",
        "mdl_category_enrichment": "mdl_category_enrichment",
    }
    
    # Mapping from knowledgebase entity_type to store names
    KNOWLEDGEBASE_ENTITY_TO_STORE = {
        "feature": "entities",
        "metric": "entities",
        "aggregation": "entities",
        "instruction": "instructions",
        "example": "sql_pairs",
    }
    
    # Mapping from extraction_type to general store names (use type="policy" in metadata)
    EXTRACTION_TYPE_TO_POLICY_STORE = {
        "context": "domain_knowledge",  # Policy context goes to domain_knowledge with type="policy"
        "entities": "entities",  # Policy entities go to general entities store with type="policy"
        "requirement": "domain_knowledge",  # Policy requirements go to domain_knowledge with type="policy"
        "full_content": "domain_knowledge",  # Policy documents go to domain_knowledge with type="policy"
        "evidence": "evidence",  # Policy evidence goes to general evidence store with type="policy"
        "fields": "fields",  # Policy fields go to general fields store with type="policy"
    }
    
    # Mapping from extraction_type to risk controls store names (for split files)
    EXTRACTION_TYPE_TO_RISK_STORE = {
        "control": "controls",  # Risk controls go to general controls store
        "entities": "entities",  # Risk entities go to general entities store
        "fields": "fields",  # Risk fields go to general fields store
        "evidence": "evidence",  # Risk evidence goes to general evidence store
        "requirements": "domain_knowledge",  # Risk requirements go to domain_knowledge
        "context": "domain_knowledge",  # Risk context goes to domain_knowledge
        "base": "domain_knowledge",  # Base row data goes to domain_knowledge
    }
    
    # Policy preview _new store names (for collection_factory and indexing_service)
    POLICY_PREVIEW_NEW_STORES = (
        "controls_new",
        "risks_new",
        "key_concepts_new",
        "identifiers_new",
        "framework_docs_new",
        "edges_new",
    )
    # Content types that map to policy preview (for --policy-preview-only)
    POLICY_PREVIEW_CONTENT_TYPES = (
        "policy_controls",
        "policy_risks",
        "policy_key_concepts",
        "policy_identifiers",
        "policy_framework_docs",
        "policy_edges",
    )

    # Mapping from store_name to extraction_type for document_kg_insights
    STORE_NAME_TO_EXTRACTION_TYPE = {
        # General stores (used for policies, risks, etc. - distinguished by metadata.type)
        "entities": "entities",  # General entities (metadata.type: policy, risk_entities, etc.)
        "evidence": "evidence",  # General evidence (metadata.type: policy, risk_evidence, etc.)
        "fields": "fields",  # General fields (metadata.type: policy, risk_fields, etc.)
        "controls": "control",  # General controls (metadata.type: policy, risk_control, compliance, etc.)
        "domain_knowledge": "context",  # Used for risks, policies domain knowledge (metadata.type: policy, risk, etc.)
        # Policy preview _new stores
        "controls_new": "control",
        "risks_new": "entities",
        "key_concepts_new": "entities",
        "identifiers_new": "entities",
        "framework_docs_new": "context",
        "edges_new": "context",
        # Compliance collections (framework in metadata, not collection name)
        "compliance_controls": "control",
        # Schema collections
        "table_definitions": "schema",
        "table_descriptions": "schema",
        "column_definitions": "schema",
        "schema_descriptions": "schema",
        # Feature collections (feature knowledge base)
        "features": "feature",  # Feature knowledge base (metadata.type: feature_knowledge, feature_type: control, risk, etc.)
        "feature_store_features": "feature",  # Alternative name with prefix
        # Product collections (consolidated into general stores with type="product" in metadata)
        # Note: Product content types are routed to general stores (entities, domain_knowledge) with type="product"
    }
    
    # Content types that might contain contextual graph data
    CONTEXTUAL_GRAPH_CONTENT_TYPES = {
        "context_definitions": "context_definitions",
        "contextual_edges": "contextual_edges",
        "control_context_profiles": "control_context_profiles",
    }

    # kb-dump-utility enriched doc_type -> store_name (collection_factory) for minimal assistant changes
    # Aligns preview/enriched/*.json (doc_type from extractions.json + product_docs for vendor) with collection_factory stores
    DOC_TYPE_TO_STORE = {
        "policy": "domain_knowledge",
        "playbook": "domain_knowledge",
        "documentation": "domain_knowledge",
        "product_docs": "domain_knowledge",
        "exception": "entities",
        "advisory": "domain_knowledge",
        "procedure": "domain_knowledge",
        "standard": "compliance_controls",
        "vulnerability": "entities",
        "guide": "domain_knowledge",
        "faq": "domain_knowledge",
        "framework": "domain_knowledge",
        "requirement": "domain_knowledge",
        "control": "compliance_controls",
        "rule_reference": "entities",
        "security-check": "domain_knowledge",
    }
    
    def __init__(
        self,
        preview_dir: str = "indexing_preview",
        collection_prefix: str = "",  # Empty prefix by default to match project_reader.py collections
        vector_store_type: str = "chroma",
        force_recreate: bool = False,
        postgres_batch_size: int = 1000,
        skip_contextual_graph: bool = False,
        edge_batch_size: int = 500,
        edge_postgres_batch_size: int = 1000,
        enriched_subdirs: Optional[List[str]] = None,
        document_batch_size: int = 200,
        checkpoint_file: Optional[str] = None,
        clear_checkpoint: bool = False,
        preview_dirs: Optional[List[str]] = None,
    ):
        """
        Initialize the preview file ingester.
        
        Args:
            preview_dir: Directory containing preview files (used when preview_dirs not set). Ignored if preview_dirs is set.
            collection_prefix: Prefix for ChromaDB collections
            vector_store_type: Vector store type ("chroma" or "qdrant")
            force_recreate: If True, delete and recreate collections before ingesting
            postgres_batch_size: Batch size for PostgreSQL inserts (default: 1000)
            skip_contextual_graph: If True, skip contextual graph extraction and ingestion (default: False)
            edge_batch_size: Batch size for contextual edge vector store inserts (default: 500)
            edge_postgres_batch_size: Batch size for contextual edge PostgreSQL inserts (default: 1000)
            enriched_subdirs: Subdirs under preview_dir to load enriched JSON from (e.g. ["enriched", "enriched_vendor"])
            document_batch_size: Batch size for embedding and upserting documents to vector store (default: 200)
            checkpoint_file: If set, save progress after each batch and resume from this file on restart
            clear_checkpoint: If True, delete checkpoint file before starting (fresh run)
            preview_dirs: If set, list of preview directories to merge (Snyk schema + product KB + policies). Overrides preview_dir.
        """
        if preview_dirs:
            self.preview_dirs = [Path(d) for d in preview_dirs]
            self.preview_dir = self.preview_dirs[0]  # primary for enriched_subdirs
        else:
            self.preview_dir = Path(preview_dir)
            self.preview_dirs = [self.preview_dir]
        self.collection_prefix = collection_prefix
        self.vector_store_type = vector_store_type
        self.force_recreate = force_recreate
        self.postgres_batch_size = postgres_batch_size
        self.skip_contextual_graph = skip_contextual_graph
        self.edge_batch_size = edge_batch_size
        self.edge_postgres_batch_size = edge_postgres_batch_size
        self.enriched_subdirs = enriched_subdirs
        self.document_batch_size = document_batch_size
        self.checkpoint_file = Path(checkpoint_file) if checkpoint_file else None
        self.clear_checkpoint = clear_checkpoint
        
        # NOTE: Schema collections are UNPREFIXED to match project-based system for interoperability
        # Schema collections (db_schema, table_descriptions, column_metadata) are shared
        # between project_reader.py and comprehensive indexing so they can be used interchangeably.
        # Other collections (policy, compliance, etc.) use the prefix.
        
        # Initialize indexing service with pipeline processing disabled
        persistent_client = get_chromadb_client() if vector_store_type == "chroma" else None
        embeddings = get_embeddings_model()
        llm = get_llm(temperature=0.2)
        
        self.indexing_service = ComprehensiveIndexingService(
            vector_store_type=vector_store_type,
            persistent_client=persistent_client,
            embeddings_model=embeddings,
            llm=llm,
            collection_prefix=collection_prefix,
            preview_mode=False,  # Not in preview mode - will index to database
            enable_pipeline_processing=False,  # Skip pipelines - documents already processed
            pipeline_batch_size=50
        )
        
        # Initialize collection factory to access collections by store name
        if vector_store_type == "chroma" and persistent_client:
            try:
                # Create VectorStoreClient wrapper for CollectionFactory
                # Get persist_directory from client or settings, never use hardcoded fallback
                persist_directory = getattr(persistent_client, "path", None)
                if not persist_directory:
                    from app.core.settings import get_settings
                    settings = get_settings()
                    persist_directory = settings.CHROMA_STORE_PATH
                vector_store_config = {
                    "use_local": True,
                    "persist_directory": persist_directory
                }
                vector_store_client = ChromaVectorStoreClient(
                    config=vector_store_config,
                    embeddings_model=embeddings
                )
                # Set the client directly to avoid re-initialization
                vector_store_client._client = persistent_client
                
                self.collection_factory = CollectionFactory(
                    vector_store_client=vector_store_client,
                    embeddings_model=embeddings,
                    collection_prefix=collection_prefix
                )
                logger.info(f"Initialized CollectionFactory with collection_prefix='{collection_prefix}'")
            except Exception as e:
                logger.warning(f"Could not initialize CollectionFactory: {e}. Will use indexing_service.stores as fallback.")
                self.collection_factory = None
        else:
            self.collection_factory = None
        
        # Initialize contextual graph storage
        self.contextual_graph_storage = None
        self.control_service = None
        self.db_pool = None
        self.db_client = None
        
        # Initialize contextual graph storage for both ChromaDB and Qdrant
        if vector_store_type == "chroma" and persistent_client:
            try:
                # Create VectorStoreClient wrapper for ContextualGraphStorage
                # Get persist_directory from client or settings, never use hardcoded fallback
                persist_directory = getattr(persistent_client, "path", None)
                if not persist_directory:
                    from app.core.settings import get_settings
                    settings = get_settings()
                    persist_directory = settings.CHROMA_STORE_PATH
                vector_store_config = {
                    "use_local": True,
                    "persist_directory": persist_directory
                }
                vector_store_client = ChromaVectorStoreClient(
                    config=vector_store_config,
                    embeddings_model=embeddings
                )
                # Set the client directly to avoid re-initialization
                vector_store_client._client = persistent_client
                
                self.contextual_graph_storage = ContextualGraphStorage(
                    vector_store_client=vector_store_client,
                    embeddings_model=embeddings,
                    collection_prefix=collection_prefix
                )
                logger.info(f"Initialized ContextualGraphStorage with collection_prefix='{collection_prefix}'")
                
                # Database client will be initialized lazily when needed (in async context)
                self._db_client_initialized = False
                self._db_pool_initialized = False
            except Exception as e:
                logger.warning(f"Could not initialize ContextualGraphStorage: {e}. Contextual graph indexing will be skipped.")
        
        elif vector_store_type == "qdrant":
            try:
                # Create VectorStoreClient wrapper for ContextualGraphStorage with Qdrant
                from app.core.settings import get_settings
                
                settings = get_settings()
                qdrant_config = settings.get_vector_store_config()
                
                vector_store_config = {
                    "type": "qdrant",
                    "host": qdrant_config.get("host", "localhost"),
                    "port": qdrant_config.get("port", 6333)
                }
                
                vector_store_client = QdrantVectorStoreClient(
                    config=vector_store_config,
                    embeddings_model=embeddings
                )
                
                self.contextual_graph_storage = ContextualGraphStorage(
                    vector_store_client=vector_store_client,
                    embeddings_model=embeddings,
                    collection_prefix=collection_prefix
                )
                logger.info(f"Initialized ContextualGraphStorage for Qdrant with collection_prefix='{collection_prefix}'")
                
                # Database client will be initialized lazily when needed (in async context)
                self._db_client_initialized = False
                self._db_pool_initialized = False
            except Exception as e:
                logger.warning(f"Could not initialize ContextualGraphStorage for Qdrant: {e}. Contextual graph indexing will be skipped.")
        
        # Force recreate collections if requested
        if force_recreate and vector_store_type == "chroma":
            self._recreate_collections()
        
        logger.info(f"PreviewFileIngester initialized with preview_dir={preview_dir}, collection_prefix={collection_prefix}, force_recreate={force_recreate}, skip_contextual_graph={skip_contextual_graph}")
    
    def _get_collection_name(self, store_name: str) -> str:
        """
        Get the collection name for a store, handling unprefixed collections for schema content.
        
        Schema collections are always unprefixed to match project_reader.py and retrieval.py,
        regardless of collection_prefix. This ensures compatibility with index_mdl.py which
        writes to unprefixed collections.
        
        Args:
            store_name: Store name (e.g., "db_schema", "table_descriptions", "policy_documents")
            
        Returns:
            Collection name (unprefixed for schema collections, prefixed for others)
        """
        # Schema collections are always unprefixed to match project_reader.py, retrieval.py, and index_mdl.py
        # These collections are shared between comprehensive indexing and project-based systems
        unprefixed_collections = {
            "db_schema": "db_schema",
            "table_descriptions": "table_descriptions",
            "table_definitions": "table_definitions",  # Unprefixed to match index_mdl.py
            "column_definitions": "column_metadata",  # Map to column_metadata to match project_reader
            "schema_descriptions": "schema_descriptions",  # Unprefixed to match index_mdl.py
        }
        
        if store_name in unprefixed_collections:
            collection_name = unprefixed_collections[store_name]
        elif self.collection_prefix:
            collection_name = f"{self.collection_prefix}_{store_name}"
        else:
            collection_name = store_name
        
        return sanitize_collection_name(collection_name)
    
    def discover_preview_files(self, content_types: Optional[List[str]] = None) -> Dict[str, List[Path]]:
        """
        Discover all preview JSON files in the preview directory (or all preview_dirs if set).
        When multiple preview dirs are used, files are merged per content_type so Snyk schema
        (column_definitions, contextual_edges) and product KB (preview_product_kb) are ingested together.
        
        Args:
            content_types: Optional list of content types to filter by
            
        Returns:
            Dictionary mapping content_type to list of file paths
        """
        files_by_type = defaultdict(list)
        
        for pdir in self.preview_dirs:
            if not pdir.exists():
                logger.warning(f"Preview directory does not exist: {pdir}")
                continue
            
            # Scan all subdirectories in this preview dir
            for content_dir in pdir.iterdir():
                if not content_dir.is_dir():
                    continue
                dir_name = content_dir.name
                # Policy preview: policy_docs/ contains per-type files (policy_controls.json, policy_risks.json, ...)
                # Use file stem as content_type so each file routes to its _new store
                if dir_name == "policy_docs":
                    for json_file in content_dir.glob("*.json"):
                        if "summary" not in json_file.name:
                            file_content_type = json_file.stem
                            if content_types and file_content_type not in content_types:
                                continue
                            files_by_type[file_content_type].append(json_file)
                    continue
                # MDL contextual preview: mdl_docs/ contains per-type files (mdl_key_concepts_20260128_005808_Snyk.json, ...)
                if dir_name == "mdl_docs":
                    for json_file in content_dir.glob("*.json"):
                        if "summary" not in json_file.name:
                            stem = json_file.stem
                            # stem e.g. mdl_key_concepts_20260128_005808_Snyk -> content_type mdl_key_concepts
                            parts = stem.split("_")
                            file_content_type = stem
                            for i, p in enumerate(parts):
                                if len(p) == 8 and p.isdigit():
                                    file_content_type = "_".join(parts[:i])
                                    break
                            if content_types and file_content_type not in content_types:
                                continue
                            files_by_type[file_content_type].append(json_file)
                    continue
                content_type = dir_name
                if content_types and content_type not in content_types:
                    continue
                for json_file in content_dir.glob("*.json"):
                    if "summary" not in json_file.name:
                        files_by_type[content_type].append(json_file)
        
        # Log discovery results
        total_files = sum(len(files) for files in files_by_type.values())
        logger.info(f"Discovered {total_files} preview files across {len(files_by_type)} content types (from {len(self.preview_dirs)} dir(s))")
        for content_type, files in files_by_type.items():
            logger.info(f"  {content_type}: {len(files)} files")
        
        return dict(files_by_type)
    
    def load_preview_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load a preview JSON file.
        
        Args:
            file_path: Path to preview JSON file
            
        Returns:
            Dictionary with metadata and documents, or None if file is invalid/empty (skipped).
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                logger.warning(f"Skipping empty file: {file_path}")
                return None
            data = json.loads(raw)
            if not isinstance(data, dict):
                logger.warning(f"Skipping non-object JSON in {file_path}")
                return None
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Skipping invalid JSON in {file_path}: {e}")
            return None
        except OSError as e:
            logger.warning(f"Skipping unreadable file {file_path}: {e}")
            return None
    
    def convert_to_documents(self, file_data: Dict[str, Any]) -> List[Document]:
        """
        Convert preview file data to LangChain Document objects.
        Supports: (1) standard format with "documents" list; (2) metrics collection with "items" list.
        
        Args:
            file_data: Dictionary from preview JSON file
            
        Returns:
            List of Document objects
        """
        documents = []

        # Metrics collection format (preview/metrics/collection.json): name, version, items[]
        items = file_data.get("items")
        if items is not None and isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                common = item.get("common") or {}
                meta = item.get("metadata") or {}
                # Searchable text for embedding
                parts = [
                    common.get("metricTitle") or item.get("displayName") or item.get("name") or meta.get("name") or "",
                    common.get("metricDescription") or item.get("description") or meta.get("description") or "",
                    common.get("comment") or meta.get("comments") or item.get("purpose") or "",
                    common.get("category") or "",
                    common.get("subCategory") or "",
                    common.get("source") or "",
                ]
                page_content = "\n\n".join(p for p in parts if p)
                entity_type = (common.get("featureType") or item.get("type") or "feature").lower()
                doc_id = meta.get("id") or item.get("name") or str(uuid4())
                metadata = {
                    "id": doc_id,
                    "entity_type": entity_type,
                    "source_content_type": "metrics",
                    "mdl_entity_type": entity_type,
                    "type": "ENTITY",
                    "name": item.get("name") or meta.get("name") or common.get("metricTitle"),
                    "displayName": item.get("displayName") or common.get("metricTitle"),
                    "featureType": common.get("featureType") or item.get("type"),
                    "featureCategory": common.get("featureCategory"),
                    "category": common.get("category"),
                    "subCategory": common.get("subCategory"),
                    "metricTitle": common.get("metricTitle"),
                    "metricDescription": common.get("metricDescription"),
                    "reportPeriod": common.get("reportPeriod"),
                    "target": common.get("target"),
                    "comment": common.get("comment"),
                    "contributor": common.get("contributor"),
                    "source": common.get("source"),
                }
                metadata = {k: v for k, v in metadata.items() if v is not None}
                documents.append(Document(page_content=page_content, metadata=metadata))
            return documents

        for doc_data in file_data.get("documents", []):
            meta = dict(doc_data.get("metadata", {}))
            doc = Document(
                page_content=doc_data.get("page_content", ""),
                metadata=meta
            )
            documents.append(doc)

        return documents

    @staticmethod
    def _column_entity_id(metadata: Dict[str, Any]) -> str:
        """
        Build stable column entity id matching contextual_edges (TABLE_HAS_COLUMN / COLUMN_BELONGS_TO_TABLE).
        Format: column_{table_lower}_{column_lower} e.g. column_accessrequest_attributes.
        """
        table = (metadata.get("table_name") or "").strip().lower().replace(" ", "_")
        column = (metadata.get("column_name") or "").strip().lower().replace(" ", "_")
        if not table or not column:
            return metadata.get("id") or metadata.get("document_id") or ""
        return f"column_{table}_{column}"

    def _parse_supports_traversals(self, supports_traversals: List[str]) -> Dict[str, str]:
        """Parse supports_traversals (e.g. 'category:soc2', 'type:policy') into metadata for filtering."""
        out = {}
        for t in supports_traversals or []:
            if ":" in t:
                k, v = t.split(":", 1)
                k, v = k.strip().lower(), v.strip()
                if k == "category":
                    out["framework"] = v
                out[k] = v
        return out

    def convert_enriched_section_to_document(
        self, section: Dict[str, Any], doc_type: str
    ) -> Document:
        """
        Convert one kb-dump-utility enriched section to a LangChain Document with store-aligned metadata.
        Sets metadata.type and metadata.store_name so collection_factory / assistants can filter with minimal changes.
        """
        store_name = self.DOC_TYPE_TO_STORE.get(
            doc_type, "domain_knowledge"
        )
        content = section.get("content") or section.get("excerpt") or ""
        if len(content) > 12000:
            content = (section.get("excerpt") or content[:12000]) or ""

        # product_docs (vendor) -> metadata type "product" so product assistant finds them
        metadata_type = "product" if doc_type == "product_docs" else doc_type
        meta = {
            "id": section.get("section_id") or section.get("doc_id", ""),
            "document_id": section.get("doc_id"),
            "section_id": section.get("section_id"),
            "type": metadata_type,
            "store_name": store_name,
            "source_content_type": doc_type,
            "title": section.get("title"),
            "source_id": section.get("source_id"),
            "repo": section.get("repo"),
            "path": section.get("path"),
            "heading": section.get("heading"),
            "heading_path": section.get("heading_path"),
            "ordinal": section.get("ordinal"),
            "domains": section.get("domains"),
            "section_label": section.get("section_label"),
        }
        traversals = self._parse_supports_traversals(
            section.get("supports_traversals") or []
        )
        if traversals.get("framework"):
            meta["framework"] = traversals["framework"]
        meta.update({k: v for k, v in traversals.items() if k not in meta})
        if section.get("controls"):
            meta["controls"] = section["controls"]
        if section.get("requirements"):
            meta["requirements"] = section["requirements"]

        return Document(page_content=content, metadata=meta)

    def load_enriched_file(self, file_path: Path) -> tuple:
        """
        Load an enriched JSON file (doc_type + sections) and convert to LangChain Documents.
        Returns (doc_type, List[Document]) with metadata.type and metadata.store_name set.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        doc_type = data.get("doc_type", file_path.stem.lower())
        sections = data.get("sections") or []
        documents = [
            self.convert_enriched_section_to_document(sec, doc_type)
            for sec in sections
        ]
        return doc_type, documents

    def discover_enriched_files(
        self,
        enriched_dir: Optional[Path] = None,
        enriched_subdirs: Optional[List[str]] = None,
    ) -> Dict[str, List[Document]]:
        """
        Load enriched/*.json (kb-dump-utility format) from one or more subdirs, convert sections to Documents,
        and return documents grouped by store_name. Use enriched_subdirs to merge e.g. enriched + enriched_vendor.
        """
        subdirs = enriched_subdirs if enriched_subdirs else ["enriched"]
        bases = [Path(enriched_dir)] if enriched_dir is not None else [self.preview_dir / s for s in subdirs]
        by_store = defaultdict(list)
        for base in bases:
            if not base.exists() or not base.is_dir():
                logger.debug(f"Enriched subdir not found, skipping: {base}")
                continue
            for json_file in base.glob("*.json"):
                try:
                    doc_type, docs = self.load_enriched_file(json_file)
                    for doc in docs:
                        store_name = doc.metadata.get("store_name", "domain_knowledge")
                        by_store[store_name].append(doc)
                except Exception as e:
                    logger.warning(f"Error loading enriched file {json_file.name}: {e}")
        if by_store:
            total = sum(len(d) for d in by_store.values())
            logger.info(f"Discovered {total} enriched sections across {len(by_store)} stores")
            for store_name, docs in by_store.items():
                logger.info(f"  {store_name}: {len(docs)} documents")
        return dict(by_store)

    def _load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load checkpoint from file if it exists and matches current run. Returns None if disabled or invalid."""
        if not self.checkpoint_file:
            return None
        if self.clear_checkpoint and self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info("Cleared checkpoint file: %s", self.checkpoint_file)
            except OSError as e:
                logger.warning("Could not delete checkpoint file: %s", e)
            return None
        if not self.checkpoint_file.exists():
            return None
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Match single preview_dir or list of preview_dirs
            saved_dirs = data.get("preview_dirs")
            if saved_dirs is not None:
                if sorted(str(Path(d).resolve()) for d in saved_dirs) != sorted(str(p.resolve()) for p in self.preview_dirs):
                    logger.warning("Checkpoint preview_dirs mismatch, ignoring checkpoint")
                    return None
            else:
                preview_dir = str(Path(data.get("preview_dir", "")).resolve())
                if preview_dir != str(self.preview_dir.resolve()):
                    logger.warning("Checkpoint preview_dir mismatch, ignoring checkpoint")
                    return None
            subs = data.get("enriched_subdirs")
            expected = (self.enriched_subdirs or ["enriched"]) if self.enriched_subdirs else ["enriched"]
            if subs is not None and sorted(subs or []) != sorted(expected):
                logger.warning("Checkpoint enriched_subdirs mismatch, ignoring checkpoint")
                return None
            if data.get("vector_store_type") != self.vector_store_type:
                logger.warning("Checkpoint vector_store_type mismatch, ignoring checkpoint")
                return None
            logger.info("Resuming from checkpoint: %s", self.checkpoint_file)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load checkpoint: %s", e)
            return None

    def _save_checkpoint(self, data: Dict[str, Any]) -> None:
        """Write checkpoint atomically (write to .tmp then rename)."""
        if not self.checkpoint_file:
            return
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data["preview_dir"] = str(self.preview_dir.resolve())
        if len(self.preview_dirs) > 1:
            data["preview_dirs"] = [str(p.resolve()) for p in self.preview_dirs]
        data["enriched_subdirs"] = self.enriched_subdirs or ["enriched"]
        data["vector_store_type"] = self.vector_store_type
        tmp = self.checkpoint_file.with_suffix(self.checkpoint_file.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.checkpoint_file)
        except OSError as e:
            logger.warning("Could not save checkpoint: %s", e)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    async def ingest_enriched_documents(
        self,
        enriched_by_store: Dict[str, List[Document]],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest kb-dump-utility enriched documents (grouped by store_name) into collection_factory stores.
        Uses route_documents_to_stores(store_name, documents) then add_documents so assistants see data with minimal changes.
        When checkpoint_file is set, progress is saved after each batch and resume is supported on restart.
        """
        all_results = []
        total_documents = 0
        total_by_store = defaultdict(int)
        checkpoint = None
        if not dry_run and self.checkpoint_file:
            checkpoint = self._load_checkpoint()
            if checkpoint is None:
                checkpoint = {"stores": {}}
            checkpoint.setdefault("stores", {})
        for store_name, documents in enriched_by_store.items():
            routed_docs = self.route_documents_to_stores(documents, store_name)
            for sn, docs in routed_docs.items():
                total_by_store[sn] += len(docs)
                total_documents += len(docs)
                if dry_run:
                    all_results.append(
                        {"source": "enriched", "store_name": sn, "count": len(docs), "dry_run": True}
                    )
                    continue
                if sn not in self.indexing_service.stores:
                    logger.warning(f"  Store '{sn}' not in indexing_service.stores, skipping {len(docs)} enriched documents")
                    continue
                resume_from = 0
                if checkpoint is not None:
                    resume_from = min(checkpoint.get("stores", {}).get(sn, 0), len(docs))
                    if resume_from >= len(docs):
                        logger.info(f"  Skipping {sn} (already complete: {resume_from}/{len(docs)})")
                        all_results.append({"source": "enriched", "store_name": sn, "count": len(docs), "success": True, "resumed": True})
                        continue
                    if resume_from > 0:
                        logger.info(f"  Resuming {sn} from {resume_from}/{len(docs)}")
                docs_to_process = docs[resume_from:]
                store = self.indexing_service.stores[sn]
                batch_size = getattr(self, "document_batch_size", 200)
                ingested_count = 0
                last_error = None
                for start in range(0, len(docs_to_process), batch_size):
                    batch = docs_to_process[start : start + batch_size]
                    try:
                        store.add_documents(batch)
                        ingested_count += len(batch)
                        if checkpoint is not None:
                            checkpoint.setdefault("stores", {})[sn] = resume_from + start + len(batch)
                            self._save_checkpoint(checkpoint)
                        if len(docs_to_process) > batch_size and (start // batch_size + 1) % 5 == 0:
                            logger.info(f"  Ingested {resume_from + min(start + batch_size, len(docs_to_process))}/{len(docs)} enriched docs to {sn}")
                    except Exception as e:
                        last_error = e
                        logger.warning(f"  Batch failed for {sn} at offset {resume_from + start}: {e}")
                if last_error and ingested_count == 0:
                    all_results.append({"source": "enriched", "store_name": sn, "count": len(docs), "error": str(last_error)})
                else:
                    logger.info(f"  ✓ Ingested {resume_from + ingested_count}/{len(docs)} enriched documents to {sn}")
                    all_results.append({"source": "enriched", "store_name": sn, "count": resume_from + ingested_count, "success": True})
                    if last_error:
                        all_results[-1]["partial_error"] = str(last_error)
        return {
            "results": all_results,
            "total_documents": total_documents,
            "stores": dict(total_by_store),
        }

    def route_documents_to_stores(
        self,
        documents: List[Document],
        content_type: str
    ) -> Dict[str, List[Document]]:
        """
        Route documents to appropriate stores based on content_type and extraction_type.
        Uses fixed collections with metadata-based filtering (type, framework, etc.).
        
        Args:
            documents: List of documents to route
            content_type: Content type from preview file
            
        Returns:
            Dictionary mapping store_name to list of documents with updated metadata
        """
        routed = defaultdict(list)
        
        # Check if this is a contextual graph content type
        if content_type in self.CONTEXTUAL_GRAPH_CONTENT_TYPES:
            # Route to contextual graph storage (will be handled separately)
            routed["_contextual_graph"] = documents
            return dict(routed)
        
        # Special handling for knowledgebase and metrics collection - split by entity_type, route to appropriate stores
        if content_type in ("knowledgebase", "metrics"):
            for doc in documents:
                entity_type = doc.metadata.get("entity_type", "")
                store_name = self.KNOWLEDGEBASE_ENTITY_TO_STORE.get(
                    entity_type,
                    "entities"  # Default fallback
                )
                
                # Create a copy to avoid modifying original
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                
                # Ensure entity_type is in metadata for filtering
                if entity_type:
                    doc_copy.metadata["entity_type"] = entity_type
                
                # For features and metrics, ensure mdl_entity_type is set
                if entity_type in ["feature", "metric"]:
                    doc_copy.metadata["mdl_entity_type"] = entity_type
                    doc_copy.metadata["type"] = "ENTITY"  # Match ChromaDB collection type
                
                # For instructions, ensure type is set
                if entity_type == "instruction":
                    doc_copy.metadata["type"] = "INSTRUCTION"
                
                # For examples, ensure type is set to SQL_PAIR
                if entity_type == "example":
                    doc_copy.metadata["type"] = "SQL_PAIR"
                
                # Add source information
                doc_copy.metadata["source_content_type"] = content_type
                
                routed[store_name].append(doc_copy)
                
                logger.debug(f"  Routed knowledgebase entity '{entity_type}' to {store_name}")
        
        # Special handling for policy_documents - split by extraction_type, route to general stores
        elif content_type == "policy_documents":
            for doc in documents:
                extraction_type = doc.metadata.get("extraction_type", "full_content")
                store_name = self.EXTRACTION_TYPE_TO_POLICY_STORE.get(
                    extraction_type,
                    "domain_knowledge"  # Default fallback
                )
                
                # Create a copy to avoid modifying original
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                
                # Set type="policy" in metadata for filtering
                doc_copy.metadata["type"] = "policy"
                
                # Ensure framework is in metadata (not collection name)
                if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                    doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                
                # Add source information
                doc_copy.metadata["source_content_type"] = content_type
                
                routed[store_name].append(doc_copy)
        elif content_type in ["risk_controls", "riskmanagement_risk_controls"]:
            # Route risk controls - handle split files by extraction_type
            for doc in documents:
                # Create a copy to avoid modifying original
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                
                # Check if this is a split file (has extraction_type in metadata)
                extraction_type = doc_copy.metadata.get("extraction_type")
                
                if extraction_type and extraction_type != "base":
                    # This is a split document - route based on extraction_type
                    store_name = self.EXTRACTION_TYPE_TO_RISK_STORE.get(
                        extraction_type,
                        "domain_knowledge"  # Default fallback
                    )
                    
                    # Set type in metadata for filtering (e.g., "risk_control", "risk_entities")
                    doc_copy.metadata["type"] = f"risk_{extraction_type}"
                    
                    # Preserve framework if present
                    if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                        doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                    
                    # Add source information
                    doc_copy.metadata["source_content_type"] = content_type
                    
                    routed[store_name].append(doc_copy)
                else:
                    # Non-split or base document - route to domain_knowledge
                    doc_copy.metadata["type"] = "risk"
                    if extraction_type == "base":
                        doc_copy.metadata["type"] = "risk_base"
                    
                    # Preserve framework if present
                    if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                        doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                    
                    routed["domain_knowledge"].append(doc_copy)
        elif content_type in ["product_purpose", "product_docs_link", "product_key_concepts", "product_key_concept", 
                              "extendable_entity", "extendable_doc"]:
            # Route product content types to general stores with type="product" in metadata
            for doc in documents:
                # Create a copy to avoid modifying original
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                
                # Set type="product" in metadata for filtering
                doc_copy.metadata["type"] = "product"
                
                # Route to appropriate general store based on content type
                if content_type in ["product_purpose", "product_docs_link", "extendable_doc"]:
                    # Purpose, docs, and extendable docs go to domain_knowledge
                    store_name = "domain_knowledge"
                elif content_type in ["product_key_concepts", "product_key_concept", "extendable_entity"]:
                    # Key concepts and extendable entities go to entities store
                    store_name = "entities"
                else:
                    # Default fallback
                    store_name = "domain_knowledge"
                
                # Preserve product_name if present
                if "product_name" not in doc_copy.metadata and doc_copy.metadata.get("product"):
                    doc_copy.metadata["product_name"] = doc_copy.metadata.get("product")
                
                # Add source information
                doc_copy.metadata["source_content_type"] = content_type
                
                routed[store_name].append(doc_copy)
        elif content_type == "domain_knowledge":
            # Domain knowledge for policies should have type="policies" in metadata
            for doc in documents:
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                # If it's policy-related domain knowledge, set type="policies"
                if "policy" in content_type.lower() or doc_copy.metadata.get("policy_related"):
                    doc_copy.metadata["type"] = "policies"
                # Preserve framework if present
                if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                    doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                routed["domain_knowledge"].append(doc_copy)
        elif content_type == "soc2_controls":
            # Route SOC2 controls to compliance_controls store with framework="SOC2"
            for doc in documents:
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                # Ensure framework is set to SOC2
                doc_copy.metadata["framework"] = "SOC2"
                # Preserve framework if already set
                if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                    doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                # Add source information
                doc_copy.metadata["source_content_type"] = content_type
                routed["compliance_controls"].append(doc_copy)
        elif content_type in ["entities", "evidence", "fields", "controls"]:
            # Route to general collections with metadata.type set
            for doc in documents:
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                # Set type in metadata for filtering
                if "type" not in doc_copy.metadata:
                    # Use extraction_type if available, otherwise infer from content_type
                    extraction_type = doc_copy.metadata.get("extraction_type")
                    if extraction_type:
                        doc_copy.metadata["type"] = extraction_type
                    else:
                        doc_copy.metadata["type"] = content_type
                # Move framework_name to framework if present
                if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                    doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                routed[content_type].append(doc_copy)
        elif content_type in (
            "policy_controls", "policy_risks", "policy_key_concepts",
            "policy_identifiers", "policy_framework_docs", "policy_edges",
        ):
            # Policy preview (kb-dump-utility preview_policy) -> single _new store per type
            store_name = self.CONTENT_TYPE_TO_STORE.get(content_type, content_type)
            for doc in documents:
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                doc_copy.metadata["source_content_type"] = content_type
                if "type" not in doc_copy.metadata:
                    doc_copy.metadata["type"] = "policy_preview"
                routed[store_name].append(doc_copy)
            return dict(routed)
        else:
            # For other content types, use direct mapping
            store_name = self.CONTENT_TYPE_TO_STORE.get(
                content_type,
                content_type  # Fallback to content_type as store name
            )
            
            # Ensure framework is in metadata for compliance/policy collections
            for doc in documents:
                doc_copy = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy() if doc.metadata else {}
                )
                # Move framework_name to framework if present
                if "framework" not in doc_copy.metadata and doc_copy.metadata.get("framework_name"):
                    doc_copy.metadata["framework"] = doc_copy.metadata.get("framework_name")
                # For schema collections, ensure type is set
                if store_name in ["table_definitions", "table_descriptions", "column_definitions", "schema_descriptions"]:
                    if "type" not in doc_copy.metadata:
                        # Infer type from content_type or store_name
                        if "definition" in store_name:
                            doc_copy.metadata["type"] = "definition"
                        elif "description" in store_name:
                            doc_copy.metadata["type"] = "description"
                routed[store_name].append(doc_copy)
        
        return dict(routed)
    
    def _get_extraction_type_for_store(self, store_name: str, content_type: str) -> str:
        """
        Get extraction_type for document_kg_insights based on store_name and content_type.
        
        Args:
            store_name: Store name (e.g., "entities", "controls", "domain_knowledge", "table_definitions")
            content_type: Content type from preview file
            
        Returns:
            Extraction type string for document_kg_insights table
        """
        # For product content types, prioritize content_type-based mapping
        # since they may be routed to general stores (entities, domain_knowledge)
        if "product" in content_type.lower() or "connector" in content_type.lower():
            # Map product content types to specific extraction types
            if "entity" in content_type.lower() or "extendable_entity" in content_type.lower():
                return "entities"
            elif "concept" in content_type.lower():
                return "entities"  # Key concepts are entities
            elif "purpose" in content_type.lower() or "doc" in content_type.lower():
                return "product"  # Purpose and docs are product-level
            else:
                return "product"
        
        # First try store_name mapping
        if store_name in self.STORE_NAME_TO_EXTRACTION_TYPE:
            return self.STORE_NAME_TO_EXTRACTION_TYPE[store_name]
        
        # Fallback to content_type-based mapping
        if "policy" in content_type.lower():
            if "context" in content_type.lower():
                return "context"
            elif "entity" in content_type.lower():
                return "entities"
            elif "requirement" in content_type.lower():
                return "requirement"
            elif "evidence" in content_type.lower():
                return "evidence"
            elif "field" in content_type.lower():
                return "fields"
            else:
                return "full_content"
        elif "control" in content_type.lower() or "risk" in content_type.lower():
            # For risk controls, check if it's a split file by looking at store_name
            # If store_name is "controls", "entities", "fields", etc., it's a split file
            if store_name in ["controls", "entities", "fields", "evidence"]:
                # This is a split risk control file
                if store_name == "controls":
                    return "control"
                elif store_name == "entities":
                    return "entities"
                elif store_name == "fields":
                    return "fields"
                elif store_name == "evidence":
                    return "evidence"
            return "control"
        elif "schema" in content_type.lower() or "table" in content_type.lower() or "column" in content_type.lower():
            return "schema"
        elif "product" in content_type.lower() or "connector" in content_type.lower():
            return "product"
        else:
            return "document"
    
    async def _save_doc_insights_batch_to_postgres(
        self,
        doc_insights: List[Dict[str, Any]]
    ) -> int:
        """
        Save multiple document insights to PostgreSQL document_kg_insights table in a batch.
        
        Args:
            doc_insights: List of dictionaries with keys:
                - doc_id: Document ID (matches ChromaDB document ID)
                - document_content: Original document content
                - extraction_type: Type of extraction (context, control, entities, fields, etc.)
                - extracted_data: Extracted data as dictionary
                - context_id: Optional context ID
                - extraction_metadata: Optional extraction metadata
            
        Returns:
            Number of documents successfully saved
        """
        if not self.db_pool or not doc_insights:
            return 0
        
        try:
            async with self.db_pool.acquire() as conn:
                # Use executemany for batch insert
                values = []
                for insight in doc_insights:
                    values.append((
                        insight["doc_id"],
                        insight["document_content"],
                        insight["extraction_type"],
                        json.dumps(insight["extracted_data"]),
                        insight.get("context_id"),
                        json.dumps(insight.get("extraction_metadata")) if insight.get("extraction_metadata") else None
                    ))
                
                # Use COPY or batch INSERT with executemany
                # For better performance with many rows, we'll use a single transaction
                async with conn.transaction():
                    await conn.executemany(
                        """
                        INSERT INTO document_kg_insights (
                            doc_id, document_content, extraction_type, extracted_data,
                            context_id, extraction_metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (doc_id) DO UPDATE SET
                            document_content = EXCLUDED.document_content,
                            extraction_type = EXCLUDED.extraction_type,
                            extracted_data = EXCLUDED.extracted_data,
                            context_id = EXCLUDED.context_id,
                            extraction_metadata = EXCLUDED.extraction_metadata,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        values
                    )
                
                return len(doc_insights)
        except Exception as e:
            logger.warning(f"Failed to save batch of {len(doc_insights)} doc insights to PostgreSQL: {str(e)}")
            logger.debug(f"  PostgreSQL batch error details: {type(e).__name__}: {str(e)}", exc_info=True)
            return 0
    
    def extract_contextual_graph_data(
        self,
        documents: List[Document],
        content_type: str
    ) -> Dict[str, List[Any]]:
        """
        Extract contextual graph data from documents.
        
        This method extracts contextual graph data from various content types:
        - Context types (domain_knowledge with type="policy", etc.) -> ContextDefinition
        - Control types (compliance_controls, risk_controls) -> ControlContextProfile
        - Edge types (contextual_edges) -> ContextualEdge
        
        Args:
            documents: List of documents
            content_type: Content type identifier
            
        Returns:
            Dictionary with 'contexts', 'edges', and 'profiles' lists
        """
        result = {
            "contexts": [],
            "edges": [],
            "profiles": []
        }
        
        if not self.contextual_graph_storage:
            return result
        
        # Helper function to parse JSON fields
        def parse_json_field(value, default=[]):
            if value is None:
                return default
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return default
            if isinstance(value, list):
                return value
            return default
        
        # Content types that should be saved as contexts
        context_content_types = {
            "domain_knowledge", "context_definitions",  # domain_knowledge with type="policy" for policy contexts
            "policy_documents"  # Policy documents can also be contexts
        }
        
        # Content types that should be saved as control profiles
        control_content_types = {
            "compliance_controls", "risk_controls", "riskmanagement_risk_controls",
            "control_context_profiles"
        }
        
        # Content types that are edges
        edge_content_types = {
            "contextual_edges"
        }
        
        for doc in documents:
            metadata = doc.metadata or {}
            page_content = doc.page_content or ""
            doc_id = metadata.get("id") or metadata.get("document_id") or ""
            
            try:
                # Check if this is an edge
                if content_type in edge_content_types or metadata.get("edge_id"):
                    # Get edge_id from metadata, doc_id, or generate a proper UUID
                    edge_id = metadata.get("edge_id") or doc_id
                    
                    # Ensure edge_id is a valid UUID for Qdrant compatibility
                    if edge_id:
                        # Try to parse as UUID, if it fails, generate a new UUID
                        try:
                            # Check if it's already a valid UUID format
                            UUID(edge_id)
                        except (ValueError, AttributeError, TypeError):
                            # Not a valid UUID, generate a deterministic UUID from the edge_id string
                            # Use UUID5 with DNS namespace to create deterministic UUIDs
                            edge_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(edge_id)))
                    else:
                        # No edge_id available, generate a new random UUID
                        edge_id = str(uuid4())
                    
                    if edge_id:
                        edge = ContextualEdge(
                            edge_id=edge_id,
                            document=page_content,
                            source_entity_id=metadata.get("source_entity_id", ""),
                            source_entity_type=metadata.get("source_entity_type", ""),
                            target_entity_id=metadata.get("target_entity_id", ""),
                            target_entity_type=metadata.get("target_entity_type", ""),
                            edge_type=metadata.get("edge_type", "RELATED_TO"),
                            context_id=metadata.get("context_id", ""),
                            relevance_score=metadata.get("relevance_score", 0.0),
                            priority_in_context=metadata.get("priority_in_context"),
                            risk_score_in_context=metadata.get("risk_score_in_context"),
                            likelihood_in_context=metadata.get("likelihood_in_context"),
                            impact_in_context=metadata.get("impact_in_context"),
                            implementation_complexity=metadata.get("implementation_complexity"),
                            estimated_effort_hours=metadata.get("estimated_effort_hours"),
                            estimated_cost=metadata.get("estimated_cost"),
                            prerequisites=parse_json_field(metadata.get("prerequisites")),
                            automation_possible=metadata.get("automation_possible", False),
                            evidence_available=metadata.get("evidence_available", False),
                            data_quality=metadata.get("data_quality"),
                            created_at=metadata.get("created_at"),
                            valid_until=metadata.get("valid_until")
                        )
                        result["edges"].append(edge)
                
                # Check if this is a control profile
                elif content_type in control_content_types or metadata.get("profile_id") or metadata.get("control_id"):
                    profile_id = metadata.get("profile_id") or doc_id
                    control_id = metadata.get("control_id") or metadata.get("id", "")
                    
                    if profile_id or control_id:
                        # Use control_id as profile_id if profile_id not provided
                        if not profile_id and control_id:
                            context_id = metadata.get("context_id", "")
                            if context_id:
                                # Generate deterministic UUID from control_id and context_id
                                profile_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"profile_{control_id}_{context_id}"))
                            else:
                                # Generate deterministic UUID from control_id
                                profile_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"profile_{control_id}"))
                        
                        # Ensure profile_id is a valid UUID
                        if profile_id:
                            try:
                                UUID(profile_id)
                            except (ValueError, AttributeError, TypeError):
                                # Not a valid UUID, convert it
                                profile_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(profile_id)))
                        
                        profile = ControlContextProfile(
                            profile_id=profile_id,
                            document=page_content,
                            control_id=control_id,
                            context_id=metadata.get("context_id", ""),
                            framework=metadata.get("framework"),
                            control_category=metadata.get("control_category") or metadata.get("category"),
                            inherent_risk_score=metadata.get("inherent_risk_score"),
                            current_control_effectiveness=metadata.get("current_control_effectiveness"),
                            residual_risk_score=metadata.get("residual_risk_score"),
                            risk_level=metadata.get("risk_level"),
                            implementation_complexity=metadata.get("implementation_complexity"),
                            estimated_effort_hours=metadata.get("estimated_effort_hours"),
                            estimated_cost=metadata.get("estimated_cost"),
                            success_probability=metadata.get("success_probability"),
                            implementation_feasibility=metadata.get("implementation_feasibility"),
                            timeline_weeks=metadata.get("timeline_weeks"),
                            automation_possible=metadata.get("automation_possible", False),
                            automation_coverage=metadata.get("automation_coverage"),
                            manual_effort_remaining=metadata.get("manual_effort_remaining"),
                            evidence_available=metadata.get("evidence_available", False),
                            evidence_quality=metadata.get("evidence_quality"),
                            evidence_gaps=parse_json_field(metadata.get("evidence_gaps")),
                            systems_in_scope=parse_json_field(metadata.get("systems_in_scope")),
                            systems_count=metadata.get("systems_count"),
                            users_in_scope=metadata.get("users_in_scope"),
                            integration_maturity=metadata.get("integration_maturity"),
                            metrics_defined=metadata.get("metrics_defined", False),
                            metrics_count=metadata.get("metrics_count"),
                            metrics_automated=metadata.get("metrics_automated"),
                            created_at=metadata.get("created_at"),
                            updated_at=metadata.get("updated_at")
                        )
                        result["profiles"].append(profile)
                
                # Check if this is a context (most common case)
                elif content_type in context_content_types or metadata.get("context_id") or metadata.get("extraction_type") == "context":
                    context_id = metadata.get("context_id") or doc_id
                    
                    # Generate context_id from content if not available
                    if not context_id:
                        # Generate a deterministic UUID from content
                        context_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ctx_{content_type}_{page_content[:100]}"))
                    
                    # Ensure context_id is a valid UUID
                    if context_id:
                        try:
                            UUID(context_id)
                        except (ValueError, AttributeError, TypeError):
                            # Not a valid UUID, convert it
                            context_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(context_id)))
                    
                    if context_id:
                        context = ContextDefinition(
                            context_id=context_id,
                            document=page_content,
                            context_type=metadata.get("context_type", "organizational_situational"),
                            industry=metadata.get("industry"),
                            organization_size=metadata.get("organization_size"),
                            employee_count_range=metadata.get("employee_count_range"),
                            maturity_level=metadata.get("maturity_level"),
                            regulatory_frameworks=parse_json_field(metadata.get("regulatory_frameworks")),
                            data_types=parse_json_field(metadata.get("data_types")),
                            systems=parse_json_field(metadata.get("systems")),
                            automation_capability=metadata.get("automation_capability"),
                            current_situation=metadata.get("current_situation"),
                            audit_timeline_days=metadata.get("audit_timeline_days"),
                            active_status=metadata.get("active_status", True),
                            created_at=metadata.get("created_at"),
                            updated_at=metadata.get("updated_at")
                        )
                        result["contexts"].append(context)
            except Exception as e:
                logger.warning(f"Error extracting contextual graph data from document (content_type={content_type}): {e}")
                logger.debug(f"  Document metadata keys: {list(metadata.keys())}")
        
        return result
    
    def _recreate_collections(self):
        """Delete and recreate all collections to fix dimension mismatches."""
        if self.vector_store_type != "chroma":
            logger.warning("Force recreate only supported for ChromaDB")
            return
        
        logger.info("Force recreating collections...")
        
        # Get persistent client
        if not hasattr(self.indexing_service, 'persistent_client') or self.indexing_service.persistent_client is None:
            logger.warning("Persistent client not available, cannot recreate collections")
            return
        
        persistent_client = self.indexing_service.persistent_client
        
        # Get all store names from the indexing service
        all_store_names = set(self.indexing_service.stores.keys())
        
        # Also discover files to find any additional stores that might be needed
        try:
            files_by_type = self.discover_preview_files()
            for content_type, file_paths in files_by_type.items():
                if file_paths:
                    # Load first file to determine routing
                    try:
                        file_data = self.load_preview_file(file_paths[0])
                        if file_data is None:
                            continue
                        actual_content_type = file_data.get("metadata", {}).get("content_type", content_type)
                        documents = self.convert_to_documents(file_data)
                        routed = self.route_documents_to_stores(documents, actual_content_type)
                        all_store_names.update(routed.keys())
                    except Exception as e:
                        logger.debug(f"Could not determine routing for {content_type}: {e}")
        except Exception as e:
            logger.warning(f"Could not discover preview files for collection recreation: {e}")
        
        # Delete collections
        deleted_count = 0
        for store_name in all_store_names:
            collection_name = self._get_collection_name(store_name)
            try:
                # Try to get collection to see if it exists
                try:
                    collection = persistent_client.get_collection(name=collection_name)
                    logger.info(f"Deleting existing collection: {collection_name}")
                    persistent_client.delete_collection(name=collection_name)
                    logger.info(f"Deleted collection: {collection_name}")
                    deleted_count += 1
                except Exception as get_error:
                    # Collection doesn't exist, that's fine
                    logger.debug(f"Collection {collection_name} doesn't exist, skipping deletion")
            except Exception as e:
                logger.warning(f"Error deleting collection {collection_name}: {e}")
        
        logger.info(f"Deleted {deleted_count} collections. They will be recreated when stores are initialized.")
    
    async def ingest_file(
        self,
        file_path: Path,
        content_type: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Ingest a single preview file into ChromaDB stores.
        
        Args:
            file_path: Path to preview JSON file
            content_type: Content type identifier (from directory name, may be overridden by file metadata)
            dry_run: If True, only show what would be ingested without actually ingesting
            
        Returns:
            Dictionary with ingestion results
        """
        logger.info(f"Processing file: {file_path.name} (content_type: {content_type})")
        
        # Load file (skip invalid/empty JSON)
        file_data = self.load_preview_file(file_path)
        if file_data is None:
            logger.warning(f"Skipped {file_path.name} (invalid or empty JSON)")
            return {
                "file_path": str(file_path),
                "content_type": content_type,
                "total_documents": 0,
                "stores": {},
                "contextual_graph": {},
                "skipped": True,
                "skip_reason": "invalid or empty JSON",
            }
        file_metadata = file_data.get("metadata", {})
        # Convert to Document objects (metrics collection uses "items", others use "documents")
        documents = self.convert_to_documents(file_data)
        document_count = file_metadata.get("document_count") or len(documents)

        # Use content_type from file metadata if available (more accurate)
        actual_content_type = file_metadata.get("content_type", content_type)
        # Ensure column_definitions have stable entity id matching contextual_edges (TABLE_HAS_COLUMN / COLUMN_BELONGS_TO_TABLE)
        if actual_content_type == "column_definitions":
            for doc in documents:
                if (doc.metadata.get("table_name") or doc.metadata.get("column_name")) and not doc.metadata.get("id"):
                    col_id = self._column_entity_id(doc.metadata)
                    if col_id:
                        doc.metadata["id"] = col_id
                        if not doc.metadata.get("document_id"):
                            doc.metadata["document_id"] = col_id

        # Check if this is a split file
        is_split_file = file_metadata.get("split", False) or "_split" in file_path.name
        if is_split_file:
            original_count = file_metadata.get("original_document_count", document_count)
            logger.info(f"  Detected split file: {original_count} original documents split into {document_count} documents")
        if actual_content_type != content_type:
            logger.info(f"  Using content_type from file metadata: {actual_content_type}")

        logger.info(f"  Loaded {len(documents)} documents from {file_path.name}")
        
        # Route documents to stores using actual content type
        routed_docs = self.route_documents_to_stores(documents, actual_content_type)
        
        # Log routing information for split files
        if is_split_file:
            logger.info(f"  Routing split documents to {len(routed_docs)} stores:")
            for store_name, docs in routed_docs.items():
                extraction_types = {}
                for doc in docs:
                    ext_type = doc.metadata.get("extraction_type", "unknown")
                    extraction_types[ext_type] = extraction_types.get(ext_type, 0) + 1
                logger.info(f"    {store_name}: {len(docs)} documents ({', '.join([f'{k}:{v}' for k, v in extraction_types.items()])})")
        
        results = {
            "file_path": str(file_path),
            "content_type": actual_content_type,
            "total_documents": len(documents),
            "stores": {},
            "contextual_graph": {}
        }
        
        # Extract contextual graph data from all documents (if not skipped)
        # This allows domain_knowledge (with type="policy"), compliance_controls, etc. to be saved to contextual graph
        contextual_graph_data = None
        if not self.skip_contextual_graph and self.contextual_graph_storage:
            # Extract from all documents, not just specific content types
            contextual_graph_data = self.extract_contextual_graph_data(
                documents,  # Use all documents, not just routed ones
                actual_content_type
            )
            
            # If this was explicitly a contextual graph content type, remove from routed_docs
            if "_contextual_graph" in routed_docs:
                del routed_docs["_contextual_graph"]
        elif self.skip_contextual_graph:
            logger.info("  Skipping contextual graph extraction (--skip-contextual-graph flag set)")
            # Remove contextual graph content types from routed_docs if present
            if "_contextual_graph" in routed_docs:
                del routed_docs["_contextual_graph"]
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would ingest to {len(routed_docs)} stores:")
            for store_name, docs in routed_docs.items():
                logger.info(f"    {store_name}: {len(docs)} documents")
                results["stores"][store_name] = {
                    "count": len(docs),
                    "dry_run": True
                }
            
            # Show contextual graph data that would be ingested
            if contextual_graph_data:
                logger.info(f"  [DRY RUN] Would ingest contextual graph data:")
                if contextual_graph_data["contexts"]:
                    logger.info(f"    Context Definitions: {len(contextual_graph_data['contexts'])}")
                if contextual_graph_data["edges"]:
                    logger.info(f"    Contextual Edges: {len(contextual_graph_data['edges'])}")
                if contextual_graph_data["profiles"]:
                    logger.info(f"    Control Context Profiles: {len(contextual_graph_data['profiles'])}")
                results["contextual_graph"] = {
                    "contexts": len(contextual_graph_data["contexts"]),
                    "edges": len(contextual_graph_data["edges"]),
                    "profiles": len(contextual_graph_data["profiles"]),
                    "dry_run": True
                }
            return results
        
        # Ingest contextual graph data first
        if contextual_graph_data and self.contextual_graph_storage:
            try:
                # Initialize database client if not already initialized (lazy initialization)
                if not hasattr(self, '_db_client_initialized') or not self._db_client_initialized:
                    try:
                        # Get database client (which wraps the pool)
                        self.db_client = await get_database_client()
                        # Ensure it's connected
                        if not hasattr(self.db_client, '_pool') or self.db_client._pool is None:
                            await self.db_client.connect()
                        
                        self.control_service = ControlStorageService(self.db_client)
                        self._db_client_initialized = True
                        logger.info("  ✓ Initialized database client for PostgreSQL storage")
                    except Exception as db_error:
                        logger.warning(f"  Could not initialize database client: {db_error}. Controls will only be saved to vector store.")
                        logger.debug(f"  Database error details: {type(db_error).__name__}: {str(db_error)}", exc_info=True)
                        self._db_client_initialized = False
                
                if contextual_graph_data["contexts"]:
                    context_ids = await self.contextual_graph_storage.save_context_definitions(
                        contextual_graph_data["contexts"]
                    )
                    logger.info(f"  ✓ Ingested {len(context_ids)} context definitions to contextual graph (vector store)")
                    results["contextual_graph"]["contexts"] = {
                        "success": True,
                        "count": len(context_ids),
                        "storage": "vector_store"
                    }
                
                if contextual_graph_data["edges"]:
                    # Save edges to vector store (with batching for performance)
                    edge_ids = await self.contextual_graph_storage.save_contextual_edges(
                        contextual_graph_data["edges"],
                        batch_size=self.edge_batch_size
                    )
                    logger.info(f"  ✓ Ingested {len(edge_ids)} contextual edges to contextual graph (vector store)")
                    
                    # Also save edges to PostgreSQL (with batching for performance)
                    edges_saved_to_postgres = 0
                    try:
                        # Initialize database pool if not already initialized
                        if not hasattr(self, '_db_pool_initialized') or not self._db_pool_initialized:
                            try:
                                self.db_pool = await get_database_pool()
                                self._db_pool_initialized = True
                                logger.info("  ✓ Initialized database pool for PostgreSQL edge storage")
                            except Exception as db_pool_error:
                                logger.warning(f"  Could not initialize database pool: {db_pool_error}. Edges will only be saved to vector store.")
                                logger.debug(f"  Database pool error details: {type(db_pool_error).__name__}: {str(db_pool_error)}", exc_info=True)
                                self.db_pool = None
                        
                        if self.db_pool:
                            edges_saved_to_postgres = await self.contextual_graph_storage.save_edges_to_postgres(
                                contextual_graph_data["edges"],
                                db_pool=self.db_pool,
                                batch_size=self.edge_postgres_batch_size
                            )
                            if edges_saved_to_postgres > 0:
                                logger.info(f"  ✓ Saved {edges_saved_to_postgres} contextual edges to PostgreSQL")
                    except Exception as postgres_error:
                        logger.warning(f"  Could not save edges to PostgreSQL: {postgres_error}")
                        logger.debug(f"  PostgreSQL error details: {type(postgres_error).__name__}: {str(postgres_error)}", exc_info=True)
                    
                    results["contextual_graph"]["edges"] = {
                        "success": True,
                        "count": len(edge_ids),
                        "storage": "vector_store",
                        "postgres_count": edges_saved_to_postgres if hasattr(self, 'db_pool') and self.db_pool else 0
                    }
                
                if contextual_graph_data["profiles"]:
                    # For control profiles, save to both PostgreSQL and vector store
                    profile_ids = []
                    controls_saved_to_db = 0
                    
                    for profile in contextual_graph_data["profiles"]:
                        try:
                            # Save Control entity to PostgreSQL if we have database access
                            if self._db_client_initialized and self.control_service and profile.control_id:
                                try:
                                    control = Control(
                                        control_id=profile.control_id,
                                        framework=profile.framework or "unknown",
                                        control_name=profile.document[:200] if profile.document else f"Control {profile.control_id}",
                                        control_description=profile.document[:1000] if profile.document else None,
                                        category=profile.control_category,
                                        vector_doc_id=profile.profile_id
                                    )
                                    await self.control_service.save_control(control)
                                    controls_saved_to_db += 1
                                    logger.debug(f"  Saved control {profile.control_id} to PostgreSQL")
                                except Exception as db_save_error:
                                    logger.warning(f"  Could not save control {profile.control_id} to PostgreSQL: {db_save_error}")
                                    logger.debug(f"  Database save error details: {type(db_save_error).__name__}: {str(db_save_error)}", exc_info=True)
                            
                            # Save profile to vector store
                            profile_id = await self.contextual_graph_storage.save_control_profile(profile)
                            profile_ids.append(profile_id)
                            
                            # Update vector_doc_id in PostgreSQL if control was saved
                            if self._db_client_initialized and self.control_service and profile.control_id:
                                try:
                                    await self.control_service.update_vector_doc_id(profile.control_id, profile.profile_id)
                                    logger.debug(f"  Updated vector_doc_id for control {profile.control_id}")
                                except Exception as update_error:
                                    logger.debug(f"  Could not update vector_doc_id for control {profile.control_id}: {update_error}")
                        except Exception as profile_error:
                            logger.warning(f"  Error processing profile {profile.profile_id}: {profile_error}")
                    
                    logger.info(f"  ✓ Ingested {len(profile_ids)} control context profiles to contextual graph")
                    logger.info(f"    - Vector store: {len(profile_ids)} profiles")
                    if controls_saved_to_db > 0:
                        logger.info(f"    - PostgreSQL: {controls_saved_to_db} controls")
                    
                    results["contextual_graph"]["profiles"] = {
                        "success": True,
                        "count": len(profile_ids),
                        "storage": "vector_store",
                        "controls_saved_to_db": controls_saved_to_db if self._db_client_initialized else 0
                    }
            except Exception as e:
                logger.error(f"  ✗ Error ingesting contextual graph data: {e}")
                results["contextual_graph"]["error"] = str(e)
        
        # Ingest to stores using fixed store names from mappings
        # Use collection factory to verify collections exist, then use indexing_service.stores to add documents
        for store_name, docs in routed_docs.items():
            # Verify store exists in collection factory (using fixed store names)
            collection_exists = False
            if self.collection_factory:
                collection_service = self.collection_factory.get_collection_by_store_name(store_name)
                if collection_service:
                    collection_exists = True
                    logger.debug(f"  Store '{store_name}' found in collection factory")
            
            # Use indexing_service.stores to add documents (it has DocumentChromaStore with add_documents method)
            if store_name not in self.indexing_service.stores:
                if not collection_exists:
                    logger.warning(f"  Store '{store_name}' not available in collection factory or indexing service, skipping {len(docs)} documents")
                    results["stores"][store_name] = {
                        "error": "Store not available",
                        "count": len(docs)
                    }
                    continue
                else:
                    logger.warning(f"  Store '{store_name}' found in collection factory but not in indexing_service.stores, skipping {len(docs)} documents")
                    results["stores"][store_name] = {
                        "error": "Store not initialized in indexing service",
                        "count": len(docs)
                    }
                    continue
            
            try:
                store = self.indexing_service.stores[store_name]
                batch_size = getattr(self, "document_batch_size", 200)
                result_ids = []
                for start in range(0, len(docs), batch_size):
                    batch = docs[start : start + batch_size]
                    result_ids.extend(store.add_documents(batch))
                logger.info(f"  ✓ Ingested {len(docs)} documents to {store_name} (vector store)")
                
                # Save documents to PostgreSQL document_kg_insights table
                docs_saved_to_postgres = 0
                
                # Initialize database pool lazily if not already initialized
                if not hasattr(self, '_db_pool_initialized') or not self._db_pool_initialized:
                    try:
                        self.db_pool = await get_database_pool()
                        self._db_pool_initialized = True
                        logger.info("  ✓ Initialized database pool for PostgreSQL document storage")
                    except Exception as db_pool_error:
                        logger.warning(f"  Could not initialize database pool: {db_pool_error}. Document insights will not be saved to PostgreSQL.")
                        logger.debug(f"  Database pool error details: {type(db_pool_error).__name__}: {str(db_pool_error)}", exc_info=True)
                        self.db_pool = None
                
                if self.db_pool:
                    try:
                        # Prepare batch of document insights
                        doc_insights = []
                        for doc in docs:
                            doc_id = doc.metadata.get("id") or doc.metadata.get("document_id") or str(uuid4())
                            
                            # For split files, use extraction_type from document metadata if available
                            # Otherwise, determine from store_name and content_type
                            if doc.metadata.get("extraction_type"):
                                extraction_type = doc.metadata.get("extraction_type")
                            else:
                                extraction_type = self._get_extraction_type_for_store(store_name, actual_content_type)
                            
                            doc_insights.append({
                                "doc_id": doc_id,
                                "document_content": doc.page_content,
                                "extraction_type": extraction_type,
                                "extracted_data": {"store_name": store_name, "content_type": actual_content_type},
                                "context_id": doc.metadata.get("context_id"),
                                "extraction_metadata": doc.metadata
                            })
                        
                        # Save batch to PostgreSQL (split into chunks if needed)
                        if doc_insights:
                            total_saved = 0
                            # Process in batches to avoid memory issues with very large document sets
                            for i in range(0, len(doc_insights), self.postgres_batch_size):
                                batch = doc_insights[i:i + self.postgres_batch_size]
                                batch_saved = await self._save_doc_insights_batch_to_postgres(batch)
                                total_saved += batch_saved
                            
                            if total_saved > 0:
                                logger.info(f"  ✓ Saved {total_saved} documents to PostgreSQL (document_kg_insights) in batch")
                            docs_saved_to_postgres = total_saved
                    except Exception as postgres_error:
                        logger.warning(f"  Could not save documents to PostgreSQL: {postgres_error}")
                        logger.debug(f"  PostgreSQL error details: {type(postgres_error).__name__}: {str(postgres_error)}", exc_info=True)
                
                results["stores"][store_name] = {
                    "success": True,
                    "count": len(docs),
                    "result": result_ids,
                    "postgres_count": docs_saved_to_postgres if self.db_pool else 0
                }
            except Exception as e:
                error_msg = str(e)
                # Check if it's a dimension mismatch error
                if "dimension" in error_msg.lower() or "dimensionality" in error_msg.lower():
                    logger.warning(f"  Dimension mismatch detected for {store_name}: {error_msg}")
                    logger.info(f"  Attempting to recreate collection and retry...")
                    
                    # Try to recreate the collection
                    if self.vector_store_type == "chroma":
                        try:
                            collection_name = self._get_collection_name(store_name)
                            persistent_client = self.indexing_service.persistent_client
                            
                            # Delete the collection
                            try:
                                persistent_client.delete_collection(name=collection_name)
                                logger.info(f"  Deleted collection: {collection_name}")
                            except Exception as del_error:
                                logger.warning(f"  Could not delete collection: {del_error}")
                            
                            # Reinitialize the store (which will recreate the collection)
                            # We need to reinitialize the store in the indexing service
                            # For now, log and suggest using --force-recreate
                            logger.error(f"  ✗ Dimension mismatch. Please run with --force-recreate to fix this.")
                            logger.error(f"  Or manually delete the collection: {collection_name}")
                            results["stores"][store_name] = {
                                "success": False,
                                "error": f"Dimension mismatch: {error_msg}. Use --force-recreate to fix.",
                                "count": len(docs)
                            }
                        except Exception as recreate_error:
                            logger.error(f"  ✗ Error recreating collection: {recreate_error}")
                            results["stores"][store_name] = {
                                "success": False,
                                "error": f"Dimension mismatch and recreation failed: {recreate_error}",
                                "count": len(docs)
                            }
                    else:
                        results["stores"][store_name] = {
                            "success": False,
                            "error": f"Dimension mismatch: {error_msg}",
                            "count": len(docs)
                        }
                else:
                    logger.error(f"  ✗ Error ingesting to {store_name}: {e}")
                    results["stores"][store_name] = {
                        "success": False,
                        "error": str(e),
                        "count": len(docs)
                    }
        
        return results
    
    async def ingest_all(
        self,
        content_types: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Ingest all preview files into ChromaDB stores.
        
        Args:
            content_types: Optional list of content types to ingest (None = all)
            dry_run: If True, only show what would be ingested without actually ingesting
            
        Returns:
            Dictionary with overall ingestion results
        """
        logger.info("=" * 80)
        logger.info("Preview File Ingestion")
        logger.info("=" * 80)
        if len(self.preview_dirs) > 1:
            logger.info(f"Preview Directories ({len(self.preview_dirs)}): {[str(d) for d in self.preview_dirs]}")
        else:
            logger.info(f"Preview Directory: {self.preview_dir}")
        logger.info(f"Collection Prefix: {self.collection_prefix}")
        logger.info(f"Vector Store: {self.vector_store_type}")
        logger.info(f"Skip Contextual Graph: {self.skip_contextual_graph}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info("")
        
        all_results = []
        total_documents = 0
        total_by_store = defaultdict(int)
        total_contextual_graph = {"contexts": 0, "edges": 0, "profiles": 0}
        
        # Discover files (preview dir layout: content_type/*.json)
        files_by_type = self.discover_preview_files(content_types)

        # kb-dump-utility enriched: preview_dir/<enriched_subdirs>/*.json (e.g. enriched + enriched_vendor)
        enriched_by_store = self.discover_enriched_files(enriched_subdirs=self.enriched_subdirs)
        if enriched_by_store:
            logger.info("")
            logger.info("Ingesting enriched documents from %s", self.enriched_subdirs or ["enriched"])
            enriched_result = await self.ingest_enriched_documents(enriched_by_store, dry_run=dry_run)
            for sn, count in enriched_result.get("stores", {}).items():
                total_by_store[sn] = total_by_store.get(sn, 0) + count
            all_results.extend(enriched_result.get("results", []))
            total_documents += enriched_result.get("total_documents", 0)
        
        if not files_by_type and not enriched_by_store:
            logger.warning("No preview files or enriched documents found to ingest")
            return {
                "success": False,
                "error": "No preview files found",
                "files_processed": 0
            }
        
        # Process each preview file
        for content_type, file_paths in files_by_type.items():
            logger.info(f"\n{'='*80}")
            logger.info(f"Processing {content_type} ({len(file_paths)} files)")
            logger.info(f"{'='*80}")
            
            for file_path in file_paths:
                result = await self.ingest_file(file_path, content_type, dry_run=dry_run)
                all_results.append(result)
                total_documents += result["total_documents"]
                
                # Aggregate by store
                for store_name, store_result in result["stores"].items():
                    if store_result.get("success") or store_result.get("dry_run"):
                        total_by_store[store_name] += store_result.get("count", 0)
                
                # Aggregate contextual graph data
                if "contextual_graph" in result:
                    cg_data = result["contextual_graph"]
                    if isinstance(cg_data.get("contexts"), dict):
                        total_contextual_graph["contexts"] += cg_data["contexts"].get("count", 0)
                    elif isinstance(cg_data.get("contexts"), int):
                        total_contextual_graph["contexts"] += cg_data["contexts"]
                    if isinstance(cg_data.get("edges"), dict):
                        total_contextual_graph["edges"] += cg_data["edges"].get("count", 0)
                    elif isinstance(cg_data.get("edges"), int):
                        total_contextual_graph["edges"] += cg_data["edges"]
                    if isinstance(cg_data.get("profiles"), dict):
                        total_contextual_graph["profiles"] += cg_data["profiles"].get("count", 0)
                    elif isinstance(cg_data.get("profiles"), int):
                        total_contextual_graph["profiles"] += cg_data["profiles"]
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("Ingestion Summary")
        logger.info("=" * 80)
        logger.info(f"Files Processed: {len(all_results)}")
        logger.info(f"Total Documents: {total_documents}")
        logger.info(f"Documents by Store:")
        for store_name, count in sorted(total_by_store.items()):
            collection_name = self._get_collection_name(store_name)
            logger.info(f"  {store_name} → Collection: '{collection_name}': {count} documents")
        
        # Contextual graph summary
        if any(total_contextual_graph.values()):
            logger.info(f"Contextual Graph Data:")
            if total_contextual_graph["contexts"] > 0:
                if self.collection_prefix:
                    collection_name = f"{self.collection_prefix}_context_definitions"
                else:
                    collection_name = "context_definitions"
                collection_name = sanitize_collection_name(collection_name)
                logger.info(f"  Context Definitions → Collection: '{collection_name}': {total_contextual_graph['contexts']} documents")
            if total_contextual_graph["edges"] > 0:
                if self.collection_prefix:
                    collection_name = f"{self.collection_prefix}_contextual_edges"
                else:
                    collection_name = "contextual_edges"
                collection_name = sanitize_collection_name(collection_name)
                logger.info(f"  Contextual Edges → Collection: '{collection_name}': {total_contextual_graph['edges']} documents")
            if total_contextual_graph["profiles"] > 0:
                if self.collection_prefix:
                    collection_name = f"{self.collection_prefix}_control_context_profiles"
                else:
                    collection_name = "control_context_profiles"
                collection_name = sanitize_collection_name(collection_name)
                logger.info(f"  Control Context Profiles → Collection: '{collection_name}': {total_contextual_graph['profiles']} documents")
        
        logger.info("=" * 80)
        
        # Verify collections have data
        if not dry_run and self.vector_store_type == "chroma":
            logger.info("")
            logger.info("Verifying collections have data...")
            try:
                persistent_client = self.indexing_service.persistent_client
                
                # Verify regular stores
                for store_name in sorted(total_by_store.keys()):
                    collection_name = self._get_collection_name(store_name)
                    try:
                        collection = persistent_client.get_collection(collection_name)
                        count = collection.count()
                        status = "✓" if count > 0 else "✗ (empty)"
                        logger.info(f"  {status} Collection '{collection_name}': {count} documents")
                    except Exception as e:
                        logger.warning(f"  ✗ Collection '{collection_name}': {str(e)}")
                
                # Verify contextual graph collections
                if any(total_contextual_graph.values()):
                    contextual_collections = [
                        ("context_definitions", total_contextual_graph["contexts"]),
                        ("contextual_edges", total_contextual_graph["edges"]),
                        ("control_context_profiles", total_contextual_graph["profiles"])
                    ]
                    for collection_base, expected_count in contextual_collections:
                        if expected_count > 0:
                            if self.collection_prefix:
                                collection_name = f"{self.collection_prefix}_{collection_base}"
                            else:
                                collection_name = collection_base
                            collection_name = sanitize_collection_name(collection_name)
                            try:
                                collection = persistent_client.get_collection(collection_name)
                                count = collection.count()
                                status = "✓" if count > 0 else "✗ (empty)"
                                logger.info(f"  {status} Collection '{collection_name}': {count} documents")
                            except Exception as e:
                                logger.warning(f"  ✗ Collection '{collection_name}': {str(e)}")
            except Exception as e:
                logger.warning(f"Could not verify collections: {str(e)}")
            logger.info("=" * 80)
        
        return {
            "success": True,
            "files_processed": len(all_results),
            "total_documents": total_documents,
            "documents_by_store": dict(total_by_store),
            "contextual_graph": total_contextual_graph,
            "results": all_results,
            "dry_run": dry_run
        }
    
    async def reindex_contextual_graph(
        self,
        content_types: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Reindex only contextual graph data from preview files.
        
        This method:
        1. Finds all preview files that might contain contextual graph data
        2. Extracts contextual graph data (contexts, edges, profiles)
        3. Saves them to both vector store and PostgreSQL
        
        Args:
            content_types: Optional list of content types to reindex (default: all contextual graph types)
            dry_run: If True, only show what would be reindexed without actually reindexing
            
        Returns:
            Dictionary with reindexing results
        """
        logger.info("=" * 80)
        logger.info("Reindexing Contextual Graph Data")
        logger.info("=" * 80)
        
        if not self.contextual_graph_storage:
            logger.error("Contextual graph storage not initialized. Cannot reindex.")
            return {
                "success": False,
                "error": "Contextual graph storage not initialized"
            }
        
        # Default content types that might contain contextual graph data
        if content_types is None:
            content_types = [
                "context_definitions",
                "contextual_edges",
                "control_context_profiles",
                "compliance_controls",
                "risk_controls",
                "riskmanagement_risk_controls",
                "policy_documents",
                "domain_knowledge"
            ]
        
        # Discover preview files for these content types
        preview_files = self.discover_preview_files(content_types=content_types)
        
        total_contexts = 0
        total_edges = 0
        total_profiles = 0
        files_processed = 0
        
        results = []
        
        for content_type, file_paths in preview_files.items():
            if not file_paths:
                continue
            
            logger.info(f"\nProcessing {len(file_paths)} files for content_type: {content_type}")
            
            for file_path in file_paths:
                try:
                    # Load file (skip invalid/empty JSON)
                    file_data = self.load_preview_file(file_path)
                    if file_data is None:
                        continue
                    documents = self.convert_to_documents(file_data)
                    
                    # Extract contextual graph data
                    contextual_graph_data = self.extract_contextual_graph_data(
                        documents,
                        content_type
                    )
                    
                    if not any([contextual_graph_data["contexts"], 
                               contextual_graph_data["edges"], 
                               contextual_graph_data["profiles"]]):
                        continue
                    
                    files_processed += 1
                    
                    if dry_run:
                        logger.info(f"  [DRY RUN] Would reindex from {file_path.name}:")
                        if contextual_graph_data["contexts"]:
                            logger.info(f"    - {len(contextual_graph_data['contexts'])} contexts")
                        if contextual_graph_data["edges"]:
                            logger.info(f"    - {len(contextual_graph_data['edges'])} edges")
                        if contextual_graph_data["profiles"]:
                            logger.info(f"    - {len(contextual_graph_data['profiles'])} profiles")
                        continue
                    
                    # Initialize database pool if needed
                    if not hasattr(self, '_db_pool_initialized') or not self._db_pool_initialized:
                        try:
                            self.db_pool = await get_database_pool()
                            self._db_pool_initialized = True
                            logger.info("  ✓ Initialized database pool for PostgreSQL")
                        except Exception as db_pool_error:
                            logger.warning(f"  Could not initialize database pool: {db_pool_error}")
                            self.db_pool = None
                    
                    # Save contexts
                    if contextual_graph_data["contexts"]:
                        context_ids = await self.contextual_graph_storage.save_context_definitions(
                            contextual_graph_data["contexts"]
                        )
                        total_contexts += len(context_ids)
                        logger.info(f"  ✓ Reindexed {len(context_ids)} contexts from {file_path.name}")
                    
                    # Save edges (with batching for performance)
                    if contextual_graph_data["edges"]:
                        edge_ids = await self.contextual_graph_storage.save_contextual_edges(
                            contextual_graph_data["edges"],
                            batch_size=self.edge_batch_size
                        )
                        total_edges += len(edge_ids)
                        
                        # Also save to PostgreSQL (with batching for performance)
                        edges_saved_to_postgres = 0
                        if self.db_pool:
                            try:
                                edges_saved_to_postgres = await self.contextual_graph_storage.save_edges_to_postgres(
                                    contextual_graph_data["edges"],
                                    db_pool=self.db_pool,
                                    batch_size=self.edge_postgres_batch_size
                                )
                            except Exception as e:
                                logger.warning(f"  Could not save edges to PostgreSQL: {e}")
                        
                        logger.info(f"  ✓ Reindexed {len(edge_ids)} edges from {file_path.name} (PostgreSQL: {edges_saved_to_postgres})")
                    
                    # Save profiles
                    if contextual_graph_data["profiles"]:
                        profile_ids = []
                        for profile in contextual_graph_data["profiles"]:
                            profile_id = await self.contextual_graph_storage.save_control_profile(profile)
                            profile_ids.append(profile_id)
                        total_profiles += len(profile_ids)
                        logger.info(f"  ✓ Reindexed {len(profile_ids)} profiles from {file_path.name}")
                    
                    results.append({
                        "file_path": str(file_path),
                        "content_type": content_type,
                        "contexts": len(contextual_graph_data["contexts"]),
                        "edges": len(contextual_graph_data["edges"]),
                        "profiles": len(contextual_graph_data["profiles"])
                    })
                    
                except Exception as e:
                    logger.error(f"  ✗ Error processing {file_path.name}: {e}")
                    logger.debug(f"  Error details: {type(e).__name__}: {str(e)}", exc_info=True)
        
        logger.info("=" * 80)
        logger.info("Reindexing Summary")
        logger.info("=" * 80)
        logger.info(f"Files processed: {files_processed}")
        logger.info(f"Contexts reindexed: {total_contexts}")
        logger.info(f"Edges reindexed: {total_edges}")
        logger.info(f"Profiles reindexed: {total_profiles}")
        logger.info("=" * 80)
        
        return {
            "success": True,
            "files_processed": files_processed,
            "contexts_reindexed": total_contexts,
            "edges_reindexed": total_edges,
            "profiles_reindexed": total_profiles,
            "results": results,
            "dry_run": dry_run
        }


async def main_async():
    """Async CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest preview files into ChromaDB stores without re-running pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--preview-dir",
        type=str,
        nargs="+",
        default=["indexing_preview"],
        metavar="DIR",
        help="One or more directories containing preview files. When multiple dirs are given, content is merged: use Snyk schema (flowharmonicai/knowledge/indexing_preview) + product KB (kb-dump-utility/preview_product_kb) so column_definitions and contextual_edges are ingested together. Default: indexing_preview"
    )
    
    parser.add_argument(
        "--collection-prefix",
        type=str,
        default="",  # Empty prefix by default to match project_reader.py collections
        help="Prefix for ChromaDB collections (default: '' for unprefixed collections to match project_reader.py). Schema collections (table_definitions, table_descriptions, column_definitions, schema_descriptions, db_schema, column_metadata) are always unprefixed regardless of this setting."
    )
    
    parser.add_argument(
        "--vector-store",
        type=str,
        choices=["chroma", "qdrant"],
        default="chroma",
        help="Vector store type (default: chroma)"
    )
    
    parser.add_argument(
        "--content-types",
        type=str,
        nargs="+",
        help="Specific content types to ingest (default: all)"
    )
    parser.add_argument(
        "--policy-preview-only",
        action="store_true",
        help="Ingest only policy preview content (policy_controls, policy_risks, policy_key_concepts, policy_identifiers, policy_framework_docs, policy_edges) into _new collections. Use with --preview-dir pointing to kb-dump-utility/preview_policy."
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode: show what would be ingested without actually ingesting"
    )
    
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Force recreate collections: delete and recreate all collections before ingesting (fixes dimension mismatches)"
    )
    
    parser.add_argument(
        "--postgres-batch-size",
        type=int,
        default=1000,
        help="Batch size for PostgreSQL inserts (default: 1000). Larger batches are faster but use more memory."
    )
    parser.add_argument(
        "--edge-batch-size",
        type=int,
        default=500,
        help="Batch size for contextual edge vector store inserts (default: 500). Larger batches are faster but use more memory."
    )
    parser.add_argument(
        "--edge-postgres-batch-size",
        type=int,
        default=1000,
        help="Batch size for contextual edge PostgreSQL inserts (default: 1000). Larger batches are faster but use more memory."
    )
    
    parser.add_argument(
        "--skip-contextual-graph",
        action="store_true",
        help="Skip contextual graph extraction and ingestion. Only ingest to vector stores, not contextual graph."
    )
    parser.add_argument(
        "--enriched-subdirs",
        type=str,
        nargs="+",
        metavar="SUBDIR",
        help="Enriched subdirs under preview-dir to merge (e.g. enriched enriched_vendor). Default: enriched only.",
    )
    parser.add_argument(
        "--document-batch-size",
        type=int,
        default=200,
        help="Batch size for embedding and upserting documents to vector store (default: 200). Larger batches are faster but use more memory and API calls.",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to checkpoint JSON. When set, progress is saved after each batch and ingest resumes from this file on restart. Safe for background runs.",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Delete checkpoint file before starting (fresh run). Use with --checkpoint-file to then create a new checkpoint.",
    )
    parser.add_argument(
        "--reindex-contextual-graph",
        action="store_true",
        help="Reindex only contextual graph data from preview files. This will extract and save contexts, edges, and profiles to both vector store and PostgreSQL."
    )
    
    args = parser.parse_args()
    
    # Normalize preview_dir to list (CLI may pass one or more)
    preview_dirs = getattr(args, "preview_dir", None)
    if isinstance(preview_dirs, str):
        preview_dirs = [preview_dirs]
    if not preview_dirs:
        preview_dirs = ["indexing_preview"]

    # Restrict to policy preview content types when requested
    content_types = getattr(args, "content_types", None)
    if getattr(args, "policy_preview_only", False):
        content_types = list(PreviewFileIngester.POLICY_PREVIEW_CONTENT_TYPES)
        logger.info("Policy preview only: restricting to content types %s", content_types)
        if preview_dirs == ["indexing_preview"]:
            logger.warning("Using default preview dir 'indexing_preview'. Pass --preview-dir /path/to/kb-dump-utility/preview_policy to ingest from policy preview.")

    # Create ingester (multiple preview dirs merge schema + product KB + policies)
    ingester = PreviewFileIngester(
        preview_dir=preview_dirs[0],
        preview_dirs=preview_dirs if len(preview_dirs) > 1 else None,
        collection_prefix=args.collection_prefix,
        vector_store_type=args.vector_store,
        force_recreate=args.force_recreate,
        postgres_batch_size=args.postgres_batch_size,
        skip_contextual_graph=args.skip_contextual_graph,
        edge_batch_size=getattr(args, 'edge_batch_size', 500),
        edge_postgres_batch_size=getattr(args, 'edge_postgres_batch_size', 1000),
        enriched_subdirs=getattr(args, 'enriched_subdirs', None),
        document_batch_size=getattr(args, 'document_batch_size', 200),
        checkpoint_file=getattr(args, 'checkpoint_file', None),
        clear_checkpoint=getattr(args, 'clear_checkpoint', False),
    )
    
    # Run ingestion or reindex
    if args.reindex_contextual_graph:
        # Reindex only contextual graph data
        if args.dry_run:
            logger.info("Running in DRY RUN mode - no data will be reindexed")
        
        result = await ingester.reindex_contextual_graph(
            content_types=content_types,
            dry_run=args.dry_run
        )
    else:
        # Normal ingestion
        if args.dry_run:
            logger.info("Running in DRY RUN mode - no data will be ingested")
        result = await ingester.ingest_all(
            content_types=content_types,
            dry_run=args.dry_run
        )
    
    if result["success"]:
        logger.info("\n✓ Ingestion completed successfully")
        return 0
    else:
        logger.error(f"\n✗ Ingestion failed: {result.get('error', 'Unknown error')}")
        return 1


def main():
    """CLI entry point wrapper."""
    import asyncio
    return asyncio.run(main_async())


if __name__ == "__main__":
    import sys
    sys.exit(main())

