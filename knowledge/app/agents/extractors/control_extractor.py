"""
Configurable LLM extractor for creating control/entity documents from text.

This extractor uses configurable rules to extract structured information,
allowing it to work for different domains and entity types.
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from .extraction_rules import ExtractionRules, get_compliance_control_rules

logger = logging.getLogger(__name__)


class ControlExtractor:
    """
    Extract control/entity information and create rich documents using configurable rules.
    
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
        self.rules = rules or get_compliance_control_rules()
        self.json_parser = JsonOutputParser() if self.rules.use_json_parser else None
    
    async def extract_control_from_text(
        self,
        text: str,
        framework: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract control/entity information from text and create rich document.
        
        Args:
            text: Text to extract from
            framework: Optional framework/domain identifier
            context_metadata: Optional context metadata
            **kwargs: Additional variables for prompt template
            
        Returns:
            Dictionary with extracted information
        """
        # Build system prompt from rules
        system_prompt = f"You are an {self.rules.system_role}.\n\n{self.rules.system_instructions}"
        
        # If using JSON parser, explicitly instruct to return strict JSON only (using markdown format)
        if self.rules.use_json_parser:
            system_prompt += "\n\n**Output Format:** Return ONLY valid JSON (no markdown, no code blocks, no explanations). Start with opening brace and end with closing brace."
        
        # Build prompt variables
        prompt_vars = {"text": text}
        if framework:
            prompt_vars["framework"] = framework
        
        # Convert context_metadata to JSON string and escape curly braces to prevent LangChain from treating them as template variables
        if context_metadata:
            if isinstance(context_metadata, dict):
                context_metadata_str = json.dumps(context_metadata, indent=2)
            else:
                context_metadata_str = str(context_metadata)
            # Escape curly braces in JSON string to prevent LangChain from treating them as template variables
            context_metadata_str = context_metadata_str.replace("{", "{{").replace("}", "}}")
            prompt_vars["context_metadata"] = context_metadata_str
        else:
            prompt_vars["context_metadata"] = "{}"
        
        prompt_vars.update(kwargs)
        
        # Build human prompt template - add compact JSON format instruction if needed
        human_prompt_template = self.rules.human_prompt_template
        if self.rules.use_json_parser:
            human_prompt_template += "\n\n**Return ONLY valid JSON** (no markdown, no code blocks)."
        
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
                result_text = result.content if hasattr(result, 'content') else str(result)
                return {
                    "extracted_text": result_text,
                    "raw_result": result
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting control: {str(e)}", exc_info=True)
            return {}
    
    async def create_control_profile_document(
        self,
        control_id: str,
        control_name: str,
        control_description: str,
        framework: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Create a rich control-context profile document using LLM.
        
        This document will be stored in the vector store for semantic search.
        Uses the document_sections from rules to structure the document.
        """
        # Build system prompt for document generation
        sections_text = "\n".join([
            f"{i+1}. {section['name']}: {section['description']}"
            for i, section in enumerate(self.rules.document_sections)
        ]) if self.rules.document_sections else "Create a comprehensive document."
        
        system_prompt = f"""You are an {self.rules.system_role}.

Create a comprehensive document that describes how a control/entity should be implemented
in a specific organizational context. Include:

{sections_text}

Make it detailed, actionable, and context-aware."""
        
        # Build prompt variables
        prompt_vars = {
            "control_id": control_id,
            "control_name": control_name,
            "control_description": control_description,
        }
        if framework:
            prompt_vars["framework"] = framework
        if context_metadata:
            prompt_vars["context_metadata"] = json.dumps(context_metadata, indent=2) if isinstance(context_metadata, dict) else str(context_metadata)
        prompt_vars.update(kwargs)
        
        # Use a default template if rules don't specify one for document generation
        human_prompt = f"""Create a control implementation profile:

Control: {control_id} - {control_name}
Framework: {framework or 'N/A'}
Description: {control_description}

Context:
{json.dumps(context_metadata, indent=2) if context_metadata else 'N/A'}

Create a comprehensive implementation profile document."""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        
        chain = prompt | self.llm
        
        try:
            result = await chain.ainvoke(prompt_vars)
            
            return result.content if hasattr(result, 'content') else str(result)
            
        except Exception as e:
            logger.error(f"Error creating control profile: {str(e)}", exc_info=True)
            return ""

