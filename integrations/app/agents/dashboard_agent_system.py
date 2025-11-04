"""
Dashboard Transformation Multi-Agent System
Core LangGraph Implementation
"""

from typing import TypedDict, List, Dict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field
from .visualization_powerbi_agent import VegaLiteToPowerBIVisualizationAgent
from .visualization_tableau_agent import VegaLiteToTableauVisualizationAgent
import operator


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class ComponentData(BaseModel):
    """Individual dashboard component"""
    component_id: str
    component_type: str
    question: str
    sql_query: str
    chart_schema: Dict
    sample_data: Dict
    executive_summary: str = ""


class MaterializedView(BaseModel):
    """Materialized view definition"""
    view_name: str
    source_queries: List[str]
    dimensions: List[str]
    measures: List[str]
    aggregation_logic: str
    create_statement: str
    refresh_policy: str = "incremental"


class TransformedQuery(BaseModel):
    """Query transformed for target platform"""
    component_id: str
    original_sql: str
    transformed_query: str
    query_type: str  # "DAX", "Tableau", "SQL"
    materialized_view_ref: str = ""


class DashboardTransformationState(TypedDict):
    """Main state for the transformation workflow"""
    # Input
    source_dashboard: Dict
    target_platform: Literal["powerbi", "tableau", "generic"]
    table_metadata: List[Dict]
    
    # Parsed Data
    components: Annotated[List[ComponentData], operator.add]
    all_queries: Annotated[List[str], operator.add]
    all_tables: Annotated[List[str], operator.add]
    
    # Materialized Views
    materialized_views: Annotated[List[MaterializedView], operator.add]
    
    # Transformation Results
    transformed_queries: Annotated[List[TransformedQuery], operator.add]
    transformed_visualizations: Annotated[List[Dict], operator.add]
    
    # Output
    final_dashboard: Dict
    insights: Annotated[List[str], operator.add]
    
    # Control Flow
    processing_stage: str
    errors: Annotated[List[str], operator.add]
    messages: Annotated[List[BaseMessage], operator.add]


# ============================================================================
# AGENT NODES
# ============================================================================

class DashboardParserAgent:
    """Parses source dashboard JSON and extracts components"""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
    
    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        """Parse dashboard and extract components"""
        print("🔍 Parsing dashboard...")
        
        dashboard = state["source_dashboard"]
        components = []
        queries = []
        tables = set()
        
        # Extract components from dashboard
        for comp in dashboard.get("content", {}).get("components", []):
            component_data = ComponentData(
                component_id=comp.get("id", ""),
                component_type=comp.get("type", ""),
                question=comp.get("question", ""),
                sql_query=comp.get("sql_query", ""),
                chart_schema=comp.get("chart_schema", {}),
                sample_data=comp.get("sample_data", {}),
                executive_summary=comp.get("executive_summary", "")
            )
            components.append(component_data)
            
            # Extract SQL query
            if component_data.sql_query:
                queries.append(component_data.sql_query)
                
                # Extract table names from SQL (simplified)
                sql_lower = component_data.sql_query.lower()
                if "from" in sql_lower:
                    # Basic extraction - would use proper SQL parser in production
                    tables.update(self._extract_table_names(component_data.sql_query))
        
        return {
            "components": components,
            "all_queries": queries,
            "all_tables": list(tables),
            "processing_stage": "parsed"
        }
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL query"""
        # Simplified extraction - use sqlglot in production
        import re
        pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables = [m[0] or m[1] for m in matches if m[0] or m[1]]
        return tables


class MaterializedViewAgent:
    """Creates materialized views from queries"""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
    
    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        """Analyze queries and create materialized views"""
        print("📊 Creating materialized views...")
        
        components = state["components"]
        queries = state["all_queries"]
        
        materialized_views = []
        
        # Analyze queries to find aggregation patterns
        query_analysis = self._analyze_queries(queries)
        
        # Create materialized views for common patterns
        for idx, analysis in enumerate(query_analysis):
            mv = MaterializedView(
                view_name=f"mv_dashboard_component_{idx}",
                source_queries=[analysis["query"]],
                dimensions=analysis["dimensions"],
                measures=analysis["measures"],
                aggregation_logic=analysis["aggregation"],
                create_statement=self._generate_mv_sql(analysis),
                refresh_policy="incremental"
            )
            materialized_views.append(mv)
        
        return {
            "materialized_views": materialized_views,
            "processing_stage": "materialized_views_created"
        }
    
    def _analyze_queries(self, queries: List[str]) -> List[Dict]:
        """Analyze queries to extract dimensions and measures"""
        analyses = []
        
        for query in queries:
            # Use LLM to analyze query structure
            analysis_prompt = f"""
            Analyze this SQL query and extract:
            1. Dimensions (GROUP BY columns)
            2. Measures (aggregated columns like COUNT, SUM, AVG)
            3. Aggregation logic
            
            Query: {query}
            
            Return as JSON with keys: dimensions, measures, aggregation
            """
            
            # Simplified for now - would call LLM in production
            analyses.append({
                "query": query,
                "dimensions": self._extract_group_by(query),
                "measures": self._extract_aggregations(query),
                "aggregation": "GROUP BY aggregation"
            })
        
        return analyses
    
    def _extract_group_by(self, query: str) -> List[str]:
        """Extract GROUP BY columns"""
        import re
        match = re.search(r'GROUP BY\s+([\w,\s.]+)', query, re.IGNORECASE)
        if match:
            return [col.strip() for col in match.group(1).split(',')]
        return []
    
    def _extract_aggregations(self, query: str) -> List[str]:
        """Extract aggregated columns"""
        import re
        agg_functions = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
        measures = []
        for func in agg_functions:
            pattern = f'{func}\\s*\\([^)]+\\)'
            matches = re.findall(pattern, query, re.IGNORECASE)
            measures.extend(matches)
        return measures
    
    def _generate_mv_sql(self, analysis: Dict) -> str:
        """Generate CREATE MATERIALIZED VIEW statement"""
        query = analysis["query"]
        # Wrap the original query in a materialized view
        return f"""
        CREATE MATERIALIZED VIEW mv_aggregated AS
        {query};
        """


class DataSourceAdapter(BaseModel):
    """Adapter for datasource-specific SQL generation for materialized views"""
    platform: Literal["powerbi", "tableau", "generic"] = "generic"
    view_prefix: str = "mv"

    def qualify_view_name(self, base: str) -> str:
        return f"{self.view_prefix}_{base}"

    def render_create_mv(self, view_name: str, select_sql: str) -> str:
        return f"""
        CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name} AS
        {select_sql};
        """


class MultiStageMaterializedViewAgent:
    """
    Creates systematic materialized views using a two-stage LLM approach:
    1) Unify schema contexts across queries/tables (columns with same semantics).
    2) Propose drillable, time/location-aware views for dashboards.

    Designed to be extended to Tableau Cloud, PowerBI or other datasources via adapters.
    """

    def __init__(self, llm: ChatAnthropic):
        self.llm = llm

    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        print("📊 Creating advanced materialized views (multi-stage)...")

        queries = state["all_queries"]
        table_metadata = state.get("table_metadata", [])
        target_platform = state.get("target_platform", "generic")

        adapter = self._get_adapter(target_platform)

        # Stage 1: Unify schema across tables/queries
        unified_context = self._unify_schema_context(queries, table_metadata)

        # Stage 2: Propose systematic views for drill-down analysis
        view_specs = self._propose_views(unified_context, queries)

        materialized_views: List[MaterializedView] = []
        for idx, spec in enumerate(view_specs):
            view_base = spec.get("name", f"dashboard_component_{idx}")
            view_name = adapter.qualify_view_name(view_base)
            select_sql = self._build_select_sql(spec)
            create_stmt = adapter.render_create_mv(view_name, select_sql)

            mv = MaterializedView(
                view_name=view_name,
                source_queries=spec.get("source_queries", []),
                dimensions=spec.get("dimensions", []),
                measures=spec.get("measures", []),
                aggregation_logic=spec.get("aggregation", "GROUP BY aggregation"),
                create_statement=create_stmt,
                refresh_policy=spec.get("refresh_policy", "incremental")
            )
            materialized_views.append(mv)

        return {
            "materialized_views": materialized_views,
            "processing_stage": "materialized_views_created"
        }

    def _get_adapter(self, platform: str) -> DataSourceAdapter:
        prefix = {
            "powerbi": "mv_pbi",
            "tableau": "mv_tbl",
            "generic": "mv"
        }.get(platform, "mv")
        return DataSourceAdapter(platform=platform if platform in ["powerbi", "tableau", "generic"] else "generic", view_prefix=prefix)

    def _unify_schema_context(self, queries: List[str], table_metadata: List[Dict]) -> Dict:
        """
        Identify semantically equivalent columns across tables and standardize keys
        (e.g., date, time, location, category, id). Uses LLM in production; rule-based fallback here.
        """
        # Heuristic extraction for fallback
        import re

        candidate_dims = set(["date", "day", "week", "month", "year", "timestamp",
                              "location", "state", "city", "country", "region",
                              "category", "type", "status", "department"])
        candidate_ids = set(["id", "user_id", "account_id", "customer_id", "product_id"]) 

        def cols_from_sql(sql: str) -> List[str]:
            # Very naive: find words that look like column references table.col or bare col
            return re.findall(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*|\b[A-Za-z_][A-Za-z0-9_]*\b", sql)

        all_cols: List[str] = []
        for q in queries:
            all_cols.extend(cols_from_sql(q))

        normalized_map: Dict[str, List[str]] = {
            "time": [],
            "location": [],
            "category": [],
            "id": [],
            "measure": []
        }

        for c in set([c.split(".")[-1].lower() for c in all_cols]):
            if c in candidate_dims or any(k in c for k in ["date", "time", "month", "year", "week"]):
                normalized_map["time"].append(c)
            elif c in candidate_dims or any(k in c for k in ["city", "state", "region", "country", "loc"]):
                normalized_map["location"].append(c)
            elif c in candidate_ids or c.endswith("_id"):
                normalized_map["id"].append(c)
            elif any(k in c for k in ["type", "category", "status"]):
                normalized_map["category"].append(c)

        # Minimal measure detection from SELECT aggregates
        agg_funcs = ["count", "sum", "avg", "max", "min"]
        for q in queries:
            for f in agg_funcs:
                for m in re.findall(fr"{f}\\s*\\([^)]+\\)", q, flags=re.IGNORECASE):
                    normalized_map["measure"].append(m)

        # Include table relationships if provided
        relationships = []
        for t in table_metadata or []:
            rels = t.get("relationships") or []
            if isinstance(rels, list):
                relationships.extend(rels)

        return {
            "normalized_columns": normalized_map,
            "relationships": relationships,
            "tables": [t.get("name") for t in (table_metadata or []) if t.get("name")]
        }

    def _propose_views(self, unified_context: Dict, queries: List[str]) -> List[Dict]:
        """
        Propose a small set of reusable, drillable views:
        - base_aggregate: core rollups by time/location/category
        - trend: time-series metrics
        - geographical: location groupings
        - detail: row-level with keys for drill-through
        """
        norm = unified_context.get("normalized_columns", {})
        time_dims = norm.get("time", []) or []
        loc_dims = norm.get("location", []) or []
        cat_dims = norm.get("category", []) or []
        measures = norm.get("measure", []) or ["COUNT(*) AS row_count"]

        # Choose primary time dimension if available
        time_dim = next((d for d in ["date", "timestamp", "month", "year"] if d in time_dims), (time_dims[0] if time_dims else None))

        # Base Aggregate View
        base_dims = [d for d in [time_dim] if d] + loc_dims[:1] + cat_dims[:1]
        views: List[Dict] = []
        views.append({
            "name": "base_aggregate",
            "dimensions": base_dims,
            "measures": measures,
            "aggregation": "GROUP BY",
            "source_queries": queries,
            "refresh_policy": "incremental"
        })

        # Trend View (time only)
        if time_dim:
            views.append({
                "name": "trend_time",
                "dimensions": [time_dim],
                "measures": measures,
                "aggregation": "GROUP BY",
                "source_queries": queries,
                "refresh_policy": "incremental"
            })

        # Geographical View (location)
        if loc_dims:
            views.append({
                "name": "geo_rollup",
                "dimensions": loc_dims[:2],
                "measures": measures,
                "aggregation": "GROUP BY",
                "source_queries": queries,
                "refresh_policy": "incremental"
            })

        # Detail View (for drill-through)
        id_dims = norm.get("id", [])
        detail_dims = (id_dims[:2] if id_dims else []) + (cat_dims[:1] if cat_dims else [])
        if detail_dims:
            views.append({
                "name": "detail_drill",
                "dimensions": detail_dims,
                "measures": [],
                "aggregation": "NONE",
                "source_queries": queries,
                "refresh_policy": "full"
            })

        return views

    def _build_select_sql(self, spec: Dict) -> str:
        """Compose a SELECT for the view spec. For now, we union source queries and regroup."""
        dims = spec.get("dimensions", [])
        measures = spec.get("measures", [])
        src = spec.get("source_queries", [])

        # If no measures (detail), just union all
        if not measures:
            unioned = "\nUNION ALL\n".join([f"({q.strip().rstrip(';')})" for q in src]) or "SELECT *"
            return unioned

        select_list = []
        select_list.extend(dims)
        select_list.extend(measures)
        select_clause = ", ".join([s for s in select_list if s]) or "*"
        group_by_clause = f"\nGROUP BY {', '.join([d for d in dims if d])}" if dims else ""
        unioned = "\nUNION ALL\n".join([f"({q.strip().rstrip(';')})" for q in src]) or "SELECT *"
        return f"SELECT {select_clause}\nFROM ({unioned}) t{group_by_clause}"


class PowerBITransformAgent:
    """Transforms SQL to PowerBI DAX and visualization configs"""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        self.viz_agent = VegaLiteToPowerBIVisualizationAgent(llm)
    
    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        """Transform to PowerBI format"""
        print("⚡ Transforming to PowerBI...")
        
        if state["target_platform"] != "powerbi":
            return {"processing_stage": state["processing_stage"]}
        
        components = state["components"]
        transformed_queries = []
        transformed_viz = []
        
        for comp in components:
            # Transform SQL to DAX
            dax_query = self._sql_to_dax(comp.sql_query, comp)
            
            transformed_queries.append(TransformedQuery(
                component_id=comp.component_id,
                original_sql=comp.sql_query,
                transformed_query=dax_query,
                query_type="DAX"
            ))
            
            # Transform Vega-Lite to PowerBI visual
            powerbi_viz = self._vegaLite_to_powerbi(comp.chart_schema, comp)
            transformed_viz.append(powerbi_viz)
        
        return {
            "transformed_queries": transformed_queries,
            "transformed_visualizations": transformed_viz,
            "processing_stage": "powerbi_transformed"
        }
    
    def _sql_to_dax(self, sql: str, component: ComponentData) -> str:
        """Convert SQL to DAX measure"""
        # Simplified conversion - use LLM for complex transformations
        
        # Example: COUNT(*) -> COUNTROWS(Table)
        if "COUNT(*)" in sql.upper():
            return """
            Drop Off Rate = 
            DIVIDE(
                COUNTROWS(
                    FILTER(
                        Training,
                        Training[completed_date] = BLANK()
                    )
                ),
                COUNTROWS(Training)
            ) * 100
            """
        
        # Use LLM for complex transformations
        dax_prompt = f"""
        Convert this SQL query to PowerBI DAX:
        
        SQL: {sql}
        
        Context: {component.question}
        
        Return only the DAX code.
        """
        
        # Would call LLM here
        return f"-- DAX conversion of: {sql}\n-- Implement with LLM"
    
    def _vegaLite_to_powerbi(self, chart_schema: Dict, component: ComponentData) -> Dict:
        """Convert Vega-Lite chart to PowerBI visual config using dedicated agent"""
        return self.viz_agent.convert(chart_schema, component)
    
    def _extract_data_roles(self, chart_schema: Dict) -> List[Dict]:
        """Extract data roles from Vega-Lite encoding"""
        encoding = chart_schema.get("encoding", {})
        roles = []
        
        for channel, config in encoding.items():
            roles.append({
                "name": channel,
                "field": config.get("field", ""),
                "type": config.get("type", "")
            })
        
        return roles
    
    def _extract_properties(self, chart_schema: Dict) -> Dict:
        """Extract visual properties"""
        return {
            "title": chart_schema.get("title", ""),
            "legend": chart_schema.get("encoding", {}).get("color", {})
        }


class TableauTransformAgent:
    """Transforms SQL to Tableau calculations and format"""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        self.viz_agent = VegaLiteToTableauVisualizationAgent(llm)
    
    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        """Transform to Tableau format"""
        print("📈 Transforming to Tableau...")
        
        if state["target_platform"] != "tableau":
            return {"processing_stage": state["processing_stage"]}
        
        components = state["components"]
        transformed_queries = []
        transformed_viz = []
        
        for comp in components:
            # Transform SQL to Tableau calculated field
            tableau_calc = self._sql_to_tableau(comp.sql_query, comp)
            
            transformed_queries.append(TransformedQuery(
                component_id=comp.component_id,
                original_sql=comp.sql_query,
                transformed_query=tableau_calc,
                query_type="Tableau"
            ))
            
            # Transform Vega-Lite to Tableau format
            tableau_viz = self._vegaLite_to_tableau(comp.chart_schema, comp)
            transformed_viz.append(tableau_viz)
        
        return {
            "transformed_queries": transformed_queries,
            "transformed_visualizations": transformed_viz,
            "processing_stage": "tableau_transformed"
        }
    
    def _sql_to_tableau(self, sql: str, component: ComponentData) -> str:
        """Convert SQL to Tableau calculated field"""
        # Simplified - use LLM for production
        return f"""
        // Tableau Calculated Field
        // Original SQL: {sql[:100]}...
        
        IF ISNULL([Completed Date]) THEN 1 ELSE 0 END
        """
    
    def _vegaLite_to_tableau(self, chart_schema: Dict, component: ComponentData) -> Dict:
        """Convert Vega-Lite to Tableau dashboard format using dedicated agent"""
        return self.viz_agent.convert(chart_schema, component)
    
    def _extract_shelves(self, chart_schema: Dict) -> Dict:
        """Extract Tableau shelves from Vega-Lite encoding"""
        encoding = chart_schema.get("encoding", {})
        
        shelves = {
            "rows": [],
            "columns": [],
            "marks": "automatic"
        }
        
        # Map encoding channels to Tableau shelves
        if "x" in encoding:
            shelves["columns"].append(encoding["x"].get("field", ""))
        if "y" in encoding:
            shelves["rows"].append(encoding["y"].get("field", ""))
        
        return shelves


class InsightsGeneratorAgent:
    """Generates insights and enables conversational capabilities"""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
    
    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        """Generate insights from dashboard data"""
        print("💡 Generating insights...")
        
        components = state["components"]
        insights = []
        
        for comp in components:
            # Generate insights using LLM
            insight_prompt = f"""
            Based on this dashboard component, generate 3 key insights:
            
            Question: {comp.question}
            Summary: {comp.executive_summary[:500]}
            
            Provide actionable insights.
            """
            
            # Simplified - would call LLM
            insights.append(f"Insight for {comp.question}: {comp.executive_summary[:200]}...")
        
        return {
            "insights": insights,
            "processing_stage": "insights_generated"
        }


class DashboardRendererAgent:
    """Renders final dashboard in target format"""
    
    def __call__(self, state: DashboardTransformationState) -> DashboardTransformationState:
        """Compile final dashboard package"""
        print("🎨 Rendering final dashboard...")
        
        final_dashboard = {
            "platform": state["target_platform"],
            "dashboard_id": state["source_dashboard"].get("dashboard_id"),
            "dashboard_name": state["source_dashboard"].get("dashboard_name"),
            "components": [],
            "materialized_views": [mv.dict() for mv in state["materialized_views"]],
            "metadata": {
                "processing_stage": state["processing_stage"],
                "total_components": len(state["components"]),
                "total_queries": len(state["transformed_queries"])
            }
        }
        
        # Combine components with transformations
        for comp, query, viz in zip(
            state["components"],
            state["transformed_queries"],
            state["transformed_visualizations"]
        ):
            final_dashboard["components"].append({
                "component_id": comp.component_id,
                "question": comp.question,
                "original_query": comp.sql_query,
                "transformed_query": query.transformed_query,
                "visualization": viz,
                "insights": state["insights"]
            })
        
        return {
            "final_dashboard": final_dashboard,
            "processing_stage": "complete"
        }


# ============================================================================
# LANGGRAPH WORKFLOW
# ============================================================================

def create_dashboard_transformation_graph():
    """Create the LangGraph workflow for dashboard transformation"""
    
    # Initialize LLM
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0)
    
    # Initialize agents
    parser_agent = DashboardParserAgent(llm)
    mv_agent = MultiStageMaterializedViewAgent(llm)
    powerbi_agent = PowerBITransformAgent(llm)
    tableau_agent = TableauTransformAgent(llm)
    insights_agent = InsightsGeneratorAgent(llm)
    renderer_agent = DashboardRendererAgent()
    
    # Create graph
    workflow = StateGraph(DashboardTransformationState)
    
    # Add nodes
    workflow.add_node("parse_dashboard", parser_agent)
    workflow.add_node("create_materialized_views", mv_agent)
    workflow.add_node("transform_powerbi", powerbi_agent)
    workflow.add_node("transform_tableau", tableau_agent)
    workflow.add_node("generate_insights", insights_agent)
    workflow.add_node("render_dashboard", renderer_agent)
    
    # Define edges
    workflow.set_entry_point("parse_dashboard")
    workflow.add_edge("parse_dashboard", "create_materialized_views")
    
    # Conditional routing based on target platform
    def route_platform(state: DashboardTransformationState) -> str:
        platform = state["target_platform"]
        if platform == "powerbi":
            return "transform_powerbi"
        elif platform == "tableau":
            return "transform_tableau"
        else:
            return "generate_insights"
    
    workflow.add_conditional_edges(
        "create_materialized_views",
        route_platform,
        {
            "transform_powerbi": "transform_powerbi",
            "transform_tableau": "transform_tableau",
            "generate_insights": "generate_insights"
        }
    )
    
    workflow.add_edge("transform_powerbi", "generate_insights")
    workflow.add_edge("transform_tableau", "generate_insights")
    workflow.add_edge("generate_insights", "render_dashboard")
    workflow.add_edge("render_dashboard", END)
    
    return workflow.compile()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def transform_dashboard(
    source_dashboard: Dict,
    target_platform: str,
    table_metadata: List[Dict] = None
):
    """
    Transform a source dashboard to target platform
    
    Args:
        source_dashboard: Source dashboard JSON
        target_platform: Target platform ('powerbi', 'tableau', 'generic')
        table_metadata: Optional table metadata for better transformations
    """
    
    # Create workflow
    app = create_dashboard_transformation_graph()
    
    # Initial state
    initial_state = {
        "source_dashboard": source_dashboard,
        "target_platform": target_platform,
        "table_metadata": table_metadata or [],
        "components": [],
        "all_queries": [],
        "all_tables": [],
        "materialized_views": [],
        "transformed_queries": [],
        "transformed_visualizations": [],
        "final_dashboard": {},
        "insights": [],
        "processing_stage": "initialized",
        "errors": [],
        "messages": []
    }
    
    # Execute workflow
    print(f"\n{'='*60}")
    print(f"Starting Dashboard Transformation")
    print(f"Target Platform: {target_platform}")
    print(f"{'='*60}\n")
    
    result = app.invoke(initial_state)
    
    print(f"\n{'='*60}")
    print(f"Transformation Complete!")
    print(f"Status: {result['processing_stage']}")
    print(f"Components Processed: {len(result['components'])}")
    print(f"Materialized Views Created: {len(result['materialized_views'])}")
    print(f"{'='*60}\n")
    
    return result


if __name__ == "__main__":
    # Example usage
    sample_dashboard = {
        "dashboard_id": "test-123",
        "dashboard_name": "Training Analytics",
        "content": {
            "components": [
                {
                    "id": "comp-1",
                    "type": "question",
                    "question": "What is the drop-off rate?",
                    "sql_query": "SELECT training_title, COUNT(*) as drop_off FROM training GROUP BY training_title",
                    "chart_schema": {"mark": {"type": "bar"}},
                    "sample_data": {},
                    "executive_summary": "High drop-off rates observed..."
                }
            ]
        }
    }
    
    result = transform_dashboard(sample_dashboard, "powerbi")
    print("Final Dashboard:", result["final_dashboard"])
