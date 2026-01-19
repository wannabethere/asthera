"""
CLI utility to ingest MDL definitions into contextual graph.

This script processes MDL (Model Definition Language) files and creates contextual graph
entities from table definitions. For each table entity, it analyzes:
- Which compliance frameworks it can help with (SOC2, HIPAA, etc.)
- Specific controls necessary
- Key concepts
- Extracts fields (columns) with key definitions

It then creates contextual graph nodes (entities as contexts), edges to compliance
controls if they exist, and saves fields to the fields collection.

Usage:
    # Ingest MDL file to contextual graph
    python -m app.indexing.cli.ingest_mdl_contextual_graph \
        --mdl-file path/to/snyk_mdl1.json \
        --product-name Snyk

    # Dry run (show what would be ingested)
    python -m app.indexing.cli.ingest_mdl_contextual_graph \
        --mdl-file path/to/snyk_mdl1.json \
        --product-name Snyk \
        --dry-run
"""
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.dependencies import (
    get_chromadb_client,
    get_embeddings_model,
    get_llm,
    get_database_pool,
    get_database_client
)
from app.storage.vector_store import ChromaVectorStoreClient
from app.services.contextual_graph_storage import (
    ContextualGraphStorage,
    ContextDefinition,
    ContextualEdge,
)
from app.storage.query.collection_factory import CollectionFactory
from app.services.storage.control_service import ControlStorageService
from app.agents.extractors import FieldsExtractor
from langchain_core.documents import Document

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MDLContextualGraphIngester:
    """Ingests MDL definitions into contextual graph as entities."""
    
    def __init__(
        self,
        collection_prefix: str = "",
        vector_store_type: str = "chroma",
        llm_temperature: float = 0.2
    ):
        """
        Initialize the MDL contextual graph ingester.
        
        Args:
            collection_prefix: Prefix for ChromaDB collections (default: "" for no prefix)
            vector_store_type: Vector store type ("chroma" or "qdrant")
            llm_temperature: Temperature for LLM calls
        """
        # Always use empty prefix to match collection_factory.py collections without prefixes
        self.collection_prefix = ""
        self.vector_store_type = vector_store_type
        
        # Initialize dependencies
        persistent_client = get_chromadb_client() if vector_store_type == "chroma" else None
        embeddings = get_embeddings_model()
        llm = get_llm(temperature=llm_temperature)
        
        self.llm = llm
        self.embeddings = embeddings
        
        # Initialize contextual graph storage
        if vector_store_type == "chroma" and persistent_client:
            try:
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
                vector_store_client._client = persistent_client
                
                # Initialize collection factory for searching compliance controls
                # Use empty prefix to match collection_factory.py collections (no prefixes)
                self.collection_factory = CollectionFactory(
                    vector_store_client=vector_store_client,
                    embeddings_model=embeddings,
                    collection_prefix=""  # No prefix - use collections as defined in collection_factory.py
                )
                
                self.contextual_graph_storage = ContextualGraphStorage(
                    vector_store_client=vector_store_client,
                    embeddings_model=embeddings,
                    collection_prefix="",  # No prefix - use collections as defined in collection_factory.py
                    collection_factory=self.collection_factory
                )
                logger.info(f"Initialized ContextualGraphStorage without collection prefix (using collection_factory.py collections)")
            except Exception as e:
                logger.warning(f"Could not initialize ContextualGraphStorage: {e}")
                self.contextual_graph_storage = None
                self.collection_factory = None
        else:
            self.contextual_graph_storage = None
            self.collection_factory = None
        
        # Initialize JSON parser for LLM responses
        self.json_parser = JsonOutputParser()
        
        # Initialize FieldsExtractor for extracting table fields
        self.fields_extractor = FieldsExtractor(
            llm=llm,
            model_name=getattr(llm, "model_name", "gpt-4o")
        )
        
        # Database connections (lazy initialization)
        self.db_pool = None
        self.db_client = None
        self.control_service = None
        self._db_pool_initialized = False
        self._db_client_initialized = False
        
        logger.info(f"MDLContextualGraphIngester initialized without collection prefix (using collection_factory.py collections)")
    
    def load_mdl_file(self, mdl_file_path: Path) -> Dict[str, Any]:
        """
        Load MDL file.
        
        Args:
            mdl_file_path: Path to MDL JSON file
            
        Returns:
            MDL dictionary
        """
        try:
            with open(mdl_file_path, "r", encoding="utf-8") as f:
                mdl_data = json.load(f)
            return mdl_data
        except Exception as e:
            logger.error(f"Error loading MDL file {mdl_file_path}: {e}")
            raise
    
    def combine_table_mdl(self, model: Dict[str, Any], mdl_dict: Dict[str, Any]) -> str:
        """
        Combine a table's MDL definition into a single comprehensive representation.
        
        Args:
            model: Model/table dictionary from MDL
            mdl_dict: Full MDL dictionary for context
            
        Returns:
            Combined MDL representation as JSON string
        """
        table_mdl = {
            "table_name": model.get("name", ""),
            "schema": mdl_dict.get("schema", "public"),
            "catalog": mdl_dict.get("catalog", ""),
            "description": model.get("description", ""),
            "columns": model.get("columns", []),
            "properties": model.get("properties", {}),
            "table_type": model.get("table_type"),
            "primary_key": model.get("primaryKey"),
            "ref_sql": model.get("refSql"),
            "base_object": model.get("baseObject"),
            "table_reference": model.get("tableReference"),
            "cached": model.get("cached"),
            "refresh_time": model.get("refreshTime"),
        }
        
        return json.dumps(table_mdl, indent=2)
    
    async def analyze_entity_compliance(
        self,
        table_name: str,
        table_mdl: str,
        product_name: str
    ) -> Dict[str, Any]:
        """
        Analyze an entity (table) for compliance frameworks, controls, and key concepts.
        
        Uses a single prompt to fetch all information:
        - Compliance frameworks it can help with
        - Specific controls necessary
        - Key concepts
        
        Args:
            table_name: Name of the table
            table_mdl: Combined MDL representation of the table
            product_name: Product name for context
            
        Returns:
            Dictionary with compliance_frameworks, controls, and key_concepts
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert compliance analyst specializing in data governance and regulatory frameworks.

Analyze the provided table/entity definition and determine:
1. Which compliance frameworks this entity can help with (e.g., SOC2, HIPAA, GDPR, PCI-DSS, ISO27001, etc.)
2. Specific controls from those frameworks that are relevant or necessary
3. Key concepts and business terms related to this entity

For each compliance framework identified, provide:
- Framework name (e.g., "SOC2", "HIPAA", "GDPR")
- Relevance score (0.0-1.0) indicating how relevant this entity is to the framework
- Specific control IDs or names that are relevant (if known)
- Brief explanation of why this entity is relevant

Return a JSON object with the following structure:
{{
    "compliance_frameworks": [
        {{
            "framework": "SOC2",
            "relevance_score": 0.85,
            "relevant_controls": ["CC6.1", "CC6.2", "CC7.1"],
            "explanation": "This table stores access logs which are critical for SOC2 access control requirements"
        }}
    ],
    "controls": [
        {{
            "control_id": "CC6.1",
            "control_name": "Logical Access Controls",
            "framework": "SOC2",
            "description": "The entity implements logical access security software, infrastructure, and procedures to protect against unauthorized access"
        }}
    ],
    "key_concepts": [
        "Access Control",
        "Authentication",
        "User Management",
        "Security Logging"
    ]
}}

If you cannot identify specific control IDs, provide descriptive control names based on the framework's requirements."""),
            ("human", """Analyze this table entity for compliance:

Table Name: {table_name}
Product: {product_name}

Table MDL Definition:
{table_mdl}

Provide compliance analysis as JSON.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            result = await chain.ainvoke({
                "table_name": table_name,
                "product_name": product_name,
                "table_mdl": table_mdl
            })
            
            # Ensure result has expected structure
            if not isinstance(result, dict):
                logger.warning(f"Unexpected result type from LLM: {type(result)}")
                return {
                    "compliance_frameworks": [],
                    "controls": [],
                    "key_concepts": []
                }
            
            # Normalize structure
            return {
                "compliance_frameworks": result.get("compliance_frameworks", []),
                "controls": result.get("controls", []),
                "key_concepts": result.get("key_concepts", [])
            }
        except Exception as e:
            logger.error(f"Error analyzing entity compliance for {table_name}: {e}")
            logger.debug(f"  Error details: {type(e).__name__}: {str(e)}", exc_info=True)
            return {
                "compliance_frameworks": [],
                "controls": [],
                "key_concepts": []
            }
    
    async def search_compliance_controls(
        self,
        framework: str,
        control_id: Optional[str] = None,
        control_name: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for compliance controls in the vector store.
        
        Args:
            framework: Framework name (e.g., "SOC2", "HIPAA")
            control_id: Optional control ID to search for
            control_name: Optional control name to search for
            top_k: Number of results to return
            
        Returns:
            List of control documents found
        """
        if not self.collection_factory:
            return []
        
        try:
            # Search in compliance_controls collection
            compliance_collection = self.collection_factory.get_collection_by_store_name("compliance_controls")
            if not compliance_collection:
                return []
            
            # Build query
            query = ""
            if control_id:
                query = f"{framework} {control_id}"
            elif control_name:
                query = f"{framework} {control_name}"
            else:
                query = framework
            
            # Build filters
            filters = {"framework": framework} if framework else {}
            
            # Search using hybrid_search
            results = await compliance_collection.hybrid_search(
                query=query,
                top_k=top_k,
                where=filters
            )
            
            return results if results else []
        except Exception as e:
            logger.debug(f"Error searching compliance controls: {e}")
            return []
    
    async def create_entity_context(
        self,
        table_name: str,
        table_mdl: str,
        compliance_analysis: Dict[str, Any],
        product_name: str,
        domain: Optional[str] = None
    ) -> ContextDefinition:
        """
        Create a context definition for a table entity.
        
        Args:
            table_name: Name of the table
            table_mdl: Combined MDL representation
            compliance_analysis: Results from analyze_entity_compliance
            product_name: Product name
            domain: Optional domain
            
        Returns:
            ContextDefinition for the entity
        """
        # Extract frameworks
        frameworks = [f.get("framework", "") for f in compliance_analysis.get("compliance_frameworks", [])]
        frameworks = [f for f in frameworks if f]  # Remove empty strings
        
        # Build document description
        document_parts = [
            f"Entity: {table_name}",
            f"Product: {product_name}",
            "",
            "MDL Definition:",
            table_mdl,
            "",
            "Compliance Analysis:",
        ]
        
        if compliance_analysis.get("compliance_frameworks"):
            document_parts.append("Relevant Compliance Frameworks:")
            for framework_info in compliance_analysis["compliance_frameworks"]:
                framework = framework_info.get("framework", "")
                relevance = framework_info.get("relevance_score", 0.0)
                explanation = framework_info.get("explanation", "")
                document_parts.append(f"- {framework} (relevance: {relevance:.2f}): {explanation}")
        
        if compliance_analysis.get("controls"):
            document_parts.append("")
            document_parts.append("Relevant Controls:")
            for control in compliance_analysis["controls"]:
                control_id = control.get("control_id", "")
                control_name = control.get("control_name", "")
                framework = control.get("framework", "")
                description = control.get("description", "")
                document_parts.append(f"- {framework} {control_id}: {control_name}")
                if description:
                    document_parts.append(f"  {description}")
        
        if compliance_analysis.get("key_concepts"):
            document_parts.append("")
            document_parts.append("Key Concepts:")
            document_parts.append(", ".join(compliance_analysis["key_concepts"]))
        
        document = "\n".join(document_parts)
        
        # Create context ID
        context_id = f"entity_{product_name}_{table_name}".lower().replace(" ", "_")
        
        # Create context definition
        context = ContextDefinition(
            context_id=context_id,
            document=document,
            context_type="entity",
            regulatory_frameworks=frameworks,
            data_types=compliance_analysis.get("key_concepts", []),
            systems=[product_name] if product_name else [],
            created_at=datetime.utcnow().isoformat() + "Z",
            updated_at=datetime.utcnow().isoformat() + "Z"
        )
        
        return context
    
    async def create_control_edges(
        self,
        context_id: str,
        table_name: str,
        compliance_analysis: Dict[str, Any]
    ) -> List[ContextualEdge]:
        """
        Create edges from entity to compliance controls.
        
        Args:
            context_id: Entity context ID
            table_name: Table name
            compliance_analysis: Results from analyze_entity_compliance
            
        Returns:
            List of ContextualEdge objects
        """
        edges = []
        
        # Process each control from analysis
        for control_info in compliance_analysis.get("controls", []):
            framework = control_info.get("framework", "")
            control_id = control_info.get("control_id", "")
            control_name = control_info.get("control_name", "")
            
            if not framework or not control_id:
                continue
            
            # Search for existing controls in vector store
            existing_controls = await self.search_compliance_controls(
                framework=framework,
                control_id=control_id,
                control_name=control_name,
                top_k=1
            )
            
            # Determine target entity ID
            if existing_controls:
                # Use existing control ID from vector store
                # Results from hybrid_search have structure: {"id": ..., "document": ..., "metadata": ..., "score": ...}
                first_result = existing_controls[0]
                target_control_id = first_result.get("id") or first_result.get("metadata", {}).get("control_id", control_id)
            else:
                # Create a placeholder control ID (control doesn't exist yet)
                target_control_id = f"{framework}_{control_id}".lower().replace(" ", "_")
            
            # Create edge document
            edge_document = f"Entity '{table_name}' is relevant to {framework} control {control_id}: {control_name}"
            if control_info.get("description"):
                edge_document += f"\n\n{control_info.get('description')}"
            
            # Create edge
            edge = ContextualEdge(
                edge_id=f"edge_{context_id}_{target_control_id}",
                document=edge_document,
                source_entity_id=context_id,
                source_entity_type="entity",
                target_entity_id=target_control_id,
                target_entity_type="control",
                edge_type="RELEVANT_TO_CONTROL",
                context_id=context_id,
                relevance_score=1.0,  # High relevance since it was identified by analysis
                created_at=datetime.utcnow().isoformat() + "Z"
            )
            
            edges.append(edge)
        
        return edges
    
    async def _initialize_database_pool(self):
        """Initialize database pool lazily if not already initialized."""
        if not self._db_pool_initialized:
            try:
                self.db_pool = await get_database_pool()
                self._db_pool_initialized = True
                logger.info("  ✓ Initialized database pool for PostgreSQL document storage")
            except Exception as db_pool_error:
                logger.warning(f"  Could not initialize database pool: {db_pool_error}. Document insights will not be saved to PostgreSQL.")
                logger.debug(f"  Database pool error details: {type(db_pool_error).__name__}: {str(db_pool_error)}", exc_info=True)
                self.db_pool = None
    
    async def _initialize_database_client(self):
        """Initialize database client lazily if not already initialized."""
        if not self._db_client_initialized:
            try:
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
    
    async def _save_doc_insight_to_postgres(
        self,
        doc_id: str,
        document_content: str,
        extraction_type: str,
        extracted_data: Dict[str, Any],
        context_id: Optional[str] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save a document insight to PostgreSQL document_kg_insights table.
        
        Args:
            doc_id: Document ID (matches vector store document ID)
            document_content: Original document content
            extraction_type: Type of extraction (context, edge, etc.)
            extracted_data: Extracted data as dictionary
            context_id: Optional context ID
            extraction_metadata: Optional extraction metadata
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.db_pool:
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
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
                    doc_id,
                    document_content,
                    extraction_type,
                    json.dumps(extracted_data),
                    context_id,
                    json.dumps(extraction_metadata) if extraction_metadata else None
                )
                return True
        except Exception as e:
            logger.warning(f"Failed to save doc insight {doc_id} to PostgreSQL: {str(e)}")
            logger.debug(f"  PostgreSQL error details: {type(e).__name__}: {str(e)}", exc_info=True)
            return False
    
    async def extract_table_fields(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        context_id: str,
        product_name: str,
        domain: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Extract fields from table columns and save to fields collection.
        
        Args:
            table_name: Name of the table
            columns: List of column definitions from MDL
            context_id: Entity context ID
            product_name: Product name
            domain: Optional domain
            dry_run: If True, only extract without saving
            
        Returns:
            Dictionary with extracted_fields and edges
        """
        if not self.collection_factory:
            return {"extracted_fields": [], "edges": []}
        
        # Build field definitions from columns
        field_definitions = []
        for column in columns:
            column_name = column.get("name", "")
            column_type = column.get("type", "")
            column_description = column.get("description", "")
            
            if not column_name:
                continue
            
            field_definitions.append({
                "name": column_name,
                "description": f"Column '{column_name}' ({column_type})" + (f": {column_description}" if column_description else ""),
                "data_type": column_type
            })
        
        if not field_definitions:
            return {"extracted_fields": [], "edges": []}
        
        # Build text representation of table columns for extraction
        columns_text = json.dumps({
            "table_name": table_name,
            "columns": columns
        }, indent=2)
        
        # Extract fields using FieldsExtractor
        try:
            fields_result = await self.fields_extractor.extract_fields_and_create_edges(
                text=columns_text,
                context_id=context_id,
                source_entity_id=context_id,
                source_entity_type="entity",
                field_definitions=field_definitions,
                context_metadata={
                    "context_id": context_id,
                    "table_name": table_name,
                    "product_name": product_name,
                    "domain": domain,
                    "source": "mdl_contextual_graph"
                }
            )
            
            extracted_fields = fields_result.get("extracted_fields", [])
            edges = fields_result.get("edges", [])
            
            # Save fields to fields collection
            if not dry_run and extracted_fields:
                fields_collection = self.collection_factory.get_collection_by_store_name("fields")
                if fields_collection:
                    field_documents = []
                    field_metadatas = []
                    field_ids = []
                    
                    for field in extracted_fields:
                        field_name = field.get("field_name", "")
                        field_value = field.get("field_value", "")
                        field_id = f"{context_id}_{field_name}".lower().replace(" ", "_")
                        
                        # Create field document
                        field_doc = f"Field: {field_name}\nTable: {table_name}\nType: {field.get('data_type', 'unknown')}\nValue: {field_value}"
                        if field.get("description"):
                            field_doc += f"\nDescription: {field.get('description')}"
                        
                        field_documents.append(field_doc)
                        field_metadatas.append({
                            "type": "schema_field",  # Use metadata.type for filtering
                            "field_id": field_id,
                            "field_name": field_name,
                            "table_name": table_name,
                            "context_id": context_id,
                            "product_name": product_name,
                            "domain": domain or "",
                            "source": "mdl_contextual_graph"
                        })
                        field_ids.append(field_id)
                    
                    # Save to fields collection
                    await fields_collection.add_documents(
                        documents=field_documents,
                        metadatas=field_metadatas,
                        ids=field_ids
                    )
                    logger.info(f"  ✓ Saved {len(field_documents)} fields to fields collection")
            
            return {
                "extracted_fields": extracted_fields,
                "edges": edges
            }
        except Exception as e:
            logger.error(f"Error extracting fields for table {table_name}: {e}")
            logger.debug(f"  Error details: {type(e).__name__}: {str(e)}", exc_info=True)
            return {"extracted_fields": [], "edges": []}
    
    def _get_checkpoint_path(self, mdl_file_path: Path, product_name: str) -> Path:
        """
        Get checkpoint file path for this MDL file and product.
        
        Args:
            mdl_file_path: Path to MDL file
            product_name: Product name
            
        Returns:
            Path to checkpoint file
        """
        checkpoint_dir = Path(".checkpoints")
        checkpoint_dir.mkdir(exist_ok=True)
        
        # Create unique checkpoint filename based on MDL file and product
        mdl_stem = mdl_file_path.stem
        checkpoint_filename = f"mdl_ingest_{mdl_stem}_{product_name.lower().replace(' ', '_')}.json"
        return checkpoint_dir / checkpoint_filename
    
    def _load_checkpoint(self, checkpoint_path: Path) -> Dict[str, Any]:
        """
        Load checkpoint data if it exists.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            Dictionary with processed_tables (set of table names) and batch_number
        """
        if not checkpoint_path.exists():
            return {
                "processed_tables": set(),
                "last_batch": 0,
                "total_tables": 0
            }
        
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert list back to set
                return {
                    "processed_tables": set(data.get("processed_tables", [])),
                    "last_batch": data.get("last_batch", 0),
                    "total_tables": data.get("total_tables", 0)
                }
        except Exception as e:
            logger.warning(f"Error loading checkpoint: {e}. Starting fresh.")
            return {
                "processed_tables": set(),
                "last_batch": 0,
                "total_tables": 0
            }
    
    def _save_checkpoint(
        self,
        checkpoint_path: Path,
        processed_tables: set,
        batch_number: int,
        total_tables: int
    ):
        """
        Save checkpoint data.
        
        Args:
            checkpoint_path: Path to checkpoint file
            processed_tables: Set of processed table names
            batch_number: Current batch number
            total_tables: Total number of tables
        """
        try:
            # Convert set to list for JSON serialization
            data = {
                "processed_tables": list(processed_tables),
                "last_batch": batch_number,
                "total_tables": total_tables,
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Checkpoint saved: {len(processed_tables)}/{total_tables} tables processed (batch {batch_number})")
        except Exception as e:
            logger.warning(f"Error saving checkpoint: {e}")
    
    async def ingest_mdl_file(
        self,
        mdl_file_path: Path,
        product_name: str,
        domain: Optional[str] = None,
        dry_run: bool = False,
        resume: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest an MDL file into contextual graph.
        
        Args:
            mdl_file_path: Path to MDL JSON file
            product_name: Product name
            domain: Optional domain
            dry_run: If True, only show what would be ingested
            resume: If True, resume from checkpoint if available
            
        Returns:
            Dictionary with ingestion results
        """
        logger.info(f"Processing MDL file: {mdl_file_path.name}")
        
        if not self.contextual_graph_storage:
            logger.error("ContextualGraphStorage not initialized")
            return {
                "success": False,
                "error": "ContextualGraphStorage not initialized"
            }
        
        # Load MDL file
        mdl_dict = self.load_mdl_file(mdl_file_path)
        models = mdl_dict.get("models", [])
        
        logger.info(f"Found {len(models)} models/tables in MDL")
        
        # Load checkpoint if resuming
        checkpoint_path = self._get_checkpoint_path(mdl_file_path, product_name)
        processed_tables = set()
        start_batch = 0
        
        if resume and not dry_run:
            checkpoint_data = self._load_checkpoint(checkpoint_path)
            processed_tables = checkpoint_data["processed_tables"]
            start_batch = checkpoint_data["last_batch"]
            
            if processed_tables:
                logger.info(f"Resuming from checkpoint: {len(processed_tables)}/{len(models)} tables already processed")
                logger.info(f"  Last batch: {start_batch}")
                logger.info(f"  Processed tables: {len(processed_tables)}")
                logger.info(f"  Resuming from batch {start_batch + 1}")
            else:
                logger.info("No checkpoint found. Starting fresh.")
        elif dry_run:
            logger.info("Dry run mode: Checkpoint will not be saved")
        
        results = {
            "mdl_file": str(mdl_file_path),
            "product_name": product_name,
            "domain": domain,
            "tables_processed": 0,
            "contexts_created": 0,
            "edges_created": 0,
            "fields_extracted": 0,
            "fields_saved_to_postgres": 0,
            "contexts_saved_to_postgres": 0,
            "edges_saved_to_postgres": 0,
            "errors": []
        }
        
        # Process tables in batches of 10
        batch_size = 10
        total_batches = (len(models) + batch_size - 1) // batch_size
        
        logger.info(f"Processing {len(models)} tables in {total_batches} batches of {batch_size}")
        if resume and not dry_run and processed_tables:
            remaining = len(models) - len(processed_tables)
            logger.info(f"  {len(processed_tables)} already processed, {remaining} remaining")
        logger.info("")
        
        for batch_num in range(start_batch, total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(models))
            batch = models[start_idx:end_idx]
            
            logger.info("=" * 80)
            logger.info(f"Processing Batch {batch_num + 1}/{total_batches} (tables {start_idx + 1}-{end_idx} of {len(models)})")
            logger.info("=" * 80)
            
            batch_processed_count = 0
            
            # Process each table/model in the batch
            for model in batch:
                table_name = model.get("name", "")
                if not table_name:
                    continue
                
                # Skip if already processed (when resuming)
                if resume and not dry_run and table_name in processed_tables:
                    logger.info(f"Skipping {table_name} (already processed)")
                    continue
            
            try:
                logger.info(f"Processing table: {table_name}")
                
                # Combine table MDL
                table_mdl = self.combine_table_mdl(model, mdl_dict)
                
                # Analyze entity for compliance
                logger.info(f"  Analyzing compliance for {table_name}...")
                compliance_analysis = await self.analyze_entity_compliance(
                    table_name=table_name,
                    table_mdl=table_mdl,
                    product_name=product_name
                )
                
                # Create entity context
                context = await self.create_entity_context(
                    table_name=table_name,
                    table_mdl=table_mdl,
                    compliance_analysis=compliance_analysis,
                    product_name=product_name,
                    domain=domain
                )
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Would create context: {context.context_id}")
                    logger.info(f"    Frameworks: {context.regulatory_frameworks}")
                    logger.info(f"    Key concepts: {context.data_types}")
                    results["contexts_created"] += 1
                else:
                    # Save context to vector store
                    context_id = await self.contextual_graph_storage.save_context_definition(context)
                    logger.info(f"  ✓ Created context: {context_id}")
                    results["contexts_created"] += 1
                    
                    # Save context to PostgreSQL document_kg_insights
                    await self._initialize_database_pool()
                    saved_to_postgres = await self._save_doc_insight_to_postgres(
                        doc_id=context_id,
                        document_content=context.document,
                        extraction_type="context",
                        extracted_data={
                            "context_type": context.context_type,
                            "regulatory_frameworks": context.regulatory_frameworks,
                            "data_types": context.data_types,
                            "systems": context.systems,
                            "table_name": table_name,
                            "product_name": product_name,
                            "compliance_analysis": compliance_analysis
                        },
                        context_id=context_id,
                        extraction_metadata={
                            "context_type": context.context_type,
                            "table_name": table_name,
                            "product_name": product_name,
                            "domain": domain,
                            "source": "mdl_contextual_graph"
                        }
                    )
                    if saved_to_postgres:
                        results["contexts_saved_to_postgres"] += 1
                        logger.info(f"  ✓ Saved context to PostgreSQL: {context_id}")
                
                # Create control edges
                edges = await self.create_control_edges(
                    context_id=context.context_id,
                    table_name=table_name,
                    compliance_analysis=compliance_analysis
                )
                
                if dry_run:
                    logger.info(f"  [DRY RUN] Would create {len(edges)} edges to controls")
                    results["edges_created"] += len(edges)
                else:
                    # Save edges to vector store
                    if edges:
                        edge_ids = await self.contextual_graph_storage.save_contextual_edges(edges)
                        logger.info(f"  ✓ Created {len(edge_ids)} edges to controls")
                        results["edges_created"] += len(edge_ids)
                        
                        # Save edges to PostgreSQL document_kg_insights
                        await self._initialize_database_pool()
                        edges_saved_count = 0
                        for edge in edges:
                            saved_to_postgres = await self._save_doc_insight_to_postgres(
                                doc_id=edge.edge_id,
                                document_content=edge.document,
                                extraction_type="edge",
                                extracted_data={
                                    "edge_type": edge.edge_type,
                                    "source_entity_id": edge.source_entity_id,
                                    "source_entity_type": edge.source_entity_type,
                                    "target_entity_id": edge.target_entity_id,
                                    "target_entity_type": edge.target_entity_type,
                                    "relevance_score": edge.relevance_score
                                },
                                context_id=edge.context_id,
                                extraction_metadata={
                                    "edge_type": edge.edge_type,
                                    "source_entity_id": edge.source_entity_id,
                                    "source_entity_type": edge.source_entity_type,
                                    "target_entity_id": edge.target_entity_id,
                                    "target_entity_type": edge.target_entity_type,
                                    "table_name": table_name,
                                    "product_name": product_name,
                                    "source": "mdl_contextual_graph"
                                }
                            )
                            if saved_to_postgres:
                                edges_saved_count += 1
                                results["edges_saved_to_postgres"] += 1
                        
                        if edges_saved_count > 0:
                            logger.info(f"  ✓ Saved {edges_saved_count} edges to PostgreSQL")
                
                # Extract fields from table columns
                columns = model.get("columns", [])
                if columns:
                    logger.info(f"  Extracting fields from {len(columns)} columns...")
                    fields_result = await self.extract_table_fields(
                        table_name=table_name,
                        columns=columns,
                        context_id=context.context_id,
                        product_name=product_name,
                        domain=domain,
                        dry_run=dry_run
                    )
                    
                    extracted_fields = fields_result.get("extracted_fields", [])
                    field_edges = fields_result.get("edges", [])
                    
                    if dry_run:
                        logger.info(f"  [DRY RUN] Would extract {len(extracted_fields)} fields")
                        results["fields_extracted"] += len(extracted_fields)
                    else:
                        results["fields_extracted"] += len(extracted_fields)
                        
                        # Save field edges to contextual graph
                        if field_edges:
                            edge_ids = await self.contextual_graph_storage.save_contextual_edges(field_edges)
                            logger.info(f"  ✓ Created {len(edge_ids)} field relationship edges")
                            results["edges_created"] += len(edge_ids)
                            
                            # Save field edges to PostgreSQL
                            await self._initialize_database_pool()
                            field_edges_saved = 0
                            for edge in field_edges:
                                saved = await self._save_doc_insight_to_postgres(
                                    doc_id=edge.edge_id,
                                    document_content=edge.document,
                                    extraction_type="edge",
                                    extracted_data={
                                        "edge_type": edge.edge_type,
                                        "source_entity_id": edge.source_entity_id,
                                        "source_entity_type": edge.source_entity_type,
                                        "target_entity_id": edge.target_entity_id,
                                        "target_entity_type": edge.target_entity_type,
                                        "relevance_score": edge.relevance_score
                                    },
                                    context_id=edge.context_id,
                                    extraction_metadata={
                                        "edge_type": edge.edge_type,
                                        "source_entity_id": edge.source_entity_id,
                                        "source_entity_type": edge.source_entity_type,
                                        "target_entity_id": edge.target_entity_id,
                                        "target_entity_type": edge.target_entity_type,
                                        "table_name": table_name,
                                        "product_name": product_name,
                                        "source": "mdl_contextual_graph_fields"
                                    }
                                )
                                if saved:
                                    field_edges_saved += 1
                            
                            if field_edges_saved > 0:
                                results["edges_saved_to_postgres"] += field_edges_saved
                        
                        # Save field documents to PostgreSQL
                        if extracted_fields:
                            await self._initialize_database_pool()
                            fields_saved = 0
                            for field in extracted_fields:
                                field_name = field.get("field_name", "")
                                field_id = f"{context.context_id}_{field_name}".lower().replace(" ", "_")
                                
                                saved = await self._save_doc_insight_to_postgres(
                                    doc_id=field_id,
                                    document_content=json.dumps(field, indent=2),
                                    extraction_type="fields",
                                    extracted_data={
                                        "field_name": field_name,
                                        "field_value": field.get("field_value", ""),
                                        "data_type": field.get("data_type", ""),
                                        "table_name": table_name
                                    },
                                    context_id=context.context_id,
                                    extraction_metadata={
                                        "field_name": field_name,
                                        "table_name": table_name,
                                        "product_name": product_name,
                                        "domain": domain,
                                        "source": "mdl_contextual_graph"
                                    }
                                )
                                if saved:
                                    fields_saved += 1
                            
                            if fields_saved > 0:
                                results["fields_saved_to_postgres"] += fields_saved
                                logger.info(f"  ✓ Saved {fields_saved} fields to PostgreSQL")
                
                results["tables_processed"] += 1
                batch_processed_count += 1
                
                # Mark table as processed
                if not dry_run:
                    processed_tables.add(table_name)
                
            except Exception as e:
                error_msg = f"Error processing table {table_name}: {e}"
                logger.error(f"  ✗ {error_msg}")
                results["errors"].append(error_msg)
                logger.debug(f"  Error details: {type(e).__name__}: {str(e)}", exc_info=True)
            
            # Save checkpoint after each batch (if not dry run)
            if not dry_run and batch_processed_count > 0:
                self._save_checkpoint(
                    checkpoint_path=checkpoint_path,
                    processed_tables=processed_tables,
                    batch_number=batch_num + 1,
                    total_tables=len(models)
                )
            
            # Log batch progress
            logger.info(f"  Batch {batch_num + 1} progress: {results['tables_processed']}/{len(models)} tables processed")
            if not dry_run:
                logger.info(f"  Checkpoint saved: {len(processed_tables)}/{len(models)} tables processed")
            logger.info("")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("Ingestion Summary")
        logger.info("=" * 80)
        logger.info(f"Tables Processed: {results['tables_processed']}")
        logger.info(f"Contexts Created: {results['contexts_created']}")
        logger.info(f"  - Vector store: {results['contexts_created']}")
        logger.info(f"  - PostgreSQL: {results.get('contexts_saved_to_postgres', 0)}")
        logger.info(f"Fields Extracted: {results.get('fields_extracted', 0)}")
        logger.info(f"  - Vector store (fields collection): {results.get('fields_extracted', 0)}")
        logger.info(f"  - PostgreSQL: {results.get('fields_saved_to_postgres', 0)}")
        logger.info(f"Edges Created: {results['edges_created']}")
        logger.info(f"  - Vector store: {results['edges_created']}")
        logger.info(f"  - PostgreSQL: {results.get('edges_saved_to_postgres', 0)}")
        if results["errors"]:
            logger.warning(f"Errors: {len(results['errors'])}")
            for error in results["errors"]:
                logger.warning(f"  - {error}")
        logger.info("=" * 80)
        
        # Verify ChromaDB collections
        if not dry_run and self.vector_store_type == "chroma" and hasattr(self, 'contextual_graph_storage'):
            try:
                from app.core.settings import get_settings
                from app.core.dependencies import get_chromadb_client
                
                settings = get_settings()
                chroma_path = settings.CHROMA_STORE_PATH
                
                logger.info("")
                logger.info("=" * 80)
                logger.info("ChromaDB Store Verification")
                logger.info("=" * 80)
                logger.info(f"ChromaDB Path: {chroma_path}")
                
                # Get persistent client to list collections
                persistent_client = get_chromadb_client()
                collections = persistent_client.list_collections()
                
                # Filter collections created by this script
                relevant_collections = [
                    "context_definitions",
                    "contextual_edges",
                    "fields"
                ]
                
                logger.info(f"Total collections in ChromaDB: {len(collections)}")
                logger.info("")
                logger.info("Relevant collections created by this script:")
                
                total_docs = 0
                for collection_name in relevant_collections:
                    try:
                        collection = persistent_client.get_collection(collection_name)
                        count = collection.count()
                        total_docs += count
                        status = "✓" if count > 0 else "✗ (empty)"
                        logger.info(f"  {status} '{collection_name}': {count} documents")
                    except Exception:
                        logger.warning(f"  ✗ '{collection_name}': collection does not exist")
                
                logger.info(f"Total documents in relevant collections: {total_docs}")
                logger.info("=" * 80)
            except Exception as e:
                logger.warning(f"Could not verify ChromaDB collections: {str(e)}")
        
        results["success"] = len(results["errors"]) == 0
        return results


async def main_async():
    """Async CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest MDL definitions into contextual graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--mdl-file",
        type=str,
        required=True,
        help="Path to MDL JSON file"
    )
    
    parser.add_argument(
        "--product-name",
        type=str,
        required=True,
        help="Product name (e.g., 'Snyk')"
    )
    
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Domain filter (optional)"
    )
    
    parser.add_argument(
        "--collection-prefix",
        type=str,
        default="",
        help="[DEPRECATED] Prefix for ChromaDB collections. This is ignored - collections are used without prefixes to match collection_factory.py"
    )
    
    parser.add_argument(
        "--vector-store",
        type=str,
        choices=["chroma", "qdrant"],
        default="chroma",
        help="Vector store type (default: chroma)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode: show what would be ingested without actually ingesting"
    )
    
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=0.2,
        help="Temperature for LLM calls (default: 0.2)"
    )
    
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume from checkpoint. Start fresh (default: resume from checkpoint if available)"
    )
    
    args = parser.parse_args()
    
    # Create ingester (collection_prefix is ignored - always uses empty prefix)
    if args.collection_prefix:
        logger.warning(f"--collection-prefix is deprecated and ignored. Collections are used without prefixes.")
    
    ingester = MDLContextualGraphIngester(
        collection_prefix="",  # Always empty - use collections as defined in collection_factory.py
        vector_store_type=args.vector_store,
        llm_temperature=args.llm_temperature
    )
    
    # Ingest MDL file
    mdl_path = Path(args.mdl_file)
    if not mdl_path.exists():
        logger.error(f"MDL file not found: {mdl_path}")
        return 1
    
    result = await ingester.ingest_mdl_file(
        mdl_file_path=mdl_path,
        product_name=args.product_name,
        domain=args.domain,
        dry_run=args.dry_run,
        resume=not args.no_resume
    )
    
    if result["success"]:
        logger.info("\n✓ Ingestion completed successfully")
        return 0
    else:
        logger.error(f"\n✗ Ingestion completed with errors: {len(result.get('errors', []))} errors")
        return 1


def main():
    """CLI entry point wrapper."""
    import asyncio
    return asyncio.run(main_async())


if __name__ == "__main__":
    import sys
    sys.exit(main())

