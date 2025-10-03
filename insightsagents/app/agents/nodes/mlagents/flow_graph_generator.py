"""
Flow Graph Generator Agent

This agent takes the output from the SelfCorrectingPipelineCodeGenerator and creates
a comprehensive flow graph with nodes, edges, and execution order information.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import matplotlib.pyplot as plt
import networkx as nx
import matplotlib.patches as mpatches

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
    
    def create_comprehensive_flow_file(self, pipeline_flow_result: Dict[str, Any], output_dir: str, analysis_name: str, timestamp: str = "") -> Optional[str]:
        """
        Create a comprehensive single file with all flow information
        
        Args:
            pipeline_flow_result: Result from pipeline flow integration
            output_dir: Directory to save the file
            analysis_name: Name of the analysis
            timestamp: Optional timestamp to append to filename
            
        Returns:
            Path to the created file, or None if failed
        """
        try:
            if not pipeline_flow_result or pipeline_flow_result.get("status") != "success":
                self.logger.warning("No valid pipeline flow result for comprehensive file")
                return None
            
            pipeline_result = pipeline_flow_result["pipeline_result"]
            flow_graph_result = pipeline_flow_result["flow_graph_result"]
            integration_metadata = pipeline_flow_result["integration_metadata"]
            
            # Create comprehensive flow file
            filename = f"{analysis_name}_comprehensive_flow{'_' + timestamp if timestamp else ''}.py"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f'"""\n')
                f.write(f'Comprehensive Pipeline Flow Analysis\n')
                f.write(f'Analysis: {analysis_name.replace("_", " ").title()}\n')
                f.write(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                f.write(f'Status: {pipeline_flow_result["status"]}\n')
                f.write(f'"""\n\n')
                
                # Write imports
                f.write('# Required imports\n')
                f.write('import pandas as pd\n')
                f.write('import numpy as np\n')
                f.write('from datetime import datetime, timedelta\n\n')
                
                # Pipeline imports
                f.write('# Pipeline imports\n')
                f.write('from app.tools.mltools import (\n')
                f.write('    # Cohort Analysis\n')
                f.write('    CohortPipe, form_time_cohorts, form_behavioral_cohorts, form_acquisition_cohorts,\n')
                f.write('    calculate_retention, calculate_conversion, calculate_lifetime_value,\n\n')
                f.write('    # Segmentation\n')
                f.write('    SegmentationPipe, get_features, run_kmeans, run_dbscan, run_hierarchical,\n')
                f.write('    run_rule_based, generate_summary, get_segment_data, compare_algorithms, custom_calculation,\n\n')
                f.write('    # Trend Analysis\n')
                f.write('    TrendPipe, aggregate_by_time, calculate_growth_rates, calculate_moving_average,\n')
                f.write('    calculate_statistical_trend, decompose_trend, forecast_metric, compare_periods, get_top_metrics, _test_trend,\n\n')
                f.write('    # Funnel Analysis\n')
                f.write('    analyze_funnel, analyze_funnel_by_time, analyze_user_paths, analyze_funnel_by_segment,\n')
                f.write('    get_funnel_summary, compare_segments,\n\n')
                f.write('    # Time Series Analysis\n')
                f.write('    TimeSeriesPipe, lead, lag, distribution_analysis, cumulative_distribution,\n')
                f.write('    variance_analysis, get_distribution_summary, custom_calculation, rolling_window,\n\n')
                f.write('    # Metrics Analysis\n')
                f.write('    MetricsPipe, Mean, Sum, Count, Max, Min, Ratio, Dot, Nth, Variance,\n')
                f.write('    StandardDeviation, CV, Correlation, Cov, Median, Percentile, PivotTable,\n')
                f.write('    GroupBy, Filter, CumulativeSum, RollingMetric, Execute, ShowPivot, ShowDataFrame,\n\n')
                f.write('    # Operations Analysis\n')
                f.write('    OperationsPipe, PercentChange, AbsoluteChange, MH, CUPED, PrePostChange,\n')
                f.write('    SelectColumns, FilterConditions, PowerAnalysis, StratifiedSummary, BootstrapCI,\n')
                f.write('    MultiComparisonAdjustment, ExecuteOperations, ShowOperation, ShowComparison,\n\n')
                f.write('    # Moving Averages\n')
                f.write('    MovingAggrPipe, moving_average, moving_variance, moving_sum, moving_quantile,\n')
                f.write('    moving_correlation, moving_zscore, moving_apply_by_group, moving_ratio,\n')
                f.write('    detect_turning_points, moving_regression, moving_min_max, moving_count,\n')
                f.write('    moving_aggregate, moving_percentile_rank, time_weighted_average, moving_cumulative, expanding_window,\n\n')
                f.write('    # Risk Analysis\n')
                f.write('    RiskPipe, fit_distribution, calculate_var, calculate_cvar, calculate_portfolio_risk,\n')
                f.write('    monte_carlo_simulation, stress_test, rolling_risk_metrics, correlation_analysis,\n')
                f.write('    risk_attribution, get_risk_summary, compare_distributions,\n\n')
                f.write('    # Anomaly Detection\n')
                f.write('    AnomalyPipe, detect_statistical_outliers, detect_contextual_anomalies, detect_collective_anomalies,\n')
                f.write('    calculate_seasonal_residuals, detect_anomalies_from_residuals, get_anomaly_summary,\n')
                f.write('    get_top_anomalies, detect_change_points, forecast_and_detect_anomalies, batch_detect_anomalies,\n\n')
                f.write('    # Group Aggregation Functions - Basic\n')
                f.write('    mean, sum_values, count_values, max_value, min_value, std_dev, variance, median,\n')
                f.write('    quantile, range_values, coefficient_of_variation, skewness, kurtosis, unique_count, mode,\n')
                f.write('    weighted_average, geometric_mean, harmonic_mean, interquartile_range, mad,\n\n')
                f.write('    # Group Aggregation Functions - Operations\n')
                f.write('    percent_change, absolute_change, mantel_haenszel_estimate, cuped_adjustment,\n')
                f.write('    prepost_adjustment, power_analysis, stratified_summary, bootstrap_confidence_interval,\n')
                f.write('    multi_comparison_adjustment, effect_size, z_score, relative_risk, odds_ratio,\n\n')
                f.write('    # Group Aggregation Functions - Utilities\n')
                f.write('    get_function_by_name, get_all_function_names, get_function_metadata,\n')
                f.write('    get_all_functions_metadata, GROUP_AGGREGATION_FUNCTIONS,\n\n')
                f.write('    # Function Registry\n')
                f.write('    MLFunctionRegistry, FunctionMetadata, initialize_function_registry,\n')
                f.write('    FunctionSearchInterface, SearchResult, create_search_interface,\n')
                f.write('    FunctionRetrievalService, create_function_retrieval_service\n')
                f.write(')\n\n')
                
                # Write flow graph metadata
                f.write('# Flow Graph Metadata\n')
                f.write('# ===================\n')
                metadata = flow_graph_result['metadata']
                f.write(f'TOTAL_NODES = {metadata["total_nodes"]}\n')
                f.write(f'TOTAL_EDGES = {metadata["total_edges"]}\n')
                f.write(f'PIPELINE_TYPES = {metadata["pipeline_types"]}\n')
                f.write(f'FUNCTIONS_USED = {metadata["functions_used"]}\n')
                f.write(f'CAN_PARALLELIZE = {metadata["can_parallelize"]}\n')
                f.write(f'HAS_CONDITIONAL_LOGIC = {metadata["has_conditional_logic"]}\n\n')
                
                # Write execution analysis
                f.write('# Execution Analysis\n')
                f.write('# ==================\n')
                execution_analysis = flow_graph_result.get('execution_analysis', {})
                f.write(f'EXECUTION_ORDER = {execution_analysis.get("execution_order", [])}\n')
                f.write(f'CRITICAL_PATH = {execution_analysis.get("critical_path", [])}\n')
                f.write(f'PARALLEL_OPPORTUNITIES = {execution_analysis.get("parallel_opportunities", [])}\n')
                f.write(f'TOTAL_EXECUTION_STEPS = {execution_analysis.get("total_execution_steps", 0)}\n')
                f.write(f'CAN_PARALLELIZE = {execution_analysis.get("can_parallelize", False)}\n\n')
                
                # Write dependency analysis
                f.write('# Dependency Analysis\n')
                f.write('# ===================\n')
                dependency_analysis = flow_graph_result.get('dependency_analysis', {})
                f.write(f'CIRCULAR_DEPENDENCIES = {len(dependency_analysis.get("circular_dependencies", []))}\n')
                f.write(f'ORPHANED_NODES = {len(dependency_analysis.get("orphaned_nodes", []))}\n')
                f.write(f'MAX_DEPENDENCY_DEPTH = {dependency_analysis.get("max_dependency_depth", 0)}\n\n')
                
                # Write data flow analysis
                f.write('# Data Flow Analysis\n')
                f.write('# ==================\n')
                data_flow_analysis = flow_graph_result.get('data_flow_analysis', {})
                f.write(f'TOTAL_TRANSFORMATIONS = {data_flow_analysis.get("total_transformations", 0)}\n')
                f.write(f'BOTTLENECKS = {len(data_flow_analysis.get("bottlenecks", []))}\n\n')
                
                # Write individual step functions
                f.write('# Individual Step Functions\n')
                f.write('# =========================\n')
                step_codes = pipeline_result.get('step_codes', [])
                
                for i, step in enumerate(step_codes, 1):
                    f.write(f'def step_{i}_{step["function"].lower()}(df):\n')
                    f.write(f'    """\n')
                    f.write(f'    Step {i}: {step["title"]}\n')
                    f.write(f'    Function: {step["function"]}\n')
                    f.write(f'    Pipeline Type: {step["pipeline_type"]}\n')
                    f.write(f'    Input: {step["input_dataframe"]} -> Output: {step["output_dataframe"]}\n')
                    f.write(f'    Dependencies: {step["dependencies"]}\n')
                    f.write(f'    """\n')
                    f.write(f'    try:\n')
                    
                    # Indent the generated code
                    for line in step['code'].split('\n'):
                        if line.strip():
                            f.write(f'        {line}\n')
                        else:
                            f.write('\n')
                    
                    f.write(f'        return result\n')
                    f.write(f'    except Exception as e:\n')
                    f.write(f'        print(f"Error in step {i}: {{e}}")\n')
                    f.write(f'        return None\n\n')
                
                # Write combined pipeline function
                f.write('# Combined Pipeline Function\n')
                f.write('# ==========================\n')
                f.write('def run_combined_pipeline(df):\n')
                f.write('    """Execute the complete pipeline with all steps"""\n')
                f.write('    try:\n')
                f.write('        # Start with original data\n')
                f.write('        result = df.copy()\n\n')
                
                for i, step in enumerate(step_codes, 1):
                    f.write(f'        # Step {i}: {step["title"]}\n')
                    f.write(f'        result = step_{i}_{step["function"].lower()}(result)\n')
                    f.write(f'        if result is None:\n')
                    f.write(f'            print(f"Pipeline failed at step {i}")\n')
                    f.write(f'            return None\n\n')
                
                f.write('        return result\n')
                f.write('    except Exception as e:\n')
                f.write('        print(f"Error running combined pipeline: {e}")\n')
                f.write('        return None\n\n')
                
                # Write parallel execution function
                if flow_graph_result['metadata']['can_parallelize']:
                    f.write('# Parallel Execution Function\n')
                    f.write('# ===========================\n')
                    f.write('import concurrent.futures\n\n')
                    f.write('def run_parallel_pipeline(df):\n')
                    f.write('    """Execute independent steps in parallel where possible"""\n')
                    f.write('    try:\n')
                    f.write('        # This is a simplified parallel execution\n')
                    f.write('        # In practice, you would need to handle dependencies properly\n')
                    f.write('        result = df.copy()\n')
                    f.write('        \n')
                    f.write('        # Execute steps sequentially for now\n')
                    f.write('        # TODO: Implement proper parallel execution based on dependencies\n')
                    f.write('        return run_combined_pipeline(result)\n')
                    f.write('    except Exception as e:\n')
                    f.write('        print(f"Error running parallel pipeline: {e}")\n')
                    f.write('        return None\n\n')
                
                # Write main execution block
                f.write('# Main Execution\n')
                f.write('# ==============\n')
                f.write('if __name__ == "__main__":\n')
                f.write('    # Load your data here\n')
                f.write('    # df = pd.read_csv("your_data.csv")\n')
                f.write('    \n')
                f.write('    print("🚀 Running Pipeline Flow Analysis...")\n')
                f.write('    print(f"Total Steps: {len(step_codes)}")\n')
                f.write('    print(f"Pipeline Types: {PIPELINE_TYPES}")\n')
                f.write('    print(f"Can Parallelize: {CAN_PARALLELIZE}")\n\n')
                f.write('    # Run individual steps\n')
                f.write('    for i in range(1, len(step_codes) + 1):\n')
                f.write('        print(f"\\n🔧 Executing Step {i}...")\n')
                f.write('        # result = step_i_function(df)\n')
                f.write('    \n')
                f.write('    # Run combined pipeline\n')
                f.write('    print("\\n🔄 Running Combined Pipeline...")\n')
                f.write('    # final_result = run_combined_pipeline(df)\n')
                f.write('    \n')
                f.write('    if CAN_PARALLELIZE:\n')
                f.write('        print("\\n⚡ Running Parallel Pipeline...")\n')
                f.write('        # parallel_result = run_parallel_pipeline(df)\n')
                f.write('    \n')
                f.write('    print("\\n✅ Pipeline execution complete!")\n')
            
            self.logger.info(f"📄 Comprehensive flow file saved: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ Error creating comprehensive flow file: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def create_mermaid_visualization(self, pipeline_flow_result: Dict[str, Any], output_dir: str, analysis_name: str, timestamp: str = "") -> Optional[str]:
        """
        Create a Mermaid chart visualization of the flow graph
        
        Args:
            pipeline_flow_result: Result from pipeline flow integration
            output_dir: Directory to save the file
            analysis_name: Name of the analysis
            timestamp: Optional timestamp to append to filename
            
        Returns:
            Path to the created file, or None if failed
        """
        try:
            if not pipeline_flow_result or pipeline_flow_result.get("status") != "success":
                self.logger.warning("No valid pipeline flow result for Mermaid visualization")
                return None
            
            flow_graph_result = pipeline_flow_result["flow_graph_result"]
            mermaid_chart = flow_graph_result.get("mermaid_chart", "")
            step_details = flow_graph_result.get("step_details", {})
            
            if not mermaid_chart:
                self.logger.warning("No Mermaid chart found in flow graph result")
                return None
            
            # Create Mermaid directory
            mermaid_dir = os.path.join(output_dir, "mermaid_charts")
            os.makedirs(mermaid_dir, exist_ok=True)
            
            # Save Mermaid chart
            filename = f"{analysis_name}_flow_chart{'_' + timestamp if timestamp else ''}.mmd"
            filepath = os.path.join(mermaid_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f'%% Flow Chart for {analysis_name.replace("_", " ").title()}\n')
                f.write(f'%% Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
                f.write(mermaid_chart)
            
            self.logger.info(f"🎨 Mermaid chart saved: {filepath}")
            
            # Also create an HTML file with embedded Mermaid
            html_filename = f"{analysis_name}_flow_chart{'_' + timestamp if timestamp else ''}.html"
            html_filepath = os.path.join(mermaid_dir, html_filename)
            
            # Generate step details HTML
            step_details_html = ""
            if step_details:
                step_details_html = """
        <div class="step-details">
            <h2>Step Details</h2>
"""
                for step_id, details in step_details.items():
                    step_details_html += f"""
            <div class="step-card">
                <h3>Step {details['step_number']}: {details['title']}</h3>
                <div class="step-info">
                    <p><strong>Function:</strong> {details['function']}</p>
                    <p><strong>Pipeline Type:</strong> {details['pipeline_type']}</p>
                    <p><strong>Input:</strong> {details['input_dataframe']} → <strong>Output:</strong> {details['output_dataframe']}</p>
                </div>
                <div class="reasoning">
                    <h4>Reasoning:</h4>
                    <p>{details['reasoning']}</p>
                </div>
                <div class="example">
                    <h4>Example:</h4>
                    <p>{details['example']}</p>
                </div>
                <div class="code-section">
                    <h4>Generated Code:</h4>
                    <pre><code>{details['code']}</code></pre>
                </div>
            </div>
"""
                step_details_html += "        </div>"

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Flow Chart - {analysis_name.replace("_", " ").title()}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }}
        .mermaid {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .step-details {{
            margin-top: 40px;
        }}
        .step-card {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            background-color: #fafafa;
        }}
        .step-card h3 {{
            color: #2c3e50;
            margin-top: 0;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .step-info {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}
        .step-info p {{
            margin: 5px 0;
        }}
        .reasoning, .example {{
            margin: 15px 0;
        }}
        .reasoning h4, .example h4 {{
            color: #27ae60;
            margin-bottom: 10px;
        }}
        .code-section {{
            margin-top: 15px;
        }}
        .code-section h4 {{
            color: #8e44ad;
            margin-bottom: 10px;
        }}
        .code-section pre {{
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 12px;
        }}
        .metadata {{
            margin-top: 30px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
            font-size: 14px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Flow Chart - {analysis_name.replace("_", " ").title()}</h1>
        <div class="mermaid">
{mermaid_chart}
        </div>
{step_details_html}
        <div class="metadata">
            <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>Analysis:</strong> {analysis_name}</p>
            <p><strong>Status:</strong> {pipeline_flow_result.get("status", "Unknown")}</p>
        </div>
    </div>
    
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            flowchart: {{
                useMaxWidth: true,
                htmlLabels: true
            }}
        }});
    </script>
</body>
</html>
        """
            
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"🌐 Interactive HTML chart saved: {html_filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ Error creating Mermaid visualization: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def create_flow_visualization(self, pipeline_flow_result: Dict[str, Any], output_dir: str, analysis_name: str, timestamp: str = "") -> Optional[str]:
        """
        Create a clean visual representation of the flow graph (matplotlib version)
        
        Args:
            pipeline_flow_result: Result from pipeline flow integration
            output_dir: Directory to save the file
            analysis_name: Name of the analysis
            timestamp: Optional timestamp to append to filename
            
        Returns:
            Path to the created file, or None if failed
        """
        try:
            if not pipeline_flow_result or pipeline_flow_result.get("status") != "success":
                self.logger.warning("No valid pipeline flow result for visualization")
                return None
            
            flow_graph_result = pipeline_flow_result["flow_graph_result"]
            flow_graph = flow_graph_result["flow_graph"]
            nodes = flow_graph["nodes"]
            edges = flow_graph["edges"]
            
            if not nodes:
                self.logger.warning("No nodes found in flow graph")
                return None
            
            # Create the graph
            G = nx.DiGraph()
            
            # Add nodes
            for node in nodes:
                G.add_node(
                    node["id"],
                    title=node["title"],
                    function=node["function"],
                    pipeline_type=node["pipeline_type"],
                    node_type=node["node_type"],
                    complexity=node["metadata"]["complexity_score"],
                    execution_time=node["metadata"]["estimated_execution_time"],
                    memory_usage=node["metadata"]["memory_usage"]
                )
            
            # Add edges
            for edge in edges:
                G.add_edge(
                    edge["from_node"],
                    edge["to_node"],
                    edge_type=edge["edge_type"],
                    data_flow=edge.get("data_flow", "")
                )
            
            # Create visualization
            plt.figure(figsize=(16, 12))
            plt.title(f"Pipeline Flow Graph - {analysis_name.replace('_', ' ').title()}", 
                     fontsize=16, fontweight='bold', pad=20)
            
            # Use hierarchical layout
            pos = nx.spring_layout(G, k=3, iterations=50)
            
            # Define colors for different pipeline types
            pipeline_colors = {
                'MetricsPipe': '#FF6B6B',      # Red
                'TimeSeriesPipe': '#4ECDC4',   # Teal
                'CohortPipe': '#45B7D1',       # Blue
                'TrendPipe': '#96CEB4',        # Green
                'SegmentPipe': '#FFEAA7',      # Yellow
                'RiskPipe': '#DDA0DD',         # Plum
                'AnomalyPipe': '#FFB347',      # Orange
                'OperationsPipe': '#98D8C8',   # Mint
                'MovingAggrPipe': '#F7DC6F',   # Light Yellow
                'FunnelPipe': '#BB8FCE'        # Light Purple
            }
            
            # Draw nodes
            node_colors = []
            node_sizes = []
            node_labels = {}
            
            for node_id in G.nodes():
                node_data = G.nodes[node_id]
                pipeline_type = node_data['pipeline_type']
                complexity = node_data['complexity']
                
                # Color based on pipeline type
                color = pipeline_colors.get(pipeline_type, '#CCCCCC')
                node_colors.append(color)
                
                # Size based on complexity
                size = 800 + (complexity * 1200)  # Base size + complexity scaling
                node_sizes.append(size)
                
                # Label with step number and function
                step_num = node_id.split('_')[1] if '_' in node_id else node_id
                node_labels[node_id] = f"Step {step_num}\n{node_data['function']}"
            
            # Draw the graph
            nx.draw_networkx_nodes(G, pos, 
                                  node_color=node_colors,
                                  node_size=node_sizes,
                                  alpha=0.8,
                                  edgecolors='black',
                                  linewidths=2)
            
            # Draw edges with different styles
            edge_colors = []
            edge_styles = []
            edge_widths = []
            
            for edge in G.edges():
                edge_data = G.edges[edge]
                edge_type = edge_data['edge_type']
                
                if edge_type == 'data_flow':
                    edge_colors.append('#2C3E50')
                    edge_styles.append('solid')
                    edge_widths.append(2)
                elif edge_type == 'dependency':
                    edge_colors.append('#E74C3C')
                    edge_styles.append('dashed')
                    edge_widths.append(1.5)
                else:
                    edge_colors.append('#7F8C8D')
                    edge_styles.append('dotted')
                    edge_widths.append(1)
            
            # Draw edges
            for i, (edge, color, style, width) in enumerate(zip(G.edges(), edge_colors, edge_styles, edge_widths)):
                nx.draw_networkx_edges(G, pos, 
                                     edgelist=[edge],
                                     edge_color=color,
                                     style=style,
                                     width=width,
                                     alpha=0.7,
                                     arrows=True,
                                     arrowsize=20,
                                     arrowstyle='->')
            
            # Draw labels
            nx.draw_networkx_labels(G, pos, 
                                   labels=node_labels,
                                   font_size=8,
                                   font_weight='bold',
                                   font_color='white')
            
            # Create legend
            legend_elements = []
            for pipeline_type, color in pipeline_colors.items():
                if any(node['pipeline_type'] == pipeline_type for node in nodes):
                    legend_elements.append(
                        mpatches.Patch(color=color, label=pipeline_type)
                    )
            
            # Add edge type legend
            legend_elements.extend([
                mpatches.Patch(color='#2C3E50', label='Data Flow'),
                mpatches.Patch(color='#E74C3C', label='Dependency'),
                mpatches.Patch(color='#7F8C8D', label='Other')
            ])
            
            plt.legend(handles=legend_elements, 
                      loc='upper left', 
                      bbox_to_anchor=(0, 1),
                      fontsize=10)
            
            # Add metadata text
            metadata_text = f"""
Flow Graph Metadata:
• Total Nodes: {len(nodes)}
• Total Edges: {len(edges)}
• Pipeline Types: {', '.join(flow_graph_result['metadata']['pipeline_types'])}
• Can Parallelize: {flow_graph_result['metadata']['can_parallelize']}
• Has Conditional Logic: {flow_graph_result['metadata']['has_conditional_logic']}
            """
            
            plt.figtext(0.02, 0.02, metadata_text, 
                       fontsize=9, 
                       verticalalignment='bottom',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
            
            plt.tight_layout()
            
            # Save the visualization
            vis_dir = os.path.join(output_dir, "flow_visualizations")
            os.makedirs(vis_dir, exist_ok=True)
            
            filename = f"{analysis_name}_flow_graph{'_' + timestamp if timestamp else ''}.png"
            filepath = os.path.join(vis_dir, filename)
            
            plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            
            self.logger.info(f"🎨 Flow visualization saved: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ Error creating flow visualization: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
