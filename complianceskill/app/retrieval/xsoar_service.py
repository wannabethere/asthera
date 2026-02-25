"""
XSOAR Retrieval Service

Retrieval service for XSOAR enriched collection with entity_type filtering.

Follows the pattern from knowledge/app/agents/data/retrieval_helper.py.
"""
import logging
from typing import Dict, List, Optional, Any
import hashlib
import json

from app.core.dependencies import get_doc_store_provider
from app.ingestion.embedder import EmbeddingService
from app.utils.cache import InMemoryCache
from app.retrieval.xsoar_results import (
    XSOARPlaybookResult,
    XSOARDashboardResult,
    XSOARScriptResult,
    XSOARIntegrationResult,
    XSOARIndicatorResult,
    XSOARRetrievedContext,
)

logger = logging.getLogger(__name__)


class XSOARRetrievalService:
    """Retrieval service for XSOAR enriched collection."""
    
    def __init__(
        self,
        doc_store_provider=None,
        embedder: Optional[EmbeddingService] = None
    ):
        """
        Initialize XSOAR retrieval service.
        
        Args:
            doc_store_provider: Optional DocumentStoreProvider instance
            embedder: Optional EmbeddingService instance
        """
        self._embedder = embedder or EmbeddingService()
        self._doc_stores = doc_store_provider or get_doc_store_provider()
        self._cache = InMemoryCache()
        
        # Get XSOAR document store
        stores = self._doc_stores.stores if hasattr(self._doc_stores, 'stores') else {}
        self._xsoar_store = stores.get("xsoar_enriched")
        
        if not self._xsoar_store:
            logger.warning("xsoar_enriched store not available. XSOAR retrieval may not work.")
    
    def _get_cache_key(self, method: str, *args) -> str:
        """Generate cache key from method name and arguments."""
        key_data = {"method": method, "args": args}
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True, default=str).encode()
        ).hexdigest()
    
    def _format_result(self, result: Dict) -> Optional[Dict[str, Any]]:
        """Format raw document store result into structured format."""
        try:
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)
            doc_id = result.get("id", "")
            
            # Try to parse content if it's a JSON string
            parsed_content = content
            if isinstance(content, str):
                try:
                    parsed_content = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    # Keep as string if not JSON
                    pass
            
            return {
                "content": parsed_content if isinstance(parsed_content, dict) else content,
                "metadata": metadata,
                "score": score,
                "id": doc_id
            }
        except Exception as e:
            logger.warning(f"Error formatting result: {e}")
            return None
    
    async def _search_by_entity_type(
        self,
        query: str,
        entity_type: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generic search method with entity_type filtering."""
        cache_key = self._get_cache_key(
            f"search_{entity_type}", query, limit, project_id
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._xsoar_store:
                logger.warning("xsoar_enriched store not available")
                return []
            
            # Build where clause with entity_type filter
            # Note: DocumentChromaStore/DocumentQdrantStore handle filter normalization
            # For ChromaDB: {"entity_type": {"$eq": entity_type}} or {"entity_type": entity_type}
            # For Qdrant: {"entity_type": entity_type} (direct match)
            # The document store's semantic_search will normalize the filter format
            where = {"entity_type": entity_type}
            if project_id:
                where = {
                    "$and": [
                        {"entity_type": entity_type},
                        {"project_id": project_id}
                    ]
                }
            
            results = self._xsoar_store.semantic_search(
                query=query,
                k=limit,
                where=where
            )
            
            formatted_results = []
            for result in results:
                formatted = self._format_result(result)
                if formatted:
                    formatted_results.append(formatted)
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching XSOAR {entity_type}: {e}", exc_info=True)
            return []
    
    async def search_playbooks(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[XSOARPlaybookResult]:
        """Search XSOAR playbooks (entity_type="playbook")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="playbook",
            limit=limit,
            project_id=project_id
        )
        
        formatted_results = []
        for result in raw_results:
            content = result.get("content", {}) if isinstance(result.get("content"), dict) else {}
            metadata = result.get("metadata", {})
            
            playbook_result = XSOARPlaybookResult(
                playbook_id=metadata.get("id", "") or content.get("id", ""),
                playbook_name=metadata.get("name", "") or content.get("name", ""),
                content=str(result.get("content", "")),
                tasks=content.get("tasks", []) if isinstance(content, dict) else [],
                metadata=metadata,
                score=result.get("score", 0.0),
                id=result.get("id", "")
            )
            formatted_results.append(playbook_result)
        
        return formatted_results
    
    async def search_dashboards(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[XSOARDashboardResult]:
        """Search XSOAR dashboards (entity_type="dashboard")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="dashboard",
            limit=limit,
            project_id=project_id
        )
        
        formatted_results = []
        for result in raw_results:
            content = result.get("content", {}) if isinstance(result.get("content"), dict) else {}
            metadata = result.get("metadata", {})
            
            dashboard_result = XSOARDashboardResult(
                dashboard_id=metadata.get("id", "") or content.get("id", ""),
                dashboard_name=metadata.get("name", "") or content.get("name", ""),
                widgets=content.get("widgets", []) if isinstance(content, dict) else [],
                metadata=metadata,
                score=result.get("score", 0.0),
                id=result.get("id", "")
            )
            formatted_results.append(dashboard_result)
        
        return formatted_results
    
    async def search_scripts(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[XSOARScriptResult]:
        """Search XSOAR scripts (entity_type="script")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="script",
            limit=limit,
            project_id=project_id
        )
        
        formatted_results = []
        for result in raw_results:
            content = result.get("content", {}) if isinstance(result.get("content"), dict) else {}
            metadata = result.get("metadata", {})
            
            script_result = XSOARScriptResult(
                script_id=metadata.get("id", "") or content.get("id", ""),
                script_name=metadata.get("name", "") or content.get("name", ""),
                content=str(result.get("content", "")),
                script_type=metadata.get("script_type", "") or content.get("type", ""),
                metadata=metadata,
                score=result.get("score", 0.0),
                id=result.get("id", "")
            )
            formatted_results.append(script_result)
        
        return formatted_results
    
    async def search_integrations(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[XSOARIntegrationResult]:
        """Search XSOAR integrations (entity_type="integration")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="integration",
            limit=limit,
            project_id=project_id
        )
        
        formatted_results = []
        for result in raw_results:
            content = result.get("content", {}) if isinstance(result.get("content"), dict) else {}
            metadata = result.get("metadata", {})
            
            integration_result = XSOARIntegrationResult(
                integration_id=metadata.get("id", "") or content.get("id", ""),
                integration_name=metadata.get("name", "") or content.get("name", ""),
                content=str(result.get("content", "")),
                commands=content.get("commands", []) if isinstance(content, dict) else [],
                metadata=metadata,
                score=result.get("score", 0.0),
                id=result.get("id", "")
            )
            formatted_results.append(integration_result)
        
        return formatted_results
    
    async def search_indicators(
        self,
        query: str,
        limit: int = 5,
        project_id: Optional[str] = None
    ) -> List[XSOARIndicatorResult]:
        """Search XSOAR indicators (entity_type="indicator")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="indicator",
            limit=limit,
            project_id=project_id
        )
        
        formatted_results = []
        for result in raw_results:
            content = result.get("content", {}) if isinstance(result.get("content"), dict) else {}
            metadata = result.get("metadata", {})
            
            indicator_result = XSOARIndicatorResult(
                indicator_id=metadata.get("id", "") or content.get("id", ""),
                indicator_name=metadata.get("name", "") or content.get("name", ""),
                indicator_type=metadata.get("indicator_type", "") or content.get("type", ""),
                content=str(result.get("content", "")),
                regex=content.get("regex", "") if isinstance(content, dict) else None,
                metadata=metadata,
                score=result.get("score", 0.0),
                id=result.get("id", "")
            )
            formatted_results.append(indicator_result)
        
        return formatted_results
    
    async def search_all_xsoar(
        self,
        query: str,
        limit_per_entity_type: int = 3,
        project_id: Optional[str] = None,
        entity_types: Optional[List[str]] = None
    ) -> XSOARRetrievedContext:
        """
        Search all XSOAR entity types simultaneously and merge results.
        
        Args:
            query: Natural language query
            limit_per_entity_type: Max results per entity type
            project_id: Optional project ID filter
            entity_types: Optional list of entity types to search.
                         If None, searches all: playbook, dashboard, script, integration
            
        Returns:
            XSOARRetrievedContext with results from all entity types
        """
        if entity_types is None:
            entity_types = ["playbook", "dashboard", "script", "integration", "indicator"]
        
        # Search all entity types in parallel
        import asyncio
        
        # Create coroutines for each entity type search
        async def empty_list():
            return []
        
        tasks = []
        if "playbook" in entity_types:
            tasks.append(self.search_playbooks(query, limit_per_entity_type, project_id))
        else:
            tasks.append(empty_list())
        
        if "dashboard" in entity_types:
            tasks.append(self.search_dashboards(query, limit_per_entity_type, project_id))
        else:
            tasks.append(empty_list())
        
        if "script" in entity_types:
            tasks.append(self.search_scripts(query, limit_per_entity_type, project_id))
        else:
            tasks.append(empty_list())
        
        if "integration" in entity_types:
            tasks.append(self.search_integrations(query, limit_per_entity_type, project_id))
        else:
            tasks.append(empty_list())
        
        if "indicator" in entity_types:
            tasks.append(self.search_indicators(query, limit_per_entity_type, project_id))
        else:
            tasks.append(empty_list())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions gracefully
        playbooks = results[0] if not isinstance(results[0], Exception) else []
        dashboards = results[1] if not isinstance(results[1], Exception) else []
        scripts = results[2] if not isinstance(results[2], Exception) else []
        integrations = results[3] if not isinstance(results[3], Exception) else []
        indicators = results[4] if len(results) > 4 and not isinstance(results[4], Exception) else []
        
        # Log exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                entity_names = ["playbooks", "dashboards", "scripts", "integrations", "indicators"]
                if i < len(entity_names):
                    logger.error(f"Error searching {entity_names[i]}: {result}")
        
        return XSOARRetrievedContext(
            query=query,
            playbooks=playbooks if isinstance(playbooks, list) else [],
            dashboards=dashboards if isinstance(dashboards, list) else [],
            scripts=scripts if isinstance(scripts, list) else [],
            integrations=integrations if isinstance(integrations, list) else [],
            indicators=indicators if isinstance(indicators, list) else [],
            total_hits=0  # Will be calculated in __post_init__
        )
