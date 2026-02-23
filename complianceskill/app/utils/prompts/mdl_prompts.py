"""
MDL-Specific Prompts
Prompts for MDL semantic layer queries and schema understanding.
"""

# MDL-specific context breakdown rules
MDL_CONTEXT_BREAKDOWN_RULES = """
#### MDL SEMANTIC LAYER RULES ####
- **CRITICAL**: MDL queries involve schema semantics: tables, columns, relationships, categories
- **CRITICAL**: For table queries, first check schema_descriptions for available categories (e.g., Snyk: access requests, assets, projects, vulnerabilities)
- **CRITICAL**: Table relationships use specific edge types: BELONGS_TO_TABLE, HAS_MANY_TABLES, REFERENCES_TABLE, MANY_TO_MANY_TABLE, LINKED_TO_TABLE, RELATED_TO_TABLE
- **CRITICAL**: Table entity IDs follow format: entity_{{product_name}}_{{table_name}} (e.g., entity_Snyk_AccessRequest)
- **CRITICAL**: Always include product_name and table_name in metadata filters for MDL queries
- **CRITICAL**: Use schema_descriptions to understand category context before querying specific tables
- **CRITICAL**: For relationship queries, use contextual_edges with appropriate edge_type filters
- **CRITICAL**: Column-level queries should use fields collection with context_id pointing to table entity
- **CRITICAL FIRST BREAKDOWN RULE**: The FIRST breakdown step should NOT ask for specific tables/entities. Instead, breakdown into HIGHER-LEVEL entity detection using available stores, descriptions, and categories. For example:
  * Instead of: "AccessRequest table context for Snyk" (specific table)
  * Use: "Search for Access related tables for Snyk, category of tables accessrequest" (higher-level category search)
  * Entity: Use stores like "table_descriptions", "schema_descriptions", "category_mapping" for discovery
  * Entity: Use "contextual_edges" for relationship discovery (not specific table relationships yet)
- Use natural language keywords from the original question when generating search questions
- Make search questions specific enough to retrieve relevant MDL documents
- Include context about what schema information is needed (table structure, relationships, columns, categories)
- Specify response types clearly (table definitions, relationships, column metadata, schema categories, etc.)
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
