#!/usr/bin/env python3
"""
Example script demonstrating the alert thread component functionality

This script shows how to:
1. Add alerts as thread message components to dashboard workflows
2. Test and trigger alerts
3. Generate n8n workflows with alert nodes
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import the app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.models.workflowmodels import (
    AlertThreadComponentCreate, AlertType, AlertSeverity, ComponentType
)

def create_example_alert_thread_components():
    """Create example alert thread components for different use cases"""
    
    print("🚨 Creating example alert thread components...")
    
    # 1. Threshold Alert - Revenue drops below target
    revenue_threshold_alert = AlertThreadComponentCreate(
        question="Revenue Drop Alert",
        description="Alert when monthly revenue drops below target threshold",
        alert_type=AlertType.THRESHOLD,
        severity=AlertSeverity.HIGH,
        condition_config={
            "field": "monthly_revenue",
            "operator": "<",
            "threshold_value": 100000
        },
        threshold_config={
            "unit": "USD",
            "baseline": 120000,
            "tolerance_percentage": 10
        },
        notification_channels=["email", "slack"],
        escalation_config={
            "escalate_after_minutes": 30,
            "escalate_to": ["sales-manager@company.com"]
        },
        cooldown_period=3600  # 1 hour
    )
    
    # 2. Anomaly Alert - Unusual user activity
    user_anomaly_alert = AlertThreadComponentCreate(
        question="User Activity Anomaly",
        description="Detect unusual patterns in user activity",
        alert_type=AlertType.ANOMALY,
        severity=AlertSeverity.MEDIUM,
        condition_config={
            "field": "active_users",
            "method": "zscore"
        },
        anomaly_config={
            "method": "zscore",
            "sensitivity": 2.5,
            "baseline_period": "7d",
            "min_data_points": 30
        },
        notification_channels=["slack", "webhook"],
        escalation_config={
            "escalate_after_minutes": 15,
            "escalate_to": ["dev-team@company.com"]
        },
        cooldown_period=1800  # 30 minutes
    )
    
    # 3. Trend Alert - Declining conversion rates
    conversion_trend_alert = AlertThreadComponentCreate(
        question="Conversion Rate Decline",
        description="Alert when conversion rates show declining trend",
        alert_type=AlertType.TREND,
        severity=AlertSeverity.MEDIUM,
        condition_config={
            "field": "conversion_rate",
            "trend_direction": "decreasing",
            "period": "daily"
        },
        trend_config={
            "trend_period": "7d",
            "min_trend_strength": 0.7,
            "baseline_period": "30d"
        },
        notification_channels=["email", "slack"],
        escalation_config={
            "escalate_after_minutes": 60,
            "escalate_to": ["marketing-team@company.com"]
        },
        cooldown_period=7200  # 2 hours
    )
    
    # 4. Comparison Alert - Performance vs Benchmark
    performance_comparison_alert = AlertThreadComponentCreate(
        question="Performance vs Benchmark",
        description="Compare performance metrics against industry benchmarks",
        alert_type=AlertType.COMPARISON,
        severity=AlertSeverity.LOW,
        condition_config={
            "field1": "our_performance",
            "field2": "industry_benchmark",
            "operator": "<"
        },
        notification_channels=["email"],
        escalation_config={
            "escalate_after_minutes": 120,
            "escalate_to": ["analytics-team@company.com"]
        },
        cooldown_period=14400  # 4 hours
    )
    
    # 5. Schedule Alert - Daily system health check
    system_health_alert = AlertThreadComponentCreate(
        question="Daily System Health Check",
        description="Scheduled daily check of system health metrics",
        alert_type=AlertType.SCHEDULE,
        severity=AlertSeverity.INFO,
        condition_config={
            "schedule_type": "daily",
            "time": "09:00",
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
        },
        notification_channels=["email", "slack"],
        escalation_config={
            "escalate_after_minutes": 0,
            "escalate_to": ["ops-team@company.com"]
        },
        cooldown_period=86400  # 24 hours
    )
    
    alerts = [
        revenue_threshold_alert,
        user_anomaly_alert,
        conversion_trend_alert,
        performance_comparison_alert,
        system_health_alert
    ]
    
    print(f"✅ Created {len(alerts)} alert thread components:")
    for i, alert in enumerate(alerts, 1):
        print(f"   {i}. {alert.question} ({alert.alert_type.value}) - {alert.severity.value}")
    
    return alerts

def demonstrate_alert_evaluation():
    """Demonstrate how alert conditions are evaluated"""
    
    print("\n🔍 Demonstrating alert condition evaluation...")
    
    # Example data for testing
    test_data = {
        "monthly_revenue": 95000,
        "active_users": 1500,
        "conversion_rate": 0.025,
        "our_performance": 0.85,
        "industry_benchmark": 0.90,
        "system_uptime": 99.9
    }
    
    print("   📊 Test data:")
    for key, value in test_data.items():
        print(f"      {key}: {value}")
    
    # Example threshold evaluation
    print("\n   🎯 Threshold Alert Example:")
    print("      Condition: monthly_revenue < 100000")
    print(f"      Actual: {test_data['monthly_revenue']}")
    print(f"      Threshold: 100000")
    print(f"      Result: {'TRIGGERED' if test_data['monthly_revenue'] < 100000 else 'NOT TRIGGERED'}")
    
    # Example comparison evaluation
    print("\n   ⚖️ Comparison Alert Example:")
    print("      Condition: our_performance < industry_benchmark")
    print(f"      Our Performance: {test_data['our_performance']}")
    print(f"      Industry Benchmark: {test_data['industry_benchmark']}")
    print(f"      Result: {'TRIGGERED' if test_data['our_performance'] < test_data['industry_benchmark'] else 'NOT TRIGGERED'}")
    
    return test_data

def show_alert_api_endpoints():
    """Show the available API endpoints for alert thread component management"""
    
    print("\n🌐 Available API endpoints for alert thread component management:")
    
    endpoints = [
        {
            "method": "POST",
            "path": "/api/v1/workflows/{workflow_id}/alerts",
            "description": "Add an alert as a thread message component to a workflow"
        },
        {
            "method": "PATCH",
            "path": "/api/v1/workflows/{workflow_id}/alerts/{component_id}",
            "description": "Update an existing alert thread component"
        },
        {
            "method": "POST",
            "path": "/api/v1/workflows/{workflow_id}/alerts/{component_id}/test",
            "description": "Test an alert thread component with sample data"
        },
        {
            "method": "POST",
            "path": "/api/v1/workflows/{workflow_id}/alerts/{component_id}/trigger",
            "description": "Manually trigger an alert thread component for testing"
        }
    ]
    
    for endpoint in endpoints:
        print(f"   {endpoint['method']} {endpoint['path']}")
        print(f"      {endpoint['description']}")
        print()

def show_n8n_integration():
    """Show how alert thread components integrate with n8n workflows"""
    
    print("\n🔗 N8N Workflow Integration:")
    
    print("   📋 Alert thread components are automatically converted to n8n nodes:")
    
    alert_node_types = [
        {
            "type": "Threshold Alert",
            "description": "Code node with threshold evaluation logic",
            "position": "After data processing, before sharing"
        },
        {
            "type": "Anomaly Alert",
            "description": "Code node with statistical anomaly detection",
            "position": "After data processing, before sharing"
        },
        {
            "type": "Trend Alert",
            "description": "Code node with trend analysis logic",
            "position": "After data processing, before sharing"
        },
        {
            "type": "Comparison Alert",
            "description": "Code node with comparison evaluation logic",
            "position": "After data processing, before sharing"
        },
        {
            "type": "Schedule Alert",
            "description": "Trigger node with scheduled execution",
            "position": "Workflow start, triggers other nodes"
        }
    ]
    
    for node in alert_node_types:
        print(f"      • {node['type']}: {node['description']}")
        print(f"        Position: {node['position']}")
    
    print("\n   🔄 Workflow execution flow:")
    print("      1. Trigger (schedule/manual)")
    print("      2. Data processing components")
    print("      3. Alert evaluation nodes (from thread components)")
    print("      4. Notification sharing")
    print("      5. External integrations")

def show_alert_configuration_examples():
    """Show practical examples of alert thread component configurations"""
    
    print("\n📝 Practical Alert Thread Component Examples:")
    
    examples = [
        {
            "name": "Sales Performance Alert",
            "type": "threshold",
            "description": "Monitor daily sales against targets",
            "config": {
                "field": "daily_sales",
                "operator": "<",
                "threshold_value": 5000,
                "severity": "high",
                "channels": ["email", "slack"]
            }
        },
        {
            "name": "System Error Rate Alert",
            "type": "anomaly",
            "description": "Detect unusual error rates in system logs",
            "config": {
                "field": "error_rate",
                "method": "zscore",
                "sensitivity": 2.0,
                "severity": "critical",
                "channels": ["slack", "webhook"]
            }
        },
        {
            "name": "Customer Satisfaction Trend",
            "type": "trend",
            "description": "Monitor declining customer satisfaction scores",
            "config": {
                "field": "satisfaction_score",
                "trend_direction": "decreasing",
                "period": "weekly",
                "severity": "medium",
                "channels": ["email"]
            }
        },
        {
            "name": "Budget vs Actual Spending",
            "type": "comparison",
            "description": "Compare actual spending against budget limits",
            "config": {
                "field1": "actual_spending",
                "field2": "budget_limit",
                "operator": ">",
                "severity": "high",
                "channels": ["email", "slack"]
            }
        }
    ]
    
    for example in examples:
        print(f"\n   📊 {example['name']}")
        print(f"      Type: {example['type']}")
        print(f"      Description: {example['description']}")
        print(f"      Configuration: {example['config']}")

def main():
    """Main function to run the alert thread component example"""
    
    print("🚨 Alert Thread Component Example")
    print("=" * 50)
    
    try:
        # Create example alert thread components
        alerts = create_example_alert_thread_components()
        
        # Demonstrate alert evaluation
        test_data = demonstrate_alert_evaluation()
        
        # Show API endpoints
        show_alert_api_endpoints()
        
        # Show n8n integration
        show_n8n_integration()
        
        # Show practical examples
        show_alert_configuration_examples()
        
        print("\n✅ Alert thread component example completed successfully!")
        print(f"\n📊 Created {len(alerts)} alert thread components:")
        for alert in alerts:
            print(f"   • {alert.question} ({alert.alert_type.value})")
        
        print("\n🚀 Key Features:")
        print("   • Alerts are added as thread message components")
        print("   • Multiple alert types: threshold, anomaly, trend, comparison, schedule")
        print("   • Configurable severity levels and notification channels")
        print("   • Escalation rules and cooldown periods")
        print("   • Automatic n8n workflow integration")
        print("   • Comprehensive API for management")
        print("   • Testing and manual triggering capabilities")
        
        print("\n🔧 Next Steps:")
        print("   • Integrate with your dashboard workflows")
        print("   • Configure real notification channels")
        print("   • Implement sophisticated anomaly detection algorithms")
        print("   • Set up monitoring and alerting dashboards")
        
    except Exception as e:
        print(f"\n❌ Error running alert thread component example: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
