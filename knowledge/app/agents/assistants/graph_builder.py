"""
Graph Builder for Contextual Assistants

Builds LangGraph workflows for contextual assistants that use:
- Contextual graph reasoning pipelines
- Actor types for personalized responses
- Q&A and writing capabilities
- Integration with streaming service
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import ContextualAssistantState
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

logger = logging.getLogger(__name__)


class ContextualAssistantGraphBuilder:
    """Builder for contextual assistant graphs"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        graph_registry: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        """
        Initialize the graph builder
        
        Args:
            contextual_graph_service: ContextualGraphService instance
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance
            reasoning_pipeline: ContextualGraphReasoningPipeline instance
            graph_registry: Optional GraphRegistry for sub-graph routing
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.contextual_graph_service = contextual_graph_service
        self.retrieval_pipeline = retrieval_pipeline
        self.reasoning_pipeline = reasoning_pipeline
        self.graph_registry = graph_registry
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        
        # Initialize nodes
        self.intent_node = IntentUnderstandingNode(
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        )
        self.context_node = ContextRetrievalNode(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        )
        self.reasoning_node = ContextualReasoningNode(
            reasoning_pipeline=reasoning_pipeline,
            llm=self.llm
        )
        self.qa_node = QAAgentNode(
            llm=self.llm,
            model_name=model_name
        )
        self.executor_node = ExecutorNode(
            llm=self.llm,
            model_name=model_name
        )
        self.writer_node = WriterAgentNode(
            llm=self.llm,
            model_name=model_name
        )
        self.router_node = GraphRouterNode(
            graph_registry=graph_registry,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        ) if graph_registry else None
        self.finalize_node = FinalizeNode()
    
    def build_graph(self, use_checkpointing: bool = True) -> StateGraph:
        """
        Build the contextual assistant graph
        
        Args:
            use_checkpointing: Whether to use checkpointing for state persistence
            
        Returns:
            Compiled StateGraph
        """
        # Create graph
        workflow = StateGraph(ContextualAssistantState)
        
        # Add nodes
        workflow.add_node("intent_understanding", self.intent_node)
        workflow.add_node("retrieve_context", self.context_node)
        workflow.add_node("contextual_reasoning", self.reasoning_node)
        workflow.add_node("qa_agent", self.qa_node)
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("writer_agent", self.writer_node)
        if self.router_node:
            workflow.add_node("route_to_graph", self.router_node)
        workflow.add_node("finalize", self.finalize_node)
        
        # Set entry point
        workflow.set_entry_point("intent_understanding")
        
        # Add edges
        workflow.add_edge("intent_understanding", "retrieve_context")
        workflow.add_edge("retrieve_context", "contextual_reasoning")
        
        # Conditional routing from reasoning: Q&A vs Executor based on intent
        workflow.add_conditional_edges(
            "contextual_reasoning",
            self._route_after_reasoning,
            {
                "qa": "qa_agent",
                "executor": "executor",
                "finalize": "finalize"
            }
        )
        
        # Both Q&A and Executor route to writer (writer decides what to do)
        workflow.add_edge("qa_agent", "writer_agent")
        workflow.add_edge("executor", "writer_agent")
        
        # Writer agent always goes to finalize
        workflow.add_edge("writer_agent", "finalize")
        
        # Router (if available)
        if self.router_node:
            workflow.add_edge("route_to_graph", "retrieve_context")  # After graph, continue
        
        # Finalize always ends
        workflow.add_edge("finalize", END)
        
        # Compile with optional checkpointing
        if use_checkpointing:
            checkpointer = MemorySaver()
            return workflow.compile(checkpointer=checkpointer)
        else:
            return workflow.compile()
    
    def _route_after_reasoning(self, state: ContextualAssistantState) -> str:
        """Route after contextual reasoning: Q&A vs Executor based on intent"""
        intent = state.get("intent", "general")
        
        # Route to executor if intent is execution
        if intent == "execution":
            return "executor"
        # Route to Q&A for questions, analysis, or general queries
        elif intent in ["question", "analysis", "general"]:
            return "qa"
        # Fallback to Q&A
        else:
            return "qa"


def create_contextual_assistant_graph(
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    graph_registry: Any = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    use_checkpointing: bool = True
) -> StateGraph:
    """
    Factory function to create a contextual assistant graph
    
    Args:
        contextual_graph_service: ContextualGraphService instance
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance
        reasoning_pipeline: ContextualGraphReasoningPipeline instance
        graph_registry: Optional GraphRegistry for sub-graph routing
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        use_checkpointing: Whether to use checkpointing
        
    Returns:
        Compiled StateGraph
    """
    builder = ContextualAssistantGraphBuilder(
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name
    )
    return builder.build_graph(use_checkpointing=use_checkpointing)

