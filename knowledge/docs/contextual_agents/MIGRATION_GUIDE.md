# Migration Guide: Old Agents to New Contextual Agents

This guide explains how to migrate from the old agent architecture to the new generic contextual agents architecture.

## Overview of Changes

### Old Architecture
- **Location**: `app/agents/`
- **Files**:
  - `contextual_graph_reasoning_agent.py` - Compliance reasoning
  - `contextual_graph_retrieval_agent.py` - Compliance retrieval
  - `mdl_context_breakdown_agent.py` - MDL breakdown
  - `mdl_edge_pruning_agent.py` - MDL edge pruning
- **Limitations**:
  - Mixed concerns (MDL and compliance in same agents)
  - No intelligent routing between domains
  - Difficult to extend to new domains
  - Tight coupling between services

### New Architecture
- **Location**: `app/agents/contextual_agents/`
- **Files**:
  - `base_context_breakdown_agent.py` - Base class for context breakdown
  - `mdl_context_breakdown_agent.py` - MDL-specific breakdown
  - `compliance_context_breakdown_agent.py` - Compliance-specific breakdown
  - `context_breakdown_planner.py` - Intelligent routing planner
  - `base_edge_pruning_agent.py` - Base class for edge pruning
  - `mdl_edge_pruning_agent.py` - MDL-specific edge pruning
  - `compliance_edge_pruning_agent.py` - Compliance-specific edge pruning
- **Benefits**:
  - Clear separation of concerns
  - Intelligent routing based on query type
  - Easy to extend to new domains
  - Reusable base classes
  - Generic data structures that work across domains

## Migration Steps

### Step 1: Update Context Breakdown

**Old Code:**
```python
from app.services.context_breakdown_service import ContextBreakdownService

service = ContextBreakdownService()
breakdown = await service.breakdown_question(
    user_question="What are the SOC2 controls?",
    available_frameworks=["SOC2"]
)
```

**New Code:**
```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls?",
    available_frameworks=["SOC2"]
)

# Access the breakdown
breakdown = result["combined_breakdown"]
plan = result["plan"]  # Contains routing decision

# Check which agents were used
if plan["use_compliance"]:
    compliance_breakdown = result["compliance_breakdown"]
if plan["use_mdl"]:
    mdl_breakdown = result["mdl_breakdown"]
```

### Step 2: Update Edge Pruning

**Old Code (MDL):**
```python
from app.agents.mdl_edge_pruning_agent import MDLEdgePruningAgent

agent = MDLEdgePruningAgent()
pruned = await agent.prune_edges(
    user_question="What tables are related?",
    discovered_edges=edges,
    max_edges=10
)
```

**New Code (MDL):**
```python
from app.agents.contextual_agents import MDLEdgePruningAgent

agent = MDLEdgePruningAgent()
pruned = await agent.prune_edges(
    user_question="What tables are related?",
    discovered_edges=edges,
    max_edges=10,
    context_breakdown=breakdown.__dict__  # Pass context breakdown
)
```

**Old Code (Compliance):**
```python
from app.services.edge_pruning_service import EdgePruningService

service = EdgePruningService()
pruned = await service.prune_edges(
    user_question="What controls apply?",
    discovered_edges=edges,
    max_edges=10
)
```

**New Code (Compliance):**
```python
from app.agents.contextual_agents import ComplianceEdgePruningAgent

agent = ComplianceEdgePruningAgent()
pruned = await agent.prune_edges(
    user_question="What controls apply?",
    discovered_edges=edges,
    max_edges=10,
    context_breakdown=breakdown.__dict__
)
```

### Step 3: Update Retrieval Agents

**Old Code:**
```python
from app.agents.contextual_graph_retrieval_agent import ContextualGraphRetrievalAgent

retrieval_agent = ContextualGraphRetrievalAgent(
    contextual_graph_service=service
)

# Uses old context breakdown service internally
contexts = await retrieval_agent.retrieve_contexts(
    query="What are the SOC2 controls?",
    use_context_breakdown=True
)
```

**New Code:**
```python
from app.agents.contextual_graph_retrieval_agent import ContextualGraphRetrievalAgent
from app.agents.contextual_agents import ContextBreakdownPlanner

# Create planner
planner = ContextBreakdownPlanner()

# Get breakdown using planner
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls?",
    available_frameworks=["SOC2"]
)
breakdown = result["combined_breakdown"]

# Use retrieval agent with new breakdown
retrieval_agent = ContextualGraphRetrievalAgent(
    contextual_graph_service=service
)

# Pass the breakdown to retrieval agent
contexts = await retrieval_agent.retrieve_contexts(
    query="What are the SOC2 controls?",
    use_context_breakdown=False  # We already have breakdown
)
```

**Better Approach - Update retrieval agent to use planner:**
```python
# Update ContextualGraphRetrievalAgent constructor to accept planner
def __init__(
    self,
    contextual_graph_service: Any,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o-mini",
    collection_factory: Optional[Any] = None,
    context_breakdown_planner: Optional[ContextBreakdownPlanner] = None
):
    self.contextual_graph_service = contextual_graph_service
    self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
    self.collection_factory = collection_factory
    
    # Use new planner instead of old service
    if context_breakdown_planner:
        self.breakdown_planner = context_breakdown_planner
    else:
        from app.agents.contextual_agents import ContextBreakdownPlanner
        self.breakdown_planner = ContextBreakdownPlanner(llm=self.llm)
```

### Step 4: Update Reasoning Agents

**Old Code:**
```python
from app.agents.contextual_graph_reasoning_agent import ContextualGraphReasoningAgent

reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=service
)

# Uses old context breakdown service internally
result = await reasoning_agent.reason_with_context(
    query="What are the priority controls?",
    context_id="ctx_123",
    use_context_breakdown=True
)
```

**New Code:**
```python
from app.agents.contextual_graph_reasoning_agent import ContextualGraphReasoningAgent
from app.agents.contextual_agents import ContextBreakdownPlanner

# Create planner
planner = ContextBreakdownPlanner()

# Get breakdown using planner
result = await planner.breakdown_question(
    user_question="What are the priority controls?",
    available_frameworks=["SOC2"]
)
breakdown = result["combined_breakdown"]

# Use reasoning agent with new breakdown
reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=service
)

# Pass the breakdown to reasoning agent
result = await reasoning_agent.reason_with_context(
    query="What are the priority controls?",
    context_id="ctx_123",
    use_context_breakdown=False,  # We already have breakdown
    # You'll need to add a parameter to pass breakdown directly
    context_breakdown=breakdown
)
```

**Better Approach - Update reasoning agent to use planner:**
```python
# Update ContextualGraphReasoningAgent constructor to accept planner
def __init__(
    self,
    contextual_graph_service: Any,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    collection_factory: Optional[Any] = None,
    context_breakdown_planner: Optional[ContextBreakdownPlanner] = None
):
    self.contextual_graph_service = contextual_graph_service
    self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
    self.collection_factory = collection_factory
    
    # Use new planner instead of old service
    if context_breakdown_planner:
        self.breakdown_planner = context_breakdown_planner
    else:
        from app.agents.contextual_agents import ContextBreakdownPlanner
        self.breakdown_planner = ContextBreakdownPlanner(llm=self.llm)
```

## Key Differences

### 1. Context Breakdown

**Old:**
- Single service for all query types
- Returns `ContextBreakdown` object
- No intelligent routing

**New:**
- Separate agents for MDL and compliance
- Planner decides which agent(s) to use
- Returns dictionary with plan and breakdowns
- Can combine multiple breakdowns

### 2. Edge Pruning

**Old:**
- Generic edge pruning service
- Same logic for all edge types
- No domain-specific scoring

**New:**
- Separate agents for MDL and compliance
- Domain-specific scoring and prioritization
- Better understanding of edge semantics

### 3. Data Structure

**Old `ContextBreakdown`:**
```python
@dataclass
class ContextBreakdown:
    user_question: str
    compliance_context: Optional[str] = None
    action_context: Optional[str] = None
    product_context: Optional[str] = None
    frameworks: List[str] = None
    entity_types: List[str] = None
    # ... other fields
```

**New `ContextBreakdown`:**
```python
@dataclass
class ContextBreakdown:
    user_question: str
    query_type: str = "unknown"  # NEW: mdl, compliance, hybrid
    identified_entities: List[str] = field(default_factory=list)
    search_questions: List[Dict[str, Any]] = field(default_factory=list)  # NEW
    metadata: Dict[str, Any] = field(default_factory=dict)  # NEW: domain-specific metadata
    # ... all old fields still present
```

## Testing During Migration

### Parallel Testing

Run both old and new agents in parallel to compare results:

```python
from app.services.context_breakdown_service import ContextBreakdownService
from app.agents.contextual_agents import ContextBreakdownPlanner

# Old way
old_service = ContextBreakdownService()
old_breakdown = await old_service.breakdown_question(
    user_question="What are the SOC2 controls?",
    available_frameworks=["SOC2"]
)

# New way
new_planner = ContextBreakdownPlanner()
new_result = await new_planner.breakdown_question(
    user_question="What are the SOC2 controls?",
    available_frameworks=["SOC2"]
)
new_breakdown = new_result["combined_breakdown"]

# Compare results
print(f"Old identified entities: {old_breakdown.identified_entities}")
print(f"New identified entities: {new_breakdown.identified_entities}")
print(f"Query type: {new_breakdown.query_type}")
print(f"Plan: {new_result['plan']}")
```

### Feature Flags

Use feature flags to gradually roll out new agents:

```python
from app.config import settings

if settings.USE_NEW_CONTEXTUAL_AGENTS:
    from app.agents.contextual_agents import ContextBreakdownPlanner
    planner = ContextBreakdownPlanner()
    result = await planner.breakdown_question(...)
    breakdown = result["combined_breakdown"]
else:
    from app.services.context_breakdown_service import ContextBreakdownService
    service = ContextBreakdownService()
    breakdown = await service.breakdown_question(...)
```

## Troubleshooting

### Issue: Missing search_questions attribute

**Error:**
```python
AttributeError: 'ContextBreakdown' object has no attribute 'search_questions'
```

**Solution:**
The new `ContextBreakdown` includes `search_questions` by default, but if using old breakdown objects, add it manually:
```python
if not hasattr(breakdown, 'search_questions'):
    breakdown.search_questions = []
```

### Issue: Different query_type values

**Old:** No `query_type` field
**New:** `query_type` can be "mdl", "compliance", "hybrid", "unknown"

**Solution:**
Handle both old and new:
```python
query_type = getattr(breakdown, 'query_type', 'unknown')
if query_type == 'unknown':
    # Use old logic to infer type
    if breakdown.compliance_context:
        query_type = 'compliance'
```

### Issue: Planner returns different structure

**Old:**
```python
breakdown = await service.breakdown_question(...)
# Returns ContextBreakdown directly
```

**New:**
```python
result = await planner.breakdown_question(...)
# Returns dict with plan, mdl_breakdown, compliance_breakdown, combined_breakdown
breakdown = result["combined_breakdown"]
```

**Solution:**
Use a wrapper function:
```python
async def get_breakdown(user_question: str, **kwargs) -> ContextBreakdown:
    planner = ContextBreakdownPlanner()
    result = await planner.breakdown_question(user_question, **kwargs)
    return result["combined_breakdown"]
```

## Rollback Plan

If issues arise, you can easily rollback to old agents:

1. **Keep old imports**: Keep old service imports in code
2. **Feature flag**: Use feature flag to switch between old and new
3. **Gradual migration**: Migrate one component at a time
4. **Test thoroughly**: Test each component before moving to next

## Timeline

**Phase 1** (Weeks 1-2): Set up new agents
- ✅ Create base classes
- ✅ Implement MDL and compliance agents
- ✅ Create planner
- ✅ Write tests

**Phase 2** (Weeks 3-4): Parallel testing
- Run both old and new agents in parallel
- Compare results
- Fix any discrepancies
- Add feature flags

**Phase 3** (Weeks 5-6): Gradual migration
- Migrate context breakdown first
- Then migrate edge pruning
- Then migrate retrieval agents
- Finally migrate reasoning agents

**Phase 4** (Week 7): Cleanup
- Remove old agents
- Update documentation
- Remove feature flags

## Support

For questions or issues during migration:
1. Check the README.md in `contextual_agents/` folder
2. Review the test files for examples
3. Contact the team for assistance
