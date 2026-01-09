"""
Metadata Generation Agent - Generates domain-specific metadata entries
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from .metadata_state import MetadataTransferLearningState, MetadataEntry, DomainMapping

logger = logging.getLogger(__name__)


class MetadataGenerationAgent:
    """
    Agent that generates metadata entries for target domain based on:
    - Learned patterns from source domains
    - Domain mappings
    - Target domain documents
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, model_name: str = "gpt-4o"):
        """Initialize the metadata generation agent"""
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
    async def __call__(self, state: MetadataTransferLearningState) -> MetadataTransferLearningState:
        """Execute metadata generation"""
        try:
            target_domain = state.get("target_domain", "")
            logger.info(f"Starting metadata generation for domain: {target_domain}")
            
            target_documents = state.get("target_documents", [])
            adaptation_strategy = state.get("adaptation_strategy", {})
            
            # Identify risks from documents
            risks = await self._identify_risks(
                target_documents,
                target_domain,
                adaptation_strategy
            )
            state["identified_risks"] = risks
            
            # Get patterns and mappings from state
            from .state_helpers import get_patterns_from_state, get_mappings_from_state
            patterns = get_patterns_from_state(state)
            mappings = get_mappings_from_state(state)
            
            # Generate metadata entries
            metadata_entries = await self._generate_metadata_entries(
                risks,
                patterns,
                mappings,
                target_domain,
                state.get("target_framework"),
                adaptation_strategy
            )
            
            # Convert entries to dict for state storage
            from .state_helpers import entry_to_dict
            state["generated_metadata"] = [entry_to_dict(e) for e in metadata_entries]
            
            # Generate notes
            state["generation_notes"] = await self._generate_generation_notes(
                metadata_entries,
                patterns
            )
            
            state["current_step"] = "metadata_generation_complete"
            state["status"] = "validation"
            state["metadata_entries_created"] = len(metadata_entries)
            
            logger.info(f"Metadata generation complete. Generated {len(metadata_entries)} entries")
            
        except Exception as e:
            logger.error(f"Error in metadata generation: {str(e)}", exc_info=True)
            errors = state.get("errors", [])
            errors.append(f"Metadata generation failed: {str(e)}")
            state["errors"] = errors
            state["status"] = "failed"
            
        return state
    
    async def _identify_risks(
        self,
        documents: List[str],
        target_domain: str,
        adaptation_strategy: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify risks/threats/violations from target domain documents"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at identifying compliance risks from regulatory documents.
Analyze the provided documents and identify:
1. What can go wrong (threats, violations, failures)
2. Severity levels mentioned
3. Likelihood factors
4. Impact descriptions
5. Control requirements

For each identified risk, provide:
- risk_name: Name of the risk/violation/threat
- category: 'threat', 'violation', 'failure', 'control_gap'
- description: Description from documents
- severity_indicators: What indicates severity
- likelihood_indicators: What indicates likelihood
- impact_indicators: What indicates impact
- regulatory_source: Which document/section

Return a JSON array of identified risks."""),
            ("human", """Identify risks from these {target_domain} compliance documents:

{documents}

Adaptation Strategy:
{adaptation_strategy}

Provide identified risks as a JSON array.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            result = await chain.ainvoke({
                "target_domain": target_domain,
                "documents": "\n\n---DOCUMENT SEPARATOR---\n\n".join(documents),
                "adaptation_strategy": json.dumps(adaptation_strategy, indent=2)
            })
            
            return result if isinstance(result, list) else []
            
        except Exception as e:
            logger.error(f"Error identifying risks: {str(e)}", exc_info=True)
            return []
    
    async def _generate_metadata_entries(
        self,
        risks: List[Dict[str, Any]],
        patterns: List,
        mappings: List[DomainMapping],
        target_domain: str,
        target_framework: Optional[str],
        adaptation_strategy: Dict[str, Any]
    ) -> List[MetadataEntry]:
        """Generate metadata entries for identified risks"""
        
        if not risks:
            logger.warning("No risks identified, cannot generate metadata")
            return []
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at generating risk metadata following established patterns.
Generate metadata entries for identified risks using:
1. Learned patterns from source domains
2. Domain mappings
3. Adaptation strategy

For each risk, generate a complete metadata entry with:
- domain_name: Target domain
- framework_name: Framework if applicable
- metadata_category: 'severity', 'likelihood', 'threat', 'control', 'consequence'
- enum_type: Specific type within category
- code: Unique code identifier
- description: Clear description
- numeric_score: 0-100 normalized score
- priority_order: Ranking (1 = highest)
- severity_level: 0-10 severity
- weight: Multiplicative weight (default 1.0)
- risk_score: Combined risk score if applicable
- occurrence_likelihood: Probability 0-100 if applicable
- consequence_severity: Impact 0-100 if applicable
- rationale: Detailed reasoning for scores
- data_indicators: What data signals indicate this risk
- abbreviation: Short code if applicable

Follow the patterns and ensure consistency with source domain scoring methodology.

Return a JSON array of metadata entries."""),
            ("human", """Generate metadata entries:

Identified Risks:
{risks}

Learned Patterns:
{patterns}

Domain Mappings:
{mappings}

Target Domain: {target_domain}
Target Framework: {target_framework}
Adaptation Strategy:
{adaptation_strategy}

Provide metadata entries as a JSON array.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            # Prepare summaries
            pattern_summaries = [
                {
                    "name": p.pattern_name,
                    "type": p.pattern_type,
                    "structure": p.pattern_structure
                }
                for p in patterns
            ]
            
            mapping_summaries = [
                {
                    "source": f"{m.source_domain}:{m.source_code}",
                    "target": f"{m.target_domain}:{m.target_code}",
                    "type": m.mapping_type,
                    "rationale": m.mapping_rationale
                }
                for m in mappings
            ]
            
            result = await chain.ainvoke({
                "risks": json.dumps(risks, indent=2),
                "patterns": json.dumps(pattern_summaries, indent=2),
                "mappings": json.dumps(mapping_summaries, indent=2),
                "target_domain": target_domain,
                "target_framework": target_framework or "GENERAL",
                "adaptation_strategy": json.dumps(adaptation_strategy, indent=2)
            })
            
            entries = []
            for entry_data in result:
                try:
                    entry = MetadataEntry(
                        domain_name=entry_data.get("domain_name", target_domain),
                        framework_name=entry_data.get("framework_name", target_framework),
                        metadata_category=entry_data.get("metadata_category", "threat"),
                        enum_type=entry_data.get("enum_type", "risk_type"),
                        code=entry_data.get("code", ""),
                        description=entry_data.get("description", ""),
                        numeric_score=float(entry_data.get("numeric_score", 50.0)),
                        priority_order=int(entry_data.get("priority_order", 1)),
                        severity_level=int(entry_data.get("severity_level")) if entry_data.get("severity_level") else None,
                        weight=float(entry_data.get("weight", 1.0)),
                        risk_score=float(entry_data.get("risk_score")) if entry_data.get("risk_score") else None,
                        occurrence_likelihood=float(entry_data.get("occurrence_likelihood")) if entry_data.get("occurrence_likelihood") else None,
                        consequence_severity=float(entry_data.get("consequence_severity")) if entry_data.get("consequence_severity") else None,
                        exploitability_score=float(entry_data.get("exploitability_score")) if entry_data.get("exploitability_score") else None,
                        impact_score=float(entry_data.get("impact_score")) if entry_data.get("impact_score") else None,
                        rationale=entry_data.get("rationale"),
                        data_source=entry_data.get("data_source"),
                        calculation_method=entry_data.get("calculation_method"),
                        data_indicators=entry_data.get("data_indicators"),
                        parent_code=entry_data.get("parent_code"),
                        equivalent_codes=entry_data.get("equivalent_codes"),
                        confidence_score=float(entry_data.get("confidence_score")) if entry_data.get("confidence_score") else None,
                        abbreviation=entry_data.get("abbreviation")
                    )
                    entries.append(entry)
                except Exception as e:
                    logger.warning(f"Error parsing metadata entry: {str(e)}")
                    continue
            
            return entries
            
        except Exception as e:
            logger.error(f"Error generating metadata entries: {str(e)}", exc_info=True)
            return []
    
    async def _generate_generation_notes(
        self,
        metadata_entries: List[MetadataEntry],
        patterns: List
    ) -> List[str]:
        """Generate notes about the generation process"""
        
        notes = [
            f"Generated {len(metadata_entries)} metadata entries",
            f"Applied {len(patterns)} learned patterns",
            f"Categories: {set(e.metadata_category for e in metadata_entries)}",
            f"Average confidence: {sum(e.confidence_score or 0.5 for e in metadata_entries) / len(metadata_entries) if metadata_entries else 0:.2f}"
        ]
        
        return notes

