# Relationship Workflow with User-Provided Tables

## Overview

The relationship workflow has been enhanced to give users greater control over semantic definitions and relationships by allowing them to pass table definitions directly instead of relying on domain ID lookup. This approach provides:

- **Greater Control**: Users define exactly which tables to analyze
- **Flexibility**: Can analyze tables from different sources or configurations
- **Semantic Control**: Users provide business context and descriptions
- **Standalone Analysis**: Can analyze tables without full workflow setup

## New Request Models

### TableDefinition
```python
class TableDefinition(BaseModel):
    name: str                    # Table name
    display_name: Optional[str]  # Display name for the table
    description: Optional[str]   # Table description
    columns: List[Dict[str, Any]] # List of column definitions
    metadata: Optional[Dict[str, Any]] # Additional table metadata
```

### ColumnDefinition
```python
class ColumnDefinition(BaseModel):
    name: str                    # Column name
    display_name: Optional[str]  # Display name for the column
    data_type: str              # Data type of the column
    description: Optional[str]   # Column description
    is_primary_key: bool        # Whether this column is a primary key
    is_nullable: bool           # Whether this column can be null
    is_foreign_key: bool        # Whether this column is a foreign key
    usage_type: Optional[str]   # Business usage type of the column
    metadata: Optional[Dict[str, Any]] # Additional column metadata
```

### Enhanced RelationshipWorkflowRequest
```python
class RelationshipWorkflowRequest(BaseModel):
    session_id: Optional[str]                    # Session ID (optional)
    domain_id: str                              # Domain ID for the workflow
    domain_name: Optional[str]                  # Domain name
    business_domain: Optional[str]              # Business domain
    tables: List[TableDefinition]               # List of table definitions to analyze
    business_context: Optional[Dict[str, Any]]  # Additional business context
```

## API Endpoints

### 1. Generate Relationship Recommendations (Workflow Mode)
**POST** `/workflow/relationships/recommendations`

Generates relationship recommendations for tables within a workflow session.

**Request Example:**
```json
{
  "session_id": "workflow_session_123",
  "domain_id": "sales_analytics_001",
  "domain_name": "Sales Analytics",
  "business_domain": "Sales",
  "tables": [
    {
      "name": "customers",
      "display_name": "Customer Information",
      "description": "Stores customer details and demographics",
      "columns": [
        {
          "name": "customer_id",
          "data_type": "INTEGER",
          "description": "Unique customer identifier",
          "is_primary_key": true,
          "is_nullable": false,
          "usage_type": "identifier"
        },
        {
          "name": "customer_name",
          "data_type": "VARCHAR(100)",
          "description": "Full name of the customer",
          "is_nullable": false,
          "usage_type": "attribute"
        },
        {
          "name": "email",
          "data_type": "VARCHAR(255)",
          "description": "Customer email address",
          "is_nullable": true,
          "usage_type": "identifier"
        }
      ],
      "metadata": {
        "business_context": {
          "business_entity": "Customer",
          "data_owner": "Sales Team",
          "update_frequency": "Daily"
        }
      }
    },
    {
      "name": "orders",
      "display_name": "Customer Orders",
      "description": "Stores order information and line items",
      "columns": [
        {
          "name": "order_id",
          "data_type": "INTEGER",
          "description": "Unique order identifier",
          "is_primary_key": true,
          "is_nullable": false,
          "usage_type": "identifier"
        },
        {
          "name": "customer_id",
          "data_type": "INTEGER",
          "description": "Reference to customer who placed the order",
          "is_foreign_key": true,
          "is_nullable": false,
          "usage_type": "identifier"
        },
        {
          "name": "order_date",
          "data_type": "TIMESTAMP",
          "description": "Date and time when order was placed",
          "is_nullable": false,
          "usage_type": "timestamp"
        },
        {
          "name": "total_amount",
          "data_type": "DECIMAL(10,2)",
          "description": "Total order amount",
          "is_nullable": false,
          "usage_type": "measure"
        }
      ]
    }
  ],
  "business_context": {
    "industry": "E-commerce",
    "business_process": "Order Management",
    "key_metrics": ["Customer Lifetime Value", "Order Conversion Rate"],
    "data_governance": {
      "privacy_level": "PII",
      "retention_policy": "7 years",
      "access_control": "Role-based"
    }
  }
}
```

### 2. Analyze Tables for Relationships (Standalone Mode)
**POST** `/workflow/relationships/analyze-tables`

Analyzes specific tables for relationships without requiring workflow setup. Useful for:
- Quick relationship analysis
- Testing different table configurations
- Getting recommendations for tables from different sources

**Request Example:** Same as above, but no session_id required.

### 3. Add Custom Relationship
**POST** `/workflow/relationships/custom`

Adds a custom relationship that may not have been automatically detected.

**Request Example:**
```json
{
  "from_table": "customers",
  "to_table": "orders",
  "relationship_type": "one_to_many",
  "from_column": "customer_id",
  "to_column": "customer_id",
  "name": "customer_orders",
  "description": "A customer can have multiple orders",
  "confidence_score": 1.0,
  "reasoning": "Business rule: One customer can place multiple orders over time",
  "business_justification": "Essential for customer analytics and order tracking"
}
```

## Enhanced MDL Generation

The new approach generates enhanced MDL (Model Definition Language) that includes:

### User-Provided Context
- Table-level business context
- Column-level business descriptions
- Enhanced metadata for better semantic analysis

### Example MDL Output
```json
{
  "tables": [
    {
      "name": "customers",
      "display_name": "Customer Information",
      "description": "Stores customer details and demographics",
      "user_provided": true,
      "business_context": {
        "business_entity": "Customer",
        "data_owner": "Sales Team",
        "update_frequency": "Daily"
      },
      "columns": [
        {
          "name": "customer_id",
          "display_name": "Customer ID",
          "data_type": "INTEGER",
          "description": "Unique customer identifier",
          "is_primary_key": true,
          "is_nullable": false,
          "usage_type": "identifier",
          "business_description": "Primary identifier for customer records"
        }
      ]
    }
  ],
  "domain": {
    "id": "sales_analytics_001",
    "name": "Sales Analytics",
    "business_domain": "Sales",
    "purpose": "Generate relationship recommendations for user-provided tables",
    "enhanced_context": true
  },
  "business_context": {
    "industry": "E-commerce",
    "business_process": "Order Management",
    "key_metrics": ["Customer Lifetime Value", "Order Conversion Rate"]
  }
}
```

## Benefits of the New Approach

### 1. **Greater Semantic Control**
- Users provide business context and descriptions
- Column usage types are explicitly defined
- Business rules can be embedded in metadata

### 2. **Flexibility**
- Can analyze tables from different sources
- No dependency on workflow state
- Can test different table configurations

### 3. **Enhanced Analysis**
- Better understanding of business relationships
- More accurate relationship recommendations
- Context-aware analysis

### 4. **Standalone Usage**
- Can analyze tables without full workflow setup
- Useful for quick prototyping
- Can be integrated into other systems

## Migration from Old Approach

### Before (Domain ID Lookup)
```python
# Old approach required tables to be in workflow state
recommendations = await workflow_service.get_comprehensive_relationship_recommendations(domain_context)
```

### After (User-Provided Tables)
```python
# New approach accepts tables directly
recommendations = await workflow_service.get_relationship_recommendations_from_tables(
    user_tables, domain_context, business_context
)
```

### Backward Compatibility
The old approach is still supported for existing workflows. The new approach is an enhancement that provides additional capabilities.

## Best Practices

### 1. **Table Definitions**
- Provide clear, descriptive names
- Include business descriptions for tables and columns
- Use appropriate data types and constraints

### 2. **Business Context**
- Include industry-specific information
- Define key business processes
- Specify data governance requirements

### 3. **Column Metadata**
- Use appropriate usage types (identifier, measure, attribute, etc.)
- Include business rules and constraints
- Provide examples where helpful

### 4. **Relationship Analysis**
- Start with core business entities
- Include all relevant tables for comprehensive analysis
- Provide context about business relationships

## Example Use Cases

### 1. **E-commerce Domain**
- Customers, Orders, Products, Categories
- Business context: Online retail, customer analytics

### 2. **Financial Services**
- Accounts, Transactions, Customers, Products
- Business context: Banking, risk management

### 3. **Healthcare**
- Patients, Visits, Providers, Procedures
- Business context: Patient care, clinical analytics

### 4. **Manufacturing**
- Products, Inventory, Suppliers, Orders
- Business context: Supply chain, production planning

## Error Handling

The system provides comprehensive error handling:

- **Validation Errors**: Clear messages for invalid table definitions
- **Service Errors**: Detailed error information from relationship service
- **Context Errors**: Guidance on missing business context

## Performance Considerations

- **Table Count**: Optimal for 2-10 tables per analysis
- **Column Count**: Handles tables with up to 100+ columns
- **Context Size**: Business context should be concise but informative
- **Caching**: Results are cached when using workflow sessions
