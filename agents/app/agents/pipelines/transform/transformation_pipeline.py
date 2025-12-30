"""
Transformation Pipeline Architecture for Feature Recommendations

This pipeline provides a high-level interface for the feature engineering agent,
designed to support chat-based interactions where users ask questions and receive
feature recommendations. It manages the complete workflow from user queries to
feature registry management.

The pipeline architecture supports:
1. Feature Recommendation: Generate features based on user queries
2. Feature Registry: Manage selected features and their dependencies
3. Conversation Context: Maintain context across multiple interactions
4. Pipeline Generation: Generate transformation pipelines for selected features
5. Export & Scheduling: Support for exporting pipelines in various formats

This is designed to work with the chat-based UX shown in CompletePipelineWithExport.jsx
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from langchain_openai import ChatOpenAI

from app.agents.pipelines.base import AgentPipeline
from app.agents.nodes.transform.feature_engineering_agent import (
    run_feature_engineering_pipeline,
    generate_standard_features
)
from app.agents.nodes.transform.domain_config import (
    DomainConfiguration,
    get_domain_config,
    CYBERSECURITY_DOMAIN_CONFIG
)
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm

logger = logging.getLogger("lexy-ai-service")


class FeatureStatus(str, Enum):
    """Status of a feature in the registry"""
    RECOMMENDED = "recommended"
    SELECTED = "selected"
    IN_PIPELINE = "in_pipeline"
    DEPLOYED = "deployed"


@dataclass
class FeatureRegistryEntry:
    """Entry in the feature registry"""
    feature_id: str
    feature_name: str
    feature_type: str
    natural_language_question: str
    business_context: Optional[str] = None
    compliance_reasoning: Optional[str] = None
    transformation_layer: str = "gold"  # silver or gold
    feature_group: Optional[str] = None
    recommendation_score: Optional[float] = None
    required_schemas: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    calculation_logic: Optional[str] = None
    status: FeatureStatus = FeatureStatus.RECOMMENDED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # Pipeline structure
    silver_pipeline: Optional[Dict[str, Any]] = None
    gold_pipeline: Optional[Dict[str, Any]] = None
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # feature_ids
    used_by: List[str] = field(default_factory=list)  # feature_ids


@dataclass
class ConversationContext:
    """Context maintained across conversation turns"""
    project_id: str
    domain: str = "cybersecurity"
    compliance_framework: Optional[str] = None
    severity_levels: List[str] = field(default_factory=list)
    sla_requirements: Dict[str, int] = field(default_factory=dict)
    previous_queries: List[str] = field(default_factory=list)
    selected_features: Set[str] = field(default_factory=set)  # feature_ids
    feature_registry: Dict[str, FeatureRegistryEntry] = field(default_factory=dict)


@dataclass
class FeatureRecommendationRequest:
    """Request for feature recommendations"""
    user_query: str
    project_id: str
    domain: Optional[str] = "cybersecurity"
    conversation_context: Optional[ConversationContext] = None
    include_risk_features: bool = True
    include_impact_features: bool = True
    include_likelihood_features: bool = True
    min_recommendation_score: float = 0.5


@dataclass
class FeatureRecommendationResponse:
    """Response containing feature recommendations"""
    success: bool
    recommended_features: List[FeatureRegistryEntry]
    clarifying_questions: List[str] = field(default_factory=list)
    reasoning_plan: Optional[Dict[str, Any]] = None
    analytical_intent: Optional[Dict[str, Any]] = None
    relevant_schemas: List[str] = field(default_factory=list)
    conversation_context: Optional[ConversationContext] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class PipelineGenerationRequest:
    """Request to generate transformation pipelines for selected features"""
    feature_ids: List[str]
    conversation_context: ConversationContext
    export_format: str = "dbt"  # dbt, airflow, databricks, sql
    include_dependencies: bool = True


@dataclass
class PipelineGenerationResponse:
    """Response containing generated pipelines"""
    success: bool
    pipelines: Dict[str, Dict[str, Any]]  # feature_id -> pipeline structure
    dependencies: Dict[str, List[str]]  # feature_id -> list of dependent feature_ids
    execution_order: List[str]  # Ordered list of feature_ids
    error: Optional[str] = None


class TransformationPipeline(AgentPipeline):
    """
    Pipeline architecture for feature recommendation and transformation.
    
    This pipeline wraps the feature engineering agent and provides:
    - Feature recommendation based on user queries
    - Feature registry management
    - Conversation context tracking
    - Pipeline generation for selected features
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        retrieval_helper: Optional[RetrievalHelper] = None,
        domain_config: Optional[DomainConfiguration] = None
    ):
        """Initialize the transformation pipeline
        
        Args:
            llm: Language model instance (defaults to get_llm())
            retrieval_helper: Retrieval helper for schema/knowledge retrieval
            domain_config: Domain configuration (defaults to cybersecurity)
        """
        # Use default LLM if not provided
        if llm is None:
            llm = get_llm(temperature=0, model="gpt-4o-mini")
        
        # Use default domain config if not provided
        if domain_config is None:
            domain_config = CYBERSECURITY_DOMAIN_CONFIG
        
        super().__init__(
            name="transformation_pipeline",
            version="1.0.0",
            description="Pipeline for feature recommendation and transformation generation",
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        self._domain_config = domain_config
        self._conversation_contexts: Dict[str, ConversationContext] = {}
        self._metrics = {
            "total_recommendations": 0,
            "total_selections": 0,
            "total_pipelines_generated": 0,
            "average_recommendation_score": 0.0
        }
    
    async def initialize(self) -> None:
        """Initialize the pipeline"""
        await super().initialize()
        logger.info("TransformationPipeline initialized successfully")
    
    async def recommend_features(
        self,
        request: FeatureRecommendationRequest
    ) -> FeatureRecommendationResponse:
        """
        Generate feature recommendations based on user query.
        
        This is the main entry point for the chat-based UX where users
        ask questions and receive feature recommendations.
        
        Args:
            request: Feature recommendation request
            
        Returns:
            Feature recommendation response with recommended features
        """
        try:
            logger.info(f"Generating feature recommendations for query: {request.user_query[:100]}...")
            
            # Get or create conversation context
            context_key = f"{request.project_id}_{request.domain}"
            if request.conversation_context:
                context = request.conversation_context
            elif context_key in self._conversation_contexts:
                context = self._conversation_contexts[context_key]
            else:
                context = ConversationContext(
                    project_id=request.project_id,
                    domain=request.domain or "cybersecurity"
                )
                self._conversation_contexts[context_key] = context
            
            # Add query to history
            context.previous_queries.append(request.user_query)
            
            # Get selected features from context to pass to the agent
            selected_features_for_agent = []
            if context.selected_features:
                for feature_id in context.selected_features:
                    if feature_id in context.feature_registry:
                        entry = context.feature_registry[feature_id]
                        # Convert to format expected by feature engineering agent
                        selected_features_for_agent.append({
                            "feature_name": entry.feature_name,
                            "natural_language_question": entry.natural_language_question,
                            "feature_type": entry.feature_type,
                            "transformation_layer": entry.transformation_layer,
                            "business_context": entry.business_context,
                            "compliance_reasoning": entry.compliance_reasoning,
                            "calculation_logic": entry.calculation_logic,
                            "required_schemas": entry.required_schemas,
                            "required_fields": entry.required_fields
                        })
            
            # Enhance user query with selected features context if available
            enhanced_query = request.user_query
            if selected_features_for_agent:
                selected_summary = f"\n\nPreviously selected features ({len(selected_features_for_agent)}):\n"
                for i, feat in enumerate(selected_features_for_agent[:5], 1):  # Show first 5
                    selected_summary += f"{i}. {feat['feature_name']}: {feat['natural_language_question']}\n"
                if len(selected_features_for_agent) > 5:
                    selected_summary += f"... and {len(selected_features_for_agent) - 5} more selected features.\n"
                selected_summary += "\nPlease generate additional features that complement or build upon these selected features."
                enhanced_query = request.user_query + selected_summary
                logger.info(f"Including {len(selected_features_for_agent)} selected features in recommendation context")
            
            # Get domain config
            domain_config = get_domain_config(request.domain or "cybersecurity")
            
            # Prepare initial state with selected features
            initial_state = None
            if selected_features_for_agent:
                from app.agents.nodes.transform.feature_engineering_types import FeatureEngineeringState
                initial_state: FeatureEngineeringState = {
                    "messages": [],
                    "user_query": enhanced_query,
                    "analytical_intent": {},
                    "relevant_schemas": [],
                    "available_features": selected_features_for_agent,  # Pass selected features
                    "clarifying_questions": [],
                    "reasoning_plan": {},
                    "recommended_features": [],
                    "feature_dependencies": {},
                    "relevance_scores": {},
                    "next_agent": "breakdown_analysis",
                    "project_id": request.project_id,
                    "histories": context.previous_queries[:-1],  # Exclude current query
                    "schema_registry": {},
                    "knowledge_documents": [],
                    "domain_config": domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict(),
                    "validation_expectations": [],
                    "refining_instructions": None,
                    "refining_examples": [],
                    "feature_generation_instructions": None,
                    "feature_generation_examples": [],
                    "identified_controls": None,
                    "control_universe": None,
                    "metrics": None
                }
            
            # Call feature engineering agent
            result = await run_feature_engineering_pipeline(
                user_query=enhanced_query,
                project_id=request.project_id,
                retrieval_helper=self._retrieval_helper,
                domain_config=domain_config,
                histories=context.previous_queries[:-1],  # Exclude current query
                initial_state=initial_state  # Pass initial state with selected features
            )
            
            # Convert recommended features to registry entries
            # Track new vs existing features
            new_features = []
            existing_features = []
            recommended_features = []
            
            # Process standard features
            for feature_dict in result.get("recommended_features", []):
                entry = self._create_registry_entry(feature_dict, FeatureStatus.RECOMMENDED, context)
                if entry.feature_id not in context.feature_registry:
                    # New feature - add to registry
                    context.feature_registry[entry.feature_id] = entry
                    new_features.append(entry)
                    recommended_features.append(entry)
                else:
                    # Existing feature - update status if needed
                    existing_features.append(entry)
                    recommended_features.append(entry)
            
            # Process risk features if requested
            if request.include_risk_features:
                for feature_dict in result.get("risk_features", []):
                    entry = self._create_registry_entry(feature_dict, FeatureStatus.RECOMMENDED, context)
                    if entry.recommendation_score and entry.recommendation_score >= request.min_recommendation_score:
                        if entry.feature_id not in context.feature_registry:
                            context.feature_registry[entry.feature_id] = entry
                            new_features.append(entry)
                            recommended_features.append(entry)
                        else:
                            existing_features.append(entry)
                            recommended_features.append(entry)
            
            # Process impact features if requested
            if request.include_impact_features:
                for feature_dict in result.get("impact_features", []):
                    entry = self._create_registry_entry(feature_dict, FeatureStatus.RECOMMENDED, context)
                    if entry.recommendation_score and entry.recommendation_score >= request.min_recommendation_score:
                        if entry.feature_id not in context.feature_registry:
                            context.feature_registry[entry.feature_id] = entry
                            new_features.append(entry)
                            recommended_features.append(entry)
                        else:
                            existing_features.append(entry)
                            recommended_features.append(entry)
            
            # Process likelihood features if requested
            if request.include_likelihood_features:
                for feature_dict in result.get("likelihood_features", []):
                    entry = self._create_registry_entry(feature_dict, FeatureStatus.RECOMMENDED, context)
                    if entry.recommendation_score and entry.recommendation_score >= request.min_recommendation_score:
                        if entry.feature_id not in context.feature_registry:
                            context.feature_registry[entry.feature_id] = entry
                            new_features.append(entry)
                            recommended_features.append(entry)
                        else:
                            existing_features.append(entry)
                            recommended_features.append(entry)
            
            logger.info(f"Added {len(new_features)} new features, found {len(existing_features)} existing features in cache")
            if selected_features_for_agent:
                logger.info(f"Used {len(selected_features_for_agent)} selected features as context for recommendations")
            
            # Update metrics
            self._metrics["total_recommendations"] += len(recommended_features)
            if recommended_features:
                avg_score = sum(
                    f.recommendation_score or 0.0 
                    for f in recommended_features 
                    if f.recommendation_score
                ) / len([f for f in recommended_features if f.recommendation_score])
                self._metrics["average_recommendation_score"] = avg_score
            
            # Update context with extracted information
            if result.get("analytical_intent"):
                intent = result["analytical_intent"]
                if "compliance_framework" in intent:
                    context.compliance_framework = intent["compliance_framework"]
                if "severity_levels" in intent:
                    context.severity_levels = intent["severity_levels"]
                if "sla_requirements" in intent:
                    context.sla_requirements = intent["sla_requirements"]
            
            return FeatureRecommendationResponse(
                success=True,
                recommended_features=recommended_features,
                clarifying_questions=result.get("clarifying_questions", []),
                reasoning_plan=result.get("reasoning_plan"),
                analytical_intent=result.get("analytical_intent"),
                relevant_schemas=result.get("relevant_schemas", []),
                conversation_context=context,
                # Include metadata about new vs existing features and selected features used
                metadata={
                    "new_features_count": len(new_features),
                    "existing_features_count": len(existing_features),
                    "total_in_registry": len(context.feature_registry),
                    "selected_features_used": len(selected_features_for_agent),
                    "selected_feature_names": [f["feature_name"] for f in selected_features_for_agent] if selected_features_for_agent else []
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating feature recommendations: {e}", exc_info=True)
            return FeatureRecommendationResponse(
                success=False,
                recommended_features=[],
                error=str(e)
            )
    
    def _create_registry_entry(
        self,
        feature_dict: Dict[str, Any],
        status: FeatureStatus,
        context: Optional[ConversationContext] = None
    ) -> FeatureRegistryEntry:
        """Create a registry entry from a feature dictionary
        
        Args:
            feature_dict: Feature dictionary from agent
            status: Feature status
            context: Optional conversation context to check for duplicates
            
        Returns:
            FeatureRegistryEntry - new entry or existing entry if duplicate found
        """
        feature_name = feature_dict.get("feature_name", "unknown")
        
        # Check for existing feature with same name in context (deduplication)
        if context:
            for existing_id, existing_entry in context.feature_registry.items():
                if existing_entry.feature_name == feature_name:
                    # Feature already exists, return existing entry
                    logger.info(f"Feature '{feature_name}' already exists in registry with ID {existing_id}")
                    return existing_entry
        
        # Generate unique feature ID for new feature
        feature_id = f"{feature_name}_{datetime.now().timestamp()}"
        
        # Extract pipeline structure if available
        silver_pipeline = feature_dict.get("silver_pipeline")
        gold_pipeline = feature_dict.get("gold_pipeline")
        
        # If pipelines not provided, generate basic structure
        if not silver_pipeline:
            silver_pipeline = self._generate_silver_pipeline(feature_dict)
        if not gold_pipeline and feature_dict.get("transformation_layer") == "gold":
            gold_pipeline = self._generate_gold_pipeline(feature_dict)
        
        return FeatureRegistryEntry(
            feature_id=feature_id,
            feature_name=feature_name,
            feature_type=feature_dict.get("feature_type", "metric"),
            natural_language_question=feature_dict.get("natural_language_question", ""),
            business_context=feature_dict.get("business_context"),
            compliance_reasoning=feature_dict.get("compliance_reasoning") or feature_dict.get("soc2_compliance_reasoning"),
            transformation_layer=feature_dict.get("transformation_layer", "gold"),
            feature_group=feature_dict.get("feature_group"),
            recommendation_score=feature_dict.get("recommendation_score"),
            required_schemas=feature_dict.get("required_schemas", []),
            required_fields=feature_dict.get("required_fields", []),
            calculation_logic=feature_dict.get("calculation_logic"),
            status=status,
            silver_pipeline=silver_pipeline,
            gold_pipeline=gold_pipeline,
            depends_on=feature_dict.get("depends_on", [])
        )
    
    def _generate_silver_pipeline(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a basic silver pipeline structure"""
        feature_name = feature_dict.get("feature_name", "unknown")
        schemas = feature_dict.get("required_schemas", [])
        
        return {
            "source_tables": [
                {
                    "name": schema.replace("*: ", ""),
                    "layer": "bronze",
                    "columns": feature_dict.get("required_fields", [])
                }
                for schema in schemas
            ],
            "destination_table": {
                "name": f"silver_{feature_name}",
                "layer": "silver",
                "columns": [feature_name, "updated_at"]
            },
            "transformation_description": f"Transform {', '.join(schemas)} to calculate {feature_dict.get('natural_language_question', '')}",
            "sample_output": []
        }
    
    def _generate_gold_pipeline(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a basic gold pipeline structure"""
        feature_name = feature_dict.get("feature_name", "unknown")
        aggregation_method = feature_dict.get("aggregation_method", "count")
        
        return {
            "source_tables": [{
                "name": f"silver_{feature_name}",
                "layer": "silver",
                "columns": [feature_name, "updated_at"]
            }],
            "destination_table": {
                "name": f"gold_{feature_name}",
                "layer": "gold",
                "columns": [feature_name, "aggregated_value", "updated_at"]
            },
            "transformation_description": f"Aggregate {feature_name} using {aggregation_method}",
            "sample_output": []
        }
    
    async def select_features(
        self,
        feature_ids: List[str],
        conversation_context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Select features and add them to the registry.
        
        This is called when the user selects features from recommendations
        in the chat UX.
        
        Args:
            feature_ids: List of feature IDs to select
            conversation_context: Current conversation context
            
        Returns:
            Dictionary with selected features and updated context
        """
        selected_entries = []
        
        for feature_id in feature_ids:
            if feature_id in conversation_context.feature_registry:
                entry = conversation_context.feature_registry[feature_id]
                entry.status = FeatureStatus.SELECTED
                conversation_context.selected_features.add(feature_id)
                selected_entries.append(entry)
            else:
                logger.warning(f"Feature {feature_id} not found in registry")
        
        # Update metrics
        self._metrics["total_selections"] += len(selected_entries)
        
        return {
            "success": True,
            "selected_features": [self._entry_to_dict(e) for e in selected_entries],
            "conversation_context": conversation_context
        }
    
    async def generate_pipelines(
        self,
        request: PipelineGenerationRequest
    ) -> PipelineGenerationResponse:
        """
        Generate transformation pipelines for selected features.
        
        This generates the complete pipeline structure (Bronze -> Silver -> Gold)
        for the selected features, including dependency resolution.
        
        Args:
            request: Pipeline generation request
            
        Returns:
            Pipeline generation response with pipeline structures
        """
        try:
            pipelines = {}
            dependencies = {}
            execution_order = []
            
            # Get all features from registry
            all_features = request.conversation_context.feature_registry
            
            # Build dependency graph
            for feature_id in request.feature_ids:
                if feature_id not in all_features:
                    continue
                
                entry = all_features[feature_id]
                pipelines[feature_id] = {
                    "feature_name": entry.feature_name,
                    "silver_pipeline": entry.silver_pipeline,
                    "gold_pipeline": entry.gold_pipeline,
                    "transformation_layer": entry.transformation_layer
                }
                
                # Collect dependencies
                if request.include_dependencies:
                    deps = self._resolve_dependencies(feature_id, all_features)
                    dependencies[feature_id] = deps
            
            # Calculate execution order (topological sort)
            execution_order = self._calculate_execution_order(
                request.feature_ids,
                dependencies,
                all_features
            )
            
            # Update metrics
            self._metrics["total_pipelines_generated"] += len(pipelines)
            
            return PipelineGenerationResponse(
                success=True,
                pipelines=pipelines,
                dependencies=dependencies,
                execution_order=execution_order
            )
            
        except Exception as e:
            logger.error(f"Error generating pipelines: {e}", exc_info=True)
            return PipelineGenerationResponse(
                success=False,
                pipelines={},
                dependencies={},
                execution_order=[],
                error=str(e)
            )
    
    def _resolve_dependencies(
        self,
        feature_id: str,
        all_features: Dict[str, FeatureRegistryEntry]
    ) -> List[str]:
        """Resolve all dependencies for a feature"""
        if feature_id not in all_features:
            return []
        
        entry = all_features[feature_id]
        deps = set(entry.depends_on)
        
        # Recursively resolve dependencies
        for dep_id in entry.depends_on:
            deps.update(self._resolve_dependencies(dep_id, all_features))
        
        return list(deps)
    
    def _calculate_execution_order(
        self,
        feature_ids: List[str],
        dependencies: Dict[str, List[str]],
        all_features: Dict[str, FeatureRegistryEntry]
    ) -> List[str]:
        """Calculate execution order using topological sort"""
        # Build in-degree map
        in_degree = {fid: 0 for fid in feature_ids}
        
        for feature_id in feature_ids:
            deps = dependencies.get(feature_id, [])
            for dep_id in deps:
                if dep_id in in_degree:
                    in_degree[feature_id] += 1
        
        # Topological sort
        queue = [fid for fid, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while queue:
            current = queue.pop(0)
            execution_order.append(current)
            
            # Update in-degrees of dependents
            for feature_id in feature_ids:
                if current in dependencies.get(feature_id, []):
                    in_degree[feature_id] -= 1
                    if in_degree[feature_id] == 0:
                        queue.append(feature_id)
        
        # Add any remaining features (shouldn't happen in a DAG)
        for feature_id in feature_ids:
            if feature_id not in execution_order:
                execution_order.append(feature_id)
        
        return execution_order
    
    def _entry_to_dict(self, entry: FeatureRegistryEntry) -> Dict[str, Any]:
        """Convert registry entry to dictionary"""
        return {
            "feature_id": entry.feature_id,
            "feature_name": entry.feature_name,
            "feature_type": entry.feature_type,
            "natural_language_question": entry.natural_language_question,
            "business_context": entry.business_context,
            "compliance_reasoning": entry.compliance_reasoning,
            "transformation_layer": entry.transformation_layer,
            "feature_group": entry.feature_group,
            "recommendation_score": entry.recommendation_score,
            "required_schemas": entry.required_schemas,
            "required_fields": entry.required_fields,
            "calculation_logic": entry.calculation_logic,
            "status": entry.status.value,
            "silver_pipeline": entry.silver_pipeline,
            "gold_pipeline": entry.gold_pipeline,
            "depends_on": entry.depends_on
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Main pipeline run method.
        
        This method supports different operation modes:
        - recommend: Generate feature recommendations
        - select: Select features
        - generate_pipelines: Generate transformation pipelines
        
        Args:
            **kwargs: Pipeline arguments including:
                - operation: "recommend", "select", or "generate_pipelines"
                - request: Request object for the operation
                
        Returns:
            Pipeline results
        """
        operation = kwargs.get("operation", "recommend")
        
        if operation == "recommend":
            request = kwargs.get("request")
            if not request:
                # Create request from kwargs
                request = FeatureRecommendationRequest(
                    user_query=kwargs.get("user_query", ""),
                    project_id=kwargs.get("project_id", ""),
                    domain=kwargs.get("domain", "cybersecurity"),
                    conversation_context=kwargs.get("conversation_context")
                )
            response = await self.recommend_features(request)
            return {
                "success": response.success,
                "recommended_features": [self._entry_to_dict(f) for f in response.recommended_features],
                "clarifying_questions": response.clarifying_questions,
                "reasoning_plan": response.reasoning_plan,
                "analytical_intent": response.analytical_intent,
                "relevant_schemas": response.relevant_schemas,
                "error": response.error
            }
        
        elif operation == "select":
            feature_ids = kwargs.get("feature_ids", [])
            conversation_context = kwargs.get("conversation_context")
            if not conversation_context:
                raise ValueError("conversation_context is required for select operation")
            return await self.select_features(feature_ids, conversation_context)
        
        elif operation == "generate_pipelines":
            request = kwargs.get("request")
            if not request:
                raise ValueError("request is required for generate_pipelines operation")
            response = await self.generate_pipelines(request)
            return {
                "success": response.success,
                "pipelines": response.pipelines,
                "dependencies": response.dependencies,
                "execution_order": response.execution_order,
                "error": response.error
            }
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "domain": self._domain_config.domain_name if self._domain_config else "cybersecurity",
            "has_retrieval_helper": self._retrieval_helper is not None,
            "active_conversations": len(self._conversation_contexts)
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the pipeline"""
        return {
            **self._metrics,
            "active_conversations": len(self._conversation_contexts),
            "total_registry_features": sum(
                len(ctx.feature_registry) 
                for ctx in self._conversation_contexts.values()
            )
        }
    
    def reset_metrics(self) -> None:
        """Reset the pipeline's performance metrics"""
        self._metrics = {
            "total_recommendations": 0,
            "total_selections": 0,
            "total_pipelines_generated": 0,
            "average_recommendation_score": 0.0
        }
    
    def get_conversation_context(
        self,
        project_id: str,
        domain: str = "cybersecurity"
    ) -> Optional[ConversationContext]:
        """Get conversation context for a project/domain"""
        context_key = f"{project_id}_{domain}"
        return self._conversation_contexts.get(context_key)
    
    def clear_conversation_context(
        self,
        project_id: str,
        domain: str = "cybersecurity"
    ) -> None:
        """Clear conversation context for a project/domain"""
        context_key = f"{project_id}_{domain}"
        if context_key in self._conversation_contexts:
            del self._conversation_contexts[context_key]
            logger.info(f"Cleared conversation context for {context_key}")

