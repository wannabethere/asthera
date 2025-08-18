#!/usr/bin/env python3
"""
Example script demonstrating the report alert thread component functionality

This script shows how to:
1. Add alerts as thread message components to report workflows
2. Test and trigger alerts
3. Manage report-specific alert configurations
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import the app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.models.workflowmodels import (
    AlertThreadComponentCreate, AlertType, AlertSeverity, ComponentType
)

def create_example_report_alert_thread_components():
    """Create example alert thread components for report workflows"""
    
    print("🚨 Creating example report alert thread components...")
    
    # 1. Threshold Alert - Report generation time exceeds limit
    generation_time_alert = AlertThreadComponentCreate(
        question="Report Generation Time Alert",
        description="Alert when report generation takes longer than expected",
        alert_type=AlertType.THRESHOLD,
        severity=AlertSeverity.HIGH,
        condition_config={
            "field": "generation_time_seconds",
            "operator": ">",
            "threshold_value": 300  # 5 minutes
        },
        threshold_config={
            "unit": "seconds",
            "baseline": 180,
            "tolerance_percentage": 20
        },
        notification_channels=["email", "slack"],
        escalation_config={
            "escalate_after_minutes": 15,
            "escalate_to": ["dev-ops@company.com"]
        },
        cooldown_period=1800  # 30 minutes
    )
    
    # 2. Anomaly Alert - Unusual report access patterns
    access_pattern_alert = AlertThreadComponentCreate(
        question="Report Access Pattern Anomaly",
        description="Detect unusual patterns in report access",
        alert_type=AlertType.ANOMALY,
        severity=AlertSeverity.MEDIUM,
        condition_config={
            "field": "access_count",
            "method": "zscore"
        },
        anomaly_config={
            "method": "zscore",
            "sensitivity": 2.0,
            "baseline_period": "7d",
            "min_data_points": 20
        },
        notification_channels=["slack"],
        escalation_config={
            "escalate_after_minutes": 30,
            "escalate_to": ["security-team@company.com"]
        },
        cooldown_period=3600  # 1 hour
    )
    
    # 3. Trend Alert - Declining report quality scores
    quality_trend_alert = AlertThreadComponentCreate(
        question="Report Quality Decline",
        description="Alert when report quality scores show declining trend",
        alert_type=AlertType.TREND,
        severity=AlertSeverity.MEDIUM,
        condition_config={
            "field": "quality_score",
            "trend_direction": "decreasing",
            "period": "weekly"
        },
        trend_config={
            "trend_period": "4w",
            "min_trend_strength": 0.6,
            "baseline_period": "12w"
        },
        notification_channels=["email"],
        escalation_config={
            "escalate_after_minutes": 120,
            "escalate_to": ["quality-team@company.com"]
        },
        cooldown_period=86400  # 24 hours
    )
    
    # 4. Comparison Alert - Report size vs expected
    size_comparison_alert = AlertThreadComponentCreate(
        question="Report Size vs Expected",
        description="Compare actual report size against expected limits",
        alert_type=AlertType.COMPARISON,
        severity=AlertSeverity.LOW,
        condition_config={
            "field1": "actual_size_mb",
            "field2": "expected_size_mb",
            "operator": ">"
        },
        notification_channels=["email"],
        escalation_config={
            "escalate_after_minutes": 60,
            "escalate_to": ["storage-team@company.com"]
        },
        cooldown_period=7200  # 2 hours
    )
    
    # 5. Schedule Alert - Weekly report health check
    weekly_health_alert = AlertThreadComponentCreate(
        question="Weekly Report Health Check",
        description="Scheduled weekly check of report system health",
        alert_type=AlertType.SCHEDULE,
        severity=AlertSeverity.INFO,
        condition_config={
            "schedule_type": "weekly",
            "time": "10:00",
            "days": ["monday"]
        },
        notification_channels=["email", "slack"],
        escalation_config={
            "escalate_after_minutes": 0,
            "escalate_to": ["report-admin@company.com"]
        },
        cooldown_period=604800  # 1 week
    )
    
    alerts = [
        generation_time_alert,
        access_pattern_alert,
        quality_trend_alert,
        size_comparison_alert,
        weekly_health_alert
    ]
    
    print(f"✅ Created {len(alerts)} report alert thread components:")
    for i, alert in enumerate(alerts, 1):
        print(f"   {i}. {alert.question} ({alert.alert_type.value}) - {alert.severity.value}")
    
    return alerts

def demonstrate_report_alert_evaluation():
    """Demonstrate how report alert conditions are evaluated"""
    
    print("\n🔍 Demonstrating report alert condition evaluation...")
    
    # Example data for testing
    test_data = {
        "generation_time_seconds": 350,
        "access_count": 150,
        "quality_score": 0.75,
        "actual_size_mb": 25.5,
        "expected_size_mb": 20.0,
        "report_status": "completed"
    }
    
    print("   📊 Test data:")
    for key, value in test_data.items():
        print(f"      {key}: {value}")
    
    # Example threshold evaluation
    print("\n   🎯 Threshold Alert Example:")
    print("      Condition: generation_time_seconds > 300")
    print(f"      Actual: {test_data['generation_time_seconds']}")
    print(f"      Threshold: 300")
    print(f"      Result: {'TRIGGERED' if test_data['generation_time_seconds'] > 300 else 'NOT TRIGGERED'}")
    
    # Example comparison evaluation
    print("\n   ⚖️ Comparison Alert Example:")
    print("      Condition: actual_size_mb > expected_size_mb")
    print(f"      Actual Size: {test_data['actual_size_mb']}")
    print(f"      Expected Size: {test_data['expected_size_mb']}")
    print(f"      Result: {'TRIGGERED' if test_data['actual_size_mb'] > test_data['expected_size_mb'] else 'NOT TRIGGERED'}")
    
    return test_data

def show_report_alert_api_endpoints():
    """Show the available API endpoints for report alert thread component management"""
    
    print("\n🌐 Available API endpoints for report alert thread component management:")
    
    endpoints = [
        {
            "method": "POST",
            "path": "/api/v1/reports/{workflow_id}/alerts",
            "description": "Add an alert as a thread message component to a report workflow"
        },
        {
            "method": "GET",
            "path": "/api/v1/reports/{workflow_id}/alerts",
            "description": "Get all alert thread components for a report workflow"
        },
        {
            "method": "PATCH",
            "path": "/api/v1/reports/{workflow_id}/alerts/{component_id}",
            "description": "Update an existing alert thread component in a report workflow"
        },
        {
            "method": "DELETE",
            "path": "/api/v1/reports/{workflow_id}/alerts/{component_id}",
            "description": "Delete an alert thread component from a report workflow"
        },
        {
            "method": "POST",
            "path": "/api/v1/reports/{workflow_id}/alerts/{component_id}/test",
            "description": "Test an alert thread component in a report workflow with sample data"
        },
        {
            "method": "POST",
            "path": "/api/v1/reports/{workflow_id}/alerts/{component_id}/trigger",
            "description": "Manually trigger an alert thread component in a report workflow for testing"
        }
    ]
    
    for endpoint in endpoints:
        print(f"   {endpoint['method']} {endpoint['path']}")
        print(f"      {endpoint['description']}")
        print()

def show_report_specific_alert_features():
    """Show report-specific alert features and use cases"""
    
    print("\n📊 Report-Specific Alert Features:")
    
    features = [
        {
            "name": "Report Generation Monitoring",
            "description": "Monitor report generation time, success rates, and failures",
            "alert_types": ["threshold", "anomaly"],
            "use_cases": ["Performance monitoring", "Resource optimization", "Error detection"]
        },
        {
            "name": "Data Quality Alerts",
            "description": "Track data quality metrics and trends in reports",
            "alert_types": ["trend", "threshold"],
            "use_cases": ["Data validation", "Quality assurance", "Compliance monitoring"]
        },
        {
            "name": "Access Pattern Monitoring",
            "description": "Detect unusual access patterns and potential security issues",
            "alert_types": ["anomaly", "threshold"],
            "use_cases": ["Security monitoring", "Usage analytics", "Compliance tracking"]
        },
        {
            "name": "Storage and Performance",
            "description": "Monitor report sizes, storage usage, and performance metrics",
            "alert_types": ["comparison", "threshold"],
            "use_cases": ["Capacity planning", "Performance optimization", "Cost management"]
        },
        {
            "name": "Scheduled Health Checks",
            "description": "Regular automated health checks of the report system",
            "alert_types": ["schedule"],
            "use_cases": ["System maintenance", "Proactive monitoring", "Compliance reporting"]
        }
    ]
    
    for feature in features:
        print(f"\n   🔧 {feature['name']}")
        print(f"      Description: {feature['description']}")
        print(f"      Alert Types: {', '.join(feature['alert_types'])}")
        print(f"      Use Cases: {', '.join(feature['use_cases'])}")

def show_report_alert_configuration_examples():
    """Show practical examples of report alert configurations"""
    
    print("\n📝 Practical Report Alert Configuration Examples:")
    
    examples = [
        {
            "name": "Report Generation Timeout",
            "type": "threshold",
            "description": "Monitor when report generation exceeds time limits",
            "config": {
                "field": "generation_time_seconds",
                "operator": ">",
                "threshold_value": 600,
                "severity": "high",
                "channels": ["email", "slack"]
            }
        },
        {
            "name": "Data Source Failure",
            "type": "anomaly",
            "description": "Detect unusual patterns in data source failures",
            "config": {
                "field": "failure_rate",
                "method": "zscore",
                "sensitivity": 2.5,
                "severity": "critical",
                "channels": ["slack", "webhook"]
            }
        },
        {
            "name": "Report Quality Decline",
            "type": "trend",
            "description": "Monitor declining report quality scores",
            "config": {
                "field": "quality_score",
                "trend_direction": "decreasing",
                "period": "weekly",
                "severity": "medium",
                "channels": ["email"]
            }
        },
        {
            "name": "Storage Usage vs Budget",
            "type": "comparison",
            "description": "Compare actual storage usage against budget limits",
            "config": {
                "field1": "actual_storage_gb",
                "field2": "budget_storage_gb",
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
    """Main function to run the report alert thread component example"""
    
    print("🚨 Report Alert Thread Component Example")
    print("=" * 50)
    
    try:
        # Create example report alert thread components
        alerts = create_example_report_alert_thread_components()
        
        # Demonstrate alert evaluation
        test_data = demonstrate_report_alert_evaluation()
        
        # Show API endpoints
        show_report_alert_api_endpoints()
        
        # Show report-specific features
        show_report_specific_alert_features()
        
        # Show practical examples
        show_report_alert_configuration_examples()
        
        print("\n✅ Report alert thread component example completed successfully!")
        print(f"\n📊 Created {len(alerts)} report alert thread components:")
        for alert in alerts:
            print(f"   • {alert.question} ({alert.alert_type.value})")
        
        print("\n🚀 Key Features:")
        print("   • Alerts are added as thread message components to report workflows")
        print("   • Multiple alert types: threshold, anomaly, trend, comparison, schedule")
        print("   • Report-specific monitoring (generation time, quality, access patterns)")
        print("   • Configurable severity levels and notification channels")
        print("   • Escalation rules and cooldown periods")
        print("   • Comprehensive API for management")
        print("   • Testing and manual triggering capabilities")
        
        print("\n🔧 Next Steps:")
        print("   • Integrate with your report workflows")
        print("   • Configure real notification channels")
        print("   • Implement sophisticated anomaly detection algorithms")
        print("   • Set up monitoring and alerting dashboards")
        print("   • Customize alert conditions for your specific report types")
        
    except Exception as e:
        print(f"\n❌ Error running report alert thread component example: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
