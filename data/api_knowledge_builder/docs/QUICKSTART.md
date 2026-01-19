# Quick Start Guide - API to MDL Converter

## Installation

```bash
# Install required dependency
pip install requests
```

## Files Overview

**Core Classes** (use these separately):
- `openapi_parser.py` - OpenAPI spec parser
- `mdl_builder.py` - MDL schema builder  
- `api_to_mdl_converter.py` - Main converter

**Test & Examples**:
- `test_converter.py` - Comprehensive test suite
- `real_api_converter.py` - Real-world API examples
- `example_usage.py` - Simple usage example

**Documentation**:
- `README.md` - Full documentation
- `requirements.txt` - Dependencies

## 1-Minute Quick Start

### Convert a local OpenAPI spec:

```python
from api_to_mdl_converter import APIToMDLConverter

# Load and convert
converter = APIToMDLConverter.from_file('your_openapi.json')
mdl = converter.convert()
converter.save('output_mdl.json')
```

### Run the example:

```bash
python example_usage.py
```

This creates a sample OpenAPI spec and converts it to MDL.

## Test the Converter

```bash
# Run all tests
python test_converter.py

# Run specific test
python test_converter.py basic
python test_converter.py relationships
```

## Convert Snyk API

```bash
# Option 1: Try direct conversion (may need auth)
python real_api_converter.py snyk

# Option 2: Manual download
# 1. Visit https://apidocs.snyk.io/?version=2024-10-15
# 2. Download OpenAPI spec JSON
# 3. Save as snyk_openapi.json
# 4. Run:
python example_usage.py snyk_openapi.json snyk_mdl.json
```

## LLM Enrichment Workflow

1. **Convert API to MDL**:
```python
converter = APIToMDLConverter.from_file('api_spec.json')
mdl = converter.convert()
converter.save('initial_mdl.json')
```

2. **Run enrichment demo**:
```bash
python test_converter.py enrichment
```

This creates `enrichment_template.json` with all columns that need descriptions.

3. **Use LLM** to enrich the template with:
   - Better descriptions
   - Data quality rules
   - Business context
   - Privacy classifications

4. **Update MDL** with enriched information

## Common Use Cases

### Filter specific schemas:
```python
mdl = converter.convert(
    filter_schemas=['User', 'Organization']
)
```

### Disable features:
```python
converter = APIToMDLConverter(
    spec,
    create_endpoint_views=False,
    infer_relationships=False
)
```

### Batch convert multiple APIs:
```python
from api_to_mdl_converter import BatchConverter

batch = BatchConverter(catalog="my_apis")
batch.add_from_file("users", "users_api.json")
batch.add_from_file("projects", "projects_api.json")
batch.convert_all()
batch.save_all(output_dir="mdl_schemas")
```

## Next Steps

1. Read `README.md` for comprehensive documentation
2. Check `test_converter.py` for more examples
3. Modify the classes to fit your specific needs
4. Use the LLM enrichment pattern to add business context

## Troubleshooting

**Import errors**: Make sure all 3 core files are in the same directory
**File not found**: Use absolute paths or check current directory
**API errors**: Some APIs require auth - download specs manually

## Need Help?

- Full docs: `README.md`
- Examples: `test_converter.py`
- Real APIs: `real_api_converter.py`
