"""
Metadata Generation Pipeline
Generates metadata entries for target domain using contextual graphs for context-aware scoring
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from .base import ExtractionPipeline
from ..metadata_generation_agent import MetadataGenerationAgent
from ..metadata_state import MetadataEntry

logger = logging.getLogger(__name__)


class MetadataGenerationPipeline(ExtractionPipeline):
    """Pipeline for generating metadata entries with contextual graph integration"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        contextual_graph_service: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize metadata generation pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            contextual_graph_service: Optional contextual graph service for context-aware generation
        """
        super().__init__(
            name="metadata_generation",
            version="1.0.0",
            description="Generate metadata entries for target domain using contextual graphs",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.agent = MetadataGenerationAgent(llm=llm, model_name=model_name)
        self.contextual_graph_service = contextual_graph_service
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        if self.contextual_graph_service:
            logger.info("Metadata generation pipeline initialized with contextual graph service")
        else:
            logger.info("Metadata generation pipeline initialized (no contextual graph service)")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate metadata entries with optional contextual graph integration
        
        Args:
            inputs: Dictionary with keys:
                - target_domain: Target domain name
                - target_documents: List of target domain document texts
                - target_framework: Optional framework name
                - learned_patterns: List of learned patterns
                - domain_mappings: List of domain mappings
                - adaptation_strategy: Adaptation strategy dict
                - use_contextual_graph: Whether to use contextual graphs (default: True if service available)
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with generated metadata entries and notes
        """
        if status_callback:
            status_callback("generating", {"stage": "metadata_generation_start"})
        
        target_domain = inputs.get("target_domain", "")
        target_documents = inputs.get("target_documents", [])
        target_framework = inputs.get("target_framework")
        learned_patterns = inputs.get("learned_patterns", [])
        domain_mappings = inputs.get("domain_mappings", [])
        adaptation_strategy = inputs.get("adaptation_strategy", {})
        use_contextual_graph = inputs.get("use_contextual_graph", self.contextual_graph_service is not None)
        
        try:
            # Create state from inputs
            from ..metadata_state import MetadataTransferLearningState
            from ..state_helpers import pattern_to_dict, mapping_to_dict
            
            state: MetadataTransferLearningState = {
                "target_domain": target_domain,
                "target_framework": target_framework,
                "target_documents": target_documents,
                "learned_patterns": [pattern_to_dict(p) if hasattr(p, 'pattern_name') else p for p in learned_patterns],
                "domain_mappings": [mapping_to_dict(m) if hasattr(m, 'source_domain') else m for m in domain_mappings],
                "adaptation_strategy": adaptation_strategy,
                "identified_risks": [],
                "generated_metadata": [],
                "generation_notes": [],
                "status": "metadata_generation",
                "current_step": "start",
                "messages": [],
                "errors": [],
                "warnings": []
            }
            
            # If using contextual graphs, enhance risk identification and scoring
            if use_contextual_graph and self.contextual_graph_service:
                if status_callback:
                    status_callback("processing", {"stage": "identifying_context_aware_risks"})
                
                # Find target context
                target_context = await self._find_target_context(target_domain, target_documents)
                
                if target_context:
                    # Get context-aware risks from control profiles
                    context_risks = await self._identify_context_aware_risks(
                        target_domain,
                        target_context,
                        adaptation_strategy
                    )
                    
                    if context_risks:
                        state["identified_risks"] = context_risks
                        logger.info(f"Identified {len(context_risks)} context-aware risks")
            
            # Run metadata generation agent
            if status_callback:
                status_callback("processing", {"stage": "generating_metadata_entries"})
            
            state = await self.agent(state)
            
            # Enhance generated metadata with context-aware scoring if available
            if use_contextual_graph and self.contextual_graph_service and target_context:
                if status_callback:
                    status_callback("processing", {"stage": "enhancing_with_context_scores"})
                
                enhanced_metadata = await self._enhance_metadata_with_context(
                    state.get("generated_metadata", []),
                    target_context
                )
                state["generated_metadata"] = enhanced_metadata
            
            # Extract results
            from ..state_helpers import get_entries_from_state
            entries = get_entries_from_state(state)
            
            if status_callback:
                status_callback("completed", {"stage": "metadata_generation_complete"})
            
            return {
                "success": True,
                "data": {
                    "metadata_entries": [self._entry_to_dict(e) for e in entries],
                    "generation_notes": state.get("generation_notes", []),
                    "identified_risks": state.get("identified_risks", []),
                    "entry_count": len(entries)
                },
                "state": state
            }
            
        except Exception as e:
            logger.error(f"Error in metadata generation: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "metadata_generation_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "metadata_entries": [],
                    "generation_notes": [],
                    "identified_risks": []
                }
            }
    
    async def _find_target_context(
        self,
        target_domain: str,
        target_documents: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Find matching context for target domain"""
        if not self.contextual_graph_service:
            return None
        
        try:
            from app.services.models import ContextSearchRequest
            
            context_query = f"{target_domain} compliance context: {target_documents[0][:500] if target_documents else ''}"
            response = await self.contextual_graph_service.search_contexts(
                ContextSearchRequest(
                    description=context_query,
                    top_k=1,
                    request_id=f"gen_ctx_{target_domain}"
                )
            )
            
            if response.success and response.data:
                contexts = response.data.get("contexts", [])
                if contexts:
                    return contexts[0]
            
            return None
            
        except Exception as e:
            logger.warning(f"Error finding target context: {str(e)}")
            return None
    
    async def _identify_context_aware_risks(
        self,
        target_domain: str,
        target_context: Dict[str, Any],
        adaptation_strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify risks from context-aware control profiles"""
        if not self.contextual_graph_service:
            return []
        
        try:
            from app.services.models import PriorityControlsRequest
            
            context_id = target_context.get("context_id")
            if not context_id:
                return []
            
            # Get priority controls for context
            response = await self.contextual_graph_service.get_priority_controls(
                PriorityControlsRequest(
                    context_id=context_id,
                    query=f"Risks and threats in {target_domain}",
                    top_k=20,
                    request_id=f"gen_risks_{context_id}"
                )
            )
            
            if not response.success or not response.data:
                return []
            
            controls = response.data.get("controls", [])
            risks = []
            
            for control in controls:
                profile = control.get("context_profile", {})
                risk_level = profile.get("risk_level", "")
                
                # Only include high/critical risks
                if risk_level in ["high", "critical"]:
                    risks.append({
                        "risk_name": control.get("control_id", "unknown"),
                        "category": "threat",
                        "description": control.get("reasoning", ""),
                        "severity_indicators": f"Risk level: {risk_level}, Residual risk: {profile.get('residual_risk_score', 0)}",
                        "likelihood_indicators": f"Implementation complexity: {profile.get('implementation_complexity', 'unknown')}",
                        "impact_indicators": f"Estimated effort: {profile.get('estimated_effort_hours', 0)} hours",
                        "regulatory_source": target_domain,
                        "context_id": context_id
                    })
            
            return risks
            
        except Exception as e:
            logger.warning(f"Error identifying context-aware risks: {str(e)}")
            return []
    
    async def _enhance_metadata_with_context(
        self,
        metadata_entries: List[Dict[str, Any]],
        target_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance metadata entries with context-aware scores"""
        if not self.contextual_graph_service:
            return metadata_entries
        
        try:
            from app.services.models import ControlSearchRequest
            
            context_id = target_context.get("context_id")
            if not context_id:
                return metadata_entries
            
            enhanced = []
            
            for entry in metadata_entries:
                # Find similar control in context
                entry_code = entry.get("code", "")
                entry_desc = entry.get("description", "")
                
                if entry_code or entry_desc:
                    control_response = await self.contextual_graph_service.search_controls(
                        ControlSearchRequest(
                            context_id=context_id,
                            query=entry_desc or entry_code,
                            top_k=1,
                            request_id=f"enhance_{entry_code}"
                        )
                    )
                    
                    if control_response.success and control_response.data:
                        controls = control_response.data.get("controls", [])
                        if controls:
                            control = controls[0]
                            profile = control.get("context_profile", {})
                            
                            # Enhance scores based on context profile
                            entry["numeric_score"] = self._calculate_context_score(profile, entry.get("numeric_score", 50.0))
                            entry["priority_order"] = profile.get("priority_in_context", entry.get("priority_order", 1))
                            entry["risk_score"] = profile.get("residual_risk_score", entry.get("risk_score"))
                            entry["rationale"] = f"{entry.get('rationale', '')} [Context-aware: {control.get('reasoning', '')[:200]}]"
                
                enhanced.append(entry)
            
            return enhanced
            
        except Exception as e:
            logger.warning(f"Error enhancing metadata with context: {str(e)}")
            return metadata_entries
    
    def _calculate_context_score(self, profile: Dict[str, Any], default_score: float) -> float:
        """Calculate numeric score from context profile"""
        risk_level = profile.get("risk_level", "")
        residual_risk = profile.get("residual_risk_score")
        
        if residual_risk is not None:
            # Convert 0-1 risk score to 0-100 numeric score
            return residual_risk * 100
        
        # Map risk level to score
        risk_level_map = {
            "critical": 90,
            "high": 75,
            "medium": 50,
            "low": 25
        }
        
        return risk_level_map.get(risk_level.lower(), default_score)
    
    def _entry_to_dict(self, entry: MetadataEntry) -> Dict[str, Any]:
        """Convert MetadataEntry to dictionary"""
        from ..state_helpers import entry_to_dict
        return entry_to_dict(entry)
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("MetadataGenerationPipeline cleaned up")

