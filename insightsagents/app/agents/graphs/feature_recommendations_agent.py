import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Literal, Annotated
from dataclasses import dataclass, field
from enum import Enum
import json
import warnings
from datetime import datetime
import uuid

# LangChain imports
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI

# LangGraph imports  
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# Import the new data analysis utility
from data_analysis_utility import enhanced_dataframe_storage, DataAnalysisResult

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


# Note: DataFrameStorage has been replaced by enhanced_dataframe_storage from data_analysis_utility


class FeatureType(Enum):
    """Types of features that can be recommended"""
    EXISTING = "existing"  # Use column as-is
    TRANSFORMED = "transformed"  # Transform existing column
    INTERACTION = "interaction"  # Combine multiple columns
    DERIVED = "derived"  # Create new feature from business logic
    AGGREGATED = "aggregated"  # Group-by aggregations
    TEMPORAL = "temporal"  # Time-based features
    CATEGORICAL_ENCODED = "categorical_encoded"  # Encoding categorical variables


@dataclass
class FeatureRecommendation:
    """Single feature recommendation"""
    feature_name: str
    feature_type: FeatureType
    source_columns: List[str]
    creation_steps: str  # Natural language description of how to create
    business_reasoning: str  # Why this feature is important for the goal
    expected_importance: float  # Predicted importance (0-1)
    technical_details: Dict[str, Any]  # Technical specifications for feature creation
    dependencies: List[str] = field(default_factory=list)  # Other features this depends on
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "feature_name": self.feature_name,
            "feature_type": self.feature_type.value,
            "source_columns": self.source_columns,
            "creation_steps": self.creation_steps,
            "business_reasoning": self.business_reasoning,
            "expected_importance": self.expected_importance,
            "technical_details": self.technical_details,
            "dependencies": self.dependencies
        }


# Note: DataAnalysis has been replaced by DataAnalysisResult from data_analysis_utility


@dataclass
class FeatureRecommendationState:
    """State for the feature recommendation workflow"""
    # Inputs
    business_goal: str = ""
    training_objective: str = ""
    business_knowledge: str = ""
    data_description: str = ""
    
    # Analysis - now using pre-calculated analysis
    data_analysis: Optional[Dict[str, Any]] = None
    domain_insights: Dict[str, Any] = field(default_factory=dict)
    
    # Recommendations
    feature_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    feature_engineering_plan: Dict[str, Any] = field(default_factory=dict)
    
    # Data - use key instead of DataFrame
    data_key: str = ""
    
    # Processing state
    messages: Annotated[List[BaseMessage], add_messages] = field(default_factory=list)
    current_step: str = "start"
    
    def get_data(self) -> Optional[pd.DataFrame]:
        """Get the DataFrame using the stored key"""
        if self.data_key:
            return enhanced_dataframe_storage.get_dataframe(self.data_key)
        return None
    
    def has_data(self) -> bool:
        """Check if data is available"""
        return self.data_key and enhanced_dataframe_storage.get_dataframe(self.data_key) is not None
    
    def set_data(self, df: pd.DataFrame, dataset_name: str = "dataset") -> str:
        """Store DataFrame with pre-calculated analysis and set the key"""
        key = enhanced_dataframe_storage.store_dataframe_with_analysis(df, dataset_name=dataset_name)
        self.data_key = key
        return key
    
    def get_analysis(self) -> Optional[Dict[str, Any]]:
        """Get pre-calculated analysis"""
        if self.data_key:
            return enhanced_dataframe_storage.get_analysis_dict(self.data_key)
        return None


class FeatureKnowledgeBase:
    """Knowledge base of feature engineering patterns and domain expertise"""
    
    @staticmethod
    def get_domain_patterns(domain: str) -> Dict[str, List[str]]:
        """Get common feature patterns for different domains"""
        
        domain_patterns = {
            "customer_analytics": [
                "Recency, Frequency, Monetary (RFM) features",
                "Customer lifetime value calculations",
                "Engagement ratios (purchases/visits)",
                "Seasonality indicators for purchase behavior",
                "Customer tenure and lifecycle stage"
            ],
            
            "finance": [
                "Moving averages and technical indicators",
                "Volatility measures and risk ratios",
                "Trend and momentum indicators", 
                "Liquidity and profitability ratios",
                "Time-series lag features"
            ],
            
            "healthcare": [
                "BMI and health index calculations",
                "Age-adjusted risk factors",
                "Comorbidity indicators and scores",
                "Treatment response patterns",
                "Diagnostic code combinations"
            ],
            
            "marketing": [
                "Campaign response rates and lift",
                "Channel attribution and touchpoint analysis", 
                "Demographic and psychographic segments",
                "Content engagement metrics",
                "A/B test participation indicators"
            ],
            
            "operations": [
                "Efficiency ratios and productivity metrics",
                "Quality control indicators",
                "Resource utilization rates",
                "Process cycle times",
                "Inventory turnover ratios"
            ],
            
            "sales": [
                "Sales pipeline velocity metrics",
                "Deal size and probability scores", 
                "Territory and quota performance",
                "Customer acquisition cost ratios",
                "Seasonal adjustment factors"
            ]
        }
        
        return domain_patterns.get(domain.lower(), [])
    
    @staticmethod
    def get_feature_templates() -> Dict[str, Dict[str, Any]]:
        """Get templates for common feature engineering patterns"""
        
        return {
            "ratio_features": {
                "description": "Create ratios between related numerical variables",
                "template": "{numerator} / {denominator}",
                "examples": ["revenue_per_employee", "cost_per_acquisition", "profit_margin"],
                "when_to_use": "When you have related metrics that provide context for each other"
            },
            
            "interaction_features": {
                "description": "Combine categorical and numerical features",
                "template": "{categorical}_{numerical}_interaction",
                "examples": ["department_salary_band", "region_sales_level"],
                "when_to_use": "When business logic suggests different groups behave differently"
            },
            
            "temporal_features": {
                "description": "Extract time-based patterns from dates",
                "template": "{date_column}_{time_component}",
                "examples": ["purchase_month", "signup_day_of_week", "last_activity_days_ago"],
                "when_to_use": "When timing and seasonality matter for business outcomes"
            },
            
            "aggregation_features": {
                "description": "Group-by statistics for categorical variables",
                "template": "{metric}_by_{group}_{aggregation}",
                "examples": ["avg_sales_by_region", "total_orders_by_customer", "max_score_by_department"],
                "when_to_use": "When group-level statistics provide predictive power"
            },
            
            "transformation_features": {
                "description": "Mathematical transformations of numerical variables",
                "template": "{transformation}_{original_column}",
                "examples": ["log_revenue", "sqrt_age", "standardized_score"],
                "when_to_use": "When distributions are skewed or relationships are non-linear"
            },
            
            "binning_features": {
                "description": "Convert continuous variables into categorical bins",
                "template": "{column}_bin_{strategy}",
                "examples": ["age_group_quintiles", "income_bracket", "score_tier"],
                "when_to_use": "When business thinks in categories rather than continuous values"
            }
        }


class FeatureRecommendationAgent:
    """Independent Feature Recommendation Agent using LangGraph"""
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """Initialize the feature recommendation agent"""
        self.llm = ChatOpenAI(model=llm_model, temperature=0.1)
        self.knowledge_base = FeatureKnowledgeBase()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the feature recommendation workflow"""
        
        workflow = StateGraph(FeatureRecommendationState)
        
        # Add workflow nodes
        workflow.add_node("analyze_data", self._analyze_data_for_features)
        workflow.add_node("extract_domain_insights", self._extract_domain_insights)
        workflow.add_node("generate_feature_ideas", self._generate_feature_ideas)
        workflow.add_node("evaluate_features", self._evaluate_feature_recommendations)
        workflow.add_node("create_engineering_plan", self._create_feature_engineering_plan)
        workflow.add_node("finalize_recommendations", self._finalize_recommendations)
        
        # Define workflow flow
        workflow.add_edge(START, "analyze_data")
        workflow.add_edge("analyze_data", "extract_domain_insights")
        workflow.add_edge("extract_domain_insights", "generate_feature_ideas")
        workflow.add_edge("generate_feature_ideas", "evaluate_features")
        workflow.add_edge("evaluate_features", "create_engineering_plan")
        workflow.add_edge("create_engineering_plan", "finalize_recommendations")
        workflow.add_edge("finalize_recommendations", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    def _analyze_data_for_features(self, state: FeatureRecommendationState) -> FeatureRecommendationState:
        """Step 1: Use pre-calculated data analysis"""
        
        print(f"🔍 Analyzing data - State type: {type(state)}")
        
        if not state.has_data():
            raise ValueError("No data provided for analysis")
        
        # Get pre-calculated analysis
        analysis = state.get_analysis()
        if not analysis:
            raise ValueError("No pre-calculated analysis available")
        
        # Store the analysis in state
        state.data_analysis = analysis
        
        state.current_step = "data_analyzed"
        print(f"✅ Data analysis complete - Step: {state.current_step}")
        return state
    
    def _extract_domain_insights(self, state: FeatureRecommendationState) -> FeatureRecommendationState:
        """Step 2: Extract domain-specific insights from business knowledge"""
        
        domain_prompt = ChatPromptTemplate.from_template("""
        You are a domain expert analyzing business requirements for feature engineering.
        
        Business Goal: {business_goal}
        Training Objective: {training_objective}
        Business Knowledge: {business_knowledge}
        
        Data Columns Available: {available_columns}
        Data Description: {data_description}
        
        Analyze and extract:
        1. **Industry Domain**: What industry/domain is this (e.g., finance, healthcare, retail, etc.)
        2. **Key Business Drivers**: What factors typically drive success in this domain for this objective
        3. **Domain-Specific Patterns**: Common feature patterns that work well in this industry
        4. **Business Logic**: Important business rules or relationships to consider
        5. **Success Metrics**: What constitutes a successful feature in this context
        6. **Data Relationships**: Expected relationships between variables based on business knowledge
        
        Respond in JSON format:
        {{
            "domain": "identified industry domain",
            "key_business_drivers": ["driver1", "driver2", "driver3"],
            "domain_patterns": ["pattern1", "pattern2"],
            "business_rules": ["rule1", "rule2"],
            "success_criteria": "what makes a feature valuable",
            "expected_relationships": [
                {{"variable1": "col1", "variable2": "col2", "relationship": "positive/negative correlation", "business_reason": "why"}}
            ],
            "critical_features_to_include": ["must-have feature categories"],
            "features_to_avoid": ["problematic feature types"]
        }}
        """)
        
        chain = domain_prompt | self.llm | JsonOutputParser()
        
        data = state.get_data()
        available_columns = list(data.columns) if data is not None else []
        
        domain_insights = chain.invoke({
            "business_goal": state.business_goal,
            "training_objective": state.training_objective,
            "business_knowledge": state.business_knowledge,
            "available_columns": available_columns,
            "data_description": state.data_description
        })
        
        state.domain_insights = domain_insights
        state.current_step = "domain_insights_extracted"
        
        return state
    
    def _generate_feature_ideas(self, state: FeatureRecommendationState) -> FeatureRecommendationState:
        """Step 3: Generate comprehensive feature ideas"""
        
        if not state.data_analysis or not state.domain_insights:
            return state
        
        feature_generation_prompt = ChatPromptTemplate.from_template("""
        You are a feature engineering expert generating specific feature recommendations.
        
        **Business Context:**
        Goal: {business_goal}
        Training Objective: {training_objective}
        Domain: {domain}
        
        **Data Available:**
        Numerical Columns: {numerical_columns}
        Categorical Columns: {categorical_columns}
        Datetime Columns: {datetime_columns}
        Data Quality Score: {data_quality_score}
        
        **Domain Insights:**
        Key Business Drivers: {key_drivers}
        Business Rules: {business_rules}
        Critical Features: {critical_features}
        
        **Feature Templates Available:**
        {feature_templates}
        
        Generate 15-20 specific feature recommendations. For each feature, specify:
        
        Respond in JSON format with an array of features:
        {{
            "features": [
                {{
                    "feature_name": "descriptive_name_for_feature",
                    "feature_type": "existing|transformed|interaction|derived|aggregated|temporal|categorical_encoded",
                    "source_columns": ["col1", "col2"],
                    "creation_steps": "Clear natural language steps to create this feature",
                    "business_reasoning": "Why this feature will help achieve the business goal",
                    "expected_importance": 0.85,
                    "technical_details": {{
                        "operation": "specific operation",
                        "parameters": {{"param1": "value1"}},
                        "validation_rules": ["rule1", "rule2"]
                    }},
                    "dependencies": ["other_feature_names"]
                }}
            ]
        }}
        
        Focus on features that:
        1. Directly support the training objective
        2. Leverage domain-specific business knowledge
        3. Use available data columns effectively
        4. Follow proven feature engineering patterns
        5. Are implementable with the given data
        """)
        
        # Get feature templates
        templates = self.knowledge_base.get_feature_templates()
        template_descriptions = "\n".join([
            f"**{name}**: {details['description']} - {details['when_to_use']}"
            for name, details in templates.items()
        ])
        
        # Get column lists
        data = state.get_data()
        if data is None:
            return state
            
        numerical_columns = [col for col, dtype in state.data_analysis["column_types"].items() if dtype == "numerical"]
        categorical_columns = [col for col, dtype in state.data_analysis["column_types"].items() if dtype == "categorical"]
        datetime_columns = [col for col, dtype in state.data_analysis["column_types"].items() if dtype == "datetime"]
        
        chain = feature_generation_prompt | self.llm | JsonOutputParser()
        
        feature_ideas = chain.invoke({
            "business_goal": state.business_goal,
            "training_objective": state.training_objective,
            "domain": state.domain_insights.get("domain", "general"),
            "numerical_columns": numerical_columns,
            "categorical_columns": categorical_columns,
            "datetime_columns": datetime_columns,
            "data_quality_score": state.data_analysis["data_quality_score"],
            "key_drivers": state.domain_insights.get("key_business_drivers", []),
            "business_rules": state.domain_insights.get("business_rules", []),
            "critical_features": state.domain_insights.get("critical_features_to_include", []),
            "feature_templates": template_descriptions
        })
        
        # Convert to FeatureRecommendation objects and then to dictionaries
        recommendations = []
        for feature_data in feature_ideas.get("features", []):
            try:
                recommendation = FeatureRecommendation(
                    feature_name=feature_data["feature_name"],
                    feature_type=FeatureType(feature_data["feature_type"]),
                    source_columns=feature_data["source_columns"],
                    creation_steps=feature_data["creation_steps"],
                    business_reasoning=feature_data["business_reasoning"],
                    expected_importance=feature_data["expected_importance"],
                    technical_details=feature_data["technical_details"],
                    dependencies=feature_data.get("dependencies", [])
                )
                recommendations.append(recommendation.to_dict())
            except (KeyError, ValueError) as e:
                # Skip malformed recommendations
                continue
        
        state.feature_recommendations = recommendations
        state.current_step = "features_generated"
        
        return state
    
    def _evaluate_feature_recommendations(self, state: FeatureRecommendationState) -> FeatureRecommendationState:
        """Step 4: Evaluate and prioritize feature recommendations"""
        
        if not state.feature_recommendations:
            return state
        
        evaluation_prompt = ChatPromptTemplate.from_template("""
        You are evaluating feature recommendations for feasibility and business impact.
        
        **Context:**
        Business Goal: {business_goal}
        Domain: {domain}
        Available Data: {data_shape} rows with {column_count} columns
        
        **Feature Recommendations to Evaluate:**
        {feature_recommendations}
        
        **Evaluation Criteria:**
        1. **Business Impact**: How much will this feature help achieve the goal?
        2. **Implementation Feasibility**: How easy is it to create with available data?
        3. **Data Quality**: Will the feature be reliable given data quality?
        4. **Interpretability**: Can business users understand and trust this feature?
        5. **Computational Cost**: How expensive is this feature to create and maintain?
        
        For each feature, provide:
        - Feasibility score (0-1)
        - Business impact score (0-1) 
        - Overall priority score (0-1)
        - Implementation complexity (low/medium/high)
        - Potential issues or limitations
        
        Respond in JSON format:
        {{
            "evaluated_features": [
                {{
                    "feature_name": "name",
                    "feasibility_score": 0.9,
                    "business_impact_score": 0.8,
                    "priority_score": 0.85,
                    "implementation_complexity": "low|medium|high",
                    "potential_issues": ["issue1", "issue2"],
                    "recommended_for_mvp": true
                }}
            ],
            "top_5_features": ["feature1", "feature2", "feature3", "feature4", "feature5"],
            "must_have_features": ["critical_feature1", "critical_feature2"],
            "nice_to_have_features": ["optional_feature1", "optional_feature2"]
        }}
        """)
        
        chain = evaluation_prompt | self.llm | JsonOutputParser()
        
        # Prepare feature data for evaluation
        feature_data = []
        for rec in state.feature_recommendations:
            feature_data.append({
                "feature_name": rec["feature_name"],
                "feature_type": rec["feature_type"],
                "source_columns": rec["source_columns"],
                "creation_steps": rec["creation_steps"],
                "business_reasoning": rec["business_reasoning"],
                "expected_importance": rec["expected_importance"]
            })
        
        evaluation_results = chain.invoke({
            "business_goal": state.business_goal,
            "domain": state.domain_insights.get("domain", "general"),
            "data_shape": (state.data_analysis["shape_rows"], state.data_analysis["shape_cols"]),
            "column_count": len(state.data_analysis["column_types"]),
            "feature_recommendations": json.dumps(feature_data, indent=2)
        })
        
        # Update recommendations with evaluation scores
        evaluated_features = evaluation_results.get("evaluated_features", [])
        feature_lookup = {f["feature_name"]: f for f in evaluated_features}
        
        for rec in state.feature_recommendations:
            if rec["feature_name"] in feature_lookup:
                eval_data = feature_lookup[rec["feature_name"]]
                rec["technical_details"].update({
                    "feasibility_score": eval_data.get("feasibility_score", 0.5),
                    "business_impact_score": eval_data.get("business_impact_score", 0.5),
                    "priority_score": eval_data.get("priority_score", 0.5),
                    "implementation_complexity": eval_data.get("implementation_complexity", "medium"),
                    "potential_issues": eval_data.get("potential_issues", []),
                    "recommended_for_mvp": eval_data.get("recommended_for_mvp", False)
                })
        
        # Store evaluation results
        state.domain_insights.update(evaluation_results)
        state.current_step = "features_evaluated"
        
        return state
    
    def _create_feature_engineering_plan(self, state: FeatureRecommendationState) -> FeatureRecommendationState:
        """Step 5: Create a structured feature engineering plan"""
        
        planning_prompt = ChatPromptTemplate.from_template("""
        Create a structured feature engineering implementation plan.
        
        **Context:**
        Business Goal: {business_goal}
        Top Features: {top_features}
        
        **Feature Recommendations:**
        {feature_recommendations}
        
        Create a step-by-step implementation plan that includes:
        
        1. **Phase 1 - Foundation Features**: Core features to implement first
        2. **Phase 2 - Enhanced Features**: Advanced features for better performance
        3. **Phase 3 - Experimental Features**: Innovative features to test
        
        For each phase, specify:
        - Which features to implement
        - Order of implementation (considering dependencies)
        - Expected timeline/effort
        - Success criteria
        
        Also provide:
        - **Data Preparation Steps**: Required preprocessing
        - **Quality Checks**: How to validate features work correctly
        - **Business Validation**: How to confirm features make business sense
        
        Respond in JSON format:
        {{
            "implementation_plan": {{
                "phase_1": {{
                    "features": ["feature1", "feature2"],
                    "order": ["step1", "step2"],
                    "effort_estimate": "X hours/days",
                    "success_criteria": "criteria"
                }},
                "phase_2": {{ ... }},
                "phase_3": {{ ... }}
            }},
            "data_preparation": ["prep_step1", "prep_step2"],
            "quality_checks": ["check1", "check2"],
            "business_validation": ["validation1", "validation2"],
            "estimated_total_effort": "time estimate",
            "risk_mitigation": ["risk1_mitigation", "risk2_mitigation"]
        }}
        """)
        
        chain = planning_prompt | self.llm | JsonOutputParser()
        
        # Get top features for planning
        top_features = state.domain_insights.get("top_5_features", [])
        
        # Prepare detailed feature info
        feature_details = []
        for rec in state.feature_recommendations:
            if rec["feature_name"] in top_features or rec["technical_details"].get("recommended_for_mvp", False):
                feature_details.append({
                    "name": rec["feature_name"],
                    "type": rec["feature_type"],
                    "sources": rec["source_columns"],
                    "steps": rec["creation_steps"],
                    "reasoning": rec["business_reasoning"],
                    "complexity": rec["technical_details"].get("implementation_complexity", "medium"),
                    "dependencies": rec["dependencies"]
                })
        
        engineering_plan = chain.invoke({
            "business_goal": state.business_goal,
            "top_features": top_features,
            "feature_recommendations": json.dumps(feature_details, indent=2)
        })
        
        state.feature_engineering_plan = engineering_plan
        state.current_step = "plan_created"
        
        return state
    
    def _finalize_recommendations(self, state: FeatureRecommendationState) -> FeatureRecommendationState:
        """Step 6: Finalize and format the recommendations"""
        
        # Clean up stored DataFrame to free memory
        if state.data_key:
            enhanced_dataframe_storage.remove_dataframe(state.data_key)
        
        finalization_prompt = ChatPromptTemplate.from_template("""
        Create the final feature recommendation summary for business stakeholders.
        
        **Project Context:**
        Business Goal: {business_goal}
        Training Objective: {training_objective}
        Domain: {domain}
        
        **Analysis Results:**
        Data Quality Score: {data_quality_score}
        Total Features Analyzed: {total_features}
        Top Recommendations: {top_features}
        
        **Implementation Plan:**
        {implementation_plan}
        
        Create a comprehensive but concise summary that includes:
        
        1. **Executive Summary**: Key findings and recommendations
        2. **Priority Features**: Top 5-7 features with clear business justification
        3. **Implementation Roadmap**: Phased approach with timelines
        4. **Expected Business Impact**: What outcomes to expect
        5. **Success Metrics**: How to measure feature engineering success
        6. **Risks and Mitigation**: Potential issues and how to address them
        
        Format for business stakeholder consumption - clear, actionable, and focused on value.
        """)
        
        chain = finalization_prompt | self.llm | StrOutputParser()
        
        final_summary = chain.invoke({
            "business_goal": state.business_goal,
            "training_objective": state.training_objective,
            "domain": state.domain_insights.get("domain", "general"),
            "data_quality_score": f"{state.data_analysis['data_quality_score']:.1%}",
            "total_features": len(state.feature_recommendations),
            "top_features": state.domain_insights.get("top_5_features", []),
            "implementation_plan": json.dumps(state.feature_engineering_plan, indent=2)
        })
        
        state.messages.append(AIMessage(content=final_summary))
        state.current_step = "completed"
        
        return state
    
    def recommend_features(self,
                          data: pd.DataFrame,
                          business_goal: str,
                          training_objective: str,
                          business_knowledge: str,
                          data_description: str = "",
                          session_id: str = "default") -> Dict[str, Any]:
        """
        Main method to get feature recommendations
        
        Args:
            data: DataFrame to analyze
            business_goal: High-level business objective
            training_objective: Specific ML training goal
            business_knowledge: Domain expertise and business context
            data_description: Description of the data
            session_id: Unique session identifier
            
        Returns:
            Dictionary with recommendations, plan, and analysis
        """
        
        # Initialize state
        initial_state = FeatureRecommendationState(
            business_goal=business_goal,
            training_objective=training_objective,
            business_knowledge=business_knowledge,
            data_description=data_description
        )
        
        # Store the DataFrame with pre-calculated analysis and set the key
        initial_state.set_data(data, dataset_name="feature_analysis")
        
        # Execute the workflow
        print(f"🔧 Starting workflow with session_id: {session_id}")
        final_state = self.graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )
        
        print(f"🔧 Workflow completed. Final state type: {type(final_state)}")
        
        # Format output for easy consumption
        return self._format_recommendations_output(final_state)
    
    def _format_recommendations_output(self, state) -> Dict[str, Any]:
        """Format the final recommendations for easy consumption"""
        
        # Handle both state objects and dictionaries
        if hasattr(state, 'feature_recommendations'):
            # It's a state object
            feature_recommendations = state.feature_recommendations
            data_analysis = state.data_analysis
            domain_insights = state.domain_insights
            feature_engineering_plan = state.feature_engineering_plan
            messages = state.messages
        else:
            # It's a dictionary (AddableValuesDict)
            print(f"⚠️  State is dictionary type: {type(state)}")
            feature_recommendations = state.get('feature_recommendations', [])
            data_analysis = state.get('data_analysis', {})
            domain_insights = state.get('domain_insights', {})
            feature_engineering_plan = state.get('feature_engineering_plan', {})
            messages = state.get('messages', [])
        
        # Group features by type and priority
        features_by_type = {}
        high_priority_features = []
        medium_priority_features = []
        low_priority_features = []
        
        for rec in feature_recommendations:
            # Group by type
            feature_type = rec["feature_type"]
            if feature_type not in features_by_type:
                features_by_type[feature_type] = []
            
            features_by_type[feature_type].append({
                "name": rec["feature_name"],
                "source_columns": rec["source_columns"],
                "creation_steps": rec["creation_steps"],
                "business_reasoning": rec["business_reasoning"],
                "expected_importance": rec["expected_importance"],
                "technical_details": rec["technical_details"]
            })
            
            # Group by priority
            priority_score = rec["technical_details"].get("priority_score", 0.5)
            if priority_score >= 0.8:
                high_priority_features.append(rec["feature_name"])
            elif priority_score >= 0.6:
                medium_priority_features.append(rec["feature_name"])
            else:
                low_priority_features.append(rec["feature_name"])
        
        return {
            # Core recommendations
            "recommended_features": [
                {
                    "feature_name": rec["feature_name"],
                    "feature_type": rec["feature_type"],
                    "source_columns": rec["source_columns"],
                    "creation_steps": rec["creation_steps"],
                    "business_reasoning": rec["business_reasoning"],
                    "expected_importance": rec["expected_importance"],
                    "technical_details": rec["technical_details"],
                    "dependencies": rec["dependencies"]
                }
                for rec in feature_recommendations
            ],
            
            # Organized views
            "features_by_type": features_by_type,
            "features_by_priority": {
                "high_priority": high_priority_features,
                "medium_priority": medium_priority_features,
                "low_priority": low_priority_features
            },
            
            # Implementation guidance
            "feature_engineering_plan": feature_engineering_plan,
            "implementation_phases": feature_engineering_plan.get("implementation_plan", {}),
            
            # Analysis context
            "data_analysis": {
                "shape": (data_analysis.get("shape_rows", 0), data_analysis.get("shape_cols", 0)),
                "data_quality_score": data_analysis.get("data_quality_score", 0.0),
                "column_types": data_analysis.get("column_types", {}),
                "correlation_insights": data_analysis.get("correlation_insights", [])
            } if data_analysis else {},
            
            "domain_insights": domain_insights,
            
            # Quick access
            "top_features": domain_insights.get("top_5_features", []),
            "must_have_features": domain_insights.get("must_have_features", []),
            "columns_to_use": list(set([
                col for rec in feature_recommendations 
                for col in rec["source_columns"]
            ])),
            
            # Summary
            "executive_summary": messages[-1].content if messages else "",
            "total_features_recommended": len(feature_recommendations),
            "session_metadata": {
                "domain": domain_insights.get("domain", "general"),
                "complexity_level": self._assess_complexity_level_dict(feature_recommendations),
                "estimated_impact": self._estimate_business_impact_dict(feature_recommendations)
            }
        }
    
    def _assess_complexity_level(self, state: FeatureRecommendationState) -> str:
        """Assess overall complexity of feature engineering plan"""
        
        complexities = [
            rec["technical_details"].get("implementation_complexity", "medium")
            for rec in state.feature_recommendations
        ]
        
        high_count = complexities.count("high")
        medium_count = complexities.count("medium")
        
        if high_count > len(complexities) * 0.3:
            return "high"
        elif medium_count > len(complexities) * 0.5:
            return "medium"
        else:
            return "low"
    
    def _assess_complexity_level_dict(self, feature_recommendations: List[Dict[str, Any]]) -> str:
        """Assess complexity from feature recommendations list"""
        
        complexities = [
            rec["technical_details"].get("implementation_complexity", "medium")
            for rec in feature_recommendations
        ]
        
        high_count = complexities.count("high")
        medium_count = complexities.count("medium")
        
        if high_count > len(complexities) * 0.3:
            return "high"
        elif medium_count > len(complexities) * 0.5:
            return "medium"
        else:
            return "low"
    
    def _estimate_business_impact(self, state: FeatureRecommendationState) -> str:
        """Estimate expected business impact"""
        
        avg_importance = float(np.mean([
            rec["expected_importance"] 
            for rec in state.feature_recommendations
        ])) if state.feature_recommendations else 0.5
        
        if avg_importance >= 0.8:
            return "high"
        elif avg_importance >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _estimate_business_impact_dict(self, feature_recommendations: List[Dict[str, Any]]) -> str:
        """Estimate business impact from feature recommendations list"""
        
        avg_importance = float(np.mean([
            rec["expected_importance"] 
            for rec in feature_recommendations
        ])) if feature_recommendations else 0.5
        
        if avg_importance >= 0.8:
            return "high"
        elif avg_importance >= 0.6:
            return "medium"
        else:
            return "low"


# Tool interface for integration with other agents
class FeatureRecommendationTool:
    """Tool wrapper for the Feature Recommendation Agent"""
    
    def __init__(self, agent: FeatureRecommendationAgent = None):
        self.agent = agent or FeatureRecommendationAgent()
    
    def recommend_features_for_goal(self,
                                   data: pd.DataFrame,
                                   business_goal: str,
                                   training_objective: str,
                                   business_knowledge: str) -> Dict[str, Any]:
        """
        Tool function that can be called by other agents
        
        Returns simplified output focused on actionable recommendations
        """
        
        results = self.agent.recommend_features(
            data=data,
            business_goal=business_goal,
            training_objective=training_objective,
            business_knowledge=business_knowledge
        )
        
        # Return simplified format for tool use
        return {
            "top_features": results["top_features"],
            "must_have_features": results["must_have_features"],
            "columns_to_use": results["columns_to_use"],
            "feature_creation_steps": [
                {
                    "feature_name": rec["feature_name"],
                    "creation_steps": rec["creation_steps"],
                    "source_columns": rec["source_columns"]
                }
                for rec in results["recommended_features"]
                if rec["technical_details"].get("recommended_for_mvp", False)
            ],
            "business_reasoning": results["domain_insights"].get("key_business_drivers", []),
            "implementation_complexity": results["session_metadata"]["complexity_level"]
        }


# Example usage and testing
def demo_feature_recommendation_agent():
    """Demonstrate the feature recommendation agent"""
    
    # Create sample customer data
    np.random.seed(42)
    n_customers = 2000
    
    data = pd.DataFrame({
        # Customer demographics
        'customer_id': range(1, n_customers + 1),
        'age': np.random.randint(18, 80, n_customers),
        'income': np.random.normal(60000, 25000, n_customers),
        'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n_customers),
        'location': np.random.choice(['Urban', 'Suburban', 'Rural'], n_customers),
        
        # Transaction data
        'total_purchases': np.random.poisson(12, n_customers),
        'avg_order_value': np.random.normal(85, 30, n_customers),
        'days_since_last_purchase': np.random.exponential(30, n_customers),
        'preferred_category': np.random.choice(['Electronics', 'Clothing', 'Home', 'Books'], n_customers),
        
        # Engagement data
        'website_visits_per_month': np.random.poisson(8, n_customers),
        'email_open_rate': np.random.uniform(0.1, 0.8, n_customers),
        'support_tickets': np.random.poisson(2, n_customers),
        'loyalty_program_member': np.random.choice([0, 1], n_customers, p=[0.6, 0.4]),
        
        # Outcome
        'customer_lifetime_value': np.random.exponential(500, n_customers),
        'will_churn': np.random.choice([0, 1], n_customers, p=[0.8, 0.2])
    })
    
    # Business context
    business_goal = """
    Reduce customer churn by 25% over the next 12 months by identifying at-risk customers
    and implementing targeted retention strategies. We want to understand the key drivers
    of churn and be able to predict which customers are most likely to leave.
    """
    
    training_objective = """
    Build a classification model to predict customer churn (will_churn = 1) with high precision.
    The model should be interpretable so our customer success team can understand why
    specific customers are at risk and take appropriate action.
    """
    
    business_knowledge = """
    E-commerce retail company with subscription-based and one-time customers.
    
    Key Business Insights:
    - Customers who haven't purchased in 60+ days are high churn risk
    - Higher engagement (website visits, email opens) correlates with retention
    - Loyalty program members have 40% lower churn rate
    - Support ticket volume can indicate either engagement or frustration
    - Customer lifetime value varies significantly by product category
    - Seasonal patterns affect purchase behavior (holidays, back-to-school)
    - Acquisition channel impacts long-term value and retention
    
    Business Rules:
    - New customers (< 6 months) have different behavior patterns
    - High-value customers (top 20%) get special treatment
    - Geographic location affects shipping costs and satisfaction
    - Product category preferences indicate customer segments
    """
    
    data_description = """
    Customer dataset containing demographics, transaction history, engagement metrics,
    and churn outcomes. Data represents 2 years of customer interactions.
    """
    
    # Initialize and run the agent
    print("🧠 Starting Feature Recommendation Agent Demo...")
    print("=" * 55)
    
    agent = FeatureRecommendationAgent()
    
    results = agent.recommend_features(
        data=data,
        business_goal=business_goal,
        training_objective=training_objective,
        business_knowledge=business_knowledge,
        data_description=data_description,
        session_id="churn_demo"
    )
    
    # Display results
    print(f"\n📊 **Data Analysis Summary:**")
    print(f"• Dataset Shape: {results['data_analysis']['shape']}")
    print(f"• Data Quality Score: {results['data_analysis']['data_quality_score']:.1%}")
    print(f"• Columns Available: {len(results['data_analysis']['column_types'])}")
    
    print(f"\n🎯 **Domain Insights:**")
    print(f"• Industry Domain: {results['domain_insights'].get('domain', 'Not identified')}")
    print(f"• Key Business Drivers: {', '.join(results['domain_insights'].get('key_business_drivers', [])[:3])}")
    
    print(f"\n⭐ **Top Feature Recommendations:**")
    for i, feature_name in enumerate(results['top_features'][:5], 1):
        # Find the full recommendation
        full_rec = next((rec for rec in results['recommended_features'] if rec['feature_name'] == feature_name), None)
        if full_rec:
            print(f"\n{i}. **{full_rec['feature_name']}**")
            print(f"   • Source: {', '.join(full_rec['source_columns'])}")
            print(f"   • Type: {full_rec['feature_type']}")
            print(f"   • Expected Importance: {full_rec['expected_importance']:.1%}")
            print(f"   • Creation: {full_rec['creation_steps'][:100]}...")
            print(f"   • Business Value: {full_rec['business_reasoning'][:120]}...")
    
    print(f"\n🛠️ **Implementation Plan:**")
    implementation_plan = results['implementation_phases']
    for phase, details in implementation_plan.items():
        print(f"\n**{phase.upper()}:**")
        print(f"• Features: {', '.join(details.get('features', [])[:3])}")
        print(f"• Effort: {details.get('effort_estimate', 'Not estimated')}")
        print(f"• Success Criteria: {details.get('success_criteria', 'Not defined')}")
    
    print(f"\n📋 **Executive Summary:**")
    print("=" * 25)
    print(results['executive_summary'])
    
    print(f"\n✅ **Feature Recommendation Complete!**")
    print(f"• Total Features: {results['total_features_recommended']}")
    print(f"• Complexity Level: {results['session_metadata']['complexity_level']}")
    print(f"• Expected Impact: {results['session_metadata']['estimated_impact']}")
    
    return results


# Tool wrapper for integration
def create_feature_recommendation_tool():
    """Create a tool that can be used by other agents"""
    
    agent = FeatureRecommendationAgent()
    tool = FeatureRecommendationTool(agent)
    
    return tool.recommend_features_for_goal


if __name__ == "__main__":
    # Run the demo
    import os
    os.environ["OPENAI_API_KEY"] = "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"
    demo_results = demo_feature_recommendation_agent()
    
    # Example of using as a tool
    print(f"\n🔧 **Tool Integration Example:**")
    print("=" * 35)
    
    tool_function = create_feature_recommendation_tool()
    
    # Sample data for tool demo
    sample_data = pd.DataFrame({
        'revenue': [100, 200, 150, 300],
        'customers': [10, 25, 15, 40],
        'marketing_spend': [50, 100, 75, 150],
        'region': ['North', 'South', 'East', 'West']
    })
    
    tool_result = tool_function(
        data=sample_data,
        business_goal="Increase revenue efficiency",
        training_objective="Predict high-performing regions",
        business_knowledge="Revenue varies by region and marketing investment"
    )
    
    print(f"Tool Output - Top Features: {tool_result['top_features']}")
    print(f"Tool Output - Columns to Use: {tool_result['columns_to_use']}")
    print(f"Tool Output - Complexity: {tool_result['implementation_complexity']}")