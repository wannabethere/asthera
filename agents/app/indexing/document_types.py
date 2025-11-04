"""
Document Types Enum for ChromaDB Indexing System

This module defines all the document types used in the ChromaDB indexing system
with detailed comments explaining their purpose and usage.
"""

from enum import Enum
from typing import Dict, Any


class DocumentType(Enum):
    """
    Enumeration of all document types used in the ChromaDB indexing system.
    
    These types are used in two contexts:
    1. As metadata.type for ChromaDB document classification
    2. As content.type within the page_content payload
    
    ARCHITECTURE PRINCIPLE:
    - SCHEMA_DOCUMENT: Technical structure (tables, columns, relationships)
    - DESCRIPTION_DOCUMENT: Business context (descriptions, metadata)
    - This eliminates duplication between TABLE and TABLE_SCHEMA
    """
    
    # =============================================================================
    # METADATA TYPES (used in ChromaDB metadata.type field)
    # =============================================================================
    
    SCHEMA_DOCUMENT = "SCHEMA_DOCUMENT"
    """
    Metadata type for technical schema documents.
    
    Contains technical database structure information:
    - Table definitions (TABLE_DEFINITION content)
    - Column definitions (TABLE_COLUMNS content)
    - Foreign key relationships (FOREIGN_KEY content)
    - View definitions (VIEW content)
    - Metric definitions (METRIC content)
    
    This replaces the old TABLE_SCHEMA type and eliminates
    duplication with TABLE_DESCRIPTION documents.
    """
    
    DESCRIPTION_DOCUMENT = "DESCRIPTION_DOCUMENT"
    """
    Metadata type for business description documents.
    
    Contains business context and human-readable information:
    - Table descriptions (TABLE_DESCRIPTION content)
    - Column descriptions (COLUMN_DESCRIPTION content)
    - Business metadata and context
    
    This replaces the old TABLE_DESCRIPTION type and provides
    clear separation from technical schema documents.
    """
    
    # =============================================================================
    # CONTENT TYPES (used within page_content payload)
    # =============================================================================
    
    TABLE_DEFINITION = "TABLE_DEFINITION"
    """
    Content type for technical table structure.
    
    Contains technical table information:
    - Table name and structure
    - Primary key information
    - Table constraints
    - Technical properties
    
    Example structure:
    {
        "type": "TABLE_DEFINITION",
        "name": "users",
        "primary_key": "user_id",
        "constraints": [...],
        "technical_properties": {...}
    }
    """
    
    TABLE_DESCRIPTION = "TABLE_DESCRIPTION"
    """
    Content type for business table descriptions.
    
    Contains business context and descriptions:
    - Business purpose and description
    - Display name and alias
    - Business rules and context
    - Usage guidelines
    
    Example structure:
    {
        "type": "TABLE_DESCRIPTION",
        "name": "users",
        "display_name": "User Accounts",
        "description": "Stores user account information",
        "business_purpose": "User management and authentication"
    }
    """
    
    COLUMN = "COLUMN"
    """
    Content type for technical column structure.
    
    Contains technical column information:
    - Column name and data type
    - Technical constraints and properties
    - MDL properties (isCalculated, expression, relationship)
    - Primary key status
    - Nullable status
    
    Example structure:
    {
        "type": "COLUMN",
        "name": "user_id",
        "data_type": "VARCHAR",
        "is_primary_key": true,
        "isCalculated": false,
        "expression": "",
        "relationship": {...}
    }
    """
    
    COLUMN_DESCRIPTION = "COLUMN_DESCRIPTION"
    """
    Content type for business column descriptions.
    
    Contains business context for columns:
    - Business description and purpose
    - Display name and alias
    - Business rules and validation
    - Usage guidelines and examples
    
    Example structure:
    {
        "type": "COLUMN_DESCRIPTION",
        "name": "user_id",
        "display_name": "User Identifier",
        "description": "Unique identifier for user accounts",
        "business_purpose": "Primary key for user management"
    }
    """
    
    TABLE_COLUMNS = "TABLE_COLUMNS"
    """
    Content type for batched column information.
    
    Groups multiple COLUMN objects together for efficient storage.
    The batch size is controlled by column_batch_size parameter (default: 200).
    
    Contains:
    - Array of COLUMN objects
    - Used to reduce the number of documents while maintaining
      efficient retrieval of column information
    
    Example structure:
    {
        "type": "TABLE_COLUMNS",
        "columns": [
            { /* COLUMN object 1 */ },
            { /* COLUMN object 2 */ },
            ...
        ]
    }
    """
    
    FOREIGN_KEY = "FOREIGN_KEY"
    """
    Content type for foreign key relationships.
    
    Contains:
    - Foreign key constraint definition
    - Related table information
    - Join type and condition
    - Relationship metadata
    
    Example structure:
    {
        "type": "FOREIGN_KEY",
        "comment": "-- {'condition': 'users.id = orders.user_id', 'joinType': 'ONE_TO_MANY'}",
        "constraint": "FOREIGN KEY (user_id) REFERENCES users(id)",
        "tables": ["orders", "users"]
    }
    """
    
    VIEW = "VIEW"
    """
    Content type for database views.
    
    Contains:
    - View name
    - SQL statement
    - View properties and comments
    
    Example structure:
    {
        "type": "VIEW",
        "comment": "/* {'displayName': 'Active Users', 'description': 'Currently active users'} */",
        "name": "active_users",
        "statement": "SELECT * FROM users WHERE status = 'active'"
    }
    """
    
    METRIC = "METRIC"
    """
    Content type for calculated metrics and measures.
    
    Contains:
    - Metric name and properties
    - Dimension columns (categorical data)
    - Measure columns (numeric data)
    - Business context and usage information
    
    Example structure:
    {
        "type": "METRIC",
        "comment": "/* {'displayName': 'Sales Metrics', 'description': 'Key sales performance indicators'} */",
        "name": "sales_metrics",
        "columns": [
            { /* dimension columns */ },
            { /* measure columns */ }
        ]
    }
    """
    
    # =============================================================================
    # MDL TYPES (used in table_description.py for mdl_type field)
    # =============================================================================
    
    TABLE_SCHEMA_MDL = "TABLE_SCHEMA"
    """
    MDL type for table schema definitions.
    
    Used in table_description.py to identify that a resource
    came from the 'models' section of the MDL.
    """
    
    METRIC_MDL = "METRIC"
    """
    MDL type for metric definitions.
    
    Used in table_description.py to identify that a resource
    came from the 'metrics' section of the MDL.
    """
    
    VIEW_MDL = "VIEW"
    """
    MDL type for view definitions.
    
    Used in table_description.py to identify that a resource
    came from the 'views' section of the MDL.
    """


class DocumentTypeUsage:
    """
    Helper class to understand how document types are used in the system.
    """
    
    @staticmethod
    def get_metadata_types() -> Dict[str, str]:
        """
        Get all metadata types used in ChromaDB metadata.type field.
        
        Returns:
            Dict mapping type names to descriptions
        """
        return {
            DocumentType.SCHEMA_DOCUMENT.value: "Technical schema documents (structure, columns, relationships)",
            DocumentType.DESCRIPTION_DOCUMENT.value: "Business description documents (context, metadata)"
        }
    
    @staticmethod
    def get_migration_mapping() -> Dict[str, str]:
        """
        Get mapping from old types to new types for migration.
        
        Returns:
            Dict mapping old type names to new type names
        """
        return {
            # Old metadata types -> New metadata types
            "TABLE_SCHEMA": DocumentType.SCHEMA_DOCUMENT.value,
            "TABLE_DESCRIPTION": DocumentType.DESCRIPTION_DOCUMENT.value,
            
            # Old content types -> New content types
            "TABLE": DocumentType.TABLE_DEFINITION.value,  # Technical structure
            "COLUMN": DocumentType.COLUMN.value,  # Technical structure (unchanged)
            "TABLE_COLUMNS": DocumentType.TABLE_COLUMNS.value,  # Unchanged
            "FOREIGN_KEY": DocumentType.FOREIGN_KEY.value,  # Unchanged
            "VIEW": DocumentType.VIEW.value,  # Unchanged
            "METRIC": DocumentType.METRIC.value,  # Unchanged
        }
    
    @staticmethod
    def get_content_types() -> Dict[str, str]:
        """
        Get all content types used within page_content payloads.
        
        Returns:
            Dict mapping type names to descriptions
        """
        return {
            # Technical structure types
            DocumentType.TABLE_DEFINITION.value: "Technical table structure and constraints",
            DocumentType.COLUMN.value: "Technical column definitions",
            DocumentType.TABLE_COLUMNS.value: "Batched technical column information",
            DocumentType.FOREIGN_KEY.value: "Foreign key relationship definitions",
            DocumentType.VIEW.value: "Database view definitions",
            DocumentType.METRIC.value: "Calculated metrics and measures",
            
            # Business description types
            DocumentType.TABLE_DESCRIPTION.value: "Business table descriptions and context",
            DocumentType.COLUMN_DESCRIPTION.value: "Business column descriptions and context"
        }
    
    @staticmethod
    def get_mdl_types() -> Dict[str, str]:
        """
        Get all MDL types used in table descriptions.
        
        Returns:
            Dict mapping type names to descriptions
        """
        return {
            DocumentType.TABLE_SCHEMA_MDL.value: "Table schema from MDL models",
            DocumentType.METRIC_MDL.value: "Metrics from MDL metrics",
            DocumentType.VIEW_MDL.value: "Views from MDL views"
        }
    
    @staticmethod
    def get_retrieval_queries() -> Dict[str, str]:
        """
        Get common retrieval query patterns for each type.
        
        Returns:
            Dict mapping query patterns to descriptions
        """
        return {
            # New unified architecture
            "SCHEMA_DOCUMENT documents": "where={'type': 'SCHEMA_DOCUMENT', 'name': {'$in': table_names}}",
            "DESCRIPTION_DOCUMENT documents": "where={'type': 'DESCRIPTION_DOCUMENT', 'name': table_name}",
            
            # Content type queries
            "TABLE_DEFINITION content": "Look for content.type == 'TABLE_DEFINITION' within SCHEMA_DOCUMENT documents",
            "TABLE_DESCRIPTION content": "Look for content.type == 'TABLE_DESCRIPTION' within DESCRIPTION_DOCUMENT documents",
            "TABLE_COLUMNS content": "Look for content.type == 'TABLE_COLUMNS' within SCHEMA_DOCUMENT documents",
            "COLUMN_DESCRIPTION content": "Look for content.type == 'COLUMN_DESCRIPTION' within DESCRIPTION_DOCUMENT documents",
            
            # Legacy queries (for migration)
            "Legacy TABLE_SCHEMA": "where={'type': 'TABLE_SCHEMA', 'name': {'$in': table_names}}",
            "Legacy TABLE_DESCRIPTION": "where={'type': 'TABLE_DESCRIPTION', 'name': table_name}"
        }


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

def example_usage():
    """
    Example usage of the DocumentType enum.
    """
    
    # Check if a document is a schema document
    metadata_type = "TABLE_SCHEMA"
    is_schema_doc = metadata_type == DocumentType.TABLE_SCHEMA.value
    
    # Check content type within a document
    content = {"type": "TABLE_COLUMNS", "columns": [...]}
    is_column_batch = content["type"] == DocumentType.TABLE_COLUMNS.value
    
    # Get all metadata types
    metadata_types = DocumentTypeUsage.get_metadata_types()
    
    # Get all content types
    content_types = DocumentTypeUsage.get_content_types()
    
    # Get retrieval patterns
    retrieval_patterns = DocumentTypeUsage.get_retrieval_queries()
    
    return {
        "is_schema_doc": is_schema_doc,
        "is_column_batch": is_column_batch,
        "metadata_types": metadata_types,
        "content_types": content_types,
        "retrieval_patterns": retrieval_patterns
    }


if __name__ == "__main__":
    # Print all document types with their descriptions
    print("=== DOCUMENT TYPES ENUM (UNIFIED ARCHITECTURE) ===")
    print()
    
    print("METADATA TYPES (ChromaDB metadata.type):")
    for doc_type in [DocumentType.SCHEMA_DOCUMENT, DocumentType.DESCRIPTION_DOCUMENT]:
        print(f"  {doc_type.name} = '{doc_type.value}'")
        print(f"    {doc_type.__doc__.strip()}")
        print()
    
    print("TECHNICAL CONTENT TYPES (within SCHEMA_DOCUMENT):")
    for doc_type in [DocumentType.TABLE_DEFINITION, DocumentType.COLUMN, DocumentType.TABLE_COLUMNS, 
                     DocumentType.FOREIGN_KEY, DocumentType.VIEW, DocumentType.METRIC]:
        print(f"  {doc_type.name} = '{doc_type.value}'")
        print(f"    {doc_type.__doc__.strip()}")
        print()
    
    print("BUSINESS CONTENT TYPES (within DESCRIPTION_DOCUMENT):")
    for doc_type in [DocumentType.TABLE_DESCRIPTION, DocumentType.COLUMN_DESCRIPTION]:
        print(f"  {doc_type.name} = '{doc_type.value}'")
        print(f"    {doc_type.__doc__.strip()}")
        print()
    
    print("MDL TYPES:")
    for doc_type in [DocumentType.TABLE_SCHEMA_MDL, DocumentType.METRIC_MDL, DocumentType.VIEW_MDL]:
        print(f"  {doc_type.name} = '{doc_type.value}'")
        print(f"    {doc_type.__doc__.strip()}")
        print()
    
    print("=== MIGRATION MAPPING ===")
    migration = DocumentTypeUsage.get_migration_mapping()
    for old, new in migration.items():
        print(f"  '{old}' -> '{new}'")
    print()
    
    print("=== USAGE EXAMPLES ===")
    example = example_usage()
    for key, value in example.items():
        print(f"{key}: {value}")
