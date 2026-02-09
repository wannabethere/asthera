# Usage Examples for Contextual Agents

This document provides practical examples of using the new contextual agents architecture.

## Table of Contents
1. [Basic Usage](#basic-usage)
2. [MDL Queries](#mdl-queries)
3. [Compliance Queries](#compliance-queries)
4. [Hybrid Queries](#hybrid-queries)
5. [Edge Pruning](#edge-pruning)
6. [Advanced Usage](#advanced-usage)

## Basic Usage

### Example 1: Simple Context Breakdown with Planner

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

# Initialize planner
planner = ContextBreakdownPlanner()

# Break down a question
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls for access management?"
)

# Access the plan
plan = result["plan"]
print(f"Use MDL: {plan['use_mdl']}")
print(f"Use Compliance: {plan['use_compliance']}")
print(f"Reasoning: {plan['reasoning']}")

# Access the combined breakdown
breakdown = result["combined_breakdown"]
print(f"Query type: {breakdown.query_type}")
print(f"Identified entities: {breakdown.identified_entities}")
print(f"Frameworks: {breakdown.frameworks}")
```

## MDL Queries

### Example 2: Pure MDL Query - Table Relationships

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()

# Query about table relationships
result = await planner.breakdown_question(
    user_question="What are the relationships from AccessRequest table to other tables in Snyk?",
    product_name="Snyk"
)

# Check the plan
plan = result["plan"]
assert plan["use_mdl"] == True
assert plan["use_compliance"] == False

# Access MDL breakdown
mdl_breakdown = result["mdl_breakdown"]
print(f"Query type: {mdl_breakdown.query_type}")  # Should be 'mdl'
print(f"Product context: {mdl_breakdown.product_context}")
print(f"Search questions: {mdl_breakdown.search_questions}")

# MDL-specific metadata
mdl_detection = mdl_breakdown.metadata.get("mdl_detection", {})
print(f"Is relationship query: {mdl_detection['query_type']['is_relationship_query']}")
print(f"Potential tables: {mdl_detection['potential_tables']}")
```

### Example 3: MDL Query - Column Information

```python
planner = ContextBreakdownPlanner()

result = await planner.breakdown_question(
    user_question="What columns are in the users table in Snyk?",
    product_name="Snyk"
)

mdl_breakdown = result["mdl_breakdown"]
mdl_detection = mdl_breakdown.metadata.get("mdl_detection", {})

# Check query type
assert mdl_detection['query_type']['is_column_query'] == True
print(f"Potential tables: {mdl_detection['potential_tables']}")
```

### Example 4: MDL Query - Metrics and Features

```python
planner = ContextBreakdownPlanner()

result = await planner.breakdown_question(
    user_question="What metrics are available for tracking user access in Snyk?",
    product_name="Snyk"
)

mdl_breakdown = result["mdl_breakdown"]

# Check for evidence gathering requirements
if mdl_breakdown.evidence_gathering_required:
    print(f"Evidence types needed: {mdl_breakdown.evidence_types_needed}")
    print(f"Data retrieval plan: {mdl_breakdown.data_retrieval_plan}")
    print(f"Metrics/KPIs needed: {mdl_breakdown.metrics_kpis_needed}")
```

## Compliance Queries

### Example 5: Pure Compliance Query - Controls

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()

# Query about compliance controls
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls for access management?",
    available_frameworks=["SOC2", "HIPAA"]
)

# Check the plan
plan = result["plan"]
assert plan["use_mdl"] == False
assert plan["use_compliance"] == True

# Access compliance breakdown
compliance_breakdown = result["compliance_breakdown"]
print(f"Query type: {compliance_breakdown.query_type}")  # Should be 'compliance'
print(f"Compliance context: {compliance_breakdown.compliance_context}")
print(f"Frameworks: {compliance_breakdown.frameworks}")
print(f"Action context: {compliance_breakdown.action_context}")

# Compliance-specific metadata
compliance_detection = compliance_breakdown.metadata.get("compliance_detection", {})
print(f"Is control query: {compliance_detection['query_type']['is_control_query']}")
print(f"Detected frameworks: {compliance_detection['detected_frameworks']}")
```

### Example 6: Compliance Query - Evidence

```python
planner = ContextBreakdownPlanner()

result = await planner.breakdown_question(
    user_question="What evidence is needed for SOC2 CC6.1 control?",
    available_frameworks=["SOC2"]
)

compliance_breakdown = result["compliance_breakdown"]
compliance_detection = compliance_breakdown.metadata.get("compliance_detection", {})

# Check query type
assert compliance_detection['query_type']['is_evidence_query'] == True
print(f"Frameworks: {compliance_breakdown.frameworks}")
print(f"Search questions: {compliance_breakdown.search_questions}")
```

### Example 7: Compliance Query - Actor-Specific

```python
planner = ContextBreakdownPlanner()

result = await planner.breakdown_question(
    user_question="What compliance tasks should the Compliance Officer perform for SOC2?",
    available_frameworks=["SOC2"],
    available_actors=["Compliance Officer", "Auditor", "CISO"]
)

compliance_breakdown = result["compliance_breakdown"]
compliance_detection = compliance_breakdown.metadata.get("compliance_detection", {})

# Check for actor mentions
print(f"Detected actors: {compliance_detection['detected_actors']}")
```

## Hybrid Queries

### Example 8: Hybrid Query - Compliance with Data

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()

# Query that requires both MDL and compliance knowledge
result = await planner.breakdown_question(
    user_question="What database tables do I need to query to gather evidence for SOC2 user access controls?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

# Check the plan
plan = result["plan"]
assert plan["use_mdl"] == True
assert plan["use_compliance"] == True
assert plan["query_type"] == "hybrid"

# Access both breakdowns
mdl_breakdown = result["mdl_breakdown"]
compliance_breakdown = result["compliance_breakdown"]

# Access combined breakdown
combined = result["combined_breakdown"]
assert combined.query_type == "hybrid"

print(f"MDL entities: {mdl_breakdown.identified_entities}")
print(f"Compliance entities: {compliance_breakdown.identified_entities}")
print(f"Combined entities: {combined.identified_entities}")

# Check evidence gathering requirements
if combined.evidence_gathering_required:
    print(f"Evidence types: {combined.evidence_types_needed}")
    print(f"Data retrieval plan: {combined.data_retrieval_plan}")
```

### Example 9: Hybrid Query - Compliance Controls for Specific Tables

```python
planner = ContextBreakdownPlanner()

result = await planner.breakdown_question(
    user_question="Which SOC2 controls apply to the AccessRequest table in Snyk?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

combined = result["combined_breakdown"]

# Both MDL and compliance information
print(f"Query type: {combined.query_type}")
print(f"Product context: {combined.product_context}")
print(f"Compliance context: {combined.compliance_context}")
print(f"Frameworks: {combined.frameworks}")

# Get both MDL and compliance search questions
print(f"Search questions: {len(combined.search_questions)}")
for question in combined.search_questions:
    print(f"  - Entity: {question['entity']}, Question: {question['question']}")
```

## Edge Pruning

### Example 10: MDL Edge Pruning

```python
from app.agents.contextual_agents import MDLEdgePruningAgent, ContextBreakdownPlanner
from app.services.contextual_graph_storage import ContextualEdge

# First, get context breakdown
planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What tables are related to AccessRequest in Snyk?",
    product_name="Snyk"
)
breakdown = result["combined_breakdown"]

# Assume we have discovered edges
discovered_edges = [...]  # List of ContextualEdge objects

# Prune edges using MDL agent
mdl_pruning_agent = MDLEdgePruningAgent()
pruned_edges = await mdl_pruning_agent.prune_edges(
    user_question="What tables are related to AccessRequest in Snyk?",
    discovered_edges=discovered_edges,
    max_edges=10,
    context_breakdown=breakdown.__dict__
)

print(f"Discovered: {len(discovered_edges)} edges")
print(f"Pruned to: {len(pruned_edges)} edges")

# Print pruned edges
for edge in pruned_edges:
    print(f"  - {edge.edge_type}: {edge.source_entity_id} -> {edge.target_entity_id}")
    print(f"    Relevance: {edge.relevance_score}")
```

### Example 11: Compliance Edge Pruning

```python
from app.agents.contextual_agents import ComplianceEdgePruningAgent, ContextBreakdownPlanner

# Get context breakdown
planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What are the SOC2 access control requirements?",
    available_frameworks=["SOC2"]
)
breakdown = result["combined_breakdown"]

# Assume we have discovered edges
discovered_edges = [...]  # List of ContextualEdge objects

# Prune edges using compliance agent
compliance_pruning_agent = ComplianceEdgePruningAgent()
pruned_edges = await compliance_pruning_agent.prune_edges(
    user_question="What are the SOC2 access control requirements?",
    discovered_edges=discovered_edges,
    max_edges=10,
    context_breakdown=breakdown.__dict__
)

# Print pruned edges
for edge in pruned_edges:
    print(f"  - {edge.edge_type}: {edge.source_entity_id} -> {edge.target_entity_id}")
    print(f"    Relevance: {edge.relevance_score}")
```

## Advanced Usage

### Example 12: Using Individual Agents Directly

```python
from app.agents.contextual_agents import MDLContextBreakdownAgent

# Use MDL agent directly (without planner)
mdl_agent = MDLContextBreakdownAgent()

breakdown = await mdl_agent.breakdown_question(
    user_question="What are the column definitions for AccessRequest table?",
    product_name="Snyk"
)

print(f"Query type: {breakdown.query_type}")
print(f"Search questions: {breakdown.search_questions}")
```

### Example 13: Custom LLM Configuration

```python
from app.agents.contextual_agents import ContextBreakdownPlanner
from langchain_openai import ChatOpenAI

# Create custom LLM
custom_llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,
    max_tokens=2000
)

# Create planner with custom LLM
planner = ContextBreakdownPlanner(llm=custom_llm)

result = await planner.breakdown_question(
    user_question="Complex query here...",
    product_name="Snyk"
)
```

### Example 14: Accessing Detailed Metadata

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls for database access in Snyk?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

combined = result["combined_breakdown"]

# Access MDL-specific metadata
if "mdl_detection" in combined.metadata:
    mdl_detection = combined.metadata["mdl_detection"]
    print(f"Is table query: {mdl_detection['query_type']['is_table_query']}")
    print(f"Is relationship query: {mdl_detection['query_type']['is_relationship_query']}")
    print(f"Detected products: {mdl_detection['detected_products']}")

# Access compliance-specific metadata
if "compliance_detection" in combined.metadata:
    compliance_detection = combined.metadata["compliance_detection"]
    print(f"Is control query: {compliance_detection['query_type']['is_control_query']}")
    print(f"Detected frameworks: {compliance_detection['detected_frameworks']}")
```

### Example 15: Iterating Through Search Questions

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What are the relationships and controls for AccessRequest table in Snyk?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

combined = result["combined_breakdown"]

# Iterate through all search questions
for i, question in enumerate(combined.search_questions):
    print(f"\nSearch Question {i+1}:")
    print(f"  Entity: {question.get('entity')}")
    print(f"  Question: {question.get('question')}")
    print(f"  Metadata filters: {question.get('metadata_filters')}")
    print(f"  Response type: {question.get('response_type')}")
```

### Example 16: Error Handling

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()

try:
    result = await planner.breakdown_question(
        user_question="What are the controls?",
        available_frameworks=["SOC2"]
    )
    
    # Check if breakdown was successful
    if result["combined_breakdown"].query_type == "error":
        print(f"Error in breakdown: {result['plan']['reasoning']}")
    else:
        # Process result
        breakdown = result["combined_breakdown"]
        print(f"Success! Query type: {breakdown.query_type}")
        
except Exception as e:
    print(f"Error: {str(e)}")
    # Handle error
```

## Testing Tips

### Tip 1: Compare Old vs New

```python
# Compare results from old and new agents
from app.services.context_breakdown_service import ContextBreakdownService
from app.agents.contextual_agents import ContextBreakdownPlanner

question = "What are the SOC2 controls?"

# Old way
old_service = ContextBreakdownService()
old_breakdown = await old_service.breakdown_question(
    user_question=question,
    available_frameworks=["SOC2"]
)

# New way
new_planner = ContextBreakdownPlanner()
new_result = await new_planner.breakdown_question(
    user_question=question,
    available_frameworks=["SOC2"]
)
new_breakdown = new_result["combined_breakdown"]

# Compare
print(f"Old entities: {old_breakdown.identified_entities}")
print(f"New entities: {new_breakdown.identified_entities}")
print(f"New query type: {new_breakdown.query_type}")
print(f"New search questions: {len(new_breakdown.search_questions)}")
```

### Tip 2: Validate Search Questions

```python
# Validate that search questions are well-formed
result = await planner.breakdown_question(...)
breakdown = result["combined_breakdown"]

for question in breakdown.search_questions:
    assert "entity" in question
    assert "question" in question
    assert "metadata_filters" in question
    assert isinstance(question["metadata_filters"], dict)
```

### Tip 3: Check Plan Decisions

```python
# Test planner decisions for different query types
test_queries = [
    "What tables are in Snyk?",  # Should use MDL only
    "What are the SOC2 controls?",  # Should use compliance only
    "What tables are needed for SOC2 access control?"  # Should use both
]

for query in test_queries:
    result = await planner.breakdown_question(user_question=query)
    plan = result["plan"]
    print(f"\nQuery: {query}")
    print(f"Use MDL: {plan['use_mdl']}, Use Compliance: {plan['use_compliance']}")
    print(f"Reasoning: {plan['reasoning']}")
```

## Performance Tips

### Tip 1: Reuse Planner Instance

```python
# Create planner once, reuse for multiple queries
planner = ContextBreakdownPlanner()

# Process multiple queries
queries = ["query1", "query2", "query3"]
for query in queries:
    result = await planner.breakdown_question(user_question=query)
    # Process result...
```

### Tip 2: Use Specific Agents When Type is Known

```python
# If you know it's an MDL query, use MDL agent directly
from app.agents.contextual_agents import MDLContextBreakdownAgent

mdl_agent = MDLContextBreakdownAgent()
breakdown = await mdl_agent.breakdown_question(
    user_question="Table-specific query",
    product_name="Snyk"
)
# No overhead of planner decision
```

### Tip 3: Cache Breakdown Results

```python
from functools import lru_cache
import hashlib

# Cache breakdown results for common queries
breakdown_cache = {}

async def get_cached_breakdown(user_question: str, **kwargs) -> dict:
    # Create cache key
    cache_key = hashlib.md5(
        f"{user_question}{json.dumps(kwargs, sort_keys=True)}".encode()
    ).hexdigest()
    
    if cache_key in breakdown_cache:
        return breakdown_cache[cache_key]
    
    # Not in cache, compute
    planner = ContextBreakdownPlanner()
    result = await planner.breakdown_question(
        user_question=user_question,
        **kwargs
    )
    
    breakdown_cache[cache_key] = result
    return result
```
