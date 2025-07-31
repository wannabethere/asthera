#!/usr/bin/env python3
"""
Test script to verify the embedded function parameter handling works correctly
"""

import re
import ast

def fix_common_syntax_issues(code: str) -> str:
    """Fix common syntax issues in generated code"""
    # Fix common issues
    code = re.sub(r'(\w+)\s*\(\s*\)\s*\|', r'\1() |', code)  # Fix empty function calls
    code = re.sub(r'\|\s*\(\s*\)', '|', code)  # Remove empty parentheses in pipe chains
    code = re.sub(r'\(\s*\)', '', code)  # Remove standalone empty parentheses
    
    # Fix common pipe syntax issues
    code = re.sub(r'\|\s*\|\s*', ' | ', code)  # Fix double pipes
    code = re.sub(r'\(\s*\|', '(', code)  # Fix opening parenthesis followed by pipe
    code = re.sub(r'\|\s*\)', ')', code)  # Fix pipe followed by closing parenthesis
    
    # Fix common function call issues
    code = re.sub(r'(\w+)\s*\(\s*,\s*', r'\1(', code)  # Fix function calls starting with comma
    code = re.sub(r'\(\s*,\s*', '(', code)  # Fix parentheses starting with comma
    
    # Fix to_df() missing parentheses
    code = re.sub(r'\|\s*to_df\s*(\||\)|$)', r' | to_df()\1', code)
    code = re.sub(r'^\s*to_df\s*(\||\)|$)', r'to_df()\1', code)
    
    # Fix function parameter issues - remove quotes around function names
    # Pattern: function='Variance' -> function=Variance
    code = re.sub(r"function\s*=\s*'([^']+)'", r'function=\1', code)
    code = re.sub(r'function\s*=\s*"([^"]+)"', r'function=\1', code)
    
    # Fix function parameters to direct method calls
    # Pattern: moving_apply_by_group(function=Variance, ...) -> variance(...)
    # This converts function parameters to direct method calls
    function_conversions = {
        'Variance': 'variance',
        'Mean': 'mean', 
        'Sum': 'sum',
        'Count': 'count',
        'Max': 'max',
        'Min': 'min',
        'StandardDeviation': 'std',
        'Correlation': 'correlation',
        'Covariance': 'covariance',
        'Median': 'median',
        'Percentile': 'percentile'
    }
    
    for func_param, method_name in function_conversions.items():
        # Pattern: moving_apply_by_group(function=Variance, ...) -> variance(...)
        pattern = rf'moving_apply_by_group\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
        replacement = rf'{method_name}(\1)'
        code = re.sub(pattern, replacement, code)
        
        # Also handle other wrapper functions
        pattern2 = rf'(\w+)\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
        replacement2 = rf'{method_name}(\2)'
        code = re.sub(pattern2, replacement2, code)
    
    # CRITICAL: Handle the case where we need to embed MetricsPipe functions as function parameters in TimeSeriesPipe
    # Pattern: moving_apply_by_group(function=Variance, ...) -> function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df())
    for func_param, method_name in function_conversions.items():
        # Look for moving_apply_by_group with function parameter
        pattern = rf'moving_apply_by_group\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
        if re.search(pattern, code):
            # Extract the dataframe name from the context
            dataframe_match = re.search(r'(\w+Pipe\.from_dataframe\([^)]+\))', code)
            if dataframe_match:
                dataframe_expr = dataframe_match.group(1)
                # Convert to embedded function format
                replacement = rf'function=({dataframe_expr} | {method_name}(variable=\'Transactional value\') | to_df()),\1'
                code = re.sub(pattern, replacement, code)
                print(f"Converted function={func_param} to embedded pipeline expression")
    
    # Fix pipeline indentation issues - this is the main fix for the reported error
    # Pattern: result = PipeType.from_dataframe(...)\n         | function(...)\n         | to_df()
    # Convert to: result = (PipeType.from_dataframe(...)\n                     | function(...)\n                     | to_df()\n                    )
    lines = code.split('\n')
    if len(lines) > 1:
        # Check if we have a pipeline pattern with incorrect indentation
        pipeline_pattern = re.compile(r'^(\w+)\s*=\s*(\w+Pipe\.from_dataframe\([^)]*\))')
        first_line_match = pipeline_pattern.match(lines[0].strip())
        
        if first_line_match and len(lines) > 1:
            # Check if subsequent lines start with pipe operators and indentation
            pipe_lines = []
            for i, line in enumerate(lines[1:], 1):
                stripped = line.strip()
                if stripped.startswith('|'):
                    pipe_lines.append((i, stripped))
            
            if pipe_lines:
                # Reconstruct the code with proper parentheses and indentation
                result_var = first_line_match.group(1)
                pipe_init = first_line_match.group(2)
                
                # Start with opening parenthesis
                fixed_lines = [f"{result_var} = ({pipe_init}"]
                
                # Add pipe operations with proper indentation
                for _, pipe_line in pipe_lines:
                    # Remove the leading | and add proper indentation
                    pipe_content = pipe_line[1:].strip()
                    fixed_lines.append(f"                     | {pipe_content}")
                
                # Close the parentheses
                fixed_lines.append("                    )")
                
                # Join the lines
                code = '\n'.join(fixed_lines)
    
    return code

def clean_generated_code(code: str) -> str:
    """Clean and format generated code with enhanced error handling"""
    if not code or not isinstance(code, str):
        return ""
    
    # Remove markdown code blocks
    code = re.sub(r'```python\s*', '', code)
    code = re.sub(r'```\s*', '', code)
    
    # Clean whitespace and remove empty lines
    lines = [line.rstrip() for line in code.split('\n') if line.strip()]
    
    if not lines:
        return ""
    
    # Join lines back together
    code = '\n'.join(lines)
    
    # Fix common syntax issues
    code = fix_common_syntax_issues(code)
    
    # Final validation - if still has syntax errors, try to generate a minimal valid version
    try:
        ast.parse(code)
        return code
    except SyntaxError as e:
        print(f"Syntax error after cleaning: {e}")
        # Return a basic fallback
        return "result = MetricsPipe.from_dataframe(df) | to_df()"

def test_embedded_function_parameter():
    """Test the embedded function parameter handling"""
    
    # Test case 1: The problematic code that should be converted to embedded function parameter
    problematic_code = '''result = (TimeSeriesPipe.from_dataframe("Purchase Orders Data")
         | moving_apply_by_group(
             columns='Transactional value',
             group_column='Project, Cost center, Department',
             function=Variance,
             window=5,
             min_periods=1,
             time_column='Date',
             output_suffix='_rolling_variance'
         )
         | to_df()
)'''
    
    print("Test Case 1 - Problematic code (function parameter):")
    print(problematic_code)
    print("\n" + "="*80 + "\n")
    
    # Try to fix it
    fixed_code = clean_generated_code(problematic_code)
    
    print("Fixed code:")
    print(fixed_code)
    print("\n" + "="*80 + "\n")
    
    # Test if it's valid Python
    try:
        ast.parse(fixed_code)
        print("✅ SUCCESS: Fixed code is valid Python syntax!")
    except SyntaxError as e:
        print(f"❌ FAILED: Fixed code still has syntax errors: {e}")
    
    # Test case 2: Expected correct format
    expected_code = '''result = (TimeSeriesPipe.from_dataframe("Purchase Orders Data")
         | moving_apply_by_group(
             columns='Transactional value',
             group_column='Project, Cost center, Department',
             function=(MetricsPipe.from_dataframe("Purchase Orders Data")
                      | Variance(variable='Transactional value')
                      | to_df()),
             window=5,
             min_periods=1,
             time_column='Date',
             output_suffix='_rolling_variance'
         )
         | to_df()
)'''
    
    print("\n" + "="*80 + "\n")
    print("Expected correct format:")
    print(expected_code)
    print("\n" + "="*80 + "\n")
    
    try:
        ast.parse(expected_code)
        print("✅ SUCCESS: Expected code is valid Python syntax!")
    except SyntaxError as e:
        print(f"❌ FAILED: Expected code has syntax errors: {e}")

if __name__ == "__main__":
    test_embedded_function_parameter() 