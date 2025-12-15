# Vulnerability Analytics Knowledge Graph System
## Complete Deliverables Summary

---

## 🎯 Project Overview

This deliverable provides a complete **Knowledge Graph System** for vulnerability analytics that enables:

1. **Automatic knowledge graph construction** from JSON schemas
2. **Natural language to SQL** query generation
3. **Intelligent function call planning** based on entity relationships
4. **Explainable query plans** with step-by-step guidance

---

## 📦 Deliverables

### **Core System (2 Python Files)**

#### 1. **`kg_builder.py`** (42 KB)
**Purpose:** Builds knowledge graph from JSON schemas

**What it does:**
- Reads entity schemas (Assets, Software, Vulnerabilities)
- Analyzes attribute relationships
- Discovers all calculation paths automatically
- Maps functions to required attributes
- Stores knowledge graph in ChromaDB

**Key Classes:**
- `EntitySchema` - Entity structure with attribute groups
- `CalculationPath` - Path from attributes → calculations
- `FunctionDefinition` - SQL function metadata
- `AttributeDependency` - Attribute relationship graph
- `KnowledgeGraphBuilder` - Main orchestrator

**Usage:**
```python
builder = KnowledgeGraphBuilder("./chromadb_kg")
builder.load_entity_schema("assets_schema.json")
builder.build_calculation_paths()
builder.store_knowledge_graph()
```

---

#### 2. **`kg_query_agent.py`** (34 KB)
**Purpose:** Uses knowledge graph to generate SQL from natural language

**What it does:**
- Parses natural language queries
- Identifies query intent and complexity
- Searches knowledge graph for relevant paths
- Selects optimal calculation approach
- Generates SQL with step-by-step instructions

**Key Classes:**
- `QueryIntent` - Parsed query understanding
- `CalculationStep` - Single calculation step
- `QueryPlan` - Complete execution plan
- `QueryInstruction` - Final instructions with SQL
- `KnowledgeGraphQueryAgent` - Main orchestrator

**Usage:**
```python
agent = KnowledgeGraphQueryAgent("./chromadb_kg")
instruction = agent.generate_instructions("Show me critical vulnerabilities")
print(instruction.query_plan.final_sql)
```

---

### **Documentation (3 Files)**

#### 3. **`KNOWLEDGE_GRAPH_README.md`** (20 KB)
**Complete user guide covering:**
- System architecture diagrams
- File-by-file explanations
- Complete workflow examples
- Input format specifications
- Output examples
- Integration with SQL framework
- Troubleshooting guide
- Future enhancements

---

#### 4. **`vulnerability_knowledge_graph_schema.md`** (45 KB)
**Theoretical knowledge graph schema:**
- 7 node types (Asset, Software, Vulnerability, etc.)
- 10 relationship types with SQL joins
- 10 pre-defined graph paths
- Query planning rules
- ChromaDB document structures
- Collection organization

**Earlier implementation reference** - more conceptual

---

#### 5. **`vulnerability_kg_implementation.py`** (43 KB)
**Earlier full implementation** with:
- Complete dataclass models
- ChromaDB integration
- 8 pre-defined graph paths as objects
- Query planner with semantic search
- Example usage code

**Note:** This is an earlier version; `kg_builder.py` and `kg_query_agent.py` are the refined production versions.

---

### **Configuration (1 File)**

#### 6. **`sample_json_configurations.json`** (24 KB)
**Complete sample configurations showing:**
- Asset schema JSON structure
- Vulnerability schema JSON structure
- Software schema JSON structure
- Function definitions JSON structure
- Materialized view metadata

**Use this as a template** for creating your own schema files.

---

### **SQL Framework (2 Files)**

#### 7. **`vulnerability_risk_calculations.sql`** (36 KB)
**Complete SQL implementation:**
- 11 major components
- 5 SQL functions
- 5 materialized views
- Time-weighted statistics with Gamma distribution
- Breach method likelihood calculations
- CVSS parsing and scoring

**Your existing SQL framework** that the knowledge graph references.

---

#### 8. **`vulnerability_sql_instructions.json`** (46 KB)
**20 example queries** with:
- Natural language questions
- Instructions for LLM
- Complete SQL queries
- Chain of thought reasoning

**Training data format** for text-to-SQL models.

---

### **Report Frameworks (2 Files)**

#### 9. **`enhanced_vulnerability_analytics_with_metadata.md`** (52 KB)
**Comprehensive report framework** with:
- 10 major report categories
- 100+ natural language questions
- Multi-dimensional analysis
- Time-weighted statistics
- Breach method attribution
- CVSS metric decomposition

---

#### 10. **`daily_reports_and_alerts_framework.md`** (74 KB)
**Operational framework** with:
- 6 daily management reports
- 4 executive reports
- 8 real-time alerts
- SQL queries for each
- Alert templates
- Integration patterns

---

## 🔄 System Workflow

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: BUILD KNOWLEDGE GRAPH (One-Time Setup)        │
└─────────────────────────────────────────────────────────┘

Input: JSON Schemas
  ├─ assets_schema.json
  ├─ vulnerability_instances_schema.json
  ├─ software_instances_schema.json
  └─ function_definitions.json

           ↓

    kg_builder.py
  ├─ Parse schemas
  ├─ Analyze relationships
  ├─ Discover paths
  └─ Store in ChromaDB

           ↓

Output: Knowledge Graph
  ├─ Entity Schemas (3 entities)
  ├─ Calculation Paths (10+ paths)
  ├─ Function Definitions (5 functions)
  └─ Attribute Dependencies (50+ dependencies)


┌─────────────────────────────────────────────────────────┐
│ PHASE 2: QUERY WITH AGENT (Runtime)                    │
└─────────────────────────────────────────────────────────┘

Input: Natural Language Query
  "Which Mission Critical assets have CRITICAL vulnerabilities?"

           ↓

  kg_query_agent.py
  ├─ Parse query intent
  ├─ Search knowledge graph
  ├─ Select calculation path
  ├─ Plan execution
  └─ Generate SQL

           ↓

Output: Query Instructions
  ├─ Generated SQL
  ├─ Step-by-step guide
  ├─ Chain of thought
  ├─ Function calls needed
  ├─ Complexity estimate
  └─ Execution time estimate
```

---

## 🎓 How to Use

### **Step 1: Prepare Your Schemas**

Create JSON files for your entities using `sample_json_configurations.json` as template:

```json
{
  "entity_name": "Asset",
  "type": "entity",
  "description": "Your description",
  "primary_key": ["nuid", "dev_id"],
  "properties": {
    "nuid": {"type": "integer", "description": "..."},
    "effective_risk": {"type": "number", "description": "..."}
  }
}
```

---

### **Step 2: Build Knowledge Graph**

```python
from kg_builder import KnowledgeGraphBuilder

builder = KnowledgeGraphBuilder("./chromadb_kg")

# Load schemas
builder.load_entity_schema("schemas/assets_schema.json")
builder.load_entity_schema("schemas/vulnerability_instances_schema.json")
builder.load_entity_schema("schemas/software_instances_schema.json")
builder.load_function_definitions("schemas/function_definitions.json")

# Build graph
builder.build_calculation_paths()
builder.build_attribute_dependencies()
builder.store_knowledge_graph()

print(f"Built {len(builder.calculation_paths)} calculation paths")
```

---

### **Step 3: Query with Agent**

```python
from kg_query_agent import KnowledgeGraphQueryAgent

agent = KnowledgeGraphQueryAgent("./chromadb_kg")

# Process query
query = "Show me top 10 Mission Critical assets by risk score"
instruction = agent.generate_instructions(query)

# Get results
print("SQL:", instruction.query_plan.final_sql)
print("Complexity:", instruction.estimated_complexity)
print("Functions:", instruction.query_plan.required_functions)

# Export
agent.export_instruction_to_json(instruction, "query_1.json")
```

---

## 💡 Key Features

### **Automatic Path Discovery**
The builder automatically discovers that:
- `Vulnerability` can calculate exploitability (has AV, AC, PR, UI)
- `Vulnerability` can calculate impact (has C, I, A, Scope)
- `Vulnerability` can calculate comprehensive risk (has both + time)

No manual path definition needed!

---

### **Semantic Query Understanding**
ChromaDB enables:
- "vulnerability risk" ≈ "CVE danger" ≈ "security threat"
- "Mission Critical assets" ≈ "critical systems"
- "attack difficulty" ≈ "exploitability"

---

### **Multi-Function Planning**
For complex queries like:
> "Calculate comprehensive risk for Mission Critical Perimeter assets with CISA exploits"

The agent plans:
1. Use `mv_vulnerability_risk_scores` (has pre-computed exploitability + impact)
2. Join with `assets` for impact/propagation class
3. Filter: impact_class='Mission Critical', propagation_class='Perimeter', has_cisa_exploit=TRUE
4. No additional functions needed (already in view)

---

### **Explainable Plans**
Every query comes with:
- **Chain of thought:** "1. Identified intent: risk_analysis, 2. Entity: Asset, 3. Filters: 4 conditions..."
- **Step-by-step:** "Step 1: Use mv_vulnerability_risk_scores, Step 2: Join assets..."
- **Alternative paths:** "Could also use: Asset → Breach Methods"
- **Estimates:** "Complexity: moderate, Time: 1-5 seconds"

---

## 📊 Example Query Processing

### **Input Query:**
```
"Which Mission Critical assets have CRITICAL vulnerabilities with Network attack vectors in the last 30 days?"
```

---

### **Agent Processing:**

**1. Parse Intent:**
- Intent: `vulnerability_assessment`
- Primary entity: `Asset`
- Filters detected: severity=CRITICAL, impact_class=Mission Critical, attack_vector=N, time_window=30 days
- Complexity: `COMPLEX`
- Confidence: 0.9

**2. Search Knowledge Graph:**
- Found 5 relevant paths
- Selected: `Asset → Comprehensive Risk`

**3. Generate Plan:**
- Base table: `mv_vulnerability_risk_scores vrs`
- Joins: `assets a`
- Functions: `calculate_exploitability_score()`, `calculate_impact_score()`
- Filters: 4 conditions
- Sort: by exploitability DESC
- Limit: 10

**4. Generate SQL:**
```sql
SELECT
    a.final_name,
    a.ip,
    vrs.cve_id,
    vrs.comprehensive_risk_score,
    vrs.exploitability_score
FROM mv_vulnerability_risk_scores vrs
JOIN assets a ON vrs.nuid = a.nuid AND vrs.dev_id = a.dev_id
WHERE
    vrs.severity = 'CRITICAL'
    AND a.impact_class = 'Mission Critical'
    AND vrs.attack_vector = 'N'
    AND vrs.detected_time >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY vrs.exploitability_score DESC
LIMIT 10
```

---

### **Output:**
```json
{
  "query": "Which Mission Critical assets...",
  "sql": "SELECT a.final_name, ...",
  "chain_of_thought": [
    "1. Identified intent: vulnerability_assessment",
    "2. Primary entity: Asset",
    "3. Extracted 4 filter conditions",
    "4. Selected path: Asset → Comprehensive Risk",
    "5. Functions: calculate_exploitability_score, calculate_impact_score",
    "6. Sort by exploitability DESC",
    "7. Limit to top 10"
  ],
  "estimated_complexity": "complex",
  "estimated_execution_time": "5-10 seconds",
  "required_functions": [
    "calculate_exploitability_score",
    "calculate_impact_score"
  ],
  "requires_materialized_views": [
    "mv_vulnerability_risk_scores"
  ]
}
```

---

## 🔗 Integration with Your SQL Framework

The knowledge graph references your existing SQL framework:

### **Your SQL Functions:**
- `calculate_exploitability_score(av, ac, pr, ui)`
- `calculate_impact_score(c, i, a, s)`
- `calculate_breach_method_likelihood(...)`
- `calculate_time_weighted_stats(value, days, tau)`

### **Your Materialized Views:**
- `mv_enriched_vulnerability_instances`
- `mv_vulnerability_risk_scores`
- `mv_asset_breach_likelihood`
- `mv_vulnerability_timeseries`

### **How It Works:**
1. Function definitions specify which attributes they need
2. Builder analyzes entity schemas to find matching attributes
3. Builder discovers paths: "Vulnerability has attack_vector → can call calculate_exploitability_score()"
4. Agent selects optimal view: "Query needs exploitability → use mv_vulnerability_risk_scores (pre-computed)"

---

## 📈 Statistics

### **Knowledge Graph Contents:**
- **Entities:** 3 (Asset, Vulnerability, Software)
- **Attributes:** 50+ per entity
- **Functions:** 5 SQL functions
- **Calculation Paths:** 10+ automatic paths
- **Dependencies:** 50+ attribute dependencies

### **File Sizes:**
- **Total deliverables:** 11 files, 451 KB
- **Core system:** 2 files, 76 KB (kg_builder + kg_query_agent)
- **Documentation:** 3 files, 108 KB
- **SQL framework:** 2 files, 82 KB

---

## 🚀 Next Steps

1. **Review** `KNOWLEDGE_GRAPH_README.md` for complete documentation
2. **Examine** `sample_json_configurations.json` for schema templates
3. **Create** your own JSON schemas based on your database
4. **Run** `kg_builder.py` to build your knowledge graph
5. **Test** `kg_query_agent.py` with sample queries
6. **Integrate** with your existing SQL framework

---

## 🎯 Key Innovations

### **1. Automatic Path Discovery**
No manual path definition - the builder discovers all calculation paths by analyzing:
- Function requirements
- Entity attributes
- Dependency chains

### **2. Semantic Query Understanding**
ChromaDB embeddings enable natural language flexibility:
- Synonyms automatically matched
- Context-aware entity detection
- Similar example retrieval

### **3. Multi-Function Planning**
Handles complex queries requiring multiple functions:
- Plans execution order
- Identifies dependencies
- Optimizes with materialized views

### **4. Explainable AI**
Every query includes:
- Chain of thought reasoning
- Step-by-step execution plan
- Alternative approaches
- Complexity estimates

---

## 📞 Support Resources

**Documentation Files:**
- `KNOWLEDGE_GRAPH_README.md` - Complete user guide
- `vulnerability_knowledge_graph_schema.md` - Theoretical schema
- `sample_json_configurations.json` - Configuration templates

**Example Files:**
- `vulnerability_sql_instructions.json` - 20 example queries
- `enhanced_vulnerability_analytics_with_metadata.md` - Report framework
- `daily_reports_and_alerts_framework.md` - Operational framework

**SQL Reference:**
- `vulnerability_risk_calculations.sql` - Complete SQL implementation

---

## ✅ Summary

This knowledge graph system provides:

✅ **Automatic knowledge graph construction** from JSON schemas  
✅ **Natural language to SQL** with semantic understanding  
✅ **Intelligent function call planning** based on entity analysis  
✅ **Explainable query plans** with step-by-step guidance  
✅ **Integration with existing SQL** functions and views  
✅ **Extensible architecture** for custom calculations  
✅ **Production-ready code** with comprehensive documentation  

The system bridges natural language and SQL while maintaining the full power and flexibility of your existing vulnerability analytics SQL framework. 🚀
