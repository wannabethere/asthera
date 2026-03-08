"""
Dashboard Decision Tree Retrieval Service

Retrieval service for dashboard templates and metrics from the vector store.
Mirrors DecisionTreeRetrievalService exactly — same constructor pattern,
same _format_* pattern, same search_* / search_all / get_by_id pattern.

Three collections consumed:
  layout_templates       — EnrichedTemplate docs  (RETRIEVAL POINT 1)
  metric_catalog         — EnrichedMetric docs    (RETRIEVAL POINT 2)
  decision_tree_options  — DecisionOption docs    (prompt injection, optional)

Usage:
    service = DashboardDecisionTreeService()

    # Load templates for decision node
    ctx = service.search_templates("soc2 compliance training completion", limit=10)

    # Load per-metric config for spec generation
    ctx = service.search_metrics("training completion overdue assignments", limit=20)

    # Full combined retrieval (call once per pipeline run)
    ctx = service.search_all(
        query="compliance training dashboard",
        framework_filter="soc2",
        destination_filter="embedded",
    )
    state.update(ctx.to_state_payload())
"""
import json
import logging
from typing import Any, Dict, List, Optional

from dashboard_decision_tree_results import (
    DashboardTemplateResult,
    DashboardMetricResult,
    DashboardDecisionContext,
)

logger = logging.getLogger(__name__)


class DashboardDecisionTreeService:
    """
    Retrieval service for dashboard templates and metric catalog.

    Designed to be a drop-in companion to DecisionTreeRetrievalService.
    Reads from vector store collections written by VectorStoreWriter
    (ingest/vector_writer.py).
    """

    def __init__(
        self,
        doc_store_provider=None,
        embedder=None,
    ):
        try:
            from app.core.dependencies import get_doc_store_provider
            from app.ingestion.embedder import EmbeddingService
            from app.utils.cache import InMemoryCache
        except ImportError:
            # Allow standalone use without the app package
            get_doc_store_provider = lambda: None  # noqa: E731
            EmbeddingService = object  # noqa: N806

        self._embedder  = embedder or (
            EmbeddingService() if EmbeddingService is not object else None
        )
        self._doc_stores = doc_store_provider or (
            get_doc_store_provider() if callable(get_doc_store_provider) else None
        )

        try:
            from app.utils.cache import InMemoryCache
            self._cache = InMemoryCache()
        except ImportError:
            self._cache = {}

        stores = (
            self._doc_stores.stores
            if self._doc_stores and hasattr(self._doc_stores, "stores")
            else {}
        )

        self._templates_store = stores.get("layout_templates")
        self._metrics_store   = stores.get("metric_catalog")
        self._options_store   = stores.get("decision_tree_options")

        if not self._templates_store:
            logger.warning(
                "layout_templates store not available. "
                "Template retrieval will return empty results."
            )
        if not self._metrics_store:
            logger.warning(
                "metric_catalog store not available. "
                "Metric retrieval will return empty results."
            )

    # ── Formatters ────────────────────────────────────────────────────────

    def _format_template_result(self, result: Dict) -> Optional[DashboardTemplateResult]:
        """Format raw vector store result into DashboardTemplateResult."""
        try:
            content  = result.get("content",  {})
            metadata = result.get("metadata", {})
            score    = result.get("score",    0.0)
            doc_id   = result.get("id",       "")

            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    content = {}

            def _get(*keys):
                for k in keys:
                    v = content.get(k) or metadata.get(k)
                    if v is not None:
                        return v
                return None

            def _get_list(*keys):
                for k in keys:
                    v = content.get(k) or metadata.get(k)
                    if v:
                        if isinstance(v, str):
                            return [x.strip() for x in v.split("|") if x.strip()]
                        if isinstance(v, list):
                            return v
                return []

            template_id = _get("template_id", "id") or doc_id

            return DashboardTemplateResult(
                template_id=str(template_id),
                name=_get("name") or str(template_id),
                registry_source=_get("registry_source"),
                description=_get("description"),
                source_system=_get("source_system"),
                category=_get("category") or "",
                focus_areas=_get_list("focus_areas"),
                audience_levels=_get_list("audience_levels", "audience"),
                complexity=_get("complexity") or "medium",
                metric_profile_fit=_get_list("metric_profile_fit"),
                supported_destinations=_get_list("destinations", "supported_destinations"),
                interaction_modes=_get_list("interaction_modes"),
                primitives=_get_list("primitives"),
                panels=_get("panels") or {},
                layout_grid=_get("layout_grid") or {},
                strip_cells=int(_get("strip_cells") or 0),
                has_chat=str(_get("has_chat") or "false").lower() == "true",
                has_graph=str(_get("has_graph") or "false").lower() == "true",
                has_filters=str(_get("has_filters") or "false").lower() == "true",
                chart_types=_get_list("chart_types"),
                best_for=_get_list("best_for"),
                theme_hint=_get("theme_hint") or "light",
                domains=_get_list("domains"),
                powerbi_constraints=_get("powerbi_constraints") or {},
                simple_constraints=_get("simple_constraints") or {},
                content_hash=_get("content_hash") or "",
                score=float(score),
                id=doc_id,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(f"Error formatting template result: {exc}")
            return None

    def _format_metric_result(self, result: Dict) -> Optional[DashboardMetricResult]:
        """Format raw vector store result into DashboardMetricResult."""
        try:
            content  = result.get("content",  {})
            metadata = result.get("metadata", {})
            score    = result.get("score",    0.0)
            doc_id   = result.get("id",       "")

            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    content = {}

            def _get(*keys):
                for k in keys:
                    v = content.get(k) or metadata.get(k)
                    if v is not None:
                        return v
                return None

            def _get_list(*keys):
                for k in keys:
                    v = content.get(k) or metadata.get(k)
                    if v:
                        if isinstance(v, str):
                            return [x.strip() for x in v.split("|") if x.strip()]
                        if isinstance(v, list):
                            return v
                return []

            def _get_float(key):
                v = _get(key)
                try:
                    return float(v) if v not in (None, "", "None") else None
                except (TypeError, ValueError):
                    return None

            metric_id = _get("metric_id", "id") or doc_id

            return DashboardMetricResult(
                metric_id=str(metric_id),
                name=_get("name") or str(metric_id),
                dashboard_id=_get("dashboard_id"),
                dashboard_name=_get("dashboard_name"),
                dashboard_category=_get("dashboard_category"),
                metric_type=_get("metric_type"),
                unit=_get("unit"),
                chart_type=_get("chart_type"),
                section=_get("section"),
                metric_profile=_get("metric_profile"),
                category=_get("category"),
                focus_areas=_get_list("focus_areas"),
                source_capabilities=_get_list("source_capabilities"),
                source_schemas=_get_list("source_schemas"),
                kpis=_get_list("kpis"),
                threshold_warning=_get_float("threshold_warning"),
                threshold_critical=_get_float("threshold_critical"),
                good_direction=_get("good_direction") or "neutral",
                axis_label=_get("axis_label"),
                aggregation=_get("aggregation"),
                display_name=_get("display_name") or _get("name"),
                score=float(score),
                id=doc_id,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(f"Error formatting metric result: {exc}")
            return None

    # ── Search: templates ─────────────────────────────────────────────────

    def search_templates(
        self,
        query: str,
        limit: int = 10,
        category_filter: Optional[str] = None,
        destination_filter: Optional[str] = None,
        audience_filter: Optional[str] = None,
        complexity_filter: Optional[str] = None,
        registry_source_filter: Optional[str] = None,
    ) -> List[DashboardTemplateResult]:
        """
        Search layout_templates collection by semantic similarity.

        Args:
            query:                  Natural language query
            limit:                  Max results
            category_filter:        e.g. "security_operations"
            destination_filter:     e.g. "embedded" | "powerbi"
            audience_filter:        e.g. "compliance_team"
            complexity_filter:      e.g. "medium"
            registry_source_filter: e.g. "dashboard_registry" | "ld_templates_registry"

        Returns:
            List of DashboardTemplateResult ordered by similarity.
        """
        if not self._templates_store:
            logger.warning("layout_templates store not available")
            return []

        try:
            where: Dict[str, Any] = {}
            if category_filter:
                where["category"] = category_filter
            if destination_filter:
                where["destination_type"] = destination_filter
            if audience_filter:
                where["audience"] = audience_filter
            if complexity_filter:
                where["complexity"] = complexity_filter
            if registry_source_filter:
                where["registry_source"] = registry_source_filter

            if len(where) > 1:
                where = {"$and": [{"k": k, "v": v} for k, v in where.items()]}

            results = self._templates_store.semantic_search(
                query=query,
                k=limit,
                where=where if where else None,
            )

            out = []
            for r in results:
                fmt = self._format_template_result(r)
                if fmt:
                    out.append(fmt)
            return out

        except Exception as exc:
            logger.error(f"Error searching templates: {exc}", exc_info=True)
            return []

    # ── Search: metrics ───────────────────────────────────────────────────

    def search_metrics(
        self,
        query: str,
        limit: int = 20,
        category_filter: Optional[str] = None,
        focus_area_filter: Optional[List[str]] = None,
        source_capability_filter: Optional[str] = None,
        metric_profile_filter: Optional[str] = None,
    ) -> List[DashboardMetricResult]:
        """
        Search metric_catalog collection by semantic similarity.
        Used to hydrate per-metric config for spec_generation_node.

        Args:
            query:                    Natural language query
            limit:                    Max results
            category_filter:          e.g. "learning_development"
            focus_area_filter:        List of focus areas (OR match)
            source_capability_filter: e.g. "cornerstone.lms"
            metric_profile_filter:    e.g. "rate_percentage"

        Returns:
            List of DashboardMetricResult ordered by similarity.
        """
        if not self._metrics_store:
            logger.warning("metric_catalog store not available")
            return []

        try:
            where: Dict[str, Any] = {}
            if category_filter:
                where["category"] = category_filter
            if source_capability_filter:
                where["source_capabilities"] = source_capability_filter
            if metric_profile_filter:
                where["metric_profile"] = metric_profile_filter
            if focus_area_filter:
                where["focus_areas"] = (
                    {"$in": focus_area_filter}
                    if isinstance(focus_area_filter, list)
                    else focus_area_filter
                )

            if len(where) > 1:
                where = {"$and": [{"k": k, "v": v} for k, v in where.items()]}

            results = self._metrics_store.semantic_search(
                query=query,
                k=limit,
                where=where if where else None,
            )

            out = []
            for r in results:
                fmt = self._format_metric_result(r)
                if fmt:
                    out.append(fmt)
            return out

        except Exception as exc:
            logger.error(f"Error searching metrics: {exc}", exc_info=True)
            return []

    # ── Combined retrieval ────────────────────────────────────────────────

    def search_all(
        self,
        query: str,
        templates_limit: int = 10,
        metrics_limit:   int = 20,
        category_filter:     Optional[str] = None,
        destination_filter:  Optional[str] = None,
        focus_area_filter:   Optional[List[str]] = None,
        source_capability_filter: Optional[str] = None,
    ) -> DashboardDecisionContext:
        """
        Search both layout_templates and metric_catalog simultaneously.
        Returns a DashboardDecisionContext ready to be unpacked into state.

        Call once per pipeline run:

            ctx = service.search_all(
                query=state["user_query"],
                destination_filter=state.get("output_format", "embedded"),
                focus_area_filter=state.get("data_enrichment", {}).get("suggested_focus_areas"),
                source_capability_filter=state.get("selected_data_sources", [None])[0],
            )
            state.update(ctx.to_state_payload())
        """
        warnings = []

        # Templates
        try:
            templates = self.search_templates(
                query=query,
                limit=templates_limit,
                category_filter=category_filter,
                destination_filter=destination_filter,
            )
        except Exception as exc:
            logger.error(f"Error in template search: {exc}", exc_info=True)
            templates = []
            warnings.append(f"Template search failed: {exc}")

        # Template boosts: {template_id: normalised similarity score}
        template_boosts = {
            t.template_id: min(1.0, max(0.0, float(t.score)))
            for t in templates
        }

        # Metrics
        try:
            metrics = self.search_metrics(
                query=query,
                limit=metrics_limit,
                category_filter=category_filter,
                focus_area_filter=focus_area_filter,
                source_capability_filter=source_capability_filter,
            )
        except Exception as exc:
            logger.error(f"Error in metric search: {exc}", exc_info=True)
            metrics = []
            warnings.append(f"Metric search failed: {exc}")

        return DashboardDecisionContext(
            query=query,
            templates=templates,
            metrics=metrics,
            template_boosts=template_boosts,
            warnings=warnings or None,
        )

    # ── Direct lookups ────────────────────────────────────────────────────

    def get_template_by_id(self, template_id: str) -> Optional[DashboardTemplateResult]:
        """Direct lookup of a template by ID."""
        if not self._templates_store:
            return None
        try:
            results = self._templates_store.semantic_search(
                query=template_id,
                k=1,
                where={"template_id": template_id},
            )
            return self._format_template_result(results[0]) if results else None
        except Exception as exc:
            logger.error(f"Error getting template by ID: {exc}", exc_info=True)
            return None

    def get_metric_by_id(self, metric_id: str) -> Optional[DashboardMetricResult]:
        """Direct lookup of a metric by ID."""
        if not self._metrics_store:
            return None
        try:
            results = self._metrics_store.semantic_search(
                query=metric_id,
                k=1,
                where={"metric_id": metric_id},
            )
            return self._format_metric_result(results[0]) if results else None
        except Exception as exc:
            logger.error(f"Error getting metric by ID: {exc}", exc_info=True)
            return None
