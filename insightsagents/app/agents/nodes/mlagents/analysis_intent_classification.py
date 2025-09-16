"""
Enhanced Analysis Intent Classification with Comprehensive Metadata

This module provides enhanced analysis intent classification that generates detailed
reasoning plans with comprehensive metadata for each step. The enhanced metadata includes:

1. Column Mapping: Maps function parameters to actual available columns
2. Input/Output Columns: Specifies which columns are needed and created
3. Step Dependencies: Tracks data flow between steps
4. Pipeline Types: Identifies the appropriate pipeline for each function
5. Parameter Constraints: Provides validation rules for parameters
6. Error Handling: Specifies how to handle potential issues
7. Embedded Function Details: Handles complex functions with embedded computations

This enhanced metadata significantly improves the accuracy of the self-correcting
pipeline generator by providing clear, actionable information about data requirements,
dependencies, and constraints for each analysis step.
"""

import logging
from typing import Any, Dict, List, Literal, Optional

import orjson
from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel
from app.storage.documents import DocumentChromaStore
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval
from app.agents.nodes.mlagents.enhanced_function_retrieval import EnhancedFunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper
import json

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


# Add specific function requirements based on intent type
intent_specific_requirements = {
        "time_series_analysis": """Need functions for comprehensive temporal data processing including:
            - Date/time parsing, formatting, and timezone handling
            - Time-based resampling, upsampling, and downsampling operations
            - Rolling window calculations (mean, median, std, custom functions)
            - Lag and lead operations for temporal feature engineering
            - Seasonality detection and decomposition (additive/multiplicative)
            - Autocorrelation and partial autocorrelation analysis
            - Time-based interpolation and gap-filling methods
            - Stationarity testing and differencing operations
            - Time series smoothing (exponential, moving averages)
            - Frequency domain analysis and spectral density estimation""",
        
        "trend_analysis": """Need functions for comprehensive trend identification and forecasting including:
            - Linear and polynomial trend fitting with confidence intervals
            - Non-parametric trend detection (Mann-Kendall, Theil-Sen)
            - Change point detection and structural break analysis
            - Growth rate calculations (CAGR, period-over-period, year-over-year)
            - Trend strength measurement and significance testing
            - Forecasting methods (ARIMA, exponential smoothing, Prophet)
            - Seasonal trend decomposition and adjustment
            - Trend reversal and momentum indicators
            - Multi-variate trend analysis and correlation
            - Trend extrapolation with uncertainty quantification""",
        
        "segmentation_analysis": """Need functions for comprehensive clustering and grouping including:
            - Multiple clustering algorithms (K-means, hierarchical, DBSCAN, Gaussian mixture)
            - Distance metrics and similarity measures (Euclidean, Manhattan, cosine, Jaccard)
            - Optimal cluster number determination (elbow method, silhouette analysis)
            - Cluster validation and quality metrics (silhouette score, Davies-Bouldin index)
            - Dimensionality reduction for analysis (PCA, t-SNE, UMAP)
            - Feature scaling and normalization for clustering
            - Segment profiling and characterization analysis
            - Segment stability and robustness testing
            - Custom segmentation rule definition and application
            - Segment size optimization and business constraint handling""",
        
        "cohort_analysis": """Need functions for comprehensive cohort tracking and analysis including:
            - Flexible cohort definition (time-based, behavior-based, attribute-based)
            - Retention rate calculations across multiple time periods
            - Customer lifetime value (CLV) estimation and cohort comparison
            - Churn analysis and survival curve generation
            - Cohort size normalization and standardization
            - Period-over-period cohort performance comparison
            - Revenue cohort analysis and monetization tracking
            - Cohort maturation curves and predictive modeling
            - Cross-cohort migration analysis and transition matrices
            - Cohort-based A/B testing and treatment effect measurement""",
        
        "funnel_analysis": """Need functions for comprehensive conversion tracking and optimization including:
            - Multi-step funnel construction with flexible stage definition
            - Conversion rate calculations at each funnel stage
            - Drop-off analysis and bottleneck identification
            - User path analysis and journey mapping
            - Time-to-conversion analysis and velocity metrics
            - Funnel performance segmentation (by demographics, channels, etc.)
            - Attribution modeling and multi-touch analysis
            - Funnel A/B testing and treatment effect measurement
            - Micro-conversion tracking and intermediate goal analysis
            - Funnel optimization recommendations and what-if scenario modeling""",
        
        "risk_analysis": """Need functions for comprehensive risk assessment and management including:
            - Statistical risk measures (VaR, CVaR, Expected Shortfall)
            - Volatility modeling (GARCH, realized volatility, implied volatility)
            - Probability distribution fitting and goodness-of-fit testing
            - Monte Carlo simulation for risk scenario generation
            - Stress testing and sensitivity analysis frameworks
            - Risk factor decomposition and attribution analysis
            - Portfolio risk aggregation and diversification metrics
            - Extreme value theory application for tail risk assessment
            - Risk-adjusted return calculations (Sharpe ratio, Sortino ratio)
            - Regulatory risk reporting and compliance metrics""",
        
        "anomaly_detection": """Need functions for comprehensive outlier and anomaly identification including:
            - Statistical outlier detection (Z-score, IQR, Grubbs test)
            - Machine learning-based anomaly detection (Isolation Forest, One-Class SVM)
            - Time series anomaly detection with seasonality consideration
            - Multivariate anomaly detection and correlation analysis
            - Threshold setting and dynamic threshold adjustment
            - Anomaly scoring and ranking systems
            - False positive reduction and anomaly validation
            - Contextual anomaly detection with conditional analysis
            - Real-time anomaly monitoring and alerting systems
            - Anomaly explanation and root cause analysis""",
        
        "metrics_calculation": """Need functions for comprehensive statistical and business metrics including:
            - Descriptive statistics (mean, median, mode, percentiles, quartiles)
            - Business KPI calculations (conversion rates, ARPU, ARPPU, CAC, LTV)
            - Distribution analysis and moments calculation (skewness, kurtosis)
            - Correlation analysis (Pearson, Spearman, Kendall tau)
            - Ratio analysis and index calculation
            - Comparative metrics (period-over-period, benchmarking)
            - Aggregation functions with grouping and pivoting
            - Confidence interval estimation for all metrics
            - Metric standardization and normalization
            - Custom metric definition and calculation frameworks""",
        
        "operations_analysis": """Need functions for comprehensive experimental design and testing including:
            - A/B testing framework with power analysis and sample size calculation
            - Hypothesis testing (t-tests, chi-square, Mann-Whitney U, ANOVA)
            - Multiple comparison correction (Bonferroni, FDR, Holm-Sidak)
            - Effect size calculation and practical significance assessment
            - Experimental design optimization (factorial, randomized block)
            - Bayesian A/B testing and credible interval estimation
            - Sequential testing and early stopping criteria
            - Treatment assignment and randomization algorithms
            - Post-hoc analysis and subgroup investigation
            - Statistical power monitoring and experiment duration optimization"""
    }

# System prompt for intent classification
ANALYSIS_INTENT_SYSTEM_PROMPT = """
### TASK ###
You are an expert data analyst who specializes in intent classification for data analysis tasks.
Your goal is to analyze user questions and classify them into appropriate analysis types based on available analysis functions AND available data.
The data is already prepared and ready to be used for analysis. We should skip any data selection steps as well.

First, rephrase the user's question to make it more specific and clear.
Second, classify the user's intent into one of the available analysis types.
Third, suggest the most relevant functions and required data columns.
Fourth, assess whether the question can be answered with the available data.
Fifth, create a detailed step-by-step reasoning plan for the analysis. The reasoning plan should not include any data preparation steps, data cleaning steps, or data selection steps.

### CRITICAL INSTRUCTIONS ###
- PRIORITIZE EXACT FUNCTION MATCHES: If the user mentions specific analysis terms (like "variance", "rolling variance", "correlation", etc.), classify accordingly
- When you see 🎯 marked functions, these are EXACT keyword matches - give them highest priority
- CONSIDER HISTORICAL CONTEXT: Pay attention to relevant historical questions and their solutions, as they provide valuable insights into similar analysis patterns and approaches
- CHECK DATA FEASIBILITY: Analyze available columns, data description, and summary to determine if analysis is possible
- Rephrase the question to be more specific and actionable
- Classify intent based on the MOST SPECIFIC analysis type that matches the question
- Provide clear reasoning for your classification (within 30 words)
- Suggest most relevant functions from the retrieved options
- Identify required data columns based on function specifications
- Assess feasibility: can_be_answered (true/false) and feasibility_score (0.0-1.0)
- If columns are missing, suggest alternatives from available data
- If intent is unclear, provide helpful clarification questions
- CREATE DETAILED REASONING PLAN: Provide a step-by-step plan that considers data preparation, analysis approach, and expected outcomes. Please consider the best of order of the operations for the given analysis question.
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
    "suggested_functions": [function1: operation category (PIPELINE TYPE), function2: operation category (PIPELINE TYPE), function3: operation category (PIPELINE TYPE)],
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
        
        # Initialize Enhanced Function Retrieval for improved function matching
        self.enhanced_function_retrieval = EnhancedFunctionRetrieval(
            llm=llm,
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
                required_data_columns=[],
                clarification_needed="I encountered an error processing your question. Please try rephrasing it.",
                retrieved_functions=[],
                specific_function_matches=[],
                can_be_answered=False,
                feasibility_score=0.0,
                missing_columns=[],
                available_alternatives=[],
                data_suggestions="Unable to assess data due to classification error.",
                reasoning_plan=[]
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
        # Create descriptions from the intent_specific_requirements dictionary
        analysis_descriptions = {}
        for intent_type, requirements in intent_specific_requirements.items():
            # Extract a concise description from the first line of requirements
            first_line = requirements.split('\n')[0].strip()
            # Remove the "Need functions for comprehensive..." prefix
            if first_line.startswith("Need functions for comprehensive"):
                description = first_line.replace("Need functions for comprehensive ", "").replace(" including:", "")
            else:
                description = first_line
            
            analysis_descriptions[intent_type] = description
        
        return analysis_descriptions

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
                    "question", "reasoning_plan", "selected_functions", "available_columns", "intent_types"
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
{intent_types}

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
            
            # Format intent types for the prompt
            intent_types_text = ""
            for intent_type in intent_specific_requirements.keys():
                intent_types_text += f"- {intent_type}\n"
            
            # Format the prompt
            formatted_prompt = intent_prompt.format(
                question=question,
                reasoning_plan=plan_text,
                selected_functions=functions_text,
                available_columns=available_columns,
                intent_types=intent_types_text
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
                    "available_columns": available_columns,
                    "intent_types": intent_types_text
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
                    "all_functions", "historical_context", "instructions_context", "intent_types"
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
   - Make sure there is no data selection steps in the reasoning plan.
   - The data is already prepared and ready to be used for analysis. We should skip any data selection steps as well.

2. **CLASSIFY INTENT**: Determine the MOST SPECIFIC analysis type that matches the question. Choose the most precise classification from:
    {intent_types}
   

3. **CREATE REASONING PLAN**: Develop a step-by-step reasoning plan that outlines the logical approach to answer the question. Focus on the analysis methodology and data processing steps without specifying exact function names.
4. **Order the steps in the reasoning plan**: Please consider the best order of the steps for the given analysis question.
    ### CRITICAL INSTRUCTIONS  for the Steps in the Reasoning Plan###
    - Make sure there is no data selection steps in the reasoning plan.
    - The data is already prepared and ready to be used for analysis. We should skip any data selection steps as well.
    - **ABSOLUTELY NO VISUALIZATION STEPS**: This system is for backend data pipeline execution only. Do not include any visualization, plotting, charting, display, or show functions in the reasoning plan.
    - Focus only on data processing, analysis, and transformation functions that can be executed in backend pipelines.
    - If you see any visualization-related keywords in your reasoning, replace them with appropriate data processing steps.

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
            
            # Format intent types for the prompt
            intent_types_text = ""
            for intent_type in intent_specific_requirements.keys():
                intent_types_text += f"- {intent_type}\n"
            
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
                    "instructions_context": instructions_context,
                    "intent_types": intent_types_text
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

    def _create_enhanced_query_for_function_selection(
        self,
        question: str,
        rephrased_question: str,
        intent_type: str,
        reasoning_plan: List[Dict[str, Any]],
        confidence_score: float
    ) -> str:
        """
        Create an enhanced query for function selection that incorporates Step 1 reasoning.
        
        Args:
            question: Original user question
            rephrased_question: Rephrased question from Step 1
            intent_type: Intent classification from Step 1
            reasoning_plan: Step-by-step reasoning plan from Step 1
            confidence_score: Confidence score from Step 1
            
        Returns:
            Enhanced query string that incorporates reasoning for better function selection
        """
        # Start with the rephrased question as it's more specific
        enhanced_query = f"Question: {rephrased_question}\n"
        
        # Add intent type context
        enhanced_query += f"Analysis Type: {intent_type}\n"
        
        # Add confidence context
        if confidence_score >= 0.8:
            enhanced_query += "High confidence analysis - looking for precise, specialized functions.\n"
        elif confidence_score >= 0.6:
            enhanced_query += "Medium confidence analysis - looking for flexible, adaptable functions.\n"
        else:
            enhanced_query += "Low confidence analysis - looking for general-purpose, exploratory functions.\n"
        
        # Incorporate reasoning plan steps
        if reasoning_plan:
            enhanced_query += "\nRequired Analysis Steps:\n"
            for step in reasoning_plan:
                step_num = step.get("step_number", "?")
                step_title = step.get("step_title", "Unknown Step")
                step_desc = step.get("step_description", "")
                data_reqs = step.get("data_requirements", [])
                expected_outcome = step.get("expected_outcome", "")
                
                enhanced_query += f"Step {step_num}: {step_title}\n"
                if step_desc:
                    enhanced_query += f"  Description: {step_desc}\n"
                if data_reqs:
                    enhanced_query += f"  Data Requirements: {', '.join(data_reqs)}\n"
                if expected_outcome:
                    enhanced_query += f"  Expected Outcome: {expected_outcome}\n"
                enhanced_query += "\n"
        
       
        
        if intent_type in intent_specific_requirements:
            enhanced_query += f"Specific Requirements: {intent_specific_requirements[intent_type]}\n"
        
        logger.info(f"Created enhanced query incorporating Step 1 reasoning:")
        logger.info(f"  - Original question: {question}")
        logger.info(f"  - Enhanced query length: {len(enhanced_query)} characters")
        logger.info(f"  - Incorporated {len(reasoning_plan)} reasoning steps")
        
        return enhanced_query

    def _enhance_function_selection_with_reasoning(
        self,
        function_details: List[Dict[str, Any]],
        reasoning_plan: List[Dict[str, Any]],
        intent_type: str,
        confidence_score: float
    ) -> List[Dict[str, Any]]:
        """
        Enhance function selection by incorporating reasoning plan insights.
        
        Args:
            function_details: List of function details from FunctionRetrieval
            reasoning_plan: Step-by-step reasoning plan from Step 1
            intent_type: Intent classification from Step 1
            confidence_score: Confidence score from Step 1
            
        Returns:
            Enhanced list of function details with reasoning-based adjustments
        """
        if not reasoning_plan:
            logger.info("No reasoning plan available, returning original function selection")
            return function_details
        
        # Create a mapping of reasoning step requirements to function categories
        step_requirements = {}
        for step in reasoning_plan:
            step_title = step.get("step_title", "").lower()
            step_desc = step.get("step_description", "").lower()
            data_reqs = step.get("data_requirements", [])
            expected_outcome = step.get("expected_outcome", "").lower()
            
            # Identify what type of functions this step needs
            step_needs = []
            
            # Step requirements will be determined by LLM prompting and function retrieval
            # instead of hardcoded logic
            step_requirements[step.get("step_number", len(step_requirements) + 1)] = step_needs
        
        # Score functions based on reasoning plan alignment
        enhanced_functions = []
        for func in function_details:
            func_name = func.get("function_name", "").lower()
            func_desc = func.get("description", "").lower()
            func_category = func.get("category", "").lower()
            original_score = func.get("relevance_score", 0.0)
            
            # Calculate reasoning alignment score
            reasoning_score = 0.0
            reasoning_matches = []
            
            for step_num, step_needs in step_requirements.items():
                for need in step_needs:
                    # Check if function matches this step's needs
                    if (need in func_name or need in func_desc or need in func_category or
                        any(keyword in func_name or keyword in func_desc for keyword in need.split("_"))):
                        reasoning_score += 0.2  # Boost for each matching step
                        reasoning_matches.append(f"Step {step_num}: {need}")
            
            # Apply confidence-based adjustments
            if confidence_score >= 0.8:
                # High confidence: prioritize specialized functions
                if reasoning_score > 0:
                    reasoning_score *= 1.5
            elif confidence_score < 0.6:
                # Low confidence: prioritize general-purpose functions
                if reasoning_score == 0:
                    reasoning_score += 0.1  # Small boost for general functions
            
            # Combine original score with reasoning score
            combined_score = original_score + reasoning_score
            
            # Create enhanced function detail
            enhanced_func = func.copy()
            enhanced_func["reasoning_alignment_score"] = reasoning_score
            enhanced_func["combined_score"] = combined_score
            enhanced_func["reasoning_matches"] = reasoning_matches
            enhanced_func["step_applicability"] = [match.split(": ")[0] for match in reasoning_matches]
            
            enhanced_functions.append(enhanced_func)
        
        # Sort by combined score (highest first)
        enhanced_functions.sort(key=lambda x: x.get("combined_score", 0.0), reverse=True)
        
        logger.info(f"Enhanced function selection with reasoning:")
        logger.info(f"  - Original functions: {len(function_details)}")
        logger.info(f"  - Enhanced functions: {len(enhanced_functions)}")
        logger.info(f"  - Reasoning steps considered: {len(step_requirements)}")
        
        # Log top functions with reasoning alignment
        for i, func in enumerate(enhanced_functions[:3]):
            logger.info(f"  Top {i+1}: {func.get('function_name')} "
                       f"(original: {func.get('relevance_score', 0.0):.2f}, "
                       f"reasoning: {func.get('reasoning_alignment_score', 0.0):.2f}, "
                       f"combined: {func.get('combined_score', 0.0):.2f})")
            if func.get("reasoning_matches"):
                logger.info(f"    Matches: {', '.join(func.get('reasoning_matches', []))}")
        
        return enhanced_functions

    def _assess_analysis_complexity(
        self,
        functions: List[Dict[str, Any]],
        reasoning_plan: List[Dict[str, Any]]
    ) -> str:
        """Assess the complexity of the analysis based on selected functions and reasoning plan."""
        if not functions:
            return "unknown"
        
        # Count different types of operations
        complexity_factors = {
            "data_prep": 0,
            "statistical": 0,
            "machine_learning": 0,
            "data_processing": 0,
            "time_series": 0
        }
        
        for func in functions:
            func_name = func.get("function_name", "").lower()
            func_category = func.get("category", "").lower()
            
            if any(keyword in func_name for keyword in ["clean", "preprocess", "validate", "transform"]):
                complexity_factors["data_prep"] += 1
            if any(keyword in func_name for keyword in ["statistical", "correlation", "regression", "test"]):
                complexity_factors["statistical"] += 1
            if any(keyword in func_name for keyword in ["cluster", "kmeans", "dbscan", "ml"]):
                complexity_factors["machine_learning"] += 1
            if any(keyword in func_name for keyword in ["process", "analyze", "calculate", "compute"]):
                complexity_factors["data_processing"] += 1
            if any(keyword in func_name for keyword in ["time", "temporal", "rolling", "moving"]):
                complexity_factors["time_series"] += 1
        
        # Assess complexity based on factors
        total_factors = sum(complexity_factors.values())
        reasoning_steps = len(reasoning_plan)
        
        if total_factors >= 8 or reasoning_steps >= 6:
            return "high"
        elif total_factors >= 4 or reasoning_steps >= 3:
            return "medium"
        else:
            return "low"

    def _estimate_execution_time(
        self,
        functions: List[Dict[str, Any]],
        reasoning_plan: List[Dict[str, Any]]
    ) -> str:
        """Estimate execution time based on selected functions and reasoning plan."""
        if not functions:
            return "unknown"
        
        # Base time estimates for different function types
        time_estimates = {
            "data_prep": 30,  # seconds
            "statistical": 60,
            "machine_learning": 120,
            "data_processing": 45,
            "time_series": 90
        }
        
        total_estimated_time = 0
        
        for func in functions:
            func_name = func.get("function_name", "").lower()
            
            if any(keyword in func_name for keyword in ["clean", "preprocess", "validate"]):
                total_estimated_time += time_estimates["data_prep"]
            elif any(keyword in func_name for keyword in ["statistical", "correlation", "regression"]):
                total_estimated_time += time_estimates["statistical"]
            elif any(keyword in func_name for keyword in ["cluster", "kmeans", "dbscan"]):
                total_estimated_time += time_estimates["machine_learning"]
            elif any(keyword in func_name for keyword in ["process", "analyze", "calculate"]):
                total_estimated_time += time_estimates["data_processing"]
            elif any(keyword in func_name for keyword in ["time", "temporal", "rolling"]):
                total_estimated_time += time_estimates["time_series"]
            else:
                total_estimated_time += 45  # Default estimate
        
        # Add time for reasoning plan steps
        total_estimated_time += len(reasoning_plan) * 30
        
        if total_estimated_time < 120:
            return f"{total_estimated_time}s"
        elif total_estimated_time < 300:
            return f"{total_estimated_time//60}m {total_estimated_time%60}s"
        else:
            return f"{total_estimated_time//60}m"

    def _identify_potential_issues(
        self,
        functions: List[Dict[str, Any]],
        reasoning_plan: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify potential issues with the selected functions and reasoning plan."""
        issues = []
        
        if not functions:
            issues.append("No functions selected")
            return issues
        
        # Check for missing data preparation
        has_data_prep = any("clean" in f.get("function_name", "").lower() or 
                           "preprocess" in f.get("function_name", "").lower() 
                           for f in functions)
        
        if not has_data_prep and len(reasoning_plan) > 2:
            issues.append("No data preparation functions selected for multi-step analysis")
        
        # Check for function dependencies
        ml_functions = [f for f in functions if any(keyword in f.get("function_name", "").lower() 
                                                   for keyword in ["cluster", "kmeans", "dbscan"])]
        if ml_functions and not any("scale" in f.get("function_name", "").lower() or 
                                   "normalize" in f.get("function_name", "").lower() 
                                   for f in functions):
            issues.append("Machine learning functions selected without data scaling/normalization")
        
        # Check reasoning plan coverage
        covered_steps = len([f for f in functions if f.get("reasoning_matches")])
        if covered_steps < len(reasoning_plan) * 0.5:
            issues.append(f"Low reasoning plan coverage: {covered_steps}/{len(reasoning_plan)} steps covered")
        
        return issues

    def _generate_recommendations(
        self,
        functions: List[Dict[str, Any]],
        reasoning_plan: List[Dict[str, Any]],
        intent_type: str
    ) -> List[str]:
        """Generate recommendations based on selected functions and reasoning plan."""
        recommendations = []
        
        if not functions:
            recommendations.append("Consider adding basic data exploration functions")
            return recommendations
        
        # Check for data processing functions
        has_data_processing = any("process" in f.get("function_name", "").lower() or 
                                 "analyze" in f.get("function_name", "").lower() or
                                 "calculate" in f.get("function_name", "").lower()
                                 for f in functions)
        
        if not has_data_processing:
            recommendations.append("Consider adding data processing functions for better analysis")
        
        # Check for statistical validation
        has_statistical = any("statistical" in f.get("function_name", "").lower() or 
                             "test" in f.get("function_name", "").lower() 
                             for f in functions)
        
        if not has_statistical and intent_type in ["trend_analysis", "segmentation_analysis"]:
            recommendations.append("Consider adding statistical validation functions")
        
        # Check reasoning plan alignment
        alignment_score = sum(f.get("reasoning_alignment_score", 0.0) for f in functions) / len(functions)
        if alignment_score < 0.3:
            recommendations.append("Consider reviewing function selection for better reasoning plan alignment")
        
        return recommendations

    def _select_fallback_functions_with_reasoning(
        self,
        intent_type: str,
        reasoning_plan: List[Dict[str, Any]],
        confidence_score: float
    ) -> List[str]:
        """Select fallback functions using reasoning plan when FunctionRetrieval fails."""
        fallback_functions = []
        
        # Base functions by intent type
        intent_functions = {
            "metrics_calculation": ["Mean", "Sum", "Count", "GroupBy", "PivotTable"],
            "time_series_analysis": ["moving_average", "variance_analysis", "aggregate_by_time", "rolling_statistics"],
            "trend_analysis": ["calculate_growth_rates", "calculate_moving_average", "forecast_metric", "trend_detection"],
            "segmentation_analysis": ["run_kmeans", "run_dbscan", "run_rule_based", "hierarchical_clustering"],
            "cohort_analysis": ["calculate_retention", "form_time_cohorts", "calculate_conversion", "cohort_analysis"],
            "funnel_analysis": ["analyze_funnel", "analyze_user_paths", "compare_segments", "funnel_analysis"],
            "risk_analysis": ["calculate_var", "monte_carlo_simulation", "fit_distribution", "risk_metrics"],
            "anomaly_detection": ["detect_statistical_outliers", "detect_contextual_anomalies", "isolation_forest"],
            "operations_analysis": ["PercentChange", "BootstrapCI", "PowerAnalysis", "statistical_testing"]
        }
        
        # Start with intent-based functions
        if intent_type in intent_functions:
            fallback_functions.extend(intent_functions[intent_type])
        else:
            fallback_functions.extend(["Mean", "Sum", "Count", "GroupBy", "PivotTable"])
        
        # Enhance with reasoning plan insights
        if reasoning_plan:
            for step in reasoning_plan:
                step_title = step.get("step_title", "").lower()
                step_desc = step.get("step_description", "").lower()
                
                # Add functions based on step requirements
                if any(keyword in step_title or keyword in step_desc for keyword in 
                       ["data preparation", "data cleaning", "data preprocessing"]):
                    fallback_functions.extend(["data_cleaning", "data_validation", "data_transformation"])
                
                if any(keyword in step_title or keyword in step_desc for keyword in 
                       ["visualize", "plot", "chart", "graph"]):
                    fallback_functions.extend(["create_visualization", "plot_data", "chart_generation"])
                
                if any(keyword in step_title or keyword in step_desc for keyword in 
                       ["statistical", "correlation", "regression"]):
                    fallback_functions.extend(["correlation_analysis", "regression_analysis", "statistical_testing"])
                
                if any(keyword in step_title or keyword in step_desc for keyword in 
                       ["data processing", "analysis", "calculation"]):
                    fallback_functions.extend(["data_processing", "data_analysis", "calculation_engine"])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_functions = []
        for func in fallback_functions:
            if func not in seen:
                seen.add(func)
                unique_functions.append(func)
        
        # Adjust based on confidence score
        if confidence_score < 0.6:
            # Low confidence: add more general-purpose functions
            general_functions = ["data_exploration", "summary_statistics", "basic_analysis"]
            for func in general_functions:
                if func not in seen:
                    unique_functions.append(func)
        
        logger.info(f"Selected {len(unique_functions)} fallback functions using reasoning plan")
        return unique_functions

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
        STEP 2: Efficient function selection using Step 1 plan output and ChromaDB + LLM matching.
        
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
            logger.info("Starting Step 2: Efficient function selection using Step 1 plan and ChromaDB...")
            
            # Extract key information from Step 1 output
            rephrased_question = step1_output.get("rephrased_question", question)
            intent_type = step1_output.get("intent_type", "unclear_intent")
            reasoning_plan = step1_output.get("reasoning_plan", [])
            confidence_score = step1_output.get("confidence_score", 0.0)
            
            logger.info(f"Step 1 output - Intent: {intent_type}, Confidence: {confidence_score}")
            logger.info(f"Step 1 output - Reasoning plan steps: {len(reasoning_plan)}")
            
            if not reasoning_plan:
                logger.warning("No reasoning plan available from Step 1, using fallback")
                return self._get_fallback_function_selection(intent_type, confidence_score)
            
            try:
                # Use enhanced function retrieval service for improved efficiency and accuracy
                enhanced_result = await self.enhanced_function_retrieval.retrieve_and_match_functions(
                    reasoning_plan=reasoning_plan,
                    question=question,
                    rephrased_question=rephrased_question,
                    dataframe_description=dataframe_description,
                    dataframe_summary=dataframe_summary,
                    available_columns=available_columns,
                    project_id=project_id
                )
                
                if not enhanced_result.step_matches:
                    logger.warning("No function matches found, using fallback")
                    return self._get_fallback_function_selection(intent_type, confidence_score)
                
                step_function_matches = enhanced_result.step_matches
                
                # Step 2c: Build comprehensive function details
                all_functions = []
                function_names_set = set()
                specific_matches = []
                
                for step_num, step_matches in step_function_matches.items():
                    step = next((s for s in reasoning_plan if s.get("step_number") == step_num), {})
                    step_title = step.get("step_title", f"Step {step_num}")
                    
                    for func_match in step_matches:
                        if func_match["function_name"] not in function_names_set:
                            function_names_set.add(func_match["function_name"])
                            
                            # Create comprehensive function detail
                            function_detail = {
                                "function_name": func_match["function_name"],
                                "pipe_name": func_match.get("pipe_name", "unknown_pipeline"),
                                "description": func_match.get("description", ""),
                                "usage_description": func_match.get("usage_description", ""),
                                "relevance_score": func_match.get("relevance_score", 0.0),
                                "reasoning": func_match.get("reasoning", ""),
                                "priority": 1,
                                "step_applicability": [f"Step {step_num}"],
                                "data_requirements": step.get("data_requirements", []),
                                "expected_output": step.get("expected_output", ""),
                                "source_step": step_num,
                                "source_step_title": step_title
                            }
                            
                            # Add function definition details if available
                            if "function_definition" in func_match:
                                function_def = func_match["function_definition"]
                                function_detail.update({
                                    "required_params": function_def.get("required_params", []),
                                    "optional_params": function_def.get("optional_params", []),
                                    "outputs": function_def.get("outputs", {}),
                                    "category": function_def.get("category", "unknown_category"),
                                    "type_of_operation": function_def.get("type_of_operation", "unknown_operation")
                                })
                            
                            all_functions.append(function_detail)
                            
                            # Mark as specific match if high relevance
                            if func_match.get("relevance_score", 0.0) >= 0.9:
                                specific_matches.append(func_match["function_name"])
                
                # Sort by relevance score (highest first)
                all_functions.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
                
                # Take top functions (up to 8)
                max_functions = min(8, len(all_functions))
                top_functions = all_functions[:max_functions]
                
                # Format suggested functions with operation category and pipeline type
                top_function_names = []
                for func in top_functions:
                    function_name = func["function_name"]
                    category = func.get("category", "unknown_category")
                    pipe_name = func.get("pipe_name", "unknown_pipeline")
                    formatted_function = f"{function_name}: {category} ({pipe_name})"
                    top_function_names.append(formatted_function)
                
                logger.info(f"Step 2 completed successfully:")
                logger.info(f"  - Enhanced retrieval metrics: {enhanced_result.total_functions_retrieved} functions, {enhanced_result.total_steps_covered} steps covered, avg relevance: {enhanced_result.average_relevance_score:.2f}")
                logger.info(f"  - Selected {len(top_function_names)} top functions")
                logger.info(f"  - Specific matches: {specific_matches}")
                
                return {
                    "function_names": top_function_names,
                    "function_details": top_functions,
                    "specific_matches": specific_matches,
                    "total_selected": len(all_functions),
                    "analysis_complexity": self._assess_analysis_complexity(top_functions, reasoning_plan),
                    "estimated_execution_time": self._estimate_execution_time(top_functions, reasoning_plan),
                    "potential_issues": self._identify_potential_issues(top_functions, reasoning_plan),
                    "recommendations": self._generate_recommendations(top_functions, reasoning_plan, intent_type),
                    "function_selection_reasoning": enhanced_result.reasoning,
                    "reasoning_plan_alignment": {
                        "steps_covered": enhanced_result.total_steps_covered,
                        "total_steps": len(reasoning_plan),
                        "alignment_score": enhanced_result.confidence_score
                    },
                    "enhanced_retrieval_metrics": {
                        "total_functions_retrieved": enhanced_result.total_functions_retrieved,
                        "average_relevance_score": enhanced_result.average_relevance_score,
                        "fallback_used": enhanced_result.fallback_used
                    }
                }
                
            except Exception as retrieval_error:
                logger.warning(f"Efficient function selection failed: {retrieval_error}")
                return self._get_fallback_function_selection(intent_type, confidence_score, str(retrieval_error))
            
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
                "function_selection_reasoning": f"Error in Step 2: {str(e)}",
                "reasoning_plan_alignment": {
                    "steps_covered": 0,
                    "total_steps": 0,
                    "alignment_score": 0.0
                }
            }
    

    
    def _get_fallback_function_selection(
        self,
        intent_type: str,
        confidence_score: float,
        error_message: str = ""
    ) -> Dict[str, Any]:
        """
        Get fallback function selection when the main process fails.
        
        Args:
            intent_type: The intent type from Step 1
            confidence_score: The confidence score from Step 1
            error_message: Error message for debugging
            
        Returns:
            Fallback function selection result
        """
        # Use reasoning plan to guide function selection
        fallback_functions = self._select_fallback_functions_with_reasoning(
            intent_type=intent_type,
            reasoning_plan=[],  # Empty since we don't have it
            confidence_score=confidence_score
        )
        
        # Take first 5 functions and format them with category and pipeline info
        unique_functions = fallback_functions[:5]
        formatted_fallback_functions = []
        for func_name in unique_functions:
            formatted_function = f"{func_name}: unknown_category (unknown_pipeline)"
            formatted_fallback_functions.append(formatted_function)
        
        return {
            "function_names": formatted_fallback_functions,
            "function_details": [],
            "specific_matches": [],
            "total_selected": len(formatted_fallback_functions),
            "analysis_complexity": "unknown",
            "estimated_execution_time": "unknown",
            "potential_issues": [f"Using fallback selection: {error_message}"],
            "recommendations": ["Verify function selection manually"],
            "function_selection_reasoning": f"Fallback selection due to error: {error_message}",
            "reasoning_plan_alignment": {
                "steps_covered": 0,
                "total_steps": 0,
                "alignment_score": 0.0
            }
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
If there are data selection steps in the original reasoning plan, please remove them.
The data is already prepared and ready to be used for analysis. We should skip any data selection steps as well.

### CRITICAL INSTRUCTIONS ###
- Make sure there is no data selection steps in the reasoning plan.
- The data is already prepared and ready to be used for analysis. We should skip any data selection steps as well.
- **ABSOLUTELY NO VISUALIZATION STEPS**: This system is for backend data pipeline execution only. Do not include any visualization, plotting, charting, display, or show functions in the reasoning plan.
- Focus only on data processing, analysis, and transformation functions that can be executed in backend pipelines.
- If you see any visualization-related keywords in your reasoning, replace them with appropriate data processing steps.
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

### SELECTION STRATEGY ###
1. Please always create step 1 of plan as the data selection step so we can get the most relevant columns from the dataframe.
2. Add as many columns to the plan that will be needed for selection.

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
**CRITICAL**: If after the replan step the order is incorrect, please consider the best order of the steps for the given analysis question.

**CRITICAL EMBEDDED FUNCTION PARAMETER RULES**:
- For function input callable, if applicable, the function parameter should contain the function name from group aggregation functions
- Example: moving_apply_by_group(function=variance) where 'variance' is a function from group_aggregation_functions
- This embeds the group aggregation function directly within the MovingAggrPipe moving_apply_by_group function
- Do NOT create separate pipelines for functions that should be embedded as parameters
- Use function names from the group aggregation functions: mean, sum_values, count_values, max_value, min_value, std_dev, variance, median, unique_count, mode, weighted_average, geometric_mean, harmonic_mean, interquartile_range, mad, percent_change, absolute_change, etc.

**CRITICAL PARAMETER MAPPING RULES**:
- **Configuration parameters** (window, annualize, method, etc.) should be set to appropriate values, NOT mapped to columns
- **Data parameters** (variable, group_column, time_column, etc.) should be mapped to actual column names
- For calculate_growth_rates: window should be an integer (e.g., 30 for 30-day window), annualize should be boolean (True/False), method should be string ('percentage', 'log', 'cagr')
- For GroupBy: by should be column names, agg_dict should map columns to aggregation functions
- For aggregate_by_time: date_column should be date column, metric_columns should be numeric columns

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
- embedded_function_parameter: For functions like moving_apply_by_group, specify if a function parameter should contain a group aggregation function name (e.g., "function=variance")
- embedded_function_details: If embedded_function_parameter is true, specify the details of the embedded function (function name from group aggregation functions, no pipe type needed)

### ENHANCED METADATA REQUIREMENTS ###
Each step should also include enhanced metadata for better pipeline generation:

- **column_mapping**: Dictionary mapping DATA parameters (not configuration parameters) to actual available columns
  - Example: {{"variable": "Transactional value", "by": "Region, Project", "date_column": "Date"}}
  - **DO NOT MAP**: window, annualize, method, min_periods, center, output_suffix, suffix, periods, lag, lead, shift, fill_value, limit, dropna, how, axis, level, ascending, inplace, ignore_index, sort, na_position, key, keep, duplicates, verify_integrity, sort_index, sort_values, reset_index, drop, append, agg_dict, time_period, aggregation, fill_missing, include_current_period, time_name, datetime_format
  - **ONLY MAP**: variable, columns, by, date_column, time_column, metric_columns, value_column, target_column, feature_column, label_column, category_column, region_column, project_column, department_column, cost_center_column
  - **CORRECT EXAMPLE**: For calculate_growth_rates, column_mapping should be {{"time_column": "Date"}} and parameter_mapping should be {{"window": 30, "annualize": True, "method": "percentage"}}
- **output_columns**: List of columns that will be created by this step
  - Example: ["sum_Transactional value", "count_Transactional value", "mean_Transactional value"]
- **input_columns**: List of columns required as input for this step
  - Example: ["Transactional value", "Region", "Project", "Date"]
- **step_dependencies**: List of step numbers this step depends on (empty for first step)
  - Example: [1] if this step uses output from step 1
- **data_flow**: Description of how data flows from previous steps to this step
  - Example: "Uses aggregated data from step 1 as input"
- **embedded_function_columns**: If embedded_function_parameter is true, specify columns needed by embedded function
  - Example: {{"embedded_input_columns": ["Transactional value"], "embedded_output_columns": ["variance_Transactional value"]}}
- **pipeline_type**: The pipeline type this step will use
  - Example: "MetricsPipe", "TimeSeriesPipe", "CohortPipe"
- **function_category**: The category/type of operation this function performs
  - Example: "basic_metrics", "time_aggregation", "clustering"
- **parameter_constraints**: Any constraints or validation rules for parameters
  - Example: {{"window": "must be positive integer", "threshold": "must be between 0 and 1"}}
- **error_handling**: How to handle potential errors or edge cases
  - Example: "Handle missing values in group columns", "Validate time column format"

**FUNCTION SELECTION PRIORITY**:
1. **FIRST CHOICE**: Use functions from the specific_function_matches list
2. **SECOND CHOICE**: Use other functions from the function_details that best match the step requirements
3. **LAST RESORT**: Use "None" only if no suitable function exists for data preparation or data processing steps

**EMBEDDED FUNCTION PARAMETER GUIDELINES**:
- **USE EMBEDDED PARAMETERS FOR**: moving_apply_by_group, GroupBy, and similar functions that accept function parameters
- **EMBEDDED FUNCTION EXAMPLES**:
  - moving_apply_by_group with variance: function=variance (from group aggregation functions)
  - moving_apply_by_group with mean: function=mean (from group aggregation functions)
  - moving_apply_by_group with sum_values: function=sum_values (from group aggregation functions)
- **DO NOT EMBED FOR**: Direct function calls like Variance(), Mean(), Sum() that are used standalone
- **IMPORTANT**: Use function names from group_aggregation_functions module
- **FUNCTION NAMES**: Use lowercase with underscores: variance, mean, sum_values, count_values, max_value, min_value, std_dev, median, unique_count, mode, weighted_average, geometric_mean, harmonic_mean, interquartile_range, mad, percent_change, absolute_change, etc.

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
            "pipeline_name": "pipeline_name",
            "input_processing": "How to process inputs for this function",
            "parameter_mapping": "How to map data to function parameters",
            "expected_output": "What this step produces",
            "data_requirements": ["column1", "column2"],
            "considerations": "Important considerations",
            "merge_with_previous": false,
            "embedded_function_parameter": false,
            "embedded_function_details": null,
            "column_mapping": {{"variable": "column1", "group_column": "column2"}},
            "output_columns": ["output_col1", "output_col2"],
            "input_columns": ["input_col1", "input_col2"],
            "step_dependencies": [],
            "data_flow": "Initial data input",
            "embedded_function_columns": null,
            "pipeline_type": "MetricsPipe",
            "function_category": "basic_metrics",
            "parameter_constraints": {{"param1": "constraint description"}},
            "error_handling": "How to handle errors"
        }},
        {{
            "step_number": 2,
            "step_title": "Moving Apply with Embedded Variance",
            "step_description": "Apply moving variance calculation by group with embedded Variance function",
            "function_name": "moving_apply_by_group",
            "pipeline_name": "MovingAveragePipe",
            "input_processing": "Prepare time series data with group columns",
            "parameter_mapping": "Map columns to function parameters, embed Variance as function parameter",
            "expected_output": "Rolling variance values by group over time",
            "data_requirements": ["Transactional value", "Project", "Cost center", "Department", "Date"],
            "considerations": "Ensure proper time column format and handle missing values",
            "merge_with_previous": false,
            "embedded_function_parameter": true,
            "embedded_function_details": {{
                "embedded_function": "variance",
                "embedded_parameters": {{"column": "Transactional value"}},
                "embedded_output": "variance_Transactional value"
            }},
            "column_mapping": {{
                "columns": "Transactional value",
                "group_column": "Project, Cost center, Department",
                "time_column": "Date",
                "window": 5,
                "min_periods": 1,
                "output_suffix": "_rolling_variance"
            }},
            "output_columns": ["Transactional value_rolling_variance"],
            "input_columns": ["Transactional value", "Project", "Cost center", "Department", "Date"],
            "step_dependencies": [1],
            "data_flow": "Uses aggregated data from step 1 as input",
            "embedded_function_columns": {{
                "embedded_input_columns": ["Transactional value"],
                "embedded_output_columns": ["variance_Transactional value"]
            }},
            "pipeline_type": "TimeSeriesPipe",
            "function_category": "time_aggregation",
            "parameter_constraints": {{
                "window": "must be positive integer",
                "min_periods": "must be positive integer <= {{window}}"
            }},
            "error_handling": "Handle missing values in group columns, validate time column format"
        }}
    ]
}}

Focus on creating clear, actionable reasoning steps that the next agent can use to generate actual pipeline code. Each step should be specific enough to guide code generation but general enough to be flexible.

**REMEMBER**: The specific function matches are the most relevant functions for this analysis. Use them as the primary functions in your pipeline reasoning plan.

**SPECIFIC EXAMPLE - Variance + moving_apply_by_group**:
When the user asks for "variance with moving apply by group", the reasoning plan should specify:
- Step 1: Use moving_apply_by_group as the primary function
- embedded_function_parameter: true
- embedded_function_details: Specify variance as the embedded function from group aggregation functions
- This tells the code generation agent to create: function=variance
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
                    
                    # Post-process: Filter out any visualization steps that might have slipped through
                    if "pipeline_reasoning_plan" in step3_result and step3_result["pipeline_reasoning_plan"]:
                        filtered_pipeline_plan = []
                        for step in step3_result["pipeline_reasoning_plan"]:
                            step_title = step.get("step_title", "").lower()
                            step_desc = step.get("step_description", "").lower()
                            
                            # Check for visualization keywords
                            visualization_keywords = [
                                "visualize", "visualization", "plot", "plotting", "chart", "charting", 
                                "graph", "graphing", "show", "display", "create visual", "create plot",
                                "create chart", "create graph", "draw", "render", "present"
                            ]
                            
                            has_visualization = any(keyword in step_title or keyword in step_desc 
                                                  for keyword in visualization_keywords)
                            
                            if not has_visualization:
                                filtered_pipeline_plan.append(step)
                            else:
                                logger.warning(f"Filtered out visualization step from pipeline: {step.get('step_title', 'Unknown')}")
                        
                        step3_result["pipeline_reasoning_plan"] = filtered_pipeline_plan
                        logger.info(f"Filtered pipeline reasoning plan: {len(filtered_pipeline_plan)} steps after removing visualization steps")
                    
                except Exception as parse_error:
                    logger.warning(f"Failed to parse Step 3 JSON response: {parse_error}")
                    logger.warning(f"Raw response: {response_content}")
                    
                    # Create fallback result
                    step3_result = {
                        "pipeline_reasoning_plan": []
                    }
                
                logger.info(f"Step 3 completed successfully:")
                logger.info(f"  - Pipeline steps: {len(step3_result.get('pipeline_reasoning_plan', []))}")
                
                # Enhance the reasoning plan with additional metadata
                if step3_result.get("pipeline_reasoning_plan"):
                    enhanced_plan = await self._enhance_reasoning_plan_with_metadata(
                        step3_result["pipeline_reasoning_plan"],
                        available_columns,
                        dataframe_description,
                        dataframe_summary,
                        function_details
                    )
                    step3_result["pipeline_reasoning_plan"] = enhanced_plan
                    logger.info(f"Enhanced reasoning plan with metadata for {len(enhanced_plan)} steps")
                
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

    async def _enhance_reasoning_plan_with_metadata(
        self,
        reasoning_plan: List[Dict[str, Any]],
        available_columns: List[str],
        dataframe_description: str,
        dataframe_summary: str,
        function_details: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enhance the reasoning plan with additional metadata for better pipeline generation.
        
        This method adds comprehensive metadata to each reasoning plan step, including:
        - Column mapping between function parameters and available columns
        - Input/output column specifications
        - Step dependencies and data flow information
        - Pipeline type and function category details
        - Parameter constraints and error handling
        - Embedded function column requirements
        
        This enhanced metadata significantly improves the accuracy of the self-correcting
        pipeline generator by providing clear information about:
        1. Which columns to use for each function parameter
        2. How data flows between steps
        3. What constraints apply to parameters
        4. How to handle embedded functions
        
        Args:
            reasoning_plan: List of reasoning plan steps
            available_columns: List of available columns in the dataframe
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            function_details: List of function details from Step 2
            
        Returns:
            Enhanced reasoning plan with additional metadata for each step:
            
            Each step now includes:
            - column_mapping: Dict mapping function parameters to actual columns
            - input_columns: List of columns required as input
            - output_columns: List of columns that will be created
            - step_dependencies: List of step numbers this step depends on
            - data_flow: Description of how data flows to this step
            - pipeline_type: The pipeline type (e.g., "MetricsPipe", "TimeSeriesPipe")
            - function_category: The type of operation (e.g., "basic_metrics", "time_aggregation")
            - parameter_constraints: Validation rules for parameters
            - error_handling: How to handle potential errors
            - embedded_function_columns: Column requirements for embedded functions (if applicable)
        """
        if not reasoning_plan:
            return reasoning_plan
        
        enhanced_plan = []
        
        for i, step in enumerate(reasoning_plan):
            if not isinstance(step, dict):
                continue
            
            enhanced_step = step.copy()
            
            # Get function details for this step
            function_name = step.get('function_name', '')
            function_detail = None
            
            # Find matching function details
            for func in function_details:
                if func.get('function_name') == function_name:
                    function_detail = func
                    break
            
            # Enhance with column mapping
            if function_detail and function_name:
                enhanced_step = await self._enhance_step_with_column_mapping(
                    enhanced_step, function_detail, available_columns, dataframe_description
                )
            
            # Enhance with pipeline type and category
            if function_detail:
                enhanced_step = self._enhance_step_with_pipeline_info(enhanced_step, function_detail)
            
            # Enhance with step dependencies and data flow
            enhanced_step = self._enhance_step_with_dependencies(enhanced_step, i, enhanced_plan)
            
            # Enhance with parameter constraints and error handling
            enhanced_step = self._enhance_step_with_constraints(enhanced_step, function_detail)
            
            # Enhance embedded function details if present
            if step.get('embedded_function_parameter', False):
                enhanced_step = await self._enhance_embedded_function_details(
                    enhanced_step, available_columns, function_details
                )
            
            enhanced_plan.append(enhanced_step)
        
        return enhanced_plan
    
    async def _enhance_step_with_column_mapping(
        self,
        step: Dict[str, Any],
        function_detail: Dict[str, Any],
        available_columns: List[str],
        dataframe_description: str
    ) -> Dict[str, Any]:
        """
        Enhance a step with basic metadata - column mapping will be handled by LLM-based function input detection
        """
        enhanced_step = step.copy()
        
        # Let the self-correcting RAG pipeline handle column mapping through LLM-based detection
        # This avoids hardcoded column mapping logic and uses the more sophisticated approach
        
        # Add basic metadata that doesn't require hardcoded column mapping
        enhanced_step['available_columns'] = available_columns
        enhanced_step['dataframe_description'] = dataframe_description
        enhanced_step['function_name'] = function_detail.get('function_name', '')
        enhanced_step['pipeline_type'] = function_detail.get('category', 'Unknown')
        enhanced_step['function_category'] = function_detail.get('type_of_operation', 'unknown')
        
        # Initialize empty column mapping - will be filled by LLM-based detection
        enhanced_step['column_mapping'] = {}
        enhanced_step['input_columns'] = []
        enhanced_step['output_columns'] = []
        
        return enhanced_step
    
    # Column mapping is now handled by LLM-based function input detection in the self-correcting RAG pipeline
    # This removes hardcoded column mapping logic and uses the more sophisticated approach
    
    def _enhance_step_with_pipeline_info(
        self,
        step: Dict[str, Any],
        function_detail: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance a step with pipeline type and function category information
        """
        enhanced_step = step.copy()
        
        # Get pipeline type from function detail
        pipeline_type = function_detail.get('category', 'Unknown')
        enhanced_step['pipeline_type'] = pipeline_type
        
        # Get function category from type of operation
        function_category = function_detail.get('type_of_operation', 'unknown')
        enhanced_step['function_category'] = function_category
        
        return enhanced_step
    
    def _enhance_step_with_dependencies(
        self,
        step: Dict[str, Any],
        step_index: int,
        previous_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Enhance a step with dependencies and data flow information
        """
        enhanced_step = step.copy()
        
        if step_index == 0:
            # First step has no dependencies
            enhanced_step['step_dependencies'] = []
            enhanced_step['data_flow'] = "Initial data input"
        else:
            # Check if this step depends on previous steps
            dependencies = []
            data_flow_parts = []
            
            for prev_step in previous_steps:
                prev_outputs = prev_step.get('output_columns', [])
                current_inputs = step.get('input_columns', [])
                
                # Check if current step uses outputs from previous step
                if any(output in current_inputs for output in prev_outputs):
                    dependencies.append(prev_step.get('step_number', 0))
                    data_flow_parts.append(f"Uses {', '.join(prev_outputs)} from step {prev_step.get('step_number', 0)}")
            
            enhanced_step['step_dependencies'] = dependencies
            enhanced_step['data_flow'] = "; ".join(data_flow_parts) if data_flow_parts else "Uses original dataframe"
        
        return enhanced_step
    
    def _enhance_step_with_constraints(
        self,
        step: Dict[str, Any],
        function_detail: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance a step with parameter constraints and error handling
        """
        enhanced_step = step.copy()
        
        # Add parameter constraints based on function type
        parameter_constraints = {}
        error_handling = []
        
        function_name = step.get('function_name', '').lower()
        
        # Add constraints based on function type
        if 'window' in function_name or 'rolling' in function_name:
            parameter_constraints['window'] = "must be positive integer"
            parameter_constraints['min_periods'] = "must be positive integer <= window"
        
        if 'threshold' in function_name:
            parameter_constraints['threshold'] = "must be between 0 and 1"
        
        if 'n_clusters' in function_name:
            parameter_constraints['n_clusters'] = "must be positive integer"
        
        # Add error handling based on function type
        if any(keyword in function_name for keyword in ['group', 'aggregate']):
            error_handling.append("Handle missing values in group columns")
        
        if any(keyword in function_name for keyword in ['time', 'date', 'rolling']):
            error_handling.append("Validate time column format")
        
        if any(keyword in function_name for keyword in ['variance', 'std', 'correlation']):
            error_handling.append("Handle non-numeric columns")
        
        enhanced_step['parameter_constraints'] = parameter_constraints
        enhanced_step['error_handling'] = "; ".join(error_handling) if error_handling else "Standard error handling"
        
        return enhanced_step
    
    async def _enhance_embedded_function_details(
        self,
        step: Dict[str, Any],
        available_columns: List[str],
        function_details: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Enhance embedded function details with column information
        """
        enhanced_step = step.copy()
        
        embedded_details = step.get('embedded_function_details', {})
        if not embedded_details:
            return enhanced_step
        
        # Find the embedded function details
        embedded_function = embedded_details.get('embedded_function', '')
        embedded_pipe = embedded_details.get('embedded_pipe', 'MetricsPipe')
        
        # Find function details for embedded function
        embedded_func_detail = None
        for func in function_details:
            if func.get('function_name') == embedded_function:
                embedded_func_detail = func
                break
        
        if embedded_func_detail:
            # Get embedded function parameters
            embedded_params = embedded_details.get('embedded_parameters', {})
            
            # Map embedded function parameters to columns
            embedded_input_columns = []
            embedded_output_columns = []
            
            for param_name, param_value in embedded_params.items():
                if param_name == 'variable':
                    # This is the main column for the embedded function
                    embedded_input_columns.append(param_value)
                    # Generate output column name
                    output_col = f"{embedded_function.lower()}_{param_value}"
                    embedded_output_columns.append(output_col)
            
            # Add embedded function columns to the step
            enhanced_step['embedded_function_columns'] = {
                'embedded_input_columns': embedded_input_columns,
                'embedded_output_columns': embedded_output_columns
            }
        
        return enhanced_step


# Example usage
if __name__ == "__main__":
    import asyncio
    
    
