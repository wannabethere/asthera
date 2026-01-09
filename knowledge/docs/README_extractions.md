# Configurable Extraction Rules

The extractors in this module have been refactored to use a configurable rules-based system, making them domain-agnostic and reusable for different extraction tasks.

## Overview

All extractors (`ContextExtractor`, `ControlExtractor`, `EvidenceExtractor`, `RequirementExtractor`) now accept an `ExtractionRules` configuration object that defines:
- What fields to extract
- System prompts and instructions
- Document structure
- Output format

This allows you to use the same extractors for compliance, finance, healthcare, or any other domain by simply changing the rules configuration.

## Basic Usage

### Using Default Compliance Rules (Backward Compatible)

```python
from app.agents.extractors import ContextExtractor

extractor = ContextExtractor()
# Uses compliance rules by default
context = await extractor.extract_context_from_description(
    description="A healthcare company with 500 employees..."
)
```

### Using Custom Rules

```python
from app.agents.extractors import (
    ContextExtractor,
    ExtractionRules,
    FieldExtractionRule
)

# Define custom rules for finance domain
finance_rules = ExtractionRules(
    extraction_type="context",
    domain="finance",
    system_role="expert at analyzing financial organizational contexts",
    system_instructions="""Extract structured information:
1. Company type (bank, fintech, investment firm, etc.)
2. Assets under management
3. Regulatory bodies (SEC, FINRA, etc.)
4. Risk profile
5. Compliance maturity""",
    fields=[
        FieldExtractionRule("company_type", "Type of financial company"),
        FieldExtractionRule("aum", "Assets under management", data_type="float"),
        FieldExtractionRule("regulatory_bodies", "Regulatory bodies", data_type="list"),
        FieldExtractionRule("risk_profile", "Risk profile", examples=["low", "medium", "high"]),
    ],
    human_prompt_template="Extract financial context from: {description}",
    human_prompt_variables=["description"]
)

extractor = ContextExtractor(rules=finance_rules)
context = await extractor.extract_context_from_description(
    description="A regional bank with $10B in assets..."
)
```

## Creating Custom Rules

### Field Extraction Rules

```python
from app.agents.extractors import FieldExtractionRule

field = FieldExtractionRule(
    name="industry",
    description="Industry sector",
    data_type="string",  # string, list, int, float, bool
    required=False,
    default_value=None,
    examples=["healthcare", "finance", "technology"],
    validation_rules={"enum": ["healthcare", "finance", "technology"]}
)
```

### Complete Extraction Rules

```python
from app.agents.extractors import ExtractionRules, FieldExtractionRule

rules = ExtractionRules(
    extraction_type="entity",  # Your extraction type
    domain="healthcare",       # Your domain
    
    # System prompt configuration
    system_role="expert at extracting healthcare entity information",
    system_instructions="""Extract the following:
1. Entity type
2. Regulatory requirements
3. Data handling requirements
...""",
    
    # Fields to extract
    fields=[
        FieldExtractionRule("entity_type", "Type of entity", required=True),
        FieldExtractionRule("regulatory_requirements", "Requirements", data_type="list"),
    ],
    
    # Document sections (for document generation)
    document_sections=[
        {"name": "Overview", "description": "Entity overview"},
        {"name": "Requirements", "description": "Regulatory requirements"},
    ],
    
    # Prompt template
    human_prompt_template="Extract from: {text}\nContext: {context}",
    human_prompt_variables=["text", "context"],
    
    # Output configuration
    output_format="json",
    use_json_parser=True
)
```

## Loading Rules from Configuration

You can serialize and load rules from JSON:

```python
import json
from app.agents.extractors import ExtractionRules

# Save rules
rules_dict = rules.to_dict()
with open("my_rules.json", "w") as f:
    json.dump(rules_dict, f, indent=2)

# Load rules
with open("my_rules.json", "r") as f:
    rules_dict = json.load(f)
rules = ExtractionRules.from_dict(rules_dict)
```

## Examples

### Example 1: Healthcare Context Extraction

```python
healthcare_rules = ExtractionRules(
    extraction_type="context",
    domain="healthcare",
    system_role="expert at analyzing healthcare organizational contexts",
    system_instructions="""Extract:
1. Healthcare setting (hospital, clinic, research, etc.)
2. Patient volume
3. Data types (PHI, ePHI, research data)
4. HIPAA compliance status
5. Systems in use (EHR, billing, etc.)""",
    fields=[
        FieldExtractionRule("healthcare_setting", "Type of healthcare setting"),
        FieldExtractionRule("patient_volume", "Monthly patient volume", data_type="int"),
        FieldExtractionRule("data_types", "Data types handled", data_type="list"),
        FieldExtractionRule("hipaa_compliant", "HIPAA compliance status", data_type="bool"),
    ],
    human_prompt_template="Analyze this healthcare organization: {description}",
    human_prompt_variables=["description"]
)

extractor = ContextExtractor(rules=healthcare_rules)
```

### Example 2: Finance Control Extraction

```python
finance_control_rules = ExtractionRules(
    extraction_type="control",
    domain="finance",
    system_role="expert at extracting financial control information",
    system_instructions="""Extract:
1. Control ID
2. Control name
3. Regulatory framework (SEC, FINRA, etc.)
4. Risk category
5. Implementation requirements""",
    fields=[
        FieldExtractionRule("control_id", "Control identifier", required=True),
        FieldExtractionRule("control_name", "Control name", required=True),
        FieldExtractionRule("regulatory_framework", "Regulatory framework"),
        FieldExtractionRule("risk_category", "Risk category"),
    ],
    document_sections=[
        {"name": "Control Overview", "description": "What the control requires"},
        {"name": "Financial Context", "description": "How it applies in financial context"},
        {"name": "Implementation", "description": "How to implement"},
    ],
    human_prompt_template="Extract control from: {text}\nFramework: {framework}",
    human_prompt_variables=["text", "framework"]
)

extractor = ControlExtractor(rules=finance_control_rules)
```

## Migration Guide

### Before (Hardcoded)

```python
extractor = ContextExtractor()
# Always uses compliance-specific prompts
```

### After (Configurable)

```python
# Option 1: Use default compliance rules (backward compatible)
extractor = ContextExtractor()

# Option 2: Use custom rules
custom_rules = ExtractionRules(...)
extractor = ContextExtractor(rules=custom_rules)
```

## Fields and Entities Extractors

Two new generic extractors are available for extracting fields and entities from text and automatically creating contextual edges:

### FieldsExtractor

Extracts structured fields from text and creates contextual edges based on the fields found.

```python
from app.agents.extractors import FieldsExtractor
from app.services.contextual_graph_storage import ContextualGraphStorage

extractor = FieldsExtractor()

# Define fields to extract
field_definitions = [
    {"name": "industry", "description": "Industry sector", "data_type": "string"},
    {"name": "employee_count", "description": "Number of employees", "data_type": "int"},
    {"name": "regulatory_frameworks", "description": "Applicable frameworks", "data_type": "list"},
]

result = await extractor.extract_fields_and_create_edges(
    text="A healthcare company with 500 employees needs HIPAA compliance...",
    context_id="ctx_123",
    source_entity_id="org_001",
    source_entity_type="organization",
    field_definitions=field_definitions,
    context_metadata={"domain": "compliance"}
)

# result contains:
# - extracted_fields: List of extracted field values
# - edges: List of ContextualEdge objects ready to save
# - raw_result: Raw LLM response

# Save edges to storage
storage = ContextualGraphStorage(...)
for edge in result["edges"]:
    storage.save_contextual_edge(edge)
```

### EntitiesExtractor

Extracts entities and their relationships from text and creates contextual edges.

```python
from app.agents.extractors import EntitiesExtractor

extractor = EntitiesExtractor()

result = await extractor.extract_entities_and_create_edges(
    text="HIPAA requires access controls. Control AC-001 implements user authentication...",
    context_id="ctx_123",
    entity_types=["control", "requirement", "evidence", "system"],
    context_metadata={"framework": "HIPAA"}
)

# result contains:
# - entities: List of extracted entities with properties
# - edges: List of ContextualEdge objects representing relationships
# - raw_result: Raw LLM response

# Example entities extracted:
# [
#   {
#     "entity_id": "control_ac001",
#     "entity_type": "control",
#     "entity_name": "Access Control AC-001",
#     "properties": {"category": "access_control", "framework": "HIPAA"}
#   },
#   ...
# ]

# Example edges created:
# [
#   ContextualEdge(
#     edge_id="edge_...",
#     source_entity_id="control_ac001",
#     target_entity_id="requirement_r001",
#     edge_type="HAS_REQUIREMENT",
#     ...
#   ),
#   ...
# ]
```

### Custom Rules for Fields/Entities Extraction

You can create custom rules for domain-specific field/entity extraction:

```python
from app.agents.extractors import (
    FieldsExtractor,
    ExtractionRules,
    FieldExtractionRule
)

# Custom rules for finance domain
finance_fields_rules = ExtractionRules(
    extraction_type="fields",
    domain="finance",
    system_role="expert at extracting financial fields from text",
    system_instructions="""Extract financial fields and create relationships:
1. Extract financial metrics (AUM, revenue, etc.)
2. Identify regulatory relationships
3. Create edges between entities and their financial attributes""",
    fields=[
        FieldExtractionRule("aum", "Assets under management", data_type="float"),
        FieldExtractionRule("revenue", "Annual revenue", data_type="float"),
        FieldExtractionRule("regulatory_bodies", "Regulatory bodies", data_type="list"),
    ],
    human_prompt_template="""Extract financial fields from: {text}
Context: {context_metadata}
Fields: {field_definitions}""",
    human_prompt_variables=["text", "context_metadata", "field_definitions"]
)

extractor = FieldsExtractor(rules=finance_fields_rules)
```

## Predefined Rules

For backward compatibility, the following predefined rule sets are available:

- `get_compliance_context_rules()` - Compliance context extraction
- `get_compliance_control_rules()` - Compliance control extraction
- `get_compliance_evidence_rules()` - Compliance evidence extraction
- `get_compliance_requirement_rules()` - Compliance requirement extraction
- `get_default_fields_rules()` - Default field extraction rules
- `get_default_entities_rules()` - Default entity extraction rules

These are used by default if no rules are provided, ensuring backward compatibility.

