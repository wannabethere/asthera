"""
MDL Prompt Generator Utility
Generates markdown-formatted system prompts for MDL semantic layer queries.
Extends prompt_generator.py with MDL-specific semantic understanding.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.utils.prompt_generator import (
    load_vector_store_prompts,
    AVAILABLE_ENTITIES_MARKDOWN,
    CONTEXT_BREAKDOWN_RULES
)

logger = logging.getLogger(__name__)

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


def generate_mdl_context_breakdown_prompt(
    prompts_data: Optional[Dict[str, Any]] = None,
    include_examples: bool = True
) -> str:
    """
    Generate markdown-formatted system prompt for MDL semantic layer queries.
    
    Args:
        prompts_data: Optional prompts data (will load if not provided)
        include_examples: Whether to include examples in the prompt
        
    Returns:
        Markdown-formatted system prompt string for MDL queries
    """
    if prompts_data is None:
        prompts_data = load_vector_store_prompts()
    
    # Base prompt template combining generic and MDL-specific rules
    base_prompt = f"""{CONTEXT_BREAKDOWN_RULES}

{MDL_CONTEXT_BREAKDOWN_RULES}

{AVAILABLE_ENTITIES_MARKDOWN}

{MDL_ENTITIES_MARKDOWN}

{MDL_CONTEXT_BREAKDOWN_INSTRUCTIONS}
"""
    
    # MDL-specific examples section
    examples_section = """
## MDL Semantic Layer Examples

### Example 1: Table Relationship Query

**Question**: "What are the relationships from AccessRequest table to other tables in Snyk?"

**First Breakdown** (Generic - Identify Query Type):
```json
{
  "query_type": "mdl",
  "identified_entities": ["table_descriptions", "contextual_edges"],
  "entity_sub_types": ["table_descriptions", "table_relationships"],
  "search_questions": [
    {
      "entity": "table_descriptions",
      "question": "What types of tables are available for access requests in Snyk?",
      "metadata_filters": {"product_name": "Snyk"},
      "response_type": "Table descriptions to discover available tables"
    },
    {
      "entity": "contextual_edges",
      "question": "What table relationships exist in Snyk?",
      "metadata_filters": {"product_name": "Snyk"},
      "response_type": "Relationship edges showing table relationships"
    }
  ]
}
```

**Note**: The first breakdown identifies this as an MDL query. The MDL retrieval step (second query) will then use MDL-specific rules and filters based on the query type.

### Example 2: Column/Field Query

**Question**: "What fields are in the AccessRequest table and how do they relate to compliance?"
**Project ID**: "project_456"

**Breakdown**:
```json
{
  "identified_entities": ["fields", "context_definitions", "contextual_edges"],
  "entity_sub_types": ["table_fields", "table_contexts", "compliance_relationships"],
  "search_questions": [
    {
      "entity": "fields",
      "question": "Fields and columns in AccessRequest table for Snyk",
      "metadata_filters": {
        "context_id": "entity_Snyk_AccessRequest",
        "type": "schema_field",
        "product_name": "Snyk"
      },
      "response_type": "Field definitions with names, types, descriptions"
    },
    {
      "entity": "context_definitions",
      "question": "AccessRequest table context and compliance analysis",
      "metadata_filters": {"context_id": "entity_Snyk_AccessRequest"},
      "response_type": "Table context with compliance frameworks and controls"
    },
    {
      "entity": "contextual_edges",
      "question": "Compliance control relationships for AccessRequest table",
      "metadata_filters": {
        "source_entity_id": "entity_Snyk_AccessRequest",
        "edge_type": "RELEVANT_TO_CONTROL"
      },
      "response_type": "Edges to compliance controls relevant to this table"
    }
  ]
}
```

### Example 3: Schema Category Query

**Question**: "What tables are in the 'access requests' category for Snyk?"
**Project ID**: "project_789"

**Breakdown**:
```json
{
  "identified_entities": ["table_descriptions", "category_mapping"],
  "entity_sub_types": ["table_descriptions", "category_tables"],
  "search_questions": [
    {
      "entity": "table_descriptions",
      "question": "Snyk table descriptions for access requests",
      "metadata_filters": {"product_name": "Snyk"},
      "response_type": "Table descriptions for access requests (use semantic search, not category filters)"
    },
    {
      "entity": "category_mapping",
      "question": "Tables related to access requests category in Snyk",
      "metadata_filters": {"product_name": "Snyk"},
      "response_type": "Table mappings for access requests (use semantic search based on query)"
    },
    {
      "entity": "table_descriptions",
      "question": "Table descriptions for access request related tables in Snyk",
      "metadata_filters": {"product_name": "Snyk"},
      "response_type": "Detailed table descriptions with business context (use semantic search)"
    }
  ]
}
```

### Example 4: Multi-Hop Schema Query

**Question**: "What compliance controls are relevant to tables that have relationships with AccessRequest?"
**Project ID**: "project_101"

**Breakdown**:
```json
{
  "identified_entities": ["contextual_edges", "context_definitions", "compliance_controls"],
  "entity_sub_types": ["table_relationships", "table_contexts", "compliance_controls"],
  "search_questions": [
    {
      "entity": "contextual_edges",
      "question": "Tables related to AccessRequest via relationships",
      "metadata_filters": {
        "source_entity_id": "entity_Snyk_AccessRequest",
        "edge_type": {"$in": ["BELONGS_TO_TABLE", "HAS_MANY_TABLES", "REFERENCES_TABLE"]}
      },
      "response_type": "Related tables and their relationship types"
    },
    {
      "entity": "contextual_edges",
      "question": "Compliance control relationships for tables related to AccessRequest",
      "metadata_filters": {
        "edge_type": "RELEVANT_TO_CONTROL",
        "source_entity_id": {"$in": ["entity_Snyk_Project", "entity_Snyk_User"]}
      },
      "response_type": "Compliance controls relevant to related tables"
    },
    {
      "entity": "compliance_controls",
      "question": "SOC2 and HIPAA controls for access management",
      "metadata_filters": {"framework": {"$in": ["SOC2", "HIPAA"]}},
      "response_type": "Control definitions for access management"
    }
  ]
}
```
"""
    
    # Combine sections
    if include_examples:
        return base_prompt + examples_section
    else:
        return base_prompt


def get_mdl_context_breakdown_system_prompt(
    prompts_file: Optional[str] = None,
    include_examples: bool = True
) -> str:
    """
    Get the complete system prompt for MDL semantic layer context breakdown.
    
    Args:
        prompts_file: Optional path to vector_store_prompts.json
        include_examples: Whether to include examples
        
    Returns:
        Complete markdown-formatted system prompt for MDL queries
    """
    prompts_data = load_vector_store_prompts(prompts_file)
    return generate_mdl_context_breakdown_prompt(prompts_data, include_examples)


def get_mdl_edge_type_semantics() -> Dict[str, Dict[str, Any]]:
    """
    Get MDL edge type semantics for understanding table relationships.
    
    Returns:
        Dictionary mapping edge types to their semantic meaning
    """
    return {
        "BELONGS_TO_TABLE": {
            "description": "Table belongs to another table (many-to-one relationship)",
            "cardinality": "many-to-one",
            "example": "AccessRequest belongs to Project",
            "join_type": "MANY_TO_ONE",
            "semantic_meaning": "Child table references parent table",
            "query_priority": "high"  # Important for understanding table hierarchy
        },
        "HAS_MANY_TABLES": {
            "description": "Table has many related tables (one-to-many relationship)",
            "cardinality": "one-to-many",
            "example": "Project has many AccessRequests",
            "join_type": "ONE_TO_MANY",
            "semantic_meaning": "Parent table has multiple child tables",
            "query_priority": "high"
        },
        "REFERENCES_TABLE": {
            "description": "Table references another table (one-to-one relationship)",
            "cardinality": "one-to-one",
            "example": "User references Profile",
            "join_type": "ONE_TO_ONE",
            "semantic_meaning": "Direct reference between tables",
            "query_priority": "medium"
        },
        "MANY_TO_MANY_TABLE": {
            "description": "Many-to-many relationship between tables",
            "cardinality": "many-to-many",
            "example": "Users <-> Groups",
            "join_type": "MANY_TO_MANY",
            "semantic_meaning": "Complex relationship requiring junction table",
            "query_priority": "medium"
        },
        "LINKED_TO_TABLE": {
            "description": "Tables are linked (general relationship)",
            "cardinality": "variable",
            "example": "Related tables without specific cardinality",
            "join_type": "variable",
            "semantic_meaning": "General linkage between tables",
            "query_priority": "low"
        },
        "RELATED_TO_TABLE": {
            "description": "Tables are related (general relationship)",
            "cardinality": "variable",
            "example": "Fallback for any table relationship",
            "join_type": "variable",
            "semantic_meaning": "Generic relationship",
            "query_priority": "low"
        },
        "RELEVANT_TO_CONTROL": {
            "description": "Table is relevant to compliance control",
            "cardinality": "many-to-many",
            "example": "AccessRequest relevant to SOC2 CC6.1",
            "join_type": "N/A",
            "semantic_meaning": "Compliance relationship",
            "query_priority": "high"  # Important for compliance queries
        },
        "HAS_FIELD": {
            "description": "Table has field/column",
            "cardinality": "one-to-many",
            "example": "AccessRequest has field 'requested_at'",
            "join_type": "N/A",
            "semantic_meaning": "Table-column relationship",
            "query_priority": "medium"
        }
    }


def get_mdl_schema_category_semantics(product_name: str) -> Dict[str, Any]:
    """
    Get schema category semantics for a product.
    
    Args:
        product_name: Product name (e.g., "Snyk", "Cornerstone")
        
    Returns:
        Dictionary with category semantics
    """
    # Categories from schema_descriptions for Snyk
    # This would typically be loaded from schema_descriptions or configuration
    # For now, return common patterns based on schema_descriptions
    common_categories = {
        "Snyk": {
            "access requests": {
                "description": "Tables related to access request management",
                "tables": ["AccessRequest", "AccessRequestHistory", "AccessRequestApproval"],
                "semantic_meaning": "User access and permission management"
            },
            "application data": {
                "description": "Tables related to application data and application-specific information",
                "tables": [],
                "semantic_meaning": "Application-level data and metadata"
            },
            "assets": {
                "description": "Tables related to asset management",
                "tables": ["Asset", "AssetGroup", "AssetTag"],
                "semantic_meaning": "Infrastructure and resource tracking"
            },
            "projects": {
                "description": "Tables related to project management",
                "tables": ["Project", "ProjectMember", "ProjectSettings"],
                "semantic_meaning": "Project organization and configuration"
            },
            "vulnerabilities": {
                "description": "Tables related to vulnerability management",
                "tables": ["Vulnerability", "VulnerabilityFinding", "VulnerabilityRemediation"],
                "semantic_meaning": "Security vulnerability tracking and remediation"
            },
            "integrations": {
                "description": "Tables related to integrations and external connections",
                "tables": [],
                "semantic_meaning": "Integration management and external system connections"
            },
            "configuration": {
                "description": "Tables related to configuration and settings",
                "tables": [],
                "semantic_meaning": "System configuration and settings management"
            },
            "audit logs": {
                "description": "Tables related to audit logs and audit trail",
                "tables": [],
                "semantic_meaning": "Audit logging and compliance trail tracking"
            },
            "risk management": {
                "description": "Tables related to risk management and risk assessment",
                "tables": [],
                "semantic_meaning": "Risk identification, assessment, and mitigation tracking"
            },
            "deployment": {
                "description": "Tables related to deployment and deployment management",
                "tables": [],
                "semantic_meaning": "Deployment tracking and management"
            }
        },
        "Cornerstone": {
            "learning": {
                "description": "Tables related to learning management",
                "tables": ["Course", "Enrollment", "Completion"],
                "semantic_meaning": "Learning and training management"
            },
            "compliance": {
                "description": "Tables related to compliance tracking",
                "tables": ["ComplianceRecord", "ComplianceRequirement", "ComplianceEvidence"],
                "semantic_meaning": "Compliance and certification tracking"
            }
        }
    }
    
    return common_categories.get(product_name, {})

