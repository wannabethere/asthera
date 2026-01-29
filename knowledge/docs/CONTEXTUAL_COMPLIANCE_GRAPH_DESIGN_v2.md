# Contextual Compliance Graph: System Design Document

## Document Information

**Version:** 2.0  
**Date:** January 28, 2026  
**Status:** Design Phase  
**Author:** System Architecture Team  
**System Type:** Metadata Knowledge Graph (Agentic Access Only)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Objectives](#system-objectives)
3. [Architecture Philosophy](#architecture-philosophy)
4. [Object Framework](#object-framework)
5. [Metadata Models](#metadata-models)
6. [Agentic Query Interface](#agentic-query-interface)
7. [Knowledge Graph Structure](#knowledge-graph-structure)
8. [Integration Patterns](#integration-patterns)
9. [Implementation Considerations](#implementation-considerations)

---

## Executive Summary

This document defines the architecture for a **Contextual Compliance Knowledge Graph** - a metadata-only system that provides semantic understanding of compliance frameworks, controls, and their relationships. Unlike operational compliance systems, this knowledge graph contains **definitions, templates, and relationships** but no actual operational data.

**What This System Is:**
- A semantic layer defining compliance concepts and their relationships
- A knowledge base agents query to understand "what should be"
- A contextual graph mapping frameworks → controls → required actions
- A reference system for compliance intelligence

**What This System Is NOT:**
- An operational system storing real user actions or evidence
- A GRC platform replacement
- A compliance monitoring or alerting system
- A system of record for audit data

**Key Capabilities:**
- Multi-level compliance ontology (Framework → Required Action Templates)
- Semantic relationships between compliance concepts
- Natural language query interface for agentic workflows
- Contextual reasoning about control requirements
- Template-based guidance for evidence and actions

**Access Pattern:**
ALL queries go through agentic workflows. No direct database access. No CRUD APIs for end users.

---

## System Objectives

### Primary Goals

1. **Compliance Knowledge Repository**
   - Store and organize compliance framework definitions
   - Maintain relationships between controls, policies, procedures
   - Provide templates for required actions and evidence types
   - Enable semantic search across compliance concepts

2. **Product/Domain Knowledge Mapping**
   - Map product entities (Snyk vulnerabilities, AWS resources, etc.) to compliance controls
   - Define relationships between business entities and requirements
   - Enable contextual queries like "Which Snyk findings impact SOC 2?"
   - Support goal-oriented reasoning (e.g., "prioritize vulnerabilities for audit")
   - Bridge technical security data to compliance requirements

3. **Agentic Intelligence Layer**
   - Answer questions like "What controls apply to user access?"
   - Explain relationships like "How does CC6.1 relate to HIPAA?"
   - Suggest relevant controls for specific contexts
   - Provide templates for evidence collection
   - Map product knowledge to compliance requirements

4. **Context-Aware Reasoning**
   - Map business contexts to relevant compliance requirements
   - Understand domain-specific interpretations of controls
   - Support multi-framework reasoning (e.g., SOC 2 + HIPAA)
   - Enable "compliance as code" through structured metadata
   - Connect product features/entities to compliance controls

5. **Integration Enablement**
   - Provide semantic layer for operational systems to query
   - Guide agents on what to look for in real systems
   - Define expected evidence types and validation criteria
   - Template required actions for automation
   - Map external product schemas to compliance concepts

### Non-Goals

- Storing operational data (logs, tickets, user actions)
- Real-time monitoring or alerting
- Compliance scoring based on actual system state
- Replacing GRC platforms or audit tools
- Managing actual evidence artifacts

---

## Architecture Philosophy

### Knowledge Graph vs. Operational System

This system is fundamentally a **knowledge graph** containing compliance ontology:

```
┌─────────────────────────────────────────────────────────────┐
│  METADATA LAYER (This System)                               │
│  • Framework definitions                                     │
│  • Control descriptions                                      │
│  • Policy templates                                          │
│  • Procedure definitions                                     │
│  • Required action templates                                 │
│  • Expected evidence types                                   │
│  • Semantic relationships                                    │
└─────────────────────────────────────────────────────────────┘
                            ↕
          Queried by Agentic Workflows
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  OPERATIONAL LAYER (External Systems)                        │
│  • IAM logs (actual user actions)                           │
│  • SIEM alerts (actual detections)                          │
│  • Ticketing systems (actual issues)                        │
│  • Audit logs (actual evidence)                             │
│  • GRC platforms (actual compliance state)                  │
└─────────────────────────────────────────────────────────────┘
```

### Separation of Concerns

**This System Answers:**
- "What is CC6.1?" (definition)
- "What actions are required for quarterly access reviews?" (template)
- "What evidence types validate this control?" (specification)
- "How do SOC 2 and HIPAA controls relate?" (relationships)

**External Systems Answer:**
- "Did the access review happen?" (operational data)
- "Is there evidence in S3?" (actual artifacts)
- "Are there open issues?" (current state)
- "What's the control effectiveness?" (computed scores)

### Agentic Workflow Pattern

```
User Query
    ↓
Agentic Workflow (LangGraph)
    ↓
Knowledge Graph Query
    ↓
Retrieve Definitions/Templates
    ↓
Agent Uses Templates to Query External Systems
    ↓
Agent Synthesizes Response
    ↓
User Receives Answer
```

**Example:**
```
User: "What evidence do I need for SOC 2 CC6.1?"

Workflow:
1. Query knowledge graph: GET control definition for CC6.1
2. Response: Control requires "logical access controls"
3. Query knowledge graph: GET required evidence types
4. Response: ["IAM audit logs", "access review reports", "approval tickets"]
5. Query knowledge graph: GET evidence validation criteria
6. Response: {"freshness": "30 days", "format": "JSON", "fields": [...]}
7. Agent synthesizes answer with templates

User receives: Structured guidance on required evidence
```

---

## Object Framework

### 1. Canonical Hierarchy

The system implements a many-to-many, graph-first hierarchy of **definitions**:

```
Framework Definition
  ↓
Trust Service Criteria Definition
  ↓
Control Objective Definition
  ↓
Control Definition
  ↓
Policy Template
  ↓
Procedure Definition
  ↓
Required Action Template
  ↓
Expected Evidence Specification
  ↓
Issue Pattern Definition
```

**Key Insight:** Each level defines "what should be" not "what is"

### 2. Level Definitions

Each level provides metadata and specifications:

| Level | Contains | Purpose | Example |
|-------|----------|---------|---------|
| **Framework Definition** | Framework metadata | Defines compliance standard | SOC 2 Type II (2017 version) |
| **Trust Service Criteria** | Category definitions | Groups related controls | CC6 - Logical Access Controls |
| **Control Objective** | Outcome specifications | What must be achieved | "Access restricted to authorized users" |
| **Control Definition** | Control metadata | How outcome is ensured | Role-based access control definition |
| **Policy Template** | Policy structure | What rule should exist | Least privilege policy template |
| **Procedure Definition** | Workflow specification | How to execute policy | "Quarterly access review" steps |
| **Required Action Template** | Action specifications | What actions are needed | "Manager reviews and approves/revokes access" |
| **Expected Evidence Spec** | Evidence requirements | What proves compliance | "IAM audit log with timestamps and actors" |
| **Issue Pattern Definition** | Failure patterns | Common compliance gaps | "Review completed but no revocations" |

### 3. Metadata vs. Operational Data

**This System Stores:**
```yaml
Control CC6.1:
  name: "Logical Access Controls"
  description: "Access to systems must be restricted..."
  control_type: "preventive"
  required_procedures:
    - procedure_id: "quarterly_access_review"
      frequency: "quarterly"
  required_actions:
    - action_type: "generate_report"
      actor_role: "system"
      system: "IAM"
    - action_type: "review_access"
      actor_role: "manager"
      sla: "7 days"
  expected_evidence:
    - evidence_type: "audit_log"
      source_system: "IAM"
      required_fields: ["timestamp", "actor", "action", "resource"]
      freshness_requirement: "30 days"
```

**This System Does NOT Store:**
```yaml
# No operational data like this:
Actual Action:
  action_id: "abc123"
  timestamp: "2026-01-20T14:30:00Z"
  actor: "john@company.com"
  system: "Okta"
  outcome: "approved"
  
Actual Evidence:
  evidence_id: "xyz789"
  s3_path: "s3://bucket/evidence.json"
  collected_at: "2026-01-20T14:35:00Z"
  
Actual Issue:
  issue_id: "issue-456"
  detected_at: "2026-01-22T09:00:00Z"
  status: "open"
```

### 4. Key Relationships

All relationships are between **definitions**:

```
framework_definition --[has_criteria]--> trust_service_criteria_definition
trust_service_criteria --[defines]--> control_objective_definition
control_objective --[satisfied_by]--> control_definition
control_definition --[implemented_by]--> policy_template
control_definition --[requires]--> procedure_definition
procedure_definition --[specifies]--> required_action_template
control_definition --[validated_by]--> expected_evidence_spec
control_definition --[known_failures]--> issue_pattern_definition
```

### 5. Critical Design Principles

**Principle 1: Metadata First**
- Every entity is a definition or template
- No operational state (timestamps, statuses, actual values)
- Focus on "what should be" not "what is"

**Principle 2: Template-Based**
- Action templates define required behaviors
- Evidence specs define validation criteria
- Issue patterns define known failure modes

**Principle 3: Semantic Relationships**
- Relationships enable graph traversal
- Support "why" questions (e.g., "Why is this control needed?")
- Enable multi-hop reasoning (e.g., "What frameworks require MFA?")

**Principle 4: Context as Metadata**
- Domain-specific interpretations stored as context
- Context edges link controls to entities/scenarios
- Enable contextual reasoning (e.g., "For SaaS companies...")

**Principle 5: Agentic Access Only**
- No direct database queries by end users
- All access mediated through agentic workflows
- Agents translate natural language → graph queries → responses

---

## Metadata Models

### Model Philosophy

All models store **definitions, specifications, and relationships** - not operational data.

**Characteristics:**
- No timestamps (except metadata creation/update)
- No status fields (active/inactive is metadata)
- No actual values (only expected values or templates)
- No audit trails (that's operational data)
- Rich metadata in JSONB for extensibility

### Entity Definitions

#### 1. Framework Definition

**Purpose:** Metadata about compliance framework or standard

```yaml
Entity: FrameworkDefinition
Attributes:
  - framework_id: uuid (PK)
  - name: string (e.g., "SOC 2 Type II")
  - code: string (e.g., "SOC2")
  - version: string (e.g., "2017")
  - issuing_body: string (e.g., "AICPA")
  - description: text
  - scope: text (what this framework covers)
  - applicability: jsonb (industry, company size, etc.)
  - documentation_url: string
  - metadata: jsonb
    - publication_date: date
    - revision_history: array
    - related_standards: array
  - created_at: timestamp (metadata only)
  - updated_at: timestamp (metadata only)

Indexes:
  - name, code (unique)
  - issuing_body
```

#### 2. Trust Service Criteria Definition

**Purpose:** High-level category or principle within framework

```yaml
Entity: TrustServiceCriteriaDefinition
Attributes:
  - tsc_id: uuid (PK)
  - framework_id: uuid (FK → FrameworkDefinition)
  - code: string (e.g., "CC6")
  - name: string (e.g., "Logical and Physical Access Controls")
  - description: text (detailed explanation)
  - category: enum (confidentiality, availability, integrity, security, privacy)
  - focus_area: text (what this TSC addresses)
  - metadata: jsonb
    - scope: text
    - key_concepts: array
    - related_tsc: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - framework_id
  - code (unique within framework)
  - category
```

#### 3. Control Objective Definition

**Purpose:** Specification of desired outcome

```yaml
Entity: ControlObjectiveDefinition
Attributes:
  - objective_id: uuid (PK)
  - tsc_id: uuid (FK → TrustServiceCriteriaDefinition)
  - code: string (e.g., "CC6.1-OBJ1")
  - description: text (what must be achieved)
  - success_criteria: text (how to measure achievement)
  - rationale: text (why this objective exists)
  - risk_if_unmet: text (what happens if objective not met)
  - metadata: jsonb
    - related_objectives: array
    - industry_interpretations: object
    - regulatory_references: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - tsc_id
  - code (unique within TSC)
```

#### 4. Control Definition

**Purpose:** Specification of control mechanism

```yaml
Entity: ControlDefinition
Attributes:
  - control_id: uuid (PK)
  - code: string (e.g., "CC6.1")
  - name: string (e.g., "Logical Access Controls")
  - description: text (detailed control specification)
  - control_type: enum (preventive, detective, corrective)
  - automation_potential: enum (manual, semi_automated, fully_automated)
  - implementation_guidance: text
  - testing_guidance: text
  - frequency_guidance: enum (continuous, daily, weekly, monthly, quarterly, annual)
  - owner_role_guidance: string (recommended owner)
  - metadata: jsonb
    - implementation_examples: array
    - common_technologies: array
    - industry_specific_notes: object
    - difficulty_level: enum
    - estimated_effort: string
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - code (unique)
  - control_type
  - automation_potential

Relationships:
  - satisfies (many-to-many with ControlObjectiveDefinition)
  - implemented_by (many-to-many with PolicyTemplate)
```

#### 5. Policy Template

**Purpose:** Template for company policy

```yaml
Entity: PolicyTemplate
Attributes:
  - policy_id: uuid (PK)
  - name: string (e.g., "Access Control Policy Template")
  - policy_type: enum (security, privacy, operational, legal)
  - description: text
  - template_content: text (policy template with placeholders)
  - required_sections: jsonb (structure of policy)
  - approval_requirements: text (who should approve)
  - review_frequency_guidance: enum (annual, semi_annual, quarterly)
  - scope_guidance: text (what should be covered)
  - metadata: jsonb
    - sample_policies: array
    - customization_points: array
    - industry_variations: object
    - related_policies: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - name
  - policy_type
```

#### 6. Procedure Definition

**Purpose:** Specification of operational workflow

```yaml
Entity: ProcedureDefinition
Attributes:
  - procedure_id: uuid (PK)
  - control_id: uuid (FK → ControlDefinition)
  - policy_id: uuid (FK → PolicyTemplate, optional)
  - name: string (e.g., "Quarterly User Access Review")
  - description: text
  - procedure_steps: jsonb (structured step-by-step)
    - step_number: int
    - step_name: string
    - step_description: text
    - responsible_role: string
    - expected_duration: string
    - dependencies: array
  - frequency_specification: enum (continuous, daily, weekly, monthly, quarterly, annual)
  - responsible_role_guidance: string
  - prerequisites: text
  - success_criteria: text
  - automation_guidance: text
  - metadata: jsonb
    - tool_recommendations: array
    - common_pitfalls: array
    - best_practices: array
    - flowchart_url: string
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - control_id
  - policy_id
  - frequency_specification
```

#### 7. Required Action Template

**Purpose:** Specification of actions needed for procedure

```yaml
Entity: RequiredActionTemplate
Attributes:
  - action_template_id: uuid (PK)
  - procedure_id: uuid (FK → ProcedureDefinition)
  - action_type: string (e.g., "approve_access", "generate_report")
  - action_name: string
  - action_description: text (what should happen)
  - actor_role_requirement: string (who should do it)
  - actor_type: enum (human, system, automated_agent)
  - system_recommendation: string (recommended system)
  - target_resource_type: string (what is acted upon)
  - expected_outcome_specification: jsonb
    - success_conditions: array
    - failure_conditions: array
    - side_effects: array
  - timing_requirements: jsonb
    - frequency: string
    - sla: string
    - sequence_order: int
  - quality_criteria: jsonb (how to assess action quality)
  - automation_guidance: text
  - metadata: jsonb
    - examples: array
    - tools: array
    - scripts: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - procedure_id
  - action_type
  - actor_role_requirement
```

#### 8. Expected Evidence Specification

**Purpose:** Specification of evidence requirements

```yaml
Entity: ExpectedEvidenceSpecification
Attributes:
  - evidence_spec_id: uuid (PK)
  - evidence_type: enum (log, document, screenshot, report, api_response, database_query)
  - evidence_name: string
  - description: text (what this evidence proves)
  - source_system_recommendation: string
  - collection_method_guidance: enum (automated, manual, api_pull, query)
  - content_requirements: jsonb
    - required_fields: array
    - format_specification: string
    - validation_rules: array
  - freshness_requirement: string (e.g., "30 days", "real-time")
  - retention_requirement: string (how long to keep)
  - verification_criteria: jsonb (how to validate evidence)
  - sampling_guidance: text (if full population not needed)
  - metadata: jsonb
    - collection_scripts: array
    - query_examples: array
    - api_endpoints: array
    - common_issues: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - evidence_type
  - source_system_recommendation

Relationships:
  - validates (many-to-many with ControlDefinition)
  - produced_by (many-to-many with RequiredActionTemplate)
```

#### 9. Issue Pattern Definition

**Purpose:** Known compliance failure patterns

```yaml
Entity: IssuePatternDefinition
Attributes:
  - pattern_id: uuid (PK)
  - pattern_type: enum (missing_action, invalid_action, missing_evidence, 
                        weak_evidence, control_gap, policy_violation)
  - pattern_name: string
  - description: text (what this failure looks like)
  - detection_method: text (how to identify this pattern)
  - severity_guidance: enum (critical, high, medium, low)
  - root_cause_guidance: text (common root causes)
  - remediation_template: text (how to fix)
  - prevention_guidance: text (how to prevent)
  - indicators: jsonb (signals this issue exists)
  - metadata: jsonb
    - real_world_examples: array
    - related_patterns: array
    - automated_detection: object
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - pattern_type
  - pattern_name

Relationships:
  - impacts (many-to-many with ControlDefinition)
  - caused_by_missing (many-to-many with RequiredActionTemplate)
```

#### 10. Context Definition

**Purpose:** Domain-specific or entity-specific contexts

```yaml
Entity: ContextDefinition
Attributes:
  - context_id: uuid (PK)
  - context_type: enum (entity, policy, domain_knowledge, scenario)
  - name: string (e.g., "SaaS Company Access Management")
  - description: text
  - applicability: text (when this context applies)
  - interpretation_guidance: text (how to interpret controls in this context)
  - specific_requirements: jsonb
  - metadata: jsonb
    - industry: string
    - company_size: string
    - technology_stack: array
    - related_contexts: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - context_type
  - name
```

### Relationship Tables (Many-to-Many)

```yaml
# Control satisfies multiple objectives
ControlObjectiveMapping:
  - control_id: uuid (FK → ControlDefinition)
  - objective_id: uuid (FK → ControlObjectiveDefinition)
  - sufficiency: enum (fully_satisfies, partially_satisfies, contributes_to)
  - notes: text
  - PRIMARY KEY (control_id, objective_id)

# Control implemented by multiple policies
ControlPolicyMapping:
  - control_id: uuid (FK → ControlDefinition)
  - policy_id: uuid (FK → PolicyTemplate)
  - implementation_notes: text
  - PRIMARY KEY (control_id, policy_id)

# Evidence validates multiple controls
EvidenceControlMapping:
  - evidence_spec_id: uuid (FK → ExpectedEvidenceSpecification)
  - control_id: uuid (FK → ControlDefinition)
  - validation_strength: enum (strong, moderate, weak)
  - notes: text
  - PRIMARY KEY (evidence_spec_id, control_id)

# Evidence produced by actions
EvidenceActionMapping:
  - evidence_spec_id: uuid (FK → ExpectedEvidenceSpecification)
  - action_template_id: uuid (FK → RequiredActionTemplate)
  - production_method: text
  - PRIMARY KEY (evidence_spec_id, action_template_id)

# Issue patterns impact controls
IssuePatternControlMapping:
  - pattern_id: uuid (FK → IssuePatternDefinition)
  - control_id: uuid (FK → ControlDefinition)
  - impact_type: enum (blocks, degrades, informational)
  - impact_description: text
  - PRIMARY KEY (pattern_id, control_id)

# Contextual edges (key for reasoning)
ContextualEdge:
  - edge_id: uuid (PK)
  - source_type: enum (context, control, entity, procedure)
  - source_id: uuid
  - relationship_type: enum (applies_to, requires, related_to, interprets)
  - target_type: enum (context, control, entity, procedure)
  - target_id: uuid
  - relationship_strength: float (0.0 - 1.0)
  - metadata: jsonb
    - reasoning: text
    - examples: array
  - PRIMARY KEY (source_type, source_id, target_type, target_id, relationship_type)

Indexes:
  - source_type, source_id
  - target_type, target_id
  - relationship_type
```

### Vector Embeddings (for Semantic Search)

```yaml
# All text-heavy entities embedded in vector store
EmbeddedEntity:
  - entity_type: enum (framework, tsc, objective, control, policy, procedure, 
                       action_template, evidence_spec, issue_pattern, context)
  - entity_id: uuid
  - embedding: vector(1536) (e.g., OpenAI ada-002)
  - text_content: text (what was embedded)
  - metadata: jsonb (original entity metadata)

Collections:
  - framework_definitions
  - control_definitions
  - procedure_definitions
  - context_definitions
  - evidence_specifications
  - etc.
```

---

## Product/Domain Knowledge Models

### Overview

**Purpose:** Map product-specific entities (Snyk vulnerabilities, AWS resources, data tables, etc.) to compliance requirements, enabling contextual queries like "Which vulnerabilities impact SOC 2?" or "Prioritize Snyk findings for audit."

**Key Insight:** The contextual compliance graph bridges TWO knowledge domains:
1. **Compliance Knowledge** (frameworks, controls, requirements)
2. **Product Knowledge** (security tools, business entities, technical assets)

The **contextual edges** between these domains enable sophisticated reasoning.

### Product Knowledge Entities

#### 1. Product Definition

**Purpose:** Metadata about security/compliance products and tools

```yaml
Entity: ProductDefinition
Attributes:
  - product_id: uuid (PK)
  - name: string (e.g., "Snyk", "AWS Security Hub", "Okta")
  - product_type: enum (vulnerability_scanner, iam, siem, cloud_security, asset_mgmt)
  - vendor: string
  - description: text
  - capabilities: jsonb (what this product does)
    - vulnerability_scanning: boolean
    - access_management: boolean
    - monitoring: boolean
    - etc.
  - integration_methods: jsonb
    - api: object (endpoints, authentication)
    - webhook: object
    - export: object (formats, schedules)
  - metadata: jsonb
    - documentation_url: string
    - typical_users: array (who uses this product)
    - compliance_relevance: array (which frameworks it helps with)
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - name (unique)
  - product_type
  - vendor
```

#### 2. Entity Schema Definition

**Purpose:** Define entities/objects within products (e.g., Snyk vulnerabilities, AWS EC2 instances)

```yaml
Entity: EntitySchemaDefinition
Attributes:
  - schema_id: uuid (PK)
  - product_id: uuid (FK → ProductDefinition)
  - entity_name: string (e.g., "vulnerability", "user", "resource")
  - entity_type: enum (finding, asset, identity, configuration, event)
  - description: text
  - schema_definition: jsonb (structure of this entity)
    - fields: array
      - field_name: string
      - field_type: string
      - description: text
      - required: boolean
      - enum_values: array (if applicable)
  - example_entity: jsonb (sample data)
  - compliance_significance: text (why this entity matters for compliance)
  - metadata: jsonb
    - api_endpoint: string (where to fetch these entities)
    - query_examples: array
    - common_filters: array
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - product_id
  - entity_name
  - entity_type

Example:
  product: "Snyk"
  entity_name: "vulnerability"
  schema_definition:
    fields:
      - {name: "id", type: "string", required: true}
      - {name: "severity", type: "enum", enum_values: ["critical", "high", "medium", "low"]}
      - {name: "package_name", type: "string"}
      - {name: "cvss_score", type: "float"}
      - {name: "exploit_maturity", type: "enum", enum_values: ["mature", "proof-of-concept", "no-known-exploit"]}
      - {name: "fixable", type: "boolean"}
      - {name: "introduced_date", type: "timestamp"}
```

#### 3. Field Mapping Definition

**Purpose:** Map product fields to compliance concepts

```yaml
Entity: FieldMappingDefinition
Attributes:
  - mapping_id: uuid (PK)
  - schema_id: uuid (FK → EntitySchemaDefinition)
  - field_name: string
  - compliance_concept: string (what this field represents in compliance terms)
  - mapping_type: enum (direct, derived, calculated, contextual)
  - mapping_logic: text (how to interpret this field)
  - relevance_to_controls: jsonb
    - control_id: uuid
    - relevance: enum (critical, high, medium, low)
    - usage: text (how this field is used for this control)
  - example_values: jsonb
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - schema_id
  - field_name
  - compliance_concept

Example:
  field_name: "severity"
  compliance_concept: "risk_level"
  mapping_logic: "Critical/High severity vulnerabilities require immediate remediation per SOC2 CC7.2"
  relevance_to_controls:
    - {control_id: "cc7.2_uuid", relevance: "critical", usage: "Determines remediation SLA"}
    - {control_id: "cc7.1_uuid", relevance: "high", usage: "Triggers security review process"}
```

#### 4. Business Entity Definition

**Purpose:** Define business-level entities that compliance applies to

```yaml
Entity: BusinessEntityDefinition
Attributes:
  - entity_id: uuid (PK)
  - entity_type: enum (application, service, database, api, infrastructure, data_store)
  - name: string (e.g., "Customer Portal", "Payment API", "User Database")
  - description: text
  - criticality: enum (critical, high, medium, low)
  - data_classification: enum (public, internal, confidential, restricted)
  - compliance_scope: jsonb
    - frameworks: array (which frameworks apply)
    - controls: array (which controls are relevant)
    - data_types: array (PII, PHI, PCI, etc.)
  - ownership: jsonb
    - business_owner: string
    - technical_owner: string
    - compliance_owner: string
  - metadata: jsonb
    - aws_resources: array (if AWS-based)
    - github_repos: array (if code-based)
    - snyk_projects: array (if monitored by Snyk)
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - entity_type
  - criticality
  - data_classification

Example:
  name: "Payment Processing API"
  entity_type: "api"
  criticality: "critical"
  data_classification: "restricted"
  compliance_scope:
    frameworks: ["SOC2", "PCI-DSS"]
    controls: ["CC6.1", "CC6.6", "CC7.2"]
    data_types: ["PCI", "PII"]
  metadata:
    snyk_projects: ["org/payment-api"]
    aws_resources: ["api-gateway/payment", "lambda/process-payment"]
```

#### 5. Contextual Mapping (Product → Compliance)

**Purpose:** Map product entities/findings to compliance controls

```yaml
Entity: ProductComplianceMapping
Attributes:
  - mapping_id: uuid (PK)
  - source_type: enum (product_entity, schema_field, business_entity)
  - source_id: uuid
  - target_type: enum (control, procedure, evidence_spec, issue_pattern)
  - target_id: uuid
  - mapping_type: enum (provides_evidence, indicates_risk, satisfies_requirement, violates_policy)
  - mapping_strength: float (0.0 - 1.0)
  - mapping_logic: text (how this mapping works)
  - conditions: jsonb (when this mapping applies)
  - examples: jsonb (real-world examples)
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - source_type, source_id
  - target_type, target_id
  - mapping_type
  - mapping_strength

Example 1: Snyk vulnerability → SOC 2 control
  source_type: "product_entity"
  source_id: "snyk_vulnerability_schema_id"
  target_type: "control"
  target_id: "cc7.2_uuid"
  mapping_type: "indicates_risk"
  mapping_strength: 0.9
  mapping_logic: "High/Critical Snyk vulnerabilities in production indicate potential CC7.2 control failure"
  conditions:
    - {field: "severity", operator: "in", values: ["critical", "high"]}
    - {field: "environment", operator: "eq", value: "production"}
  examples:
    - "Critical SQL injection in payment API → CC7.2 risk"
    - "High severity RCE in customer portal → CC7.2 risk"

Example 2: Snyk vulnerability → Evidence spec
  source_type: "product_entity"
  source_id: "snyk_vulnerability_schema_id"
  target_type: "evidence_spec"
  target_id: "vulnerability_scan_evidence_uuid"
  mapping_type: "provides_evidence"
  mapping_strength: 1.0
  mapping_logic: "Snyk scan results serve as evidence of vulnerability management process"
  conditions: []
  examples:
    - "Weekly Snyk scans → Evidence for CC7.1 vulnerability monitoring"
```

#### 6. Goal-Oriented Query Template

**Purpose:** Define common user goals and how to achieve them using the knowledge graph

```yaml
Entity: GoalQueryTemplate
Attributes:
  - goal_id: uuid (PK)
  - goal_name: string (e.g., "Prioritize vulnerabilities for SOC2 audit")
  - goal_type: enum (prioritization, gap_analysis, evidence_collection, risk_assessment)
  - description: text
  - user_personas: array (who typically has this goal)
  - query_pattern: text (natural language pattern)
  - query_logic: jsonb (how to execute this query)
    - step_1: string
    - step_2: string
    - etc.
  - required_mappings: array (which product→compliance mappings are needed)
  - example_queries: array
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - goal_type
  - user_personas

Example:
  goal_name: "Prioritize Snyk vulnerabilities for SOC 2 audit"
  goal_type: "prioritization"
  user_personas: ["security_engineer", "compliance_manager"]
  query_pattern: "Prioritize [product] findings for [framework] [event]"
  query_logic:
    step_1: "Identify relevant SOC 2 controls for vulnerability management"
    step_2: "Map Snyk vulnerabilities to these controls using ProductComplianceMapping"
    step_3: "Filter vulnerabilities by: severity + SOC2 relevance + business criticality"
    step_4: "Score vulnerabilities: (severity × compliance_impact × business_criticality)"
    step_5: "Return prioritized list with remediation guidance"
  required_mappings: ["snyk_vulnerability → CC7.1", "snyk_vulnerability → CC7.2"]
  example_queries:
    - "Which Snyk vulnerabilities should I fix first for SOC 2?"
    - "Prioritize our security findings for the upcoming audit"
    - "What vulnerabilities pose the highest compliance risk?"
```

### Relationship Tables (Product ↔ Compliance)

```yaml
# Product entities map to compliance controls
ProductEntityControlMapping:
  - schema_id: uuid (FK → EntitySchemaDefinition)
  - control_id: uuid (FK → ControlDefinition)
  - relationship_type: enum (provides_evidence, indicates_compliance, signals_risk)
  - conditions: jsonb (when this relationship holds)
  - PRIMARY KEY (schema_id, control_id)

# Business entities map to compliance scope
BusinessEntityComplianceScope:
  - entity_id: uuid (FK → BusinessEntityDefinition)
  - control_id: uuid (FK → ControlDefinition)
  - applicability: enum (required, recommended, optional, not_applicable)
  - rationale: text
  - PRIMARY KEY (entity_id, control_id)

# Product fields map to evidence requirements
FieldEvidenceMapping:
  - mapping_id: uuid (FK → FieldMappingDefinition)
  - evidence_spec_id: uuid (FK → ExpectedEvidenceSpecification)
  - field_role: enum (primary_evidence, supporting_evidence, validation_criteria)
  - PRIMARY KEY (mapping_id, evidence_spec_id)
```

### Example: Complete Snyk → SOC 2 Mapping

```yaml
# Product Definition
Snyk:
  product_id: "snyk_uuid"
  name: "Snyk"
  product_type: "vulnerability_scanner"
  capabilities:
    vulnerability_scanning: true
    license_compliance: true
    container_security: true

# Entity Schema
SnykVulnerability:
  schema_id: "snyk_vuln_schema_uuid"
  product_id: "snyk_uuid"
  entity_name: "vulnerability"
  schema_definition:
    fields:
      - {name: "severity", type: "enum", values: ["critical", "high", "medium", "low"]}
      - {name: "cvss_score", type: "float"}
      - {name: "exploit_maturity", type: "enum"}
      - {name: "fixable", type: "boolean"}
      - {name: "package_name", type: "string"}

# Field Mappings
SeverityMapping:
  field_name: "severity"
  compliance_concept: "risk_level"
  relevance_to_controls:
    - {control_id: "CC7.2", relevance: "critical"}
    - {control_id: "CC7.1", relevance: "high"}

FixableMapping:
  field_name: "fixable"
  compliance_concept: "remediability"
  relevance_to_controls:
    - {control_id: "CC7.2", relevance: "high", usage: "Prioritize fixable vulnerabilities"}

# Product → Compliance Mappings
CriticalVulnMapping:
  source: "SnykVulnerability"
  target: "CC7.2"
  mapping_type: "indicates_risk"
  conditions:
    - {field: "severity", operator: "in", values: ["critical", "high"]}
  mapping_logic: "Critical/High Snyk vulnerabilities indicate CC7.2 risk requiring immediate action"

VulnScanEvidenceMapping:
  source: "SnykVulnerability"
  target: "vulnerability_scan_evidence_spec"
  mapping_type: "provides_evidence"
  mapping_logic: "Snyk scan results serve as evidence of CC7.1 vulnerability monitoring"
```

---

#### 1. Framework

**Purpose:** Top-level compliance standard or regulatory regime

```yaml
Entity: Framework
Attributes:
  - framework_id: uuid (PK)
  - name: string (e.g., "SOC 2 Type II")
  - version: string (e.g., "2017")
  - effective_date: timestamp
  - issuing_body: string (e.g., "AICPA")
  - scope: text (description)
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - name (unique)
  - effective_date
```

#### 2. Trust Service Criteria (TSC)

**Purpose:** High-level category or principle within a framework

```yaml
Entity: TrustServiceCriteria
Attributes:
  - tsc_id: uuid (PK)
  - framework_id: uuid (FK → Framework)
  - code: string (e.g., "CC6")
  - name: string (e.g., "Logical and Physical Access Controls")
  - description: text
  - category: enum (confidentiality, availability, integrity, security, privacy)
  - weight: float (for risk scoring)
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - framework_id
  - code (unique within framework)
  - category
```

#### 3. Control Objective

**Purpose:** Specific outcome that must be achieved to satisfy criteria

```yaml
Entity: ControlObjective
Attributes:
  - objective_id: uuid (PK)
  - tsc_id: uuid (FK → TrustServiceCriteria)
  - code: string (e.g., "CC6.1-OBJ1")
  - description: text (e.g., "Ensure access is restricted to authorized users")
  - success_criteria: text (measurable outcomes)
  - risk_level: enum (critical, high, medium, low)
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - tsc_id
  - code (unique within TSC)
  - risk_level
```

#### 4. Control

**Purpose:** Specific mechanism or practice to achieve objective

```yaml
Entity: Control
Attributes:
  - control_id: uuid (PK)
  - code: string (e.g., "CC6.1")
  - name: string (e.g., "Logical Access Controls")
  - description: text
  - control_type: enum (preventive, detective, corrective)
  - automation_level: enum (manual, semi_automated, automated)
  - frequency: enum (continuous, daily, weekly, monthly, quarterly, annual)
  - owner_role: string
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - code (unique)
  - control_type
  - automation_level
  - owner_role

Relationships:
  - control_objectives (many-to-many)
  - policies (many-to-many)
  - procedures (one-to-many)
```

#### 5. Policy

**Purpose:** Company directive or rule supporting controls

```yaml
Entity: Policy
Attributes:
  - policy_id: uuid (PK)
  - name: string (e.g., "Access Control Policy")
  - version: string
  - effective_date: timestamp
  - review_date: timestamp
  - owner: string
  - approval_status: enum (draft, approved, active, deprecated)
  - scope: text
  - content: text
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - name
  - effective_date
  - approval_status
  - owner
```

#### 6. Procedure

**Purpose:** Operational workflow executing a policy

```yaml
Entity: Procedure
Attributes:
  - procedure_id: uuid (PK)
  - control_id: uuid (FK → Control)
  - policy_id: uuid (FK → Policy)
  - name: string (e.g., "Quarterly User Access Review")
  - description: text (step-by-step instructions)
  - frequency: enum (continuous, daily, weekly, monthly, quarterly, annual)
  - duration_estimate: interval
  - responsible_role: string
  - approval_required: boolean
  - automation_status: enum (manual, scripted, automated)
  - sla: interval (expected completion time)
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - control_id
  - policy_id
  - frequency
  - responsible_role
```

#### 7. User Action

**Purpose:** Time-bound, attributable event performed by human or system

```yaml
Entity: UserAction
Attributes:
  - action_id: uuid (PK)
  - procedure_id: uuid (FK → Procedure)
  - action_type: string (e.g., "approve_access", "review_completed")
  - actor_id: string (user/service account)
  - actor_role: string
  - actor_type: enum (human, system, automated_agent)
  - system_source: string (e.g., "IAM", "ServiceNow", "GitHub")
  - target_resource: string (what was acted upon)
  - timestamp: timestamp
  - expected_outcome: jsonb
  - actual_outcome: jsonb
  - outcome_match: boolean (did actual match expected?)
  - quality_score: float (0.0 - 1.0)
  - metadata: jsonb (original event payload)
  - created_at: timestamp

Indexes:
  - procedure_id
  - action_type
  - actor_id
  - actor_role
  - system_source
  - timestamp
  - quality_score

Quality Dimensions:
  - timeliness: Was it done on time?
  - completeness: Were all required steps taken?
  - authority: Did the right role perform it?
  - outcome_validity: Did it change system state appropriately?
  - consistency: Does it match historical behavior?
```

#### 8. Evidence

**Purpose:** Verifiable artifact proving action occurred

```yaml
Entity: Evidence
Attributes:
  - evidence_id: uuid (PK)
  - evidence_type: enum (log, document, screenshot, report, api_response)
  - source_system: string
  - collection_method: enum (automated, manual, api_pull)
  - content_type: string (mime type)
  - content_location: string (S3 path, URL, etc.)
  - content_hash: string (SHA-256)
  - collected_at: timestamp
  - valid_from: timestamp
  - valid_until: timestamp (evidence expiration)
  - collector_id: string (who/what collected it)
  - verification_status: enum (pending, verified, invalid, expired)
  - metadata: jsonb
  - created_at: timestamp

Indexes:
  - evidence_type
  - source_system
  - verification_status
  - valid_from, valid_until (range index)
  - content_hash (unique)

Relationships:
  - user_actions (many-to-many) - which actions produced this evidence
  - controls (many-to-many) - which controls this evidence supports
```

#### 9. Issue / Finding

**Purpose:** Compliance gap or control failure

```yaml
Entity: Issue
Attributes:
  - issue_id: uuid (PK)
  - issue_type: enum (missing_action, invalid_action, missing_evidence, 
                      weak_evidence, control_failure, policy_violation)
  - severity: enum (critical, high, medium, low, info)
  - status: enum (open, in_progress, resolved, accepted_risk, false_positive)
  - title: string
  - description: text
  - root_cause: text
  - remediation_plan: text
  - detected_at: timestamp
  - resolved_at: timestamp
  - detected_by: string (system, agent, human)
  - assigned_to: string
  - sla_due_date: timestamp
  - risk_score: float (likelihood × impact)
  - metadata: jsonb
  - created_at: timestamp
  - updated_at: timestamp

Indexes:
  - issue_type
  - severity
  - status
  - detected_at
  - risk_score

Relationships:
  - controls (many-to-many) - which controls are impacted
  - procedures (many-to-many) - which procedures failed
  - user_actions (many-to-many) - which actions (or missing actions) caused this
  - evidence (many-to-many) - related evidence
```

### Relationship Tables (Many-to-Many)

```yaml
# Control satisfies multiple objectives
ControlObjectiveMapping:
  - control_id: uuid (FK)
  - objective_id: uuid (FK)
  - effectiveness_contribution: float (0.0 - 1.0)
  - PRIMARY KEY (control_id, objective_id)

# Control implemented by multiple policies
ControlPolicyMapping:
  - control_id: uuid (FK)
  - policy_id: uuid (FK)
  - PRIMARY KEY (control_id, policy_id)

# Evidence supports multiple controls
EvidenceControlMapping:
  - evidence_id: uuid (FK)
  - control_id: uuid (FK)
  - relevance_score: float (0.0 - 1.0)
  - PRIMARY KEY (evidence_id, control_id)

# Evidence produced by multiple actions
EvidenceActionMapping:
  - evidence_id: uuid (FK)
  - action_id: uuid (FK)
  - PRIMARY KEY (evidence_id, action_id)

# Issue impacts multiple controls
IssueControlMapping:
  - issue_id: uuid (FK)
  - control_id: uuid (FK)
  - impact_level: enum (blocks, degrades, informational)
  - PRIMARY KEY (issue_id, control_id)

# Issue caused by user actions
IssueActionMapping:
  - issue_id: uuid (FK)
  - action_id: uuid (FK)
  - causation_type: enum (missing_action, invalid_action, late_action)
  - PRIMARY KEY (issue_id, action_id)
```

### Computed/Derived Entities

#### Control Effectiveness Score

**Purpose:** Real-time assessment of control health

```yaml
Entity: ControlEffectivenessScore
Attributes:
  - control_id: uuid (PK, FK)
  - score: float (0.0 - 1.0)
  - calculation_timestamp: timestamp
  - factors: jsonb
    - action_completion_rate: float
    - action_quality_avg: float
    - evidence_freshness: float
    - issue_count: int
    - issue_severity_weighted: float
  - trend: enum (improving, stable, degrading)
  - last_validated: timestamp
  - next_validation_due: timestamp

Formula:
  effectiveness = (
    0.3 × action_completion_rate +
    0.3 × action_quality_avg +
    0.2 × evidence_freshness +
    0.2 × (1 - normalized_issue_severity)
  )
```

#### Risk Score

**Purpose:** Quantified risk for controls, objectives, and frameworks

```yaml
Entity: RiskScore
Attributes:
  - entity_type: enum (control, objective, tsc, framework)
  - entity_id: uuid
  - likelihood: float (0.0 - 1.0)
  - impact: float (0.0 - 1.0)
  - risk_score: float (likelihood × impact)
  - risk_level: enum (critical, high, medium, low)
  - calculation_method: enum (fair, monte_carlo, historical, manual)
  - calculation_timestamp: timestamp
  - factors: jsonb
  - confidence_interval: float (for probabilistic methods)
  - PRIMARY KEY (entity_type, entity_id, calculation_timestamp)
```

---

## Agentic Query Interface

### Design Philosophy

**Single Entry Point:** All queries enter through agentic workflows  
**No Direct Access:** No CRUD APIs, no SQL queries, no direct database access  
**Natural Language First:** Queries in plain English, responses in structured + narrative format  
**Context-Aware:** System understands user role, project, and intent  
**Template-Based Responses:** Return definitions, specifications, and guidance

### Interface Architecture

```
┌─────────────────────────────────────┐
│  User Query (Natural Language)      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Agentic Workflow (LangGraph)       │
│  • Intent Classification            │
│  • Context Retrieval                │
│  • Query Planning                   │
│  • Multi-Step Reasoning             │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Knowledge Graph Service            │
│  • Vector Search (semantic)         │
│  • Graph Traversal (relationships)  │
│  • Template Retrieval               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Response Generation                │
│  • Synthesize findings              │
│  • Format for user                  │
│  • Include templates & guidance     │
└──────────────┬──────────────────────┘
               │
               ▼
           User Response
```

### Agentic Query API

#### Primary Query Endpoint

```http
POST /api/v1/query
```

**Purpose:** Accept natural language queries, return contextual responses

**Request:**
```json
{
  "query": "What controls are required for user access management in a SaaS company?",
  "context": {
    "project_id": "my_project",
    "user_role": "compliance_manager",
    "domain": "saas",
    "frameworks": ["SOC2", "ISO27001"]
  },
  "response_preferences": {
    "format": "detailed" | "summary" | "executive",
    "include_templates": true,
    "include_examples": true,
    "include_guidance": true
  },
  "session_id": "uuid" (optional, for multi-turn conversation)
}
```

**Response:**
```json
{
  "query_id": "uuid",
  "session_id": "uuid",
  "query_understanding": {
    "intent": "find_applicable_controls",
    "entities_identified": ["user access management", "SaaS"],
    "frameworks_referenced": ["SOC 2", "ISO 27001"],
    "context_applied": ["saas_company", "access_management"]
  },
  "answer": {
    "summary": "For SaaS companies, user access management requires 8 primary controls across SOC 2 CC6 and ISO 27001 A.9...",
    "detailed_response": "...",
    "structured_data": {
      "controls": [
        {
          "control_id": "uuid",
          "code": "CC6.1",
          "name": "Logical Access Controls",
          "framework": "SOC 2",
          "relevance": "Required for all SaaS companies",
          "saas_specific_guidance": "Implement SSO with MFA, use identity provider...",
          "required_procedures": [
            {
              "procedure_id": "uuid",
              "name": "Quarterly Access Review",
              "description": "..."
            }
          ]
        }
      ]
    }
  },
  "templates": [
    {
      "template_type": "policy",
      "template_id": "uuid",
      "name": "Access Control Policy Template",
      "description": "Pre-configured for SaaS companies",
      "download_url": "/templates/policy/uuid"
    },
    {
      "template_type": "procedure",
      "template_id": "uuid",
      "name": "Access Review Procedure",
      "description": "Step-by-step workflow",
      "download_url": "/templates/procedure/uuid"
    }
  ],
  "evidence_requirements": [
    {
      "evidence_spec_id": "uuid",
      "evidence_type": "audit_log",
      "description": "IAM access logs showing authentication events",
      "freshness": "30 days",
      "required_fields": ["timestamp", "user_id", "action", "result"],
      "collection_guidance": "Export from Okta/Auth0 via API..."
    }
  ],
  "implementation_guidance": {
    "recommended_tools": ["Okta", "Auth0", "JumpCloud"],
    "estimated_effort": "4-6 weeks",
    "prerequisites": ["Identity provider integration", "Role definitions"],
    "common_pitfalls": ["Forgetting service accounts", "Not documenting break-glass procedures"]
  },
  "follow_up_suggestions": [
    "Would you like to see the procedure definitions for these controls?",
    "Should I explain how these controls map to your existing systems?",
    "Would you like guidance on evidence collection?"
  ],
  "reasoning_trace": [
    "Identified query as control discovery request",
    "Retrieved SaaS context definition",
    "Filtered controls by applicability to SaaS + user access",
    "Retrieved contextual edges for SaaS companies",
    "Synthesized guidance from templates"
  ]
}
```

### Query Types

The system supports these query intents:

#### 1. Definition Queries

**Examples:**
- "What is SOC 2 CC6.1?"
- "Explain the difference between CC6.1 and CC6.7"
- "What are the Trust Service Criteria in SOC 2?"

**Response Type:** Framework/control definitions with relationships

#### 2. Requirement Queries

**Examples:**
- "What controls do I need for HIPAA?"
- "What evidence is required for quarterly access reviews?"
- "What actions must be performed for CC6.1?"

**Response Type:** Lists of controls, evidence specs, action templates

#### 3. Implementation Queries

**Examples:**
- "How do I implement least privilege access?"
- "What tools are recommended for access reviews?"
- "Show me a policy template for data classification"

**Response Type:** Procedures, templates, tool recommendations, guidance

#### 4. Relationship Queries

**Examples:**
- "How does SOC 2 CC6 relate to ISO 27001 A.9?"
- "Which controls satisfy multiple frameworks?"
- "What procedures support CC6.1?"

**Response Type:** Graph traversals, relationship mappings

#### 5. Contextual Queries

**Examples:**
- "What controls apply to SaaS companies?"
- "How is 'access control' interpreted in healthcare?"
- "What's different about HIPAA for small organizations?"

**Response Type:** Context-specific interpretations and guidance

#### 6. Gap Analysis Queries

**Examples:**
- "What controls am I missing for SOC 2?"
- "Compare my controls to ISO 27001 requirements"
- "What evidence types am I not collecting?"

**Response Type:** Gap lists, missing definitions, recommendations

#### 7. Template Retrieval Queries

**Examples:**
- "Give me a policy template for incident response"
- "Show me procedure steps for access provisioning"
- "What's a good format for access review reports?"

**Response Type:** Templates with placeholders, examples, guidance

#### 8. Product Mapping Queries

**Examples:**
- "Which Snyk vulnerabilities impact SOC 2?"
- "Map AWS Security Hub findings to HIPAA controls"
- "What Okta events provide evidence for CC6.1?"
- "Which database tables are relevant for PCI-DSS compliance?"

**Response Type:** Product → compliance mappings, field interpretations

#### 9. Goal-Oriented Queries

**Examples:**
- "Prioritize Snyk vulnerabilities for SOC 2 audit"
- "Which AWS resources need HIPAA controls?"
- "Find data tables that handle PII for GDPR"
- "What security findings should I fix first for audit?"

**Response Type:** Prioritized lists, scoring logic, remediation guidance

#### 10. Schema Understanding Queries

**Examples:**
- "What does Snyk's 'exploit_maturity' field mean for compliance?"
- "How should I interpret AWS Security Hub severity levels?"
- "Which Okta log fields are required for access control evidence?"

**Response Type:** Field definitions, compliance interpretations, usage guidance

### Multi-Turn Conversations

**Session Management:**

```http
POST /api/v1/query
{
  "query": "What controls do I need for user access?",
  "context": {...}
}

Response includes: session_id

# Follow-up query
POST /api/v1/query
{
  "query": "Show me the evidence requirements for the first one",
  "session_id": "previous_session_id"
}
```

**The agent maintains:**
- Previously discussed entities (controls, frameworks, procedures)
- User's focus area
- Context stack (domain, role, project)
- Suggested follow-ups

### Template Download Endpoints

```http
# Get specific template
GET /api/v1/templates/{template_type}/{template_id}

# Response: Template content with placeholders
{
  "template_id": "uuid",
  "template_type": "policy",
  "name": "Access Control Policy",
  "content": "# Access Control Policy\n\n## Purpose\n{{PURPOSE}}...",
  "placeholders": [
    {"name": "PURPOSE", "description": "Why this policy exists", "example": "..."},
    {"name": "SCOPE", "description": "What systems this covers", "example": "..."}
  ],
  "usage_guidance": "Fill in placeholders, review with legal, get executive approval",
  "related_templates": ["procedure_access_review", "form_access_request"]
}
```

### Evidence Specification Queries

```http
# Get evidence specs for a control
POST /api/v1/query
{
  "query": "What evidence do I need for CC6.1?",
  "context": {
    "project_id": "my_project",
    "control_id": "cc6.1_uuid"
  }
}

# Response includes:
{
  "evidence_specifications": [
    {
      "evidence_spec_id": "uuid",
      "evidence_type": "audit_log",
      "source_system": "IAM",
      "required_fields": [...],
      "freshness": "30 days",
      "collection_method": "automated",
      "validation_criteria": {...},
      "collection_script": "# Python script to collect from Okta\nimport okta...",
      "query_example": "SELECT * FROM auth_logs WHERE timestamp > NOW() - INTERVAL '30 days'"
    }
  ]
}
```

### Reasoning Transparency

All responses include `reasoning_trace` showing how the agent arrived at the answer:

```json
{
  "reasoning_trace": [
    {
      "step": 1,
      "action": "query_understanding",
      "result": "Identified as control discovery query for SaaS + user access"
    },
    {
      "step": 2,
      "action": "context_retrieval",
      "result": "Retrieved SaaS context definition and related edges"
    },
    {
      "step": 3,
      "action": "semantic_search",
      "result": "Found 12 controls matching 'user access management'"
    },
    {
      "step": 4,
      "action": "context_filtering",
      "result": "Filtered to 8 controls applicable to SaaS companies"
    },
    {
      "step": 5,
      "action": "graph_traversal",
      "result": "Retrieved procedures, templates, and evidence specs"
    },
    {
      "step": 6,
      "action": "synthesis",
      "result": "Generated guidance combining all retrieved metadata"
    }
  ]
}
```

### Error Handling

```json
{
  "error": {
    "code": "INSUFFICIENT_CONTEXT",
    "message": "Need more information to answer this query",
    "clarification_needed": [
      "Which framework? (SOC 2, ISO 27001, HIPAA, or other)",
      "What type of company? (SaaS, Healthcare, Financial, etc.)",
      "Specific focus area? (Access control, Data protection, Monitoring)"
    ],
    "suggested_refinements": [
      "What SOC 2 controls apply to SaaS companies for user access?",
      "Show me ISO 27001 A.9 controls for healthcare organizations"
    ]
  }
}
```

---

1. **Agent-First Design**: APIs optimized for LLM consumption and generation
2. **Semantic Queries**: Support natural language in addition to structured filters
3. **Graph Traversal**: Enable multi-hop queries across hierarchy
4. **Context-Aware**: Return contextually relevant information
5. **Temporal Support**: Query historical state and trends

### API Categories

## Knowledge Graph Structure

### Graph Database Schema

The knowledge graph uses **nodes** (entities) and **edges** (relationships):

#### Node Types

```
# Compliance Knowledge Nodes
1. FrameworkNode
2. TSCNode (Trust Service Criteria)
3. ControlObjectiveNode
4. ControlNode
5. PolicyTemplateNode
6. ProcedureNode
7. ActionTemplateNode
8. EvidenceSpecNode
9. IssuePatternNode
10. ContextNode

# Product/Domain Knowledge Nodes (NEW)
11. ProductNode
12. EntitySchemaNode
13. FieldMappingNode
14. BusinessEntityNode
15. GoalTemplateNode
```

#### Edge Types

```
# Hierarchical relationships (Compliance)
HAS_CRITERIA (Framework → TSC)
DEFINES_OBJECTIVE (TSC → ControlObjective)
SATISFIES (Control → ControlObjective)

# Implementation relationships (Compliance)
IMPLEMENTED_BY (Control → PolicyTemplate)
EXECUTED_BY (Policy → Procedure)
REQUIRES_ACTION (Procedure → ActionTemplate)

# Validation relationships (Compliance)
VALIDATED_BY (Control → EvidenceSpec)
PRODUCES_EVIDENCE (ActionTemplate → EvidenceSpec)

# Risk relationships (Compliance)
CAUSES_FAILURE (IssuePattern → Control)
MITIGATES (Control → IssuePattern)

# Contextual relationships (Compliance)
APPLIES_TO (Context → Control)
INTERPRETS (Context → Control)
RELEVANT_FOR (Context → Procedure)
EXEMPLIFIED_BY (Control → Context)

# Product Knowledge relationships (NEW)
HAS_SCHEMA (Product → EntitySchema)
DEFINES_FIELD (EntitySchema → FieldMapping)
MAPS_TO_CONCEPT (FieldMapping → ComplianceConcept)

# Product ↔ Compliance Bridge (NEW - CRITICAL)
PROVIDES_EVIDENCE_FOR (EntitySchema → Control)
INDICATES_RISK_FOR (EntitySchema → Control)
SATISFIES_REQUIREMENT (EntitySchema → Control)
VIOLATES_POLICY (EntitySchema → Control)
RELEVANT_TO_GOAL (EntitySchema → GoalTemplate)
SCOPED_TO_CONTROL (BusinessEntity → Control)
```

### Contextual Edges (Key Feature)

**Purpose:** Enable context-aware reasoning about compliance

```cypher
# Example: SaaS company context
(SaaSContext:Context {name: "SaaS Company"})
  -[APPLIES_TO {strength: 0.9}]->
(CC6_1:Control {code: "CC6.1"})

(SaaSContext)
  -[INTERPRETS {
    interpretation: "For SaaS: SSO with MFA required, role-based access via IDP",
    specific_requirements: ["SSO", "MFA", "IDP integration"]
  }]->
(CC6_1)

# Example: Healthcare industry context
(HealthcareContext:Context {name: "Healthcare Organization"})
  -[APPLIES_TO {strength: 1.0}]->
(HIPAAControl:Control {code: "HIPAA-164.308"})

(HealthcareContext)
  -[INTERPRETS {
    interpretation: "PHI access must be logged and auditable",
    specific_requirements: ["PHI encryption", "Audit trails", "BAA agreements"]
  }]->
(HIPAAControl)
```

### Query Patterns (Cypher Examples)

#### 1. Find applicable controls for context

```cypher
// Find all controls applicable to SaaS companies
MATCH (ctx:Context {name: "SaaS Company"})
      -[r:APPLIES_TO]->
      (ctrl:Control)
WHERE r.strength > 0.7
RETURN ctrl.code, ctrl.name, r.strength
ORDER BY r.strength DESC
```

#### 2. Traverse framework to procedures

```cypher
// From framework to all procedures
MATCH (f:Framework {code: "SOC2"})
      -[:HAS_CRITERIA]->
      (tsc:TSC)
      -[:DEFINES_OBJECTIVE]->
      (obj:ControlObjective)
      <-[:SATISFIES]-
      (ctrl:Control)
      -[:EXECUTED_BY]->
      (proc:Procedure)
RETURN f.name, tsc.code, ctrl.code, proc.name
```

#### 3. Find evidence requirements

```cypher
// What evidence is needed for a control?
MATCH (ctrl:Control {code: "CC6.1"})
      -[:VALIDATED_BY]->
      (evSpec:EvidenceSpec)
OPTIONAL MATCH (evSpec)
      <-[:PRODUCES_EVIDENCE]-
      (action:ActionTemplate)
      <-[:REQUIRES_ACTION]-
      (proc:Procedure)
RETURN evSpec.evidence_type,
       evSpec.required_fields,
       evSpec.freshness_requirement,
       collect(proc.name) as producing_procedures
```

#### 4. Multi-framework mapping

```cypher
// Controls that satisfy both SOC 2 and ISO 27001
MATCH (soc2:Framework {code: "SOC2"})
      -[:HAS_CRITERIA]->
      (tsc:TSC)
      -[:DEFINES_OBJECTIVE]->
      (obj1:ControlObjective)
      <-[:SATISFIES]-
      (ctrl:Control)
      -[:SATISFIES]->
      (obj2:ControlObjective)
      <-[:DEFINES_OBJECTIVE]-
      (iso_ctrl:TSC)
      <-[:HAS_CRITERIA]-
      (iso:Framework {code: "ISO27001"})
RETURN ctrl.code, ctrl.name, tsc.code as soc2_tsc, iso_ctrl.code as iso_clause
```

#### 5. Contextual interpretation

```cypher
// How is "access control" interpreted for SaaS companies?
MATCH (ctx:Context {name: "SaaS Company"})
      -[interp:INTERPRETS]->
      (ctrl:Control)
WHERE ctrl.name CONTAINS "Access"
RETURN ctrl.code,
       ctrl.name,
       interp.interpretation,
       interp.specific_requirements
```

#### 6. Product entity to compliance control mapping

```cypher
// Which controls are impacted by Snyk vulnerabilities?
MATCH (prod:Product {name: "Snyk"})
      -[:HAS_SCHEMA]->
      (schema:EntitySchema {entity_name: "vulnerability"})
      -[mapping:INDICATES_RISK_FOR]->
      (ctrl:Control)
WHERE mapping.mapping_strength > 0.7
RETURN ctrl.code,
       ctrl.name,
       mapping.mapping_logic,
       mapping.conditions
ORDER BY mapping.mapping_strength DESC
```

#### 7. Goal-oriented query: Prioritize vulnerabilities

```cypher
// Prioritize Snyk vulnerabilities for SOC 2 audit
// Step 1: Find relevant controls
MATCH (f:Framework {code: "SOC2"})
      -[:HAS_CRITERIA]->
      (tsc:TSC)
      -[:DEFINES_OBJECTIVE]->
      (obj:ControlObjective)
      <-[:SATISFIES]-
      (ctrl:Control)
WHERE tsc.code IN ["CC7", "CC8"]  // Security and change management

// Step 2: Map Snyk vulnerabilities to these controls
MATCH (prod:Product {name: "Snyk"})
      -[:HAS_SCHEMA]->
      (schema:EntitySchema {entity_name: "vulnerability"})
      -[mapping:INDICATES_RISK_FOR]->
      (ctrl)

// Step 3: Get field mappings for prioritization
MATCH (schema)
      -[:DEFINES_FIELD]->
      (field:FieldMapping)
WHERE field.field_name IN ["severity", "cvss_score", "exploit_maturity", "fixable"]

// Step 4: Return prioritization guidance
RETURN ctrl.code,
       ctrl.name,
       mapping.mapping_logic,
       mapping.conditions,
       collect(field.compliance_concept) as prioritization_factors,
       mapping.mapping_strength as compliance_impact
ORDER BY mapping.mapping_strength DESC
```

#### 8. Find evidence sources for a control

```cypher
// What product entities provide evidence for CC6.1?
MATCH (ctrl:Control {code: "CC6.1"})
      <-[mapping:PROVIDES_EVIDENCE_FOR]-
      (schema:EntitySchema)
      <-[:HAS_SCHEMA]-
      (prod:Product)
OPTIONAL MATCH (schema)
      -[:DEFINES_FIELD]->
      (field:FieldMapping)
WHERE field.field_role = "primary_evidence"
RETURN prod.name as product,
       schema.entity_name as entity_type,
       collect(field.field_name) as evidence_fields,
       mapping.mapping_logic as collection_guidance
```

#### 9. Business entity compliance scope

```cypher
// What controls apply to the "Payment API" business entity?
MATCH (be:BusinessEntity {name: "Payment Processing API"})
      -[scope:SCOPED_TO_CONTROL]->
      (ctrl:Control)
      -[:SATISFIES]->
      (obj:ControlObjective)
      -[:DEFINED_BY]->
      (tsc:TSC)
      -[:BELONGS_TO]->
      (f:Framework)
WHERE scope.applicability IN ["required", "recommended"]
RETURN f.name as framework,
       tsc.code as category,
       ctrl.code,
       ctrl.name,
       scope.applicability,
       scope.rationale,
       be.criticality,
       be.data_classification
ORDER BY be.criticality DESC, scope.applicability
```

#### 10. Product field interpretation

```cypher
// How should I interpret Snyk's "exploit_maturity" field?
MATCH (prod:Product {name: "Snyk"})
      -[:HAS_SCHEMA]->
      (schema:EntitySchema {entity_name: "vulnerability"})
      -[:DEFINES_FIELD]->
      (field:FieldMapping {field_name: "exploit_maturity"})
      -[:MAPS_TO_CONCEPT]->
      (concept:ComplianceConcept)
OPTIONAL MATCH (field)
      -[:RELEVANT_TO]-
      (ctrl:Control)
RETURN field.field_name,
       field.compliance_concept,
       field.mapping_logic,
       field.example_values,
       collect({
         control: ctrl.code,
         usage: ctrl.usage_guidance
       }) as control_usage
```

### Vector Embeddings Layer

**Purpose:** Enable semantic search over definitions

```
┌─────────────────────────────────────┐
│  ChromaDB / QDrantDB Collections    │
├─────────────────────────────────────┤
│  frameworks (embedded descriptions) │
│  controls (embedded definitions)    │
│  procedures (embedded steps)        │
│  contexts (embedded applicability)  │
│  evidence_specs (embedded reqs)     │
└─────────────────────────────────────┘
         ↕ Semantic Search
┌─────────────────────────────────────┐
│  User Query (natural language)      │
│  "Find controls for API security"   │
└─────────────────────────────────────┘
```

**Search Flow:**
1. Embed query: "Find controls for API security"
2. Search `controls` collection with similarity
3. Return top K matching controls (cosine similarity > 0.7)
4. Retrieve full metadata from graph database
5. Follow contextual edges for refinement
6. Return structured + narrative response

### Hybrid Search Strategy

**Combination of:**
1. **Vector search** for semantic similarity
2. **Graph traversal** for relationships
3. **Metadata filtering** for exact matches
4. **Contextual edges** for interpretation

**Example:**
```
Query: "What controls do SaaS companies need for user authentication?"

Step 1: Vector search
  - Find controls matching "user authentication"
  - Results: CC6.1, CC6.6, CC6.7, ISO-A.9.2, ISO-A.9.4

Step 2: Graph filter
  - Filter by framework (if specified)
  - Filter by control_type (preventive/detective)

Step 3: Context enhancement
  - Retrieve edges: (SaaSContext)-[:APPLIES_TO]->(Controls)
  - Filter to controls with strength > 0.7

Step 4: Enrichment
  - Traverse to procedures, templates, evidence specs
  - Add SaaS-specific interpretations from edges

Step 5: Synthesis
  - Combine findings
  - Generate response with context-aware guidance
```

---

#### Get Framework Hierarchy

```http
GET /api/v1/frameworks/{framework_id}/hierarchy
```

**Purpose:** Retrieve complete hierarchy for a framework

**Query Parameters:**
```yaml
depth: integer (default: all, max levels to traverse)
include_scores: boolean (default: false, include effectiveness scores)
include_issues: boolean (default: false, include open issues)
filter_by_risk: enum (critical, high, medium, low)
```

**Response:**
```json
{
  "framework": {
    "framework_id": "uuid",
    "name": "SOC 2 Type II",
    "version": "2017",
    "effectiveness_score": 0.87,
    "risk_score": 0.23
  },
  "trust_service_criteria": [
    {
      "tsc_id": "uuid",
      "code": "CC6",
      "name": "Logical and Physical Access Controls",
      "effectiveness_score": 0.82,
      "risk_score": 0.31,
      "control_objectives": [
        {
          "objective_id": "uuid",
          "description": "Access restricted to authorized users",
          "risk_level": "high",
          "controls": [
            {
              "control_id": "uuid",
              "code": "CC6.1",
              "name": "Logical Access Controls",
              "effectiveness_score": 0.78,
              "open_issues_count": 2,
              "procedures": [...]
            }
          ]
        }
      ]
    }
  ]
}
```

#### Traverse Control to Evidence

```http
GET /api/v1/controls/{control_id}/evidence-chain
```

**Purpose:** Trace from control down to evidence and actions

**Response:**
```json
{
  "control": {...},
  "procedures": [
    {
      "procedure_id": "uuid",
      "name": "Quarterly Access Review",
      "required_actions": [
        {
          "action_type": "generate_access_report",
          "frequency": "quarterly",
          "last_performed": "2026-01-15T10:00:00Z",
          "next_due": "2026-04-15T10:00:00Z",
          "completion_rate": 0.95
        }
      ],
      "recent_actions": [
        {
          "action_id": "uuid",
          "action_type": "review_completed",
          "actor": "manager@company.com",
          "timestamp": "2026-01-20T14:30:00Z",
          "quality_score": 0.6,
          "evidence": [
            {
              "evidence_id": "uuid",
              "evidence_type": "report",
              "verification_status": "verified",
              "collected_at": "2026-01-20T14:35:00Z"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Reverse Lookup: Issue to Framework

```http
GET /api/v1/issues/{issue_id}/impact-chain
```

**Purpose:** Understand which frameworks/controls an issue impacts

**Response:**
```json
{
  "issue": {
    "issue_id": "uuid",
    "title": "Access review completed without revocations",
    "severity": "high",
    "risk_score": 0.42
  },
  "impact_chain": {
    "procedures": [
      {
        "procedure_id": "uuid",
        "name": "Quarterly Access Review",
        "impact": "effectiveness reduced by 40%"
      }
    ],
    "controls": [
      {
        "control_id": "uuid",
        "code": "CC6.1",
        "impact": "detection capability compromised"
      }
    ],
    "objectives": [
      {
        "objective_id": "uuid",
        "description": "Access restricted to authorized users",
        "risk_increase": 0.15
      }
    ],
    "trust_service_criteria": [
      {
        "tsc_id": "uuid",
        "code": "CC6",
        "impact": "partial failure"
      }
    ],
    "frameworks": [
      {
        "framework_id": "uuid",
        "name": "SOC 2 Type II",
        "compliance_status": "at_risk"
      }
    ]
  }
}
```

---

### 2. Entity CRUD APIs

#### Standard CRUD Pattern

All entities follow this pattern:

```http
# Create
POST /api/v1/{entity_type}

# Read
GET /api/v1/{entity_type}/{entity_id}

# Update
PUT /api/v1/{entity_type}/{entity_id}
PATCH /api/v1/{entity_type}/{entity_id}

# Delete
DELETE /api/v1/{entity_type}/{entity_id}

# List with filters
GET /api/v1/{entity_type}?filter[]=...&sort=...&page=...
```

**Entity Types:**
- `frameworks`
- `trust-service-criteria`
- `control-objectives`
- `controls`
- `policies`
- `procedures`
- `user-actions`
- `evidence`
- `issues`

#### Bulk Operations

```http
POST /api/v1/{entity_type}/bulk
```

**Request Body:**
```json
{
  "operation": "create" | "update" | "delete",
  "items": [...],
  "options": {
    "validate": true,
    "dry_run": false,
    "continue_on_error": false
  }
}
```

---

### 3. Search & Discovery APIs

#### Semantic Search

```http
POST /api/v1/search/semantic
```

**Purpose:** Natural language search across all entities

**Request:**
```json
{
  "query": "Find controls related to user access management that are failing",
  "entity_types": ["controls", "procedures", "issues"],
  "filters": {
    "effectiveness_score": {"max": 0.7},
    "issue_status": "open"
  },
  "limit": 20,
  "include_reasoning": true
}
```

**Response:**
```json
{
  "results": [
    {
      "entity_type": "control",
      "entity_id": "uuid",
      "entity": {...},
      "relevance_score": 0.95,
      "reasoning": "Control CC6.1 manages user access and has effectiveness score of 0.65",
      "related_issues": [...]
    }
  ],
  "query_understanding": {
    "intent": "find_failing_controls",
    "extracted_concepts": ["user access", "access management", "failing"],
    "suggested_refinements": [...]
  }
}
```

#### Context-Based Discovery

```http
POST /api/v1/discovery/by-context
```

**Purpose:** Find entities relevant to a given context

**Request:**
```json
{
  "context": {
    "type": "compliance_audit",
    "framework": "SOC 2",
    "focus_areas": ["access controls", "monitoring"],
    "time_period": {
      "from": "2025-10-01",
      "to": "2026-01-01"
    }
  },
  "discover": ["controls", "evidence", "issues"],
  "risk_threshold": "high"
}
```

---

### 4. Analysis APIs

#### Control Effectiveness Analysis

```http
GET /api/v1/analytics/control-effectiveness
```

**Query Parameters:**
```yaml
control_ids: uuid[] (optional, specific controls)
framework_id: uuid (optional, all controls in framework)
time_range: string (e.g., "30d", "6m", "1y")
include_trends: boolean
breakdown_by: enum (procedure, actor_role, system_source)
```

**Response:**
```json
{
  "summary": {
    "total_controls": 45,
    "avg_effectiveness": 0.83,
    "controls_at_risk": 5,
    "trend": "stable"
  },
  "controls": [
    {
      "control_id": "uuid",
      "code": "CC6.1",
      "effectiveness_score": 0.78,
      "factors": {
        "action_completion_rate": 0.92,
        "action_quality_avg": 0.71,
        "evidence_freshness": 0.85,
        "issue_impact": 0.15
      },
      "trend": "degrading",
      "historical": [
        {"date": "2026-01-01", "score": 0.85},
        {"date": "2026-01-15", "score": 0.81},
        {"date": "2026-01-28", "score": 0.78}
      ],
      "recommendations": [
        "Action quality declining: managers approving without investigation",
        "Consider additional training or automation"
      ]
    }
  ]
}
```

#### Risk Assessment

```http
POST /api/v1/analytics/risk-assessment
```

**Request:**
```json
{
  "entity_type": "control",
  "entity_id": "uuid",
  "assessment_method": "fair" | "monte_carlo" | "historical",
  "time_horizon": "90d",
  "simulation_runs": 10000,
  "include_sensitivity_analysis": true
}
```

**Response:**
```json
{
  "risk_score": 0.42,
  "risk_level": "high",
  "likelihood": 0.6,
  "impact": 0.7,
  "calculation_method": "monte_carlo",
  "confidence_interval": {
    "lower_bound": 0.35,
    "upper_bound": 0.49,
    "confidence_level": 0.95
  },
  "contributing_factors": [
    {
      "factor": "action_completion_rate",
      "current_value": 0.85,
      "target_value": 0.95,
      "contribution_to_risk": 0.15
    }
  ],
  "sensitivity_analysis": {
    "most_sensitive_to": "action_quality",
    "tornado_chart_data": [...]
  },
  "simulation_results": {
    "mean": 0.42,
    "median": 0.41,
    "percentile_90": 0.52,
    "percentile_95": 0.58
  }
}
```

#### Gap Analysis

```http
POST /api/v1/analytics/gap-analysis
```

**Purpose:** Identify missing controls, evidence, or actions

**Request:**
```json
{
  "framework_id": "uuid",
  "target_maturity": "level_3",
  "compare_to": "industry_benchmark" | "previous_audit" | "another_framework",
  "include_remediation_plan": true
}
```

**Response:**
```json
{
  "gaps": [
    {
      "gap_type": "missing_control",
      "severity": "high",
      "description": "No detective control for privileged access monitoring",
      "required_for": ["CC6.1", "CC6.7"],
      "recommendation": "Implement SIEM-based privileged access monitoring",
      "estimated_effort": "4-6 weeks",
      "priority": 1
    }
  ],
  "maturity_scores": {
    "current": 2.3,
    "target": 3.0,
    "gap": 0.7
  },
  "remediation_roadmap": [...]
}
```

---

### 5. Agentic Query APIs

#### Natural Language Query

```http
POST /api/v1/agentic/query
```

**Purpose:** Accept natural language queries from agents, return structured + narrative response

**Request:**
```json
{
  "query": "Why is our SOC 2 CC6 effectiveness declining? What actions are causing this?",
  "context": {
    "project_id": "Snyk",
    "actor_type": "compliance_manager",
    "context_ids": ["soc2_compliance"]
  },
  "response_format": "detailed" | "summary" | "executive",
  "include_recommendations": true,
  "include_evidence": true,
  "skip_deep_research": false
}
```

**Response:**
```json
{
  "query_understanding": {
    "intent": "root_cause_analysis",
    "entities_identified": ["SOC 2", "CC6", "effectiveness"],
    "time_frame_inferred": "recent_trend"
  },
  "answer": {
    "summary": "CC6 effectiveness declined from 0.85 to 0.78 over the past 30 days. Root cause: quarterly access reviews are being rubber-stamped without actual investigation.",
    "detailed_analysis": "...",
    "structured_findings": {
      "current_effectiveness": 0.78,
      "previous_effectiveness": 0.85,
      "decline_percentage": 8.2,
      "primary_cause": {
        "factor": "action_quality_degradation",
        "description": "Managers completing reviews without revoking stale access",
        "impact": "40% reduction in control effectiveness"
      },
      "contributing_actions": [
        {
          "action_type": "access_review",
          "quality_score_avg": 0.62,
          "quality_score_target": 0.90,
          "gap": 0.28
        }
      ]
    }
  },
  "evidence": [
    {
      "evidence_id": "uuid",
      "type": "user_action_log",
      "description": "12 of 15 recent reviews had zero revocations",
      "source": "IAM audit logs",
      "timestamp": "2026-01-20"
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "recommendation": "Implement manager training on access review procedures",
      "expected_impact": "Improve action quality score to 0.85+",
      "estimated_effort": "2 weeks",
      "type": "training"
    },
    {
      "priority": "medium",
      "recommendation": "Add automated detection of 'rubber-stamp' patterns",
      "expected_impact": "Early warning system for declining quality",
      "estimated_effort": "1 week",
      "type": "automation"
    }
  ],
  "related_issues": [
    {
      "issue_id": "uuid",
      "title": "Access reviews completed without revocations",
      "status": "open",
      "severity": "high"
    }
  ],
  "execution_metadata": {
    "reasoning_steps": ["context_retrieval", "mdl_reasoning", "data_knowledge_retrieval", "deep_research", "analysis"],
    "execution_time_ms": 2340,
    "tokens_used": 15420
  }
}
```

#### Multi-Step Reasoning

```http
POST /api/v1/agentic/reasoning-session
```

**Purpose:** Support multi-turn conversations with state persistence

**Request:**
```json
{
  "session_id": "uuid" (optional, create new if not provided),
  "message": "Show me the controls related to user access",
  "continue_from": "previous_message_id" (optional)
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "message_id": "uuid",
  "response": {
    "text": "I found 12 controls related to user access...",
    "structured_data": {...},
    "visualizations": [...]
  },
  "conversation_state": {
    "entities_discussed": ["control:uuid1", "control:uuid2"],
    "context_stack": [...],
    "suggested_follow_ups": [
      "Would you like to see the effectiveness scores?",
      "Should I analyze recent issues for these controls?"
    ]
  }
}
```

#### Evidence Collection Orchestration

```http
POST /api/v1/agentic/evidence-collection
```

**Purpose:** Agent requests evidence collection for specific control/procedure

**Request:**
```json
{
  "control_id": "uuid",
  "collection_scope": {
    "time_range": {"from": "2025-10-01", "to": "2026-01-28"},
    "systems": ["IAM", "ServiceNow", "GitHub"],
    "evidence_types": ["logs", "reports", "approvals"]
  },
  "validation_required": true,
  "async": true
}
```

**Response (if async=true):**
```json
{
  "collection_job_id": "uuid",
  "status": "initiated",
  "estimated_completion": "2026-01-28T15:30:00Z",
  "webhook_url": "https://api.example.com/webhooks/evidence-collection/{job_id}"
}
```

**Response (if async=false):**
```json
{
  "evidence_collected": [
    {
      "evidence_id": "uuid",
      "source_system": "IAM",
      "evidence_type": "log",
      "validation_status": "verified",
      "content_location": "s3://...",
      "collected_at": "2026-01-28T14:00:00Z"
    }
  ],
  "summary": {
    "total_collected": 45,
    "verified": 43,
    "invalid": 2,
    "missing": 3
  }
}
```

---

## Integration Patterns

### How Agents Use This System

The knowledge graph serves as a **reference layer** that agents query to understand compliance requirements before checking operational systems.

```
┌─────────────────────────────────────────────────────────┐
│  AGENT WORKFLOW                                          │
└─────────────────────────────────────────────────────────┘
    ↓
1. Query Knowledge Graph
   "What controls apply to user access?"
   → Retrieve control definitions, procedures, templates
    ↓
2. Use Templates to Query Operational Systems
   Agent now knows:
   - What to look for (evidence types)
   - Where to look (IAM, SIEM, ticketing)
   - How to validate (validation criteria)
    ↓
3. Collect Actual Data from External Systems
   - IAM logs from Okta
   - Tickets from Jira
   - Alerts from Datadog
    ↓
4. Apply Knowledge Graph Specifications
   - Validate evidence against specs
   - Check for required fields
   - Verify freshness requirements
    ↓
5. Synthesize Response
   - Match operational state to requirements
   - Identify gaps using issue patterns
   - Provide recommendations using templates
```

### Integration Scenario 1: Discovery Agent

**User Query:** "What controls do we need for SOC 2?"

**Agent Workflow:**
```python
# Step 1: Query knowledge graph
response = await query_knowledge_graph(
    query="Get all SOC 2 control definitions",
    context={"framework": "SOC2"}
)
# Returns: List of 64 SOC 2 controls with metadata

# Step 2: Agent doesn't check operational systems yet
# Just returns definitions and requirements

# Step 3: Response to user
return {
    "controls": [...],  # Definitions from knowledge graph
    "guidance": "Here are the 64 SOC 2 controls. To assess your current state, I can check your systems if you provide access."
}
```

### Integration Scenario 2: Evidence Specification Agent

**User Query:** "What evidence do I need for access reviews?"

**Agent Workflow:**
```python
# Step 1: Query knowledge graph
response = await query_knowledge_graph(
    query="Get evidence specifications for access review procedures",
    context={"procedure_type": "access_review"}
)
# Returns: Evidence specs with requirements

# Step 2: Agent formats specifications
evidence_specs = response["evidence_specifications"]
# Example:
# {
#   "evidence_type": "audit_log",
#   "source_system": "IAM",
#   "required_fields": ["timestamp", "reviewer", "decision"],
#   "freshness": "30 days",
#   "collection_method": "automated",
#   "validation_criteria": {...}
# }

# Step 3: Agent returns specifications (NOT actual evidence)
return {
    "evidence_requirements": evidence_specs,
    "collection_guidance": "Use these specifications to collect evidence from your IAM system",
    "collection_scripts": [...]  # Templates from knowledge graph
}
```

### Integration Scenario 3: Implementation Guidance Agent

**User Query:** "How do I implement least privilege access?"

**Agent Workflow:**
```python
# Step 1: Query knowledge graph for control definition
control = await query_knowledge_graph(
    query="Get control definition for least privilege",
    context={"control_concept": "least_privilege"}
)
# Returns: Control CC6.1 definition

# Step 2: Retrieve implementation templates
templates = await query_knowledge_graph(
    query="Get implementation templates for CC6.1",
    include=["policies", "procedures", "action_templates"]
)

# Step 3: Get contextual guidance
context_guidance = await query_knowledge_graph(
    query="Get SaaS-specific interpretation of CC6.1",
    context={"industry": "saas"}
)

# Step 4: Synthesize response (all from knowledge graph)
return {
    "control_definition": control,
    "policy_template": templates["policy"],  # Template, not actual policy
    "procedure_steps": templates["procedure"],  # Steps, not actual procedure
    "saas_specific_guidance": context_guidance,
    "tool_recommendations": ["Okta", "Auth0"],
    "example_implementations": [...]
}
```

### Integration Scenario 4: Gap Analysis Agent

**User Query:** "What SOC 2 controls are we missing?"

**Agent Workflow:**
```python
# Step 1: Get all SOC 2 control definitions from knowledge graph
all_soc2_controls = await query_knowledge_graph(
    query="Get all SOC 2 control definitions"
)

# Step 2: Agent needs to check operational systems
# (NOT part of knowledge graph)
implemented_controls = await check_external_systems(
    system="grc_platform",  # e.g., Vanta, Drata
    query="list_implemented_controls"
)

# Step 3: Compare (logic in agent)
missing_controls = set(all_soc2_controls) - set(implemented_controls)

# Step 4: Enrich gaps with knowledge graph metadata
gap_analysis = []
for control_id in missing_controls:
    control_def = await query_knowledge_graph(
        query=f"Get control definition {control_id}"
    )
    gap_analysis.append({
        "control": control_def,
        "status": "missing",
        "implementation_guidance": control_def["implementation_guidance"],
        "estimated_effort": control_def["metadata"]["estimated_effort"]
    })

return gap_analysis
```

### Key Patterns

#### Pattern 1: Definition Lookup
**Knowledge Graph provides:** Metadata, definitions, specifications  
**Agent uses for:** Understanding what something is  
**External systems:** Not queried

#### Pattern 2: Template Retrieval
**Knowledge Graph provides:** Templates with placeholders  
**Agent uses for:** Guiding implementation  
**External systems:** Not queried

#### Pattern 3: Specification Matching
**Knowledge Graph provides:** Requirements, validation criteria  
**Agent queries:** External systems for actual data  
**Agent validates:** Actual data against specifications

#### Pattern 4: Contextual Reasoning
**Knowledge Graph provides:** Context-specific interpretations  
**Agent applies:** To user's specific situation  
**External systems:** May be queried for context (e.g., "What industry is this company?")

### Data Flow Diagram

```
User Query: "Are we compliant with SOC 2 CC6?"
    ↓
┌───────────────────────────────────────────────┐
│  AGENT WORKFLOW                               │
├───────────────────────────────────────────────┤
│  1. Query Knowledge Graph                     │
│     → Get CC6 control definitions             │
│     → Get evidence specifications             │
│     → Get validation criteria                 │
│                                               │
│  2. Query External Systems                    │
│     → Check IAM logs (Okta)                  │
│     → Check access review tickets (Jira)     │
│     → Check audit reports (S3)               │
│                                               │
│  3. Validate (using knowledge graph specs)    │
│     → Evidence meets freshness requirement?  │
│     → Required fields present?                │
│     → Matches validation criteria?            │
│                                               │
│  4. Identify Gaps (using issue patterns)      │
│     → Compare actual vs. required            │
│     → Match to known failure patterns         │
│                                               │
│  5. Generate Response                         │
│     → Status: Partially compliant            │
│     → Issues: Missing evidence for X         │
│     → Recommendations: Use template Y         │
└───────────────────────────────────────────────┘
    ↓
Response to User
```

---

## Implementation Considerations

### Storage Layer

**Primary: PostgreSQL**
- Store all entity definitions
- Relational integrity for foreign keys
- JSONB for flexible metadata
- Full-text search (GIN indexes)

**Graph: Neo4j (Optional but Recommended)**
- Store nodes and edges
- Complex multi-hop traversals
- Relationship-heavy queries
- Visualization support

**Vector: ChromaDB / Pinecone**
- Semantic search over descriptions
- Embedding-based similarity
- Collection per entity type

**Decision:** Use PostgreSQL as source of truth, Neo4j for graph queries, ChromaDB for semantic search

### Indexing Strategy

**PostgreSQL Indexes:**
```sql
-- Full-text search
CREATE INDEX idx_control_definition_fts
ON control_definitions USING gin(to_tsvector('english', description));

-- JSONB metadata
CREATE INDEX idx_control_metadata
ON control_definitions USING gin(metadata);

-- Composite for filtering
CREATE INDEX idx_control_type_automation
ON control_definitions(control_type, automation_potential);
```

**Neo4j Indexes:**
```cypher
// Node indexes
CREATE INDEX control_code FOR (c:Control) ON (c.code);
CREATE INDEX context_name FOR (ctx:Context) ON (ctx.name);

// Full-text search
CALL db.index.fulltext.createNodeIndex(
  "controlDescriptions",
  ["Control"],
  ["description", "implementation_guidance"]
);
```

**ChromaDB Collections:**
```python
# Separate collections for each entity type
collections = [
    "framework_definitions",
    "control_definitions",
    "procedure_definitions",
    "action_templates",
    "evidence_specifications",
    "context_definitions"
]

# Each with metadata for filtering
metadata = {
    "entity_type": "control",
    "entity_id": "uuid",
    "framework": "SOC2",
    "control_type": "preventive"
}
```

### Query Optimization

**Hybrid Query Strategy:**

```python
async def query_knowledge_graph(query: str, context: dict):
    # Step 1: Semantic search (vector similarity)
    vector_results = await chromadb.search(
        query_embedding=embed(query),
        collection="control_definitions",
        n_results=20,
        where=context  # Metadata filtering
    )
    
    # Step 2: Graph enrichment (Neo4j traversal)
    enriched_results = []
    for result in vector_results:
        # Get relationships
        graph_data = await neo4j.query(f"""
            MATCH (c:Control {{code: '{result.metadata["code"]}'}})
            OPTIONAL MATCH (c)-[r]->(related)
            RETURN c, r, related
        """)
        enriched_results.append({
            "definition": result,
            "relationships": graph_data
        })
    
    # Step 3: Context application (PostgreSQL lookup)
    for result in enriched_results:
        contextual_edges = await postgres.query("""
            SELECT * FROM contextual_edges
            WHERE source_id = $1 AND source_type = 'control'
        """, result["definition"]["entity_id"])
        result["contextual_interpretations"] = contextual_edges
    
    return enriched_results
```

### Caching Strategy

**What to Cache:**
- Framework hierarchies (rarely change)
- Control definitions (static)
- Policy templates (static)
- Popular contextual edges (frequently accessed)

**What NOT to Cache:**
- Search results (query-dependent)
- Contextual interpretations (context-dependent)

**Implementation:**
```python
from functools import lru_cache
import redis

# In-memory cache for static data
@lru_cache(maxsize=1000)
async def get_control_definition(control_id: str):
    return await db.query("SELECT * FROM control_definitions WHERE control_id = $1", control_id)

# Redis cache for frequent queries
redis_client = redis.Redis()

async def get_framework_hierarchy(framework_id: str):
    cache_key = f"framework_hierarchy:{framework_id}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    result = await build_framework_hierarchy(framework_id)
    redis_client.setex(cache_key, 3600, json.dumps(result))  # 1 hour TTL
    return result
```

### Scalability Considerations

**Current Scale:**
- ~10 frameworks
- ~1000 controls
- ~5000 procedures
- ~10000 action templates
- ~20000 contextual edges

**Expected Growth:**
- Frameworks: Slow (few new standards per year)
- Controls: Medium (new versions of frameworks)
- Contextual edges: Fast (learning from usage)

**Partitioning: Not Needed Yet**
- Dataset size manageable in single database
- Consider partitioning if > 1M entities

### Security Considerations

**Access Control:**
- Knowledge graph is generally non-sensitive (public framework definitions)
- Context definitions may contain company-specific info → RBAC
- Templates may contain proprietary methodology → RBAC

**Implementation:**
```python
class AccessControl:
    def can_access_entity(self, user: User, entity_type: str, entity_id: str) -> bool:
        # Public entities (framework definitions, standard controls)
        if entity_type in ["framework", "tsc", "control_objective", "standard_control"]:
            return True
        
        # Private entities (custom contexts, company-specific templates)
        if entity_type in ["custom_context", "custom_template"]:
            return user.organization_id == entity.organization_id
        
        return False
```

### Observability

**Metrics to Track:**
- Query latency (p50, p95, p99)
- Cache hit rates
- Vector search accuracy (relevance scores)
- Graph traversal depth (complexity)
- Most queried entities (usage patterns)

**Logging:**
```python
import structlog

logger = structlog.get_logger()

async def query_knowledge_graph(query: str, context: dict):
    logger.info(
        "knowledge_graph_query",
        query=query,
        context=context,
        user_id=context.get("user_id"),
        session_id=context.get("session_id")
    )
    
    start_time = time.time()
    result = await execute_query(query, context)
    duration = time.time() - start_time
    
    logger.info(
        "knowledge_graph_query_complete",
        query=query,
        duration_ms=duration * 1000,
        result_count=len(result),
        cache_hit=result.metadata.get("cached", False)
    )
    
    return result
```

### Versioning and Change Management

**Framework Versions:**
- Store multiple versions of same framework (e.g., SOC 2 2017 vs SOC 2 2023)
- Track effective dates
- Support "What changed between versions?" queries

**Schema:**
```yaml
FrameworkDefinition:
  - framework_id: uuid
  - name: "SOC 2 Type II"
  - version: "2017"
  - superseded_by: uuid (FK to newer version)
  - effective_date: date
  - sunset_date: date (when this version is no longer valid)
```

**Change Tracking:**
```yaml
ChangeLog:
  - change_id: uuid
  - entity_type: enum
  - entity_id: uuid
  - change_type: enum (created, updated, deprecated)
  - changed_at: timestamp
  - changed_by: string
  - change_details: jsonb
```

---

## Example Use Cases

### Use Case 1: Product Knowledge - Prioritize Snyk Vulnerabilities for SOC 2 Audit

**User:** Security Engineer preparing for SOC 2 audit

**Query:** "Prioritize our Snyk vulnerabilities for the SOC 2 audit next month. Focus on what matters most for compliance."

**What Knowledge Graph Provides:**

1. **SOC 2 Control Mapping**
   - Identifies relevant controls: CC7.1 (vulnerability detection), CC7.2 (vulnerability remediation)
   - Retrieves control definitions and requirements

2. **Snyk Entity Schema**
   - Vulnerability schema definition with all fields
   - Field mappings to compliance concepts:
     - `severity` → risk_level
     - `cvss_score` → quantified_risk
     - `exploit_maturity` → threat_likelihood
     - `fixable` → remediability
     - `package_name` → affected_component

3. **Product → Compliance Mappings**
   - Critical/High severity → CC7.2 risk (strength: 0.9)
   - Exploitable vulnerabilities → CC7.1 monitoring requirement (strength: 0.85)
   - Unfixable vulnerabilities → Compensating control need (strength: 0.7)

4. **Business Entity Context**
   - Maps Snyk projects to business entities (e.g., "Payment API", "Customer Portal")
   - Retrieves criticality and data classification
   - Identifies which entities are in SOC 2 scope

5. **Prioritization Logic**
   ```
   priority_score = 
     (severity_weight × severity_score) +
     (compliance_impact_weight × compliance_relevance) +
     (business_criticality_weight × entity_criticality) +
     (exploitability_weight × exploit_maturity_score) +
     (fixability_weight × fixable_score)
   ```

**Response Structure:**

```json
{
  "query_understanding": {
    "intent": "prioritize_vulnerabilities_for_audit",
    "product": "Snyk",
    "framework": "SOC 2",
    "context": "audit_preparation"
  },
  "prioritization_guidance": {
    "scoring_model": {
      "factors": [
        {
          "factor": "severity",
          "weight": 0.3,
          "mapping": "Snyk severity → SOC 2 risk level",
          "guidance": "Critical/High = immediate remediation required"
        },
        {
          "factor": "compliance_impact",
          "weight": 0.3,
          "mapping": "Vulnerability impacts CC7.1, CC7.2",
          "guidance": "Focus on controls that will be tested in audit"
        },
        {
          "factor": "business_criticality",
          "weight": 0.25,
          "mapping": "Affected component criticality",
          "guidance": "Payment API = critical, Marketing site = low"
        },
        {
          "factor": "exploitability",
          "weight": 0.1,
          "mapping": "Exploit maturity → threat likelihood",
          "guidance": "Mature exploits = higher priority"
        },
        {
          "factor": "fixability",
          "weight": 0.05,
          "mapping": "Snyk fixable field",
          "guidance": "Fixable vulnerabilities = quick wins"
        }
      ]
    },
    "soc2_requirements": {
      "CC7.1": {
        "requirement": "Detect security threats and vulnerabilities",
        "relevance": "All vulnerabilities in production scope",
        "audit_focus": "Evidence of continuous scanning"
      },
      "CC7.2": {
        "requirement": "Respond to security incidents and vulnerabilities",
        "relevance": "Remediation of critical/high findings",
        "audit_focus": "Evidence of timely remediation (30-90 day SLA)"
      }
    }
  },
  "prioritization_rules": [
    {
      "rule_id": 1,
      "condition": "severity IN ['critical', 'high'] AND entity.criticality = 'critical' AND fixable = true",
      "priority": "P0 - Immediate",
      "rationale": "High risk to critical system with available fix",
      "sla": "7 days",
      "audit_impact": "Critical finding if not remediated"
    },
    {
      "rule_id": 2,
      "condition": "severity = 'critical' AND exploit_maturity = 'mature'",
      "priority": "P0 - Immediate",
      "rationale": "Actively exploitable vulnerability",
      "sla": "7 days",
      "audit_impact": "Critical finding"
    },
    {
      "rule_id": 3,
      "condition": "severity = 'high' AND entity.data_classification = 'restricted'",
      "priority": "P1 - Urgent",
      "rationale": "High risk to sensitive data",
      "sla": "30 days",
      "audit_impact": "High finding if not remediated"
    },
    {
      "rule_id": 4,
      "condition": "severity IN ['medium', 'low'] AND entity.in_soc2_scope = false",
      "priority": "P3 - Low",
      "rationale": "Lower risk, out of audit scope",
      "sla": "90 days",
      "audit_impact": "Minimal"
    }
  ],
  "field_interpretation_guide": {
    "severity": {
      "snyk_values": ["critical", "high", "medium", "low"],
      "compliance_mapping": {
        "critical": "Immediate risk to control effectiveness",
        "high": "Significant risk requiring timely remediation",
        "medium": "Moderate risk, monitor and remediate",
        "low": "Low risk, remediate as resources permit"
      }
    },
    "exploit_maturity": {
      "snyk_values": ["mature", "proof-of-concept", "no-known-exploit"],
      "compliance_mapping": {
        "mature": "High likelihood of exploitation, prioritize",
        "proof-of-concept": "Medium likelihood, monitor",
        "no-known-exploit": "Lower priority, but still relevant"
      }
    },
    "fixable": {
      "snyk_values": [true, false],
      "compliance_mapping": {
        "true": "Can remediate immediately, prioritize for quick wins",
        "false": "Requires compensating controls or risk acceptance"
      }
    }
  },
  "evidence_guidance": {
    "for_cc7_1": {
      "evidence_type": "Snyk scan results showing continuous monitoring",
      "what_to_collect": [
        "Weekly scan reports from last 6 months",
        "Vulnerability trend over time",
        "Scan coverage (all production apps included)"
      ],
      "where_to_find": "Snyk API: GET /org/{org_id}/projects → GET /project/{project_id}/issues",
      "validation_criteria": "Scans run at least weekly, all critical apps included"
    },
    "for_cc7_2": {
      "evidence_type": "Vulnerability remediation tracking",
      "what_to_collect": [
        "Critical/High vulnerabilities discovered",
        "Remediation timelines",
        "Evidence of fixes (commits, deployments)",
        "Risk acceptance for unfixable vulnerabilities"
      ],
      "where_to_find": "Snyk API + Jira tickets for remediation tracking",
      "validation_criteria": "Critical remediated within 30 days, High within 90 days"
    }
  },
  "business_entity_mapping": {
    "Payment Processing API": {
      "criticality": "critical",
      "data_classification": "restricted",
      "compliance_scope": ["SOC2", "PCI-DSS"],
      "snyk_projects": ["org/payment-api"],
      "priority_multiplier": 1.5,
      "rationale": "Handles payment data, critical business function"
    },
    "Customer Portal": {
      "criticality": "high",
      "data_classification": "confidential",
      "compliance_scope": ["SOC2"],
      "snyk_projects": ["org/customer-portal"],
      "priority_multiplier": 1.2,
      "rationale": "Customer data, authentication gateway"
    },
    "Marketing Website": {
      "criticality": "medium",
      "data_classification": "public",
      "compliance_scope": ["SOC2"],
      "snyk_projects": ["org/marketing-site"],
      "priority_multiplier": 0.8,
      "rationale": "Public content, lower compliance impact"
    }
  },
  "sample_query_to_operational_system": {
    "description": "After understanding prioritization logic, query Snyk API for actual vulnerabilities",
    "api_call": "GET https://api.snyk.io/v1/org/{org_id}/projects",
    "filter_logic": "Filter by severity, exploitability, business entity criticality",
    "scoring_logic": "Apply priority_score formula to each vulnerability",
    "output": "Sorted list of vulnerabilities with priority and remediation guidance"
  },
  "next_steps": {
    "immediate": [
      "Query Snyk API using provided guidance",
      "Apply prioritization scoring model",
      "Create remediation tickets for P0/P1 items"
    ],
    "for_audit": [
      "Collect evidence per CC7.1 and CC7.2 guidance",
      "Document remediation timelines",
      "Prepare risk acceptance memos for unfixable items"
    ]
  }
}
```

**What This Use Case Demonstrates:**

1. **Product knowledge mapping**: Snyk fields → compliance concepts
2. **Business entity context**: Payment API vs Marketing site prioritization
3. **Goal-oriented reasoning**: Specific goal (audit prep) drives the response
4. **Actionable guidance**: Not just "here's Snyk schema", but "here's how to use it for SOC 2"
5. **Bridge to operational**: Knowledge graph provides logic, agent queries Snyk API for actual data

**Agent Workflow:**

```
1. Understand query intent: "prioritize for SOC 2 audit"
   ↓
2. Query knowledge graph:
   - Get SOC 2 controls (CC7.1, CC7.2)
   - Get Snyk vulnerability schema
   - Get field mappings (severity → risk_level)
   - Get product→compliance mappings
   - Get business entity definitions
   ↓
3. Synthesize prioritization logic from mappings
   ↓
4. Return guidance (NOT actual vulnerabilities)
   ↓
5. Agent can now query Snyk API with this logic
   and apply prioritization to real data
```

---

### Use Case 2: Compliance Manager - Framework Understanding

**Query:** "Explain SOC 2 CC6 to me"

**What Knowledge Graph Provides:**
- Framework definition (SOC 2)
- TSC definition (CC6 - Logical and Physical Access Controls)
- All control objectives under CC6
- Control definitions implementing those objectives
- Relationships between controls

**What It Does NOT Provide:**
- Your company's current compliance status
- Actual evidence from your systems
- Risk scores based on your implementation

**Response:**
```json
{
  "framework": "SOC 2 Type II",
  "tsc": {
    "code": "CC6",
    "name": "Logical and Physical Access Controls",
    "description": "The entity restricts physical and logical access..."
  },
  "control_objectives": [
    {"code": "CC6.1", "description": "Access restricted to authorized users"},
    {"code": "CC6.2", "description": "New users provisioned appropriately"},
    ...
  ],
  "controls": [
    {
      "code": "CC6.1",
      "name": "Logical Access Controls",
      "description": "...",
      "implementation_guidance": "...",
      "required_procedures": [...],
      "evidence_requirements": [...]
    }
  ]
}
```

### Use Case 2: Security Engineer - Implementation Guidance

**Query:** "How do I implement CC6.1 for a SaaS company?"

**What Knowledge Graph Provides:**
- CC6.1 control definition
- SaaS context definition
- Contextual edges: (SaaSContext)-[INTERPRETS]->(CC6.1)
- Policy template for access control
- Procedure definitions (e.g., access provisioning, review)
- Action templates (what actions are required)
- Evidence specifications (what to collect)
- Tool recommendations from metadata

**What It Does NOT Provide:**
- Your actual Okta/Auth0 configuration
- Your current IAM logs
- Analysis of your current access patterns

**Response:**
```json
{
  "control": {...},
  "saas_interpretation": {
    "requirements": ["SSO", "MFA", "Role-based access via IDP"],
    "guidance": "For SaaS companies, implement SSO with MFA using an identity provider..."
  },
  "templates": {
    "policy": "Access Control Policy Template (SaaS variant)",
    "procedures": [
      {"name": "User Onboarding", "steps": [...]},
      {"name": "Quarterly Access Review", "steps": [...]}
    ]
  },
  "evidence_requirements": [
    {
      "evidence_type": "audit_log",
      "source_system": "IAM (Okta/Auth0)",
      "required_fields": ["timestamp", "user_id", "action", "result"],
      "freshness": "30 days",
      "collection_method": "Automated API pull",
      "validation_criteria": {...},
      "collection_script": "# Python script..."
    }
  ],
  "recommended_tools": ["Okta", "Auth0", "JumpCloud"],
  "estimated_effort": "4-6 weeks"
}
```

### Use Case 3: Auditor - Evidence Requirements

**Query:** "What evidence do I need to collect for SOC 2 audit?"

**What Knowledge Graph Provides:**
- All evidence specifications for SOC 2 controls
- Evidence types, formats, freshness requirements
- Collection methods and validation criteria
- Grouping by control/TSC

**What It Does NOT Provide:**
- Actual evidence files
- Links to your S3 buckets or file systems
- Evidence quality assessment (that requires actual evidence)

**Response:**
```json
{
  "evidence_requirements_by_tsc": {
    "CC6": [
      {
        "control": "CC6.1",
        "evidence_specs": [
          {
            "evidence_type": "audit_log",
            "description": "IAM authentication logs",
            "required_fields": [...],
            "freshness": "Continuous (real-time)",
            "collection_method": "Automated",
            "validation_criteria": {...}
          },
          {
            "evidence_type": "report",
            "description": "Quarterly access review reports",
            "required_fields": [...],
            "freshness": "Quarterly",
            "collection_method": "Manual or automated",
            "validation_criteria": {...}
          }
        ]
      }
    ]
  },
  "collection_guidance": "Use these specifications to set up evidence collection processes",
  "retention_requirements": "Retain evidence for 12 months post-audit"
}
```

---

## Future Enhancements

### Phase 1: Enhanced Contextual Reasoning
- Machine learning to suggest contextual edges
- Auto-discovery of industry-specific interpretations
- Learning from user feedback on relevance

### Phase 2: Multi-Language Support
- Framework definitions in multiple languages
- Template translations
- Locale-specific guidance

### Phase 3: Control Effectiveness Prediction
- ML models predicting control failure likelihood based on definition characteristics
- Risk scoring for control gaps (still metadata, not operational)
- Prioritization algorithms for implementation

### Phase 4: Integration Recipes
- Pre-built templates for common integrations (Okta, Auth0, AWS IAM, etc.)
- API mapping guides (how to collect evidence from specific tools)
- Automated setup scripts for evidence collection

---

## Appendix: Data Model Summary

### Core Entities (Metadata Only)

1. **FrameworkDefinition** - Compliance standard metadata
2. **TrustServiceCriteriaDefinition** - Category definitions
3. **ControlObjectiveDefinition** - Outcome specifications
4. **ControlDefinition** - Control mechanism metadata
5. **PolicyTemplate** - Policy structure templates
6. **ProcedureDefinition** - Workflow specifications
7. **RequiredActionTemplate** - Action specifications
8. **ExpectedEvidenceSpecification** - Evidence requirements
9. **IssuePatternDefinition** - Known failure patterns
10. **ContextDefinition** - Domain/entity contexts

### Relationship Types

- Hierarchical (Framework → Control)
- Implementation (Control → Policy → Procedure)
- Validation (Control → Evidence)
- Contextual (Context → Control, most important for reasoning)

### Storage Layers

- **PostgreSQL**: Source of truth, relational integrity
- **Neo4j**: Graph queries, relationship traversal
- **ChromaDB**: Semantic search, embeddings
- **(None)**: No operational data storage

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-28 | System Architecture | Initial design (operational focus) |
| 2.0 | 2026-01-28 | System Architecture | Major revision: Metadata-only, agentic access only |

---

**END OF DOCUMENT**
