# Domain Separation - Visual Architecture Guide

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KNOWLEDGE GRAPH SYSTEM                                │
│                       (5 Separate Domain Graphs)                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   MDL DOMAIN     │  │ COMPLIANCE DOMAIN│  │   RISK DOMAIN    │
│   (Snyk, etc.)   │  │ (SOC2, HIPAA)    │  │ (Risk Controls)  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         │                     │                     │
┌──────────────────┐  ┌──────────────────┐
│  POLICY DOMAIN   │  │ PRODUCT DOCS     │
│  (Org Policies)  │  │ (How-to Guides)  │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         └─────────┬───────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │      SHARED INFRASTRUCTURE       │
    │                                  │
    │  Vector Store (ChromaDB/Qdrant)  │
    │  ├─ domain_knowledge (shared)    │
    │  ├─ entities (shared)            │
    │  ├─ contextual_edges (shared)    │
    │  ├─ table_descriptions (MDL)     │
    │  └─ compliance_controls (Comp.)  │
    │                                  │
    │  Type Discriminators:            │
    │  - type field                    │
    │  - mdl_entity_type field         │
    │  - edge_type field               │
    │  - framework field               │
    └──────────────────────────────────┘
```

## Domain 1: MDL (Product Schemas)

```
┌─────────────────────────────────────────────────────────────────┐
│                     MDL DOMAIN GRAPH                            │
└─────────────────────────────────────────────────────────────────┘

                    Product: Snyk
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
  Category:         Category:          Category:
  vulnerabilities   access requests    assets
      │                  │                  │
      ├─ Table:          ├─ Table:          ├─ Table:
      │  Vulnerability   │  AccessRequest   │  Asset
      │  │               │  │               │  │
      │  ├─ Column:      │  ├─ Column:      │  ├─ Column:
      │  │  severity     │  │  status       │  │  asset_id
      │  │  created_at   │  │  id           │  │  name
      │  │               │  │               │  │
      │  ├─ Feature:     │  ├─ Feature:     │  ├─ Feature:
      │  │  vuln_count   │  │  access_rate  │  │  asset_count
      │  │               │  │               │  │
      │  ├─ Metric:      │  ├─ Metric:      │  ├─ Metric:
      │  │  crit_rate    │  │  approval_pct │  │  asset_coverage
      │  │               │  │               │  │
      │  ├─ Instruction: │  └─ Example:     │  └─ Example:
      │  │  "Filter by   │     "SELECT *"   │     "SELECT *"
      │  │   status"     │                  │
      │  │               │                  │
      │  └─ Example:     │                  │
      │     "SELECT      │                  │
      │      COUNT(*)"   │                  │
      └─────────────────┴──────────────────┘

Collections Used:
  - table_descriptions (product_name="Snyk")
  - table_definitions (product_name="Snyk")
  - column_definitions (product_name="Snyk")
  - entities (mdl_entity_type="feature"/"metric")
  - instructions (product_name="Snyk")
  - sql_pairs (product_name="Snyk")
  - contextual_edges (edge_type="TABLE_*")

Agent: MDLContextBreakdownAgent
```

## Domain 2: Compliance (Frameworks)

```
┌─────────────────────────────────────────────────────────────────┐
│                  COMPLIANCE DOMAIN GRAPH                        │
└─────────────────────────────────────────────────────────────────┘

           Framework: SOC2
                 │
      ┌──────────┼──────────┐
      │          │          │
      ▼          ▼          ▼
    TSC: CC     TSC: CI    TSC: PI
      │          │          │
      ▼          ▼          ▼
  Objective   Objective  Objective
      │          │          │
      ├─ Control:        Control:
      │  CC6.1           CI1.1
      │  │               │
      │  ├─ Policy:      ├─ Policy:
      │  │  Access Ctrl  │  Change Mgmt
      │  │               │
      │  ├─ Procedure:   ├─ Procedure:
      │  │  User Prov.   │  Code Review
      │  │               │
      │  ├─ Evidence:    ├─ Evidence:
      │  │  Access Log   │  PR Records
      │  │               │
      │  └─ Finding:     └─ Finding:
      │     Issue #123       Issue #456
      └────────────────────────────────┘

Collections Used:
  - compliance_controls (framework="SOC2"/"HIPAA"/etc.)
  - domain_knowledge (type="compliance", framework="SOC2")
  - entities (type="compliance")
  - evidence (type="compliance")
  - contextual_edges (edge_type="CONTROL_*", "FRAMEWORK_*")

Agent: ComplianceContextBreakdownAgent
```

## Domain 3: Risk Management

```
┌─────────────────────────────────────────────────────────────────┐
│                   RISK DOMAIN GRAPH                             │
└─────────────────────────────────────────────────────────────────┘

           Risk Category: Security
                    │
      ┌─────────────┼─────────────┐
      │             │             │
      ▼             ▼             ▼
  Risk:        Risk:        Risk:
  Data Breach  Malware      Phishing
      │             │             │
      ├─ Control:   ├─ Control:   ├─ Control:
      │  Encryption │  Antivirus  │  Email Filter
      │  │          │  │          │  │
      │  ├─ Evidence: ├─ Evidence: ├─ Evidence:
      │  │  Logs     │  │  Scans   │  │  Filter Logs
      │  │          │  │          │  │
      │  └─ Finding: └─ Finding:  └─ Finding:
      │     Issue    │    Issue    │    Issue
      └─────────────┴─────────────┴─────────────┘

Collections Used:
  - domain_knowledge (type="risk")
  - controls (type="risk_control")
  - entities (type="risk_entities")
  - evidence (type="risk_evidence")
  - contextual_edges (edge_type="RISK_*")

Agent: (TBD - can reuse BaseContextBreakdownAgent)
```

## Domain 4: Policy Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    POLICY DOMAIN GRAPH                          │
└─────────────────────────────────────────────────────────────────┘

        Policy Category: Security
                  │
      ┌───────────┼───────────┐
      │           │           │
      ▼           ▼           ▼
  Policy:    Policy:    Policy:
  Access     Password   Network
  Control    Policy     Policy
      │           │           │
      ├─ Procedure:  ├─ Procedure:  ├─ Procedure:
      │  User Prov.  │  Pwd Reset   │  Firewall
      │  │           │  │           │  │
      │  └─ Control:  └─ Control:   └─ Control:
      │     (maps to     (maps to      (maps to
      │     compliance)  compliance)   compliance)
      └──────────────────────────────────────────┘

Collections Used:
  - domain_knowledge (type="policy")
  - entities (type="policy")
  - fields (type="policy")
  - contextual_edges (edge_type="POLICY_*")

Agent: (TBD - can reuse BaseContextBreakdownAgent)
```

## Domain 5: Product Documentation

```
┌─────────────────────────────────────────────────────────────────┐
│              PRODUCT DOCUMENTATION GRAPH                        │
└─────────────────────────────────────────────────────────────────┘

           Product: Snyk
                 │
      ┌──────────┼──────────┐
      │          │          │
      ▼          ▼          ▼
  Concept:   Concept:   Concept:
  Projects   Issues     Integrations
      │          │          │
      ├─ Feature: ├─ Feature: ├─ Feature:
      │  Project  │  Issue    │  GitHub
      │  Scanning │  Tracking │  Integration
      │           │           │
      └─ Control: └─ Control: └─ Control:
         (if security product)
         ────────────────────────┘

Collections Used:
  - domain_knowledge (type="product")
  - entities (type="product")
  - product_key_concepts
  - extendable_docs
  - contextual_edges (edge_type="PRODUCT_*")

Agent: (TBD - can reuse BaseContextBreakdownAgent)
```

## Shared Collections with Domain Isolation

### domain_knowledge Collection

```
domain_knowledge
├─ Documents with type="compliance"
│  ├─ Framework requirements
│  ├─ Control descriptions
│  └─ Compliance concepts
│
├─ Documents with type="risk"
│  ├─ Risk assessments
│  ├─ Risk control descriptions
│  └─ Risk concepts
│
├─ Documents with type="policy"
│  ├─ Organizational policies
│  ├─ Policy procedures
│  └─ Policy standards
│
└─ Documents with type="product"
   ├─ Product documentation
   ├─ How-to guides
   └─ Product concepts

Query Isolation:
  where={"type": "compliance"}  → Only compliance docs
  where={"type": "risk"}        → Only risk docs
  where={"type": "policy"}      → Only policy docs
  where={"type": "product"}     → Only product docs
```

### entities Collection

```
entities
├─ Documents with type="mdl"
│  ├─ mdl_entity_type="feature" (MDL features)
│  └─ mdl_entity_type="metric" (MDL metrics)
│
├─ Documents with type="compliance"
│  └─ Compliance entities
│
├─ Documents with type="risk_entities"
│  └─ Risk entities
│
├─ Documents with type="policy"
│  └─ Policy entities
│
└─ Documents with type="product"
   └─ Product key concepts

Query Isolation:
  where={"mdl_entity_type": "feature"}      → Only MDL features
  where={"type": "compliance"}               → Only compliance entities
  where={"type": "risk_entities"}           → Only risk entities
```

### contextual_edges Collection

```
contextual_edges
├─ MDL edges
│  ├─ edge_type="TABLE_HAS_FEATURE"
│  ├─ edge_type="TABLE_HAS_COLUMN"
│  ├─ edge_type="TABLE_RELATES_TO_TABLE"
│  └─ source_entity_type="table"
│
├─ Compliance edges
│  ├─ edge_type="CONTROL_HAS_EVIDENCE"
│  ├─ edge_type="FRAMEWORK_HAS_CONTROL"
│  └─ source_entity_type="control"/"framework"
│
├─ Risk edges
│  ├─ edge_type="RISK_MITIGATED_BY_CONTROL"
│  └─ source_entity_type="risk"
│
└─ Policy edges
   ├─ edge_type="POLICY_HAS_PROCEDURE"
   └─ source_entity_type="policy"

Query Isolation:
  where={"edge_type": "TABLE_HAS_FEATURE"}           → Only MDL edges
  where={"edge_type": "CONTROL_HAS_EVIDENCE"}        → Only compliance edges
  where={"source_entity_type": "table"}              → Only MDL edges
  where={"source_entity_type": "control"}            → Only compliance edges
```

## Preview File Separation

```
indexing_preview/
│
├─ MDL DOMAIN (Generated by create_mdl_enriched_preview.py)
│  ├─ table_definitions/
│  │  └─ table_definitions_20260128_XXXXXX_Snyk.json
│  ├─ table_descriptions/
│  │  └─ table_descriptions_20260128_XXXXXX_Snyk.json
│  ├─ column_definitions/
│  │  └─ column_definitions_20260128_XXXXXX_Snyk.json
│  ├─ knowledgebase/
│  │  └─ knowledgebase_20260128_XXXXXX_Snyk.json
│  └─ contextual_edges/
│     └─ contextual_edges_20260128_XXXXXX_Snyk.json  ← MDL edges
│
├─ COMPLIANCE DOMAIN (Generated by create_compliance_hierarchical_edges.py)
│  ├─ compliance_controls/
│  │  └─ compliance_controls_20260124_XXXXXX.json
│  ├─ domain_knowledge/
│  │  ├─ domain_knowledge_20260124_XXXXXX_compliance_SOC2.json
│  │  └─ domain_knowledge_20260124_XXXXXX_compliance_HIPAA.json
│  └─ contextual_edges/
│     └─ contextual_edges_20260124_XXXXXX_compliance.json  ← Compliance edges
│
├─ RISK DOMAIN (Generated by risk preview scripts)
│  ├─ riskmanagement_risk_controls/
│  │  └─ riskmanagement_risk_controls_20260121_XXXXXX.json
│  ├─ domain_knowledge/
│  │  └─ (risk docs with type="risk")
│  └─ contextual_edges/
│     └─ contextual_edges_XXXXXX_risk.json  ← Risk edges
│
├─ POLICY DOMAIN (Generated by policy preview scripts)
│  ├─ policy_documents/
│  │  └─ policy_documents_20260121_XXXXXX.json
│  ├─ domain_knowledge/
│  │  └─ (policy docs with type="policy")
│  └─ contextual_edges/
│     └─ contextual_edges_XXXXXX_policy.json  ← Policy edges
│
└─ PRODUCT DOCS DOMAIN (Generated by create_product_docs_preview.py)
   ├─ product_docs_link/
   │  └─ product_docs_link_20260124_XXXXXX_Snyk.json
   ├─ product_key_concepts/
   │  └─ product_key_concepts_20260124_XXXXXX_Snyk.json
   └─ contextual_edges/
      └─ contextual_edges_XXXXXX_product.json  ← Product edges
```

**Key Observation:** All domains write to `contextual_edges/` directory but:
- Different filenames (suffixed by domain)
- Different edge types
- Different entity ID prefixes
- Ingested into same collection but filterable by `edge_type`

## Agent Routing

```
User Question
     │
     ▼
┌─────────────────────┐
│ ContextBreakdown    │
│ Planner (Router)    │
└────────┬────────────┘
         │
    ┌────┴────────────────────────────────┐
    │                                     │
    ▼                                     ▼
Is it MDL?                          Is it Compliance?
(table, schema, column, feature)    (framework, control, evidence)
    │                                     │
    ▼                                     ▼
┌────────────────────┐            ┌────────────────────┐
│ MDLContextBreakdown│            │ ComplianceContext  │
│ Agent              │            │ BreakdownAgent     │
└────────┬───────────┘            └────────┬───────────┘
         │                                  │
         ▼                                  ▼
  Query MDL Collections              Query Compliance Collections
  - table_descriptions               - compliance_controls
  - entities (mdl_entity_type)       - domain_knowledge (type="compliance")
  - contextual_edges (TABLE_*)       - contextual_edges (CONTROL_*)
         │                                  │
         └──────────┬───────────────────────┘
                    │
                    ▼
              ┌─────────────┐
              │  Combined   │
              │  Results    │
              └─────────────┘
```

## Edge Type Hierarchy

### MDL Edge Types (Prefix: TABLE_, COLUMN_, FEATURE_, METRIC_)

```
PRODUCT_HAS_CATEGORY
  └─ CATEGORY_HAS_TABLE
      └─ TABLE_BELONGS_TO_CATEGORY
      └─ TABLE_HAS_COLUMN
          └─ COLUMN_BELONGS_TO_TABLE
      └─ TABLE_HAS_FEATURE
          └─ FEATURE_USES_TABLE
      └─ TABLE_HAS_METRIC
          └─ METRIC_USES_TABLE
      └─ TABLE_FOLLOWS_INSTRUCTION
      └─ EXAMPLE_USES_TABLE
      └─ TABLE_RELATES_TO_TABLE (FK)
```

### Compliance Edge Types (Prefix: FRAMEWORK_, CONTROL_, REQUIREMENT_)

```
FRAMEWORK_HAS_TSC
  └─ TSC_HAS_OBJECTIVE
      └─ OBJECTIVE_HAS_CONTROL
          └─ CONTROL_REQUIRES_POLICY
          └─ CONTROL_HAS_PROCEDURE
          └─ CONTROL_HAS_EVIDENCE
          └─ CONTROL_HAS_FINDING
```

### Risk Edge Types (Prefix: RISK_)

```
RISK_CATEGORY_HAS_RISK
  └─ RISK_MITIGATED_BY_CONTROL
  └─ RISK_HAS_EVIDENCE
  └─ RISK_HAS_FINDING
```

**No overlap in edge types = No cross-domain contamination!**

## Query Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  User Query: "What features does Vulnerability table have?"  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Detect Domain: MDL  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌────────────────────────┐
              │ MDLContextBreakdown    │
              │ Agent                  │
              └──────────┬─────────────┘
                         │
                         ▼
              ┌────────────────────────────────────┐
              │ Generate Search Questions:         │
              │                                    │
              │ 1. Entity: table_descriptions      │
              │    Question: "Vulnerability table" │
              │    Filters: {                      │
              │      product_name: "Snyk",         │
              │      category_name: "vulnerabilities"
              │    }                               │
              │                                    │
              │ 2. Entity: entities                │
              │    Question: "vulnerability features"
              │    Filters: {                      │
              │      product_name: "Snyk",         │
              │      mdl_entity_type: "feature",   │ ← Knowledgebase
              │      category_name: "vulnerabilities"
              │    }                               │
              │                                    │
              │ 3. Entity: contextual_edges        │ ← New!
              │    Question: "feature relationships"
              │    Filters: {                      │
              │      edge_type: "TABLE_HAS_FEATURE",
              │      source_entity_id: "table_vulnerability"
              │    }                               │
              └────────────┬───────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ Execute Searches        │
              │ (Domain-specific only)  │
              └─────────────┬───────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ Return Results          │
              │ (MDL domain only)       │
              └─────────────────────────┘
```

## Ingestion Flow

```
┌────────────────────────────────────────────────────────┐
│                  ingest_preview_files.py               │
│                                                        │
│  Reads ALL preview files from indexing_preview/       │
│  Routes to appropriate collections based on:          │
│  - content_type (from file metadata)                  │
│  - entity_type (from document metadata)               │
│  - extraction_type (for split files)                  │
└────────────────────────┬───────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    MDL Files      Compliance Files   Risk Files
         │               │               │
         ▼               ▼               ▼
    Add type       Add type         Add type
    metadata       discriminators   discriminators
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Vector Store        │
              │  (Shared Collections)│
              │                      │
              │  But isolated by:    │
              │  - type field        │
              │  - edge_type field   │
              │  - entity prefixes   │
              └──────────────────────┘
```

## Complete Command Reference

### MDL Domain

```bash
# 1. Generate MDL preview files
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --product-name "Snyk" \
    --batch-size 50

# 2. Ingest MDL preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase contextual_edges

# 3. Query MDL
python -c "
import asyncio
from app.agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent
agent = MDLContextBreakdownAgent()
breakdown = asyncio.run(agent.breakdown_mdl_question('What features exist?', 'Snyk'))
print(breakdown.search_questions)
"
```

### Compliance Domain

```bash
# 1. Generate compliance preview files
python -m indexing_examples.create_compliance_hierarchical_edges \
    --frameworks SOC2 HIPAA

# 2. Ingest compliance preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types compliance_controls domain_knowledge contextual_edges

# 3. Query compliance
python -c "
import asyncio
from app.agents.contextual_agents.compliance_context_breakdown_agent import ComplianceContextBreakdownAgent
agent = ComplianceContextBreakdownAgent()
breakdown = asyncio.run(agent.breakdown_question('What are SOC2 requirements?', frameworks=['SOC2']))
print(breakdown.search_questions)
"
```

## Verification Commands

```bash
# 1. Check MDL collections
python -c "
from app.core.dependencies import get_chromadb_client
client = get_chromadb_client()

print('MDL Collections:')
for coll_name in ['table_descriptions', 'entities', 'contextual_edges']:
    coll = client.get_collection(coll_name)
    count = coll.count()
    print(f'  {coll_name}: {count} documents')
"

# 2. Check domain separation in contextual_edges
python -c "
from app.core.dependencies import get_chromadb_client
client = get_chromadb_client()
edges = client.get_collection('contextual_edges')

mdl_edges = edges.query(query_texts=['table'], where={'edge_type': 'TABLE_HAS_COLUMN'}, n_results=1)
print(f'MDL edges sample: {len(mdl_edges[\"ids\"][0])}')

comp_edges = edges.query(query_texts=['control'], where={'edge_type': 'CONTROL_HAS_EVIDENCE'}, n_results=1)
print(f'Compliance edges sample: {len(comp_edges[\"ids\"][0])}')
"

# 3. Verify no cross-contamination
python -c "
from app.core.dependencies import get_chromadb_client
client = get_chromadb_client()
domain_know = client.get_collection('domain_knowledge')

# Should return 0 (MDL doesn't use domain_knowledge)
mdl_docs = domain_know.query(query_texts=['table'], where={'type': 'mdl'}, n_results=10)
print(f'MDL docs in domain_knowledge: {len(mdl_docs[\"ids\"][0])} (should be 0)')

# Should return > 0 (Compliance uses domain_knowledge)
comp_docs = domain_know.query(query_texts=['control'], where={'type': 'compliance'}, n_results=10)
print(f'Compliance docs in domain_knowledge: {len(comp_docs[\"ids\"][0])} (should be > 0)')
"
```

## Summary

✅ **5 Separate Domain Graphs** maintained through:
- Type discriminators in metadata
- Domain-specific entity ID prefixes  
- Domain-specific edge types
- Domain-specific context breakdown agents

✅ **Shared Infrastructure** with **complete isolation**:
- Same collections, different `type` values
- Same `contextual_edges`, different `edge_type` values
- No cross-domain queries possible

✅ **MDL Domain Complete** with:
- Tables, columns, features, metrics, instructions, examples
- Contextual edges connecting all entities
- Organization support (metadata only)
- Category-based filtering

✅ **All Domains Can Coexist** without interference:
- MDL: Product schemas
- Compliance: Framework controls
- Risk: Risk management
- Policy: Organizational policies
- Product Docs: How-to guides

🎉 **Clean domain separation achieved!**
