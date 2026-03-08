# Prompts — Artifact Generation Pipeline
**CubeJS Assembly + n8n Workflow + Version Changelog**

All prompts use `claude-sonnet-4-6`. Temperature guidance is per-prompt.
Enrichment hooks indicate where vector store retrieval replaces static examples.

---

## Prompt Index

| # | Name | Agent | Output | LLM Required |
|---|---|---|---|---|
| 1 | Gold Table → Cube Scaffold | CubeJS Agent | One `.js` cube file | Yes |
| 2 | Join Inference Between Cubes | CubeJS Agent | Joins block patch | Yes |
| 3 | CubeJS Schema YAML | CubeJS Agent | `schema.yml` | Yes (light) |
| 4 | Pre-Aggregation Planner | CubeJS Agent | `pre_aggregations.js` | Yes |
| 5 | n8n Workflow Assembly | n8n Agent | `n8n_workflow.json` | Yes |
| 6 | n8n Alert Conditions | n8n Agent | IF node parameter array | Yes |
| 7 | n8n Slack Alert Message | n8n Agent | Alert message strings | Yes |
| 8 | Changelog Entry | Version Agent | CHANGELOG.md entry | Yes |
| 9 | Artifact Manifest Summary | Version Agent | `manifest.json` summary | Yes (light) |

---

## Prompt 1 — Gold Table → Cube Scaffold

**Agent:** CubeJS Agent
**Called by:** `cubejs_node` — once per gold table in scope
**Temperature:** 0.2
**Output:** Complete Cube.js `.js` file for one gold table

**Variables:**
- `{cube_name}` — PascalCase from gold table (e.g., `CsodCourseCompletion`)
- `{sql_table}` — fully qualified gold table (e.g., `gold.csod_course_completion`)
- `{table_schema}` — JSON array of `{column_name, sql_type, nullable, description}` from DBT manifest
- `{assigned_measures}` — JSON array of `{metric_id, measure_name, sql_expr, type, format, control_id}`
- `{domain_display_name}` — e.g. `Learning & Training`
- `{metric_groups}` — which metric groups this cube serves

---

### SYSTEM

```
You are a CubeJS schema engineer. You write production-quality Cube.js cube definitions
in JavaScript (module.exports = {...} syntax).

Rules:
1. Output ONLY the JavaScript — no markdown, no explanation, no backticks.
2. Every measure must have: name, sql, type, and description.
3. Every dimension must have: name, sql, type. Add primaryKey: true for id columns.
4. Time dimensions must use type: 'time'.
5. Boolean columns use type: 'boolean'.
6. Format currency amounts with format: 'currency', percentages with format: 'percent'.
7. Add a top-level description to the cube summarizing its domain and purpose.
8. Do not add joins — those are handled separately.
9. Use snake_case for measure/dimension names matching the column names exactly.
10. Do not invent columns that are not in the provided schema.
```

### USER

```
Generate a Cube.js cube file for the following gold table.

Cube name: {cube_name}
SQL table: {sql_table}
Domain: {domain_display_name}
Metric groups served: {metric_groups}

Table schema (all available columns):
{table_schema}

Pre-assigned measures (these metrics are already mapped to this cube):
{assigned_measures}

All columns NOT in the assigned_measures list should become dimensions.
All assigned_measures should become cube measures using the provided sql_expr.
```

---

### Static Examples (few-shot, inject before user turn)

**Example 1 — LMS training completion cube:**

```javascript
// Input: CsodCourseCompletion | gold.csod_course_completion | Learning & Training
module.exports = {
  name: 'CsodCourseCompletion',
  description: 'Cornerstone OnDemand course assignment completion for Learning & Training. Serves training_completion and compliance_posture metric groups.',
  sql_table: 'gold.csod_course_completion',

  measures: {
    completionRate: {
      sql: `COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)`,
      type: 'number',
      format: 'percent',
      description: 'Percentage of assignments completed out of total assigned',
    },
    overdueCount: {
      sql: `COUNT(CASE WHEN due_date < CURRENT_DATE AND status != 'completed' THEN 1 END)`,
      type: 'count',
      description: 'Assignments past due date and not completed',
    },
    totalAssignments: { sql: `*`, type: 'count', description: 'Total course assignments' },
  },

  dimensions: {
    assignmentId: { sql: `assignment_id`, type: 'string', primaryKey: true },
    userId:       { sql: `user_id`,       type: 'string' },
    courseId:     { sql: `course_id`,     type: 'string' },
    status:       { sql: `status`,        type: 'string' },
    dueDate:      { sql: `due_date`,      type: 'time' },
    completedAt:  { sql: `completed_at`,  type: 'time' },
    department:   { sql: `department`,    type: 'string' },
  },
};
```

**Example 2 — Security vulnerability finding cube:**

```javascript
// Input: SnykVulnFindings | gold.snyk_vuln_findings | Security Operations
module.exports = {
  name: 'SnykVulnFindings',
  description: 'Snyk vulnerability findings for Security Operations. Serves risk_exposure and operational_security metric groups.',
  sql_table: 'gold.snyk_vuln_findings',

  measures: {
    criticalUnpatchedCount: {
      sql: `COUNT(CASE WHEN severity = 'critical' AND remediated_at IS NULL THEN 1 END)`,
      type: 'count',
      description: 'Unpatched critical severity vulnerabilities',
    },
    meanTimeToRemediate: {
      sql: `AVG(DATEDIFF('day', discovered_at, COALESCE(remediated_at, CURRENT_DATE)))`,
      type: 'number',
      format: 'number',
      description: 'Average days from discovery to remediation',
    },
  },

  dimensions: {
    cveId:        { sql: 'cve_id',        type: 'string', primaryKey: true },
    severity:     { sql: 'severity',      type: 'string' },
    discoveredAt: { sql: 'discovered_at', type: 'time' },
    remediatedAt: { sql: 'remediated_at', type: 'time' },
    assetId:      { sql: 'asset_id',      type: 'string' },
  },
};
```

**Enrichment hook:** Replace or prepend static examples with top-2 patterns retrieved from CubeJS Pattern Store, queried by embedding of `{domain} {table_type} {metric_groups}`.

---

## Prompt 2 — Join Inference Between Cubes

**Agent:** CubeJS Agent — Step 4
**Called by:** `cubejs_node` — once per group after all cube files are generated
**Temperature:** 0.1
**Output:** JSON joins array to patch into cube files

**Variables:**
- `{cube_list}` — JSON array of `{cube_name, sql_table, dimensions[]}` for all cubes in the group
- `{domain}` — for FK pattern context
- `{known_join_patterns}` — static map of common FK patterns per domain

---

### SYSTEM

```
You are a CubeJS join relationship engineer.
Given cube definitions, identify join relationships by matching dimension names that
appear in multiple cubes — these represent foreign keys.

Output ONLY valid JSON in this exact schema — no explanation, no markdown:
{
  "joins": [
    {
      "from_cube": "CubeName",
      "to_cube": "OtherCubeName",
      "join_sql": "${CubeName}.column = ${OtherCubeName}.column",
      "relationship": "many_to_one | one_to_many | one_to_one"
    }
  ]
}

Rules:
- Only join dimensions sharing the same name AND representing a foreign key
- Common FK patterns: user_id, employee_id, course_id, asset_id, department_id
- Do not join generic columns: status, created_at, updated_at, name
- relationship is from the perspective of from_cube
- If no clear join exists return: {"joins": []}
```

### USER

```
Domain: {domain}

Cube definitions (name + dimensions only):
{cube_list}

Known FK patterns for this domain: {known_join_patterns}

Identify all valid join relationships.
```

---

### Static Example

Input:
```json
[
  {"cube_name": "CsodCourseCompletion", "dimensions": ["userId", "courseId", "department", "dueDate"]},
  {"cube_name": "WorkdayEmployee", "dimensions": ["employeeId", "userId", "department", "hireDate"]}
]
```

Output:
```json
{
  "joins": [
    {
      "from_cube": "CsodCourseCompletion",
      "to_cube": "WorkdayEmployee",
      "join_sql": "${CsodCourseCompletion}.user_id = ${WorkdayEmployee}.user_id",
      "relationship": "many_to_one"
    }
  ]
}
```

---

## Prompt 3 — CubeJS Schema YAML

**Agent:** CubeJS Agent — Step 6
**Called by:** `cubejs_node` — once per group after cube files finalized
**Temperature:** 0.1
**Output:** `schema.yml` — Cube.js YAML entry point

**Variables:**
- `{group_id}` — e.g. `soc2_audit_hybrid_compliance`
- `{cube_file_names}` — list of `.js` files (e.g. `["CsodCourseCompletion.js", "SnykVulnFindings.js"]`)
- `{datasource_env_var}` — e.g. `CCE_DATASOURCE`
- `{domain}` — for context
- `{timeframe}` — dashboard timeframe for default date filter

---

### SYSTEM

```
You write Cube.js YAML configuration files.
Output ONLY valid YAML — no markdown, no explanation.
The schema.yml is the entry point that loads cube JS files and configures the datasource.
```

### USER

```
Generate schema.yml for a CubeJS deployment.

Group: {group_id}
Domain: {domain}
Cube files to include: {cube_file_names}
Datasource env var: {datasource_env_var}
Default timeframe for date filters: {timeframe}
```

---

### Static Example

Output:
```yaml
schemaVersion: '1'
datasources:
  default:
    type: duckdb
    url: "{{ env_var('CCE_DATASOURCE') }}"

cubes:
  - path: CsodCourseCompletion.js
  - path: SnykVulnFindings.js
  - path: WorkdayEmployee.js

queryRewrite:
  defaultDateRange:
    granularity: month
    rollingWindow:
      trailing: 1 month

context:
  groupId: soc2_audit_hybrid_compliance
  domain: hybrid_compliance
  generatedAt: "{{ now() }}"
```

---

## Prompt 4 — Pre-Aggregation Planner

**Agent:** CubeJS Agent — Step 5
**Called by:** `cubejs_node` — once per group using chart_specs from layout_spec
**Temperature:** 0.2
**Output:** `pre_aggregations.js`

**Variables:**
- `{strip_cells}` — list of `{metric_id, measure_name, cube_name}` for posture strip
- `{chart_specs}` — list of `{metric_group, chart_type, measures[], time_dimension, granularity, category_dimension}`
- `{timeframe}` — dashboard timeframe

---

### SYSTEM

```
You write Cube.js pre-aggregation definitions for dashboard performance optimization.
Output ONLY JavaScript — no markdown, no explanation.
Export a single const PREAGGS object.

Pre-aggregation type selection:
- rollup: strip cells and KPI cards (no time breakdown)
- rollup with timeDimension: time-series chart measures
- rollup with dimensions: bar/compare chart measures

Rules:
1. Strip cell measures → rollup, refreshKey: every 1 hour
2. Time-series chart measures → rollup with timeDimension, granularity from chart spec
3. Bar/compare chart measures → rollup with the category dimension
4. Name pattern: {CubeName}_{purpose}_{granularity}
5. scheduledRefresh: true on all entries
```

### USER

```
Generate pre_aggregations.js for this dashboard group.

Posture strip metrics (KPI rollups):
{strip_cells}

Chart specs (time-series and grouped rollups):
{chart_specs}

Default timeframe: {timeframe}
```

---

### Static Example

Input:
```
strip_cells: [{measure: "CsodCourseCompletion.completionRate"}, {measure: "SnykVulnFindings.criticalUnpatchedCount"}]
chart_specs: [
  {chart_type: "bar_compare", measure: "CsodCourseCompletion.completionRate", category_dim: "CsodCourseCompletion.department"},
  {chart_type: "trend_line", measure: "SnykVulnFindings.criticalUnpatchedCount", time_dim: "SnykVulnFindings.discoveredAt", granularity: "month"}
]
```

Output:
```javascript
const PREAGGS = {
  CsodCourseCompletion_stripKpi: {
    type: 'rollup',
    measures: [CsodCourseCompletion.completionRate, CsodCourseCompletion.totalAssignments],
    refreshKey: { every: '1 hour' },
    scheduledRefresh: true,
  },
  SnykVulnFindings_stripKpi: {
    type: 'rollup',
    measures: [SnykVulnFindings.criticalUnpatchedCount],
    refreshKey: { every: '1 hour' },
    scheduledRefresh: true,
  },
  CsodCourseCompletion_byDepartment: {
    type: 'rollup',
    measures: [CsodCourseCompletion.completionRate],
    dimensions: [CsodCourseCompletion.department],
    refreshKey: { every: '24 hours' },
    scheduledRefresh: true,
  },
  SnykVulnFindings_trendMonth: {
    type: 'rollup',
    measures: [SnykVulnFindings.criticalUnpatchedCount],
    timeDimension: SnykVulnFindings.discoveredAt,
    granularity: 'month',
    refreshKey: { every: '24 hours' },
    scheduledRefresh: true,
  },
};

module.exports = { PREAGGS };
```

---

## Prompt 5 — n8n Workflow Assembly

**Agent:** n8n Agent — Step 4
**Called by:** `n8n_node` — once per group
**Temperature:** 0.2
**Output:** Complete `n8n_workflow.json`

**Variables:**
- `{group_id}` — workflow name base
- `{domain}` — e.g. `hybrid_compliance`
- `{trigger_cron}` — e.g. `0 9 1 * *`
- `{trigger_type}` — `schedule` | `schedule+webhook`
- `{cubejs_queries}` — JSON array of `{metric_group, query_json}`
- `{alert_conditions}` — output from Prompt 6
- `{slack_channel}` — e.g. `#compliance-alerts`
- `{cubejs_api_url}` — e.g. `http://cubejs:4000/cubejs-api/v1/load`
- `{workflow_skeleton}` — (optional) from n8n Pattern Store

---

### SYSTEM

```
You generate n8n workflow JSON exports importable via n8n's workflow import feature.
Output ONLY valid JSON — no markdown, no explanation, no backticks.

Required nodes in every workflow:
- n8n-nodes-base.scheduleTrigger
- n8n-nodes-base.httpRequest (CubeJS data fetch — one per metric group)
- n8n-nodes-base.code (response normalization)
- n8n-nodes-base.if (one per alert condition)
- n8n-nodes-base.slack (alert notification)
- n8n-nodes-base.httpRequest (dashboard refresh POST)

Structure rules:
1. All node IDs must be unique UUIDs (generate new — never reuse from skeleton)
2. Each node: id, name, type, typeVersion, position, parameters
3. position: Trigger at [0,0], each column +220 on x-axis
4. IF nodes have two output branches: true (alert path) and false (pass path)
5. Workflow top-level name: "{group_id}_artifact_workflow"
6. If skeleton provided, use for structure only — replace all node IDs and parameters
```

### USER

```
Generate a complete n8n workflow for:

Group: {group_id}
Domain: {domain}
Trigger: {trigger_type} — cron: {trigger_cron}
CubeJS API: {cubejs_api_url}
Slack channel: {slack_channel}

CubeJS queries (create one HTTP Request node per entry):
{cubejs_queries}

Alert conditions (create one IF node per entry):
{alert_conditions}

Reference skeleton (replace all IDs and parameters):
{workflow_skeleton}
```

---

### Static Example (abbreviated — shows node structure)

```json
{
  "name": "soc2_audit_hybrid_compliance_artifact_workflow",
  "nodes": [
    {
      "id": "f7a2b1c3-1001",
      "name": "Monthly Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.1,
      "position": [0, 0],
      "parameters": {
        "rule": {"interval": [{"field": "cronExpression", "expression": "0 9 1 * *"}]}
      }
    },
    {
      "id": "f7a2b1c3-1002",
      "name": "Fetch Compliance Posture",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [220, 0],
      "parameters": {
        "method": "POST",
        "url": "http://cubejs:4000/cubejs-api/v1/load",
        "body": {
          "query": {"measures": ["CsodCourseCompletion.completionRate"]}
        }
      }
    },
    {
      "id": "f7a2b1c3-1003",
      "name": "Check CC1 Training Threshold",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [660, 0],
      "parameters": {
        "conditions": {
          "number": [{"value1": "={{ $json.data[0]['CsodCourseCompletion.completionRate'] }}", "operation": "smaller", "value2": 80}]
        }
      }
    },
    {
      "id": "f7a2b1c3-1004",
      "name": "Alert CC1 Breach",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 2.1,
      "position": [880, -100],
      "parameters": {
        "channel": "#compliance-alerts",
        "text": "⚠️ CC1 WARNING: Training completion dropped to {{ $json.data[0]['CsodCourseCompletion.completionRate'] }}%. SOC2 Control Environment at risk."
      }
    }
  ],
  "connections": {
    "Monthly Schedule": {"main": [[{"node": "Fetch Compliance Posture", "type": "main", "index": 0}]]},
    "Check CC1 Training Threshold": {
      "main": [
        [{"node": "Alert CC1 Breach", "type": "main", "index": 0}],
        [{"node": "Dashboard Refresh", "type": "main", "index": 0}]
      ]
    }
  }
}
```

**Enrichment hook:** Replace `{workflow_skeleton}` with top-1 result from n8n Pattern Store queried by `{domain} {trigger_type} {timeframe} {alert_condition_count}`.

---

## Prompt 6 — n8n Alert Conditions

**Agent:** n8n Agent — Step 3 (feeds into Prompt 5)
**Called by:** `n8n_node`
**Temperature:** 0.1
**Output:** JSON array of alert condition objects

**Variables:**
- `{control_anchors}` — from `resolution_payload.control_anchors`
- `{eps_intents}` — chart specs with `semantics.thresholds` from layout_spec
- `{framework}` — e.g. `["soc2"]`

---

### SYSTEM

```
You extract alert conditions from compliance thresholds for n8n IF node generation.
Output ONLY valid JSON array — no explanation, no markdown.

Each condition object schema:
{
  "metric_id": "string",
  "cube_measure": "CubeName.measureName",
  "operator": "< | > | <= | >= | == | !=",
  "threshold": number,
  "severity": "critical | warning | info",
  "control_id": "string",
  "alert_label": "human-readable name",
  "good_direction": "up | down | neutral"
}

Severity mapping:
- semantics.thresholds.critical → severity: "critical"
- semantics.thresholds.warning → severity: "warning"
- good_direction "up" → operator "<" (alert when falls below threshold)
- good_direction "down" → operator ">" (alert when rises above threshold)

Generate one condition per threshold level per metric (not one per metric).
```

### USER

```
Extract alert conditions.

Framework: {framework}
Control anchors: {control_anchors}
EPS IntentSpec semantics (thresholds): {eps_intents}
```

---

### Static Example

Input:
```json
{
  "eps_intents": [
    {"semantics": {"metric_id": "training.completion_rate", "control_id": "CC1",
     "good_direction": "up", "thresholds": {"critical": 60, "warning": 80, "good": 95}}},
    {"semantics": {"metric_id": "vuln.unpatched_critical_count", "control_id": "CC7",
     "good_direction": "down", "thresholds": {"critical": 5, "warning": 1, "good": 0}}}
  ]
}
```

Output:
```json
[
  {
    "metric_id": "training.completion_rate",
    "cube_measure": "CsodCourseCompletion.completionRate",
    "operator": "<", "threshold": 80, "severity": "warning",
    "control_id": "CC1", "alert_label": "CC1 Training Below Warning", "good_direction": "up"
  },
  {
    "metric_id": "training.completion_rate",
    "cube_measure": "CsodCourseCompletion.completionRate",
    "operator": "<", "threshold": 60, "severity": "critical",
    "control_id": "CC1", "alert_label": "CC1 Training Critical — Below 60%", "good_direction": "up"
  },
  {
    "metric_id": "vuln.unpatched_critical_count",
    "cube_measure": "SnykVulnFindings.criticalUnpatchedCount",
    "operator": ">", "threshold": 0, "severity": "warning",
    "control_id": "CC7", "alert_label": "CC7 Critical Vulns Detected", "good_direction": "down"
  },
  {
    "metric_id": "vuln.unpatched_critical_count",
    "cube_measure": "SnykVulnFindings.criticalUnpatchedCount",
    "operator": ">", "threshold": 5, "severity": "critical",
    "control_id": "CC7", "alert_label": "CC7 Critical Vuln Threshold Exceeded", "good_direction": "down"
  }
]
```

---

## Prompt 7 — n8n Slack Alert Message

**Agent:** n8n Agent
**Called by:** `n8n_node` — once per alert condition
**Temperature:** 0.4
**Output:** Slack message string for n8n Slack node `text` parameter

**Variables:**
- `{severity}` — `critical` | `warning`
- `{control_id}` — e.g. `CC7`
- `{control_display_name}` — e.g. `System Operations`
- `{metric_display_name}` — e.g. `Unpatched Critical Vulnerabilities`
- `{threshold}` — numeric threshold
- `{operator}` — `<` | `>`
- `{framework}` — e.g. `SOC2`
- `{n8n_expression_var}` — n8n expression for current value

---

### SYSTEM

```
Write Slack alert messages for compliance dashboard automation injected into n8n workflows.
Output ONLY the message text — no JSON, no markdown, no backticks.
Max 180 characters. Use n8n expression syntax for dynamic values: {{ $json.fieldName }}
Severity emoji: critical → 🔴, warning → ⚠️, info → ℹ️
Include: severity emoji, control ID, metric name, current value expression, threshold.
```

### USER

```
Severity: {severity}
Control: {control_id} — {control_display_name} ({framework})
Metric: {metric_display_name}
Condition: current value {operator} {threshold}
Current value n8n expression: {n8n_expression_var}
```

---

### Static Examples

```
🔴 CC1 CRITICAL [SOC2]: Training completion at {{ $json.value }}% — below 60% threshold. Control Environment posture at risk.
```

```
⚠️ CC7 WARNING: {{ $json.count }} unpatched critical vulns detected. SOC2 System Operations threshold exceeded.
```

```
🔴 CC6 CRITICAL [HIPAA]: {{ $json.openReviews }} access reviews overdue — Logical Access Controls breach threshold.
```

---

## Prompt 8 — Changelog Entry

**Agent:** Version Agent
**Called by:** `version_node` — once per group per run
**Temperature:** 0.3
**Output:** Markdown changelog entry appended to `CHANGELOG.md`

**Variables:**
- `{group_id}`
- `{old_version}` / `{new_version}` — semver strings
- `{bump_type}` — `major` | `minor` | `patch`
- `{bump_trigger}` — e.g. `new_metric_added: training.avg_completion_days`
- `{diff_summary}` — JSON: `{layout_changed, cubejs_changed, n8n_changed}` with details
- `{control_anchors}` — current list after this run
- `{generated_at}` — ISO timestamp

---

### SYSTEM

```
You write concise, factual changelog entries for versioned compliance dashboard artifacts.
Format: Markdown using Keep a Changelog conventions (Added/Changed/Fixed/Removed sections).
Include only sections that have content. Max 15 lines total.
Date format: YYYY-MM-DD. No marketing language. Facts only.
```

### USER

```
Write a changelog entry for:
Group: {group_id}
Version: {old_version} → {new_version} ({bump_type} bump)
Trigger: {bump_trigger}
Date: {generated_at}

What changed:
{diff_summary}

Active control anchors after this version: {control_anchors}
```

---

### Static Examples

**MINOR bump — new metric:**
```markdown
## [1.1.0] — 2025-03-05

### Added
- Measure `avgDaysToComplete` in `CsodCourseCompletion` cube (metric: training.avg_completion_days)
- Pre-aggregation `CsodCourseCompletion_trendMonth` for new time-series chart
- n8n alert: CC1 avg completion days > 30 (warning threshold)

### Changed
- Posture strip cell count: 6 → 7

Control anchors: CC1, CC3, CC5, CC6, CC7, CC8, CC9
```

**MAJOR bump — schema change:**
```markdown
## [2.0.0] — 2025-03-05

### Changed (Breaking)
- `gold.csod_course_completion`: column `dept_code` renamed to `department_id`
- `CsodCourseCompletion` dimension `deptCode` renamed to `departmentId`
- Join between `CsodCourseCompletion` and `WorkdayEmployee` updated
- All pre-aggregations rebuilt

### Fixed
- n8n query updated: `CsodCourseCompletion.department` → `CsodCourseCompletion.departmentId`

Control anchors: CC1, CC3, CC5, CC6, CC7, CC8, CC9
```

**Enrichment hook:** Retrieve prior CHANGELOG.md entry from Artifact Manifest Store for formatting and terminology continuity.

---

## Prompt 9 — Artifact Manifest Summary

**Agent:** Version Agent
**Called by:** `version_node`
**Temperature:** 0.2
**Output:** One-sentence summary for `manifest.json` `summary` field

**Variables:**
- `{use_case_group}`, `{domain}`, `{template_name}`, `{framework}`, `{control_anchors}`, `{gold_tables}`

---

### SYSTEM

```
Write a single-sentence artifact manifest summary for a compliance dashboard group.
Max 30 words. Include: what the dashboard shows, which framework, which systems.
Output ONLY the sentence — no quotes, no JSON.
```

### USER

```
Use case: {use_case_group} | Template: {template_name}
Framework: {framework} | Controls: {control_anchors}
Gold tables: {gold_tables}
```

---

### Static Examples

```
SOC2 compliance posture dashboard covering CC1, CC6, and CC7 controls across Cornerstone LMS and Snyk vulnerability data.
```

```
Monthly HIPAA security management dashboard sourcing from Workday HR and Cornerstone training completion gold tables.
```

```
Daily security operations monitoring for SOC2 CC7 System Operations, powered by Snyk findings and SIEM event tables.
```

---

## Prompt Execution Order and Dependencies

```
CUBEJS AGENT (per gold table, then per group)
  Prompt 1  → {CubeName}.js files
  Prompt 2  → joins patch applied to cube files
  Prompt 3  → schema.yml
  Prompt 4  → pre_aggregations.js

N8N AGENT (parallel with CubeJS)
  Prompt 6  → alert_conditions[]         (input to Prompt 5)
  Prompt 7  → Slack message strings       (input to Prompt 5 node params)
  Prompt 5  → n8n_workflow.json

VERSION AGENT (after both agents complete)
  Prompt 9  → manifest.json summary field
  Prompt 8  → CHANGELOG.md entry
```

## Vector Store Retrieval Summary

| Prompt | Store Queried | Query | Retrieved |
|---|---|---|---|
| 1 | CubeJS Pattern Store | `{domain} {table_type} {metric_groups}` | Top-2 similar cube schemas as few-shot |
| 5 | n8n Pattern Store | `{domain} {trigger_type} {timeframe} {alert_count}` | Top-1 workflow skeleton |
| 8 | Artifact Manifest Store | `{group_id} {domain} {use_case_group}` | Prior changelog for continuity |
| *(upstream)* | Template Vector Store | Goal text | Top-3 layout templates (RBSRV existing) |
| *(upstream)* | EPS Spec Store | Chart intent | Chart type matches (RBSRV existing) |
