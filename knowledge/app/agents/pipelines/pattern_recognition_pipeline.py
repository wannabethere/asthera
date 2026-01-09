"""
Pattern Recognition Pipeline
Extracts transferable patterns from source domain metadata using contextual graphs
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from .base import ExtractionPipeline
from ..pattern_recognition_agent import PatternRecognitionAgent
from ..metadata_state import MetadataPattern

logger = logging.getLogger(__name__)


class PatternRecognitionPipeline(ExtractionPipeline):
    """Pipeline for recognizing patterns from source domains with contextual graph integration"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        contextual_graph_service: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize pattern recognition pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            contextual_graph_service: Optional contextual graph service for context-aware pattern retrieval
        """
        super().__init__(
            name="pattern_recognition",
            version="1.0.0",
            description="Extract transferable patterns from source domain metadata using contextual graphs",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.agent = PatternRecognitionAgent(llm=llm, model_name=model_name)
        self.contextual_graph_service = contextual_graph_service
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        if self.contextual_graph_service:
            logger.info("Pattern recognition pipeline initialized with contextual graph service")
        else:
            logger.info("Pattern recognition pipeline initialized (no contextual graph service)")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract patterns from source domains with optional contextual graph integration
        
        Args:
            inputs: Dictionary with keys:
                - source_domains: List of source domain names
                - source_metadata: Optional pre-loaded metadata (if not provided, will load)
                - use_contextual_graph: Whether to use contextual graphs (default: True if service available)
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with learned patterns and analysis
        """
        if status_callback:
            status_callback("extracting", {"stage": "pattern_recognition_start"})
        
        source_domains = inputs.get("source_domains", [])
        use_contextual_graph = inputs.get("use_contextual_graph", self.contextual_graph_service is not None)
        
        try:
            # Create initial state
            from ..metadata_state import MetadataTransferLearningState
            state: MetadataTransferLearningState = {
                "source_domains": source_domains,
                "source_metadata": inputs.get("source_metadata", []),
                "learned_patterns": [],
                "pattern_analysis": {},
                "status": "pattern_learning",
                "current_step": "start",
                "messages": [],
                "errors": [],
                "warnings": []
            }
            
            # If using contextual graphs, enhance source metadata
            if use_contextual_graph and self.contextual_graph_service:
                if status_callback:
                    status_callback("processing", {"stage": "loading_context_aware_patterns"})
                
                # Load context-aware patterns from contextual graphs
                context_patterns = await self._load_context_aware_patterns(source_domains)
                if context_patterns:
                    state["source_metadata"].extend(context_patterns)
                    logger.info(f"Loaded {len(context_patterns)} context-aware patterns")
            
            # Run pattern recognition agent
            if status_callback:
                status_callback("processing", {"stage": "analyzing_patterns"})
            
            state = await self.agent(state)
            
            # Extract results
            from ..state_helpers import get_patterns_from_state
            patterns = get_patterns_from_state(state)
            
            if status_callback:
                status_callback("completed", {"stage": "pattern_recognition_complete"})
            
            return {
                "success": True,
                "data": {
                    "patterns": [self._pattern_to_dict(p) for p in patterns],
                    "pattern_analysis": state.get("pattern_analysis", {}),
                    "pattern_count": len(patterns),
                    "source_domains": source_domains
                },
                "state": state
            }
            
        except Exception as e:
            logger.error(f"Error in pattern recognition: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "pattern_recognition_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "patterns": [],
                    "pattern_analysis": {},
                    "pattern_count": 0
                }
            }
    
    async def _load_context_aware_patterns(self, source_domains: List[str]) -> List[Dict[str, Any]]:
        """Load patterns from contextual graphs for source domains"""
        if not self.contextual_graph_service:
            return []
        
        try:
            from app.services.models import ContextSearchRequest, PriorityControlsRequest
            
            all_patterns = []
            
            # Search for relevant contexts for each source domain
            for domain in source_domains:
                context_query = f"Compliance metadata patterns for {domain} domain"
                context_response = await self.contextual_graph_service.search_contexts(
                    ContextSearchRequest(
                        description=context_query,
                        top_k=5,
                        request_id=f"pattern_ctx_{domain}"
                    )
                )
                
                if context_response.success and context_response.data:
                    contexts = context_response.data.get("contexts", [])
                    
                    # Get control profiles for each context (these contain patterns)
                    for context in contexts:
                        context_id = context.get("context_id")
                        if context_id:
                            controls_response = await self.contextual_graph_service.get_priority_controls(
                                PriorityControlsRequest(
                                    context_id=context_id,
                                    top_k=20,
                                    request_id=f"pattern_ctrl_{context_id}"
                                )
                            )
                            
                            if controls_response.success and controls_response.data:
                                controls = controls_response.data.get("controls", [])
                                
                                # Extract patterns from control profiles
                                for control in controls:
                                    pattern = self._extract_pattern_from_control(control, domain)
                                    if pattern:
                                        all_patterns.append(pattern)
            
            return all_patterns
            
        except Exception as e:
            logger.warning(f"Error loading context-aware patterns: {str(e)}")
            return []
    
    def _extract_pattern_from_control(self, control: Dict[str, Any], source_domain: str) -> Optional[Dict[str, Any]]:
        """Extract pattern structure from control profile"""
        try:
            profile = control.get("context_profile", {})
            reasoning = control.get("reasoning", "")
            
            return {
                "domain_name": source_domain,
                "pattern_name": f"{control.get('control_id', 'unknown')}_pattern",
                "pattern_type": "scoring",  # or determine from profile
                "pattern_structure": {
                    "risk_level": profile.get("risk_level"),
                    "residual_risk_score": profile.get("residual_risk_score"),
                    "implementation_complexity": profile.get("implementation_complexity"),
                    "estimated_effort_hours": profile.get("estimated_effort_hours")
                },
                "pattern_examples": [reasoning] if reasoning else [],
                "description": reasoning[:500] if reasoning else ""
            }
        except Exception as e:
            logger.warning(f"Error extracting pattern from control: {str(e)}")
            return None
    
    def _pattern_to_dict(self, pattern: MetadataPattern) -> Dict[str, Any]:
        """Convert MetadataPattern to dictionary"""
        return {
            "pattern_name": pattern.pattern_name,
            "pattern_type": pattern.pattern_type,
            "source_domain": pattern.source_domain,
            "pattern_structure": pattern.pattern_structure,
            "pattern_examples": pattern.pattern_examples,
            "confidence": pattern.confidence,
            "description": pattern.description
        }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("PatternRecognitionPipeline cleaned up")

