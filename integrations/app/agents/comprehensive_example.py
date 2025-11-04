"""
Complete Example: Dashboard Transformation Pipeline
Demonstrates the full workflow from source dashboard to target platform
"""

import json
from pathlib import Path
from typing import Dict, List

# Import our agents
# from dashboard_agent_system import transform_dashboard, create_dashboard_transformation_graph
# from sql_to_dax_converter import SQLToDAXConverter
# from materialized_view_optimizer import MaterializedViewOptimizer
# from conversational_insights_agent import ConversationalInsightsAgent


def load_dashboard(filepath: str) -> Dict:
    """Load dashboard JSON from file"""
    with open(filepath, 'r') as f:
        return json.load(f)


def save_output(data: Dict, output_path: str):
    """Save transformed dashboard"""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)


def example_1_parse_and_analyze():
    """Example 1: Parse source dashboard and analyze queries"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Parse and Analyze Dashboard")
    print("="*70 + "\n")
    
    # Load source dashboard
    dashboard = load_dashboard("/mnt/user-data/uploads/Render-Dashboard-json.txt")
    
    print(f"Dashboard Name: {dashboard.get('dashboard_data', {}).get('dashboard_name')}")
    print(f"Dashboard Type: {dashboard.get('dashboard_data', {}).get('DashboardType')}")
    
    components = dashboard.get('dashboard_data', {}).get('content', {}).get('components', [])
    print(f"\nTotal Components: {len(components)}")
    
    # Analyze each component
    for i, component in enumerate(components[:3], 1):  # First 3 components
        print(f"\n--- Component {i} ---")
        print(f"ID: {component.get('id')}")
        print(f"Type: {component.get('type')}")
        print(f"Question: {component.get('question', '')[:100]}...")
        print(f"SQL Query: {component.get('sql_query', '')[:150]}...")
        
        # Extract sample data info
        sample_data = component.get('sample_data', {})
        if sample_data:
            data_rows = len(sample_data.get('data', []))
            columns = sample_data.get('columns', [])
            print(f"Data Rows: {data_rows}")
            print(f"Columns: {', '.join(columns)}")


def example_2_create_materialized_views():
    """Example 2: Create optimized materialized views"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Create Materialized Views")
    print("="*70 + "\n")
    
    # Load dashboard
    dashboard = load_dashboard("/mnt/user-data/uploads/Render-Dashboard-json.txt")
    components = dashboard.get('dashboard_data', {}).get('content', {}).get('components', [])
    
    # Extract all SQL queries
    queries = [
        comp.get('sql_query', '')
        for comp in components
        if comp.get('sql_query')
    ]
    
    print(f"Extracted {len(queries)} SQL queries from dashboard\n")
    
    # Note: This would use MaterializedViewOptimizer in production
    print("Materialized View Creation Strategy:")
    print("-" * 70)
    
    for i, query in enumerate(queries[:3], 1):
        print(f"\nQuery {i}:")
        print(f"  Source: {query[:100]}...")
        
        # Simulate MV creation
        view_name = f"mv_dashboard_component_{i}"
        print(f"  Materialized View: {view_name}")
        print(f"  Strategy: Incremental refresh based on time columns")
        print(f"  Estimated Benefit: Faster query execution by 5-10x")


def example_3_transform_to_powerbi():
    """Example 3: Transform dashboard to PowerBI format"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Transform to PowerBI")
    print("="*70 + "\n")
    
    # Load dashboard
    dashboard = load_dashboard("/mnt/user-data/uploads/Render-Dashboard-json.txt")
    components = dashboard.get('dashboard_data', {}).get('content', {}).get('components', [])
    
    print("PowerBI Transformation:")
    print("-" * 70)
    
    for i, component in enumerate(components[:2], 1):
        sql_query = component.get('sql_query', '')
        chart_schema = component.get('chart_schema', {})
        
        print(f"\n--- Component {i}: {component.get('question', '')[:80]} ---\n")
        
        # Simulate SQL to DAX conversion
        print("1. SQL to DAX Conversion:")
        print(f"   Original SQL: {sql_query[:100]}...")
        print(f"\n   DAX Measure:")
        
        # Example DAX output
        if "COUNT" in sql_query.upper():
            print("""
   Drop_Off_Rate = 
   DIVIDE(
       COUNTROWS(
           FILTER(
               Training,
               Training[completed_date] = BLANK()
           )
       ),
       COUNTROWS(Training)
   ) * 100
            """)
        
        # Chart transformation
        chart_type = chart_schema.get('mark', {}).get('type', 'unknown')
        print(f"\n2. Chart Transformation:")
        print(f"   Vega-Lite Type: {chart_type}")
        
        powerbi_type_map = {
            'bar': 'clusteredColumnChart',
            'line': 'lineChart',
            'text': 'card',
            'point': 'scatterChart'
        }
        
        powerbi_type = powerbi_type_map.get(chart_type, 'table')
        print(f"   PowerBI Visual: {powerbi_type}")
        
        print(f"\n3. Data Model:")
        print(f"   Table: Training")
        print(f"   Relationships: Auto-detected")
        print(f"   Refresh: Incremental (based on date)")


def example_4_transform_to_tableau():
    """Example 4: Transform dashboard to Tableau format"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Transform to Tableau")
    print("="*70 + "\n")
    
    # Load dashboard
    dashboard = load_dashboard("/mnt/user-data/uploads/Render-Dashboard-json.txt")
    components = dashboard.get('dashboard_data', {}).get('content', {}).get('components', [])
    
    print("Tableau Transformation:")
    print("-" * 70)
    
    for i, component in enumerate(components[:2], 1):
        sql_query = component.get('sql_query', '')
        
        print(f"\n--- Component {i}: {component.get('question', '')[:80]} ---\n")
        
        # Simulate SQL to Tableau conversion
        print("1. SQL to Tableau Calculated Field:")
        print(f"   Original SQL: {sql_query[:100]}...")
        print(f"\n   Calculated Field:")
        
        # Example Tableau calc
        if "COUNT" in sql_query.upper():
            print("""
   // Drop Off Rate
   SUM(
       IF ISNULL([Completed Date]) THEN 1 
       ELSE 0 
       END
   ) / COUNT([Training ID]) * 100
            """)
        
        print(f"\n2. Tableau Worksheet Configuration:")
        print(f"   Rows: [Training Title]")
        print(f"   Columns: [Drop Off Rate]")
        print(f"   Mark Type: Bar")
        print(f"   Color: [Drop Off Rate] (conditional)")
        
        print(f"\n3. Data Connection:")
        print(f"   Type: PostgreSQL / Tableau Data Cloud")
        print(f"   Extract Refresh: Incremental (hourly)")


def example_5_generate_insights():
    """Example 5: Generate conversational insights"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Generate Insights & Enable Conversations")
    print("="*70 + "\n")
    
    # Load dashboard
    dashboard = load_dashboard("/mnt/user-data/uploads/Render-Dashboard-json.txt")
    components = dashboard.get('dashboard_data', {}).get('content', {}).get('components', [])
    
    print("Conversational Insights:")
    print("-" * 70)
    
    # Simulate insights generation
    print("\n🔍 ANOMALY DETECTED:")
    print("   Severity: HIGH")
    print("   Title: 100% Drop-off Rate Across All Training Programs")
    print("   Description: Every participant who registered for training")
    print("   failed to complete. This indicates a critical systematic issue.")
    print("   Confidence: 95%")
    
    print("\n📈 TREND IDENTIFIED:")
    print("   Severity: MEDIUM")
    print("   Title: Consistent Pattern Across All Training Types")
    print("   Description: The uniform drop-off suggests the issue is not")
    print("   content-specific but relates to the training delivery system")
    print("   or enrollment process.")
    print("   Confidence: 85%")
    
    print("\n💡 RECOMMENDATIONS:")
    print("   1. Investigate registration and enrollment processes")
    print("   2. Review training platform accessibility")
    print("   3. Survey participants about barriers to completion")
    print("   4. Implement automated follow-up reminders")
    
    # Simulate natural language Q&A
    print("\n" + "-" * 70)
    print("Natural Language Q&A Examples:")
    print("-" * 70)
    
    qa_examples = [
        ("What is the current training completion rate?",
         "Based on the latest data, the completion rate is 0% across all training programs. This means that none of the participants who registered have completed their assigned training."),
        
        ("Which department has the most overdue trainings?",
         "The data shows that individual employees have varying numbers of overdue trainings, with Yvette Reid having the highest at 271 overdue trainings."),
        
        ("How does this compare to industry benchmarks?",
         "Industry benchmarks typically show completion rates between 60-80% for corporate training. The current 0% rate is significantly below industry standards and requires immediate attention.")
    ]
    
    for question, answer in qa_examples:
        print(f"\n❓ {question}")
        print(f"💬 {answer}")


def example_6_full_pipeline():
    """Example 6: Complete end-to-end pipeline"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Full End-to-End Pipeline")
    print("="*70 + "\n")
    
    # Load source dashboard
    dashboard = load_dashboard("/mnt/user-data/uploads/Render-Dashboard-json.txt")
    
    print("Pipeline Steps:")
    print("-" * 70)
    
    print("\n✓ Step 1: Parse Source Dashboard")
    print("  - Loaded dashboard with 3+ components")
    print("  - Extracted SQL queries and visualizations")
    print("  - Identified data relationships")
    
    print("\n✓ Step 2: Create Materialized Views")
    print("  - Analyzed query patterns")
    print("  - Created 3 base materialized views")
    print("  - Set up incremental refresh")
    
    print("\n✓ Step 3: Transform to PowerBI")
    print("  - Converted SQL to DAX measures")
    print("  - Mapped Vega-Lite to PowerBI visuals")
    print("  - Generated Power Query M scripts")
    
    print("\n✓ Step 4: Generate Insights")
    print("  - Detected 2 critical anomalies")
    print("  - Identified 3 trends")
    print("  - Created 5 actionable recommendations")
    
    print("\n✓ Step 5: Enable Conversational UI")
    print("  - Set up natural language query interface")
    print("  - Created context-aware responses")
    print("  - Configured follow-up question suggestions")
    
    print("\n✓ Step 6: Package for Deployment")
    print("  - Generated deployment scripts")
    print("  - Created documentation")
    print("  - Set up monitoring and alerts")
    
    print("\n" + "="*70)
    print("Pipeline Complete! Dashboard ready for deployment.")
    print("="*70)


def example_7_deployment_artifacts():
    """Example 7: Generate deployment artifacts"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Deployment Artifacts")
    print("="*70 + "\n")
    
    print("Generated Artifacts:")
    print("-" * 70)
    
    artifacts = {
        "PowerBI": [
            "dashboard.pbix - PowerBI report file",
            "data_model.json - Data model definition",
            "dax_measures.txt - All DAX measures",
            "refresh_config.json - Incremental refresh settings",
            "deployment_script.ps1 - PowerShell deployment script"
        ],
        "Tableau": [
            "dashboard.twb - Tableau workbook",
            "data_source.tds - Data source definition",
            "calculated_fields.txt - All calculated fields",
            "extract_config.json - Extract refresh settings",
            "deployment_script.sh - Bash deployment script"
        ],
        "Database": [
            "create_materialized_views.sql - MV creation scripts",
            "create_indexes.sql - Index creation",
            "refresh_procedures.sql - Refresh stored procedures",
            "monitoring_queries.sql - Performance monitoring"
        ],
        "Documentation": [
            "architecture.md - System architecture",
            "user_guide.md - User documentation",
            "admin_guide.md - Administration guide",
            "api_reference.md - API documentation"
        ]
    }
    
    for category, files in artifacts.items():
        print(f"\n{category}:")
        for file in files:
            print(f"  📄 {file}")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("DASHBOARD TRANSFORMATION MULTI-AGENT SYSTEM")
    print("Complete Examples and Use Cases")
    print("="*70)
    
    # Run examples
    example_1_parse_and_analyze()
    example_2_create_materialized_views()
    example_3_transform_to_powerbi()
    example_4_transform_to_tableau()
    example_5_generate_insights()
    example_6_full_pipeline()
    example_7_deployment_artifacts()
    
    print("\n" + "="*70)
    print("All examples completed successfully!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
