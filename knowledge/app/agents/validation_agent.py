"""
Validation Agent - Validates and refines generated metadata
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from .metadata_state import MetadataTransferLearningState, MetadataEntry

logger = logging.getLogger(__name__)


class ValidationAgent:
    """
    Agent that validates generated metadata for:
    - Completeness
    - Consistency
    - Scoring accuracy
    - Cross-domain alignment
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, model_name: str = "gpt-4o"):
        """Initialize the validation agent"""
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.1)
        self.json_parser = JsonOutputParser()
        
    async def __call__(self, state: MetadataTransferLearningState) -> MetadataTransferLearningState:
        """Execute validation"""
        try:
            generated_metadata = state.get("generated_metadata", [])
            logger.info(f"Starting validation for {len(generated_metadata)} metadata entries")
            
            target_domain = state.get("target_domain", "")
            from .state_helpers import get_patterns_from_state, get_entries_from_state
            patterns = get_patterns_from_state(state)
            entries = get_entries_from_state(state)
            
            # Validate entries
            validation_results = await self._validate_metadata(
                entries,
                target_domain,
                patterns
            )
            state["validation_results"] = validation_results
            
            # Identify issues
            issues = await self._identify_issues(
                entries,
                validation_results
            )
            state["validation_issues"] = issues
            
            # Refine metadata if needed
            if issues:
                refined = await self._refine_metadata(
                    entries,
                    issues,
                    target_domain
                )
                from .state_helpers import entry_to_dict
                state["refined_metadata"] = [entry_to_dict(e) for e in refined]
            else:
                state["refined_metadata"] = state.get("generated_metadata", [])
            
            # Calculate quality metrics
            refined_entries = get_entries_from_state(state)
            quality_scores = await self._calculate_quality_scores(
                refined_entries,
                validation_results
            )
            state["quality_scores"] = quality_scores
            state["overall_confidence"] = quality_scores.get("overall_confidence", 0.0)
            
            state["current_step"] = "validation_complete"
            state["status"] = "completed"
            
            logger.info(f"Validation complete. Quality score: {state['overall_confidence']:.2f}")
            
        except Exception as e:
            logger.error(f"Error in validation: {str(e)}", exc_info=True)
            errors = state.get("errors", [])
            errors.append(f"Validation failed: {str(e)}")
            state["errors"] = errors
            state["status"] = "failed"
            
        return state
    
    async def _validate_metadata(
        self,
        entries: List[MetadataEntry],
        target_domain: str,
        patterns: List
    ) -> Dict[str, Any]:
        """Validate metadata entries"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at validating risk metadata.
Validate the provided metadata entries for:
1. Completeness: All required fields present
2. Consistency: Scores align with descriptions
3. Accuracy: Scoring follows established patterns
4. Alignment: Cross-domain mappings are correct
5. Rationale: Reasoning is sound

For each entry, provide:
- is_valid: Boolean
- completeness_score: 0-1
- consistency_score: 0-1
- accuracy_score: 0-1
- issues: List of specific issues found
- suggestions: Suggestions for improvement

Return a JSON object with validation results per entry."""),
            ("human", """Validate these metadata entries:

{entries}

Target Domain: {target_domain}
Expected Patterns:
{patterns}

Provide validation results as JSON object with entry codes as keys.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            entry_summaries = [
                {
                    "code": e.code,
                    "category": e.metadata_category,
                    "description": e.description,
                    "numeric_score": e.numeric_score,
                    "risk_score": e.risk_score,
                    "rationale": e.rationale
                }
                for e in entries
            ]
            
            pattern_summaries = [
                {
                    "name": p.pattern_name,
                    "type": p.pattern_type,
                    "structure": p.pattern_structure
                }
                for p in patterns
            ]
            
            result = await chain.ainvoke({
                "entries": json.dumps(entry_summaries, indent=2),
                "target_domain": target_domain,
                "patterns": json.dumps(pattern_summaries, indent=2)
            })
            
            return result if isinstance(result, dict) else {}
            
        except Exception as e:
            logger.error(f"Error validating metadata: {str(e)}", exc_info=True)
            return {}
    
    async def _identify_issues(
        self,
        entries: List[MetadataEntry],
        validation_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify validation issues"""
        
        issues = []
        
        for entry in entries:
            validation = validation_results.get(entry.code, {})
            
            if not validation.get("is_valid", True):
                issues.append({
                    "entry_code": entry.code,
                    "entry_description": entry.description,
                    "severity": "high" if validation.get("completeness_score", 1.0) < 0.5 else "medium",
                    "issues": validation.get("issues", []),
                    "suggestions": validation.get("suggestions", [])
                })
        
        return issues
    
    async def _refine_metadata(
        self,
        entries: List[MetadataEntry],
        issues: List[Dict[str, Any]],
        target_domain: str
    ) -> List[MetadataEntry]:
        """Refine metadata entries based on validation issues"""
        
        if not issues:
            return entries
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at refining risk metadata based on validation feedback.
Refine the provided metadata entries to address identified issues.

Maintain consistency with:
- Original scoring methodology
- Domain context
- Established patterns

Return refined metadata entries as a JSON array."""),
            ("human", """Refine these metadata entries:

{entries}

Validation Issues:
{issues}

Target Domain: {target_domain}

Provide refined entries as JSON array.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            entry_summaries = [
                {
                    "code": e.code,
                    "category": e.metadata_category,
                    "description": e.description,
                    "numeric_score": e.numeric_score,
                    "rationale": e.rationale
                }
                for e in entries
            ]
            
            result = await chain.ainvoke({
                "entries": json.dumps(entry_summaries, indent=2),
                "issues": json.dumps(issues, indent=2),
                "target_domain": target_domain
            })
            
            # Convert back to MetadataEntry objects
            refined_entries = []
            for entry_data in result:
                try:
                    # Find original entry to preserve fields
                    original = next((e for e in entries if e.code == entry_data.get("code")), None)
                    if original:
                        # Update with refined values
                        refined = MetadataEntry(
                            domain_name=original.domain_name,
                            framework_name=original.framework_name,
                            metadata_category=entry_data.get("metadata_category", original.metadata_category),
                            enum_type=entry_data.get("enum_type", original.enum_type),
                            code=entry_data.get("code", original.code),
                            description=entry_data.get("description", original.description),
                            numeric_score=float(entry_data.get("numeric_score", original.numeric_score)),
                            priority_order=int(entry_data.get("priority_order", original.priority_order)),
                            severity_level=int(entry_data.get("severity_level")) if entry_data.get("severity_level") else original.severity_level,
                            weight=float(entry_data.get("weight", original.weight)),
                            risk_score=float(entry_data.get("risk_score")) if entry_data.get("risk_score") else original.risk_score,
                            occurrence_likelihood=float(entry_data.get("occurrence_likelihood")) if entry_data.get("occurrence_likelihood") else original.occurrence_likelihood,
                            consequence_severity=float(entry_data.get("consequence_severity")) if entry_data.get("consequence_severity") else original.consequence_severity,
                            rationale=entry_data.get("rationale", original.rationale),
                            data_indicators=entry_data.get("data_indicators", original.data_indicators),
                            confidence_score=float(entry_data.get("confidence_score")) if entry_data.get("confidence_score") else original.confidence_score
                        )
                        refined_entries.append(refined)
                except Exception as e:
                    logger.warning(f"Error refining entry: {str(e)}")
                    # Keep original if refinement fails
                    original = next((e for e in entries if entry_data.get("code") == e.code), None)
                    if original:
                        refined_entries.append(original)
            
            return refined_entries if refined_entries else entries
            
        except Exception as e:
            logger.error(f"Error refining metadata: {str(e)}", exc_info=True)
            return entries
    
    async def _calculate_quality_scores(
        self,
        entries: List[MetadataEntry],
        validation_results: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate quality scores for generated metadata"""
        
        if not entries:
            return {
                "overall_confidence": 0.0,
                "completeness": 0.0,
                "consistency": 0.0,
                "accuracy": 0.0
            }
        
        completeness_scores = []
        consistency_scores = []
        accuracy_scores = []
        confidence_scores = []
        
        for entry in entries:
            validation = validation_results.get(entry.code, {})
            completeness_scores.append(validation.get("completeness_score", 0.5))
            consistency_scores.append(validation.get("consistency_score", 0.5))
            accuracy_scores.append(validation.get("accuracy_score", 0.5))
            confidence_scores.append(entry.confidence_score or 0.5)
        
        return {
            "overall_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0,
            "completeness": sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0.0,
            "consistency": sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.0,
            "accuracy": sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0,
            "entry_count": len(entries)
        }

