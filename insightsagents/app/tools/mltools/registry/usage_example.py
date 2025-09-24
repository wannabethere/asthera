#!/usr/bin/env python3
"""
Usage Example for Enhanced Function Retrieval Service

This script demonstrates how to use the enhanced function retrieval service
with retrieval helper and input extractor using comprehensive definitions.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.tools.mltools.registry.enhanced_comprehensive_registry import (
    initialize_enhanced_comprehensive_registry
)
from app.core.dependencies import get_llm, get_doc_store_provider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("usage-example")

async def main():
    """Main function demonstrating enhanced function retrieval usage."""
    print("🚀 Enhanced Function Retrieval Service Usage Example")
    print("=" * 60)
    
    try:
        # Step 1: Initialize components
        print("\n📋 Step 1: Initializing Components")
        print("-" * 40)
        
        # Get LLM
        print("• Getting LLM instance...")
        llm = get_llm()
        print("  ✅ LLM initialized")
        
        # Initialize retrieval helper
        print("• Initializing RetrievalHelper...")
        retrieval_helper = RetrievalHelper()
        print("  ✅ RetrievalHelper initialized")
        
        # Initialize comprehensive registry
        print("• Initializing Enhanced Comprehensive Registry...")
        comprehensive_registry = initialize_enhanced_comprehensive_registry(
            collection_name="comprehensive_ml_functions_demo",
            force_recreate=True,  # Auto-detect and handle embedding dimension mismatches
            enable_separate_collections=True
        )
        print("  ✅ Enhanced Comprehensive Registry initialized")
        
        # Check if registry has functions
        if hasattr(comprehensive_registry, 'functions_cache'):
            print(f"  📊 Registry has {len(comprehensive_registry.functions_cache)} functions cached")
            if comprehensive_registry.functions_cache:
                sample_function = list(comprehensive_registry.functions_cache.values())[0]
                print(f"  🔍 Sample function: {sample_function.function_name}")
                print(f"  📝 Has source code: {bool(sample_function.source_code)}")
                print(f"  💡 Has examples: {len(sample_function.examples) if sample_function.examples else 0}")
        else:
            print("  ⚠️  Registry functions cache not available")
        
        # Get document stores for input extraction
        print("• Getting document stores...")
        doc_store_provider = get_doc_store_provider()
        document_stores = doc_store_provider.stores
        
        example_collection = document_stores.get("usage_examples")
        function_collection = document_stores.get("function_spec")
        insights_collection = document_stores.get("insights_store")
        print("  ✅ Document stores retrieved")
        
        # Step 2: Prepare test data
        print("\n📋 Step 2: Preparing Test Data")
        print("-" * 40)
        
        # Sample reasoning plan for time series analysis
        reasoning_plan = [
            {
                "step_number": 1,
                "step_title": "Data Preparation",
                "step_description": "Clean and prepare the time series dataset",
                "data_requirements": ["date_column", "value_column"]
            },
            {
                "step_number": 2,
                "step_title": "Rolling Variance Analysis",
                "step_description": "Calculate rolling variance with appropriate window size",
                "data_requirements": ["date_column", "value_column", "window_size"]
            },
            {
                "step_number": 3,
                "step_title": "Anomaly Detection",
                "step_description": "Identify outliers using statistical methods",
                "data_requirements": ["value_column", "threshold"]
            }
        ]
        
        question = "Analyze the rolling variance of stock prices and detect anomalies"
        rephrased_question = "Calculate rolling variance for stock price data and identify outliers"
        dataframe_description = "Stock price dataset with date, price, and volume columns"
        dataframe_summary = "Daily stock prices from 2020-2024 with 1000+ records"
        available_columns = ["date", "price", "volume", "ticker"]
        project_id = "demo_project"
        
        print("• Test data prepared:")
        print(f"  - Question: {question}")
        print(f"  - Available columns: {available_columns}")
        print(f"  - Reasoning plan steps: {len(reasoning_plan)}")
        
        # Step 3: Call enhanced function retrieval
        print("\n📋 Step 3: Calling Enhanced Function Retrieval")
        print("-" * 40)
        
        print("• Calling get_enhanced_function_retrieval...")
        result = await retrieval_helper.get_enhanced_function_retrieval(
            reasoning_plan=reasoning_plan,
            question=question,
            rephrased_question=rephrased_question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id,
            llm=llm,
            comprehensive_registry=comprehensive_registry,
            example_collection=example_collection,
            function_collection=function_collection,
            insights_collection=insights_collection
        )
        
        # Step 4: Display results
        print("\n📋 Step 4: Displaying Results")
        print("-" * 40)
        
        if "error" in result:
            print(f"❌ Retrieval failed: {result['error']}")
            return
        
        print("✅ Function retrieval completed successfully!")
        print(f"• Total functions retrieved: {result['total_functions_retrieved']}")
        print(f"• Steps covered: {result['total_steps_covered']}")
        print(f"• Average relevance score: {result['average_relevance_score']:.2f}")
        print(f"• Confidence score: {result['confidence_score']:.2f}")
        print(f"• Fallback used: {result['fallback_used']}")
        print(f"• Reasoning: {result['reasoning']}")
        
        # Display step matches with complete function details
        step_matches = result.get('step_matches', {})
        if step_matches:
            print(f"\n📊 Step-Function Matches:")
            for step_num, functions in step_matches.items():
                print(f"\n  Step {step_num}:")
                for i, func in enumerate(functions, 1):
                    print(f"    {i}. {func.get('function_name', 'Unknown')} "
                          f"(Score: {func.get('relevance_score', 0.0):.2f})")
                    print(f"       Pipeline: {func.get('pipe_name', 'Unknown')}")
                    print(f"       Category: {func.get('category', 'Unknown')}")
                    if func.get('extracted_parameters'):
                        print(f"       Extracted Parameters: {len(func['extracted_parameters'])} parameters")
                    
                    # Debug: Check what data is available
                    print(f"       🔍 Debug - Available keys: {list(func.keys())}")
                    print(f"       📝 Has source_code: {bool(func.get('source_code'))}")
                    print(f"       💡 Has examples: {len(func.get('examples', []))}")
                    print(f"       📋 Has required_params: {len(func.get('required_params', []))}")
                    print(f"       🎯 Has use_cases: {len(func.get('use_cases', []))}")
                    
                    # Print complete function details
                    print(f"\n    📋 Complete Function Details for {func.get('function_name', 'Unknown')}:")
                    print("    " + "="*60)
                    
                    # Function definition
                    function_definition = func.get('function_definition', {})
                    if function_definition:
                        print(f"    🔧 Function Definition:")
                        print(f"    {json.dumps(function_definition, indent=4, default=str)}")
                        
                        # Debug: Show parameter structure
                        if 'parameters' in function_definition:
                            print(f"    🔍 Parameter Structure Debug:")
                            for param_name, param_info in function_definition['parameters'].items():
                                print(f"      {param_name}: {type(param_info).__name__} = {param_info}")
                    
                    # Enhanced function specifications
                    required_params = func.get('required_params', [])
                    optional_params = func.get('optional_params', [])
                    if required_params or optional_params:
                        print(f"\n    📋 Function Specifications:")
                        if required_params:
                            print(f"    Required Parameters:")
                            for param in required_params:
                                if isinstance(param, dict):
                                    print(f"      • {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}")
                                else:
                                    print(f"      • {param}")
                        if optional_params:
                            print(f"    Optional Parameters:")
                            for param in optional_params:
                                if isinstance(param, dict):
                                    print(f"      • {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}")
                                else:
                                    print(f"      • {param}")
                    
                    # Use cases and tags
                    use_cases = func.get('use_cases', [])
                    tags = func.get('tags', [])
                    if use_cases or tags:
                        print(f"\n    🎯 Use Cases: {', '.join(use_cases) if use_cases else 'None'}")
                        print(f"    🏷️  Tags: {', '.join(tags) if tags else 'None'}")
                    
                    # Description
                    description = func.get('description', '')
                    if description:
                        print(f"\n    📝 Description:")
                        print(f"    {description}")
                    
                    # Usage description
                    usage = func.get('usage_description', '')
                    if usage:
                        print(f"\n    🔧 Usage:")
                        print(f"    {usage}")
                    
                    # Examples
                    examples = func.get('examples', [])
                    if examples:
                        print(f"\n    💡 Examples ({len(examples)}):")
                        for j, example in enumerate(examples, 1):
                            if isinstance(example, dict) and 'variations' in example:
                                print(f"    {j}. {example.get('function', example.get('description', 'Example'))} - {example.get('description', '')}")
                                print(f"        Variations ({len(example['variations'])}):")
                                for k, variation in enumerate(example['variations'], 1):
                                    print(f"        {k}. {variation.get('name', f'Variation {k}')}")
                                    print(f"           Example: {variation.get('example', '')}")
                                    if variation.get('inputs'):
                                        print(f"           Inputs: {json.dumps(variation['inputs'], indent=12, default=str)}")
                            else:
                                print(f"    {j}. {json.dumps(example, indent=4, default=str)}")
                    
                    # Instructions
                    instructions = func.get('instructions', [])
                    if instructions:
                        print(f"\n    📖 Instructions ({len(instructions)}):")
                        for j, instruction in enumerate(instructions, 1):
                            print(f"    {j}. {json.dumps(instruction, indent=4, default=str)}")
                    
                    # Extracted parameters
                    extracted_params = func.get('extracted_parameters', {})
                    if extracted_params:
                        print(f"\n    ⚙️  Extracted Parameters:")
                        print(f"    {json.dumps(extracted_params, indent=4, default=str)}")
                    
                    # Historical rules
                    historical_rules = func.get('historical_rules', [])
                    if historical_rules:
                        print(f"\n    📚 Historical Rules ({len(historical_rules)}):")
                        for j, rule in enumerate(historical_rules, 1):
                            print(f"    {j}. {json.dumps(rule, indent=4, default=str)}")
                    
                    # Examples store (insights)
                    examples_store = func.get('examples_store', [])
                    if examples_store:
                        print(f"\n    🗄️  Examples Store/Insights ({len(examples_store)}):")
                        for j, insight in enumerate(examples_store, 1):
                            print(f"    {j}. {json.dumps(insight, indent=4, default=str)}")
                    
                    # Source code
                    source_code = func.get('source_code', '')
                    if source_code:
                        print(f"\n    💻 Source Code:")
                        print("    " + "="*40)
                        print(f"    {source_code}")
                        print("    " + "="*40)
                    
                    # Function signature
                    function_signature = func.get('function_signature', '')
                    if function_signature:
                        print(f"\n    🔧 Function Signature:")
                        print(f"    {function_signature}")
                    
                    # Docstring
                    docstring = func.get('docstring', '')
                    if docstring:
                        print(f"\n    📖 Docstring:")
                        print(f"    {docstring}")
                    
                    # Code snippets
                    code_snippets = func.get('code_snippets', [])
                    if code_snippets:
                        print(f"\n    💻 Code Snippets ({len(code_snippets)}):")
                        for j, snippet in enumerate(code_snippets, 1):
                            print(f"    {j}. {snippet}")
                    
                    print("    " + "="*60)
        else:
            print("⚠️  No step matches found")
        
        # Step 5: Test with different query
        print("\n📋 Step 5: Testing with Different Query")
        print("-" * 40)
        
        different_question = "Perform cohort analysis on user retention data"
        different_reasoning_plan = [
            {
                "step_number": 1,
                "step_title": "Cohort Definition",
                "step_description": "Define user cohorts based on acquisition date",
                "data_requirements": ["user_id", "acquisition_date"]
            },
            {
                "step_number": 2,
                "step_title": "Retention Calculation",
                "step_description": "Calculate retention rates for each cohort",
                "data_requirements": ["user_id", "activity_date", "cohort_period"]
            }
        ]
        
        print(f"• Testing with query: {different_question}")
        
        result2 = await retrieval_helper.get_enhanced_function_retrieval(
            reasoning_plan=different_reasoning_plan,
            question=different_question,
            rephrased_question=different_question,
            dataframe_description="User activity dataset with user_id, acquisition_date, and activity_date",
            dataframe_summary="User activity data with 10,000+ users and 50,000+ activity records",
            available_columns=["user_id", "acquisition_date", "activity_date", "activity_type"],
            project_id=project_id,
            llm=llm,
            comprehensive_registry=comprehensive_registry,
            example_collection=example_collection,
            function_collection=function_collection,
            insights_collection=insights_collection
        )
        
        if "error" not in result2:
            print("✅ Second retrieval completed successfully!")
            print(f"• Total functions retrieved: {result2['total_functions_retrieved']}")
            print(f"• Steps covered: {result2['total_steps_covered']}")
            print(f"• Average relevance score: {result2['average_relevance_score']:.2f}")
            
            # Display step matches for second query with complete function details
            step_matches2 = result2.get('step_matches', {})
            if step_matches2:
                print(f"\n📊 Step-Function Matches for Cohort Analysis:")
                for step_num, functions in step_matches2.items():
                    print(f"\n  Step {step_num}:")
                    for i, func in enumerate(functions, 1):
                        print(f"    {i}. {func.get('function_name', 'Unknown')} "
                              f"(Score: {func.get('relevance_score', 0.0):.2f})")
                        print(f"       Pipeline: {func.get('pipe_name', 'Unknown')}")
                        print(f"       Category: {func.get('category', 'Unknown')}")
                        if func.get('extracted_parameters'):
                            print(f"       Extracted Parameters: {len(func['extracted_parameters'])} parameters")
                        
                        # Print complete function details
                        print(f"\n    📋 Complete Function Details for {func.get('function_name', 'Unknown')}:")
                        print("    " + "="*60)
                        
                        # Function definition
                        function_definition = func.get('function_definition', {})
                        if function_definition:
                            print(f"    🔧 Function Definition:")
                            print(f"    {json.dumps(function_definition, indent=4, default=str)}")
                            
                            # Debug: Show parameter structure
                            if 'parameters' in function_definition:
                                print(f"    🔍 Parameter Structure Debug:")
                                for param_name, param_info in function_definition['parameters'].items():
                                    print(f"      {param_name}: {type(param_info).__name__} = {param_info}")
                        
                        # Enhanced function specifications
                        required_params = func.get('required_params', [])
                        optional_params = func.get('optional_params', [])
                        if required_params or optional_params:
                            print(f"\n    📋 Function Specifications:")
                            if required_params:
                                print(f"    Required Parameters:")
                                for param in required_params:
                                    if isinstance(param, dict):
                                        print(f"      • {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}")
                                    else:
                                        print(f"      • {param}")
                            if optional_params:
                                print(f"    Optional Parameters:")
                                for param in optional_params:
                                    if isinstance(param, dict):
                                        print(f"      • {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}")
                                    else:
                                        print(f"      • {param}")
                        
                        # Use cases and tags
                        use_cases = func.get('use_cases', [])
                        tags = func.get('tags', [])
                        if use_cases or tags:
                            print(f"\n    🎯 Use Cases: {', '.join(use_cases) if use_cases else 'None'}")
                            print(f"    🏷️  Tags: {', '.join(tags) if tags else 'None'}")
                        
                        # Description
                        description = func.get('description', '')
                        if description:
                            print(f"\n    📝 Description:")
                            print(f"    {description}")
                        
                        # Usage description
                        usage = func.get('usage_description', '')
                        if usage:
                            print(f"\n    🔧 Usage:")
                            print(f"    {usage}")
                        
                        # Examples
                        examples = func.get('examples', [])
                        if examples:
                            print(f"\n    💡 Examples ({len(examples)}):")
                            for j, example in enumerate(examples, 1):
                                if isinstance(example, dict) and 'variations' in example:
                                    print(f"    {j}. {example.get('function', example.get('description', 'Example'))} - {example.get('description', '')}")
                                    print(f"        Variations ({len(example['variations'])}):")
                                    for k, variation in enumerate(example['variations'], 1):
                                        print(f"        {k}. {variation.get('name', f'Variation {k}')}")
                                        print(f"           Example: {variation.get('example', '')}")
                                        if variation.get('inputs'):
                                            print(f"           Inputs: {json.dumps(variation['inputs'], indent=12, default=str)}")
                                else:
                                    print(f"    {j}. {json.dumps(example, indent=4, default=str)}")
                        
                        # Instructions
                        instructions = func.get('instructions', [])
                        if instructions:
                            print(f"\n    📖 Instructions ({len(instructions)}):")
                            for j, instruction in enumerate(instructions, 1):
                                print(f"    {j}. {json.dumps(instruction, indent=4, default=str)}")
                        
                        # Extracted parameters
                        extracted_params = func.get('extracted_parameters', {})
                        if extracted_params:
                            print(f"\n    ⚙️  Extracted Parameters:")
                            print(f"    {json.dumps(extracted_params, indent=4, default=str)}")
                        
                        # Historical rules
                        historical_rules = func.get('historical_rules', [])
                        if historical_rules:
                            print(f"\n    📚 Historical Rules ({len(historical_rules)}):")
                            for j, rule in enumerate(historical_rules, 1):
                                print(f"    {j}. {json.dumps(rule, indent=4, default=str)}")
                        
                        # Examples store (insights)
                        examples_store = func.get('examples_store', [])
                        if examples_store:
                            print(f"\n    🗄️  Examples Store/Insights ({len(examples_store)}):")
                            for j, insight in enumerate(examples_store, 1):
                                print(f"    {j}. {json.dumps(insight, indent=4, default=str)}")
                        
                        # Source code
                        source_code = func.get('source_code', '')
                        if source_code:
                            print(f"\n    💻 Source Code:")
                            print("    " + "="*40)
                            print(f"    {source_code}")
                            print("    " + "="*40)
                        
                        # Function signature
                        function_signature = func.get('function_signature', '')
                        if function_signature:
                            print(f"\n    🔧 Function Signature:")
                            print(f"    {function_signature}")
                        
                        # Docstring
                        docstring = func.get('docstring', '')
                        if docstring:
                            print(f"\n    📖 Docstring:")
                            print(f"    {docstring}")
                        
                        # Code snippets
                        code_snippets = func.get('code_snippets', [])
                        if code_snippets:
                            print(f"\n    💻 Code Snippets ({len(code_snippets)}):")
                            for j, snippet in enumerate(code_snippets, 1):
                                print(f"    {j}. {snippet}")
                        
                        print("    " + "="*60)
        else:
            print(f"❌ Second retrieval failed: {result2['error']}")
        
        # Step 6: Test usage store functions
        print("\n📋 Step 6: Testing Usage Store Functions")
        print("-" * 40)
        
        # Test single function usage data
        test_function = "calculate_retention"
        print(f"• Testing usage data for: {test_function}")
        
        usage_data = comprehensive_registry.get_usage_data_for_function(test_function)
        if usage_data and usage_data.get('total_examples', 0) > 0:
            print(f"  ✅ Found {usage_data['total_examples']} usage examples")
            print(f"  💡 Usage patterns: {len(usage_data.get('usage_patterns', []))}")
            
            # Show sample usage example
            if usage_data.get('usage_examples'):
                sample_example = usage_data['usage_examples'][0]
                print(f"  📚 Sample usage:")
                print(f"    Description: {sample_example.get('description', 'No description')}")
                print(f"    Example: {sample_example.get('example', '')[:150]}...")
        else:
            print("  ⚠️  No usage examples found")
        
        # Test multiple functions usage data
        print(f"\n• Testing usage data for multiple functions")
        test_functions = ["calculate_retention", "form_time_cohorts"]
        multiple_usage = comprehensive_registry.get_usage_data_for_functions(test_functions)
        
        for func_name, data in multiple_usage.items():
            examples_count = data.get('total_examples', 0)
            print(f"  {func_name}: {examples_count} examples")
        
        # Step 7: Test fetching from each data source
        print("\n📋 Step 7: Testing Data Fetching from Each Source")
        print("-" * 40)
        
        # Test function: calculate_retention
        test_function = "calculate_retention"
        print(f"• Testing data sources for: {test_function}")
        
        # 1. Test toolspecs collection
        print(f"\n  🔧 1. ToolSpecs Collection:")
        try:
            toolspecs_collection = comprehensive_registry.document_stores.get(
                comprehensive_registry.collection_names['toolspecs']
            )
            if toolspecs_collection:
                toolspecs_results = toolspecs_collection.semantic_search(test_function, k=3)
                print(f"    ✅ Found {len(toolspecs_results)} toolspecs results")
                if toolspecs_results:
                    result = toolspecs_results[0]
                    if hasattr(result, 'page_content'):
                        content = result.page_content[:200] + "..." if len(result.page_content) > 200 else result.page_content
                        print(f"    📝 Sample content: {content}")
                    if hasattr(result, 'metadata'):
                        print(f"    🏷️  Metadata: {result.metadata}")
            else:
                print(f"    ❌ ToolSpecs collection not found")
        except Exception as e:
            print(f"    ❌ Error accessing toolspecs: {e}")
        
        # 2. Test instructions collection
        print(f"\n  📖 2. Instructions Collection:")
        try:
            instructions_collection = comprehensive_registry.document_stores.get(
                comprehensive_registry.collection_names['instructions']
            )
            if instructions_collection:
                instructions_results = instructions_collection.semantic_search(test_function, k=3)
                print(f"    ✅ Found {len(instructions_results)} instructions results")
                if instructions_results:
                    result = instructions_results[0]
                    if hasattr(result, 'page_content'):
                        content = result.page_content[:200] + "..." if len(result.page_content) > 200 else result.page_content
                        print(f"    📝 Sample content: {content}")
                    if hasattr(result, 'metadata'):
                        print(f"    🏷️  Metadata: {result.metadata}")
            else:
                print(f"    ❌ Instructions collection not found")
        except Exception as e:
            print(f"    ❌ Error accessing instructions: {e}")
        
        # 3. Test usage_examples collection
        print(f"\n  💡 3. Usage Examples Collection:")
        try:
            usage_collection = comprehensive_registry.document_stores.get(
                comprehensive_registry.collection_names['usage_examples']
            )
            if usage_collection:
                usage_results = usage_collection.semantic_search(test_function, k=3)
                print(f"    ✅ Found {len(usage_results)} usage examples results")
                if usage_results:
                    result = usage_results[0]
                    if hasattr(result, 'page_content'):
                        content = result.page_content[:200] + "..." if len(result.page_content) > 200 else result.page_content
                        print(f"    📝 Sample content: {content}")
                    if hasattr(result, 'metadata'):
                        print(f"    🏷️  Metadata: {result.metadata}")
            else:
                print(f"    ❌ Usage examples collection not found")
        except Exception as e:
            print(f"    ❌ Error accessing usage examples: {e}")
        
        # 4. Test code_examples collection
        print(f"\n  💻 4. Code Examples Collection:")
        try:
            code_examples_collection = comprehensive_registry.document_stores.get(
                comprehensive_registry.collection_names['code_examples']
            )
            if code_examples_collection:
                code_examples_results = code_examples_collection.semantic_search(test_function, k=3)
                print(f"    ✅ Found {len(code_examples_results)} code examples results")
                if code_examples_results:
                    result = code_examples_results[0]
                    if hasattr(result, 'page_content'):
                        content = result.page_content[:200] + "..." if len(result.page_content) > 200 else result.page_content
                        print(f"    📝 Sample content: {content}")
                    if hasattr(result, 'metadata'):
                        print(f"    🏷️  Metadata: {result.metadata}")
            else:
                print(f"    ❌ Code examples collection not found")
        except Exception as e:
            print(f"    ❌ Error accessing code examples: {e}")
        
        # 5. Test code collection
        print(f"\n  🔍 5. Code Collection:")
        try:
            code_collection = comprehensive_registry.document_stores.get(
                comprehensive_registry.collection_names['code']
            )
            if code_collection:
                code_results = code_collection.semantic_search(test_function, k=3)
                print(f"    ✅ Found {len(code_results)} code results")
                if code_results:
                    result = code_results[0]
                    if hasattr(result, 'page_content'):
                        content = result.page_content[:200] + "..." if len(result.page_content) > 200 else result.page_content
                        print(f"    📝 Sample content: {content}")
                    if hasattr(result, 'metadata'):
                        print(f"    🏷️  Metadata: {result.metadata}")
            else:
                print(f"    ❌ Code collection not found")
        except Exception as e:
            print(f"    ❌ Error accessing code: {e}")
        
        # Step 8: Test comprehensive function data retrieval
        print(f"\n📋 Step 8: Testing Comprehensive Function Data Retrieval")
        print("-" * 40)
        
        print(f"• Testing comprehensive data for: {test_function}")
        comprehensive_data = comprehensive_registry.get_function_by_name(test_function)
        
        if comprehensive_data:
            print(f"  ✅ Retrieved comprehensive data")
            print(f"  📊 Data fields available:")
            for key, value in comprehensive_data.items():
                if isinstance(value, list):
                    print(f"    {key}: {len(value)} items")
                elif isinstance(value, str):
                    print(f"    {key}: {len(value)} characters")
                else:
                    print(f"    {key}: {type(value).__name__}")
            
            # Show sample data from each field
            print(f"\n  📝 Sample Data:")
            
            # Description
            if comprehensive_data.get('description'):
                desc = comprehensive_data['description'][:150] + "..." if len(comprehensive_data['description']) > 150 else comprehensive_data['description']
                print(f"    Description: {desc}")
            
            # Usage description
            if comprehensive_data.get('usage_description'):
                usage_desc = comprehensive_data['usage_description'][:150] + "..." if len(comprehensive_data['usage_description']) > 150 else comprehensive_data['usage_description']
                print(f"    Usage: {usage_desc}")
            
            # Examples count
            examples = comprehensive_data.get('examples', [])
            print(f"    Examples: {len(examples)} items")
            
            # Instructions count
            instructions = comprehensive_data.get('instructions', [])
            print(f"    Instructions: {len(instructions)} items")
            
            # Code snippets count
            code_snippets = comprehensive_data.get('code_snippets', [])
            print(f"    Code Snippets: {len(code_snippets)} items")
            
            # Source code
            source_code = comprehensive_data.get('source_code', '')
            if source_code:
                source_preview = source_code[:100] + "..." if len(source_code) > 100 else source_code
                print(f"    Source Code: {len(source_code)} characters - {source_preview}")
            
        else:
            print(f"  ❌ No comprehensive data found for {test_function}")
        
        print("\n🎉 Enhanced function retrieval usage example completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
