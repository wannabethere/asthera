"""
Domain Adaptation Agent - Transfers learned patterns to target domain
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from app.agents.metadata_state import MetadataTransferLearningState, DomainMapping, MetadataPattern

logger = logging.getLogger(__name__)


class DomainAdaptationAgent:
    """
    Agent that adapts learned patterns from source domains to target domain.
    
    Performs:
    - Analogical mapping (source concepts → target concepts)
    - Dimension transfer (scoring dimensions, risk factors)
    - Semantic alignment (ensuring concepts match domain context)
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, model_name: str = "gpt-4o"):
        """Initialize the domain adaptation agent"""
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
    async def __call__(self, state: MetadataTransferLearningState) -> MetadataTransferLearningState:
        """Execute domain adaptation"""
        try:
            target_domain = state.get("target_domain", "")
            logger.info(f"Starting domain adaptation for target: {target_domain}")
            
            # Get patterns from state
            from .state_helpers import get_patterns_from_state
            patterns = get_patterns_from_state(state)
            source_domains = state.get("source_domains", [])
            target_documents = state.get("target_documents", [])
            
            # Create domain mappings
            mappings = await self._create_domain_mappings(
                patterns,
                source_domains,
                target_domain,
                target_documents
            )
            
            # Convert mappings to dict for state storage
            from .state_helpers import mapping_to_dict
            state["domain_mappings"] = [mapping_to_dict(m) for m in mappings]
            
            # Generate adaptation strategy
            strategy = await self._generate_adaptation_strategy(
                patterns,
                target_domain,
                target_documents
            )
            state["adaptation_strategy"] = strategy
            
            # Generate analogical reasoning
            reasoning = await self._generate_analogical_reasoning(
                patterns,
                target_domain,
                target_documents
            )
            state["analogical_reasoning"] = reasoning
            
            state["current_step"] = "domain_adaptation_complete"
            state["status"] = "metadata_generation"
            
            logger.info(f"Domain adaptation complete. Created {len(mappings)} mappings")
            
        except Exception as e:
            logger.error(f"Error in domain adaptation: {str(e)}", exc_info=True)
            errors = state.get("errors", [])
            errors.append(f"Domain adaptation failed: {str(e)}")
            state["errors"] = errors
            state["status"] = "failed"
            
        return state
    
    async def _create_domain_mappings(
        self,
        patterns: List[MetadataPattern],
        source_domains: List[str],
        target_domain: str,
        target_documents: List[str]
    ) -> List[DomainMapping]:
        """Create mappings between source and target domain concepts"""
        
        if not patterns:
            logger.warning("No patterns available for domain mapping")
            return []
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at mapping risk concepts across different compliance domains.
Your task is to identify equivalent concepts between source domains and a target domain.

For each source concept, identify:
1. EXACT matches: Identical concepts in target domain
2. SIMILAR matches: Close concepts with minor differences
3. ANALOGICAL matches: Conceptually equivalent but domain-specific

For each mapping, provide:
- source_domain: Source domain name
- source_code: Source concept code
- source_enum_type: Source enum type
- target_domain: Target domain name
- target_code: Target concept code (or suggest new)
- target_enum_type: Target enum type (or suggest new)
- mapping_type: 'exact', 'similar', or 'analogical'
- similarity_score: 0-1 similarity score
- mapping_rationale: Explanation of why these map

Return a JSON array of mappings."""),
            ("human", """Create domain mappings:

Source Patterns:
{patterns}

Target Domain: {target_domain}
Target Domain Context:
{target_documents}

Provide mappings as a JSON array.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            # Prepare pattern summaries
            pattern_summaries = [
                {
                    "name": p.pattern_name,
                    "type": p.pattern_type,
                    "structure": p.pattern_structure,
                    "examples": p.pattern_examples[:2]  # Limit examples
                }
                for p in patterns
            ]
            
            result = await chain.ainvoke({
                "patterns": json.dumps(pattern_summaries, indent=2),
                "target_domain": target_domain,
                "target_documents": "\n\n".join(target_documents[:3])  # Limit documents
            })
            
            mappings = []
            for mapping_data in result:
                mapping = DomainMapping(
                    source_domain=mapping_data.get("source_domain", source_domains[0] if source_domains else "unknown"),
                    source_code=mapping_data.get("source_code", ""),
                    source_enum_type=mapping_data.get("source_enum_type", ""),
                    target_domain=target_domain,
                    target_code=mapping_data.get("target_code", ""),
                    target_enum_type=mapping_data.get("target_enum_type", ""),
                    mapping_type=mapping_data.get("mapping_type", "analogical"),
                    similarity_score=float(mapping_data.get("similarity_score", 0.5)),
                    mapping_rationale=mapping_data.get("mapping_rationale", "")
                )
                mappings.append(mapping)
            
            return mappings
            
        except Exception as e:
            logger.error(f"Error creating domain mappings: {str(e)}", exc_info=True)
            return []
    
    async def _generate_adaptation_strategy(
        self,
        patterns: List[MetadataPattern],
        target_domain: str,
        target_documents: List[str]
    ) -> Dict[str, Any]:
        """Generate strategy for adapting patterns to target domain"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at adapting risk metadata patterns across domains.
Generate a strategy for adapting learned patterns to a new domain.

The strategy should include:
1. Which patterns to apply directly
2. Which patterns need modification
3. How to modify scoring dimensions
4. Domain-specific considerations
5. Risk factors unique to target domain

Return a JSON object with the adaptation strategy."""),
            ("human", """Generate adaptation strategy:

Learned Patterns:
{patterns}

Target Domain: {target_domain}
Target Domain Context:
{target_documents}

Provide adaptation strategy as JSON.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            pattern_summaries = [
                {
                    "name": p.pattern_name,
                    "type": p.pattern_type,
                    "description": p.description
                }
                for p in patterns
            ]
            
            result = await chain.ainvoke({
                "patterns": json.dumps(pattern_summaries, indent=2),
                "target_domain": target_domain,
                "target_documents": "\n\n".join(target_documents[:3])
            })
            
            return result if isinstance(result, dict) else {}
            
        except Exception as e:
            logger.error(f"Error generating adaptation strategy: {str(e)}", exc_info=True)
            return {}
    
    async def _generate_analogical_reasoning(
        self,
        patterns: List[MetadataPattern],
        target_domain: str,
        target_documents: List[str]
    ) -> List[str]:
        """Generate analogical reasoning explanations"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at analogical reasoning across compliance domains.
Generate clear explanations of how source domain concepts map to target domain concepts.

For each key mapping, provide:
- Source concept and its role
- Target concept and its role
- Why they are equivalent
- How scoring/prioritization transfers

Return a JSON array of reasoning explanations."""),
            ("human", """Generate analogical reasoning:

Patterns:
{patterns}

Target Domain: {target_domain}
Target Context:
{target_documents}

Provide reasoning as JSON array of strings.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            pattern_summaries = [
                {
                    "name": p.pattern_name,
                    "type": p.pattern_type,
                    "description": p.description
                }
                for p in patterns
            ]
            
            result = await chain.ainvoke({
                "patterns": json.dumps(pattern_summaries, indent=2),
                "target_domain": target_domain,
                "target_documents": "\n\n".join(target_documents[:3])
            })
            
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "reasoning" in result:
                return result["reasoning"]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error generating analogical reasoning: {str(e)}", exc_info=True)
            return []

