"""
Example demonstrating the new pipeline flow generation functionality

This example shows how to use the PipelineFlowIntegrationAgent to generate
separate step codes and flow graphs for data analysis pipelines.
"""

import asyncio
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock classes for demonstration (in real usage, these would be actual implementations)
class MockLLM:
    def __init__(self):
        pass

class MockStore:
    def __init__(self):
        pass

class MockAnalysisIntentResult:
    def __init__(self):
        self.intent_type = "time_series_analysis"
        self.confidence_score = 0.85
        self.rephrased_question = "Analyze variance over time with moving averages"
        self.reasoning = "User wants to understand variance patterns over time"
        self.suggested_functions = ["variance_analysis", "moving_apply_by_group"]
        self.required_data_columns = ["value", "date", "group"]
        self.missing_columns = []
        self.can_be_answered = True
        self.feasibility_score = 0.9
        self.clarification_needed = None
        self.reasoning_plan = [
            {
                "step_number": 1,
                "step_title": "Calculate Basic Variance",
                "step_description": "Calculate variance for the value column",
                "function_name": "variance",
                "pipeline_name": "MetricsPipe",
                "input_processing": "Prepare data with value column",
                "parameter_mapping": {"variable": "value"},
                "expected_output": "Variance values for the value column",
                "data_requirements": ["value"],
                "considerations": "Handle missing values",
                "merge_with_previous": False,
                "embedded_function_parameter": False,
                "embedded_function_details": None,
                "column_mapping": {"variable": "value"},
                "output_columns": ["variance_value"],
                "input_columns": ["value"],
                "step_dependencies": [],
                "data_flow": "Initial data input",
                "embedded_function_columns": None,
                "pipeline_type": "MetricsPipe",
                "function_category": "basic_metrics",
                "parameter_constraints": {},
                "error_handling": "Handle missing values"
            },
            {
                "step_number": 2,
                "step_title": "Apply Moving Variance by Group",
                "step_description": "Apply moving variance calculation by group over time",
                "function_name": "moving_apply_by_group",
                "pipeline_name": "MovingAggrPipe",
                "input_processing": "Prepare time series data with group columns",
                "parameter_mapping": "Map columns to function parameters, embed Variance as function parameter",
                "expected_output": "Rolling variance values by group over time",
                "data_requirements": ["value", "group", "date"],
                "considerations": "Ensure proper time column format and handle missing values",
                "merge_with_previous": False,
                "embedded_function_parameter": True,
                "embedded_function_details": {
                    "embedded_function": "variance",
                    "embedded_parameters": {"column": "value"},
                    "embedded_output": "variance_value"
                },
                "column_mapping": {
                    "columns": "value",
                    "group_column": "group",
                    "time_column": "date",
                    "window": 5,
                    "min_periods": 1,
                    "output_suffix": "_rolling_variance"
                },
                "output_columns": ["value_rolling_variance"],
                "input_columns": ["value", "group", "date"],
                "step_dependencies": [1],
                "data_flow": "Uses variance calculation from step 1",
                "embedded_function_columns": {
                    "embedded_input_columns": ["value"],
                    "embedded_output_columns": ["variance_value"]
                },
                "pipeline_type": "TimeSeriesPipe",
                "function_category": "time_aggregation",
                "parameter_constraints": {
                    "window": "must be positive integer",
                    "min_periods": "must be positive integer <= window"
                },
                "error_handling": "Handle missing values in group columns, validate time column format"
            }
        ]
        self.retrieved_functions = [
            {"function_name": "variance", "description": "Calculate variance"},
            {"function_name": "moving_apply_by_group", "description": "Apply function by group over time"}
        ]

async def demonstrate_pipeline_flow_generation():
    """Demonstrate the new pipeline flow generation functionality"""
    
    print("🚀 Pipeline Flow Generation Demo")
    print("=" * 50)
    
    # Create mock instances (in real usage, these would be actual implementations)
    llm = MockLLM()
    usage_examples_store = MockStore()
    code_examples_store = MockStore()
    function_definition_store = MockStore()
    
    # Import the integration agent
    try:
        from app.agents.nodes.mlagents.pipeline_flow_integration import PipelineFlowIntegrationAgent
        
        # Initialize the integration agent
        agent = PipelineFlowIntegrationAgent(
            llm=llm,
            usage_examples_store=usage_examples_store,
            code_examples_store=code_examples_store,
            function_definition_store=function_definition_store
        )
        
        # Example context and parameters
        context = "Analyze variance over time with moving averages by group"
        function_name = ["variance", "moving_apply_by_group"]
        function_inputs = {"variable": "value", "group_column": "group", "time_column": "date"}
        dataframe_name = "df"
        classification = MockAnalysisIntentResult()
        dataset_description = "Time series data with value, group, and date columns"
        columns_description = {
            "value": "Numeric value to analyze",
            "group": "Grouping dimension",
            "date": "Time dimension"
        }
        
        print("📊 Generating Pipeline with Flow Graph...")
        print(f"Context: {context}")
        print(f"Dataframe: {dataframe_name}")
        print(f"Functions: {function_name}")
        print()
        
        # Generate pipeline with flow graph
        result = await agent.generate_pipeline_with_flow_graph(
            context=context,
            function_name=function_name,
            function_inputs=function_inputs,
            dataframe_name=dataframe_name,
            classification=classification,
            dataset_description=dataset_description,
            columns_description=columns_description
        )
        
        # Display results
        print("✅ Generation Complete!")
        print("=" * 50)
        
        # Show pipeline result
        pipeline_result = result["pipeline_result"]
        print("📋 Pipeline Result:")
        print(f"  Status: {pipeline_result['status']}")
        print(f"  Iterations: {pipeline_result['iterations']}")
        print(f"  Function: {pipeline_result['function_name']}")
        print(f"  Pipeline Type: {pipeline_result['pipeline_type']}")
        print()
        
        # Show step codes
        step_codes = pipeline_result.get("step_codes", [])
        print(f"🔧 Individual Step Codes ({len(step_codes)} steps):")
        for i, step in enumerate(step_codes, 1):
            print(f"  Step {i}: {step['title']}")
            print(f"    Function: {step['function']}")
            print(f"    Pipeline Type: {step['pipeline_type']}")
            print(f"    Input: {step['input_dataframe']} -> Output: {step['output_dataframe']}")
            print(f"    Dependencies: {step['dependencies']}")
            print(f"    Code Preview: {step['code'][:100]}...")
            print()
        
        # Show flow graph result
        flow_graph_result = result["flow_graph_result"]
        print("🕸️  Flow Graph Analysis:")
        metadata = flow_graph_result["metadata"]
        print(f"  Total Nodes: {metadata['total_nodes']}")
        print(f"  Total Edges: {metadata['total_edges']}")
        print(f"  Pipeline Types: {metadata['pipeline_types']}")
        print(f"  Functions Used: {metadata['functions_used']}")
        print(f"  Can Parallelize: {metadata['can_parallelize']}")
        print(f"  Has Conditional Logic: {metadata['has_conditional_logic']}")
        print()
        
        # Show execution analysis
        execution_analysis = flow_graph_result["execution_analysis"]
        print("⚡ Execution Analysis:")
        print(f"  Execution Order: {execution_analysis['execution_order']}")
        print(f"  Critical Path: {execution_analysis['critical_path']}")
        print(f"  Parallel Opportunities: {len(execution_analysis['parallel_opportunities'])} groups")
        print()
        
        # Show dependency analysis
        dependency_analysis = flow_graph_result["dependency_analysis"]
        print("🔗 Dependency Analysis:")
        print(f"  Circular Dependencies: {len(dependency_analysis['circular_dependencies'])}")
        print(f"  Orphaned Nodes: {len(dependency_analysis['orphaned_nodes'])}")
        print(f"  Max Dependency Depth: {dependency_analysis['max_dependency_depth']}")
        print()
        
        # Show data flow analysis
        data_flow_analysis = flow_graph_result["data_flow_analysis"]
        print("📊 Data Flow Analysis:")
        print(f"  Data Transformations: {data_flow_analysis['total_transformations']}")
        print(f"  Bottlenecks: {len(data_flow_analysis['bottlenecks'])}")
        print()
        
        # Show integration metadata
        integration_metadata = result["integration_metadata"]
        print("🔧 Integration Metadata:")
        print(f"  Pipeline Steps: {integration_metadata['pipeline_steps']}")
        print(f"  Flow Nodes: {integration_metadata['flow_nodes']}")
        print(f"  Step Consistency: {integration_metadata['step_consistency']}")
        print(f"  Integration Quality: {integration_metadata['integration_quality']}")
        print(f"  Has Issues: {integration_metadata['has_issues']}")
        if integration_metadata['integration_issues']:
            print(f"  Issues: {integration_metadata['integration_issues']}")
        print()
        
        # Show summary
        summary = result["summary"]
        print("📈 Summary:")
        print(f"  Total Steps: {summary['total_steps']}")
        print(f"  Pipeline Types: {summary['pipeline_types']}")
        print(f"  Functions Used: {summary['functions_used']}")
        print(f"  Execution Complexity: {summary['execution_complexity']}")
        print(f"  Optimization Opportunities: {len(summary['optimization_opportunities'])}")
        print()
        
        # Show optimization opportunities
        if summary['optimization_opportunities']:
            print("🎯 Optimization Opportunities:")
            for opp in summary['optimization_opportunities']:
                print(f"  - {opp['type']}: {opp['description']} (Impact: {opp['impact']}, Effort: {opp['effort']})")
            print()
        
        # Generate execution plan
        print("📋 Generating Execution Plan...")
        execution_plan = await agent.generate_step_execution_plan(flow_graph_result)
        
        if "error" not in execution_plan:
            print("✅ Execution Plan Generated:")
            print(f"  Sequential Steps: {execution_plan['sequential_steps']}")
            print(f"  Parallel Groups: {execution_plan['parallel_groups']}")
            print(f"  Critical Path: {execution_plan['critical_path']}")
            print(f"  Recommendations: {len(execution_plan['recommendations'])}")
            print()
            
            # Show step details
            print("🔍 Step Details:")
            for step_id, details in execution_plan['step_details'].items():
                print(f"  {step_id}: {details['title']}")
                print(f"    Function: {details['function']}")
                print(f"    Pipeline Type: {details['pipeline_type']}")
                print(f"    Execution Order: {details['execution_order']}")
                print(f"    Dependencies: {details['dependencies']}")
                print(f"    Estimated Time: {details['estimated_time']}")
                print(f"    Memory Usage: {details['memory_usage']}")
                print(f"    Complexity Score: {details['complexity_score']:.2f}")
                print()
        
        print("🎉 Demo Complete!")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure the pipeline_flow_integration module is properly installed.")
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Error in demonstration")

def demonstrate_flow_graph_structure():
    """Demonstrate the structure of the flow graph"""
    
    print("\n🕸️  Flow Graph Structure Demo")
    print("=" * 50)
    
    # Example flow graph structure
    example_flow_graph = {
        "nodes": [
            {
                "id": "step_1",
                "title": "Calculate Basic Variance",
                "node_type": "processing",
                "function": "variance",
                "pipeline_type": "MetricsPipe",
                "input_dataframe": "df",
                "output_dataframe": "step_1_result",
                "dependencies": [],
                "input_columns": ["value"],
                "output_columns": ["variance_value"],
                "code": "# Calculate Basic Variance\nstep_1_result = (\n    MetricsPipe.from_dataframe(df)\n    | variance(variable='value')\n    ).to_df()",
                "metadata": {
                    "execution_order": 1,
                    "complexity_score": 0.3,
                    "estimated_execution_time": "fast",
                    "memory_usage": "medium"
                }
            },
            {
                "id": "step_2",
                "title": "Apply Moving Variance by Group",
                "node_type": "processing",
                "function": "moving_apply_by_group",
                "pipeline_type": "TimeSeriesPipe",
                "input_dataframe": "step_1_result",
                "output_dataframe": "step_2_result",
                "dependencies": ["step_1"],
                "input_columns": ["value", "group", "date"],
                "output_columns": ["value_rolling_variance"],
                "code": "# Apply Moving Variance by Group\nstep_2_result = (\n    TimeSeriesPipe.from_dataframe(step_1_result)\n    | moving_apply_by_group(\n        columns='value',\n        group_column='group',\n        time_column='date',\n        function=variance,\n        window=5,\n        min_periods=1,\n        output_suffix='_rolling_variance'\n    )\n    ).to_df()",
                "metadata": {
                    "execution_order": 2,
                    "complexity_score": 0.7,
                    "estimated_execution_time": "slow",
                    "memory_usage": "high"
                }
            }
        ],
        "edges": [
            {
                "from_node": "step_1",
                "to_node": "step_2",
                "edge_type": "data_flow",
                "data_flow": "step_1_result -> step_2_input",
                "metadata": {
                    "flow_type": "sequential",
                    "is_critical": True
                }
            }
        ],
        "metadata": {
            "total_steps": 2,
            "pipeline_types": ["MetricsPipe", "TimeSeriesPipe"],
            "functions_used": ["variance", "moving_apply_by_group"]
        }
    }
    
    print("📊 Example Flow Graph Structure:")
    print(f"  Nodes: {len(example_flow_graph['nodes'])}")
    print(f"  Edges: {len(example_flow_graph['edges'])}")
    print()
    
    print("🔗 Node Details:")
    for node in example_flow_graph['nodes']:
        print(f"  {node['id']}: {node['title']}")
        print(f"    Type: {node['node_type']}")
        print(f"    Function: {node['function']}")
        print(f"    Pipeline: {node['pipeline_type']}")
        print(f"    Input: {node['input_dataframe']} -> Output: {node['output_dataframe']}")
        print(f"    Dependencies: {node['dependencies']}")
        print(f"    Complexity: {node['metadata']['complexity_score']}")
        print()
    
    print("🔗 Edge Details:")
    for edge in example_flow_graph['edges']:
        print(f"  {edge['from_node']} -> {edge['to_node']}")
        print(f"    Type: {edge['edge_type']}")
        print(f"    Data Flow: {edge['data_flow']}")
        print(f"    Critical: {edge['metadata']['is_critical']}")
        print()

if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_pipeline_flow_generation())
    
    # Show flow graph structure
    demonstrate_flow_graph_structure()
