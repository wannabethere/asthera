"""
Requirement Extraction Pipeline
Creates contextual requirement documents using configurable rules
"""
import logging
from typing import Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI

from app.agents.extractors import RequirementExtractor, ExtractionRules, get_compliance_requirement_rules
from app.pipelines.base import ExtractionPipeline

logger = logging.getLogger(__name__)


class RequirementExtractionPipeline(ExtractionPipeline):
    """Pipeline for creating requirement documents using configurable rules"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None,
        **kwargs
    ):
        """
        Initialize requirement extraction pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses compliance rules for backward compatibility.
        """
        super().__init__(
            name="requirement_extraction",
            version="2.0.0",
            description="Create contextual requirement documents using configurable rules",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.rules = rules or get_compliance_requirement_rules()
        self.extractor = RequirementExtractor(llm=llm, model_name=model_name, rules=self.rules)
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("RequirementExtractionPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a contextual requirement document.
        
        Args:
            inputs: Dictionary with keys:
                - requirement_text: Requirement text
                - control_id: Control ID
                - context_metadata: Context metadata
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides (can include 'rules' for custom rules)
            **kwargs: Additional parameters passed to extractor
            
        Returns:
            Dictionary with requirement document
        """
        if status_callback:
            status_callback("creating", {"stage": "creating_requirement_doc"})
        
        # Allow rules override via configuration
        if configuration and "rules" in configuration:
            from app.agents.extractors import ExtractionRules
            if isinstance(configuration["rules"], dict):
                rules = ExtractionRules.from_dict(configuration["rules"])
            else:
                rules = configuration["rules"]
            self.extractor.rules = rules
        
        requirement_text = inputs.get("requirement_text", "")
        control_id = inputs.get("control_id", "")
        context_metadata = inputs.get("context_metadata", {})
        
        try:
            if status_callback:
                status_callback("processing", {"stage": "llm_generation"})
            
            # Use the extractor with configurable rules
            document = await self.extractor.create_requirement_edge_document(
                requirement_text=requirement_text,
                control_id=control_id,
                context_metadata=context_metadata,
                **kwargs
            )
            
            if status_callback:
                status_callback("completed", {"stage": "document_created"})
            
            return {
                "success": True,
                "data": {
                    "document": document,
                    "requirement_text": requirement_text,
                    "control_id": control_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating requirement document: {str(e)}", exc_info=True)
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
        logger.info("RequirementExtractionPipeline cleaned up")

