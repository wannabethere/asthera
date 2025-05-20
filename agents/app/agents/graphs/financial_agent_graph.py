"""
LangGraph Integration with Vector-Based Financial Fluctuation Recommender

This script demonstrates how to integrate the Vector-Based Financial Fluctuation 
Recommender into a LangGraph workflow to create a complete analysis pipeline.
"""

import json
import os
from typing import Dict, List, Any, TypedDict, Annotated, Literal
import operator
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END

# Import the components from the vector-based recommender module
from chatbot.multiagent_planners.nodes.recommender_agent import (
    FinancialFluctuationVectorRecommender
)


# Define the state for the graph
class FinancialAnalysisState(TypedDict, total=False):
    """State for the financial fluctuation analysis graph."""
    # Input state
    question: str
    schema: str
    function_specs: List[Dict[str, Any]]
    
    # Intermediate states
    function_store: Any  # FunctionVectorStore instance
    relevant_functions: Dict[str, Any]
    recommendations: Dict[str, Any]
    formatted_recommendations: str
    grades: Dict[str, Any]
    
    # Output state
    next_steps: Dict[str, Any]
    final_response: str
    error: str


# Define the next steps recommender
class NextStepsRecommender:
    """Recommends next steps based on recommendations and available functions."""
    
    def __init__(self, llm=None):
        # Initialize LLM if not provided
        if llm is None:
            self.llm = ChatOpenAI(model="gpt-4", temperature=0.2)
        else:
            self.llm = llm
        
        # Define the prompt for recommending next steps
        self.prompt = PromptTemplate(
            template="""
            You are a financial data analysis expert. Your goal is to recommend next steps for a user who wants to analyze
            financial fluctuations based on the recommendations and available functions.
            
            Here's the original question:
            <question>{question}</question>
            
            Here's the data schema:
            <schema>{schema}</schema>
            
            Here are the recommended follow-up questions:
            <recommendations>{recommendations}</recommendations>
            
            Here are the available analysis functions:
            <available_functions>{available_functions}</available_functions>
            
            Instructions:
            * Recommend 3-5 concrete next steps the user should take to analyze their financial fluctuation data.
            * Each step should be specific, actionable, and directly relevant to the user's question.
            * Include which functions to use and what parameters to set for each step.
            * Organize steps in a logical order of execution.
            * For each step, provide a brief explanation of why this step is important and what it will help discover.
            
            Return your response in the following JSON format:
            {{
                "next_steps": [
                    {{
                        "step": "Step description",
                        "function": "function_name",
                        "parameters": {{"param1": "value1", "param2": "value2"}},
                        "explanation": "Why this step is important"
                    }},
                    ...
                ],
                "summary": "A concise 1-2 sentence summary of the recommended approach"
            }}
            """,
            input_variables=["question", "schema", "recommendations", "available_functions"]
        )
        
        # Create the LLM chain
        self.chain = self.prompt | self.llm | JsonOutputParser()
    
    def recommend_next_steps(self, 
                            question: str, 
                            schema: str, 
                            recommendations: Dict[str, Any],
                            available_functions: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend next steps based on the recommendations and available functions."""
        
        return self.chain.invoke({
            "question": question,
            "schema": schema,
            "recommendations": json.dumps(recommendations, indent=2),
            "available_functions": json.dumps(available_functions, indent=2)
        })


# Define the response formatter
class ResponseFormatter:
    """Formats the final response to the user."""
    
    def __init__(self, llm=None):
        # Initialize LLM if not provided
        if llm is None:
            self.llm = ChatOpenAI(model="gpt-4", temperature=0.2)
        else:
            self.llm = llm
        
        # Define the prompt for formatting the response
        self.prompt = PromptTemplate(
            template="""
            You are a financial data analysis expert. Your goal is to create a comprehensive response for a user
            who wants to analyze financial fluctuations.
            
            Here's the original question:
            <question>{question}</question>
            
            Here are the recommended follow-up questions:
            <recommendations>{recommendations}</recommendations>
            
            Here are the recommended next steps:
            <next_steps>{next_steps}</next_steps>
            
            Instructions:
            * Create a complete, well-structured response that helps the user analyze their financial fluctuation data.
            * Start by acknowledging the user's question and providing a brief overview of the approach.
            * Include the recommended follow-up questions to help clarify their analysis needs.
            * Include the recommended next steps as a concrete action plan.
            * Use a professional but friendly tone.
            * Format the response using markdown for readability.
            
            Return your response as a markdown-formatted string.
            """,
            input_variables=["question", "recommendations", "next_steps"]
        )
        
        # Create the LLM chain
        self.chain = self.prompt | self.llm
    
    def format_response(self, 
                       question: str, 
                       recommendations: str, 
                       next_steps: Dict[str, Any]) -> str:
        """Format the final response to the user."""
        
        return self.chain.invoke({
            "question": question,
            "recommendations": recommendations,
            "next_steps": json.dumps(next_steps, indent=2)
        })


# Node functions for the graph

def initialize_function_store(state: FinancialAnalysisState) -> FinancialAnalysisState:
    """Initialize the function vector store and load functions."""
    try:
        # Initialize the embeddings model
        embeddings = OpenAIEmbeddings()
        
        # Create the function store
        function_store = FunctionVectorStore(embedding_model=embeddings)
        
        # Load functions from specs
        if "function_specs" in state:
            for spec in state["function_specs"]:
                if "source" in spec and "document_content" in spec:
                    source = spec["source"]
                    content = spec["document_content"]
                    
                    # Determine category from filename
                    category = source.split("_")[0] if "_" in source else "unknown"
                    
                    # Parse content if it's a string
                    if isinstance(content, str):
                        try:
                            content_dict = json.loads(content)
                            function_store.add_functions_from_spec(content_dict, category)
                        except json.JSONDecodeError:
                            return {"error": f"Error parsing content from {source}", **state}
                    else:
                        # If content is already a dictionary
                        function_store.add_functions_from_spec(content, category)
        
        # Update the state
        return {"function_store": function_store, **state}
    except Exception as e:
        return {"error": f"Error initializing function store: {str(e)}", **state}


def find_relevant_functions(state: FinancialAnalysisState) -> FinancialAnalysisState:
    """Find functions relevant for financial fluctuation analysis."""
    try:
        # Get the function store
        function_store = state["function_store"]
        
        # Define criteria for financial fluctuation functions
        criteria = {
            "keywords": ["variance", "fluctuation", "volatility", "trend", "change", "growth", "deviation", "anomaly"],
            "categories": ["timeseries", "trend"]
        }
        
        # Get functions using vector similarity and filtering
        relevant_functions = function_store.get_functions_for_analysis_type(
            analysis_type="financial fluctuation",
            schema=state["schema"],
            top_k=20
        )
        
        # Apply criteria filtering
        filtered_functions = function_store.filter_functions_by_criteria(criteria)
        
        # Keep only functions that are both relevant and match criteria
        relevant_functions = {
            name: spec for name, spec in relevant_functions.items()
            if name in filtered_functions
        }
        
        # Update the state
        return {"relevant_functions": relevant_functions, **state}
    except Exception as e:
        return {"error": f"Error finding relevant functions: {str(e)}", **state}


def generate_recommendations(state: FinancialAnalysisState) -> FinancialAnalysisState:
    """Generate recommendations for financial fluctuation analysis."""
    try:
        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-4", temperature=0.2)
        
        # Initialize the recommender with the function store
        recommender = FinancialFluctuationVectorRecommender(
            function_store=state["function_store"],
            llm=llm
        )
        
        # Generate recommendations using the relevant functions
        agent_result = recommender.agent.invoke({
            "business_question": state["question"], 
            "schema": state["schema"],
            "available_functions": json.dumps(state["relevant_functions"], indent=2)
        })
        
        # Format the recommendations
        formatted_recommendations = recommender.format_recommendations_for_display(agent_result)
        
        # Update the state
        return {
            "recommendations": agent_result,
            "formatted_recommendations": formatted_recommendations,
            **state
        }
    except Exception as e:
        return {"error": f"Error generating recommendations: {str(e)}", **state}


def recommend_next_steps(state: FinancialAnalysisState) -> FinancialAnalysisState:
    """Recommend next steps based on recommendations and available functions."""
    try:
        # Initialize the next steps recommender
        next_steps_recommender = NextStepsRecommender()
        
        # Recommend next steps
        next_steps = next_steps_recommender.recommend_next_steps(
            question=state["question"],
            schema=state["schema"],
            recommendations=state["recommendations"],
            available_functions=state["relevant_functions"]
        )
        
        # Update the state
        return {"next_steps": next_steps, **state}
    except Exception as e:
        return {"error": f"Error recommending next steps: {str(e)}", **state}


def format_response(state: FinancialAnalysisState) -> FinancialAnalysisState:
    """Format the final response."""
    try:
        # Initialize the response formatter
        formatter = ResponseFormatter()
        
        # Format the response
        final_response = formatter.format_response(
            question=state["question"],
            recommendations=state["formatted_recommendations"],
            next_steps=state["next_steps"]
        )
        
        # Update the state
        return {"final_response": final_response, **state}
    except Exception as e:
        return {"error": f"Error formatting response: {str(e)}", **state}


def should_end_due_to_error(state: FinancialAnalysisState) -> Literal["end", "continue"]:
    """Check if the process should end due to an error."""
    if "error" in state and state["error"]:
        return "end"
    return "continue"


# Create the graph
def create_financial_analysis_graph():
    """Create the financial fluctuation analysis graph."""
    # Initialize the graph
    graph = StateGraph(FinancialAnalysisState)
    
    # Add nodes
    graph.add_node("initialize_function_store", initialize_function_store)
    graph.add_node("find_relevant_functions", find_relevant_functions)
    graph.add_node("generate_recommendations", generate_recommendations)
    graph.add_node("recommend_next_steps", recommend_next_steps)
    graph.add_node("format_response", format_response)
    
    # Add edges
    graph.add_edge("initialize_function_store", "find_relevant_functions")
    graph.add_edge("find_relevant_functions", "generate_recommendations")
    graph.add_edge("generate_recommendations", "recommend_next_steps")
    graph.add_edge("recommend_next_steps", "format_response")
    graph.add_edge("format_response", END)
    
    # Add conditional edges for error handling
    graph.add_conditional_edges(
        "initialize_function_store",
        should_end_due_to_error,
        {
            "end": END,
            "continue": "find_relevant_functions"
        }
    )
    
    graph.add_conditional_edges(
        "find_relevant_functions",
        should_end_due_to_error,
        {
            "end": END,
            "continue": "generate_recommendations"
        }
    )
    
    graph.add_conditional_edges(
        "generate_recommendations",
        should_end_due_to_error,
        {
            "end": END,
            "continue": "recommend_next_steps"
        }
    )
    
    graph.add_conditional_edges(
        "recommend_next_steps",
        should_end_due_to_error,
        {
            "end": END,
            "continue": "format_response"
        }
    )
    
    # Set the entry point
    graph.set_entry_point("initialize_function_store")
    
    # Compile the graph
    return graph.compile()


# Example usage
def main():
    """Main function to demonstrate the LangGraph integration with vector-based recommender."""
    # Create the graph
    financial_analysis_graph = create_financial_analysis_graph()
    
    # Example function specs
    example_specs = [
        {
            "source": "timeseries_analysis_spec.json",
            "document_content": json.dumps({
                "functions": {
                    "variance_analysis": {
                        "description": "Calculate variance and standard deviation for time series data",
                        "required_params": ["columns"],
                        "optional_params": ["method", "window", "time_column", "group_columns", "suffix"]
                    },
                    "lag": {
                        "description": "Create lag (past) values for specified columns",
                        "required_params": ["columns"],
                        "optional_params": ["periods", "time_column", "group_columns", "suffix"]
                    },
                    "distribution_analysis": {
                        "description": "Analyze the distribution of values in specified columns",
                        "required_params": ["columns"],
                        "optional_params": ["bins", "group_columns", "normalize"]
                    }
                }
            })
        },
        {
            "source": "trend_analysis_spec.json",
            "document_content": json.dumps({
                "functions": {
                    "aggregate_by_time": {
                        "description": "Aggregate data by time periods",
                        "required_params": ["date_column", "metric_columns"],
                        "optional_params": ["time_period", "aggregation", "fill_missing"]
                    },
                    "calculate_growth_rates": {
                        "description": "Calculate growth rates for aggregated metrics",
                        "required_params": [],
                        "optional_params": ["window", "annualize", "method"]
                    },
                    "calculate_moving_average": {
                        "description": "Calculate moving averages for time series data",
                        "required_params": [],
                        "optional_params": ["window", "method", "center"]
                    }
                }
            })
        }
    ]
    
    # Example input
    input_state = {
        "question": "Can you show me which projects, cost centers, or regions have the most fluctuation in daily financial performance over time?",
        "schema": "Date,Region,Cost center,Project,Account,Source,Category,Event Type,PO No,Transactional value,Functional value,PO with Line item",
        "function_specs": example_specs
    }
    
    # Run the graph
    print("Running Financial Analysis Graph...")
    config = {"recursion_limit": 25}
    result = financial_analysis_graph.invoke(input_state, config)
    
    # Print the final response
    if "error" in result and result["error"]:
        print(f"Error: {result['error']}")
    else:
        print("\nFinal Response:")
        print(result["final_response"])
        
        print("\nRecommended Next Steps:")
        print(json.dumps(result["next_steps"], indent=2))


if __name__ == "__main__":
    main()