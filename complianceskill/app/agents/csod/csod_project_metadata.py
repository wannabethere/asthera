"""
CSOD Project Metadata Loader and Category Recommender

Loads project metadata from JSON and recommends categories based on:
- Intent classification
- Data sources
- User query (optional semantic search)

Supports both JSON-based lookup and optional vector store semantic search.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CSODProjectMetadata:
    """Metadata for a CSOD project."""
    project_id: str
    project_name: str
    data_sources: List[str]
    categories: List[str]
    intents: List[str]
    focus_areas: List[str]
    description: str


class CSODProjectMetadataLoader:
    """Loads and queries CSOD project metadata from JSON."""
    
    def __init__(self, metadata_path: Optional[Path] = None):
        """
        Initialize metadata loader.
        
        Args:
            metadata_path: Path to JSON metadata file. Defaults to data/csod_project_metadata.json
        """
        if metadata_path is None:
            # Default to data/csod_project_metadata.json relative to project root
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            metadata_path = base_dir / "data" / "csod_project_metadata.json"
        
        self.metadata_path = Path(metadata_path)
        self._metadata: Optional[Dict[str, Any]] = None
        self._projects: List[CSODProjectMetadata] = []
        self._vector_store_enabled = False
        self._vector_store = None
    
    def load(self) -> None:
        """Load metadata from JSON file."""
        if not self.metadata_path.exists():
            logger.warning(f"CSOD project metadata file not found: {self.metadata_path}")
            self._metadata = {"projects": [], "category_mappings": {}, "intent_to_categories": {}}
            self._projects = []
            return
        
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self._metadata = json.load(f)
            
            # Parse projects
            self._projects = [
                CSODProjectMetadata(
                    project_id=proj.get("project_id", ""),
                    project_name=proj.get("project_name", ""),
                    data_sources=proj.get("data_sources", []),
                    categories=proj.get("categories", []),
                    intents=proj.get("intents", []),
                    focus_areas=proj.get("focus_areas", []),
                    description=proj.get("description", ""),
                )
                for proj in self._metadata.get("projects", [])
            ]
            logger.info(f"Loaded {len(self._projects)} CSOD projects from {self.metadata_path}")
        except Exception as e:
            logger.error(f"Failed to load CSOD project metadata: {e}", exc_info=True)
            self._metadata = {"projects": [], "category_mappings": {}, "intent_to_categories": {}}
            self._projects = []
    
    def enable_vector_store(self, collection_name: str = "csod_project_metadata") -> None:
        """
        Enable vector store for semantic search (optional).
        
        Uses the document store provider to get or create the vector store.
        
        Args:
            collection_name: Name of the vector store collection
        """
        try:
            from app.core.dependencies import get_doc_store_provider
            from app.core.settings import get_settings
            
            settings = get_settings()
            doc_store_provider = get_doc_store_provider()
            stores = doc_store_provider.stores if hasattr(doc_store_provider, "stores") else {}
            
            # Try to get existing store from provider
            self._vector_store = stores.get(collection_name)
            
            if not self._vector_store:
                # Store doesn't exist in provider - try to create it using provider's infrastructure
                # Get the vector store type and create appropriate store
                vector_store_type = settings.VECTOR_STORE_TYPE
                
                from app.storage.documents import DocumentQdrantStore, DocumentChromaStore
                from langchain_openai import OpenAIEmbeddings
                
                embeddings_model = OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    openai_api_key=settings.OPENAI_API_KEY
                )
                
                if vector_store_type.value == "qdrant":
                    qdrant_config = settings.get_vector_store_config()
                    self._vector_store = DocumentQdrantStore(
                        collection_name=collection_name,
                        host=qdrant_config.get("host", "localhost"),
                        port=qdrant_config.get("port", 6333),
                        embeddings_model=embeddings_model
                    )
                elif vector_store_type.value == "chroma":
                    from app.core.dependencies import get_chromadb_client
                    client = get_chromadb_client()
                    self._vector_store = DocumentChromaStore(
                        persistent_client=client,
                        collection_name=collection_name,
                        embeddings_model=embeddings_model
                    )
                else:
                    logger.warning(f"Unsupported vector store type: {vector_store_type.value}")
                    self._vector_store = None
                
                # Add to provider if created successfully
                if self._vector_store and hasattr(doc_store_provider, "add_store"):
                    doc_store_provider.add_store(collection_name, self._vector_store)
            
            self._vector_store_enabled = bool(self._vector_store)
            if self._vector_store_enabled:
                logger.info(f"Vector store enabled for CSOD project metadata: {collection_name}")
            else:
                logger.warning(f"Could not enable vector store for CSOD project metadata: {collection_name}")
        except Exception as e:
            logger.warning(f"Failed to enable vector store for CSOD metadata: {e}", exc_info=True)
            self._vector_store_enabled = False
            self._vector_store = None
    
    def recommend_categories(
        self,
        intent: Optional[str] = None,
        data_sources: Optional[List[str]] = None,
        user_query: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        use_semantic_search: bool = False,
        limit: int = 10,
    ) -> List[str]:
        """
        Recommend categories based on intent, data sources, and optionally semantic search.
        
        Args:
            intent: CSOD intent (e.g., "metrics_dashboard_plan")
            data_sources: List of data source IDs (e.g., ["cornerstone", "workday"])
            user_query: Optional user query for semantic search
            focus_areas: Optional focus areas from classifier
            use_semantic_search: If True, use vector store for semantic search
            limit: Maximum number of categories to return
        
        Returns:
            List of recommended category strings
        """
        if self._metadata is None:
            self.load()
        
        if not self._metadata:
            return []
        
        recommended_categories: Set[str] = set()
        
        # Method 1: Intent-based recommendation
        if intent:
            intent_categories = self._metadata.get("intent_to_categories", {}).get(intent, [])
            recommended_categories.update(intent_categories)
            logger.debug(f"Intent '{intent}' recommended categories: {intent_categories}")
        
        # Method 2: Data source matching
        if data_sources:
            for project in self._projects:
                # Check if project's data sources overlap with requested sources
                project_ds = {ds.lower() for ds in project.data_sources}
                requested_ds = {ds.lower().split(".")[0] for ds in data_sources}
                
                if project_ds & requested_ds:  # Any overlap
                    recommended_categories.update(project.categories)
                    logger.debug(f"Project '{project.project_id}' matched data sources, added categories: {project.categories}")
        
        # Method 3: Semantic search (if enabled and query provided)
        if use_semantic_search and user_query and self._vector_store_enabled and self._vector_store:
            try:
                semantic_categories = self._semantic_search_categories(user_query, limit=limit)
                recommended_categories.update(semantic_categories)
                logger.debug(f"Semantic search recommended categories: {semantic_categories}")
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")
        
        # Method 4: Focus area matching
        if focus_areas:
            for project in self._projects:
                if any(fa in project.focus_areas for fa in focus_areas):
                    recommended_categories.update(project.categories)
                    logger.debug(f"Project '{project.project_id}' matched focus areas, added categories: {project.categories}")
        
        # Expand related categories
        expanded_categories = self._expand_related_categories(list(recommended_categories))
        
        # Limit and return
        return expanded_categories[:limit]
    
    def _semantic_search_categories(
        self,
        query: str,
        limit: int = 10,
    ) -> List[str]:
        """
        Perform semantic search to find relevant categories.
        
        Args:
            query: User query or description
            limit: Maximum results
        
        Returns:
            List of category strings
        """
        if not self._vector_store:
            return []
        
        try:
            # Search for projects matching the query
            results = self._vector_store.semantic_search(
                query=query,
                k=limit * 2,  # Get more to filter
            )
            
            categories: Set[str] = set()
            for result in results:
                metadata = result.get("metadata", {})
                project_categories = metadata.get("categories", [])
                if isinstance(project_categories, list):
                    categories.update(project_categories)
            
            return list(categories)[:limit]
        except Exception as e:
            logger.warning(f"Semantic search for categories failed: {e}")
            return []
    
    def _expand_related_categories(self, categories: List[str]) -> List[str]:
        """Expand categories with related categories from mappings."""
        if not self._metadata:
            return categories
        
        expanded = set(categories)
        category_mappings = self._metadata.get("category_mappings", {})
        
        for cat in categories:
            if cat in category_mappings:
                related = category_mappings[cat].get("related_categories", [])
                expanded.update(related)
        
        return list(expanded)
    
    def find_projects_by_categories(
        self,
        categories: List[str],
        data_sources: Optional[List[str]] = None,
    ) -> List[CSODProjectMetadata]:
        """
        Find projects that match the given categories.
        
        Args:
            categories: List of category strings
            data_sources: Optional filter by data sources
        
        Returns:
            List of matching project metadata
        """
        if self._metadata is None:
            self.load()
        
        matching_projects = []
        categories_set = set(categories)
        
        for project in self._projects:
            # Check category match
            project_cats = set(project.categories)
            if not (project_cats & categories_set):
                continue
            
            # Check data source match if provided
            if data_sources:
                project_ds = {ds.lower() for ds in project.data_sources}
                requested_ds = {ds.lower().split(".")[0] for ds in data_sources}
                if not (project_ds & requested_ds):
                    continue
            
            matching_projects.append(project)
        
        return matching_projects
    
    def get_project_ids_for_categories(
        self,
        categories: List[str],
        data_sources: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Get project IDs that match the given categories.
        
        Args:
            categories: List of category strings
            data_sources: Optional filter by data sources
        
        Returns:
            List of project_id strings
        """
        projects = self.find_projects_by_categories(categories, data_sources)
        return [p.project_id for p in projects]
    
    def get_all_categories(self) -> List[str]:
        """Get all unique categories from all projects."""
        if self._metadata is None:
            self.load()
        
        all_categories: Set[str] = set()
        for project in self._projects:
            all_categories.update(project.categories)
        
        return sorted(list(all_categories))


# Global singleton instance
_metadata_loader: Optional[CSODProjectMetadataLoader] = None


def get_csod_metadata_loader() -> CSODProjectMetadataLoader:
    """Get or create the global CSOD metadata loader instance."""
    global _metadata_loader
    if _metadata_loader is None:
        _metadata_loader = CSODProjectMetadataLoader()
        _metadata_loader.load()
    return _metadata_loader
