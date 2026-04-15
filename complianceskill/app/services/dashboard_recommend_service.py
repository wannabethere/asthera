"""
Dashboard Recommendation Service

Thin wrapper around DashboardDecisionTreeService that maps user intent
(goals, tone, purpose) to decision tree filters and returns top-K templates.
Called from AstheraBackend via POST /workflow/dashboard/recommend.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tone → audience_level mapping (for future filter support)
TONE_AUDIENCE_MAP: Dict[str, str] = {
    "executive": "executive",
    "operational": "operational",
    "technical": "technical",
}

# Purpose → category mapping passed to search_all category_filter
PURPOSE_CATEGORY_MAP: Dict[str, str] = {
    "monitoring": "monitoring",
    "compliance": "compliance",
    "analysis": "analysis",
    "reporting": "reporting",
}


class DashboardRecommendService:
    """
    Wraps DashboardDecisionTreeService to recommend dashboard templates
    based on user goals, tone, and purpose.
    """

    def recommend(
        self,
        goals: str,
        tone: str,
        purpose: str,
        selected_metrics: Optional[List[str]] = None,
        top_k: int = 3,
        # Pipeline context — passed from the live pipeline state
        primary_area: Optional[str] = None,
        area_concepts: Optional[List[str]] = None,
        intent: Optional[str] = None,
        persona: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recommend dashboard templates for user goals/tone/purpose.

        Uses pipeline context (primary_area, area_concepts, intent, persona) to
        build a richer semantic query and derive category/destination filters so
        the decision tree returns the most relevant templates.

        Args:
            goals: Free-text description of what the dashboard should achieve.
            tone: Audience tone — "executive" | "operational" | "technical".
            purpose: Dashboard purpose — "monitoring" | "compliance" | "analysis" | "reporting".
            selected_metrics: Optional list of metric/KPI names from the pipeline run.
            top_k: Maximum number of template results to return.
            primary_area: Primary recommendation area from the pipeline.
            area_concepts: Area/concept labels confirmed during the pipeline run.
            intent: Classified intent from the pipeline.
            persona: User persona from the pipeline.
            output_format: Target renderer ("echarts" | "powerbi" | "simple").

        Returns:
            Dict with:
              - templates: List[dict] — top-k matched templates
              - metrics: List[dict] — related metric catalog entries
              - warnings: List[str] — any retrieval warnings
        """
        try:
            from app.agents.decision_trees.dashboard.dashboard_decision_tree_service import (  # noqa: PLC0415
                DashboardDecisionTreeService,
            )
        except ImportError as e:
            logger.error("Could not import DashboardDecisionTreeService: %s", e)
            return {"templates": [], "metrics": [], "warnings": [str(e)]}

        try:
            svc = DashboardDecisionTreeService()
        except Exception as e:
            logger.error("Failed to init DashboardDecisionTreeService: %s", e)
            return {"templates": [], "metrics": [], "warnings": [str(e)]}

        # ── Build semantic query ─────────────────────────────────────────────
        # Combine: user goals + primary area + area concepts + intent + metric names
        area_clause = " ".join(filter(None, [
            primary_area or "",
            " ".join(area_concepts or []),
            intent or "",
        ])).strip()
        metric_clause = " ".join((selected_metrics or [])[:10])
        query = " ".join(filter(None, [goals, area_clause, metric_clause])).strip() \
                or "compliance dashboard"

        # ── Derive category filter ────────────────────────────────────────────
        # Purpose is the first signal; fall back to area/concept keywords
        category = PURPOSE_CATEGORY_MAP.get(purpose.lower() if purpose else "", None)
        if not category:
            concept_text = (area_clause + " " + (goals or "")).lower()
            if any(x in concept_text for x in ("training", "learning", "lms", "completion", "cornerstone")):
                category = "learning_development"
            elif any(x in concept_text for x in ("vuln", "security", "siem", "incident", "threat")):
                category = "security_operations"
            elif any(x in concept_text for x in ("compliance", "audit", "soc2", "hipaa", "nist", "risk")):
                category = "compliance_audit"
            elif any(x in concept_text for x in ("hr", "workforce", "headcount", "workday")):
                category = "hr_workforce"

        # ── Derive destination filter from output_format ─────────────────────
        dest_map = {"echarts": "embedded", "powerbi": "powerbi",
                    "html": "simple", "simple": "simple"}
        destination = dest_map.get((output_format or "").lower(), None)

        logger.info(
            "Dashboard recommend: query=%r category=%r destination=%r top_k=%d",
            query, category, destination, top_k,
        )

        try:
            ctx = svc.search_all(
                query=query,
                templates_limit=top_k,
                metrics_limit=20,
                category_filter=category,
                destination_filter=destination,
            )
        except Exception as e:
            logger.error("Decision tree search failed: %s", e, exc_info=True)
            return {"templates": [], "metrics": [], "warnings": [str(e)]}

        def _to_dict(obj: Any) -> Dict[str, Any]:
            """Safely convert a dataclass/NamedTuple/dict to plain dict."""
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, "__dict__"):
                return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
            if hasattr(obj, "_asdict"):
                return obj._asdict()
            return {"value": str(obj)}

        templates = [_to_dict(t) for t in ctx.templates][:top_k]
        metrics = [_to_dict(m) for m in ctx.metrics]

        return {
            "templates": templates,
            "metrics": metrics,
            "warnings": list(ctx.warnings or []),
        }


# ── Singleton ──────────────────────────────────────────────────────────────────

_service: Optional[DashboardRecommendService] = None


def get_dashboard_recommend_service() -> DashboardRecommendService:
    """Return or create the singleton DashboardRecommendService."""
    global _service
    if _service is None:
        _service = DashboardRecommendService()
    return _service
