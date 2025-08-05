import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
import json
import warnings
from datetime import datetime

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

# LangGraph imports  
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# Pipeline imports (assuming these are available)
from app.tools.mltools.models.causal_inference import *
from app.tools.mltools.models.kmeans_clustering import *  
from app.tools.mltools.models.prophet_forecast import *
from app.tools.mltools.models.randomforest_classifier import *

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def safe_json_serialize(obj):
    """
    Safely serialize objects to JSON, handling NumPy arrays and other non-serializable types.
    
    Parameters:
    -----------
    obj : Any
        Object to serialize
        
    Returns:
    --------
    str
        JSON string representation
    """
    def convert_to_serializable(item):
        if item is None:
            return None
        elif isinstance(item, np.ndarray):
            return item.tolist()
        elif isinstance(item, np.integer):
            return int(item)
        elif isinstance(item, np.floating):
            return float(item)
        elif isinstance(item, np.bool_):
            return bool(item)
        elif isinstance(item, dict):
            return {str(key): convert_to_serializable(value) for key, value in item.items()}
        elif isinstance(item, (list, tuple)):
            return [convert_to_serializable(element) for element in item]
        elif hasattr(item, '__dict__'):
            # Handle custom objects by converting to dict
            try:
                return convert_to_serializable(item.__dict__)
            except:
                return str(item)
        elif hasattr(item, 'tolist'):
            # Handle pandas objects and other array-like objects
            try:
                return item.tolist()
            except:
                return str(item)
        else:
            return item
    
    try:
        serializable_obj = convert_to_serializable(obj)
        return json.dumps(serializable_obj, indent=2, default=str)
    except Exception as e:
        # Fallback: convert to string representation
        try:
            return str(obj)
        except:
            return f"<Non-serializable object: {type(obj).__name__}>"


class ProblemType(Enum):
    """Enumeration of ML problem types"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression" 
    CLUSTERING = "clustering"
    FORECASTING = "forecasting"
    CAUSAL_INFERENCE = "causal_inference"
    UNKNOWN = "unknown"


class PipelineType(Enum):
    """Enumeration of available pipeline types"""
    RANDOM_FOREST = "RFPipe"
    CAUSAL = "CausalPipe"
    KMEANS = "KMeansPipe"
    PROPHET = "ProphetPipe"


@dataclass
class DataProfile:
    """Data profiling results"""
    shape: List[int]
    column_types: Dict[str, str]
    missing_values: Dict[str, int]
    categorical_features: List[str]
    numerical_features: List[str]
    datetime_features: List[str]
    target_candidates: List[str]
    data_quality_issues: List[str]


@dataclass 
class ModelRecommendation:
    """Model recommendation with reasoning"""
    pipeline_type: PipelineType
    problem_type: ProblemType
    confidence: float
    reasoning: str
    suggested_features: List[str]
    suggested_target: Optional[str]
    estimated_performance: str
    

@dataclass
class TrainingState:
    """State for the training agent workflow"""
    # Input from user
    business_goal: str = ""
    data_description: str = ""
    training_context: str = ""
    user_question: str = ""
    
    # Analysis results
    data_profile: Optional[Dict[str, Any]] = None
    intent: Optional[Dict[str, Any]] = None
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    selected_pipeline: Optional[str] = None
    
    # Training results
    training_results: Optional[Dict[str, Any]] = None
    feature_importance: Optional[Dict[str, float]] = None
    performance_metrics: Optional[Dict[str, float]] = None
    
    # Conversation context
    messages: List[Dict[str, str]] = field(default_factory=list)  # Store cleaned messages as dicts
    current_step: str = "start"
    explanation_requested: bool = False
    
    # Data reference - store only metadata, not the actual DataFrame
    data_shape: Optional[List[int]] = None
    data_columns: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a serializable dictionary"""
        return {
            'business_goal': self.business_goal,
            'data_description': self.data_description,
            'training_context': self.training_context,
            'user_question': self.user_question,
            'data_profile': self.data_profile,
            'intent': self.intent,
            'recommendations': self.recommendations,
            'selected_pipeline': self.selected_pipeline,
            'training_results': self.training_results,
            'feature_importance': self.feature_importance,
            'performance_metrics': self.performance_metrics,
            'messages': self.messages,
            'current_step': self.current_step,
            'explanation_requested': self.explanation_requested,
            'data_shape': self.data_shape,
            'data_columns': self.data_columns
        }
    
    def create_serializable_copy(self) -> 'TrainingState':
        """Create a copy of the state that is guaranteed to be serializable"""
        # Import the serialization helper (we'll need to pass it as a parameter)
        # For now, we'll create a simple copy and let the calling code handle serialization
        
        # Create a new state with all fields converted to serializable types
        new_state = TrainingState(
            business_goal=str(self.business_goal),
            data_description=str(self.data_description),
            training_context=str(self.training_context),
            user_question=str(self.user_question),
            data_profile=self.data_profile,
            intent=self.intent,
            recommendations=self.recommendations,
            selected_pipeline=str(self.selected_pipeline) if self.selected_pipeline else None,
            training_results=self.training_results,
            feature_importance=self.feature_importance,
            performance_metrics=self.performance_metrics,
            messages=self.messages,
            current_step=str(self.current_step),
            explanation_requested=bool(self.explanation_requested),
            data_shape=self.data_shape,
            data_columns=[str(col) for col in self.data_columns] if self.data_columns else None
        )
        
        return new_state


class InstructionsStore:
    """Store of instructions, examples and tools for different models"""
    
    @staticmethod
    def get_pipeline_instructions(pipeline_type: PipelineType) -> Dict[str, str]:
        """Get detailed instructions for each pipeline type"""
        
        instructions = {
            PipelineType.RANDOM_FOREST: {
                "description": "Random Forest is excellent for classification and regression tasks with tabular data",
                "best_for": "Classification, regression with mixed data types, feature importance analysis",
                "data_requirements": "Tabular data with clear target variable, handles missing values well",
                "strengths": "Robust, interpretable, handles non-linear relationships, provides feature importance",
                "limitations": "Can overfit with small datasets, less effective with very high-dimensional sparse data",
                "typical_use_cases": [
                    "Customer churn prediction",
                    "Risk assessment", 
                    "Medical diagnosis",
                    "Product recommendation scoring"
                ]
            },
            
            PipelineType.CAUSAL: {
                "description": "Causal inference for understanding cause-and-effect relationships",
                "best_for": "A/B testing, policy evaluation, treatment effect estimation",
                "data_requirements": "Data with treatment/control groups, confounding variables identified",
                "strengths": "Provides causal insights, handles confounders, quantifies treatment effects",
                "limitations": "Requires careful design, sensitive to hidden confounders",
                "typical_use_cases": [
                    "Marketing campaign effectiveness",
                    "Policy impact assessment",
                    "Medical treatment evaluation",
                    "Product feature impact analysis"
                ]
            },
            
            PipelineType.KMEANS: {
                "description": "K-means clustering for discovering hidden patterns and groupings",
                "best_for": "Customer segmentation, pattern discovery, unsupervised analysis",
                "data_requirements": "Numerical features, no target variable needed",
                "strengths": "Discovers hidden patterns, scalable, interpretable clusters",
                "limitations": "Requires choosing K, sensitive to outliers, assumes spherical clusters",
                "typical_use_cases": [
                    "Customer segmentation",
                    "Market research",
                    "Anomaly detection",
                    "Product categorization"
                ]
            },
            
            PipelineType.PROPHET: {
                "description": "Time series forecasting with automatic seasonality detection",
                "best_for": "Business forecasting, trend analysis, seasonal pattern modeling",
                "data_requirements": "Time series data with date and value columns",
                "strengths": "Handles seasonality automatically, robust to missing data, interpretable components",
                "limitations": "Primarily for univariate forecasting, requires sufficient historical data",
                "typical_use_cases": [
                    "Sales forecasting",
                    "Demand planning",
                    "Financial projections",
                    "Website traffic prediction"
                ]
            }
        }
        
        return instructions.get(pipeline_type, {})
    
    @staticmethod
    def get_feature_engineering_examples(pipeline_type: PipelineType) -> List[str]:
        """Get feature engineering examples for each pipeline"""
        
        examples = {
            PipelineType.RANDOM_FOREST: [
                "Create interaction features between categorical and numerical variables",
                "Apply log transformation to skewed numerical features",
                "One-hot encode categorical variables with reasonable cardinality",
                "Create binned versions of continuous variables",
                "Generate polynomial features for non-linear relationships"
            ],
            
            PipelineType.CAUSAL: [
                "Identify and include all potential confounding variables",
                "Create propensity score features for matching",
                "Include pre-treatment covariates only",
                "Consider interaction terms between treatment and confounders",
                "Include instrumental variables if available"
            ],
            
            PipelineType.KMEANS: [
                "Standardize all numerical features to same scale",
                "Create ratio features between related variables", 
                "Apply dimensionality reduction for high-dimensional data",
                "Remove highly correlated features",
                "Create aggregated features for grouped data"
            ],
            
            PipelineType.PROPHET: [
                "Add external regressors for known drivers",
                "Create holiday calendars for business-specific events",
                "Handle data quality issues and outliers",
                "Add capacity constraints for logistic growth",
                "Include weather or economic indicators as regressors"
            ]
        }
        
        return examples.get(pipeline_type, [])


class MLTrainingAgent:
    """Main ML Training Agent using LangGraph"""
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """Initialize the training agent"""
        self.llm = ChatOpenAI(model=llm_model, temperature=0.1)
        self.instructions_store = InstructionsStore()
        self.graph = self._build_graph()
        self._session_data = {}  # Store data separately by session
        self._current_data = None  # Store current session data
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the graph
        workflow = StateGraph(TrainingState)
        
        # Add nodes
        workflow.add_node("intent_identification", self._identify_intent)
        workflow.add_node("data_analysis", self._analyze_data)
        workflow.add_node("model_recommendation", self._recommend_models)
        workflow.add_node("feature_guidance", self._provide_feature_guidance)
        workflow.add_node("training_execution", self._execute_training)
        workflow.add_node("results_explanation", self._explain_results)
        workflow.add_node("qa_handler", self._handle_questions)
        workflow.add_node("final_summary", self._provide_final_summary)
        
        # Define the workflow logic
        workflow.add_edge(START, "intent_identification")
        workflow.add_edge("intent_identification", "data_analysis")
        workflow.add_edge("data_analysis", "model_recommendation")
        workflow.add_edge("model_recommendation", "feature_guidance")
        workflow.add_edge("feature_guidance", "training_execution")
        workflow.add_edge("training_execution", "results_explanation")
        
        # Conditional edges for Q&A
        workflow.add_conditional_edges(
            "results_explanation",
            self._should_handle_questions,
            {
                "questions": "qa_handler",
                "complete": "final_summary"
            }
        )
        
        workflow.add_conditional_edges(
            "qa_handler", 
            self._continue_qa_or_finish,
            {
                "more_questions": "qa_handler",
                "complete": "final_summary"
            }
        )
        
        workflow.add_edge("final_summary", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    def _identify_intent(self, state: TrainingState) -> TrainingState:
        """Step 1: Identify user intent and problem type"""
        
        intent_prompt = ChatPromptTemplate.from_template("""
        You are an expert ML consultant helping a business user understand their machine learning needs.
        
        Business Goal: {business_goal}
        Data Description: {data_description}  
        Training Context: {training_context}
        
        Analyze the user's intent and identify:
        1. What type of ML problem this is (classification, regression, clustering, forecasting, causal_inference)
        2. What the user is trying to achieve from a business perspective
        3. What success looks like for this project
        4. Any constraints or special requirements
        5. The level of ML expertise the user seems to have
        
        Respond in JSON format:
        {{
            "problem_type": "classification|regression|clustering|forecasting|causal_inference",
            "business_objective": "clear business objective", 
            "success_criteria": "what defines success",
            "constraints": ["list", "of", "constraints"],
            "user_expertise_level": "beginner|intermediate|advanced",
            "key_questions_to_address": ["question1", "question2"],
            "recommended_next_steps": ["step1", "step2"]
        }}
        """)
        
        chain = intent_prompt | self.llm | JsonOutputParser()
        
        intent_result = chain.invoke({
            "business_goal": state.business_goal,
            "data_description": state.data_description,
            "training_context": state.training_context
        })
        
        state.intent = intent_result
        state.current_step = "intent_identified"
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        🎯 **Intent Analysis Complete**
        
        **Problem Type:** {intent_result.get('problem_type', 'Unknown')}
        **Business Objective:** {intent_result.get('business_objective', 'Not specified')}
        **Success Criteria:** {intent_result.get('success_criteria', 'Not defined')}
        
        **Key Questions to Address:**
        {chr(10).join(f"• {q}" for q in intent_result.get('key_questions_to_address', []))}
        
        **Recommended Next Steps:**
        {chr(10).join(f"• {s}" for s in intent_result.get('recommended_next_steps', []))}
        """
        })
        print(f"Debug: Intent result: {intent_result}")
        
        return state
    
    def _analyze_data(self, state: TrainingState) -> TrainingState:
        """Step 2: Analyze the provided data"""
        
        # Get data from current session
        data = self._current_data
        
        print(f"Debug: Found data in current session: {data is not None}")
        if data is not None:
            print(f"Debug: Data shape: {data.shape}")
        
        if data is None:
            state.messages.append({
                'type': 'AIMessage',
                'content': """
            📊 **Data Analysis**
            
            No data has been provided yet. Please upload your dataset so I can:
            • Analyze data structure and quality
            • Identify potential features and targets
            • Detect data quality issues
            • Suggest preprocessing steps
            
            Once you provide the data, I'll perform a comprehensive analysis.
            """
            })
            state.current_step = "awaiting_data"
            return state
        
        # Perform data profiling
        data_profile = self._profile_data(data)
        # Convert to dictionary for serialization
        state.data_profile = {
            'shape': data_profile.shape,  # Already a list now
            'column_types': data_profile.column_types,
            'missing_values': data_profile.missing_values,
            'categorical_features': data_profile.categorical_features,
            'numerical_features': data_profile.numerical_features,
            'datetime_features': data_profile.datetime_features,
            'target_candidates': data_profile.target_candidates,
            'data_quality_issues': data_profile.data_quality_issues
        }
        
        # Create data analysis summary
        analysis_prompt = ChatPromptTemplate.from_template("""
        You are analyzing a dataset for machine learning. Based on the data profile below, provide insights:
        
        Data Shape: {shape}
        Column Types: {column_types}
        Missing Values: {missing_values}
        Categorical Features: {categorical_features}
        Numerical Features: {numerical_features}
        Datetime Features: {datetime_features}
        Data Quality Issues: {data_quality_issues}
        
        Business Goal: {business_goal}
        Problem Type: {problem_type}
        
        Provide a comprehensive analysis including:
        1. Data quality assessment
        2. Potential target variables based on business goal
        3. Recommended preprocessing steps
        4. Feature engineering opportunities
        5. Potential challenges or limitations
        
        Format as clear, business-friendly explanations.
        """)
        
        chain = analysis_prompt | self.llm | StrOutputParser()
        
        analysis_result = chain.invoke({
            "shape": state.data_profile['shape'],
            "column_types": state.data_profile['column_types'],
            "missing_values": state.data_profile['missing_values'],
            "categorical_features": state.data_profile['categorical_features'],
            "numerical_features": state.data_profile['numerical_features'],
            "datetime_features": state.data_profile['datetime_features'],
            "data_quality_issues": state.data_profile['data_quality_issues'],
            "business_goal": state.business_goal,
            "problem_type": state.intent.get('problem_type', 'unknown') if state.intent else 'unknown'
        })
        
        state.current_step = "data_analyzed"
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        📊 **Data Analysis Complete**
        
        **Dataset Overview:**
        • Shape: {state.data_profile['shape'][0]:,} rows × {state.data_profile['shape'][1]} columns
        • Data Quality: {len(state.data_profile['data_quality_issues'])} issues identified
        
        {analysis_result}
        """
        })
        print(f"Debug: Data analysis result: {analysis_result}")
        
        return state
    
    def _recommend_models(self, state: TrainingState) -> TrainingState:
        """Step 3: Recommend appropriate models/pipelines"""
        
        if not state.intent or not state.data_profile:
            return state
        
        # Get problem type from intent
        problem_type = state.intent.get('problem_type', 'unknown')
        
        # Generate model recommendations
        recommendations = self._generate_model_recommendations(
            problem_type, 
            state.data_profile, 
            state.business_goal
        )
        
        # Convert to dictionaries for serialization
        state.recommendations = []
        for rec in recommendations:
            state.recommendations.append({
                'pipeline_type': rec.pipeline_type.value,
                'problem_type': rec.problem_type.value,
                'confidence': rec.confidence,
                'reasoning': rec.reasoning,
                'suggested_features': rec.suggested_features,
                'suggested_target': rec.suggested_target,
                'estimated_performance': rec.estimated_performance
            })
        
        # Create recommendation explanation
        rec_prompt = ChatPromptTemplate.from_template("""
        You are an ML expert explaining model recommendations to a business user.
        
        Problem Type: {problem_type}
        Business Goal: {business_goal}
        
        Model Recommendations:
        {recommendations}
        
        Explain each recommendation in business terms:
        1. Why this model is suitable for their problem
        2. What are the trade-offs (accuracy vs interpretability vs speed)
        3. What kind of insights they can expect
        4. What business questions this model can answer
        
        Use clear, non-technical language that a business user can understand.
        """)
        
        chain = rec_prompt | self.llm | StrOutputParser()
        
        rec_explanation = chain.invoke({
            "problem_type": problem_type,
            "business_goal": state.business_goal,
            "recommendations": json.dumps([{
                "pipeline": rec['pipeline_type'],
                "confidence": rec['confidence'],
                "reasoning": rec['reasoning'],
                "expected_performance": rec['estimated_performance']
            } for rec in state.recommendations], indent=2)
        })
        
        state.current_step = "models_recommended"
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        🤖 **Model Recommendations**
        
        Based on your business goal and data analysis, here are my recommendations:
        
        {rec_explanation}
        
        **Next:** I'll guide you through feature engineering and model training for the best option.
        """
        })
        print(f"Debug: Model recommendations: {rec_explanation}")
        
        return state
    
    def _provide_feature_guidance(self, state: TrainingState) -> TrainingState:
        """Step 4: Provide feature engineering guidance"""
        
        if not state.recommendations:
            return state
        
        # Select the top recommendation
        best_recommendation = max(state.recommendations, key=lambda x: x['confidence'])
        state.selected_pipeline = best_recommendation['pipeline_type']
        
        # Get feature engineering guidance
        pipeline_type = PipelineType(best_recommendation['pipeline_type'])
        fe_examples = self.instructions_store.get_feature_engineering_examples(
            pipeline_type
        )
        
        feature_prompt = ChatPromptTemplate.from_template("""
        You are guiding a business user through feature engineering for {pipeline_type}.
        
        Available Features: {available_features}
        Recommended Target: {target}
        Business Goal: {business_goal}
        
        Feature Engineering Examples for this model type:
        {feature_examples}
        
        Provide specific, actionable guidance on:
        1. Which features are most likely to be important for their business goal
        2. What new features they should create and why
        3. How to handle categorical variables
        4. What preprocessing steps are needed
        5. Which features might be redundant or problematic
        
        Explain the business reasoning behind each recommendation.
        """)
        
        chain = feature_prompt | self.llm | StrOutputParser()
        
        feature_guidance = chain.invoke({
            "pipeline_type": best_recommendation['pipeline_type'],
            "available_features": state.data_profile['numerical_features'] + state.data_profile['categorical_features'] if state.data_profile else [],
            "target": best_recommendation['suggested_target'],
            "business_goal": state.business_goal,
            "feature_examples": "\n".join(f"• {ex}" for ex in fe_examples)
        })
        
        state.current_step = "feature_guidance_provided"
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        ⚙️ **Feature Engineering Guidance**
        
        **Selected Model:** {best_recommendation['pipeline_type']}
        **Confidence:** {float(best_recommendation.get('confidence', 0)):.1%}
        
        {feature_guidance}
        """
        })
        print(f"Debug: Feature guidance: {feature_guidance}")
        return state
    
    def _execute_training(self, state: TrainingState) -> TrainingState:
        """Step 5: Execute model training"""
        
        print("Debug: Entering _execute_training method")
        
        # Get data from current session
        data = self._current_data
        
        print(f"Debug: Data available: {data is not None}")
        if data is not None:
            print(f"Debug: Data shape: {data.shape}")
        print(f"Debug: Selected pipeline: {state.selected_pipeline}")
        
        if not state.selected_pipeline or data is None:
            state.messages.append(AIMessage(content="Cannot execute training: missing pipeline selection or data."))
            return state
        
        try:
            print(f"Debug: Starting training with pipeline: {state.selected_pipeline}")
            
            # Execute training based on selected pipeline
            if state.selected_pipeline == "RFPipe":
                results = self._train_random_forest(state, data)
            elif state.selected_pipeline == "CausalPipe":
                results = self._train_causal_model(state, data)
            elif state.selected_pipeline == "KMeansPipe":
                results = self._train_kmeans_model(state, data)
            elif state.selected_pipeline == "ProphetPipe":
                results = self._train_prophet_model(state, data)
            else:
                raise ValueError(f"Unknown pipeline type: {state.selected_pipeline}")
            
            print(f"Debug: Training completed, results: {results}")
            # Ensure results are serializable before storing in state
            serializable_results = self._ensure_serializable(results)
            state.training_results = serializable_results
            state.current_step = "training_completed"
            
            # Also store results in session data for easy access
            self._session_data["results"] = serializable_results
            
            state.messages.append({
                'type': 'AIMessage',
                'content': f"""
            ✅ **Training Complete**
            
            **Model:** {state.selected_pipeline}
            **Status:** Successfully trained and evaluated
            
            **Quick Results:**
            {self._format_quick_results(results)}
            
            **Next:** Let me explain what these results mean for your business...
            """
            })
            print(f"Debug: Training results: {results}")
            print(f"Training Complete\nModel: {state.selected_pipeline}\nStatus: Successfully trained and evaluated\n Quick Results:\n{self._format_quick_results(results)}\n Next: Let me explain what these results mean for your business.\n")
            
            # Debug: Check messages after adding
            print(f"Debug: Messages count after adding training message: {len(state.messages)}")
            print(f"Debug: Last message: {state.messages[-1] if state.messages else 'No messages'}")
            
            # Debug: Check state for DataFrames before returning
            print("Debug: Checking state for DataFrames before returning...")
            self._inspect_for_dataframes(state, "state")
            
            # Ensure all state fields are serializable before returning
            print("Debug: Ensuring all state fields are serializable...")
            try:
                if state.data_profile:
                    state.data_profile = self._ensure_serializable(state.data_profile)
                if state.intent:
                    state.intent = self._ensure_serializable(state.intent)
                if state.recommendations:
                    state.recommendations = self._ensure_serializable(state.recommendations)
                if state.training_results:
                    state.training_results = self._ensure_serializable(state.training_results)
                if state.feature_importance:
                    state.feature_importance = self._ensure_serializable(state.feature_importance)
                if state.performance_metrics:
                    state.performance_metrics = self._ensure_serializable(state.performance_metrics)
                if state.messages:
                    print(f"Debug: Messages before serialization: {len(state.messages)}")
                    state.messages = self._ensure_serializable(state.messages)
                    print(f"Debug: Messages after serialization: {len(state.messages)}")
                print("Debug: All state fields serialized successfully")
                
                # Additional check: inspect the state object's attributes directly
                print("Debug: Inspecting state object attributes...")
                for attr_name in dir(state):
                    if not attr_name.startswith('_'):
                        try:
                            attr_value = getattr(state, attr_name)
                            if str(type(attr_value)).startswith("<class 'pandas"):
                                print(f"⚠️  Found pandas object in state.{attr_name}: {type(attr_value)}")
                        except Exception as attr_error:
                            print(f"Debug: Error inspecting state.{attr_name}: {attr_error}")
                
                # Create a clean, serializable copy of the state
                print("Debug: Creating serializable copy of state...")
                try:
                    clean_state = state.create_serializable_copy()
                    
                    # Apply serialization to all fields in the copy
                    if clean_state.data_profile:
                        clean_state.data_profile = self._ensure_serializable(clean_state.data_profile)
                    if clean_state.intent:
                        clean_state.intent = self._ensure_serializable(clean_state.intent)
                    if clean_state.recommendations:
                        clean_state.recommendations = self._ensure_serializable(clean_state.recommendations)
                    if clean_state.training_results:
                        clean_state.training_results = self._ensure_serializable(clean_state.training_results)
                    if clean_state.feature_importance:
                        clean_state.feature_importance = self._ensure_serializable(clean_state.feature_importance)
                    if clean_state.performance_metrics:
                        clean_state.performance_metrics = self._ensure_serializable(clean_state.performance_metrics)
                    if clean_state.messages:
                        print(f"Debug: Messages in clean_state before serialization: {len(clean_state.messages)}")
                        clean_state.messages = self._ensure_serializable(clean_state.messages)
                        print(f"Debug: Messages in clean_state after serialization: {len(clean_state.messages)}")
                    
                    print("Debug: Serializable copy created and serialized successfully")
                    
                    # Final validation: ensure no DataFrames remain
                    print("Debug: Final validation of clean state...")
                    self._inspect_for_dataframes(clean_state, "clean_state")
                    
                    return clean_state
                except Exception as copy_error:
                    print(f"Debug: Error creating serializable copy: {copy_error}")
                    import traceback
                    traceback.print_exc()
                    # Return original state if copy fails
                    return state
                    
            except Exception as serialize_error:
                print(f"Debug: Error serializing state fields: {serialize_error}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"Debug: Training failed with error: {e}")
            import traceback
            traceback.print_exc()
            state.current_step = "training_failed"
            # Create a safe error result that won't cause serialization issues
            error_results = {
                "model_type": "Error",
                "error": str(e),
                "status": "failed"
            }
            state.training_results = error_results
            self._session_data["results"] = error_results
            
            state.messages.append({
                'type': 'AIMessage',
                'content': f"""
            ❌ **Training Failed**
            
            An error occurred during training: {str(e)}
            
            Let me help you troubleshoot this issue...
            """
            })
        
        return state
    
    def _explain_results(self, state: TrainingState) -> TrainingState:
        """Step 6: Explain training results and feature importance"""
        
        if not state.training_results:
            return state
        
        # Create detailed explanation
        explanation_prompt = ChatPromptTemplate.from_template("""
        You are explaining ML training results to a business user in clear, actionable terms.
        
        Business Goal: {business_goal}
        Model Type: {model_type}
        Training Results: {training_results}
        
        Provide a comprehensive explanation covering:
        1. **Performance Summary**: How well the model performed (in business terms)
        2. **Feature Importance**: Which factors are most important for predictions and why
        3. **Business Insights**: What this means for their business decisions
        4. **Reliability**: How confident we can be in these results
        5. **Next Steps**: What they should do with this model
        6. **Limitations**: What the model cannot do or predict
        
        Use specific examples and avoid technical jargon. Focus on actionable business insights.
        """)
        
        chain = explanation_prompt | self.llm | StrOutputParser()
        
        explanation = chain.invoke({
            "business_goal": state.business_goal,
            "model_type": state.selected_pipeline if state.selected_pipeline else "Unknown",
            "training_results": safe_json_serialize(state.training_results)
        })
        
        state.current_step = "results_explained"
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        📈 **Results Explanation**
        
        {explanation}
        
        **Questions?** Feel free to ask me anything about these results, feature importance, or how to use this model for your business!
        """
        })
        
        return state
    
    def _handle_questions(self, state: TrainingState) -> TrainingState:
        """Handle user questions about the model and results"""
        
        if not state.user_question:
            return state
        
        qa_prompt = ChatPromptTemplate.from_template("""
        You are an ML expert answering business user questions about their trained model.
        
        Business Goal: {business_goal}
        Model Type: {model_type}
        Training Results: {training_results}
        Feature Importance: {feature_importance}
        
        User Question: {user_question}
        
        Provide a clear, helpful answer that:
        1. Directly addresses their question
        2. Uses their specific model results and data
        3. Explains concepts in business terms
        4. Provides actionable insights when relevant
        5. Suggests follow-up actions if appropriate
        
        Be conversational and helpful, like a trusted ML consultant.
        """)
        
        chain = qa_prompt | self.llm | StrOutputParser()
        
        answer = chain.invoke({
            "business_goal": state.business_goal,
            "model_type": state.selected_pipeline if state.selected_pipeline else "Unknown",
            "training_results": safe_json_serialize(state.training_results or {}),
            "feature_importance": safe_json_serialize(state.feature_importance or {}),
            "user_question": state.user_question
        })
        
        state.messages.append({
            'type': 'HumanMessage',
            'content': state.user_question
        })
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        💡 **Answer to Your Question**
        
        {answer}
        
        **Any other questions?** I'm here to help you understand your model and how to use it effectively!
        """
        })
        
        # Reset question for next iteration
        state.user_question = ""
        
        return state
    
    def _provide_final_summary(self, state: TrainingState) -> TrainingState:
        """Provide final summary and next steps"""
        
        summary_prompt = ChatPromptTemplate.from_template("""
        Create a final executive summary for a business user about their ML training project.
        
        Business Goal: {business_goal}
        Model Type: {model_type}  
        Training Results: {training_results}
        Key Insights: {key_insights}
        
        Provide:
        1. **Executive Summary**: What was accomplished
        2. **Key Findings**: Most important insights from the analysis
        3. **Business Impact**: How this model can drive business value
        4. **Implementation Roadmap**: Clear next steps to put this into action
        5. **Success Metrics**: How to measure ongoing performance
        
        Keep it concise but actionable. This should be something they can share with stakeholders.
        """)
        
        chain = summary_prompt | self.llm | StrOutputParser()
        
        # Extract key insights from messages
        key_insights = [msg['content'] for msg in state.messages if msg.get('type') == 'AIMessage'][-3:]  # Last 3 AI messages
        
        summary = chain.invoke({
            "business_goal": state.business_goal,
            "model_type": state.selected_pipeline if state.selected_pipeline else "Unknown",
            "training_results": safe_json_serialize(state.training_results or {}),
            "key_insights": "\n".join(key_insights)
        })
        
        state.current_step = "completed"
        state.messages.append({
            'type': 'AIMessage',
            'content': f"""
        📋 **Final Summary & Next Steps**
        
        {summary}
        
        **Your model is ready!** The training artifacts have been saved and can now be used by the Prediction Agent for making new predictions.
        """
        })
        
        return state
    
    # Conditional edge functions
    def _should_handle_questions(self, state: TrainingState) -> Literal["questions", "complete"]:
        """Determine if we should handle questions or complete"""
        return "questions" if state.explanation_requested else "complete"
    
    def _continue_qa_or_finish(self, state: TrainingState) -> Literal["more_questions", "complete"]:
        """Determine if more Q&A is needed"""
        return "more_questions" if state.user_question else "complete"
    
    # Helper methods
    def _profile_data(self, data: pd.DataFrame) -> DataProfile:
        """Profile the provided data"""
        
        # Analyze column types
        column_types = {}
        categorical_features = []
        numerical_features = []
        datetime_features = []
        
        for col in data.columns:
            if pd.api.types.is_numeric_dtype(data[col]):
                column_types[col] = "numerical"
                numerical_features.append(col)
            elif pd.api.types.is_datetime64_any_dtype(data[col]):
                column_types[col] = "datetime"
                datetime_features.append(col)
            else:
                column_types[col] = "categorical"
                categorical_features.append(col)
        
        # Check for missing values
        missing_values_series = data.isnull().sum()
        missing_values = {str(col): int(count) for col, count in missing_values_series.items()}
        
        # Identify potential target variables
        target_candidates = []
        for col in data.columns:
            if any(keyword in col.lower() for keyword in ['target', 'label', 'class', 'outcome', 'result']):
                target_candidates.append(col)
        
        # Identify data quality issues
        data_quality_issues = []
        
        # Check for high missing values
        for col, missing_count in missing_values.items():
            if missing_count > len(data) * 0.5:
                data_quality_issues.append(f"Column '{col}' has {missing_count}/{len(data)} missing values")
        
        # Check for high cardinality categorical features
        for col in categorical_features:
            unique_count = data[col].nunique()
            if unique_count > len(data) * 0.8:
                data_quality_issues.append(f"Column '{col}' has very high cardinality ({unique_count} unique values)")
        
        return DataProfile(
            shape=[int(dim) for dim in data.shape],  # Convert tuple to list
            column_types=column_types,
            missing_values=missing_values,
            categorical_features=categorical_features,
            numerical_features=numerical_features,
            datetime_features=datetime_features,
            target_candidates=target_candidates,
            data_quality_issues=data_quality_issues
        )
    
    def _generate_model_recommendations(self, problem_type: str, data_profile: Dict[str, Any], business_goal: str) -> List[ModelRecommendation]:
        """Generate model recommendations based on problem type and data"""
        
        recommendations = []
        
        # Random Forest - good for most tabular problems
        if problem_type in ['classification', 'regression'] and data_profile['numerical_features']:
            rf_confidence = 0.8 if len(data_profile['numerical_features']) > 5 else 0.6
            recommendations.append(ModelRecommendation(
                pipeline_type=PipelineType.RANDOM_FOREST,
                problem_type=ProblemType(problem_type),
                confidence=rf_confidence,
                reasoning=f"Random Forest is excellent for {problem_type} with mixed data types. Your dataset has {len(data_profile['numerical_features'])} numerical and {len(data_profile['categorical_features'])} categorical features, which Random Forest handles well.",
                suggested_features=data_profile['numerical_features'] + data_profile['categorical_features'][:10],  # Limit categorical
                suggested_target=data_profile['target_candidates'][0] if data_profile['target_candidates'] else None,
                estimated_performance="High accuracy expected with good feature importance insights"
            ))
        
        # Prophet for time series
        if problem_type == 'forecasting' or data_profile['datetime_features']:
            prophet_confidence = 0.9 if data_profile['datetime_features'] else 0.3
            recommendations.append(ModelRecommendation(
                pipeline_type=PipelineType.PROPHET,
                problem_type=ProblemType.FORECASTING,
                confidence=prophet_confidence,
                reasoning="Prophet is ideal for time series forecasting with automatic seasonality detection. Perfect for business forecasting tasks.",
                suggested_features=data_profile['datetime_features'] + data_profile['numerical_features'][:5],
                suggested_target=None,
                estimated_performance="Good forecasting accuracy with interpretable seasonal components"
            ))
        
        # K-means for clustering
        if problem_type == 'clustering' or 'segment' in business_goal.lower():
            kmeans_confidence = 0.7 if len(data_profile['numerical_features']) > 3 else 0.4
            recommendations.append(ModelRecommendation(
                pipeline_type=PipelineType.KMEANS,
                problem_type=ProblemType.CLUSTERING,
                confidence=kmeans_confidence,
                reasoning="K-means clustering will help discover natural groupings in your data, perfect for customer segmentation or pattern discovery.",
                suggested_features=data_profile['numerical_features'],
                suggested_target=None,
                estimated_performance="Clear cluster separation expected with actionable segments"
            ))
        
        # Causal inference for A/B testing or treatment effects
        if 'causal' in business_goal.lower() or 'treatment' in business_goal.lower() or 'effect' in business_goal.lower():
            causal_confidence = 0.8
            recommendations.append(ModelRecommendation(
                pipeline_type=PipelineType.CAUSAL,
                problem_type=ProblemType.CAUSAL_INFERENCE,
                confidence=causal_confidence,
                reasoning="Causal inference is perfect for understanding treatment effects and making policy decisions based on data.",
                suggested_features=data_profile['numerical_features'] + data_profile['categorical_features'],
                suggested_target=data_profile['target_candidates'][0] if data_profile['target_candidates'] else None,
                estimated_performance="Reliable causal effect estimates with confidence intervals"
            ))
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x.confidence, reverse=True)
        
        return recommendations[:3]  # Return top 3 recommendations
    
    def _train_random_forest(self, state: TrainingState, data: pd.DataFrame) -> Dict[str, Any]:
        """Execute Random Forest training"""
        
        print("Debug: Starting _train_random_forest method")
        
        # Debug: Check if pipeline functions are imported
        try:
            print("Debug: Checking pipeline function imports...")
            print(f"Debug: generate_categorical_features available: {generate_categorical_features is not None}")
            print(f"Debug: create_binary_labels available: {create_binary_labels is not None}")
            print(f"Debug: train_random_forest available: {train_random_forest is not None}")
            print(f"Debug: predict available: {predict is not None}")
            print(f"Debug: calculate_metrics available: {calculate_metrics is not None}")
            print(f"Debug: save_model available: {save_model is not None}")
            print(f"Debug: RFPipe available: {RFPipe is not None}")
        except NameError as e:
            print(f"Debug: Import error - {e}")
            raise
        
        if data is None:
            raise ValueError("No data available for training")
        
        print(f"Debug: Data shape: {data.shape}")
        print(f"Debug: Data columns: {list(data.columns)}")
        
        # Get recommended features and target
        best_rec = max(state.recommendations, key=lambda x: x['confidence'])
        feature_cols = [col for col in best_rec['suggested_features'] if col in data.columns]
        target_col = best_rec['suggested_target']
        
        print(f"Debug: Best recommendation: {best_rec}")
        print(f"Debug: Feature columns: {feature_cols}")
        print(f"Debug: Target column: {target_col}")
        
        if not target_col:
            # Try to infer target column
            if state.data_profile and state.data_profile['target_candidates']:
                target_col = state.data_profile['target_candidates'][0]
            else:
                # Look for common target column names
                target_candidates = ['will_leave', 'target', 'label', 'class', 'outcome', 'churn', 'default']
                for candidate in target_candidates:
                    if candidate in data.columns:
                        target_col = candidate
                        break
                
                if not target_col:
                    raise ValueError("No target column identified. Please specify the target variable.")
        
        print(f"Debug: Final target column: {target_col}")
        
        # Create and train RF pipeline
        try:
            print("Debug: Creating RFPipe...")
            rf_pipe = RFPipe(data)
            print("Debug: RFPipe created successfully")
        except Exception as e:
            print(f"Debug: Error creating RFPipe: {e}")
            raise
        
        # Determine if target is binary/categorical
        unique_values = data[target_col].nunique()
        print(f"Debug: Target unique values: {unique_values}")
        
        if unique_values <= 10:  # Assume classification
            # For classification, use the target column as is
            available_features = [col for col in feature_cols if col in data.columns]
            print(f"Debug: Classification path - available_features: {available_features}")
            
            try:
                print("Debug: Starting pipeline execution...")
                print("Debug: Step 1: generate_categorical_features")
                rf_pipe = rf_pipe | generate_categorical_features(available_features)
                print("Debug: Step 1 completed")
                
                # Check if features were added, if not, add some numerical features as fallback
                if not rf_pipe.feature_columns:
                    print("Debug: No features added by generate_categorical_features, adding numerical features as fallback")
                    numerical_cols = data.select_dtypes(include=[np.number]).columns.tolist()
                    numerical_cols = [col for col in numerical_cols if col != target_col]
                    if numerical_cols:
                        rf_pipe.feature_columns = numerical_cols[:5]  # Use first 5 numerical columns
                        print(f"Debug: Added fallback features: {rf_pipe.feature_columns}")
                
                print("Debug: Step 2: create_binary_labels")
                rf_pipe = rf_pipe | create_binary_labels(target_col, condition='==1', label_column='target')
                print("Debug: Step 2 completed")
                
                print("Debug: Step 3: train_random_forest")
                rf_pipe = rf_pipe | train_random_forest(model_name='random_forest_model')
                print("Debug: Step 3 completed")
                
                print("Debug: Step 4: predict")
                rf_pipe = rf_pipe | predict(model_name='random_forest_model')
                print("Debug: Step 4 completed")
                
                print("Debug: Step 5: calculate_metrics")
                rf_pipe = rf_pipe | calculate_metrics(model_name='random_forest_model')
                print("Debug: Step 5 completed")
                
                print("Debug: Step 6: save_model")
                rf_pipe = rf_pipe | save_model('random_forest_model')
                print("Debug: Step 6 completed")
                
            except Exception as e:
                print(f"Debug: Error in pipeline execution: {e}")
                import traceback
                traceback.print_exc()
                raise
            
        else:  # Regression - convert to classification for demo
            median_val = data[target_col].median()
            # Use available features, prioritizing categorical ones
            available_features = [col for col in feature_cols[:5] if col in data.columns]
            categorical_features = [col for col in available_features if col in data.select_dtypes(include=['object', 'category']).columns]
            if not categorical_features:
                categorical_features = available_features  # Use any available features if no categorical ones
            print(f"Debug: Regression path - categorical_features: {categorical_features}")
            print(f"Debug: target_col: {target_col}")
            
            try:
                print("Debug: Starting pipeline execution (regression path)...")
                print("Debug: Step 1: generate_categorical_features")
                rf_pipe = rf_pipe | generate_categorical_features(categorical_features)
                print("Debug: Step 1 completed")
                
                # Check if features were added, if not, add some numerical features as fallback
                if not rf_pipe.feature_columns:
                    print("Debug: No features added by generate_categorical_features, adding numerical features as fallback")
                    numerical_cols = data.select_dtypes(include=[np.number]).columns.tolist()
                    numerical_cols = [col for col in numerical_cols if col != target_col]
                    if numerical_cols:
                        rf_pipe.feature_columns = numerical_cols[:5]  # Use first 5 numerical columns
                        print(f"Debug: Added fallback features: {rf_pipe.feature_columns}")
                
                print("Debug: Step 2: create_binary_labels")
                rf_pipe = rf_pipe | create_binary_labels(target_col, condition=f'>{median_val}', label_column='target')
                print("Debug: Step 2 completed")
                
                print("Debug: Step 3: train_random_forest")
                rf_pipe = rf_pipe | train_random_forest(model_name='random_forest_model')
                print("Debug: Step 3 completed")
                
                print("Debug: Step 4: predict")
                rf_pipe = rf_pipe | predict(model_name='random_forest_model')
                print("Debug: Step 4 completed")
                
                print("Debug: Step 5: calculate_metrics")
                rf_pipe = rf_pipe | calculate_metrics(model_name='random_forest_model')
                print("Debug: Step 5 completed")
                
                print("Debug: Step 6: save_model")
                rf_pipe = rf_pipe | save_model('random_forest_model')
                print("Debug: Step 6 completed")
                
            except Exception as e:
                print(f"Debug: Error in pipeline execution (regression path): {e}")
                import traceback
                traceback.print_exc()
                raise
        
        # Get results - create a custom summary since get_summary() is failing
        try:
            print("Debug: Creating custom summary...")
            summary = {
                "model_type": "RandomForestClassifier",
                "status": "success",
                "target_column": str(target_col),
                "feature_columns": [str(col) for col in feature_cols],
                "data_shape": [int(dim) for dim in data.shape],  # Convert tuple to list of ints
                "training_completed": True
            }
            print(f"Debug: Custom summary created: {summary}")
        except Exception as e:
            print(f"Debug: Error creating summary: {e}")
            summary = {"error": str(e)}
        
        print(f"Debug: Summary completed: {summary}")
        
        # Extract feature importance
        try:
            if hasattr(rf_pipe, 'predictions') and rf_pipe.predictions:
                pred_name = list(rf_pipe.predictions.keys())[0]
                if 'feature_importance' in rf_pipe.predictions[pred_name]:
                    importance_df = rf_pipe.predictions[pred_name]['feature_importance']
                    print(f"Debug: importance_df type: {type(importance_df)}")
                    print(f"Debug: importance_df shape: {importance_df.shape if hasattr(importance_df, 'shape') else 'no shape'}")
                    
                    # Handle different data types
                    if hasattr(importance_df, 'to_dict'):
                        # It's a DataFrame
                        try:
                            importance_dict = importance_df.to_dict('records')
                            state.feature_importance = {
                                str(item['feature']): float(item['importance']) 
                                for item in importance_dict
                            }
                        except Exception as df_error:
                            print(f"Debug: DataFrame conversion failed: {df_error}")
                            # Try alternative approach
                            try:
                                state.feature_importance = {
                                    str(feature): float(importance) 
                                    for feature, importance in zip(importance_df['feature'], importance_df['importance'])
                                }
                            except Exception as alt_error:
                                print(f"Debug: Alternative approach failed: {alt_error}")
                                state.feature_importance = {}
                    elif isinstance(importance_df, np.ndarray):
                        # It's a NumPy array - try to extract feature names and importance values
                        try:
                            print(f"Debug: NumPy array shape: {importance_df.shape}")
                            if len(importance_df.shape) == 2 and importance_df.shape[1] >= 2:
                                # Assume first column is feature names, second is importance
                                features = importance_df[:, 0]
                                importances = importance_df[:, 1]
                                state.feature_importance = {
                                    str(feature): float(importance) 
                                    for feature, importance in zip(features, importances)
                                }
                            elif len(importance_df.shape) == 1:
                                # Single array - use feature columns as names
                                if hasattr(rf_pipe, 'feature_columns') and rf_pipe.feature_columns:
                                    state.feature_importance = {
                                        str(feature): float(importance) 
                                        for feature, importance in zip(rf_pipe.feature_columns, importance_df)
                                    }
                                else:
                                    # Use generic feature names
                                    state.feature_importance = {
                                        f"feature_{i}": float(importance) 
                                        for i, importance in enumerate(importance_df)
                                    }
                            else:
                                print(f"Debug: Unexpected NumPy array shape: {importance_df.shape}")
                                state.feature_importance = {}
                        except Exception as np_error:
                            print(f"Debug: NumPy array processing failed: {np_error}")
                            state.feature_importance = {}
                    elif isinstance(importance_df, dict):
                        # It's already a dict
                        state.feature_importance = {
                            str(feature): float(importance) 
                            for feature, importance in importance_df.items()
                        }
                    else:
                        print(f"Debug: Unknown importance_df type: {type(importance_df)}")
                        state.feature_importance = {}
                    
                    print(f"Debug: Feature importance extracted: {state.feature_importance}")
        except Exception as e:
            print(f"Debug: Error extracting feature importance: {e}")
            import traceback
            traceback.print_exc()
            state.feature_importance = {}
        
        # Extract performance metrics
        try:
            if hasattr(rf_pipe, 'metrics') and rf_pipe.metrics:
                metric_name = list(rf_pipe.metrics.keys())[0]
                metrics = rf_pipe.metrics[metric_name]
                # Convert NumPy types to Python types for serialization
                state.performance_metrics = {}
                for key, value in metrics.items():
                    if isinstance(value, (np.integer, np.floating)):
                        state.performance_metrics[key] = float(value)
                    elif isinstance(value, np.ndarray):
                        state.performance_metrics[key] = value.tolist()
                    elif isinstance(value, dict):
                        # Handle nested dictionaries (like classification_report)
                        state.performance_metrics[key] = {}
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, (np.integer, np.floating)):
                                state.performance_metrics[key][sub_key] = float(sub_value)
                            else:
                                state.performance_metrics[key][sub_key] = sub_value
                    elif str(type(value)).startswith("<class 'pandas"):
                        # Handle pandas DataFrames and Series
                        print(f"Debug: Found pandas object in metrics[{key}]: {type(value)}")
                        if hasattr(value, 'shape'):
                            print(f"Debug: DataFrame shape: {value.shape}")
                        if hasattr(value, 'columns'):
                            print(f"Debug: DataFrame columns: {list(value.columns)}")
                        try:
                            if hasattr(value, 'to_dict'):
                                state.performance_metrics[key] = value.to_dict()
                            elif hasattr(value, 'tolist'):
                                state.performance_metrics[key] = value.tolist()
                            elif hasattr(value, 'values'):
                                state.performance_metrics[key] = value.values.tolist()
                            elif hasattr(value, 'columns') and 'feature' in value.columns and 'importance' in value.columns:
                                # Special handling for feature importance DataFrame
                                print(f"Debug: Converting feature importance DataFrame for {key}")
                                feature_importance_dict = {}
                                for _, row in value.iterrows():
                                    feature_importance_dict[str(row['feature'])] = float(row['importance'])
                                state.performance_metrics[key] = feature_importance_dict
                            else:
                                state.performance_metrics[key] = str(value)
                        except Exception as df_error:
                            print(f"Debug: Error converting DataFrame {key}: {df_error}")
                            state.performance_metrics[key] = str(value)
                    else:
                        state.performance_metrics[key] = value
                print(f"Debug: Performance metrics extracted: {state.performance_metrics}")
        except Exception as e:
            print(f"Debug: Error extracting performance metrics: {e}")
            state.performance_metrics = {}
        
        print(f"Debug: Final results - model_type: RandomForestClassifier\nsummary: {summary}\nfeature_importance: {state.feature_importance}\nperformance_metrics: {state.performance_metrics}\ntarget_column: {target_col}\nfeature_columns: {feature_cols}")

        # Ensure all values are serializable
        final_results = {
            "model_type": "RandomForestClassifier",
            "summary": summary,
            "feature_importance": state.feature_importance,
            "performance_metrics": state.performance_metrics,
            "target_column": str(target_col),
            "feature_columns": [str(col) for col in feature_cols]
        }
        
        # Debug: Check for any remaining DataFrames before serialization
        print("Debug: Checking final_results for DataFrames...")
        self._inspect_for_dataframes(final_results, "final_results")
        
        # Apply serialization helper to ensure everything is serializable
        serialized_results = self._ensure_serializable(final_results)
        
        # Debug: Check again after serialization
        print("Debug: Checking serialized_results for DataFrames...")
        self._inspect_for_dataframes(serialized_results, "serialized_results")
        
        return serialized_results
    
    def _train_causal_model(self, state: TrainingState, data: pd.DataFrame) -> Dict[str, Any]:
        """Execute Causal inference training"""
        
        # This is a simplified example - in practice, you'd need to identify treatment/outcome
        results = {
            "model_type": "CausalInference",
            "message": "Causal inference requires careful setup of treatment and outcome variables. Please specify these for proper analysis."
        }
        
        return self._ensure_serializable(results)
    
    def _train_kmeans_model(self, state: TrainingState, data: pd.DataFrame) -> Dict[str, Any]:
        """Execute K-means training"""
        
        if data is None:
            raise ValueError("No data available for training")
        
        numerical_cols = state.data_profile['numerical_features'] if state.data_profile else []
        if len(numerical_cols) < 2:
            raise ValueError("K-means requires at least 2 numerical features")
        
        # Create and train K-means pipeline with simplified approach
        kmeans_pipe = KMeansPipe(data)
        
        # Use only the first few numerical features for simplicity
        feature_cols = numerical_cols[:5]  # Limit to 5 features
        
        # Configure and fit K-means directly
        kmeans_pipe = (kmeans_pipe
                      | configure_kmeans(n_clusters=5, model_name='kmeans_model')
                      | fit_kmeans('kmeans_model', feature_subset=feature_cols)
                      | evaluate_clustering('kmeans_model')
                      | profile_clusters('kmeans_model'))
        
        try:
            summary = kmeans_pipe.get_summary()
        except Exception as e:
            print(f"Debug: Error getting K-means summary: {e}")
            summary = {"error": str(e)}
        
        results = {
            "model_type": "KMeans",
            "summary": summary,
            "n_clusters": 5,
            "feature_columns": [str(col) for col in feature_cols]
        }
        
        return self._ensure_serializable(results)
    
    def _train_prophet_model(self, state: TrainingState, data: pd.DataFrame) -> Dict[str, Any]:
        """Execute Prophet training"""
        
        if data is None:
            raise ValueError("No data available for training")
        
        datetime_cols = state.data_profile['datetime_features'] if state.data_profile else []
        numerical_cols = state.data_profile['numerical_features'] if state.data_profile else []
        
        if not datetime_cols or not numerical_cols:
            raise ValueError("Prophet requires datetime and numerical columns")
        
        # For now, return a simplified result since Prophet setup is complex
        results = {
            "model_type": "Prophet",
            "message": "Prophet time series forecasting requires specific data format with 'ds' (date) and 'y' (value) columns. Please ensure your data is properly formatted for time series analysis.",
            "date_column": str(datetime_cols[0]) if datetime_cols else None,
            "value_column": str(numerical_cols[0]) if numerical_cols else None
        }
        
        return self._ensure_serializable(results)
    
    def _ensure_serializable(self, obj):
        """Ensure an object is serializable by converting NumPy types to Python types"""
        if obj is None:
            return None
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, dict):
            return {str(key): self._ensure_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._ensure_serializable(item) for item in obj]
        elif hasattr(obj, 'dtype'):  # Handle pandas objects
            try:
                return obj.tolist()
            except:
                return str(obj)
        elif hasattr(obj, '__dict__'):  # Handle custom objects
            try:
                return self._ensure_serializable(obj.__dict__)
            except:
                return str(obj)
        elif hasattr(obj, '__weakref__') or 'weakref' in str(type(obj)):  # Handle weak references
            return f"<WeakRef: {type(obj).__name__}>"
        elif hasattr(obj, 'content'):  # Handle LangChain messages
            try:
                return {
                    'type': type(obj).__name__,
                    'content': str(obj.content)
                }
            except:
                return f"<{type(obj).__name__}: {str(obj)}>"
        elif callable(obj):  # Handle functions and methods
            return f"<Callable: {type(obj).__name__}>"
        elif str(type(obj)).startswith("<class 'pandas"):  # Handle any pandas objects
            print(f"Debug: Found pandas object in _ensure_serializable: {type(obj)}")
            try:
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                elif hasattr(obj, 'tolist'):
                    return obj.tolist()
                elif hasattr(obj, 'values'):
                    return obj.values.tolist()
                else:
                    return str(obj)
            except Exception as pandas_error:
                print(f"Debug: Error converting pandas object: {pandas_error}")
                return f"<PandasObject: {type(obj).__name__}>"
        else:
            try:
                # Try to convert to string as last resort
                return str(obj)
            except:
                return f"<Non-serializable: {type(obj).__name__}>"

    def _clean_messages_for_serialization(self, messages):
        """Clean LangChain messages to make them serializable"""
        cleaned_messages = []
        for msg in messages:
            try:
                if hasattr(msg, 'content'):
                    cleaned_msg = {
                        'type': type(msg).__name__,
                        'content': str(msg.content)
                    }
                    cleaned_messages.append(cleaned_msg)
                else:
                    cleaned_messages.append(str(msg))
            except Exception as e:
                print(f"Debug: Error cleaning message: {e}")
                cleaned_messages.append(f"<Error: {type(msg).__name__}>")
        return cleaned_messages

    def _inspect_for_dataframes(self, obj, path=""):
        """Recursively inspect an object for DataFrame references"""
        try:
            if obj is None:
                return
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    self._inspect_for_dataframes(value, f"{path}.{key}")
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    self._inspect_for_dataframes(item, f"{path}[{i}]")
            elif hasattr(obj, '__dict__'):
                for attr_name, attr_value in obj.__dict__.items():
                    self._inspect_for_dataframes(attr_value, f"{path}.{attr_name}")
            elif str(type(obj)).startswith("<class 'pandas"):
                print(f"⚠️  FOUND DATAFRAME at {path}: {type(obj)}")
                if hasattr(obj, 'shape'):
                    print(f"   Shape: {obj.shape}")
                if hasattr(obj, 'columns'):
                    print(f"   Columns: {list(obj.columns)}")
            elif hasattr(obj, 'dtype'):
                print(f"⚠️  FOUND PANDAS OBJECT at {path}: {type(obj)}")
                print(f"   Dtype: {obj.dtype}")
        except Exception as e:
            print(f"Error inspecting {path}: {e}")

    def _format_quick_results(self, results: Dict[str, Any]) -> str:
        """Format quick results summary"""
        
        model_type = results.get("model_type", "Unknown")
        
        def safe_format_percentage(value, default=0.0):
            """Safely format a value as a percentage"""
            try:
                if isinstance(value, (int, float)):
                    return f"{float(value):.1%}"
                elif isinstance(value, str):
                    # Try to convert string to float
                    return f"{float(value):.1%}"
                else:
                    return f"{default:.1%}"
            except (ValueError, TypeError):
                return f"{default:.1%}"
        
        if model_type == "RandomForestClassifier":
            metrics = results.get("performance_metrics", {})
            return f"""
            • **Accuracy:** {safe_format_percentage(metrics.get('accuracy', 0))}
            • **Precision:** {safe_format_percentage(metrics.get('precision', 0))}  
            • **Recall:** {safe_format_percentage(metrics.get('recall', 0))}
            • **F1-Score:** {safe_format_percentage(metrics.get('f1_score', 0))}
            """
        elif model_type == "KMeans":
            return f"""
            • **Clusters:** {results.get('n_clusters', 'Unknown')} segments identified
            • **Features:** {len(results.get('feature_columns', []))} features used
            """
        elif model_type == "Prophet":
            return f"""
            • **Forecast:** 30-day prediction generated
            • **Date Column:** {results.get('date_column', 'Unknown')}
            • **Value Column:** {results.get('value_column', 'Unknown')}
            """
        else:
            return "Training completed successfully"
    
    def run_training_session(self, 
                           business_goal: str,
                           data: pd.DataFrame,
                           data_description: str = "",
                           training_context: str = "",
                           session_id: str = "default") -> Dict[str, Any]:
        """Run a complete training session"""
        
        # Store data in session storage and current data
        # IMPORTANT: Never store DataFrames in the state - only store metadata
        self._session_data[session_id] = data
        self._current_data = data
        
        # Verify no DataFrames are being stored in the state
        print("Debug: Verifying no DataFrames in state...")
        if data is not None:
            print(f"Debug: Data shape: {data.shape}, Data type: {type(data)}")
            # Only store metadata, not the actual DataFrame
        
        # Initialize state with data metadata
        initial_state = TrainingState(
            business_goal=business_goal,
            data_description=data_description,
            training_context=training_context,
            data_shape=[int(dim) for dim in data.shape] if data is not None else None,  # Convert tuple to list
            data_columns=[str(col) for col in data.columns] if data is not None else None
        )
        
        # Ensure the initial state is serializable
        print("Debug: Ensuring initial state is serializable...")
        try:
            # Test serialization by converting to dict and back
            state_dict = {
                'business_goal': initial_state.business_goal,
                'data_description': initial_state.data_description,
                'training_context': initial_state.training_context,
                'data_shape': initial_state.data_shape,
                'data_columns': initial_state.data_columns,
                'messages': initial_state.messages,
                'current_step': initial_state.current_step,
                'explanation_requested': initial_state.explanation_requested,
                'data_profile': initial_state.data_profile,
                'intent': initial_state.intent,
                'recommendations': initial_state.recommendations,
                'selected_pipeline': initial_state.selected_pipeline,
                'training_results': initial_state.training_results,
                'feature_importance': initial_state.feature_importance,
                'performance_metrics': initial_state.performance_metrics,
                'user_question': initial_state.user_question
            }
            # Apply serialization helper to ensure everything is serializable
            serialized_dict = self._ensure_serializable(state_dict)
            print("Debug: Initial state serialization test passed")
            print(f"Debug: Serialized state keys: {list(serialized_dict.keys())}")
        except Exception as e:
            print(f"Debug: Initial state serialization test failed: {e}")
            import traceback
            traceback.print_exc()
            # Continue anyway, the workflow will handle serialization errors
        print(f"Debug: Initial state: {initial_state}")
        
        # Ensure the TrainingState object itself is serializable by applying serialization to all its fields
        print("Debug: Ensuring TrainingState object is serializable...")
        try:
            # Apply serialization helper to all fields that might contain non-serializable objects
            if initial_state.data_profile:
                initial_state.data_profile = self._ensure_serializable(initial_state.data_profile)
            if initial_state.intent:
                initial_state.intent = self._ensure_serializable(initial_state.intent)
            if initial_state.recommendations:
                initial_state.recommendations = self._ensure_serializable(initial_state.recommendations)
            if initial_state.training_results:
                initial_state.training_results = self._ensure_serializable(initial_state.training_results)
            if initial_state.feature_importance:
                initial_state.feature_importance = self._ensure_serializable(initial_state.feature_importance)
            if initial_state.performance_metrics:
                initial_state.performance_metrics = self._ensure_serializable(initial_state.performance_metrics)
            if initial_state.messages:
                initial_state.messages = self._ensure_serializable(initial_state.messages)
            print("Debug: TrainingState serialization applied successfully")
            
            # Deep inspection to find any DataFrame references
            print("Debug: Deep inspection for DataFrame references...")
            self._inspect_for_dataframes(initial_state, "initial_state")
            
        except Exception as e:
            print(f"Debug: TrainingState serialization failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Execute the workflow synchronously
        print("Debug: Starting workflow execution...")
        print(f"Debug: Initial state type: {type(initial_state)}")
        print(f"Debug: Initial state current_step: {initial_state.current_step}")
        print(f"Debug: Graph type: {type(self.graph)}")
        
        try:
            final_state = self.graph.invoke(
                initial_state,  # Pass the TrainingState object, not the dict
                config={"configurable": {"thread_id": session_id}}
            )
            print(f"Debug: Workflow completed, final_state type: {type(final_state)}")
            print(f"Debug: Workflow execution successful")
            
            # Debug: Check if we can get the current state from the graph
            try:
                current_state = self.graph.get_state(config={"configurable": {"thread_id": session_id}})
                print(f"Debug: Current state from graph: {type(current_state)}")
                if current_state and hasattr(current_state, 'values'):
                    current_values = current_state.values
                    if callable(current_values):
                        current_values = current_values()
                    print(f"Debug: Current state values: {list(current_values) if hasattr(current_values, '__iter__') else current_values}")
            except Exception as state_error:
                print(f"Debug: Error getting current state: {state_error}")
                
        except Exception as e:
            print(f"Debug: Workflow execution failed: {e}")
            import traceback
            traceback.print_exc()
            # Return a safe fallback result
            return {
                "final_state": None,
                "messages": [],
                "training_results": {"error": str(e), "status": "failed"},
                "feature_importance": {},
                "model_type": "Error"
            }
        
        # Debug: Print final state details and extract the actual TrainingState
        print(f"Debug: final_state type: {type(final_state)}")
        print(f"Debug: final_state dir: {[attr for attr in dir(final_state) if not attr.startswith('_')]}")
        
        # Extract the actual TrainingState from the LangGraph output
        actual_state = None
        
        if hasattr(final_state, 'values'):
            print(f"Debug: final_state has 'values' attribute")
            state_values = final_state.values
            if callable(state_values):
                state_values = state_values()
            print(f"Debug: state_values type: {type(state_values)}")
            print(f"Debug: state_values content: {list(state_values) if hasattr(state_values, '__iter__') else state_values}")
            
            # Try to find the TrainingState object in the values
            if hasattr(state_values, '__iter__'):
                # Iterate through the values directly (for dict_values, list, etc.)
                for i, value in enumerate(state_values):
                    print(f"Debug: Found value {i} with type {type(value)}")
                    if isinstance(value, TrainingState):
                        actual_state = value
                        print(f"Debug: Found TrainingState in values at index {i}")
                        break
                    elif hasattr(value, '__dict__'):
                        print(f"Debug: Value {i} has __dict__: {list(value.__dict__.keys())}")
                if actual_state is None:
                    # If no TrainingState found, try to use the first value
                    try:
                        first_value = next(iter(state_values))
                        if first_value is not None:
                            actual_state = first_value
                            print(f"Debug: Using first value as actual_state")
                    except StopIteration:
                        print(f"Debug: No values found in state_values")
            else:
                actual_state = state_values
        elif hasattr(final_state, '__getitem__'):
            print(f"Debug: final_state is dict-like")
            actual_state = final_state
        else:
            print(f"Debug: final_state is direct state object")
            actual_state = final_state
        
        print(f"Debug: actual_state type: {type(actual_state)}")
        if hasattr(actual_state, '__dict__'):
            print(f"Debug: actual_state attributes: {list(actual_state.__dict__.keys())}")
        
        # Safe access to state values
        def safe_get_attr(obj, attr, default=None):
            if hasattr(obj, attr):
                return getattr(obj, attr, default)
            elif hasattr(obj, 'get') and callable(obj.get):
                return obj.get(attr, default)
            else:
                return default
        
        def safe_get_pipeline_value(obj):
            pipeline = safe_get_attr(obj, 'selected_pipeline')
            if pipeline:
                return pipeline
            return None
        
        # Extract results from the actual state
        result = {
            "final_state": final_state,
            "messages": safe_get_attr(actual_state, 'messages', []),
            "training_results": safe_get_attr(actual_state, 'training_results'),
            "feature_importance": safe_get_attr(actual_state, 'feature_importance'),
            "model_type": safe_get_pipeline_value(actual_state)
        }
        
        print(f"Debug: Returning from run_training_session:")
        print(f"Debug: - training_results: {result['training_results']}")
        print(f"Debug: - model_type: {result['model_type']}")
        print(f"Debug: - messages count: {len(result['messages'])}")
        
        # Additional debugging for messages
        if result['messages']:
            print(f"Debug: First few messages:")
            for i, msg in enumerate(result['messages'][:3]):
                print(f"  Message {i}: {msg.get('type', 'unknown')} - {msg.get('content', '')[:100]}...")
        else:
            print(f"Debug: No messages found in result")
            # Try to get messages directly from actual_state
            if actual_state and hasattr(actual_state, 'messages'):
                print(f"Debug: actual_state.messages: {actual_state.messages}")
        
        return result
    
    def ask_question(self, 
                    question: str, 
                    session_id: str = "default") -> str:
        """Ask a question about the training results"""
        
        # Get current state
        current_state = self.graph.get_state(config={"configurable": {"thread_id": session_id}})
        
        if current_state is None:
            return "No training session found. Please run a training session first."
        
        # Get the training results from the session
        training_results = None
        if hasattr(current_state, 'values'):
            state = current_state.values
        else:
            state = current_state
            
        # Extract training results
        if hasattr(state, 'training_results'):
            training_results = state.training_results
        elif hasattr(state, 'get') and callable(state.get):
            training_results = state.get("training_results")
        
        # Debug: Print state information
        print(f"Debug: State type: {type(state)}")
        print(f"Debug: State attributes: {[attr for attr in dir(state) if not attr.startswith('_')]}")
        if hasattr(state, '__dict__'):
            print(f"Debug: State __dict__: {state.__dict__}")
        
        # If no training results, try to get from session data
        if not training_results:
            print(f"Debug: No training_results found in state")
            # Try to get from the session data
            session_results = self._session_data.get("results")
            if session_results is not None:
                print(f"Debug: Found training results in session data")
                training_results = session_results
            else:
                # Check if we have any DataFrame data
                for key, value in self._session_data.items():
                    if isinstance(value, pd.DataFrame):
                        print(f"Debug: Found session data with shape: {value.shape}")
                        return f"Training session found but no results stored. Session data has {value.shape[0]} rows and {value.shape[1]} columns."
                return "No training session found. Please run a training session first."
        
        # Create a simple Q&A response using the training results
        qa_prompt = ChatPromptTemplate.from_template("""
        You are an ML expert answering business user questions about their trained model.
        
        Training Results: {training_results}
        
        User Question: {user_question}
        
        Provide a clear, helpful answer that:
        1. Directly addresses their question
        2. Uses the specific training results provided
        3. Explains concepts in business terms
        4. Provides actionable insights when relevant
        5. Suggests follow-up actions if appropriate
        
        Be conversational and helpful, like a trusted ML consultant.
        """)
        
        chain = qa_prompt | self.llm | StrOutputParser()
        
        try:
            answer = chain.invoke({
                "training_results": safe_json_serialize(training_results),
                "user_question": question
            })
            
            return f"""
            💡 **Answer to Your Question**
            
            {answer}
            
            **Any other questions?** I'm here to help you understand your model and how to use it effectively!
            """
            
        except Exception as e:
            return f"I encountered an error while processing your question: {str(e)}"


# Example usage and testing
def demo_training_agent():
    """Demonstrate the training agent with sample data"""
    
    # Create sample data
    np.random.seed(42)
    n_samples = 1000
    
    data = pd.DataFrame({
        'age': np.random.randint(18, 80, n_samples),
        'income': np.random.normal(50000, 20000, n_samples),
        'education_level': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n_samples),
        'years_experience': np.random.randint(0, 40, n_samples),
        'department': np.random.choice(['Sales', 'Engineering', 'Marketing', 'HR'], n_samples),
        'performance_score': np.random.uniform(1, 5, n_samples),
        'will_leave': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])  # Target variable
    })
    
    # Initialize agent
    agent = MLTrainingAgent()
    
    # Run training session
    business_goal = """
    We want to predict which employees are likely to leave the company in the next 6 months.
    This will help HR proactively engage with at-risk employees and improve retention.
    The most important thing is to identify the key factors that drive employee turnover.
    """
    
    data_description = """
    Employee dataset with demographics, job information, and performance metrics.
    The 'will_leave' column indicates if an employee left within 6 months (1) or stayed (0).
    """
    
    training_context = """
    This is for HR analytics. We need interpretable results that HR managers can understand
    and act upon. Model accuracy is important, but understanding WHY people leave is more critical.
    """
    
    print("🚀 Starting ML Training Agent Demo...")
    print("=" * 50)
    
    # Run the training session
    try:
        results = agent.run_training_session(
            business_goal=business_goal,
            data=data,
            data_description=data_description,
            training_context=training_context,
            session_id="demo_session"
        )
    except Exception as e:
        print(f"❌ Training session failed: {e}")
        import traceback
        traceback.print_exc()
        # Return a safe fallback result
        results = {
            "final_state": None,
            "messages": [],
            "training_results": {"error": str(e), "status": "failed"},
            "feature_importance": {},
            "model_type": "Error"
        }
    
    # Print conversation flow
    print("\n📝 Conversation Flow:")
    print("=" * 30)
    messages = results.get("messages", [])
    if not messages:
        print("No messages available (workflow may have failed)")
    else:
        for i, message in enumerate(messages):
            try:
                if message.get('type') == 'AIMessage':
                    print(f"\n🤖 Agent Step {i//2 + 1}:")
                    print(message['content'])
                elif message.get('type') == 'HumanMessage':
                    print(f"\n👤 User:")
                    print(message['content'])
            except Exception as e:
                print(f"\n⚠️ Error displaying message {i}: {e}")
                print(f"Message: {message}")
    
    # Demo Q&A
    print(f"\n❓ Demo Q&A Session:")
    print("=" * 25)
    
    questions = [
        "What are the top 3 factors that predict employee turnover?",
        "How confident should we be in these predictions?", 
        "What actionable steps can HR take based on these insights?"
    ]
    
    for question in questions:
        print(f"\n👤 Question: {question}")
        try:
            answer = agent.ask_question(question, session_id="demo_session")
            print(f"🤖 Answer: {answer}")
        except Exception as e:
            print(f"🤖 Error answering question: {e}")
            print(f"🤖 Answer: Unable to answer due to error in training session")
    
    return results


if __name__ == "__main__":
    # Run the demo
    import os
    os.environ["OPENAI_API_KEY"] = "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"
    demo_results = demo_training_agent()
    
    print(f"\n✅ Training Agent Demo Complete!")
    final_state = demo_results['final_state']
    
    # Handle case where final_state is None (workflow failed)
    if final_state is None:
        print("Final State: workflow_failed")
        print(f"Model Type: {demo_results.get('model_type', 'unknown')}")
    else:
        if hasattr(final_state, 'values'):
            current_step = getattr(final_state.values, 'current_step', 'unknown')
        else:
            current_step = final_state.get('current_step', 'unknown') if hasattr(final_state, 'get') else 'unknown'
        print(f"Final State: {current_step}")
        print(f"Model Type: {demo_results.get('model_type', 'unknown')}")