"""
SQL to DAX Conversion Agent
Converts SQL queries to PowerBI DAX measures and calculated columns
"""

from typing import Dict, List, Any, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import sqlglot
from sqlglot import exp


class DAXMeasure(BaseModel):
    """DAX Measure definition"""
    name: str
    expression: str
    format: str = ""
    description: str = ""


class DAXTable(BaseModel):
    """DAX Table/Query definition"""
    name: str
    source_query: str
    columns: List[str]
    measures: List[DAXMeasure]


class SQLToDAXConverter:
    """Converts SQL queries to PowerBI DAX"""
    
    def __init__(self, llm: ChatAnthropic = None, use_llm_first: bool = True):
        self.llm = llm or ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0
        )
        self.conversion_patterns = self._load_conversion_patterns()
        self.use_llm_first = use_llm_first
    
    def convert(self, sql: str, context: Dict = None) -> DAXTable:
        """
        Convert SQL query to DAX measures
        
        Args:
            sql: SQL query string
            context: Additional context (table schema, business logic)
        
        Returns:
            DAXTable with measures
        """
        # Parse SQL
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except Exception as e:
            print(f"SQL parsing error: {e}")
            # Fallback to LLM-based conversion
            return self._llm_convert(sql, context)
        
        # Extract components
        table_name = self._extract_table_name(parsed)
        select_cols = self._extract_select_columns(parsed)
        group_by = self._extract_group_by(parsed)
        aggregations = self._extract_aggregations(parsed)
        filters = self._extract_filters(parsed)
        
        # LLM-first conversion using SQL, SQLGlot AST, and table data (fallback to rule-based)
        if self.use_llm_first:
            try:
                sqlglot_ast = self._serialize_sqlglot_ast(parsed)
                table_docs = self._collect_table_documents(table_name, select_cols, context)
                llm_table = self._llm_convert_with_ast(sql, sqlglot_ast, table_docs, context)
                if isinstance(llm_table, DAXTable) and llm_table.measures:
                    return llm_table
            except Exception as e:
                # Soft-fallback to rule-based path below
                print(f"LLM-first conversion failed, falling back. Reason: {e}")
        
        # Convert to DAX measures
        measures = []
        
        for agg in aggregations:
            dax_measure = self._convert_aggregation_to_dax(
                agg, table_name, filters, context
            )
            measures.append(dax_measure)
        
        # Handle calculated columns
        for col in select_cols:
            if self._is_calculated_column(col):
                calc_measure = self._convert_calculated_column(col, table_name)
                measures.append(calc_measure)
        
        return DAXTable(
            name=table_name,
            source_query=sql,
            columns=select_cols,
            measures=measures
        )
    
    def _extract_table_name(self, parsed) -> str:
        """Extract primary table name from parsed SQL"""
        for table in parsed.find_all(exp.Table):
            return table.name
        return "UnknownTable"
    
    def _extract_select_columns(self, parsed) -> List[str]:
        """Extract SELECT columns"""
        columns = []
        for select in parsed.find_all(exp.Select):
            for expr in select.expressions:
                if isinstance(expr, exp.Alias):
                    columns.append(expr.alias)
                else:
                    columns.append(str(expr))
        return columns
    
    def _extract_group_by(self, parsed) -> List[str]:
        """Extract GROUP BY columns"""
        for group in parsed.find_all(exp.Group):
            return [str(expr) for expr in group.expressions]
        return []
    
    def _extract_aggregations(self, parsed) -> List[Dict]:
        """Extract aggregation functions"""
        aggregations = []
        
        for select in parsed.find_all(exp.Select):
            for expr in select.expressions:
                if self._is_aggregation(expr):
                    agg_info = self._parse_aggregation(expr)
                    aggregations.append(agg_info)
        
        return aggregations
    
    def _is_aggregation(self, expr) -> bool:
        """Check if expression is an aggregation"""
        agg_functions = {exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max}
        return any(isinstance(expr.find(t), t) for t in agg_functions)
    
    def _parse_aggregation(self, expr) -> Dict:
        """Parse aggregation expression"""
        # Find aggregation function
        for func_type in [exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max]:
            func = expr.find(func_type)
            if func:
                return {
                    "function": func_type.__name__.upper(),
                    "column": str(func.this) if func.this else "*",
                    "alias": expr.alias if isinstance(expr, exp.Alias) else None,
                    "full_expr": str(expr)
                }
        
        return {}
    
    def _extract_filters(self, parsed) -> List[str]:
        """Extract WHERE clause conditions"""
        filters = []
        for where in parsed.find_all(exp.Where):
            filters.append(str(where.this))
        return filters
    
    def _is_calculated_column(self, col: str) -> bool:
        """Check if column is calculated (has operators)"""
        operators = ['+', '-', '*', '/', 'CASE', 'WHEN']
        return any(op in col.upper() for op in operators)
    
    def _convert_aggregation_to_dax(
        self,
        agg: Dict,
        table_name: str,
        filters: List[str],
        context: Dict = None
    ) -> DAXMeasure:
        """Convert SQL aggregation to DAX measure"""
        
        function = agg["function"]
        column = agg["column"]
        alias = agg["alias"] or f"{function}_{column}"
        
        # Base conversion patterns
        if function == "COUNT":
            if column == "*":
                dax_expr = f"COUNTROWS({table_name})"
            else:
                dax_expr = f"COUNTROWS(FILTER({table_name}, NOT(ISBLANK({table_name}[{column}]))))"
        
        elif function == "SUM":
            dax_expr = f"SUM({table_name}[{column}])"
        
        elif function == "AVG":
            dax_expr = f"AVERAGE({table_name}[{column}])"
        
        elif function == "MIN":
            dax_expr = f"MIN({table_name}[{column}])"
        
        elif function == "MAX":
            dax_expr = f"MAX({table_name}[{column}])"
        
        else:
            dax_expr = f"-- Unknown function: {function}"
        
        # Add filters
        if filters:
            filter_conditions = self._convert_filters_to_dax(filters, table_name)
            dax_expr = f"""
CALCULATE(
    {dax_expr},
    {filter_conditions}
)
            """.strip()
        
        return DAXMeasure(
            name=alias,
            expression=dax_expr,
            format=self._infer_format(function),
            description=f"Converted from: {agg['full_expr']}"
        )
    
    def _convert_filters_to_dax(self, filters: List[str], table_name: str) -> str:
        """Convert SQL WHERE conditions to DAX filter context"""
        dax_filters = []
        
        for filter_expr in filters:
            # Simple conversions
            filter_expr = filter_expr.replace("=", " = ")
            filter_expr = filter_expr.replace("lower(", "LOWER(")
            filter_expr = filter_expr.replace(" IN (", " IN {")
            filter_expr = filter_expr.replace(")", "}")
            
            # Add table reference
            dax_filters.append(f"{table_name}[{filter_expr}]")
        
        return ",\n    ".join(dax_filters)
    
    def _convert_calculated_column(self, col: str, table_name: str) -> DAXMeasure:
        """Convert calculated column to DAX"""
        # Use LLM for complex calculations
        return self._llm_convert_expression(col, table_name)
    
    def _infer_format(self, function: str) -> str:
        """Infer DAX format string based on function"""
        if function == "COUNT":
            return "#,##0"
        elif function in ["SUM", "AVG"]:
            return "#,##0.00"
        return ""
    
    def _llm_convert(self, sql: str, context: Dict = None) -> DAXTable:
        """Use LLM for complex SQL to DAX conversion"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in converting SQL queries to PowerBI DAX.
            
            Convert the SQL query to DAX measures. Return the result as:
            1. Table name
            2. List of DAX measures with names and expressions
            3. Ensure proper DAX syntax and filter context
            
            Important DAX patterns:
            - Use CALCULATE for filtered aggregations
            - Use COUNTROWS instead of COUNT(*)
            - Use FILTER for WHERE conditions
            - Use RELATED for JOINs
            - Proper table[column] syntax
            """),
            ("user", """SQL Query:
            {sql}
            
            Context: {context}
            
            Convert to DAX measures. Format:
            Table Name: [name]
            
            Measures:
            1. [Measure Name] = [DAX Expression]
            2. [Measure Name] = [DAX Expression]
            ...
            """)
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                sql=sql,
                context=str(context or {})
            )
        )
        
        # Parse LLM response
        return self._parse_llm_response(response.content, sql)

    def _llm_convert_with_ast(
        self,
        sql: str,
        sqlglot_ast: Dict[str, Any],
        table_documents: Dict[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> DAXTable:
        """Use LLM with SQL, SQLGlot AST, and table data to produce DAX (JSON output)."""
        system_msg = (
            "You are an expert Power BI DAX engineer. Convert SQL queries to high-quality DAX measures "
            "and calculated columns that produce equivalent semantics in Power BI. Prefer measures that "
            "honor filter and row contexts correctly. Use CALCULATE, FILTER, SUMX, VAR, and ALL/ALLEXCEPT "
            "properly. Avoid synthetic columns unless necessary."
        )

        # Build table docs string
        def fmt_table(name: str, doc: Dict[str, Any]) -> str:
            cols = doc.get("columns", [])
            rows = doc.get("sample_rows", [])[:5]
            cols_str = "\n".join([f"- {c.get('name')}: {c.get('type', 'unknown')}" for c in cols])
            rows_str = "\n".join([f"- {r}" for r in rows]) if rows else "- (no samples)"
            return f"TABLE {name}\nCOLUMNS:\n{cols_str}\nSAMPLE ROWS:\n{rows_str}"

        tables_str = "\n\n".join([fmt_table(n, d) for n, d in (table_documents or {}).items()])

        user_msg = f"""
SQL (verbatim):
```
{sql}
```

SQLGlot AST (JSON-ish):
```
{sqlglot_ast}
```

Available tables and samples:
```
{tables_str or '(none)'}
```

Context (if any):
```
{context or {}}
```

Task:
- Return JSON with fields:
  - "table_name": string
  - "dax_measures": list of objects {{"name": string, "expression": string, "format": string, "description": string}}
  - "dax_calculated_columns": list of objects {{"name": string, "expression": string}}
  - "notes": string
Only return valid JSON. Do not wrap in code fences.
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", user_msg),
        ])

        response = self.llm.invoke(prompt.format_messages())

        import json
        data = json.loads(response.content)

        measures: List[DAXMeasure] = []
        for m in data.get("dax_measures", []) or []:
            measures.append(DAXMeasure(
                name=m.get("name", "Unnamed"),
                expression=m.get("expression", ""),
                format=m.get("format", ""),
                description=m.get("description", "")
            ))

        # Calculated columns may be returned; map them as measures or handle separately
        for c in data.get("dax_calculated_columns", []) or []:
            measures.append(DAXMeasure(
                name=c.get("name", "Calculated"),
                expression=c.get("expression", ""),
                description="Calculated column"
            ))

        return DAXTable(
            name=data.get("table_name") or table_documents and next(iter(table_documents.keys()), "GeneratedTable") or "GeneratedTable",
            source_query=sql,
            columns=[],
            measures=measures
        )

    def _collect_table_documents(self, table_name: str, select_cols: List[str], context: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build minimal table document from known columns; enrich with context if provided."""
        cols = []
        for c in select_cols:
            # Take alias/name if available; strip quotes/brackets
            name = str(c).replace("[", "").replace("]", "").replace('"', "")
            cols.append({"name": name, "type": "unknown"})
        return {
            table_name: {
                "columns": cols,
                "sample_rows": []
            }
        }

    def _serialize_sqlglot_ast(self, parsed: Any) -> Dict[str, Any]:
        try:
            return parsed.to_dict() if hasattr(parsed, "to_dict") else {"repr": str(parsed)}
        except Exception:
            return {"repr": str(parsed)}

    def convert_dax_to_sql(
        self,
        dax_text: str,
        table_documents: Dict[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convert DAX measures/columns into SQL using the LLM."""
        system_msg = (
            "You are an expert SQL engineer. Convert DAX measures/columns into a single SQL query that "
            "produces equivalent results. Assume standard SQL unless context specifies a dialect. "
            "Use GROUP BY, window functions, and joins carefully to reproduce DAX semantics."
        )

        def fmt_table(name: str, doc: Dict[str, Any]) -> str:
            cols = doc.get("columns", [])
            rows = doc.get("sample_rows", [])[:5]
            cols_str = "\n".join([f"- {c.get('name')}: {c.get('type', 'unknown')}" for c in cols])
            rows_str = "\n".join([f"- {r}" for r in rows]) if rows else "- (no samples)"
            return f"TABLE {name}\nCOLUMNS:\n{cols_str}\nSAMPLE ROWS:\n{rows_str}"

        tables_str = "\n\n".join([fmt_table(n, d) for n, d in (table_documents or {}).items()])

        user_msg = f"""
DAX:
```
{dax_text}
```

Available tables and samples:
```
{tables_str or '(none)'}
```

Context (if any):
```
{context or {}}
```

Task:
- Return JSON with fields:
  - "sql": string query
  - "notes": string
Only return valid JSON. Do not wrap in code fences.
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", user_msg),
        ])

        response = self.llm.invoke(prompt.format_messages())
        import json
        data = json.loads(response.content)
        return data.get("sql", "")
    
    def _llm_convert_expression(self, expr: str, table_name: str) -> DAXMeasure:
        """Use LLM to convert complex expressions"""
        
        prompt = f"""
        Convert this SQL expression to DAX:
        
        Expression: {expr}
        Table: {table_name}
        
        Return only the DAX expression.
        """
        
        response = self.llm.invoke(prompt)
        
        return DAXMeasure(
            name=f"Calculated_{expr[:20]}",
            expression=response.content.strip(),
            description=f"Converted from: {expr}"
        )
    
    def _parse_llm_response(self, response: str, original_sql: str) -> DAXTable:
        """Parse LLM response into DAXTable"""
        lines = response.strip().split('\n')
        table_name = "GeneratedTable"
        measures = []
        
        for line in lines:
            if "Table Name:" in line:
                table_name = line.split(":")[-1].strip()
            elif "=" in line and not line.startswith("//"):
                # Parse measure
                parts = line.split("=", 1)
                if len(parts) == 2:
                    name = parts[0].strip().replace("[", "").replace("]", "")
                    expression = parts[1].strip()
                    measures.append(DAXMeasure(
                        name=name,
                        expression=expression
                    ))
        
        return DAXTable(
            name=table_name,
            source_query=original_sql,
            columns=[],
            measures=measures
        )
    
    def _load_conversion_patterns(self) -> Dict:
        """Load common SQL to DAX conversion patterns"""
        return {
            "COUNT(*)": "COUNTROWS({table})",
            "COUNT(DISTINCT": "DISTINCTCOUNT({table}[{column}])",
            "SUM(": "SUM({table}[{column}])",
            "AVG(": "AVERAGE({table}[{column}])",
            "MIN(": "MIN({table}[{column}])",
            "MAX(": "MAX({table}[{column}])",
            "CASE WHEN": "IF(",
            "GROUP BY": "-- Use implicit grouping in DAX",
            "LEFT JOIN": "RELATED({related_table}[{column}])",
        }
    
    def generate_power_query_m(self, sql: str, connection_string: str = None) -> str:
        """Generate Power Query M code for data loading"""
        
        m_code = f"""
let
    Source = Sql.Database("{connection_string or 'localhost'}", "database"),
    CustomSQL = Value.NativeQuery(
        Source,
        "{sql.replace('"', '""')}",
        null,
        [EnableFolding=true]
    ),
    ChangedType = Table.TransformColumnTypes(CustomSQL, {{}})
in
    ChangedType
        """
        
        return m_code.strip()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example SQL queries
    sql_queries = [
        """
        SELECT 
            training_title AS "Training Title",
            (COUNT(CASE WHEN completed_date IS NULL THEN 1 END) * 100.0 / COUNT(*)) AS "Drop-Off Rate"
        FROM csod_training_records
        WHERE lower(transcript_status) IN (lower('Registered'), lower('Approved'))
        GROUP BY training_title
        ORDER BY "Drop-Off Rate" DESC
        LIMIT 1
        """,
        
        """
        SELECT 
            full_name,
            COUNT(*) as overdue_count
        FROM training_records
        WHERE due_date < CURRENT_DATE
        GROUP BY full_name
        HAVING COUNT(*) > 5
        """,
        
        """
        SELECT
            department,
            AVG(completion_rate) as avg_completion,
            SUM(total_hours) as total_hours
        FROM training_summary
        WHERE year = 2024
        GROUP BY department
        """
    ]
    
    converter = SQLToDAXConverter()
    
    for i, sql in enumerate(sql_queries, 1):
        print(f"\n{'='*70}")
        print(f"Query {i}")
        print(f"{'='*70}")
        print(f"SQL:\n{sql}\n")
        
        dax_table = converter.convert(sql)
        
        print(f"Table: {dax_table.name}")
        print(f"\nMeasures:")
        for measure in dax_table.measures:
            print(f"\n  {measure.name} = ")
            print(f"    {measure.expression}")
            if measure.description:
                print(f"    // {measure.description}")
        
        # Generate Power Query M
        print(f"\nPower Query M:")
        print(converter.generate_power_query_m(sql))
