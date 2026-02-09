# Comprehensive Indexing Service

A comprehensive indexing solution for API docs, help docs, product descriptions, schema definitions, and column metadata with support for ChromaDB and Qdrant, domain filtering, and pipeline integration.

## Features

- **Multi-Store Support**: Works with both ChromaDB and Qdrant vector stores
- **Domain Filtering**: Filter content by domain (e.g., "Assets")
- **Pipeline Integration**: Integrates with extraction pipelines:
  - Entities Extraction
  - Evidence Extraction
  - Fields Extraction
  - Metadata Generation
  - Pattern Recognition
- **Content Types**: Indexes various content types:
  - API Documentation
  - Help Documentation
  - Product Descriptions
  - Table Definitions
  - Column Definitions
  - Schema Descriptions
  - Domain Knowledge

## Installation

The service uses existing dependencies from the knowledge app. Ensure you have:

```bash
pip install langchain-openai chromadb
# For Qdrant support:
pip install qdrant-client langchain-qdrant
```

## Quick Start

### Basic Usage

```python
import asyncio
from app.indexing import ComprehensiveIndexingService
from app.core.dependencies import (
    get_chromadb_client,
    get_embeddings_model,
    get_llm
)

async def main():
    # Initialize service using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm
    )
    
    # Index API docs
    await service.index_api_docs(
        api_docs="Your API documentation here",
        product_name="My Product",
        domain="Assets"
    )
    
    # Search
    results = await service.search(
        query="What are the asset tables?",
        domain="Assets",
        k=5
    )

asyncio.run(main())
```

### Indexing Schema from MDL

```python
import json
from pathlib import Path

# Load MDL file
with open("snyk_mdl1.json", "r") as f:
    mdl_data = json.load(f)

# Index schema (uses TableDescription structure by default)
result = await service.index_schema_from_mdl(
    mdl_data=mdl_data,
    product_name="Snyk",
    domain="Assets",
    use_table_description_structure=True  # Uses table_description.py structure
)

# The result includes:
# - tables_indexed: Number of tables indexed
# - columns_indexed: Number of columns indexed
# - table_descriptions_indexed: Number of table descriptions using TableDescription structure
```

**TableDescription Structure**: When `use_table_description_structure=True` (default), the service stores table descriptions using the same structure as `table_description.py`:
- Document format: `{name, mdl_type, type: "TABLE_DESCRIPTION", description, columns, relationships}`
- Metadata includes: `type`, `mdl_type`, `name`, `description`, `relationships`, `project_id`
- Stored in `table_descriptions` collection for easy retrieval

### Using Domain Configurations

```python
from app.indexing.domain_config import get_assets_domain_config

# Get Assets domain configuration
assets_config = get_assets_domain_config()

# Index example schema
if assets_config.example_schema:
    await service.index_table_definition(
        table_name=assets_config.example_schema.table_name,
        columns=assets_config.example_schema.columns,
        description=assets_config.example_schema.description,
        product_name="Assets Management",
        domain="Assets"
    )
```

### Indexing Compliance Documents

Index SOC2 controls, policy documents, and risk controls with automatic extraction using pipelines.

```python
# Index policy document (PDF)
await service.index_policy_document(
    file_path="path/to/Full Policy Packet.pdf",
    domain="compliance",
    metadata={"document_category": "policy"}
)

# Index risk controls (Excel)
await service.index_risk_controls(
    file_path="path/to/Risk and Controls.xlsx",
    domain="compliance",
    metadata={"document_category": "risk_controls"}
)

# Index SOC2 controls (PDF or Excel)
await service.index_soc2_controls(
    file_path="path/to/SOC2_Controls.pdf",
    domain="compliance",
    metadata={"document_category": "soc2_controls"}
)
```

The compliance document processor automatically:
- Extracts context information (industry, organization size, regulatory frameworks)
- Extracts controls with control IDs, descriptions, and frameworks
- Extracts entities (policies, requirements, controls, procedures)
- Extracts requirements and evidence
- Creates structured documents for search and retrieval

### Indexing Product Information

Index comprehensive product information including purpose, documentation links, key concepts, and extendable entities.

```python
# Index product information for Snyk
await service.index_product_info(
    product_name="Snyk",
    product_purpose="Snyk is a developer security platform that helps organizations find and fix vulnerabilities...",
    product_docs_link="https://docs.snyk.io",
    key_concepts=[
        "Vulnerability Scanning",
        "Dependency Management",
        "Container Security",
        "Infrastructure as Code Security"
    ],
    extendable_entities=[
        {
            "name": "Projects",
            "type": "entity",
            "description": "Projects represent applications monitored by Snyk",
            "api": "https://api.snyk.io/v1/orgs/{orgId}/projects",
            "endpoints": ["GET /orgs/{orgId}/projects", "POST /orgs/{orgId}/projects"],
            "examples": [{"name": "my-app", "type": "npm"}]
        }
    ],
    extendable_docs=[
        {
            "title": "Getting Started",
            "type": "getting_started",
            "link": "https://docs.snyk.io/getting-started",
            "description": "Learn how to get started with Snyk",
            "sections": ["Creating an account", "Connecting projects"],
            "content": "Snyk helps you find and fix vulnerabilities..."
        }
    ],
    domain="Security"
)
```

Or use a dictionary:

```python
from indexing_examples.snyk_product_config import get_snyk_product_config

# Get Snyk product configuration
snyk_config = get_snyk_product_config()

# Index using dictionary
await service.index_product_from_dict(
    product_data=snyk_config,
    domain="Security"
)
```

## Domain Configuration

### Assets Domain Example

The Assets domain includes:

- **Example Schema**: `assets` table with columns for asset tracking
- **Example Use Cases**: Asset inventory management, lifecycle tracking, compliance
- **Additional Schemas**: `asset_assignments`, `asset_maintenance`

### Creating Custom Domains

```python
from app.indexing.domain_config import DomainConfig, DomainSchema, DomainUseCase

# Create domain schema
schema = DomainSchema(
    table_name="my_table",
    columns=[...],
    description="Table description",
    primary_key="id"
)

# Create use case
use_case = DomainUseCase(
    name="My Use Case",
    description="Use case description",
    example_queries=["SELECT * FROM my_table"],
    business_value="Business value description"
)

# Create domain config
domain_config = DomainConfig(
    domain_name="MyDomain",
    description="Domain description",
    schemas=[schema],
    use_cases=[use_case],
    example_schema=schema,
    example_use_case=use_case
)
```

## Search Capabilities

### Basic Search

```python
results = await service.search(
    query="What are the asset tables?",
    k=5
)
```

### Domain-Filtered Search

```python
results = await service.search(
    query="asset management",
    domain="Assets",
    k=5
)
```

### Content Type Filtering

```python
results = await service.search(
    query="API endpoints",
    content_types=["api_doc"],
    k=5
)
```

### Search Types

- `semantic`: Semantic similarity search (default)
- `bm25`: BM25 ranking combined with semantic search
- `tfidf`: TF-IDF combined with semantic search
- `tfidf_only`: TF-IDF only search

## Pipeline Integration

The service automatically processes documents through extraction pipelines:

- **Entities Extraction**: Extracts entities and relationships
- **Fields Extraction**: Extracts field definitions
- **Evidence Extraction**: Creates evidence documents (for compliance domains)
- **Metadata Generation**: Generates metadata entries
- **Pattern Recognition**: Recognizes patterns (optional)

## Vector Store Configuration

### ChromaDB (Default)

```python
service = ComprehensiveIndexingService(
    vector_store_type="chroma",
    persistent_client=get_chromadb_client()
)
```

### Qdrant

```python
from qdrant_client import QdrantClient

qdrant_client = QdrantClient(host="localhost", port=6333)
service = ComprehensiveIndexingService(
    vector_store_type="qdrant",
    qdrant_client=qdrant_client
)
```

## Processor Classes

The indexing service uses separate processor classes for different content types:

### TableDescriptionProcessor

Processes table descriptions from MDL using the TableDescription structure.

```python
from app.indexing.processors import TableDescriptionProcessor

processor = TableDescriptionProcessor()
documents = await processor.process_mdl(
    mdl=mdl_dict,
    project_id="my_project",
    product_name="My Product",
    domain="Assets"
)
```

**Methods:**
- `extract_table_descriptions(mdl)`: Extract table descriptions from MDL
- `create_documents(table_descriptions, ...)`: Create Document objects
- `process_mdl(mdl, ...)`: Full processing pipeline

### DBSchemaProcessor

Processes database schema from MDL using DBSchema structure.

```python
from app.indexing.processors import DBSchemaProcessor

processor = DBSchemaProcessor(column_batch_size=200)
documents = await processor.process_mdl(
    mdl=mdl_dict,
    project_id="my_project",
    product_name="My Product",
    domain="Assets"
)
```

**Methods:**
- `process_models(models, relationships)`: Preprocess models
- `convert_models_to_ddl_commands(...)`: Convert to DDL commands
- `convert_views_to_ddl_commands(views)`: Convert views
- `convert_metrics_to_ddl_commands(metrics)`: Convert metrics
- `create_documents(ddl_commands, ...)`: Create Document objects
- `process_mdl(mdl, ...)`: Full processing pipeline

### DomainProcessor

Processes domain-specific knowledge and configurations.

```python
from app.indexing.processors import DomainProcessor

processor = DomainProcessor()
documents = processor.process_domain_config(
    domain_config=assets_config,
    product_name="Assets Management"
)
```

**Methods:**
- `process_domain_config(domain_config, ...)`: Process domain configuration
- `process_domain_knowledge(knowledge, domain, ...)`: Process domain knowledge text

### ProductProcessor

Processes product-specific information including purpose, docs, key concepts, and entities.

```python
from app.indexing.processors import ProductProcessor

processor = ProductProcessor()
documents = processor.process_product_info(
    product_name="Snyk",
    product_purpose="Developer security platform...",
    product_docs_link="https://docs.snyk.io",
    key_concepts=["Vulnerability Scanning", "Container Security"],
    extendable_entities=[...],
    extendable_docs=[...]
)
```

**Methods:**
- `process_product_info(...)`: Process comprehensive product information
- `process_product_from_dict(product_data, ...)`: Process from dictionary
- `_create_product_purpose_document(...)`: Create purpose document
- `_create_product_docs_link_document(...)`: Create docs link document
- `_create_key_concepts_documents(...)`: Create key concepts documents
- `_create_extendable_entities_documents(...)`: Create entities documents
- `_create_extendable_docs_documents(...)`: Create docs documents

### ComplianceDocumentProcessor

Processes compliance documents (SOC2 controls, policies, risk controls) with extraction pipelines.

```python
from app.indexing.processors import ComplianceDocumentProcessor

processor = ComplianceDocumentProcessor(enable_extraction=True)
documents = await processor.process_pdf_document(
    pdf_path="path/to/policy.pdf",
    document_type="policy",
    domain="compliance"
)
```

**Methods:**
- `process_pdf_document(pdf_path, document_type, domain, metadata)`: Process PDF documents
- `process_excel_document(excel_path, document_type, sheet_name, domain, metadata)`: Process Excel documents
- `_process_policy_document(content, base_metadata)`: Process policy documents with extraction
- `_process_soc2_controls_document(content, base_metadata)`: Process SOC2 controls with extraction
- `_process_risk_controls_document(content, base_metadata)`: Process risk controls with extraction
- `_process_risk_controls_excel(df, content, base_metadata)`: Process risk controls from Excel
- `_process_soc2_controls_excel(df, content, base_metadata)`: Process SOC2 controls from Excel

**Extraction Pipelines Used:**
- **Context Extraction**: Extracts organizational context (industry, size, frameworks, maturity)
- **Control Extraction**: Extracts controls with IDs, descriptions, frameworks
- **Entity Extraction**: Extracts entities (policies, requirements, controls, procedures)
- **Evidence Extraction**: Extracts evidence requirements
- **Fields Extraction**: Extracts structured fields from documents
- **Requirement Extraction**: Extracts requirements from text sections

## API Reference

### ComprehensiveIndexingService

#### Methods

- `index_api_docs(api_docs, product_name, domain, metadata)`: Index API documentation
- `index_help_docs(help_docs, product_name, domain, metadata)`: Index help documentation
- `index_product_description(description, product_name, domain, metadata)`: Index product description
- `index_table_definition(table_name, columns, description, ...)`: Index table definition
- `index_column_definitions(table_name, columns, ...)`: Index column definitions
- `index_schema_from_mdl(mdl_data, product_name, domain, metadata)`: Index schema from MDL
- `index_db_schema_from_mdl(mdl_data, product_name, domain, metadata)`: Index DB schema from MDL
- `index_domain_knowledge(knowledge, domain, product_name, metadata)`: Index domain knowledge
- `index_domain_config(domain_config, product_name, metadata)`: Index domain configuration
- `index_product_info(product_name, product_purpose, product_docs_link, key_concepts, extendable_entities, extendable_docs, ...)`: Index comprehensive product information
- `index_product_from_dict(product_data, domain, metadata)`: Index product from dictionary
- `index_soc2_controls(file_path, domain, metadata)`: Index SOC2 controls from PDF or Excel
- `index_policy_document(file_path, domain, metadata)`: Index policy document from PDF
- `index_risk_controls(file_path, domain, metadata)`: Index risk controls from PDF or Excel
- `search(query, content_types, domain, product_name, k, search_type)`: Search indexed content
- `delete_by_domain(domain)`: Delete all documents for a domain

## Integration with project_reader.py

The indexing service can be used alongside `project_reader.py`:

```python
from agents.app.indexing.project_reader import ProjectReader
from app.indexing import ComprehensiveIndexingService

# Read project
reader = ProjectReader(base_path="../../data/sql_meta")
project_data = await reader.read_project("my_project")

# Index using comprehensive service
indexing_service = ComprehensiveIndexingService(...)

# Index tables from project
for table in project_data["tables"]:
    if "mdl" in table:
        await indexing_service.index_schema_from_mdl(
            mdl_data=table["mdl"],
            product_name=project_data["project_id"],
            domain="Assets"
        )
```

## Examples

See `integration_example.py` for complete examples including:

- Indexing Assets domain
- Indexing API docs
- Indexing MDL schemas
- Searching indexed content

## Error Handling

The service includes comprehensive error handling:

- Pipeline failures fall back to original documents
- Store errors are logged but don't stop processing
- Invalid documents are skipped with warnings

## Performance Considerations

- Use batch processing for large document sets
- Enable TF-IDF for better search quality (ChromaDB)
- Consider Qdrant for production deployments with high throughput
- Pipeline processing can be disabled for faster indexing

## License

Part of the FlowHarmonic AI knowledge management system.

