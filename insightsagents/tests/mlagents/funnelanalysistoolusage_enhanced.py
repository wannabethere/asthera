import pandas as pd
import asyncio
import os
import numpy as np
from datetime import datetime, timedelta
import chromadb
from langchain_openai import ChatOpenAI
from app.storage.documents import DocumentChromaStore, create_langchain_doc_util
from app.core.settings import get_settings
from app.agents.nodes.mlagents.funnelanalysis_node import FunnelAnalysisAgent,retrieve_function_definition, retrieve_function_examples
from app.agents.nodes.mlagents.selfrag_mltool_pipeline import SelfCorrectingForwardPlanner
from app.agents.nodes.recommenders.ds_agents import SummarizeDatasetAgent
from app.agents.models.dsmodels import InsightManagerState
from app.agents.nodes.mlagents.analysis_intent_classification_simplified import SimplifiedAnalysisIntentPlanner
from app.agents.nodes.mlagents.pipeline_flow_integration import PipelineFlowIntegrationAgent
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper
import json
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH

# Output configuration
OUTPUT_CONFIG = {
    "save_to_json": True,           # Save results to JSON files
    "save_individual_files": True,   # Save individual analysis files
    "output_directory": "analysis_results",  # Directory to save files
    "include_timestamp": True,       # Include timestamp in filenames
    "create_summary": True,          # Create summary text file
    "console_output": True,          # Also show results in console
    "file_encoding": "utf-8",       # File encoding for output files
    "extract_generated_code": True,  # Extract generated code to Python files
    "code_output_directory": "generated_code",  # Directory for generated Python code
    "create_flow_visualization": True,  # Create flow graph visualization
    "visualization_output_directory": "flow_visualizations",  # Directory for flow visualizations
    "create_mermaid_charts": True,  # Create Mermaid charts
    "mermaid_output_directory": "mermaid_charts"  # Directory for Mermaid charts
}

os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
# Use the same ChromaDB path as RetrievalHelper
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH+"/enhanced_comprehensive_registry"
# Initialize ChromaDB client and collections
client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
collection_name = "comprehensive_ml_functions_demo"
# Define collection names for different data types
# Note: These must match the collection names expected by RetrievalHelper
collection_names = {
    'unified': collection_name,
    'toolspecs': f"{collection_name}_toolspecs",  # Enhanced collection with detailed parameters
    'instructions': f"{collection_name}_instructions",  # Enhanced collection with detailed parameters
    'usage_examples': f"{collection_name}_usage_examples",  # Enhanced collection with detailed parameters
    'code_examples': f"{collection_name}_code_examples",
    'code': f"{collection_name}_code"
}

# Initialize separate document stores for each collection type (excluding unified)
document_stores = {}
for collection_type, full_collection_name in collection_names.items():
    if collection_type != 'unified':  # Skip unified collection, use parent's document_store
        print(f"Initializing document store for collection: {full_collection_name}")
        try:
            document_stores[full_collection_name] = DocumentChromaStore(
                persistent_client=client,
                collection_name=full_collection_name,
                tf_idf=False  # Disable TF-IDF to avoid UUID collection issues
            )
            print(f"Successfully initialized document store for: {full_collection_name}")
        except Exception as e:
            print(f"Failed to initialize document store for {full_collection_name}: {e}")
            raise

#examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_examples_collection")
#functions_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_spec_collection")
#insights_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="tools_insights_collection")
#usage_examples_vectorstore = DocumentChromaStore(persistent_client=client, collection_name="usage_examples_collection")

# Use the base collection name to access the document stores
# Note: These must match the collection names expected by RetrievalHelper
examples_vectorstore = document_stores[f'{collection_name}_code_examples']
functions_vectorstore = document_stores[f'{collection_name}_toolspecs']  # Enhanced collection with detailed parameters
insights_vectorstore = document_stores[f'{collection_name}_instructions']  # Enhanced collection with detailed parameters
usage_examples_vectorstore = document_stores[f'{collection_name}_usage_examples']  # Enhanced collection with detailed parameters
# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
retrieval_helper = RetrievalHelper()

# Initialize the pipeline flow integration agent
pipeline_flow_agent = PipelineFlowIntegrationAgent(
    llm=llm,
    usage_examples_store=usage_examples_vectorstore,
    code_examples_store=examples_vectorstore,
    function_definition_store=functions_vectorstore,
    retrieval_helper=retrieval_helper
)

# Initialize the simplified intent planner
planner = SimplifiedAnalysisIntentPlanner(
    llm=llm,
    retrieval_helper=retrieval_helper
)

def analyze_question_with_pipeline_flow(
    question: str,
    dataframe: pd.DataFrame,
    dataframe_description: str = None,
    dataframe_summary: str = None,
    columns_description: dict = None,
    context: str = None,
    dataframe_name: str = "Dataset"
):
    """
    Analyze a question using pipeline flow integration with separate step codes and flow graphs.
    
    Args:
        question (str): The question to analyze
        dataframe (pd.DataFrame): The dataframe to analyze
        dataframe_description (str, optional): Description of the dataframe
        dataframe_summary (str, optional): Summary of the dataframe
        columns_description (dict, optional): Description of each column
        context (str, optional): Additional context for code generation
        dataframe_name (str): Name of the dataframe for code generation
    
    Returns:
        dict: Analysis results including pipeline flow with separate step codes and flow graphs
    """
    print(f"\n{'='*80}")
    print(f"🔍 ANALYZING QUESTION: {question}")
    print(f"{'='*80}")
    
    # Initialize function retrieval
    retrieval = FunctionRetrieval(
        llm=llm,
        function_library_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/all_pipes_functions.json"
    )
    retrieval_result = asyncio.run(retrieval.retrieve_relevant_functions(
        question, dataframe_description, dataframe_summary, columns_description
    ))
    print(f"📋 Retrieved {len(retrieval_result.top_functions)} relevant functions")
    
    # If dataframe description/summary not provided, generate them
    if dataframe_description is None or dataframe_summary is None:
        print("📊 Generating dataframe summary...")
        summarize_agent = SummarizeDatasetAgent()
        state = InsightManagerState(
            question=question,
            context="Data analysis request",
            goal="Generate insights from the dataset",
            dataset_path=""
        )
        dataframe_summary = summarize_agent.summarize_dataframe(
            dataframe=dataframe, 
            question=question, 
            state=state
        )
        dataframe_description = dataframe_description or "Dataset for analysis"
    
    # Classify intent
    print("🎯 Classifying intent...")
    intent_result = asyncio.run(planner.classify_intent(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=dataframe.columns.tolist()
    ))
    
    # Print intent classification results
    print(f"\n📈 Intent Classification Results:")
    print(f"  ✅ Feasibility Score: {intent_result.get('feasibility_score', 0.0)}")
    print(f"  ✅ Can be answered: {intent_result.get('can_be_answered', False)}")
    print(f"  📊 Missing columns: {intent_result.get('missing_columns', [])}")
    print(f"  🔧 Suggested functions: {intent_result.get('suggested_functions', [])}")
    print(f"  📋 Reasoning plan steps: {len(intent_result.get('reasoning_plan', []))}")
    print(f"  📋 Pipeline plan steps: {len(intent_result.get('pipeline_reasoning_plan', []))}")
    
    if not intent_result.get('can_be_answered', False):
        print("❌ Question cannot be answered with available data")
        return {
            "question": question,
            "intent_classification": intent_result,
            "pipeline_flow_result": None,
            "error": "Question cannot be answered with available data"
        }
    
    # Generate pipeline with flow graph
    print("\n🚀 Generating Pipeline with Flow Graph...")
    try:
        # Extract function names from suggested functions
        function_names = []
        suggested_functions = intent_result.get('suggested_functions', [])
        if suggested_functions:
            for func in suggested_functions:
                if ': ' in func:
                    function_name = func.split(': ')[0]
                    function_names.append(function_name)
                else:
                    function_names.append(func)
        
        # Create enhanced columns description
        enhanced_columns_description = columns_description or {}
        reasoning_plan = intent_result.get('reasoning_plan', [])
        pipeline_reasoning_plan = intent_result.get('pipeline_reasoning_plan', [])
        
        if reasoning_plan and isinstance(reasoning_plan, list):
            enhanced_columns_description['_enhanced_metadata'] = {
                'reasoning_plan_steps': len(reasoning_plan),
                'pipeline_plan_steps': len(pipeline_reasoning_plan),
                'has_enhanced_metadata': any(
                    step.get('column_mapping') or step.get('input_columns') or step.get('output_columns')
                    for step in pipeline_reasoning_plan if isinstance(step, dict)
                ),
                'pipeline_types': list(set(
                    step.get('pipeline_type') for step in pipeline_reasoning_plan 
                    if isinstance(step, dict) and step.get('pipeline_type')
                )),
                'function_categories': list(set(
                    step.get('function_category') for step in pipeline_reasoning_plan 
                    if isinstance(step, dict) and step.get('function_category')
                ))
            }
        
        # Generate pipeline with flow graph
        pipeline_flow_result = asyncio.run(pipeline_flow_agent.generate_pipeline_with_flow_graph(
            context=context or question,
            function_name=function_names,
            function_inputs=intent_result.get('required_data_columns', []),
            dataframe_name=dataframe_name,
            classification=intent_result,
            dataset_description=dataframe_summary,
            columns_description=enhanced_columns_description
        ))
        
        print("✅ Pipeline flow generation completed successfully!")
        
        # Display results summary
        if pipeline_flow_result["status"] == "success":
            pipeline_result = pipeline_flow_result["pipeline_result"]
            flow_graph_result = pipeline_flow_result["flow_graph_result"]
            
            print(f"\n📊 Pipeline Flow Summary:")
            print(f"  🔧 Total Steps: {len(pipeline_result.get('step_codes', []))}")
            print(f"  🕸️  Flow Graph Nodes: {flow_graph_result['metadata']['total_nodes']}")
            print(f"  🔗 Flow Graph Edges: {flow_graph_result['metadata']['total_edges']}")
            print(f"  ⚡ Can Parallelize: {flow_graph_result['metadata']['can_parallelize']}")
            print(f"  🎯 Pipeline Types: {flow_graph_result['metadata']['pipeline_types']}")
            
            # Display step details
            step_codes = pipeline_result.get('step_codes', [])
            if step_codes:
                print(f"\n🔧 Individual Step Details:")
                for i, step in enumerate(step_codes, 1):
                    print(f"  Step {i}: {step['title']}")
                    print(f"    Function: {step['function']}")
                    print(f"    Pipeline Type: {step['pipeline_type']}")
                    print(f"    Input: {step['input_dataframe']} -> Output: {step['output_dataframe']}")
                    print(f"    Dependencies: {step['dependencies']}")
        
        return {
            "question": question,
            "intent_classification": intent_result,
            "pipeline_flow_result": pipeline_flow_result,
            "dataframe_info": {
                "shape": dataframe.shape,
                "columns": dataframe.columns.tolist(),
                "summary": dataframe_summary
            }
        }
        
    except Exception as e:
        print(f"❌ Error during pipeline flow generation: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "question": question,
            "intent_classification": intent_result,
            "pipeline_flow_result": None,
            "error": str(e)
        }

def create_mermaid_visualization(pipeline_flow_result, output_dir, analysis_name, timestamp=""):
    """
    Create a Mermaid chart visualization of the flow graph
    """
    try:
        if not pipeline_flow_result or pipeline_flow_result.get("status") != "success":
            print("⚠️  No valid pipeline flow result for Mermaid visualization")
            return None
        
        flow_graph_result = pipeline_flow_result["flow_graph_result"]
        mermaid_chart = flow_graph_result.get("mermaid_chart", "")
        step_details = flow_graph_result.get("step_details", {})
        
        if not mermaid_chart:
            print("⚠️  No Mermaid chart found in flow graph result")
            return None
        
        # Create Mermaid directory
        mermaid_dir = os.path.join(output_dir, "mermaid_charts")
        os.makedirs(mermaid_dir, exist_ok=True)
        
        # Save Mermaid chart
        filename = f"{analysis_name}_flow_chart{'_' + timestamp if timestamp else ''}.mmd"
        filepath = os.path.join(mermaid_dir, filename)
        
        with open(filepath, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as f:
            f.write(f'%% Flow Chart for {analysis_name.replace("_", " ").title()}\n')
            f.write(f'%% Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
            f.write(mermaid_chart)
        
        print(f"🎨 Mermaid chart saved: {filepath}")
        
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
        
        with open(html_filepath, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as f:
            f.write(html_content)
        
        print(f"🌐 Interactive HTML chart saved: {html_filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Error creating Mermaid visualization: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

def create_flow_visualization(pipeline_flow_result, output_dir, analysis_name, timestamp=""):
    """
    Create a clean visual representation of the flow graph (matplotlib version)
    """
    try:
        if not pipeline_flow_result or pipeline_flow_result.get("status") != "success":
            print("⚠️  No valid pipeline flow result for visualization")
            return None
        
        flow_graph_result = pipeline_flow_result["flow_graph_result"]
        flow_graph = flow_graph_result["flow_graph"]
        nodes = flow_graph["nodes"]
        edges = flow_graph["edges"]
        
        if not nodes:
            print("⚠️  No nodes found in flow graph")
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
        vis_dir = os.path.join(output_dir, OUTPUT_CONFIG["visualization_output_directory"])
        os.makedirs(vis_dir, exist_ok=True)
        
        filename = f"{analysis_name}_flow_graph{'_' + timestamp if timestamp else ''}.png"
        filepath = os.path.join(vis_dir, filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"🎨 Flow visualization saved: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Error creating flow visualization: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

def create_comprehensive_flow_file(pipeline_flow_result, output_dir, analysis_name, timestamp=""):
    """
    Create a comprehensive single file with all flow information
    """
    try:
        if not pipeline_flow_result or pipeline_flow_result.get("status") != "success":
            print("⚠️  No valid pipeline flow result for comprehensive file")
            return None
        
        pipeline_result = pipeline_flow_result["pipeline_result"]
        flow_graph_result = pipeline_flow_result["flow_graph_result"]
        integration_metadata = pipeline_flow_result["integration_metadata"]
        
        # Create comprehensive flow file
        filename = f"{analysis_name}_comprehensive_flow{'_' + timestamp if timestamp else ''}.py"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as f:
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
                
                f.write(f'        return step_{i}_result\n')
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
        
        print(f"📄 Comprehensive flow file saved: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Error creating comprehensive flow file: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

def main():
    print("🚀 Enhanced Funnel Analysis Tool with Pipeline Flow Integration")
    print("=" * 80)
    
    # Load data
    po_df = pd.read_csv("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv")
    print(f"📊 Loaded dataset with shape: {po_df.shape}")
    
    # Initialize summarization agent
    summarize_agent = SummarizeDatasetAgent()
    
    # Define analysis questions
    analysis_questions = [
         {
            "name": "rolling_variance_analysis",
            "question": "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            "context": "Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment"
        },
        {
            "name": "rolling_variance_analysis",
            "question": "What are the daily total transactional values for purchase orders by projects, region and departments",
            "context": "Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment"
        },
        {
            "name": "anomaly_detection",
            "question": "Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
            "context": "Find anomalies in daily spending patterns"
        },
       
        {
            "name": "mean_transactional_values",
            "question": "What are the mean, average daily transactional values for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "daily_trends_forecast",
            "question": "What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "distribution_analysis",
            "question": "What is the distribution of the mean daily transactional values for each type of source by region and project daily?",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "flux_analysis",
            "question": "Perform rolling 5 day mean transactiona values, forecasted values. Using those perform flux analysis by calculating the variance for the mean transactional values, forecasted values by region,cost center, and project",
            "context": "Calculate mean daily transactional values"
        }
         
    ]
    """
        {
            "name": "anomaly_detection",
            "question": "Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
            "context": "Find anomalies in daily spending patterns"
        }
       {
            "name": "rolling_variance_analysis",
            "question": "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
            "context": "Analyze the flux values over time for each group of projects, cost centers, and departments for making better decisions of investment"
        },

        {
            "name": "anomaly_detection",
            "question": "Find anomalies in daily spending patterns in daily transactional values that deviate from normal business patterns week by week by region and project",
            "context": "Find anomalies in daily spending patterns"
        },
        {
            "name": "mean_transactional_values",
            "question": "What are the mean, average daily transactional values for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "daily_trends_forecast",
            "question": "What are the daily trends of transactional values, forecasted values, and forecasted PO with line item for purchase orders by region and project",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "distribution_analysis",
            "question": "What is the distribution of the mean daily transactional values for each type of source by region and project daily?",
            "context": "Calculate mean daily transactional values"
        },
        {
            "name": "flux_analysis",
            "question": "Perform rolling 5 day mean transactiona values, forecasted values. Using those perform flux analysis by calculating the variance for the mean transactional values, forecasted values by region,cost center, and project",
            "context": "Calculate mean daily transactional values"
        }
    """
    
    # Column descriptions
    columns_description = {
        "Date": "Transaction date in YYYY-MM-DD format, indicating when the financial transaction occurred",
        "Region": "Geographic region or country where the transaction took place (e.g., France, Germany, United Kingdom, United Arab Emirates)",
        "Cost center": "Organizational cost center identifier, typically 'Center A' in this dataset, representing the department or unit responsible for the cost",
        "Project": "Project identifier or project number, can be numeric (e.g., 10.0, 20.0) or empty, indicating which project the transaction is associated with",
        "Account": "Account number or identifier, appears to be consistently '2' in this dataset, representing the general ledger account",
        "Source": "Source system or module that generated the transaction (e.g., PROJECT ACCOUNTING, PAYABLES, REVALUATION, SPREADSHEET)",
        "Category": "Transaction category or type (e.g., MISCELLANEOUS_COST, PURCHASE INVOICES, ACCRUAL - AUTOREVERSE, REVALUE PROFIT/LOSS)",
        "Event Type": "Specific event or action type (e.g., MISC_COST_DIST, INVOICE VALIDATED, INVOICE CANCELLED, CREDIT MEMO VALIDATED, MISC_COST_DIST_ADJ)",
        "PO No": "Purchase Order number identifier, format like 'NEW_PO_XXXX' where XXXX is a numeric identifier",
        "Transactional value": "Original transaction amount in the transaction currency, can be positive or negative values representing debits and credits",
        "Functional value": "Transaction amount converted to the functional currency (typically the reporting currency), accounting for exchange rate differences",
        "PO with Line item": "Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking",
        "Forecasted value": "Forecasted transaction amount in the transaction currency, can be positive or negative values representing debits and credits",
        "Forecasted functional value": "Forecasted transaction amount converted to the functional currency (typically the reporting currency), accounting for exchange rate differences",
        "Forecasted PO with Line item": "Forecasted Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking"
    }
    
    # Run analyses
    results = {}
    for analysis in analysis_questions:
        print(f"\n{'='*80}")
        print(f"🔍 Running Analysis: {analysis['name'].replace('_', ' ').title()}")
        print(f"{'='*80}")
        
        # Generate dataframe summary
        state = InsightManagerState(
            question=analysis["question"],
            context=analysis["context"],
            goal="Generate insights from the dataset",
            dataset_path=""
        )
        dataframe_summary = summarize_agent.summarize_dataframe(
            dataframe=po_df, 
            question=analysis["question"], 
            state=state
        )
        
        # Run analysis
        result = analyze_question_with_pipeline_flow(
            question=analysis["question"],
            dataframe=po_df,
            dataframe_description="Financial flux data with project, cost center, and department information",
            dataframe_summary=dataframe_summary,
            columns_description=columns_description,
            context=analysis["context"],
            dataframe_name="Purchase Orders Data"
        )
        
        results[analysis["name"]] = result
    
    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if OUTPUT_CONFIG["include_timestamp"] else ""
    
    # Create output directory
    output_dir = OUTPUT_CONFIG["output_directory"]
    os.makedirs(output_dir, exist_ok=True)
    
    # Create visualizations and comprehensive files
    print(f"\n🎨 Creating Visualizations and Comprehensive Files...")
    for analysis_name, result in results.items():
        if result.get("pipeline_flow_result"):
            # Create Mermaid flow visualization
            if OUTPUT_CONFIG["create_flow_visualization"]:
                create_mermaid_visualization(
                    result["pipeline_flow_result"], 
                    output_dir, 
                    analysis_name, 
                    timestamp
                )
            
            # Create comprehensive flow file
            create_comprehensive_flow_file(
                result["pipeline_flow_result"], 
                output_dir, 
                analysis_name, 
                timestamp
            )
    
    # Save results to JSON
    if OUTPUT_CONFIG["save_to_json"]:
        print(f"\n💾 Saving Results to JSON...")
        
        # Convert results to JSON-serializable format
        def convert_to_json_serializable(obj):
            if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
                return obj.dict()
            elif isinstance(obj, dict):
                return {key: convert_to_json_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_json_serializable(item) for item in obj]
            else:
                return obj
        
        json_results = {
            "analysis_results": {
                name: convert_to_json_serializable(result) 
                for name, result in results.items()
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_analyses": len(results),
                "analysis_type": "enhanced_funnel_analysis_with_pipeline_flow"
            }
        }
        
        # Save main results file
        main_filename = f"enhanced_funnel_analysis_results{'_' + timestamp if timestamp else ''}.json"
        output_filename = os.path.join(output_dir, main_filename)
        
        try:
            with open(output_filename, 'w', encoding=OUTPUT_CONFIG["file_encoding"]) as json_file:
                json.dump(json_results, json_file, indent=4, ensure_ascii=False, default=str)
            print(f"✅ Results saved to: {output_filename}")
        except Exception as e:
            print(f"❌ Error saving results: {e}")
    
    # Display summary
    print(f"\n📊 ANALYSIS SUMMARY")
    print(f"{'='*80}")
    print(f"Total analyses: {len(results)}")
    print(f"Successful analyses: {sum(1 for r in results.values() if r.get('pipeline_flow_result'))}")
    print(f"Failed analyses: {sum(1 for r in results.values() if not r.get('pipeline_flow_result'))}")
    
    # Display file summary
    print(f"\n📁 OUTPUT FILES CREATED:")
    print(f"   📄 Main results: {output_filename if OUTPUT_CONFIG['save_to_json'] else 'Not saved'}")
    
    if OUTPUT_CONFIG["create_flow_visualization"]:
        vis_dir = os.path.join(output_dir, OUTPUT_CONFIG["visualization_output_directory"])
        if os.path.exists(vis_dir):
            png_files = [f for f in os.listdir(vis_dir) if f.endswith('.png')]
            print(f"   🎨 Flow visualizations: {len(png_files)} PNG files")
            print(f"   📁 Visualization directory: {os.path.abspath(vis_dir)}")
    
    if OUTPUT_CONFIG["create_mermaid_charts"]:
        mermaid_dir = os.path.join(output_dir, OUTPUT_CONFIG["mermaid_output_directory"])
        if os.path.exists(mermaid_dir):
            mmd_files = [f for f in os.listdir(mermaid_dir) if f.endswith('.mmd')]
            html_files = [f for f in os.listdir(mermaid_dir) if f.endswith('.html')]
            print(f"   📊 Mermaid charts: {len(mmd_files)} MMD files, {len(html_files)} HTML files")
            print(f"   📁 Mermaid directory: {os.path.abspath(mermaid_dir)}")
    
    # Count comprehensive flow files
    py_files = [f for f in os.listdir(output_dir) if f.endswith('_comprehensive_flow.py')]
    print(f"   📄 Comprehensive flow files: {len(py_files)} Python files")
    print(f"   📁 Output directory: {os.path.abspath(output_dir)}")
    
    print(f"\n🎉 Enhanced Funnel Analysis Complete!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
