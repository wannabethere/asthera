"""
Pipeline Flow Integration Agent

This agent integrates the SelfCorrectingPipelineCodeGenerator with the FlowGraphGenerator
to provide a complete solution for generating separate step codes and flow graphs.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from .self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator
from .flow_graph_generator import FlowGraphGenerator

logger = logging.getLogger(__name__)

class PipelineFlowIntegrationAgent:
    """
    Integration agent that combines pipeline code generation with flow graph generation
    """
    
    def __init__(self, 
                 llm,
                 usage_examples_store,
                 code_examples_store, 
                 function_definition_store,
                 logical_reasoning_store=None,
                 function_retrieval=None,
                 retrieval_helper=None,
                 max_iterations: int = 3,
                 relevance_threshold: float = 0.7):
        """
        Initialize the integration agent
        
        Args:
            llm: Language model instance
            usage_examples_store: Store for usage examples
            code_examples_store: Store for code examples
            function_definition_store: Store for function definitions
            logical_reasoning_store: Store for logical reasoning examples
            function_retrieval: Function retrieval instance
            retrieval_helper: RetrievalHelper instance for accessing function definitions, examples, and insights
            max_iterations: Maximum iterations for self-correction
            relevance_threshold: Threshold for document relevance
        """
        self.pipeline_generator = SelfCorrectingPipelineCodeGenerator(
            llm=llm,
            usage_examples_store=usage_examples_store,
            code_examples_store=code_examples_store,
            function_definition_store=function_definition_store,
            logical_reasoning_store=logical_reasoning_store,
            function_retrieval=function_retrieval,
            retrieval_helper=retrieval_helper,
            max_iterations=max_iterations,
            relevance_threshold=relevance_threshold
        )
        
        self.flow_graph_generator = FlowGraphGenerator()
        
        self.logger = logging.getLogger(__name__)
    
    async def generate_pipeline_with_flow_graph(self, 
                                             context: str,
                                             function_name: Union[str, List[str]],
                                             function_inputs,
                                             dataframe_name: str = "df",
                                             classification: Optional[Union[Dict[str, Any], Any]] = None,
                                             dataset_description: Optional[str] = None,
                                             columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generate pipeline code with separate steps and flow graph
        
        Args:
            context: Natural language description of the task
            function_name: Fallback function(s) to use
            function_inputs: Extracted function inputs
            dataframe_name: Name of the dataframe variable
            classification: Optional classification results
            dataset_description: Optional description of the dataset
            columns_description: Optional dictionary mapping column names to descriptions
            
        Returns:
            Dictionary containing:
            - pipeline_result: Original pipeline generation result
            - flow_graph_result: Enhanced flow graph with analysis
            - integration_metadata: Metadata about the integration
        """
        try:
            self.logger.info("Starting integrated pipeline and flow graph generation")
            
            # Debug: Log input parameters
            self.logger.info(f"Context: {context}")
            self.logger.info(f"Function name: {function_name}")
            self.logger.info(f"Function inputs: {function_inputs}")
            self.logger.info(f"Dataframe name: {dataframe_name}")
            self.logger.info(f"Classification type: {type(classification)}")
            self.logger.info(f"Dataset description: {dataset_description}")
            self.logger.info(f"Columns description: {columns_description}")
            
            # Step 1: Generate pipeline code with separate steps
            self.logger.info("=== Step 1: Generating Pipeline Code ===")
            try:
                pipeline_result = await self.pipeline_generator.generate_pipeline_code(
                    context=context,
                    function_name=function_name,
                    function_inputs=function_inputs,
                    dataframe_name=dataframe_name,
                    classification=classification,
                    dataset_description=dataset_description,
                    columns_description=columns_description
                )
                self.logger.info("Pipeline generation completed successfully")
            except Exception as e:
                self.logger.error(f"Error in pipeline generation: {e}")
                self.logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            
            # Debug: Log pipeline result structure
            self.logger.info(f"Pipeline result type: {type(pipeline_result)}")
            self.logger.info(f"Pipeline result keys: {list(pipeline_result.keys()) if isinstance(pipeline_result, dict) else 'N/A'}")
            
            if isinstance(pipeline_result, dict):
                for key, value in pipeline_result.items():
                    self.logger.info(f"Pipeline result {key}: {type(value)} - {repr(value)[:200]}")
            
            self.logger.info(f"Pipeline generation completed:")
            self.logger.info(f"  - Status: {pipeline_result.get('status', 'unknown')}")
            self.logger.info(f"  - Steps: {len(pipeline_result.get('step_codes', []))}")
            self.logger.info(f"  - Flow graph nodes: {len(pipeline_result.get('flow_graph', {}).get('nodes', []))}")
            
            # Step 2: Generate enhanced flow graph
            self.logger.info("=== Step 2: Generating Enhanced Flow Graph ===")
            step_codes = pipeline_result.get('step_codes', [])
            self.logger.info(f"Pipeline result step_codes: {len(step_codes)} steps")
            self.logger.info(f"Pipeline result type: {type(pipeline_result)}")
            self.logger.info(f"Pipeline result keys: {list(pipeline_result.keys())}")
            
            if step_codes:
                self.logger.info(f"First step_codes type: {type(step_codes[0])}")
                self.logger.info(f"First step_codes: {step_codes[0]}")
                
                # Debug: Check each step code structure
                for i, step in enumerate(step_codes):
                    self.logger.info(f"Pipeline step {i} type: {type(step)}")
                    if isinstance(step, dict):
                        for key, value in step.items():
                            self.logger.info(f"Pipeline step {i} {key}: {type(value)} - {repr(value)[:100]}")
                    else:
                        self.logger.error(f"Pipeline step {i} is not a dict: {step}")
            
            self.logger.info("Calling flow_graph_generator.generate_flow_graph")
            
            # Debug: Check pipeline_result structure before calling flow graph generator
            self.logger.info("=== DEBUG: Pipeline Result Structure ===")
            self.logger.info(f"Pipeline result type: {type(pipeline_result)}")
            self.logger.info(f"Pipeline result keys: {list(pipeline_result.keys())}")
            
            # Debug: Check each key-value pair in pipeline_result
            for key, value in pipeline_result.items():
                self.logger.info(f"Pipeline result {key}: {type(value)} - {repr(value)[:200]}")
            
            # Debug: Check step_codes specifically
            if 'step_codes' in pipeline_result:
                step_codes = pipeline_result['step_codes']
                self.logger.info(f"Step codes type: {type(step_codes)}")
                self.logger.info(f"Step codes length: {len(step_codes) if isinstance(step_codes, list) else 'N/A'}")
                
                if isinstance(step_codes, list) and len(step_codes) > 0:
                    for i, step in enumerate(step_codes):
                        self.logger.info(f"Step {i} type: {type(step)}")
                        if isinstance(step, dict):
                            for step_key, step_value in step.items():
                                self.logger.info(f"Step {i} {step_key}: {type(step_value)} - {repr(step_value)[:100]}")
                        else:
                            self.logger.error(f"Step {i} is not a dict: {step}")
            
            # Debug: Check flow_graph specifically
            if 'flow_graph' in pipeline_result:
                flow_graph = pipeline_result['flow_graph']
                self.logger.info(f"Flow graph type: {type(flow_graph)}")
                self.logger.info(f"Flow graph keys: {list(flow_graph.keys()) if isinstance(flow_graph, dict) else 'N/A'}")
                
                if isinstance(flow_graph, dict):
                    for fg_key, fg_value in flow_graph.items():
                        self.logger.info(f"Flow graph {fg_key}: {type(fg_value)} - {repr(fg_value)[:100]}")
            
            # Debug: Check generated_code specifically
            if 'generated_code' in pipeline_result:
                generated_code = pipeline_result['generated_code']
                self.logger.info(f"Generated code type: {type(generated_code)}")
                self.logger.info(f"Generated code: {repr(generated_code)[:200]}")
            
            self.logger.info("=== END DEBUG: Pipeline Result Structure ===")
            
            try:
                flow_graph_result = self.flow_graph_generator.generate_flow_graph(pipeline_result)
                self.logger.info("Flow graph generation completed successfully")
            except Exception as e:
                self.logger.error(f"Error in flow_graph_generator.generate_flow_graph: {e}")
                self.logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            
            self.logger.info(f"Flow graph generation completed:")
            self.logger.info(f"  - Enhanced nodes: {flow_graph_result.get('metadata', {}).get('total_nodes', 0)}")
            self.logger.info(f"  - Enhanced edges: {flow_graph_result.get('metadata', {}).get('total_edges', 0)}")
            self.logger.info(f"  - Can parallelize: {flow_graph_result.get('metadata', {}).get('can_parallelize', False)}")
            
            # Step 3: Create integration metadata
            integration_metadata = self._create_integration_metadata(
                pipeline_result, flow_graph_result
            )
            
            # Step 4: Combine results
            result = {
                "pipeline_result": pipeline_result,
                "flow_graph_result": flow_graph_result,
                "integration_metadata": integration_metadata,
                "status": "success",
                "summary": {
                    "total_steps": len(pipeline_result.get('step_codes', [])),
                    "pipeline_types": flow_graph_result.get('metadata', {}).get('pipeline_types', []),
                    "functions_used": flow_graph_result.get('metadata', {}).get('functions_used', []),
                    "execution_complexity": self._assess_execution_complexity(flow_graph_result),
                    "optimization_opportunities": self._identify_optimization_opportunities(flow_graph_result)
                }
            }
            
            self.logger.info("Integration completed successfully")
            return result
            
        except Exception as e:
            
            self.logger.error(f"Error in integrated generation: {e}")
            return {
                "pipeline_result": {},
                "flow_graph_result": {},
                "integration_metadata": {},
                "status": "error",
                "error": str(e)
            }
    
    def _create_integration_metadata(self, pipeline_result: Dict[str, Any], 
                                   flow_graph_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create metadata about the integration process"""
        
        # Extract key metrics
        pipeline_steps = len(pipeline_result.get('step_codes', []))
        flow_nodes = flow_graph_result['metadata']['total_nodes']
        flow_edges = flow_graph_result['metadata']['total_edges']
        
        # Check consistency
        step_consistency = pipeline_steps == flow_nodes
        
        # Calculate complexity metrics
        complexity_metrics = self._calculate_complexity_metrics(flow_graph_result)
        
        # Identify integration issues
        integration_issues = []
        if not step_consistency:
            integration_issues.append("Step count mismatch between pipeline and flow graph")
        
        if flow_graph_result.get('dependency_analysis', {}).get('circular_dependencies'):
            integration_issues.append("Circular dependencies detected in flow graph")
        
        if flow_graph_result.get('dependency_analysis', {}).get('orphaned_nodes'):
            integration_issues.append("Orphaned nodes detected in flow graph")
        
        return {
            "pipeline_steps": pipeline_steps,
            "flow_nodes": flow_nodes,
            "flow_edges": flow_edges,
            "step_consistency": step_consistency,
            "complexity_metrics": complexity_metrics,
            "integration_issues": integration_issues,
            "has_issues": len(integration_issues) > 0,
            "integration_quality": self._assess_integration_quality(pipeline_result, flow_graph_result)
        }
    
    def _calculate_complexity_metrics(self, flow_graph_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate complexity metrics for the flow graph"""
        nodes = flow_graph_result['flow_graph']['nodes']
        
        if not nodes:
            return {"overall_complexity": 0, "max_complexity": 0, "avg_complexity": 0}
        
        complexity_scores = [node['metadata']['complexity_score'] for node in nodes]
        
        return {
            "overall_complexity": sum(complexity_scores) / len(complexity_scores),
            "max_complexity": max(complexity_scores),
            "min_complexity": min(complexity_scores),
            "high_complexity_steps": len([s for s in complexity_scores if s > 0.7]),
            "medium_complexity_steps": len([s for s in complexity_scores if 0.3 <= s <= 0.7]),
            "low_complexity_steps": len([s for s in complexity_scores if s < 0.3])
        }
    
    def _assess_integration_quality(self, pipeline_result: Dict[str, Any], 
                                  flow_graph_result: Dict[str, Any]) -> str:
        """Assess the quality of the integration"""
        quality_score = 0.0
        
        # Check pipeline success
        if pipeline_result.get('status') == 'success':
            quality_score += 0.3
        
        # Check step consistency
        pipeline_steps = len(pipeline_result.get('step_codes', []))
        flow_nodes = flow_graph_result['metadata']['total_nodes']
        if pipeline_steps == flow_nodes:
            quality_score += 0.2
        
        # Check for issues
        integration_issues = flow_graph_result.get('integration_metadata', {}).get('integration_issues', [])
        if not integration_issues:
            quality_score += 0.2
        
        # Check execution analysis
        execution_analysis = flow_graph_result.get('execution_analysis', {})
        if execution_analysis.get('critical_path'):
            quality_score += 0.1
        
        # Check data flow analysis
        data_flow_analysis = flow_graph_result.get('data_flow_analysis', {})
        if data_flow_analysis.get('data_transformations'):
            quality_score += 0.2
        
        if quality_score >= 0.8:
            return "excellent"
        elif quality_score >= 0.6:
            return "good"
        elif quality_score >= 0.4:
            return "fair"
        else:
            return "poor"
    
    def _assess_execution_complexity(self, flow_graph_result: Dict[str, Any]) -> str:
        """Assess the execution complexity of the pipeline"""
        metadata = flow_graph_result.get('metadata', {})
        complexity_metrics = flow_graph_result.get('integration_metadata', {}).get('complexity_metrics', {})
        
        # Factors affecting complexity
        total_steps = metadata.get('total_steps', 0)
        pipeline_types = len(metadata.get('pipeline_types', []))
        can_parallelize = metadata.get('can_parallelize', False)
        has_conditional = metadata.get('has_conditional_logic', False)
        
        # Calculate complexity score
        complexity_score = 0
        
        # Step count complexity
        if total_steps > 10:
            complexity_score += 3
        elif total_steps > 5:
            complexity_score += 2
        elif total_steps > 2:
            complexity_score += 1
        
        # Pipeline type diversity
        if pipeline_types > 3:
            complexity_score += 2
        elif pipeline_types > 1:
            complexity_score += 1
        
        # Parallel execution
        if can_parallelize:
            complexity_score += 1
        
        # Conditional logic
        if has_conditional:
            complexity_score += 2
        
        # Overall complexity assessment
        if complexity_score >= 6:
            return "high"
        elif complexity_score >= 3:
            return "medium"
        else:
            return "low"
    
    def _identify_optimization_opportunities(self, flow_graph_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify optimization opportunities in the flow graph"""
        opportunities = []
        
        # Check for parallel execution opportunities
        execution_analysis = flow_graph_result.get('execution_analysis', {})
        if execution_analysis.get('can_parallelize'):
            opportunities.append({
                "type": "parallel_execution",
                "description": "Some steps can be executed in parallel",
                "impact": "high",
                "effort": "medium"
            })
        
        # Check for bottlenecks
        data_flow_analysis = flow_graph_result.get('data_flow_analysis', {})
        bottlenecks = data_flow_analysis.get('bottlenecks', [])
        if bottlenecks:
            opportunities.append({
                "type": "bottleneck_optimization",
                "description": f"Found {len(bottlenecks)} potential bottlenecks",
                "impact": "high",
                "effort": "high"
            })
        
        # Check for circular dependencies
        dependency_analysis = flow_graph_result.get('dependency_analysis', {})
        circular_deps = dependency_analysis.get('circular_dependencies', [])
        if circular_deps:
            opportunities.append({
                "type": "dependency_optimization",
                "description": f"Found {len(circular_deps)} circular dependencies",
                "impact": "high",
                "effort": "high"
            })
        
        # Check for orphaned nodes
        orphaned_nodes = dependency_analysis.get('orphaned_nodes', [])
        if orphaned_nodes:
            opportunities.append({
                "type": "cleanup",
                "description": f"Found {len(orphaned_nodes)} orphaned nodes",
                "impact": "medium",
                "effort": "low"
            })
        
        return opportunities
    
    async def generate_step_execution_plan(self, flow_graph_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an execution plan for the individual steps
        
        Args:
            flow_graph_result: Result from flow graph generation
            
        Returns:
            Execution plan with step ordering and parallel execution groups
        """
        try:
            execution_analysis = flow_graph_result.get('execution_analysis', {})
            flow_graph = flow_graph_result.get('flow_graph', {})
            nodes = flow_graph.get('nodes', [])
            
            # Create execution plan
            execution_plan = {
                "sequential_steps": execution_analysis.get('execution_order', []),
                "parallel_groups": execution_analysis.get('parallel_opportunities', []),
                "critical_path": execution_analysis.get('critical_path', []),
                "step_details": {}
            }
            
            # Add detailed step information
            for node in nodes:
                execution_plan["step_details"][node["id"]] = {
                    "title": node["title"],
                    "function": node["function"],
                    "pipeline_type": node["pipeline_type"],
                    "execution_order": node["step_number"],
                    "dependencies": node["dependencies"],
                    "estimated_time": node["metadata"]["estimated_execution_time"],
                    "memory_usage": node["metadata"]["memory_usage"],
                    "complexity_score": node["metadata"]["complexity_score"],
                    "code": node["code"]
                }
            
            # Add execution recommendations
            execution_plan["recommendations"] = self._generate_execution_recommendations(flow_graph_result)
            
            return execution_plan
            
        except Exception as e:
            self.logger.error(f"Error generating execution plan: {e}")
            return {"error": str(e)}
    
    def _generate_execution_recommendations(self, flow_graph_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate execution recommendations based on flow graph analysis"""
        recommendations = []
        
        metadata = flow_graph_result.get('metadata', {})
        execution_analysis = flow_graph_result.get('execution_analysis', {})
        
        # Parallel execution recommendation
        if execution_analysis.get('can_parallelize'):
            recommendations.append({
                "type": "parallel_execution",
                "priority": "high",
                "description": "Consider executing independent steps in parallel to improve performance",
                "steps": execution_analysis.get('parallel_opportunities', [])
            })
        
        # Memory optimization recommendation
        nodes = flow_graph_result.get('flow_graph', {}).get('nodes', [])
        high_memory_nodes = [node for node in nodes if node['metadata']['memory_usage'] == 'high']
        if high_memory_nodes:
            recommendations.append({
                "type": "memory_optimization",
                "priority": "medium",
                "description": "Consider optimizing high memory usage steps",
                "steps": [node['id'] for node in high_memory_nodes]
            })
        
        # Complexity optimization recommendation
        high_complexity_nodes = [node for node in nodes if node['metadata']['complexity_score'] > 0.7]
        if high_complexity_nodes:
            recommendations.append({
                "type": "complexity_optimization",
                "priority": "medium",
                "description": "Consider breaking down high complexity steps",
                "steps": [node['id'] for node in high_complexity_nodes]
            })
        
        return recommendations
