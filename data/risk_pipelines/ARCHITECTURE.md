# Universal Risk Platform - Architecture Design

## Table of Contents
1. [System Overview](#system-overview)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Transfer Learning Mechanism](#transfer-learning-mechanism)
5. [Database Design](#database-design)
6. [API Architecture](#api-architecture)
7. [Scalability & Performance](#scalability--performance)

---

## System Overview

### Architecture Principles

1. **Domain Agnostic**: Works across any risk domain without domain-specific code
2. **Explainable AI**: Every decision is traceable and auditable
3. **Hybrid Intelligence**: Combines LLM reasoning with deterministic SQL
4. **Transfer Learning**: Knowledge from one domain improves others
5. **Continuous Improvement**: Learns from actual outcomes

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                          │
│  • REST API  • Python SDK  • Web Dashboard  • CLI Tools         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LLM UNDERSTANDING LAYER                         │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │ Risk Domain   │  │   Semantic    │  │   Parameter      │   │
│  │ Classifier    │  │   Feature     │  │   Generator      │   │
│  │ (Claude)      │  │   Extractor   │  │   (LLM + RAG)    │   │
│  └───────────────┘  └───────────────┘  └──────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              TRANSFER LEARNING LAYER                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Universal Risk Embedding Space (1536-dim vectors)      │   │
│  │  • Semantic similarity search (pgvector)                │   │
│  │  • Cross-domain pattern matching                        │   │
│  │  • Parameter adaptation logic                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              SQL CALCULATION ENGINE                              │
│  • calculate_generic_likelihood()                                │
│  • calculate_generic_impact()                                    │
│  • Decay functions (9 types)                                     │
│  • Aggregation methods (6 types)                                 │
│  • Fully deterministic and explainable                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              FEEDBACK & LEARNING LAYER                           │
│  • Outcome tracking                                              │
│  • Pattern accuracy updates                                      │
│  • Embedding fine-tuning                                         │
│  • Transfer success monitoring                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. LLM Understanding Layer

**Purpose**: Translate natural language risk specifications into structured parameters

**Components**:

#### A. Risk Domain Classifier
```python
Input: "Calculate employee attrition risk based on training engagement"
Output: {
  "domain": "hr",
  "entity": "employee",
  "outcome": "attrition",
  "risk_classification": "operational"
}
```

**LLM Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- Temperature: 0.0 (deterministic)
- Max tokens: 4000
- Latency: ~1-2 seconds

#### B. Semantic Feature Extractor
```python
Input: Database schema (MDL format)
Output: {
  "risk_relevant_columns": [
    {
      "column": "completion_rate",
      "semantic_meaning": "engagement_indicator",
      "relevance_score": 0.92
    }
  ]
}
```

**Technology**: 
- Embeddings: OpenAI text-embedding-3-large (1536-dim)
- Similarity: Cosine distance
- Storage: PostgreSQL with pgvector

#### C. Parameter Generator
```python
Input: Risk specification + Schema + Similar patterns
Output: {
  "likelihood_parameters": [...],
  "impact_parameters": [...],
  "decay_functions": {...}
}
```

**Mechanism**: RAG (Retrieval-Augmented Generation)
- Retrieves top 5 similar patterns
- LLM adapts parameters for new context
- Confidence scoring for reliability

---

### 2. Transfer Learning Layer

**Purpose**: Enable zero-shot and few-shot learning across domains

#### Universal Risk Embedding Space

All risk patterns are embedded in a shared 1536-dimensional space where:
- Similar risks cluster together (e.g., attrition ↔ churn)
- Distance = semantic similarity
- Enables automatic knowledge transfer

```python
# Example: Finding similar patterns
query = "Supply chain disruption risk"
query_embedding = embed(query)

# Vector similarity search
similar_patterns = db.query(
    "SELECT * FROM risk_patterns "
    "ORDER BY embedding_vector <=> %s LIMIT 5",
    query_embedding
)

# Results:
# 1. "Vendor reliability risk" (security domain) - similarity: 0.82
# 2. "Financial distress risk" (finance domain) - similarity: 0.78
# 3. "Geographic concentration risk" (ops domain) - similarity: 0.75
```

#### Parameter Adaptation Algorithm

```python
def adapt_parameters(target_analysis, similar_patterns):
    """
    Transfer parameters from similar domains
    
    Steps:
    1. Weight interpolation based on similarity scores
    2. Domain-specific adjustment factors
    3. Decay function mapping
    4. Confidence calculation
    """
    
    adapted = {}
    total_similarity = sum(p['similarity'] for p in similar_patterns)
    
    for pattern in similar_patterns:
        weight = pattern['similarity'] / total_similarity
        
        # Interpolate parameters
        for param in pattern['parameters']:
            if param['name'] in adapted:
                adapted[param['name']]['weight'] += param['weight'] * weight
            else:
                adapted[param['name']] = {
                    'weight': param['weight'] * weight,
                    'decay': param['decay'],
                    'source_domains': [pattern['domain']]
                }
    
    # LLM refinement for final adjustments
    refined = llm_refine(adapted, target_analysis)
    
    return refined
```

---

### 3. SQL Calculation Engine

**Purpose**: Deterministic, explainable risk computation

#### Architecture

```sql
-- Parameter → Normalization → Decay → Weight → Aggregation → Risk Score

-- Example Flow:
1. Raw Value: completion_rate = 65%
2. Normalized: 0.65 (to 0-1 scale)
3. Decay Applied: 0.65 * exp(-days/30) = 0.52 (if 20 days old)
4. Weighted: 0.52 * 0.35 = 0.182 (weight = 0.35)
5. Aggregated: Sum of all weighted values
6. Scaled: Final score 0-100
```

#### Key Functions

**Likelihood Calculation**:
```sql
SELECT * FROM calculate_generic_likelihood(
    ARRAY[
        build_parameter('completion_rate', 65, 0.35, 100, 'exponential', 30, 20, FALSE),
        build_parameter('overdue_ratio', 42, 0.25, 100, 'linear', 90, 42, FALSE),
        -- ... more parameters
    ],
    'weighted_sum',  -- Aggregation method
    100.0,           -- Scale to 100
    'none'           -- Normalization
);
```

**Impact Calculation**:
```sql
SELECT * FROM calculate_generic_impact(
    ARRAY[
        build_impact_parameter('tenure', 5.2, 0.30, 10, 'direct', 1.0, 'none', 1.0, 0, FALSE),
        build_impact_parameter('team_size', 8, 0.25, 20, 'cascading', 1.5, 'none', 1.0, 0, FALSE),
        -- ... more parameters
    ],
    'cascading',  -- Use cascading for compound effects
    100.0,        -- Scale
    TRUE,         -- Enable cascade
    2             -- Cascade depth
);
```

#### Decay Functions (9 Types)

| Function | Formula | Use Case |
|----------|---------|----------|
| none | value | No time effect |
| linear | value * (1 - t/τ) | Simple decrease |
| exponential | value * e^(-t/τ) | Natural decay |
| logarithmic | value * ln(1 + t/τ) | Slow growth |
| step | 0 if t < τ else value | Threshold trigger |
| compound | value * (1+r)^t | Accelerating growth |
| inverse_exp | value * (1 - e^(-t/τ)) | Saturation |
| sigmoid | value / (1+e^(-r(t-50))) | S-curve |
| square | value * (t/τ)² | Quadratic growth |

---

### 4. LangGraph Orchestration

**Purpose**: Multi-step agentic workflow for complex risk assessment

#### Workflow Graph

```python
graph = StateGraph(RiskAssessmentState)

# Nodes
graph.add_node("understand", understand_risk_node)
graph.add_node("find_patterns", find_patterns_node)
graph.add_node("transfer_learn", transfer_learn_node)
graph.add_node("generate_sql", generate_sql_node)
graph.add_node("execute_sql", execute_sql_node)
graph.add_node("explain", explain_risk_node)

# Edges (workflow)
graph.set_entry_point("understand")
graph.add_edge("understand", "find_patterns")
graph.add_edge("find_patterns", "transfer_learn")
graph.add_edge("transfer_learn", "generate_sql")
graph.add_edge("generate_sql", "execute_sql")
graph.add_edge("execute_sql", "explain")
graph.add_edge("explain", END)
```

#### State Management

```python
class RiskAssessmentState(TypedDict):
    # Input
    risk_specification: str
    entity_id: str
    
    # Intermediate
    llm_analysis: Dict
    similar_patterns: List[Dict]
    adapted_parameters: Dict
    sql_query: str
    
    # Output
    risk_score: float
    likelihood: float
    impact: float
    explanation: str
    recommendations: List[str]
    
    # Metadata
    transfer_confidence: float
    errors: List[str]
```

---

## Database Design

### Core Tables

#### 1. risk_patterns (Knowledge Base)

```sql
CREATE TABLE risk_patterns (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50),
    pattern_name VARCHAR(200),
    pattern_description TEXT,
    risk_type VARCHAR(50),
    
    -- Semantic embedding for similarity search
    embedding_vector VECTOR(1536),
    
    -- Parameter template
    parameter_template JSONB,
    
    -- Performance metrics
    prediction_accuracy DECIMAL(5,2),
    usage_count INTEGER DEFAULT 0,
    transferability_score DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON risk_patterns 
USING ivfflat (embedding_vector vector_cosine_ops);
```

**Example Data**:
```json
{
  "id": 1,
  "domain": "hr",
  "pattern_name": "employee_attrition_training_based",
  "embedding_vector": [0.023, -0.145, ...],
  "parameter_template": {
    "likelihood_parameters": [
      {
        "name": "completion_rate",
        "weight": 0.35,
        "decay_function": "exponential",
        "decay_rate": 30
      }
    ]
  },
  "prediction_accuracy": 87.3,
  "transferability_score": 0.82
}
```

#### 2. risk_parameter_mappings (Cross-Domain Mappings)

```sql
CREATE TABLE risk_parameter_mappings (
    id SERIAL PRIMARY KEY,
    source_domain VARCHAR(50),
    target_domain VARCHAR(50),
    
    source_parameter VARCHAR(200),
    target_parameter VARCHAR(200),
    
    mapping_confidence DECIMAL(5,2),
    weight_transfer_factor DECIMAL(5,3),
    
    source_embedding VECTOR(1536),
    target_embedding VECTOR(1536),
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example**: Mapping "completion_rate" (HR) → "patch_compliance" (Security)

#### 3. domain_schemas (Schema Repository)

```sql
CREATE TABLE domain_schemas (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50),
    table_name VARCHAR(200),
    schema_json JSONB,
    
    -- LLM-generated understanding
    semantic_summary TEXT,
    risk_relevant_columns JSONB,
    entity_relationships JSONB,
    
    schema_embedding VECTOR(1536),
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 4. risk_outcomes (Feedback Loop)

```sql
CREATE TABLE risk_outcomes (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(200),
    domain VARCHAR(50),
    
    -- Predictions
    predicted_risk DECIMAL(10,2),
    predicted_likelihood DECIMAL(10,2),
    predicted_impact DECIMAL(10,2),
    
    -- Actual outcome
    actual_outcome BOOLEAN,
    outcome_severity DECIMAL(10,2),
    outcome_date TIMESTAMP,
    
    -- Error analysis
    prediction_error DECIMAL(10,2),
    
    -- Context
    parameters_used JSONB,
    
    recorded_at TIMESTAMP DEFAULT NOW()
);
```

#### 5. ml_learned_parameters (ML Optimizations)

```sql
CREATE TABLE ml_learned_parameters (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50),
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

**Example Config**:
```json
{
  "domain": "hr_attrition",
  "weights": {
    "completion_rate": 0.38,
    "overdue_ratio": 0.27,
    "login_recency": 0.22,
    "manager_changes": 0.13
  },
  "decay_config": {
    "login_recency": {
      "function": "exponential",
      "rate": 27.3
    }
  },
  "version": "1.0",
  "trained_date": "2026-01-05T10:30:00Z"
}
```

---

## Data Flow

### End-to-End Request Flow

```
1. User Request
   │
   POST /assess-risk
   {
     "specification": "Calculate attrition risk...",
     "entity_id": "USR123",
     "domain": "hr"
   }
   │
   ▼
2. LLM Analysis (2s)
   │
   • Parse specification
   • Identify domain & entity
   • Extract risk dimensions
   │
   ▼
3. Schema Loading (<100ms)
   │
   • Load domain schema
   • Identify data sources
   • Map to tables/columns
   │
   ▼
4. Semantic Search (200ms)
   │
   • Generate embedding
   • Vector similarity search
   • Retrieve top 5 similar patterns
   │
   ▼
5. Transfer Learning (1.5s)
   │
   • Adapt parameters from similar patterns
   • LLM refinement
   • Confidence calculation
   │
   ▼
6. SQL Generation (500ms)
   │
   • Build likelihood parameters
   • Build impact parameters
   • Generate complete SQL query
   │
   ▼
7. SQL Execution (<100ms)
   │
   • Execute calculate_generic_likelihood()
   • Execute calculate_generic_impact()
   • Combine scores
   │
   ▼
8. Explanation Generation (1s)
   │
   • LLM generates human-readable explanation
   • Extract recommendations
   • Format output
   │
   ▼
9. Response (Total: 4-6s)
   {
     "risk_score": 68.4,
     "explanation": "...",
     "recommendations": [...]
   }
```

---

## Transfer Learning Mechanism

### How Knowledge Transfers Across Domains

#### Example: HR Attrition → Customer Churn

**Step 1: Semantic Similarity**
```python
# HR attrition pattern
hr_pattern = {
  "engagement_decline": 0.35,
  "activity_recency": 0.25,
  "relationship_quality": 0.20
}

# Customer churn request
churn_query = "predict customer churn using support and usage data"

# Similarity: 0.84 (high!)
```

**Step 2: Parameter Mapping**
```python
# Automatic mapping
engagement_decline (HR) → usage_decline (Customer)
activity_recency (HR) → login_recency (Customer)  
relationship_quality (HR) → support_satisfaction (Customer)
```

**Step 3: Weight Adaptation**
```python
# Transfer with adjustment
hr_weight = 0.35
domain_similarity = 0.84
confidence_factor = 0.9

churn_weight = hr_weight * domain_similarity * confidence_factor
             = 0.35 * 0.84 * 0.9
             = 0.26
```

**Step 4: Decay Function Transfer**
```python
# If HR uses exponential decay with τ=30 days
# Customer might need different rate

hr_decay_rate = 30  # days
customer_churn_cycle = 90  # longer cycle
adjustment = customer_churn_cycle / hr_decay_rate

customer_decay_rate = 30 * 3 = 90 days
```

### Transfer Confidence Scoring

```python
def calculate_transfer_confidence(
    source_pattern, 
    target_analysis,
    similarity_score
):
    """
    Confidence = f(similarity, accuracy, transferability)
    """
    
    base_confidence = similarity_score
    
    # Adjust for source accuracy
    accuracy_factor = source_pattern['prediction_accuracy'] / 100
    
    # Adjust for known transferability
    transfer_factor = source_pattern['transferability_score']
    
    # Domain compatibility
    domain_distance = get_domain_distance(
        source_pattern['domain'],
        target_analysis['domain']
    )
    
    final_confidence = (
        base_confidence * 0.4 +
        accuracy_factor * 0.3 +
        transfer_factor * 0.2 +
        (1 - domain_distance) * 0.1
    )
    
    return min(final_confidence, 0.95)  # Cap at 95%
```

---

## API Architecture

### FastAPI Application

```python
# Layered architecture
app/
├── api/
│   ├── routes/
│   │   ├── risk_assessment.py
│   │   ├── patterns.py
│   │   └── feedback.py
│   └── dependencies.py
├── core/
│   ├── llm_engine.py
│   ├── transfer_learning.py
│   └── sql_generator.py
├── models/
│   ├── requests.py
│   ├── responses.py
│   └── internal.py
└── services/
    ├── risk_service.py
    ├── pattern_service.py
    └── feedback_service.py
```

### API Endpoints

```python
# Main risk assessment
POST /api/v1/assess-risk
POST /api/v1/assess-risk/batch

# Pattern management
GET /api/v1/patterns
GET /api/v1/patterns/{id}
POST /api/v1/patterns/search

# Feedback
POST /api/v1/feedback/outcome
GET /api/v1/feedback/accuracy

# Admin
GET /api/v1/admin/transfer-stats
POST /api/v1/admin/retrain-embeddings
```

---

## Scalability & Performance

### Performance Characteristics

| Component | Latency | Throughput | Bottleneck |
|-----------|---------|------------|------------|
| LLM Analysis | 1-2s | 10 req/s | API rate limit |
| Embedding | 200ms | 50 req/s | API call |
| Vector Search | 50-100ms | 1000 req/s | Index size |
| SQL Execution | <100ms | 5000 req/s | DB capacity |
| Total E2E | 2-5s | 10 req/s | LLM calls |

### Scaling Strategies

#### 1. LLM Call Optimization
```python
# Cache frequent analysis results
@cache(ttl=3600)
def analyze_specification(spec: str) -> Dict:
    return llm.analyze(spec)

# Batch embedding requests
embeddings = embed_batch([text1, text2, text3, ...])
```

#### 2. Database Optimization
```sql
-- Partition by domain
CREATE TABLE risk_patterns_hr PARTITION OF risk_patterns
FOR VALUES IN ('hr');

-- Optimize vector index
CREATE INDEX CONCURRENTLY ON risk_patterns 
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);
```

#### 3. Horizontal Scaling
```yaml
# docker-compose.yml
services:
  api:
    image: risk-platform:latest
    replicas: 5
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

#### 4. Caching Layer
```python
# Redis for hot patterns
redis_client.setex(
    f"pattern:{pattern_id}",
    3600,  # 1 hour TTL
    json.dumps(pattern)
)
```

### Monitoring & Observability

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

risk_assessments_total = Counter(
    'risk_assessments_total',
    'Total risk assessments',
    ['domain', 'status']
)

assessment_duration = Histogram(
    'assessment_duration_seconds',
    'Time to complete assessment',
    ['domain']
)

transfer_confidence = Histogram(
    'transfer_confidence_score',
    'Transfer learning confidence',
    ['source_domain', 'target_domain']
)
```

---

## Security Considerations

### Data Privacy
- PII data stays in source databases
- Only metadata and aggregates in risk_patterns
- Row-level security for multi-tenant deployments

### API Security
```python
# JWT authentication
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.post("/assess-risk")
async def assess_risk(
    request: RiskRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    verify_jwt(credentials.credentials)
    # ...
```

### Audit Logging
```sql
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(200),
    action VARCHAR(100),
    entity_id VARCHAR(200),
    parameters JSONB,
    result JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

---

## Deployment Architecture

### Production Deployment

```
                    ┌──────────────────┐
                    │   Load Balancer  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ┌────────┐     ┌────────┐     ┌────────┐
         │ API 1  │     │ API 2  │     │ API 3  │
         └───┬────┘     └───┬────┘     └───┬────┘
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │  (Primary)   │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │              │
               ┌────▼────┐    ┌───▼─────┐
               │Replica 1│    │Replica 2│
               └─────────┘    └─────────┘
```

### Container Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "python.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Future Enhancements

1. **Real-time Streaming**: WebSocket support for live risk updates
2. **Multi-modal**: Support for document/image analysis
3. **Fine-tuning**: Custom embeddings per organization
4. **Federated Learning**: Learn across organizations without sharing data
5. **Explainable AI**: SHAP values for ML components

---

**Version**: 1.0  
**Last Updated**: 2026-01-05  
**Maintained By**: Risk Platform Team
