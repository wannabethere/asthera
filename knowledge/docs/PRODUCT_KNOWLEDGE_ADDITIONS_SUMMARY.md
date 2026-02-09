# Product Knowledge Mapping - What Was Added

## Summary

The design document has been updated to include **Product/Domain Knowledge Mapping** - the critical missing piece that enables contextual queries like "prioritize Snyk vulnerabilities for SOC 2 audit" and "which database tables are relevant for compliance."

---

## Major Additions

### 1. Updated System Objectives

Added **Goal #2: Product/Domain Knowledge Mapping**
- Map product entities (Snyk vulnerabilities, AWS resources, database tables) to compliance controls
- Define relationships between business entities and requirements
- Enable contextual queries bridging technical security data to compliance requirements
- Support goal-oriented reasoning (e.g., "prioritize vulnerabilities for audit")

### 2. New Data Models (Section: Product/Domain Knowledge Models)

Six new entity types added:

#### ProductDefinition
- Metadata about security/compliance products (Snyk, AWS Security Hub, Okta)
- Product capabilities and integration methods
- Example: Snyk as vulnerability scanner with API integration

#### EntitySchemaDefinition
- Define entities/objects within products (e.g., Snyk vulnerabilities, AWS EC2 instances, database tables)
- Full schema with fields, types, compliance significance
- Example: Snyk vulnerability schema with severity, cvss_score, exploit_maturity, fixable fields

#### FieldMappingDefinition
- Map product fields to compliance concepts
- Example: severity → risk_level, exploit_maturity → threat_likelihood
- Includes relevance to specific controls (e.g., severity is "critical" for CC7.2)

#### BusinessEntityDefinition
- Business-level entities (applications, services, databases, APIs)
- Criticality and data classification
- Compliance scope per entity
- Example: "Payment Processing API" = critical, restricted data, SOC2+PCI scope

#### ProductComplianceMapping
- **THE KEY BRIDGE**: Maps product entities to compliance controls
- Mapping types: provides_evidence, indicates_risk, satisfies_requirement, violates_policy
- Conditions: when mappings apply (e.g., "severity IN ['critical', 'high']")
- Examples: "Critical Snyk vulnerability → CC7.2 risk"

#### GoalQueryTemplate
- Define common user goals and how to achieve them
- Example: "Prioritize Snyk vulnerabilities for SOC 2 audit"
- Includes query logic, required mappings, example queries

### 3. Extended Knowledge Graph Structure

Added new node types:
- ProductNode
- EntitySchemaNode
- FieldMappingNode
- BusinessEntityNode
- GoalTemplateNode

Added new edge types (Product ↔ Compliance Bridge):
- PROVIDES_EVIDENCE_FOR (EntitySchema → Control)
- INDICATES_RISK_FOR (EntitySchema → Control)
- SATISFIES_REQUIREMENT (EntitySchema → Control)
- VIOLATES_POLICY (EntitySchema → Control)
- RELEVANT_TO_GOAL (EntitySchema → GoalTemplate)
- SCOPED_TO_CONTROL (BusinessEntity → Control)

### 4. New Query Patterns

Added Cypher query examples:
- Product entity to compliance control mapping (Query #6)
- Goal-oriented prioritization (Query #7)
- Find evidence sources for controls (Query #8)
- Business entity compliance scope (Query #9)
- Product field interpretation (Query #10)

### 5. New Query Types in Agentic Interface

#### Query Type 8: Product Mapping Queries
- "Which Snyk vulnerabilities impact SOC 2?"
- "Map AWS Security Hub findings to HIPAA controls"
- "What Okta events provide evidence for CC6.1?"
- "Which database tables are relevant for PCI-DSS?"

#### Query Type 9: Goal-Oriented Queries
- "Prioritize Snyk vulnerabilities for SOC 2 audit"
- "Which AWS resources need HIPAA controls?"
- "Find data tables that handle PII for GDPR"
- "What security findings should I fix first for audit?"

#### Query Type 10: Schema Understanding Queries
- "What does Snyk's 'exploit_maturity' field mean for compliance?"
- "How should I interpret AWS Security Hub severity levels?"
- "Which Okta log fields are required for access control evidence?"

### 6. Complete Use Case: Snyk Vulnerability Prioritization

Added **Use Case 1** showing end-to-end workflow:
- User query: "Prioritize our Snyk vulnerabilities for SOC 2 audit"
- Knowledge graph provides:
  - SOC 2 control mapping (CC7.1, CC7.2)
  - Snyk entity schema with field definitions
  - Field mappings (severity → risk_level, etc.)
  - Product→compliance mappings with conditions
  - Business entity context (Payment API = critical)
  - Prioritization scoring model with weights
  - Prioritization rules (P0, P1, P2, P3)
  - Field interpretation guide
  - Evidence collection guidance
  - Business entity priority multipliers

**Key Innovation:** The knowledge graph doesn't return actual vulnerabilities - it returns the **logic for prioritizing them**, which agents then apply to real Snyk data.

### 7. Complete Use Case: Data Table Mapping

Added **Use Case 3** (to be inserted) showing:
- User query: "Which database tables are relevant for SOC 2 CC6?"
- Knowledge graph provides:
  - Table schema mappings (user_access_logs, user_roles, access_reviews)
  - Required fields per table with compliance concepts
  - Field-level validation rules
  - Sample SQL queries
  - Compliance report schema generation
  - Validation query examples

---

## The Key Insight

The **Contextual Compliance Graph** now bridges TWO domains:

```
┌─────────────────────────────────────┐
│  COMPLIANCE KNOWLEDGE               │
│  • Frameworks (SOC 2, HIPAA)        │
│  • Controls (CC6.1, CC7.2)          │
│  • Requirements                      │
└──────────────┬──────────────────────┘
               │
        CONTEXTUAL EDGES
        (ProductComplianceMapping)
               │
┌──────────────▼──────────────────────┐
│  PRODUCT/DOMAIN KNOWLEDGE           │
│  • Snyk vulnerabilities             │
│  • AWS resources                     │
│  • Database tables                   │
│  • Security findings                 │
│  • Business entities                 │
└─────────────────────────────────────┘
```

This enables queries like:
- "What Snyk findings matter for my audit?" (Product → Compliance)
- "What evidence do I need for CC6?" (Compliance → Product)
- "Prioritize vulnerabilities by compliance impact" (Goal-oriented using both)

---

## Example: Complete Snyk → SOC 2 Mapping

```yaml
# Product
Snyk:
  type: vulnerability_scanner
  
# Entity Schema
SnykVulnerability:
  fields:
    - severity: enum [critical, high, medium, low]
    - cvss_score: float
    - exploit_maturity: enum
    - fixable: boolean

# Field Mappings
severity → risk_level (critical relevance for CC7.2)
exploit_maturity → threat_likelihood (high relevance for CC7.1)
fixable → remediability (high relevance for CC7.2)

# Product → Compliance Mapping
Critical Vulnerability:
  source: SnykVulnerability
  target: CC7.2
  type: indicates_risk
  strength: 0.9
  conditions: severity IN ['critical', 'high']
  logic: "Requires immediate remediation per CC7.2"

# Business Entity Context
Payment API:
  criticality: critical
  data_classification: restricted
  snyk_projects: ["org/payment-api"]
  priority_multiplier: 1.5

# Goal Template
Prioritize for Audit:
  pattern: "Prioritize [product] for [framework] audit"
  logic:
    1. Map product entities to controls
    2. Score by: severity × compliance_impact × business_criticality
    3. Apply prioritization rules
    4. Return ranked list with remediation guidance
```

---

## What This Enables

### For Security Engineers:
- "Show me Snyk findings that impact SOC 2"
- "Which vulnerabilities should I fix for the audit?"
- "What AWS resources need HIPAA controls?"

### For Data Engineers:
- "Which database tables matter for PCI compliance?"
- "What fields do I need for compliance reporting?"
- "Generate a compliance report schema for CC6"

### For Compliance Managers:
- "Map our security tools to compliance requirements"
- "What evidence sources do we have for each control?"
- "Prioritize findings by audit impact"

---

## Document Status

✅ System objectives updated
✅ Product knowledge data models added
✅ Knowledge graph structure extended
✅ Query patterns added (Cypher examples)
✅ Agentic query types extended
✅ Complete Snyk prioritization use case added
⚠️  Data table mapping use case outlined (needs insertion)

The design document now fully supports **product knowledge mapping** and **goal-oriented contextual reasoning** - the missing pieces for enabling queries like "prioritize Snyk vulnerabilities for SOC 2 audit."
