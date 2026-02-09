# Data Assistance: Skip Deep Research Mode

## Overview

The Data Assistance workflow now supports a `skip_deep_research` flag that allows for simplified table retrieval without deep contextual edge analysis. This is useful when you just need table recommendations quickly without the full research workflow.

## Feature Description

When `skip_deep_research` is set to `True` in the request:

1. **MDL Reasoning** still runs to identify relevant tables and contexts
2. **Data Knowledge Retrieval** still retrieves full table schemas, metrics, and controls
3. **Deep Research Integration** is **skipped** (no contextual edge retrieval or evidence gathering)
4. **Table-Specific Reasoning** is **skipped** (no per-table insights generation)
5. **Metric Generation** still runs (if needed)
6. **Writer** still generates a comprehensive summary with the curated tables and descriptions

## Workflow Comparison

### Full Research Mode (default: `skip_deep_research=False`)

```
Intent → Context → MDL Reasoning → Data Knowledge → 
Deep Research → Table Reasoning → Metrics → Q&A/Executor → Writer → Finalize
```

### Simplified Mode (`skip_deep_research=True`)

```
Intent → Context → MDL Reasoning → Data Knowledge → 
[SKIP] → [SKIP] → Metrics → Q&A/Executor → Writer → Finalize
```

## Usage

### Python API

```python
from app.assistants import create_data_assistance_factory

# Create the data assistance graph
graph = await create_data_assistance_factory(...)

# Run with skip_deep_research flag
result = await graph.ainvoke({
    "query": "What tables are related to user access?",
    "project_id": "Snyk",
    "actor_type": "data_engineer",
    "skip_deep_research": True  # Enable simplified mode
})
```

### State Configuration

Add the flag to your initial state:

```python
state = {
    "query": "Find tables for compliance reporting",
    "project_id": "my_project",
    "skip_deep_research": True,  # Skip deep research
    "user_context": {
        "context_ids": ["soc2_compliance"]
    }
}
```

## Output Differences

### With `skip_deep_research=False` (Full Mode)
- Includes contextual edge analysis
- Provides evidence gathering plans
- Per-table insights and recommendations
- Identifies data gaps and feature requirements
- ~30-60 seconds execution time

### With `skip_deep_research=True` (Simplified Mode)
- Curated table list with descriptions
- Full table schemas (DDL + columns)
- Relationships between tables
- Relevant contexts and metrics
- Note in output indicating simplified mode
- ~10-20 seconds execution time

## State Fields Affected

When `skip_deep_research=True`:

**Present:**
- `mdl_curated_tables` - Curated tables from MDL reasoning
- `mdl_summary` - MDL reasoning summary
- `data_knowledge` - Full schemas, metrics, controls
- `generated_metrics` - Generated metrics (if any)

**Absent/Empty:**
- `deep_research_review` - Not generated
- `deep_research_edges` - Not retrieved
- `table_specific_reasoning` - Not performed

## Use Cases

### When to Use `skip_deep_research=True`

1. **Quick Table Lookup**
   - "What tables contain user data?"
   - "Show me tables for reporting"
   
2. **Initial Exploration**
   - Getting a high-level view of available tables
   - Understanding table relationships quickly

3. **Simple Recommendations**
   - Basic table suggestions without deep analysis
   - When you need fast responses

### When to Use `skip_deep_research=False` (Default)

1. **Evidence Gathering**
   - "Why is this control failing?"
   - "What data proves compliance?"

2. **Root Cause Analysis**
   - "Why are access metrics high?"
   - "Find the source of security issues"

3. **Comprehensive Research**
   - Need to understand contextual edges
   - Need per-table insights and recommendations
   - Need evidence gathering plans

## Implementation Details

### Graph Routing

The routing happens in `DataAssistanceGraphBuilder._route_after_data_knowledge()`:

```python
def _route_after_data_knowledge(self, state: Dict[str, Any]) -> str:
    skip_deep_research = state.get("skip_deep_research", False)
    
    if skip_deep_research:
        return "metric_generation"  # Skip to metrics
    else:
        return "deep_research"  # Continue with deep research
```

### State Model

Added to `ContextualAssistantState`:

```python
class ContextualAssistantState(TypedDict, total=False):
    ...
    skip_deep_research: bool  # If True, skip deep research and table-specific reasoning
    ...
```

### Writer Integration

The `WriterAgentNode` automatically detects when deep research was skipped and adds a note to the output:

```python
if skip_deep_research:
    deep_research_note = "\n\n**Note:** This is a simplified analysis focusing on table recommendations. Deep contextual edge analysis was not performed."
```

## Performance Impact

| Mode | Avg Time | LLM Calls | Use Case |
|------|----------|-----------|----------|
| Full Research | 30-60s | 8-12 | Comprehensive analysis |
| Simplified | 10-20s | 4-6 | Quick table lookup |

## Example

### Full Research Query

```python
result = await graph.ainvoke({
    "query": "Why are my SOC2 user access controls failing?",
    "project_id": "Snyk",
    "skip_deep_research": False  # Full research
})
# Output: Deep analysis with evidence, gaps, and recommendations
```

### Simplified Query

```python
result = await graph.ainvoke({
    "query": "What tables contain user access data?",
    "project_id": "Snyk",
    "skip_deep_research": True  # Simplified
})
# Output: Table list with schemas, faster response
```

## Best Practices

1. **Default to Full Mode** for analysis and evidence gathering queries
2. **Use Simplified Mode** for quick lookups and exploration
3. **Consider User Intent** - if they ask "why" or need evidence, use full mode
4. **Performance Trade-off** - simplified mode is 2-3x faster but less comprehensive
5. **Clear Communication** - the output indicates which mode was used

## Future Enhancements

Potential improvements:

1. **Auto-Detection**: Automatically choose mode based on query intent
2. **Hybrid Mode**: Allow partial deep research (e.g., edges only)
3. **Caching**: Cache deep research results for repeated queries
4. **Progressive Enhancement**: Start with simplified, expand to full if needed
