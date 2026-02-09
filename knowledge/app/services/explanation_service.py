"""
Explanation Service
Generates explanations for user actions based on all available contexts
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.services.base import BaseService, ServiceRequest, ServiceResponse
from app.models.service import ExplanationRequest, ExplanationResponse
from app.services.contextual_graph_service import ContextualGraphService

logger = logging.getLogger(__name__)


class ExplanationService(BaseService[ServiceRequest, ServiceResponse]):
    """
    Service that generates explanations for user actions based on contextual graphs.
    
    Provides detailed explanations of why certain actions were taken, what contexts
    were considered, and how decisions were made.
    """
    
    def __init__(
        self,
        contextual_graph_service: ContextualGraphService,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        maxsize: int = 1_000_000,
        ttl: int = 300  # 5 minutes for explanations
    ):
        """Initialize explanation service"""
        super().__init__(maxsize=maxsize, ttl=ttl)
        
        self.contextual_graph_service = contextual_graph_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
    
    async def generate_explanation(self, request: ExplanationRequest) -> ExplanationResponse:
        """
        Generate explanation for a user action based on contexts
        
        Args:
            request: ExplanationRequest with user action and context information
            
        Returns:
            ExplanationResponse with detailed explanation
        """
        try:
            user_action = request.user_action
            action_type = request.action_type
            context_ids = request.context_ids
            include_reasoning = request.include_reasoning
            
            # Step 1: Find relevant contexts
            relevant_contexts = await self._find_relevant_contexts(
                user_action,
                action_type,
                context_ids
            )
            
            # Step 2: Gather context information
            context_details = await self._gather_context_details(relevant_contexts)
            
            # Step 3: Generate explanation
            explanation = await self._generate_explanation_text(
                user_action,
                action_type,
                relevant_contexts,
                context_details,
                include_reasoning
            )
            
            return ExplanationResponse(
                success=True,
                data={
                    "explanation": explanation,
                    "contexts_used": [
                        {
                            "context_id": ctx.get("context_id"),
                            "relevance_score": ctx.get("combined_score", 0.0),
                            "metadata": ctx.get("metadata", {})
                        }
                        for ctx in relevant_contexts
                    ],
                    "reasoning_steps": context_details.get("reasoning_steps", []) if include_reasoning else [],
                    "total_contexts": len(relevant_contexts)
                },
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}", exc_info=True)
            return ExplanationResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def _find_relevant_contexts(
        self,
        user_action: str,
        action_type: Optional[str],
        context_ids: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Find relevant contexts for the user action"""
        from .models import ContextSearchRequest
        
        contexts = []
        
        # If specific context IDs provided, get those
        if context_ids:
            for ctx_id in context_ids:
                response = await self.contextual_graph_service.search_contexts(
                    ContextSearchRequest(
                        description=user_action,
                        filters={"context_id": ctx_id},
                        top_k=1,
                        request_id=f"explain_ctx_{ctx_id}"
                    )
                )
                if response.success and response.data:
                    contexts.extend(response.data.get("contexts", []))
        
        # Search for relevant contexts
        search_query = user_action
        if action_type:
            search_query += f" {action_type}"
        
        response = await self.contextual_graph_service.search_contexts(
            ContextSearchRequest(
                description=search_query,
                top_k=5,
                request_id=f"explain_all_{action_type or 'general'}"
            )
        )
        
        if response.success and response.data:
            new_contexts = response.data.get("contexts", [])
            # Deduplicate
            existing_ids = {ctx.get("context_id") for ctx in contexts}
            for ctx in new_contexts:
                if ctx.get("context_id") not in existing_ids:
                    contexts.append(ctx)
                    existing_ids.add(ctx.get("context_id"))
        
        return contexts
    
    async def _gather_context_details(self, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Gather detailed information from contexts"""
        details = {
            "contexts": [],
            "controls": [],
            "reasoning_steps": []
        }
        
        for context in contexts[:3]:  # Limit to top 3 for performance
            context_id = context.get("context_id")
            if not context_id:
                continue
            
            # Get priority controls for context
            from .models import PriorityControlsRequest
            
            response = await self.contextual_graph_service.get_priority_controls(
                PriorityControlsRequest(
                    context_id=context_id,
                    top_k=5,
                    request_id=f"explain_details_{context_id}"
                )
            )
            
            if response.success and response.data:
                controls = response.data.get("controls", [])
                details["controls"].extend(controls)
                details["contexts"].append({
                    "context_id": context_id,
                    "metadata": context.get("metadata", {}),
                    "controls_count": len(controls)
                })
        
        return details
    
    async def _generate_explanation_text(
        self,
        user_action: str,
        action_type: Optional[str],
        contexts: List[Dict[str, Any]],
        context_details: Dict[str, Any],
        include_reasoning: bool
    ) -> str:
        """Generate explanation text using LLM"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at explaining compliance and risk management decisions.

Given a user action and the contexts that were considered, provide a clear, detailed explanation that:
1. Explains what the action does
2. Describes why this action was taken
3. Identifies which organizational contexts influenced the decision
4. Explains the reasoning behind the decision
5. Highlights any risks or considerations

Make it clear, concise, and actionable."""),
            ("human", """Explain this user action:

Action: {user_action}
Action Type: {action_type}

Contexts Considered ({context_count}):
{contexts_summary}

Controls Found:
{controls_summary}

Provide a comprehensive explanation{reasoning_note}.""")
        ])
        
        chain = prompt | self.llm
        
        try:
            contexts_summary = "\n".join([
                f"- {ctx.get('context_id')}: {ctx.get('metadata', {}).get('industry', 'N/A')} "
                f"({ctx.get('combined_score', 0.0):.2f} relevance)"
                for ctx in contexts
            ])
            
            controls = context_details.get("controls", [])
            controls_summary = "\n".join([
                f"- {ctrl.get('control_id', 'unknown')}: "
                f"Risk level: {ctrl.get('context_profile', {}).get('risk_level', 'N/A')}"
                for ctrl in controls[:5]
            ]) if controls else "No specific controls identified"
            
            result = await chain.ainvoke({
                "user_action": user_action,
                "action_type": action_type or "general",
                "context_count": len(contexts),
                "contexts_summary": contexts_summary,
                "controls_summary": controls_summary,
                "reasoning_note": " including reasoning steps" if include_reasoning else ""
            })
            
            return result.content if hasattr(result, 'content') else str(result)
            
        except Exception as e:
            logger.error(f"Error generating explanation text: {str(e)}", exc_info=True)
            return f"Explanation for action: {user_action}. Considered {len(contexts)} contexts."
    
    async def _process_request_impl(self, request) -> ServiceResponse:
        """Route requests to appropriate handlers"""
        if isinstance(request, ExplanationRequest):
            return await self.generate_explanation(request)
        else:
            return ServiceResponse(
                success=False,
                error=f"Unknown request type: {type(request)}",
                request_id=getattr(request, 'request_id', None)
            )

