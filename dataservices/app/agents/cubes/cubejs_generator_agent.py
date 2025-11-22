"""
Cube.js Definition Generator Agent
Generates valid Cube.js JSON definitions for cubes, views, and pre-aggregations
"""

from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import json


class CubeDimension(BaseModel):
    """Cube.js dimension definition"""
    name: str
    sql: str
    type: str  # string, number, time, geo
    title: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    case: Optional[Dict[str, Any]] = None
    primaryKey: Optional[bool] = False


class CubeMeasure(BaseModel):
    """Cube.js measure definition"""
    name: str
    sql: str
    type: str  # count, countDistinct, sum, avg, min, max, runningTotal, etc.
    title: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    filters: Optional[List[Dict[str, Any]]] = None
    rollingWindow: Optional[Dict[str, Any]] = None
    drillMembers: Optional[List[str]] = None


class CubeJoin(BaseModel):
    """Cube.js join definition"""
    name: str
    sql: str
    relationship: str  # hasOne, hasMany, belongsTo


class CubePreAggregation(BaseModel):
    """Cube.js pre-aggregation definition"""
    name: str
    type: str  # rollup, originalSql, rollupJoin, rollupLambda
    measures: Optional[List[str]] = None
    dimensions: Optional[List[str]] = None
    timeDimension: Optional[str] = None
    granularity: Optional[str] = None  # day, week, month, year
    partitionGranularity: Optional[str] = None
    refreshKey: Optional[Dict[str, Any]] = None
    buildRangeStart: Optional[Dict[str, str]] = None
    buildRangeEnd: Optional[Dict[str, str]] = None


class CubeDefinitionFull(BaseModel):
    """Complete Cube.js cube definition"""
    name: str
    sql: str
    title: Optional[str] = None
    description: Optional[str] = None
    dimensions: List[CubeDimension] = Field(default_factory=list)
    measures: List[CubeMeasure] = Field(default_factory=list)
    joins: List[CubeJoin] = Field(default_factory=list)
    preAggregations: List[CubePreAggregation] = Field(default_factory=list)
    segments: List[Dict[str, Any]] = Field(default_factory=list)


class CubeView(BaseModel):
    """Cube.js view definition"""
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    cubes: List[Dict[str, Any]]
    includes: Optional[List[str]] = None
    excludes: Optional[List[str]] = None


class CubeJsGeneratorAgent:
    """Generates Cube.js definitions from schema analysis"""
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        from app.core.dependencies import get_llm
        self.llm = get_llm(temperature=0, model=model_name)
        self.parser = JsonOutputParser()
    
    def generate_cube(
        self,
        table_name: str,
        schema_analysis: Dict[str, Any],
        layer: str = "raw",
        sql_override: Optional[str] = None
    ) -> CubeDefinitionFull:
        """
        Generate a complete Cube.js cube definition.
        
        Args:
            table_name: Name of the table/cube
            schema_analysis: Schema analysis from SchemaAnalysisAgent
            layer: Medallion layer (raw, silver, gold)
            sql_override: Optional custom SQL for the cube
            
        Returns:
            Complete Cube.js cube definition
        """
        system_prompt = """You are a Cube.js expert. Generate valid Cube.js cube definitions.

**Cube.js Syntax Rules:**

1. **Dimensions**:
   - string: Text/categorical data
   - number: Numeric identifiers
   - time: Dates/timestamps
   - geo: Geographic data

2. **Measures**:
   - count: COUNT(*)
   - countDistinct: COUNT(DISTINCT column)
   - sum: SUM(column)
   - avg: AVG(column)
   - min: MIN(column)
   - max: MAX(column)
   - runningTotal: Cumulative sum

3. **SQL References**:
   - Use ${CUBE}.column_name for referencing columns
   - Use ${CubeName.dimension} for cross-cube references

4. **Formatting**:
   - Currency: format: 'currency'
   - Percentage: format: 'percent'
   - Date: format: 'MM/DD/YYYY'

5. **Best Practices**:
   - Add title and description for user-friendliness
   - Use primaryKey for identifier dimensions
   - Set drillMembers for measures to enable drill-down
   - Group related dimensions and measures

Generate production-ready definitions following Cube.js documentation exactly."""
        
        columns_info = json.dumps(schema_analysis.get("columns", []), indent=2)
        grain = schema_analysis.get("grain", "Row-level detail")
        
        user_prompt = f"""Generate a Cube.js cube for: {table_name} ({layer} layer)

**Schema Analysis:**
```json
{columns_info}
```

**Table Grain:** {grain}

**SQL:** {sql_override or f"SELECT * FROM {table_name}"}

Generate a complete cube definition with:

1. **Dimensions** (one per categorical/text/date column):
   - Proper type (string, number, time)
   - User-friendly titles
   - SQL using ${{CUBE}}.column_name syntax

2. **Measures** (one per numeric column + count measures):
   - Appropriate aggregation type
   - Descriptive names (e.g., totalAmount, averagePrice)
   - Add drillMembers for detail views

3. **Metadata**:
   - Clear title and description
   - Document the grain

Return as valid JSON matching Cube.js schema."""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        try:
            cube_dict = self.parser.parse(response.content)
            
            # Parse nested structures
            if "dimensions" in cube_dict:
                cube_dict["dimensions"] = [
                    CubeDimension(**dim) if isinstance(dim, dict) else dim
                    for dim in cube_dict["dimensions"]
                ]
            
            if "measures" in cube_dict:
                cube_dict["measures"] = [
                    CubeMeasure(**meas) if isinstance(meas, dict) else meas
                    for meas in cube_dict["measures"]
                ]
            
            return CubeDefinitionFull(**cube_dict)
            
        except Exception as e:
            # Fallback to basic cube
            return self._create_basic_cube(table_name, schema_analysis, layer, sql_override)
    
    def _create_basic_cube(
        self,
        table_name: str,
        schema_analysis: Dict[str, Any],
        layer: str,
        sql_override: Optional[str]
    ) -> CubeDefinitionFull:
        """Create a basic cube definition as fallback"""
        
        dimensions = []
        measures = []
        
        for col in schema_analysis.get("columns", []):
            col_name = col.get("name", "")
            col_type = col.get("data_type", "VARCHAR")
            is_measure = col.get("is_measure", False)
            is_temporal = col.get("is_temporal", False)
            is_identifier = col.get("is_identifier", False)
            
            if is_temporal:
                dimensions.append(CubeDimension(
                    name=col_name,
                    sql=f"${{{table_name}}}.{col_name}",
                    type="time",
                    title=col_name.replace("_", " ").title()
                ))
            elif is_identifier:
                dimensions.append(CubeDimension(
                    name=col_name,
                    sql=f"${{{table_name}}}.{col_name}",
                    type="number",
                    primaryKey=True,
                    title=col_name.replace("_", " ").title()
                ))
            elif not is_measure:
                dimensions.append(CubeDimension(
                    name=col_name,
                    sql=f"${{{table_name}}}.{col_name}",
                    type="string",
                    title=col_name.replace("_", " ").title()
                ))
            else:
                # Add as measure
                measures.append(CubeMeasure(
                    name=col_name,
                    sql=f"${{{table_name}}}.{col_name}",
                    type="sum",
                    title=col_name.replace("_", " ").title()
                ))
        
        # Always add count measure
        measures.insert(0, CubeMeasure(
            name="count",
            sql="1",
            type="count",
            title="Count",
            drillMembers=[d.name for d in dimensions if d.primaryKey]
        ))
        
        return CubeDefinitionFull(
            name=table_name,
            sql=sql_override or f"SELECT * FROM {table_name}",
            title=table_name.replace("_", " ").title(),
            description=f"{layer.title()} layer cube for {table_name}",
            dimensions=dimensions,
            measures=measures
        )
    
    def generate_view(
        self,
        view_name: str,
        cube_names: List[str],
        description: str = ""
    ) -> CubeView:
        """
        Generate a Cube.js view definition.
        
        Args:
            view_name: Name of the view
            cube_names: List of cube names to include
            description: Description of the view
            
        Returns:
            Cube.js view definition
        """
        system_prompt = """You are a Cube.js expert. Generate view definitions.

**Cube.js Views:**
- Combine multiple cubes into a single interface
- Can include/exclude specific dimensions and measures
- Simplify complex data models
- Provide business-friendly access

**View Syntax:**
```javascript
view(`ViewName`, {
  cubes: [
    {
      join_path: CubeName,
      includes: ['dimension1', 'measure1']
    }
  ]
})
```

Generate clean, well-documented views."""
        
        user_prompt = f"""Generate a Cube.js view: {view_name}

**Cubes to Include:** {', '.join(cube_names)}
**Purpose:** {description or 'Unified view of related data'}

Create a view that:
1. Includes all specified cubes
2. Uses appropriate join paths
3. Includes the most useful dimensions and measures
4. Has clear documentation

Return as valid JSON."""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        try:
            view_dict = self.parser.parse(response.content)
            return CubeView(**view_dict)
        except:
            # Create basic view
            cubes = [{"join_path": cube} for cube in cube_names]
            
            return CubeView(
                name=view_name,
                title=view_name.replace("_", " ").title(),
                description=description or f"Combined view of {', '.join(cube_names)}",
                cubes=cubes
            )
    
    def generate_pre_aggregations(
        self,
        cube_name: str,
        dimensions: List[str],
        measures: List[str],
        time_dimensions: List[str],
        query_patterns: Optional[Dict[str, Any]] = None
    ) -> List[CubePreAggregation]:
        """
        Generate pre-aggregation definitions for performance optimization.
        
        Args:
            cube_name: Name of the cube
            dimensions: List of dimension names
            measures: List of measure names
            time_dimensions: List of time dimension names
            query_patterns: Optional expected query patterns
            
        Returns:
            List of pre-aggregation definitions
        """
        system_prompt = """You are a Cube.js performance optimization expert.

**Pre-Aggregation Types:**

1. **rollup**: Aggregate data by dimensions
   - Best for: Grouping queries with measures
   - Example: Daily sales by region

2. **originalSql**: Cache full query results
   - Best for: Complex queries with many filters
   - Example: Detail reports

3. **rollupJoin**: Pre-join multiple cubes
   - Best for: Frequent joins between cubes
   - Example: Orders with customer details

4. **rollupLambda**: Serverless aggregations
   - Best for: Dynamic, large-scale aggregations

**Refresh Strategies:**
- every: Refresh on schedule (e.g., '1 hour', '1 day')
- sql: Refresh when SQL query changes
- immutable: Never refresh (historical data)

**Partitioning:**
- Use partitionGranularity for time-series data
- Benefits: Faster refreshes, efficient queries

Design pre-aggregations that balance performance and storage."""
        
        query_info = json.dumps(query_patterns or {}, indent=2)
        
        user_prompt = f"""Generate pre-aggregations for cube: {cube_name}

**Dimensions:** {', '.join(dimensions)}
**Measures:** {', '.join(measures)}
**Time Dimensions:** {', '.join(time_dimensions)}

**Expected Query Patterns:**
```json
{query_info}
```

Create pre-aggregations for:
1. **Time-series rollup**: Daily/weekly/monthly aggregations
2. **Dimensional rollup**: Common dimension combinations
3. **Detail cache**: Full data with frequently used filters

For each pre-aggregation:
- Choose appropriate type (rollup, originalSql, etc.)
- Define refresh strategy
- Set partition granularity if applicable
- Balance performance vs. storage

Return as JSON array."""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        try:
            pre_aggs_data = self.parser.parse(response.content)
            if isinstance(pre_aggs_data, dict) and "preAggregations" in pre_aggs_data:
                pre_aggs_data = pre_aggs_data["preAggregations"]
            return [CubePreAggregation(**pa) for pa in pre_aggs_data]
        except:
            return self._create_basic_pre_aggregations(
                cube_name, dimensions, measures, time_dimensions
            )
    
    def _create_basic_pre_aggregations(
        self,
        cube_name: str,
        dimensions: List[str],
        measures: List[str],
        time_dimensions: List[str]
    ) -> List[CubePreAggregation]:
        """Create basic pre-aggregations as fallback"""
        
        pre_aggs = []
        
        # Time-series rollup
        if time_dimensions and measures:
            pre_aggs.append(CubePreAggregation(
                name="dailyRollup",
                type="rollup",
                measures=measures[:3],  # Limit to first 3 measures
                dimensions=dimensions[:2],  # Limit to first 2 dimensions
                timeDimension=time_dimensions[0],
                granularity="day",
                partitionGranularity="month",
                refreshKey={
                    "every": "1 day"
                }
            ))
        
        # Main rollup
        if dimensions and measures:
            pre_aggs.append(CubePreAggregation(
                name="mainRollup",
                type="rollup",
                measures=measures,
                dimensions=dimensions[:5],  # Limit dimensions
                refreshKey={
                    "every": "1 hour"
                }
            ))
        
        return pre_aggs
    
    def export_to_javascript(self, cube: CubeDefinitionFull) -> str:
        """
        Export cube definition as JavaScript for Cube.js schema files.
        
        Args:
            cube: Cube definition
            
        Returns:
            JavaScript code string
        """
        js_template = f"""cube(`{cube.name}`, {{
  sql: `{cube.sql}`,
  
  title: "{cube.title or cube.name}",
  description: "{cube.description or ''}",
  
  dimensions: {{
{self._format_dimensions(cube.dimensions)}
  }},
  
  measures: {{
{self._format_measures(cube.measures)}
  }},
  
  {"joins: {" + self._format_joins(cube.joins) + "}," if cube.joins else ""}
  
  {"preAggregations: {" + self._format_pre_aggregations(cube.preAggregations) + "}" if cube.preAggregations else ""}
}});
"""
        return js_template
    
    def _format_dimensions(self, dimensions: List[CubeDimension]) -> str:
        """Format dimensions for JavaScript export"""
        lines = []
        for dim in dimensions:
            lines.append(f"    {dim.name}: {{")
            lines.append(f"      sql: `{dim.sql}`,")
            lines.append(f"      type: `{dim.type}`,")
            if dim.title:
                lines.append(f"      title: `{dim.title}`,")
            if dim.primaryKey:
                lines.append(f"      primaryKey: true,")
            lines.append(f"    }},")
        return "\n".join(lines)
    
    def _format_measures(self, measures: List[CubeMeasure]) -> str:
        """Format measures for JavaScript export"""
        lines = []
        for meas in measures:
            lines.append(f"    {meas.name}: {{")
            lines.append(f"      sql: `{meas.sql}`,")
            lines.append(f"      type: `{meas.type}`,")
            if meas.title:
                lines.append(f"      title: `{meas.title}`,")
            if meas.drillMembers:
                lines.append(f"      drillMembers: [{', '.join(meas.drillMembers)}],")
            lines.append(f"    }},")
        return "\n".join(lines)
    
    def _format_joins(self, joins: List[CubeJoin]) -> str:
        """Format joins for JavaScript export"""
        # Simplified - just return empty for now
        return ""
    
    def _format_pre_aggregations(self, pre_aggs: List[CubePreAggregation]) -> str:
        """Format pre-aggregations for JavaScript export"""
        # Simplified - just return empty for now
        return ""


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    agent = CubeJsGeneratorAgent()
    
    # Example schema analysis
    schema_analysis = {
        "table_name": "dev_network_devices",
        "grain": "One row per network device",
        "columns": [
            {
                "name": "id",
                "data_type": "BIGINT",
                "is_identifier": True,
                "is_measure": False,
                "is_temporal": False
            },
            {
                "name": "ip",
                "data_type": "VARCHAR",
                "is_dimension": True,
                "is_measure": False
            },
            {
                "name": "updated_at",
                "data_type": "TIMESTAMP",
                "is_temporal": True
            },
            {
                "name": "days_since_last_seen",
                "data_type": "INTEGER",
                "is_measure": True
            }
        ]
    }
    
    # Generate cube
    print("Generating Cube.js definition...")
    cube = agent.generate_cube(
        "dev_network_devices",
        schema_analysis,
        layer="silver"
    )
    
    print("\nCube Definition (JSON):")
    print(json.dumps(cube.dict(), indent=2))
    
    print("\n" + "="*80)
    print("Cube Definition (JavaScript):")
    print("="*80)
    print(agent.export_to_javascript(cube))
    
    # Generate pre-aggregations
    print("\n" + "="*80)
    print("Pre-Aggregations:")
    print("="*80)
    pre_aggs = agent.generate_pre_aggregations(
        cube_name="dev_network_devices",
        dimensions=["ip", "site", "manufacturer"],
        measures=["count", "days_since_last_seen"],
        time_dimensions=["updated_at"]
    )
    
    for pa in pre_aggs:
        print(json.dumps(pa.dict(), indent=2))
