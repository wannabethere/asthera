"""
Dashboard Template Retrieval Service

Retrieval service for dashboard templates using the unified registry.
Supports both semantic search (vector store) and rule-based scoring.

Follows the pattern from retrieval/service.py and retrieval/mdl_service.py.
"""
import logging
import json
from typing import Dict, List, Optional, Any

from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

from app.ingestion.embedder import EmbeddingService
from app.dashboard_agent.dashboard_template_results import (
    DashboardTemplateResult,
    DashboardTemplateRetrievedContext,
)

# Import unified registry
try:
    from app.dashboard_agent.registry_config.registry_unified import (
        ALL_TEMPLATES,
        ALL_CATEGORIES,
        get_unified_embedding_text,
        score_all_templates,
    )
except ImportError:
    # Fallback to templates.py if registry_unified not available
    from app.dashboard_agent.templates import (
        TEMPLATES as ALL_TEMPLATES,
        CATEGORIES as ALL_CATEGORIES,
        get_template_embedding_text as get_unified_embedding_text,
    )
    # Simple scoring fallback
    def score_all_templates(decisions: dict) -> list[tuple[str, int, list[str]]]:
        """Fallback scoring function."""
        scores = []
        for tid, tpl in ALL_TEMPLATES.items():
            score = 0
            reasons = []
            if decisions.get("category") and tpl.get("category") in decisions["category"]:
                score += 30
                reasons.append(f"category: {tpl['category']}")
            scores.append((tid, score, reasons))
        return sorted(scores, key=lambda x: x[1], reverse=True)

logger = logging.getLogger(__name__)


class DashboardTemplateRetrievalService:
    """
    Retrieval service for dashboard templates.
    
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
    
    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        vector_store_backend: str = "faiss",
        vector_store_persist_dir: Optional[str] = None,
    ):
        """
        Initialize dashboard template retrieval service.
        
        Args:
            embedder: Optional EmbeddingService instance
            vector_store_backend: "faiss" or "chroma"
            vector_store_persist_dir: Directory to persist vector store (for chroma)
        """
        self._embedder = embedder or EmbeddingService()
        self._backend = vector_store_backend
        self._persist_dir = vector_store_persist_dir
        self._vector_store = None
        self._templates = ALL_TEMPLATES
        self._categories = ALL_CATEGORIES
        
        logger.info(f"Initialized DashboardTemplateRetrievalService with {len(self._templates)} templates")
    
    def _get_vector_store(self):
        """Lazy-load vector store on first use."""
        if self._vector_store is None:
            self._vector_store = self._build_vector_store()
        return self._vector_store
    
    def _build_vector_store(self):
        """Build vector store from all templates."""
        from langchain_core.embeddings import Embeddings
        
        # Create embeddings adapter
        class EmbeddingAdapter(Embeddings):
            def __init__(self, embedder):
                self._embedder = embedder
            
            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return [self._embedder.embed_one(text) for text in texts]
            
            def embed_query(self, text: str) -> List[float]:
                return self._embedder.embed_one(text)
        
        embeddings = EmbeddingAdapter(self._embedder)
        docs = self._build_template_documents()
        
        if self._backend == "chroma":
            from langchain_chroma import Chroma
            store = Chroma.from_documents(
                docs,
                embeddings,
                collection_name="dashboard_templates",
                persist_directory=self._persist_dir or "./chroma_dashboard_templates",
            )
            logger.info(f"Built Chroma store with {len(docs)} template documents")
        else:
            from langchain_community.vectorstores import FAISS
            store = FAISS.from_documents(docs, embeddings)
            logger.info(f"Built FAISS store with {len(docs)} template documents")
        
        return store
    
    def _build_template_documents(self) -> List[Document]:
        """Convert all templates into Documents for vector store ingestion."""
        docs = []
        for tid, tpl in self._templates.items():
            text = get_unified_embedding_text(tpl)
            metadata = {
                "template_id": tid,
                "name": tpl["name"],
                "category": tpl["category"],
                "category_label": self._categories.get(tpl["category"], {}).get("label", ""),
                "domains": json.dumps(tpl.get("domains", [])),
                "complexity": tpl.get("complexity", "medium"),
                "has_chat": tpl.get("has_chat", False),
                "has_graph": tpl.get("has_graph", False),
                "strip_cells": tpl.get("strip_cells", 0),
                "best_for": json.dumps(tpl.get("best_for", [])),
                "primitives": json.dumps(tpl.get("primitives", [])),
                "theme": tpl.get("theme_hint", "light"),
            }
            
            # L&D specific metadata
            if tpl.get("chart_types"):
                metadata["chart_types"] = json.dumps(tpl["chart_types"])
            if tpl.get("activity_types"):
                metadata["activity_types"] = json.dumps(tpl["activity_types"])
            if tpl.get("table_columns"):
                if isinstance(tpl["table_columns"], list):
                    metadata["table_columns"] = json.dumps(tpl["table_columns"])
                elif isinstance(tpl["table_columns"], dict):
                    metadata["table_columns"] = json.dumps(tpl["table_columns"])
            
            docs.append(Document(page_content=text, metadata=metadata))
        
        return docs
    
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
        Semantic search across templates.
        
        Args:
            query: Natural language query
            k: Number of results to return
            filter_dict: Optional metadata filters (e.g., {"category": "compliance"})
        
        Returns:
            DashboardTemplateRetrievedContext with matching templates
        """
        try:
            store = self._get_vector_store()
            
            if filter_dict:
                results = store.similarity_search_with_score(
                    query, k=k, filter=filter_dict
                )
            else:
                results = store.similarity_search_with_score(query, k=k)
            
            template_results = []
            for doc, score in results:
                tid = doc.metadata["template_id"]
                template = self._templates.get(tid)
                if not template:
                    logger.warning(f"Template {tid} not found in registry")
                    continue
                
                # Normalize score (FAISS uses distance, Chroma uses similarity)
                similarity = round(1 - score, 4) if score <= 1 else round(score, 4)
                result = self._template_to_result(template, similarity_score=similarity)
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
            
            # Score all templates
            scored = score_all_templates(decisions)
            
            # Merge with vector scores if hybrid
            if use_hybrid and vector_results:
                vector_map = {vr["template_id"]: vr["similarity_score"] for vr in vector_results}
                # Boost scores for templates that appeared in vector search
                scored = [
                    (tid, score + (vector_map.get(tid, 0) * 15), reasons)
                    for tid, score, reasons in scored
                ]
                scored.sort(key=lambda x: x[1], reverse=True)
            
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
