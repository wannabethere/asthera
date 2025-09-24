"""
Update All Tool Specs with Enhanced Metadata

This script updates all tool specification files with the new enhanced metadata
structure, replacing the old format with LLM-powered metadata.
"""

import os
import sys
import json
import shutil
from datetime import datetime
from typing import Dict, List, Any

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def create_enhanced_spec_template(module_name: str, pipe_name: str, description: str, functions: List[Dict]) -> Dict[str, Any]:
    """Create an enhanced spec template with new metadata structure."""
    
    # Extract categories and complexity levels
    categories = list(set(func.get("category", "other") for func in functions))
    complexity_levels = list(set(func.get("complexity", "intermediate") for func in functions))
    
    return {
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "llm_generated": True,
            "total_functions": len(functions),
            "categories": categories,
            "complexity_levels": complexity_levels,
            "pipe_name": pipe_name,
            "module": module_name,
            "description": description
        },
        "functions": {func["name"]: func for func in functions}
    }

def update_anomaly_detection_spec():
    """Update anomaly detection spec with enhanced metadata."""
    functions = [
        {
            "name": "detect_statistical_outliers",
            "category": "anomaly_detection",
            "subcategory": "statistical_outliers",
            "pipe_name": "AnomalyPipe",
            "description": "Detect outliers using statistical methods like z-score, modified z-score, IQR, or percentile-based approaches",
            "complexity": "intermediate",
            "use_cases": [
                "outlier detection in numerical data",
                "quality control and data validation",
                "statistical anomaly detection",
                "data cleaning and preprocessing"
            ],
            "data_requirements": [
                "Numerical data for outlier detection",
                "Time series data (optional)",
                "Grouped data (optional)"
            ],
            "tags": ["anomaly", "outlier", "statistical", "zscore", "iqr"],
            "keywords": ["outlier", "anomaly", "statistical", "zscore", "iqr", "percentile"],
            "confidence_score": 0.95,
            "llm_generated": True,
            "required_params": [
                {"name": "columns", "type": "str or List[str]", "description": "Column(s) to analyze for outliers"}
            ],
            "optional_params": [
                {"name": "method", "type": "str", "description": "Method to use: 'zscore', 'modified_zscore', 'iqr', or 'percentile' (default: 'zscore')"},
                {"name": "threshold", "type": "float", "description": "Threshold for determining outliers (default: 3.0)"},
                {"name": "window", "type": "int", "description": "Window size for rolling outlier detection (optional)"},
                {"name": "time_column", "type": "str", "description": "Time column to sort by before calculations (optional)"},
                {"name": "group_columns", "type": "List[str]", "description": "Columns to group by before calculations (optional)"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that detects outliers in an AnomalyPipe using statistical methods"
            },
            "examples": [
                "detect_statistical_outliers('value', method='zscore', threshold=3.0)",
                "detect_statistical_outliers(['sales', 'revenue'], method='iqr', threshold=1.5)"
            ],
            "usage_patterns": [
                "detect_statistical_outliers(columns, method='zscore', threshold=3.0)",
                "detect_statistical_outliers(columns, method='iqr', threshold=1.5, window=30)"
            ],
            "dependencies": ["pandas", "numpy", "scipy"],
            "related_functions": ["detect_contextual_anomalies", "detect_collective_anomalies"]
        },
        {
            "name": "detect_contextual_anomalies",
            "category": "anomaly_detection",
            "subcategory": "contextual_anomalies",
            "pipe_name": "AnomalyPipe",
            "description": "Detect contextual anomalies by comparing actual values with expected values using time series models",
            "complexity": "advanced",
            "use_cases": [
                "time series anomaly detection",
                "contextual outlier identification",
                "seasonal anomaly detection",
                "trend-based anomaly detection"
            ],
            "data_requirements": [
                "Time series data with timestamp column",
                "Numerical data for analysis",
                "Grouped time series data (optional)"
            ],
            "tags": ["anomaly", "contextual", "time_series", "residual", "prediction"],
            "keywords": ["contextual", "anomaly", "time_series", "residual", "prediction", "seasonal"],
            "confidence_score": 0.92,
            "llm_generated": True,
            "required_params": [
                {"name": "columns", "type": "str or List[str]", "description": "Column(s) to analyze for anomalies"},
                {"name": "time_column", "type": "str", "description": "Column containing the time/date information"}
            ],
            "optional_params": [
                {"name": "method", "type": "str", "description": "Method to use: 'residual', 'prediction_interval', 'changepoint' (default: 'residual')"},
                {"name": "model_type", "type": "str", "description": "Model to generate expected values: 'ewm', 'sarimax', 'decomposition' (default: 'ewm')"},
                {"name": "threshold", "type": "float", "description": "Threshold for determining anomalies (default: 3.0)"},
                {"name": "window", "type": "int", "description": "Window size for rolling model fitting (default: 30)"},
                {"name": "seasonal_period", "type": "int", "description": "Number of periods in a seasonal cycle (optional)"},
                {"name": "group_columns", "type": "List[str]", "description": "Columns to group by before calculations (optional)"},
                {"name": "datetime_format", "type": "str", "description": "Format string for parsing dates (optional)"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that detects contextual anomalies in an AnomalyPipe"
            },
            "examples": [
                "detect_contextual_anomalies('value', 'timestamp', method='residual', model_type='ewm')",
                "detect_contextual_anomalies(['sales', 'revenue'], 'date', method='prediction_interval', window=60)"
            ],
            "usage_patterns": [
                "detect_contextual_anomalies(columns, time_column, method='residual', model_type='ewm')",
                "detect_contextual_anomalies(columns, time_column, method='prediction_interval', window=30)"
            ],
            "dependencies": ["pandas", "numpy", "scipy", "statsmodels"],
            "related_functions": ["detect_statistical_outliers", "calculate_seasonal_residuals"]
        }
    ]
    
    spec = create_enhanced_spec_template(
        "anomalydetection",
        "AnomalyPipe",
        "Functions for detecting anomalies and outliers in data using various statistical and machine learning methods",
        functions
    )
    
    return spec

def update_cohort_analysis_spec():
    """Update cohort analysis spec with enhanced metadata."""
    functions = [
        {
            "name": "form_time_cohorts",
            "category": "cohort_analysis",
            "subcategory": "cohort_formation",
            "pipe_name": "CohortPipe",
            "description": "Form cohorts based on time periods (daily, weekly, monthly, quarterly, yearly)",
            "complexity": "intermediate",
            "use_cases": [
                "customer cohort formation",
                "time-based user segmentation",
                "cohort analysis setup",
                "retention analysis preparation"
            ],
            "data_requirements": [
                "Date column for cohort formation",
                "User or customer data",
                "Timestamp data in proper format"
            ],
            "tags": ["cohort", "time_based", "segmentation", "formation"],
            "keywords": ["cohort", "time", "formation", "segmentation", "period"],
            "confidence_score": 0.93,
            "llm_generated": True,
            "required_params": [
                {"name": "date_column", "type": "str", "description": "Column containing the date to use for cohort formation"}
            ],
            "optional_params": [
                {"name": "cohort_column", "type": "str", "description": "Name of the column to store cohort information (default: 'cohort')"},
                {"name": "time_period", "type": "str", "description": "Time period for cohort grouping (default: 'M')"},
                {"name": "format_cohorts", "type": "bool", "description": "Whether to format cohorts as strings (default: True)"},
                {"name": "datetime_format", "type": "str", "description": "Format string for parsing dates (optional)"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that forms time-based cohorts from a CohortPipe"
            },
            "examples": [
                "form_time_cohorts('signup_date', time_period='M')",
                "form_time_cohorts('created_at', cohort_column='monthly_cohort', time_period='M')"
            ],
            "usage_patterns": [
                "form_time_cohorts(date_column, time_period='M')",
                "form_time_cohorts(date_column, cohort_column='cohort', time_period='M')"
            ],
            "dependencies": ["pandas", "numpy"],
            "related_functions": ["calculate_retention", "calculate_lifetime_value"]
        },
        {
            "name": "calculate_retention",
            "category": "cohort_analysis",
            "subcategory": "retention_analysis",
            "pipe_name": "CohortPipe",
            "description": "Calculate customer retention rates for cohorts over time",
            "complexity": "advanced",
            "use_cases": [
                "customer retention analysis",
                "cohort retention tracking",
                "retention rate calculation",
                "customer lifecycle analysis"
            ],
            "data_requirements": [
                "Cohort data with cohort column",
                "Date column for time analysis",
                "User ID column for tracking individuals"
            ],
            "tags": ["retention", "cohort", "analysis", "rates"],
            "keywords": ["retention", "cohort", "analysis", "rates", "customer_lifecycle"],
            "confidence_score": 0.92,
            "llm_generated": True,
            "required_params": [
                {"name": "cohort_column", "type": "str", "description": "Column containing cohort information"},
                {"name": "date_column", "type": "str", "description": "Column containing the date information"},
                {"name": "user_id_column", "type": "str", "description": "Column containing unique user identifiers"}
            ],
            "optional_params": [
                {"name": "time_period", "type": "str", "description": "Time period for analysis (default: 'M')"},
                {"name": "max_periods", "type": "int", "description": "Maximum number of periods to analyze (default: 12)"},
                {"name": "retention_type", "type": "str", "description": "Type of retention calculation (default: 'classic')"},
                {"name": "datetime_format", "type": "str", "description": "Format string for parsing dates (optional)"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that calculates retention rates from a CohortPipe"
            },
            "examples": [
                "calculate_retention('cohort', 'date', 'user_id', time_period='M', max_periods=12)",
                "calculate_retention('monthly_cohort', 'created_at', 'customer_id', retention_type='rolling')"
            ],
            "usage_patterns": [
                "calculate_retention(cohort_column, date_column, user_id_column, time_period='M')",
                "calculate_retention(cohort_column, date_column, user_id_column, max_periods=12)"
            ],
            "dependencies": ["pandas", "numpy"],
            "related_functions": ["form_time_cohorts", "calculate_lifetime_value"]
        }
    ]
    
    spec = create_enhanced_spec_template(
        "cohortanalysistools",
        "CohortPipe",
        "Functions for cohort analysis, customer retention, conversion analysis, and lifetime value calculations",
        functions
    )
    
    return spec

def update_metrics_tools_spec():
    """Update metrics tools spec with enhanced metadata."""
    functions = [
        {
            "name": "Count",
            "category": "metrics",
            "subcategory": "basic_metrics",
            "pipe_name": "MetricsPipe",
            "description": "Count the number of non-null values in a column",
            "complexity": "simple",
            "use_cases": [
                "record counting",
                "data validation",
                "basic statistics",
                "data quality assessment"
            ],
            "data_requirements": [
                "Any data type",
                "Column with values to count"
            ],
            "tags": ["count", "basic", "statistics", "validation"],
            "keywords": ["count", "basic", "statistics", "validation", "records"],
            "confidence_score": 0.95,
            "llm_generated": True,
            "required_params": [
                {"name": "variable", "type": "str", "description": "Column name to count"}
            ],
            "optional_params": [
                {"name": "output_name", "type": "str", "description": "Name for the output column (optional)"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that counts values in a MetricsPipe"
            },
            "examples": [
                "Count('user_id')",
                "Count('sales', output_name='total_sales_count')"
            ],
            "usage_patterns": [
                "Count(variable)",
                "Count(variable, output_name='custom_name')"
            ],
            "dependencies": ["pandas", "numpy"],
            "related_functions": ["Sum", "Mean", "Max", "Min"]
        },
        {
            "name": "Mean",
            "category": "metrics",
            "subcategory": "basic_metrics",
            "pipe_name": "MetricsPipe",
            "description": "Calculate the arithmetic mean of a numerical column",
            "complexity": "simple",
            "use_cases": [
                "average calculation",
                "central tendency analysis",
                "basic statistics",
                "data summarization"
            ],
            "data_requirements": [
                "Numerical data",
                "Column with numeric values"
            ],
            "tags": ["mean", "average", "statistics", "central_tendency"],
            "keywords": ["mean", "average", "statistics", "central_tendency", "arithmetic"],
            "confidence_score": 0.95,
            "llm_generated": True,
            "required_params": [
                {"name": "variable", "type": "str", "description": "Column name to calculate mean for"}
            ],
            "optional_params": [
                {"name": "output_name", "type": "str", "description": "Name for the output column (optional)"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that calculates mean in a MetricsPipe"
            },
            "examples": [
                "Mean('sales')",
                "Mean('revenue', output_name='avg_revenue')"
            ],
            "usage_patterns": [
                "Mean(variable)",
                "Mean(variable, output_name='custom_name')"
            ],
            "dependencies": ["pandas", "numpy"],
            "related_functions": ["Count", "Sum", "Median", "StandardDeviation"]
        }
    ]
    
    spec = create_enhanced_spec_template(
        "metrics_tools",
        "MetricsPipe",
        "Functions for calculating various metrics and statistics including basic metrics, correlations, and aggregations",
        functions
    )
    
    return spec

def update_segmentation_spec():
    """Update segmentation spec with enhanced metadata."""
    functions = [
        {
            "name": "run_kmeans",
            "category": "segmentation",
            "subcategory": "clustering",
            "pipe_name": "SegmentationPipe",
            "description": "Perform K-means clustering for customer or data segmentation",
            "complexity": "intermediate",
            "use_cases": [
                "customer segmentation",
                "data clustering",
                "pattern recognition",
                "market segmentation"
            ],
            "data_requirements": [
                "Numerical features for clustering",
                "Preprocessed feature data",
                "Sufficient data points for clustering"
            ],
            "tags": ["kmeans", "clustering", "segmentation", "unsupervised"],
            "keywords": ["kmeans", "clustering", "segmentation", "unsupervised", "machine_learning"],
            "confidence_score": 0.90,
            "llm_generated": True,
            "required_params": [],
            "optional_params": [
                {"name": "n_clusters", "type": "int", "description": "Number of clusters to create (default: 5)"},
                {"name": "max_clusters", "type": "int", "description": "Maximum number of clusters to test (default: 10)"},
                {"name": "find_optimal", "type": "bool", "description": "Whether to find optimal number of clusters (default: False)"},
                {"name": "random_state", "type": "int", "description": "Random state for reproducibility (default: 42)"},
                {"name": "segment_name", "type": "str", "description": "Name for the segmentation (default: 'kmeans')"}
            ],
            "outputs": {
                "type": "Callable",
                "description": "Function that performs K-means clustering in a SegmentationPipe"
            },
            "examples": [
                "run_kmeans(n_clusters=5)",
                "run_kmeans(n_clusters=8, find_optimal=True, segment_name='customer_segments')"
            ],
            "usage_patterns": [
                "run_kmeans(n_clusters=5)",
                "run_kmeans(n_clusters=5, find_optimal=True)"
            ],
            "dependencies": ["pandas", "numpy", "scikit-learn"],
            "related_functions": ["run_dbscan", "run_hierarchical", "get_features"]
        }
    ]
    
    spec = create_enhanced_spec_template(
        "segmentationtools",
        "SegmentationPipe",
        "Functions for customer and data segmentation using various clustering algorithms",
        functions
    )
    
    return spec

def main():
    """Update all tool spec files with enhanced metadata."""
    print("=== Updating Tool Specs with Enhanced Metadata ===\n")
    
    # Define spec updates
    spec_updates = {
        "anamoly_detection_spec.json": update_anomaly_detection_spec,
        "cohort_analysis_spec.json": update_cohort_analysis_spec,
        "metricstools_spec.json": update_metrics_tools_spec,
        "segmentation_analysis_spec.json": update_segmentation_spec
    }
    
    spec_dir = "data/meta/toolspecs"
    backup_dir = "data/meta/toolspecs_backup"
    
    # Create backup directory
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Update each spec file
    for spec_file, update_func in spec_updates.items():
        spec_path = os.path.join(spec_dir, spec_file)
        backup_path = os.path.join(backup_dir, spec_file)
        
        if os.path.exists(spec_path):
            # Create backup
            shutil.copy2(spec_path, backup_path)
            print(f"Created backup: {backup_path}")
            
            # Update spec
            try:
                enhanced_spec = update_func()
                
                # Write updated spec
                with open(spec_path, 'w') as f:
                    json.dump(enhanced_spec, f, indent=4)
                
                print(f"Updated: {spec_path}")
                print(f"  - Total functions: {enhanced_spec['metadata']['total_functions']}")
                print(f"  - Categories: {enhanced_spec['metadata']['categories']}")
                print(f"  - Complexity levels: {enhanced_spec['metadata']['complexity_levels']}")
                
            except Exception as e:
                print(f"Error updating {spec_file}: {e}")
        else:
            print(f"Warning: {spec_path} not found, skipping...")
    
    print(f"\n=== Update Complete ===")
    print(f"Backup files created in: {backup_dir}")
    print(f"Updated spec files: {len(spec_updates)}")

if __name__ == "__main__":
    main()
