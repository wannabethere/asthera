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

from app.assistants.state import ContextualAssistantState
from app.assistants.actor_types import get_actor_config, get_actor_prompt_context

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
    """Node that retrieves SOC2 compliance knowledge: controls, risks, and measures
    
    Uses TSC (Trust Service Criteria) hierarchy for intelligent query breakdown:
    Framework → TSC → Control Objective → Control → Policy → Procedure → User Actions → Evidence → Issues
    """
    
    # TSC Categories mapping for query classification
    TSC_CATEGORIES = {
        "CC1": "Control Environment",
        "CC2": "Communication and Information",
        "CC3": "Risk Assessment",
        "CC4": "Monitoring Activities",
        "CC5": "Control Activities",
        "CC6": "Logical and Physical Access Controls",
        "CC7": "System Operations",
        "CC8": "Change Management",
        "CC9": "Risk Mitigation"
    }
    
    # Compliance hierarchy levels for query mapping
    HIERARCHY_LEVELS = {
        "framework": ["SOC2", "SOC 2", "HIPAA", "PCI-DSS", "ISO27001", "compliance framework"],
        "tsc": ["trust service criteria", "TSC", "CC1", "CC2", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "CC9"],
        "control": ["control", "CC6.1", "CC7.2", "security control"],
        "policy": ["policy", "standard", "company rule"],
        "procedure": ["procedure", "workflow", "process", "how to execute"],
        "user_action": ["user action", "approval", "review", "what people do", "actor", "responsibility"],
        "evidence": ["evidence", "proof", "artifact", "logs", "documentation"],
        "issue": ["issue", "finding", "gap", "failure", "risk", "non-compliance"]
    }
    
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
            
            # Analyze query using TSC hierarchy to determine what type of knowledge is needed
            hierarchy_analysis = self._analyze_query_hierarchy_level(query)
            
            # Map hierarchy analysis to knowledge categories for targeted retrieval
            target_categories = self._map_hierarchy_to_categories(hierarchy_analysis)
            
            logger.info(f"Query mapped to hierarchy level '{hierarchy_analysis['primary_level']}' "
                       f"with categories: {target_categories}")
            
            # Store hierarchy analysis in state for downstream use
            state["hierarchy_analysis"] = hierarchy_analysis
            state["target_categories"] = target_categories
            
            # 1. Retrieve controls for the framework
            controls = []
            if self.contextual_graph_service and context_ids:
                logger.info(f"Retrieving {framework} controls using context_ids from framework")
                try:
                    # Get controls for contexts retrieved by framework
                    for context_id in context_ids[:1]:  # Use first context
                        if context_id:
                            from app.models.service import ControlSearchRequest
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
                                from app.models.service import ControlSearchRequest
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
                            "risk_analytics": None,
                            "product_mappings": []  # Product-to-compliance edge mappings
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
                        
                        # Retrieve product-compliance edge mappings
                        if hasattr(self.contextual_graph_service, 'vector_storage'):
                            try:
                                # Query for edges where this control is the target
                                # These edges show which product entities/tables/features map to this control
                                product_edge_types = [
                                    "TABLE_PROVIDES_EVIDENCE",
                                    "COLUMN_PROVIDES_EVIDENCE",
                                    "FEATURE_SUPPORTS_CONTROL"
                                ]
                                
                                product_edges = []
                                for edge_type in product_edge_types:
                                    # Search for edges pointing to this control
                                    edges = await self.contextual_graph_service.vector_storage.search_edges(
                                        query=f"{control_id} {edge_type}",
                                        top_k=10,
                                        filters={"edge_type": edge_type, "target_entity_id": control_id}
                                    )
                                    product_edges.extend(edges)
                                
                                # Process product edges
                                for edge in product_edges[:10]:  # Limit to 10 product mappings per control
                                    mapping = {
                                        "edge_type": edge.edge_type,
                                        "source_entity_id": edge.source_entity_id,
                                        "source_entity_type": edge.source_entity_type,
                                        "mapping_description": edge.document[:500] if edge.document else "",
                                        "relevance_score": edge.relevance_score if hasattr(edge, 'relevance_score') else None,
                                        "evidence_available": edge.evidence_available if hasattr(edge, 'evidence_available') else None,
                                        "automation_possible": edge.automation_possible if hasattr(edge, 'automation_possible') else None
                                    }
                                    enriched_control["product_mappings"].append(mapping)
                                
                                if product_edges:
                                    logger.info(f"Retrieved {len(product_edges)} product-compliance edges for control {control_id}")
                            except Exception as e:
                                logger.warning(f"Error retrieving product-compliance edges for control {control_id}: {e}")
                        
                        enriched_controls.append(enriched_control)
                        
                except Exception as e:
                    logger.warning(f"Error enriching control: {e}")
                    continue
            
            # Store retrieved knowledge in state (no aggregation, just raw data)
            state["knowledge_data"] = {
                "controls": enriched_controls,
                "framework": framework,
                "total_controls": len(enriched_controls),
                "context_ids": context_ids,
                "hierarchy_analysis": hierarchy_analysis,
                "target_categories": target_categories,
                "tsc_categories": hierarchy_analysis.get("tsc_categories", [])
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
                "context_ids": [],
                "hierarchy_analysis": state.get("hierarchy_analysis", {}),
                "target_categories": state.get("target_categories", []),
                "tsc_categories": []
            }
            state["next_node"] = "knowledge_qa"  # Continue anyway
        
        # Return only the fields we updated to avoid conflicts
        return _build_state_update(
            state,
            required_fields=["knowledge_data", "current_node", "next_node"],
            optional_fields=["status", "error", "hierarchy_analysis", "target_categories"]
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
    
    def _analyze_query_hierarchy_level(self, query: str) -> Dict[str, Any]:
        """
        Analyze query to determine which level(s) of the compliance hierarchy are being requested.
        
        Compliance Hierarchy:
        Framework → TSC → Control Objective → Control → Policy → Procedure → User Actions → Evidence → Issues
        
        Returns:
            Dict with hierarchy levels and their relevance scores
        """
        query_lower = query.lower()
        
        analysis = {
            "primary_level": None,
            "secondary_levels": [],
            "tsc_categories": [],
            "requires_actions": False,
            "requires_evidence": False,
            "scope": "control"  # default scope
        }
        
        # Detect hierarchy levels
        level_matches = {}
        for level, keywords in self.HIERARCHY_LEVELS.items():
            matches = sum(1 for keyword in keywords if keyword.lower() in query_lower)
            if matches > 0:
                level_matches[level] = matches
        
        # Determine primary and secondary levels
        if level_matches:
            sorted_levels = sorted(level_matches.items(), key=lambda x: x[1], reverse=True)
            analysis["primary_level"] = sorted_levels[0][0]
            analysis["secondary_levels"] = [level for level, _ in sorted_levels[1:]]
        else:
            analysis["primary_level"] = "control"  # default to control level
        
        # Detect TSC categories mentioned
        for tsc_code, tsc_name in self.TSC_CATEGORIES.items():
            if tsc_code in query or tsc_name.lower() in query_lower:
                analysis["tsc_categories"].append(tsc_code)
        
        # Detect if user actions are relevant
        action_keywords = ["action", "approval", "review", "responsibility", "who performs", "actor", "workflow"]
        analysis["requires_actions"] = any(keyword in query_lower for keyword in action_keywords)
        
        # Detect if evidence is relevant
        evidence_keywords = ["evidence", "proof", "artifact", "logs", "documentation", "audit trail"]
        analysis["requires_evidence"] = any(keyword in query_lower for keyword in evidence_keywords)
        
        # Determine scope based on query breadth
        if any(word in query_lower for word in ["all", "entire", "complete", "comprehensive", "everything"]):
            analysis["scope"] = "comprehensive"
        elif any(word in query_lower for word in ["specific", "particular", "single", "one"]):
            analysis["scope"] = "specific"
        else:
            analysis["scope"] = "focused"
        
        logger.info(f"Query hierarchy analysis: primary={analysis['primary_level']}, "
                   f"TSC={analysis['tsc_categories']}, actions={analysis['requires_actions']}, "
                   f"evidence={analysis['requires_evidence']}, scope={analysis['scope']}")
        
        return analysis
    
    def _map_hierarchy_to_categories(self, hierarchy_analysis: Dict[str, Any]) -> List[str]:
        """
        Map hierarchy analysis to knowledge store categories for targeted retrieval.
        
        Returns:
            List of category names to prioritize in retrieval
        """
        categories = []
        
        primary_level = hierarchy_analysis.get("primary_level")
        
        # Map hierarchy levels to categories
        if primary_level == "framework":
            categories.extend(["compliance_frameworks", "regulatory_requirements"])
        elif primary_level == "tsc":
            categories.extend(["trust_service_criteria", "control_objectives"])
        elif primary_level == "control":
            categories.extend(["controls", "security_controls", "compliance_controls"])
        elif primary_level == "policy":
            categories.extend(["policies", "standards", "governance"])
        elif primary_level == "procedure":
            categories.extend(["procedures", "workflows", "processes"])
        elif primary_level == "user_action":
            categories.extend(["user_actions", "responsibilities", "approvals", "reviews"])
        elif primary_level == "evidence":
            categories.extend(["evidence", "audit_logs", "artifacts", "documentation"])
        elif primary_level == "issue":
            categories.extend(["findings", "issues", "gaps", "risks", "non_compliance"])
        
        # Add TSC-specific categories if identified
        tsc_categories = hierarchy_analysis.get("tsc_categories", [])
        for tsc in tsc_categories:
            tsc_name = self.TSC_CATEGORIES.get(tsc, "").lower().replace(" ", "_")
            if tsc_name:
                categories.append(tsc_name)
        
        # Add action and evidence categories if needed
        if hierarchy_analysis.get("requires_actions"):
            categories.extend(["user_actions", "actor_responsibilities", "workflow_steps"])
        if hierarchy_analysis.get("requires_evidence"):
            categories.extend(["evidence_types", "audit_artifacts", "compliance_proof"])
        
        return list(set(categories))  # Remove duplicates


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
        Uses TSC hierarchy awareness to structure the presentation appropriately.
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
            hierarchy_analysis = knowledge_data.get("hierarchy_analysis", {})
            tsc_categories = knowledge_data.get("tsc_categories", [])
            
            # Format knowledge as markdown with TSC hierarchy awareness
            markdown_content = self._format_knowledge_as_markdown(
                controls, 
                framework, 
                query, 
                hierarchy_analysis, 
                tsc_categories
            )
            
            # Build hierarchy context for the prompt
            hierarchy_context = ""
            if hierarchy_analysis:
                primary_level = hierarchy_analysis.get("primary_level", "control")
                hierarchy_context = f"""
Query Hierarchy Analysis:
- Primary Level: {primary_level} (in the compliance hierarchy: Framework → TSC → Control → Policy → Procedure → User Actions → Evidence → Issues)
- TSC Categories: {', '.join(tsc_categories) if tsc_categories else 'General'}
- Requires User Actions: {'Yes' if hierarchy_analysis.get('requires_actions') else 'No'}
- Requires Evidence Details: {'Yes' if hierarchy_analysis.get('requires_evidence') else 'No'}
"""
            
            # Q&A prompt - just format the knowledge, don't aggregate
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a compliance knowledge assistant that presents SOC2 compliance information using the Trust Service Criteria (TSC) hierarchy.

{actor_context}

Compliance Hierarchy:
Framework → Trust Service Criteria (TSC) → Control Objective → Control → Policy → Procedure → User Actions → Evidence → Issues

TSC Categories (SOC 2):
- CC1: Control Environment
- CC2: Communication and Information
- CC3: Risk Assessment
- CC4: Monitoring Activities
- CC5: Control Activities
- CC6: Logical and Physical Access Controls
- CC7: System Operations
- CC8: Change Management
- CC9: Risk Mitigation

Your task is to present compliance knowledge in a clear, organized markdown format that respects this hierarchy.
You should:
- Present controls, risks, measures, and product mappings as retrieved (no aggregation)
- Use clear markdown formatting with headers, lists, and tables
- Organize information according to TSC categories when applicable
- Show relationships between different hierarchy levels (e.g., Control → Procedure → User Actions → Evidence)
- Present each control with its associated risks, requirements, measures, and product mappings
- Product mappings show how database tables, columns, and features connect to compliance controls
- When user actions or evidence are requested, emphasize those aspects
- Use {actor_config['communication_style']} style
- Provide {actor_config['preferred_detail_level']} level of detail

IMPORTANT: 
- Do NOT aggregate or consolidate data
- Do NOT combine similar controls
- Present each control separately with all its information
- Show all measures/effectiveness data as retrieved
- Present risks as they appear in the data
- Show product mappings to help users understand which data sources provide evidence for each control
- Product mappings bridge technical/product capabilities to compliance requirements
- Respect the TSC hierarchy when organizing information

{hierarchy_context}

Format your response as clean markdown with proper structure.
"""),
                ("human", """User Query: {query}

Framework: {framework}
TSC Categories: {tsc_categories}

Present the following compliance knowledge in markdown format:

{markdown_content}

Present this knowledge clearly without aggregation or consolidation. Include product/domain knowledge mappings that show how database tables, features, and columns connect to compliance controls. Organize according to the TSC hierarchy where applicable.
""")
            ])
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "framework": framework,
                "tsc_categories": ', '.join(tsc_categories) if tsc_categories else "General",
                "markdown_content": markdown_content
            }
            logger.info(f"[LLM Step: KnowledgeQANode] Starting LLM call for knowledge presentation")
            logger.info(f"[LLM Step: KnowledgeQANode] Input - query={query[:100]}, framework={framework}, TSC={tsc_categories}")
            logger.info(f"[LLM Step: KnowledgeQANode] Context - controls_count={len(controls)}, markdown_content_length={len(markdown_content)}")
            logger.info(f"[LLM Step: KnowledgeQANode] Hierarchy - primary_level={hierarchy_analysis.get('primary_level')}, scope={hierarchy_analysis.get('scope')}")
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
                "total_risks": sum(len(c.get("risks", [])) for c in controls),
                "total_product_mappings": sum(len(c.get("product_mappings", [])) for c in controls)
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
    
    def _format_knowledge_as_markdown(
        self, 
        controls: List[Dict], 
        framework: str, 
        query: str,
        hierarchy_analysis: Optional[Dict[str, Any]] = None,
        tsc_categories: Optional[List[str]] = None
    ) -> str:
        """Format knowledge data as markdown (no aggregation) with TSC hierarchy awareness"""
        if not controls:
            return f"# {framework} Compliance Knowledge\n\nNo controls found for the query: {query}"
        
        parts = [f"# {framework} Compliance Knowledge\n"]
        
        # Add TSC context if available
        if tsc_categories and len(tsc_categories) > 0:
            tsc_names = [f"{tsc} ({KnowledgeRetrievalNode.TSC_CATEGORIES.get(tsc, 'Unknown')})" 
                        for tsc in tsc_categories]
            parts.append(f"**Trust Service Criteria:** {', '.join(tsc_names)}\n")
        
        # Add hierarchy level context
        if hierarchy_analysis:
            primary_level = hierarchy_analysis.get("primary_level", "control")
            parts.append(f"**Query Focus:** {primary_level.replace('_', ' ').title()} Level\n")
        
        parts.append(f"## Query: {query}\n")
        parts.append(f"## Total Controls: {len(controls)}\n")
        
        # Present each control separately (no consolidation)
        for i, control in enumerate(controls, 1):
            control_id = control.get("control_id", "Unknown")
            control_name = control.get("control_name", "")
            control_description = control.get("control_description", "")
            
            parts.append(f"\n## Control {i}: {control_id} - {control_name}\n")
            
            # Show TSC category if the control ID matches TSC pattern (e.g., CC6.1)
            if control_id and len(control_id) >= 3:
                tsc_prefix = control_id[:3].upper()  # e.g., "CC6"
                if tsc_prefix in KnowledgeRetrievalNode.TSC_CATEGORIES:
                    tsc_name = KnowledgeRetrievalNode.TSC_CATEGORIES[tsc_prefix]
                    parts.append(f"**Trust Service Criteria:** {tsc_prefix} - {tsc_name}\n")
            
            parts.append(f"**Description:** {control_description}\n")
            
            # Add hierarchy path if user wants to understand the full hierarchy
            if hierarchy_analysis and hierarchy_analysis.get("requires_actions"):
                parts.append(f"\n_Hierarchy Path: Control → Policy → Procedure → User Actions → Evidence_\n")
            
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
            
            # Product-Compliance Mappings
            product_mappings = control.get("product_mappings", [])
            if product_mappings:
                parts.append(f"\n### Product/Domain Knowledge Mappings\n")
                parts.append(f"_These mappings connect product capabilities, data tables, and features to this compliance control._\n")
                
                # Group mappings by edge type for better readability
                mappings_by_type = {}
                for mapping in product_mappings:
                    edge_type = mapping.get("edge_type", "UNKNOWN")
                    if edge_type not in mappings_by_type:
                        mappings_by_type[edge_type] = []
                    mappings_by_type[edge_type].append(mapping)
                
                # Present each type of mapping
                for edge_type, mappings in mappings_by_type.items():
                    if edge_type == "TABLE_PROVIDES_EVIDENCE":
                        parts.append(f"\n#### Tables Providing Evidence\n")
                        for mapping in mappings:
                            table_name = mapping.get("source_entity_id", "Unknown")
                            description = mapping.get("mapping_description", "")
                            relevance = mapping.get("relevance_score")
                            evidence_available = mapping.get("evidence_available")
                            
                            parts.append(f"- **Table:** `{table_name}`")
                            if description:
                                parts.append(f"  - {description}")
                            if relevance is not None:
                                parts.append(f"  - Relevance: {relevance:.2f}")
                            if evidence_available is not None:
                                parts.append(f"  - Evidence Available: {'Yes' if evidence_available else 'No'}")
                    
                    elif edge_type == "COLUMN_PROVIDES_EVIDENCE":
                        parts.append(f"\n#### Columns Providing Evidence\n")
                        for mapping in mappings:
                            column_name = mapping.get("source_entity_id", "Unknown")
                            description = mapping.get("mapping_description", "")
                            relevance = mapping.get("relevance_score")
                            
                            parts.append(f"- **Column:** `{column_name}`")
                            if description:
                                parts.append(f"  - {description}")
                            if relevance is not None:
                                parts.append(f"  - Relevance: {relevance:.2f}")
                    
                    elif edge_type == "FEATURE_SUPPORTS_CONTROL":
                        parts.append(f"\n#### Features Supporting This Control\n")
                        for mapping in mappings:
                            feature_name = mapping.get("source_entity_id", "Unknown")
                            description = mapping.get("mapping_description", "")
                            relevance = mapping.get("relevance_score")
                            automation = mapping.get("automation_possible")
                            
                            parts.append(f"- **Feature:** `{feature_name}`")
                            if description:
                                parts.append(f"  - {description}")
                            if relevance is not None:
                                parts.append(f"  - Relevance: {relevance:.2f}")
                            if automation is not None:
                                parts.append(f"  - Automation Possible: {'Yes' if automation else 'No'}")
                    
                    else:
                        # Generic handling for other edge types
                        parts.append(f"\n#### {edge_type.replace('_', ' ').title()}\n")
                        for mapping in mappings:
                            entity_name = mapping.get("source_entity_id", "Unknown")
                            entity_type = mapping.get("source_entity_type", "Unknown")
                            description = mapping.get("mapping_description", "")
                            
                            parts.append(f"- **{entity_type}:** `{entity_name}`")
                            if description:
                                parts.append(f"  - {description}")
        
        return "\n".join(parts)

