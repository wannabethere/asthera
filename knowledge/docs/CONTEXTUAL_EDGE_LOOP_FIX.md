# Contextual Edge Reasoning Loop Fix

## Problem

The MDL reasoning graph was appearing to "loop" during the contextual edge reasoning phase when running queries like:

```bash
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to user access request and their soc2 compliance controls?" \
    --product-name Snyk \
    --actor "Compliance Officer" \
    --project-id Snyk
```

**Symptoms:**
- Test appears to hang or loop indefinitely
- Logs show repeated queries to `contextual_edges` collection
- All queries return 0 results
- Multiple queries like "OrgAttributes What tables are related to..." repeated

## Root Cause

The `MDLContextualPlannerNode` processes up to 20 curated tables, and for each table makes 3 edge searches:
1. Edges where table is source entity
2. Edges where table is target entity  
3. General semantic search for related edges

Additionally, it searches for products, policies, compliance controls, and risk controls per table.

This results in ~60-100 queries total. When ALL queries return 0 results (because the collection is empty or entity IDs don't match), the processing takes a long time and feels like an infinite loop.

**Why queries returned 0 results:**
- The `contextual_edges` collection may be empty, OR
- The entity ID format used in queries (`entity_{product}_{table}`) doesn't match the actual entity IDs in the collection

## Solution

Three optimizations were implemented:

### 1. Early Exit on Empty Collection

After checking 5 tables with 0 edges found, the node now exits early with a warning:

```python
# Early exit check: if we've checked 5 tables and found 0 edges, collection is likely empty
if tables_checked >= 5 and total_edges_found == 0:
    logger.warning(
        f"MDLContextualPlannerNode: ⚠️  No edges found after checking {tables_checked} tables. "
        f"The contextual_edges collection may be empty or entity IDs don't match. "
        f"Skipping remaining {len(curated_tables_info) - tables_checked} tables to avoid excessive queries."
    )
    break
```

This reduces queries from ~100 down to ~25.

### 2. Skip LLM Call When No Edges Found

If no edges are discovered, the LLM call is skipped and an empty contextual plan is returned:

```python
if total_edges_found == 0:
    logger.warning(
        f"MDLContextualPlannerNode: No edges found for any curated table. "
        f"Returning empty contextual plan and proceeding to next step."
    )
    state["contextual_plan"] = {
        "table_edges": [],
        "reasoning": "No contextual edges found in collection..."
    }
    return state
```

### 3. Better Diagnostic Logging

Added logging to show which entity IDs are being searched (for first 3 tables):

```python
if tables_checked <= 3:
    logger.info(f"MDLContextualPlannerNode: Searching for edges with entity_id='{table_entity_id}', product_name='{product_name}'")
```

## Diagnostic Tool

A diagnostic script was created to help identify entity ID format mismatches:

```bash
python3 -m diagnose_contextual_edges --product-name Snyk --table-name OrgAttributes
```

This will:
1. Check if the collection has data
2. Show sample entity IDs in the collection
3. Test specific table queries
4. Identify entity ID format mismatches
5. Suggest fixes

## Usage

### Run the test with the fixes:

```bash
cd /Users/sameermangalampalli/flowharmonicai/knowledge

python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to user access request and their soc2 compliance controls?" \
    --product-name Snyk \
    --actor "Compliance Officer" \
    --project-id Snyk
```

Expected behavior:
- If collection is empty: Test will complete quickly (~30 seconds) with warnings
- If entity IDs don't match: Test will show which entity IDs were searched in first 3 tables
- Test will proceed to completion even without edges

### Run diagnostics:

```bash
python3 -m diagnose_contextual_edges --product-name Snyk --table-name OrgAttributes
```

### Fix entity ID mismatches:

If diagnostics show entity ID format differs:

**Option 1: Update code to match data format**
- Edit `app/agents/mdl_reasoning_nodes.py` line 2978
- Change entity ID construction to match actual format

**Option 2: Re-index data with correct format**
- Update indexing pipeline to use `entity_{product}_{table}` format
- Re-run indexing to populate `contextual_edges` collection

## Testing

The fixes ensure:
- ✅ Test completes in reasonable time (30-60s instead of hanging)
- ✅ Clear warning messages explain what's happening  
- ✅ Workflow continues gracefully even without edges
- ✅ Diagnostic information helps identify root cause
- ✅ Reduced from ~100 queries to ~25 when collection is empty

## Files Modified

1. `app/agents/mdl_reasoning_nodes.py`:
   - Added early exit logic
   - Added diagnostic logging
   - Skip LLM call when no edges found

2. `diagnose_contextual_edges.py` (new):
   - Diagnostic script to check collection and entity IDs

3. `docs/CONTEXTUAL_EDGE_LOOP_FIX.md` (this file):
   - Documentation of the fix
