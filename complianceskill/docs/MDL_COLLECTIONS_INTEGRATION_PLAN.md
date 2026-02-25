# MDL Collections Integration Plan

## Overview

This plan outlines how to integrate four MDL (Metadata Language) collections into the compliance automation pipeline to enhance planning and artifact generation capabilities:

- **`leen_db_schema`**: MDL DDL chunks (TABLE + TABLE_COLUMNS) - Database schema information
- **`leen_table_description`**: MDL table descriptions with columns and relationships
- **`leen_project_meta`**: MDL project metadata (one per file)
- **`leen_metrics_registry`**: Metric definitions, KPIs, trends, filters

---

## Current State Analysis

### What We Have Now

1. **Framework Knowledge Base (Qdrant)**
   - Collections: `controls`, `requirements`, `risks`, `scenarios`, `test_cases`
   - Accessed via `RetrievalService` for compliance context
   - Used by: Planner, Framework Analyzer, Detection Engineer, etc.

2. **Planning Flow**
   - Planner creates execution steps that retrieve framework KB context
   - Steps specify `required_data` (e.g., ["controls", "risks"])
   - `intelligent_retrieval()` routes queries to appropriate RetrievalService methods

3. **Agent Capabilities**
   - Agents generate artifacts (SIEM rules, playbooks, tests) based on framework context
   - **Missing**: Understanding of actual data sources, tables, metrics available

### What's Missing

1. **Data Source Awareness**: Agents don't know what tables/columns exist for monitoring
2. **Metrics Context**: No understanding of available KPIs/metrics for validation
3. **Project Context**: No awareness of project-specific data models
4. **Schema-Aware Generation**: SIEM rules and tests can't reference actual table/column names

---

## Integration Strategy

### Phase 1: Add MDL Collection Access Layer

**Goal**: Create a service to search MDL collections similar to `RetrievalService` for framework KB.

**Components**:

1. **`MDLRetrievalService`** (new class in `app/retrieval/mdl_service.py`)
   - Methods:
     - `search_db_schema(query: str, limit: int = 5) -> List[Dict]`
     - `search_table_descriptions(query: str, limit: int = 5) -> List[Dict]`
     - `search_project_meta(query: str, limit: int = 5) -> List[Dict]`
     - `search_metrics_registry(query: str, limit: int = 5) -> List[Dict]`
     - `search_all_mdl(query: str, limit_per_collection: int = 3) -> Dict[str, List[Dict]]`
   
   - Uses `DocumentChromaStore` or `DocumentQdrantStore` (from `get_doc_store_provider()`)
   - Collection names: `leen_db_schema`, `leen_table_description`, `leen_project_meta`, `leen_metrics_registry`

2. **Update `dependencies.py`**
   - Add MDL collections to `get_doc_store_provider()`:
     ```python
     "leen_db_schema": DocumentChromaStore(...),
     "leen_table_description": DocumentChromaStore(...),
     "leen_project_meta": DocumentChromaStore(...),
     "leen_metrics_registry": DocumentChromaStore(...),
     ```

### Phase 2: Enhance Planner with MDL Context

**Goal**: Planner can discover relevant data sources and metrics when creating execution plans.

**Changes**:

1. **Update `planner_node()` in `nodes.py`**
   - Before creating plan, optionally search MDL collections:
     - If user query mentions "monitoring", "data", "metrics", "tables" → search MDL
     - If intent involves "detection", "validation", "testing" → search MDL
   
   - Add MDL context to planner prompt:
     ```python
     # In planner_node()
     mdl_context = ""
     if should_include_mdl_context(state):
         mdl_service = MDLRetrievalService()
         # Search for relevant tables/metrics
         tables = mdl_service.search_table_descriptions(
             query=f"{state['user_query']} monitoring detection",
             limit=5
         )
         metrics = mdl_service.search_metrics_registry(
             query=f"{state['user_query']} compliance validation",
             limit=5
         )
         mdl_context = format_mdl_context_for_prompt(tables, metrics)
     ```

2. **Update `02_planner.md` prompt**
   - Add section about MDL collections:
     ```
     ### AVAILABLE DATA SOURCES (MDL Collections)
     
     You have access to metadata about:
     - Database schemas (tables, columns, data types)
     - Table descriptions (relationships, business context)
     - Project metadata (data models, project context)
     - Metrics registry (KPIs, validation metrics, trends)
     
     When planning steps that involve:
     - Monitoring/detection → Consider relevant tables from leen_table_description
     - Validation/testing → Consider metrics from leen_metrics_registry
     - Data pipelines → Consider schemas from leen_db_schema
     ```

3. **Enhance `PlanStep` dataclass** (optional)
   - Add optional field: `mdl_context: Optional[Dict]` to store relevant MDL data for the step

### Phase 3: Enhance Plan Executor with MDL Retrieval

**Goal**: When executing plan steps, retrieve MDL context alongside framework KB context.

**Changes**:

1. **Update `plan_executor_node()` in `nodes.py`**
   - After retrieving framework KB context, optionally retrieve MDL context:
     ```python
     # In plan_executor_node()
     if step.agent in ["detection_engineer", "test_generator", "pipeline_builder"]:
         # These agents benefit from MDL context
         mdl_service = MDLRetrievalService()
         mdl_context = mdl_service.search_all_mdl(
             query=step.description,
             limit_per_collection=3
         )
         step.context["mdl"] = mdl_context
         state["context_cache"][f"{step.step_id}_mdl"] = mdl_context
     ```

2. **Update `intelligent_retrieval()` in `tool_integration.py`**
   - Add optional MDL retrieval:
     ```python
     def intelligent_retrieval(
         query: str,
         required_data: List[str],
         framework_id: Optional[str] = None,
         include_mdl: bool = False,  # NEW
         retrieval_service: Optional[RetrievalService] = None
     ) -> Dict[str, Any]:
         # ... existing framework KB retrieval ...
         
         if include_mdl:
             mdl_service = MDLRetrievalService()
             results["mdl"] = mdl_service.search_all_mdl(query, limit_per_collection=3)
         
         return results
     ```

### Phase 4: Enhance Agent Prompts with MDL Context

**Goal**: Generator agents (Detection Engineer, Test Generator, Playbook Writer) can use actual table/column names and metrics.

**Changes**:

1. **Update `03_detection_engineer.md`**
   - Add section:
     ```
     ### DATA SOURCE CONTEXT
     
     If MDL context is provided, use actual table and column names in your SIEM rules:
     - Reference specific tables: `index=security_logs | table=authentication_events`
     - Use actual column names: `user_id`, `event_timestamp`, `ip_address`
     - Reference metrics: Use metric definitions from metrics registry for alert thresholds
     ```

2. **Update `09_test_generator.md`**
   - Add section:
     ```
     ### DATA SOURCE CONTEXT
     
     If MDL context is provided:
     - Write tests that query actual tables from leen_db_schema
     - Use table relationships from leen_table_description
     - Validate against metrics from leen_metrics_registry
     - Reference project metadata from leen_project_meta for context
     ```

3. **Update generator nodes** (`enhanced_detection_engineer_node`, `enhanced_test_generator_node`, etc.)
   - Extract MDL context from step context:
     ```python
     # In enhanced_detection_engineer_node()
     mdl_context = state.get("context_cache", {}).get(f"{current_step.step_id}_mdl", {})
     if mdl_context:
         tables = mdl_context.get("leen_table_description", [])
         metrics = mdl_context.get("leen_metrics_registry", [])
         # Format and include in prompt
     ```

### Phase 5: Add MDL Tools to Tool Registry (Optional)

**Goal**: Make MDL collections accessible as LangChain tools for tool-calling agents.

**Changes**:

1. **Create `app/agents/tools/mdl_tools.py`**
   - Tools:
     - `search_db_schema_tool`: Search database schemas
     - `search_table_descriptions_tool`: Search table descriptions
     - `search_metrics_registry_tool`: Search metrics
     - `search_project_meta_tool`: Search project metadata

2. **Update `app/agents/tools/__init__.py`**
   - Add MDL tools to `TOOL_REGISTRY`

3. **Update `get_tools_for_agent()` in `tool_integration.py`**
   - Add MDL tools to relevant agents:
     ```python
     "detection_engineer": [
         # ... existing tools ...
         "search_table_descriptions",
         "search_metrics_registry",
     ],
     "test_generator": [
         # ... existing tools ...
         "search_db_schema",
         "search_table_descriptions",
         "search_metrics_registry",
     ],
     ```

---

## Use Cases & Benefits

### Use Case 1: Schema-Aware SIEM Rule Generation

**Before**:
```splunk
index=security | search "failed login" | stats count by user
```

**After** (with MDL context):
```splunk
index=security_logs | table=authentication_events 
| where event_type="login_failure" 
| stats count by user_id, ip_address
| where count > 5
```

**Benefit**: Rules reference actual table/column names, making them immediately deployable.

### Use Case 2: Data-Driven Test Generation

**Before**:
```python
def test_control_compliance():
    # Generic test
    assert True
```

**After** (with MDL context):
```python
def test_control_compliance():
    # Query actual table
    result = query_table(
        table="compliance_audit_log",
        columns=["control_id", "status", "timestamp"],
        filters={"control_id": "CIS-1.1.1", "status": "passed"}
    )
    assert len(result) > 0, "Control must have audit evidence"
```

**Benefit**: Tests validate against actual data sources.

### Use Case 3: Metrics-Based Validation

**Before**:
- Playbooks/test scripts use generic thresholds

**After** (with MDL context):
- Reference actual metrics from `leen_metrics_registry`:
  - "Alert if failed login rate exceeds `metric:auth_failure_rate_threshold`"
  - "Validate control using `metric:compliance_score_kpi`"

**Benefit**: Artifacts align with existing metrics/KPIs.

### Use Case 4: Project-Aware Planning

**Before**:
- Planner creates generic steps

**After** (with MDL context):
- Planner knows project-specific data models:
  - "This project uses `wiz_scan_results` table for vulnerability data"
  - "Use `qualys_compliance_scores` metric for validation"

**Benefit**: Plans are tailored to actual project infrastructure.

---

## Implementation Order

### Step 1: Foundation (Low Risk)
1. ✅ Create `MDLRetrievalService` class
2. ✅ Add MDL collections to `get_doc_store_provider()`
3. ✅ Test MDL collection access (verify collections exist and are queryable)

### Step 2: Planner Enhancement (Medium Risk)
1. ✅ Add MDL context detection logic to planner
2. ✅ Update planner prompt with MDL section
3. ✅ Test planner with MDL-aware queries

### Step 3: Plan Executor Enhancement (Medium Risk)
1. ✅ Add MDL retrieval to `plan_executor_node()`
2. ✅ Update `intelligent_retrieval()` to optionally include MDL
3. ✅ Test plan execution with MDL context

### Step 4: Agent Prompt Updates (Low Risk)
1. ✅ Update generator agent prompts (detection_engineer, test_generator, etc.)
2. ✅ Update generator nodes to extract and use MDL context
3. ✅ Test artifact generation with MDL context

### Step 5: Tool Integration (Optional, Low Risk)
1. ✅ Create MDL tools
2. ✅ Add to tool registry
3. ✅ Test tool-calling agents with MDL tools

---

## Risk Mitigation

### Risk 1: MDL Collections Not Available
- **Mitigation**: Make MDL retrieval optional (graceful degradation)
- **Fallback**: Agents work without MDL context (current behavior)

### Risk 2: Performance Impact
- **Mitigation**: 
  - Only search MDL when needed (conditional based on query/intent)
  - Cache MDL results in `context_cache`
  - Limit results per collection (default: 3-5)

### Risk 3: Collection Name Mismatch
- **Mitigation**: 
  - Make collection names configurable via settings
  - Add validation to check if collections exist before querying
  - Log warnings if collections are missing

### Risk 4: Schema Drift
- **Mitigation**:
  - MDL collections are metadata (should be relatively stable)
  - Agents should handle missing/outdated schema gracefully
  - Consider adding schema versioning if needed

---

## Testing Strategy

### Unit Tests
1. Test `MDLRetrievalService` methods with mock document stores
2. Test MDL context formatting functions
3. Test conditional MDL retrieval logic

### Integration Tests
1. Test planner with MDL context enabled
2. Test plan executor with MDL retrieval
3. Test generator agents with MDL context in prompts
4. Verify artifacts reference actual tables/metrics when MDL available

### Manual Testing
1. Run end-to-end workflow with MDL collections
2. Verify SIEM rules use actual table names
3. Verify tests query actual tables
4. Verify metrics are referenced correctly

---

## Configuration

### Environment Variables
```bash
# Optional: Override default MDL collection names
MDL_DB_SCHEMA_COLLECTION=leen_db_schema
MDL_TABLE_DESC_COLLECTION=leen_table_description
MDL_PROJECT_META_COLLECTION=leen_project_meta
MDL_METRICS_COLLECTION=leen_metrics_registry

# Optional: Enable/disable MDL integration
ENABLE_MDL_INTEGRATION=true
```

### Settings
```python
# In app/settings.py
class Settings:
    # ... existing settings ...
    
    # MDL Collection Configuration
    MDL_DB_SCHEMA_COLLECTION: str = "leen_db_schema"
    MDL_TABLE_DESC_COLLECTION: str = "leen_table_description"
    MDL_PROJECT_META_COLLECTION: str = "leen_project_meta"
    MDL_METRICS_COLLECTION: str = "leen_metrics_registry"
    ENABLE_MDL_INTEGRATION: bool = True
```

---

## Success Criteria

1. ✅ Planner can discover relevant tables/metrics when creating plans
2. ✅ Plan executor retrieves MDL context for relevant steps
3. ✅ Generator agents produce artifacts that reference actual table/column names
4. ✅ Tests validate against actual data sources
5. ✅ SIEM rules use real table names (when MDL available)
6. ✅ Metrics are referenced from metrics registry
7. ✅ Graceful degradation when MDL collections are unavailable

---

## Next Steps

1. **Review this plan** - Confirm approach and priorities
2. **Verify MDL collections exist** - Check if collections are already indexed
3. **Start with Phase 1** - Create `MDLRetrievalService` and test collection access
4. **Iterate** - Implement phases incrementally, testing after each phase

---

## Questions to Resolve

1. **Collection Names**: Are the collection names exactly `leen_db_schema`, `leen_table_description`, `leen_project_meta`, `leen_metrics_registry`? (Note: doc says `leen_metric_registry` but we'll use `leen_metrics_registry`)

2. **Collection Structure**: What metadata fields are in each collection? (Need to understand filter capabilities)

3. **Project ID Filtering**: Do MDL collections support project_id filtering? (Similar to framework_id filtering in framework KB)

4. **Vector Store Type**: Are MDL collections in ChromaDB or Qdrant? (Need to use correct document store type)

5. **Indexing Status**: Are these collections already populated with data?

---

## Appendix: Example Code Structure

### MDLRetrievalService (Outline)
```python
class MDLRetrievalService:
    def __init__(self, doc_store_provider=None):
        self.doc_stores = doc_store_provider or get_doc_store_provider()
    
    def search_db_schema(self, query: str, limit: int = 5, project_id: Optional[str] = None):
        store = self.doc_stores.stores.get("leen_db_schema")
        # Semantic search with optional project_id filter
        return store.semantic_search(query=query, k=limit, where={"project_id": project_id} if project_id else None)
    
    # Similar methods for other collections...
```

### Enhanced Planner (Outline)
```python
def planner_node(state):
    # Check if MDL context should be included
    should_include_mdl = _should_include_mdl_context(state)
    
    mdl_context = ""
    if should_include_mdl:
        mdl_service = MDLRetrievalService()
        # Search for relevant context
        tables = mdl_service.search_table_descriptions(...)
        metrics = mdl_service.search_metrics_registry(...)
        mdl_context = format_mdl_context_for_prompt(tables, metrics)
    
    # Include mdl_context in planner prompt
    prompt = load_prompt("02_planner") + f"\n\n### MDL CONTEXT ###\n{mdl_context}"
    # ... rest of planner logic
```
