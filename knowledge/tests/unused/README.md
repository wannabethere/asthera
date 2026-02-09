# Universal Risk Metadata Framework

A comprehensive system for generating domain-adaptive risk metadata using transfer learning and LLM agents.

## Overview

This framework implements **STAGE 0: Universal Risk Metadata Framework with Transfer Learning** as described in the metadata design document. It enables:

- **Transfer Learning**: Learn metadata patterns from one domain (e.g., cybersecurity) and apply to others (HR, finance, operations)
- **LLM-Driven Generation**: Use LangGraph agents to automatically generate metadata from compliance documents
- **PostgreSQL Storage**: Universal schema that works across any compliance domain
- **Data-Driven Risk Evaluation**: Quantitative risk scoring and prioritization

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Metadata Transfer Learning Workflow (LangGraph)       │
├─────────────────────────────────────────────────────────┤
│  1. Pattern Recognition Agent                            │
│     ↓                                                     │
│  2. Domain Adaptation Agent                              │
│     ↓                                                     │
│  3. Metadata Generation Agent                             │
│     ↓                                                     │
│  4. Validation Agent                                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL Database                                    │
│  - domain_risk_metadata                                 │
│  - metadata_patterns                                    │
│  - cross_domain_mappings                                │
│  - metadata_generation_sessions                        │
└─────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

```bash
pip install langchain langchain-openai langgraph
pip install asyncpg  # For PostgreSQL
```

### Database Setup

Run the migration to create the schema:

```bash
psql -U your_user -d your_database -f migrations/create_universal_metadata_schema.sql
```

## Quick Start

### Basic Usage

```python
from knowledge.app.agents import generate_metadata_for_domain

# Generate metadata for HR compliance domain
state = await generate_metadata_for_domain(
    target_domain="hr_compliance",
    target_documents=[
        "Title VII prohibits discriminatory hiring practices...",
        "FLSA requires overtime pay for non-exempt employees...",
        "ADA requires reasonable accommodations for disabilities..."
    ],
    source_domains=["cybersecurity"],
    target_framework="GENERAL"
)

# Access generated metadata
for entry in state["refined_metadata"]:
    print(f"{entry['code']}: {entry['description']} (score: {entry['numeric_score']})")
```

### Using the Workflow Directly

```python
from knowledge.app.agents import MetadataTransferLearningWorkflow
from langchain_openai import ChatOpenAI

# Initialize workflow
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
workflow = MetadataTransferLearningWorkflow(llm=llm)

# Run workflow
state = await workflow.run(
    target_domain="financial_risk",
    target_documents=["SOX Section 302 requires CEO/CFO certification..."],
    source_domains=["cybersecurity", "hr_compliance"],
    target_framework="SOX"
)

# Check results
print(f"Status: {state['status']}")
print(f"Entries created: {state['metadata_entries_created']}")
print(f"Confidence: {state['overall_confidence']:.2f}")
```

### Database Integration

```python
import asyncpg
from knowledge.app.services import MetadataService
from knowledge.app.agents import generate_metadata_for_domain

# Create database pool
db_pool = await asyncpg.create_pool(
    host="localhost",
    database="genieml",
    user="postgres",
    password="password"
)

# Initialize service
metadata_service = MetadataService(db_pool)

# Generate metadata
state = await generate_metadata_for_domain(
    target_domain="hr_compliance",
    target_documents=["..."],
    source_domains=["cybersecurity"]
)

# Save to database
from knowledge.app.agents.state_helpers import get_entries_from_state
entries = get_entries_from_state(state)
await metadata_service.save_metadata_entries(entries)
```

## Components

### 1. Agents

- **PatternRecognitionAgent**: Analyzes source domain metadata to extract transferable patterns
- **DomainAdaptationAgent**: Maps source patterns to target domain concepts
- **MetadataGenerationAgent**: Generates metadata entries from documents using learned patterns
- **ValidationAgent**: Validates and refines generated metadata

### 2. Database Schema

- **domain_risk_metadata**: Universal metadata table for all domains
- **metadata_patterns**: Stores learned patterns for reuse
- **cross_domain_mappings**: Maps equivalent concepts across domains
- **metadata_generation_sessions**: Tracks generation sessions

### 3. Services

- **MetadataService**: Database operations for metadata management

## Example: HR Compliance Metadata Generation

```python
from knowledge.app.agents import generate_metadata_for_domain

# HR compliance documents
hr_docs = [
    """
    Title VII of the Civil Rights Act prohibits employment discrimination
    based on race, color, religion, sex, or national origin. Violations
    can result in EEOC investigations, lawsuits, and significant penalties.
    """,
    """
    The Fair Labor Standards Act (FLSA) requires overtime pay for non-exempt
    employees working more than 40 hours per week. Common violations include
    misclassification of employees and failure to pay overtime.
    """,
    """
    The Americans with Disabilities Act (ADA) requires employers to provide
    reasonable accommodations for qualified individuals with disabilities.
    Failure to accommodate can result in discrimination claims.
    """
]

# Generate metadata
state = await generate_metadata_for_domain(
    target_domain="hr_compliance",
    target_documents=hr_docs,
    source_domains=["cybersecurity"],
    target_framework="GENERAL"
)

# Results include:
# - discriminatory_hiring (risk_score: 90.0)
# - wage_hour_violations (risk_score: 85.0)
# - ada_accommodation_failure (risk_score: 80.0)
```

## Integration with Existing Systems

The metadata framework integrates with:

1. **Control Universe (Stages 1-3)**: Metadata enriches knowledge graph nodes
2. **Semantic Context (Stage 2)**: Risk-informed retrieval and reasoning
3. **Data Model & Metrics (Stage 3)**: Metadata drives metric generation

## API Reference

See the individual module documentation:

- `knowledge/app/agents/` - Agent implementations
- `knowledge/app/services/` - Service layer
- `knowledge/migrations/` - Database schema

## Advanced Usage

### Custom LLM Configuration

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.2,
    max_tokens=4000
)

workflow = MetadataTransferLearningWorkflow(llm=llm)
```

### Loading Source Metadata from Database

```python
from knowledge.app.services import MetadataService

service = MetadataService(db_pool)
source_metadata = await service.load_source_metadata(
    source_domains=["cybersecurity"],
    metadata_categories=["threat", "severity"]
)
```

### Cross-Domain Mappings

```python
# Get mappings between domains
mappings = await service.get_cross_domain_mappings(
    source_domain="cybersecurity",
    target_domain="hr_compliance"
)
```

## Testing

```python
# Run workflow with test data
state = await generate_metadata_for_domain(
    target_domain="test_domain",
    target_documents=["Test document content..."],
    source_domains=["cybersecurity"]
)

assert state["status"] == "completed"
assert len(state["refined_metadata"]) > 0
```

## License

Same as parent project.

