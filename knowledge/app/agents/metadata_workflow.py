"""
Main LangGraph Workflow for Universal Metadata Generation
"""
import logging
from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import uuid

from app.agents.metadata_state import (
    MetadataTransferLearningState,
    MetadataGenerationStatus
)
from app.agents.extractors.pattern_recognition_agent import PatternRecognitionAgent
from app.agents.extractors.domain_adaptation_agent import DomainAdaptationAgent
from app.agents.extractors.metadata_generation_agent import MetadataGenerationAgent
from app.agents.extractors.validation_agent import ValidationAgent

logger = logging.getLogger(__name__)


class MetadataTransferLearningWorkflow:
    """
    Main workflow orchestrator for universal metadata generation using transfer learning.
    
    Workflow stages:
    1. Pattern Recognition - Learn patterns from source domains
    2. Domain Adaptation - Adapt patterns to target domain
    3. Metadata Generation - Generate metadata entries
    4. Validation - Validate and refine metadata
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        use_rag: bool = True
    ):
        """Initialize the workflow"""
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.use_rag = use_rag
        
        # Initialize agents
        self.pattern_agent = PatternRecognitionAgent(self.llm, model_name)
        self.adaptation_agent = DomainAdaptationAgent(self.llm, model_name)
        self.generation_agent = MetadataGenerationAgent(self.llm, model_name)
        self.validation_agent = ValidationAgent(self.llm, model_name)
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(MetadataTransferLearningState)
        
        # Add nodes
        workflow.add_node("pattern_recognition", self.pattern_agent)
        workflow.add_node("domain_adaptation", self.adaptation_agent)
        workflow.add_node("metadata_generation", self.generation_agent)
        workflow.add_node("validation", self.validation_agent)
        
        # Define workflow edges
        workflow.set_entry_point("pattern_recognition")
        workflow.add_edge("pattern_recognition", "domain_adaptation")
        workflow.add_edge("domain_adaptation", "metadata_generation")
        workflow.add_edge("metadata_generation", "validation")
        workflow.add_edge("validation", END)
        
        return workflow.compile()
    
    async def run(
        self,
        target_domain: str,
        target_documents: List[str],
        source_domains: Optional[List[str]] = None,
        target_framework: Optional[str] = None,
        target_document_sources: Optional[List[str]] = None,
        created_by: str = "llm_agent"
    ) -> MetadataTransferLearningState:
        """
        Execute the metadata generation workflow
        
        Args:
            target_domain: Target domain name (e.g., 'hr_compliance', 'financial_risk')
            target_documents: List of document texts to analyze
            source_domains: List of source domains for transfer learning (default: ['cybersecurity'])
            target_framework: Framework name if applicable (e.g., 'HIPAA', 'SOX')
            target_document_sources: Source identifiers for documents
            created_by: Creator identifier
            
        Returns:
            MetadataTransferLearningState with generated metadata
        """
        
        # Initialize state as TypedDict
        initial_state: MetadataTransferLearningState = {
            "target_domain": target_domain,
            "target_framework": target_framework,
            "source_domains": source_domains or ["cybersecurity"],
            "target_documents": target_documents,
            "target_document_sources": target_document_sources or [],
            "session_id": str(uuid.uuid4()),
            "created_by": created_by,
            "status": "pattern_learning",
            "current_step": "start",
            "messages": [],
            "errors": [],
            "warnings": [],
            "source_metadata": [],
            "learned_patterns": [],
            "pattern_analysis": {},
            "domain_mappings": [],
            "adaptation_strategy": {},
            "analogical_reasoning": [],
            "identified_risks": [],
            "generated_metadata": [],
            "generation_notes": [],
            "validation_results": {},
            "validation_issues": [],
            "refined_metadata": [],
            "overall_confidence": 0.0,
            "quality_scores": {},
            "metadata_entries_created": 0,
            "patterns_applied": []
        }
        
        logger.info(f"Starting metadata generation workflow for domain: {target_domain}")
        logger.info(f"Session ID: {initial_state.session_id}")
        
        try:
            # Execute workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            logger.info(f"Workflow completed. Generated {final_state.metadata_entries_created} entries")
            logger.info(f"Overall confidence: {final_state.overall_confidence:.2f}")
            
            return final_state
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}", exc_info=True)
            initial_state.errors.append(f"Workflow execution failed: {str(e)}")
            initial_state.status = MetadataGenerationStatus.FAILED
            return initial_state
    
    async def run_with_state(self, state: MetadataTransferLearningState) -> MetadataTransferLearningState:
        """Run workflow with existing state (for resuming/continuing)"""
        
        try:
            final_state = await self.graph.ainvoke(state)
            return final_state
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}", exc_info=True)
            state.errors.append(f"Workflow execution failed: {str(e)}")
            state.status = MetadataGenerationStatus.FAILED
            return state


# Convenience function for quick usage
async def generate_metadata_for_domain(
    target_domain: str,
    target_documents: List[str],
    source_domains: Optional[List[str]] = None,
    target_framework: Optional[str] = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o"
) -> MetadataTransferLearningState:
    """
    Convenience function to generate metadata for a domain
    
    Example:
        state = await generate_metadata_for_domain(
            target_domain="hr_compliance",
            target_documents=[
                "Title VII prohibits discriminatory hiring practices...",
                "FLSA requires overtime pay for non-exempt employees..."
            ],
            source_domains=["cybersecurity"],
            target_framework="GENERAL"
        )
        
        # Access generated metadata
        for entry in state.refined_metadata:
            print(f"{entry.code}: {entry.description} (score: {entry.numeric_score})")
    """
    
    workflow = MetadataTransferLearningWorkflow(llm=llm, model_name=model_name)
    return await workflow.run(
        target_domain=target_domain,
        target_documents=target_documents,
        source_domains=source_domains,
        target_framework=target_framework
    )

