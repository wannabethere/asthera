# Ingest CSOD Learn MDL Projects into Cornerstone Enriched Learning

This guide describes how to ingest Cornerstone OnDemand (CSOD) Learn MDL project folders into the complianceskill data source as enriched learning metadata. The pipeline produces unified project metadata with concepts, categories, and MDL annotations for Lexy/CCE consumption.

---

## Source Folder Structure

The ingestion expects MDL project folders with this structure:

```
CSOD_Learn_mdl_files/
├── Assessment & Q&A/
│   └── Assessment & Q&A/
│       ├── project_metadata.json
│       ├── *.mdl.json
│       └── ddl_*.json (optional)
├── Custom Fields (CF)/
│   └── Custom Fields (CF)/
│       ├── project_metadata.json
│       └── *.mdl.json
├── Learning & Training/
│   ├── Assignments (LAT)/
│   ├── Curriculum & Bundles/
│   ├── ILT (Event-Session)/
│   ├── SCORM/
│   ├── Training Catalog (LO)/
│   ├── Training Finance-E-Commerce/
│   ├── Training Models/
│   └── Transcript & Statuses/
│       ├── project_metadata.json
│       └── *.mdl.json (per subfolder)
├── Localization & Metadata/
│   └── Localization & Metadata/
│       ├── project_metadata.json
│       └── *.mdl.json
└── Users & HR Management/
    ├── Organizational Units (OU)/
    ├── Termination/
    ├── User Core Details/
    ├── User Dynamic Relation/
    └── User-OU Association/
        ├── project_metadata.json
        └── *.mdl.json (per subfolder)
```

Each project folder must contain:
- `project_metadata.json` — project_id, title, description, tables[], knowledge_base, examples
- `*.mdl.json` — MDL schema files referenced in tables[].mdl_file

---

## Projects Ingested

| Category | Subfolders | Project IDs |
|----------|------------|-------------|
| **Assessment & Q&A** | Assessment & Q&A | csod_assessment_qa |
| **Custom Fields (CF)** | Custom Fields (CF) | csod_custom_fields |
| **Learning & Training** | Assignments (LAT), Curriculum & Bundles, ILT (Event-Session), SCORM, Training Catalog (LO), Training Finance-E-Commerce, Training Models, Transcript & Statuses | csod_assignments_lat, csod_curriculum_bundles, csod_ilt_event_session, csod_scorm, csod_training_catalog_lo, csod_training_finance_ecommerce, csod_training_models, csod_transcript_statuses |
| **Localization & Metadata** | Localization & Metadata | csod_localization_metadata |
| **Users & HR Management** | Organizational Units (OU), Termination, User Core Details, User Dynamic Relation, User-OU Association | csod_organizational_units, csod_termination, csod_user_core_details, csod_user_dynamic_relation, csod_user_ou_association |

---

## Ingestion Pipeline (3 Steps)

### Step 1: Ingest MDL Projects

Scans the source directory for `project_metadata.json`, loads each project, and produces a unified metadata file.

```bash
cd complianceskill

python3 app/ingestion/ingest_csod_mdl_projects.py \
  --input-dir /path/to/CSOD_Learn_mdl_files \
  --output data/csod_project_metadata.json
```

**Output:** `data/csod_project_metadata.json` with:
- `projects[]` — folder_path, category, subcategory, tables
- `table_schemas` — per table: `{catalog, schema}` from MDL files (e.g. `csod_dE.dbo`)
- `db_catalog`, `db_schema` — project-level defaults for SQL generation

**Hook:** L3 vector store seeded with raw table docs (stage=raw). Requires `qdrant_client`; non-blocking if unavailable.

---

### Step 2: Enrich Project Metadata

Adds `mdl_tables`, `table_to_category`, `key_columns`, and `concept_ids` using the MDL Enrichment Engine (LLM-driven) or rule-based fallback.

```bash
python3 app/ingestion/enrich_csod_project_metadata.py \
  --input data/csod_project_metadata.json \
  --output data/csod_project_metadata_enriched.json \
  --method llm
```

**Methods:**
- `--method llm` — Uses LLM to infer concepts/categories from MDL content (requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, `LLM_PROVIDER` in .env)
- `--method rule-based` — Minimal heuristics when LLM unavailable

**Output:** `data/csod_project_metadata_enriched.json` with:
- `concept_ids`, `mdl_tables`, `table_to_category`, `key_columns` per project
- `table_schemas`, `db_catalog`, `db_schema` (from MDL or preserved from Step 1)
- `source_id` — default `cornerstone`

**Hooks:**
- L1 vector store — source concepts (project_ids per concept, built from enriched metadata)
- **Option A:** Never writes to `source_concept_registry.json` — that file is owned by `build_source_concept_registry.py` or seed

---

### Step 3: Enrich MDL Files with Concepts

Annotates each `.mdl.json` file with `concept_ids` and `recommendation_area_ids` in model properties, and adds a `concept_id` virtual column.

```bash
python3 app/ingestion/enrich_mdl_with_concepts.py \
  --input-dir /path/to/CSOD_Learn_mdl_files \
  --project-metadata data/csod_project_metadata_enriched.json
```

**Options:**
- `--project-metadata` — Use enriched metadata for concept_ids (recommended)
- Omit `--project-metadata` — Engine infers concepts per project from MDL content
- `--concept-rec-registry` — Path to concept_recommendation_registry.json for recommendation_area_ids
- `--dry-run` — Preview without modifying files

**Output:** MDL files updated in place with `properties.concept_ids`, `properties.recommendation_area_ids`, and `concept_id` column.

**Hook:** L3 vector store updated with concept-annotated table docs (stage=enriched), including `db_catalog`, `db_schema` per table.

---

## LLM Enrich Registries (Optional)

Generate `concept_recommendation_registry.json` and optionally enrich `source_concept_map` using LLM:

```bash
# Generate recommendation areas for all concepts
python3 app/ingestion/enrich_registries_with_llm.py \
  --enriched data/csod_project_metadata_enriched.json

# Limit to specific concepts
python3 app/ingestion/enrich_registries_with_llm.py \
  --enriched data/csod_project_metadata_enriched.json \
  --concepts compliance_training learning_effectiveness training_roi

# Also update source_concept_map with mdl_table_refs, project_ids
python3 app/ingestion/enrich_registries_with_llm.py \
  --enriched data/csod_project_metadata_enriched.json \
  --enrich-source-map

# Source map only (no LLM, no API key)
python3 app/ingestion/enrich_registries_with_llm.py \
  --enriched data/csod_project_metadata_enriched.json \
  --source-map-only

# Dry run (no writes)
python3 app/ingestion/enrich_registries_with_llm.py \
  --enriched data/csod_project_metadata_enriched.json \
  --dry-run

# Preview (print formatted summary of generated data)
python3 app/ingestion/enrich_registries_with_llm.py \
  --enriched data/csod_project_metadata_enriched.json \
  --preview
```

Requires `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Output: `registries/concept_recommendation_registry.json`.

---

## Preview (Dry Run)

Preview what would be ingested into the vector store for specific categories, without writing:

```bash
# Preview with default categories (Assessment & Q&A, Custom Fields (CF), Learning & Training, Localization & Metadata)
python3 app/ingestion/preview_csod_ingestion.py \
  --input-dir /path/to/CSOD_Learn_mdl_files

# Preview using existing metadata files
python3 app/ingestion/preview_csod_ingestion.py \
  --metadata data/csod_project_metadata.json \
  --enriched data/csod_project_metadata_enriched.json \
  --categories "Assessment & Q&A" "Custom Fields (CF)" "Learning & Training" "Localization & Metadata"

# Create output folder with registries/, data/, mdl_schemas/
python3 app/ingestion/preview_csod_ingestion.py \
  --metadata data/csod_project_metadata.json \
  --enriched data/csod_project_metadata_enriched.json \
  --output preview_out

# Include enriched source_concept_map (mdl_table_refs, project_ids) in output registries
python3 app/ingestion/preview_csod_ingestion.py \
  --metadata data/csod_project_metadata.json \
  --enriched data/csod_project_metadata_enriched.json \
  --output preview_out \
  --enrich-registries

# Include enriched MDL files in output (run Step 3 first to enrich source)
python3 app/ingestion/preview_csod_ingestion.py \
  --metadata data/csod_project_metadata.json \
  --enriched data/csod_project_metadata_enriched.json \
  --output preview_out \
  --copy-mdl
```

Output: console preview of L1/L2/L3 doc counts. With `--output <dir>`: creates folder with `registries/`, `data/`, `mdl_schemas/<category>/<project_id>/`. With `--copy-mdl`: copies actual `.mdl.json` files (run Step 3 first to enrich them).

---

## Preview Enriched MDL Data

After running Step 3 (`enrich_mdl_with_concepts.py`), MDL files have `properties.concept_ids`, `properties.recommendation_area_ids`, and a `concept_id` column. To preview:

**Option 1 — Preview script with `--copy-mdl`** (copies MDL files into output folder):
```bash
python3 app/ingestion/preview_csod_ingestion.py \
  --metadata data/csod_project_metadata.json \
  --enriched data/csod_project_metadata_enriched.json \
  --output preview_out \
  --copy-mdl
# Inspect: preview_out/mdl_schemas/Assessment & Q&A/csod_assessment_qa/*.mdl.json
```

**Option 2 — Inspect a single MDL file** (after Step 3):
```bash
jq '.models[0].properties | {concept_ids, recommendation_area_ids}' \
  "/path/to/CSOD_Learn_mdl_files/Assessment & Q&A/Assessment & Q&A/assessment_test_core.mdl.json"
```

---

## Full Pipeline (One-Liner)

```bash
cd complianceskill

# 1. Ingest
python3 app/ingestion/ingest_csod_mdl_projects.py \
  --input-dir /path/to/CSOD_Learn_mdl_files \
  --output data/csod_project_metadata.json

# 2. Enrich metadata (LLM or rule-based)
python3 app/ingestion/enrich_csod_project_metadata.py \
  --input data/csod_project_metadata.json \
  --output data/csod_project_metadata_enriched.json \
  --method llm

# 3. Annotate MDL files
python3 app/ingestion/enrich_mdl_with_concepts.py \
  --input-dir /path/to/CSOD_Learn_mdl_files \
  --project-metadata data/csod_project_metadata_enriched.json
```

---

## Ingest to Vector Store (Single Script)

Push all registry data into Qdrant collections (L1, L2, L3) for use during read/lookup:

```bash
# Push from existing files (default: data/, registries/)
python3 app/ingestion/ingest_registry_vector_store.py

# Push with custom paths (e.g. preview output)
python3 app/ingestion/ingest_registry_vector_store.py \
  --enriched preview_out/data/csod_project_metadata_enriched.json \
  --source-registry preview_out/registries/source_concept_registry.json \
  --concept-rec-registry preview_out/registries/concept_recommendation_registry.json

# Full pipeline: ingest → enrich → enrich MDL → push
python3 app/ingestion/ingest_registry_vector_store.py \
  --input-dir /path/to/CSOD_Learn_mdl_files \
  --run-full-pipeline

# With LLM registry enrichment (concept_recommendation_registry)
python3 app/ingestion/ingest_registry_vector_store.py \
  --input-dir /path/to/CSOD_Learn_mdl_files \
  --run-full-pipeline \
  --enrich-registries

# Dry run (no Qdrant writes)
python3 app/ingestion/ingest_registry_vector_store.py --dry-run
```

**Collections:** `csod_l1_source_concepts`, `csod_l2_recommendation_areas`, `csod_l3_mdl_tables`, `csod_metrics_registry` (with --all)

**Requires:** Qdrant (default `http://localhost:6333`), `OPENAI_API_KEY` for embeddings.

---

## Prerequisites

- **Python 3.10+**
- **complianceskill** project with dependencies installed
- **LLM (optional):** Set in `.env`:
  - `LLM_PROVIDER=anthropic` or `openai`
  - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
  - `LLM_MODEL` (e.g. `claude-sonnet-4-20250514` or `gpt-4o`)

Without LLM, Step 2 uses rule-based fallback; Step 3 requires `--project-metadata` from Step 2.

---

## Output Artifacts

| File | Description |
|------|-------------|
| `data/csod_project_metadata.json` | Unified project list with folder_path, tables, table_schemas, db_catalog, db_schema |
| `data/csod_project_metadata_enriched.json` | Enriched with concept_ids, mdl_tables, table_to_category, key_columns, source_id |
| `registries/source_concept_registry.json` | key_concepts seed (source_concept_map owned by build_source_concept_registry.py) |
| `*.mdl.json` (in source) | Annotated with concept_ids, recommendation_area_ids, concept_id column |

---

## Validation Checklist

After running the full pipeline, verify:

1. **Step 1 — Ingest**
   - `data/csod_project_metadata.json` exists and has `projects[]`
   - Each project has `table_schemas` with `{table_name: {catalog, schema}}` (e.g. `csod_dE`, `dbo`)
   - Each project has `db_catalog` and `db_schema`

2. **Step 2 — Enrich**
   - `data/csod_project_metadata_enriched.json` has `concept_ids` per project
   - Each project has `source_id: "cornerstone"`
   - L1 vector store has `project_ids` (list) per concept — concept spans multiple projects

3. **Step 3 — Enrich MDL**
   - Sample `.mdl.json` has `properties.concept_ids` and `properties.recommendation_area_ids` on models
   - Each model has a `concept_id` column (virtual)

4. **Registry Vector Store** (optional — requires Qdrant + OpenAI)
   - L1: `csod_l1_source_concepts` — concept docs with `project_ids[]` (1:many)
   - L2: `csod_l2_recommendation_areas` — from concept_recommendation_registry.json
   - L3: `csod_l3_mdl_tables` — table docs with db_catalog, db_schema, qualified_table_name, key_columns

**Quick validation commands:**
```bash
# Check table_schemas in Step 1 output
jq '.projects[0] | {table_schemas, db_catalog, db_schema}' data/csod_project_metadata.json

# Check concept_ids and source_id in Step 2 output
jq '.projects[0] | {concept_ids, source_id}' data/csod_project_metadata_enriched.json

# Check MDL annotations in Step 3
jq '.models[0].properties | {concept_ids, recommendation_area_ids}' /path/to/CSOD_Learn_mdl_files/.../transcript_core.mdl.json
```

---

## Reference

- **CSOD Learn MDL Reference:** `data/csod_learn_mdl_reference.md`
- **Lexy Metadata Design:** See `lexy_metadata_registry_design.md` for concept taxonomy and registry architecture
