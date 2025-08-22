import json
import logging
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
import hashlib
from datetime import datetime

import chromadb
from chromadb import HttpClient, PersistentClient
from chromadb.api.models.Collection import Collection

from app.core.settings import get_settings
from app.n8ncomponents.node import n8nPythonNode, n8nNodeMeta
from app.n8ncomponents.models import NodeType
from app.n8ncomponents.parameters import visit_parameter

logger = logging.getLogger(__name__)


class N8nChromaDBStore:
    """
    Utility class for storing n8n node components into ChromaDB.
    Creates and manages a collection called 'n8n_store' for storing n8n component data.
    """
    
    def __init__(self, collection_name: str = None, use_local: bool = None, local_path: str = None):
        """
        Initialize the N8nChromaDBStore.
        
        Args:
            collection_name: Name of the ChromaDB collection (default: from settings)
            use_local: Whether to use local storage (default: from settings)
            local_path: Custom local storage path (default: from settings)
        """
        self.settings = get_settings()
        
        # Use settings defaults if not specified
        self.collection_name = collection_name or self.settings.N8N_STORE_COLLECTION_NAME
        self.use_local = use_local if use_local is not None else self.settings.N8N_STORE_USE_LOCAL
        self.local_path = local_path or self.settings.N8N_STORE_LOCAL_PATH
        
        # Initialize client and collection
        self.client = self._initialize_client()
        self.collection = self._get_or_create_collection()
        
    def _initialize_client(self):
        """Initialize ChromaDB client based on settings."""
        try:
            if self.use_local:
                # Use local persistent client with n8n-specific settings
                local_path = Path(self.local_path)
                
                # Create directory if it doesn't exist
                local_path.mkdir(parents=True, exist_ok=True)
                
                # Use absolute path for local storage
                if not local_path.is_absolute():
                    local_path = self.settings.BASE_DIR / local_path
                
                logger.info(f"Initializing local ChromaDB client at: {local_path}")
                
                return PersistentClient(
                    path=str(local_path),
                    settings=chromadb.config.Settings(
                        anonymized_telemetry=self.settings.CHROMA_ANONYMIZED_TELEMETRY,
                        allow_reset=self.settings.CHROMA_ALLOW_RESET,
                        isolate_collections=self.settings.CHROMA_ISOLATE_COLLECTIONS
                    )
                )
            else:
                # Use HTTP client with n8n-specific settings
                host = self.settings.N8N_STORE_HOST
                port = self.settings.N8N_STORE_PORT
                
                logger.info(f"Initializing HTTP ChromaDB client at: {host}:{port}")
                
                return HttpClient(
                    host=host,
                    port=port
                )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    
    def _get_or_create_collection(self) -> Collection:
        """Get or create the n8n_store collection."""
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "n8n node components and their metadata",
                    "created_at": datetime.now().isoformat(),
                    "source": "n8n_components",
                    "storage_type": "local" if self.use_local else "remote",
                    "storage_path": str(self.local_path) if self.use_local else f"{self.settings.N8N_STORE_HOST}:{self.settings.N8N_STORE_PORT}",
                    "collection_purpose": "n8n_node_component_search",
                    "version": "1.0.0"
                }
            )
            logger.info(f"Successfully initialized collection: {self.collection_name}")
            return collection
        except Exception as e:
            logger.error(f"Failed to get/create collection {self.collection_name}: {e}")
            raise
    
    def _generate_node_id(self, node_data: Dict[str, Any]) -> str:
        """
        Generate a unique ID for a node based on its properties.
        
        Args:
            node_data: The node data dictionary
            
        Returns:
            str: A unique identifier for the node
        """
        # Create a hash based on key identifying properties
        key_props = {
            "name": node_data.get("name", ""),
            "type": node_data.get("type", ""),
            "typeVersion": node_data.get("typeVersion", ""),
            "position": str(node_data.get("position", {}))
        }
        
        # Convert to sorted string for consistent hashing
        key_string = json.dumps(key_props, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _extract_node_metadata(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant metadata from a node.
        
        Args:
            node_data: The node data dictionary
            
        Returns:
            Dict: Extracted metadata
        """
        metadata = {
            "node_name": node_data.get("name", ""),
            "node_type": node_data.get("type", ""),
            "type_version": node_data.get("typeVersion", ""),
            "position_x": node_data.get("position", {}).get("x", 0),
            "position_y": node_data.get("position", {}).get("y", 0),
            "parameters_count": len(node_data.get("parameters", {})),
            "properties_count": len(node_data.get("properties", [])),
            "has_credentials": bool(node_data.get("credentials", {})),
            "has_webhook": bool(node_data.get("webhookId")),
            "created_at": datetime.now().isoformat()
        }
        
        # Add integration-specific metadata
        if "resource" in node_data:
            metadata["resource"] = node_data["resource"]
        if "operation" in node_data:
            metadata["operation"] = node_data["operation"]
        if "authentication" in node_data:
            metadata["authentication"] = node_data["authentication"]
            
        return metadata
    
    def _extract_node_content(self, node_data: Dict[str, Any]) -> str:
        """
        Extract searchable content from a node.
        
        Args:
            node_data: The node data dictionary
            
        Returns:
            str: Searchable text content
        """
        content_parts = []
        
        # Basic node information
        content_parts.append(f"Node: {node_data.get('name', 'Unknown')}")
        content_parts.append(f"Type: {node_data.get('type', 'Unknown')}")
        content_parts.append(f"Version: {node_data.get('typeVersion', 'Unknown')}")
        
        # Description if available
        if "description" in node_data:
            content_parts.append(f"Description: {node_data['description']}")
        
        # Properties information
        if "properties" in node_data:
            for prop in node_data["properties"]:
                if isinstance(prop, dict):
                    prop_name = prop.get("name", "")
                    prop_type = prop.get("type", "")
                    prop_description = prop.get("description", "")
                    
                    if prop_name:
                        content_parts.append(f"Property: {prop_name}")
                        if prop_type:
                            content_parts.append(f"  Type: {prop_type}")
                        if prop_description:
                            content_parts.append(f"  Description: {prop_description}")
        
        # Parameters information
        if "parameters" in node_data:
            for param_name, param_value in node_data["parameters"].items():
                content_parts.append(f"Parameter: {param_name} = {param_value}")
        
        # Display options
        if "displayOptions" in node_data:
            content_parts.append(f"Display Options: {json.dumps(node_data['displayOptions'])}")
        
        return "\n".join(content_parts)
    
    def store_node(self, node_data: Dict[str, Any]) -> str:
        """
        Store a single node in ChromaDB.
        
        Args:
            node_data: The node data dictionary
            
        Returns:
            str: The ID of the stored node
        """
        try:
            node_id = self._generate_node_id(node_data)
            metadata = self._extract_node_metadata(node_data)
            content = self._extract_node_content(node_data)
            
            # Store in ChromaDB
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[node_id]
            )
            
            logger.info(f"Successfully stored node: {node_data.get('name', 'Unknown')} with ID: {node_id}")
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to store node {node_data.get('name', 'Unknown')}: {e}")
            raise
    
    def store_nodes_from_json(self, json_file_path: str) -> List[str]:
        """
        Store all nodes from a JSON file into ChromaDB.
        
        Args:
            json_file_path: Path to the JSON file containing n8n nodes
            
        Returns:
            List[str]: List of stored node IDs
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stored_ids = []
            
            # Handle different JSON structures
            if isinstance(data, list):
                # Direct list of nodes
                nodes = data
            elif isinstance(data, dict):
                # Check for common structures
                if "nodes" in data:
                    nodes = data["nodes"]
                elif "workflow" in data and "nodes" in data["workflow"]:
                    nodes = data["workflow"]["nodes"]
                else:
                    # Try to find nodes in the first level
                    nodes = [data]
            else:
                raise ValueError("Invalid JSON structure: expected list or dict")
            
            logger.info(f"Found {len(nodes)} nodes to store")
            
            for i, node in enumerate(nodes):
                try:
                    if isinstance(node, dict):
                        node_id = self.store_node(node)
                        stored_ids.append(node_id)
                        
                        if (i + 1) % 100 == 0:
                            logger.info(f"Processed {i + 1}/{len(nodes)} nodes")
                    else:
                        logger.warning(f"Skipping non-dict node at index {i}: {type(node)}")
                        
                except Exception as e:
                    logger.error(f"Failed to store node at index {i}: {e}")
                    continue
            
            logger.info(f"Successfully stored {len(stored_ids)} out of {len(nodes)} nodes")
            return stored_ids
            
        except Exception as e:
            logger.error(f"Failed to read or process JSON file {json_file_path}: {e}")
            raise
    
    def search_nodes(self, query: str, n_results: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for nodes in the collection.
        
        Args:
            query: Search query string
            n_results: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List[Dict]: Search results with documents, metadata, and distances
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filters
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['metadatas'] and results['distances']:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        'document': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i],
                        'id': results['ids'][0][i] if results['ids'] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific node by its ID.
        
        Args:
            node_id: The ID of the node to retrieve
            
        Returns:
            Optional[Dict]: Node data if found, None otherwise
        """
        try:
            results = self.collection.get(ids=[node_id])
            
            if results['documents'] and results['metadatas']:
                return {
                    'document': results['documents'][0],
                    'metadata': results['metadatas'][0],
                    'id': results['ids'][0] if results['ids'] else None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve node {node_id}: {e}")
            return None
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.
        
        Returns:
            Dict: Collection statistics
        """
        try:
            count = self.collection.count()
            
            # Get sample metadata to analyze structure
            sample_results = self.collection.peek(limit=1)
            
            stats = {
                'total_nodes': count,
                'collection_name': self.collection_name,
                'storage_type': 'local' if self.use_local else 'remote',
                'storage_path': str(self.local_path) if self.use_local else f"{self.settings.N8N_STORE_HOST}:{self.settings.N8N_STORE_PORT}",
                'sample_metadata_keys': list(sample_results['metadatas'][0].keys()) if sample_results['metadatas'] else []
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get detailed storage information.
        
        Returns:
            Dict: Storage configuration and status
        """
        try:
            storage_info = {
                'collection_name': self.collection_name,
                'use_local': self.use_local,
                'local_path': str(self.local_path),
                'remote_host': self.settings.N8N_STORE_HOST,
                'remote_port': self.settings.N8N_STORE_PORT,
                'client_type': 'PersistentClient' if self.use_local else 'HttpClient',
                'base_directory': str(self.settings.BASE_DIR),
                'collection_exists': True,
                'total_nodes': self.collection.count()
            }
            
            if self.use_local:
                local_path = Path(self.local_path)
                if not local_path.is_absolute():
                    local_path = self.settings.BASE_DIR / local_path
                
                storage_info['absolute_local_path'] = str(local_path)
                storage_info['local_path_exists'] = local_path.exists()
                storage_info['local_path_size'] = self._get_directory_size(local_path) if local_path.exists() else 0
            
            return storage_info
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {}
    
    def _get_directory_size(self, path: Path) -> int:
        """
        Calculate the size of a directory in bytes.
        
        Args:
            path: Path to the directory
            
        Returns:
            int: Size in bytes
        """
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.exists():
                        total_size += filepath.stat().st_size
            return total_size
        except Exception as e:
            logger.error(f"Failed to calculate directory size: {e}")
            return 0
    
    def clear_collection(self):
        """Clear all data from the collection."""
        try:
            self.collection.delete(where={})
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise


def main():
    """
    Main function to demonstrate usage of the N8nChromaDBStore.
    """
    try:
        # Initialize the store
        store = N8nChromaDBStore()
        
        # Get collection stats
        stats = store.get_collection_stats()
        print(f"Collection stats: {stats}")
        
        # Example: Store nodes from the nodes.json file
        nodes_json_path = Path(__file__).parent.parent / "n8ncomponents" / "nodes.json"
        
        if nodes_json_path.exists():
            print(f"Found nodes.json at: {nodes_json_path}")
            
            # Store nodes (this might take a while for large files)
            print("Storing nodes in ChromaDB...")
            stored_ids = store.store_nodes_from_json(str(nodes_json_path))
            print(f"Stored {len(stored_ids)} nodes")
            
            # Get updated stats
            updated_stats = store.get_collection_stats()
            print(f"Updated collection stats: {updated_stats}")
            
            # Example search
            print("\nSearching for 'HTTP' nodes...")
            search_results = store.search_nodes("HTTP", n_results=5)
            for i, result in enumerate(search_results):
                print(f"\nResult {i+1}:")
                print(f"  Node: {result['metadata'].get('node_name', 'Unknown')}")
                print(f"  Type: {result['metadata'].get('node_type', 'Unknown')}")
                print(f"  Distance: {result['distance']:.4f}")
                
        else:
            print(f"nodes.json not found at: {nodes_json_path}")
            print("Please ensure the file exists before running this utility.")
            
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Main execution failed: {e}")


if __name__ == "__main__":
    main()
