"""
Control Prioritization Workflow

This module provides a separate workflow for periodically calculating and storing
control priorities. This is NOT part of the feature engineering flow.

The workflow:
1. Loads controls from domain configurations
2. Assesses risk, impact, likelihood (Phase 1)
3. Classifies priority, relevance, quality (Phase 2)
4. Stores results for later use

This workflow should be run periodically (e.g., weekly/monthly) to update
control priorities based on current organizational context.
"""

import logging
from typing import Dict, List, Optional, Any, TypedDict
from pathlib import Path
from datetime import datetime
import json

from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END, START

from app.agents.nodes.transform.control_universe_model import (
    ComplianceControlUniverse,
    Control,
    SubControl,
    DomainContext,
    ControlPriorityInfo,
    prioritize_controls_with_llm,
    load_external_control_data
)
from app.agents.nodes.transform.domain_config import (
    get_compliance_control_set,
    get_control_prioritization_config,
    get_all_prioritization_configs,
    ComplianceControl
)

logger = logging.getLogger("lexy-ai-service")


# ============================================================================
# STATE DEFINITION
# ============================================================================

class ControlPrioritizationState(TypedDict):
    """State for control prioritization workflow"""
    organization_name: str
    domain_name: str
    compliance_framework: Optional[str]
    
    # Controls to prioritize
    controls: List[Control]
    control_universe: Optional[ComplianceControlUniverse]
    
    # Phase 1 results
    risk_assessments: Dict[str, Dict[str, Any]]
    
    # Phase 2 results
    priority_infos: Dict[str, ControlPriorityInfo]
    
    # Configuration
    deep_research_knowledge: Optional[Dict[str, Any]]
    downstream_processing_context: Optional[str]
    external_data_file: Optional[str]
    
    # Output
    output_file: Optional[str]
    results_summary: Dict[str, Any]
    
    # Metadata
    messages: List[Dict[str, str]]
    errors: List[str]


# ============================================================================
# WORKFLOW NODES
# ============================================================================

class ControlUniverseBuilder:
    """Node: Build control universe from domain configurations"""
    
    def __init__(self):
        pass
    
    async def __call__(self, state: ControlPrioritizationState) -> ControlPrioritizationState:
        """Build control universe from domain configurations"""
        try:
            domain_name = state.get("domain_name")
            organization_name = state.get("organization_name", "Organization")
            
            # Get control set for domain
            control_set = get_compliance_control_set(domain_name)
            
            # Create control universe
            universe = ComplianceControlUniverse(organization_name)
            
            # Add domain context
            domain_context = DomainContext(
                domain_name=domain_name,
                industry=domain_name.replace("_", " ").title(),
                applicable_frameworks=[control_set.framework],
                business_processes=[],
                data_categories=[],
                system_components=[],
                stakeholders=[]
            )
            universe.set_domain_context(domain_context)
            
            # Convert ComplianceControl to Control objects
            controls = []
            for comp_control in control_set.controls:
                control = Control(
                    control_id=comp_control.control_id,
                    control_name=comp_control.control_name,
                    framework=comp_control.framework,
                    category=comp_control.category,
                    description=comp_control.description,
                    control_owner="Compliance Team",
                    source_document=f"{comp_control.framework} Framework",
                    document_section=comp_control.control_id,
                    extracted_text=comp_control.description
                )
                universe.add_control(control)
                controls.append(control)
            
            state["control_universe"] = universe
            state["controls"] = controls
            
            state["messages"].append({
                "role": "system",
                "content": f"Built control universe with {len(controls)} controls from {domain_name} domain"
            })
            
        except Exception as e:
            logger.error(f"Error building control universe: {e}")
            state["errors"].append(f"Error building control universe: {str(e)}")
        
        return state


class ExternalDataLoader:
    """Node: Load external control data from file if available"""
    
    def __init__(self):
        pass
    
    async def __call__(self, state: ControlPrioritizationState) -> ControlPrioritizationState:
        """Load external control data from file"""
        try:
            external_data_file = state.get("external_data_file")
            universe = state.get("control_universe")
            
            if external_data_file and universe:
                loaded_data = load_external_control_data(
                    control_universe=universe,
                    file_path=external_data_file
                )
                
                if loaded_data:
                    state["messages"].append({
                        "role": "system",
                        "content": f"Loaded external data for {len(loaded_data)} controls from {external_data_file}"
                    })
                else:
                    state["messages"].append({
                        "role": "system",
                        "content": f"External data file not found or empty: {external_data_file}"
                    })
            else:
                state["messages"].append({
                    "role": "system",
                    "content": "No external data file specified, using default configurations"
                })
            
        except Exception as e:
            logger.error(f"Error loading external data: {e}")
            state["errors"].append(f"Error loading external data: {str(e)}")
        
        return state


class ControlPrioritizationAgent:
    """Node: Run two-phase control prioritization"""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
    
    async def __call__(self, state: ControlPrioritizationState) -> ControlPrioritizationState:
        """Run two-phase control prioritization"""
        try:
            universe = state.get("control_universe")
            if not universe:
                raise ValueError("Control universe not initialized")
            
            # Get configuration
            deep_research_knowledge = state.get("deep_research_knowledge")
            downstream_processing_context = state.get(
                "downstream_processing_context",
                "Controls will be used for risk estimation, monitoring, and compliance reporting"
            )
            
            # Run prioritization
            priority_infos = await universe.prioritize_all_controls_two_phase(
                llm=self.llm,
                deep_research_knowledge=deep_research_knowledge,
                state=state,
                downstream_processing_context=downstream_processing_context
            )
            
            state["priority_infos"] = priority_infos
            
            state["messages"].append({
                "role": "system",
                "content": f"Completed prioritization for {len(priority_infos)} controls"
            })
            
        except Exception as e:
            logger.error(f"Error in control prioritization: {e}")
            state["errors"].append(f"Error in control prioritization: {str(e)}")
        
        return state


class ResultsStorage:
    """Node: Store prioritization results"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("data/control_priorities")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def __call__(self, state: ControlPrioritizationState) -> ControlPrioritizationState:
        """Store prioritization results to file"""
        try:
            universe = state.get("control_universe")
            priority_infos = state.get("priority_infos", {})
            
            if not universe or not priority_infos:
                raise ValueError("Control universe or priority infos not available")
            
            # Build results summary
            results_summary = {
                "organization": universe.organization_name,
                "domain": state.get("domain_name"),
                "framework": state.get("compliance_framework"),
                "prioritization_date": datetime.now().isoformat(),
                "total_controls": len(priority_infos),
                "priority_distribution": {},
                "controls": []
            }
            
            # Count by priority level
            for control_id, priority_info in priority_infos.items():
                level = priority_info.priority_level.value
                results_summary["priority_distribution"][level] = \
                    results_summary["priority_distribution"].get(level, 0) + 1
                
                # Add control details
                control = universe.controls.get(control_id)
                control_data = {
                    "control_id": control_id,
                    "control_name": control.control_name if control else "Unknown",
                    "framework": control.framework if control else "Unknown",
                    "priority_level": priority_info.priority_level.value,
                    "priority_score": priority_info.priority_score,
                    "priority_order": priority_info.priority_order,
                    "risk_score": priority_info.risk_score,
                    "risk_classification": priority_info.risk_classification,
                    "relevance_score": priority_info.relevance_score,
                    "quality_score": priority_info.quality_score,
                    "coverage_score": priority_info.coverage_score,
                    "has_coverage_gaps": priority_info.has_coverage_gaps,
                    "priority_reasoning": priority_info.priority_reasoning
                }
                results_summary["controls"].append(control_data)
            
            # Sort controls by priority order
            results_summary["controls"].sort(key=lambda x: x["priority_order"])
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain_name = state.get("domain_name", "unknown")
            output_file = self.output_dir / f"control_priorities_{domain_name}_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(results_summary, f, indent=2)
            
            state["output_file"] = str(output_file)
            state["results_summary"] = results_summary
            
            state["messages"].append({
                "role": "system",
                "content": f"Saved prioritization results to {output_file}"
            })
            
        except Exception as e:
            logger.error(f"Error storing results: {e}")
            state["errors"].append(f"Error storing results: {str(e)}")
        
        return state


# ============================================================================
# WORKFLOW ORCHESTRATION
# ============================================================================

class ControlPrioritizationWorkflow:
    """
    Separate workflow for control prioritization.
    
    This workflow should be run periodically (not as part of feature engineering)
    to calculate and store control priorities.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        output_dir: Optional[Path] = None
    ):
        """Initialize the workflow"""
        self.llm = llm
        self.output_dir = output_dir
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(ControlPrioritizationState)
        
        # Initialize nodes
        universe_builder = ControlUniverseBuilder()
        data_loader = ExternalDataLoader()
        prioritization_agent = ControlPrioritizationAgent(self.llm)
        results_storage = ResultsStorage(self.output_dir)
        
        # Add nodes
        workflow.add_node("build_universe", universe_builder)
        workflow.add_node("load_external_data", data_loader)
        workflow.add_node("prioritize_controls", prioritization_agent)
        workflow.add_node("store_results", results_storage)
        
        # Define workflow
        workflow.set_entry_point("build_universe")
        workflow.add_edge("build_universe", "load_external_data")
        workflow.add_edge("load_external_data", "prioritize_controls")
        workflow.add_edge("prioritize_controls", "store_results")
        workflow.add_edge("store_results", END)
        
        return workflow.compile()
    
    async def run(
        self,
        organization_name: str,
        domain_name: str,
        compliance_framework: Optional[str] = None,
        external_data_file: Optional[str] = None,
        deep_research_knowledge: Optional[Dict[str, Any]] = None,
        downstream_processing_context: Optional[str] = None
    ) -> ControlPrioritizationState:
        """
        Run the control prioritization workflow.
        
        Args:
            organization_name: Name of the organization
            domain_name: Domain name (e.g., "cybersecurity", "hr_compliance")
            compliance_framework: Optional compliance framework filter
            external_data_file: Optional path to external control data file
            deep_research_knowledge: Optional deep research knowledge dict
            downstream_processing_context: Optional context about downstream processing
        
        Returns:
            ControlPrioritizationState with results
        """
        initial_state: ControlPrioritizationState = {
            "organization_name": organization_name,
            "domain_name": domain_name,
            "compliance_framework": compliance_framework,
            "controls": [],
            "control_universe": None,
            "risk_assessments": {},
            "priority_infos": {},
            "deep_research_knowledge": deep_research_knowledge,
            "downstream_processing_context": downstream_processing_context,
            "external_data_file": external_data_file,
            "output_file": None,
            "results_summary": {},
            "messages": [],
            "errors": []
        }
        
        # Run workflow
        final_state = await self.graph.ainvoke(initial_state)
        
        return final_state


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_prioritization_results(file_path: str) -> Dict[str, Any]:
    """
    Load prioritization results from a previously saved file.
    
    Args:
        file_path: Path to JSON file with prioritization results
    
    Returns:
        Dict with prioritization results
    """
    with open(file_path, 'r') as f:
        return json.load(f)


def get_control_priority_from_results(
    results: Dict[str, Any],
    control_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get priority information for a specific control from results.
    
    Args:
        results: Prioritization results dict
        control_id: Control ID to look up
    
    Returns:
        Control priority dict if found, None otherwise
    """
    controls = results.get("controls", [])
    for control in controls:
        if control.get("control_id") == control_id:
            return control
    return None

