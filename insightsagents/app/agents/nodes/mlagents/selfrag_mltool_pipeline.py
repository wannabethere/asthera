from langchain.agents import Tool
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from typing import Dict, List, Any, Optional
import json
import re

def clean_json_response(response: str) -> str:
    """
    Clean a response that may contain markdown code blocks around JSON
    
    Args:
        response: The raw response from the LLM
        
    Returns:
        Cleaned JSON string
    """
    cleaned = response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]  # Remove ```json
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]  # Remove ```
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]  # Remove trailing ```
    return cleaned.strip()

# Import the existing FunnelAnalysisAgent
# from your_module import FunnelAnalysisAgent

FORWARD_PLANNER_PROMPT = """
You are a funnel analysis planning expert who helps users analyze user journeys through conversion funnels.

QUESTION:
{question}

DATAFRAME INFORMATION:
{dataframe_info}

Your task is to create a step-by-step plan for the funnel analysis, working from the initial data to the final insights.
Focus on creating a coherent pipeline that addresses the user's question completely.

THOUGHT PROCESS:
{agent_scratchpad}
"""

PIPELINE_OPERATORS = """
Pipeline Operators are the functions that can be used to analyze the data.
They are defined in the function_specs.json file.
"time_series_analysis": TimeSeriesPipe,
"time series operation": TimeSeriesPipe,
"cohort_analysis": CohortPipe,
"cohort analysis operation": CohortPipe,
"funnel_analysis": FunnelPipe,
"funnel analysis operation": FunnelPipe,
"segmentation": SegmentationPipe,
"segmentation operation": SegmentationPipe,
"trend_analysis": TrendPipe,
"trend analysis operation": TrendPipe,
"risk_analysis": RiskPipe,
"risk analysis operation": RiskPipe,
"metric_analysis": MetricPipe,
"metric analysis operation": MetricPipe,
"operation analysis": OperationPipe,
"operation operation": OperationPipe,

"""

class SelfCorrectingForwardPlanner:
    """Self-correcting forward planner that uses the existing FunnelAnalysisAgent for various analysis types"""
    
    def __init__(self, llm, funnel_analysis_agent):
        """
        Initialize the Self-Correcting Forward Planner
        
        Args:
            llm: Language model instance
            funnel_analysis_agent: Existing FunnelAnalysisAgent instance
        """
        self.llm = llm
        self.funnel_analysis_agent = funnel_analysis_agent
        
        # Initialize memory for the agent
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        
        # Create the tools
        self.tools = self._create_tools()
        
    def _create_tools(self) -> List[Tool]:
        """Create the tools for the agent"""
        tools = [
            Tool(
                name="identify_analysis_goal",
                func=lambda query: self._identify_analysis_goal(query),
                description="Identifies the goal of the funnel analysis"
            ),
            Tool(
                name="identify_funnel_steps",
                func=lambda query, dataframe_info: self._identify_funnel_steps(query, dataframe_info),
                description="Identifies the funnel steps for the analysis"
            ),
            Tool(
                name="plan_pipeline_steps",
                func=lambda query, goal, funnel_steps: self._plan_pipeline_steps(query, goal, funnel_steps),
                description="Plans the sequence of operations for the funnel analysis"
            ),
            Tool(
                name="validate_and_correct_plan",
                func=lambda plan, query: self._validate_and_correct_plan(plan, query),
                description="Validates and corrects the funnel analysis plan"
            ),
            Tool(
                name="generate_step_code",
                func=lambda pipeline_operator, step_query: self._generate_step_code(pipeline_operator, step_query),
                description="Generates code for a step using the FunnelAnalysisAgent with pipeline operator context"
            ),
            Tool(
                name="assemble_pipeline",
                func=lambda steps: self._assemble_pipeline(steps),
                description="Assembles the complete pipeline from the individual steps"
            )
        ]
        return tools
    
    def _identify_analysis_goal(self, query: str, dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Identify the goal of the funnel analysis from the query
        
        Args:
            query: The user's question
            
        Returns:
            Dictionary with the identified goal
        """
        # Create a prompt template for identifying the goal
        goal_prompt = PromptTemplate(
            input_variables=["query", "dataframe_description","PIPELINE_OPERATORS"],
            template="""
            Based on the following question, identify the goal of the analysis:
            
            QUESTION:
            {query}
            
            DATAFRAME DESCRIPTION:
            {dataframe_description}

            PIPELINE OPERATORS:
            {PIPELINE_OPERATORS}
            
            Analyze the question to determine what type of analysis is being requested:
            - If it mentions variance, volatility, or statistical measures, it's likely variance analysis
            - If it mentions funnels, conversion, or user journeys, it's funnel analysis
            - If it mentions cohorts, retention, or time-based grouping, it's cohort analysis
            - If it mentions trends, patterns over time, it's trend analysis
            - If it mentions segmentation, clustering, or grouping, it's segmentation analysis
            - If it mentions risk, risk analysis, risk management, it's risk analysis
            - If it mentions metric, metric analysis, metric management, it's metric analysis
            - If it mentions operation, operation analysis, operation management, it's operation analysis
            
            Provide a concise description of the analysis goal in JSON format:
            {{
                "goal": "description_of_goal",
                "analysis_type": "variance_analysis|funnel_analysis|cohort_analysis|trend_analysis|segmentation_analysis|risk_analysis|metric_analysis|operation_analysis",
                "metrics": ["metric1", "metric2", ...],
                "dimensions": ["dimension1", "dimension2", ...],
                "segmentation": "segment_by_attribute_if_any"
            }}
            
            Only output valid JSON without any explanations.
            """
        )
        
        # Create the goal identification chain
        goal_chain = goal_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            print(f"Goal chain: Step 1 Identifying analysis goal")
            result = goal_chain.invoke({
                "query": query,
                "dataframe_description": dataframe_description or "No dataframe description provided",
                "PIPELINE_OPERATORS": PIPELINE_OPERATORS
            })
            
            # Clean the result by removing markdown code blocks if present
            cleaned_result = clean_json_response(result)
            
            # Parse the JSON result
            goal_data = json.loads(cleaned_result)
            print(f"Goal data: {goal_data}")


            return {
                "status": "success",
                "goal": goal_data.get("goal", ""),
                "analysis_type": goal_data.get("analysis_type", "funnel_analysis"),
                "metrics": goal_data.get("metrics", []),
                "dimensions": goal_data.get("dimensions", []),
                "segmentation": goal_data.get("segmentation", "")
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to identify analysis goal: {str(e)}",
                "goal": "Analysis",
                "analysis_type": "funnel_analysis",
                "metrics": ["conversion_rate"],
                "dimensions": [],
                "segmentation": ""
            }
    


    def _identify_funnel_steps(self, query: str, dataframe_info: str) -> Dict[str, Any]:
        """
        Identify the pipeline steps from the query and dataframe info
        
        Args:
            query: The user's question
            dataframe_info: Information about the dataframe
            
        Returns:
            Dictionary with the identified pipeline steps
        """
        # Create a prompt template for identifying funnel steps
        steps_prompt = PromptTemplate(
            input_variables=["query", "dataframe_info","PIPELINE_OPERATORS"],
            template="""
            Based on the following question and dataframe information, identify the pipeline steps for the analysis:
            
            QUESTION:
            {query}
            
            DATAFRAME INFORMATION:
            {dataframe_info}
            
            PIPELINE OPERATORS:
            {PIPELINE_OPERATORS}

            IMPORTANT: 
            1. Identify the Pipeline Operator based on the question content and the pipeline operators provided.          
            3. Determine the operation type as SQL, Cohort Analysis, Segmentation, Machine Learning, Time Series, General Analysis, Risk analysis
            4. Consider potential challenges and include steps to address them
            5. Identify the features of the data that needed to be preprocessed as a natural language question 
            **5.1. Features could be groups by columns, rows, time, etc.
            **5.2. Features could be the columns that needed to be transformed, aggregated, etc.
            **5.3. Features could be the columns that needed to be filtered, sorted, etc.
            **5.5. Features could be the columns that needed to be pivoted, stacked, etc.
            **5.6. Features could be the columns that needed to be normalized, standardized, etc.
            **5.7. Features could be the columns that needed to be encoded, one-hot encoded, etc.
            6. Please include all the columns in the dataset provided in the context
            7. Make sure each step is specific and actionable
            8. For each step, Indicate whether the operation is a SQL operation, a feature engineering operation, a analysis operation, a machine learning operation, a time series operation, a general analysis operation
            9. Each step should use a function from the functions available + a possible SQL operation. If there is a choice between function available and SQL operation, use the function.
            10. For each step, identify the set of possible columns that can be used for the operation. 
            11. Include steps for validation and interpretation of results
            12. Align your approach with the specified planner type
            13. If the question involves a pipeline pattern, ensure your plan properly addresses the sequential flow of operations
            14. Incorporate detailed reasoning about your approach
            15. If the question involves a machine learning operation, ensure your plan properly addresses the machine learning operation
            16. If the question involves a time series operation, ensure your plan properly addresses the time series operation
            17. If the question involves a general analysis operation, ensure your plan properly addresses the general analysis operation
            18. If the question involves a cohort analysis operation, ensure your plan properly addresses the cohort analysis operation
            19. If the question involves a segmentation operation, ensure your plan properly addresses the segmentation operation
            20. If the question involves a trend analysis operation, ensure your plan properly addresses the trend analysis operation
            21. If the question involves a funnel analysis operation, ensure your plan properly addresses the funnel analysis operation
            22. If the question involves a time series analysis operation, ensure your plan properly addresses the time series analysis operation
            23. If the question involves a risk analysis operation, ensure your plan properly addresses the risk analysis operation
            24. If the question involves a metric analysis operation, ensure your plan properly addresses the metric analysis operation
            25. If the question involves an operation analysis operation, ensure your plan properly addresses the operation analysis operation
            26. Your plan should be thorough enough that another data scientist could follow it to answer the question.
            First provide your REASONING about how to approach this problem, then output the numbered steps of your plan, with one step per line.
               
            
            Provide the pipeline steps in JSON format:
            {
                "pipeline_steps": {
                    "pipeline_operator_name": ["step1", "step2", "step3", ...],
                    "another_operator_name": ["step1", "step2", "step3", ...]
                },
                "step_names": {
                    "Step 1": {
                        "columns": ["column_name: column_metric", "column_name: column_metric", ...]
                    },
                    "Step 2": {
                        "columns": ["column_name: column_metric", "column_name: column_metric", ...]
                    },
                    "Step 3": {
                        "columns": ["column_name: column_metric", "column_name: column_metric", ...]
                    }
                },
                "event_column": "event_column_name",
                "user_id_column": "user_id_column_name",
                "timestamp_column": "timestamp_column_name"
            }
            
            Only output valid JSON without any explanations.
            """
        )
        
        # Create the funnel steps identification chain
        steps_chain = steps_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            result = steps_chain.invoke({
                "query": query,
                "dataframe_info": dataframe_info,
                "PIPELINE_OPERATORS": PIPELINE_OPERATORS
            })
            
            # Clean the result by removing markdown code blocks if present
            cleaned_result = clean_json_response(result)
            print(f"Cleaned result: {cleaned_result}")
            # Parse the JSON result
            steps_data = json.loads(cleaned_result)
            
            return {
                "status": "success",
                "pipeline_steps": steps_data.get("pipeline_steps", {}),
                "step_names": steps_data.get("step_names", {}),
                "event_column": steps_data.get("event_column", "event"),
                "user_id_column": steps_data.get("user_id_column", "user_id"),
                "timestamp_column": steps_data.get("timestamp_column", "timestamp")
            }
        except Exception as e:
            # Try to determine the analysis type from the query for better fallback
            query_lower = query.lower()
            if any(word in query_lower for word in ["variance", "volatility", "statistical", "rolling"]):
                pipeline_operator = "variance_analysis"
                pipeline_steps = {
                    "variance_analysis": ["calculate_variance", "group_by_dimensions", "apply_rolling_window"]
                }
                step_names = {
                    "Step 1": {"columns": ["variance_calculation: statistical"]},
                    "Step 2": {"columns": ["grouping: dimensions"]},
                    "Step 3": {"columns": ["rolling_window: time_series"]}
                }
            elif any(word in query_lower for word in ["cohort", "retention", "time_period"]):
                pipeline_operator = "cohort_analysis"
                pipeline_steps = {
                    "cohort_analysis": ["form_cohorts", "calculate_retention", "analyze_patterns"]
                }
                step_names = {
                    "Step 1": {"columns": ["cohort_formation: grouping"]},
                    "Step 2": {"columns": ["retention_calculation: metrics"]},
                    "Step 3": {"columns": ["pattern_analysis: trends"]}
                }
            else:
                pipeline_operator = "funnel_analysis"
                pipeline_steps = {
                    "funnel_analysis": ["page_view", "product_view", "add_to_cart", "checkout", "purchase"]
                }
                step_names = {
                    "Step 1": {"columns": ["page_view: count"]},
                    "Step 2": {"columns": ["product_view: count"]},
                    "Step 3": {"columns": ["add_to_cart: count"]},
                    "Step 4": {"columns": ["checkout: count"]},
                    "Step 5": {"columns": ["purchase: count"]}
                }
            
            return {
                "status": "error",
                "message": f"Failed to identify funnel steps: {str(e)}",
                "pipeline_steps": pipeline_steps,
                "step_names": step_names,
                "event_column": "event",
                "user_id_column": "user_id",
                "timestamp_column": "timestamp"
            }
    
    def _plan_pipeline_steps(self, query: str, goal: Dict[str, Any], funnel_steps: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan the sequence of operations for the analysis
        
        Args:
            query: The user's question
            goal: The identified analysis goal
            funnel_steps: Dictionary containing pipeline_steps and step_names
            
        Returns:
            Dictionary with the pipeline steps
        """
        # Create a prompt template for planning the pipeline
        plan_prompt = PromptTemplate(
            input_variables=["query", "goal", "pipeline_steps", "step_names","pipeline_operations"],
            template="""
            Plan a sequence of operations for analysis based on the following:
            
            QUESTION:
            {query}
            
            ANALYSIS GOAL:
            {goal}
            
            PIPELINE STEPS:
            {pipeline_steps}
            
            STEP NAMES AND COLUMNS:
            {step_names}
            
            PIPELINE OPERATIONS:
            {pipeline_operations}
            
            IMPORTANT INSTRUCTIONS:
            1. For each step, Indicate whether the operation is a SQL operation, a feature engineering operation, a analysis operation, a machine learning operation, a time series operation, a general analysis operation
            2. Each step should use a function from the functions available + a possible SQL operation. If there is a choice between function available and SQL operation, use the function.
            3. For each step, identify the set of possible columns that can be used for the operation. 
            4. Include steps for validation and interpretation of results
            5. For each step focus on rolling window vs time based operation.
            AS an example:
            1. For variance analysis questions (mentioning variance, rolling, statistical):
               - Use "variance_analysis" as the operation
               - Focus on statistical calculations, rolling windows, and time series analysis
               - Include parameters like window size, group columns, time column
            
            2. For funnel analysis questions (mentioning conversion, user journey):
               - Use "analyze_funnel" as the operation
               - Focus on conversion events and user journeys
            
            3. For cohort analysis questions (mentioning retention, time periods):
               - Use "analyze_cohort" as the operation
               - Focus on time-based grouping and retention
            
            Create a pipeline plan in JSON format:
            {{
                "steps": [
                    {{
                        "step_number": 1,
                        "operation": "operation_name",
                        "description": "what_this_step_does",
                        "natural_language_query": "query_for_analysis_agent",
                        "inputs": {{
                            "param1": "value1",
                            "param2": "value2"
                        }}
                    }},
                    ...
                ]
            }}
            
            The first step should always be initializing the pipeline with the dataframe.
            Initialize Pipeline code should be based on the Pipeline Operator that has been identified.
            for ex: FunnelPipe.from_dataframe(events_df), or CohortPipe.from_dataframe(events_df) or TrendPipe.from_dataframe(events_df)
            Do not include any visualization steps.
            Only output valid JSON without any explanations.
            """
        )
        

        # Format the inputs as strings
        goal_str = json.dumps(goal, indent=2)
        pipeline_steps_str = json.dumps(funnel_steps.get("pipeline_steps", {}), indent=2)
        step_names_str = json.dumps(funnel_steps.get("step_names", {}), indent=2)
        
        print("================================================")
        print(f"Plan prompt: goal: {goal_str}, pipeline_steps: {pipeline_steps_str}, step_names: {step_names_str}")
        print("================================================")

        # Create the planning chain
        plan_chain = plan_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            print(f"  📤 Sending planning request to LLM...")
            result = plan_chain.invoke({
                "query": query,
                "goal": goal_str,
                "pipeline_steps": pipeline_steps_str,
                "step_names": step_names_str,
                "pipeline_operations": PIPELINE_OPERATORS
            })
            
            print(f"  📥 Received LLM response: {len(result)} characters")
            
            # Check if result is empty or None
            if not result or result.strip() == "":
                print(f"❌ Empty LLM response in _plan_pipeline_steps")
                return {
                    "status": "error",
                    "message": "Empty LLM response",
                    "steps": []
                }
            
            # Clean the result by removing markdown code blocks if present
            cleaned_result = clean_json_response(result)
            
            # Parse the JSON result
            try:
                print(f"  🔍 Attempting to parse JSON response...")
                plan_data = json.loads(cleaned_result)
                print(f"  ✅ JSON parsed successfully, found {len(plan_data.get('steps', []))} steps")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed in _plan_pipeline_steps: {str(e)}")
                print(f"❌ Raw result: {result[:200]}...")
                print(f"❌ Cleaned result: {cleaned_result[:200]}...")
                return {
                    "status": "error",
                    "message": f"JSON parsing failed: {str(e)}",
                    "steps": []
                }
            
            # Ensure steps are properly numbered
            steps = plan_data.get("steps", [])
            for i, step in enumerate(steps):
                step["step_number"] = i + 1
                
            # Debug: Check if the correct operation type is being generated
            for step in steps:
                operation = step.get("operation", "")
                print(f"  🔍 Step operation: {operation}")
                if "variance" in query.lower() and "variance" not in operation.lower():
                    print(f"  ⚠️  WARNING: Variance question but operation is '{operation}'")
                elif "funnel" in query.lower() and "funnel" not in operation.lower():
                    print(f"  ⚠️  WARNING: Funnel question but operation is '{operation}'")
                
            return {
                "status": "success",
                "steps": steps
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to plan pipeline steps: {str(e)}",
                "steps": []
            }
    
    def _validate_and_correct_plan(self, plan: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Validate and correct the analysis plan
        
        Args:
            plan: The initial pipeline plan
            query: The original user question
            
        Returns:
            Dictionary with the validated and corrected plan
        """
        # Create a prompt template for validation and correction
        validate_prompt = PromptTemplate(
            input_variables=["plan", "query","pipeline_operations"],
            template="""
            Review and correct the following analysis plan to ensure it completely addresses the user's question:
            
            PLAN:
            {plan}
            
            ORIGINAL QUESTION:
            {query}

            PIPELINE OPERATIONS:
            {pipeline_operations}
            
            IMPORTANT: Analyze the question type first to identify the pipeline operator:
            For ex: FunnelPipe, CohortPipe,TrendPipe
            - If the question mentions "variance", "rolling", "statistical" → This is a variance analysis
            - If the question mentions "conversion", "funnel", "user journey" → This is a funnel analysis
            - If the question mentions "cohort", "retention", "time period" → This is a cohort analysis
            
            Check for the following issues:
            1. Missing parameters required for any operation
            2. Incorrect parameter values
            3. Missing operations needed to fulfill the question
            4. Operations in an illogical order
            5. Redundant or unnecessary operations
            6. Wrong operation type for the question (e.g., using funnel analysis for variance questions)
            
            For variance analysis, ensure the operation is "variance_analysis" with appropriate parameters.
            For funnel analysis, ensure the operation is "analyze_funnel" with appropriate parameters.
            For cohort analysis, ensure the operation is "analyze_cohort" with appropriate parameters.
            
            Important: Do not include any visualization steps.
            Provide a corrected plan in JSON format:
            {{
                "steps": [
                    {{
                        "step_number": 1,
                        "operation": "operation_name",
                        "description": "what_this_step_does",
                        "natural_language_query": "query_for_analysis_agent",
                        "inputs": {{
                            "param1": "value1",
                            "param2": "value2"
                        }}
                    }},
                    ...
                ],
                "corrections": [
                    {{
                        "type": "correction_type",
                        "step_number": step_number,
                        "description": "description_of_correction"
                    }},
                    ...
                ]
            }}
            
            Only output valid JSON without any explanations.
            """
        )
        
        # Format the plan as a string
        plan_str = json.dumps(plan, indent=2)
        
        # Create the validation chain
        validate_chain = validate_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            print(f"  📤 Sending validation request to LLM...")
            result = validate_chain.invoke({
                "plan": plan_str,
                "query": query,
                "pipeline_operations": PIPELINE_OPERATORS
            })
            
            print(f"  📥 Received validation response: {len(result)} characters")
            
            # Check if result is empty or None
            if not result or result.strip() == "":
                print(f"❌ Empty LLM response in _validate_and_correct_plan")
                return {
                    "status": "error",
                    "message": "Empty LLM response",
                    "steps": plan.get("steps", []),
                    "corrections": []
                }
            
            # Clean the result by removing markdown code blocks if present
            cleaned_result = clean_json_response(result)
            
            # Parse the JSON result
            try:
                print(f"  🔍 Attempting to parse validation JSON response...")
                corrected_data = json.loads(cleaned_result)
                print(f"  ✅ Validation JSON parsed successfully, found {len(corrected_data.get('steps', []))} steps")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed in _validate_and_correct_plan: {str(e)}")
                print(f"❌ Raw result: {result[:200]}...")
                print(f"❌ Cleaned result: {cleaned_result[:200]}...")
                return {
                    "status": "error",
                    "message": f"JSON parsing failed: {str(e)}",
                    "steps": plan.get("steps", []),
                    "corrections": []
                }
            
            # Ensure steps are properly numbered
            steps = corrected_data.get("steps", plan.get("steps", []))
            for i, step in enumerate(steps):
                step["step_number"] = i + 1
                
            return {
                "status": "success",
                "steps": steps,
                "corrections": corrected_data.get("corrections", [])
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to validate and correct plan: {str(e)}",
                "steps": plan.get("steps", []),
                "corrections": []
            }
    
    def _generate_step_code(self, pipeline_operator: str, step_query: str) -> Dict[str, Any]:
        """
        Generate code for a step using the FunnelAnalysisAgent
        
        Args:
            pipeline_operator: The pipeline operator to use (e.g., "funnel_analysis", "cohort_analysis")
            step_query: Natural language query for the step
            
        Returns:
            Dictionary with the generated code
        """
        # Use the existing FunnelAnalysisAgent to generate code
        try:
            # Call the run method of the FunnelAnalysisAgent with pipeline operator context
            result = self.funnel_analysis_agent.run(
                query=step_query,
                pipeline_operator=pipeline_operator
            )
            
            # Check if result is valid
            if not result:
                print(f"❌ Empty result from FunnelAnalysisAgent for query: {step_query[:50]}...")
                return {
                    "status": "error",
                    "message": "Empty result from FunnelAnalysisAgent",
                    "code": "",
                    "pipeline_operator": pipeline_operator
                }
            
            # Extract the generated code
            generated_code = result.get("generated_code", "")
            function_type = result.get("function_type", "")
            function_inputs = result.get("function_inputs", {})
            
            # Check if generated code is empty
            if not generated_code:
                print(f"⚠️  Empty generated code from FunnelAnalysisAgent for query: {step_query[:50]}...")
            
            return {
                "status": "success",
                "code": generated_code,
                "function_type": function_type,
                "function_inputs": function_inputs,
                "pipeline_operator": pipeline_operator
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to generate step code: {str(e)}",
                "code": "",
                "pipeline_operator": pipeline_operator
            }
    
    def _assemble_pipeline(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assemble the complete pipeline from the individual steps
        
        Args:
            steps: List of pipeline steps with generated code
            
        Returns:
            Dictionary with the assembled pipeline code
        """
        # Create a prompt template for assembling the pipeline
        assemble_prompt = PromptTemplate(
            input_variables=["steps"],
            template="""
            Assemble a complete funnel analysis pipeline from the following steps:
            
            STEPS:
            {steps}
            
            The pipeline should follow this format:
            ```python
            result = (
                CohortPipe.from_dataframe(events_df)
                | operation1(param1='value1', param2='value2')
                | operation2(param1='value1', param2='value2')
                ...
            )
            ```
            
            Only output the assembled pipeline code without any explanations.
            """
        )
        
        # Format the steps as a string
        steps_str = json.dumps(steps, indent=2)
        
        # Create the assembly chain
        assemble_chain = assemble_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            result = assemble_chain.invoke({
                "steps": steps_str
            })
            
            # Clean up the code (remove markdown code blocks if present)
            code = result.strip()
            if code.startswith("```python"):
                code = code[10:]
            if code.endswith("```"):
                code = code[:-3]
            
            return {
                "status": "success",
                "pipeline_code": code.strip()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to assemble pipeline: {str(e)}",
                "pipeline_code": "# Error assembling pipeline"
            }
    
    def plan(self, question: str, dataframe_columns: List[str] = None, dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate a complete analysis plan and code
        
        Args:
            question: The user's question
            dataframe_columns: List of column names in the dataset
            dataframe_description: Dictionary with schema information
            
        Returns:
            Dictionary with the complete plan and generated code
        """
        import time
        start_time = time.time()
        max_execution_time = 300  # 5 minutes timeout
        # Prepare dataframe information
        dataframe_info = self._format_dataframe_info(dataframe_columns, dataframe_description)
        
        # Step 1: Identify the analysis goal
        print(f"🔍 Step 1: Identifying analysis goal")
        goal_result = self._identify_analysis_goal(question, dataframe_description)
        goal = goal_result.get("goal", "Analysis")
        analysis_type = goal_result.get("analysis_type", "funnel_analysis")
        metrics = goal_result.get("metrics", [])
        dimensions = goal_result.get("dimensions", [])
        segmentation = goal_result.get("segmentation", "")
        print(f"Goal result: {goal_result}")    
        
        # Step 2: Identify funnel steps
        print(f"🔍 Step 2: Identifying funnel steps")
        funnel_steps_result = self._identify_funnel_steps(question, dataframe_info)
        funnel_steps = funnel_steps_result.get("pipeline_steps", {})
        step_names = funnel_steps_result.get("step_names", {})
        event_column = funnel_steps_result.get("event_column", "event")
        user_id_column = funnel_steps_result.get("user_id_column", "user_id")
        timestamp_column = funnel_steps_result.get("timestamp_column", "timestamp")
        
        print(f"Funnel steps result: {funnel_steps_result}")
        # Fallback: If funnel steps detection failed, create  basic steps based on analysis type
        if not funnel_steps:
            print(f"⚠️  Fallback: Creating pipeline steps for '{analysis_type}'")
            funnel_steps = self._create_fallback_pipeline_steps(analysis_type)
        if not step_names:
            print(f"⚠️  Fallback: Creating step names for '{analysis_type}'")
            step_names = self._create_fallback_step_names(analysis_type)
        
        # Step 3: Plan the pipeline operations
        print(f"🔍 Step 3: Planning pipeline operations for '{analysis_type}'")
        
        
        plan_result = self._plan_pipeline_steps(
            query=question,
            goal=goal_result,
            funnel_steps=funnel_steps_result
        )

        initial_steps = plan_result.get("steps", [])
        print(f"📊 Initial steps generated: {len(initial_steps)}")
        
        # Step 4: Validate and correct the plan
        print(f"🔍 Step 4: Validating and correcting plan")
        corrected_result = self._validate_and_correct_plan(
            plan={"steps": initial_steps},
            query=question
        )
        corrected_steps = corrected_result.get("steps", [])
        corrections = corrected_result.get("corrections", [])
        print(f"📊 Corrected steps: {len(corrected_steps)}, Corrections: {len(corrections)}")
        
        # Step 5: Generate code for each step
        print(f"🔍 Step 5: Generating code for {len(corrected_steps)} steps")
        steps_with_code = []
        
        # Check if we need to force the correct operation type
        if corrected_steps and analysis_type == "variance_analysis":
            # Force variance_analysis operation if planning generated wrong type
            for step in corrected_steps:
                if step.get("operation", "") != "variance_analysis":
                    print(f"  🔧 Forcing operation type from '{step.get('operation', '')}' to 'variance_analysis'")
                    step["operation"] = "variance_analysis"
        
        for i, step in enumerate(corrected_steps):
            step_query = step.get("natural_language_query", "")
            operation = step.get("operation", "funnel_analysis")  # Default to funnel_analysis
            
            print(f"  📝 Step {i+1}: {operation} - {step_query[:50]}...")
            
            if step_query:
                code_result = self._generate_step_code(operation, step_query)
                step["generated_code"] = code_result.get("code", "")
                step["function_type"] = code_result.get("function_type", "")
                step["function_inputs"] = code_result.get("function_inputs", {})
                step["pipeline_operator"] = code_result.get("pipeline_operator", operation)
                
                if code_result.get("status") == "error":
                    print(f"    ❌ Code generation failed: {code_result.get('message', 'Unknown error')}")
                elif not step["generated_code"]:
                    print(f"    ⚠️  Empty generated code")
                else:
                    print(f"    ✅ Code generated successfully")
            else:
                print(f"    ⚠️  No natural language query for step")
            steps_with_code.append(step)
        
        # Fallback: If no steps were generated, create a basic step based on analysis type
        if not steps_with_code:
            print(f"⚠️  Fallback: Creating fallback step for '{analysis_type}'")
            fallback_step = self._create_fallback_step(question, analysis_type, funnel_steps)
            if fallback_step:
                steps_with_code = [fallback_step]
        
        # Step 6: Assemble the complete pipeline
        print(f"🔍 Step 6: Assembling pipeline with {len(steps_with_code)} steps")
        pipeline_result = self._assemble_pipeline(steps_with_code)
        pipeline_code = pipeline_result.get("pipeline_code", "")
        
        if pipeline_result.get("status") == "error":
            print(f"❌ Pipeline assembly failed: {pipeline_result.get('message', 'Unknown error')}")
        elif not pipeline_code or pipeline_code == "# Error assembling pipeline":
            print(f"⚠️  Pipeline assembly returned error or empty code")
        else:
            print(f"✅ Pipeline assembled successfully")
        
        # Fallback: If pipeline assembly failed, create a basic pipeline
        if not pipeline_code or pipeline_code == "# Error assembling pipeline":
            print(f"⚠️  Fallback: Creating fallback pipeline for '{analysis_type}'")
            pipeline_code = self._create_fallback_pipeline(analysis_type, question)
        
        # Check execution time
        execution_time = time.time() - start_time
        if execution_time > max_execution_time:
            print(f"⚠️  Execution time exceeded {max_execution_time}s: {execution_time:.2f}s")
        
        print(f"🎯 Planning completed in {execution_time:.2f}s")
        
        # Return the complete result
        return {
            "question": question,
            "goal": goal,
            "analysis_type": analysis_type,
            "metrics": metrics,
            "dimensions": dimensions,
            "segmentation": segmentation,
            "funnel_steps": funnel_steps,
            "step_names": step_names,
            "event_column": event_column,
            "user_id_column": user_id_column,
            "timestamp_column": timestamp_column,
            "initial_plan": initial_steps,
            "corrected_plan": corrected_steps,
            "corrections": corrections,
            "pipeline_code": pipeline_code,
            "execution_time": execution_time
        }
    
    def _format_dataframe_info(self, dataframe_columns: List[str] = None, dataframe_description: Dict[str, Any] = None) -> str:
        """
        Format dataframe information as a string
        
        Args:
            dataframe_columns: List of column names in the dataset
            dataframe_description: Dictionary with schema information
            
        Returns:
            Formatted dataframe information string
        """
        info_parts = []
        
        # Add columns information
        if dataframe_columns:
            info_parts.append(f"Columns: {', '.join(dataframe_columns)}")
        
        # Add schema information if available
        if dataframe_description and "schema" in dataframe_description:
            schema = dataframe_description["schema"]
            schema_parts = []
            for col, dtype in schema.items():
                schema_parts.append(f"{col} ({dtype})")
            
            if schema_parts:
                info_parts.append(f"Schema: {', '.join(schema_parts)}")
        
        # Add summary if available
        if dataframe_description and "summary" in dataframe_description:
            info_parts.append(f"Summary: {dataframe_description['summary']}")
        
        # Combine all parts
        return "\n".join(info_parts)
    
    def _create_fallback_step(self, question: str, analysis_type: str, funnel_steps: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a fallback step when the planning process fails
        
        Args:
            question: The user's question
            analysis_type: The detected analysis type
            funnel_steps: The identified pipeline steps
            
        Returns:
            Dictionary with a basic step configuration
        """
        # Determine the appropriate operation based on analysis type
        operation_mapping = {
            "variance_analysis": "variance_analysis",
            "funnel_analysis": "analyze_funnel",
            "cohort_analysis": "analyze_cohort",
            "trend_analysis": "analyze_trends",
            "segmentation": "analyze_segmentation",
            "time_series_analysis": "analyze_time_series",
            "risk_analysis": "analyze_risk",
            "metric_analysis": "analyze_metrics",
            "operation_analysis": "analyze_operations"
        }
        
        operation = operation_mapping.get(analysis_type, "analyze_funnel")
        
        # Create a basic step
        fallback_step = {
            "step_number": 1,
            "operation": operation,
            "description": f"Basic {analysis_type} step for the given question",
            "natural_language_query": question,
            "inputs": {},
            "generated_code": "",
            "function_type": operation,
            "function_inputs": {},
            "pipeline_operator": analysis_type
        }
        
        return fallback_step
    
    def _create_fallback_pipeline(self, analysis_type: str, question: str) -> str:
        """
        Create a fallback pipeline when assembly fails
        
        Args:
            analysis_type: The detected analysis type
            question: The user's question
            
        Returns:
            String with basic pipeline code
        """
        # Create basic pipeline code based on analysis type
        if analysis_type == "variance_analysis":
            return """# Basic variance analysis pipeline
result = (
    VariancePipe.from_dataframe(df)
    | variance_analysis(
        columns=df.columns.tolist(),
        window=5,
        group_columns=['group_column'],
        time_column='date_column'
    )
)"""
        elif analysis_type == "cohort_analysis":
            return """# Basic cohort analysis pipeline
result = (
    CohortPipe.from_dataframe(df)
    | analyze_cohort(
        event_column='event',
        user_id_column='user_id',
        time_column='timestamp'
    )
)"""
        elif analysis_type == "trend_analysis":
            return """# Basic trend analysis pipeline
result = (
    TrendPipe.from_dataframe(df)
    | analyze_trends(
        time_column='date',
        value_column='value',
        group_columns=['group']
    )
)"""
        else:
            return """# Basic funnel analysis pipeline
result = (
    FunnelPipe.from_dataframe(df)
    | analyze_funnel(
        event_column='event',
        user_id_column='user_id',
        funnel_steps=['step1', 'step2', 'step3']
    )
)"""
    
    def _detect_analysis_type_from_question(self, question: str) -> str:
        """
        Detect analysis type from question keywords as a fallback
        
        Args:
            question: The user's question
            
        Returns:
            Detected analysis type
        """
        question_lower = question.lower()
        
        # Check for variance analysis keywords
        if any(word in question_lower for word in ["variance", "volatility", "statistical", "rolling", "standard deviation"]):
            return "variance_analysis"
        
        # Check for cohort analysis keywords
        if any(word in question_lower for word in ["cohort", "retention", "time period", "group by time"]):
            return "cohort_analysis"
        
        # Check for trend analysis keywords
        if any(word in question_lower for word in ["trend", "pattern", "over time", "temporal"]):
            return "trend_analysis"
        
        # Check for segmentation keywords
        if any(word in question_lower for word in ["segment", "cluster", "group", "categorize"]):
            return "segmentation"
        
        # Check for time series keywords
        if any(word in question_lower for word in ["time series", "forecast", "prediction", "seasonal"]):
            return "time_series_analysis"
        
        # Check for risk analysis keywords
        if any(word in question_lower for word in ["risk", "anomaly", "outlier", "detection"]):
            return "risk_analysis"
        
        # Check for metric analysis keywords
        if any(word in question_lower for word in ["metric", "kpi", "performance", "measure"]):
            return "metric_analysis"
        
        # Check for funnel analysis keywords
        if any(word in question_lower for word in ["funnel", "conversion", "journey", "flow"]):
            return "funnel_analysis"
        
        # Default to funnel analysis if no clear match
        return "funnel_analysis"
    
    def _create_timeout_fallback_result(self, question: str, analysis_type: str, start_time: float) -> Dict[str, Any]:
        """
        Create a fallback result when timeout is reached
        
        Args:
            question: The user's question
            analysis_type: The detected analysis type
            start_time: Start time for execution timing
            
        Returns:
            Dictionary with timeout fallback result
        """
        execution_time = time.time() - start_time
        print(f"⏰ Creating timeout fallback result after {execution_time:.2f}s")
        
        # Create basic fallback data
        fallback_steps = self._create_fallback_pipeline_steps(analysis_type)
        fallback_step_names = self._create_fallback_step_names(analysis_type)
        fallback_pipeline = self._create_fallback_pipeline(analysis_type, question)
        
        return {
            "question": question,
            "goal": f"{analysis_type.replace('_', ' ').title()} Analysis",
            "analysis_type": analysis_type,
            "metrics": [],
            "dimensions": [],
            "segmentation": "",
            "funnel_steps": fallback_steps,
            "step_names": fallback_step_names,
            "event_column": "event",
            "user_id_column": "user_id",
            "timestamp_column": "timestamp",
            "initial_plan": [],
            "corrected_plan": [],
            "corrections": [],
            "pipeline_code": fallback_pipeline,
            "execution_time": execution_time,
            "timeout_reached": True
        }
    
    def _create_fallback_pipeline_steps(self, analysis_type: str) -> Dict[str, Any]:
        """
        Create fallback pipeline steps based on analysis type
        
        Args:
            analysis_type: The detected analysis type
            
        Returns:
            Dictionary with basic pipeline steps
        """
        if analysis_type == "variance_analysis":
            return {
                "variance_analysis": ["calculate_variance", "group_by_dimensions", "apply_rolling_window"]
            }
        elif analysis_type == "cohort_analysis":
            return {
                "cohort_analysis": ["form_cohorts", "calculate_retention", "analyze_patterns"]
            }
        elif analysis_type == "trend_analysis":
            return {
                "trend_analysis": ["identify_trends", "calculate_patterns", "analyze_changes"]
            }
        elif analysis_type == "segmentation":
            return {
                "segmentation": ["identify_segments", "analyze_characteristics", "compare_groups"]
            }
        else:
            return {
                "funnel_analysis": ["page_view", "product_view", "add_to_cart", "checkout", "purchase"]
            }
    
    def _create_fallback_step_names(self, analysis_type: str) -> Dict[str, Any]:
        """
        Create fallback step names based on analysis type
        
        Args:
            analysis_type: The detected analysis type
            
        Returns:
            Dictionary with basic step names
        """
        if analysis_type == "variance_analysis":
            return {
                "Step 1": {"columns": ["variance_calculation: statistical"]},
                "Step 2": {"columns": ["grouping: dimensions"]},
                "Step 3": {"columns": ["rolling_window: time_series"]}
            }
        elif analysis_type == "cohort_analysis":
            return {
                "Step 1": {"columns": ["cohort_formation: grouping"]},
                "Step 2": {"columns": ["retention_calculation: metrics"]},
                "Step 3": {"columns": ["pattern_analysis: trends"]}
            }
        elif analysis_type == "trend_analysis":
            return {
                "Step 1": {"columns": ["trend_identification: patterns"]},
                "Step 2": {"columns": ["pattern_calculation: metrics"]},
                "Step 3": {"columns": ["change_analysis: comparisons"]}
            }
        elif analysis_type == "segmentation":
            return {
                "Step 1": {"columns": ["segment_identification: clustering"]},
                "Step 2": {"columns": ["characteristic_analysis: features"]},
                "Step 3": {"columns": ["group_comparison: metrics"]}
            }
        else:
            return {
                "Step 1": {"columns": ["page_view: count"]},
                "Step 2": {"columns": ["product_view: count"]},
                "Step 3": {"columns": ["add_to_cart: count"]},
                "Step 4": {"columns": ["checkout: count"]},
                "Step 5": {"columns": ["purchase: count"]}
            }

# Example usage
if __name__ == "__main__":
    # This would be replaced with your actual implementation
    class MockLLM:
        def __call__(self, prompt):
            return "Mock LLM response"
    
    class MockFunnelAnalysisAgent:
        def run(self, query, dataframe_columns=None, dataframe_description=None):
            return {
                "generated_code": "mock_function(param='value')",
                "function_type": "mock_function",
                "function_inputs": {"param": "value"}
            }
    
    # Initialize components
    llm = MockLLM()
    funnel_analysis_agent = MockFunnelAnalysisAgent()
    
    # Create the planner
    planner = SelfCorrectingForwardPlanner(llm, funnel_analysis_agent)
    
    # Example usage
    result = planner.plan(
        question="How do users from different acquisition sources progress through the conversion funnel?",
        dataframe_columns=["user_id", "event", "timestamp", "acquisition_source"],
        dataframe_description={"schema": {"user_id": "string", "event": "string"}}
    )
    
    # In a real implementation, you would process the result
    print(result)