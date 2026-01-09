"""
Configurable LLM extractor for creating context definitions from descriptions.

This extractor uses configurable rules to extract structured information,
allowing it to work for different domains (compliance, finance, healthcare, etc.)
"""
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from app.services.contextual_graph_storage import ContextDefinition
from .extraction_rules import ExtractionRules, get_compliance_context_rules

logger = logging.getLogger(__name__)


class ContextExtractor:
    """
    Extract context information from descriptions using configurable rules.
    
    Uses ExtractionRules to define what to extract, making it domain-agnostic.
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None
    ):
        """
        Initialize with LLM and extraction rules.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses compliance rules for backward compatibility.
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.rules = rules or get_compliance_context_rules()
        # Always use JSON parser if rules specify it, and create parser with schema hint
        if self.rules.use_json_parser:
            # Create JSON parser with pydantic model if fields are defined
            self.json_parser = JsonOutputParser()
        else:
            self.json_parser = None
    
    async def extract_context_from_description(
        self,
        description: str,
        context_id: Optional[str] = None,
        **kwargs
    ) -> ContextDefinition:
        """
        Extract structured context information from a natural language description.
        
        Args:
            description: Natural language description of the organization/situation
            context_id: Optional context ID (will be generated if not provided)
            **kwargs: Additional variables for prompt template
            
        Returns:
            ContextDefinition object (or dict if rules specify different output)
        """
        # Build system prompt from rules
        system_prompt = f"You are an {self.rules.system_role}.\n\n{self.rules.system_instructions}"
        
        # If using JSON parser, explicitly instruct to return strict JSON only (using markdown format for compactness)
        if self.rules.use_json_parser:
            system_prompt += "\n\n**Output Format:** Return ONLY valid JSON (no markdown, no code blocks, no explanations). Start with opening brace and end with closing brace."
        
        # Build prompt variables
        prompt_vars = {"description": description}
        prompt_vars.update(kwargs)
        
        # Get the human prompt template and escape any curly braces that aren't template variables
        # First, identify which variables are actually in the template
        import re
        template_vars = set(re.findall(r'\{(\w+)\}', self.rules.human_prompt_template))
        
        # Escape all curly braces that aren't template variables
        # We'll do this by replacing { with {{ and } with }}, then un-escaping the template variables
        human_prompt_template = self.rules.human_prompt_template
        # Escape all braces first
        human_prompt_template = human_prompt_template.replace("{", "{{").replace("}", "}}")
        # Un-escape template variables (need to handle both single and double escaping)
        for var in template_vars:
            # Replace {{{{var}}}} with {var} (double-escaped back to single)
            human_prompt_template = human_prompt_template.replace(f"{{{{{var}}}}}", f"{{{var}}}")
        
        # If using JSON parser, add compact markdown-formatted field list
        if self.rules.use_json_parser:
            # Build compact field descriptions using markdown
            if self.rules.fields:
                field_list = []
                for field in self.rules.fields:
                    field_info = f"- `{field.name}`"
                    if field.data_type != "string":
                        field_info += f" ({field.data_type})"
                    field_info += f": {field.description}"
                    if field.examples:
                        # Use markdown inline code for examples (no curly braces to escape)
                        examples_str = ', '.join(f"`{e}`" for e in field.examples[:3])
                        field_info += f" - examples: {examples_str}"
                    field_list.append(field_info)
                
                human_prompt_template += "\n\n**Extract these fields as JSON:**\n"
                human_prompt_template += "\n".join(field_list)
                human_prompt_template += "\n\nReturn ONLY valid JSON (no markdown, no code blocks)."
        
        # Create prompt template - let LangChain handle the formatting
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt_template)
        ])
        
        # Build chain
        if self.rules.use_json_parser and self.json_parser:
            chain = prompt | self.llm | self.json_parser
        else:
            chain = prompt | self.llm
        
        try:
            result = await chain.ainvoke(prompt_vars)
            
            # If not using JSON parser, result is a message object
            if not self.rules.use_json_parser:
                result = result.content if hasattr(result, 'content') else str(result)
                # For text output, return a dict with the text
                return {
                    "context_id": context_id or "ctx_auto",
                    "document": description,
                    "extracted_text": result
                }
            
            # For JSON output, create ContextDefinition (backward compatibility)
            # If rules specify different fields, return dict instead
            if self.rules.domain == "compliance":
                # Use existing ContextDefinition structure for compliance
                context = ContextDefinition(
                    context_id=context_id or f"ctx_{result.get('context_id', 'auto')}",
                    document=description,
                    context_type=result.get("context_type", "organizational_situational"),
                    industry=result.get("industry"),
                    organization_size=result.get("organization_size"),
                    employee_count_range=result.get("employee_count_range"),
                    maturity_level=result.get("maturity_level"),
                    regulatory_frameworks=result.get("regulatory_frameworks", []),
                    data_types=result.get("data_types", []),
                    systems=result.get("systems", []),
                    automation_capability=result.get("automation_capability"),
                    current_situation=result.get("current_situation"),
                    audit_timeline_days=result.get("audit_timeline_days"),
                    active_status=True
                )
                return context
            else:
                # For other domains, return dict with extracted fields
                return {
                    "context_id": context_id or f"ctx_{result.get('context_id', 'auto')}",
                    "document": description,
                    **result
                }
            
        except Exception as e:
            logger.error(f"Error extracting context: {str(e)}", exc_info=True)
            # Return minimal context on error
            if self.rules.domain == "compliance":
                return ContextDefinition(
                    context_id=context_id or "ctx_error",
                    document=description,
                    context_type="organizational_situational"
                )
            else:
                return {
                    "context_id": context_id or "ctx_error",
                    "document": description,
                    "error": str(e)
                }

