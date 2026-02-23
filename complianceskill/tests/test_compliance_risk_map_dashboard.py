#!/usr/bin/env python3
"""
Test suite for compliance risk mapping and dashboard generation.

This test validates the complete compliance-to-operations pipeline for risk mapping:
1. Intent Classification (dashboard_generation)
2. Profile Resolution (data source recommendations and selection)
3. Focus Area Resolution (vulnerabilities, asset management)
4. Metrics Recommendation
5. Calculation Planning
6. Dashboard Generation

Based on use cases from:
- docs/compliance_usecases.md
- docs/conversational_compliance_usecase.md

Uses .env configuration for ChromaDB settings.
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

from app.agents.workflow import create_compliance_app
from app.agents.state import EnhancedCompliancePipelineState
from langgraph.checkpoint.memory import MemorySaver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Create output directory
OUTPUT_DIR = base_dir / "tests" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ComplianceRiskMapDashboardTester:
    """Test suite for compliance risk mapping and dashboard generation."""
    
    def __init__(self):
        self.app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_dir = OUTPUT_DIR
    
    def setup(self):
        """Initialize the compliance app."""
        logger.info("Setting up compliance pipeline app...")
        self.app = create_compliance_app(checkpointer=self.checkpointer)
        logger.info("✓ Compliance app initialized")
    
    def create_initial_state(self, user_query: str) -> EnhancedCompliancePipelineState:
        """Create initial state for the pipeline."""
        return {
            "user_query": user_query,
            "messages": [],
            "session_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            
            # Initialize empty artifact lists
            "controls": [],
            "risks": [],
            "scenarios": [],
            "test_cases": [],
            "siem_rules": [],
            "playbooks": [],
            "test_scripts": [],
            "data_pipelines": [],
            "dashboards": [],
            "vulnerability_mappings": [],
            
            # Initialize execution logging
            "execution_steps": [],
            "gap_analysis_results": [],
            "cross_framework_mappings": [],
            "metrics_context": [],
            "xsoar_indicators": [],
            
            # Initialize validation & refinement tracking
            "validation_results": [],
            "validation_passed": True,
            "iteration_count": 0,
            "max_iterations": 3,
            "refinement_history": [],
            "context_cache": {},
            
            # Initialize planning
            "execution_plan": None,
            "current_step_index": 0,
            "plan_completion_status": {},
            
            # Optional fields
            "intent": None,
            "framework_id": None,
            "requirement_id": None,
            "requirement_code": None,
            "requirement_name": None,
            "requirement_description": None,
            "next_agent": None,
            "error": None,
            "quality_score": None,
            
            # New fields for profile/metrics/calculation flow
            "data_enrichment": {
                "needs_mdl": False,
                "needs_metrics": False,
                "needs_xsoar_dashboard": False,
                "suggested_focus_areas": [],
                "metrics_intent": None
            },
            "compliance_profile": None,
            "selected_data_sources": [],
            "resolved_focus_areas": [],
            "focus_area_categories": [],
            "resolved_metrics": [],
            "calculation_plan": None,
        }
    
    def simulate_data_source_selection(self, state: EnhancedCompliancePipelineState, select_all: bool = True) -> EnhancedCompliancePipelineState:
        """
        Simulate user selecting all recommended data sources.
        
        Args:
            state: Current pipeline state
            select_all: If True, select all recommended sources
        """
        # Get recommended data sources from checkpoint or state
        checkpoints = state.get("checkpoints", [])
        recommended = []
        
        # Try to get recommendations from checkpoint
        for checkpoint in checkpoints:
            if checkpoint.get("type") == "profile_resolver_data_sources":
                recommended = checkpoint.get("data", {}).get("recommended_data_sources", [])
                break
        
        if not recommended:
            # Get all available sources
            from app.config.focus_areas import get_all_supported_data_sources
            all_sources = get_all_supported_data_sources()
            recommended = [{"name": src} for src in all_sources]
        
        if select_all:
            # Select all recommended sources
            selected = [src.get("name") if isinstance(src, dict) else src for src in recommended]
        else:
            # Select only first 2-3 sources
            selected = [src.get("name") if isinstance(src, dict) else src for src in recommended[:3]]
        
        # Set user checkpoint input to simulate selection
        state["user_checkpoint_input"] = {
            "checkpoint_type": "profile_resolver_data_sources",
            "selected_data_sources": selected
        }
        
        logger.info(f"  ✓ Simulated data source selection: {selected}")
        return state
    
    def simulate_focus_area_selection(self, state: EnhancedCompliancePipelineState, categories: List[str] = None) -> EnhancedCompliancePipelineState:
        """
        Simulate user selecting focus areas based on categories.
        
        Args:
            state: Current pipeline state
            categories: List of categories to select (default: ["vulnerabilities", "assets"])
                        Note: Actual categories in catalogs are "vulnerabilities", "assets", "inventory"
        """
        if categories is None:
            # Use actual category names from focus area catalogs
            categories = ["vulnerabilities", "assets", "inventory"]
        
        # Get all available focus areas from checkpoint or state
        checkpoints = state.get("checkpoints", [])
        all_focus_areas = state.get("resolved_focus_areas", [])
        
        # Try to get from checkpoint
        for checkpoint in checkpoints:
            if checkpoint.get("type") == "profile_resolver_focus_areas":
                all_focus_areas = checkpoint.get("data", {}).get("all_available_focus_areas", all_focus_areas)
                break
        
        # Filter focus areas by categories
        selected_focus_areas = []
        for fa in all_focus_areas:
            fa_categories = fa.get("categories", [])
            if any(cat in fa_categories for cat in categories):
                selected_focus_areas.append(fa.get("id") or fa.get("name"))
        
        # If no matches, select all focus areas
        if not selected_focus_areas:
            selected_focus_areas = [fa.get("id") or fa.get("name") for fa in all_focus_areas]
        
        # Set user checkpoint input to simulate selection
        state["user_checkpoint_input"] = {
            "checkpoint_type": "profile_resolver_focus_areas",
            "selected_focus_areas": selected_focus_areas
        }
        
        logger.info(f"  ✓ Simulated focus area selection: {len(selected_focus_areas)} areas for categories {categories}")
        return state
    
    def test_hipaa_risk_dashboard(self) -> Dict[str, Any]:
        """
        Test: HIPAA Risk Dashboard Generation
        
        Use Case: Build dashboard for HIPAA compliance showing vulnerability and asset management risks.
        Based on compliance_usecases.md - HIPAA breach detection use case.
        """
        logger.info("=" * 80)
        logger.info("TEST: HIPAA Risk Dashboard Generation")
        logger.info("=" * 80)
        
        user_query = (
            "Show me my HIPAA compliance posture for vulnerability management and asset management. "
            "I need a dashboard with KPIs showing current state and trends for risks related to "
            "HIPAA §164.308(a)(6)(ii) - Security Incident Procedures."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            # Run the pipeline
            logger.info(f"Executing pipeline with query: {user_query[:100]}...")
            
            # Step 1: Intent classification
            from app.agents.nodes import intent_classifier_node
            result = intent_classifier_node(initial_state)
            logger.info(f"  ✓ Intent: {result.get('intent')}")
            
            # Step 2: Profile resolution with data source selection
            from app.agents.nodes import profile_resolver_node
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            logger.info(f"  ✓ Data sources: {result.get('selected_data_sources', [])}")
            
            # Step 2b: If checkpoint created for focus areas, simulate selection
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            else:
                logger.warning("  ⚠️  No checkpoint created for focus areas - checking if already resolved")
                if not result.get("resolved_focus_areas"):
                    logger.warning("  ⚠️  Focus areas not resolved - may need to check data sources or framework_id")
            
            logger.info(f"  ✓ Focus areas: {len(result.get('resolved_focus_areas', []))}")
            logger.info(f"  ✓ Categories: {result.get('focus_area_categories', [])}")
            
            # Step 4: Metrics recommendation
            from app.agents.nodes import metrics_recommender_node
            result = metrics_recommender_node(result)
            logger.info(f"  ✓ Metrics resolved: {len(result.get('resolved_metrics', []))}")
            
            # Step 5: Calculation planning
            from app.agents.dt_nodes import calculation_planner_node
            result = calculation_planner_node(result)
            logger.info(f"  ✓ Calculation plan generated: {result.get('calculation_plan') is not None}")
            
            # Step 6: Dashboard generation
            from app.agents.nodes import dashboard_generator_node
            result = dashboard_generator_node(result)
            
            # Validate results
            validation_results = self.validate_dashboard_output(result)
            
            # Save output
            self.save_test_output("hipaa_risk_dashboard", result, validation_results)
            
            return {
                "test_name": "hipaa_risk_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return {
                "test_name": "hipaa_risk_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_soc2_vulnerability_dashboard(self) -> Dict[str, Any]:
        """
        Test: SOC2 Vulnerability Dashboard
        
        Use Case: Show SOC2 vulnerability management compliance posture with trends.
        Based on conversational_compliance_usecase.md.
        """
        logger.info("=" * 80)
        logger.info("TEST: SOC2 Vulnerability Dashboard")
        logger.info("=" * 80)
        
        user_query = (
            "Show me my SOC2 vulnerability management compliance posture with trends. "
            "I need a dashboard with KPIs and time-series metrics for CC6.1 and CC7.2."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            from app.agents.nodes import (
                intent_classifier_node,
                profile_resolver_node,
                metrics_recommender_node,
                dashboard_generator_node
            )
            from app.agents.dt_nodes import (
                calculation_planner_node,
            )
            
            # Execute pipeline
            result = intent_classifier_node(initial_state)
            logger.info(f"  ✓ Framework ID: {result.get('framework_id')}")
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            else:
                logger.warning("  ⚠️  No checkpoint created - checking focus areas")
                if not result.get("resolved_focus_areas"):
                    logger.warning("  ⚠️  Focus areas not resolved")
            result = metrics_recommender_node(result)
            result = calculation_planner_node(result)
            result = dashboard_generator_node(result)
            
            validation_results = self.validate_dashboard_output(result)
            self.save_test_output("soc2_vulnerability_dashboard", result, validation_results)
            
            return {
                "test_name": "soc2_vulnerability_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "soc2_vulnerability_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_hipaa_breach_detection_dashboard(self) -> Dict[str, Any]:
        """
        Test: HIPAA Breach Detection Dashboard
        
        Use Case: Dashboard for monitoring breach detection controls.
        Based on compliance_usecases.md - Phase 4: Auto-Generate Artifacts.
        """
        logger.info("=" * 80)
        logger.info("TEST: HIPAA Breach Detection Dashboard")
        logger.info("=" * 80)
        
        user_query = (
            "Build a dashboard for HIPAA breach detection monitoring. "
            "I need to track controls AM-5 (MFA), IR-8 (EDR), and AU-12 (Logging) "
            "with real-time metrics showing compliance status and risk levels."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            from app.agents.nodes import (
                intent_classifier_node,
                profile_resolver_node,
                metrics_recommender_node,
                dashboard_generator_node
            )
            from app.agents.dt_nodes import (
                calculation_planner_node,
            )
            
            result = intent_classifier_node(initial_state)
            logger.info(f"  ✓ Framework ID: {result.get('framework_id')}")
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            else:
                logger.warning("  ⚠️  No checkpoint created - checking focus areas")
                if not result.get("resolved_focus_areas"):
                    logger.warning("  ⚠️  Focus areas not resolved")
            result = metrics_recommender_node(result)
            result = calculation_planner_node(result)
            result = dashboard_generator_node(result)
            
            validation_results = self.validate_dashboard_output(result)
            self.save_test_output("hipaa_breach_detection_dashboard", result, validation_results)
            
            return {
                "test_name": "hipaa_breach_detection_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "hipaa_breach_detection_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_risk_control_mapping_dashboard(self) -> Dict[str, Any]:
        """
        Test: Risk Control Mapping Dashboard
        
        Use Case: Dashboard showing risk-to-control mappings with vulnerability data.
        Based on compliance_usecases.md - Phase 1: Requirement → Risk → Control Mapping.
        """
        logger.info("=" * 80)
        logger.info("TEST: Risk Control Mapping Dashboard")
        logger.info("=" * 80)
        
        user_query = (
            "Create a dashboard showing risk-to-control mappings for HIPAA. "
            "I need to see how vulnerabilities map to controls AM-5, IR-8, and AU-12, "
            "with asset management data showing coverage gaps."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            from app.agents.nodes import (
                intent_classifier_node,
                profile_resolver_node,
                metrics_recommender_node,
                dashboard_generator_node
            )
            from app.agents.dt_nodes import (
                calculation_planner_node,
            )
            
            result = intent_classifier_node(initial_state)
            logger.info(f"  ✓ Framework ID: {result.get('framework_id')}")
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            else:
                logger.warning("  ⚠️  No checkpoint created - checking focus areas")
                if not result.get("resolved_focus_areas"):
                    logger.warning("  ⚠️  Focus areas not resolved")
            result = metrics_recommender_node(result)
            result = calculation_planner_node(result)
            result = dashboard_generator_node(result)
            
            validation_results = self.validate_dashboard_output(result)
            self.save_test_output("risk_control_mapping_dashboard", result, validation_results)
            
            return {
                "test_name": "risk_control_mapping_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "risk_control_mapping_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_conversational_dashboard_flow(self) -> Dict[str, Any]:
        """
        Test: Conversational Dashboard Flow
        
        Use Case: Simulate the conversational flow from conversational_compliance_usecase.md.
        User asks for dashboard, agent recommends tools, user selects all.
        """
        logger.info("=" * 80)
        logger.info("TEST: Conversational Dashboard Flow")
        logger.info("=" * 80)
        
        user_query = (
            "I need to build a dashboard for HIPAA compliance. "
            "Our auditor is coming in 3 weeks and wants to see our security monitoring. "
            "Show me vulnerability and asset management risks."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            from app.agents.nodes import (
                intent_classifier_node,
                profile_resolver_node,
                metrics_recommender_node,
                dashboard_generator_node
            )
            from app.agents.dt_nodes import (
                calculation_planner_node,
            )
            
            # Step-by-step execution with logging
            logger.info("Step 1: Intent Classification")
            result = intent_classifier_node(initial_state)
            intent = result.get("intent")
            logger.info(f"  ✓ Intent: {intent}")
            
            logger.info("Step 2: Profile Resolution (with data source recommendations)")
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            selected_sources = result.get("selected_data_sources", [])
            logger.info(f"  ✓ Selected data sources: {selected_sources}")
            
            logger.info("Step 3: Focus Area Resolution")
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            else:
                logger.warning("  ⚠️  No checkpoint created - checking focus areas")
            focus_areas = result.get("resolved_focus_areas", [])
            logger.info(f"  ✓ Resolved focus areas: {len(focus_areas)}")
            logger.info(f"  ✓ Categories: {result.get('focus_area_categories', [])}")
            if focus_areas:
                logger.info(f"  ✓ Sample focus area: {focus_areas[0].get('name', 'unknown')} (categories: {focus_areas[0].get('categories', [])})")
            
            logger.info("Step 4: Metrics Recommendation")
            result = metrics_recommender_node(result)
            metrics = result.get("resolved_metrics", [])
            logger.info(f"  ✓ Resolved metrics: {len(metrics)}")
            
            logger.info("Step 5: Calculation Planning")
            result = calculation_planner_node(result)
            calc_plan = result.get("calculation_plan")
            logger.info(f"  ✓ Calculation plan: {calc_plan is not None}")
            
            logger.info("Step 6: Dashboard Generation")
            result = dashboard_generator_node(result)
            dashboards = result.get("dashboards", [])
            logger.info(f"  ✓ Dashboards generated: {len(dashboards)}")
            
            validation_results = self.validate_dashboard_output(result)
            self.save_test_output("conversational_dashboard_flow", result, validation_results)
            
            return {
                "test_name": "conversational_dashboard_flow",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "conversational_dashboard_flow",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_dashboard_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the dashboard output against expected criteria."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent was classified as dashboard_generation
        intent = result.get("intent")
        validation["checks"]["intent_classified"] = intent == "dashboard_generation"
        if intent != "dashboard_generation":
            validation["issues"].append(f"Intent should be 'dashboard_generation', got '{intent}'")
            validation["overall_success"] = False
        
        # Check 2: Profile was resolved
        compliance_profile = result.get("compliance_profile")
        selected_data_sources = result.get("selected_data_sources", [])
        validation["checks"]["profile_resolved"] = (
            compliance_profile is not None or len(selected_data_sources) > 0
        )
        if not validation["checks"]["profile_resolved"]:
            validation["issues"].append("Profile was not resolved")
        
        # Check 3: Data sources were selected (all recommended)
        validation["checks"]["data_sources_selected"] = len(selected_data_sources) > 0
        if not validation["checks"]["data_sources_selected"]:
            validation["issues"].append("No data sources were selected")
        else:
            logger.info(f"  ✓ Data sources selected: {len(selected_data_sources)}")
        
        # Check 4: Focus areas were resolved
        resolved_focus_areas = result.get("resolved_focus_areas", [])
        focus_area_categories = result.get("focus_area_categories", [])
        validation["checks"]["focus_areas_resolved"] = (
            len(resolved_focus_areas) > 0 or len(focus_area_categories) > 0
        )
        if not validation["checks"]["focus_areas_resolved"]:
            validation["issues"].append("Focus areas were not resolved")
        else:
            logger.info(f"  ✓ Focus areas resolved: {len(resolved_focus_areas)}")
            logger.info(f"  ✓ Categories: {focus_area_categories}")
        
        # Check 5: Focus area categories match expected (flexible - can be "assets", "inventory", or "asset_management")
        expected_categories = ["vulnerabilities"]
        asset_categories = ["assets", "inventory", "asset_management"]
        validation["checks"]["has_vulnerabilities"] = "vulnerabilities" in focus_area_categories
        validation["checks"]["has_asset_category"] = any(cat in focus_area_categories for cat in asset_categories)
        validation["checks"]["correct_categories"] = (
            validation["checks"]["has_vulnerabilities"] and validation["checks"]["has_asset_category"]
        )
        if not validation["checks"]["correct_categories"]:
            validation["issues"].append(
                f"Expected categories to include 'vulnerabilities' and one of {asset_categories}, got {focus_area_categories}"
            )
        
        # Check 6: Metrics resolved
        resolved_metrics = result.get("resolved_metrics", [])
        validation["checks"]["metrics_resolved"] = len(resolved_metrics) > 0
        if not validation["checks"]["metrics_resolved"]:
            validation["issues"].append("Metrics were not resolved")
        else:
            logger.info(f"  ✓ Metrics resolved: {len(resolved_metrics)}")
        
        # Check 7: Calculation plan generated
        calculation_plan = result.get("calculation_plan")
        validation["checks"]["calculation_plan_generated"] = calculation_plan is not None
        if calculation_plan:
            field_instructions = calculation_plan.get("field_instructions", [])
            metric_instructions = calculation_plan.get("metric_instructions", [])
            validation["checks"]["calculation_plan_has_instructions"] = (
                len(field_instructions) > 0 or len(metric_instructions) > 0
            )
            if validation["checks"]["calculation_plan_has_instructions"]:
                logger.info(f"  ✓ Calculation plan: {len(field_instructions)} fields, {len(metric_instructions)} metrics")
        
        # Check 8: Dashboards generated
        dashboards = result.get("dashboards", [])
        validation["checks"]["dashboards_generated"] = len(dashboards) > 0
        if not validation["checks"]["dashboards_generated"]:
            validation["issues"].append("No dashboards were generated")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Dashboards generated: {len(dashboards)}")
            for dashboard in dashboards:
                has_spec = "dashboard_spec" in dashboard or "specification" in dashboard
                validation["checks"]["dashboard_has_spec"] = has_spec
                if not has_spec:
                    validation["issues"].append(f"Dashboard missing spec: {dashboard.get('name', 'unnamed')}")
        
        # Check 9: No critical errors
        error = result.get("error")
        validation["checks"]["no_errors"] = error is None
        if error:
            validation["issues"].append(f"Pipeline error: {error}")
            validation["overall_success"] = False
        
        # Update overall success based on critical checks
        critical_checks = [
            "intent_classified",
            "data_sources_selected",
            "focus_areas_resolved",
            "metrics_resolved",
            "dashboards_generated",
            "no_errors"
        ]
        
        for check in critical_checks:
            if not validation["checks"].get(check, False):
                validation["overall_success"] = False
        
        return validation
    
    def save_test_output(self, test_name: str, result: Dict[str, Any], validation: Dict[str, Any]):
        """Save test output to JSON file in tests/output directory."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"{test_name}_{timestamp}.json"
        
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
        
        logger.info(f"  ✓ Output saved to: {output_file}")
    
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
        logger.info("COMPLIANCE RISK MAP DASHBOARD TEST SUITE")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        # Run all tests
        tests = [
            ("HIPAA Risk Dashboard", self.test_hipaa_risk_dashboard),
            ("SOC2 Vulnerability Dashboard", self.test_soc2_vulnerability_dashboard),
            ("HIPAA Breach Detection Dashboard", self.test_hipaa_breach_detection_dashboard),
            ("Risk Control Mapping Dashboard", self.test_risk_control_mapping_dashboard),
            ("Conversational Dashboard Flow", self.test_conversational_dashboard_flow),
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
        summary_file = self.output_dir / f"test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
        description="Test compliance risk mapping and dashboard generation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--test',
        choices=['all', 'hipaa_risk', 'soc2_vuln', 'hipaa_breach', 'risk_control', 'conversational'],
        default='all',
        help='Which test to run'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = ComplianceRiskMapDashboardTester()
    results = None
    
    if args.test == 'all':
        results = tester.run_all_tests()
    elif args.test == 'hipaa_risk':
        tester.setup()
        result = tester.test_hipaa_risk_dashboard()
        tester.print_summary({"HIPAA Risk Dashboard": result})
        results = {"results": result}
    elif args.test == 'soc2_vuln':
        tester.setup()
        result = tester.test_soc2_vulnerability_dashboard()
        tester.print_summary({"SOC2 Vulnerability Dashboard": result})
        results = {"results": result}
    elif args.test == 'hipaa_breach':
        tester.setup()
        result = tester.test_hipaa_breach_detection_dashboard()
        tester.print_summary({"HIPAA Breach Detection Dashboard": result})
        results = {"results": result}
    elif args.test == 'risk_control':
        tester.setup()
        result = tester.test_risk_control_mapping_dashboard()
        tester.print_summary({"Risk Control Mapping Dashboard": result})
        results = {"results": result}
    elif args.test == 'conversational':
        tester.setup()
        result = tester.test_conversational_dashboard_flow()
        tester.print_summary({"Conversational Dashboard Flow": result})
        results = {"results": result}
    
    if results:
        logger.info(f"\nAll outputs saved to: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
