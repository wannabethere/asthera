"""
Workflow Executor
End-to-end execution of Cube.js generation workflow
"""

import json
import os
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd

from app.agents.cubes.cube_generation_agent import (
    CubeGenerationAgent,
    TableDDL,
    LODConfig,
    RelationshipMapping,
    AgentState,
    CubeDefinition,
    ViewDefinition,
    TransformationStep
)
from app.agents.cubes.schema_analysis_agent import SchemaAnalysisAgent
from app.agents.cubes.transformation_planner_agent import TransformationPlannerAgent, LODDeduplication
from app.agents.cubes.cubejs_generator_agent import CubeJsGeneratorAgent
from app.agents.cubes.metric_discovery_agent import MetricDiscoveryAgent
from app.agents.cubes.sql_generator_agent import SQLGeneratorAgent, SQLDialect, SQLType
from app.agents.cubes.silver_human_in_loop import SilverHumanInLoopAgent, enrich_silver_workflow_with_human_in_loop
from app.agents.cubes.mdl_schema_generator import MDLSchemaGenerator
from app.agents.cubes.mdl_transformers import (
    MDLToCubeJsTransformer,
    MDLToDbtTransformer,
    MDLToTransformationsExporter
)
from app.agents.cubes.nl_question_generator import NLQuestionGenerator
from app.agents.cubes.pipeline_execution_planner import PipelineExecutionPlanner
from app.core.dependencies import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
import logging

logger = logging.getLogger("genieml-agents")


class WorkflowExecutor:
    """Execute complete Cube.js generation workflow"""
    
    def __init__(
        self, 
        output_dir: str = "./output", 
        llm=None,
        table_dataframes: Optional[Dict[str, pd.DataFrame]] = None,
        db_connection: Optional[Any] = None,
        target_sql_dialect: SQLDialect = SQLDialect.POSTGRESQL
    ):
        """
        Initialize the workflow executor.
        
        Args:
            output_dir: Directory to save all generated artifacts
            llm: Optional LLM instance (uses get_llm() from dependencies if not provided)
            table_dataframes: Optional dictionary mapping table names to pandas DataFrames
            db_connection: Optional database connection for statistics
            target_sql_dialect: Target SQL dialect for conversion (default: PostgreSQL)
        """
        self.output_dir = Path(output_dir)
        self.target_sql_dialect = target_sql_dialect
        
        # Get LLM instance
        if llm is None:
            self.llm = get_llm()
            logger.info("WorkflowExecutor: Created LLM instance using get_llm() from dependencies")
        else:
            self.llm = llm
            logger.info("WorkflowExecutor: Using provided LLM instance")
        
        # Extract model name from LLM for agents that need it
        # Try different ways to get model name from ChatOpenAI
        if hasattr(self.llm, 'model_name'):
            self.model_name = self.llm.model_name
        elif hasattr(self.llm, '_model_name'):
            self.model_name = self.llm._model_name
        elif hasattr(self.llm, 'model'):
            self.model_name = self.llm.model
        else:
            self.model_name = "gpt-4o-mini"  # Default fallback
        
        self.table_dataframes = table_dataframes
        self.db_connection = db_connection
        self.target_sql_dialect = target_sql_dialect
        
        # Create output directory structure
        self._setup_output_directories()
        
        # Initialize MDL components (will be updated with config values later)
        self.mdl_generator = MDLSchemaGenerator(
            catalog="default_catalog",
            schema="public"
        )
        self.cubejs_transformer = MDLToCubeJsTransformer()
        self.dbt_transformer = MDLToDbtTransformer()
        self.transformations_exporter = MDLToTransformationsExporter()
        self.nl_question_generator = NLQuestionGenerator()
        
        # Initialize agents with LLM - pass LLM directly to ensure all sub-agents use it
        self.main_agent = CubeGenerationAgent(
            model_name=self.model_name,
            table_dataframes=table_dataframes,
            db_connection=db_connection,
            llm=self.llm  # Pass LLM directly to ensure it's used throughout
        )
        # Ensure all sub-agents use the same LLM instance
        # The LLM is already passed to CubeGenerationAgent, which passes it to SilverHumanInLoopAgent
        # But we update it here to be absolutely sure all sub-agents use the correct instance
        self.main_agent.llm = self.llm
        self.main_agent.human_in_loop_agent.update_llm(self.llm)
        
        self.schema_agent = SchemaAnalysisAgent(model_name=self.model_name)
        self.schema_agent.llm = self.llm
        
        # Initialize centralized SQL generator agent with target dialect FIRST
        # (needed by other agents)
        self.sql_generator = SQLGeneratorAgent(
            llm=self.llm,
            model_name=self.model_name,
            default_target_dialect=self.target_sql_dialect
        )
        
        self.transform_agent = TransformationPlannerAgent(
            model_name=self.model_name,
            sql_generator=self.sql_generator
        )
        self.transform_agent.llm = self.llm
        
        self.cubejs_agent = CubeJsGeneratorAgent(model_name=self.model_name)
        self.cubejs_agent.llm = self.llm
        
        # Initialize metric discovery agent with SQL generator
        self.metric_discovery_agent = MetricDiscoveryAgent(
            llm=self.llm,
            model_name=self.model_name,
            sql_generator=self.sql_generator
        )
        
        # Initialize pipeline execution planner
        self.pipeline_planner = PipelineExecutionPlanner(
            llm=self.llm,
            output_dir=self.output_dir,
            sql_generator=self.sql_generator
        )
    
    def _setup_output_directories(self):
        """Create output directory structure"""
        directories = [
            "cubes/raw",
            "cubes/silver",
            "cubes/gold",
            "views",
            "transformations/raw_to_silver",
            "transformations/silver_to_gold",
            "sql/raw_to_silver",
            "sql/silver_to_gold",
            "data_quality_checks",
            "relationships",
            "documentation",
            "data_marts",
            "dbt/models/gold",
            "dbt/models/silver",
            "semantic_layer",
            "visualizations",
            "mdl",  # MDL schema output directory
            "nl_questions",  # Natural language questions directory
            "state",  # State persistence directory
            "pipeline_execution/trino",  # Trino materialized views
            "pipeline_execution/spark",  # Spark transformations
            "pipeline_execution/python",  # Python transformations
            "pipeline_execution/automation_questions"  # Automation questions
        ]
        
        for directory in directories:
            (self.output_dir / directory).mkdir(parents=True, exist_ok=True)
    
    def _get_state_file_path(self, workflow_name: str) -> Path:
        """Get path to state file for a workflow"""
        return self.output_dir / "state" / f"{workflow_name}_state.json"
    
    def _save_workflow_state(
        self,
        workflow_name: str,
        state: Dict[str, Any],
        schema_analyses: Optional[Dict] = None,
        transformation_plans: Optional[Dict] = None,
        silver_result: Optional[Dict] = None,
        gold_result: Optional[Dict] = None,
        raw_ddls: Optional[List] = None,
        lod_configs: Optional[List] = None,
        relationships: Optional[List] = None
    ):
        """Save workflow state to disk for resuming between steps"""
        state_file = self._get_state_file_path(workflow_name)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert objects to dicts for JSON serialization
        state_dict = {}
        for key, value in state.items():
            if hasattr(value, 'dict'):
                state_dict[key] = value.dict() if callable(getattr(value, 'dict', None)) else value
            elif isinstance(value, list):
                state_dict[key] = [
                    item.dict() if hasattr(item, 'dict') and callable(getattr(item, 'dict', None)) else item
                    for item in value
                ]
            else:
                state_dict[key] = value
        
        saved_state = {
            "workflow_name": workflow_name,
            "state": state_dict,
            "schema_analyses": {
                k: v.dict() if hasattr(v, 'dict') and callable(getattr(v, 'dict', None)) else v
                for k, v in (schema_analyses or {}).items()
            },
            "transformation_plans": {
                k: {
                    k2: [step.dict() if hasattr(step, 'dict') and callable(getattr(step, 'dict', None)) else step for step in v2]
                    if isinstance(v2, list) else v2
                    for k2, v2 in v.items()
                }
                for k, v in (transformation_plans or {}).items()
            },
            "silver_result": silver_result,
            "gold_result": gold_result,
            "raw_ddls": [ddl.dict() if hasattr(ddl, 'dict') and callable(getattr(ddl, 'dict', None)) else ddl for ddl in (raw_ddls or [])],
            "lod_configs": [lod.dict() if hasattr(lod, 'dict') and callable(getattr(lod, 'dict', None)) else lod for lod in (lod_configs or [])],
            "relationships": [rel.dict() if hasattr(rel, 'dict') and callable(getattr(rel, 'dict', None)) else rel for rel in (relationships or [])],
            "timestamp": datetime.now().isoformat()
        }
        
        with open(state_file, 'w') as f:
            json.dump(saved_state, f, indent=2, default=str)
        
        logger.info(f"Workflow state saved to {state_file}")
        return state_file
    
    def _load_workflow_state(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Load workflow state from disk"""
        state_file = self._get_state_file_path(workflow_name)
        
        if not state_file.exists():
            logger.info(f"No saved state found at {state_file}")
            return None
        
        try:
            with open(state_file, 'r') as f:
                saved_state = json.load(f)
            
            logger.info(f"Workflow state loaded from {state_file}")
            return saved_state
        except Exception as e:
            logger.error(f"Error loading workflow state: {e}")
            return None
    
    def _check_prerequisites(
        self,
        modeling_type: str,
        workflow_name: str,
        workflow_config: Dict[str, Any]
    ) -> tuple[bool, str, Optional[Dict]]:
        """
        Check prerequisites for a modeling type.
        
        Returns:
            (is_ready, message, saved_state)
        """
        saved_state = self._load_workflow_state(workflow_name)
        
        if modeling_type == "silver":
            # Silver can always run - it will create all prerequisites (inputs, metadata, human-in-loop)
            # If saved state exists with human-in-loop complete, we can skip that step
            if saved_state:
                state = saved_state.get("state", {})
                if state.get("table_analysis_configs") and len(state.get("table_analysis_configs", [])) > 0:
                    return True, "Prerequisites met: saved state found with human-in-loop data (will reuse)", saved_state
                else:
                    return True, "Saved state found but incomplete, will complete human-in-loop step", saved_state
            else:
                # Will create everything from scratch
                return True, "No saved state found, will create new state with all prerequisites", None
        
        elif modeling_type == "gold":
            # Gold requires: silver layer complete
            if not saved_state:
                return False, "Prerequisites missing: no saved state found. Run 'silver' modeling type first.", None
            
            state = saved_state.get("state", {})
            silver_result = saved_state.get("silver_result")
            
            if not state.get("generation_complete", False):
                return False, "Prerequisites missing: silver workflow not complete. Run 'silver' modeling type first.", saved_state
            
            if not silver_result or not silver_result.get("silver_cubes"):
                return False, "Prerequisites missing: silver cubes not found. Run 'silver' modeling type first.", saved_state
            
            return True, "Prerequisites met: silver layer complete", saved_state
        
        elif modeling_type == "transform":
            # Transform requires: schema analyses and transformation plans
            if not saved_state:
                return False, "Prerequisites missing: no saved state found. Run 'silver' modeling type first.", None
            
            schema_analyses = saved_state.get("schema_analyses", {})
            transformation_plans = saved_state.get("transformation_plans", {})
            
            if not schema_analyses:
                return False, "Prerequisites missing: schema analyses not found. Run 'silver' modeling type first.", saved_state
            
            if not transformation_plans:
                return False, "Prerequisites missing: transformation plans not found. Run 'silver' modeling type first.", saved_state
            
            return True, "Prerequisites met: schema analyses and transformation plans available", saved_state
        
        else:
            return False, f"Unknown modeling type: {modeling_type}. Use 'silver', 'gold', or 'transform'.", saved_state
    
    async def execute_workflow(
        self,
        workflow_config: Dict[str, Any],
        modeling_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute workflow from configuration with optional step-by-step execution.
        
        Args:
            workflow_config: Workflow configuration dictionary
            modeling_type: Optional modeling type to execute:
                - "silver": Generate silver layer (requires: inputs, metadata, human-in-loop)
                - "gold": Generate gold layer (requires: silver layer complete)
                - "transform": Generate transformation layer (requires: schema analyses, plans)
                - None: Execute full workflow
            
        Returns:
            Dictionary containing all generated artifacts and their file paths
        """
        workflow_name = workflow_config["workflow_name"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # If modeling_type is specified, check prerequisites
        if modeling_type:
            is_ready, message, saved_state = self._check_prerequisites(
                modeling_type, workflow_name, workflow_config
            )
            if not is_ready:
                raise RuntimeError(f"Prerequisites not met for {modeling_type}: {message}")
            print(f"✓ Prerequisites check passed: {message}")
            logger.info(f"Prerequisites check passed for {modeling_type}: {message}")
        
        # Check if workflow is already running (prevent concurrent execution)
        execution_lock_file = self.output_dir / f".{workflow_name}_executing.lock"
        if execution_lock_file.exists():
            logger.warning(f"Workflow {workflow_name} appears to be already executing. If this is an error, delete {execution_lock_file}")
            # Check if lock is stale (older than 1 hour)
            import time
            lock_age = time.time() - execution_lock_file.stat().st_mtime
            if lock_age > 3600:  # 1 hour
                logger.info(f"Removing stale lock file (age: {lock_age}s)")
                execution_lock_file.unlink()
            else:
                raise RuntimeError(f"Workflow {workflow_name} is already executing. Lock file: {execution_lock_file}")
        
        # Create lock file
        execution_lock_file.touch()
        
        try:
            print(f"\n{'='*80}")
            print(f"Executing Workflow: {workflow_name}")
            if modeling_type:
                print(f"Modeling Type: {modeling_type}")
            print(f"Timestamp: {timestamp}")
            print(f"{'='*80}\n")
            logger.info(f"Starting workflow execution: {workflow_name} at {timestamp} (modeling_type={modeling_type})")
            
            # Load saved state if available and modeling_type is specified
            saved_state = None
            if modeling_type:
                saved_state = self._load_workflow_state(workflow_name)
            
            # Initialize variables
            raw_ddls = None
            lod_configs = None
            relationships = None
            state = None
            schema_analyses = None
            transformation_plans = None
            silver_result = None
            gold_result = None
            pipeline_plans = None  # Initialize pipeline plans for incremental updates
            
            # Initialize pipeline plans if pipeline execution is enabled
            if not modeling_type and workflow_config.get("enable_pipeline_execution", True):
                pipeline_plans = self.pipeline_planner.initialize_pipeline_plans()
                logger.info("Initialized pipeline plans for incremental updates")
            
            # Step 1: Parse inputs (required for all modeling types)
            if not modeling_type or modeling_type == "silver":
                print("📋 Step 1: Parsing workflow inputs...")
                raw_ddls, lod_configs, relationships = self._parse_workflow_inputs(workflow_config)
            elif saved_state:
                # Load from saved state
                raw_ddls = saved_state.get("raw_ddls")
                lod_configs = saved_state.get("lod_configs")
                relationships = saved_state.get("relationships")
                # Load pipeline plans if available
                if saved_state.get("pipeline_plans"):
                    pipeline_plans = saved_state.get("pipeline_plans")
            
            # Step 2-4: Silver layer setup (only for silver modeling_type or full workflow)
            if not modeling_type or modeling_type == "silver":
                # Step 2: Create initial state for silver workflow
                print("\n🔍 Step 2: Initializing silver workflow state...")
                if saved_state and saved_state.get("state"):
                    # Restore state from saved file
                    state_dict = saved_state["state"]
                    # Convert back to AgentState if needed
                    state = state_dict
                    logger.info("Restored state from saved file")
                else:
                    initial_state = self.main_agent._create_initial_state(
                        raw_ddls=raw_ddls,
                        user_query=workflow_config["user_query"],
                        lod_configs=lod_configs,
                        relationship_mappings=relationships
                    )
                    
                    # Step 3: Enrich table metadata (with pandas DataFrames if provided)
                    print("\n📊 Step 3: Enriching table metadata...")
                    from app.agents.cubes.metadata_enrichment import enrich_table_metadata
                    state = enrich_table_metadata(
                        state=initial_state,
                        table_dataframes=self.table_dataframes,
                        db_connection=self.db_connection,
                        llm=self.llm
                    )
                
                # Step 4: Human-in-the-loop collection with data mart planning
                print("\n👤 Step 4: Human-in-the-loop collection and data mart planning...")
                # Check if already done to prevent duplicate execution
                if state.get("table_analysis_configs") and len(state.get("table_analysis_configs", [])) > 0:
                    logger.info("Human-in-the-loop already completed, skipping Step 4")
                    print("  ⏭️  Human-in-the-loop already completed, skipping...")
                else:
                    data_mart_goals = workflow_config.get("data_mart_goals", [])
                    state = await enrich_silver_workflow_with_human_in_loop(
                        state=state,
                        human_in_loop_agent=self.main_agent.human_in_loop_agent,
                        data_mart_goals=data_mart_goals
                    )
                    logger.info(f"Human-in-the-loop completed for {len(state.get('table_analysis_configs', []))} tables")
            
            # Step 5: Analyze schemas (required for silver and transform)
            if not modeling_type or modeling_type in ["silver", "transform"]:
                print("\n🔍 Step 5: Analyzing schemas...")
                if saved_state and saved_state.get("schema_analyses"):
                    schema_analyses = saved_state["schema_analyses"]
                    logger.info("Loaded schema analyses from saved state")
                else:
                    schema_analyses = self._analyze_schemas(raw_ddls)
            
            # Step 6: Generate transformation plans (required for silver and transform)
            if not modeling_type or modeling_type in ["silver", "transform"]:
                print("\n🔄 Step 6: Planning transformations...")
                if saved_state and saved_state.get("transformation_plans"):
                    transformation_plans = saved_state["transformation_plans"]
                    logger.info("Loaded transformation plans from saved state")
                else:
                    transformation_plans = self._plan_transformations(schema_analyses, lod_configs, relationships)
            
            # Step 7: Execute main agent workflow (silver generation)
            # Only execute if modeling_type is None (full workflow) or "silver"
            if not modeling_type or modeling_type == "silver":
                # Use the enriched state from human-in-the-loop
                print("\n🤖 Step 7: Executing silver generation workflow...")
                # Ensure state has all required fields
                state["raw_ddls"] = raw_ddls
                state["user_query"] = workflow_config["user_query"]
                state["lod_configs"] = lod_configs or []
                state["relationship_mappings"] = relationships or []
                # Ensure optional fields exist
                if "raw_cubes" not in state:
                    state["raw_cubes"] = []
                if "silver_cubes" not in state:
                    state["silver_cubes"] = []
                if "gold_cubes" not in state:
                    state["gold_cubes"] = []
                if "views" not in state:
                    state["views"] = []
                if "raw_to_silver_steps" not in state:
                    state["raw_to_silver_steps"] = []
                if "silver_to_gold_steps" not in state:
                    state["silver_to_gold_steps"] = []
                if "current_layer" not in state:
                    state["current_layer"] = "raw"
                if "generation_complete" not in state:
                    state["generation_complete"] = False
                    if "gold_generation_complete" not in state:
                        state["gold_generation_complete"] = False
                    if "enhanced_cubes_generated" not in state:
                        state["enhanced_cubes_generated"] = False
                if "error" not in state:
                    state["error"] = None
            
                # Run silver workflow with enriched state
                # Check if already complete to avoid re-running
                if state.get("generation_complete", False) and state.get("silver_cubes"):
                    logger.info("Silver workflow already marked as complete, using existing state")
                    print("  ⏭️  Silver workflow already complete, skipping execution...")
                    silver_final_state = state
                else:
                    logger.info("Invoking silver workflow...")
                    silver_final_state = self.main_agent.silver_workflow.invoke(state)
                    # Mark as complete to prevent re-execution
                    silver_final_state["generation_complete"] = True
                    logger.info(f"Silver workflow completed. Generated {len(silver_final_state.get('silver_cubes', []))} silver cubes")
                
                # Convert to expected format
                silver_result = {
                    "table_metadata": [meta.dict() if hasattr(meta, 'dict') else meta for meta in silver_final_state.get("table_metadata", [])],
                    "raw_cubes": [cube.dict() if hasattr(cube, 'dict') else cube for cube in silver_final_state.get("raw_cubes", [])],
                    "silver_cubes": [cube.dict() if hasattr(cube, 'dict') else cube for cube in silver_final_state.get("silver_cubes", [])],
                    "raw_to_silver_transformations": [step.dict() if hasattr(step, 'dict') else step for step in silver_final_state.get("raw_to_silver_steps", [])],
                    "messages": silver_final_state.get("messages", []),
                    "state": silver_final_state
                }
                
                # Update pipeline plans with silver layer artifacts
                if pipeline_plans is not None and workflow_config.get("enable_pipeline_execution", True):
                    print("\n🔧 Updating pipeline plans with silver layer artifacts...")
                    pipeline_plans = self.pipeline_planner.update_silver_pipeline_plans(
                        pipeline_plans,
                        workflow_config,
                        silver_result,
                        transformation_plans,
                        silver_final_state
                    )
                    # Store in state for persistence
                    silver_final_state["pipeline_plans"] = pipeline_plans
                
                # Save state after silver generation
                self._save_workflow_state(
                    workflow_name,
                    silver_final_state,
                    schema_analyses,
                    transformation_plans,
                    silver_result,
                    raw_ddls=raw_ddls,
                    lod_configs=lod_configs,
                    relationships=relationships
                )
            elif saved_state:
                # Load silver result from saved state
                silver_result = saved_state.get("silver_result")
                state = saved_state.get("state", {})
                # Also load raw_ddls, lod_configs, relationships if not already loaded
                if not raw_ddls:
                    raw_ddls = saved_state.get("raw_ddls")
                if not lod_configs:
                    lod_configs = saved_state.get("lod_configs")
                if not relationships:
                    relationships = saved_state.get("relationships")
        
            # Step 8: Generate gold layer if requested
            # Only execute if modeling_type is None (full workflow) or "gold"
            gold_result = None
            if (not modeling_type or modeling_type == "gold") and workflow_config.get("generate_gold", True):
                print("\n✨ Step 8: Generating gold layer...")
                # Check if gold workflow already completed to avoid re-running
                gold_state = silver_result["state"] if silver_result else state
                if gold_state.get("gold_generation_complete", False) and gold_state.get("gold_cubes"):
                    logger.info("Gold workflow already marked as complete, using existing state")
                    print("  ⏭️  Gold workflow already complete, skipping execution...")
                    gold_final_state = gold_state
                else:
                    logger.info("Invoking gold workflow...")
                    gold_final_state = self.main_agent.gold_workflow.invoke(silver_result["state"] if silver_result else state)
                    # Mark as complete to prevent re-execution
                    gold_final_state["gold_generation_complete"] = True
                    logger.info(f"Gold workflow completed. Generated {len(gold_final_state.get('gold_cubes', []))} gold cubes")
                
                    # Step 8b: Discover and generate metrics from natural language questions AND data mart goals
                    metric_questions = workflow_config.get("metric_questions", [])
                    data_mart_goals = workflow_config.get("data_mart_goals", [])
                    
                    all_metric_questions = list(metric_questions)  # Start with explicit metric questions
                    
                    # Add data mart goals as metric discovery questions
                    if data_mart_goals:
                        print(f"\n📊 Step 8b: Discovering metrics from data mart goals and natural language questions...")
                        print(f"  Found {len(data_mart_goals)} data mart goal(s) to discover metrics from")
                        all_metric_questions.extend(data_mart_goals)
                    elif metric_questions:
                        print("\n📊 Step 8b: Discovering and generating metrics from natural language questions...")
                    
                    if all_metric_questions:
                        discovered_metrics_result = self._discover_metrics_from_questions(
                            questions=all_metric_questions,
                            silver_result=silver_result,
                            schema_analyses=schema_analyses,
                            state=gold_final_state,
                            data_mart_goals=data_mart_goals  # Pass goals to associate metrics
                        )
                        
                        # Add discovered metrics to state
                        if "discovered_metrics" not in gold_final_state:
                            gold_final_state["discovered_metrics"] = []
                        gold_final_state["discovered_metrics"].extend(
                            discovered_metrics_result.get("discovered_metrics", [])
                        )
                        
                        # Associate metrics with data mart goals
                        if data_mart_goals:
                            self._associate_metrics_with_data_mart_goals(
                                gold_final_state,
                                data_mart_goals,
                                discovered_metrics_result.get("discovered_metrics", [])
                            )
                        
                        # Convert discovered metrics to transformation steps
                        metric_steps = self._convert_metrics_to_transformation_steps(
                            discovered_metrics_result
                        )
                        
                        # Add metric steps to gold transformation steps
                        if "silver_to_gold_steps" not in gold_final_state:
                            gold_final_state["silver_to_gold_steps"] = []
                        gold_final_state["silver_to_gold_steps"].extend(metric_steps)
                        
                        total_metrics = len(discovered_metrics_result.get("discovered_metrics", []))
                        from_goals = len([m for m in discovered_metrics_result.get("discovered_metrics", []) if m.get("associated_data_mart_goal")])
                        from_questions = total_metrics - from_goals
                        
                        logger.info(f"Discovered {total_metrics} metrics ({from_goals} from data mart goals, {from_questions} from questions)")
                        print(f"  ✓ Discovered {total_metrics} metrics ({from_goals} from data mart goals, {from_questions} from questions)")
                        print(f"  ✓ Generated {len(metric_steps)} metric transformation(s)")
                
                # Convert to expected format
                gold_result = {
                    "gold_cubes": [cube.dict() if hasattr(cube, 'dict') else cube for cube in gold_final_state.get("gold_cubes", [])],
                    "views": [view.dict() if hasattr(view, 'dict') else view for view in gold_final_state.get("views", [])],
                    "silver_to_gold_transformations": [step.dict() if hasattr(step, 'dict') else step for step in gold_final_state.get("silver_to_gold_steps", [])],
                    "messages": gold_final_state.get("messages", []),
                    "state": gold_final_state
                }
                
                # Update pipeline plans with gold layer artifacts
                if pipeline_plans is not None and workflow_config.get("enable_pipeline_execution", True):
                    print("\n🔧 Updating pipeline plans with gold layer artifacts...")
                    pipeline_plans = self.pipeline_planner.update_gold_pipeline_plans(
                        pipeline_plans,
                        workflow_config,
                        gold_result,
                        transformation_plans,
                        gold_final_state
                    )
                    # Store in state for persistence
                    gold_final_state["pipeline_plans"] = pipeline_plans
                
                # Save state after gold generation
                self._save_workflow_state(
                    workflow_name,
                    gold_final_state,
                    schema_analyses,
                    transformation_plans,
                    silver_result,
                    gold_result,
                    raw_ddls=raw_ddls,
                    lod_configs=lod_configs,
                    relationships=relationships
                )
            elif saved_state:
                # Load gold result from saved state
                gold_result = saved_state.get("gold_result")
            
            # Step 9: Generate enhanced cube definitions
            # Only for full workflow or transform modeling type
            enhanced_cubes = {"raw": {}, "silver": {}, "gold": {}}
            if not modeling_type or modeling_type == "transform":
                # Skip if cubes already generated to avoid redundant work
                print("\n📦 Step 9: Generating detailed cube definitions...")
                # Check if enhanced cube generation is enabled (can be disabled for faster execution)
                if not workflow_config.get("enable_enhanced_cubes", True):
                    logger.info("Enhanced cube generation disabled in config, skipping Step 9")
                    print("  ⏭️  Enhanced cube generation disabled, skipping...")
                elif state and state.get("enhanced_cubes_generated", False):
                    logger.info("Enhanced cubes already generated, skipping Step 9")
                    print("  ⏭️  Enhanced cubes already generated, skipping...")
                    # Use existing enhanced cubes from state if available, otherwise generate
                    if "enhanced_cubes" in state:
                        enhanced_cubes = state["enhanced_cubes"]
                    else:
                        print("  ⚠️  Enhanced cubes flag set but cubes not found in state, regenerating...")
                        enhanced_cubes = self._generate_enhanced_cubes(schema_analyses, transformation_plans)
                        if state:
                            state["enhanced_cubes"] = enhanced_cubes
                            state["enhanced_cubes_generated"] = True
                else:
                    print(f"  ℹ️  This step generates cubes for {len(schema_analyses)} tables × 3 layers = {len(schema_analyses) * 3} total cubes")
                    print(f"  ℹ️  This may take several minutes due to multiple LLM calls...")
                    enhanced_cubes = self._generate_enhanced_cubes(schema_analyses, transformation_plans)
                    if state:
                        state["enhanced_cubes"] = enhanced_cubes
                        state["enhanced_cubes_generated"] = True
            
            # Step 10: Enhance data marts with transformations
            # Only for full workflow
            enhanced_data_marts = None
            if not modeling_type:
                if workflow_config.get("enable_enhanced_data_marts", True):
                    print("\n🔄 Step 10: Enhancing data marts with transformations...")
                    enhanced_data_marts = self._enhance_data_marts_with_transformations(
                        state.get("data_mart_plans", []) if state else [],
                        silver_result,
                        gold_result
                    )
                    
                    # Update pipeline plans with data mart artifacts
                    if pipeline_plans is not None and workflow_config.get("enable_pipeline_execution", True):
                        print("  Updating pipeline plans with data mart artifacts...")
                        pipeline_plans = self.pipeline_planner.update_data_mart_pipeline_plans(
                            pipeline_plans,
                            workflow_config,
                            enhanced_data_marts,
                            state
                        )
                        # Store in state for persistence
                        if state:
                            state["pipeline_plans"] = pipeline_plans
                else:
                    print("\n⏭️  Step 10: Skipping data mart enhancement (disabled in config)")
            
            # Step 11: Generate gold metrics from DDL, dimensions, and measures
            # Only for full workflow
            gold_metrics = None
            if not modeling_type:
                if workflow_config.get("enable_gold_metrics", True):
                    print("\n📊 Step 11: Generating gold layer metrics...")
                    gold_metrics_config = workflow_config.get("gold_metrics_config", {})
                    gold_metrics = self._generate_gold_metrics(
                        enhanced_data_marts or [],
                        gold_result,
                        schema_analyses,
                        gold_metrics_config
                    )
                else:
                    print("\n⏭️  Step 11: Skipping gold metrics generation (disabled in config)")
        
            # Step 12: Generate MDL schema (single source of truth)
            # Only for full workflow
            mdl_schema = None
            if not modeling_type:
                print("\n📐 Step 12: Generating MDL schema (single source of truth)...")
                mdl_schema = self._generate_mdl_schema(
                    state,
                    silver_result,
                    gold_result,
                    schema_analyses,
                    transformation_plans,
                    enhanced_cubes,
                    enhanced_data_marts,
                    gold_metrics,
                    workflow_config
                )
                
                # Step 13: Save MDL schema
                print("\n💾 Step 13: Saving MDL schema...")
                mdl_path = self.output_dir / "mdl" / f"{workflow_name}_schema.json"
                mdl_path.parent.mkdir(parents=True, exist_ok=True)
                self.mdl_generator.save_to_file(mdl_schema, str(mdl_path))
                print(f"  MDL schema saved: {mdl_path}")
            
            # Step 13b: Generate natural language questions
            # Only for full workflow
            nl_question_paths = []
            if not modeling_type:
                print("\n❓ Step 13b: Generating natural language questions...")
                # Check if questions already exist to avoid regenerating
                questions_dir = self.output_dir / "nl_questions"
                existing_questions_file = questions_dir / "workflow_all.json"
                
                if existing_questions_file.exists() and workflow_config.get("skip_existing_questions", False):
                    print("  Skipping NL question generation (already exists, use skip_existing_questions=false to regenerate)")
                    nl_question_paths = [str(existing_questions_file)]
                else:
                    try:
                        nl_question_paths = self._generate_nl_questions(
                            state,
                            silver_result,
                            gold_result,
                            transformation_plans,
                            enhanced_cubes,
                            enhanced_data_marts,
                            workflow_config
                        )
                        print(f"  Generated {len(nl_question_paths)} question file(s)")
                    except Exception as e:
                        logger.error(f"Error generating NL questions: {e}")
                        print(f"  ⚠️  Error generating NL questions: {e}")
                        nl_question_paths = []
            
            # Step 14: Save all original artifacts (for backward compatibility)
            # For transform modeling type, focus on transformation artifacts
            print("\n💾 Step 14: Saving artifacts...")
            if modeling_type == "transform":
                # Save only transformation-related artifacts
                saved_paths = {
                    "transformations": [],
                    "sql": [],
                    "analyses": []
                }
                
                # Save transformation plans
                for layer_transition in ["raw_to_silver", "silver_to_gold"]:
                    for table_name, steps in transformation_plans.get(layer_transition, {}).items():
                        plan_path = self.output_dir / f"transformations/{layer_transition}/{table_name}.json"
                        plan_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(plan_path, 'w') as f:
                            # Handle both dict and object formats
                            step_dicts = []
                            for step in steps:
                                if isinstance(step, dict):
                                    step_dicts.append(step)
                                elif hasattr(step, 'dict'):
                                    step_dicts.append(step.dict() if callable(getattr(step, 'dict', None)) else step)
                                else:
                                    step_dicts.append(step)
                            json.dump(step_dicts, f, indent=2)
                        saved_paths["transformations"].append(str(plan_path))
                
                # Save transformation SQL
                for layer_transition in ["raw_to_silver", "silver_to_gold"]:
                    for table_name, steps in transformation_plans.get(layer_transition, {}).items():
                        sql_path = self.output_dir / f"sql/{layer_transition}/{table_name}.sql"
                        sql_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(sql_path, 'w') as f:
                            f.write(f"-- Transformation: {layer_transition}\n")
                            f.write(f"-- Table: {table_name}\n")
                            f.write(f"-- Generated: {timestamp}\n\n")
                            
                            for step in steps:
                                # Handle both dict and object formats
                                if isinstance(step, dict):
                                    step_name = step.get("step_name", "Unknown")
                                    step_type = step.get("transformation_type", "Unknown")
                                    step_desc = step.get("description", "")
                                    step_sql = step.get("sql_logic", "")
                                else:
                                    step_name = getattr(step, "step_name", "Unknown")
                                    step_type = getattr(step, "transformation_type", "Unknown")
                                    step_desc = getattr(step, "description", "")
                                    step_sql = getattr(step, "sql_logic", "")
                                
                                f.write(f"-- Step: {step_name}\n")
                                f.write(f"-- Type: {step_type}\n")
                                f.write(f"-- Description: {step_desc}\n\n")
                                f.write(step_sql)
                                f.write("\n\n")
                                f.write("-" * 80)
                                f.write("\n\n")
                        
                        saved_paths["sql"].append(str(sql_path))
                
                # Save schema analyses
                for table_name, analysis in schema_analyses.items():
                    analysis_path = self.output_dir / f"documentation/{table_name}_analysis.json"
                    analysis_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(analysis_path, 'w') as f:
                        # Handle both dict and object formats
                        if isinstance(analysis, dict):
                            json.dump(analysis, f, indent=2)
                        elif hasattr(analysis, 'dict'):
                            json.dump(analysis.dict() if callable(getattr(analysis, 'dict', None)) else analysis, f, indent=2)
                        else:
                            json.dump(analysis, f, indent=2, default=str)
                    saved_paths["analyses"].append(str(analysis_path))
                
                print(f"  ✓ Saved {len(saved_paths['transformations'])} transformation plan(s)")
                print(f"  ✓ Saved {len(saved_paths['sql'])} SQL file(s)")
                print(f"  ✓ Saved {len(saved_paths['analyses'])} analysis file(s)")
            else:
                # Full workflow: save all artifacts
                saved_paths = self._save_all_artifacts(
                    workflow_name,
                    timestamp,
                    silver_result,
                    schema_analyses,
                    transformation_plans,
                    enhanced_cubes,
                    gold_result,
                    state,
                    enhanced_data_marts,
                    gold_metrics,
                    workflow_config
                )
            
            # Step 15: Transform MDL to target formats (Cube.js, dbt) - additional MDL-based outputs
            # Only for full workflow
            if not modeling_type and mdl_schema:
                print("\n🔄 Step 15: Transforming MDL to target formats (additional outputs)...")
                mdl_paths = self._transform_mdl_to_targets(
                    mdl_schema,
                    workflow_name,
                    timestamp,
                    workflow_config
                )
                
                # Merge MDL paths with all other paths (MDL-generated files supplement original files)
                for key, value in mdl_paths.items():
                    if key in saved_paths:
                        # Add MDL-generated files, avoiding exact duplicates
                        existing_paths = set(saved_paths[key])
                        new_paths = [p for p in value if p not in existing_paths]
                        saved_paths[key].extend(new_paths)
                    else:
                        saved_paths[key] = value
                
                # Add MDL schema path
                mdl_path = self.output_dir / "mdl" / f"{workflow_name}_schema.json"
                saved_paths["mdl"] = [str(mdl_path)]
            
            # Add NL questions paths (from Step 13b)
            if nl_question_paths:
                saved_paths["nl_questions"] = nl_question_paths
            
            # Step 17: Finalize pipeline execution plans and generate automation questions
            # Only for full workflow
            if not modeling_type:
                if workflow_config.get("enable_pipeline_execution", True):
                    print("\n🚀 Step 17: Finalizing pipeline execution plans...")
                    
                    # Finalize pipeline plans (create execution order)
                    if pipeline_plans is None:
                        # Fallback: if pipeline plans weren't initialized incrementally, create them now
                        logger.warning("Pipeline plans not initialized incrementally, creating full plan now")
                        pipeline_plans = self.pipeline_planner.plan_pipeline_execution(
                            workflow_config,
                            silver_result,
                            gold_result,
                            transformation_plans,
                            enhanced_data_marts,
                            state
                        )
                    else:
                        # Finalize the incrementally built plans
                        pipeline_plans = self.pipeline_planner.finalize_pipeline_plans(
                            pipeline_plans,
                            workflow_config
                        )
                    
                    # Save pipeline execution plans
                    self.pipeline_planner.save_pipeline_execution_plans(
                        workflow_name,
                        timestamp,
                        pipeline_plans,
                        saved_paths,
                        workflow_config
                    )
                    
                    print(f"  ✓ Finalized {len(pipeline_plans.get('trino_materialized_views', []))} Trino materialized views")
                    print(f"  ✓ Finalized {len(pipeline_plans.get('spark_transformations', []))} Spark transformations")
                    print(f"  ✓ Finalized {len(pipeline_plans.get('python_transformations', []))} Python transformations")
                    print(f"  ✓ Created execution order with {len(pipeline_plans.get('execution_order', []))} steps")
                    print(f"  ✓ Generated automation questions for pipeline execution")
                else:
                    print("\n⏭️  Step 17: Skipping pipeline execution planning (disabled in config)")
            
            # Step 18: Generate documentation
            # Only for full workflow
            if not modeling_type:
                print("\n📚 Step 18: Generating documentation...")
                self._generate_documentation(workflow_name, workflow_config, silver_result, saved_paths, state, mdl_schema)
            
            print(f"\n✅ Workflow completed successfully!")
            if modeling_type:
                print(f"✓ Completed {modeling_type} modeling type")
            print(f"📂 Outputs saved to: {self.output_dir}")
            
            result = {
                "workflow_name": workflow_name,
                "timestamp": timestamp,
                "modeling_type": modeling_type,
                "result": silver_result,
                "gold_result": gold_result,
                "saved_paths": saved_paths,
                "data_mart_plans": state.get("data_mart_plans", []) if state else [],
                "pipeline_plans": pipeline_plans
            }
            
            return result
        finally:
            # Always remove lock file, even on error
            try:
                if execution_lock_file.exists():
                    execution_lock_file.unlink()
            except Exception as e:
                logger.warning(f"Could not remove lock file: {e}")
    
    def execute_workflow_sync(
        self,
        workflow_config: Dict[str, Any],
        modeling_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for execute_workflow.
        
        Args:
            workflow_config: Workflow configuration dictionary
            modeling_type: Optional modeling type to execute (silver/gold/transform)
            
        Returns:
            Dictionary containing all generated artifacts and their file paths
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use nest_asyncio
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    return asyncio.run(self.execute_workflow(workflow_config, modeling_type))
                except:
                    # Fallback: create new event loop
                    return asyncio.run(self.execute_workflow(workflow_config, modeling_type))
            else:
                return loop.run_until_complete(self.execute_workflow(workflow_config, modeling_type))
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(self.execute_workflow(workflow_config, modeling_type))
    
    def _parse_workflow_inputs(self, config: Dict[str, Any]) -> tuple:
        """Parse workflow configuration into agent inputs"""
        # Parse raw DDLs
        raw_ddls = [
            TableDDL(**schema)
            for schema in config["raw_schemas"]
        ]
        
        # Parse LOD configs
        lod_configs = [
            LODConfig(**lod)
            for lod in config.get("lod_configurations", [])
        ]
        
        # Parse relationships - map JSON fields to model fields
        relationships = []
        for rel in config.get("relationship_mappings", []):
            # Handle both formats: new format (from_table/to_table) and old format (child_table/parent_table)
            if "from_table" in rel and "to_table" in rel:
                # New format: convert to model format
                from_table = rel.get("from_table", "")
                to_table = rel.get("to_table", "")
                from_column = rel.get("from_column", "")
                to_column = rel.get("to_column", "")
                relationship_type = rel.get("relationship_type", "many_to_one")
                layer = rel.get("layer", "silver")
                
                # Convert relationship_type to join_type format
                join_type_map = {
                    "many_to_one": "MANY_TO_ONE",
                    "one_to_many": "ONE_TO_MANY",
                    "one_to_one": "ONE_TO_ONE"
                }
                join_type = join_type_map.get(relationship_type.lower(), "MANY_TO_ONE")
                
                # Build join condition
                if from_column and to_column:
                    join_condition = f"{from_table}.{from_column} = {to_table}.{to_column}"
                else:
                    # Fallback: use common column name if columns not specified
                    join_condition = f"{from_table}.{from_table.split('_')[-1]}_id = {to_table}.{to_table.split('_')[-1]}_id"
                
                relationships.append(RelationshipMapping(
                    child_table=from_table,
                    parent_table=to_table,
                    join_type=join_type,
                    join_condition=join_condition,
                    layer=layer
                ))
            else:
                # Old format: use directly
                relationships.append(RelationshipMapping(**rel))
        
        return raw_ddls, lod_configs, relationships
    
    def _discover_metrics_from_questions(
        self,
        questions: List[str],
        silver_result: Dict,
        schema_analyses: Optional[Dict] = None,
        state: Optional[Dict] = None,
        data_mart_goals: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Discover and plan metrics from natural language questions.
        
        Args:
            questions: List of natural language questions
            silver_result: Silver layer results
            schema_analyses: Optional schema analyses for context
            state: Optional current state
            
        Returns:
            Dictionary with discovered_metrics, metric_plans, and generated_sql
        """
        # Build available tables list
        available_tables = []
        
        # Add silver tables
        if silver_result and "silver_cubes" in silver_result:
            for cube in silver_result["silver_cubes"]:
                if isinstance(cube, dict):
                    cube_name = cube.get("name", "")
                    table_name = cube_name.replace("silver_", "")
                    available_tables.append({
                        "table_name": cube_name,
                        "description": cube.get("description", ""),
                        "columns": cube.get("dimensions", []) + cube.get("measures", [])
                    })
        
        # Add schema analysis info
        if schema_analyses:
            for table_name, analysis in schema_analyses.items():
                if isinstance(analysis, dict):
                    available_tables.append({
                        "table_name": table_name,
                        "description": analysis.get("description", ""),
                        "columns": analysis.get("columns", [])
                    })
        
        # Get silver and gold table names
        silver_tables = []
        gold_tables = []
        if silver_result:
            if "silver_cubes" in silver_result:
                silver_tables = [
                    cube.get("name", "").replace("silver_", "")
                    for cube in silver_result["silver_cubes"]
                    if isinstance(cube, dict)
                ]
            if "gold_cubes" in silver_result.get("state", {}):
                gold_tables = [
                    cube.get("name", "").replace("gold_", "")
                    for cube in silver_result["state"].get("gold_cubes", [])
                    if isinstance(cube, dict)
                ]
        
        # Process each question
        all_discovered_metrics = []
        all_metric_plans = []
        all_generated_sql = {}
        all_errors = []
        
        data_mart_goals = data_mart_goals or []
        
        for question in questions:
            print(f"  Processing question: {question[:80]}...")
            
            # Check if this question is a data mart goal
            is_data_mart_goal = question in data_mart_goals
            
            result = self.metric_discovery_agent.discover_and_plan_metrics(
                question=question,
                available_tables=available_tables,
                silver_tables=silver_tables,
                gold_tables=gold_tables
            )
            
            # Add association to data mart goal if applicable
            discovered_metrics = result.get("discovered_metrics", [])
            if is_data_mart_goal:
                for metric in discovered_metrics:
                    if isinstance(metric, dict):
                        metric["associated_data_mart_goal"] = question
                    else:
                        # If it's a Pydantic model, convert to dict and add field
                        metric_dict = metric.dict() if hasattr(metric, 'dict') else metric
                        metric_dict["associated_data_mart_goal"] = question
                        discovered_metrics = [metric_dict if m == metric else m for m in discovered_metrics]
                result["discovered_metrics"] = discovered_metrics
            
            all_discovered_metrics.extend(discovered_metrics)
            all_metric_plans.extend(result.get("metric_plans", []))
            all_generated_sql.update(result.get("generated_sql", {}))
            all_errors.extend(result.get("errors", []))
        
        return {
            "discovered_metrics": all_discovered_metrics,
            "metric_plans": all_metric_plans,
            "generated_sql": all_generated_sql,
            "errors": all_errors
        }
    
    def _associate_metrics_with_data_mart_goals(
        self,
        state: Dict,
        data_mart_goals: List[str],
        discovered_metrics: List[Dict[str, Any]]
    ):
        """
        Associate discovered metrics with their corresponding data mart goals AND specific data marts.
        Updates data mart plans and individual marts with associated metrics.
        
        Args:
            state: Current workflow state
            data_mart_goals: List of data mart goals
            discovered_metrics: List of discovered metric dictionaries
        """
        # Get data mart plans from state
        data_mart_plans = state.get("data_mart_plans", [])
        
        # Group metrics by associated goal
        metrics_by_goal = {}
        for metric in discovered_metrics:
            if isinstance(metric, dict):
                goal = metric.get("associated_data_mart_goal")
                if goal:
                    if goal not in metrics_by_goal:
                        metrics_by_goal[goal] = []
                    metrics_by_goal[goal].append(metric)
        
        # Update data mart plans and individual marts with associated metrics
        for plan in data_mart_plans:
            if isinstance(plan, dict):
                goal = plan.get("goal", "")
                marts = plan.get("marts", [])
                
                # Associate metrics with the goal (plan level)
                if goal in metrics_by_goal:
                    plan["associated_metrics"] = metrics_by_goal[goal]
                    logger.info(f"Associated {len(metrics_by_goal[goal])} metrics with data mart goal: {goal}")
                
                # Associate metrics with each specific data mart
                # Since a goal can have multiple marts, we associate all goal metrics with each mart
                # (or we could use semantic matching to associate specific metrics to specific marts)
                for mart in marts:
                    if isinstance(mart, dict):
                        mart_name = mart.get("mart_name", "")
                        if goal in metrics_by_goal:
                            # Initialize associated_metrics if not present
                            if "associated_metrics" not in mart:
                                mart["associated_metrics"] = []
                            
                            # Add metrics to this mart (avoid duplicates)
                            existing_metric_names = {m.get("metric_name") for m in mart["associated_metrics"] if isinstance(m, dict)}
                            for metric in metrics_by_goal[goal]:
                                metric_name = metric.get("metric_name", "")
                                if metric_name not in existing_metric_names:
                                    # Create a copy of the metric with mart-specific association
                                    mart_metric = metric.copy()
                                    mart_metric["associated_data_mart"] = mart_name
                                    mart["associated_metrics"].append(mart_metric)
                                    existing_metric_names.add(metric_name)
                            
                            logger.info(f"Associated {len(mart['associated_metrics'])} metrics with data mart: {mart_name}")
        
        # Also store in state for easy access
        if "metrics_by_data_mart_goal" not in state:
            state["metrics_by_data_mart_goal"] = {}
        state["metrics_by_data_mart_goal"].update(metrics_by_goal)
        
        # Store metrics by mart name for quick lookup
        if "metrics_by_data_mart" not in state:
            state["metrics_by_data_mart"] = {}
        
        for plan in data_mart_plans:
            if isinstance(plan, dict):
                marts = plan.get("marts", [])
                for mart in marts:
                    if isinstance(mart, dict):
                        mart_name = mart.get("mart_name", "")
                        mart_metrics = mart.get("associated_metrics", [])
                        if mart_metrics:
                            state["metrics_by_data_mart"][mart_name] = mart_metrics
    
    def _analyze_schemas(self, raw_ddls: list) -> Dict[str, Any]:
        """Analyze all schemas"""
        analyses = {}
        
        for ddl in raw_ddls:
            print(f"  Analyzing: {ddl.table_name}")
            analysis = self.schema_agent.analyze_ddl(
                ddl.table_name,
                ddl.table_ddl,
                ddl.relationships
            )
            analyses[ddl.table_name] = analysis
        
        return analyses
    
    def _plan_transformations(
        self,
        schema_analyses: Dict,
        lod_configs: list,
        relationships: list
    ) -> Dict[str, Any]:
        """Plan all transformations"""
        plans = {
            "raw_to_silver": {},
            "silver_to_gold": {}
        }
        
        # Raw to Silver transformations
        for table_name, analysis in schema_analyses.items():
            print(f"  Planning raw→silver for: {table_name}")
            
            # Find LOD config for this table
            from app.agents.cubes.transformation_planner_agent import LODDeduplication
            lod = next(
                (LODDeduplication(
                    lod_type=lod.lod_type,
                    dimensions=lod.dimensions,
                    tie_breaker="updated_at"  # Default
                ) for lod in lod_configs if lod.table_name == table_name),
                None
            )
            
            steps = self.transform_agent.plan_raw_to_silver(
                table_name,
                analysis.dict(),
                lod
            )
            plans["raw_to_silver"][table_name] = steps
        
        # Silver to Gold transformations
        for table_name, analysis in schema_analyses.items():
            print(f"  Planning silver→gold for: {table_name}")
            
            steps = self.transform_agent.plan_silver_to_gold(
                table_name,
                analysis.dict(),
                {"aggregation_type": "daily"}  # Default
            )
            plans["silver_to_gold"][table_name] = steps
        
        return plans
    
    def _convert_metrics_to_transformation_steps(
        self,
        discovered_metrics_result: Dict[str, Any]
    ) -> List[Any]:
        """
        Convert discovered metrics to transformation steps.
        
        Args:
            discovered_metrics_result: Result from metric discovery agent
            
        Returns:
            List of TransformationStep objects
        """
        from app.agents.cubes.transformation_planner_agent import TransformationStep, TransformationType
        
        steps = []
        generated_sql = discovered_metrics_result.get("generated_sql", {})
        discovered_metrics = discovered_metrics_result.get("discovered_metrics", [])
        
        for metric_data in discovered_metrics:
            # Handle both dict and Pydantic model formats
            if not isinstance(metric_data, dict):
                if hasattr(metric_data, 'dict'):
                    metric_data = metric_data.dict()
                else:
                    continue
            
            metric_name = metric_data.get("metric_name", "")
            sql_logic = generated_sql.get(metric_name, "")
            
            if not sql_logic:
                continue
            
            # Get layer from metric data, default to "gold"
            metric_layer = metric_data.get("layer", "gold")
            if hasattr(metric_layer, 'value'):  # If it's an enum
                metric_layer = metric_layer.value
            elif isinstance(metric_layer, str):
                metric_layer = metric_layer.lower()
            else:
                metric_layer = "gold"
            
            # Create step as dict to preserve all fields for later conversion
            # This will be converted to CubeTransformationStep in _generate_mdl_schema
            # Store as dict to include both transformation_planner_agent and cube_generation_agent fields
            step_dict = {
                "step_id": f"metric_{len(steps) + 1:03d}",
                "step_name": f"Metric: {metric_name}",
                "transformation_type": TransformationType.METRIC.value if hasattr(TransformationType.METRIC, 'value') else str(TransformationType.METRIC),
                "step_type": "metric",  # For cube_generation_agent format
                "input_tables": metric_data.get("source_tables", []),
                "output_table": f"gold_{metric_name.lower().replace(' ', '_')}",
                "sql_logic": sql_logic,
                "description": metric_data.get("metric_description", ""),
                "layer": metric_layer,  # Required for cube_generation_agent format
                "business_rules": metric_data.get("business_rules", []),
                "data_quality_checks": ["Verify metric calculation", "Check for null values"]
            }
            
            # Store as dict to preserve all fields including layer and step_type
            steps.append(step_dict)
        
        return steps
    
    def _generate_metric_definitions(
        self,
        discovered_metrics: List[Dict[str, Any]],
        workflow_name: str,
        timestamp: str
    ):
        """
        Generate cube.js and dbt definitions for discovered metrics.
        
        Args:
            discovered_metrics: List of discovered metric dictionaries
            workflow_name: Workflow name
            timestamp: Timestamp string
        """
        for metric_data in discovered_metrics:
            if isinstance(metric_data, dict):
                metric_name = metric_data.get("metric_name", "")
                metric_desc = metric_data.get("metric_description", "")
                metric_type = metric_data.get("metric_type", "count")
                dimensions = metric_data.get("dimensions", [])
                sql_logic = metric_data.get("sql_logic", "")
                
                if not sql_logic:
                    continue
                
                # Generate cube.js definition
                cube_def = {
                    "name": f"gold_{metric_name.lower().replace(' ', '_')}",
                    "sql": sql_logic.split("AS")[0] + "AS" if "AS" in sql_logic else sql_logic,
                    "dimensions": [
                        {
                            "name": dim,
                            "type": "string",
                            "sql": f"${{CUBE}}.{dim}",
                            "description": f"Dimension: {dim}"
                        }
                        for dim in dimensions
                    ],
                    "measures": [
                        {
                            "name": metric_name,
                            "type": metric_type if metric_type in ["count", "sum", "avg"] else "sum",
                            "sql": f"${{CUBE}}.{metric_name}",
                            "description": metric_desc
                        }
                    ],
                    "description": metric_desc,
                    "layer": "gold"
                }
                
                # Save cube.js JSON
                cube_path = self.output_dir / "cubes" / "gold" / f"{metric_name.lower().replace(' ', '_')}.json"
                cube_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cube_path, 'w') as f:
                    json.dump(cube_def, f, indent=2)
                
                # Generate dbt model
                dbt_sql = f"""-- dbt model: {metric_name}
{{{{ config(materialized='table') }}}}

{sql_logic.replace('CREATE TABLE', 'SELECT').replace('AS', '')}"""
                
                dbt_path = self.output_dir / "dbt" / "models" / "gold" / f"{metric_name.lower().replace(' ', '_')}.sql"
                dbt_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dbt_path, 'w') as f:
                    f.write(dbt_sql)
                
                logger.info(f"Generated cube.js and dbt definitions for metric: {metric_name}")
    
    def _generate_enhanced_cubes(
        self,
        schema_analyses: Dict,
        transformation_plans: Dict
    ) -> Dict[str, Any]:
        """Generate enhanced cube definitions"""
        cubes = {
            "raw": {},
            "silver": {},
            "gold": {}
        }
        
        total_tables = len(schema_analyses)
        total_cubes = total_tables * 3  # raw, silver, gold for each table
        current_cube = 0
        
        logger.info(f"Generating enhanced cubes: {total_tables} tables × 3 layers = {total_cubes} cubes total")
        
        # Generate cubes for each layer
        for table_idx, (table_name, analysis) in enumerate(schema_analyses.items(), 1):
            print(f"  Generating cubes for: {table_name} ({table_idx}/{total_tables})")
            
            # Raw cube
            current_cube += 1
            print(f"    [{current_cube}/{total_cubes}] Generating raw cube...")
            logger.info(f"Generating raw cube for {table_name} ({current_cube}/{total_cubes})")
            try:
                cubes["raw"][table_name] = self.cubejs_agent.generate_cube(
                    f"raw_{table_name}",
                    analysis.dict(),
                    layer="raw"
                )
                logger.info(f"✓ Raw cube generated for {table_name}")
            except Exception as e:
                logger.error(f"Error generating raw cube for {table_name}: {e}")
                raise
            
            # Silver cube
            current_cube += 1
            print(f"    [{current_cube}/{total_cubes}] Generating silver cube...")
            logger.info(f"Generating silver cube for {table_name} ({current_cube}/{total_cubes})")
            try:
                cubes["silver"][table_name] = self.cubejs_agent.generate_cube(
                    f"silver_{table_name}",
                    analysis.dict(),
                    layer="silver"
                )
                logger.info(f"✓ Silver cube generated for {table_name}")
            except Exception as e:
                logger.error(f"Error generating silver cube for {table_name}: {e}")
                raise
            
            # Gold cube
            current_cube += 1
            print(f"    [{current_cube}/{total_cubes}] Generating gold cube...")
            logger.info(f"Generating gold cube for {table_name} ({current_cube}/{total_cubes})")
            try:
                cubes["gold"][table_name] = self.cubejs_agent.generate_cube(
                    f"gold_{table_name}",
                    analysis.dict(),
                    layer="gold"
                )
                logger.info(f"✓ Gold cube generated for {table_name}")
            except Exception as e:
                logger.error(f"Error generating gold cube for {table_name}: {e}")
                raise
        
        logger.info(f"✓ Enhanced cube generation complete: {total_cubes} cubes generated")
        print(f"  ✓ Generated {total_cubes} enhanced cubes")
        return cubes
    
    def _enhance_data_marts_with_transformations(
        self,
        data_mart_plans: List[Dict[str, Any]],
        silver_result: Dict,
        gold_result: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Enhance data marts with transformations using LLM.
        This creates a graph that adds transformations to enhance data marts.
        
        Args:
            data_mart_plans: List of data mart plans from human-in-the-loop
            silver_result: Silver layer results
            gold_result: Gold layer results (optional)
            
        Returns:
            List of enhanced data mart definitions with transformations
        """
        enhanced_marts = []
        
        for plan in data_mart_plans:
            goal = plan.get("goal", "")
            marts = plan.get("marts", [])
            
            for mart in marts:
                mart_name = mart.get("mart_name", "")
                original_sql = mart.get("sql", "")
                description = mart.get("description", "")
                
                print(f"  Enhancing data mart: {mart_name}")
                
                # Use SQL generator to enhance data mart SQL
                try:
                    # Parse source tables from original SQL or mart info
                    source_tables = mart.get("source_tables", [])
                    if not source_tables:
                        # Try to extract from SQL
                        import re
                        from_matches = re.findall(r'FROM\s+(\w+)', original_sql, re.IGNORECASE)
                        join_matches = re.findall(r'JOIN\s+(\w+)', original_sql, re.IGNORECASE)
                        source_tables = list(set(from_matches + join_matches))
                    
                    # Use SQL generator to enhance
                    enhanced_sql = self.sql_generator.generate_data_mart_sql(
                        mart_name=mart_name,
                        description=f"{description}\n\nOriginal SQL:\n{original_sql}",
                        source_tables=source_tables,
                        business_rules=[goal, description],
                        target_dialect=SQLDialect.POSTGRESQL  # Will be converted to target dialect if needed
                    )
                    
                    enhanced_mart = {
                        **mart,
                        "enhanced_sql": enhanced_sql,
                        "original_sql": original_sql,
                        "has_enhancements": True
                    }
                    enhanced_marts.append(enhanced_mart)
                    
                except Exception as e:
                    logger.error(f"Error enhancing data mart {mart_name}: {str(e)}")
                    # Fallback to original
                    enhanced_mart = {
                        **mart,
                        "enhanced_sql": original_sql,
                        "original_sql": original_sql,
                        "has_enhancements": False,
                        "error": str(e)
                    }
                    enhanced_marts.append(enhanced_mart)
        
        return enhanced_marts
    
    def _generate_gold_metrics(
        self,
        enhanced_data_marts: List[Dict[str, Any]],
        gold_result: Optional[Dict],
        schema_analyses: Dict,
        gold_metrics_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate gold layer metrics based on DDL, dimensions, and measures from data marts.
        
        Args:
            enhanced_data_marts: Enhanced data mart definitions
            gold_result: Gold layer results
            schema_analyses: Schema analyses for understanding structure
            
        Returns:
            Dictionary of gold metrics with dimensions and measures
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        
        gold_metrics = {
            "metrics": [],
            "dimensions": [],
            "measures": []
        }
        
        # Extract metrics from data marts
        for mart in enhanced_data_marts:
            mart_name = mart.get("mart_name", "")
            enhanced_sql = mart.get("enhanced_sql", "")
            description = mart.get("description", "")
            
            print(f"  Generating metrics for: {mart_name}")
            
            system_prompt = """You are a data modeling expert. Analyze SQL CREATE TABLE statements 
and extract:
1. Dimensions (categorical fields for grouping)
2. Measures (numeric fields for aggregation)
3. Metrics (calculated business metrics)

Return a JSON structure with dimensions, measures, and metrics."""
            
            # Use gold_metrics_config if provided
            config_hint = ""
            if gold_metrics_config:
                dimensions_hint = gold_metrics_config.get("dimensions", [])
                measures_hint = gold_metrics_config.get("measures", [])
                if dimensions_hint or measures_hint:
                    config_hint = f"\n\nExpected dimensions (if present): {', '.join(dimensions_hint)}\nExpected measures (if present): {', '.join(measures_hint)}"
            
            user_prompt = f"""Analyze this data mart SQL and extract dimensions, measures, and metrics:

Mart Name: {mart_name}
Description: {description}

SQL:
{enhanced_sql}{config_hint}

Return JSON with this structure:
{{
    "dimensions": [
        {{"name": "dimension_name", "type": "string|date|numeric", "description": "..."}}
    ],
    "measures": [
        {{"name": "measure_name", "type": "sum|avg|count|max|min", "description": "..."}}
    ],
    "metrics": [
        {{"name": "metric_name", "formula": "calculation", "description": "..."}}
    ]
}}"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            try:
                response = self.llm.invoke(messages)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # Parse JSON from response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    metrics_data = json.loads(json_match.group(0))
                    
                    # Add mart context
                    for dim in metrics_data.get("dimensions", []):
                        dim["mart_name"] = mart_name
                        gold_metrics["dimensions"].append(dim)
                    
                    for measure in metrics_data.get("measures", []):
                        measure["mart_name"] = mart_name
                        gold_metrics["measures"].append(measure)
                    
                    for metric in metrics_data.get("metrics", []):
                        metric["mart_name"] = mart_name
                        gold_metrics["metrics"].append(metric)
                        
            except Exception as e:
                logger.error(f"Error generating metrics for {mart_name}: {str(e)}")
                continue
        
        return gold_metrics
    
    def _generate_mdl_schema(
        self,
        state: AgentState,
        silver_result: Dict,
        gold_result: Optional[Dict],
        schema_analyses: Dict,
        transformation_plans: Dict,
        enhanced_cubes: Dict,
        enhanced_data_marts: Optional[List[Dict[str, Any]]],
        gold_metrics: Optional[Dict[str, Any]],
        workflow_config: Dict[str, Any]
    ):
        """Generate MDL schema from all agent outputs"""
        # Update MDL generator with catalog/schema from config
        catalog = workflow_config.get("catalog", "default_catalog")
        schema = workflow_config.get("schema", "public")
        self.mdl_generator.catalog = catalog
        self.mdl_generator.schema = schema
        
        # Get discovered metrics from state
        discovered_metrics = state.get("discovered_metrics", [])
        
        # Extract cubes from results
        raw_cubes = [
            CubeDefinition(**cube) if isinstance(cube, dict) else cube
            for cube in silver_result.get("raw_cubes", [])
        ]
        silver_cubes = [
            CubeDefinition(**cube) if isinstance(cube, dict) else cube
            for cube in silver_result.get("silver_cubes", [])
        ]
        gold_cubes = []
        if gold_result:
            gold_cubes = [
                CubeDefinition(**cube) if isinstance(cube, dict) else cube
                for cube in gold_result.get("gold_cubes", [])
            ]
        
        # Extract views
        views = []
        if gold_result:
            views = [
                ViewDefinition(**view) if isinstance(view, dict) else view
                for view in gold_result.get("views", [])
            ]
        
        # Extract transformation steps
        # Use cube_generation_agent.TransformationStep which has step_type and layer
        from app.agents.cubes.cube_generation_agent import TransformationStep as CubeTransformationStep
        
        raw_to_silver_steps = []
        for step in silver_result.get("raw_to_silver_transformations", []):
            if isinstance(step, dict):
                # Convert transformation_planner_agent format to cube_generation_agent format
                converted_step = {
                    "step_name": step.get("step_name", ""),
                    "step_type": step.get("transformation_type", step.get("step_type", "transform")),
                    "sql_logic": step.get("sql_logic", ""),
                    "description": step.get("description", ""),
                    "input_tables": step.get("input_tables", []),
                    "output_table": step.get("output_table", ""),
                    "layer": step.get("layer", "silver")
                }
                raw_to_silver_steps.append(CubeTransformationStep(**converted_step))
            else:
                raw_to_silver_steps.append(step)
        
        silver_to_gold_steps = []
        if gold_result:
            for step in gold_result.get("silver_to_gold_transformations", []):
                if isinstance(step, dict):
                    # Convert transformation_planner_agent format to cube_generation_agent format
                    # Handle both enum and string values for transformation_type
                    trans_type = step.get("transformation_type", step.get("step_type", "transform"))
                    if hasattr(trans_type, 'value'):  # If it's an enum
                        trans_type = trans_type.value
                    elif not isinstance(trans_type, str):
                        trans_type = str(trans_type)
                    
                    converted_step = {
                        "step_name": step.get("step_name", ""),
                        "step_type": trans_type,
                        "sql_logic": step.get("sql_logic", ""),
                        "description": step.get("description", ""),
                        "input_tables": step.get("input_tables", []),
                        "output_table": step.get("output_table", ""),
                        "layer": step.get("layer", "gold")
                    }
                    silver_to_gold_steps.append(CubeTransformationStep(**converted_step))
                else:
                    silver_to_gold_steps.append(step)
        
        # Get relationships and LOD configs from state
        relationships = state.get("relationship_mappings", [])
        lod_configs = state.get("lod_configs", [])
        
        # Generate MDL schema
        mdl_schema = self.mdl_generator.generate_mdl_schema(
            table_metadata=state.get("table_metadata", []),
            raw_cubes=raw_cubes,
            silver_cubes=silver_cubes,
            gold_cubes=gold_cubes,
            views=views,
            raw_to_silver_steps=raw_to_silver_steps,
            silver_to_gold_steps=silver_to_gold_steps,
            relationships=relationships,
            lod_configs=lod_configs,
            data_mart_plans=state.get("data_mart_plans"),
            gold_metrics=gold_metrics
        )
        
        # Add discovered metrics to MDL schema
        if discovered_metrics:
            from app.agents.cubes.mdl_schema_generator import MDLMetric, MDLColumn
            metric_objects = []
            for metric_data in discovered_metrics:
                if isinstance(metric_data, dict):
                    metric_name = metric_data.get("metric_name", "")
                    metric_desc = metric_data.get("metric_description", "")
                    metric_type = metric_data.get("metric_type", "count")
                    dimensions = metric_data.get("dimensions", [])
                    
                    # Create MDL metric
                    mdl_dimensions = [
                        MDLColumn(
                            name=dim,
                            type="VARCHAR",
                            properties={"description": f"Dimension: {dim}"}
                        )
                        for dim in dimensions
                    ]
                    
                    mdl_measure = MDLColumn(
                        name=metric_name,
                        type="DOUBLE",
                        isCalculated=True,
                        expression=metric_data.get("sql_logic", ""),
                        properties={
                            "description": metric_desc,
                            "aggregation": metric_type,
                            "formula": metric_data.get("formula_description", "")
                        }
                    )
                    
                    # Build properties including data mart goal and mart association
                    properties = {
                        "description": metric_desc,
                        "layer": metric_data.get("layer", "gold"),
                        "business_rules": ", ".join(metric_data.get("business_rules", []))
                    }
                    associated_goal = metric_data.get("associated_data_mart_goal")
                    associated_mart = metric_data.get("associated_data_mart")
                    if associated_goal:
                        properties["associated_data_mart_goal"] = associated_goal
                    if associated_mart:
                        properties["associated_data_mart"] = associated_mart
                    
                    metric_obj = MDLMetric(
                        name=metric_name,
                        baseObject=metric_data.get("source_tables", [""])[0] if metric_data.get("source_tables") else "unknown",
                        dimension=mdl_dimensions,
                        measure=[mdl_measure],
                        properties=properties
                    )
                    metric_objects.append(metric_obj)
            
            # Add metrics to schema
            mdl_schema.metrics.extend(metric_objects)
            logger.info(f"Added {len(metric_objects)} discovered metrics to MDL schema")
        
        return mdl_schema
    
    def _transform_mdl_to_targets(
        self,
        mdl_schema,
        workflow_name: str,
        timestamp: str,
        workflow_config: Dict[str, Any]
    ) -> Dict[str, list]:
        """Transform MDL schema to target formats (Cube.js, dbt)"""
        saved_paths = {
            "cubes": [],
            "dbt_models": [],
            "dbt_schema": [],
            "transformations": []
        }
        
        # Transform to Cube.js
        if workflow_config.get("output_formats", []):
            if "cubejs" in workflow_config.get("output_formats", []):
                for layer in ["raw", "silver", "gold"]:
                    cube_dir = self.output_dir / "cubes" / layer
                    cube_files = self.cubejs_transformer.generate_cubejs_files(
                        mdl_schema,
                        cube_dir,
                        layer=layer
                    )
                    saved_paths["cubes"].extend(cube_files)
        
        # Transform to dbt
        if workflow_config.get("enable_dbt_generation", True):
            for layer in ["raw", "silver", "gold"]:
                dbt_dir = self.output_dir / "dbt" / "models" / layer
                dbt_files = self.dbt_transformer.generate_dbt_files(
                    mdl_schema,
                    dbt_dir.parent,  # Pass parent to create models/{layer} structure
                    layer=layer
                )
                saved_paths["dbt_models"].extend([f for f in dbt_files if f.endswith('.sql')])
                schema_files = [f for f in dbt_files if f.endswith('schema.yml')]
                if schema_files:
                    saved_paths["dbt_schema"].extend(schema_files)
        
        # Export transformations
        trans_dir = self.output_dir / "transformations"
        trans_files = self.transformations_exporter.export_transformations(
            mdl_schema,
            trans_dir
        )
        saved_paths["transformations"].extend(trans_files)
        
        return saved_paths
    
    def _generate_nl_questions(
        self,
        state: AgentState,
        silver_result: Dict,
        gold_result: Optional[Dict],
        transformation_plans: Dict,
        enhanced_cubes: Dict,
        enhanced_data_marts: Optional[List[Dict[str, Any]]],
        workflow_config: Dict[str, Any]
    ) -> List[str]:
        """Generate natural language questions for all components"""
        all_questions = []
        saved_files = []
        
        # Get table metadata for context
        table_metadata_dict = {
            meta.table_name: meta
            for meta in state.get("table_metadata", [])
        }
        
        # 1. Generate transformation questions (raw to silver)
        print("  Generating raw→silver transformation questions...")
        try:
            raw_to_silver_steps = [
                TransformationStep(**step) if isinstance(step, dict) else step
                for step in silver_result.get("raw_to_silver_transformations", [])
            ]
            
            if raw_to_silver_steps:
                # Group by table
                for table_name in transformation_plans.get("raw_to_silver", {}).keys():
                    try:
                        table_steps = [s for s in raw_to_silver_steps if getattr(s, "output_table", getattr(s, "table_name", "")) == table_name]
                        if table_steps:
                            table_meta = table_metadata_dict.get(table_name)
                            # Find LOD config - handle both dict and object formats
                            lod_config = None
                            for lod in state.get("lod_configs", []):
                                try:
                                    lod_table_name = lod.table_name if hasattr(lod, 'table_name') else lod.get("table_name", "") if isinstance(lod, dict) else ""
                                    if lod_table_name == table_name:
                                        lod_config = lod.dict() if hasattr(lod, 'dict') else lod
                                        break
                                except Exception as e:
                                    logger.debug(f"Error accessing LOD config: {e}")
                                    continue
                            
                            trans_questions = self.nl_question_generator.generate_transformation_questions(
                                transformation_steps=table_steps,
                                source_layer="raw",
                                target_layer="silver",
                                table_metadata=table_meta,
                                lod_config=lod_config
                            )
                            all_questions.extend(trans_questions)
                    except Exception as e:
                        logger.error(f"Error generating transformation questions for {table_name}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error in raw→silver transformation question generation: {e}")
        
        # 2. Generate transformation questions (silver to gold)
        if gold_result:
            print("  Generating silver→gold transformation questions...")
            try:
                silver_to_gold_steps = [
                    TransformationStep(**step) if isinstance(step, dict) else step
                    for step in gold_result.get("silver_to_gold_transformations", [])
                ]
                
                if silver_to_gold_steps:
                    for table_name in transformation_plans.get("silver_to_gold", {}).keys():
                        try:
                            table_steps = [s for s in silver_to_gold_steps if getattr(s, "output_table", getattr(s, "table_name", "")) == table_name]
                            if table_steps:
                                table_meta = table_metadata_dict.get(table_name)
                                
                                trans_questions = self.nl_question_generator.generate_transformation_questions(
                                    transformation_steps=table_steps,
                                    source_layer="silver",
                                    target_layer="gold",
                                    table_metadata=table_meta
                                )
                                all_questions.extend(trans_questions)
                        except Exception as e:
                            logger.error(f"Error generating transformation questions for {table_name}: {e}")
                            continue
            except Exception as e:
                logger.error(f"Error in silver→gold transformation question generation: {e}")
        
        # 3. Generate cube questions for each layer
        print("  Generating cube building questions...")
        try:
            relationships = state.get("relationship_mappings", [])
            
            for layer in ["raw", "silver", "gold"]:
                cubes = enhanced_cubes.get(layer, {})
                for table_name, cube in cubes.items():
                    try:
                        cube_obj = CubeDefinition(**cube) if isinstance(cube, dict) else cube
                        table_meta = table_metadata_dict.get(table_name)
                        # Handle both dict and object formats for relationships
                        table_relationships = []
                        for r in relationships:
                            try:
                                child_table = r.child_table if hasattr(r, 'child_table') else r.get("child_table", "") if isinstance(r, dict) else ""
                                parent_table = r.parent_table if hasattr(r, 'parent_table') else r.get("parent_table", "") if isinstance(r, dict) else ""
                                if child_table == table_name or parent_table == table_name:
                                    table_relationships.append(r)
                            except Exception as e:
                                logger.debug(f"Error accessing relationship: {e}")
                                continue
                        
                        cube_questions = self.nl_question_generator.generate_cube_questions(
                            cubes=[cube_obj],
                            layer=layer,
                            table_metadata=table_meta,
                            relationships=table_relationships
                        )
                        all_questions.extend(cube_questions)
                    except Exception as e:
                        logger.error(f"Error generating cube questions for {table_name} in {layer} layer: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error in cube question generation: {e}")
        
        # 4. Generate SQL questions for data marts
        if enhanced_data_marts:
            print("  Generating SQL questions for data marts...")
            for mart in enhanced_data_marts:
                mart_name = mart.get("mart_name", "")
                enhanced_sql = mart.get("enhanced_sql", "")
                description = mart.get("description", "")
                goal = mart.get("goal", "")
                
                # Extract source tables from SQL or context
                source_tables = mart.get("source_tables", [])
                if not source_tables:
                    # Try to infer from state
                    source_tables = [meta.table_name for meta in state.get("table_metadata", [])]
                
                sql_question = self.nl_question_generator.generate_sql_questions(
                    sql_type="data_mart",
                    target_object=mart_name,
                    source_tables=source_tables,
                    business_requirements=[goal, description] if goal or description else ["Create data mart for analytics"],
                    sql_content=enhanced_sql,
                    description=description
                )
                all_questions.append(sql_question)
        
        # 5. Generate SQL questions for transformations
        print("  Generating SQL questions for transformations...")
        for layer_transition in ["raw_to_silver", "silver_to_gold"]:
            for table_name, steps in transformation_plans.get(layer_transition, {}).items():
                source_layer, target_layer = layer_transition.split("_to_")
                table_meta = table_metadata_dict.get(table_name)
                
                business_reqs = [
                    f"Transform {table_name} from {source_layer} to {target_layer}",
                    f"Apply data quality checks",
                    f"Handle deduplication if needed"
                ]
                
                if table_meta and table_meta.description:
                    business_reqs.append(f"Maintain business logic: {table_meta.description}")
                
                sql_question = self.nl_question_generator.generate_sql_questions(
                    sql_type="transformation",
                    target_object=f"{target_layer}_{table_name}",
                    source_tables=[table_name],
                    business_requirements=business_reqs
                )
                all_questions.append(sql_question)
        
        # Save all questions
        questions_dir = self.output_dir / "nl_questions"
        saved_files = self.nl_question_generator.save_questions(
            all_questions,
            str(questions_dir),
            category="workflow"
        )
        
        # Also save by category
        trans_questions = [q for q in all_questions if q.question_id.startswith("trans_")]
        cube_questions = [q for q in all_questions if q.question_id.startswith("cube_")]
        sql_questions = [q for q in all_questions if q.question_id.startswith("sql_")]
        
        if trans_questions:
            self.nl_question_generator.save_questions(
                trans_questions,
                str(questions_dir / "transformations"),
                category="transformation"
            )
        
        if cube_questions:
            self.nl_question_generator.save_questions(
                cube_questions,
                str(questions_dir / "cubes"),
                category="cube"
            )
        
        if sql_questions:
            self.nl_question_generator.save_questions(
                sql_questions,
                str(questions_dir / "sql"),
                category="sql"
            )
        
        return saved_files
    
    def _save_all_artifacts(
        self,
        workflow_name: str,
        timestamp: str,
        result: Dict,
        schema_analyses: Dict,
        transformation_plans: Dict,
        enhanced_cubes: Dict,
        gold_result: Optional[Dict] = None,
        state: Optional[AgentState] = None,
        enhanced_data_marts: Optional[List[Dict[str, Any]]] = None,
        gold_metrics: Optional[Dict[str, Any]] = None,
        workflow_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, list]:
        """Save all generated artifacts to files"""
        saved_paths = {
            "cubes": [],
            "views": [],
            "transformations": [],
            "sql": [],
            "analyses": [],
            "data_marts": [],
            "dbt_models": [],
            "dbt_schema": [],
            "gold_metrics": []
        }
        
        # Save cube definitions
        for layer in ["raw", "silver", "gold"]:
            for table_name, cube in enhanced_cubes[layer].items():
                # JSON format
                json_path = self.output_dir / f"cubes/{layer}/{table_name}.json"
                with open(json_path, 'w') as f:
                    json.dump(cube.dict(), f, indent=2)
                saved_paths["cubes"].append(str(json_path))
                
                # JavaScript format
                js_path = self.output_dir / f"cubes/{layer}/{table_name}.js"
                with open(js_path, 'w') as f:
                    f.write(self.cubejs_agent.export_to_javascript(cube))
                saved_paths["cubes"].append(str(js_path))
        
        # Save transformation SQL
        for layer_transition in ["raw_to_silver", "silver_to_gold"]:
            for table_name, steps in transformation_plans[layer_transition].items():
                sql_path = self.output_dir / f"sql/{layer_transition}/{table_name}.sql"
                with open(sql_path, 'w') as f:
                    f.write(f"-- Transformation: {layer_transition}\n")
                    f.write(f"-- Table: {table_name}\n")
                    f.write(f"-- Generated: {timestamp}\n\n")
                    
                    for step in steps:
                        f.write(f"-- Step: {step.step_name}\n")
                        f.write(f"-- Type: {step.transformation_type}\n")
                        f.write(f"-- Description: {step.description}\n\n")
                        f.write(step.sql_logic)
                        f.write("\n\n")
                        f.write("-" * 80)
                        f.write("\n\n")
                
                saved_paths["sql"].append(str(sql_path))
        
        # Save transformation plans
        for layer_transition in ["raw_to_silver", "silver_to_gold"]:
            for table_name, steps in transformation_plans[layer_transition].items():
                plan_path = self.output_dir / f"transformations/{layer_transition}/{table_name}.json"
                with open(plan_path, 'w') as f:
                    json.dump([step.dict() for step in steps], f, indent=2)
                saved_paths["transformations"].append(str(plan_path))
        
        # Save schema analyses
        for table_name, analysis in schema_analyses.items():
            analysis_path = self.output_dir / f"documentation/{table_name}_analysis.json"
            with open(analysis_path, 'w') as f:
                json.dump(analysis.dict(), f, indent=2)
            saved_paths["analyses"].append(str(analysis_path))
        
        # Save data mart plans if available
        if state and "data_mart_plans" in state:
            data_mart_dir = self.output_dir / "data_marts"
            data_mart_dir.mkdir(parents=True, exist_ok=True)
            
            for i, plan in enumerate(state["data_mart_plans"]):
                plan_path = data_mart_dir / f"data_mart_plan_{i+1}.json"
                with open(plan_path, 'w') as f:
                    json.dump(plan, f, indent=2)
                saved_paths["data_marts"].append(str(plan_path))
                
                # Also save SQL files for each data mart
                for mart in plan.get("marts", []):
                    sql_path = data_mart_dir / f"{mart.get('mart_name', f'mart_{i+1}')}.sql"
                    with open(sql_path, 'w') as f:
                        f.write(f"-- Data Mart: {mart.get('mart_name', '')}\n")
                        f.write(f"-- Goal: {plan.get('goal', '')}\n")
                        f.write(f"-- Question: {mart.get('natural_language_question', '')}\n")
                        f.write(f"-- Generated: {timestamp}\n\n")
                        f.write(mart.get('sql', ''))
                    saved_paths["sql"].append(str(sql_path))
        
        # Save enhanced data marts
        workflow_config = workflow_config or {}
        enable_enhanced = workflow_config.get("enable_enhanced_data_marts", True)
        enable_dbt = workflow_config.get("enable_dbt_generation", True)
        
        if enhanced_data_marts and enable_enhanced:
            for mart in enhanced_data_marts:
                mart_name = mart.get("mart_name", "")
                enhanced_sql = mart.get("enhanced_sql", "")
                
                if enhanced_sql:
                    # Save enhanced SQL
                    enhanced_path = data_mart_dir / f"{mart_name}_enhanced.sql"
                    with open(enhanced_path, 'w') as f:
                        f.write(f"-- Enhanced Data Mart: {mart_name}\n")
                        f.write(f"-- Generated: {timestamp}\n\n")
                        f.write(enhanced_sql)
                    saved_paths["sql"].append(str(enhanced_path))
                    
                    # Generate and save dbt model if enabled
                    if enable_dbt:
                        dbt_model = self._generate_dbt_model(mart_name, enhanced_sql, mart)
                        dbt_path = self.output_dir / f"dbt/models/gold/{mart_name}.sql"
                        with open(dbt_path, 'w') as f:
                            f.write(dbt_model)
                        saved_paths["dbt_models"].append(str(dbt_path))
        
        # Generate and save dbt schema.yml if enabled
        if enable_dbt and (enhanced_data_marts or gold_metrics):
            dbt_schema = self._generate_dbt_schema(enhanced_data_marts, gold_metrics, schema_analyses)
            schema_path = self.output_dir / "dbt/schema.yml"
            with open(schema_path, 'w') as f:
                f.write(dbt_schema)
            saved_paths["dbt_schema"].append(str(schema_path))
        
        # Save gold metrics
        if gold_metrics:
            metrics_path = self.output_dir / "documentation/gold_metrics.json"
            with open(metrics_path, 'w') as f:
                json.dump(gold_metrics, f, indent=2)
            saved_paths["gold_metrics"].append(str(metrics_path))
        
        return saved_paths
    
    def _generate_dbt_model(
        self,
        mart_name: str,
        sql: str,
        mart_info: Dict[str, Any]
    ) -> str:
        """Generate a dbt model from SQL using SQL generator"""
        from app.agents.cubes.sql_generator_agent import SQLType
        
        try:
            # Use SQL generator to convert to dbt format
            request = {
                "sql_type": SQLType.DBT_MODEL,
                "description": f"dbt model for {mart_name}: {mart_info.get('description', '')}",
                "source_tables": [],  # Will be extracted from SQL
                "target_table": mart_name,
                "additional_context": {
                    "original_sql": sql,
                    "mart_name": mart_name,
                    "description": mart_info.get('description', '')
                }
            }
            
            result = self.sql_generator.generate_sql(request)
            return result.sql
        except Exception as e:
            logger.error(f"Error generating dbt model for {mart_name}: {str(e)}")
            # Fallback: basic dbt model
            import re
            # Extract SELECT part from CREATE TABLE AS SELECT
            select_sql = sql
            if "CREATE TABLE" in sql.upper() and "AS SELECT" in sql.upper():
                select_sql = re.sub(r'CREATE\s+TABLE\s+\w+\s+AS\s*', '', sql, flags=re.IGNORECASE)
            
            return f"""-- dbt model: {mart_name}
{{{{ config(materialized='table') }}}}

{select_sql}"""
    
    def _generate_dbt_schema(
        self,
        enhanced_data_marts: Optional[List[Dict[str, Any]]],
        gold_metrics: Optional[Dict[str, Any]],
        schema_analyses: Dict
    ) -> str:
        """Generate dbt schema.yml with models, columns, and metrics"""
        # Prepare context
        marts_info = []
        if enhanced_data_marts:
            for mart in enhanced_data_marts:
                marts_info.append({
                    "name": mart.get("mart_name", ""),
                    "description": mart.get("description", ""),
                    "sql": mart.get("enhanced_sql", "")[:500]  # Truncate for context
                })
        
        metrics_info = gold_metrics.get("metrics", []) if gold_metrics else []
        dimensions_info = gold_metrics.get("dimensions", []) if gold_metrics else []
        measures_info = gold_metrics.get("measures", []) if gold_metrics else []
        
        system_prompt = """You are a dbt expert. Generate a dbt schema.yml file with:
1. Model definitions with descriptions
2. Column definitions with data types and descriptions
3. Metrics definitions
4. Tests where appropriate

Follow dbt schema.yml format exactly."""
        
        user_prompt = f"""Generate a dbt schema.yml file for these data marts:

Data Marts:
{json.dumps(marts_info, indent=2)}

Metrics:
{json.dumps(metrics_info, indent=2)}

Dimensions:
{json.dumps(dimensions_info, indent=2)}

Measures:
{json.dumps(measures_info, indent=2)}

Generate a complete schema.yml with:
- version: 2
- models section with all marts
- columns with descriptions and tests
- metrics section

Return only the YAML, no explanations."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            schema_yaml = response.content if hasattr(response, 'content') else str(response)
            
            # Extract YAML from markdown if present
            import re
            yaml_match = re.search(r'```yaml\n(.*?)\n```', schema_yaml, re.DOTALL)
            if yaml_match:
                schema_yaml = yaml_match.group(1)
            else:
                yaml_match = re.search(r'```\n(.*?)\n```', schema_yaml, re.DOTALL)
                if yaml_match:
                    schema_yaml = yaml_match.group(1)
            
            return schema_yaml
        except Exception as e:
            logger.error(f"Error generating dbt schema: {str(e)}")
            # Fallback: basic schema
            return f"""version: 2

models:
  - name: {marts_info[0]['name'] if marts_info else 'data_mart'}
    description: Generated data mart model
"""

    def _generate_documentation(
        self,
        workflow_name: str,
        config: Dict,
        result: Dict,
        saved_paths: Dict,
        state: Optional[AgentState] = None,
        mdl_schema: Optional[Any] = None
    ):
        """Generate comprehensive documentation"""
        doc_path = self.output_dir / "documentation" / f"{workflow_name}_README.md"
        
        with open(doc_path, 'w') as f:
            f.write(f"# {workflow_name} - Data Model Documentation\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"## Overview\n\n")
            f.write(f"{config.get('description', 'No description provided')}\n\n")
            
            f.write(f"## Architecture\n\n")
            f.write(f"This data model follows the medallion architecture:\n\n")
            f.write(f"```\n")
            f.write(f"Raw Layer → Silver Layer → Gold Layer\n")
            f.write(f"```\n\n")
            
            f.write(f"### Raw Layer\n")
            f.write(f"Source tables with minimal transformation:\n\n")
            for schema in config["raw_schemas"]:
                f.write(f"- `{schema['table_name']}`\n")
            f.write("\n")
            
            f.write(f"### Silver Layer\n")
            f.write(f"Cleaned, deduplicated, and conformed data\n\n")
            
            # Add human-in-the-loop information
            if state and "table_analysis_configs" in state:
                f.write(f"#### Silver Table Analysis\n")
                f.write(f"Collected requirements for {len(state['table_analysis_configs'])} tables:\n\n")
                for config_data in state["table_analysis_configs"][:5]:  # Show first 5
                    f.write(f"- **{config_data.get('table_name', 'Unknown')}**:\n")
                    f.write(f"  - Analysis Types: {', '.join(config_data.get('analysis_types', []))}\n")
                    f.write(f"  - Business Goals: {len(config_data.get('business_goals', []))} goals\n")
                if len(state["table_analysis_configs"]) > 5:
                    f.write(f"- ... and {len(state['table_analysis_configs']) - 5} more tables\n")
                f.write("\n")
            
            f.write(f"### Gold Layer\n")
            f.write(f"Business-level aggregations and metrics\n\n")
            
            # Add data mart information
            if state and "data_mart_plans" in state and state["data_mart_plans"]:
                f.write(f"## Data Marts\n\n")
                f.write(f"Planned {len(state['data_mart_plans'])} data mart(s):\n\n")
                for i, plan in enumerate(state["data_mart_plans"], 1):
                    f.write(f"### Data Mart {i}: {plan.get('goal', 'Unknown Goal')}\n\n")
                    f.write(f"**Complexity**: {plan.get('complexity', 'medium')}\n\n")
                    f.write(f"**Marts**:\n")
                    for mart in plan.get("marts", []):
                        f.write(f"- **{mart.get('mart_name', 'Unknown')}**: {mart.get('description', '')}\n")
                        f.write(f"  - Question: {mart.get('natural_language_question', '')}\n")
                        f.write(f"  - Grain: {mart.get('grain', '')}\n")
                    f.write("\n")
            
            f.write(f"## MDL Schema (Single Source of Truth)\n\n")
            if mdl_schema:
                f.write(f"The complete MDL schema is available at: `mdl/{workflow_name}_schema.json`\n\n")
                f.write(f"This schema contains:\n")
                f.write(f"- **Models**: {len(mdl_schema.models)} models across raw, silver, and gold layers\n")
                f.write(f"- **Relationships**: {len(mdl_schema.relationships)} relationships\n")
                f.write(f"- **Metrics**: {len(mdl_schema.metrics)} metrics\n")
                f.write(f"- **Views**: {len(mdl_schema.views)} views\n")
                f.write(f"- **Transformations**: {len(mdl_schema.transformations)} transformations\n")
                if mdl_schema.governance:
                    f.write(f"- **Governance**: Data quality rules, compliance requirements, lineage\n")
                f.write("\n")
                f.write(f"All target formats (Cube.js, dbt) are generated from this MDL schema.\n\n")
            
            f.write(f"## Generated Artifacts\n\n")
            
            f.write(f"### Cubes (Generated from MDL)\n")
            for cube_path in saved_paths["cubes"][:10]:  # Show first 10
                f.write(f"- `{Path(cube_path).relative_to(self.output_dir)}`\n")
            if len(saved_paths["cubes"]) > 10:
                f.write(f"- ... and {len(saved_paths['cubes']) - 10} more\n")
            f.write("\n")
            
            f.write(f"### Transformations\n")
            for trans_path in saved_paths["transformations"]:
                f.write(f"- `{Path(trans_path).relative_to(self.output_dir)}`\n")
            f.write("\n")
            
            f.write(f"### SQL Scripts\n")
            for sql_path in saved_paths["sql"]:
                f.write(f"- `{Path(sql_path).relative_to(self.output_dir)}`\n")
            f.write("\n")
            
            if saved_paths.get("data_marts"):
                f.write(f"### Data Marts\n")
                for mart_path in saved_paths["data_marts"]:
                    f.write(f"- `{Path(mart_path).relative_to(self.output_dir)}`\n")
                f.write("\n")
            
            f.write(f"## Usage\n\n")
            f.write(f"1. Review generated Cube.js definitions in `cubes/`\n")
            f.write(f"2. Execute transformation SQL in `sql/` in order\n")
            f.write(f"3. Review data mart SQL in `data_marts/`\n")
            f.write(f"4. Deploy cube definitions to your Cube.js instance\n")
            f.write(f"5. Configure pre-aggregations based on query patterns\n\n")
            
            f.write(f"## Next Steps\n\n")
            f.write(f"1. Validate SQL transformations\n")
            f.write(f"2. Test cube definitions\n")
            f.write(f"3. Execute data mart SQL queries\n")
            f.write(f"4. Configure refresh schedules\n")
            f.write(f"5. Set up data quality monitoring\n")
        
        print(f"  Documentation saved: {doc_path}")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Execute Cube.js generation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full workflow
  python workflow_executor.py config.json --output-dir ./output

  # Run only silver layer generation
  python workflow_executor.py config.json --output-dir ./output --modeling_type silver

  # Run only gold layer generation (requires silver to be complete)
  python workflow_executor.py config.json --output-dir ./output --modeling_type gold

  # Run only transformation layer generation
  python workflow_executor.py config.json --output-dir ./output --modeling_type transform
        """
    )
    parser.add_argument(
        "config",
        help="Path to workflow configuration JSON file"
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Output directory for generated artifacts"
    )
    parser.add_argument(
        "--modeling_type",
        choices=["silver", "gold", "transform"],
        default=None,
        help="Modeling type to execute: 'silver' (silver layer), 'gold' (gold layer), or 'transform' (transformation layer). If not specified, runs full workflow."
    )
    
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # Execute workflow
    executor = WorkflowExecutor(
        output_dir=args.output_dir
    )
    
    result = executor.execute_workflow_sync(config, modeling_type=args.modeling_type)
    
    print("\n" + "="*80)
    print("WORKFLOW SUMMARY")
    print("="*80)
    print(f"Workflow: {result['workflow_name']}")
    if args.modeling_type:
        print(f"Modeling Type: {args.modeling_type}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Output Directory: {args.output_dir}")
    print(f"\nGenerated Artifacts:")
    
    saved_paths = result.get('saved_paths', {})
    if saved_paths.get('cubes'):
        print(f"  Cubes: {len(saved_paths['cubes'])} files")
    if saved_paths.get('transformations'):
        print(f"  Transformations: {len(saved_paths['transformations'])} files")
    if saved_paths.get('sql'):
        print(f"  SQL Scripts: {len(saved_paths['sql'])} files")
    if saved_paths.get('analyses'):
        print(f"  Analyses: {len(saved_paths['analyses'])} files")
    if result.get('data_mart_plans'):
        print(f"  Data Marts: {len(result['data_mart_plans'])} plan(s)")
        for i, plan in enumerate(result['data_mart_plans'], 1):
            print(f"    - Plan {i}: {plan.get('goal', 'Unknown')} ({len(plan.get('marts', []))} mart(s))")
    print("="*80)


if __name__ == "__main__":
    # Run as CLI if arguments provided, otherwise run example
    import sys
    
    if len(sys.argv) > 1:
        # CLI mode
        main()
    else:
        # Example: Run from Python directly
        from .workflow_examples import network_device_workflow
        
        print("Running example workflow (network_device_workflow)...")
        print("To run with a config file, use: python -m dataservices.app.agents.cubes.workflow_executor <config.json>")
        print()
        
        executor = WorkflowExecutor(output_dir="./output")
        result = executor.execute_workflow_sync(network_device_workflow)
        
        print("\n✅ Example workflow executed successfully!")
        print(f"📂 Check the output directory for generated files")
