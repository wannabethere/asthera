"""
Domain Adaptation Pipeline
Adapts learned patterns to target domain using contextual graphs for analogical reasoning
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from app.pipelines.base import ExtractionPipeline
from app.agents.domain_adaptation_agent import DomainAdaptationAgent
from app.agents.metadata_state import DomainMapping

logger = logging.getLogger(__name__)


class DomainAdaptationPipeline(ExtractionPipeline):
    """Pipeline for adapting patterns to target domain with contextual graph integration"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        contextual_graph_service: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize domain adaptation pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            contextual_graph_service: Optional contextual graph service for context-aware adaptation
        """
        super().__init__(
            name="domain_adaptation",
            version="1.0.0",
            description="Adapt learned patterns to target domain using contextual graphs",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.agent = DomainAdaptationAgent(llm=llm, model_name=model_name)
        self.contextual_graph_service = contextual_graph_service
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        if self.contextual_graph_service:
            logger.info("Domain adaptation pipeline initialized with contextual graph service")
        else:
            logger.info("Domain adaptation pipeline initialized (no contextual graph service)")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Adapt patterns to target domain with optional contextual graph integration
        
        Args:
            inputs: Dictionary with keys:
                - target_domain: Target domain name
                - target_documents: List of target domain document texts
                - learned_patterns: List of learned patterns from pattern recognition
                - source_domains: List of source domain names
                - use_contextual_graph: Whether to use contextual graphs (default: True if service available)
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with domain mappings, adaptation strategy, and analogical reasoning
        """
        if status_callback:
            status_callback("adapting", {"stage": "domain_adaptation_start"})
        
        target_domain = inputs.get("target_domain", "")
        target_documents = inputs.get("target_documents", [])
        learned_patterns = inputs.get("learned_patterns", [])
        source_domains = inputs.get("source_domains", [])
        use_contextual_graph = inputs.get("use_contextual_graph", self.contextual_graph_service is not None)
        
        try:
            # Create state from inputs
            from ..metadata_state import MetadataTransferLearningState
            from ..state_helpers import pattern_to_dict
            
            state: MetadataTransferLearningState = {
                "target_domain": target_domain,
                "target_documents": target_documents,
                "source_domains": source_domains,
                "learned_patterns": [pattern_to_dict(p) if hasattr(p, 'pattern_name') else p for p in learned_patterns],
                "domain_mappings": [],
                "adaptation_strategy": {},
                "analogical_reasoning": [],
                "status": "domain_adaptation",
                "current_step": "start",
                "messages": [],
                "errors": [],
                "warnings": []
            }
            
            # If using contextual graphs, enhance adaptation with context-aware mappings
            if use_contextual_graph and self.contextual_graph_service:
                if status_callback:
                    status_callback("processing", {"stage": "finding_context_mappings"})
                
                # Find target context
                target_context = await self._find_target_context(target_domain, target_documents)
                
                if target_context:
                    # Use multi-hop reasoning for analogical mappings
                    if status_callback:
                        status_callback("processing", {"stage": "analogical_reasoning"})
                    
                    context_mappings = await self._create_context_aware_mappings(
                        learned_patterns,
                        source_domains,
                        target_domain,
                        target_context
                    )
                    
                    if context_mappings:
                        # Merge with agent-generated mappings
                        state["domain_mappings"].extend(context_mappings)
                        logger.info(f"Created {len(context_mappings)} context-aware mappings")
            
            # Run domain adaptation agent
            if status_callback:
                status_callback("processing", {"stage": "adapting_patterns"})
            
            state = await self.agent(state)
            
            # Extract results
            from ..state_helpers import get_mappings_from_state
            mappings = get_mappings_from_state(state)
            
            if status_callback:
                status_callback("completed", {"stage": "domain_adaptation_complete"})
            
            return {
                "success": True,
                "data": {
                    "domain_mappings": [self._mapping_to_dict(m) for m in mappings],
                    "adaptation_strategy": state.get("adaptation_strategy", {}),
                    "analogical_reasoning": state.get("analogical_reasoning", []),
                    "mapping_count": len(mappings)
                },
                "state": state
            }
            
        except Exception as e:
            logger.error(f"Error in domain adaptation: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "domain_adaptation_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "domain_mappings": [],
                    "adaptation_strategy": {},
                    "analogical_reasoning": []
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
            from ..services.models import ContextSearchRequest
            
            context_query = f"{target_domain} compliance context: {target_documents[0][:500] if target_documents else ''}"
            response = await self.contextual_graph_service.search_contexts(
                ContextSearchRequest(
                    description=context_query,
                    top_k=1,
                    request_id=f"adapt_ctx_{target_domain}"
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
    
    async def _create_context_aware_mappings(
        self,
        patterns: List[Any],
        source_domains: List[str],
        target_domain: str,
        target_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create context-aware mappings using multi-hop reasoning"""
        if not self.contextual_graph_service:
            return []
        
        try:
            from app.services.models import ContextSearchRequest, MultiHopQueryRequest
            
            mappings = []
            target_context_id = target_context.get("context_id")
            
            # For each pattern, find source context and create mapping
            for pattern in patterns[:10]:  # Limit to avoid too many queries
                source_domain = pattern.get("source_domain") or (source_domains[0] if source_domains else "unknown")
                pattern_name = pattern.get("pattern_name", "")
                
                # Find source context
                source_response = await self.contextual_graph_service.search_contexts(
                    ContextSearchRequest(
                        description=f"{source_domain} compliance context",
                        filters={"regulatory_frameworks": source_domain} if source_domain else None,
                        top_k=1,
                        request_id=f"adapt_src_{source_domain}"
                    )
                )
                
                if source_response.success and source_response.data:
                    source_contexts = source_response.data.get("contexts", [])
                    
                    if source_contexts and target_context_id:
                        source_ctx = source_contexts[0]
                        source_context_id = source_ctx.get("context_id")
                        
                        # Use multi-hop query for analogical reasoning
                        mapping_query = f"Map {pattern_name} pattern from {source_domain} to {target_domain}"
                        reasoning_response = await self.contextual_graph_service.multi_hop_query(
                            MultiHopQueryRequest(
                                query=mapping_query,
                                context_id=target_context_id,
                                max_hops=2,
                                request_id=f"adapt_map_{pattern_name}"
                            )
                        )
                        
                        if reasoning_response.success and reasoning_response.data:
                            # Extract mappings from reasoning path
                            reasoning_path = reasoning_response.data.get("reasoning_path", [])
                            final_answer = reasoning_response.data.get("final_answer", "")
                            
                            # Create mapping from reasoning
                            mapping = {
                                "source_domain": source_domain,
                                "source_code": pattern_name,
                                "source_enum_type": pattern.get("pattern_type", ""),
                                "target_domain": target_domain,
                                "target_code": pattern_name,  # Could be refined
                                "target_enum_type": pattern.get("pattern_type", ""),
                                "mapping_type": "analogical",
                                "similarity_score": 0.7,  # Could be calculated from context similarity
                                "mapping_rationale": final_answer[:500]
                            }
                            mappings.append(mapping)
            
            return mappings
            
        except Exception as e:
            logger.warning(f"Error creating context-aware mappings: {str(e)}")
            return []
    
    def _mapping_to_dict(self, mapping: DomainMapping) -> Dict[str, Any]:
        """Convert DomainMapping to dictionary"""
        return {
            "source_domain": mapping.source_domain,
            "source_code": mapping.source_code,
            "source_enum_type": mapping.source_enum_type,
            "target_domain": mapping.target_domain,
            "target_code": mapping.target_code,
            "target_enum_type": mapping.target_enum_type,
            "mapping_type": mapping.mapping_type,
            "similarity_score": mapping.similarity_score,
            "mapping_rationale": mapping.mapping_rationale
        }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("DomainAdaptationPipeline cleaned up")

