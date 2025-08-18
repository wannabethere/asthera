#!/usr/bin/env python3
"""
Test script for Data Setup Workflow functionality

This script demonstrates the new data setup workflow endpoints:
1. Setup sharing permissions
2. Check permissions status
3. Execute complete data setup workflow
4. Monitor workflow progress
"""

import asyncio
import json
import httpx
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
WORKFLOW_BASE_URL = f"{BASE_URL}/workflow"
TEST_DOMAIN_ID = "test-domain-123"
TEST_USER_ID = "test-user-456"
TEST_SESSION_ID = "test-session-789"

class DataSetupWorkflowTester:
    """Test class for data setup workflow endpoints"""
    
    def __init__(self, base_url: str, domain_id: str, user_id: str, session_id: str):
        self.base_url = base_url
        self.domain_id = domain_id
        self.user_id = user_id
        self.session_id = session_id
        self.headers = {
            "X-User-Id": user_id,
            "X-Session-Id": session_id,
            "Content-Type": "application/json"
        }
    
    async def test_sharing_permissions_setup(self):
        """Test the sharing permissions setup endpoint"""
        print("🧪 Testing Sharing Permissions Setup")
        print("=" * 50)
        
        try:
            url = f"{self.base_url}/{self.domain_id}/setup-sharing-permissions"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers)
                
                if response.status_code == 200:
                    result = response.json()
                    print("✅ Sharing permissions setup completed successfully!")
                    print(f"   - Domain ID: {result.get('domain_id')}")
                    print(f"   - Setup completed at: {result.get('setup_completed_at')}")
                    print(f"   - Setup by: {result.get('setup_by')}")
                    print(f"   - Workflow step: {result.get('workflow_step')}")
                    
                    # Show permissions summary
                    permissions = result.get('permissions', {})
                    if permissions:
                        print(f"\n   📊 Permissions Summary:")
                        print(f"      - Users: {len(permissions.get('permissions', {}).get('users', []))}")
                        print(f"      - Teams: {len(permissions.get('permissions', {}).get('teams', []))}")
                        print(f"      - Workspaces: {len(permissions.get('permissions', {}).get('workspaces', []))}")
                        print(f"      - Projects: {len(permissions.get('permissions', {}).get('projects', []))}")
                        print(f"      - Organizations: {len(permissions.get('permissions', {}).get('organizations', []))}")
                    
                    print(f"\n   🎯 Next Steps:")
                    for step in result.get('next_steps', []):
                        print(f"      - {step}")
                    
                    return result
                else:
                    print(f"❌ Sharing permissions setup failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error testing sharing permissions setup: {str(e)}")
            return None
    
    async def test_sharing_permissions_status(self):
        """Test the sharing permissions status endpoint"""
        print(f"\n📊 Testing Sharing Permissions Status")
        print("-" * 40)
        
        try:
            url = f"{self.base_url}/{self.domain_id}/sharing-permissions-status"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    result = response.json()
                    print("✅ Sharing permissions status retrieved successfully!")
                    print(f"   - Domain ID: {result.get('domain_id')}")
                    print(f"   - Status: {result.get('status')}")
                    print(f"   - Can proceed: {result.get('can_proceed')}")
                    print(f"   - Message: {result.get('message')}")
                    
                    if result.get('status') == 'setup_completed':
                        print(f"\n   📋 Setup Details:")
                        print(f"      - Setup completed at: {result.get('setup_completed_at')}")
                        print(f"      - Setup by: {result.get('setup_by')}")
                        print(f"      - Workflow step: {result.get('workflow_step')}")
                        
                        # Show permissions summary
                        summary = result.get('permissions_summary', {})
                        print(f"\n   📊 Permissions Summary:")
                        print(f"      - Total Users: {summary.get('total_users', 0)}")
                        print(f"      - Total Teams: {summary.get('total_teams', 0)}")
                        print(f"      - Total Workspaces: {summary.get('total_workspaces', 0)}")
                        print(f"      - Total Projects: {summary.get('total_projects', 0)}")
                        print(f"      - Total Organizations: {summary.get('total_organizations', 0)}")
                    else:
                        print(f"\n   ⚠️  Setup Required:")
                        print(f"      - Next action: {result.get('next_action')}")
                    
                    return result
                else:
                    print(f"❌ Sharing permissions status check failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error testing sharing permissions status: {str(e)}")
            return None
    
    async def test_data_setup_workflow(self, setup_steps: list = None):
        """Test the complete data setup workflow endpoint"""
        print(f"\n🔄 Testing Complete Data Setup Workflow")
        print("-" * 50)
        
        try:
            url = f"{self.base_url}/{self.domain_id}/data-setup-workflow"
            
            # Prepare request payload
            payload = {}
            if setup_steps:
                payload["setup_steps"] = setup_steps
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    print("✅ Data setup workflow executed successfully!")
                    print(f"   - Domain ID: {result.get('domain_id')}")
                    print(f"   - Workflow started at: {result.get('workflow_started_at')}")
                    print(f"   - Executed by: {result.get('executed_by')}")
                    print(f"   - Overall status: {result.get('overall_status')}")
                    print(f"   - Message: {result.get('message')}")
                    
                    # Show workflow steps results
                    steps = result.get('steps', {})
                    if steps:
                        print(f"\n   📋 Workflow Steps Results:")
                        for step_name, step_result in steps.items():
                            status = step_result.get('status', 'unknown')
                            status_emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
                            print(f"      {status_emoji} {step_name}: {status}")
                            
                            if step_result.get('completed_at'):
                                print(f"         Completed at: {step_result.get('completed_at')}")
                            elif step_result.get('failed_at'):
                                print(f"         Failed at: {step_result.get('failed_at')}")
                                print(f"         Error: {step_result.get('error')}")
                    
                    if result.get('overall_status') == 'completed':
                        print(f"\n   🎉 Workflow completed at: {result.get('completed_at')}")
                    elif result.get('overall_status') == 'failed':
                        failed_steps = result.get('failed_steps', [])
                        print(f"\n   ❌ Workflow failed for steps: {', '.join(failed_steps)}")
                    
                    return result
                else:
                    print(f"❌ Data setup workflow failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error testing data setup workflow: {str(e)}")
            return None
    
    async def test_custom_workflow_steps(self):
        """Test the data setup workflow with custom steps"""
        print(f"\n🎯 Testing Custom Workflow Steps")
        print("-" * 40)
        
        # Test with only sharing permissions step
        custom_steps = ["sharing_permissions"]
        print(f"   Testing with custom steps: {custom_steps}")
        
        result = await self.test_data_setup_workflow(custom_steps)
        return result
    
    async def run_complete_test_suite(self):
        """Run the complete test suite"""
        print("🚀 Starting Data Setup Workflow Test Suite")
        print("=" * 60)
        
        # Test 1: Check initial status
        print("\n1️⃣  Checking initial sharing permissions status...")
        initial_status = await self.test_sharing_permissions_status()
        
        # Test 2: Setup sharing permissions
        print("\n2️⃣  Setting up sharing permissions...")
        setup_result = await self.test_sharing_permissions_setup()
        
        # Test 3: Check status after setup
        print("\n3️⃣  Checking status after setup...")
        final_status = await self.test_sharing_permissions_status()
        
        # Test 4: Execute complete workflow
        print("\n4️⃣  Executing complete data setup workflow...")
        workflow_result = await self.test_data_setup_workflow()
        
        # Test 5: Test custom workflow steps
        print("\n5️⃣  Testing custom workflow steps...")
        custom_result = await self.test_custom_workflow_steps()
        
        # Summary
        print(f"\n📊 Test Suite Summary")
        print("=" * 40)
        tests = [
            ("Initial Status Check", initial_status),
            ("Permissions Setup", setup_result),
            ("Status After Setup", final_status),
            ("Complete Workflow", workflow_result),
            ("Custom Workflow Steps", custom_result)
        ]
        
        for test_name, result in tests:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name}: {status}")
        
        print(f"\n🎉 Test suite completed!")
        print("=" * 60)
        
        return {
            "initial_status": initial_status,
            "setup_result": setup_result,
            "final_status": final_status,
            "workflow_result": workflow_result,
            "custom_result": custom_result
        }

async def main():
    """Main test function"""
    print("🧪 Data Setup Workflow Test Suite")
    print("=" * 60)
    
    # Initialize tester
    tester = DataSetupWorkflowTester(
        base_url=WORKFLOW_BASE_URL,
        domain_id=TEST_DOMAIN_ID,
        user_id=TEST_USER_ID,
        session_id=TEST_SESSION_ID
    )
    
    # Run complete test suite
    results = await tester.run_complete_test_suite()
    
    # Show detailed results
    print(f"\n📋 Detailed Results")
    print("=" * 40)
    print(json.dumps(results, indent=2, default=str))
    
    print(f"\n✨ All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())
