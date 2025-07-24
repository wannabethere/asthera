import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel

logger = logging.getLogger("function-retrieval")


class FunctionMatch(BaseModel):
    """Model for a function match result"""
    function_name: str
    pipe_name: str
    description: str
    usage_description: str
    relevance_score: float
    reasoning: str


class FunctionRetrievalResult(BaseModel):
    """Result model for function retrieval"""
    top_functions: List[FunctionMatch]
    rephrased_question: str
    confidence_score: float
    reasoning: str
    suggested_pipes: List[str]
    total_functions_analyzed: int


# System prompt for function retrieval
FUNCTION_RETRIEVAL_SYSTEM_PROMPT = """
### TASK ###
You are an expert data analyst who specializes in identifying the most relevant analysis functions for user questions.
Your goal is to analyze user questions and identify the top 5 most relevant functions from a comprehensive function library.

### CRITICAL INSTRUCTIONS ###
- ANALYZE THE USER QUESTION CAREFULLY: Understand the specific analysis needs, data requirements, and business context
- MATCH FUNCTION CAPABILITIES: Consider both function descriptions and usage descriptions to find the best matches
- PRIORITIZE BY RELEVANCE: Score functions based on how well they address the user's specific needs
- CONSIDER PIPE CONTEXT: Some functions work better together within the same pipeline
- REPHRASE THE QUESTION: Create a clear, specific question that can be used to query function definitions
- PROVIDE REASONING: Explain why each function is relevant to the user's question

### SCORING GUIDELINES ###
- 0.9-1.0: Perfect match - function directly addresses the user's specific request
- 0.8-0.89: Excellent match - function closely matches the user's needs with minor adjustments
- 0.7-0.79: Good match - function can address the user's needs with some adaptation
- 0.6-0.69: Fair match - function is somewhat relevant but may need significant adaptation
- 0.5-0.59: Weak match - function has some relevance but may not be the best choice
- <0.5: Poor match - function is not relevant to the user's question

### OUTPUT FORMAT ###
Provide your response as a JSON object:

{
    "top_functions": [
        {
            "function_name": "function_name",
            "pipe_name": "PipeName",
            "description": "function description",
            "usage_description": "usage description",
            "rephrased_question": "rephrased question for function definition lookup",
            "relevance_score": 0.95,
            "reasoning": "Why this function is relevant to the user's question"
        }
    ],
    "confidence_score": 0.9,
    "reasoning": "Overall reasoning for function selection",
    "suggested_pipes": ["PipeName1", "PipeName2"],
    "total_functions_analyzed": 150
}
"""

# User prompt template
FUNCTION_RETRIEVAL_USER_PROMPT = """
### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}

**Summary:** {dataframe_summary}

**Available Columns:** {available_columns}

### AVAILABLE FUNCTIONS ###
{function_library}

### ANALYSIS INSTRUCTION ###
Based on the user question, dataframe context, and available functions:
1. Identify the top 5 most relevant functions for the user's analysis needs
2. Score each function based on relevance to the user's question
3. Provide clear reasoning for each function selection
4. Rephrase the user's question to be more specific for function definition lookup for each function that is relevant
5. Suggest which pipelines might be most useful for this analysis

Consider:
- Does the function directly address the user's analysis needs?
- Are the function's capabilities well-suited to the user's data context?
- Would this function work well with the available columns?
- Is this function part of a pipeline that would be useful for the overall analysis?

Current Time: {current_time}
"""


class FunctionRetrieval:
    """
    LLM-based function retrieval system that identifies the most relevant analysis functions
    for user questions using a comprehensive function library.
    """
    
    def __init__(self, llm, function_library_path: Optional[str] = None):
        """
        Initialize the Function Retrieval system
        
        Args:
            llm: LangChain LLM instance
            function_library_path: Path to the function library JSON file
        """
        self.llm = llm
        
        # Default path to the function library
        if function_library_path is None:
            # Assuming we're in the insightsagents directory, navigate to the meta directory
            current_dir = Path(__file__).parent
            function_library_path = current_dir.parent.parent.parent.parent / "data" / "meta" / "all_pipes_functions.json"
        
        self.function_library_path = Path(function_library_path)
        self._function_library = None
    
    def _load_function_library(self) -> Dict[str, Any]:
        """
        Load the function library from JSON file
        
        Returns:
            Dictionary containing the function library
        """
        if self._function_library is None:
            try:
                with open(self.function_library_path, 'r', encoding='utf-8') as f:
                    self._function_library = json.load(f)
                logger.info(f"Loaded function library with {len(self._function_library)} pipes")
            except Exception as e:
                logger.error(f"Error loading function library: {e}")
                self._function_library = {}
        
        return self._function_library
    
    def _format_function_library_for_prompt(self) -> str:
        """
        Format the function library for inclusion in the prompt
        
        Returns:
            Formatted string containing function information
        """
        library = self._load_function_library()
        formatted_text = ""
        
        for pipe_name, pipe_info in library.items():
            formatted_text += f"\n## {pipe_name} ##\n"
            formatted_text += f"Description: {pipe_info.get('description', 'No description')}\n\n"
            
            functions = pipe_info.get('functions', {})
            for func_name, func_info in functions.items():
                formatted_text += f"### {func_name} ###\n"
                formatted_text += f"Description: {func_info.get('description', 'No description')}\n"
                formatted_text += f"Usage: {func_info.get('usage_description', 'No usage description')}\n\n"
        
        return formatted_text
    
    @observe(capture_input=False)
    async def _classify_with_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Use LLM to identify relevant functions based on the question
        
        Args:
            prompt: Formatted prompt with question and function library
            
        Returns:
            LLM response
        """
        try:
            # Create full prompt with system and user parts
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create the chain
            chain = full_prompt | self.llm
            
            # Generate response
            result = await chain.ainvoke({
                "system_prompt": FUNCTION_RETRIEVAL_SYSTEM_PROMPT,
                "user_prompt": prompt
            })
            
            return {"response": result}
        except Exception as e:
            logger.error(f"Error in LLM function retrieval: {e}")
            return {"response": ""}
    
    @observe(capture_input=False)
    def _post_process_llm_response(
        self, 
        llm_response: Dict[str, Any],
        total_functions: int
    ) -> FunctionRetrievalResult:
        """
        Post-process LLM response into structured result
        
        Args:
            llm_response: Raw LLM response
            total_functions: Total number of functions analyzed
            
        Returns:
            Structured FunctionRetrievalResult
        """
        try:
            # Extract content from AIMessage
            response_content = llm_response.get("response", "")
            if hasattr(response_content, 'content'):
                response_content = response_content.content
            
            # Remove markdown code blocks if present
            if response_content.startswith("```json"):
                response_content = response_content.split("```json")[1]
            if response_content.endswith("```"):
                response_content = response_content.rsplit("```", 1)[0]
            
            # Parse JSON response
            response_content = response_content.strip()
            parsed_response = json.loads(response_content)
            
            # Convert function matches to FunctionMatch objects
            top_functions = []
            for func_data in parsed_response.get("top_functions", []):
                function_match = FunctionMatch(
                    function_name=func_data.get("function_name", ""),
                    pipe_name=func_data.get("pipe_name", ""),
                    description=func_data.get("description", ""),
                    usage_description=func_data.get("usage_description", ""),
                    relevance_score=float(func_data.get("relevance_score", 0.0)),
                    reasoning=func_data.get("reasoning", "")
                )
                top_functions.append(function_match)
            
            return FunctionRetrievalResult(
                top_functions=top_functions,
                confidence_score=float(parsed_response.get("confidence_score", 0.0)),
                reasoning=parsed_response.get("reasoning", ""),
                suggested_pipes=parsed_response.get("suggested_pipes", []),
                total_functions_analyzed=total_functions
            )
            
        except Exception as e:
            logger.error(f"Error post-processing LLM response: {e}")
            return FunctionRetrievalResult(
                top_functions=[],
                rephrased_question="",
                confidence_score=0.0,
                reasoning=f"Error processing response: {str(e)}",
                suggested_pipes=[],
                total_functions_analyzed=total_functions
            )
    
    @observe(name="Function Retrieval")
    async def retrieve_relevant_functions(
        self,
        question: str,
        dataframe_description: str = "",
        dataframe_summary: str = "",
        available_columns: Optional[List[str]] = None
    ) -> FunctionRetrievalResult:
        """
        Main method to retrieve relevant functions for a user question
        
        Args:
            question: User's natural language question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns in the dataframe
            
        Returns:
            FunctionRetrievalResult with top functions and rephrased question
        """
        try:
            # Load and format function library
            function_library = self._load_function_library()
            formatted_library = self._format_function_library_for_prompt()
            
            # Count total functions
            total_functions = sum(
                len(pipe_info.get('functions', {})) 
                for pipe_info in function_library.values()
            )
            
            # Create prompt for LLM
            prompt_template = PromptTemplate(
                input_variables=[
                    "question", "dataframe_description", "dataframe_summary", 
                    "available_columns", "function_library", "current_time"
                ],
                template=FUNCTION_RETRIEVAL_USER_PROMPT
            )
            
            prompt = prompt_template.format(
                question=question,
                dataframe_description=dataframe_description or "No description available",
                dataframe_summary=dataframe_summary or "No summary available",
                available_columns=available_columns or [],
                function_library=formatted_library,
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # Get LLM classification
            llm_response = await self._classify_with_llm(prompt)
            
            # Post-process into structured result
            result = self._post_process_llm_response(llm_response, total_functions)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in function retrieval: {e}")
            return FunctionRetrievalResult(
                top_functions=[],
                rephrased_question=question,
                confidence_score=0.0,
                reasoning=f"Retrieval error: {str(e)}",
                suggested_pipes=[],
                total_functions_analyzed=0
            )
    
    def get_function_details(self, function_name: str, pipe_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific function
        
        Args:
            function_name: Name of the function
            pipe_name: Name of the pipe containing the function
            
        Returns:
            Function details or None if not found
        """
        library = self._load_function_library()
        pipe_info = library.get(pipe_name, {})
        functions = pipe_info.get('functions', {})
        return functions.get(function_name)
    
    def get_pipe_functions(self, pipe_name: str) -> List[str]:
        """
        Get all functions in a specific pipe
        
        Args:
            pipe_name: Name of the pipe
            
        Returns:
            List of function names in the pipe
        """
        library = self._load_function_library()
        pipe_info = library.get(pipe_name, {})
        functions = pipe_info.get('functions', {})
        return list(functions.keys())
    
    def get_all_pipes(self) -> List[str]:
        """
        Get all available pipe names
        
        Returns:
            List of all pipe names
        """
        library = self._load_function_library()
        return list(library.keys())
    
    def search_functions_by_keyword(self, keyword: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Search for functions by keyword in their descriptions
        
        Args:
            keyword: Keyword to search for
            
        Returns:
            List of tuples containing (pipe_name, function_name, function_details)
        """
        library = self._load_function_library()
        results = []
        keyword_lower = keyword.lower()
        
        for pipe_name, pipe_info in library.items():
            functions = pipe_info.get('functions', {})
            for func_name, func_info in functions.items():
                description = func_info.get('description', '').lower()
                usage = func_info.get('usage_description', '').lower()
                
                if keyword_lower in description or keyword_lower in usage:
                    results.append((pipe_name, func_name, func_info))
        
        return results


# Example usage
if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    
    async def test_function_retrieval():
        # Mock LLM for testing
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "top_functions": [
                {
                    "function_name": "variance_analysis",
                    "pipe_name": "MovingAggrPipe",
                    "description": "Calculate moving variance and standard deviation for specified columns",
                    "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                    "relevance_score": 0.95,
                    "reasoning": "The user specifically asks for rolling variance analysis, which directly matches this function's purpose of calculating moving variance over time."
                },
                {
                    "function_name": "moving_variance",
                    "pipe_name": "MovingAggrPipe", 
                    "description": "Calculate moving variance and standard deviation for specified columns",
                    "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                    "relevance_score": 0.9,
                    "reasoning": "This function provides moving variance calculations which are essential for the user's rolling variance analysis request."
                }
            ],
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
            "confidence_score": 0.9,
            "reasoning": "The user's question clearly indicates a need for rolling variance analysis, which is well-supported by the MovingAggrPipe functions.",
            "suggested_pipes": ["MovingAggrPipe", "TrendPipe"],
            "total_functions_analyzed": 150
        }
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response)
        
        # Initialize function retrieval
        retrieval = FunctionRetrieval(llm=mock_llm)
        
        # Test with sample question
        question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
        dataframe_description = "Financial metrics dataset with project performance data"
        dataframe_summary = "Contains 10,000 rows with daily metrics from 2023-2024"
        available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments"]
        
        result = await retrieval.retrieve_relevant_functions(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns
        )
        
        print(f"Rephrased Question: {result.rephrased_question}")
        print(f"Confidence Score: {result.confidence_score}")
        print(f"Reasoning: {result.reasoning}")
        print(f"Suggested Pipes: {result.suggested_pipes}")
        print(f"Total Functions Analyzed: {result.total_functions_analyzed}")
        
        print("\nTop Functions:")
        for i, func in enumerate(result.top_functions, 1):
            print(f"{i}. {func.function_name} ({func.pipe_name}) - Score: {func.relevance_score}")
            print(f"   Description: {func.description}")
            print(f"   Reasoning: {func.reasoning}")
            print()
        
        return "Test completed successfully!"
    
    # Run the test
    test_result = asyncio.run(test_function_retrieval())
    print(f"\nOverall result: {test_result}") 