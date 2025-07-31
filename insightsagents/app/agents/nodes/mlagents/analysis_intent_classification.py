import logging
from typing import Any, Dict, List, Literal, Optional

import orjson
from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel
from app.storage.documents import DocumentChromaStore
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper

logger = logging.getLogger("analysis-intent-planner")


class AnalysisIntentResult(BaseModel):
    """Result model for analysis intent classification"""
    intent_type: Literal[
        "time_series_analysis", 
        "trend_analysis", 
        "segmentation_analysis", 
        "cohort_analysis", 
        "funnel_analysis", 
        "risk_analysis", 
        "anomaly_detection",
        "metrics_calculation",
        "operations_analysis",
        "unclear_intent",
        "unsupported_analysis"
    ]
    confidence_score: float
    rephrased_question: str
    suggested_functions: List[str]
    required_data_columns: List[str]
    clarification_needed: Optional[str] = None
    retrieved_functions: List[Dict[str, Any]] = []
    specific_function_matches: List[str] = []  # Track exact keyword matches
    
    # Data feasibility assessment
    can_be_answered: bool
    feasibility_score: float  # 0.0 to 1.0
    missing_columns: List[str] = []
    available_alternatives: List[str] = []
    data_suggestions: Optional[str] = None
    
    # Step-by-step reasoning plan
    reasoning_plan: Optional[List[Dict[str, Any]]] = None   # List of reasoning steps
    
    def dict(self, *args, **kwargs):
        """Convert the model to a dictionary for JSON serialization"""
        return super().dict(*args, **kwargs)
    
    def json(self, *args, **kwargs):
        """Convert the model to JSON string"""
        return super().json(*args, **kwargs)




# System prompt for intent classification
ANALYSIS_INTENT_SYSTEM_PROMPT = """
### TASK ###
You are an expert data analyst who specializes in intent classification for data analysis tasks.
Your goal is to analyze user questions and classify them into appropriate analysis types based on available analysis functions AND available data.

First, rephrase the user's question to make it more specific and clear.
Second, classify the user's intent into one of the available analysis types.
Third, suggest the most relevant functions and required data columns.
Fourth, assess whether the question can be answered with the available data.
Fifth, create a detailed step-by-step reasoning plan for the analysis.

### CRITICAL INSTRUCTIONS ###
- PRIORITIZE EXACT FUNCTION MATCHES: If the user mentions specific analysis terms (like "variance", "rolling variance", "correlation", etc.), classify accordingly
- When you see 🎯 marked functions, these are EXACT keyword matches - give them highest priority
- CONSIDER HISTORICAL CONTEXT: Pay attention to relevant historical questions and their solutions, as they provide valuable insights into similar analysis patterns and approaches
- CHECK DATA FEASIBILITY: Analyze available columns, data description, and summary to determine if analysis is possible
- Rephrase the question to be more specific and actionable
- Classify intent based on the MOST SPECIFIC analysis type that matches the question
- Provide clear reasoning for your classification (within 30 words)
- Suggest 2-3 most relevant functions from the retrieved options
- Identify required data columns based on function specifications
- Assess feasibility: can_be_answered (true/false) and feasibility_score (0.0-1.0)
- If columns are missing, suggest alternatives from available data
- If intent is unclear, provide helpful clarification questions
- CREATE DETAILED REASONING PLAN: Provide a step-by-step plan that considers data preparation, analysis approach, and expected outcomes
- For the reasoning plan, assume the data is clean and ready to be used for analysis. 
- Data preparation steps included should only be used for the purposes of transforming data to be used for analysis.

### DATA FEASIBILITY ASSESSMENT ###
- can_be_answered: true if all required columns exist or suitable alternatives are available
- feasibility_score: 1.0 = perfect match, 0.8+ = good alternatives exist, 0.5+ = partial match, <0.5 = major limitations
- missing_columns: list columns that are required but not available
- available_alternatives: suggest similar columns that could work
- data_suggestions: provide advice on data preparation or alternative approaches

### REASONING PLAN REQUIREMENTS ###
The reasoning_plan should be a list of steps, where each step contains:
- step_number: Sequential number (1, 2, 3, etc.)
- step_title: Brief title describing the step
- step_description: Detailed description of what this step involves
- data_requirements: What data/columns are needed for this step
- expected_outcome: What result or insight this step should produce
- considerations: Any important considerations or potential issues

### ANALYSIS TYPES ###
- time_series_analysis: Analyze data patterns over time periods (lead, lag, variance_analysis with rolling windows, distribution analysis)
- trend_analysis: Analyze trends, growth patterns, forecasting (growth rates, moving averages, decomposition)
- segmentation_analysis: Group users/data into meaningful segments (clustering, rule-based)
- cohort_analysis: Analyze user behavior and retention over time (retention, lifetime value)
- funnel_analysis: Analyze user conversion funnels and paths (conversion rates, user journeys)
- risk_analysis: Perform risk analysis and portfolio assessment (VaR, Monte Carlo)
- anomaly_detection: Detect outliers and anomalies in data (statistical outliers, contextual anomalies, collective anomalies, change points)
- metrics_calculation: Calculate statistical metrics and aggregations (sum, mean, correlation)
- operations_analysis: Statistical operations and experimental analysis (A/B tests, confidence intervals)
- unclear_intent: Question is too vague or ambiguous
- unsupported_analysis: Requested analysis is not supported by available functions

### OUTPUT FORMAT ###
Provide your response as a JSON object:

{
    "intent_type": "analysis_type",
    "confidence_score": 0.0-1.0,
    "rephrased_question": "clear and specific question",
    "suggested_functions": ["function1: operation category", "function2: operation category", "function3: operation category"],
    "function_categories": ["Use the Category from function definition", "Use the Category from function definition", "Use the Category from function definition"],
    "function_type_of_operations": ["Use the Type of Operation from function definition", "Use the Type of Operation from function definition", "Use the Type of Operation from function definition"],
    "reasoning": "brief explanation emphasizing specific function matches and data availability",
    "required_data_columns": ["column1", "column2"],
    "clarification_needed": "question if intent unclear or null",
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["missing_col1", "missing_col2"],
    "available_alternatives": ["alt_col1", "alt_col2"],
    "data_suggestions": "advice on data prep or alternatives or null",
    "reasoning_plan": [
        {
            "step_number": 1,
            "step_title": "Data Preparation",
            "step_description": "Clean and prepare the data for analysis",
            "data_requirements": ["timestamp", "flux"],
            "expected_outcome": "Clean dataset ready for analysis",
            "considerations": "Ensure timestamp is in datetime format"
        },
        {
            "step_number": 2,
            "step_title": "Rolling Variance Calculation",
            "step_description": "Calculate 5-day rolling variance for flux metric",
            "data_requirements": ["flux", "timestamp"],
            "expected_outcome": "Rolling variance values over time",
            "considerations": "Handle missing values appropriately"
        }
    ]
}
"""

# User prompt template
ANALYSIS_INTENT_USER_PROMPT = """
### USER QUESTION ###
{question}

### AVAILABLE DATAFRAME ###
**Description:** {dataframe_description}

**Summary:** {dataframe_summary}

**Available Columns:** {available_columns}

### RETRIEVED FUNCTION DEFINITIONS ###
{function_definitions}

### RETRIEVED FUNCTION EXAMPLES ###
{function_examples}

### RETRIEVED FUNCTION INSIGHTS ###
{function_insights}

{historical_context}

### ANALYSIS INSTRUCTION ###
Based on the user question, available dataframe information, retrieved function information, and any relevant historical context:
1. Classify the analysis intent 
2. Assess whether the question can be answered with the available data
3. Suggest alternative approaches if exact columns don't exist
4. Provide suggestions for data preparation if needed
5. Consider how similar historical questions were approached and what insights they provide
6. CREATE A DETAILED STEP-BY-STEP REASONING PLAN that includes:
   - Data preparation and cleaning steps
   - Analysis approach and methodology
   - Expected outcomes and insights
   - Potential challenges and considerations
   - How to use the available columns effectively

Consider:
- Do the available columns support the requested analysis?
- Are there similar columns that could work as alternatives?
- What data transformations might be needed?
- Is the dataframe structure suitable for the intended analysis?
- How do similar historical questions inform the analysis approach?
- What patterns emerge from historical analysis approaches?
- What specific steps are needed to transform the raw data into actionable insights?
- How can the analysis be broken down into logical, sequential steps?


Current Time: {current_time}
"""





class AnalysisIntentPlanner:
    """
    LLM-based natural language to analysis intent planner that uses semantic search
    and LangChain to classify user questions and suggest appropriate analysis types.
    """
    
    def __init__(
        self,
        llm,
        function_collection:DocumentChromaStore=None,
        example_collection:DocumentChromaStore=None,
        insights_collection:DocumentChromaStore=None,
        max_functions_to_retrieve: int = 10
    ):
        """
        Initialize the Analysis Intent Planner
        
        Args:
            llm: LangChain LLM instance
            function_collection: ChromaDB collection for function definitions
            example_collection: ChromaDB collection for function examples
            insights_collection: ChromaDB collection for function insights
            max_functions_to_retrieve: Maximum number of functions to retrieve
        """
        self.llm = llm
        self.function_collection = function_collection
        self.example_collection = example_collection
        self.insights_collection = insights_collection
        self.max_functions_to_retrieve = max_functions_to_retrieve
        self.retrieval_helper = RetrievalHelper()
        
        # Initialize FunctionRetrieval for getting top functions
        self.function_retrieval = FunctionRetrieval(
            llm=llm,
            function_library_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/all_pipes_functions.json",
            retrieval_helper=self.retrieval_helper
        )
        
       






    @observe(as_type="generation", capture_input=False)
    async def _classify_with_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Use LLM to classify intent based on retrieved context
        
        Args:
            prompt: Formatted prompt with question and retrieved context
            
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
                "system_prompt": ANALYSIS_INTENT_SYSTEM_PROMPT,
                "user_prompt": prompt
            })
            
            return {"response": result}
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            return {"response": ""}



    @observe(name="Analysis Intent Classification")
    async def classify_intent(
        self, 
        question: str, 
        dataframe_description: str, 
        dataframe_summary: str, 
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> AnalysisIntentResult:
        """
        Main method to classify user intent and suggest analysis approach
        
        Args:
            question: User's natural language question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns in the dataframe
            project_id: Optional project ID for retrieving historical questions and instructions
            
        Returns:
            AnalysisIntentResult with classification and suggestions
        """
        try:
            # STEP 1: Rephrase question, classify intent, and create reasoning plan
            logger.info("=== STEP 1: Question Rephrasing, Intent Classification, and Reasoning Plan ===")
            step1_result = await self._step1_question_analysis(
                question=question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                project_id=project_id
            )
            
            # STEP 2: Use Step 1 output for function selection and detailed planning
            logger.info("=== STEP 2: Function Selection and Detailed Planning ===")
            step2_result = await self._step2_function_selection_and_planning(
                step1_output=step1_result,
                question=question,
                available_columns=available_columns,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                project_id=project_id
            )
            
            # STEP 3: Create pipeline reasoning steps based on function definitions
            logger.info("=== STEP 3: Pipeline Reasoning Planning ===")
            step3_result = await self._step3_pipeline_reasoning_planning(
                step1_output=step1_result,
                step2_output=step2_result,
                question=question,
                available_columns=available_columns,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                project_id=project_id
            )
            logger.info(f"Step 3 result: {step3_result}")
            # Create final result combining all three steps
            result = AnalysisIntentResult(
                intent_type=step1_result.get("intent_type", "unclear_intent"),
                confidence_score=float(step1_result.get("confidence_score", 0.0)),
                rephrased_question=step1_result.get("rephrased_question", question),
                suggested_functions=step2_result.get("function_names", []),
                required_data_columns=step1_result.get("required_data_columns", []),
                clarification_needed=step1_result.get("clarification_needed"),
                retrieved_functions=step2_result.get("function_details", []),
                specific_function_matches=step2_result.get("specific_matches", []),
                can_be_answered=step1_result.get("can_be_answered", False),
                feasibility_score=float(step1_result.get("feasibility_score", 0.0)),
                missing_columns=step1_result.get("missing_columns", []),
                available_alternatives=step1_result.get("available_alternatives", []),
                data_suggestions=step1_result.get("data_suggestions"),
                reasoning_plan=step3_result.get("pipeline_reasoning_plan", []),  # Not returned in final result
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in intent classification: {e}")
            return AnalysisIntentResult(
                intent_type="unsupported_analysis",
                confidence_score=0.0,
                rephrased_question=question,
                suggested_functions=[],
                reasoning=f"Classification error: {str(e)}",
                required_data_columns=[],
                clarification_needed="I encountered an error processing your question. Please try rephrasing it.",
                retrieved_functions=[],
                specific_function_matches=[],
                can_be_answered=False,
                feasibility_score=0.0,
                missing_columns=[],
                available_alternatives=[],
                data_suggestions="Unable to assess data due to classification error.",
                reasoning_plan=[],
                pipeline_reasoning_plan=[]
            )

    async def _assess_data_feasibility_with_llm(
        self, 
        required_columns: List[str], 
        available_columns: List[str],
        question: str,
        dataframe_description: str = "",
        dataframe_summary: str = ""
    ) -> Dict[str, Any]:
        """
        Enhanced assessment of data feasibility using LLM for intelligent matching
        
        Args:
            required_columns: List of columns needed for the analysis
            available_columns: List of columns available in the dataframe
            question: User's original question for context
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            
        Returns:
            Dict with enhanced feasibility assessment
        """
        if not required_columns or not available_columns:
            return {
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": required_columns,
                "available_alternatives": [],
                "llm_reasoning": "No required columns or available columns provided"
            }
        
        try:
            # Create LLM prompt for feasibility assessment
            feasibility_prompt = PromptTemplate(
                input_variables=[
                    "question", "required_columns", "available_columns", 
                    "dataframe_description", "dataframe_summary"
                ],
                template="""
You are an expert data analyst assessing whether a data analysis question can be answered with available data.

USER QUESTION: {question}

REQUIRED COLUMNS (what the analysis needs): {required_columns}

AVAILABLE COLUMNS (what's in the dataset): {available_columns}

DATAFRAME DESCRIPTION: {dataframe_description}

DATAFRAME SUMMARY: {dataframe_summary}

TASK: Assess whether the required columns can be satisfied by the available columns, considering:
1. Exact matches
2. Semantic similarity (e.g., "user_id" vs "customer_id", "timestamp" vs "created_at")
3. Data type compatibility
4. Business context relevance
5. Potential transformations or derived columns

ANALYSIS:
- For each required column, find the best match from available columns
- Consider common naming patterns and synonyms
- Evaluate if data types are compatible for the intended analysis
- Assess if any transformations could create suitable columns

OUTPUT FORMAT (JSON):
{{
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["columns that cannot be matched"],
    "available_alternatives": ["column_name (explanation of why it's suitable)"],
    "column_mappings": {{
        "required_column": "best_available_match",
        "required_column2": "best_available_match2"
    }},
    "data_type_assessment": "Assessment of data type compatibility",
    "transformation_suggestions": ["suggestions for data transformations if needed"],
    "llm_reasoning": "Detailed explanation of the feasibility assessment"
}}

SCORING GUIDELINES:
- 1.0: Perfect matches for all required columns
- 0.9: Excellent semantic matches with compatible data types
- 0.8: Good matches with minor transformations needed
- 0.7: Acceptable matches with some data preparation required
- 0.6: Partial matches with significant workarounds needed
- <0.5: Poor matches, analysis may not be feasible
"""
            )
            
            # Format the prompt
            formatted_prompt = feasibility_prompt.format(
                question=question,
                required_columns=required_columns,
                available_columns=available_columns,
                dataframe_description=dataframe_description or "No description available",
                dataframe_summary=dataframe_summary or "No summary available"
            )
            
            # Get LLM assessment using direct LLM call instead of _classify_with_llm
            try:
                # Create the chain for feasibility assessment
                chain = feasibility_prompt | self.llm
                
                # Generate response
                result = await chain.ainvoke({
                    "question": question,
                    "required_columns": required_columns,
                    "available_columns": available_columns,
                    "dataframe_description": dataframe_description or "No description available",
                    "dataframe_summary": dataframe_summary or "No summary available"
                })
                
                # Extract content from AIMessage
                response_content = result.content if hasattr(result, 'content') else str(result)
                
                # Remove markdown code blocks if present
                if response_content.startswith("```json"):
                    response_content = response_content.split("```json")[1]
                if response_content.endswith("```"):
                    response_content = response_content.rsplit("```", 1)[0]
                
                # Clean the response content - remove JavaScript-style comments
                import re
                # Remove single-line comments (// ...)
                response_content = re.sub(r'//.*?$', '', response_content, flags=re.MULTILINE)
                # Remove multi-line comments (/* ... */)
                response_content = re.sub(r'/\*.*?\*/', '', response_content, flags=re.DOTALL)
                # Clean up any trailing commas before closing braces/brackets
                response_content = re.sub(r',(\s*[}\]])', r'\1', response_content)
                
                # Parse JSON response
                response_content = response_content.strip()
                try:
                    assessment = orjson.loads(response_content)
                    
                    # Validate that assessment has required fields
                    required_fields = ["can_be_answered", "feasibility_score", "missing_columns", "available_alternatives"]
                    missing_fields = [field for field in required_fields if field not in assessment]
                    
                    if missing_fields:
                        logger.warning(f"LLM assessment missing required fields: {missing_fields}")
                        # Fill in missing fields with defaults
                        if "can_be_answered" not in assessment:
                            assessment["can_be_answered"] = False
                        if "feasibility_score" not in assessment:
                            assessment["feasibility_score"] = 0.0
                        if "missing_columns" not in assessment:
                            assessment["missing_columns"] = required_columns
                        if "available_alternatives" not in assessment:
                            assessment["available_alternatives"] = []
                        if "llm_reasoning" not in assessment:
                            assessment["llm_reasoning"] = "LLM assessment incomplete, using basic assessment for missing fields"
                            
                except (orjson.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"Failed to parse LLM response as JSON: {json_error}")
                    logger.debug(f"Raw response: {response_content}")
                    # Fallback to basic assessment
                    assessment = self._assess_data_feasibility(required_columns, available_columns)
                    assessment["llm_reasoning"] = f"LLM response was not valid JSON: {str(json_error)}, using basic assessment"
                
            except Exception as llm_error:
                logger.warning(f"LLM feasibility assessment failed: {llm_error}")
                # Fallback to basic assessment
                assessment = self._assess_data_feasibility(required_columns, available_columns)
                assessment["llm_reasoning"] = f"LLM assessment failed: {str(llm_error)}, using basic assessment"
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error in LLM feasibility assessment: {e}")
            # Fallback to basic assessment
            basic_assessment = self._assess_data_feasibility(required_columns, available_columns)
            basic_assessment["llm_reasoning"] = f"LLM assessment failed: {str(e)}, using basic assessment"
            return basic_assessment

    def _assess_data_feasibility(
        self, 
        required_columns: List[str], 
        available_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Quick assessment of data feasibility based on column requirements
        
        Args:
            required_columns: List of columns needed for the analysis
            available_columns: List of columns available in the dataframe
            
        Returns:
            Dict with feasibility assessment
        """
        if not required_columns or not available_columns:
            return {
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": required_columns,
                "available_alternatives": []
            }
        
        # Check exact matches
        exact_matches = [col for col in required_columns if col in available_columns]
        missing_columns = [col for col in required_columns if col not in available_columns]
        
        # Look for similar column names (basic string matching)
        alternatives = []
        for missing_col in missing_columns:
            missing_lower = missing_col.lower()
            for avail_col in available_columns:
                avail_lower = avail_col.lower()
                # Check for partial matches or common substitutions
                if (missing_lower in avail_lower or avail_lower in missing_lower or
                    any(keyword in avail_lower for keyword in missing_lower.split('_')) or
                    self._are_similar_columns(missing_col, avail_col)):
                    alternatives.append(f"{avail_col} (similar to {missing_col})")
        
        # Calculate feasibility score
        exact_match_ratio = len(exact_matches) / len(required_columns)
        alternative_ratio = len(alternatives) / max(len(missing_columns), 1)
        
        feasibility_score = exact_match_ratio + (alternative_ratio * 0.5)
        can_be_answered = feasibility_score >= 0.6  # At least 60% feasibility
        
        return {
            "can_be_answered": can_be_answered,
            "feasibility_score": min(feasibility_score, 1.0),
            "missing_columns": missing_columns,
            "available_alternatives": alternatives
        }
    
    def _are_similar_columns(self, col1: str, col2: str) -> bool:
        """
        Check if two column names are semantically similar
        
        Args:
            col1: First column name
            col2: Second column name
            
        Returns:
            True if columns are likely similar
        """
        # Common column name mappings
        synonyms = {
            'time': ['date', 'timestamp', 'datetime', 'created_at', 'updated_at'],
            'user': ['customer', 'client', 'account', 'person'],
            'id': ['identifier', 'key', 'uuid', 'index'],
            'value': ['amount', 'price', 'cost', 'revenue', 'total'],
            'type': ['category', 'class', 'kind', 'group'],
            'name': ['title', 'label', 'description']
        }
        
        col1_lower = col1.lower()
        col2_lower = col2.lower()
        
        for key, similar_words in synonyms.items():
            if ((key in col1_lower and any(word in col2_lower for word in similar_words)) or
                (key in col2_lower and any(word in col1_lower for word in similar_words))):
                return True
        
        return False

    def get_available_analyses(self) -> Dict[str, str]:
        """Return available analysis types and their descriptions"""
        return {
            "time_series_analysis": "Analyze data patterns over time periods (includes variance, lead, lag analysis)",
            "trend_analysis": "Analyze trends, growth patterns, and forecasting",
            "segmentation_analysis": "Group users or data points into meaningful segments",
            "cohort_analysis": "Analyze user behavior and retention over time",
            "funnel_analysis": "Analyze user conversion funnels and paths",
            "risk_analysis": "Perform risk analysis and portfolio assessment",
            "anomaly_detection": "Detect outliers and anomalies in data (statistical, contextual, collective, change points)",
            "metrics_calculation": "Calculate statistical metrics and aggregations",
            "operations_analysis": "Statistical operations and experimental analysis"
        }

    async def quick_feasibility_check(
        self,
        question: str,
        available_columns: List[str],
        dataframe_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Quick feasibility check without full LLM classification
        
        Args:
            question: User's question
            available_columns: List of available columns
            dataframe_description: Optional description of the dataframe
            
        Returns:
            Basic feasibility assessment
        """
        try:
            # Extract basic requirements from question using keywords
            question_lower = question.lower()
            
            # Infer likely required columns based on question content
            inferred_columns = []
            
            # Time-related requirements
            if any(word in question_lower for word in ['time', 'over time', 'temporal', 'trend', 'rolling', 'moving']):
                time_cols = [col for col in available_columns if any(t in col.lower() for t in ['time', 'date', 'timestamp', 'created'])]
                if time_cols:
                    inferred_columns.extend(time_cols[:1])  # Take first time column
                else:
                    inferred_columns.append("time_column")
            
            # User/ID requirements
            if any(word in question_lower for word in ['user', 'customer', 'retention', 'cohort', 'funnel']):
                id_cols = [col for col in available_columns if any(t in col.lower() for t in ['user', 'customer', 'id', 'account'])]
                if id_cols:
                    inferred_columns.extend(id_cols[:1])
                else:
                    inferred_columns.append("user_id")
            
            # Anomaly detection requirements
            if any(word in question_lower for word in ['anomaly', 'anomalies', 'outlier', 'outliers', 'detect', 'detection']):
                # For anomaly detection, we typically need time column and value column
                time_cols = [col for col in available_columns if any(t in col.lower() for t in ['time', 'date', 'timestamp', 'created'])]
                if time_cols:
                    inferred_columns.extend(time_cols[:1])
                else:
                    inferred_columns.append("time_column")
                
                # Add value columns that could be analyzed for anomalies
                value_cols = [col for col in available_columns if any(t in col.lower() for t in ['value', 'amount', 'price', 'cost', 'revenue', 'total', 'metric'])]
                if value_cols:
                    inferred_columns.extend(value_cols[:2])  # Take first 2 value columns
                else:
                    inferred_columns.append("value_column")
            
            # Extract mentioned column names from question
            for col in available_columns:
                if col.lower() in question_lower:
                    inferred_columns.append(col)
            
            # Remove duplicates
            inferred_columns = list(set(inferred_columns))
            
            # Assess feasibility using LLM
            feasibility = await self._assess_data_feasibility_with_llm(
                inferred_columns, 
                available_columns, 
                question, 
                dataframe_description or "",
                dataframe_description or ""
            )
            
            return {
                "feasible": feasibility["can_be_answered"],
                "feasibility_score": feasibility["feasibility_score"],
                "inferred_requirements": inferred_columns,
                "missing_columns": feasibility["missing_columns"],
                "available_alternatives": feasibility["available_alternatives"],
                "recommendation": "Proceed with full analysis" if feasibility["can_be_answered"] 
                               else "Consider data preparation or question modification"
            }
            
        except Exception as e:
            logger.error(f"Error in quick feasibility check: {e}")
            return {
                "feasible": False,
                "feasibility_score": 0.0,
                "inferred_requirements": [],
                "missing_columns": [],
                "available_alternatives": [],
                "recommendation": f"Error in assessment: {str(e)}"
            }

    async def get_historical_questions(
        self, 
        query: str, 
        project_id: str,
        similarity_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Retrieve historical questions for a given query and project.
        
        Args:
            query: The query string to search for similar historical questions
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            
        Returns:
            Dictionary containing historical questions and metadata
        """
        if not self.retrieval_helper:
            logger.warning("RetrievalHelper not available")
            return {
                "error": "RetrievalHelper not available",
                "historical_questions": []
            }
        
        try:
            return await self.retrieval_helper.get_historical_questions(
                query=query,
                project_id=project_id,
                similarity_threshold=similarity_threshold
            )
        except Exception as e:
            logger.error(f"Error retrieving historical questions: {str(e)}")
            return {
                "error": str(e),
                "historical_questions": []
            }

    async def get_instructions(
        self, 
        query: str, 
        project_id: str,
        similarity_threshold: float = 0.7,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieve instructions for a given query and project.
        
        Args:
            query: The query string to search for similar instructions
            project_id: The project ID to filter results
            similarity_threshold: Minimum similarity score for retrieved documents
            top_k: Maximum number of documents to retrieve
            
        Returns:
            Dictionary containing instructions and metadata
        """
        if not self.retrieval_helper:
            logger.warning("RetrievalHelper not available")
            return {
                "error": "RetrievalHelper not available",
                "instructions": []
            }
        
        try:
            return await self.retrieval_helper.get_instructions(
                query=query,
                project_id=project_id,
                similarity_threshold=similarity_threshold,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"Error retrieving instructions: {str(e)}")
            return {
                "error": str(e),
                "instructions": []
            }




        """
        Generate a comprehensive reasoning plan using ALL available functions.
        
        Args:
            question: User's question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            all_functions: List of all available functions
            historical_context: Historical questions context
            instructions_context: Instructions context
            
        Returns:
            List of reasoning plan steps
        """
        try:
            # Format all functions for the prompt
            functions_text = "### ALL AVAILABLE FUNCTIONS ###\n"
            for i, func in enumerate(all_functions[:50], 1):  # Limit to first 50 for prompt size
                functions_text += f"{i}. {func['function_name']} ({func['pipe_name']})\n"
                functions_text += f"   Description: {func['description']}\n"
                functions_text += f"   Usage: {func['usage_description']}\n"
                functions_text += f"   Category: {func['category']}\n"
                functions_text += f"   Type: {func['type_of_operation']}\n\n"
            
            # Create prompt for comprehensive reasoning plan
            comprehensive_prompt = PromptTemplate(
                input_variables=[
                    "question", "dataframe_description", "dataframe_summary", "available_columns",
                    "all_functions", "historical_context", "instructions_context"
                ],
                template="""
You are an expert data analyst creating a comprehensive step-by-step reasoning plan for analysis.

### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}
**Available Columns:** {available_columns}

{all_functions}

{historical_context}

{instructions_context}

### TASK ###
Create a comprehensive step-by-step reasoning plan for this analysis. Consider ALL available functions and choose the best approach based on:
1. The specific requirements of the user's question
2. The available data columns and their characteristics
3. Historical patterns and similar analyses
4. Project-specific instructions and best practices
5. The most effective combination of functions to achieve the desired outcome

### REASONING PLAN REQUIREMENTS ###
Each step should include:
- step_number: Sequential number
- step_title: Brief, descriptive title
- step_description: Detailed description of what this step involves
- data_requirements: Specific columns/data needed for this step
- expected_outcome: What result or insight this step should produce
- considerations: Important considerations, potential issues, or best practices
- suggested_functions: List of specific function names that could be used for this step
- function_reasoning: Why these functions are appropriate for this step

### ANALYSIS APPROACH ###
Consider the following aspects:
1. Data preparation and cleaning
2. Feature engineering if needed
3. Primary analysis methodology
4. Secondary analysis or validation
5. Visualization and interpretation
6. Quality checks and validation
7. Expected insights and outcomes

### OUTPUT FORMAT ###
Provide your response as a JSON array of steps:

[
    {{
        "step_number": 1,
        "step_title": "Data Preparation",
        "step_description": "Clean and prepare the data for analysis",
        "data_requirements": ["column1", "column2"],
        "expected_outcome": "Clean dataset ready for analysis",
        "considerations": "Important considerations for this step",
        "suggested_functions": ["function1", "function2"],
        "function_reasoning": "Why these functions are appropriate"
    }},
    {{
        "step_number": 2,
        "step_title": "Analysis Step",
        "step_description": "Perform the main analysis",
        "data_requirements": ["column1", "column2"],
        "expected_outcome": "Analysis results",
        "considerations": "Important considerations for this step",
        "suggested_functions": ["function3", "function4"],
        "function_reasoning": "Why these functions are appropriate"
    }}
]

Make the plan practical, actionable, and specific to the available data and analysis type. Consider multiple approaches and choose the most effective combination of functions.
"""
            )
            
            # Format the prompt
            formatted_prompt = comprehensive_prompt.format(
                question=question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                all_functions=functions_text,
                historical_context=historical_context,
                instructions_context=instructions_context
            )
            
            # Get LLM response
            try:
                # Create the chain for comprehensive reasoning plan generation
                chain = comprehensive_prompt | self.llm
                
                # Generate response
                result = await chain.ainvoke({
                    "question": question,
                    "dataframe_description": dataframe_description,
                    "dataframe_summary": dataframe_summary,
                    "available_columns": available_columns,
                    "all_functions": functions_text,
                    "historical_context": historical_context,
                    "instructions_context": instructions_context
                })
                
                # Extract content from AIMessage
                response_content = result.content if hasattr(result, 'content') else str(result)
                
                # Remove markdown code blocks if present
                if response_content.startswith("```json"):
                    response_content = response_content.split("```json")[1]
                if response_content.endswith("```"):
                    response_content = response_content.rsplit("```", 1)[0]
                
                # Clean the response content - remove JavaScript-style comments
                import re
                # Remove single-line comments (// ...)
                response_content = re.sub(r'//.*?$', '', response_content, flags=re.MULTILINE)
                # Remove multi-line comments (/* ... */)
                response_content = re.sub(r'/\*.*?\*/', '', response_content, flags=re.DOTALL)
                # Clean up any trailing commas before closing braces/brackets
                response_content = re.sub(r',(\s*[}\]])', r'\1', response_content)
                
                # Parse JSON response
                response_content = response_content.strip()
                try:
                    reasoning_plan = orjson.loads(response_content)
                    
                    # Validate that reasoning_plan is a list
                    if not isinstance(reasoning_plan, list):
                        logger.warning("LLM response is not a list, converting to list")
                        reasoning_plan = [reasoning_plan] if reasoning_plan else []
                    
                    # Validate each step has required fields
                    validated_plan = []
                    for i, step in enumerate(reasoning_plan):
                        if isinstance(step, dict):
                            validated_step = {
                                "step_number": step.get("step_number", i + 1),
                                "step_title": step.get("step_title", f"Step {i + 1}"),
                                "step_description": step.get("step_description", ""),
                                "data_requirements": step.get("data_requirements", []),
                                "expected_outcome": step.get("expected_outcome", ""),
                                "considerations": step.get("considerations", ""),
                                "suggested_functions": step.get("suggested_functions", []),
                                "function_reasoning": step.get("function_reasoning", "")
                            }
                            validated_plan.append(validated_step)
                    
                    logger.info(f"Generated comprehensive reasoning plan with {len(validated_plan)} steps")
                    return validated_plan
                    
                except (orjson.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"Failed to parse LLM response as JSON: {json_error}")
                    logger.debug(f"Raw response: {response_content}")
                    # Return a basic plan
                    return [
                        {
                            "step_number": 1,
                            "step_title": "Data Preparation",
                            "step_description": "Prepare and clean the data for analysis",
                            "data_requirements": available_columns[:3],
                            "expected_outcome": "Clean dataset ready for analysis",
                            "considerations": "Ensure data quality and handle missing values",
                            "suggested_functions": ["data_cleaning_function"],
                            "function_reasoning": "Basic data preparation needed"
                        },
                        {
                            "step_number": 2,
                            "step_title": "Analysis Execution",
                            "step_description": "Perform the main analysis",
                            "data_requirements": available_columns[:3],
                            "expected_outcome": "Analysis results and insights",
                            "considerations": "Follow best practices for the analysis type",
                            "suggested_functions": ["analysis_function"],
                            "function_reasoning": "Primary analysis function needed"
                        }
                    ]
                
            except Exception as llm_error:
                logger.warning(f"LLM comprehensive reasoning plan generation failed: {llm_error}")
                # Return a basic plan
                return [
                    {
                        "step_number": 1,
                        "step_title": "Data Preparation",
                        "step_description": "Prepare and clean the data for analysis",
                        "data_requirements": available_columns[:3],
                        "expected_outcome": "Clean dataset ready for analysis",
                        "considerations": "Ensure data quality and handle missing values",
                        "suggested_functions": ["data_cleaning_function"],
                        "function_reasoning": "Basic data preparation needed"
                    },
                    {
                        "step_number": 2,
                        "step_title": "Analysis Execution",
                        "step_description": "Perform the main analysis",
                        "data_requirements": available_columns[:3],
                        "expected_outcome": "Analysis results and insights",
                        "considerations": "Follow best practices for the analysis type",
                        "suggested_functions": ["analysis_function"],
                        "function_reasoning": "Primary analysis function needed"
                    }
                ]
            
        except Exception as e:
            logger.error(f"Error generating comprehensive reasoning plan: {e}")
            return [
                {
                    "step_number": 1,
                    "step_title": "Error in Plan Generation",
                    "step_description": "Unable to generate detailed plan due to error",
                    "data_requirements": [],
                    "expected_outcome": "Error resolution needed",
                    "considerations": f"Error: {str(e)}",
                    "suggested_functions": [],
                    "function_reasoning": "Error occurred during plan generation"
                }
            ]

    async def _select_best_functions_from_plan(
        self,
        question: str,
        reasoning_plan: List[Dict[str, Any]],
        all_functions: List[Dict[str, Any]],
        available_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Select the best functions based on the comprehensive reasoning plan.
        
        Args:
            question: User's question
            reasoning_plan: Comprehensive reasoning plan
            all_functions: List of all available functions
            available_columns: List of available columns
            
        Returns:
            Dictionary with selected function information
        """
        try:
            # Extract all suggested functions from the reasoning plan
            all_suggested_functions = []
            for step in reasoning_plan:
                suggested_functions = step.get("suggested_functions", [])
                all_suggested_functions.extend(suggested_functions)
            
            # Remove duplicates and get unique function names
            unique_function_names = list(set(all_suggested_functions))
            
            # Find the actual function details for each suggested function
            selected_function_details = []
            specific_matches = []
            
            for func_name in unique_function_names:
                # Find the function in all_functions
                for func in all_functions:
                    if func['function_name'] == func_name:
                        # Calculate relevance score based on how many times it appears in the plan
                        relevance_count = all_suggested_functions.count(func_name)
                        relevance_score = min(0.9 + (relevance_count * 0.1), 1.0)  # Base 0.9, max 1.0
                        
                        function_detail = {
                            "function_name": func['function_name'],
                            "pipe_name": func['pipe_name'],
                            "description": func['description'],
                            "usage_description": func['usage_description'],
                            "relevance_score": relevance_score,
                            "reasoning": f"Selected based on reasoning plan (appears {relevance_count} times)",
                            "category": func['category'],
                            "type_of_operation": func['type_of_operation']
                        }
                        
                        selected_function_details.append(function_detail)
                        
                        # Mark as specific match if high relevance
                        if relevance_score >= 0.95:
                            specific_matches.append(func_name)
                        
                        break
            
            # Sort by relevance score (highest first)
            selected_function_details.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Take top 5 functions
            top_functions = selected_function_details[:5]
            
            # Get function names for the result
            function_names = [func['function_name'] for func in top_functions]
            
            logger.info(f"Selected {len(top_functions)} functions based on reasoning plan")
            logger.info(f"Selected functions: {function_names}")
            
            return {
                "function_names": function_names,
                "function_details": top_functions,
                "specific_matches": specific_matches,
                "total_suggested": len(unique_function_names),
                "reasoning_plan_steps": len(reasoning_plan)
            }
            
        except Exception as e:
            logger.error(f"Error selecting best functions from plan: {e}")
            # Return fallback selection
            fallback_functions = all_functions[:3]  # Take first 3 functions as fallback
            return {
                "function_names": [func['function_name'] for func in fallback_functions],
                "function_details": fallback_functions,
                "specific_matches": [],
                "total_suggested": 3,
                "reasoning_plan_steps": len(reasoning_plan)
            }

    async def _classify_intent_from_plan(
        self,
        question: str,
        reasoning_plan: List[Dict[str, Any]],
        selected_functions: Dict[str, Any],
        available_columns: List[str]
    ) -> Dict[str, Any]:
        """
        Classify intent based on the reasoning plan and selected functions.
        
        Args:
            question: User's question
            reasoning_plan: Comprehensive reasoning plan
            selected_functions: Selected function information
            available_columns: List of available columns
            
        Returns:
            Dictionary with intent classification information
        """
        try:
            # Create prompt for intent classification based on plan
            intent_prompt = PromptTemplate(
                input_variables=[
                    "question", "reasoning_plan", "selected_functions", "available_columns"
                ],
                template="""
You are an expert data analyst classifying the intent of a user's question based on a comprehensive reasoning plan and selected functions.

### USER QUESTION ###
{question}

### COMPREHENSIVE REASONING PLAN ###
{reasoning_plan}

### SELECTED FUNCTIONS ###
{selected_functions}

### AVAILABLE COLUMNS ###
{available_columns}

### TASK ###
Based on the comprehensive reasoning plan and selected functions, classify the analysis intent and assess feasibility.

### ANALYSIS TYPES ###
- time_series_analysis: Analyze data patterns over time periods
- trend_analysis: Analyze trends, growth patterns, forecasting
- segmentation_analysis: Group users/data into meaningful segments
- cohort_analysis: Analyze user behavior and retention over time
- funnel_analysis: Analyze user conversion funnels and paths
- risk_analysis: Perform risk analysis and portfolio assessment
- anomaly_detection: Detect outliers and anomalies in data
- metrics_calculation: Calculate statistical metrics and aggregations
- operations_analysis: Statistical operations and experimental analysis
- unclear_intent: Question is too vague or ambiguous
- unsupported_analysis: Requested analysis is not supported by available functions

### OUTPUT FORMAT ###
Provide your response as a JSON object:

{{
    "intent_type": "analysis_type",
    "confidence_score": 0.0-1.0,
    "rephrased_question": "clear and specific question",
    "reasoning": "brief explanation based on reasoning plan and selected functions",
    "required_data_columns": ["column1", "column2"],
    "clarification_needed": "question if intent unclear or null",
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["missing_col1", "missing_col2"],
    "available_alternatives": ["alt_col1", "alt_col2"],
    "data_suggestions": "advice on data prep or alternatives or null"
}}

Consider the reasoning plan steps and selected functions to determine the most appropriate intent classification.
"""
            )
            
            # Format the reasoning plan for the prompt
            plan_text = ""
            for step in reasoning_plan:
                plan_text += f"Step {step.get('step_number', 'N/A')}: {step.get('step_title', 'N/A')}\n"
                plan_text += f"  Description: {step.get('step_description', 'N/A')}\n"
                plan_text += f"  Functions: {', '.join(step.get('suggested_functions', []))}\n"
                plan_text += f"  Reasoning: {step.get('function_reasoning', 'N/A')}\n\n"
            
            # Format selected functions for the prompt
            functions_text = ""
            for func in selected_functions.get("function_details", []):
                functions_text += f"- {func['function_name']} ({func['pipe_name']})\n"
                functions_text += f"  Description: {func['description']}\n"
                functions_text += f"  Relevance: {func['relevance_score']}\n"
                functions_text += f"  Category: {func['category']}\n\n"
            
            # Format the prompt
            formatted_prompt = intent_prompt.format(
                question=question,
                reasoning_plan=plan_text,
                selected_functions=functions_text,
                available_columns=available_columns
            )
            
            # Get LLM response
            try:
                # Create the chain for intent classification
                chain = intent_prompt | self.llm
                
                # Generate response
                result = await chain.ainvoke({
                    "question": question,
                    "reasoning_plan": plan_text,
                    "selected_functions": functions_text,
                    "available_columns": available_columns
                })
                
                # Extract content from AIMessage
                response_content = result.content if hasattr(result, 'content') else str(result)
                
                # Remove markdown code blocks if present
                if response_content.startswith("```json"):
                    response_content = response_content.split("```json")[1]
                if response_content.endswith("```"):
                    response_content = response_content.rsplit("```", 1)[0]
                
                # Clean the response content - remove JavaScript-style comments
                import re
                # Remove single-line comments (// ...)
                response_content = re.sub(r'//.*?$', '', response_content, flags=re.MULTILINE)
                # Remove multi-line comments (/* ... */)
                response_content = re.sub(r'/\*.*?\*/', '', response_content, flags=re.DOTALL)
                # Clean up any trailing commas before closing braces/brackets
                response_content = re.sub(r',(\s*[}\]])', r'\1', response_content)
                
                # Parse JSON response
                response_content = response_content.strip()
                try:
                    classification = orjson.loads(response_content)
                    
                    # Validate required fields
                    required_fields = ["intent_type", "confidence_score", "rephrased_question", "reasoning"]
                    missing_fields = [field for field in required_fields if field not in classification]
                    
                    if missing_fields:
                        logger.warning(f"Intent classification missing required fields: {missing_fields}")
                        # Fill in missing fields with defaults
                        if "intent_type" not in classification:
                            classification["intent_type"] = "unclear_intent"
                        if "confidence_score" not in classification:
                            classification["confidence_score"] = 0.0
                        if "rephrased_question" not in classification:
                            classification["rephrased_question"] = question
                        if "reasoning" not in classification:
                            classification["reasoning"] = "Classification incomplete"
                    
                    logger.info(f"Intent classified as: {classification.get('intent_type', 'unknown')}")
                    return classification
                    
                except (orjson.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"Failed to parse intent classification as JSON: {json_error}")
                    logger.debug(f"Raw response: {response_content}")
                    # Return fallback classification
                    return {
                        "intent_type": "unclear_intent",
                        "confidence_score": 0.0,
                        "rephrased_question": question,
                        "reasoning": f"Error parsing classification: {str(json_error)}",
                        "required_data_columns": [],
                        "clarification_needed": "Unable to classify intent due to processing error",
                        "can_be_answered": False,
                        "feasibility_score": 0.0,
                        "missing_columns": [],
                        "available_alternatives": [],
                        "data_suggestions": "Error in intent classification"
                    }
                
            except Exception as llm_error:
                logger.warning(f"LLM intent classification failed: {llm_error}")
                # Return fallback classification
                return {
                    "intent_type": "unclear_intent",
                    "confidence_score": 0.0,
                    "rephrased_question": question,
                    "reasoning": f"Intent classification failed: {str(llm_error)}",
                    "required_data_columns": [],
                    "clarification_needed": "Unable to classify intent due to LLM error",
                    "can_be_answered": False,
                    "feasibility_score": 0.0,
                    "missing_columns": [],
                    "available_alternatives": [],
                    "data_suggestions": "Error in intent classification"
                }
            
        except Exception as e:
            logger.error(f"Error in intent classification from plan: {e}")
            return {
                "intent_type": "unsupported_analysis",
                "confidence_score": 0.0,
                "rephrased_question": question,
                "reasoning": f"Error in intent classification: {str(e)}",
                "required_data_columns": [],
                "clarification_needed": "Error occurred during intent classification",
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": [],
                "available_alternatives": [],
                "data_suggestions": "Error in intent classification"
            }

    async def _step1_question_analysis(
        self,
        question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        STEP 1: Rephrase question, classify intent based on MOST SPECIFIC analysis type, and create reasoning plan.
        
        Args:
            question: User's natural language question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID for context retrieval
            
        Returns:
            Dictionary with rephrased question, intent classification, and reasoning plan
        """
        try:
            # Load all available functions for comprehensive planning
            function_library = self.function_retrieval._load_function_library()
            all_functions = []
            
            # Extract all functions from the library
            for pipe_name, pipe_info in function_library.items():
                if 'functions' in pipe_info:
                    for func_name, func_info in pipe_info['functions'].items():
                        all_functions.append({
                            'function_name': func_name,
                            'pipe_name': pipe_name,
                            'description': func_info.get('description', ''),
                            'usage_description': func_info.get('usage_description', ''),
                            'category': func_info.get('category', ''),
                            'type_of_operation': func_info.get('type_of_operation', '')
                        })
            
            logger.info(f"Loaded {len(all_functions)} total functions for Step 1 analysis")
            
            # Retrieve historical context and instructions if project_id is provided
            historical_context = ""
            instructions_context = ""
            
            if self.retrieval_helper and project_id:
                try:
                    # Get historical questions
                    historical_result = await self.retrieval_helper.get_historical_questions(
                        query=question,
                        project_id=project_id,
                        similarity_threshold=0.7
                    )
                    
                    if historical_result and historical_result.get("historical_questions"):
                        historical_questions = historical_result.get("historical_questions", [])
                        if historical_questions:
                            historical_context = "\n### RELEVANT HISTORICAL QUESTIONS ###\n"
                            for i, hist_question in enumerate(historical_questions[:3], 1):
                                historical_context += f"{i}. Question: {hist_question.get('question', 'N/A')}\n"
                                if hist_question.get('summary'):
                                    historical_context += f"   Summary: {hist_question.get('summary', 'N/A')}\n"
                                if hist_question.get('statement'):
                                    historical_context += f"   Statement: {hist_question.get('statement', 'N/A')}\n"
                                historical_context += "\n"
                            logger.info(f"Retrieved {len(historical_questions)} historical questions for project {project_id}")
                    
                    # Get instructions
                    instructions_result = await self.retrieval_helper.get_instructions(
                        query=question,
                        project_id=project_id,
                        similarity_threshold=0.7,
                        top_k=10
                    )
                    
                    if instructions_result and instructions_result.get("instructions"):
                        instructions = instructions_result.get("instructions", [])
                        if instructions:
                            instructions_context = "\n### RELEVANT INSTRUCTIONS ###\n"
                            for i, instruction in enumerate(instructions[:5], 1):
                                instructions_context += f"{i}. Question: {instruction.get('question', 'N/A')}\n"
                                instructions_context += f"   Instruction: {instruction.get('instruction', 'N/A')}\n\n"
                            logger.info(f"Retrieved {len(instructions)} instructions for project {project_id}")
                            
                except Exception as e:
                    logger.error(f"Error retrieving context: {str(e)}")
            
            # Create prompt for Step 1 analysis
            step1_prompt = PromptTemplate(
                input_variables=[
                    "question", "dataframe_description", "dataframe_summary", "available_columns",
                    "all_functions", "historical_context", "instructions_context"
                ],
                template="""
You are an expert data analyst performing STEP 1 of a multi-step analysis process.

### USER QUESTION ###
{question}

### DATAFRAME CONTEXT ###
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}
**Available Columns:** {available_columns}

### ALL AVAILABLE FUNCTIONS ###
{all_functions}

{historical_context}

{instructions_context}

### STEP 1 TASK ###
Perform the following three tasks in order:

1. **REPHRASE THE QUESTION**: Create a clear, specific, and actionable version of the user's question that can be directly used for analysis.

2. **CLASSIFY INTENT**: Determine the MOST SPECIFIC analysis type that matches the question. Choose the most precise classification from:
   - time_series_analysis: Analyze data patterns over time periods (rolling windows, trends, seasonality)
   - trend_analysis: Analyze growth patterns, forecasting, directional changes
   - segmentation_analysis: Group users/data into meaningful segments or clusters
   - cohort_analysis: Analyze user behavior and retention over time periods
   - funnel_analysis: Analyze user conversion funnels and paths
   - risk_analysis: Perform risk assessment, portfolio analysis, volatility analysis
   - anomaly_detection: Detect outliers, anomalies, unusual patterns
   - metrics_calculation: Calculate statistical metrics, aggregations, KPIs
   - operations_analysis: Statistical operations, experimental analysis, A/B testing
   - unclear_intent: Question is too vague or ambiguous
   - unsupported_analysis: Requested analysis is not supported by available functions

3. **CREATE REASONING PLAN**: Develop a step-by-step reasoning plan that outlines the logical approach to answer the question. Focus on the analysis methodology and data processing steps without specifying exact function names.

### OUTPUT FORMAT ###
Provide your response as a JSON object:

{{
    "rephrased_question": "clear and specific question",
    "intent_type": "most_specific_analysis_type",
    "confidence_score": 0.0-1.0,
    "reasoning": "brief explanation of why this intent type was chosen",
    "required_data_columns": ["column1", "column2"],
    "clarification_needed": "question if intent unclear or null",
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["missing_col1", "missing_col2"],
    "available_alternatives": ["alt_col1", "alt_col2"],
    "data_suggestions": "advice on data prep or alternatives or null",
    "reasoning_plan": [
        {{
            "step_number": 1,
            "step_title": "Data Preparation",
            "step_description": "What this step involves",
            "data_requirements": ["column1", "column2"],
            "expected_outcome": "What result this step should produce",
            "considerations": "Important considerations for this step"
        }}
    ]
}}

Focus on the MOST SPECIFIC analysis type that precisely matches the question requirements. The reasoning plan should describe the analysis methodology and data processing steps without specifying exact function names - function selection will be handled separately.
"""
            )
            
            # Format all functions for the prompt
            functions_text = ""
            for i, func in enumerate(all_functions[:50], 1):  # Limit to first 50 for prompt size
                functions_text += f"{i}. {func['function_name']} ({func['pipe_name']})\n"
                functions_text += f"   Description: {func['description']}\n"
                functions_text += f"   Usage: {func['usage_description']}\n"
                functions_text += f"   Category: {func['category']}\n"
                functions_text += f"   Type: {func['type_of_operation']}\n\n"
            
            # Get LLM response for Step 1
            try:
                # Create the chain for Step 1 analysis
                chain = step1_prompt | self.llm
                
                # Generate response
                result = await chain.ainvoke({
                    "question": question,
                    "dataframe_description": dataframe_description,
                    "dataframe_summary": dataframe_summary,
                    "available_columns": available_columns,
                    "all_functions": functions_text,
                    "historical_context": historical_context,
                    "instructions_context": instructions_context
                })
                
                # Extract content from AIMessage
                response_content = result.content if hasattr(result, 'content') else str(result)
                
                # Remove markdown code blocks if present
                if response_content.startswith("```json"):
                    response_content = response_content.split("```json")[1]
                if response_content.endswith("```"):
                    response_content = response_content.rsplit("```", 1)[0]
                
                # Clean the response content - remove JavaScript-style comments
                import re
                # Remove single-line comments (// ...)
                response_content = re.sub(r'//.*?$', '', response_content, flags=re.MULTILINE)
                # Remove multi-line comments (/* ... */)
                response_content = re.sub(r'/\*.*?\*/', '', response_content, flags=re.DOTALL)
                # Clean up any trailing commas before closing braces/brackets
                response_content = re.sub(r',(\s*[}\]])', r'\1', response_content)
                
                # Parse JSON response
                response_content = response_content.strip()
                try:
                    step1_result = orjson.loads(response_content)
                    
                    # Validate required fields
                    required_fields = ["rephrased_question", "intent_type", "confidence_score", "reasoning", "reasoning_plan"]
                    missing_fields = [field for field in required_fields if field not in step1_result]
                    
                    if missing_fields:
                        logger.warning(f"Step 1 result missing required fields: {missing_fields}")
                        # Fill in missing fields with defaults
                        if "rephrased_question" not in step1_result:
                            step1_result["rephrased_question"] = question
                        if "intent_type" not in step1_result:
                            step1_result["intent_type"] = "unclear_intent"
                        if "confidence_score" not in step1_result:
                            step1_result["confidence_score"] = 0.0
                        if "reasoning" not in step1_result:
                            step1_result["reasoning"] = "Step 1 analysis incomplete"
                        if "reasoning_plan" not in step1_result:
                            step1_result["reasoning_plan"] = []
                    
                    logger.info(f"Step 1 completed successfully:")
                    logger.info(f"  - Rephrased question: {step1_result.get('rephrased_question', 'N/A')}")
                    logger.info(f"  - Intent type: {step1_result.get('intent_type', 'N/A')}")
                    logger.info(f"  - Confidence score: {step1_result.get('confidence_score', 'N/A')}")
                    logger.info(f"  - Reasoning plan steps: {len(step1_result.get('reasoning_plan', []))}")
                    
                    return step1_result
                    
                except (orjson.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"Failed to parse Step 1 response as JSON: {json_error}")
                    logger.debug(f"Raw response: {response_content}")
                    # Return fallback result
                    return {
                        "rephrased_question": question,
                        "intent_type": "unclear_intent",
                        "confidence_score": 0.0,
                        "reasoning": f"Error parsing Step 1 response: {str(json_error)}",
                        "required_data_columns": [],
                        "clarification_needed": "Unable to analyze question due to processing error",
                        "can_be_answered": False,
                        "feasibility_score": 0.0,
                        "missing_columns": [],
                        "available_alternatives": [],
                        "data_suggestions": "Error in Step 1 analysis",
                        "reasoning_plan": []
                    }
                
            except Exception as llm_error:
                logger.warning(f"LLM Step 1 analysis failed: {llm_error}")
                # Return fallback result
                return {
                    "rephrased_question": question,
                    "intent_type": "unclear_intent",
                    "confidence_score": 0.0,
                    "reasoning": f"Step 1 analysis failed: {str(llm_error)}",
                    "required_data_columns": [],
                    "clarification_needed": "Unable to analyze question due to LLM error",
                    "can_be_answered": False,
                    "feasibility_score": 0.0,
                    "missing_columns": [],
                    "available_alternatives": [],
                    "data_suggestions": "Error in Step 1 analysis",
                    "reasoning_plan": []
                }
            
        except Exception as e:
            logger.error(f"Error in Step 1 question analysis: {e}")
            return {
                "rephrased_question": question,
                "intent_type": "unsupported_analysis",
                "confidence_score": 0.0,
                "reasoning": f"Error in Step 1 analysis: {str(e)}",
                "required_data_columns": [],
                "clarification_needed": "Error occurred during question analysis",
                "can_be_answered": False,
                "feasibility_score": 0.0,
                "missing_columns": [],
                "available_alternatives": [],
                "data_suggestions": "Error in Step 1 analysis",
                "reasoning_plan": []
            }

    async def _step2_function_selection_and_planning(
        self,
        step1_output: Dict[str, Any],
        question: str,
        available_columns: List[str],
        dataframe_description: str = "",
        dataframe_summary: str = "",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        STEP 2: Use FunctionRetrieval to get relevant functions based on Step 1 output.
        
        Args:
            step1_output: Output from Step 1 (rephrased question, intent, reasoning plan)
            question: Original user question
            available_columns: List of available columns
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            project_id: Optional project ID for context retrieval
            
        Returns:
            Dictionary with selected function information
        """
        try:
            logger.info("Starting Step 2: Function selection using FunctionRetrieval...")
            
            # Extract key information from Step 1 output
            rephrased_question = step1_output.get("rephrased_question", question)
            intent_type = step1_output.get("intent_type", "unclear_intent")
            reasoning_plan = step1_output.get("reasoning_plan", [])
            confidence_score = step1_output.get("confidence_score", 0.0)
            
            logger.info(f"Step 1 output - Intent: {intent_type}, Confidence: {confidence_score}")
            logger.info(f"Step 1 output - Reasoning plan steps: {len(reasoning_plan)}")
            
            # Use FunctionRetrieval to get relevant functions
            try:
                function_retrieval_result = await self.function_retrieval.retrieve_relevant_functions(
                    question=question,
                    dataframe_description=dataframe_description,
                    dataframe_summary=dataframe_summary,
                    available_columns=available_columns,
                    project_id=project_id
                )
                
                logger.info(f"FunctionRetrieval completed successfully:")
                logger.info(f"  - Retrieved {len(function_retrieval_result.top_functions)} functions")
                logger.info(f"  - Confidence score: {function_retrieval_result.confidence_score}")
                logger.info(f"  - Suggested pipes: {function_retrieval_result.suggested_pipes}")
                
                # Convert FunctionRetrievalResult to the expected format
                function_names = []
                function_details = []
                specific_matches = []
                
                for func_match in function_retrieval_result.top_functions:
                    function_names.append(func_match.function_name)
                    
                    # Create function detail with complete specification
                    function_detail = {
                        "function_name": func_match.function_name,
                        "pipe_name": func_match.pipe_name,
                        "description": func_match.description,
                        "usage_description": func_match.usage_description,
                        "relevance_score": func_match.relevance_score,
                        "reasoning": func_match.reasoning,
                        "priority": 1,  # Default priority, could be enhanced later
                        "step_applicability": [],  # Could be enhanced based on reasoning plan
                        "data_requirements": [],  # Could be extracted from function definition
                        "expected_output": ""  # Could be enhanced based on function definition
                    }
                    
                    # Add complete function definition if available
                    if func_match.function_definition:
                        # Extract required and optional parameters from function definition
                        function_def = func_match.function_definition
                        
                        # Add required parameters
                        if "required_params" in function_def:
                            function_detail["required_params"] = function_def["required_params"]
                        else:
                            function_detail["required_params"] = []
                        
                        # Add optional parameters
                        if "optional_params" in function_def:
                            function_detail["optional_params"] = function_def["optional_params"]
                        else:
                            function_detail["optional_params"] = []
                        
                        # Add outputs
                        if "outputs" in function_def:
                            function_detail["outputs"] = function_def["outputs"]
                        else:
                            function_detail["outputs"] = {}
                        
                        # Add category
                        if "category" in function_def:
                            function_detail["category"] = function_def["category"]
                        
                        # Add any other fields from the function definition
                        for key, value in function_def.items():
                            if key not in ["required_params", "optional_params", "outputs", "category"]:
                                function_detail[key] = value
                        
                        logger.info(f"Added complete function definition for {func_match.function_name}")
                    else:
                        logger.warning(f"No function definition found for {func_match.function_name}")
                    
                    function_details.append(function_detail)
                    
                    # Mark as specific match if high relevance
                    if func_match.relevance_score >= 0.9:
                        specific_matches.append(func_match.function_name)
                
                # Sort by relevance score (highest first)
                function_details.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
                
                # Take top 5 functions
                top_functions = function_details[:5]
                top_function_names = [func["function_name"] for func in top_functions]
                
                logger.info(f"Step 2 completed successfully:")
                logger.info(f"  - Selected {len(top_function_names)} functions")
                logger.info(f"  - Function names: {top_function_names}")
                logger.info(f"  - Specific matches: {specific_matches}")
                
                return {
                    "function_names": top_function_names,
                    "function_details": top_functions,
                    "specific_matches": specific_matches,
                    "total_selected": len(function_retrieval_result.top_functions),
                    "analysis_complexity": "medium",  # Could be enhanced based on function types
                    "estimated_execution_time": "unknown",  # Could be enhanced based on function complexity
                    "potential_issues": [],  # Could be enhanced based on function requirements
                    "recommendations": [],  # Could be enhanced based on function capabilities
                    "function_selection_reasoning": function_retrieval_result.reasoning
                }
                
            except Exception as retrieval_error:
                logger.warning(f"FunctionRetrieval failed: {retrieval_error}")
                # Return fallback result - since reasoning plan no longer contains function names,
                # we'll use a basic set of common functions based on the intent type
                fallback_functions = []
                if intent_type == "metrics_calculation":
                    fallback_functions = ["Mean", "Sum", "Count", "GroupBy"]
                elif intent_type == "time_series_analysis":
                    fallback_functions = ["moving_average", "variance_analysis", "aggregate_by_time"]
                elif intent_type == "trend_analysis":
                    fallback_functions = ["calculate_growth_rates", "calculate_moving_average", "forecast_metric"]
                elif intent_type == "segmentation_analysis":
                    fallback_functions = ["run_kmeans", "run_dbscan", "run_rule_based"]
                elif intent_type == "cohort_analysis":
                    fallback_functions = ["calculate_retention", "form_time_cohorts", "calculate_conversion"]
                elif intent_type == "funnel_analysis":
                    fallback_functions = ["analyze_funnel", "analyze_user_paths", "compare_segments"]
                elif intent_type == "risk_analysis":
                    fallback_functions = ["calculate_var", "monte_carlo_simulation", "fit_distribution"]
                elif intent_type == "anomaly_detection":
                    fallback_functions = ["detect_statistical_outliers", "detect_contextual_anomalies"]
                elif intent_type == "operations_analysis":
                    fallback_functions = ["PercentChange", "BootstrapCI", "PowerAnalysis"]
                else:
                    fallback_functions = ["Mean", "Sum", "Count", "GroupBy", "PivotTable"]
                
                # Take first 5 functions
                unique_functions = fallback_functions[:5]
                
                return {
                    "function_names": unique_functions,
                    "function_details": [],
                    "specific_matches": [],
                    "total_selected": len(unique_functions),
                    "analysis_complexity": "medium",
                    "estimated_execution_time": "unknown",
                    "potential_issues": ["FunctionRetrieval failed, using fallback"],
                    "recommendations": ["Verify function selection manually"],
                    "function_selection_reasoning": f"Fallback selection due to FunctionRetrieval error: {str(retrieval_error)}"
                }
            
        except Exception as e:
            logger.error(f"Error in Step 2 function selection and planning: {e}")
            return {
                "function_names": [],
                "function_details": [],
                "specific_matches": [],
                "total_selected": 0,
                "analysis_complexity": "unknown",
                "estimated_execution_time": "unknown",
                "potential_issues": [f"Step 2 error: {str(e)}"],
                "recommendations": ["Check system configuration"],
                "function_selection_reasoning": f"Error in Step 2: {str(e)}"
            }

    async def _step3_pipeline_reasoning_planning(
        self,
        step1_output: Dict[str, Any],
        step2_output: Dict[str, Any],
        question: str,
        available_columns: List[str],
        dataframe_description: str = "",
        dataframe_summary: str = "",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        STEP 3: Create pipeline reasoning steps based on function definitions and parameters.
        
        This step takes the selected functions from Step 2 and creates natural language
        reasoning steps that define how to process inputs and execute the pipeline.
        For pipeline type functions, it merges similar steps when possible.
        
        Args:
            step1_output: Output from Step 1 (rephrased question, intent, reasoning plan)
            step2_output: Output from Step 2 (selected functions and their definitions)
            question: Original user question
            available_columns: List of available columns
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            project_id: Optional project ID for context retrieval
            
        Returns:
            Dictionary with pipeline reasoning plan only
        """
        try:
            logger.info("Starting Step 3: Pipeline reasoning planning...")
            
            # Extract key information from previous steps
            rephrased_question = step1_output.get("rephrased_question", question)
            intent_type = step1_output.get("intent_type", "unclear_intent")
            original_reasoning_plan = step1_output.get("reasoning_plan", [])
            
            function_details = step2_output.get("function_details", [])
            function_names = step2_output.get("function_names", [])
            specific_function_matches = step2_output.get("specific_matches", [])
            
            # Log Step 1 outputs for tracking purposes
            logger.info(f"Step 1 reasoning: {step1_output.get('reasoning', 'No reasoning')}")
            logger.info(f"Step 1 reasoning plan steps: {len(original_reasoning_plan)}")
            for i, step in enumerate(original_reasoning_plan):
                logger.info(f"  Step {i+1}: {step.get('step_title', 'Unknown')} - {step.get('step_description', 'No description')}")
            
            logger.info(f"Step 3 input - Intent: {intent_type}")
            logger.info(f"Step 3 input - Functions: {function_names}")
            logger.info(f"Step 3 input - Function details: {len(function_details)}")
            logger.info(f"Step 3 input - Specific matches: {specific_function_matches}")
            
            if not function_details:
                logger.warning("No function details available for Step 3")
                return {
                    "pipeline_reasoning_plan": []
                }
            
            # Create prompt for Step 3 pipeline reasoning
            step3_prompt = PromptTemplate(
                input_variables=[
                    "question", "rephrased_question", "intent_type", "original_reasoning_plan",
                    "function_details", "specific_function_matches", "available_columns", "dataframe_description", "dataframe_summary"
                ],
                template="""
You are an expert data pipeline architect performing STEP 3 of a multi-step analysis process.

### USER QUESTION ###
{question}

### REPHRASED QUESTION ###
{rephrased_question}

### ANALYSIS INTENT ###
{intent_type}

### ORIGINAL REASONING PLAN ###
{original_reasoning_plan}

### SELECTED FUNCTIONS ###
{function_details}

### SPECIFIC FUNCTION MATCHES (HIGH PRIORITY) ###
The following functions are EXACT matches for the user's question and should be prioritized:
{specific_function_matches}

### DATAFRAME CONTEXT ###
**Available Columns:** {available_columns}
**Description:** {dataframe_description}
**Summary:** {dataframe_summary}

### STEP 3 TASK ###
Create a detailed pipeline reasoning plan that:

1. **PRIORITIZE SPECIFIC MATCHES**: Use the specific function matches listed above as the PRIMARY functions for your pipeline steps
2. **ANALYZE FUNCTION DEFINITIONS**: Examine each function's required parameters, optional parameters, and outputs
3. **CREATE NATURAL LANGUAGE STEPS**: Convert function definitions into natural language reasoning steps
4. **PROCESS INPUTS PROPERLY**: Define how to process and prepare inputs for each function
5. **MERGE SIMILAR STEPS**: For pipeline type functions, merge similar steps when possible
6. **DEFINE EXECUTION FLOW**: Create a logical sequence of steps that the next agent can use to generate pipeline code
7. **HANDLE EMBEDDED FUNCTION PARAMETERS**: For functions like moving_apply_by_group that accept function parameters, specify when to use embedded pipeline expressions

**CRITICAL**: The specific function matches are EXACT matches for the user's question. You MUST use these functions in your pipeline reasoning plan, especially for the main analysis steps.

**CRITICAL EMBEDDED FUNCTION PARAMETER RULES**:
- For function input callable, if applicable, the function parameter should contain a complete pipeline expression
- Example: moving_apply_by_group(function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df()))
- This embeds the MetricsPipe Variance calculation within the TimeSeriesPipe moving_apply_by_group function
- Do NOT create separate pipelines for functions that should be embedded as parameters

### PIPELINE REASONING REQUIREMENTS ###
Each pipeline reasoning step should contain:
- step_number: Sequential number (1, 2, 3, etc.)
- step_title: Brief title describing the pipeline step
- step_description: Detailed natural language description of what this step does
- function_name: The specific function being used. **PRIORITIZE the specific function matches listed above** for the main analysis steps
- input_processing: How to process and prepare inputs for this function
- parameter_mapping: How to map available data to function parameters
- expected_output: What result or data transformation this step produces
- data_requirements: What data/columns are needed for this step
- considerations: Any important considerations or potential issues
- merge_with_previous: Whether this step can be merged with previous similar steps
- embedded_function_parameter: For functions like moving_apply_by_group, specify if a function parameter should contain an embedded pipeline expression (e.g., "function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df())")
- embedded_function_details: If embedded_function_parameter is true, specify the details of the embedded function (function name, parameters, pipe type)

**FUNCTION SELECTION PRIORITY**:
1. **FIRST CHOICE**: Use functions from the specific_function_matches list
2. **SECOND CHOICE**: Use other functions from the function_details that best match the step requirements
3. **LAST RESORT**: Use "None" only if no suitable function exists for data preparation or visualization steps

**EMBEDDED FUNCTION PARAMETER GUIDELINES**:
- **USE EMBEDDED PARAMETERS FOR**: moving_apply_by_group, aggregate_by_group, and similar functions that accept function parameters
- **EMBEDDED FUNCTION EXAMPLES**:
  - moving_apply_by_group with Variance: function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df())
  - moving_apply_by_group with Mean: function=(MetricsPipe.from_dataframe(...) | Mean(...) | to_df())
  - aggregate_by_group with Sum: function=(MetricsPipe.from_dataframe(...) | Sum(...) | to_df())
- **DO NOT EMBED FOR**: Direct function calls like Variance(), Mean(), Sum() that are used standalone
- **PIPE TYPE SEPARATION**: When embedding, ensure the embedded function uses the correct pipe type (MetricsPipe for Variance, etc.)

### MERGING STRATEGY ###
- For pipeline type functions, try to merge similar data preparation steps
- Keep separate steps when functions have significantly different purposes
- Consider data dependencies and execution order
- Maintain logical flow and readability

### OUTPUT FORMAT ###
Provide your response as a JSON object with only the pipeline_reasoning_plan:

{{
    "pipeline_reasoning_plan": [
        {{
            "step_number": 1,
            "step_title": "Data Preparation and Validation",
            "step_description": "Natural language description of what this step does",
            "function_name": "function_name",
            "input_processing": "How to process inputs for this function",
            "parameter_mapping": "How to map data to function parameters",
            "expected_output": "What this step produces",
            "data_requirements": ["column1", "column2"],
            "considerations": "Important considerations",
            "merge_with_previous": false,
            "embedded_function_parameter": false,
            "embedded_function_details": null
        }},
        {{
            "step_number": 2,
            "step_title": "Moving Apply with Embedded Variance",
            "step_description": "Apply moving variance calculation by group with embedded Variance function",
            "function_name": "moving_apply_by_group",
            "input_processing": "Prepare time series data with group columns",
            "parameter_mapping": "Map columns to function parameters, embed Variance as function parameter",
            "expected_output": "Rolling variance values by group over time",
            "data_requirements": ["Transactional value", "Project", "Cost center", "Department", "Date"],
            "considerations": "Ensure proper time column format and handle missing values",
            "merge_with_previous": false,
            "embedded_function_parameter": true,
            "embedded_function_details": {{
                "embedded_function": "Variance",
                "embedded_pipe": "MetricsPipe",
                "embedded_parameters": {{"variable": "Transactional value"}},
                "embedded_output": "variance_Transactional value"
            }}
        }}
    ]
}}

Focus on creating clear, actionable reasoning steps that the next agent can use to generate actual pipeline code. Each step should be specific enough to guide code generation but general enough to be flexible.

**REMEMBER**: The specific function matches are the most relevant functions for this analysis. Use them as the primary functions in your pipeline reasoning plan.

**SPECIFIC EXAMPLE - Variance + moving_apply_by_group**:
When the user asks for "variance with moving apply by group", the reasoning plan should specify:
- Step 1: Use moving_apply_by_group as the primary function
- embedded_function_parameter: true
- embedded_function_details: Specify Variance as the embedded function with MetricsPipe
- This tells the code generation agent to create: function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df())
- NOT separate pipelines for Variance and moving_apply_by_group
"""
            )
            
            # Format function details for the prompt
            function_details_text = ""
            for i, func in enumerate(function_details, 1):
                function_details_text += f"Function {i}: {func.get('function_name', 'Unknown')}\n"
                function_details_text += f"  Pipe: {func.get('pipe_name', 'Unknown')}\n"
                function_details_text += f"  Description: {func.get('description', 'No description')}\n"
                function_details_text += f"  Usage: {func.get('usage_description', 'No usage info')}\n"
                
                # Add required parameters
                required_params = func.get('required_params', [])
                if required_params:
                    function_details_text += f"  Required Parameters: {required_params}\n"
                
                # Add optional parameters
                optional_params = func.get('optional_params', [])
                if optional_params:
                    function_details_text += f"  Optional Parameters: {optional_params}\n"
                
                # Add outputs
                outputs = func.get('outputs', {})
                if outputs:
                    function_details_text += f"  Outputs: {outputs}\n"
                
                # Add category
                category = func.get('category', 'Unknown')
                function_details_text += f"  Category: {category}\n"
                
                function_details_text += "\n"
            
            # Format specific function matches for the prompt
            specific_matches_text = ""
            if specific_function_matches:
                specific_matches_text = "**HIGH PRIORITY FUNCTIONS (EXACT MATCHES):**\n"
                for i, func_name in enumerate(specific_function_matches, 1):
                    # Find the function details for this specific match
                    func_detail = None
                    for func in function_details:
                        if func.get('function_name') == func_name:
                            func_detail = func
                            break
                    
                    if func_detail:
                        specific_matches_text += f"{i}. **{func_name}** ({func_detail.get('pipe_name', 'Unknown')})\n"
                        specific_matches_text += f"   Description: {func_detail.get('description', 'No description')}\n"
                        specific_matches_text += f"   Usage: {func_detail.get('usage_description', 'No usage info')}\n"
                        specific_matches_text += f"   Category: {func_detail.get('category', 'Unknown')}\n"
                        specific_matches_text += f"   Type: {func_detail.get('type_of_operation', 'Unknown')}\n\n"
                    else:
                        specific_matches_text += f"{i}. **{func_name}** (details not found)\n\n"
            else:
                specific_matches_text = "No specific function matches identified."
            
            # Format original reasoning plan
            original_plan_text = ""
            for step in original_reasoning_plan:
                original_plan_text += f"Step {step.get('step_number', '?')}: {step.get('step_title', 'Unknown')}\n"
                original_plan_text += f"  Description: {step.get('step_description', 'No description')}\n"
                original_plan_text += f"  Data Requirements: {step.get('data_requirements', [])}\n"
                original_plan_text += f"  Expected Outcome: {step.get('expected_outcome', 'Unknown')}\n\n"
            
            # Get LLM response for Step 3
            try:
                # Create the chain for Step 3 analysis
                chain = step3_prompt | self.llm
                
                # Generate response
                result = await chain.ainvoke({
                    "question": question,
                    "rephrased_question": rephrased_question,
                    "intent_type": intent_type,
                    "original_reasoning_plan": original_plan_text,
                    "function_details": function_details_text,
                    "specific_function_matches": specific_matches_text,
                    "available_columns": available_columns,
                    "dataframe_description": dataframe_description,
                    "dataframe_summary": dataframe_summary
                })
                
                # Extract content from AIMessage
                response_content = result.content if hasattr(result, 'content') else str(result)
                
                # Remove markdown code blocks if present
                if response_content.startswith("```json"):
                    response_content = response_content.split("```json")[1]
                if response_content.endswith("```"):
                    response_content = response_content.rsplit("```", 1)[0]
                
                # Clean the response content - remove JavaScript-style comments
                import re
                # Remove single-line comments (// ...)
                response_content = re.sub(r'//.*?$', '', response_content, flags=re.MULTILINE)
                # Remove multi-line comments (/* ... */)
                response_content = re.sub(r'/\*.*?\*/', '', response_content, flags=re.DOTALL)
                # Clean up any trailing commas before closing braces/brackets
                response_content = re.sub(r',(\s*[}\]])', r'\1', response_content)
                
                # Parse JSON response
                try:
                    step3_result = orjson.loads(response_content.strip())
                    logger.info("Step 3 LLM response parsed successfully")
                except Exception as parse_error:
                    logger.warning(f"Failed to parse Step 3 JSON response: {parse_error}")
                    logger.warning(f"Raw response: {response_content}")
                    
                    # Create fallback result
                    step3_result = {
                        "pipeline_reasoning_plan": []
                    }
                
                logger.info(f"Step 3 completed successfully:")
                logger.info(f"  - Pipeline steps: {len(step3_result.get('pipeline_reasoning_plan', []))}")
                
                return step3_result
                
            except Exception as llm_error:
                logger.error(f"LLM error in Step 3: {llm_error}")
                return {
                    "pipeline_reasoning_plan": []
                }
            
        except Exception as e:
            logger.error(f"Error in Step 3 pipeline reasoning planning: {e}")
            return {
                "pipeline_reasoning_plan": []
            }


# Example usage
if __name__ == "__main__":
    import asyncio
    
    
