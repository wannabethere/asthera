"""
Natural Language Metric Discovery Agent
Uses LangGraph to discover, plan, and generate metrics from natural language questions
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
import json
import logging
from enum import Enum
import operator

from app.core.dependencies import get_llm
from app.agents.cubes.sql_generator_agent import SQLGeneratorAgent, SQLDialect

logger = logging.getLogger("genieml-agents")


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class MetricLayer(str, Enum):
    """Metric layer classification"""
    SILVER = "silver"  # Metric can be calculated from silver tables
    GOLD = "gold"  # Metric requires gold layer aggregations


class DiscoveredMetric(BaseModel):
    """A metric discovered from natural language question"""
    metric_name: str
    metric_description: str
    metric_type: str  # count, sum, avg, ratio, percentage, growth_rate, trend, etc.
    layer: MetricLayer = MetricLayer.GOLD  # Default to gold, will be classified later
    source_tables: List[str]
    dimensions: List[str] = Field(default_factory=list)
    time_granularity: Optional[str] = None  # day, week, month, quarter, year
    formula_description: str
    business_rules: List[str] = Field(default_factory=list)
    sql_logic: Optional[str] = None  # Generated SQL
    target_mart: Optional[str] = None


class MetricPlan(BaseModel):
    """Plan for generating a metric"""
    metric: DiscoveredMetric
    execution_order: int
    dependencies: List[str] = Field(default_factory=list)  # Other metric names this depends on
    estimated_complexity: str  # low, medium, high
    reasoning: str


class MetricDiscoveryState(TypedDict):
    """State for metric discovery workflow"""
    # Input
    natural_language_question: str
    available_tables: List[Dict[str, Any]]  # Table metadata
    silver_tables: List[str]  # Available silver table names
    gold_tables: List[str]  # Available gold table names
    
    # Processing
    messages: Annotated[List[Any], lambda x, y: x + y]  # LLM conversation history
    
    # Output
    discovered_metrics: List[DiscoveredMetric]
    metric_plans: List[MetricPlan]
    generated_sql: Dict[str, str]  # metric_name -> SQL
    errors: List[str]


# ============================================================================
# METRIC DISCOVERY AGENT
# ============================================================================

class MetricDiscoveryAgent:
    """Agent that discovers and plans metrics from natural language questions"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        sql_generator: Optional[SQLGeneratorAgent] = None
    ):
        self.llm = llm or get_llm(model=model_name)
        self.sql_generator = sql_generator or SQLGeneratorAgent(llm=self.llm, model_name=model_name)
        self.graph = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow for metric discovery"""
        workflow = StateGraph(MetricDiscoveryState)
        
        # Add nodes
        workflow.add_node("discover_metrics", self.discover_metrics)
        workflow.add_node("classify_layers", self.classify_layers)
        workflow.add_node("plan_metrics", self.plan_metrics)
        workflow.add_node("generate_sql", self.generate_sql)
        workflow.add_node("validate_output", self.validate_output)
        
        # Define edges
        workflow.set_entry_point("discover_metrics")
        workflow.add_edge("discover_metrics", "classify_layers")
        workflow.add_edge("classify_layers", "plan_metrics")
        workflow.add_edge("plan_metrics", "generate_sql")
        workflow.add_edge("generate_sql", "validate_output")
        workflow.add_edge("validate_output", END)
        
        return workflow.compile()
    
    # ========================================================================
    # WORKFLOW NODES
    # ========================================================================
    
    def discover_metrics(self, state: MetricDiscoveryState) -> MetricDiscoveryState:
        """
        Step 1: Discover metrics from natural language question.
        Identifies all metrics needed to answer the question.
        """
        system_prompt = """You are a business intelligence expert specializing in metric discovery from natural language questions.

Your task is to analyze a natural language question and identify ALL metrics needed to answer it.

**Metric Types:**
- count: Counting records or distinct values
- sum: Summing numeric values
- avg: Calculating averages
- ratio: Comparing two values (numerator/denominator)
- percentage: Percentage calculations
- growth_rate: Period-over-period growth
- trend: Time-series trends
- comparison: Comparing values across dimensions or time periods

**Key Considerations:**
1. Break down complex questions into individual metrics
2. Identify time comparisons (year-over-year, month-over-month, etc.)
3. Identify dimensional comparisons (by category, by region, etc.)
4. Identify aggregations needed
5. Note any filters or conditions

Return a JSON array of discovered metrics."""
        
        # Build table context
        table_info = []
        for table in state["available_tables"]:
            table_name = table.get("table_name", "")
            description = table.get("description", "")
            columns = table.get("columns", [])
            table_info.append(f"- {table_name}: {description}\n  Columns: {', '.join([c.get('name', '') for c in columns[:10]])}")
        
        user_prompt = f"""Analyze this natural language question and discover all metrics needed to answer it:

**Question:** {state['natural_language_question']}

**Available Tables:**
{chr(10).join(table_info)}

**Available Silver Tables:** {', '.join(state.get('silver_tables', []))}
**Available Gold Tables:** {', '.join(state.get('gold_tables', []))}

Identify ALL metrics needed. For each metric, provide:
1. Metric name (snake_case, descriptive)
2. Metric description (what it measures)
3. Metric type (count, sum, avg, ratio, percentage, growth_rate, trend, comparison)
4. Source tables needed
5. Dimensions to group by (if any)
6. Time granularity (if time-based)
7. Formula description (how to calculate)
8. Business rules or assumptions

Return as JSON array:
[
    {{
        "metric_name": "metric_name",
        "metric_description": "What this metric measures",
        "metric_type": "count|sum|avg|ratio|percentage|growth_rate|trend|comparison",
        "source_tables": ["table1", "table2"],
        "dimensions": ["dimension1", "dimension2"],
        "time_granularity": "day|week|month|quarter|year|none",
        "formula_description": "How to calculate this metric",
        "business_rules": ["rule1", "rule2"]
    }}
]"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            state["messages"].append(response)
            
            # Parse response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            metrics_data = json.loads(content)
            if isinstance(metrics_data, dict) and "metrics" in metrics_data:
                metrics_data = metrics_data["metrics"]
            
            # Convert to DiscoveredMetric objects
            discovered_metrics = []
            for metric_data in metrics_data:
                try:
                    # Ensure required fields have defaults
                    if "layer" not in metric_data or not metric_data.get("layer"):
                        metric_data["layer"] = "gold"  # Default to gold, will be classified later
                    elif isinstance(metric_data["layer"], str):
                        metric_data["layer"] = metric_data["layer"].lower()
                        # Validate layer value
                        if metric_data["layer"] not in ["silver", "gold"]:
                            metric_data["layer"] = "gold"
                    
                    # Ensure other required fields have defaults
                    if "source_tables" not in metric_data:
                        metric_data["source_tables"] = []
                    if "dimensions" not in metric_data:
                        metric_data["dimensions"] = []
                    if "business_rules" not in metric_data:
                        metric_data["business_rules"] = []
                    if "time_granularity" not in metric_data:
                        metric_data["time_granularity"] = None
                    
                    metric = DiscoveredMetric(**metric_data)
                    discovered_metrics.append(metric)
                except Exception as e:
                    logger.warning(f"Error parsing metric: {e}")
                    logger.debug(f"Metric dict that failed: {metric_data}")
                    continue
            
            state["discovered_metrics"] = discovered_metrics
            logger.info(f"Discovered {len(discovered_metrics)} metrics")
            
        except Exception as e:
            logger.error(f"Error discovering metrics: {e}")
            state["errors"].append(f"Error discovering metrics: {str(e)}")
            state["discovered_metrics"] = []
        
        return state
    
    def classify_layers(self, state: MetricDiscoveryState) -> MetricDiscoveryState:
        """
        Step 2: Classify each metric as silver or gold layer.
        Determines which layer can best support each metric.
        """
        system_prompt = """You are a data architecture expert. Classify metrics as SILVER or GOLD layer.

**SILVER Layer Metrics:**
- Can be calculated directly from silver tables
- Simple aggregations (count, sum, avg)
- Single table operations
- Basic filtering and grouping
- No complex time comparisons or multi-period calculations

**GOLD Layer Metrics:**
- Require pre-aggregated data
- Complex time comparisons (year-over-year, period-over-period)
- Multi-table joins with aggregations
- Trend analysis
- Growth rate calculations
- Percentage changes across time periods
- Requires historical aggregations

Classify each metric based on its complexity and requirements."""
        
        metrics_summary = []
        for metric in state["discovered_metrics"]:
            metrics_summary.append(f"""
- {metric.metric_name} ({metric.metric_type}): {metric.metric_description}
  Formula: {metric.formula_description}
  Source Tables: {', '.join(metric.source_tables)}
  Dimensions: {', '.join(metric.dimensions) if metric.dimensions else 'None'}
  Time Granularity: {metric.time_granularity or 'None'}
""")
        
        user_prompt = f"""Classify each discovered metric as SILVER or GOLD layer:

**Discovered Metrics:**
{chr(10).join(metrics_summary)}

**Available Silver Tables:** {', '.join(state.get('silver_tables', []))}
**Available Gold Tables:** {', '.join(state.get('gold_tables', []))}

For each metric, determine:
1. Layer (SILVER or GOLD)
2. Reasoning (why this layer is appropriate)

Return as JSON:
{{
    "classifications": [
        {{
            "metric_name": "metric_name",
            "layer": "silver|gold",
            "reasoning": "Why this layer is appropriate"
        }}
    ]
}}"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            state["messages"].append(response)
            
            # Parse response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            classifications = json.loads(content)
            classifications_dict = {
                c["metric_name"]: c for c in classifications.get("classifications", [])
            }
            
            # Update metric layers
            for metric in state["discovered_metrics"]:
                if metric.metric_name in classifications_dict:
                    classification = classifications_dict[metric.metric_name]
                    metric.layer = MetricLayer(classification["layer"].lower())
                    if not metric.business_rules:
                        metric.business_rules = [classification.get("reasoning", "")]
            
            logger.info(f"Classified {len(state['discovered_metrics'])} metrics")
            
        except Exception as e:
            logger.error(f"Error classifying layers: {e}")
            state["errors"].append(f"Error classifying layers: {str(e)}")
            # Default to gold for complex metrics
            for metric in state["discovered_metrics"]:
                if metric.metric_type in ["growth_rate", "trend", "comparison"]:
                    metric.layer = MetricLayer.GOLD
                else:
                    metric.layer = MetricLayer.SILVER
        
        return state
    
    def plan_metrics(self, state: MetricDiscoveryState) -> MetricDiscoveryState:
        """
        Step 3: Create execution plan for each metric.
        Determines dependencies and execution order.
        """
        system_prompt = """You are a data engineering planner. Create execution plans for metrics.

Analyze dependencies between metrics and determine:
1. Execution order (which metrics must be calculated first)
2. Dependencies (which metrics this metric depends on)
3. Complexity estimation
4. Reasoning for the plan"""
        
        metrics_list = []
        for i, metric in enumerate(state["discovered_metrics"], 1):
            metrics_list.append(f"""
{i}. {metric.metric_name} ({metric.layer.value} layer)
   Type: {metric.metric_type}
   Description: {metric.metric_description}
   Source Tables: {', '.join(metric.source_tables)}
   Formula: {metric.formula_description}
""")
        
        user_prompt = f"""Create execution plans for these metrics:

**Metrics:**
{chr(10).join(metrics_list)}

For each metric, determine:
1. Execution order (1, 2, 3, etc.)
2. Dependencies (list of metric names this depends on)
3. Estimated complexity (low, medium, high)
4. Reasoning

Return as JSON:
{{
    "plans": [
        {{
            "metric_name": "metric_name",
            "execution_order": 1,
            "dependencies": ["dependency1", "dependency2"],
            "estimated_complexity": "low|medium|high",
            "reasoning": "Why this order and complexity"
        }}
    ]
}}"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            state["messages"].append(response)
            
            # Parse response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            plans_data = json.loads(content)
            plans_dict = {
                p["metric_name"]: p for p in plans_data.get("plans", [])
            }
            
            # Create MetricPlan objects
            metric_plans = []
            for metric in state["discovered_metrics"]:
                if metric.metric_name in plans_dict:
                    plan_data = plans_dict[metric.metric_name]
                    plan = MetricPlan(
                        metric=metric,
                        execution_order=plan_data.get("execution_order", 1),
                        dependencies=plan_data.get("dependencies", []),
                        estimated_complexity=plan_data.get("estimated_complexity", "medium"),
                        reasoning=plan_data.get("reasoning", "")
                    )
                    metric_plans.append(plan)
                else:
                    # Default plan
                    plan = MetricPlan(
                        metric=metric,
                        execution_order=1,
                        dependencies=[],
                        estimated_complexity="medium",
                        reasoning="Default plan"
                    )
                    metric_plans.append(plan)
            
            # Sort by execution order
            metric_plans.sort(key=lambda x: x.execution_order)
            state["metric_plans"] = metric_plans
            
            logger.info(f"Created plans for {len(metric_plans)} metrics")
            
        except Exception as e:
            logger.error(f"Error planning metrics: {e}")
            state["errors"].append(f"Error planning metrics: {str(e)}")
            # Create default plans
            state["metric_plans"] = [
                MetricPlan(
                    metric=metric,
                    execution_order=i + 1,
                    dependencies=[],
                    estimated_complexity="medium",
                    reasoning="Default plan"
                )
                for i, metric in enumerate(state["discovered_metrics"])
            ]
        
        return state
    
    def generate_sql(self, state: MetricDiscoveryState) -> MetricDiscoveryState:
        """
        Step 4: Generate SQL for each metric using the centralized SQL generator agent.
        Creates production-ready SQL transformations.
        """
        generated_sql = {}
        
        for plan in state["metric_plans"]:
            metric = plan.metric
            
            # Build table schemas dictionary
            table_schemas = {}
            for table_name in metric.source_tables:
                # Find table in available_tables
                table_info = next(
                    (t for t in state["available_tables"] if t.get("table_name", "").replace("silver_", "").replace("gold_", "") == table_name.replace("silver_", "").replace("gold_", "")),
                    None
                )
                if table_info:
                    table_schemas[table_name] = table_info.get("columns", [])
            
            try:
                # Use SQL generator agent
                sql = self.sql_generator.generate_metric_sql(
                    metric_name=metric.metric_name,
                    metric_description=metric.metric_description,
                    metric_type=metric.metric_type,
                    source_tables=metric.source_tables,
                    formula=metric.formula_description,
                    dimensions=metric.dimensions,
                    time_granularity=metric.time_granularity,
                    table_schemas=table_schemas if table_schemas else None,
                    business_rules=metric.business_rules,
                    target_dialect=SQLDialect.POSTGRESQL  # Will be converted to target dialect if needed
                )
                
                # Store SQL
                generated_sql[metric.metric_name] = sql
                metric.sql_logic = sql
                
                logger.info(f"Generated SQL for metric: {metric.metric_name}")
                
            except Exception as e:
                logger.error(f"Error generating SQL for {metric.metric_name}: {e}")
                state["errors"].append(f"Error generating SQL for {metric.metric_name}: {str(e)}")
                # Create fallback SQL
                fallback_sql = self._create_fallback_sql(metric)
                generated_sql[metric.metric_name] = fallback_sql
                metric.sql_logic = fallback_sql
        
        state["generated_sql"] = generated_sql
        return state
    
    def _create_fallback_sql(self, metric: DiscoveredMetric) -> str:
        """Create basic fallback SQL for a metric"""
        source_table = metric.source_tables[0] if metric.source_tables else "silver_table"
        
        if metric.metric_type == "count":
            sql_expr = "COUNT(*)"
        elif metric.metric_type == "sum":
            sql_expr = "SUM(value)"
        elif metric.metric_type == "avg":
            sql_expr = "AVG(value)"
        else:
            sql_expr = "COUNT(*)"
        
        group_by = ""
        if metric.dimensions:
            group_by = f"GROUP BY {', '.join(metric.dimensions)}"
        
        return f"""
CREATE TABLE gold_{metric.metric_name.lower().replace(' ', '_')} AS
SELECT
    {', '.join(metric.dimensions) if metric.dimensions else ''}
    {sql_expr} as {metric.metric_name}
FROM {source_table}
{group_by};
"""
    
    def validate_output(self, state: MetricDiscoveryState) -> MetricDiscoveryState:
        """
        Step 5: Validate generated metrics and SQL.
        """
        validation_summary = f"""Validation Summary:
- Discovered Metrics: {len(state['discovered_metrics'])}
- Metric Plans: {len(state['metric_plans'])}
- Generated SQL: {len(state['generated_sql'])}
- Errors: {len(state['errors'])}"""
        
        logger.info(validation_summary)
        state["messages"].append(AIMessage(content=validation_summary))
        
        return state
    
    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================
    
    def discover_and_plan_metrics(
        self,
        question: str,
        available_tables: List[Dict[str, Any]],
        silver_tables: Optional[List[str]] = None,
        gold_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Discover and plan metrics from natural language question.
        
        Args:
            question: Natural language question
            available_tables: List of table metadata dictionaries
            silver_tables: Optional list of silver table names
            gold_tables: Optional list of gold table names
            
        Returns:
            Dictionary with discovered_metrics, metric_plans, and generated_sql
        """
        initial_state: MetricDiscoveryState = {
            "natural_language_question": question,
            "available_tables": available_tables,
            "silver_tables": silver_tables or [],
            "gold_tables": gold_tables or [],
            "messages": [],
            "discovered_metrics": [],
            "metric_plans": [],
            "generated_sql": {},
            "errors": []
        }
        
        # Execute workflow
        final_state = self.graph.invoke(initial_state)
        
        return {
            "discovered_metrics": [m.dict() for m in final_state["discovered_metrics"]],
            "metric_plans": [p.dict() for p in final_state["metric_plans"]],
            "generated_sql": final_state["generated_sql"],
            "errors": final_state["errors"],
            "messages": final_state["messages"]
        }

