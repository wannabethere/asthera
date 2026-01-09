"""
Shared types, models, and utilities for feature engineering agents.

This module contains:
- FeatureEngineeringState: TypedDict for workflow state
- Pydantic models for structured outputs
- Utility functions for metrics tracking
"""

import logging
import time
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
import operator
from datetime import datetime
from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

logger = logging.getLogger("lexy-ai-service")


# ============================================================================
# METRICS TRACKING UTILITIES
# ============================================================================

def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation: ~4 chars per token)"""
    if not text:
        return 0
    return len(text) // 4


def extract_token_usage(response: Any) -> Dict[str, int]:
    """Extract token usage from LLM response"""
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }
    
    # Try to get from response_metadata (OpenAI models)
    if hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        if metadata:
            usage_info = metadata.get('token_usage', {})
            usage["prompt_tokens"] = usage_info.get('prompt_tokens', 0)
            usage["completion_tokens"] = usage_info.get('completion_tokens', 0)
            usage["total_tokens"] = usage_info.get('total_tokens', 0)
    
    # If no metadata, try to estimate from content
    if usage["total_tokens"] == 0 and hasattr(response, 'content'):
        usage["completion_tokens"] = estimate_tokens(response.content)
        usage["total_tokens"] = usage["completion_tokens"]
    
    return usage


async def track_llm_call(
    agent_name: str,
    llm: BaseChatModel,
    messages: List[BaseMessage],
    state: Dict[str, Any],
    step_name: Optional[str] = None
) -> Any:
    """
    Track LLM call with timing and token usage.
    
    Args:
        agent_name: Name of the agent making the call
        llm: LLM instance
        messages: Messages to send to LLM
        state: Current state (will be updated with metrics)
        step_name: Optional step name (defaults to agent_name)
    
    Returns:
        LLM response
    """
    step_name = step_name or agent_name
    start_time = time.perf_counter()
    
    # Estimate prompt tokens
    prompt_text = "\n".join([msg.content if hasattr(msg, 'content') else str(msg) for msg in messages])
    estimated_prompt_tokens = estimate_tokens(prompt_text)
    
    try:
        # Make LLM call
        response = await llm.ainvoke(messages)
        
        # Calculate response time
        response_time = time.perf_counter() - start_time
        
        # Extract token usage
        token_usage = extract_token_usage(response)
        
        # If we estimated prompt tokens but got actual ones, use actual
        if token_usage["prompt_tokens"] == 0:
            token_usage["prompt_tokens"] = estimated_prompt_tokens
        
        # Update total tokens if we only have completion tokens
        if token_usage["total_tokens"] == 0:
            token_usage["total_tokens"] = token_usage["prompt_tokens"] + token_usage["completion_tokens"]
        
        # Store metrics in state
        if "metrics" not in state or state["metrics"] is None:
            state["metrics"] = {
                "steps": [],
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_response_time": 0.0,
                "step_count": 0
            }
        
        step_metrics = {
            "step_name": step_name,
            "agent_name": agent_name,
            "response_time_seconds": round(response_time, 3),
            "prompt_tokens": token_usage["prompt_tokens"],
            "completion_tokens": token_usage["completion_tokens"],
            "total_tokens": token_usage["total_tokens"],
            "timestamp": datetime.now().isoformat()
        }
        
        state["metrics"]["steps"].append(step_metrics)
        state["metrics"]["total_prompt_tokens"] += token_usage["prompt_tokens"]
        state["metrics"]["total_completion_tokens"] += token_usage["completion_tokens"]
        state["metrics"]["total_tokens"] += token_usage["total_tokens"]
        state["metrics"]["total_response_time"] += response_time
        state["metrics"]["step_count"] += 1
        
        logger.info(
            f"[{step_name}] Response time: {response_time:.3f}s | "
            f"Tokens: {token_usage['total_tokens']} (prompt: {token_usage['prompt_tokens']}, "
            f"completion: {token_usage['completion_tokens']})"
        )
        
        return response
        
    except Exception as e:
        # Track error metrics
        response_time = time.perf_counter() - start_time
        
        if "metrics" not in state or state["metrics"] is None:
            state["metrics"] = {
                "steps": [],
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_response_time": 0.0,
                "step_count": 0,
                "errors": []
            }
        
        error_metrics = {
            "step_name": step_name,
            "agent_name": agent_name,
            "response_time_seconds": round(response_time, 3),
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        state["metrics"]["steps"].append(error_metrics)
        if "errors" not in state["metrics"]:
            state["metrics"]["errors"] = []
        state["metrics"]["errors"].append({
            "step": step_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        logger.error(f"[{step_name}] Error after {response_time:.3f}s: {e}")
        raise


# ============================================================================
# STATE DEFINITION
# ============================================================================

class FeatureEngineeringState(TypedDict, total=False):
    """State for the feature engineering workflow"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    query_breakdown: Optional[Dict[str, Any]]  # Query breakdown into multiple steps
    analytical_intent: Dict[str, Any]
    relevant_schemas: List[str]
    available_features: List[Dict[str, Any]]
    clarifying_questions: List[str]
    reasoning_plan: Dict[str, Any]
    recommended_features: List[Dict[str, Any]]
    feature_dependencies: Dict[str, Any]  # Feature dependency chains and calculation order
    relevance_scores: Dict[str, Any]  # Relevance scores for features and overall output
    feature_calculation_plan: Dict[str, Any]  # Plan for calculating features based on knowledge, not schema lookup
    impact_features: List[Dict[str, Any]]  # Impact features as natural language questions
    likelihood_features: List[Dict[str, Any]]  # Likelihood features as natural language questions
    risk_features: List[Dict[str, Any]]  # Risk features as natural language questions
    next_agent: str
    project_id: str
    histories: Optional[List[Any]]
    schema_registry: Dict[str, Any]
    knowledge_documents: List[Dict[str, Any]]
    domain_config: Dict[str, Any]
    validation_expectations: Optional[List[Dict[str, Any]]]  # External expectations/examples for validation
    refining_instructions: Optional[str]  # Instructions for knowledge refining agent
    refining_examples: Optional[List[Dict[str, Any]]]  # Examples for knowledge refining agent
    feature_generation_instructions: Optional[str]  # Instructions for feature generation agent
    feature_generation_examples: Optional[List[Dict[str, Any]]]  # Examples for feature generation agent
    identified_controls: Optional[List[Dict[str, Any]]]  # Compliance controls identified from data model
    control_universe: Optional[Dict[str, Any]]  # Control universe structure
    deep_research_review: Optional[Dict[str, Any]]  # Deep research review results
    metrics: Optional[Dict[str, Any]]  # Token usage and response time metrics for each step
    use_case_groups: Optional[List[Dict[str, Any]]]  # Features grouped by use case (e.g., Identity controls -- CC1.2, CC1.3)
    risk_configuration: Optional[Dict[str, Any]]  # Configuration for enabling/disabling risk/impact/likelihood features per use case group
    planned_groups: Optional[Dict[str, Any]]  # Groups created by GroupPlannerAgent based on knowledge and goal
    group_kpis: Optional[Dict[str, Any]]  # KPIs generated per group (external agent output)
    group_metrics: Optional[Dict[str, Any]]  # Metrics generated per group (external agent output)
    group_sql_questions: Optional[Dict[str, Any]]  # Natural Language SQL questions per group (external agent output)
    risk_quantification_goal: Optional[str]  # User-defined risk quantification goal
    risk_quantification_groups: Optional[Dict[str, Any]]  # Groups for risk quantification breakdown


# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUTS
# ============================================================================

class TimeConstraints(BaseModel):
    """Time constraint requirements"""
    sla_days: Optional[int] = Field(default=None, description="SLA in days")
    time_window: Optional[str] = Field(default=None, description="Time window (e.g., '30 days', '1 year')")
    deadline: Optional[str] = Field(default=None, description="Specific deadline if mentioned")
    urgency: Optional[str] = Field(default=None, description="Urgency level (e.g., 'immediate', 'high', 'medium')")


class AnalyticalIntent(BaseModel):
    """Structured representation of user's analytical intent"""
    primary_goal: str = Field(description="Main analytical objective")
    compliance_framework: str = Field(default="", description="Compliance framework if mentioned (domain-specific)")
    severity_levels: List[str] = Field(default_factory=list, description="Severity/priority levels of interest (domain-specific)")
    time_constraints: Optional[TimeConstraints] = Field(default=None, description="Time constraint requirements (domain-specific)")
    metrics_required: List[str] = Field(default_factory=list, description="Specific metrics needed")
    aggregation_level: str = Field(default="", description="Aggregation level (domain-specific entity types)")
    time_series_requirements: bool = Field(default=False, description="Whether time-series features needed")


class SchemaMapping(BaseModel):
    """Mapping between user requirements and available schemas"""
    schema_name: str
    relevance_score: float
    required_fields: List[str]
    reasoning: str


class FeatureRecommendation(BaseModel):
    """Recommended feature with metadata"""
    feature_name: str
    feature_type: str  # metric, count, ratio, time_series, derived, impact, likelihood, risk
    natural_language_question: str = Field(description="A clear, natural language question that represents what this feature calculates. This is REQUIRED and must be a complete, interpretable question.")
    required_schemas: List[str] = Field(default_factory=list, description="List of schema names required for this feature")
    required_fields: List[str] = Field(default_factory=list, description="List of specific fields/columns needed")
    aggregation_method: str = Field(description="Aggregation method: count, sum, avg, min, max, ratio, percentile, etc.")
    filters_applied: List[str] = Field(default_factory=list, description="List of filters to apply (e.g., severity='Critical', state='ACTIVE')")
    business_context: str = Field(description="Why this feature matters for business monitoring and decision-making")
    compliance_reasoning: str = Field(default="", description="Explanation of how this feature supports compliance requirements (e.g., SOC2, HIPAA, GDPR)")
    feature_group: Optional[str] = Field(default=None, description="Group name for related features that should be calculated together (e.g., 'vulnerability_counts', 'sla_metrics', 'risk_scores')")
    transformation_layer: str = Field(default="gold", description="Data mart transformation layer: 'bronze' (raw), 'silver' (cleaned/normalized), 'gold' (business aggregations/metrics)")
    time_series_type: Optional[str] = Field(default=None, description="Time series classification: 'snapshot' (point-in-time), 'cumulative' (running total), 'rolling_window' (moving average), 'period_over_period' (YoY, MoM), 'trend' (slope/rate), None (not time-series)")
    # Dependency information (added by FeatureDependencyAgent)
    depends_on: Optional[List[str]] = Field(default_factory=list, description="List of feature names this feature depends on")
    calculation_order: Optional[int] = Field(default=None, description="Order in which this feature should be calculated (1 = first, 2 = second, etc.)")
    is_base_feature: Optional[bool] = Field(default=None, description="True if this is a base feature with no dependencies")
    # Recommendation score information (added by RelevancyScoringAgent)
    recommendation_score: Optional[float] = Field(default=None, description="Overall relevance score for this feature (0.0 to 1.0)")
    recommendation_confidence: Optional[float] = Field(default=None, description="Confidence in the recommendation score (0.0 to 1.0)")
    score_dimensions: Optional[Dict[str, float]] = Field(default=None, description="Scores for different dimensions (relevance, completeness, feasibility, clarity, technical_accuracy)")
    matches_goal: Optional[bool] = Field(default=None, description="Whether this feature matches the user's goal")
    matches_examples: Optional[bool] = Field(default=None, description="Whether this feature matches provided examples")
    score_feedback: Optional[str] = Field(default=None, description="Feedback on the feature quality")
    improvement_suggestions: Optional[List[str]] = Field(default_factory=list, description="Suggestions for improving this feature")


class ReasoningPlan(BaseModel):
    """Step-by-step analytical reasoning plan"""
    plan_id: str
    objective: str
    steps: List[Dict[str, Any]]
    data_flow: List[str]
    feature_dependencies: Dict[str, List[str]]
    quality_checks: List[str]


class ClarifyingQuestion(BaseModel):
    """Questions to refine feature requirements"""
    question: str
    question_type: str  # sla, scope, metric, filter, aggregation
    context: str
    default_assumption: str


class FeatureDependency(BaseModel):
    """Feature dependency information"""
    feature_name: str
    depends_on: List[str]  # List of feature names this feature depends on
    calculation_order: int  # Order in which this feature should be calculated
    natural_language_chain: List[str]  # Chain of natural language questions/operations
    data_dependencies: List[str]  # Required schemas/tables
    is_base_feature: bool  # True if this is a base feature (no dependencies)


class FeatureDependencyGraph(BaseModel):
    """Complete dependency graph for all features"""
    features: List[FeatureDependency]
    calculation_sequence: List[List[str]]  # Groups of features that can be calculated in parallel
    dependency_chains: List[List[str]]  # Sequential chains of feature calculations
    total_steps: int  # Total number of calculation steps required


class RelevanceScore(BaseModel):
    """Relevance score for a feature or output"""
    feature_name: Optional[str] = None  # None for overall score
    score: float  # 0.0 to 1.0
    confidence: float  # Confidence in the score (0.0 to 1.0)
    dimensions: Dict[str, float]  # Scores for different dimensions (relevance, completeness, etc.)
    matches_goal: bool  # Whether this matches the user's goal
    matches_examples: bool  # Whether this matches provided examples
    feedback: str  # Feedback on quality and improvements
    improvement_suggestions: List[str]


class RelevancyScoringResult(BaseModel):
    """Overall relevancy scoring result"""
    overall_score: float
    overall_confidence: float
    feature_scores: List[RelevanceScore]
    goal_alignment: float  # How well features align with user goal
    example_alignment: float  # How well features match provided examples
    quality_metrics: Dict[str, float]
    recommendations: List[str]


class QueryBreakdownStep(BaseModel):
    """A single step in the query breakdown"""
    step_number: int = Field(description="Step number in the breakdown sequence")
    step_name: str = Field(description="Name/title of this step")
    description: str = Field(description="Detailed description of what this step should accomplish")
    step_type: str = Field(
        description="Type of step: 'risk_trend', 'impact_trend', 'likelihood_trend', 'general_metrics', 'compliance_tracking', or 'other'"
    )
    focus_areas: List[str] = Field(
        default_factory=list,
        description="Specific areas or entities this step focuses on (e.g., 'Critical vulnerabilities', 'Training completion')"
    )
    required_metrics: List[str] = Field(
        default_factory=list,
        description="Types of metrics needed for this step (e.g., 'count', 'rate', 'trend', 'risk_score')"
    )
    compliance_frameworks: List[str] = Field(
        default_factory=list,
        description="Relevant compliance frameworks for this step (e.g., 'SOC2', 'GDPR')"
    )
    entity_types: List[str] = Field(
        default_factory=list,
        description="Entity types relevant to this step (e.g., 'Asset', 'Vulnerability', 'Employee', 'Course')"
    )


class QueryBreakdown(BaseModel):
    """Breakdown of user query into multiple analytical steps"""
    original_query: str = Field(description="Original user query")
    domain: str = Field(description="Domain name (e.g., 'cybersecurity', 'hr_compliance')")
    overall_goal: str = Field(description="The overarching analytical goal of the original query")
    analytical_intent: str = Field(description="The primary analytical intent - what the user wants to achieve or understand")
    applicable_compliance_frameworks: List[str] = Field(
        default_factory=list,
        description="List of compliance frameworks identified as applicable to this query (e.g., 'SOC2', 'GDPR', 'HIPAA')"
    )
    primary_goals: List[str] = Field(
        default_factory=list,
        description="List of primary goals identified from the query breakdown (e.g., 'Track risk trends', 'Monitor compliance', 'Assess impact')"
    )
    breakdown_steps: List[QueryBreakdownStep] = Field(
        description="List of steps that break down the query into manageable analytical components"
    )
    time_series_requirements: bool = Field(
        default=False,
        description="Whether the analysis requires time series/trending data"
    )

