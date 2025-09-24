"""
Update Tool Specs with Enhanced Metadata

This script updates all tool specification files with the new enhanced metadata
structure from the LLM-powered function registry.
"""

import os
import sys
import json
import inspect
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.tools.mltools.registry import (
    initialize_enhanced_function_registry,
    create_llm_metadata_generator
)
import chromadb


def get_enhanced_metadata_for_module(module, llm_generator):
    """Get enhanced metadata for all functions in a module."""
    functions_metadata = {}
    module_name = module.__name__.split('.')[-1]
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and not name.startswith('_'):
            try:
                # Generate LLM metadata
                llm_metadata = llm_generator.generate_function_metadata(obj, module_name)
                
                # Extract function information
                docstring = inspect.getdoc(obj) or ""
                sig = inspect.signature(obj)
                
                # Parse parameters
                parameters = {}
                for param_name, param in sig.parameters.items():
                    param_info = {
                        'name': param_name,
                        'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
                        'default': param.default if param.default != inspect.Parameter.empty else None,
                        'required': param.default == inspect.Parameter.empty,
                        'description': f"Parameter of type {str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'}"
                    }
                    parameters[param_name] = param_info
                
                # Extract examples from docstring
                examples = extract_examples_from_docstring(docstring)
                
                # Generate usage patterns
                usage_patterns = generate_usage_patterns(name, parameters, examples)
                
                # Extract dependencies
                try:
                    source_code = inspect.getsource(obj)
                    dependencies = extract_dependencies_from_source(source_code)
                except:
                    source_code = ""
                    dependencies = []
                
                # Generate output description
                output_description = generate_output_description(name, str(sig.return_annotation), docstring)
                
                # Create enhanced metadata
                enhanced_metadata = {
                    "name": name,
                    "module": module_name,
                    "description": llm_metadata.description or extract_description_from_docstring(docstring),
                    "docstring": docstring,
                    "parameters": parameters,
                    "return_type": str(sig.return_annotation),
                    "examples": examples,
                    "category": llm_metadata.category,
                    "subcategory": llm_metadata.subcategory,
                    "use_cases": llm_metadata.use_cases,
                    "tags": llm_metadata.tags,
                    "keywords": llm_metadata.keywords,
                    "source_code": source_code,
                    "usage_patterns": usage_patterns,
                    "dependencies": dependencies,
                    "complexity": llm_metadata.complexity_level,
                    "data_requirements": llm_metadata.data_requirements,
                    "output_description": output_description,
                    "related_functions": llm_metadata.related_functions,
                    "confidence_score": llm_metadata.confidence_score,
                    "llm_generated": True
                }
                
                functions_metadata[name] = enhanced_metadata
                
            except Exception as e:
                print(f"Error processing function {name}: {e}")
                # Create fallback metadata
                functions_metadata[name] = create_fallback_metadata(name, module_name, obj)
    
    return functions_metadata


def extract_examples_from_docstring(docstring: str) -> List[str]:
    """Extract examples from docstring."""
    import re
    examples = []
    if not docstring:
        return examples
    
    # Look for example sections
    example_patterns = [
        r'Examples?:\s*\n(.*?)(?=\n\w+:|$)',
        r'Example:\s*\n(.*?)(?=\n\w+:|$)',
        r'Usage:\s*\n(.*?)(?=\n\w+:|$)',
        r'```python\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```'
    ]
    
    for pattern in example_patterns:
        matches = re.findall(pattern, docstring, re.DOTALL | re.IGNORECASE)
        for match in matches:
            example_lines = [line.strip() for line in match.split('\n') if line.strip()]
            examples.extend(example_lines)
    
    return examples


def extract_description_from_docstring(docstring: str) -> str:
    """Extract description from docstring."""
    if not docstring:
        return ""
    
    lines = docstring.strip().split('\n')
    description_lines = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith(('Parameters:', 'Returns:', 'Examples:', 'Raises:', 'Note:', 'Warning:')):
            description_lines.append(line)
        else:
            break
    
    return ' '.join(description_lines).strip()


def generate_usage_patterns(name: str, parameters: Dict, examples: List[str]) -> List[str]:
    """Generate usage patterns for the function."""
    patterns = []
    
    # Basic usage pattern
    param_names = list(parameters.keys())
    if param_names:
        basic_pattern = f"{name}({', '.join(param_names[:3])}{'...' if len(param_names) > 3 else ''})"
        patterns.append(basic_pattern)
    
    # Add patterns from examples
    for example in examples:
        if name in example:
            patterns.append(example)
    
    return patterns


def extract_dependencies_from_source(source_code: str) -> List[str]:
    """Extract dependencies from source code."""
    dependencies = []
    
    # Common ML and data science libraries
    common_deps = ['pandas', 'numpy', 'scipy', 'sklearn', 'statsmodels', 'matplotlib', 'seaborn']
    
    for dep in common_deps:
        if dep in source_code.lower():
            dependencies.append(dep)
    
    return dependencies


def generate_output_description(name: str, return_type: str, docstring: str) -> str:
    """Generate output description for the function."""
    if 'Returns:' in docstring:
        # Extract from docstring
        returns_section = docstring.split('Returns:')[1].split('\n')[0].strip()
        return returns_section
    
    # Generate based on function name and return type
    if 'detect' in name.lower():
        return f"Detection results with anomaly flags and scores"
    elif 'forecast' in name.lower():
        return f"Forecasted values with confidence intervals"
    elif 'aggregate' in name.lower():
        return f"Aggregated data with calculated metrics"
    elif 'segment' in name.lower():
        return f"Segmentation results with cluster assignments"
    else:
        return f"Results of type {return_type}"


def create_fallback_metadata(name: str, module_name: str, func) -> Dict[str, Any]:
    """Create fallback metadata when LLM generation fails."""
    sig = inspect.signature(func)
    
    # Simple heuristic-based classification
    category = "other"
    if "anomaly" in name.lower() or "outlier" in name.lower():
        category = "anomaly_detection"
    elif "forecast" in name.lower() or "trend" in name.lower():
        category = "time_series"
    elif "segment" in name.lower() or "cluster" in name.lower():
        category = "segmentation"
    elif "cohort" in name.lower() or "retention" in name.lower():
        category = "cohort_analysis"
    elif "moving" in name.lower() or "rolling" in name.lower():
        category = "moving_averages"
    elif "risk" in name.lower() or "var" in name.lower():
        category = "risk_analysis"
    elif "funnel" in name.lower() or "conversion" in name.lower():
        category = "funnel_analysis"
    elif "metric" in name.lower() or "stat" in name.lower():
        category = "metrics"
    
    # Parse parameters
    parameters = {}
    for param_name, param in sig.parameters.items():
        param_info = {
            'name': param_name,
            'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
            'default': param.default if param.default != inspect.Parameter.empty else None,
            'required': param.default == inspect.Parameter.empty,
            'description': f"Parameter of type {str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'}"
        }
        parameters[param_name] = param_info
    
    return {
        "name": name,
        "module": module_name,
        "description": f"Function {name} from {module_name}",
        "docstring": inspect.getdoc(func) or "",
        "parameters": parameters,
        "return_type": str(sig.return_annotation),
        "examples": [],
        "category": category,
        "subcategory": "",
        "use_cases": [],
        "tags": [],
        "keywords": [],
        "source_code": "",
        "usage_patterns": [],
        "dependencies": [],
        "complexity": "intermediate",
        "data_requirements": [],
        "output_description": f"Results of type {str(sig.return_annotation)}",
        "related_functions": [],
        "confidence_score": 0.5,
        "llm_generated": False
    }


def update_tool_spec_file(module, spec_file_path: str, llm_generator):
    """Update a single tool spec file with enhanced metadata."""
    print(f"Updating {spec_file_path}...")
    
    # Get enhanced metadata for the module
    functions_metadata = get_enhanced_metadata_for_module(module, llm_generator)
    
    # Create new spec structure
    new_spec = {
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "llm_generated": True,
            "total_functions": len(functions_metadata),
            "categories": list(set(func["category"] for func in functions_metadata.values())),
            "complexity_levels": list(set(func["complexity"] for func in functions_metadata.values()))
        },
        "functions": {}
    }
    
    # Convert to the expected format
    for func_name, func_metadata in functions_metadata.items():
        # Convert parameters to the expected format
        required_params = []
        optional_params = []
        
        for param_name, param_info in func_metadata["parameters"].items():
            param_dict = {
                "name": param_name,
                "type": param_info["type"],
                "description": param_info["description"]
            }
            
            if param_info["required"]:
                required_params.append(param_dict)
            else:
                if param_info["default"] is not None:
                    param_dict["default"] = str(param_info["default"])
                optional_params.append(param_dict)
        
        # Create function spec
        function_spec = {
            "category": func_metadata["category"],
            "subcategory": func_metadata["subcategory"],
            "description": func_metadata["description"],
            "complexity": func_metadata["complexity"],
            "use_cases": func_metadata["use_cases"],
            "data_requirements": func_metadata["data_requirements"],
            "tags": func_metadata["tags"],
            "keywords": func_metadata["keywords"],
            "confidence_score": func_metadata["confidence_score"],
            "llm_generated": func_metadata["llm_generated"],
            "required_params": required_params,
            "optional_params": optional_params,
            "outputs": {
                "type": func_metadata["return_type"],
                "description": func_metadata["output_description"]
            },
            "examples": func_metadata["examples"],
            "usage_patterns": func_metadata["usage_patterns"],
            "dependencies": func_metadata["dependencies"],
            "related_functions": func_metadata["related_functions"]
        }
        
        new_spec["functions"][func_name] = function_spec
    
    # Write updated spec
    with open(spec_file_path, 'w') as f:
        json.dump(new_spec, f, indent=4)
    
    print(f"Updated {spec_file_path} with {len(functions_metadata)} functions")
    return len(functions_metadata)


def main():
    """Update all tool spec files with enhanced metadata."""
    print("=== Updating Tool Specs with Enhanced Metadata ===\n")
    
    # Initialize LLM generator
    print("Initializing LLM metadata generator...")
    llm_generator = create_llm_metadata_generator("gpt-3.5-turbo")
    
    # Define module to spec file mappings
    module_mappings = {
        "anomalydetection": "anamoly_detection_spec.json",
        "cohortanalysistools": "cohort_analysis_spec.json",
        "segmentationtools": "segmentation_analysis_spec.json",
        "trendanalysistools": "trend_analysis_spec.json",
        "timeseriesanalysis": "timeseries_analysis_spec.json",
        "funnelanalysis": "funnel_analysis_spec.json",
        "metrics_tools": "metricstools_spec.json",
        "operations_tools": "operations_tools_spec.json",
        "movingaverages": "movingaverages_tool_spec.json",
        "riskanalysis": "riskanalysis_tools_spec.json",
        "select_pipe": "select_pipe_spec.json",
        "randomforest_classifier": "randomforest_spec.json",
        "kmeans": "kmeans_spec.json"
    }
    
    # Import modules
    print("Importing ML tool modules...")
    try:
        from app.tools.mltools import (
            anomalydetection, cohortanalysistools, segmentationtools,
            trendanalysistools, timeseriesanalysis, funnelanalysis,
            metrics_tools, operations_tools, movingaverages, riskanalysis
        )
        from app.tools.mltools.select_pipe import SelectPipe
        from app.tools.mltools.models.randomforest_classifier import RandomForestPipe
        from app.tools.mltools.segmentationtools import run_kmeans
        
        modules = {
            "anomalydetection": anomalydetection,
            "cohortanalysistools": cohortanalysistools,
            "segmentationtools": segmentationtools,
            "trendanalysistools": trendanalysistools,
            "timeseriesanalysis": timeseriesanalysis,
            "funnelanalysis": funnelanalysis,
            "metrics_tools": metrics_tools,
            "operations_tools": operations_tools,
            "movingaverages": movingaverages,
            "riskanalysis": riskanalysis,
            "select_pipe": None,  # Will handle separately
            "randomforest_classifier": None,  # Will handle separately
            "kmeans": None  # Will handle separately
        }
        
    except ImportError as e:
        print(f"Error importing modules: {e}")
        return 1
    
    # Update spec files
    spec_dir = "data/meta/toolspecs"
    total_functions = 0
    
    for module_name, spec_file in module_mappings.items():
        spec_path = os.path.join(spec_dir, spec_file)
        
        if not os.path.exists(spec_path):
            print(f"Warning: Spec file {spec_path} not found, skipping...")
            continue
        
        module = modules.get(module_name)
        if module is None:
            print(f"Warning: Module {module_name} not found, skipping...")
            continue
        
        try:
            func_count = update_tool_spec_file(module, spec_path, llm_generator)
            total_functions += func_count
        except Exception as e:
            print(f"Error updating {spec_file}: {e}")
    
    print(f"\n=== Update Complete ===")
    print(f"Total functions processed: {total_functions}")
    print(f"Updated spec files: {len(module_mappings)}")
    
    return 0


if __name__ == "__main__":
    exit(main())
