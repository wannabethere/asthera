"""
Category Mapping Processor
Processes MDL and groups tables by category, creating category-level documents
that contain lists of table descriptions for efficient category-based search.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class CategoryMappingProcessor:
    """Processes MDL and creates category-level documents with grouped table descriptions."""
    
    def __init__(self):
        """Initialize the Category Mapping processor."""
        logger.info("Initializing CategoryMappingProcessor")
    
    def extract_table_descriptions_by_category(self, mdl: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract table descriptions from MDL and group them by category.
        
        Args:
            mdl: MDL dictionary containing models, metrics, views, and relationships
            
        Returns:
            Dictionary mapping category names to lists of table description dictionaries
        """
        logger.info("Starting category-based table description extraction from MDL")
        
        def _structure_data(mdl_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            """Structure data from MDL payload."""
            properties = payload.get("properties", {})
            return {
                "mdl_type": mdl_type,
                "name": payload.get("name"),
                "description": payload.get("description", ""),
                "columns": [column["name"] for column in payload.get("columns", [])],
                "properties": properties,
                "category": properties.get("category") or "other",  # Default to "other" if no category
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
        
        # Group by category
        category_groups = defaultdict(list)
        for resource in resources:
            if resource["name"] is not None:
                table_name = resource["name"]
                category = resource.get("category", "other")
                table_rels = table_relationships.get(table_name, [])
                
                description = {
                    "name": table_name,
                    "mdl_type": resource["mdl_type"],
                    "type": "TABLE_DESCRIPTION",
                    "description": resource.get("description", ""),
                    "columns": ", ".join(resource["columns"]) if isinstance(resource["columns"], list) else str(resource["columns"]),
                    "relationships": table_rels,
                    "category": category
                }
                category_groups[category].append(description)
                logger.debug(f"Added {table_name} to category {category}")
        
        logger.info(f"Created {len(category_groups)} category groups with {sum(len(tables) for tables in category_groups.values())} total tables")
        return dict(category_groups)
    
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
        category_mappings: Dict[str, List[Dict[str, Any]]],
        project_id: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Create Document objects from category mappings.
        Each document represents a category with its list of table descriptions.
        
        Args:
            category_mappings: Dictionary mapping category names to lists of table descriptions
            project_id: Project ID
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            List of Document objects in CategoryMapping format
        """
        logger.info(f"Creating {len(category_mappings)} category mapping documents")
        
        documents = []
        for category, tables in category_mappings.items():
            # Create a structured content for the category
            # This will be the searchable content
            category_content = {
                "category": category,
                "table_count": len(tables),
                "tables": tables
            }
            
            # Create a human-readable summary for the page content
            # This helps with semantic search
            table_summaries = []
            for table in tables:
                summary_parts = [
                    f"Table: {table['name']}",
                    f"Type: {table['mdl_type']}",
                ]
                if table.get("description"):
                    summary_parts.append(f"Description: {table['description']}")
                if table.get("columns"):
                    summary_parts.append(f"Columns: {table['columns']}")
                table_summaries.append(" | ".join(summary_parts))
            
            page_content = f"Category: {category}\n"
            page_content += f"Number of tables: {len(tables)}\n\n"
            page_content += "Tables in this category:\n"
            page_content += "\n".join(f"- {summary}" for summary in table_summaries)
            
            # Create document metadata
            doc_metadata = {
                "type": "CATEGORY_MAPPING",
                "category": category,
                "table_count": len(tables),
                "table_names": [table["name"] for table in tables],
                "content_type": "category_mapping",
                "indexed_at": datetime.utcnow().isoformat()
            }
            
            # Add optional fields
            if project_id:
                doc_metadata["project_id"] = project_id
            if product_name:
                doc_metadata["product_name"] = product_name
            if domain:
                doc_metadata["domain"] = domain
            if metadata:
                doc_metadata.update(metadata)
            
            # Store the full structured data in metadata for easy retrieval
            doc_metadata["category_data"] = category_content
            
            doc = Document(
                page_content=page_content,
                metadata=doc_metadata
            )
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} category mapping documents")
        return documents
    
    async def process_mdl(
        self,
        mdl: Dict[str, Any],
        project_id: Optional[str] = None,
        product_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process MDL and create category mapping documents.
        
        Args:
            mdl: MDL dictionary
            project_id: Project ID
            product_name: Product name
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            List of Document objects, one per category
        """
        logger.info(f"Processing MDL for category mappings (project: {project_id}, domain: {domain})")
        
        # Extract table descriptions grouped by category
        category_mappings = self.extract_table_descriptions_by_category(mdl)
        
        # Create documents
        documents = self.create_documents(
            category_mappings=category_mappings,
            project_id=project_id or product_name,
            product_name=product_name,
            domain=domain,
            metadata=metadata
        )
        
        return documents

