"""
Metadata Generation Action Service
Generates metadata for user actions based on all available contexts
"""
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI

from .base import BaseService, ServiceRequest, ServiceResponse
from .models import MetadataGenerationActionRequest, MetadataGenerationActionResponse
from .contextual_graph_service import ContextualGraphService
# Lazy import to avoid circular dependency with app.pipelines
# from app.pipelines import (
#     PatternRecognitionPipeline,
#     DomainAdaptationPipeline,
#     MetadataGenerationPipeline,
#     ValidationPipeline
# )

logger = logging.getLogger(__name__)


class MetadataGenerationActionService(BaseService[ServiceRequest, ServiceResponse]):
    """
    Service that generates metadata for user actions using all available contexts.
    
    Orchestrates the full metadata transfer learning workflow:
    1. Pattern Recognition (with context-aware patterns)
    2. Domain Adaptation (with context-aware mappings)
    3. Metadata Generation (with context-aware scoring)
    4. Validation (with context-aware validation)
    """
    
    def __init__(
        self,
        contextual_graph_service: ContextualGraphService,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        maxsize: int = 1_000_000,
        ttl: int = 600  # 10 minutes for metadata generation
    ):
        """Initialize metadata generation action service"""
        super().__init__(maxsize=maxsize, ttl=ttl)
        
        self.contextual_graph_service = contextual_graph_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        
        # Lazy import to avoid circular dependency
        from app.pipelines import (
            PatternRecognitionPipeline,
            DomainAdaptationPipeline,
            MetadataGenerationPipeline,
            ValidationPipeline
        )
        
        # Initialize pipelines with contextual graph service
        self.pattern_pipeline = PatternRecognitionPipeline(
            llm=self.llm,
            model_name=model_name,
            contextual_graph_service=contextual_graph_service
        )
        self.adaptation_pipeline = DomainAdaptationPipeline(
            llm=self.llm,
            model_name=model_name,
            contextual_graph_service=contextual_graph_service
        )
        self.generation_pipeline = MetadataGenerationPipeline(
            llm=self.llm,
            model_name=model_name,
            contextual_graph_service=contextual_graph_service
        )
        self.validation_pipeline = ValidationPipeline(
            llm=self.llm,
            model_name=model_name,
            contextual_graph_service=contextual_graph_service
        )
    
    async def initialize(self) -> None:
        """Initialize all pipelines"""
        await self.pattern_pipeline.initialize()
        await self.adaptation_pipeline.initialize()
        await self.generation_pipeline.initialize()
        await self.validation_pipeline.initialize()
        logger.info("MetadataGenerationActionService initialized")
    
    async def generate_metadata_for_action(
        self,
        request: MetadataGenerationActionRequest
    ) -> MetadataGenerationActionResponse:
        """
        Generate metadata for a user action based on all available contexts
        
        Args:
            request: MetadataGenerationActionRequest with user action and context information
            
        Returns:
            MetadataGenerationActionResponse with generated metadata and reasoning
        """
        try:
            user_action = request.user_action
            target_domain = request.target_domain
            target_documents = request.target_documents
            source_domains = request.source_domains or ["cybersecurity"]
            target_framework = request.target_framework
            context_ids = request.context_ids
            use_all_contexts = request.use_all_contexts
            
            # Step 1: Find relevant contexts
            relevant_contexts = await self._find_relevant_contexts(
                user_action,
                target_domain,
                context_ids,
                use_all_contexts
            )
            
            # Step 2: Pattern Recognition
            logger.info("Starting pattern recognition...")
            pattern_result = await self.pattern_pipeline.run(
                inputs={
                    "source_domains": source_domains,
                    "use_contextual_graph": True
                }
            )
            
            if not pattern_result.get("success"):
                return MetadataGenerationActionResponse(
                    success=False,
                    error=f"Pattern recognition failed: {pattern_result.get('error')}",
                    request_id=request.request_id
                )
            
            learned_patterns = pattern_result["data"]["patterns"]
            
            # Step 3: Domain Adaptation
            logger.info("Starting domain adaptation...")
            adaptation_result = await self.adaptation_pipeline.run(
                inputs={
                    "target_domain": target_domain,
                    "target_documents": target_documents,
                    "learned_patterns": learned_patterns,
                    "source_domains": source_domains,
                    "use_contextual_graph": True
                }
            )
            
            if not adaptation_result.get("success"):
                return MetadataGenerationActionResponse(
                    success=False,
                    error=f"Domain adaptation failed: {adaptation_result.get('error')}",
                    request_id=request.request_id
                )
            
            domain_mappings = adaptation_result["data"]["domain_mappings"]
            adaptation_strategy = adaptation_result["data"]["adaptation_strategy"]
            
            # Step 4: Metadata Generation
            logger.info("Starting metadata generation...")
            generation_result = await self.generation_pipeline.run(
                inputs={
                    "target_domain": target_domain,
                    "target_documents": target_documents,
                    "target_framework": target_framework,
                    "learned_patterns": learned_patterns,
                    "domain_mappings": domain_mappings,
                    "adaptation_strategy": adaptation_strategy,
                    "use_contextual_graph": True
                }
            )
            
            if not generation_result.get("success"):
                return MetadataGenerationActionResponse(
                    success=False,
                    error=f"Metadata generation failed: {generation_result.get('error')}",
                    request_id=request.request_id
                )
            
            generated_metadata = generation_result["data"]["metadata_entries"]
            
            # Step 5: Validation
            logger.info("Starting validation...")
            validation_result = await self.validation_pipeline.run(
                inputs={
                    "target_domain": target_domain,
                    "generated_metadata": generated_metadata,
                    "learned_patterns": learned_patterns,
                    "use_contextual_graph": True
                }
            )
            
            if not validation_result.get("success"):
                logger.warning(f"Validation had issues: {validation_result.get('error')}")
                # Continue with generated metadata even if validation fails
            
            refined_metadata = validation_result["data"].get("refined_metadata", generated_metadata)
            
            # Compile results
            return MetadataGenerationActionResponse(
                success=True,
                data={
                    "metadata_entries": refined_metadata,
                    "generation_summary": {
                        "total_entries": len(refined_metadata),
                        "patterns_learned": len(learned_patterns),
                        "mappings_created": len(domain_mappings),
                        "contexts_used": len(relevant_contexts),
                        "validation_confidence": validation_result["data"].get("overall_confidence", 0.0)
                    },
                    "reasoning": {
                        "user_action": user_action,
                        "target_domain": target_domain,
                        "source_domains": source_domains,
                        "adaptation_strategy": adaptation_strategy,
                        "contexts_considered": [
                            {
                                "context_id": ctx.get("context_id"),
                                "relevance_score": ctx.get("combined_score", 0.0)
                            }
                            for ctx in relevant_contexts
                        ]
                    },
                    "validation_results": validation_result["data"].get("validation_results", {}),
                    "quality_scores": validation_result["data"].get("quality_scores", {})
                },
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error generating metadata for action: {str(e)}", exc_info=True)
            return MetadataGenerationActionResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def _find_relevant_contexts(
        self,
        user_action: str,
        target_domain: str,
        context_ids: Optional[List[str]],
        use_all_contexts: bool
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
                        request_id=f"meta_action_ctx_{ctx_id}"
                    )
                )
                if response.success and response.data:
                    contexts.extend(response.data.get("contexts", []))
        
        # Search for relevant contexts
        if use_all_contexts or not context_ids:
            search_query = f"{user_action} in {target_domain} domain"
            
            response = await self.contextual_graph_service.search_contexts(
                ContextSearchRequest(
                    description=search_query,
                    top_k=10,
                    request_id=f"meta_action_all_{target_domain}"
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
    
    async def _process_request_impl(self, request) -> ServiceResponse:
        """Route requests to appropriate handlers"""
        if isinstance(request, MetadataGenerationActionRequest):
            return await self.generate_metadata_for_action(request)
        else:
            return ServiceResponse(
                success=False,
                error=f"Unknown request type: {type(request)}",
                request_id=getattr(request, 'request_id', None)
            )
    
    async def cleanup(self) -> None:
        """Clean up service resources"""
        await self.pattern_pipeline.cleanup()
        await self.adaptation_pipeline.cleanup()
        await self.generation_pipeline.cleanup()
        await self.validation_pipeline.cleanup()
        logger.info("MetadataGenerationActionService cleaned up")

