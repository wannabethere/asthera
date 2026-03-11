-- ============================================================================
-- CCE (Causal Context Engine) Postgres Schema
-- ============================================================================
-- Creates all tables required for causal graph storage and retrieval
-- Run this script once before first ingestion
--
-- Tables:
--   - cce.causal_corpus          : Seed + live causal relationship corpus
--   - cce.causal_adjacency        : Structural edge lookups (fast Postgres queries)
--   - cce.metric_registry        : Metric definitions (optional, if not using ChromaDB)
--   - cce.intervention_log       : Dashboard action → causal feedback
--   - cce.graph_snapshots        : Point-in-time graph state for audit
-- ============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS cce;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pg_trgm extension (optional - for fuzzy text search, comment out if not supported)
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- Table 1: cce.causal_corpus
-- ============================================================================
-- Primary corpus table for causal edge definitions
-- Used by N5 CausalValidationLayer for edge confidence grounding

CREATE TABLE IF NOT EXISTS cce.causal_corpus (
    entry_id                VARCHAR(100) PRIMARY KEY,
    source_node_category    VARCHAR(100) NOT NULL,     -- 'lms.engagement'
    target_node_category    VARCHAR(100) NOT NULL,     -- 'lms.compliance'
    direction               VARCHAR(20) NOT NULL,       -- positive|negative|nonlinear|unknown
    mechanism               TEXT NOT NULL,
    lag_window_days         INTEGER NOT NULL,
    confidence              NUMERIC(4,3) NOT NULL,      -- 0.000 – 1.000
    evidence_type           VARCHAR(50) NOT NULL,     -- peer_reviewed|operational_study|analogous|live_intervention
    vertical                VARCHAR(50) DEFAULT 'lms',
    domain                  VARCHAR(100),
    contradictions          TEXT,
    provenance              TEXT,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW(),
    source                  VARCHAR(50) DEFAULT 'seed'  -- seed|live_intervention|curated
);

CREATE INDEX IF NOT EXISTS idx_corpus_categories 
    ON cce.causal_corpus(source_node_category, target_node_category);
CREATE INDEX IF NOT EXISTS idx_corpus_vertical 
    ON cce.causal_corpus(vertical, is_active);
CREATE INDEX IF NOT EXISTS idx_corpus_domain 
    ON cce.causal_corpus(domain) WHERE domain IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_corpus_confidence 
    ON cce.causal_corpus(confidence DESC) WHERE is_active = TRUE;

-- ============================================================================
-- Table 2: cce.causal_adjacency
-- ============================================================================
-- Structural edge lookups for fast node_id-based queries
-- Populated from causal_corpus + node_id mappings
-- Used by hybrid_retrieve() for Postgres structural lookups

CREATE TABLE IF NOT EXISTS cce.causal_adjacency (
    edge_id             VARCHAR(100) PRIMARY KEY,
    source_node_id      VARCHAR(200) NOT NULL,
    target_node_id      VARCHAR(200) NOT NULL,
    direction           VARCHAR(20)  NOT NULL DEFAULT 'positive',
    lag_window_days     INTEGER      NOT NULL DEFAULT 14,
    confidence          NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    corpus_match_type   VARCHAR(30)  NOT NULL DEFAULT 'confirmed',
    evidence_type       VARCHAR(50)  NOT NULL DEFAULT 'operational_study',
    mechanism           TEXT,
    vertical            VARCHAR(50)  NOT NULL DEFAULT 'lms',
    domain              VARCHAR(100),
    provenance          TEXT,
    source              VARCHAR(30)  NOT NULL DEFAULT 'seed',
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_causal_adj_source
    ON cce.causal_adjacency (source_node_id, vertical);
CREATE INDEX IF NOT EXISTS idx_causal_adj_target
    ON cce.causal_adjacency (target_node_id, vertical);
CREATE INDEX IF NOT EXISTS idx_causal_adj_src_tgt_vertical
    ON cce.causal_adjacency (vertical, source_node_id, target_node_id);
CREATE INDEX IF NOT EXISTS idx_causal_adj_confidence
    ON cce.causal_adjacency (confidence DESC) WHERE confidence >= 0.45;

-- ============================================================================
-- Table 3: cce.metric_registry
-- ============================================================================
-- Optional: Metric definitions (if not using ChromaDB for metric registry)
-- The causal engine's N1-N2 nodes reason over this table

CREATE TABLE IF NOT EXISTS cce.metric_registry (
    metric_id               VARCHAR(200) PRIMARY KEY,
    name                    VARCHAR(300) NOT NULL,
    category                VARCHAR(100) NOT NULL,     -- dot-notation: 'lms.compliance'
    description             TEXT,
    temporal_grain          VARCHAR(20) NOT NULL,       -- daily|weekly|monthly|quarterly
    is_leading_indicator    BOOLEAN DEFAULT FALSE,
    is_lagging_indicator    BOOLEAN DEFAULT FALSE,
    good_direction          VARCHAR(10),               -- up|down|neutral
    unit                    VARCHAR(50),               -- percentage|count|ratio|currency
    source_system           VARCHAR(50),               -- cornerstone|workday|hris|survey
    silver_table            VARCHAR(200),              -- e.g. 'lms_silver.compliance_status'
    gold_table              VARCHAR(200),              -- e.g. 'lms_gold.compliance_metrics'
    gold_column             VARCHAR(200),              -- column name in gold table
    aggregation             VARCHAR(50),               -- sum|avg|rate|rolling_12m
    known_correlates        TEXT[],                    -- other metric_ids
    threshold_warning       NUMERIC,
    threshold_critical      NUMERIC,
    is_active               BOOLEAN DEFAULT TRUE,
    vertical                VARCHAR(50) DEFAULT 'lms',
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metric_registry_category 
    ON cce.metric_registry(category);
CREATE INDEX IF NOT EXISTS idx_metric_registry_vertical 
    ON cce.metric_registry(vertical, is_active);
-- Fuzzy search index (requires pg_trgm extension - comment out if extension not available)
-- CREATE INDEX IF NOT EXISTS idx_metric_registry_name_trgm 
--     ON cce.metric_registry USING gin(name gin_trgm_ops);

-- ============================================================================
-- Table 4: cce.intervention_log
-- ============================================================================
-- Dashboard user action → causal feedback record
-- Required infrastructure for intervention feedback loop (design doc P5)

CREATE TABLE IF NOT EXISTS cce.intervention_log (
    intervention_id         VARCHAR(100) PRIMARY KEY,
    session_id              VARCHAR(100),
    timestamp               TIMESTAMP NOT NULL,
    template_id             VARCHAR(100),
    focus_area              VARCHAR(100),
    user_action             TEXT NOT NULL,
    targeted_causal_path    TEXT[],                    -- node_ids in order
    graph_confidence_at_time NUMERIC(4,3),
    observation_window_days INTEGER DEFAULT 90,
    
    -- Observed outcome
    observed_outcome_delta  JSONB,                     -- {metric_id: delta_value}
    expected_outcome_delta  JSONB,                     -- {metric_id: expected_change}
    edge_patches            JSONB,                     -- [{edge, old_conf, new_conf, delta}]
    
    -- Corpus linkage
    corpus_entry_id         VARCHAR(100),              -- FK to cce.causal_corpus when appended
    provenance              VARCHAR(50) DEFAULT 'live_intervention',
    
    created_at              TIMESTAMP DEFAULT NOW(),
    observation_closed_at   TIMESTAMP                  -- Set when outcome window closes
);

CREATE INDEX IF NOT EXISTS idx_intervention_session 
    ON cce.intervention_log(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_intervention_template 
    ON cce.intervention_log(template_id, focus_area);
CREATE INDEX IF NOT EXISTS idx_intervention_observation 
    ON cce.intervention_log(observation_closed_at) WHERE observation_closed_at IS NULL;

-- ============================================================================
-- Table 5: cce.graph_snapshots
-- ============================================================================
-- Point-in-time causal graph state for audit, diff, and intervention feedback attribution

CREATE TABLE IF NOT EXISTS cce.graph_snapshots (
    snapshot_id         VARCHAR(100) PRIMARY KEY,
    session_id          VARCHAR(100),
    vertical            VARCHAR(50),
    user_query          TEXT,
    graph_data          JSONB NOT NULL,                -- nx.node_link_data output
    graph_metadata      JSONB NOT NULL,                -- GraphMetadata dict
    node_count          INTEGER,
    edge_count          INTEGER,
    mean_confidence     NUMERIC(4,3),
    observable_ratio    NUMERIC(4,3),
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_session  
    ON cce.graph_snapshots(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_vertical 
    ON cce.graph_snapshots(vertical, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_confidence 
    ON cce.graph_snapshots(mean_confidence DESC);

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE cce.causal_corpus IS 
    'Seed + live causal relationship corpus. Used by N5 CausalValidationLayer for edge confidence grounding.';
COMMENT ON TABLE cce.causal_adjacency IS 
    'Structural edge lookups for fast node_id-based queries. Populated from causal_corpus + node_id mappings.';
COMMENT ON TABLE cce.metric_registry IS 
    'Metric definitions the causal engine reasons over. Optional if using ChromaDB for metric registry.';
COMMENT ON TABLE cce.intervention_log IS 
    'Dashboard user action → causal feedback record. Required for intervention feedback loop.';
COMMENT ON TABLE cce.graph_snapshots IS 
    'Point-in-time causal graph state for audit, diff, and intervention feedback attribution.';
