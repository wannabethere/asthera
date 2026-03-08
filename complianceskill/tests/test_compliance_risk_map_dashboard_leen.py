#!/usr/bin/env python3
"""
Test suite for compliance risk mapping and dashboard generation - LEEN Request Scenarios.

This test validates the complete compliance-to-operations pipeline with leen-specific flags:
- is_leen_request=True: Enables format conversion to planner-compatible outputs
- silver_gold_tables_only=True: Filters to only use silver and gold tables (skips source/bronze)

Test Cases (mirrors test_compliance_risk_map_dashboard.py but with leen flags):
1. HIPAA Risk Dashboard (with leen format conversion)
2. SOC2 Vulnerability Dashboard (with leen format conversion)
3. HIPAA Breach Detection Dashboard (with leen format conversion)

Based on use cases from:
- docs/compliance_usecases.md
- docs/conversational_compliance_usecase.md

Uses .env configuration for ChromaDB settings.
Generates output in tests/output/leen_* directories for comparison.
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

from app.agents.detectiontriageworkflows.workflow import create_compliance_app
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


class ComplianceRiskMapDashboardLeenTester:
    """Test suite for compliance risk mapping and dashboard generation with LEEN flags."""
    
    def __init__(self):
        self.app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_dir = OUTPUT_DIR
    
    def setup(self):
        """Initialize the compliance app."""
        logger.info("Setting up compliance pipeline app (LEEN mode)...")
        self.app = create_compliance_app(checkpointer=self.checkpointer)
        logger.info("✓ Compliance app initialized (LEEN mode)")
    
    def create_initial_state(self, user_query: str) -> EnhancedCompliancePipelineState:
        """Create initial state for the pipeline with LEEN flags enabled."""
        state = {
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
            
            # LEEN-specific flags
            "is_leen_request": True,
            "silver_gold_tables_only": True,
            
            # LEEN output fields
            "goal_metric_definitions": [],
            "goal_metrics": [],
            "planner_siem_rules": [],
            "planner_metric_recommendations": [],
            "planner_execution_plan": {},
            "planner_medallion_plan": {},
        }
        
        logger.info("  ✓ LEEN flags enabled: is_leen_request=True, silver_gold_tables_only=True")
        return state
    
    def simulate_data_source_selection(self, state: EnhancedCompliancePipelineState, select_all: bool = True) -> EnhancedCompliancePipelineState:
        """Simulate user selecting all recommended data sources."""
        checkpoints = state.get("checkpoints", [])
        recommended = []
        
        for checkpoint in checkpoints:
            if checkpoint.get("type") == "profile_resolver_data_sources":
                recommended = checkpoint.get("data", {}).get("recommended_data_sources", [])
                break
        
        if not recommended:
            from app.config.focus_areas import get_all_supported_data_sources
            all_sources = get_all_supported_data_sources()
            recommended = [{"name": src} for src in all_sources]
        
        if select_all:
            selected = [src.get("name") if isinstance(src, dict) else src for src in recommended]
        else:
            selected = [src.get("name") if isinstance(src, dict) else src for src in recommended[:3]]
        
        state["user_checkpoint_input"] = {
            "checkpoint_type": "profile_resolver_data_sources",
            "selected_data_sources": selected
        }
        
        logger.info(f"  ✓ Simulated data source selection: {selected}")
        return state
    
    def simulate_focus_area_selection(self, state: EnhancedCompliancePipelineState, categories: List[str] = None) -> EnhancedCompliancePipelineState:
        """Simulate user selecting focus areas based on categories."""
        if categories is None:
            categories = ["vulnerabilities", "assets", "inventory"]
        
        checkpoints = state.get("checkpoints", [])
        all_focus_areas = state.get("resolved_focus_areas", [])
        
        for checkpoint in checkpoints:
            if checkpoint.get("type") == "profile_resolver_focus_areas":
                all_focus_areas = checkpoint.get("data", {}).get("all_available_focus_areas", all_focus_areas)
                break
        
        selected_focus_areas = []
        for fa in all_focus_areas:
            fa_categories = fa.get("categories", [])
            if any(cat in fa_categories for cat in categories):
                selected_focus_areas.append(fa.get("id") or fa.get("name"))
        
        if not selected_focus_areas:
            selected_focus_areas = [fa.get("id") or fa.get("name") for fa in all_focus_areas]
        
        state["user_checkpoint_input"] = {
            "checkpoint_type": "profile_resolver_focus_areas",
            "selected_focus_areas": selected_focus_areas
        }
        
        logger.info(f"  ✓ Simulated focus area selection: {len(selected_focus_areas)} areas for categories {categories}")
        return state
    
    def test_hipaa_risk_dashboard_leen(self) -> Dict[str, Any]:
        """
        Test: HIPAA Risk Dashboard Generation (LEEN Mode)
        
        Same as test_hipaa_risk_dashboard but with LEEN flags enabled.
        """
        logger.info("=" * 80)
        logger.info("TEST (LEEN): HIPAA Risk Dashboard Generation")
        logger.info("=" * 80)
        
        user_query = (
            "Show me my HIPAA compliance posture for vulnerability management and asset management. "
            "I need a dashboard with KPIs showing current state and trends for risks related to "
            "HIPAA §164.308(a)(6)(ii) - Security Incident Procedures."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            logger.info(f"Executing pipeline (LEEN mode) with query: {user_query[:100]}...")
            
            # Run the pipeline
            from app.agents.nodes import intent_classifier_node, profile_resolver_node, metrics_recommender_node, dashboard_generator_node
            from app.agents.shared import calculation_planner_node
            
            result = intent_classifier_node(initial_state)
            logger.info(f"  ✓ Intent: {result.get('intent')}")
            
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            logger.info(f"  ✓ Data sources: {result.get('selected_data_sources', [])}")
            
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            
            logger.info(f"  ✓ Focus areas: {len(result.get('resolved_focus_areas', []))}")
            
            result = metrics_recommender_node(result)
            logger.info(f"  ✓ Metrics resolved: {len(result.get('resolved_metrics', []))}")
            
            result = calculation_planner_node(result)
            logger.info(f"  ✓ Calculation plan generated")
            
            result = dashboard_generator_node(result)
            
            # Validate LEEN-specific outputs
            validation_results = self.validate_leen_dashboard_output(result)
            
            # Save output
            self.save_test_output("leen_hipaa_risk_dashboard", result, validation_results)
            
            return {
                "test_name": "leen_hipaa_risk_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return {
                "test_name": "leen_hipaa_risk_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_soc2_vulnerability_dashboard_leen(self) -> Dict[str, Any]:
        """
        Test: SOC2 Vulnerability Dashboard (LEEN Mode)
        
        Same as test_soc2_vulnerability_dashboard but with LEEN flags enabled.
        """
        logger.info("=" * 80)
        logger.info("TEST (LEEN): SOC2 Vulnerability Dashboard")
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
            from app.agents.shared import calculation_planner_node
            
            result = intent_classifier_node(initial_state)
            logger.info(f"  ✓ Framework ID: {result.get('framework_id')}")
            
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            
            if result.get("checkpoints"):
                logger.info(f"  ✓ Checkpoint created, simulating focus area selection")
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            
            result = metrics_recommender_node(result)
            result = calculation_planner_node(result)
            result = dashboard_generator_node(result)
            
            validation_results = self.validate_leen_dashboard_output(result)
            self.save_test_output("leen_soc2_vulnerability_dashboard", result, validation_results)
            
            return {
                "test_name": "leen_soc2_vulnerability_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "leen_soc2_vulnerability_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_hipaa_breach_detection_dashboard_leen(self) -> Dict[str, Any]:
        """
        Test: HIPAA Breach Detection Dashboard (LEEN Mode)
        
        Same as test_hipaa_breach_detection_dashboard but with LEEN flags enabled.
        """
        logger.info("=" * 80)
        logger.info("TEST (LEEN): HIPAA Breach Detection Dashboard")
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
            from app.agents.shared import calculation_planner_node
            
            result = intent_classifier_node(initial_state)
            result = self.simulate_data_source_selection(result, select_all=True)
            result = profile_resolver_node(result)
            
            if result.get("checkpoints"):
                result = self.simulate_focus_area_selection(result, categories=["vulnerabilities", "assets", "inventory"])
                result = profile_resolver_node(result)
            
            result = metrics_recommender_node(result)
            result = calculation_planner_node(result)
            result = dashboard_generator_node(result)
            
            validation_results = self.validate_leen_dashboard_output(result)
            self.save_test_output("leen_hipaa_breach_detection_dashboard", result, validation_results)
            
            return {
                "test_name": "leen_hipaa_breach_detection_dashboard",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "leen_hipaa_breach_detection_dashboard",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_leen_dashboard_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dashboard output with LEEN-specific checks."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: LEEN flags are set
        is_leen = result.get("is_leen_request", False)
        silver_gold_only = result.get("silver_gold_tables_only", False)
        validation["checks"]["leen_flags_set"] = is_leen and silver_gold_only
        if not validation["checks"]["leen_flags_set"]:
            validation["issues"].append("LEEN flags not set: is_leen_request or silver_gold_tables_only is False")
            validation["overall_success"] = False
        
        # Check 2: Intent classified
        intent = result.get("intent")
        validation["checks"]["intent_classified"] = intent is not None
        if not validation["checks"]["intent_classified"]:
            validation["issues"].append("Intent was not classified")
            validation["overall_success"] = False
        else:
            logger.info(f"  ✓ Intent: {intent}")
        
        # Check 3: Metrics resolved
        resolved_metrics = result.get("resolved_metrics", [])
        validation["checks"]["metrics_resolved"] = len(resolved_metrics) > 0
        if not validation["checks"]["metrics_resolved"]:
            validation["issues"].append("No metrics resolved")
        else:
            logger.info(f"  ✓ Metrics resolved: {len(resolved_metrics)}")
        
        # Check 4: Format converter ran (if metrics exist)
        if resolved_metrics:
            goal_metrics = result.get("goal_metrics", [])
            goal_metric_definitions = result.get("goal_metric_definitions", [])
            validation["checks"]["format_converter_ran"] = len(goal_metrics) > 0 or len(goal_metric_definitions) > 0
            if validation["checks"]["format_converter_ran"]:
                logger.info(f"  ✓ Format converter: {len(goal_metric_definitions)} definitions, {len(goal_metrics)} metrics")
        
        # Check 5: Dashboard assembled (if dashboard generation intent)
        if intent == "dashboard_generation":
            assembled_dashboard = result.get("dt_dashboard_assembled")
            validation["checks"]["dashboard_assembled"] = assembled_dashboard is not None
            if validation["checks"]["dashboard_assembled"]:
                components = assembled_dashboard.get("components", [])
                logger.info(f"  ✓ Dashboard assembled: {len(components)} components")
        
        # Check 6: Silver/gold tables only filtering
        # Note: This would be validated in MDL schema retrieval if it runs
        # For dashboard generation, we check if schemas are filtered
        resolved_schemas = result.get("dt_resolved_schemas", [])
        if resolved_schemas:
            all_silver_gold = all(
                "silver" in schema.get("table_name", "").lower() or
                "gold" in schema.get("table_name", "").lower()
                for schema in resolved_schemas
            )
            validation["checks"]["silver_gold_filtering"] = all_silver_gold
            if validation["checks"]["silver_gold_filtering"]:
                logger.info(f"  ✓ All {len(resolved_schemas)} schemas are silver/gold tables")
        
        # Check 7: No critical errors
        error = result.get("error")
        validation["checks"]["no_errors"] = error is None
        if error:
            validation["issues"].append(f"Pipeline error: {error}")
            validation["overall_success"] = False
        
        return validation
    
    def save_test_output(self, test_name: str, result: Dict[str, Any], validation: Dict[str, Any]):
        """Save test output to JSON file in tests/output/leen_* directory."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        leen_output_dir = self.output_dir / "leen_dashboard_tests"
        leen_output_dir.mkdir(parents=True, exist_ok=True)
        output_file = leen_output_dir / f"{test_name}_{timestamp}.json"
        
        # Sanitize result for JSON
        sanitized_result = self.sanitize_for_json(result)
        
        output_data = {
            "test_name": test_name,
            "timestamp": datetime.utcnow().isoformat(),
            "leen_flags": {
                "is_leen_request": result.get("is_leen_request", False),
                "silver_gold_tables_only": result.get("silver_gold_tables_only", False),
            },
            "validation": validation,
            "result": sanitized_result
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        logger.info(f"  ✓ Saved test output to: {output_file}")
        
        # Also save LEEN-specific outputs separately
        outputs_dir = leen_output_dir / f"{test_name}_{timestamp}_outputs"
        outputs_dir.mkdir(exist_ok=True)
        
        if result.get("goal_metric_definitions"):
            with open(outputs_dir / "goal_metric_definitions.json", 'w') as f:
                json.dump(result["goal_metric_definitions"], f, indent=2, default=str)
        
        if result.get("goal_metrics"):
            with open(outputs_dir / "goal_metrics.json", 'w') as f:
                json.dump(result["goal_metrics"], f, indent=2, default=str)
        
        if result.get("resolved_metrics"):
            with open(outputs_dir / "resolved_metrics.json", 'w') as f:
                json.dump(result["resolved_metrics"], f, indent=2, default=str)
        
        if result.get("dt_dashboard_assembled"):
            with open(outputs_dir / "dashboard_assembled.json", 'w') as f:
                json.dump(result["dt_dashboard_assembled"], f, indent=2, default=str)
    
    def sanitize_for_json(self, obj: Any, max_length: int = 10000) -> Any:
        """Sanitize object for JSON serialization, truncating large strings."""
        if isinstance(obj, dict):
            return {k: self.sanitize_for_json(v, max_length) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.sanitize_for_json(item, max_length) for item in obj[:100]]
        elif isinstance(obj, str) and len(obj) > max_length:
            return obj[:max_length] + f"... (truncated, original length: {len(obj)})"
        else:
            return obj
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all LEEN-specific dashboard tests and generate summary."""
        logger.info("=" * 80)
        logger.info("Running LEEN Dashboard Test Suite")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        tests = [
            ("LEEN HIPAA Risk Dashboard", self.test_hipaa_risk_dashboard_leen),
            ("LEEN SOC2 Vulnerability Dashboard", self.test_soc2_vulnerability_dashboard_leen),
            ("LEEN HIPAA Breach Detection Dashboard", self.test_hipaa_breach_detection_dashboard_leen),
        ]
        
        results = {}
        for test_name, test_func in tests:
            logger.info("")
            try:
                result = test_func()
                results[test_name] = result
                self.results.append(result)
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}", exc_info=True)
                results[test_name] = {
                    "test_name": test_name,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Generate summary
        total = len(results)
        passed = sum(1 for r in results.values() if r.get("success", False))
        failed = total - passed
        
        summary = {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Save summary
        summary_file = self.output_dir / "leen_dashboard_test_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("LEEN Dashboard Test Suite Summary")
        logger.info("=" * 80)
        logger.info(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        logger.info(f"Summary saved to: {summary_file}")
        
        return summary


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LEEN-specific dashboard tests")
    parser.add_argument(
        "--test",
        type=str,
        help="Run specific test (hipaa_risk, soc2_vulnerability, hipaa_breach, or all)",
        default="all"
    )
    
    args = parser.parse_args()
    
    tester = ComplianceRiskMapDashboardLeenTester()
    
    if args.test == "all":
        tester.run_all_tests()
    elif args.test == "hipaa_risk":
        tester.setup()
        tester.test_hipaa_risk_dashboard_leen()
    elif args.test == "soc2_vulnerability":
        tester.setup()
        tester.test_soc2_vulnerability_dashboard_leen()
    elif args.test == "hipaa_breach":
        tester.setup()
        tester.test_hipaa_breach_detection_dashboard_leen()
    else:
        logger.error(f"Unknown test: {args.test}")
        sys.exit(1)
