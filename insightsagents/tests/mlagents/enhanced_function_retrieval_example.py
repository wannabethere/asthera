"""
Enhanced Function Retrieval Example

This example demonstrates how to use the enhanced function retrieval system
that attaches specific examples, instructions, and examples store for each
retrieved function to help LLMs make better decisions on generating functions or code.

Key Features:
1. Function retrieval with context enrichment
2. Examples retrieval from usage_examples collection
3. Instructions retrieval from instructions collection
4. Examples store retrieval from insights collection
5. Historical rules and hardcoded patterns
6. Enhanced LLM prompts with rich context
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from unittest.mock import Mock

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.mlagents.enhanced_function_retrieval import EnhancedFunctionRetrieval
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval


class MockLLM:
    """Mock LLM for testing purposes"""
    
    def __init__(self):
        self.response_templates = {
            "function_retrieval": '''
            {
                "top_functions": [
                    {
                        "function_name": "variance_analysis",
                        "pipe_name": "MovingAggrPipe",
                        "description": "Calculate moving variance and standard deviation for specified columns",
                        "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                        "relevance_score": 0.95,
                        "reasoning": "The user specifically asks for rolling variance analysis, which directly matches this function's purpose of calculating moving variance over time.",
                        "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time"
                    },
                    {
                        "function_name": "moving_variance",
                        "pipe_name": "MovingAggrPipe",
                        "description": "Calculate moving variance and standard deviation for specified columns",
                        "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                        "relevance_score": 0.9,
                        "reasoning": "This function provides moving variance calculations which are essential for the user's rolling variance analysis request.",
                        "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time"
                    }
                ],
                "confidence_score": 0.9,
                "reasoning": "The user's question clearly indicates a need for rolling variance analysis, which is well-supported by the MovingAggrPipe functions.",
                "suggested_pipes": ["MovingAggrPipe", "TrendPipe"],
                "total_functions_analyzed": 150
            }
            ''',
            "step_matching": '''
            {
                "step_matches": {
                    "1": [
                        {
                            "function_name": "variance_analysis",
                            "pipe_name": "MovingAggrPipe",
                            "relevance_score": 0.95,
                            "reasoning": "Perfect match for calculating rolling variance in step 1",
                            "description": "Calculate moving variance and standard deviation for specified columns",
                            "usage_description": "Measures volatility and variability over time",
                            "category": "time_series",
                            "function_definition": {}
                        }
                    ],
                    "2": [
                        {
                            "function_name": "moving_variance",
                            "pipe_name": "MovingAggrPipe",
                            "relevance_score": 0.9,
                            "reasoning": "Good match for additional variance calculations in step 2",
                            "description": "Calculate moving variance and standard deviation for specified columns",
                            "usage_description": "Measures volatility and variability over time",
                            "category": "time_series",
                            "function_definition": {}
                        }
                    ]
                }
            }
            '''
        }
    
    async def ainvoke(self, input_data: Dict[str, Any]) -> Mock:
        """Mock async invoke method"""
        response = Mock()
        
        if "system_prompt" in input_data and "user_prompt" in input_data:
            # Function retrieval response
            response.content = self.response_templates["function_retrieval"]
        else:
            # Step matching response
            response.content = self.response_templates["step_matching"]
        
        return response


class MockRetrievalHelper:
    """Mock RetrievalHelper for testing purposes"""
    
    def __init__(self):
        self.mock_data = {
            "examples": [
                {
                    "function_name": "variance_analysis",
                    "example_code": "variance_analysis(df, columns=['price'], window_size=5)",
                    "description": "Calculate 5-day rolling variance for price column",
                    "parameters": {
                        "columns": ["price"],
                        "window_size": 5,
                        "method": "rolling"
                    }
                },
                {
                    "function_name": "variance_analysis",
                    "example_code": "variance_analysis(df, columns=['volume'], window_size=10)",
                    "description": "Calculate 10-day rolling variance for volume column",
                    "parameters": {
                        "columns": ["volume"],
                        "window_size": 10,
                        "method": "rolling"
                    }
                }
            ],
            "insights": [
                {
                    "function_name": "variance_analysis",
                    "insight": "Variance analysis works best with at least 30 data points per window",
                    "best_practices": [
                        "Ensure data is sorted by time",
                        "Handle missing values before calculation",
                        "Use appropriate window sizes based on data frequency"
                    ]
                }
            ],
            "instructions": [
                {
                    "question": "How to calculate rolling variance?",
                    "instruction": "Use variance_analysis function with appropriate window size based on data frequency",
                    "project_id": "test_project"
                }
            ]
        }
    
    async def get_function_examples(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """Mock function examples retrieval"""
        examples = [ex for ex in self.mock_data["examples"] if ex["function_name"] == function_name]
        return {
            "examples": examples,
            "scores": [0.9, 0.8] if examples else [],
            "avg_score": 0.85 if examples else 0.0,
            "total_examples": len(examples),
            "function_name": function_name
        }
    
    async def get_function_insights(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """Mock function insights retrieval"""
        insights = [ins for ins in self.mock_data["insights"] if ins["function_name"] == function_name]
        return {
            "insights": insights,
            "scores": [0.9] if insights else [],
            "avg_score": 0.9 if insights else 0.0,
            "total_insights": len(insights),
            "function_name": function_name
        }
    
    async def get_instructions(self, query: str, project_id: str, **kwargs) -> Dict[str, Any]:
        """Mock instructions retrieval"""
        instructions = self.mock_data["instructions"]
        return {
            "instructions": instructions,
            "scores": [0.9],
            "avg_score": 0.9,
            "total_instructions": len(instructions)
        }
    
    async def get_function_definition(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """Mock function definition retrieval"""
        return {
            "function_definition": {
                "name": function_name,
                "description": f"Mock definition for {function_name}",
                "parameters": ["columns", "window_size", "method"],
                "returns": "DataFrame with variance calculations"
            }
        }
    
    async def get_function_definition_by_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """Mock function definition retrieval by query"""
        return await self.get_function_definition("variance_analysis")


async def demonstrate_enhanced_function_retrieval():
    """Demonstrate the enhanced function retrieval system"""
    
    print("🚀 Enhanced Function Retrieval Demo")
    print("=" * 50)
    
    # Initialize components
    mock_llm = MockLLM()
    mock_retrieval_helper = MockRetrievalHelper()
    
    # Initialize enhanced function retrieval
    enhanced_retrieval = EnhancedFunctionRetrieval(
        llm=mock_llm,
        retrieval_helper=mock_retrieval_helper
    )
    
    # Initialize regular function retrieval for comparison
    regular_retrieval = FunctionRetrieval(
        llm=mock_llm,
        retrieval_helper=mock_retrieval_helper
    )
    
    # Test data
    question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
    dataframe_description = "Financial metrics dataset with project performance data"
    dataframe_summary = "Contains 10,000 rows with daily metrics from 2023-2024"
    available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments"]
    project_id = "test_project"
    
    # Mock reasoning plan
    reasoning_plan = [
        {
            "step_number": 1,
            "step_title": "Calculate Rolling Variance",
            "step_description": "Calculate 5-day rolling variance for flux metric",
            "data_requirements": ["flux", "timestamp"]
        },
        {
            "step_number": 2,
            "step_title": "Group Analysis",
            "step_description": "Group by projects, cost centers, and departments",
            "data_requirements": ["projects", "cost_centers", "departments"]
        }
    ]
    
    print("\n📊 Test Question:")
    print(f"   {question}")
    print(f"\n📈 Dataframe: {dataframe_description}")
    print(f"📋 Columns: {', '.join(available_columns)}")
    
    # Test Enhanced Function Retrieval
    print("\n🔍 Testing Enhanced Function Retrieval...")
    print("-" * 40)
    
    try:
        enhanced_result = await enhanced_retrieval.retrieve_and_match_functions(
            reasoning_plan=reasoning_plan,
            question=question,
            rephrased_question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id
        )
        
        print(f"✅ Enhanced retrieval completed successfully!")
        print(f"   📊 Total functions retrieved: {enhanced_result.total_functions_retrieved}")
        print(f"   🎯 Steps covered: {enhanced_result.total_steps_covered}")
        print(f"   📈 Average relevance score: {enhanced_result.average_relevance_score:.2f}")
        print(f"   🎯 Confidence score: {enhanced_result.confidence_score:.2f}")
        print(f"   💭 Reasoning: {enhanced_result.reasoning}")
        
        # Display step matches with enriched context
        print(f"\n📋 Step-Function Matches:")
        for step_num, functions in enhanced_result.step_matches.items():
            print(f"\n   Step {step_num}:")
            for func in functions:
                print(f"     🔧 Function: {func.get('function_name', 'unknown')}")
                print(f"        📦 Pipeline: {func.get('pipe_name', 'unknown')}")
                print(f"        📊 Relevance: {func.get('relevance_score', 0):.2f}")
                print(f"        💭 Reasoning: {func.get('reasoning', 'No reasoning')}")
                
                # Show enriched context
                examples = func.get('examples', [])
                if examples:
                    print(f"        📚 Examples ({len(examples)}):")
                    for i, example in enumerate(examples[:2], 1):
                        print(f"          {i}. {example.get('description', str(example)[:100])}...")
                
                instructions = func.get('instructions', [])
                if instructions:
                    print(f"        📝 Instructions ({len(instructions)}):")
                    for i, instruction in enumerate(instructions[:2], 1):
                        print(f"          {i}. {instruction.get('instruction', str(instruction)[:100])}...")
                
                historical_rules = func.get('historical_rules', [])
                if historical_rules:
                    print(f"        📜 Historical Rules ({len(historical_rules)}):")
                    for i, rule in enumerate(historical_rules[:2], 1):
                        content = rule.get('content', str(rule))
                        print(f"          {i}. {content[:100]}...")
                
                print()
        
    except Exception as e:
        print(f"❌ Enhanced retrieval failed: {e}")
    
    # Test Regular Function Retrieval
    print("\n🔍 Testing Regular Function Retrieval...")
    print("-" * 40)
    
    try:
        regular_result = await regular_retrieval.retrieve_relevant_functions(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id
        )
        
        print(f"✅ Regular retrieval completed successfully!")
        print(f"   📊 Total functions analyzed: {regular_result.total_functions_analyzed}")
        print(f"   🎯 Confidence score: {regular_result.confidence_score:.2f}")
        print(f"   💭 Reasoning: {regular_result.reasoning}")
        print(f"   📦 Suggested pipes: {', '.join(regular_result.suggested_pipes)}")
        
        # Display top functions with enriched context
        print(f"\n🏆 Top Functions:")
        for i, func in enumerate(regular_result.top_functions, 1):
            print(f"\n   {i}. {func.function_name} ({func.pipe_name})")
            print(f"      📊 Relevance: {func.relevance_score:.2f}")
            print(f"      💭 Reasoning: {func.reasoning}")
            print(f"      🔄 Rephrased: {func.rephrased_question}")
            
            # Show enriched context
            if func.examples:
                print(f"      📚 Examples ({len(func.examples)}):")
                for j, example in enumerate(func.examples[:2], 1):
                    print(f"        {j}. {example.get('description', str(example)[:100])}...")
            
            if func.instructions:
                print(f"      📝 Instructions ({len(func.instructions)}):")
                for j, instruction in enumerate(func.instructions[:2], 1):
                    print(f"        {j}. {instruction.get('instruction', str(instruction)[:100])}...")
            
            if func.historical_rules:
                print(f"      📜 Historical Rules ({len(func.historical_rules)}):")
                for j, rule in enumerate(func.historical_rules[:2], 1):
                    content = rule.get('content', str(rule))
                    print(f"        {j}. {content[:100]}...")
        
    except Exception as e:
        print(f"❌ Regular retrieval failed: {e}")
    
    print("\n🎉 Demo completed!")
    print("\nKey Benefits of Enhanced Function Retrieval:")
    print("✅ Context-rich function matching with examples and instructions")
    print("✅ Historical rules and patterns for better decision making")
    print("✅ Project-specific instructions for customized behavior")
    print("✅ Examples store for learning from past implementations")
    print("✅ Hardcoded rules for domain-specific best practices")
    print("✅ Enhanced LLM prompts with comprehensive context")


async def demonstrate_function_input_extraction():
    """Demonstrate how the enhanced context helps with function input extraction"""
    
    print("\n🔧 Function Input Extraction Demo")
    print("=" * 50)
    
    # This would typically use the actual function input extractor
    # but we'll show how the enriched context would be used
    
    enriched_function_data = {
        "function_name": "variance_analysis",
        "pipe_name": "MovingAggrPipe",
        "description": "Calculate moving variance and standard deviation for specified columns",
        "usage_description": "Measures volatility and variability over time",
        "examples": [
            {
                "function_name": "variance_analysis",
                "example_code": "variance_analysis(df, columns=['price'], window_size=5)",
                "description": "Calculate 5-day rolling variance for price column",
                "parameters": {
                    "columns": ["price"],
                    "window_size": 5,
                    "method": "rolling"
                }
            }
        ],
        "instructions": [
            {
                "question": "How to calculate rolling variance?",
                "instruction": "Use variance_analysis function with appropriate window size based on data frequency",
                "project_id": "test_project"
            }
        ],
        "historical_rules": [
            {
                "type": "hardcoded_rule",
                "content": "For time series analysis, always ensure data is sorted by time column before applying rolling functions",
                "source": "hardcoded"
            }
        ]
    }
    
    context = "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time"
    columns = ["flux", "timestamp", "projects", "cost_centers", "departments"]
    
    print(f"📝 Context: {context}")
    print(f"📋 Available columns: {', '.join(columns)}")
    print(f"🔧 Function: {enriched_function_data['function_name']}")
    
    print(f"\n📚 Available Examples:")
    for i, example in enumerate(enriched_function_data['examples'], 1):
        print(f"  {i}. {example['description']}")
        print(f"     Code: {example['example_code']}")
        print(f"     Parameters: {example['parameters']}")
    
    print(f"\n📝 Available Instructions:")
    for i, instruction in enumerate(enriched_function_data['instructions'], 1):
        print(f"  {i}. {instruction['instruction']}")
    
    print(f"\n📜 Historical Rules:")
    for i, rule in enumerate(enriched_function_data['historical_rules'], 1):
        print(f"  {i}. {rule['content']}")
    
    # Simulate how an LLM would use this context
    print(f"\n🤖 LLM Decision Process:")
    print("  1. Analyze user context: '5-day rolling variance of flux'")
    print("  2. Match with examples: Found similar example with window_size=5")
    print("  3. Apply instructions: Use appropriate window size based on data frequency")
    print("  4. Follow historical rules: Ensure data is sorted by time column")
    print("  5. Generate parameters:")
    print("     - columns: ['flux'] (from context)")
    print("     - window_size: 5 (from context and examples)")
    print("     - method: 'rolling' (from examples)")
    print("     - groupby: ['projects', 'cost_centers', 'departments'] (from context)")


if __name__ == "__main__":
    # Run the demonstrations
    asyncio.run(demonstrate_enhanced_function_retrieval())
    asyncio.run(demonstrate_function_input_extraction())
