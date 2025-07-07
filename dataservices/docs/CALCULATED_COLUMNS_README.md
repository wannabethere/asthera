# Calculated Columns Documentation

## Overview

Calculated columns are a special type of SQLColumn that represents derived or computed values. They are stored as regular SQLColumns with a specific `column_type` of `'calculated_column'` and have an associated `CalculatedColumn` record that contains the calculation logic.

## Architecture

### Database Schema

```sql
-- SQLColumn table (main column storage)
CREATE TABLE columns (
    column_id UUID PRIMARY KEY,
    table_id UUID REFERENCES tables(table_id),
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    column_type VARCHAR(20) DEFAULT 'column' NOT NULL, -- 'column' or 'calculated_column'
    data_type VARCHAR(50),
    usage_type VARCHAR(50),
    is_nullable BOOLEAN DEFAULT TRUE,
    is_primary_key BOOLEAN DEFAULT FALSE,
    is_foreign_key BOOLEAN DEFAULT FALSE,
    default_value TEXT,
    ordinal_position INTEGER,
    json_metadata JSONB,
    -- ... other standard column fields
);

-- CalculatedColumn table (calculation details)
CREATE TABLE calculated_columns (
    calculated_column_id UUID PRIMARY KEY,
    column_id UUID REFERENCES columns(column_id) ON DELETE CASCADE,
    calculation_sql TEXT NOT NULL,
    function_id UUID REFERENCES sql_functions(function_id),
    dependencies JSONB, -- Array of column/table dependencies
    -- ... other metadata fields
);
```

### Key Concepts

1. **SQLColumn as Base**: All columns (regular and calculated) are stored in the `columns` table
2. **Column Type Distinction**: Calculated columns have `column_type = 'calculated_column'`
3. **Calculation Storage**: The actual calculation logic is stored in the `calculated_columns` table
4. **Function Association**: Calculated columns can optionally reference SQL functions
5. **Dependency Tracking**: Dependencies are tracked to understand column relationships

## Usage Examples

### Creating a Calculated Column

```python
from app.service.models import CalculatedColumnCreate
from app.schemas.dbmodels import SQLColumn, CalculatedColumn

# 1. Create the calculated column data
calc_data = CalculatedColumnCreate(
    name="total_amount",
    display_name="Total Amount",
    description="Total amount (quantity * unit_price)",
    calculation_sql="quantity * unit_price",
    data_type="DECIMAL(10,2)",
    usage_type="calculated",
    is_nullable=True,
    dependencies=["quantity", "unit_price"],
    metadata={
        "business_purpose": "Calculate total sale amount",
        "formula": "quantity * unit_price",
        "category": "financial"
    }
)

# 2. Create the SQLColumn with type 'calculated_column'
column = SQLColumn(
    table_id=table_id,
    name=calc_data.name,
    display_name=calc_data.display_name,
    description=calc_data.description,
    column_type='calculated_column',  # Key distinction!
    data_type=calc_data.data_type,
    usage_type=calc_data.usage_type,
    is_nullable=calc_data.is_nullable,
    ordinal_position=3,
    json_metadata=calc_data.metadata,
    modified_by="user"
)

db.add(column)
await db.commit()
await db.refresh(column)

# 3. Create the associated CalculatedColumn
calc_column = CalculatedColumn(
    column_id=column.column_id,
    calculation_sql=calc_data.calculation_sql,
    function_id=calc_data.function_id,
    dependencies=calc_data.dependencies,
    modified_by="user"
)

db.add(calc_column)
await db.commit()
```

### Using the API

```python
# POST /tables/{table_id}/calculated-columns
response = await client.post(
    f"/tables/{table_id}/calculated-columns",
    json={
        "name": "profit_margin",
        "display_name": "Profit Margin",
        "description": "Profit margin percentage",
        "calculation_sql": "(revenue - cost) / revenue * 100",
        "data_type": "DECIMAL(5,2)",
        "usage_type": "calculated",
        "dependencies": ["revenue", "cost"],
        "metadata": {
            "business_purpose": "Calculate profit margin percentage",
            "formula": "(revenue - cost) / revenue * 100",
            "category": "financial"
        }
    }
)
```

### Querying Calculated Columns

```python
# Get all columns including calculated ones
columns = await db.execute(
    select(SQLColumn)
    .options(selectinload(SQLColumn.calculated_column))
    .where(SQLColumn.table_id == table_id)
    .order_by(SQLColumn.ordinal_position)
)

for column in columns.scalars().all():
    print(f"Column: {column.name} ({column.column_type})")
    if column.column_type == 'calculated_column':
        print(f"  Calculation: {column.calculated_column.calculation_sql}")
        print(f"  Dependencies: {column.calculated_column.dependencies}")
```

## Benefits of This Approach

### 1. **Unified Column Interface**
- All columns (regular and calculated) are treated the same way
- Same querying, filtering, and relationship capabilities
- Consistent API for column operations

### 2. **Type Safety**
- Clear distinction between regular and calculated columns
- Database constraints ensure data integrity
- Easy to identify calculated columns in queries

### 3. **Flexibility**
- Calculated columns can have all standard column properties
- Support for complex calculations with dependencies
- Optional association with SQL functions

### 4. **Performance**
- Calculated columns are stored as regular columns
- No special handling needed for most operations
- Efficient querying and indexing

### 5. **Extensibility**
- Easy to add new column types in the future
- Metadata storage for additional properties
- Version control and audit trail support

## Advanced Features

### SQL Function Integration

```python
# Create a SQL function
function = SQLFunction(
    name="calculate_discount",
    function_sql="""
    CREATE OR REPLACE FUNCTION calculate_discount(amount DECIMAL, discount_rate DECIMAL)
    RETURNS DECIMAL AS $$
    BEGIN
        RETURN amount * (1 - discount_rate);
    END;
    $$ LANGUAGE plpgsql;
    """,
    return_type="DECIMAL",
    parameters=[
        {"name": "amount", "type": "DECIMAL"},
        {"name": "discount_rate", "type": "DECIMAL"}
    ]
)

# Use the function in a calculated column
calc_data = CalculatedColumnCreate(
    name="discounted_amount",
    calculation_sql="calculate_discount(total_amount, discount_rate)",
    function_id=function.function_id,
    dependencies=["total_amount", "discount_rate"]
)
```

### Dependency Management

```python
# Track column dependencies
dependencies = ["quantity", "unit_price", "tax_rate"]

# Validate dependencies exist
for dep in dependencies:
    dep_column = await db.execute(
        select(SQLColumn).where(
            SQLColumn.table_id == table_id,
            SQLColumn.name == dep
        )
    )
    if not dep_column.scalar_one_or_none():
        raise ValueError(f"Dependency column '{dep}' not found")
```

### Business Logic Integration

```python
# Add business metadata
metadata = {
    "business_purpose": "Calculate total revenue after taxes",
    "formula": "quantity * unit_price * (1 + tax_rate)",
    "category": "financial",
    "approval_required": True,
    "data_quality_rules": [
        "tax_rate must be between 0 and 1",
        "quantity must be positive"
    ]
}
```

## Migration Guide

### From Old Approach

If you were previously using a separate table for calculated columns:

```python
# Old approach (deprecated)
class OldCalculatedColumn(Base):
    __tablename__ = 'calculated_columns_old'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    calculation = Column(Text)
    # ... other fields

# New approach
# 1. Create SQLColumn with type 'calculated_column'
# 2. Create associated CalculatedColumn
# 3. Migrate data from old table
```

### Migration Script

```python
async def migrate_calculated_columns():
    """Migrate from old calculated columns to new approach"""
    
    # Get old calculated columns
    old_calc_columns = await db.execute(select(OldCalculatedColumn))
    
    for old_col in old_calc_columns.scalars().all():
        # Create new SQLColumn
        new_column = SQLColumn(
            table_id=old_col.table_id,
            name=old_col.name,
            column_type='calculated_column',
            data_type=old_col.data_type,
            usage_type='calculated',
            modified_by='migration'
        )
        db.add(new_column)
        await db.flush()
        
        # Create associated CalculatedColumn
        calc_column = CalculatedColumn(
            column_id=new_column.column_id,
            calculation_sql=old_col.calculation,
            dependencies=old_col.dependencies,
            modified_by='migration'
        )
        db.add(calc_column)
    
    await db.commit()
```

## Best Practices

### 1. **Naming Conventions**
- Use descriptive names for calculated columns
- Prefix with `calc_` or `computed_` if needed
- Follow consistent naming patterns

### 2. **Documentation**
- Always provide clear descriptions
- Document the calculation logic
- Include business context in metadata

### 3. **Performance**
- Keep calculations simple when possible
- Use SQL functions for complex logic
- Consider caching for expensive calculations

### 4. **Validation**
- Validate dependencies exist
- Check calculation syntax
- Test with sample data

### 5. **Version Control**
- Track changes to calculations
- Maintain audit trail
- Version control calculation logic

## Troubleshooting

### Common Issues

1. **Missing Dependencies**
   ```python
   # Error: Dependency column not found
   # Solution: Ensure all referenced columns exist
   ```

2. **Invalid SQL Syntax**
   ```python
   # Error: Invalid calculation_sql
   # Solution: Validate SQL syntax before saving
   ```

3. **Circular Dependencies**
   ```python
   # Error: Circular dependency detected
   # Solution: Check dependency graph for cycles
   ```

### Debugging

```python
# Check column type
if column.column_type == 'calculated_column':
    print(f"Calculated column: {column.calculated_column.calculation_sql}")

# Verify dependencies
deps = column.calculated_column.dependencies
for dep in deps:
    dep_col = await get_column_by_name(table_id, dep)
    if not dep_col:
        print(f"Missing dependency: {dep}")
```

## Conclusion

The calculated column approach provides a clean, unified way to handle derived data while maintaining the flexibility and power of SQL. By treating calculated columns as special types of SQLColumns, we get the best of both worlds: the simplicity of regular columns and the power of computed values. 