# Contextual Agents - Generic and Reusable Architecture

This folder contains a generic, reusable architecture for context breakdown, edge pruning, and knowledge retrieval. The architecture supports both **MDL (semantic layer)** and **Compliance (risk management)** knowledge domains, with a planner that automatically decides which agents to use based on the user's query.

## Architecture Overview

### 1. Context Breakdown Agents

Context breakdown agents analyze user queries and extract relevant context information for knowledge retrieval.

#### Base Class: `BaseContextBreakdownAgent`
- Abstract base class for all context breakdown agents
- Provides common functionality:
  - Loading prompts from `vector_store_prompts.json`
  - LLM interaction
  - Query type detection
  - Entity identification

#### Specialized Implementations:

**`MDLContextBreakdownAgent`** - For MDL semantic layer queries
- Handles: Tables, relations, metrics, features, examples, histories, instructions, semantic information, use cases
- Detects: Table queries, relationship queries, column queries, category queries
- Edge types: `BELONGS_TO_TABLE`, `HAS_MANY_TABLES`, `REFERENCES_TABLE`, `HAS_FIELD`, etc.
- Knowledge elements: Tables, columns, relationships, categories, metrics, features

**`ComplianceContextBreakdownAgent`** - For compliance/risk management queries
- Handles: Frameworks, actors, compliance controls, evidences, requirements, features, keywords, topics, patterns
- Detects: Framework queries, control queries, evidence queries, risk queries, policy queries
- Edge types: `HAS_REQUIREMENT_IN_CONTEXT`, `PROVED_BY`, `RELEVANT_TO_CONTROL`, `MITIGATED_BY`, etc.
- Knowledge elements: Controls, requirements, evidences, policies, actors, frameworks

#### Context Breakdown Planner: `ContextBreakdownPlanner`
- **Intelligent routing**: Analyzes user question and decides which agent(s) to use
- **Decision logic**:
  - Use MDL agent only: Pure schema/table queries
  - Use Compliance agent only: Pure compliance/risk queries
  - Use both agents: Hybrid queries (e.g., "What tables are needed for SOC2 access control?")
- **Automatic combination**: Merges results when both agents are used

### 2. Edge Pruning Agents

Edge pruning agents select the most relevant edges from discovered edges using LLM-based semantic understanding.

#### Base Class: `BaseEdgePruningAgent`
- Abstract base class for all edge pruning agents
- Provides common functionality:
  - LLM interaction
  - Edge summarization
  - Domain-specific scoring

#### Specialized Implementations:

**`MDLEdgePruningAgent`** - For MDL-related edges
- Prioritizes table relationship edges for relationship queries
- Prioritizes field edges for column queries
- Understands MDL edge type semantics and cardinality
- Priority scoring based on query type

**`ComplianceEdgePruningAgent`** - For compliance/risk-related edges
- Prioritizes control/requirement edges for compliance queries
- Prioritizes evidence edges for audit queries
- Framework-aware scoring
- Risk assessment-aware scoring

### 3. Data Structure: `ContextBreakdown`

Generic data structure that works for both MDL and compliance queries:

```python
@dataclass
class ContextBreakdown:
    # Core fields (used by both)
    user_question: str
    query_type: str  # mdl, compliance, hybrid, etc.
    identified_entities: List[str]
    entity_types: List[str]
    search_questions: List[Dict[str, Any]]
    
    # Context-specific fields
    compliance_context: Optional[str]  # For compliance queries
    action_context: Optional[str]
    product_context: Optional[str]
    frameworks: List[str]
    
    # Evidence gathering (for deep research)
    evidence_gathering_required: bool
    evidence_types_needed: List[str]
    data_retrieval_plan: List[Dict[str, Any]]
    
    # Domain-specific metadata
    metadata: Dict[str, Any]
```

## Usage Examples

### Example 1: Pure MDL Query

```python
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()

# Pure MDL query
result = await planner.breakdown_question(
    user_question="What are the relationships from AccessRequest table to other tables in Snyk?",
    product_name="Snyk"
)

# Result:
# - plan["use_mdl"] = True
# - plan["use_compliance"] = False
# - mdl_breakdown contains table and relationship information
# - combined_breakdown = mdl_breakdown
```

### Example 2: Pure Compliance Query

```python
# Pure compliance query
result = await planner.breakdown_question(
    user_question="What are the SOC2 controls for access management?",
    available_frameworks=["SOC2", "HIPAA"]
)

# Result:
# - plan["use_mdl"] = False
# - plan["use_compliance"] = True
# - compliance_breakdown contains control and framework information
# - combined_breakdown = compliance_breakdown
```

### Example 3: Hybrid Query

```python
# Hybrid query (both MDL and compliance)
result = await planner.breakdown_question(
    user_question="What database tables do I need to query to gather evidence for SOC2 user access controls?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)

# Result:
# - plan["use_mdl"] = True
# - plan["use_compliance"] = True
# - Both mdl_breakdown and compliance_breakdown are populated
# - combined_breakdown merges both with query_type="hybrid"
```

## Knowledge Element Types

### MDL Knowledge Elements
- **Tables**: Database tables, schemas, models, entities
- **Relations**: Relationships between tables (belongs_to, has_many, references)
- **Metrics**: Calculations, aggregations, KPIs
- **Features**: Semantic features, data definitions
- **Examples**: Sample data, usage examples
- **Histories**: Change history, version information
- **Instructions**: Usage instructions, best practices
- **Use Cases**: Common use cases, patterns

**Note**: Currently, many MDL edges could be empty as the MDL knowledge graph is being populated.

### Compliance Knowledge Elements
- **Frameworks**: SOC2, HIPAA, ISO 27001, GDPR, NIST, PCI-DSS, etc.
- **Actors**: Compliance Officer, Auditor, CISO, Security Analyst, Risk Manager
- **Controls**: Compliance controls, security controls
- **Requirements**: Control requirements, mandates
- **Evidences**: Evidence types, proof, documentation
- **Features**: Compliance features, control implementations
- **Keywords**: Compliance keywords, topics
- **Topics**: Compliance topics, categories
- **Patterns**: Compliance patterns, best practices

## Store Types and Hybrid Search

The architecture keeps stores **generic with type** so that hybrid search continues to work across all knowledge domains:

### Generic Store Structure
```python
{
    "store_name": "contextual_edges",  # Generic store name
    "entity_type": "entity",           # Generic entity type
    "metadata": {
        "type": "mdl",                 # Domain-specific type
        "subtype": "table_relationship",
        "product_name": "Snyk",
        "framework": "SOC2"            # Optional compliance metadata
    }
}
```

### Hybrid Search Benefits
1. **Single search interface**: Use the same search API for both MDL and compliance
2. **Cross-domain queries**: Find connections between MDL and compliance (e.g., tables needed for compliance controls)
3. **Unified ranking**: Rank results across both domains
4. **Flexible filtering**: Filter by domain type, subtype, product, framework, etc.

## Edge Types Reference

### MDL Edge Types
- `BELONGS_TO_TABLE`: Many-to-one relationship
- `HAS_MANY_TABLES`: One-to-many relationship
- `REFERENCES_TABLE`: One-to-one reference
- `MANY_TO_MANY_TABLE`: Many-to-many relationship
- `LINKED_TO_TABLE`: General linked relationship
- `RELATED_TO_TABLE`: General related relationship
- `HAS_FIELD`: Table has field/column
- `RELEVANT_TO_CONTROL`: Table relevant to compliance control

### Compliance Edge Types
- `HAS_REQUIREMENT_IN_CONTEXT`: Control has requirement
- `PROVED_BY`: Requirement proved by evidence
- `RELEVANT_TO_CONTROL`: Entity relevant to control
- `MITIGATED_BY`: Risk mitigated by control
- `RELATED_TO_IN_CONTEXT`: General contextual relationship
- `HAS_EVIDENCE`: Control has evidence
- `APPLIES_TO`: Control applies to entity

## Integration Points

### With Existing Services
- **ContextualGraphService**: Main service for graph operations
- **EdgePruningService**: Legacy service (can be replaced by new agents)
- **ContextBreakdownService**: Legacy service (can be replaced by new agents)

### With Retrieval Agents
- The context breakdown results are used by retrieval agents to:
  1. Search for relevant entities using `search_questions`
  2. Filter results using `metadata_filters`
  3. Traverse edges based on `edge_types`
  4. Combine results from multiple stores

### With Reasoning Agents
- The context breakdown informs reasoning by:
  1. Identifying which knowledge domains are relevant
  2. Providing framework and product context
  3. Suggesting evidence gathering strategies
  4. Planning data retrieval steps

## Migration Path

The new agents coexist with the old agents during migration:

1. **Phase 1** (Current): New agents in `contextual_agents/` folder
   - Old agents remain in `agents/` folder
   - Both can be used simultaneously
   - Test new agents without breaking existing functionality

2. **Phase 2**: Gradual migration
   - Update services to use new agents
   - Run both old and new agents in parallel for validation
   - Compare results and fix any discrepancies

3. **Phase 3**: Complete migration
   - Remove old agents once new agents are fully tested
   - Update all references to use new agents
   - Archive old agents for reference

## Testing

To test the new agents:

```python
# Test MDL context breakdown
from app.agents.contextual_agents import MDLContextBreakdownAgent

mdl_agent = MDLContextBreakdownAgent()
breakdown = await mdl_agent.breakdown_question(
    user_question="What tables are related to AccessRequest in Snyk?",
    product_name="Snyk"
)
print(f"Identified entities: {breakdown.identified_entities}")
print(f"Search questions: {breakdown.search_questions}")

# Test Compliance context breakdown
from app.agents.contextual_agents import ComplianceContextBreakdownAgent

compliance_agent = ComplianceContextBreakdownAgent()
breakdown = await compliance_agent.breakdown_question(
    user_question="What are the SOC2 controls for access management?",
    available_frameworks=["SOC2"]
)
print(f"Frameworks: {breakdown.frameworks}")
print(f"Compliance context: {breakdown.compliance_context}")

# Test Context Breakdown Planner
from app.agents.contextual_agents import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()
result = await planner.breakdown_question(
    user_question="What database tables do I need for SOC2 user access evidence?",
    product_name="Snyk",
    available_frameworks=["SOC2"]
)
print(f"Plan: {result['plan']}")
print(f"Combined breakdown: {result['combined_breakdown']}")
```

## Future Enhancements

1. **Additional domain agents**: Create agents for other domains (risk, policy, etc.)
2. **Dynamic agent registration**: Allow new agents to be registered at runtime
3. **Agent orchestration**: Coordinate multiple agents for complex queries
4. **Learning and feedback**: Improve agent decisions based on user feedback
5. **Caching and optimization**: Cache breakdown results for common queries
6. **Multi-language support**: Support queries in multiple languages

## Contributing

When adding new domain agents:

1. Extend `BaseContextBreakdownAgent` for context breakdown
2. Extend `BaseEdgePruningAgent` for edge pruning
3. Update `ContextBreakdownPlanner` to recognize new domain
4. Add domain-specific prompts to `vector_store_prompts.json`
5. Document knowledge element types and edge types
6. Add tests for new agents
