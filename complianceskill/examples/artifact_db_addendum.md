# Addendum — PostgreSQL Metadata & Version Registry
**Persistent storage layer for artifact orchestration, versioning, and pipeline state**

---

## Design Principle

The file system (git) is the **artifact store** — it holds the actual generated files and is the source of truth for content. PostgreSQL is the **metadata store** — it holds everything needed to query, schedule, diff, audit, and manage those artifacts without touching the file system.

The two are linked by `version_hash` (SHA-256 of artifact content). Nothing in Postgres duplicates file content. Everything in Postgres is either derived metadata, operational state, or audit trail.

---

## Database Schema

### Table 1 — `artifact_groups`

Master registry of all known dashboard groups. One row per group, one row forever — updated in place as versions change.

```sql
CREATE TABLE artifact_groups (
    group_id                VARCHAR(120)    PRIMARY KEY,
    -- e.g. "soc2_audit_hybrid_compliance"

    -- Identity
    use_case_group          VARCHAR(80)     NOT NULL,
    domain                  VARCHAR(80)     NOT NULL,
    framework               TEXT[]          NOT NULL DEFAULT '{}',
    audience                VARCHAR(60),
    complexity              VARCHAR(20),
    template_id             VARCHAR(80),
    theme                   VARCHAR(20),

    -- Current version pointer
    current_version         VARCHAR(20)     NOT NULL DEFAULT '0.0.0',
    current_version_id      UUID            REFERENCES artifact_versions(version_id),
    status                  VARCHAR(30)     NOT NULL DEFAULT 'active',
    -- active | archived | generation_failed | pending_first_run

    -- Artifact file paths (relative to /artifacts/{group_id}/latest/)
    layout_spec_path        TEXT,
    cubejs_schema_path      TEXT,
    cubejs_cube_paths       TEXT[]          DEFAULT '{}',
    n8n_workflow_path       TEXT,

    -- Scheduling
    schedule_cron           VARCHAR(60),
    -- e.g. "0 9 1 * *"
    schedule_timeframe      VARCHAR(20),
    -- daily | weekly | monthly | quarterly
    last_run_at             TIMESTAMPTZ,
    next_run_at             TIMESTAMPTZ,
    last_run_status         VARCHAR(30),
    -- success | failed | skipped | running

    -- Source inputs (hashes for staleness detection)
    layout_spec_hash        CHAR(64),
    gold_table_hashes       JSONB           DEFAULT '{}',
    -- {table_name: sha256_hash}
    metric_catalog_hash     CHAR(64),
    control_taxonomy_hash   CHAR(64),

    -- Counts (denormalized for query perf)
    control_anchor_count    SMALLINT        DEFAULT 0,
    cube_count              SMALLINT        DEFAULT 0,
    measure_count           SMALLINT        DEFAULT 0,
    n8n_node_count          SMALLINT        DEFAULT 0,
    alert_condition_count   SMALLINT        DEFAULT 0,

    -- Audit
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by              VARCHAR(80),
    approved_by             VARCHAR(80)
);

CREATE INDEX idx_artifact_groups_domain    ON artifact_groups(domain);
CREATE INDEX idx_artifact_groups_status    ON artifact_groups(status);
CREATE INDEX idx_artifact_groups_next_run  ON artifact_groups(next_run_at)
    WHERE status = 'active';
```

---

### Table 2 — `artifact_versions`

Immutable version history. One row per version per group — never updated, only inserted. This is the audit trail.

```sql
CREATE TABLE artifact_versions (
    version_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id                VARCHAR(120)    NOT NULL REFERENCES artifact_groups(group_id),
    version                 VARCHAR(20)     NOT NULL,
    -- semver: "1.2.0"

    -- Version metadata
    bump_type               VARCHAR(10)     NOT NULL,
    -- major | minor | patch
    bump_trigger            VARCHAR(200),
    -- e.g. "new_metric_added: training.avg_completion_days"
    is_current              BOOLEAN         NOT NULL DEFAULT FALSE,

    -- File system reference
    fs_path                 TEXT            NOT NULL,
    -- /artifacts/{group_id}/v{version}/
    git_commit_hash         CHAR(40),

    -- Artifact content hashes (for diff and integrity check)
    layout_spec_hash        CHAR(64)        NOT NULL,
    cubejs_hash             CHAR(64)        NOT NULL,
    n8n_hash                CHAR(64)        NOT NULL,
    manifest_hash           CHAR(64)        NOT NULL,

    -- Input hashes at time of generation (for staleness comparison)
    input_layout_spec_hash  CHAR(64),
    input_gold_table_hashes JSONB           DEFAULT '{}',
    input_metric_hash       CHAR(64),
    input_control_hash      CHAR(64),

    -- Snapshot of key counts at this version
    control_anchors         TEXT[]          DEFAULT '{}',
    gold_tables             TEXT[]          DEFAULT '{}',
    cube_count              SMALLINT,
    measure_count           SMALLINT,
    n8n_node_count          SMALLINT,
    alert_condition_count   SMALLINT,

    -- Pipeline provenance
    resolve_path            VARCHAR(30),
    -- decision_tree | llm_advisor
    validation_passed       BOOLEAN         NOT NULL DEFAULT TRUE,
    validation_errors       JSONB           DEFAULT '[]',
    generation_duration_ms  INTEGER,

    -- LLM provenance
    cubejs_model            VARCHAR(60),
    n8n_model               VARCHAR(60),
    changelog_model         VARCHAR(60),

    -- Changelog
    changelog_entry         TEXT,
    summary                 TEXT,

    -- Audit
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    approved_by             VARCHAR(80),
    approved_at             TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_artifact_versions_unique
    ON artifact_versions(group_id, version);
CREATE INDEX idx_artifact_versions_group_current
    ON artifact_versions(group_id, is_current)
    WHERE is_current = TRUE;
CREATE INDEX idx_artifact_versions_git
    ON artifact_versions(git_commit_hash);
```

---

### Table 3 — `control_anchor_bindings`

Normalized junction table: which control anchors are active in which group version. Enables querying "which groups cover CC7?" without parsing JSON.

```sql
CREATE TABLE control_anchor_bindings (
    id                      BIGSERIAL       PRIMARY KEY,
    group_id                VARCHAR(120)    NOT NULL REFERENCES artifact_groups(group_id),
    version_id              UUID            NOT NULL REFERENCES artifact_versions(version_id),
    control_id              VARCHAR(30)     NOT NULL,
    -- e.g. "CC7", "164.312(b)", "GOVERN"
    framework               VARCHAR(30)     NOT NULL,
    -- soc2 | hipaa | nist_ai_rmf
    control_domain          VARCHAR(80),
    focus_area              VARCHAR(80),
    is_current_version      BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Metric binding
    metric_id               VARCHAR(120),
    cube_measure            VARCHAR(120),
    -- e.g. "SnykVulnFindings.criticalUnpatchedCount"

    -- Strip cell
    strip_cell_label        VARCHAR(80),
    strip_cell_position     SMALLINT,

    -- Alert
    has_alert               BOOLEAN         DEFAULT FALSE,
    alert_threshold_warning NUMERIC,
    alert_threshold_critical NUMERIC,
    alert_good_direction    VARCHAR(10),
    -- up | down | neutral
    alert_severity_max      VARCHAR(20)
);

CREATE INDEX idx_cab_group_current
    ON control_anchor_bindings(group_id, is_current_version)
    WHERE is_current_version = TRUE;
CREATE INDEX idx_cab_control_current
    ON control_anchor_bindings(control_id, is_current_version)
    WHERE is_current_version = TRUE;
CREATE INDEX idx_cab_framework
    ON control_anchor_bindings(framework);
```

---

### Table 4 — `gold_table_dependencies`

Maps gold tables to the groups that consume them. The dependency graph in relational form. Drives cascade detection.

```sql
CREATE TABLE gold_table_dependencies (
    id                      BIGSERIAL       PRIMARY KEY,
    gold_table              VARCHAR(200)    NOT NULL,
    -- e.g. "gold.csod_course_completion"
    group_id                VARCHAR(120)    NOT NULL REFERENCES artifact_groups(group_id),
    version_id              UUID            NOT NULL REFERENCES artifact_versions(version_id),
    is_current_version      BOOLEAN         NOT NULL DEFAULT FALSE,

    -- What the table contributes to this group
    cube_name               VARCHAR(120),
    metric_ids              TEXT[]          DEFAULT '{}',
    measure_names           TEXT[]          DEFAULT '{}',

    -- Staleness tracking
    last_known_schema_hash  CHAR(64),
    schema_changed_at       TIMESTAMPTZ,
    staleness_signal        VARCHAR(60),
    -- none | column_added | column_removed | column_renamed | type_changed

    UNIQUE (gold_table, group_id, version_id)
);

CREATE INDEX idx_gtd_table_current
    ON gold_table_dependencies(gold_table, is_current_version)
    WHERE is_current_version = TRUE;
CREATE INDEX idx_gtd_group
    ON gold_table_dependencies(group_id, is_current_version)
    WHERE is_current_version = TRUE;
```

---

### Table 5 — `orchestrator_runs`

One row per orchestrator execution (a run may process multiple groups). Operational log for scheduling, retry management, and run history.

```sql
CREATE TABLE orchestrator_runs (
    run_id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_by            VARCHAR(30)     NOT NULL,
    -- schedule | manual | api | cascade | staleness_scan
    trigger_detail          TEXT,
    -- e.g. "gold.csod_course_completion schema change"
    status                  VARCHAR(20)     NOT NULL DEFAULT 'running',
    -- running | complete | partial_failure | failed

    -- Queue snapshot
    groups_queued           TEXT[]          DEFAULT '{}',
    groups_processed        TEXT[]          DEFAULT '{}',
    groups_failed           TEXT[]          DEFAULT '{}',
    groups_skipped          TEXT[]          DEFAULT '{}',

    -- Timing
    started_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    duration_ms             INTEGER,

    -- Error summary
    error_summary           JSONB           DEFAULT '[]',
    -- [{group_id, stage, error_message}]

    -- Run config
    force_regenerate        BOOLEAN         DEFAULT FALSE,
    bump_type_override      VARCHAR(10)
);

CREATE INDEX idx_orchestrator_runs_status ON orchestrator_runs(status);
CREATE INDEX idx_orchestrator_runs_started ON orchestrator_runs(started_at DESC);
```

---

### Table 6 — `group_run_log`

One row per group per orchestrator run. Granular per-group execution record.

```sql
CREATE TABLE group_run_log (
    id                      BIGSERIAL       PRIMARY KEY,
    run_id                  UUID            NOT NULL REFERENCES orchestrator_runs(run_id),
    group_id                VARCHAR(120)    NOT NULL REFERENCES artifact_groups(group_id),
    version_id              UUID            REFERENCES artifact_versions(version_id),

    -- Execution
    status                  VARCHAR(20)     NOT NULL,
    -- success | failed | skipped | validation_failed
    stage_reached           VARCHAR(30),
    -- intake | bind | layout | cubejs | n8n | version | validation | storage | notify
    bump_type               VARCHAR(10),
    old_version             VARCHAR(20),
    new_version             VARCHAR(20),
    skip_reason             TEXT,
    -- e.g. "no_staleness_signal"

    -- Timing per stage (ms)
    duration_ms_total       INTEGER,
    duration_ms_cubejs      INTEGER,
    duration_ms_n8n         INTEGER,
    duration_ms_storage     INTEGER,

    -- LLM token usage
    tokens_cubejs           INTEGER,
    tokens_n8n              INTEGER,
    tokens_changelog        INTEGER,
    tokens_total            INTEGER,

    -- Validation
    validation_passed       BOOLEAN,
    validation_errors       JSONB           DEFAULT '[]',

    -- Errors
    error_stage             VARCHAR(30),
    error_message           TEXT,
    error_detail            JSONB,

    started_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ
);

CREATE INDEX idx_group_run_log_run    ON group_run_log(run_id);
CREATE INDEX idx_group_run_log_group  ON group_run_log(group_id, started_at DESC);
CREATE INDEX idx_group_run_log_status ON group_run_log(status);
```

---

### Table 7 — `staleness_signals`

Incoming change events that trigger regeneration. Written by external sources (DBT manifest watcher, metric catalog change hook). Read and consumed by `dependency_check_node`.

```sql
CREATE TABLE staleness_signals (
    signal_id               UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_type             VARCHAR(40)     NOT NULL,
    -- gold_table_schema | metric_catalog | control_taxonomy | threshold_change
    -- layout_spec_change | manual_force | cascade
    source                  VARCHAR(80),
    -- e.g. "dbt_manifest_watcher", "metric_catalog_api", "admin"

    -- What changed
    affected_resource       VARCHAR(200)    NOT NULL,
    -- gold table name, metric_id, control_id, group_id, etc.
    change_detail           JSONB           DEFAULT '{}',
    -- {old_hash, new_hash, changed_columns: [...]} etc.

    -- Derived impact
    affected_group_ids      TEXT[]          DEFAULT '{}',
    -- populated by dependency_check_node
    implied_bump_type       VARCHAR(10),
    -- major | minor | patch

    -- Lifecycle
    status                  VARCHAR(20)     NOT NULL DEFAULT 'pending',
    -- pending | processing | consumed | ignored
    consumed_by_run_id      UUID            REFERENCES orchestrator_runs(run_id),
    consumed_at             TIMESTAMPTZ,
    ignore_reason           TEXT,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at              TIMESTAMPTZ
    -- signals older than 30 days are auto-ignored if not consumed
);

CREATE INDEX idx_staleness_signals_pending
    ON staleness_signals(status, created_at)
    WHERE status = 'pending';
CREATE INDEX idx_staleness_signals_resource
    ON staleness_signals(affected_resource);
```

---

### Table 8 — `cubejs_measures`

Flattened measure registry across all current group versions. Enables queries like "which groups expose training.completion_rate?" without reading cube files.

```sql
CREATE TABLE cubejs_measures (
    id                      BIGSERIAL       PRIMARY KEY,
    group_id                VARCHAR(120)    NOT NULL REFERENCES artifact_groups(group_id),
    version_id              UUID            NOT NULL REFERENCES artifact_versions(version_id),
    is_current_version      BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Cube reference
    cube_name               VARCHAR(120)    NOT NULL,
    gold_table              VARCHAR(200)    NOT NULL,

    -- Measure definition
    measure_name            VARCHAR(120)    NOT NULL,
    -- snake_case, e.g. "completion_rate"
    full_measure_name       VARCHAR(250)    NOT NULL,
    -- CubeName.measure_name
    metric_id               VARCHAR(120),
    sql_expression          TEXT,
    measure_type            VARCHAR(20),
    -- count | sum | avg | number | countDistinct | max | min
    format                  VARCHAR(20),
    -- number | currency | percent
    control_id              VARCHAR(30),
    description             TEXT,

    UNIQUE (group_id, version_id, full_measure_name)
);

CREATE INDEX idx_cubejs_measures_metric
    ON cubejs_measures(metric_id, is_current_version)
    WHERE is_current_version = TRUE;
CREATE INDEX idx_cubejs_measures_control
    ON cubejs_measures(control_id, is_current_version)
    WHERE is_current_version = TRUE;
CREATE INDEX idx_cubejs_measures_cube
    ON cubejs_measures(cube_name, is_current_version)
    WHERE is_current_version = TRUE;
```

---

### Table 9 — `n8n_alert_registry`

Flattened alert condition registry for all active n8n workflows. Enables querying active alerts without reading workflow JSON.

```sql
CREATE TABLE n8n_alert_registry (
    id                      BIGSERIAL       PRIMARY KEY,
    group_id                VARCHAR(120)    NOT NULL REFERENCES artifact_groups(group_id),
    version_id              UUID            NOT NULL REFERENCES artifact_versions(version_id),
    is_current_version      BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Alert identity
    control_id              VARCHAR(30)     NOT NULL,
    metric_id               VARCHAR(120),
    cube_measure            VARCHAR(250),
    alert_label             VARCHAR(200),

    -- Condition
    operator                VARCHAR(5),
    threshold               NUMERIC,
    severity                VARCHAR(20),
    -- critical | warning | info
    good_direction          VARCHAR(10),

    -- n8n node reference
    n8n_node_id             VARCHAR(80),
    n8n_node_name           VARCHAR(120),

    -- Runtime state (updated by n8n callback or monitoring)
    last_evaluated_at       TIMESTAMPTZ,
    last_alert_fired_at     TIMESTAMPTZ,
    current_value           NUMERIC,
    current_status          VARCHAR(20)     DEFAULT 'unknown',
    -- unknown | passing | warning | critical

    UNIQUE (group_id, version_id, control_id, metric_id, threshold)
);

CREATE INDEX idx_n8n_alert_control
    ON n8n_alert_registry(control_id, is_current_version)
    WHERE is_current_version = TRUE;
CREATE INDEX idx_n8n_alert_firing
    ON n8n_alert_registry(current_status, is_current_version)
    WHERE is_current_version = TRUE AND current_status IN ('warning', 'critical');
```

---

## Version Transition Logic

When a new version is committed, the following operations run in a single transaction to maintain consistency between Postgres and the file system.

```sql
-- Version transition stored procedure
CREATE OR REPLACE PROCEDURE promote_version(
    p_group_id      VARCHAR,
    p_new_version   VARCHAR,
    p_version_id    UUID,
    p_approved_by   VARCHAR
)
LANGUAGE plpgsql AS $$
BEGIN
    -- 1. Mark all prior versions as not current
    UPDATE artifact_versions
    SET    is_current = FALSE
    WHERE  group_id = p_group_id
    AND    is_current = TRUE;

    -- 2. Mark new version as current
    UPDATE artifact_versions
    SET    is_current = TRUE,
           approved_by = p_approved_by,
           approved_at = NOW()
    WHERE  version_id = p_version_id;

    -- 3. Update group's current version pointer
    UPDATE artifact_groups
    SET    current_version    = p_new_version,
           current_version_id = p_version_id,
           last_run_at        = NOW(),
           last_run_status    = 'success',
           updated_at         = NOW()
    WHERE  group_id = p_group_id;

    -- 4. Flip is_current on all junction tables
    UPDATE control_anchor_bindings
    SET    is_current_version = (version_id = p_version_id)
    WHERE  group_id = p_group_id;

    UPDATE gold_table_dependencies
    SET    is_current_version = (version_id = p_version_id)
    WHERE  group_id = p_group_id;

    UPDATE cubejs_measures
    SET    is_current_version = (version_id = p_version_id)
    WHERE  group_id = p_group_id;

    UPDATE n8n_alert_registry
    SET    is_current_version = (version_id = p_version_id)
    WHERE  group_id = p_group_id;

    COMMIT;
END;
$$;
```

This procedure is called by `storage_node` after the git commit hash is confirmed. The file system write and the Postgres write are not in the same transaction — the git commit runs first, and if it succeeds the procedure runs. If Postgres fails after git succeeds, `storage_node` retries the procedure only (not the git commit), using the already-confirmed `git_commit_hash`.

---

## Key Operational Queries

### Scheduler: groups due for a run

```sql
SELECT
    g.group_id,
    g.current_version,
    g.schedule_timeframe,
    g.next_run_at,
    COUNT(s.signal_id)          AS pending_signals,
    MAX(s.implied_bump_type)    AS max_bump_type
FROM artifact_groups g
LEFT JOIN staleness_signals s
    ON  g.group_id = ANY(s.affected_group_ids)
    AND s.status = 'pending'
WHERE g.status = 'active'
  AND (
      g.next_run_at <= NOW()
      OR COUNT(s.signal_id) > 0
  )
GROUP BY g.group_id, g.current_version, g.schedule_timeframe, g.next_run_at
ORDER BY
    CASE MAX(s.implied_bump_type) WHEN 'major' THEN 1 WHEN 'minor' THEN 2 ELSE 3 END,
    g.control_anchor_count DESC;
```

### Coverage: which groups cover a given control

```sql
SELECT
    g.group_id,
    g.domain,
    g.framework,
    g.current_version,
    cab.metric_id,
    cab.strip_cell_label,
    cab.has_alert,
    cab.alert_threshold_warning,
    cab.alert_threshold_critical
FROM control_anchor_bindings cab
JOIN artifact_groups g ON cab.group_id = g.group_id
WHERE cab.control_id = 'CC7'
  AND cab.is_current_version = TRUE
  AND g.status = 'active'
ORDER BY g.domain;
```

### Cascade detection: groups affected by a gold table change

```sql
SELECT DISTINCT
    gtd.group_id,
    g.current_version,
    g.status,
    gtd.cube_name,
    gtd.last_known_schema_hash,
    gtd.staleness_signal
FROM gold_table_dependencies gtd
JOIN artifact_groups g ON gtd.group_id = g.group_id
WHERE gtd.gold_table = 'gold.csod_course_completion'
  AND gtd.is_current_version = TRUE
  AND g.status = 'active';
```

### Audit: full version history for a group with diff summary

```sql
SELECT
    v.version,
    v.bump_type,
    v.bump_trigger,
    v.control_anchors,
    v.cube_count,
    v.measure_count,
    v.n8n_node_count,
    v.alert_condition_count,
    v.git_commit_hash,
    v.approved_by,
    v.approved_at,
    v.changelog_entry
FROM artifact_versions v
WHERE v.group_id = 'soc2_audit_hybrid_compliance'
ORDER BY v.created_at DESC;
```

### Active alerts: current firing conditions across all groups

```sql
SELECT
    g.group_id,
    g.domain,
    a.control_id,
    a.metric_id,
    a.alert_label,
    a.severity,
    a.current_value,
    a.threshold,
    a.operator,
    a.current_status,
    a.last_alert_fired_at
FROM n8n_alert_registry a
JOIN artifact_groups g ON a.group_id = g.group_id
WHERE a.is_current_version = TRUE
  AND a.current_status IN ('warning', 'critical')
ORDER BY
    CASE a.current_status WHEN 'critical' THEN 1 ELSE 2 END,
    a.last_alert_fired_at DESC;
```

### Token usage: LLM cost by group and run

```sql
SELECT
    grl.group_id,
    COUNT(*)                        AS run_count,
    SUM(grl.tokens_total)           AS total_tokens,
    SUM(grl.tokens_cubejs)          AS cubejs_tokens,
    SUM(grl.tokens_n8n)             AS n8n_tokens,
    AVG(grl.duration_ms_total)      AS avg_duration_ms,
    MAX(grl.started_at)             AS last_run
FROM group_run_log grl
WHERE grl.status = 'success'
  AND grl.started_at >= NOW() - INTERVAL '30 days'
GROUP BY grl.group_id
ORDER BY total_tokens DESC;
```

---

## Storage Agent — Write Sequence

The `storage_node` writes to both git and Postgres in this order. Steps 1–4 are file system, steps 5–10 are Postgres.

```
1.  Write versioned directory to /artifacts/{group_id}/v{version}/
2.  Update /artifacts/{group_id}/latest symlink
3.  git add + git commit → capture git_commit_hash
4.  Update /artifacts/registry/*.json (local JSON files kept as hot cache)

5.  INSERT INTO artifact_versions (all fields including git_commit_hash)
6.  INSERT INTO control_anchor_bindings (from resolution_payload.control_anchors)
7.  INSERT INTO gold_table_dependencies (from current_group.gold_tables)
8.  INSERT INTO cubejs_measures (parsed from generated cube files)
9.  INSERT INTO n8n_alert_registry (from alert_conditions used in generation)
10. CALL promote_version(group_id, new_version, version_id, approved_by)
    — this single transaction flips is_current on all tables and updates artifact_groups
11. UPDATE staleness_signals SET status = 'consumed' WHERE signal_id = ANY(consumed_signals)
12. UPDATE orchestrator_runs (increment processed count, update timing)
```

---

## Schema Diagram (Relationships)

```
artifact_groups  ──< artifact_versions (one per bump)
      │                       │
      │              control_anchor_bindings
      │              gold_table_dependencies
      │              cubejs_measures
      │              n8n_alert_registry
      │
      └──< group_run_log >── orchestrator_runs
                                    │
                          staleness_signals (consumed_by)
```

---

## Migration Notes

### From JSON File Registry → Postgres

The four JSON registry files described in the main design doc become secondary caches populated from Postgres, not primary stores.

| JSON File (prior design) | Replaces With | Kept As |
|---|---|---|
| `artifact_versions.json` | `artifact_versions` table | Hot cache (written after Postgres commit) |
| `dependency_graph.json` | `gold_table_dependencies` table | Hot cache |
| `staleness_index.json` | `staleness_signals` + `artifact_groups.last_run_*` | Hot cache |
| `group_manifest.json` | `artifact_groups` table | Removed — Postgres is source of truth |

The hot cache JSON files remain on disk so the orchestrator can start without a Postgres connection in degraded mode. They are always written after the Postgres write succeeds — never before.

### Postgres Connection

The orchestrator and all agents connect via a single `CCE_DB_URL` environment variable. The `storage_node` acquires a connection only at Step 5 — generation runs fully in memory without a DB connection. This keeps the DB write surface narrow and the generation agents stateless.
