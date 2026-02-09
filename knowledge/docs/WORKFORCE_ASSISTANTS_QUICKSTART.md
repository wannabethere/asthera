# Workforce Assistants Quick Start Guide

Get started with Product, Compliance, and Domain Knowledge assistants in 5 minutes.

## Installation

The Workforce Assistants are already part of the knowledge service. No additional installation required.

## Basic Usage

### 1. Product Assistant

Ask questions about product features, APIs, and configurations.

```python
from app.assistants import create_product_assistant

# Create assistant
assistant = create_product_assistant()

# Ask a question
result = await assistant.process_query(
    user_question="How do I configure Snyk to scan for high-severity vulnerabilities?",
    available_products=["Snyk"],
    available_actions=["Configure", "Scan", "Filter"],
    output_format="summary"
)

# Use the response
print(result["response"])
```

**Example Questions:**
- "How do I integrate Snyk with GitHub?"
- "What API endpoints does Okta provide for user management?"
- "How do I configure alerts in PagerDuty?"

### 2. Compliance Assistant

Ask questions about compliance frameworks, controls, and requirements.

```python
from app.assistants import create_compliance_assistant

# Create assistant
assistant = create_compliance_assistant()

# Ask a question
result = await assistant.process_query(
    user_question="What SOC2 controls are required for access management?",
    available_frameworks=["SOC2"],
    available_products=["Okta", "Snyk"],
    available_actors=["Compliance Officer", "Auditor"],
    output_format="summary"
)

# Use the response
print(result["response"])
```

**Example Questions:**
- "What SOC2 controls cover data encryption?"
- "What evidence is needed for HIPAA compliance?"
- "How do I implement GDPR data retention policies?"

### 3. Domain Knowledge Assistant

Ask questions about industry concepts, best practices, and technical patterns.

```python
from app.assistants import create_domain_knowledge_assistant

# Create assistant
assistant = create_domain_knowledge_assistant()

# Ask a question
result = await assistant.process_query(
    user_question="What are the best practices for implementing encryption at rest?",
    available_domains=["Security", "Privacy"],
    available_concepts=["Encryption", "Data Protection"],
    output_format="summary"
)

# Use the response
print(result["response"])
```

**Example Questions:**
- "What is Zero Trust Architecture?"
- "What are best practices for API authentication?"
- "How does SAML differ from OAuth?"

## Response Structure

All assistants return the same structure:

```python
{
    "breakdown": {
        "query_type": "product",
        "user_intent": "Configure Snyk for vulnerability scanning",
        "identified_entities": ["Snyk", "Vulnerability Scanning"],
        "query_keywords": ["configure", "snyk", "vulnerability", "high-severity"]
    },
    "retrieved_docs": [
        {
            "document": "Snyk provides...",
            "metadata": {...},
            "relevance_score": 0.95
        }
    ],
    "web_search_results": [...],
    "response": "To configure Snyk for high-severity vulnerability scanning..."
}
```

## Output Formats

### Summary Format (Human-Readable)

```python
result = await assistant.process_query(
    user_question="...",
    output_format="summary"  # Default
)

print(result["response"])
# Output: "To configure Snyk for high-severity vulnerability scanning,
#          you need to: 1) Enable severity filtering in settings..."
```

### JSON Format (Machine-Readable)

```python
result = await assistant.process_query(
    user_question="...",
    output_format="json"
)

import json
docs = json.loads(result["response"])
for doc in docs:
    print(f"- {doc['title']}: {doc['summary']}")
```

## Common Patterns

### Pattern 1: Simple Query

```python
assistant = create_product_assistant()
result = await assistant.process_query(
    user_question="How do I use Snyk's API?",
    available_products=["Snyk"],
    output_format="summary"
)
```

### Pattern 2: With Context

```python
assistant = create_compliance_assistant()
result = await assistant.process_query(
    user_question="What controls do I need?",
    available_frameworks=["SOC2", "HIPAA"],
    available_products=["Okta", "Snyk"],
    available_actors=["Compliance Officer"],
    output_format="summary"
)
```

### Pattern 3: Batch Processing

```python
assistant = create_domain_knowledge_assistant()

questions = [
    "What is encryption at rest?",
    "What is encryption in transit?",
    "What is end-to-end encryption?"
]

results = await asyncio.gather(*[
    assistant.process_query(
        user_question=q,
        available_domains=["Security"],
        output_format="summary"
    )
    for q in questions
])
```

### Pattern 4: Custom Configuration

```python
from app.assistants import AssistantConfig, DataSourceConfig, AssistantType

# Create custom config
config = AssistantConfig(
    assistant_type=AssistantType.PRODUCT,
    model_name="gpt-4o",  # Use better model
    temperature=0.1,      # More deterministic
    web_search_enabled=False,  # Disable web search
    max_edges=5  # Limit results
)

# Use custom config
assistant = create_product_assistant(config=config)
```

## Integration with FastAPI

```python
from fastapi import APIRouter
from app.assistants import create_product_assistant

router = APIRouter()

@router.post("/api/workforce/product")
async def product_query(
    question: str,
    products: list[str],
    output_format: str = "summary"
):
    assistant = create_product_assistant()
    result = await assistant.process_query(
        user_question=question,
        available_products=products,
        output_format=output_format
    )
    return {
        "query": question,
        "response": result["response"],
        "breakdown": result["breakdown"]
    }
```

## Troubleshooting

### Issue: Slow Responses

**Solution:** Reduce `max_edges` or disable web search

```python
config = AssistantConfig(
    assistant_type=AssistantType.PRODUCT,
    web_search_enabled=False,
    max_edges=5
)
assistant = create_product_assistant(config=config)
```

### Issue: Irrelevant Results

**Solution:** Provide more context

```python
result = await assistant.process_query(
    user_question="How do I configure scanning?",
    available_products=["Snyk"],  # Be specific
    available_actions=["Configure", "Scan"],  # Add context
    output_format="summary"
)
```

### Issue: Missing Information

**Solution:** Enable web search or add data sources

```python
config = AssistantConfig(
    assistant_type=AssistantType.PRODUCT,
    web_search_enabled=True,  # Enable web search
    max_edges=15  # Increase results
)
```

## Next Steps

1. **Read the Full Documentation:** [workforce_assistants_README.md](../app/assistants/workforce_assistants_README.md)
2. **See More Examples:** [workforce_assistants_usage.py](../examples/workforce_assistants_usage.py)
3. **Customize Configuration:** [workforce_config.py](../app/assistants/workforce_config.py)
4. **Integration Guide:** [WORKFORCE_ASSISTANTS_IMPLEMENTATION.md](./WORKFORCE_ASSISTANTS_IMPLEMENTATION.md)

## Quick Reference

### Product Assistant
```python
create_product_assistant()
# Questions: product features, APIs, configuration
# Context: available_products, available_actions
```

### Compliance Assistant
```python
create_compliance_assistant()
# Questions: frameworks, controls, requirements
# Context: available_frameworks, available_actors
```

### Domain Knowledge Assistant
```python
create_domain_knowledge_assistant()
# Questions: concepts, best practices, patterns
# Context: available_domains, available_concepts
```

## Getting Help

- **Documentation:** See `app/assistants/workforce_assistants_README.md`
- **Examples:** See `examples/workforce_assistants_usage.py`
- **Implementation:** See `docs/WORKFORCE_ASSISTANTS_IMPLEMENTATION.md`
- **Design:** See `docs/Design_assistance_workforce.md`
