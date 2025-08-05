# Enhanced Column Definitions

This document explains how to use the enhanced column definitions feature in the Add Table request and how it enhances column documentation with LLM-generated insights.

## Overview

The `EnhancedColumnDefinition` class provides comprehensive column documentation that goes beyond basic schema information to include business context, data quality rules, and usage recommendations.

## Key Features

### Enhanced Column Properties

Each enhanced column definition includes:

- **Business-friendly names and descriptions**
- **Usage type classification** (dimension, measure, attribute, identifier, timestamp, flag, metadata, calculated)
- **Data quality checks and business rules**
- **Privacy classification** (public, internal, confidential, restricted)
- **Aggregation and filtering suggestions**
- **Related business concepts**
- **Example values and patterns**

### Usage Types

The system classifies columns into the following usage types:

- `dimension` - Categorical data for grouping/filtering
- `measure` - Numeric data for aggregation
- `attribute` - Descriptive information
- `identifier` - Unique identifiers
- `timestamp` - Date/time information
- `flag` - Boolean indicators
- `metadata` - System/technical information
- `calculated` - Derived/computed values

## API Usage

### 1. Enhanced Add Table Response

When you add a table using the `/workflow/table` endpoint, the response now includes enhanced column definitions:

```python
POST /workflow/table
{
    "dataset_id": "your_dataset_id",
    "schema": {
        "table_name": "sales_data",
        "table_description": "Sales transaction data",
        "columns": [
            {
                "name": "transaction_id",
                "data_type": "INTEGER",
                "is_nullable": false,
                "is_primary_key": true
            },
            {
                "name": "amount",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": false
            }
        ]
    }
}
```

**Enhanced Response:**
```json
{
    "table_id": "table_123",
    "name": "sales_data",
    "display_name": "Sales Data",
    "description": "Comprehensive sales transaction data for business analysis",
    "business_purpose": "Track and analyze sales performance across different dimensions",
    "primary_use_cases": [
        "Sales performance analysis",
        "Revenue reporting",
        "Customer behavior analysis"
    ],
    "enhanced_columns": [
        {
            "column_name": "transaction_id",
            "display_name": "Transaction ID",
            "description": "Unique identifier for each sales transaction",
            "business_description": "Primary key used to uniquely identify individual sales transactions",
            "usage_type": "identifier",
            "data_type": "INTEGER",
            "example_values": ["1001", "1002", "1003"],
            "business_rules": [
                "Must be unique across all transactions",
                "Cannot be null",
                "Auto-incrementing sequence"
            ],
            "data_quality_checks": [
                "Check for duplicate values",
                "Validate non-null constraint",
                "Verify sequential ordering"
            ],
            "related_concepts": ["Transaction", "Sales", "Order"],
            "privacy_classification": "internal",
            "aggregation_suggestions": ["COUNT"],
            "filtering_suggestions": [
                "Filter by date range",
                "Filter by customer",
                "Filter by product category"
            ],
            "json_metadata": {
                "typical_cardinality": "high",
                "business_importance": "critical",
                "analysis_frequency": "daily"
            }
        },
        {
            "column_name": "amount",
            "display_name": "Transaction Amount",
            "description": "Monetary value of the sales transaction",
            "business_description": "Total dollar amount for each sales transaction",
            "usage_type": "measure",
            "data_type": "DECIMAL(10,2)",
            "example_values": ["99.99", "149.50", "299.00"],
            "business_rules": [
                "Must be positive value",
                "Cannot exceed maximum transaction limit",
                "Must be in USD currency"
            ],
            "data_quality_checks": [
                "Check for negative values",
                "Validate decimal precision",
                "Check for reasonable amount ranges"
            ],
            "related_concepts": ["Revenue", "Sales", "Money"],
            "privacy_classification": "confidential",
            "aggregation_suggestions": [
                "SUM",
                "AVG",
                "MIN",
                "MAX",
                "COUNT"
            ],
            "filtering_suggestions": [
                "Filter by amount ranges",
                "Filter by high-value transactions",
                "Filter by discount amounts"
            ],
            "json_metadata": {
                "typical_cardinality": "medium",
                "business_importance": "critical",
                "analysis_frequency": "real-time"
            }
        }
    ]
}
```

### 2. Get Enhanced Columns for Existing Tables

You can retrieve enhanced column definitions for existing tables:

```python
GET /workflow/table/{table_id}/enhanced-columns
```

**Response:**
```json
{
    "table_id": "table_123",
    "table_name": "sales_data",
    "enhanced_columns": [
        {
            "column_name": "transaction_id",
            "display_name": "Transaction ID",
            "description": "Unique identifier for each sales transaction",
            "business_description": "Primary key used to uniquely identify individual sales transactions",
            "usage_type": "identifier",
            "data_type": "INTEGER",
            "example_values": ["1001", "1002", "1003"],
            "business_rules": [
                "Must be unique across all transactions",
                "Cannot be null",
                "Auto-incrementing sequence"
            ],
            "data_quality_checks": [
                "Check for duplicate values",
                "Validate non-null constraint",
                "Verify sequential ordering"
            ],
            "related_concepts": ["Transaction", "Sales", "Order"],
            "privacy_classification": "internal",
            "aggregation_suggestions": ["COUNT"],
            "filtering_suggestions": [
                "Filter by date range",
                "Filter by customer",
                "Filter by product category"
            ],
            "json_metadata": {
                "typical_cardinality": "high",
                "business_importance": "critical",
                "analysis_frequency": "daily"
            }
        }
    ]
}
```

## Database Storage

Enhanced column definitions are stored in two places in the database:

### 1. Table Metadata (`Table.json_metadata`)

The complete enhanced column definitions are stored in the table's JSON metadata:

```json
{
    "columns": [...],  // Original column definitions
    "enhanced_columns": [
        {
            "column_name": "transaction_id",
            "display_name": "Transaction ID",
            "description": "Unique identifier for each sales transaction",
            "business_description": "Primary key used to uniquely identify individual sales transactions",
            "usage_type": "identifier",
            "data_type": "INTEGER",
            "example_values": ["1001", "1002", "1003"],
            "business_rules": [
                "Must be unique across all transactions",
                "Cannot be null",
                "Auto-incrementing sequence"
            ],
            "data_quality_checks": [
                "Check for duplicate values",
                "Validate non-null constraint",
                "Verify sequential ordering"
            ],
            "related_concepts": ["Transaction", "Sales", "Order"],
            "privacy_classification": "internal",
            "aggregation_suggestions": ["COUNT"],
            "filtering_suggestions": [
                "Filter by date range",
                "Filter by customer",
                "Filter by product category"
            ],
            "json_metadata": {
                "typical_cardinality": "high",
                "business_importance": "critical",
                "analysis_frequency": "daily"
            }
        }
    ],
    "semantic_description": "...",
    "business_purpose": "...",
    "primary_use_cases": [...],
    "key_relationships": [...],
    "data_lineage": "...",
    "update_frequency": "...",
    "data_retention": "...",
    "access_patterns": [...],
    "performance_considerations": [...]
}
```

### 2. Column Metadata (`SQLColumn.json_metadata`)

Individual column enhanced data is also stored in each column's metadata:

```json
{
    "business_description": "Primary key used to uniquely identify individual sales transactions",
    "usage_type": "identifier",
    "example_values": ["1001", "1002", "1003"],
    "business_rules": [
        "Must be unique across all transactions",
        "Cannot be null",
        "Auto-incrementing sequence"
    ],
    "data_quality_checks": [
        "Check for duplicate values",
        "Validate non-null constraint",
        "Verify sequential ordering"
    ],
    "related_concepts": ["Transaction", "Sales", "Order"],
    "privacy_classification": "internal",
    "aggregation_suggestions": ["COUNT"],
    "filtering_suggestions": [
        "Filter by date range",
        "Filter by customer",
        "Filter by product category"
    ],
    "enhanced_metadata": {
        "typical_cardinality": "high",
        "business_importance": "critical",
        "analysis_frequency": "daily"
    }
}
```

### Storage Strategy

1. **Table Creation**: Enhanced columns are generated and stored in table metadata during table creation
2. **Retrieval**: When requesting enhanced columns, the system first checks table metadata
3. **Fallback**: If not found in metadata, generates with LLM and stores for future use
4. **Persistence**: All enhanced column data is persisted in the database for fast retrieval

## Benefits

### For Business Users
- **Clear understanding** of what each column represents
- **Business rules** and data quality expectations
- **Usage recommendations** for analysis and reporting
- **Privacy considerations** for data handling

### For Data Analysts
- **Aggregation suggestions** for common analysis patterns
- **Filtering recommendations** for data exploration
- **Related concepts** for understanding data relationships
- **Example values** for data validation

### For Developers
- **Technical descriptions** for implementation
- **Data quality checks** for validation logic
- **Business context** for feature development
- **Metadata** for system integration

## Integration with LLM

The enhanced column definitions are generated using the `LLMSchemaDocumentationGenerator` through the `DomainWorkflowService` which:

1. **Analyzes column context** within the table and domain
2. **Generates business-friendly descriptions** using LLM
3. **Classifies usage types** based on data characteristics
4. **Suggests business rules** and data quality checks
5. **Provides privacy classifications** based on data sensitivity

## Architecture

The enhanced column definitions feature follows a clean architecture pattern:

### Service Layer (`DomainWorkflowService`)
- **`add_table()`**: Main method that orchestrates table creation with enhanced documentation
- **`create_enhanced_columns()`**: Creates enhanced column definitions with LLM-generated insights
- **`get_enhanced_table_response()`**: Formats the response with all enhanced column data
- **`get_enhanced_columns_for_table()`**: Retrieves enhanced column definitions for existing tables

### Router Layer (`project_workflow.py`)
- **`api_add_table()`**: Handles HTTP requests and delegates to service layer
- **`api_get_table_enhanced_columns()`**: Retrieves enhanced columns for existing tables

This separation ensures:
- **Business logic** is contained in the service layer
- **HTTP concerns** are handled in the router layer
- **Reusability** of enhanced column logic across different endpoints
- **Testability** of business logic independent of HTTP layer

## Best Practices

1. **Provide rich domain context** when creating tables for better LLM analysis
2. **Include sample data** when available for more accurate column analysis
3. **Review and validate** generated business rules and data quality checks
4. **Update enhanced definitions** as business requirements evolve
5. **Use privacy classifications** to ensure proper data handling

## Example Use Cases

### 1. Data Catalog Enhancement
Use enhanced column definitions to build a comprehensive data catalog with business context.

### 2. Data Quality Monitoring
Implement the suggested data quality checks to monitor data integrity.

### 3. Self-Service Analytics
Provide business users with clear guidance on how to use each column in their analysis.

### 4. Compliance Reporting
Use privacy classifications to ensure proper data handling for compliance requirements.

### 5. Data Lineage Documentation
Track how enhanced column definitions evolve as data flows through the system. 