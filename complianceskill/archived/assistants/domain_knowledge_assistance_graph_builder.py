"""
Graph Builder for Domain Knowledge Assistant (same pattern as product/compliance).

Flow: intent -> query_plan (breakdown) -> retrieve_context -> contextual_reasoning
-> domain_knowledge_retrieval -> qa_agent -> writer -> finalize.
Uses general_prompts for plan; then executes retrieval (domain_knowledge, entities, compliance_controls).
"""
import logging
from typing import Optional, Any
from langchain_openai import ChatOpenAI

from app.assistants.graph_builder import ContextualAssistantGraphBuilder
from app.assistants.domain_knowledge_assistance_nodes import (
    DomainKnowledgeRetrievalNode,
    DomainKnowledgeQANode,
)
from app.assistants.query_plan_node import QueryPlanNode
from app.assistants.intent_planner_node import IntentPlannerNode
from app.storage.query.collection_factory import CollectionFactory

logger = logging.getLogger(__name__)


class DomainKnowledgeAssistanceGraphBuilder(ContextualAssistantGraphBuilder):
    """Builder for domain knowledge assistant graph: plan first (general_prompts), then domain retrieval."""

    def __init__(
        self,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        collection_factory: Optional[CollectionFactory] = None,
        graph_registry: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        assistant_type: str = "domain_knowledge_assistant",
    ):
        super().__init__(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            graph_registry=graph_registry,
            llm=llm,
            model_name=model_name,
        )
        self.collection_factory = collection_factory
        self.assistant_type = assistant_type
        self.intent_planner_node = IntentPlannerNode(
            assistant_type=assistant_type,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
        )
        self.query_plan_node = QueryPlanNode(
            assistant_type=assistant_type,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            include_examples=True,
        )
        self.domain_knowledge_retrieval_node = DomainKnowledgeRetrievalNode(
            collection_factory=collection_factory,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            top_k=10,
        )
        self.domain_knowledge_qa_node = DomainKnowledgeQANode(llm=self.llm, model_name=model_name)

    def build_graph(self, use_checkpointing: bool = True):
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from .state import ContextualAssistantState

        workflow = StateGraph(ContextualAssistantState)
        workflow.add_node("intent_understanding", self.intent_node)
        workflow.add_node("intent_planner", self.intent_planner_node)
        workflow.add_node("query_planning", self.query_plan_node)  # node name must not equal state key "query_plan"
        workflow.add_node("retrieve_context", self.context_node)
        workflow.add_node("contextual_reasoning", self.reasoning_node)
        workflow.add_node("domain_knowledge_retrieval", self.domain_knowledge_retrieval_node)
        workflow.add_node("qa_agent", self.domain_knowledge_qa_node)
        workflow.add_node("writer_agent", self.writer_node)
        if self.router_node:
            workflow.add_node("route_to_graph", self.router_node)
        workflow.add_node("finalize", self.finalize_node)

        workflow.set_entry_point("intent_understanding")
        workflow.add_edge("intent_understanding", "intent_planner")
        workflow.add_edge("intent_planner", "query_planning")
        workflow.add_edge("query_planning", "retrieve_context")
        workflow.add_edge("retrieve_context", "contextual_reasoning")
        workflow.add_edge("contextual_reasoning", "domain_knowledge_retrieval")
        workflow.add_edge("domain_knowledge_retrieval", "qa_agent")
        workflow.add_edge("qa_agent", "writer_agent")
        workflow.add_edge("writer_agent", "finalize")
        workflow.add_edge("finalize", END)

        if use_checkpointing:
            return workflow.compile(checkpointer=MemorySaver())
        return workflow.compile()


def create_domain_knowledge_assistance_graph(
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    collection_factory: Optional[CollectionFactory] = None,
    graph_registry: Any = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    use_checkpointing: bool = True,
):
    """Create domain knowledge assistance graph (plan then execute, same as product/compliance)."""
    builder = DomainKnowledgeAssistanceGraphBuilder(
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        collection_factory=collection_factory,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name,
        assistant_type="domain_knowledge_assistant",
    )
    return builder.build_graph(use_checkpointing=use_checkpointing)
