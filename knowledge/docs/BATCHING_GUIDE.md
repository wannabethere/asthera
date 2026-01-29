# Batching Guide for MDL Enriched Preview Generation

## Overview

The `create_mdl_enriched_preview.py` script supports **batched parallel processing** to extract metadata from multiple tables concurrently while respecting API rate limits.

## When to Use Batching

### ✅ Use Batching When:
- MDL file has 100+ tables
- Using OpenAI with tier limits
- Risk of hitting rate limits
- Want predictable execution time
- Processing multiple large MDL files

### ❌ Don't Use Batching When:
- MDL file has < 50 tables
- Using self-hosted LLM with no rate limits
- Need absolute fastest execution
- Testing with small sample data

## Batch Size Recommendations

### By LLM Provider

| Provider | Tier/Plan | Recommended Batch Size | Reasoning |
|----------|-----------|----------------------|-----------|
| **OpenAI** | Tier 1 (Free/Basic) | 10-20 | Low rate limits (3 RPM) |
| **OpenAI** | Tier 2 | 30-50 | Moderate limits (50 RPM) |
| **OpenAI** | Tier 3 | 50-100 | High limits (500 RPM) |
| **OpenAI** | Tier 4+ | 100+ or omit | Very high limits (5000+ RPM) |
| **Anthropic Claude** | All tiers | 50-100 | High rate limits |
| **Azure OpenAI** | Standard | 25-50 | Regional limits vary |
| **Local/Ollama** | N/A | 100+ or omit | No rate limits |

### By MDL File Size

| Tables | Recommended Batch Size | Estimated Time |
|--------|----------------------|----------------|
| < 50 | Omit (all at once) | < 1 minute |
| 50-100 | 25-50 | 1-3 minutes |
| 100-300 | 30-50 | 3-7 minutes |
| 300-500 | 50 | 5-10 minutes |
| 500-1000 | 50-100 | 10-20 minutes |
| 1000+ | 100 | 20-40 minutes |

## Usage Examples

### Example 1: Default (All at Once)

```bash
# Best for: Small files (< 50 tables), no rate limits
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file small_mdl.json \
    --product-name "MyProduct"
```

**Output:**
```
Created 42 extraction tasks
Running LLM extraction in parallel (all 42 tables at once)...
This may take a few minutes...
✓ Extracted metadata for 42 tables
  Success: 42, Errors: 0
```

### Example 2: Batched (Recommended)

```bash
# Best for: Large files, rate limit safety
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file snyk_mdl1.json \
    --product-name "Snyk" \
    --batch-size 50
```

**Output:**
```
Created 494 extraction tasks
Running LLM extraction in batches of 50...
Processing batch 1/10 (50 tables)...
  ✓ Completed batch 1
Processing batch 2/10 (50 tables)...
  ✓ Completed batch 2
...
✓ Extracted metadata for 494 tables
  Success: 494, Errors: 0
```

### Example 3: Conservative (Rate Limit Protection)

```bash
# Best for: OpenAI Tier 1, avoiding any risk of rate limits
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file large_mdl.json \
    --product-name "LargeProduct" \
    --batch-size 10
```

**Output:**
```
Created 1000 extraction tasks
Running LLM extraction in batches of 10...
Processing batch 1/100 (10 tables)...
  ✓ Completed batch 1
...
```

### Example 4: Aggressive (High Throughput)

```bash
# Best for: Local LLM, high tier OpenAI, need speed
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file huge_mdl.json \
    --product-name "HugeProduct" \
    --batch-size 200
```

## Performance Comparison

### Sequential (Old Approach)
```
500 tables × 3 seconds per table = 1500 seconds = 25 minutes
```

### Batched Parallel (New Approach)
```
500 tables ÷ 50 batch_size × 5 seconds per batch = 50 seconds ≈ 1 minute
```

**Speedup: 25x faster! ⚡**

## Rate Limit Error Handling

If you hit rate limits, the script will:
1. Mark failed extractions as errors
2. Use fallback metadata (category from name pattern)
3. Continue processing remaining batches
4. Report success/error counts at the end

**Example with errors:**
```
✓ Extracted metadata for 494 tables
  Success: 490, Errors: 4 (using fallback)
```

You can then:
- **Option 1**: Use the preview files as-is (fallback is decent)
- **Option 2**: Re-run with smaller batch size for failed tables
- **Option 3**: Manually edit preview files to fix failed extractions

## Troubleshooting

### Problem: Still hitting rate limits

**Solution:** Reduce batch size
```bash
# Try half the current batch size
--batch-size 25  # Instead of 50
```

### Problem: Too slow

**Solution:** Increase batch size or remove it
```bash
# Try doubling batch size
--batch-size 100  # Instead of 50

# Or remove batching entirely
# (omit --batch-size)
```

### Problem: Out of memory

**Solution:** Reduce batch size
```bash
# Use smaller batches
--batch-size 20
```

### Problem: Inconsistent results between batches

**Solution:** This shouldn't happen (each extraction is independent), but if you see this:
1. Check LLM model temperature (should be low, e.g., 0.2)
2. Verify LLM provider is stable
3. Try re-running specific failed batches

## Best Practices

### 1. Start Conservative

For your first run with a new MDL file:
```bash
--batch-size 25  # Safe starting point
```

Then adjust based on results.

### 2. Monitor Rate Limits

Check your LLM provider's dashboard:
- OpenAI: https://platform.openai.com/settings/organization/limits
- Anthropic: https://console.anthropic.com/settings/limits

### 3. Use Batching for Production

Even if you don't hit rate limits, batching provides:
- More predictable execution
- Better error handling
- Easier to monitor progress
- Safer for scheduled jobs

### 4. Optimize for Your Setup

Test different batch sizes and measure:
```bash
# Small batch
time python -m indexing_cli.create_mdl_enriched_preview ... --batch-size 25

# Medium batch
time python -m indexing_cli.create_mdl_enriched_preview ... --batch-size 50

# Large batch
time python -m indexing_cli.create_mdl_enriched_preview ... --batch-size 100

# Compare times and error rates
```

## Summary

✅ **Use batching** for most production scenarios  
✅ **Start with batch-size 50** as a safe default  
✅ **Adjust based on** your LLM provider tier and rate limits  
✅ **Monitor** for rate limit errors and adjust accordingly  
✅ **Remember**: Batching is 25x faster than sequential, even with conservative batch sizes  

🚀 **Recommended Command:**
```bash
python -m indexing_cli.create_mdl_enriched_preview \
    --mdl-file your_mdl.json \
    --product-name "YourProduct" \
    --batch-size 50
```
