import json
import logging
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime

import orjson
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langfuse.decorators import observe
from pydantic import BaseModel
from app.storage.documents import DocumentChromaStore

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
    reasoning: str
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


# System prompt for intent classification
ANALYSIS_INTENT_SYSTEM_PROMPT = """
### TASK ###
You are an expert data analyst who specializes in intent classification for data analysis tasks.
Your goal is to analyze user questions and classify them into appropriate analysis types based on available analysis functions AND available data.

First, rephrase the user's question to make it more specific and clear.
Second, classify the user's intent into one of the available analysis types.
Third, suggest the most relevant functions and required data columns.
Fourth, assess whether the question can be answered with the available data.

### CRITICAL INSTRUCTIONS ###
- PRIORITIZE EXACT FUNCTION MATCHES: If the user mentions specific analysis terms (like "variance", "rolling variance", "correlation", etc.), classify accordingly
- When you see 🎯 marked functions, these are EXACT keyword matches - give them highest priority
- CHECK DATA FEASIBILITY: Analyze available columns, data description, and summary to determine if analysis is possible
- Rephrase the question to be more specific and actionable
- Classify intent based on the MOST SPECIFIC analysis type that matches the question
- Provide clear reasoning for your classification (within 30 words)
- Suggest 2-3 most relevant functions from the retrieved options
- Identify required data columns based on function specifications
- Assess feasibility: can_be_answered (true/false) and feasibility_score (0.0-1.0)
- If columns are missing, suggest alternatives from available data
- If intent is unclear, provide helpful clarification questions

### DATA FEASIBILITY ASSESSMENT ###
- can_be_answered: true if all required columns exist or suitable alternatives are available
- feasibility_score: 1.0 = perfect match, 0.8+ = good alternatives exist, 0.5+ = partial match, <0.5 = major limitations
- missing_columns: list columns that are required but not available
- available_alternatives: suggest similar columns that could work
- data_suggestions: provide advice on data preparation or alternative approaches

### SPECIFIC ANALYSIS TYPE MAPPING ###
When user asks about:
- "variance", "rolling variance", "variance analysis" → classify as time_series_analysis with variance_analysis function
- "rolling", "moving", "window" calculations → classify as time_series_analysis and look for specific rolling function (variance_analysis, moving_average, etc.)
- "lead", "lag", "future/past values" → time_series_analysis with lead/lag functions
- "trend", "growth", "forecast" → trend_analysis
- "cluster", "segment", "group users" → segmentation_analysis  
- "retention", "cohort", "lifetime value" → cohort_analysis
- "funnel", "conversion", "user journey" → funnel_analysis
- "risk", "VaR", "monte carlo" → risk_analysis
- "anomaly", "outlier", "anomalies", "outliers" → anomaly_detection with appropriate detection function
- "sum", "count", "average", "correlation" → metrics_calculation
- "percent change", "A/B test", "confidence interval" → operations_analysis

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
    "suggested_functions": ["function1", "function2", "function3"],
    "reasoning": "brief explanation emphasizing specific function matches and data availability",
    "required_data_columns": ["column1", "column2"],
    "clarification_needed": "question if intent unclear or null",
    "can_be_answered": true/false,
    "feasibility_score": 0.0-1.0,
    "missing_columns": ["missing_col1", "missing_col2"],
    "available_alternatives": ["alt_col1", "alt_col2"],
    "data_suggestions": "advice on data prep or alternatives or null"
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

### ANALYSIS INSTRUCTION ###
Based on the user question, available dataframe information, and the retrieved function information above:
1. Classify the analysis intent 
2. Assess whether the question can be answered with the available data
3. Suggest alternative approaches if exact columns don't exist
4. Provide suggestions for data preparation if needed

Consider:
- Do the available columns support the requested analysis?
- Are there similar columns that could work as alternatives?
- What data transformations might be needed?
- Is the dataframe structure suitable for the intended analysis?

Current Time: {current_time}
"""


def retrieve_function_definition(function_name: str, function_collection) -> Dict[str, Any]:
    """
    Retrieve function definition from ChromaDB
    
    Args:
        function_name: Name of the function to retrieve
        function_collection: DocumentChromaStore instance containing function definitions
        
    Returns:
        Dict with function definition and retrieval score
    """
    
    # Query ChromaDB for function definition
    query_result = function_collection.semantic_searches(query_texts=[function_name], n_results=3)
    
    if not query_result or not query_result["documents"] or len(query_result["documents"][0]) == 0:
        return {
            "status": "error",
            "message": f"No definition found for function {function_name}",
            "score": 0.0
        }
    
    # Parse the document content
    try:
        document = query_result["documents"][0][0]  # First query, first result
        score = query_result["distances"][0][0] if "distances" in query_result else 0.0
        
        # Convert from JSON string if needed
        if isinstance(document, str) and document.startswith('"') and document.endswith('"'):
            document = json.loads(document)
            
        if isinstance(document, str) and (document.startswith('{') or document.startswith('{"')):
            document = json.loads(document)
            
        return {
            "status": "success",
            "function_definition": document,
            "score": score
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing function definition: {str(e)}",
            "score": 0.0
        }


def retrieve_function_examples(function_name: str, example_collection) -> Dict[str, Any]:
    """
    Retrieve function examples from ChromaDB
    
    Args:
        function_name: Name of the function to retrieve examples for
        example_collection: DocumentChromaStore instance containing function examples
        
    Returns:
        Dict with function examples and retrieval score
    """
    # Query ChromaDB for function examples
    query_result = example_collection.semantic_searches(
        query_texts=[function_name],
        n_results=5
    )
    
    if not query_result or not query_result["documents"]:
        return {
            "status": "error",
            "message": f"No examples found for function {function_name}",
            "score": 0.0
        }
    
    # Parse the document content
    try:
        examples = []
        scores = []
        
        for i, document in enumerate(query_result["documents"][0]):
            score = query_result["distances"][0][i] if "distances" in query_result else 0.0
            
            # Convert from JSON string if needed
            if isinstance(document, str) and document.startswith('"') and document.endswith('"'):
                document = json.loads(document)
                
            if isinstance(document, str) and (document.startswith('{') or document.startswith('{"')):
                document = json.loads(document)
            
            examples.append(document)
            scores.append(score)
        
        return {
            "status": "success",
            "examples": examples,
            "scores": scores,
            "avg_score": sum(scores) / len(scores) if scores else 0.0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing function examples: {str(e)}",
            "score": 0.0
        }


def retrieve_function_insights(function_name: str, insights_collection) -> Dict[str, Any]:
    """
    Retrieve function insights from ChromaDB
    
    Args:
        function_name: Name of the function to retrieve insights for
        insights_collection: DocumentChromaStore instance containing function insights
        
    Returns:
        Dict with function insights and retrieval score
    """
    # Query ChromaDB for function insights
    query_result = insights_collection.semantic_searches(
        query_texts=[function_name],
        n_results=5
    )
    
    if not query_result or not query_result["documents"]:
        return {
            "status": "error",
            "message": f"No insights found for function {function_name}",
            "score": 0.0
        }
    
    # Parse the document content
    try:
        insights = []
        scores = []
        
        for i, document in enumerate(query_result["documents"][0]):
            score = query_result["distances"][0][i] if "distances" in query_result else 0.0
            
            # Convert from JSON string if needed
            if isinstance(document, str) and document.startswith('"') and document.endswith('"'):
                document = json.loads(document)
                
            if isinstance(document, str) and (document.startswith('{') or document.startswith('{"')):
                document = json.loads(document)
            
            insights.append(document)
            scores.append(score)
        
        return {
            "status": "success",
            "insights": insights,
            "scores": scores,
            "avg_score": sum(scores) / len(scores) if scores else 0.0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing function insights: {str(e)}",
            "score": 0.0
        }


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
        
        # Core analysis functions to search for
        self.core_functions = [
            # Time series
            "lead", "lag", "variance_analysis", "distribution_analysis", "cumulative_distribution",
            # Trend analysis
            "aggregate_by_time", "calculate_growth_rates", "calculate_moving_average", 
            "decompose_trend", "forecast_metric", "calculate_statistical_trend",
            # Segmentation
            "run_kmeans", "run_dbscan", "run_hdbscan", "run_agglomerative", "run_rule_based",
            # Cohort analysis
            "form_time_cohorts", "form_behavioral_cohorts", "calculate_retention", 
            "calculate_conversion", "calculate_lifetime_value",
            # Funnel analysis
            "analyze_funnel", "analyze_funnel_by_time", "analyze_funnel_by_segment", 
            "analyze_user_paths", "compare_segments",
            # Risk analysis
            "fit_distribution", "calculate_var", "calculate_cvar", "calculate_portfolio_risk",
            "monte_carlo_simulation", "stress_test", "rolling_risk_metrics",
            # Anomaly detection
            "detect_statistical_outliers", "detect_contextual_anomalies", "detect_collective_anomalies",
            "detect_anomalies_from_residuals", "detect_change_points", "forecast_and_detect_anomalies",
            "batch_detect_anomalies", "calculate_seasonal_residuals",
            # Metrics
            "Count", "Sum", "Max", "Min", "Mean", "Median", "Ratio", "Correlation",
            # Operations
            "PercentChange", "AbsoluteChange", "MH", "CUPED", "PowerAnalysis", "BootstrapCI"
        ]

    def _extract_specific_function_keywords(self, question: str) -> List[str]:
        """
        Extract specific function keywords that should be prioritized
        
        Args:
            question: User's question
            
        Returns:
            List of specific function names that match keywords in the question
        """
        question_lower = question.lower()
        specific_matches = []
        
        # Direct function keyword mapping for more precise matching
        function_keywords = {
            "variance_analysis": ["variance", "rolling variance", "variance over time", "variance analysis"],
            "lead": ["lead", "future values", "forward looking"],
            "lag": ["lag", "past values", "lagged", "previous"],
            "distribution_analysis": ["distribution", "histogram", "bins"],
            "cumulative_distribution": ["cumulative", "cumsum", "running total"],
            "aggregate_by_time": ["aggregate", "group by time", "time periods"],
            "calculate_growth_rates": ["growth rate", "growth", "yoy", "mom"],
            "calculate_moving_average": ["moving average", "rolling average", "smooth"],
            "decompose_trend": ["decompose", "seasonal", "trend decomposition"],
            "forecast_metric": ["forecast", "predict", "future"],
            "run_kmeans": ["kmeans", "k-means", "cluster"],
            "run_dbscan": ["dbscan", "density cluster"],
            "calculate_retention": ["retention", "user retention", "customer retention"],
            "calculate_conversion": ["conversion", "funnel conversion"],
            "analyze_funnel": ["funnel", "conversion funnel"],
            "calculate_var": ["var", "value at risk"],
            "monte_carlo_simulation": ["monte carlo", "simulation"],
            "PercentChange": ["percent change", "percentage change"],
            "BootstrapCI": ["bootstrap", "confidence interval"],
            # Anomaly detection keywords
            "detect_statistical_outliers": ["anomaly", "anomalies", "outlier", "outliers", "statistical outlier", "z-score", "iqr"],
            "detect_contextual_anomalies": ["contextual anomaly", "time series anomaly", "pattern anomaly", "temporal anomaly"],
            "detect_collective_anomalies": ["collective anomaly", "multivariate anomaly", "isolation forest", "local outlier factor"],
            "detect_anomalies_from_residuals": ["residual anomaly", "seasonal residual", "decomposition anomaly"],
            "detect_change_points": ["change point", "changepoint", "break point", "structural break"],
            "forecast_and_detect_anomalies": ["forecast anomaly", "prediction anomaly", "forecast error"],
            "batch_detect_anomalies": ["ensemble anomaly", "multiple anomaly", "combined anomaly detection"]
        }
        
        for func_name, keywords in function_keywords.items():
            for keyword in keywords:
                if keyword in question_lower:
                    specific_matches.append(func_name)
                    break  # Only add once per function
        
        return specific_matches

    @observe(capture_input=False)
    def _retrieve_relevant_functions(self, question: str) -> Dict[str, Any]:
        """
        Retrieve relevant function definitions, examples, and insights based on the question
        
        Args:
            question: User's question
            
        Returns:
            Dict containing retrieved function information
        """
        results = {
            "definitions": [],
            "examples": [],
            "insights": [],
            "specific_matches": []
        }
        
        # First, check for specific function keyword matches
        specific_matches = self._extract_specific_function_keywords(question)
        results["specific_matches"] = specific_matches
        
        try:
            # Use the question to semantically search for relevant functions
            if self.function_collection:
                # Search function definitions using the question
                query_result = self.function_collection.semantic_searches(
                    query_texts=[question], 
                    n_results=self.max_functions_to_retrieve
                )
                
                # If we have specific matches, also search for those function names directly
                if specific_matches:
                    for func_name in specific_matches:
                        func_query_result = self.function_collection.semantic_searches(
                            query_texts=[func_name], 
                            n_results=2
                        )
                        if func_query_result and func_query_result.get("documents"):
                            # Add these results with higher priority (lower distance scores)
                            for i, doc in enumerate(func_query_result["documents"][0]):
                                score = func_query_result["distances"][0][i] if "distances" in func_query_result else 0.0
                                # Boost priority by reducing score for specific matches
                                score = score * 0.5  
                                
                                try:
                                    if isinstance(doc, str) and (doc.startswith('{') or doc.startswith('{"')):
                                        doc = json.loads(doc)
                                    results["definitions"].append({
                                        "content": doc,
                                        "score": score,
                                        "specific_match": True
                                    })
                                except json.JSONDecodeError:
                                    continue
                
                if query_result and query_result.get("documents"):
                    for i, doc in enumerate(query_result["documents"][0]):
                        score = query_result["distances"][0][i] if "distances" in query_result else 0.0
                        
                        # Parse document
                        try:
                            if isinstance(doc, str) and (doc.startswith('{') or doc.startswith('{"')):
                                doc = json.loads(doc)
                            results["definitions"].append({
                                "content": doc,
                                "score": score,
                                "specific_match": False
                            })
                        except json.JSONDecodeError:
                            continue
            
            # Similarly retrieve examples and insights
            if self.example_collection:
                query_result = self.example_collection.semantic_searches(
                    query_texts=[question], 
                    n_results=5
                )
                
                if query_result and query_result.get("documents"):
                    for i, doc in enumerate(query_result["documents"][0]):
                        score = query_result["distances"][0][i] if "distances" in query_result else 0.0
                        
                        try:
                            if isinstance(doc, str) and (doc.startswith('{') or doc.startswith('{"')):
                                doc = json.loads(doc)
                            results["examples"].append({
                                "content": doc,
                                "score": score
                            })
                        except json.JSONDecodeError:
                            continue
            
            if self.insights_collection:
                query_result = self.insights_collection.semantic_searches(
                    query_texts=[question], 
                    n_results=5
                )
                
                if query_result and query_result.get("documents"):
                    for i, doc in enumerate(query_result["documents"][0]):
                        score = query_result["distances"][0][i] if "distances" in query_result else 0.0
                        
                        try:
                            if isinstance(doc, str) and (doc.startswith('{') or doc.startswith('{"')):
                                doc = json.loads(doc)
                            results["insights"].append({
                                "content": doc,
                                "score": score
                            })
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Error retrieving relevant functions: {e}")
        
        return results

    @observe(capture_input=False)
    def _format_retrieved_content(self, retrieved_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Format retrieved content for prompt inclusion
        
        Args:
            retrieved_data: Dictionary containing retrieved functions, examples, insights
            
        Returns:
            Formatted strings for prompt
        """
        # Sort definitions to prioritize specific matches
        definitions = retrieved_data.get("definitions", [])
        definitions.sort(key=lambda x: (not x.get("specific_match", False), x.get("score", 1.0)))
        
        # Format function definitions with priority indication
        definitions_text = ""
        if definitions:
            definitions_text = "Available Functions (ordered by relevance):\n"
            
            # Add specific matches first
            specific_matches = retrieved_data.get("specific_matches", [])
            if specific_matches:
                definitions_text += f"\n🎯 EXACT KEYWORD MATCHES for your question: {', '.join(specific_matches)}\n\n"
            
            for i, item in enumerate(definitions[:8]):  # Top 8
                content = item.get("content", {})
                if isinstance(content, dict):
                    func_name = content.get("function_name", f"Function_{i+1}")
                    description = content.get("description", "No description")
                    params = content.get("parameters", {})
                    
                    # Mark specific matches
                    priority_marker = "🎯 " if item.get("specific_match", False) else ""
                    
                    definitions_text += f"- {priority_marker}{func_name}: {description}\n"
                    definitions_text += f"  Parameters: {params}\n\n"
        
        # Format examples
        examples_text = ""
        if retrieved_data.get("examples"):
            examples_text = "Usage Examples:\n"
            for i, item in enumerate(retrieved_data["examples"][:3]):  # Top 3
                content = item.get("content", {})
                if isinstance(content, dict):
                    example = content.get("example", content.get("usage", ""))
                    examples_text += f"Example {i+1}: {example}\n\n"
        
        # Format insights
        insights_text = ""
        if retrieved_data.get("insights"):
            insights_text = "Analysis Insights:\n"
            for i, item in enumerate(retrieved_data["insights"][:3]):  # Top 3
                content = item.get("content", {})
                if isinstance(content, dict):
                    insight = content.get("insight", content.get("tip", ""))
                    insights_text += f"Insight {i+1}: {insight}\n\n"
        
        return {
            "function_definitions": definitions_text,
            "function_examples": examples_text,
            "function_insights": insights_text
        }

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

    @observe(capture_input=False)
    def _post_process_llm_response(
        self, 
        llm_response: Dict[str, Any], 
        retrieved_data: Dict[str, Any],
        available_columns: Optional[List[str]] = None
    ) -> AnalysisIntentResult:
        """
        Post-process LLM response into structured result
        
        Args:
            llm_response: Raw LLM response
            retrieved_data: Retrieved function data for context
            available_columns: List of available columns in the dataframe
            
        Returns:
            Structured AnalysisIntentResult
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
            parsed_response = orjson.loads(response_content)
            
            # Extract retrieved function names for context
            retrieved_functions = []
            for item in retrieved_data.get("definitions", [])[:3]:
                content = item.get("content", {})
                if isinstance(content, dict) and "function_name" in content:
                    retrieved_functions.append(content)
            
            # Get specific matches
            specific_matches = retrieved_data.get("specific_matches", [])
            
            # Validate feasibility assessment with available data
            required_columns = parsed_response.get("required_data_columns", [])
            missing_columns = parsed_response.get("missing_columns", [])
            can_be_answered = parsed_response.get("can_be_answered", False)
            feasibility_score = parsed_response.get("feasibility_score", 0.0)
            
            # Double-check feasibility if we have column information
            if available_columns is not None and required_columns:
                actual_missing = [col for col in required_columns if col not in available_columns]
                if actual_missing and not missing_columns:
                    missing_columns = actual_missing
                    can_be_answered = False
                    feasibility_score = min(feasibility_score, 0.3)
            
            return AnalysisIntentResult(
                intent_type=parsed_response.get("intent_type", "unclear_intent"),
                confidence_score=float(parsed_response.get("confidence_score", 0.0)),
                rephrased_question=parsed_response.get("rephrased_question", ""),
                suggested_functions=parsed_response.get("suggested_functions", []),
                reasoning=parsed_response.get("reasoning", ""),
                required_data_columns=required_columns,
                clarification_needed=parsed_response.get("clarification_needed"),
                retrieved_functions=retrieved_functions,
                specific_function_matches=specific_matches,
                can_be_answered=can_be_answered,
                feasibility_score=float(feasibility_score),
                missing_columns=missing_columns,
                available_alternatives=parsed_response.get("available_alternatives", []),
                data_suggestions=parsed_response.get("data_suggestions")
            )
            
        except Exception as e:
            logger.error(f"Error post-processing LLM response: {e}")
            return AnalysisIntentResult(
                intent_type="unsupported_analysis",
                confidence_score=0.0,
                rephrased_question="",
                suggested_functions=[],
                reasoning=f"Error processing response: {str(e)}",
                required_data_columns=[],
                clarification_needed="I encountered an error processing your question. Please try rephrasing it.",
                retrieved_functions=[],
                specific_function_matches=[],
                can_be_answered=False,
                feasibility_score=0.0,
                missing_columns=[],
                available_alternatives=[],
                data_suggestions="Unable to assess data due to processing error."
            )

    @observe(name="Analysis Intent Classification")
    async def classify_intent(self, question: str, dataframe_description: str, dataframe_summary: str, available_columns: List[str]) -> AnalysisIntentResult:
        """
        Main method to classify user intent and suggest analysis approach
        
        Args:
            question: User's natural language question
            
        Returns:
            AnalysisIntentResult with classification and suggestions
        """
        try:
            # Step 1: Retrieve relevant functions using semantic search
            retrieved_data = self._retrieve_relevant_functions(question)
            
            # Step 2: Format retrieved content for prompt
            formatted_content = self._format_retrieved_content(retrieved_data)
            
            # Step 3: Create prompt for LLM
            prompt_template = PromptTemplate(
                input_variables=["question", "dataframe_description", "dataframe_summary", "available_columns", "function_definitions", "function_examples", 
                               "function_insights", "current_time"],
                template=ANALYSIS_INTENT_USER_PROMPT
            )
            
            prompt = prompt_template.format(
                question=question,  
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                function_definitions=formatted_content["function_definitions"],
                function_examples=formatted_content["function_examples"],
                function_insights=formatted_content["function_insights"],
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # Step 4: Get LLM classification
            llm_response = await self._classify_with_llm(prompt)
            
            # Step 5: Post-process into structured result
            result = self._post_process_llm_response(llm_response, retrieved_data, available_columns)
            
            # Step 6: Enhanced feasibility assessment using LLM
            if result.required_data_columns and available_columns:
                try:
                    llm_feasibility = await self._assess_data_feasibility_with_llm(
                        required_columns=result.required_data_columns,
                        available_columns=available_columns,
                        question=question,
                        dataframe_description=dataframe_description,
                        dataframe_summary=dataframe_summary
                    )
                    
                    # Update result with LLM-based feasibility assessment
                    result.can_be_answered = llm_feasibility.get("can_be_answered", result.can_be_answered)
                    result.feasibility_score = llm_feasibility.get("feasibility_score", result.feasibility_score)
                    result.missing_columns = llm_feasibility.get("missing_columns", result.missing_columns)
                    result.available_alternatives = llm_feasibility.get("available_alternatives", result.available_alternatives)
                    
                    # Add additional LLM insights
                    if "llm_reasoning" in llm_feasibility:
                        result.data_suggestions = f"LLM Assessment: {llm_feasibility['llm_reasoning']}"
                    if "transformation_suggestions" in llm_feasibility:
                        result.data_suggestions = f"{result.data_suggestions or ''}\nTransformations: {', '.join(llm_feasibility['transformation_suggestions'])}"
                except Exception as feasibility_error:
                    logger.warning(f"Feasibility assessment failed, using basic assessment: {feasibility_error}")
                    # Fallback to basic assessment
                    basic_feasibility = self._assess_data_feasibility(result.required_data_columns, available_columns)
                    result.can_be_answered = basic_feasibility.get("can_be_answered", result.can_be_answered)
                    result.feasibility_score = basic_feasibility.get("feasibility_score", result.feasibility_score)
                    result.missing_columns = basic_feasibility.get("missing_columns", result.missing_columns)
                    result.available_alternatives = basic_feasibility.get("available_alternatives", result.available_alternatives)
                    result.data_suggestions = f"Basic assessment used due to LLM error: {str(feasibility_error)}"
            
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
                retrieved_functions=[]
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


# Example usage
if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    
# Example usage
if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    
    async def test_planner():
        # Mock LLM for testing
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
            "suggested_functions": ["variance_analysis"],
            "reasoning": "Question specifically asks for rolling variance analysis with time grouping",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "clarification_needed": null,
            "can_be_answered": true,
            "feasibility_score": 0.9,
            "missing_columns": [],
            "available_alternatives": ["date_column could substitute for timestamp"],
            "data_suggestions": "Ensure timestamp column is in datetime format for proper time series analysis"
        }
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response)
        
        planner = AnalysisIntentPlanner(llm=mock_llm)
        
        # Sample dataframe information
        df_description = "Financial metrics dataset with project performance data"
        df_summary = "Contains 10,000 rows with daily metrics from 2023-2024, covering flux measurements across different organizational units"
        available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments", "revenue", "employee_count"]
        
        test_questions = [
            "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            "Show me user retention over the last 6 months",  # This will have missing columns
            "I want to segment my projects based on performance",
            "What are the trends in revenue?"
        ]
        
        for question in test_questions:
            # Test with all parameters
            result = await planner.classify_intent(
                question=question,
                dataframe_description=df_description,
                dataframe_summary=df_summary,
                available_columns=available_columns
            )
            print(f"\nQuestion: {question}")
            print(f"Intent: {result.intent_type}")
            print(f"Confidence: {result.confidence_score:.2f}")
            print(f"Can be answered: {result.can_be_answered}")
            print(f"Feasibility score: {result.feasibility_score:.2f}")
            print(f"Suggested functions: {result.suggested_functions}")
            print(f"Required columns: {result.required_data_columns}")
            print(f"Missing columns: {result.missing_columns}")
            print(f"Alternatives: {result.available_alternatives}")
            print(f"Specific Matches: {result.specific_function_matches}")
            if result.data_suggestions:
                print(f"Data suggestions: {result.data_suggestions}")
            if result.clarification_needed:
                print(f"Clarification: {result.clarification_needed}")
        
        # Test with minimal parameters (question only)
        print("\n--- Testing with question only ---")
        result_minimal = await planner.classify_intent("What is the variance of my data?")
        print(f"Minimal test - Intent: {result_minimal.intent_type}")
        print(f"Can be answered: {result_minimal.can_be_answered}")
    
    # Test the method signature directly
    def test_method_signature():
        from inspect import signature
        sig = signature(AnalysisIntentPlanner.classify_intent)
        print("Method signature:", sig)
        print("Parameters:")
        for name, param in sig.parameters.items():
            print(f"  {name}: {param.annotation} = {param.default}")
    
    async def test_all_usage_patterns():
        """Test different ways to call classify_intent"""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
            "suggested_functions": ["variance_analysis"],
            "reasoning": "Question specifically asks for rolling variance analysis with time grouping",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "clarification_needed": null,
            "can_be_answered": true,
            "feasibility_score": 0.9,
            "missing_columns": [],
            "available_alternatives": [],
            "data_suggestions": null
        }
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response)
        
        planner = AnalysisIntentPlanner(llm=mock_llm)
        
        print("=== Testing Different Usage Patterns ===")
        
        # First, test the feasibility assessment method directly
        print("\n=== TESTING FEASIBILITY ASSESSMENT DIRECTLY ===")
        required_cols = ["flux", "timestamp", "projects", "cost_centers", "departments"]
        available_cols = ["flux", "timestamp", "projects", "cost_centers", "departments"]
        
        feasibility_test = planner._assess_data_feasibility(required_cols, available_cols)
        print(f"Direct feasibility test (perfect match):")
        print(f"  Can be answered: {feasibility_test['can_be_answered']}")
        print(f"  Feasibility score: {feasibility_test['feasibility_score']}")
        print(f"  Missing columns: {feasibility_test['missing_columns']}")
        
        # Test with missing columns
        available_cols_partial = ["flux", "timestamp", "projects"]
        feasibility_test_partial = planner._assess_data_feasibility(required_cols, available_cols_partial)
        print(f"\nDirect feasibility test (missing columns):")
        print(f"  Can be answered: {feasibility_test_partial['can_be_answered']}")
        print(f"  Feasibility score: {feasibility_test_partial['feasibility_score']}")
        print(f"  Missing columns: {feasibility_test_partial['missing_columns']}")
        
        # Test with the exact parameters mentioned in the issue
        print("\n=== MAIN TEST: With your exact dataframe parameters ===")
        result_main = await planner.classify_intent(
            question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            dataframe_description="Financial metrics dataset with project performance data",
            dataframe_summary="Contains 10,000 rows with daily metrics from 2023-2024",
            available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"]
        )
        
        print(f"Intent: {result_main.intent_type}")
        print(f"Confidence: {result_main.confidence_score}")
        print(f"Can be answered: {result_main.can_be_answered}")
        print(f"Feasibility score: {result_main.feasibility_score}")
        print(f"Required columns: {result_main.required_data_columns}")
        print(f"Missing columns: {result_main.missing_columns}")
        print(f"Available alternatives: {result_main.available_alternatives}")
        print(f"Data suggestions: {result_main.data_suggestions}")
        print(f"Specific function matches: {result_main.specific_function_matches}")
        
        # Test with missing columns to verify feasibility assessment works
        print("\n=== TEST: With missing columns ===")
        
        # Update mock response for missing columns test
        mock_response_missing = Mock()
        mock_response_missing.content = '''
        {
            "intent_type": "cohort_analysis",
            "confidence_score": 0.8,
            "rephrased_question": "Calculate user retention rates over the last 6 months",
            "suggested_functions": ["calculate_retention"],
            "reasoning": "Question asks for user retention analysis over time periods",
            "required_data_columns": ["user_id", "signup_date", "activity_date", "timestamp"],
            "clarification_needed": null,
            "can_be_answered": false,
            "feasibility_score": 0.4,
            "missing_columns": ["user_id", "signup_date", "activity_date"],
            "available_alternatives": ["timestamp might work for activity tracking"],
            "data_suggestions": "Need user identification and activity tracking data"
        }
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response_missing)
        
        result_missing = await planner.classify_intent(
            question="Show me user retention over the last 6 months",
            dataframe_description="Financial metrics dataset",
            dataframe_summary="Contains project data but no user information",
            available_columns=["flux", "timestamp", "projects"]  # Missing user_id
        )
        
        print(f"Intent: {result_missing.intent_type}")
        print(f"Can be answered: {result_missing.can_be_answered}")
        print(f"Feasibility score: {result_missing.feasibility_score}")
        print(f"Missing columns: {result_missing.missing_columns}")
        print(f"Data suggestions: {result_missing.data_suggestions}")
        
        return "All tests completed successfully!"
    
    print("=== Testing Method Signature ===")
    test_method_signature()
    
    print("\n=== Running Usage Pattern Tests ===")
    test_result = asyncio.run(test_all_usage_patterns())
    print(f"\nOverall result: {test_result}")
    
    print("\n=== Example Usage ===")
    print("""
# Example 1: Basic usage
planner = AnalysisIntentPlanner(llm=your_llm)
result = await planner.classify_intent("What is the variance?")

# Example 2: With dataframe context
result = await planner.classify_intent(
    question="How does variance change over time?",
    dataframe_description="Financial metrics dataset", 
    dataframe_summary="Contains daily metrics from 2023-2024",
    available_columns=["flux", "timestamp", "projects"]
)

# Example 3: Check what you get back
print(f"Intent: {result.intent_type}")
print(f"Can answer: {result.can_be_answered}")  
print(f"Feasibility: {result.feasibility_score}")
print(f"Functions: {result.suggested_functions}")
print(f"Missing columns: {result.missing_columns}")
    """)
    
    asyncio.run(test_planner())