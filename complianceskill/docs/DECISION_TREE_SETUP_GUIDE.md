# Decision Tree Setup and Workflow Execution Guide

This guide covers the complete setup process for the Decision Tree metric enrichment system, from data preparation to workflow execution.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Metrics Registry Preparation](#metrics-registry-preparation)
3. [Indexing Metrics to Qdrant](#indexing-metrics-to-qdrant)
4. [Framework Controls Indexing](#framework-controls-indexing)
5. [Running the Workflows](#running-the-workflows)
6. [Verification Steps](#verification-steps)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Environment Setup

Ensure you have the following configured:

```bash
# Required environment variables (.env file)
QDRANT_HOST=localhost          # Qdrant server host
QDRANT_PORT=6333               # Qdrant server port
QDRANT_API_KEY=                # Optional: API key if using cloud Qdrant
EMBEDDING_MODEL=text-embedding-3-small  # Or your preferred embedding model
OPENAI_API_KEY=                # Required for embeddings (if using OpenAI)
```

### 2. Dependencies

```bash
# Install required packages
pip install qdrant-client langchain openai
```

### 3. Qdrant Server

Ensure Qdrant is running and accessible:

```bash
# Check Qdrant connection
curl http://localhost:6333/health
```

### 4. Metrics Registry Files

You need metrics registry JSON files. These should be in the format:

```json
{
  "metrics": [
    {
      "id": "vuln_count_by_severity",
      "name": "Vulnerability Count by Severity",
      "description": "Count of vulnerabilities grouped by severity level",
      "category": "vulnerabilities",
      "source_capabilities": ["qualys.vulnerabilities", "snyk.vulnerabilities"],
      "source_schemas": ["vulnerability_instances_schema"],
      "kpis": ["critical_count", "high_count", "medium_count"],
      "trends": ["vulnerability_trend"],
      "natural_language_question": "How many vulnerabilities exist by severity?",
      "data_filters": ["severity"],
      "data_groups": ["severity"],
      "data_capability": ["temporal", "aggregation"]
    }
  ]
}
```

**Location:** Metrics files should be in a directory structure like:
```
/path/to/metrics/
  ├── product_metrics.json
  ├── compliance_metrics.json
  └── security_metrics.json
```

---

## Metrics Registry Preparation

### Step 1: Validate Metrics Format

Ensure your metrics JSON files conform to the expected schema. Each metric should have:

- **Required fields:**
  - `id`: Unique metric identifier
  - `name`: Human-readable metric name
  - `description`: Metric description
  - `category`: Metric category (e.g., "vulnerabilities", "access_control")

- **Recommended fields:**
  - `source_capabilities`: List of data source capabilities (e.g., `["qualys.vulnerabilities"]`)
  - `source_schemas`: List of schema names this metric uses
  - `kpis`: List of KPI names this metric supports
  - `trends`: List of trend analysis this metric supports
  - `natural_language_question`: Natural language question this metric answers
  - `data_filters`: List of filter fields
  - `data_groups`: List of grouping fields
  - `data_capability`: List of data capabilities (e.g., `["temporal", "aggregation"]`)

### Step 2: Optional - Enrich Metrics with Decision Tree Attributes

If you want to pre-enrich metrics with decision tree attributes (goals, focus_areas, use_cases, etc.), you can add these fields:

```json
{
  "id": "vuln_count_by_severity",
  "goals": ["risk_exposure", "compliance_posture"],
  "focus_areas": ["vulnerability_management"],
  "use_cases": ["soc2_audit", "risk_posture_report"],
  "audience_levels": ["security_ops", "compliance_team", "executive_board"],
  "metric_type": "distribution",
  "aggregation_windows": ["daily", "weekly", "monthly"],
  "mapped_control_domains": ["CC7"],
  "mapped_risk_categories": ["unpatched_systems"],
  "group_affinity": ["risk_exposure", "compliance_posture"]
}
```

**Note:** If these fields are not present, the decision tree enrichment will infer them at runtime based on category and other metadata.

---

## Indexing Metrics to Qdrant

### Step 1: Index Metrics Registry

Use the ingestion script to index metrics into Qdrant:

```bash
# Index a single metrics file
python -m app.ingestion.ingest_metrics_registry \
  --metrics-file /path/to/metrics/product_metrics.json \
  --collection-name leen_metrics_registry

# Index all metrics files in a directory
python -m app.ingestion.ingest_metrics_registry \
  --metrics-dir /path/to/metrics \
  --collection-name leen_metrics_registry

# Reinitialize collection (WARNING: Deletes existing data)
python -m app.ingestion.ingest_metrics_registry \
  --metrics-dir /path/to/metrics \
  --collection-name leen_metrics_registry \
  --reinit-qdrant
```

### Step 2: Verify Metrics Indexing

Check that metrics were indexed successfully:

```python
from app.retrieval.mdl_service import MDLRetrievalService
import asyncio

async def verify_metrics():
    service = MDLRetrievalService()
    results = await service.search_metrics_registry(
        query="vulnerability count by severity",
        limit=5
    )
    print(f"Found {len(results)} metrics")
    for result in results:
        print(f"  - {result.metric_name} (score: {result.score:.3f})")

asyncio.run(verify_metrics())
```

**Expected output:**
```
Found 5 metrics
  - Vulnerability Count by Severity (score: 0.892)
  - Critical Vulnerability Count (score: 0.856)
  ...
```

---

## Framework Controls Indexing

### Step 1: Index Framework Controls

Framework controls are indexed via the framework ingestion process. This is typically done separately:

```bash
# Ingest SOC2 framework (includes controls)
python -m app.ingestion.ingest \
  --framework soc2 \
  --reinit-qdrant  # Optional: reinitialize collections
```

This indexes controls to the `framework_controls` collection in Qdrant.

### Step 2: Verify Controls Indexing

```python
from app.retrieval.service import RetrievalService

service = RetrievalService()
results = service.search_controls(
    query="vulnerability monitoring",
    framework_filter="soc2",
    limit=5
)

print(f"Found {len(results.controls)} controls")
for ctrl in results.controls:
    print(f"  - {ctrl.code}: {ctrl.name}")
```

---

## Running the Workflows

### Step 1: Prepare Initial State

Create an initial state for the workflow:

```python
from app.agents.dt_workflow import create_dt_initial_state
from app.agents.dt_workflow import get_detection_triage_app

# Create initial state
initial_state = create_dt_initial_state(
    user_query="I need metrics for SOC2 audit focusing on vulnerability management",
    session_id="test-session-123",
    framework_id="soc2",
    selected_data_sources=["qualys", "snyk", "wiz"],
    active_project_id="your-project-id",
)

# Enable decision tree enrichment (default: True)
initial_state["dt_use_decision_tree"] = True
```

### Step 2: Run DT Workflow

```python
from app.agents.dt_workflow import get_detection_triage_app

# Get the workflow app
app = get_detection_triage_app()

# Run the workflow
config = {"configurable": {"thread_id": "test-thread-123"}}
final_state = app.invoke(initial_state, config)

# Check results
print(f"Resolved metrics: {len(final_state.get('resolved_metrics', []))}")
print(f"Decision tree groups: {len(final_state.get('dt_metric_groups', []))}")
print(f"Scored metrics: {len(final_state.get('dt_scored_metrics', []))}")

# View decision tree results
decisions = final_state.get("dt_metric_decisions", {})
print(f"Use case: {decisions.get('use_case')}")
print(f"Goal: {decisions.get('goal')}")
print(f"Confidence: {decisions.get('auto_resolve_confidence', 0):.2f}")

# View grouped metrics
groups = final_state.get("dt_metric_groups", [])
for group in groups:
    print(f"\nGroup: {group.get('group_name')}")
    print(f"  Metrics: {group.get('total_assigned', 0)}")
    print(f"  KPIs: {len(group.get('kpis', []))}")
    print(f"  Trends: {len(group.get('trends', []))}")
```

### Step 3: Run Main Compliance Workflow

```python
from app.agents.workflow import get_compliance_app

# Get the workflow app
app = get_compliance_app()

# Create initial state
initial_state = {
    "user_query": "Generate compliance metrics for SOC2 audit",
    "session_id": "test-session-456",
    "messages": [],
    "framework_id": "soc2",
    "selected_data_sources": ["qualys", "snyk"],
    "resolved_metrics": [],
    "controls": [],
    "risks": [],
    "scenarios": [],
    "execution_steps": [],
    "context_cache": {},
    "dt_use_decision_tree": True,  # Enable decision tree enrichment
}

# Run the workflow
config = {"configurable": {"thread_id": "test-thread-456"}}
final_state = app.invoke(initial_state, config)

# Check results
print(f"Resolved metrics: {len(final_state.get('resolved_metrics', []))}")
print(f"Decision tree groups: {len(final_state.get('dt_metric_groups', []))}")
```

### Step 4: Stream Workflow Execution (Optional)

For debugging, you can stream the workflow execution:

```python
from app.agents.dt_workflow import get_detection_triage_app

app = get_detection_triage_app()
config = {"configurable": {"thread_id": "test-thread-789"}}

# Stream execution
for event in app.stream(initial_state, config):
    node_name = list(event.keys())[0]
    node_output = event[node_name]
    
    if "resolved_metrics" in node_output:
        print(f"[{node_name}] Resolved {len(node_output['resolved_metrics'])} metrics")
    
    if "dt_metric_groups" in node_output:
        print(f"[{node_name}] Created {len(node_output['dt_metric_groups'])} groups")
```

---

## Verification Steps

### 1. Verify Metrics Are Indexed

```python
from app.retrieval.mdl_service import MDLRetrievalService
import asyncio

async def check_metrics():
    service = MDLRetrievalService()
    
    # Search for metrics
    results = await service.search_metrics_registry(
        query="vulnerability",
        limit=10
    )
    
    print(f"✓ Found {len(results)} metrics in registry")
    
    # Check if metrics have required fields
    for result in results[:3]:
        print(f"\nMetric: {result.metric_name}")
        print(f"  ID: {result.metric_id}")
        print(f"  Category: {result.category}")
        print(f"  Source capabilities: {result.source_capabilities}")

asyncio.run(check_metrics())
```

### 2. Verify Decision Tree Enrichment

```python
from app.agents.dt_workflow import get_detection_triage_app, create_dt_initial_state

app = get_detection_triage_app()
initial_state = create_dt_initial_state(
    user_query="SOC2 audit metrics for vulnerability management",
    session_id="verify-123",
    framework_id="soc2",
    selected_data_sources=["qualys"],
)
initial_state["dt_use_decision_tree"] = True

config = {"configurable": {"thread_id": "verify-thread"}}
final_state = app.invoke(initial_state, config)

# Check enrichment results
assert "dt_metric_decisions" in final_state, "Decision tree decisions not found"
assert "dt_scored_metrics" in final_state, "Scored metrics not found"
assert "dt_metric_groups" in final_state, "Metric groups not found"

decisions = final_state["dt_metric_decisions"]
print(f"✓ Decisions resolved: {decisions.get('use_case')}")
print(f"✓ Confidence: {decisions.get('auto_resolve_confidence', 0):.2f}")

scored = final_state["dt_scored_metrics"]
print(f"✓ Metrics scored: {len(scored)}")

groups = final_state["dt_metric_groups"]
print(f"✓ Groups created: {len(groups)}")
for group in groups:
    print(f"  - {group.get('group_name')}: {group.get('total_assigned', 0)} metrics")
```

### 3. Verify Workflow Integration

Check that both workflows have decision tree enrichment:

```python
# Check DT workflow
from app.agents.dt_nodes import dt_metrics_retrieval_node

# Check main workflow
from app.agents.nodes import metrics_recommender_node

# Both should call enrich_metrics_with_decision_tree
# Verify by checking the source code or running with logging
```

### 4. Verify Qdrant Collections

```python
from app.storage.qdrant_framework_store import _get_underlying_qdrant_client
from app.storage.collections import MDLCollections, FrameworkCollections

client = _get_underlying_qdrant_client()

# Check metrics collection
try:
    collection = client.get_collection(MDLCollections.METRICS_REGISTRY)
    print(f"✓ Metrics collection exists: {collection.points_count} points")
except Exception as e:
    print(f"✗ Metrics collection error: {e}")

# Check controls collection
try:
    collection = client.get_collection(FrameworkCollections.CONTROLS)
    print(f"✓ Controls collection exists: {collection.points_count} points")
except Exception as e:
    print(f"✗ Controls collection error: {e}")
```

---

## Troubleshooting

### Issue: No metrics found in search

**Symptoms:**
- `search_metrics_registry` returns empty results
- Workflow shows 0 resolved metrics

**Solutions:**
1. Verify metrics are indexed:
   ```bash
   python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/metrics
   ```

2. Check Qdrant connection:
   ```python
   from app.storage.qdrant_framework_store import _get_underlying_qdrant_client
   client = _get_underlying_qdrant_client()
   collections = client.get_collections()
   print([c.name for c in collections.collections])
   ```

3. Verify collection name matches:
   - Default: `leen_metrics_registry`
   - Check `MDLCollections.METRICS_REGISTRY`

### Issue: Decision tree enrichment not running

**Symptoms:**
- `dt_metric_decisions` is empty
- `dt_scored_metrics` is empty
- No groups created

**Solutions:**
1. Check flag is enabled:
   ```python
   state["dt_use_decision_tree"] = True  # Must be True
   ```

2. Verify metrics exist:
   ```python
   assert len(state.get("resolved_metrics", [])) > 0
   ```

3. Check logs for errors:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Issue: Controls not found

**Symptoms:**
- Control scoring fails
- No control evidence in metrics

**Solutions:**
1. Verify framework is ingested:
   ```bash
   python -m app.ingestion.ingest --framework soc2
   ```

2. Check controls collection:
   ```python
   from app.retrieval.service import RetrievalService
   service = RetrievalService()
   results = service.search_controls("vulnerability", framework_filter="soc2", limit=1)
   assert len(results.controls) > 0
   ```

### Issue: Workflow fails with import errors

**Symptoms:**
- `ImportError: cannot import name 'enrich_metrics_with_decision_tree'`
- Module not found errors

**Solutions:**
1. Verify Python path includes the project root
2. Check all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```
3. Verify file structure:
   ```
   app/
     agents/
       decision_trees/
         dt_metric_decision_nodes.py  # Must exist
   ```

### Issue: Low decision tree confidence

**Symptoms:**
- `auto_resolve_confidence < 0.6`
- Many unresolved decisions

**Solutions:**
1. Provide more context in user query:
   ```python
   user_query = "SOC2 Type II audit metrics for vulnerability management and compliance posture"
   ```

2. Set framework explicitly:
   ```python
   initial_state["framework_id"] = "soc2"
   ```

3. Provide focus areas:
   ```python
   initial_state["data_enrichment"] = {
       "suggested_focus_areas": ["vulnerability_management"]
   }
   ```

---

## Quick Reference

### Collection Names

- **Metrics Registry:** `leen_metrics_registry` (MDLCollections.METRICS_REGISTRY)
- **Framework Controls:** `framework_controls` (FrameworkCollections.CONTROLS)
- **Framework Risks:** `framework_risks` (FrameworkCollections.RISKS)
- **Framework Scenarios:** `framework_scenarios` (FrameworkCollections.SCENARIOS)

### State Fields (Decision Tree)

- `dt_use_decision_tree`: Enable/disable enrichment (default: True)
- `dt_metric_decisions`: Resolved decision values
- `dt_scored_metrics`: All metrics with composite scores
- `dt_metric_groups`: Grouped metric recommendations
- `dt_metric_coverage_report`: Coverage validation report
- `dt_metric_dropped`: Metrics below threshold

### Key Functions

- `enrich_metrics_with_decision_tree(state)`: Reusable enrichment tool
- `dt_metrics_retrieval_node(state)`: DT workflow metrics retrieval (with enrichment)
- `metrics_recommender_node(state)`: Main workflow metrics retrieval (with enrichment)

### Command Line Tools

```bash
# Index metrics
python -m app.ingestion.ingest_metrics_registry --metrics-dir /path/to/metrics

# Index frameworks
python -m app.ingestion.ingest --framework soc2

# Verify collections
python -c "from app.storage.qdrant_framework_store import _get_underlying_qdrant_client; client = _get_underlying_qdrant_client(); print([c.name for c in client.get_collections().collections])"
```

---

## Next Steps

After setup is complete:

1. **Test with real queries:** Run workflows with actual user queries
2. **Monitor performance:** Check decision tree confidence scores
3. **Tune thresholds:** Adjust scoring thresholds in `metric_scoring.py` if needed
4. **Add custom groups:** Extend `metric_grouping.py` with organization-specific groups
5. **Integrate LLM generation:** Enable `dt_use_llm_generation` for dynamic group generation (future)

---

## Support

For issues or questions:
- Check logs: `logging.basicConfig(level=logging.DEBUG)`
- Review code: `app/agents/decision_trees/dt_metric_decision_nodes.py`
- Check state: Inspect `final_state` after workflow execution
