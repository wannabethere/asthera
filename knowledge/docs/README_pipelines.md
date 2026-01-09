# Extraction Pipelines

This directory contains extraction pipelines for creating contextual graph documents using LLM-powered extraction. The pipelines follow the async pipeline architecture pattern from `genieml/agents/docs/pipeline.md`.

**All pipelines now support configurable rules**, allowing them to work for different domains (compliance, finance, healthcare, etc.) instead of being hardcoded for compliance.

## Architecture

### Base Pipeline Class

All extraction pipelines inherit from `ExtractionPipeline` which provides:
- Async execution with `run()` method
- Batch processing with `run_batch()` method (controlled concurrency)
- Status callbacks for progress tracking
- Configuration management
- Initialization and cleanup hooks

### Available Pipelines

1. **ControlExtractionPipeline**: Extracts control information from regulatory text (v2.0.0 - configurable rules)
2. **ContextExtractionPipeline**: Extracts structured context from organizational descriptions (v2.0.0 - configurable rules)
3. **RequirementExtractionPipeline**: Creates contextual requirement documents (v2.0.0 - configurable rules)
4. **EvidenceExtractionPipeline**: Creates evidence collection guides (v2.0.0 - configurable rules)
5. **FieldsExtractionPipeline**: Extracts fields from text and creates contextual edges (v1.0.0 - NEW)
6. **EntitiesExtractionPipeline**: Extracts entities and relationships from text and creates contextual edges (v1.0.0 - NEW)

## Usage

### Single Extraction (Default Compliance Rules)

```python
from app.agents.pipelines import ControlExtractionPipeline
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
pipeline = ControlExtractionPipeline(llm=llm)
await pipeline.initialize()

result = await pipeline.run(
    inputs={
        "text": "HIPAA requires access controls...",
        "framework": "HIPAA",
        "context_metadata": {"industry": "healthcare"}
    }
)
```

### Using Custom Rules

```python
from app.agents.pipelines import ContextExtractionPipeline
from app.agents.extractors import ExtractionRules, FieldExtractionRule

# Create custom rules for finance domain
finance_rules = ExtractionRules(
    extraction_type="context",
    domain="finance",
    system_role="expert at analyzing financial organizational contexts",
    system_instructions="Extract: company type, AUM, regulatory bodies...",
    fields=[
        FieldExtractionRule("company_type", "Type of financial company"),
        FieldExtractionRule("aum", "Assets under management", data_type="float"),
    ],
    human_prompt_template="Extract financial context from: {description}",
    human_prompt_variables=["description"]
)

pipeline = ContextExtractionPipeline(llm=llm, rules=finance_rules)
await pipeline.initialize()

result = await pipeline.run(
    inputs={"description": "A regional bank with $10B in assets..."}
)
```

### Fields Extraction Pipeline

```python
from app.agents.pipelines import FieldsExtractionPipeline

pipeline = FieldsExtractionPipeline(llm=llm)
await pipeline.initialize()

field_definitions = [
    {"name": "metric_id", "description": "Metric identifier", "data_type": "string"},
    {"name": "target_value", "description": "Target metric value", "data_type": "string"},
]

result = await pipeline.run(
    inputs={
        "text": "AC-001: User Access Review Completion Rate...",
        "context_id": "ctx_123",
        "source_entity_id": "metrics_registry",
        "field_definitions": field_definitions
    }
)

# result["data"]["edges"] contains ContextualEdge objects ready to save
```

### Entities Extraction Pipeline

```python
from app.agents.pipelines import EntitiesExtractionPipeline

pipeline = EntitiesExtractionPipeline(llm=llm)
await pipeline.initialize()

result = await pipeline.run(
    inputs={
        "text": "HIPAA requires access controls. Control AC-001 implements...",
        "context_id": "ctx_123",
        "entity_types": ["control", "requirement", "evidence"],
        "context_metadata": {"framework": "HIPAA"}
    }
)

# result["data"]["entities"] contains extracted entities
# result["data"]["edges"] contains relationship edges
```

### Batch Extraction

```python
inputs_list = [
    {"text": "...", "framework": "SOC2", "context_metadata": {}},
    {"text": "...", "framework": "GDPR", "context_metadata": {}},
]

results = await pipeline.run_batch(
    inputs_list=inputs_list,
    max_concurrent=5  # Process up to 5 in parallel
)
```

## ExtractionService

For a unified interface with caching and request management, use `ExtractionService`:

```python
from app.services.extraction_service import ExtractionService

service = ExtractionService(llm=llm)
await service.initialize()

# Single extraction
response = await service.extract_control(
    text="...",
    framework="HIPAA",
    context_metadata={}
)

# Batch extraction
batch_response = await service.batch_extract_controls(
    texts=[...],
    max_concurrent=5
)
```

See `app/services/examples/extraction_service_example.py` for complete examples.

## Migration from Legacy Extractors

The old extractors in `app/agents/extractors/` are still available for backward compatibility, but new code should use the pipelines:

**Old (still works):**
```python
from app.agents.extractors import ControlExtractor
extractor = ControlExtractor(llm=llm)
result = await extractor.extract_control_from_text(...)
```

**New (recommended):**
```python
from app.agents.pipelines import ControlExtractionPipeline
pipeline = ControlExtractionPipeline(llm=llm)
await pipeline.initialize()
result = await pipeline.run(inputs={...})
```

## Pipeline Pattern

Each pipeline follows this pattern:

1. **Initialization**: `await pipeline.initialize()` - Set up resources
2. **Execution**: `await pipeline.run(inputs, ...)` - Process single input
3. **Batch Execution**: `await pipeline.run_batch(inputs_list, ...)` - Process multiple inputs
4. **Cleanup**: `await pipeline.cleanup()` - Release resources

All pipelines support:
- Status callbacks for progress tracking
- Configuration overrides (including rules via `configuration={"rules": ...}`)
- Error handling with detailed error messages
- Async/await throughout
- Configurable rules for domain-agnostic extraction

## Configuration

### Rules Configuration

All pipelines accept `ExtractionRules` configuration:

```python
from app.agents.extractors import ExtractionRules, get_compliance_context_rules

# Option 1: Use predefined rules
pipeline = ContextExtractionPipeline(
    llm=llm,
    rules=get_compliance_context_rules()
)

# Option 2: Create custom rules
custom_rules = ExtractionRules(...)
pipeline = ContextExtractionPipeline(llm=llm, rules=custom_rules)

# Option 3: Override rules at runtime
result = await pipeline.run(
    inputs={...},
    configuration={"rules": custom_rules_dict}
)
```

See `app/agents/extractors/extraction_rules.py` for details on creating custom rules.

