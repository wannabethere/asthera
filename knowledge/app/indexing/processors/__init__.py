"""
Indexing Processors
Separate classes for processing table descriptions, DB schema, domain configurations, products, compliance documents, and category mappings.
"""
from app.indexing.processors.table_description_processor import TableDescriptionProcessor
from app.indexing.processors.db_schema_processor import DBSchemaProcessor
from app.indexing.processors.domain_processor import DomainProcessor
from app.indexing.processors.product_processor import ProductProcessor
from app.indexing.processors.compliance_document_processor import ComplianceDocumentProcessor
from app.indexing.processors.category_mapping_processor import CategoryMappingProcessor

__all__ = [
    "TableDescriptionProcessor",
    "DBSchemaProcessor",
    "DomainProcessor",
    "ProductProcessor",
    "ComplianceDocumentProcessor",
    "CategoryMappingProcessor"
]

