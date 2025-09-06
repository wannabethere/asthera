"""
Pipeline Code Generator for ML Tools

This module generates executable code from ML pipeline code that uses BasePipe classes.
It creates a cache system to store DataFrames by name/key and generates executable
code that can be run independently.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class PipelineCodeGenerator:
    """
    Generates executable code from ML pipeline code that uses BasePipe classes.
    
    This generator:
    1. Parses pipeline code to identify DataFrame operations
    2. Creates a cache system for storing DataFrames
    3. Generates executable code that can be run independently
    4. Handles the BasePipe.from_dataframe() and to_df() pattern
    """
    
    def __init__(self):
        """Initialize the pipeline code generator."""
        self.cache_variables = []
        self.cache_counter = 0
        self.imports = set()
        self.dataframe_cache = {}
    
    def generate_executable(self, pipeline_code: str, output_file: Optional[str] = None) -> str:
        """
        Generate executable code from pipeline code.
        
        Args:
            pipeline_code: The ML pipeline code to convert
            output_file: Optional output file path
            
        Returns:
            Generated executable code
        """
        # Reset state
        self.cache_variables = []
        self.cache_counter = 0
        self.imports = set()
        self.dataframe_cache = {}
        
        # Parse the pipeline code
        parsed_code = self._parse_pipeline_code(pipeline_code)
        
        # Generate the executable code
        executable_code = self._generate_executable_code(parsed_code)
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(executable_code)
        
        return executable_code
    
    def _parse_pipeline_code(self, pipeline_code: str) -> List[Dict]:
        """
        Parse the pipeline code into structured components.
        
        Args:
            pipeline_code: Raw pipeline code
            
        Returns:
            List of parsed pipeline steps
        """
        # Split into steps (lines starting with #)
        steps = []
        current_step = None
        
        for line in pipeline_code.strip().split('\n'):
            line = line.strip()
            
            if line.startswith('# Step'):
                if current_step:
                    steps.append(current_step)
                
                # Extract step number and description
                step_match = re.match(r'# Step (\d+): (.+)', line)
                if step_match:
                    current_step = {
                        'step_number': int(step_match.group(1)),
                        'description': step_match.group(2),
                        'code': [],
                        'result_variable': None,
                        'input_dataframe': None
                    }
            
            elif line and current_step:
                current_step['code'].append(line)
                
                # Extract result variable and input dataframe
                if '=' in line and 'from_dataframe' in line:
                    # Extract result variable
                    var_match = re.match(r'(\w+)\s*=', line)
                    if var_match:
                        current_step['result_variable'] = var_match.group(1)
                    
                    # Extract input dataframe name
                    df_match = re.search(r'from_dataframe\("([^"]+)"\)', line)
                    if df_match:
                        current_step['input_dataframe'] = df_match.group(1)
        
        # Add the last step
        if current_step:
            steps.append(current_step)
        
        return steps
    
    def _generate_executable_code(self, parsed_steps: List[Dict]) -> str:
        """
        Generate executable code from parsed pipeline steps.
        
        Args:
            parsed_steps: List of parsed pipeline steps
            
        Returns:
            Generated executable code
        """
        # Generate imports
        imports_code = self._generate_imports()
        
        # Generate cache initialization
        cache_code = self._generate_cache_initialization()
        
        # Generate data loading
        data_loading_code = self._generate_data_loading(parsed_steps)
        
        # Generate pipeline execution
        pipeline_code = self._generate_pipeline_execution(parsed_steps)
        
        # Generate results display
        results_code = self._generate_results_display(parsed_steps)
        
        # Combine all parts
        executable_code = f"""#!/usr/bin/env python3
\"\"\"
Generated ML Pipeline Executable

This file was automatically generated from ML pipeline code.
It executes a series of data analysis steps using the BasePipe system.
\"\"\"

{imports_code}

{cache_code}

{data_loading_code}

# =============================================================================
# PIPELINE EXECUTION
# =============================================================================

{pipeline_code}

# =============================================================================
# RESULTS DISPLAY
# =============================================================================

{results_code}

print("\\n✅ Pipeline execution completed successfully!")
"""
        
        return executable_code
    
    def _generate_imports(self) -> str:
        """Generate import statements."""
        self.imports.update([
            'pandas as pd',
            'numpy as np',
            'matplotlib.pyplot as plt',
            'seaborn as sns'
        ])
        
        # Add BasePipe imports
        base_imports = [
            'from insightsagents.app.tools.mltools.base_pipe import BasePipe',
            'from insightsagents.app.tools.mltools.metrics_pipe import MetricsPipe',
            'from insightsagents.app.tools.mltools.trends_pipe import TrendsPipe',
            'from insightsagents.app.tools.mltools.time_series_pipe import TimeSeriesPipe'
        ]
        
        imports_code = "\n".join(sorted(self.imports)) + "\n\n" + "\n".join(base_imports)
        return imports_code
    
    def _generate_cache_initialization(self) -> str:
        """Generate cache initialization code."""
        return '''# =============================================================================
# DATA CACHE SYSTEM
# =============================================================================

class DataFrameCache:
    """Cache system for storing DataFrames by name."""
    
    def __init__(self):
        self._cache = {}
    
    def store(self, name: str, df: pd.DataFrame):
        """Store a DataFrame in the cache."""
        self._cache[name] = df.copy()
        print(f"📊 Stored DataFrame '{name}' in cache (shape: {df.shape})")
    
    def retrieve(self, name: str) -> pd.DataFrame:
        """Retrieve a DataFrame from the cache."""
        if name not in self._cache:
            raise KeyError(f"DataFrame '{name}' not found in cache")
        return self._cache[name].copy()
    
    def list_available(self) -> List[str]:
        """List all available DataFrame names in cache."""
        return list(self._cache.keys())
    
    def get_info(self, name: str) -> Dict[str, Any]:
        """Get information about a cached DataFrame."""
        if name not in self._cache:
            return {"error": f"DataFrame '{name}' not found"}
        
        df = self._cache[name]
        return {
            "name": name,
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "memory_usage": df.memory_usage(deep=True).sum()
        }

# Initialize the cache
cache = DataFrameCache()

# =============================================================================
# DATA LOADING FUNCTIONS
# =============================================================================

def load_data_from_source(source_name: str) -> pd.DataFrame:
    """
    Load data from a specified source.
    
    This function should be customized based on your data sources.
    Currently returns sample data for demonstration.
    """
    print(f"🔄 Loading data from source: {source_name}")
    
    # TODO: Replace this with your actual data loading logic
    if source_name == "Purchase Orders Data":
        # Generate sample purchase orders data
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        regions = ['North', 'South', 'East', 'West']
        projects = ['Project A', 'Project B', 'Project C', 'Project D']
        sources = ['Online', 'Phone', 'Email', 'Walk-in']
        
        n_records = 1000
        data = {
            'Date': np.random.choice(dates, n_records),
            'Region': np.random.choice(regions, n_records),
            'Project': np.random.choice(projects, n_records),
            'Source': np.random.choice(sources, n_records),
            'Transactional value': np.random.uniform(100, 10000, n_records)
        }
        
        df = pd.DataFrame(data)
        print(f"✅ Generated sample data with {len(df)} records")
        return df
    
    else:
        # For other sources, you can add custom loading logic
        raise ValueError(f"Unknown data source: {source_name}")

def load_and_cache_data(source_name: str) -> str:
    """
    Load data from source and store in cache.
    
    Args:
        source_name: Name of the data source
        
    Returns:
        Cache key for the loaded data
    """
    df = load_data_from_source(source_name)
    cache.store(source_name, df)
    return source_name
'''
    
    def _generate_data_loading(self, parsed_steps: List[Dict]) -> str:
        """Generate data loading code."""
        # Collect unique data sources
        data_sources = set()
        for step in parsed_steps:
            if step['input_dataframe']:
                data_sources.add(step['input_dataframe'])
        
        if not data_sources:
            return "# No external data sources detected in pipeline."
        
        loading_code = "# Load all required data sources into cache\n"
        for source in sorted(data_sources):
            loading_code += f"load_and_cache_data('{source}')\n"
        
        return loading_code
    
    def _generate_pipeline_execution(self, parsed_steps: List[Dict]) -> str:
        """Generate pipeline execution code."""
        pipeline_code = ""
        
        for step in parsed_steps:
            pipeline_code += f"\n# Step {step['step_number']}: {step['description']}\n"
            
            # Generate the step execution code
            step_code = self._generate_step_execution(step)
            pipeline_code += step_code + "\n"
        
        return pipeline_code
    
    def _generate_step_execution(self, step: Dict) -> str:
        """Generate code for a single pipeline step."""
        step_code = ""
        
        # Handle the case where we need to load data from cache
        if step['input_dataframe'] and step['input_dataframe'] != 'result':
            step_code += f"# Load input data from cache\n"
            step_code += f"input_df = cache.retrieve('{step['input_dataframe']}')\n\n"
        
        # Convert the pipeline code to use cached data
        for line in step['code']:
            modified_line = self._modify_pipeline_line(line, step)
            step_code += modified_line + "\n"
        
        # Store result in cache if it's not the final result
        if step['result_variable'] and step['result_variable'] != 'result':
            step_code += f"\n# Store result in cache for potential reuse\n"
            step_code += f"cache.store('{step['result_variable']}', {step['result_variable']})\n"
        
        return step_code
    
    def _modify_pipeline_line(self, line: str, step: Dict) -> str:
        """Modify a pipeline line to work with cached data."""
        # Replace from_dataframe calls with cached data
        if 'from_dataframe' in line and step['input_dataframe']:
            if step['input_dataframe'] == 'result':
                # If input is 'result', use the previous result
                line = line.replace(f'from_dataframe("result")', 'from_dataframe(input_df)')
            else:
                # Use cached data
                line = line.replace(f'from_dataframe("{step["input_dataframe"]}")', 'from_dataframe(input_df)')
        
        return line
    
    def _generate_results_display(self, parsed_steps: List[Dict]) -> str:
        """Generate results display code."""
        if not parsed_steps:
            return "# No results to display"
        
        # Get the final result variable
        final_step = parsed_steps[-1]
        final_var = final_step.get('result_variable', 'result')
        
        display_code = f"""# Display final results
print(f"\\n📊 Final Result Shape: {{final_result.shape}}")
print(f"📋 Final Result Columns: {{list(final_result.columns)}}")

# Show first few rows
print("\\n🔍 First 5 rows of final result:")
print(final_result.head())

# Show basic statistics
print("\\n📈 Basic Statistics:")
print(final_result.describe())

# Show data types
print("\\n🔧 Data Types:")
print(final_result.dtypes)

# Cache information
print("\\n💾 Cache Status:")
for name in cache.list_available():
    info = cache.get_info(name)
    print(f"  - {{name}}: {{info['shape']}} shape, {{info['memory_usage']}} bytes")

# Optional: Save results to file
try:
    output_file = "pipeline_results.csv"
    final_result.to_csv(output_file, index=False)
    print(f"\\n💾 Results saved to {{output_file}}")
except Exception as e:
    print(f"\\n⚠️  Could not save results: {{e}}")
"""
        
        # Replace final_result with the actual variable name
        display_code = display_code.replace('final_result', final_var)
        
        return display_code


def main():
    """Example usage of the PipelineCodeGenerator."""
    generator = PipelineCodeGenerator()
    
    # Example pipeline code
    example_pipeline = '''# Step 1: Data Selection
result = (
    MetricsPipe.from_dataframe("Purchase Orders Data")
    | Select(selectors=['Date', 'Region', 'Project', 'Source', 'Transactional value'])
    ).to_df()
# Step 2: Daily Aggregation of Transactional Values
result = (
    TrendsPipe.from_dataframe(result)
    | aggregate_by_time(group_by=['Date', 'Region', 'Project', 'Source'], aggregation={'mean': 'Transactional value'})
    ).to_df()
# Step 3: Distribution Analysis of Mean Daily Transactional Values
result = (
    TimeSeriesPipe.from_dataframe(result)
    | distribution_analysis(data='mean daily transactional values', group_by=['Region', 'Project', 'Source'])
    ).to_df()'''
    
    # Generate executable code
    executable_code = generator.generate_executable(
        example_pipeline, 
        output_file="generated_pipeline_executor.py"
    )
    
    print("✅ Generated executable pipeline code!")
    print("📁 Output file: generated_pipeline_executor.py")
    print("\n🔍 Preview of generated code:")
    print("=" * 50)
    print(executable_code[:500] + "...")
    print("=" * 50)


if __name__ == "__main__":
    main()
