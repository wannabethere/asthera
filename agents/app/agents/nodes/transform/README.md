# Compliance Feature Engineering & Risk Modeling System

## Overview

This system provides a multi-agent framework for compliance feature engineering, control universe definition, and risk modeling. It uses LangGraph to orchestrate specialized agents that work together in a **sequential three-phase approach**:

### The Three-Phase Process

1. **STEP 1: Document Analysis** - Analyze compliance documents to build a structured control universe
   - Extracts controls, sub-controls, and measurable expectations from documents
   - Maps evidence types to controls
   - Performs initial risk assessment
   - **Output**: Control Universe (controls, expectations, evidence)

2. **STEP 2: Feature Engineering** - Generate compliance features from user queries
   - Uses Control Universe from STEP 1 to inform feature recommendations
   - Analyzes user queries and available data schemas
   - Generates compliance monitoring features
   - **Output**: Recommended Features (compliance features, calculation logic, schemas)

3. **STEP 3: Deep Research & Risk Modeling** - Build comprehensive risk models
   - Performs deep research using **features from STEP 2** and **domain analysis**
   - Builds likelihood models using universal likelihood drivers
   - Builds impact models using universal impact dimensions
   - Identifies contextual factors that modify risk
   - **Output**: Complete Risk Model Blueprint (signals, likelihood, impact, risk calculations)

The system is domain-agnostic and works across multiple compliance frameworks (SOC2, HIPAA, GDPR, PCI-DSS, etc.).

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Query / Documents                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   Domain Configuration & Knowledge     │
        │   - Domain-specific terminology         │
        │   - Compliance frameworks               │
        │   - Feature patterns                    │
        │   - Control sets                        │
        │   - Metric libraries                    │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   STEP 1: Document Analysis Workflow   │
        │                                         │
        │  - Domain Context Reasoning            │
        │  - Control Identification              │
        │  - Measurable Expectations            │
        │  - Evidence Mapping                    │
        │  - Risk Assessment                     │
        │                                         │
        │  Output: Control Universe              │
        │  (Controls, Sub-Controls, Evidence)     │
        └───────────────────┬─────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   STEP 2: Feature Engineering Workflow │
        │                                         │
        │  - Query Understanding                 │
        │  - Control Identification (from data) │
        │  - Knowledge Retrieval                 │
        │  - Schema Analysis                     │
        │  - Feature Recommendation               │
        │  - Feature Calculation Planning        │
        │                                         │
        │  Output: Recommended Features          │
        │  (Compliance features, schemas, logic) │
        └───────────────────┬─────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   STEP 3: Deep Research & Risk Modeling │
        │                                         │
        │  Uses: Features + Domain Analysis      │
        │                                         │
        │  - Measurable Signals                  │
        │  - Likelihood Model Inputs             │
        │  - Impact Model Inputs                  │
        │  - Contextual Factors                   │
        │  - Risk Model Integration               │
        │                                         │
        │  Output: Complete Risk Model Blueprint │
        │  (Signals, Likelihood, Impact, Risk)    │
        └───────────────────────────────────────┘
```

---

## Workflow Flows

The system follows a **sequential three-phase approach**:

1. **Document Analysis** - Analyze compliance documents to build control universe
2. **Feature Engineering** - Generate compliance features from user queries
3. **Deep Research & Risk Modeling** - Build comprehensive risk models using features and domain analysis

---

### 1. Document Analysis Workflow (STEP 1)

**Purpose**: Analyze compliance documents and build a structured control universe with measurable expectations. This is the **first step** in the overall process.

**Entry Point**: `ControlUniverseReasoningWorkflow.run()`

**When to Use**: Run this workflow first when you have compliance documents to analyze. The output (Control Universe) feeds into subsequent workflows.

**Flow**:

```
Domain Context Reasoning
        │
        ▼
Control Identification Reasoning
        │
        ▼
Measurable Expectations Reasoning
        │
        ▼
Evidence Mapping Reasoning
        │
        ▼
Risk Assessment Reasoning
        │
        ▼
Control Universe Integration
        │
        ▼
      END
```

**Key Agents**:

1. **DomainContextReasoningAgent**: Extracts domain context from documents
   - Identifies business processes
   - Categorizes data types
   - Lists system components
   - Determines applicable frameworks

2. **ControlIdentificationReasoningAgent**: Identifies controls from documents
   - Extracts control IDs and names
   - Maps to compliance frameworks
   - Categorizes controls
   - Links to source documents

3. **MeasurableExpectationsReasoningAgent**: Creates measurable expectations
   - Converts requirements into measurable statements
   - Defines success/failure criteria
   - Specifies measurement methods
   - Links to sub-controls

4. **EvidenceMappingReasoningAgent**: Maps evidence types to controls
   - Identifies what evidence demonstrates compliance
   - Specifies collection methods
   - Defines sufficiency criteria
   - Links evidence to sub-controls

5. **RiskAssessmentReasoningAgent**: Assesses risk for controls
   - Assigns likelihood and impact levels
   - Calculates risk scores using risk matrix
   - Classifies risk levels
   - Provides risk reasoning

6. **ControlUniverseIntegrationAgent**: Integrates all components
   - Creates complete control universe blueprint
   - Validates consistency
   - Generates summary

**State Structure**: `ControlUniverseReasoningState`
- Contains: source_documents, compliance_framework, identified_controls, proposed_measurable_expectations, control_universe_blueprint, etc.

**Output**: `ComplianceControlUniverse` object containing:
- Controls and sub-controls
- Measurable expectations
- Evidence types
- Control mappings
- Domain context
- Risk assessments

**Usage Example**:
```python
from app.agents.nodes.transform.document_analysis_agents import (
    create_control_universe_workflow
)

workflow = create_control_universe_workflow(anthropic_api_key)

result = workflow.run(
    source_documents=[
        {"content": "HIPAA Security Rule document...", "metadata": {...}}
    ],
    compliance_framework="HIPAA"
)

blueprint = extract_blueprint(result)
control_universe = blueprint.get("control_universe_blueprint")
```

---

### 2. Feature Engineering Workflow (STEP 2)

**Purpose**: Generate feature engineering plans from natural language queries for compliance analytics. This workflow uses the **Control Universe** from Document Analysis (STEP 1) to inform feature recommendations.

**Entry Point**: `FeatureEngineeringPipeline.run()` or `run_feature_engineering_pipeline()`

**Prerequisites**: Ideally, run Document Analysis Workflow first to get Control Universe. However, this workflow can also identify controls from the data model directly.

**Flow**:

```
Query Understanding
    │
    ├─→ [SOC2 detected?] → Control Identification
    │                          │
    └─→ Knowledge Retrieval ←──┘
            │
            ▼
    Schema Analysis
            │
            ▼
    Question Generation
            │
            ▼
    Feature Recommendation
            │
            ├─→ Feature Calculation Planning
            │
            ├─→ Reasoning Plan Creation
            │
            └─→ Feature Dependency Analysis
                    │
                    ▼
            Relevancy Scoring
                    │
                    ▼
                  END
```

**Note**: Impact, Likelihood, and Risk features are generated in STEP 3 (Deep Research & Risk Modeling), not in this workflow. This workflow focuses on generating compliance features based on the control universe and user queries.

**Key Agents**:

1. **QueryUnderstandingAgent**: Parses user query and extracts analytical intent
   - Identifies compliance framework
   - Extracts severity levels, time constraints
   - Determines aggregation levels

2. **ControlIdentificationAgent**: Identifies relevant SOC2 controls from data model
   - Only runs for SOC2 framework
   - Maps available schemas to control requirements
   - Returns identified controls with confidence levels
   - Can use Control Universe from STEP 1 if available

3. **KnowledgeRefiningAgent**: Retrieves and refines knowledge documents
   - Uses RetrievalHelper to fetch relevant compliance knowledge
   - Filters by framework and category
   - Provides context for feature generation

4. **SchemaAnalysisAgent**: Maps requirements to available data schemas
   - Retrieves database schemas using RetrievalHelper
   - Identifies relevant tables and fields
   - Builds schema registry

5. **QuestionGenerationAgent**: Generates clarifying questions
   - Identifies ambiguities in requirements
   - Creates domain-specific questions
   - Provides default assumptions

6. **FeatureRecommendationAgent**: Recommends specific features to calculate
   - Uses domain configuration and feature patterns
   - Maps features to identified controls (from STEP 1 or data model)
   - Generates natural language questions for each feature
   - Focuses on compliance monitoring features

7. **FeatureCalculationPlanAgent**: Creates knowledge-based calculation plans
   - Determines required data fields (inferred from knowledge)
   - Provides step-by-step calculation logic
   - Identifies transformations and aggregations

8. **ReasoningPlanAgent**: Creates step-by-step analytical reasoning plan
   - Defines data extraction steps
   - Specifies feature calculation order
   - Includes quality checks

9. **FeatureDependencyAgent**: Analyzes feature dependencies
   - Identifies which features depend on others
   - Creates calculation sequence
   - Builds dependency chains

10. **RelevancyScoringAgent**: Scores feature relevance
    - Evaluates against user goals
    - Compares to examples/expectations
    - Provides feedback and improvements

**State Structure**: `FeatureEngineeringState`
- Contains: user_query, analytical_intent, recommended_features, identified_controls, knowledge_documents, schema_registry, etc.

**Usage Example**:
```python
from app.agents.nodes.transform.feature_engineering_agent import (
    FeatureEngineeringPipeline,
    HR_COMPLIANCE_DOMAIN_CONFIG
)

pipeline = FeatureEngineeringPipeline(
    llm=llm,
    retrieval_helper=retrieval_helper,
    domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
)

result = await pipeline.run(
    user_query="Track training completion rates for GDPR compliance",
    project_id="cornerstone_learning"
)

# Access results
features = result["recommended_features"]
# Note: Impact, Likelihood, and Risk features are generated in STEP 3
```

---

### 3. Deep Research & Risk Modeling Workflow (STEP 3)

**Purpose**: Perform deep research using **features from Feature Engineering** and **domain analysis** to build comprehensive risk models with measurable signals, likelihood inputs, impact inputs, and contextual factors. This is the final phase that synthesizes all previous work.

**Entry Point**: `RiskModelReasoningWorkflow.run()`

**Prerequisites**: 
- Control Universe from Document Analysis (STEP 1)
- Recommended Features from Feature Engineering (STEP 2)
- Domain context and analysis

**Key Difference**: This workflow performs **deep research** that combines:
- Generated features from STEP 2
- Domain-specific analysis
- Control universe from STEP 1
- Historical patterns and benchmarks

To build comprehensive likelihood, impact, and risk models.

**Flow**:

```
Measurable Signals Reasoning
        │
        ▼
Likelihood Model Reasoning
        │
        ▼
Impact Model Reasoning
        │
        ▼
Contextual Factors Reasoning
        │
        ▼
Risk Model Integration
        │
        ▼
      END
```

**Key Agents**:

1. **MeasurableSignalsReasoningAgent**: Identifies measurable signals
   - Uses universal signal categories (timeliness, completeness, adherence, drift, etc.)
   - Defines signal types (continuous, binary, categorical, count, percentage, score)
   - Specifies measurement formulas
   - Links signals to controls

2. **LikelihoodModelReasoningAgent**: Defines likelihood model inputs
   - Uses universal likelihood drivers (historical failure, control drift, evidence quality, etc.)
   - Specifies calculation methods
   - Defines likelihood ranges
   - Explains predictive power

3. **ImpactModelReasoningAgent**: Defines impact model inputs
   - Uses universal impact dimensions (regulatory severity, financial, operational, etc.)
   - Specifies calculation methods
   - Defines impact ranges
   - Explains impact quantification

4. **ContextualFactorsReasoningAgent**: Identifies contextual factors
   - Temporal factors (time since review, seasonal patterns)
   - Organizational factors (control owner capability, team size)
   - Data sensitivity factors (classification level, crown jewel relevance)
   - Population factors (size, criticality)
   - Defines adjustment formulas

5. **RiskModelIntegrationAgent**: Integrates all components
   - Creates complete risk model blueprint
   - Defines model architecture
   - Specifies how likelihood and impact combine
   - Maps signals to risk

**State Structure**: `RiskModelReasoningState`
- Contains: controls, compliance_framework, proposed_signals, proposed_likelihood_inputs, proposed_impact_inputs, risk_model_blueprint, etc.

**Output**: `RiskModelBlueprint` object containing:
- Signal library with measurable signals
- Likelihood model inputs
- Impact model inputs
- Contextual factors
- Model design reasoning

**Usage Example**:
```python
from app.agents.nodes.transform.risk_model_agents import (
    create_risk_model_workflow
)

workflow = create_risk_model_workflow(anthropic_api_key)

result = workflow.run(
    controls=[...],  # From control universe
    compliance_framework="SOC2",
    domain_context={...}
)

blueprint = extract_risk_model_blueprint(result)
```

---

## Data Structures

### Domain Configuration (`domain_config.py`)

**Purpose**: Provides domain-specific configurations for feature engineering agents.

**Key Components**:
- `DomainConfiguration`: Domain-specific settings (entity types, severity levels, compliance frameworks, feature patterns)
- `ComplianceMetricLibrary`: Library of natural language questions mapped to compliance metrics
- `ComplianceControlSet`: Predefined controls for cybersecurity and HR domains

**Usage**:
```python
from app.agents.nodes.transform.domain_config import (
    get_domain_config,
    get_compliance_metric_library,
    get_compliance_control_set
)

# Get domain configuration
config = get_domain_config("hr_compliance")

# Get metrics library
metrics = get_compliance_metric_library("hr_compliance")

# Get control set
controls = get_compliance_control_set("cybersecurity")
```

### Control Universe Model (`control_universe_model.py`)

**Purpose**: Defines data structures for compliance control universe.

**Key Components**:
- `Control`: High-level compliance control (e.g., SOC2 CC2.1)
- `SubControl`: Specific measurable requirement under a control
- `EvidenceType`: Type of evidence that demonstrates control compliance
- `MeasurableExpectation`: Measurable expectation derived from compliance requirements
- `ComplianceControlUniverse`: Complete universe of compliance controls
- `RiskMatrixMapping`: Risk matrix calculations (5x5 and 3x3)

### Risk Model Structures (`risk_model_structures.py`)

**Purpose**: Defines data structures for risk modeling.

**Key Components**:
- `MeasurableSignal`: Definition of a measurable signal for compliance health
- `SignalLibrary`: Feature definition library of all measurable signals
- `LikelihoodInput`: Input feature for likelihood model
- `ImpactInput`: Input feature for impact model
- `ContextualFactor`: Cross-domain modifier for risk assessment
- `RiskModelBlueprint`: Complete blueprint for risk modeling

### Knowledge and Context (`knowledge_and_context.py`)

**Purpose**: Provides knowledge base structures for agents.

**Key Components**:
- `DataModelKnowledgeBase`: Knowledge about data models
- `ComplianceRulesKnowledgeBase`: Knowledge about compliance rules
- `HistoricalExample`: Historical examples of compliance analysis
- `ExamplesLibrary`: Library of historical examples
- `AgentInstructions`: Instructions and guidelines for agents
- `ReasoningContextBuilder`: Builds context for agents

---

## Integration Patterns

### Pattern 1: Complete Sequential Flow (Recommended)

**This is the standard flow that should be followed:**

```
STEP 1: Document Analysis
   → ControlUniverseReasoningWorkflow
   → Input: Compliance documents
   → Output: ComplianceControlUniverse
   → Contains: Controls, Sub-Controls, Measurable Expectations, Evidence Types

STEP 2: Feature Engineering
   → FeatureEngineeringPipeline
   → Input: User query + Control Universe from STEP 1
   → Output: Recommended Features
   → Contains: Compliance features, schemas, calculation logic

STEP 3: Deep Research & Risk Modeling
   → RiskModelReasoningWorkflow
   → Input: 
     - Control Universe from STEP 1
     - Recommended Features from STEP 2
     - Domain analysis
   → Output: Complete Risk Model Blueprint
   → Contains: 
     - Measurable Signals
     - Likelihood Model Inputs
     - Impact Model Inputs
     - Contextual Factors
     - Risk Calculations
```

### Pattern 2: Feature Engineering Only (Without Documents)

```
1. User query for compliance analytics
   → FeatureEngineeringPipeline
   → Input: User query, project_id
   → Output: Recommended Features
   → Note: Controls identified from data model, not documents

2. (Optional) Generate impact/likelihood/risk features separately
   → generate_impact_features()
   → generate_likelihood_features()
   → generate_risk_features()
   → Note: These are simpler versions, not the deep research from STEP 3
```

### Pattern 3: Domain-Specific Configuration

```
1. Select domain configuration
   → get_domain_config("hr_compliance")
   → Provides: Entity types, frameworks, feature patterns

2. Get compliance metrics library
   → get_compliance_metric_library("hr_compliance")
   → Provides: Natural language questions → metrics mapping

3. Get compliance controls
   → get_compliance_control_set("hr_compliance")
   → Provides: Predefined controls for the domain

4. Use in feature engineering
   → FeatureEngineeringPipeline(domain_config=config)
   → Agents use domain-specific knowledge
```

---

## Key Concepts

### Universal Frameworks

The system uses **universal frameworks** that work across all compliance domains:

**Universal Impact Dimensions**:
- Regulatory Severity
- Customer Trust / Brand Sensitivity
- Financial Impact
- Operational Disruption
- Downstream Dependency
- Crown Jewel Relevance

**Universal Likelihood Drivers**:
- Historical Failure Rate
- Control Drift Frequency
- Evidence Quality Score
- Process Volatility
- Human Dependency
- Operational Load
- Control Maturity Level

**Universal Signal Categories**:
- Timeliness
- Completeness
- Adherence
- Drift
- Incident Frequency
- Exceptions
- Responsiveness
- Maturity

### Natural Language Questions

Features are represented as **natural language questions** that can be interpreted by other agents:

- Instead of: `risk_score = exploitability * asset_criticality`
- Use: `"What is the overall risk score when combining exploitability scores with asset criticality ratings?"`

This enables:
- Better agent-to-agent communication
- Human-readable feature definitions
- Easier validation and debugging

### Knowledge-Based Reasoning

The system uses **knowledge-based reasoning** rather than just schema lookup:

- Agents infer data requirements from knowledge documents
- Domain expertise guides feature generation
- Compliance frameworks inform calculations
- Historical examples provide patterns

---

## Usage Examples

### Example 1: Complete Sequential Flow (Recommended)

**This example shows the complete three-phase approach:**

```python
from app.agents.nodes.transform.document_analysis_agents import (
    create_control_universe_workflow,
    extract_blueprint
)
from app.agents.nodes.transform.feature_engineering_agent import (
    FeatureEngineeringPipeline
)
from app.agents.nodes.transform.risk_model_agents import (
    create_risk_model_workflow,
    extract_risk_model_blueprint
)
from app.agents.nodes.transform.domain_config import (
    HR_COMPLIANCE_DOMAIN_CONFIG
)

# ============================================================
# STEP 1: Document Analysis - Build Control Universe
# ============================================================
print("STEP 1: Analyzing compliance documents...")
doc_workflow = create_control_universe_workflow(anthropic_api_key)

doc_result = doc_workflow.run(
    source_documents=[
        {
            "content": "GDPR Article 5 requires...",
            "metadata": {"source": "GDPR_Regulation.pdf"}
        }
    ],
    compliance_framework="GDPR"
)

blueprint = extract_blueprint(doc_result)
control_universe = blueprint.get("control_universe_blueprint")
controls = blueprint.get("identified_controls", [])

print(f"✓ Identified {len(controls)} controls from documents")

# ============================================================
# STEP 2: Feature Engineering - Generate Compliance Features
# ============================================================
print("\nSTEP 2: Generating compliance features...")
feature_pipeline = FeatureEngineeringPipeline(
    llm=llm,
    retrieval_helper=retrieval_helper,
    domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
)

feature_result = await feature_pipeline.run(
    user_query="Track training completion rates for GDPR compliance",
    project_id="cornerstone_learning"
)

recommended_features = feature_result["recommended_features"]
print(f"✓ Generated {len(recommended_features)} compliance features")

# ============================================================
# STEP 3: Deep Research & Risk Modeling
# ============================================================
print("\nSTEP 3: Performing deep research for risk modeling...")
risk_workflow = create_risk_model_workflow(anthropic_api_key)

risk_result = risk_workflow.run(
    controls=controls,  # From STEP 1
    compliance_framework="GDPR",
    domain_context={
        "domain_name": "HR Compliance",
        "industry": "Technology",
        "features": recommended_features  # From STEP 2
    },
    signal_patterns=[...],
    benchmarks={...},
    historical_models=[...]
)

risk_blueprint = extract_risk_model_blueprint(risk_result)

# Access comprehensive risk model components
signals = risk_blueprint.get("proposed_signals", [])
likelihood_inputs = risk_blueprint.get("proposed_likelihood_inputs", [])
impact_inputs = risk_blueprint.get("proposed_impact_inputs", [])
contextual_factors = risk_blueprint.get("proposed_contextual_factors", [])

print(f"✓ Built complete risk model:")
print(f"  - {len(signals)} measurable signals")
print(f"  - {len(likelihood_inputs)} likelihood inputs")
print(f"  - {len(impact_inputs)} impact inputs")
print(f"  - {len(contextual_factors)} contextual factors")
```

### Example 2: Feature Engineering Only (Without Documents)

**Use this pattern when you don't have compliance documents but want to generate features:**

```python
from app.agents.nodes.transform.feature_engineering_agent import (
    run_feature_engineering_pipeline
)
from app.agents.nodes.transform.domain_config import (
    HR_COMPLIANCE_DOMAIN_CONFIG
)

# Generate compliance features without document analysis
result = await run_feature_engineering_pipeline(
    user_query="Track training completion rates for GDPR compliance",
    project_id="cornerstone_learning",
    domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
)

# Access results
features = result["recommended_features"]
# Note: Controls are identified from data model, not documents
```

**This example shows STEP 3 (Deep Research) using outputs from STEP 1 and STEP 2:**

```python
from app.agents.nodes.transform.risk_model_agents import (
    create_risk_model_workflow,
    extract_risk_model_blueprint
)

# Assume you have:
# - controls: From STEP 1 (Document Analysis)
# - recommended_features: From STEP 2 (Feature Engineering)
# - domain_context: Domain analysis

workflow = create_risk_model_workflow(anthropic_api_key)

result = workflow.run(
    controls=controls,  # From STEP 1: Control Universe
    compliance_framework="SOC2",
    domain_context={
        "domain_name": "Cybersecurity",
        "industry": "Technology",
        "features": recommended_features,  # From STEP 2: Features
        "domain_analysis": {
            "entity_types": ["Asset", "Vulnerability", "CVE"],
            "risk_factors": ["exploitability", "asset_criticality"],
            "compliance_requirements": ["SLA compliance", "patch management"]
        }
    },
    signal_patterns=[...],  # Historical patterns
    benchmarks={...},        # Industry benchmarks
    historical_models=[...] # Previous risk models
)

# Extract the risk model blueprint
blueprint = extract_risk_model_blueprint(result)

# Access comprehensive risk model components
signals = blueprint.get("proposed_signals", [])
likelihood_inputs = blueprint.get("proposed_likelihood_inputs", [])
impact_inputs = blueprint.get("proposed_impact_inputs", [])
contextual_factors = blueprint.get("proposed_contextual_factors", [])

# The blueprint contains the complete risk model that combines:
# - Features from STEP 2
# - Controls from STEP 1
# - Domain analysis
# - Deep research on likelihood, impact, and risk
```

---

## State Management

All workflows use **LangGraph state management**:

- State is passed between agents
- Each agent reads from and writes to state
- State contains all context needed for reasoning
- State can be persisted and resumed

**Key State Fields**:
- `messages`: Conversation history
- `user_query`: Original user query
- `analytical_intent`: Parsed intent
- `recommended_features`: Generated features
- `identified_controls`: Controls from data model
- `knowledge_documents`: Retrieved knowledge
- `schema_registry`: Available data schemas
- `domain_config`: Domain configuration

---

## Extensibility

### Adding New Domains

1. Create domain configuration in `domain_config.py`:
```python
MY_DOMAIN_CONFIG = DomainConfiguration(
    domain_name="my_domain",
    entity_types=["Entity1", "Entity2"],
    compliance_frameworks=["Framework1"],
    feature_patterns={...},
    ...
)
```

2. Add to domain registry:
```python
DOMAIN_CONFIGS["my_domain"] = MY_DOMAIN_CONFIG
```

3. Create compliance metrics library:
```python
MY_DOMAIN_METRICS = ComplianceMetricLibrary(
    domain_name="my_domain",
    metrics=[...],
    ...
)
```

4. Create control set:
```python
MY_DOMAIN_CONTROLS = ComplianceControlSet(
    domain_name="my_domain",
    controls=[...],
    ...
)
```

### Adding New Agents

1. Create agent class inheriting from base agent pattern
2. Implement `__call__` method that takes state and returns updated state
3. Add agent to workflow graph
4. Define routing logic

---

## Dependencies

- **LangGraph**: Workflow orchestration
- **LangChain**: LLM integration and message handling
- **Pydantic**: Data validation and structured outputs
- **RetrievalHelper**: Schema and knowledge retrieval

---

## Best Practices

1. **Always provide domain configuration**: Use appropriate domain config for your use case
2. **Use natural language questions**: Represent features as questions for better agent communication
3. **Leverage knowledge documents**: Provide relevant compliance knowledge for better feature generation
4. **Follow the workflow patterns**: Use the established patterns for consistency
5. **Validate outputs**: Use relevancy scoring to validate feature quality
6. **Handle errors gracefully**: All agents have fallback mechanisms

---

## Troubleshooting

### Common Issues

1. **No controls identified**: Check if compliance framework is correctly specified
2. **Missing features**: Ensure knowledge documents are available and relevant
3. **Schema not found**: Verify RetrievalHelper is configured and project_id is correct
4. **Low relevance scores**: Review user query clarity and provide better examples

### Debugging

- Check state at each agent step
- Review agent messages in state["messages"]
- Validate domain configuration matches your use case
- Ensure LLM has proper API keys and access

---

## Future Enhancements

- [ ] Support for more compliance frameworks
- [ ] Automated control universe updates
- [ ] Real-time feature monitoring
- [ ] Integration with data quality systems
- [ ] Advanced risk model calibration
- [ ] Multi-domain risk aggregation

---

## Contributing

When adding new features:
1. Follow the existing agent patterns
2. Update domain configurations
3. Add comprehensive documentation
4. Include usage examples
5. Update this README

---

## License

[Your License Here]

