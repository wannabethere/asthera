"""
Enhanced Function Registry with Source Code Integration Example

This script demonstrates the enhanced function retrieval capabilities
with source code integration for better LLM context and matching.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Example function source code for demonstration
SAMPLE_FUNCTION_CODE = '''
def cohort_analysis(df, user_id_col, signup_date_col, activity_date_col, period='monthly'):
    """
    Perform cohort analysis to analyze user retention patterns.
    
    Args:
        df: DataFrame containing user activity data
        user_id_col: Column name for user ID
        signup_date_col: Column name for signup date
        activity_date_col: Column name for activity date
        period: Analysis period ('daily', 'weekly', 'monthly')
    
    Returns:
        DataFrame with cohort analysis results
    """
    import pandas as pd
    import numpy as np
    
    # Convert dates to datetime
    df[signup_date_col] = pd.to_datetime(df[signup_date_col])
    df[activity_date_col] = pd.to_datetime(df[activity_date_col])
    
    # Create cohort groups based on signup period
    if period == 'monthly':
        df['cohort_group'] = df[signup_date_col].dt.to_period('M')
        df['period_number'] = df[activity_date_col].dt.to_period('M')
    elif period == 'weekly':
        df['cohort_group'] = df[signup_date_col].dt.to_period('W')
        df['period_number'] = df[activity_date_col].dt.to_period('W')
    else:  # daily
        df['cohort_group'] = df[signup_date_col].dt.to_period('D')
        df['period_number'] = df[activity_date_col].dt.to_period('D')
    
    # Calculate period number for each cohort
    df['period_number'] = (df['period_number'] - df['cohort_group']).apply(attrgetter('n'))
    
    # Group by cohort and period to get user counts
    cohort_data = df.groupby(['cohort_group', 'period_number'])[user_id_col].nunique().reset_index()
    cohort_data = cohort_data.rename(columns={user_id_col: 'user_count'})
    
    # Pivot to get cohort table
    cohort_table = cohort_data.pivot(index='cohort_group', columns='period_number', values='user_count')
    
    # Calculate retention rates
    cohort_sizes = cohort_table.iloc[:, 0]
    retention_table = cohort_table.divide(cohort_sizes, axis=0)
    
    return {
        'cohort_table': cohort_table,
        'retention_table': retention_table,
        'cohort_sizes': cohort_sizes
    }
'''

async def demonstrate_source_code_integration():
    """Demonstrate the enhanced function retrieval with source code integration."""
    
    print("🚀 Enhanced Function Registry with Source Code Integration")
    print("=" * 60)
    
    # Example reasoning plan
    reasoning_plan = [
        {
            "step_number": 1,
            "step_title": "Cohort Analysis",
            "step_description": "Analyze user retention patterns using cohort analysis",
            "data_requirements": ["user_id", "signup_date", "activity_date"]
        },
        {
            "step_number": 2,
            "step_title": "Risk Assessment",
            "step_description": "Identify high-risk customers based on transaction patterns",
            "data_requirements": ["user_id", "transaction_value", "risk_score"]
        }
    ]
    
    # Example function data with source code
    sample_function_data = {
        "function_name": "cohort_analysis",
        "pipe_name": "CohortAnalysisPipe",
        "description": "Perform cohort analysis to analyze user retention patterns",
        "usage_description": "Analyze user cohorts based on signup dates and activity patterns",
        "category": "cohort_analysis",
        "source_code": SAMPLE_FUNCTION_CODE,
        "function_definition": {
            "parameters": {
                "df": {"type": "DataFrame", "required": True},
                "user_id_col": {"type": "str", "required": True},
                "signup_date_col": {"type": "str", "required": True},
                "activity_date_col": {"type": "str", "required": True},
                "period": {"type": "str", "required": False, "default": "'monthly'"}
            },
            "docstring": "Perform cohort analysis to analyze user retention patterns.",
            "source_code": SAMPLE_FUNCTION_CODE
        }
    }
    
    print("📊 Sample Function Data:")
    print(f"  - Function: {sample_function_data['function_name']}")
    print(f"  - Description: {sample_function_data['description']}")
    print(f"  - Source Code Length: {len(sample_function_data['source_code'])} characters")
    print()
    
    # Show what the enhanced registry can do with source code
    print("🔧 Enhanced Features with Source Code Integration:")
    print("1. ✅ Function Source Code Extraction - Parse and format function code")
    print("2. ✅ Code Analysis for LLM - Include source code in LLM prompts")
    print("3. ✅ Signature Extraction - Extract function signatures and parameters")
    print("4. ✅ Docstring Parsing - Extract and format docstrings")
    print("5. ✅ Code Truncation - Smart truncation for LLM context limits")
    print("6. ✅ Implementation Analysis - Analyze actual code logic for matching")
    print("7. ✅ Enhanced Reasoning - LLM reasoning based on actual implementation")
    print()
    
    # Demonstrate code parsing utilities
    print("🔍 Code Parsing Demonstration:")
    print("=" * 35)
    
    # Mock the enhanced registry methods
    class MockEnhancedRegistry:
        def _extract_function_code(self, function_data):
            return function_data.get('source_code', 'Source code not available')
        
        def _format_code_for_llm(self, source_code, function_name):
            lines = source_code.strip().split('\n')
            func_lines = lines[:20]  # Show first 20 lines
            formatted_lines = []
            for i, line in enumerate(func_lines, 1):
                if len(line) > 80:
                    line = line[:77] + "..."
                formatted_lines.append(f"{i:3d}| {line}")
            return "\n".join(formatted_lines)
        
        def _get_function_signature(self, function_data):
            func_def = function_data.get('function_definition', {})
            parameters = func_def.get('parameters', {})
            param_list = []
            for param_name, param_info in parameters.items():
                param_type = param_info.get('type', 'Any')
                default = param_info.get('default')
                if default is not None:
                    param_list.append(f"{param_name}: {param_type} = {default}")
                else:
                    param_list.append(f"{param_name}: {param_type}")
            return f"def {function_data['function_name']}({', '.join(param_list)})"
        
        def _get_function_docstring(self, function_data):
            func_def = function_data.get('function_definition', {})
            docstring = func_def.get('docstring', 'No docstring available')
            if len(docstring) > 200:
                docstring = docstring[:197] + "..."
            return docstring
    
    mock_registry = MockEnhancedRegistry()
    
    # Extract and format function code
    source_code = mock_registry._extract_function_code(sample_function_data)
    formatted_code = mock_registry._format_code_for_llm(source_code, "cohort_analysis")
    signature = mock_registry._get_function_signature(sample_function_data)
    docstring = mock_registry._get_function_docstring(sample_function_data)
    
    print(f"📝 Function Signature:")
    print(f"   {signature}")
    print()
    
    print(f"📖 Function Docstring:")
    print(f"   {docstring}")
    print()
    
    print(f"💻 Formatted Source Code (first 20 lines):")
    print(formatted_code)
    print()
    
    # Show LLM prompt structure
    print("🤖 LLM Prompt Structure with Source Code:")
    print("=" * 45)
    
    llm_prompt_example = f"""
    Function: {sample_function_data['function_name']}
    Pipeline: {sample_function_data['pipe_name']}
    Description: {sample_function_data['description']}
    Usage: {sample_function_data['usage_description']}
    Category: {sample_function_data['category']}
    
    Signature: {signature}
    
    Docstring:
    {docstring}
    
    Source Code:
    {formatted_code}
    
    Examples (if available):
    - cohort_analysis(df, 'user_id', 'signup_date', 'activity_date')
    - cohort_analysis(df, 'user_id', 'signup_date', 'activity_date', period='weekly')
    
    Instructions (if available):
    - Always validate date columns before cohort analysis
    - Use consistent time periods for cohort calculations
    """
    
    print("Sample LLM prompt structure:")
    print(llm_prompt_example[:500] + "...")
    print()
    
    # Show benefits
    print("🎯 Benefits of Source Code Integration:")
    print("=" * 40)
    print("• Better Function Understanding - LLM can analyze actual implementation")
    print("• More Accurate Matching - Based on code logic, not just descriptions")
    print("• Implementation Analysis - Understand algorithmic approach and complexity")
    print("• Parameter Compatibility - Analyze function signatures for compatibility")
    print("• Code Quality Assessment - Evaluate code structure and best practices")
    print("• Enhanced Reasoning - LLM can provide detailed reasoning based on code")
    print("• Better Error Handling - Understand function limitations from code")
    print("• Performance Insights - Analyze code for performance characteristics")
    print()
    
    # Show evaluation criteria
    print("📊 Enhanced Evaluation Criteria:")
    print("=" * 35)
    print("• Function signature compatibility with step requirements")
    print("• Source code logic alignment with step objectives")
    print("• Data processing capabilities based on implementation")
    print("• Algorithmic approach suitability for the step")
    print("• Code complexity and performance considerations")
    print("• Documentation and examples relevance")
    print("• Error handling and edge case coverage")
    print("• Parameter validation and data requirements")
    print()
    
    print("✨ Source Code Integration Complete!")
    print("The enhanced function registry now provides LLM with complete function context including source code.")


def show_enhanced_data_models_with_code():
    """Show the enhanced data models with source code fields."""
    
    print("\n🏗️ Enhanced Data Models with Source Code:")
    print("=" * 45)
    
    print("""
    class EnhancedFunctionMetadata:
        # Basic metadata
        name: str
        description: str
        category: str
        # ... existing fields ...
        
        # Enhanced retrieval features
        examples_store: Optional[List[Dict[str, Any]]] = None
        instructions: Optional[List[Dict[str, Any]]] = None
        historical_rules: Optional[List[Dict[str, Any]]] = None
        insights: Optional[List[Dict[str, Any]]] = None
        
        # Source code integration
        source_code: str
        function_signature: str
        function_docstring: str
    
    class FunctionMatch:
        function_name: str
        pipe_name: str
        description: str
        usage_description: str
        relevance_score: float
        reasoning: str
        category: str = "unknown"
        function_definition: Optional[Dict[str, Any]] = None
        examples: Optional[List[Dict[str, Any]]] = None
        instructions: Optional[List[Dict[str, Any]]] = None
        examples_store: Optional[List[Dict[str, Any]]] = None
        historical_rules: Optional[List[Dict[str, Any]]] = None
        insights: Optional[List[Dict[str, Any]]] = None
        
        # Source code integration
        source_code: Optional[str] = None
        function_signature: Optional[str] = None
        function_docstring: Optional[str] = None
    """)


def show_enhanced_methods_with_code():
    """Show the enhanced methods with source code integration."""
    
    print("\n🔧 Enhanced Methods with Source Code Integration:")
    print("=" * 50)
    
    print("""
    # Source code parsing and formatting methods
    def _extract_function_code(self, function_data: Dict[str, Any]) -> str
    def _format_code_for_llm(self, source_code: str, function_name: str) -> str
    def _get_function_signature(self, function_data: Dict[str, Any]) -> str
    def _get_function_docstring(self, function_data: Dict[str, Any]) -> str
    
    # Enhanced retrieval with source code
    async def retrieve_and_match_functions(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> EnhancedFunctionRetrievalResult
    
    # Enhanced function definition with source code
    async def get_enhanced_function_definition(
        self,
        function_name: str,
        question: str = "",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]
    
    # Enhanced search with source code context
    async def search_functions_with_context(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]
    """)


async def main():
    """Main demonstration function."""
    await demonstrate_source_code_integration()
    show_enhanced_data_models_with_code()
    show_enhanced_methods_with_code()
    
    print("\n✨ Enhanced Function Registry with Source Code Integration is ready!")
    print("The function registry now provides LLM with complete function context including source code for better matching and reasoning.")


if __name__ == "__main__":
    asyncio.run(main())
