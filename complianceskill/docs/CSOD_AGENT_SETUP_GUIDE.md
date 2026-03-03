# CSOD Agent Setup Guide

This guide outlines the key steps needed to set up and run the CSOD Metrics, Tables, and KPIs Recommender workflow.

## Overview

The CSOD workflow requires several data sources and registries to be properly ingested and configured:

1. **Metrics Registry** - `lms_dashboard_metrics.json` → ingested into `leen_metrics_registry` collection
2. **Dashboard Taxonomy** - `dashboard_domain_taxonomy.json` (or enriched version) - static JSON file
3. **Dashboard Templates** - `ld_templates_registry.json` and `dashboard_registry.json` - static JSON files
4. **MDL Schemas** - Database schemas ingested into `leen_db_schema` and `leen_table_description` collections
5. **Project Metadata** - Gold standard tables ingested into `leen_project_meta` collection

---

## Step 1: Metrics Ingestion

### 1.1 Prepare Metrics Registry File

**Location:** `app/dashboard_agent/registry_config/lms_dashboard_metrics.json`

**Format:** JSON file with dashboards containing metrics:

```json
{
  "metadata": {
    "extraction_date": "2026-02-26",
    "source_platform": "Cornerstone OnDemand / CSOD-style LMS",
    "total_dashboards": 6,
    "total_metrics_extracted": 108
  },
  "dashboards": [
    {
      "dashboard_id": "dash_learning_measurement",
      "dashboard_name": "Enterprise Learning Measurement Dashboard",
      "dashboard_category": "ld_operations",
      "description": "...",
      "metrics": [
        {
          "id": "lm_learner_total",
          "name": "Total Learners",
          "type": "count",
          "unit": "learners",
          "category": "learning",
          "source_capabilities": ["cornerstone.lms"],
          "source_schemas": ["cornerstone_training_assignments"],
          "kpis": ["Training Completion Rate"],
          "trends": ["learner_growth"],
          "natural_language_question": "What is the total number of learners?",
          "data_filters": [],
          "data_groups": ["course_id", "learner_id"]
        }
      ]
    }
  ]
}
```

**Required Fields for Each Metric:**
- `id` - Unique metric identifier (e.g., `"lm_learner_total"`)
- `name` - Metric name (e.g., `"Total Learners"`)
- `type` - Metric type (e.g., `"count"`, `"currency"`, `"percentage"`)
- `unit` - Unit of measurement (e.g., `"learners"`, `"USD"`, `"percentage"`)
- `category` - Metric category (e.g., `"learning"`, `"training"`, `"compliance"`) - **Important for filtering**
- `sources` - List of data sources (e.g., `["Cornerstone LMS", "HRIS"]`) - **Will be mapped to `source_capabilities`**
- `section` - Dashboard section this metric belongs to (optional)

**Recommended Fields:**
- `description` - Metric description
- `source_capabilities` - List of data source capabilities (e.g., `["cornerstone.lms"]`) - **Used for filtering by data source**
- `source_schemas` - List of table names this metric uses (e.g., `["cornerstone_training_assignments"]`) - **Used for schema mapping**
- `kpis` - List of KPIs this metric supports (optional)
- `trends` - List of trend types (optional)
- `natural_language_question` - Natural language question for this metric (recommended)
- `chart_type` - Recommended chart type (e.g., `"kpi_card"`, `"trend_line"`, `"bar_chart"`)

**Note:** If `source_capabilities` is not present, the ingestion script may try to derive it from `sources` field, but it's better to include `source_capabilities` explicitly.

### 1.2 Ingest Metrics into Vector Store

**Command for CSOD workflow:**
```bash
python -m app.ingestion.ingest_metrics_registry \
    --metrics-file app/dashboard_agent/registry_config/lms_dashboard_metrics.json \
    --collection-name csod_metrics_registry \
    --reinit-qdrant
```

**Note:** CSOD workflow uses `csod_metrics_registry` collection, while DT/LEEN workflow uses `leen_metrics_registry`. The collection factory automatically selects the correct collection based on workflow type.

**What it does:**
- **Automatically extracts** individual metrics from the `dashboards` structure in `lms_dashboard_metrics.json`
- The ingestion script handles the nested format: `{"dashboards": [{"metrics": [...]}]}`
- Creates embeddings for each metric (using name, description, category, KPIs, trends, etc.)
- Indexes metrics into Qdrant collection `leen_metrics_registry`
- Each metric becomes searchable via semantic search using `MDLRetrievalService.search_metrics_registry()`

**Alternative: Ingest from directory**
```bash
python -m app.ingestion.ingest_metrics_registry \
    --metrics-dir app/dashboard_agent/registry_config \
    --collection-name leen_metrics_registry
```

**Important Notes:**
- The ingestion script automatically handles the `lms_dashboard_metrics.json` format where metrics are nested inside dashboards
- Metrics are extracted from each dashboard's `metrics` array
- Each metric gets a unique ID based on `schema_name:metric_id` to avoid collisions
- The CSOD workflow uses `MDLRetrievalService.search_metrics_registry()` which queries the `leen_metrics_registry` collection
- Metrics are filtered by `source_capabilities` to match your `selected_data_sources` (e.g., `["cornerstone.lms"]`)

---

## Step 2: Dashboard Taxonomy Setup

### 2.1 Dashboard Domain Taxonomy File

**Location:** `app/dashboard_agent/registry_config/dashboard_domain_taxonomy.json` (or `dashboard_domain_taxonomy_enriched.json`)

**Format:** JSON file with domain definitions:

```json
{
  "meta": {
    "version": "1.0.0",
    "description": "Dashboard domain taxonomy for dashboard generation decision trees"
  },
  "domains": {
    "ld_training": {
      "domain": "ld_training",
      "display_name": "Learning & Training",
      "goals": [
        "training_completion",
        "assignment_tracking",
        "learner_profile_analysis",
        "compliance_training_monitoring"
      ],
      "focus_areas": [
        "training_compliance",
        "learner_engagement",
        "curriculum_performance"
      ],
      "use_cases": [
        "training_plan_rollout_tracking",
        "manager_team_training_oversight"
      ],
      "audience_levels": [
        "learning_admin",
        "training_coordinator",
        "team_manager"
      ],
      "complexity": "medium",
      "theme_preference": "light"
    },
    "ld_operations": {
      "domain": "ld_operations",
      "display_name": "L&D Operations & Measurement",
      "goals": [
        "enterprise_learning_measurement",
        "training_cost_management",
        "vendor_and_ilt_performance_tracking"
      ],
      "focus_areas": [
        "training_cost_analytics",
        "vendor_spend_tracking"
      ],
      "use_cases": [
        "executive_learning_roi_dashboard",
        "training_budget_oversight"
      ],
      "audience_levels": [
        "l&d_director",
        "learning_operations_manager"
      ],
      "complexity": "high",
      "theme_preference": "light"
    },
    "ld_engagement": {
      "domain": "ld_engagement",
      "display_name": "LMS Platform Adoption",
      "goals": [
        "lms_adoption_tracking",
        "user_engagement_measurement"
      ],
      "focus_areas": [
        "login_trends",
        "active_user_monitoring"
      ],
      "use_cases": [
        "lms_usage_analytics",
        "platform_adoption_dashboard"
      ],
      "audience_levels": [
        "learning_admin",
        "l&d_director"
      ],
      "complexity": "medium",
      "theme_preference": "light"
    },
    "hr_workforce": {
      "domain": "hr_workforce",
      "display_name": "HR & Workforce Analytics",
      "goals": [
        "workforce_headcount_tracking",
        "employee_lifecycle_monitoring"
      ],
      "focus_areas": [
        "headcount_analytics",
        "lifecycle_tracking"
      ],
      "use_cases": [
        "workforce_planning_dashboard",
        "employee_retention_analytics"
      ],
      "audience_levels": [
        "hr_operations_manager",
        "hr_director"
      ],
      "complexity": "medium",
      "theme_preference": "light"
    },
    "compliance_training": {
      "domain": "compliance_training",
      "display_name": "Compliance Training & Certification",
      "goals": [
        "compliance_posture_unification",
        "control_evidence_mapping"
      ],
      "focus_areas": [
        "certification_tracking",
        "policy_acknowledgment"
      ],
      "use_cases": [
        "compliance_training_audit",
        "certification_expiration_monitoring"
      ],
      "audience_levels": [
        "compliance_officer",
        "learning_admin"
      ],
      "complexity": "medium",
      "theme_preference": "light"
    }
  }
}
```

**Required Fields for Each Domain:**
- `domain` - Domain identifier (e.g., `ld_training`, `ld_operations`)
- `display_name` - Human-readable name
- `goals` - List of business goals (used for KPI mapping)
- `focus_areas` - List of focus areas (used for metric filtering)
- `use_cases` - List of use cases (used for dashboard template selection)
- `audience_levels` - List of personas/audience levels (used for dashboard generation)
- `complexity` - Complexity level (`simple`, `medium`, `high`)
- `theme_preference` - UI theme preference (`light`, `dark`)

**How it's used:**
- Intent classifier maps user queries to focus areas
- Planner uses focus areas to filter metrics and select templates
- Metrics recommender maps KPIs to goals
- Dashboard generator matches personas to audience levels

### 2.2 Generate/Enrich Taxonomy (Optional)

If you need to generate or enrich the taxonomy:

**Generate from dashboard data:**
```bash
python -m app.ingestion.generate_dashboard_taxonomy \
    --templates-dir app/dashboard_agent/registry_config \
    --output app/dashboard_agent/registry_config/dashboard_domain_taxonomy.json \
    --max-samples 20
```

**Enrich existing taxonomy:**
```bash
python -m app.ingestion.enrich_dashboard_taxonomy \
    --input app/dashboard_agent/registry_config/dashboard_domain_taxonomy.json \
    --output app/dashboard_agent/registry_config/dashboard_domain_taxonomy_enriched.json \
    --templates-dir app/dashboard_agent/registry_config \
    --method llm
```

---

## Step 3: Dashboard Templates Setup

### 3.1 Learning & Development Templates

**Location:** `app/dashboard_agent/registry_config/ld_templates_registry.json`

**Format:** JSON file with dashboard templates:

```json
{
  "templates": [
    {
      "template_id": "ld_training_completion",
      "name": "Training Completion Dashboard",
      "domain": "ld_training",
      "category": "training_completion",
      "audience_levels": ["learning_admin", "team_manager"],
      "complexity": "medium",
      "best_for": ["training_plan_rollout_tracking"],
      "layout_grid": "3-column",
      "panels": [
        {
          "panel_id": "completion_metrics",
          "panel_type": "kpi_grid",
          "metrics": ["completion_rate", "on_time_completion"]
        }
      ]
    }
  ]
}
```

### 3.2 Dashboard Registry

**Location:** `app/dashboard_agent/registry_config/dashboard_registry.json`

**Format:** Similar to `ld_templates_registry.json` but for general dashboard patterns.

**How it's used:**
- Dashboard generator selects templates based on persona, domain, and use case
- Templates provide layout structure and component patterns

---

## Step 4: MDL Schema Ingestion

### 4.1 Database Schemas

The CSOD workflow needs database schemas to be ingested into:
- `leen_db_schema` - Table DDL and structure
- `leen_table_description` - Table descriptions and relationships

**Ingestion:** Use MDL schema ingestion scripts (typically done separately for your database).

**Required for:**
- Mapping metrics to actual tables
- Calculation planning (field_instructions, metric_instructions)
- Dashboard generation (data_table_definition)

### 4.2 Gold Standard Tables

**Collection:** `leen_project_meta` (via `GoldStandardTable` lookup)

**Required for:**
- Medallion planner to identify existing gold tables
- Metrics recommender to prefer gold tables over silver/bronze

**Lookup:** Uses `active_project_id` from state to find project-specific gold tables.

---

## Step 5: SQL Functions Reference (for Data Science Insights)

### 5.1 SQL Functions Library

**Location:** 
- `app/data/sql_functions/sql_functions.json`
- `app/data/sql_functions/sql_function_appendix.json`

**Format:** JSON files with SQL function definitions:

```json
{
  "function_reference": {
    "calculate_statistical_trend": {
      "function": "calculate_statistical_trend",
      "description": "Calculates statistical trend using linear regression...",
      "parameters": {
        "p_data": "JSONB array with time and metric columns",
        "p_confidence_level": "float (default 95.0)"
      },
      "returns": "JSONB with trend_direction, slope, r_squared, etc."
    }
  }
}
```

**Required for:**
- Data science insights enricher to generate insights using SQL functions
- Calculation planner to incorporate SQL functions into calculation instructions

---

## Step 6: Quick Start Commands

### Complete Setup (All Steps)

```bash
# 1. Ingest metrics from lms_dashboard_metrics.json
python -m app.ingestion.ingest_metrics_registry \
    --metrics-file app/dashboard_agent/registry_config/lms_dashboard_metrics.json \
    --collection-name leen_metrics_registry \
    --reinit-qdrant

# 2. Verify taxonomy exists (should already be in place)
ls app/dashboard_agent/registry_config/dashboard_domain_taxonomy*.json

# 3. Verify templates exist (should already be in place)
ls app/dashboard_agent/registry_config/ld_templates_registry.json
ls app/dashboard_agent/registry_config/dashboard_registry.json

# 4. Run CSOD workflow test
python -m complianceskill.tests.test_csod_workflow --test use_case_1
```

### Verify Metrics Were Ingested

```python
from app.retrieval.mdl_service import MDLRetrievalService
import asyncio

async def test_metrics_search():
    service = MDLRetrievalService()
    results = await service.search_metrics_registry(
        query="training completion metrics",
        limit=5
    )
    print(f"Found {len(results)} metrics")
    for r in results:
        print(f"  - {r.metric_name} (score: {r.score:.3f})")

asyncio.run(test_metrics_search())
```

---

## Step 7: Verification Checklist

### Metrics Registry
- [ ] `lms_dashboard_metrics.json` exists with metrics
- [ ] Metrics ingested into `leen_metrics_registry` collection
- [ ] Each metric has: `id`, `name`, `category`, `source_capabilities`, `source_schemas`
- [ ] Metrics are searchable via `MDLRetrievalService.search_metrics_registry()`

### Dashboard Taxonomy
- [ ] `dashboard_domain_taxonomy.json` (or enriched version) exists
- [ ] Contains domains: `ld_training`, `ld_operations`, `ld_engagement`, `hr_workforce`, `compliance_training`
- [ ] Each domain has: `goals`, `focus_areas`, `use_cases`, `audience_levels`

### Dashboard Templates
- [ ] `ld_templates_registry.json` exists with L&D templates
- [ ] `dashboard_registry.json` exists with general templates
- [ ] Templates have: `domain`, `audience_levels`, `best_for`, `layout_grid`

### MDL Schemas
- [ ] Database schemas ingested into `leen_db_schema`
- [ ] Table descriptions ingested into `leen_table_description`
- [ ] Gold standard tables available in `leen_project_meta` (if using gold models)

### SQL Functions
- [ ] `sql_functions.json` exists with function definitions
- [ ] `sql_function_appendix.json` exists with function summaries

---

## Step 8: Testing the Setup

### 8.1 Run CSOD Workflow Test

```bash
# Run all tests
python -m complianceskill.tests.test_csod_workflow

# Run specific test
python -m complianceskill.tests.test_csod_workflow --test use_case_1
```

### 8.2 Verify Collections

Check that collections exist and have data:

```python
from app.storage.collections import MDLCollections
from app.core.dependencies import get_doc_store_provider

doc_stores = get_doc_store_provider()
metrics_store = doc_stores.stores.get(MDLCollections.METRICS_REGISTRY)

# Check if collection has data
# (implementation depends on your document store provider)
```

---

## Common Issues and Solutions

### Issue: No metrics found in search

**Solution:**
1. Verify `lms_dashboard_metrics.json` has metrics with proper structure
2. Re-run metrics ingestion: `python -m app.ingestion.ingest_metrics_registry --reinit-qdrant`
3. Check that `source_capabilities` in metrics match your `selected_data_sources`

### Issue: Focus areas not mapping to domains

**Solution:**
1. Verify `dashboard_domain_taxonomy.json` has the focus areas you're using
2. Check that intent classifier is outputting focus areas that exist in taxonomy
3. Ensure taxonomy file is in the correct location and loaded properly

### Issue: No dashboard templates found

**Solution:**
1. Verify `ld_templates_registry.json` and `dashboard_registry.json` exist
2. Check that templates have matching `domain` and `audience_levels`
3. Ensure templates are being loaded by the dashboard generator

### Issue: Calculation planner not finding schemas

**Solution:**
1. Verify MDL schemas are ingested into `leen_db_schema` and `leen_table_description`
2. Check that `csod_resolved_schemas` in state contains schemas
3. Ensure schema table names match `source_schemas` in metrics

---

## File Locations Summary

```
genieml/complianceskill/
├── app/
│   ├── dashboard_agent/
│   │   └── registry_config/
│   │       ├── lms_dashboard_metrics.json          # Metrics registry (source)
│   │       ├── dashboard_domain_taxonomy.json      # Taxonomy (static)
│   │       ├── dashboard_domain_taxonomy_enriched.json  # Enriched taxonomy (static)
│   │       ├── dashboard_registry.json             # Dashboard templates (static)
│   │       └── ld_templates_registry.json         # L&D templates (static)
│   ├── data/
│   │   └── sql_functions/
│   │       ├── sql_functions.json                  # SQL function definitions
│   │       └── sql_function_appendix.json         # SQL function summaries
│   └── ingestion/
│       ├── ingest_metrics_registry.py             # Metrics ingestion script
│       ├── generate_dashboard_taxonomy.py         # Taxonomy generation script
│       └── enrich_dashboard_taxonomy.py           # Taxonomy enrichment script
└── tests/
    └── test_csod_workflow.py                      # CSOD workflow tests
```

---

## Next Steps

1. **Ingest metrics** from `lms_dashboard_metrics.json` into `leen_metrics_registry`
2. **Verify taxonomy** file exists and has all required domains
3. **Ensure templates** are in place for dashboard generation
4. **Ingest MDL schemas** for your Cornerstone/Workday tables
5. **Run tests** to verify everything works

For detailed ingestion instructions, see:
- `app/ingestion/ingest_metrics_registry.py` - Metrics ingestion
- `docs/README_DASHBOARD_TAXONOMY.md` - Taxonomy generation/enrichment
- `docs/QDRANT_COLLECTIONS_DT_WORKFLOW.md` - Collection setup (similar for CSOD)
