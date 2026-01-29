"""
Lane-to-Feature Engineering Integration

This module bridges playbook lanes with feature engineering agents,
allowing lanes to leverage the sophisticated feature generation 
capabilities directly.

Key integrations:
- LaneType.SILVER_FEATURES → FeatureRecommendationAgent, FeatureCalculationPlanAgent
- LaneType.RISK_SCORING → ImpactFeatureGenerationAgent, LikelihoodFeatureGenerationAgent, RiskFeatureGenerationAgent
- LaneType.COMPLIANCE → ControlIdentificationAgent
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.transform.domain_config import (
    DomainConfiguration,
    get_domain_config,
    CYBERSECURITY_DOMAIN_CONFIG,
    HR_COMPLIANCE_DOMAIN_CONFIG
)
from app.agents.nodes.transform.feature_engineering_types import FeatureEngineeringState
from app.agents.nodes.transform.feature_engineering_agent import (
    QueryBreakdownAgent,
    QueryUnderstandingAgent,
    KnowledgeRefiningAgent,
    SchemaAnalysisAgent,
    ControlIdentificationAgent,
    FeatureRecommendationAgent,
    FeatureCalculationPlanAgent,
    ImpactFeatureGenerationAgent,
    LikelihoodFeatureGenerationAgent,
    RiskFeatureGenerationAgent,
    FeatureDependencyAgent,
    RelevancyScoringAgent,
    FeatureCombinationAgent,
)
from app.agents.nodes.transform.playbook_knowledge_helper import (
    LaneType,
    KnowledgeContext,
    LaneResearchContext,
    NLFeatureQuestion,
    NLFeatureGenerationResult,
    PlaybookKnowledgeHelper,
    LaneDeepResearchAgent,
    NLFeatureGenerationAgent,
    EnhancedKnowledgeRetriever,
    get_playbook_knowledge_helper,
    get_enhanced_knowledge_retriever,
    create_lane_deep_research_agent,
    create_nl_feature_generation_agent
)

logger = logging.getLogger("lexy-ai-service")


# ============================================================================
# LANE TYPE TO AGENT MAPPING
# ============================================================================

class AgentRole(str, Enum):
    """Roles that agents play in lane execution"""
    PRIMARY = "primary"  # Main feature generator
    SECONDARY = "secondary"  # Supporting agent
    VALIDATOR = "validator"  # Validation/scoring


@dataclass
class LaneAgentConfig:
    """Configuration for agents used in a lane"""
    lane_type: LaneType
    primary_agents: List[str]  # Agent class names in execution order
    secondary_agents: List[str] = field(default_factory=list)
    validator_agents: List[str] = field(default_factory=list)
    description: str = ""
    
    # Context requirements
    needs_schema: bool = True
    needs_knowledge: bool = True
    needs_controls: bool = False
    needs_prior_features: bool = False


# Mapping from lane types to agent configurations
LANE_AGENT_CONFIGS = {
    LaneType.BOOTSTRAP: LaneAgentConfig(
        lane_type=LaneType.BOOTSTRAP,
        primary_agents=["SchemaAnalysisAgent"],
        secondary_agents=["KnowledgeRefiningAgent"],
        description="Load schemas and knowledge for subsequent lanes"
    ),
    
    LaneType.INGESTION: LaneAgentConfig(
        lane_type=LaneType.INGESTION,
        primary_agents=["SchemaAnalysisAgent"],
        description="Retrieve and validate bronze table schemas"
    ),
    
    LaneType.ASSETIZATION: LaneAgentConfig(
        lane_type=LaneType.ASSETIZATION,
        primary_agents=["FeatureRecommendationAgent"],
        secondary_agents=["QueryUnderstandingAgent"],
        description="Generate asset identity and mapping features",
        needs_controls=False
    ),
    
    LaneType.MONITORING: LaneAgentConfig(
        lane_type=LaneType.MONITORING,
        primary_agents=["FeatureRecommendationAgent"],
        description="Generate monitoring and agent coverage features",
        needs_controls=True
    ),
    
    LaneType.NORMALIZATION: LaneAgentConfig(
        lane_type=LaneType.NORMALIZATION,
        primary_agents=["FeatureRecommendationAgent", "FeatureCalculationPlanAgent"],
        secondary_agents=["KnowledgeRefiningAgent"],
        description="Generate data normalization and enrichment features"
    ),
    
    LaneType.SILVER_FEATURES: LaneAgentConfig(
        lane_type=LaneType.SILVER_FEATURES,
        primary_agents=["FeatureRecommendationAgent", "FeatureCalculationPlanAgent"],
        secondary_agents=["QueryUnderstandingAgent", "KnowledgeRefiningAgent"],
        validator_agents=["FeatureDependencyAgent"],
        description="Generate comprehensive silver-layer features",
        needs_controls=True,
        needs_prior_features=True
    ),
    
    LaneType.RISK_SCORING: LaneAgentConfig(
        lane_type=LaneType.RISK_SCORING,
        primary_agents=[
            "ImpactFeatureGenerationAgent",
            "LikelihoodFeatureGenerationAgent", 
            "RiskFeatureGenerationAgent"
        ],
        secondary_agents=["FeatureCombinationAgent"],
        validator_agents=["FeatureDependencyAgent", "RelevancyScoringAgent"],
        description="Generate impact, likelihood, and risk features",
        needs_controls=True,
        needs_prior_features=True
    ),
    
    LaneType.TIME_SERIES: LaneAgentConfig(
        lane_type=LaneType.TIME_SERIES,
        primary_agents=["FeatureRecommendationAgent"],
        description="Generate time series snapshot features",
        needs_prior_features=True
    ),
    
    LaneType.COMPLIANCE: LaneAgentConfig(
        lane_type=LaneType.COMPLIANCE,
        primary_agents=["ControlIdentificationAgent", "FeatureRecommendationAgent"],
        secondary_agents=["KnowledgeRefiningAgent"],
        validator_agents=["RelevancyScoringAgent"],
        description="Generate compliance control evaluation features",
        needs_controls=True,
        needs_prior_features=True
    ),
    
    LaneType.DELIVERY: LaneAgentConfig(
        lane_type=LaneType.DELIVERY,
        primary_agents=["FeatureRecommendationAgent"],
        validator_agents=["RelevancyScoringAgent"],
        description="Generate evidence packaging features",
        needs_prior_features=True
    )
}


def get_lane_agent_config(lane_type: LaneType) -> LaneAgentConfig:
    """Get agent configuration for a lane type"""
    return LANE_AGENT_CONFIGS.get(lane_type, LaneAgentConfig(
        lane_type=lane_type,
        primary_agents=["FeatureRecommendationAgent"],
        description="Generic feature generation"
    ))


# ============================================================================
# STATE CONVERSION UTILITIES
# ============================================================================

def playbook_to_feature_state(
    playbook_state: Dict[str, Any],
    lane_definition: Any,
    knowledge_context: KnowledgeContext,
    user_query: Optional[str] = None
) -> FeatureEngineeringState:
    """
    Convert playbook execution state to feature engineering state.
    
    Args:
        playbook_state: Current playbook execution state
        lane_definition: Lane definition with inputs/outputs
        knowledge_context: Knowledge context for the lane
        user_query: Optional user query (generated from lane if not provided)
        
    Returns:
        FeatureEngineeringState for feature engineering agents
    """
    # Generate query from lane if not provided
    if not user_query:
        user_query = _generate_query_from_lane(lane_definition, playbook_state)
    
    # Extract domain config
    domain = playbook_state.get("domain", "cybersecurity")
    domain_config = get_domain_config(domain)
    
    # Get compliance frameworks
    frameworks = playbook_state.get("compliance_frameworks", ["SOC2"])
    
    # Build feature engineering state
    fe_state: FeatureEngineeringState = {
        "messages": [],
        "user_query": user_query,
        "query_breakdown": None,
        "analytical_intent": {
            "primary_goal": lane_definition.description if hasattr(lane_definition, 'description') else "",
            "compliance_frameworks": frameworks,
            "data_sources": lane_definition.inputs if hasattr(lane_definition, 'inputs') else [],
            "output_requirements": lane_definition.outputs if hasattr(lane_definition, 'outputs') else [],
        },
        "relevant_schemas": [],
        "available_features": [],
        "clarifying_questions": [],
        "reasoning_plan": {},
        "recommended_features": [],
        "feature_dependencies": {},
        "relevance_scores": {},
        "feature_calculation_plan": {},
        "impact_features": [],
        "likelihood_features": [],
        "risk_features": [],
        "next_agent": "feature_recommendation",
        "project_id": playbook_state.get("project_id", ""),
        "histories": [],
        "schema_registry": {},
        "knowledge_documents": _convert_knowledge_to_documents(knowledge_context),
        "domain_config": domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict(),
        "identified_controls": None,
        "control_universe": None,
        "validation_expectations": [],
        "refining_instructions": _build_refining_instructions(lane_definition, frameworks),
        "refining_examples": knowledge_context.examples if knowledge_context else [],
        "feature_generation_instructions": _build_feature_instructions(lane_definition, frameworks),
        "feature_generation_examples": knowledge_context.examples if knowledge_context else [],
    }
    
    # Copy over prior features if available
    silver_features = playbook_state.get("silver_features", {})
    if silver_features:
        fe_state["available_features"] = list(silver_features.values())
    
    # Copy schema context if available
    schema_context = playbook_state.get("schema_context", [])
    if schema_context:
        fe_state["relevant_schemas"] = schema_context
    
    return fe_state


def feature_to_playbook_state(
    fe_state: FeatureEngineeringState,
    playbook_state: Dict[str, Any],
    lane_type: LaneType
) -> Dict[str, Any]:
    """
    Convert feature engineering results back to playbook state updates.
    
    Args:
        fe_state: Feature engineering state with results
        playbook_state: Current playbook state
        lane_type: Type of lane that was executed
        
    Returns:
        Dictionary of state updates to merge into playbook state
    """
    updates = {}
    
    # Extract generated features based on lane type
    if lane_type == LaneType.RISK_SCORING:
        updates["risk_scores"] = {
            "impact_features": fe_state.get("impact_features", []),
            "likelihood_features": fe_state.get("likelihood_features", []),
            "risk_features": fe_state.get("risk_features", []),
        }
    elif lane_type in [LaneType.SILVER_FEATURES, LaneType.ASSETIZATION, LaneType.NORMALIZATION]:
        updates["silver_features"] = {
            "recommended_features": fe_state.get("recommended_features", []),
            "calculation_plan": fe_state.get("feature_calculation_plan", {}),
            "dependencies": fe_state.get("feature_dependencies", {}),
        }
    elif lane_type == LaneType.COMPLIANCE:
        updates["compliance_evidence"] = {
            "identified_controls": fe_state.get("identified_controls", []),
            "recommended_features": fe_state.get("recommended_features", []),
        }
    
    # Always update these
    updates["feature_definitions"] = playbook_state.get("feature_definitions", []) + fe_state.get("recommended_features", [])
    updates["relevance_scores"] = fe_state.get("relevance_scores", {})
    
    return updates


def _generate_query_from_lane(lane_definition: Any, playbook_state: Dict[str, Any]) -> str:
    """Generate a natural language query from lane definition"""
    lane_name = lane_definition.name if hasattr(lane_definition, 'name') else "Unknown"
    lane_desc = lane_definition.description if hasattr(lane_definition, 'description') else ""
    inputs = lane_definition.inputs if hasattr(lane_definition, 'inputs') else []
    outputs = lane_definition.outputs if hasattr(lane_definition, 'outputs') else []
    frameworks = playbook_state.get("compliance_frameworks", ["SOC2"])
    
    query = f"Generate features for {lane_name}. "
    if lane_desc:
        query += f"{lane_desc}. "
    if inputs:
        query += f"Using input tables: {', '.join(inputs[:5])}. "
    if outputs:
        query += f"Output to: {', '.join(outputs[:5])}. "
    if frameworks:
        query += f"Compliance frameworks: {', '.join(frameworks)}."
    
    return query


def _convert_knowledge_to_documents(knowledge_context: KnowledgeContext) -> List[Dict[str, Any]]:
    """Convert KnowledgeContext to knowledge documents format"""
    documents = []
    
    if knowledge_context:
        # Add features as documents
        for feature in knowledge_context.features:
            documents.append({
                "type": "feature",
                "content": feature,
                "metadata": {"source": "playbook_knowledge"}
            })
        
        # Add examples as documents  
        for example in knowledge_context.examples:
            documents.append({
                "type": "example",
                "content": example,
                "metadata": {"source": "playbook_knowledge"}
            })
        
        # Add instructions
        for instruction in knowledge_context.instructions:
            documents.append({
                "type": "instruction",
                "content": instruction,
                "metadata": {"source": "playbook_knowledge"}
            })
        
        # Add compliance info
        if knowledge_context.compliance_info:
            documents.append({
                "type": "compliance",
                "content": knowledge_context.compliance_info,
                "metadata": {"source": "playbook_knowledge"}
            })
    
    return documents


def _build_refining_instructions(lane_definition: Any, frameworks: List[str]) -> str:
    """Build refining instructions from lane definition"""
    lane_type = lane_definition.lane_type if hasattr(lane_definition, 'lane_type') else None
    
    instructions = "Focus on silver-layer features only. "
    
    if lane_type == LaneType.RISK_SCORING:
        instructions += "Generate impact, likelihood, and risk features. "
        instructions += "Use enum metadata tables for classification lookups. "
    elif lane_type == LaneType.COMPLIANCE:
        instructions += "Generate control evaluation features. "
        instructions += "Include evidence packaging requirements. "
    elif lane_type == LaneType.SILVER_FEATURES:
        instructions += "Generate per-entity features without population aggregates. "
    
    if frameworks:
        instructions += f"Target frameworks: {', '.join(frameworks)}. "
    
    return instructions


def _build_feature_instructions(lane_definition: Any, frameworks: List[str]) -> str:
    """Build feature generation instructions from lane definition"""
    outputs = lane_definition.outputs if hasattr(lane_definition, 'outputs') else []
    
    instructions = "Generate features as natural language questions with metadata. "
    
    if outputs:
        instructions += f"Features should populate these tables: {', '.join(outputs[:3])}. "
    
    instructions += "Include calculation formulas where applicable. "
    instructions += "Specify enum lookups for classifications. "
    
    return instructions


# ============================================================================
# LANE FEATURE EXECUTOR
# ============================================================================

class LaneFeatureExecutor:
    """
    Executes feature engineering agents for a lane.
    
    This class bridges playbook lanes with the feature engineering 
    agent system, allowing lanes to leverage sophisticated feature
    generation without duplicating logic.
    
    Features:
    - Uses EnhancedKnowledgeRetriever for rich context
    - Integrates LaneDeepResearchAgent for research insights
    - Automatic agent selection based on lane type
    - State conversion between playbook and feature engineering
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        retrieval_helper: Optional[RetrievalHelper] = None,
        domain_config: Optional[DomainConfiguration] = None,
        use_deep_research: bool = True
    ):
        self.llm = llm
        self.retrieval_helper = retrieval_helper
        self.domain_config = domain_config or CYBERSECURITY_DOMAIN_CONFIG
        self.use_deep_research = use_deep_research
        
        # Agent cache - lazily initialized
        self._agents: Dict[str, Any] = {}
        
        # Enhanced knowledge retriever with deep research
        self.knowledge_retriever = get_enhanced_knowledge_retriever(llm=llm)
        
        # Deep research agent for lane context
        self.research_agent = create_lane_deep_research_agent(
            llm=llm,
            knowledge_helper=get_playbook_knowledge_helper()
        )
        
        # NL Feature Generation agent for generating questions
        self.nl_feature_agent = create_nl_feature_generation_agent(
            llm=llm,
            knowledge_helper=get_playbook_knowledge_helper()
        )
    
    def _get_agent(self, agent_name: str, domain_config: DomainConfiguration) -> Any:
        """Get or create an agent instance"""
        cache_key = f"{agent_name}_{id(domain_config)}"
        
        if cache_key not in self._agents:
            agent_class = self._get_agent_class(agent_name)
            if agent_class:
                # Create agent with appropriate parameters
                if agent_name in ["SchemaAnalysisAgent", "ControlIdentificationAgent"]:
                    self._agents[cache_key] = agent_class(
                        llm=self.llm,
                        retrieval_helper=self.retrieval_helper,
                        domain_config=domain_config
                    )
                elif agent_name == "KnowledgeRefiningAgent":
                    self._agents[cache_key] = agent_class(
                        llm=self.llm,
                        retrieval_helper=self.retrieval_helper,
                        domain_config=domain_config
                    )
                else:
                    self._agents[cache_key] = agent_class(
                        llm=self.llm,
                        domain_config=domain_config
                    )
        
        return self._agents.get(cache_key)
    
    def _get_agent_class(self, agent_name: str):
        """Get agent class by name"""
        agent_map = {
            "QueryBreakdownAgent": QueryBreakdownAgent,
            "QueryUnderstandingAgent": QueryUnderstandingAgent,
            "KnowledgeRefiningAgent": KnowledgeRefiningAgent,
            "SchemaAnalysisAgent": SchemaAnalysisAgent,
            "ControlIdentificationAgent": ControlIdentificationAgent,
            "FeatureRecommendationAgent": FeatureRecommendationAgent,
            "FeatureCalculationPlanAgent": FeatureCalculationPlanAgent,
            "ImpactFeatureGenerationAgent": ImpactFeatureGenerationAgent,
            "LikelihoodFeatureGenerationAgent": LikelihoodFeatureGenerationAgent,
            "RiskFeatureGenerationAgent": RiskFeatureGenerationAgent,
            "FeatureDependencyAgent": FeatureDependencyAgent,
            "RelevancyScoringAgent": RelevancyScoringAgent,
            "FeatureCombinationAgent": FeatureCombinationAgent,
        }
        return agent_map.get(agent_name)
    
    async def execute_lane(
        self,
        lane_type: LaneType,
        lane_definition: Any,
        playbook_state: Dict[str, Any],
        knowledge_context: KnowledgeContext,
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute feature engineering for a lane.
        
        Args:
            lane_type: Type of lane to execute
            lane_definition: Lane definition with inputs/outputs
            playbook_state: Current playbook execution state
            knowledge_context: Knowledge context for the lane
            user_query: Optional user query override
            
        Returns:
            Dictionary with:
            - success: bool
            - features: List of generated features
            - state_updates: Updates to merge into playbook state
            - reasoning: Explanation of what was generated
            - research_context: Deep research context (if enabled)
        """
        logger.info(f"LaneFeatureExecutor: Executing {lane_type.value} with feature engineering agents")
        
        try:
            # Get agent configuration for this lane
            config = get_lane_agent_config(lane_type)
            
            # Get domain config
            domain = playbook_state.get("domain", "cybersecurity")
            domain_config = get_domain_config(domain)
            compliance_frameworks = playbook_state.get("compliance_frameworks", [])
            
            # Get enhanced research context if deep research is enabled
            research_context = None
            if self.use_deep_research:
                lane_inputs = lane_definition.inputs if hasattr(lane_definition, 'inputs') else []
                lane_outputs = lane_definition.outputs if hasattr(lane_definition, 'outputs') else []
                lane_desc = lane_definition.description if hasattr(lane_definition, 'description') else ""
                
                logger.info(f"Generating deep research context for {lane_type.value}")
                research_context = await self.knowledge_retriever.get_rich_context(
                    lane_type=lane_type,
                    domain=domain,
                    compliance_frameworks=compliance_frameworks,
                    lane_inputs=lane_inputs,
                    lane_outputs=lane_outputs,
                    lane_description=lane_desc
                )
                
                # Enhance knowledge context with research insights
                knowledge_context = self._enhance_knowledge_with_research(
                    knowledge_context, research_context
                )
            
            # Convert to feature engineering state
            fe_state = playbook_to_feature_state(
                playbook_state=playbook_state,
                lane_definition=lane_definition,
                knowledge_context=knowledge_context,
                user_query=user_query
            )
            
            # Add research context to state for agents to use
            if research_context:
                fe_state["research_context"] = {
                    "feature_templates": research_context.feature_templates,
                    "calculation_patterns": research_context.calculation_patterns,
                    "quality_criteria": research_context.quality_criteria,
                    "control_mappings": research_context.control_mappings,
                    "research_insights": research_context.research_insights,
                    "recommended_features": research_context.recommended_features,
                }
            
            # Load schemas if needed
            if config.needs_schema and self.retrieval_helper:
                fe_state = await self._load_schemas(fe_state, lane_definition)
            
            # Run primary agents
            for agent_name in config.primary_agents:
                agent = self._get_agent(agent_name, domain_config)
                if agent:
                    logger.info(f"Running primary agent: {agent_name}")
                    fe_state = await agent(fe_state)
            
            # Run secondary agents
            for agent_name in config.secondary_agents:
                agent = self._get_agent(agent_name, domain_config)
                if agent:
                    logger.info(f"Running secondary agent: {agent_name}")
                    fe_state = await agent(fe_state)
            
            # Run validator agents
            for agent_name in config.validator_agents:
                agent = self._get_agent(agent_name, domain_config)
                if agent:
                    logger.info(f"Running validator agent: {agent_name}")
                    fe_state = await agent(fe_state)
            
            # Convert results back to playbook state updates
            state_updates = feature_to_playbook_state(fe_state, playbook_state, lane_type)
            
            # Build result
            all_features = []
            all_features.extend(fe_state.get("recommended_features", []))
            all_features.extend(fe_state.get("impact_features", []))
            all_features.extend(fe_state.get("likelihood_features", []))
            all_features.extend(fe_state.get("risk_features", []))
            
            # Include research-recommended features
            if research_context and research_context.recommended_features:
                for rec_feature in research_context.recommended_features:
                    if rec_feature not in all_features:
                        all_features.append(rec_feature)
            
            result = {
                "success": True,
                "features": all_features,
                "state_updates": state_updates,
                "reasoning": self._build_reasoning(fe_state, config, research_context),
                "calculation_plan": fe_state.get("feature_calculation_plan", {}),
                "dependencies": fe_state.get("feature_dependencies", {}),
                "relevance_scores": fe_state.get("relevance_scores", {}),
            }
            
            # Add research context to result if available
            if research_context:
                result["research_context"] = {
                    "insights": research_context.research_insights,
                    "quality_criteria": research_context.quality_criteria,
                    "control_mappings": research_context.control_mappings,
                }
            
            # Generate NL questions for features
            nl_questions_result = await self.generate_nl_questions(
                lane_type=lane_type,
                domain=domain,
                compliance_frameworks=compliance_frameworks,
                user_goal=user_query,
                lane_inputs=lane_definition.inputs if hasattr(lane_definition, 'inputs') else [],
                lane_outputs=lane_definition.outputs if hasattr(lane_definition, 'outputs') else [],
                research_context=research_context
            )
            
            result["nl_questions"] = [
                {
                    "question": q.question,
                    "feature_name": q.feature_name,
                    "feature_type": q.feature_type,
                    "dependencies": q.dependencies,
                    "compliance_mapping": q.compliance_mapping,
                    "validation_rules": q.validation_rules,
                    "priority": q.priority
                }
                for q in nl_questions_result.questions
            ]
            result["generation_reasoning"] = nl_questions_result.generation_reasoning
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing lane with feature agents: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "features": [],
                "state_updates": {},
            }
    
    async def generate_nl_questions(
        self,
        lane_type: LaneType,
        domain: str,
        compliance_frameworks: List[str],
        user_goal: Optional[str] = None,
        lane_inputs: List[str] = None,
        lane_outputs: List[str] = None,
        research_context: Optional[LaneResearchContext] = None
    ) -> NLFeatureGenerationResult:
        """
        Generate natural language questions for feature engineering.
        
        This uses the NLFeatureGenerationAgent to produce detailed questions
        that describe features to compute without generating SQL directly.
        
        Args:
            lane_type: Type of lane
            domain: Domain name
            compliance_frameworks: Compliance frameworks
            user_goal: User's stated goal
            lane_inputs: Input table names
            lane_outputs: Output table names
            research_context: Optional pre-computed research context
            
        Returns:
            NLFeatureGenerationResult with questions
            
        Example output questions:
            - "Calculate soc2_raw_impact by combining environment weight (0.4 for prod),
               bastion access multiplier (1.5 if true), and internet exposure weight
               (0.3 if exposed) using dev_assets and asset_control_evidence_features.
               This feature measures the potential impact of a security incident for SOC2 CC6.1.
               Dependencies: asset_environment, is_bastion_host, is_internet_exposed.
               Output type: float 0-1."
        """
        return await self.nl_feature_agent.generate_nl_questions(
            lane_type=lane_type,
            domain=domain,
            compliance_frameworks=compliance_frameworks,
            user_goal=user_goal,
            lane_inputs=lane_inputs,
            lane_outputs=lane_outputs,
            research_context=research_context
        )
    
    def _enhance_knowledge_with_research(
        self,
        knowledge_context: KnowledgeContext,
        research_context: LaneResearchContext
    ) -> KnowledgeContext:
        """Enhance knowledge context with deep research insights"""
        # Add feature templates as hints
        knowledge_context.feature_generation_hints = research_context.feature_templates
        
        # Add quality guidelines
        knowledge_context.quality_guidelines = research_context.quality_criteria
        
        # Add deep research context
        knowledge_context.deep_research_context = {
            "insights": research_context.research_insights,
            "recommended_features": research_context.recommended_features,
            "calculation_patterns": research_context.calculation_patterns,
            "control_mappings": research_context.control_mappings,
        }
        
        return knowledge_context
    
    async def _load_schemas(
        self,
        fe_state: FeatureEngineeringState,
        lane_definition: Any
    ) -> FeatureEngineeringState:
        """Load schemas for the lane"""
        if not self.retrieval_helper:
            return fe_state
        
        try:
            project_id = fe_state.get("project_id", "")
            inputs = lane_definition.inputs if hasattr(lane_definition, 'inputs') else []
            outputs = lane_definition.outputs if hasattr(lane_definition, 'outputs') else []
            
            all_tables = list(set(inputs + outputs))
            
            if all_tables:
                schema_result = await self.retrieval_helper.get_database_schemas(
                    project_id=project_id,
                    table_retrieval={
                        "table_retrieval_size": len(all_tables) + 5,
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": False
                    },
                    query=f"Tables: {', '.join(all_tables[:10])}",
                    tables=all_tables
                )
                
                # Build schema registry
                schema_registry = {}
                for schema in schema_result.get("schemas", []):
                    if isinstance(schema, dict):
                        table_name = schema.get("table_name", "")
                        if table_name:
                            schema_registry[table_name] = {
                                "table_ddl": schema.get("table_ddl", ""),
                                "column_metadata": schema.get("column_metadata", []),
                            }
                
                fe_state["schema_registry"] = schema_registry
                fe_state["relevant_schemas"] = list(schema_registry.keys())
                
        except Exception as e:
            logger.warning(f"Error loading schemas: {e}")
        
        return fe_state
    
    def _build_reasoning(
        self,
        fe_state: FeatureEngineeringState,
        config: LaneAgentConfig,
        research_context: Optional[LaneResearchContext] = None
    ) -> str:
        """Build reasoning explanation from feature state and research context"""
        parts = []
        
        parts.append(f"Lane type: {config.lane_type.value}")
        parts.append(f"Agents used: {', '.join(config.primary_agents)}")
        
        # Add deep research insights if available
        if research_context and research_context.research_insights:
            insights = research_context.research_insights
            if insights.get("key_features"):
                parts.append(f"Research identified {len(insights['key_features'])} key features")
            if insights.get("calculation_approaches"):
                parts.append(f"Research provided {len(insights['calculation_approaches'])} calculation approaches")
        
        recommended = fe_state.get("recommended_features", [])
        if recommended:
            parts.append(f"Generated {len(recommended)} recommended features")
        
        impact = fe_state.get("impact_features", [])
        if impact:
            parts.append(f"Generated {len(impact)} impact features")
        
        likelihood = fe_state.get("likelihood_features", [])
        if likelihood:
            parts.append(f"Generated {len(likelihood)} likelihood features")
        
        risk = fe_state.get("risk_features", [])
        if risk:
            parts.append(f"Generated {len(risk)} risk features")
        
        controls = fe_state.get("identified_controls")
        if controls:
            parts.append(f"Identified {len(controls)} compliance controls")
        
        # Add quality criteria applied
        if research_context and research_context.quality_criteria:
            criteria = research_context.quality_criteria
            if criteria.get("medallion_layer"):
                parts.append(f"Quality: {criteria['medallion_layer']}-layer only")
            if criteria.get("aggregation_level"):
                parts.append(f"Aggregation: {criteria['aggregation_level']}")
        
        return "\n".join(parts)


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_lane_feature_executor(
    llm: Optional[BaseChatModel] = None,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None,
    model_name: str = "gpt-4o",
    use_deep_research: bool = True
) -> LaneFeatureExecutor:
    """
    Factory function to create a LaneFeatureExecutor.
    
    Args:
        llm: Optional LLM instance (created if not provided)
        retrieval_helper: Optional retrieval helper
        domain_config: Optional domain configuration
        model_name: Model name if creating LLM
        use_deep_research: Whether to use deep research for richer context
        
    Returns:
        LaneFeatureExecutor instance
    """
    if llm is None:
        llm = ChatOpenAI(model=model_name, temperature=0.2)
    
    return LaneFeatureExecutor(
        llm=llm,
        retrieval_helper=retrieval_helper,
        domain_config=domain_config,
        use_deep_research=use_deep_research
    )
