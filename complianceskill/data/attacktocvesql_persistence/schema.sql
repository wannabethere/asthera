-- ============================================================================
-- ATT&CK → CIS Control Mapping — Postgres Schema
-- ============================================================================
-- Designed to sit inside the CCE database alongside your existing tables.
-- Run once during CCE bootstrap.  Safe to re-run (IF NOT EXISTS everywhere).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. ATT&CK Techniques  (seeded by ingest_stix_to_postgres())
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attack_techniques (
    technique_id    TEXT PRIMARY KEY,          -- e.g. "T1078", "T1059.001"
    name            TEXT NOT NULL,
    description     TEXT,
    tactics         TEXT[]    DEFAULT '{}',
    platforms       TEXT[]    DEFAULT '{}',
    data_sources    TEXT[]    DEFAULT '{}',
    detection       TEXT,
    mitigations     JSONB     DEFAULT '[]',    -- [{id, name}]
    url             TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attack_techniques_tactics
    ON attack_techniques USING GIN (tactics);

CREATE INDEX IF NOT EXISTS idx_attack_techniques_platforms
    ON attack_techniques USING GIN (platforms);

COMMENT ON TABLE attack_techniques IS
    'MITRE ATT&CK Enterprise technique catalogue, seeded from STIX bundle.';


-- ---------------------------------------------------------------------------
-- 2. CIS Risk Scenarios  (seeded from YAML by load_cis_scenarios())
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cis_risk_scenarios (
    scenario_id     TEXT PRIMARY KEY,          -- "CIS-RISK-001" .. "CIS-RISK-067"
    name            TEXT NOT NULL,
    asset           TEXT NOT NULL,
    trigger         TEXT,
    loss_outcomes   TEXT[]  DEFAULT '{}',
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cis_scenarios_asset
    ON cis_risk_scenarios (asset);

COMMENT ON TABLE cis_risk_scenarios IS
    'CIS Controls v8.1 risk scenarios, imported from YAML registry.';


-- ---------------------------------------------------------------------------
-- 3. Control Mappings  (populated by the LangGraph pipeline)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attack_control_mappings (
    id                  BIGSERIAL PRIMARY KEY,
    technique_id        TEXT        NOT NULL REFERENCES attack_techniques(technique_id) ON DELETE CASCADE,
    scenario_id         TEXT        NOT NULL REFERENCES cis_risk_scenarios(scenario_id) ON DELETE CASCADE,
    relevance_score     NUMERIC(4,3) NOT NULL CHECK (relevance_score BETWEEN 0 AND 1),
    confidence          TEXT        NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    rationale           TEXT,
    attack_tactics      TEXT[]      DEFAULT '{}',
    attack_platforms    TEXT[]      DEFAULT '{}',
    loss_outcomes       TEXT[]      DEFAULT '{}',

    -- Pipeline provenance
    mapping_run_id      UUID,                   -- ties mappings to a single pipeline run
    retrieval_source    TEXT,                   -- "qdrant" | "chroma" | "yaml_fallback"
    validated           BOOLEAN     DEFAULT FALSE,
    validation_notes    TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (technique_id, scenario_id)          -- one row per pair, UPSERT-safe
);

CREATE INDEX IF NOT EXISTS idx_mappings_technique
    ON attack_control_mappings (technique_id);

CREATE INDEX IF NOT EXISTS idx_mappings_scenario
    ON attack_control_mappings (scenario_id);

CREATE INDEX IF NOT EXISTS idx_mappings_confidence
    ON attack_control_mappings (confidence);

CREATE INDEX IF NOT EXISTS idx_mappings_relevance
    ON attack_control_mappings (relevance_score DESC);

COMMENT ON TABLE attack_control_mappings IS
    'ATT&CK technique → CIS risk scenario mappings produced by the LangGraph enrichment pipeline.';


-- ---------------------------------------------------------------------------
-- 4. Mapping Runs  (audit trail for batch enrichment jobs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mapping_runs (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_by        TEXT,                   -- "batch_enricher" | "cce_node" | "cli"
    technique_filter    TEXT,                   -- NULL = all techniques
    asset_filter        TEXT,
    scenario_count      INT,
    technique_count     INT,
    mapping_count       INT,
    coverage_pct        NUMERIC(5,2),
    duration_seconds    NUMERIC(8,2),
    status              TEXT DEFAULT 'running' CHECK (status IN ('running','complete','failed')),
    error_message       TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

COMMENT ON TABLE mapping_runs IS
    'Audit log for each batch enrichment run or CCE pipeline invocation.';


-- ---------------------------------------------------------------------------
-- 5. Evaluation Results  (persisted from evaluation.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mapping_evaluations (
    eval_id             BIGSERIAL PRIMARY KEY,
    run_id              UUID REFERENCES mapping_runs(run_id),
    scenario_coverage_pct   NUMERIC(5,2),
    total_mappings          INT,
    unique_techniques       INT,
    tactic_breadth_pct      NUMERIC(5,2),
    avg_relevance_score     NUMERIC(4,3),
    precision_vs_gt         NUMERIC(4,3),
    recall_vs_gt            NUMERIC(4,3),
    issues_count            INT,
    full_report             JSONB,              -- complete EvaluationReport.to_dict()
    evaluated_at            TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE mapping_evaluations IS
    'Quality metrics snapshots produced by evaluation.py after each batch run.';


-- ---------------------------------------------------------------------------
-- 6. Convenience views
-- ---------------------------------------------------------------------------

-- Coverage per CIS asset domain
CREATE OR REPLACE VIEW v_asset_coverage AS
SELECT
    s.asset,
    COUNT(DISTINCT s.scenario_id)                   AS total_scenarios,
    COUNT(DISTINCT m.scenario_id)                   AS mapped_scenarios,
    ROUND(COUNT(DISTINCT m.scenario_id)::NUMERIC /
          NULLIF(COUNT(DISTINCT s.scenario_id),0) * 100, 1) AS coverage_pct,
    COUNT(m.id)                                     AS total_mappings,
    COUNT(DISTINCT m.technique_id)                  AS unique_techniques
FROM cis_risk_scenarios s
LEFT JOIN attack_control_mappings m ON m.scenario_id = s.scenario_id
GROUP BY s.asset
ORDER BY coverage_pct DESC;

COMMENT ON VIEW v_asset_coverage IS
    'Control mapping coverage broken down by CIS asset domain.';


-- Most common ATT&CK techniques across all scenarios
CREATE OR REPLACE VIEW v_top_techniques AS
SELECT
    m.technique_id,
    t.name                                          AS technique_name,
    t.tactics,
    COUNT(DISTINCT m.scenario_id)                   AS scenario_count,
    ROUND(AVG(m.relevance_score), 3)                AS avg_relevance,
    COUNT(*) FILTER (WHERE m.confidence = 'high')   AS high_confidence_mappings
FROM attack_control_mappings m
JOIN attack_techniques t ON t.technique_id = m.technique_id
GROUP BY m.technique_id, t.name, t.tactics
ORDER BY scenario_count DESC, avg_relevance DESC;

COMMENT ON VIEW v_top_techniques IS
    'ATT&CK techniques most frequently mapped across CIS risk scenarios.';


-- Unmapped scenarios (the gap list)
CREATE OR REPLACE VIEW v_unmapped_scenarios AS
SELECT
    s.scenario_id,
    s.name,
    s.asset,
    s.loss_outcomes,
    s.trigger
FROM cis_risk_scenarios s
LEFT JOIN attack_control_mappings m ON m.scenario_id = s.scenario_id
WHERE m.id IS NULL
ORDER BY s.scenario_id;

COMMENT ON VIEW v_unmapped_scenarios IS
    'CIS risk scenarios that have no confirmed ATT&CK technique mapping.';


-- High-confidence mapping summary per scenario
CREATE OR REPLACE VIEW v_scenario_control_summary AS
SELECT
    s.scenario_id,
    s.name,
    s.asset,
    COUNT(m.id)                                             AS total_mappings,
    COUNT(m.id) FILTER (WHERE m.confidence = 'high')       AS high_confidence,
    ARRAY_AGG(DISTINCT m.technique_id ORDER BY m.technique_id) AS technique_ids,
    ROUND(MAX(m.relevance_score), 3)                        AS best_relevance
FROM cis_risk_scenarios s
LEFT JOIN attack_control_mappings m ON m.scenario_id = s.scenario_id
GROUP BY s.scenario_id, s.name, s.asset
ORDER BY total_mappings DESC NULLS LAST;

COMMENT ON VIEW v_scenario_control_summary IS
    'Per-scenario mapping summary — total, high-confidence, and technique list.';


-- ---------------------------------------------------------------------------
-- 7. UPSERT helper function (called from Python persistence layer)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION upsert_attack_control_mapping(
    p_technique_id      TEXT,
    p_scenario_id       TEXT,
    p_relevance_score   NUMERIC,
    p_confidence        TEXT,
    p_rationale         TEXT,
    p_attack_tactics    TEXT[],
    p_attack_platforms  TEXT[],
    p_loss_outcomes     TEXT[],
    p_run_id            UUID,
    p_retrieval_source  TEXT,
    p_validated         BOOLEAN DEFAULT FALSE,
    p_validation_notes  TEXT    DEFAULT NULL
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO attack_control_mappings (
        technique_id, scenario_id, relevance_score, confidence, rationale,
        attack_tactics, attack_platforms, loss_outcomes,
        mapping_run_id, retrieval_source, validated, validation_notes, updated_at
    ) VALUES (
        p_technique_id, p_scenario_id, p_relevance_score, p_confidence, p_rationale,
        p_attack_tactics, p_attack_platforms, p_loss_outcomes,
        p_run_id, p_retrieval_source, p_validated, p_validation_notes, NOW()
    )
    ON CONFLICT (technique_id, scenario_id) DO UPDATE SET
        relevance_score   = EXCLUDED.relevance_score,
        confidence        = EXCLUDED.confidence,
        rationale         = EXCLUDED.rationale,
        attack_tactics    = EXCLUDED.attack_tactics,
        attack_platforms  = EXCLUDED.attack_platforms,
        loss_outcomes     = EXCLUDED.loss_outcomes,
        mapping_run_id    = EXCLUDED.mapping_run_id,
        retrieval_source  = EXCLUDED.retrieval_source,
        validated         = EXCLUDED.validated,
        validation_notes  = EXCLUDED.validation_notes,
        updated_at        = NOW()
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

COMMENT ON FUNCTION upsert_attack_control_mapping IS
    'Safe upsert for a single ATT&CK→CIS mapping. Called from the Python persistence layer.';
