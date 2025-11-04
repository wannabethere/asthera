"""
Materialized View Optimizer
Analyzes queries and creates optimized materialized views for dashboard performance
"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
import sqlglot
from sqlglot import exp
from collections import defaultdict
import hashlib


@dataclass
class QueryPattern:
    """Represents a common query pattern"""
    tables: Set[str]
    dimensions: List[str]
    measures: List[str]
    filters: List[str]
    time_column: str = None
    grain: str = "row"  # row, day, week, month, year


@dataclass
class MaterializedViewSpec:
    """Specification for a materialized view"""
    view_name: str
    description: str
    base_query: str
    create_statement: str
    refresh_strategy: str  # incremental, full, on-demand
    refresh_schedule: str = None
    dependencies: List[str] = None
    estimated_rows: int = 0
    covers_queries: List[str] = None  # Query patterns this MV covers


class MaterializedViewOptimizer:
    """Optimizes dashboard queries by creating materialized views"""
    
    def __init__(self, llm: ChatAnthropic = None):
        self.llm = llm or ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0
        )
    
    def analyze_queries(self, queries: List[str]) -> List[QueryPattern]:
        """
        Analyze multiple queries to find common patterns
        
        Args:
            queries: List of SQL queries from dashboard
            
        Returns:
            List of common query patterns
        """
        patterns = []
        
        for query in queries:
            try:
                pattern = self._extract_pattern(query)
                patterns.append(pattern)
            except Exception as e:
                print(f"Error analyzing query: {e}")
                continue
        
        return patterns
    
    def create_materialized_views(
        self,
        queries: List[str],
        table_metadata: Dict[str, List[str]] = None
    ) -> List[MaterializedViewSpec]:
        """
        Create optimal materialized views for dashboard queries
        
        Strategy:
        1. Identify common query patterns
        2. Find aggregation opportunities
        3. Create base materialized views
        4. Create derived views if beneficial
        
        Args:
            queries: Dashboard SQL queries
            table_metadata: Table schemas for better optimization
            
        Returns:
            List of materialized view specifications
        """
        # Analyze query patterns
        patterns = self.analyze_queries(queries)
        
        # Group patterns by similarity
        pattern_groups = self._group_similar_patterns(patterns)
        
        # Create materialized views
        mv_specs = []
        
        for group in pattern_groups:
            # Create base aggregated view
            base_mv = self._create_base_mv(group, table_metadata)
            if base_mv:
                mv_specs.append(base_mv)
            
            # Check if derived views would be beneficial
            derived_mvs = self._create_derived_mvs(base_mv, group)
            mv_specs.extend(derived_mvs)
        
        # Optimize for incremental refresh
        for mv in mv_specs:
            mv.refresh_strategy = self._determine_refresh_strategy(mv)
        
        return mv_specs
    
    def _extract_pattern(self, query: str) -> QueryPattern:
        """Extract pattern from a single query"""
        try:
            parsed = sqlglot.parse_one(query, read="postgres")
        except:
            # Fallback to text analysis
            return self._extract_pattern_text(query)
        
        # Extract tables
        tables = {table.name for table in parsed.find_all(exp.Table)}
        
        # Extract dimensions (GROUP BY columns)
        dimensions = []
        for group in parsed.find_all(exp.Group):
            dimensions.extend([str(expr) for expr in group.expressions])
        
        # Extract measures (aggregations)
        measures = []
        for select in parsed.find_all(exp.Select):
            for expr in select.expressions:
                if self._is_aggregation(expr):
                    measures.append(str(expr))
        
        # Extract filters
        filters = []
        for where in parsed.find_all(exp.Where):
            filters.append(str(where.this))
        
        # Detect time column
        time_column = self._detect_time_column(parsed)
        
        # Infer grain
        grain = self._infer_grain(dimensions, time_column)
        
        return QueryPattern(
            tables=tables,
            dimensions=dimensions,
            measures=measures,
            filters=filters,
            time_column=time_column,
            grain=grain
        )
    
    def _extract_pattern_text(self, query: str) -> QueryPattern:
        """Fallback text-based pattern extraction"""
        import re
        
        # Extract tables
        tables = set(re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)', query, re.IGNORECASE))
        tables = {t[0] or t[1] for t in tables}
        
        # Extract GROUP BY
        group_by = re.search(r'GROUP BY\s+([\w,\s.]+)', query, re.IGNORECASE)
        dimensions = []
        if group_by:
            dimensions = [d.strip() for d in group_by.group(1).split(',')]
        
        # Extract aggregations
        measures = re.findall(
            r'(COUNT|SUM|AVG|MIN|MAX)\s*\([^)]+\)',
            query,
            re.IGNORECASE
        )
        
        return QueryPattern(
            tables=tables,
            dimensions=dimensions,
            measures=measures,
            filters=[],
            grain="row"
        )
    
    def _is_aggregation(self, expr) -> bool:
        """Check if expression is an aggregation"""
        agg_types = {exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max}
        return any(expr.find(t) for t in agg_types)
    
    def _detect_time_column(self, parsed) -> str:
        """Detect time/date column in query"""
        time_keywords = ['date', 'time', 'timestamp', 'created', 'updated', 'completed']
        
        for select in parsed.find_all(exp.Select):
            for expr in select.expressions:
                col_name = str(expr).lower()
                if any(kw in col_name for kw in time_keywords):
                    return str(expr)
        
        return None
    
    def _infer_grain(self, dimensions: List[str], time_column: str) -> str:
        """Infer aggregation grain from dimensions"""
        if not dimensions:
            return "total"
        
        if time_column:
            time_lower = time_column.lower()
            if "year" in time_lower:
                return "year"
            elif "month" in time_lower:
                return "month"
            elif "week" in time_lower:
                return "week"
            elif "day" in time_lower or "date" in time_lower:
                return "day"
        
        return "row"
    
    def _group_similar_patterns(
        self,
        patterns: List[QueryPattern]
    ) -> List[List[QueryPattern]]:
        """Group similar query patterns together"""
        groups = defaultdict(list)
        
        for pattern in patterns:
            # Create similarity key based on tables and grain
            key = (
                tuple(sorted(pattern.tables)),
                pattern.grain,
                tuple(sorted(pattern.dimensions[:3]))  # Top 3 dimensions
            )
            groups[key].append(pattern)
        
        return list(groups.values())
    
    def _create_base_mv(
        self,
        pattern_group: List[QueryPattern],
        table_metadata: Dict[str, List[str]] = None
    ) -> MaterializedViewSpec:
        """Create base materialized view for a pattern group"""
        
        if not pattern_group:
            return None
        
        # Merge patterns to find common dimensions and measures
        common_tables = set.intersection(*[p.tables for p in pattern_group])
        all_dimensions = []
        all_measures = []
        
        for pattern in pattern_group:
            all_dimensions.extend(pattern.dimensions)
            all_measures.extend(pattern.measures)
        
        # Deduplicate while preserving order
        dimensions = list(dict.fromkeys(all_dimensions))
        measures = list(dict.fromkeys(all_measures))
        
        # Generate view name
        view_name = self._generate_view_name(common_tables, pattern_group[0].grain)
        
        # Build aggregated query
        base_query = self._build_aggregated_query(
            tables=common_tables,
            dimensions=dimensions,
            measures=measures,
            grain=pattern_group[0].grain
        )
        
        # Generate CREATE statement
        create_statement = f"""
CREATE MATERIALIZED VIEW {view_name} AS
{base_query};

-- Create indexes for better query performance
CREATE INDEX idx_{view_name}_dims ON {view_name} ({', '.join(dimensions[:3])});
        """.strip()
        
        return MaterializedViewSpec(
            view_name=view_name,
            description=f"Aggregated view at {pattern_group[0].grain} grain",
            base_query=base_query,
            create_statement=create_statement,
            refresh_strategy="incremental",
            covers_queries=[str(p) for p in pattern_group]
        )
    
    def _generate_view_name(self, tables: Set[str], grain: str) -> str:
        """Generate meaningful view name"""
        table_str = "_".join(sorted(tables))[:30]
        hash_suffix = hashlib.md5(table_str.encode()).hexdigest()[:6]
        return f"mv_{table_str}_{grain}_{hash_suffix}"
    
    def _build_aggregated_query(
        self,
        tables: Set[str],
        dimensions: List[str],
        measures: List[str],
        grain: str
    ) -> str:
        """Build aggregated SQL query for materialized view"""
        
        # Handle multiple tables (simplified JOIN logic)
        from_clause = ", ".join(tables) if len(tables) == 1 else f"{list(tables)[0]}"
        
        # Build SELECT clause
        select_parts = []
        select_parts.extend(dimensions)
        
        # Convert measures to proper aggregations
        agg_measures = []
        for i, measure in enumerate(measures):
            if "COUNT" not in measure.upper() and "SUM" not in measure.upper():
                # Assume it needs aggregation
                agg_measures.append(f"SUM({measure}) as measure_{i}")
            else:
                agg_measures.append(f"{measure} as measure_{i}")
        
        select_parts.extend(agg_measures)
        
        # Build query
        query = f"""
SELECT 
    {',\n    '.join(select_parts)}
FROM {from_clause}
        """
        
        if dimensions:
            query += f"\nGROUP BY {', '.join(dimensions)}"
        
        return query.strip()
    
    def _create_derived_mvs(
        self,
        base_mv: MaterializedViewSpec,
        pattern_group: List[QueryPattern]
    ) -> List[MaterializedViewSpec]:
        """Create derived materialized views if beneficial"""
        
        derived_views = []
        
        # Check if we need time-based rollups
        if any(p.time_column for p in pattern_group):
            # Create monthly rollup if base is daily
            if "day" in base_mv.view_name:
                monthly_mv = self._create_time_rollup(base_mv, "month")
                if monthly_mv:
                    derived_views.append(monthly_mv)
        
        return derived_views
    
    def _create_time_rollup(
        self,
        base_mv: MaterializedViewSpec,
        target_grain: str
    ) -> MaterializedViewSpec:
        """Create time-based rollup view"""
        
        view_name = base_mv.view_name.replace("_day_", f"_{target_grain}_")
        
        rollup_query = f"""
SELECT 
    DATE_TRUNC('{target_grain}', date_column) as {target_grain},
    dimension_1,
    dimension_2,
    SUM(measure_1) as measure_1,
    SUM(measure_2) as measure_2
FROM {base_mv.view_name}
GROUP BY DATE_TRUNC('{target_grain}', date_column), dimension_1, dimension_2
        """
        
        create_statement = f"""
CREATE MATERIALIZED VIEW {view_name} AS
{rollup_query};
        """
        
        return MaterializedViewSpec(
            view_name=view_name,
            description=f"Time rollup to {target_grain} grain",
            base_query=rollup_query,
            create_statement=create_statement,
            refresh_strategy="incremental",
            dependencies=[base_mv.view_name]
        )
    
    def _determine_refresh_strategy(self, mv: MaterializedViewSpec) -> str:
        """Determine optimal refresh strategy"""
        
        # Use LLM to analyze query and suggest strategy
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze this materialized view and suggest the best refresh strategy.
            
            Options:
            - incremental: Use when data is append-only or has time partitions
            - full: Use when data can be updated anywhere
            - on-demand: Use for rarely changing data
            
            Return only one word: incremental, full, or on-demand
            """),
            ("user", """Materialized View:
            {query}
            
            Refresh strategy:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(query=mv.base_query)
        )
        
        strategy = response.content.strip().lower()
        if strategy in ["incremental", "full", "on-demand"]:
            return strategy
        
        return "incremental"  # Default
    
    def generate_refresh_schedule(
        self,
        mv_spec: MaterializedViewSpec,
        dashboard_usage: str = "hourly"
    ) -> str:
        """Generate cron schedule for MV refresh"""
        
        schedules = {
            "real-time": "*/5 * * * *",  # Every 5 minutes
            "hourly": "0 * * * *",       # Every hour
            "daily": "0 2 * * *",        # 2 AM daily
            "weekly": "0 2 * * 0",       # 2 AM Sunday
        }
        
        return schedules.get(dashboard_usage, "0 * * * *")
    
    def optimize_for_platform(
        self,
        mv_specs: List[MaterializedViewSpec],
        platform: str
    ) -> List[MaterializedViewSpec]:
        """Platform-specific optimizations"""
        
        if platform == "powerbi":
            return self._optimize_for_powerbi(mv_specs)
        elif platform == "tableau":
            return self._optimize_for_tableau(mv_specs)
        
        return mv_specs
    
    def _optimize_for_powerbi(
        self,
        mv_specs: List[MaterializedViewSpec]
    ) -> List[MaterializedViewSpec]:
        """PowerBI-specific optimizations"""
        
        # PowerBI works well with star schema
        # Add surrogate keys if needed
        for mv in mv_specs:
            if "CREATE MATERIALIZED VIEW" in mv.create_statement:
                # Add surrogate key
                mv.create_statement = mv.create_statement.replace(
                    "CREATE MATERIALIZED VIEW",
                    "CREATE MATERIALIZED VIEW -- With surrogate key\n"
                )
        
        return mv_specs
    
    def _optimize_for_tableau(
        self,
        mv_specs: List[MaterializedViewSpec]
    ) -> List[MaterializedViewSpec]:
        """Tableau-specific optimizations"""
        
        # Tableau benefits from denormalized wide tables
        for mv in mv_specs:
            mv.description += " (Optimized for Tableau)"
        
        return mv_specs


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Sample dashboard queries
    queries = [
        """
        SELECT 
            training_title,
            COUNT(*) as total_registrations,
            COUNT(CASE WHEN completed_date IS NOT NULL THEN 1 END) as completed
        FROM csod_training_records
        WHERE registration_date >= '2024-01-01'
        GROUP BY training_title
        """,
        
        """
        SELECT 
            training_title,
            department,
            COUNT(*) as count
        FROM csod_training_records
        GROUP BY training_title, department
        """,
        
        """
        SELECT 
            DATE_TRUNC('month', registration_date) as month,
            training_title,
            COUNT(*) as registrations
        FROM csod_training_records
        WHERE registration_date >= '2024-01-01'
        GROUP BY DATE_TRUNC('month', registration_date), training_title
        """
    ]
    
    optimizer = MaterializedViewOptimizer()
    
    print("Analyzing queries and creating materialized views...\n")
    
    # Create materialized views
    mv_specs = optimizer.create_materialized_views(queries)
    
    print(f"Created {len(mv_specs)} materialized views:\n")
    
    for i, mv in enumerate(mv_specs, 1):
        print(f"{'='*70}")
        print(f"Materialized View {i}: {mv.view_name}")
        print(f"{'='*70}")
        print(f"Description: {mv.description}")
        print(f"Refresh Strategy: {mv.refresh_strategy}")
        print(f"\nCreate Statement:")
        print(mv.create_statement)
        print(f"\nCovers {len(mv.covers_queries or [])} queries")
        print()
