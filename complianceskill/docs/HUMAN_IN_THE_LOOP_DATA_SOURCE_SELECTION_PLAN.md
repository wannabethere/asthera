# Human-in-the-Loop Data Source & Focus Area Selection Plan (REVISED)

## Overview

This plan introduces a streamlined approach to data source and focus area selection for the compliance automation workflow. Based on architectural review, the plan has been revised to eliminate per-query interrupts and use static catalogs with tenant profiles.

**Key Changes from Original Plan:**
- Data sources are tenant configuration (one-time), not per-query interrupts
- Focus areas are static catalog lookups, not dynamically discovered
- Metrics registry schema (`source_capabilities`, `category`, `source_schemas`) solves filtering at schema level
- Single optional interrupt for metric confirmation (dashboard intent only)

## Current Flow (Problem)

```
Intent Classifier → Planner → Plan Executor → [Agent Nodes]
```

**Issues:**
- Dashboard generator searches XSOAR/metrics registry with generic query (not enriched with framework context)
- MDL schemas retrieved with free-text search → returns "unknown" tables, LLM fabricates table names
- No metrics recommender to filter metrics by tenant's configured data sources
- Empty XSOAR references because search uses vague user query instead of precise metric anchors

## Revised Enhanced Flow

```
Intent Classifier
  → Profile Resolver (lookup existing tenant profile, or run onboarding once)
       ↓ [profile exists: framework + vendor capabilities + data sources]
  → Focus Area Resolver (static catalog lookup, no interrupt)
       ↓ [focus_areas from catalog, e.g., CC6.1, CC7.2, AU-12]
  → Planner (now has framework + focus areas as hard context)
  → Plan Executor
  → [Framework Analyzer / Detection Engineer / Playbook Writer]
       (all use focus_areas as retrieval filter, not generic query)
  
  → IF dashboard intent:
       → Metrics Recommender
           → Query leen_metrics_registry filtered by [focus_areas + framework + source_capabilities]
           → Optional interrupt: "Confirm these metrics?"
       → Dashboard Generator
           → Use confirmed metrics from registry (content)
           → Use source_schemas for direct MDL lookup (no fabrication)
           → Use natural_language_question for XSOAR search (precise anchor)
           → Query xsoar_enriched for layout patterns (presentation)
           → Generate with real metric anchors, not generic query
```

**Key Differences:**
- **No mandatory interrupts** for data source/focus area selection (tenant profile handles this)
- **Static catalog lookup** for focus areas (deterministic from framework + data source)
- **Metrics registry as primary source** (filtered by `source_capabilities` and `category`)
- **Direct MDL lookup** via `source_schemas` field (no semantic search needed)
- **Precise XSOAR search** via `natural_language_question` from metrics (not user query)

## State Schema Updates

Add to `EnhancedCompliancePipelineState`:

```python
# Tenant profile (one-time configuration)
compliance_profile: Optional[Dict[str, Any]]  # {
#   framework: "soc2_type2",
#   vendor_capabilities: ["endpoint_detection", "log_management", "identity"],
#   data_sources: ["qualys", "sentinel", "snyk"],
#   tenant_field_mappings: {...}  # Field name mappings per data source
# }

# Focus areas (resolved from static catalog)
resolved_focus_areas: List[Dict[str, Any]]  # [{id, name, categories, framework_mappings, source_capabilities}]
focus_area_categories: List[str]  # ["vulnerabilities", "access_control", "audit_logging"]

# Metrics recommender (for dashboard intent)
resolved_metrics: List[Dict[str, Any]]  # [{
#   metric_id: "vuln_count_by_severity",
#   source_schemas: ["vulnerability_instances_schema", ...],  # for direct MDL lookup
#   source_capabilities: ["qualys.vulnerabilities", ...],      # for retrieval scoping
#   kpis: [...],                                               # widget content
#   trends: [...],                                             # widget content
#   natural_language_question: "...",                          # xsoar search anchor
#   data_filters: [...],                                       # user-configurable filters
#   data_groups: [...]                                         # grouping dimensions
# }]
selected_metric_ids: Optional[List[str]]  # User-selected metrics (optional, for interrupt)
```

## New Nodes Required (REVISED)

### 1. Profile Resolver Node
**File:** `app/agents/nodes.py`  
**Function:** `profile_resolver_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState`

**Purpose:**
- Lookup existing tenant compliance profile (one-time configuration)
- If profile exists: use it and skip to focus area resolution
- If profile doesn't exist: trigger onboarding flow (separate, not per-query)

**Output:**
- `compliance_profile`: Tenant profile with framework, vendor capabilities, data sources, field mappings

**Implementation Notes:**
- Profile stored in tenant config or state cache
- Onboarding is separate flow (not part of per-query workflow)
- Profile includes: `framework`, `vendor_capabilities`, `data_sources`, `tenant_field_mappings`

### 2. Focus Area Resolver Node
**File:** `app/agents/nodes.py`  
**Function:** `focus_area_resolver_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState`

**Purpose:**
- Resolve focus areas from static catalog based on framework + data sources
- Uses `app/config/focus_areas/{data_source}_focus_areas.json` catalogs
- No LLM needed - pure lookup

**Output:**
- `resolved_focus_areas`: List of focus areas from catalog
- `focus_area_categories`: List of category strings for filtering

**Implementation Notes:**
- Load catalog via `app/config/focus_areas/__init__.py` utilities
- Filter by framework: `get_focus_areas_by_framework(data_source, framework_id)`
- Each focus area includes: `id`, `name`, `categories`, `framework_mappings`, `source_capabilities`, `mdl_schemas`
- **No interrupt needed** - deterministic lookup

### 3. Metrics Recommender Node (Dashboard Intent)
**File:** `app/agents/nodes.py`  
**Function:** `metrics_recommender_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState`

**Purpose:**
- Filter metrics from `leen_metrics_registry` using deterministic steps:
  1. Filter by `source_capabilities` (match tenant's configured data sources)
  2. Filter by `category` (derived from resolved focus areas)
  3. Score/rank by `data_capability` match (temporal vs semantic)
- LLM only used to explain selection and handle optional confirmation interrupt

**Output:**
- `resolved_metrics`: List of filtered metrics with full schema fields
- Optional interrupt: "Confirm these metrics?" (user can proceed or deselect)

**Implementation Notes:**
- **Step 1**: Filter by `source_capabilities` metadata field
  - If tenant has `qualys`, keep metrics where `source_capabilities` contains `qualys.*`
  - Pure metadata filter on Qdrant query
- **Step 2**: Filter by `category` field
  - Map framework control codes to metric categories (static lookup)
  - SOC2 CC7.1 → `category: "vulnerabilities"`
  - HIPAA 164.312(b) → `category: "audit_logging"`
- **Step 3**: Score by `data_capability` match
  - "temporal" if user wants trends
  - "semantic" if analysis needed
- **LLM**: Only for explanation and optional confirmation interrupt
- Each metric includes: `source_schemas`, `source_capabilities`, `kpis`, `trends`, `natural_language_question`, `data_filters`, `data_groups`

### 4. Intent-Specific Retrieval Nodes (Enhanced)

#### 4a. Enhanced Dashboard Generator Node
**Current:** `dashboard_generator_node`  
**Enhancement:** Use resolved metrics and focus areas for precise retrieval

**Changes:**
1. **Metrics Registry (Primary Source of Truth)**:
   - Already filtered by `metrics_recommender_node`
   - Use `resolved_metrics` from state (not generic query)
   - Each metric has `source_schemas`, `kpis`, `trends`, `natural_language_question`

2. **MDL Schema Retrieval (Direct Lookup)**:
   - Use `source_schemas` field from resolved metrics
   - Direct lookup in `leen_db_schema` by schema name (no semantic search)
   - No more "unknown" tables or fabricated table names
   - Example: `vulnerability_instances_schema` → direct lookup → actual table/column definitions

3. **XSOAR Dashboard Search (Precise Anchor)**:
   - Use `natural_language_question` from resolved metrics (not user query)
   - Query `xsoar_enriched` (entity_type="dashboard") with precise metric question
   - Example: "How many critical and high severity vulnerabilities..." (from metric)
   - This solves empty XSOAR references problem

4. **Widget Content Definition**:
   - Use `kpis` array from metrics → gauge/count widgets
   - Use `trends` array from metrics → time-series widgets
   - Use XSOAR layout patterns → presentation/styling

#### 4b. Enhanced Pipeline Generator (if exists)
**Enhancement:** Search pipeline examples by focus areas

**Changes:**
1. Query pipeline examples from XSOAR or MDL collections
2. Filter by `resolved_focus_areas` categories
3. Use as examples in pipeline generation prompt

#### 4c. Enhanced SIEM Rule Generator
**Enhancement:** Search indicators by focus areas

**Changes:**
1. Query `xsoar_enriched` (entity_type="indicator") filtered by `focus_area_categories`
2. Use indicators as examples/patterns in SIEM rule generation

## Workflow Graph Updates (REVISED)

### Updated Workflow Structure

```python
# Entry point
workflow.set_entry_point("intent_classifier")

# After intent classification, route to profile resolver
workflow.add_edge("intent_classifier", "profile_resolver")

# Profile resolution (no interrupt for returning users)
workflow.add_node("profile_resolver", profile_resolver_node)
workflow.add_edge("profile_resolver", "focus_area_resolver")

# Focus area resolution (static catalog lookup, no interrupt)
workflow.add_node("focus_area_resolver", focus_area_resolver_node)
workflow.add_edge("focus_area_resolver", "planner")

# Planner now has framework + focus areas as hard context
workflow.add_edge("planner", "plan_executor")

# Intent-specific routing after plan executor
def route_after_plan_executor(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("intent", "")
    if intent == "dashboard_generation":
        return "metrics_recommender"  # Then → dashboard_generator
    elif intent == "detection_engineering":
        return "detection_engineer"
    elif intent == "pipeline_generation":
        return "pipeline_generator"
    else:
        return "framework_analyzer"  # Default flow

workflow.add_conditional_edges(
    "plan_executor",
    route_after_plan_executor,
    {
        "metrics_recommender": "metrics_recommender",
        "detection_engineer": "detection_engineer",
        "pipeline_generator": "pipeline_generator",
        "framework_analyzer": "framework_analyzer"
    }
)

# Metrics recommender (for dashboard intent) - optional interrupt
workflow.add_node("metrics_recommender", metrics_recommender_node)
# Optional interrupt node for metric confirmation
workflow.add_node("wait_for_metrics_confirmation", wait_for_metrics_confirmation_node)
workflow.add_conditional_edges(
    "metrics_recommender",
    lambda state: "wait_for_metrics_confirmation" if state.get("show_metrics_interrupt") else "dashboard_generator",
    {
        "wait_for_metrics_confirmation": "wait_for_metrics_confirmation",
        "dashboard_generator": "dashboard_generator"
    }
)
workflow.add_edge("wait_for_metrics_confirmation", "dashboard_generator")

# Existing nodes continue from here
# ... rest of existing workflow
```

**Key Changes:**
- **No mandatory interrupts** before planning starts
- **Profile resolver** checks for existing tenant profile (one-time)
- **Focus area resolver** does static catalog lookup (deterministic)
- **Metrics recommender** has optional interrupt (dashboard intent only)

## Intent-Specific Flows

### 1. Dashboard Generation Intent

```
Intent Classifier (dashboard_generation)
  → Data Source Discovery
    - Search: MDL collections, XSOAR dashboards, metrics registry
    - Output: available_datasources (MDL sources, XSOAR, framework KB)
  → Wait for Data Source Selection (INTERRUPT)
    - User selects: e.g., ["snyk_mdl", "xsoar_enriched", "hipaa_framework"]
  → Focus Area Discovery
    - Based on selected sources + user query
    - Query capabilities of selected sources
    - Output: available_focus_areas (e.g., ["vulnerability_management", "access_control", "audit_logging"])
  → Wait for Focus Area Selection (INTERRUPT)
    - User selects: e.g., ["vulnerability_management", "access_control"]
  → Metrics Recommender
    - Query metrics_registry filtered by:
      - Selected focus areas
      - Selected data sources
      - Framework context
    - Output: recommended_metrics with relevance scores
  → Dashboard Generator (Enhanced)
    - XSOAR Dashboard Search: Filter by selected focus areas
    - Metrics Registry Search: Use recommended_metrics + focus areas
    - MDL Schema Retrieval: Filter by selected data sources + focus areas
    - Generate dashboard with scoped context
```

### 2. Detection Engineering Intent

```
Intent Classifier (detection_engineering)
  → Data Source Discovery
    - Search: XSOAR indicators, ATT&CK, framework controls
    - Output: available_datasources
  → Wait for Data Source Selection (INTERRUPT)
  → Focus Area Discovery
    - Based on selected sources + user query
    - Output: available_focus_areas (attack vectors, threat categories)
  → Wait for Focus Area Selection (INTERRUPT)
  → Planner
    - Uses selected data sources + focus areas in plan
  → Plan Executor
  → Detection Engineer (Enhanced)
    - XSOAR Indicator Search: Filter by selected focus areas
    - ATT&CK Search: Filter by focus areas
    - Generate SIEM rules with scoped context
```

### 3. Pipeline Generation Intent

```
Intent Classifier (pipeline_generation)
  → Data Source Discovery
    - Search: MDL collections, pipeline examples
    - Output: available_datasources
  → Wait for Data Source Selection (INTERRUPT)
  → Focus Area Discovery
    - Based on selected sources + user query
    - Output: available_focus_areas (ETL patterns, transformation categories)
  → Wait for Focus Area Selection (INTERRUPT)
  → Planner
  → Plan Executor
  → Pipeline Generator (Enhanced)
    - Pipeline Example Search: Filter by selected focus areas
    - MDL Schema Retrieval: Filter by selected data sources
    - Generate pipeline with scoped context
```

### 4. Compliance Validation Intent (Full Chain)

```
Intent Classifier (compliance_validation)
  → Data Source Discovery
    - Search: All available sources (MDL, XSOAR, framework KB)
  → Wait for Data Source Selection (INTERRUPT)
  → Focus Area Discovery
    - Output: available_focus_areas (control domains, compliance categories)
  → Wait for Focus Area Selection (INTERRUPT)
  → Planner
    - Creates plan with awareness of selected sources + focus areas
  → Plan Executor
    - Uses selected sources + focus areas for retrieval
  → Framework Analyzer (Enhanced)
    - Retrieves controls filtered by focus areas
  → Detection Engineer (Enhanced)
    - Uses selected sources + focus areas
  → Playbook Writer (Enhanced)
    - Uses selected sources + focus areas
  → Dashboard Generator (Enhanced)
    - Uses selected sources + focus areas
```

## Service Layer Updates

### New Service: CompliancePlannerService
**File:** `app/services/compliance_planner_service.py`  
**Similar to:** `LeenPlannerService`

**Purpose:**
- Stream compliance workflow with interrupt/resume support
- Handle data source and focus area selection interrupts
- Extract results for UI display

**Methods:**
- `stream_compliance_workflow(goal, session_id, resume=None) -> AsyncGenerator[str, None]`
- `invoke_with_resume(session_id, resume) -> Dict[str, Any]`
- `get_state(session_id) -> Optional[Dict[str, Any]]`
- `detect_interrupt_from_state(state) -> tuple[Optional[str], Optional[Dict]]`

**Interrupt Detection:**
```python
def detect_interrupt_from_state(state: Dict[str, Any]) -> tuple[Optional[str], Optional[Dict]]:
    # Data source selection interrupt
    if state.get("available_datasources") and not state.get("selected_datasource_ids"):
        return "wait_for_datasource_selection", {
            "message": "Please select which data sources to use.",
            "available_datasources": state.get("available_datasources", []),
            "suggested_datasources": state.get("suggested_datasources", []),
        }
    
    # Focus area selection interrupt
    if state.get("available_focus_areas") and not state.get("selected_focus_area_ids"):
        return "wait_for_focus_area_selection", {
            "message": "Please select which focus areas to use.",
            "available_focus_areas": state.get("available_focus_areas", []),
            "selected_datasources": state.get("selected_datasource_ids", []),
        }
    
    # Metrics selection interrupt (optional, for dashboard intent)
    if state.get("recommended_metrics") and state.get("intent") == "dashboard_generation":
        # Optional: allow user to filter metrics
        pass
    
    return None, None
```

## Router Updates

### New Router: Compliance Planner Router
**File:** `app/routers/compliance_planner.py`  
**Similar to:** `leen_planner.py`

**Endpoints:**
- `POST /api/compliance/stream` - Start or resume compliance workflow stream
- `POST /api/compliance/resume` - Resume after interrupt (non-streaming)
- `GET /api/compliance/state/{session_id}` - Get current state (for interrupt payload)

## Retrieval Service Enhancements

### MDLRetrievalService Updates
**File:** `app/retrieval/mdl_service.py` (may need to be created)

**New Methods:**
```python
async def search_metrics_registry(
    query: str,
    focus_areas: Optional[List[str]] = None,
    datasource_ids: Optional[List[str]] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Search metrics registry filtered by focus areas and data sources."""
    
async def search_all_mdl(
    query: str,
    datasource_ids: Optional[List[str]] = None,
    focus_areas: Optional[List[str]] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """Search all MDL collections with filters."""
```

### XSOARRetrievalService Updates
**File:** `app/retrieval/xsoar_service.py`

**Enhanced Methods:**
```python
async def search_dashboards(
    query: str,
    focus_areas: Optional[List[str]] = None,
    limit: int = 5,
    project_id: Optional[str] = None
) -> List[XSOARDashboardResult]:
    """Search dashboards filtered by focus areas."""
    # Add focus_area filter to metadata_filters
    
async def search_indicators(
    query: str,
    focus_areas: Optional[List[str]] = None,
    limit: int = 5,
    project_id: Optional[str] = None
) -> List[XSOARIndicatorResult]:
    """Search indicators filtered by focus areas."""
```

## Implementation Steps (REVISED)

### Phase 1: Static Focus Area Catalogs ✅
1. ✅ Create focus area JSON files for each data source:
   - `app/config/focus_areas/qualys_focus_areas.json`
   - `app/config/focus_areas/sentinel_focus_areas.json`
   - `app/config/focus_areas/snyk_focus_areas.json`
   - `app/config/focus_areas/wiz_focus_areas.json`
2. ✅ Create `app/config/focus_areas/__init__.py` loader utilities

### Phase 2: State & Infrastructure
3. Update `EnhancedCompliancePipelineState` with new fields:
   - `compliance_profile`, `resolved_focus_areas`, `focus_area_categories`, `resolved_metrics`
4. Create tenant profile storage/retrieval mechanism (one-time onboarding)

### Phase 3: Profile & Focus Area Resolution
5. Create `profile_resolver_node` (lookup tenant profile)
6. Create `focus_area_resolver_node` (static catalog lookup)
7. Update workflow graph to add profile → focus area → planner flow

### Phase 4: Metrics Recommender (Dashboard Intent)
8. Create `metrics_recommender_node`:
   - Filter by `source_capabilities` (metadata filter)
   - Filter by `category` (from focus areas)
   - Score by `data_capability` match
   - LLM for explanation only
9. Create `wait_for_metrics_confirmation_node` (optional interrupt)
10. Update workflow graph to add metrics recommender → dashboard generator flow

### Phase 5: Enhanced Dashboard Generator
11. Enhance `dashboard_generator_node`:
   - Use `resolved_metrics` from state (not generic query)
   - Use `source_schemas` for direct MDL lookup
   - Use `natural_language_question` for XSOAR search
   - Use `kpis` and `trends` for widget content

### Phase 6: Retrieval Service Updates
12. Update `MDLRetrievalService`:
   - Add `search_by_schema_names()` method (direct lookup by schema name)
   - Remove dependency on semantic search for schema retrieval
13. Update `XSOARRetrievalService`:
   - Enhance `search_dashboards()` to accept `natural_language_question` parameter
   - Use metric questions instead of user query

### Phase 7: Testing & Integration
14. Test profile resolver (with and without existing profile)
15. Test focus area resolver (static catalog lookup)
16. Test metrics recommender (filtering and optional interrupt)
17. Test dashboard generation with resolved metrics
18. Integration tests for full workflow

## Key Design Decisions (REVISED)

1. **Tenant Profile**: Data sources configured once at onboarding, not per-query
2. **Static Focus Area Catalog**: Deterministic lookup from framework + data source (no LLM, no interrupt)
3. **Metrics Registry Schema**: Leverage `source_capabilities`, `category`, `source_schemas` fields for filtering
4. **Direct MDL Lookup**: Use `source_schemas` field for direct schema lookup (no semantic search)
5. **Precise XSOAR Search**: Use `natural_language_question` from metrics (not user query)
6. **Single Optional Interrupt**: Only for metric confirmation (dashboard intent), not mandatory
7. **Backward Compatibility**: Existing workflows work with default profile (all sources)

## Dependencies

- LangGraph interrupt/resume functionality
- CollectionFactory or MDLRetrievalService for data source discovery
- XSOARRetrievalService for XSOAR collections
- Metrics registry collection in Qdrant
- Streaming service support for interrupts

## Success Criteria

1. ✅ Dashboard generator retrieves relevant XSOAR dashboards based on selected focus areas
2. ✅ Dashboard generator retrieves relevant metrics from metrics registry based on selected focus areas
3. ✅ MDL schemas retrieved are scoped to selected data sources
4. ✅ All intents support data source and focus area selection
5. ✅ Human-in-the-loop interrupts work via SSE streaming
6. ✅ Resume functionality works correctly after user selections
