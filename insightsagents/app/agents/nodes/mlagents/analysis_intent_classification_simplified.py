"""
Simplified Analysis Intent Classification

This is a simplified version that focuses on:
1. Step 1: Generate simple reasoning plan without complex function retrieval
2. Step 2: Look up specific functions for each step
3. Step 3: Create detailed pipeline plan

The key insight is to separate concerns:
- Step 1: High-level reasoning plan
- Step 2: Function lookup and selection
- Step 3: Detailed pipeline planning
"""

import json
import logging
from typing import Dict, List, Any, Optional
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser

logger = logging.getLogger(__name__)

def extract_json_from_response(response_text: str) -> dict:
    """
    Extract JSON from response text, handling various formats including markdown code blocks.
    
    Args:
        response_text: The response text that may contain JSON
        
    Returns:
        dict: Parsed JSON object or None if extraction fails
    """
    import re
    import json
    
    # Try direct JSON parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Clean up the response text
    cleaned_text = response_text.strip()
    
    # Try multiple JSON extraction patterns
    json_patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',  # JSON in json code block
        r'```\s*(\{[\s\S]*?\})\s*```',  # JSON in generic code block
        r'\{[\s\S]*?\}',  # More flexible JSON matching (non-greedy)
        r'\{.*\}',  # Basic JSON object (greedy)
    ]
    
    for pattern in json_patterns:
        json_match = re.search(pattern, cleaned_text, re.DOTALL)
        if json_match:
            try:
                json_text = json_match.group(1) if json_match.groups() else json_match.group()
                # Clean up the extracted JSON text
                json_text = json_text.strip()
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON with pattern {pattern}: {e}")
                continue
    
    # If no pattern matches, try to find the first complete JSON object
    try:
        # Find the first { and try to parse from there
        start_idx = cleaned_text.find('{')
        if start_idx != -1:
            # Try to find the matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i, char in enumerate(cleaned_text[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            if brace_count == 0:  # Found matching braces
                json_text = cleaned_text[start_idx:end_idx]
                return json.loads(json_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Failed to extract JSON using brace matching: {e}")
    
    return None

class SimplifiedAnalysisIntentPlanner:
    """
    Simplified analysis intent planner that focuses on clean separation of concerns.
    """
    
    def __init__(self, llm, retrieval_helper=None):
        self.llm = llm
        self.retrieval_helper = retrieval_helper
    
    async def _step1_question_analysis(
        self,
        question: str,
        dataframe_description: str = "",
        dataframe_summary: str = "",
        available_columns: List[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        STEP 1: Simple question analysis and reasoning plan generation.
        Focus on creating a clean reasoning plan without complex function retrieval.

        Args:
            question: The user's question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID for context

        Returns:
            Dictionary with rephrased question, intent classification, and reasoning plan
        """
        try:
            logger.info("Step 1: Generating simple reasoning plan without function retrieval")
            
            # Create a simple prompt for Step 1 that focuses on reasoning plan generation
            step1_prompt = PromptTemplate(
                input_variables=["question", "dataframe_description", "dataframe_summary", "available_columns"],
                template="""
You are an expert data analyst performing STEP 1 of a multi-step analysis process.

### TASK ###
Analyze the user's question and create a high-level reasoning plan for data analysis.

### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}
**Available Columns:** {available_columns}

### STEP 1 REQUIREMENTS ###
1. **Rephrase the question** to be more specific and actionable
2. **Classify the intent** into one of these categories:
   - time_series_analysis: Analyze data patterns over time periods
   - trend_analysis: Analyze trends, growth patterns, forecasting
   - segmentation_analysis: Group users/data into meaningful segments
   - cohort_analysis: Analyze user behavior and retention over time
   - funnel_analysis: Analyze user conversion funnels and drop-off points
   - risk_analysis: Analyze financial risk metrics and volatility
   - anomaly_detection: Identify outliers and unusual patterns
   - metrics_calculation: Calculate basic statistics and aggregations
   - operations_analysis: Perform statistical tests and operations
3. **Generate a reasoning plan** with 2-5 high-level steps that break down the analysis
4. **For each step, specify the function name and pipeline type** that should be used
5. **Identify required data columns** needed for the analysis
6. **Assess feasibility** and provide confidence score

### IMPORTANT CONSTRAINTS ###
- **DO NOT include data preparation steps** - assume data is already clean and prepared by a separate agent
- **DO NOT include visualization steps** - assume visualization is handled by other specialized agents
- **DO NOT include summary/statistical summary steps** - assume summary generation is handled by other specialized agents
- **DO NOT include reporting or presentation steps** - assume reporting is handled by other specialized agents
- **Focus only on analytical computation steps** - calculations, aggregations, transformations, statistical analysis
- **Start directly with the core analysis logic** - no data cleaning, validation, visualization, or summary steps

### FUNCTION SELECTION GUIDANCE ###
When selecting functions for each step, consider these common analytical functions:
- **MovingAggrPipe**: moving_variance, moving_average, moving_sum, rolling_window
- **TimeSeriesPipe**: variance_analysis, rolling_window, lead, lag
- **MetricsPipe**: Variance, Mean, Sum, Count, GroupBy, RollingMetric
- **TrendPipe**: calculate_statistical_trend, calculate_growth_rates, aggregate_by_time
- **RiskPipe**: calculate_var, calculate_cvar, rolling_risk_metrics
- **CohortPipe**: calculate_retention, calculate_conversion, calculate_lifetime_value
- **SegmentPipe**: run_kmeans, run_dbscan, run_hierarchical, get_features
- **AnomalyPipe**: detect_statistical_outliers, detect_contextual_anomalies

### REASONING PLAN FORMAT ###
Each step should include:
- A natural language description of what needs to be done
- The specific function name that should be used
- The pipeline type for the function
- Data requirements for the step

Example reasoning plan for "How does the 5-day rolling variance of flux change over time for each group?":
[
    {{
        "step_number": 1,
        "step_title": "Rolling Variance Calculation", 
        "step_description": "Calculate rolling variance with appropriate window size for each group",
        "function_name": "moving_variance",
        "pipeline_type": "MovingAggrPipe",
        "data_requirements": ["date_column", "value_column", "group_columns", "window_size"]
    }},
    {{
        "step_number": 2,
        "step_title": "Group-wise Analysis",
        "step_description": "Analyze variance patterns across different groups over time",
        "function_name": "variance_analysis",
        "pipeline_type": "TimeSeriesPipe",
        "data_requirements": ["group_columns", "rolling_variance_results", "date_column"]
    }}
]

**IMPORTANT: Do NOT include summary, visualization, or reporting steps like:**
- "Statistical Summary" 
- "Generate Report"
- "Create Visualization"
- "Summary Statistics"
- "Final Summary"
- "Data Summary"
- "Results Summary"

### OUTPUT FORMAT ###
**CRITICAL: Provide your response as a VALID JSON object ONLY. Do NOT wrap it in markdown code blocks, do NOT use ```json or ```. Return pure JSON that can be parsed directly.**

Provide your response as a JSON object:
{{
    "rephrased_question": "Rephrased version of the user's question",
    "intent_type": "one of the analysis types above",
    "confidence_score": 0.0-1.0,
    "reasoning": "Brief explanation of your analysis approach",
    "required_data_columns": ["column1", "column2", "column3"],
    "clarification_needed": "Any questions or clarifications needed",
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["column1", "column2"] if any columns are missing,
    "available_alternatives": ["alternative1", "alternative2"] if any,
    "data_suggestions": "Suggestions for data preparation or collection",
    "reasoning_plan": [array of reasoning plan steps as shown above]
}}

### JSON FORMATTING REQUIREMENTS ###
- Return ONLY valid JSON, no markdown formatting
- Do NOT use ```json or ``` code blocks
- Do NOT include any text before or after the JSON
- Start your response with {{ and end with }}
- Ensure proper JSON syntax with correct quotes and commas
"""
            )
            
            # Generate the response
            step1_chain = step1_prompt | self.llm | StrOutputParser()
            step1_result = await step1_chain.ainvoke({
                "question": question,
                "dataframe_description": dataframe_description,
                "dataframe_summary": dataframe_summary,
                "available_columns": available_columns
            })
            
            # Parse the response
            step1_data = extract_json_from_response(step1_result)
            
            if not step1_data:
                logger.error(f"Failed to parse Step 1 response as JSON: {step1_result}")
                return {
                    "rephrased_question": question,
                    "intent_type": "unsupported_analysis",
                    "confidence_score": 0.0,
                    "reasoning": "Failed to parse analysis response",
                    "required_data_columns": [],
                    "clarification_needed": "System error: Failed to parse response",
                    "can_be_answered": False,
                    "feasibility_score": 0.0,
                    "missing_columns": [],
                    "available_alternatives": [],
                    "data_suggestions": "System error: Failed to parse response",
                    "reasoning_plan": [],
                    "error": "JSON parsing failed"
                }
            
            # Add suggested_functions field for compatibility
            if 'suggested_functions' not in step1_data:
                step1_data['suggested_functions'] = []
            
            logger.info(f"Step 1 completed - Intent: {step1_data.get('intent_type')}, Confidence: {step1_data.get('confidence_score')}")
            logger.info(f"Step 1 reasoning plan steps: {len(step1_data.get('reasoning_plan', []))}")
            
            return step1_data
            
        except Exception as e:
            logger.error(f"Error in Step 1 question analysis: {e}")
            return {
                "rephrased_question": question,
                "intent_type": "unsupported_analysis",
                "confidence_score": 0.0,
                "reasoning": f"Error in question analysis: {str(e)}",
                "required_data_columns": [],
                "clarification_needed": "System error occurred",
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": [],
                "available_alternatives": [],
                "data_suggestions": "System error occurred",
                "reasoning_plan": []
            }
    
    async def _step2_function_lookup(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        available_columns: List[str],
        dataframe_description: str = "",
        dataframe_summary: str = ""
    ) -> Dict[str, Any]:
        """
        STEP 2: Look up specific functions for each step in the reasoning plan.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            question: The original question
            available_columns: List of available columns
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            
        Returns:
            Dictionary with function matches for each step
        """
        try:
            logger.info("Step 2: Looking up specific functions for each reasoning plan step")
            
            if not self.retrieval_helper:
                logger.warning("No retrieval helper available, using fallback function selection")
                return self._get_fallback_function_selection(reasoning_plan)
            
            step_function_matches = {}
            
            for step in reasoning_plan:
                step_number = step.get('step_number', 1)
                step_title = step.get('step_title', '')
                step_description = step.get('step_description', '')
                
                logger.info(f"Looking up functions for Step {step_number}: {step_title}")
                
                # Create a focused query for this specific step
                step_query = f"{step_title} {step_description} {question}"
                
                try:
                    # Get function definitions for this step
                    function_result = await self.retrieval_helper.get_function_definition_by_query(
                        query=step_query,
                        similarity_threshold=0.3,
                        top_k=5
                    )
                    
                    if function_result and function_result.get("function_definitions"):
                        functions = function_result["function_definitions"]
                        step_function_matches[step_number] = functions
                        logger.info(f"Found {len(functions)} functions for Step {step_number}")
                    else:
                        logger.warning(f"No functions found for Step {step_number}")
                        step_function_matches[step_number] = []
                        
                except Exception as e:
                    logger.error(f"Error looking up functions for Step {step_number}: {e}")
                    step_function_matches[step_number] = []
            
            return {
                "step_function_matches": step_function_matches,
                "total_steps": len(reasoning_plan),
                "steps_with_functions": len([s for s in step_function_matches.values() if s])
            }
            
        except Exception as e:
            logger.error(f"Error in Step 2 function lookup: {e}")
            return {
                "step_function_matches": {},
                "total_steps": len(reasoning_plan),
                "steps_with_functions": 0,
                "error": str(e)
            }
    
    def _get_fallback_function_selection(self, reasoning_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get fallback function selection when retrieval helper is not available.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            
        Returns:
            Dictionary with fallback function matches
        """
        step_function_matches = {}
        
        for step in reasoning_plan:
            step_number = step.get('step_number', 1)
            step_title = step.get('step_title', '').lower()
            
            # Simple keyword-based function selection
            functions = []
            
            if any(keyword in step_title for keyword in ['group', 'aggregate', 'sum', 'mean']):
                functions = [
                    {"function_name": "GroupBy", "pipe_name": "MetricsPipe", "description": "Group and aggregate data"},
                    {"function_name": "Sum", "pipe_name": "MetricsPipe", "description": "Calculate sum"},
                    {"function_name": "Mean", "pipe_name": "MetricsPipe", "description": "Calculate mean"}
                ]
            elif any(keyword in step_title for keyword in ['rolling', 'moving', 'window', 'variance']):
                functions = [
                    {"function_name": "moving_variance", "pipe_name": "MovingAggrPipe", "description": "Calculate moving variance"},
                    {"function_name": "rolling_window", "pipe_name": "TimeSeriesPipe", "description": "Apply rolling window operations"}
                ]
            elif any(keyword in step_title for keyword in ['time', 'date', 'trend', 'forecast']):
                functions = [
                    {"function_name": "variance_analysis", "pipe_name": "TimeSeriesPipe", "description": "Analyze variance over time"},
                    {"function_name": "calculate_statistical_trend", "pipe_name": "TrendPipe", "description": "Calculate statistical trends"}
                ]
            
            step_function_matches[step_number] = functions
        
        return {
            "step_function_matches": step_function_matches,
            "total_steps": len(reasoning_plan),
            "steps_with_functions": len([s for s in step_function_matches.values() if s])
        }
    
    async def _step3_detailed_reasoning(
        self,
        reasoning_plan: List[Dict[str, Any]],
        step_function_matches: Dict[int, List[Dict[str, Any]]],
        question: str,
        available_columns: List[str],
        dataframe_description: str = "",
        dataframe_summary: str = ""
    ) -> Dict[str, Any]:
        """
        STEP 3: Create detailed reasoning plan for each individual step.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            step_function_matches: Function matches from Step 2
            question: The original question
            available_columns: List of available columns
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            
        Returns:
            Dictionary with detailed reasoning for each step
        """
        try:
            logger.info("Step 3: Creating detailed reasoning for each step")
            
            # Create prompt for Step 3 detailed reasoning
            step3_prompt = PromptTemplate(
                input_variables=[
                    "question", "reasoning_plan", "step_function_matches", 
                    "available_columns", "dataframe_description", "dataframe_summary"
                ],
                template="""
You are an expert data analyst performing STEP 3 of a multi-step analysis process.

### TASK ###
Create detailed reasoning for each individual step using the functions found in Step 2.

### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}
**Available Columns:** {available_columns}

### REASONING PLAN FROM STEP 1 ###
{reasoning_plan}

### FUNCTION MATCHES FROM STEP 2 ###
{step_function_matches}

### STEP 3 REQUIREMENTS ###
For each step in the reasoning plan, create detailed reasoning that includes:

1. **Select the best function** from the available function matches for that step
2. **Map parameters** to the available columns
3. **Specify pipeline type** based on the function's pipe_name
4. **Add detailed metadata** including input/output columns, etc.

### IMPORTANT CONSTRAINTS ###
- **DO NOT include data preparation functions** - assume data is already clean and prepared
- **DO NOT include visualization functions** - assume visualization is handled by other agents
- **DO NOT include summary/statistical summary functions** - assume summary generation is handled by other agents
- **DO NOT include reporting or presentation functions** - assume reporting is handled by other agents
- **Focus only on analytical computation functions** - calculations, aggregations, transformations, statistical analysis
- **Skip any steps that are purely data cleaning, validation, visualization, or summary generation**

### OUTPUT FORMAT ###
**CRITICAL: Provide your response as a VALID JSON object ONLY. Do NOT wrap it in markdown code blocks, do NOT use ```json or ```. Return pure JSON that can be parsed directly.**

Provide your response as a JSON object with a "detailed_steps" array:

{{
    "detailed_steps": [
        {{
            "step_number": 1,
            "step_title": "Step title from reasoning plan",
            "step_description": "Detailed description of what this step does",
            "function_name": "selected_function_name",
            "pipeline_name": "PipeName",
            "pipeline_type": "PipeName",
            "function_category": "category_from_function",
            "parameter_mapping": {{
                "variable": "column1",
                "unbiased": true
            }},
            "input_columns": ["column1", "column2"],
            "output_columns": ["output1", "output2"],
            "column_mapping": {{
                "variable": "column1",
                "unbiased": true
            }},
            "expected_output": "Description of expected output",
            "data_requirements": ["column1", "column2"],
            "considerations": "Important considerations for this step",
            "available_columns": {{available_columns}},
            "dataframe_description": "{{dataframe_description}}"
        }}
    ]
}}

### CRITICAL INSTRUCTIONS ###
- Use ONLY the exact function names from the step_function_matches
- Map parameters to available columns intelligently
- Set pipeline_type to match the function's pipe_name
- Ensure all required parameters are mapped
- Focus on individual step details, not pipeline organization

### PARAMETER MAPPING GUIDANCE ###
- Use the EXACT parameter names from the function definition (e.g., "variable", "unbiased", "window", "columns")
- Do NOT add prefixes like "-_" to parameter names
- Do NOT use generic names like "param1", "param2"
- Check the function definition for the correct parameter names
- Common parameter names: "variable", "columns", "window", "unbiased", "output_name", "group_columns", "time_column"

### EXAMPLES OF CORRECT PARAMETER MAPPING ###
- Variance function: {{"variable": "column_name", "unbiased": true}}
- moving_variance function: {{"columns": "column_name", "window": 5, "group_columns": ["group1", "group2"]}}
- GroupBy function: {{"columns": ["col1", "col2"], "agg_functions": ["sum", "mean"]}}
- variance_analysis function: {{"columns": "column_name", "method": "rolling", "window": 5}}

### JSON FORMATTING REQUIREMENTS ###
- Return ONLY valid JSON, no markdown formatting
- Do NOT use ```json or ``` code blocks
- Do NOT include any text before or after the JSON
- Start your response with {{ and end with }}
- Ensure proper JSON syntax with correct quotes and commas
"""
            )
            
            # Format the inputs for the prompt
            reasoning_plan_text = json.dumps(reasoning_plan, indent=2)
            step_function_matches_text = json.dumps(step_function_matches, indent=2)
            
            # Generate the response
            step3_chain = step3_prompt | self.llm | StrOutputParser()
            step3_result = await step3_chain.ainvoke({
                "question": question,
                "reasoning_plan": reasoning_plan_text,
                "step_function_matches": step_function_matches_text,
                "available_columns": available_columns,
                "dataframe_description": dataframe_description,
                "dataframe_summary": dataframe_summary
            })
            
            # Parse the response
            step3_data = extract_json_from_response(step3_result)
            
            if not step3_data:
                logger.error(f"Failed to parse Step 3 response as JSON: {step3_result}")
                # Create a fallback response with basic structure
                step3_data = {
                    "detailed_steps": [
                        {
                            "step_number": 1,
                            "step_title": "Analysis Step",
                            "step_description": "Perform the requested analysis",
                            "function_name": "unknown",
                            "parameters": {},
                            "reasoning": "Unable to parse detailed reasoning, using fallback"
                        }
                    ],
                    "error": "JSON parsing failed"
                }
            
            detailed_steps = step3_data.get("detailed_steps", [])
            logger.info(f"Step 3 completed - Generated detailed reasoning for {len(detailed_steps)} steps")
            
            return step3_data
            
        except Exception as e:
            logger.error(f"Error in Step 3 detailed reasoning: {e}")
            return {
                "detailed_steps": [],
                "error": str(e)
            }
    
    async def _step4_pipeline_organization(
        self,
        detailed_steps: List[Dict[str, Any]],
        question: str,
        available_columns: List[str],
        dataframe_description: str = "",
        dataframe_summary: str = ""
    ) -> Dict[str, Any]:
        """
        STEP 4: Organize the pipeline with ordering and dependencies.
        
        Args:
            detailed_steps: Detailed steps from Step 3
            question: The original question
            available_columns: List of available columns
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            
        Returns:
            Dictionary with organized pipeline reasoning plan
        """
        try:
            logger.info("Step 4: Organizing pipeline with ordering and dependencies")
            
            # Create prompt for Step 4 pipeline organization
            step4_prompt = PromptTemplate(
                input_variables=[
                    "question", "detailed_steps", "available_columns", 
                    "dataframe_description", "dataframe_summary"
                ],
                template="""
You are an expert data analyst performing STEP 4 of a multi-step analysis process.

### TASK ###
Organize the detailed steps into a coherent pipeline with proper ordering and dependencies.

### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}
**Available Columns:** {available_columns}

### DETAILED STEPS FROM STEP 3 ###
{detailed_steps}

### STEP 4 REQUIREMENTS ###
Organize the detailed steps into a pipeline by:

1. **Determine execution order** - which steps must run first, which can run in parallel
2. **Identify dependencies** - which steps depend on outputs from other steps
3. **Set data flow** - how data flows between steps
4. **Add pipeline metadata** - overall pipeline characteristics

### IMPORTANT CONSTRAINTS ###
- **Focus only on analytical computation steps** - no data preparation, visualization, or summary steps
- **Ensure all steps are purely analytical** - calculations, aggregations, transformations, statistical analysis
- **Skip any data cleaning, validation, visualization, or summary steps** - these are handled by other agents
- **DO NOT include summary/statistical summary steps** - assume summary generation is handled by other specialized agents
- **DO NOT include reporting or presentation steps** - assume reporting is handled by other specialized agents

### OUTPUT FORMAT ###
**CRITICAL: Provide your response as a VALID JSON object ONLY. Do NOT wrap it in markdown code blocks, do NOT use ```json or ```. Return pure JSON that can be parsed directly.**

Provide your response as a JSON object with a "pipeline_reasoning_plan" array:

{{
    "pipeline_reasoning_plan": [
        {{
            "step_number": 1,
            "step_title": "Step title",
            "step_description": "Detailed description",
            "function_name": "function_name",
            "pipeline_name": "PipeName",
            "pipeline_type": "PipeName",
            "function_category": "category",
            "parameter_mapping": {{}},
            "input_columns": [],
            "output_columns": [],
            "column_mapping": {{}},
            "expected_output": "Description",
            "data_requirements": [],
            "considerations": "Considerations",
            "merge_with_previous": false,
            "embedded_function_parameter": false,
            "embedded_function_details": null,
            "step_dependencies": [],
            "data_flow": "Description of data flow",
            "embedded_function_columns": null,
            "parameter_constraints": {{}},
            "error_handling": "Standard error handling",
            "available_columns": {{available_columns}},
            "dataframe_description": "{{dataframe_description}}",
            "execution_order": 1,
            "can_parallelize": false,
            "depends_on_steps": [],
            "enables_steps": []
        }}
    ],
    "pipeline_metadata": {{
        "total_steps": 3,
        "execution_order": [1, 2, 3],
        "parallel_opportunities": [],
        "critical_path": [1, 2, 3],
        "estimated_complexity": "medium",
        "data_flow_summary": "Sequential processing with rolling calculations"
    }}
}}

### CRITICAL INSTRUCTIONS ###
- Analyze the data flow between steps
- Identify which steps can run in parallel
- Set proper dependencies and execution order
- Ensure the pipeline is logically sound and executable
- Add pipeline-level metadata for optimization

### JSON FORMATTING REQUIREMENTS ###
- Return ONLY valid JSON, no markdown formatting
- Do NOT use ```json or ``` code blocks
- Do NOT include any text before or after the JSON
- Start your response with {{ and end with }}
- Ensure proper JSON syntax with correct quotes and commas
"""
            )
            
            # Format the inputs for the prompt
            detailed_steps_text = json.dumps(detailed_steps, indent=2)
            
            # Generate the response
            step4_chain = step4_prompt | self.llm | StrOutputParser()
            step4_result = await step4_chain.ainvoke({
                "question": question,
                "detailed_steps": detailed_steps_text,
                "available_columns": available_columns,
                "dataframe_description": dataframe_description,
                "dataframe_summary": dataframe_summary
            })
            
            # Parse the response
            step4_data = extract_json_from_response(step4_result)
            
            if not step4_data:
                logger.error(f"Failed to parse Step 4 response as JSON: {step4_result}")
                return {
                    "pipeline_reasoning_plan": [],
                    "pipeline_metadata": {},
                    "error": "JSON parsing failed"
                }
            
            pipeline_plan = step4_data.get("pipeline_reasoning_plan", [])
            pipeline_metadata = step4_data.get("pipeline_metadata", {})
            logger.info(f"Step 4 completed - Organized {len(pipeline_plan)} steps with metadata")
            
            return step4_data
            
        except Exception as e:
            logger.error(f"Error in Step 4 pipeline organization: {e}")
            return {
                "pipeline_reasoning_plan": [],
                "pipeline_metadata": {},
                "error": str(e)
            }
    
    async def classify_intent(
        self,
        question: str,
        dataframe_description: str = "",
        dataframe_summary: str = "",
        available_columns: List[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main method that orchestrates the 4-step analysis process.
        
        Args:
            question: The user's question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID for context
            
        Returns:
            Complete analysis result with reasoning plan and pipeline plan
        """
        try:
            logger.info("Starting simplified 4-step analysis process")
            
            # Step 1: Generate reasoning plan
            step1_result = await self._step1_question_analysis(
                question=question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns or [],
                project_id=project_id
            )
            
            if not step1_result.get("can_be_answered", False):
                logger.warning("Step 1 determined question cannot be answered")
                return step1_result
            
            reasoning_plan = step1_result.get("reasoning_plan", [])
            if not reasoning_plan:
                logger.warning("No reasoning plan generated in Step 1")
                return step1_result
            
            # Step 2: Look up functions for each step
            step2_result = await self._step2_function_lookup(
                reasoning_plan=reasoning_plan,
                question=question,
                available_columns=available_columns or [],
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary
            )
            
            step_function_matches = step2_result.get("step_function_matches", {})
            if not step_function_matches:
                logger.warning("No function matches found in Step 2")
                return step1_result
            
            # Step 3: Create detailed reasoning for each step
            step3_result = await self._step3_detailed_reasoning(
                reasoning_plan=reasoning_plan,
                step_function_matches=step_function_matches,
                question=question,
                available_columns=available_columns or [],
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary
            )
            
            detailed_steps = step3_result.get("detailed_steps", [])
            if not detailed_steps:
                logger.warning("No detailed steps generated in Step 3")
                return step1_result
            
            # Step 4: Organize pipeline with ordering and dependencies
            step4_result = await self._step4_pipeline_organization(
                detailed_steps=detailed_steps,
                question=question,
                available_columns=available_columns or [],
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary
            )
            
            # Extract suggested functions from pipeline reasoning plan
            suggested_functions = []
            pipeline_plan = step4_result.get("pipeline_reasoning_plan", [])
            logger.info(f"Pipeline plan has {len(pipeline_plan)} steps")
            
            for step in pipeline_plan:
                if step.get('function_name'):
                    pipe_name = step.get('pipeline_name', 'Unknown')
                    function_name = step['function_name']
                    suggested_functions.append(f"{function_name}: {step.get('function_category', 'unknown_operation')} ({pipe_name})")
                    logger.info(f"Added function: {function_name} from pipeline plan")
            
            # If no functions found in pipeline plan, try to extract from step function matches
            if not suggested_functions:
                logger.warning("No functions found in pipeline plan, trying step function matches")
                for step_num, matches in step_function_matches.items():
                    if matches and len(matches) > 0:
                        for match in matches:
                            if isinstance(match, dict) and match.get('function_name'):
                                function_name = match['function_name']
                                pipe_name = match.get('pipeline_name', 'Unknown')
                                suggested_functions.append(f"{function_name}: {match.get('function_category', 'unknown_operation')} ({pipe_name})")
                                logger.info(f"Added function from step matches: {function_name}")
            
            # If still no functions, try to extract from detailed steps
            if not suggested_functions:
                logger.warning("No functions found in step matches, trying detailed steps")
                for step in detailed_steps:
                    if step.get('function_name') and step['function_name'] != 'unknown':
                        function_name = step['function_name']
                        pipe_name = step.get('pipeline_name', 'Unknown')
                        suggested_functions.append(f"{function_name}: {step.get('function_category', 'unknown_operation')} ({pipe_name})")
                        logger.info(f"Added function from detailed steps: {function_name}")
            
            logger.info(f"Final suggested_functions: {suggested_functions}")
            
            # Combine all results
            final_result = {
                **step1_result,  # Include Step 1 results
                "step2_result": step2_result,  # Include Step 2 results
                "step3_result": step3_result,  # Include Step 3 results
                "step4_result": step4_result,  # Include Step 4 results
                "pipeline_reasoning_plan": pipeline_plan,
                "pipeline_metadata": step4_result.get("pipeline_metadata", {}),
                "suggested_functions": suggested_functions,  # Add suggested functions
                "total_steps": len(reasoning_plan),
                "steps_with_functions": step2_result.get("steps_with_functions", 0),
                "detailed_steps_count": len(detailed_steps)
            }
            
            logger.info(f"Simplified 4-step analysis completed - {len(reasoning_plan)} reasoning steps, {step2_result.get('steps_with_functions', 0)} with functions, {len(detailed_steps)} detailed steps")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in simplified 4-step analysis process: {e}")
            return {
                "rephrased_question": question,
                "intent_type": "unsupported_analysis",
                "confidence_score": 0.0,
                "reasoning": f"Error in analysis process: {str(e)}",
                "required_data_columns": [],
                "clarification_needed": "System error occurred",
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": [],
                "available_alternatives": [],
                "data_suggestions": "System error occurred",
                "reasoning_plan": [],
                "pipeline_reasoning_plan": [],
                "pipeline_metadata": {},
                "error": str(e)
            }
