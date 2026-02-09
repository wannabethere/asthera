# Metadata Transfer Learning Pipelines

This directory contains pipelines for the metadata transfer learning workflow, integrated with contextual graphs for context-aware decision making.

## Pipelines

### 1. Pattern Recognition Pipeline (`pattern_recognition_pipeline.py`)

Extracts transferable patterns from source domain metadata using contextual graphs.

**Features:**
- Loads context-aware patterns from control profiles
- Integrates with `PatternRecognitionAgent`
- Falls back to traditional metadata loading if no context available

**Usage:**
```python
from app.pipelines import PatternRecognitionPipeline
from app.services import ContextualGraphService

pipeline = PatternRecognitionPipeline(
    llm=llm,
    contextual_graph_service=context_service
)

result = await pipeline.run({
    "source_domains": ["cybersecurity"],
    "use_contextual_graph": True
})
```

### 2. Domain Adaptation Pipeline (`domain_adaptation_pipeline.py`)

Adapts learned patterns to target domain using contextual graphs for analogical reasoning.

**Features:**
- Finds matching contexts for source and target domains
- Uses multi-hop reasoning for analogical mappings
- Creates context-aware domain mappings

**Usage:**
```python
from app.pipelines import DomainAdaptationPipeline

pipeline = DomainAdaptationPipeline(
    llm=llm,
    contextual_graph_service=context_service
)

result = await pipeline.run({
    "target_domain": "healthcare_compliance",
    "target_documents": ["HIPAA requires..."],
    "learned_patterns": patterns,
    "source_domains": ["cybersecurity"],
    "use_contextual_graph": True
})
```

### 3. Metadata Generation Pipeline (`metadata_generation_pipeline.py`)

Generates metadata entries for target domain using contextual graphs for context-aware scoring.

**Features:**
- Identifies context-aware risks from control profiles
- Uses context profiles for scoring decisions
- Enhances metadata with context-specific scores

**Usage:**
```python
from app.pipelines import MetadataGenerationPipeline

pipeline = MetadataGenerationPipeline(
    llm=llm,
    contextual_graph_service=context_service
)

result = await pipeline.run({
    "target_domain": "healthcare_compliance",
    "target_documents": ["..."],
    "learned_patterns": patterns,
    "domain_mappings": mappings,
    "adaptation_strategy": strategy,
    "use_contextual_graph": True
})
```

### 4. Validation Pipeline (`validation_pipeline.py`)

Validates and refines generated metadata using contextual graphs for context-aware validation.

**Features:**
- Validates against context-specific control profiles
- Checks score alignment with organizational risk profiles
- Generates context-aware suggestions

**Usage:**
```python
from app.pipelines import ValidationPipeline

pipeline = ValidationPipeline(
    llm=llm,
    contextual_graph_service=context_service
)

result = await pipeline.run({
    "target_domain": "healthcare_compliance",
    "generated_metadata": metadata_entries,
    "learned_patterns": patterns,
    "use_contextual_graph": True
})
```

## Integration with Contextual Graphs

All pipelines support optional `contextual_graph_service` parameter. When provided:

1. **Pattern Recognition**: Loads patterns from control profiles in relevant contexts
2. **Domain Adaptation**: Uses multi-hop reasoning for analogical mappings
3. **Metadata Generation**: Uses context profiles for risk identification and scoring
4. **Validation**: Validates against context-specific profiles

If no contextual graph service is provided, pipelines fall back to LLM-only approaches (existing behavior).

## Services

Three new services use these pipelines:

### 1. Reasoning Plan Service (`app/services/reasoning_plan_service.py`)

Creates reasoning plans for user actions based on all available contexts.

**Usage:**
```python
from app.services import ReasoningPlanService, ReasoningPlanRequest

service = ReasoningPlanService(
    contextual_graph_service=context_service,
    llm=llm
)

response = await service.create_reasoning_plan(
    ReasoningPlanRequest(
        user_action="Generate metadata for HIPAA compliance",
        target_domain="healthcare_compliance",
        include_all_contexts=True
    )
)
```

### 2. Explanation Service (`app/services/explanation_service.py`)

Generates explanations for user actions based on contexts.

**Usage:**
```python
from app.services import ExplanationService, ExplanationRequest

service = ExplanationService(
    contextual_graph_service=context_service,
    llm=llm
)

response = await service.generate_explanation(
    ExplanationRequest(
        user_action="Generated 50 metadata entries",
        action_type="metadata_generation",
        include_reasoning=True
    )
)
```

### 3. Metadata Generation Action Service (`app/services/metadata_generation_action_service.py`)

Orchestrates the full metadata transfer learning workflow for user actions.

**Usage:**
```python
from app.services import MetadataGenerationActionService, MetadataGenerationActionRequest

service = MetadataGenerationActionService(
    contextual_graph_service=context_service,
    llm=llm
)
await service.initialize()

response = await service.generate_metadata_for_action(
    MetadataGenerationActionRequest(
        user_action="Generate HIPAA compliance metadata",
        target_domain="healthcare_compliance",
        target_documents=["HIPAA requires encryption..."],
        source_domains=["cybersecurity"],
        use_all_contexts=True
    )
)
```

## Decision-Making Logic

All pipelines and services follow this decision logic:

1. **If contextual graph service available**:
   - Try to find relevant contexts
   - Use context-aware approaches (more accurate)
   - Fall back to LLM if context not found

2. **If no contextual graph service**:
   - Use LLM-only approaches (existing behavior)

3. **Context matching**:
   - Search for contexts matching the query/domain
   - Use top-k contexts by relevance score
   - Consider all contexts if `use_all_contexts=True`

## Benefits

1. **Context-Aware**: Decisions reflect organizational reality
2. **More Accurate**: Scores based on actual risk profiles
3. **Better Mappings**: Analogical reasoning through context relationships
4. **Fallback Safe**: Always works even without context
5. **Scalable**: Can process multiple contexts in parallel

## Example Workflow

```python
# 1. Initialize services
context_service = ContextualGraphService(...)
meta_service = MetadataGenerationActionService(
    contextual_graph_service=context_service,
    llm=llm
)
await meta_service.initialize()

# 2. Generate metadata for user action
response = await meta_service.generate_metadata_for_action(
    MetadataGenerationActionRequest(
        user_action="Generate HIPAA compliance metadata for our clinic",
        target_domain="healthcare_compliance",
        target_documents=[hipaa_doc],
        use_all_contexts=True
    )
)

# 3. Get reasoning plan
reasoning_service = ReasoningPlanService(
    contextual_graph_service=context_service,
    llm=llm
)
plan = await reasoning_service.create_reasoning_plan(
    ReasoningPlanRequest(
        user_action="Generate HIPAA compliance metadata",
        target_domain="healthcare_compliance"
    )
)

# 4. Get explanation
explanation_service = ExplanationService(
    contextual_graph_service=context_service,
    llm=llm
)
explanation = await explanation_service.generate_explanation(
    ExplanationRequest(
        user_action="Generated 50 metadata entries",
        action_type="metadata_generation"
    )
)
```

