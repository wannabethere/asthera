# Vector Store Metadata Guide

This document describes all available vector stores, their purpose, data structure, and when to use each store. The stores are organized by umbrella concepts for easy navigation.

## Table of Contents

1. [Compliance & Policies](#compliance--policies)
2. [Risk Management](#risk-management)
3. [Controls](#controls)
4. [Schema & Database](#schema--database)
5. [Products & Connectors](#products--connectors)
6. [General Purpose Stores](#general-purpose-stores)
7. [Contextual Graph](#contextual-graph)

---

## Compliance & Policies

### `compliance_controls`

**Description**: Stores compliance control definitions from various frameworks (SOC2, HIPAA, ISO 27001, GDPR, NIST, PCI-DSS, etc.). All frameworks are stored in a single collection with framework information in metadata.

**Data Stored**:
- Control definitions from compliance frameworks
- Control IDs, names, descriptions
- Framework-specific requirements
- Implementation guidance
- Evidence types needed

**Metadata Filtering**:
- `framework`: Framework name (e.g., "SOC2", "HIPAA", "ISO 27001")
- `domain`: Domain filter (typically "compliance")
- `extraction_type`: Usually "control"
- `type`: Not typically set (framework distinguishes it)

**When to Use**:
- Searching for specific compliance controls by framework
- Finding controls that meet certain requirements
- Understanding framework-specific control definitions
- Compliance mapping and gap analysis

**Example Queries**:
- "Find all SOC2 controls related to access management"
- "What HIPAA controls require encryption?"
- "List ISO 27001 controls for incident response"

---

### `domain_knowledge` (with `type="policy"`)

**Description**: Stores policy documents, policy context, and policy requirements. All policy-related content is consolidated into this general store with `type="policy"` in metadata.

**Data Stored**:
- Full policy documents (PDF content)
- Policy context definitions
- Policy requirements
- Policy descriptions and summaries
- Framework information in metadata

**Metadata Filtering**:
- `type`: Must be `"policy"` to filter policy content
- `framework`: Framework name (e.g., "SOC2", "HIPAA", "ISO 27001")
- `extraction_type`: "context", "requirement", "full_content"
- `domain`: Domain filter (typically "compliance")

**When to Use**:
- Searching for policy documents by framework
- Finding policy requirements
- Understanding policy context
- Policy compliance analysis

**Example Queries**:
- "What are the access control policies for SOC2?"
- "Find policy requirements related to data encryption"
- "What is the context for HIPAA privacy policies?"

---

## Risk Management

### `domain_knowledge` (with `type="risk"` or `type="risk_*"`)

**Description**: Stores risk control documents, risk context, and risk requirements. Risk-related content is stored in the general `domain_knowledge` store with various `type` values.

**Data Stored**:
- Risk control definitions
- Risk assessment data
- Risk context and descriptions
- Risk requirements
- Base row data from risk control spreadsheets

**Metadata Filtering**:
- `type`: 
  - `"risk"` - General risk documents
  - `"risk_base"` - Base row data from risk controls
  - `"risk_requirements"` - Risk requirements
  - `"risk_context"` - Risk context
- `framework`: Framework name (e.g., "SOC2", "HIPAA", "Risk Management")
- `extraction_type`: "base", "requirements", "context"
- `domain`: Domain filter (typically "compliance")

**When to Use**:
- Searching for risk controls by framework
- Finding risk assessment information
- Understanding risk context
- Risk management analysis

**Example Queries**:
- "What are the risk controls for SOC2 compliance?"
- "Find risk assessments related to data breaches"
- "What is the risk context for access management?"

---

## Controls

### `controls` (General Controls Store)

**Description**: Unified store for all types of controls (policy controls, risk controls, compliance controls). Distinguished by `type` metadata.

**Data Stored**:
- Policy controls (with `type="policy"`)
- Risk controls (with `type="risk_control"`)
- Compliance controls (with `type="compliance"` or framework in metadata)
- Control definitions, IDs, names, descriptions
- Control requirements and evidence types

**Metadata Filtering**:
- `type`: 
  - `"policy"` - Policy-related controls
  - `"risk_control"` - Risk management controls
  - `"compliance"` - Compliance controls (or use framework)
- `framework`: Framework name for compliance controls
- `extraction_type`: Usually "control"
- `domain`: Domain filter

**When to Use**:
- Searching across all control types
- Finding controls regardless of source (policy, risk, compliance)
- Unified control search and analysis
- Control mapping across different sources

**Example Queries**:
- "Find all controls related to access management"
- "What controls require encryption evidence?"
- "List controls that apply to data storage"

---

## Schema & Database

### `table_definitions`

**Description**: Stores table structure definitions including column information, data types, and table metadata.

**Data Stored**:
- Table names and schemas
- Column definitions (name, type, description)
- Table properties and constraints
- Column counts and structure information
- Product and domain associations

**Metadata Filtering**:
- `table_name`: Specific table name
- `schema`: Schema name
- `product_name`: Product/application name
- `domain`: Domain filter
- `content_type`: "table_definition"

**When to Use**:
- Finding table structures by name
- Understanding database schema
- Column-level searches
- Schema documentation

**Example Queries**:
- "What is the structure of the users table?"
- "Find all tables in the compliance schema"
- "What columns are in the audit_log table?"

---

### `table_descriptions`

**Description**: Stores detailed table descriptions using the TableDescription structure. Used by project_reader.py for schema understanding.

**Data Stored**:
- Table descriptions and purpose
- Business context for tables
- Table relationships
- Usage patterns
- Category information

**Metadata Filtering**:
- `table_name`: Specific table name
- `product_name`: Product/application name
- `domain`: Domain filter
- `category`: Table category

**When to Use**:
- Understanding what a table is used for
- Finding tables by business purpose
- Schema documentation and understanding
- Category-based table discovery

**Example Queries**:
- "What tables are used for user authentication?"
- "Find tables related to compliance tracking"
- "What is the purpose of the audit_log table?"

---

### `column_definitions` (stored as `column_metadata`)

**Description**: Stores individual column definitions with detailed metadata. Used by project_reader.py for column-level understanding.

**Data Stored**:
- Column names and data types
- Column descriptions
- Column properties and constraints
- Table associations
- Data type information

**Metadata Filtering**:
- `column_name`: Specific column name
- `table_name`: Parent table name
- `data_type`: Column data type
- `product_name`: Product/application name
- `domain`: Domain filter

**When to Use**:
- Finding columns by name or type
- Understanding column properties
- Data type analysis
- Column-level documentation

**Example Queries**:
- "Find all columns of type timestamp"
- "What columns contain user email addresses?"
- "List all columns in the users table"

---

### `schema_descriptions`

**Description**: Stores schema-level descriptions and metadata about entire database schemas.

**Data Stored**:
- Schema names and catalogs
- Model counts (tables, enums, metrics, views)
- Schema-level documentation
- Schema properties

**Metadata Filtering**:
- `schema`: Schema name
- `product_name`: Product/application name
- `domain`: Domain filter

**When to Use**:
- Understanding overall schema structure
- Schema-level documentation
- Finding schemas by product

**Example Queries**:
- "What schemas exist in the compliance database?"
- "How many tables are in the main schema?"
- "What is the structure of the analytics schema?"

---

### `db_schema`

**Description**: Stores complete database schema documents in DBSchema format. Used for comprehensive schema understanding.

**Data Stored**:
- Complete schema definitions
- All tables, columns, relationships
- Schema metadata and properties
- Product and domain associations

**Metadata Filtering**:
- `product_name`: Product/application name
- `domain`: Domain filter
- `content_type`: "db_schema"

**When to Use**:
- Complete schema understanding
- Schema documentation
- Product-level schema analysis

**Example Queries**:
- "What is the complete schema for the compliance system?"
- "Show me all tables and relationships in the main database"

---

### `category_mapping`

**Description**: Stores category-based mappings of tables, grouping tables by business category for efficient discovery.

**Data Stored**:
- Category names and descriptions
- Lists of tables in each category
- Category-based table groupings
- Business context for categories

**Metadata Filtering**:
- `category`: Category name
- `product_name`: Product/application name
- `domain`: Domain filter

**When to Use**:
- Finding tables by business category
- Category-based schema discovery
- Understanding table groupings

**Example Queries**:
- "What tables are in the compliance category?"
- "Find all authentication-related tables"
- "What categories exist for the compliance system?"

---

## Products & Connectors

### `product_descriptions`

**Description**: Stores product descriptions and general product information.

**Data Stored**:
- Product names and descriptions
- Product purpose and capabilities
- Product metadata

**Metadata Filtering**:
- `product_name`: Product name
- `domain`: Domain filter
- `content_type`: "product_description"

**When to Use**:
- Finding product information
- Understanding product capabilities
- Product discovery

**Example Queries**:
- "What products are available for compliance?"
- "Describe the Snyk product"
- "What products support SOC2 compliance?"

---

### `domain_knowledge` (with `type="product"`)

**Description**: Stores product-specific knowledge including product purpose, documentation links, and extendable documentation.

**Data Stored**:
- Product purpose descriptions
- Product documentation links
- Extendable documentation references
- Product context and knowledge

**Metadata Filtering**:
- `type`: Must be `"product"` to filter product content
- `product_name`: Product name
- `content_type`: "product_purpose", "product_docs_link", "extendable_doc"
- `domain`: Domain filter

**When to Use**:
- Finding product purpose and documentation
- Understanding product capabilities
- Product knowledge base queries

**Example Queries**:
- "What is the purpose of the Snyk product?"
- "Where is the documentation for the compliance tool?"
- "What documentation is available for product integrations?"

---

### `entities` (with `type="product"`)

**Description**: Stores product-related entities including key concepts and extendable entities (APIs, integrations).

**Data Stored**:
- Product key concepts
- Extendable entities (APIs, integrations)
- Entity names, types, descriptions
- API endpoints and examples

**Metadata Filtering**:
- `type`: Must be `"product"` to filter product entities
- `product_name`: Product name
- `content_type`: "product_key_concepts", "product_key_concept", "extendable_entity"
- `entity_type`: Type of entity (e.g., "API", "integration")
- `domain`: Domain filter

**When to Use**:
- Finding product key concepts
- Discovering product APIs and integrations
- Understanding product entities

**Example Queries**:
- "What are the key concepts for the Snyk product?"
- "What APIs are available for the compliance tool?"
- "Find integration endpoints for product X"

---

## General Purpose Stores

### `entities` (General Entities Store)

**Description**: Unified store for all types of entities across different domains. Distinguished by `type` metadata.

**Data Stored**:
- Policy entities (with `type="policy"`)
- Product entities (with `type="product"`)
- Risk entities (with `type="risk_entities"`)
- Entity names, types, descriptions
- Entity relationships and properties

**Metadata Filtering**:
- `type`: 
  - `"policy"` - Policy-related entities
  - `"product"` - Product-related entities
  - `"risk_entities"` - Risk-related entities
- `extraction_type`: Usually "entities"
- `domain`: Domain filter
- `entity_type`: Type of entity

**When to Use**:
- Searching across all entity types
- Finding entities regardless of source
- Unified entity search
- Entity relationship analysis

**Example Queries**:
- "Find all entities related to access control"
- "What entities are mentioned in compliance policies?"
- "List all API entities across products"

---

### `evidence` (General Evidence Store)

**Description**: Unified store for all types of evidence across different domains. Distinguished by `type` metadata.

**Data Stored**:
- Policy evidence (with `type="policy"`)
- Risk evidence (with `type="risk_evidence"`)
- Evidence names, types, descriptions
- Evidence requirements and associations

**Metadata Filtering**:
- `type`: 
  - `"policy"` - Policy-related evidence
  - `"risk_evidence"` - Risk-related evidence
- `extraction_type`: Usually "evidence"
- `domain`: Domain filter
- `evidence_type`: Type of evidence

**When to Use**:
- Searching across all evidence types
- Finding evidence requirements
- Evidence mapping and analysis

**Example Queries**:
- "What evidence is required for access control?"
- "Find all evidence types for SOC2 compliance"
- "What evidence supports risk controls?"

---

### `fields` (General Fields Store)

**Description**: Unified store for all types of fields across different domains. Distinguished by `type` metadata.

**Data Stored**:
- Policy fields (with `type="policy"`)
- Risk fields (with `type="risk_fields"`)
- Field names, types, descriptions
- Field definitions and properties

**Metadata Filtering**:
- `type`: 
  - `"policy"` - Policy-related fields
  - `"risk_fields"` - Risk-related fields
- `extraction_type`: Usually "fields"
- `domain`: Domain filter
- `field_type`: Type of field

**When to Use**:
- Searching across all field types
- Finding field definitions
- Field mapping and analysis

**Example Queries**:
- "What fields are defined in compliance policies?"
- "Find all fields related to risk assessment"
- "What fields are required for access control?"

---

### `domain_knowledge` (General Domain Knowledge Store)

**Description**: Unified store for domain knowledge across different content types. Distinguished by `type` metadata.

**Data Stored**:
- Policy documents and context (with `type="policy"`)
- Product knowledge (with `type="product"`)
- Risk context and requirements (with `type="risk"` or `type="risk_*"`)
- Domain-specific knowledge and documentation

**Metadata Filtering**:
- `type`: 
  - `"policy"` - Policy-related knowledge
  - `"product"` - Product-related knowledge
  - `"risk"` - General risk knowledge
  - `"risk_base"` - Risk base data
  - `"risk_requirements"` - Risk requirements
  - `"risk_context"` - Risk context
- `extraction_type`: "context", "requirement", "full_content", "base"
- `domain`: Domain filter
- `framework`: Framework name (for policies and risks)

**When to Use**:
- Searching for domain knowledge across all types
- Finding context and requirements
- General knowledge base queries
- Cross-domain knowledge discovery

**Example Queries**:
- "What is the context for compliance requirements?"
- "Find knowledge about risk management"
- "What are the requirements for data protection?"

---

## Contextual Graph

### `context_definitions`

**Description**: Stores context definitions for the contextual graph system. Used for entity context and relationships.

**Data Stored**:
- Context IDs and names
- Context descriptions
- Context metadata
- Entity associations

**Metadata Filtering**:
- `context_id`: Context identifier
- `domain`: Domain filter
- `content_type`: "context_definitions"

**When to Use**:
- Finding context definitions
- Understanding entity contexts
- Contextual graph queries

**Example Queries**:
- "What contexts are defined for compliance?"
- "Find context definitions for access control"

---

### `contextual_edges`

**Description**: Stores edges/relationships in the contextual graph system.

**Data Stored**:
- Edge definitions
- Relationship types
- Source and target entities
- Edge properties

**Metadata Filtering**:
- `edge_type`: Type of edge/relationship
- `domain`: Domain filter
- `content_type`: "contextual_edges"

**When to Use**:
- Finding relationships between entities
- Understanding entity connections
- Graph traversal queries

**Example Queries**:
- "What entities are related to access control?"
- "Find all relationships for compliance controls"

---

### `control_context_profiles`

**Description**: Stores control context profiles linking controls to contexts in the contextual graph.

**Data Stored**:
- Control IDs
- Context associations
- Profile metadata
- Control-context relationships

**Metadata Filtering**:
- `control_id`: Control identifier
- `context_id`: Context identifier
- `domain`: Domain filter
- `content_type`: "control_context_profiles"

**When to Use**:
- Finding controls by context
- Understanding control-context relationships
- Context-based control discovery

**Example Queries**:
- "What controls apply to the access management context?"
- "Find control profiles for compliance contexts"

---

## Decision Guide: When to Pick What Store

### For Compliance & Policy Queries

1. **Specific Compliance Controls**: Use `compliance_controls` with `framework` filter
2. **Policy Documents**: Use `domain_knowledge` with `type="policy"` and `framework` filter
3. **Policy Requirements**: Use `domain_knowledge` with `type="policy"` and `extraction_type="requirement"`
4. **Policy Entities**: Use `entities` with `type="policy"`
5. **Policy Evidence**: Use `evidence` with `type="policy"`
6. **Policy Fields**: Use `fields` with `type="policy"`

### For Risk Management Queries

1. **Risk Controls**: Use `controls` with `type="risk_control"` or `domain_knowledge` with `type="risk"`
2. **Risk Context**: Use `domain_knowledge` with `type="risk_context"`
3. **Risk Requirements**: Use `domain_knowledge` with `type="risk_requirements"`
4. **Risk Entities**: Use `entities` with `type="risk_entities"`
5. **Risk Evidence**: Use `evidence` with `type="risk_evidence"`
6. **Risk Fields**: Use `fields` with `type="risk_fields"`

### For Schema & Database Queries

1. **Table Structures**: Use `table_definitions` with `table_name` filter
2. **Table Descriptions**: Use `table_descriptions` with `table_name` or `category` filter
3. **Column Definitions**: Use `column_definitions` with `column_name` or `table_name` filter
4. **Schema Overview**: Use `schema_descriptions` with `schema` filter
5. **Complete Schema**: Use `db_schema` with `product_name` filter
6. **Category-based Discovery**: Use `category_mapping` with `category` filter

### For Product & Connector Queries

1. **Product Information**: Use `product_descriptions` with `product_name` filter
2. **Product Purpose**: Use `domain_knowledge` with `type="product"` and `content_type="product_purpose"`
3. **Product Documentation**: Use `domain_knowledge` with `type="product"` and `content_type="product_docs_link"`
4. **Product Concepts**: Use `entities` with `type="product"` and `content_type="product_key_concepts"`
5. **Product APIs/Integrations**: Use `entities` with `type="product"` and `content_type="extendable_entity"`

### For Cross-Domain Queries

1. **All Controls**: Use `controls` (will include policy, risk, and compliance controls)
2. **All Entities**: Use `entities` (will include policy, product, and risk entities)
3. **All Evidence**: Use `evidence` (will include policy and risk evidence)
4. **All Fields**: Use `fields` (will include policy and risk fields)
5. **All Domain Knowledge**: Use `domain_knowledge` (will include policy, product, and risk knowledge)

### For Contextual Graph Queries

1. **Context Definitions**: Use `context_definitions`
2. **Entity Relationships**: Use `contextual_edges`
3. **Control-Context Links**: Use `control_context_profiles`

---

## Metadata Filtering Best Practices

### Always Filter by `type` for General Stores

When querying general stores (`entities`, `evidence`, `fields`, `controls`, `domain_knowledge`), always include a `type` filter to narrow results:

```python
where_clause = {
    "type": "policy",  # or "product", "risk_control", etc.
    "framework": "SOC2"  # if applicable
}
```

### Use `framework` for Compliance Content

For compliance-related queries, use the `framework` metadata:

```python
where_clause = {
    "framework": "SOC2",  # or "HIPAA", "ISO 27001", etc.
    "type": "policy"  # if querying general stores
}
```

### Combine Filters for Precision

Combine multiple metadata filters for precise results:

```python
where_clause = {
    "type": "risk_control",
    "framework": "SOC2",
    "domain": "compliance",
    "extraction_type": "control"
}
```

---

## Store Consolidation Strategy

The vector stores follow a consolidation strategy:

1. **General Stores**: `entities`, `evidence`, `fields`, `controls`, `domain_knowledge` are used for multiple content types, distinguished by `type` metadata
2. **Specialized Stores**: Schema stores (`table_definitions`, `column_definitions`, etc.) remain separate for performance and compatibility
3. **Compliance Store**: `compliance_controls` remains separate but uses `framework` metadata for filtering
4. **Metadata-Based Filtering**: All stores use metadata (`type`, `framework`, `domain`, etc.) for filtering rather than separate collections

This approach reduces the number of collections while maintaining query flexibility through metadata filtering.

