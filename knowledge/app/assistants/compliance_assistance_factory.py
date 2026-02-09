"""
Factory for creating and registering Compliance Assistant (own implementation).

Uses PolicyRetrievalAgent for policy/controls/risks/edges retrieval. Optional deep research (compliance goal).
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.streams.graph_registry import GraphRegistry, get_registry
from app.assistants.compliance_assistance_graph_builder import create_compliance_assistance_graph

logger = logging.getLogger(__name__)


class ComplianceAssistanceFactory:
    """Factory for creating and registering the compliance assistant (policy retrieval; optional deep research)."""

    def __init__(
        self,
        policy_retrieval_agent: Any,
        graph_registry: Optional[GraphRegistry] = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        framework: str = "SOC2",
        deep_research_config: Optional[Any] = None,
        retrieval_helper: Optional[Any] = None,
        contextual_data_retrieval_agent: Optional[Any] = None,
    ):
        self.policy_retrieval_agent = policy_retrieval_agent
        self.graph_registry = graph_registry or get_registry()
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.model_name = model_name
        self.framework = framework
        self.deep_research_config = deep_research_config
        self.retrieval_helper = retrieval_helper
        self.contextual_data_retrieval_agent = contextual_data_retrieval_agent

    def create_and_register_assistant(
        self,
        assistant_id: str,
        name: str,
        description: Optional[str] = None,
        graph_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_checkpointing: bool = True,
        set_as_default: bool = True,
        framework: Optional[str] = None,
    ) -> Any:
        try:
            self.graph_registry.register_assistant(
                assistant_id=assistant_id,
                name=name,
                description=description or f"Compliance assistant: {name}",
                metadata=metadata or {},
            )
            graph_id = graph_id or f"{assistant_id}_graph"
            framework_to_use = framework or self.framework
            graph = create_compliance_assistance_graph(
                policy_retrieval_agent=self.policy_retrieval_agent,
                graph_registry=self.graph_registry,
                llm=self.llm,
                model_name=self.model_name,
                use_checkpointing=use_checkpointing,
                framework=framework_to_use,
                deep_research_config=self.deep_research_config,
                retrieval_helper=getattr(self, "retrieval_helper", None),
                contextual_data_retrieval_agent=getattr(self, "contextual_data_retrieval_agent", None),
            )
            graph_config = self.graph_registry.register_graph(
                assistant_id=assistant_id,
                graph_id=graph_id,
                graph=graph,
                name=name,
                description=description or f"Compliance assistant graph for {name}",
                metadata={
                    "type": "compliance_assistance",
                    "model": self.model_name,
                    "use_checkpointing": use_checkpointing,
                    "framework": framework_to_use,
                    **(metadata or {}),
                },
                set_as_default=set_as_default,
            )
            logger.info(f"Created and registered compliance assistant: {assistant_id} with graph: {graph_id}")
            return graph_config
        except Exception as e:
            logger.error(f"Error creating compliance assistant {assistant_id}: {e}", exc_info=True)
            raise


def create_compliance_assistance_factory(
    policy_retrieval_agent: Any,
    graph_registry: Optional[GraphRegistry] = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    framework: str = "SOC2",
    deep_research_config: Optional[Any] = None,
    retrieval_helper: Optional[Any] = None,
    contextual_data_retrieval_agent: Optional[Any] = None,
) -> ComplianceAssistanceFactory:
    """Create a ComplianceAssistanceFactory (policy retrieval; optional deep research; optional table retrieval when question asks for tables)."""
    return ComplianceAssistanceFactory(
        policy_retrieval_agent=policy_retrieval_agent,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name,
        framework=framework,
        deep_research_config=deep_research_config,
        retrieval_helper=retrieval_helper,
        contextual_data_retrieval_agent=contextual_data_retrieval_agent,
    )
