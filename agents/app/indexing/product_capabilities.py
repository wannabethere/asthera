"""
Product Capabilities processor.

Indexes product capabilities from product_capabilities JSON files into Qdrant.
Maps MDL file names to API categories with descriptions.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

logger = logging.getLogger("genieml-agents")


class ProductCapabilities:
    """Processes and indexes product capabilities from product_capabilities JSON files."""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any = None,
    ) -> None:
        """Initialize the Product Capabilities processor.
        
        Args:
            document_store: The document store instance (Qdrant or Chroma)
            embedder: Optional embedder (not used for capabilities, but kept for consistency)
        """
        self._document_store = document_store
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )
        logger.info("ProductCapabilities processor initialized")

    async def run(
        self,
        product_id: str,
        capability_id: str,
        capability_data: Dict[str, Any],
        product_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process and index a single product capability.
        
        Args:
            product_id: Product identifier (e.g., "qualys", "sentinel")
            capability_id: Capability identifier (e.g., "assets", "vulnerabilities")
            capability_data: Capability data from api_categories (id, name, description, planning_notes)
            product_info: Optional product metadata (product_name, version, purpose, etc.)
        
        Returns:
            Dictionary with processing results
        """
        logger.info(
            f"Processing product capability: {product_id}.{capability_id}"
        )
        
        try:
            # Extract capability information
            name = capability_data.get("name", capability_id)
            description = capability_data.get("description", "")
            planning_notes = capability_data.get("planning_notes", "")
            
            # Build enriched content
            enriched_text_parts = [
                f"Product: {product_info.get('product_name', product_id) if product_info else product_id}",
                f"Capability: {name}",
                f"ID: {capability_id}",
                "",
                f"Description: {description}",
            ]
            
            if planning_notes:
                enriched_text_parts.extend([
                    "",
                    "Planning Notes:",
                    planning_notes,
                ])
            
            if product_info:
                purpose = product_info.get("purpose", "")
                if purpose:
                    enriched_text_parts.extend([
                        "",
                        "Product Purpose:",
                        purpose,
                    ])
                
                # Include enriched data_capabilities information if available
                data_capabilities = product_info.get("data_capabilities", {})
                if data_capabilities:
                    # Check if this capability has enriched data_capabilities info
                    for capability_type, capability_list in data_capabilities.items():
                        # Handle both formats: array of strings or array of objects
                        if isinstance(capability_list, list) and len(capability_list) > 0:
                            # Check if it's enriched format (objects with id, description)
                            if isinstance(capability_list[0], dict):
                                for cap_data in capability_list:
                                    if cap_data.get("id") == capability_id:
                                        cap_desc = cap_data.get("description", "")
                                        if cap_desc:
                                            enriched_text_parts.extend([
                                                "",
                                                f"{capability_type.capitalize()} Capability:",
                                                cap_desc,
                                            ])
                                        
                                        examples = cap_data.get("examples", [])
                                        if examples:
                                            enriched_text_parts.extend([
                                                "",
                                                "Examples:",
                                            ])
                                            for example in examples[:5]:  # Limit to 5 examples
                                                enriched_text_parts.append(f"  • {example}")
                                        
                                        relevant_props = cap_data.get("relevant_properties", [])
                                        if relevant_props:
                                            enriched_text_parts.extend([
                                                "",
                                                "Relevant Properties:",
                                                ", ".join(relevant_props[:10]),  # Limit to 10 properties
                                            ])
                                        break
            
            enriched_text = "\n".join(enriched_text_parts)
            
            # Create structured content
            page_content = json.dumps({
                "type": "PRODUCT_CAPABILITY",
                "product_id": product_id,
                "capability_id": capability_id,
                "name": name,
                "description": description,
                "planning_notes": planning_notes,
                "product_name": product_info.get("product_name", "") if product_info else "",
                "product_version": product_info.get("version", "") if product_info else "",
            }, indent=2)
            
            # Create metadata
            metadata = {
                "type": "PRODUCT_CAPABILITY",
                "product_id": product_id,
                "capability_id": capability_id,
                "name": name,
                "product_name": product_info.get("product_name", product_id) if product_info else product_id,
            }
            
            # Create document
            document = LangchainDocument(
                page_content=enriched_text,
                metadata=metadata
            )
            
            # Check if document_store is Qdrant-based and use direct points
            from app.storage.qdrant_store import DocumentQdrantStore
            if isinstance(self._document_store, DocumentQdrantStore):
                logger.info("Using direct Qdrant points insertion for product capability")
                point_data = {
                    "id": str(uuid.uuid4()),
                    "text": enriched_text,
                    "page_content": page_content,
                    "metadata": {
                        **metadata,
                        "description": description,
                        "planning_notes": planning_notes,
                    }
                }
                write_result = self._document_store.add_points_direct(
                    points_data=[point_data],
                    log_schema=True
                )
                logger.info(f"Successfully wrote {write_result['documents_written']} points to Qdrant")
            else:
                # Use standard document writer for ChromaDB
                write_result = await self._writer.run(documents=[document])
                logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "product_id": product_id,
                "capability_id": capability_id,
            }
            logger.info(f"Product capability processing completed: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing product capability {product_id}.{capability_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "documents_written": 0,
                "product_id": product_id,
                "capability_id": capability_id,
                "error": str(e)
            }

    async def clean(self, product_id: Optional[str] = None) -> None:
        """Clean documents for the specified product.
        
        Args:
            product_id: Optional product ID to clean documents for
        """
        try:
            if product_id:
                # Delete documents with the specified product_id
                from app.storage.qdrant_store import DocumentQdrantStore
                if isinstance(self._document_store, DocumentQdrantStore):
                    self._document_store.delete_by_project_id(product_id)
                else:
                    self._document_store.collection.delete(
                        where={"product_id": product_id}
                    )
                logger.info(f"Cleaned documents for product ID: {product_id}")
            else:
                # Delete all documents if no product_id specified
                if isinstance(self._document_store, DocumentQdrantStore):
                    # Qdrant doesn't have a simple delete all, so we'd need to query first
                    logger.warning("Cleaning all documents not implemented for Qdrant")
                else:
                    self._document_store.collection.delete()
                logger.info("Cleaned all documents")
                
        except Exception as e:
            logger.error(f"Error cleaning documents: {str(e)}")
            raise


def load_product_capabilities(capabilities_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load all product capabilities JSON files.
    
    Args:
        capabilities_dir: Directory containing product_capabilities JSON files
    
    Returns:
        Dictionary mapping product_id -> product capabilities data
    """
    capabilities = {}
    
    if not capabilities_dir.exists():
        logger.warning(f"Product capabilities directory not found: {capabilities_dir}")
        return capabilities
    
    # Find all JSON files (excluding schema file)
    json_files = [
        f for f in capabilities_dir.glob("*.json")
        if f.name != "product_capabilities_schema.json"
    ]
    
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            product_id = data.get("product_id")
            if product_id:
                capabilities[product_id] = data
                logger.info(f"Loaded capabilities for {product_id} from {json_file.name}")
            else:
                logger.warning(f"No product_id found in {json_file.name}")
        except Exception as e:
            logger.error(f"Error loading {json_file}: {e}")
    
    return capabilities


def map_mdl_to_capability(mdl_filename: str, api_categories: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Map MDL filename to API category.
    
    Args:
        mdl_filename: MDL filename (e.g., "assets.mdl.json")
        api_categories: List of API categories from product_capabilities
    
    Returns:
        Matching API category dict or None
    """
    # Extract base name (e.g., "assets" from "assets.mdl.json")
    base_name = mdl_filename.replace(".mdl.json", "").replace("_", "_")
    
    # Try exact match first
    for category in api_categories:
        if category.get("id") == base_name:
            return category
    
    # Try partial match (e.g., "assets_inventory" -> "assets")
    for category in api_categories:
        category_id = category.get("id", "")
        if base_name.startswith(category_id) or category_id in base_name:
            return category
    
    return None
