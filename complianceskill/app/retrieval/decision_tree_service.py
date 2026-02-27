"""
Decision Tree Retrieval Service

Retrieval service for metrics and control taxonomy from Qdrant vector store.
Supports semantic search with filtering by framework, use_case, category, etc.

Follows the pattern from retrieval/xsoar_service.py and retrieval/mdl_service.py.
"""
import logging
import json
from typing import Dict, List, Optional, Any

from app.core.dependencies import get_doc_store_provider
from app.ingestion.embedder import EmbeddingService
from app.utils.cache import InMemoryCache
from app.retrieval.decision_tree_results import (
    MetricResult,
    ControlTaxonomyResult,
    DecisionTreeRetrievedContext,
)

logger = logging.getLogger(__name__)


class DecisionTreeRetrievalService:
    """
    Retrieval service for decision tree metrics and control taxonomy.
    
    Usage:
        service = DecisionTreeRetrievalService()
        
        # Search metrics
        ctx = service.search_metrics("vulnerability count by severity", limit=10)
        
        # Search control taxonomy
        ctx = service.search_control_taxonomy("CC7.1 vulnerability monitoring", limit=5)
        
        # Search with filters
        ctx = service.search_metrics(
            "compliance posture metrics",
            framework_filter="soc2",
            use_case_filter="soc2_audit",
            limit=10
        )
    """
    
    def __init__(
        self,
        doc_store_provider=None,
        embedder: Optional[EmbeddingService] = None
    ):
        """
        Initialize decision tree retrieval service.
        
        Args:
            doc_store_provider: Optional DocumentStoreProvider instance
            embedder: Optional EmbeddingService instance
        """
        self._embedder = embedder or EmbeddingService()
        self._doc_stores = doc_store_provider or get_doc_store_provider()
        self._cache = InMemoryCache()
        
        # Get document stores for metrics and control taxonomy
        stores = self._doc_stores.stores if hasattr(self._doc_stores, 'stores') else {}
        
        # Try to get metrics registry store (from MDL collections)
        self._metrics_store = stores.get("metrics_registry") or stores.get("leen_metrics_registry")
        
        # Try to get control taxonomy store (may be in framework collections or separate)
        self._taxonomy_store = stores.get("control_taxonomy") or stores.get("framework_controls")
        
        if not self._metrics_store:
            logger.warning("metrics_registry store not available. Metric retrieval may not work.")
        if not self._taxonomy_store:
            logger.warning("control_taxonomy store not available. Taxonomy retrieval may not work.")
    
    def _format_metric_result(self, result: Dict) -> Optional[MetricResult]:
        """Format raw document store result into MetricResult."""
        try:
            content = result.get("content", {})
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)
            doc_id = result.get("id", "")
            
            # Handle both dict and string content
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    # If not JSON, treat as description
                    content = {"description": content}
            
            # Extract metric ID from various possible fields
            metric_id = (
                content.get("id") or 
                content.get("metric_id") or 
                metadata.get("id") or 
                metadata.get("metric_id") or 
                doc_id
            )
            
            # Extract name
            name = (
                content.get("name") or 
                metadata.get("name") or 
                metric_id
            )
            
            return MetricResult(
                metric_id=str(metric_id),
                name=str(name),
                description=content.get("description") or metadata.get("description"),
                category=content.get("category") or metadata.get("category"),
                goals=content.get("goals") or metadata.get("goals"),
                focus_areas=content.get("focus_areas") or metadata.get("focus_areas"),
                use_cases=content.get("use_cases") or metadata.get("use_cases"),
                audience_levels=content.get("audience_levels") or metadata.get("audience_levels"),
                metric_type=content.get("metric_type") or metadata.get("metric_type"),
                aggregation_windows=content.get("aggregation_windows") or metadata.get("aggregation_windows"),
                group_affinity=content.get("group_affinity") or metadata.get("group_affinity"),
                source_schemas=content.get("source_schemas") or metadata.get("source_schemas"),
                source_capabilities=content.get("source_capabilities") or metadata.get("source_capabilities"),
                kpis=content.get("kpis") or metadata.get("kpis"),
                trends=content.get("trends") or metadata.get("trends"),
                data_filters=content.get("data_filters") or metadata.get("data_filters"),
                data_groups=content.get("data_groups") or metadata.get("data_groups"),
                natural_language_question=content.get("natural_language_question") or metadata.get("natural_language_question"),
                mapped_control_codes=content.get("mapped_control_codes") or metadata.get("mapped_control_codes"),
                mapped_control_domains=content.get("mapped_control_domains") or metadata.get("mapped_control_domains"),
                mapped_risk_categories=content.get("mapped_risk_categories") or metadata.get("mapped_risk_categories"),
                control_evidence_hints=content.get("control_evidence_hints") or metadata.get("control_evidence_hints"),
                risk_quantification_hints=content.get("risk_quantification_hints") or metadata.get("risk_quantification_hints"),
                scenario_detection_hints=content.get("scenario_detection_hints") or metadata.get("scenario_detection_hints"),
                enrichment_source=content.get("enrichment_source") or metadata.get("enrichment_source"),
                metadata=metadata,
                score=score,
                id=doc_id,
            )
        except Exception as e:
            logger.warning(f"Error formatting metric result: {e}")
            return None
    
    def _format_taxonomy_result(self, result: Dict) -> Optional[ControlTaxonomyResult]:
        """Format raw document store result into ControlTaxonomyResult."""
        try:
            content = result.get("content", {})
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)
            doc_id = result.get("id", "")
            
            # Handle both dict and string content
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    content = {}
            
            # Extract control code
            control_code = (
                content.get("control_code") or 
                metadata.get("control_code") or 
                metadata.get("code") or 
                doc_id
            )
            
            return ControlTaxonomyResult(
                control_code=str(control_code),
                domain=content.get("domain") or metadata.get("domain"),
                sub_domain=content.get("sub_domain") or metadata.get("sub_domain"),
                measurement_goal=content.get("measurement_goal") or metadata.get("measurement_goal"),
                focus_areas=content.get("focus_areas") or metadata.get("focus_areas"),
                risk_categories=content.get("risk_categories") or metadata.get("risk_categories"),
                metric_type_preferences=content.get("metric_type_preferences") or metadata.get("metric_type_preferences"),
                evidence_requirements=content.get("evidence_requirements") or metadata.get("evidence_requirements"),
                affinity_keywords=content.get("affinity_keywords") or metadata.get("affinity_keywords"),
                control_type_classification=content.get("control_type_classification") or metadata.get("control_type_classification"),
                differentiation_note=content.get("differentiation_note") or metadata.get("differentiation_note"),
                metadata=metadata,
                score=score,
                id=doc_id,
            )
        except Exception as e:
            logger.warning(f"Error formatting taxonomy result: {e}")
            return None
    
    def search_metrics(
        self,
        query: str,
        limit: int = 10,
        framework_filter: Optional[str] = None,
        use_case_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        goal_filter: Optional[List[str]] = None,
        focus_area_filter: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> List[MetricResult]:
        """
        Search metrics by semantic similarity.
        
        Args:
            query: Natural language query
            limit: Max results to return
            framework_filter: Filter by framework (e.g., "soc2")
            use_case_filter: Filter by use case (e.g., "soc2_audit")
            category_filter: Filter by metric category
            goal_filter: Filter by goals (list)
            focus_area_filter: Filter by focus areas (list)
            project_id: Optional project ID filter
        
        Returns:
            List of MetricResult objects
        """
        if not self._metrics_store:
            logger.warning("Metrics store not available")
            return []
        
        try:
            # Build where clause for filtering
            where = {}
            if framework_filter:
                where["framework_id"] = framework_filter
            if use_case_filter:
                where["use_case"] = use_case_filter
            if category_filter:
                where["category"] = category_filter
            if goal_filter:
                # For list filters, use $in operator if supported
                where["goals"] = {"$in": goal_filter} if isinstance(goal_filter, list) else goal_filter
            if focus_area_filter:
                where["focus_areas"] = {"$in": focus_area_filter} if isinstance(focus_area_filter, list) else focus_area_filter
            if project_id:
                where["project_id"] = project_id
            
            # Combine filters with $and if multiple filters
            if len(where) > 1:
                where = {"$and": [{"k": k, "v": v} for k, v in where.items()]}
            
            # Perform semantic search
            results = self._metrics_store.semantic_search(
                query=query,
                k=limit,
                where=where if where else None
            )
            
            formatted_results = []
            for result in results:
                formatted = self._format_metric_result(result)
                if formatted:
                    formatted_results.append(formatted)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching metrics: {e}", exc_info=True)
            return []
    
    def search_control_taxonomy(
        self,
        query: str,
        limit: int = 10,
        framework_filter: Optional[str] = None,
        control_code_filter: Optional[str] = None,
        domain_filter: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[ControlTaxonomyResult]:
        """
        Search control taxonomy by semantic similarity.
        
        Args:
            query: Natural language query
            limit: Max results to return
            framework_filter: Filter by framework (e.g., "soc2")
            control_code_filter: Filter by specific control code (e.g., "CC7.1")
            domain_filter: Filter by domain
            project_id: Optional project ID filter
        
        Returns:
            List of ControlTaxonomyResult objects
        """
        if not self._taxonomy_store:
            logger.warning("Control taxonomy store not available")
            return []
        
        try:
            # Build where clause for filtering
            where = {}
            if framework_filter:
                where["framework_id"] = framework_filter
            if control_code_filter:
                where["control_code"] = control_code_filter
            if domain_filter:
                where["domain"] = domain_filter
            if project_id:
                where["project_id"] = project_id
            
            # Combine filters with $and if multiple filters
            if len(where) > 1:
                where = {"$and": [{"k": k, "v": v} for k, v in where.items()]}
            
            # Perform semantic search
            results = self._taxonomy_store.semantic_search(
                query=query,
                k=limit,
                where=where if where else None
            )
            
            formatted_results = []
            for result in results:
                formatted = self._format_taxonomy_result(result)
                if formatted:
                    formatted_results.append(formatted)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching control taxonomy: {e}", exc_info=True)
            return []
    
    def search_all(
        self,
        query: str,
        metrics_limit: int = 10,
        taxonomy_limit: int = 5,
        framework_filter: Optional[str] = None,
        use_case_filter: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> DecisionTreeRetrievedContext:
        """
        Search both metrics and control taxonomy simultaneously.
        
        Args:
            query: Natural language query
            metrics_limit: Max metric results
            taxonomy_limit: Max taxonomy results
            framework_filter: Filter by framework
            use_case_filter: Filter by use case
            project_id: Optional project ID filter
        
        Returns:
            DecisionTreeRetrievedContext with results from both searches
        """
        warnings = []
        
        # Search metrics
        try:
            metrics = self.search_metrics(
                query=query,
                limit=metrics_limit,
                framework_filter=framework_filter,
                use_case_filter=use_case_filter,
                project_id=project_id,
            )
        except Exception as e:
            logger.error(f"Error searching metrics: {e}", exc_info=True)
            metrics = []
            warnings.append(f"Error searching metrics: {str(e)}")
        
        # Search taxonomy
        try:
            taxonomy = self.search_control_taxonomy(
                query=query,
                limit=taxonomy_limit,
                framework_filter=framework_filter,
                project_id=project_id,
            )
        except Exception as e:
            logger.error(f"Error searching control taxonomy: {e}", exc_info=True)
            taxonomy = []
            warnings.append(f"Error searching control taxonomy: {str(e)}")
        
        return DecisionTreeRetrievedContext(
            query=query,
            metrics=metrics,
            control_taxonomy=taxonomy,
            warnings=warnings if warnings else None,
        )
    
    def get_metric_by_id(self, metric_id: str) -> Optional[MetricResult]:
        """
        Direct lookup of a metric by ID.
        
        Args:
            metric_id: Metric ID
        
        Returns:
            MetricResult or None if not found
        """
        if not self._metrics_store:
            return None
        
        try:
            # Try to get by ID (exact match)
            # Note: This depends on the document store implementation
            # Some stores support get_by_id, others require search with filter
            results = self._metrics_store.semantic_search(
                query=metric_id,
                k=1,
                where={"id": metric_id} if hasattr(self._metrics_store, 'semantic_search') else None
            )
            
            if results:
                return self._format_metric_result(results[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting metric by ID: {e}", exc_info=True)
            return None
    
    def get_taxonomy_by_control_code(
        self,
        control_code: str,
        framework_filter: Optional[str] = None,
    ) -> Optional[ControlTaxonomyResult]:
        """
        Direct lookup of control taxonomy by control code.
        
        Args:
            control_code: Control code (e.g., "CC7.1")
            framework_filter: Optional framework filter
        
        Returns:
            ControlTaxonomyResult or None if not found
        """
        if not self._taxonomy_store:
            return None
        
        try:
            where = {"control_code": control_code}
            if framework_filter:
                where["framework_id"] = framework_filter
            
            results = self._taxonomy_store.semantic_search(
                query=control_code,
                k=1,
                where=where
            )
            
            if results:
                return self._format_taxonomy_result(results[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting taxonomy by control code: {e}", exc_info=True)
            return None
