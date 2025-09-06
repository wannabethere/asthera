"""
Complete Example: Training Completion Alert Generation
This demonstrates the full workflow for your specific training data use case.
"""

import asyncio
import json
from datetime import datetime
from sql_to_alert_agent import SQLToAlertAgent, SQLAlertRequest
from sql_alert_fastapi_service import SQLAlertAPIRequest

# Your original data request
training_request_data = {
    "sql": """SELECT tr.training_type AS "Training Type", 
              COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) AS "Assigned Count", 
              COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) AS "Completed Count", 
              COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) AS "Expired Count", 
              (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Assigned') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Assigned Percentage", 
              (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Completed') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Completed Percentage", 
              (COUNT(CASE WHEN lower(tr.transcript_status) = lower('Expired') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS "Expired Percentage" 
              FROM csod_training_records AS tr GROUP BY tr.training_type""",
    "query": "What are the percentages of training activities by ActivityType and show their Training Statuses (Assigned, Completed, Expired)",
    "project_id": "cornerstone",
    "data_description": "CSOD training records showing completion status by training type",
    "configuration": {"additionalProp1": {}},
    "alert_request": "Alert me for the groups that have percentage of activities not completed greater than 10"
}

class TrainingAlertExamples:
    """Complete examples for training completion alerts"""
    
    def __init__(self):
        self.agent = None
    
    async def initialize(self):
        """Initialize the agent"""
        self.agent = SQLToAlertAgent()
        print("✅ SQL-to-Alert Agent initialized")
    
    async def example_1_basic_completion_alert(self):
        """Example 1: Basic completion rate alert"""
        print("\n--- Example 1: Basic Completion Rate Alert ---")
        
        request = SQLAlertRequest(
            sql=training_request_data["sql"],
            query=training_request_data["query"],
            project_id=training_request_data["project_id"], 
            data_description=training_request_data["data_description"],
            alert_request="Alert me when completion percentage is less than 90% for any training type",
            session_id="training_completion_session"
        )
        
        result = await self.agent.generate_alert(request)
        
        print(f"🎯 Generated Alert: {result.feed_configuration.notification.metric_name}")
        print(f"📊 Metric: {result.feed_configuration.metric.measure}")
        print(f"🎚️ Condition: {result.feed_configuration.condition.condition_type.value}")
        print(f"🔢 Threshold: {result.feed_configuration.condition.operator} {result.feed_configuration.condition.value}")
        print(f"📅 Schedule: {result.feed_configuration.notification.schedule_type.value}")
        print(f"🎯 Dimensions: {result.feed_configuration.metric.drilldown_dimensions}")
        print(f"⭐ Confidence: {result.confidence_score:.2f}")
        
        # Show Tellius API payload
        tellius_payload = self.agent.create_tellius_api_payload(result)
        print(f"\n📡 Tellius API Payload (First 500 chars):")
        print(json.dumps(tellius_payload, indent=2)[:500] + "...")
        
        return result
    
    async def example_2_multiple_condition_alert(self):
        """Example 2: Multiple condition alert (completion + expiry)"""
        print("\n--- Example 2: Multiple Condition Alert ---")
        
        request = SQLAlertRequest(
            sql=training_request_data["sql"],
            query=training_request_data["query"],
            project_id=training_request_data["project_id"],
            data_description=training_request_data["data_description"],
            alert_request="Alert me when completion percentage is below 85% OR expired percentage is above 15% for any training type",
            session_id="multi_condition_session"
        )
        
        result = await self.agent.generate_alert(request)
        
        print(f"🎯 Generated Alert: {result.feed_configuration.notification.metric_name}")
        print(f"📊 Primary Metric: {result.feed_configuration.metric.measure}")
        print(f"🎚️ Condition Type: {result.feed_configuration.condition.condition_type.value}")
        print(f"📧 Notification: {result.feed_configuration.notification.email_message}")
        print(f"⭐ Confidence: {result.confidence_score:.2f}")
        
        return result
    
    async def example_3_anomaly_detection_alert(self):
        """Example 3: Anomaly detection for training patterns"""
        print("\n--- Example 3: Anomaly Detection Alert ---")
        
        request = SQLAlertRequest(
            sql=training_request_data["sql"],
            query=training_request_data["query"],
            project_id=training_request_data["project_id"],
            data_description=training_request_data["data_description"],
            alert_request="Use intelligent anomaly detection to alert me about unusual patterns in training completion rates",
            session_id="anomaly_detection_session"
        )
        
        result = await self.agent.generate_alert(request)
        
        print(f"🤖 AI-Powered Alert: {result.feed_configuration.notification.metric_name}")
        print(f"🧠 Uses ARIMA: {result.feed_configuration.condition.condition_type == 'intelligent_arima'}")
        print(f"📊 Tracking: {result.feed_configuration.metric.measure}")
        print(f"🎯 Dimensions: {result.feed_configuration.metric.drilldown_dimensions}")
        print(f"⭐ Confidence: {result.confidence_score:.2f}")
        
        return result
    
    async def example_4_trend_analysis_alert(self):
        """Example 4: Trend-based alert for declining completion"""
        print("\n--- Example 4: Trend Analysis Alert ---")
        
        request = SQLAlertRequest(
            sql=training_request_data["sql"],
            query=training_request_data["query"],
            project_id=training_request_data["project_id"],
            data_description=training_request_data["data_description"],
            alert_request="Alert me weekly if training completion rates are declining by more than 5% compared to previous week",
            session_id="trend_analysis_session"
        )
        
        result = await self.agent.generate_alert(request)
        
        print(f"📈 Trend Alert: {result.feed_configuration.notification.metric_name}")
        print(f"📊 Tracking Changes In: {result.feed_configuration.metric.measure}")
        print(f"🎚️ Condition: {result.feed_configuration.condition.condition_type.value}")
        print(f"📅 Resolution: {result.feed_configuration.metric.resolution}")
        print(f"⭐ Confidence: {result.confidence_score:.2f}")
        
        return result
    
    async def demonstrate_sql_analysis(self):
        """Show detailed SQL analysis capabilities"""
        print("\n--- SQL Analysis Demonstration ---")
        
        request = SQLAlertRequest(
            sql=training_request_data["sql"],
            query=training_request_data["query"],
            project_id=training_request_data["project_id"],
            data_description=training_request_data["data_description"],
            alert_request="Analyze this SQL for alert opportunities"
        )
        
        # Get just the SQL analysis
        inputs = {"request": request}
        sql_analysis = await self.agent._analyze_sql(inputs)
        
        print(f"🗄️ Tables Identified: {sql_analysis.tables}")
        print(f"📊 Metrics Found: {sql_analysis.metrics}")
        print(f"🎯 Dimensions: {sql_analysis.dimensions}")
        print(f"🔍 Filters: {sql_analysis.filters}")
        print(f"🔢 Aggregations: {sql_analysis.aggregations}")
        print(f"🏢 Business View: {sql_analysis.business_view_name}")
        
        return sql_analysis
    
    def create_tellius_feed_json(self, result):
        """Create the final Tellius Feed JSON for API submission"""
        
        config = result.feed_configuration
        
        tellius_feed = {
            "feed": {
                "name": config.notification.metric_name,
                "description": config.notification.email_message,
                "metric": {
                    "businessView": config.metric.business_view,
                    "measure": config.metric.measure,
                    "aggregation": config.metric.aggregation,
                    "resolution": config.metric.resolution
                },
                "condition": {
                    "type": config.condition.condition_type.value,
                    "operator": config.condition.operator.value if config.condition.operator else None,
                    "value": config.condition.value
                },
                "filters": config.metric.filters,
                "drilldownDimensions": config.metric.drilldown_dimensions,
                "notification": {
                    "scheduleType": config.notification.schedule_type.value,
                    "emailAddresses": config.notification.email_addresses or ["admin@company.com"],
                    "subject": config.notification.subject,
                    "message": config.notification.email_message,
                    "includeFeedReport": config.notification.include_feed_report
                },
                "columnSelection": {
                    "included": config.column_selection.get("included", []),
                    "excluded": config.column_selection.get("excluded", [])
                }
            }
        }
        
        return tellius_feed

async def run_complete_demo():
    """Run the complete demonstration"""
    
    print("🚀 Starting SQL-to-Alert Complete Demonstration")
    print("=" * 60)
    
    examples = TrainingAlertExamples()
    await examples.initialize()
    
    # Run all examples
    results = []
    
    # Example 1: Basic completion alert
    result1 = await examples.example_1_basic_completion_alert()
    results.append(("Basic Completion Alert", result1))
    
    # Example 2: Multiple condition alert  
    result2 = await examples.example_2_multiple_condition_alert()
    results.append(("Multiple Condition Alert", result2))
    
    # Example 3: Anomaly detection
    result3 = await examples.example_3_anomaly_detection_alert()
    results.append(("Anomaly Detection Alert", result3))
    
    # Example 4: Trend analysis
    result4 = await examples.example_4_trend_analysis_alert()
    results.append(("Trend Analysis Alert", result4))
    
    # SQL Analysis demo
    sql_analysis = await examples.demonstrate_sql_analysis()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY OF GENERATED ALERTS")
    print("=" * 60)
    
    for i, (name, result) in enumerate(results, 1):
        print(f"\n{i}. {name}")
        print(f"   📊 Metric: {result.feed_configuration.metric.measure}")
        print(f"   🎚️ Condition: {result.feed_configuration.condition.condition_type.value}")
        print(f"   ⭐ Confidence: {result.confidence_score:.2f}")
        print(f"   📧 Schedule: {result.feed_configuration.notification.schedule_type.value}")
    
    # Create sample Tellius Feed JSON
    print(f"\n🔗 Sample Tellius Feed Configuration:")
    sample_feed = examples.create_tellius_feed_json(results[0][1])
    print(json.dumps(sample_feed, indent=2))
    
    print(f"\n✅ Demonstration completed successfully!")
    print(f"Generated {len(results)} different alert configurations")
    print(f"All alerts are ready for Tellius Feed integration")

# FastAPI Integration Examples
class FastAPIExamples:
    """Examples of using the FastAPI service"""
    
    @staticmethod
    def curl_examples():
        """Generate curl examples for the API"""
        
        examples = {
            "basic_training_alert": {
                "description": "Basic training completion alert",
                "curl": """
curl -X POST "http://localhost:8001/api/sql-alerts/generate" \\
  -H "Content-Type: application/json" \\
  -d '{
    "sql": "SELECT tr.training_type AS \\"Training Type\\", COUNT(CASE WHEN lower(tr.transcript_status) = lower(\\'Completed\\') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS \\"Completed Percentage\\" FROM csod_training_records AS tr GROUP BY tr.training_type",
    "query": "Training completion percentages by type", 
    "project_id": "cornerstone",
    "data_description": "Training completion tracking",
    "alert_request": "Alert when completion rate is below 90%"
  }'
                """
            },
            
            "specialized_training_endpoint": {
                "description": "Using specialized training endpoint",
                "curl": """
curl -X POST "http://localhost:8001/api/sql-alerts/training-completion" \\
  -H "Content-Type: application/json" \\
  -d '{
    "sql": "SELECT tr.training_type, tr.transcript_status FROM csod_training_records tr",
    "completion_threshold": 85.0,
    "expiry_threshold": 15.0
  }'
                """
            },
            
            "anomaly_detection": {
                "description": "Anomaly detection for training patterns",
                "curl": """
curl -X POST "http://localhost:8001/api/sql-alerts/percentage-anomaly" \\
  -H "Content-Type: application/json" \\
  -d '{
    "sql": "SELECT training_type, completion_percentage FROM training_metrics",
    "metric_name": "Training Completion Rate"
  }'
                """
            },
            
            "batch_processing": {
                "description": "Batch processing multiple alerts",
                "curl": """
curl -X POST "http://localhost:8001/api/sql-alerts/batch" \\
  -H "Content-Type: application/json" \\
  -d '{
    "alerts": [
      {
        "sql": "SELECT * FROM training_table1",
        "query": "Training query 1",
        "project_id": "proj1",
        "alert_request": "Alert for condition 1"
      },
      {
        "sql": "SELECT * FROM training_table2", 
        "query": "Training query 2",
        "project_id": "proj2",
        "alert_request": "Alert for condition 2"
      }
    ],
    "parallel_processing": true,
    "max_concurrent": 3
  }'
                """
            }
        }
        
        return examples

# Configuration Templates
class ConfigurationTemplates:
    """Pre-built configuration templates for common scenarios"""
    
    @staticmethod
    def training_completion_templates():
        """Training completion alert templates"""
        
        return {
            "low_completion_rate": {
                "name": "Low Training Completion Rate Alert",
                "description": "Alert when training completion falls below acceptable levels",
                "tellius_config": {
                    "metric": {
                        "measure": "Completed Percentage",
                        "aggregation": "AVG",
                        "resolution": "Daily",
                        "drilldown_dimensions": ["Training Type", "Department"]
                    },
                    "condition": {
                        "condition_type": "threshold_value",
                        "operator": "<",
                        "value": 90.0
                    },
                    "notification": {
                        "schedule_type": "with_data_refresh",
                        "subject": "Training Completion Rate Below Threshold"
                    }
                }
            },
            
            "high_expiry_rate": {
                "name": "High Training Expiry Alert",
                "description": "Alert when training expiry rate exceeds normal levels",
                "tellius_config": {
                    "metric": {
                        "measure": "Expired Percentage", 
                        "aggregation": "MAX",
                        "resolution": "Weekly",
                        "drilldown_dimensions": ["Training Type"]
                    },
                    "condition": {
                        "condition_type": "threshold_value",
                        "operator": ">",
                        "value": 10.0
                    },
                    "notification": {
                        "schedule_type": "custom_schedule",
                        "subject": "Training Expiry Rate Alert"
                    }
                }
            },
            
            "assignment_backlog": {
                "name": "Training Assignment Backlog Alert",
                "description": "Alert when too many trainings remain assigned but not completed",
                "tellius_config": {
                    "metric": {
                        "measure": "Assigned Percentage",
                        "aggregation": "AVG", 
                        "resolution": "Daily",
                        "drilldown_dimensions": ["Training Type", "Manager"]
                    },
                    "condition": {
                        "condition_type": "threshold_value",
                        "operator": ">",
                        "value": 25.0
                    },
                    "notification": {
                        "schedule_type": "with_data_refresh",
                        "subject": "Training Assignment Backlog Alert"
                    }
                }
            }
        }

if __name__ == "__main__":
    # Run the complete demonstration
    asyncio.run(run_complete_demo())
    
    # Print API examples
    print("\n" + "=" * 60)
    print("🌐 FastAPI CURL EXAMPLES")
    print("=" * 60)
    
    api_examples = FastAPIExamples.curl_examples()
    for name, example in api_examples.items():
        print(f"\n{example['description']}:")
        print(example['curl'])
    
    # Print templates
    print("\n" + "=" * 60)
    print("📋 CONFIGURATION TEMPLATES")
    print("=" * 60)
    
    templates = ConfigurationTemplates.training_completion_templates()
    for template_name, template in templates.items():
        print(f"\n{template['name']}:")
        print(f"Description: {template['description']}")
        print(f"Config: {json.dumps(template['tellius_config'], indent=2)}")