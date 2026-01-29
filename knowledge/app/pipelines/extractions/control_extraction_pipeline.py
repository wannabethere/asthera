"""
Control Extraction Pipeline
Extracts control information from regulatory text and creates rich documents using configurable rules
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI
import json

from app.agents.extractors.control_extractor import ControlExtractor
from app.agents.extractors.extraction_rules import ExtractionRules, get_compliance_control_rules
from app.pipelines.base import ExtractionPipeline

logger = logging.getLogger(__name__)


class ControlExtractionPipeline(ExtractionPipeline):
    """Pipeline for extracting control information from regulatory text using configurable rules"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None,
        **kwargs
    ):
        """
        Initialize control extraction pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses compliance rules for backward compatibility.
        """
        super().__init__(
            name="control_extraction",
            version="2.0.0",
            description="Extract control information from regulatory text using configurable rules",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.rules = rules or get_compliance_control_rules()
        self.extractor = ControlExtractor(llm=llm, model_name=model_name, rules=self.rules)
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("ControlExtractionPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract control information from regulatory text.
        
        Args:
            inputs: Dictionary with keys:
                - text: Regulatory text
                - framework: Framework name (e.g., "HIPAA")
                - context_metadata: Optional context metadata
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides (can include 'rules' for custom rules)
            **kwargs: Additional parameters passed to extractor
            
        Returns:
            Dictionary with extracted control information
        """
        if status_callback:
            status_callback("extracting", {"stage": "extracting_control"})
        
        # Allow rules override via configuration
        if configuration and "rules" in configuration:
            if isinstance(configuration["rules"], dict):
                rules = ExtractionRules.from_dict(configuration["rules"])
            else:
                rules = configuration["rules"]
            self.extractor.rules = rules
        
        text = inputs.get("text", "")
        framework = inputs.get("framework", "")
        context_metadata = inputs.get("context_metadata", {})
        
        try:
            if status_callback:
                status_callback("processing", {"stage": "llm_extraction"})
            
            # Use the extractor with configurable rules
            result = await self.extractor.extract_control_from_text(
                text=text,
                framework=framework,
                context_metadata=context_metadata,
                **kwargs
            )
            
            if status_callback:
                status_callback("completed", {"stage": "extraction_complete"})
            
            return {
                "success": True,
                "data": result,
                "metadata": {
                    "framework": framework,
                    "has_context": bool(context_metadata)
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting control: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "extraction_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def create_control_profile(
        self,
        control_id: str,
        control_name: str,
        control_description: str,
        framework: str,
        context_metadata: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> str:
        """Create a rich control-context profile document using configurable rules"""
        if status_callback:
            status_callback("creating_profile", {"stage": "profile_creation"})
        
        try:
            # Use the extractor's profile creation method which uses rules
            result = await self.extractor.create_control_profile_document(
                control_id=control_id,
                control_name=control_name,
                control_description=control_description,
                framework=framework,
                context_metadata=context_metadata
            )
            
            if status_callback:
                status_callback("completed", {"stage": "profile_created"})
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating control profile: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "profile_creation_failed", "error": str(e)})
            return ""
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("ControlExtractionPipeline cleaned up")

