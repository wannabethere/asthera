# CubeJS Schema Generation Node — Design Document

## Position in the Pipeline

```
Upstream (dbt gold model generation)
  → gold SQL files + metric_recommendations.json
    → THIS NODE: cubejs_schema_generation_node
      → Cube.js .js schema files (one per domain)
        → Downstream renderer / dashboard builder
```

This is a **single-step, non-interactive node** — no human-in-the-loop, no interrupt. It runs after the gold tables are finalized and produces schema files deterministically from the inputs.

---

## Inputs (State Keys)

| State key | Type | Description |
|---|---|---|
| `gold_sql_files` | `list[GoldSQLFile]` | Each entry: `{ name, sql_text, domain, granularity }` |
| `metric_recommendations` | `list[dict]` | Full metric_recommendations.json payload |
| `connection_id` | `str` | Tenant identifier — injected into `connectionId` dim |
| `output_format` | `str` | `"cubejs"` (gate check; skip node if not cubejs) |
| `cubejs_schema_files` | `list[CubeSchemaFile]` | **Output** — written by this node |
| `cubejs_generation_errors` | `list[str]` | Any per-file errors captured during generation |

```python
# State shape additions (add to LayoutAdvisorState or a sibling state)

class GoldSQLFile(TypedDict):
    name: str           # e.g. "gold_qualys_vulnerabilities_weekly_snapshot"
    sql_text: str       # full dbt SQL content
    domain: str         # "qualys" | "snyk" | "cornerstone" | ...
    granularity: str    # "daily" | "weekly" | "monthly"

class CubeSchemaFile(TypedDict):
    cube_name: str      # e.g. "QualysVulnerabilities"
    filename: str       # e.g. "QualysVulnerabilities.js"
    content: str        # full Cube.js JS schema text
    source_tables: list[str]   # gold table names this cube reads
    measures: list[str]        # measure names declared
    dimensions: list[str]      # dimension names declared
```

---

## Node Signature

```python
# nodes/cubejs_schema_generation_node.py

async def cubejs_schema_generation_node(
    state: LayoutAdvisorState,
    config: RunnableConfig,
) -> dict:
    """
    Single-step node: given gold SQL files + metric recommendations,
    generate Cube.js schema files via LLM with few-shot prompting.

    Returns:
        {
          "cubejs_schema_files": [...],
          "cubejs_generation_errors": [...],
          "phase": Phase.COMPLETE,
        }
    """
    ...
```

---

## Graph Wiring

### Option A — Standalone pipeline (no layout advisor)

```
START → cubejs_schema_generation_node → END
```

### Option B — Appended to existing layout advisor graph

```
... spec_generation → cubejs_schema_generation_node → END
```

Wire in `graph.py`:

```python
# graph.py additions

workflow.add_node("cubejs_schema_generation", cubejs_schema_generation_node)
workflow.add_edge("spec_generation", "cubejs_schema_generation")
workflow.add_edge("cubejs_schema_generation", END)
```

No routing function needed — this node always runs to completion and exits.

---

## Prompt Architecture

Two external files:

```
prompts/
  cubejs_system_prompt.md       ← static system instructions + schema rules
  cubejs_user_template.md       ← Jinja2/f-string template for the user turn
```

### `cubejs_system_prompt.md` — Contents

```markdown
You are a Cube.js schema engineer. Given one or more dbt gold SQL model
definitions and a metric recommendations JSON, produce valid Cube.js cube
definitions as JavaScript files (not TypeScript, not YAML).

## Output Rules
- One cube per logical domain grouping (not one per granularity)
- Always use the WEEKLY snapshot table as the primary sql_table
- Daily and monthly tables are NOT used as cube sources — they are the
  upstream dbt source only
- Every cube MUST have a `connectionId` string dimension as the first
  dimension — this is the tenant isolation key
- Every cube MUST have a composite `pk` primaryKey dimension using CONCAT
- Measures must map 1:1 to metric recommendation KPI entries where possible
- Include `meta` on each measure with: kpi_id, mapped_risks[], widget_hint
- Pre-aggregations: at minimum one weeklyBy* pre-aggregation per cube
- Use `type: countDistinct` (not `count`) for host/asset cardinality measures
- Never use `type: count` on a column that is not `*`
- JSON CVSS fields: use `->>'key'::numeric` extraction, note the limitation
  in a JS comment — do NOT try to aggregate raw jsonb columns
- Output ONLY valid JS — no markdown fences, no explanation, no imports
  beyond the cube() DSL itself

## Grain Strategy (always follow)
Daily → Weekly (PRIMARY grain for cubes) → Monthly (pre-agg only)

## Join Rules
- many_to_one for host→detections (safe)
- many_to_many MUST have a JS comment warning about fan-out inflation
- Never join across domains (qualys↔snyk) — different grain and keys

## Naming Conventions
- Cube names: PascalCase, domain-prefixed — QualysVulnerabilities, SnykIssues
- Measure names: camelCase verbs — criticalVulnCount, avgDaysOpen
- Dimension names: camelCase nouns — hostId, issueLanguage, weekStart
- File names: {CubeName}.js — one file per cube (or two logically related
  cubes in one file when they share a domain and have no joins between them)
```

---

### `cubejs_user_template.md` — Template Variables

```
{gold_sql_block}       ← all gold SQL files concatenated with separators
{metric_block}         ← metric_recommendations JSON (filtered to relevant domain)
{example_block}        ← few-shot examples (see below)
{domain}               ← "qualys" | "snyk" | "cornerstone" etc.
{connection_id_note}   ← reminder string about tenant key
```

Template structure:

```
## Task
Generate Cube.js schema files for the `{domain}` domain.

## Gold SQL Models
{gold_sql_block}

## Metric Recommendations (this domain only)
{metric_block}

## Examples
The following are reference examples of correct output style.
Match this structure exactly — cube names, dimension ordering, measure meta fields.

{example_block}

## Instructions
{instructions_block}

Now generate the Cube.js schema. Output only valid JS.
```

---

## Few-Shot Example Strategy

### Which files to use as examples

Use the uploaded gold SQL + generated cube files as the example corpus:

| Gold SQL (input example) | Cube JS (output example) | Domain tag |
|---|---|---|
| `gold_qualys_vulnerabilities_weekly_snapshot.sql` | `QualysVulnerabilities.js` | qualys |
| `gold_snyk_issues_weekly_snapshot.sql` | `SnykIssues.js` (from QualysApplications_SnykIssues.js) | snyk |
| `gold_qualys_hosts_weekly_snapshot.sql` | `QualysHosts.js` | qualys |
| `gold_qualys_applications_weekly_snapshot.sql` | `QualysApplications.js` | qualys |

### How examples are injected

```python
# example_loader.py

EXAMPLE_PAIRS: list[dict] = [
    {
        "domain": "qualys",
        "sql_name": "gold_qualys_vulnerabilities_weekly_snapshot",
        "sql_path": "prompts/examples/gold_qualys_vulnerabilities_weekly_snapshot.sql",
        "cube_path": "prompts/examples/QualysVulnerabilities.js",
        "note": "Shows: composite PK, criticalVulnCount, openVulnCount, avgDaysOpen, pre-agg with timeDimension",
    },
    {
        "domain": "snyk",
        "sql_name": "gold_snyk_issues_weekly_snapshot",
        "sql_path": "prompts/examples/gold_snyk_issues_weekly_snapshot.sql",
        "cube_path": "prompts/examples/SnykIssues.js",
        "note": "Shows: JSON CVSS extraction pattern, ->>'key'::numeric, standalone cube (no joins)",
    },
    {
        "domain": "qualys",
        "sql_name": "gold_qualys_hosts_weekly_snapshot",
        "sql_path": "prompts/examples/gold_qualys_hosts_weekly_snapshot.sql",
        "cube_path": "prompts/examples/QualysHosts.js",
        "note": "Shows: MAX-type aggregate measures on pre-summed rows, agentCoveragePct derived measure",
    },
]

def load_examples_for_domain(domain: str, max_examples: int = 2) -> str:
    """
    Returns formatted few-shot block for the given domain.
    Always includes one same-domain example + one cross-domain example
    for generalization.
    """
    ...
```

### Example block format (in the prompt)

```
### Example 1 — qualys domain (vulnerabilities)
-- INPUT SQL --
<contents of gold_qualys_vulnerabilities_weekly_snapshot.sql>

-- OUTPUT CUBE.JS --
<contents of QualysVulnerabilities.js>

### Example 2 — snyk domain (issues)
-- INPUT SQL --
<contents of gold_snyk_issues_weekly_snapshot.sql>

-- OUTPUT CUBE.JS --
<contents of SnykIssues.js>
```

---

## Instructions Block (external, per-domain overrides possible)

Stored in `prompts/cubejs_instructions.md`:

```markdown
## Column Inference Rules
- If a column ends in `_count` or `_total` → `type: sum`
- If a column is `avg_*` or `average_*` → `type: avg`
- If a column is a boolean flag (`is_*`) → expose as a string dimension
  with CASE WHEN mapping, not a measure
- If a column is `*_id` or `host_id` → `type: countDistinct` for cardinality
  measures, string dimension for grouping
- If a column is a `TIMESTAMP WITH TIME ZONE` → `type: time` dimension

## Pre-Aggregation Rules
- Name pre-aggregations as `weeklyBy{PrimaryGrouping}` — e.g. `weeklyByHost`,
  `weeklyByOs`, `weeklyByLanguage`
- Always include `refreshKey: { every: '1 day' }`
- `timeDimension` must reference the cube's primary time dimension
- `granularity: 'week'` is the default; add a `monthly` variant only when
  the metric has `metrics_intent: "trend"` at month granularity

## Metric Meta Mapping
For each measure, inspect metric_recommendations for a matching KPI entry.
Set `meta.kpi_id` to the full metric `id` field (e.g.
`vuln_by_asset_criticality:by_host_critical_vuln_count_per_host`).
Set `meta.mapped_risks` to the `mapped_risk_ids` array from that metric.
Set `meta.widget_hint` to the `widget_type` field from that metric.

## Multi-Tenant Rule
Every cube must declare `connectionId` as its first dimension.
The description must say: "Tenant isolation key — always filter by this".
```

---

## LLM Call Configuration

```python
# Recommended settings for schema generation (deterministic output preferred)

LLM_CONFIG = {
    "model": "claude-sonnet-4-20250514",   # or claude-opus-4 for higher fidelity
    "temperature": 0.1,                    # low temp — schema is structural
    "max_tokens": 8192,                    # cubes can be verbose
    "timeout": 120,
}
```

### Call pattern

```python
messages = [
    SystemMessage(content=load_prompt("cubejs_system_prompt.md")),
    HumanMessage(content=render_user_template(
        gold_sql_block=...,
        metric_block=...,
        example_block=load_examples_for_domain(domain),
        instructions_block=load_prompt("cubejs_instructions.md"),
        domain=domain,
    ))
]

response = await llm.ainvoke(messages, config=config)
# response.content → raw JS string
```

---

## Output Parsing & Validation

```python
def parse_cube_js_response(raw: str) -> list[CubeSchemaFile]:
    """
    Split LLM output into individual cube files.
    Detection strategy:
      1. Look for `cube(` declarations — each is a separate cube
      2. Split on `// ───` comment separators (the LLM is prompted to emit these)
      3. Extract cube name from `cube(\`CubeName\``
      4. Build filename as `{CubeName}.js`
    """
    ...

def validate_cube_schema(content: str, cube_name: str) -> list[str]:
    """
    Lightweight validation — returns list of error strings (empty = valid).
    Checks:
      - cube() declaration present
      - sql_table present
      - At least one measure
      - At least one time dimension
      - connectionId dimension present
      - No raw jsonb column in a measure sql (warn on jsonb without ->>'key')
    """
    ...
```

---

## File Layout

```
app/agents/cubejs_generation/
  __init__.py
  node.py                        ← cubejs_schema_generation_node()
  example_loader.py              ← load_examples_for_domain()
  parser.py                      ← parse_cube_js_response(), validate_cube_schema()
  prompts/
    cubejs_system_prompt.md      ← system instructions
    cubejs_user_template.md      ← user turn Jinja2 template
    cubejs_instructions.md       ← column inference + meta mapping rules
    examples/
      gold_qualys_vulnerabilities_weekly_snapshot.sql
      QualysVulnerabilities.js
      gold_snyk_issues_weekly_snapshot.sql
      SnykIssues.js
      gold_qualys_hosts_weekly_snapshot.sql
      QualysHosts.js
      gold_qualys_applications_weekly_snapshot.sql
      QualysApplications.js
```

---

## Batching Strategy

The node processes domains one LLM call at a time (not all tables in one prompt — context gets too large and output quality degrades):

```
qualys domain  → one call → QualysVulnerabilities.js, QualysHosts.js,
                             QualysHostDetections.js, QualysApplications.js
snyk domain    → one call → SnykIssues.js
cornerstone    → one call → (future)
```

Domain grouping is derived from `GoldSQLFile.domain`. The node loops over unique domains and accumulates `cubejs_schema_files`.

---

## Error Handling

| Failure | Strategy |
|---|---|
| LLM returns markdown fences | Strip ` ```js ` / ` ``` ` before parsing |
| LLM hallucinates a join that doesn't exist | Validation detects missing join target — log warning, keep file |
| LLM emits two cubes with same name | Dedup by cube_name, keep last (usually the more complete one) |
| Token overflow (too many tables in one domain) | Chunk: send 3 tables max per call, merge results |
| Validation error on output | Log to `cubejs_generation_errors`, continue — don't fail the node |

---

## Open Questions / Implementation Notes

1. **State location** — Does this node live on `LayoutAdvisorState` or a new sibling state (e.g. `GoldModelState`)? Recommend sibling state if the cube generation pipeline runs independently of the layout advisor.

2. **Example freshness** — The examples in `prompts/examples/` are static. When gold SQL changes significantly (new columns added), examples should be regenerated. Consider a CI step that validates example cubes against system prompt rules.

3. **Monthly cube variants** — Current design generates weekly cubes only. If a downstream chart needs monthly grain natively (not via pre-agg), a second pass generating `{CubeName}Monthly.js` cubes from `*_monthly_snapshot` tables should be added as a separate node or a flag on this one.

4. **Cube.js YAML vs JS** — Cube.js v1 supports YAML schema. If the project migrates to YAML, the system prompt and examples need a parallel YAML variant. The parser would change but the node contract stays the same.