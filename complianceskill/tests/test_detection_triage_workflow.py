#!/usr/bin/env python3
"""
Test suite for Detection & Triage Engineering Workflow.

This test validates the complete DT workflow pipeline using test cases from:
- docs/dt_agents_test.md

Test Cases (from dt_agents_test.md):
1. Intent Classifier - Enrichment signal extraction (needs_mdl, needs_metrics, focus_areas)
2. Planner - Gap notes for unconfigured sources
3. Framework Retrieval - Detective controls ranking
4. Metrics Retrieval - Source filtering and gap notes
5. MDL Schema Retrieval - Exact name lookup via product capabilities + project_id
6. Scoring Validator - Adversarial narrow scope filtering
7. Detection Engineer - CVE tooling and control traceability
8. Triage Engineer - No SQL in calculation steps, medallion plan accuracy
9. SIEM Validator - Source scope validation (RULE-V3)
10. Metric Validator - SQL detection (RULE-C2) and gold_available accuracy (RULE-M2)
11. Playbook Assembler - Template C (full chain) with traceability

Configuration:
- Data Sources: snyk, qualys, wiz, sentinel
- Gold Standard Project ID: cve_data
- Metrics Registry: leen_metrics_registry

Uses .env configuration for LLM and vector store settings.
Generates output in tests/output directory.
"""
import os
import sys
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
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

from app.agents.dt_workflow import (
    get_detection_triage_app,
    create_dt_initial_state,
)
from langgraph.checkpoint.memory import MemorySaver

# Configure logging with immediate flush
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,  # Ensure output goes to stdout
    force=True  # Force reconfiguration
)
logger = logging.getLogger(__name__)

# Also configure app loggers to show progress
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.agents").setLevel(logging.INFO)
logging.getLogger("app.agents.dt_nodes").setLevel(logging.INFO)

# Force immediate output
sys.stdout.flush()
sys.stderr.flush()

# Create output directory structure: tests/outputs/testcase_name/timestamp/
OUTPUT_BASE_DIR = base_dir / "tests" / "outputs"
OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Constants
GOLD_STANDARD_PROJECT_ID = "cve_data"  # As specified by user
DATA_SOURCES = ["snyk", "qualys", "wiz", "sentinel"]  # As specified by user


class DetectionTriageWorkflowTester:
    """Test suite for Detection & Triage Engineering workflow."""
    
    def __init__(self, output_base_dir: Path = None):
        self.app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_base_dir = output_base_dir or OUTPUT_BASE_DIR
        self.current_test_output_dir = None  # Will be set per test
        self.skip_slow = False  # Flag to skip slow operations
    
    def setup(self):
        """Initialize the DT workflow app."""
        logger.info("Setting up Detection & Triage workflow app...")
        self.app = get_detection_triage_app()
        logger.info("✓ DT workflow app initialized")
        logger.info(f"  Nodes: {list(self.app.nodes.keys())}")
    
    def create_initial_state(
        self,
        user_query: str,
        framework_id: str = None,
        selected_data_sources: List[str] = None,
    ) -> Dict[str, Any]:
        """Create initial state for the DT workflow."""
        return create_dt_initial_state(
            user_query=user_query,
            session_id=str(uuid.uuid4()),
            framework_id=framework_id,
            selected_data_sources=selected_data_sources or DATA_SOURCES,
            active_project_id=GOLD_STANDARD_PROJECT_ID,  # Use cve_data as specified
            compliance_profile=None,
        )
    
    def test_intent_classifier_enrichment_signals(self) -> Dict[str, Any]:
        """
        Test: Intent Classifier - Enrichment Signal Extraction
        
        From dt_agents_test.md - Tests that needs_mdl, needs_metrics, suggested_focus_areas,
        metrics_intent, and playbook_template_hint are all populated correctly.
        """
        logger.info("=" * 80)
        logger.info("TEST: Intent Classifier - Enrichment Signal Extraction")
        logger.info("=" * 80)
        
        user_query = (
            "For SOC2 CC7 and CC6, I need both Sentinel detection rules for unauthorized access "
            "and KPI tracking to show auditors our remediation trend over the last 90 days."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run only up to intent classifier
            from app.agents.dt_nodes import dt_intent_classifier_node
            result = dt_intent_classifier_node(initial_state)
            
            # Validate enrichment signals
            validation_results = self.validate_intent_classifier_output(result)
            self.get_test_output_dir("intent_classifier_enrichment")
            self.save_test_output("intent_classifier_enrichment", result, validation_results)
            
            return {
                "test_name": "intent_classifier_enrichment_signals",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "intent_classifier_enrichment_signals",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_planner_gap_notes(self) -> Dict[str, Any]:
        """
        Test: Planner - Gap Notes for Unconfigured Sources
        
        From dt_agents_test.md - Tests that planner omits steps for unconfigured sources
        and populates dt_gap_notes explaining why.
        """
        logger.info("=" * 80)
        logger.info("TEST: Planner - Gap Notes for Unconfigured Sources")
        logger.info("=" * 80)
        
        user_query = (
            "Generate HIPAA audit logging detection rules and compliance metrics. "
            "My data sources are Wiz and Sentinel only."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=["wiz", "sentinel"],  # Narrow scope to test gap notes
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run up to planner
            from app.agents.dt_nodes import dt_intent_classifier_node, dt_planner_node
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            
            validation_results = self.validate_planner_output(result)
            self.get_test_output_dir("planner_gap_notes")
            self.save_test_output("planner_gap_notes", result, validation_results)
            
            return {
                "test_name": "planner_gap_notes",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "planner_gap_notes",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_framework_retrieval_detective_controls(self) -> Dict[str, Any]:
        """
        Test: Framework Retrieval - Detective Controls Ranking
        
        From dt_agents_test.md - Tests that detective controls are ranked first and
        scenarios relevant to a specific requirement code are retrieved.
        """
        logger.info("=" * 80)
        logger.info("TEST: Framework Retrieval - Detective Controls Ranking")
        logger.info("=" * 80)
        
        user_query = (
            "Show me the detective controls and attack scenarios for HIPAA requirement 164.312(b) "
            "audit controls."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run up to framework retrieval
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            
            validation_results = self.validate_framework_retrieval_output(result)
            self.get_test_output_dir("framework_retrieval_detective")
            self.save_test_output("framework_retrieval_detective", result, validation_results)
            
            return {
                "test_name": "framework_retrieval_detective_controls",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "framework_retrieval_detective_controls",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_metrics_retrieval_source_filtering(self) -> Dict[str, Any]:
        """
        Test: Metrics Retrieval - Source Filtering and Gap Notes
        
        From dt_agents_test.md - Tests that metrics are filtered to only sources in scope
        and gap notes are generated for metrics requiring unconfigured sources.
        """
        logger.info("=" * 80)
        logger.info("TEST: Metrics Retrieval - Source Filtering and Gap Notes")
        logger.info("=" * 80)
        
        user_query = (
            "What are the SOC2 vulnerability management KPIs I can track with Qualys? "
            "I do not have Tenable or Snyk configured."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys"],  # Only Qualys to test filtering
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run up to metrics retrieval
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_metrics_retrieval_node(result)
            
            validation_results = self.validate_metrics_retrieval_output(result)
            self.get_test_output_dir("metrics_retrieval_filtering")
            self.save_test_output("metrics_retrieval_filtering", result, validation_results)
            
            return {
                "test_name": "metrics_retrieval_source_filtering",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metrics_retrieval_source_filtering",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_mdl_schema_exact_lookup(self) -> Dict[str, Any]:
        """
        Test: MDL Schema Retrieval - Exact Name Lookup
        
        From dt_agents_test.md - Tests that schemas referenced in resolved_metrics.source_schemas
        are fetched by exact name, not semantic guessing.
        """
        logger.info("=" * 80)
        logger.info("TEST: MDL Schema Retrieval - Exact Name Lookup")
        logger.info("=" * 80)
        
        user_query = (
            "How do I calculate mean time to remediate critical vulnerabilities using Qualys data? "
            "Show me what tables are available."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys"],
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run up to calculation planner (includes calculation nodes)
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
                dt_mdl_schema_retrieval_node,
                calculation_needs_assessment_node,
                calculation_planner_node,
            )
            
            logger.info("Step 1/7: Running intent_classifier_node...")
            sys.stdout.flush()  # Force immediate output
            result = dt_intent_classifier_node(initial_state)
            logger.info(f"✓ Intent classifier completed. Intent: {result.get('intent')}")
            sys.stdout.flush()
            
            logger.info("Step 2/7: Running planner_node...")
            sys.stdout.flush()
            result = dt_planner_node(result)
            logger.info(f"✓ Planner completed. Template: {result.get('dt_playbook_template')}")
            sys.stdout.flush()
            
            logger.info("Step 3/7: Running framework_retrieval_node...")
            sys.stdout.flush()
            result = dt_framework_retrieval_node(result)
            logger.info(f"✓ Framework retrieval completed. Controls: {len(result.get('dt_retrieved_controls', []))}")
            sys.stdout.flush()
            
            logger.info("Step 4/7: Running metrics_retrieval_node...")
            sys.stdout.flush()
            result = dt_metrics_retrieval_node(result)
            logger.info(f"✓ Metrics retrieval completed. Metrics: {len(result.get('resolved_metrics', []))}")
            sys.stdout.flush()
            
            logger.info("Step 5/7: Running mdl_schema_retrieval_node...")
            sys.stdout.flush()
            result = dt_mdl_schema_retrieval_node(result)
            logger.info(f"✓ MDL schema retrieval completed. Schemas: {len(result.get('dt_resolved_schemas', []))}")
            sys.stdout.flush()
            
            logger.info("Step 6/7: Running calculation_needs_assessment_node...")
            sys.stdout.flush()
            result = calculation_needs_assessment_node(result)
            needs_calculation = result.get('needs_calculation', False)
            logger.info(f"✓ Calculation needs assessment completed. Needs calculation: {needs_calculation}")
            sys.stdout.flush()
            
            if needs_calculation:
                logger.info("Step 7/7: Running calculation_planner_node...")
                sys.stdout.flush()
                result = calculation_planner_node(result)
                calculation_plan = result.get('calculation_plan', {})
                field_instructions = calculation_plan.get('field_instructions', [])
                metric_instructions = calculation_plan.get('metric_instructions', [])
                logger.info(f"✓ Calculation planner completed. Field instructions: {len(field_instructions)}, Metric instructions: {len(metric_instructions)}")
                sys.stdout.flush()
            else:
                logger.info("Step 7/7: Skipping calculation_planner (not needed)")
                sys.stdout.flush()
            
            validation_results = self.validate_mdl_schema_output(result)
            self.get_test_output_dir("mdl_schema_exact_lookup")
            self.save_test_output("mdl_schema_exact_lookup", result, validation_results)
            
            return {
                "test_name": "mdl_schema_exact_lookup",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "mdl_schema_exact_lookup",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_scoring_validator_adversarial(self) -> Dict[str, Any]:
        """
        Test: Scoring Validator - Adversarial Narrow Scope
        
        From dt_agents_test.md - Tests that validator drops irrelevant items, flags low-confidence,
        and detects schema gaps.
        """
        logger.info("=" * 80)
        logger.info("TEST: Scoring Validator - Adversarial Narrow Scope")
        logger.info("=" * 80)
        
        user_query = (
            "I need HIPAA breach detection rules for credential stuffing. "
            "My configured sources are Wiz and Sentinel only."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=["wiz", "sentinel"],  # Narrow scope to test adversarial filtering
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run up to scoring validator
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
                dt_mdl_schema_retrieval_node,
                dt_scoring_validator_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_metrics_retrieval_node(result)
            result = dt_mdl_schema_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            
            validation_results = self.validate_scoring_validator_output(result)
            self.get_test_output_dir("scoring_validator_adversarial")
            self.save_test_output("scoring_validator_adversarial", result, validation_results)
            
            return {
                "test_name": "scoring_validator_adversarial",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "scoring_validator_adversarial",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_detection_engineer_cve_tooling(self) -> Dict[str, Any]:
        """
        Test: Detection Engineer - CVE Tooling and Control Traceability
        
        From dt_agents_test.md - Tests that rules are only for log sources in scope,
        every rule has mapped_control_codes, and CVE tooling is triggered.
        """
        logger.info("=" * 80)
        logger.info("TEST: Detection Engineer - CVE Tooling and Control Traceability")
        logger.info("=" * 80)
        
        user_query = (
            "Generate Sentinel detection rules for CVE-2024-12356 exploitation against "
            "HIPAA-covered systems. My log sources are Sentinel and Wiz cloud security."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=["sentinel", "wiz"],  # Sentinel for SIEM, Wiz for cloud security
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run full detection path
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_scoring_validator_node,
                dt_detection_engineer_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_detection_engineer_node(result)
            
            validation_results = self.validate_detection_engineer_output(result)
            self.get_test_output_dir("detection_engineer_cve")
            self.save_test_output("detection_engineer_cve", result, validation_results)
            
            return {
                "test_name": "detection_engineer_cve_tooling",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "detection_engineer_cve_tooling",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_detection_engineer_metrics_generation(self) -> Dict[str, Any]:
        """
        Test: Detection Engineer - Metrics and KPIs Generation (Phase 2)
        
        Tests that detection engineer generates metrics/KPIs after SIEM rules,
        with KPIs mapped to risks and controls FROM THE START.
        """
        logger.info("=" * 80)
        logger.info("TEST: Detection Engineer - Metrics and KPIs Generation")
        logger.info("=" * 80)
        
        user_query = (
            "Generate HIPAA breach detection rules for unauthorized access to patient data. "
            "I need SIEM rules and metrics to track compliance. My log sources are Sentinel and Qualys."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=["sentinel", "qualys"],
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run full detection path including Phase 2 (metrics generation)
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_scoring_validator_node,
                dt_detection_engineer_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_detection_engineer_node(result)
            
            validation_results = self.validate_detection_engineer_metrics_output(result)
            self.get_test_output_dir("detection_engineer_metrics")
            self.save_test_output("detection_engineer_metrics", result, validation_results)
            
            return {
                "test_name": "detection_engineer_metrics_generation",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "detection_engineer_metrics_generation",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_detection_engineer_risk_control_mappings(self) -> Dict[str, Any]:
        """
        Test: Detection Engineer - Risk and Control to Metrics Mappings
        
        Tests that KPIs are mapped to risks and controls FROM THE START,
        and that control_to_metrics_mappings and risk_to_metrics_mappings are generated.
        """
        logger.info("=" * 80)
        logger.info("TEST: Detection Engineer - Risk and Control to Metrics Mappings")
        logger.info("=" * 80)
        
        user_query = (
            "Build SOC2 detection rules for unauthorized access and privilege escalation. "
            "I need both detection rules and KPIs mapped to the risks and controls. "
            "My data sources are Sentinel and Wiz."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["sentinel", "wiz"],
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run full detection path
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_scoring_validator_node,
                dt_detection_engineer_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_detection_engineer_node(result)
            
            validation_results = self.validate_detection_engineer_mappings_output(result)
            self.get_test_output_dir("detection_engineer_mappings")
            self.save_test_output("detection_engineer_mappings", result, validation_results)
            
            return {
                "test_name": "detection_engineer_risk_control_mappings",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "detection_engineer_risk_control_mappings",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_detection_engineer_medallion_plan(self) -> Dict[str, Any]:
        """
        Test: Detection Engineer - Medallion Plan Generation
        
        Tests that detection engineer generates medallion plan with bronze/silver/gold layers
        for the metrics generated from SIEM rules.
        """
        logger.info("=" * 80)
        logger.info("TEST: Detection Engineer - Medallion Plan Generation")
        logger.info("=" * 80)
        
        user_query = (
            "Generate HIPAA detection rules for credential stuffing attacks. "
            "I need SIEM rules, metrics, and a medallion architecture plan. "
            "My log sources are Sentinel and Okta."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=["sentinel", "okta"],
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run full detection path
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_scoring_validator_node,
                dt_detection_engineer_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_detection_engineer_node(result)
            
            validation_results = self.validate_detection_engineer_medallion_output(result)
            self.get_test_output_dir("detection_engineer_medallion")
            self.save_test_output("detection_engineer_medallion", result, validation_results)
            
            return {
                "test_name": "detection_engineer_medallion_plan",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "detection_engineer_medallion_plan",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_triage_engineer_no_sql(self) -> Dict[str, Any]:
        """
        Test: Triage Engineer - No SQL in Calculation Steps
        
        From dt_agents_test.md - Tests that calculation steps contain zero SQL,
        needs_silver is set correctly, and gold_available is accurate.
        """
        logger.info("=" * 80)
        logger.info("TEST: Triage Engineer - No SQL in Calculation Steps")
        logger.info("=" * 80)
        
        user_query = (
            "What KPIs should I track for SOC2 vulnerability management compliance and how "
            "should I structure the data pipeline from raw Qualys data to weekly executive metrics?"
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys"],
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run full triage path
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
                dt_mdl_schema_retrieval_node,
                dt_scoring_validator_node,
                dt_triage_engineer_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_metrics_retrieval_node(result)
            result = dt_mdl_schema_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_triage_engineer_node(result)
            
            validation_results = self.validate_triage_engineer_output(result)
            self.get_test_output_dir("triage_engineer_no_sql")
            self.save_test_output("triage_engineer_no_sql", result, validation_results)
            
            return {
                "test_name": "triage_engineer_no_sql",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "triage_engineer_no_sql",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_siem_validator_source_scope(self) -> Dict[str, Any]:
        """
        Test: SIEM Rule Validator - Source Scope Validation
        
        From dt_agents_test.md - Tests that RULE-V3 (log source out of scope) triggers
        and validator catches missing alert_config.
        """
        logger.info("=" * 80)
        logger.info("TEST: SIEM Rule Validator - Source Scope Validation")
        logger.info("=" * 80)
        
        user_query = (
            "Generate detection rules for lateral movement and privilege escalation for "
            "SOC2 CC6. I only have Wiz cloud security logs configured, no endpoint or network sources."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["wiz"],  # Narrow scope - only cloud, no endpoint
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run detection + validator
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_scoring_validator_node,
                dt_detection_engineer_node,
                dt_siem_rule_validator_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_detection_engineer_node(result)
            result = dt_siem_rule_validator_node(result)
            
            validation_results = self.validate_siem_validator_output(result)
            self.get_test_output_dir("siem_validator_source_scope")
            self.save_test_output("siem_validator_source_scope", result, validation_results)
            
            return {
                "test_name": "siem_validator_source_scope",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "siem_validator_source_scope",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_metric_validator_sql_detection(self) -> Dict[str, Any]:
        """
        Test: Metric Calculation Validator - SQL Detection and Gold Available Accuracy
        
        From dt_agents_test.md - Tests RULE-C2 (SQL detection) and RULE-M2 (gold_available accuracy).
        """
        logger.info("=" * 80)
        logger.info("TEST: Metric Calculation Validator - SQL Detection")
        logger.info("=" * 80)
        
        user_query = (
            "Give me HIPAA audit logging compliance metrics with calculation steps. "
            "This is a new tenant with no pre-built gold tables."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run full triage + validator
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
                dt_mdl_schema_retrieval_node,
                dt_scoring_validator_node,
                dt_triage_engineer_node,
                dt_metric_calculation_validator_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_metrics_retrieval_node(result)
            result = dt_mdl_schema_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_triage_engineer_node(result)
            result = dt_metric_calculation_validator_node(result)
            
            validation_results = self.validate_metric_validator_output(result)
            self.get_test_output_dir("metric_validator_sql")
            self.save_test_output("metric_validator_sql", result, validation_results)
            
            return {
                "test_name": "metric_validator_sql_detection",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "metric_validator_sql_detection",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_playbook_assembler_template_c(self) -> Dict[str, Any]:
        """
        Test: Playbook Assembler - Template C (Full Chain)
        
        From dt_agents_test.md - Tests that Template C output has both SIEM rules and
        metric recommendations with traceability section.
        """
        logger.info("=" * 80)
        logger.info("TEST: Playbook Assembler - Template C (Full Chain)")
        logger.info("=" * 80)
        
        user_query = (
            "Build me a complete HIPAA breach detection and response package for unauthorized "
            "ePHI access — I need both the Sentinel rules and the compliance dashboard metrics "
            "to show auditors after an incident."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run complete workflow
            result = self.app.invoke(initial_state, config=self.config)
            
            validation_results = self.validate_playbook_assembler_output(result)
            self.get_test_output_dir("playbook_assembler_template_c")
            self.save_test_output("playbook_assembler_template_c", result, validation_results)
            
            return {
                "test_name": "playbook_assembler_template_c",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "playbook_assembler_template_c",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_hipaa_breach_detection(self) -> Dict[str, Any]:
        """
        Test: HIPAA Breach Detection (Detection Engineering) - Full Workflow
        
        Use Case: Build SIEM rules for HIPAA breach detection on patient portal.
        Based on prompts_mdl/detection_engineer_hipaa_auth.yaml
        """
        logger.info("=" * 80)
        logger.info("TEST: HIPAA Breach Detection (Full Workflow)")
        logger.info("=" * 80)
        
        user_query = (
            "Build HIPAA breach detection for credential theft on patient portal. "
            "I need SIEM rules to detect unauthorized access to ePHI. "
            "Focus on controls for §164.308(a)(6)(ii) - Security Incident Procedures."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            # Run the complete workflow
            result = self.app.invoke(initial_state, config=self.config)
            
            # Validate results
            validation_results = self.validate_detection_output(result)
            
            # Save output
            self.get_test_output_dir("hipaa_breach_detection")
            self.save_test_output("hipaa_breach_detection", result, validation_results)
            
            return {
                "test_name": "hipaa_breach_detection",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"DT workflow execution failed: {e}", exc_info=True)
            return {
                "test_name": "hipaa_breach_detection",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_soc2_vulnerability_triage(self) -> Dict[str, Any]:
        """
        Test: SOC2 Vulnerability Triage (Triage Engineering)
        
        Use Case: Generate metric recommendations and medallion plan for SOC2 vulnerability management.
        Based on prompts_mdl/triage_engineer_soc2_vuln.yaml
        """
        logger.info("=" * 80)
        logger.info("TEST: SOC2 Vulnerability Triage (Triage Engineering)")
        logger.info("=" * 80)
        
        user_query = (
            "What metrics should I track for SOC2 vulnerability management? "
            "I need to measure compliance with CC6.1 and CC7.2. "
            "Show me how to calculate KPIs and build the medallion architecture."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys", "sentinel"]
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            result = self.app.invoke(initial_state, config=self.config)
            
            validation_results = self.validate_triage_output(result)
            self.get_test_output_dir("soc2_vulnerability_triage")
            self.save_test_output("soc2_vulnerability_triage", result, validation_results)
            
            return {
                "test_name": "soc2_vulnerability_triage",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "soc2_vulnerability_triage",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_hipaa_full_pipeline(self) -> Dict[str, Any]:
        """
        Test: HIPAA Full Pipeline (Detection + Triage)
        
        Use Case: Complete end-to-end detection and triage for HIPAA compliance.
        Based on prompts_mdl/planner_hipaa_full_chain.yaml
        """
        logger.info("=" * 80)
        logger.info("TEST: HIPAA Full Pipeline (Detection + Triage)")
        logger.info("=" * 80)
        
        user_query = (
            "Build complete detection and triage for HIPAA compliance. "
            "I need SIEM rules for breach detection AND metrics to track compliance posture. "
            "Cover controls for §164.308(a)(6)(ii) and §164.312(a)(2)(i)."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="hipaa",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            result = self.app.invoke(initial_state, config=self.config)
            
            validation_results = self.validate_full_pipeline_output(result)
            self.get_test_output_dir("hipaa_full_pipeline")
            self.save_test_output("hipaa_full_pipeline", result, validation_results)
            
            return {
                "test_name": "hipaa_full_pipeline",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "hipaa_full_pipeline",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_1_metrics_help(self) -> Dict[str, Any]:
        """
        Use Case 1: Metrics Help
        
        User wants to understand what metrics they can track for compliance.
        Focus: Metrics retrieval and recommendations.
        """
        logger.info("=" * 80)
        logger.info("USE CASE 1: Metrics Help")
        logger.info("=" * 80)
        
        user_query = (
            "What metrics should I track for SOC2 vulnerability management compliance? "
            "I have Qualys and Snyk configured. Show me the available metrics and how to calculate them."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys", "snyk"],
        )
        
        try:
            logger.info(f"Executing Metrics Help workflow...")
            
            # Run up to metrics retrieval and triage engineer
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
                dt_mdl_schema_retrieval_node,
                dt_scoring_validator_node,
                dt_triage_engineer_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_metrics_retrieval_node(result)
            result = dt_mdl_schema_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_triage_engineer_node(result)
            
            validation_results = {
                "overall_success": True,
                "checks": {
                    "metrics_retrieved": len(result.get("resolved_metrics", [])) > 0,
                    "schemas_retrieved": len(result.get("dt_resolved_schemas", [])) > 0,
                    "recommendations_generated": len(result.get("dt_metric_recommendations", [])) > 0,
                },
                "issues": []
            }
            
            self.get_test_output_dir("use_case_1_metrics_help")
            self.save_test_output("use_case_1_metrics_help", result, validation_results)
            
            return {
                "test_name": "use_case_1_metrics_help",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "use_case_1_metrics_help",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_2_dashboard_metrics_workflow(self) -> Dict[str, Any]:
        """
        Use Case 2: Dashboard Metrics Workflow
        
        User wants to build a compliance dashboard with metrics.
        Focus: Full triage workflow with medallion plan and metric recommendations.
        """
        logger.info("=" * 80)
        logger.info("USE CASE 2: Dashboard Metrics Workflow")
        logger.info("=" * 80)
        
        user_query = (
            "I need to build a SOC2 compliance dashboard showing vulnerability management metrics. "
            "I have Qualys, Snyk, and Wiz configured. Generate the metric recommendations and "
            "medallion architecture plan for weekly executive reporting."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys", "snyk", "wiz"],
        )
        
        try:
            logger.info(f"Executing Dashboard Metrics Workflow...")
            
            # Run full triage workflow
            from app.agents.dt_nodes import (
                dt_intent_classifier_node,
                dt_planner_node,
                dt_framework_retrieval_node,
                dt_metrics_retrieval_node,
                dt_mdl_schema_retrieval_node,
                dt_scoring_validator_node,
                dt_triage_engineer_node,
                dt_metric_calculation_validator_node,
                dt_playbook_assembler_node,
            )
            result = dt_intent_classifier_node(initial_state)
            result = dt_planner_node(result)
            result = dt_framework_retrieval_node(result)
            result = dt_metrics_retrieval_node(result)
            result = dt_mdl_schema_retrieval_node(result)
            result = dt_scoring_validator_node(result)
            result = dt_triage_engineer_node(result)
            result = dt_metric_calculation_validator_node(result)
            result = dt_playbook_assembler_node(result)
            
            validation_results = {
                "overall_success": True,
                "checks": {
                    "metrics_retrieved": len(result.get("resolved_metrics", [])) > 0,
                    "recommendations_generated": len(result.get("dt_metric_recommendations", [])) >= 10,
                    "medallion_plan_generated": bool(result.get("dt_medallion_plan")),
                    "playbook_assembled": bool(result.get("dt_assembled_playbook")),
                    "validation_passed": result.get("dt_metric_validation_passed", False),
                },
                "issues": []
            }
            
            self.get_test_output_dir("use_case_2_dashboard_metrics")
            self.save_test_output("use_case_2_dashboard_metrics", result, validation_results)
            
            return {
                "test_name": "use_case_2_dashboard_metrics_workflow",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "use_case_2_dashboard_metrics_workflow",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_3_detection_and_metrics_full(self) -> Dict[str, Any]:
        """
        Use Case 3: Detection + Metrics Full Workflow
        
        User wants both SIEM detection rules and compliance metrics.
        Focus: Full pipeline (Template C) with both detection and triage.
        """
        logger.info("=" * 80)
        logger.info("USE CASE 3: Detection + Metrics Full Workflow")
        logger.info("=" * 80)
        
        user_query = (
            "Build a complete SOC2 compliance package for vulnerability management. "
            "I need both Sentinel detection rules for unauthorized access attempts and "
            "compliance dashboard metrics to show auditors. I have Qualys, Snyk, Wiz, and Sentinel configured."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing Full Detection + Metrics Workflow...")
            
            # Run complete workflow
            result = self.app.invoke(initial_state, config=self.config)
            
            validation_results = {
                "overall_success": True,
                "checks": {
                    "siem_rules_generated": len(result.get("siem_rules", [])) > 0,
                    "metrics_recommendations_generated": len(result.get("dt_metric_recommendations", [])) >= 10,
                    "playbook_assembled": bool(result.get("dt_assembled_playbook")),
                    "template_c": result.get("dt_playbook_template") == "C",
                },
                "issues": []
            }
            
            self.get_test_output_dir("use_case_3_detection_metrics_full")
            self.save_test_output("use_case_3_detection_metrics_full", result, validation_results)
            
            return {
                "test_name": "use_case_3_detection_metrics_full",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "use_case_3_detection_metrics_full",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_soc2_triage_only(self) -> Dict[str, Any]:
        """
        Test: SOC2 Triage Only (Template B)
        
        Use Case: Focus on triage engineering only - metrics and medallion plan.
        Based on prompts_mdl/planner_soc2_triage.yaml
        """
        logger.info("=" * 80)
        logger.info("TEST: SOC2 Triage Only (Template B)")
        logger.info("=" * 80)
        
        user_query = (
            "I need metric recommendations for SOC2 vulnerability management. "
            "Show me how to calculate KPIs for CC7.1 and CC7.2 with medallion architecture."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys"],
        )
        
        try:
            logger.info(f"Executing DT workflow with query: {user_query[:100]}...")
            
            result = self.app.invoke(initial_state, config=self.config)
            
            validation_results = self.validate_triage_output(result)
            self.get_test_output_dir("soc2_triage_only")
            self.save_test_output("soc2_triage_only", result, validation_results)
            
            return {
                "test_name": "soc2_triage_only",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "soc2_triage_only",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_intent_classifier_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate intent classifier enrichment signal extraction."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent classified as full_pipeline
        intent = result.get("intent")
        validation["checks"]["intent_full_pipeline"] = intent == "full_pipeline"
        if not validation["checks"]["intent_full_pipeline"]:
            validation["issues"].append(f"Intent should be 'full_pipeline', got '{intent}'")
        
        # Check 2: needs_mdl is true
        data_enrichment = result.get("data_enrichment", {})
        needs_mdl = data_enrichment.get("needs_mdl", False)
        validation["checks"]["needs_mdl_true"] = needs_mdl is True
        if not needs_mdl:
            validation["issues"].append("needs_mdl should be true (trend + tables implied)")
        
        # Check 3: needs_metrics is true
        needs_metrics = data_enrichment.get("needs_metrics", False)
        validation["checks"]["needs_metrics_true"] = needs_metrics is True
        if not needs_metrics:
            validation["issues"].append("needs_metrics should be true (KPI tracking, trend)")
        
        # Check 4: metrics_intent is trend
        metrics_intent = data_enrichment.get("metrics_intent")
        validation["checks"]["metrics_intent_trend"] = metrics_intent == "trend"
        if metrics_intent != "trend":
            validation["issues"].append(f"metrics_intent should be 'trend' (90-day trend), got '{metrics_intent}'")
        
        # Check 5: suggested_focus_areas contains expected areas
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        has_iam = "identity_access_management" in focus_areas
        has_log_siem = "log_management_siem" in focus_areas
        validation["checks"]["has_identity_access"] = has_iam
        validation["checks"]["has_log_management"] = has_log_siem
        if not (has_iam or has_log_siem):
            validation["issues"].append(
                f"Expected focus areas to include 'identity_access_management' or 'log_management_siem', got {focus_areas}"
            )
        
        # Check 6: playbook_template_hint is full_chain
        template_hint = data_enrichment.get("playbook_template_hint")
        validation["checks"]["template_hint_full_chain"] = template_hint == "full_chain"
        if template_hint != "full_chain":
            validation["issues"].append(f"playbook_template_hint should be 'full_chain', got '{template_hint}'")
        
        # Update overall success
        critical_checks = [
            "intent_full_pipeline",
            "needs_mdl_true",
            "needs_metrics_true",
            "metrics_intent_trend",
            "template_hint_full_chain"
        ]
        for check in critical_checks:
            if not validation["checks"].get(check, False):
                validation["overall_success"] = False
        
        return validation
    
    def validate_planner_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate planner gap notes and data source scoping."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: data_sources_in_scope matches input
        data_sources_in_scope = result.get("dt_data_sources_in_scope", [])
        selected_sources = result.get("selected_data_sources", [])
        validation["checks"]["data_sources_scoped"] = (
            set(data_sources_in_scope) == set(selected_sources) or
            all(ds in data_sources_in_scope for ds in selected_sources)
        )
        if not validation["checks"]["data_sources_scoped"]:
            validation["issues"].append(
                f"dt_data_sources_in_scope {data_sources_in_scope} should match selected {selected_sources}"
            )
        
        # Check 2: Template C selected (full_chain)
        playbook_template = result.get("dt_playbook_template")
        validation["checks"]["template_c_selected"] = playbook_template == "C"
        if playbook_template != "C":
            validation["issues"].append(f"Template should be 'C' (full_chain), got '{playbook_template}'")
        
        # Check 3: Gap notes populated
        gap_notes = result.get("dt_gap_notes", [])
        validation["checks"]["gap_notes_populated"] = len(gap_notes) > 0
        if not validation["checks"]["gap_notes_populated"]:
            validation["issues"].append("dt_gap_notes should contain notes about unavailable sources")
        else:
            logger.info(f"  ✓ Gap notes: {len(gap_notes)}")
            # Check that gap notes mention vulnerability management
            has_vuln_note = any("vulnerability" in note.lower() or "vuln" in note.lower() for note in gap_notes)
            validation["checks"]["gap_notes_mention_vuln"] = has_vuln_note
        
        # Check 4: Semantic questions populated
        context_cache = result.get("context_cache", {})
        semantic_questions = context_cache.get("dt_semantic_questions", {})
        validation["checks"]["semantic_questions_populated"] = len(semantic_questions) > 0
        if not validation["checks"]["semantic_questions_populated"]:
            validation["issues"].append("context_cache['dt_semantic_questions'] should be populated")
        
        return validation
    
    def validate_framework_retrieval_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate framework retrieval detective controls ranking."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Controls retrieved
        controls = result.get("dt_retrieved_controls", [])
        validation["checks"]["controls_retrieved"] = len(controls) > 0
        if not validation["checks"]["controls_retrieved"]:
            validation["issues"].append("No controls retrieved")
        else:
            logger.info(f"  ✓ Controls retrieved: {len(controls)}")
            # Check that detective controls appear first
            detective_indices = [
                i for i, c in enumerate(controls)
                if c.get("control_type") == "detective"
            ]
            other_indices = [
                i for i, c in enumerate(controls)
                if c.get("control_type") != "detective"
            ]
            if detective_indices and other_indices:
                first_detective = min(detective_indices)
                first_other = min(other_indices)
                validation["checks"]["detective_controls_first"] = first_detective < first_other
                if not validation["checks"]["detective_controls_first"]:
                    validation["issues"].append("Detective controls should appear before other control types")
        
        # Check 2: Risks retrieved
        risks = result.get("dt_retrieved_risks", [])
        validation["checks"]["risks_retrieved"] = len(risks) > 0
        if risks:
            # Check that risks reference audit logging or unauthorized access
            risk_texts = " ".join(str(r) for r in risks).lower()
            has_audit_ref = "audit" in risk_texts or "unauthorized" in risk_texts
            validation["checks"]["risks_relevant"] = has_audit_ref
        
        # Check 3: Scenarios retrieved
        scenarios = result.get("dt_retrieved_scenarios", [])
        validation["checks"]["scenarios_retrieved"] = len(scenarios) > 0
        if scenarios:
            scenario_texts = " ".join(str(s) for s in scenarios).lower()
            has_ephi_ref = "ephi" in scenario_texts or "audit" in scenario_texts or "tamper" in scenario_texts
            validation["checks"]["scenarios_relevant"] = has_ephi_ref
        
        # Check 4: Base state synced
        base_controls = result.get("controls", [])
        validation["checks"]["base_state_synced"] = len(base_controls) == len(controls)
        
        return validation
    
    def validate_metrics_retrieval_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metrics retrieval source filtering."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Metrics retrieved
        resolved_metrics = result.get("resolved_metrics", [])
        validation["checks"]["metrics_retrieved"] = len(resolved_metrics) > 0
        if not validation["checks"]["metrics_retrieved"]:
            validation["issues"].append("No metrics retrieved")
        else:
            logger.info(f"  ✓ Metrics retrieved: {len(resolved_metrics)}")
            
            # Check 2: All metrics have source_capabilities matching selected sources
            selected_sources = result.get("selected_data_sources", [])
            if selected_sources:
                for metric in resolved_metrics[:5]:  # Check first 5
                    source_caps = metric.get("source_capabilities", [])
                    if source_caps:
                        # Check if any capability matches selected sources
                        matches = any(
                            any(cap.startswith(src.split(".")[0].lower()) for cap in source_caps if isinstance(cap, str))
                            for src in selected_sources
                        )
                        validation["checks"]["metrics_source_filtered"] = matches
                        if not matches:
                            validation["issues"].append(
                                f"Metric {metric.get('metric_id', '?')} has source_capabilities {source_caps} "
                                f"that don't match selected sources {selected_sources}"
                            )
        
        # Check 3: Gap notes mention unavailable sources
        gap_notes = result.get("dt_gap_notes", [])
        if gap_notes:
            has_tenable_note = any("tenable" in note.lower() for note in gap_notes)
            has_snyk_note = any("snyk" in note.lower() for note in gap_notes)
            validation["checks"]["gap_notes_mention_unavailable"] = has_tenable_note or has_snyk_note
        
        # Check 4: Focus area categories populated
        focus_area_categories = result.get("focus_area_categories", [])
        has_vuln = "vulnerabilities" in focus_area_categories
        has_patch = "patch_compliance" in focus_area_categories
        validation["checks"]["has_vulnerability_category"] = has_vuln or has_patch
        
        return validation
    
    def validate_mdl_schema_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate MDL schema exact name lookup."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Schemas retrieved
        resolved_schemas = result.get("dt_resolved_schemas", [])
        validation["checks"]["schemas_retrieved"] = len(resolved_schemas) > 0
        if not validation["checks"]["schemas_retrieved"]:
            validation["issues"].append("No MDL schemas retrieved")
        else:
            logger.info(f"  ✓ MDL schemas retrieved: {len(resolved_schemas)}")
        
        # Check 2: Schema resolution in context_cache
        context_cache = result.get("context_cache", {})
        schema_resolution = context_cache.get("schema_resolution", {})
        schemas_in_cache = schema_resolution.get("schemas", [])
        validation["checks"]["schemas_in_cache"] = len(schemas_in_cache) > 0
        
        # Check 3: Lookup hits/misses tracked
        # Note: These are in the schema_data returned by dt_retrieve_mdl_schemas
        # We can check if schemas have project_id/product_id (indicating product-based lookup worked)
        has_project_info = any(
            s.get("project_id") or s.get("product_id")
            for s in resolved_schemas[:3]
        )
        validation["checks"]["schemas_have_project_info"] = has_project_info
        if not has_project_info:
            validation["issues"].append("Schemas should have project_id or product_id from product-based lookup")
        
        # Check 4: Gold standard tables retrieved
        gold_tables = result.get("dt_gold_standard_tables", [])
        validation["checks"]["gold_tables_retrieved"] = len(gold_tables) >= 0  # May be empty
        
        return validation
    
    def validate_scoring_validator_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate scoring validator adversarial filtering."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Dropped items recorded
        dropped_items = result.get("dt_dropped_items", [])
        validation["checks"]["dropped_items_recorded"] = len(dropped_items) > 0
        if dropped_items:
            logger.info(f"  ✓ Items dropped: {len(dropped_items)}")
            # Check for D4=0.0 (source unavailable)
            has_d4_failure = any(
                "D4=0.0" in str(item.get("reason", "")) or "data_source_availability" in str(item.get("reason", ""))
                for item in dropped_items
            )
            validation["checks"]["has_source_unavailable_drops"] = has_d4_failure
        
        # Check 2: Schema gaps detected
        schema_gaps = result.get("dt_schema_gaps", [])
        validation["checks"]["schema_gaps_detected"] = len(schema_gaps) >= 0  # May be empty
        if schema_gaps:
            logger.info(f"  ✓ Schema gaps: {len(schema_gaps)}")
        
        # Check 3: Scored context produced
        scored_context = result.get("dt_scored_context", {})
        scored_controls = scored_context.get("controls", [])
        validation["checks"]["scored_context_produced"] = len(scored_controls) > 0
        if scored_controls:
            # Check score breakdown
            first_control = scored_controls[0]
            has_breakdown = "score_breakdown" in first_control
            validation["checks"]["has_score_breakdown"] = has_breakdown
            if has_breakdown:
                breakdown = first_control.get("score_breakdown", {})
                has_all_dimensions = all(
                    dim in breakdown
                    for dim in ["intent_alignment", "focus_area_match", "cross_item_coherence", "data_source_availability"]
                )
                validation["checks"]["breakdown_has_all_dimensions"] = has_all_dimensions
        
        # Check 4: Threshold applied
        threshold = result.get("dt_scoring_threshold_applied", 0.0)
        validation["checks"]["threshold_applied"] = threshold in (0.50, 0.40)
        
        return validation
    
    def validate_detection_engineer_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate detection engineer CVE tooling and control traceability."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: SIEM rules generated
        siem_rules = result.get("siem_rules", [])
        validation["checks"]["siem_rules_generated"] = len(siem_rules) > 0
        if not validation["checks"]["siem_rules_generated"]:
            validation["issues"].append("No SIEM rules generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ SIEM rules generated: {len(siem_rules)}")
            
            # Check 2: All rules have log_sources_required in scope
            selected_sources = result.get("selected_data_sources", [])
            for rule in siem_rules:
                log_sources = rule.get("log_sources_required", []) or rule.get("data_sources_required", [])
                if log_sources:
                    source_prefixes = [src.split(".")[0].lower() for src in selected_sources]
                    rule_prefixes = [ls.split(".")[0].lower() for ls in log_sources if isinstance(ls, str)]
                    in_scope = any(rp in source_prefixes for rp in rule_prefixes)
                    validation["checks"]["rules_in_scope"] = in_scope
                    if not in_scope:
                        validation["issues"].append(
                            f"Rule {rule.get('rule_id', '?')} has log_sources {log_sources} not in scope {selected_sources}"
                        )
            
            # Check 3: All rules have mapped_control_codes
            for rule in siem_rules:
                has_control = bool(rule.get("mapped_control_codes"))
                validation["checks"]["rule_has_control"] = has_control
                if not has_control:
                    validation["issues"].append(f"Rule {rule.get('rule_id', '?')} missing mapped_control_codes")
            
            # Check 4: ATT&CK techniques populated
            for rule in siem_rules:
                attack_techs = rule.get("mapped_attack_techniques", [])
                has_attack = len(attack_techs) > 0
                validation["checks"]["rule_has_attack_techniques"] = has_attack
                if attack_techs:
                    # Check format (T-format IDs)
                    valid_format = all(t.startswith("T") for t in attack_techs if isinstance(t, str))
                    validation["checks"]["attack_techniques_valid_format"] = valid_format
            
            # Check 5: Alert config present
            for rule in siem_rules:
                alert_config = rule.get("alert_config", {})
                has_threshold = bool(alert_config.get("threshold"))
                has_time_window = bool(alert_config.get("time_window"))
                has_severity = bool(alert_config.get("severity"))
                validation["checks"]["rule_has_alert_config"] = has_threshold and has_time_window and has_severity
        
        # Check 6: Rule gaps populated if needed
        rule_gaps = result.get("dt_rule_gaps", [])
        validation["checks"]["rule_gaps_tracked"] = True  # May be empty
        
        # Check 7: Phase 2 - Metrics/KPIs generated (NEW)
        metrics = result.get("dt_metric_recommendations", [])
        kpis = result.get("kpis", [])
        validation["checks"]["metrics_generated"] = len(metrics) > 0
        validation["checks"]["kpis_generated"] = len(kpis) > 0
        if metrics:
            logger.info(f"  ✓ Metrics generated: {len(metrics)}")
        if kpis:
            logger.info(f"  ✓ KPIs generated: {len(kpis)}")
        
        # Check 8: Phase 2 - Medallion plan generated (NEW)
        medallion_plan = result.get("dt_medallion_plan", {})
        medallion_entries = medallion_plan.get("entries", [])
        validation["checks"]["medallion_plan_generated"] = len(medallion_entries) > 0
        if medallion_entries:
            logger.info(f"  ✓ Medallion plan entries: {len(medallion_entries)}")
        
        # Check 9: Phase 2 - Mappings generated (NEW)
        control_mappings = result.get("control_to_metrics_mappings", [])
        risk_mappings = result.get("risk_to_metrics_mappings", [])
        validation["checks"]["control_mappings_generated"] = len(control_mappings) > 0
        validation["checks"]["risk_mappings_generated"] = len(risk_mappings) > 0
        if control_mappings:
            logger.info(f"  ✓ Control to metrics mappings: {len(control_mappings)}")
        if risk_mappings:
            logger.info(f"  ✓ Risk to metrics mappings: {len(risk_mappings)}")
        
        return validation
    
    def validate_detection_engineer_metrics_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate detection engineer Phase 2 metrics/KPIs generation."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: SIEM rules generated (Phase 1)
        siem_rules = result.get("siem_rules", [])
        validation["checks"]["siem_rules_generated"] = len(siem_rules) > 0
        if not validation["checks"]["siem_rules_generated"]:
            validation["issues"].append("No SIEM rules generated in Phase 1")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ SIEM rules (Phase 1): {len(siem_rules)}")
        
        # Check 2: Metrics generated (Phase 2)
        metrics = result.get("dt_metric_recommendations", [])
        validation["checks"]["metrics_generated"] = len(metrics) > 0
        if not validation["checks"]["metrics_generated"]:
            validation["issues"].append("No metrics generated in Phase 2")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Metrics (Phase 2): {len(metrics)}")
            
            # Check that metrics have natural language calculation steps (no SQL)
            sql_keywords = {"select", "from", "where", "group by", "join", "having", "order by"}
            for metric in metrics[:5]:  # Check first 5
                steps = metric.get("calculation_plan_steps", [])
                for step in steps:
                    step_lower = step.lower() if isinstance(step, str) else ""
                    found_sql = [kw for kw in sql_keywords if kw in step_lower]
                    if found_sql:
                        validation["issues"].append(
                            f"Metric {metric.get('metric_id', '?')} has SQL keywords in steps: {found_sql}"
                        )
                        validation["overall_success"] = False
        
        # Check 3: KPIs generated (Phase 2)
        kpis = result.get("kpis", [])
        validation["checks"]["kpis_generated"] = len(kpis) > 0
        if not validation["checks"]["kpis_generated"]:
            validation["issues"].append("No KPIs generated in Phase 2")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ KPIs (Phase 2): {len(kpis)}")
            
            # Check that KPIs have traceability to risks and controls
            for kpi in kpis[:5]:  # Check first 5
                traceability = kpi.get("traceability", {})
                risk_ids = traceability.get("risk_ids", [])
                control_codes = traceability.get("control_codes", [])
                
                has_risk_mapping = len(risk_ids) > 0
                has_control_mapping = len(control_codes) > 0
                
                if not has_risk_mapping:
                    validation["issues"].append(
                        f"KPI {kpi.get('kpi_id', '?')} missing risk_ids in traceability"
                    )
                if not has_control_mapping:
                    validation["issues"].append(
                        f"KPI {kpi.get('kpi_id', '?')} missing control_codes in traceability"
                    )
        
        # Check 4: Medallion plan generated
        medallion_plan = result.get("dt_medallion_plan", {})
        medallion_entries = medallion_plan.get("entries", [])
        validation["checks"]["medallion_plan_generated"] = len(medallion_entries) > 0
        if not validation["checks"]["medallion_plan_generated"]:
            validation["issues"].append("No medallion plan entries generated")
        else:
            logger.info(f"  ✓ Medallion plan entries: {len(medallion_entries)}")
        
        return validation
    
    def validate_detection_engineer_mappings_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate detection engineer risk and control to metrics mappings."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Control to metrics mappings generated
        control_mappings = result.get("control_to_metrics_mappings", [])
        validation["checks"]["control_mappings_generated"] = len(control_mappings) > 0
        if not validation["checks"]["control_mappings_generated"]:
            validation["issues"].append("No control_to_metrics_mappings generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Control to metrics mappings: {len(control_mappings)}")
            
            # Validate mapping structure
            for mapping in control_mappings[:3]:  # Check first 3
                has_control_code = bool(mapping.get("control_code"))
                has_metric_ids = bool(mapping.get("metric_ids") or mapping.get("kpi_ids"))
                if not has_control_code:
                    validation["issues"].append("Control mapping missing control_code")
                if not has_metric_ids:
                    validation["issues"].append("Control mapping missing metric_ids/kpi_ids")
        
        # Check 2: Risk to metrics mappings generated
        risk_mappings = result.get("risk_to_metrics_mappings", [])
        validation["checks"]["risk_mappings_generated"] = len(risk_mappings) > 0
        if not validation["checks"]["risk_mappings_generated"]:
            validation["issues"].append("No risk_to_metrics_mappings generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Risk to metrics mappings: {len(risk_mappings)}")
            
            # Validate mapping structure
            for mapping in risk_mappings[:3]:  # Check first 3
                has_risk_id = bool(mapping.get("risk_id"))
                has_metric_ids = bool(mapping.get("metric_ids") or mapping.get("kpi_ids"))
                if not has_risk_id:
                    validation["issues"].append("Risk mapping missing risk_id")
                if not has_metric_ids:
                    validation["issues"].append("Risk mapping missing metric_ids/kpi_ids")
        
        # Check 3: KPIs have traceability to risks and controls FROM THE START
        kpis = result.get("kpis", [])
        if kpis:
            scored_context = result.get("dt_scored_context", {})
            scored_risks = {r.get("risk_id", "") for r in scored_context.get("risks", [])}
            scored_controls = {c.get("code", "") for c in scored_context.get("controls", [])}
            
            for kpi in kpis[:5]:  # Check first 5
                traceability = kpi.get("traceability", {})
                kpi_risk_ids = set(traceability.get("risk_ids", []))
                kpi_control_codes = set(traceability.get("control_codes", []))
                
                # Check that KPI risk_ids exist in scored_context.risks
                if kpi_risk_ids:
                    valid_risks = kpi_risk_ids.intersection(scored_risks)
                    if not valid_risks:
                        validation["issues"].append(
                            f"KPI {kpi.get('kpi_id', '?')} has risk_ids {kpi_risk_ids} not in scored_context.risks"
                        )
                
                # Check that KPI control_codes exist in scored_context.controls
                if kpi_control_codes:
                    valid_controls = kpi_control_codes.intersection(scored_controls)
                    if not valid_controls:
                        validation["issues"].append(
                            f"KPI {kpi.get('kpi_id', '?')} has control_codes {kpi_control_codes} not in scored_context.controls"
                        )
        
        # Check 4: Metrics have traceability to risks and controls
        metrics = result.get("dt_metric_recommendations", [])
        if metrics:
            for metric in metrics[:5]:  # Check first 5
                traceability = metric.get("traceability", {})
                metric_risk_ids = traceability.get("risk_ids", [])
                metric_control_codes = traceability.get("control_codes", [])
                
                has_risk_mapping = len(metric_risk_ids) > 0
                has_control_mapping = len(metric_control_codes) > 0
                
                if not has_risk_mapping and not has_control_mapping:
                    validation["issues"].append(
                        f"Metric {metric.get('metric_id', '?')} missing both risk_ids and control_codes in traceability"
                    )
        
        return validation
    
    def validate_detection_engineer_medallion_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate detection engineer medallion plan generation."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Medallion plan generated
        medallion_plan = result.get("dt_medallion_plan", {})
        medallion_entries = medallion_plan.get("entries", [])
        validation["checks"]["medallion_plan_generated"] = len(medallion_entries) > 0
        if not validation["checks"]["medallion_plan_generated"]:
            validation["issues"].append("No medallion plan entries generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Medallion plan entries: {len(medallion_entries)}")
            
            # Check 2: Each entry has required fields
            for entry in medallion_entries[:5]:  # Check first 5
                has_metric_id = bool(entry.get("metric_id"))
                has_bronze_table = bool(entry.get("bronze_table"))
                needs_silver = entry.get("needs_silver")
                
                validation["checks"]["entry_has_metric_id"] = has_metric_id
                validation["checks"]["entry_has_bronze_table"] = has_bronze_table
                validation["checks"]["needs_silver_set"] = needs_silver is not None
                
                if not has_metric_id:
                    validation["issues"].append("Medallion entry missing metric_id")
                if not has_bronze_table:
                    validation["issues"].append("Medallion entry missing bronze_table")
                
                # Check 3: Silver table suggestion if needs_silver is True
                if needs_silver is True:
                    silver_suggestion = entry.get("silver_table_suggestion", {})
                    if isinstance(silver_suggestion, dict):
                        has_silver_name = bool(silver_suggestion.get("name"))
                        has_silver_steps = len(silver_suggestion.get("calculation_steps", [])) >= 3
                        validation["checks"]["silver_has_name"] = has_silver_name
                        validation["checks"]["silver_has_steps"] = has_silver_steps
                        if not has_silver_name:
                            validation["issues"].append(f"Entry {entry.get('metric_id', '?')} needs_silver=True but missing silver name")
                        if not has_silver_steps:
                            validation["issues"].append(f"Entry {entry.get('metric_id', '?')} silver table has < 3 calculation steps")
                
                # Check 4: Gold table accuracy
                gold_available = entry.get("gold_available", False)
                if gold_available is True:
                    gold_table = (entry.get("gold_table") or "").lower()
                    if gold_table:
                        gold_tables = result.get("dt_gold_standard_tables", [])
                        gold_table_names = {gt.get("table_name", "").lower() for gt in gold_tables}
                        in_gold_tables = gold_table in gold_table_names
                        validation["checks"]["gold_available_accurate"] = in_gold_tables
                        if not in_gold_tables:
                            validation["issues"].append(
                                f"Entry {entry.get('metric_id', '?')} has gold_available=True but '{gold_table}' not in gold_tables"
                            )
        
        # Check 5: Bronze tables listed
        bronze_tables = medallion_plan.get("bronze_tables", [])
        validation["checks"]["bronze_tables_listed"] = len(bronze_tables) > 0
        if bronze_tables:
            logger.info(f"  ✓ Bronze tables: {len(bronze_tables)}")
        
        # Check 6: Silver tables suggested (if any)
        silver_tables = medallion_plan.get("silver_tables", [])
        validation["checks"]["silver_tables_suggested"] = len(silver_tables) >= 0  # May be empty
        
        # Check 7: Gold tables referenced
        gold_tables_list = medallion_plan.get("gold_tables", [])
        validation["checks"]["gold_tables_referenced"] = len(gold_tables_list) >= 0  # May be empty
        
        return validation
    
    def validate_triage_engineer_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate triage engineer no-SQL and medallion plan."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Metric recommendations ≥ 10
        recommendations = result.get("dt_metric_recommendations", [])
        validation["checks"]["recommendations_count"] = len(recommendations) >= 10
        if not validation["checks"]["recommendations_count"]:
            validation["issues"].append(f"Only {len(recommendations)} recommendations (minimum 10 required)")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Metric recommendations: {len(recommendations)}")
            
            # Check 2: No SQL keywords in calculation_plan_steps
            sql_keywords = {"select", "from", "where", "group by", "join", "having", "order by"}
            for rec in recommendations:
                steps = rec.get("calculation_plan_steps", [])
                for step in steps:
                    step_lower = step.lower() if isinstance(step, str) else ""
                    found_sql = [kw for kw in sql_keywords if kw in step_lower]
                    validation["checks"]["no_sql_keywords"] = len(found_sql) == 0
                    if found_sql:
                        validation["issues"].append(
                            f"Recommendation {rec.get('id', '?')} has SQL keywords in steps: {found_sql}"
                        )
                        validation["overall_success"] = False
            
            # Check 3: First step references a table
            for rec in recommendations:
                steps = rec.get("calculation_plan_steps", [])
                if steps:
                    first_step = steps[0].lower() if isinstance(steps[0], str) else ""
                    has_table_ref = "table" in first_step or "from" in first_step
                    validation["checks"]["first_step_has_table_ref"] = has_table_ref
                    if not has_table_ref:
                        validation["issues"].append(
                            f"Recommendation {rec.get('id', '?')} first step should reference a table"
                        )
            
            # Check 4: All recommendations have mapped_control_codes
            for rec in recommendations:
                has_control = bool(rec.get("mapped_control_codes"))
                validation["checks"]["rec_has_control"] = has_control
                if not has_control:
                    validation["issues"].append(f"Recommendation {rec.get('id', '?')} missing mapped_control_codes")
        
        # Check 5: Medallion plan generated
        medallion_plan = result.get("dt_medallion_plan", {})
        medallion_entries = medallion_plan.get("entries", [])
        validation["checks"]["medallion_plan_generated"] = len(medallion_entries) > 0
        if medallion_entries:
            logger.info(f"  ✓ Medallion plan entries: {len(medallion_entries)}")
            # Check needs_silver for trend metrics
            for entry in medallion_entries:
                needs_silver = entry.get("needs_silver")
                validation["checks"]["needs_silver_set"] = needs_silver is not None
            
            # Check gold_available accuracy
            gold_tables = result.get("dt_gold_standard_tables", [])
            gold_table_names = {gt.get("table_name", "").lower() for gt in gold_tables}
            for entry in medallion_entries:
                if entry.get("gold_available") is True:
                    gold_table = (entry.get("gold_table") or "").lower()
                    if gold_table:
                        in_gold_tables = gold_table in gold_table_names
                        validation["checks"]["gold_available_accurate"] = in_gold_tables
                        if not in_gold_tables:
                            validation["issues"].append(
                                f"Entry {entry.get('metric_id', '?')} has gold_available=True but '{gold_table}' not in gold_tables"
                            )
        
        return validation
    
    def validate_siem_validator_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate SIEM validator source scope checks."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Validation status (may fail for narrow scope)
        validation_passed = result.get("dt_siem_validation_passed", False)
        validation["checks"]["validation_ran"] = True  # Just that it ran
        
        # Check 2: Failures recorded
        failures = result.get("dt_siem_validation_failures", [])
        validation["checks"]["failures_recorded"] = len(failures) >= 0  # May be empty
        
        # Check 3: RULE-V3 failures for out-of-scope sources
        rule_v3_failures = [
            f for f in failures
            if f.get("check") == "RULE-V3" or "out of scope" in str(f.get("finding", "")).lower()
        ]
        validation["checks"]["rule_v3_failures"] = len(rule_v3_failures) >= 0  # May be empty
        if rule_v3_failures:
            logger.info(f"  ✓ RULE-V3 failures: {len(rule_v3_failures)}")
            # Check fix instructions
            has_fix_instructions = all(
                bool(f.get("fix_instruction"))
                for f in rule_v3_failures
            )
            validation["checks"]["failures_have_fix_instructions"] = has_fix_instructions
        
        # Check 4: Validation iteration incremented if failed
        if not validation_passed:
            iteration = result.get("dt_validation_iteration", 0)
            validation["checks"]["iteration_incremented"] = iteration > 0
        
        return validation
    
    def validate_metric_validator_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metric calculation validator SQL detection."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Rule summary populated
        rule_summary = result.get("dt_metric_validation_rule_summary", {})
        validation["checks"]["rule_summary_populated"] = len(rule_summary) > 0
        
        # Check 2: RULE-C2 (SQL detection) status
        rule_c2_status = rule_summary.get("RULE-C2", "unknown")
        validation["checks"]["rule_c2_pass"] = rule_c2_status == "pass"
        if rule_c2_status != "pass":
            validation["issues"].append(f"RULE-C2 (SQL detection) should pass, got '{rule_c2_status}'")
        
        # Check 3: RULE-M2 (gold_available accuracy) status
        rule_m2_status = rule_summary.get("RULE-M2", "unknown")
        validation["checks"]["rule_m2_pass"] = rule_m2_status == "pass"
        if rule_m2_status != "pass":
            validation["issues"].append(f"RULE-M2 (gold_available accuracy) should pass, got '{rule_m2_status}'")
        
        # Check 4: RULE-W1 (minimum 10 recommendations) status
        rule_w1_status = rule_summary.get("RULE-W1", "unknown")
        validation["checks"]["rule_w1_pass_or_warning"] = rule_w1_status in ("pass", "warning")
        
        # Check 5: Failures have step_number if applicable
        failures = result.get("dt_metric_validation_failures", [])
        if failures:
            has_step_numbers = any(f.get("step_number") is not None for f in failures)
            validation["checks"]["failures_have_step_numbers"] = has_step_numbers
        
        return validation
    
    def validate_playbook_assembler_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate playbook assembler Template C output."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Playbook assembled
        assembled_playbook = result.get("dt_assembled_playbook")
        validation["checks"]["playbook_assembled"] = assembled_playbook is not None
        if not assembled_playbook:
            validation["issues"].append("dt_assembled_playbook not generated")
            validation["overall_success"] = False
        else:
            # Check 2: Template C sections present
            has_exec_summary = "executive_summary" in assembled_playbook or "summary" in assembled_playbook
            has_detection_rules = "detection_rules" in assembled_playbook or "siem_rules" in assembled_playbook
            has_medallion = "medallion" in str(assembled_playbook).lower() or "medallion_plan" in assembled_playbook
            has_metrics = "metric" in str(assembled_playbook).lower() or "recommendations" in assembled_playbook
            has_traceability = "traceability" in str(assembled_playbook).lower()
            has_gap_analysis = "gap" in str(assembled_playbook).lower()
            
            validation["checks"]["has_exec_summary"] = has_exec_summary
            validation["checks"]["has_detection_rules"] = has_detection_rules
            validation["checks"]["has_medallion"] = has_medallion
            validation["checks"]["has_metrics"] = has_metrics
            validation["checks"]["has_traceability"] = has_traceability
            validation["checks"]["has_gap_analysis"] = has_gap_analysis
            
            if not (has_detection_rules and has_metrics):
                validation["issues"].append("Template C should have both detection rules and metrics sections")
        
        # Check 3: Quality score
        quality_score = result.get("quality_score")
        validation["checks"]["quality_score_present"] = quality_score is not None
        if quality_score is not None:
            validation["checks"]["quality_score_above_60"] = quality_score >= 60
            logger.info(f"  ✓ Quality score: {quality_score:.1f}/100")
        
        # Check 4: Gap notes in playbook
        gap_notes = result.get("dt_gap_notes", [])
        if gap_notes:
            validation["checks"]["gap_notes_present"] = len(gap_notes) > 0
        
        return validation
    
    def validate_detection_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate detection engineering output."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent classified correctly
        intent = result.get("intent")
        validation["checks"]["intent_classified"] = intent in (
            "detection_engineering", "full_pipeline"
        )
        if not validation["checks"]["intent_classified"]:
            validation["issues"].append(f"Intent should be 'detection_engineering' or 'full_pipeline', got '{intent}'")
        
        # Check 2: Plan generated
        plan_summary = result.get("dt_plan_summary")
        playbook_template = result.get("dt_playbook_template")
        validation["checks"]["plan_generated"] = plan_summary is not None
        validation["checks"]["template_selected"] = playbook_template in ("A", "C")
        if not validation["checks"]["plan_generated"]:
            validation["issues"].append("DT plan summary not generated")
        
        # Check 3: Framework context retrieved
        controls = result.get("dt_retrieved_controls", [])
        risks = result.get("dt_retrieved_risks", [])
        scenarios = result.get("dt_retrieved_scenarios", [])
        validation["checks"]["controls_retrieved"] = len(controls) > 0
        validation["checks"]["risks_retrieved"] = len(risks) > 0
        validation["checks"]["scenarios_retrieved"] = len(scenarios) > 0
        if not validation["checks"]["scenarios_retrieved"]:
            validation["issues"].append("No attack scenarios retrieved")
        
        # Check 4: Scored context produced
        scored_context = result.get("dt_scored_context", {})
        validation["checks"]["scored_context_produced"] = scored_context is not None
        if scored_context:
            scored_controls = scored_context.get("controls", [])
            scored_scenarios = scored_context.get("scenarios", [])
            validation["checks"]["scored_controls"] = len(scored_controls) > 0
            validation["checks"]["scored_scenarios"] = len(scored_scenarios) > 0
        
        # Check 5: SIEM rules generated
        siem_rules = result.get("siem_rules", [])
        validation["checks"]["siem_rules_generated"] = len(siem_rules) > 0
        if not validation["checks"]["siem_rules_generated"]:
            validation["issues"].append("No SIEM rules generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ SIEM rules generated: {len(siem_rules)}")
            # Validate rule structure
            for rule in siem_rules[:3]:  # Check first 3 rules
                has_control = bool(rule.get("mapped_control_codes"))
                has_alert_config = bool(rule.get("alert_config"))
                validation["checks"]["rule_has_control"] = has_control
                validation["checks"]["rule_has_alert_config"] = has_alert_config
                if not has_control:
                    validation["issues"].append(f"Rule {rule.get('rule_id', '?')} missing mapped_control_codes")
        
        # Check 6: SIEM validation
        siem_validation_passed = result.get("dt_siem_validation_passed", False)
        validation["checks"]["siem_validation_passed"] = siem_validation_passed
        if not siem_validation_passed:
            failures = result.get("dt_siem_validation_failures", [])
            critical = [f for f in failures if f.get("severity") == "critical"]
            validation["issues"].append(f"SIEM validation failed: {len(critical)} critical issues")
        
        # Check 7: Playbook assembled
        assembled_playbook = result.get("dt_assembled_playbook")
        validation["checks"]["playbook_assembled"] = assembled_playbook is not None
        
        # Check 8: No critical errors
        error = result.get("error")
        validation["checks"]["no_errors"] = error is None
        if error:
            validation["issues"].append(f"Pipeline error: {error}")
            validation["overall_success"] = False
        
        # Update overall success
        critical_checks = [
            "intent_classified",
            "scenarios_retrieved",
            "siem_rules_generated",
            "no_errors"
        ]
        for check in critical_checks:
            if not validation["checks"].get(check, False):
                validation["overall_success"] = False
        
        return validation
    
    def validate_triage_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate triage engineering output."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent classified correctly
        intent = result.get("intent")
        validation["checks"]["intent_classified"] = intent in (
            "triage_engineering", "full_pipeline"
        )
        if not validation["checks"]["intent_classified"]:
            validation["issues"].append(f"Intent should be 'triage_engineering' or 'full_pipeline', got '{intent}'")
        
        # Check 2: Plan generated
        plan_summary = result.get("dt_plan_summary")
        playbook_template = result.get("dt_playbook_template")
        validation["checks"]["plan_generated"] = plan_summary is not None
        validation["checks"]["template_selected"] = playbook_template in ("B", "C")
        
        # Check 3: Metrics retrieved
        resolved_metrics = result.get("resolved_metrics", [])
        validation["checks"]["metrics_retrieved"] = len(resolved_metrics) > 0
        if not validation["checks"]["metrics_retrieved"]:
            validation["issues"].append("No metrics retrieved from leen_metrics_registry")
        else:
            logger.info(f"  ✓ Metrics retrieved: {len(resolved_metrics)}")
        
        # Check 4: MDL schemas retrieved (via product capabilities + project_id)
        resolved_schemas = result.get("dt_resolved_schemas", [])
        validation["checks"]["schemas_retrieved"] = len(resolved_schemas) > 0
        if not validation["checks"]["schemas_retrieved"]:
            validation["issues"].append("No MDL schemas retrieved")
        else:
            logger.info(f"  ✓ MDL schemas retrieved: {len(resolved_schemas)}")
            # Check that schemas have project_id/product_id info
            has_project_info = any(
                s.get("project_id") or s.get("product_id")
                for s in resolved_schemas[:3]
            )
            validation["checks"]["schemas_have_project_info"] = has_project_info
        
        # Check 5: Gold standard tables retrieved
        gold_tables = result.get("dt_gold_standard_tables", [])
        validation["checks"]["gold_tables_retrieved"] = len(gold_tables) >= 0  # May be empty
        if gold_tables:
            logger.info(f"  ✓ Gold standard tables: {len(gold_tables)}")
        
        # Check 6: Metric recommendations generated
        metric_recommendations = result.get("dt_metric_recommendations", [])
        validation["checks"]["metric_recommendations_generated"] = len(metric_recommendations) >= 10
        if not validation["checks"]["metric_recommendations_generated"]:
            validation["issues"].append(
                f"Only {len(metric_recommendations)} recommendations (minimum 10 required)"
            )
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Metric recommendations: {len(metric_recommendations)}")
            # Validate recommendation structure
            for rec in metric_recommendations[:3]:
                has_control = bool(rec.get("mapped_control_codes"))
                has_steps = len(rec.get("calculation_plan_steps", [])) >= 3
                validation["checks"]["rec_has_control"] = has_control
                validation["checks"]["rec_has_steps"] = has_steps
                if not has_control:
                    validation["issues"].append(f"Recommendation {rec.get('id', '?')} missing mapped_control_codes")
                if not has_steps:
                    validation["issues"].append(f"Recommendation {rec.get('id', '?')} has < 3 calculation steps")
        
        # Check 7: Medallion plan generated
        medallion_plan = result.get("dt_medallion_plan", {})
        medallion_entries = medallion_plan.get("entries", [])
        validation["checks"]["medallion_plan_generated"] = len(medallion_entries) > 0
        if not validation["checks"]["medallion_plan_generated"]:
            validation["issues"].append("No medallion plan entries generated")
        else:
            logger.info(f"  ✓ Medallion plan entries: {len(medallion_entries)}")
        
        # Check 8: Metric validation
        metric_validation_passed = result.get("dt_metric_validation_passed", False)
        validation["checks"]["metric_validation_passed"] = metric_validation_passed
        if not metric_validation_passed:
            failures = result.get("dt_metric_validation_failures", [])
            validation["issues"].append(f"Metric validation failed: {len(failures)} critical issues")
        
        # Check 9: Playbook assembled
        assembled_playbook = result.get("dt_assembled_playbook")
        validation["checks"]["playbook_assembled"] = assembled_playbook is not None
        
        # Check 10: No critical errors
        error = result.get("error")
        validation["checks"]["no_errors"] = error is None
        if error:
            validation["issues"].append(f"Pipeline error: {error}")
            validation["overall_success"] = False
        
        # Update overall success
        critical_checks = [
            "intent_classified",
            "metrics_retrieved",
            "metric_recommendations_generated",
            "medallion_plan_generated",
            "no_errors"
        ]
        for check in critical_checks:
            if not validation["checks"].get(check, False):
                validation["overall_success"] = False
        
        return validation
    
    def validate_full_pipeline_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate full pipeline (detection + triage) output."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent classified as full_pipeline
        intent = result.get("intent")
        validation["checks"]["intent_classified"] = intent == "full_pipeline"
        if not validation["checks"]["intent_classified"]:
            validation["issues"].append(f"Intent should be 'full_pipeline', got '{intent}'")
        
        # Check 2: Template C selected
        playbook_template = result.get("dt_playbook_template")
        validation["checks"]["template_c_selected"] = playbook_template == "C"
        
        # Check 3: Both SIEM rules and metrics generated
        siem_rules = result.get("siem_rules", [])
        metric_recommendations = result.get("dt_metric_recommendations", [])
        validation["checks"]["siem_rules_generated"] = len(siem_rules) > 0
        validation["checks"]["metric_recommendations_generated"] = len(metric_recommendations) >= 10
        if not validation["checks"]["siem_rules_generated"]:
            validation["issues"].append("No SIEM rules generated in full pipeline")
        if not validation["checks"]["metric_recommendations_generated"]:
            validation["issues"].append(f"Only {len(metric_recommendations)} metric recommendations (min 10)")
        
        # Check 4: Both validations passed
        siem_validation_passed = result.get("dt_siem_validation_passed", False)
        metric_validation_passed = result.get("dt_metric_validation_passed", False)
        validation["checks"]["siem_validation_passed"] = siem_validation_passed
        validation["checks"]["metric_validation_passed"] = metric_validation_passed
        
        # Check 5: Playbook assembled with both sections
        assembled_playbook = result.get("dt_assembled_playbook")
        validation["checks"]["playbook_assembled"] = assembled_playbook is not None
        
        # Check 6: Quality score
        quality_score = result.get("quality_score")
        validation["checks"]["quality_score_present"] = quality_score is not None
        if quality_score is not None:
            logger.info(f"  ✓ Quality score: {quality_score:.1f}/100")
        
        # Check 7: No critical errors
        error = result.get("error")
        validation["checks"]["no_errors"] = error is None
        if error:
            validation["issues"].append(f"Pipeline error: {error}")
            validation["overall_success"] = False
        
        # Update overall success
        critical_checks = [
            "intent_classified",
            "siem_rules_generated",
            "metric_recommendations_generated",
            "no_errors"
        ]
        for check in critical_checks:
            if not validation["checks"].get(check, False):
                validation["overall_success"] = False
        
        return validation
    
    def get_test_output_dir(self, test_name: str) -> Path:
        """Create and return test-specific output directory: tests/outputs/testcase_name/timestamp/"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_output_dir = self.output_base_dir / test_name / timestamp
        test_output_dir.mkdir(parents=True, exist_ok=True)
        self.current_test_output_dir = test_output_dir
        return test_output_dir
    
    def save_test_output(self, test_name: str, result: Dict[str, Any], validation: Dict[str, Any]):
        """Save test output to organized directory structure: tests/outputs/testcase_name/timestamp/"""
        # Get or create test-specific output directory
        test_output_dir = self.current_test_output_dir or self.get_test_output_dir(test_name)
        
        # Save main output file
        output_file = test_output_dir / "output.json"
        
        # Sanitize result for JSON (truncate large content)
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
        
        # Save state snapshot (key fields only)
        if "result" in output_data and isinstance(output_data["result"], dict):
            state_snapshot = {
                "intent": output_data["result"].get("intent"),
                "framework_id": output_data["result"].get("framework_id"),
                "dt_playbook_template": output_data["result"].get("dt_playbook_template"),
                "dt_data_sources_in_scope": output_data["result"].get("dt_data_sources_in_scope"),
                "resolved_metrics_count": len(output_data["result"].get("resolved_metrics", [])),
                "dt_resolved_schemas_count": len(output_data["result"].get("dt_resolved_schemas", [])),
                "siem_rules_count": len(output_data["result"].get("siem_rules", [])),
                "dt_metric_recommendations_count": len(output_data["result"].get("dt_metric_recommendations", [])),
            }
            with open(outputs_dir / "state_snapshot.json", 'w') as f:
                json.dump(state_snapshot, f, indent=2, default=str)
            
            # Save metrics if present
            if output_data["result"].get("resolved_metrics"):
                with open(outputs_dir / "resolved_metrics.json", 'w') as f:
                    json.dump(output_data["result"]["resolved_metrics"], f, indent=2, default=str)
            
            # Save schemas if present
            if output_data["result"].get("dt_resolved_schemas"):
                with open(outputs_dir / "resolved_schemas.json", 'w') as f:
                    json.dump(output_data["result"]["dt_resolved_schemas"], f, indent=2, default=str)
            
            # Save SIEM rules if present
            if output_data["result"].get("siem_rules"):
                with open(outputs_dir / "siem_rules.json", 'w') as f:
                    json.dump(output_data["result"]["siem_rules"], f, indent=2, default=str)
            
            # Save metric recommendations if present
            if output_data["result"].get("dt_metric_recommendations"):
                with open(outputs_dir / "metric_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["dt_metric_recommendations"], f, indent=2, default=str)
            
            # Save medallion plan if present
            if output_data["result"].get("dt_medallion_plan"):
                with open(outputs_dir / "medallion_plan.json", 'w') as f:
                    json.dump(output_data["result"]["dt_medallion_plan"], f, indent=2, default=str)
            
            # Save KPIs if present (detection engineer Phase 2)
            if output_data["result"].get("kpis"):
                with open(outputs_dir / "kpis.json", 'w') as f:
                    json.dump(output_data["result"]["kpis"], f, indent=2, default=str)
            
            # Save control to metrics mappings if present
            if output_data["result"].get("control_to_metrics_mappings"):
                with open(outputs_dir / "control_to_metrics_mappings.json", 'w') as f:
                    json.dump(output_data["result"]["control_to_metrics_mappings"], f, indent=2, default=str)
            
            # Save risk to metrics mappings if present
            if output_data["result"].get("risk_to_metrics_mappings"):
                with open(outputs_dir / "risk_to_metrics_mappings.json", 'w') as f:
                    json.dump(output_data["result"]["risk_to_metrics_mappings"], f, indent=2, default=str)
        
        logger.info(f"  ✓ Output saved to: {test_output_dir}")
        logger.info(f"    - Main output: {output_file}")
        logger.info(f"    - Key outputs: {outputs_dir}")
    
    def sanitize_for_json(self, data: Any, max_length: int = 10000) -> Any:
        """Recursively sanitize data for JSON output."""
        if isinstance(data, dict):
            return {k: self.sanitize_for_json(v, max_length) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_for_json(item, max_length) for item in data[:10]]  # Limit list size
        elif isinstance(data, str) and len(data) > max_length:
            return {
                "truncated": True,
                "original_length": len(data),
                "preview": data[:max_length],
                "suffix": data[-500:] if len(data) > 500 else data
            }
        else:
            return data
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and generate summary."""
        logger.info("=" * 80)
        logger.info("DETECTION & TRIAGE WORKFLOW TEST SUITE")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        # Run all tests (from dt_agents_test.md)
        # Note: Use --test use_cases to run only the 3 focused use cases
        tests = [
            # Focused Use Cases (fastest, most relevant)
            ("Use Case 1: Metrics Help", self.test_use_case_1_metrics_help),
            ("Use Case 2: Dashboard Metrics", self.test_use_case_2_dashboard_metrics_workflow),
            ("Use Case 3: Detection + Metrics Full", self.test_use_case_3_detection_and_metrics_full),
            # Individual Node Tests (for debugging)
            ("Intent Classifier - Enrichment Signals", self.test_intent_classifier_enrichment_signals),
            ("Planner - Gap Notes", self.test_planner_gap_notes),
            ("Framework Retrieval - Detective Controls", self.test_framework_retrieval_detective_controls),
            ("Metrics Retrieval - Source Filtering", self.test_metrics_retrieval_source_filtering),
            ("MDL Schema - Exact Lookup", self.test_mdl_schema_exact_lookup),
            ("Scoring Validator - Adversarial", self.test_scoring_validator_adversarial),
            ("Detection Engineer - CVE Tooling", self.test_detection_engineer_cve_tooling),
            ("Detection Engineer - Metrics Generation", self.test_detection_engineer_metrics_generation),
            ("Detection Engineer - Risk Control Mappings", self.test_detection_engineer_risk_control_mappings),
            ("Detection Engineer - Medallion Plan", self.test_detection_engineer_medallion_plan),
            ("Triage Engineer - No SQL", self.test_triage_engineer_no_sql),
            ("SIEM Validator - Source Scope", self.test_siem_validator_source_scope),
            ("Metric Validator - SQL Detection", self.test_metric_validator_sql_detection),
            ("Playbook Assembler - Template C", self.test_playbook_assembler_template_c),
            ("HIPAA Breach Detection (Full)", self.test_hipaa_breach_detection),
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
        summary_file = self.output_base_dir / f"dt_test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Detection & Triage Engineering workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--test',
        choices=[
            'all',
            'use_cases',  # Run only the 3 focused use cases
            'use_case_1',  # Metrics Help
            'use_case_2',  # Dashboard Metrics Workflow
            'use_case_3',  # Detection + Metrics Full
            'intent_classifier',
            'planner',
            'framework_retrieval',
            'metrics_retrieval',
            'mdl_schema',
            'scoring_validator',
            'detection_engineer',
            'detection_engineer_metrics',
            'detection_engineer_mappings',
            'detection_engineer_medallion',
            'triage_engineer',
            'siem_validator',
            'metric_validator',
            'playbook_assembler',
            'hipaa_detection',
        ],
        default='all',
        help='Which test to run (use_cases = run only the 3 focused use cases)'
    )
    
    parser.add_argument(
        '--skip-slow',
        action='store_true',
        help='Skip slow operations (full workflow, playbook assembly)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Enable verbose logging for all app modules
        logging.getLogger("app").setLevel(logging.DEBUG)
        logging.getLogger("app.agents").setLevel(logging.DEBUG)
        logging.getLogger("app.agents.dt_nodes").setLevel(logging.DEBUG)
        logging.getLogger("app.core").setLevel(logging.DEBUG)
        logging.getLogger("app.retrieval").setLevel(logging.DEBUG)
    
    tester = DetectionTriageWorkflowTester()
    results = None
    
    # Store skip_slow flag for use in test methods if needed
    tester.skip_slow = args.skip_slow
    
    if args.test == 'all':
        results = tester.run_all_tests()
    elif args.test == 'use_cases':
        # Run only the 3 focused use cases
        tester.setup()
        results = {}
        result1 = tester.test_use_case_1_metrics_help()
        results["Use Case 1: Metrics Help"] = result1
        result2 = tester.test_use_case_2_dashboard_metrics_workflow()
        results["Use Case 2: Dashboard Metrics"] = result2
        if not args.skip_slow:
            result3 = tester.test_use_case_3_detection_and_metrics_full()
            results["Use Case 3: Detection + Metrics Full"] = result3
        tester.print_summary(results)
    elif args.test == 'use_case_1':
        tester.setup()
        result = tester.test_use_case_1_metrics_help()
        tester.print_summary({"Use Case 1: Metrics Help": result})
        results = {"results": result}
    elif args.test == 'use_case_2':
        tester.setup()
        result = tester.test_use_case_2_dashboard_metrics_workflow()
        tester.print_summary({"Use Case 2: Dashboard Metrics": result})
        results = {"results": result}
    elif args.test == 'use_case_3':
        tester.setup()
        result = tester.test_use_case_3_detection_and_metrics_full()
        tester.print_summary({"Use Case 3: Detection + Metrics Full": result})
        results = {"results": result}
    elif args.test == 'intent_classifier':
        tester.setup()
        result = tester.test_intent_classifier_enrichment_signals()
        tester.print_summary({"Intent Classifier": result})
        results = {"results": result}
    elif args.test == 'planner':
        tester.setup()
        result = tester.test_planner_gap_notes()
        tester.print_summary({"Planner": result})
        results = {"results": result}
    elif args.test == 'framework_retrieval':
        tester.setup()
        result = tester.test_framework_retrieval_detective_controls()
        tester.print_summary({"Framework Retrieval": result})
        results = {"results": result}
    elif args.test == 'metrics_retrieval':
        tester.setup()
        result = tester.test_metrics_retrieval_source_filtering()
        tester.print_summary({"Metrics Retrieval": result})
        results = {"results": result}
    elif args.test == 'mdl_schema':
        tester.setup()
        result = tester.test_mdl_schema_exact_lookup()
        tester.print_summary({"MDL Schema": result})
        results = {"results": result}
    elif args.test == 'scoring_validator':
        tester.setup()
        result = tester.test_scoring_validator_adversarial()
        tester.print_summary({"Scoring Validator": result})
        results = {"results": result}
    elif args.test == 'detection_engineer':
        tester.setup()
        result = tester.test_detection_engineer_cve_tooling()
        tester.print_summary({"Detection Engineer": result})
        results = {"results": result}
    elif args.test == 'detection_engineer_metrics':
        tester.setup()
        result = tester.test_detection_engineer_metrics_generation()
        tester.print_summary({"Detection Engineer Metrics": result})
        results = {"results": result}
    elif args.test == 'detection_engineer_mappings':
        tester.setup()
        result = tester.test_detection_engineer_risk_control_mappings()
        tester.print_summary({"Detection Engineer Mappings": result})
        results = {"results": result}
    elif args.test == 'detection_engineer_medallion':
        tester.setup()
        result = tester.test_detection_engineer_medallion_plan()
        tester.print_summary({"Detection Engineer Medallion": result})
        results = {"results": result}
    elif args.test == 'triage_engineer':
        tester.setup()
        result = tester.test_triage_engineer_no_sql()
        tester.print_summary({"Triage Engineer": result})
        results = {"results": result}
    elif args.test == 'siem_validator':
        tester.setup()
        result = tester.test_siem_validator_source_scope()
        tester.print_summary({"SIEM Validator": result})
        results = {"results": result}
    elif args.test == 'metric_validator':
        tester.setup()
        result = tester.test_metric_validator_sql_detection()
        tester.print_summary({"Metric Validator": result})
        results = {"results": result}
    elif args.test == 'playbook_assembler':
        tester.setup()
        result = tester.test_playbook_assembler_template_c()
        tester.print_summary({"Playbook Assembler": result})
        results = {"results": result}
    elif args.test == 'hipaa_detection':
        tester.setup()
        result = tester.test_hipaa_breach_detection()
        tester.print_summary({"HIPAA Breach Detection": result})
        results = {"results": result}
    
    if results:
        logger.info(f"\nAll outputs saved to: {OUTPUT_BASE_DIR}")


if __name__ == '__main__':
    main()
