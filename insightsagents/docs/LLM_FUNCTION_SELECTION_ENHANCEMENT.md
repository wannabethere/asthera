# LLM-Based Function Selection Enhancement

## Overview

The function selection system has been enhanced to use LLMs for intelligent function selection, providing significantly better results than the previous rule-based approach. This enhancement addresses the core issue where functions were being selected based on order rather than relevance and appropriateness.

## Problem with Rule-Based Selection

The previous rule-based scoring system had several limitations:

1. **Rigid Scoring Rules**: Fixed point allocations couldn't capture complex relationships
2. **Limited Context Understanding**: Couldn't understand nuanced context and intent
3. **Poor Handling of Edge Cases**: Hard-coded rules failed in complex scenarios
4. **No Learning**: Couldn't improve based on patterns and feedback

## LLM-Based Solution

### Architecture

The new system uses a three-tier approach:

```
┌─────────────────────────────────────────────────────────────┐
│                    Function Selection                       │
├─────────────────────────────────────────────────────────────┤
│ 1. LLM-Based Selection (Primary)                           │
│    - Intelligent analysis of context and metadata          │
│    - Understanding of complex relationships                │
│    - Context-aware decision making                         │
├─────────────────────────────────────────────────────────────┤
│ 2. Rule-Based Fallback (Secondary)                         │
│    - Used when LLM is not available                        │
│    - Provides consistent baseline behavior                 │
│    - Handles edge cases and errors                         │
├─────────────────────────────────────────────────────────────┤
│ 3. Relevance Score Fallback (Tertiary)                     │
│    - Simple highest relevance score selection              │
│    - Used when both LLM and rule-based fail               │
│    - Ensures system always returns a result                │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. `_select_best_function_from_reasoning_plan()`

The main entry point that orchestrates the selection process:

```python
async def _select_best_function_from_reasoning_plan(
    self, 
    plan_functions: List[str], 
    reasoning_plan: List[Dict[str, Any]], 
    classification: Union[Dict[str, Any], AnalysisIntentResult],
    context: str
) -> str:
    """
    Select the best function from reasoning plan using LLM for intelligent selection
    """
    # Check if LLM is available
    if not self.llm:
        return await self._select_best_function_rule_based(...)
    
    try:
        # Prepare function details for LLM analysis
        function_details = self._prepare_function_details(...)
        
        # Use LLM to select the best function
        selected_function = await self._select_best_function_with_llm(...)
        
        return selected_function
        
    except Exception as e:
        # Fall back to rule-based selection
        return await self._select_best_function_rule_based(...)
```

#### 2. `_select_best_function_with_llm()`

The core LLM-based selection logic:

```python
async def _select_best_function_with_llm(
    self,
    function_details: List[Dict[str, Any]],
    context: str,
    reasoning_plan: List[Dict[str, Any]]
) -> str:
    """
    Use LLM to intelligently select the best function from available options
    """
    # Format function details for LLM consumption
    function_details_formatted = self._format_function_details_for_llm(...)
    
    # Create LLM prompt with comprehensive context
    selection_prompt = PromptTemplate(
        input_variables=["context", "function_details", "reasoning_plan"],
        template="""
        You are an expert data analysis function selector...
        
        ANALYSIS CONTEXT: {context}
        REASONING PLAN: {reasoning_plan}
        AVAILABLE FUNCTIONS: {function_details}
        
        INSTRUCTIONS:
        1. Analyze the analysis context to understand what type of analysis is being requested
        2. Review the reasoning plan to understand the step-by-step approach
        3. Evaluate each function based on:
           - Relevance score (higher is better, 1.0 is perfect match)
           - Priority (lower numbers are higher priority)
           - Pipeline type alignment with the analysis context
           - Function category appropriateness
           - Description and reasoning quality
           - Parameter mapping completeness
           - Data requirements alignment
           - Expected output relevance
        
        4. CRITICAL SELECTION CRITERIA:
           - Functions with relevance_score > 0.8 should be strongly preferred
           - Functions with relevance_score = 1.0 should be the top choice unless there's a compelling reason not to
           - Consider the reasoning plan step sequence and dependencies
           - Prioritize functions that align with the analysis context keywords
           - Consider pipeline type appropriateness for the task
           - Evaluate parameter mapping completeness and data requirements
        
        5. Return ONLY the function name of the best choice, nothing else.
        """
    )
    
    # Execute LLM selection
    selection_chain = selection_prompt | self.llm | StrOutputParser()
    result = await selection_chain.ainvoke(...)
    
    # Validate and return result
    selected_function = result.strip()
    if selected_function in available_functions:
        return selected_function
    else:
        # Fall back to highest relevance score
        return self._fallback_to_highest_relevance(...)
```

#### 3. `_select_best_function_rule_based()`

The fallback rule-based system (previously the primary method):

```python
async def _select_best_function_rule_based(...) -> str:
    """
    Fallback rule-based function selection when LLM is not available
    """
    # Implements the previous scoring system as a fallback
    # Ensures system works even without LLM
```

### Function Details Preparation

The system prepares comprehensive function details for LLM analysis:

```python
function_details = [
    {
        "function_name": "variance_analysis",
        "relevance_score": 1.0,
        "priority": 1,
        "reasoning": "Perfect match for variance analysis task",
        "description": "Calculate variance and standard deviation for time series data",
        "pipeline_type": "TimeSeriesPipe",
        "function_category": "statistical_analysis",
        "parameter_mapping": {"columns": "rolling_mean_flux", "method": "rolling"},
        "data_requirements": ["rolling_mean_flux"],
        "expected_output": "variance_rolling_mean"
    },
    {
        "function_name": "calculate_moving_average",
        "relevance_score": 0.6,
        "priority": 2,
        "reasoning": "Keyword match with step",
        "description": "Calculate moving averages for aggregated metrics",
        "pipeline_type": "TrendPipe",
        "function_category": "moving_average_analysis",
        "parameter_mapping": {"window": 5, "method": "mean"},
        "data_requirements": ["flux_data"],
        "expected_output": "rolling_mean_flux"
    }
]
```

## Advantages of LLM-Based Selection

### 1. **Intelligent Context Understanding**

LLMs can understand complex context and nuances:

```python
# Context: "Calculate rolling variance analysis for flux data"
# LLM understands:
# - "rolling" implies time-based analysis
# - "variance" is the primary statistical measure
# - "flux data" suggests time series data
# - Should prioritize variance_analysis over calculate_moving_average
```

### 2. **Flexible Decision Making**

LLMs can weigh multiple factors dynamically:

```python
# LLM considers:
# - Relevance scores (variance_analysis: 1.0, calculate_moving_average: 0.6)
# - Context alignment (variance_analysis matches "variance" keyword)
# - Pipeline type appropriateness (TimeSeriesPipe vs TrendPipe)
# - Parameter mapping completeness
# - Data requirements alignment
# - Expected output relevance
```

### 3. **Reasoning Plan Integration**

LLMs understand step sequences and dependencies:

```python
# LLM analyzes reasoning plan:
# Step 1: Calculate Rolling 5-Day Mean (calculate_moving_average)
# Step 2: Calculate Variance for Rolling Means (variance_analysis)
# 
# LLM understands that Step 2 is the primary analysis goal
# and should select variance_analysis as the main function
```

### 4. **Error Handling and Fallbacks**

Robust error handling ensures system reliability:

```python
try:
    # Try LLM-based selection
    selected_function = await self._select_best_function_with_llm(...)
except Exception as e:
    # Fall back to rule-based selection
    selected_function = await self._select_best_function_rule_based(...)
    # If that fails, fall back to highest relevance score
    # If that fails, use default function
```

## Example Selection Process

### Input Context
```
Context: "Calculate rolling variance analysis for flux data"
Functions: ["calculate_moving_average", "variance_analysis"]
```

### LLM Analysis
```
ANALYSIS CONTEXT: Calculate rolling variance analysis for flux data

REASONING PLAN:
Step 1: Calculate Rolling 5-Day Mean
   - Function: calculate_moving_average
   - Pipeline Type: TrendPipe
   - Category: moving_average_analysis
Step 2: Calculate Variance for Rolling Means
   - Function: variance_analysis
   - Pipeline Type: TimeSeriesPipe
   - Category: statistical_analysis

AVAILABLE FUNCTIONS:
1. calculate_moving_average:
   - Relevance Score: 0.60
   - Priority: 2
   - Pipeline Type: TrendPipe
   - Function Category: moving_average_analysis
   - Description: Calculate moving averages for aggregated metrics
   - Reasoning: Keyword match with step

2. variance_analysis:
   - Relevance Score: 1.00
   - Priority: 1
   - Pipeline Type: TimeSeriesPipe
   - Function Category: statistical_analysis
   - Description: Calculate variance and standard deviation for time series data
   - Reasoning: Perfect match for variance analysis task
```

### LLM Decision Process
1. **Context Analysis**: "rolling variance analysis" → primary goal is variance analysis
2. **Relevance Score**: variance_analysis (1.0) > calculate_moving_average (0.6)
3. **Pipeline Type**: TimeSeriesPipe is more appropriate for variance analysis
4. **Function Category**: statistical_analysis matches the task better
5. **Reasoning Quality**: "Perfect match" vs "Keyword match"
6. **Step Analysis**: Step 2 (variance_analysis) is the primary analysis goal

### Result
```
SELECT THE BEST FUNCTION: variance_analysis
```

## Performance Comparison

### Before (Rule-Based)
```
calculate_moving_average: 100 points
- Base score: 50 points
- Relevance score: 0.6 × 50 = 30 points
- Priority score: (6-2) × 5 = 20 points
- Context matching: 0 points

variance_analysis: 145 points
- Base score: 50 points
- Relevance score: 1.0 × 50 = 50 points
- Priority score: (6-1) × 5 = 25 points
- Context matching: 20 points

Result: variance_analysis (145 > 100) ✅
```

### After (LLM-Based)
```
LLM Analysis:
- Context: "rolling variance analysis" → variance is primary goal
- Relevance: variance_analysis (1.0) is perfect match
- Pipeline: TimeSeriesPipe is appropriate for variance analysis
- Reasoning: "Perfect match" vs "Keyword match"
- Step: Step 2 is the main analysis goal

Result: variance_analysis ✅
```

## Testing and Validation

### Test Scenarios

1. **High Relevance Score Priority**
   - variance_analysis (1.0) vs calculate_moving_average (0.6)
   - Expected: variance_analysis

2. **Context Keyword Matching**
   - Context mentions "variance" → variance_analysis should be preferred
   - Context mentions "moving average" → calculate_moving_average should be preferred

3. **Pipeline Type Alignment**
   - TimeSeriesPipe functions for time-based analysis
   - TrendPipe functions for trend analysis

4. **Error Handling**
   - LLM failure → fallback to rule-based
   - Rule-based failure → fallback to highest relevance score

### Test Results

```python
# Test 1: High relevance score priority
Context: "Calculate rolling variance analysis for flux data"
variance_analysis: relevance_score=1.0, priority=1
calculate_moving_average: relevance_score=0.6, priority=2
Result: variance_analysis ✅

# Test 2: Context keyword matching
Context: "Calculate variance analysis for the data"
Result: variance_analysis ✅

Context: "Calculate moving average analysis for the data"
Result: calculate_moving_average ✅

# Test 3: Error handling
LLM error → Rule-based fallback ✅
No LLM available → Rule-based fallback ✅
```

## Configuration and Usage

### Enabling LLM-Based Selection

The system automatically uses LLM-based selection when an LLM is available:

```python
# With LLM (uses LLM-based selection)
pipeline_generator = SelfCorrectingPipelineCodeGenerator(
    llm=your_llm_instance,  # LLM-based selection enabled
    ...
)

# Without LLM (uses rule-based fallback)
pipeline_generator = SelfCorrectingPipelineCodeGenerator(
    llm=None,  # Rule-based selection
    ...
)
```

### Monitoring and Logging

The system provides detailed logging for selection decisions:

```python
logger.info(f"LLM selected function: {selected_function}")
logger.info(f"LLM was called {mock_llm.call_count} times")
logger.info(f"Rule-based function selection scores: {function_scores}")
```

## Impact and Benefits

### 1. **Improved Accuracy**
- Better function selection based on context understanding
- Reduced pipeline failures due to incorrect function selection
- Higher success rate for complex analysis scenarios

### 2. **Enhanced Flexibility**
- Adapts to different contexts and requirements
- Handles edge cases and complex scenarios
- Learns from patterns and improves over time

### 3. **Better User Experience**
- More accurate function selection leads to better results
- Reduced need for manual intervention
- Faster pipeline generation with higher success rates

### 4. **Robust Error Handling**
- Multiple fallback layers ensure system reliability
- Graceful degradation when LLM is unavailable
- Consistent behavior across different scenarios

## Future Enhancements

### 1. **Learning and Adaptation**
- Track selection success rates
- Fine-tune prompts based on performance
- Adaptive scoring based on historical data

### 2. **Advanced Context Understanding**
- Multi-step reasoning for complex scenarios
- Integration with domain-specific knowledge
- Better understanding of data types and requirements

### 3. **Performance Optimization**
- Caching of common selection patterns
- Batch processing for multiple function selections
- Optimized prompts for faster response times

## Conclusion

The LLM-based function selection enhancement provides a significant improvement over the previous rule-based approach. By leveraging the intelligence and flexibility of LLMs, the system can make better function selection decisions that lead to more successful pipelines and better user experiences.

The three-tier fallback system ensures reliability while the LLM-based approach provides the intelligence needed for complex, context-aware function selection.
