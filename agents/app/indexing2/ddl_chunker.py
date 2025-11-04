"""
DDL Chunker for Unified Storage System

This module provides DDL chunking capabilities that create separate TABLE_DOCUMENTs
for each table with rich descriptions, business context, and enhanced metadata.
This enables natural language search by table names and business context.

Features:
- Separate TABLE_DOCUMENTs for each table
- Rich business descriptions and context
- Enhanced column descriptions
- Properties object for metadata enhancement
- Natural language search capabilities
- Project ID filtering
"""

import asyncio
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
class TableDocument:
    """
    TABLE_DOCUMENT structure for natural language search.
    
    This document contains all information about a table in a format
    optimized for natural language search and business context discovery.
    """
    # Primary identifiers
    table_name: str
    project_id: str
    
    # Business context
    display_name: str
    description: str
    business_purpose: str
    business_rules: List[str]
    usage_guidelines: List[str]
    
    # Technical structure
    primary_key: str
    columns: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    
    # Enhanced metadata
    properties: Dict[str, Any]
    tags: List[str]
    classification: str
    
    # Search optimization
    searchable_text: str
    business_keywords: List[str]
    technical_keywords: List[str]
    
    # Timestamps
    created_at: str
    updated_at: str
    
    # Optional fields (must come after required fields)
    domain: Optional[str] = None


class DDLChunker:
    """
    DDL Chunker for creating separate TABLE_DOCUMENTs with rich business context.
    
    This class creates separate documents for each table that are
    optimized for natural language search and business context discovery.
    """
    
    def __init__(self, column_batch_size: int = 200):
        """
        Initialize the DDL Chunker.
        
        Args:
            column_batch_size: Batch size for column processing
        """
        self.column_batch_size = column_batch_size
        logger.info("DDL Chunker initialized")
    
    async def create_table_documents(
        self,
        mdl: Dict[str, Any],
        project_id: str
    ) -> List[LangchainDocument]:
        """
        Create separate TABLE_DOCUMENTs for each table.
        
        Args:
            mdl: MDL structure containing models, relationships, views, metrics
            project_id: Project identifier
            
        Returns:
            List of TABLE_DOCUMENT LangchainDocuments
        """
        logger.info(f"Creating TABLE_DOCUMENTs for project: {project_id}")
        
        documents = []
        models = mdl.get("models", [])
        
        for model in models:
            try:
                table_name = model.get("name", "")
                if not table_name:
                    continue
                
                # Create TABLE_DOCUMENT
                table_doc = await self._build_table_document(model, mdl, project_id)
                
                # Convert to LangchainDocument
                doc = LangchainDocument(
                    page_content=json.dumps(table_doc, indent=2),
                    metadata={
                        "type": "TABLE_DOCUMENT",
                        "name": table_name,
                        "project_id": project_id,
                        "table_name": table_name,
                        "display_name": model.get("properties", {}).get("displayName", ""),
                        "description": model.get("properties", {}).get("description", ""),
                        "business_purpose": model.get("properties", {}).get("businessPurpose", ""),
                        "classification": model.get("properties", {}).get("classification", "internal"),
                        "tags": model.get("properties", {}).get("tags", []),
                        "domain": model.get("properties", {}).get("domain", ""),
                        "primary_key": model.get("primaryKey", ""),
                        "column_count": len(model.get("columns", [])),
                        "relationship_count": len(self._extract_table_relationships(table_name, mdl.get("relationships", []))),
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                )
                
                documents.append(doc)
                logger.info(f"Created TABLE_DOCUMENT for table: {table_name}")
                
            except Exception as e:
                logger.error(f"Error creating TABLE_DOCUMENT for {model.get('name', 'unknown')}: {str(e)}")
                continue
        
        return documents
    
    async def create_table_column_documents(
        self,
        mdl: Dict[str, Any],
        project_id: str
    ) -> List[LangchainDocument]:
        """
        Create TABLE_COLUMN documents using helper.py functionality for each column.
        
        Args:
            mdl: MDL structure containing models, relationships, views, metrics
            project_id: Project identifier
            
        Returns:
            List of TABLE_COLUMN LangchainDocuments with comments
        """
        logger.info(f"Creating TABLE_COLUMN documents for project: {project_id}")
        
        documents = []
        models = mdl.get("models", [])
        
        for model in models:
            try:
                table_name = model.get("name", "")
                if not table_name:
                    continue
                
                # Get columns for this table
                columns = model.get("columns", [])
                for column in columns:
                    if column.get("isHidden", False):
                        continue
                    
                    # Create TABLE_COLUMN document using helper functionality
                    column_doc = await self._create_table_column_document(
                        table_name, column, model, project_id
                    )
                    if column_doc:
                        documents.append(column_doc)
                        
            except Exception as e:
                logger.error(f"Error creating TABLE_COLUMN documents for {model.get('name', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Created {len(documents)} TABLE_COLUMN documents")
        return documents
    
    async def _create_table_column_document(
        self,
        table_name: str,
        column: Dict[str, Any],
        model: Dict[str, Any],
        project_id: str
    ) -> Optional[LangchainDocument]:
        """
        Create a TABLE_COLUMN document using helper.py functionality.
        
        Args:
            table_name: Name of the table
            column: Column definition
            model: Model definition
            project_id: Project identifier
            
        Returns:
            TABLE_COLUMN LangchainDocument with comments
        """
        try:
            column_name = column.get("name", "")
            if not column_name:
                return None
            
            # Create TABLE_COLUMN document aligned with existing structure
            column_doc = {
                "type": "COLUMN",
                "name": column_name,
                "table_name": table_name,
                "data_type": column.get("type", ""),
                "is_primary_key": column.get("name") == model.get("primaryKey", ""),
                "is_nullable": not column.get("notNull", False),
                "is_calculated": column.get("isCalculated", False),
                "expression": column.get("expression", ""),
                "relationship": column.get("relationship", {}),
                "properties": column.get("properties", {}),
                # Enhanced properties for better search and classification
                "field_type": self._determine_field_type(column, model),
                "business_context": self._extract_column_business_context(column),
                "technical_context": self._extract_column_technical_context(column),
                "searchable_text": self._create_column_searchable_text(column),
                # Comment with enhanced properties (key-value format)
                "comment": self._build_enhanced_column_comment(column, model)
            }
            
            # Convert to LangchainDocument
            doc = LangchainDocument(
                page_content=json.dumps(column_doc, indent=2),
                metadata={
                    "type": "TABLE_COLUMN",
                    "table_name": table_name,
                    "column_name": column_name,
                    "project_id": project_id,
                    "field_type": column_doc["field_type"],
                    "data_type": column_doc["data_type"],
                    "is_primary_key": column_doc["is_primary_key"],
                    "is_calculated": column_doc["is_calculated"]
                }
            )
            logger.info(f"Created TABLE_COLUMN document for {table_name}.{column_name}")
            logger.info(f"Created TABLE_COLUMN document for json: {json.dumps(column_doc, indent=2)}")
            return doc
            
        except Exception as e:
            logger.error(f"Error creating TABLE_COLUMN document for {table_name}.{column.get('name', 'unknown')}: {str(e)}")
            return None
    
    def _build_column_definition_with_comments(
        self,
        column: Dict[str, Any],
        model: Dict[str, Any]
    ) -> str:
        """
        Build column definition using helper.py functionality with comments.
        
        Args:
            column: Column definition
            model: Model definition
            
        Returns:
            Column definition string with comments
        """
        try:
            column_name = column.get("name", "")
            data_type = column.get("type", "")
            is_nullable = not column.get("notNull", False)
            is_primary_key = column.get("name") == model.get("primaryKey", "")
            
            # Start with basic column definition
            definition_parts = [column_name, data_type]
            
            # Add constraints
            if is_primary_key:
                definition_parts.append("PRIMARY KEY")
            elif not is_nullable:
                definition_parts.append("NOT NULL")
            
            # Add comments using helper functionality
            comments = []
            for helper_name, helper_func in helper.COLUMN_COMMENT_HELPERS.items():
                if helper_func.condition(column, model=model):
                    comment = helper_func(column, model=model)
                    if comment:
                        comments.append(comment)
            
            # Combine definition and comments
            column_definition = " ".join(definition_parts)
            if comments:
                column_definition = "\n  ".join(comments) + column_definition
            
            return column_definition
            
        except Exception as e:
            logger.error(f"Error building column definition with comments: {str(e)}")
            # Fallback to basic definition
            return f"{column.get('name', '')} {column.get('type', '')}"
    
    def _extract_json_metadata_from_definition(self, column_definition: str) -> Dict[str, Any]:
        """
        Extract metadata from column definition using simple key-value comment format.
        
        Args:
            column_definition: Column definition string that may contain key-value comments
            
        Returns:
            Dictionary containing extracted metadata
        """
        import re
        
        try:
            # Look for key-value comments (-- key: value)
            comment_pattern = r'--\s*([^:]+):\s*(.+?)(?=\n|$)'
            matches = re.findall(comment_pattern, column_definition, re.MULTILINE)
            
            if matches:
                # Convert matches to dictionary
                metadata = {}
                for key, value in matches:
                    # Clean up key and value
                    clean_key = key.strip()
                    clean_value = value.strip()
                    metadata[clean_key] = clean_value
                return metadata
            else:
                return {}
                
        except Exception as e:
            logger.warning(f"Could not extract metadata from column definition: {str(e)}")
            return {}
    
    def _create_clean_column_definition(self, column_definition: str) -> str:
        """
        Create a clean column definition with only the column name (data type moved to comments).
        
        Args:
            column_definition: Column definition string that may contain key-value comments
            
        Returns:
            Clean column definition with only column name
        """
        import re
        
        try:
            # Extract just the column name from the definition
            # Look for the pattern: "column_name DATATYPE ..."
            match = re.search(r'(\w+)\s+\w+', column_definition)
            if match:
                column_name = match.group(1)
                return column_name
            else:
                # Fallback: try to extract any word that's not a comment
                lines = column_definition.split('\n')
                for line in lines:
                    stripped_line = line.strip()
                    # Skip comment lines
                    if not stripped_line.startswith('--'):
                        # Extract first word (column name)
                        words = stripped_line.split()
                        if words:
                            return words[0]
                
                return column_definition.strip()
            
        except Exception as e:
            logger.warning(f"Could not create clean column definition: {str(e)}")
            return column_definition
    
    def _create_backward_compatible_definition(self, column: Dict[str, Any], model: Dict[str, Any]) -> str:
        """
        Create backward-compatible column definition in the original format.
        
        Args:
            column: Column definition
            model: Model definition
            
        Returns:
            Backward-compatible column definition with full SQL syntax
        """
        try:
            column_name = column.get("name", "")
            column_type = column.get("type", "")
            not_null = "NOT NULL" if column.get("notNull", False) else ""
            primary_key = "PRIMARY KEY" if column.get("name") == model.get("primaryKey", "") else ""
            
            # Build the basic column definition
            definition_parts = [column_name, column_type]
            if not_null:
                definition_parts.append(not_null)
            if primary_key:
                definition_parts.append(primary_key)
            
            # Create the full SQL definition
            sql_definition = " ".join(definition_parts)
            
            # Add comments using the helper functionality
            from app.indexing.utils.helper import COLUMN_COMMENT_HELPERS
            
            comments = []
            for helper_name, helper in COLUMN_COMMENT_HELPERS.items():
                if helper.condition(column, model=model):
                    comment = helper.helper(column, model=model)
                    if comment:
                        comments.append(comment)
            
            # Combine definition and comments
            if comments:
                return "\n  ".join(comments) + sql_definition
            else:
                return sql_definition
                
        except Exception as e:
            logger.error(f"Error creating backward-compatible column definition: {str(e)}")
            # Fallback to basic definition
            return f"{column.get('name', '')} {column.get('type', '')}"
    
    def _build_enhanced_column_comment(self, column: Dict[str, Any], model: Dict[str, Any]) -> str:
        """
        Build enhanced column comment with key-value properties.
        
        Args:
            column: Column definition
            model: Model definition
            
        Returns:
            Enhanced comment string with key-value properties
        """
        try:
            from app.indexing.utils.helper import COLUMN_COMMENT_HELPERS
            
            # Get properties from column
            props = column.get("properties", {})
            
            # Add data type as a property
            props["datatype"] = column.get("type", "")
            
            # Add field type classification
            props["field_type"] = self._determine_field_type(column, model)
            
            # Filter out empty values
            meaningful_properties = {k: v for k, v in props.items() if v}
            
            if not meaningful_properties:
                return ""
            
            # Create simple key-value comment format
            comment_lines = []
            for key, value in meaningful_properties.items():
                comment_lines.append(f"-- {key}: {value}")
            
            return "\n  ".join(comment_lines) + "\n  "
            
        except Exception as e:
            logger.error(f"Error building enhanced column comment: {str(e)}")
            return ""
    
    def _classify_table_field_types(self, columns: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Classify table field types for better search and query building.
        
        Args:
            columns: List of enhanced column definitions
            
        Returns:
            Dictionary with field type classifications
        """
        try:
            classification = {
                "dimensions": [],
                "facts": [],
                "identifiers": [],
                "timestamps": [],
                "calculated": []
            }
            
            for column in columns:
                field_type = column.get("field_type", "dimension")
                column_name = column.get("name", "")
                
                if field_type == "dimension":
                    classification["dimensions"].append(column_name)
                elif field_type == "fact":
                    classification["facts"].append(column_name)
                elif field_type == "identifier":
                    classification["identifiers"].append(column_name)
                elif field_type == "timestamp":
                    classification["timestamps"].append(column_name)
                elif field_type == "calculated":
                    classification["calculated"].append(column_name)
            
            return classification
            
        except Exception as e:
            logger.error(f"Error classifying table field types: {str(e)}")
            return {"dimensions": [], "facts": [], "identifiers": [], "timestamps": [], "calculated": []}
    
    def _build_ddl_ready_columns(self, enhanced_columns: List[Dict[str, Any]], model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build DDL-ready column information for the retrieval pipeline.
        
        Args:
            enhanced_columns: List of enhanced column definitions
            model: Model definition
            
        Returns:
            List of DDL-ready column information
        """
        try:
            ddl_columns = []
            
            for column in enhanced_columns:
                # Build DDL-ready column definition
                column_definition = self._build_column_definition_with_comments(column, model)
                extracted_metadata = self._extract_json_metadata_from_definition(column_definition)
                clean_column_definition = self._create_clean_column_definition(column_definition)
                backward_compatible_definition = self._create_backward_compatible_definition(column, model)
                
                ddl_column = {
                    "column_name": column.get("name", ""),
                    "data_type": column.get("type", ""),
                    "is_primary_key": column.get("is_primary_key", False),
                    "is_nullable": column.get("is_nullable", True),
                    "is_calculated": column.get("is_calculated", False),
                    "expression": column.get("expression", ""),
                    "field_type": column.get("field_type", "dimension"),
                    
                    # DDL generation fields
                    "column_definition": backward_compatible_definition,  # Full SQL with comments
                    "clean_column_definition": clean_column_definition,  # Column name only
                    "extracted_metadata": extracted_metadata,  # Key-value pairs
                    
                    # Business context
                    "display_name": column.get("display_name", ""),
                    "business_description": column.get("business_description", ""),
                    "business_purpose": column.get("business_purpose", ""),
                    "usage_type": column.get("usage_type", ""),
                    "privacy_classification": column.get("privacy_classification", ""),
                    
                    # Technical context
                    "comments": column.get("comments", ""),
                    "business_keywords": column.get("business_keywords", []),
                    "technical_keywords": column.get("technical_keywords", []),
                    "searchable_text": column.get("searchable_text", ""),
                    
                    # Enhanced properties
                    "dimension_fact_classification": column.get("dimension_fact_classification", ""),
                    "query_building_hints": column.get("query_building_hints", {}),
                    "properties": column.get("properties", {})
                }
                
                ddl_columns.append(ddl_column)
            
            return ddl_columns
            
        except Exception as e:
            logger.error(f"Error building DDL-ready columns: {str(e)}")
            return []
    
    def _build_comprehensive_table_description(self, model: Dict[str, Any], enhanced_columns: List[Dict[str, Any]], properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build comprehensive table description for retrieval pipeline.
        
        Args:
            model: Model definition
            enhanced_columns: List of enhanced column definitions
            properties: Table properties
            
        Returns:
            Comprehensive table description
        """
        try:
            table_name = model.get("name", "")
            primary_key = model.get("primaryKey", "")
            
            # Build column summaries
            column_summaries = []
            for column in enhanced_columns:
                column_summary = {
                    "name": column.get("name", ""),
                    "type": column.get("type", ""),
                    "is_primary_key": column.get("is_primary_key", False),
                    "is_calculated": column.get("is_calculated", False),
                    "field_type": column.get("field_type", "dimension"),
                    "display_name": column.get("display_name", ""),
                    "business_description": column.get("business_description", ""),
                    "usage_type": column.get("usage_type", "")
                }
                column_summaries.append(column_summary)
            
            # Build comprehensive description
            table_description = {
                "table_name": table_name,
                "display_name": properties.get("displayName", ""),
                "description": properties.get("description", ""),
                "business_purpose": properties.get("businessPurpose", ""),
                "primary_key": primary_key,
                "column_count": len(enhanced_columns),
                "calculated_column_count": len([c for c in enhanced_columns if c.get("is_calculated", False)]),
                "dimension_columns": [c["name"] for c in enhanced_columns if c.get("field_type") == "dimension"],
                "fact_columns": [c["name"] for c in enhanced_columns if c.get("field_type") == "fact"],
                "identifier_columns": [c["name"] for c in enhanced_columns if c.get("field_type") == "identifier"],
                "timestamp_columns": [c["name"] for c in enhanced_columns if c.get("field_type") == "timestamp"],
                "calculated_columns": [c["name"] for c in enhanced_columns if c.get("is_calculated", False)],
                "column_summaries": column_summaries,
                "business_domain": properties.get("domain", ""),
                "classification": properties.get("classification", "internal"),
                "tags": properties.get("tags", []),
                "business_rules": properties.get("businessRules", []),
                "usage_guidelines": properties.get("usageGuidelines", [])
            }
            
            return table_description
            
        except Exception as e:
            logger.error(f"Error building comprehensive table description: {str(e)}")
            return {}
    
    async def _build_table_document(
        self,
        model: Dict[str, Any],
        mdl: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Build a comprehensive TABLE_DOCUMENT."""
        
        table_name = model.get("name", "")
        properties = model.get("properties", {})
        
        # Extract relationships for this table
        relationships = self._extract_table_relationships(table_name, mdl.get("relationships", []))
        
        # Enhance columns with business context
        enhanced_columns = await self._enhance_columns_with_business_context(
            model.get("columns", []), model
        )
        
        # Extract constraints
        constraints = self._extract_constraints(model)
        
        # Create searchable text content
        searchable_text = self._create_searchable_text(model, enhanced_columns, relationships)
        
        # Extract keywords for search optimization
        business_keywords = self._extract_business_keywords(model, enhanced_columns)
        technical_keywords = self._extract_technical_keywords(model, enhanced_columns)
        
        # Build table document aligned with existing structure
        table_document = {
            "type": "TABLE_SCHEMA",
            "name": table_name,
            "project_id": project_id,
            
            # Basic table information (aligned with existing structure)
            "primaryKey": model.get("primaryKey", ""),
            "properties": properties,
            "columns": enhanced_columns,
            "relationships": relationships,
            
            # DDL-ready column information for retrieval pipeline
            "table_columns": self._build_ddl_ready_columns(enhanced_columns, model),
            
            # Comprehensive table description for retrieval
            "table_description": self._build_comprehensive_table_description(model, enhanced_columns, properties),
            
            # Enhanced properties for better search and classification
            "display_name": properties.get("displayName", ""),
            "description": properties.get("description", ""),
            "business_purpose": properties.get("businessPurpose", ""),
            "field_type_classification": self._classify_table_field_types(enhanced_columns),
            "searchable_text": searchable_text,
            "tags": properties.get("tags", []),
            "classification": properties.get("classification", "internal"),
            "domain": properties.get("domain", ""),
            
            # Search optimization
            "searchable_text": searchable_text,
            "business_keywords": business_keywords,
            "technical_keywords": technical_keywords,
            
            # Timestamps
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        logger.info(f"Table document: {json.dumps(table_document, indent=2)}")
        
        return table_document
    
    async def _enhance_columns_with_business_context(
        self,
        columns: List[Dict[str, Any]],
        model: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance columns with comprehensive business context."""
        enhanced_columns = []
        
        for column in columns:
            if column.get("isHidden", False):
                continue
            
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
                "notNull": column.get("notNull", False),
                # New field type for dimensions vs facts
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
            
            # Add comprehensive business context
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
                    "filtering_suggestions": properties.get("filteringSuggestions", []),
                    "related_concepts": properties.get("relatedConcepts", []),
                    "validation_rules": properties.get("validationRules", []),
                    "usage_guidelines": properties.get("usageGuidelines", []),
                    "business_examples": properties.get("businessExamples", []),
                    "data_lineage": properties.get("dataLineage", ""),
                    "source_system": properties.get("sourceSystem", ""),
                    "update_frequency": properties.get("updateFrequency", ""),
                    "data_steward": properties.get("dataSteward", ""),
                    "business_owner": properties.get("businessOwner", ""),
                    # Enhanced field type information
                    "dimension_fact_classification": self._classify_dimension_fact(enhanced_column),
                    "query_building_hints": self._generate_query_building_hints(enhanced_column)
                })
            
            # Create searchable text for this column
            column_searchable_text = self._create_column_searchable_text(enhanced_column)
            enhanced_column["searchable_text"] = column_searchable_text
            
            # Extract keywords for this column
            enhanced_column["business_keywords"] = self._extract_column_business_keywords(enhanced_column)
            enhanced_column["technical_keywords"] = self._extract_column_technical_keywords(enhanced_column)
            
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
                enhanced_relationship = {
                    "name": relationship.get("name", ""),
                    "models": models_in_relationship,
                    "joinType": relationship.get("joinType", ""),
                    "condition": relationship.get("condition", ""),
                    "properties": relationship.get("properties", {}),
                    "business_purpose": relationship.get("properties", {}).get("businessPurpose", ""),
                    "description": relationship.get("properties", {}).get("description", ""),
                    "usage_guidelines": relationship.get("properties", {}).get("usageGuidelines", [])
                }
                table_relationships.append(enhanced_relationship)
        
        return table_relationships
    
    def _extract_constraints(self, model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract constraints from model definition."""
        constraints = []
        
        # Add primary key constraint
        if model.get("primaryKey"):
            constraints.append({
                "type": "PRIMARY_KEY",
                "column": model["primaryKey"],
                "name": f"pk_{model['name']}",
                "description": f"Primary key constraint on {model['primaryKey']}"
            })
        
        # Add other constraints if available
        if "constraints" in model:
            for constraint in model["constraints"]:
                enhanced_constraint = {
                    "type": constraint.get("type", ""),
                    "name": constraint.get("name", ""),
                    "description": constraint.get("description", ""),
                    "columns": constraint.get("columns", []),
                    "condition": constraint.get("condition", ""),
                    "business_purpose": constraint.get("businessPurpose", "")
                }
                constraints.append(enhanced_constraint)
        
        return constraints
    
    def _create_searchable_text(
        self,
        model: Dict[str, Any],
        columns: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> str:
        """Create comprehensive searchable text for the table."""
        searchable_parts = []
        
        # Table information
        properties = model.get("properties", {})
        searchable_parts.extend([
            f"Table: {model.get('name', '')}",
            f"Display Name: {properties.get('displayName', '')}",
            f"Description: {properties.get('description', '')}",
            f"Business Purpose: {properties.get('businessPurpose', '')}",
            f"Domain: {properties.get('domain', '')}",
            f"Classification: {properties.get('classification', '')}"
        ])
        
        # Business rules and guidelines
        business_rules = properties.get("businessRules", [])
        for rule in business_rules:
            searchable_parts.append(f"Business Rule: {rule}")
        
        usage_guidelines = properties.get("usageGuidelines", [])
        for guideline in usage_guidelines:
            searchable_parts.append(f"Usage Guideline: {guideline}")
        
        # Column information
        for column in columns:
            searchable_parts.extend([
                f"Column: {column.get('name', '')}",
                f"Display Name: {column.get('display_name', '')}",
                f"Description: {column.get('business_description', '')}",
                f"Business Purpose: {column.get('business_purpose', '')}",
                f"Usage Type: {column.get('usage_type', '')}",
                f"Privacy Classification: {column.get('privacy_classification', '')}"
            ])
            
            # Column business rules
            column_rules = column.get("business_rules", [])
            for rule in column_rules:
                searchable_parts.append(f"Column Business Rule: {rule}")
            
            # Column usage guidelines
            column_guidelines = column.get("usage_guidelines", [])
            for guideline in column_guidelines:
                searchable_parts.append(f"Column Usage Guideline: {guideline}")
        
        # Relationship information
        for relationship in relationships:
            searchable_parts.extend([
                f"Relationship: {relationship.get('name', '')}",
                f"Description: {relationship.get('description', '')}",
                f"Business Purpose: {relationship.get('business_purpose', '')}",
                f"Join Type: {relationship.get('joinType', '')}"
            ])
        
        return " ".join(searchable_parts)
    
    def _create_column_searchable_text(self, column: Dict[str, Any]) -> str:
        """Create searchable text for a specific column."""
        searchable_parts = [
            f"Column: {column.get('name', '')}",
            f"Display Name: {column.get('display_name', '')}",
            f"Description: {column.get('business_description', '')}",
            f"Business Purpose: {column.get('business_purpose', '')}",
            f"Usage Type: {column.get('usage_type', '')}",
            f"Data Type: {column.get('data_type', '')}",
            f"Privacy Classification: {column.get('privacy_classification', '')}"
        ]
        
        # Add business rules
        business_rules = column.get("business_rules", [])
        for rule in business_rules:
            searchable_parts.append(f"Business Rule: {rule}")
        
        # Add usage guidelines
        usage_guidelines = column.get("usage_guidelines", [])
        for guideline in usage_guidelines:
            searchable_parts.append(f"Usage Guideline: {guideline}")
        
        # Add example values
        example_values = column.get("example_values", [])
        for example in example_values:
            searchable_parts.append(f"Example: {example}")
        
        return " ".join(searchable_parts)
    
    def _extract_business_keywords(
        self,
        model: Dict[str, Any],
        columns: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract business keywords for search optimization."""
        keywords = set()
        
        # Table-level keywords
        properties = model.get("properties", {})
        keywords.update([
            properties.get("displayName", ""),
            properties.get("domain", ""),
            properties.get("classification", "")
        ])
        
        # Add tags
        tags = properties.get("tags", [])
        keywords.update(tags)
        
        # Column-level keywords
        for column in columns:
            keywords.update([
                column.get("display_name", ""),
                column.get("usage_type", ""),
                column.get("privacy_classification", "")
            ])
            
            # Add related concepts
            related_concepts = column.get("related_concepts", [])
            keywords.update(related_concepts)
        
        # Filter out empty strings
        return [kw for kw in keywords if kw]
    
    def _extract_technical_keywords(
        self,
        model: Dict[str, Any],
        columns: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract technical keywords for search optimization."""
        keywords = set()
        
        # Table technical info
        keywords.add(model.get("name", ""))
        keywords.add(model.get("primaryKey", ""))
        
        # Column technical info
        for column in columns:
            keywords.update([
                column.get("name", ""),
                column.get("data_type", ""),
                column.get("type", "")
            ])
            
            # Add relationship info
            if column.get("relationship"):
                keywords.add("foreign_key")
                keywords.add("relationship")
        
        # Filter out empty strings
        return [kw for kw in keywords if kw]
    
    def _extract_column_business_keywords(self, column: Dict[str, Any]) -> List[str]:
        """Extract business keywords for a specific column."""
        keywords = set()
        
        keywords.update([
            column.get("display_name", ""),
            column.get("usage_type", ""),
            column.get("privacy_classification", "")
        ])
        
        # Add related concepts
        related_concepts = column.get("related_concepts", [])
        keywords.update(related_concepts)
        
        # Filter out empty strings
        return [kw for kw in keywords if kw]
    
    def _extract_column_technical_keywords(self, column: Dict[str, Any]) -> List[str]:
        """Extract technical keywords for a specific column."""
        keywords = set()
        
        keywords.update([
            column.get("name", ""),
            column.get("data_type", ""),
            column.get("type", "")
        ])
        
        if column.get("is_primary_key"):
            keywords.add("primary_key")
        
        if column.get("is_calculated"):
            keywords.add("calculated")
        
        if column.get("relationship"):
            keywords.add("foreign_key")
        
        # Filter out empty strings
        return [kw for kw in keywords if kw]
    
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
    
    def _classify_dimension_fact(self, column: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide detailed classification of dimension vs fact for query building.
        
        Args:
            column: Enhanced column definition
            
        Returns:
            Dictionary with dimension/fact classification details
        """
        field_type = column.get("field_type", "dimension")
        column_name = column.get("name", "")
        data_type = column.get("data_type", "")
        usage_type = column.get("usage_type", "")
        
        classification = {
            "field_type": field_type,
            "is_dimension": field_type == "dimension",
            "is_fact": field_type == "fact",
            "is_identifier": field_type == "identifier",
            "is_timestamp": field_type == "timestamp",
            "is_calculated": field_type == "fact" and column.get("is_calculated", False),
            "query_usage": self._get_query_usage_hints(field_type, column),
            "aggregation_suitable": field_type == "fact",
            "filter_suitable": field_type in ["dimension", "identifier", "timestamp"],
            "group_by_suitable": field_type in ["dimension", "identifier", "timestamp"],
            "join_suitable": field_type == "identifier"
        }
        
        return classification
    
    def _get_query_usage_hints(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """
        Get query usage hints based on field type.
        
        Args:
            field_type: The determined field type
            column: Column definition
            
        Returns:
            List of query usage hints
        """
        hints = []
        
        if field_type == "fact":
            hints.extend([
                "Use in SELECT with aggregation functions (SUM, COUNT, AVG, MAX, MIN)",
                "Suitable for GROUP BY with dimension columns",
                "Can be used in HAVING clauses for filtering aggregated results",
                "Good for analytical queries and reporting"
            ])
        elif field_type == "dimension":
            hints.extend([
                "Use in SELECT for descriptive information",
                "Suitable for WHERE clauses for filtering",
                "Good for GROUP BY to create categories",
                "Can be used in JOIN conditions with identifier columns"
            ])
        elif field_type == "identifier":
            hints.extend([
                "Use in JOIN conditions to link tables",
                "Suitable for WHERE clauses for exact matches",
                "Good for primary key lookups",
                "Can be used in GROUP BY for unique groupings"
            ])
        elif field_type == "timestamp":
            hints.extend([
                "Use in WHERE clauses for date range filtering",
                "Suitable for ORDER BY for chronological sorting",
                "Good for date-based GROUP BY (YEAR, MONTH, DAY)",
                "Can be used in date functions (DATE_TRUNC, EXTRACT)"
            ])
        
        return hints
    
    def _generate_query_building_hints(self, column: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive query building hints for a column.
        
        Args:
            column: Enhanced column definition
            
        Returns:
            Dictionary with query building hints
        """
        field_type = column.get("field_type", "dimension")
        column_name = column.get("name", "")
        data_type = column.get("data_type", "")
        
        hints = {
            "field_type": field_type,
            "sql_suggestions": self._get_sql_suggestions(field_type, column),
            "aggregation_functions": self._get_aggregation_suggestions(field_type, data_type),
            "filter_operators": self._get_filter_operators(field_type, data_type),
            "join_conditions": self._get_join_suggestions(field_type, column),
            "indexing_suggestions": self._get_indexing_suggestions(field_type, column),
            "performance_considerations": self._get_performance_considerations(field_type, column)
        }
        
        return hints
    
    def _get_sql_suggestions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get SQL usage suggestions for a column."""
        suggestions = []
        
        if field_type == "fact":
            suggestions.extend([
                f"SELECT SUM({column.get('name')}) FROM table_name",
                f"SELECT COUNT({column.get('name')}) FROM table_name",
                f"SELECT AVG({column.get('name')}) FROM table_name",
                f"GROUP BY dimension_column HAVING SUM({column.get('name')}) > threshold"
            ])
        elif field_type == "dimension":
            suggestions.extend([
                f"SELECT {column.get('name')} FROM table_name",
                f"WHERE {column.get('name')} = 'value'",
                f"GROUP BY {column.get('name')}",
                f"ORDER BY {column.get('name')}"
            ])
        elif field_type == "identifier":
            suggestions.extend([
                f"JOIN table1 ON table1.{column.get('name')} = table2.{column.get('name')}",
                f"WHERE {column.get('name')} = 'specific_id'",
                f"SELECT * FROM table_name WHERE {column.get('name')} IN (id1, id2, id3)"
            ])
        elif field_type == "timestamp":
            suggestions.extend([
                f"WHERE {column.get('name')} >= '2023-01-01'",
                f"GROUP BY DATE_TRUNC('month', {column.get('name')})",
                f"ORDER BY {column.get('name')} DESC",
                f"WHERE {column.get('name')} BETWEEN 'start_date' AND 'end_date'"
            ])
        
        return suggestions
    
    def _get_aggregation_suggestions(self, field_type: str, data_type: str) -> List[str]:
        """Get aggregation function suggestions."""
        if field_type == "fact":
            if data_type in ["INTEGER", "BIGINT", "DECIMAL", "FLOAT", "DOUBLE", "NUMERIC"]:
                return ["SUM", "COUNT", "AVG", "MAX", "MIN", "STDDEV", "VARIANCE"]
            else:
                return ["COUNT", "COUNT_DISTINCT"]
        else:
            return ["COUNT", "COUNT_DISTINCT"]
    
    def _get_filter_operators(self, field_type: str, data_type: str) -> List[str]:
        """Get appropriate filter operators for a column."""
        operators = ["=", "!=", "IS NULL", "IS NOT NULL"]
        
        if field_type == "fact":
            operators.extend([">", "<", ">=", "<=", "BETWEEN"])
        elif field_type == "dimension":
            operators.extend(["LIKE", "ILIKE", "IN", "NOT IN"])
        elif field_type == "timestamp":
            operators.extend([">", "<", ">=", "<=", "BETWEEN", "DATE_TRUNC"])
        
        return operators
    
    def _get_join_suggestions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get join condition suggestions."""
        if field_type == "identifier":
            return [
                f"Use {column.get('name')} as foreign key in JOIN conditions",
                f"Create indexes on {column.get('name')} for better join performance",
                f"Consider composite keys if multiple identifier columns exist"
            ]
        else:
            return ["Not typically used in JOIN conditions"]
    
    def _get_indexing_suggestions(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get indexing suggestions for a column."""
        suggestions = []
        
        if field_type == "identifier":
            suggestions.append(f"Create primary key or unique index on {column.get('name')}")
        elif field_type == "dimension":
            suggestions.append(f"Consider index on {column.get('name')} for frequent filtering")
        elif field_type == "timestamp":
            suggestions.append(f"Create index on {column.get('name')} for date range queries")
        elif field_type == "fact":
            suggestions.append(f"Consider composite indexes with dimension columns for {column.get('name')}")
        
        return suggestions
    
    def _get_performance_considerations(self, field_type: str, column: Dict[str, Any]) -> List[str]:
        """Get performance considerations for a column."""
        considerations = []
        
        if field_type == "fact":
            considerations.extend([
                "Use appropriate aggregation functions for better performance",
                "Consider materialized views for frequently aggregated data",
                "Use columnar storage for analytical workloads"
            ])
        elif field_type == "dimension":
            considerations.extend([
                "Use appropriate data types to minimize storage",
                "Consider denormalization for frequently accessed dimensions",
                "Use bitmap indexes for low-cardinality dimensions"
            ])
        elif field_type == "identifier":
            considerations.extend([
                "Use integer types for better join performance",
                "Consider surrogate keys for better performance",
                "Ensure proper indexing for foreign key relationships"
            ])
        elif field_type == "timestamp":
            considerations.extend([
                "Use appropriate timestamp data types",
                "Consider partitioning by date ranges",
                "Use date functions efficiently in queries"
            ])
        
        return considerations
    
    def _extract_column_business_context(self, column: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business context for a column."""
        business_context = {
            "business_purpose": column.get("business_purpose", ""),
            "business_rules": column.get("business_rules", []),
            "data_governance": column.get("data_governance", {}),
            "compliance_requirements": column.get("compliance_requirements", []),
            "sensitivity_level": column.get("sensitivity_level", "standard"),
            "data_quality_rules": column.get("data_quality_rules", []),
            "business_owner": column.get("business_owner", ""),
            "steward": column.get("steward", ""),
            "usage_guidelines": column.get("usage_guidelines", []),
            "retention_policy": column.get("retention_policy", "")
        }
        
        # Clean up empty values
        return {k: v for k, v in business_context.items() if v}
    
    def _extract_column_technical_context(self, column: Dict[str, Any]) -> Dict[str, Any]:
        """Extract technical context for a column."""
        technical_context = {
            "data_type": column.get("data_type", ""),
            "nullable": column.get("nullable", False),
            "default_value": column.get("default_value"),
            "constraints": column.get("constraints", []),
            "indexes": column.get("indexes", []),
            "foreign_keys": column.get("foreign_keys", []),
            "performance_notes": column.get("performance_notes", []),
            "storage_requirements": column.get("storage_requirements", ""),
            "computation_complexity": column.get("computation_complexity", "low"),
            "access_patterns": column.get("access_patterns", [])
        }
        
        # Clean up empty values
        return {k: v for k, v in technical_context.items() if v}
    
    def _create_column_searchable_text(self, column: Dict[str, Any]) -> str:
        """Create searchable text for a specific column."""
        searchable_parts = [
            f"Column: {column.get('name', '')}",
            f"Type: {column.get('data_type', '')}",
            f"Purpose: {column.get('business_purpose', '')}",
            f"Description: {column.get('description', '')}",
            f"Field Type: {column.get('field_type', '')}",
            f"Business Rules: {' '.join(column.get('business_rules', []))}",
            f"Usage Guidelines: {' '.join(column.get('usage_guidelines', []))}"
        ]
        
        # Add properties if available
        properties = column.get("properties", {})
        if properties:
            for key, value in properties.items():
                if isinstance(value, str):
                    searchable_parts.append(f"{key}: {value}")
                elif isinstance(value, list):
                    searchable_parts.append(f"{key}: {' '.join(str(v) for v in value)}")
        
        return " ".join(filter(None, searchable_parts))
