"""
Document Builder for Unified Storage

This module provides utilities for building and enhancing documents
for the unified storage system. It handles the creation of enhanced
documents with business context, technical structure, and metadata.

Features:
- Enhanced document creation with business context
- Metadata enrichment and validation
- Document structure standardization
- Integration with helper utilities
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import json
from datetime import datetime

from langchain_core.documents import Document as LangchainDocument
from app.indexing.utils import helper

logger = logging.getLogger("genieml-agents")


@dataclass
class DocumentMetadata:
    """Standardized document metadata structure."""
    # Primary identifiers
    type: str
    name: str
    project_id: str
    
    # Table-specific metadata
    table_name: Optional[str] = None
    primary_key: Optional[str] = None
    
    # Business context
    display_name: Optional[str] = None
    description: Optional[str] = None
    business_purpose: Optional[str] = None
    
    # Technical metadata
    document_type: Optional[str] = None  # unified, individual
    batch_index: Optional[int] = None
    column_count: Optional[int] = None
    
    # Classification and tags
    classification: Optional[str] = None
    tags: Optional[List[str]] = None
    
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # TF-IDF vector
    tfidf_vector: Optional[List[float]] = None


class DocumentBuilder:
    """
    Document builder for the unified storage system.
    
    This class provides utilities for:
    1. Building enhanced documents with business context
    2. Standardizing document metadata
    3. Integrating with helper utilities
    4. Creating consistent document structures
    """
    
    def __init__(self):
        """Initialize the document builder."""
        logger.info("Document Builder initialized")
    
    def build_unified_document(
        self,
        table_name: str,
        project_id: str,
        model: Dict[str, Any],
        mdl: Dict[str, Any],
        enhanced_columns: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> LangchainDocument:
        """
        Build a unified TABLE_SCHEMA document.
        
        Args:
            table_name: Name of the table
            project_id: Project identifier
            model: Model definition from MDL
            mdl: Complete MDL structure
            enhanced_columns: Enhanced column definitions
            relationships: Table relationships
            
        Returns:
            LangchainDocument with unified structure
        """
        logger.info(f"Building unified document for table: {table_name}")
        
        try:
            # Create unified document content
            unified_content = {
                "type": "TABLE_SCHEMA",
                "table_name": table_name,
                "project_id": project_id,
                
                # Technical structure
                "primary_key": model.get("primaryKey", ""),
                "columns": enhanced_columns,
                "relationships": relationships,
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
                
                # Timestamps
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Create metadata
            metadata = DocumentMetadata(
                type="TABLE_SCHEMA",
                name=table_name,
                project_id=project_id,
                table_name=table_name,
                primary_key=model.get("primaryKey", ""),
                display_name=model.get("properties", {}).get("displayName", ""),
                description=model.get("properties", {}).get("description", ""),
                business_purpose=model.get("properties", {}).get("businessPurpose", ""),
                document_type="unified",
                classification=model.get("properties", {}).get("classification", "internal"),
                tags=model.get("properties", {}).get("tags", []),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # Convert to dict for LangchainDocument
            metadata_dict = asdict(metadata)
            
            # Create LangchainDocument
            doc = LangchainDocument(
                page_content=json.dumps(unified_content, indent=2),
                metadata=metadata_dict
            )
            
            logger.info(f"Successfully built unified document for table: {table_name}")
            return doc
            
        except Exception as e:
            logger.error(f"Error building unified document for {table_name}: {str(e)}")
            raise
    
    def build_table_columns_document(
        self,
        table_name: str,
        project_id: str,
        columns: List[Dict[str, Any]],
        batch_index: int = 0
    ) -> LangchainDocument:
        """
        Build a TABLE_COLUMNS document.
        
        Args:
            table_name: Name of the table
            project_id: Project identifier
            columns: List of column definitions
            batch_index: Batch index for column batching
            
        Returns:
            LangchainDocument with TABLE_COLUMNS structure
        """
        logger.info(f"Building TABLE_COLUMNS document for table: {table_name}, batch: {batch_index}")
        
        try:
            # Create TABLE_COLUMNS content
            content = {
                "type": "TABLE_COLUMNS",
                "table_name": table_name,
                "project_id": project_id,
                "batch_index": batch_index,
                "columns": columns
            }
            
            # Create metadata
            metadata = DocumentMetadata(
                type="TABLE_COLUMNS",
                name=table_name,
                project_id=project_id,
                table_name=table_name,
                document_type="individual",
                batch_index=batch_index,
                column_count=len(columns),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # Convert to dict for LangchainDocument
            metadata_dict = asdict(metadata)
            
            # Create LangchainDocument
            doc = LangchainDocument(
                page_content=json.dumps(content, indent=2),
                metadata=metadata_dict
            )
            
            logger.info(f"Successfully built TABLE_COLUMNS document for table: {table_name}")
            return doc
            
        except Exception as e:
            logger.error(f"Error building TABLE_COLUMNS document for {table_name}: {str(e)}")
            raise
    
    def build_relationships_document(
        self,
        table_name: str,
        project_id: str,
        relationship: Dict[str, Any],
        constraint: str
    ) -> LangchainDocument:
        """
        Build a RELATIONSHIPS document.
        
        Args:
            table_name: Name of the table
            project_id: Project identifier
            relationship: Relationship definition
            constraint: Foreign key constraint
            
        Returns:
            LangchainDocument with RELATIONSHIPS structure
        """
        logger.info(f"Building RELATIONSHIPS document for table: {table_name}")
        
        try:
            # Create RELATIONSHIPS content
            content = {
                "type": "FOREIGN_KEY",
                "table_name": table_name,
                "project_id": project_id,
                "constraint": constraint,
                "tables": relationship.get("models", []),
                "condition": relationship.get("condition", ""),
                "joinType": relationship.get("joinType", ""),
                "properties": relationship.get("properties", {})
            }
            
            # Create metadata
            metadata = DocumentMetadata(
                type="RELATIONSHIPS",
                name=f"{table_name}_{relationship.get('name', '')}",
                project_id=project_id,
                table_name=table_name,
                document_type="individual",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # Convert to dict for LangchainDocument
            metadata_dict = asdict(metadata)
            
            # Create LangchainDocument
            doc = LangchainDocument(
                page_content=json.dumps(content, indent=2),
                metadata=metadata_dict
            )
            
            logger.info(f"Successfully built RELATIONSHIPS document for table: {table_name}")
            return doc
            
        except Exception as e:
            logger.error(f"Error building RELATIONSHIPS document for {table_name}: {str(e)}")
            raise
    
    def build_view_document(
        self,
        view_name: str,
        project_id: str,
        view: Dict[str, Any]
    ) -> LangchainDocument:
        """
        Build a VIEW document.
        
        Args:
            view_name: Name of the view
            project_id: Project identifier
            view: View definition
            
        Returns:
            LangchainDocument with VIEW structure
        """
        logger.info(f"Building VIEW document for view: {view_name}")
        
        try:
            # Create VIEW content
            content = {
                "type": "VIEW",
                "name": view_name,
                "project_id": project_id,
                "statement": view.get("statement", ""),
                "properties": view.get("properties", {})
            }
            
            # Create metadata
            metadata = DocumentMetadata(
                type="VIEW",
                name=view_name,
                project_id=project_id,
                display_name=view.get("properties", {}).get("displayName", ""),
                description=view.get("properties", {}).get("description", ""),
                document_type="individual",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # Convert to dict for LangchainDocument
            metadata_dict = asdict(metadata)
            
            # Create LangchainDocument
            doc = LangchainDocument(
                page_content=json.dumps(content, indent=2),
                metadata=metadata_dict
            )
            
            logger.info(f"Successfully built VIEW document for view: {view_name}")
            return doc
            
        except Exception as e:
            logger.error(f"Error building VIEW document for {view_name}: {str(e)}")
            raise
    
    def build_metric_document(
        self,
        metric_name: str,
        project_id: str,
        metric: Dict[str, Any],
        dimensions: List[Dict[str, Any]],
        measures: List[Dict[str, Any]]
    ) -> LangchainDocument:
        """
        Build a METRIC document.
        
        Args:
            metric_name: Name of the metric
            project_id: Project identifier
            metric: Metric definition
            dimensions: Dimension columns
            measures: Measure columns
            
        Returns:
            LangchainDocument with METRIC structure
        """
        logger.info(f"Building METRIC document for metric: {metric_name}")
        
        try:
            # Create METRIC content
            content = {
                "type": "METRIC",
                "name": metric_name,
                "project_id": project_id,
                "columns": dimensions + measures,
                "properties": metric.get("properties", {}),
                "dimension_count": len(dimensions),
                "measure_count": len(measures)
            }
            
            # Create metadata
            metadata = DocumentMetadata(
                type="METRIC",
                name=metric_name,
                project_id=project_id,
                display_name=metric.get("properties", {}).get("displayName", ""),
                description=metric.get("properties", {}).get("description", ""),
                document_type="individual",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # Convert to dict for LangchainDocument
            metadata_dict = asdict(metadata)
            
            # Create LangchainDocument
            doc = LangchainDocument(
                page_content=json.dumps(content, indent=2),
                metadata=metadata_dict
            )
            
            logger.info(f"Successfully built METRIC document for metric: {metric_name}")
            return doc
            
        except Exception as e:
            logger.error(f"Error building METRIC document for {metric_name}: {str(e)}")
            raise
    
    def enhance_column_with_business_context(
        self,
        column: Dict[str, Any],
        model: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance a column with business context using helper utilities.
        
        Args:
            column: Column definition
            model: Model definition
            
        Returns:
            Enhanced column definition
        """
        try:
            # Start with base column information
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
                "notNull": column.get("notNull", False),
                # Add field type for dimension vs fact classification
                "field_type": self._determine_field_type(column, model)
            }
            
            # Apply helper functions for comments
            comments = []
            for helper_name, helper_func in helper.COLUMN_COMMENT_HELPERS.items():
                if helper_func.condition(column, model=model):
                    comment = helper_func(column, model=model)
                    if comment:
                        comments.append(comment)
            
            enhanced_column["comments"] = "".join(comments)
            
            # Apply column preprocessors
            for key, helper_func in helper.COLUMN_PREPROCESSORS.items():
                if helper_func.condition(column, model=model):
                    enhanced_column[key] = helper_func(column, model=model)
            
            # Add business context from properties
            if "properties" in column:
                properties = column["properties"]
                enhanced_column.update({
                    "display_name": properties.get("displayName", ""),
                    "business_description": properties.get("description", ""),
                    "business_purpose": properties.get("businessPurpose", ""),
                    "usage_type": properties.get("usageType", ""),
                    "example_values": properties.get("exampleValues", []),
                    "business_rules": properties.get("businessRules", []),
                    "privacy_classification": properties.get("privacyClassification", ""),
                    "data_quality_checks": properties.get("dataQualityChecks", []),
                    "aggregation_suggestions": properties.get("aggregationSuggestions", []),
                    "filtering_suggestions": properties.get("filteringSuggestions", [])
                })
            
            return enhanced_column
            
        except Exception as e:
            logger.error(f"Error enhancing column {column.get('name', 'unknown')}: {str(e)}")
            return column
    
    def _extract_constraints(self, model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract constraints from model definition."""
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
    
    def validate_document_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate document metadata structure.
        
        Args:
            metadata: Document metadata to validate
            
        Returns:
            True if metadata is valid, False otherwise
        """
        required_fields = ["type", "name", "project_id"]
        
        for field in required_fields:
            if field not in metadata or not metadata[field]:
                logger.warning(f"Missing required metadata field: {field}")
                return False
        
        return True
    
    def standardize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize document metadata structure.
        
        Args:
            metadata: Raw metadata to standardize
            
        Returns:
            Standardized metadata
        """
        standardized = {
            "type": metadata.get("type", ""),
            "name": metadata.get("name", ""),
            "project_id": metadata.get("project_id", ""),
            "table_name": metadata.get("table_name"),
            "primary_key": metadata.get("primary_key"),
            "display_name": metadata.get("display_name"),
            "description": metadata.get("description"),
            "business_purpose": metadata.get("business_purpose"),
            "document_type": metadata.get("document_type"),
            "batch_index": metadata.get("batch_index"),
            "column_count": metadata.get("column_count"),
            "classification": metadata.get("classification", "internal"),
            "tags": metadata.get("tags", []),
            "created_at": metadata.get("created_at", datetime.now().isoformat()),
            "updated_at": metadata.get("updated_at", datetime.now().isoformat()),
            "tfidf_vector": metadata.get("tfidf_vector")
        }
        
        # Remove None values
        standardized = {k: v for k, v in standardized.items() if v is not None}
        
        return standardized
    
    def _determine_field_type(self, column: Dict[str, Any], model: Dict[str, Any]) -> str:
        """
        Determine the field type (dimension vs fact) for a column.
        
        Args:
            column: Column definition
            model: Model definition
            
        Returns:
            Field type: 'dimension', 'fact', 'identifier', 'timestamp', 'calculated'
        """
        column_name = column.get("name", "").lower()
        data_type = column.get("type", "").upper()
        is_primary_key = column.get("name") == model.get("primaryKey", "")
        is_calculated = column.get("isCalculated", False)
        usage_type = column.get("properties", {}).get("usageType", "").lower()
        
        # Primary key is always an identifier
        if is_primary_key:
            return "identifier"
        
        # Calculated fields are facts
        if is_calculated:
            return "fact"
        
        # Check usage type from properties
        if usage_type:
            if usage_type in ["measure", "metric", "kpi", "aggregate"]:
                return "fact"
            elif usage_type in ["dimension", "attribute", "category", "classification"]:
                return "dimension"
            elif usage_type in ["identifier", "key", "id"]:
                return "identifier"
            elif usage_type in ["timestamp", "date", "time"]:
                return "timestamp"
        
        # Check column name patterns
        if any(pattern in column_name for pattern in ["_id", "_key", "id_", "key_"]):
            return "identifier"
        
        if any(pattern in column_name for pattern in ["_date", "_time", "created_", "updated_", "timestamp"]):
            return "timestamp"
        
        if any(pattern in column_name for pattern in ["_count", "_total", "_sum", "_avg", "_max", "_min", "_amount", "_price", "_cost", "_revenue"]):
            return "fact"
        
        if any(pattern in column_name for pattern in ["_name", "_type", "_status", "_category", "_class", "_group", "_level"]):
            return "dimension"
        
        # Check data type patterns
        if data_type in ["INTEGER", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC"]:
            # Numeric types could be facts or dimensions
            if any(pattern in column_name for pattern in ["count", "total", "sum", "amount", "price", "cost", "revenue", "quantity"]):
                return "fact"
            else:
                return "dimension"
        
        elif data_type in ["VARCHAR", "TEXT", "CHAR", "STRING"]:
            # Text types are usually dimensions
            return "dimension"
        
        elif data_type in ["DATE", "DATETIME", "TIMESTAMP", "TIME"]:
            return "timestamp"
        
        # Default to dimension for unknown cases
        return "dimension"
