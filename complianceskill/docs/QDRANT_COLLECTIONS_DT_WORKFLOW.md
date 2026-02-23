# Qdrant Collections Required for Detection & Triage Workflow

This document lists all Qdrant collections that must be populated for the Detection & Triage (DT) workflow to function correctly.

## Summary

**Total Collections Required:** 11 collections

- **Framework KB:** 5 collections (via `RetrievalService`)
- **MDL Collections:** 4 collections (via `MDLRetrievalService`)
- **Product Capabilities:** 1 collection (used by `dt_retrieve_mdl_schemas`)
- **XSOAR (Optional):** 1 collection (for dashboard examples)

---

## 1. Framework Knowledge Base Collections

**Accessed via:** `RetrievalService` (in `app/retrieval/service.py`)

**Used by DT Nodes:**
- `dt_framework_retrieval_node` - Retrieves controls, risks, and scenarios
- `dt_detection_engineer_node` - Uses controls and scenarios for SIEM rule generation
- `dt_triage_engineer_node` - Uses controls for metric recommendations

### Collections:

1. **`framework_controls`**
   - **Purpose:** Compliance controls (HIPAA, SOC2, CIS, NIST, ISO, PCI-DSS)
   - **Used for:** Control retrieval, SIEM rule mapping, metric recommendation traceability
   - **Key Fields:** `control_type` (detective/preventive/corrective), `code`, `framework_id`, `domain`
   - **Critical:** Must have `control_type="detective"` controls for detection-focused workflows

2. **`framework_requirements`**
   - **Purpose:** Framework requirements (e.g., HIPAA §164.312(b))
   - **Used for:** Requirement-to-control mapping
   - **Key Fields:** `requirement_code`, `framework_id`, `control_ids`

3. **`framework_risks`**
   - **Purpose:** Risk scenarios associated with controls
   - **Used for:** Risk assessment, triage prioritization
   - **Key Fields:** `risk_code`, `likelihood`, `impact`, `mitigated_by` (control references)

4. **`framework_scenarios`**
   - **Purpose:** Attack scenarios and threat patterns
   - **Used for:** SIEM rule generation, detection engineering
   - **Key Fields:** `severity`, `attack_techniques` (ATT&CK IDs), `scenario_type`

5. **`framework_test_cases`**
   - **Purpose:** Test cases for control validation
   - **Used for:** Validation and testing (optional for DT workflow)

---

## 2. MDL Collections

**Accessed via:** `MDLRetrievalService` (in `app/retrieval/mdl_service.py`)

**Used by DT Nodes:**
- `dt_metrics_retrieval_node` - Filters metrics from `leen_metrics_registry`
- `dt_mdl_schema_retrieval_node` - Retrieves schemas via product capabilities + project_id
- `dt_triage_engineer_node` - Uses schemas for medallion plan generation

### Collections:

6. **`leen_db_schema`**
   - **Purpose:** Database schema DDL chunks (TABLE + TABLE_COLUMNS)
   - **Used for:** Direct schema name lookup, table structure retrieval
   - **Key Fields:** `table_name`, `schema_ddl`, `columns`, `project_id` (for filtering)
   - **Critical:** Must have schemas matching `source_schemas` from `leen_metrics_registry`
   - **Project ID Format:** `"{product_id}_{capability_id}"` (e.g., `"qualys_assets"`)

7. **`leen_table_description`**
   - **Purpose:** Table descriptions with columns and relationships
   - **Used for:** Table context and relationship mapping
   - **Key Fields:** `table_name`, `description`, `relationships`, `project_id` (for filtering)
   - **Project ID Format:** `"{product_id}_{capability_id}"` (e.g., `"qualys_assets"`)

8. **`leen_project_meta`**
   - **Purpose:** Project metadata and GoldStandardTables
   - **Used for:** GoldStandardTable lookup for medallion architecture
   - **Key Fields:** `project_id`, `table_name`, `is_gold_standard`, `category`, `grain`
   - **Critical:** Must have entries for your `active_project_id` (e.g., `"cve_data"`)

9. **`leen_metrics_registry`**
   - **Purpose:** Metric definitions, KPIs, trends, filters
   - **Used for:** Metric recommendations, calculation planning
   - **Key Fields:** 
     - `metric_id`, `name`, `description`
     - `source_capabilities` (e.g., `["qualys.*", "snyk.*"]`)
     - `source_schemas` (e.g., `["vulnerability_instances", "asset_inventory"]`)
     - `category` (e.g., `"vulnerabilities"`, `"patch_compliance"`)
     - `data_capability` (e.g., `"current_state"`, `"trend"`)
   - **Critical:** Must have `source_schemas` field populated for direct schema lookup

---

## 3. Product Capabilities Collection

**Accessed via:** `_query_product_capabilities_from_qdrant()` in `dt_tool_integration.py`

**Used by DT Nodes:**
- `dt_mdl_schema_retrieval_node` - Queries product capabilities to construct `project_id` for MDL lookup

### Collection:

10. **`product_capabilities`**
   - **Purpose:** Product capabilities mapping (product_id → capability_id)
   - **Used for:** Constructing `project_id` as `"{product_id}_{capability_id}"` for MDL schema filtering
   - **Key Fields:**
     - `product_id` (e.g., `"qualys"`, `"snyk"`, `"wiz"`, `"sentinel"`)
     - `capability_id` (e.g., `"assets"`, `"vulnerabilities"`, `"compliance"`)
     - `name`, `description`, `product_name`
     - `type` (must be `"PRODUCT_CAPABILITY"`)
   - **Critical:** Must have entries for your data sources:
     - `snyk` → capabilities (e.g., `"vulnerabilities"`, `"dependencies"`)
     - `qualys` → capabilities (e.g., `"assets"`, `"vulnerabilities"`, `"compliance"`)
     - `wiz` → capabilities (e.g., `"cloud_findings"`, `"misconfigs"`)
     - `sentinel` → capabilities (e.g., `"security_events"`, `"alerts"`)
   - **Example Entry:**
     ```json
     {
       "product_id": "qualys",
       "capability_id": "assets",
       "name": "Asset Inventory",
       "type": "PRODUCT_CAPABILITY",
       "description": "Qualys asset inventory and discovery"
     }
     ```
   - **Note:** This collection is created on-the-fly if not found, but should be pre-populated for best performance

---

## 4. Optional Collections

### Collection:

11. **`xsoar_enriched`** (Optional)
   - **Purpose:** XSOAR content examples (dashboards, scripts, integrations)
   - **Used for:** Dashboard examples and enrichment (not critical for DT workflow)
   - **Entity Types:** `dashboard`, `script`, `integration`, `indicator`, `playbook`

---

## Data Population Checklist

### Framework KB Collections
- [ ] `framework_controls` - Populated with controls for HIPAA, SOC2, etc.
- [ ] `framework_requirements` - Populated with framework requirements
- [ ] `framework_risks` - Populated with risk scenarios
- [ ] `framework_scenarios` - Populated with attack scenarios
- [ ] `framework_test_cases` - Optional, for validation

### MDL Collections
- [ ] `leen_db_schema` - Populated with table schemas, filtered by `project_id`
- [ ] `leen_table_description` - Populated with table descriptions, filtered by `project_id`
- [ ] `leen_project_meta` - Populated with project metadata and GoldStandardTables
- [ ] `leen_metrics_registry` - Populated with metrics, including `source_schemas` field

### Product Capabilities
- [ ] `product_capabilities` - Populated with product_id → capability_id mappings for:
  - [ ] `snyk` → capabilities
  - [ ] `qualys` → capabilities
  - [ ] `wiz` → capabilities
  - [ ] `sentinel` → capabilities

### Critical Data Relationships

1. **Metrics → Schemas:**
   - `leen_metrics_registry.source_schemas` must match `leen_db_schema.table_name`
   - Example: If metric has `source_schemas: ["vulnerability_instances"]`, then `leen_db_schema` must have a table with `table_name: "vulnerability_instances"`

2. **Product Capabilities → MDL Schemas:**
   - `product_capabilities` entry with `product_id="qualys"`, `capability_id="assets"` → constructs `project_id="qualys_assets"`
   - `leen_db_schema` entries must have `project_id="qualys_assets"` for filtering

3. **Project Meta → GoldStandardTables:**
   - `leen_project_meta` entries with `project_id="cve_data"` and `is_gold_standard=true` → used for medallion architecture

---

## Verification Commands

### Check Framework KB Collections
```python
from app.retrieval.service import RetrievalService

service = RetrievalService()
controls = service.search_controls(query="HIPAA audit", framework_id="hipaa", limit=5)
risks = service.search_risks(query="unauthorized access", framework_id="hipaa", limit=5)
scenarios = service.search_scenarios(query="credential theft", limit=5)
```

### Check MDL Collections
```python
from app.retrieval.mdl_service import MDLRetrievalService

mdl_service = MDLRetrievalService()
schemas = await mdl_service.search_db_schema(query="vulnerability", limit=5, project_id="qualys_assets")
metrics = await mdl_service.search_metrics_registry(query="vulnerability management", limit=5)
project_meta = await mdl_service.search_project_meta(query="gold standard", project_id="cve_data", limit=5)
```

### Check Product Capabilities
```python
from app.core.dependencies import get_doc_store_provider

doc_store = get_doc_store_provider()
product_cap_store = doc_store.stores.get("product_capabilities")
if product_cap_store:
    results = product_cap_store.semantic_search(
        query="qualys capabilities",
        k=10,
        where={"product_id": {"$eq": "qualys"}}
    )
```

---

## Common Issues

1. **Schema Lookup Misses:**
   - **Symptom:** `dt_mdl_schema_retrieval_node` reports `lookup_misses`
   - **Cause:** `leen_metrics_registry.source_schemas` doesn't match `leen_db_schema.table_name`
   - **Fix:** Ensure schema names in metrics registry exactly match table names in `leen_db_schema`

2. **No Product Capabilities Found:**
   - **Symptom:** `dt_retrieve_mdl_schemas` returns empty results
   - **Cause:** `product_capabilities` collection not populated or product_id not found
   - **Fix:** Populate `product_capabilities` with entries for your data sources (snyk, qualys, wiz, sentinel)

3. **No GoldStandardTables:**
   - **Symptom:** `dt_gold_standard_tables` is empty
   - **Cause:** `leen_project_meta` has no entries with `project_id="cve_data"` and `is_gold_standard=true`
   - **Fix:** Populate `leen_project_meta` with GoldStandardTable entries for your project_id

4. **Metrics Not Filtered by Source:**
   - **Symptom:** Metrics returned don't match selected data sources
   - **Cause:** `leen_metrics_registry.source_capabilities` not populated or doesn't match data source names
   - **Fix:** Ensure `source_capabilities` field contains patterns matching your data sources (e.g., `["qualys.*"]` for Qualys)

---

## References

- **Collections Registry:** `app/storage/collections.py`
- **MDL Service:** `app/retrieval/mdl_service.py`
- **DT Tool Integration:** `app/agents/dt_tool_integration.py`
- **Collections Documentation:** `docs/collections.md`


python tests/test_detection_triage_workflow.py
python tests/test_detection_triage_workflow.py --test intent_classifier
python tests/test_detection_triage_workflow.py --test mdl_schema
python tests/test_detection_triage_workflow.py --test playbook_assembler