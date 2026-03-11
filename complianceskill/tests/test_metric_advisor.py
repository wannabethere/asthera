#!/usr/bin/env python3
"""
Test suite for CSOD Metric Advisor Workflow.

This test validates the CSOD Metric Advisor workflow pipeline for metric and KPI recommendations
with causal graph integration.

Test Cases:
1. Use Case 1: Basic Metric Advisor (compliance training effectiveness)
2. Use Case 2: Metric Advisor with Causal Graph (learning effectiveness)
3. Use Case 3: KPI Relations Mapping (metric relationships)
4. Use Case 4: Reasoning Plan Generation (structured reasoning)

Configuration:
- Data Sources: cornerstone, workday
- Metrics Registry: lms_metrics_registry.json
- Causal Vertical: lms

Uses .env configuration for LLM and vector store settings.
Generates output in tests/outputs/metric_advisor_* directories for comparison.
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


class MetricAdvisorWorkflowTester:
    """Test suite for CSOD Metric Advisor workflow."""
    
    def __init__(self, output_base_dir: Path = None):
        self.app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_base_dir = output_base_dir or OUTPUT_BASE_DIR
        self.current_test_output_dir = None
        self.skip_slow = False
    
    def setup(self):
        """Initialize the Metric Advisor workflow app."""
        logger.info("Setting up CSOD Metric Advisor workflow app...")
        self.app = get_csod_metric_advisor_app()
        logger.info("✓ Metric Advisor workflow app initialized")
        logger.info(f"  Nodes: {list(self.app.nodes.keys())}")
    
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
    ) -> Dict[str, Any]:
        """Create initial state for the Metric Advisor workflow."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        state = create_csod_metric_advisor_initial_state(
            user_query=user_query,
            session_id=session_id,
            active_project_id=None,
            selected_data_sources=selected_data_sources or DATA_SOURCES,
            compliance_profile={},
            causal_graph_enabled=causal_graph_enabled,
            causal_vertical=causal_vertical,
        )
        
        # Load and add metrics registry
        metrics_registry = self.load_metrics_registry(metrics_registry_path)
        if metrics_registry:
            state["csod_causal_metric_registry"] = metrics_registry
            state["csod_retrieved_metrics"] = metrics_registry[:20]  # Use first 20 for testing
            logger.info(f"  ✓ Added {len(metrics_registry)} metrics to state")
        
        logger.info(f"  ✓ Initial state created with {len(selected_data_sources or DATA_SOURCES)} data sources")
        return state
    
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
        
        try:
            logger.info(f"Executing Metric Advisor workflow with query: {user_query[:100]}...")
            
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
        ],
        default='all',
        help='Which test to run'
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
    
    if results:
        logger.info(f"\nAll outputs saved to: {OUTPUT_BASE_DIR}")


if __name__ == '__main__':
    main()
