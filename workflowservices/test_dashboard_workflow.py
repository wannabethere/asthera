import asyncio
import httpx
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional,Union,List
from pathlib import Path
import sys

def setup_logging():
    """Set up comprehensive logging configuration with UTF-8 support"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"dashboard_api_tests_{timestamp}.log"
    
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
    logger = logging.getLogger('dashboard_api_test')
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers if setup_logging() called multiple times
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger


class DashboardAPITester:
    def __init__(self, base_url: str = "http://localhost:8020"):
        self.base_url = base_url
        self.logger = setup_logging()
        self.workflow_id = None
        self.component_ids = []
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
    
    async def create_dashboard_workflow(self, workflow_config: Dict,params:Optional[Dict]=None) -> Optional[Dict]:
        """Test: Create dashboard workflow"""
        test_name = "create_dashboard_workflow"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/dashboard", workflow_config)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/dashboard", 
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
                        self.logger.info(f"✅ Workflow created with ID: {self.workflow_id}")
                        print(f"✅ Workflow ID stored: {self.workflow_id}")
                else:
                    self.test_results["failed"] += 1
                
                return result
                
        except Exception as e:
            self.test_results["failed"] += 1
            self.log_error(test_name, e)
            return None
    
    async def add_dashboard_component(self, component: Union[Dict, List], params: Optional[Dict] = None) -> Union[Dict, List]:
            """Test: Add component to dashboard"""
            test_name = "add_dashboard_component"
            self.test_results["total_tests"] += 1
            
            print(f"Workflow ID: {self.workflow_id}")
            
            try:
                self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/add-component", component)
                timeout = httpx.Timeout(connect=60.0, read=120.0, write=60.0, pool=120.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/add-component",
                        json=component,
                        params=params
                    )
                    
                    # Remove the duplicate response parsing line that was causing the issue
                    # print(f"response from the add_dashboard_component {response} {response.json()} {response.text}")
                    
                    result = self.log_api_response(response, test_name)
                    
                    if response.status_code < 400:
                        self.test_results["passed"] += 1
                        # Store component_id if present
                        if isinstance(result, dict) and "component_id" in result:
                            self.component_ids.append(result["component_id"])
                            self.logger.info(f"✅ Component added with ID: {result['component_id']}")
                        # Handle multiple component IDs if the result contains them
                        elif isinstance(result, dict) and "component_ids" in result:
                            self.component_ids.extend(result["component_ids"])
                            self.logger.info(f"✅ Components added with IDs: {result['component_ids']}")
                    else:
                        self.test_results["failed"] += 1
                    
                    return result
                    
            except Exception as e:
                self.test_results["failed"] += 1
                self.log_error(test_name, e)
                return None
    
    
    async def configure_dashboard_component(self, component_id: str, configuration: Dict) -> Optional[Dict]:
        """Test: Configure dashboard component"""
        test_name = "configure_dashboard_component"
        self.test_results["total_tests"] += 1
        
        payload = configuration
        
        try:
            endpoint = f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/configure-component/{component_id}"
            self.log_api_call("PATCH", endpoint, payload)
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(endpoint, json=payload)
                
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
    
    async def share_dashboard(self, share_config: Dict) -> Optional[Dict]:
        """Test: Share dashboard"""
        test_name = "share_dashboard"
        self.test_results["total_tests"] += 1
        
        payload = share_config
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/share", payload)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/share",
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
    
    async def schedule_dashboard(self, schedule_config: Dict) -> Optional[Dict]:
        """Test: Schedule dashboard"""
        test_name = "schedule_dashboard"
        self.test_results["total_tests"] += 1
        
        payload = schedule_config
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/schedule", payload)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/schedule",
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
    
    async def add_integrations(self, integration_config: Dict) -> Optional[Dict]:
        """Test: Add integrations"""
        test_name = "add_integrations"
        self.test_results["total_tests"] += 1
        
        payload = integration_config
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/integrations", payload)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/integrations",
                    json=payload
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
    
    async def publish_dashboard(self) -> Optional[Dict]:
        """Test: Publish dashboard"""
        test_name = "publish_dashboard"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/publish")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/publish",
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

    async def edit_dashboard(self,content:Dict,metadata:Optional[Dict]=None,params:Optional[Dict]=None):
        test_name = "edit_dashboard"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("PATCH", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/edit",content )
            content = {"content":content}
            if metadata:
                content["metadata"] = metadata
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/edit",
                    json=content,
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


    async def update_dashboard_info(self, info: Dict,params:Optional[Dict]=None) -> Optional[Dict]:
        """Test: Update dashboard info"""
        test_name = "update_dashboard_info"
        self.test_results["total_tests"] += 1
        
        try:
            self.log_api_call("POST", f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/update-info", {"info":info})
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows/{self.workflow_id}/dashboard/update-info",
                    json={"info":info},
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
    """Run complete integration test suite"""
    print("🚀 Starting Dashboard Workflow API Integration Tests")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize tester
    tester = DashboardAPITester()
    
    start_time = time.time()
    
    # Test 1: Create workflow
    workflow_config = {
        "metadata": {
            "source": "test",
            "version": "1.0.0"
        }
    }
    params={
        "name": "Test Dashboard Workflow",
        "description": "Test dashboard workflow for integration testing",
        "workspace_id": "055d8308-1534-424a-8b41-7b6901c38c75",
        
    }
    await tester.create_dashboard_workflow(workflow_config,params)
    await asyncio.sleep(20)

    # Test 2: Add components
    sample_component = [
        {
        "component_type": "question",
        "question": "Which training has the highest drop-off rate (i.e., the number of 'Registered' or 'Approved' statuses that did not result in 'Completed')",
        "description": "This report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
        "overview": {
            "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown"
        },
        "chart_config": {
            "format": "vega_lite",
            "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
            "batch_used": 0,
            "chart_type": "kpi",
            "data_count": 4,
            "data_sample": {
            "data": [
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
                }
            ],
            "columns": [
                "Training Title",
                "Drop-Off Rate"
            ]
            },
            "chart_schema": {
            "data": {
                "values": [
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Code of Conduct Awareness"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Effective Communication"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Product Knowledge"
                },
                {
                    "Drop-Off Rate": "100.0",
                    "Training Title": "Time Management"
                }
                ]
            },
            "mark": {
                "type": "text"
            },
            "title": "Highest Drop-Off Rate Training",
            "encoding": {
                "text": {
                "type": "quantitative",
                "field": "value"
                },
                "color": {
                "type": "nominal",
                "field": "metric"
                }
            },
            "kpi_metadata": {
                "is_dummy": True,
                "kpi_data": {
                "units": [],
                "values": [],
                "metrics": [],
                "targets": []
                },
                "chart_type": "kpi",
                "description": "KPI chart - templates will be created elsewhere",
                "vega_lite_compatible": False,
                "requires_custom_template": True
            }
            },
            "execution_info": {
            "data_count": 4,
            "execution_config": {
                "sort_by": None,
                "max_rows": 10000,
                "page_size": 1000,
                "sort_order": "ASC",
                "enable_pagination": True
            },
            "validation_success": False
            }
        },
        "table_config": {},
        "configuration": {},
        "sql_query": "SELECT training_title AS \"Training Title\", (COUNT(CASE WHEN completed_date IS None THEN 1 END) * 100.0 / COUNT(*)) AS \"Drop-Off Rate\" FROM csod_training_records WHERE lower(transcript_status) IN (lower('Registered'), lower('Approved')) GROUP BY training_title ORDER BY \"Drop-Off Rate\" DESC LIMIT 1",
        "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
        "data_overview": {
            "total_rows": 0,
            "total_batches": 1,
            "batches_processed": 1
        },
        "visualization_data": {
            "data": [
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
            }
            ],
            "columns": [
            "Training Title",
            "Drop-Off Rate"
            ]
        },
        "sample_data": {
            "data": [
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
            },
            {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
            }
            ],
            "columns": [
            "Training Title",
            "Drop-Off Rate"
            ]
        },
        "metadata": {
            "project_id": "cornerstone",
            "data_description": "I have given the sql query and question.",
            "processing_stats": {
            "timestamp": "2025-08-20T15:55:13.358800",
            "total_tokens": 0,
            "estimated_cost": 0
            }
        },
        "chart_schema": {
            "data": {
            "values": [
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Code of Conduct Awareness"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Effective Communication"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Product Knowledge"
                },
                {
                "Drop-Off Rate": "100.0",
                "Training Title": "Time Management"
                }
            ]
            },
            "mark": {
            "type": "text"
            },
            "title": "Highest Drop-Off Rate Training",
            "encoding": {
            "text": {
                "type": "quantitative",
                "field": "value"
            },
            "color": {
                "type": "nominal",
                "field": "metric"
            }
            },
            "kpi_metadata": {
            "is_dummy": True,
            "kpi_data": {
                "units": [],
                "values": [],
                "metrics": [],
                "targets": []
            },
            "chart_type": "kpi",
            "description": "KPI chart - templates will be created elsewhere",
            "vega_lite_compatible": False,
            "requires_custom_template": True
            }
        },
        "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
        "data_count": 4,
        "validation_results": {
            "data_count": 4,
            "execution_config": {
            "sort_by": None,
            "max_rows": 10000,
            "page_size": 1000,
            "sort_order": "ASC",
            "enable_pagination": True
            },
            "validation_success": False
        }
        },
        {
        "component_type": "question",
        "question": "Are there specific users who have a high number of overdue trainings across different curriculums?",
        "description": "This report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
        "overview": {
            "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown"
        },
        "chart_config": {
            "format": "vega_lite",
            "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
            "batch_used": 0,
            "chart_type": "bar",
            "data_count": 487,
            "data_sample": {
            "data": [
                {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
                }
            ],
            "columns": [
                "full_name",
                "overdue_trainings"
            ]
            },
            "chart_schema": {
            "data": {
                "values": [
                {
                    "full_name": "Yvette Reid",
                    "overdue_trainings": "271"
                }
                ]
            },
            "mark": {
                "type": "bar"
            },
            "title": "Overdue Trainings by User",
            "height": 430,
            "encoding": {
                "x": {
                "type": "nominal",
                "field": "full_name",
                "title": "User"
                },
                "y": {
                "type": "quantitative",
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings"
                },
                "tooltip": [
                {
                    "field": "full_name",
                    "title": "User"
                },
                {
                    "field": "overdue_trainings",
                    "title": "Number of Overdue Trainings",
                    "format": ","
                }
                ]
            }
            },
            "execution_info": {
            "data_count": 487,
            "execution_config": {
                "sort_by": None,
                "max_rows": 10000,
                "page_size": 1000,
                "sort_order": "ASC",
                "enable_pagination": True
            },
            "validation_success": False
            }
        },
        "table_config": {},
        "configuration": {},
        "sql_query": "SELECT tr.full_name AS Full_Name, COUNT(*) AS Overdue_Trainings FROM csod_training_records AS tr WHERE tr.due_date < CAST('2025-08-20 00:00:00' AS TIMESTAMP WITH TIME ZONE) GROUP BY tr.full_name HAVING COUNT(*) > 3 ORDER BY Overdue_Trainings DESC",
        "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
        "data_overview": {
            "total_rows": 0,
            "total_batches": 1,
            "batches_processed": 1
        },
        "visualization_data": {
            "data": [
            {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
            }
            ],
            "columns": [
            "full_name",
            "overdue_trainings"
            ]
        },
        "sample_data": {
            "data": [
            {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
            }
            ],
            "columns": [
            "full_name",
            "overdue_trainings"
            ]
        },
        "metadata": {
            "project_id": "cornerstone",
            "data_description": "I have given the sql query and question.",
            "processing_stats": {
            "timestamp": "2025-08-20T15:52:11.327061",
            "total_tokens": 0,
            "estimated_cost": 0
            }
        },
        "chart_schema": {
            "data": {
            "values": [
                {
                "full_name": "Yvette Reid",
                "overdue_trainings": "271"
                }
            ]
            },
            "mark": {
            "type": "bar"
            },
            "title": "Overdue Trainings by User",
            "height": 430,
            "encoding": {
            "x": {
                "type": "nominal",
                "field": "full_name",
                "title": "User"
            },
            "y": {
                "type": "quantitative",
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings"
            },
            "tooltip": [
                {
                "field": "full_name",
                "title": "User"
                },
                {
                "field": "overdue_trainings",
                "title": "Number of Overdue Trainings",
                "format": ","
                }
            ]
            }
        },
        "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
        "data_count": 487,
        "validation_results": {
            "data_count": 487,
            "execution_config": {
            "sort_by": None,
            "max_rows": 10000,
            "page_size": 1000,
            "sort_order": "ASC",
            "enable_pagination": True
            },
            "validation_success": False
        }
        }
  ]
    await tester.add_dashboard_component(sample_component)
    await asyncio.sleep(20)
    # Test 3: Configure component (if we have component IDs)
    if tester.component_ids:
        config = {
        "configuration": {
            "layout": "grid",
            "theme": "dark",
            "show_title": True,
            "data_source": "HR_api_v2"
        }
    }
        await tester.configure_dashboard_component(tester.component_ids[0], config)
    await asyncio.sleep(20)
    # Test 4: Share dashboard
    share_config = {
        "share_type": "user",
        "target_ids": [
            "c3e7df53-16f0-4b6d-ba76-1e9c36aa339a","d7ef6680-b541-4291-8ea8-e8ba74fd1085","b49dadf3-3235-4490-8a0f-00c622d08105"
        ],
        "permissions": {
            "Action":"read_write"
        }
    }
    await tester.share_dashboard(share_config)
    await asyncio.sleep(20)
    # Test 5: Schedule dashboard
    schedule_config = {
        "schedule_type": "once",
        "timezone": "UTC",
        "start_date": str(datetime.now()),
        "end_date": str(datetime.now())
    }
    # [
    #     {
    #         "schedule_type": "daily",
    #         "timezone": "UTC",
    #         "start_date": "2025-09-15T09:00:00Z",
    #         "end_date": "2025-09-30T09:00:00Z"
    #     },
    #     {
    #         "schedule_type": "weekly",
    #         "timezone": "UTC",
    #         "start_date": "2025-09-20T10:00:00Z",
    #         "end_date": "2025-10-18T10:00:00Z"
    #     },
    #     {
    #         "schedule_type": "biweekly",
    #         "timezone": "UTC",
    #         "start_date": "2025-09-25T11:00:00Z",
    #         "end_date": "2025-10-23T11:00:00Z"
    #     },
    #     {
    #         "schedule_type": "monthly",
    #         "timezone": "UTC",
    #         "start_date": "2025-10-01T12:00:00Z",
    #         "end_date": "2025-11-15T12:00:00Z"
    #     },
    #     {
    #         "schedule_type": "once",
    #         "timezone": "UTC",
    #         "start_date": "2025-09-12T08:30:00Z",
    #         "end_date": "2025-09-12T08:30:00Z"
    #     }
    # ]

    await tester.schedule_dashboard(schedule_config)
    await asyncio.sleep(20)
    
    # Test 6: Add integrations
    integration_config = [
        {
            "integration_type": "tableau",
            "connection_config": {
            "server_url": "https://tableau.company.com",
            "username": "tableau_user",
            "password": "P@ssw0rd8XyZ1",
            "site": "default"
            },
            "mapping_config": {
            "workspace": "Sales Dashboard",
            "project": "Q3 Reports"
            },
            "filter_config": {
            "region": ["US", "EU"],
            "department": ["Sales", "Marketing"]
            },
            "transform_config": {
            "date_format": "YYYY-MM-DD",
            "currency": "USD"
            }
        },
        {
            "integration_type": "powerbi",
            "connection_config": {
            "workspace_id": "abc123",
            "client_id": "xyz789",
            "client_secret": "A9f3kL2pX8Qw",
            "tenant_id": "tenant123"
            },
            "mapping_config": {
            "dataset_name": "Sales_Data",
            "report_name": "Monthly_Sales_Report"
            },
            "filter_config": {
            "region": ["APAC", "EMEA"],
            "department": ["Finance"]
            },
            "transform_config": {
            "date_format": "MM/DD/YYYY",
            "currency": "EUR"
            }
        },
        {
            "integration_type": "teams",
            "connection_config": {
            "team_id": "team_456",
            "channel_id": "channel_789",
            "bot_token": "bT7xQp9WmZ4R"
            },
            "mapping_config": {
            "message_template": "Daily summary: {summary}"
            },
            "filter_config": {
            "priority": ["high", "medium"]
            },
            "transform_config": {
            "timestamp_format": "YYYY-MM-DD HH:mm:ss"
            }
        },
        {
            "integration_type": "slack",
            "connection_config": {
            "workspace_id": "T12345",
            "channel_id": "C67890",
            "bot_token": "xoxb-9Qw2E7RtV1yZ"
            },
            "mapping_config": {
            "message_template": "Alert: {alert_message}"
            },
            "filter_config": {
            "severity": ["critical", "warning"]
            },
            "transform_config": {
            "timestamp_format": "YYYY-MM-DDTHH:mm:ssZ"
            }
        }
    ]

    await tester.add_integrations(integration_config)
    await asyncio.sleep(20)
    # Test 7: Publish dashboard
    await tester.publish_dashboard()
    await asyncio.sleep(20)
    # Test 8: Edit dashboard
    content_update = {
            "content": {
                "components": [
                {
                "component_type": "question",
                "question": "What is the training completion rate by department?",
                "description": "This report provides a comparative analysis of training completion rates across different departments within the organization. It aims to identify which departments are excelling in employee development and which may require additional support or investigation into their training programs. The data highlights significant variations, with the Engineering department showing the highest completion rate and the Sales department lagging behind.",
                "overview": {
                    "summary": "**EXECUTIVE SUMMARY**\n\nThis analysis reveals a clear disparity in training completion rates across departments. The Engineering department leads with an impressive 88% completion rate, suggesting a strong culture of continuous learning and development. In contrast, the Sales department has the lowest rate at 55%, which could indicate challenges such as time constraints due to client-facing responsibilities or a need for more relevant training content. The overall company average stands at 75%, indicating a generally healthy but improvable training engagement level. These insights are crucial for tailoring departmental training strategies and allocating resources effectively.\n\n**KEY METRICS**\n\n- **Highest Completion Rate:** Engineering (88%)\n- **Lowest Completion Rate:** Sales (55%)\n- **Company Average:** 75%\n- **Departments Analyzed:** 5\n\n--Begin Insights Markdown\n1. **Acknowledge High-Performers:** Recognize the Engineering department for its commitment to training, and study their methods to create best practices for other departments.\n2. **Investigate Low-Performers:** Engage with the Sales department leadership to understand the barriers to training completion. This could involve surveys, focus groups, or one-on-one meetings.\n3. **Set Departmental Goals:** Implement targeted completion rate goals for each department to foster accountability and drive improvement.\n--End Insights Markdown"
                },
                "chart_config": {
                    "format": "vega_lite",
                    "reasoning": "A bar chart is the most effective visualization to compare the completion rates of different departments side-by-side. It allows for quick identification of high and low-performing departments.",
                    "batch_used": 0,
                    "chart_type": "bar",
                    "data_count": 5,
                    "data_sample": {
                    "data": [
                        {
                        "department": "Engineering",
                        "completion_rate": 88
                        },
                        {
                        "department": "Human Resources",
                        "completion_rate": 82
                        },
                        {
                        "department": "Marketing",
                        "completion_rate": 78
                        },
                        {
                        "department": "Support",
                        "completion_rate": 72
                        },
                        {
                        "department": "Sales",
                        "completion_rate": 55
                        }
                    ],
                    "columns": [
                        "department",
                        "completion_rate"
                    ]
                    },
                    "chart_schema": {
                    "data": {
                        "values": []
                    },
                    "mark": {
                        "type": "bar"
                    },
                    "title": "Training Completion Rate by Department",
                    "encoding": {
                        "x": {
                        "field": "department",
                        "type": "nominal",
                        "title": "Department"
                        },
                        "y": {
                        "field": "completion_rate",
                        "type": "quantitative",
                        "title": "Completion Rate (%)"
                        }
                    }
                    },
                    "execution_info": {
                    "data_count": 5,
                    "execution_config": {
                        "sort_by": "completion_rate",
                        "max_rows": 100,
                        "page_size": 100,
                        "sort_order": "DESC",
                        "enable_pagination": False
                    },
                    "validation_success": True
                    }
                },
                "table_config": {},
                "configuration": {
                    "layout": "grid",
                    "theme": "light",
                    "show_title": True
                },
                "sql_query": "SELECT department, (SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS completion_rate FROM employee_trainings GROUP BY department ORDER BY completion_rate DESC;",
                "executive_summary": "The Engineering department shows the highest training completion rate at 88%, while the Sales department has the lowest at 55%. This suggests a need to investigate potential barriers to completion within the Sales team and to leverage best practices from Engineering across the organization to improve overall engagement.",
                "data_overview": {
                    "total_rows": 5,
                    "total_batches": 1,
                    "batches_processed": 1
                },
                "visualization_data": {
                    "data": [
                    {
                        "department": "Engineering",
                        "completion_rate": 88
                    },
                    {
                        "department": "Human Resources",
                        "completion_rate": 82
                    }
                    ],
                    "columns": [
                    "department",
                    "completion_rate"
                    ]
                },
                "sample_data": {
                    "data": [
                    {
                        "department": "Engineering",
                        "completion_rate": 88
                    },
                    {
                        "department": "Human Resources",
                        "completion_rate": 82
                    },
                    {
                        "department": "Marketing",
                        "completion_rate": 78
                    }
                    ],
                    "columns": [
                    "department",
                    "completion_rate"
                    ]
                },
                "metadata": {
                    "project_id": "cornerstone_hr",
                    "data_source": "employee_trainings_view",
                    "processing_stats": {
                    "timestamp": "2025-09-08T18:15:00.000000",
                    "total_tokens": 0,
                    "estimated_cost": 0
                    }
                },
                "chart_schema": {
                    "data": {
                    "values": [
                        {
                        "department": "Engineering",
                        "completion_rate": 88
                        },
                        {
                        "department": "Sales",
                        "completion_rate": 55
                        }
                    ]
                    },
                    "mark": {
                    "type": "bar"
                    },
                    "title": "Training Completion Rate by Department"
                },
                "reasoning": "A bar chart provides a clear and direct comparison of a quantitative metric (completion rate) across different categorical groups (departments), making it easy to spot trends and outliers.",
                "data_count": 5,
                "validation_results": {
                    "status": "success",
                    "message": "Data validation passed successfully."
                }
                },
                {
                "component_type": "question",
                "question": "Which are the most popular training courses based on enrollment?",
                "description": "This analysis identifies the top training courses by the number of registered or completed enrollments. Understanding course popularity helps in planning future training calendars, allocating resources for high-demand topics, and identifying emerging areas of interest among employees.",
                "overview": {
                    "summary": "**EXECUTIVE SUMMARY**\n\nThe data on course enrollment highlights a strong organizational focus on leadership and technical skills. 'Advanced Leadership Skills' is the most popular course with 450 enrollments, indicating a high demand for management development. This is closely followed by 'Cybersecurity Fundamentals' and 'Project Management Essentials', showing that employees are actively seeking to improve their technical and project-based competencies. The popularity of these courses suggests that the current training offerings are well-aligned with key business priorities and employee career goals.\n\n**KEY METRICS**\n\n- **Most Popular Course:** Advanced Leadership Skills (450 enrollments)\n- **Total Enrollments (Top 5 Courses):** 1,850\n- **Top Skill Categories:** Leadership, Cybersecurity, Project Management\n\n--Begin Insights Markdown\n1. **Expand High-Demand Offerings:** Consider adding more sessions or advanced levels for the top-enrolled courses like 'Advanced Leadership Skills' to meet demand.\n2. **Promote Under-Enrolled Courses:** Analyze courses with lower enrollment to determine if the issue is lack of awareness or relevance. A targeted communication campaign may boost numbers.\n3. **Future Curriculum Planning:** Use the enrollment data to inform the creation of new courses. A clear interest in technical skills suggests that courses on topics like Data Analytics or Cloud Computing could be successful.\n--End Insights Markdown"
                },
                "chart_config": {
                    "format": "vega_lite",
                    "reasoning": "A horizontal bar chart is ideal for displaying rankings of categorical data, such as course titles. It provides ample space for long labels and makes it easy to compare the number of enrollments.",
                    "batch_used": 0,
                    "chart_type": "bar",
                    "data_count": 10,
                    "data_sample": {
                    "data": [
                        {
                        "training_title": "Advanced Leadership Skills",
                        "enrollment_count": 450
                        },
                        {
                        "training_title": "Cybersecurity Fundamentals",
                        "enrollment_count": 410
                        },
                        {
                        "training_title": "Project Management Essentials",
                        "enrollment_count": 380
                        }
                    ],
                    "columns": [
                        "training_title",
                        "enrollment_count"
                    ]
                    },
                    "chart_schema": {
                    "data": {
                        "values": []
                    },
                    "mark": {
                        "type": "bar"
                    },
                    "title": "Top 10 Most Popular Training Courses",
                    "encoding": {
                        "y": {
                        "field": "training_title",
                        "type": "nominal",
                        "title": "Training Course",
                        "sort": "-x"
                        },
                        "x": {
                        "field": "enrollment_count",
                        "type": "quantitative",
                        "title": "Number of Enrollments"
                        }
                    }
                    },
                    "execution_info": {
                    "data_count": 10,
                    "execution_config": {
                        "sort_by": "enrollment_count",
                        "max_rows": 10,
                        "page_size": 10,
                        "sort_order": "DESC",
                        "enable_pagination": False
                    },
                    "validation_success": True
                    }
                },
                "table_config": {},
                "configuration": {
                    "layout": "list",
                    "theme": "dark",
                    "show_description": False
                },
                "sql_query": "SELECT training_title, COUNT(user_id) AS enrollment_count FROM csod_training_records GROUP BY training_title ORDER BY enrollment_count DESC LIMIT 10;",
                "executive_summary": "The analysis shows a strong employee interest in leadership and technical skills, with 'Advanced Leadership Skills' being the most enrolled course. This data should be used to guide future curriculum development and resource allocation for training programs.",
                "data_overview": {
                    "total_rows": 10,
                    "total_batches": 1,
                    "batches_processed": 1
                },
                "visualization_data": {
                    "data": [
                        {
                        "training_title": "Advanced Leadership Skills",
                        "enrollment_count": 450
                        },
                        {
                        "training_title": "Cybersecurity Fundamentals",
                        "enrollment_count": 410
                        },
                        {
                        "training_title": "Project Management Essentials",
                        "enrollment_count": 380
                        },
                        {
                        "training_title": "Public Speaking Workshop",
                        "enrollment_count": 320
                        },
                        {
                        "training_title": "Data Privacy and GDPR",
                        "enrollment_count": 290
                        }
                    ],
                    "columns": [
                    "training_title",
                    "enrollment_count"
                    ]
                },
                "sample_data": {
                    "data": [
                        {
                        "training_title": "Advanced Leadership Skills",
                        "enrollment_count": 450
                        },
                        {
                        "training_title": "Cybersecurity Fundamentals",
                        "enrollment_count": 410
                        }
                    ],
                    "columns": [
                    "training_title",
                    "enrollment_count"
                    ]
                },
                "metadata": {
                    "project_id": "cornerstone_dev",
                    "data_source": "training_enrollment_summary",
                    "processing_stats": {
                    "timestamp": "2025-09-08T18:30:00.000000",
                    "total_tokens": 0,
                    "estimated_cost": 0
                    }
                },
                "chart_schema": {
                    "data": {
                    "values": [
                        {
                            "training_title": "Advanced Leadership Skills",
                            "enrollment_count": 450
                        },
                        {
                            "training_title": "Cybersecurity Fundamentals",
                            "enrollment_count": 410
                        }
                    ]
                    },
                    "mark": {
                    "type": "bar"
                    },
                    "title": "Most Popular Courses"
                },
                "reasoning": "A horizontal bar chart is used because some course titles can be long, and this orientation provides more readable labels compared to a vertical chart. It effectively ranks the courses by enrollment.",
                "data_count": 10,
                "validation_results": {
                    "status": "success",
                    "message": "Data validation passed successfully."
                }
                },
                {
                    "component_type": "question",
                    "question": "Are there specific users who have a high number of overdue trainings across different curriculums?",
                    "description": "This report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
                    "overview": {
                    "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown"
                    },
                    "chart_config": {
                    "format": "vega_lite",
                    "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
                    "batch_used": 0,
                    "chart_type": "bar",
                    "data_count": 487,
                    "data_sample": {
                        "data": [
                        {
                            "full_name": "Yvette Reid",
                            "overdue_trainings": "271"
                        }
                        ],
                        "columns": [
                        "full_name",
                        "overdue_trainings"
                        ]
                    },
                    "chart_schema": {
                        "data": {
                        "values": [
                            {
                            "full_name": "Yvette Reid",
                            "overdue_trainings": "271"
                            }
                        ]
                        },
                        "mark": {
                        "type": "bar"
                        },
                        "title": "Overdue Trainings by User",
                        "height": 430,
                        "encoding": {
                        "x": {
                            "type": "nominal",
                            "field": "full_name",
                            "title": "User"
                        },
                        "y": {
                            "type": "quantitative",
                            "field": "overdue_trainings",
                            "title": "Number of Overdue Trainings"
                        },
                        "tooltip": [
                            {
                            "field": "full_name",
                            "title": "User"
                            },
                            {
                            "field": "overdue_trainings",
                            "title": "Number of Overdue Trainings",
                            "format": ","
                            }
                        ]
                        }
                    },
                    "execution_info": {
                        "data_count": 487,
                        "execution_config": {
                        "sort_by": None,
                        "max_rows": 10000,
                        "page_size": 1000,
                        "sort_order": "ASC",
                        "enable_pagination": True
                        },
                        "validation_success": False
                    }
                    },
                    "table_config": {},
                    "configuration": {},
                    "sql_query": "SELECT tr.full_name AS Full_Name, COUNT(*) AS Overdue_Trainings FROM csod_training_records AS tr WHERE tr.due_date < CAST('2025-08-20 00:00:00' AS TIMESTAMP WITH TIME ZONE) GROUP BY tr.full_name HAVING COUNT(*) > 3 ORDER BY Overdue_Trainings DESC",
                    "executive_summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a comprehensive analysis of overdue training requirements within the organization, based on a dataset comprising 487 entries. Each entry represents an individual employee with outstanding training obligations. The analysis reveals significant patterns and trends that warrant attention from senior executives and stakeholders.\n\nKey findings indicate that there are 21 unique values for the number of overdue trainings, reflecting a diverse range of overdue training counts among employees. Notably, the most frequently occurring number of overdue trainings is 132, which appears 151 times, suggesting a common threshold for overdue obligations among a substantial portion of the workforce. However, the analysis also identifies a critical outlier: Yvette Reid, who has an alarming total of 271 overdue trainings, significantly surpassing her peers.\n\nThe distribution of overdue trainings is notably skewed, with a concentration around the 132 mark, indicating that while many employees are facing overdue trainings, a few individuals are experiencing exceptionally high counts. This raises concerns regarding compliance and engagement with training programs, which could pose risks to organizational performance and readiness.\n\n**KEY METRICS**\n\n- Total Records Analyzed: 487\n- Unique Values for Overdue Trainings: 21\n- Most Common Overdue Training Count: 132 (151 occurrences)\n- Highest Number of Overdue Trainings: 271 (Yvette Reid)\n- Distribution Skewness: Concentration around 132 with significant outlier presence\n\nThe findings underscore the need for immediate action to address the high number of overdue trainings, particularly for individuals like Yvette Reid. The data suggests a potential risk in compliance and employee readiness, necessitating a strategic review of training engagement and completion strategies.\n\n--Begin Insights Markdown  \n1. **Targeted Interventions:** Implement focused initiatives for employees with high overdue training counts to enhance compliance and engagement.\n2. **Review Training Strategies:** Conduct a thorough review of current training programs to identify barriers to completion and improve overall training effectiveness.\n3. **Monitor Compliance:** Establish a monitoring system to track overdue trainings and ensure timely completion, thereby reducing risks associated with non-compliance.  \n--End Insights Markdown",
                    "data_overview": {
                    "total_rows": 0,
                    "total_batches": 1,
                    "batches_processed": 1
                    },
                    "visualization_data": {
                    "data": [
                        {
                        "full_name": "Yvette Reid",
                        "overdue_trainings": "271"
                        }
                    ],
                    "columns": [
                        "full_name",
                        "overdue_trainings"
                    ]
                    },
                    "sample_data": {
                    "data": [
                        {
                        "full_name": "Yvette Reid",
                        "overdue_trainings": "271"
                        }
                    ],
                    "columns": [
                        "full_name",
                        "overdue_trainings"
                    ]
                    },
                    "metadata": {
                    "project_id": "cornerstone",
                    "data_description": "I have given the sql query and question.",
                    "processing_stats": {
                        "timestamp": "2025-08-20T15:52:11.327061",
                        "total_tokens": 0,
                        "estimated_cost": 0
                    }
                    },
                    "chart_schema": {
                    "data": {
                        "values": [
                        {
                            "full_name": "Yvette Reid",
                            "overdue_trainings": "271"
                        }
                        ]
                    },
                    "mark": {
                        "type": "bar"
                    },
                    "title": "Overdue Trainings by User",
                    "height": 430,
                    "encoding": {
                        "x": {
                        "type": "nominal",
                        "field": "full_name",
                        "title": "User"
                        },
                        "y": {
                        "type": "quantitative",
                        "field": "overdue_trainings",
                        "title": "Number of Overdue Trainings"
                        },
                        "tooltip": [
                        {
                            "field": "full_name",
                            "title": "User"
                        },
                        {
                            "field": "overdue_trainings",
                            "title": "Number of Overdue Trainings",
                            "format": ","
                        }
                        ]
                    }
                    },
                    "reasoning": "A bar chart is chosen to display the number of overdue trainings for each user, allowing for easy comparison across different individuals. This visualization effectively highlights users with a high number of overdue trainings, which aligns with the user's inquiry.",
                    "data_count": 487,
                    "validation_results": {
                    "data_count": 487,
                    "execution_config": {
                        "sort_by": None,
                        "max_rows": 10000,
                        "page_size": 1000,
                        "sort_order": "ASC",
                        "enable_pagination": True
                    },
                    "validation_success": False
                    }
                },
                {
                    "id": "ce9075cf-3397-4e95-b989-eef8a064ae70",
                    "type": "question",
                    "chart": {
                        "format": "vega_lite",
                        "reasoning": "A KPI chart is chosen to display the highest drop-off rate as a key performance indicator, even though all training titles have the same drop-off rate of 100.0%. This represents critical information regarding training effectiveness.",
                        "batch_used": 0,
                        "chart_type": "kpi",
                        "data_count": 4,
                        "data_sample": {
                        "data": [
                            {
                            "Drop-Off Rate": "100.0",
                            "Training Title": "Code of Conduct Awareness"
                            },
                            {
                            "Drop-Off Rate": "100.0",
                            "Training Title": "Effective Communication"
                            },
                            {
                            "Drop-Off Rate": "100.0",
                            "Training Title": "Product Knowledge"
                            },
                            {
                            "Drop-Off Rate": "100.0",
                            "Training Title": "Time Management"
                            }
                        ],
                        "columns": [
                            "Training Title",
                            "Drop-Off Rate"
                        ]
                        },
                        "chart_schema": {
                        "data": {
                            "values": [
                            {
                                "Drop-Off Rate": "100.0",
                                "Training Title": "Code of Conduct Awareness"
                            },
                            {
                                "Drop-Off Rate": "100.0",
                                "Training Title": "Effective Communication"
                            },
                            {
                                "Drop-Off Rate": "100.0",
                                "Training Title": "Product Knowledge"
                            },
                            {
                                "Drop-Off Rate": "100.0",
                                "Training Title": "Time Management"
                            }
                            ]
                        },
                        "mark": {
                            "type": "text"
                        },
                        "title": "Highest Drop-Off Rate Training",
                        "encoding": {
                            "text": {
                            "type": "quantitative",
                            "field": "value"
                            },
                            "color": {
                            "type": "nominal",
                            "field": "metric"
                            }
                        },
                        "kpi_metadata": {
                            "is_dummy": True,
                            "kpi_data": {
                            "units": [],
                            "values": [],
                            "metrics": [],
                            "targets": []
                            },
                            "chart_type": "kpi",
                            "description": "KPI chart - templates will be created elsewhere",
                            "vega_lite_compatible": False,
                            "requires_custom_template": True
                        }
                        },
                        "execution_info": {
                        "data_count": 4,
                        "execution_config": {
                            "sort_by": None,
                            "max_rows": 10000,
                            "page_size": 1000,
                            "sort_order": "ASC",
                            "enable_pagination": True
                        },
                        "validation_success": False
                        }
                    },
                    "table": {},
                    "overview": {
                        "summary": "**EXECUTIVE SUMMARY**\n\nThis report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown"
                    },
                    "question": "Which training has the highest drop-off rate (i.e., the number of 'Registered' or 'Approved' statuses that did not result in 'Completed')",
                    "sequence": 1,
                    "description": "This report presents a critical analysis of training drop-off rates across four training sessions, revealing a concerning trend that necessitates immediate attention from senior executives and stakeholders. The analysis indicates a uniform drop-off rate of 100%, meaning that every participant who initiated these training sessions failed to complete them. This alarming statistic highlights a systemic issue that could significantly hinder employee development and overall organizational effectiveness.\n\nThe findings suggest that the current training programs may not be meeting the needs or expectations of participants, leading to disengagement and abandonment. Given the uniformity of the drop-off rate across all sessions, it is imperative to investigate the underlying causes, which may include the relevance of training content, the effectiveness of delivery methods, or the strategies employed to engage participants.\n\n**KEY METRICS**\n\n- **Total Training Sessions Analyzed:** 4\n- **Unique Training Titles:** 4\n- **Drop-Off Rate:** 100% across all sessions\n- **Engagement Consistency:** No variation in drop-off rates, indicating a critical area for improvement\n\nThe absence of anomalies or outliers in the data further emphasizes the need for a thorough examination of the training programs. The consistent drop-off rate across all sessions suggests that the issue is not isolated to a specific training title but rather indicative of a broader challenge within the training framework.\n\n--Begin Insights Markdown  \n1. **Immediate Investigation Required:** The 100% drop-off rate is a significant concern that warrants prompt action. Stakeholders should prioritize understanding the factors contributing to this disengagement.\n  \n2. **Feedback Mechanism:** Implementing surveys or feedback mechanisms for participants could provide valuable insights into barriers to completion and areas for improvement in training design and delivery.\n\n3. **Content Relevance and Delivery:** A review of the training content and delivery methods is essential to ensure they align with participant needs and expectations, potentially increasing engagement and completion rates.\n\n4. **Engagement Strategies:** Exploring innovative engagement strategies may enhance participant motivation and commitment to completing training sessions.\n\n5. **Long-term Monitoring:** Establishing a framework for ongoing monitoring of training completion rates and participant feedback will be crucial in assessing the effectiveness of any implemented changes.  \n--End Insights Markdown",
                    "configuration": {
                        "configuration": {
                        "theme": "dark",
                        "layout": "grid",
                        "show_title": True,
                        "data_source": "HR_api_v2"
                        }
                    },
                    "is_configured": True
                }
            ]
            }
    }
    await tester.edit_dashboard(content_update)
    await asyncio.sleep(10)
    # Test 8: Publish dashboard
    await tester.publish_dashboard()
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Print summary
    tester.print_test_summary()
    print(f"⏱️  Total Execution Time: {execution_time:.2f} seconds")
    
    return tester.test_results

if __name__ == "__main__":
    # Run the integration tests
    results = asyncio.run(run_integration_tests())