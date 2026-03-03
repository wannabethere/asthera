#!/usr/bin/env python3
"""
Test suite for CSOD Metrics, Tables, and KPIs Recommender Workflow.

This test validates the CSOD workflow pipeline for Cornerstone OnDemand and Workday integrations.

Test Cases:
1. Use Case 1: Metrics Recommender (metrics_recommender_with_gold_plan)
2. Use Case 2: Metrics Dashboard Plan (metrics_dashboard_plan)
3. Use Case 3: Dashboard Generation for Persona (dashboard_generation_for_persona)
4. Use Case 4: Compliance Test Generator (compliance_test_generator)

Configuration:
- Data Sources: cornerstone.lms, workday.hcm
- Gold Standard Project ID: csod_project
- Metrics Registry: lms_dashboard_metrics_registry
- Focus Areas: ld_training, ld_operations, compliance_training

Uses .env configuration for LLM and vector store settings.
Generates output in tests/outputs/csod_* directories for comparison.
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

from app.agents.csod.csod_workflow import (
    get_csod_app,
    create_csod_initial_state,
)
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

# Create output directory structure: tests/outputs/csod_testcase_name/timestamp/
OUTPUT_BASE_DIR = base_dir / "tests" / "outputs"
OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Constants
GOLD_STANDARD_PROJECT_ID = "csod_project"
DATA_SOURCES = ["cornerstone.lms", "workday.hcm"]


class CSODWorkflowTester:
    """Test suite for CSOD Metrics, Tables, and KPIs Recommender workflow."""
    
    def __init__(self, output_base_dir: Path = None):
        self.app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_base_dir = output_base_dir or OUTPUT_BASE_DIR
        self.current_test_output_dir = None
        self.skip_slow = False
    
    def setup(self):
        """Initialize the CSOD workflow app."""
        logger.info("Setting up CSOD workflow app...")
        self.app = get_csod_app()
        logger.info("✓ CSOD workflow app initialized")
        logger.info(f"  Nodes: {list(self.app.nodes.keys())}")
    
    def create_initial_state(
        self,
        user_query: str,
        selected_data_sources: List[str] = None,
    ) -> Dict[str, Any]:
        """Create initial state for the CSOD workflow."""
        state = create_csod_initial_state(
            user_query=user_query,
            session_id=str(uuid.uuid4()),
            active_project_id=GOLD_STANDARD_PROJECT_ID,
            selected_data_sources=selected_data_sources or DATA_SOURCES,
            compliance_profile=None,
            silver_gold_tables_only=False,
        )
        
        logger.info(f"  ✓ Initial state created with {len(selected_data_sources or DATA_SOURCES)} data sources")
        return state
    
    def test_use_case_1_metrics_recommender_with_gold_plan(self) -> Dict[str, Any]:
        """
        Test: Use Case 1 - Metrics Recommender with Gold Plan
        
        Intent: metrics_recommender_with_gold_plan
        
        Expected outputs:
        - csod_metric_recommendations
        - csod_kpi_recommendations
        - csod_table_recommendations
        - csod_data_science_insights
        - csod_medallion_plan
        - calculation_plan (field_instructions, metric_instructions)
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 1 - Metrics Recommender with Gold Plan")
        logger.info("=" * 80)
        
        user_query = (
            "I need metrics recommendations for training completion tracking in Cornerstone. "
            "Generate a gold model plan for the recommended metrics."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            selected_data_sources=["cornerstone.lms"],
        )
        
        try:
            logger.info(f"Executing CSOD workflow with query: {user_query[:100]}...")
            
            # Run full workflow with timeout protection
            final_state = None
            max_iterations = 50  # Safety limit to prevent infinite loops
            iteration_count = 0
            
            for event in self.app.stream(initial_state, self.config):
                node_name = list(event.keys())[0]
                node_output = event[node_name]
                logger.info(f"  → {node_name} (iteration {iteration_count + 1})")
                final_state = node_output
                iteration_count += 1
                
                # Safety check: prevent infinite loops
                if iteration_count >= max_iterations:
                    logger.error(f"Workflow exceeded {max_iterations} iterations - possible infinite loop!")
                    logger.error(f"Last node: {node_name}, State keys: {list(final_state.keys())[:10]}")
                    raise RuntimeError(f"Workflow exceeded {max_iterations} iterations - possible infinite loop in node: {node_name}")
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate CSOD-specific outputs
            validation_results = self.validate_csod_outputs(final_state, expected_intent="metrics_recommender_with_gold_plan")
            self.get_test_output_dir("csod_use_case_1_metrics_recommender_gold")
            self.save_test_output("csod_use_case_1_metrics_recommender_gold", final_state, validation_results)
            
            return {
                "test_name": "csod_use_case_1_metrics_recommender_gold",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "csod_use_case_1_metrics_recommender_gold",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_2_metrics_dashboard_plan(self) -> Dict[str, Any]:
        """
        Test: Use Case 2 - Metrics Dashboard Plan
        
        Intent: metrics_dashboard_plan
        
        Expected outputs:
        - csod_metric_recommendations
        - csod_kpi_recommendations
        - csod_data_science_insights
        - calculation_plan
        - csod_dashboard_assembled (if dashboard generator runs)
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 2 - Metrics Dashboard Plan")
        logger.info("=" * 80)
        
        user_query = (
            "Create a metrics dashboard plan for learning and development operations. "
            "I need to track training costs, completion rates, and learner engagement."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing CSOD workflow with query: {user_query[:100]}...")
            
            # Run full workflow with timeout protection
            final_state = None
            max_iterations = 50
            iteration_count = 0
            
            for event in self.app.stream(initial_state, self.config):
                node_name = list(event.keys())[0]
                node_output = event[node_name]
                logger.info(f"  → {node_name} (iteration {iteration_count + 1})")
                final_state = node_output
                iteration_count += 1
                
                if iteration_count >= max_iterations:
                    logger.error(f"Workflow exceeded {max_iterations} iterations - possible infinite loop!")
                    raise RuntimeError(f"Workflow exceeded {max_iterations} iterations")
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate outputs
            validation_results = self.validate_csod_outputs(final_state, expected_intent="metrics_dashboard_plan")
            self.get_test_output_dir("csod_use_case_2_metrics_dashboard_plan")
            self.save_test_output("csod_use_case_2_metrics_dashboard_plan", final_state, validation_results)
            
            return {
                "test_name": "csod_use_case_2_metrics_dashboard_plan",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "csod_use_case_2_metrics_dashboard_plan",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_3_dashboard_generation_for_persona(self) -> Dict[str, Any]:
        """
        Test: Use Case 3 - Dashboard Generation for Persona
        
        Intent: dashboard_generation_for_persona
        
        Expected outputs:
        - csod_dashboard_assembled
        - csod_data_science_insights (for dashboard metrics)
        - calculation_plan (for dashboard metrics)
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 3 - Dashboard Generation for Persona")
        logger.info("=" * 80)
        
        user_query = (
            "Generate a dashboard for a learning manager persona. "
            "The dashboard should show training completion rates, learner progress, "
            "and compliance training status for their team."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            selected_data_sources=["cornerstone.lms"],
        )
        
        try:
            logger.info(f"Executing CSOD workflow with query: {user_query[:100]}...")
            
            # Run full workflow
            final_state = None
            max_iterations = 50
            iteration_count = 0
            
            for event in self.app.stream(initial_state, self.config):
                node_name = list(event.keys())[0]
                node_output = event[node_name]
                logger.info(f"  → {node_name} (iteration {iteration_count + 1})")
                final_state = node_output
                iteration_count += 1
                
                if iteration_count >= max_iterations:
                    logger.error(f"Workflow exceeded {max_iterations} iterations!")
                    raise RuntimeError(f"Workflow exceeded {max_iterations} iterations")
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate outputs
            validation_results = self.validate_csod_outputs(final_state, expected_intent="dashboard_generation_for_persona")
            self.get_test_output_dir("csod_use_case_3_dashboard_persona")
            self.save_test_output("csod_use_case_3_dashboard_persona", final_state, validation_results)
            
            return {
                "test_name": "csod_use_case_3_dashboard_persona",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "csod_use_case_3_dashboard_persona",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_4_compliance_test_generator(self) -> Dict[str, Any]:
        """
        Test: Use Case 4 - Compliance Test Generator
        
        Intent: compliance_test_generator
        
        Expected outputs:
        - csod_test_cases
        - csod_test_queries
        - csod_test_validation_passed
        """
        logger.info("=" * 80)
        logger.info("TEST: Use Case 4 - Compliance Test Generator")
        logger.info("=" * 80)
        
        user_query = (
            "Generate compliance test cases and SQL alert queries for training completion monitoring. "
            "I need to ensure all mandatory training is completed on time."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            selected_data_sources=["cornerstone.lms"],
        )
        
        try:
            logger.info(f"Executing CSOD workflow with query: {user_query[:100]}...")
            
            # Run full workflow
            final_state = None
            max_iterations = 50
            iteration_count = 0
            
            for event in self.app.stream(initial_state, self.config):
                node_name = list(event.keys())[0]
                node_output = event[node_name]
                logger.info(f"  → {node_name} (iteration {iteration_count + 1})")
                final_state = node_output
                iteration_count += 1
                
                if iteration_count >= max_iterations:
                    logger.error(f"Workflow exceeded {max_iterations} iterations!")
                    raise RuntimeError(f"Workflow exceeded {max_iterations} iterations")
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate outputs
            validation_results = self.validate_csod_outputs(final_state, expected_intent="compliance_test_generator")
            self.get_test_output_dir("csod_use_case_4_compliance_test")
            self.save_test_output("csod_use_case_4_compliance_test", final_state, validation_results)
            
            return {
                "test_name": "csod_use_case_4_compliance_test",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "csod_use_case_4_compliance_test",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_csod_outputs(self, result: Dict[str, Any], expected_intent: str = None) -> Dict[str, Any]:
        """Validate CSOD-specific outputs."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent classification
        csod_intent = result.get("csod_intent")
        if expected_intent:
            validation["checks"]["intent_correct"] = csod_intent == expected_intent
            if not validation["checks"]["intent_correct"]:
                validation["issues"].append(f"Intent mismatch: expected {expected_intent}, got {csod_intent}")
                validation["overall_success"] = False
        else:
            validation["checks"]["intent_correct"] = csod_intent is not None
            if not validation["checks"]["intent_correct"]:
                validation["issues"].append("Intent not classified")
        
        # Check 2: Metrics recommendations (for metrics-related intents)
        if expected_intent in ("metrics_recommender_with_gold_plan", "metrics_dashboard_plan"):
            metric_recommendations = result.get("csod_metric_recommendations", [])
            kpi_recommendations = result.get("csod_kpi_recommendations", [])
            table_recommendations = result.get("csod_table_recommendations", [])
            
            validation["checks"]["has_metric_recommendations"] = len(metric_recommendations) > 0
            validation["checks"]["has_kpi_recommendations"] = len(kpi_recommendations) > 0
            validation["checks"]["has_table_recommendations"] = len(table_recommendations) > 0
            
            if not validation["checks"]["has_metric_recommendations"]:
                validation["issues"].append("No metric recommendations generated")
                validation["overall_success"] = False
            else:
                logger.info(f"  ✓ Generated {len(metric_recommendations)} metrics, {len(kpi_recommendations)} KPIs, {len(table_recommendations)} tables")
        
        # Check 3: Data science insights (for metrics-related intents)
        if expected_intent in ("metrics_recommender_with_gold_plan", "metrics_dashboard_plan", "dashboard_generation_for_persona"):
            data_science_insights = result.get("csod_data_science_insights", [])
            validation["checks"]["has_data_science_insights"] = len(data_science_insights) > 0
            if not validation["checks"]["has_data_science_insights"]:
                validation["issues"].append("No data science insights generated")
            else:
                logger.info(f"  ✓ Generated {len(data_science_insights)} data science insights")
        
        # Check 4: Medallion plan (for gold plan intent)
        if expected_intent == "metrics_recommender_with_gold_plan":
            medallion_plan = result.get("csod_medallion_plan", {})
            validation["checks"]["has_medallion_plan"] = bool(medallion_plan) and medallion_plan.get("requires_gold_model", False)
            if not validation["checks"]["has_medallion_plan"]:
                validation["issues"].append("Medallion plan not generated or does not require gold model")
            else:
                logger.info(f"  ✓ Medallion plan generated with {len(medallion_plan.get('specifications', []))} specifications")
        
        # Check 5: Calculation plan (for metrics-related intents)
        if expected_intent in ("metrics_recommender_with_gold_plan", "metrics_dashboard_plan", "dashboard_generation_for_persona"):
            calculation_plan = result.get("calculation_plan", {})
            field_instructions = calculation_plan.get("field_instructions", [])
            metric_instructions = calculation_plan.get("metric_instructions", [])
            
            validation["checks"]["has_calculation_plan"] = len(field_instructions) > 0 or len(metric_instructions) > 0
            if not validation["checks"]["has_calculation_plan"]:
                validation["issues"].append("Calculation plan not generated")
            else:
                logger.info(f"  ✓ Calculation plan: {len(field_instructions)} field instructions, {len(metric_instructions)} metric instructions")
        
        # Check 6: Dashboard (for dashboard intent)
        if expected_intent == "dashboard_generation_for_persona":
            dashboard_assembled = result.get("csod_dashboard_assembled")
            validation["checks"]["has_dashboard"] = dashboard_assembled is not None
            if not validation["checks"]["has_dashboard"]:
                validation["issues"].append("Dashboard not generated")
                validation["overall_success"] = False
            else:
                logger.info("  ✓ Dashboard generated")
        
        # Check 7: Test cases (for compliance test intent)
        if expected_intent == "compliance_test_generator":
            test_cases = result.get("csod_test_cases", [])
            test_queries = result.get("csod_test_queries", [])
            
            validation["checks"]["has_test_cases"] = len(test_cases) > 0
            validation["checks"]["has_test_queries"] = len(test_queries) > 0
            
            if not validation["checks"]["has_test_cases"]:
                validation["issues"].append("No test cases generated")
                validation["overall_success"] = False
            else:
                logger.info(f"  ✓ Generated {len(test_cases)} test cases, {len(test_queries)} test queries")
        
        # Check 8: Resolved schemas
        resolved_schemas = result.get("csod_resolved_schemas", [])
        validation["checks"]["has_resolved_schemas"] = len(resolved_schemas) > 0
        if not validation["checks"]["has_resolved_schemas"]:
            validation["issues"].append("No resolved schemas found")
        else:
            logger.info(f"  ✓ Resolved {len(resolved_schemas)} schemas")
        
        return validation
    
    def get_test_output_dir(self, test_name: str) -> Path:
        """Create and return test-specific output directory: tests/outputs/csod_testcase_name/timestamp/"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_output_dir = self.output_base_dir / test_name / timestamp
        test_output_dir.mkdir(parents=True, exist_ok=True)
        self.current_test_output_dir = test_output_dir
        return test_output_dir
    
    def save_test_output(self, test_name: str, result: Dict[str, Any], validation: Dict[str, Any]):
        """Save test output with CSOD-specific fields."""
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
                "csod_persona": output_data["result"].get("csod_persona"),
                "active_project_id": output_data["result"].get("active_project_id"),
                "selected_data_sources": output_data["result"].get("selected_data_sources", []),
                "csod_resolved_schemas_count": len(output_data["result"].get("csod_resolved_schemas", [])),
                "csod_metric_recommendations_count": len(output_data["result"].get("csod_metric_recommendations", [])),
                "csod_kpi_recommendations_count": len(output_data["result"].get("csod_kpi_recommendations", [])),
                "csod_table_recommendations_count": len(output_data["result"].get("csod_table_recommendations", [])),
                "csod_data_science_insights_count": len(output_data["result"].get("csod_data_science_insights", [])),
                "has_medallion_plan": bool(output_data["result"].get("csod_medallion_plan", {})),
                "has_calculation_plan": bool(output_data["result"].get("calculation_plan", {})),
                "has_dashboard": output_data["result"].get("csod_dashboard_assembled") is not None,
                "csod_test_cases_count": len(output_data["result"].get("csod_test_cases", [])),
                "csod_test_queries_count": len(output_data["result"].get("csod_test_queries", [])),
            }
            with open(outputs_dir / "state_snapshot.json", 'w') as f:
                json.dump(state_snapshot, f, indent=2, default=str)
            
            # Save CSOD-specific outputs
            if output_data["result"].get("csod_metric_recommendations"):
                with open(outputs_dir / "metric_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["csod_metric_recommendations"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_kpi_recommendations"):
                with open(outputs_dir / "kpi_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["csod_kpi_recommendations"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_table_recommendations"):
                with open(outputs_dir / "table_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["csod_table_recommendations"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_data_science_insights"):
                with open(outputs_dir / "data_science_insights.json", 'w') as f:
                    json.dump(output_data["result"]["csod_data_science_insights"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_medallion_plan"):
                with open(outputs_dir / "medallion_plan.json", 'w') as f:
                    json.dump(output_data["result"]["csod_medallion_plan"], f, indent=2, default=str)
            
            if output_data["result"].get("calculation_plan"):
                with open(outputs_dir / "calculation_plan.json", 'w') as f:
                    json.dump(output_data["result"]["calculation_plan"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_dashboard_assembled"):
                with open(outputs_dir / "dashboard.json", 'w') as f:
                    json.dump(output_data["result"]["csod_dashboard_assembled"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_test_cases"):
                with open(outputs_dir / "test_cases.json", 'w') as f:
                    json.dump(output_data["result"]["csod_test_cases"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_test_queries"):
                with open(outputs_dir / "test_queries.json", 'w') as f:
                    json.dump(output_data["result"]["csod_test_queries"], f, indent=2, default=str)
            
            if output_data["result"].get("csod_resolved_schemas"):
                with open(outputs_dir / "resolved_schemas.json", 'w') as f:
                    json.dump(output_data["result"]["csod_resolved_schemas"], f, indent=2, default=str)
        
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
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all CSOD workflow tests and generate summary."""
        logger.info("=" * 80)
        logger.info("Running CSOD Workflow Test Suite")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        # Run CSOD use cases
        tests = [
            ("CSOD Use Case 1: Metrics Recommender with Gold Plan", self.test_use_case_1_metrics_recommender_with_gold_plan),
            ("CSOD Use Case 2: Metrics Dashboard Plan", self.test_use_case_2_metrics_dashboard_plan),
            ("CSOD Use Case 3: Dashboard Generation for Persona", self.test_use_case_3_dashboard_generation_for_persona),
            ("CSOD Use Case 4: Compliance Test Generator", self.test_use_case_4_compliance_test_generator),
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
        summary_file = self.output_base_dir / "csod_test_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("CSOD Test Suite Summary")
        logger.info("=" * 80)
        logger.info(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        logger.info(f"Summary saved to: {summary_file}")
        
        return summary


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run CSOD workflow tests")
    parser.add_argument(
        "--test",
        type=str,
        help="Run specific test (use_case_1, use_case_2, use_case_3, use_case_4, or all)",
        default="all"
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow operations"
    )
    
    args = parser.parse_args()
    
    tester = CSODWorkflowTester()
    tester.skip_slow = args.skip_slow
    
    if args.test == "all":
        tester.run_all_tests()
    elif args.test == "use_case_1":
        tester.setup()
        tester.test_use_case_1_metrics_recommender_with_gold_plan()
    elif args.test == "use_case_2":
        tester.setup()
        tester.test_use_case_2_metrics_dashboard_plan()
    elif args.test == "use_case_3":
        tester.setup()
        tester.test_use_case_3_dashboard_generation_for_persona()
    elif args.test == "use_case_4":
        tester.setup()
        tester.test_use_case_4_compliance_test_generator()
    else:
        logger.error(f"Unknown test: {args.test}")
        sys.exit(1)
