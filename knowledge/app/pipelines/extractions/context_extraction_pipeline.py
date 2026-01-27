"""
Context Extraction Pipeline
Extracts structured context information from organizational descriptions using configurable rules
"""
import logging
from typing import Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI

from app.services.contextual_graph_storage import ContextDefinition
from app.agents.extractors import ContextExtractor, ExtractionRules, get_compliance_context_rules
from app.pipelines.base import ExtractionPipeline

logger = logging.getLogger(__name__)


class ContextExtractionPipeline(ExtractionPipeline):
    """Pipeline for extracting context information from descriptions using configurable rules"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None,
        **kwargs
    ):
        """
        Initialize context extraction pipeline
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses compliance rules for backward compatibility.
        """
        super().__init__(
            name="context_extraction",
            version="2.0.0",
            description="Extract structured context from organizational descriptions using configurable rules",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.rules = rules or get_compliance_context_rules()
        self.extractor = ContextExtractor(llm=llm, model_name=model_name, rules=self.rules)
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("ContextExtractionPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract structured context information from description.
        
        Args:
            inputs: Dictionary with keys:
                - description: Natural language description
                - context_id: Optional context ID
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides (can include 'rules' for custom rules)
            **kwargs: Additional parameters passed to extractor
            
        Returns:
            Dictionary with ContextDefinition data
        """
        if status_callback:
            status_callback("extracting", {"stage": "extracting_context"})
        
        # Allow rules override via configuration
        if configuration and "rules" in configuration:
            from app.agents.extractors import ExtractionRules
            from langchain_core.output_parsers import JsonOutputParser
            if isinstance(configuration["rules"], dict):
                rules = ExtractionRules.from_dict(configuration["rules"])
            else:
                rules = configuration["rules"]
            self.extractor.rules = rules
            # Reinitialize JSON parser based on new rules
            if rules.use_json_parser:
                self.extractor.json_parser = JsonOutputParser()
            else:
                self.extractor.json_parser = None
        
        description = inputs.get("description", "")
        context_id = inputs.get("context_id")
        
        try:
            if status_callback:
                status_callback("processing", {"stage": "llm_extraction"})
            
            # Use the extractor with configurable rules
            context = await self.extractor.extract_context_from_description(
                description=description,
                context_id=context_id,
                **kwargs
            )
            
            # Handle both ContextDefinition and dict returns
            if isinstance(context, ContextDefinition):
                context_def = context
            elif isinstance(context, dict):
                # Convert dict to ContextDefinition for backward compatibility
                context_def = ContextDefinition(
                    context_id=context.get("context_id", context_id or "ctx_auto"),
                    document=description,
                    context_type=context.get("context_type", "organizational_situational"),
                    industry=context.get("industry"),
                    organization_size=context.get("organization_size"),
                    employee_count_range=context.get("employee_count_range"),
                    maturity_level=context.get("maturity_level"),
                    regulatory_frameworks=context.get("regulatory_frameworks", []),
                    data_types=context.get("data_types", []),
                    systems=context.get("systems", []),
                    automation_capability=context.get("automation_capability"),
                    current_situation=context.get("current_situation"),
                    audit_timeline_days=context.get("audit_timeline_days"),
                    active_status=True
                )
            else:
                raise ValueError(f"Unexpected return type from extractor: {type(context)}")
            
            if status_callback:
                status_callback("completed", {"stage": "extraction_complete"})
            
            return {
                "success": True,
                "data": {
                    "context_id": context_def.context_id,
                    "context_type": context_def.context_type,
                    "industry": context_def.industry,
                    "organization_size": context_def.organization_size,
                    "maturity_level": context_def.maturity_level,
                    "regulatory_frameworks": context_def.regulatory_frameworks,
                    "data_types": context_def.data_types,
                    "systems": context_def.systems,
                    "automation_capability": context_def.automation_capability,
                    "current_situation": context_def.current_situation,
                    "audit_timeline_days": context_def.audit_timeline_days
                },
                "context_definition": context_def
            }
            
        except Exception as e:
            logger.error(f"Error extracting context: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "extraction_failed", "error": str(e)})
            
            # Return minimal context on error
            context_def = ContextDefinition(
                context_id=context_id or "ctx_error",
                document=description,
                context_type="organizational_situational"
            )
            
            return {
                "success": False,
                "error": str(e),
                "context_definition": context_def
            }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("ContextExtractionPipeline cleaned up")

