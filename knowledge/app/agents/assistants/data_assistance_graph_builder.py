"""
Graph Builder for Data Assistance Assistant

Extends the ContextualAssistantGraphBuilder framework to add data assistance capabilities:
- Retrieves schemas, metrics, and controls
- Generates new metrics based on schema definitions
- Answers questions about metrics for compliance controls
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from .graph_builder import ContextualAssistantGraphBuilder
from .data_assistance_nodes import (
    DataKnowledgeRetrievalNode,
    MetricGenerationNode,
    DataAssistanceQANode
)

logger = logging.getLogger(__name__)


class DataAssistanceGraphBuilder(ContextualAssistantGraphBuilder):
    """Builder for data assistance assistant graphs - extends the framework"""
    
    def __init__(
        self,
        retrieval_helper: Any,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        graph_registry: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        """
        Initialize the data assistance graph builder
        
        Args:
            retrieval_helper: RetrievalHelper instance for schema/metric retrieval
            contextual_graph_service: ContextualGraphService for control retrieval
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance (from framework)
            reasoning_pipeline: ContextualGraphReasoningPipeline instance (from framework)
            graph_registry: Optional GraphRegistry for sub-graph routing
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        # Store data assistance specific components first
        self.retrieval_helper = retrieval_helper
        
        # Initialize parent class with required framework components
        super().__init__(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            graph_registry=graph_registry,
            llm=llm,
            model_name=model_name
        )
        
        # Override context_node to include retrieval_helper for schema-aware reasoning plans
        from .nodes import ContextRetrievalNode
        self.context_node = ContextRetrievalNode(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            retrieval_helper=retrieval_helper  # Pass retrieval_helper for schema retrieval
        )
        
        # Override/add data assistance specific nodes
        self.data_knowledge_node = DataKnowledgeRetrievalNode(
            retrieval_helper=retrieval_helper,
            contextual_graph_service=contextual_graph_service,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        )
        self.metric_generation_node = MetricGenerationNode(
            llm=self.llm,
            model_name=model_name
        )
        self.data_assistance_qa_node = DataAssistanceQANode(
            llm=self.llm,
            model_name=model_name
        )
    
    def build_graph(self, use_checkpointing: bool = True):
        """
        Build the data assistance assistant graph using the framework
        
        Overrides parent to add data assistance specific nodes while maintaining
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
        workflow.add_node("retrieve_context", self.context_node)  # Framework context retrieval
        workflow.add_node("contextual_reasoning", self.reasoning_node)  # Framework reasoning
        
        # Add data assistance specific nodes
        workflow.add_node("data_knowledge_retrieval", self.data_knowledge_node)
        workflow.add_node("metric_generation", self.metric_generation_node)
        
        # Add Q&A nodes (data assistance specific overrides framework Q&A)
        workflow.add_node("qa_agent", self.data_assistance_qa_node)
        workflow.add_node("executor", self.executor_node)  # Framework executor
        workflow.add_node("writer_agent", self.writer_node)  # Framework writer
        if self.router_node:
            workflow.add_node("route_to_graph", self.router_node)
        workflow.add_node("finalize", self.finalize_node)  # Framework finalize
        
        # Set entry point
        workflow.set_entry_point("intent_understanding")
        
        # Framework routing: intent -> context retrieval
        workflow.add_edge("intent_understanding", "retrieve_context")
        
        # After context retrieval, go to contextual reasoning to suggest relevant tables
        # This allows the contextual assistant to suggest the most relevant tables
        # before we retrieve actual data tables
        workflow.add_edge("retrieve_context", "contextual_reasoning")
        
        # After contextual reasoning suggests tables, retrieve data knowledge using those suggestions
        workflow.add_edge("contextual_reasoning", "data_knowledge_retrieval")
        
        # Data knowledge retrieval -> metric generation
        workflow.add_edge("data_knowledge_retrieval", "metric_generation")
        
        # Framework routing: reasoning -> Q&A or Executor based on intent
        workflow.add_conditional_edges(
            "contextual_reasoning",
            self._route_after_reasoning,
            {
                "qa": "qa_agent",  # Uses data assistance Q&A node
                "executor": "executor",
                "finalize": "finalize"
            }
        )
        
        # Framework routing: Q&A and Executor -> Writer
        workflow.add_edge("qa_agent", "writer_agent")
        workflow.add_edge("executor", "writer_agent")
        
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


def create_data_assistance_graph(
    retrieval_helper: Any,
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    graph_registry: Any = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    use_checkpointing: bool = True
):
    """
    Factory function to create a data assistance assistant graph using the framework
    
    Args:
        retrieval_helper: RetrievalHelper instance for schema/metric retrieval
        contextual_graph_service: ContextualGraphService for control retrieval
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
        reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
        graph_registry: Optional GraphRegistry for sub-graph routing
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        use_checkpointing: Whether to use checkpointing
        
    Returns:
        Compiled StateGraph with framework features (state management, memory, etc.)
    """
    builder = DataAssistanceGraphBuilder(
        retrieval_helper=retrieval_helper,
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name
    )
    return builder.build_graph(use_checkpointing=use_checkpointing)

