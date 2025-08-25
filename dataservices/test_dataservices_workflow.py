import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from httpx import AsyncClient, ReadTimeout, RequestError, HTTPStatusError
import json
from datetime import datetime
import random
import re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import random

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

@dataclass
class APIConfig:
    base_url: str = "http://127.0.0.1:8023"
    timeout: float = 1200.0
    max_retries: int = 3
    log_level: LogLevel = LogLevel.INFO

class APIError(Exception):
    """Custom exception for API-related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, endpoint: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(self.message)

class APIClient:
    """Enhanced API client with comprehensive error handling and logging"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Configure logging with file and console handlers"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(getattr(logging, self.config.log_level.value))
        
        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, self.config.log_level.value))
        
        # File handler with timestamp
        log_file = Path(f'api_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request with comprehensive error handling and retry logic
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: JSON payload for request body
            params: URL parameters
            headers: HTTP headers
            
        Returns:
            Response data as dictionary or None if failed
            
        Raises:
            APIError: For API-specific errors
        """
        if not method or not endpoint:
            raise ValueError("Method and endpoint are required")
            
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization":f"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxZTBjYmE4Ni0xMTBhLTRkNDUtYTIwNS0xODI5NjM4ODBkNzUiLCJleHAiOjE3ODc0MDczNTZ9.fVls_y6dr7nOM8XuUvBOlQ0gK1bmB1iRD2gXqaPczTc"
        }
        for attempt in range(self.config.max_retries):
            try:
                async with AsyncClient(timeout=self.config.timeout) as client:
                    self.logger.info(f"Making {method} request to {url} (attempt {attempt + 1}/{self.config.max_retries})")
                    
                    if data and self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Request payload: {json.dumps(data, indent=2, default=str)}")
                    
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        json=data,
                        params=params,
                        headers=headers
                    )
                    
                    self.logger.info(f"Response status: {response.status_code}")
                    
                    # Handle HTTP errors
                    if response.status_code >= 400:
                        error_message = f"HTTP {response.status_code} error for {endpoint}"
                        try:
                            error_detail = response.text
                            if error_detail:
                                self.logger.error(f"{error_message}: {error_detail}")
                            else:
                                self.logger.error(error_message)
                        except Exception as e:
                            self.logger.error(f"{error_message}: Could not read error details - {e}")
                        
                        if attempt == self.config.max_retries - 1:
                            raise APIError(error_message, response.status_code, endpoint)
                        continue
                    
                    # Parse response
                    try:
                        result = response.json()
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"Response data: {json.dumps(result, indent=2, default=str)}")
                        return result
                    except json.JSONDecodeError:
                        self.logger.info("Request successful (non-JSON response)")
                        return {"status": "success", "status_code": response.status_code}
                
            except ReadTimeout:
                self.logger.warning(f"Request timeout (attempt {attempt + 1}/{self.config.max_retries})")
                if attempt == self.config.max_retries - 1:
                    raise APIError(f"Request timed out after {self.config.max_retries} attempts", endpoint=endpoint)
                    
            except RequestError as e:
                self.logger.error(f"Request error: {e} (attempt {attempt + 1}/{self.config.max_retries})")
                if attempt == self.config.max_retries - 1:
                    raise APIError(f"Request failed after {self.config.max_retries} attempts: {e}", endpoint=endpoint)
                    
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                if attempt == self.config.max_retries - 1:
                    raise APIError(f"Unexpected error: {e}", endpoint=endpoint)
                
            # Exponential backoff
            if attempt < self.config.max_retries - 1:
                wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                self.logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        return None

class DataModelingAPI:
    """High-level API for data modeling operations"""
    
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = client.logger

    async def create_datasource(self, datasource_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new data source connection"""
        if not datasource_config.get("name") or not datasource_config.get("database_type"):
            raise ValueError("Datasource name and database_type are required")
            
        try:
            result = await self.client.make_request("POST", "/datasources/connections/createConnections", data=datasource_config)
            if not result or not result.get("connection_id"):
                raise APIError("Failed to create datasource - missing connection_id in response")
            return result
        except Exception as e:
            self.logger.error(f"Failed to create datasource: {e}")
            raise

    async def get_erd(self, connection_id: str) -> Dict[str, Any]:
        """Get Entity Relationship Diagram for a connection"""
        if not connection_id:
            raise ValueError("Connection ID is required")
            
        try:
            result = await self.client.make_request("GET", f"/datasources/connections/{connection_id}/ERD")
            if not result or not result.get("tables"):
                raise APIError("Failed to get ERD - missing tables in response")
            return result
        except Exception as e:
            self.logger.error(f"Failed to get ERD for connection {connection_id}: {e}")
            raise

    async def create_semantic_models(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create semantic models for multiple tables"""
        if not tables:
            raise ValueError("Tables list cannot be empty")
            
        valid_tables = []
        for i, table in enumerate(tables):
            if not table.get("name"):
                self.logger.warning(f"Skipping table at index {i} - missing name")
                continue
            valid_tables.append(table)
        
        if not valid_tables:
            raise ValueError("No valid tables provided")
            
        try:
            tasks = [self.client.make_request("POST", "/semantics/semantics/describe-table", data=table) for table in valid_tables]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and log them
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to create semantic model for table {valid_tables[i].get('name', 'unknown')}: {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create semantic models: {e}")
            raise

    async def create_domain(self, domain_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new domain"""
        required_fields = ["domain_id", "display_name", "description", "created_by"]
        missing_fields = [field for field in required_fields if not domain_config.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
            
        try:
            result = await self.client.make_request("POST", "/projects/workflow/workflow/domain", data=domain_config)
            if not result or not result.get("domain_id"):
                raise APIError("Failed to create domain - missing domain_id in response")
            return result
        except Exception as e:
            self.logger.error(f"Failed to create domain: {e}")
            raise

    async def create_dataset(self, dataset_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new dataset"""
        required_fields = ["domain_id", "name", "connection_id"]
        missing_fields = [field for field in required_fields if not dataset_config.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
            
        try:
            result = await self.client.make_request("POST", "/projects/workflow/workflow/dataset", data=dataset_config)
            if not result or not result.get("dataset_id"):
                raise APIError("Failed to create dataset - missing dataset_id in response")
            return result
        except Exception as e:
            self.logger.error(f"Failed to create dataset: {e}")
            raise

    async def create_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple tables"""
        if not tables:
            raise ValueError("Tables list cannot be empty")
            
        valid_tables = []
        for i, table in enumerate(tables):
            if not table.get("add_table_request", {}).get("dataset_id"):
                self.logger.warning(f"Skipping table at index {i} - missing dataset_id")
                continue
            valid_tables.append(table)
        
        if not valid_tables:
            raise ValueError("No valid tables provided")
            
        try:
            tasks = [self.client.make_request("POST", "/projects/workflow/workflow/table", data=table) for table in valid_tables]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    table_name = valid_tables[i].get("add_table_request", {}).get("schema", {}).get("table_name", "unknown")
                    self.logger.error(f"Failed to create table {table_name}: {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create tables: {e}")
            raise

    async def get_share_permissions(self, domain_id: str) -> Dict[str, Any]:
        """Get sharing permissions for a domain"""
        if not domain_id:
            raise ValueError("Domain ID is required")
            
        try:
            return await self.client.make_request("GET", f"/projects/workflow/workflow/{domain_id}/sharing-permissions")
        except Exception as e:
            self.logger.error(f"Failed to get share permissions for domain {domain_id}: {e}")
            raise

    # async def share_domain(self, domain_id: str) -> Dict[str, Any]:
    #     """Setup sharing permissions for a domain"""
    #     if not domain_id:
    #         raise ValueError("Domain ID is required")
            
    #     try:
    #         return await self.client.make_request("POST", f"/projects/workflow/workflow/{domain_id}/setup-sharing-permissions")
    #     except Exception as e:
    #         self.logger.error(f"Failed to share domain {domain_id}: {e}")
    #         raise

    async def commit_domain(self) -> Dict[str, Any]:
        """Commit domain changes"""
        try:
            return await self.client.make_request("POST", "/projects/workflow/workflow/commit")
        except Exception as e:
            self.logger.error(f"Failed to commit domain: {e}")
            raise

    async def create_metrics(self, table_id: str, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple metrics for a table"""
        if not table_id or not metrics:
            raise ValueError("Table ID and metrics list are required")
            
        valid_metrics = []
        for i, metric in enumerate(metrics):
            if not metric.get("name"):
                self.logger.warning(f"Skipping metric at index {i} - missing name")
                continue
            valid_metrics.append(metric)
        
        if not valid_metrics:
            raise ValueError("No valid metrics provided")
            
        try:
            tasks = [self.client.make_request("POST", "/projects/workflow/workflow/metric", data=metric, params={"table_id": table_id}) for metric in valid_metrics]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    metric_name = valid_metrics[i].get("name", "unknown")
                    self.logger.error(f"Failed to create metric {metric_name}: {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create metrics for table {table_id}: {e}")
            raise

    async def create_views(self, table_id: str, views: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple views for a table"""
        if not table_id or not views:
            raise ValueError("Table ID and views list are required")
            
        valid_views = []
        for i, view in enumerate(views):
            if not view.get("name"):
                self.logger.warning(f"Skipping view at index {i} - missing name")
                continue
            valid_views.append(view)
        
        if not valid_views:
            raise ValueError("No valid views provided")
            
        try:
            tasks = [self.client.make_request("POST", "/projects/workflow/workflow/view", data=view, params={"table_id": table_id}) for view in valid_views]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    view_name = valid_views[i].get("name", "unknown")
                    self.logger.error(f"Failed to create view {view_name}: {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create views for table {table_id}: {e}")
            raise

    async def create_calculated_columns(self, table_id: str, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple calculated columns for a table"""
        if not table_id or not columns:
            raise ValueError("Table ID and columns list are required")
            
        valid_columns = []
        for i, column in enumerate(columns):
            if not column.get("name"):
                self.logger.warning(f"Skipping column at index {i} - missing name")
                continue
            valid_columns.append(column)
        
        if not valid_columns:
            raise ValueError("No valid columns provided")
            
        try:
            tasks = [self.client.make_request("POST", "/projects/workflow/workflow/calculated-column", data=column, params={"table_id": table_id}) for column in valid_columns]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    column_name = valid_columns[i].get("name", "unknown")
                    self.logger.error(f"Failed to create calculated column {column_name}: {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create calculated columns for table {table_id}: {e}")
            raise

class LearningAPI:
    """API for learning-related operations"""
    
    def __init__(self, client: APIClient):
        self.client = client
        self.logger = client.logger

    async def create_instructions(self, instructions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple instructions"""
        if not instructions:
            raise ValueError("Instructions list cannot be empty")
            
        valid_instructions = []
        for i, instruction in enumerate(instructions):
            required_fields = ["domain_id", "question", "instructions", "sql_query"]
            missing_fields = [field for field in required_fields if not instruction.get(field)]
            
            if missing_fields:
                self.logger.warning(f"Skipping instruction at index {i} - missing fields: {missing_fields}")
                continue
            valid_instructions.append(instruction)
        
        if not valid_instructions:
            raise ValueError("No valid instructions provided")
            
        try:
            tasks = [self.client.make_request("POST", "/instructions/instructions/", data=instruction) for instruction in valid_instructions]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    question = valid_instructions[i].get("question", "unknown")
                    self.logger.error(f"Failed to create instruction '{question}': {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create instructions: {e}")
            raise

    async def create_examples(self, examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple examples"""
        if not examples:
            raise ValueError("Examples list cannot be empty")
            
        valid_examples = []
        for i, example in enumerate(examples):
            required_fields = ["domain_id", "definition_type", "name", "question", "sql_query"]
            missing_fields = [field for field in required_fields if not example.get(field)]
            
            if missing_fields:
                self.logger.warning(f"Skipping example at index {i} - missing fields: {missing_fields}")
                continue
            valid_examples.append(example)
        
        if not valid_examples:
            raise ValueError("No valid examples provided")
            
        try:
            tasks = [self.client.make_request("POST", "/examples/examples/", data=example) for example in valid_examples]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    name = valid_examples[i].get("name", "unknown")
                    self.logger.error(f"Failed to create example '{name}': {result}")
                else:
                    successful_results.append(result)
            
            return successful_results
        except Exception as e:
            self.logger.error(f"Failed to create examples: {e}")
            raise

class DataProcessor:
    """Utility class for data processing operations"""
    
    @staticmethod
    def parse_column(column_definition: str) -> Dict[str, Any]:
        """Parse column definition into structured format"""
        if not column_definition or not isinstance(column_definition, str):
            raise ValueError("Column definition must be a non-empty string")
            
        # Enhanced regex pattern to handle more column formats
        pattern = r"(\w+)\s+\(([^)]+)\)(?:\s+\[(.+)\])?"
        match = re.match(pattern, column_definition.strip())
        
        if match:
            name, data_type, meta = match.groups()
        else:
            # Fallback for simpler formats
            parts = column_definition.strip().split()
            name = parts[0] if parts else column_definition
            data_type = "text"
            meta = None
        
        return {
            "name": name,
            "display_name": name.replace("_", " ").title(),
            "description": f"{name.replace('_', ' ')} field",
            "data_type": data_type.lower(),
            "is_primary_key": meta == "PK" if meta else False,
            "is_nullable": meta != "PK" if meta else True,
            "usage_type": "identifier" if meta == "PK" else "attribute"
        }

    @staticmethod
    def get_random_tables(erd_tables: List[Dict[str, Any]], count: int = 3) -> List[Dict[str, Any]]:
        """Select random tables and format them for processing"""
        if not erd_tables:
            raise ValueError("ERD tables list cannot be empty")
            
        if count <= 0:
            raise ValueError("Count must be positive")
            
        # Ensure we don't try to sample more than available
        sample_count = min(count, len(erd_tables))
        selected_tables = random.sample(erd_tables, sample_count)
        
        result = []
        for table in selected_tables:
            if not table.get("name"):
                continue
                
            columns = table.get("columns", [])
            processed_columns = []
            
            for column in columns:
                try:
                    processed_column = DataProcessor.parse_column(column)
                    processed_columns.append(processed_column)
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Failed to parse column '{column}': {e}")
                    continue
            
            if processed_columns:  # Only add table if it has valid columns
                result.append({
                    "name": table["name"],
                    "display_name": table["name"].replace("_", " ").title(),
                    "description": f"Table storing {table['name'].replace('_', ' ')} related data",
                    "columns": processed_columns,
                    "business_domain": "General"
                })
        
        return result

async def main():
    """Main execution function with comprehensive error handling"""
    config = APIConfig(
        base_url="http://127.0.0.1:8023",
        timeout=1200.0,
        max_retries=3,
        log_level=LogLevel.INFO
    )
    
    client = APIClient(config)
    data_modeling_api = DataModelingAPI(client)
    learning_api = LearningAPI(client)
    
    try:
        # Step 1: Create datasource
        client.logger.info("Starting datasource creation...")
        datasource_config = {
            "name": "APITest_Uneda_dev",
            "database_type": "postgresql",
            "database_details": {
                "host": "unedadevpostgresql.postgres.database.azure.com",
                "port": "5432",
                "username": "pixentia",
                "password": "FLc&dL@M9A5Q7wI;",
                "database": "phenom_egen_ai"
            }
        }
        
        data_source = await data_modeling_api.create_datasource(datasource_config)
        client.logger.info(f"Created datasource successfully: {data_source.get('connection_name', 'Unknown')}")

        # Step 2: Get ERD
        client.logger.info("Fetching ERD tables...")
        erd_data = await data_modeling_api.get_erd(data_source['connection_id'])
        client.logger.info(f"Retrieved {len(erd_data.get('tables', []))} tables from ERD")

        # Step 3: Create domain
        client.logger.info("Creating domain...")
        domain_config = {
            "domain_id": "IntegrationCSOD",
            "display_name": "CSOD Integration",
            "description": "Here we are integrating the CSOD domain into the Data Modelling framework to enable seamless data engineering, semantic enrichment, and business intelligence capabilities.",
            "created_by": "john.doe@example.com",
            "context": {
                "domain_id": "IntegrationCSOD",
                "domain_name": "Cornerstone OnDemand Integration",
                "business_domain": "Learning & Talent Management",
                "purpose": "To centralize and harmonize training, learning, and talent management data from CSOD into the enterprise data ecosystem. This integration provides a semantic layer that simplifies analytics, reporting, and AI-driven insights for business stakeholders.",
                "target_users": [
                    "Learning & Development Teams",
                    "HR and Talent Management Professionals",
                    "Data Engineers and Analysts",
                    "Business Intelligence Teams",
                    "Compliance Officers"
                ],
                "key_business_concepts": [
                    "Curriculum and Course Management",
                    "Training Records and Transcripts",
                    "Employee Skills and Competency Tracking",
                    "Managerial Oversight and Reporting",
                    "Compliance and Certification Tracking",
                    "Business Models and Semantic Datasets"
                ],
                "data_sources": [
                    "CSOD Training Records",
                    "CSOD Curriculum and Course Catalogs",
                    "Employee and Manager Profiles",
                    "CSOD Transcript Data",
                    "CSOD Learning Events"
                ],
                "compliance_requirements": [
                    "Corporate Learning Compliance Policies",
                    "Industry Certification Standards (e.g., ISO, OSHA, HIPAA where applicable)",
                    "Data Privacy and Protection Regulations (GDPR, CCPA)",
                    "Internal Audit and Reporting Standards"
                ]
            }
        }

        created_domain = await data_modeling_api.create_domain(domain_config)
        client.logger.info(f"Created domain successfully: {created_domain.get('display_name', 'Unknown')} {created_domain}")
        
        # Step 4: Process random tables and create semantic models
        client.logger.info("Processing tables for semantic modeling...")
        random_tables = DataProcessor.get_random_tables(erd_data["tables"], 3)
        
        tables_for_semantic = [
            {**table, "domain_id": created_domain["domain_id"], "domain_name": created_domain["display_name"]}
            for table in random_tables
        ]
        
        semantic_models = await data_modeling_api.create_semantic_models(tables_for_semantic)
        client.logger.info(f"Created {len(semantic_models)} semantic models successfully")

        # Step 5: Create dataset
        client.logger.info("Creating dataset...")
        dataset_config = {
            "domain_id": created_domain['domain_id'],
            "name": "Learner Attempts",
            "description": "This dataset is created to get the Learner Attempts",
            "connection_id": data_source['connection_id'],
            "permissions":{
                "entity_id":"d91c0418-8af0-4224-9918-449ef51e462c",
                "entity_type":"user",
                "permission":"read_write"
            }
        }
        
        created_dataset = await data_modeling_api.create_dataset(dataset_config)
        client.logger.info(f"Created dataset successfully: {created_dataset.get('name', 'Unknown')},{created_dataset}")

        # Step 6: Create tables
        client.logger.info("Creating tables...")
        tables_config = [{
            "add_table_request": {
                "dataset_id": created_dataset["dataset_id"],
                "schema": {
                    "table_name": table['display_name'],
                    "table_description": table['description'],
                    "columns": table['columns']
                }
            },
            "domain_context": created_domain['context']
        } for table in tables_for_semantic]

        created_tables = await data_modeling_api.create_tables(tables_config)
        client.logger.info(f"Created {len(created_tables)} tables successfully")

        # Step 7: Setup domain sharing
        client.logger.info("Setting up domain sharing...")
        share_permissions = await data_modeling_api.get_share_permissions(created_domain["domain_id"])
        client.logger.info(f"Retrieved sharing permissions: {len(share_permissions) if share_permissions else 0} permissions")

        # await data_modeling_api.share_domain(created_domain["domain_id"])
        client.logger.info("Domain sharing setup completed")

        await data_modeling_api.commit_domain()
        client.logger.info("Domain committed successfully")

        await asyncio.sleep(150)

        client.logger.info(f"Waiting for the domain to become active. Estimated time: 150 seconds...")

        # Step 8: Create metrics, views, and calculated columns for each table
        client.logger.info("Creating metrics, views, and calculated columns...")
        
        metrics_config = [
            {
                "name": "completion_rate",
                "display_name": "Completion Rate",
                "description": "Percentage of assigned trainings that have been successfully completed by users.",
                "metric_sql": "SELECT (COUNT(*) FILTER (WHERE is_completed = TRUE)::decimal / COUNT(*)::decimal) * 100 FROM csod_training_records;",
                "metric_type": "percentage",
                "aggregation_type": "avg"
            },
            {
                "name": "average_completion_time",
                "display_name": "Average Completion Time",
                "description": "The average number of days taken by users to complete a training after assignment.",
                "metric_sql": "SELECT AVG(EXTRACT(DAY FROM (completion_date - assigned_date))) FROM csod_training_records WHERE is_completed = TRUE;",
                "metric_type": "duration",
                "aggregation_type": "avg"
            },
            {
                "name": "overdue_training_count",
                "display_name": "Overdue Training Count",
                "description": "Number of trainings where the due date has passed but completion has not occurred.",
                "metric_sql": "SELECT COUNT(*) FROM csod_training_records WHERE is_overdue = TRUE;",
                "metric_type": "count",
                "aggregation_type": "sum"
            }
        ]

        views_config = [
            {
                "name": "active_training_assignments",
                "display_name": "Active Training Assignments",
                "description": "A view listing all active training assignments with user, training, and due date details. Useful for monitoring ongoing training obligations.",
                "view_sql": "SELECT user_id, full_name, training_title, assigned_date, due_date, transcript_status FROM csod_training_records WHERE is_assigned = TRUE AND is_completed = FALSE;",
                "view_type": "table"
            },
            {
                "name": "completed_trainings",
                "display_name": "Completed Trainings",
                "description": "Shows all trainings that have been successfully completed by users, including completion dates and satisfaction status.",
                "view_sql": "SELECT user_id, full_name, training_title, completion_date, satisfied_late FROM csod_training_records WHERE is_completed = TRUE;",
                "view_type": "table"
            },
            {
                "name": "overdue_trainings",
                "display_name": "Overdue Trainings",
                "description": "A list of all training assignments that are overdue based on due date and completion status.",
                "view_sql": "SELECT user_id, full_name, training_title, due_date FROM csod_training_records WHERE is_overdue = TRUE;",
                "view_type": "table"
            },
            {
                "name": "certification_status",
                "display_name": "Certification Status",
                "description": "View showing users' certification compliance, including expirations and current status.",
                "view_sql": "SELECT user_id, full_name, training_title, is_compliant, expiration_date FROM csod_training_records WHERE is_certification = TRUE;",
                "view_type": "table"
            },
            {
                "name": "training_summary_by_manager",
                "display_name": "Training Summary by Manager",
                "description": "Aggregated view of training completion status grouped by manager, useful for managerial oversight and compliance tracking.",
                "view_sql": "SELECT manager_name, COUNT(*) AS total_assigned, SUM(CASE WHEN is_completed = TRUE THEN 1 ELSE 0 END) AS completed, SUM(CASE WHEN is_overdue = TRUE THEN 1 ELSE 0 END) AS overdue FROM csod_training_records GROUP BY manager_name;",
                "view_type": "aggregate"
            },
            {
                "name": "user_training_history",
                "display_name": "User Training History",
                "description": "Full history of training records for each user, including assignments, completions, and status changes.",
                "view_sql": "SELECT user_id, full_name, training_title, assigned_date, completed_date, transcript_status FROM csod_training_records ORDER BY user_id, assigned_date;",
                "view_type": "table"
            }
        ]

        calculated_columns_config = [
            {
                "name": "training_completion_duration",
                "display_name": "Training Completion Duration",
                "description": "Total number of days taken by a user to finish training after assignment.",
                "calculation_sql": "EXTRACT(DAY FROM (completion_date - assigned_date))",
                "data_type": "integer",
                "usage_type": "calculated",
                "is_nullable": True,
                "is_primary_key": False,
                "is_foreign_key": False,
                "default_value": None,
                "ordinal_position": 1,
                "function_id": "calc_training_completion_duration",
                "dependencies": ["assigned_date", "completion_date"],
                "json_metadata": {}
            },
            {
                "name": "completed_after_due",
                "display_name": "Completed After Due Date",
                "description": "Boolean flag indicating whether the training was finished past its due date.",
                "calculation_sql": "CASE WHEN completion_date > due_date THEN TRUE ELSE FALSE END",
                "data_type": "boolean",
                "usage_type": "calculated",
                "is_nullable": False,
                "is_primary_key": False,
                "is_foreign_key": False,
                "default_value": "FALSE",
                "ordinal_position": 2,
                "function_id": "calc_completed_after_due",
                "dependencies": ["completion_date", "due_date"],
                "json_metadata": {}
            },
            {
                "name": "late_days_count",
                "display_name": "Late Days Count",
                "description": "Shows the number of days a training was overdue before being completed or currently pending.",
                "calculation_sql": "CASE WHEN completion_date > due_date THEN EXTRACT(DAY FROM (completion_date - due_date)) WHEN is_overdue = TRUE THEN EXTRACT(DAY FROM (CURRENT_DATE - due_date)) ELSE NULL END",
                "data_type": "integer",
                "usage_type": "calculated",
                "is_nullable": True,
                "is_primary_key": False,
                "is_foreign_key": False,
                "default_value": None,
                "ordinal_position": 3,
                "function_id": "calc_late_days_count",
                "dependencies": ["completion_date", "due_date", "is_overdue"],
                "json_metadata": {}
            },
            {
                "name": "normalized_completion_status",
                "display_name": "Normalized Completion Status",
                "description": "Training status categorized as 'On Time', 'Late', 'Pending', or 'Overdue'.",
                "calculation_sql": "CASE WHEN is_completed = TRUE AND completion_date <= due_date THEN 'On Time' WHEN is_completed = TRUE AND completion_date > due_date THEN 'Late' WHEN is_completed = FALSE AND due_date < CURRENT_DATE THEN 'Overdue' ELSE 'Pending' END",
                "data_type": "varchar",
                "usage_type": "calculated",
                "is_nullable": False,
                "is_primary_key": False,
                "is_foreign_key": False,
                "default_value": "'Pending'",
                "ordinal_position": 4,
                "function_id": "calc_normalized_completion_status",
                "dependencies": ["is_completed", "completion_date", "due_date"],
                "json_metadata": {}
            },
            {
                "name": "completion_month",
                "display_name": "Completion Month",
                "description": "Year and month the training was completed, useful for trend visualization.",
                "calculation_sql": "TO_CHAR(completion_date, 'YYYY-MM')",
                "data_type": "varchar",
                "usage_type": "calculated",
                "is_nullable": True,
                "is_primary_key": False,
                "is_foreign_key": False,
                "default_value": None,
                "ordinal_position": 5,
                "function_id": "calc_completion_month",
                "dependencies": ["completion_date"],
                "json_metadata": {}
            },
            {
                "name": "manager_team_compliance",
                "display_name": "Manager Team Compliance",
                "description": "Indicates whether all of a manager's direct reports have completed their assigned trainings.",
                "calculation_sql": "CASE WHEN NOT EXISTS (SELECT 1 FROM csod_training_records t2 WHERE t2.manager_name = csod_training_records.manager_name AND t2.is_completed = FALSE) THEN TRUE ELSE FALSE END",
                "data_type": "boolean",
                "usage_type": "calculated",
                "is_nullable": False,
                "is_primary_key": False,
                "is_foreign_key": False,
                "default_value": "FALSE",
                "ordinal_position": 6,
                "function_id": "calc_manager_team_compliance",
                "dependencies": ["manager_name", "is_completed"],
                "json_metadata": {}
            }
    ]


        # Create metrics, views, and calculated columns for each table
        if metrics_config:
            random.shuffle(metrics_config)
        if views_config:
            random.shuffle(views_config)
        if calculated_columns_config:
            random.shuffle(calculated_columns_config)

        metrics_index = 0
        views_index = 0
        columns_index = 0

        for table in created_tables:
            table_id = table.get('table_id')
            if not table_id:
                client.logger.warning("Skipping table operations - missing table_id")
                continue
                
            table_name = table.get('name', 'Unknown')
            client.logger.info(f"Processing table: {table_name}")

            try:
                # Create 1-2 metrics per table
                if metrics_index < len(metrics_config):
                    metrics_count = random.randint(1, min(2, len(metrics_config) - metrics_index))
                    table_metrics = metrics_config[metrics_index:metrics_index + metrics_count]
                    created_metrics = await data_modeling_api.create_metrics(table_id, table_metrics)
                    client.logger.info(f"Created {len(created_metrics)} metrics for table {table_name}")
                    metrics_index += metrics_count

                # Create 1-2 views per table
                if views_index < len(views_config):
                    views_count = random.randint(1, min(2, len(views_config) - views_index))
                    table_views = views_config[views_index:views_index + views_count]
                    created_views = await data_modeling_api.create_views(table_id, table_views)
                    client.logger.info(f"Created {len(created_views)} views for table {table_name}")
                    views_index += views_count

                # Create 1-2 calculated columns per table
                if columns_index < len(calculated_columns_config):
                    columns_count = random.randint(1, min(2, len(calculated_columns_config) - columns_index))
                    table_columns = calculated_columns_config[columns_index:columns_index + columns_count]
                    created_columns = await data_modeling_api.create_calculated_columns(table_id, table_columns)
                    client.logger.info(f"Created {len(created_columns)} calculated columns for table {table_name}")
                    columns_index += columns_count

            except Exception as e:
                client.logger.error(f"Failed to process table {table_name}: {e}")
                continue

        # Step 9: Create instructions
        client.logger.info("Creating instructions...")
        instructions_config = [
            {
                "domain_id": created_domain['domain_id'],
                "question": "What is the completion rate of trainings?",
                "instructions": "LLM must calculate completion rate as (completed / assigned) * 100. Do not divide by all records, only those assigned.",
                "sql_query": "SELECT (COUNT(*) FILTER (WHERE is_completed = TRUE)::decimal / COUNT(*) FILTER (WHERE is_assigned = TRUE)::decimal) * 100 AS completion_rate FROM csod_training_records;",
                "chain_of_thought": "The model incorrectly used total records as denominator. Correct approach is to use assigned trainings as denominator.",
                "json_metadata": {}
            },
            {
                "domain_id": created_domain['domain_id'],
                "question": "List overdue trainings.",
                "instructions": "Overdue means due_date < CURRENT_DATE AND is_completed = FALSE. Do not confuse overdue with satisfied_late (which applies to completed trainings).",
                "sql_query": "SELECT user_id, full_name, training_title, due_date FROM csod_training_records WHERE is_completed = FALSE AND due_date < CURRENT_DATE;",
                "chain_of_thought": "The LLM mistakenly filtered on satisfied_late column. Correct logic requires due_date < CURRENT_DATE and completion is still false.",
                "json_metadata": {}
            },
            {
                "domain_id": created_domain['domain_id'],
                "question": "Show training summary by manager.",
                "instructions": "Always group by manager_name. Count total assigned, completed, and overdue separately. Do not aggregate across the entire dataset without grouping.",
                "sql_query": "SELECT manager_name, COUNT(*) AS total_assigned, SUM(CASE WHEN is_completed = TRUE THEN 1 ELSE 0 END) AS completed, SUM(CASE WHEN due_date < CURRENT_DATE AND is_completed = FALSE THEN 1 ELSE 0 END) AS overdue FROM csod_training_records GROUP BY manager_name;",
                "chain_of_thought": "The LLM initially forgot the GROUP BY manager_name and tried to return global counts. Correct approach aggregates per manager.",
                "json_metadata": {}
            },
            {
                "domain_id": created_domain['domain_id'],
                "question": "Calculate average completion time for trainings.",
                "instructions": "Average completion time must be based on completed trainings only. Ignore null completion_date values.",
                "sql_query": "SELECT AVG(EXTRACT(DAY FROM (completion_date - assigned_date))) AS avg_days_to_complete FROM csod_training_records WHERE is_completed = TRUE;",
                "chain_of_thought": "The model mistakenly included rows with no completion_date, producing null results. Correct logic filters only completed trainings.",
                "json_metadata": {}
            },
            {
                "domain_id": created_domain['domain_id'],
                "question": "Find certification compliance rate.",
                "instructions": "Compliance rate must be calculated only for rows where is_certification = TRUE. Do not include non-certification trainings.",
                "sql_query": "SELECT (COUNT(*) FILTER (WHERE is_compliant = TRUE)::decimal / COUNT(*)::decimal) * 100 AS certification_compliance FROM csod_training_records WHERE is_certification = TRUE;",
                "chain_of_thought": "The LLM mistakenly included all trainings. Correction: restrict scope to certifications only.",
                "json_metadata": {}
            }
        ]

        created_instructions = await learning_api.create_instructions(instructions_config)
        client.logger.info(f"Created {len(created_instructions)} instructions successfully")

        # Step 10: Create examples
        client.logger.info("Creating examples...")
        examples_config = [
            {
                "domain_id": created_domain['domain_id'],
                "definition_type": "metric",
                "name": "completion_rate",
                "question": "What is the training completion rate for all assigned trainings?",
                "sql_query": "SELECT (COUNT(*) FILTER (WHERE is_completed = TRUE)::decimal / COUNT(*) FILTER (WHERE is_assigned = TRUE)::decimal) * 100 AS completion_rate FROM csod_training_records;",
                "context": "Tracks the percentage of trainings completed out of those assigned, used as a KPI by Learn Admins.",
                "document_reference": "CSOD Admin Metrics Guide - Section 3",
                "instructions": "Always divide completed by assigned trainings, not total records.",
                "categories": ["training", "kpi", "compliance"],
                "samples": [
                {"input": "Show me completion rate"},
                {"input": "What % of trainings are completed?"}
                ],
                "additional_context": {
                "business_value": "Used in compliance dashboards to measure overall learner engagement.",
                "visualization_hint": "Recommended as a gauge or KPI card with thresholds: <70% red, 70–90% amber, >90% green.",
                "edge_cases": ["Exclude withdrawn or canceled enrollments.", "Null values in due_date should not affect denominator."]
                },
                "user_id": "system",
                "json_metadata": {
                "source_table": "csod_training_records",
                "dependencies": ["is_assigned", "is_completed"],
                "data_type": "percentage",
                "aggregation": "avg",
                "tags": ["kpi", "completion", "training"]
                }
            },
            {
                "domain_id": created_domain['domain_id'],
                "definition_type": "view",
                "name": "overdue_trainings",
                "question": "List all overdue trainings that are not yet completed.",
                "sql_query": "SELECT user_id, full_name, training_title, due_date FROM csod_training_records WHERE is_completed = FALSE AND due_date < CURRENT_DATE;",
                "context": "Provides a list of overdue trainings for proactive compliance management.",
                "document_reference": "CSOD Compliance Dashboard Spec",
                "instructions": "Filter only trainings past due_date and not completed.",
                "categories": ["overdue", "compliance", "training"],
                "samples": [
                {"input": "List overdue trainings"},
                {"input": "Which trainings are overdue?"}
                ],
                "additional_context": {
                "business_value": "Helps compliance managers track which employees are at risk of failing mandatory training requirements.",
                "visualization_hint": "Tabular view with sorting by due_date. Optional grouping by department.",
                "edge_cases": ["Handle users with no due_date set (exclude them)."]
                },
                "user_id": "system",
                "json_metadata": {
                "source_table": "csod_training_records",
                "dependencies": ["is_completed", "due_date"],
                "data_type": "table",
                "tags": ["compliance", "audit", "overdue"]
                }
            },
            {
                "domain_id": created_domain['domain_id'],
                "definition_type": "calculated_column",
                "name": "days_to_complete",
                "question": "How many days did it take a user to complete a training?",
                "sql_query": "EXTRACT(DAY FROM (completion_date - assigned_date))",
                "context": "Derived column measuring the time gap between assignment and completion, useful for efficiency analysis.",
                "document_reference": "Data Modelling - Calculated Fields",
                "instructions": "Use only rows with non-null completion_date and assigned_date.",
                "categories": ["derived", "timing", "training"],
                "samples": [
                {"input": "Show days to complete"},
                {"input": "How long did completion take?"}
                ],
                "additional_context": {
                "business_value": "Measures training efficiency and identifies bottlenecks in training programs.",
                "visualization_hint": "Histogram or boxplot to show distribution of completion times.",
                "edge_cases": ["Exclude self-paced courses with no assigned_date."]
                },
                "user_id": "system",
                "json_metadata": {
                "source_table": "csod_training_records",
                "dependencies": ["assigned_date", "completion_date"],
                "data_type": "integer",
                "tags": ["timing", "calculated", "training"]
                }
            },
            {
                "domain_id": created_domain['domain_id'],
                "definition_type": "sql_pair",
                "name": "active_vs_inactive_users",
                "question": "Compare active vs inactive users in training participation.",
                "sql_query": "SELECT CASE WHEN completion_date IS NOT NULL OR assigned_date IS NOT NULL THEN 'Active' ELSE 'Inactive' END AS user_status, COUNT(DISTINCT user_id) FROM csod_training_records GROUP BY user_status;",
                "context": "SQL pair that provides a breakdown of active vs inactive learners for adoption analysis.",
                "document_reference": "Adoption Reports v2",
                "instructions": "Classify users with any training record as Active, else Inactive.",
                "categories": ["user_engagement", "adoption"],
                "samples": [
                {"input": "Breakdown of active vs inactive users"},
                {"input": "How many active learners exist?"}
                ],
                "additional_context": {
                "business_value": "Shows adoption levels of the LMS and highlights user engagement gaps.",
                "visualization_hint": "Pie chart showing % active vs inactive users.",
                "edge_cases": ["Users with deleted accounts should be excluded."]
                },
                "user_id": "system",
                "json_metadata": {
                "source_table": "csod_training_records",
                "dependencies": ["assigned_date", "completion_date"],
                "data_type": "categorical",
                "tags": ["engagement", "adoption"]
                }
            },
            {
                "domain_id": created_domain['domain_id'],
                "definition_type": "instruction",
                "name": "calculate_certification_compliance",
                "question": "How to calculate certification compliance rate?",
                "sql_query": "SELECT (COUNT(*) FILTER (WHERE is_compliant = TRUE)::decimal / COUNT(*)::decimal) * 100 FROM csod_training_records WHERE is_certification = TRUE;",
                "context": "Ensures compliance metrics are calculated only for certification-related trainings.",
                "document_reference": "Certification Compliance Rules v1.1",
                "instructions": "Always filter by is_certification = TRUE before calculating compliance metrics.",
                "categories": ["instruction", "certification", "compliance"],
                "samples": [
                {"input": "Compliance rate for certifications"},
                {"input": "What % are certified?"}
                ],
                "additional_context": {
                "business_value": "Critical for organizations in regulated industries where certifications are mandatory.",
                "visualization_hint": "Gauge or KPI card with thresholds (<80% alert, >95% target).",
                "edge_cases": ["Users with expired certifications should count as non-compliant."]
                },
                "user_id": "system",
                "json_metadata": {
                "source_table": "csod_training_records",
                "dependencies": ["is_certification", "is_compliant"],
                "data_type": "percentage",
                "tags": ["certification", "compliance"]
                }
            }
        ]


        created_examples = await learning_api.create_examples(examples_config)
        client.logger.info(f"Created {len(created_examples)} examples successfully")

        client.logger.info("API integration workflow completed successfully!")
        
        # Summary report
        client.logger.info("="*50)
        client.logger.info("EXECUTION SUMMARY")
        client.logger.info("="*50)
        client.logger.info(f"Datasource: {data_source.get('name', 'Unknown')} (ID: {data_source.get('connection_id', 'Unknown')})")
        client.logger.info(f"Domain: {created_domain.get('display_name', 'Unknown')} (ID: {created_domain.get('domain_id', 'Unknown')})")
        client.logger.info(f"Dataset: {created_dataset.get('name', 'Unknown')} (ID: {created_dataset.get('dataset_id', 'Unknown')})")
        client.logger.info(f"Tables processed: {len(created_tables)}")
        client.logger.info(f"Semantic models: {len(semantic_models)}")
        client.logger.info(f"Metrics created: {len(created_metrics)}")
        client.logger.info(f"Views created: {len(created_views)}")
        client.logger.info(f"Calculated Columns created: {len(created_columns)}")
        client.logger.info(f"Instructions created: {len(created_instructions)}")
        client.logger.info(f"Examples created: {len(created_examples)}")
        client.logger.info("="*50)

    except APIError as e:
        client.logger.error(f"API Error: {e.message}")
        if e.status_code:
            client.logger.error(f"Status Code: {e.status_code}")
        if e.endpoint:
            client.logger.error(f"Endpoint: {e.endpoint}")
        raise
    
    except ValueError as e:
        client.logger.error(f"Validation Error: {e}")
        raise
    
    except Exception as e:
        client.logger.error(f"Unexpected error in main execution: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Process interrupted by user")
    except Exception as e:
        print(f"Process failed with error: {e}")
        exit(1)