import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Literal, Annotated, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import warnings
from datetime import datetime
import re
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

# LangChain imports
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI

# LangGraph imports  
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

warnings.filterwarnings('ignore')


class ModelType(Enum):
    """Types of available models"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    FORECASTING = "forecasting"
    CAUSAL_INFERENCE = "causal_inference"


class ConfidenceLevel(Enum):
    """Confidence levels for predictions"""
    HIGH = "high"      # >90% feature alignment, strong model match
    MEDIUM = "medium"  # 70-90% alignment, good model match
    LOW = "low"        # 50-70% alignment, fair model match
    VERY_LOW = "very_low"  # <50% alignment, poor model match


@dataclass
class AvailableModel:
    """Description of an available trained model"""
    model_id: str
    model_name: str
    model_type: ModelType
    description: str
    business_purpose: str
    training_features: List[str]
    target_variable: str
    performance_metrics: Dict[str, float]
    training_data_description: str
    training_data_summary: Dict[str, Any]
    model_artifacts_path: str
    feature_engineering_steps: List[str]
    preprocessing_pipeline: Dict[str, Any]
    domain: str
    last_trained: datetime
    

@dataclass
class FeatureAlignment:
    """Feature alignment analysis between new data and model requirements"""
    available_features: List[str]
    missing_features: List[str]
    mappable_features: Dict[str, str]  # new_col -> training_col
    creatable_features: List[str]
    alignment_score: float
    transfer_learning_strategy: str


@dataclass
class PredictionResult:
    """Results of the prediction process"""
    predictions: np.ndarray
    prediction_probabilities: Optional[np.ndarray]
    confidence_scores: np.ndarray
    feature_importance: Dict[str, float]
    prediction_explanation: str
    business_insights: List[str]
    data_quality_warnings: List[str]
    model_used: str
    features_created: List[str]


@dataclass
class ReasoningStep:
    """Individual reasoning step with justification"""
    step_name: str
    decision: str
    reasoning: str
    evidence: List[str]
    confidence: float
    alternatives_considered: List[str]
    risks_identified: List[str]


@dataclass
class ReasoningChain:
    """Complete reasoning chain for decision transparency"""
    overall_objective: str
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    final_conclusion: str = ""
    confidence_assessment: str = ""
    key_assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


@dataclass
class PredictionState:
    """State for the prediction agent workflow"""
    # Inputs
    prediction_question: str = ""
    new_data: Optional[pd.DataFrame] = None
    available_models: List[AvailableModel] = field(default_factory=list)
    
    # Analysis
    question_analysis: Dict[str, Any] = field(default_factory=dict)
    model_matches: List[Dict[str, Any]] = field(default_factory=list)
    selected_model: Optional[AvailableModel] = None
    feature_alignment: Optional[FeatureAlignment] = None
    
    # Processing
    processed_data: Optional[pd.DataFrame] = None
    created_features: List[str] = field(default_factory=list)
    
    # Results
    predictions: Optional[PredictionResult] = None
    
    # Reasoning
    reasoning_chain: ReasoningChain = field(default_factory=lambda: ReasoningChain(""))
    
    # Workflow state
    messages: Annotated[List[BaseMessage], add_messages] = field(default_factory=list)
    current_step: str = "start"
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM


class TransferLearningEngine:
    """Engine for applying transfer learning concepts to feature alignment"""
    
    @staticmethod
    def calculate_semantic_similarity(text1: str, text2: str) -> float:
        """Calculate semantic similarity between two text descriptions"""
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity
        except:
            return 0.0
    
    @staticmethod
    def find_column_mappings(new_columns: List[str], 
                           training_columns: List[str]) -> Dict[str, str]:
        """Find potential mappings between new data columns and training columns"""
        
        mappings = {}
        
        for new_col in new_columns:
            best_match = None
            best_score = 0.0
            
            for train_col in training_columns:
                # Exact match
                if new_col.lower() == train_col.lower():
                    mappings[new_col] = train_col
                    break
                
                # Partial match
                score = 0.0
                
                # Check for common substrings
                new_tokens = set(re.split(r'[_\-\s]+', new_col.lower()))
                train_tokens = set(re.split(r'[_\-\s]+', train_col.lower()))
                
                intersection = new_tokens.intersection(train_tokens)
                if intersection:
                    score = len(intersection) / max(len(new_tokens), len(train_tokens))
                
                # Boost score for common business terms
                business_terms = {'customer', 'revenue', 'sales', 'cost', 'price', 'value', 'amount', 'count', 'rate', 'score'}
                if intersection.intersection(business_terms):
                    score += 0.2
                
                if score > best_score and score > 0.3:  # Minimum threshold
                    best_score = score
                    best_match = train_col
            
            if best_match:
                mappings[new_col] = best_match
        
        return mappings
    
    @staticmethod
    def suggest_feature_creation(missing_features: List[str], 
                               available_columns: List[str],
                               domain_knowledge: str) -> List[Dict[str, Any]]:
        """Suggest how to create missing features from available columns"""
        
        suggestions = []
        
        for missing_feature in missing_features:
            # Analyze feature name for creation hints
            feature_lower = missing_feature.lower()
            
            # Ratio features
            if any(keyword in feature_lower for keyword in ['ratio', 'per', 'rate', 'percentage']):
                suggestions.append({
                    "missing_feature": missing_feature,
                    "creation_strategy": "ratio",
                    "suggested_columns": [col for col in available_columns if any(term in col.lower() for term in ['total', 'count', 'amount'])],
                    "creation_steps": f"Create {missing_feature} by dividing related numerical columns",
                    "confidence": 0.7
                })
            
            # Aggregation features
            elif any(keyword in feature_lower for keyword in ['avg', 'mean', 'sum', 'total', 'count']):
                suggestions.append({
                    "missing_feature": missing_feature,
                    "creation_strategy": "aggregation",
                    "suggested_columns": [col for col in available_columns if 'id' in col.lower() or 'group' in col.lower()],
                    "creation_steps": f"Create {missing_feature} by aggregating data by relevant grouping variables",
                    "confidence": 0.6
                })
            
            # Temporal features
            elif any(keyword in feature_lower for keyword in ['days', 'months', 'years', 'since', 'age', 'tenure']):
                date_columns = [col for col in available_columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_columns:
                    suggestions.append({
                        "missing_feature": missing_feature,
                        "creation_strategy": "temporal",
                        "suggested_columns": date_columns,
                        "creation_steps": f"Create {missing_feature} by calculating time differences from date columns",
                        "confidence": 0.8
                    })
            
            # Transformation features
            elif any(keyword in feature_lower for keyword in ['log', 'sqrt', 'square', 'scaled', 'normalized']):
                numerical_cols = [col for col in available_columns if col.lower() in missing_feature.lower()]
                if numerical_cols:
                    suggestions.append({
                        "missing_feature": missing_feature,
                        "creation_strategy": "transformation",
                        "suggested_columns": numerical_cols,
                        "creation_steps": f"Apply mathematical transformation to create {missing_feature}",
                        "confidence": 0.9
                    })
        
        return suggestions


class ReasoningEngine:
    """Advanced reasoning engine for transparent decision-making"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
    
    def analyze_prediction_intent(self, question: str, data_info: Dict[str, Any]) -> ReasoningStep:
        """Reason about the prediction intent and requirements"""
        
        reasoning_prompt = ChatPromptTemplate.from_template("""
        You are reasoning about a prediction request to make transparent decisions.
        
        **Question:** {question}
        **Data Info:** {data_info}
        
        Provide step-by-step reasoning:
        1. **Intent Analysis**: What is the user actually trying to achieve?
        2. **Problem Classification**: What type of ML problem is this and why?
        3. **Business Context**: What business decision depends on this prediction?
        4. **Success Criteria**: How should we measure if this prediction is valuable?
        5. **Constraints**: What limitations or requirements should we consider?
        
        For each reasoning point, provide:
        - Your conclusion
        - Evidence supporting this conclusion
        - Alternative interpretations you considered
        - Confidence in your reasoning
        
        Respond in JSON format:
        {{
            "step_name": "prediction_intent_analysis",
            "decision": "main conclusion about prediction intent",
            "reasoning": "detailed explanation of reasoning process",
            "evidence": ["evidence1", "evidence2", "evidence3"],
            "confidence": 0.85,
            "alternatives_considered": ["alternative1", "alternative2"],
            "risks_identified": ["risk1", "risk2"],
            "key_insights": ["insight1", "insight2"]
        }}
        """)
        
        chain = reasoning_prompt | self.llm | JsonOutputParser()
        
        result = chain.invoke({
            "question": question,
            "data_info": json.dumps(data_info, indent=2)
        })
        
        return ReasoningStep(
            step_name=result["step_name"],
            decision=result["decision"],
            reasoning=result["reasoning"],
            evidence=result["evidence"],
            confidence=result["confidence"],
            alternatives_considered=result["alternatives_considered"],
            risks_identified=result["risks_identified"]
        )
    
    def reason_model_selection(self, 
                              question_analysis: Dict[str, Any],
                              available_models: List[AvailableModel],
                              model_evaluations: List[Dict[str, Any]]) -> ReasoningStep:
        """Reason about model selection decision"""
        
        reasoning_prompt = ChatPromptTemplate.from_template("""
        You are reasoning about which model to select for a prediction task.
        
        **Question Analysis:** {question_analysis}
        **Available Models:** {available_models}
        **Model Evaluations:** {model_evaluations}
        
        Provide detailed reasoning for model selection:
        1. **Selection Criteria**: What factors are most important for this decision?
        2. **Trade-off Analysis**: How do you weigh accuracy vs interpretability vs speed?
        3. **Risk Assessment**: What are the risks of choosing each model?
        4. **Business Alignment**: Which model best serves the business objective?
        5. **Fallback Strategy**: What if the chosen model doesn't work well?
        
        Explain your reasoning process transparently:
        
        Respond in JSON format:
        {{
            "step_name": "model_selection_reasoning",
            "decision": "selected model and why",
            "reasoning": "step-by-step thought process",
            "evidence": ["evidence supporting selection"],
            "confidence": 0.8,
            "alternatives_considered": ["why other models were not chosen"],
            "risks_identified": ["potential issues with selected model"],
            "selection_criteria_weights": {{
                "task_alignment": 0.3,
                "feature_compatibility": 0.25,
                "performance": 0.2,
                "domain_relevance": 0.15,
                "recency": 0.1
            }},
            "trade_off_analysis": "explanation of key trade-offs made"
        }}
        """)
        
        chain = reasoning_prompt | self.llm | JsonOutputParser()
        
        # Format models for reasoning
        models_summary = [
            {
                "id": m.model_id,
                "name": m.model_name,
                "type": m.model_type.value,
                "performance": m.performance_metrics,
                "domain": m.domain
            }
            for m in available_models
        ]
        
        result = chain.invoke({
            "question_analysis": json.dumps(question_analysis, indent=2),
            "available_models": json.dumps(models_summary, indent=2),
            "model_evaluations": json.dumps(model_evaluations, indent=2)
        })
        
        return ReasoningStep(
            step_name=result["step_name"],
            decision=result["decision"],
            reasoning=result["reasoning"],
            evidence=result["evidence"],
            confidence=result["confidence"],
            alternatives_considered=result["alternatives_considered"],
            risks_identified=result["risks_identified"]
        )
    
    def reason_feature_engineering(self,
                                  feature_alignment: FeatureAlignment,
                                  selected_model: AvailableModel,
                                  new_data_columns: List[str]) -> ReasoningStep:
        """Reason about feature engineering decisions"""
        
        reasoning_prompt = ChatPromptTemplate.from_template("""
        You are reasoning about feature engineering and transfer learning decisions.
        
        **Model Requirements:** {model_features}
        **Available Data:** {available_columns}
        **Feature Alignment:** {alignment_info}
        **Domain:** {domain}
        
        Reason through the feature engineering approach:
        1. **Gap Analysis**: What features are missing and why are they important?
        2. **Creation Strategy**: How can we create missing features from available data?
        3. **Quality Assessment**: How reliable will the created features be?
        4. **Transfer Learning**: What domain differences affect feature interpretation?
        5. **Risk Mitigation**: What could go wrong and how to handle it?
        
        Provide transparent reasoning:
        
        Respond in JSON format:
        {{
            "step_name": "feature_engineering_reasoning",
            "decision": "feature engineering strategy and approach",
            "reasoning": "detailed thought process for feature decisions",
            "evidence": ["evidence supporting feature choices"],
            "confidence": 0.75,
            "alternatives_considered": ["other approaches considered"],
            "risks_identified": ["potential feature engineering risks"],
            "feature_creation_confidence": {{
                "high_confidence": ["reliable features"],
                "medium_confidence": ["somewhat reliable features"],
                "low_confidence": ["uncertain features"]
            }},
            "transfer_learning_reasoning": "why this transfer approach makes sense"
        }}
        """)
        
        chain = reasoning_prompt | self.llm | JsonOutputParser()
        
        alignment_info = {
            "alignment_score": feature_alignment.alignment_score,
            "available_features": feature_alignment.available_features,
            "missing_features": feature_alignment.missing_features,
            "mappable_features": feature_alignment.mappable_features,
            "strategy": feature_alignment.transfer_learning_strategy
        }
        
        result = chain.invoke({
            "model_features": selected_model.training_features,
            "available_columns": new_data_columns,
            "alignment_info": json.dumps(alignment_info, indent=2),
            "domain": selected_model.domain
        })
        
        return ReasoningStep(
            step_name=result["step_name"],
            decision=result["decision"],
            reasoning=result["reasoning"],
            evidence=result["evidence"],
            confidence=result["confidence"],
            alternatives_considered=result["alternatives_considered"],
            risks_identified=result["risks_identified"]
        )
    
    def reason_prediction_confidence(self,
                                   prediction_results: PredictionResult,
                                   feature_alignment_score: float,
                                   transfer_strategy: str,
                                   model_performance: Dict[str, float]) -> ReasoningStep:
        """Reason about prediction confidence and reliability"""
        
        reasoning_prompt = ChatPromptTemplate.from_template("""
        You are reasoning about prediction confidence and reliability.
        
        **Model Performance:** {model_performance}
        **Feature Alignment:** {alignment_score}
        **Transfer Strategy:** {transfer_strategy}
        **Prediction Stats:** {prediction_stats}
        
        Reason through confidence assessment:
        1. **Model Reliability**: How reliable was the original model?
        2. **Data Compatibility**: How well does new data match training data?
        3. **Feature Quality**: How good are the features (original + created)?
        4. **Transfer Learning Impact**: How does domain transfer affect reliability?
        5. **Uncertainty Sources**: What are the main sources of uncertainty?
        
        Provide confidence reasoning:
        
        Respond in JSON format:
        {{
            "step_name": "confidence_reasoning",
            "decision": "overall confidence assessment and level",
            "reasoning": "detailed explanation of confidence factors",
            "evidence": ["factors supporting confidence level"],
            "confidence": 0.8,
            "alternatives_considered": ["other confidence levels considered"],
            "risks_identified": ["main uncertainty sources"],
            "confidence_breakdown": {{
                "model_quality": 0.9,
                "feature_quality": 0.7,
                "data_compatibility": 0.8,
                "domain_transfer": 0.6
            }},
            "reliability_indicators": ["strong points", "weak points"],
            "recommended_usage": "how these predictions should be used"
        }}
        """)
        
        chain = reasoning_prompt | self.llm | JsonOutputParser()
        
        prediction_stats = {
            "n_predictions": len(prediction_results.predictions),
            "avg_confidence": np.mean(prediction_results.confidence_scores),
            "confidence_range": [float(prediction_results.confidence_scores.min()), 
                               float(prediction_results.confidence_scores.max())],
            "features_used": len(prediction_results.feature_importance)
        }
        
        result = chain.invoke({
            "model_performance": json.dumps(model_performance, indent=2),
            "alignment_score": alignment_score,
            "transfer_strategy": transfer_strategy,
            "prediction_stats": json.dumps(prediction_stats, indent=2)
        })
        
        return ReasoningStep(
            step_name=result["step_name"],
            decision=result["decision"],
            reasoning=result["reasoning"],
            evidence=result["evidence"],
            confidence=result["confidence"],
            alternatives_considered=result["alternatives_considered"],
            risks_identified=result["risks_identified"]
        )
    
    def reason_business_implications(self,
                                   prediction_question: str,
                                   prediction_results: PredictionResult,
                                   business_context: Dict[str, Any]) -> ReasoningStep:
        """Reason about business implications and actionable insights"""
        
        reasoning_prompt = ChatPromptTemplate.from_template("""
        You are reasoning about the business implications of ML predictions.
        
        **Original Question:** {prediction_question}
        **Business Context:** {business_context}
        **Prediction Results:** {prediction_summary}
        **Feature Importance:** {feature_importance}
        
        Reason through business implications:
        1. **Business Impact**: What do these predictions mean for business decisions?
        2. **Actionable Insights**: What specific actions should be taken?
        3. **Priority Assessment**: Which predictions are most critical to act on?
        4. **Resource Implications**: What resources are needed to act on insights?
        5. **Success Measurement**: How should the business measure success?
        
        Provide business reasoning:
        
        Respond in JSON format:
        {{
            "step_name": "business_implications_reasoning",
            "decision": "key business decisions enabled by these predictions",
            "reasoning": "logic connecting predictions to business actions",
            "evidence": ["prediction patterns supporting business insights"],
            "confidence": 0.8,
            "alternatives_considered": ["other business interpretations"],
            "risks_identified": ["business risks of acting on predictions"],
            "actionable_insights": [
                {{
                    "insight": "specific insight",
                    "recommended_action": "what to do",
                    "priority": "high|medium|low",
                    "resources_needed": "what's required",
                    "success_metric": "how to measure success"
                }}
            ],
            "business_value_assessment": "high|medium|low"
        }}
        """)
        
        chain = reasoning_prompt | self.llm | JsonOutputParser()
        
        # Prepare prediction summary
        pred_summary = {
            "total_predictions": len(prediction_results.predictions),
            "prediction_distribution": self._get_prediction_distribution_for_reasoning(prediction_results.predictions),
            "avg_confidence": float(np.mean(prediction_results.confidence_scores)),
            "model_used": prediction_results.model_used
        }
        
        # Get top 5 most important features
        top_features = dict(sorted(
            prediction_results.feature_importance.items(),
            key=lambda x: x[1], 
            reverse=True
        )[:5])
        
        result = chain.invoke({
            "prediction_question": prediction_question,
            "business_context": json.dumps(business_context, indent=2),
            "prediction_summary": json.dumps(pred_summary, indent=2),
            "feature_importance": json.dumps(top_features, indent=2)
        })
        
        return ReasoningStep(
            step_name=result["step_name"],
            decision=result["decision"],
            reasoning=result["reasoning"],
            evidence=result["evidence"],
            confidence=result["confidence"],
            alternatives_considered=result["alternatives_considered"],
            risks_identified=result["risks_identified"]
        )
    
    def synthesize_reasoning_chain(self, reasoning_steps: List[ReasoningStep], objective: str) -> ReasoningChain:
        """Synthesize all reasoning steps into a coherent chain"""
        
        synthesis_prompt = ChatPromptTemplate.from_template("""
        You are synthesizing a complete reasoning chain for an ML prediction task.
        
        **Overall Objective:** {objective}
        **Reasoning Steps:** {reasoning_steps}
        
        Synthesize the reasoning into a coherent narrative:
        1. **Overall Logic**: How do all the reasoning steps connect?
        2. **Key Assumptions**: What assumptions underlie the entire approach?
        3. **Confidence Assessment**: What's the overall confidence and why?
        4. **Critical Dependencies**: What factors are most critical for success?
        5. **Limitations**: What are the boundaries of this reasoning?
        
        Provide a synthesis that someone could follow and validate:
        
        Respond in JSON format:
        {{
            "final_conclusion": "overall conclusion of the reasoning process",
            "confidence_assessment": "assessment of overall confidence with justification",
            "key_assumptions": ["assumption1", "assumption2", "assumption3"],
            "limitations": ["limitation1", "limitation2"],
            "critical_success_factors": ["factor1", "factor2"],
            "reasoning_quality": "high|medium|low",
            "validation_suggestions": ["how to validate this reasoning"]
        }}
        """)
        
        chain = synthesis_prompt | self.llm | JsonOutputParser()
        
        # Format reasoning steps
        steps_summary = []
        for step in reasoning_steps:
            steps_summary.append({
                "step": step.step_name,
                "decision": step.decision,
                "confidence": step.confidence,
                "key_evidence": step.evidence[:3]  # Top 3 pieces of evidence
            })
        
        result = chain.invoke({
            "objective": objective,
            "reasoning_steps": json.dumps(steps_summary, indent=2)
        })
        
        return ReasoningChain(
            overall_objective=objective,
            reasoning_steps=reasoning_steps,
            final_conclusion=result["final_conclusion"],
            confidence_assessment=result["confidence_assessment"],
            key_assumptions=result["key_assumptions"],
            limitations=result["limitations"]
        )
    
    def _get_prediction_distribution_for_reasoning(self, predictions: np.ndarray) -> Dict[str, Any]:
        """Get prediction distribution for reasoning purposes"""
        
        # Handle different types of predictions
        if len(np.unique(predictions)) <= 10:  # Likely classification or small discrete values
            unique, counts = np.unique(predictions, return_counts=True)
            return {"type": "categorical", "distribution": dict(zip(unique.tolist(), counts.tolist()))}
        else:  # Continuous values
            return {
                "type": "continuous",
                "range": [float(predictions.min()), float(predictions.max())],
                "mean": float(predictions.mean()),
                "std": float(predictions.std())
            }


class PredictionAgent:
    """Independent Prediction Agent with Transfer Learning capabilities"""
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """Initialize the prediction agent"""
        self.llm = ChatOpenAI(model=llm_model, temperature=0.1)
        self.transfer_engine = TransferLearningEngine()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the prediction workflow"""
        
        workflow = StateGraph(PredictionState)
        
        # Add workflow nodes
        workflow.add_node("analyze_prediction_question", self._analyze_prediction_question)
        workflow.add_node("select_best_model", self._select_best_model)
        workflow.add_node("analyze_feature_alignment", self._analyze_feature_alignment)
        workflow.add_node("create_missing_features", self._create_missing_features)
        workflow.add_node("apply_transfer_learning", self._apply_transfer_learning)
        workflow.add_node("execute_prediction", self._execute_prediction)
        workflow.add_node("interpret_results", self._interpret_results)
        
        # Define workflow
        workflow.add_edge(START, "analyze_prediction_question")
        workflow.add_edge("analyze_prediction_question", "select_best_model")
        workflow.add_edge("select_best_model", "analyze_feature_alignment")
        workflow.add_edge("analyze_feature_alignment", "create_missing_features")
        workflow.add_edge("create_missing_features", "apply_transfer_learning")
        workflow.add_edge("apply_transfer_learning", "execute_prediction")
        workflow.add_edge("execute_prediction", "interpret_results")
        workflow.add_edge("interpret_results", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    def _analyze_prediction_question(self, state: PredictionState) -> PredictionState:
        """Step 1: Analyze the prediction question to understand requirements"""
        
        analysis_prompt = ChatPromptTemplate.from_template("""
        You are analyzing a prediction request to understand the requirements.
        
        **Prediction Question:** {prediction_question}
        
        **Available Data Columns:** {data_columns}
        **Data Shape:** {data_shape}
        
        Analyze the prediction question and determine:
        1. **Prediction Type**: What type of ML prediction is needed (classification, regression, forecasting, clustering, causal)?
        2. **Target Outcome**: What specific outcome are we trying to predict?
        3. **Business Context**: What business decision will this prediction support?
        4. **Data Requirements**: What type of data/features would be most relevant?
        5. **Success Criteria**: How should prediction quality be measured?
        6. **Urgency Level**: Is this ad-hoc analysis or production prediction?
        7. **Interpretation Needs**: How much explanation/interpretability is needed?
        
        Respond in JSON format:
        {{
            "prediction_type": "classification|regression|forecasting|clustering|causal_inference",
            "target_outcome": "specific outcome to predict",
            "business_context": "business decision this supports",
            "data_requirements": ["requirement1", "requirement2"],
            "success_criteria": "how to measure success",
            "urgency_level": "low|medium|high",
            "interpretation_needs": "low|medium|high",
            "keywords": ["keyword1", "keyword2"],
            "domain_hints": ["domain_indicator1", "domain_indicator2"]
        }}
        """)
        
        chain = analysis_prompt | self.llm | JsonOutputParser()
        
        question_analysis = chain.invoke({
            "prediction_question": state.prediction_question,
            "data_columns": list(state.new_data.columns) if state.new_data is not None else [],
            "data_shape": state.new_data.shape if state.new_data is not None else "Unknown"
        })
        
        state.question_analysis = question_analysis
        state.current_step = "question_analyzed"
        
        return state
    
    def _select_best_model(self, state: PredictionState) -> PredictionState:
        """Step 2: Select the best model from available options"""
        
        if not state.available_models or not state.question_analysis:
            return state
        
        model_selection_prompt = ChatPromptTemplate.from_template("""
        You are selecting the best model for a prediction task.
        
        **Prediction Requirements:**
        Question: {prediction_question}
        Prediction Type: {prediction_type}
        Target Outcome: {target_outcome}
        Business Context: {business_context}
        Keywords: {keywords}
        
        **Available Models:**
        {available_models}
        
        **New Data Info:**
        Columns: {new_data_columns}
        Shape: {data_shape}
        
        Evaluate each model and select the best one based on:
        1. **Task Alignment**: How well does the model's purpose match the prediction question?
        2. **Feature Compatibility**: How many required features are available in new data?
        3. **Domain Relevance**: Is the model trained on similar business context/domain?
        4. **Performance Quality**: How reliable are the model's historical performance metrics?
        5. **Recency**: How recently was the model trained (fresher is better)?
        
        Respond in JSON format:
        {{
            "model_evaluations": [
                {{
                    "model_id": "model_id",
                    "task_alignment_score": 0.9,
                    "feature_compatibility_score": 0.8,
                    "domain_relevance_score": 0.7,
                    "performance_score": 0.85,
                    "recency_score": 0.9,
                    "overall_score": 0.84,
                    "reasoning": "why this model is good/bad for the task"
                }}
            ],
            "selected_model_id": "best_model_id",
            "selection_reasoning": "why this model was chosen",
            "confidence_in_selection": 0.9,
            "potential_limitations": ["limitation1", "limitation2"],
            "transfer_learning_needed": true
        }}
        """)
        
        # Format available models for analysis
        models_info = []
        for model in state.available_models:
            models_info.append({
                "model_id": model.model_id,
                "name": model.model_name,
                "type": model.model_type.value,
                "description": model.description,
                "business_purpose": model.business_purpose,
                "features": model.training_features,
                "target": model.target_variable,
                "performance": model.performance_metrics,
                "domain": model.domain,
                "last_trained": model.last_trained.strftime("%Y-%m-%d")
            })
        
        chain = model_selection_prompt | self.llm | JsonOutputParser()
        
        selection_result = chain.invoke({
            "prediction_question": state.prediction_question,
            "prediction_type": state.question_analysis.get("prediction_type", "unknown"),
            "target_outcome": state.question_analysis.get("target_outcome", "unknown"),
            "business_context": state.question_analysis.get("business_context", "unknown"),
            "keywords": state.question_analysis.get("keywords", []),
            "available_models": json.dumps(models_info, indent=2),
            "new_data_columns": list(state.new_data.columns) if state.new_data is not None else [],
            "data_shape": state.new_data.shape if state.new_data is not None else "Unknown"
        })
        
        # Find and set the selected model
        selected_model_id = selection_result.get("selected_model_id")
        state.selected_model = next(
            (model for model in state.available_models if model.model_id == selected_model_id),
            None
        )
        
        state.model_matches = selection_result.get("model_evaluations", [])
        state.current_step = "model_selected"
        
        return state
    
    def _analyze_feature_alignment(self, state: PredictionState) -> PredictionState:
        """Step 3: Analyze feature alignment between new data and selected model"""
        
        if not state.selected_model or state.new_data is None:
            return state
        
        new_columns = list(state.new_data.columns)
        training_features = state.selected_model.training_features
        
        # Find column mappings using transfer learning
        column_mappings = self.transfer_engine.find_column_mappings(new_columns, training_features)
        
        # Identify available, missing, and creatable features
        available_features = list(column_mappings.keys())
        missing_features = [f for f in training_features if f not in column_mappings.values()]
        
        # Suggest feature creation for missing features
        creation_suggestions = self.transfer_engine.suggest_feature_creation(
            missing_features, 
            new_columns,
            state.selected_model.domain
        )
        
        creatable_features = [s["missing_feature"] for s in creation_suggestions if s["confidence"] > 0.5]
        
        # Calculate alignment score
        total_required = len(training_features)
        available_count = len(available_features)
        creatable_count = len(creatable_features)
        alignment_score = (available_count + creatable_count * 0.7) / total_required
        
        # Determine transfer learning strategy
        if alignment_score > 0.8:
            strategy = "direct_application"
        elif alignment_score > 0.6:
            strategy = "feature_adaptation"
        elif alignment_score > 0.4:
            strategy = "extensive_feature_engineering"
        else:
            strategy = "domain_adaptation_required"
        
        state.feature_alignment = FeatureAlignment(
            available_features=available_features,
            missing_features=missing_features,
            mappable_features=column_mappings,
            creatable_features=creatable_features,
            alignment_score=alignment_score,
            transfer_learning_strategy=strategy
        )
        
        # Set confidence level based on alignment
        if alignment_score > 0.9:
            state.confidence_level = ConfidenceLevel.HIGH
        elif alignment_score > 0.7:
            state.confidence_level = ConfidenceLevel.MEDIUM
        elif alignment_score > 0.5:
            state.confidence_level = ConfidenceLevel.LOW
        else:
            state.confidence_level = ConfidenceLevel.VERY_LOW
        
        state.current_step = "features_aligned"
        
        return state
    
    def _create_missing_features(self, state: PredictionState) -> PredictionState:
        """Step 4: Create missing features using transfer learning techniques"""
        
        if not state.feature_alignment or state.new_data is None:
            return state
        
        feature_creation_prompt = ChatPromptTemplate.from_template("""
        You are creating missing features for a prediction task using transfer learning.
        
        **Selected Model:** {model_name}
        **Model Features:** {required_features}
        **Available Columns:** {available_columns}
        **Missing Features:** {missing_features}
        **Feature Mappings:** {column_mappings}
        
        **Transfer Learning Strategy:** {strategy}
        **Domain:** {domain}
        
        For each missing feature, provide specific creation instructions using available columns:
        
        Respond in JSON format:
        {{
            "feature_creation_plan": [
                {{
                    "target_feature": "missing_feature_name",
                    "creation_method": "mathematical_operation|aggregation|transformation|proxy_feature",
                    "source_columns": ["col1", "col2"],
                    "creation_formula": "specific formula or transformation",
                    "python_code": "pandas code to create the feature",
                    "business_justification": "why this approximation makes sense",
                    "confidence_level": 0.8,
                    "fallback_strategy": "what to do if creation fails"
                }}
            ],
            "data_preprocessing_steps": ["step1", "step2"],
            "quality_checks": ["check1", "check2"],
            "approximation_warnings": ["warning1", "warning2"]
        }}
        """)
        
        chain = feature_creation_prompt | self.llm | JsonOutputParser()
        
        creation_plan = chain.invoke({
            "model_name": state.selected_model.model_name,
            "required_features": state.selected_model.training_features,
            "available_columns": list(state.new_data.columns),
            "missing_features": state.feature_alignment.missing_features,
            "column_mappings": state.feature_alignment.mappable_features,
            "strategy": state.feature_alignment.transfer_learning_strategy,
            "domain": state.selected_model.domain
        })
        
        # Execute feature creation
        processed_data = state.new_data.copy()
        created_features = []
        
        for feature_plan in creation_plan.get("feature_creation_plan", []):
            try:
                target_feature = feature_plan["target_feature"]
                python_code = feature_plan["python_code"]
                
                # Simple feature creation execution (in practice, you'd want more robust execution)
                if feature_plan["creation_method"] == "mathematical_operation":
                    # Example: processed_data['new_feature'] = processed_data['col1'] / processed_data['col2']
                    exec(f"processed_data['{target_feature}'] = {python_code}")
                    created_features.append(target_feature)
                
                elif feature_plan["creation_method"] == "transformation":
                    # Example: np.log, np.sqrt, etc.
                    exec(f"processed_data['{target_feature}'] = {python_code}")
                    created_features.append(target_feature)
                
                # Add more creation methods as needed
                
            except Exception as e:
                # Log failed feature creation
                print(f"Failed to create feature {feature_plan['target_feature']}: {str(e)}")
        
        state.processed_data = processed_data
        state.created_features = created_features
        state.current_step = "features_created"
        
        return state
    
    def _apply_transfer_learning(self, state: PredictionState) -> PredictionState:
        """Step 5: Apply transfer learning adjustments"""
        
        if not state.processed_data or not state.selected_model:
            return state
        
        transfer_prompt = ChatPromptTemplate.from_template("""
        You are applying transfer learning to adapt a trained model to new data.
        
        **Model Context:**
        Model: {model_name}
        Original Domain: {original_domain}
        Training Data Summary: {training_summary}
        
        **New Data Context:**
        New Data Shape: {new_data_shape}
        Available Features: {available_features}
        Created Features: {created_features}
        Feature Alignment Score: {alignment_score}
        
        **Transfer Learning Strategy:** {strategy}
        
        Recommend transfer learning adjustments:
        1. **Feature Scaling**: Should features be rescaled based on new data distribution?
        2. **Feature Weights**: Should certain features be weighted differently?
        3. **Threshold Adjustments**: Should prediction thresholds be adjusted?
        4. **Uncertainty Adjustments**: How should prediction confidence be calibrated?
        5. **Domain Adaptation**: What domain differences should be considered?
        
        Respond in JSON format:
        {{
            "scaling_adjustments": {{
                "method": "standardize|normalize|robust|none",
                "features_to_scale": ["feature1", "feature2"],
                "reasoning": "why scaling is needed"
            }},
            "feature_weight_adjustments": {{
                "features_to_boost": ["feature1"],
                "features_to_reduce": ["feature2"],
                "reasoning": "why weights should change"
            }},
            "threshold_adjustments": {{
                "recommended_threshold": 0.5,
                "reasoning": "why this threshold is appropriate"
            }},
            "confidence_calibration": {{
                "calibration_factor": 0.9,
                "reasoning": "how to adjust confidence"
            }},
            "domain_adaptation_notes": ["note1", "note2"],
            "prediction_reliability": "high|medium|low"
        }}
        """)
        
        chain = transfer_prompt | self.llm | JsonOutputParser()
        
        transfer_adjustments = chain.invoke({
            "model_name": state.selected_model.model_name,
            "original_domain": state.selected_model.domain,
            "training_summary": json.dumps(state.selected_model.training_data_summary, indent=2),
            "new_data_shape": state.processed_data.shape,
            "available_features": state.feature_alignment.available_features,
            "created_features": state.created_features,
            "alignment_score": state.feature_alignment.alignment_score,
            "strategy": state.feature_alignment.transfer_learning_strategy
        })
        
        # Apply transfer learning adjustments to data
        if transfer_adjustments.get("scaling_adjustments", {}).get("method") != "none":
            scaling_method = transfer_adjustments["scaling_adjustments"]["method"]
            features_to_scale = transfer_adjustments["scaling_adjustments"]["features_to_scale"]
            
            # Apply scaling (simplified - in practice use sklearn scalers)
            for feature in features_to_scale:
                if feature in state.processed_data.columns:
                    if scaling_method == "standardize":
                        mean_val = state.processed_data[feature].mean()
                        std_val = state.processed_data[feature].std()
                        state.processed_data[feature] = (state.processed_data[feature] - mean_val) / std_val
        
        # Store transfer learning configuration
        state.question_analysis.update({"transfer_learning_config": transfer_adjustments})
        state.current_step = "transfer_learning_applied"
        
        return state
    
    def _execute_prediction(self, state: PredictionState) -> PredictionState:
        """Step 6: Execute the actual prediction"""
        
        if not state.processed_data or not state.selected_model:
            return state
        
        # This is a simplified prediction execution
        # In practice, you would load the actual trained model and apply it
        
        # Simulate prediction based on model type
        n_rows = len(state.processed_data)
        
        if state.selected_model.model_type == ModelType.CLASSIFICATION:
            # Simulate binary classification
            predictions = np.random.choice([0, 1], size=n_rows, p=[0.7, 0.3])
            probabilities = np.random.uniform(0.1, 0.9, size=(n_rows, 2))
            probabilities = probabilities / probabilities.sum(axis=1, keepdims=True)
            confidence_scores = np.max(probabilities, axis=1)
            
        elif state.selected_model.model_type == ModelType.REGRESSION:
            # Simulate regression predictions
            predictions = np.random.normal(100, 25, size=n_rows)
            probabilities = None
            confidence_scores = np.random.uniform(0.6, 0.95, size=n_rows)
            
        elif state.selected_model.model_type == ModelType.CLUSTERING:
            # Simulate cluster assignments
            n_clusters = 5
            predictions = np.random.choice(range(n_clusters), size=n_rows)
            probabilities = None
            confidence_scores = np.random.uniform(0.5, 0.9, size=n_rows)
            
        else:
            # Default prediction
            predictions = np.random.uniform(0, 1, size=n_rows)
            probabilities = None
            confidence_scores = np.random.uniform(0.4, 0.8, size=n_rows)
        
        # Simulate feature importance (based on training features)
        feature_importance = {}
        if state.selected_model.training_features:
            importance_values = np.random.dirichlet(np.ones(len(state.selected_model.training_features)))
            feature_importance = dict(zip(state.selected_model.training_features, importance_values))
        
        state.predictions = PredictionResult(
            predictions=predictions,
            prediction_probabilities=probabilities,
            confidence_scores=confidence_scores,
            feature_importance=feature_importance,
            prediction_explanation="",  # Will be filled in interpretation step
            business_insights=[],
            data_quality_warnings=[],
            model_used=state.selected_model.model_name,
            features_created=state.created_features
        )
        
        state.current_step = "prediction_executed"
        
        return state
    
    def _interpret_results(self, state: PredictionState) -> PredictionState:
        """Step 7: Interpret and explain prediction results"""
        
        if not state.predictions or not state.selected_model:
            return state
        
        interpretation_prompt = ChatPromptTemplate.from_template("""
        You are interpreting ML prediction results for business stakeholders.
        
        **Prediction Context:**
        Original Question: {prediction_question}
        Model Used: {model_name}
        Model Performance: {model_performance}
        Confidence Level: {confidence_level}
        
        **Prediction Results:**
        Number of Predictions: {n_predictions}
        Prediction Type: {prediction_type}
        Predictions Summary: {predictions_summary}
        Average Confidence: {avg_confidence}
        
        **Feature Analysis:**
        Top Important Features: {top_features}
        Features Created: {created_features}
        Feature Alignment Score: {alignment_score}
        
        **Transfer Learning Info:**
        Strategy Used: {transfer_strategy}
        Domain Adaptation: {domain_notes}
        
        Provide a comprehensive interpretation including:
        1. **Prediction Summary**: What the predictions show in business terms
        2. **Confidence Assessment**: How reliable these predictions are and why
        3. **Key Drivers**: Which factors most influence the predictions
        4. **Business Insights**: Actionable insights from the predictions
        5. **Limitations**: What these predictions cannot tell us
        6. **Recommendations**: How to use these predictions effectively
        7. **Next Steps**: What follow-up analysis or actions are recommended
        
        Use clear, business-friendly language and focus on actionable insights.
        """)
        
        chain = interpretation_prompt | self.llm | StrOutputParser()
        
        # Prepare prediction summary
        if state.selected_model.model_type == ModelType.CLASSIFICATION:
            pred_summary = f"Class distribution: {np.bincount(state.predictions.predictions.astype(int))}"
        elif state.selected_model.model_type == ModelType.REGRESSION:
            pred_summary = f"Range: {state.predictions.predictions.min():.2f} to {state.predictions.predictions.max():.2f}, Mean: {state.predictions.predictions.mean():.2f}"
        else:
            pred_summary = f"Predictions generated for {len(state.predictions.predictions)} records"
        
        # Get top features by importance
        top_features = dict(sorted(
            state.predictions.feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5])
        
        interpretation = chain.invoke({
            "prediction_question": state.prediction_question,
            "model_name": state.selected_model.model_name,
            "model_performance": json.dumps(state.selected_model.performance_metrics, indent=2),
            "confidence_level": state.confidence_level.value,
            "n_predictions": len(state.predictions.predictions),
            "prediction_type": state.selected_model.model_type.value,
            "predictions_summary": pred_summary,
            "avg_confidence": np.mean(state.predictions.confidence_scores),
            "top_features": json.dumps(top_features, indent=2),
            "created_features": state.created_features,
            "alignment_score": state.feature_alignment.alignment_score,
            "transfer_strategy": state.feature_alignment.transfer_learning_strategy,
            "domain_notes": state.question_analysis.get("transfer_learning_config", {}).get("domain_adaptation_notes", [])
        })
        
        state.predictions.prediction_explanation = interpretation
        state.messages.append(AIMessage(content=interpretation))
        state.current_step = "results_interpreted"
        
        return state
    
    def predict(self,
               new_data: pd.DataFrame,
               prediction_question: str,
               available_models: List[AvailableModel],
               session_id: str = "default") -> Dict[str, Any]:
        """
        Main prediction method
        
        Args:
            new_data: DataFrame to make predictions on
            prediction_question: What you want to predict
            available_models: List of available trained models
            session_id: Unique session identifier
            
        Returns:
            Comprehensive prediction results with explanations
        """
        
        # Initialize state
        initial_state = PredictionState(
            prediction_question=prediction_question,
            new_data=new_data,
            available_models=available_models
        )
        
        # Execute workflow
        final_state = self.graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )
        
        return self._format_prediction_output(final_state)
    
    def _format_prediction_output(self, state: PredictionState) -> Dict[str, Any]:
        """Format prediction results for consumption"""
        
        if not state.predictions or not state.selected_model:
            return {"error": "Prediction failed", "state": state.current_step}
        
        # Create predictions DataFrame
        predictions_df = state.new_data.copy()
        predictions_df['prediction'] = state.predictions.predictions
        predictions_df['confidence'] = state.predictions.confidence_scores
        
        if state.predictions.prediction_probabilities is not None:
            n_classes = state.predictions.prediction_probabilities.shape[1]
            for i in range(n_classes):
                predictions_df[f'probability_class_{i}'] = state.predictions.prediction_probabilities[:, i]
        
        return {
            # Core predictions
            "predictions": state.predictions.predictions.tolist(),
            "predictions_dataframe": predictions_df,
            "confidence_scores": state.predictions.confidence_scores.tolist(),
            "prediction_probabilities": state.predictions.prediction_probabilities.tolist() if state.predictions.prediction_probabilities is not None else None,
            
            # Model and feature info
            "model_used": {
                "model_id": state.selected_model.model_id,
                "model_name": state.selected_model.model_name,
                "model_type": state.selected_model.model_type.value,
                "domain": state.selected_model.domain,
                "performance_metrics": state.selected_model.performance_metrics
            },
            
            "feature_analysis": {
                "features_required": state.selected_model.training_features,
                "features_available": state.feature_alignment.available_features if state.feature_alignment else [],
                "features_created": state.created_features,
                "feature_alignment_score": state.feature_alignment.alignment_score if state.feature_alignment else 0.0,
                "feature_importance": state.predictions.feature_importance
            },
            
            # Transfer learning info
            "transfer_learning": {
                "strategy_used": state.feature_alignment.transfer_learning_strategy if state.feature_alignment else "none",
                "confidence_level": state.confidence_level.value,
                "domain_adaptation_applied": True if state.confidence_level != ConfidenceLevel.HIGH else False
            },
            
            # Business interpretation
            "business_interpretation": {
                "explanation": state.predictions.prediction_explanation,
                "key_insights": state.predictions.business_insights,
                "limitations": state.predictions.data_quality_warnings,
                "recommendations": self._generate_recommendations(state)
            },
            
            # Summary statistics
            "prediction_summary": {
                "total_predictions": len(state.predictions.predictions),
                "average_confidence": np.mean(state.predictions.confidence_scores),
                "confidence_distribution": self._get_confidence_distribution(state.predictions.confidence_scores),
                "prediction_distribution": self._get_prediction_distribution(state.predictions.predictions, state.selected_model.model_type)
            },
            
            # Quality indicators
            "quality_indicators": {
                "model_selection_confidence": self._get_model_selection_confidence(state),
                "feature_coverage": len(state.feature_alignment.available_features) / len(state.selected_model.training_features) if state.feature_alignment else 0.0,
                "data_quality_score": self._assess_new_data_quality(state.new_data),
                "overall_reliability": state.confidence_level.value
            }
        }
    
    def _generate_recommendations(self, state: PredictionState) -> List[str]:
        """Generate business recommendations based on predictions"""
        
        recommendations = []
        
        if state.confidence_level == ConfidenceLevel.HIGH:
            recommendations.append("Predictions are highly reliable - safe to use for business decisions")
        elif state.confidence_level == ConfidenceLevel.MEDIUM:
            recommendations.append("Predictions are moderately reliable - consider additional validation")
        else:
            recommendations.append("Predictions have lower reliability - use with caution and seek additional data")
        
        if state.created_features:
            recommendations.append(f"Created {len(state.created_features)} features to improve compatibility")
        
        if state.feature_alignment and state.feature_alignment.alignment_score < 0.7:
            recommendations.append("Consider collecting additional data to improve feature alignment")
        
        return recommendations
    
    def _get_confidence_distribution(self, confidence_scores: np.ndarray) -> Dict[str, int]:
        """Get distribution of confidence levels"""
        
        high_conf = np.sum(confidence_scores > 0.8)
        medium_conf = np.sum((confidence_scores > 0.6) & (confidence_scores <= 0.8))
        low_conf = np.sum(confidence_scores <= 0.6)
        
        return {
            "high_confidence": int(high_conf),
            "medium_confidence": int(medium_conf),
            "low_confidence": int(low_conf)
        }
    
    def _get_prediction_distribution(self, predictions: np.ndarray, model_type: ModelType) -> Dict[str, Any]:
        """Get distribution of predictions"""
        
        if model_type == ModelType.CLASSIFICATION:
            unique, counts = np.unique(predictions.astype(int), return_counts=True)
            return {"class_distribution": dict(zip(unique.tolist(), counts.tolist()))}
        
        elif model_type == ModelType.REGRESSION:
            return {
                "min": float(predictions.min()),
                "max": float(predictions.max()),
                "mean": float(predictions.mean()),
                "std": float(predictions.std())
            }
        
        else:
            return {"summary": f"{len(predictions)} predictions generated"}
    
    def _get_model_selection_confidence(self, state: PredictionState) -> float:
        """Get confidence in model selection"""
        
        if not state.model_matches:
            return 0.5
        
        # Find the selected model's score
        selected_id = state.selected_model.model_id if state.selected_model else None
        for match in state.model_matches:
            if match.get("model_id") == selected_id:
                return match.get("overall_score", 0.5)
        
        return 0.5
    
    def _assess_new_data_quality(self, data: pd.DataFrame) -> float:
        """Assess quality of new data"""
        
        if data is None:
            return 0.0
        
        # Simple data quality assessment
        missing_pct = data.isnull().sum().sum() / (len(data) * len(data.columns))
        quality_score = 1.0 - missing_pct
        
        return max(0.0, min(1.0, quality_score))


# Tool interface for integration
class PredictionTool:
    """Tool wrapper for the Prediction Agent"""
    
    def __init__(self, agent: PredictionAgent = None):
        self.agent = agent or PredictionAgent()
    
    def predict_with_best_model(self,
                               new_data: pd.DataFrame,
                               prediction_question: str,
                               available_models: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Tool function for making predictions with the best available model
        
        Args:
            new_data: Data to predict on
            prediction_question: What to predict
            available_models: List of model dictionaries
            
        Returns:
            Simplified prediction results
        """
        
        # Convert dict models to AvailableModel objects
        model_objects = []
        for model_dict in available_models:
            try:
                model_obj = AvailableModel(
                    model_id=model_dict.get("model_id", "unknown"),
                    model_name=model_dict.get("model_name", "Unknown Model"),
                    model_type=ModelType(model_dict.get("model_type", "classification")),
                    description=model_dict.get("description", ""),
                    business_purpose=model_dict.get("business_purpose", ""),
                    training_features=model_dict.get("training_features", []),
                    target_variable=model_dict.get("target_variable", ""),
                    performance_metrics=model_dict.get("performance_metrics", {}),
                    training_data_description=model_dict.get("training_data_description", ""),
                    training_data_summary=model_dict.get("training_data_summary", {}),
                    model_artifacts_path=model_dict.get("model_artifacts_path", ""),
                    feature_engineering_steps=model_dict.get("feature_engineering_steps", []),
                    preprocessing_pipeline=model_dict.get("preprocessing_pipeline", {}),
                    domain=model_dict.get("domain", "general"),
                    last_trained=datetime.fromisoformat(model_dict.get("last_trained", "2024-01-01"))
                )
                model_objects.append(model_obj)
            except Exception as e:
                print(f"Error processing model {model_dict.get('model_id', 'unknown')}: {e}")
                continue
        
        # Run prediction
        results = self.agent.predict(
            new_data=new_data,
            prediction_question=prediction_question,
            available_models=model_objects
        )
        
        # Return simplified format for tool use
        return {
            "predictions": results["predictions"],
            "confidence_scores": results["confidence_scores"],
            "model_used": results["model_used"]["model_name"],
            "feature_alignment_score": results["feature_analysis"]["feature_alignment_score"],
            "key_insights": results["business_interpretation"]["key_insights"],
            "reliability_level": results["quality_indicators"]["overall_reliability"],
            "recommendations": results["business_interpretation"]["recommendations"]
        }


# Demo and testing
def demo_prediction_agent():
    """Demonstrate the prediction agent with sample scenarios"""
    
    print("🔮 Starting Prediction Agent Demo...")
    print("=" * 40)
    
    # Create sample new data for prediction
    np.random.seed(42)
    new_customer_data = pd.DataFrame({
        'customer_age': np.random.randint(25, 65, 100),
        'annual_income': np.random.normal(75000, 20000, 100),
        'total_spent': np.random.normal(1200, 400, 100),
        'months_active': np.random.randint(3, 24, 100),
        'support_calls': np.random.poisson(2, 100),
        'product_category': np.random.choice(['Premium', 'Standard', 'Basic'], 100),
        'region': np.random.choice(['North', 'South', 'East', 'West'], 100)
    })
    
    # Create sample available models
    available_models = [
        AvailableModel(
            model_id="churn_model_v1",
            model_name="Customer Churn Predictor",
            model_type=ModelType.CLASSIFICATION,
            description="Predicts customer churn with 87% accuracy",
            business_purpose="Identify customers at risk of leaving to enable proactive retention",
            training_features=["customer_age", "annual_income", "total_spent", "months_active", "support_calls", "engagement_score"],
            target_variable="will_churn",
            performance_metrics={"accuracy": 0.87, "precision": 0.82, "recall": 0.84, "f1_score": 0.83},
            training_data_description="Customer data from past 2 years with churn outcomes",
            training_data_summary={"n_customers": 10000, "churn_rate": 0.23, "avg_tenure": 14.5},
            model_artifacts_path="/models/churn_model_v1.joblib",
            feature_engineering_steps=["StandardScaler on numerical features", "OneHot encoding for categories"],
            preprocessing_pipeline={"scaler": "StandardScaler", "encoder": "OneHotEncoder"},
            domain="customer_analytics",
            last_trained=datetime(2024, 7, 15)
        ),
        
        AvailableModel(
            model_id="value_predictor_v2", 
            model_name="Customer Lifetime Value Predictor",
            model_type=ModelType.REGRESSION,
            description="Predicts customer lifetime value with RMSE of $125",
            business_purpose="Estimate potential value of customers for prioritization and resource allocation",
            training_features=["customer_age", "annual_income", "purchase_frequency", "avg_order_value", "tenure_months"],
            target_variable="lifetime_value",
            performance_metrics={"rmse": 125.0, "mae": 98.5, "r2_score": 0.78},
            training_data_description="Customer transaction data with calculated lifetime values",
            training_data_summary={"n_customers": 8500, "avg_clv": 850, "clv_range": "50-5000"},
            model_artifacts_path="/models/clv_model_v2.joblib",
            feature_engineering_steps=["Log transform for skewed features", "RFM feature creation"],
            preprocessing_pipeline={"scaler": "RobustScaler", "log_features": ["annual_income", "total_spent"]},
            domain="customer_analytics", 
            last_trained=datetime(2024, 7, 20)
        ),
        
        AvailableModel(
            model_id="segment_model_v1",
            model_name="Customer Segmentation Model", 
            model_type=ModelType.CLUSTERING,
            description="Groups customers into 5 behavioral segments",
            business_purpose="Segment customers for targeted marketing and personalization",
            training_features=["purchase_frequency", "avg_order_value", "recency_days", "total_spent", "product_diversity"],
            target_variable="customer_segment",
            performance_metrics={"silhouette_score": 0.72, "calinski_harabasz_score": 1840},
            training_data_description="Customer behavioral data for segmentation analysis",
            training_data_summary={"n_customers": 12000, "n_segments": 5, "avg_segment_size": 2400},
            model_artifacts_path="/models/segmentation_v1.joblib",
            feature_engineering_steps=["StandardScaler", "RFM feature calculation", "Outlier removal"],
            preprocessing_pipeline={"scaler": "StandardScaler", "outlier_method": "IQR"},
            domain="customer_analytics",
            last_trained=datetime(2024, 7, 10)
        )
    ]
    
    # Initialize agent
    agent = PredictionAgent()
    
    # Test scenarios
    test_scenarios = [
        {
            "question": "Which of these customers are most likely to cancel their subscription in the next 3 months?",
            "expected_model": "churn_model_v1"
        },
        {
            "question": "What is the predicted lifetime value for each of these new customers?", 
            "expected_model": "value_predictor_v2"
        },
        {
            "question": "How should we segment these customers for our next marketing campaign?",
            "expected_model": "segment_model_v1"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🧪 **Test Scenario {i}:**")
        print(f"Question: {scenario['question']}")
        print(f"Expected Best Model: {scenario['expected_model']}")
        print("-" * 50)
        
        # Run prediction
        results = agent.predict(
            new_data=new_customer_data,
            prediction_question=scenario["question"],
            available_models=available_models,
            session_id=f"demo_scenario_{i}"
        )
        
        # Display results
        print(f"✅ **Selected Model:** {results['model_used']['model_name']}")
        print(f"📊 **Model Type:** {results['model_used']['model_type']}")
        print(f"🎯 **Confidence Level:** {results['transfer_learning']['confidence_level']}")
        print(f"🔗 **Feature Alignment:** {results['feature_analysis']['feature_alignment_score']:.1%}")
        print(f"🚀 **Transfer Strategy:** {results['transfer_learning']['strategy_used']}")
        
        print(f"\n📈 **Prediction Summary:**")
        pred_summary = results["prediction_summary"]
        print(f"• Total Predictions: {pred_summary['total_predictions']}")
        print(f"• Average Confidence: {pred_summary['average_confidence']:.1%}")
        
        print(f"\n🧠 **Key Insights:**")
        interpretation = results["business_interpretation"]
        print(interpretation["explanation"][:300] + "...")
        
        print(f"\n💡 **Recommendations:**")
        for rec in interpretation["recommendations"][:3]:
            print(f"• {rec}")
        
        print(f"\n🔍 **Top Features:**")
        feature_importance = results["feature_analysis"]["feature_importance"]
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
        for feature, importance in top_features:
            print(f"• {feature}: {importance:.1%} importance")
        
        if results["feature_analysis"]["features_created"]:
            print(f"\n🛠️ **Features Created:** {', '.join(results['feature_analysis']['features_created'])}")
        
        print("\n" + "=" * 60)
    
    return results


# Integration helper functions
def create_sample_model_registry() -> List[Dict[str, Any]]:
    """Create a sample model registry for testing"""
    
    return [
        {
            "model_id": "churn_rf_v1",
            "model_name": "Random Forest Churn Predictor",
            "model_type": "classification",
            "description": "Predicts customer churn using random forest",
            "business_purpose": "Reduce churn through early identification",
            "training_features": ["tenure_months", "monthly_charges", "total_charges", "contract_type", "payment_method"],
            "target_variable": "churn",
            "performance_metrics": {"accuracy": 0.84, "precision": 0.79, "recall": 0.82},
            "training_data_description": "Telecom customer data with churn labels",
            "training_data_summary": {"customers": 7043, "churn_rate": 0.27},
            "model_artifacts_path": "/models/churn_rf_v1.joblib",
            "feature_engineering_steps": ["StandardScaler", "LabelEncoder for categories"],
            "preprocessing_pipeline": {"scaler": "StandardScaler"},
            "domain": "telecom",
            "last_trained": "2024-07-15T10:30:00"
        },
        
        {
            "model_id": "sales_forecast_v1",
            "model_name": "Sales Forecasting Model",
            "model_type": "forecasting", 
            "description": "Forecasts monthly sales using Prophet",
            "business_purpose": "Predict future sales for inventory and resource planning",
            "training_features": ["date", "sales_amount", "marketing_spend", "seasonality_factors"],
            "target_variable": "sales_amount",
            "performance_metrics": {"mape": 8.5, "rmse": 12500, "mae": 9800},
            "training_data_description": "Monthly sales data with marketing spend",
            "training_data_summary": {"months": 36, "avg_sales": 125000, "trend": "growing"},
            "model_artifacts_path": "/models/sales_forecast_v1.joblib",
            "feature_engineering_steps": ["Seasonality detection", "Holiday effects"],
            "preprocessing_pipeline": {"freq": "M", "seasonality": "multiplicative"},
            "domain": "sales",
            "last_trained": "2024-07-01T14:20:00"
        }
    ]


def create_prediction_tool():
    """Create a prediction tool for integration with other agents"""
    
    agent = PredictionAgent()
    tool = PredictionTool(agent)
    
    return tool.predict_with_best_model


# Example usage
if __name__ == "__main__":
    # Run the demo
    demo_results = demo_prediction_agent()
    
    print(f"\n🔧 **Tool Integration Example:**")
    print("=" * 35)
    
    # Example of using as a tool
    tool_function = create_prediction_tool()
    
    # Sample new data
    sample_data = pd.DataFrame({
        'customer_tenure': [12, 24, 6, 18],
        'monthly_payment': [50, 75, 45, 65],
        'total_paid': [600, 1800, 270, 1170],
        'contract': ['Month-to-month', 'One year', 'Month-to-month', 'Two year']
    })
    
    # Sample model registry
    sample_models = create_sample_model_registry()
    
    tool_result = tool_function(
        new_data=sample_data,
        prediction_question="Which customers are likely to churn next month?",
        available_models=sample_models
    )
    
    print(f"**Tool Output:**")
    print(f"• Model Used: {tool_result['model_used']}")
    print(f"• Predictions: {tool_result['predictions'][:4]}")
    print(f"• Confidence: {[f'{c:.1%}' for c in tool_result['confidence_scores'][:4]]}")
    print(f"• Reliability: {tool_result['reliability_level']}")
    
    print(f"\n✅ **Prediction Agent Demo Complete!**")