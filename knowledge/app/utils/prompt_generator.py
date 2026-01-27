"""
Prompt Generator Utility
Generates markdown-formatted system prompts for question/project ID context breakdown.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

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


def load_vector_store_prompts(prompts_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load vector_store_prompts.json file.
    
    Args:
        prompts_file: Path to vector_store_prompts.json (defaults to app/indexing/vector_store_prompts.json)
        
    Returns:
        Dictionary containing prompts data
    """
    if prompts_file is None:
        base_path = Path(__file__).parent.parent
        prompts_file = base_path / "indexing" / "vector_store_prompts.json"
    
    prompts_path = Path(prompts_file)
    try:
        if prompts_path.exists():
            with open(prompts_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Prompts file not found: {prompts_path}")
            return {}
    except Exception as e:
        logger.error(f"Error loading prompts file: {str(e)}")
        return {}


def generate_context_breakdown_prompt(
    prompts_data: Optional[Dict[str, Any]] = None,
    include_examples: bool = True
) -> str:
    """
    Generate markdown-formatted system prompt for question/project ID context breakdown.
    
    Args:
        prompts_data: Optional prompts data (will load if not provided)
        include_examples: Whether to include examples in the prompt
        
    Returns:
        Markdown-formatted system prompt string
    """
    if prompts_data is None:
        prompts_data = load_vector_store_prompts()
    
    # Base prompt template using static markdown
    base_prompt = "{}\n\n{}\n\n{}\n".format(CONTEXT_BREAKDOWN_RULES, AVAILABLE_ENTITIES_MARKDOWN, CONTEXT_BREAKDOWN_INSTRUCTIONS)
    
    # Examples section
    examples_section = """
## Examples

### Example 1: Compliance Framework Query

**Question**: "What are the SOC2 controls for access management?"
**Project ID**: "project_123"

**Breakdown**:
```json
{{
  "query_type": "compliance_framework",
  "identified_entities": ["compliance_controls"],
  "entity_sub_types": ["soc2_controls"],
  "search_questions": [
    {{
      "entity": "compliance_controls",
      "question": "SOC2 controls for access management and authentication",
      "metadata_filters": {{"framework": "SOC2"}},
      "response_type": "Control definitions with requirements and implementation guidance"
    }}
  ]
}}
```

### Example 2: MDL/Table Related Query

**Question**: "What tables are related to AccessRequest in Snyk?"
**Project ID**: "project_456"

**Breakdown**:
```json
{{
  "query_type": "mdl",
  "identified_entities": ["table_descriptions", "contextual_edges"],
  "entity_sub_types": ["table_descriptions", "table_relationships"],
  "search_questions": [
    {{
      "entity": "table_descriptions",
      "question": "What types of tables are available for access requests in Snyk?",
      "metadata_filters": {{"product_name": "Snyk"}},
      "response_type": "Table descriptions to discover available tables"
    }},
    {{
      "entity": "contextual_edges",
      "question": "What table relationships exist in Snyk?",
      "metadata_filters": {{"product_name": "Snyk"}},
      "response_type": "Relationship edges showing table relationships"
    }}
  ]
}}
```

### Example 3: Policy Query

**Question**: "What evidence is required for SOC2 access control controls?"
**Project ID**: "project_789"

**Breakdown**:
```json
{{
  "query_type": "policy",
  "identified_entities": ["compliance_controls", "evidence"],
  "entity_sub_types": ["soc2_controls", "policy_evidence"],
  "search_questions": [
    {{
      "entity": "compliance_controls",
      "question": "SOC2 access control controls",
      "metadata_filters": {{"framework": "SOC2"}},
      "response_type": "Control definitions mentioning evidence requirements"
    }},
    {{
      "entity": "evidence",
      "question": "Evidence required for access control compliance",
      "metadata_filters": {{"type": "policy", "framework": "SOC2"}},
      "response_type": "Evidence definitions and examples for access control"
    }}
  ]
}}
```

### Example 4: Risk Control Query

**Question**: "What risk controls are associated with data access management?"
**Project ID**: "project_101"

**Breakdown**:
```json
{{
  "query_type": "risk_control",
  "identified_entities": ["risk_controls", "risk_entities"],
  "entity_sub_types": ["risk_controls", "risk_entities"],
  "search_questions": [
    {{
      "entity": "risk_controls",
      "question": "Risk controls for data access management",
      "metadata_filters": {{"type": "risk_control"}},
      "response_type": "Risk control documents and requirements"
    }},
    {{
      "entity": "risk_entities",
      "question": "Entities related to data access risk management",
      "metadata_filters": {{"type": "risk_entities", "extraction_type": "entities"}},
      "response_type": "Risk entities and their relationships"
    }}
  ]
}}
```
"""
    
    # Combine sections
    if include_examples:
        return base_prompt + examples_section
    else:
        return base_prompt


def get_context_breakdown_system_prompt(
    prompts_file: Optional[str] = None,
    include_examples: bool = True
) -> str:
    """
    Get the complete system prompt for context breakdown.
    
    Args:
        prompts_file: Optional path to vector_store_prompts.json
        include_examples: Whether to include examples
        
    Returns:
        Complete markdown-formatted system prompt
    """
    prompts_data = load_vector_store_prompts(prompts_file)
    return generate_context_breakdown_prompt(prompts_data, include_examples)

