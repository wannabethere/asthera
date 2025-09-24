# Enhanced Self-Correcting Pipeline Generator

## Overview

The Self-Correcting Pipeline Generator has been enhanced to utilize the rich function context from the Enhanced Function Registry, including examples, instructions, and historical rules. This integration significantly improves code generation quality and follows best practices.

## ✅ New Features Added

### 1. Enhanced Function Registry Integration
- **Enhanced Function Context Retrieval** - `_get_enhanced_function_context()` method
- **Enhanced Function Definition Retrieval** - Updated `_retrieve_function_definitions()` method
- **Context-Aware Code Generation** - Individual step code generation with enhanced context

### 2. Enhanced Function Context Usage
- **Function Examples** - Real usage examples for better parameter mapping
- **Project Instructions** - Project-specific guidance and best practices
- **Historical Rules** - Past successful patterns and conventions
- **Source Code Integration** - Function implementation details for better understanding
- **Function Signatures** - Complete parameter types and requirements
- **Docstrings** - Function documentation for better context

### 3. Enhanced Code Generation
- **Rich Comments** - Generated code includes function descriptions and best practices
- **Better Parameter Mapping** - Based on actual function signatures and examples
- **Historical Context** - Code follows established patterns and rules
- **Project-Specific Guidance** - Follows project instructions and conventions

## 🔧 Technical Implementation

### Enhanced Initialization

```python
def __init__(self, 
             llm,
             usage_examples_store: DocumentChromaStore,
             code_examples_store: DocumentChromaStore, 
             function_definition_store: DocumentChromaStore,
             logical_reasoning_store=None,
             function_retrieval: FunctionRetrieval = None,
             enhanced_function_registry=None,  # NEW: Enhanced function registry
             max_iterations: int = 3,
             relevance_threshold: float = 0.7):
```

### Enhanced Function Context Retrieval

```python
async def _get_enhanced_function_context(self, function_name: str, context: str, project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get enhanced function context including examples, instructions, and rules.
    
    Args:
        function_name: Name of the function to get context for
        context: User context for better matching
        project_id: Optional project ID for project-specific instructions
        
    Returns:
        Dictionary containing enhanced function context
    """
    if not self.enhanced_function_registry:
        return {}
    
    try:
        # Get enhanced function definition with context
        enhanced_def = await self.enhanced_function_registry.get_enhanced_function_definition(
            function_name=function_name,
            question=context,
            project_id=project_id
        )
        
        if "error" in enhanced_def:
            return {}
        
        # Extract relevant context
        enhanced_context = {
            "function_name": function_name,
            "description": enhanced_def.get("description", ""),
            "usage_description": enhanced_def.get("usage_description", ""),
            "category": enhanced_def.get("category", ""),
            "source_code": enhanced_def.get("source_code", ""),
            "function_signature": enhanced_def.get("function_signature", ""),
            "function_docstring": enhanced_def.get("function_docstring", ""),
            "examples": enhanced_def.get("examples", []),
            "instructions": enhanced_def.get("instructions", []),
            "historical_rules": enhanced_def.get("historical_rules", []),
            "examples_store": enhanced_def.get("examples_store", [])
        }
        
        return enhanced_context
        
    except Exception as e:
        logger.warning(f"Error getting enhanced function context for {function_name}: {e}")
        return {}
```

### Enhanced Function Definition Retrieval

```python
async def _retrieve_function_definitions(self, function_names: List[str], context: str = "", project_id: Optional[str] = None) -> str:
    """
    Retrieve function definitions using enhanced function registry if available, fallback to FunctionRetrieval or function_definition_store.
    
    Args:
        function_names: List of function names to retrieve definitions for
        context: User context for better function matching
        project_id: Optional project ID for project-specific instructions
        
    Returns:
        Formatted string containing function definitions with enhanced context
    """
    # Try to use enhanced function registry first if available
    if self.enhanced_function_registry:
        all_definitions = []
        
        for function_name in function_names:
            try:
                # Get enhanced function context
                enhanced_context = await self._get_enhanced_function_context(
                    function_name=function_name,
                    context=context,
                    project_id=project_id
                )
                
                if enhanced_context:
                    # Format the enhanced function definition
                    definition_text = f"Function: {function_name}\n"
                    definition_text += f"Description: {enhanced_context.get('description', 'No description available')}\n"
                    definition_text += f"Usage: {enhanced_context.get('usage_description', 'No usage info available')}\n"
                    definition_text += f"Category: {enhanced_context.get('category', 'unknown')}\n"
                    
                    # Add function signature
                    signature = enhanced_context.get('function_signature', '')
                    if signature:
                        definition_text += f"Signature: {signature}\n"
                    
                    # Add docstring
                    docstring = enhanced_context.get('function_docstring', '')
                    if docstring and docstring != "No docstring available":
                        definition_text += f"Docstring: {docstring}\n"
                    
                    # Add source code (truncated for prompt)
                    source_code = enhanced_context.get('source_code', '')
                    if source_code and source_code != "Source code not available":
                        # Truncate source code for prompt
                        lines = source_code.split('\n')
                        truncated_code = '\n'.join(lines[:20])  # First 20 lines
                        if len(lines) > 20:
                            truncated_code += "\n... (truncated)"
                        definition_text += f"Source Code:\n{truncated_code}\n"
                    
                    # Add examples
                    examples = enhanced_context.get('examples', [])
                    if examples:
                        definition_text += f"Examples ({len(examples)} available):\n"
                        for i, example in enumerate(examples[:3], 1):  # Show top 3 examples
                            example_str = str(example)
                            if len(example_str) > 200:
                                example_str = example_str[:197] + "..."
                            definition_text += f"  {i}. {example_str}\n"
                    
                    # Add instructions
                    instructions = enhanced_context.get('instructions', [])
                    if instructions:
                        definition_text += f"Instructions ({len(instructions)} available):\n"
                        for i, instruction in enumerate(instructions[:2], 1):  # Show top 2 instructions
                            instruction_str = instruction.get('instruction', str(instruction))
                            if len(instruction_str) > 150:
                                instruction_str = instruction_str[:147] + "..."
                            definition_text += f"  {i}. {instruction_str}\n"
                    
                    # Add historical rules
                    historical_rules = enhanced_context.get('historical_rules', [])
                    if historical_rules:
                        definition_text += f"Historical Rules ({len(historical_rules)} available):\n"
                        for i, rule in enumerate(historical_rules[:2], 1):  # Show top 2 rules
                            content = rule.get('content', str(rule))
                            if isinstance(content, str) and len(content) > 150:
                                content = content[:147] + "..."
                            definition_text += f"  {i}. {content}\n"
                    
                    all_definitions.append(definition_text)
                    continue
            
            except Exception as e:
                logger.warning(f"Error getting enhanced context for {function_name}: {e}")
    
    # Fallback to FunctionRetrieval if enhanced registry not available or failed
    # ... (existing fallback logic)
```

### Enhanced Individual Step Code Generation

```python
async def _generate_individual_step_code(self, 
                                       function_name: str,
                                       param_str: str,
                                       pipeline_type: PipelineType,
                                       current_dataframe: str,
                                       step_title: str,
                                       step_number: int,
                                       embedded_function_details: Optional[Dict[str, Any]] = None,
                                       context: str = "") -> str:
    """
    Generate individual code for a single step with enhanced function context
    
    Args:
        function_name: Name of the function to call
        param_str: Formatted parameter string
        pipeline_type: Type of pipeline to use
        current_dataframe: Name of the input dataframe
        step_title: Title of the step
        step_number: Number of the step
        embedded_function_details: Details for embedded functions
        context: User context for enhanced function retrieval
        
    Returns:
        Generated code for the individual step
    """
    # Get enhanced function context if available
    enhanced_context = {}
    if self.enhanced_function_registry and context:
        try:
            enhanced_context = await self._get_enhanced_function_context(
                function_name=function_name,
                context=context
            )
        except Exception as e:
            logger.warning(f"Error getting enhanced context for {function_name}: {e}")
    
    # Generate enhanced comments based on function context
    enhanced_comments = []
    if enhanced_context:
        # Add function description
        description = enhanced_context.get('description', '')
        if description:
            enhanced_comments.append(f"# {description}")
        
        # Add usage information
        usage = enhanced_context.get('usage_description', '')
        if usage:
            enhanced_comments.append(f"# Usage: {usage}")
        
        # Add historical rules as comments
        historical_rules = enhanced_context.get('historical_rules', [])
        if historical_rules:
            enhanced_comments.append("# Best practices:")
            for rule in historical_rules[:2]:  # Show top 2 rules
                content = rule.get('content', str(rule))
                if isinstance(content, str) and len(content) > 100:
                    content = content[:97] + "..."
                enhanced_comments.append(f"# - {content}")
    
    # Combine enhanced comments with step title
    comment_lines = [f"# {step_title}"]
    if enhanced_comments:
        comment_lines.extend(enhanced_comments)
    
    comment_section = "\n".join(comment_lines)
    
    if embedded_function_details and embedded_function_details.get('embedded_function'):
        # Handle embedded functions
        embedded_function = embedded_function_details.get('embedded_function')
        embedded_params = embedded_function_details.get('embedded_parameters', {})
        
        # Format embedded function parameters
        embedded_param_str = ", ".join([f"{k}={v}" for k, v in embedded_params.items()])
        if param_str:
            full_params = f"{param_str}, function={embedded_function}"
        else:
            full_params = f"function={embedded_function}"
        
        step_code = f"""{comment_section}
step_{step_number}_result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {function_name}({full_params})
    ).to_df()"""
    else:
        # Regular function call
        step_code = f"""{comment_section}
step_{step_number}_result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {function_name}({param_str})
    ).to_df()"""
    
    return step_code
```

## 🎯 Enhanced Prompt Structure

### Enhanced Function Definitions Section

```python
ENHANCED FUNCTION DEFINITIONS (with examples, instructions, and rules):
{function_definitions}
```

### Enhanced Generation Instructions

```python
Generate a complete pipeline code using the SEQUENTIAL PIPELINE APPROACH that:
1. Starts with the original dataframe and creates a result copy
2. Processes each step sequentially using the appropriate pipeline type
3. Each pipeline type runs independently and updates the result dataframe
4. Follows the reasoning plan steps in order with proper pipeline type detection
5. Considers the intent type and suggested functions from classification
6. CRITICAL: Aligns with the reasoning plan steps and their expected outcomes
7. Uses the reasoning plan step mapping to ensure proper implementation of each step
8. CRITICAL: Each pipeline type runs independently and updates the result sequentially
9. CRITICAL: Use the sequential approach: result = (PipeType.from_dataframe(result) | function()).to_df()
10. CRITICAL: Different pipeline types should NOT be chained together - run them separately
11. CRITICAL: Use the enhanced function definitions with examples, instructions, and rules for better code generation
12. CRITICAL: Follow the function signatures, docstrings, and source code patterns provided
13. CRITICAL: Apply the historical rules and best practices from the function context
14. CRITICAL: Use the examples as reference for proper function usage patterns
```

## 📊 Enhanced Code Generation Example

### Before Enhancement

```python
# Cohort Analysis
step_1_result = (
    CohortPipe.from_dataframe(df)
    | cohort_analysis(user_id_col='user_id', signup_date_col='signup_date', activity_date_col='activity_date', period='monthly')
    ).to_df()
```

### After Enhancement

```python
# Cohort Analysis
# Perform cohort analysis to analyze user retention patterns
# Usage: Analyze user cohorts based on signup dates and activity patterns
# Best practices:
# - For cohort analysis, ensure user_id and date columns are properly formatted and contain no null values
# - Use consistent time periods (monthly, weekly) for cohort calculations to ensure comparability
step_1_result = (
    CohortPipe.from_dataframe(df)
    | cohort_analysis(user_id_col='user_id', signup_date_col='signup_date', activity_date_col='activity_date', period='monthly')
    ).to_df()
```

## 🎯 Benefits of Enhanced Pipeline Generation

### 1. Better Code Quality
- **Function Best Practices** - Code follows established patterns and rules
- **Historical Context** - Learning from past successful implementations
- **Project-Specific Guidance** - Following project instructions and conventions
- **Error Prevention** - Following historical rules and patterns

### 2. Improved Parameter Mapping
- **Function Signatures** - Based on actual function parameter types
- **Usage Examples** - Real examples for proper parameter mapping
- **Source Code Patterns** - Understanding implementation details
- **Documentation Context** - Using docstrings for better understanding

### 3. Enhanced Documentation
- **Rich Comments** - Function descriptions and usage information
- **Best Practices** - Historical rules as comments
- **Context Information** - Enhanced understanding of function purpose
- **Maintenance Guidance** - Better code maintainability

### 4. Better Understanding
- **Function Context** - Complete understanding of function capabilities
- **Usage Patterns** - Real examples of function usage
- **Implementation Details** - Source code for better understanding
- **Project Context** - Project-specific instructions and guidance

## 🔗 Integration Points

### Enhanced Function Registry
- **Source of Context** - Examples, instructions, and rules
- **Function Definitions** - Complete function information
- **Project Instructions** - Project-specific guidance
- **Historical Rules** - Past successful patterns

### Self-Correcting Pipeline Generator
- **Consumer of Context** - Uses enhanced function context
- **Code Generation** - Generates better code with context
- **Parameter Mapping** - Improved parameter mapping
- **Documentation** - Enhanced code documentation

### Function Definition Retrieval
- **Context Enrichment** - Enhanced with function context
- **Better Matching** - Context-aware function retrieval
- **Project Integration** - Project-specific instructions
- **Historical Context** - Past successful patterns

## 📁 Files Modified

### Modified Files
- `self_correcting_pipeline_generator.py` - Enhanced with function context integration

### New Files
- `enhanced_pipeline_generator_example.py` - Comprehensive examples
- `ENHANCED_PIPELINE_GENERATION_SUMMARY.md` - This summary document

## 🔄 Backward Compatibility

The enhanced pipeline generation is fully backward compatible:
- All existing methods continue to work unchanged
- Enhanced features are opt-in through enhanced function registry
- Graceful fallback when enhanced context is not available
- No breaking changes to existing APIs

## 🎯 Key Benefits Summary

1. **Better Code Quality** - Following function best practices and rules
2. **Improved Parameter Mapping** - Based on actual function signatures
3. **Enhanced Documentation** - Rich comments with function context
4. **Better Error Prevention** - Following historical rules and patterns
5. **Improved Maintainability** - Code follows established patterns
6. **Better Understanding** - Enhanced comments explain function usage
7. **Project-Specific Guidance** - Following project instructions
8. **Historical Context** - Learning from past successful implementations

## 🚀 Next Steps

The Enhanced Self-Correcting Pipeline Generator is now ready for production use. The system provides:

1. **Rich Function Context** - Examples, instructions, and rules
2. **Better Code Generation** - Following best practices and patterns
3. **Enhanced Documentation** - Rich comments and context
4. **Improved Quality** - Better parameter mapping and error prevention
5. **Project Integration** - Project-specific guidance and instructions

The pipeline generator now utilizes rich function context for the most accurate and intelligent code generation possible! 🚀
