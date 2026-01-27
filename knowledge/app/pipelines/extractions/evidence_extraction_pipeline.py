"""
Evidence Extraction Pipeline
Creates evidence collection guides using configurable rules
"""
import logging
from typing import Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI

from app.agents.extractors import EvidenceExtractor, ExtractionRules, get_compliance_evidence_rules
from app.pipelines.base import ExtractionPipeline

logger = logging.getLogger(__name__)


class EvidenceExtractionPipeline(ExtractionPipeline):
    """Pipeline for creating evidence documents using configurable rules"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None,
        **kwargs
    ):
        """
        Initialize evidence extraction pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses compliance rules for backward compatibility.
        """
        super().__init__(
            name="evidence_extraction",
            version="2.0.0",
            description="Create evidence collection guides using configurable rules",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.rules = rules or get_compliance_evidence_rules()
        self.extractor = EvidenceExtractor(llm=llm, model_name=model_name, rules=self.rules)
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("EvidenceExtractionPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a contextual evidence document.
        
        Args:
            inputs: Dictionary with keys:
                - evidence_name: Evidence type name
                - requirement_id: Requirement ID
                - context_metadata: Context metadata
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides (can include 'rules' for custom rules)
            **kwargs: Additional parameters passed to extractor
            
        Returns:
            Dictionary with evidence document
        """
        if status_callback:
            status_callback("creating", {"stage": "creating_evidence_doc"})
        
        # Allow rules override via configuration
        if configuration and "rules" in configuration:
            from app.agents.extractors import ExtractionRules
            if isinstance(configuration["rules"], dict):
                rules = ExtractionRules.from_dict(configuration["rules"])
            else:
                rules = configuration["rules"]
            self.extractor.rules = rules
        
        evidence_name = inputs.get("evidence_name", "")
        requirement_id = inputs.get("requirement_id", "")
        context_metadata = inputs.get("context_metadata", {})
        
        try:
            if status_callback:
                status_callback("processing", {"stage": "llm_generation"})
            
            # Use the extractor with configurable rules
            document = await self.extractor.create_evidence_edge_document(
                evidence_name=evidence_name,
                requirement_id=requirement_id,
                context_metadata=context_metadata,
                **kwargs
            )
            
            if status_callback:
                status_callback("completed", {"stage": "document_created"})
            
            return {
                "success": True,
                "data": {
                    "document": document,
                    "evidence_name": evidence_name,
                    "requirement_id": requirement_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating evidence document: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "document_creation_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("EvidenceExtractionPipeline cleaned up")

