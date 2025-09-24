"""
Enhanced Self-Correcting Pipeline Generator Example

This script demonstrates the enhanced pipeline generation capabilities
that now utilize function examples, instructions, and historical rules
from the enhanced function registry.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Example enhanced function context
SAMPLE_ENHANCED_FUNCTION_CONTEXT = {
    "function_name": "cohort_analysis",
    "description": "Perform cohort analysis to analyze user retention patterns",
    "usage_description": "Analyze user cohorts based on signup dates and activity patterns",
    "category": "cohort_analysis",
    "function_signature": "def cohort_analysis(df, user_id_col, signup_date_col, activity_date_col, period='monthly')",
    "function_docstring": "Perform cohort analysis for user retention patterns.",
    "source_code": '''
def cohort_analysis(df, user_id_col, signup_date_col, activity_date_col, period='monthly'):
    """Perform cohort analysis for user retention patterns."""
    import pandas as pd
    # Convert dates to datetime
    df[signup_date_col] = pd.to_datetime(df[signup_date_col])
    df[activity_date_col] = pd.to_datetime(df[activity_date_col])
    # Create cohort groups
    df['cohort_group'] = df[signup_date_col].dt.to_period('M')
    # Calculate retention
    return cohort_table
''',
    "examples": [
        "cohort_analysis(df, 'user_id', 'signup_date', 'activity_date')",
        "cohort_analysis(df, 'user_id', 'signup_date', 'activity_date', period='weekly')",
        "cohort_analysis(df, 'customer_id', 'registration_date', 'purchase_date', period='monthly')"
    ],
    "instructions": [
        {
            "instruction": "Always validate date columns before cohort analysis",
            "source": "project_instructions"
        },
        {
            "instruction": "Use consistent time periods for cohort calculations",
            "source": "project_instructions"
        }
    ],
    "historical_rules": [
        {
            "type": "hardcoded_rule",
            "content": "For cohort analysis, ensure user_id and date columns are properly formatted and contain no null values",
            "source": "hardcoded"
        },
        {
            "type": "hardcoded_rule",
            "content": "Use consistent time periods (monthly, weekly) for cohort calculations to ensure comparability",
            "source": "hardcoded"
        }
    ],
    "examples_store": [
        {
            "example": "cohort_analysis(df, 'user_id', 'signup_date', 'activity_date', period='monthly')",
            "description": "Monthly cohort analysis example"
        }
    ]
}

async def demonstrate_enhanced_pipeline_generation():
    """Demonstrate the enhanced pipeline generation with function context."""
    
    print("🚀 Enhanced Self-Correcting Pipeline Generator")
    print("=" * 50)
    
    # Example reasoning plan
    reasoning_plan = [
        {
            "step_number": 1,
            "step_title": "Cohort Analysis",
            "step_description": "Analyze user retention patterns using cohort analysis",
            "function_name": "cohort_analysis",
            "parameter_mapping": {
                "user_id_col": "user_id",
                "signup_date_col": "signup_date",
                "activity_date_col": "activity_date",
                "period": "monthly"
            },
            "pipeline_type": "CohortPipe",
            "data_requirements": ["user_id", "signup_date", "activity_date"]
        },
        {
            "step_number": 2,
            "step_title": "Risk Assessment",
            "step_description": "Identify high-risk customers based on transaction patterns",
            "function_name": "risk_analysis",
            "parameter_mapping": {
                "columns": ["transaction_value", "risk_score"],
                "method": "monte_carlo"
            },
            "pipeline_type": "RiskPipe",
            "data_requirements": ["user_id", "transaction_value", "risk_score"]
        }
    ]
    
    print("📊 Sample Reasoning Plan:")
    for step in reasoning_plan:
        print(f"  Step {step['step_number']}: {step['step_title']}")
        print(f"    Function: {step['function_name']}")
        print(f"    Pipeline: {step['pipeline_type']}")
        print(f"    Parameters: {step['parameter_mapping']}")
        print()
    
    print("🔧 Enhanced Features in Pipeline Generation:")
    print("1. ✅ Enhanced Function Context - Examples, instructions, and rules")
    print("2. ✅ Source Code Integration - Function implementation details")
    print("3. ✅ Historical Rules - Best practices and patterns")
    print("4. ✅ Project Instructions - Project-specific guidance")
    print("5. ✅ Enhanced Comments - Rich documentation in generated code")
    print("6. ✅ Better Parameter Mapping - Based on function signatures")
    print("7. ✅ Improved Code Quality - Following best practices")
    print()
    
    # Demonstrate enhanced function context usage
    print("💡 Enhanced Function Context Usage:")
    print("=" * 40)
    
    enhanced_context = SAMPLE_ENHANCED_FUNCTION_CONTEXT
    
    print(f"Function: {enhanced_context['function_name']}")
    print(f"Description: {enhanced_context['description']}")
    print(f"Signature: {enhanced_context['function_signature']}")
    print(f"Docstring: {enhanced_context['function_docstring']}")
    print()
    
    print("Examples:")
    for i, example in enumerate(enhanced_context['examples'], 1):
        print(f"  {i}. {example}")
    print()
    
    print("Instructions:")
    for i, instruction in enumerate(enhanced_context['instructions'], 1):
        print(f"  {i}. {instruction['instruction']}")
    print()
    
    print("Historical Rules:")
    for i, rule in enumerate(enhanced_context['historical_rules'], 1):
        print(f"  {i}. {rule['content']}")
    print()
    
    # Demonstrate enhanced code generation
    print("🔨 Enhanced Code Generation:")
    print("=" * 35)
    
    # Mock enhanced individual step code generation
    def generate_enhanced_step_code(step, enhanced_context):
        """Generate enhanced step code with function context."""
        
        # Enhanced comments based on function context
        enhanced_comments = []
        
        # Add function description
        if enhanced_context.get('description'):
            enhanced_comments.append(f"# {enhanced_context['description']}")
        
        # Add usage information
        if enhanced_context.get('usage_description'):
            enhanced_comments.append(f"# Usage: {enhanced_context['usage_description']}")
        
        # Add historical rules as comments
        historical_rules = enhanced_context.get('historical_rules', [])
        if historical_rules:
            enhanced_comments.append("# Best practices:")
            for rule in historical_rules[:2]:  # Show top 2 rules
                content = rule.get('content', str(rule))
                if len(content) > 100:
                    content = content[:97] + "..."
                enhanced_comments.append(f"# - {content}")
        
        # Combine enhanced comments with step title
        comment_lines = [f"# {step['step_title']}"]
        if enhanced_comments:
            comment_lines.extend(enhanced_comments)
        
        comment_section = "\n".join(comment_lines)
        
        # Format parameters
        param_str = ", ".join([f"{k}={v}" for k, v in step['parameter_mapping'].items()])
        
        # Generate step code
        step_code = f"""{comment_section}
step_{step['step_number']}_result = (
    {step['pipeline_type']}.from_dataframe({step.get('current_dataframe', 'df')})
    | {step['function_name']}({param_str})
    ).to_df()"""
        
        return step_code
    
    # Generate enhanced code for each step
    for step in reasoning_plan:
        step['current_dataframe'] = 'df' if step['step_number'] == 1 else f"step_{step['step_number']-1}_result"
        
        enhanced_code = generate_enhanced_step_code(step, enhanced_context)
        print(f"Step {step['step_number']} - {step['step_title']}:")
        print(enhanced_code)
        print()
    
    # Demonstrate enhanced prompt structure
    print("🤖 Enhanced Prompt Structure:")
    print("=" * 30)
    
    enhanced_prompt_example = f"""
    ENHANCED FUNCTION DEFINITIONS (with examples, instructions, and rules):
    
    Function: {enhanced_context['function_name']}
    Description: {enhanced_context['description']}
    Usage: {enhanced_context['usage_description']}
    Category: {enhanced_context['category']}
    
    Signature: {enhanced_context['function_signature']}
    
    Docstring:
    {enhanced_context['function_docstring']}
    
    Source Code:
    {enhanced_context['source_code'][:200]}...
    
    Examples (3 available):
      1. {enhanced_context['examples'][0]}
      2. {enhanced_context['examples'][1]}
      3. {enhanced_context['examples'][2]}
    
    Instructions (2 available):
      1. {enhanced_context['instructions'][0]['instruction']}
      2. {enhanced_context['instructions'][1]['instruction']}
    
    Historical Rules (2 available):
      1. {enhanced_context['historical_rules'][0]['content']}
      2. {enhanced_context['historical_rules'][1]['content']}
    
    Generate a complete pipeline code using the SEQUENTIAL PIPELINE APPROACH that:
    11. CRITICAL: Use the enhanced function definitions with examples, instructions, and rules for better code generation
    12. CRITICAL: Follow the function signatures, docstrings, and source code patterns provided
    13. CRITICAL: Apply the historical rules and best practices from the function context
    14. CRITICAL: Use the examples as reference for proper function usage patterns
    """
    
    print("Sample enhanced prompt structure:")
    print(enhanced_prompt_example[:500] + "...")
    print()
    
    # Show benefits
    print("🎯 Benefits of Enhanced Pipeline Generation:")
    print("=" * 45)
    print("• Better Code Quality - Following function best practices and rules")
    print("• Improved Parameter Mapping - Based on actual function signatures")
    print("• Enhanced Documentation - Rich comments with function context")
    print("• Better Error Prevention - Following historical rules and patterns")
    print("• Improved Maintainability - Code follows established patterns")
    print("• Better Understanding - Enhanced comments explain function usage")
    print("• Project-Specific Guidance - Following project instructions")
    print("• Historical Context - Learning from past successful implementations")
    print()
    
    # Show integration points
    print("🔗 Integration Points:")
    print("=" * 20)
    print("• Enhanced Function Registry - Source of examples, instructions, and rules")
    print("• Self-Correcting Pipeline Generator - Consumer of enhanced context")
    print("• Function Definition Retrieval - Enhanced with context enrichment")
    print("• Individual Step Code Generation - Uses enhanced function context")
    print("• LLM Prompts - Include enhanced function definitions")
    print("• Code Comments - Generated from function context")
    print()
    
    print("✨ Enhanced Pipeline Generation Complete!")
    print("The self-correcting pipeline generator now utilizes rich function context for better code generation.")


def show_enhanced_pipeline_methods():
    """Show the enhanced pipeline generation methods."""
    
    print("\n🔧 Enhanced Pipeline Generation Methods:")
    print("=" * 45)
    
    print("""
    # Enhanced initialization with enhanced function registry
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
    
    # Enhanced function context retrieval
    async def _get_enhanced_function_context(self, function_name: str, context: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        '''Get enhanced function context including examples, instructions, and rules.'''
    
    # Enhanced function definition retrieval
    async def _retrieve_function_definitions(self, function_names: List[str], context: str = "", project_id: Optional[str] = None) -> str:
        '''Retrieve function definitions with enhanced context.'''
    
    # Enhanced individual step code generation
    async def _generate_individual_step_code(self, 
                                           function_name: str,
                                           param_str: str,
                                           pipeline_type: PipelineType,
                                           current_dataframe: str,
                                           step_title: str,
                                           step_number: int,
                                           embedded_function_details: Optional[Dict[str, Any]] = None,
                                           context: str = "") -> str:
        '''Generate individual code for a single step with enhanced function context.'''
    """)


def show_enhanced_prompt_improvements():
    """Show the enhanced prompt improvements."""
    
    print("\n🤖 Enhanced Prompt Improvements:")
    print("=" * 35)
    
    print("""
    # Enhanced prompt template includes:
    
    ENHANCED FUNCTION DEFINITIONS (with examples, instructions, and rules):
    {function_definitions}
    
    # Enhanced generation instructions:
    11. CRITICAL: Use the enhanced function definitions with examples, instructions, and rules for better code generation
    12. CRITICAL: Follow the function signatures, docstrings, and source code patterns provided
    13. CRITICAL: Apply the historical rules and best practices from the function context
    14. CRITICAL: Use the examples as reference for proper function usage patterns
    
    # Enhanced code generation includes:
    - Function description in comments
    - Usage information in comments
    - Historical rules as best practices comments
    - Source code patterns for reference
    - Project-specific instructions
    """)


async def main():
    """Main demonstration function."""
    await demonstrate_enhanced_pipeline_generation()
    show_enhanced_pipeline_methods()
    show_enhanced_prompt_improvements()
    
    print("\n✨ Enhanced Self-Correcting Pipeline Generator is ready!")
    print("The pipeline generator now utilizes rich function context for better code generation.")


if __name__ == "__main__":
    asyncio.run(main())
