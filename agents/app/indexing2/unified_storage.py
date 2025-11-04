"""
Unified ChromaDB Storage Mechanism

This module provides a unified storage system that consolidates all document types
into a single TABLE_SCHEMA document per table, while maintaining individual documents
for specific types (TABLE_COLUMNS, RELATIONSHIPS, METRICS, VIEWS).

Key Features:
- TABLE_SCHEMA as the primary document with all metadata
- Individual documents for each type with TABLE as the key
- TF-IDF generation for quick reference lookups
- Enhanced search capabilities with embeddings
- Backward compatibility with existing retrieval systems
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import json

from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy
from app.indexing.utils import helper

logger = logging.getLogger("genieml-agents")


@dataclass
class TableSchemaDocument:
    """
    Unified TABLE_SCHEMA document structure.
    
    This is the primary document that contains all information about a table:
    - Technical structure (columns, relationships, constraints)
    - Business descriptions and context
    - Enhanced metadata and properties
    - TF-IDF vectors for quick lookups
    """
    # Primary identifiers
    table_name: str
    project_id: str
    
    # Technical structure
    primary_key: str
    columns: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    
    # Business context
    display_name: str
    description: str
    business_purpose: str
    business_rules: List[str]
    
    # Enhanced metadata
    properties: Dict[str, Any]
    tags: List[str]
    classification: str  # public/internal/confidential/restricted
    
    # TF-IDF vectors
    tfidf_vectors: Dict[str, List[float]]
    
    # Timestamps
    created_at: str
    updated_at: str


@dataclass
class IndividualDocument:
    """
    Individual document for specific types (TABLE_COLUMNS, RELATIONSHIPS, etc.).
    
    These documents are linked to the main TABLE_SCHEMA document
    and provide detailed information for specific aspects.
    """
    document_type: str  # TABLE_COLUMNS, RELATIONSHIPS, METRICS, VIEWS
    table_name: str
    project_id: str
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    tfidf_vector: List[float]


class UnifiedStorage:
    """
    Unified ChromaDB storage mechanism that consolidates all document types.
    
    This class provides:
    1. TABLE_SCHEMA documents with complete table information
    2. Individual documents for each type (TABLE_COLUMNS, RELATIONSHIPS, etc.)
    3. TF-IDF generation for quick reference lookups
    4. Enhanced search capabilities
    5. Backward compatibility
    """
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        tfidf_generator: Any = None,
        column_batch_size: int = 200,
    ):
        """Initialize the unified storage system."""
        logger.info("Initializing Unified Storage system")
        self._document_store = document_store
        self._embedder = embedder
        self._tfidf_generator = tfidf_generator
        self._column_batch_size = column_batch_size
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        logger.info("Unified Storage system initialized successfully")
    
    async def process_mdl(
        self, 
        mdl_str: str, 
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process MDL string and create unified documents.
        
        Args:
            mdl_str: MDL string containing models, relationships, views, metrics
            project_id: Project identifier
            
        Returns:
            Dict containing processing results
        """
        logger.info(f"Starting unified MDL processing for project: {project_id}")
        
        try:
            # Parse MDL
            mdl = json.loads(mdl_str)
            logger.info("MDL parsed successfully")
            
            # Create unified documents
            unified_docs = await self._create_unified_documents(mdl, project_id)
            logger.info(f"Created {len(unified_docs)} unified documents")
            
            # Create individual documents
            individual_docs = await self._create_individual_documents(mdl, project_id)
            logger.info(f"Created {len(individual_docs)} individual documents")
            
            # Generate TF-IDF vectors
            if self._tfidf_generator:
                await self._generate_tfidf_vectors(unified_docs + individual_docs)
                logger.info("TF-IDF vectors generated successfully")
            
            # Store documents
            all_documents = unified_docs + individual_docs
            write_result = await self._writer.run(documents=all_documents)
            logger.info(f"Successfully stored {write_result['documents_written']} documents")
            
            return {
                "documents_written": write_result["documents_written"],
                "unified_documents": len(unified_docs),
                "individual_documents": len(individual_docs),
                "project_id": project_id
            }
            
        except Exception as e:
            error_msg = f"Error in unified MDL processing: {str(e)}"
            logger.error(error_msg)
            raise
    
    async def _create_unified_documents(
        self, 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create unified TABLE_SCHEMA documents."""
        logger.info("Creating unified TABLE_SCHEMA documents")
        
        documents = []
        models = mdl.get("models", [])
        
        for model in models:
            try:
                # Extract table information
                table_name = model.get("name", "")
                if not table_name:
                    continue
                
                # Create unified document structure
                unified_doc = await self._build_unified_document(model, mdl, project_id)
                
                # Convert to LangchainDocument
                doc = LangchainDocument(
                    page_content=json.dumps(unified_doc, indent=2),
                    metadata={
                        "type": "TABLE_SCHEMA",
                        "name": table_name,
                        "project_id": project_id,
                        "document_type": "unified",
                        "table_name": table_name,
                        "primary_key": model.get("primaryKey", ""),
                        "display_name": model.get("properties", {}).get("displayName", ""),
                        "description": model.get("properties", {}).get("description", ""),
                        "business_purpose": model.get("properties", {}).get("businessPurpose", ""),
                        "classification": model.get("properties", {}).get("classification", "internal"),
                        "tags": model.get("properties", {}).get("tags", []),
                        "created_at": str(uuid.uuid4()),  # Placeholder for actual timestamp
                        "updated_at": str(uuid.uuid4())
                    }
                )
                
                documents.append(doc)
                logger.info(f"Created unified document for table: {table_name}")
                
            except Exception as e:
                logger.error(f"Error creating unified document for {model.get('name', 'unknown')}: {str(e)}")
                continue
        
        return documents
    
    async def _build_unified_document(
        self, 
        model: Dict[str, Any], 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> Dict[str, Any]:
        """Build the unified document structure."""
        
        # Extract relationships for this table
        table_relationships = self._extract_table_relationships(model["name"], mdl.get("relationships", []))
        
        # Extract columns with enhanced information
        enhanced_columns = await self._enhance_columns(model.get("columns", []), model)
        
        # Build unified structure
        unified_doc = {
            "type": "TABLE_SCHEMA",
            "table_name": model["name"],
            "project_id": project_id,
            
            # Technical structure
            "primary_key": model.get("primaryKey", ""),
            "columns": enhanced_columns,
            "relationships": table_relationships,
            "constraints": self._extract_constraints(model),
            
            # Business context
            "display_name": model.get("properties", {}).get("displayName", ""),
            "description": model.get("properties", {}).get("description", ""),
            "business_purpose": model.get("properties", {}).get("businessPurpose", ""),
            "business_rules": model.get("properties", {}).get("businessRules", []),
            
            # Enhanced metadata
            "properties": model.get("properties", {}),
            "tags": model.get("properties", {}).get("tags", []),
            "classification": model.get("properties", {}).get("classification", "internal"),
            
            # TF-IDF vectors (will be populated later)
            "tfidf_vectors": {},
            
            # Timestamps
            "created_at": str(uuid.uuid4()),  # Placeholder
            "updated_at": str(uuid.uuid4())
        }
        
        return unified_doc
    
    async def _enhance_columns(
        self, 
        columns: List[Dict[str, Any]], 
        model: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance columns with additional metadata and descriptions."""
        enhanced_columns = []
        
        for column in columns:
            if column.get("isHidden", False):
                continue
                
            # Apply column preprocessors
            enhanced_column = {
                "name": column.get("name", ""),
                "type": column.get("type", ""),
                "data_type": column.get("type", ""),
                "is_primary_key": column.get("name") == model.get("primaryKey", ""),
                "is_nullable": not column.get("notNull", False),
                "is_calculated": column.get("isCalculated", False),
                "expression": column.get("expression", ""),
                "relationship": column.get("relationship", {}),
                "properties": column.get("properties", {}),
                "notNull": column.get("notNull", False)
            }
            
            # Apply helper functions for comments and metadata
            comments = []
            for helper_name, helper_func in helper.COLUMN_COMMENT_HELPERS.items():
                if helper_func.condition(column, model=model):
                    comment = helper_func(column, model=model)
                    if comment:
                        comments.append(comment)
            
            enhanced_column["comments"] = "".join(comments)
            
            # Add business context if available
            if "properties" in column:
                enhanced_column["display_name"] = column["properties"].get("displayName", "")
                enhanced_column["business_description"] = column["properties"].get("description", "")
                enhanced_column["business_purpose"] = column["properties"].get("businessPurpose", "")
                enhanced_column["usage_type"] = column["properties"].get("usageType", "")
                enhanced_column["example_values"] = column["properties"].get("exampleValues", [])
                enhanced_column["business_rules"] = column["properties"].get("businessRules", [])
                enhanced_column["privacy_classification"] = column["properties"].get("privacyClassification", "")
            
            enhanced_columns.append(enhanced_column)
        
        return enhanced_columns
    
    def _extract_table_relationships(
        self, 
        table_name: str, 
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relationships for a specific table."""
        table_relationships = []
        
        for relationship in relationships:
            models_in_relationship = relationship.get("models", [])
            if table_name in models_in_relationship:
                table_relationships.append({
                    "name": relationship.get("name", ""),
                    "models": models_in_relationship,
                    "joinType": relationship.get("joinType", ""),
                    "condition": relationship.get("condition", ""),
                    "properties": relationship.get("properties", {})
                })
        
        return table_relationships
    
    def _extract_constraints(self, model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract constraints from model."""
        constraints = []
        
        # Add primary key constraint
        if model.get("primaryKey"):
            constraints.append({
                "type": "PRIMARY_KEY",
                "column": model["primaryKey"],
                "name": f"pk_{model['name']}"
            })
        
        # Add other constraints if available
        if "constraints" in model:
            constraints.extend(model["constraints"])
        
        return constraints
    
    async def _create_individual_documents(
        self, 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create individual documents for each type."""
        logger.info("Creating individual documents")
        
        documents = []
        
        # Process models for TABLE_COLUMNS documents
        for model in mdl.get("models", []):
            table_name = model.get("name", "")
            if not table_name:
                continue
            
            # Create TABLE_COLUMNS documents
            column_docs = await self._create_table_columns_documents(model, project_id)
            documents.extend(column_docs)
            
            # Create RELATIONSHIPS documents
            relationship_docs = await self._create_relationships_documents(model, mdl, project_id)
            documents.extend(relationship_docs)
        
        # Process views
        for view in mdl.get("views", []):
            view_doc = await self._create_view_document(view, project_id)
            if view_doc:
                documents.append(view_doc)
        
        # Process metrics
        for metric in mdl.get("metrics", []):
            metric_doc = await self._create_metric_document(metric, project_id)
            if metric_doc:
                documents.append(metric_doc)
        
        return documents
    
    async def _create_table_columns_documents(
        self, 
        model: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create TABLE_COLUMNS documents."""
        documents = []
        table_name = model.get("name", "")
        columns = model.get("columns", [])
        
        # Batch columns
        for i in range(0, len(columns), self._column_batch_size):
            batch_columns = columns[i:i + self._column_batch_size]
            
            # Create column documents
            column_docs = []
            for column in batch_columns:
                if column.get("isHidden", False):
                    continue
                
                column_doc = {
                    "type": "COLUMN",
                    "name": column.get("name", ""),
                    "data_type": column.get("type", ""),
                    "is_primary_key": column.get("name") == model.get("primaryKey", ""),
                    "is_calculated": column.get("isCalculated", False),
                    "expression": column.get("expression", ""),
                    "relationship": column.get("relationship", {}),
                    "properties": column.get("properties", {}),
                    "notNull": column.get("notNull", False)
                }
                
                # Add comments
                comments = []
                for helper_name, helper_func in helper.COLUMN_COMMENT_HELPERS.items():
                    if helper_func.condition(column, model=model):
                        comment = helper_func(column, model=model)
                        if comment:
                            comments.append(comment)
                
                column_doc["comment"] = "".join(comments)
                column_docs.append(column_doc)
            
            if column_docs:
                # Create TABLE_COLUMNS document
                doc = LangchainDocument(
                    page_content=json.dumps({
                        "type": "TABLE_COLUMNS",
                        "table_name": table_name,
                        "columns": column_docs
                    }, indent=2),
                    metadata={
                        "type": "TABLE_COLUMNS",
                        "name": table_name,
                        "project_id": project_id,
                        "table_name": table_name,
                        "batch_index": i // self._column_batch_size,
                        "column_count": len(column_docs)
                    }
                )
                documents.append(doc)
        
        return documents
    
    async def _create_relationships_documents(
        self, 
        model: Dict[str, Any], 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create RELATIONSHIPS documents."""
        documents = []
        table_name = model.get("name", "")
        relationships = mdl.get("relationships", [])
        
        # Create primary keys map
        primary_keys_map = {m["name"]: m.get("primaryKey", "") for m in mdl.get("models", [])}
        
        for relationship in relationships:
            models_in_relationship = relationship.get("models", [])
            if table_name not in models_in_relationship:
                continue
            
            # Build foreign key constraint
            condition = relationship.get("condition", "")
            join_type = relationship.get("joinType", "")
            
            if len(models_in_relationship) == 2:
                is_source = table_name == models_in_relationship[0]
                related_table = models_in_relationship[1] if is_source else models_in_relationship[0]
                
                if condition and "=" in condition:
                    condition_parts = condition.split(" = ")
                    fk_column = condition_parts[0 if is_source else 1].split(".")[1]
                    
                    fk_constraint = f"FOREIGN KEY ({fk_column}) REFERENCES {related_table}({primary_keys_map.get(related_table, '')})"
                    
                    # Create RELATIONSHIPS document
                    doc = LangchainDocument(
                        page_content=json.dumps({
                            "type": "FOREIGN_KEY",
                            "constraint": fk_constraint,
                            "tables": models_in_relationship,
                            "condition": condition,
                            "joinType": join_type
                        }, indent=2),
                        metadata={
                            "type": "RELATIONSHIPS",
                            "name": f"{table_name}_{relationship.get('name', '')}",
                            "project_id": project_id,
                            "table_name": table_name,
                            "related_table": related_table,
                            "join_type": join_type
                        }
                    )
                    documents.append(doc)
        
        return documents
    
    async def _create_view_document(
        self, 
        view: Dict[str, Any], 
        project_id: str
    ) -> Optional[LangchainDocument]:
        """Create VIEW document."""
        view_name = view.get("name", "")
        if not view_name:
            return None
        
        doc = LangchainDocument(
            page_content=json.dumps({
                "type": "VIEW",
                "name": view_name,
                "statement": view.get("statement", ""),
                "properties": view.get("properties", {})
            }, indent=2),
            metadata={
                "type": "VIEW",
                "name": view_name,
                "project_id": project_id,
                "display_name": view.get("properties", {}).get("displayName", ""),
                "description": view.get("properties", {}).get("description", "")
            }
        )
        return doc
    
    async def _create_metric_document(
        self, 
        metric: Dict[str, Any], 
        project_id: str
    ) -> Optional[LangchainDocument]:
        """Create METRIC document."""
        metric_name = metric.get("name", "")
        if not metric_name:
            return None
        
        # Create dimension and measure columns
        dimensions = []
        measures = []
        
        for dim in metric.get("dimension", []):
            dimensions.append({
                "type": "COLUMN",
                "name": dim.get("name", ""),
                "data_type": dim.get("type", ""),
                "comment": "-- This column is a dimension\n  "
            })
        
        for measure in metric.get("measure", []):
            measures.append({
                "type": "COLUMN", 
                "name": measure.get("name", ""),
                "data_type": measure.get("type", ""),
                "comment": "-- This column is a measure\n  "
            })
        
        doc = LangchainDocument(
            page_content=json.dumps({
                "type": "METRIC",
                "name": metric_name,
                "columns": dimensions + measures,
                "properties": metric.get("properties", {})
            }, indent=2),
            metadata={
                "type": "METRIC",
                "name": metric_name,
                "project_id": project_id,
                "display_name": metric.get("properties", {}).get("displayName", ""),
                "description": metric.get("properties", {}).get("description", ""),
                "dimension_count": len(dimensions),
                "measure_count": len(measures)
            }
        )
        return doc
    
    async def _generate_tfidf_vectors(
        self, 
        documents: List[LangchainDocument]
    ) -> None:
        """Generate TF-IDF vectors for documents."""
        if not self._tfidf_generator:
            logger.warning("TF-IDF generator not available, skipping vector generation")
            return
        
        logger.info("Generating TF-IDF vectors for documents")
        
        try:
            # Extract text content from documents
            texts = []
            for doc in documents:
                # Combine page_content and metadata for TF-IDF
                text_content = f"{doc.page_content} {json.dumps(doc.metadata)}"
                texts.append(text_content)
            
            # Generate TF-IDF vectors
            tfidf_vectors = await self._tfidf_generator.generate_vectors(texts)
            
            # Add vectors to document metadata
            for i, doc in enumerate(documents):
                if i < len(tfidf_vectors):
                    doc.metadata["tfidf_vector"] = tfidf_vectors[i]
            
            logger.info(f"Generated TF-IDF vectors for {len(documents)} documents")
            
        except Exception as e:
            logger.error(f"Error generating TF-IDF vectors: {str(e)}")
    
    async def clean(self, project_id: Optional[str] = None) -> None:
        """Clean documents for the specified project."""
        logger.info(f"Starting cleanup for project: {project_id}")
        
        try:
            if project_id:
                logger.info(f"Deleting documents for project ID: {project_id}")
                self._document_store.collection.delete(
                    where={"project_id": project_id}
                )
                logger.info(f"Successfully deleted documents for project ID: {project_id}")
            else:
                logger.info("Deleting all documents")
                self._document_store.collection.delete()
                logger.info("Successfully deleted all documents")
                
        except Exception as e:
            error_msg = f"Error cleaning documents: {str(e)}"
            logger.error(error_msg)
            raise
