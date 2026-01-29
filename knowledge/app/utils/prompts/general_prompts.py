"""
General Prompts
General-purpose prompts and context breakdown rules used across the application.
"""

# Static rules for context breakdown
CONTEXT_BREAKDOWN_RULES = """
#### CONTEXT BREAKDOWN RULES ####
- **CRITICAL**: Only use entities that are explicitly defined in the available entities list. Never hallucinate or assume entities exist.
- **CRITICAL**: Always use exact entity names from the rules when identifying entities (e.g., "compliance_controls", not "compliance controls" or "controls").
- **CRITICAL**: For product queries (e.g., Snyk), first check schema_descriptions store to see available categories before querying specific tables.
- **CRITICAL**: Always include metadata filters (type, framework, product_name, etc.) when generating search questions.
- **CRITICAL**: For table relationships, use entity type "entity" (not "schema") and be more specific based on the topics in the question.
- Use natural language keywords from the original question when generating search questions.
- Make search questions specific enough to retrieve relevant documents from ChromaDB.
- Include context about what information is needed in the search question.
- Specify response types clearly (control definitions, evidence requirements, table structures, etc.).
"""

# Static instructions for context breakdown
CONTEXT_BREAKDOWN_INSTRUCTIONS = """
#### CONTEXT BREAKDOWN INSTRUCTIONS ####

For question/project ID context breakdown, you must:

1. **Identify Query Type**: Determine the type of query based on identified entities - MUST be one of:
   - "mdl" or "table_related" - if ANY SCHEMA & DATABASE entities are identified:
     * table_definitions, table_descriptions, column_definitions, schema_descriptions, db_schema, category_mapping
   - "policy" - if ANY policy-related entities are identified:
     * policy_documents, policy_entities, policy_evidence, policy_fields
   - "risk_control" - if ANY risk-related entities are identified:
     * risk_controls, risk_entities, risk_evidence, risk_fields
   - "compliance_framework" - if compliance_controls entity is identified:
     * compliance_controls (for SOC2, HIPAA, ISO 27001, GDPR, NIST 800-53, PCI-DSS frameworks)
   - "product" - if ANY product-related entities are identified:
     * product_descriptions, product_knowledge, product_entities
   - "unknown" - if the query type cannot be determined or no entities match the above categories

2. **Identify Entities**: Determine which entities from the rules above are relevant to the question
   - Only use entities from the available entities list
   - Use exact entity names (case-sensitive)
   - For product queries, check schema_descriptions first

3. **Generate Search Questions**: Create specific search questions for each identified entity that can be used to query ChromaDB
   - Use natural language keywords from the original question
   - Be specific enough to retrieve relevant documents
   - Include context about what information is needed
   - DO NOT use specific table names, entity IDs, or context_ids in filters (this is the first breakdown)

4. **Specify Response Types**: Define what type of information should be retrieved for each entity
   - Control definitions and requirements
   - Evidence requirements and examples
   - Table structures and relationships
   - Compliance framework mappings
   - Entity relationships and connections

5. **Include Metadata Filters**: Specify required metadata filters
   - Always use type filter for general stores (entities, evidence, fields, controls, domain_knowledge)
   - Use framework filter for compliance content (SOC2, HIPAA, etc.)
   - Use product_name filter for product-specific queries
   - DO NOT use context_id or specific table_name filters in first breakdown (use only after discovery)
"""

# Static entity summary markdown
AVAILABLE_ENTITIES_MARKDOWN = """## Available Entities

### COMPLIANCE & POLICY

| Entity | Store | Frameworks | Description |
|--------|-------|------------|------------|
| compliance_controls | compliance_controls | SOC2, HIPAA, ISO 27001, GDPR, NIST 800-53, PCI-DSS | Compliance control definitions with IDs, requirements, implementation guidance |
| policy_documents | domain_knowledge | policy | Policy documents, context, requirements (filter: type='policy') |
| policy_entities | entities | policy | Entities from policies: people, systems, processes (filter: type='policy', extraction_type='entities') |
| policy_evidence | evidence | policy | Evidence types from policies (filter: type='policy', extraction_type='evidence') |
| policy_fields | fields | policy | Fields/data from policies (filter: type='policy', extraction_type='fields') |
| risk_controls | domain_knowledge | Risk Management | Risk control documents, context, requirements (filter: type='risk_control') |
| risk_entities | entities | Risk Management | Entities from risk controls (filter: type='risk_entities', extraction_type='entities') |
| risk_evidence | evidence | Risk Management | Evidence from risk controls (filter: type='risk_evidence', extraction_type='evidence') |
| risk_fields | fields | Risk Management | Fields from risk controls (filter: type='risk_fields', extraction_type='fields') |
| controls_general | controls | - | Unified controls store (filter: type='policy'/'risk_control'/'compliance') |
| entities_general | entities | - | Unified entities store (filter: type='policy'/'product'/'risk_entities') |
| evidence_general | evidence | - | Unified evidence store (filter: type='policy'/'risk_evidence') |
| fields_general | fields | - | Unified fields store (filter: type='policy'/'risk_fields') |

### SCHEMA & DATABASE

| Entity | Store | Products | Description |
|--------|-------|----------|-------------|
| table_definitions | table_definitions | Snyk, Cornerstone | Table structure definitions with columns, data types, metadata |
| table_descriptions | table_descriptions | Snyk, Cornerstone | Table descriptions with business context, relationships, categories |
| column_definitions | column_definitions | Snyk, Cornerstone | Column definitions with names, types, descriptions, constraints |
| schema_descriptions | schema_descriptions | Snyk | Schema-level descriptions with categories (Snyk: access requests, assets, projects, vulnerabilities, etc.) |
| db_schema | db_schema | Snyk, Cornerstone | Complete database schema documents (DBSchema format) |
| category_mapping | category_mapping | Snyk, Cornerstone | Category-based table mappings for discovery |

### PRODUCT

| Entity | Store | Products | Description |
|--------|-------|----------|-------------|
| product_descriptions | product_descriptions | Snyk, Cornerstone | Product descriptions, purpose, capabilities |
| product_knowledge | domain_knowledge | Snyk, Cornerstone | Product knowledge, docs, extendable documentation (filter: type='product') |
| product_entities | entities | Snyk, Cornerstone | Product entities: key concepts, APIs, integrations (filter: type='product') |

### CONTEXTUAL GRAPH

| Entity | Store | Description |
|--------|-------|-------------|
| context_definitions | context_definitions | Context definitions for entities (query: context_id, domain) |
| contextual_edges | contextual_edges | Relationships between entities/evidence/fields/controls/context/schema (query: edge_type, source_entity_type, target_entity_type) |
| control_context_profiles | control_context_profiles | Control-context profile links (query: control_id, context_id) |
"""

# MDL-specific entity definitions
MDL_ENTITIES_MARKDOWN = """## MDL-Specific Entities

### SCHEMA & TABLE ENTITIES

| Entity | Store | Products | Description |
|--------|-------|----------|-------------|
| table_definitions | table_definitions | Snyk, Cornerstone | Table structure definitions with columns, data types, metadata |
| table_descriptions | table_descriptions | Snyk, Cornerstone | Table descriptions with business context, relationships, categories |
| column_definitions | column_definitions | Snyk, Cornerstone | Column definitions with names, types, descriptions, constraints |
| schema_descriptions | schema_descriptions | Snyk | Schema-level descriptions with categories (Snyk: access requests, assets, projects, vulnerabilities, etc.) |
| db_schema | db_schema | Snyk, Cornerstone | Complete database schema documents (DBSchema format) |
| category_mapping | category_mapping | Snyk, Cornerstone | Category-based table mappings for discovery |

### CONTEXTUAL GRAPH MDL ENTITIES

| Entity | Store | Description |
|--------|-------|-------------|
| table_contexts | context_definitions | Table entity contexts (query: context_id = entity_{{product}}_{{table}}) |
| table_relationships | contextual_edges | Table-to-table relationships (edge_type: BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.) |
| table_fields | fields | Table column fields (metadata: context_id = entity_{{product}}_{{table}}, type = schema_field) |
| table_compliance | contextual_edges | Table-to-compliance control relationships (edge_type: RELEVANT_TO_CONTROL) |

### MDL EDGE TYPES

| Edge Type | Description | Use Case |
|-----------|-------------|----------|
| BELONGS_TO_TABLE | Table belongs to another table (many-to-one) | AccessRequest belongs to Project |
| HAS_MANY_TABLES | Table has many related tables (one-to-many) | Project has many AccessRequests |
| REFERENCES_TABLE | Table references another table (one-to-one) | User references Profile |
| MANY_TO_MANY_TABLE | Many-to-many relationship | Users <-> Groups |
| LINKED_TO_TABLE | Tables are linked (general relationship) | Related tables without specific cardinality |
| RELATED_TO_TABLE | Tables are related (general relationship) | Fallback for any table relationship |
| RELEVANT_TO_CONTROL | Table is relevant to compliance control | AccessRequest relevant to SOC2 CC6.1 |
| HAS_FIELD | Table has field/column | AccessRequest has field 'requested_at' |
"""

# MDL-specific context breakdown instructions (for second step - MDL retrieval queries)
MDL_CONTEXT_BREAKDOWN_INSTRUCTIONS = """
#### MDL CONTEXT BREAKDOWN INSTRUCTIONS ####
(These instructions are for MDL retrieval queries AFTER the first breakdown identifies the query type as MDL)

For MDL semantic layer queries (when query_type is "mdl"), you must:

1. **Identify Schema Context**: Determine which schema entities are relevant
   - Check if query involves tables, columns, relationships, or categories
   - For product queries (Snyk, Cornerstone), first check schema_descriptions for categories
   - Use exact entity names from the available entities list
   - For table queries, construct context_id as: entity_{{product_name}}_{{table_name}} (ONLY after tables are discovered)

2. **Generate MDL-Specific Search Questions**: Create search questions that understand schema semantics
   - Use natural language keywords from the original question
   - Focus on categories, types, and high-level discovery
   - Include schema context (categories, relationship types) - NOT specific table names yet
   - Be specific about what schema information is needed
   - For relationship queries, specify edge types (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.) but without specific source_entity_id

3. **Specify MDL Response Types**: Define what type of schema information should be retrieved
   - Schema categories and table organization (first step)
   - Table definitions and structures (after discovery)
   - Table relationships and join conditions (after tables are identified)
   - Column metadata and field definitions
   - Compliance context for tables

4. **Include MDL Metadata Filters**: Specify required metadata filters for MDL queries
   - Always use product_name filter for product-specific queries
   - Note: Categories are for LLM question identification only, not for database filtering. Use semantic search instead.
   - Use table_name filter ONLY after tables are discovered
   - Use context_id filter ONLY after tables are identified (format: entity_{{product}}_{{table}})
   - Use edge_type filter for relationship queries (without specific source_entity_id in first breakdown)
   - Use type='schema_field' for column/field queries

5. **Leverage Schema Semantics**: Understand MDL-specific concepts
   - Schema categories (access requests, assets, projects, vulnerabilities, integrations, configuration, audit logs, risk management, deployment)
   - Table relationship semantics (join types, cardinality)
   - Column-level relationships and field semantics
   - Schema hierarchies and dependencies
"""
