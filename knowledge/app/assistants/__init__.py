"""
Contextual Assistants

LangGraph-based assistants that use contextual graph reasoning
to provide context-aware answers and content generation.

Key Features:
- Context-aware reasoning using contextual graphs
- Actor types for personalized responses
- Q&A and writing capabilities
- Integration with streaming service
- Pipeline-based context retrieval and reasoning
"""
from .state import ContextualAssistantState
from .actor_types import (
    ActorType,
    ACTOR_TYPE_CONFIGS,
    get_actor_config,
    get_actor_prompt_context
)
from .nodes import (
    IntentUnderstandingNode,
    ContextRetrievalNode,
    ContextualReasoningNode,
    QAAgentNode,
    ExecutorNode,
    WriterAgentNode,
    GraphRouterNode,
    FinalizeNode
)
from .graph_builder import (
    ContextualAssistantGraphBuilder,
    create_contextual_assistant_graph
)
from .factory import (
    ContextualAssistantFactory,
    create_contextual_assistant_factory
)
from .data_assistance_nodes import (
    DataKnowledgeRetrievalNode,
    MetricGenerationNode,
    DataAssistanceQANode
)
from .data_assistance_graph_builder import (
    DataAssistanceGraphBuilder,
    create_data_assistance_graph
)
from .data_assistance_factory import (
    DataAssistanceFactory,
    create_data_assistance_factory
)
from .knowledge_assistance_nodes import (
    KnowledgeRetrievalNode,
    KnowledgeQANode
)
from .knowledge_assistance_graph_builder import (
    KnowledgeAssistanceGraphBuilder,
    create_knowledge_assistance_graph
)
from .knowledge_assistance_factory import (
    KnowledgeAssistanceFactory,
    create_knowledge_assistance_factory
)

__all__ = [
    # State
    "ContextualAssistantState",
    
    # Actor Types
    "ActorType",
    "ACTOR_TYPE_CONFIGS",
    "get_actor_config",
    "get_actor_prompt_context",
    
    # Nodes
    "IntentUnderstandingNode",
    "ContextRetrievalNode",
    "ContextualReasoningNode",
    "QAAgentNode",
    "ExecutorNode",
    "WriterAgentNode",
    "GraphRouterNode",
    "FinalizeNode",
    
    # Graph Builder
    "ContextualAssistantGraphBuilder",
    "create_contextual_assistant_graph",
    
    # Factory
    "ContextualAssistantFactory",
    "create_contextual_assistant_factory",
    
    # Data Assistance Nodes
    "DataKnowledgeRetrievalNode",
    "MetricGenerationNode",
    "DataAssistanceQANode",
    
    # Data Assistance Graph Builder
    "DataAssistanceGraphBuilder",
    "create_data_assistance_graph",
    
    # Data Assistance Factory
    "DataAssistanceFactory",
    "create_data_assistance_factory",
    
    # Knowledge Assistance Nodes
    "KnowledgeRetrievalNode",
    "KnowledgeQANode",
    
    # Knowledge Assistance Graph Builder
    "KnowledgeAssistanceGraphBuilder",
    "create_knowledge_assistance_graph",
    
    # Knowledge Assistance Factory
    "KnowledgeAssistanceFactory",
    "create_knowledge_assistance_factory",
]

