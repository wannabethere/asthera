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

Workforce Assistants:
- Product Assistant for product documentation and APIs
- Compliance Assistant for frameworks and controls
- Domain Knowledge Assistant for concepts and best practices
"""
from app.assistants.state import ContextualAssistantState
from app.assistants.actor_types import (
    ActorType,
    ACTOR_TYPE_CONFIGS,
    get_actor_config,
    get_actor_prompt_context
)
from app.assistants.nodes import (
    IntentUnderstandingNode,
    ContextRetrievalNode,
    ContextualReasoningNode,
    QAAgentNode,
    ExecutorNode,
    WriterAgentNode,
    GraphRouterNode,
    FinalizeNode
)
from app.assistants.graph_builder import (
    ContextualAssistantGraphBuilder,
    create_contextual_assistant_graph
)
from app.assistants.factory import (
    ContextualAssistantFactory,
    create_contextual_assistant_factory
)
from app.assistants.data_assistance_nodes import (
    DataKnowledgeRetrievalNode,
    MetricGenerationNode,
    DataAssistanceQANode
)
from app.assistants.data_assistance_graph_builder import (
    DataAssistanceGraphBuilder,
    create_data_assistance_graph
)
from app.assistants.data_assistance_factory import (
    DataAssistanceFactory,
    create_data_assistance_factory
)
from app.assistants.knowledge_assistance_nodes import (
    KnowledgeRetrievalNode,
    KnowledgeQANode
)
from app.assistants.knowledge_assistance_graph_builder import (
    KnowledgeAssistanceGraphBuilder,
    create_knowledge_assistance_graph
)
from app.assistants.knowledge_assistance_factory import (
    KnowledgeAssistanceFactory,
    create_knowledge_assistance_factory
)
from app.config.workforce_config import (
    AssistantType,
    AssistantConfig,
    DataSourceConfig,
    get_assistant_config,
    list_assistant_types
)
from app.assistants.workforce_assistants import (
    WorkforceAssistant,
    create_product_assistant,
    create_compliance_assistant,
    create_domain_knowledge_assistant
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
    
    # Workforce Assistants
    "AssistantType",
    "AssistantConfig",
    "DataSourceConfig",
    "get_assistant_config",
    "list_assistant_types",
    "WorkforceAssistant",
    "create_product_assistant",
    "create_compliance_assistant",
    "create_domain_knowledge_assistant",
]

