"""
Validation Pipeline
Validates and refines generated metadata using contextual graphs for context-aware validation
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from .base import ExtractionPipeline
from ..validation_agent import ValidationAgent

logger = logging.getLogger(__name__)


class ValidationPipeline(ExtractionPipeline):
    """Pipeline for validating metadata with contextual graph integration"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        contextual_graph_service: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize validation pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            contextual_graph_service: Optional contextual graph service for context-aware validation
        """
        super().__init__(
            name="validation",
            version="1.0.0",
            description="Validate and refine metadata using contextual graphs",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.agent = ValidationAgent(llm=llm, model_name=model_name)
        self.contextual_graph_service = contextual_graph_service
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        if self.contextual_graph_service:
            logger.info("Validation pipeline initialized with contextual graph service")
        else:
            logger.info("Validation pipeline initialized (no contextual graph service)")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate metadata entries with optional contextual graph integration
        
        Args:
            inputs: Dictionary with keys:
                - target_domain: Target domain name
                - generated_metadata: List of generated metadata entries
                - learned_patterns: List of learned patterns
                - use_contextual_graph: Whether to use contextual graphs (default: True if service available)
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with validation results, issues, and refined metadata
        """
        if status_callback:
            status_callback("validating", {"stage": "validation_start"})
        
        target_domain = inputs.get("target_domain", "")
        generated_metadata = inputs.get("generated_metadata", [])
        learned_patterns = inputs.get("learned_patterns", [])
        use_contextual_graph = inputs.get("use_contextual_graph", self.contextual_graph_service is not None)
        
        try:
            # Create state from inputs
            from ..metadata_state import MetadataTransferLearningState
            from ..state_helpers import pattern_to_dict, entry_to_dict
            
            state: MetadataTransferLearningState = {
                "target_domain": target_domain,
                "generated_metadata": [entry_to_dict(e) if hasattr(e, 'code') else e for e in generated_metadata],
                "learned_patterns": [pattern_to_dict(p) if hasattr(p, 'pattern_name') else p for p in learned_patterns],
                "validation_results": {},
                "validation_issues": [],
                "refined_metadata": [],
                "quality_scores": {},
                "overall_confidence": 0.0,
                "status": "validation",
                "current_step": "start",
                "messages": [],
                "errors": [],
                "warnings": []
            }
            
            # If using contextual graphs, enhance validation with context-aware checks
            if use_contextual_graph and self.contextual_graph_service:
                if status_callback:
                    status_callback("processing", {"stage": "context_aware_validation"})
                
                # Find target context
                target_context = await self._find_target_context(target_domain)
                
                if target_context:
                    # Validate against context profiles
                    context_validation = await self._validate_against_context(
                        generated_metadata,
                        target_context
                    )
                    
                    # Merge with agent validation
                    state["validation_results"].update(context_validation)
            
            # Run validation agent
            if status_callback:
                status_callback("processing", {"stage": "validating_metadata"})
            
            state = await self.agent(state)
            
            # Extract results
            from ..state_helpers import get_entries_from_state
            refined_entries = get_entries_from_state(state)
            
            if status_callback:
                status_callback("completed", {"stage": "validation_complete"})
            
            return {
                "success": True,
                "data": {
                    "validation_results": state.get("validation_results", {}),
                    "validation_issues": state.get("validation_issues", []),
                    "refined_metadata": [self._entry_to_dict(e) for e in refined_entries],
                    "quality_scores": state.get("quality_scores", {}),
                    "overall_confidence": state.get("overall_confidence", 0.0),
                    "issue_count": len(state.get("validation_issues", []))
                },
                "state": state
            }
            
        except Exception as e:
            logger.error(f"Error in validation: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "validation_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "validation_results": {},
                    "validation_issues": [],
                    "refined_metadata": [],
                    "quality_scores": {},
                    "overall_confidence": 0.0
                }
            }
    
    async def _find_target_context(self, target_domain: str) -> Optional[Dict[str, Any]]:
        """Find matching context for target domain"""
        if not self.contextual_graph_service:
            return None
        
        try:
            from app.services.models import ContextSearchRequest
            
            context_query = f"{target_domain} compliance validation context"
            response = await self.contextual_graph_service.search_contexts(
                ContextSearchRequest(
                    description=context_query,
                    top_k=1,
                    request_id=f"val_ctx_{target_domain}"
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
    
    async def _validate_against_context(
        self,
        metadata_entries: List[Dict[str, Any]],
        target_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate metadata entries against context profiles"""
        if not self.contextual_graph_service:
            return {}
        
        try:
            from app.services.models import ControlSearchRequest
            
            context_id = target_context.get("context_id")
            if not context_id:
                return {}
            
            validation_results = {}
            
            for entry in metadata_entries:
                entry_code = entry.get("code", "")
                entry_desc = entry.get("description", "")
                
                if entry_code or entry_desc:
                    control_response = await self.contextual_graph_service.search_controls(
                        ControlSearchRequest(
                            context_id=context_id,
                            query=entry_desc or entry_code,
                            top_k=1,
                            request_id=f"val_{entry_code}"
                        )
                    )
                    
                    if control_response.success and control_response.data:
                        controls = control_response.data.get("controls", [])
                        if controls:
                            control = controls[0]
                            profile = control.get("context_profile", {})
                            
                            # Validate entry against profile
                            validation_results[entry_code] = {
                                "is_valid": True,
                                "completeness_score": self._check_completeness(entry, profile),
                                "consistency_score": self._check_consistency(entry, profile),
                                "accuracy_score": self._check_accuracy(entry, profile),
                                "issues": [],
                                "suggestions": self._generate_suggestions(entry, profile)
                            }
            
            return validation_results
            
        except Exception as e:
            logger.warning(f"Error validating against context: {str(e)}")
            return {}
    
    def _check_completeness(self, entry: Dict[str, Any], profile: Dict[str, Any]) -> float:
        """Check if entry is complete based on profile"""
        required_fields = ["code", "description", "numeric_score"]
        present_fields = sum(1 for field in required_fields if entry.get(field))
        return present_fields / len(required_fields)
    
    def _check_consistency(self, entry: Dict[str, Any], profile: Dict[str, Any]) -> float:
        """Check if entry scores are consistent with profile"""
        entry_score = entry.get("numeric_score", 50.0)
        profile_risk = profile.get("residual_risk_score")
        
        if profile_risk is not None:
            expected_score = profile_risk * 100
            # Score within 20 points is considered consistent
            diff = abs(entry_score - expected_score)
            return max(0.0, 1.0 - (diff / 20.0))
        
        return 0.7  # Default consistency if no profile risk score
    
    def _check_accuracy(self, entry: Dict[str, Any], profile: Dict[str, Any]) -> float:
        """Check if entry accurately reflects profile"""
        # Combine completeness and consistency
        completeness = self._check_completeness(entry, profile)
        consistency = self._check_consistency(entry, profile)
        return (completeness + consistency) / 2.0
    
    def _generate_suggestions(self, entry: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
        """Generate suggestions for improving entry based on profile"""
        suggestions = []
        
        profile_risk = profile.get("residual_risk_score")
        if profile_risk is not None:
            expected_score = profile_risk * 100
            current_score = entry.get("numeric_score", 50.0)
            
            if abs(current_score - expected_score) > 10:
                suggestions.append(f"Consider adjusting numeric_score to {expected_score:.1f} based on context profile")
        
        risk_level = profile.get("risk_level", "")
        if risk_level:
            suggestions.append(f"Risk level in context: {risk_level}")
        
        return suggestions
    
    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        """Convert entry to dictionary"""
        from ..state_helpers import entry_to_dict
        if hasattr(entry, 'code'):
            return entry_to_dict(entry)
        return entry
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("ValidationPipeline cleaned up")

