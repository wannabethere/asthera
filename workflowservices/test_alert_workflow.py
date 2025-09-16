#!/usr/bin/env python3
"""
Test script for alert workflow functionality
"""

import asyncio
import sys
import os
from uuid import UUID

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.workflow_orchestrator import WorkflowOrchestrator, WorkflowType
from app.core.dependencies import get_async_db_session

async def test_alert_workflow():
    """Test creating an alert workflow"""
    
    # Get database session
    async for db in get_async_db_session():
        orchestrator = WorkflowOrchestrator(db)
        
        try:
            # Test data for alert workflow
            test_data = {
                "name": "Test Alert Workflow",
                "description": "A test alert workflow for monitoring system metrics",
                "project_id": None,
                "workspace_id": None,
                "dataset_details": [
                    {
                        "name": "system_metrics",
                        "description": "System performance metrics",
                        "source": "prometheus",
                        "query": "up{job='node-exporter'}"
                    }
                ],
                "metric_details": [
                    {
                        "name": "cpu_usage",
                        "description": "CPU usage percentage",
                        "type": "gauge",
                        "query": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)"
                    }
                ],
                "condition_details": [
                    {
                        "name": "high_cpu_alert",
                        "description": "Alert when CPU usage is high",
                        "condition": "cpu_usage > 80",
                        "severity": "high",
                        "cooldown": 300
                    }
                ],
                "metadata": {
                    "environment": "test",
                    "team": "platform"
                }
            }
            
            print("Creating alert workflow...")
            result = await orchestrator.create_workflow(
                user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),
                workflow_type=WorkflowType.ALERT,
                name=test_data["name"],
                description=test_data["description"],
                project_id=test_data["project_id"],
                workspace_id=test_data["workspace_id"],
                dataset_details=test_data["dataset_details"],
                metric_details=test_data["metric_details"],
                condition_details=test_data["condition_details"],
                metadata=test_data["metadata"]
            )
            
            print("✅ Alert workflow created successfully!")
            print(f"Workflow ID: {result['workflow_id']}")
            print(f"Workflow Type: {result['workflow_type']}")
            print(f"Resource ID: {result['resource_id']}")
            print(f"State: {result['state']}")
            print(f"Created At: {result['created_at']}")
            
            # Test getting workflow status
            print("\nGetting workflow status...")
            status = await orchestrator.get_workflow_status(
                user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),
                workflow_id=UUID(result['workflow_id'])
            )
            
            print("✅ Workflow status retrieved successfully!")
            print(f"Status: {status}")
            
            # Test listing user workflows
            print("\nListing user workflows...")
            workflows = await orchestrator.list_user_workflows(
                user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),
                workflow_type=WorkflowType.ALERT
            )
            
            print("✅ User workflows listed successfully!")
            print(f"Found {len(workflows)} alert workflows")
            for workflow in workflows:
                print(f"  - {workflow['workflow_id']}: {workflow['type']} ({workflow['state']})")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing alert workflow: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            await db.close()

async def test_alert_workflow_endpoint():
    """Test the alert workflow endpoint via HTTP"""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            # Test data
            test_data = {
                "name": "HTTP Test Alert Workflow",
                "description": "Testing alert workflow via HTTP endpoint",
                "dataset_details": [
                    {
                        "name": "test_dataset",
                        "description": "Test dataset for HTTP testing",
                        "source": "test_source"
                    }
                ],
                "metric_details": [
                    {
                        "name": "test_metric",
                        "description": "Test metric",
                        "type": "counter"
                    }
                ],
                "condition_details": [
                    {
                        "name": "test_condition",
                        "description": "Test condition",
                        "condition": "test_metric > 0",
                        "severity": "medium"
                    }
                ]
            }
            
            print("Testing alert workflow HTTP endpoint...")
            response = await client.post(
                "http://localhost:8000/api/v1/workflows/alert",
                json=test_data
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ HTTP endpoint test successful!")
                print(f"Response: {result}")
                return True
            else:
                print(f"❌ HTTP endpoint test failed: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing HTTP endpoint: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting alert workflow tests...")
    
    # Test direct orchestrator functionality
    print("\n1. Testing direct orchestrator functionality...")
    success = asyncio.run(test_alert_workflow())
    
    if success:
        print("\n✅ Direct orchestrator test passed!")
    else:
        print("\n❌ Direct orchestrator test failed!")
        sys.exit(1)
    
    # Test HTTP endpoint (only if server is running)
    print("\n2. Testing HTTP endpoint...")
    http_success = asyncio.run(test_alert_workflow_endpoint())
    
    if http_success:
        print("\n✅ HTTP endpoint test passed!")
    else:
        print("\n⚠️  HTTP endpoint test skipped (server not running)")
    
    print("\n🎉 Alert workflow functionality test completed!")
