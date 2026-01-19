# Enhanced MDL Generation with Agents

This script integrates the API-to-MDL converter with intelligent agents to generate enhanced MDL schemas from OpenAPI specifications.

## Features

- ✅ Converts OpenAPI 3.x specifications to MDL format
- ✅ Filters for GET endpoints only (configurable)
- ✅ Enhances models with semantic descriptions
- ✅ Adds comprehensive schema documentation
- ✅ Recommends relationships between models
- ✅ Validates the final MDL schema

## Usage

### Basic Usage (GET endpoints only)

```bash
python generate_mdl_with_agents.py \
    --input openapi.json \
    --output enhanced_mdl.json
```

### From URL

```bash
python generate_mdl_with_agents.py \
    --input https://api.example.com/openapi.json \
    --output enhanced_mdl.json
```

### From Known APIs (Snyk)

```bash
python generate_mdl_with_agents.py \
    --api snyk \
    --version 2024-10-15 \
    --output snyk_enhanced_mdl.json
```

### With API Token

```bash
python generate_mdl_with_agents.py \
    --input https://api.example.com/openapi.json \
    --api-token YOUR_API_TOKEN \
    --output enhanced_mdl.json
```

### All HTTP Methods

```bash
python generate_mdl_with_agents.py \
    --input openapi.json \
    --output enhanced_mdl.json \
    --all-methods
```

### Custom Domain Configuration

```bash
python generate_mdl_with_agents.py \
    --input openapi.json \
    --output enhanced_mdl.json \
    --domain-id my_api \
    --domain-name "My API Integration" \
    --catalog my_catalog \
    --schema public
```

## Command Line Options

### Input Options (choose one)
- `--input`: OpenAPI specification file path or URL
- `--api`: Use a known API specification (e.g., `snyk`)

### Output Options
- `--output` (required): Output MDL JSON file path

### Configuration Options
- `--domain-id`: Domain identifier (default: `api`)
- `--domain-name`: Domain display name (default: `API Data`)
- `--catalog`: MDL catalog name (default: `api`)
- `--schema`: MDL schema name (default: `public`)
- `--all-methods`: Process all HTTP methods, not just GET (default: GET only)
- `--indent`: JSON indentation (default: 2)

### API Options
- `--api-token`: API token for authenticated endpoints
- `--version`: API version (for APIs that support versioning, e.g., Snyk)

## What the Script Does

1. **Parses OpenAPI Specification**: Loads and parses the OpenAPI spec from file or URL
2. **Filters Endpoints**: By default, only processes GET endpoints (can be disabled with `--all-methods`)
3. **Converts to MDL**: Creates initial MDL schema with models and views
4. **Enhances with Semantic Descriptions**: Uses `SemanticsDescription` agent to add business context
5. **Adds Schema Documentation**: Uses `LLMSchemaDocumentationGenerator` to add comprehensive documentation
6. **Recommends Relationships**: Uses `RelationshipRecommendation` agent to suggest relationships
7. **Validates Schema**: Validates the final MDL schema structure

## Output

The script generates an enhanced MDL JSON file with:

- **Models**: API schemas converted to MDL models with enhanced descriptions
- **Views**: API endpoints converted to MDL views (GET endpoints only by default)
- **Relationships**: Recommended relationships between models
- **Properties**: Enhanced metadata including:
  - Semantic descriptions
  - Business purpose
  - Primary use cases
  - Key relationships
  - Business context

## Example Output Structure

```json
{
  "catalog": "api",
  "schema": "public",
  "models": [
    {
      "name": "User",
      "description": "Enhanced description from semantic analysis",
      "columns": [...],
      "properties": {
        "display_name": "User Information",
        "business_purpose": "Stores user account information",
        "semantic_description": "...",
        "primary_use_cases": "user_management,authentication"
      }
    }
  ],
  "views": [
    {
      "name": "GET_users",
      "statement": "...",
      "properties": {...}
    }
  ],
  "relationships": [
    {
      "name": "User_Order",
      "models": ["User", "Order"],
      "joinType": "ONE_TO_MANY",
      "condition": "User.id = Order.user_id",
      "properties": {
        "explanation": "...",
        "business_value": "...",
        "confidence_score": "0.95"
      }
    }
  ]
}
```

## Requirements

- Python 3.8+
- Required packages (install via pip):
  - `requests` (for URL loading)
  - `langchain` and `langchain-openai` (for LLM integration)
  - `pydantic` and `pydantic-settings` (for settings)
  - `python-dotenv` (for environment variable loading)
  - All dependencies from `dataservices/app/` (agents, etc.)

## Environment Setup

Create a `.env` file in the `api_knowledge_builder` directory:

```bash
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.0
EMBEDDING_MODEL=text-embedding-3-small
```

Or set environment variables directly:

```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

## Environment Setup

Make sure you have:
1. Environment variables set (OPENAI_API_KEY, etc.)
2. All agent dependencies installed
3. Access to the `dataservices` directory for agent imports

## Troubleshooting

### Import Errors

If you get import errors, make sure:
- The script is run from the `data/api_knowledge_builder/` directory, OR
- The `dataservices` directory is accessible from the script location

### LLM Errors

If semantic enhancement fails:
- Check your OPENAI_API_KEY environment variable
- Verify network connectivity
- Check API rate limits

### No GET Endpoints Found

If no GET endpoints are found:
- Verify your OpenAPI spec has GET endpoints
- Use `--all-methods` to process all HTTP methods
- Check the OpenAPI spec structure

## Integration with Other Tools

The generated MDL can be used with:
- `table_description.py` for ChromaDB storage
- `schema_manager.py` for further processing
- `project_manager.py` for definition generation

