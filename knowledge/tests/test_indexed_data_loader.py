"""
Utility to load and discover indexed data from indexing_preview/ directory.

This module helps tests use actual indexed data instead of synthetic test data.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class IndexedDataLoader:
    """Loads and discovers indexed data from indexing_preview/ directory."""
    
    def __init__(self, preview_dir: str = "indexing_preview"):
        """
        Initialize the loader.
        
        Args:
            preview_dir: Path to indexing_preview directory (relative to knowledge/ root)
        """
        # Get the knowledge/ root directory (parent of tests/)
        knowledge_root = Path(__file__).parent.parent
        self.preview_dir = knowledge_root / preview_dir
        self._cached_data: Optional[Dict[str, Any]] = None
    
    def discover_indexed_data(self) -> Dict[str, Any]:
        """
        Discover all indexed data from preview files.
        
        Returns:
            Dictionary with:
            - contexts: List of context_ids found
            - context_metadata: Dict mapping context_id to metadata
            - controls: List of control-related entities
            - content_types: Dict mapping content_type to file count
        """
        if self._cached_data:
            return self._cached_data
        
        if not self.preview_dir.exists():
            logger.warning(f"Preview directory does not exist: {self.preview_dir}")
            return {
                "contexts": [],
                "context_metadata": {},
                "controls": [],
                "content_types": {},
                "entities": []
            }
        
        contexts: Set[str] = set()
        context_metadata: Dict[str, Dict[str, Any]] = {}
        controls: List[Dict[str, Any]] = []
        entities: List[Dict[str, Any]] = []
        content_types: Dict[str, int] = defaultdict(int)
        
        # Scan all subdirectories
        for content_dir in self.preview_dir.iterdir():
            if not content_dir.is_dir():
                continue
            
            content_type = content_dir.name
            json_files = list(content_dir.glob("*.json"))
            # Exclude summary files
            json_files = [f for f in json_files if "summary" not in f.name]
            content_types[content_type] = len(json_files)
            
            # Load each JSON file
            for json_file in json_files:
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    
                    # Extract contexts, controls, entities from documents
                    for doc in file_data.get("documents", []):
                        doc_metadata = doc.get("metadata", {})
                        
                        # Extract context_id
                        context_id = doc_metadata.get("context_id")
                        if context_id:
                            contexts.add(context_id)
                            if context_id not in context_metadata:
                                context_metadata[context_id] = {
                                    "context_id": context_id,
                                    "content_type": content_type,
                                    "extraction_type": doc_metadata.get("extraction_type"),
                                    "source_file": doc_metadata.get("source_file"),
                                    "domain": doc_metadata.get("domain"),
                                    "framework": doc_metadata.get("framework"),
                                    "metadata": doc_metadata
                                }
                        
                        # Extract entities (which might be controls)
                        extraction_type = doc_metadata.get("extraction_type")
                        if extraction_type == "entities":
                            page_content = doc.get("page_content", "")
                            try:
                                # Try to parse as JSON (entities are often stored as JSON)
                                entities_data = json.loads(page_content)
                                if isinstance(entities_data, dict) and "entities" in entities_data:
                                    for entity in entities_data["entities"]:
                                        entity_type = entity.get("entity_type", "")
                                        if entity_type in ["control", "policy"]:
                                            controls.append({
                                                "entity_id": entity.get("entity_id"),
                                                "entity_name": entity.get("entity_name"),
                                                "entity_type": entity_type,
                                                "context_id": context_id,
                                                "properties": entity.get("properties", {})
                                            })
                                        else:
                                            entities.append({
                                                "entity_id": entity.get("entity_id"),
                                                "entity_name": entity.get("entity_name"),
                                                "entity_type": entity_type,
                                                "context_id": context_id,
                                                "properties": entity.get("properties", {})
                                            })
                            except (json.JSONDecodeError, KeyError):
                                # Not JSON format, skip
                                pass
                
                except Exception as e:
                    logger.warning(f"Error loading {json_file}: {e}")
        
        result = {
            "contexts": sorted(list(contexts)),
            "context_metadata": context_metadata,
            "controls": controls,
            "entities": entities,
            "content_types": dict(content_types)
        }
        
        self._cached_data = result
        return result
    
    def get_context_ids(self) -> List[str]:
        """Get list of all context IDs found in indexed data."""
        data = self.discover_indexed_data()
        return data["contexts"]
    
    def get_context_metadata(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific context ID."""
        data = self.discover_indexed_data()
        return data["context_metadata"].get(context_id)
    
    def get_controls_for_context(self, context_id: str) -> List[Dict[str, Any]]:
        """Get controls/entities for a specific context."""
        data = self.discover_indexed_data()
        return [
            ctrl for ctrl in data["controls"]
            if ctrl.get("context_id") == context_id
        ]
    
    def find_contexts_by_query(self, query: str, top_k: int = 5) -> List[str]:
        """
        Find context IDs that might match a query (simple keyword matching).
        
        This is a simple implementation - actual search should use the vector store.
        """
        data = self.discover_indexed_data()
        query_lower = query.lower()
        
        matching_contexts = []
        for context_id, metadata in data["context_metadata"].items():
            # Simple keyword matching
            if (query_lower in context_id.lower() or
                query_lower in str(metadata.get("domain", "")).lower() or
                query_lower in str(metadata.get("framework", "")).lower()):
                matching_contexts.append(context_id)
        
        return matching_contexts[:top_k]
    
    def get_summary(self) -> str:
        """Get a summary of discovered indexed data."""
        data = self.discover_indexed_data()
        
        summary_lines = [
            "Indexed Data Summary:",
            f"  Total Contexts: {len(data['contexts'])}",
            f"  Total Controls/Entities: {len(data['controls'])}",
            f"  Content Types: {len(data['content_types'])}",
            "",
            "Content Types:"
        ]
        
        for content_type, count in sorted(data["content_types"].items()):
            summary_lines.append(f"  - {content_type}: {count} files")
        
        summary_lines.append("")
        summary_lines.append("Contexts:")
        for ctx_id in data["contexts"][:10]:  # Show first 10
            metadata = data["context_metadata"].get(ctx_id, {})
            summary_lines.append(f"  - {ctx_id} ({metadata.get('extraction_type', 'unknown')})")
        
        if len(data["contexts"]) > 10:
            summary_lines.append(f"  ... and {len(data['contexts']) - 10} more")
        
        return "\n".join(summary_lines)


# Global instance for easy access
_loader_instance: Optional[IndexedDataLoader] = None


def get_indexed_data_loader() -> IndexedDataLoader:
    """Get or create the global IndexedDataLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = IndexedDataLoader()
    return _loader_instance

