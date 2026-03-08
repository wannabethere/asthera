"""
Graph Builder for Compliance Assistant (own implementation).

Flow: intent -> query_plan -> compliance_retrieval (policy agent) -> [optional deep_research] -> compliance_qa -> writer -> finalize.
When deep_research_config is set and skip_deep_research is False, runs URL-based deep research (compliance goal) before QA.
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.assistants.nodes import (
    IntentUnderstandingNode,
    WriterAgentNode,
    FinalizeNode,
)
from app.assistants.compliance_assistance_nodes import (
    ComplianceRetrievalNode,
    ComplianceQANode,
)
from app.assistants.query_plan_node import QueryPlanNode
from app.assistants.intent_planner_node import IntentPlannerNode
from app.assistants.state import ContextualAssistantState

logger = logging.getLogger(__name__)


class ComplianceAssistanceGraphBuilder:
    """Builder for compliance assistant graph: plan, policy retrieval, optional deep research (compliance goal), then QA."""

    def __init__(
        self,
        policy_retrieval_agent: Any,
        graph_registry: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        framework: str = "SOC2",
        assistant_type: str = "compliance_assistant",
        deep_research_config: Optional[Any] = None,
        retrieval_helper: Optional[Any] = None,
        contextual_data_retrieval_agent: Optional[Any] = None,
    ):
        self.policy_retrieval_agent = policy_retrieval_agent
        self.graph_registry = graph_registry
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.model_name = model_name
        self.framework = framework
        self.assistant_type = assistant_type
        self.deep_research_config = deep_research_config
        self.retrieval_helper = retrieval_helper
        self.contextual_data_retrieval_agent = contextual_data_retrieval_agent

        self.intent_node = IntentUnderstandingNode(
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
        )
        self.intent_planner_node = IntentPlannerNode(
            assistant_type=assistant_type,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
        )
        self.query_plan_node = QueryPlanNode(
            assistant_type=assistant_type,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            include_examples=True,
        )
        self.compliance_retrieval_node = ComplianceRetrievalNode(
            policy_retrieval_agent=policy_retrieval_agent,
            llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2),
            model_name="gpt-4o-mini",
            framework=framework,
            contextual_data_retrieval_agent=contextual_data_retrieval_agent,
            retrieval_helper=retrieval_helper,
        )
        self.compliance_qa_node = ComplianceQANode(
            llm=self.llm,
            model_name=model_name,
        )
        self.writer_node = WriterAgentNode(
            llm=self.llm,
            model_name=model_name,
        )
        self.finalize_node = FinalizeNode()

        self.deep_research_node = None
        if deep_research_config:
            from app.assistants.deep_research_integration_node import DeepResearchIntegrationNode
            from app.utils.deep_research_utility import DeepResearchUtility
            dr_utility = DeepResearchUtility(llm=llm, model_name=model_name)
            self.deep_research_node = DeepResearchIntegrationNode(
                contextual_graph_storage=None,
                deep_research_config=deep_research_config,
                deep_research_utility=dr_utility,
                llm=llm,
                model_name=model_name,
            )

    def _route_after_compliance_retrieval(self, state: ContextualAssistantState) -> str:
        """Route to deep_research when config is set and not skip_deep_research; else compliance_qa."""
        if not self.deep_research_node:
            return "compliance_qa"
        skip = state.get("skip_deep_research", False)
        if skip:
            logger.info("ComplianceAssistanceGraphBuilder: Skipping deep research")
            return "compliance_qa"
        return "deep_research_integration"

    def build_graph(self, use_checkpointing: bool = True):
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver

        workflow = StateGraph(ContextualAssistantState)

        workflow.add_node("intent_understanding", self.intent_node)
        workflow.add_node("intent_planner", self.intent_planner_node)
        workflow.add_node("query_planning", self.query_plan_node)  # node name must not equal state key "query_plan"
        workflow.add_node("compliance_retrieval", self.compliance_retrieval_node)
        workflow.add_node("compliance_qa", self.compliance_qa_node)
        workflow.add_node("writer_agent", self.writer_node)
        workflow.add_node("finalize", self.finalize_node)

        if self.deep_research_node:
            workflow.add_node("deep_research_integration", self.deep_research_node)

        workflow.set_entry_point("intent_understanding")
        workflow.add_edge("intent_understanding", "intent_planner")
        workflow.add_edge("intent_planner", "query_planning")
        workflow.add_edge("query_planning", "compliance_retrieval")

        if self.deep_research_node:
            workflow.add_conditional_edges(
                "compliance_retrieval",
                self._route_after_compliance_retrieval,
                {"compliance_qa": "compliance_qa", "deep_research_integration": "deep_research_integration"},
            )
            workflow.add_edge("deep_research_integration", "compliance_qa")
        else:
            workflow.add_edge("compliance_retrieval", "compliance_qa")

        workflow.add_edge("compliance_qa", "writer_agent")
        workflow.add_edge("writer_agent", "finalize")
        workflow.add_edge("finalize", END)

        if use_checkpointing:
            checkpointer = MemorySaver()
            return workflow.compile(checkpointer=checkpointer)
        return workflow.compile()


def create_compliance_assistance_graph(
    policy_retrieval_agent: Any,
    graph_registry: Any = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    use_checkpointing: bool = True,
    framework: str = "SOC2",
    deep_research_config: Optional[Any] = None,
    retrieval_helper: Optional[Any] = None,
    contextual_data_retrieval_agent: Optional[Any] = None,
):
    """Create and return the compliance assistance graph (policy retrieval; optional deep research; optional table retrieval when intent includes table_related)."""
    builder = ComplianceAssistanceGraphBuilder(
        policy_retrieval_agent=policy_retrieval_agent,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name,
        framework=framework,
        deep_research_config=deep_research_config,
        retrieval_helper=retrieval_helper,
        contextual_data_retrieval_agent=contextual_data_retrieval_agent,
    )
    return builder.build_graph(use_checkpointing=use_checkpointing)
