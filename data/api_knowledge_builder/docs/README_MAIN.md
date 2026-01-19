# Real API Converter - Main Entry Point

`real_api_converter.py` is now the **main entry point** for converting OpenAPI specifications to enhanced MDL schemas.

## Overview

This script:
1. **Fetches OpenAPI specs** from URLs, files, or known APIs (e.g., Snyk)
2. **Converts to MDL** using `api_to_mdl_converter.py`
3. **Enhances with agents** for semantic descriptions, documentation, and relationships
4. **Filters GET endpoints** by default (configurable)

## Key Features

- ✅ **Better API Integration**: Handles authentication, versioning, and known APIs
- ✅ **Uses api_to_mdl_converter.py**: Core conversion logic is in the converter
- ✅ **Agent Enhancements**: Optional semantic descriptions, documentation, relationships
- ✅ **Flexible Input**: URLs, files, or known APIs
- ✅ **GET Endpoint Filtering**: Processes GET endpoints only by default

## Usage

### From URL

```bash
python real_api_converter.py \
    --input https://api.example.com/openapi.json \
    --output enhanced_mdl.json
```

### From File

```bash
python real_api_converter.py \
    --input openapi.json \
    --output enhanced_mdl.json
```

### From Known API (Snyk)

```bash
python real_api_converter.py \
    --api snyk \
    --version 2024-10-15 \
    --output snyk_mdl.json
```

### With API Token

```bash
python real_api_converter.py \
    --input https://api.example.com/openapi.json \
    --api-token YOUR_TOKEN \
    --output enhanced_mdl.json
```

### Without Agent Enhancements (Faster)

```bash
python real_api_converter.py \
    --input openapi.json \
    --output basic_mdl.json \
    --no-agents
```

### All HTTP Methods

```bash
python real_api_converter.py \
    --input openapi.json \
    --output all_methods_mdl.json \
    --all-methods
```

## Command Line Options

### Input (choose one)
- `--input`: OpenAPI specification file path or URL
- `--api`: Use a known API (`snyk`)

### Output
- `--output` (required): Output MDL JSON file path

### API Configuration
- `--api-token`: API token for authenticated endpoints
- `--version`: API version (for APIs that support versioning)

### MDL Configuration
- `--catalog`: MDL catalog name (default: `api`)
- `--schema`: MDL schema name (default: `public`)
- `--domain-id`: Domain identifier (default: `api`)
- `--domain-name`: Domain display name (default: `API Data`)

### Processing Options
- `--no-agents`: Disable agent-based enhancements (faster)
- `--all-methods`: Process all HTTP methods, not just GET
- `--indent`: JSON indentation (default: 2)

## Architecture

```
real_api_converter.py (Main Entry Point)
    │
    ├── Fetches OpenAPI spec (URL/File/Known API)
    │
    ├── Calls api_to_mdl_converter.py
    │   └── Converts OpenAPI → MDL
    │
    └── Enhances with agents (if enabled)
        ├── Semantic descriptions
        ├── Schema documentation
        └── Relationship recommendations
```

## Programmatic Usage

```python
from real_api_converter import RealAPIConverter
import asyncio

# Initialize converter
converter = RealAPIConverter(
    api_token="your_token",  # optional
    enable_agents=True,      # enable agent enhancements
    domain_id="my_api",
    domain_name="My API"
)

# Convert from URL
mdl = await converter.convert_spec_from_url(
    url="https://api.example.com/openapi.json",
    catalog="my_catalog",
    schema="public",
    output_file="output.json",
    filter_get_only=True
)

# Convert from file
mdl = await converter.convert_spec_from_file(
    filepath="openapi.json",
    catalog="my_catalog",
    schema="public",
    output_file="output.json",
    filter_get_only=True
)

# Convert known API (Snyk)
mdl = await converter.convert_snyk_api(
    version="2024-10-15",
    catalog="snyk",
    schema="rest_api",
    output_file="snyk_mdl.json",
    filter_get_only=True
)
```

## Known APIs

Currently supported:
- **Snyk**: `--api snyk --version 2024-10-15`

To add more known APIs, edit `KNOWN_SPECS` in `real_api_converter.py`:

```python
KNOWN_SPECS = {
    'snyk_rest': 'https://api.snyk.io/rest/openapi',
    'your_api': 'https://api.example.com/openapi.json',  # Add here
}
```

## Agent Enhancements

When `--no-agents` is NOT specified, the converter automatically:

1. **Semantic Descriptions**: Adds business context and semantic meaning
2. **Schema Documentation**: Generates comprehensive documentation
3. **Relationship Recommendations**: Suggests relationships between models
4. **MDL Validation**: Validates the final schema

## Output

The generated MDL includes:

- **Models**: API schemas converted to MDL models
- **Views**: API endpoints converted to MDL views (GET only by default)
- **Relationships**: Recommended relationships between models
- **Properties**: Enhanced metadata from agents

## Environment Setup

Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.0
```

Or set environment variables:

```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

## Comparison with generate_mdl_with_agents.py

| Feature | real_api_converter.py | generate_mdl_with_agents.py |
|---------|----------------------|----------------------------|
| Main Entry Point | ✅ Yes | ❌ No |
| API Integration | ✅ Better (auth, versioning) | ⚠️ Basic |
| Known APIs | ✅ Yes (Snyk, extensible) | ❌ No |
| Uses api_to_mdl_converter | ✅ Yes | ✅ Yes |
| Agent Enhancements | ✅ Yes | ✅ Yes |
| Command Line | ✅ Full featured | ✅ Full featured |

**Recommendation**: Use `real_api_converter.py` as the main entry point.

## Migration from generate_mdl_with_agents.py

If you were using `generate_mdl_with_agents.py`, switch to `real_api_converter.py`:

```bash
# Old
python generate_mdl_with_agents.py --input openapi.json --output mdl.json

# New (same command works!)
python real_api_converter.py --input openapi.json --output mdl.json
```

The command-line interface is compatible, but `real_api_converter.py` has better API integration features.

