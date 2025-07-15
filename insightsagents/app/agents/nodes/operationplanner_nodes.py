from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import os
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.pydantic import PydanticOutputParser
from langchain.schema import AIMessage

# Define the data models for our Operation
class OperationStep(BaseModel):
    """A single step in an analytics Operation."""
    
    step_number: int = Field(description="The position of this step in the Operation")
    purpose: str = Field(description="What this step accomplishes")
    function_name: str = Field(description="The analytics function to use")
    input_features: List[str] = Field(description="Required data features/columns")
    parameters: Dict[str, str] = Field(description="Parameter values for the function")
    output: str = Field(description="Description of the output from this step")
    rationale: str = Field(description="Explanation of why this step is important")

class AnalyticsOperation(BaseModel):
    """A complete analytics Operation plan."""
    
    question: str = Field(description="The original user question")
    steps: List[OperationStep] = Field(description="Ordered sequence of Operation steps")
    final_output: str = Field(description="Description of the final analysis output")

# Define the function database to store our analytical functions
class AnalyticsFunction(BaseModel):
    name: str
    description: str
    category: str
    required_params: List[str]
    optional_params: List[str]
    output_description: str

class FunctionDatabase:
    """Database of available analytics functions."""
    
    def __init__(self):
        self.functions: Dict[str, AnalyticsFunction] = {}
        self.categories: List[str] = []
        
    def load_from_directory(self, directory_path: str):
        """
        Load all function specifications from JSON files in a directory.
        
        Args:
            directory_path: Path to the directory containing JSON spec files
        """
        # Get all JSON files in the directory
        if not os.path.isdir(directory_path):
            raise ValueError(f"Directory not found: {directory_path}")
        
        spec_files = {}
        for filename in os.listdir(directory_path):
            if filename.endswith('.json'):
                file_path = os.path.join(directory_path, filename)
                with open(file_path, 'r') as f:
                    file_content = f.read()
                    # Extract category name from filename (remove _spec.json)
                    category = filename.replace('_spec.json', '')
                    spec_files[category] = file_content
        
        return self.load_from_specs(spec_files)
    
    def load_from_specs(self, spec_files: Dict[str, str]):
        """
        Load functions from specification JSON files.
        
        Args:
            spec_files: Dictionary mapping category names to JSON content
        """
        for category, file_content in spec_files.items():
            # Parse the JSON content
            try:
                spec_data = json.loads(file_content)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON for category {category}: {e}")
                continue
            
            # Add the category to our list
            if category not in self.categories:
                self.categories.append(category)
            
            # Process each function in the specification
            if "functions" not in spec_data:
                print(f"Warning: No functions found in category {category}")
                continue
                
            for func_name, func_spec in spec_data["functions"].items():
                try:
                    self.functions[func_name] = AnalyticsFunction(
                        name=func_name,
                        description=func_spec["description"],
                        category=category,
                        required_params=func_spec["required_params"],
                        optional_params=func_spec["optional_params"],
                        output_description=func_spec["outputs"]["description"]
                    )
                except KeyError as e:
                    print(f"Missing key in function {func_name}: {e}")
                    continue
        
        # Return self for method chaining
        return self
    
    def get_function_by_name(self, name: str) -> Optional[AnalyticsFunction]:
        """Get function details by name."""
        return self.functions.get(name)
    
    def get_functions_by_category(self, category: str) -> List[AnalyticsFunction]:
        """Get all functions in a specific category."""
        return [f for f in self.functions.values() if f.category == category]
    
    def get_function_summary(self) -> str:
        """Generate a summary of all available functions by category."""
        summary = []
        
        for category in self.categories:
            summary.append(f"## {category.replace('_', ' ').title()}")
            funcs = self.get_functions_by_category(category)
            
            for func in funcs:
                params = ", ".join(func.required_params)
                summary.append(f"- **{func.name}**: {func.description} (Required: {params})")
            
            summary.append("")
        
        return "\n".join(summary)
    
    def get_function_details(self, function_names: List[str]) -> str:
        """Get detailed information about specific functions."""
        details = []
        
        for name in function_names:
            func = self.get_function_by_name(name)
            if func:
                details.append(f"## {func.name}")
                details.append(f"Description: {func.description}")
                details.append(f"Category: {func.category}")
                details.append(f"Required parameters: {', '.join(func.required_params)}")
                details.append(f"Optional parameters: {', '.join(func.optional_params)}")
                details.append(f"Output: {func.output_description}")
                details.append("")
        
        return "\n".join(details)

# Define the OperationPlannerAgent
class OperationPlannerAgent:
    """Agent for planning an analytics Operation."""
    
    def __init__(self, llm, function_db: FunctionDatabase):
        self.llm = llm
        self.function_db = function_db
        self.output_parser = PydanticOutputParser(pydantic_object=AnalyticsOperation)
        
        # The prompt template drives the agent's behavior
        self.template = """
        You are a data analytics Operation planner. Your job is to create a step-by-step plan to answer a user's analytics question.

        # USER QUESTION
        {user_question}
        
        # MATCHED FUNCTIONS
        {matched_functions}
        
        # IDENTIFIED FEATURES
        {identified_features}
        
        # AVAILABLE FUNCTIONS DETAILS
        {function_details}
        
        # TASK
        Create a logical sequence of analytical steps that would answer the user's question. 
        Think step by step about the logical order of operations needed to perform this analysis.
        Each step should build on previous steps, transforming the data progressively toward the final answer.
        
        Create 3-5 steps that break down the analytics process into a clear chain of operations.
        
        For each step:
        1. Identify which function to use
        2. Specify which features/columns are needed
        3. List the parameter values that should be passed to the function
        4. Explain what the output of this step will be
        5. Provide a rationale for why this step is necessary
        6. For the output generated please dont include any comments on the output code generated. 
        
        {format_instructions}
        """
        
        self.prompt = PromptTemplate(
            template=self.template,
            input_variables=["user_question", "matched_functions", "identified_features", "function_details"],
            partial_variables={"format_instructions": self.output_parser.get_format_instructions()}
        )
        
    def create_Operation_plan(self, 
                           question: str, 
                           matched_functions: List[Dict[str, Any]], 
                           identified_features: List[Dict[str, Any]]) -> AnalyticsOperation:
        """Create a Operation plan for the analytics question."""
        
        # Extract function names from matched functions
        function_names = [f["function_name"] for f in matched_functions]
        
        # Get detailed information about these functions
        function_details = self.function_db.get_function_details(function_names)
        
        # Prepare the inputs for the language model
        inputs = {
            "user_question": question,
            "matched_functions": str(matched_functions),
            "identified_features": str(identified_features),
            "function_details": function_details
        }
        
        # Generate the Operation plan using the language model
        #prompt_value = self.prompt.format(**inputs)
        #agent = self.prompt | self.llm | self.output_parser
        
        # Parse the response into our structured AnalyticsOperation object
        try:
                # Generate the prompt and format it with our inputs
            agent = self.prompt | self.llm 
            response = agent.invoke(inputs)
            print("response: ", response.content)
            # Extract text from the LLM response
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, AIMessage):
                response_text = response.content
            else:
                response_text = str(response)
            
           
            parsed_data = json.loads(response_text)
            print("parsed_data: ", parsed_data)
            print("AnalyticsOperation.model_validate(parsed_data): ", AnalyticsOperation.model_validate(parsed_data))
                # Create AnalyticsOperation from the parsed JSON
            return AnalyticsOperation.model_validate(parsed_data)
                
        except Exception as e:
            # Handle parsing errors gracefully
            print(f"Error parsing response: {e}")
            # Return a simplified Operation in case of parsing error
            return AnalyticsOperation(
                question=question,
                steps=[
                    OperationStep(
                        step_number=1,
                        purpose="Process the data based on the query",
                        function_name=function_names[0] if function_names else "unknown",
                        input_features=[],
                        parameters={},
                        output="Data processing result",
                        rationale="Initial data processing step"
                    )
                ],
                final_output="Analysis result for the query (Note: Error in parsing detailed Operation)"
            )

# Define the PipelineTranslatorAgent to explain the Operation in natural language
class PipelineTranslatorAgent:
    """Agent for translating a Operation plan into a pipeline structure explanation."""
    
    def __init__(self, llm):
        self.llm = llm
        
        self.template = """
        You are a data pipeline structure translator. Your job is to explain how an analytics Operation would be implemented as a pipeline structure.

        # Operation PLAN
        {Operation_plan}
        
        # TASK
        Explain in natural language how this Operation would be structured as a data pipeline, similar to the example below but WITHOUT generating actual code.

        Example Pipeline Structure:
        ```
        CohortPipe.from_dataframe(transactions_df)
            | form_behavioral_cohorts(...)
            | calculate_lifetime_value(...)
        ```

        For Risk Analysis Operations, use RiskPipe:
        ```
        RiskPipe.from_dataframe(returns_df)
            | fit_distribution(...)
            | calculate_var(...)
            | calculate_portfolio_risk(...)
        ```

        Your explanation should:
        1. Identify the starting data source/pipe (CohortPipe, RiskPipe, etc.)
        2. Describe each transformation step in sequence
        3. Explain the key parameters that would be needed at each step
        4. Describe how the output would address the original question
        5. For risk analysis, emphasize the logical flow: data preparation → distribution fitting → risk calculation → portfolio analysis → stress testing

        Remember to use natural language and NOT to generate actual code.
        """
        
        self.prompt = PromptTemplate(
            template=self.template,
            input_variables=["Operation_plan"]
        )
    
    def translate_to_pipeline(self, Operation_plan: AnalyticsOperation) -> str:
        """Translate a Operation plan into a pipeline structure explanation."""
        
        # Generate the pipeline explanation
        prompt_value = self.prompt.format(Operation_plan=str(Operation_plan))
        pipeline_explanation = self.llm.invoke(prompt_value)
        
        return pipeline_explanation

# Example usage in a complete analytics Operation system
def create_analytics_system(spec_files: Dict[str, str], llm):
    """Create a complete analytics Operation planning system."""
    
    # Initialize the function database
    function_db = FunctionDatabase()
    function_db.load_from_specs(spec_files)
    
    # Create the Operation planner agent
    Operation_planner = OperationPlannerAgent(llm, function_db)
    
    # Create the pipeline translator agent
    pipeline_translator = PipelineTranslatorAgent(llm)
    
    return {
        "function_db": function_db,
        "Operation_planner": Operation_planner,
        "pipeline_translator": pipeline_translator
    }

# Usage example
def process_analytics_question(analytics_system, question, matched_functions, identified_features):
    """Process an analytics question through the Operation planning pipeline."""
    
    # Create the Operation plan
    print("Creating Operation plan")
    Operation_plan = analytics_system["Operation_planner"].create_Operation_plan(
        question=question,
        matched_functions=matched_functions,
        identified_features=identified_features
    )
    
    # Translate the Operation plan to a pipeline structure explanation
    pipeline_explanation = analytics_system["pipeline_translator"].translate_to_pipeline(Operation_plan)
    
    # Return the results
    return {
        "operation_plan": Operation_plan,
        "pipeline_explanation": pipeline_explanation
    }
