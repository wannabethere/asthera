"""
Reasoning Plan Service
Creates reasoning plans for user actions based on all available contexts
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.services.base import BaseService, ServiceRequest, ServiceResponse
from app.models.service import ReasoningPlanRequest, ReasoningPlanResponse
from app.services.contextual_graph_service import ContextualGraphService

logger = logging.getLogger(__name__)


class ReasoningPlanService(BaseService[ServiceRequest, ServiceResponse]):
    """
    Service that creates reasoning plans for user actions based on contextual graphs.
    
    Analyzes all available contexts and creates a step-by-step reasoning plan
    that considers organizational context, risk profiles, and control implementations.
    """
    
    def __init__(
        self,
        contextual_graph_service: ContextualGraphService,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        maxsize: int = 1_000_000,
        ttl: int = 300  # 5 minutes for reasoning plans
    ):
        """Initialize reasoning plan service"""
        super().__init__(maxsize=maxsize, ttl=ttl)
        
        self.contextual_graph_service = contextual_graph_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
    
    async def create_reasoning_plan(self, request: ReasoningPlanRequest) -> ReasoningPlanResponse:
        """
        Create a reasoning plan for a user action based on available contexts
        
        Args:
            request: ReasoningPlanRequest with user action and context information
            
        Returns:
            ReasoningPlanResponse with step-by-step reasoning plan
        """
        try:
            user_action = request.user_action
            target_domain = request.target_domain
            context_ids = request.context_ids
            include_all_contexts = request.include_all_contexts
            
            # Step 1: Find relevant contexts
            relevant_contexts = await self._find_relevant_contexts(
                user_action,
                target_domain,
                context_ids,
                include_all_contexts
            )
            
            # Step 2: Analyze contexts and create reasoning steps
            reasoning_steps = await self._create_reasoning_steps(
                user_action,
                relevant_contexts,
                target_domain
            )
            
            # Step 3: Generate plan with priorities
            plan = await self._generate_plan(
                user_action,
                reasoning_steps,
                relevant_contexts,
                target_domain
            )
            
            return ReasoningPlanResponse(
                success=True,
                data={
                    "reasoning_plan": plan,
                    "reasoning_steps": reasoning_steps,
                    "contexts_considered": [
                        {
                            "context_id": ctx.get("context_id"),
                            "relevance_score": ctx.get("combined_score", 0.0),
                            "metadata": ctx.get("metadata", {})
                        }
                        for ctx in relevant_contexts
                    ],
                    "total_contexts": len(relevant_contexts)
                },
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error creating reasoning plan: {str(e)}", exc_info=True)
            return ReasoningPlanResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def _find_relevant_contexts(
        self,
        user_action: str,
        target_domain: Optional[str],
        context_ids: Optional[List[str]],
        include_all_contexts: bool
    ) -> List[Dict[str, Any]]:
        """Find relevant contexts for the user action"""
        from .models import ContextSearchRequest
        
        contexts = []
        
        # If specific context IDs provided, get those
        if context_ids:
            for ctx_id in context_ids:
                # Search with context ID filter
                response = await self.contextual_graph_service.search_contexts(
                    ContextSearchRequest(
                        description=user_action,
                        filters={"context_id": ctx_id},
                        top_k=1,
                        request_id=f"plan_ctx_{ctx_id}"
                    )
                )
                if response.success and response.data:
                    contexts.extend(response.data.get("contexts", []))
        
        # If include_all_contexts, search broadly
        if include_all_contexts or not context_ids:
            search_query = f"{user_action}"
            if target_domain:
                search_query += f" in {target_domain} domain"
            
            response = await self.contextual_graph_service.search_contexts(
                ContextSearchRequest(
                    description=search_query,
                    top_k=10,
                    request_id=f"plan_all_{target_domain or 'general'}"
                )
            )
            
            if response.success and response.data:
                new_contexts = response.data.get("contexts", [])
                # Deduplicate by context_id
                existing_ids = {ctx.get("context_id") for ctx in contexts}
                for ctx in new_contexts:
                    if ctx.get("context_id") not in existing_ids:
                        contexts.append(ctx)
                        existing_ids.add(ctx.get("context_id"))
        
        return contexts
    
    async def _create_reasoning_steps(
        self,
        user_action: str,
        contexts: List[Dict[str, Any]],
        target_domain: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Create reasoning steps based on contexts"""
        steps = []
        
        # Step 1: Context analysis
        steps.append({
            "step_number": 1,
            "step_name": "Context Analysis",
            "description": f"Analyze {len(contexts)} relevant organizational contexts",
            "contexts_involved": [ctx.get("context_id") for ctx in contexts],
            "output": f"Identified {len(contexts)} contexts relevant to: {user_action}"
        })
        
        # Step 2: For each context, get priority controls
        for idx, context in enumerate(contexts[:5]):  # Limit to top 5 contexts
            context_id = context.get("context_id")
            if context_id:
                from .models import PriorityControlsRequest
                
                response = await self.contextual_graph_service.get_priority_controls(
                    PriorityControlsRequest(
                        context_id=context_id,
                        query=user_action,
                        top_k=5,
                        request_id=f"plan_steps_{context_id}"
                    )
                )
                
                if response.success and response.data:
                    controls = response.data.get("controls", [])
                    steps.append({
                        "step_number": len(steps) + 1,
                        "step_name": f"Control Analysis - {context_id}",
                        "description": f"Analyze priority controls in context {context_id}",
                        "contexts_involved": [context_id],
                        "controls_found": len(controls),
                        "output": f"Found {len(controls)} priority controls for this context"
                    })
        
        # Step 3: Multi-hop reasoning if applicable
        if target_domain and contexts:
            primary_context = contexts[0]
            context_id = primary_context.get("context_id")
            
            if context_id:
                from .models import MultiHopQueryRequest
                
                response = await self.contextual_graph_service.multi_hop_query(
                    MultiHopQueryRequest(
                        query=user_action,
                        context_id=context_id,
                        max_hops=2,
                        request_id=f"plan_reasoning_{context_id}"
                    )
                )
                
                if response.success and response.data:
                    reasoning_path = response.data.get("reasoning_path", [])
                    steps.append({
                        "step_number": len(steps) + 1,
                        "step_name": "Multi-Hop Reasoning",
                        "description": "Perform multi-hop reasoning through contextual graph",
                        "contexts_involved": [context_id],
                        "reasoning_hops": len(reasoning_path),
                        "output": response.data.get("final_answer", "")[:500]
                    })
        
        return steps
    
    async def _generate_plan(
        self,
        user_action: str,
        reasoning_steps: List[Dict[str, Any]],
        contexts: List[Dict[str, Any]],
        target_domain: Optional[str]
    ) -> Dict[str, Any]:
        """Generate final reasoning plan using LLM"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at creating reasoning plans for compliance and risk management actions.

Given a user action and the available contexts, create a clear, step-by-step reasoning plan that:
1. Considers all relevant organizational contexts
2. Identifies key decision points
3. Provides reasoning for each step
4. Considers risk implications
5. Suggests validation steps

Return a structured reasoning plan."""),
            ("human", """Create a reasoning plan for this user action:

User Action: {user_action}
Target Domain: {target_domain}

Available Contexts ({context_count}):
{contexts_summary}

Reasoning Steps Identified:
{reasoning_steps}

Provide a structured reasoning plan with:
1. Overview
2. Key decision points
3. Step-by-step reasoning
4. Risk considerations
5. Validation approach""")
        ])
        
        chain = prompt | self.llm
        
        try:
            contexts_summary = "\n".join([
                f"- {ctx.get('context_id')}: {ctx.get('metadata', {}).get('industry', 'N/A')} "
                f"({ctx.get('combined_score', 0.0):.2f} relevance)"
                for ctx in contexts[:5]
            ])
            
            steps_summary = "\n".join([
                f"{step['step_number']}. {step['step_name']}: {step['description']}"
                for step in reasoning_steps
            ])
            
            result = await chain.ainvoke({
                "user_action": user_action,
                "target_domain": target_domain or "General",
                "context_count": len(contexts),
                "contexts_summary": contexts_summary,
                "reasoning_steps": steps_summary
            })
            
            plan_text = result.content if hasattr(result, 'content') else str(result)
            
            return {
                "overview": f"Reasoning plan for: {user_action}",
                "total_steps": len(reasoning_steps),
                "contexts_used": len(contexts),
                "plan_text": plan_text,
                "steps": reasoning_steps
            }
            
        except Exception as e:
            logger.error(f"Error generating plan: {str(e)}", exc_info=True)
            return {
                "overview": f"Reasoning plan for: {user_action}",
                "total_steps": len(reasoning_steps),
                "contexts_used": len(contexts),
                "plan_text": "Error generating detailed plan",
                "steps": reasoning_steps
            }
    
    async def _process_request_impl(self, request) -> ServiceResponse:
        """Route requests to appropriate handlers"""
        if isinstance(request, ReasoningPlanRequest):
            return await self.create_reasoning_plan(request)
        else:
            return ServiceResponse(
                success=False,
                error=f"Unknown request type: {type(request)}",
                request_id=getattr(request, 'request_id', None)
            )

