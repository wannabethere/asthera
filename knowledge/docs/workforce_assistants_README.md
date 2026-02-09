# Workforce Assistants

A series of specialized assistants for Product, Compliance, and Domain Knowledge queries.

## Overview

The Workforce Assistants provide a unified framework for handling different types of queries:

1. **Product Assistant** - Product documentation, API docs, features, user actions
2. **Compliance Assistant** - Compliance frameworks, controls, requirements, policies
3. **Domain Knowledge Assistant** - Industry concepts, best practices, technical patterns

All assistants share:
- Same contextual breakdown architecture
- Configurable models and prompts
- Multiple data sources with category filtering
- Web search integration
- Evidence gathering support (when enabled)

## Architecture

```
User Question
     ↓
WorkforceAssistant
     ↓
Context Breakdown Agent (Product/Compliance/Domain)
     ↓
Data Source Retrieval (Chroma/Web/PostgreSQL)
     ↓
Edge Pruning Agent (Product/Compliance/Domain)
     ↓
LLM Composition
     ↓
Final Response (Summary or JSON)
```

## Quick Start

### 1. Product Assistant

```python
from app.assistants.workforce_assistants import create_product_assistant

# Create assistant
assistant = create_product_assistant()

# Process query
result = await assistant.process_query(
    user_question="How do I configure Snyk to scan for vulnerabilities?",
    available_products=["Snyk"],
    available_actions=["Configure", "Scan", "Monitor"],
    output_format="summary"
)

print(result["response"])
```

### 2. Compliance Assistant

```python
from app.assistants.workforce_assistants import create_compliance_assistant

# Create assistant
assistant = create_compliance_assistant()

# Process query
result = await assistant.process_query(
    user_question="What SOC2 controls are needed for access management?",
    available_frameworks=["SOC2"],
    available_products=["Okta", "Snyk"],
    available_actors=["Compliance Officer", "Auditor"],
    output_format="json"
)

print(result["response"])
```

### 3. Domain Knowledge Assistant

```python
from app.assistants.workforce_assistants import create_domain_knowledge_assistant

# Create assistant
assistant = create_domain_knowledge_assistant()

# Process query
result = await assistant.process_query(
    user_question="What are the best practices for encryption at rest?",
    available_domains=["Security", "Privacy"],
    available_concepts=["Encryption", "Data Protection"],
    output_format="summary"
)

print(result["response"])
```

## Configuration

Each assistant is configured via `workforce_config.py`:

```python
from app.assistants.workforce_config import (
    AssistantType,
    AssistantConfig,
    DataSourceConfig,
    get_assistant_config
)

# Get default config
config = get_assistant_config(AssistantType.PRODUCT)

# Customize config
custom_config = AssistantConfig(
    assistant_type=AssistantType.PRODUCT,
    model_name="gpt-4o",  # Use different model
    temperature=0.3,
    system_prompt_template="...",
    human_prompt_template="...",
    data_sources=[
        DataSourceConfig(
            source_name="chroma_product_docs",
            enabled=True,
            categories=["api_docs", "user_guides"],
            priority=10
        )
    ],
    web_search_enabled=True,
    max_edges=15
)

# Use custom config
assistant = create_product_assistant(config=custom_config)
```

## Data Sources

Each assistant can retrieve from multiple data sources:

### Chroma Vector Stores
```python
DataSourceConfig(
    source_name="chroma_product_docs",
    enabled=True,
    categories=["product_features", "api_docs"],
    metadata_filters={"product_name": "Snyk"},
    priority=9
)
```

### Web Search
```python
DataSourceConfig(
    source_name="web_search",
    enabled=True,
    categories=[],
    metadata_filters={},
    priority=7
)
```

### Custom Sources
```python
# Provide custom retrieval function
async def custom_retrieval(breakdown, source_config):
    # Custom retrieval logic
    return retrieved_docs

result = await assistant.process_query(
    user_question="...",
    chroma_product_docs_retrieval_fn=custom_retrieval
)
```

## Output Formats

### Summary Format
```python
result = await assistant.process_query(
    user_question="...",
    output_format="summary"
)

# Returns: String summary
```

### JSON Format
```python
result = await assistant.process_query(
    user_question="...",
    output_format="json"
)

# Returns: JSON list of documents with summaries
```

## Response Structure

```python
{
    "breakdown": ContextBreakdown,  # Context breakdown object
    "retrieved_docs": [...],  # Retrieved documents
    "web_search_results": [...],  # Web search results
    "response": "..."  # Final response (summary or JSON)
}
```

## Design Principles

### 1. Unified Context Breakdown
All assistants use the same context breakdown architecture but with domain-specific agents.

### 2. Configurable
- Model for each action
- System prompt from static configuration
- Human message prompt with variables
- Data sources with category breakdown

### 3. Web Search as Tool
Web search is treated as a data source that can be enabled/disabled per assistant.

### 4. Category-Based Filtering
Data sources support category filtering for targeted retrieval:
- Product: `product_features`, `api_docs`, `user_guides`
- Compliance: `frameworks`, `controls`, `requirements`
- Domain: `concepts`, `best_practices`, `patterns`

## Integration Examples

### Integration with API Router

```python
from fastapi import APIRouter
from app.assistants.workforce_assistants import create_product_assistant

router = APIRouter()

@router.post("/api/product/query")
async def product_query(request: ProductQueryRequest):
    assistant = create_product_assistant()
    result = await assistant.process_query(
        user_question=request.question,
        available_products=request.products,
        output_format=request.output_format
    )
    return result
```

### Integration with Streaming

```python
from app.assistants.workforce_assistants import WorkforceAssistant
from app.assistants.workforce_config import AssistantType

async def stream_product_response(user_question: str):
    assistant = WorkforceAssistant(AssistantType.PRODUCT)
    
    # Get breakdown first
    breakdown = await assistant.context_agent.breakdown_question(
        user_question=user_question
    )
    
    # Stream retrieval progress
    yield {"status": "retrieving", "breakdown": breakdown}
    
    # Retrieve docs
    docs = await assistant._retrieve_from_data_sources(breakdown, {})
    
    # Stream final response
    yield {"status": "composing", "docs_count": len(docs)}
    
    # Compose and stream
    response = await assistant._compose_response(...)
    yield {"status": "complete", "response": response}
```

## TSC Hierarchy (Compliance Assistant)

The Compliance Assistant uses the TSC (Trust Service Criteria) hierarchy:

```
Framework (SOC2, HIPAA, GDPR)
  ↓
Trust Service Criteria (Privacy, Security, etc.)
  ↓
Control Objective
  ↓
Control
  ↓
Policy / Standard
  ↓
Procedure
  ↓
Evidence
```

Responses are structured according to this hierarchy for clarity.

## Best Practices

1. **Always provide available lists**: Pass `available_products`, `available_frameworks`, etc. for better context
2. **Use category filtering**: Configure data sources with specific categories for faster retrieval
3. **Enable web search selectively**: Enable web search only when external docs are needed
4. **Choose output format wisely**: Use `summary` for end-user display, `json` for downstream processing
5. **Custom retrieval functions**: Provide custom retrieval functions for specialized data sources
6. **Cache assistants**: Create assistant instances once and reuse them

## Troubleshooting

### Slow Queries
- Reduce `max_edges` in configuration
- Use category filtering on data sources
- Disable web search if not needed
- Implement caching for retrieved docs

### Irrelevant Results
- Check context breakdown output
- Adjust system prompt templates
- Review data source priorities
- Add more specific metadata filters

### Missing Information
- Enable web search
- Add more data sources
- Increase `max_edges`
- Check category filtering isn't too restrictive

## Future Enhancements

### User Actions Assistant (Placeholder)
A fourth assistant for user action tracking is planned:

```python
# Future implementation
from app.assistants.workforce_assistants import create_user_actions_assistant

assistant = create_user_actions_assistant()
result = await assistant.process_query(
    user_question="What actions did user X perform on product Y?",
    available_products=["Snyk"],
    available_actors=["Compliance Officer"],
    time_range="last_30_days"
)
```

## Related Documentation

- [Contextual Agents](../agents/contextual_agents/README.md) - Context breakdown and edge pruning agents
- [Data Assistance Nodes](./data_assistance_nodes.py) - Integration with data retrieval
- [Knowledge Assistance Nodes](./knowledge_assistance_nodes.py) - Integration with knowledge graph
- [Design Workforce](../../docs/Design_assistance_workforce.md) - Original design document
