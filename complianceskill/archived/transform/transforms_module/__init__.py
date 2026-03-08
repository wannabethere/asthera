"""
Transforms (Agentic Silver) assistant.

Human-in-the-loop LangGraph for feature-generation chat:
- User sets a goal -> playbook suggestion + source categories (dummy store)
- Wait for user to select playbook and source topics
- Respond with QA summary of what can be accomplished.

Designed for eventual integration with transform agents (playbook_driven_transform_agent, etc.).
"""
from app.agents.transform.transforms_module.state import TransformsAssistantState
from app.agents.transform.transforms_module.store import (
    list_playbooks_for_goal,
    list_source_categories,
    get_playbook,
    get_source_category,
    PLAYBOOK_STORE,
    SOURCE_CATEGORIES_STORE,
    AVAILABLE_FEATURE_BUCKETS,
    EXTERNAL_EXAMPLES_FOR_BUCKETS,
    get_external_examples_for_buckets,
    SOC2_FEATURE_PROCESSING_INSTRUCTIONS,
    COMPLIANCE_FRAMEWORK_FEATURE_INSTRUCTIONS,
    get_compliance_feature_instructions,
    DEFAULT_SELECTED_SOURCES,
    DEFAULT_COMPLIANCE_FRAMEWORK,
    fetch_data_models_from_vector_store,
)
from app.agents.transform.transforms_module.nodes import (
    IntentAndPlaybookNode,
    PlaybookSuggestionNode,
    SourceCategoriesNode,
    IdentifyFeatureBucketsNode,
    FetchDataModelsNode,
    ProcessSelectionQANode,
    BuildFeaturesNode,
    StructuredGraphNode,
    ProcessBuildQANode,
)
from app.agents.transform.transforms_module.graph_builder import (
    build_transforms_graph,
    create_transforms_graph,
)
from app.agents.transform.transforms_module.memory import (
    get_transforms_config,
    create_default_checkpointer,
    get_checkpointer,
)
from app.agents.transform.transforms_module.lane_feature_integration import (
    LaneType,
    LaneFeatureExecutor,
    create_lane_feature_executor,
    get_lane_agent_config,
    playbook_to_feature_state,
    feature_to_playbook_state,
    LANE_AGENT_CONFIGS,
)

__all__ = [
    "TransformsAssistantState",
    "list_playbooks_for_goal",
    "list_source_categories",
    "get_playbook",
    "get_source_category",
    "PLAYBOOK_STORE",
    "SOURCE_CATEGORIES_STORE",
    "IntentAndPlaybookNode",
    "PlaybookSuggestionNode",
    "SourceCategoriesNode",
    "IdentifyFeatureBucketsNode",
    "FetchDataModelsNode",
    "ProcessSelectionQANode",
    "BuildFeaturesNode",
    "StructuredGraphNode",
    "ProcessBuildQANode",
    "AVAILABLE_FEATURE_BUCKETS",
    "DEFAULT_SELECTED_SOURCES",
    "DEFAULT_COMPLIANCE_FRAMEWORK",
    "fetch_data_models_from_vector_store",
    "EXTERNAL_EXAMPLES_FOR_BUCKETS",
    "get_external_examples_for_buckets",
    "SOC2_FEATURE_PROCESSING_INSTRUCTIONS",
    "COMPLIANCE_FRAMEWORK_FEATURE_INSTRUCTIONS",
    "get_compliance_feature_instructions",
    "build_transforms_graph",
    "create_transforms_graph",
    "get_transforms_config",
    "create_default_checkpointer",
    "get_checkpointer",
    "LaneType",
    "LaneFeatureExecutor",
    "create_lane_feature_executor",
    "get_lane_agent_config",
    "playbook_to_feature_state",
    "feature_to_playbook_state",
    "LANE_AGENT_CONFIGS",
]
