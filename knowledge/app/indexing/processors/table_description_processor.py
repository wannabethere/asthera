"""
Table Description Processor
Processes and indexes table descriptions from MDL using the TableDescription structure.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class TableDescriptionProcessor:
    """Processes table descriptions from MDL and creates documents in TableDescription format."""
    
    def __init__(self):
        """Initialize the TableDescription processor."""
        logger.info("Initializing TableDescriptionProcessor")
    
    def extract_table_descriptions(self, mdl: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract table descriptions from MDL.
        
        Args:
            mdl: MDL dictionary containing models, metrics, views, and relationships
            
        Returns:
            List of table description dictionaries
        """
        logger.info("Starting table description extraction from MDL")
        
        def _structure_data(mdl_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            """Structure data from MDL payload."""
            properties = payload.get("properties", {})
            return {
                "mdl_type": mdl_type,
                "name": payload.get("name"),
                "description": payload.get("description", ""),
                "columns": [column["name"] for column in payload.get("columns", [])],
                "properties": properties,
                "category": properties.get("category"),  # Extract category from properties
            }
        
        # Process models
        logger.info("Processing models")
        models = [_structure_data("TABLE_SCHEMA", model) for model in mdl.get("models", [])]
        logger.info(f"Processed {len(models)} models")
        
        # Process metrics
        logger.info("Processing metrics")
        metrics = [_structure_data("METRIC", metric) for metric in mdl.get("metrics", [])]
        logger.info(f"Processed {len(metrics)} metrics")
        
        # Process views
        logger.info("Processing views")
        views = [_structure_data("VIEW", view) for view in mdl.get("views", [])]
        logger.info(f"Processed {len(views)} views")
        
        # Process relationships
        logger.info("Processing relationships")
        relationships = mdl.get("relationships", [])
        logger.info(f"Processed {len(relationships)} relationships")
        
        # Create a mapping of table names to their relationships
        table_relationships = self._build_relationship_map(relationships)
        
        # Combine all resources
        resources = models + metrics + views
        logger.info(f"Total resources found: {len(resources)}")
        
        # Create descriptions
        logger.info("Creating table descriptions")
        descriptions = []
        for resource in resources:
            if resource["name"] is not None:
                table_name = resource["name"]
                table_rels = table_relationships.get(table_name, [])
                
                description = {
                    "name": table_name,
                    "mdl_type": resource["mdl_type"],
                    "type": "TABLE_DESCRIPTION",
                    "description": resource.get("description", ""),
                    "columns": ", ".join(resource["columns"]) if isinstance(resource["columns"], list) else str(resource["columns"]),
                    "relationships": table_rels,
                    "category": resource.get("category")  # Include category in description
                }
                descriptions.append(description)
                logger.debug(f"Created description for {table_name}: {description['description'][:100]}...")
        
        logger.info(f"Created {len(descriptions)} table descriptions with relationships")
        return descriptions
    
    def _build_relationship_map(self, relationships: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build a mapping of table names to their relationships.
        
        Args:
            relationships: List of relationship dictionaries from MDL
            
        Returns:
            Dictionary mapping table names to their relationships
        """
        table_relationships = {}
        for relationship in relationships:
            models_in_relationship = relationship.get("models", [])
            for table_name in models_in_relationship:
                if table_name not in table_relationships:
                    table_relationships[table_name] = []
                table_relationships[table_name].append({
                    "name": relationship.get("name", ""),
                    "models": models_in_relationship,
                    "joinType": relationship.get("joinType", ""),
                    "condition": relationship.get("condition", ""),
                    "properties": relationship.get("properties", {})
                })
        return table_relationships
    
    def create_documents(
        self,
        table_descriptions: List[Dict[str, Any]],
        project_id: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None,
        table_ddl_map: Optional[Dict[str, str]] = None,
    ) -> List[Document]:
        """
        Create Document objects from table descriptions.

        Args:
            table_descriptions: List of table description dictionaries
            project_id: Project ID (used as project_id in metadata)
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            table_ddl_map: Optional map table_name -> full CREATE TABLE DDL (included in content for retrieval)
        Returns:
            List of Document objects in TableDescription format
        """
        logger.info(f"Creating {len(table_descriptions)} documents from table descriptions")
        table_ddl_map = table_ddl_map or {}
        documents = []
        for chunk in table_descriptions:
            # Create stringified dictionary content (compatible with TableDescription format from project_reader.py)
            # Ensure columns is a comma-separated string, not a list
            columns_str = chunk['columns']
            if isinstance(columns_str, list):
                columns_str = ', '.join(columns_str)

            content_dict = {
                "name": chunk['name'],
                "mdl_type": chunk['mdl_type'],
                "type": "TABLE_DESCRIPTION",
                "description": chunk['description'],
                "columns": columns_str  # Comma-separated string, not list
            }
            if chunk['name'] in table_ddl_map:
                content_dict["ddl"] = table_ddl_map[chunk['name']]

            # Add relationships if they exist
            if chunk.get('relationships'):
                content_dict["relationships"] = chunk['relationships']
            
            # Convert to stringified dictionary (same format as TableDescriptionChunker in project_reader.py)
            page_content = str(content_dict)
            
            # Create document with TableDescription metadata structure
            doc_metadata = {
                "type": "TABLE_DESCRIPTION",
                "mdl_type": chunk["mdl_type"],
                "name": chunk["name"],
                "description": chunk["description"],
                "relationships": chunk.get("relationships", []),
                "content_type": "table_description",
                "indexed_at": datetime.utcnow().isoformat()
            }
            
            # Add category if available (for LLM guidance, not database filtering)
            if chunk.get("category"):
                doc_metadata["category"] = chunk["category"]
            
            # Add optional fields
            if project_id:
                doc_metadata["project_id"] = project_id
            if product_name:
                doc_metadata["product_name"] = product_name
            if domain:
                doc_metadata["domain"] = domain
            if metadata:
                doc_metadata.update(metadata)
            
            doc = Document(
                page_content=page_content,
                metadata=doc_metadata
            )
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} documents")
        return documents
    
    async def process_mdl(
        self,
        mdl: Dict[str, Any],
        project_id: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None,
        table_ddl_map: Optional[Dict[str, str]] = None,
    ) -> List[Document]:
        """
        Process MDL and create table description documents.

        Args:
            mdl: MDL dictionary
            project_id: Project ID
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            table_ddl_map: Optional map table_name -> full CREATE TABLE DDL (included in content for retrieval)
        Returns:
            List of Document objects
        """
        logger.info(f"Processing MDL for table descriptions (project: {project_id}, domain: {domain})")

        # Extract table descriptions
        table_descriptions = self.extract_table_descriptions(mdl)

        # Create documents (optionally include full DDL in each table description)
        documents = self.create_documents(
            table_descriptions=table_descriptions,
            project_id=project_id or product_name,
            product_name=product_name,
            domain=domain,
            metadata=metadata,
            table_ddl_map=table_ddl_map,
        )
        return documents

