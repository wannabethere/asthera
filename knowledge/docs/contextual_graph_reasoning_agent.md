# **Transforming Knowledge Graph → Contextual Graph**

## **Conceptual Difference**

```
Knowledge Graph (Static):
├── Entities with fixed relationships
├── Universal truths: "Control X requires Evidence Y"
├── Context-free: Same for everyone
└── Query: "What evidence proves Control X?"

Contextual Graph (Dynamic):
├── Entities with context-dependent relationships
├── Situational truths: "Control X requires Evidence Y [if automated collection exists]"
├── Context-aware: Different for each organization/situation
└── Query: "What evidence proves Control X [for healthcare org, with EHR system, 
            preparing for HIPAA audit, limited automation maturity]?"
```

---

## **Architecture: From Knowledge to Context**

### **Layer 1: Core Knowledge Graph (Foundation)**

Your existing knowledge graph structure:

```
Nodes:
├── Framework (HIPAA, SOC2)
├── Control (CC6.1, Access Control)
├── Requirement (quarterly reviews)
├── Evidence (review reports)
├── System (EHR, Workday)
├── Data Type (ePHI, PII)
└── Stakeholder (CISO, Auditor)

Edges:
├── REQUIRES
├── PROVED_BY
├── APPLIES_TO
├── MAPS_TO
└── MEASURED_BY
```

---

### **Layer 2: Context Dimensions (The Transformation)**

Add context as **first-class entities** in the graph:

```
Context Node Types:
│
├── Temporal Context
│   ├── Time period (Q1 2024, FY2024)
│   ├── Event timeline (before audit, during incident, post-breach)
│   ├── Validity period (effective date, expiration)
│   └── Measurement window (real-time, historical, predictive)
│
├── Organizational Context
│   ├── Industry vertical (Healthcare, Finance, Tech)
│   ├── Organization size (employees, revenue, geographic spread)
│   ├── Maturity level (nascent, developing, mature, optimized)
│   ├── Risk appetite (risk-averse, moderate, aggressive)
│   └── Regulatory scope (which frameworks apply)
│
├── Environmental Context
│   ├── Threat landscape (current attack patterns, vulnerability trends)
│   ├── Regulatory climate (enforcement trends, new requirements)
│   ├── Industry incidents (breaches, failures, lessons learned)
│   └── Technology trends (emerging tools, deprecated practices)
│
├── Operational Context
│   ├── Technology stack (what systems exist)
│   ├── Data availability (what can be measured)
│   ├── Automation capability (what's automated vs manual)
│   ├── Resource constraints (budget, headcount, expertise)
│   └── Integration patterns (APIs available, data flows)
│
├── Risk Context
│   ├── Current risk posture (active threats, vulnerabilities)
│   ├── Historical incidents (past failures, lessons)
│   ├── Risk concentrations (what's most exposed)
│   └── Mitigation status (what controls are active)
│
└── Stakeholder Context
    ├── Current priorities (board directives, audit prep)
    ├── Knowledge level (technical expertise, compliance awareness)
    ├── Decision authority (who approves what)
    └── Communication preferences (technical vs executive)
```

---

### **Layer 3: Contextual Relationships**

Transform static edges into **context-qualified relationships**:

```
Before (Static):
Control --[REQUIRES]--> Requirement

After (Contextual):
Control --[REQUIRES]--> Requirement
    [WHEN: in_context]
    [STRENGTH: relationship_strength]
    [CONDITIONS: prerequisites_met]
    [EXCEPTIONS: special_cases]

Example:
HIPAA_Access_Control --[REQUIRES]--> Quarterly_Reviews
    [WHEN: {
        organization_type: "Covered Entity",
        ephi_volume: "high",
        historical_violations: "none"
    }]
    [STRENGTH: 0.9]  -- Required in 90% of situations
    [CONDITIONS: {
        iam_system_exists: true,
        review_process_documented: true
    }]
    [EXCEPTIONS: {
        IF risk_assessment_justifies: "can extend to 120 days with documentation"
    }]
```

---

## **Transformation Patterns**

### **Pattern 1: Context as Edge Properties (Time-Varying Relationships)**

```sql
-- Traditional Knowledge Graph Edge
CREATE TABLE kg_control_requirements (
    control_id VARCHAR(100),
    requirement_id VARCHAR(100),
    relationship_type VARCHAR(50)  -- 'REQUIRES'
);

-- Contextual Graph Edge (Time-Varying)
CREATE TABLE cg_control_requirements (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(100),
    requirement_id VARCHAR(100),
    relationship_type VARCHAR(50),
    
    -- Temporal Context
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    effectiveness_date DATE,
    
    -- Situational Context
    context_conditions JSONB,  -- When does this relationship hold?
    /*
    {
        "organization_type": ["healthcare", "finance"],
        "data_sensitivity": ["high", "critical"],
        "geographic_scope": ["us", "eu"],
        "system_count": {"min": 5}
    }
    */
    
    -- Relationship Metadata
    relationship_strength DECIMAL(3,2),  -- 0.0 to 1.0
    confidence_score DECIMAL(3,2),       -- How sure are we?
    source_authority TEXT,               -- Why do we know this?
    
    -- Conditional Logic
    prerequisites JSONB,     -- What must exist first?
    exceptions JSONB,        -- When doesn't this apply?
    alternatives JSONB,      -- What else could satisfy this?
    
    -- Dynamic Properties
    current_status VARCHAR(50),  -- 'active', 'suspended', 'overridden'
    override_reason TEXT,
    override_authority VARCHAR(100)
);

CREATE INDEX idx_cg_control_req_context ON cg_control_requirements 
    USING GIN (context_conditions);
```

**Query Pattern:**
```sql
-- Context-Aware Query
SELECT cr.*
FROM cg_control_requirements cr
WHERE control_id = 'HIPAA-AC-001'
  -- Temporal context
  AND CURRENT_TIMESTAMP BETWEEN valid_from AND valid_until
  -- Organizational context (JSONB query)
  AND context_conditions @> '{"organization_type": ["healthcare"]}'::jsonb
  AND context_conditions @> '{"data_sensitivity": ["high"]}'::jsonb
  -- Relationship still active
  AND current_status = 'active'
  AND relationship_strength > 0.7;
```

---

### **Pattern 2: Context as Separate Nodes (Reified Context)**

```sql
-- ============================================================================
-- CONTEXT NODES
-- ============================================================================

CREATE TABLE context_nodes (
    context_id SERIAL PRIMARY KEY,
    context_type VARCHAR(50),  -- 'temporal', 'organizational', 'operational', etc.
    context_name VARCHAR(200),
    context_definition JSONB,
    
    -- Temporal bounds
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

-- Example Context Nodes
INSERT INTO context_nodes (context_type, context_name, context_definition) VALUES
    ('organizational', 'Large Healthcare Organization',
     '{
         "industry": "healthcare",
         "employee_count": {"min": 1000, "max": 10000},
         "data_types": ["ePHI", "PII"],
         "regulatory_scope": ["HIPAA", "state_breach_laws"],
         "maturity_level": "developing"
     }'::jsonb),
     
    ('situational', 'Pre-Audit State',
     '{
         "event": "upcoming_audit",
         "timeline": "within_90_days",
         "audit_type": "HIPAA_compliance",
         "priority_level": "critical"
     }'::jsonb),
     
    ('operational', 'High Automation Capability',
     '{
         "iam_system": "Okta",
         "siem_platform": "Splunk",
         "automation_maturity": "high",
         "api_availability": true,
         "data_quality": "excellent"
     }'::jsonb);

-- ============================================================================
-- CONTEXTUAL RELATIONSHIPS (3-way edges)
-- ============================================================================

CREATE TABLE contextual_edges (
    id SERIAL PRIMARY KEY,
    
    -- Traditional edge
    source_node_id VARCHAR(100),
    edge_type VARCHAR(50),
    target_node_id VARCHAR(100),
    
    -- Context qualification
    context_id INTEGER REFERENCES context_nodes(context_id),
    
    -- Context-dependent properties
    relevance_in_context DECIMAL(3,2),   -- How relevant in this context?
    priority_in_context INTEGER,         -- Priority rank in this context
    evidence_strength_in_context DECIMAL(3,2),
    
    -- Reasoning
    context_reasoning TEXT  -- Why does context affect this relationship?
);

-- Example: Same control, different priority in different contexts
INSERT INTO contextual_edges VALUES
    (DEFAULT, 'HIPAA-AC-001', 'HAS_PRIORITY', 'access_reviews',
     1,  -- context: Large Healthcare Org
     0.95, 1, 0.90,
     'Critical priority: Large healthcare org with high ePHI volume. 
      Access control failures have major impact. Risk score: 90.'),
     
    (DEFAULT, 'HIPAA-AC-001', 'HAS_PRIORITY', 'access_reviews',
     2,  -- context: Pre-Audit State
     1.0, 1, 1.0,
     'Maximum priority: Upcoming HIPAA audit. Access reviews are auditable 
      requirement. Must demonstrate consistent compliance.'),
     
    (DEFAULT, 'HIPAA-AC-001', 'HAS_PRIORITY', 'access_reviews',
     3,  -- context: High Automation Capability
     0.85, 2, 0.95,
     'High automation reduces operational burden, making frequent reviews 
      feasible. Can implement monthly instead of quarterly with same effort.');
```

**Context-Aware Query:**
```sql
-- "What are high-priority access control requirements 
--  for a large healthcare org preparing for an audit?"

SELECT 
    ce.source_node_id AS control_id,
    ce.target_node_id AS requirement_id,
    cn.context_name,
    ce.relevance_in_context,
    ce.priority_in_context,
    ce.context_reasoning
FROM contextual_edges ce
JOIN context_nodes cn ON ce.context_id = cn.context_id
WHERE ce.source_node_id = 'HIPAA-AC-001'
  AND cn.context_type IN ('organizational', 'situational')
  AND cn.context_definition @> '{"industry": "healthcare"}'::jsonb
  AND ce.relevance_in_context > 0.8
ORDER BY ce.priority_in_context;
```

---

### **Pattern 3: Context-Dependent Node Properties**

```sql
-- ============================================================================
-- NODES WITH CONTEXTUAL PROPERTIES
-- ============================================================================

CREATE TABLE contextual_control_profiles (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(100),
    context_id INTEGER REFERENCES context_nodes(context_id),
    
    -- Properties vary by context
    implementation_complexity VARCHAR(50),  -- 'simple', 'moderate', 'complex'
    estimated_cost DECIMAL(10,2),
    estimated_effort_hours INTEGER,
    required_expertise TEXT[],
    
    -- Risk varies by context
    likelihood_in_context INTEGER,  -- 1-5
    impact_in_context INTEGER,      -- 1-5
    risk_score_in_context INTEGER,  -- likelihood × impact
    
    -- Evidence availability varies by context
    evidence_types_available TEXT[],
    evidence_collection_method VARCHAR(100),
    evidence_automation_possible BOOLEAN,
    
    -- Measurement feasibility varies by context
    measurable_in_context BOOLEAN,
    metrics_available TEXT[],
    data_quality_in_context VARCHAR(50),
    
    reasoning TEXT  -- LLM reasoning for context-specific properties
);

-- Example: Same control, different complexity in different contexts
INSERT INTO contextual_control_profiles VALUES
    (DEFAULT, 'HIPAA-AC-001', 1,  -- Large Healthcare context
     'moderate',  -- complexity
     50000,       -- cost
     120,         -- hours
     ARRAY['IAM specialist', 'Compliance analyst'],
     3,           -- likelihood
     4,           -- impact
     12,          -- risk score
     ARRAY['access_review_reports', 'iam_export_logs'],
     'Automated IAM export',
     true,        -- automation possible
     true,        -- measurable
     ARRAY['review_interval_days', 'inappropriate_access_count'],
     'high',      -- data quality
     'Large org context: Moderate complexity due to multiple systems (EHR, PMS, LIS). 
      Cost includes IAM integration, workflow setup. High data quality available 
      from mature IAM platform.'),
      
    (DEFAULT, 'HIPAA-AC-001', 3,  -- High Automation context
     'simple',    -- complexity (easier with automation!)
     20000,       -- cost (lower with existing tools)
     40,          -- hours (less manual work)
     ARRAY['Automation engineer'],
     2,           -- likelihood (automation reduces risk)
     4,           -- impact
     8,           -- risk score (lower!)
     ARRAY['automated_review_reports', 'api_audit_data'],
     'Fully automated via Okta API',
     true,
     true,
     ARRAY['review_interval_days', 'auto_remediation_rate'],
     'excellent',
     'High automation context: Simple implementation leveraging existing Okta 
      platform. API-driven reviews reduce manual effort. Real-time monitoring 
      reduces likelihood of prolonged violations.');
```

---

## **Advanced: Hypergraph Representation**

For complex contexts involving multiple entities simultaneously:

```sql
-- ============================================================================
-- HYPEREDGES: Multi-way relationships with context
-- ============================================================================

CREATE TABLE hyperedges (
    hyperedge_id SERIAL PRIMARY KEY,
    hyperedge_type VARCHAR(100),
    description TEXT,
    
    -- Multiple participating nodes
    participating_nodes JSONB,
    /*
    {
        "control": "HIPAA-AC-001",
        "requirement": "quarterly_reviews",
        "evidence": "review_reports",
        "system": "Workday",
        "stakeholder": "HR_Manager"
    }
    */
    
    -- Context for this hyperedge
    context_id INTEGER REFERENCES context_nodes(context_id),
    
    -- Relationship semantics
    relationship_semantics TEXT,
    relationship_strength DECIMAL(3,2),
    
    -- Reasoning
    reasoning TEXT
);

-- Example Hyperedge
INSERT INTO hyperedges VALUES
    (DEFAULT,
     'complete_compliance_workflow',
     'Full workflow for access control compliance in healthcare org',
     '{
         "control": "HIPAA-AC-001",
         "requirement": "quarterly_reviews",
         "evidence": "review_reports",
         "system": "Workday",
         "stakeholder": "HR_Manager",
         "automation_tool": "n8n",
         "metric": "review_interval_days"
     }'::jsonb,
     1,  -- Large Healthcare Org context
     'In healthcare context with Workday: HR Manager runs quarterly reviews 
      via n8n automation, generates reports from Workday, measured by interval metric. 
      Complete workflow requires all components.',
     0.95,  -- high strength - all components necessary
     'LLM Reasoning: In large healthcare orgs, access reviews require coordination 
      across systems (Workday), stakeholders (HR Manager), automation (n8n), and 
      measurement (metrics). Missing any component breaks compliance workflow. 
      Context-specific because smaller orgs might use manual process without automation.');
```

---

## **Context-Aware Graph Queries**

### **Query 1: Context-Filtered Control Universe**

```sql
-- "Show me controls relevant for my organization"
WITH my_context AS (
    SELECT context_id
    FROM context_nodes
    WHERE context_definition @> '{
        "industry": "healthcare",
        "employee_count": {"min": 500, "max": 2000},
        "maturity_level": "developing"
    }'::jsonb
)
SELECT 
    cp.control_id,
    c.control_name,
    cp.implementation_complexity,
    cp.risk_score_in_context,
    cp.measurable_in_context,
    cp.reasoning
FROM contextual_control_profiles cp
JOIN my_context mc ON cp.context_id = mc.context_id
JOIN controls c ON cp.control_id = c.control_id
WHERE cp.risk_score_in_context > 10  -- High risk in our context
  AND cp.implementation_complexity IN ('simple', 'moderate')  -- Feasible
ORDER BY cp.risk_score_in_context DESC;
```

### **Query 2: Temporal Context Evolution**

```sql
-- "How has this control's priority changed over time?"
SELECT 
    cn.valid_from,
    cn.context_name,
    ce.priority_in_context,
    ce.relevance_in_context,
    ce.context_reasoning
FROM contextual_edges ce
JOIN context_nodes cn ON ce.context_id = cn.context_id
WHERE ce.source_node_id = 'HIPAA-AC-001'
  AND cn.context_type = 'temporal'
ORDER BY cn.valid_from;

-- Results show:
-- 2023-Q1: Priority 3, Relevance 0.7 (business as usual)
-- 2023-Q4: Priority 1, Relevance 0.95 (audit announced)
-- 2024-Q1: Priority 1, Relevance 1.0 (active audit)
-- 2024-Q2: Priority 2, Relevance 0.85 (post-audit, sustaining)
```

### **Query 3: Multi-Context Aggregation**

```sql
-- "What's the comprehensive risk score considering ALL active contexts?"
WITH active_contexts AS (
    SELECT context_id, context_type, context_definition
    FROM context_nodes
    WHERE CURRENT_TIMESTAMP BETWEEN valid_from AND valid_until
),
context_weighted_risks AS (
    SELECT 
        cp.control_id,
        ac.context_type,
        cp.risk_score_in_context,
        -- Weight by context type importance
        CASE ac.context_type
            WHEN 'situational' THEN 1.5  -- Current situation most important
            WHEN 'organizational' THEN 1.2
            WHEN 'operational' THEN 1.0
            WHEN 'environmental' THEN 0.8
        END AS context_weight,
        cp.risk_score_in_context * 
        CASE ac.context_type
            WHEN 'situational' THEN 1.5
            WHEN 'organizational' THEN 1.2
            WHEN 'operational' THEN 1.0
            WHEN 'environmental' THEN 0.8
        END AS weighted_risk
    FROM contextual_control_profiles cp
    JOIN active_contexts ac ON cp.context_id = ac.context_id
)
SELECT 
    control_id,
    AVG(risk_score_in_context) AS avg_risk,
    MAX(risk_score_in_context) AS max_risk,
    SUM(weighted_risk) / SUM(context_weight) AS composite_context_risk,
    JSONB_AGG(
        JSONB_BUILD_OBJECT(
            'context', context_type,
            'risk', risk_score_in_context
        )
    ) AS risk_by_context
FROM context_weighted_risks
GROUP BY control_id
ORDER BY composite_context_risk DESC;
```

---

## **LLM Integration with Contextual Graphs**

### **Context-Aware Reasoning Pattern**

```python
# Conceptual workflow

class ContextualGraphReasoningAgent:
    """
    LLM agent that uses contextual graph for situational reasoning
    """
    
    def reason_with_context(self, query, user_context):
        """
        Query: "What access control measures should I prioritize?"
        Context: {
            organization: "Large healthcare system",
            situation: "Preparing for HIPAA audit",
            systems: ["Epic EHR", "Workday", "PACS"],
            automation: "Medium maturity",
            timeline: "60 days until audit"
        }
        """
        
        # Step 1: Retrieve from contextual graph
        relevant_nodes = self.contextual_graph_query(
            query_embedding=embed(query),
            context_filters=user_context,
            return_reasoning=True
        )
        
        # Step 2: LLM reasons with context-enriched data
        reasoning = llm.generate(f"""
        Query: {query}
        
        Your Organization Context:
        - Industry: Healthcare (HIPAA applies)
        - Size: Large (1000+ employees)
        - Systems: Epic EHR, Workday, PACS
        - Automation: Medium maturity
        - Timeline: 60 days until HIPAA audit
        
        Relevant Controls from Contextual Graph:
        {relevant_nodes}
        
        For each control, I've provided:
        - Risk score IN YOUR CONTEXT (not generic)
        - Implementation complexity FOR YOUR ORG (based on systems/maturity)
        - Evidence availability FROM YOUR SYSTEMS (Epic, Workday, PACS)
        - Audit relevance FOR UPCOMING HIPAA AUDIT
        
        Analyze and prioritize considering:
        1. Your specific context (healthcare, audit prep, systems)
        2. What's most achievable in 60 days
        3. What auditors will focus on
        4. What evidence you can realistically collect
        """)
        
        return reasoning
```

**Example Output:**
```
Given your context as a large healthcare organization preparing for a HIPAA 
audit in 60 days with Epic EHR and Workday:

TOP PRIORITY (Immediate - Week 1-2):
1. Access Review Compliance (HIPAA-AC-001)
   - Context-specific risk: 16 (High) - Audit will scrutinize this heavily
   - Your situation: Workday has review capabilities, but may not be configured
   - Achievability: High - Workday API available, n8n automation feasible
   - Evidence: Can extract review reports directly from Workday
   - Action: Configure automated quarterly reviews in Workday, generate 
             reports for last 12 months to show historical compliance

2. Audit Logging (HIPAA-AUDIT-001)
   - Context-specific risk: 15 (High) - Critical for proving access controls
   - Your situation: Epic has audit logs, need to verify 6-year retention
   - Achievability: Medium - May need to configure log aggregation in Splunk
   - Evidence: Epic audit log exports, Splunk retention policies
   - Action: Verify Epic audit logs are forwarded to Splunk with proper retention

MEDIUM PRIORITY (Weeks 3-6):
[Additional context-aware recommendations...]

Note: These priorities are specific to YOUR context. A smaller organization 
or one not facing an imminent audit would have different priorities.
```

---

## **Context Graph Schema Design**

### **Recommended Schema Structure**

```sql
-- ============================================================================
-- CONTEXTUAL GRAPH SCHEMA
-- ============================================================================

-- 1. CORE ENTITIES (from knowledge graph)
CREATE TABLE entities (
    entity_id VARCHAR(100) PRIMARY KEY,
    entity_type VARCHAR(50),  -- 'control', 'requirement', 'evidence', etc.
    entity_name TEXT,
    entity_description TEXT,
    metadata JSONB
);

-- 2. CONTEXT DEFINITIONS
CREATE TABLE contexts (
    context_id SERIAL PRIMARY KEY,
    context_type VARCHAR(50),
    context_name VARCHAR(200),
    context_definition JSONB,
    parent_context_id INTEGER REFERENCES contexts(context_id),
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. CONTEXTUAL PROPERTIES (properties that vary by context)
CREATE TABLE entity_contextual_properties (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(100) REFERENCES entities(entity_id),
    context_id INTEGER REFERENCES contexts(context_id),
    property_name VARCHAR(100),
    property_value JSONB,
    confidence_score DECIMAL(3,2),
    reasoning TEXT,
    data_source TEXT,
    UNIQUE(entity_id, context_id, property_name)
);

-- 4. CONTEXTUAL RELATIONSHIPS
CREATE TABLE contextual_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(100) REFERENCES entities(entity_id),
    relationship_type VARCHAR(50),
    target_entity_id VARCHAR(100) REFERENCES entities(entity_id),
    context_id INTEGER REFERENCES contexts(context_id),
    
    -- Relationship strength in this context
    strength DECIMAL(3,2),
    confidence DECIMAL(3,2),
    
    -- Conditional logic
    conditions JSONB,
    exceptions JSONB,
    
    -- Metadata
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    reasoning TEXT
);

-- 5. CONTEXT INHERITANCE (contexts can inherit from other contexts)
CREATE TABLE context_inheritance (
    child_context_id INTEGER REFERENCES contexts(context_id),
    parent_context_id INTEGER REFERENCES contexts(context_id),
    inheritance_type VARCHAR(50),  -- 'full', 'partial', 'override'
    PRIMARY KEY (child_context_id, parent_context_id)
);

-- Indexes for performance
CREATE INDEX idx_entity_type ON entities(entity_type);
CREATE INDEX idx_context_type ON contexts(context_type);
CREATE INDEX idx_context_def ON contexts USING GIN (context_definition);
CREATE INDEX idx_contextual_props_entity ON entity_contextual_properties(entity_id);
CREATE INDEX idx_contextual_props_context ON entity_contextual_properties(context_id);
CREATE INDEX idx_contextual_rels_source ON contextual_relationships(source_entity_id);
CREATE INDEX idx_contextual_rels_context ON contextual_relationships(context_id);
```

---

## **Practical Implementation: Hybrid Approach**

**Best Practice:** Use hybrid knowledge + contextual graph

```
Layer 1: Knowledge Graph (Universal truths)
├── Static entities and relationships
├── Framework definitions (HIPAA, SOC2)
├── Standard control libraries
└── Universal requirements

Layer 2: Context Layer (Situational awareness)
├── Organizational context nodes
├── Temporal/situational context nodes
├── Operational capability nodes
└── Context-dependent properties

Layer 3: Reasoning Layer (LLM intelligence)
├── Query: "What should I prioritize?"
├── Retrieves: Knowledge graph + Active contexts
├── Reasons: Considering specific situation
└── Returns: Context-aware recommendations
```

**Query Flow:**
```
1. User Query: "What are my highest-risk controls?"

2. Context Activation:
   - Identify active contexts for this user
   - organizational: large_healthcare_org
   - situational: pre_audit_state  
   - operational: medium_automation
   - temporal: Q1_2024

3. Graph Traversal:
   - Start with universal controls (knowledge graph)
   - Apply context filters (contextual graph)
   - Weight by context-specific risk scores
   - Consider context-specific feasibility

4. LLM Reasoning:
   - Synthesize results with context awareness
   - Explain WHY priorities differ in this context
   - Provide actionable guidance FOR THIS SITUATION

5. Response: Context-aware, personalized recommendations
```

---

## **Migration Path: Knowledge → Contextual Graph**

### **Phase 1: Add Minimal Context**

```sql
-- Start by adding context columns to existing tables
ALTER TABLE controls ADD COLUMN context_applicability JSONB;
ALTER TABLE requirements ADD COLUMN context_conditions JSONB;

-- Populate with basic context
UPDATE controls 
SET context_applicability = '{
    "industries": ["healthcare", "finance"],
    "data_types": ["PHI", "PII"]
}'::jsonb
WHERE control_id = 'HIPAA-AC-001';
```

### **Phase 2: Extract Context Nodes**

```sql
-- Create context nodes from existing data patterns
INSERT INTO contexts (context_type, context_name, context_definition)
SELECT DISTINCT
    'organizational' AS context_type,
    'Healthcare Organizations' AS context_name,
    JSONB_BUILD_OBJECT(
        'industry', 'healthcare',
        'applicable_frameworks', ARRAY['HIPAA', 'HITECH'],
        'data_types', ARRAY['ePHI', 'PHI']
    ) AS context_definition
FROM controls
WHERE control_framework = 'HIPAA';
```

### **Phase 3: Link Entities to Contexts**

```sql
-- Create contextual relationships
INSERT INTO contextual_relationships (
    source_entity_id,
    relationship_type,
    target_entity_id,
    context_id,
    strength,
    reasoning
)
SELECT 
    c.control_id,
    'APPLIES_IN_CONTEXT',
    r.requirement_id,
    ctx.context_id,
    0.95,
    'HIPAA controls apply strongly in healthcare context'
FROM controls c
JOIN requirements r ON c.control_id = r.control_id
JOIN contexts ctx ON ctx.context_name = 'Healthcare Organizations'
WHERE c.control_framework = 'HIPAA';
```

### **Phase 4: Add Context-Specific Properties**

```sql
-- LLM generates context-specific risk scores
INSERT INTO entity_contextual_properties 
    (entity_id, context_id, property_name, property_value, reasoning)
VALUES
    ('HIPAA-AC-001', 
     1,  -- Healthcare context
     'risk_score',
     '{"likelihood": 3, "impact": 4, "score": 12}'::jsonb,
     'In healthcare context, access control failures have high impact (ePHI exposure) 
      and moderate likelihood (complex systems, staff turnover)');
```

---

## **Key Takeaways**

```
Knowledge Graph → Contextual Graph Transformation:

1. ADD CONTEXT AS FIRST-CLASS ENTITIES
   └── Context nodes (organizational, temporal, operational, etc.)

2. QUALIFY RELATIONSHIPS WITH CONTEXT
   └── Edges have context conditions and strength

3. MAKE PROPERTIES CONTEXT-DEPENDENT
   └── Risk, priority, feasibility vary by context

4. ENABLE TEMPORAL REASONING
   └── Context changes over time (before/during/after audit)

5. SUPPORT MULTI-CONTEXT QUERIES
   └── "What's important FOR ME, RIGHT NOW?"

6. LLM REASONS WITH CONTEXT
   └── Not just "what's required" but "what's relevant to you"

Result: From generic compliance checklist to personalized, 
        situation-aware risk intelligence
```