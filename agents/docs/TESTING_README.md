# TABLE_SCHEMA Retrieval Pipeline Testing

The `example_usage.py` file now includes comprehensive testing functionality for the TABLE_SCHEMA retrieval pipeline. This ensures that TABLE_SCHEMA documents contain all necessary information for DDL generation.

## Running Tests

### 1. Complete Example with Tests (Default)
```bash
cd /Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml
python -m agents.app.indexing2.example_usage
```

This runs the complete example including:
- MDL processing
- Search capabilities demonstration
- TF-IDF functionality
- Natural language search
- **TABLE_SCHEMA retrieval pipeline tests**

### 2. Tests Only
```bash
cd /Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml
python -m agents.app.indexing2.example_usage --tests-only
```

This runs only the TABLE_SCHEMA retrieval pipeline tests:
- TABLE_SCHEMA document structure validation
- DDL generation testing
- Retrieval pipeline simulation

## Test Coverage

### 1. TABLE_SCHEMA Document Structure Tests
- ✅ **Required Fields Validation**: Ensures all required fields are present
- ✅ **Table Columns Structure**: Validates `table_columns` field structure
- ✅ **Table Description Structure**: Validates `table_description` field structure
- ✅ **Column Information Completeness**: Tests each column's DDL-ready information

### 2. DDL Generation Tests
- ✅ **Column DDL Statements**: Tests individual column DDL generation
- ✅ **Complete Table DDL**: Tests full table DDL creation
- ✅ **Calculated Columns**: Tests calculated field DDL generation
- ✅ **Business Context**: Validates business context inclusion

### 3. Retrieval Pipeline Simulation
- ✅ **Table Information Extraction**: Tests table metadata extraction
- ✅ **Column Information Extraction**: Tests column data extraction
- ✅ **DDL Generation**: Tests complete DDL generation from TABLE_SCHEMA
- ✅ **Business Context Retrieval**: Tests business context availability
- ✅ **Field Type Classification**: Tests dimension/fact classification

## Test Output

### Successful Test Run
```
============================================================
RUNNING TABLE_SCHEMA RETRIEVAL PIPELINE TESTS
============================================================

=== Testing TABLE_SCHEMA Document Structure ===
Found 2 table documents to test
Testing table document 1: users
✓ table_name: <class 'str'>
✓ display_name: <class 'str'>
✓ description: <class 'str'>
✓ business_purpose: <class 'str'>
✓ primary_key: <class 'str'>
✓ columns: <class 'list'>
✓ table_columns: <class 'list'>
✓ table_description: <class 'dict'>
✓ table_columns: 6 columns
✓ table_description: 15 fields
✅ Table document users structure validated

=== Testing DDL Generation from TABLE_SCHEMA ===
Testing DDL generation for table: users
✓ DDL statement for user_id:   user_id VARCHAR NOT NULL
✓ DDL statement for email:   email VARCHAR NOT NULL
✓ DDL statement for status:   status VARCHAR NOT NULL
✓ DDL statement for created_at:   created_at TIMESTAMP NOT NULL
✓ DDL statement for full_name:   full_name AS (CONCAT(first_name, ' ', last_name))
✓ DDL statement for account_age_days:   account_age_days AS (DATEDIFF(CURRENT_DATE, created_at))
✅ DDL generation test passed for users

=== Testing Retrieval Pipeline Simulation ===
Simulating retrieval pipeline for table: users
✓ Table info extracted: {'name': 'users', 'display_name': 'User Accounts', ...}
✓ DDL statement for user_id: -- user_id: Unique identifier for user accounts
  user_id VARCHAR NOT NULL
✓ Complete DDL for users:
CREATE TABLE users (
  user_id VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  created_at TIMESTAMP NOT NULL,
  full_name AS (CONCAT(first_name, ' ', last_name)),
  account_age_days AS (DATEDIFF(CURRENT_DATE, created_at))
);
✓ Business context: {'business_purpose': 'User management and authentication', ...}
✓ Field classification: {'dimensions': ['email', 'status'], 'facts': [], ...}
✅ Retrieval pipeline simulation completed for users

✅ All TABLE_SCHEMA retrieval pipeline tests passed!
```

## Test Structure

### Required Fields Validation
```python
required_fields = [
    'table_name', 'display_name', 'description', 'business_purpose',
    'primary_key', 'columns', 'table_columns', 'table_description'
]
```

### Column Structure Validation
```python
required_column_fields = [
    'column_name', 'data_type', 'is_primary_key', 'is_nullable',
    'is_calculated', 'field_type', 'column_definition',
    'clean_column_definition', 'extracted_metadata'
]
```

### DDL Generation Testing
```python
# Test individual column DDL
if is_calculated:
    ddl_statement = f"  {column_name} AS ({expression})"
else:
    nullable_clause = "NOT NULL" if not is_nullable else ""
    ddl_statement = f"  {column_name} {data_type} {nullable_clause}".strip()

# Test complete table DDL
complete_ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(ddl_statements) + "\n);"
```

## Benefits

### 1. **Comprehensive Testing** ✅
- Tests all aspects of TABLE_SCHEMA documents
- Validates DDL generation capabilities
- Simulates complete retrieval pipeline

### 2. **Real-world Scenarios** ✅
- Uses actual MDL data for testing
- Tests with various column types (dimensions, facts, calculated)
- Validates business context inclusion

### 3. **Quality Assurance** ✅
- Ensures TABLE_SCHEMA documents contain all necessary information
- Validates DDL generation from single document
- Tests retrieval pipeline efficiency

### 4. **Integrated Workflow** ✅
- Tests run as part of the example workflow
- Can be run independently for focused testing
- Provides comprehensive validation

## Troubleshooting

### Common Issues
1. **No Table Documents Found**: Check MDL processing and storage manager initialization
2. **Missing Required Fields**: Verify TABLE_SCHEMA document structure
3. **DDL Generation Failures**: Check column information completeness

### Debug Mode
Set logging level to DEBUG for detailed output:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Integration

The testing functionality is fully integrated into the example workflow:

1. **Default Mode**: Runs complete example with tests
2. **Tests-Only Mode**: Runs only the TABLE_SCHEMA tests
3. **Comprehensive Coverage**: Tests all aspects of the retrieval pipeline
4. **Quality Assurance**: Ensures TABLE_SCHEMA documents are DDL-ready

This ensures that the TABLE_SCHEMA retrieval pipeline is thoroughly tested and ready for production use!
