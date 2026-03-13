#!/usr/bin/env python3
"""
Test suite for CSOD Metric Advisor Workflow.

This test validates the CSOD Metric Advisor workflow pipeline for metric and KPI recommendations
with causal graph integration.

UPDATED: Now uses the new conversation engine (app.conversation.planner_workflow) instead of
the legacy csod_planner_workflow. The conversation engine provides:
- Multi-turn conversation support with interrupts
- Scoping questions based on area filters
- Concept and area confirmation
- Metric narration
- Automatic checkpoint handling and resumption

Test Cases:
1. Use Case 1: Basic Metric Advisor (compliance training effectiveness)
2. Use Case 2: Metric Advisor with Causal Graph (learning effectiveness)
3. Use Case 3: KPI Relations Mapping (metric relationships)
4. Use Case 4: Reasoning Plan Generation (structured reasoning)
5. Use Case 5: Lexy Pre-Resolved Intent (skip classification)
6. Use Case 6: Planner Workflow Integration

Configuration:
- Data Sources: cornerstone, workday
- Metrics Registry: lms_metrics_registry.json
- Causal Vertical: lms
- Conversation Config: LMS_CONVERSATION_CONFIG (from app.conversation.verticals.lms_config)

Uses .env configuration for LLM and vector store settings.
Generates output in tests/outputs/metric_advisor_* directories for comparison.

Note: Tests auto-respond to conversation checkpoints to simulate user interaction.
In production, the API layer handles checkpoint resumption with actual user responses.
"""
import os
import sys
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load .env file before importing app modules
base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✓ Loaded .env file from: {env_file}")
else:
    print("⚠️  No .env file found. Using default environment variables.")

# Add parent directory to path
sys.path.insert(0, str(base_dir))

from app.agents.csod.csod_metric_advisor_workflow import (
    create_csod_metric_advisor_initial_state,
    get_csod_metric_advisor_app,
)
from app.conversation.planner_workflow import create_conversation_planner_app
from app.conversation.verticals.lms_config import LMS_CONVERSATION_CONFIG
from app.conversation.integration import invoke_workflow_after_conversation
from app.conversation.turn import ConversationCheckpoint
from langgraph.checkpoint.memory import MemorySaver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Also configure app loggers
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.agents").setLevel(logging.INFO)
logging.getLogger("app.agents.csod").setLevel(logging.INFO)

# Force immediate output
sys.stdout.flush()
sys.stderr.flush()

# Create output directory structure: tests/outputs/metric_advisor_testcase_name/timestamp/
OUTPUT_BASE_DIR = base_dir / "tests" / "outputs"
OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Constants
DATA_SOURCES = ["cornerstone", "workday"]


def safe_get_id(item: Any, id_key: str = "concept_id") -> Any:
    """
    Safely extract ID from dict or object.
    
    Args:
        item: Dict or object with ID field
        id_key: Key/attribute name for ID (default: "concept_id")
    
    Returns:
        ID value or None if not found
    """
    if item is None:
        return None
    if isinstance(item, dict):
        return item.get(id_key)
    elif hasattr(item, id_key):
        return getattr(item, id_key)
    elif hasattr(item, "to_dict"):
        try:
            return item.to_dict().get(id_key)
        except Exception:
            return None
    return None


class MetricAdvisorWorkflowTester:
    """Test suite for CSOD Metric Advisor workflow."""
    
    def __init__(self, output_base_dir: Path = None):
        self.app = None
        self.planner_app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_base_dir = output_base_dir or OUTPUT_BASE_DIR
        self.current_test_output_dir = None
        self.skip_slow = False
        self.use_planner_workflow = True  # Default to using planner workflow
    
    def setup(self):
        """Initialize the Metric Advisor workflow app and conversation planner app."""
        logger.info("Setting up CSOD Metric Advisor workflow apps...")
        self.app = get_csod_metric_advisor_app()
        if self.use_planner_workflow:
            self.planner_app = create_conversation_planner_app(LMS_CONVERSATION_CONFIG)
            logger.info("✓ Conversation planner workflow app initialized")
            logger.info(f"  Planner nodes: {list(self.planner_app.nodes.keys())}")
        logger.info("✓ Metric Advisor workflow app initialized")
        logger.info(f"  Main workflow nodes: {list(self.app.nodes.keys())}")
    
    def load_metrics_registry(self, registry_path: str = None) -> list:
        """
        Load metrics registry from JSON file.
        
        Args:
            registry_path: Path to metrics registry JSON file.
                          Defaults to data/lms_metrics_registry.json
        
        Returns:
            List of metric dicts
        """
        if registry_path is None:
            # Default to lms_metrics_registry.json in data/
            registry_path = base_dir / "data" / "lms_metrics_registry.json"
        
        registry_path = Path(registry_path)
        if not registry_path.exists():
            logger.warning(f"Metrics registry not found at {registry_path}")
            logger.info("Using empty registry - workflow will still run but with limited metrics")
            return []
        
        with open(registry_path, "r") as f:
            data = json.load(f)
        
        # Handle different formats
        if isinstance(data, dict) and "metrics" in data:
            metrics = data["metrics"]
        elif isinstance(data, list):
            metrics = data
        else:
            logger.warning(f"Unexpected registry format in {registry_path}")
            return []
        
        logger.info(f"Loaded {len(metrics)} metrics from {registry_path}")
        return metrics
    
    def create_initial_state(
        self,
        user_query: str,
        session_id: str = None,
        causal_graph_enabled: bool = True,
        causal_vertical: str = "lms",
        metrics_registry_path: str = None,
        selected_data_sources: List[str] = None,
        compliance_profile: Dict[str, Any] = None,
        lexy_pre_resolved: bool = False,
        lexy_metric_narration: str = None,
        use_planner: bool = None,
    ) -> Dict[str, Any]:
        """
        Create initial state for the Metric Advisor workflow.
        
        Args:
            user_query: User's natural language query
            session_id: Optional session ID
            causal_graph_enabled: Enable causal graph
            causal_vertical: Causal vertical identifier
            metrics_registry_path: Path to metrics registry JSON
            selected_data_sources: List of data source IDs
            compliance_profile: Optional compliance profile dict with Lexy conversational layer fields
            lexy_pre_resolved: If True, pre-set csod_intent to test Lexy skip path
            lexy_metric_narration: Optional metric narration from Lexy Phase 3
            use_planner: If True, use planner workflow first (default: self.use_planner_workflow)
        """
        use_planner = use_planner if use_planner is not None else self.use_planner_workflow
        
        if use_planner:
            # Use planner workflow to resolve concepts and project_ids
            return self._create_state_with_planner(
                user_query=user_query,
                session_id=session_id,
                selected_data_sources=selected_data_sources,
                compliance_profile=compliance_profile,
                lexy_pre_resolved=lexy_pre_resolved,
                lexy_metric_narration=lexy_metric_narration,
                causal_graph_enabled=causal_graph_enabled,
                causal_vertical=causal_vertical,
                metrics_registry_path=metrics_registry_path,
            )
        
        # Legacy path: direct Metric Advisor workflow
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if compliance_profile is None:
            compliance_profile = {}
        
        # If testing Lexy pre-resolved path, add the required fields
        if lexy_pre_resolved:
            if lexy_metric_narration:
                compliance_profile["lexy_metric_narration"] = lexy_metric_narration
        
        state = create_csod_metric_advisor_initial_state(
            user_query=user_query,
            session_id=session_id,
            active_project_id=None,
            selected_data_sources=selected_data_sources or DATA_SOURCES,
            compliance_profile=compliance_profile,
            causal_graph_enabled=causal_graph_enabled,
            causal_vertical=causal_vertical,
        )
        
        # Pre-set intent if testing Lexy skip path
        if lexy_pre_resolved:
            state["csod_intent"] = "metric_kpi_advisor"
            logger.info(f"  ✓ Pre-resolved intent (Lexy skip path): {state['csod_intent']}")
        
        # Load and add metrics registry
        metrics_registry = self.load_metrics_registry(metrics_registry_path)
        if metrics_registry:
            state["csod_causal_metric_registry"] = metrics_registry
            state["csod_retrieved_metrics"] = metrics_registry[:20]  # Use first 20 for testing
            logger.info(f"  ✓ Added {len(metrics_registry)} metrics to state")
        
        logger.info(f"  ✓ Initial state created with {len(selected_data_sources or DATA_SOURCES)} data sources")
        if compliance_profile:
            logger.info(f"  ✓ Compliance profile includes: {list(compliance_profile.keys())}")
        return state
    
    def _create_state_with_planner(
        self,
        user_query: str,
        session_id: str = None,
        selected_data_sources: List[str] = None,
        compliance_profile: Dict[str, Any] = None,
        lexy_pre_resolved: bool = False,
        lexy_metric_narration: str = None,
        causal_graph_enabled: bool = True,
        causal_vertical: str = "lms",
        metrics_registry_path: str = None,
    ) -> Dict[str, Any]:
        """
        Create initial state by running conversation planner workflow first, then preparing for metric advisor workflow.
        
        Handles multi-turn conversations with interrupts (checkpoints).
        Returns state ready to pass to invoke_workflow_after_conversation().
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if compliance_profile is None:
            compliance_profile = {}
        
        # If testing Lexy pre-resolved path, add the required fields
        if lexy_pre_resolved:
            if lexy_metric_narration:
                compliance_profile["lexy_metric_narration"] = lexy_metric_narration
        
        # Determine datasource from selected_data_sources or default
        datasource = "cornerstone"  # Default
        if selected_data_sources:
            first_source = selected_data_sources[0].split(".")[0] if "." in selected_data_sources[0] else selected_data_sources[0]
            datasource = first_source
        
        # Create conversation planner initial state
        planner_state = {
            "user_query": user_query,
            "session_id": session_id,
            "csod_selected_datasource": datasource,
            "csod_datasource_confirmed": True,  # Skip datasource selection in tests
            "csod_concept_matches": [],
            "csod_selected_concepts": [],
            "csod_confirmed_concept_ids": [],
            "csod_scoping_answers": compliance_profile.get("scoping_answers", {}),
            "csod_scoping_complete": len(compliance_profile.get("scoping_answers", {})) > 0,
            "csod_area_matches": [],
            "csod_preliminary_area_matches": [],
            "csod_primary_area": {},
            "csod_confirmed_area_id": None,
            "csod_metric_narration": lexy_metric_narration,
            "csod_metric_narration_confirmed": lexy_pre_resolved and bool(lexy_metric_narration),
            "csod_conversation_checkpoint": None,
            "csod_checkpoint_resolved": False,
            "csod_use_advisor_workflow": True,  # Force advisor workflow for metric advisor tests
            "compliance_profile": compliance_profile,
            "active_project_id": None,
            "selected_data_sources": selected_data_sources or [],
        }
        
        # Update config with session_id as thread_id
        self.config = {"configurable": {"thread_id": session_id}}
        
        # Run conversation planner workflow (handles interrupts automatically)
        logger.info("  → Running conversation planner workflow to resolve concepts and project_ids...")
        planner_final_state = None
        max_turns = 10  # Max conversation turns (each turn may have multiple nodes)
        turn_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        # Create planner stages output directory if we have a current test output dir
        planner_stages_dir = None
        if hasattr(self, 'current_test_output_dir') and self.current_test_output_dir:
            planner_stages_dir = self.current_test_output_dir / "planner_stages"
            planner_stages_dir.mkdir(parents=True, exist_ok=True)
        
        while turn_count < max_turns:
            try:
                # Invoke graph (will pause at interrupt or complete)
                result = self.planner_app.invoke(planner_state, self.config)
                
                # Check for checkpoint (interrupt)
                checkpoint = result.get("csod_conversation_checkpoint")
                checkpoint_resolved = result.get("csod_checkpoint_resolved", False)
                
                if checkpoint and not checkpoint_resolved:
                    # Graph paused at checkpoint - get state from checkpointer and update it
                    try:
                        state_snapshot = self.planner_app.get_state(self.config)
                        if not state_snapshot or not state_snapshot.values:
                            logger.warning(f"    → No state snapshot found for checkpoint, breaking")
                            break
                        
                        current_state = state_snapshot.values.copy()
                        
                        # Validate checkpoint format
                        if not isinstance(checkpoint, dict):
                            logger.warning(f"    → Invalid checkpoint format: {type(checkpoint)}, breaking")
                            break
                        
                        # Parse checkpoint with error handling
                        try:
                            checkpoint_obj = ConversationCheckpoint.from_dict(checkpoint)
                            resume_field = checkpoint_obj.resume_with_field
                            phase = checkpoint_obj.phase
                        except (KeyError, ValueError, TypeError, AttributeError) as e:
                            logger.error(f"    → Failed to parse checkpoint: {e}", exc_info=True)
                            consecutive_failures += 1
                            if consecutive_failures >= max_consecutive_failures:
                                logger.error(f"    → Too many consecutive failures ({consecutive_failures}), breaking")
                                break
                            continue
                        
                        logger.info(f"    → Checkpoint detected at phase: {phase}")
                        
                        # Auto-respond based on checkpoint phase
                        if phase == "concept_confirm":
                            # Auto-confirm first concept
                            concept_matches = current_state.get("csod_concept_matches", [])
                            if not isinstance(concept_matches, list):
                                logger.warning(f"    → Invalid concept_matches format: {type(concept_matches)}")
                                concept_matches = []
                            
                            if not concept_matches:
                                logger.warning("    → No concept matches found, cannot auto-confirm")
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    break
                                continue
                            
                            concept_id = safe_get_id(concept_matches[0], "concept_id")
                            if not concept_id:
                                logger.warning("    → Concept match missing concept_id")
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    break
                                continue
                            
                            current_state["csod_confirmed_concept_ids"] = [concept_id]
                            logger.info(f"    → Auto-confirmed concept: {current_state['csod_confirmed_concept_ids']}")
                            consecutive_failures = 0  # Reset on success
                        
                        elif phase == "scoping":
                            # Use pre-filled scoping answers or provide defaults
                            scoping_answers = compliance_profile.get("scoping_answers", {})
                            if not scoping_answers or not isinstance(scoping_answers, dict):
                                # Provide default scoping answers
                                scoping_answers = {
                                    "org_unit": "whole_org",
                                    "time_window": "last_quarter",
                                }
                            current_state["csod_scoping_answers"] = scoping_answers
                            logger.info(f"    → Auto-filled scoping answers: {list(scoping_answers.keys())}")
                            consecutive_failures = 0  # Reset on success
                        
                        elif phase == "area_confirm":
                            # Auto-confirm first area
                            area_matches = current_state.get("csod_area_matches", [])
                            if not isinstance(area_matches, list):
                                logger.warning(f"    → Invalid area_matches format: {type(area_matches)}")
                                area_matches = []
                            
                            if not area_matches:
                                logger.warning("    → No area matches found, cannot auto-confirm")
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    break
                                continue
                            
                            area_id = safe_get_id(area_matches[0], "area_id")
                            if not area_id:
                                logger.warning("    → Area match missing area_id")
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    break
                                continue
                            
                            current_state["csod_confirmed_area_id"] = area_id
                            logger.info(f"    → Auto-confirmed area: {area_id}")
                            consecutive_failures = 0  # Reset on success
                        
                        elif phase == "metric_narration":
                            # Auto-confirm metric narration
                            current_state["csod_metric_narration_confirmed"] = True
                            logger.info("    → Auto-confirmed metric narration")
                            consecutive_failures = 0  # Reset on success
                        
                        else:
                            logger.warning(f"    → Unknown checkpoint phase: {phase}, resolving anyway")
                            consecutive_failures = 0  # Reset on success
                        
                        # Mark checkpoint as resolved and resume workflow
                        current_state["csod_checkpoint_resolved"] = True
                        planner_state = current_state
                        turn_count += 1
                        continue  # Resume workflow with updated state
                        
                    except Exception as e:
                        logger.error(f"    → Error handling checkpoint: {e}", exc_info=True)
                        consecutive_failures += 1
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error(f"    → Too many consecutive failures ({consecutive_failures}), breaking")
                            break
                        continue
                
                # No checkpoint or checkpoint resolved - conversation complete
                planner_final_state = result
                consecutive_failures = 0  # Reset on success
                break
                
            except Exception as e:
                logger.error(f"    → Error in conversation turn {turn_count + 1}: {e}", exc_info=True)
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"    → Too many consecutive failures ({consecutive_failures}), breaking")
                break
                continue
        
        if planner_stages_dir:
            logger.info(f"  ✓ Saved planner stage outputs to {planner_stages_dir}")
        
        if planner_final_state is None:
            logger.warning("Planner workflow did not complete, falling back to direct workflow")
            return self.create_initial_state(
                user_query=user_query,
                session_id=session_id,
                selected_data_sources=selected_data_sources,
                compliance_profile=compliance_profile,
                lexy_pre_resolved=lexy_pre_resolved,
                lexy_metric_narration=lexy_metric_narration,
                causal_graph_enabled=causal_graph_enabled,
                causal_vertical=causal_vertical,
                metrics_registry_path=metrics_registry_path,
                use_planner=False,
            )
        
        # Verify conversation completed successfully
        if not planner_final_state.get("csod_target_workflow"):
            logger.warning("Conversation completed but no target_workflow set - this may be expected for some test cases")
            # Don't fail here, but log it for debugging
        
        # Ensure session_id is preserved in the final state
        if not planner_final_state.get("session_id"):
            planner_final_state["session_id"] = session_id
            logger.info(f"  ✓ Preserved session_id in conversation state: {session_id}")
        
        # Merge compliance_profile from test into planner-resolved profile
        planner_profile = planner_final_state.get("compliance_profile", {})
        if not isinstance(planner_profile, dict):
            planner_profile = {}
        planner_profile.update(compliance_profile)
        planner_final_state["compliance_profile"] = planner_profile
        
        # Set causal graph settings
        planner_final_state["csod_causal_graph_enabled"] = causal_graph_enabled
        planner_final_state["causal_vertical"] = causal_vertical
        
        # Pre-set intent if testing Lexy skip path
        if lexy_pre_resolved:
            planner_final_state["csod_intent"] = "metric_kpi_advisor"
            logger.info(f"  ✓ Pre-resolved intent (Lexy skip path): {planner_final_state['csod_intent']}")
        
        # Load and add metrics registry
        metrics_registry = self.load_metrics_registry(metrics_registry_path)
        if metrics_registry:
            planner_final_state["csod_causal_metric_registry"] = metrics_registry
            planner_final_state["csod_retrieved_metrics"] = metrics_registry[:20]
            logger.info(f"  ✓ Added {len(metrics_registry)} metrics to state")
        
        # Log planner results
        resolved_project_ids = planner_final_state.get("csod_resolved_project_ids", [])
        selected_concepts = planner_final_state.get("csod_selected_concepts", [])
        logger.info(f"  ✓ Planner resolved {len(selected_concepts)} concepts, {len(resolved_project_ids)} project_ids")
        if resolved_project_ids:
            logger.info(f"  ✓ Primary project_id: {planner_final_state.get('csod_primary_project_id')}")
        
        return planner_final_state
    
    def run_workflow(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run workflow (with planner integration if enabled).
        
        Args:
            initial_state: Initial state dict
            
        Returns:
            Final state from workflow execution
        """
        # Check if conversation planner workflow already ran
        if self.use_planner_workflow and initial_state.get("csod_target_workflow"):
            # Conversation planner workflow already ran, invoke downstream workflow
            logger.info(f"  → Invoking downstream workflow: {initial_state.get('csod_target_workflow')}")
            
            # Create stages output directory if we have a current test output dir
            stages_dir = None
            if hasattr(self, 'current_test_output_dir') and self.current_test_output_dir:
                stages_dir = self.current_test_output_dir / "stages"
                stages_dir.mkdir(parents=True, exist_ok=True)
            
            # Track previous state for input/output logging
            previous_state = initial_state.copy()
            iteration_count = 0
            
            # Use integration helper to invoke workflow
            # First, create initial state for the metric advisor workflow
            from app.agents.csod.csod_metric_advisor_workflow import create_csod_metric_advisor_initial_state
            
            advisor_initial_state = create_csod_metric_advisor_initial_state(
                user_query=initial_state.get("user_query", ""),
                session_id=initial_state.get("session_id", ""),
                active_project_id=initial_state.get("active_project_id"),
                selected_data_sources=initial_state.get("selected_data_sources", []),
                compliance_profile=initial_state.get("compliance_profile", {}),
                causal_graph_enabled=initial_state.get("csod_causal_graph_enabled", True),
                causal_vertical=initial_state.get("causal_vertical", "lms"),
            )
            
            # Merge conversation state into advisor initial state
            advisor_initial_state.update(initial_state)
            
            # Stream the downstream workflow to capture stages
            final_state = None
            for event in self.app.stream(advisor_initial_state, self.config):
                node_name = list(event.keys())[0]
                node_output = event[node_name]
                logger.info(f"  → {node_name} (iteration {iteration_count + 1})")
                
                # Save stage input and output if stages directory exists
                if stages_dir:
                    try:
                        stage_file = stages_dir / f"stage_{iteration_count:03d}_{node_name}.json"
                        stage_data = {
                            "iteration": iteration_count + 1,
                            "node_name": node_name,
                            "timestamp": datetime.utcnow().isoformat(),
                            "input": self.sanitize_for_json(previous_state),
                            "output": self.sanitize_for_json(node_output),
                        }
                        with open(stage_file, 'w') as f:
                            json.dump(stage_data, f, indent=2, default=str)
                        logger.debug(f"    Saved stage input/output to {stage_file}")
                    except Exception as e:
                        logger.warning(f"    Failed to save stage output: {e}")
                
                final_state = node_output
                previous_state = node_output.copy() if isinstance(node_output, dict) else node_output
                iteration_count += 1
                
                if iteration_count >= 50:
                    logger.warning(f"Downstream workflow exceeded 50 iterations")
                    break
            
            if stages_dir:
                logger.info(f"  ✓ Saved {iteration_count} stage outputs to {stages_dir}")
            
            return final_state if final_state is not None else invoke_workflow_after_conversation(
                conversation_state=initial_state,
                csod_metric_advisor_app=self.app,
            )
        else:
            # Run workflow directly (legacy path or planner disabled)
            final_state = None
            max_iterations = 50
            iteration_count = 0
            
            # Create stages output directory if we have a current test output dir
            stages_dir = None
            if hasattr(self, 'current_test_output_dir') and self.current_test_output_dir:
                stages_dir = self.current_test_output_dir / "stages"
                stages_dir.mkdir(parents=True, exist_ok=True)
            
            # Track previous state for input/output logging
            previous_state = initial_state.copy()
            
            for event in self.app.stream(initial_state, self.config):
                node_name = list(event.keys())[0]
                node_output = event[node_name]
                logger.info(f"  → {node_name} (iteration {iteration_count + 1})")
                
                # Save stage input and output if stages directory exists
                if stages_dir:
                    try:
                        stage_file = stages_dir / f"stage_{iteration_count:03d}_{node_name}.json"
                        stage_data = {
                            "iteration": iteration_count + 1,
                            "node_name": node_name,
                            "timestamp": datetime.utcnow().isoformat(),
                            "input": self.sanitize_for_json(previous_state),
                            "output": self.sanitize_for_json(node_output),
                        }
                        with open(stage_file, 'w') as f:
                            json.dump(stage_data, f, indent=2, default=str)
                        logger.debug(f"    Saved stage input/output to {stage_file}")
                    except Exception as e:
                        logger.warning(f"    Failed to save stage output: {e}")
                
                final_state = node_output
                previous_state = node_output.copy() if isinstance(node_output, dict) else node_output
                iteration_count += 1
                
                if iteration_count >= max_iterations:
                    logger.error(f"Workflow exceeded {max_iterations} iterations!")
                    raise RuntimeError(f"Workflow exceeded {max_iterations} iterations")
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            if stages_dir:
                logger.info(f"  ✓ Saved {iteration_count} stage outputs to {stages_dir}")
            
            return final_state
    
    def test_use_case_1_basic_metric_advisor(self) -> Dict[str, Any]:
        """
        Test: Use Case 1 - Basic Metric Advisor
        
        Tests basic metric recommendation without causal graph.
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 1 - Basic Metric Advisor")
        logger.info("=" * 80)
        
        user_query = "What metrics should I track for compliance training effectiveness?"
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            causal_graph_enabled=False,
        )
        
        try:
            logger.info(f"Executing Metric Advisor workflow with query: {user_query[:100]}...")
            final_state = self.run_workflow(initial_state)
            
            # Validate outputs
            validation_results = self.validate_metric_advisor_outputs(final_state)
            self.get_test_output_dir("metric_advisor_use_case_1_basic")
            self.save_test_output("metric_advisor_use_case_1_basic", final_state, validation_results)
            
            return {
                "test_name": "metric_advisor_use_case_1_basic",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_advisor_use_case_1_basic",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_2_causal_graph_advisor(self) -> Dict[str, Any]:
        """
        Test: Use Case 2 - Metric Advisor with Causal Graph
        
        Tests metric recommendation with causal graph enabled.
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 2 - Metric Advisor with Causal Graph")
        logger.info("=" * 80)
        
        user_query = "What metrics should I track for learning effectiveness and pass rates?"
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            causal_graph_enabled=True,
            causal_vertical="lms",
        )
        
        try:
            logger.info(f"Executing Metric Advisor workflow with query: {user_query[:100]}...")
            final_state = self.run_workflow(initial_state)
            
            # Validate outputs
            validation_results = self.validate_metric_advisor_outputs(final_state, expect_causal_graph=True)
            self.get_test_output_dir("metric_advisor_use_case_2_causal")
            self.save_test_output("metric_advisor_use_case_2_causal", final_state, validation_results)
            
            return {
                "test_name": "metric_advisor_use_case_2_causal",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_advisor_use_case_2_causal",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_3_kpi_relations(self) -> Dict[str, Any]:
        """
        Test: Use Case 3 - KPI Relations Mapping
        
        Tests metric/KPI relation mapping functionality.
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 3 - KPI Relations Mapping")
        logger.info("=" * 80)
        
        user_query = "Show me how completion rate relates to pass rate and compliance metrics."
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            causal_graph_enabled=True,
            causal_vertical="lms",
        )
        
        try:
            logger.info(f"Executing Metric Advisor workflow with query: {user_query[:100]}...")
            final_state = self.run_workflow(initial_state)
            
            # Validate outputs
            validation_results = self.validate_metric_advisor_outputs(final_state, expect_relations=True)
            self.get_test_output_dir("metric_advisor_use_case_3_relations")
            self.save_test_output("metric_advisor_use_case_3_relations", final_state, validation_results)
            
            return {
                "test_name": "metric_advisor_use_case_3_relations",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_advisor_use_case_3_relations",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_5_lexy_pre_resolved_advisor(self) -> Dict[str, Any]:
        """
        Test: Use Case 5 - Lexy Pre-Resolved Intent for Metric Advisor
        
        Tests that the intent classifier skips LLM classification when Lexy
        has pre-resolved the intent via conversational layer for metric advisor workflow.
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 5 - Lexy Pre-Resolved Intent for Metric Advisor")
        logger.info("=" * 80)
        
        user_query = "What metrics should I track for compliance training effectiveness?"
        
        # Create compliance profile with Lexy conversational layer fields
        compliance_profile = {
            "lexy_metric_narration": (
                "Based on your question, I'm recommending metrics for compliance training effectiveness. "
                "I'll focus on completion rates, pass rates, and engagement metrics."
            ),
            "time_window": "last_quarter",
            "org_unit": "whole_org",
            "persona": "compliance_officer",
            "skills_domain": "compliance",
        }
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            compliance_profile=compliance_profile,
            lexy_pre_resolved=True,
            lexy_metric_narration=compliance_profile["lexy_metric_narration"],
            causal_graph_enabled=True,
        )
        
        try:
            logger.info(f"Executing Metric Advisor workflow with pre-resolved intent: {initial_state.get('csod_intent')}")
            logger.info(f"  Lexy metric narration present: {bool(compliance_profile.get('lexy_metric_narration'))}")
            
            final_state = self.run_workflow(initial_state)
            
            # Check if intent classifier skipped LLM call (for logging)
            messages = final_state.get("messages", [])
            for msg in messages:
                if isinstance(msg, dict) and "content" in msg:
                    content = msg["content"]
                    if "pre-resolved by Lexy" in content or "lexy_conversational_layer" in str(content).lower():
                        logger.info(f"  ✓ Intent classifier detected Lexy pre-resolved intent")
                elif hasattr(msg, "content"):
                    content = str(msg.content)
                    if "pre-resolved by Lexy" in content or "lexy_conversational_layer" in content.lower():
                        logger.info(f"  ✓ Intent classifier detected Lexy pre-resolved intent")
            
            # Validate outputs
            validation_results = self.validate_metric_advisor_outputs(
                final_state,
                expect_lexy_pre_resolved=True
            )
            self.get_test_output_dir("metric_advisor_use_case_5_lexy_pre_resolved")
            self.save_test_output("metric_advisor_use_case_5_lexy_pre_resolved", final_state, validation_results)
            
            return {
                "test_name": "metric_advisor_use_case_5_lexy_pre_resolved",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_advisor_use_case_5_lexy_pre_resolved",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_6_planner_workflow_integration(self) -> Dict[str, Any]:
        """
        Test: Use Case 6 - Planner Workflow Integration for Metric Advisor
        
        Tests that the planner workflow correctly resolves concepts, project_ids,
        and recommendation areas, then routes to the metric advisor workflow.
        
        Expected behavior:
        - Planner resolves concepts using L1 collection
        - Planner resolves project_ids from concepts
        - Planner matches recommendation areas using L2 collection
        - Planner routes to metric_advisor_workflow
        - Metric advisor workflow uses planner-resolved state
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 6 - Planner Workflow Integration for Metric Advisor")
        logger.info("=" * 80)
        
        user_query = "What metrics should I track for compliance training effectiveness?"
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            selected_data_sources=["cornerstone"],
            use_planner=True,
            causal_graph_enabled=True,
        )
        
        try:
            logger.info(f"Executing planner + Metric Advisor workflow with query: {user_query[:100]}...")
            
            # Conversation planner workflow should have already run in create_initial_state
            if not initial_state.get("csod_target_workflow"):
                logger.warning("Conversation planner workflow did not set target_workflow, running planner now...")
                # Re-run planner if needed - use the same method as _create_state_with_planner
                initial_state = self._create_state_with_planner(
                    user_query=user_query,
                    selected_data_sources=["cornerstone"],
                    causal_graph_enabled=True,
                )
            
            # Invoke downstream workflow
            logger.info(f"  → Invoking downstream workflow: {initial_state.get('csod_target_workflow', 'csod_metric_advisor_workflow')}")
            final_state = invoke_workflow_after_conversation(
                conversation_state=initial_state,
                csod_metric_advisor_app=self.app,
            )
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate planner integration
            validation_results = self.validate_metric_advisor_outputs(
                final_state,
                expect_planner_integration=True
            )
            self.get_test_output_dir("metric_advisor_use_case_6_planner_integration")
            self.save_test_output("metric_advisor_use_case_6_planner_integration", final_state, validation_results)
            
            return {
                "test_name": "metric_advisor_use_case_6_planner_integration",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_advisor_use_case_6_planner_integration",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_4_reasoning_plan(self) -> Dict[str, Any]:
        """
        Test: Use Case 4 - Reasoning Plan Generation
        
        Tests structured reasoning plan generation.
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 4 - Reasoning Plan Generation")
        logger.info("=" * 80)
        
        user_query = "Generate a reasoning plan for tracking training ROI and cost efficiency."
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            causal_graph_enabled=True,
            causal_vertical="lms",
        )
        
        # Pre-set intent to metric_kpi_advisor to ensure routing to metric advisor node
        initial_state["csod_intent"] = "metric_kpi_advisor"
        logger.info(f"  ✓ Pre-set intent to: {initial_state['csod_intent']}")
        
        try:
            logger.info(f"Executing Metric Advisor workflow with query: {user_query[:100]}...")
            final_state = self.run_workflow(initial_state)
            
            # Validate outputs
            validation_results = self.validate_metric_advisor_outputs(final_state, expect_reasoning_plan=True)
            self.get_test_output_dir("metric_advisor_use_case_4_reasoning")
            self.save_test_output("metric_advisor_use_case_4_reasoning", final_state, validation_results)
            
            return {
                "test_name": "metric_advisor_use_case_4_reasoning",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_advisor_use_case_4_reasoning",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_metric_advisor_outputs(
        self,
        result: Dict[str, Any],
        expect_causal_graph: bool = False,
        expect_relations: bool = False,
        expect_reasoning_plan: bool = False,
        expect_lexy_pre_resolved: bool = False,
        expect_planner_integration: bool = False,
    ) -> Dict[str, Any]:
        """Validate Metric Advisor-specific outputs."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent classification
        csod_intent = result.get("csod_intent")
        validation["checks"]["has_intent"] = csod_intent is not None
        if not validation["checks"]["has_intent"]:
            validation["issues"].append("Intent not classified")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Intent: {csod_intent}")
        
        # Check 2: Metric recommendations
        metric_recommendations = result.get("csod_metric_recommendations", [])
        validation["checks"]["has_metric_recommendations"] = len(metric_recommendations) > 0
        if not validation["checks"]["has_metric_recommendations"]:
            validation["issues"].append("No metric recommendations generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Generated {len(metric_recommendations)} metric recommendations")
        
        # Check 3: Causal graph (if expected)
        if expect_causal_graph:
            causal_nodes = result.get("csod_causal_nodes", [])
            causal_edges = result.get("csod_causal_edges", [])
            validation["checks"]["has_causal_nodes"] = len(causal_nodes) > 0
            validation["checks"]["has_causal_edges"] = len(causal_edges) > 0
            if not validation["checks"]["has_causal_nodes"]:
                validation["issues"].append("No causal nodes generated")
            if not validation["checks"]["has_causal_edges"]:
                validation["issues"].append("No causal edges generated")
            if validation["checks"]["has_causal_nodes"] and validation["checks"]["has_causal_edges"]:
                logger.info(f"  ✓ Causal graph: {len(causal_nodes)} nodes, {len(causal_edges)} edges")
        
        # Check 4: Metric/KPI relations (if expected)
        if expect_relations:
            metric_kpi_relations = result.get("csod_metric_kpi_relations", {})
            validation["checks"]["has_relations"] = bool(metric_kpi_relations)
            if not validation["checks"]["has_relations"]:
                validation["issues"].append("No metric/KPI relations generated")
                validation["overall_success"] = False
            else:
                relation_count = len(metric_kpi_relations.get("relations", []))
                logger.info(f"  ✓ Generated {relation_count} metric/KPI relations")
        
        # Check 5: Reasoning plan (if expected)
        if expect_reasoning_plan:
            reasoning_plan = result.get("csod_reasoning_plan", {})
            validation["checks"]["has_reasoning_plan"] = bool(reasoning_plan)
            if not validation["checks"]["has_reasoning_plan"]:
                validation["issues"].append("No reasoning plan generated")
                validation["overall_success"] = False
            else:
                logger.info("  ✓ Reasoning plan generated")
        
        # Check 6: Advisor output
        advisor_output = result.get("csod_advisor_output")
        validation["checks"]["has_advisor_output"] = advisor_output is not None
        if not validation["checks"]["has_advisor_output"]:
            validation["issues"].append("No advisor output generated")
        else:
            logger.info("  ✓ Advisor output generated")
        
        # Check 7: Assembled output
        assembled_output = result.get("csod_assembled_output")
        validation["checks"]["has_assembled_output"] = assembled_output is not None
        if not validation["checks"]["has_assembled_output"]:
            validation["issues"].append("No assembled output generated")
        else:
            logger.info("  ✓ Assembled output generated")
        
        # Check 8: Lexy pre-resolved intent (if expected)
        if expect_lexy_pre_resolved:
            messages = result.get("messages", [])
            lexy_detected = False
            for msg in messages:
                if isinstance(msg, dict) and "content" in msg:
                    content = str(msg["content"]).lower()
                    if "pre-resolved by lexy" in content or "lexy_conversational_layer" in content:
                        lexy_detected = True
                        break
                elif hasattr(msg, "content"):
                    content = str(msg.content).lower()
                    if "pre-resolved by lexy" in content or "lexy_conversational_layer" in content:
                        lexy_detected = True
                        break
            
            validation["checks"]["lexy_pre_resolved_detected"] = lexy_detected
            if not lexy_detected:
                validation["issues"].append("Lexy pre-resolved intent not detected in messages")
            else:
                logger.info("  ✓ Lexy pre-resolved intent path detected")
        
        # Check 9: Planner workflow integration (if planner was used or expected)
        if expect_planner_integration or result.get("csod_resolved_project_ids"):
            resolved_project_ids = result.get("csod_resolved_project_ids", [])
            selected_concepts = result.get("csod_selected_concepts", [])
            primary_area = result.get("csod_primary_area", {})
            
            validation["checks"]["planner_resolved_project_ids"] = len(resolved_project_ids) > 0
            validation["checks"]["planner_resolved_concepts"] = len(selected_concepts) > 0
            validation["checks"]["planner_resolved_area"] = bool(primary_area)
            
            if validation["checks"]["planner_resolved_project_ids"]:
                logger.info(f"  ✓ Planner resolved {len(resolved_project_ids)} project_ids")
            if validation["checks"]["planner_resolved_concepts"]:
                logger.info(f"  ✓ Planner resolved {len(selected_concepts)} concepts")
            if validation["checks"]["planner_resolved_area"]:
                logger.info(f"  ✓ Planner resolved recommendation area: {primary_area.get('display_name', 'N/A')}")
            
            # Check compliance_profile has planner-resolved fields
            compliance_profile = result.get("compliance_profile", {})
            validation["checks"]["has_priority_metrics"] = len(compliance_profile.get("priority_metrics", [])) > 0
            validation["checks"]["has_data_requirements"] = len(compliance_profile.get("data_requirements", [])) > 0
            validation["checks"]["has_active_mdl_tables"] = len(compliance_profile.get("active_mdl_tables", [])) > 0
            
            if validation["checks"]["has_priority_metrics"]:
                logger.info(f"  ✓ Priority metrics from planner: {len(compliance_profile.get('priority_metrics', []))}")
            if validation["checks"]["has_data_requirements"]:
                logger.info(f"  ✓ Data requirements from planner: {len(compliance_profile.get('data_requirements', []))}")
            if validation["checks"]["has_active_mdl_tables"]:
                logger.info(f"  ✓ Active MDL tables from planner: {len(compliance_profile.get('active_mdl_tables', []))}")
        
        return validation
    
    def get_test_output_dir(self, test_name: str) -> Path:
        """Create and return test-specific output directory: tests/outputs/metric_advisor_testcase_name/timestamp/"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_output_dir = self.output_base_dir / test_name / timestamp
        test_output_dir.mkdir(parents=True, exist_ok=True)
        self.current_test_output_dir = test_output_dir
        return test_output_dir
    
    def save_test_output(self, test_name: str, result: Dict[str, Any], validation: Dict[str, Any]):
        """Save test output with Metric Advisor-specific fields."""
        test_output_dir = self.current_test_output_dir or self.get_test_output_dir(test_name)
        
        # Save main output file
        output_file = test_output_dir / "output.json"
        
        # Sanitize result for JSON
        sanitized_result = self.sanitize_for_json(result)
        
        output_data = {
            "test_name": test_name,
            "timestamp": datetime.utcnow().isoformat(),
            "validation": validation,
            "result": sanitized_result
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        # Save separate files for key outputs
        outputs_dir = test_output_dir / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        
        # Save state snapshot
        if "result" in output_data and isinstance(output_data["result"], dict):
            state_snapshot = {
                "csod_intent": output_data["result"].get("csod_intent"),
                "csod_metric_recommendations_count": len(output_data["result"].get("csod_metric_recommendations", [])),
                "csod_causal_nodes_count": len(output_data["result"].get("csod_causal_nodes", [])),
                "csod_causal_edges_count": len(output_data["result"].get("csod_causal_edges", [])),
                "has_metric_kpi_relations": bool(output_data["result"].get("csod_metric_kpi_relations", {})),
                "has_reasoning_plan": bool(output_data["result"].get("csod_reasoning_plan", {})),
                "has_advisor_output": output_data["result"].get("csod_advisor_output") is not None,
                "has_assembled_output": output_data["result"].get("csod_assembled_output") is not None,
            }
            with open(outputs_dir / "state_snapshot.json", 'w') as f:
                json.dump(state_snapshot, f, indent=2, default=str)
            
            # Save Metric Advisor-specific outputs
            if output_data["result"].get("csod_metric_recommendations"):
                with open(outputs_dir / "metric_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["csod_metric_recommendations"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_causal_nodes"):
                with open(outputs_dir / "causal_nodes.json", 'w') as f:
                    json.dump(output_data["result"]["csod_causal_nodes"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_causal_edges"):
                with open(outputs_dir / "causal_edges.json", 'w') as f:
                    json.dump(output_data["result"]["csod_causal_edges"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_metric_kpi_relations"):
                with open(outputs_dir / "metric_kpi_relations.json", 'w') as f:
                    json.dump(output_data["result"]["csod_metric_kpi_relations"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_reasoning_plan"):
                with open(outputs_dir / "reasoning_plan.json", 'w') as f:
                    json.dump(output_data["result"]["csod_reasoning_plan"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_advisor_output"):
                with open(outputs_dir / "advisor_output.json", 'w') as f:
                    json.dump(output_data["result"]["csod_advisor_output"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_assembled_output"):
                with open(outputs_dir / "assembled_output.json", 'w') as f:
                    json.dump(output_data["result"]["csod_assembled_output"], f, indent=2, default=str)
        
        logger.info(f"  ✓ Saved test output to: {test_output_dir}")
    
    def sanitize_for_json(self, obj: Any, max_length: int = 10000) -> Any:
        """Sanitize object for JSON serialization, truncating large strings."""
        if isinstance(obj, dict):
            return {k: self.sanitize_for_json(v, max_length) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.sanitize_for_json(item, max_length) for item in obj[:100]]  # Limit list size
        elif isinstance(obj, str) and len(obj) > max_length:
            return obj[:max_length] + f"... (truncated, original length: {len(obj)})"
        else:
            return obj
    
    def generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test summary."""
        total = len(results)
        passed = sum(1 for r in results.values() if r.get("success", False))
        failed = total - passed
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0
        }
    
    def print_summary(self, results: Dict[str, Any]):
        """Print test summary."""
        summary = self.generate_summary(results)
        
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tests: {summary['total']}")
        logger.info(f"✅ Passed: {summary['passed']}")
        logger.info(f"❌ Failed: {summary['failed']}")
        logger.info(f"Pass rate: {summary['pass_rate']:.1f}%")
        logger.info("")
        
        logger.info("Test Results:")
        for test_name, result in results.items():
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            logger.info(f"  {status} {test_name}")
            if not result.get("success", False) and "error" in result:
                logger.info(f"    Error: {result['error']}")
        logger.info("")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all Metric Advisor workflow tests and generate summary."""
        logger.info("=" * 80)
        logger.info("METRIC ADVISOR WORKFLOW TEST SUITE")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        # Run Metric Advisor use cases
        tests = [
            ("Use Case 1: Basic Metric Advisor", self.test_use_case_1_basic_metric_advisor),
            ("Use Case 2: Causal Graph Advisor", self.test_use_case_2_causal_graph_advisor),
            ("Use Case 3: KPI Relations Mapping", self.test_use_case_3_kpi_relations),
            ("Use Case 4: Reasoning Plan Generation", self.test_use_case_4_reasoning_plan),
            ("Use Case 5: Lexy Pre-Resolved Intent", self.test_use_case_5_lexy_pre_resolved_advisor),
            ("Use Case 6: Planner Workflow Integration", self.test_use_case_6_planner_workflow_integration),
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = result
                self.results.append(result)
            except Exception as e:
                logger.error(f"Test '{test_name}' failed with exception: {e}", exc_info=True)
                results[test_name] = {
                    "test_name": test_name.lower().replace(" ", "_"),
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            logger.info("")
        
        # Generate summary
        self.print_summary(results)
        
        # Save overall summary
        summary_file = self.output_base_dir / f"metric_advisor_test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump({
                "summary": self.generate_summary(results),
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }, f, indent=2, default=str)
        
        logger.info(f"Summary saved to: {summary_file}")
        
        return {
            "summary": self.generate_summary(results),
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test CSOD Metric Advisor workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--test',
        choices=[
            'all',
            'use_case_1',
            'use_case_2',
            'use_case_3',
            'use_case_4',
            'use_case_5',
            'use_case_6',
        ],
        default='all',
        help='Which test to run'
    )
    
    parser.add_argument(
        '--no-planner',
        action='store_true',
        help='Disable planner workflow (use direct workflow path)'
    )
    
    parser.add_argument(
        '--skip-slow',
        action='store_true',
        help='Skip slow operations'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("app").setLevel(logging.DEBUG)
        logging.getLogger("app.agents").setLevel(logging.DEBUG)
        logging.getLogger("app.agents.csod").setLevel(logging.DEBUG)
    
    tester = MetricAdvisorWorkflowTester()
    tester.skip_slow = args.skip_slow
    tester.use_planner_workflow = not args.no_planner
    results = None
    
    if args.test == 'all':
        results = tester.run_all_tests()
    elif args.test == 'use_case_1':
        tester.setup()
        result = tester.test_use_case_1_basic_metric_advisor()
        tester.print_summary({"Use Case 1: Basic Metric Advisor": result})
        results = {"results": result}
    elif args.test == 'use_case_2':
        tester.setup()
        result = tester.test_use_case_2_causal_graph_advisor()
        tester.print_summary({"Use Case 2: Causal Graph Advisor": result})
        results = {"results": result}
    elif args.test == 'use_case_3':
        tester.setup()
        result = tester.test_use_case_3_kpi_relations()
        tester.print_summary({"Use Case 3: KPI Relations Mapping": result})
        results = {"results": result}
    elif args.test == 'use_case_4':
        tester.setup()
        result = tester.test_use_case_4_reasoning_plan()
        tester.print_summary({"Use Case 4: Reasoning Plan Generation": result})
        results = {"results": result}
    elif args.test == 'use_case_5':
        tester.setup()
        result = tester.test_use_case_5_lexy_pre_resolved_advisor()
        tester.print_summary({"Use Case 5: Lexy Pre-Resolved Intent": result})
        results = {"results": result}
    elif args.test == 'use_case_6':
        tester.setup()
        result = tester.test_use_case_6_planner_workflow_integration()
        tester.print_summary({"Use Case 6: Planner Workflow Integration": result})
        results = {"results": result}
    
    if results:
        logger.info(f"\nAll outputs saved to: {OUTPUT_BASE_DIR}")


if __name__ == '__main__':
    main()
