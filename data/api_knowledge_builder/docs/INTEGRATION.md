# Integration Guide: Real API Converter with Enhanced MDL Generation

This document explains how `real_api_converter.py` is integrated with the enhanced MDL generator that uses agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    generate_mdl_with_agents.py              │
│                  (Main Orchestrator)                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ RealAPIConv  │ │ Standalone  │ │   Agents    │
│    erter     │ │  Settings/   │ │             │
│              │ │ Dependencies │ │             │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        │               │               │
        └───────────────┼───────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Enhanced MDL    │
              │     Output       │
              └──────────────────┘
```

## Components

### 1. RealAPIConverter (`real_api_converter.py`)

Handles fetching and loading OpenAPI specifications from:
- URLs (with optional authentication)
- Local files
- Known APIs (e.g., Snyk)

**Key Methods:**
- `fetch_spec(url, version, headers)` - Fetch OpenAPI spec from URL
- `convert_spec_from_url()` - Fetch and convert in one step
- `convert_snyk_api()` - Specialized Snyk API converter

### 2. Standalone Settings (`standalone_settings.py`)

Independent settings management that:
- Loads from environment variables or `.env` file
- Provides OpenAI API key configuration
- Configures LLM and embedding models
- Works without requiring the full dataservices infrastructure

**Key Features:**
- Environment variable support
- `.env` file support
- Validation of API keys
- Caching for performance

### 3. Standalone Dependencies (`standalone_dependencies.py`)

Provides LLM and embedding instances:
- `get_llm()` - Returns cached ChatOpenAI instance
- `get_embeddings()` - Returns cached OpenAIEmbeddings instance
- Works independently of dataservices dependencies

### 4. Enhanced MDL Generator (`generate_mdl_with_agents.py`)

Main orchestrator that:
1. Uses `RealAPIConverter` to load OpenAPI specs
2. Uses standalone settings/dependencies for LLM calls
3. Integrates with agents for enhancement
4. Generates final enhanced MDL

## Integration Flow

### Step 1: Load OpenAPI Specification

```python
# Option A: From URL
generator = EnhancedAPIToMDLGenerator(...)
mdl = await generator.generate_enhanced_mdl(
    openapi_url="https://api.example.com/openapi.json",
    api_token="your_token"  # optional
)

# Option B: From File
mdl = await generator.generate_enhanced_mdl(
    openapi_file="openapi.json"
)

# Option C: From Known API
mdl = await generator.generate_enhanced_mdl(
    openapi_url=RealAPIConverter.KNOWN_SPECS['snyk_rest'],
    version="2024-10-15"
)
```

### Step 2: Agent Enhancement

The generator automatically:
1. Converts OpenAPI to initial MDL
2. Enhances with semantic descriptions
3. Adds schema documentation
4. Recommends relationships
5. Validates the schema

### Step 3: Output

Generates enhanced MDL JSON with all agent enhancements.

## Usage Examples

### Command Line

```bash
# From URL
python generate_mdl_with_agents.py \
    --input https://api.example.com/openapi.json \
    --output enhanced_mdl.json

# From Known API
python generate_mdl_with_agents.py \
    --api snyk \
    --version 2024-10-15 \
    --output snyk_mdl.json

# With Authentication
python generate_mdl_with_agents.py \
    --input https://api.example.com/openapi.json \
    --api-token YOUR_TOKEN \
    --output enhanced_mdl.json
```

### Programmatic

```python
from generate_mdl_with_agents import EnhancedAPIToMDLGenerator
from real_api_converter import RealAPIConverter

# Initialize
generator = EnhancedAPIToMDLGenerator(
    domain_id="my_api",
    domain_name="My API Integration"
)

# Load and convert
real_converter = RealAPIConverter(api_token="your_token")
openapi_spec = real_converter.fetch_spec("https://api.example.com/openapi.json")

# Generate enhanced MDL
mdl = await generator.generate_enhanced_mdl(
    openapi_spec=openapi_spec,
    filter_get_only=True
)
```

## Configuration

### Environment Variables

Create `.env` file:

```bash
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.0
EMBEDDING_MODEL=text-embedding-3-small
```

### Settings Override

You can override settings programmatically:

```python
from standalone_settings import get_settings, init_environment
import os

# Override before initialization
os.environ["OPENAI_API_KEY"] = "your_key"
os.environ["LLM_MODEL"] = "gpt-4"

# Initialize
init_environment()
```

## Benefits of Standalone Approach

1. **Independence**: Works without full dataservices infrastructure
2. **Portability**: Can be run as standalone script
3. **Simplicity**: Minimal dependencies
4. **Flexibility**: Easy to configure and customize
5. **Compatibility**: Still integrates with dataservices agents

## Extending

### Adding New Known APIs

Edit `real_api_converter.py`:

```python
KNOWN_SPECS = {
    'snyk_rest': 'https://api.snyk.io/rest/openapi',
    'your_api': 'https://api.example.com/openapi.json',  # Add here
}
```

### Custom Settings

Extend `standalone_settings.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Add your custom settings
    CUSTOM_SETTING: str = "default_value"
```

### Custom Dependencies

Extend `standalone_dependencies.py`:

```python
def get_custom_service():
    """Get your custom service"""
    settings = get_settings()
    # Initialize your service
    return CustomService(settings.CUSTOM_SETTING)
```

## Troubleshooting

### API Key Issues

```bash
# Check if API key is set
python -c "from standalone_settings import get_settings; print(get_settings().OPENAI_API_KEY[:10])"

# Set in environment
export OPENAI_API_KEY=sk-...
```

### Import Errors

Make sure paths are correct:
- `standalone_settings.py` and `standalone_dependencies.py` are in same directory
- `dataservices` directory is accessible for agent imports

### Network Issues

For authenticated APIs:
- Check API token is valid
- Verify network connectivity
- Check API endpoint is accessible

