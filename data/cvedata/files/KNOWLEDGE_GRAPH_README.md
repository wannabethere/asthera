# Knowledge Graph System for Vulnerability Analytics

## Overview

This system consists of two Python modules that work together to enable natural language to SQL query generation for vulnerability analytics:

1. **`kg_builder.py`** - Knowledge Graph Builder
2. **`kg_query_agent.py`** - Knowledge Graph Query Agent

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH SYSTEM                   │
└─────────────────────────────────────────────────────────────┘

Phase 1: BUILD KNOWLEDGE GRAPH
├─ Input: JSON Schema Files
│  ├─ assets_schema.json
│  ├─ vulnerability_instances_schema.json
│  ├─ software_instances_schema.json
│  └─ function_definitions.json
│
├─ Process: kg_builder.py
│  ├─ Parse entity schemas
│  ├─ Analyze attribute relationships
│  ├─ Discover calculation paths
│  ├─ Build dependency graph
│  └─ Store in ChromaDB
│
└─ Output: Knowledge Graph in ChromaDB
   ├─ Entity Schemas Collection
   ├─ Calculation Paths Collection
   ├─ Function Definitions Collection
   └─ Attribute Dependencies Collection

Phase 2: QUERY WITH AGENT
├─ Input: Natural Language Query
│  └─ "Which Mission Critical assets have CRITICAL vulnerabilities?"
│
├─ Process: kg_query_agent.py
│  ├─ Parse query intent
│  ├─ Search knowledge graph
│  ├─ Select calculation path
│  ├─ Plan query execution
│  └─ Generate SQL + Instructions
│
└─ Output: Query Instructions
   ├─ Generated SQL
   ├─ Step-by-step guide
   ├─ Chain of thought
   ├─ Required functions
   └─ Complexity estimates
```

---

## File 1: `kg_builder.py`

### Purpose
Reads JSON schema definitions and builds a comprehensive knowledge graph that encodes:
- Entity structures (Assets, Software, Vulnerabilities)
- Attribute relationships and dependencies
- Calculation paths (all ways to compute risk, exploitability, impact, etc.)
- Function call planning (which functions need which attributes)

### Key Classes

#### `EntitySchema`
Represents the schema of an entity with attributes grouped by category:
- Identifiers (nuid, dev_id, keys)
- Scores (risk scores, CVSS scores)
- Temporal (dates, dwell time, age)
- Network (IP, propagation class, bastion)
- CVSS Components (attack vector, complexity, etc.)
- Configuration (SMB, secure boot, policies)

#### `CalculationPath`
Represents a path from entity attributes to a calculated value:
- Source entity and attributes
- Target function to call
- Intermediate calculation steps
- Dependencies (entities, attributes, functions)
- SQL pattern for query generation

#### `FunctionDefinition`
Represents a SQL function:
- Parameters and return type
- Required attributes per entity
- Use cases and examples
- Parameter mapping to entity attributes

#### `AttributeDependency`
Tracks what each attribute enables:
- Which functions it enables
- Which calculations it enables
- What it depends on
- Metadata enrichment source

#### `KnowledgeGraphBuilder`
Main class that orchestrates the building process:
- Loads schemas from JSON
- Discovers calculation paths automatically
- Builds attribute dependency graph
- Stores everything in ChromaDB

### Input Format

The builder expects JSON schema files with this structure:

```json
{
  "entity_name": "Asset",
  "type": "entity",
  "description": "Physical or virtual computing resources",
  "primary_key": ["nuid", "dev_id"],
  "properties": {
    "nuid": {
      "type": "integer",
      "description": "Network unique identifier"
    },
    "effective_risk": {
      "type": "number",
      "description": "Effective risk score"
    },
    "attack_vector": {
      "type": "string",
      "description": "CVSS attack vector"
    }
  }
}
```

Function definitions JSON:

```json
{
  "functions": {
    "calculate_exploitability_score": {
      "description": "Calculate exploitability from CVSS components",
      "purpose": "Determine ease of exploitation",
      "parameters": [
        {
          "name": "p_attack_vector_weight",
          "type": "DECIMAL",
          "description": "Attack vector weight"
        }
      ],
      "return_type": "DECIMAL",
      "use_cases": ["Vulnerability prioritization"],
      "example_call": "calculate_exploitability_score(0.85, 0.77, 0.85, 0.85)",
      "required_attributes": {
        "Vulnerability": ["attack_vector", "attack_complexity", "privileges_required", "user_interaction"]
      }
    }
  }
}
```

### Usage

```python
from kg_builder import KnowledgeGraphBuilder

# Initialize builder
builder = KnowledgeGraphBuilder(persist_directory="./chromadb_kg")

# Load entity schemas
builder.load_entity_schema("assets_schema.json")
builder.load_entity_schema("vulnerability_instances_schema.json")
builder.load_entity_schema("software_instances_schema.json")

# Load function definitions
builder.load_function_definitions("function_definitions.json")

# Build calculation paths automatically
builder.build_calculation_paths()

# Build attribute dependencies
builder.build_attribute_dependencies()

# Store in ChromaDB
builder.store_knowledge_graph()

# Export summary
builder.export_graph_summary("kg_summary.json")
```

### Output

The builder creates 4 ChromaDB collections:

1. **`kg_entity_schemas`** - Entity definitions
2. **`kg_calculation_paths`** - All paths from entities to calculations
3. **`kg_function_definitions`** - SQL function metadata
4. **`kg_attribute_dependencies`** - Attribute relationship graph

---

## File 2: `kg_query_agent.py`

### Purpose
Uses the built knowledge graph to:
- Parse natural language queries
- Identify query intent and complexity
- Select optimal calculation paths
- Generate SQL queries with instructions
- Provide step-by-step execution guidance

### Key Classes

#### `QueryIntent`
Parsed understanding of a natural language query:
- Intent type (risk_analysis, vulnerability_assessment, etc.)
- Primary entity being queried
- Filters detected (severity, impact class, etc.)
- Aggregations (group by, order by, limit)
- Time windows
- Complexity level
- Confidence score

#### `CalculationStep`
Single step in a calculation plan:
- Step number and description
- Function to call
- Input attributes needed
- Output name
- SQL fragment
- Dependencies on other steps

#### `QueryPlan`
Complete execution plan:
- Selected calculation path
- Required entities and attributes
- Required functions
- SQL components (base table, joins, filters, etc.)
- Generated SQL query
- Explanation and chain of thought

#### `QueryInstruction`
Complete instruction set:
- Query plan
- Natural language instructions
- Step-by-step guide
- Alternative approaches
- Complexity and time estimates
- Required materialized views

#### `KnowledgeGraphQueryAgent`
Main class that orchestrates query processing:
- Parses natural language queries
- Searches knowledge graph for relevant paths
- Plans query execution
- Generates SQL and instructions
- Exports results

### Usage

```python
from kg_query_agent import KnowledgeGraphQueryAgent

# Initialize agent (reads from same ChromaDB as builder)
agent = KnowledgeGraphQueryAgent(kg_directory="./chromadb_kg")

# Process a natural language query
query = "Which Mission Critical assets have CRITICAL vulnerabilities with Network attack vectors?"

instruction = agent.generate_instructions(query)

# Access generated components
print("SQL:", instruction.query_plan.final_sql)
print("Instructions:", instruction.instructions)
print("Step-by-step:", instruction.step_by_step_guide)
print("Chain of thought:", instruction.query_plan.chain_of_thought)
print("Complexity:", instruction.estimated_complexity)
print("Execution time:", instruction.estimated_execution_time)

# Export to JSON
agent.export_instruction_to_json(instruction, "query_instruction.json")
```

### Query Parsing Capabilities

The agent can detect:

**Intent Types:**
- Risk analysis
- Vulnerability assessment
- Exploitability analysis
- Impact analysis
- Breach method analysis
- Time series trends
- Compliance queries
- Patch analysis

**Filters:**
- Severity (CRITICAL, HIGH, MEDIUM, LOW)
- Impact class (Mission Critical, Critical, Other)
- Propagation class (Perimeter, Core)
- State (ACTIVE, REMEDIATED, etc.)
- CISA Known Exploits
- Attack vectors (Network, Adjacent, Local, Physical)
- Patch availability
- Time windows (last 24 hours, 7 days, 30 days, 90 days)

**Aggregations:**
- Group by: asset, CVE, software, device type, etc.
- Order by: risk score, date, severity, etc.
- Limit: top 10, top 20, top 50, etc.

**Complexity Levels:**
- SIMPLE - Single entity, single function
- MODERATE - Multiple entities, single function
- COMPLEX - Multiple entities, multiple functions
- ADVANCED - Multi-hop paths, composite calculations

---

## Complete Workflow

### Step 1: Build Knowledge Graph (One-Time Setup)

```python
from kg_builder import KnowledgeGraphBuilder

# Initialize
builder = KnowledgeGraphBuilder("./chromadb_kg")

# Load your JSON schemas
builder.load_entity_schema("assets_schema.json")
builder.load_entity_schema("vulnerability_instances_schema.json")
builder.load_entity_schema("software_instances_schema.json")
builder.load_function_definitions("function_definitions.json")

# Build graph
builder.build_calculation_paths()
builder.build_attribute_dependencies()
builder.store_knowledge_graph()

print(f"Built {len(builder.calculation_paths)} calculation paths")
```

### Step 2: Query with Agent (Runtime)

```python
from kg_query_agent import KnowledgeGraphQueryAgent

# Initialize agent
agent = KnowledgeGraphQueryAgent("./chromadb_kg")

# Process queries
queries = [
    "Show me top 10 Mission Critical assets by risk score",
    "Which CRITICAL vulnerabilities have CISA exploits?",
    "Calculate exploitability scores for all active vulnerabilities",
    "What breach methods threaten Perimeter assets?",
    "Show vulnerability trends for the last 30 days"
]

for query in queries:
    instruction = agent.generate_instructions(query)
    
    print(f"\nQuery: {query}")
    print(f"SQL:\n{instruction.query_plan.final_sql}")
    print(f"Complexity: {instruction.estimated_complexity}")
    
    # Export
    agent.export_instruction_to_json(instruction, f"instruction_{i}.json")
```

---

## Output Examples

### Example 1: Simple Query

**Input:**
```
"Show me all CRITICAL vulnerabilities"
```

**Generated SQL:**
```sql
SELECT
    *
    , calculate_exploitability_score(...) as exploitability_score
FROM mv_enriched_vulnerability_instances vi
WHERE
    severity = 'CRITICAL'
    AND state = 'ACTIVE'
```

**Instructions:**
```
QUERY EXECUTION INSTRUCTIONS

Intent: vulnerability_assessment
Complexity: simple

CALCULATION PATH: Vulnerability → Exploitability Score

REQUIRED FUNCTIONS:
  - calculate_exploitability_score

REQUIRED ATTRIBUTES:
  - attack_vector
  - attack_complexity
  - privileges_required
  - user_interaction
```

### Example 2: Complex Query

**Input:**
```
"Which Mission Critical assets have CRITICAL vulnerabilities with Network attack vectors in the last 30 days?"
```

**Generated SQL:**
```sql
SELECT
    *
    , calculate_exploitability_score(...) as exploitability_score
    , calculate_impact_score(...) as impact_score
FROM mv_vulnerability_risk_scores vrs
JOIN assets a ON vrs.nuid = a.nuid AND vrs.dev_id = a.dev_id
WHERE
    severity = 'CRITICAL'
    AND impact_class = 'Mission Critical'
    AND attack_vector = 'N'
    AND detected_time >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY exploitability_score DESC
LIMIT 10
```

**Step-by-Step Guide:**
```
Step 1: Identify base data source
  → Use table/view: mv_vulnerability_risk_scores vrs

Step 2: Join related entities
  → Join 1: JOIN assets a ON vrs.nuid = a.nuid AND vrs.dev_id = a.dev_id

Step 3: Apply 4 filter conditions
  → Filter: severity = 'CRITICAL'
  → Filter: impact_class = 'Mission Critical'
  → Filter: attack_vector = 'N'
  → Filter: detected_time >= CURRENT_DATE - INTERVAL '30 days'

Step 4: Execute calculations
  → Calculate exploitability
    Function: calculate_exploitability_score
    Inputs: attack_vector, attack_complexity, privileges_required, user_interaction
    Output: exploitability_score

Step 5: Sort results
  → ORDER BY exploitability_score DESC

Step 6: Limit results
  → LIMIT 10
```

---

## Integration with Your SQL Framework

The system integrates with your existing SQL functions:

### Your Functions:
```sql
calculate_exploitability_score(av, ac, pr, ui) → DECIMAL
calculate_impact_score(c, i, a, s) → DECIMAL
calculate_breach_method_likelihood(...) → TABLE
calculate_time_weighted_stats(value, days, tau) → TABLE
```

### Your Materialized Views:
```sql
mv_enriched_vulnerability_instances
mv_vulnerability_risk_scores
mv_vulnerability_timeseries
mv_cve_timeseries_aggregates
mv_asset_breach_likelihood
```

### How It Works:

1. **Builder** reads your JSON schemas and creates a graph of:
   - Which attributes each entity has
   - Which attributes each function needs
   - All possible paths from entities → calculations

2. **Agent** uses the graph to:
   - Match natural language queries to calculation paths
   - Determine which functions to call
   - Select the right base tables and views
   - Generate SQL that uses your functions

---

## Key Features

### Automatic Path Discovery

The builder automatically discovers calculation paths by analyzing:
- Function parameter requirements
- Entity attribute availability
- Dependency chains
- Composite calculations

Example: It discovers that `Vulnerability` entity can calculate:
- Exploitability (has attack vector, complexity, privileges, UI)
- Impact (has C, I, A impacts and scope)
- Comprehensive risk (has both + temporal attributes)

### Semantic Search

ChromaDB enables semantic matching:
- "vulnerability risk" matches "CVE danger"
- "asset security posture" matches "device risk score"
- "attack difficulty" matches "exploitability"

### Multi-Path Support

Same query can have multiple execution paths:
- Direct calculation from entity
- Pre-computed from materialized view
- Composite from multiple functions

Agent selects optimal path based on:
- Data availability
- Query complexity
- Performance considerations

### Explainable AI

Every query comes with:
- Chain of thought reasoning
- Step-by-step execution plan
- Alternative approaches
- Complexity estimates
- Required resources

---

## Requirements

```
chromadb>=0.4.0
sentence-transformers>=2.2.0  # For embeddings
```

Install:
```bash
pip install chromadb sentence-transformers
```

---

## File Structure

```
vulnerability_analytics/
├── kg_builder.py                 # Knowledge graph builder
├── kg_query_agent.py             # Query agent
├── schemas/                      # Input JSON schemas
│   ├── assets_schema.json
│   ├── vulnerability_instances_schema.json
│   ├── software_instances_schema.json
│   └── function_definitions.json
├── chromadb_kg/                  # ChromaDB storage (created)
│   ├── kg_entity_schemas/
│   ├── kg_calculation_paths/
│   ├── kg_function_definitions/
│   └── kg_attribute_dependencies/
└── outputs/                      # Generated instructions (created)
    ├── knowledge_graph_summary.json
    ├── query_instruction_1.json
    ├── query_instruction_2.json
    └── ...
```

---

## Advanced Usage

### Custom Calculation Paths

Add custom composite calculations:

```python
# In kg_builder.py, extend _build_composite_paths()

custom_path = CalculationPath(
    path_id="asset_to_comprehensive_risk_with_forecast",
    path_name="Asset → Comprehensive Risk + Forecast",
    description="Calculate risk with 30-day forecast",
    calculation_type="comprehensive_risk_forecast",
    source_entity="Asset",
    intermediate_calculations=[
        {"step": 1, "function": "calculate_exploitability_score"},
        {"step": 2, "function": "calculate_impact_score"},
        {"step": 3, "function": "calculate_time_weighted_stats"},
        {"step": 4, "function": "gamma_distribution_forecast"}
    ],
    # ... rest of path definition
)
```

### Query Pattern Matching

Customize pattern detection in agent:

```python
# In kg_query_agent.py, extend _determine_intent_type()

intent_patterns = {
    "your_custom_intent": ["pattern1", "pattern2", "pattern3"]
}
```

### Export to Other Formats

Export knowledge graph to other systems:

```python
# Export to Neo4j
def export_to_neo4j(builder, neo4j_uri, credentials):
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(neo4j_uri, auth=credentials)
    
    with driver.session() as session:
        # Create entity nodes
        for entity_name, schema in builder.entity_schemas.items():
            session.run(
                "CREATE (e:Entity {name: $name, type: $type})",
                name=entity_name,
                type=schema.entity_type
            )
        
        # Create calculation path relationships
        for path in builder.calculation_paths:
            session.run(
                "MATCH (e:Entity {name: $source}) "
                "CREATE (e)-[:CALCULATES {function: $func}]->(:Calculation {name: $output})",
                source=path.source_entity,
                func=path.target_function,
                output=path.output_name
            )
```

---

## Performance Considerations

### Batch Loading
When loading large numbers of entities:

```python
# Load in batches to avoid memory issues
batch_size = 1000

for i in range(0, len(entities), batch_size):
    batch = entities[i:i + batch_size]
    # Process batch
```

### Caching
Cache frequently used paths:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_calculation_path(path_id: str):
    # Cached lookup
    pass
```

### Incremental Updates
Update graph incrementally:

```python
# Add new function without rebuilding entire graph
builder.function_definitions["new_function"] = new_func_def
new_paths = builder._build_paths_for_function(new_func_def)
builder.calculation_paths.extend(new_paths)
# Store only new paths
```

---

## Troubleshooting

### Issue: No calculation paths found

**Solution:** Check that:
1. Entity has required attributes
2. Function definitions specify correct attribute mappings
3. ChromaDB collections exist

### Issue: Low confidence scores

**Solution:** 
1. Add more query patterns to intent detection
2. Improve entity keyword matching
3. Add more example queries to ChromaDB

### Issue: Incorrect SQL generated

**Solution:**
1. Verify calculation path selection
2. Check base table mapping in agent
3. Review filter extraction logic

---

## Future Enhancements

Potential improvements:

1. **Learning from Feedback**
   - Store successful queries
   - Learn from corrections
   - Improve path selection

2. **Query Optimization**
   - Cost-based path selection
   - Index recommendations
   - View materialization suggestions

3. **Multi-Language Support**
   - Spanish, Chinese, etc.
   - Domain-specific terminology

4. **Visual Query Builder**
   - Interactive path selection
   - Visual calculation flow
   - Real-time preview

5. **Automated Testing**
   - Generate test queries
   - Validate SQL correctness
   - Performance benchmarking

---

## Conclusion

This two-file system provides:

✅ **Automatic knowledge graph building** from JSON schemas  
✅ **Semantic query understanding** via ChromaDB embeddings  
✅ **Intelligent SQL generation** with function planning  
✅ **Explainable query plans** with step-by-step guidance  
✅ **Extensible architecture** for custom calculations  

The system bridges natural language and SQL, making vulnerability analytics accessible while maintaining the power and flexibility of your existing SQL framework.
