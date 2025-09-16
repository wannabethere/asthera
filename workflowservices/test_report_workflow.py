import asyncio
import httpx
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
import sys

def setup_logging():
    """Set up comprehensive logging configuration with UTF-8 support"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"report_api_tests_{timestamp}.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler (UTF-8)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler (UTF-8)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Setup logger
    logger = logging.getLogger('report_api_test')
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers if setup_logging() called multiple times
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger


class ReportAPITester:
    def __init__(self, base_url: str = "http://localhost:8033"):
        self.base_url = base_url
        self.logger = setup_logging()
        self.workflow_id = None
        self.section_ids = []
        self.test_results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "responses": []
        }
    
    def log_api_call(self, method: str, endpoint: str, payload: Optional[Dict] = None):
        """Log API call details"""
        self.logger.info(f"🔄 API CALL: {method} {endpoint}")
        if payload:
            self.logger.debug(f"📤 REQUEST PAYLOAD: {json.dumps(payload, indent=2)}")
        print(f"\n{'='*80}")
        print(f"🔄 CALLING API: {method} {endpoint}")
        if payload:
            print(f"📤 PAYLOAD: {json.dumps(payload, indent=2)}")
        print(f"{'='*80}")
    
    def log_api_response(self, response: httpx.Response, test_name: str):
        """Log API response details"""
        status_icon = "✅" if response.status_code < 400 else "❌"
        
        self.logger.info(f"{status_icon} RESPONSE: Status {response.status_code}")
        
        try:
            response_json = response.json()
            self.logger.debug(f"📥 RESPONSE DATA: {json.dumps(response_json, indent=2)}")
            
            print(f"{status_icon} RESPONSE STATUS: {response.status_code}")
            print(f"📥 RESPONSE DATA: {json.dumps(response_json, indent=2)}")
            
            # Store response for reporting
            self.test_results["responses"].append({
                "test_name": test_name,
                "status_code": response.status_code,
                "response_data": response_json,
                "timestamp": datetime.now().isoformat()
            })
            
            return response_json
        except json.JSONDecodeError:
            error_msg = f"Failed to parse JSON response: {response.text}"
            self.logger.error(error_msg)
            print(f"❌ JSON PARSE ERROR: {error_msg}")
            return {"error": "Invalid JSON response", "raw_response": response.text}
    
    def log_error(self, test_name: str, error: Exception):
        """Log test errors"""
        error_msg = f"Test '{test_name}' failed with error: {str(error)}"
        self.logger.error(error_msg)
        print(f"❌ ERROR in {test_name}: {str(error)}")
        
        self.test_results["errors"].append({
            "test_name": test_name,
            "error": str(error),
            "timestamp": datetime.now().isoformat()
        })
    
    async def create_report_workflow(self, workflow_config: Dict, params: Optional[Dict] = None) -> Optional[Dict]:
        """Test: Create report workflow"""
        test_name = "create_report_workflow"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/report", workflow_config)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/report", 
                    json=workflow_config,
                    params=params,
                    timeout=30.0
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                    # Extract workflow_id if present
                    if isinstance(result, dict) and "workflow_id" in result:
                        self.workflow_id = result["workflow_id"]
                        self.logger.info(f"✅ Report workflow created with ID: {self.workflow_id}")
                        print(f"✅ Workflow ID stored: {self.workflow_id}")
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None
    
    async def add_report_section(self, section: Union[Dict, List], params: Optional[Dict] = None) -> Union[Dict, List]:
        """Test: Add section to report"""
        test_name = "add_report_section"
        self.test_results["total_tests"] += 1
        
        print(f"Workflow ID: {self.workflow_id}")
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/add-section", section)
            timeout = httpx.Timeout(connect=60.0, read=120.0, write=60.0, pool=120.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/add-section",
                    json=section,
                    params=params
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                    # Store section_id if present
                    if isinstance(result, dict) and "section_id" in result:
                        self.section_ids.append(result["section_id"])
                        self.logger.info(f"✅ Section added with ID: {result['section_id']}")
                    # Handle multiple section IDs if the result contains them
                    elif isinstance(result, dict) and "section_ids" in result:
                        self.section_ids.extend(result["section_ids"])
                        self.logger.info(f"✅ Sections added with IDs: {result['section_ids']}")
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None
    
    async def add_data_sources(self, data_sources_config: Dict, params: Optional[Dict] = None) -> Optional[Dict]:
        """Test: Add data sources to report"""
        test_name = "add_data_sources"
        self.test_results["total_tests"] += 1
        
        payload = data_sources_config
        
        try:
            endpoint = f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/data-sources"
            self.log_api_call("POST", endpoint, payload)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint, 
                    json=payload,
                    params=params,
                    timeout=30.0
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None
    
    async def publish_report(self) -> Optional[Dict]:
        """Test: Publish report"""
        test_name = "publish_report"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/publish")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/publish",
                    timeout=30.0
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None

    async def edit_report(self, content: Dict, metadata: Optional[Dict] = None, params: Optional[Dict] = None):
        """Test: Edit report"""
        test_name = "edit_report"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("PATCH", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/edit", content)
            edit_content = {"content": content}
            if metadata:
                edit_content["metadata"] = metadata
                
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/edit",
                    json=edit_content,
                    params=params
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None

    async def get_draft_changes(self, params: Optional[Dict] = None) -> Optional[Dict]:
        """Test: Get draft changes"""
        test_name = "get_draft_changes"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("GET", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/draft-changes")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/draft-changes",
                    params=params,
                    timeout=30.0
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None

    async def discard_draft(self, discard_config: Optional[Dict] = None) -> Optional[Dict]:
        """Test: Discard draft"""
        test_name = "discard_draft"
        self.test_results["total_tests"] += 1
        
        payload = discard_config or {}
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/discard-draft", payload)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/report/discard-draft",
                    json=payload,
                    timeout=30.0
                )
                
                result = self.log_api_response(response, test_name)
                
                if response.status_code < 400:
                    self.test_results["passed"] += 1
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None
    
    def print_test_summary(self):
        """Print comprehensive test summary"""
        print(f"\n{'='*100}")
        print("📊 TEST EXECUTION SUMMARY")
        print(f"{'='*100}")
        print(f"🔢 Total Tests: {self.test_results['total_tests']}")
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        print(f"📈 Success Rate: {(self.test_results['passed']/self.test_results['total_tests']*100):.1f}%")
        
        if self.test_results['errors']:
            print(f"\n❌ ERRORS ENCOUNTERED:")
            for error in self.test_results['errors']:
                print(f"   • {error['test_name']}: {error['error']}")
        
        print(f"\n💾 Log files saved in: logs/")
        print(f"{'='*100}\n")
        
        # Log summary
        self.logger.info(f"Test Summary - Total: {self.test_results['total_tests']}, "
                        f"Passed: {self.test_results['passed']}, "
                        f"Failed: {self.test_results['failed']}")

async def run_integration_tests():
    """Run complete report integration test suite"""
    print("🚀 Starting Report Workflow API Integration Tests")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize tester
    tester = ReportAPITester()
    
    start_time = time.time()
    
    # Test 1: Create report workflow
    workflow_config = {
        "metadata": {
            "source": "test",
            "version": "1.0.0",
            "report_type": "analytical"
        }
    }
    params = {
        "name": "Test Report Workflow",
        "description": "Test report workflow for integration testing",
        "workspace_id": "055d8308-1534-424a-8b41-7b6901c38c75",
    }
    await tester.create_report_workflow(workflow_config, params)
    await asyncio.sleep(20)

    # Test 2: Add report sections
    sample_sections = [
        {
            "section_type": "executive_summary",
            "title": "Executive Summary",
            "content": "This section provides an overview of key findings...",
            "order": 1
        },
        {
            "section_type": "analysis",
            "title": "Data Analysis",
            "content": "Detailed analysis of the data reveals...",
            "order": 2,
            "charts": [
                {
                    "chart_id": "chart_1",
                    "chart_type": "bar",
                    "data_source": "placeholder_data"
                }
            ]
        }
    ]
    await tester.add_report_section(sample_sections)
    await asyncio.sleep(20)
    
    # Test 3: Add data sources
    data_sources_config = {
        "data_sources": [
            {
                "source_id": "db_source_1",
                "source_type": "database",
                "connection_string": "postgresql://placeholder",
                "tables": ["employees", "departments"]
            },
            {
                "source_id": "api_source_1",
                "source_type": "api",
                "endpoint": "https://api.example.com/data",
                "auth_config": {
                    "type": "bearer",
                    "token": "placeholder_token"
                }
            }
        ]
    }
    await tester.add_data_sources(data_sources_config)
    await asyncio.sleep(20)
    
    # Test 4: Edit report
    content_update = {
        "sections": [
            {
                "section_id": "section_1",
                "title": "Updated Executive Summary",
                "content": "This updated section provides enhanced overview...",
                "order": 1
            }
        ],
        "metadata": {
            "last_modified": datetime.now().isoformat(),
            "version": "1.1.0"
        }
    }
    await tester.edit_report(content_update)
    await asyncio.sleep(10)
    
    # Test 5: Get draft changes
    await tester.get_draft_changes()
    await asyncio.sleep(10)
    
    # Test 6: Discard draft (optional test)
    discard_config = {
        "confirm": False,
        "reason": "Testing discard functionality"
    }
    await tester.discard_draft(discard_config)
    await asyncio.sleep(10)
    
    # Test 7: Publish report
    await tester.publish_report()
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Print summary
    tester.print_test_summary()
    print(f"⏱️  Total Execution Time: {execution_time:.2f} seconds")
    
    return tester.test_results

if __name__ == "__main__":
    # Run the integration tests
    results = asyncio.run(run_integration_tests())