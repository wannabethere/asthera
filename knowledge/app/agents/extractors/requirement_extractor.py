"""
Configurable LLM extractor for creating requirement/edge documents.

This extractor uses configurable rules to create contextual documents,
allowing it to work for different domains and document types.
"""
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from .extraction_rules import ExtractionRules, get_compliance_requirement_rules

logger = logging.getLogger(__name__)


class RequirementExtractor:
    """
    Extract requirement/edge information and create context documents using configurable rules.
    
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
        self.rules = rules or get_compliance_requirement_rules()
    
    async def create_requirement_edge_document(
        self,
        requirement_text: str,
        control_id: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Create a contextual edge document for a requirement/entity.
        
        Args:
            requirement_text: Text/description of the requirement/entity
            control_id: Optional related control/entity ID
            context_metadata: Optional context metadata
            **kwargs: Additional variables for prompt template
            
        Returns:
            Generated document text
        """
        # Build system prompt from rules
        sections_text = "\n".join([
            f"{i+1}. {section['name']}: {section['description']}"
            for i, section in enumerate(self.rules.document_sections)
        ]) if self.rules.document_sections else self.rules.system_instructions
        
        system_prompt = f"You are an {self.rules.system_role}.\n\n{sections_text}"
        
        # Build prompt variables
        prompt_vars = {"requirement_text": requirement_text}
        if control_id:
            prompt_vars["control_id"] = control_id
        if context_metadata:
            prompt_vars["context_metadata"] = json.dumps(context_metadata, indent=2) if isinstance(context_metadata, dict) else str(context_metadata)
        prompt_vars.update(kwargs)
        
        # Format human prompt template
        human_prompt = self.rules.human_prompt_template.format(**prompt_vars)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        
        chain = prompt | self.llm
        
        try:
            result = await chain.ainvoke(prompt_vars)
            
            return result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            logger.error(f"Error creating requirement document: {str(e)}", exc_info=True)
            return ""

