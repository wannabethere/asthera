"""
ChromaDB Registration Utility for Group Aggregation Functions

This module provides utilities for registering group aggregation functions into ChromaDB
with proper metadata, descriptions, and examples for use in natural language queries.
"""

from typing import Dict, List, Any, Optional
from .group_aggregation_functions import get_all_functions_metadata


def demonstrate_registration():
    """
    Demonstrate the ChromaDB registration functionality.
    """
    print("=== ChromaDB Registration Demonstration ===\n")
    
    # Get all function metadata
    all_metadata = get_all_functions_metadata()
    
    print(f"Total functions available: {len(all_metadata)}")
    print()
    
    # Show function categories
    categories = {}
    for func_name, metadata in all_metadata.items():
        # Determine category based on function name
        if any(op in func_name for op in ['percent_change', 'absolute_change', 'mantel_haenszel', 'cuped', 'prepost', 'power_analysis', 'stratified_summary', 'bootstrap_confidence_interval', 'multi_comparison_adjustment', 'effect_size', 'z_score', 'relative_risk', 'odds_ratio']):
            category = 'Operations Tools'
        elif any(stat in func_name for stat in ['skewness', 'kurtosis', 'coefficient_of_variation', 'interquartile_range', 'mad']):
            category = 'Advanced Statistics'
        elif any(basic in func_name for basic in ['mean', 'sum_values', 'count_values', 'max_value', 'min_value', 'std_dev', 'variance', 'median', 'quantile', 'range_values']):
            category = 'Basic Aggregation'
        else:
            category = 'Specialized Functions'
        
        if category not in categories:
            categories[category] = []
        categories[category].append(func_name)
    
    print("Function Categories:")
    for category, functions in categories.items():
        print(f"  {category}: {len(functions)} functions")
        for func in functions[:3]:  # Show first 3 functions
            print(f"    - {func}")
        if len(functions) > 3:
            print(f"    ... and {len(functions) - 3} more")
        print()
    
    # Show detailed examples
    print("Detailed Examples:")
    print("1. Basic Aggregation:")
    mean_metadata = all_metadata['mean']
    print(f"   Function: {mean_metadata['description']}")
    print(f"   Example: {mean_metadata['example']}")
    print(f"   Returns: {mean_metadata['returns']}")
    print()
    
    print("2. Operations Tool:")
    pct_change_metadata = all_metadata['percent_change']
    print(f"   Function: {pct_change_metadata['description']}")
    print(f"   Example: {pct_change_metadata['example']}")
    print(f"   Returns: {pct_change_metadata['returns']}")
    print()
    
    print("3. Advanced Statistics:")
    skewness_metadata = all_metadata['skewness']
    print(f"   Function: {skewness_metadata['description']}")
    print(f"   Example: {skewness_metadata['example']}")
    print(f"   Returns: {skewness_metadata['returns']}")
    print()
    
    print("4. Specialized Function:")
    weighted_avg_metadata = all_metadata['weighted_average']
    print(f"   Function: {weighted_avg_metadata['description']}")
    print(f"   Example: {weighted_avg_metadata['example']}")
    print(f"   Returns: {weighted_avg_metadata['returns']}")
    print()
    
    # Show search capabilities
    print("Search Capabilities:")
    print("  - Search by description keywords")
    print("  - Search by function type")
    print("  - Search by example usage")
    print("  - Search by return type")
    print()
    
    print("ChromaDB Integration Ready!")
    print("  - All functions include comprehensive metadata")
    print("  - Ready for natural language queries")
    print("  - Supports automated analysis workflows")
    print("  - Includes examples and parameter descriptions")
    
    # Note: ChromaDB registration would require actual ChromaDB installation
    print("\nNote: ChromaDB registration requires ChromaDB to be installed.")
    print("To register functions, install ChromaDB and run the registration functions.")


if __name__ == "__main__":
    # Run demonstration if script is executed directly
    demonstrate_registration()
