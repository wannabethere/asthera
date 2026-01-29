"""
Pattern Recognition Agent - Learns metadata patterns from source domains
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from app.agents.metadata_state import MetadataTransferLearningState, MetadataPattern

logger = logging.getLogger(__name__)


class PatternRecognitionAgent:
    """
    Agent that analyzes source domain metadata to extract transferable patterns.
    
    Identifies:
    - Structural patterns (table schemas, field types)
    - Semantic patterns (concept relationships, scoring logic)
    - Scoring patterns (how scores are calculated)
    - Relationship patterns (hierarchies, mappings)
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, model_name: str = "gpt-4o"):
        """Initialize the pattern recognition agent"""
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.1)
        self.json_parser = JsonOutputParser()
        
    async def __call__(self, state: MetadataTransferLearningState) -> MetadataTransferLearningState:
        """Execute pattern recognition on source metadata"""
        try:
            source_domains = state.get("source_domains", [])
            logger.info(f"Starting pattern recognition for source domains: {source_domains}")
            
            # Load source metadata if not already loaded
            source_metadata = state.get("source_metadata", [])
            if not source_metadata:
                source_metadata = await self._load_source_metadata(source_domains)
                state["source_metadata"] = source_metadata
            
            # Analyze patterns
            patterns = await self._analyze_patterns(source_metadata)
            
            # Convert patterns to dict for state storage
            from .state_helpers import pattern_to_dict
            state["learned_patterns"] = [pattern_to_dict(p) for p in patterns]
            
            # Generate pattern analysis summary
            state["pattern_analysis"] = await self._generate_pattern_analysis(patterns)
            
            state["current_step"] = "pattern_learning_complete"
            state["status"] = "domain_adaptation"
            
            logger.info(f"Pattern recognition complete. Found {len(patterns)} patterns")
            
        except Exception as e:
            logger.error(f"Error in pattern recognition: {str(e)}", exc_info=True)
            errors = state.get("errors", [])
            errors.append(f"Pattern recognition failed: {str(e)}")
            state["errors"] = errors
            state["status"] = "failed"
            
        return state
    
    async def _load_source_metadata(self, source_domains: List[str]) -> List[Dict[str, Any]]:
        """Load metadata from source domains"""
        logger.info(f"Loading source metadata for domains: {source_domains}")
        
        # Try to load from database if available
        # This would be injected via dependency injection in production
        try:
            # Check if metadata_service is available (injected via workflow)
            if hasattr(self, 'metadata_service') and self.metadata_service:
                return await self.metadata_service.load_source_metadata(source_domains)
        except Exception as e:
            logger.warning(f"Could not load from database: {str(e)}. Using empty list.")
        
        # Return empty list if database not available
        # In production, this should always load from database
        return []
    
    async def _analyze_patterns(self, source_metadata: List[Dict[str, Any]]) -> List[MetadataPattern]:
        """Analyze source metadata to extract patterns"""
        
        if not source_metadata:
            logger.warning("No source metadata provided for pattern analysis")
            return []
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at analyzing risk metadata structures and identifying 
transferable patterns. Your task is to analyze source domain metadata and extract patterns that 
can be applied to other domains.

Analyze the provided metadata and identify:
1. STRUCTURAL PATTERNS: Table schemas, field types, relationships
2. SEMANTIC PATTERNS: Concept relationships, scoring logic, prioritization methods
3. SCORING PATTERNS: How numeric scores are calculated and normalized
4. RELATIONSHIP PATTERNS: Hierarchies, mappings, cross-references

For each pattern, provide:
- pattern_name: Descriptive name
- pattern_type: 'structural', 'semantic', 'scoring', or 'relationship'
- pattern_structure: JSON schema of the pattern
- pattern_examples: 2-3 example instantiations
- confidence: Your confidence in this pattern (0-1)
- description: Explanation of the pattern

Return a JSON array of patterns."""),
            ("human", """Analyze this source metadata and extract transferable patterns:

{source_metadata}

Provide your analysis as a JSON array of pattern objects.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        try:
            result = await chain.ainvoke({
                "source_metadata": json.dumps(source_metadata, indent=2)
            })
            
            patterns = []
            for pattern_data in result:
                pattern = MetadataPattern(
                    pattern_name=pattern_data.get("pattern_name", ""),
                    pattern_type=pattern_data.get("pattern_type", ""),
                    source_domain=source_metadata[0].get("domain_name", "unknown") if source_metadata else "unknown",
                    pattern_structure=pattern_data.get("pattern_structure", {}),
                    pattern_examples=pattern_data.get("pattern_examples", []),
                    confidence=float(pattern_data.get("confidence", 0.5)),
                    description=pattern_data.get("description", "")
                )
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {str(e)}", exc_info=True)
            return []
    
    async def _generate_pattern_analysis(self, patterns: List[MetadataPattern]) -> Dict[str, Any]:
        """Generate summary analysis of learned patterns"""
        
        if not patterns:
            return {
                "pattern_count": 0,
                "pattern_types": {},
                "average_confidence": 0.0,
                "summary": "No patterns identified"
            }
        
        pattern_types = {}
        total_confidence = 0.0
        
        for pattern in patterns:
            pattern_types[pattern.pattern_type] = pattern_types.get(pattern.pattern_type, 0) + 1
            total_confidence += pattern.confidence
        
        return {
            "pattern_count": len(patterns),
            "pattern_types": pattern_types,
            "average_confidence": total_confidence / len(patterns) if patterns else 0.0,
            "summary": f"Identified {len(patterns)} patterns across {len(pattern_types)} types",
            "high_confidence_patterns": [
                p.pattern_name for p in patterns if p.confidence >= 0.8
            ]
        }

