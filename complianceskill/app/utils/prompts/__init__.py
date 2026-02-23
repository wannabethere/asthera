"""
Prompts Module
Centralized location for all LLM prompts used across the application.

Organization:
- workforce_prompts.py: Prompts for workforce assistants (Product, Compliance, Domain Knowledge)
- mdl_prompts.py: Prompts for MDL semantic layer queries
- general_prompts.py: General-purpose prompts and context breakdown rules
"""
from app.utils.prompts.workforce_prompts import (
    PRODUCT_SYSTEM_PROMPT,
    PRODUCT_HUMAN_PROMPT,
    COMPLIANCE_SYSTEM_PROMPT,
    COMPLIANCE_HUMAN_PROMPT,
    DOMAIN_KNOWLEDGE_SYSTEM_PROMPT,
    DOMAIN_KNOWLEDGE_HUMAN_PROMPT
)
from app.utils.prompts.mdl_prompts import (
    MDL_CONTEXT_BREAKDOWN_RULES,
    MDL_ENTITIES_MARKDOWN,
    MDL_CONTEXT_BREAKDOWN_INSTRUCTIONS
)
from app.utils.prompts.general_prompts import (
    CONTEXT_BREAKDOWN_RULES,
    CONTEXT_BREAKDOWN_INSTRUCTIONS,
    AVAILABLE_ENTITIES_MARKDOWN
)

__all__ = [
    # Workforce Prompts
    "PRODUCT_SYSTEM_PROMPT",
    "PRODUCT_HUMAN_PROMPT",
    "COMPLIANCE_SYSTEM_PROMPT",
    "COMPLIANCE_HUMAN_PROMPT",
    "DOMAIN_KNOWLEDGE_SYSTEM_PROMPT",
    "DOMAIN_KNOWLEDGE_HUMAN_PROMPT",
    
    # MDL Prompts
    "MDL_CONTEXT_BREAKDOWN_RULES",
    "MDL_ENTITIES_MARKDOWN",
    "MDL_CONTEXT_BREAKDOWN_INSTRUCTIONS",
    
    # General Prompts
    "CONTEXT_BREAKDOWN_RULES",
    "CONTEXT_BREAKDOWN_INSTRUCTIONS",
    "AVAILABLE_ENTITIES_MARKDOWN",
]
