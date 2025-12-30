# Deep Research Feature Engineering Architecture

## Overview

The Deep Research Feature Engineering system is a multi-agent architecture built on LangGraph that implements a **compliance-first approach** to feature engineering. It uses deep research techniques to identify compliance controls, generate detailed natural language questions, and create executable feature specifications in a **Medallion Architecture** (Bronze/Silver/Gold).

### Key Principles

1. **Compliance-First Approach**: The workflow starts by identifying compliance frameworks and controls before generating features
2. **Deep Research**: Uses knowledge retrieval, historical patterns, and domain expertise to inform feature generation
3. **Natural Language Questions**: Generates detailed, step-by-step natural language questions that can be executed by transformation agents
4. **Medallion Architecture**: Classifies features into SILVER (basic transformations) or GOLD (complex aggregations)
5. **Domain-Agnostic**: Works across multiple compliance frameworks (SOC2, HIPAA, GDPR, PCI-DSS, etc.)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Query                                    │
│              "Create SOC2 compliance report..."                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 1: Query Understanding                         │
│  • Parse user query                                             │
│  • Identify compliance frameworks                               │
│  • Retrieve knowledge documents                                 │
│  • Analyze historical examples                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 2: Control Identification                          │
│  • Identify relevant compliance controls                        │
│  • Fetch knowledge for each control                             │
│  • Identify key measures/metrics                                │
│  • Map controls to available data                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 3: Schema Analysis                             │
│  • Map requirements to schemas                                  │
│  • Identify relevant tables/fields                              │
│  • Build schema registry                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 4: Feature Recommendation                          │
│  • Generate natural language questions                          │
│  • Classify as SILVER or GOLD                                   │
│  • Define calculation logic                                     │
│  • Map to compliance controls                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 5: Feature Dependency Analysis                    │
│  • Identify feature dependencies                                │
│  • Create calculation sequence                                  │
│  • Build dependency chains                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 6: Relevancy Scoring                               │
│  • Score features against goals                                 │
│  • Compare with examples                                        │
│  • Provide quality feedback                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 7: Deep Research Review                            │
│  • Review control coverage                                      │
│  • Validate natural language questions                          │
│  • Check medallion classification                               │
│  • Provide improvement recommendations                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                    Feature Specifications
```

---

## Workflow Steps

### 1. Query Understanding (`QueryUnderstandingAgent`)

**Purpose**: Identify the most important compliance frameworks and controls based on the user's query.

**Process**:
- Parses user query to extract analytical intent
- Retrieves knowledge documents (compliance frameworks, best practices)
- Analyzes historical examples and patterns
- Identifies domain-specific compliance requirements

**Output**:
- `analytical_intent`: Structured representation of user's goal
- `compliance_framework`: Identified framework (e.g., SOC2, GDPR)
- `knowledge_documents`: Retrieved knowledge documents

**Example**:
```python
analytical_intent = {
    "primary_goal": "Create SOC2 compliance report for vulnerabilities",
    "compliance_framework": "SOC2",
    "severity_levels": ["Critical", "High"],
    "time_constraints": {"sla_days": 7, "urgency": "high"}
}
```

---

### 2. Control Identification (`ControlIdentificationAgent`)

**Purpose**: Identify relevant compliance controls and fetch knowledge for each control.

**Process**:
- Identifies compliance controls based on analytical intent
- For each control, fetches specific knowledge documents
- Identifies key measures/metrics needed for each control
- Maps controls to available data model

**Output**:
- `identified_controls`: List of controls with metadata
- `control_universe`: Control universe structure
- `knowledge_documents`: Control-specific knowledge

**Example Control**:
```python
{
    "control_id": "CC6.1",
    "control_name": "Logical Access Controls",
    "description": "The entity implements logical access security software...",
    "key_measures": [
        "Access control effectiveness metrics",
        "Failed login attempt rates",
        "Privileged access usage"
    ],
    "confidence": "high"
}
```

---

### 3. Schema Analysis (`SchemaAnalysisAgent`)

**Purpose**: Map requirements to available data schemas.

**Process**:
- Retrieves database schemas using retrieval helper
- Maps analytical intent to relevant schemas
- Builds schema registry with descriptions and key fields
- Identifies relationships between schemas

**Output**:
- `relevant_schemas`: List of relevant schema names
- `schema_registry`: Detailed schema information

---

### 4. Feature Recommendation (`FeatureRecommendationAgent`)

**Purpose**: Generate detailed natural language questions for each compliance control.

**Key Features**:
- **Natural Language Questions**: Detailed, step-by-step instructions
- **Medallion Classification**: SILVER or GOLD
- **Calculation Logic**: SQL-like pseudocode
- **Compliance Mapping**: Links features to specific controls

**Medallion Architecture Classification**:

- **SILVER**: Transformations from raw data (bronze)
  - Data cleaning, normalization, deduplication
  - Type conversions, basic calculations
  - Example: "Create a calculated column for vulnerability_age based on publish_time and current_date"

- **GOLD**: Requires other transformations or aggregations
  - Complex calculations, multi-step transformations
  - Aggregations across tables, derived metrics
  - Example: "Calculate raw_risk score for each asset by first calculating raw_impact, then calculating raw_likelihood from breach method likelihoods and asset exposure, then combining them with appropriate weighting"

**Example Feature**:
```python
{
    "feature_name": "critical_sla_breached_count",
    "natural_language_question": "Count the number of critical vulnerabilities that have exceeded their SLA of 7 days since creation and are still open",
    "feature_type": "count",
    "transformation_layer": "gold",
    "calculation_logic": "COUNT(*) WHERE severity='Critical' AND days_since_creation > 7 AND status='open'",
    "soc2_compliance_reasoning": "Supports CC7.2 (System Operations) by monitoring SLA compliance for critical vulnerabilities",
    "required_schemas": ["vulnerabilities", "assets"],
    "time_series_type": "snapshot"
}
```

---

### 5. Feature Dependency Analysis (`FeatureDependencyAgent`)

**Purpose**: Identify feature dependencies and calculation order.

**Process**:
- Analyzes all recommended features
- Identifies which features depend on others
- Creates natural language chains of operations
- Determines optimal calculation sequence

**Output**:
- `feature_dependencies`: Dependency graph
- `calculation_sequence`: Groups of features that can be calculated in parallel
- `dependency_chains`: Sequential chains of calculations

**Example**:
```python
{
    "features": [
        {
            "feature_name": "raw_risk",
            "depends_on": ["raw_impact", "raw_likelihood"],
            "calculation_order": 3,
            "is_base_feature": False
        }
    ],
    "calculation_sequence": [
        ["raw_impact", "raw_likelihood"],  # Can be calculated in parallel
        ["raw_risk"]  # Must wait for above
    ]
}
```

---

### 6. Relevancy Scoring (`RelevancyScoringAgent`)

**Purpose**: Score features against goals and examples using GRPO methodology.

**Dimensions Evaluated**:
- **Relevance**: How relevant to user's goal
- **Completeness**: How complete the feature definition
- **Feasibility**: How feasible given available data
- **Clarity**: How clear and actionable
- **Technical Accuracy**: How technically accurate

**Output**:
- `overall_score`: Overall relevance score (0.0-1.0)
- `feature_scores`: Individual feature scores
- `goal_alignment`: How well features align with goals
- `improvement_suggestions`: Actionable feedback

---

### 7. Deep Research Review (`DeepResearchReviewAgent`)

**Purpose**: Review all recommendations and ensure quality and completeness.

**Review Criteria**:
1. **Control Coverage**: Every identified control should have at least 1 feature
2. **Natural Language Questions**: Must be detailed, step-by-step, executable
3. **Medallion Architecture**: Correct SILVER vs GOLD classification
4. **Goal Alignment**: Features should support risk estimation, monitoring, and reporting
5. **Quality**: Identify low-quality features that need improvement

**Output**:
- `review_summary`: Overall assessment
- `coverage_gaps`: Missing controls
- `quality_issues`: Low-quality features
- `improvement_recommendations`: Specific recommendations

---

## State Management

The workflow uses a shared state (`FeatureEngineeringState`) that flows through all agents:

```python
class FeatureEngineeringState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    analytical_intent: Dict[str, Any]
    relevant_schemas: List[str]
    recommended_features: List[Dict[str, Any]]
    identified_controls: List[Dict[str, Any]]
    knowledge_documents: List[Dict[str, Any]]
    feature_dependencies: Dict[str, Any]
    relevance_scores: Dict[str, Any]
    deep_research_review: Dict[str, Any]
    metrics: Dict[str, Any]  # Token usage and response times
    next_agent: str  # Routing control
```

---

## Resume Capability

The workflow supports **resuming from any point** by:

1. **Skip Logic**: Initial nodes check if they should be skipped when resuming
2. **Flexible Routing**: All nodes can route to any destination
3. **State Preservation**: Full state is returned for follow-up scenarios

**Example - Follow-up Feature Generation**:
```python
# Initial run
result = await pipeline.run(
    user_query="Create SOC2 compliance report...",
    project_id="cve_data"
)

# Follow-up: Add more features
follow_up_state = result["_full_state"]
follow_up_state["next_agent"] = "feature_recommendation"
follow_up_state["feature_generation_instructions"] = "Generate 5 additional features..."

result_followup = await pipeline.run(initial_state=follow_up_state)
```

---

## Usage Examples

### Basic Usage

```python
from app.agents.nodes.transform.feature_engineering_agent import (
    FeatureEngineeringPipeline,
    get_domain_config
)

# Initialize pipeline
pipeline = FeatureEngineeringPipeline(
    llm=llm,
    retrieval_helper=retrieval_helper,
    domain_config=get_domain_config("cybersecurity")
)

# Run pipeline
result = await pipeline.run(
    user_query="""
    Create a report for Snyk that looks at Critical and High vulnerabilities 
    for SOC2 compliance. Critical = 7 Days, High = 30 days SLA.
    """,
    project_id="cve_data"
)

# Access results
features = result["recommended_features"]
controls = result["identified_controls"]
scores = result["relevance_scores"]
```

### With Follow-up

```python
# Initial run
result = await pipeline.run(
    user_query="Create SOC2 compliance report...",
    project_id="cve_data"
)

# Follow-up: Add more features
follow_up_state = result["_full_state"]
follow_up_state["next_agent"] = "feature_recommendation"
follow_up_state["feature_generation_instructions"] = (
    "Generate 5 additional features focusing on risk quantification metrics."
)

result_followup = await pipeline.run(initial_state=follow_up_state)
```

### Generating Impact/Likelihood/Risk Features (STEP 3)

```python
from app.agents.nodes.transform.feature_engineering_agent import (
    generate_impact_features,
    generate_likelihood_features,
    generate_risk_features
)

# Step 1: Generate regular compliance features
result = await pipeline.run(
    user_query="Create SOC2 compliance report...",
    project_id="cve_data"
)

# Step 2: Generate impact features
impact_result = await generate_impact_features(
    initial_state=result["_full_state"],
    retrieval_helper=retrieval_helper,
    domain_config=get_domain_config("cybersecurity")
)

# Step 3: Generate likelihood features
likelihood_result = await generate_likelihood_features(
    initial_state=impact_result["_full_state"],
    retrieval_helper=retrieval_helper,
    domain_config=get_domain_config("cybersecurity")
)

# Step 4: Generate risk features
risk_result = await generate_risk_features(
    initial_state=likelihood_result["_full_state"],
    retrieval_helper=retrieval_helper,
    domain_config=get_domain_config("cybersecurity")
)
```

---

## Domain Configuration

The system is domain-agnostic and uses `DomainConfiguration` to customize behavior:

```python
from app.agents.nodes.transform.domain_config import (
    DomainConfiguration,
    CYBERSECURITY_DOMAIN_CONFIG,
    HR_COMPLIANCE_DOMAIN_CONFIG
)

# Use predefined configs
pipeline = FeatureEngineeringPipeline(
    llm=llm,
    domain_config=CYBERSECURITY_DOMAIN_CONFIG
)

# Or create custom config
custom_config = DomainConfiguration(
    domain_name="Finance",
    compliance_frameworks=["SOX", "PCI-DSS"],
    entity_types=["transaction", "account", "payment"],
    severity_levels=["Critical", "High", "Medium", "Low"]
)
```

---

## Metrics Tracking

The workflow automatically tracks performance metrics:

```python
metrics = result["metrics"]
print(f"Total Steps: {metrics['step_count']}")
print(f"Total Tokens: {metrics['total_tokens']}")
print(f"Total Time: {metrics['total_response_time']:.3f}s")

# Per-step metrics
for step in metrics["steps"]:
    print(f"{step['step_name']}: {step['response_time_seconds']:.3f}s, {step['total_tokens']} tokens")
```

---

## Natural Language Question Format

The system generates detailed, executable natural language questions:

**Good Example**:
```
"Calculate raw_risk score for each asset by first calculating raw_impact using 
asset criticality and data classification, then calculating raw_likelihood from 
breach method likelihoods and asset exposure metrics, then combining them with 
appropriate weighting factors"
```

**Bad Example** (too simple):
```
"Calculate raw_risk"
```

**Characteristics of Good Questions**:
1. **Detailed**: Step-by-step instructions
2. **Entity-Specific**: "for each asset", "for each vulnerability"
3. **Calculation Steps**: "first calculate X, then calculate Y, then combine"
4. **Field References**: Mentions specific fields/data sources
5. **Executable**: Can be interpreted by a transformation agent

---

## Medallion Architecture Integration

Features are classified into transformation layers:

### SILVER Layer
- **Purpose**: Transformations from raw data (bronze)
- **Characteristics**:
  - Basic calculations from raw fields
  - Data cleaning and normalization
  - Type conversions
  - Simple aggregations
- **Example**: "Create a calculated column for vulnerability_age based on publish_time and current_date"

### GOLD Layer
- **Purpose**: Business aggregations and complex metrics
- **Characteristics**:
  - Requires other transformations
  - Complex multi-step calculations
  - Aggregations across tables
  - Derived metrics and risk scores
- **Example**: "Calculate raw_risk score for each asset by first calculating raw_impact, then calculating raw_likelihood, then combining them"

---

## Error Handling & Resilience

The workflow includes several resilience features:

1. **Skip Logic**: Nodes skip execution when resuming to later steps
2. **Fallback Parsing**: Multiple strategies for parsing LLM responses
3. **Validation**: Validates and fixes data structures
4. **Error Tracking**: Errors are tracked in metrics
5. **Graceful Degradation**: Continues even if some steps fail

---

## Best Practices

1. **Query Clarity**: Provide clear, specific queries with compliance framework mentions
2. **Domain Configuration**: Use appropriate domain config for your use case
3. **Follow-ups**: Use follow-up feature generation to refine and expand features
4. **Review Output**: Always review the deep research review for quality issues
5. **Metrics Monitoring**: Monitor token usage and response times for optimization

---

## Architecture Benefits

1. **Compliance-First**: Ensures features directly support compliance monitoring
2. **Deep Research**: Uses knowledge retrieval and domain expertise
3. **Executable Output**: Natural language questions can be executed by transformation agents
4. **Domain-Agnostic**: Works across multiple compliance frameworks
5. **Resumable**: Can resume from any point for follow-up scenarios
6. **Quality Assurance**: Built-in relevancy scoring and deep research review

---

## Future Enhancements

- Integration with STEP 3 (Deep Research & Risk Modeling) for comprehensive risk models
- Support for more compliance frameworks
- Enhanced natural language question generation
- Better integration with transformation agents
- Real-time feature validation

---

## Related Documentation

- [Main README](./README.md) - Three-phase compliance system overview
- [Domain Configuration](./domain_config.py) - Domain configuration details
- [Risk Model Agents](../risk_model_agents.py) - STEP 3 Deep Research workflow

---

## License

[Your License Here]

