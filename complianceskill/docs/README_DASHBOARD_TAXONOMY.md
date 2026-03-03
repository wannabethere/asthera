# Dashboard Taxonomy Generation and Enrichment

This directory contains scripts for generating and enriching dashboard domain taxonomies for dashboard generation decision trees.

## Workflow

### Step 1: Generate Taxonomy from Dashboard Data

Use `generate_dashboard_taxonomy.py` to create an initial taxonomy by analyzing actual dashboard templates and metrics.

```bash
python -m app.ingestion.generate_dashboard_taxonomy \
    --templates-dir app/dashboard_agent/registry_config \
    --output app/dashboard_agent/registry_config/dashboard_domain_taxonomy.json \
    --max-samples 20
```

**What it does:**
- Extracts dashboard samples from:
  - `ld_templates_registry.json` (L&D templates)
  - `lms_dashboard_metrics.json` (LMS dashboards with metrics)
  - `templates_registry.json` (base security/compliance templates)
- Uses LLM to analyze dashboards and generate taxonomy domains
- Creates taxonomy with goals, focus areas, use cases, audience levels, complexity, and theme preferences

**Output:** `dashboard_domain_taxonomy.json`

### Step 2: Enrich the Generated Taxonomy

Use `enrich_dashboard_taxonomy.py` to improve the taxonomy with additional analysis.

```bash
python -m app.ingestion.enrich_dashboard_taxonomy \
    --input app/dashboard_agent/registry_config/dashboard_domain_taxonomy.json \
    --output app/dashboard_agent/registry_config/dashboard_domain_taxonomy_enriched.json \
    --templates-dir app/dashboard_agent/registry_config \
    --method llm
```

**What it does:**
- Loads the generated taxonomy
- Analyzes all dashboard templates to identify improvements
- Enhances goals, focus areas, use cases, and audience levels
- Identifies missing domains
- Suggests better domain names/descriptions

**Output:** `dashboard_domain_taxonomy_enriched.json`

## Files

- `app/ingestion/generate_dashboard_taxonomy.py`: Generates taxonomy from dashboard data
- `app/ingestion/enrich_dashboard_taxonomy.py`: Enriches existing taxonomy
- `app/agents/decision_trees/prompts/16_generate_dashboard_taxonomy.md`: Prompt for taxonomy generation
- `app/agents/decision_trees/prompts/15_enrich_dashboard_taxonomy.md`: Prompt for taxonomy enrichment
- `dashboard_domain_taxonomy.json`: Generated taxonomy (created by step 1)
- `dashboard_domain_taxonomy_enriched.json`: Enriched taxonomy (created by step 2)

## Taxonomy Structure

Each domain in the taxonomy includes:

```json
{
  "domain_id": {
    "domain": "domain_id",
    "display_name": "Display Name",
    "goals": ["goal1", "goal2", ...],
    "focus_areas": ["focus1", "focus2", ...],
    "use_cases": ["use_case1", "use_case2", ...],
    "audience_levels": ["audience1", "audience2", ...],
    "complexity": "low|medium|high",
    "theme_preference": "light|dark"
  }
}
```

## Usage in Dashboard Generation

The enriched taxonomy is used by:
- Dashboard template selection logic
- Decision tree resolution for dashboard generation
- Matching user requirements to appropriate dashboard templates

Similar to how `control_domain_taxonomy.json` maps controls to compliance frameworks, this taxonomy maps dashboards to their purposes and contexts.
