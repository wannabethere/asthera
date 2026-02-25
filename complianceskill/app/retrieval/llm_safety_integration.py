"""
LLM Safety Retrieval Integration Utilities

Provides utilities for integrating LLM Safety retrieval into agents.
"""
import logging
from typing import Dict, List, Optional, Any
import asyncio

from app.retrieval.llm_safety_service import LLMSafetyRetrievalService
from app.retrieval.llm_safety_results import (
    LLMSafetyRetrievedContext,
    LLMSafetyTechniqueResult,
    LLMSafetyMitigationResult,
    LLMSafetyDetectionRuleResult,
)

logger = logging.getLogger(__name__)


def format_llm_safety_context(context: LLMSafetyRetrievedContext) -> str:
    """
    Format LLM Safety retrieval context into a string for prompt injection.
    
    Args:
        context: LLMSafetyRetrievedContext from retrieval
        
    Returns:
        Formatted string with techniques, mitigations, and detection rules
    """
    parts = []
    
    if context.techniques:
        parts.append("## LLM Safety Techniques")
        for technique in context.techniques[:3]:  # Limit to top 3
            parts.append(f"\n### {technique.title} ({technique.technique_id})")
            parts.append(f"**Description:** {technique.description}")
            if technique.severity:
                parts.append(f"**Severity:** {technique.severity}")
            if technique.tactic:
                parts.append(f"**Tactic:** {technique.tactic}")
            if technique.has_detection_rule:
                parts.append(f"**Has Detection Rule:** Yes ({technique.detection_rule_title or 'Available'})")
            if technique.keywords:
                parts.append(f"**Keywords:** {', '.join(technique.keywords[:5])}")
    
    if context.mitigations:
        parts.append("\n## LLM Safety Mitigations")
        for mitigation in context.mitigations[:3]:  # Limit to top 3
            parts.append(f"\n### {mitigation.title} ({mitigation.mitigation_id})")
            parts.append(f"**Description:** {mitigation.description}")
            if mitigation.effectiveness:
                parts.append(f"**Effectiveness:** {mitigation.effectiveness}")
            if mitigation.implementation_complexity:
                parts.append(f"**Implementation Complexity:** {mitigation.implementation_complexity}")
    
    if context.detection_rules:
        parts.append("\n## Detection Rule Templates")
        for rule in context.detection_rules[:3]:  # Limit to top 3
            parts.append(f"\n### {rule.title} ({rule.rule_id})")
            if rule.technique_id:
                parts.append(f"**For Technique:** {rule.technique_id} - {rule.technique_title or ''}")
            parts.append(f"**Description:** {rule.description}")
            if rule.level:
                parts.append(f"**Detection Level:** {rule.level}")
            if rule.status:
                parts.append(f"**Status:** {rule.status}")
            if rule.tags:
                parts.append(f"**Tags:** {', '.join(rule.tags[:5])}")
            # Include YAML content as template
            parts.append(f"\n**YAML Template:**\n```yaml\n{rule.content[:500]}...\n```")
    
    return "\n".join(parts) if parts else ""


async def retrieve_llm_safety_context(
    query: str,
    limit_per_type: int = 3,
    entity_types: Optional[List[str]] = None,
    technique_id: Optional[str] = None
) -> Optional[LLMSafetyRetrievedContext]:
    """
    Retrieve LLM Safety context for a query.
    
    Args:
        query: Natural language query
        limit_per_type: Max results per entity type
        entity_types: Optional list of entity types to search (technique, mitigation, detection_rule)
        technique_id: Optional technique ID to filter detection rules
        
    Returns:
        LLMSafetyRetrievedContext or None if service unavailable
    """
    try:
        service = LLMSafetyRetrievalService()
        
        # If technique_id is provided, also search for its detection rules
        if technique_id:
            detection_rules = await service.search_detection_rules_by_technique(
                technique_id=technique_id,
                limit=limit_per_type
            )
            # Get the technique itself
            techniques = await service.search_techniques(
                query=f"{technique_id} {query}",
                limit=1
            )
            
            return LLMSafetyRetrievedContext(
                query=query,
                techniques=techniques,
                mitigations=[],
                detection_rules=detection_rules,
                total_hits=len(techniques) + len(detection_rules)
            )
        else:
            return await service.search_all_llm_safety(
                query=query,
                limit_per_entity_type=limit_per_type,
                entity_types=entity_types
            )
    except Exception as e:
        logger.warning(f"LLM Safety retrieval failed: {e}")
        return None


def get_llm_safety_context_sync(
    query: str,
    limit_per_type: int = 3,
    entity_types: Optional[List[str]] = None,
    technique_id: Optional[str] = None
) -> str:
    """
    Synchronous wrapper for LLM Safety retrieval.
    
    Args:
        query: Natural language query
        limit_per_type: Max results per entity type
        entity_types: Optional list of entity types to search
        technique_id: Optional technique ID to filter detection rules
        
    Returns:
        Formatted string with LLM Safety context, or empty string if unavailable
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    context = loop.run_until_complete(
        retrieve_llm_safety_context(
            query=query,
            limit_per_type=limit_per_type,
            entity_types=entity_types,
            technique_id=technique_id
        )
    )
    
    if context:
        return format_llm_safety_context(context)
    return ""


async def get_detection_rule_template(
    technique_id: str,
    limit: int = 1
) -> Optional[LLMSafetyDetectionRuleResult]:
    """
    Get detection rule template for a specific technique.
    
    Args:
        technique_id: Technique ID (e.g., "SAFE-T1001")
        limit: Maximum number of rules to return
        
    Returns:
        First detection rule result, or None if not found
    """
    try:
        service = LLMSafetyRetrievalService()
        rules = await service.search_detection_rules_by_technique(
            technique_id=technique_id,
            limit=limit
        )
        return rules[0] if rules else None
    except Exception as e:
        logger.warning(f"Failed to get detection rule template for {technique_id}: {e}")
        return None
