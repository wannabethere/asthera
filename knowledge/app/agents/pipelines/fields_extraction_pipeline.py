"""
Fields Extraction Pipeline
Extracts fields from text and creates contextual edges using configurable rules
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from app.agents.extractors import FieldsExtractor, ExtractionRules, get_default_fields_rules
from .base import ExtractionPipeline

logger = logging.getLogger(__name__)


class FieldsExtractionPipeline(ExtractionPipeline):
    """Pipeline for extracting fields from text and creating contextual edges"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None,
        **kwargs
    ):
        """
        Initialize fields extraction pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses default rules.
        """
        super().__init__(
            name="fields_extraction",
            version="1.0.0",
            description="Extract fields from text and create contextual edges using configurable rules",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.rules = rules or get_default_fields_rules()
        self.extractor = FieldsExtractor(llm=llm, model_name=model_name, rules=self.rules)
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("FieldsExtractionPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract fields from text and create contextual edges.
        
        Args:
            inputs: Dictionary with keys:
                - text: Text to extract fields from
                - context_id: Context ID for creating edges
                - source_entity_id: Optional source entity ID
                - source_entity_type: Optional source entity type
                - field_definitions: Optional list of field definitions
                - context_metadata: Optional context metadata
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides (can include 'rules' for custom rules)
            **kwargs: Additional parameters passed to extractor
            
        Returns:
            Dictionary with extracted fields and edges
        """
        if status_callback:
            status_callback("extracting", {"stage": "extracting_fields"})
        
        # Allow rules override via configuration
        if configuration and "rules" in configuration:
            from app.agents.extractors import ExtractionRules
            if isinstance(configuration["rules"], dict):
                rules = ExtractionRules.from_dict(configuration["rules"])
            else:
                rules = configuration["rules"]
            self.extractor.rules = rules
        
        text = inputs.get("text", "")
        context_id = inputs.get("context_id", "")
        source_entity_id = inputs.get("source_entity_id")
        source_entity_type = inputs.get("source_entity_type")
        field_definitions = inputs.get("field_definitions")
        context_metadata = inputs.get("context_metadata", {})
        
        try:
            if status_callback:
                status_callback("processing", {"stage": "llm_extraction"})
            
            # Use the extractor with configurable rules
            result = await self.extractor.extract_fields_and_create_edges(
                text=text,
                context_id=context_id,
                source_entity_id=source_entity_id,
                source_entity_type=source_entity_type,
                field_definitions=field_definitions,
                context_metadata=context_metadata,
                **kwargs
            )
            
            if status_callback:
                status_callback("completed", {"stage": "extraction_complete"})
            
            return {
                "success": True,
                "data": {
                    "extracted_fields": result.get("extracted_fields", []),
                    "edges": [
                        {
                            "edge_id": edge.edge_id,
                            "edge_type": edge.edge_type,
                            "source_entity_id": edge.source_entity_id,
                            "target_entity_id": edge.target_entity_id,
                            "context_id": edge.context_id
                        }
                        for edge in result.get("edges", [])
                    ],
                    "edges_count": len(result.get("edges", []))
                },
                "edges": result.get("edges", []),  # Full edge objects for direct use
                "metadata": {
                    "context_id": context_id,
                    "fields_extracted": len(result.get("extracted_fields", []))
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting fields: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "extraction_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "extracted_fields": [],
                    "edges": []
                }
            }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("FieldsExtractionPipeline cleaned up")

