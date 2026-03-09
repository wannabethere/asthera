#!/usr/bin/env python3
"""
Test suite for Detection & Triage Engineering Workflow - LEEN Request Scenarios.

This test validates the DT workflow pipeline with leen-specific flags:
- is_leen_request=True: Enables format conversion to planner-compatible outputs
- silver_gold_tables_only=True: Filters to only use silver and gold tables (skips source/bronze)

Test Cases (mirrors test_detection_triage_workflow.py but with leen flags):
1. Use Case 1: Metrics Help (format conversion + gold dbt models + CubeJS)
2. Use Case 2: Dashboard Metrics (format conversion + gold dbt models + CubeJS)
3. Use Case 3: Detection + Metrics Full (format conversion + gold dbt models + CubeJS)

All use cases run with generate_sql=True to ensure gold dbt models and CubeJS schemas are generated.

Configuration:
- Data Sources: snyk, qualys, wiz, sentinel
- Gold Standard Project ID: cve_data
- Metrics Registry: leen_metrics_registry
- LEEN Flags: is_leen_request=True, silver_gold_tables_only=True

Uses .env configuration for LLM and vector store settings.
Generates output in tests/outputs/leen_* directories for comparison.
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

from app.agents.mdlworkflows.dt_workflow import (
    get_detection_triage_app,
    create_dt_initial_state,
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
logging.getLogger("app.agents.mdlworkflows.dt_nodes").setLevel(logging.INFO)

# Force immediate output
sys.stdout.flush()
sys.stderr.flush()

# Create output directory structure: tests/outputs/leen_testcase_name/timestamp/
OUTPUT_BASE_DIR = base_dir / "tests" / "outputs"
OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Constants
GOLD_STANDARD_PROJECT_ID = "cve_data"
DATA_SOURCES = ["snyk", "qualys", "wiz", "sentinel"]


class DetectionTriageWorkflowLeenTester:
    """Test suite for Detection & Triage Engineering workflow with LEEN request flags."""
    
    def __init__(self, output_base_dir: Path = None):
        self.app = None
        self.checkpointer = MemorySaver()
        # Generate a new thread_id for each test run to avoid checkpoint conflicts
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
        self.output_base_dir = output_base_dir or OUTPUT_BASE_DIR
        self.current_test_output_dir = None
        self.skip_slow = False
        logger.debug(f"Test instance created with thread_id: {self.config['configurable']['thread_id']}")
    
    def setup(self):
        """Initialize the DT workflow app."""
        logger.info("Setting up Detection & Triage workflow app (LEEN mode)...")
        self.app = get_detection_triage_app()
        logger.info("✓ DT workflow app initialized (LEEN mode)")
        logger.info(f"  Nodes: {list(self.app.nodes.keys())}")
    
    def create_initial_state(
        self,
        user_query: str,
        framework_id: str = None,
        selected_data_sources: List[str] = None,
    ) -> Dict[str, Any]:
        """Create initial state for the DT workflow with LEEN flags enabled."""
        state = create_dt_initial_state(
            user_query=user_query,
            session_id=str(uuid.uuid4()),
            framework_id=framework_id,
            selected_data_sources=selected_data_sources or DATA_SOURCES,
            active_project_id=GOLD_STANDARD_PROJECT_ID,
            compliance_profile=None,
            is_leen_request=True,  # Enable LEEN mode
            silver_gold_tables_only=True,  # Only use silver/gold tables
            generate_sql=True,  # Enable SQL generation for gold models
        )
        
        # Note: dt_use_llm_generation is already False by default in create_dt_initial_state
        # (control taxonomy and metrics enrichment already exist, so LLM generation is not needed)
        
        logger.info("  ✓ LEEN flags enabled: is_leen_request=True, silver_gold_tables_only=True, generate_sql=True")
        
        # Verify the flag is actually set in the state
        if state.get("dt_generate_sql") != True:
            logger.error(f"  ✗ ERROR: dt_generate_sql is not True! Value: {state.get('dt_generate_sql')}")
            raise ValueError(f"dt_generate_sql flag not set correctly. Expected True, got {state.get('dt_generate_sql')}")
        else:
            logger.info(f"  ✓ Verified: dt_generate_sql={state.get('dt_generate_sql')}")
        
        return state
    
    def test_use_case_1_metrics_help_leen(self) -> Dict[str, Any]:
        """
        Test: Use Case 1 - Metrics Help (LEEN Mode)
        
        Same as test_use_case_1_metrics_help but with:
        - is_leen_request=True (enables format conversion)
        - silver_gold_tables_only=True (filters to silver/gold tables only)
        - generate_sql=True (gold dbt models + CubeJS)
        
        Expected outputs:
        - goal_metric_definitions, goal_metrics (planner format)
        - planner_metric_recommendations, planner_medallion_plan, planner_execution_plan
        - dt_generated_gold_model_sql (gold dbt models)
        - cubejs_schema_files (CubeJS schemas)
        """
        logger.info("=" * 80)
        logger.info("TEST (LEEN): Use Case 1 - Metrics Help")
        logger.info("=" * 80)
        
        user_query = (
            "What metrics should I track for SOC2 vulnerability management and asset management compliance? "
            "I have Qualys and Snyk configured."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=["qualys", "snyk"],
        )
        
        # Verify initial state has the flag set before running
        if initial_state.get("dt_generate_sql") != True:
            logger.error(f"ERROR: dt_generate_sql is not True in initial_state! Value: {initial_state.get('dt_generate_sql')}")
            raise ValueError(f"dt_generate_sql flag not set correctly in initial_state. Expected True, got {initial_state.get('dt_generate_sql')}")
        
        try:
            logger.info(f"Executing DT workflow (LEEN mode) with query: {user_query[:100]}...")
            logger.info(f"  Initial state verification: dt_generate_sql={initial_state.get('dt_generate_sql')}, is_leen_request={initial_state.get('is_leen_request')}")
            
            # Use invoke() to get full accumulated state. stream() yields only each node's
            # partial output, so the last event would overwrite with just cubejs_schema_generation
            # output, losing planner_medallion_plan, dt_generated_gold_model_sql, LEEN flags, etc.
            logger.info("  Running workflow (invoke)...")
            final_state = self.app.invoke(initial_state, self.config)
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Log final state flag value for debugging
            logger.info(f"  Final state dt_generate_sql={final_state.get('dt_generate_sql')}")
            if final_state.get("dt_generate_sql") != True:
                logger.warning(f"  WARNING: dt_generate_sql changed from True to {final_state.get('dt_generate_sql')} during workflow execution!")
            
            # Validate LEEN-specific outputs
            validation_results = self.validate_leen_outputs(final_state)
            self.get_test_output_dir("leen_use_case_1_metrics_help")
            self.save_test_output("leen_use_case_1_metrics_help", final_state, validation_results)
            
            return {
                "test_name": "leen_use_case_1_metrics_help",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "leen_use_case_1_metrics_help",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_2_dashboard_metrics_leen(self) -> Dict[str, Any]:
        """
        Test: Use Case 2 - Dashboard Metrics Workflow (LEEN Mode)
        
        Same as test_use_case_2_dashboard_metrics_workflow but with LEEN flags.
        
        Expected outputs:
        - goal_metric_definitions, goal_metrics (from format converter)
        - planner_metric_recommendations, planner_medallion_plan, planner_execution_plan
        - dt_generated_gold_model_sql (gold dbt models)
        - cubejs_schema_files (CubeJS schemas)
        """
        logger.info("=" * 80)
        logger.info("TEST (LEEN): Use Case 2 - Dashboard Metrics Workflow")
        logger.info("=" * 80)
        
        user_query = (
            "I need to build a SOC2 compliance dashboard showing vulnerability management metrics. "
            "Generate the metric recommendations and medallion architecture plan."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow (LEEN mode) with query: {user_query[:100]}...")
            
            # Use invoke() to get full accumulated state (stream yields partial updates only)
            logger.info("  Running workflow (invoke)...")
            final_state = self.app.invoke(initial_state, self.config)
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate LEEN-specific outputs
            validation_results = self.validate_leen_outputs(final_state)
            self.get_test_output_dir("leen_use_case_2_dashboard_metrics")
            self.save_test_output("leen_use_case_2_dashboard_metrics", final_state, validation_results)
            
            return {
                "test_name": "leen_use_case_2_dashboard_metrics",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "leen_use_case_2_dashboard_metrics",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_use_case_3_detection_and_metrics_full_leen(self) -> Dict[str, Any]:
        """
        Test: Use Case 3 - Detection + Metrics Full Workflow (LEEN Mode)
        
        Same as test_use_case_3_detection_and_metrics_full but with LEEN flags.
        
        Expected outputs:
        - planner_siem_rules, planner_metric_recommendations
        - planner_medallion_plan, planner_execution_plan
        - dt_generated_gold_model_sql (gold dbt models)
        - cubejs_schema_files (CubeJS schemas)
        """
        logger.info("=" * 80)
        logger.info("TEST (LEEN): Use Case 3 - Detection + Metrics Full Workflow")
        logger.info("=" * 80)
        
        user_query = (
            "Build a complete SOC2 compliance package. I need both Sentinel detection rules "
            "and compliance dashboard metrics."
        )
        
        initial_state = self.create_initial_state(
            user_query=user_query,
            framework_id="soc2",
            selected_data_sources=DATA_SOURCES,
        )
        
        try:
            logger.info(f"Executing DT workflow (LEEN mode) with query: {user_query[:100]}...")
            
            # Use invoke() to get full accumulated state (stream yields partial updates only)
            logger.info("  Running workflow (invoke)...")
            final_state = self.app.invoke(initial_state, self.config)
            
            if final_state is None:
                raise ValueError("Workflow did not produce final state")
            
            # Validate LEEN-specific outputs
            validation_results = self.validate_leen_outputs(final_state)
            self.get_test_output_dir("leen_use_case_3_detection_metrics_full")
            self.save_test_output("leen_use_case_3_detection_metrics_full", final_state, validation_results)
            
            return {
                "test_name": "leen_use_case_3_detection_metrics_full",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": final_state,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                "test_name": "leen_use_case_3_detection_metrics_full",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_leen_outputs(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate LEEN-specific outputs (planner-compatible formats)."""
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
        
        # Check 2: Format converter ran (goal_metrics should exist)
        goal_metrics = result.get("goal_metrics", [])
        goal_metric_definitions = result.get("goal_metric_definitions", [])
        validation["checks"]["format_converter_ran"] = len(goal_metrics) > 0 or len(goal_metric_definitions) > 0
        if not validation["checks"]["format_converter_ran"]:
            validation["issues"].append("Format converter did not run: no goal_metrics or goal_metric_definitions found")
        else:
            logger.info(f"  ✓ Format converter: {len(goal_metric_definitions)} definitions, {len(goal_metrics)} metrics")
        
        # Check 3: Unified format converter ran (planner_* fields should exist)
        planner_siem_rules = result.get("planner_siem_rules", [])
        planner_metric_recommendations = result.get("planner_metric_recommendations", [])
        planner_execution_plan = result.get("planner_execution_plan", {})
        planner_medallion_plan = result.get("planner_medallion_plan", {})
        
        has_planner_outputs = (
            len(planner_siem_rules) > 0 or
            len(planner_metric_recommendations) > 0 or
            bool(planner_execution_plan) or
            bool(planner_medallion_plan)
        )
        validation["checks"]["unified_converter_ran"] = has_planner_outputs
        if not validation["checks"]["unified_converter_ran"]:
            validation["issues"].append("Unified format converter did not run: no planner_* outputs found")
        else:
            logger.info(
                f"  ✓ Unified converter: {len(planner_siem_rules)} SIEM rules, "
                f"{len(planner_metric_recommendations)} metric recommendations, "
                f"{len(planner_execution_plan.get('execution_plan', []))} execution steps"
            )
        
        # Check 4: Silver/gold tables only filtering (verify schemas are filtered)
        resolved_schemas = result.get("dt_resolved_schemas", [])
        if resolved_schemas:
            # Check that schemas contain "silver" or "gold" in table names
            all_silver_gold = all(
                "silver" in schema.get("table_name", "").lower() or
                "gold" in schema.get("table_name", "").lower()
                for schema in resolved_schemas
            )
            validation["checks"]["silver_gold_filtering"] = all_silver_gold
            if not validation["checks"]["silver_gold_filtering"]:
                validation["issues"].append("Some schemas are not silver/gold tables (silver_gold_tables_only filter may not be working)")
            else:
                logger.info(f"  ✓ All {len(resolved_schemas)} schemas are silver/gold tables")
        
        # Check 5: Planner-compatible structure
        if planner_execution_plan:
            has_execution_plan = "execution_plan" in planner_execution_plan
            has_plan_summary = "plan_summary" in planner_execution_plan
            validation["checks"]["planner_structure_valid"] = has_execution_plan and has_plan_summary
            if not validation["checks"]["planner_structure_valid"]:
                validation["issues"].append("planner_execution_plan missing required fields (execution_plan, plan_summary)")
        
        # Check 6: Gold dbt models (if gold model plan exists and requires_gold_model is True)
        dt_generate_sql = result.get("dt_generate_sql", False)
        generated_sql = result.get("dt_generated_gold_model_sql", [])
        gold_model_artifact_name = result.get("dt_gold_model_artifact_name")

        if dt_generate_sql:
            if planner_medallion_plan and planner_medallion_plan.get("requires_gold_model"):
                gold_ok = len(generated_sql) > 0
                validation["checks"]["gold_dbt_models_generated"] = gold_ok
                validation["checks"]["sql_generation_ran"] = gold_ok  # backward compat
                if not gold_ok:
                    validation["issues"].append("Gold dbt models not generated: SQL flag set and plan requires models, but no SQL was produced")
                    validation["overall_success"] = False
                else:
                    logger.info(f"  ✓ Gold dbt models: {len(generated_sql)} models generated, artifact: {gold_model_artifact_name}")
            else:
                validation["checks"]["gold_dbt_models_generated"] = True
                validation["checks"]["sql_generation_ran"] = True
                logger.info("  ✓ Gold dbt models: Plan does not require gold models, skipping")
        else:
            validation["checks"]["gold_dbt_models_generated"] = True
            validation["checks"]["sql_generation_ran"] = True
            logger.info("  ✓ Gold dbt models: Flag not set, skipping check")

        # Check 7: CubeJS schema files (when gold SQL exists, cubejs should be generated)
        cubejs_schema_files = result.get("cubejs_schema_files", [])
        cubejs_errors = result.get("cubejs_generation_errors", [])

        if generated_sql and len(generated_sql) > 0:
            validation["checks"]["cubejs_generated"] = len(cubejs_schema_files) > 0
            if not validation["checks"]["cubejs_generated"]:
                validation["issues"].append(
                    f"CubeJS not generated: {len(generated_sql)} gold models exist but no cubejs_schema_files "
                    f"(errors: {cubejs_errors[:3] if cubejs_errors else 'none'})"
                )
                validation["overall_success"] = False
            else:
                logger.info(f"  ✓ CubeJS: {len(cubejs_schema_files)} cube(s) generated")
        else:
            validation["checks"]["cubejs_generated"] = True  # No gold SQL, cubejs not expected
            logger.info("  ✓ CubeJS: No gold SQL, skipping check")

        return validation
    
    def get_test_output_dir(self, test_name: str) -> Path:
        """Create and return test-specific output directory: tests/outputs/leen_testcase_name/timestamp/"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_output_dir = self.output_base_dir / test_name / timestamp
        test_output_dir.mkdir(parents=True, exist_ok=True)
        self.current_test_output_dir = test_output_dir
        return test_output_dir
    
    def save_test_output(self, test_name: str, result: Dict[str, Any], validation: Dict[str, Any]):
        """Save test output with LEEN-specific fields."""
        test_output_dir = self.current_test_output_dir or self.get_test_output_dir(test_name)
        
        # Save main output file
        output_file = test_output_dir / "output.json"
        
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
        
        # Save separate files for key outputs
        outputs_dir = test_output_dir / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        
        # Save state snapshot with LEEN fields
        if "result" in output_data and isinstance(output_data["result"], dict):
            state_snapshot = {
                "intent": output_data["result"].get("intent"),
                "framework_id": output_data["result"].get("framework_id"),
                "is_leen_request": output_data["result"].get("is_leen_request"),
                "silver_gold_tables_only": output_data["result"].get("silver_gold_tables_only"),
                "dt_playbook_template": output_data["result"].get("dt_playbook_template"),
                "resolved_metrics_count": len(output_data["result"].get("resolved_metrics", [])),
                "dt_resolved_schemas_count": len(output_data["result"].get("dt_resolved_schemas", [])),
                "siem_rules_count": len(output_data["result"].get("siem_rules", [])),
                "dt_metric_recommendations_count": len(output_data["result"].get("dt_metric_recommendations", [])),
                # LEEN-specific outputs
                "goal_metric_definitions_count": len(output_data["result"].get("goal_metric_definitions", [])),
                "goal_metrics_count": len(output_data["result"].get("goal_metrics", [])),
                "planner_siem_rules_count": len(output_data["result"].get("planner_siem_rules", [])),
                "planner_metric_recommendations_count": len(output_data["result"].get("planner_metric_recommendations", [])),
                "planner_execution_plan_steps": len(output_data["result"].get("planner_execution_plan", {}).get("execution_plan", [])),
                # SQL generation outputs
                "dt_generate_sql": output_data["result"].get("dt_generate_sql", False),
                "dt_generated_gold_model_sql_count": len(output_data["result"].get("dt_generated_gold_model_sql", [])),
                "dt_gold_model_artifact_name": output_data["result"].get("dt_gold_model_artifact_name"),
                # CubeJS outputs
                "cubejs_schema_files_count": len(output_data["result"].get("cubejs_schema_files", [])),
                "cubejs_generation_errors": output_data["result"].get("cubejs_generation_errors", []),
            }
            with open(outputs_dir / "state_snapshot.json", 'w') as f:
                json.dump(state_snapshot, f, indent=2, default=str)
            
            # Save LEEN-specific outputs
            if output_data["result"].get("goal_metric_definitions"):
                with open(outputs_dir / "goal_metric_definitions.json", 'w') as f:
                    json.dump(output_data["result"]["goal_metric_definitions"], f, indent=2, default=str)
            
            if output_data["result"].get("goal_metrics"):
                with open(outputs_dir / "goal_metrics.json", 'w') as f:
                    json.dump(output_data["result"]["goal_metrics"], f, indent=2, default=str)
            
            if output_data["result"].get("planner_siem_rules"):
                with open(outputs_dir / "planner_siem_rules.json", 'w') as f:
                    json.dump(output_data["result"]["planner_siem_rules"], f, indent=2, default=str)
            
            if output_data["result"].get("planner_metric_recommendations"):
                with open(outputs_dir / "planner_metric_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["planner_metric_recommendations"], f, indent=2, default=str)
            
            if output_data["result"].get("planner_execution_plan"):
                with open(outputs_dir / "planner_execution_plan.json", 'w') as f:
                    json.dump(output_data["result"]["planner_execution_plan"], f, indent=2, default=str)
            
            if output_data["result"].get("planner_medallion_plan"):
                with open(outputs_dir / "planner_medallion_plan.json", 'w') as f:
                    json.dump(output_data["result"]["planner_medallion_plan"], f, indent=2, default=str)
                # Also save as gold_model_plan.json for consistency
                with open(outputs_dir / "gold_model_plan.json", 'w') as f:
                    json.dump(output_data["result"]["planner_medallion_plan"], f, indent=2, default=str)
            
            # Also save original outputs for comparison
            if output_data["result"].get("resolved_metrics"):
                with open(outputs_dir / "resolved_metrics.json", 'w') as f:
                    json.dump(output_data["result"]["resolved_metrics"], f, indent=2, default=str)
            
            if output_data["result"].get("dt_resolved_schemas"):
                with open(outputs_dir / "resolved_schemas.json", 'w') as f:
                    json.dump(output_data["result"]["dt_resolved_schemas"], f, indent=2, default=str)
            
            if output_data["result"].get("siem_rules"):
                with open(outputs_dir / "siem_rules.json", 'w') as f:
                    json.dump(output_data["result"]["siem_rules"], f, indent=2, default=str)
            
            if output_data["result"].get("dt_metric_recommendations"):
                with open(outputs_dir / "metric_recommendations.json", 'w') as f:
                    json.dump(output_data["result"]["dt_metric_recommendations"], f, indent=2, default=str)
            
            # Save generated SQL models if available
            if output_data["result"].get("dt_generated_gold_model_sql"):
                with open(outputs_dir / "generated_gold_model_sql.json", 'w') as f:
                    json.dump(output_data["result"]["dt_generated_gold_model_sql"], f, indent=2, default=str)
                
                # Also save individual SQL files for each model
                sql_dir = outputs_dir / "generated_sql"
                sql_dir.mkdir(exist_ok=True)
                for model in output_data["result"]["dt_generated_gold_model_sql"]:
                    model_name = model.get("name", "unknown")
                    sql_query = model.get("sql_query", "")
                    if sql_query:
                        sql_file = sql_dir / f"{model_name}.sql"
                        with open(sql_file, 'w') as f:
                            f.write(sql_query)
                        logger.info(f"  ✓ Saved SQL for model: {model_name}")
                
                # Save artifact name
                if output_data["result"].get("dt_gold_model_artifact_name"):
                    with open(outputs_dir / "gold_model_artifact_name.txt", 'w') as f:
                        f.write(output_data["result"]["dt_gold_model_artifact_name"])

            # Save CubeJS schema files if available
            if output_data["result"].get("cubejs_schema_files"):
                with open(outputs_dir / "cubejs_schema_files.json", 'w') as f:
                    json.dump(output_data["result"]["cubejs_schema_files"], f, indent=2, default=str)
                cubejs_dir = outputs_dir / "cubejs"
                cubejs_dir.mkdir(exist_ok=True)
                for cube in output_data["result"]["cubejs_schema_files"]:
                    filename = cube.get("filename", "unknown.js")
                    content = cube.get("content", "")
                    if content:
                        with open(cubejs_dir / filename, 'w') as f:
                            f.write(content)
                        logger.info(f"  ✓ Saved CubeJS: {filename}")
        
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
        """Run all LEEN-specific tests and generate summary."""
        logger.info("=" * 80)
        logger.info("Running LEEN Request Test Suite")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        # Run LEEN-specific use cases
        tests = [
            ("LEEN Use Case 1: Metrics Help", self.test_use_case_1_metrics_help_leen),
            ("LEEN Use Case 2: Dashboard Metrics", self.test_use_case_2_dashboard_metrics_leen),
            ("LEEN Use Case 3: Detection + Metrics Full", self.test_use_case_3_detection_and_metrics_full_leen),
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
        summary_file = self.output_base_dir / "leen_test_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("LEEN Test Suite Summary")
        logger.info("=" * 80)
        logger.info(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        logger.info(f"Summary saved to: {summary_file}")
        
        return summary


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LEEN-specific DT workflow tests")
    parser.add_argument(
        "--test",
        type=str,
        help="Run specific test (use_case_1, use_case_2, use_case_3, or all)",
        default="all"
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow operations"
    )
    
    args = parser.parse_args()
    
    tester = DetectionTriageWorkflowLeenTester()
    tester.skip_slow = args.skip_slow
    
    if args.test == "all":
        tester.run_all_tests()
    elif args.test == "use_case_1":
        tester.setup()
        tester.test_use_case_1_metrics_help_leen()
    elif args.test == "use_case_2":
        tester.setup()
        tester.test_use_case_2_dashboard_metrics_leen()
    elif args.test == "use_case_3":
        tester.setup()
        tester.test_use_case_3_detection_and_metrics_full_leen()
    else:
        logger.error(f"Unknown test: {args.test}")
        sys.exit(1)
