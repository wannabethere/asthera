# Implementation Summary: Generic Contextual Agents Architecture

## Overview

I've created a new generic and reusable architecture for context breakdown and edge pruning agents in the `app/agents/contextual_agents/` folder. This architecture provides a clean separation between **MDL (semantic layer)** knowledge and **Compliance (risk management)** knowledge, with an intelligent planner that automatically decides which agents to use based on the user's query.

## What Was Created

### 1. Core Components

#### Base Classes
- **`base_context_breakdown_agent.py`**: Abstract base class for context breakdown agents
  - Common functionality for loading prompts, LLM interaction, query type detection
  - Generic `ContextBreakdown` data structure that works for both MDL and compliance
  - Extensible for future domain agents

- **`base_edge_pruning_agent.py`**: Abstract base class for edge pruning agents
  - Common functionality for LLM interaction, edge summarization
  - Domain-specific scoring hooks
  - Reusable ranking methods

#### MDL Agents
- **`mdl_context_breakdown_agent.py`**: Specialized for MDL semantic layer queries
  - Handles: tables, relations, metrics, features, examples, histories, instructions, use cases
  - Detects: table queries, relationship queries, column queries, category queries
  - Uses LLM to intelligently detect table names and data categories
  - Edge types: `BELONGS_TO_TABLE`, `HAS_MANY_TABLES`, `REFERENCES_TABLE`, `HAS_FIELD`, etc.

- **`mdl_edge_pruning_agent.py`**: Specialized for MDL edge pruning
  - MDL-aware edge type semantics and priorities
  - Understands table relationship hierarchy
  - Boosts relevant edges based on query type (relationships, columns, etc.)

#### Compliance Agents
- **`compliance_context_breakdown_agent.py`**: Specialized for compliance/risk queries
  - Handles: frameworks, actors, controls, evidences, requirements, features, keywords, topics, patterns
  - Detects: framework queries, control queries, evidence queries, risk queries, policy queries
  - Automatically detects mentioned frameworks (SOC2, HIPAA, etc.) and actors
  - Edge types: `HAS_REQUIREMENT_IN_CONTEXT`, `PROVED_BY`, `RELEVANT_TO_CONTROL`, etc.

- **`compliance_edge_pruning_agent.py`**: Specialized for compliance edge pruning
  - Compliance-aware edge type priorities
  - Framework-specific scoring
  - Control and evidence prioritization

#### Intelligent Planner
- **`context_breakdown_planner.py`**: Decides which agent(s) to use
  - Analyzes user question using LLM
  - Determines if query is MDL, compliance, or hybrid
  - Routes to appropriate agent(s)
  - Automatically combines results from multiple agents
  - Returns unified breakdown with plan metadata

### 2. Data Structure

**Generic `ContextBreakdown`** class that works for both domains:
```python
@dataclass
class ContextBreakdown:
    # Core fields (used by both)
    user_question: str
    query_type: str  # "mdl", "compliance", "hybrid", "unknown"
    identified_entities: List[str]
    entity_types: List[str]
    search_questions: List[Dict[str, Any]]
    edge_types: List[str]
    
    # Context-specific fields
    compliance_context: Optional[str]
    action_context: Optional[str]
    product_context: Optional[str]
    frameworks: List[str]
    
    # Evidence gathering (for deep research)
    evidence_gathering_required: bool
    evidence_types_needed: List[str]
    data_retrieval_plan: List[Dict[str, Any]]
    metrics_kpis_needed: List[Dict[str, Any]]
    
    # Domain-specific metadata
    metadata: Dict[str, Any]
```

### 3. Documentation

- **`README.md`**: Comprehensive documentation
  - Architecture overview
  - Usage examples
  - Knowledge element types
  - Store types and hybrid search
  - Edge types reference
  - Integration points
  - Migration path
  - Future enhancements

- **`MIGRATION_GUIDE.md`**: Step-by-step migration guide
  - Overview of changes
  - Migration steps for each component
  - Key differences between old and new
  - Parallel testing strategies
  - Troubleshooting tips
  - Rollback plan
  - Timeline

- **`EXAMPLES.md`**: Practical usage examples
  - Basic usage
  - MDL queries (tables, relations, columns, metrics)
  - Compliance queries (controls, evidence, frameworks)
  - Hybrid queries
  - Edge pruning
  - Advanced usage
  - Testing tips
  - Performance tips

- **`IMPLEMENTATION_SUMMARY.md`**: This file

## Key Features

### 1. Intelligent Routing
The planner automatically determines which agent(s) to use:
```python
planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What tables are needed for SOC2 access control?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

# Automatically uses both MDL and compliance agents
# Returns: plan, mdl_breakdown, compliance_breakdown, combined_breakdown
```

### 2. Domain-Specific Knowledge

**MDL Knowledge**:
- Tables, relations, metrics, features
- Examples, histories, instructions, use cases
- Semantic information about data
- Currently many edges could be empty (being populated)

**Compliance Knowledge**:
- Frameworks (SOC2, HIPAA, ISO 27001, GDPR, etc.)
- Actors (Compliance Officer, Auditor, CISO, etc.)
- Controls, requirements, evidences
- Features for compliance
- Keywords, topics, patterns

### 3. Generic Store Structure
Stores are kept generic with "type" metadata for hybrid search:
```python
{
    "store_name": "contextual_edges",
    "entity_type": "entity",
    "metadata": {
        "type": "mdl",  # or "compliance"
        "subtype": "table_relationship",
        "product_name": "Snyk",
        "framework": "SOC2"
    }
}
```

### 4. Automatic Combination
When both agents are used, results are intelligently merged:
```python
combined_breakdown = ContextBreakdown(
    user_question=...,
    query_type="hybrid",
    identified_entities=[...],  # Merged from both
    search_questions=[...],     # Combined from both
    frameworks=[...],            # Merged from both
    metadata={
        "mdl_detection": {...},
        "compliance_detection": {...}
    }
)
```

## Usage

### Basic Example
```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls for access management?",
    available_frameworks=["SOC2"]
)

# Access the plan
plan = result["plan"]
print(f"Use MDL: {plan['use_mdl']}")  # False
print(f"Use Compliance: {plan['use_compliance']}")  # True
print(f"Query type: {plan['query_type']}")  # "compliance"

# Access the breakdown
breakdown = result["combined_breakdown"]
print(f"Frameworks: {breakdown.frameworks}")  # ["SOC2"]
print(f"Compliance context: {breakdown.compliance_context}")
```

### Hybrid Query Example
```python
result = await planner.breakdown_question(
    user_question="What database tables do I need to query to gather evidence for SOC2 user access controls?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

plan = result["plan"]
print(f"Query type: {plan['query_type']}")  # "hybrid"

# Access both breakdowns
mdl_breakdown = result["mdl_breakdown"]
compliance_breakdown = result["compliance_breakdown"]
combined = result["combined_breakdown"]

# Combined breakdown merges both
print(f"MDL entities: {mdl_breakdown.identified_entities}")
print(f"Compliance entities: {compliance_breakdown.identified_entities}")
print(f"Combined entities: {combined.identified_entities}")
```

## Benefits

### 1. Clear Separation of Concerns
- MDL agents handle only MDL knowledge
- Compliance agents handle only compliance knowledge
- No mixed concerns in a single agent

### 2. Intelligent Routing
- Planner automatically decides which agent(s) to use
- No manual decision logic needed
- Handles hybrid queries seamlessly

### 3. Extensible Architecture
- Easy to add new domain agents (risk, policy, etc.)
- Base classes provide common functionality
- Generic data structures work across domains

### 4. Hybrid Search Support
- Stores remain generic with type metadata
- Single search interface for all domains
- Cross-domain queries supported
- Unified ranking and filtering

### 5. Backward Compatible
- Old agents remain in `agents/` folder
- New agents coexist during migration
- Gradual migration path
- Feature flags for rollback

## Migration Path

### Phase 1 (Current): Coexistence
- New agents in `contextual_agents/` folder
- Old agents remain in `agents/` folder
- Both can be used simultaneously

### Phase 2: Testing
- Run both old and new agents in parallel
- Compare results and fix discrepancies
- Use feature flags for gradual rollout

### Phase 3: Migration
- Update services to use new agents
- Migrate one component at a time
- Keep old agents as fallback

### Phase 4: Cleanup
- Remove old agents once new agents tested
- Update all references
- Archive old agents for reference

## Next Steps

1. **Test the new agents**:
   ```bash
   # Create test file
   python -m pytest app/agents/contextual_agents/tests/
   ```

2. **Update existing services**:
   - Update `ContextualGraphRetrievalAgent` to use planner
   - Update `ContextualGraphReasoningAgent` to use planner
   - Add feature flags for gradual rollout

3. **Create integration tests**:
   - Test MDL queries
   - Test compliance queries
   - Test hybrid queries
   - Compare with old agents

4. **Document edge types**:
   - Add comprehensive edge type documentation
   - Document semantic meanings
   - Add examples for each type

5. **Populate MDL knowledge**:
   - Add table relationships
   - Add column definitions
   - Add metrics and features
   - Add examples and use cases

## File Structure

```
app/agents/contextual_agents/
├── __init__.py                              # Package exports
├── base_context_breakdown_agent.py         # Base class for context breakdown
├── mdl_context_breakdown_agent.py          # MDL-specific breakdown
├── compliance_context_breakdown_agent.py   # Compliance-specific breakdown
├── context_breakdown_planner.py            # Intelligent routing planner
├── base_edge_pruning_agent.py             # Base class for edge pruning
├── mdl_edge_pruning_agent.py              # MDL-specific edge pruning
├── compliance_edge_pruning_agent.py        # Compliance-specific edge pruning
├── README.md                               # Comprehensive documentation
├── MIGRATION_GUIDE.md                      # Step-by-step migration guide
├── EXAMPLES.md                             # Practical usage examples
└── IMPLEMENTATION_SUMMARY.md               # This file
```

## Notes

- **Old agents preserved**: All old agents remain in `app/agents/` folder
- **No breaking changes**: Existing code continues to work
- **Gradual migration**: Migrate at your own pace
- **Feature flags**: Use feature flags to enable/disable new agents
- **Testing**: Test thoroughly before removing old agents

## Questions or Issues?

1. Check the README.md for architecture overview
2. Check the EXAMPLES.md for usage examples
3. Check the MIGRATION_GUIDE.md for migration steps
4. Review test files for integration examples
5. Contact the team for assistance

## Summary

This new architecture provides:
- ✅ Clear separation between MDL and compliance domains
- ✅ Intelligent routing based on query type
- ✅ Reusable base classes for extensibility
- ✅ Generic data structures for hybrid search
- ✅ Automatic combination of results from multiple agents
- ✅ Comprehensive documentation and examples
- ✅ Backward compatible with gradual migration path
- ✅ Ready for testing and integration

The old agents remain untouched, allowing you to test and validate the new architecture before fully migrating.

pip install
opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp