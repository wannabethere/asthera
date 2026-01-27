"""
Specialized nodes for Knowledge Assistance Assistant

These nodes handle:
- Retrieving SOC2 compliance controls
- Retrieving risks associated with controls
- Retrieving measures/effectiveness for controls
- Presenting knowledge as markdown without aggregation or consolidation
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .state import ContextualAssistantState
from .actor_types import get_actor_config, get_actor_prompt_context

logger = logging.getLogger(__name__)


def _build_state_update(state: Dict[str, Any], required_fields: List[str], optional_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Build a state update dict with only the fields we actually updated.
    
    This prevents LangGraph conflicts when multiple nodes might update the same field.
    
    Args:
        state: The state dictionary
        required_fields: Fields that must be included (will be included even if None)
        optional_fields: Fields to include only if they're actually set (not None/empty)
        
    Returns:
        Dictionary with only the updated fields
    """
    result = {}
    for field in required_fields:
        if field in state:
            result[field] = state[field]
    
    if optional_fields:
        for field in optional_fields:
            if field in state and state[field] is not None:
                # For lists/dicts, also check if they're not empty
                value = state[field]
                if isinstance(value, (list, dict)) and len(value) == 0:
                    continue
                result[field] = value
    
    return result


class KnowledgeRetrievalNode:
    """Node that retrieves SOC2 compliance knowledge: controls, risks, and measures"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        framework: str = "SOC2"
    ):
        self.contextual_graph_service = contextual_graph_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.framework = framework.upper()
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Retrieve SOC2 compliance knowledge: controls, risks, and measures
        
        This node retrieves knowledge without aggregation or consolidation.
        It simply gathers:
        - Controls for SOC2 compliance
        - Risks associated with controls
        - Measures/effectiveness data for controls
        
        All knowledge is stored in state for presentation as markdown.
        """
        query = state.get("query", "")
        user_context = state.get("user_context", {})
        
        # Use context_ids from framework's context retrieval (already retrieved)
        context_ids = state.get("context_ids", [])
        if not context_ids:
            # Fallback to user_context if framework didn't retrieve any
            context_ids = user_context.get("context_ids", [])
        
        if not query:
            state["status"] = "error"
            state["error"] = "No query provided"
            return state
        
        try:
            # Extract framework from query or user context (default to SOC2)
            framework = self._extract_framework(query, user_context) or self.framework
            
            # 1. Retrieve controls for SOC2
            controls = []
            if self.contextual_graph_service and context_ids:
                logger.info(f"Retrieving {framework} controls using context_ids from framework")
                try:
                    # Get controls for contexts retrieved by framework
                    for context_id in context_ids[:1]:  # Use first context
                        if context_id:
                            from app.services.models import ControlSearchRequest
                            search_request = ControlSearchRequest(
                                context_id=context_id,
                                framework=framework,
                                query=query,
                                top_k=20,  # Get more controls for knowledge
                                request_id=f"knowledge_assistance_{context_id}"
                            )
                            search_response = await self.contextual_graph_service.search_controls(search_request)
                            if search_response.success and search_response.data:
                                context_controls = search_response.data.get("controls", [])
                                controls.extend(context_controls)
                except Exception as e:
                    logger.warning(f"Error retrieving controls: {e}")
            elif self.contextual_graph_service:
                # Fallback: try to find contexts if framework didn't retrieve any
                logger.info(f"Framework didn't retrieve contexts, trying to find contexts for framework {framework}")
                try:
                    if hasattr(self.contextual_graph_service, 'query_engine'):
                        contexts = await self.contextual_graph_service.query_engine.find_relevant_contexts(
                            user_context_description=query,
                            top_k=3
                        )
                        fallback_context_ids = [ctx.get("context_id") for ctx in contexts if ctx.get("context_id")]
                        for context_id in fallback_context_ids[:1]:
                            if context_id:
                                from app.services.models import ControlSearchRequest
                                search_request = ControlSearchRequest(
                                    context_id=context_id,
                                    framework=framework,
                                    query=query,
                                    top_k=20,
                                    request_id=f"knowledge_assistance_{context_id}"
                                )
                                search_response = await self.contextual_graph_service.search_controls(search_request)
                                if search_response.success and search_response.data:
                                    context_controls = search_response.data.get("controls", [])
                                    controls.extend(context_controls)
                except Exception as e:
                    logger.warning(f"Error retrieving controls with fallback: {e}")
            
            # 2. For each control, retrieve risks, requirements, and measures
            enriched_controls = []
            for control_data in controls[:15]:  # Limit to 15 controls
                try:
                    # Extract control information
                    if isinstance(control_data, dict):
                        control_obj = control_data.get("control") or control_data
                        control_id = control_obj.get("control_id") or control_data.get("control_id")
                        
                        if not control_id:
                            continue
                        
                        enriched_control = {
                            "control_id": control_id,
                            "control_name": control_obj.get("control_name") or control_data.get("control_name", ""),
                            "control_description": control_obj.get("control_description") or control_data.get("control_description", ""),
                            "framework": framework,
                            "risks": [],
                            "requirements": [],
                            "measures": [],
                            "risk_analytics": None
                        }
                        
                        # Get requirements for this control
                        if hasattr(self.contextual_graph_service, 'requirement_service'):
                            try:
                                requirements = await self.contextual_graph_service.requirement_service.get_requirements_for_control(
                                    control_id
                                )
                                enriched_control["requirements"] = [
                                    {
                                        "requirement_id": req.requirement_id if hasattr(req, 'requirement_id') else None,
                                        "requirement_text": req.requirement_text if hasattr(req, 'requirement_text') else str(req),
                                        "requirement_type": req.requirement_type if hasattr(req, 'requirement_type') else None
                                    }
                                    for req in requirements[:10]  # Limit to 10 requirements
                                ]
                            except Exception as e:
                                logger.warning(f"Error retrieving requirements for control {control_id}: {e}")
                        
                        # Get measures/measurements for this control
                        if hasattr(self.contextual_graph_service, 'measurement_service'):
                            try:
                                # Get measurements
                                measurements = await self.contextual_graph_service.measurement_service.get_measurements_for_control(
                                    control_id=control_id,
                                    context_id=context_ids[0] if context_ids else None,
                                    days=90  # Last 90 days
                                )
                                enriched_control["measures"] = [
                                    {
                                        "measurement_id": m.measurement_id if hasattr(m, 'measurement_id') else None,
                                        "measured_value": m.measured_value if hasattr(m, 'measured_value') else None,
                                        "measurement_date": m.measurement_date.isoformat() if hasattr(m, 'measurement_date') and m.measurement_date else None,
                                        "passed": m.passed if hasattr(m, 'passed') else None,
                                        "data_source": m.data_source if hasattr(m, 'data_source') else None,
                                        "quality_score": m.quality_score if hasattr(m, 'quality_score') else None
                                    }
                                    for m in measurements[:10]  # Limit to 10 measurements
                                ]
                                
                                # Get risk analytics
                                analytics = await self.contextual_graph_service.measurement_service.get_risk_analytics(
                                    control_id
                                )
                                if analytics:
                                    enriched_control["risk_analytics"] = {
                                        "avg_compliance_score": analytics.avg_compliance_score if hasattr(analytics, 'avg_compliance_score') else None,
                                        "trend": analytics.trend if hasattr(analytics, 'trend') else None,
                                        "current_risk_score": analytics.current_risk_score if hasattr(analytics, 'current_risk_score') else None,
                                        "risk_level": analytics.risk_level if hasattr(analytics, 'risk_level') else None,
                                        "failure_count_30d": analytics.failure_count_30d if hasattr(analytics, 'failure_count_30d') else None,
                                        "failure_count_90d": analytics.failure_count_90d if hasattr(analytics, 'failure_count_90d') else None
                                    }
                            except Exception as e:
                                logger.warning(f"Error retrieving measures for control {control_id}: {e}")
                        
                        # Extract risks from control profile if available
                        profile = control_data.get("profile") or {}
                        if profile:
                            risk_level = profile.get("risk_level")
                            if risk_level:
                                enriched_control["risks"].append({
                                    "risk_level": risk_level,
                                    "source": "control_profile"
                                })
                        
                        # Extract risks from reasoning path if available
                        reasoning_path = state.get("reasoning_path", [])
                        if reasoning_path:
                            for hop in reasoning_path:
                                store_results = hop.get("store_results", {})
                                risks = store_results.get("risks", [])
                                if risks:
                                    for risk in risks[:3]:  # Limit to 3 risks per control
                                        risk_doc = risk.get("document") or risk.get("content", "")
                                        if risk_doc and control_id in str(risk_doc):
                                            enriched_control["risks"].append({
                                                "risk_description": risk_doc[:500],
                                                "source": "reasoning_path"
                                            })
                        
                        enriched_controls.append(enriched_control)
                        
                except Exception as e:
                    logger.warning(f"Error enriching control: {e}")
                    continue
            
            # Store retrieved knowledge in state (no aggregation, just raw data)
            state["knowledge_data"] = {
                "controls": enriched_controls,
                "framework": framework,
                "total_controls": len(enriched_controls),
                "context_ids": context_ids
            }
            
            state["current_node"] = "knowledge_retrieval"
            state["next_node"] = "knowledge_qa"
            logger.info(f"Retrieved {len(enriched_controls)} {framework} controls with risks, requirements, and measures")
            
        except Exception as e:
            logger.error(f"Error in knowledge retrieval: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["knowledge_data"] = {
                "controls": [],
                "framework": self.framework,
                "total_controls": 0,
                "context_ids": []
            }
            state["next_node"] = "knowledge_qa"  # Continue anyway
        
        # Return only the fields we updated to avoid conflicts
        return _build_state_update(
            state,
            required_fields=["knowledge_data", "current_node", "next_node"],
            optional_fields=["status", "error"]
        )
    
    def _extract_framework(self, query: str, user_context: Dict[str, Any]) -> Optional[str]:
        """Extract compliance framework from query or user context (default to SOC2)"""
        query_lower = query.lower()
        
        # Check user context first
        if user_context.get("framework"):
            return user_context["framework"].upper()
        
        # Check query for framework mentions
        frameworks = ["SOC2", "SOC 2", "GDPR", "HIPAA", "PCI-DSS", "PCI DSS", "ISO27001", "NIST"]
        for framework in frameworks:
            if framework.lower() in query_lower:
                return framework.upper()
        
        # Default to SOC2 for knowledge assistant
        return "SOC2"


class KnowledgeQANode:
    """Node that presents knowledge as markdown without aggregation or consolidation"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Present knowledge as markdown without aggregation or consolidation
        
        This node formats the retrieved knowledge (controls, risks, measures) as markdown.
        It does NOT aggregate or consolidate data - it simply presents what was retrieved.
        """
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        knowledge_data = state.get("knowledge_data", {})
        
        try:
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            actor_config = get_actor_config(actor_type)
            
            # Extract knowledge components
            controls = knowledge_data.get("controls", [])
            framework = knowledge_data.get("framework", "SOC2")
            
            # Format knowledge as markdown
            markdown_content = self._format_knowledge_as_markdown(controls, framework, query)
            
            # Q&A prompt - just format the knowledge, don't aggregate
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a compliance knowledge assistant that presents SOC2 compliance information.

{actor_context}

Your task is to present compliance knowledge in a clear, organized markdown format.
You should:
- Present controls, risks, and measures as retrieved (no aggregation)
- Use clear markdown formatting with headers, lists, and tables
- Organize information logically but don't consolidate or summarize
- Present each control with its associated risks, requirements, and measures
- Use {actor_config['communication_style']} style
- Provide {actor_config['preferred_detail_level']} level of detail

IMPORTANT: 
- Do NOT aggregate or consolidate data
- Do NOT combine similar controls
- Present each control separately with all its information
- Show all measures/effectiveness data as retrieved
- Present risks as they appear in the data

Format your response as clean markdown with proper structure.
"""),
                ("human", """User Query: {query}

Framework: {framework}

Present the following compliance knowledge in markdown format:

{markdown_content}

Present this knowledge clearly without aggregation or consolidation.
""")
            ])
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "framework": framework,
                "markdown_content": markdown_content
            }
            logger.info(f"[LLM Step: KnowledgeQANode] Starting LLM call for knowledge presentation")
            logger.info(f"[LLM Step: KnowledgeQANode] Input - query={query[:100]}, framework={framework}")
            logger.info(f"[LLM Step: KnowledgeQANode] Context - controls_count={len(controls)}, markdown_content_length={len(markdown_content)}")
            logger.debug(f"[LLM Step: KnowledgeQANode] Markdown content preview: {markdown_content[:500]}...")
            
            chain = prompt | self.llm
            response = await chain.ainvoke(llm_input)
            
            # Log LLM call output
            answer = response.content if hasattr(response, "content") else str(response)
            logger.info(f"[LLM Step: KnowledgeQANode] LLM call completed successfully")
            logger.info(f"[LLM Step: KnowledgeQANode] Output: Answer length={len(answer) if answer else 0} characters")
            logger.info(f"[LLM Step: KnowledgeQANode] Answer preview: {answer[:500] if answer else 'None'}...")
            logger.debug(f"[LLM Step: KnowledgeQANode] Full answer (first 1000 chars): {answer[:1000] if answer else 'None'}...")
            
            state["qa_answer"] = answer
            state["qa_sources"] = {
                "controls_count": len(controls),
                "framework": framework,
                "total_measures": sum(len(c.get("measures", [])) for c in controls),
                "total_risks": sum(len(c.get("risks", [])) for c in controls)
            }
            state["qa_confidence"] = 0.9 if controls else 0.5
            
            # Add to messages
            from langchain_core.messages import HumanMessage, AIMessage
            messages = list(state.get("messages", []))
            messages.append(HumanMessage(content=query))
            messages.append(AIMessage(content=answer))
            state["messages"] = messages
            
            state["next_node"] = "writer_agent"
            state["current_node"] = "knowledge_qa"
            logger.info("Knowledge Q&A answer generated")
            
        except Exception as e:
            logger.error(f"Error in knowledge Q&A: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["qa_answer"] = f"Error generating answer: {str(e)}"
            state["next_node"] = "finalize"
        
        # Return only the fields we updated to avoid conflicts
        return _build_state_update(
            state,
            required_fields=["qa_answer", "qa_sources", "qa_confidence", "messages", "next_node"],
            optional_fields=["current_node", "status", "error"]
        )
    
    def _format_knowledge_as_markdown(self, controls: List[Dict], framework: str, query: str) -> str:
        """Format knowledge data as markdown (no aggregation)"""
        if not controls:
            return f"# {framework} Compliance Knowledge\n\nNo controls found for the query: {query}"
        
        parts = [f"# {framework} Compliance Knowledge\n"]
        parts.append(f"## Query: {query}\n")
        parts.append(f"## Total Controls: {len(controls)}\n")
        
        # Present each control separately (no consolidation)
        for i, control in enumerate(controls, 1):
            control_id = control.get("control_id", "Unknown")
            control_name = control.get("control_name", "")
            control_description = control.get("control_description", "")
            
            parts.append(f"\n## Control {i}: {control_id} - {control_name}\n")
            parts.append(f"**Description:** {control_description}\n")
            
            # Risks
            risks = control.get("risks", [])
            if risks:
                parts.append(f"\n### Risks\n")
                for risk in risks:
                    if isinstance(risk, dict):
                        risk_level = risk.get("risk_level")
                        risk_description = risk.get("risk_description", "")
                        if risk_level:
                            parts.append(f"- **Risk Level:** {risk_level}")
                        if risk_description:
                            parts.append(f"  - {risk_description[:300]}...")
                    else:
                        parts.append(f"- {str(risk)[:300]}")
            
            # Requirements
            requirements = control.get("requirements", [])
            if requirements:
                parts.append(f"\n### Requirements\n")
                for req in requirements:
                    if isinstance(req, dict):
                        req_text = req.get("requirement_text", str(req))
                        req_type = req.get("requirement_type", "")
                        if req_type:
                            parts.append(f"- **{req_type}:** {req_text[:500]}")
                        else:
                            parts.append(f"- {req_text[:500]}")
                    else:
                        parts.append(f"- {str(req)[:500]}")
            
            # Measures/Effectiveness
            measures = control.get("measures", [])
            if measures:
                parts.append(f"\n### Measures for Effectiveness\n")
                for measure in measures:
                    if isinstance(measure, dict):
                        measured_value = measure.get("measured_value")
                        measurement_date = measure.get("measurement_date", "")
                        passed = measure.get("passed")
                        data_source = measure.get("data_source", "")
                        quality_score = measure.get("quality_score")
                        
                        measure_info = f"- **Date:** {measurement_date}"
                        if measured_value is not None:
                            measure_info += f" | **Value:** {measured_value}"
                        if passed is not None:
                            measure_info += f" | **Passed:** {passed}"
                        if data_source:
                            measure_info += f" | **Source:** {data_source}"
                        if quality_score is not None:
                            measure_info += f" | **Quality:** {quality_score}"
                        parts.append(measure_info)
                    else:
                        parts.append(f"- {str(measure)[:300]}")
            
            # Risk Analytics
            risk_analytics = control.get("risk_analytics")
            if risk_analytics:
                parts.append(f"\n### Risk Analytics\n")
                if isinstance(risk_analytics, dict):
                    avg_score = risk_analytics.get("avg_compliance_score")
                    trend = risk_analytics.get("trend")
                    risk_score = risk_analytics.get("current_risk_score")
                    risk_level = risk_analytics.get("risk_level")
                    failures_30d = risk_analytics.get("failure_count_30d")
                    failures_90d = risk_analytics.get("failure_count_90d")
                    
                    if avg_score is not None:
                        parts.append(f"- **Average Compliance Score:** {avg_score}")
                    if trend:
                        parts.append(f"- **Trend:** {trend}")
                    if risk_score is not None:
                        parts.append(f"- **Current Risk Score:** {risk_score}")
                    if risk_level:
                        parts.append(f"- **Risk Level:** {risk_level}")
                    if failures_30d is not None:
                        parts.append(f"- **Failures (30 days):** {failures_30d}")
                    if failures_90d is not None:
                        parts.append(f"- **Failures (90 days):** {failures_90d}")
                else:
                    parts.append(f"- {str(risk_analytics)[:300]}")
        
        return "\n".join(parts)

