"""
Product Processor
Processes and indexes product-specific information including purpose, docs, key concepts, and entities.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ProductProcessor:
    """Processes product-specific information and configurations."""
    
    def __init__(self):
        """Initialize the Product processor."""
        logger.info("Initializing ProductProcessor")
    
    def process_product_info(
        self,
        product_name: str,
        product_purpose: Optional[str] = None,
        product_docs_link: Optional[str] = None,
        key_concepts: Optional[List[str]] = None,
        extendable_entities: Optional[List[Dict[str, Any]]] = None,
        extendable_docs: Optional[List[Dict[str, Any]]] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process product information and create documents.
        
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
            List of Document objects
        """
        logger.info(f"Processing product information for: {product_name}")
        
        documents = []
        
        # Create product purpose document
        if product_purpose:
            purpose_doc = self._create_product_purpose_document(
                product_name=product_name,
                product_purpose=product_purpose,
                domain=domain,
                metadata=metadata
            )
            documents.append(purpose_doc)
        
        # Create product docs link document
        if product_docs_link:
            docs_link_doc = self._create_product_docs_link_document(
                product_name=product_name,
                product_docs_link=product_docs_link,
                domain=domain,
                metadata=metadata
            )
            documents.append(docs_link_doc)
        
        # Create key concepts documents
        if key_concepts:
            concepts_docs = self._create_key_concepts_documents(
                product_name=product_name,
                key_concepts=key_concepts,
                domain=domain,
                metadata=metadata
            )
            documents.extend(concepts_docs)
        
        # Create extendable entities documents
        if extendable_entities:
            entities_docs = self._create_extendable_entities_documents(
                product_name=product_name,
                extendable_entities=extendable_entities,
                domain=domain,
                metadata=metadata
            )
            documents.extend(entities_docs)
        
        # Create extendable docs documents
        if extendable_docs:
            docs_docs = self._create_extendable_docs_documents(
                product_name=product_name,
                extendable_docs=extendable_docs,
                domain=domain,
                metadata=metadata
            )
            documents.extend(docs_docs)
        
        logger.info(f"Created {len(documents)} documents for product: {product_name}")
        return documents
    
    def _create_product_purpose_document(
        self,
        product_name: str,
        product_purpose: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Document:
        """Create a document for product purpose."""
        purpose_content = {
            "product_name": product_name,
            "purpose": product_purpose,
            "description": f"{product_name} is a product that {product_purpose.lower()}"
        }
        
        return Document(
            page_content=json.dumps(purpose_content, indent=2),
            metadata={
                "content_type": "product_purpose",
                "product_name": product_name,
                "domain": domain,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
    
    def _create_product_docs_link_document(
        self,
        product_name: str,
        product_docs_link: str,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Document:
        """Create a document for product documentation link."""
        docs_content = {
            "product_name": product_name,
            "docs_link": product_docs_link,
            "description": f"Documentation for {product_name} is available at {product_docs_link}"
        }
        
        return Document(
            page_content=json.dumps(docs_content, indent=2),
            metadata={
                "content_type": "product_docs_link",
                "product_name": product_name,
                "docs_link": product_docs_link,
                "domain": domain,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
    
    def _create_key_concepts_documents(
        self,
        product_name: str,
        key_concepts: List[str],
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """Create documents for key concepts."""
        documents = []
        
        # Create a combined document with all concepts
        concepts_content = {
            "product_name": product_name,
            "key_concepts": key_concepts,
            "concepts_count": len(key_concepts),
            "description": f"Key concepts for {product_name}: {', '.join(key_concepts)}"
        }
        
        combined_doc = Document(
            page_content=json.dumps(concepts_content, indent=2),
            metadata={
                "content_type": "product_key_concepts",
                "product_name": product_name,
                "domain": domain,
                "concepts_count": len(key_concepts),
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
        documents.append(combined_doc)
        
        # Also create individual documents for each concept for better searchability
        for concept in key_concepts:
            concept_doc = Document(
                page_content=f"Key Concept: {concept}\n\nProduct: {product_name}\n\nThis is a key concept in {product_name} that users should understand.",
                metadata={
                    "content_type": "product_key_concept",
                    "product_name": product_name,
                    "concept": concept,
                    "domain": domain,
                    "indexed_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            documents.append(concept_doc)
        
        return documents
    
    def _create_extendable_entities_documents(
        self,
        product_name: str,
        extendable_entities: List[Dict[str, Any]],
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """Create documents for extendable entities."""
        documents = []
        
        for entity in extendable_entities:
            entity_name = entity.get("name", "")
            entity_type = entity.get("type", "entity")
            entity_description = entity.get("description", "")
            entity_api = entity.get("api", "")
            entity_endpoints = entity.get("endpoints", [])
            entity_examples = entity.get("examples", [])
            
            entity_content = {
                "product_name": product_name,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "description": entity_description,
                "api": entity_api,
                "endpoints": entity_endpoints,
                "examples": entity_examples
            }
            
            # Create readable content
            content_parts = [
                f"Extendable Entity: {entity_name}",
                f"Type: {entity_type}",
                f"\nDescription: {entity_description}",
            ]
            
            if entity_api:
                content_parts.append(f"\nAPI: {entity_api}")
            
            if entity_endpoints:
                content_parts.append("\nEndpoints:")
                for endpoint in entity_endpoints:
                    content_parts.append(f"  - {endpoint}")
            
            if entity_examples:
                content_parts.append("\nExamples:")
                for example in entity_examples:
                    if isinstance(example, dict):
                        content_parts.append(f"  - {json.dumps(example, indent=4)}")
                    else:
                        content_parts.append(f"  - {example}")
            
            doc = Document(
                page_content="\n".join(content_parts),
                metadata={
                    "content_type": "extendable_entity",
                    "product_name": product_name,
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "domain": domain,
                    "indexed_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            documents.append(doc)
        
        return documents
    
    def _create_extendable_docs_documents(
        self,
        product_name: str,
        extendable_docs: List[Dict[str, Any]],
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """Create documents for extendable documentation."""
        documents = []
        
        for doc_ref in extendable_docs:
            doc_title = doc_ref.get("title", "")
            doc_link = doc_ref.get("link", "")
            doc_type = doc_ref.get("type", "documentation")
            doc_description = doc_ref.get("description", "")
            doc_sections = doc_ref.get("sections", [])
            doc_content = doc_ref.get("content", "")
            
            # Create readable content
            content_parts = [
                f"Documentation: {doc_title}",
                f"Type: {doc_type}",
            ]
            
            if doc_description:
                content_parts.append(f"\nDescription: {doc_description}")
            
            if doc_link:
                content_parts.append(f"\nLink: {doc_link}")
            
            if doc_sections:
                content_parts.append("\nSections:")
                for section in doc_sections:
                    content_parts.append(f"  - {section}")
            
            if doc_content:
                content_parts.append(f"\n\nContent:\n{doc_content}")
            
            doc = Document(
                page_content="\n".join(content_parts),
                metadata={
                    "content_type": "extendable_doc",
                    "product_name": product_name,
                    "doc_title": doc_title,
                    "doc_type": doc_type,
                    "doc_link": doc_link,
                    "domain": domain,
                    "indexed_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            documents.append(doc)
        
        return documents
    
    def process_product_from_dict(
        self,
        product_data: Dict[str, Any],
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process product information from a dictionary.
        
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
            List of Document objects
        """
        return self.process_product_info(
            product_name=product_data.get("product_name", ""),
            product_purpose=product_data.get("product_purpose"),
            product_docs_link=product_data.get("product_docs_link"),
            key_concepts=product_data.get("key_concepts"),
            extendable_entities=product_data.get("extendable_entities"),
            extendable_docs=product_data.get("extendable_docs"),
            domain=domain,
            metadata=metadata
        )

