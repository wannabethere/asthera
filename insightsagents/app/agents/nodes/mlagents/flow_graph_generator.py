"""
Flow Graph Generator Agent

This agent takes the output from the SelfCorrectingPipelineCodeGenerator and creates
a comprehensive flow graph with nodes, edges, and execution order information.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class NodeType(Enum):
    """Types of nodes in the flow graph"""
    DATA_INPUT = "data_input"
    PROCESSING = "processing"
    DATA_OUTPUT = "data_output"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    PARALLEL = "parallel"
    DATA_SELECTION = "data_selection"
    SUMMARIZATION = "summarization"
    VISUALIZATION = "visualization"

class EdgeType(Enum):
    """Types of edges in the flow graph"""
    DATA_FLOW = "data_flow"
    CONTROL_FLOW = "control_flow"
    DEPENDENCY = "dependency"
    CONDITIONAL = "conditional"

@dataclass
class FlowNode:
    """Represents a node in the flow graph"""
    id: str
    title: str
    node_type: NodeType
    function: str
    pipeline_type: str
    input_dataframe: str
    output_dataframe: str
    dependencies: List[str]
    input_columns: List[str]
    output_columns: List[str]
    code: str
    metadata: Dict[str, Any]

@dataclass
class FlowEdge:
    """Represents an edge in the flow graph"""
    from_node: str
    to_node: str
    edge_type: EdgeType
    data_flow: Optional[str] = None
    condition: Optional[str] = None
    metadata: Dict[str, Any] = None

class FlowGraphGenerator:
    """
    Generates flow graphs from pipeline generator output
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_flow_graph(self, pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive flow graph from pipeline generator output
        
        Args:
            pipeline_result: Output from SelfCorrectingPipelineCodeGenerator containing
                           step_codes, flow_graph, and other metadata
        
        Returns:
            Enhanced flow graph with additional analysis and visualization data
        """
        try:
            self.logger.info("Starting flow graph generation")
            
            # Debug: Log pipeline result structure
            self.logger.info(f"Pipeline result keys: {list(pipeline_result.keys())}")
            self.logger.info(f"Pipeline result type: {type(pipeline_result)}")
            
            # Debug: Check if pipeline_result is None or invalid
            if pipeline_result is None:
                self.logger.error("Pipeline result is None!")
                raise ValueError("Pipeline result is None")
            
            if not isinstance(pipeline_result, dict):
                self.logger.error(f"Pipeline result is not a dict: {type(pipeline_result)}")
                raise ValueError(f"Pipeline result is not a dict: {type(pipeline_result)}")
            
            # Extract data from pipeline result
            step_codes = pipeline_result.get("step_codes", [])
            basic_flow_graph = pipeline_result.get("flow_graph", {})
            generated_code = pipeline_result.get("generated_code", "")
            
            # Debug: Log extracted data
            self.logger.info(f"Step codes type: {type(step_codes)}, length: {len(step_codes) if isinstance(step_codes, list) else 'N/A'}")
            self.logger.info(f"Basic flow graph type: {type(basic_flow_graph)}")
            self.logger.info(f"Generated code type: {type(generated_code)}")
            
            # Debug: Log first step code structure if available
            if step_codes and isinstance(step_codes, list) and len(step_codes) > 0:
                first_step = step_codes[0]
                self.logger.info(f"First step type: {type(first_step)}")
                self.logger.info(f"First step keys: {list(first_step.keys()) if isinstance(first_step, dict) else 'N/A'}")
                if isinstance(first_step, dict):
                    for key, value in first_step.items():
                        self.logger.info(f"First step {key}: {type(value)} - {repr(value)[:100]}")
            else:
                self.logger.warning("No step codes found or step_codes is not a list")
            
            # Create enhanced flow graph
            enhanced_flow_graph = self._create_enhanced_flow_graph(
                step_codes, basic_flow_graph, generated_code
            )
            
            # Add execution analysis
            try:
                self.logger.info("Analyzing execution order")
                execution_analysis = self._analyze_execution_order(enhanced_flow_graph)
                self.logger.info("Execution analysis completed")
            except Exception as e:
                self.logger.error(f"Error in execution analysis: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                execution_analysis = {}
            
            # Add dependency analysis
            try:
                self.logger.info("Analyzing dependencies")
                dependency_analysis = self._analyze_dependencies(enhanced_flow_graph)
                self.logger.info("Dependency analysis completed")
            except Exception as e:
                self.logger.error(f"Error in dependency analysis: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                dependency_analysis = {}
            
            # Add data flow analysis
            try:
                self.logger.info("Analyzing data flow")
                data_flow_analysis = self._analyze_data_flow(enhanced_flow_graph)
                self.logger.info("Data flow analysis completed")
            except Exception as e:
                self.logger.error(f"Error in data flow analysis: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                data_flow_analysis = {}
            
            # Create visualization data
            try:
                self.logger.info("Creating visualization data")
                visualization_data = self._create_visualization_data(enhanced_flow_graph)
                self.logger.info("Visualization data creation completed")
            except Exception as e:
                self.logger.error(f"Error creating visualization data: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                visualization_data = {}
            
            # Generate Mermaid chart
            try:
                self.logger.info("Generating Mermaid chart")
                mermaid_chart = self._generate_mermaid_chart(enhanced_flow_graph)
                self.logger.info("Mermaid chart generation completed")
            except Exception as e:
                self.logger.error(f"Error generating Mermaid chart: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                mermaid_chart = "graph TD\n    A[Error generating chart]"
            
            # Generate step details with reasoning and examples
            try:
                self.logger.info("Generating step details")
                step_details = self._generate_step_details(enhanced_flow_graph)
                self.logger.info("Step details generation completed")
            except Exception as e:
                self.logger.error(f"Error generating step details: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                step_details = {}
            
            try:
                self.logger.info("Creating final result")
                result = {
                    "flow_graph": enhanced_flow_graph,
                    "execution_analysis": execution_analysis,
                    "dependency_analysis": dependency_analysis,
                    "data_flow_analysis": data_flow_analysis,
                    "visualization_data": visualization_data,
                    "mermaid_chart": mermaid_chart,
                    "step_details": step_details,
                    "metadata": self._calculate_metadata(enhanced_flow_graph)
                }
                
                self.logger.info(f"Flow graph generation completed: {result['metadata']['total_nodes']} nodes, {result['metadata']['total_edges']} edges")
                return result
                
            except Exception as e:
                self.logger.error(f"Error creating final result: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                # Return a minimal result to prevent complete failure
                return {
                    "flow_graph": enhanced_flow_graph,
                    "execution_analysis": {},
                    "dependency_analysis": {},
                    "data_flow_analysis": {},
                    "visualization_data": {},
                    "mermaid_chart": "graph TD\n    A[Error in flow graph generation]",
                    "step_details": {},
                    "metadata": {
                        "total_nodes": len(enhanced_flow_graph.get("nodes", [])),
                        "total_edges": len(enhanced_flow_graph.get("edges", [])),
                        "pipeline_types": [],
                        "functions_used": [],
                        "has_parallel_execution": False,
                        "can_parallelize": False,
                        "has_conditional_logic": False
                    },
                    "error": str(e)
                }
            
        except Exception as e:
            self.logger.error(f"Error generating flow graph: {e}")
            return {
                "flow_graph": {"nodes": [], "edges": [], "metadata": {}},
                "execution_analysis": {},
                "dependency_analysis": {},
                "data_flow_analysis": {},
                "visualization_data": {},
                "metadata": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "pipeline_types": [],
                    "functions_used": [],
                    "has_parallel_execution": False,
                    "can_parallelize": False,
                    "has_conditional_logic": False
                },
                "error": str(e)
            }
    
    def _create_enhanced_flow_graph(self, step_codes: List[Dict[str, Any]], 
                                  basic_flow_graph: Dict[str, Any], 
                                  generated_code: str) -> Dict[str, Any]:
        """Create an enhanced flow graph with additional metadata"""
        
        enhanced_nodes = []
        enhanced_edges = []
        
        # Debug: Log step_codes structure
        self.logger.info(f"Processing {len(step_codes)} step codes")
        self.logger.info(f"Step codes type: {type(step_codes)}")
        
        if step_codes:
            self.logger.info(f"First step type: {type(step_codes[0])}")
            self.logger.info(f"First step keys: {list(step_codes[0].keys()) if isinstance(step_codes[0], dict) else 'N/A'}")
            self.logger.info(f"First step: {step_codes[0]}")
            
            # Debug: Check each step code structure
            for i, step in enumerate(step_codes):
                self.logger.info(f"Step {i} type: {type(step)}")
                if isinstance(step, dict):
                    for key, value in step.items():
                        self.logger.info(f"Step {i} {key}: {type(value)} - {repr(value)[:100]}")
                else:
                    self.logger.error(f"Step {i} is not a dict: {step}")
        else:
            self.logger.warning("No step codes provided to flow graph generator")
            return {
                "nodes": [],
                "edges": [],
                "metadata": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "pipeline_types": [],
                    "functions_used": [],
                    "has_parallel_execution": False,
                    "can_parallelize": False,
                    "has_conditional_logic": False
                }
            }
        
        # Process each step code
        for i, step in enumerate(step_codes):
            try:
                self.logger.info(f"Processing step {i+1}: {step.get('title', 'Unknown')}")
                self.logger.info(f"Step type: {type(step)}")
                self.logger.info(f"Step keys: {list(step.keys()) if isinstance(step, dict) else 'N/A'}")
                
                # Debug: Log step data before validation
                if isinstance(step, dict):
                    for key, value in step.items():
                        self.logger.info(f"Before validation - Step {i+1} {key}: {type(value)} - {repr(value)[:100]}")
                
                # Validate and fix step data structure
                self.logger.info(f"Calling _validate_and_fix_step_data for step {i+1}")
                step = self._validate_and_fix_step_data(step)
                self.logger.info(f"After validation - Step {i+1} validated successfully")
                
                node_id = f"step_{step['step_number']}"
                
                # Determine node type based on function and context
                node_type = self._determine_node_type(step)
                self.logger.info(f"Determined node type: {node_type}")
                
            except Exception as e:
                self.logger.error(f"Error processing step {i+1} (step_number: {step.get('step_number', 'unknown')}): {e}")
                self.logger.error(f"Step data: {step}")
                self.logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            
            try:
                # Generate natural language question for data selection
                nl_question = self._generate_nl_question(step, i)
                self.logger.info(f"Generated NL question: {nl_question[:50]}...")
                
                # Create enhanced node
                enhanced_node = {
                    "id": node_id,
                    "title": step["title"],
                    "node_type": node_type.value,
                    "function": step["function"],
                    "pipeline_type": step["pipeline_type"],
                    "input_dataframe": step["input_dataframe"],
                    "output_dataframe": step["output_dataframe"],
                    "dependencies": step["dependencies"],
                    "input_columns": step.get("input_columns", []),
                    "output_columns": step.get("output_columns", []),
                    "code": step["code"],
                    "step_number": step["step_number"],
                    "nl_question": nl_question,
                    "metadata": {
                        "execution_order": i + 1,
                        "is_parallel": False,
                        "is_conditional": False,
                        "complexity_score": self._calculate_complexity_score(step),
                        "estimated_execution_time": self._estimate_execution_time(step),
                        "memory_usage": self._estimate_memory_usage(step)
                    }
                }
                
                enhanced_nodes.append(enhanced_node)
                self.logger.info(f"Successfully created enhanced node for step {i+1}")
                
            except Exception as e:
                self.logger.error(f"Error creating enhanced node for step {i+1}: {e}")
                self.logger.error(f"Step data: {step}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        
        # Create enhanced edges
        for i, step in enumerate(step_codes):
            try:
                self.logger.info(f"Creating edges for step {i+1}")
                node_id = f"step_{step['step_number']}"
                
                # Add dependency edges
                for dep_step in step["dependencies"]:
                    dep_node_id = f"step_{dep_step}"
                    edge = {
                        "from_node": dep_node_id,
                        "to_node": node_id,
                        "edge_type": EdgeType.DEPENDENCY.value,
                        "data_flow": f"{dep_node_id}_result -> {node_id}_input",
                        "metadata": {
                            "dependency_type": "data_dependency",
                            "is_critical": True
                        }
                    }
                    enhanced_edges.append(edge)
                
                # Add sequential flow edge (if not the first step)
                if i > 0:
                    prev_node_id = f"step_{step_codes[i-1]['step_number']}"
                    edge = {
                        "from_node": prev_node_id,
                        "to_node": node_id,
                        "edge_type": EdgeType.DATA_FLOW.value,
                        "data_flow": f"{prev_node_id}_result -> {node_id}_input",
                        "metadata": {
                            "flow_type": "sequential",
                            "is_critical": True
                        }
                    }
                    enhanced_edges.append(edge)
                    
                self.logger.info(f"Successfully created edges for step {i+1}")
                
            except Exception as e:
                self.logger.error(f"Error creating edges for step {i+1}: {e}")
                self.logger.error(f"Step data: {step}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        
        # Add summarization and visualization steps at the end
        try:
            self.logger.info("Adding pipeline end steps (summarization and visualization)")
            final_nodes, final_edges = self._add_pipeline_end_steps(enhanced_nodes, enhanced_edges, step_codes)
            self.logger.info(f"Successfully added pipeline end steps. Final nodes: {len(final_nodes)}, Final edges: {len(final_edges)}")
        except Exception as e:
            self.logger.error(f"Error adding pipeline end steps: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback to original nodes and edges if end steps fail
            final_nodes = enhanced_nodes
            final_edges = enhanced_edges
        
        return {
            "nodes": final_nodes,
            "edges": final_edges,
            "metadata": {
                "total_steps": len(step_codes),
                "pipeline_types": list(set([node["pipeline_type"] for node in final_nodes])),
                "functions_used": list(set([node["function"] for node in final_nodes])),
                "generated_code": generated_code
            }
        }
    
    def _validate_and_fix_step_data(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix step data structure to ensure all required fields are present"""
        
        # Debug: Log the step data structure
        self.logger.info(f"Validating step data: {step}")
        
        # Ensure required fields exist with defaults
        fixed_step = step.copy()
        
        # Required string fields
        required_string_fields = {
            'title': 'Unknown Step',
            'function': 'unknown_function',
            'pipeline_type': 'UnknownPipe',
            'input_dataframe': 'unknown_input',
            'output_dataframe': 'unknown_output',
            'code': '# No code available'
        }
        
        # Debug: Check code field specifically
        if 'code' in fixed_step:
            code_value = fixed_step['code']
            self.logger.info(f"Code field type: {type(code_value)}, value: {repr(code_value)}")
            if not isinstance(code_value, str):
                self.logger.error(f"Code field is not a string: {type(code_value)} - {code_value}")
                fixed_step['code'] = '# No code available'
        
        for field, default_value in required_string_fields.items():
            if field not in fixed_step or not fixed_step[field]:
                fixed_step[field] = default_value
                self.logger.warning(f"Missing or empty {field}, using default: {default_value}")
        
        # Required list fields
        required_list_fields = {
            'dependencies': [],
            'input_columns': [],
            'output_columns': []
        }
        
        for field, default_value in required_list_fields.items():
            if field not in fixed_step or not isinstance(fixed_step[field], list):
                fixed_step[field] = default_value
                self.logger.warning(f"Missing or invalid {field}, using default: {default_value}")
        
        # Required integer fields
        if 'step_number' not in fixed_step or not isinstance(fixed_step['step_number'], int):
            fixed_step['step_number'] = 1
            self.logger.warning("Missing or invalid step_number, using default: 1")
        
        # Fix pipeline_type if it's unknown
        if fixed_step['pipeline_type'] in ['unknown_category', 'UnknownPipe']:
            # Try to determine pipeline type from function
            function = fixed_step['function'].lower()
            if any(keyword in function for keyword in ['moving', 'rolling', 'time', 'lag', 'lead']):
                fixed_step['pipeline_type'] = 'TimeSeriesPipe'
            elif any(keyword in function for keyword in ['variance', 'mean', 'sum', 'count', 'std']):
                fixed_step['pipeline_type'] = 'MetricsPipe'
            elif any(keyword in function for keyword in ['cohort', 'segment', 'group']):
                fixed_step['pipeline_type'] = 'CohortPipe'
            else:
                fixed_step['pipeline_type'] = 'ProcessingPipe'
            
            self.logger.info(f"Fixed pipeline_type: {step.get('pipeline_type', 'unknown')} -> {fixed_step['pipeline_type']}")
        
        # Try to extract input/output columns from code if missing
        if not fixed_step['input_columns'] or not fixed_step['output_columns']:
            self.logger.info(f"Extracting columns from code for step with function: {fixed_step.get('function', 'unknown')}")
            self.logger.info(f"Code field before extraction: {type(fixed_step.get('code', ''))} - {repr(fixed_step.get('code', '')[:100])}")
            self._extract_columns_from_code(fixed_step)
            self.logger.info(f"Columns extracted successfully")
        
        return fixed_step
    
    def _extract_columns_from_code(self, step: Dict[str, Any]) -> None:
        """Try to extract input/output columns from step code"""
        code = step.get('code', '')
        function = step.get('function', '')
        
        # Debug: Check if code is a string
        if not isinstance(code, str):
            self.logger.error(f"Code field is not a string: {type(code)} - {code}")
            return
        
        # Simple column extraction patterns
        import re
        
        # Look for column references in quotes
        column_patterns = [
            r"'([^']+)'",  # Single quotes
            r'"([^"]+)"',  # Double quotes
            r'column[=:]\s*["\']([^"\']+)["\']',  # column='name'
            r'variable[=:]\s*["\']([^"\']+)["\']',  # variable='name'
            r'group_column[=:]\s*["\']([^"\']+)["\']',  # group_column='name'
            r'time_column[=:]\s*["\']([^"\']+)["\']',  # time_column='name'
        ]
        
        found_columns = set()
        for i, pattern in enumerate(column_patterns):
            try:
                self.logger.info(f"Compiling regex pattern {i}: {pattern}")
                self.logger.info(f"Pattern type: {type(pattern)}")
                matches = re.findall(pattern, code)
                self.logger.info(f"Found {len(matches)} matches: {matches}")
                found_columns.update(matches)
            except Exception as e:
                self.logger.error(f"Error compiling regex pattern {i} '{pattern}': {e}")
                self.logger.error(f"Pattern type: {type(pattern)}, Code type: {type(code)}")
                raise
        
        # Filter out common non-column values
        filtered_columns = []
        for col in found_columns:
            if not any(skip in col.lower() for skip in ['df', 'dataframe', 'pipe', 'result', 'step_', 'to_df', 'from_dataframe']):
                filtered_columns.append(col)
        
        if filtered_columns and not step['input_columns']:
            step['input_columns'] = filtered_columns[:5]  # Limit to first 5 columns
            self.logger.info(f"Extracted input columns from code: {step['input_columns']}")
        
        if filtered_columns and not step['output_columns']:
            # Generate output column names based on function
            output_columns = []
            for col in filtered_columns[:3]:  # Limit to first 3 columns
                if function.lower() in ['variance_analysis', 'variance']:
                    output_columns.append(f'variance_{col}')
                elif function.lower() in ['mean', 'average']:
                    output_columns.append(f'mean_{col}')
                elif function.lower() in ['sum']:
                    output_columns.append(f'sum_{col}')
                else:
                    output_columns.append(f'{function}_{col}')
            
            step['output_columns'] = output_columns
            self.logger.info(f"Generated output columns: {step['output_columns']}")

    def _calculate_metadata(self, enhanced_flow_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metadata for the enhanced flow graph with error handling"""
        try:
            nodes = enhanced_flow_graph.get("nodes", [])
            edges = enhanced_flow_graph.get("edges", [])
            
            # Safely extract pipeline types and functions
            pipeline_types = []
            functions_used = []
            
            for node in nodes:
                if isinstance(node, dict):
                    if "pipeline_type" in node and node["pipeline_type"]:
                        pipeline_types.append(node["pipeline_type"])
                    if "function" in node and node["function"]:
                        functions_used.append(node["function"])
            
            # Calculate parallel execution and conditional logic flags
            has_parallel = False
            has_conditional = False
            
            try:
                has_parallel = self._has_parallel_execution(enhanced_flow_graph)
            except Exception as e:
                self.logger.warning(f"Error calculating parallel execution: {e}")
            
            try:
                has_conditional = self._has_conditional_logic(enhanced_flow_graph)
            except Exception as e:
                self.logger.warning(f"Error calculating conditional logic: {e}")
            
            return {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "pipeline_types": list(set(pipeline_types)),
                "functions_used": list(set(functions_used)),
                "has_parallel_execution": has_parallel,
                "can_parallelize": has_parallel,
                "has_conditional_logic": has_conditional
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating metadata: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "total_nodes": 0,
                "total_edges": 0,
                "pipeline_types": [],
                "functions_used": [],
                "has_parallel_execution": False,
                "can_parallelize": False,
                "has_conditional_logic": False
            }

    def _generate_nl_question(self, step: Dict[str, Any], step_index: int) -> str:
        """Generate a dummy natural language question for data selection"""
        function = step.get("function", "").lower()
        pipeline_type = step.get("pipeline_type", "").lower()
        title = step.get("title", "")
        input_columns = step.get("input_columns", [])
        
        # Generate context-aware questions based on function and pipeline type
        question_templates = {
            "aggregate_by_time": f"What time periods should we analyze for {title.lower()}?",
            "calculate_trends": f"Which metrics should we track for trend analysis in {title.lower()}?",
            "detect_anomalies": f"What data patterns should we monitor for anomalies in {title.lower()}?",
            "calculate_metrics": f"Which key performance indicators should we calculate for {title.lower()}?",
            "segment_data": f"How should we group the data for segmentation in {title.lower()}?",
            "forecast_values": f"What time horizon should we use for forecasting {title.lower()}?",
            "moving_average": f"What window size should we use for the moving average in {title.lower()}?",
            "variance_analysis": f"Which variables should we analyze for variance in {title.lower()}?",
            "correlation_analysis": f"Which variables should we examine for correlations in {title.lower()}?",
            "cohort_analysis": f"What cohort groups should we create for {title.lower()}?",
            "moving_apply_by_group": f"What grouping criteria should we use for the moving analysis in {title.lower()}?",
            "unknown_function": f"What data should we select and analyze for {title.lower()}?"
        }
        
        # Get specific question or generate generic one
        if function in question_templates:
            question = question_templates[function]
        else:
            # Generic question based on pipeline type
            if pipeline_type in ["timeseriespipe", "movingaggrpipe"]:
                question = f"What time-based analysis should we perform for {title.lower()}?"
            elif pipeline_type in ["cohortpipe", "segmentpipe"]:
                question = f"How should we group and analyze the data for {title.lower()}?"
            elif pipeline_type in ["riskpipe", "anomalypipe"]:
                question = f"What risk factors should we monitor in {title.lower()}?"
            else:
                question = f"What data should we select and analyze for {title.lower()}?"
        
        # Add column-specific context if available
        if input_columns:
            columns_str = ", ".join(input_columns[:3])  # Show first 3 columns
            if len(input_columns) > 3:
                columns_str += f" and {len(input_columns) - 3} more"
            question += f" (Available columns: {columns_str})"
        
        return question
    
    def _add_pipeline_end_steps(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], 
                               step_codes: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Add summarization and visualization steps at the end of the pipeline"""
        final_nodes = nodes.copy()
        final_edges = edges.copy()
        
        if not step_codes:
            return final_nodes, final_edges
        
        # Find the last step
        last_step = max(step_codes, key=lambda x: x["step_number"])
        last_node_id = f"step_{last_step['step_number']}"
        
        # Add summarization step
        summary_step_number = len(step_codes) + 1
        summary_node = {
            "id": f"step_{summary_step_number}",
            "title": "Pipeline Results Summary",
            "node_type": NodeType.SUMMARIZATION.value,
            "function": "generate_summary",
            "pipeline_type": "SummaryPipe",
            "input_dataframe": last_step["output_dataframe"],
            "output_dataframe": f"summary_result",
            "dependencies": [last_step["step_number"]],
            "input_columns": last_step.get("output_columns", []),
            "output_columns": ["summary_text", "key_insights", "recommendations"],
            "code": "# Generate comprehensive summary of pipeline results\nsummary_result = generate_pipeline_summary(input_data)",
            "step_number": summary_step_number,
            "nl_question": "What key insights and patterns should be highlighted in the summary?",
            "metadata": {
                "execution_order": summary_step_number,
                "is_parallel": False,
                "is_conditional": False,
                "complexity_score": 0.3,
                "estimated_execution_time": "fast",
                "memory_usage": "low"
            }
        }
        final_nodes.append(summary_node)
        
        # Add edge from last step to summary
        summary_edge = {
            "from_node": last_node_id,
            "to_node": f"step_{summary_step_number}",
            "edge_type": EdgeType.DATA_FLOW.value,
            "data_flow": f"{last_node_id}_result -> step_{summary_step_number}_input",
            "metadata": {
                "flow_type": "summary_generation",
                "is_critical": True
            }
        }
        final_edges.append(summary_edge)
        
        # Add visualization step
        viz_step_number = len(step_codes) + 2
        viz_node = {
            "id": f"step_{viz_step_number}",
            "title": "Results Visualization",
            "node_type": NodeType.VISUALIZATION.value,
            "function": "create_visualizations",
            "pipeline_type": "VizPipe",
            "input_dataframe": "summary_result",
            "output_dataframe": f"visualization_result",
            "dependencies": [summary_step_number],
            "input_columns": ["summary_text", "key_insights", "recommendations"],
            "output_columns": ["charts", "plots", "dashboard"],
            "code": "# Create visualizations for pipeline results\nvisualization_result = create_pipeline_visualizations(summary_result)",
            "step_number": viz_step_number,
            "nl_question": "What types of charts and visualizations would best represent the results?",
            "metadata": {
                "execution_order": viz_step_number,
                "is_parallel": False,
                "is_conditional": False,
                "complexity_score": 0.4,
                "estimated_execution_time": "medium",
                "memory_usage": "medium"
            }
        }
        final_nodes.append(viz_node)
        
        # Add edge from summary to visualization
        viz_edge = {
            "from_node": f"step_{summary_step_number}",
            "to_node": f"step_{viz_step_number}",
            "edge_type": EdgeType.DATA_FLOW.value,
            "data_flow": f"step_{summary_step_number}_result -> step_{viz_step_number}_input",
            "metadata": {
                "flow_type": "visualization_generation",
                "is_critical": True
            }
        }
        final_edges.append(viz_edge)
        
        return final_nodes, final_edges

    def _determine_node_type(self, step: Dict[str, Any]) -> NodeType:
        """Determine the type of node based on step characteristics"""
        function = step.get("function", "").lower()
        pipeline_type = step.get("pipeline_type", "").lower()
        
        # Check for conditional logic
        if any(keyword in function for keyword in ["if", "when", "case", "switch"]):
            return NodeType.CONDITIONAL
        
        # Check for loop operations
        if any(keyword in function for keyword in ["loop", "iterate", "repeat", "for", "while"]):
            return NodeType.LOOP
        
        # Check for parallel operations
        if any(keyword in function for keyword in ["parallel", "async", "concurrent", "batch"]):
            return NodeType.PARALLEL
        
        # Check for data input/output
        if "input" in function or "load" in function:
            return NodeType.DATA_INPUT
        elif "output" in function or "save" in function or "export" in function:
            return NodeType.DATA_OUTPUT
        
        # Check for data selection operations
        if any(keyword in function for keyword in ["select", "filter", "query", "where"]):
            return NodeType.DATA_SELECTION
        
        # Check for summarization operations
        if any(keyword in function for keyword in ["summary", "summarize", "generate_summary"]):
            return NodeType.SUMMARIZATION
        
        # Check for visualization operations
        if any(keyword in function for keyword in ["visualize", "plot", "chart", "create_visualizations"]):
            return NodeType.VISUALIZATION
        
        # Default to processing
        return NodeType.PROCESSING
    
    def _calculate_complexity_score(self, step: Dict[str, Any]) -> float:
        """Calculate a complexity score for the step (0-1)"""
        score = 0.0
        
        # Base complexity from function type
        function = step.get("function", "").lower()
        if any(keyword in function for keyword in ["variance", "correlation", "regression"]):
            score += 0.3
        elif any(keyword in function for keyword in ["mean", "sum", "count"]):
            score += 0.1
        elif any(keyword in function for keyword in ["moving", "rolling", "lag", "lead"]):
            score += 0.4
        
        # Pipeline type complexity
        pipeline_type = step.get("pipeline_type", "").lower()
        if pipeline_type in ["timeseriespipe", "movingaggrpipe"]:
            score += 0.2
        elif pipeline_type in ["cohortpipe", "segmentpipe"]:
            score += 0.3
        
        # Input/output complexity
        input_cols = len(step.get("input_columns", []))
        output_cols = len(step.get("output_columns", []))
        score += min(0.2, (input_cols + output_cols) * 0.02)
        
        return min(1.0, score)
    
    def _estimate_execution_time(self, step: Dict[str, Any]) -> str:
        """Estimate execution time for the step"""
        function = step.get("function", "").lower()
        pipeline_type = step.get("pipeline_type", "").lower()
        
        if any(keyword in function for keyword in ["mean", "sum", "count"]):
            return "fast"
        elif any(keyword in function for keyword in ["variance", "correlation"]):
            return "medium"
        elif any(keyword in function for keyword in ["moving", "rolling", "lag"]):
            return "slow"
        elif pipeline_type in ["cohortpipe", "segmentpipe"]:
            return "slow"
        else:
            return "medium"
    
    def _estimate_memory_usage(self, step: Dict[str, Any]) -> str:
        """Estimate memory usage for the step"""
        function = step.get("function", "").lower()
        pipeline_type = step.get("pipeline_type", "").lower()
        
        if any(keyword in function for keyword in ["moving", "rolling", "lag", "lead"]):
            return "high"
        elif pipeline_type in ["cohortpipe", "segmentpipe"]:
            return "high"
        else:
            return "medium"
    
    def _analyze_execution_order(self, flow_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the execution order and identify potential optimizations"""
        nodes = flow_graph["nodes"]
        edges = flow_graph["edges"]
        
        # Create execution order
        execution_order = sorted(nodes, key=lambda x: x["step_number"])
        
        # Identify critical path
        critical_path = self._find_critical_path(nodes, edges)
        
        # Identify parallel execution opportunities
        parallel_opportunities = self._find_parallel_opportunities(nodes, edges)
        
        return {
            "execution_order": [node["id"] for node in execution_order],
            "critical_path": critical_path,
            "parallel_opportunities": parallel_opportunities,
            "total_execution_steps": len(execution_order),
            "can_parallelize": len(parallel_opportunities) > 0
        }
    
    def _find_critical_path(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
        """Find the critical path through the flow graph"""
        # Simple implementation - longest dependency chain
        critical_path = []
        visited = set()
        
        def dfs(node_id, path):
            if node_id in visited:
                return path
            visited.add(node_id)
            path.append(node_id)
            
            # Find dependent nodes
            dependent_edges = [e for e in edges if e["from_node"] == node_id]
            if dependent_edges:
                # Choose the longest path
                longest_path = path
                for edge in dependent_edges:
                    new_path = dfs(edge["to_node"], path.copy())
                    if len(new_path) > len(longest_path):
                        longest_path = new_path
                return longest_path
            return path
        
        # Start from nodes with no dependencies
        start_nodes = [node["id"] for node in nodes if not node["dependencies"]]
        for start_node in start_nodes:
            path = dfs(start_node, [])
            if len(path) > len(critical_path):
                critical_path = path
        
        return critical_path
    
    def _find_parallel_opportunities(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[List[str]]:
        """Find opportunities for parallel execution"""
        parallel_groups = []
        
        # Group nodes that can run in parallel (no dependencies between them)
        remaining_nodes = set(node["id"] for node in nodes)
        
        while remaining_nodes:
            # Find nodes with no dependencies on remaining nodes
            current_group = []
            for node in nodes:
                if node["id"] in remaining_nodes:
                    # Check if all dependencies are satisfied
                    dependencies_satisfied = all(
                        dep not in remaining_nodes for dep in node["dependencies"]
                    )
                    if dependencies_satisfied:
                        current_group.append(node["id"])
            
            if current_group:
                parallel_groups.append(current_group)
                remaining_nodes -= set(current_group)
            else:
                # No more parallel opportunities
                break
        
        return parallel_groups
    
    def _analyze_dependencies(self, flow_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze dependencies between nodes"""
        nodes = flow_graph.get("nodes", [])
        edges = flow_graph.get("edges", [])
        
        # Create dependency graph
        dependency_graph = {}
        for node in nodes:
            if isinstance(node, dict) and "id" in node:
                dependency_graph[node["id"]] = {
                    "dependencies": node.get("dependencies", []),
                    "dependents": []
                }
        
        # Fill in dependents
        for edge in edges:
            if isinstance(edge, dict) and edge.get("edge_type") == EdgeType.DEPENDENCY.value:
                from_node = edge.get("from_node")
                to_node = edge.get("to_node")
                if from_node and to_node and from_node in dependency_graph:
                    dependency_graph[from_node]["dependents"].append(to_node)
        
        # Find circular dependencies
        circular_deps = self._find_circular_dependencies(dependency_graph)
        
        # Find orphaned nodes
        orphaned_nodes = []
        for node in nodes:
            if isinstance(node, dict) and "id" in node:
                node_id = node["id"]
                dependencies = node.get("dependencies", [])
                has_incoming_edges = any(e.get("to_node") == node_id for e in edges if isinstance(e, dict))
                if not dependencies and not has_incoming_edges:
                    orphaned_nodes.append(node_id)
        
        return {
            "dependency_graph": dependency_graph,
            "circular_dependencies": circular_deps,
            "orphaned_nodes": orphaned_nodes,
            "max_dependency_depth": self._calculate_max_dependency_depth(dependency_graph)
        }
    
    def _find_circular_dependencies(self, dependency_graph: Dict[str, Any]) -> List[List[str]]:
        """Find circular dependencies in the graph"""
        circular_deps = []
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                circular_deps.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            if node not in dependency_graph:
                return  # Node doesn't exist in dependency graph
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            dependents = dependency_graph[node].get("dependents", [])
            for dependent in dependents:
                dfs(dependent, path.copy())
            
            rec_stack.remove(node)
        
        for node in dependency_graph:
            if node not in visited and node in dependency_graph:
                dfs(node, [])
        
        return circular_deps
    
    def _calculate_max_dependency_depth(self, dependency_graph: Dict[str, Any]) -> int:
        """Calculate the maximum dependency depth"""
        max_depth = 0
        
        def calculate_depth(node, visited):
            if node in visited:
                return 0  # Circular dependency
            if node not in dependency_graph:
                return 0  # Node doesn't exist in dependency graph
            if not dependency_graph[node].get("dependencies", []):
                return 1
            
            visited.add(node)
            dependencies = dependency_graph[node].get("dependencies", [])
            if not dependencies:
                return 1
            
            depth = 1 + max(
                calculate_depth(dep, visited.copy()) for dep in dependencies
            )
            return depth
        
        for node in dependency_graph:
            if node in dependency_graph:  # Double check node exists
                depth = calculate_depth(node, set())
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _analyze_data_flow(self, flow_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data flow through the pipeline"""
        nodes = flow_graph["nodes"]
        edges = flow_graph["edges"]
        
        # Track data transformations
        data_transformations = []
        for node in nodes:
            transformation = {
                "node_id": node["id"],
                "function": node["function"],
                "input_columns": node["input_columns"],
                "output_columns": node["output_columns"],
                "input_dataframe": node["input_dataframe"],
                "output_dataframe": node["output_dataframe"]
            }
            data_transformations.append(transformation)
        
        # Find data bottlenecks
        bottlenecks = self._find_data_bottlenecks(nodes, edges)
        
        # Calculate data volume estimates
        volume_estimates = self._estimate_data_volumes(nodes)
        
        return {
            "data_transformations": data_transformations,
            "bottlenecks": bottlenecks,
            "volume_estimates": volume_estimates,
            "total_transformations": len(data_transformations)
        }
    
    def _find_data_bottlenecks(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find potential data bottlenecks"""
        bottlenecks = []
        
        for node in nodes:
            # Check for high complexity operations
            if node["metadata"]["complexity_score"] > 0.7:
                bottlenecks.append({
                    "node_id": node["id"],
                    "type": "high_complexity",
                    "reason": f"Complex operation: {node['function']}",
                    "severity": "medium"
                })
            
            # Check for high memory usage
            if node["metadata"]["memory_usage"] == "high":
                bottlenecks.append({
                    "node_id": node["id"],
                    "type": "high_memory",
                    "reason": f"High memory usage: {node['function']}",
                    "severity": "high"
                })
        
        return bottlenecks
    
    def _estimate_data_volumes(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Estimate data volumes at each step"""
        volume_estimates = {}
        
        for node in nodes:
            # Simple estimation based on function type
            input_cols = len(node["input_columns"])
            output_cols = len(node["output_columns"])
            
            # Estimate based on function complexity
            if node["function"].lower() in ["mean", "sum", "count"]:
                volume_estimate = "reduced"
            elif node["function"].lower() in ["variance", "correlation"]:
                volume_estimate = "similar"
            elif node["function"].lower() in ["moving", "rolling"]:
                volume_estimate = "increased"
            else:
                volume_estimate = "similar"
            
            volume_estimates[node["id"]] = {
                "input_columns": input_cols,
                "output_columns": output_cols,
                "volume_change": volume_estimate,
                "estimated_rows": "unknown"  # Would need actual data to estimate
            }
        
        return volume_estimates
    
    def _create_visualization_data(self, flow_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Create data for visualization tools"""
        nodes = flow_graph["nodes"]
        edges = flow_graph["edges"]
        
        # Create node positions (simple layout)
        node_positions = {}
        for i, node in enumerate(nodes):
            node_positions[node["id"]] = {
                "x": i * 200,
                "y": 0,
                "level": node["step_number"]
            }
        
        # Create edge paths
        edge_paths = []
        for edge in edges:
            from_pos = node_positions.get(edge["from_node"], {"x": 0, "y": 0})
            to_pos = node_positions.get(edge["to_node"], {"x": 0, "y": 0})
            
            edge_paths.append({
                "from": edge["from_node"],
                "to": edge["to_node"],
                "type": edge["edge_type"],
                "path": [
                    {"x": from_pos["x"], "y": from_pos["y"]},
                    {"x": to_pos["x"], "y": to_pos["y"]}
                ]
            })
        
        return {
            "node_positions": node_positions,
            "edge_paths": edge_paths,
            "layout_type": "sequential",
            "canvas_size": {
                "width": len(nodes) * 200 + 100,
                "height": 300
            }
        }
    
    def _has_parallel_execution(self, flow_graph: Dict[str, Any]) -> bool:
        """Check if the flow graph has parallel execution opportunities"""
        execution_analysis = self._analyze_execution_order(flow_graph)
        return execution_analysis["can_parallelize"]
    
    def _has_conditional_logic(self, flow_graph: Dict[str, Any]) -> bool:
        """Check if the flow graph has conditional logic"""
        return any(node["node_type"] == NodeType.CONDITIONAL.value for node in flow_graph["nodes"])
    
    def _generate_mermaid_chart(self, flow_graph: Dict[str, Any]) -> str:
        """Generate a Mermaid flowchart from the flow graph"""
        nodes = flow_graph["nodes"]
        edges = flow_graph["edges"]
        
        if not nodes:
            return "graph TD\n    A[No nodes found]"
        
        # Start Mermaid diagram
        mermaid_lines = ["graph TD"]
        
        # Define pipeline type colors and shapes
        pipeline_styles = {
            'MetricsPipe': {'color': '#FF6B6B', 'shape': 'rect'},
            'TimeSeriesPipe': {'color': '#4ECDC4', 'shape': 'rect'},
            'CohortPipe': {'color': '#45B7D1', 'shape': 'rect'},
            'TrendPipe': {'color': '#96CEB4', 'shape': 'rect'},
            'SegmentPipe': {'color': '#FFEAA7', 'shape': 'rect'},
            'RiskPipe': {'color': '#DDA0DD', 'shape': 'rect'},
            'AnomalyPipe': {'color': '#FFB347', 'shape': 'rect'},
            'OperationsPipe': {'color': '#98D8C8', 'shape': 'rect'},
            'MovingAggrPipe': {'color': '#F7DC6F', 'shape': 'rect'},
            'FunnelPipe': {'color': '#BB8FCE', 'shape': 'rect'},
            'SummaryPipe': {'color': '#A8E6CF', 'shape': 'round'},
            'VizPipe': {'color': '#FFD93D', 'shape': 'round'}
        }
        
        # Add nodes
        for node in nodes:
            node_id = node["id"]
            title = node["title"].replace('"', '\\"')
            function = node["function"]
            pipeline_type = node["pipeline_type"]
            step_number = node.get("step_number", 1)
            
            # Create enhanced node label with step number, title, function, pipeline type, and NL question
            nl_question = node.get("nl_question", "")
            node_label = f'Step {step_number}: {title}\\nFunction: {function}\\nPipeline: {pipeline_type}'
            if nl_question:
                # Truncate long questions for better display
                short_question = nl_question[:60] + "..." if len(nl_question) > 60 else nl_question
                node_label += f'\\nQ: {short_question}'
            
            # Add node to Mermaid
            mermaid_lines.append(f'    {node_id}["{node_label}"]')
            
            # Add styling based on pipeline type
            if pipeline_type in pipeline_styles:
                style = pipeline_styles[pipeline_type]
                mermaid_lines.append(f'    classDef {pipeline_type} fill:{style["color"]},stroke:#333,stroke-width:2px')
                mermaid_lines.append(f'    class {node_id} {pipeline_type}')
        
        # Add edges
        for edge in edges:
            from_node = edge["from_node"]
            to_node = edge["to_node"]
            edge_type = edge.get("edge_type", "data_flow")
            
            # Add edge with optional label
            if edge_type == "dependency":
                mermaid_lines.append(f'    {from_node} -.-> {to_node}')
            else:
                mermaid_lines.append(f'    {from_node} --> {to_node}')
        
        # Add execution order information
        if len(nodes) > 1:
            mermaid_lines.append("")
            mermaid_lines.append("    %% Execution Order")
            execution_order = sorted(nodes, key=lambda x: x.get("step_number", 1))
            for i, node in enumerate(execution_order):
                if i < len(execution_order) - 1:
                    next_node = execution_order[i + 1]
                    mermaid_lines.append(f'    {node["id"]} -.-> {next_node["id"]}')
        
        # Add metadata as comments
        mermaid_lines.append("")
        mermaid_lines.append("    %% Flow Graph Metadata")
        mermaid_lines.append(f"    %% Total Nodes: {len(nodes)}")
        mermaid_lines.append(f"    %% Total Edges: {len(edges)}")
        mermaid_lines.append(f"    %% Pipeline Types: {', '.join(set(node['pipeline_type'] for node in nodes))}")
        
        return "\n".join(mermaid_lines)
    
    def _generate_step_details(self, flow_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed information for each step including reasoning and examples"""
        nodes = flow_graph["nodes"]
        step_details = {}
        
        for node in nodes:
            node_id = node["id"]
            step_number = node.get("step_number", 1)
            
            # Extract step information
            step_info = {
                "step_number": step_number,
                "title": node["title"],
                "function": node["function"],
                "pipeline_type": node["pipeline_type"],
                "description": node.get("description", ""),
                "input_dataframe": node.get("input_dataframe", ""),
                "output_dataframe": node.get("output_dataframe", ""),
                "dependencies": node.get("dependencies", []),
                "input_columns": node.get("input_columns", []),
                "output_columns": node.get("output_columns", []),
                "code": node.get("code", ""),
                "nl_question": node.get("nl_question", ""),
                "reasoning": self._generate_step_reasoning(node),
                "example": self._generate_step_example(node),
                "metadata": node.get("metadata", {})
            }
            
            step_details[node_id] = step_info
        
        return step_details
    
    def _generate_step_reasoning(self, node: Dict[str, Any]) -> str:
        """Generate reasoning explanation for a step"""
        function = node["function"]
        pipeline_type = node["pipeline_type"]
        title = node["title"]
        
        reasoning_templates = {
            "aggregate_by_time": f"This step aggregates data by time periods to analyze temporal patterns. The {pipeline_type} pipeline is used to group data and calculate metrics over time, which helps identify trends and seasonal patterns in the dataset.",
            "calculate_trends": f"This step calculates trend analysis using the {pipeline_type} pipeline. It identifies upward, downward, or stable trends in the data over time, providing insights into data behavior and future predictions.",
            "detect_anomalies": f"This step performs anomaly detection using the {pipeline_type} pipeline. It identifies unusual patterns or outliers in the data that may indicate important events or data quality issues.",
            "calculate_metrics": f"This step calculates key metrics using the {pipeline_type} pipeline. It computes statistical measures like mean, median, standard deviation, and other relevant metrics to summarize the data.",
            "segment_data": f"This step segments the data using the {pipeline_type} pipeline. It groups similar data points together to identify distinct patterns or customer segments for targeted analysis.",
            "forecast_values": f"This step performs forecasting using the {pipeline_type} pipeline. It predicts future values based on historical data patterns, helping with planning and decision-making.",
            "generate_summary": f"This step generates a comprehensive summary of the pipeline results using the {pipeline_type} pipeline. It consolidates all findings, identifies key insights, and provides actionable recommendations based on the analysis.",
            "create_visualizations": f"This step creates visual representations of the analysis results using the {pipeline_type} pipeline. It generates charts, plots, and dashboards to make the findings more accessible and understandable to stakeholders."
        }
        
        # Get specific reasoning for the function, or use a generic template
        reasoning = reasoning_templates.get(function.lower(), 
            f"This step executes the {function} function using the {pipeline_type} pipeline. {title} involves processing the input data to generate meaningful insights and analysis results.")
        
        return reasoning
    
    def _generate_step_example(self, node: Dict[str, Any]) -> str:
        """Generate an example for a step"""
        function = node["function"]
        pipeline_type = node["pipeline_type"]
        input_df = node.get("input_dataframe", "df")
        output_df = node.get("output_dataframe", "result")
        
        example_templates = {
            "aggregate_by_time": f"Example: Group sales data by month to see monthly revenue trends. Input: {input_df} with date and sales columns. Output: {output_df} with monthly aggregated sales.",
            "calculate_trends": f"Example: Analyze customer growth trends over quarters. Input: {input_df} with customer data by quarter. Output: {output_df} with trend analysis and growth rates.",
            "detect_anomalies": f"Example: Find unusual spending patterns in transaction data. Input: {input_df} with transaction amounts and dates. Output: {output_df} with anomaly scores and flagged transactions.",
            "calculate_metrics": f"Example: Calculate average, min, max values for key performance indicators. Input: {input_df} with KPI data. Output: {output_df} with calculated metrics and statistics.",
            "segment_data": f"Example: Group customers by spending behavior and demographics. Input: {input_df} with customer data. Output: {output_df} with customer segments and characteristics.",
            "forecast_values": f"Example: Predict next quarter's revenue based on historical data. Input: {input_df} with historical revenue. Output: {output_df} with forecasted values and confidence intervals.",
            "generate_summary": f"Example: Create executive summary of analysis results. Input: {input_df} with all analysis outputs. Output: {output_df} with summary text, key insights, and recommendations.",
            "create_visualizations": f"Example: Generate charts and dashboards for presentation. Input: {input_df} with summary data. Output: {output_df} with interactive charts, plots, and dashboard components."
        }
        
        # Get specific example for the function, or use a generic template
        example = example_templates.get(function.lower(),
            f"Example: Process data using {function} function. Input: {input_df} with relevant data columns. Output: {output_df} with processed results and insights.")
        
        return example
