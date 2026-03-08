"""
Dashboard Template Retrieval Service

Retrieval service for dashboard templates using the unified registry.
Supports both semantic search (vector store) and rule-based scoring.

Uses doc store from dependencies (ChromaDB or Qdrant per VECTOR_STORE_TYPE)
for semantic search. Falls back to rule-based scoring when store is empty/unavailable.
"""
import logging
import json
from typing import Dict, List, Optional, Any

from app.services.dashboard_template_results import (
    DashboardTemplateResult,
    DashboardTemplateRetrievedContext,
)
from app.services.dashboard_template_vector_store import (
    ALL_TEMPLATES,
    ALL_CATEGORIES,
    score_templates_hybrid,
)

logger = logging.getLogger(__name__)


class DashboardTemplateRetrievalService:
    """
    Retrieval service for dashboard templates.
    
    Uses get_doc_store_provider().get_store("dashboard_templates") for semantic search.
    Collection and store type (ChromaDB/Qdrant) come from dependencies/settings.
    
    Usage:
        service = DashboardTemplateRetrievalService()
        
        # Semantic search
        ctx = service.search_templates("SOC2 compliance monitoring with AI chat", k=5)
        
        # Search with decisions
        ctx = service.search_by_decisions(
            {"category": ["compliance"], "has_chat": True, "domain": "security"},
            k=5
        )
        
        # Direct lookup
        template = service.get_template("command-center")
    """
    
    def __init__(self):
        """Initialize dashboard template retrieval service. Uses doc store from dependencies."""
        self._templates = ALL_TEMPLATES
        self._categories = ALL_CATEGORIES
        self._doc_store = None  # Lazy-loaded from get_doc_store_provider
        
        logger.info(f"Initialized DashboardTemplateRetrievalService with {len(self._templates)} templates")
    
    def _get_doc_store(self):
        """Lazy-load dashboard_templates doc store from dependencies (ChromaDB or Qdrant)."""
        if self._doc_store is False:
            return None  # Cached failure
        if self._doc_store is None:
            try:
                from app.core.dependencies import get_doc_store_provider
                provider = get_doc_store_provider()
                self._doc_store = provider.get_store("dashboard_templates")
                if not self._doc_store:
                    self._doc_store = False
            except Exception as e:
                logger.debug(f"dashboard_templates doc store unavailable: {e}")
                self._doc_store = False
        return self._doc_store if self._doc_store else None

    def _template_to_result(
        self,
        template: Dict[str, Any],
        similarity_score: Optional[float] = None,
    ) -> DashboardTemplateResult:
        """Convert template dict to DashboardTemplateResult."""
        category_info = self._categories.get(template.get("category", ""), {})
        
        return DashboardTemplateResult(
            template_id=template["id"],
            name=template["name"],
            description=template.get("description"),
            category=template.get("category"),
            category_label=category_info.get("label"),
            icon=template.get("icon"),
            domains=template.get("domains", []),
            complexity=template.get("complexity"),
            has_chat=template.get("has_chat", False),
            has_graph=template.get("has_graph", False),
            has_filters=template.get("has_filters", False),
            strip_cells=template.get("strip_cells", 0),
            best_for=template.get("best_for", []),
            primitives=template.get("primitives", []),
            theme_hint=template.get("theme_hint"),
            similarity_score=similarity_score,
            chart_types=template.get("chart_types", []),
            activity_types=template.get("activity_types", []),
            table_columns=template.get("table_columns"),
            strip_example=template.get("strip_example", []),
            card_anatomy=template.get("card_anatomy"),
            layout_grid=template.get("layout_grid"),
            panels=template.get("panels"),
            filter_options=template.get("filter_options", []),
            metadata=template,
        )
    
    def search_templates(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> DashboardTemplateRetrievedContext:
        """
        Semantic search across templates via doc store (ChromaDB or Qdrant per dependencies).
        
        Args:
            query: Natural language query
            k: Number of results to return
            filter_dict: Optional metadata filters (e.g., {"category": "compliance"})
        
        Returns:
            DashboardTemplateRetrievedContext with matching templates
        """
        try:
            store = self._get_doc_store()
            if not store:
                logger.debug("dashboard_templates store unavailable, returning empty")
                return DashboardTemplateRetrievedContext(
                    query=query,
                    templates=[],
                    total_hits=0,
                    warnings=["Vector store unavailable; run ingest_dashboard_templates to index templates"],
                )
            
            where = filter_dict if filter_dict else None
            results = store.semantic_search(query=query, k=max(1, k), where=where)
            
            template_results = []
            for r in results:
                meta = r.get("metadata", {})
                tid = meta.get("template_id")
                if not tid:
                    continue
                template = self._templates.get(tid)
                if not template:
                    logger.warning(f"Template {tid} not found in registry")
                    continue
                
                similarity = float(r.get("score", 0.0))
                result = self._template_to_result(template, similarity_score=round(similarity, 4))
                template_results.append(result)
            
            return DashboardTemplateRetrievedContext(
                query=query,
                templates=template_results,
                total_hits=len(template_results),
            )
        
        except Exception as e:
            logger.error(f"Error in semantic search: {e}", exc_info=True)
            return DashboardTemplateRetrievedContext(
                query=query,
                templates=[],
                total_hits=0,
                warnings=[f"Search error: {str(e)}"],
            )
    
    def search_by_decisions(
        self,
        decisions: Dict[str, Any],
        k: int = 5,
        use_hybrid: bool = True,
    ) -> DashboardTemplateRetrievedContext:
        """
        Search templates using decision context with hybrid scoring.
        
        Args:
            decisions: Decision dict with keys like category, domain, has_chat, etc.
            k: Number of results to return
            use_hybrid: If True, combine vector search with rule-based scoring
        
        Returns:
            DashboardTemplateRetrievedContext with ranked templates
        """
        try:
            # Build query from decisions
            query_parts = []
            if decisions.get("category"):
                cats = decisions["category"]
                if isinstance(cats, list):
                    labels = [self._categories.get(c, {}).get("label", c) for c in cats]
                    query_parts.append(f"Dashboard for {', '.join(labels)}")
                else:
                    label = self._categories.get(cats, {}).get("label", cats)
                    query_parts.append(f"Dashboard for {label}")
            
            if decisions.get("domain"):
                query_parts.append(f"using {decisions['domain']} systems")
            
            if decisions.get("complexity"):
                query_parts.append(f"{decisions['complexity']} complexity")
            
            if decisions.get("has_chat") is True:
                query_parts.append("with AI chat advisor panel")
            elif decisions.get("has_chat") is False:
                query_parts.append("monitoring only, no chat")
            
            if decisions.get("theme"):
                query_parts.append(f"{decisions['theme']} theme")
            
            query = " ".join(query_parts) if query_parts else "general dashboard layout"
            
            # Get vector results if hybrid
            vector_results = None
            if use_hybrid:
                vector_ctx = self.search_templates(query, k=k * 2)  # Get more for scoring
                vector_results = [
                    {"template_id": t.template_id, "similarity_score": t.similarity_score or 0.0}
                    for t in vector_ctx.templates
                ]
            
            # Score all templates (uses hybrid scorer from vector_store)
            scored = score_templates_hybrid(decisions, vector_results=vector_results if use_hybrid else None)
            
            # Take top k
            top_k = scored[:k]
            
            # Build results
            template_results = []
            for tid, score, reasons in top_k:
                template = self._templates.get(tid)
                if not template:
                    continue
                
                result = self._template_to_result(template, similarity_score=score / 100.0)
                template_results.append(result)
            
            return DashboardTemplateRetrievedContext(
                query=query,
                templates=template_results,
                total_hits=len(template_results),
                decisions=decisions,
            )
        
        except Exception as e:
            logger.error(f"Error in decision-based search: {e}", exc_info=True)
            return DashboardTemplateRetrievedContext(
                query="",
                templates=[],
                total_hits=0,
                decisions=decisions,
                warnings=[f"Search error: {str(e)}"],
            )
    
    def get_template(self, template_id: str) -> Optional[DashboardTemplateResult]:
        """
        Direct lookup of a template by ID.
        
        Args:
            template_id: Template ID (e.g., "command-center")
        
        Returns:
            DashboardTemplateResult or None if not found
        """
        template = self._templates.get(template_id)
        if not template:
            logger.warning(f"Template {template_id} not found")
            return None
        
        return self._template_to_result(template)
    
    def get_templates_by_category(self, category: str) -> List[DashboardTemplateResult]:
        """Get all templates in a category."""
        results = []
        for tid, tpl in self._templates.items():
            if tpl.get("category") == category:
                results.append(self._template_to_result(tpl))
        return results
    
    def get_templates_by_domain(self, domain: str) -> List[DashboardTemplateResult]:
        """Get all templates that serve a domain."""
        results = []
        for tid, tpl in self._templates.items():
            if domain in tpl.get("domains", []):
                results.append(self._template_to_result(tpl))
        return results
    
    def list_all_templates(self) -> List[DashboardTemplateResult]:
        """List all available templates."""
        return [self._template_to_result(tpl) for tpl in self._templates.values()]
