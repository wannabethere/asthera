"""
Domain Processor
Processes and indexes domain-specific knowledge and configurations.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class DomainProcessor:
    """Processes domain-specific knowledge and configurations."""
    
    def __init__(self):
        """Initialize the Domain processor."""
        logger.info("Initializing DomainProcessor")
    
    def process_domain_config(
        self,
        domain_config: Dict[str, Any],
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process domain configuration and create documents.
        
        Args:
            domain_config: Domain configuration dictionary
            product_name: Product name
            metadata: Additional metadata
            
        Returns:
            List of Document objects
        """
        logger.info(f"Processing domain config: {domain_config.get('domain_name', 'unknown')}")
        
        documents = []
        
        # Create domain overview document
        domain_overview = {
            "domain_name": domain_config.get("domain_name", ""),
            "description": domain_config.get("description", ""),
            "metadata": domain_config.get("metadata", {})
        }
        
        domain_doc = Document(
            page_content=json.dumps(domain_overview, indent=2),
            metadata={
                "content_type": "domain_config",
                "domain": domain_config.get("domain_name", ""),
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
        documents.append(domain_doc)
        
        # Process schemas
        for schema in domain_config.get("schemas", []):
            schema_doc = self._create_schema_document(
                schema=schema,
                domain=domain_config.get("domain_name", ""),
                product_name=product_name,
                metadata=metadata
            )
            documents.append(schema_doc)
        
        # Process use cases
        for use_case in domain_config.get("use_cases", []):
            use_case_doc = self._create_use_case_document(
                use_case=use_case,
                domain=domain_config.get("domain_name", ""),
                product_name=product_name,
                metadata=metadata
            )
            documents.append(use_case_doc)
        
        logger.info(f"Created {len(documents)} documents from domain config")
        return documents
    
    def _create_schema_document(
        self,
        schema: Dict[str, Any],
        domain: str,
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Document:
        """Create a document from a schema definition."""
        schema_content = {
            "table_name": schema.get("table_name", ""),
            "description": schema.get("description", ""),
            "columns": schema.get("columns", []),
            "primary_key": schema.get("primary_key"),
            "foreign_keys": schema.get("foreign_keys", []),
            "indexes": schema.get("indexes", [])
        }
        
        return Document(
            page_content=json.dumps(schema_content, indent=2),
            metadata={
                "content_type": "domain_schema",
                "domain": domain,
                "table_name": schema.get("table_name", ""),
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
    
    def _create_use_case_document(
        self,
        use_case: Dict[str, Any],
        domain: str,
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Document:
        """Create a document from a use case definition."""
        use_case_content = {
            "name": use_case.get("name", ""),
            "description": use_case.get("description", ""),
            "example_queries": use_case.get("example_queries", []),
            "example_data": use_case.get("example_data"),
            "business_value": use_case.get("business_value", "")
        }
        
        # Create readable content
        content_parts = [
            f"Use Case: {use_case_content['name']}",
            f"\nDescription: {use_case_content['description']}",
            f"\nBusiness Value: {use_case_content['business_value'] or 'N/A'}",
            "\n\nExample Queries:"
        ]
        
        for query in use_case_content['example_queries']:
            content_parts.append(f"\n- {query}")
        
        if use_case_content.get('example_data'):
            content_parts.append(f"\n\nExample Data:\n{json.dumps(use_case_content['example_data'], indent=2)}")
        
        return Document(
            page_content="\n".join(content_parts),
            metadata={
                "content_type": "domain_use_case",
                "domain": domain,
                "use_case_name": use_case.get("name", ""),
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
    
    def process_domain_knowledge(
        self,
        knowledge: str,
        domain: str,
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Document:
        """
        Process domain knowledge text and create a document.
        
        Args:
            knowledge: Domain knowledge text
            domain: Domain name
            product_name: Product name
            metadata: Additional metadata
            
        Returns:
            Document object
        """
        logger.info(f"Processing domain knowledge for domain: {domain}")
        
        return Document(
            page_content=knowledge,
            metadata={
                "content_type": "domain_knowledge",
                "domain": domain,
                "product_name": product_name,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )

