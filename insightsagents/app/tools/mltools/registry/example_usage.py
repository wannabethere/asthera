#!/usr/bin/env python3
"""
Example Usage of Enhanced Function Retrieval Architecture

This script demonstrates how to use the new separated architecture with pretty-printed output
for better readability and documentation.
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
from app.tools.mltools.registry.function_retrieval_service import create_function_retrieval_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("example-usage")

def print_section(title: str, content: str = ""):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    if content:
        print(content)

def print_success(message: str):
    """Print a success message with emoji."""
    print(f"✅ {message}")

def print_warning(message: str):
    """Print a warning message with emoji."""
    print(f"⚠️  {message}")

def print_error(message: str):
    """Print an error message with emoji."""
    print(f"❌ {message}")

def print_info(message: str):
    """Print an info message with emoji."""
    print(f"ℹ️  {message}")

def pretty_print_json(data: Dict[str, Any], title: str = "Data"):
    """Pretty print JSON data with formatting."""
    print(f"\n📊 {title}:")
    print("-" * 40)
    try:
        formatted_json = json.dumps(data, indent=2, default=str)
        print(formatted_json)
    except Exception as e:
        print(f"Error formatting JSON: {e}")
        print(data)

def print_document_info(doc_tuple, index: int = 1):
    """Pretty print individual document from search results."""
    doc, score = doc_tuple
    print(f"\n🔧 Document #{index} (Score: {score:.3f})")
    print("=" * 50)
    
    # Extract metadata
    metadata = doc.metadata
    page_content = doc.page_content
    
    # Basic info from metadata
    name = metadata.get('function_name', 'Unknown')
    category = metadata.get('category', 'Unknown')
    type_of_op = metadata.get('type_of_operation', 'Unknown')
    source_file = metadata.get('source_file', 'Unknown')
    
    print(f"📝 Function Name: {name}")
    print(f"🏷️  Category: {category}")
    print(f"⚙️  Operation Type: {type_of_op}")
    print(f"📁 Source File: {source_file.split('/')[-1] if source_file != 'Unknown' else 'Unknown'}")
    
    # Description from metadata
    description = metadata.get('description', 'No description available')
    if description:
        print(f"\n📋 Description:")
        # Clean up the description
        clean_desc = description.replace('\\n', '\n').replace('\\t', '\t')
        print(f"   {clean_desc}")
    
    # Parse and display page content if it's JSON
    try:
        import json
        content_data = json.loads(page_content)
        print(f"\n📊 Function Details:")
        
        # Required parameters
        required_params = content_data.get('required_params', [])
        if required_params:
            print(f"   🔴 Required Parameters ({len(required_params)}):")
            for param in required_params:
                if isinstance(param, dict):
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'Any')
                    param_desc = param.get('description', '')
                    print(f"      • {param_name}: {param_type}")
                    if param_desc:
                        print(f"        └─ {param_desc}")
                else:
                    print(f"      • {param}")
        
        # Optional parameters
        optional_params = content_data.get('optional_params', [])
        if optional_params:
            print(f"   🟡 Optional Parameters ({len(optional_params)}):")
            for param in optional_params:
                if isinstance(param, dict):
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'Any')
                    param_desc = param.get('description', '')
                    print(f"      • {param_name}: {param_type}")
                    if param_desc:
                        print(f"        └─ {param_desc}")
                else:
                    print(f"      • {param}")
        
        # Outputs
        outputs = content_data.get('outputs', {})
        if outputs:
            print(f"   📤 Outputs:")
            if isinstance(outputs, dict):
                output_type = outputs.get('type', 'Unknown')
                output_desc = outputs.get('description', '')
                print(f"      • Type: {output_type}")
                if output_desc:
                    print(f"        └─ {output_desc}")
            else:
                print(f"      • {outputs}")
                
    except (json.JSONDecodeError, TypeError) as e:
        print(f"\n📄 Raw Content:")
        print(f"   {page_content[:200]}{'...' if len(page_content) > 200 else ''}")
    
    print("-" * 50)


def print_document_info(doc_tuple, index: int = 1):
    """Pretty print individual document from search results."""
    doc, score = doc_tuple
    print(f"\n🔧 Document #{index} (Score: {score:.3f})")
    print("=" * 50)
    
    # Extract metadata
    metadata = doc.metadata
    page_content = doc.page_content
    
    # Basic info from metadata
    name = metadata.get('function_name', 'Unknown')
    category = metadata.get('category', 'Unknown')
    type_of_op = metadata.get('type_of_operation', 'Unknown')
    source_file = metadata.get('source_file', 'Unknown')
    
    print(f"📝 Function Name: {name}")
    print(f"🏷️  Category: {category}")
    print(f"⚙️  Operation Type: {type_of_op}")
    print(f"📁 Source File: {source_file.split('/')[-1] if source_file != 'Unknown' else 'Unknown'}")
    
    # Description from metadata
    description = metadata.get('description', 'No description available')
    if description:
        print(f"\n📋 Description:")
        # Clean up the description
        clean_desc = description.replace('\\n', '\n').replace('\\t', '\t')
        print(f"   {clean_desc}")
    
    # Parse and display page content if it's JSON
    try:
        content_data = json.loads(page_content)
        print(f"\n📊 Function Details:")
        
        # Required parameters
        required_params = content_data.get('required_params', [])
        if required_params:
            print(f"   🔴 Required Parameters ({len(required_params)}):")
            for param in required_params:
                if isinstance(param, dict):
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'Any')
                    param_desc = param.get('description', '')
                    print(f"      • {param_name}: {param_type}")
                    if param_desc:
                        print(f"        └─ {param_desc}")
                else:
                    print(f"      • {param}")
        
        # Optional parameters
        optional_params = content_data.get('optional_params', [])
        if optional_params:
            print(f"   🟡 Optional Parameters ({len(optional_params)}):")
            for param in optional_params:
                if isinstance(param, dict):
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'Any')
                    param_desc = param.get('description', '')
                    print(f"      • {param_name}: {param_type}")
                    if param_desc:
                        print(f"        └─ {param_desc}")
                else:
                    print(f"      • {param}")
        
        # Outputs
        outputs = content_data.get('outputs', {})
        if outputs:
            print(f"   📤 Outputs:")
            if isinstance(outputs, dict):
                output_type = outputs.get('type', 'Unknown')
                output_desc = outputs.get('description', '')
                print(f"      • Type: {output_type}")
                if output_desc:
                    print(f"        └─ {output_desc}")
            else:
                print(f"      • {outputs}")
                
    except (json.JSONDecodeError, TypeError) as e:
        print(f"\n📄 Raw Content:")
        print(f"   {page_content[:200]}{'...' if len(page_content) > 200 else ''}")
    
    print("-" * 50)

def print_documents_separately(documents, title: str = "Search Results"):
    """Print each document separately with detailed formatting."""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    
    if not documents:
        print("⚠️  No documents found")
        return
    
    print(f"✅ Found {len(documents)} document(s)")
    
    for i, doc_tuple in enumerate(documents, 1):
        print_document_info(doc_tuple, i)

def print_section(title: str, content: str = ""):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    if content:
        print(content)

def print_success(message: str):
    """Print a success message with emoji."""
    print(f"✅ {message}")

def print_warning(message: str):
    """Print a warning message with emoji."""
    print(f"⚠️  {message}")

def print_error(message: str):
    """Print an error message with emoji."""
    print(f"❌ {message}")

def print_info(message: str):
    """Print an info message with emoji."""
    print(f"ℹ️  {message}")

def print_function_info(function_data: Dict[str, Any], index: int = 1):
    """Pretty print function information."""
    print(f"\n🔧 Function #{index}:")
    print("-" * 30)
    
    # Basic info
    name = function_data.get('function_name', 'Unknown')
    pipe = function_data.get('pipe_name', 'Unknown')
    category = function_data.get('category', 'Unknown')
    complexity = function_data.get('complexity', 'Unknown')
    
    print(f"Name: {name}")
    print(f"Pipeline: {pipe}")
    print(f"Category: {category}")
    print(f"Complexity: {complexity}")
    
    # Description
    description = function_data.get('description', 'No description available')
    if description and len(description) > 100:
        description = description[:100] + "..."
    print(f"Description: {description}")
    
    # Parameters
    required_params = function_data.get('required_params', [])
    optional_params = function_data.get('optional_params', [])
    
    if required_params:
        print(f"Required Parameters: {len(required_params)}")
        for param in required_params[:3]:  # Show first 3
            if isinstance(param, dict):
                param_name = param.get('name', str(param))
                param_type = param.get('type', 'Any')
                print(f"  - {param_name}: {param_type}")
            else:
                print(f"  - {param}")
        if len(required_params) > 3:
            print(f"  ... and {len(required_params) - 3} more")
    
    if optional_params:
        print(f"Optional Parameters: {len(optional_params)}")
        for param in optional_params[:2]:  # Show first 2
            if isinstance(param, dict):
                param_name = param.get('name', str(param))
                param_type = param.get('type', 'Any')
                print(f"  - {param_name}: {param_type}")
            else:
                print(f"  - {param}")
        if len(optional_params) > 2:
            print(f"  ... and {len(optional_params) - 2} more")
    
    # Examples count
    examples_count = function_data.get('examples_count', 0)
    instructions_count = function_data.get('instructions_count', 0)
    code_snippets_count = function_data.get('code_snippets_count', 0)
    
    print(f"Examples: {examples_count}")
    print(f"Instructions: {instructions_count}")
    print(f"Code Snippets: {code_snippets_count}")

def print_documents_separately(documents, title: str = "Search Results"):
    """Print each document separately with detailed formatting."""
    print_section(title)
    
    if not documents:
        print_warning("No documents found")
        return
    
    print_success(f"Found {len(documents)} document(s)")
    
    for i, doc_tuple in enumerate(documents, 1):
        print_document_info(doc_tuple, i)

def print_search_results(results: List[Dict[str, Any]], query: str):
    """Pretty print search results."""
    print_section(f"Search Results for: '{query}'")
    
    if not results:
        print_warning("No functions found - run initialization script first")
        return
    
    print_success(f"Found {len(results)} function(s)")
    
    for i, result in enumerate(results, 1):
        print_function_info(result, i)

def print_comprehensive_function_info(function_data: Dict[str, Any], index: int = 1):
    """Pretty print comprehensive function information with all available data."""
    print(f"\n🔧 Comprehensive Function #{index}:")
    print("=" * 60)
    
    # Basic info
    name = function_data.get('function_name', 'Unknown')
    pipe = function_data.get('pipe_name', 'Unknown')
    category = function_data.get('category', 'Unknown')
    complexity = function_data.get('complexity', 'Unknown')
    confidence = function_data.get('confidence_score', 0.0)
    
    print(f"📝 Name: {name}")
    print(f"🔗 Pipeline: {pipe}")
    print(f"🏷️  Category: {category}")
    print(f"⚡ Complexity: {complexity}")
    print(f"🎯 Confidence: {confidence:.2f}")
    
    # Description
    description = function_data.get('description', 'No description available')
    if description:
        print(f"\n📋 Description:")
        print(f"   {description}")
    
    # Parameters
    required_params = function_data.get('required_params', [])
    optional_params = function_data.get('optional_params', [])
    
    if required_params:
        print(f"\n🔴 Required Parameters ({len(required_params)}):")
        for param in required_params[:5]:  # Show first 5
            if isinstance(param, dict):
                param_name = param.get('name', str(param))
                param_type = param.get('type', 'Any')
                param_desc = param.get('description', '')
                print(f"   • {param_name}: {param_type}")
                if param_desc:
                    print(f"     └─ {param_desc}")
            else:
                print(f"   • {param}")
        if len(required_params) > 5:
            print(f"   ... and {len(required_params) - 5} more")
    
    if optional_params:
        print(f"\n🟡 Optional Parameters ({len(optional_params)}):")
        for param in optional_params[:3]:  # Show first 3
            if isinstance(param, dict):
                param_name = param.get('name', str(param))
                param_type = param.get('type', 'Any')
                param_desc = param.get('description', '')
                print(f"   • {param_name}: {param_type}")
                if param_desc:
                    print(f"     └─ {param_desc}")
            else:
                print(f"   • {param}")
        if len(optional_params) > 3:
            print(f"   ... and {len(optional_params) - 3} more")
    
    # Examples
    examples = function_data.get('examples', [])
    if examples:
        print(f"\n💡 Examples ({len(examples)}):")
        for i, example in enumerate(examples[:3], 1):  # Show first 3
            if isinstance(example, dict):
                example_desc = example.get('description', f'Example {i}')
                example_code = example.get('code', '')
                print(f"   {i}. {example_desc}")
                if example_code:
                    print(f"      Code: {example_code[:100]}{'...' if len(example_code) > 100 else ''}")
            else:
                print(f"   {i}. {str(example)[:100]}{'...' if len(str(example)) > 100 else ''}")
        if len(examples) > 3:
            print(f"   ... and {len(examples) - 3} more examples")
    
    # Code snippets
    code_snippets = function_data.get('code_snippets', [])
    if code_snippets:
        print(f"\n💻 Code Snippets ({len(code_snippets)}):")
        for i, snippet in enumerate(code_snippets[:2], 1):  # Show first 2
            print(f"   {i}. {snippet[:150]}{'...' if len(snippet) > 150 else ''}")
        if len(code_snippets) > 2:
            print(f"   ... and {len(code_snippets) - 2} more snippets")
    
    # Instructions
    instructions = function_data.get('instructions', [])
    if instructions:
        print(f"\n📖 Instructions ({len(instructions)}):")
        for i, instruction in enumerate(instructions[:2], 1):  # Show first 2
            if isinstance(instruction, dict):
                inst_title = instruction.get('title', f'Instruction {i}')
                inst_content = instruction.get('content', '')
                print(f"   {i}. {inst_title}")
                if inst_content:
                    print(f"      {inst_content[:100]}{'...' if len(inst_content) > 100 else ''}")
            else:
                print(f"   {i}. {str(instruction)[:100]}{'...' if len(str(instruction)) > 100 else ''}")
        if len(instructions) > 2:
            print(f"   ... and {len(instructions) - 2} more instructions")
    
    # Source code
    source_code = function_data.get('source_code', '')
    if source_code:
        print(f"\n🔧 Source Code:")
        print(f"   {source_code[:200]}{'...' if len(source_code) > 200 else ''}")
    
    # Use cases
    use_cases = function_data.get('use_cases', [])
    if use_cases:
        print(f"\n🎯 Use Cases ({len(use_cases)}):")
        for i, use_case in enumerate(use_cases[:3], 1):
            print(f"   {i}. {use_case}")
        if len(use_cases) > 3:
            print(f"   ... and {len(use_cases) - 3} more")
    
    # Tags and keywords
    tags = function_data.get('tags', [])
    keywords = function_data.get('keywords', [])
    if tags or keywords:
        print(f"\n🏷️  Tags: {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}")
        print(f"🔍 Keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
    
    print("-" * 60)

def print_comprehensive_function_details(function_data: Dict[str, Any]):
    """Print detailed comprehensive function information including all code blocks."""
    print(f"\n🔧 Detailed Function Information:")
    print("=" * 80)
    
    # Basic info
    name = function_data.get('function_name', 'Unknown')
    print(f"📝 Function Name: {name}")
    print(f"🔗 Pipeline: {function_data.get('pipe_name', 'Unknown')}")
    print(f"📦 Module: {function_data.get('module', 'Unknown')}")
    print(f"🏷️  Category: {function_data.get('category', 'Unknown')}")
    print(f"📂 Subcategory: {function_data.get('subcategory', 'Unknown')}")
    print(f"⚡ Complexity: {function_data.get('complexity', 'Unknown')}")
    print(f"🎯 Confidence: {function_data.get('confidence_score', 0.0):.2f}")
    
    # Description
    description = function_data.get('description', 'No description available')
    if description:
        print(f"\n📋 Description:")
        print(f"   {description}")
    
    # Function signature
    signature = function_data.get('function_signature', '')
    if signature:
        print(f"\n🔧 Function Signature:")
        print(f"   {signature}")
    
    # Docstring
    docstring = function_data.get('docstring', '')
    if docstring:
        print(f"\n📖 Docstring:")
        print(f"   {docstring}")
    
    # Source code - FULL CODE BLOCK
    source_code = function_data.get('source_code', '')
    if source_code:
        print(f"\n💻 FULL SOURCE CODE:")
        print("=" * 40)
        print(source_code)
        print("=" * 40)
    
    # Code snippets - ALL CODE SNIPPETS
    code_snippets = function_data.get('code_snippets', [])
    if code_snippets:
        print(f"\n💻 CODE SNIPPETS ({len(code_snippets)}):")
        for i, snippet in enumerate(code_snippets, 1):
            print(f"\n--- Code Snippet {i} ---")
            print(snippet)
            print("-" * 30)
    
    # Examples with code
    examples = function_data.get('examples', [])
    if examples:
        print(f"\n💡 EXAMPLES WITH CODE ({len(examples)}):")
        for i, example in enumerate(examples, 1):
            print(f"\n--- Example {i} ---")
            if isinstance(example, dict):
                example_desc = example.get('description', f'Example {i}')
                example_code = example.get('code', '')
                context = example.get('context', '')
                print(f"Description: {example_desc}")
                if context:
                    print(f"Context: {context}")
                if example_code:
                    print("Code:")
                    print(example_code)
            else:
                print(f"Example: {example}")
            print("-" * 30)
    
    # Instructions
    instructions = function_data.get('instructions', [])
    if instructions:
        print(f"\n📖 INSTRUCTIONS ({len(instructions)}):")
        for i, instruction in enumerate(instructions, 1):
            print(f"\n--- Instruction {i} ---")
            if isinstance(instruction, dict):
                inst_title = instruction.get('title', f'Instruction {i}')
                inst_content = instruction.get('content', '')
                inst_context = instruction.get('context', '')
                print(f"Title: {inst_title}")
                if inst_context:
                    print(f"Context: {inst_context}")
                if inst_content:
                    print(f"Content: {inst_content}")
            else:
                print(f"Instruction: {instruction}")
            print("-" * 30)
    
    # Business cases
    business_cases = function_data.get('business_cases', [])
    if business_cases:
        print(f"\n💼 Business Cases ({len(business_cases)}):")
        for i, case in enumerate(business_cases, 1):
            print(f"   {i}. {case}")
    
    # Configuration hints
    config_hints = function_data.get('configuration_hints', {})
    if config_hints:
        print(f"\n⚙️  Configuration Hints:")
        for key, value in config_hints.items():
            print(f"   • {key}: {value}")
    
    # Typical parameters
    typical_params = function_data.get('typical_parameters', {})
    if typical_params:
        print(f"\n🎯 Typical Parameters:")
        for key, value in typical_params.items():
            print(f"   • {key}: {value}")
    
    print("=" * 80)

def print_code_example_info(result: Dict[str, Any], index: int = 1):
    """Print code example information."""
    print(f"\n💻 Code Example #{index}:")
    print("-" * 40)
    
    metadata = result.get('metadata', {})
    content = result.get('content', '')
    score = result.get('score', 0.0)
    
    function_name = metadata.get('function_name', 'Unknown')
    snippet_index = metadata.get('snippet_index', 'Unknown')
    
    print(f"Function: {function_name}")
    print(f"Snippet Index: {snippet_index}")
    print(f"Score: {score:.3f}")
    print(f"\nCode:")
    print(content)

def print_instruction_info(result: Dict[str, Any], index: int = 1):
    """Print instruction information."""
    print(f"\n📖 Instruction #{index}:")
    print("-" * 40)
    
    metadata = result.get('metadata', {})
    content = result.get('content', '')
    score = result.get('score', 0.0)
    
    function_name = metadata.get('function_name', 'Unknown')
    instruction_title = metadata.get('instruction_title', 'Unknown')
    instruction_index = metadata.get('instruction_index', 'Unknown')
    
    print(f"Function: {function_name}")
    print(f"Title: {instruction_title}")
    print(f"Index: {instruction_index}")
    print(f"Score: {score:.3f}")
    print(f"\nContent:")
    print(content)

async def main():
    """Main demonstration function with comprehensive output and code blocks."""
    print_section("Enhanced Comprehensive Registry Demo", 
                 "This demo shows how to get comprehensive function data including examples, code snippets, and instructions.")
    
    try:
        # Import the enhanced comprehensive registry
        from app.tools.mltools.registry.enhanced_comprehensive_registry import (
            initialize_enhanced_comprehensive_registry,
            EnhancedComprehensiveRegistry
        )
        
        # Initialize the enhanced comprehensive registry
        print_section("Initializing Enhanced Comprehensive Registry")
        print_info("This will load comprehensive function data with examples, code snippets, and instructions")
        
        registry = initialize_enhanced_comprehensive_registry(
            collection_name="comprehensive_ml_functions_demo",
            force_recreate=False,  # Set to True if you want to recreate the collection
            enable_separate_collections=True
        )
        
        print_success("Enhanced Comprehensive Registry initialized")
        
        # Get registry statistics
        print_section("Registry Statistics")
        stats = registry.get_registry_statistics()
        print_info(f"Total functions: {stats.get('total_functions', 0)}")
        print_info(f"Total documents: {stats.get('total_documents', 0)}")
        print_info(f"Collections: {list(stats.get('collections', {}).keys())}")
        
        # Test comprehensive function search
        print_section("Comprehensive Function Search")
        test_queries = [
            "time series analysis",
            "anomaly detection", 
            "cohort analysis",
            "variance calculation"
        ]
        
        for query in test_queries:
            print_section(f"Searching: '{query}'")
            print_info(f"Searching for functions related to: {query}")
            
            # Use the enhanced search_functions method
            search_results = registry.search_functions(
                query=query,
                n_results=3,
                has_examples=True,  # Only get functions with examples
                has_instructions=True  # Only get functions with instructions
            )
            
            if search_results:
                print_success(f"Found {len(search_results)} comprehensive function(s)")
                
                for i, result in enumerate(search_results, 1):
                    print_comprehensive_function_info(result, i)
            else:
                print_warning("No comprehensive functions found")
        
        # Test getting specific function by name with all comprehensive data
        print_section("Get Function by Name with Comprehensive Data")
        if search_results:
            first_function = search_results[0]
            function_name = first_function.get('function_name')
            
            if function_name:
                print_info(f"Getting comprehensive data for: {function_name}")
                comprehensive_data = registry.get_function_by_name(function_name)
                
                if comprehensive_data:
                    print_success("Retrieved comprehensive function data")
                    print_comprehensive_function_details(comprehensive_data)
                else:
                    print_warning("Could not retrieve comprehensive data")
        
        # Test searching specific collection types for code examples
        print_section("Searching Code Examples Collection")
        code_results = registry.search_by_collection_type(
            query="pandas dataframe operations",
            collection_type="code_examples",
            n_results=3
        )
        
        if code_results:
            print_success(f"Found {len(code_results)} code example(s)")
            for i, result in enumerate(code_results, 1):
                print_code_example_info(result, i)
        else:
            print_warning("No code examples found")
        
        # Test searching instructions collection
        print_section("Searching Instructions Collection")
        instruction_results = registry.search_by_collection_type(
            query="how to configure parameters",
            collection_type="instructions",
            n_results=3
        )
        
        if instruction_results:
            print_success(f"Found {len(instruction_results)} instruction(s)")
            for i, result in enumerate(instruction_results, 1):
                print_instruction_info(result, i)
        else:
            print_warning("No instructions found")
        
        # Test unified search across all collections
        print_section("Unified Search Across All Collections")
        unified_results = registry.search_unified(
            query="time series forecasting",
            n_results=5
        )
        
        if unified_results:
            print_success(f"Found {len(unified_results)} result(s) across all collections")
            for i, result in enumerate(unified_results[:3], 1):  # Show first 3
                collection_type = result['metadata'].get('collection_type', 'Unknown')
                function_name = result['metadata'].get('function_name', 'Unknown')
                print_info(f"  {i}. [{collection_type}] {function_name}")
        else:
            print_warning("No unified results found")
        
        print_success("Comprehensive demo completed successfully!")
        
    except Exception as e:
        print_error(f"Demo failed: {e}")
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())