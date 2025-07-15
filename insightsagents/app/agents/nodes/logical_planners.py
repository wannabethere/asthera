from typing import TypedDict, Annotated, List, Dict, Any, Optional, Callable, Tuple
from typing_extensions import NotRequired
import operator
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import os
import json
import asyncio
import re
import datetime
import chromadb
from app.storage.documents import DocumentChromaStore, CHROMA_STORE_PATH

FUNCTIONS_AVAILABLE = [
            
  {"name": "form_time_cohorts", "category": "cohort_analysis", "description": "Form cohorts based on time periods" },
  {"name": "form_behavioral_cohorts", "category": "cohort_analysis", "description": "Form cohorts based on user behavior" },
  {"name": "calculate_retention", "category": "cohort_analysis", "description": "Calculate retention metrics for cohorts" },
  {"name": "calculate_conversion", "category": "cohort_analysis", "description": "Calculate conversion funnel metrics for cohorts" },
  {"name": "calculate_lifetime_value", "category": "cohort_analysis", "description": "Calculate lifetime value metrics for cohorts" },
  {"name": "analyze_funnel", "category": "funnel_analysis", "description": "Analyze a user funnel using the existing CohortPipe framework" },
  {"name": "analyze_funnel_by_time", "category": "funnel_analysis", "description": "Analyze funnel performance over time using the existing CohortPipe framework" },
  {"name": "analyze_funnel_by_segment", "category": "funnel_analysis", "description": "Analyze funnel performance by user segments" },
  {"name": "analyze_user_paths", "category": "funnel_analysis", "description": "Analyze common user paths through the funnel" },
  {"name": "get_funnel_summary", "category": "funnel_analysis", "description": "Get a summary of funnel analysis results" },
  {"name": "compare_segments", "category": "funnel_analysis", "description": "Compare funnel performance across different segments" },
  {"name": "lead", "category": "time_series_analysis", "description": "Create lead (future) values for specified columns" },
  {"name": "lag", "category": "time_series_analysis", "description": "Create lag (past) values for specified columns" },
  {"name": "variance_analysis", "category": "time_series_analysis", "description": "Calculate variance and standard deviation for time series data" },
  {"name": "distribution_analysis", "category": "time_series_analysis", "description": "Analyze the distribution of values in specified columns" },
  {"name": "cumulative_distribution", "category": "time_series_analysis", "description": "Calculate cumulative distribution for specified columns" },
  {"name": "custom_calculation", "category": "time_series_analysis", "description": "Apply a custom calculation function to the time series data" },
  {"name": "dbscan", "category": "segmentation", "description": "DBSCAN Clustering for segmentation" },
  {"name": "hierarchical", "category": "segmentation", "description": "Hierarchical Clustering for segmentation" },
  {"name": "rule_based", "category": "segmentation", "description": "Rule-Based Segmentation" },
  {"name": "generate_summary", "category": "segmentation", "description": "Segment Summary Generator" },
  {"name": "get_segment_data", "category": "segmentation", "description": "Segment Data Extractor" },
  {"name": "compare_algorithms", "category": "segmentation", "description": "Algorithm Comparison" },
  {"name": "aggregate_by_time", "category": "trend_analysis", "description": "Aggregate data by time periods" },
  {"name": "calculate_growth_rates", "category": "trend_analysis", "description": "Calculate growth rates for aggregated metrics" },
  {"name": "calculate_moving_average", "category": "trend_analysis", "description": "Calculate moving averages for time series data" },
  {"name": "decompose_trend", "category": "trend_analysis", "description": "Decompose time series into trend, seasonal, and residual components" },
  {"name": "forecast_metric", "category": "trend_analysis", "description": "Forecast future values of    a metric" },
  {"name": "calculate_statistical_trend", "category": "trend_analysis", "description": "Calculate statistical significance of trends" },
  {"name": "compare_periods", "category": "trend_analysis", "description": "Compare metrics across different time periods" },
  {"name": "get_top_metrics", "category": "trend_analysis", "description": "Get top performing metrics based on specified criteria" },
  {"name": "fit_distribution", "category": "risk_analysis", "description": "Fit probability distributions to data using maximum likelihood estimation" },
  {"name": "calculate_var", "category": "risk_analysis", "description": "Calculate Value at Risk (VaR) using various methods" },
  {"name": "calculate_cvar", "category": "risk_analysis", "description": "Calculate Conditional Value at Risk (CVaR/Expected Shortfall)" },
  {"name": "calculate_portfolio_risk", "category": "risk_analysis", "description": "Calculate portfolio risk metrics including diversification effects" },
  {"name": "monte_carlo_simulation", "category": "risk_analysis", "description": "Perform Monte Carlo simulation for risk assessment" },
  {"name": "stress_test", "category": "risk_analysis", "description": "Perform stress testing with specified scenarios" },
  {"name": "rolling_risk_metrics", "category": "risk_analysis", "description": "Calculate rolling risk metrics over time" },
  {"name": "correlation_analysis", "category": "risk_analysis", "description": "Perform correlation analysis for risk assessment" },
  {"name": "risk_attribution", "category": "risk_analysis", "description": "Perform risk attribution analysis for portfolio components" },
  {"name": "compare_distributions", "category": "risk_analysis", "description": "Compare multiple distribution fits and select the best one" },
  {"name": "get_risk_summary", "category": "risk_analysis", "description": "Get a summary of all risk analysis results" },
]


def format_functions_for_prompt(functions_list: List[Dict[str, str]]) -> str:
    """
    Format the list of available functions into a string for the prompt.
    
    Args:
        functions_list: List of dictionaries containing function information
        
    Returns:
        str: Formatted string of functions with | separation
    """
    formatted_functions = []
    for func in functions_list:
        formatted_func = f"{func['name']} ({func['category']}): {func['description']}"
        formatted_functions.append(formatted_func)
    
    return " | ".join(formatted_functions)

# Example usage:
# formatted_functions = format_functions_for_prompt(FUNCTIONS_AVAILABLE)




# Define the state structure for our data science planner
class DataSciencePlanState(TypedDict):
    # Input question to be analyzed
    question: str
    # Context provided for analysis
    context: NotRequired[Dict[str, Any]]
    # Type of logical planner to use
    planner_type: NotRequired[str]
    # Retrieved documents from retrieval node
    retrieved_docs: NotRequired[List[Dict[str, Any]]]
    # The generated plan steps
    plan: NotRequired[List[str]]
    # Document relevance grades
    doc_grades: NotRequired[Dict[str, float]]
    # Question-plan relevance score
    relevance_score: NotRequired[float]
    # Reasoning extracted from model output
    extracted_reasoning: NotRequired[str]
    # Individual scoring components
    relevance_components: NotRequired[Dict[str, float]]
    # Recommended next steps
    recommendations: NotRequired[List[str]]
    # Metadata and tracking
    metadata: NotRequired[Dict[str, Any]]

# Planner prompt template
DATA_SCIENTIST_PLANNER_PROMPT = """
You are an expert data scientist tasked with creating a logical step-by-step plan to answer a data science question.

CONTEXT:
{context}

QUESTION:
{question}

PLANNER TYPE:
{planner_type}

RETRIEVED DOCUMENTS:
{retrieved_docs}

FUNCTIONS AVAILABLE:
{functions_available}

As a data scientist, create a detailed plan with the following characteristics:
1. Break down the problem into logical, sequential steps
2. Include data collection, preprocessing, analysis, and visualization steps as needed
3. Determine the operation type as Cohort Analysis, Segmentation, Time Series, Risk analysis, Trend analysis, Metric analysis, Operation analysis
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
8. For each step, Indicate whether the operation is a cohort analysis, segmentation, time series, risk analysis, trend analysis, metric analysis, operation analysis
9. Each step should use a function from the functions available + a possible SQL operation. If there is a choice between function available and SQL operation, use the function.
10. For each step, identify the set of possible columns that can be used for the operation. 
11. Include steps for validation and interpretation of results
12. Align your approach with the specified planner type
13. If the question involves a pipeline pattern, ensure your plan properly addresses the sequential flow of operations
14. Incorporate detailed reasoning about your approach
16. If the question involves a time series operation, ensure your plan properly addresses the time series operation
18. If the question involves a cohort analysis operation, ensure your plan properly addresses the cohort analysis operation
19. If the question involves a segmentation operation, ensure your plan properly addresses the segmentation operation
20. If the question involves a trend analysis operation, ensure your plan properly addresses the trend analysis operation
21. If the question involves a metric analysis operation, ensure your plan properly addresses the metric analysis operation
22. If the question involves a operation analysis operation, ensure your plan properly addresses the operation analysis operation
23. If the question involves a risk analysis operation, ensure your plan properly addresses the risk analysis operation
24. Your plan should be thorough enough that another data scientist could follow it to answer the question.
First provide your REASONING about how to approach this problem, then output the numbered steps of your plan, with one step per line.

Format:
REASONING: [Your detailed reasoning here]
IMPORTANT: Please ignore any visualization operations. 
Output PLAN in the following format:
(1. First step: type of operation : possible functions : possible columns list : possible SQL operation for each column as natural language) | (2. Second step: type of operation : possible functions : possible columns list : possible SQL operation for each column as natural language) | ...and so on
"""

# Document grading prompt
DOC_GRADING_PROMPT = """
You are a data science expert evaluating the relevance of retrieved documents for answering a data science question.

QUESTION:
{question}

PLAN:
{plan}

RETRIEVED DOCUMENTS:
{retrieved_docs}

For each document, evaluate its relevance to answering the question and executing the plan.
Score each document from 0.0 (completely irrelevant) to 1.0 (perfectly relevant).

Consider:
- How directly the document relates to the question's domain
- If it contains information needed for the planned analysis steps
- The quality and completeness of the data or information it provides
- Whether it addresses the specific data science tasks in the plan

Output your evaluation as a JSON object with document IDs as keys and scores as values.
"""

# Recommendation prompt
RECOMMENDATION_PROMPT = """
You are a data science expert recommending next steps based on a plan and document evaluation.

QUESTION:
{question}

PLAN:
{plan}

RETRIEVED DOCUMENTS:
{retrieved_docs}

DOCUMENT GRADES:
{doc_grades}

RELEVANCE SCORE:
{relevance_score}

Based on the plan, available documents, and relevance assessments, recommend the next steps to move forward.

Consider:
- If additional documents or data sources are needed
- Which specific agents or APIs would be most suitable for each step
- Any refinements needed to the plan based on document availability
- Alternative approaches if the current plan has low relevance or insufficient documentation

Provide 3-5 clear, actionable recommendations for the next steps.
"""

"""
 "sql": {
                "terms": ["table", "column", "join", "select", "from", "where", 
                          "group by", "order by", "having", "union", "insert", 
                          "update", "delete", "create", "alter", "index", "view", 
                          "query", "subquery", "database", "schema"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },

"machine_learning": {
                "terms": ["model", "train", "test", "validation", "accuracy", "precision",
                         "recall", "f1", "roc", "auc", "cross-validation", "hyperparameter",
                         "feature selection", "feature engineering", "regression", "classification",
                         "decision tree", "random forest", "neural network", "deep learning",
                         "supervised", "unsupervised", "reinforcement", "overfitting", "underfitting"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
 "data_processing": {
                "terms": ["clean", "preprocess", "impute", "missing", "outlier", "normalize", "scale",
                         "encode", "decode", "tokenize", "parse", "extract", "transform", "format"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "general_analysis": {
                "terms": ["data", "analysis", "visualization", "preprocessing", "statistics",
                         "correlation", "causation", "hypothesis", "insight", "metric", 
                         "dashboard", "report", "chart", "graph", "plot", "aggregate", 
                         "summarize", "filter", "transform", "clean", "normalize"],
                "max_score": 0.15,
                "min_match_threshold": 2
            },

"""

class OperationTerminologyConfig:
    """Configuration class for operation terminology"""
    
    DEFAULT_CONFIG = {
        "reasoning_weight": 0.7,
        "terminology_value": 0.03,
        "length_score_thresholds": {
            "long": {"threshold": 50, "score": 0.20},
            "medium": {"threshold": 25, "score": 0.15},
            "short": {"threshold": 10, "score": 0.10},
            "very_short": {"score": 0.05}
        },
        "operations": {  
            "cohort_analysis": {
                "terms": ["cohort", "retention", "churn", "lifetime value", "ltv", 
                         "customer segmentation", "behavioral cohorts", "value segment", 
                         "transaction", "time period", "cumulative", "from_dataframe", 
                         "calculate_lifetime_value", "form_behavioral_cohorts",
                         "CohortPipe", "time_period", "max_periods"],
                "max_score": 0.25,
                "min_match_threshold": 2
            },
            "segmentation": {
                "terms": ["segmentation", "clustering", "kmeans", "dbscan", "hierarchical",
                         "features", "recency", "frequency", "monetary", "rfm", "cluster",
                         "segment", "eps", "min_samples", "linkage", "ward", "n_clusters",
                         "SegmentationPipe", "get_features", "run_kmeans", "run_dbscan",
                         "run_hierarchical", "compare_algorithms"],
                "max_score": 0.25,
                "min_match_threshold": 2
            },
            "time_series": {
                "terms": ["time series", "forecast", "trend", "seasonal", "decomposition",
                         "arima", "sarima", "prophet", "exponential smoothing", "moving average",
                         "autocorrelation", "stationarity", "periodicity", "seasonality",
                         "prediction interval", "lag", "rolling window", "resampling"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "metrics": {
                "terms": ["metrics", "metric", "kpi", "value", "score", "accuracy", "precision",
                         "recall", "f1", "roc", "auc", "cross-validation", "hyperparameter",
                         "feature selection", "feature engineering", "regression", "classification",
                         "decision tree", "random forest", "neural network", "deep learning",
                         "supervised", "unsupervised", "reinforcement", "overfitting", "underfitting"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "operations": {
                "terms": ["filter", "group", "sort", "join", "merge", "concat", "append", "split",
                         "transform", "convert", "calculate", "compute", "derive", "normalize",
                         "standardize", "rescale", "change", "difference", "delta", "comparison"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "aggregation": {
                "terms": ["aggregate", "summarize", "groupby", "pivot", "rollup", "cube", "crosstab",
                         "total", "subtotal", "accumulate", "collect", "combine", "condense"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "trends": {
                "terms": ["trend", "pattern", "anomaly", "outlier", "seasonality", "cyclical", "growth",
                         "decay", "increase", "decrease", "spike", "dip", "volatility", "stability"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "risk_analysis": {
                "terms": ["risk", "var", "value at risk", "cvar", "expected shortfall", "conditional var",
                         "volatility", "portfolio risk", "diversification", "correlation matrix",
                         "monte carlo", "simulation", "stress test", "scenario analysis", "rolling risk",
                         "risk attribution", "component risk", "marginal risk", "risk decomposition",
                         "distribution fit", "maximum likelihood", "mle", "aic", "bic", "log likelihood",
                         "normal distribution", "student t", "skewed normal", "gev", "extreme value",
                         "tail risk", "fat tails", "heavy tails", "kurtosis", "skewness", "moments",
                         "confidence level", "quantile", "percentile", "bootstrap", "parametric",
                         "historical simulation", "risk metrics", "risk assessment", "risk management",
                         "financial risk", "market risk", "credit risk", "operational risk", "liquidity risk",
                         "systematic risk", "idiosyncratic risk", "beta", "alpha", "sharpe ratio", "sortino ratio",
                         "information ratio", "tracking error", "downside deviation", "upside potential",
                         "risk adjusted return", "risk free rate", "excess return", "risk premium",
                         "RiskPipe", "fit_distribution", "calculate_var", "calculate_cvar", "calculate_portfolio_risk",
                         "monte_carlo_simulation", "stress_test", "rolling_risk_metrics", "correlation_analysis",
                         "risk_attribution", "compare_distributions", "get_risk_summary"],
                "max_score": 0.25,
                "min_match_threshold": 2
            }
        },
        "step_patterns": [
            r"first.*then", r"step\s*\d+", r"initially.*next", 
            r"begin by.*then", r"\d+\)\s", r"•\s", r"-\s", 
            r"firstly.*secondly", r"start.*then"
        ],
        "step_indicators_score": 0.15,
        "pipeline_indicators": [
            r"pipe(?:line)?", r"sequential", r"step[s]? (?:that|which) feed into", 
            r"output (?:of|from).*becomes input", r"chained operations", 
            r"series of transformations", r"\|", r"output.*feeds into",
            r"CohortPipe", r"SegmentationPipe", r"RiskPipe", r"from_dataframe", r"\.from_dataframe",
            r"TimeSeriesPipe", r"TrendAnalysisPipe", r"MetricPipe", r"FeaturePipe", r"OperationPipe",
        ],
        "pipeline_score_value": 0.05,
        "pipeline_max_score": 0.25,
        "data_field_score_value": 0.05,
        "data_field_max_score": 0.30
    }
    
    @classmethod
    def load_from_file(cls, file_path: str = None) -> dict:
        """
        Load configuration from a JSON file, falling back to defaults if file doesn't exist
        
        Args:
            file_path: Path to the configuration JSON file
            
        Returns:
            Configuration dictionary
        """
        # Start with default config
        config = cls.DEFAULT_CONFIG.copy()
        
        # If a file path is provided, try to load it
        if file_path:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        # Load from file and update default config
                        file_config = json.load(f)
                        cls._deep_update(config, file_config)
                    print(f"Loaded operation terminology config from {file_path}")
                else:
                    print(f"Config file {file_path} not found, using default configuration")
            except Exception as e:
                print(f"Error loading config file: {e}")
                print("Using default configuration")
        
        return config
    
    @staticmethod
    def _deep_update(original: dict, update: dict) -> dict:
        """
        Recursively update a dictionary
        
        Args:
            original: Original dictionary to update
            update: Dictionary with updates
            
        Returns:
            Updated dictionary
        """
        for key, value in update.items():
            if key in original and isinstance(original[key], dict) and isinstance(value, dict):
                OperationTerminologyConfig._deep_update(original[key], value)
            else:
                original[key] = value
        return original
    
    @classmethod
    def save_default_config(cls, file_path: str) -> None:
        """
        Save the default configuration to a JSON file
        
        Args:
            file_path: Path to save the configuration
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(cls.DEFAULT_CONFIG, f, indent=2)
            print(f"Default configuration saved to {file_path}")
        except Exception as e:
            print(f"Error saving default configuration: {e}")


class AdvancedRelevanceScorer:
    """
    Implements the advanced relevance scoring system based on the flowchart.
    This evaluates the reasoning component of a data science plan and supports various operations.
    """
    
    def __init__(self, config_file_path: str = None, context: dict = None):
        """
        Initialize the scoring system
        
        Args:
            config_file_path: Path to the configuration JSON file (optional)
            context: Optional context containing schema or domain information
        """
        # Load configuration
        self.config = OperationTerminologyConfig.load_from_file(config_file_path)
        self.context = context or {}
        
        # Extract key parameters from config
        self.reasoning_weight = self.config.get("reasoning_weight", 0.7)
        self.terminology_value = self.config.get("terminology_value", 0.03)
        self.operations = self.config.get("operations", {})
    
    def _extract_reasoning(self, model_output: str) -> str:
        """Extract the reasoning section from the model output"""
        if "REASONING:" in model_output and "PLAN:" in model_output:
            reasoning_part = model_output.split("REASONING:")[1].split("PLAN:")[0].strip()
            return reasoning_part
        return model_output  # Return full text if specific format not found
    
    def _calculate_length_score(self, reasoning: str) -> float:
        """Calculate score based on number of words"""
        word_count = len(reasoning.split())
        thresholds = self.config.get("length_score_thresholds", {})
        
        # Check thresholds from longest to shortest
        if "long" in thresholds and word_count >= thresholds["long"].get("threshold", 50):
            return thresholds["long"].get("score", 0.20)
        elif "medium" in thresholds and word_count >= thresholds["medium"].get("threshold", 25):
            return thresholds["medium"].get("score", 0.15)
        elif "short" in thresholds and word_count >= thresholds["short"].get("threshold", 10):
            return thresholds["short"].get("score", 0.10)
        else:
            return thresholds.get("very_short", {}).get("score", 0.05)
    
    def _detect_operation_type(self, question: str, reasoning: str) -> Tuple[str, Optional[dict]]:
        """
        Detect the type of data operation from the question and reasoning
        
        Returns:
            Tuple of (operation_type, operation_config)
        """
        # Get all operations from config
        operations = self.config.get("operations", {})
        
        # Count terms from each category in question and reasoning
        combined_text = (question + " " + reasoning).lower()
        term_counts = {}
        
        for op_name, op_config in operations.items():
            terms = op_config.get("terms", [])
            count = sum(1 for term in terms if term.lower() in combined_text)
            term_counts[op_name] = count
        
        # Find the category with the most matches
        if term_counts:
            best_category = max(term_counts.items(), key=lambda x: x[1])
            
            # Check if it meets minimum threshold
            operation_config = operations.get(best_category[0], {})
            min_threshold = operation_config.get("min_match_threshold", 2)
            
            if best_category[1] >= min_threshold:
                return best_category[0], operation_config
        
        # If no significant matches found or below threshold, default to general analysis
        default_op = "general_analysis"
        return default_op, operations.get(default_op, {})
    
    def _calculate_terminology_score(self, reasoning: str, question: str) -> dict:
        """Calculate score based on terminology specific to the operation type"""
        # Detect operation type
        operation_type, operation_config = self._detect_operation_type(question, reasoning)
        
        # If no specific operation config
        if not operation_config:
            # Use general analysis as fallback
            general_op = self.operations.get("general_analysis", {})
            general_terms = general_op.get("terms", [])
            max_score = general_op.get("max_score", 0.15)
            
            term_count = sum(1 for term in general_terms if term.lower() in reasoning.lower())
            return {
                "name": "general_data_terminology",
                "score": min(max_score, term_count * self.terminology_value),
                "term_count": term_count,
                "operation_type": "general_analysis"
            }
        
        # Get parameters from operation config
        terms = operation_config.get("terms", [])
        max_score = operation_config.get("max_score", 0.20)
        
        # Count terms specific to the detected operation type
        term_count = sum(1 for term in terms if term.lower() in reasoning.lower())
        
        # Apply formula: min(max_score, terms × terminology_value)
        return {
            "name": f"{operation_type}_terminology",
            "score": min(max_score, term_count * self.terminology_value),
            "term_count": term_count,
            "operation_type": operation_type
        }
    
    def _calculate_structure_score(self, reasoning: str) -> float:
        """Calculate score based on structure (number of lines)"""
        lines = [line for line in reasoning.split('\n') if line.strip()]
        
        if len(lines) >= 3:
            return 0.15
        elif len(lines) >= 2:
            return 0.10
        else:
            return 0.05
    
    def _check_step_indicators(self, reasoning: str) -> float:
        """Check if reasoning contains step patterns"""
        step_patterns = self.config.get("step_patterns", [
            r"first.*then", r"step\s*\d+", r"initially.*next", 
            r"begin by.*then", r"\d+\)\s", r"•\s", r"-\s", 
            r"firstly.*secondly", r"start.*then"
        ])
        
        step_score = self.config.get("step_indicators_score", 0.15)
        
        for pattern in step_patterns:
            if re.search(pattern, reasoning, re.IGNORECASE):
                return step_score
        return 0.0
    
    def _calculate_data_field_mentions_score(self, reasoning: str, question: str, operation_type: str) -> float:
        """
        Calculate score based on mentions of relevant data fields from context
        This is a more general version of the schema mentions score that works for various operations
        """
        if not self.context:
            return 0.0
        
        # Get scoring parameters from config
        data_field_score_value = self.config.get("data_field_score_value", 0.05)
        data_field_max_score = self.config.get("data_field_max_score", 0.30)
        
        # Get relevant fields based on operation type
        fields = []
        
        # Extract data fields from context based on operation type
        if operation_type == "sql" and "schema" in self.context:
            # For SQL, look for table and column names
            schema = self.context.get("schema", {})
            if isinstance(schema, dict):
                fields = list(schema.keys())  # Tables
                for table_cols in schema.values():
                    if isinstance(table_cols, list):
                        fields.extend(table_cols)  # Columns
        
        elif operation_type == "cohort_analysis":
            # For cohort analysis, look for user_id, date columns, value columns
            if "columns" in self.context:
                # Prioritize time and user-related columns
                for col in self.context.get("columns", []):
                    fields.append(col)
                    # Give extra weight to important cohort analysis fields
                    if any(term in col.lower() for term in ["date", "time", "user", "customer", "id", "value", "amount", "revenue"]):
                        fields.append(col)  # Add twice for higher weight
        
        elif operation_type == "segmentation":
            # For segmentation, look for feature columns
            if "features" in self.context:
                fields.extend(self.context.get("features", []))
            if "columns" in self.context:
                # Prioritize feature-like columns
                for col in self.context.get("columns", []):
                    fields.append(col)
                    # Extra weight to typical segmentation features
                    if any(term in col.lower() for term in ["age", "income", "frequency", "recency", "monetary", "segment"]):
                        fields.append(col)
        
        elif operation_type == "risk_analysis":
            # For risk analysis, look for return columns, price columns, portfolio components
            if "columns" in self.context:
                # Prioritize risk-related columns
                for col in self.context.get("columns", []):
                    fields.append(col)
                    # Extra weight to typical risk analysis fields
                    if any(term in col.lower() for term in ["return", "price", "volatility", "var", "risk", "portfolio", "asset", "stock", "bond", "commodity", "currency", "fx", "rate", "yield", "spread", "beta", "alpha", "sharpe", "sortino"]):
                        fields.append(col)  # Add twice for higher weight
        
        else:
            # For general or other types, extract all potential data fields from context
            context_str = str(self.context)
            fields = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', context_str)
            # Also check for any dataframe mentions
            if "dataframe" in self.context:
                df_info = self.context.get("dataframe", {})
                if isinstance(df_info, dict) and "columns" in df_info:
                    fields.extend(df_info.get("columns", []))
        
        # Also add any fields explicitly mentioned in the question
        question_fields = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*(?:_column|_id|_date|_value))\b', question)
        fields.extend(question_fields)
        
        # Count mentions of data fields
        mention_count = 0
        for field in fields:
            if len(field) > 2:  # Ignore very short field names
                mentions = len(re.findall(r'\b' + re.escape(field) + r'\b', reasoning, re.IGNORECASE))
                mention_count += mentions
        
        # Apply formula from config
        return min(data_field_max_score, mention_count * data_field_score_value)
    
    def _calculate_pipeline_structure_score(self, reasoning: str, question: str, operation_type: str) -> float:
        """
        Calculate score based on whether the reasoning correctly addresses pipeline structure
        for operations like CohortPipe or SegmentationPipe
        """
        # Check if the question involves a pipeline pattern
        has_pipe_pattern = "|" in question or "pipe" in question.lower() or "pipeline" in question.lower()
        
        # If no pipeline in question, return 0
        if not has_pipe_pattern:
            return 0.0
        # Get pipeline indicators from config
        pipeline_indicators = self.config.get("pipeline_indicators", [
            r"pipe(?:line)?", r"sequential", r"step[s]? (?:that|which) feed into", 
            r"output (?:of|from).*becomes input", r"chained operations", 
            r"series of transformations", r"\|", r"output.*feeds into",
            r"CohortPipe", r"SegmentationPipe",r"TimeSeriesPipe", r"TrendAnalysisPipe", 
            r"MetricPipe",  r"OperationPipe", r"from_dataframe", r"\.from_dataframe",
        ])
        
        
        pipeline_score_value = self.config.get("pipeline_score_value", 0.05)
        pipeline_max_score = self.config.get("pipeline_max_score", 0.25)
        
        # Count pipeline indicators
        indicator_count = 0
        for indicator in pipeline_indicators:
            matches = re.findall(indicator, reasoning, re.IGNORECASE)
            indicator_count += len(matches)
        
        # Check for sequential steps understanding
        if re.search(r"(?:first|1st).*(?:then|next|followed by).*(?:then|next|followed by|finally)", reasoning, re.IGNORECASE):
            indicator_count += 1
        
        # Additional points for operation-specific pipeline understanding
        if operation_type == "cohort_analysis" and re.search(r"form.*cohorts.*(?:then|before).*calculate", reasoning, re.IGNORECASE):
            indicator_count += 2
            
        if operation_type == "segmentation" and re.search(r"features.*(?:then|before).*(?:cluster|segment)", reasoning, re.IGNORECASE):
            indicator_count += 2
            
        if operation_type == "risk_analysis" and re.search(r"(?:fit.*distribution|calculate.*var).*(?:then|before).*(?:portfolio|stress|simulation)", reasoning, re.IGNORECASE):
            indicator_count += 2
        
        # Apply scoring formula from config
        return min(pipeline_max_score, indicator_count * pipeline_score_value)
    
    def score_reasoning(self, model_output, question):
        """
        Score the reasoning from the model output
        
        Args:
            model_output: The complete output from the model
            question: The question being answered
            
        Returns:
            Dictionary with components and final score
        """
        # Extract reasoning
        reasoning = self._extract_reasoning(model_output)
        
        # Detect operation type
        operation_type, _ = self._detect_operation_type(question, reasoning)
        
        # Calculate component scores
        length_score = self._calculate_length_score(reasoning)
        
        # Get terminology score and operation type
        terminology_result = self._calculate_terminology_score(reasoning, question)
        terminology_score = terminology_result["score"]
        detected_operation = terminology_result["operation_type"]
        
        structure_score = self._calculate_structure_score(reasoning)
        step_score = self._check_step_indicators(reasoning)
        
        # Calculate data field mentions score
        data_field_score = self._calculate_data_field_mentions_score(reasoning, question, detected_operation)
        
        # Calculate pipeline structure score for questions with pipeline patterns
        pipeline_score = self._calculate_pipeline_structure_score(reasoning, question, detected_operation)
        
        # Combine scores
        component_scores = {
            "length_score": length_score,
            f"{detected_operation}_terminology_score": terminology_score,
            "structure_score": structure_score,
            "step_indicators_score": step_score,
            "data_field_mentions_score": data_field_score
        }
        
        # Add pipeline score if applicable
        if pipeline_score > 0:
            component_scores["pipeline_structure_score"] = pipeline_score
        
        # Calculate combined score
        combined_score = sum(component_scores.values())
        
        # Scale by reasoning_weight
        final_score = combined_score * self.reasoning_weight
        
        # Cap at 1.0
        final_score = min(1.0, final_score)
        
        # Add metadata about detected operation
        component_scores["detected_operation_type"] = detected_operation
        component_scores["combined_score"] = combined_score
        component_scores["reasoning_weight"] = self.reasoning_weight
        
        # Return components and final score
        return {
            "extracted_reasoning": reasoning,
            "relevance_components": component_scores,
            "relevance_score": final_score
        }

class DataScienceLogicalPlanner:
    """
    A logical planner for data science tasks that creates plans without executing them.
    This planner coordinates with external agents/APIs for execution.
    """
    
    def __init__(self, 
                 llm=None, 
                 examples_vectorstore=None,
                 functions_vectorstore=None,
                 insights_vectorstore=None,
                 relevance_scorer=None):
        """
        Initialize the Data Science Logical Planner
        
        Args:
            llm: Language model to use (defaults to ChatOpenAI if None)
            retrieval_agent_endpoint: API endpoint for the retrieval agent
            relevance_scorer: Advanced relevance scoring system
        """
        self.llm = llm if llm else ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
        self.examples_vectorstore = examples_vectorstore
        self.functions_vectorstore = functions_vectorstore
        self.insights_vectorstore = insights_vectorstore
        
        # Create the relevance scorer or use provided one
        if relevance_scorer:
            self.relevance_scorer = relevance_scorer
        else:
            self.relevance_scorer = AdvancedRelevanceScorer()
    
    async def _call_retrieval_agent(self, question, context=None):
        """
        Call the external retrieval agent to retrieve relevant documents
        
        Args:
            question: The data science question
            context: Additional context for retrieval
            
        Returns:
            List of retrieved documents
        """
        # If a real endpoint is provided, call it
        if self.examples_vectorstore:
            try:
                # This would be an actual API call in production
                # Example using aiohttp (would need to be imported)
                # async with aiohttp.ClientSession() as session:
                #     async with session.post(
                #         self.retrieval_agent_endpoint,
                #         json={"question": question, "context": context}
                #     ) as response:
                #         return await response.json()
                retrieved_exampes_docs = self.examples_vectorstore.semantic_search(question, k=2) 
                retrieved_functions_docs = self.functions_vectorstore.semantic_search(question, k=2) 
                retrieved_insights_docs = self.insights_vectorstore.semantic_search(question, k=2) 
                retrieved_docs = retrieved_exampes_docs + retrieved_functions_docs + retrieved_insights_docs
                return retrieved_docs
            except Exception as e:
                print(f"Error calling retrieval agent: {e}")
                # Fall back to dummy docs if API call fails
        
        # For demonstration purposes, return dummy documents
        return [
            {
                "id": "doc1",
                "title": "Customer Demographics Analysis",
                "content": "Analysis of e-commerce customer demographics including age, gender, location, and purchase history.",
                "source": "Internal Database",
                "metadata": {"date": "2024-02-15", "author": "Data Team"}
            },
            {
                "id": "doc2",
                "title": "Purchase Pattern Trends",
                "content": "Quarterly report on customer purchase patterns across different product categories.",
                "source": "Quarterly Report",
                "metadata": {"date": "2024-03-30", "author": "Marketing Analytics"}
            },
            {
                "id": "doc3",
                "title": "Data Dictionary",
                "content": "Definitions and descriptions of all fields in the e-commerce database including tables: customers, orders, products with columns such as customer_id, age, gender, location, order_id, order_date, product_id, category.",
                "source": "Documentation",
                "metadata": {"date": "2024-01-10", "author": "Data Engineering"}
            }
        ]
    
    
    async def _create_plan(self, question: str, context: dict, planner_type: str, retrieved_docs: list) -> tuple[list, str]:
        """
        Generate plan steps from the retrieved documents and context.
        
        Args:
            question: The data science question
            context: Additional context for planning
            planner_type: Type of planner to use
            retrieved_docs: List of retrieved documents
            
        Returns:
            Tuple of (list of plan steps, full model output)
        """
        docs_formatted = "\n".join([
            f"Document {i+1} - {doc.get('title', 'Untitled')}:\n{doc.get('content', 'No content')}\n"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        
        # Create the prompt
        planner_prompt = ChatPromptTemplate.from_template(DATA_SCIENTIST_PLANNER_PROMPT)
        
        # Format the prompt with the current state information
        prompt_args = {
            "question": question,
            "context": str(context) if context else "No additional context provided.",
            "planner_type": planner_type,
            "retrieved_docs": docs_formatted,
            "functions_available": json.dumps(FUNCTIONS_AVAILABLE)
        }
        
        # Invoke the LLM to generate the plan
        chain = planner_prompt | self.llm
        response = await chain.ainvoke(prompt_args)
        full_output = response.content
        
        # Extract plan steps
        plan_steps = []
        if "PLAN:" in full_output:
            plan_section = full_output.split("PLAN:")[1].strip()
            plan_steps = [
                step.strip() 
                for step in re.findall(r'\d+\.\s*(.*?)(?=\n\d+\.|\Z)', plan_section + "\n", re.DOTALL)
                if step.strip() and not step.strip().isspace()
            ]
        else:
            # Fallback if PLAN section not found, try to extract numbered lines
            plan_steps = [
                step.strip() 
                for step in re.findall(r'\d+\.\s*(.*?)(?=\n\d+\.|\Z)', full_output + "\n", re.DOTALL)
                if step.strip() and not step.strip().isspace()
            ]
        
        return plan_steps, full_output
    
    async def _grade_documents(self, question, plan, retrieved_docs):
        """
        Grade the retrieved documents for relevance
        
        Args:
            question: The data science question
            plan: The generated plan
            retrieved_docs: Documents from retrieval
            
        Returns:
            Dictionary of document IDs and their relevance scores
        """
        # Format the plan and docs for the prompt
        plan_formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan)])
        
        docs_formatted = "\n".join([
            f"Document {i+1} - {doc.get('title', 'Untitled')} (ID: {doc.get('id', f'doc{i+1}')}): {doc.get('content', 'No content')}"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        # Create the prompt
        doc_grading_prompt = ChatPromptTemplate.from_template(DOC_GRADING_PROMPT)
        
        # Format the prompt
        prompt_args = {
            "question": question,
            "plan": plan_formatted,
            "retrieved_docs": docs_formatted
        }
        
        # Invoke the LLM for document grading
        chain = doc_grading_prompt | self.llm
        response = await chain.ainvoke(prompt_args)
        
        # Parse the JSON response
        try:
            # Extract JSON from the response if needed
            response_text = response.content
            # Find JSON in the response if not a pure JSON response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                grades = json.loads(json_str)
            else:
                # Fallback if no JSON found
                grades = {}
                for doc in retrieved_docs:
                    doc_id = doc.get('id', f"doc{retrieved_docs.index(doc)+1}")
                    grades[doc_id] = 0.5  # Default score
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            grades = {}
            for doc in retrieved_docs:
                doc_id = doc.get('id', f"doc{retrieved_docs.index(doc)+1}")
                grades[doc_id] = 0.5  # Default score
        
        # Ensure all grades are floats
        grades_float = {}
        for doc_id, grade in grades.items():
            try:
                grades_float[doc_id] = float(grade)
            except (ValueError, TypeError):
                grades_float[doc_id] = 0.5  # Default to 0.5 if conversion fails
        
        return grades_float
    
    async def _recommend_next_steps(self, question, plan, retrieved_docs, doc_grades, relevance_score):
        """
        Recommend next steps based on the plan and evaluations
        
        Args:
            question: The data science question
            plan: The generated plan
            retrieved_docs: Documents from retrieval
            doc_grades: Document relevance grades
            relevance_score: Question-plan relevance score
            
        Returns:
            List of recommended next steps
        """
        # Format the plan for the prompt
        plan_formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan)])
        
        # Format the docs for the prompt
        docs_formatted = "\n".join([
            f"Document {i+1} - {doc.get('title', 'Untitled')}: {doc.get('content', 'No content')} (Grade: {doc_grades.get(doc.get('id', f'doc{i+1}'), 'N/A') if doc_grades else 'N/A'})"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        # Create the prompt
        recommendation_prompt = ChatPromptTemplate.from_template(RECOMMENDATION_PROMPT)
        
        # Format the prompt
        prompt_args = {
            "question": question,
            "plan": plan_formatted,
            "retrieved_docs": docs_formatted,
            "doc_grades": json.dumps(doc_grades, indent=2) if doc_grades else "{}",
            "relevance_score": relevance_score
        }
        
        # Invoke the LLM for recommendations
        chain = recommendation_prompt | self.llm
        response = await chain.ainvoke(prompt_args)
        
        # Extract recommendations
        recommendations = []
        for line in response.content.strip().split('\n'):
            line = line.strip()
            # Skip empty lines and headers
            if not line or line.startswith('#') or line.lower().startswith('recommend'):
                continue
            # Remove list markers like "1.", "-", "*"
            cleaned_line = re.sub(r"^\d+\.\s*|\*\s*|-\s*", "", line).strip()
            if cleaned_line:
                recommendations.append(cleaned_line)
        
        return recommendations
    
    def _analyze_question_type(self, question):
        """
        Analyze the question to determine its data science operation type
        
        Args:
            question: The data science question
            
        Returns:
            Dictionary with information about the detected question type
        """
        # Check for SQL patterns
        sql_indicators = [
            "sql", "query", "database", "table", "join", "select", 
            "from where", "group by", "order by", "database schema",
            "relational database", "primary key", "foreign key"
        ]
        
        # Check for cohort analysis patterns
        cohort_indicators = [
            "cohort", "retention", "churn", "lifetime value", "ltv", 
            "customer segmentation", "behavioral cohorts", "value segment",
            "CohortPipe"
        ]
        
        # Check for segmentation patterns
        segmentation_indicators = [
            "segment", "cluster", "kmeans", "dbscan", "hierarchical",
            "recency", "frequency", "monetary", "rfm", "SegmentationPipe"
        ]
        
        # Check for ML patterns
        ml_indicators = [
            "machine learning", "predict", "classify", "regression", "train", "model",
            "feature", "accuracy", "precision", "recall", "f1", "neural network",
            "decision tree", "random forest"
        ]
        metrics = [
            "count", "sum", "mean", "median", "average", "max", "min", "std", "variance",
            "percentile", "correlation", "covariance", "frequency", "rate", "ratio",
            "metric", "measure", "kpi", "value", "score"
        ]
        operations=  [
            "filter", "group", "sort", "join", "merge", "concat", "append", "split",
            "transform", "convert", "calculate", "compute", "derive", "normalize",
            "standardize", "rescale", "change", "difference", "delta", "comparison"
        ]
        aggregation=  [
            "aggregate", "summarize", "groupby", "pivot", "rollup", "cube", "crosstab",
            "total", "subtotal", "accumulate", "collect", "combine", "condense"
        ]
        trends=  [
            "trend", "pattern", "anomaly", "outlier", "seasonality", "cyclical", "growth",
            "decay", "increase", "decrease", "spike", "dip", "volatility", "stability"
        ]
        time_series = [
            "time", "date", "period", "interval", "frequency", "duration", "timestamp",
            "temporal", "series", "sequence", "lag", "lead", "window", "moving", "rolling",
            "cumulative", "year", "month", "day", "hour", "minute", "second", "quarter", 
            "seasonal", "periodicity"
        ]
        visualization= [
            "plot", "chart", "graph", "visualize", "display", "show", "histogram", "bar",
            "line", "scatter", "pie", "area", "heatmap", "map", "boxplot", "violin"
        ]
        
        data_processing=  [
            "clean", "preprocess", "impute", "missing", "outlier", "normalize", "scale",
            "encode", "decode", "tokenize", "parse", "extract", "transform", "format"
        ]
        
        # Check for risk analysis patterns
        risk_analysis = [
            "risk", "var", "value at risk", "cvar", "expected shortfall", "conditional var",
            "volatility", "portfolio risk", "diversification", "correlation matrix",
            "monte carlo", "simulation", "stress test", "scenario analysis", "rolling risk",
            "risk attribution", "component risk", "marginal risk", "risk decomposition",
            "distribution fit", "maximum likelihood", "mle", "aic", "bic", "log likelihood",
            "normal distribution", "student t", "skewed normal", "gev", "extreme value",
            "tail risk", "fat tails", "heavy tails", "kurtosis", "skewness", "moments",
            "confidence level", "quantile", "percentile", "bootstrap", "parametric",
            "historical simulation", "risk metrics", "risk assessment", "risk management",
            "financial risk", "market risk", "credit risk", "operational risk", "liquidity risk",
            "systematic risk", "idiosyncratic risk", "beta", "alpha", "sharpe ratio", "sortino ratio",
            "information ratio", "tracking error", "downside deviation", "upside potential",
            "risk adjusted return", "risk free rate", "excess return", "risk premium"
        ]
        
        # Count indicators for each type
        sql_count = sum(1 for indicator in sql_indicators if indicator.lower() in question.lower())
        cohort_count = sum(1 for indicator in cohort_indicators if indicator.lower() in question.lower())
        segmentation_count = sum(1 for indicator in segmentation_indicators if indicator.lower() in question.lower())
        ml_count = sum(1 for indicator in ml_indicators if indicator.lower() in question.lower())
        metrics_count = sum(1 for indicator in metrics if indicator.lower() in question.lower())
        operations_count = sum(1 for indicator in operations if indicator.lower() in question.lower())
        aggregation_count = sum(1 for indicator in aggregation if indicator.lower() in question.lower())
        trends_count = sum(1 for indicator in trends if indicator.lower() in question.lower())
        time_series_count = sum(1 for indicator in time_series if indicator.lower() in question.lower())
        visualization_count = sum(1 for indicator in visualization if indicator.lower() in question.lower())
        data_processing_count = sum(1 for indicator in data_processing if indicator.lower() in question.lower())
        risk_analysis_count = sum(1 for indicator in risk_analysis if indicator.lower() in question.lower())
        # Check for pipeline patterns
        has_pipe_pattern = "|" in question or "pipe" in question.lower() or "pipeline" in question.lower()
        
        # Determine primary type
        counts = {
            "sql": sql_count,
            "cohort_analysis": cohort_count,
            "segmentation": segmentation_count,
            "machine_learning": ml_count,
            "metrics": metrics_count,
            "operations": operations_count,
            "aggregation": aggregation_count,
            "trends": trends_count,
            "time_series": time_series_count,
            "visualization": visualization_count,
            "data_processing": data_processing_count,
            "risk_analysis": risk_analysis_count
        }
        
        primary_type = max(counts.items(), key=lambda x: x[1])
        
        # If no significant pattern detected, use general analysis
        if primary_type[1] == 0:
            primary_type = ("general_analysis", 0)
        
        # Build result
        return {
            "primary_type": primary_type[0],
            "has_pipeline": has_pipe_pattern,
            "type_scores": counts,
            "is_sql": sql_count > 0,
            "is_cohort": cohort_count > 0,
            "is_segmentation": segmentation_count > 0,
            "is_ml": ml_count > 0,
            "is_metrics": metrics_count > 0,
            "is_operations": operations_count > 0,
            "is_aggregation": aggregation_count > 0,
            "is_risk_analysis": risk_analysis_count > 0
        }
    
    async def plan(self, question, context=None, planner_type="general data analysis"):
        """
        Main planning method that coordinates the logical planning process
        
        Args:
            question: The data science question to plan for
            context: Additional context (optional)
            planner_type: Type of planner to use (default: "general data analysis")
            
        Returns:
            DataSciencePlanState with the complete plan and evaluations
        """
        # Initialize the state
        state = DataSciencePlanState(
            question=question,
            context=context or {},
            planner_type=planner_type,
            metadata={"timestamp": datetime.datetime.now().isoformat()}
        )
        
        # Step 1: Call retrieval node
        print("Step 1: Calling retrieval agent...")
        retrieved_docs = await self._call_retrieval_agent(question, context)
        state["retrieved_docs"] = retrieved_docs
        
       
        # Step 3: Create the plan
        print("Step 2: Creating the plan...")
        plan, full_output = await self._create_plan(question, context, planner_type, retrieved_docs)
        state["plan"] = plan

         # Step 2: Grade the retrieval docs
        print("Step 3: Grading retrieved documents...")
        doc_grades = await self._grade_documents(question, plan, retrieved_docs)
        state["doc_grades"] = doc_grades

        
        # Step 4: Grade the relevance of the question and plan using advanced scorer
        print("Step 4: Grading question-plan relevance...")
        # Update the context in the scorer
        self.relevance_scorer.context = context or {}
        # Analyze question type
        question_analysis = self._analyze_question_type(question)
        # Get the relevance score and components
        scoring_results = self.relevance_scorer.score_reasoning(full_output, question)
        
        # Add results to state
        state["extracted_reasoning"] = scoring_results["extracted_reasoning"]
        state["relevance_components"] = scoring_results["relevance_components"]
        state["relevance_score"] = scoring_results["relevance_score"]
        
        # Step 5: Recommend next steps
        print("Step 5: Recommending next steps...")
        recommendations = await self._recommend_next_steps(
            question, plan, retrieved_docs, doc_grades, state["relevance_score"]
        )
        state["recommendations"] = recommendations
        
        return state

# Example usage (would be implemented in a step manager)
async def example_usage():
    # Initialize the planner
    from app.core.dependencies import get_llm
    from app.core.settings import get_settings
    settings = get_settings()
    llm = get_llm()
    client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    examples_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_examples_collection")
    functions_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_spec_collection")
    insights_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_insights_collection")
    planner = DataScienceLogicalPlanner(llm=llm, examples_vectorstore=examples_vectorstore,functions_vectorstore=functions_vectorstore,insights_vectorstore=insights_vectorstore)
    
    # Example input
    question = "How do customer demographics correlate with purchase patterns in our e-commerce dataset?"
    context = {
        "dataset_description": "E-commerce dataset with customer age, gender, location, purchase history, and product categories",
        "schema": {
            "customers": ["customer_id", "age", "gender", "location", "signup_date"],
            "orders": ["order_id", "customer_id", "order_date", "total_amount"],
            "order_items": ["order_id", "product_id", "quantity", "price"],
            "products": ["product_id", "name", "category", "price", "brand"]
        }
    }
    planner_type = "general data analysis"
    import pandas as pd
    po_df = pd.read_csv("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv")
    question = "How does the 5-day rolling variance of flux change over time for each group?"
    summary ='<insight>The analysis of the 5-day rolling variance of flux indicates that there are significant fluctuations in user engagement across different user segments, with the desktop segment showing a higher variance compared to the tablet segment. This suggests that desktop users may exhibit more erratic behavior in their interactions with the platform.</insight>\n\n<insight>During the observed period, there were instances where the variance of flux dropped by more than 10%, particularly in the tablet user segment. This drop correlates with specific time frames, indicating potential periods of reduced user activity or engagement that may warrant further investigation.</insight>\n\n<insight>The overall mean user engagement across all segments was approximately 250.85 events, with a standard deviation of 143.41. This indicates a diverse range of user interactions, suggesting that while some users are highly active, others may be less engaged, highlighting the need for targeted strategies to boost engagement among lower-performing segments.</insight>'
    context = {
        "dataset_description": summary,
        "schema": {
            "po_df": po_df.columns.tolist()
        }
    }
    # Run the planner
    result = await planner.plan(question, context, planner_type)
    
    # Print results
    print("\nPlanning Results:")
    print(f"Question: {result['question']}")
    
    print(f"\nExtracted Reasoning:")
    print(result['extracted_reasoning'])
    
    print(f"\nPlan ({len(result['plan'])} steps):")
    for i, step in enumerate(result['plan']):
        print(f"{i+1}. {step}")
    
    print(f"\nDocument Grades:")
    if result.get('doc_grades'):
        for doc_id, grade in result['doc_grades'].items():
            try:
                print(f"{doc_id}: {float(grade):.2f}")
            except (ValueError, TypeError):
                print(f"{doc_id}: {grade}")
    else:
        print("No document grades available")
    
    print("\nRelevance Score Components:")
    for component, score in result['relevance_components'].items():
        print(f"{component}: {score}")
    
    print(f"\nOverall Relevance Score: {result['relevance_score']:.2f}")
    
    print(f"\nRecommendations:")
    for i, rec in enumerate(result['recommendations']):
        print(f"{i+1}. {rec}")
    
    return result

# If running directly (would be executed by step manager in production)
if __name__ == "__main__":
    # Run the example
    import asyncio
    asyncio.run(example_usage())