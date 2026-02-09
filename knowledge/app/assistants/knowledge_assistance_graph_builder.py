"""
Graph Builder for Knowledge Assistance Assistant

Extends the ContextualAssistantGraphBuilder framework to add knowledge assistance capabilities:
- Retrieves SOC2 compliance controls
- Retrieves risks associated with controls
- Retrieves measures/effectiveness for controls
- Presents knowledge as markdown without aggregation or consolidation
- Optional MDL retrieval step to add related tables for the given product(s)
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.assistants.graph_builder import ContextualAssistantGraphBuilder
from app.assistants.knowledge_assistance_nodes import (
    KnowledgeRetrievalNode,
    KnowledgeQANode
)
from app.assistants.query_plan_node import QueryPlanNode
from app.assistants.intent_planner_node import IntentPlannerNode
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory

logger = logging.getLogger(__name__)


class KnowledgeAssistanceGraphBuilder(ContextualAssistantGraphBuilder):
    """Builder for knowledge assistance assistant graphs - extends the framework"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        graph_registry: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        framework: str = "SOC2",
        contextual_graph_storage: Optional[ContextualGraphStorage] = None,
        collection_factory: Optional[CollectionFactory] = None
    ):
        """
        Initialize the knowledge assistance graph builder
        
        Args:
            contextual_graph_service: ContextualGraphService for control retrieval
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance (from framework)
            reasoning_pipeline: ContextualGraphReasoningPipeline instance (from framework)
            graph_registry: Optional GraphRegistry for sub-graph routing
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            framework: Compliance framework (default: SOC2)
            contextual_graph_storage: Optional for MDL retrieval (related tables for product(s))
            collection_factory: Optional for MDL retrieval (related tables for product(s))
        """
        # Initialize parent class with required framework components
        super().__init__(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            graph_registry=graph_registry,
            llm=llm,
            model_name=model_name
        )
        
        # Optional MDL retrieval step - add related tables for the product(s) the user is retrieving
        if contextual_graph_storage and collection_factory:
            from app.assistants.mdl_reasoning_integration_node import MDLReasoningIntegrationNode
            self.mdl_reasoning_node = MDLReasoningIntegrationNode(
                contextual_graph_storage=contextual_graph_storage,
                collection_factory=collection_factory,
                retrieval_helper=None,
                llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
                model_name="gpt-4o-mini",
                assistant_type="knowledge_assistance_assistant"
            )
            logger.info("KnowledgeAssistanceGraphBuilder: MDL retrieval (related tables) enabled")
        else:
            self.mdl_reasoning_node = None
            logger.info("KnowledgeAssistanceGraphBuilder: MDL retrieval disabled (missing contextual_graph_storage/collection_factory)")

        # Intent planner then plan node (breakdown uses intent when set)
        self.intent_planner_node = IntentPlannerNode(
            assistant_type="knowledge_assistance_assistant",
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
        )
        self.query_plan_node = QueryPlanNode(
            assistant_type="knowledge_assistance_assistant",
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            include_examples=True,
        )
        
        # Override/add knowledge assistance specific nodes
        self.knowledge_retrieval_node = KnowledgeRetrievalNode(
            contextual_graph_service=contextual_graph_service,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            framework=framework
        )
        self.knowledge_qa_node = KnowledgeQANode(
            llm=self.llm,
            model_name=model_name
        )
    
    def build_graph(self, use_checkpointing: bool = True):
        """
        Build the knowledge assistance assistant graph using the framework
        
        Overrides parent to add knowledge assistance specific nodes while maintaining
        framework structure for state management, memory, and routing.
        
        Args:
            use_checkpointing: Whether to use checkpointing for state persistence
            
        Returns:
            Compiled StateGraph with framework features
        """
        # Use parent's graph creation (StateGraph with ContextualAssistantState)
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from .state import ContextualAssistantState
        
        workflow = StateGraph(ContextualAssistantState)
        
        # Add framework nodes (from parent)
        workflow.add_node("intent_understanding", self.intent_node)
        workflow.add_node("intent_planner", self.intent_planner_node)
        workflow.add_node("query_planning", self.query_plan_node)  # node name must not equal state key "query_plan"
        workflow.add_node("retrieve_context", self.context_node)  # Framework context retrieval
        if self.mdl_reasoning_node:
            workflow.add_node("mdl_reasoning_integration", self.mdl_reasoning_node)
        workflow.add_node("contextual_reasoning", self.reasoning_node)  # Framework reasoning
        
        # Add knowledge assistance specific nodes
        workflow.add_node("knowledge_retrieval", self.knowledge_retrieval_node)
        
        # Add Q&A nodes (knowledge assistance specific overrides framework Q&A)
        workflow.add_node("qa_agent", self.knowledge_qa_node)
        workflow.add_node("executor", self.executor_node)  # Framework executor
        workflow.add_node("writer_agent", self.writer_node)  # Framework writer
        if self.router_node:
            workflow.add_node("route_to_graph", self.router_node)
        workflow.add_node("finalize", self.finalize_node)  # Framework finalize
        
        # Set entry point
        workflow.set_entry_point("intent_understanding")
        
        # Framework routing: intent_understanding -> intent_planner -> query_planning (breakdown) -> context retrieval
        workflow.add_edge("intent_understanding", "intent_planner")
        workflow.add_edge("intent_planner", "query_planning")
        workflow.add_edge("query_planning", "retrieve_context")

        # After context retrieval: skip MDL for "which controls" style questions to save time
        def _route_after_retrieve_context(state: Dict[str, Any]) -> str:
            if state.get("skip_mdl_reasoning", False):
                logger.info("KnowledgeAssistanceGraphBuilder: Skipping MDL reasoning (skip_mdl_reasoning=True)")
                return "skip_mdl"
            return "mdl"

        if self.mdl_reasoning_node:
            workflow.add_conditional_edges(
                "retrieve_context",
                _route_after_retrieve_context,
                {"skip_mdl": "contextual_reasoning", "mdl": "mdl_reasoning_integration"}
            )
            workflow.add_edge("mdl_reasoning_integration", "contextual_reasoning")
        else:
            workflow.add_edge("retrieve_context", "contextual_reasoning")
        
        # After contextual reasoning, retrieve knowledge (controls, risks, measures)
        workflow.add_edge("contextual_reasoning", "knowledge_retrieval")
        
        # Knowledge retrieval -> Q&A (knowledge assistant always uses Q&A, no executor)
        workflow.add_edge("knowledge_retrieval", "qa_agent")
        
        # Framework routing: Q&A -> Writer
        workflow.add_edge("qa_agent", "writer_agent")
        
        # Framework routing: Writer -> Finalize
        workflow.add_edge("writer_agent", "finalize")
        
        # Router (if available)
        if self.router_node:
            workflow.add_edge("route_to_graph", "retrieve_context")
        
        # Finalize always ends
        workflow.add_edge("finalize", END)
        
        # Compile with framework checkpointing (from parent pattern)
        if use_checkpointing:
            checkpointer = MemorySaver()
            return workflow.compile(checkpointer=checkpointer)
        else:
            return workflow.compile()


def create_knowledge_assistance_graph(
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    graph_registry: Any = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    use_checkpointing: bool = True,
    framework: str = "SOC2",
    contextual_graph_storage: Optional[ContextualGraphStorage] = None,
    collection_factory: Optional[CollectionFactory] = None
):
    """
    Factory function to create a knowledge assistance assistant graph using the framework
    
    Args:
        contextual_graph_service: ContextualGraphService for control retrieval
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
        reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
        graph_registry: Optional GraphRegistry for sub-graph routing
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        use_checkpointing: Whether to use checkpointing
        framework: Compliance framework (default: SOC2)
        contextual_graph_storage: Optional for MDL retrieval (related tables for product(s))
        collection_factory: Optional for MDL retrieval (related tables for product(s))
        
    Returns:
        Compiled StateGraph with framework features (state management, memory, etc.)
    """
    builder = KnowledgeAssistanceGraphBuilder(
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name,
        framework=framework,
        contextual_graph_storage=contextual_graph_storage,
        collection_factory=collection_factory
    )
    return builder.build_graph(use_checkpointing=use_checkpointing)

