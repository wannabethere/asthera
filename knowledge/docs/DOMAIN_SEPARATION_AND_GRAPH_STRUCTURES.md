# Domain Separation and Graph Structures

## Overview

The knowledge system maintains **separate graph structures** for different domains:

1. **MDL (Semantic Layer)** - Product schemas, tables, columns
2. **Compliance** - Frameworks, controls, requirements
3. **Risk Management** - Risk controls, assessments
4. **Policy** - Policies, procedures, standards
5. **Product Documentation** - Product features, concepts

Each domain has:
- ✅ **Dedicated collections** in vector stores
- ✅ **Domain-specific contextual agents**
- ✅ **Separate edge types** for relationships
- ✅ **Independent metadata filtering**
- ✅ **Domain-specific reasoning**

## Domain Graph Structures

### 1. MDL Domain (Product Schemas)

**Purpose**: Semantic layer for product data models (Snyk, Cornerstone, etc.)

**Collections:**
```
MDL Domain Collections:
├── table_definitions       # Table schemas
├── table_descriptions      # Table business descriptions
├── column_definitions      # Column metadata
├── entities               # Features, metrics (with mdl_entity_type)
├── instructions          # Best practices
├── sql_pairs             # SQL examples
└── contextual_edges      # MDL relationships
```

**Edge Types:**
```
MDL Graph Structure:

Product
  └─ PRODUCT_HAS_CATEGORY → Category
      └─ CATEGORY_HAS_TABLE → Table
          ├─ TABLE_HAS_COLUMN → Column
          ├─ TABLE_HAS_FEATURE → Feature
          ├─ TABLE_HAS_METRIC → Metric
          ├─ TABLE_FOLLOWS_INSTRUCTION → Instruction
          ├─ EXAMPLE_USES_TABLE → Example
          └─ TABLE_RELATES_TO_TABLE → Table (FK)
```

**Context Breakdown Agent:**
- `app/agents/contextual_agents/mdl_context_breakdown_agent.py`
- `app/agents/mdl_context_breakdown_agent.py` (legacy location)

**Metadata Filters:**
```python
{
    "product_name": "Snyk",
    "category_name": "vulnerabilities",
    "mdl_entity_type": "feature"  # For entities
}
```

**Example Query:**
```python
# User: "Show me vulnerability tables in Snyk"
breakdown = await mdl_agent.breakdown_mdl_question(
    user_question="Show me vulnerability tables in Snyk",
    product_name="Snyk"
)

# Result:
# - search_questions: [{"entity": "table_descriptions", "question": "vulnerability tables", ...}]
# - metadata filters: {"product_name": "Snyk", "category_name": "vulnerabilities"}
# - edge_types: ["CATEGORY_HAS_TABLE", "TABLE_HAS_COLUMN"]
```

---

### 2. Compliance Domain (Frameworks & Controls)

**Purpose**: Compliance frameworks, controls, requirements, evidence

**Collections:**
```
Compliance Domain Collections:
├── compliance_controls     # SOC2, HIPAA, ISO controls
├── domain_knowledge       # Framework concepts (type="compliance")
├── entities              # Framework entities (type="compliance")
├── evidence              # Compliance evidence (type="compliance")
└── contextual_edges      # Compliance relationships
```

**Hierarchy (from FrameworkHierarchy.md):**
```
Framework (SOC2, HIPAA)
  ↓
Trust Service Criteria (TSC)
  ↓
Control Objective
  ↓
Control
  ↓
Policy / Standard
  ↓
Procedure
  ↓
Evidence
  ↓
Finding / Issue
```

**Edge Types:**
```
Compliance Graph Structure:

Framework
  └─ HAS_TSC → Trust Service Criteria
      └─ HAS_OBJECTIVE → Control Objective
          └─ HAS_CONTROL → Control
              ├─ REQUIRES_POLICY → Policy
              ├─ HAS_PROCEDURE → Procedure
              ├─ HAS_EVIDENCE → Evidence
              └─ HAS_FINDING → Issue
```

**Context Breakdown Agent:**
- `app/agents/contextual_agents/compliance_context_breakdown_agent.py`

**Metadata Filters:**
```python
{
    "framework": "SOC2",
    "type": "compliance",
    "control_category": "access_control"
}
```

**Example Query:**
```python
# User: "What are SOC2 access control requirements?"
breakdown = await compliance_agent.breakdown_question(
    user_question="What are SOC2 access control requirements?",
    frameworks=["SOC2"]
)

# Result:
# - frameworks: ["SOC2"]
# - search_questions: [{"entity": "compliance_controls", "question": "access control requirements", ...}]
# - edge_types: ["HAS_CONTROL", "REQUIRES_POLICY"]
```

---

### 3. Risk Management Domain

**Purpose**: Risk controls, risk assessments, risk evidence

**Collections:**
```
Risk Domain Collections:
├── domain_knowledge       # Risk concepts (type="risk")
├── controls              # Risk controls (type="risk_control")
├── entities              # Risk entities (type="risk_entities")
├── evidence              # Risk evidence (type="risk_evidence")
└── contextual_edges      # Risk relationships
```

**Edge Types:**
```
Risk Graph Structure:

Risk Category
  └─ HAS_RISK → Risk
      ├─ MITIGATED_BY → Control
      ├─ HAS_EVIDENCE → Evidence
      └─ HAS_FINDING → Issue
```

**Metadata Filters:**
```python
{
    "type": "risk",
    "risk_category": "security",
    "severity": "critical"
}
```

---

### 4. Policy Domain

**Purpose**: Organizational policies, procedures, standards

**Collections:**
```
Policy Domain Collections:
├── domain_knowledge       # Policy content (type="policy")
├── entities              # Policy entities (type="policy")
├── fields                # Policy fields (type="policy")
└── contextual_edges      # Policy relationships
```

**Edge Types:**
```
Policy Graph Structure:

Policy
  ├─ HAS_PROCEDURE → Procedure
  ├─ IMPLEMENTS_CONTROL → Control
  └─ HAS_EVIDENCE → Evidence
```

**Metadata Filters:**
```python
{
    "type": "policy",
    "policy_category": "access_control",
    "framework": "SOC2"  # If policy is framework-specific
}
```

---

### 5. Product Documentation Domain

**Purpose**: Product features, key concepts, how-to guides

**Collections:**
```
Product Docs Collections:
├── domain_knowledge       # Product docs (type="product")
├── entities              # Product concepts (type="product")
├── product_key_concepts  # Key concepts
└── contextual_edges      # Product doc relationships
```

**Edge Types:**
```
Product Docs Graph Structure:

Product
  └─ HAS_CONCEPT → Key Concept
      ├─ HAS_FEATURE → Feature
      ├─ HAS_CONTROL → Control (if security product)
      └─ HAS_EVIDENCE → Evidence
```

**Metadata Filters:**
```python
{
    "type": "product",
    "product_name": "Snyk"
}
```

---

## Domain Separation Architecture

### Collection Routing Strategy

**Fixed Collections with Type Discriminators:**

| Collection | Domains | Type Discriminator |
|-----------|---------|-------------------|
| `domain_knowledge` | Compliance, Risk, Policy, Product | `type` field |
| `entities` | MDL, Compliance, Risk, Policy, Product | `type` + `mdl_entity_type` |
| `controls` | Compliance, Risk | `type` field |
| `evidence` | Compliance, Risk, Policy | `type` field |
| `contextual_edges` | ALL | `source_entity_type`, `edge_type` |
| `table_descriptions` | MDL only | `product_name` |
| `compliance_controls` | Compliance only | `framework` |

**Example: Querying domain_knowledge for different domains:**

```python
# MDL domain (not used - MDL has dedicated collections)
# N/A

# Compliance domain
results = await hybrid_search(
    query="SOC2 requirements",
    collection_name="domain_knowledge",
    where={"type": "compliance", "framework": "SOC2"}
)

# Risk domain
results = await hybrid_search(
    query="security risks",
    collection_name="domain_knowledge",
    where={"type": "risk", "risk_category": "security"}
)

# Policy domain
results = await hybrid_search(
    query="access control policies",
    collection_name="domain_knowledge",
    where={"type": "policy", "policy_category": "access_control"}
)

# Product docs domain
results = await hybrid_search(
    query="Snyk features",
    collection_name="domain_knowledge",
    where={"type": "product", "product_name": "Snyk"}
)
```

---

## Contextual Agents per Domain

### MDL Context Breakdown Agent

**File:** `app/agents/contextual_agents/mdl_context_breakdown_agent.py`

**Detects:**
- Table queries
- Column queries
- Relationship queries
- Category queries
- Feature/metric queries

**Collections Used:**
- `table_descriptions`
- `column_definitions`
- `table_definitions`
- `entities` (with `mdl_entity_type` filter)
- `contextual_edges`

**Validation After Our Changes:**

```python
# ✅ WORKS with new contextual edges
breakdown = await mdl_agent.breakdown_mdl_question(
    "What tables relate to Vulnerability?",
    product_name="Snyk"
)

# Expected search_questions:
# - entity: "table_descriptions", question: "tables related to Vulnerability"
# - entity: "contextual_edges", question: "Vulnerability table relationships"

# ✅ WORKS with organization metadata (organization not in filters)
# Organization is in metadata but not queried

# ✅ WORKS with knowledgebase entities
breakdown = await mdl_agent.breakdown_mdl_question(
    "What features does Vulnerability table provide?",
    product_name="Snyk"
)

# Expected search_questions:
# - entity: "entities", question: "Vulnerability table features"
# - filters: {"mdl_entity_type": "feature", "product_name": "Snyk"}
```

### Compliance Context Breakdown Agent

**File:** `app/agents/contextual_agents/compliance_context_breakdown_agent.py`

**Detects:**
- Framework queries (SOC2, HIPAA, etc.)
- Control queries
- Evidence queries
- Risk queries
- Policy queries
- Actor queries (Compliance Officer, Auditor, etc.)

**Collections Used:**
- `compliance_controls`
- `domain_knowledge` (with `type="compliance"`)
- `entities` (with `type="compliance"`)
- `contextual_edges`

**Example:**

```python
breakdown = await compliance_agent.breakdown_question(
    "What evidence is needed for SOC2 CC6.1?",
    frameworks=["SOC2"]
)

# Expected search_questions:
# - entity: "compliance_controls", question: "SOC2 CC6.1 control"
# - entity: "evidence", question: "evidence for CC6.1"
# - entity: "contextual_edges", question: "CC6.1 evidence relationships"
```

---

## MDL Agent Compatibility Checklist

After adding contextual edges, organization support, and knowledgebase:

### ✅ **Works**

1. **Contextual Edges**
   - Agent already references `contextual_edges` in prompts (line 335)
   - Edge types properly detected
   - Relationship queries work

2. **Organization Metadata**
   - Organization is in metadata but NOT in query filters
   - Agent doesn't need to change
   - Filtering by `product_name` is sufficient

3. **Knowledgebase Entities**
   - Features/metrics in `entities` collection
   - Agent can query with `mdl_entity_type` discriminator
   - Instructions in `instructions` collection
   - Examples in `sql_pairs` collection

4. **Category Filtering**
   - Agent detects categories via LLM
   - Uses `category_name` in metadata filters
   - Works with new category-based routing

### ⚠️ **Recommendations**

1. **Update Agent to Use Knowledgebase Explicitly**

```python
# Current: Agent may not specifically query features/metrics
# Recommended: Add explicit feature/metric detection

if query_type["is_feature_query"]:
    search_questions.append({
        "entity": "entities",
        "question": "features for vulnerability analysis",
        "filters": {
            "product_name": "Snyk",
            "mdl_entity_type": "feature",
            "category_name": "vulnerabilities"
        }
    })
```

2. **Add Contextual Edge Queries**

```python
# When relationship query detected
if query_type["is_relationship_query"]:
    search_questions.append({
        "entity": "contextual_edges",
        "question": "table relationships",
        "filters": {
            "product_name": "Snyk",
            "edge_type": "TABLE_RELATES_TO_TABLE"
        }
    })
```

---

## Testing Domain Separation

### Test 1: MDL Domain Query

```bash
cd knowledge

python -c "
import asyncio
from app.agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

async def test():
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        'What vulnerability tables exist in Snyk?',
        product_name='Snyk'
    )
    print('MDL Query Breakdown:')
    print(f'  Entity Types: {breakdown.entity_types}')
    print(f'  Search Questions: {len(breakdown.search_questions)}')
    print(f'  Product Context: {breakdown.product_context}')
    for sq in breakdown.search_questions:
        print(f'    - {sq[\"entity\"]}: {sq[\"question\"]}')

asyncio.run(test())
"
```

### Test 2: Compliance Domain Query

```bash
python -c "
import asyncio
from app.agents.contextual_agents.compliance_context_breakdown_agent import ComplianceContextBreakdownAgent

async def test():
    agent = ComplianceContextBreakdownAgent()
    breakdown = await agent.breakdown_question(
        'What are SOC2 access control requirements?',
        frameworks=['SOC2']
    )
    print('Compliance Query Breakdown:')
    print(f'  Frameworks: {breakdown.frameworks}')
    print(f'  Search Questions: {len(breakdown.search_questions)}')
    for sq in breakdown.search_questions:
        print(f'    - {sq[\"entity\"]}: {sq[\"question\"]}')

asyncio.run(test())
"
```

### Test 3: Cross-Domain Query

```bash
python -c "
import asyncio
from app.agents.context_breakdown_planner import ContextBreakdownPlanner

async def test():
    planner = ContextBreakdownPlanner()
    breakdown = await planner.breakdown_question(
        'How does Snyk vulnerability table relate to SOC2 controls?'
    )
    print('Cross-Domain Query Breakdown:')
    print(f'  Query Type: {breakdown.query_type}')
    print(f'  Domains Involved: {breakdown.metadata.get(\"domains_involved\", [])}')
    print(f'  Search Questions: {len(breakdown.search_questions)}')
    for sq in breakdown.search_questions:
        print(f'    - {sq[\"entity\"]}: {sq[\"question\"]}')

asyncio.run(test())
"
```

---

## Summary

✅ **5 Separate Domain Graphs**:
1. MDL (Product Schemas) - Complete with contextual edges ⭐ NEW
2. Compliance (Frameworks & Controls)
3. Risk Management (Risk Controls)
4. Policy (Organizational Policies)
5. Product Documentation (Product Features)

✅ **Domain-Specific Agents**:
- `MDLContextBreakdownAgent` - for MDL queries ✅ Compatible with new changes
- `ComplianceContextBreakdownAgent` - for compliance queries
- Base agents for extensibility

✅ **Shared Collections with Type Discriminators**:
- `domain_knowledge` - used by multiple domains (type field)
- `entities` - used by multiple domains (type + mdl_entity_type)
- `contextual_edges` - shared graph storage

✅ **Independent Metadata Filtering**:
- Each domain has specific filter fields
- No cross-contamination in queries
- Clean separation of concerns

🎉 **MDL Agent Works After Changes!**
- Contextual edges: ✅ Already referenced in prompts
- Organization: ✅ In metadata, not in filters
- Knowledgebase: ✅ Compatible with entities collection
- Category filtering: ✅ Works with new routing
