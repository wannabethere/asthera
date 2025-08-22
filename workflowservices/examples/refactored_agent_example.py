#!/usr/bin/env python3
"""
Example script demonstrating the refactored Report Writing Agent
that works independently without database dependencies.
"""

import sys
import os
from datetime import datetime

# Add the app directory to the path so we can import the agent
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))

from agents.report_writing_agent import (
    create_report_writing_agent,
    ThreadComponentData,
    ReportWorkflowData,
    ComponentType,
    WriterActorType,
    BusinessGoal
)


def create_sample_data():
    """Create sample data for demonstration"""
    
    # Create workflow data
    workflow_data = ReportWorkflowData(
        id="demo-workflow-001",
        report_id="demo-report-001",
        user_id="demo-user-001",
        state="active",
        current_step=2,
        workflow_metadata={
            "priority": "high",
            "department": "sales",
            "tags": ["quarterly", "performance", "demo"]
        },
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Create thread components
    thread_components = [
        ThreadComponentData(
            id="comp-001",
            component_type=ComponentType.QUESTION,
            sequence_order=1,
            question="What are the key performance indicators for Q4 sales?",
            description="Analysis of Q4 sales KPIs across all regions and product lines",
            created_at=datetime.now()
        ),
        ThreadComponentData(
            id="comp-002",
            component_type=ComponentType.CHART,
            sequence_order=2,
            chart_config={
                "type": "line",
                "title": "Q4 Sales Trend",
                "data_source": "sales_analytics",
                "x_axis": "Month",
                "y_axis": "Sales Volume"
            },
            description="Q4 sales trend visualization showing month-over-month performance",
            created_at=datetime.now()
        ),
        ThreadComponentData(
            id="comp-003",
            component_type=ComponentType.TABLE,
            sequence_order=3,
            table_config={
                "type": "summary",
                "columns": ["Region", "Q4 Sales", "Growth %", "Target"],
                "data_source": "regional_sales_data"
            },
            description="Regional sales performance summary table",
            created_at=datetime.now()
        ),
        ThreadComponentData(
            id="comp-004",
            component_type=ComponentType.INSIGHT,
            sequence_order=4,
            overview={
                "insight_type": "trend_analysis",
                "confidence": 0.85,
                "key_factors": ["seasonal demand", "marketing campaigns", "product launches"]
            },
            description="Key insights from Q4 sales analysis",
            created_at=datetime.now()
        )
    ]
    
    # Create business goal
    business_goal = BusinessGoal(
        primary_objective="Optimize Q4 sales performance and identify growth opportunities",
        target_audience=[
            "Sales Executives",
            "Regional Managers", 
            "Marketing Team",
            "Product Managers"
        ],
        decision_context="Q4 planning and resource allocation for next fiscal year",
        success_metrics=[
            "Sales growth rate",
            "Market share increase",
            "Customer acquisition cost",
            "Revenue per region",
            "Product performance"
        ],
        timeframe="Q4 2024 and Q1 2025 planning",
        risk_factors=[
            "Economic uncertainty",
            "Supply chain disruptions",
            "Competitive pressure",
            "Seasonal fluctuations"
        ]
    )
    
    return workflow_data, thread_components, business_goal


def demonstrate_agent_usage():
    """Demonstrate how to use the refactored agent"""
    
    print("🚀 Refactored Report Writing Agent Demo")
    print("=" * 50)
    
    # Create sample data
    print("\n📊 Creating sample data...")
    workflow_data, thread_components, business_goal = create_sample_data()
    
    print(f"✅ Created workflow: {workflow_data.id}")
    print(f"✅ Created {len(thread_components)} thread components")
    print(f"✅ Created business goal: {business_goal.primary_objective}")
    
    # Create the agent
    print("\n🤖 Creating report writing agent...")
    try:
        agent = create_report_writing_agent()
        print("✅ Agent created successfully!")
        print(f"   - LLM: {type(agent.llm).__name__}")
        print(f"   - Embeddings: {type(agent.embeddings).__name__}")
        print(f"   - RAG System: {type(agent.rag_system).__name__}")
        print(f"   - Quality Evaluator: {type(agent.quality_evaluator).__name__}")
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        print("   This might be due to missing API keys or dependencies")
        return
    
    # Demonstrate data class operations
    print("\n🔍 Demonstrating data class operations...")
    
    # Show component details
    for i, comp in enumerate(thread_components, 1):
        print(f"   Component {i}: {comp.component_type.value}")
        if comp.question:
            print(f"     Question: {comp.question[:60]}...")
        if comp.description:
            print(f"     Description: {comp.description[:60]}...")
    
    # Show business goal details
    print(f"\n   Business Goal: {business_goal.primary_objective}")
    print(f"   Target Audience: {', '.join(business_goal.target_audience[:3])}...")
    print(f"   Timeframe: {business_goal.timeframe}")
    
    # Demonstrate the new API structure
    print("\n📝 Demonstrating new API structure...")
    print("   Before: generate_report(workflow_id, writer_actor, business_goal)")
    print("   After:  generate_report(workflow_data, thread_components, writer_actor, business_goal)")
    
    # Show how to use different writer actors
    print("\n👥 Available writer actors:")
    for actor in WriterActorType:
        print(f"   - {actor.value}")
    
    # Show how to use different component types
    print("\n🔧 Available component types:")
    for comp_type in ComponentType:
        print(f"   - {comp_type.value}")
    
    print("\n✨ Demo completed successfully!")
    print("\nThe refactored agent is now completely independent of database models.")
    print("You can use it with any data structure that matches the defined data classes.")


def show_migration_example():
    """Show how to migrate from the old database-dependent version"""
    
    print("\n🔄 Migration Example")
    print("=" * 30)
    
    print("""
# OLD WAY (Database dependent):
from app.models.workflowmodels import ReportWorkflow, ThreadComponent
from app.core.dependencies import get_db

db = next(get_db())
workflow = db.query(ReportWorkflow).filter(ReportWorkflow.id == workflow_id).first()
components = db.query(ThreadComponent).filter(
    ThreadComponent.report_workflow_id == workflow_id
).all()

result = agent.generate_report(workflow_id, writer_actor, business_goal)
""")
    
    print("""
# NEW WAY (Database independent):
from agents.report_writing_agent import ThreadComponentData, ReportWorkflowData

# Convert your data to data classes
workflow_data = ReportWorkflowData(
    id=str(workflow.id),
    report_id=str(workflow.report_id),
    state=workflow.state.value
)

thread_components = [
    ThreadComponentData(
        id=str(comp.id),
        component_type=comp.component_type,
        sequence_order=comp.sequence_order,
        question=comp.question,
        description=comp.description
    ) for comp in components
]

result = agent.generate_report(
    workflow_data, thread_components, writer_actor, business_goal
)
""")


if __name__ == "__main__":
    try:
        demonstrate_agent_usage()
        show_migration_example()
        
        print("\n🎉 All demonstrations completed!")
        print("\nTo use the refactored agent in your code:")
        print("1. Import the agent and data classes")
        print("2. Create your data using the data classes")
        print("3. Call generate_report() with your data")
        print("4. No database connection required!")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        print("This might be due to missing dependencies or configuration.")
        print("Check the README for setup instructions.")
