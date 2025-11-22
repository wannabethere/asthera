"""
Pipeline Execution Planner
Generates execution plans for Trino materialized views, Spark, and Python transformations.
Creates natural language questions for automation agents.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger("genieml-agents")


class PipelineExecutionPlanner:
    """Plans and generates pipeline execution artifacts for Trino, Spark, and Python"""
    
    def __init__(
        self,
        llm,
        output_dir: Path,
        sql_generator: Optional[Any] = None
    ):
        """
        Initialize pipeline execution planner.
        
        Args:
            llm: LLM instance for code generation
            output_dir: Output directory for saving plans
            sql_generator: Optional SQL generator agent for dialect conversion
        """
        self.llm = llm
        self.output_dir = Path(output_dir)
        self.sql_generator = sql_generator
    
    def initialize_pipeline_plans(self) -> Dict[str, Any]:
        """
        Initialize empty pipeline plans structure.
        
        Returns:
            Empty pipeline plans dictionary
        """
        return {
            "trino_materialized_views": [],
            "spark_transformations": [],
            "python_transformations": [],
            "execution_order": []
        }
    
    def update_silver_pipeline_plans(
        self,
        pipeline_plans: Dict[str, Any],
        workflow_config: Dict[str, Any],
        silver_result: Dict,
        transformation_plans: Dict,
        state: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update pipeline plans with silver layer artifacts.
        Called after silver generation is complete.
        
        Args:
            pipeline_plans: Current pipeline plans (will be updated)
            workflow_config: Workflow configuration
            silver_result: Silver layer results
            transformation_plans: Transformation plans
            state: Current workflow state
            
        Returns:
            Updated pipeline plans dictionary
        """
        pipeline_config = workflow_config.get("pipeline_execution", {})
        
        if not pipeline_config:
            logger.debug("No pipeline execution configuration, skipping silver pipeline update")
            return pipeline_plans
        
        source_destination = pipeline_config.get("source_destination", {})
        trino_config = source_destination.get("trino", {})
        
        if not trino_config:
            logger.debug("No Trino configuration, skipping silver pipeline update")
            return pipeline_plans
        
        print("  Updating pipeline plans with silver layer artifacts...")
        
        # Plan silver Trino materialized views
        silver_mv_plans = []
        if silver_result and silver_result.get("silver_cubes"):
            print(f"    Planning {len(silver_result['silver_cubes'])} silver materialized views...")
            silver_mv_plans = self._plan_silver_materialized_views(
                trino_config,
                silver_result,
                state
            )
            pipeline_plans["trino_materialized_views"].extend(silver_mv_plans)
        
        # Plan silver Spark transformations
        print("    Analyzing silver transformations for Spark candidates...")
        silver_spark_plans = self._plan_layer_spark_transformations(
            transformation_plans.get("raw_to_silver", {}),
            "raw_to_silver",
            pipeline_config
        )
        pipeline_plans["spark_transformations"].extend(silver_spark_plans)
        
        # Plan silver Python transformations
        print("    Analyzing silver transformations for Python candidates...")
        silver_python_plans = self._plan_layer_python_transformations(
            transformation_plans.get("raw_to_silver", {}),
            "raw_to_silver",
            pipeline_config
        )
        pipeline_plans["python_transformations"].extend(silver_python_plans)
        
        logger.info(f"Updated pipeline plans: {len(silver_mv_plans)} silver MVs, "
                   f"{len(silver_spark_plans)} Spark, {len(silver_python_plans)} Python")
        
        return pipeline_plans
    
    def update_gold_pipeline_plans(
        self,
        pipeline_plans: Dict[str, Any],
        workflow_config: Dict[str, Any],
        gold_result: Dict,
        transformation_plans: Dict,
        state: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update pipeline plans with gold layer artifacts.
        Called after gold generation is complete.
        
        Args:
            pipeline_plans: Current pipeline plans (will be updated)
            workflow_config: Workflow configuration
            gold_result: Gold layer results
            transformation_plans: Transformation plans
            state: Current workflow state
            
        Returns:
            Updated pipeline plans dictionary
        """
        pipeline_config = workflow_config.get("pipeline_execution", {})
        
        if not pipeline_config:
            logger.debug("No pipeline execution configuration, skipping gold pipeline update")
            return pipeline_plans
        
        source_destination = pipeline_config.get("source_destination", {})
        trino_config = source_destination.get("trino", {})
        
        if not trino_config:
            logger.debug("No Trino configuration, skipping gold pipeline update")
            return pipeline_plans
        
        print("  Updating pipeline plans with gold layer artifacts...")
        
        # Plan gold Trino materialized views
        gold_mv_plans = []
        if gold_result and gold_result.get("gold_cubes"):
            print(f"    Planning {len(gold_result['gold_cubes'])} gold materialized views...")
            gold_mv_plans = self._plan_gold_materialized_views(
                trino_config,
                gold_result,
                state
            )
            pipeline_plans["trino_materialized_views"].extend(gold_mv_plans)
        
        # Plan gold Spark transformations
        print("    Analyzing gold transformations for Spark candidates...")
        gold_spark_plans = self._plan_layer_spark_transformations(
            transformation_plans.get("silver_to_gold", {}),
            "silver_to_gold",
            pipeline_config
        )
        pipeline_plans["spark_transformations"].extend(gold_spark_plans)
        
        # Plan gold Python transformations
        print("    Analyzing gold transformations for Python candidates...")
        gold_python_plans = self._plan_layer_python_transformations(
            transformation_plans.get("silver_to_gold", {}),
            "silver_to_gold",
            pipeline_config
        )
        pipeline_plans["python_transformations"].extend(gold_python_plans)
        
        logger.info(f"Updated pipeline plans: {len(gold_mv_plans)} gold MVs, "
                   f"{len(gold_spark_plans)} Spark, {len(gold_python_plans)} Python")
        
        return pipeline_plans
    
    def update_data_mart_pipeline_plans(
        self,
        pipeline_plans: Dict[str, Any],
        workflow_config: Dict[str, Any],
        enhanced_data_marts: List[Dict[str, Any]],
        state: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update pipeline plans with data mart artifacts.
        Called after data mart enhancement is complete.
        
        Args:
            pipeline_plans: Current pipeline plans (will be updated)
            workflow_config: Workflow configuration
            enhanced_data_marts: Enhanced data mart definitions
            state: Current workflow state
            
        Returns:
            Updated pipeline plans dictionary
        """
        pipeline_config = workflow_config.get("pipeline_execution", {})
        
        if not pipeline_config:
            logger.debug("No pipeline execution configuration, skipping data mart pipeline update")
            return pipeline_plans
        
        source_destination = pipeline_config.get("source_destination", {})
        trino_config = source_destination.get("trino", {})
        
        if not trino_config:
            logger.debug("No Trino configuration, skipping data mart pipeline update")
            return pipeline_plans
        
        print("  Updating pipeline plans with data mart artifacts...")
        
        # Plan data mart Trino materialized views
        data_mart_mv_plans = []
        if enhanced_data_marts:
            print(f"    Planning {len(enhanced_data_marts)} data mart materialized views...")
            data_mart_mv_plans = self._plan_data_mart_materialized_views(
                trino_config,
                enhanced_data_marts,
                state
            )
            pipeline_plans["trino_materialized_views"].extend(data_mart_mv_plans)
        
        logger.info(f"Updated pipeline plans: {len(data_mart_mv_plans)} data mart MVs")
        
        return pipeline_plans
    
    def finalize_pipeline_plans(
        self,
        pipeline_plans: Dict[str, Any],
        workflow_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Finalize pipeline plans by creating execution order and preparing for automation.
        Called at the end of workflow execution.
        
        Args:
            pipeline_plans: Current pipeline plans
            workflow_config: Workflow configuration
            
        Returns:
            Finalized pipeline plans dictionary with execution order
        """
        print("  Finalizing pipeline execution order...")
        
        # Create execution order from all plans
        execution_order = self.create_pipeline_execution_order(
            pipeline_plans.get("trino_materialized_views", []),
            pipeline_plans.get("spark_transformations", []),
            pipeline_plans.get("python_transformations", [])
        )
        
        pipeline_plans["execution_order"] = execution_order
        
        logger.info(f"Finalized pipeline plans: {len(execution_order)} total steps in execution order")
        
        return pipeline_plans
    
    def plan_pipeline_execution(
        self,
        workflow_config: Dict[str, Any],
        silver_result: Dict,
        gold_result: Optional[Dict],
        transformation_plans: Dict,
        enhanced_data_marts: Optional[List[Dict[str, Any]]],
        state: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Plan pipeline execution for Trino materialized views and Spark/Python transformations.
        
        This method creates execution plans for:
        1. Trino materialized views for silver, gold, and data marts
        2. Spark transformations for complex computations
        3. Python transformations for custom logic
        
        Args:
            workflow_config: Workflow configuration with source/destination settings
            silver_result: Silver layer results
            gold_result: Gold layer results
            transformation_plans: Transformation plans
            enhanced_data_marts: Enhanced data mart definitions
            state: Current workflow state
            
        Returns:
            Dictionary with execution plans for Trino MVs, Spark, and Python transformations
        """
        pipeline_config = workflow_config.get("pipeline_execution", {})
        
        if not pipeline_config:
            logger.info("No pipeline execution configuration found, skipping pipeline planning")
            return {
                "trino_materialized_views": [],
                "spark_transformations": [],
                "python_transformations": [],
                "execution_order": []
            }
        
        source_destination = pipeline_config.get("source_destination", {})
        trino_config = source_destination.get("trino", {})
        
        if not trino_config:
            logger.warning("Trino configuration not found in pipeline_execution.source_destination")
            return {
                "trino_materialized_views": [],
                "spark_transformations": [],
                "python_transformations": [],
                "execution_order": []
            }
        
        print("  Planning Trino materialized views...")
        trino_mv_plans = self.plan_trino_materialized_views(
            trino_config,
            silver_result,
            gold_result,
            enhanced_data_marts,
            state
        )
        
        print("  Planning Spark transformations...")
        spark_plans = self.plan_spark_transformations(
            transformation_plans,
            silver_result,
            gold_result,
            pipeline_config
        )
        
        print("  Planning Python transformations...")
        python_plans = self.plan_python_transformations(
            transformation_plans,
            silver_result,
            gold_result,
            pipeline_config
        )
        
        # Create execution order
        execution_order = self.create_pipeline_execution_order(
            trino_mv_plans,
            spark_plans,
            python_plans
        )
        
        return {
            "trino_materialized_views": trino_mv_plans,
            "spark_transformations": spark_plans,
            "python_transformations": python_plans,
            "execution_order": execution_order
        }
    
    def plan_trino_materialized_views(
        self,
        trino_config: Dict[str, Any],
        silver_result: Dict,
        gold_result: Optional[Dict],
        enhanced_data_marts: Optional[List[Dict[str, Any]]],
        state: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Plan Trino materialized views for silver, gold, and data marts.
        
        Args:
            trino_config: Trino connection configuration
            silver_result: Silver layer results
            gold_result: Gold layer results
            enhanced_data_marts: Enhanced data mart definitions
            state: Current workflow state
            
        Returns:
            List of materialized view plans
        """
        mv_plans = []
        
        catalog = trino_config.get("catalog", "hive")
        schema = trino_config.get("schema", "default")
        
        # Plan silver layer materialized views
        if silver_result and silver_result.get("silver_cubes"):
            print(f"    Planning {len(silver_result['silver_cubes'])} silver materialized views...")
            for cube in silver_result["silver_cubes"]:
                if isinstance(cube, dict):
                    cube_name = cube.get("name", "")
                    table_name = cube_name.replace("silver_", "")
                    
                    # Get transformation SQL for this table
                    transformation_sql = self.get_transformation_sql_for_table(
                        table_name,
                        "raw_to_silver",
                        silver_result
                    )
                    
                    if transformation_sql:
                        mv_name = f"{catalog}.{schema}.mv_silver_{table_name}"
                        mv_plan = {
                            "view_name": mv_name,
                            "layer": "silver",
                            "source_table": f"raw_{table_name}",
                            "target_table": f"silver_{table_name}",
                            "create_statement": self.generate_trino_mv_create_statement(
                                mv_name,
                                transformation_sql,
                                catalog,
                                schema
                            ),
                            "refresh_policy": trino_config.get("refresh_policy", "manual"),
                            "description": cube.get("description", f"Silver materialized view for {table_name}")
                        }
                        mv_plans.append(mv_plan)
        
        # Plan gold layer materialized views
        if gold_result and gold_result.get("gold_cubes"):
            print(f"    Planning {len(gold_result['gold_cubes'])} gold materialized views...")
            for cube in gold_result["gold_cubes"]:
                if isinstance(cube, dict):
                    cube_name = cube.get("name", "")
                    table_name = cube_name.replace("gold_", "")
                    
                    # Get transformation SQL for this table
                    transformation_sql = self.get_transformation_sql_for_table(
                        table_name,
                        "silver_to_gold",
                        gold_result
                    )
                    
                    if transformation_sql:
                        mv_name = f"{catalog}.{schema}.mv_gold_{table_name}"
                        mv_plan = {
                            "view_name": mv_name,
                            "layer": "gold",
                            "source_table": f"silver_{table_name}",
                            "target_table": f"gold_{table_name}",
                            "create_statement": self.generate_trino_mv_create_statement(
                                mv_name,
                                transformation_sql,
                                catalog,
                                schema
                            ),
                            "refresh_policy": trino_config.get("refresh_policy", "manual"),
                            "description": cube.get("description", f"Gold materialized view for {table_name}")
                        }
                        mv_plans.append(mv_plan)
        
        # Plan data mart materialized views
        if enhanced_data_marts:
            print(f"    Planning {len(enhanced_data_marts)} data mart materialized views...")
            for mart in enhanced_data_marts:
                if isinstance(mart, dict):
                    mart_name = mart.get("mart_name", "")
                    enhanced_sql = mart.get("enhanced_sql", "")
                    
                    if enhanced_sql:
                        mv_name = f"{catalog}.{schema}.mv_datamart_{mart_name}"
                        mv_plan = {
                            "view_name": mv_name,
                            "layer": "data_mart",
                            "source_table": None,  # Data marts may have multiple sources
                            "target_table": f"datamart_{mart_name}",
                            "create_statement": self.generate_trino_mv_create_statement(
                                mv_name,
                                enhanced_sql,
                                catalog,
                                schema
                            ),
                            "refresh_policy": trino_config.get("refresh_policy", "manual"),
                            "description": mart.get("description", f"Data mart materialized view: {mart_name}")
                        }
                        mv_plans.append(mv_plan)
        
        return mv_plans
    
    def _plan_silver_materialized_views(
        self,
        trino_config: Dict[str, Any],
        silver_result: Dict,
        state: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Helper method to plan only silver materialized views"""
        mv_plans = []
        catalog = trino_config.get("catalog", "hive")
        schema = trino_config.get("schema", "default")
        
        if silver_result and silver_result.get("silver_cubes"):
            for cube in silver_result["silver_cubes"]:
                if isinstance(cube, dict):
                    cube_name = cube.get("name", "")
                    table_name = cube_name.replace("silver_", "")
                    
                    transformation_sql = self.get_transformation_sql_for_table(
                        table_name,
                        "raw_to_silver",
                        silver_result
                    )
                    
                    if transformation_sql:
                        mv_name = f"{catalog}.{schema}.mv_silver_{table_name}"
                        mv_plan = {
                            "view_name": mv_name,
                            "layer": "silver",
                            "source_table": f"raw_{table_name}",
                            "target_table": f"silver_{table_name}",
                            "create_statement": self.generate_trino_mv_create_statement(
                                mv_name,
                                transformation_sql,
                                catalog,
                                schema
                            ),
                            "refresh_policy": trino_config.get("refresh_policy", "manual"),
                            "description": cube.get("description", f"Silver materialized view for {table_name}")
                        }
                        mv_plans.append(mv_plan)
        
        return mv_plans
    
    def _plan_gold_materialized_views(
        self,
        trino_config: Dict[str, Any],
        gold_result: Dict,
        state: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Helper method to plan only gold materialized views"""
        mv_plans = []
        catalog = trino_config.get("catalog", "hive")
        schema = trino_config.get("schema", "default")
        
        if gold_result and gold_result.get("gold_cubes"):
            for cube in gold_result["gold_cubes"]:
                if isinstance(cube, dict):
                    cube_name = cube.get("name", "")
                    table_name = cube_name.replace("gold_", "")
                    
                    transformation_sql = self.get_transformation_sql_for_table(
                        table_name,
                        "silver_to_gold",
                        gold_result
                    )
                    
                    if transformation_sql:
                        mv_name = f"{catalog}.{schema}.mv_gold_{table_name}"
                        mv_plan = {
                            "view_name": mv_name,
                            "layer": "gold",
                            "source_table": f"silver_{table_name}",
                            "target_table": f"gold_{table_name}",
                            "create_statement": self.generate_trino_mv_create_statement(
                                mv_name,
                                transformation_sql,
                                catalog,
                                schema
                            ),
                            "refresh_policy": trino_config.get("refresh_policy", "manual"),
                            "description": cube.get("description", f"Gold materialized view for {table_name}")
                        }
                        mv_plans.append(mv_plan)
        
        return mv_plans
    
    def _plan_data_mart_materialized_views(
        self,
        trino_config: Dict[str, Any],
        enhanced_data_marts: List[Dict[str, Any]],
        state: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Helper method to plan only data mart materialized views"""
        mv_plans = []
        catalog = trino_config.get("catalog", "hive")
        schema = trino_config.get("schema", "default")
        
        for mart in enhanced_data_marts:
            if isinstance(mart, dict):
                mart_name = mart.get("mart_name", "")
                enhanced_sql = mart.get("enhanced_sql", "")
                
                if enhanced_sql:
                    mv_name = f"{catalog}.{schema}.mv_datamart_{mart_name}"
                    mv_plan = {
                        "view_name": mv_name,
                        "layer": "data_mart",
                        "source_table": None,
                        "target_table": f"datamart_{mart_name}",
                        "create_statement": self.generate_trino_mv_create_statement(
                            mv_name,
                            enhanced_sql,
                            catalog,
                            schema
                        ),
                        "refresh_policy": trino_config.get("refresh_policy", "manual"),
                        "description": mart.get("description", f"Data mart materialized view: {mart_name}")
                    }
                    mv_plans.append(mv_plan)
        
        return mv_plans
    
    def _plan_layer_spark_transformations(
        self,
        layer_transformation_plans: Dict[str, List],
        layer_name: str,
        pipeline_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Helper method to plan Spark transformations for a specific layer"""
        spark_plans = []
        spark_config = pipeline_config.get("spark", {})
        
        if not spark_config.get("enabled", True):
            return spark_plans
        
        for table_name, steps in layer_transformation_plans.items():
            for step in steps:
                if isinstance(step, dict):
                    step_name = step.get("step_name", "")
                    step_type = step.get("transformation_type", "")
                    sql_logic = step.get("sql_logic", "")
                else:
                    step_name = getattr(step, "step_name", "")
                    step_type = getattr(step, "transformation_type", "")
                    sql_logic = getattr(step, "sql_logic", "")
                
                should_use_spark = self.should_use_spark(
                    sql_logic,
                    step_type,
                    spark_config
                )
                
                if should_use_spark:
                    spark_plan = {
                        "step_id": step.get("step_id", "") if isinstance(step, dict) else getattr(step, "step_id", ""),
                        "step_name": step_name,
                        "layer": layer_name,
                        "table_name": table_name,
                        "sql_logic": sql_logic,
                        "spark_code": self.generate_spark_code(
                            sql_logic,
                            step_name,
                            spark_config
                        ),
                        "execution_config": {
                            "executor_memory": spark_config.get("executor_memory", "4g"),
                            "executor_cores": spark_config.get("executor_cores", 2),
                            "num_executors": spark_config.get("num_executors", 4)
                        }
                    }
                    spark_plans.append(spark_plan)
        
        return spark_plans
    
    def _plan_layer_python_transformations(
        self,
        layer_transformation_plans: Dict[str, List],
        layer_name: str,
        pipeline_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Helper method to plan Python transformations for a specific layer"""
        python_plans = []
        python_config = pipeline_config.get("python", {})
        
        if not python_config.get("enabled", True):
            return python_plans
        
        for table_name, steps in layer_transformation_plans.items():
            for step in steps:
                if isinstance(step, dict):
                    step_name = step.get("step_name", "")
                    step_type = step.get("transformation_type", "")
                    sql_logic = step.get("sql_logic", "")
                    description = step.get("description", "")
                else:
                    step_name = getattr(step, "step_name", "")
                    step_type = getattr(step, "transformation_type", "")
                    sql_logic = getattr(step, "sql_logic", "")
                    description = getattr(step, "description", "")
                
                should_use_python = self.should_use_python(
                    sql_logic,
                    step_type,
                    description,
                    python_config
                )
                
                if should_use_python:
                    python_plan = {
                        "step_id": step.get("step_id", "") if isinstance(step, dict) else getattr(step, "step_id", ""),
                        "step_name": step_name,
                        "layer": layer_name,
                        "table_name": table_name,
                        "sql_logic": sql_logic,
                        "python_code": self.generate_python_code(
                            sql_logic,
                            step_name,
                            description,
                            python_config
                        ),
                        "execution_config": {
                            "runtime": python_config.get("runtime", "python3"),
                            "dependencies": python_config.get("dependencies", ["pandas", "numpy"])
                        }
                    }
                    python_plans.append(python_plan)
        
        return python_plans
    
    def plan_spark_transformations(
        self,
        transformation_plans: Dict,
        silver_result: Dict,
        gold_result: Optional[Dict],
        pipeline_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Plan Spark transformations for complex computations.
        
        Identifies transformations that should run on Spark based on:
        - Complexity (joins, aggregations, window functions)
        - Data volume indicators
        - Custom Spark requirements in config
        
        Args:
            transformation_plans: Transformation plans
            silver_result: Silver layer results
            gold_result: Gold layer results
            pipeline_config: Pipeline execution configuration
            
        Returns:
            List of Spark transformation plans
        """
        spark_plans = []
        spark_config = pipeline_config.get("spark", {})
        
        if not spark_config.get("enabled", True):
            logger.info("Spark transformations disabled in config")
            return spark_plans
        
        # Analyze transformations to identify Spark candidates
        for layer_transition in ["raw_to_silver", "silver_to_gold"]:
            for table_name, steps in transformation_plans.get(layer_transition, {}).items():
                for step in steps:
                    # Handle both dict and object formats
                    if isinstance(step, dict):
                        step_name = step.get("step_name", "")
                        step_type = step.get("transformation_type", "")
                        sql_logic = step.get("sql_logic", "")
                    else:
                        step_name = getattr(step, "step_name", "")
                        step_type = getattr(step, "transformation_type", "")
                        sql_logic = getattr(step, "sql_logic", "")
                    
                    # Check if this transformation should use Spark
                    should_use_spark = self.should_use_spark(
                        sql_logic,
                        step_type,
                        spark_config
                    )
                    
                    if should_use_spark:
                        spark_plan = {
                            "step_id": step.get("step_id", "") if isinstance(step, dict) else getattr(step, "step_id", ""),
                            "step_name": step_name,
                            "layer": layer_transition,
                            "table_name": table_name,
                            "sql_logic": sql_logic,
                            "spark_code": self.generate_spark_code(
                                sql_logic,
                                step_name,
                                spark_config
                            ),
                            "execution_config": {
                                "executor_memory": spark_config.get("executor_memory", "4g"),
                                "executor_cores": spark_config.get("executor_cores", 2),
                                "num_executors": spark_config.get("num_executors", 4)
                            }
                        }
                        spark_plans.append(spark_plan)
        
        return spark_plans
    
    def plan_python_transformations(
        self,
        transformation_plans: Dict,
        silver_result: Dict,
        gold_result: Optional[Dict],
        pipeline_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Plan Python transformations for custom logic.
        
        Identifies transformations that should run as Python scripts based on:
        - Custom business logic requirements
        - Complex data manipulations not easily expressible in SQL
        - Python-specific requirements in config
        
        Args:
            transformation_plans: Transformation plans
            silver_result: Silver layer results
            gold_result: Gold layer results
            pipeline_config: Pipeline execution configuration
            
        Returns:
            List of Python transformation plans
        """
        python_plans = []
        python_config = pipeline_config.get("python", {})
        
        if not python_config.get("enabled", True):
            logger.info("Python transformations disabled in config")
            return python_plans
        
        # Analyze transformations to identify Python candidates
        for layer_transition in ["raw_to_silver", "silver_to_gold"]:
            for table_name, steps in transformation_plans.get(layer_transition, {}).items():
                for step in steps:
                    # Handle both dict and object formats
                    if isinstance(step, dict):
                        step_name = step.get("step_name", "")
                        step_type = step.get("transformation_type", "")
                        sql_logic = step.get("sql_logic", "")
                        description = step.get("description", "")
                    else:
                        step_name = getattr(step, "step_name", "")
                        step_type = getattr(step, "transformation_type", "")
                        sql_logic = getattr(step, "sql_logic", "")
                        description = getattr(step, "description", "")
                    
                    # Check if this transformation should use Python
                    should_use_python = self.should_use_python(
                        sql_logic,
                        step_type,
                        description,
                        python_config
                    )
                    
                    if should_use_python:
                        python_plan = {
                            "step_id": step.get("step_id", "") if isinstance(step, dict) else getattr(step, "step_id", ""),
                            "step_name": step_name,
                            "layer": layer_transition,
                            "table_name": table_name,
                            "sql_logic": sql_logic,
                            "python_code": self.generate_python_code(
                                sql_logic,
                                step_name,
                                description,
                                python_config
                            ),
                            "execution_config": {
                                "runtime": python_config.get("runtime", "python3"),
                                "dependencies": python_config.get("dependencies", ["pandas", "numpy"])
                            }
                        }
                        python_plans.append(python_plan)
        
        return python_plans
    
    def get_transformation_sql_for_table(
        self,
        table_name: str,
        layer_transition: str,
        result: Dict
    ) -> Optional[str]:
        """Extract transformation SQL for a specific table"""
        transformations = result.get(f"{layer_transition}_transformations", [])
        
        for trans in transformations:
            if isinstance(trans, dict):
                output_table = trans.get("output_table", "")
                if table_name in output_table:
                    return trans.get("sql_logic", "")
            else:
                output_table = getattr(trans, "output_table", "")
                if table_name in output_table:
                    return getattr(trans, "sql_logic", "")
        
        return None
    
    def generate_trino_mv_create_statement(
        self,
        mv_name: str,
        select_sql: str,
        catalog: str,
        schema: str
    ) -> str:
        """Generate Trino CREATE MATERIALIZED VIEW statement"""
        # Convert SQL to Trino dialect if needed
        # Remove CREATE TABLE AS SELECT patterns and convert to SELECT
        sql = select_sql
        if "CREATE TABLE" in sql.upper() and "AS SELECT" in sql.upper():
            # Extract SELECT part
            match = re.search(r'AS\s+SELECT', sql, re.IGNORECASE)
            if match:
                sql = sql[match.end():].strip()
        
        # Generate Trino CREATE MATERIALIZED VIEW statement
        create_mv = f"""CREATE MATERIALIZED VIEW IF NOT EXISTS {mv_name}
AS
{sql};"""
        
        return create_mv
    
    def should_use_spark(
        self,
        sql_logic: str,
        step_type: str,
        spark_config: Dict[str, Any]
    ) -> bool:
        """Determine if a transformation should use Spark"""
        # Check explicit Spark requirements
        if spark_config.get("force_all", False):
            return True
        
        # Check for complex operations that benefit from Spark
        complex_patterns = [
            r'JOIN.*JOIN',  # Multiple joins
            r'WINDOW\s+FUNCTION',  # Window functions
            r'PARTITION\s+BY',  # Partitioning
            r'LATERAL\s+VIEW',  # Lateral views
            r'ARRAY_AGG|COLLECT_LIST',  # Array aggregations
        ]
        
        sql_upper = sql_logic.upper()
        for pattern in complex_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                return True
        
        # Check step type
        spark_step_types = spark_config.get("step_types", ["aggregation", "join", "window"])
        if step_type.lower() in [t.lower() for t in spark_step_types]:
            return True
        
        return False
    
    def should_use_python(
        self,
        sql_logic: str,
        step_type: str,
        description: str,
        python_config: Dict[str, Any]
    ) -> bool:
        """Determine if a transformation should use Python"""
        # Check explicit Python requirements
        if python_config.get("force_all", False):
            return True
        
        # Check for custom logic indicators
        python_keywords = [
            "custom", "complex", "algorithm", "machine learning",
            "statistical", "model", "prediction", "scoring"
        ]
        
        description_lower = description.lower()
        for keyword in python_keywords:
            if keyword in description_lower:
                return True
        
        # Check step type
        python_step_types = python_config.get("step_types", ["custom", "metric", "calculation"])
        if step_type.lower() in [t.lower() for t in python_step_types]:
            return True
        
        return False
    
    def generate_spark_code(
        self,
        sql_logic: str,
        step_name: str,
        spark_config: Dict[str, Any]
    ) -> str:
        """Generate PySpark code from SQL transformation"""
        # Use LLM to convert SQL to Spark code
        system_prompt = """You are a PySpark expert. Convert SQL transformations to PySpark DataFrame operations.
Generate efficient, production-ready PySpark code."""
        
        user_prompt = f"""Convert this SQL transformation to PySpark code:

Step Name: {step_name}
SQL:
{sql_logic}

Generate PySpark code that:
1. Reads from source tables
2. Applies the transformation logic
3. Writes to target table
4. Includes error handling and logging"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            spark_code = response.content if hasattr(response, 'content') else str(response)
            
            # Extract code block if present
            code_match = re.search(r'```python\n(.*?)\n```', spark_code, re.DOTALL)
            if code_match:
                spark_code = code_match.group(1)
            else:
                code_match = re.search(r'```\n(.*?)\n```', spark_code, re.DOTALL)
                if code_match:
                    spark_code = code_match.group(1)
            
            return spark_code
        except Exception as e:
            logger.error(f"Error generating Spark code: {e}")
            # Fallback: basic Spark template
            return f"""# PySpark transformation: {step_name}
from pyspark.sql import SparkSession
from pyspark.sql.functions import *

spark = SparkSession.builder.appName("{step_name}").getOrCreate()

# TODO: Implement transformation based on SQL:
# {sql_logic[:200]}...
"""
    
    def generate_python_code(
        self,
        sql_logic: str,
        step_name: str,
        description: str,
        python_config: Dict[str, Any]
    ) -> str:
        """Generate Python code from SQL transformation"""
        # Use LLM to convert SQL to Python pandas code
        system_prompt = """You are a Python data engineering expert. Convert SQL transformations to Python pandas operations.
Generate efficient, production-ready Python code."""
        
        user_prompt = f"""Convert this SQL transformation to Python pandas code:

Step Name: {step_name}
Description: {description}
SQL:
{sql_logic}

Generate Python code that:
1. Reads from source tables (using pandas or database connection)
2. Applies the transformation logic
3. Writes to target table
4. Includes error handling and logging"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            python_code = response.content if hasattr(response, 'content') else str(response)
            
            # Extract code block if present
            code_match = re.search(r'```python\n(.*?)\n```', python_code, re.DOTALL)
            if code_match:
                python_code = code_match.group(1)
            else:
                code_match = re.search(r'```\n(.*?)\n```', python_code, re.DOTALL)
                if code_match:
                    python_code = code_match.group(1)
            
            return python_code
        except Exception as e:
            logger.error(f"Error generating Python code: {e}")
            # Fallback: basic Python template
            return f"""# Python transformation: {step_name}
import pandas as pd

# TODO: Implement transformation based on SQL:
# {sql_logic[:200]}...
"""
    
    def create_pipeline_execution_order(
        self,
        trino_mv_plans: List[Dict[str, Any]],
        spark_plans: List[Dict[str, Any]],
        python_plans: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create ordered execution plan for all pipeline steps"""
        execution_order = []
        
        # Order: Silver MVs -> Spark Silver -> Python Silver -> Gold MVs -> Spark Gold -> Python Gold -> Data Mart MVs
        silver_mvs = [mv for mv in trino_mv_plans if mv.get("layer") == "silver"]
        gold_mvs = [mv for mv in trino_mv_plans if mv.get("layer") == "gold"]
        data_mart_mvs = [mv for mv in trino_mv_plans if mv.get("layer") == "data_mart"]
        
        silver_spark = [sp for sp in spark_plans if "raw_to_silver" in sp.get("layer", "")]
        gold_spark = [sp for sp in spark_plans if "silver_to_gold" in sp.get("layer", "")]
        
        silver_python = [py for py in python_plans if "raw_to_silver" in py.get("layer", "")]
        gold_python = [py for py in python_plans if "silver_to_gold" in py.get("layer", "")]
        
        # Build execution order
        execution_order.extend([{"type": "trino_mv", "plan": mv} for mv in silver_mvs])
        execution_order.extend([{"type": "spark", "plan": sp} for sp in silver_spark])
        execution_order.extend([{"type": "python", "plan": py} for py in silver_python])
        execution_order.extend([{"type": "trino_mv", "plan": mv} for mv in gold_mvs])
        execution_order.extend([{"type": "spark", "plan": sp} for sp in gold_spark])
        execution_order.extend([{"type": "python", "plan": py} for py in gold_python])
        execution_order.extend([{"type": "trino_mv", "plan": mv} for mv in data_mart_mvs])
        
        return execution_order
    
    def generate_pipeline_automation_questions(
        self,
        pipeline_plans: Dict[str, Any],
        workflow_config: Dict[str, Any],
        workflow_name: str
    ) -> List[Dict[str, Any]]:
        """
        Generate natural language questions for pipeline automation.
        These questions can be used by another agent to generate automation scripts.
        
        Args:
            pipeline_plans: Pipeline execution plans
            workflow_config: Workflow configuration
            workflow_name: Workflow name
            
        Returns:
            List of natural language question dictionaries
        """
        questions = []
        
        pipeline_config = workflow_config.get("pipeline_execution", {})
        trino_config = pipeline_config.get("source_destination", {}).get("trino", {})
        spark_config = pipeline_config.get("spark", {})
        python_config = pipeline_config.get("python", {})
        
        # Question 1: Overall pipeline automation setup
        questions.append({
            "question_id": "pipeline_automation_setup",
            "question": f"""How do I set up automation for the {workflow_name} data pipeline execution?
            
The pipeline includes:
- {len(pipeline_plans.get('trino_materialized_views', []))} Trino materialized views to create
- {len(pipeline_plans.get('spark_transformations', []))} Spark transformations to execute
- {len(pipeline_plans.get('python_transformations', []))} Python transformations to execute
- {len(pipeline_plans.get('execution_order', []))} total steps in execution order

Configuration requirements:
- Trino connection: catalog={trino_config.get('catalog', 'hive')}, schema={trino_config.get('schema', 'default')}
- Spark configuration: {spark_config.get('executor_memory', '4g')} memory, {spark_config.get('num_executors', 4)} executors
- Python runtime: {python_config.get('runtime', 'python3')} with dependencies {', '.join(python_config.get('dependencies', ['pandas', 'numpy']))}

Generate an automation script that:
1. Establishes connections to Trino, Spark, and Python environments
2. Executes all pipeline steps in the correct order
3. Handles errors and retries
4. Logs execution progress
5. Validates results after each step""",
            "context": {
                "workflow_name": workflow_name,
                "trino_config": trino_config,
                "spark_config": spark_config,
                "python_config": python_config,
                "total_steps": len(pipeline_plans.get("execution_order", []))
            },
            "expected_output_type": "automation_script",
            "steps": [
                "Set up Trino connection with catalog and schema",
                "Configure Spark session with specified resources",
                "Set up Python environment with required dependencies",
                "Load execution order from pipeline plan",
                "Implement step-by-step execution with error handling",
                "Add logging and progress tracking",
                "Implement result validation"
            ],
            "metadata": {
                "category": "pipeline_setup",
                "priority": "high"
            }
        })
        
        # Questions for Trino materialized views
        for idx, mv_plan in enumerate(pipeline_plans.get("trino_materialized_views", []), 1):
            mv_name = mv_plan.get("view_name", "")
            layer = mv_plan.get("layer", "")
            questions.append({
                "question_id": f"trino_mv_{layer}_{idx}",
                "question": f"""How do I create and manage the Trino materialized view '{mv_name}' for the {layer} layer?
                
View Details:
- Full name: {mv_name}
- Layer: {layer}
- Source table: {mv_plan.get('source_table', 'N/A')}
- Target table: {mv_plan.get('target_table', 'N/A')}
- Refresh policy: {mv_plan.get('refresh_policy', 'manual')}
- Description: {mv_plan.get('description', '')}

Generate automation code that:
1. Connects to Trino using the configured catalog and schema
2. Executes the CREATE MATERIALIZED VIEW statement
3. Handles the case where the view already exists
4. Sets up refresh schedule if refresh_policy is not 'manual'
5. Validates that the view was created successfully
6. Logs the creation status""",
                "context": {
                    "view_name": mv_name,
                    "layer": layer,
                    "create_statement": mv_plan.get("create_statement", ""),
                    "refresh_policy": mv_plan.get("refresh_policy", "manual"),
                    "trino_config": trino_config
                },
                "expected_output_type": "trino_automation",
                "steps": [
                    f"Connect to Trino catalog={trino_config.get('catalog', 'hive')}, schema={trino_config.get('schema', 'default')}",
                    f"Execute CREATE MATERIALIZED VIEW statement for {mv_name}",
                    "Handle IF NOT EXISTS clause",
                    f"Configure refresh policy: {mv_plan.get('refresh_policy', 'manual')}",
                    "Validate view creation",
                    "Log execution status"
                ],
                "metadata": {
                    "category": "trino_materialized_view",
                    "layer": layer,
                    "step_number": idx
                },
                "dependencies": []
            })
        
        # Questions for Spark transformations
        for idx, spark_plan in enumerate(pipeline_plans.get("spark_transformations", []), 1):
            step_name = spark_plan.get("step_name", "")
            layer = spark_plan.get("layer", "")
            questions.append({
                "question_id": f"spark_transformation_{layer}_{idx}",
                "question": f"""How do I execute the Spark transformation '{step_name}' for the {layer} layer?
                
Transformation Details:
- Step name: {step_name}
- Layer: {layer}
- Table: {spark_plan.get('table_name', 'N/A')}
- Executor memory: {spark_plan.get('execution_config', {}).get('executor_memory', '4g')}
- Executor cores: {spark_plan.get('execution_config', {}).get('executor_cores', 2)}
- Number of executors: {spark_plan.get('execution_config', {}).get('num_executors', 4)}

Generate automation code that:
1. Initializes Spark session with the specified configuration
2. Reads source data from the appropriate tables
3. Executes the Spark transformation code
4. Writes results to the target table
5. Handles errors and retries
6. Monitors Spark job execution
7. Validates output data quality
8. Cleans up Spark resources""",
                "context": {
                    "step_name": step_name,
                    "layer": layer,
                    "spark_code": spark_plan.get("spark_code", ""),
                    "execution_config": spark_plan.get("execution_config", {}),
                    "sql_logic": spark_plan.get("sql_logic", "")
                },
                "expected_output_type": "spark_automation",
                "steps": [
                    f"Initialize Spark session with {spark_plan.get('execution_config', {}).get('executor_memory', '4g')} memory",
                    f"Configure {spark_plan.get('execution_config', {}).get('num_executors', 4)} executors",
                    "Read source data from input tables",
                    "Execute Spark transformation logic",
                    "Write results to target table",
                    "Monitor job execution and handle errors",
                    "Validate output data",
                    "Clean up Spark session"
                ],
                "metadata": {
                    "category": "spark_transformation",
                    "layer": layer,
                    "step_number": idx
                },
                "dependencies": []
            })
        
        # Questions for Python transformations
        for idx, python_plan in enumerate(pipeline_plans.get("python_transformations", []), 1):
            step_name = python_plan.get("step_name", "")
            layer = python_plan.get("layer", "")
            questions.append({
                "question_id": f"python_transformation_{layer}_{idx}",
                "question": f"""How do I execute the Python transformation '{step_name}' for the {layer} layer?
                
Transformation Details:
- Step name: {step_name}
- Layer: {layer}
- Table: {python_plan.get('table_name', 'N/A')}
- Runtime: {python_plan.get('execution_config', {}).get('runtime', 'python3')}
- Required dependencies: {', '.join(python_plan.get('execution_config', {}).get('dependencies', ['pandas', 'numpy']))}

Generate automation code that:
1. Sets up Python environment with required dependencies
2. Connects to source data (database, files, or APIs)
3. Executes the Python transformation code
4. Writes results to the target location
5. Handles errors and exceptions
6. Validates output data
7. Logs execution details
8. Manages Python process lifecycle""",
                "context": {
                    "step_name": step_name,
                    "layer": layer,
                    "python_code": python_plan.get("python_code", ""),
                    "execution_config": python_plan.get("execution_config", {}),
                    "sql_logic": python_plan.get("sql_logic", "")
                },
                "expected_output_type": "python_automation",
                "steps": [
                    f"Set up {python_plan.get('execution_config', {}).get('runtime', 'python3')} environment",
                    f"Install dependencies: {', '.join(python_plan.get('execution_config', {}).get('dependencies', ['pandas', 'numpy']))}",
                    "Connect to source data",
                    "Execute Python transformation logic",
                    "Write results to target",
                    "Handle exceptions and errors",
                    "Validate output data",
                    "Log execution details"
                ],
                "metadata": {
                    "category": "python_transformation",
                    "layer": layer,
                    "step_number": idx
                },
                "dependencies": []
            })
        
        # Question for execution order orchestration
        execution_order = pipeline_plans.get("execution_order", [])
        if execution_order:
            questions.append({
                "question_id": "pipeline_execution_orchestration",
                "question": f"""How do I orchestrate the execution of all {len(execution_order)} pipeline steps in the correct order?
                
Execution Order:
{chr(10).join([f"{i+1}. {step.get('type', 'unknown')}: {step.get('plan', {}).get('step_name', step.get('plan', {}).get('view_name', 'unknown'))}" for i, step in enumerate(execution_order[:20])])}
{f'... and {len(execution_order) - 20} more steps' if len(execution_order) > 20 else ''}

Generate orchestration code that:
1. Loads the execution order from the pipeline plan
2. Executes steps sequentially respecting dependencies
3. Handles parallel execution where possible (e.g., independent Spark jobs)
4. Implements retry logic for failed steps
5. Tracks execution status and progress
6. Handles rollback if critical steps fail
7. Sends notifications on completion or failure
8. Generates execution reports""",
                "context": {
                    "execution_order": execution_order,
                    "total_steps": len(execution_order),
                    "trino_steps": len([s for s in execution_order if s.get("type") == "trino_mv"]),
                    "spark_steps": len([s for s in execution_order if s.get("type") == "spark"]),
                    "python_steps": len([s for s in execution_order if s.get("type") == "python"])
                },
                "expected_output_type": "orchestration_script",
                "steps": [
                    "Load execution order from pipeline plan",
                    "Initialize all required connections (Trino, Spark, Python)",
                    "Execute steps in order, respecting dependencies",
                    "Implement parallel execution for independent steps",
                    "Add retry logic for transient failures",
                    "Track execution status and progress",
                    "Handle rollback for critical failures",
                    "Send notifications and generate reports"
                ],
                "metadata": {
                    "category": "orchestration",
                    "priority": "high"
                },
                "dependencies": [f"trino_mv_{step.get('plan', {}).get('layer', '')}_{i}" for i, step in enumerate(execution_order) if step.get("type") == "trino_mv"] + 
                               [f"spark_transformation_{step.get('plan', {}).get('layer', '')}_{i}" for i, step in enumerate(execution_order) if step.get("type") == "spark"] +
                               [f"python_transformation_{step.get('plan', {}).get('layer', '')}_{i}" for i, step in enumerate(execution_order) if step.get("type") == "python"]
            })
        
        # Question for monitoring and validation
        questions.append({
            "question_id": "pipeline_monitoring_validation",
            "question": f"""How do I monitor and validate the execution of the {workflow_name} pipeline?
            
Pipeline Components:
- {len(pipeline_plans.get('trino_materialized_views', []))} materialized views to monitor
- {len(pipeline_plans.get('spark_transformations', []))} Spark jobs to track
- {len(pipeline_plans.get('python_transformations', []))} Python processes to monitor

Generate monitoring and validation code that:
1. Tracks execution status of all pipeline steps
2. Monitors Trino materialized view refresh status
3. Tracks Spark job progress and resource usage
4. Monitors Python process execution
5. Validates data quality after each step
6. Checks row counts and data freshness
7. Generates alerts for failures or anomalies
8. Creates execution dashboards and reports
9. Implements health checks for all components""",
            "context": {
                "workflow_name": workflow_name,
                "pipeline_components": {
                    "trino_mvs": len(pipeline_plans.get("trino_materialized_views", [])),
                    "spark_jobs": len(pipeline_plans.get("spark_transformations", [])),
                    "python_processes": len(pipeline_plans.get("python_transformations", []))
                }
            },
            "expected_output_type": "monitoring_script",
            "steps": [
                "Set up monitoring infrastructure",
                "Track Trino MV refresh status",
                "Monitor Spark job metrics",
                "Track Python process execution",
                "Implement data quality checks",
                "Generate alerts and notifications",
                "Create execution dashboards",
                "Generate execution reports"
            ],
            "metadata": {
                "category": "monitoring",
                "priority": "medium"
            }
        })
        
        return questions
    
    def save_pipeline_execution_plans(
        self,
        workflow_name: str,
        timestamp: str,
        pipeline_plans: Dict[str, Any],
        saved_paths: Dict[str, list],
        workflow_config: Dict[str, Any]
    ):
        """Save pipeline execution plans to files"""
        pipeline_dir = self.output_dir / "pipeline_execution"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        
        # Save Trino materialized view plans
        trino_dir = pipeline_dir / "trino"
        trino_dir.mkdir(parents=True, exist_ok=True)
        
        for mv_plan in pipeline_plans.get("trino_materialized_views", []):
            mv_name = mv_plan.get("view_name", "unknown").split(".")[-1]
            mv_file = trino_dir / f"{mv_name}.sql"
            with open(mv_file, 'w') as f:
                f.write(f"-- Trino Materialized View: {mv_name}\n")
                f.write(f"-- Generated: {timestamp}\n")
                f.write(f"-- Layer: {mv_plan.get('layer', 'unknown')}\n\n")
                f.write(mv_plan.get("create_statement", ""))
            saved_paths.setdefault("pipeline_execution", []).append(str(mv_file))
        
        # Save Spark transformation plans
        spark_dir = pipeline_dir / "spark"
        spark_dir.mkdir(parents=True, exist_ok=True)
        
        for spark_plan in pipeline_plans.get("spark_transformations", []):
            step_name = spark_plan.get("step_name", "unknown").replace(" ", "_").lower()
            spark_file = spark_dir / f"{step_name}.py"
            with open(spark_file, 'w') as f:
                f.write(f"# Spark Transformation: {spark_plan.get('step_name', '')}\n")
                f.write(f"# Generated: {timestamp}\n")
                f.write(f"# Layer: {spark_plan.get('layer', 'unknown')}\n\n")
                f.write(spark_plan.get("spark_code", ""))
            saved_paths.setdefault("pipeline_execution", []).append(str(spark_file))
        
        # Save Python transformation plans
        python_dir = pipeline_dir / "python"
        python_dir.mkdir(parents=True, exist_ok=True)
        
        for python_plan in pipeline_plans.get("python_transformations", []):
            step_name = python_plan.get("step_name", "unknown").replace(" ", "_").lower()
            python_file = python_dir / f"{step_name}.py"
            with open(python_file, 'w') as f:
                f.write(f"# Python Transformation: {python_plan.get('step_name', '')}\n")
                f.write(f"# Generated: {timestamp}\n")
                f.write(f"# Layer: {python_plan.get('layer', 'unknown')}\n\n")
                f.write(python_plan.get("python_code", ""))
            saved_paths.setdefault("pipeline_execution", []).append(str(python_file))
        
        # Save execution order
        execution_order_file = pipeline_dir / "execution_order.json"
        with open(execution_order_file, 'w') as f:
            json.dump(pipeline_plans.get("execution_order", []), f, indent=2, default=str)
        saved_paths.setdefault("pipeline_execution", []).append(str(execution_order_file))
        
        # Save complete pipeline plan
        plan_file = pipeline_dir / f"{workflow_name}_pipeline_plan.json"
        with open(plan_file, 'w') as f:
            json.dump(pipeline_plans, f, indent=2, default=str)
        saved_paths.setdefault("pipeline_execution", []).append(str(plan_file))
        
        # Generate and save natural language questions for automation
        automation_questions = self.generate_pipeline_automation_questions(
            pipeline_plans,
            workflow_config,
            workflow_name
        )
        
        # Save questions to JSON file
        questions_file = pipeline_dir / f"{workflow_name}_automation_questions.json"
        with open(questions_file, 'w') as f:
            json.dump(automation_questions, f, indent=2, default=str)
        saved_paths.setdefault("pipeline_execution", []).append(str(questions_file))
        
        # Also save individual question files for easy access
        questions_dir = pipeline_dir / "automation_questions"
        questions_dir.mkdir(parents=True, exist_ok=True)
        
        for question in automation_questions:
            question_file = questions_dir / f"{question['question_id']}.json"
            with open(question_file, 'w') as f:
                json.dump(question, f, indent=2, default=str)
            saved_paths.setdefault("pipeline_execution", []).append(str(question_file))
        
        logger.info(f"Generated {len(automation_questions)} natural language questions for pipeline automation")

