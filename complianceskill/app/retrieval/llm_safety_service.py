"""
LLM Safety Retrieval Service

Retrieval service for LLM Safety collection (techniques, mitigations, detection rules).

Follows the pattern from XSOARRetrievalService.
"""
import logging
from typing import Dict, List, Optional, Any
import hashlib
import json

from app.core.dependencies import get_doc_store_provider
from app.ingestion.embedder import EmbeddingService
from app.utils.cache import InMemoryCache
from app.storage.collections import LLMSafetyCollections
from app.retrieval.llm_safety_results import (
    LLMSafetyTechniqueResult,
    LLMSafetyMitigationResult,
    LLMSafetyDetectionRuleResult,
    LLMSafetyRetrievedContext,
)

logger = logging.getLogger(__name__)


class LLMSafetyRetrievalService:
    """Retrieval service for LLM Safety collection."""
    
    def __init__(
        self,
        doc_store_provider=None,
        embedder: Optional[EmbeddingService] = None
    ):
        """
        Initialize LLM Safety retrieval service.
        
        Args:
            doc_store_provider: Optional DocumentStoreProvider instance
            embedder: Optional EmbeddingService instance
        """
        self._embedder = embedder or EmbeddingService()
        self._doc_stores = doc_store_provider or get_doc_store_provider()
        self._cache = InMemoryCache()
        
        # Get LLM Safety document store
        stores = self._doc_stores.stores if hasattr(self._doc_stores, 'stores') else {}
        self._llm_safety_store = stores.get(LLMSafetyCollections.SAFETY)
        
        if not self._llm_safety_store:
            logger.warning(f"{LLMSafetyCollections.SAFETY} store not available. LLM Safety retrieval may not work.")
    
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
            
            return {
                "content": content,
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
        technique_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generic search method with entity_type filtering."""
        cache_key = self._get_cache_key(
            f"search_{entity_type}", query, limit, technique_id
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if not self._llm_safety_store:
                logger.warning(f"{LLMSafetyCollections.SAFETY} store not available")
                return []
            
            # Build where clause with artifact_type filter
            # Note: DocumentQdrantStore will map artifact_type to top-level field (not nested)
            where = {"artifact_type": entity_type}
            
            # Optionally filter by technique_id (for detection rules)
            if technique_id and entity_type == "detection_rule":
                where = {
                    "$and": [
                        {"artifact_type": entity_type},
                        {"technique_id": technique_id}
                    ]
                }
            
            results = self._llm_safety_store.semantic_search(
                query=query,
                k=limit,
                where=where
            )
            
            # Ensure results is a list (handle None case)
            if results is None:
                results = []
            
            formatted_results = []
            for result in results:
                formatted = self._format_result(result)
                if formatted:
                    formatted_results.append(formatted)
            
            if formatted_results:
                await self._cache.set(cache_key, formatted_results, ttl=300)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching LLM Safety {entity_type}: {e}", exc_info=True)
            return []
    
    async def search_techniques(
        self,
        query: str,
        limit: int = 5
    ) -> List[LLMSafetyTechniqueResult]:
        """Search LLM Safety techniques (artifact_type="technique")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="technique",
            limit=limit
        )
        
        formatted_results = []
        for result in raw_results:
            if result is None:
                continue
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
            content = result.get("content", "") if isinstance(result, dict) else ""
            
            technique_result = LLMSafetyTechniqueResult(
                technique_id=metadata.get("artifact_id", "") if isinstance(metadata, dict) else "",
                title=metadata.get("title", "") if isinstance(metadata, dict) else "",
                description=metadata.get("description", "") if isinstance(metadata, dict) else "",
                content=content,
                severity=metadata.get("severity") if isinstance(metadata, dict) else None,
                category=metadata.get("category") if isinstance(metadata, dict) else None,
                tactic=metadata.get("tactic") if isinstance(metadata, dict) else None,
                keywords=metadata.get("keywords", []) if isinstance(metadata, dict) else [],
                has_detection_rule=metadata.get("has_detection_rule", False) if isinstance(metadata, dict) else False,
                detection_rule_title=metadata.get("detection_rule_title") if isinstance(metadata, dict) else None,
                detection_rule_level=metadata.get("detection_rule_level") if isinstance(metadata, dict) else None,
                metadata=metadata if isinstance(metadata, dict) else {},
                score=result.get("score", 0.0) if isinstance(result, dict) else 0.0,
                id=result.get("id", "") if isinstance(result, dict) else ""
            )
            formatted_results.append(technique_result)
        
        return formatted_results
    
    async def search_mitigations(
        self,
        query: str,
        limit: int = 5
    ) -> List[LLMSafetyMitigationResult]:
        """Search LLM Safety mitigations (artifact_type="mitigation")."""
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="mitigation",
            limit=limit
        )
        
        formatted_results = []
        for result in raw_results:
            if result is None:
                continue
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
            content = result.get("content", "") if isinstance(result, dict) else ""
            
            mitigation_result = LLMSafetyMitigationResult(
                mitigation_id=metadata.get("artifact_id", "") if isinstance(metadata, dict) else "",
                title=metadata.get("title", "") if isinstance(metadata, dict) else "",
                description=metadata.get("description", "") if isinstance(metadata, dict) else "",
                content=content,
                category=metadata.get("category") if isinstance(metadata, dict) else None,
                effectiveness=metadata.get("effectiveness") if isinstance(metadata, dict) else None,
                implementation_complexity=metadata.get("implementation_complexity") if isinstance(metadata, dict) else None,
                keywords=metadata.get("keywords", []) if isinstance(metadata, dict) else [],
                metadata=metadata if isinstance(metadata, dict) else {},
                score=result.get("score", 0.0) if isinstance(result, dict) else 0.0,
                id=result.get("id", "") if isinstance(result, dict) else ""
            )
            formatted_results.append(mitigation_result)
        
        return formatted_results
    
    async def search_detection_rules(
        self,
        query: str,
        limit: int = 5,
        technique_id: Optional[str] = None
    ) -> List[LLMSafetyDetectionRuleResult]:
        """
        Search LLM Safety detection rules (artifact_type="detection_rule").
        
        Args:
            query: Natural language query
            limit: Maximum number of results
            technique_id: Optional technique ID to filter by
            
        Returns:
            List of detection rule results
        """
        raw_results = await self._search_by_entity_type(
            query=query,
            entity_type="detection_rule",
            limit=limit,
            technique_id=technique_id
        )
        
        formatted_results = []
        for result in raw_results:
            if result is None:
                continue
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
            content = result.get("content", "") if isinstance(result, dict) else ""
            
            detection_rule_result = LLMSafetyDetectionRuleResult(
                rule_id=(metadata.get("rule_id", "") or metadata.get("artifact_id", "")) if isinstance(metadata, dict) else "",
                title=metadata.get("title", "") if isinstance(metadata, dict) else "",
                description=metadata.get("description", "") if isinstance(metadata, dict) else "",
                content=content,  # Full YAML content
                technique_id=metadata.get("technique_id") if isinstance(metadata, dict) else None,
                technique_title=metadata.get("technique_title") if isinstance(metadata, dict) else None,
                status=metadata.get("status") if isinstance(metadata, dict) else None,
                level=metadata.get("level") if isinstance(metadata, dict) else None,
                tags=metadata.get("tags", []) if isinstance(metadata, dict) else [],
                logsource=metadata.get("logsource") if isinstance(metadata, dict) else None,
                metadata=metadata if isinstance(metadata, dict) else {},
                score=result.get("score", 0.0) if isinstance(result, dict) else 0.0,
                id=result.get("id", "") if isinstance(result, dict) else ""
            )
            formatted_results.append(detection_rule_result)
        
        return formatted_results
    
    async def search_detection_rules_by_technique(
        self,
        technique_id: str,
        limit: int = 5
    ) -> List[LLMSafetyDetectionRuleResult]:
        """
        Search detection rules for a specific technique.
        
        Args:
            technique_id: Technique ID (e.g., "SAFE-T1001")
            limit: Maximum number of results
            
        Returns:
            List of detection rule results for the technique
        """
        # Use a generic query to find all rules for this technique
        return await self.search_detection_rules(
            query=f"detection rule for {technique_id}",
            limit=limit,
            technique_id=technique_id
        )
    
    async def search_all_llm_safety(
        self,
        query: str,
        limit_per_entity_type: int = 3,
        entity_types: Optional[List[str]] = None
    ) -> LLMSafetyRetrievedContext:
        """
        Search all LLM Safety entity types simultaneously and merge results.
        
        Args:
            query: Natural language query
            limit_per_entity_type: Max results per entity type
            entity_types: Optional list of entity types to search.
                         If None, searches all: technique, mitigation, detection_rule
            
        Returns:
            LLMSafetyRetrievedContext with results from all entity types
        """
        if entity_types is None:
            entity_types = ["technique", "mitigation", "detection_rule"]
        
        # Search all entity types in parallel
        import asyncio
        
        # Create coroutines for each entity type search
        async def empty_list():
            return []
        
        tasks = []
        if "technique" in entity_types:
            tasks.append(self.search_techniques(query, limit_per_entity_type))
        else:
            tasks.append(empty_list())
        
        if "mitigation" in entity_types:
            tasks.append(self.search_mitigations(query, limit_per_entity_type))
        else:
            tasks.append(empty_list())
        
        if "detection_rule" in entity_types:
            tasks.append(self.search_detection_rules(query, limit_per_entity_type))
        else:
            tasks.append(empty_list())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions gracefully
        techniques = results[0] if not isinstance(results[0], Exception) else []
        mitigations = results[1] if not isinstance(results[1], Exception) else []
        detection_rules = results[2] if not isinstance(results[2], Exception) else []
        
        # Log exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                entity_names = ["techniques", "mitigations", "detection_rules"]
                if i < len(entity_names):
                    logger.error(f"Error searching {entity_names[i]}: {result}")
        
        return LLMSafetyRetrievedContext(
            query=query,
            techniques=techniques if isinstance(techniques, list) else [],
            mitigations=mitigations if isinstance(mitigations, list) else [],
            detection_rules=detection_rules if isinstance(detection_rules, list) else [],
            total_hits=0  # Will be calculated in __post_init__
        )
