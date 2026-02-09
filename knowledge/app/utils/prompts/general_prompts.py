"""
General Prompts
General-purpose prompts and context breakdown rules used across the application.
"""
from pathlib import Path
from typing import Optional

# Playbook-first: first step is to find relevant playbooks to drive retrieval and summary
PLAYBOOK_FIRST_RULES = """
#### PLAYBOOK-FIRST RULES ####
- **FIRST STEP**: Always plan to retrieve from playbooks (and procedure_steps) first to find relevant actions and workflow guidance for the user's question.
- Use playbooks to identify which controls, evidence, remediations, or procedures apply before querying other collections.
- After playbook retrieval, use the same contextual_edges and relationship semantics as before (no change to edge types or graph structure).
- Your output must include an **actionable playbook summary** tailored to the role type (e.g., security engineer, HR compliance officer, Auditor) based only on sources/collections this assistant is responsible for.
"""

# Static rules for context breakdown
CONTEXT_BREAKDOWN_RULES = """
#### CONTEXT BREAKDOWN RULES ####
- **CRITICAL**: Only use entities that are explicitly defined in the available entities list. Never hallucinate or assume entities exist.
- **CRITICAL**: Entity names in search_questions must be from the entity_to_collection list (in the config) so retrieval can map them to collections; use only those entity types.
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
   - "domain_knowledge" - if ANY KB document types are identified (see EXTRACTION ENTITIES table below):
     * Use the Store and type=<metadata_type> from that table (domain_knowledge, compliance_controls, or entities)
     * Doc types: policy, playbook, procedure, guide, faq, framework, requirement, advisory, documentation, product_docs -> domain_knowledge with type filter
     * standard, control -> compliance_controls; exception, vulnerability, rule_reference -> entities with type filter
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

# Intent planner: runs first to identify query type(s) and entities (steps 1–2). Breakdown then uses this for steps 3–5.
INTENT_PLANNER_INSTRUCTIONS = """
#### INTENT PLANNER INSTRUCTIONS ####
Run this step FIRST. Your output is used by the next step (breakdown) to generate search questions.
A single question can have MULTIPLE intents (e.g. metrics AND tables for product Snyk → both "mdl" and "product").

1. **Identify Query Type(s)**: Determine ALL query types that apply - use one or more of:
   - "query_planner" - ONLY when the request explicitly sets query_planner_intent (table retrieval + calculation plan for SQL Planner handoff; no other entities). Do not infer this from the question; the client must pass it in the request.
   - "mdl" or "table_related" - if the question involves schema, tables, columns, data, metrics, or MDL (use SCHEMA & DATABASE entities)
   - "policy" - if the question involves policy documents, policy evidence, or policy entities
   - "risk_control" - if the question involves risk controls, risk evidence, or risk entities
   - "compliance_framework" - if the question involves compliance controls, frameworks (SOC2, HIPAA, ISO 27001, GDPR, NIST, PCI-DSS)
   - "product" - if the question involves product descriptions, product knowledge, or product entities
   - "domain_knowledge" - if the question involves KB docs (playbook, procedure, guide, faq, framework, requirement, advisory, documentation)
   - "unknown" - only if no other type applies
   Output as query_types (list of strings). Example: ["mdl", "product"] for "What metrics and tables are available for Snyk?"

2. **Identify Entities**: From the Available Entities table (and assistant-specific allowed entities), list ALL exact entity names relevant to the question across all identified intents. Combine entities from every applicable query type (e.g. for metrics + tables for Snyk: include table_definitions, table_descriptions, schema_descriptions, db_schema, product_knowledge, product_entities, etc.). Use only entities from the table; exact names (case-sensitive). For compliance_framework include frameworks (list). For product include product_context (string) when product is mentioned.
"""

# When intent_plan is already set, breakdown step only does steps 3–5 (search questions, response types, metadata filters).
BREAKDOWN_FOLLOW_UP_INSTRUCTIONS = """
#### BREAKDOWN FOLLOW-UP (when intent is already known) ####
You have been given the query_types (possibly multiple, e.g. mdl + product) and identified_entities from the intent planner. The question may span multiple intents (e.g. metrics and tables for Snyk). Now:

3. **Generate Search Questions**: For each identified entity, create a specific search question (natural language keywords from the original question). Cover all intents—e.g. both metric-related and table-related questions when both apply. Do not use specific table names, entity IDs, or context_ids in filters in this step.
4. **Specify Response Types**: For each search question, define what type of information should be retrieved (control definitions, evidence requirements, table structures, metrics, etc.).
5. **Include Metadata Filters**: For each question, specify required metadata filters (type, framework, product_name as applicable). Do not use context_id or table_name filters in this first breakdown.
Output: user_intent (string), search_questions (list of { entity, question, metadata_filters, response_type }), and if compliance_framework in query_types then frameworks (list); if product in query_types then product_context (string).
"""


def get_intent_planner_system_prompt(assistant_type: Optional[str] = None) -> str:
    """
    Build system prompt for the intent planner node.
    Uses AVAILABLE_ENTITIES_MARKDOWN and assistant-specific allowed entities so the planner only considers relevant entities.
    """
    entities_md = get_available_entities_markdown()
    assistant_section = get_assistant_specific_breakdown_section(assistant_type) if assistant_type else ""
    return f"""You are an intent planner. Classify the user's question into one or more query types and identify all relevant entities (from the table). A question can have multiple intents (e.g. metrics and tables for Snyk → query_types ["mdl", "product"] and entities from both).

{assistant_section}

## Available Entities (use only these exact names)

{entities_md}

{INTENT_PLANNER_INSTRUCTIONS}

Output ONLY a single JSON object with keys: query_types (list of strings, one or more of: query_planner, mdl, table_related, policy, risk_control, compliance_framework, product, domain_knowledge, unknown), identified_entities (list of all relevant entity names across intents), frameworks (list, optional), product_context (string, optional). Note: query_planner is only set when the request passes query_planner_intent; do not output it from the question alone. No markdown, no explanation."""


def get_breakdown_instructions_with_intent(intent_plan: Optional[dict] = None) -> str:
    """
    Return breakdown instructions. When intent_plan is provided with at least one non-unknown query type,
    return follow-up instructions (steps 3–5 only) so the breakdown step generates only search_questions and metadata_filters.
    """
    if not intent_plan or not isinstance(intent_plan, dict):
        return ""
    query_types = intent_plan.get("query_types") or []
    if not query_types and intent_plan.get("query_type"):
        query_types = [intent_plan["query_type"]]
    if query_types and any(t and str(t).lower() != "unknown" for t in query_types):
        return BREAKDOWN_FOLLOW_UP_INSTRUCTIONS
    return ""


def get_assistant_specific_breakdown_section(assistant_type: Optional[str]) -> str:
    """
    Return assistant-specific instructions: allowed collections, role types, and playbook summary.
    Each assistant only looks at sources/collections they are responsible for.
    Contextual edges remain as they are.
    """
    if not assistant_type:
        return ""
    section = "\n#### ASSISTANT-SPECIFIC INSTRUCTIONS ####\n"
    section += "You MUST only use the entities/collections listed below for this assistant. "
    section += "First retrieve from playbooks to find relevant actions; then use other allowed entities. "
    section += "Contextual edges (context_definitions, contextual_edges) remain unchanged in semantics and usage.\n\n"
    section += "**Output**: Include an actionable playbook summary tailored to the target role, using only the sources this assistant owns.\n\n"

    if assistant_type == "data_assistance_assistant":
        section += "**Allowed entities (Data Assistant – schema/MDL and related):**\n"
        section += "- playbooks, procedure_steps (first step)\n"
        section += "- table_definitions, table_descriptions, column_definitions, schema_descriptions, db_schema, category_mapping\n"
        section += "- context_definitions, contextual_edges (unchanged)\n"
        section += "- table_contexts, table_fields, compliance_controls (for table-compliance only)\n\n"
        section += "**Target roles (for playbook summary):** security engineer, data engineer, auditor.\n"
    elif assistant_type == "knowledge_assistance_assistant":
        section += "**Allowed entities (Knowledge Assistant – domain knowledge and docs):**\n"
        section += "- playbooks, procedure_steps (first step)\n"
        section += "- domain_knowledge (policy, playbook, procedure, guide, faq, framework, requirement, advisory, documentation, product_docs)\n"
        section += "- compliance_controls, entities (from extraction config)\n"
        section += "- context_definitions, contextual_edges (unchanged)\n\n"
        section += "**Target roles (for playbook summary):** security engineer, HR compliance officer, knowledge manager, auditor.\n"
    elif assistant_type == "compliance_assistant":
        section += "**Allowed entities (Compliance Assistant – controls and mappings):**\n"
        section += "- playbooks, procedure_steps (first step)\n"
        section += "- compliance_controls, compliance_relationships\n"
        section += "- context_definitions, contextual_edges (unchanged)\n"
        section += "- When the user asks for tables, schema, or data to support compliance, also include query_type 'table_related' and entities: table_descriptions, db_schema, table_definitions.\n\n"
        section += "**Target roles (for playbook summary):** auditor, HR compliance officer, security engineer.\n"
    elif assistant_type == "product_assistant":
        section += "**Allowed entities (Product Assistant – product docs and entities):**\n"
        section += "- playbooks, procedure_steps (first step)\n"
        section += "- product_knowledge, product_docs, product_entities, product_descriptions\n"
        section += "- context_definitions, contextual_edges (unchanged)\n\n"
        section += "**Target roles (for playbook summary):** security engineer, product owner, DevOps.\n"
    elif assistant_type == "domain_knowledge_assistant":
        section += "**Allowed entities (Domain Knowledge Assistant – domains and docs):**\n"
        section += "- playbooks, procedure_steps (first step)\n"
        section += "- domain_knowledge (policy, playbook, procedure, guide, faq, framework, requirement, advisory, documentation, product_docs)\n"
        section += "- entities (keywords, concepts), compliance_controls (for reference)\n"
        section += "- context_definitions, contextual_edges (unchanged)\n\n"
        section += "**Target roles (for playbook summary):** knowledge manager, security engineer, HR compliance officer.\n"
    else:
        return ""
    return section


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


def get_extraction_entities_markdown(
    extractions_path: Optional[Path] = None,
    mapping_path: Optional[Path] = None,
) -> str:
    """
    Build markdown table of extraction doc types and store mapping from
    extractions.json + knowledge_assistant_mapping.json for context breakdown.
    Returns empty string if config cannot be loaded.
    """
    try:
        from app.config.extraction_entities_config import (
            get_doc_type_to_store,
            get_doc_types,
            get_domains,
            load_extraction_entities_config,
        )
    except ImportError:
        return ""

    extractions, mapping = load_extraction_entities_config(
        extractions_path=extractions_path,
        mapping_path=mapping_path,
        use_cache=True,
    )
    doc_type_to_store = get_doc_type_to_store(mapping)
    if not doc_type_to_store:
        return ""

    lines = [
        "",
        "### EXTRACTION ENTITIES (from KB config)",
        "",
        "Use these doc types and store mapping for user intent breakdown. Filter by type=<metadata_type>.",
        "",
        "| Doc Type | Store | metadata_type | extraction_type |",
        "|----------|-------|---------------|-----------------|",
    ]
    for doc_type, info in sorted(doc_type_to_store.items()):
        store = info.get("store_name", "")
        meta = info.get("metadata_type", "")
        ext = info.get("extraction_type", "")
        lines.append(f"| {doc_type} | {store} | {meta} | {ext} |")

    doc_types = get_doc_types(extractions)
    domains = get_domains(extractions)
    if doc_types:
        lines.extend(["", "**Doc types (taxonomy):** " + ", ".join(doc_types)])
    if domains:
        lines.extend(["", "**Domains (for context):** " + ", ".join(domains)])
    return "\n".join(lines).strip()


def get_available_entities_markdown(
    extractions_path: Optional[Path] = None,
    mapping_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    use_config: bool = True,
) -> str:
    """
    Return available entities markdown for generic context breakdown.
    When use_config is True, loads from breakdown_entities_config.yaml (external config)
    and returns a short block (~10-15 sentences). MDL-specific entities stay in mdl_prompts.
    When config is missing or use_config is False, falls back to static tables plus
    extraction entities from extractions.json + knowledge_assistant_mapping.json.
    """
    if use_config:
        try:
            from app.config.breakdown_entities_loader import get_breakdown_entities_markdown_cached
        except ImportError:
            pass
        else:
            block = get_breakdown_entities_markdown_cached(config_path=config_path)
            if block:
                return block
    base = AVAILABLE_ENTITIES_MARKDOWN
    extraction_section = get_extraction_entities_markdown(
        extractions_path=extractions_path,
        mapping_path=mapping_path,
    )
    if extraction_section:
        base = base.rstrip() + "\n\n" + extraction_section
    return base


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
