"""
Datasource Scoping Node - Shared for Compliance and DT

Collects selected_data_sources as a multi-select SCOPING turn. This is the single field that gates
product capability scoring, MDL schema retrieval, and Qdrant product_capabilities lookup.
It is always required — there is no skip condition.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType, TurnQuestion
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import should_skip_node, create_checkpoint

logger = logging.getLogger(__name__)


def datasource_scoping_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Datasource scoping node - collects selected_data_sources.
    
    State reads: selected_data_sources (if pre-populated from tenant profile API)
    Skip condition: selected_data_sources is already non-empty AND api_context.datasources_confirmed=True.
    
    State writes: checkpoint with SCOPING turn. Multi-select chips from config.datasource_options.
    resume_with_field: selected_data_sources (list of tool ids)
    
    Note for DT: selected_data_sources feeds directly into dt_metrics_retrieval_node product capability
    query and dt_mdl_schema_retrieval_node schema lookup. Empty list = generic output.
    """
    # Skip if datasources are pre-confirmed
    if should_skip_node(state, config, "selected_data_sources", "datasources_confirmed"):
        logger.info(f"Datasources pre-confirmed: {state.get('selected_data_sources')}, skipping")
        return state
    
    # Build multi-select question
    question = TurnQuestion(
        id="datasource_select",
        label="Which security tools are you using?",
        interaction_mode="multi",
        options=[
            {"id": opt["id"], "label": opt["label"]}
            for opt in config.datasource_options
        ],
        state_key="selected_data_sources",
        required=True,
    )
    
    turn = ConversationTurn(
        phase="datasource_scoping",
        turn_type=TurnOutputType.SCOPING,
        message="Which security tools should I use for this analysis?",
        questions=[question],
    )
    
    state = create_checkpoint(state, config, "datasource_scoping", turn, "selected_data_sources")
    
    logger.info("Datasource scoping checkpoint created")
    
    return state
