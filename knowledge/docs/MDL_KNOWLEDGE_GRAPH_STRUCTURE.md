# MDL Knowledge Graph Structure

## Overview

This document defines the complete knowledge graph structure for MDL (Metadata Definition Language) semantic layer, mapping products, categories, tables, relationships, and contextual information to both ChromaDB vector stores and PostgreSQL relational storage for hybrid search capabilities.

## Hierarchical Structure

```
Product (e.g., Snyk)
  ↓
Categories (15 categories of information)
  ↓
Tables (schema entities)
  ↓
Columns (table attributes)
  ↓
Insights (metrics, features, key concepts)
```

## Entity Types and Relationships

### 1. Product Level

**Entity Type**: `product`

**Attributes**:
- product_id (unique identifier)
- product_name (e.g., "Snyk", "Cornerstone")
- product_description (semantic description)
- vendor
- api_endpoints (JSON array)
- data_sources (JSON array)

**Relationships**:
- `PRODUCT_HAS_CATEGORY` → Category
- `PRODUCT_PROVIDES_API` → API Endpoint
- `PRODUCT_SUPPORTS_FRAMEWORK` → Framework

**ChromaDB Collection**: `mdl_products`
**PostgreSQL Table**: `mdl_products`

---

### 2. Category Level

**Entity Type**: `category`

**15 Categories** (from FINAL_CATEGORIES.md):
1. access requests
2. application data
3. assets
4. projects
5. vulnerabilities
6. integrations
7. configuration
8. audit logs
9. risk management
10. deployment
11. groups
12. organizations
13. memberships and roles
14. issues
15. artifacts

**Attributes**:
- category_id (unique identifier)
- category_name (one of 15 categories)
- category_description (semantic description)
- product_id (foreign key to product)
- business_domain
- data_sensitivity_level

**Relationships**:
- `CATEGORY_BELONGS_TO_PRODUCT` → Product
- `CATEGORY_CONTAINS_TABLE` → Table
- `CATEGORY_HAS_INSIGHT` → Insight

**ChromaDB Collection**: `mdl_categories`
**PostgreSQL Table**: `mdl_categories`

---

### 3. Table Level

**Entity Type**: `table`

**Attributes**:
- table_id (unique identifier)
- table_name (e.g., "AccessRequest", "AssetAttributes")
- schema_name
- catalog_name
- semantic_description (rich description from MDL)
- table_purpose
- business_context
- category_id (foreign key to category)
- product_id (foreign key to product)
- ref_sql (reference SQL query)
- primary_key
- is_fact_table (boolean)
- is_dimension_table (boolean)
- update_frequency
- data_volume_estimate

**Relationships**:
- `TABLE_BELONGS_TO_CATEGORY` → Category
- `TABLE_BELONGS_TO_PRODUCT` → Product
- `TABLE_HAS_COLUMN` → Column
- `TABLE_RELATES_TO_TABLE` → Table (self-referential)
- `TABLE_HAS_FEATURE` → Feature
- `TABLE_SUPPORTS_METRIC` → Metric
- `TABLE_HAS_EXAMPLE` → Example
- `TABLE_FOLLOWS_INSTRUCTION` → Instruction
- `TABLE_REFERENCES_FRAMEWORK` → Framework

**ChromaDB Collection**: `mdl_tables`
**PostgreSQL Table**: `mdl_tables`

---

### 4. Column Level

**Entity Type**: `column`

**Attributes**:
- column_id (unique identifier)
- column_name (e.g., "id", "status", "attributes")
- table_id (foreign key to table)
- data_type (e.g., "varchar", "json", "integer")
- is_nullable (boolean)
- is_primary_key (boolean)
- is_foreign_key (boolean)
- column_description (semantic description)
- business_significance
- is_sensitive_data (boolean)
- is_pii (boolean)
- nested_properties (for JSON columns)
- enum_values (JSON array)
- format_pattern (e.g., "uuid", "date")

**Relationships**:
- `COLUMN_BELONGS_TO_TABLE` → Table
- `COLUMN_REFERENCES_COLUMN` → Column (foreign key relationships)
- `COLUMN_IS_TIME_DIMENSION` → Time Concept
- `COLUMN_SUPPORTS_KPI` → KPI
- `COLUMN_DERIVED_FROM` → Column (calculated columns)
- `COLUMN_HAS_METADATA` → Column Metadata

**ChromaDB Collection**: `mdl_columns`
**PostgreSQL Table**: `mdl_columns`

---

### 5. Relationship Level

**Entity Type**: `relationship`

**Attributes**:
- relationship_id (unique identifier)
- source_table_id (foreign key to table)
- target_table_id (foreign key to table)
- relationship_type (e.g., "one-to-many", "many-to-many")
- relationship_name (e.g., "has_many", "belongs_to")
- join_condition (SQL join expression)
- is_from_mdl (boolean - from MDL or external config)
- cardinality
- is_identifying (boolean)

**Relationships**:
- `RELATIONSHIP_CONNECTS_TABLES` → Table (bidirectional)
- `RELATIONSHIP_DEFINED_IN_MDL` → MDL Source
- `RELATIONSHIP_DEFINED_EXTERNALLY` → External Config

**ChromaDB Collection**: `mdl_relationships`
**PostgreSQL Table**: `mdl_relationships`

---

### 6. Insight Level

**Entity Type**: `insight`

**Sub-types**:
- **Metrics** - Quantitative measurements
- **Features** - Business capabilities/features
- **Key Concepts** - Important domain concepts

**Attributes**:
- insight_id (unique identifier)
- insight_type (metric | feature | key_concept)
- insight_name
- insight_description
- category_id (foreign key to category)
- related_table_ids (JSON array)
- related_column_ids (JSON array)

**Relationships**:
- `INSIGHT_BELONGS_TO_CATEGORY` → Category
- `INSIGHT_USES_TABLE` → Table
- `INSIGHT_USES_COLUMN` → Column
- `INSIGHT_SUPPORTS_CONTROL` → Control (for compliance features)

**ChromaDB Collection**: `mdl_insights`
**PostgreSQL Table**: `mdl_insights`

---

### 7. Metric & KPI Level

**Entity Type**: `metric` / `kpi`

**Attributes**:
- metric_id (unique identifier)
- metric_name (e.g., "Total Vulnerabilities", "Mean Time to Remediate")
- metric_type (kpi | metric | calculation)
- calculation_formula (SQL or formula)
- aggregation_type (sum, avg, count, etc.)
- table_id (source table)
- column_ids (JSON array)
- time_dimension_column
- groupby_dimensions (JSON array)
- business_definition
- target_value
- threshold_warning
- threshold_critical

**Relationships**:
- `METRIC_FROM_TABLE` → Table
- `METRIC_USES_COLUMN` → Column
- `METRIC_IS_KPI` → KPI Definition
- `METRIC_TRACKS_PERFORMANCE` → Business Objective

**ChromaDB Collection**: `mdl_metrics`
**PostgreSQL Table**: `mdl_metrics`

---

### 8. Feature Level

**Entity Type**: `feature`

**Attributes**:
- feature_id (unique identifier)
- feature_name (e.g., "Vulnerability Scanning", "Access Control")
- feature_description
- product_id (foreign key to product)
- table_ids (JSON array - tables that support this feature)
- column_ids (JSON array)
- api_endpoints (JSON array)
- feature_category
- maturity_level

**Relationships**:
- `FEATURE_BELONGS_TO_PRODUCT` → Product
- `FEATURE_USES_TABLE` → Table
- `FEATURE_USES_COLUMN` → Column
- `FEATURE_SUPPORTS_CONTROL` → Control
- `FEATURE_ENABLES_CAPABILITY` → Business Capability

**ChromaDB Collection**: `mdl_features`
**PostgreSQL Table**: `mdl_features`

---

### 9. Example & Natural Question Level

**Entity Type**: `example` / `natural_question`

**Attributes**:
- example_id (unique identifier)
- question_text (natural language question)
- sql_query (corresponding SQL query)
- answer_template (expected answer format)
- table_ids (JSON array - tables used in query)
- column_ids (JSON array)
- complexity_level (simple | medium | complex)
- use_case (exploration | reporting | monitoring)
- expected_result_type (table | scalar | chart)

**Relationships**:
- `EXAMPLE_USES_TABLE` → Table
- `EXAMPLE_USES_COLUMN` → Column
- `EXAMPLE_DEMONSTRATES_PATTERN` → Query Pattern
- `EXAMPLE_ANSWERS_QUESTION` → Natural Question

**ChromaDB Collection**: `mdl_examples`
**PostgreSQL Table**: `mdl_examples`

---

### 10. Instruction Level

**Entity Type**: `instruction`

**Attributes**:
- instruction_id (unique identifier)
- instruction_type (best_practice | constraint | optimization | warning)
- instruction_text (detailed instruction)
- product_id (foreign key to product)
- applies_to_table_id (optional)
- applies_to_column_id (optional)
- priority (high | medium | low)
- context (when to apply)

**Relationships**:
- `INSTRUCTION_APPLIES_TO_PRODUCT` → Product
- `INSTRUCTION_APPLIES_TO_TABLE` → Table
- `INSTRUCTION_APPLIES_TO_COLUMN` → Column
- `INSTRUCTION_GUIDES_USAGE` → Usage Pattern

**ChromaDB Collection**: `mdl_instructions`
**PostgreSQL Table**: `mdl_instructions`

---

### 11. Time Concept Level

**Entity Type**: `time_concept`

**Attributes**:
- time_concept_id (unique identifier)
- concept_name (e.g., "created_at", "updated_at", "event_time")
- table_id (foreign key to table)
- column_id (foreign key to column)
- time_granularity (year | quarter | month | week | day | hour)
- is_event_time (boolean)
- is_process_time (boolean)
- timezone

**Relationships**:
- `TIME_CONCEPT_IN_TABLE` → Table
- `TIME_CONCEPT_USES_COLUMN` → Column
- `TIME_CONCEPT_ENABLES_TREND` → Trend Analysis

**ChromaDB Collection**: `mdl_time_concepts`
**PostgreSQL Table**: `mdl_time_concepts`

---

### 12. Calculated Column Level

**Entity Type**: `calculated_column`

**Attributes**:
- calculated_column_id (unique identifier)
- calculated_column_name
- source_table_id (foreign key to table)
- calculation_expression (formula or SQL)
- depends_on_column_ids (JSON array)
- result_data_type
- business_purpose

**Relationships**:
- `CALCULATED_COLUMN_BELONGS_TO_TABLE` → Table
- `CALCULATED_COLUMN_DERIVED_FROM` → Column (multiple)
- `CALCULATED_COLUMN_USED_IN_METRIC` → Metric

**ChromaDB Collection**: `mdl_calculated_columns`
**PostgreSQL Table**: `mdl_calculated_columns`

---

### 13. Business Function Level

**Entity Type**: `business_function`

**Attributes**:
- business_function_id (unique identifier)
- function_name (e.g., "Security Monitoring", "Compliance Reporting")
- function_description
- product_id (foreign key to product)
- supported_by_table_ids (JSON array)
- required_features (JSON array)

**Relationships**:
- `BUSINESS_FUNCTION_BELONGS_TO_PRODUCT` → Product
- `BUSINESS_FUNCTION_USES_TABLE` → Table
- `BUSINESS_FUNCTION_REQUIRES_FEATURE` → Feature
- `BUSINESS_FUNCTION_SUPPORTS_ACTION` → User Action

**ChromaDB Collection**: `mdl_business_functions`
**PostgreSQL Table**: `mdl_business_functions`

---

### 14. Framework Level

**Entity Type**: `framework`

**Attributes**:
- framework_id (unique identifier)
- framework_name (e.g., "SOC2", "HIPAA", "GDPR")
- framework_description
- applicable_to_product_ids (JSON array)
- coverage_level

**Relationships**:
- `FRAMEWORK_APPLIES_TO_PRODUCT` → Product
- `FRAMEWORK_MAPS_TO_TABLE` → Table
- `FRAMEWORK_REQUIRES_CONTROL` → Control
- `FRAMEWORK_TRACKS_METRIC` → Metric

**ChromaDB Collection**: `mdl_frameworks`
**PostgreSQL Table**: `mdl_frameworks`

---

### 15. Ownership & Permissions Level

**Entity Type**: `ownership`

**Attributes**:
- ownership_id (unique identifier)
- entity_type (table | column | feature)
- entity_id
- owner_user_id
- owner_team
- access_permissions (JSON object)
- data_steward

**Relationships**:
- `OWNERSHIP_FOR_TABLE` → Table
- `OWNERSHIP_FOR_COLUMN` → Column
- `OWNERSHIP_GRANTS_ACCESS` → User/Team

**ChromaDB Collection**: `mdl_ownership`
**PostgreSQL Table**: `mdl_ownership`

---

## Edge Types Summary

### Critical Priority Edges
- `COLUMN_BELONGS_TO_TABLE` - Core schema relationship
- `TABLE_BELONGS_TO_CATEGORY` - Organization structure
- `TABLE_RELATES_TO_TABLE` - Data model relationships

### High Priority Edges
- `TABLE_HAS_FEATURE` - Feature to data mapping
- `FEATURE_SUPPORTS_CONTROL` - Compliance mapping
- `METRIC_FROM_TABLE` - Business intelligence
- `EXAMPLE_USES_TABLE` - Usage patterns

### Medium Priority Edges
- `TABLE_FOLLOWS_INSTRUCTION` - Best practices
- `INSIGHT_USES_TABLE` - Business insights
- `BUSINESS_FUNCTION_USES_TABLE` - Functional mapping

### Low Priority Edges
- `OWNERSHIP_FOR_TABLE` - Governance
- `FRAMEWORK_MAPS_TO_TABLE` - Compliance reference

---

## Storage Architecture

### ChromaDB Collections

Each entity type has a dedicated ChromaDB collection for vector-based semantic search:

| Collection Name | Entity Type | Purpose |
|----------------|-------------|---------|
| `mdl_products` | Product | Product definitions and capabilities |
| `mdl_categories` | Category | 15 business categories |
| `mdl_tables` | Table | Table schemas and descriptions |
| `mdl_columns` | Column | Column metadata and semantics |
| `mdl_relationships` | Relationship | Table relationships |
| `mdl_insights` | Insight | Metrics, features, concepts |
| `mdl_metrics` | Metric/KPI | Business metrics and KPIs |
| `mdl_features` | Feature | Product features |
| `mdl_examples` | Example | Query examples |
| `mdl_instructions` | Instruction | Product instructions |
| `mdl_time_concepts` | Time Concept | Temporal dimensions |
| `mdl_calculated_columns` | Calculated Column | Derived columns |
| `mdl_business_functions` | Business Function | Business capabilities |
| `mdl_frameworks` | Framework | Compliance frameworks |
| `mdl_ownership` | Ownership | Access and ownership |
| `mdl_contextual_edges` | Edge | All contextual relationships |

### PostgreSQL Tables

Each entity type has a corresponding PostgreSQL table for structured queries and relationship management:

| Table Name | Entity Type | Indexes |
|-----------|-------------|---------|
| `mdl_products` | Product | product_id (PK), product_name |
| `mdl_categories` | Category | category_id (PK), product_id (FK), category_name |
| `mdl_tables` | Table | table_id (PK), category_id (FK), product_id (FK), table_name |
| `mdl_columns` | Column | column_id (PK), table_id (FK), column_name |
| `mdl_relationships` | Relationship | relationship_id (PK), source_table_id (FK), target_table_id (FK) |
| `mdl_insights` | Insight | insight_id (PK), category_id (FK), insight_type |
| `mdl_metrics` | Metric/KPI | metric_id (PK), table_id (FK), metric_type |
| `mdl_features` | Feature | feature_id (PK), product_id (FK), feature_name |
| `mdl_examples` | Example | example_id (PK), complexity_level |
| `mdl_instructions` | Instruction | instruction_id (PK), product_id (FK), instruction_type |
| `mdl_time_concepts` | Time Concept | time_concept_id (PK), table_id (FK), column_id (FK) |
| `mdl_calculated_columns` | Calculated Column | calculated_column_id (PK), source_table_id (FK) |
| `mdl_business_functions` | Business Function | business_function_id (PK), product_id (FK) |
| `mdl_frameworks` | Framework | framework_id (PK), framework_name |
| `mdl_ownership` | Ownership | ownership_id (PK), entity_type, entity_id |
| `mdl_contextual_edges` | Edge | edge_id (PK), source_entity_id, target_entity_id, edge_type |

---

## Hybrid Search Integration

### Search Patterns

1. **Product Discovery**
   - ChromaDB: Semantic search in `mdl_products`
   - PostgreSQL: Filter by vendor, API endpoints

2. **Category Exploration**
   - ChromaDB: Search `mdl_categories` by business domain
   - PostgreSQL: Join to products and tables

3. **Table Discovery**
   - ChromaDB: Semantic search in `mdl_tables` for descriptions
   - PostgreSQL: Filter by category, product, data volume

4. **Column Lookup**
   - ChromaDB: Search `mdl_columns` by business significance
   - PostgreSQL: Filter by data_type, is_pii, is_sensitive

5. **Feature Mapping**
   - ChromaDB: Search `mdl_features` by capability
   - PostgreSQL: Join to tables, columns, controls

6. **Metric Discovery**
   - ChromaDB: Search `mdl_metrics` by business definition
   - PostgreSQL: Filter by aggregation_type, target_value

7. **Example Queries**
   - ChromaDB: Search `mdl_examples` by natural question
   - PostgreSQL: Filter by complexity_level, use_case

8. **Relationship Traversal**
   - PostgreSQL: Join `mdl_relationships` for graph traversal
   - ChromaDB: Semantic search on relationship semantics

---

## Query Examples

### Example 1: Find all tables in "assets" category for Snyk

```python
# Hybrid search with metadata filter
results = await hybrid_search_service.hybrid_search(
    query="asset management tables with vulnerability data",
    top_k=10,
    where={
        "product_name": "Snyk",
        "category_name": "assets"
    }
)
```

### Example 2: Discover features that support SOC2 controls

```python
# Search features collection
feature_results = await hybrid_search_service.hybrid_search(
    collection_name="mdl_features",
    query="security monitoring features for SOC2 compliance",
    top_k=5,
    where={
        "product_name": "Snyk"
    }
)

# Then traverse edges to find related controls
# (via PostgreSQL joins or contextual_edges collection)
```

### Example 3: Find example queries for vulnerability analysis

```python
results = await hybrid_search_service.hybrid_search(
    collection_name="mdl_examples",
    query="how to analyze high severity vulnerabilities",
    top_k=5,
    where={
        "complexity_level": "medium",
        "use_case": "exploration"
    }
)
```

---

## Integration with Context Breakdown Agent

The MDL context breakdown agent uses this structure to:

1. **Identify Entity Types** - Detect if query is about tables, columns, features, metrics, etc.
2. **Select Collections** - Choose appropriate ChromaDB collections to search
3. **Build Filters** - Construct metadata filters for product, category, etc.
4. **Discover Edges** - Find relevant relationships via `mdl_contextual_edges`
5. **Prune Results** - Use edge pruning agent to select most relevant edges

---

## Next Steps

1. ✅ Define knowledge graph structure (this document)
2. ⏳ Create PostgreSQL migration script
3. ⏳ Create store mapping configuration
4. ⏳ Update indexing CLI to populate all stores
5. ⏳ Create integration tests
6. ⏳ Add examples and usage guide
