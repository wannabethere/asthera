# Maintaining Domain Separation in Knowledge Graphs

## Problem Statement

We have **5 different domains** storing data in the same vector store:

1. **MDL** - Product schemas (Snyk, Cornerstone)
2. **Compliance** - Frameworks (SOC2, HIPAA, ISO 27001)
3. **Risk Management** - Risk controls and assessments
4. **Policy** - Organizational policies and procedures
5. **Product Documentation** - Product features and how-tos

**Challenge**: How do we keep these domains separate while sharing infrastructure?

## Solution: Type Discriminators + Metadata Filtering

### Strategy

Use **shared collections** with **type discriminators** in metadata:

```
Shared Collection: domain_knowledge
├─ Type: "compliance" (SOC2, HIPAA docs)
├─ Type: "risk" (Risk controls)
├─ Type: "policy" (Organizational policies)
└─ Type: "product" (Product documentation)

Shared Collection: entities
├─ Type: "mdl", mdl_entity_type: "feature" (MDL features)
├─ Type: "mdl", mdl_entity_type: "metric" (MDL metrics)
├─ Type: "compliance" (Compliance entities)
├─ Type: "risk_entities" (Risk entities)
└─ Type: "product" (Product key concepts)

Shared Collection: contextual_edges
├─ Source/Target entity_type discriminates domain
├─ Edge types are domain-specific
└─ Filters prevent cross-domain queries
```

## Domain Separation Rules

### Rule 1: Always Use Type Discriminator

**❌ BAD (Cross-domain contamination):**
```python
# Queries ALL domain_knowledge (mixes compliance, risk, policy, product)
results = await hybrid_search(
    query="access control",
    collection_name="domain_knowledge"
)
```

**✅ GOOD (Domain-specific):**
```python
# Queries ONLY compliance domain
results = await hybrid_search(
    query="access control requirements",
    collection_name="domain_knowledge",
    where={"type": "compliance", "framework": "SOC2"}
)
```

### Rule 2: Use Domain-Specific Agents

Each domain has a specialized context breakdown agent:

```python
# MDL queries → MDL agent
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

mdl_agent = MDLContextBreakdownAgent()
breakdown = await mdl_agent.breakdown_mdl_question(
    "What vulnerability tables exist?",
    product_name="Snyk"
)

# Compliance queries → Compliance agent
from app.agents.contextual_agents.compliance_context_breakdown_agent import ComplianceContextBreakdownAgent

compliance_agent = ComplianceContextBreakdownAgent()
breakdown = await compliance_agent.breakdown_question(
    "What are SOC2 access control requirements?",
    frameworks=["SOC2"]
)
```

### Rule 3: Namespace Entity IDs by Domain

Prevent ID collisions across domains:

```python
# MDL domain entity IDs
table_id = f"table_{table_name.lower()}"              # table_vulnerability
column_id = f"column_{table_name}_{column_name}"      # column_vulnerability_severity
feature_id = f"feature_{feature_name}"                # feature_vulnerability_count
metric_id = f"metric_{metric_name}"                   # metric_critical_rate
category_id = f"category_{category_name}"             # category_vulnerabilities
product_id = f"product_{product_name}"                # product_snyk

# Compliance domain entity IDs
framework_id = f"framework_{framework_name.lower()}"  # framework_soc2
control_id = f"control_{framework}_{control_id}"      # control_soc2_cc6.1
requirement_id = f"requirement_{framework}_{req_id}"  # requirement_soc2_001
evidence_id = f"evidence_{framework}_{evidence_id}"   # evidence_soc2_audit_log

# Risk domain entity IDs
risk_id = f"risk_{risk_name.lower()}"                 # risk_data_breach
risk_control_id = f"risk_control_{control_id}"        # risk_control_encryption

# Policy domain entity IDs
policy_id = f"policy_{policy_name.lower()}"           # policy_access_control
procedure_id = f"procedure_{procedure_name}"          # procedure_user_provisioning

# Product docs entity IDs
product_concept_id = f"product_concept_{concept}"     # product_concept_api_integration
```

### Rule 4: Use Domain-Specific Edge Types

Don't mix edge types across domains:

```python
# MDL edge types
MDL_EDGE_TYPES = [
    "PRODUCT_HAS_CATEGORY",
    "CATEGORY_HAS_TABLE",
    "TABLE_BELONGS_TO_CATEGORY",
    "TABLE_HAS_COLUMN",
    "TABLE_HAS_FEATURE",
    "TABLE_HAS_METRIC",
    "FEATURE_USES_TABLE",
    "METRIC_USES_TABLE",
    "EXAMPLE_USES_TABLE",
    "TABLE_FOLLOWS_INSTRUCTION",
    "TABLE_RELATES_TO_TABLE"
]

# Compliance edge types
COMPLIANCE_EDGE_TYPES = [
    "FRAMEWORK_HAS_TSC",
    "TSC_HAS_OBJECTIVE",
    "OBJECTIVE_HAS_CONTROL",
    "CONTROL_REQUIRES_POLICY",
    "CONTROL_HAS_PROCEDURE",
    "CONTROL_HAS_EVIDENCE",
    "CONTROL_HAS_FINDING",
    "HAS_CONTROL",  # Generic
]

# Risk edge types
RISK_EDGE_TYPES = [
    "RISK_MITIGATED_BY_CONTROL",
    "RISK_HAS_EVIDENCE",
    "RISK_HAS_FINDING",
]

# Query by edge type to stay within domain
results = await graph.find_edges_by_type(
    edge_type="TABLE_HAS_FEATURE",  # MDL domain only
    filters={"product_name": "Snyk"}
)
```

## Preview File Separation

Each domain generates **separate preview files**:

### MDL Domain Preview Files

```bash
# Generate MDL preview files
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --preview-dir indexing_preview \
    --batch-size 50

# Output:
indexing_preview/
├── table_definitions/table_definitions_TIMESTAMP_Snyk.json
├── table_descriptions/table_descriptions_TIMESTAMP_Snyk.json
├── column_definitions/column_definitions_TIMESTAMP_Snyk.json
├── knowledgebase/knowledgebase_TIMESTAMP_Snyk.json
└── contextual_edges/contextual_edges_TIMESTAMP_Snyk.json  # MDL edges only
```

### Compliance Domain Preview Files

```bash
# Generate compliance preview files (separate script)
python -m indexing_examples.create_compliance_hierarchical_edges \
    --frameworks SOC2 HIPAA ISO27001 \
    --preview-dir indexing_preview

# Output:
indexing_preview/
├── compliance_controls/compliance_controls_TIMESTAMP.json
├── domain_knowledge/domain_knowledge_TIMESTAMP_compliance_SOC2.json
└── contextual_edges/contextual_edges_TIMESTAMP_compliance.json  # Compliance edges only
```

### Key Observation

**Contextual edges are stored in the same `contextual_edges/` directory** BUT:
- Different filenames: `_Snyk.json` vs `_compliance.json`
- Different edge types: MDL edges vs Compliance edges
- Different entity IDs: `table_*` vs `control_*`
- When ingested: Same `contextual_edges` collection but filterable by `edge_type`

## Ingestion Separation

### Ingest Each Domain Separately

```bash
# 1. Ingest MDL domain
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase contextual_edges \
    --dry-run  # Check MDL files only

# 2. Ingest Compliance domain
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types compliance_controls domain_knowledge contextual_edges \
    --dry-run  # Check compliance files only

# 3. Ingest Risk domain
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types riskmanagement_risk_controls domain_knowledge contextual_edges

# 4. Ingest Policy domain
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types policy_documents domain_knowledge

# 5. Ingest Product docs
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types product_docs_link product_key_concepts extendable_doc
```

**OR Ingest All At Once (Recommended):**

```bash
# All domains ingested together (type discriminators prevent mixing)
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview
```

## Query Separation Examples

### MDL Domain Query

```python
# Query MDL tables
from app.agents.data.retrieval import hybrid_search

results = await hybrid_search(
    query="vulnerability tables",
    collection_name="table_descriptions",
    where={
        "product_name": "Snyk",  # MDL uses product_name
        "category_name": "vulnerabilities"
    },
    top_k=5
)

# Query MDL features
results = await hybrid_search(
    query="vulnerability analysis features",
    collection_name="entities",
    where={
        "product_name": "Snyk",
        "mdl_entity_type": "feature",  # MDL discriminator
        "category_name": "vulnerabilities"
    }
)

# Query MDL edges
results = await hybrid_search(
    query="table relationships",
    collection_name="contextual_edges",
    where={
        "product_name": "Snyk",
        "edge_type": "TABLE_RELATES_TO_TABLE"  # MDL edge type
    }
)
```

### Compliance Domain Query

```python
# Query compliance controls
results = await hybrid_search(
    query="access control requirements",
    collection_name="compliance_controls",
    where={
        "framework": "SOC2"  # Compliance uses framework
    }
)

# Query compliance domain knowledge
results = await hybrid_search(
    query="SOC2 requirements",
    collection_name="domain_knowledge",
    where={
        "type": "compliance",  # Domain discriminator
        "framework": "SOC2"
    }
)

# Query compliance edges
results = await hybrid_search(
    query="control evidence",
    collection_name="contextual_edges",
    where={
        "edge_type": "CONTROL_HAS_EVIDENCE",  # Compliance edge type
        "source_entity_type": "control"
    }
)
```

### Risk Domain Query

```python
# Query risk controls
results = await hybrid_search(
    query="security risks",
    collection_name="domain_knowledge",
    where={
        "type": "risk",  # Risk domain discriminator
        "risk_category": "security"
    }
)

# Query risk edges
results = await hybrid_search(
    query="risk mitigation",
    collection_name="contextual_edges",
    where={
        "edge_type": "RISK_MITIGATED_BY_CONTROL"  # Risk edge type
    }
)
```

## Verification Checklist

### After Ingesting Preview Files

Run these queries to verify domain separation:

```python
from app.core.dependencies import get_chromadb_client

client = get_chromadb_client()

# 1. Check contextual_edges has both MDL and Compliance edges
edges_coll = client.get_collection("contextual_edges")
mdl_edges = edges_coll.query(
    query_texts=["table relationships"],
    where={"edge_type": "TABLE_RELATES_TO_TABLE"},
    n_results=5
)
logger.info(f"MDL edges: {len(mdl_edges['ids'][0])}")

compliance_edges = edges_coll.query(
    query_texts=["control evidence"],
    where={"edge_type": "CONTROL_HAS_EVIDENCE"},
    n_results=5
)
logger.info(f"Compliance edges: {len(compliance_edges['ids'][0])}")

# 2. Check domain_knowledge has all domain types
domain_coll = client.get_collection("domain_knowledge")
compliance_docs = domain_coll.query(
    query_texts=["requirements"],
    where={"type": "compliance"},
    n_results=5
)
logger.info(f"Compliance docs: {len(compliance_docs['ids'][0])}")

risk_docs = domain_coll.query(
    query_texts=["risk"],
    where={"type": "risk"},
    n_results=5
)
logger.info(f"Risk docs: {len(risk_docs['ids'][0])}")

# 3. Check entities has both MDL and other types
entities_coll = client.get_collection("entities")
mdl_features = entities_coll.query(
    query_texts=["features"],
    where={"mdl_entity_type": "feature"},
    n_results=5
)
logger.info(f"MDL features: {len(mdl_features['ids'][0])}")

compliance_entities = entities_coll.query(
    query_texts=["controls"],
    where={"type": "compliance"},
    n_results=5
)
logger.info(f"Compliance entities: {len(compliance_entities['ids'][0])}")
```

## Common Pitfalls

### ❌ Pitfall 1: Forgetting Type Discriminator

```python
# BAD: Returns compliance + risk + policy docs mixed together
results = await hybrid_search(
    query="access control",
    collection_name="domain_knowledge"
)
```

**Fix:** Always add `type` filter
```python
# GOOD: Returns only compliance docs
results = await hybrid_search(
    query="access control",
    collection_name="domain_knowledge",
    where={"type": "compliance"}
)
```

### ❌ Pitfall 2: Using Wrong Agent

```python
# BAD: Using MDL agent for compliance query
mdl_agent = MDLContextBreakdownAgent()
breakdown = await mdl_agent.breakdown_mdl_question(
    "What are SOC2 requirements?"  # This is a compliance query!
)
```

**Fix:** Use correct agent
```python
# GOOD: Using compliance agent for compliance query
compliance_agent = ComplianceContextBreakdownAgent()
breakdown = await compliance_agent.breakdown_question(
    "What are SOC2 requirements?",
    frameworks=["SOC2"]
)
```

### ❌ Pitfall 3: Entity ID Collisions

```python
# BAD: Same ID for different domains
entity_id = "001"  # Could be table, control, or risk!
```

**Fix:** Namespace by domain
```python
# GOOD: Domain-prefixed IDs
mdl_id = "table_vulnerability"          # MDL table
compliance_id = "control_soc2_cc6.1"    # Compliance control
risk_id = "risk_data_breach"            # Risk entity
```

### ❌ Pitfall 4: Wrong Edge Type Filter

```python
# BAD: Looking for MDL edges with compliance edge type
results = await hybrid_search(
    query="table relationships",
    collection_name="contextual_edges",
    where={"edge_type": "CONTROL_HAS_EVIDENCE"}  # Compliance type!
)
```

**Fix:** Use domain-appropriate edge type
```python
# GOOD: MDL edge type for MDL query
results = await hybrid_search(
    query="table relationships",
    collection_name="contextual_edges",
    where={
        "edge_type": "TABLE_RELATES_TO_TABLE",  # MDL type
        "product_name": "Snyk"
    }
)
```

## Domain Configuration Summary

| Domain | Collections | Type Field | ID Prefix | Edge Types | Agent |
|--------|------------|------------|-----------|------------|-------|
| **MDL** | table_descriptions, entities, contextual_edges | `mdl_entity_type` | `table_`, `column_`, `feature_`, `metric_` | TABLE_*, COLUMN_*, FEATURE_*, METRIC_* | MDLContextBreakdownAgent |
| **Compliance** | compliance_controls, domain_knowledge, entities, contextual_edges | `type="compliance"` | `framework_`, `control_`, `requirement_` | CONTROL_*, FRAMEWORK_*, REQUIREMENT_* | ComplianceContextBreakdownAgent |
| **Risk** | domain_knowledge, controls, entities, contextual_edges | `type="risk"` | `risk_`, `risk_control_` | RISK_*, MITIGATED_BY_* | (TBD) |
| **Policy** | domain_knowledge, entities, contextual_edges | `type="policy"` | `policy_`, `procedure_` | POLICY_*, PROCEDURE_* | (TBD) |
| **Product** | domain_knowledge, entities, contextual_edges | `type="product"` | `product_concept_` | PRODUCT_*, CONCEPT_* | (TBD) |

## Testing Domain Separation

### Test Script

```bash
# Run MDL agent tests
python -m tests.test_mdl_agent_after_changes

# Expected output:
# ✅ TEST 1 PASSED - Table queries work
# ✅ TEST 2 PASSED - Relationship queries use contextual_edges
# ✅ TEST 3 PASSED - Feature queries use entities with mdl_entity_type
# ✅ TEST 4 PASSED - Metric queries work
# ✅ TEST 5 PASSED - Example queries use sql_pairs
# ✅ TEST 6 PASSED - Instruction queries work
# ✅ TEST 7 PASSED - Category filtering works
# ✅ TEST 8 PASSED - Organization NOT in filters
# ✅ TEST 9 PASSED - Cross-entity queries work
# 
# ✅ ALL TESTS PASSED - MDL Agent is compatible with new changes!
```

## Integration Testing

### Cross-Domain Query Test

Some queries span multiple domains:

```python
# User: "How does Snyk vulnerability table relate to SOC2 controls?"
# This query involves:
# - MDL domain: Snyk vulnerability table
# - Compliance domain: SOC2 controls

# Solution: Use ContextBreakdownPlanner (routes to appropriate agents)
from app.agents.context_breakdown_planner import ContextBreakdownPlanner

planner = ContextBreakdownPlanner()
breakdown = await planner.breakdown_question(
    "How does Snyk vulnerability table relate to SOC2 controls?"
)

# Planner will:
# 1. Detect both MDL and Compliance aspects
# 2. Use MDL agent for "Snyk vulnerability table"
# 3. Use Compliance agent for "SOC2 controls"
# 4. Combine results

logger.info(f"Domains involved: {breakdown.metadata.get('domains_involved')}")
# Expected: ["mdl", "compliance"]
```

## Summary

✅ **5 Separate Domains** maintained through:
- Type discriminators in shared collections
- Domain-specific entity ID prefixes
- Domain-specific edge types
- Domain-specific context breakdown agents

✅ **MDL Agent Updated** to support:
- Contextual edges (TABLE_HAS_FEATURE, etc.)
- Knowledgebase entities (features, metrics, instructions, examples)
- Organization metadata (in metadata, not in filters)
- Category filtering (category_name field)

✅ **Verification**:
- Run `tests/test_mdl_agent_after_changes.py`
- Check preview files in `indexing_preview/`
- Query each domain separately to ensure no cross-contamination

✅ **Best Practices**:
- Always use type discriminators
- Use domain-specific agents
- Namespace entity IDs by domain
- Use domain-specific edge types
- Test domain separation after changes

🎉 **Domain separation maintained while sharing infrastructure!**
