"""
Prompt Generator Utility
Generates markdown-formatted system prompts for question/project ID context breakdown.

Note: Static prompts have been moved to app/utils/prompts/general_prompts.py
This module now provides utility functions for generating dynamic prompts.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.utils.prompts import (
    CONTEXT_BREAKDOWN_RULES,
    CONTEXT_BREAKDOWN_INSTRUCTIONS,
    PLAYBOOK_FIRST_RULES,
    get_assistant_specific_breakdown_section,
    get_available_entities_markdown,
)
from app.utils.prompts.general_prompts import get_breakdown_instructions_with_intent

logger = logging.getLogger(__name__)


def load_vector_store_prompts(prompts_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load vector_store_prompts.json file.
    
    Args:
        prompts_file: Path to vector_store_prompts.json (defaults to app/indexing/vector_store_prompts.json)
        
    Returns:
        Dictionary containing prompts data
    """
    if prompts_file is None:
        base_path = Path(__file__).parent.parent
        prompts_file = base_path / "indexing" / "vector_store_prompts.json"
    
    prompts_path = Path(prompts_file)
    try:
        if prompts_path.exists():
            with open(prompts_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Prompts file not found: {prompts_path}")
            return {}
    except Exception as e:
        logger.error(f"Error loading prompts file: {str(e)}")
        return {}


def generate_context_breakdown_prompt(
    prompts_data: Optional[Dict[str, Any]] = None,
    include_examples: bool = True,
    assistant_type: Optional[str] = None,
    intent_plan: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate markdown-formatted system prompt for question/project ID context breakdown.
    When intent_plan is provided (from IntentPlannerNode), the prompt asks only for search_questions
    and metadata_filters (breakdown follow-up), using the pre-set query_type and identified_entities.
    
    Args:
        prompts_data: Optional prompts data (will load if not provided)
        include_examples: Whether to include examples in the prompt
        assistant_type: Optional assistant ID (data_assistance_assistant, knowledge_assistance_assistant,
                        compliance_assistant, product_assistant) to add playbook-first and assistant-specific instructions
        intent_plan: Optional dict from IntentPlannerNode with query_type, identified_entities, frameworks?, product_context?
        
    Returns:
        Markdown-formatted system prompt string
    """
    if prompts_data is None:
        prompts_data = load_vector_store_prompts()
    
    # Include extraction entities from extractions.json + knowledge_assistant_mapping.json when config paths set (e.g. KB_DUMP_CONFIG_DIR)
    entities_md = get_available_entities_markdown()
    playbook_first = PLAYBOOK_FIRST_RULES if assistant_type else ""
    assistant_section = get_assistant_specific_breakdown_section(assistant_type) if assistant_type else ""
    # When intent is already planned, use follow-up instructions (steps 3–5 only); otherwise full breakdown instructions
    breakdown_instructions = get_breakdown_instructions_with_intent(intent_plan)
    if breakdown_instructions:
        instructions_block = breakdown_instructions
    else:
        instructions_block = CONTEXT_BREAKDOWN_INSTRUCTIONS
    # Base prompt template: playbook-first and assistant-specific first when present, then shared rules and entities
    base_prompt = f"""{playbook_first}{assistant_section}{CONTEXT_BREAKDOWN_RULES}

{entities_md}

{instructions_block}
"""
    
    if not include_examples:
        return base_prompt
    
    # Add examples section
    examples_section = """
## Examples

### Example 1: Compliance Framework Query

**Question**: "What are the SOC2 access control requirements for Snyk?"

**Context Breakdown**:
```json
{
  "query_type": "compliance_framework",
  "compliance_context": "SOC2 access control requirements",
  "product_context": "Snyk",
  "user_intent": "Find SOC2 access control requirements applicable to Snyk",
  "frameworks": ["SOC2"],
  "identified_entities": ["compliance_controls"],
  "entity_sub_types": ["soc2_controls"],
  "search_questions": [
    {
      "entity": "compliance_controls",
      "question": "What are SOC2 access control requirements?",
      "metadata_filters": {"framework": "SOC2", "tsc_category": "CC6"},
      "response_type": "Control definitions and requirements for access control"
    }
  ]
}
```

### Example 2: Policy Evidence Query

**Question**: "What evidence is required for access control policy?"

**Context Breakdown**:
```json
{
  "query_type": "policy",
  "compliance_context": "Access control policy evidence",
  "user_intent": "Find evidence requirements for access control policy",
  "identified_entities": ["policy_documents", "policy_evidence"],
  "search_questions": [
    {
      "entity": "policy_documents",
      "question": "What are access control policy requirements?",
      "metadata_filters": {"type": "policy"},
      "response_type": "Policy documents for access control"
    },
    {
      "entity": "policy_evidence",
      "question": "What evidence is needed for access control policy?",
      "metadata_filters": {"type": "policy", "extraction_type": "evidence"},
      "response_type": "Evidence requirements for access control"
    }
  ]
}
```

### Example 3: Product Query

**Question**: "How does Snyk integrate with GitHub?"

**Context Breakdown**:
```json
{
  "query_type": "product",
  "product_context": "Snyk GitHub integration",
  "user_intent": "Understand Snyk's GitHub integration capabilities",
  "identified_entities": ["product_knowledge", "product_entities"],
  "search_questions": [
    {
      "entity": "product_knowledge",
      "question": "How does Snyk integrate with GitHub?",
      "metadata_filters": {"type": "product", "product_name": "Snyk"},
      "response_type": "Integration documentation and capabilities"
    },
    {
      "entity": "product_entities",
      "question": "What are Snyk's GitHub integration entities?",
      "metadata_filters": {"type": "product", "extraction_type": "entities"},
      "response_type": "Integration components and configuration"
    }
  ]
}
```
"""
    
    return base_prompt + examples_section


def get_context_breakdown_system_prompt(
    include_examples: bool = True,
    assistant_type: Optional[str] = None,
    intent_plan: Optional[Dict[str, Any]] = None,
) -> str:
    return generate_context_breakdown_prompt(None, include_examples, assistant_type, intent_plan)
