"""
Example showing how to use the Alert Router and Services

This demonstrates how to use both the native AlertService and the 
AlertCompatibilityService through the router endpoints.
"""

import asyncio
import httpx
from typing import Dict, Any

# Example usage of the alert services through the router


async def example_native_alert_service():
    """Example of using the native alert service endpoints"""
    print("=== Native Alert Service Example ===")
    
    base_url = "http://localhost:8000/alerts"  # Adjust based on your server
    
    async with httpx.AsyncClient() as client:
        # Example 1: Create a single alert
        try:
            response = await client.post(
                f"{base_url}/service/create-single",
                json={
                    "sql_queries": ["SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL 1 DAY"],
                    "natural_language_query": "How many users were created in the last day?",
                    "alert_request": "Alert me if more than 100 users are created in a day",
                    "project_id": "example_project",
                    "data_description": "User registration data",
                    "session_id": "session_123"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Single alert created: {result['success']}")
                print(f"Request type: {result['data']['request_type']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        # Example 2: Create a feed
        try:
            response = await client.post(
                f"{base_url}/service/create-feed",
                json={
                    "feed_id": "user_engagement_feed",
                    "feed_name": "User Engagement Monitoring",
                    "project_id": "example_project",
                    "alert_combinations": [
                        {
                            "alert_request": "Monitor user engagement metrics",
                            "sql_query": "SELECT avg(session_duration) FROM user_sessions",
                            "natural_language_query": "What is the average session duration?",
                            "alert_id": "session_duration_alert",
                            "alert_name": "Session Duration Alert",
                            "priority": "medium",
                            "tags": ["engagement", "sessions"]
                        }
                    ],
                    "description": "Monitor user engagement across the platform",
                    "priority": "medium",
                    "tags": ["engagement", "monitoring"]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Feed created: {result['success']}")
                print(f"Request type: {result['data']['request_type']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")


async def example_compatibility_service():
    """Example of using the compatibility service endpoints"""
    print("\n=== Compatibility Service Example ===")
    
    base_url = "http://localhost:8000/alerts"  # Adjust based on your server
    
    async with httpx.AsyncClient() as client:
        # Example 1: Create alert using compatibility service
        try:
            response = await client.post(
                f"{base_url}/compatibility/create",
                json={
                    "input": "Create an alert for high error rates in the API",
                    "config": {
                        "conditionTypes": ["greaterthan"],
                        "availableMetrics": ["api_error_rate", "response_time"],
                        "schedule": ["immediately", "daily"],
                        "timecolumn": ["rolling", "default"],
                        "notificationgroups": ["slack devops", "email alerts"],
                        "question": "What is the API error rate?",
                        "project_id": "compatibility_project",
                        "priority": "critical",
                        "tags": ["api", "errors", "critical"]
                    },
                    "session_id": "compatibility_session_123",
                    "project_id": "compatibility_project",
                    "priority": "critical",
                    "tags": ["api", "errors", "production"]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Compatibility alert created: {result['success']}")
                print(f"Alert name: {result['data']['alertname']}")
                print(f"Service created: {result['data']['service_created']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        # Example 2: Create alerts from response
        try:
            response = await client.post(
                f"{base_url}/compatibility/create-from-response",
                json={
                    "type": "finished",
                    "question": "What is the dropout rate?",
                    "alertname": "High Dropout Rate Alert",
                    "summary": "Monitors dropout rate and alerts when it exceeds 10%",
                    "reasoning": "User requested weekly monitoring of dropout rate",
                    "conditions": [
                        {
                            "conditionType": "greaterthan",
                            "metricselected": "dropout_rate",
                            "schedule": "weekly",
                            "timecolumn": "rolling",
                            "value": "10"
                        }
                    ],
                    "notificationgroup": "slack retention-team",
                    "project_id": "compatibility_project",
                    "session_id": "compatibility_session_123"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Alert from response created: {result['success']}")
                print(f"Alert name: {result['data']['alertname']}")
                print(f"Service created: {result['data']['service_created']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")


async def example_main_py_compatibility():
    """Example of using the main.py compatibility endpoints"""
    print("\n=== Main.py Compatibility Example ===")
    
    base_url = "http://localhost:8000/alerts"  # Adjust based on your server
    
    async with httpx.AsyncClient() as client:
        # Example: Use the exact main.py API
        try:
            response = await client.post(
                f"{base_url}/ask/alertbuilder/ai",
                json={
                    "input": "Create an alert for high dropout rates",
                    "config": {
                        "conditionTypes": ["greaterthan"],
                        "availableMetrics": ["dropout_rate"],
                        "schedule": ["weekly"],
                        "timecolumn": ["rolling"],
                        "notificationgroups": ["slack team"],
                        "question": "What is the dropout rate?"
                    },
                    "session_id": "main_py_session_123"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Main.py compatibility alert created")
                print(f"Response type: {result['response']['type']}")
                print(f"Alert name: {result['response']['alertname']}")
                print(f"Service created: {result['response']['service_created']}")
                print(f"Session ID: {result['session_id']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")


async def example_health_checks():
    """Example of using health check endpoints"""
    print("\n=== Health Check Example ===")
    
    base_url = "http://localhost:8000/alerts"  # Adjust based on your server
    
    async with httpx.AsyncClient() as client:
        # Health check
        try:
            response = await client.get(f"{base_url}/health")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Health check: {result['status']}")
                print(f"Services: {result['services']}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        
        # Service info
        try:
            response = await client.get(f"{base_url}/service/info")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Alert service info: {result}")
            else:
                print(f"❌ Service info failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Service info failed: {e}")
        
        # Compatibility service info
        try:
            response = await client.get(f"{base_url}/compatibility/info")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Compatibility service info: {result}")
            else:
                print(f"❌ Compatibility info failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Compatibility info failed: {e}")


async def example_batch_operations():
    """Example of using batch operations"""
    print("\n=== Batch Operations Example ===")
    
    base_url = "http://localhost:8000/alerts"  # Adjust based on your server
    
    async with httpx.AsyncClient() as client:
        # Batch create alerts
        try:
            response = await client.post(
                f"{base_url}/compatibility/batch-create",
                json=[
                    {
                        "input": "Alert for high CPU usage",
                        "config": {
                            "conditionTypes": ["greaterthan"],
                            "availableMetrics": ["cpu_usage"],
                            "schedule": ["immediately"],
                            "timecolumn": ["rolling"],
                            "notificationgroups": ["slack ops"],
                            "question": "What is the CPU usage?"
                        },
                        "session_id": "batch_session_1"
                    },
                    {
                        "input": "Alert for low memory",
                        "config": {
                            "conditionTypes": ["lessthan"],
                            "availableMetrics": ["memory_available"],
                            "schedule": ["daily"],
                            "timecolumn": ["rolling"],
                            "notificationgroups": ["email admin"],
                            "question": "What is the available memory?"
                        },
                        "session_id": "batch_session_2"
                    }
                ]
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"✅ Batch operation completed: {len(results)} alerts processed")
                for i, result in enumerate(results):
                    print(f"  Alert {i+1}: {result['success']} - {result['data']['alertname']}")
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Batch request failed: {e}")


async def main():
    """Run all examples"""
    print("Alert Service and Compatibility Examples")
    print("=" * 50)
    
    await example_native_alert_service()
    await example_compatibility_service()
    await example_main_py_compatibility()
    await example_health_checks()
    await example_batch_operations()
    
    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
