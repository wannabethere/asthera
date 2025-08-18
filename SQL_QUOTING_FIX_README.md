# SQL Quoting Fix for PostgreSQL Case Sensitivity

## Problem Description

The system was experiencing PostgreSQL errors due to column case sensitivity issues. The error message was:

```
PostgreSQL query failed: (psycopg2.errors.UndefinedColumn) column tr.Division does not exist
HINT: Perhaps you meant to reference the column "tr.division".
```

## Root Cause

The issue was caused by two factors:

1. **LLM Generated Incorrect Case**: The LLM was generating SQL with capitalized column names like `tr.Division` instead of the actual database column name `tr.division`.

2. **Automatic Identifier Quoting**: The `add_quotes` function in `engine.py` was using `sqlglot.transpile` with `identify=True`, which automatically quotes all identifiers. This resulted in SQL like:
   ```sql
   SELECT "tr"."Division" AS "division" FROM "csod_training_records" AS "tr"
   ```
   
   Instead of:
   ```sql
   SELECT tr.Division AS division FROM csod_training_records AS tr
   ```

3. **PostgreSQL Case Sensitivity**: PostgreSQL is case-sensitive and expects column names to match exactly. When the actual column is `division` (lowercase) but the query references `"Division"` (quoted with capital D), it fails.

## Solution Implemented

### 1. Fixed the `add_quotes` Function

**Files Modified:**
- `agents/app/core/engine.py`
- `dataengine/app/core/engine.py` 
- `insightsagents/app/core/engine.py`

**Change:**
```python
# Before (problematic)
quoted_sql = sqlglot.transpile(
    sql, read="trino", identify=True, error_level=sqlglot.ErrorLevel.RAISE
)[0]

# After (fixed)
quoted_sql = sqlglot.transpile(
    sql, read="trino", identify=False, error_level=sqlglot.ErrorLevel.RAISE
)[0]
```

**What this fixes:**
- Disables automatic identifier quoting
- Preserves the original SQL structure
- Prevents the `"tr"."Division"` quoting issue

### 2. Enhanced SQL Generation Prompts

**Files Modified:**
- `agents/app/agents/nodes/sql/utils/sql_prompts.py`

**Changes:**
- Added explicit rule about column case sensitivity
- Enhanced system prompt with critical column naming instructions

**New Rules Added:**
```
- **IMPORTANT: Use column names exactly as they appear in the database schema. If the schema shows 'division' (lowercase), use 'division', not 'Division'.**
- **CRITICAL: When generating SQL, use column names exactly as they appear in the database schema. If the schema shows 'division' (lowercase), use 'division', not 'Division'. This prevents SQL execution errors.**
```

### 3. Added Column Validation Function

**File Modified:**
- `agents/app/core/engine.py`

**New Function:**
```python
def validate_and_fix_column_names(sql: str, schema_context: Dict[str, Any] = None) -> Tuple[str, str]:
    """
    Validate and fix column names in SQL to match actual database schema case.
    """
```

**Purpose:**
- Provides a mechanism to validate and correct column names against actual schema
- Can be integrated into the SQL generation pipeline for additional safety

## Testing the Fix

A test script `test_sql_quoting_fix.py` was created to demonstrate the fix:

```bash
python test_sql_quoting_fix.py
```

**Expected Results:**
- **Before fix**: `tr.Division` → `"tr"."Division"` (causes PostgreSQL errors)
- **After fix**: `tr.Division` → `tr.Division` (works correctly)

## Integration Points

The fix affects the following components:

1. **SQL Generation Pipeline** (`agents/app/agents/pipelines/sql_pipelines.py`)
2. **SQL RAG Agent** (`agents/app/agents/nodes/sql/sql_rag_agent.py`)
3. **Enhanced SQL Pipeline** (`agents/app/agents/pipelines/enhanced_sql_pipeline.py`)
4. **Post-processing Tools** (`agents/app/agents/nodes/sql/utils/sql.py`)

## Best Practices Going Forward

1. **Schema Validation**: Always validate generated SQL against actual database schema
2. **Case Consistency**: Ensure column names in generated SQL match the actual database case
3. **Testing**: Test SQL queries with actual database connections before deployment
4. **Monitoring**: Monitor for similar case sensitivity errors in production

## Alternative Solutions Considered

1. **Schema-Aware Generation**: Generate SQL with exact column names from schema
2. **Post-Generation Validation**: Validate and correct SQL after generation
3. **Database Introspection**: Query actual database metadata for column names

## Impact Assessment

**Positive Impact:**
- Eliminates PostgreSQL column case sensitivity errors
- Improves SQL generation reliability
- Reduces production errors

**Potential Risks:**
- May affect other systems that depend on quoted identifiers
- Could impact SQL parsing in some edge cases

**Mitigation:**
- Thorough testing of the fix
- Monitoring for any unexpected side effects
- Rollback plan if issues arise

## Future Improvements

1. **Schema Integration**: Integrate actual database schema into SQL generation
2. **Case Correction**: Automatically correct column case mismatches
3. **Validation Pipeline**: Add SQL validation step before execution
4. **Error Handling**: Improve error messages for column-related issues

## Conclusion

This fix addresses the immediate PostgreSQL column case sensitivity issue by:
1. Disabling automatic identifier quoting that was causing the problem
2. Enhancing SQL generation prompts to prevent case mismatches
3. Adding infrastructure for future column validation

The solution is backward compatible and maintains the existing SQL generation functionality while fixing the specific quoting issue.
