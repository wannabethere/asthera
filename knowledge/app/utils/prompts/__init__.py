"""
Prompts Module
Centralized location for all LLM prompts used across the application.

Organization:
- workforce_prompts.py: Prompts for workforce assistants (Product, Compliance, Domain Knowledge)
- mdl_prompts.py: Prompts for MDL semantic layer queries
- general_prompts.py: General-purpose prompts and context breakdown rules
- transform_prompts.py: Transform/transforms assistant prompts (composable instructions + examples)
"""
from app.utils.prompts.workforce_prompts import (
    PRODUCT_SYSTEM_PROMPT,
    PRODUCT_HUMAN_PROMPT,
    COMPLIANCE_SYSTEM_PROMPT,
    COMPLIANCE_HUMAN_PROMPT,
    DOMAIN_KNOWLEDGE_SYSTEM_PROMPT,
    DOMAIN_KNOWLEDGE_HUMAN_PROMPT,
    ASSISTANT_INSTRUCTIONS_PRODUCT,
    ASSISTANT_INSTRUCTIONS_COMPLIANCE,
    ASSISTANT_INSTRUCTIONS_DOMAIN_KNOWLEDGE,
    ASSISTANT_EXAMPLE_PRODUCT,
    ASSISTANT_EXAMPLE_COMPLIANCE,
    ASSISTANT_EXAMPLE_DOMAIN_KNOWLEDGE,
    EXAMPLE_PLAYBOOK_PRODUCT,
    EXAMPLE_PLAYBOOK_COMPLIANCE,
    EXAMPLE_PLAYBOOK_DOMAIN_KNOWLEDGE,
    get_workforce_assistant_instructions,
    get_workforce_assistant_example,
    get_workforce_example_playbook,
    get_workforce_assistant_bundle,
)
from app.utils.prompts.mdl_prompts import (
    MDL_CONTEXT_BREAKDOWN_RULES,
    MDL_ENTITIES_MARKDOWN,
    MDL_CONTEXT_BREAKDOWN_INSTRUCTIONS
)
from app.utils.prompts.general_prompts import (
    CONTEXT_BREAKDOWN_RULES,
    CONTEXT_BREAKDOWN_INSTRUCTIONS,
    PLAYBOOK_FIRST_RULES,
    get_assistant_specific_breakdown_section,
    AVAILABLE_ENTITIES_MARKDOWN,
    get_available_entities_markdown,
    get_extraction_entities_markdown,
)
from app.utils.prompts.data_retrieval_prompts import (
    DATA_RETRIEVAL_RULES,
    DATA_RETRIEVAL_ENTITIES_MARKDOWN,
    DATA_RETRIEVAL_EXAMPLES,
    DATA_RETRIEVAL_INSTRUCTIONS,
    DATA_RETRIEVAL_SUMMARY_SYSTEM,
    DATA_RETRIEVAL_SUMMARY_HUMAN,
    get_data_retrieval_system_prompt,
    get_data_retrieval_examples_text,
    get_data_retrieval_summary_prompt,
    DATA_RETRIEVAL_SCORE_PRUNE_SYSTEM,
    DATA_RETRIEVAL_SCORE_PRUNE_HUMAN,
    get_data_retrieval_score_prune_prompt,
)
from app.utils.prompts.transform_prompts import (
    get_instructions,
    get_examples,
    build_instructions_text,
    build_examples_text,
    get_system_prompt,
    build_compliance_instructions_blob,
    get_lane_refining_instructions,
    get_lane_feature_generation_instructions,
    TRANSFORM_PROMPT_REGISTRY,
)

__all__ = [
    # Workforce Prompts
    "PRODUCT_SYSTEM_PROMPT",
    "PRODUCT_HUMAN_PROMPT",
    "COMPLIANCE_SYSTEM_PROMPT",
    "COMPLIANCE_HUMAN_PROMPT",
    "DOMAIN_KNOWLEDGE_SYSTEM_PROMPT",
    "DOMAIN_KNOWLEDGE_HUMAN_PROMPT",
    "ASSISTANT_INSTRUCTIONS_PRODUCT",
    "ASSISTANT_INSTRUCTIONS_COMPLIANCE",
    "ASSISTANT_INSTRUCTIONS_DOMAIN_KNOWLEDGE",
    "ASSISTANT_EXAMPLE_PRODUCT",
    "ASSISTANT_EXAMPLE_COMPLIANCE",
    "ASSISTANT_EXAMPLE_DOMAIN_KNOWLEDGE",
    "EXAMPLE_PLAYBOOK_PRODUCT",
    "EXAMPLE_PLAYBOOK_COMPLIANCE",
    "EXAMPLE_PLAYBOOK_DOMAIN_KNOWLEDGE",
    "get_workforce_assistant_instructions",
    "get_workforce_assistant_example",
    "get_workforce_example_playbook",
    "get_workforce_assistant_bundle",
    
    # Data retrieval prompts
    "DATA_RETRIEVAL_RULES",
    "DATA_RETRIEVAL_ENTITIES_MARKDOWN",
    "DATA_RETRIEVAL_EXAMPLES",
    "DATA_RETRIEVAL_INSTRUCTIONS",
    "get_data_retrieval_system_prompt",
    "get_data_retrieval_examples_text",
    "DATA_RETRIEVAL_SUMMARY_SYSTEM",
    "DATA_RETRIEVAL_SUMMARY_HUMAN",
    "get_data_retrieval_summary_prompt",
    "DATA_RETRIEVAL_SCORE_PRUNE_SYSTEM",
    "DATA_RETRIEVAL_SCORE_PRUNE_HUMAN",
    "get_data_retrieval_score_prune_prompt",
    # MDL Prompts
    "MDL_CONTEXT_BREAKDOWN_RULES",
    "MDL_ENTITIES_MARKDOWN",
    "MDL_CONTEXT_BREAKDOWN_INSTRUCTIONS",
    
    # General Prompts
    "CONTEXT_BREAKDOWN_RULES",
    "CONTEXT_BREAKDOWN_INSTRUCTIONS",
    "PLAYBOOK_FIRST_RULES",
    "get_assistant_specific_breakdown_section",
    "AVAILABLE_ENTITIES_MARKDOWN",
    "get_available_entities_markdown",
    "get_extraction_entities_markdown",
    # Transform / Transforms prompts
    "get_instructions",
    "get_examples",
    "build_instructions_text",
    "build_examples_text",
    "get_system_prompt",
    "build_compliance_instructions_blob",
    "get_lane_refining_instructions",
    "get_lane_feature_generation_instructions",
    "TRANSFORM_PROMPT_REGISTRY",
]
