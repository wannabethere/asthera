# Function Selection Fix

## Problem Description

The system was incorrectly selecting functions based on their order in the list rather than their relevance scores and confidence. Specifically:

1. **Poor Function Selection**: The system was selecting the first function from the reasoning plan (`plan_functions[0]`) without considering relevance scores
2. **Ignoring Relevance Scores**: Functions with higher relevance scores (e.g., `variance_analysis` with relevance_score=1.0) were being ignored in favor of functions with lower scores (e.g., `calculate_moving_average` with relevance_score=0.6)
3. **LLM Not Prioritizing Relevance**: The LLM function selection was not properly prioritizing functions with higher relevance scores

This resulted in poor function selection like:
```python
# ❌ INCORRECT - Selected calculate_moving_average (relevance_score=0.6) 
# instead of variance_analysis (relevance_score=1.0)
selected_function = plan_functions[0]  # Always picks first function
```

## Root Cause

The function selection logic in `_extract_function_from_reasoning_plan` was using a simple approach:
```python
# OLD CODE - Poor selection logic
selected_function = plan_functions[0]  # Just pick the first one
```

This ignored the rich metadata available in the retrieved functions, including:
- Relevance scores (0.0 to 1.0)
- Priority levels
- Detailed reasoning
- Function descriptions and parameters

## Solution

### 1. Enhanced Function Selection Algorithm

Created a new method `_select_best_function_from_reasoning_plan` that implements a comprehensive scoring system:

```python
async def _select_best_function_from_reasoning_plan(
    self, 
    plan_functions: List[str], 
    reasoning_plan: List[Dict[str, Any]], 
    classification: Union[Dict[str, Any], AnalysisIntentResult],
    context: str
) -> str:
    """
    Select the best function from reasoning plan based on relevance scores and confidence
    """
    # Create a scoring system for each function
    function_scores = {}
    
    for func_name in plan_functions:
        score = 0.0
        reasoning = []
        
        # Base score for being in the reasoning plan
        score += 50.0
        reasoning.append("Function present in reasoning plan")
        
        # Check if function exists in retrieved functions with relevance score
        for retrieved_func in retrieved_functions:
            if retrieved_func.get('function_name') == func_name:
                # Add relevance score (0.0 to 1.0, scaled to 0-50 points)
                relevance_score = retrieved_func.get('relevance_score', 0.0)
                score += relevance_score * 50.0
                reasoning.append(f"Relevance score: {relevance_score:.2f}")
                
                # Add priority score if available
                priority = retrieved_func.get('priority', 1)
                score += (6 - priority) * 5.0  # Higher priority gets more points
                reasoning.append(f"Priority: {priority}")
                
                # Additional scoring factors...
                break
        
        # Context-based scoring
        context_lower = context.lower()
        if any(keyword in context_lower for keyword in ['variance', 'variation', 'volatility']):
            if 'variance' in func_name.lower():
                score += 20.0
                reasoning.append("Context mentions variance - function matches")
        
        function_scores[func_name] = {
            'score': score,
            'reasoning': reasoning
        }
    
    # Select the function with the highest score
    best_function = max(function_scores.keys(), key=lambda x: function_scores[x]['score'])
    return best_function
```

### 2. Scoring System Components

The scoring system considers multiple factors:

#### Base Score (50 points)
- Every function in the reasoning plan gets 50 base points

#### Relevance Score (0-50 points)
- Relevance scores are scaled from 0.0-1.0 to 0-50 points
- Higher relevance scores = higher points
- Example: relevance_score=1.0 → 50 points, relevance_score=0.6 → 30 points

#### Priority Score (0-25 points)
- Priority levels are inverted (lower priority number = higher score)
- Priority 1 gets 25 points, Priority 2 gets 20 points, etc.

#### Context Matching (0-20 points)
- Functions that match context keywords get bonus points
- Example: Context mentions "variance" → `variance_analysis` gets +20 points

#### Metadata Quality (0-25 points)
- Detailed reasoning: +10 points
- Required parameters defined: +5 points
- Detailed parameter mapping: +10 points

### 3. Enhanced LLM Prompt

Updated the LLM prompt to explicitly prioritize relevance scores:

```python
7. CRITICAL: Use the retrieved functions metadata to prioritize function selection:
   - HIGHER RELEVANCE SCORES = BETTER MATCHES: Functions with relevance scores > 0.8 should be strongly preferred
   - ALWAYS PREFER functions with higher relevance scores over those with lower scores
   - If a function has relevance_score = 1.0, it should be the top choice unless there's a compelling reason not to
   - CRITICAL: Do NOT select the last function in the list - select the function with the highest relevance score
```

### 4. Example Selection Process

For the flux analysis example:

**Functions Available:**
- `calculate_moving_average`: relevance_score=0.6, priority=2
- `variance_analysis`: relevance_score=1.0, priority=1

**Scoring:**
```
calculate_moving_average:
- Base score: 50 points
- Relevance score: 0.6 × 50 = 30 points
- Priority score: (6-2) × 5 = 20 points
- Context matching: 0 points (no variance keywords)
- Total: 100 points

variance_analysis:
- Base score: 50 points
- Relevance score: 1.0 × 50 = 50 points
- Priority score: (6-1) × 5 = 25 points
- Context matching: 20 points (context mentions variance)
- Total: 145 points
```

**Result:** `variance_analysis` is selected (145 > 100)

## Expected Results

With these fixes, the function selection should now:

1. **Prioritize High Relevance Scores**: Functions with relevance_score > 0.8 will be strongly preferred
2. **Consider Context**: Functions that match context keywords will get bonus points
3. **Respect Priority Levels**: Lower priority numbers (higher priority) will get more points
4. **Provide Transparency**: Detailed logging shows why each function was selected

### Before Fix:
```python
# ❌ Poor selection - always picks first function
selected_function = "calculate_moving_average"  # relevance_score=0.6
```

### After Fix:
```python
# ✅ Smart selection - picks function with highest relevance score
selected_function = "variance_analysis"  # relevance_score=1.0
```

## Testing

A comprehensive test suite verifies the fix:

- `test_function_selection_fix.py`: Tests the scoring system with different scenarios
- Verifies that functions with higher relevance scores are selected
- Tests context-based scoring
- Ensures the system responds correctly to relevance score changes

## Impact

This fix ensures that:

1. **Better Function Selection**: Functions are selected based on relevance and confidence, not order
2. **Improved Accuracy**: Higher relevance scores lead to better function matches
3. **Context Awareness**: Functions that match the context get preference
4. **Transparency**: Detailed logging shows the selection reasoning
5. **Reduced Pipeline Failures**: Better function selection leads to more successful pipelines

## Migration Notes

No breaking changes were introduced. The fix improves accuracy without affecting existing functionality. The system will now make better function selections automatically.
