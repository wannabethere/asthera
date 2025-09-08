import logging
from typing import Any, Dict, Optional, List
import asyncio
import json

import orjson
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent import AgentExecutor
from langchain.schema import AgentAction, AgentFinish
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema import LLMResult

from app.agents.nodes.sql.utils.tableau_bi_utils import (
    TableauChartDataPreprocessor,
    TableauChartGenerationPostProcessor,
    TableauChartGenerationResults,
    tableau_chart_generation_instructions,
    create_tableau_data_preprocessor_tool,
    create_tableau_chart_postprocessor_tool,
    TableauChartExporter,
)

logger = logging.getLogger("lexy-ai-service")


class TableauChartGenerationAgent:
    """Langchain agent for Tableau chart generation"""
    
    def __init__(self, llm, **kwargs):
        self.llm = llm
        self.data_preprocessor = TableauChartDataPreprocessor()
        self.post_processor = TableauChartGenerationPostProcessor()
        self.exporter = TableauChartExporter()
        
        # Create tools
        self.tools = [
            create_tableau_data_preprocessor_tool(),
            create_tableau_chart_postprocessor_tool(),
        ]
        
        # Initialize agent
        self.agent = self._create_agent()
        
        # System prompt for Tableau chart generation
        self.system_prompt = f"""
        ### TASK ###
        
        You are a data visualization expert specializing in Tableau! Given the user's question, SQL query, sample data, sample column values, and column metadata, you need to generate a Tableau visualization configuration in JSON format and provide the most suitable chart type.
        
        You need to analyze the data structure, understand the user's intent, and create an appropriate Tableau visualization configuration that effectively visualizes the data to answer the user's question.
        
        Additionally, provide a concise and easy-to-understand reasoning to describe why you chose this particular chart type and configuration based on the question, SQL query, sample data, and column metadata.
        
        {tableau_chart_generation_instructions}
        
        ### EXISTING CHART SCHEMA CONSIDERATION ###
        
        If an existing chart schema is provided, you should:
        1. FIRST evaluate if the existing chart schema is suitable for the current data and query
        2. If the existing schema is appropriate, REUSE it with minimal modifications (like updating field names to match current data)
        3. If the existing schema is not suitable, generate a new one that better fits the current requirements
        4. In your reasoning, explain whether you reused the existing schema or generated a new one and why
        
        When reusing an existing schema:
        - Keep the same chart type and overall structure
        - Update field names to match the current data columns
        - Preserve styling, colors, and layout preferences
        - Only modify what's necessary for the new data
        
        ### OUTPUT FORMAT ###
        
        Please provide your chain of thought reasoning, chart type, and the Tableau visualization configuration in JSON format.
        
        {{
            "reasoning": "<REASON_TO_CHOOSE_THE_CHART_TYPE_AND_CONFIGURATION_IN_STRING_FORMATTED_IN_LANGUAGE_PROVIDED_BY_USER>",
            "chart_type": "bar" | "line" | "area" | "scatter" | "pie" | "treemap" | "heatmap" | "histogram" | "box_plot" | "bullet" | "gantt" | "map" | "symbol_map" | "filled_map" | "dual_axis" | "combined" | "",
            "chart_config": <TABLEAU_VISUALIZATION_JSON_CONFIGURATION>
        }}
        
        ### IMPORTANT NOTES ###
        
        - Ensure all field names in the configuration exist in the actual data columns
        - Choose appropriate aggregation methods based on data types (Sum for sales/revenue, Count for items, Average for rates)
        - Use proper date hierarchies for time-based data (Year, Quarter, Month, Day)
        - Consider the user's question intent when selecting chart type
        - For multiple metrics, consider using dual-axis or combined charts
        - For hierarchical data, use treemaps or nested visualizations
        - For geographical data, use map visualizations
        - For distributions, use histograms or box plots
        - For trends over time, use line or area charts
        - For comparisons across categories, use bar charts
        - For correlations, use scatter plots
        - For part-to-whole relationships, use pie charts or treemaps
        """
        
        # User prompt template
        self.user_prompt_template = PromptTemplate(
            input_variables=["query", "sql", "sample_data", "sample_column_values", "column_metadata", "language", "existing_chart_schema"],
            template="""
            ### INPUT ###
            Question: {query}
            SQL: {sql}
            Sample Data: {sample_data}
            Sample Column Values: {sample_column_values}
            Column Metadata: {column_metadata}
            Language: {language}
            Existing Chart Schema: {existing_chart_schema}
            
            Please analyze the data and user question step by step to create the most appropriate Tableau visualization.
            """
        )
    
    def _create_agent(self) -> AgentExecutor:
        """Create and configure the Langchain agent"""
        try:
            agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                early_stopping_method="generate"
            )
            return agent
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise
    
    async def generate_chart(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_config: bool = True,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Tableau chart configuration using the agent
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_config: Whether to remove data from config
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        try:
            # Preprocess data
            preprocessed_data = self.data_preprocessor.run(data)
            
            # Create the prompt
            prompt = self.user_prompt_template.format(
                query=query,
                sql=sql,
                sample_data=preprocessed_data["sample_data"],
                sample_column_values=preprocessed_data["sample_column_values"],
                column_metadata=preprocessed_data["column_metadata"],
                language=language,
                existing_chart_schema=json.dumps(existing_chart_schema) if existing_chart_schema else "None"
            )
            
            # Generate chart using LLM directly (more controlled approach)
            chart_result = await self._generate_chart_direct(prompt)
            
            # Post-process the result
            final_result = self.post_processor.run(
                chart_result, 
                preprocessed_data["sample_data"], 
                remove_data_from_chart_config
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in chart generation: {e}")
            return {
                "chart_config": {},
                "reasoning": f"Error generating chart: {str(e)}",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }
    
    async def _generate_chart_direct(self, prompt: str) -> str:
        """Generate chart using LLM directly with structured output"""
        try:
            # Create a chain for structured output using pipe operator
            generation_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}"
            )
            
            # Create the chain using pipe operator
            chain = (
                {"system_prompt": lambda x: self.system_prompt, "user_prompt": lambda x: x}
                | generation_prompt
                | self.llm
            )
            
            # Generate response
            result = await chain.ainvoke(prompt)
            
            # Ensure the result is a properly formatted JSON string
            try:
                # First try to parse the raw result
                parsed_result = orjson.loads(result)
                return orjson.dumps(parsed_result).decode('utf-8')
            except orjson.JSONDecodeError:
                # If parsing fails, try to extract JSON from the text
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        # Validate the extracted JSON
                        parsed_result = orjson.loads(json_str)
                        return orjson.dumps(parsed_result).decode('utf-8')
                    except orjson.JSONDecodeError:
                        pass
                
                # If all parsing attempts fail, return a default structure
                default_result = {
                    "reasoning": "Failed to parse LLM response into valid JSON format.",
                    "chart_type": "",
                    "chart_config": {}
                }
                return orjson.dumps(default_result).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error in direct chart generation: {e}")
            default_result = {
                "reasoning": f"Error: {str(e)}",
                "chart_type": "",
                "chart_config": {}
            }
            return orjson.dumps(default_result).decode('utf-8')


class TableauChartGenerationPipeline:
    """Main pipeline for Tableau chart generation using Langchain"""
    
    def __init__(self, llm, **kwargs):
        self.agent = TableauChartGenerationAgent(llm, **kwargs)
        self.exporter = TableauChartExporter()
    
    async def run(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        remove_data_from_chart_config: bool = True,
        export_format: Optional[str] = None,
        existing_chart_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the complete Tableau chart generation pipeline
        
        Args:
            query: Natural language query
            sql: SQL query
            data: Data dictionary with columns and data
            language: Language for the chart
            remove_data_from_chart_config: Whether to remove data from config
            export_format: Optional export format
            existing_chart_schema: Optional existing chart schema to consider for reuse
        """
        logger.info("Tableau Chart Generation pipeline is running...")
        
        try:
            # Generate chart
            result = await self.agent.generate_chart(
                query=query,
                sql=sql,
                data=data,
                language=language,
                remove_data_from_chart_config=remove_data_from_chart_config,
                existing_chart_schema=existing_chart_schema
            )
            
            # Add export functionality if requested
            if export_format and result.get("success", False):
                chart_config = result.get("chart_config", {})
                
                if export_format == "json":
                    result["exported_json"] = self.exporter.to_tableau_json(chart_config)
                elif export_format == "twb":
                    result["twb_workbook"] = self.exporter.to_tableau_workbook(chart_config)
                elif export_format == "tds":
                    result["tds_datasource"] = self.exporter.to_tableau_datasource(chart_config)
                elif export_format == "vql":
                    result["vql_query"] = self.exporter.to_tableau_vql(chart_config)
                elif export_format == "all":
                    result["exported_json"] = self.exporter.to_tableau_json(chart_config)
                    result["twb_workbook"] = self.exporter.to_tableau_workbook(chart_config)
                    result["tds_datasource"] = self.exporter.to_tableau_datasource(chart_config)
                    result["vql_query"] = self.exporter.to_tableau_vql(chart_config)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in pipeline execution: {e}")
            return {
                "chart_config": {},
                "reasoning": f"Pipeline error: {str(e)}",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }
    
    async def generate_chart_from_template(
        self,
        existing_chart: Dict[str, Any],
        new_data: Dict[str, Any],
        field_mapping: Optional[Dict[str, str]] = None,
        language: str = "English"
    ) -> Dict[str, Any]:
        """Generate a new chart using an existing chart as a template with new data
        
        Args:
            existing_chart: The existing chart configuration to use as template
            new_data: New data to visualize using the template
            field_mapping: Optional mapping from old field names to new field names
            language: Language for the chart titles and labels
            
        Returns:
            Dict containing the new chart configuration
        """
        try:
            logger.info("Generating Tableau chart from template...")
            
            # Extract chart config from existing chart
            if "chart_config" in existing_chart:
                template_config = existing_chart["chart_config"]
            elif "results" in existing_chart and "chart_config" in existing_chart["results"]:
                template_config = existing_chart["results"]["chart_config"]
            else:
                template_config = existing_chart
            
            if not template_config:
                return {
                    "success": False,
                    "error": "No valid chart config found in existing chart",
                    "chart_config": {},
                    "reasoning": "Template chart is invalid"
                }
            
            # Preprocess new data
            preprocessed_data = self.agent.data_preprocessor.run(new_data)
            new_columns = preprocessed_data["sample_data"].get("columns", [])
            
            # Create field mapping if not provided
            if not field_mapping:
                field_mapping = self._create_automatic_field_mapping(template_config, new_columns)
            
            # Generate new chart config based on template
            new_chart_config = self._adapt_chart_config(
                template_config, 
                new_columns, 
                field_mapping, 
                language
            )
            
            # Validate the new chart config
            validation_result = self._validate_chart_config(new_chart_config, new_columns)
            
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Chart validation failed: {validation_result['error']}",
                    "chart_config": new_chart_config,
                    "reasoning": f"Generated chart from template but validation failed: {validation_result['error']}"
                }
            
            # Determine chart type from config
            chart_type = self._extract_chart_type_from_config(new_chart_config)
            
            return {
                "success": True,
                "chart_config": new_chart_config,
                "chart_type": chart_type,
                "reasoning": f"Successfully generated Tableau chart from template using field mapping: {field_mapping}",
                "field_mapping": field_mapping,
                "template_info": {
                    "original_chart_type": existing_chart.get("chart_type", "unknown"),
                    "fields_mapped": len(field_mapping),
                    "validation_passed": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating Tableau chart from template: {e}")
            return {
                "success": False,
                "error": str(e),
                "chart_config": {},
                "reasoning": f"Error generating chart from template: {str(e)}"
            }
    
    def _create_automatic_field_mapping(
        self, 
        template_config: Dict[str, Any], 
        new_columns: List[str]
    ) -> Dict[str, str]:
        """Create automatic field mapping based on column names and config fields"""
        field_mapping = {}
        
        # Extract fields used in the template config
        template_fields = self._extract_fields_from_config(template_config)
        
        # Create mapping based on name similarity
        for template_field in template_fields:
            best_match = self._find_best_column_match(template_field, new_columns)
            if best_match:
                field_mapping[template_field] = best_match
        
        return field_mapping
    
    def _extract_fields_from_config(self, config: Dict[str, Any]) -> List[str]:
        """Extract all field names used in a Tableau chart config"""
        fields = []
        
        # Extract from shelves (rows, columns, marks, filters, etc.)
        shelf_keys = ["rows", "columns", "color", "size", "label", "detail", "tooltip", "filter"]
        
        for shelf_key in shelf_keys:
            if shelf_key in config and isinstance(config[shelf_key], list):
                for item in config[shelf_key]:
                    if isinstance(item, dict) and "field" in item:
                        fields.append(item["field"])
                    elif isinstance(item, str):
                        fields.append(item)
        
        # Extract from calculated fields
        if "calculated_fields" in config and isinstance(config["calculated_fields"], list):
            for calc_field in config["calculated_fields"]:
                if isinstance(calc_field, dict) and "name" in calc_field:
                    fields.append(calc_field["name"])
        
        # Extract from parameters
        if "parameters" in config and isinstance(config["parameters"], list):
            for param in config["parameters"]:
                if isinstance(param, dict) and "name" in param:
                    fields.append(param["name"])
        
        return list(set(fields))
    
    def _find_best_column_match(self, template_field: str, new_columns: List[str]) -> Optional[str]:
        """Find the best matching column name for a template field"""
        template_field_lower = template_field.lower()
        
        # Exact match
        for col in new_columns:
            if col.lower() == template_field_lower:
                return col
        
        # Partial match (contains)
        for col in new_columns:
            if template_field_lower in col.lower() or col.lower() in template_field_lower:
                return col
        
        # Fuzzy match based on common patterns
        common_patterns = {
            'date': ['date', 'time', 'timestamp', 'created', 'updated'],
            'sales': ['sales', 'revenue', 'amount', 'value'],
            'region': ['region', 'area', 'location', 'country', 'state'],
            'product': ['product', 'item', 'category', 'type'],
            'count': ['count', 'number', 'quantity', 'total'],
            'profit': ['profit', 'margin', 'income', 'earnings']
        }
        
        for pattern, keywords in common_patterns.items():
            if pattern in template_field_lower:
                for col in new_columns:
                    for keyword in keywords:
                        if keyword in col.lower():
                            return col
        
        return None
    
    def _adapt_chart_config(
        self, 
        template_config: Dict[str, Any], 
        new_columns: List[str], 
        field_mapping: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Adapt a template chart config to work with new data"""
        import copy
        
        # Deep copy the template config
        new_config = copy.deepcopy(template_config)
        
        # Update field references in shelves
        shelf_keys = ["rows", "columns", "color", "size", "label", "detail", "tooltip", "filter"]
        
        for shelf_key in shelf_keys:
            if shelf_key in new_config and isinstance(new_config[shelf_key], list):
                for i, item in enumerate(new_config[shelf_key]):
                    if isinstance(item, dict) and "field" in item:
                        if item["field"] in field_mapping:
                            new_config[shelf_key][i]["field"] = field_mapping[item["field"]]
                    elif isinstance(item, str) and item in field_mapping:
                        new_config[shelf_key][i] = field_mapping[item]
        
        # Update calculated fields
        if "calculated_fields" in new_config and isinstance(new_config["calculated_fields"], list):
            for calc_field in new_config["calculated_fields"]:
                if isinstance(calc_field, dict) and "formula" in calc_field:
                    # Update field references in formulas
                    formula = calc_field["formula"]
                    for old_field, new_field in field_mapping.items():
                        formula = formula.replace(f"[{old_field}]", f"[{new_field}]")
                        formula = formula.replace(old_field, new_field)
                    calc_field["formula"] = formula
        
        # Update titles to be language-appropriate
        self._update_titles_for_language(new_config, language)
        
        return new_config
    
    def _update_titles_for_language(self, config: Dict[str, Any], language: str):
        """Update chart titles and labels for the specified language"""
        # Update main title
        if "title" in config:
            title = config["title"]
            if isinstance(title, str) and "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>" in title:
                config["title"] = f"Chart ({language})"
        
        # Update axis titles
        if "axes" in config:
            for axis_key in ["x_axis", "y_axis", "z_axis"]:
                if axis_key in config["axes"] and "title" in config["axes"][axis_key]:
                    title = config["axes"][axis_key]["title"]
                    if isinstance(title, str) and "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>" in title:
                        config["axes"][axis_key]["title"] = f"{axis_key.replace('_axis', '').title()} ({language})"
    
    def _validate_chart_config(self, config: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
        """Validate that a chart config is compatible with the provided columns"""
        try:
            # Extract all field references from the config
            config_fields = self._extract_fields_from_config(config)
            
            # Check if all referenced fields exist in the data columns
            missing_fields = []
            for field in config_fields:
                if field not in columns:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "valid": False,
                    "error": f"Config references fields not present in data: {missing_fields}"
                }
            
            # Basic config structure validation
            if "chart_type" not in config:
                return {
                    "valid": False,
                    "error": "Config missing required 'chart_type' property"
                }
            
            # Check for required shelves based on chart type
            chart_type = config.get("chart_type", "")
            required_shelves = self._get_required_shelves_for_chart_type(chart_type)
            
            for shelf in required_shelves:
                if shelf not in config or not config[shelf]:
                    return {
                        "valid": False,
                        "error": f"Chart type '{chart_type}' requires '{shelf}' shelf to be populated"
                    }
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Config validation error: {str(e)}"
            }
    
    def _get_required_shelves_for_chart_type(self, chart_type: str) -> List[str]:
        """Get required shelves for a specific chart type"""
        requirements = {
            "bar": ["rows", "columns"],
            "line": ["rows", "columns"],
            "area": ["rows", "columns"],
            "scatter": ["rows", "columns"],
            "pie": ["rows", "columns"],
            "treemap": ["rows", "columns"],
            "heatmap": ["rows", "columns"],
            "histogram": ["rows"],
            "box_plot": ["rows", "columns"],
            "bullet": ["rows", "columns"],
            "gantt": ["rows", "columns"],
            "map": ["rows", "columns"],
            "symbol_map": ["rows", "columns"],
            "filled_map": ["rows", "columns"],
            "dual_axis": ["rows", "columns"],
            "combined": ["rows", "columns"]
        }
        
        return requirements.get(chart_type, ["rows", "columns"])
    
    def _extract_chart_type_from_config(self, config: Dict[str, Any]) -> str:
        """Extract chart type from Tableau config"""
        return config.get("chart_type", "")


# Advanced Tableau chart generation with additional features
class AdvancedTableauChartGeneration(TableauChartGenerationPipeline):
    """Advanced Tableau chart generation with additional features"""
    
    def __init__(self, llm, **kwargs):
        super().__init__(llm, **kwargs)
        self.chart_templates = self._load_chart_templates()
    
    def _load_chart_templates(self) -> Dict[str, Any]:
        """Load predefined chart templates"""
        return {
            "sales_trend": {
                "type": "line",
                "description": "Shows sales trends over time",
                "required_fields": ["date", "sales"],
                "template": {
                    "chart_type": "line",
                    "rows": [{"field": "date", "type": "date"}],
                    "columns": [{"field": "sales", "type": "measure", "aggregation": "sum"}],
                    "color": [],
                    "size": [],
                    "label": [],
                    "detail": [],
                    "tooltip": [{"field": "sales", "type": "measure"}],
                    "filter": []
                }
            },
            "category_comparison": {
                "type": "bar",
                "description": "Compares values across categories",
                "required_fields": ["category", "value"],
                "template": {
                    "chart_type": "bar",
                    "rows": [{"field": "category", "type": "dimension"}],
                    "columns": [{"field": "value", "type": "measure", "aggregation": "sum"}],
                    "color": [{"field": "category", "type": "dimension"}],
                    "size": [],
                    "label": [{"field": "value", "type": "measure"}],
                    "detail": [],
                    "tooltip": [{"field": "value", "type": "measure"}],
                    "filter": []
                }
            },
            "distribution": {
                "type": "pie",
                "description": "Shows distribution of parts within a whole",
                "required_fields": ["category", "value"],
                "template": {
                    "chart_type": "pie",
                    "rows": [{"field": "category", "type": "dimension"}],
                    "columns": [{"field": "value", "type": "measure", "aggregation": "sum"}],
                    "color": [{"field": "category", "type": "dimension"}],
                    "size": [],
                    "label": [{"field": "category", "type": "dimension"}],
                    "detail": [],
                    "tooltip": [{"field": "value", "type": "measure"}],
                    "filter": []
                }
            },
            "correlation": {
                "type": "scatter",
                "description": "Shows correlation between two variables",
                "required_fields": ["x_variable", "y_variable"],
                "template": {
                    "chart_type": "scatter",
                    "rows": [{"field": "x_variable", "type": "measure"}],
                    "columns": [{"field": "y_variable", "type": "measure"}],
                    "color": [],
                    "size": [],
                    "label": [],
                    "detail": [],
                    "tooltip": [{"field": "x_variable", "type": "measure"}, {"field": "y_variable", "type": "measure"}],
                    "filter": []
                }
            },
            "geographical": {
                "type": "map",
                "description": "Shows data on geographical map",
                "required_fields": ["location", "value"],
                "template": {
                    "chart_type": "map",
                    "rows": [{"field": "location", "type": "geographical"}],
                    "columns": [{"field": "value", "type": "measure", "aggregation": "sum"}],
                    "color": [{"field": "value", "type": "measure"}],
                    "size": [{"field": "value", "type": "measure"}],
                    "label": [{"field": "location", "type": "dimension"}],
                    "detail": [],
                    "tooltip": [{"field": "location", "type": "dimension"}, {"field": "value", "type": "measure"}],
                    "filter": []
                }
            }
        }
    
    async def suggest_chart_type(self, data: Dict[str, Any], query: str) -> List[str]:
        """Suggest appropriate chart types based on data and query"""
        suggestions = []
        
        # Analyze data structure
        columns = data.get("columns", [])
        data_sample = data.get("data", [])[:5]  # Sample first 5 rows
        
        # Simple heuristics for chart type suggestion
        temporal_fields = []
        categorical_fields = []
        numeric_fields = []
        geographical_fields = []
        
        for col in columns:
            col_name = col if isinstance(col, str) else col.get("name", "")
            
            # Check sample data for type inference
            if data_sample:
                col_index = columns.index(col) if col in columns else -1
                if col_index >= 0:
                    sample_values = [row[col_index] for row in data_sample if len(row) > col_index]
                    
                    if any(isinstance(val, (int, float)) for val in sample_values):
                        numeric_fields.append(col_name)
                    elif any(str(val).lower() in ['date', 'time', 'month', 'year'] for val in sample_values):
                        temporal_fields.append(col_name)
                    elif any(str(val).lower() in ['country', 'state', 'region', 'city', 'location'] for val in sample_values):
                        geographical_fields.append(col_name)
                    else:
                        categorical_fields.append(col_name)
        
        # Suggest based on field types and combinations
        if temporal_fields and numeric_fields:
            suggestions.extend(["line", "area"])
        
        if categorical_fields and numeric_fields:
            suggestions.extend(["bar", "pie"])
            
            # Multiple categories suggest treemap
            if len(categorical_fields) >= 2:
                suggestions.append("treemap")
        
        if len(numeric_fields) >= 2:
            suggestions.extend(["scatter", "heatmap"])
        
        if geographical_fields and numeric_fields:
            suggestions.extend(["map", "symbol_map", "filled_map"])
        
        if len(numeric_fields) >= 1 and not categorical_fields:
            suggestions.extend(["histogram", "box_plot"])
        
        # Query-based suggestions
        query_lower = query.lower()
        if any(word in query_lower for word in ["trend", "over time", "time series"]):
            suggestions.append("line")
        elif any(word in query_lower for word in ["compare", "comparison", "vs"]):
            suggestions.extend(["bar", "scatter"])
        elif any(word in query_lower for word in ["distribution", "share", "percentage"]):
            suggestions.extend(["pie", "histogram"])
        elif any(word in query_lower for word in ["correlation", "relationship"]):
            suggestions.append("scatter")
        elif any(word in query_lower for word in ["map", "geographical", "location", "country"]):
            suggestions.extend(["map", "symbol_map", "filled_map"])
        elif any(word in query_lower for word in ["hierarchy", "tree", "nested"]):
            suggestions.append("treemap")
        
        return list(set(suggestions))  # Remove duplicates
    
    async def run_with_suggestions(
        self,
        query: str,
        sql: str,
        data: Dict[str, Any],
        language: str = "English",
        **kwargs
    ) -> Dict[str, Any]:
        """Run chart generation with chart type suggestions"""
        
        # Get suggestions first
        suggestions = await self.suggest_chart_type(data, query)
        
        # Run normal pipeline
        result = await self.run(query, sql, data, language, **kwargs)
        
        # Add suggestions to result
        result["chart_suggestions"] = suggestions
        result["available_templates"] = list(self.chart_templates.keys())
        
        return result
    
    async def apply_template(
        self,
        template_name: str,
        data: Dict[str, Any],
        field_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Apply a predefined template with field mapping"""
        if template_name not in self.chart_templates:
            return {"error": f"Template '{template_name}' not found"}
        
        template = self.chart_templates[template_name]["template"].copy()
        
        # Apply field mapping to template
        shelf_keys = ["rows", "columns", "color", "size", "label", "detail", "tooltip", "filter"]
        
        for shelf_key in shelf_keys:
            if shelf_key in template and isinstance(template[shelf_key], list):
                for item in template[shelf_key]:
                    if isinstance(item, dict) and "field" in item:
                        if item["field"] in field_mapping:
                            item["field"] = field_mapping[item["field"]]
        
        return {
            "chart_config": template,
            "chart_type": template["chart_type"],
            "reasoning": f"Applied template '{template_name}' with field mapping",
            "success": True
        }


# Factory function to create the pipeline
def create_tableau_chart_generation_pipeline(llm, **kwargs) -> TableauChartGenerationPipeline:
    """Factory function to create Tableau chart generation pipeline"""
    return TableauChartGenerationPipeline(llm, **kwargs)


# Utility functions for integration
async def generate_tableau_chart(
    llm,
    query: str,
    sql: str,
    data: Dict[str, Any],
    language: str = "English",
    export_format: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to generate Tableau chart"""
    pipeline = create_tableau_chart_generation_pipeline(llm)
    return await pipeline.run(
        query=query,
        sql=sql,
        data=data,
        language=language,
        export_format=export_format
    )


async def generate_tableau_chart_from_template(
    llm,
    existing_chart: Dict[str, Any],
    new_data: Dict[str, Any],
    field_mapping: Optional[Dict[str, str]] = None,
    language: str = "English"
) -> Dict[str, Any]:
    """Convenience function to generate Tableau chart from template"""
    pipeline = create_tableau_chart_generation_pipeline(llm)
    return await pipeline.generate_chart_from_template(
        existing_chart=existing_chart,
        new_data=new_data,
        field_mapping=field_mapping,
        language=language
    )


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    from langchain.llms import OpenAI
    
    # Example usage
    async def test_tableau_chart_generation():
        # Initialize LLM (replace with your preferred LLM)
        from app.core.dependencies import get_llm
        llm = get_llm()
        
        # Sample data
        sample_data = {
            "columns": ["Region", "Sales", "Date", "Category"],
            "data": [
                ["North", 100000, "2023-01-01", "Electronics"],
                ["South", 150000, "2023-01-01", "Clothing"],
                ["East", 120000, "2023-01-01", "Electronics"],
                ["West", 180000, "2023-01-01", "Furniture"],
                ["North", 110000, "2023-02-01", "Electronics"],
                ["South", 160000, "2023-02-01", "Clothing"]
            ]
        }
        
        # Test chart generation
        result = await generate_tableau_chart(
            llm=llm,
            query="Show me sales trends by region over time",
            sql="SELECT Region, Date, SUM(Sales) as Sales FROM sales_data GROUP BY Region, Date ORDER BY Date",
            data=sample_data,
            language="English",
            export_format="all"
        )
        
        print("Chart Generation Result:")
        print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
        
        # Test individual components
        pipeline = create_tableau_chart_generation_pipeline(llm)
        
        # Test data preprocessing
        preprocessor = TableauChartDataPreprocessor()
        preprocessed = preprocessor.run(sample_data)
        print("\nPreprocessed Data:")
        print(orjson.dumps(preprocessed, option=orjson.OPT_INDENT_2).decode())
        
        # Test export functionality
        exporter = TableauChartExporter()
        if result.get("success", False):
            chart_config = result.get("chart_config", {})
            
            print("\nExported JSON:")
            print(exporter.to_tableau_json(chart_config))
            
            print("\nTableau Workbook XML:")
            print(exporter.to_tableau_workbook(chart_config))
            
            print("\nTableau Data Source:")
            print(exporter.to_tableau_datasource(chart_config))
            
            print("\nVQL Query:")
            print(exporter.to_tableau_vql(chart_config))
        
        # Test template generation
        print("\n=== Testing Template Generation ===")
        
        # Create a template chart
        template_data = {
            "columns": ["Date", "Sales", "Region"],
            "data": [
                ["2023-01-01", 100000, "North"],
                ["2023-02-01", 120000, "North"],
                ["2023-03-01", 110000, "North"]
            ]
        }
        
        template_chart = await generate_tableau_chart(
            llm=llm,
            query="Show sales trends by region over time",
            sql="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
            data=template_data,
            language="English"
        )
        
        print(f"Template chart success: {template_chart.get('success', False)}")
        print(f"Template chart type: {template_chart.get('chart_type', 'unknown')}")
        
        # New data with different column names
        new_data = {
            "columns": ["Timestamp", "Revenue", "Area"],
            "data": [
                ["2024-01-01", 150000, "East"],
                ["2024-02-01", 170000, "East"],
                ["2024-03-01", 160000, "East"]
            ]
        }
        
        # Generate new chart from template
        new_chart = await generate_tableau_chart_from_template(
            llm=llm,
            existing_chart=template_chart,
            new_data=new_data,
            language="English"
        )
        
        print(f"New chart success: {new_chart.get('success', False)}")
        print(f"Field mapping: {new_chart.get('field_mapping', {})}")
        print(f"Template info: {new_chart.get('template_info', {})}")
        
        # Test advanced features
        print("\n=== Testing Advanced Features ===")
        advanced_pipeline = AdvancedTableauChartGeneration(llm)
        
        # Test suggestions
        suggestions = await advanced_pipeline.suggest_chart_type(sample_data, "Show sales trends")
        print(f"Chart suggestions: {suggestions}")
        
        # Test template application
        template_result = await advanced_pipeline.apply_template(
            template_name="sales_trend",
            data=new_data,
            field_mapping={"date": "Timestamp", "sales": "Revenue"}
        )
        print(f"Template application success: {template_result.get('success', False)}")
    
    # Run the test
    asyncio.run(test_tableau_chart_generation())