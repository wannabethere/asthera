# MDL Edge Types Reference

## Overview

MDL edge types define the relationships between entities in the semantic layer contextual graph. This document provides a complete reference of all 25+ edge types, their semantics, priorities, and usage examples.

## Edge Type Priority Levels

**Critical (1.0)**: Essential structure and question-answering
**High (0.85-0.95)**: Important relationships and features  
**Medium (0.7-0.8)**: Supporting information
**Low (0.5-0.7)**: Supplementary details

## Structural Edge Types

### BELONGS_TO_TABLE

**Priority**: 0.95 (Critical)

**Description**: Column belongs to a table

**Semantic Meaning**: Represents the fundamental relationship between a column and its parent table in the database schema

**Valid Edges**:
- Source: `column`
- Target: `table`

**Required Metadata**:
- `column_name`: Column name
- `table_name`: Table name  
- `data_type`: Data type

**Optional Metadata**:
- `is_primary_key`: Boolean
- `is_foreign_key`: Boolean
- `is_nullable`: Boolean
- `default_value`: Default value

**Examples**:
- Column 'id' belongs to table 'AssetAttributes'
- Column 'email' belongs to table 'Users'

---

### HAS_COLUMN

**Priority**: 0.9 (Critical)

**Description**: Table has a column

**Semantic Meaning**: Inverse relationship of BELONGS_TO_TABLE, useful for table-centric queries

**Valid Edges**:
- Source: `table`
- Target: `column`

**Required Metadata**:
- `table_name`: Table name
- `column_name`: Column name

**Optional Metadata**:
- `column_order`: Order in table
- `is_indexed`: Boolean

**Examples**:
- Table 'AssetAttributes' has column 'id'
- Table 'Users' has column 'email'

---

### HAS_MANY_TABLES

**Priority**: 0.8 (High)

**Description**: Schema contains multiple tables

**Semantic Meaning**: Organizational relationship between schema/database and its tables

**Valid Edges**:
- Source: `schema` or `product`
- Target: `table`

**Required Metadata**:
- `schema_name`: Schema name
- `table_name`: Table name

**Optional Metadata**:
- `table_count`: Total tables

**Examples**:
- Snyk schema contains 'AssetAttributes' table
- Database has 'Projects' table

---

### RELATES_TO_TABLE

**Priority**: 0.85 (High)

**Description**: Table-to-table relationship (foreign key, join)

**Semantic Meaning**: Represents relationships between tables through foreign keys or logical joins

**Valid Edges**:
- Source: `table`
- Target: `table`
- Bidirectional: Yes

**Required Metadata**:
- `source_table`: Source table
- `target_table`: Target table
- `relationship_type`: Type (one_to_many, many_to_one, many_to_many)

**Optional Metadata**:
- `join_column`: Column used for join
- `cardinality`: Cardinality description
- `relationship_name`: Relationship name

**Examples**:
- 'AssetAttributes' relates to 'AssetClass' via asset_class_id
- Projects table relates to Organizations table

---

### DERIVED_FROM

**Priority**: 0.75 (Medium)

**Description**: Derived or calculated column

**Semantic Meaning**: Column is calculated or derived from other columns or tables

**Valid Edges**:
- Source: `column`
- Target: `column` or `table`

**Required Metadata**:
- `derived_column`: Derived column name
- `source_entity`: Source entity
- `calculation_logic`: Calculation expression

**Optional Metadata**:
- `dependencies`: List of dependencies

**Examples**:
- Column 'full_name' derived from 'first_name' and 'last_name'
- Column 'risk_score' calculated from vulnerability data

## Category Edge Types

### CATEGORY_CONTAINS_TABLE

**Priority**: 0.8 (High)

**Description**: Category groups related tables

**Semantic Meaning**: Logical grouping of tables by business domain or functionality

**Valid Edges**:
- Source: `category`
- Target: `table`

**Required Metadata**:
- `category_name`: Category name
- `table_name`: Table name

**Optional Metadata**:
- `category_description`: Description
- `table_count`: Tables in category

**Examples**:
- Category 'assets' contains table 'AssetAttributes'
- Category 'vulnerabilities' contains 'VulnerabilityInstances'

---

### TABLE_IN_CATEGORY

**Priority**: 0.8 (High)

**Description**: Table belongs to a category

**Semantic Meaning**: Inverse of CATEGORY_CONTAINS_TABLE, table-centric view

**Valid Edges**:
- Source: `table`
- Target: `category`

**Required Metadata**:
- `table_name`: Table name
- `category_name`: Category name

**Examples**:
- Table 'AssetAttributes' is in category 'assets'

---

### PRODUCT_HAS_CATEGORY

**Priority**: 0.7 (Medium)

**Description**: Product organizes data into categories

**Semantic Meaning**: Top-level organization of product's data model

**Valid Edges**:
- Source: `product`
- Target: `category`

**Required Metadata**:
- `product_name`: Product name
- `category_name`: Category name

**Examples**:
- Snyk has category 'assets'
- Cornerstone has category 'compliance'

## Feature Edge Types

### TABLE_HAS_FEATURE

**Priority**: 0.85 (High)

**Description**: Feature is derived from table

**Semantic Meaning**: Business feature or capability provided by a table

**Valid Edges**:
- Source: `table`
- Target: `feature`

**Required Metadata**:
- `table_name`: Table name
- `feature_name`: Feature name

**Optional Metadata**:
- `feature_description`: Description
- `implementation_details`: Implementation notes

**Examples**:
- Table 'AssetAttributes' provides feature 'asset tracking'
- Table 'VulnerabilityInstances' provides 'vulnerability monitoring'

---

### COLUMN_SUPPORTS_FEATURE

**Priority**: 0.75 (Medium)

**Description**: Column is used in a feature

**Semantic Meaning**: Specific column contributes to a business feature

**Valid Edges**:
- Source: `column`
- Target: `feature`

**Required Metadata**:
- `column_name`: Column name
- `feature_name`: Feature name

**Examples**:
- Column 'severity' supports feature 'risk scoring'

---

### FEATURE_SUPPORTS_CONTROL

**Priority**: 0.9 (Critical)

**Description**: Feature supports a compliance control

**Semantic Meaning**: Links business features to compliance controls they help satisfy

**Valid Edges**:
- Source: `feature`
- Target: `control`

**Required Metadata**:
- `feature_name`: Feature name
- `control_id`: Control ID

**Optional Metadata**:
- `framework`: Framework name
- `evidence_type`: Type of evidence

**Examples**:
- Feature 'access_monitoring' supports control 'CC6.1'
- Feature 'encryption_tracking' supports HIPAA control

## Metric Edge Types

### METRIC_FROM_TABLE

**Priority**: 0.8 (High)

**Description**: Metric calculated from table

**Semantic Meaning**: Business metric derived from table data

**Valid Edges**:
- Source: `metric` or `kpi`
- Target: `table`

**Required Metadata**:
- `metric_name`: Metric name
- `table_name`: Table name

**Optional Metadata**:
- `calculation_method`: Calculation description
- `aggregation_type`: sum, count, avg, etc.

**Examples**:
- Metric 'total_assets' calculated from 'AssetAttributes' table

---

### METRIC_FROM_COLUMN

**Priority**: 0.75 (Medium)

**Description**: Metric calculated from specific column

**Semantic Meaning**: Granular metric based on specific column data

**Valid Edges**:
- Source: `metric` or `kpi`
- Target: `column`

**Required Metadata**:
- `metric_name`: Metric name
- `column_name`: Column name

**Optional Metadata**:
- `aggregation_function`: Aggregation function

**Examples**:
- Metric 'avg_risk_score' calculated from 'risk_score' column

---

### KPI_FROM_METRIC

**Priority**: 0.7 (Medium)

**Description**: KPI based on metric

**Semantic Meaning**: High-level KPI composed from metrics

**Valid Edges**:
- Source: `kpi`
- Target: `metric`

**Required Metadata**:
- `kpi_name`: KPI name
- `metric_name`: Metric name

**Optional Metadata**:
- `threshold`: Threshold value
- `target_value`: Target value

**Examples**:
- KPI 'security_posture' based on multiple risk metrics

## Example Edge Types

### EXAMPLE_USES_TABLE

**Priority**: 0.85 (High)

**Description**: Example query uses table

**Semantic Meaning**: Links example queries to the tables they reference

**Valid Edges**:
- Source: `example` or `query_pattern`
- Target: `table`

**Required Metadata**:
- `example_id`: Example ID
- `table_name`: Table name

**Optional Metadata**:
- `query_text`: Query text
- `use_case`: Use case description

**Examples**:
- Example 'get_asset_count' uses table 'AssetAttributes'

---

### QUESTION_ANSWERED_BY_TABLE

**Priority**: 0.9 (Critical)

**Description**: Natural language question can be answered by table

**Semantic Meaning**: Maps user questions to relevant tables

**Valid Edges**:
- Source: `natural_question`
- Target: `table`

**Required Metadata**:
- `question`: Question text
- `table_name`: Table name

**Optional Metadata**:
- `confidence_score`: Confidence

**Examples**:
- Question "How many assets do we have?" answered by 'AssetAttributes'

## Instruction Edge Types

### INSTRUCTION_APPLIES_TO_TABLE

**Priority**: 0.8 (High)

**Description**: Table-specific instruction

**Semantic Meaning**: Specific guidance for working with a table

**Valid Edges**:
- Source: `instruction`
- Target: `table`

**Required Metadata**:
- `instruction_id`: Instruction ID
- `table_name`: Table name

**Optional Metadata**:
- `usage_context`: Context

**Examples**:
- Instruction 'join with AssetClass' applies to 'AssetAttributes'

---

### INSTRUCTION_APPLIES_TO_PRODUCT

**Priority**: 0.75 (Medium)

**Description**: Product-specific instruction or best practice

**Semantic Meaning**: General instructions for working with a product

**Valid Edges**:
- Source: `instruction`
- Target: `product`

**Required Metadata**:
- `instruction_id`: Instruction ID
- `product_name`: Product name

**Examples**:
- Instruction 'use API v3' applies to Snyk product

## Usage in Queries

### Query Type Mapping

**Table Queries**: BELONGS_TO_TABLE, HAS_COLUMN, HAS_MANY_TABLES

**Relationship Queries**: RELATES_TO_TABLE, DERIVED_FROM

**Category Queries**: CATEGORY_CONTAINS_TABLE, TABLE_IN_CATEGORY

**Feature Queries**: TABLE_HAS_FEATURE, FEATURE_SUPPORTS_CONTROL

**Metric Queries**: METRIC_FROM_TABLE, KPI_FROM_METRIC

**Example Queries**: EXAMPLE_USES_TABLE, QUESTION_ANSWERED_BY_TABLE

## Edge Validation

Use `validate_mdl_edge()` to validate edge structure:

```python
from app.utils.mdl_edge_types import validate_mdl_edge

is_valid, errors = validate_mdl_edge(
    edge_type="BELONGS_TO_TABLE",
    source_entity_type="column",
    target_entity_type="table",
    metadata={
        "column_name": "id",
        "table_name": "AssetAttributes",
        "data_type": "varchar"
    }
)
```

## Priority-Based Selection

Edge pruning agent uses priorities for selection:

1. **Critical edges (0.9-1.0)**: Always included if relevant
2. **High edges (0.8-0.9)**: Preferred when available
3. **Medium edges (0.7-0.8)**: Included for context
4. **Low edges (0.5-0.7)**: Included if space permits

## Complete Edge Type List

1. BELONGS_TO_TABLE (0.95)
2. HAS_COLUMN (0.9)
3. QUESTION_ANSWERED_BY_TABLE (0.9)
4. FEATURE_SUPPORTS_CONTROL (0.9)
5. HAS_MANY_TABLES (0.8)
6. RELATES_TO_TABLE (0.85)
7. TABLE_HAS_FEATURE (0.85)
8. TABLE_PROVIDES_EVIDENCE (0.85)
9. EXAMPLE_USES_TABLE (0.85)
10. QUESTION_ANSWERED_BY_COLUMN (0.85)
11. CATEGORY_CONTAINS_TABLE (0.8)
12. TABLE_IN_CATEGORY (0.8)
13. METRIC_FROM_TABLE (0.8)
14. COLUMN_PROVIDES_EVIDENCE (0.8)
15. INSTRUCTION_APPLIES_TO_TABLE (0.8)
16. PATTERN_USES_TABLE (0.8)
17. DERIVED_FROM (0.75)
18. COLUMN_SUPPORTS_FEATURE (0.75)
19. METRIC_FROM_COLUMN (0.75)
20. EXAMPLE_USES_COLUMN (0.8)
21. INSTRUCTION_APPLIES_TO_CATEGORY (0.75)
22. INSTRUCTION_APPLIES_TO_PRODUCT (0.75)
23. PRODUCT_HAS_CATEGORY (0.7)
24. KPI_FROM_METRIC (0.7)
25. FEATURE_DEPENDS_ON_FEATURE (0.7)
26. PATTERN_USES_RELATIONSHIP (0.75)

## See Also

- [MDL Contextual Indexing Overview](./MDL_CONTEXTUAL_INDEXING.md)
- [MDL Extractors Documentation](./MDL_EXTRACTORS.md)
- [MDL Indexing Guide](./MDL_INDEXING_GUIDE.md)
