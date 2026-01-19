# API Documentation Enhancement

This document explains how the converter uses API documentation from GET endpoints and associated API documentation URLs to enhance MDL generation.

## Overview

The converter now:
1. **Extracts API documentation** from each GET endpoint (summary, description, parameters, responses)
2. **Fetches associated API documentation** from provided URLs
3. **Uses this context** to enhance business context and properties in MDL tables

## Features

### 1. Endpoint Documentation Extraction

For each GET endpoint, the converter extracts:
- **Summary**: Brief description of the endpoint
- **Description**: Detailed description
- **Parameters**: Parameter names, types, descriptions
- **Responses**: Response descriptions and schemas
- **Tags**: Endpoint tags for categorization

This information is used to:
- Match endpoints to models based on path/tags
- Enhance model descriptions with endpoint context
- Add API endpoint metadata to model properties

### 2. Associated API Documentation

You can provide URLs to additional API documentation that will be:
- Fetched automatically
- Parsed (JSON or text)
- Included in the business context
- Used to enhance model descriptions and properties

## Usage

### Command Line

```bash
# With associated API documentation URLs
python real_api_converter.py \
    --input openapi.json \
    --output enhanced_mdl.json \
    --associated-docs \
        https://docs.example.com/api-guide \
        https://docs.example.com/authentication \
        https://docs.example.com/rate-limits

# From URL with associated docs
python real_api_converter.py \
    --input https://api.example.com/openapi.json \
    --output mdl.json \
    --associated-docs https://docs.example.com/getting-started

# Snyk API with associated docs
python real_api_converter.py \
    --api snyk \
    --version 2024-10-15 \
    --output snyk_mdl.json \
    --associated-docs https://docs.snyk.io/api
```

### Programmatic Usage

```python
from real_api_converter import RealAPIConverter
import asyncio

converter = RealAPIConverter(enable_agents=True)

# Convert with associated API docs
mdl = await converter.convert_spec_from_url(
    url="https://api.example.com/openapi.json",
    catalog="my_api",
    schema="public",
    output_file="output.json",
    associated_api_docs=[
        "https://docs.example.com/api-guide",
        "https://docs.example.com/authentication"
    ]
)
```

## How It Works

### Step 1: Extract Endpoint Documentation

For each GET endpoint, the converter extracts:

```python
{
    'path': '/api/v1/users',
    'method': 'GET',
    'operation_id': 'getUsers',
    'summary': 'Get list of users',
    'description': 'Retrieves a paginated list of all users...',
    'tags': ['users', 'authentication'],
    'parameters': [
        {
            'name': 'page',
            'in': 'query',
            'description': 'Page number',
            'required': False
        }
    ],
    'responses': {
        '200': {
            'description': 'List of users',
            'content': {...}
        }
    }
}
```

### Step 2: Fetch Associated Documentation

If `--associated-docs` URLs are provided:

1. Each URL is fetched using the same session (with auth if configured)
2. Content is parsed as JSON if possible, otherwise as text
3. Content is stored and included in context

### Step 3: Match Endpoints to Models

The converter matches endpoints to models by:
- **Path matching**: Model name appears in endpoint path
- **Tag matching**: Model name appears in endpoint tags
- **Response schema**: Model matches response schema

### Step 4: Enhance Business Context

The extracted documentation is used to:

1. **Enhance Domain Context**:
   - Add endpoint summaries to purpose
   - Extract business concepts from tags
   - Include associated doc URLs

2. **Enhance Model Descriptions**:
   - Add endpoint summaries and descriptions
   - Include parameter information
   - Add associated documentation context

3. **Add Model Properties**:
   - `api_endpoints`: JSON array of related endpoints
   - `associated_api_docs`: List of associated doc URLs

## Example Output

### Enhanced Model Properties

```json
{
  "name": "User",
  "description": "User account information...",
  "properties": {
    "display_name": "User Information",
    "business_purpose": "Stores user account data...",
    "api_endpoints": "[{\"path\":\"/api/v1/users\",\"method\":\"GET\",\"summary\":\"Get list of users\"}]",
    "associated_api_docs": "[\"https://docs.example.com/api-guide\"]"
  }
}
```

### Enhanced Domain Context

The domain context includes:
- Endpoint summaries in the purpose
- Business concepts extracted from endpoint tags
- References to associated documentation

## Benefits

1. **Richer Business Context**: API documentation provides real-world context
2. **Better Descriptions**: Endpoint descriptions enhance model descriptions
3. **Additional Properties**: API endpoint metadata stored in model properties
4. **Tag-based Concepts**: Business concepts extracted from endpoint tags
5. **Associated Context**: External documentation adds depth

## Best Practices

1. **Provide Relevant Docs**: Only include documentation URLs that are relevant to the API
2. **Use Official Docs**: Prefer official API documentation over third-party sources
3. **Limit URLs**: Too many URLs may slow processing (recommended: 3-5 URLs)
4. **Ensure Accessibility**: Make sure URLs are publicly accessible or use API token

## Troubleshooting

### Associated Docs Not Loading

- Check URL accessibility
- Verify network connectivity
- Check if authentication is required
- Review error messages in console

### Endpoints Not Matching Models

- Check endpoint paths and tags
- Verify model names match patterns
- Review extracted endpoint documentation

### Large Documentation Files

- Associated docs are truncated to 2000 characters per URL
- Consider using documentation summaries instead of full docs
- Use specific documentation pages rather than index pages

