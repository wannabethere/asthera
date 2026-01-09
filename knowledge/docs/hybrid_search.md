# **Contextual Graph with Hybrid Vector + Relational Architecture**

## **The Core Insight**

```
Problem with Pure PostgreSQL for Contextual Graphs:
├── Context matching is fuzzy, not exact
│   └── "healthcare org preparing for audit" should match
│       "medical facility in pre-audit state" (semantic similarity)
│
├── Context definitions are multi-dimensional
│   └── Can't easily index {"industry": "healthcare", "maturity": "developing", 
│       "situation": "audit_prep", "systems": ["EHR", "Workday"]}
│
├── Context relevance requires scoring
│   └── Which context node is MOST relevant to this query?
│
└── Context searches need semantic understanding
    └── "Show me controls for organizations like mine" requires
        understanding what "like mine" means semantically

Solution: Hybrid Vector Store + Relational Database
├── Vector Store: Semantic context matching, relevance scoring
├── Relational DB: Structured relationships, transactions, joins
└── Combined: Best of both worlds
```

---

## **Architecture: Hybrid Storage Strategy**

### **Storage Allocation**

```
┌─────────────────────────────────────────────────────────────────┐
│ POSTGRESQL (Relational)                                         │
│                                                                 │
│ Best for:                                                       │
│ ✓ Structured entities (controls, requirements)                 │
│ ✓ Hard relationships (control REQUIRES requirement)            │
│ ✓ Transactional data (audit logs, compliance measurements)     │
│ ✓ Aggregations and analytics                                   │
│ ✓ Foreign keys and referential integrity                       │
└─────────────────────────────────────────────────────────────────┘
                              ↕
                    Synchronized via IDs
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│ VECTOR STORE (ChromaDB / Qdrant)                               │
│                                                                 │
│ Best for:                                                       │
│ ✓ Context definitions (fuzzy, semantic)                        │
│ ✓ Context matching ("find similar contexts")                   │
│ ✓ Contextual edges (with rich metadata)                        │
│ ✓ Semantic search ("controls relevant to my situation")        │
│ ✓ Hybrid search (TF-IDF + embeddings)                          │
│ ✓ Relevance scoring                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## **Implementation Architecture**

### **Component 1: PostgreSQL Schema (Simplified)**

```sql
-- ============================================================================
-- POSTGRESQL: Core Structured Data
-- ============================================================================

-- Core entities with minimal context
CREATE TABLE controls (
    control_id VARCHAR(100) PRIMARY KEY,
    framework VARCHAR(50),
    control_name TEXT,
    control_description TEXT,
    category VARCHAR(100),
    
    -- Basic metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Vector store references
    vector_doc_id VARCHAR(100),  -- Reference to vector store document
    embedding_version VARCHAR(50)
);

CREATE TABLE requirements (
    requirement_id VARCHAR(100) PRIMARY KEY,
    control_id VARCHAR(100) REFERENCES controls(control_id),
    requirement_text TEXT,
    requirement_type VARCHAR(50),
    
    vector_doc_id VARCHAR(100)
);

CREATE TABLE evidence_types (
    evidence_id VARCHAR(100) PRIMARY KEY,
    evidence_name TEXT,
    evidence_category VARCHAR(50),
    collection_method TEXT,
    
    vector_doc_id VARCHAR(100)
);

-- Hard relationships (context-independent)
CREATE TABLE control_requirement_mapping (
    control_id VARCHAR(100) REFERENCES controls(control_id),
    requirement_id VARCHAR(100) REFERENCES requirements(requirement_id),
    is_mandatory BOOLEAN DEFAULT true,
    PRIMARY KEY (control_id, requirement_id)
);

-- Measurement data (time-series, transactional)
CREATE TABLE compliance_measurements (
    measurement_id SERIAL PRIMARY KEY,
    control_id VARCHAR(100) REFERENCES controls(control_id),
    measured_value DECIMAL(10,2),
    measurement_date TIMESTAMP,
    passed BOOLEAN,
    
    -- Context reference
    context_id VARCHAR(100),  -- References vector store context
    
    INDEX idx_measurements_date (measurement_date),
    INDEX idx_measurements_control (control_id)
);

-- Aggregated analytics (PostgreSQL is great for this)
CREATE TABLE control_risk_analytics (
    control_id VARCHAR(100) PRIMARY KEY,
    avg_compliance_score DECIMAL(5,2),
    trend VARCHAR(20),  -- 'improving', 'stable', 'degrading'
    last_failure_date DATE,
    failure_count_30d INTEGER,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **Component 2: Vector Store Schema (ChromaDB/Qdrant)**

#### **Collection 1: Context Definitions**

```python
# ============================================================================
# VECTOR STORE: Context Definitions Collection
# ============================================================================

context_collection = {
    "name": "context_definitions",
    "embedding_model": "all-MiniLM-L6-v2",  # or text-embedding-ada-002
    "metadata_config": {
        "index_fields": [
            "context_type",
            "industry", 
            "organization_size",
            "maturity_level",
            "regulatory_frameworks",
            "active_status"
        ]
    }
}

# Example Context Documents in Vector Store
contexts = [
    {
        "id": "ctx_001",
        "document": """
        Large healthcare organization with developing compliance maturity.
        Operates in United States with 1000-5000 employees. Manages electronic 
        Protected Health Information (ePHI) across Epic EHR, Workday HCM, and 
        PACS systems. Subject to HIPAA and state breach notification laws.
        Has medium automation capability with established IAM (Okta) and 
        SIEM (Splunk) platforms. Currently preparing for upcoming HIPAA 
        compliance audit scheduled within 90 days.
        """,
        "metadata": {
            "context_id": "ctx_001",
            "context_type": "organizational_situational",
            "industry": "healthcare",
            "organization_size": "large",
            "employee_count_range": "1000-5000",
            "maturity_level": "developing",
            "regulatory_frameworks": ["HIPAA", "state_breach_laws"],
            "data_types": ["ePHI", "PHI", "PII"],
            "systems": ["Epic_EHR", "Workday", "PACS", "Okta", "Splunk"],
            "automation_capability": "medium",
            "current_situation": "pre_audit",
            "audit_timeline_days": 90,
            "active_status": True,
            "created_at": "2024-01-01T00:00:00Z"
        },
        "embedding": [0.123, -0.456, 0.789, ...]  # Dense vector
    },
    {
        "id": "ctx_002",
        "document": """
        Small technology startup in rapid growth phase. Located in California
        with 50-200 employees. Primarily handles customer data (PII) and 
        payment information (PCI). Subject to SOC 2 Type II requirements 
        for B2B SaaS customers. Limited compliance maturity with basic 
        security controls in place. High automation capability using modern
        cloud infrastructure (AWS, Okta, Datadog). Planning SOC 2 audit
        for first time in 6 months.
        """,
        "metadata": {
            "context_id": "ctx_002",
            "context_type": "organizational_situational",
            "industry": "technology",
            "organization_size": "small",
            "employee_count_range": "50-200",
            "maturity_level": "nascent",
            "regulatory_frameworks": ["SOC2", "PCI_DSS_lite"],
            "data_types": ["PII", "payment_data"],
            "systems": ["AWS", "Okta", "Datadog", "Stripe"],
            "automation_capability": "high",
            "current_situation": "first_audit_prep",
            "audit_timeline_days": 180,
            "active_status": True,
            "created_at": "2024-01-01T00:00:00Z"
        },
        "embedding": [0.234, -0.567, 0.890, ...]
    }
]
```

#### **Collection 2: Contextual Edges**

```python
# ============================================================================
# VECTOR STORE: Contextual Edges Collection
# ============================================================================

contextual_edges_collection = {
    "name": "contextual_edges",
    "embedding_model": "all-MiniLM-L6-v2",
    "metadata_config": {
        "index_fields": [
            "source_entity_id",
            "target_entity_id",
            "edge_type",
            "context_id",
            "relevance_score",
            "priority_in_context"
        ]
    }
}

# Example Contextual Edge Documents
contextual_edges = [
    {
        "id": "edge_001",
        "document": """
        Control HIPAA-AC-001 (Access Control to ePHI Systems) has CRITICAL 
        priority for large healthcare organizations preparing for HIPAA audit.
        
        Reasoning: Access control is fundamental HIPAA requirement that auditors 
        scrutinize heavily. Large organizations with multiple systems (EHR, HCM, 
        PACS) face complexity in maintaining consistent access controls. During 
        pre-audit period, demonstrating access review compliance is essential.
        
        Implementation in this context: Leverage existing Workday HCM for role 
        management. Configure quarterly automated reviews using Okta workflows.
        Export access reports from Okta for audit trail. Estimated effort: 80 hours.
        
        Risk in this context: Likelihood=3 (moderate - manual processes prone to 
        delays), Impact=4 (high - audit finding, potential PHI exposure), 
        Risk Score=12 (HIGH).
        
        Evidence requirements: Access review reports from Okta, manager approval 
        documentation from Workday, access provisioning/deprovisioning logs from 
        all ePHI systems.
        """,
        "metadata": {
            "edge_id": "edge_001",
            "source_entity_id": "HIPAA-AC-001",
            "source_entity_type": "control",
            "target_entity_id": "access_reviews_requirement",
            "target_entity_type": "requirement",
            "edge_type": "HAS_REQUIREMENT_IN_CONTEXT",
            "context_id": "ctx_001",  # Large healthcare, pre-audit
            
            # Scores and priorities
            "relevance_score": 0.95,
            "priority_in_context": 1,
            "risk_score_in_context": 12,
            "likelihood_in_context": 3,
            "impact_in_context": 4,
            "implementation_complexity": "moderate",
            "estimated_effort_hours": 80,
            "estimated_cost": 15000,
            
            # Conditional factors
            "prerequisites": ["IAM_system_exists", "RBAC_model_defined"],
            "automation_possible": True,
            "evidence_available": True,
            "data_quality": "high",
            
            # Temporal
            "created_at": "2024-01-01T00:00:00Z",
            "valid_until": "2024-12-31T23:59:59Z"
        },
        "embedding": [0.345, -0.678, 0.901, ...]  # Dense vector from document
    },
    {
        "id": "edge_002", 
        "document": """
        Control SOC2-CC6.1 (Logical Access - User Access) has HIGH priority 
        for small technology startups preparing for first SOC 2 audit.
        
        Reasoning: First-time SOC 2 audits focus heavily on access controls 
        as they're foundational. Small orgs often lack formal processes, making 
        this a common finding. However, with high automation capability and 
        cloud-native infrastructure, implementation is straightforward.
        
        Implementation in this context: Leverage Okta SSO for all applications.
        Configure automated provisioning/deprovisioning. Implement MFA across 
        all systems. Set up quarterly access reviews in Okta. Estimated effort: 
        40 hours (easier than healthcare due to fewer systems, modern tooling).
        
        Risk in this context: Likelihood=4 (high - startups often have informal 
        processes), Impact=3 (moderate - no PHI, but customer trust critical), 
        Risk Score=12 (HIGH).
        
        Evidence requirements: Okta access logs, MFA configuration screenshots,
        access review reports, onboarding/offboarding checklists.
        """,
        "metadata": {
            "edge_id": "edge_002",
            "source_entity_id": "SOC2-CC6.1",
            "source_entity_type": "control",
            "target_entity_id": "user_access_requirement",
            "target_entity_type": "requirement",
            "edge_type": "HAS_REQUIREMENT_IN_CONTEXT",
            "context_id": "ctx_002",  # Small tech, first SOC2 audit
            
            "relevance_score": 0.90,
            "priority_in_context": 2,
            "risk_score_in_context": 12,
            "likelihood_in_context": 4,
            "impact_in_context": 3,
            "implementation_complexity": "simple",
            "estimated_effort_hours": 40,
            "estimated_cost": 8000,
            
            "prerequisites": ["Okta_SSO_deployed"],
            "automation_possible": True,
            "evidence_available": True,
            "data_quality": "high",
            
            "created_at": "2024-01-01T00:00:00Z",
            "valid_until": "2024-12-31T23:59:59Z"
        },
        "embedding": [0.456, -0.789, 0.012, ...]
    }
]
```

#### **Collection 3: Control-Context Profiles**

```python
# ============================================================================
# VECTOR STORE: Control Profiles with Context
# ============================================================================

control_profiles_collection = {
    "name": "control_context_profiles",
    "embedding_model": "all-MiniLM-L6-v2",
    "metadata_config": {
        "index_fields": [
            "control_id",
            "context_id",
            "framework",
            "risk_level",
            "implementation_feasibility",
            "automation_possible"
        ]
    }
}

control_profiles = [
    {
        "id": "profile_hipaa_ac001_ctx001",
        "document": """
        HIPAA Access Control (164.312(a)) implementation for large healthcare 
        organization with developing maturity in pre-audit state.
        
        Control Overview: Implement technical policies and procedures for 
        electronic information systems that maintain ePHI to allow access only 
        to authorized persons.
        
        Context-Specific Implementation: 
        - Complexity: MODERATE due to multiple legacy systems (Epic EHR from 2015,
          Workday implemented 2020, aging PACS system requiring special integration)
        - Systems in scope: Epic EHR (15,000 users), Workday (all employees), 
          PACS (500 radiologists), Patient Portal (50,000+ patients)
        - Current state: Okta SSO covers 60% of systems, legacy PACS uses 
          separate AD authentication
        - Gap: No centralized access review process, reviews ad-hoc by department
        
        Risk Assessment in Context:
        - Inherent risk: HIGH (Risk=12, L=3, I=4)
        - Current control effectiveness: 40% (some controls exist but inconsistent)
        - Residual risk: MEDIUM-HIGH (Risk=7.2)
        - Primary risk: Audit finding for inadequate access controls
        
        Implementation Roadmap (90-day audit timeline):
        Week 1-2: Configure Okta access review workflows for existing integrations
        Week 3-4: Integrate PACS with Okta (or document compensating controls)
        Week 5-6: Run first access review cycle, document processes
        Week 7-8: Generate historical access reports (last 12 months)
        Week 9-10: Remediate identified issues, prepare audit documentation
        Weeks 11-12: Buffer for audit prep, mock audit
        
        Effort: 80 hours (2 FTE weeks)
        Cost: $15,000 (internal effort + consulting for PACS integration)
        Success probability: 75% (some risk with PACS integration)
        
        Evidence Strategy:
        - Primary: Okta access review reports (automated quarterly)
        - Secondary: Workday manager approvals (workflow documentation)
        - Compensating: PACS manual access review logs (if integration not feasible)
        - Audit trail: Access provisioning/deprovisioning logs from all systems
        
        Metrics in this context:
        1. access_review_interval_days (Target: ≤90, Current: ~180)
        2. inappropriate_access_count (Target: 0, Current: Unknown)
        3. review_completion_rate (Target: 100%, Current: ~30%)
        4. time_to_provision_access (Target: ≤24hrs, Current: ~72hrs)
        5. time_to_deprovision_access (Target: ≤4hrs, Current: ~48hrs)
        """,
        "metadata": {
            "profile_id": "profile_hipaa_ac001_ctx001",
            "control_id": "HIPAA-AC-001",
            "context_id": "ctx_001",
            "framework": "HIPAA",
            "control_category": "access_control",
            
            # Risk scores
            "inherent_risk_score": 12,
            "current_control_effectiveness": 0.40,
            "residual_risk_score": 7.2,
            "risk_level": "MEDIUM_HIGH",
            
            # Implementation
            "implementation_complexity": "moderate",
            "estimated_effort_hours": 80,
            "estimated_cost": 15000,
            "success_probability": 0.75,
            "implementation_feasibility": "feasible",
            "timeline_weeks": 12,
            
            # Automation
            "automation_possible": True,
            "automation_coverage": 0.75,
            "manual_effort_remaining": 0.25,
            
            # Evidence
            "evidence_available": True,
            "evidence_quality": "good",
            "evidence_gaps": ["PACS_access_logs"],
            
            # Current state
            "systems_in_scope": ["Epic_EHR", "Workday", "PACS", "Patient_Portal"],
            "systems_count": 4,
            "users_in_scope": 15500,
            "integration_maturity": 0.60,
            
            # Metrics
            "metrics_defined": True,
            "metrics_count": 5,
            "metrics_automated": 0.80,
            
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-06T00:00:00Z"
        },
        "embedding": [0.567, -0.890, 0.123, ...]
    }
]
```

---

## **Hybrid Search Patterns**

### **Pattern 1: Context Matching with Hybrid Search**

```python
# ============================================================================
# HYBRID SEARCH: Find Similar Contexts
# ============================================================================

from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi

class ContextualGraphQueryEngine:
    
    def __init__(self, chroma_client, postgres_conn):
        self.chroma = chroma_client
        self.pg = postgres_conn
        
        # Collections
        self.contexts = self.chroma.get_collection("context_definitions")
        self.edges = self.chroma.get_collection("contextual_edges")
        self.profiles = self.chroma.get_collection("control_context_profiles")
    
    def find_relevant_contexts(self, user_context_description, top_k=5):
        """
        Find contexts most relevant to user's situation using hybrid search.
        
        Combines:
        1. Dense vector similarity (semantic understanding)
        2. BM25 sparse retrieval (keyword matching)
        3. Metadata filtering (structured constraints)
        """
        
        # Step 1: Dense vector search (semantic similarity)
        dense_results = self.contexts.query(
            query_texts=[user_context_description],
            n_results=top_k * 2,  # Get more candidates
            include=["documents", "metadatas", "distances"]
        )
        
        # Step 2: Get documents for BM25
        documents = dense_results["documents"][0]
        metadatas = dense_results["metadatas"][0]
        
        # Step 3: BM25 ranking (keyword-based)
        tokenized_docs = [doc.lower().split() for doc in documents]
        tokenized_query = user_context_description.lower().split()
        bm25 = BM25Okapi(tokenized_docs)
        bm25_scores = bm25.get_scores(tokenized_query)
        
        # Step 4: Hybrid scoring
        # Normalize dense scores (cosine similarity, lower is better in chromadb)
        dense_scores = [1 / (1 + dist) for dist in dense_results["distances"][0]]
        
        # Normalize BM25 scores
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        normalized_bm25 = [score / max_bm25 for score in bm25_scores]
        
        # Combined score (weighted)
        DENSE_WEIGHT = 0.7
        SPARSE_WEIGHT = 0.3
        
        combined_results = []
        for i, metadata in enumerate(metadatas):
            combined_score = (
                DENSE_WEIGHT * dense_scores[i] + 
                SPARSE_WEIGHT * normalized_bm25[i]
            )
            combined_results.append({
                "context_id": metadata["context_id"],
                "document": documents[i],
                "metadata": metadata,
                "dense_score": dense_scores[i],
                "bm25_score": normalized_bm25[i],
                "combined_score": combined_score
            })
        
        # Sort by combined score and return top_k
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        return combined_results[:top_k]

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

query_engine = ContextualGraphQueryEngine(chroma_client, pg_conn)

user_input = """
We're a healthcare provider with about 2000 employees. We use Epic for 
our EHR and Workday for HR. We have a HIPAA audit coming up in about 
3 months and need to make sure our access controls are solid. We've got 
Okta set up but haven't really configured access reviews properly yet.
"""

# Find similar contexts using hybrid search
relevant_contexts = query_engine.find_relevant_contexts(user_input, top_k=3)

print("Top 3 Similar Contexts:")
for ctx in relevant_contexts:
    print(f"\nContext: {ctx['context_id']}")
    print(f"Combined Score: {ctx['combined_score']:.3f}")
    print(f"  - Dense (semantic): {ctx['dense_score']:.3f}")
    print(f"  - BM25 (keyword): {ctx['bm25_score']:.3f}")
    print(f"Industry: {ctx['metadata']['industry']}")
    print(f"Size: {ctx['metadata']['organization_size']}")
    print(f"Situation: {ctx['metadata']['current_situation']}")

# Output:
# Context: ctx_001
# Combined Score: 0.892
#   - Dense (semantic): 0.94  (high - semantic match on "healthcare", "audit prep", "Epic", "Okta")
#   - BM25 (keyword): 0.78    (good - keyword match on "healthcare", "HIPAA", "Epic", "Workday", "Okta")
# Industry: healthcare
# Size: large
# Situation: pre_audit
```

### **Pattern 2: Context-Aware Control Retrieval**

```python
def get_priority_controls_for_context(
    self, 
    context_id: str,
    query: str = None,
    filters: dict = None,
    top_k: int = 10
):
    """
    Retrieve controls prioritized for specific context using hybrid search.
    
    Args:
        context_id: The active context
        query: Natural language query (optional)
        filters: Metadata filters (optional)
        top_k: Number of results
    """
    
    # Build metadata filter
    where_clause = {"context_id": context_id}
    if filters:
        where_clause.update(filters)
    
    if query:
        # Hybrid search with query
        results = self.profiles.query(
            query_texts=[query],
            n_results=top_k,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )
    else:
        # Metadata filtering only, sorted by priority
        results = self.profiles.get(
            where=where_clause,
            limit=top_k,
            include=["documents", "metadatas"]
        )
    
    # Enrich with PostgreSQL data
    control_ids = [m["control_id"] for m in results["metadatas"][0]]
    
    # Get current compliance status from PostgreSQL
    pg_query = """
        SELECT 
            control_id,
            avg_compliance_score,
            trend,
            last_failure_date,
            failure_count_30d
        FROM control_risk_analytics
        WHERE control_id = ANY(%s)
    """
    compliance_data = self.pg.execute(pg_query, (control_ids,))
    compliance_map = {row["control_id"]: row for row in compliance_data}
    
    # Combine vector store context + PostgreSQL reality
    enriched_results = []
    for i, control_id in enumerate(control_ids):
        enriched_results.append({
            "control_id": control_id,
            "context_profile": results["metadatas"][0][i],
            "current_compliance": compliance_map.get(control_id, {}),
            "semantic_relevance": 1 / (1 + results["distances"][0][i]),
            "reasoning": results["documents"][0][i]
        })
    
    return enriched_results

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

# User query in natural language
user_query = """
Show me the most important access control requirements I should focus on 
for the upcoming audit. I want to know what's feasible to implement in 
the next 60 days.
"""

# Get priority controls for user's context
priority_controls = query_engine.get_priority_controls_for_context(
    context_id="ctx_001",  # From earlier context matching
    query=user_query,
    filters={
        "framework": "HIPAA",
        "implementation_feasibility": "feasible",
        "timeline_weeks": {"$lte": 10}  # ≤10 weeks (~60 days)
    },
    top_k=5
)

for control in priority_controls:
    print(f"\nControl: {control['control_id']}")
    print(f"Semantic Relevance: {control['semantic_relevance']:.2f}")
    
    # From vector store (context-specific)
    profile = control['context_profile']
    print(f"Risk in Your Context: {profile['risk_level']}")
    print(f"Effort: {profile['estimated_effort_hours']} hours")
    print(f"Cost: ${profile['estimated_cost']:,}")
    print(f"Timeline: {profile['timeline_weeks']} weeks")
    
    # From PostgreSQL (current reality)
    compliance = control['current_compliance']
    print(f"Current Compliance: {compliance.get('avg_compliance_score', 'N/A')}%")
    print(f"Trend: {compliance.get('trend', 'N/A')}")
    print(f"Failures (30d): {compliance.get('failure_count_30d', 0)}")
```

### **Pattern 3: Multi-Hop Contextual Reasoning**

```python
def multi_hop_contextual_search(
    self,
    initial_query: str,
    context_id: str,
    max_hops: int = 3
):
    """
    Multi-hop reasoning through contextual graph using vector search.
    
    Example flow:
    1. Query: "What evidence do I need for access controls?"
    2. Hop 1: Find relevant controls in context
    3. Hop 2: Find requirements for those controls
    4. Hop 3: Find evidence types for those requirements
    """
    
    reasoning_path = []
    current_entities = []
    
    # Hop 1: Find relevant controls
    print(f"Hop 1: Finding controls for: '{initial_query}'")
    control_results = self.profiles.query(
        query_texts=[initial_query],
        n_results=3,
        where={"context_id": context_id},
        include=["documents", "metadatas", "distances"]
    )
    
    control_ids = [m["control_id"] for m in control_results["metadatas"][0]]
    reasoning_path.append({
        "hop": 1,
        "query": initial_query,
        "entity_type": "controls",
        "entities_found": control_ids,
        "reasoning": control_results["documents"][0][0][:300]
    })
    
    # Hop 2: Find contextual requirements for these controls
    print(f"Hop 2: Finding requirements for controls: {control_ids}")
    requirement_query = f"Requirements for controls {', '.join(control_ids)} in this context"
    
    requirement_results = self.edges.query(
        query_texts=[requirement_query],
        n_results=5,
        where={
            "source_entity_id": {"$in": control_ids},
            "context_id": context_id,
            "target_entity_type": "requirement"
        },
        include=["documents", "metadatas", "distances"]
    )
    
    requirement_ids = [m["target_entity_id"] for m in requirement_results["metadatas"][0]]
    reasoning_path.append({
        "hop": 2,
        "entity_type": "requirements",
        "entities_found": requirement_ids,
        "reasoning": requirement_results["documents"][0][0][:300]
    })
    
    # Hop 3: Find evidence types for these requirements
    print(f"Hop 3: Finding evidence for requirements: {requirement_ids}")
    evidence_query = f"Evidence that proves requirements {', '.join(requirement_ids)}"
    
    evidence_results = self.edges.query(
        query_texts=[evidence_query],
        n_results=5,
        where={
            "source_entity_id": {"$in": requirement_ids},
            "context_id": context_id,
            "target_entity_type": "evidence"
        },
        include=["documents", "metadatas", "distances"]
    )
    
    evidence_ids = [m["target_entity_id"] for m in evidence_results["metadatas"][0]]
    reasoning_path.append({
        "hop": 3,
        "entity_type": "evidence",
        "entities_found": evidence_ids,
        "reasoning": evidence_results["documents"][0][0][:300]
    })
    
    # Synthesize with LLM
    synthesis_prompt = f"""
    User Question: {initial_query}
    Context: {context_id}
    
    Multi-hop reasoning path:
    {json.dumps(reasoning_path, indent=2)}
    
    Synthesize a complete answer explaining:
    1. Which controls are relevant in this context
    2. What requirements they have
    3. What evidence is needed
    4. How to collect that evidence given the organizational context
    """
    
    # LLM generates final answer
    final_answer = llm.generate(synthesis_prompt)
    
    return {
        "reasoning_path": reasoning_path,
        "final_answer": final_answer
    }

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

result = query_engine.multi_hop_contextual_search(
    initial_query="What evidence do I need to prepare for access control audit?",
    context_id="ctx_001",
    max_hops=3
)

print("\n=== REASONING PATH ===")
for hop in result["reasoning_path"]:
    print(f"\nHop {hop['hop']}: {hop['entity_type']}")
    print(f"Entities: {hop['entities_found']}")
    print(f"Reasoning: {hop['reasoning']}")

print("\n=== SYNTHESIZED ANSWER ===")
print(result["final_answer"])

# Output:
# === REASONING PATH ===
# 
# Hop 1: controls
# Entities: ['HIPAA-AC-001', 'HIPAA-AC-002']
# Reasoning: For large healthcare organizations preparing for HIPAA audit, 
# access control (164.312(a)) is critical. Auditors will scrutinize user 
# access management, especially for Epic EHR and ePHI systems...
# 
# Hop 2: requirements  
# Entities: ['quarterly_access_reviews', 'unique_user_identification', 'emergency_access']
# Reasoning: In your context, access reviews must occur quarterly. Given 
# Okta integration, automated workflows can handle this. Emergency access 
# procedures needed for Epic EHR...
#
# Hop 3: evidence
# Entities: ['access_review_reports', 'okta_audit_logs', 'epic_access_logs']
# Reasoning: Access review reports from Okta proving quarterly reviews. 
# Manager approvals from Workday. Epic audit logs showing access patterns...
#
# === SYNTHESIZED ANSWER ===
# For your upcoming HIPAA audit, focus on these evidence items:
# 
# 1. Access Review Reports (Critical Priority)
#    - Export from Okta showing quarterly reviews for last 12 months
#    - Include manager approvals from Workday workflows
#    - Should cover all Epic EHR users, Workday users, PACS users
#    
# 2. Audit Logs (High Priority)
#    - Epic EHR access logs (last 6 years per HIPAA requirement)
#    - Okta authentication logs
#    - PACS access logs
#    ...
```

---

## **Performance Optimization Strategies**

### **Strategy 1: Indexed Metadata Filtering**

```python
# ============================================================================
# FAST FILTERING: Use metadata indexes before vector search
# ============================================================================

def get_controls_fast_filter(self, context_metadata: dict, query: str = None):
    """
    Fast path: Filter by metadata first, then semantic search.
    Avoids computing embeddings for irrelevant documents.
    """
    
    # Step 1: Narrow down with metadata filters (very fast)
    where_clause = {
        "context_id": context_metadata.get("context_id"),
        "framework": {"$in": context_metadata.get("frameworks", [])},
        "implementation_feasibility": "feasible",
        "risk_level": {"$in": ["HIGH", "CRITICAL"]}
    }
    
    # Step 2: Get candidate set (metadata filtering only)
    candidates = self.profiles.get(
        where=where_clause,
        limit=100,  # Get reasonable candidate set
        include=["documents", "metadatas", "ids"]
    )
    
    if not query:
        # No semantic search needed, sort by metadata priority
        sorted_results = sorted(
            zip(candidates["ids"], candidates["metadatas"], candidates["documents"]),
            key=lambda x: (
                -x[1].get("risk_score_in_context", 0),  # Higher risk first
                x[1].get("estimated_effort_hours", 999)  # Lower effort first
            )
        )
        return sorted_results[:10]
    
    # Step 3: Semantic search within filtered candidates
    # Create temporary collection for candidates
    temp_collection = self.chroma.create_collection(
        name=f"temp_{uuid.uuid4().hex[:8]}",
        metadata={"hnsw:space": "cosine"}
    )
    
    temp_collection.add(
        ids=candidates["ids"],
        documents=candidates["documents"],
        metadatas=candidates["metadatas"]
    )
    
    # Query within filtered set
    results = temp_collection.query(
        query_texts=[query],
        n_results=10
    )
    
    # Cleanup
    self.chroma.delete_collection(name=temp_collection.name)
    
    return results
```

### **Strategy 2: Pre-Computed Embeddings for Common Contexts**

```python
# ============================================================================
# CACHING: Pre-compute embeddings for common query patterns
# ============================================================================

COMMON_CONTEXT_QUERIES = [
    "healthcare organization preparing for audit",
    "technology startup first SOC2 audit",
    "financial services high maturity",
    "retail medium maturity PCI compliance",
    # ... more common patterns
]

def precompute_common_embeddings(self):
    """
    Pre-compute embeddings for common context patterns.
    Store in fast lookup cache (Redis or similar).
    """
    
    embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    cache = {}
    for query in COMMON_CONTEXT_QUERIES:
        embedding = embedding_model([query])[0]
        cache[query] = embedding
        
    # Store in Redis for fast lookup
    redis_client.set("context_embeddings", json.dumps(cache))
    
    return cache

def context_match_with_cache(self, user_description: str):
    """
    Check cache for similar queries before computing new embedding.
    """
    
    cached_embeddings = json.loads(redis_client.get("context_embeddings"))
    
    # Fuzzy match user description to cached queries
    from difflib import get_close_matches
    matches = get_close_matches(
        user_description.lower(), 
        [q.lower() for q in cached_embeddings.keys()],
        n=1,
        cutoff=0.7
    )
    
    if matches:
        # Use cached embedding (very fast)
        cached_query = matches[0]
        cached_embedding = cached_embeddings[cached_query]
        
        # Search with cached embedding
        results = self.contexts.query(
            query_embeddings=[cached_embedding],
            n_results=5
        )
    else:
        # Compute new embedding (slower)
        results = self.contexts.query(
            query_texts=[user_description],
            n_results=5
        )
    
    return results
```

### **Strategy 3: Hybrid Storage with Smart Routing**

```python
# ============================================================================
# SMART ROUTING: Route queries to optimal storage based on query type
# ============================================================================

class SmartStorageRouter:
    
    def route_query(self, query: dict):
        """
        Route queries to PostgreSQL or Vector Store based on query characteristics.
        """
        
        # Analytic aggregation → PostgreSQL
        if query.get("type") == "aggregation":
            return self.pg_aggregation_query(query)
        
        # Exact entity lookup → PostgreSQL
        elif query.get("type") == "lookup" and query.get("entity_id"):
            return self.pg_lookup_query(query)
        
        # Fuzzy/semantic search → Vector Store
        elif query.get("type") == "semantic_search":
            return self.vector_search_query(query)
        
        # Context-aware retrieval → Hybrid
        elif query.get("type") == "contextual":
            return self.hybrid_contextual_query(query)
        
        # Time-series analysis → PostgreSQL
        elif query.get("type") == "time_series":
            return self.pg_time_series_query(query)
    
    def hybrid_contextual_query(self, query: dict):
        """
        Combine vector search for context + PostgreSQL for current state.
        """
        
        # Step 1: Vector search for context-relevant controls
        context_results = self.vector_store.query(
            query_texts=[query["natural_language_query"]],
            where={"context_id": query["context_id"]},
            n_results=20
        )
        
        control_ids = [m["control_id"] for m in context_results["metadatas"][0]]
        
        # Step 2: PostgreSQL for current compliance status
        pg_query = """
            WITH recent_measurements AS (
                SELECT 
                    control_id,
                    AVG(measured_value) as avg_score,
                    COUNT(*) FILTER (WHERE passed = false) as failure_count
                FROM compliance_measurements
                WHERE control_id = ANY(%s)
                  AND measurement_date >= NOW() - INTERVAL '30 days'
                GROUP BY control_id
            )
            SELECT 
                c.control_id,
                c.control_name,
                rm.avg_score,
                rm.failure_count,
                ara.trend
            FROM controls c
            LEFT JOIN recent_measurements rm ON c.control_id = rm.control_id
            LEFT JOIN control_risk_analytics ara ON c.control_id = ara.control_id
            WHERE c.control_id = ANY(%s)
        """
        
        pg_results = self.pg_conn.execute(pg_query, (control_ids, control_ids))
        
        # Step 3: Merge results
        merged = []
        for i, control_id in enumerate(control_ids):
            vector_data = {
                "control_id": control_id,
                "context_reasoning": context_results["documents"][0][i],
                "context_metadata": context_results["metadatas"][0][i]
            }
            
            pg_data = next((r for r in pg_results if r["control_id"] == control_id), {})
            
            merged.append({**vector_data, **pg_data})
        
        return merged

# Example usage
router = SmartStorageRouter(pg_conn, vector_store)

# Semantic query → Vector Store
result1 = router.route_query({
    "type": "semantic_search",
    "natural_language_query": "access control requirements for healthcare",
    "context_id": "ctx_001"
})

# Aggregation → PostgreSQL
result2 = router.route_query({
    "type": "aggregation",
    "query": """
        SELECT 
            framework,
            COUNT(*) as control_count,
            AVG(avg_compliance_score) as avg_compliance
        FROM controls c
        JOIN control_risk_analytics ara ON c.control_id = ara.control_id
        GROUP BY framework
    """
})

# Hybrid → Both stores
result3 = router.route_query({
    "type": "contextual",
    "natural_language_query": "highest priority controls for my organization",
    "context_id": "ctx_001"
})
```

---

## **Benefits Summary**

```
Vector Store + PostgreSQL Hybrid Architecture:

✓ Semantic Context Matching
  └── "Organizations like mine" finds similar contexts via embeddings
  
✓ Fuzzy Context Relevance
  └── No exact match needed, similarity scoring handles variation
  
✓ Multi-Dimensional Context Filtering
  └── Combine metadata filters + semantic search efficiently
  
✓ Hybrid Search (TF-IDF + Dense)
  └── Best of keyword matching + semantic understanding
  
✓ Scalable to Millions of Edges
  └── Vector stores handle scale better than graph traversal
  
✓ Fast Context-Aware Retrieval
  └── HNSW indices for sub-100ms semantic search
  
✓ Maintain Relational Integrity
  └── PostgreSQL for transactions, joins, aggregations
  
✓ LLM-Friendly Reasoning
  └── Rich text documents in vector store feed directly to LLM context
  
✓ Flexible Schema Evolution
  └── Add new context dimensions without schema migrations
  
✓ Cost-Effective
  └── Vector stores cheaper than graph databases for this use case
```

This hybrid architecture gives you the semantic power of vector search for context matching while maintaining the relational guarantees and analytical capabilities of PostgreSQL!