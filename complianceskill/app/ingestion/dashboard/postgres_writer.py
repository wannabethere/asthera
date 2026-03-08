"""
CCE Dashboard Enricher — Postgres Writer
=========================================
Creates tables and upserts all enriched entities.

Tables:
  dashboard_templates        — one row per EnrichedTemplate
  dashboard_metrics          — one row per EnrichedMetric
  decision_tree_config       — one row per DecisionTree version (JSONB)
  template_focus_areas       — junction table (normalised)
  template_destinations      — junction table (normalised)
  metric_focus_areas         — junction table (normalised)

Connection:
  Set DATABASE_URL env var, or pass dsn= to PostgresWriter().
  Default: postgresql://localhost:5432/cce_dashboard

All writes are upsert-on-content-hash — safe to re-run.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from models import EnrichedTemplate, EnrichedMetric, DecisionTree

logger = logging.getLogger(__name__)

DDL = """
-- ── Core tables ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dashboard_templates (
    template_id          VARCHAR(120)  PRIMARY KEY,
    registry_source      VARCHAR(60)   NOT NULL,
    name                 TEXT          NOT NULL,
    description          TEXT,
    source_system        VARCHAR(120),
    content_hash         VARCHAR(32)   NOT NULL,

    -- Decision tree dimensions
    category             VARCHAR(60)   NOT NULL,
    complexity           VARCHAR(20)   NOT NULL,
    metric_profile_fit   TEXT[]        DEFAULT '{}',
    supported_destinations TEXT[]      DEFAULT '{}',
    interaction_modes    TEXT[]        DEFAULT '{}',
    audience_levels      TEXT[]        DEFAULT '{}',
    focus_areas          TEXT[]        DEFAULT '{}',

    -- Layout
    primitives           TEXT[]        DEFAULT '{}',
    panels               JSONB         DEFAULT '{}',
    layout_grid          JSONB         DEFAULT '{}',
    strip_cells          SMALLINT      DEFAULT 0,
    has_chat             BOOLEAN       DEFAULT FALSE,
    has_graph            BOOLEAN       DEFAULT FALSE,
    has_filters          BOOLEAN       DEFAULT FALSE,
    chart_types          TEXT[]        DEFAULT '{}',
    components           JSONB         DEFAULT '[]',
    best_for             TEXT[]        DEFAULT '{}',
    theme_hint           VARCHAR(20)   DEFAULT 'light',
    domains              TEXT[]        DEFAULT '{}',

    -- Destination constraints
    powerbi_constraints  JSONB         DEFAULT '{}',
    simple_constraints   JSONB         DEFAULT '{}',

    -- Embedding text (for re-indexing without recomputing)
    embedding_text       TEXT,

    -- Audit
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dashboard_metrics (
    metric_id            VARCHAR(200)  PRIMARY KEY,
    dashboard_id         VARCHAR(120)  NOT NULL,
    dashboard_name       TEXT          NOT NULL,
    dashboard_category   VARCHAR(80)   NOT NULL,

    name                 TEXT          NOT NULL,
    metric_type          VARCHAR(60)   NOT NULL,
    unit                 VARCHAR(60),
    chart_type           VARCHAR(60),
    section              VARCHAR(120),
    content_hash         VARCHAR(32)   NOT NULL,

    -- Enriched decision dimensions
    metric_profile       VARCHAR(40)   NOT NULL,
    category             VARCHAR(60)   NOT NULL,
    focus_areas          TEXT[]        DEFAULT '{}',
    source_capabilities  TEXT[]        DEFAULT '{}',
    source_schemas       TEXT[]        DEFAULT '{}',
    kpis                 TEXT[]        DEFAULT '{}',

    -- Threshold & display
    threshold_warning    NUMERIC,
    threshold_critical   NUMERIC,
    good_direction       VARCHAR(10)   DEFAULT 'neutral',
    axis_label           VARCHAR(120),
    aggregation          VARCHAR(30),
    display_name         TEXT,

    embedding_text       TEXT,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_tree_config (
    version              VARCHAR(20)   PRIMARY KEY,
    tree_json            JSONB         NOT NULL,
    built_at             TIMESTAMPTZ   NOT NULL,
    is_active            BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ── Normalised junction tables ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS template_focus_areas (
    template_id          VARCHAR(120)  NOT NULL REFERENCES dashboard_templates(template_id) ON DELETE CASCADE,
    focus_area           VARCHAR(80)   NOT NULL,
    PRIMARY KEY (template_id, focus_area)
);

CREATE TABLE IF NOT EXISTS template_destinations (
    template_id          VARCHAR(120)  NOT NULL REFERENCES dashboard_templates(template_id) ON DELETE CASCADE,
    destination_type     VARCHAR(40)   NOT NULL,
    PRIMARY KEY (template_id, destination_type)
);

CREATE TABLE IF NOT EXISTS metric_focus_areas (
    metric_id            VARCHAR(200)  NOT NULL REFERENCES dashboard_metrics(metric_id) ON DELETE CASCADE,
    focus_area           VARCHAR(80)   NOT NULL,
    PRIMARY KEY (metric_id, focus_area)
);

-- ── Indexes ────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_tmpl_category          ON dashboard_templates(category);
CREATE INDEX IF NOT EXISTS idx_tmpl_complexity        ON dashboard_templates(complexity);
CREATE INDEX IF NOT EXISTS idx_tmpl_destinations      ON dashboard_templates USING GIN(supported_destinations);
CREATE INDEX IF NOT EXISTS idx_tmpl_focus_areas       ON dashboard_templates USING GIN(focus_areas);
CREATE INDEX IF NOT EXISTS idx_tmpl_registry          ON dashboard_templates(registry_source);
CREATE INDEX IF NOT EXISTS idx_metric_category        ON dashboard_metrics(category);
CREATE INDEX IF NOT EXISTS idx_metric_dashboard       ON dashboard_metrics(dashboard_id);
CREATE INDEX IF NOT EXISTS idx_metric_profile         ON dashboard_metrics(metric_profile);
CREATE INDEX IF NOT EXISTS idx_metric_source_caps     ON dashboard_metrics USING GIN(source_capabilities);
CREATE INDEX IF NOT EXISTS idx_metric_focus_areas     ON dashboard_metrics USING GIN(focus_areas);
"""


class PostgresWriter:
    """
    Writes enriched entities to Postgres. Safe to re-run — all writes are
    upsert-on-content-hash (skips unchanged rows).
    """

    def __init__(self, dsn: Optional[str] = None):
        if not HAS_PSYCOPG2:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
        self.dsn = dsn or os.environ.get("DATABASE_URL", "postgresql://localhost:5432/cce_dashboard")

    def _connect(self):
        return psycopg2.connect(self.dsn)

    def create_schema(self):
        """Create all tables if they don't exist."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(DDL)
            conn.commit()
        logger.info("Postgres schema ready")

    # ── Templates ─────────────────────────────────────────────────────

    def upsert_templates(self, templates: list[EnrichedTemplate]) -> tuple[int, int]:
        """Upsert templates. Returns (inserted, skipped) counts."""
        inserted = skipped = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for t in templates:
                    # Check existing hash
                    cur.execute(
                        "SELECT content_hash FROM dashboard_templates WHERE template_id = %s",
                        (t.template_id,)
                    )
                    row = cur.fetchone()
                    if row and row[0] == t.content_hash:
                        skipped += 1
                        continue

                    cur.execute("""
                        INSERT INTO dashboard_templates (
                            template_id, registry_source, name, description,
                            source_system, content_hash, category, complexity,
                            metric_profile_fit, supported_destinations, interaction_modes,
                            audience_levels, focus_areas, primitives, panels, layout_grid,
                            strip_cells, has_chat, has_graph, has_filters, chart_types,
                            components, best_for, theme_hint, domains,
                            powerbi_constraints, simple_constraints, embedding_text,
                            updated_at
                        ) VALUES (
                            %(template_id)s, %(registry_source)s, %(name)s, %(description)s,
                            %(source_system)s, %(content_hash)s, %(category)s, %(complexity)s,
                            %(metric_profile_fit)s, %(supported_destinations)s, %(interaction_modes)s,
                            %(audience_levels)s, %(focus_areas)s, %(primitives)s, %(panels)s, %(layout_grid)s,
                            %(strip_cells)s, %(has_chat)s, %(has_graph)s, %(has_filters)s, %(chart_types)s,
                            %(components)s, %(best_for)s, %(theme_hint)s, %(domains)s,
                            %(powerbi_constraints)s, %(simple_constraints)s, %(embedding_text)s,
                            NOW()
                        )
                        ON CONFLICT (template_id) DO UPDATE SET
                            name                  = EXCLUDED.name,
                            description           = EXCLUDED.description,
                            content_hash          = EXCLUDED.content_hash,
                            category              = EXCLUDED.category,
                            complexity            = EXCLUDED.complexity,
                            metric_profile_fit    = EXCLUDED.metric_profile_fit,
                            supported_destinations= EXCLUDED.supported_destinations,
                            interaction_modes     = EXCLUDED.interaction_modes,
                            audience_levels       = EXCLUDED.audience_levels,
                            focus_areas           = EXCLUDED.focus_areas,
                            primitives            = EXCLUDED.primitives,
                            panels                = EXCLUDED.panels,
                            layout_grid           = EXCLUDED.layout_grid,
                            strip_cells           = EXCLUDED.strip_cells,
                            has_chat              = EXCLUDED.has_chat,
                            has_graph             = EXCLUDED.has_graph,
                            has_filters           = EXCLUDED.has_filters,
                            chart_types           = EXCLUDED.chart_types,
                            components            = EXCLUDED.components,
                            best_for              = EXCLUDED.best_for,
                            theme_hint            = EXCLUDED.theme_hint,
                            domains               = EXCLUDED.domains,
                            powerbi_constraints   = EXCLUDED.powerbi_constraints,
                            simple_constraints    = EXCLUDED.simple_constraints,
                            embedding_text        = EXCLUDED.embedding_text,
                            updated_at            = NOW()
                    """, {
                        "template_id":          t.template_id,
                        "registry_source":      t.registry_source,
                        "name":                 t.name,
                        "description":          t.description,
                        "source_system":        t.source_system,
                        "content_hash":         t.content_hash,
                        "category":             t.category.value,
                        "complexity":           t.complexity.value,
                        "metric_profile_fit":   [p.value for p in t.metric_profile_fit],
                        "supported_destinations":[d.value for d in t.supported_destinations],
                        "interaction_modes":    [m.value for m in t.interaction_modes],
                        "audience_levels":      [a.value for a in t.audience_levels],
                        "focus_areas":          t.focus_areas,
                        "primitives":           t.primitives,
                        "panels":               json.dumps(t.panels),
                        "layout_grid":          json.dumps(t.layout_grid),
                        "strip_cells":          t.strip_cells,
                        "has_chat":             t.has_chat,
                        "has_graph":            t.has_graph,
                        "has_filters":          t.has_filters,
                        "chart_types":          t.chart_types,
                        "components":           json.dumps(t.components),
                        "best_for":             t.best_for,
                        "theme_hint":           t.theme_hint,
                        "domains":              t.domains,
                        "powerbi_constraints":  json.dumps(t.powerbi_constraints.dict()),
                        "simple_constraints":   json.dumps(t.simple_constraints.dict()),
                        "embedding_text":       t.embedding_text,
                    })

                    # Upsert junction tables
                    cur.execute("DELETE FROM template_focus_areas  WHERE template_id = %s", (t.template_id,))
                    cur.execute("DELETE FROM template_destinations  WHERE template_id = %s", (t.template_id,))
                    psycopg2.extras.execute_values(cur,
                        "INSERT INTO template_focus_areas (template_id, focus_area) VALUES %s ON CONFLICT DO NOTHING",
                        [(t.template_id, fa) for fa in t.focus_areas],
                    )
                    psycopg2.extras.execute_values(cur,
                        "INSERT INTO template_destinations (template_id, destination_type) VALUES %s ON CONFLICT DO NOTHING",
                        [(t.template_id, d.value) for d in t.supported_destinations],
                    )
                    inserted += 1

            conn.commit()

        logger.info(f"Templates: {inserted} upserted, {skipped} unchanged")
        return inserted, skipped

    # ── Metrics ───────────────────────────────────────────────────────

    def upsert_metrics(self, metrics: list[EnrichedMetric]) -> tuple[int, int]:
        """Upsert metrics. Returns (inserted, skipped) counts."""
        inserted = skipped = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for m in metrics:
                    cur.execute(
                        "SELECT content_hash FROM dashboard_metrics WHERE metric_id = %s",
                        (m.metric_id,)
                    )
                    row = cur.fetchone()
                    if row and row[0] == m.content_hash:
                        skipped += 1
                        continue

                    cur.execute("""
                        INSERT INTO dashboard_metrics (
                            metric_id, dashboard_id, dashboard_name, dashboard_category,
                            name, metric_type, unit, chart_type, section, content_hash,
                            metric_profile, category, focus_areas, source_capabilities,
                            source_schemas, kpis, threshold_warning, threshold_critical,
                            good_direction, axis_label, aggregation, display_name,
                            embedding_text, updated_at
                        ) VALUES (
                            %(metric_id)s, %(dashboard_id)s, %(dashboard_name)s, %(dashboard_category)s,
                            %(name)s, %(metric_type)s, %(unit)s, %(chart_type)s, %(section)s, %(content_hash)s,
                            %(metric_profile)s, %(category)s, %(focus_areas)s, %(source_capabilities)s,
                            %(source_schemas)s, %(kpis)s, %(threshold_warning)s, %(threshold_critical)s,
                            %(good_direction)s, %(axis_label)s, %(aggregation)s, %(display_name)s,
                            %(embedding_text)s, NOW()
                        )
                        ON CONFLICT (metric_id) DO UPDATE SET
                            name                = EXCLUDED.name,
                            metric_type         = EXCLUDED.metric_type,
                            content_hash        = EXCLUDED.content_hash,
                            metric_profile      = EXCLUDED.metric_profile,
                            focus_areas         = EXCLUDED.focus_areas,
                            source_capabilities = EXCLUDED.source_capabilities,
                            good_direction      = EXCLUDED.good_direction,
                            embedding_text      = EXCLUDED.embedding_text,
                            updated_at          = NOW()
                    """, {
                        "metric_id":           m.metric_id,
                        "dashboard_id":        m.dashboard_id,
                        "dashboard_name":      m.dashboard_name,
                        "dashboard_category":  m.dashboard_category,
                        "name":                m.name,
                        "metric_type":         m.metric_type,
                        "unit":                m.unit,
                        "chart_type":          m.chart_type,
                        "section":             m.section,
                        "content_hash":        m.content_hash,
                        "metric_profile":      m.metric_profile.value,
                        "category":            m.category.value,
                        "focus_areas":         m.focus_areas,
                        "source_capabilities": m.source_capabilities,
                        "source_schemas":      m.source_schemas,
                        "kpis":                m.kpis,
                        "threshold_warning":   m.threshold_warning,
                        "threshold_critical":  m.threshold_critical,
                        "good_direction":      m.good_direction,
                        "axis_label":          m.axis_label,
                        "aggregation":         m.aggregation,
                        "display_name":        m.display_name,
                        "embedding_text":      m.embedding_text,
                    })

                    cur.execute("DELETE FROM metric_focus_areas WHERE metric_id = %s", (m.metric_id,))
                    psycopg2.extras.execute_values(cur,
                        "INSERT INTO metric_focus_areas (metric_id, focus_area) VALUES %s ON CONFLICT DO NOTHING",
                        [(m.metric_id, fa) for fa in m.focus_areas],
                    )
                    inserted += 1

            conn.commit()

        logger.info(f"Metrics: {inserted} upserted, {skipped} unchanged")
        return inserted, skipped

    # ── Decision Tree ─────────────────────────────────────────────────

    def upsert_decision_tree(self, tree: DecisionTree):
        """Upsert decision tree config. Marks previous versions as inactive."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE decision_tree_config SET is_active = FALSE WHERE version != %s",
                    (tree.version,)
                )
                cur.execute("""
                    INSERT INTO decision_tree_config (version, tree_json, built_at, is_active)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (version) DO UPDATE SET
                        tree_json  = EXCLUDED.tree_json,
                        built_at   = EXCLUDED.built_at,
                        is_active  = TRUE
                """, (
                    tree.version,
                    json.dumps(tree.dict()),
                    tree.built_at,
                ))
            conn.commit()
        logger.info(f"Decision tree v{tree.version} upserted")
