import asyncio
import logging
from typing import Dict, Any, Optional
from httpx import AsyncClient, ReadTimeout, RequestError
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'api_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "http://127.0.0.1:8023"
TIMEOUT = 1200.0
MAX_RETRIES = 3

async def make_request(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Make HTTP request with retry logic and comprehensive error handling
    """
    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    
    for attempt in range(MAX_RETRIES):
        try:
            async with AsyncClient(timeout=TIMEOUT) as client:
                logger.info(f"[REQUEST] {method} {url} (attempt {attempt + 1}/{MAX_RETRIES})")
                
                if data:
                    logger.debug(f"[PAYLOAD] Request payload: {json.dumps(data, indent=2)}")
                
                response = await client.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers
                )
                
                logger.info(f"[SUCCESS] Response: {response.status_code}")
                
                if response.status_code >= 400:
                    logger.error(f"[ERROR] HTTP {response.status_code}: {response.text}")
                    return None
                
                try:
                    result = response.json()
                    logger.debug(f"[RESPONSE] Response data: {json.dumps(result, indent=2)}")
                    return result
                except:
                    logger.info(f"[SUCCESS] Request successful (no JSON response)")
                    return {"status": "success", "status_code": response.status_code}
                
        except ReadTimeout:
            logger.warning(f"[TIMEOUT] Request timed out (attempt {attempt + 1})")
            if attempt == MAX_RETRIES - 1:
                logger.error(f"[ERROR] Request timed out after {MAX_RETRIES} attempts")
                return None
                
        except RequestError as e:
            logger.error(f"[ERROR] Request failed: {e} (attempt {attempt + 1})")
            if attempt == MAX_RETRIES - 1:
                logger.error(f"[ERROR] Request failed after {MAX_RETRIES} attempts")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error: {e}")
            return None
            
        # Wait before retry with exponential backoff
        if attempt < MAX_RETRIES - 1:
            wait_time = (2 ** attempt)
            logger.info(f"[RETRY] Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
    
    return None


# Domain Workflow API Functions
async def create_domain(domain_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new domain"""
    logger.info(f"[DOMAIN] Creating project: {domain_data.get('domain_id', 'Unknown')}")
    return await make_request("POST", "/projects/workflow/workflow/domain", data=domain_data)


async def create_dataset(dataset_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new dataset"""
    logger.info(f"[DATASET] Creating dataset: {dataset_data.get('name', 'Unknown')}")
    return await make_request("POST", "projects/workflow/workflow/dataset", data=dataset_data)


async def create_table(table_data: Dict[str, Any], domain_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new table"""
    table_name = table_data.get('table_name', 'Unknown')
    logger.info(f"[TABLE] Creating table: {table_name}")
    
    # Structure the request according to the API specification
    request_data = {
        "add_table_request": {
            "dataset_id": table_data.get("dataset_id"),
            "schema": {
                "table_name": table_data.get("table_name"),
                "table_description": table_data.get("table_description"),
                "columns": table_data.get("columns", []),
                "sample_data": table_data.get("sample_data", []),
                "constraints": table_data.get("constraints", [])
            }
        },
        "domain_context": domain_context
    }
    
    result = await make_request("POST", "projects/workflow/workflow/table", data=request_data)
    if result:
        logger.info(f"[TABLE] Successfully created table: {table_name}")
        return result
    else:
        logger.error(f"[TABLE] Failed to create table: {table_name}")
        return None


async def commit_domain_draft_ready(domain_id: str) -> bool:
    """Commit project and trigger post-commit actions"""
    logger.info(f"[COMMIT] Committing domain: {domain_id}")
    
    # Step 1: Commit
    commit_result = await make_request("POST", "projects/workflow/workflow/commit")
    if not commit_result:
        logger.error("[ERROR] Failed to commit domain")
        return False
    
    return True

async def commit_domain_active(domain_id:str) -> bool:
    # Step 2: Trigger post-commit
    trigger_result = await make_request("POST", f"projects/workflow/workflow/domain/{domain_id}/trigger-post-commit")
    if not trigger_result:
        logger.error("[ERROR] Failed to trigger post-commit")
        return False
    
    logger.info("[SUCCESS] Domain committed and triggered successfully")
    return True

# Examples API Functions
async def add_metric(metric_data: Dict[str, Any],params) -> Optional[Dict[str, Any]]:
    """Add a new metric"""
    logger.info("[METRIC] Adding metric")

    return await make_request("POST", "/projects/workflow/workflow/metric", data=metric_data,params=params)


async def add_calculated_column(column_data: Dict[str, Any],params) -> Optional[Dict[str, Any]]:
    """Add a calculated column"""
    logger.info("[COLUMN] Adding calculated column")
    return await make_request("POST", "/projects/workflow/workflow/calculated-column", data=column_data,params=params)


async def add_view(view_data: Dict[str, Any],params) -> Optional[Dict[str, Any]]:
    """Add a new view"""
    logger.info("[VIEW] Adding view")
    return await make_request("POST", "/projects/workflow/workflow/view", data=view_data,params=params)


async def create_sql_pair(sql_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create SQL pair"""
    logger.info("[SQL] Creating SQL pair")
    return await make_request("POST", "examples/examples/", data=sql_data)


async def create_instructions(instructions_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create instructions"""
    logger.info("[INSTRUCTIONS] Creating instructions")
    return await make_request("POST", "examples/examples/", data=instructions_data)

async def create_sqlFunction(sql_function_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create SQL Functions"""
    logger.info("[FUNCTION] Creating SQL Function")
    return await make_request("POST", "/sql-functions/sql-functions/", data=sql_function_data)

async def create_knowledgeBase(kb_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create KnowledgeBase"""
    logger.info("[KB] Creating KnowledgeBase")
    return await make_request("POST", "/knowledge-bases/knowledge-bases/", data=kb_data)

async def main():
    logger.info("[START] Starting API test execution")
    
    # Step 1: Create Project
    logger.info("[STEP 1] Creating project...")
    createDomain = await create_domain(
        {
            "domain_id": "IntegrationProjectAPI",
            "display_name": "Customer Insights Dashboard",
            "description": "A project focused on analyzing customer behavior to improve marketing strategies.",
            "created_by": "john.doe@example.com",
            "context": {
                "domain_id": "IntegrationProjectAPI",
                "domain_name": "Customer Insights Dashboard",
                "business_domain": "Marketing Analytics",
                "purpose": "To analyze and visualize customer engagement metrics to enhance decision-making.",
                "target_users": [
                    "Marketing Managers",
                    "Product Owners",
                    "Data Analysts"
                ],
                "key_business_concepts": [
                    "Customer Segmentation",
                    "Churn Prediction",
                    "Lifetime Value"
                ],
                "data_sources": [
                    "CRM System",
                    "Google Analytics",
                    "Salesforce"
                ],
                "compliance_requirements": [
                    "GDPR",
                    "CCPA"
                ]
            }
        }
    )
    
    if not createDomain:
        logger.error("[ERROR] Failed to create domain. Stopping execution.")
        return
    
    logger.info(f"[SUCCESS] Project created: {createDomain.get('domain_id', 'Unknown')}")
    
    # Step 2: Create Dataset
    logger.info("[STEP 2] Creating dataset...")
    createDataset = await create_dataset({
        "domain_id": createDomain['domain_id'],
        "name": "AutomationDataset",
        "description": "This dataset is created to test the application API's..."
    })
    
    if not createDataset:
        logger.error("[ERROR] Failed to create dataset. Stopping execution.")
        return
    
    logger.info(f"[SUCCESS] Dataset created: {createDataset.get('dataset_id', 'Unknown')}")

    # Prepare project context for table creation
    domain_context = {
        "domain_id": createDomain['domain_id'],
        "domain_name": createDomain['display_name'],
        "business_domain": "Retail and E-Commerce",
        "purpose": "To analyze customer purchasing behavior and optimize inventory and sales strategy.",
        "target_users": [
            "Marketing Analysts",
            "Sales Managers",
            "Product Team",
            "Business Intelligence Developers"
        ],
        "key_business_concepts": [
            "Customer Lifetime Value",
            "Sales Funnel Analysis",
            "Product Performance",
            "Churn Analysis",
            "Inventory Optimization"
        ],
        "data_sources": [
            "Web Application Logs",
            "CRM System",
            "Sales Database",
            "Inventory Management System"
        ],
        "compliance_requirements": [
            "GDPR",
            "PCI-DSS",
            "CCPA"
        ]
    }

    # Step 3: Create Tables (sequentially to avoid dependency issues)
    logger.info("[STEP 3] Creating tables...")
    
    tabledata = [
        {
            "dataset_id": createDataset["dataset_id"],
            "table_name": "Users",
            "table_description": "This table contains information about users of the application.",
            "columns": [
                {
                    "name": "user_id",
                    "description": "Unique identifier for each user.",
                    "data_type": "INTEGER",
                    "is_nullable": False,
                    "is_primary_key": True,
                    "is_foreign_key": False,
                    "usage_type": "identifier",
                    "metadata": {}
                },
                {
                    "name": "username",
                    "description": "Username selected by the user.",
                    "data_type": "VARCHAR",
                    "is_nullable": False,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "usage_type": "user_data",
                    "metadata": {}
                },
                {
                    "name": "email",
                    "description": "Email address of the user.",
                    "data_type": "VARCHAR",
                    "is_nullable": False,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "usage_type": "contact_info",
                    "metadata": {}
                },
                {
                    "name": "created_at",
                    "description": "Timestamp when the user account was created.",
                    "data_type": "TIMESTAMP",
                    "is_nullable": False,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "usage_type": "audit",
                    "metadata": {}
                }
            ],
            "sample_data": [
                {
                    "user_id": 1,
                    "username": "john_doe",
                    "email": "john.doe@example.com",
                    "created_at": "2024-01-15T10:30:00Z"
                },
                {
                    "user_id": 2,
                    "username": "jane_smith",
                    "email": "jane.smith@example.com",
                    "created_at": "2024-01-16T14:22:00Z"
                }
            ],
            "constraints": [
                {
                    "type": "PRIMARY_KEY",
                    "columns": ["user_id"]
                },
                {
                    "type": "UNIQUE",
                    "columns": ["username"]
                },
                {
                    "type": "UNIQUE",
                    "columns": ["email"]
                }
            ]
        },
        {
            "dataset_id": createDataset["dataset_id"],
            "table_name": "Products",
            "table_description": "This table contains details of products available in the application.",
            "columns": [
                {
                    "name": "product_id",
                    "description": "Unique identifier for each product.",
                    "data_type": "INTEGER",
                    "is_nullable": False,
                    "is_primary_key": True,
                    "is_foreign_key": False,
                    "usage_type": "identifier",
                    "metadata": {}
                },
                {
                    "name": "product_name",
                    "description": "Name of the product.",
                    "data_type": "VARCHAR",
                    "is_nullable": False,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "usage_type": "product_info",
                    "metadata": {}
                },
                {
                    "name": "price",
                    "description": "Price of the product.",
                    "data_type": "DECIMAL",
                    "is_nullable": False,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "usage_type": "pricing",
                    "metadata": {}
                },
                {
                    "name": "stock_quantity",
                    "description": "Available stock for the product.",
                    "data_type": "INTEGER",
                    "is_nullable": True,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "usage_type": "inventory",
                    "metadata": {}
                }
            ],
            "sample_data": [
                {
                    "product_id": 1,
                    "product_name": "Laptop",
                    "price": 999.99,
                    "stock_quantity": 50
                },
                {
                    "product_id": 2,
                    "product_name": "Mouse",
                    "price": 25.99,
                    "stock_quantity": 200
                }
            ],
            "constraints": [
                {
                    "type": "PRIMARY_KEY",
                    "columns": ["product_id"]
                },
                {
                    "type": "CHECK",
                    "columns": ["price"],
                    "condition": "price > 0"
                }
            ]
        }
        # {
        #     "dataset_id": createDataset["dataset_id"],
        #     "table_name": "Orders",
        #     "table_description": "This table records customer orders and product purchases.",
        #     "columns": [
        #         {
        #             "name": "order_id",
        #             "description": "Unique identifier for each order.",
        #             "data_type": "INTEGER",
        #             "is_nullable": False,
        #             "is_primary_key": True,
        #             "is_foreign_key": False,
        #             "usage_type": "identifier",
        #             "metadata": {}
        #         },
        #         {
        #             "name": "user_id",
        #             "description": "Foreign key to the Users table.",
        #             "data_type": "INTEGER",
        #             "is_nullable": False,
        #             "is_primary_key": False,
        #             "is_foreign_key": True,
        #             "usage_type": "relation",
        #             "metadata": {
        #                 "references": "Users.user_id"
        #             }
        #         },
        #         {
        #             "name": "product_id",
        #             "description": "Foreign key to the Products table.",
        #             "data_type": "INTEGER",
        #             "is_nullable": False,
        #             "is_primary_key": False,
        #             "is_foreign_key": True,
        #             "usage_type": "relation",
        #             "metadata": {
        #                 "references": "Products.product_id"
        #             }
        #         },
        #         {
        #             "name": "order_date",
        #             "description": "The date when the order was placed.",
        #             "data_type": "DATE",
        #             "is_nullable": False,
        #             "is_primary_key": False,
        #             "is_foreign_key": False,
        #             "usage_type": "audit",
        #             "metadata": {}
        #         },
        #         {
        #             "name": "quantity",
        #             "description": "Number of units ordered.",
        #             "data_type": "INTEGER",
        #             "is_nullable": False,
        #             "is_primary_key": False,
        #             "is_foreign_key": False,
        #             "usage_type": "transaction_data",
        #             "metadata": {}
        #         }
        #     ],
        #     "sample_data": [
        #         {
        #             "order_id": 1,
        #             "user_id": 1,
        #             "product_id": 1,
        #             "order_date": "2024-01-20",
        #             "quantity": 1
        #         },
        #         {
        #             "order_id": 2,
        #             "user_id": 2,
        #             "product_id": 2,
        #             "order_date": "2024-01-21",
        #             "quantity": 3
        #         }
        #     ],
        #     "constraints": [
        #         {
        #             "type": "PRIMARY_KEY",
        #             "columns": ["order_id"]
        #         },
        #         {
        #             "type": "FOREIGN_KEY",
        #             "columns": ["user_id"],
        #             "references": {
        #                 "table": "Users",
        #                 "columns": ["user_id"]
        #             }
        #         },
        #         {
        #             "type": "FOREIGN_KEY",
        #             "columns": ["product_id"],
        #             "references": {
        #                 "table": "Products",
        #                 "columns": ["product_id"]
        #             }
        #         },
        #         {
        #             "type": "CHECK",
        #             "columns": ["quantity"],
        #             "condition": "quantity > 0"
        #         }
        #     ]
        # }
    ]

    # Create tables sequentially instead of concurrently
    created_tables = []
    for i, table in enumerate(tabledata):
        logger.info(f"[TABLE {i+1}] Creating table: {table['table_name']}")
        result = await create_table(table, domain_context)
        if result:
            created_tables.append(result)
            logger.info(f"[SUCCESS] Table {table['table_name']} created successfully")
        else:
            logger.error(f"[ERROR] Failed to create table: {table['table_name']}")
            return
    
    logger.info(f"[SUCCESS] All {len(created_tables)} tables created successfully")

    commit_domain = await commit_domain_draft_ready(createDomain['domain_id'])
    if not commit_domain:
        logger.error("[ERROR] Failed to commit. Stopping execution.")
        return
    logger.info(f"[SUCCESS] Commited Successfully")


    createMetric = await add_metric(
        {
    
    "name": "Total Revenue",
    "display_name":"Total Revenue",
    "description":"This metric is used to calculate total revenue...",
    "metric_sql": "SELECT SUM(order_total) FROM orders",
    "metric_type": "Calculates total sales revenue from orders table",
    "aggregation_type": "revenue_report_2025.pdf"
  },{"table_id":created_tables[0]['table_id']}
    )
    if not createMetric:
        logger.error("[ERROR] Failed to create metric. Stopping execution.")
        return
    logger.info(f"[SUCCESS] created metric Successfully")


    createCalculatedColumn = await add_calculated_column(
        {
  "name": "days_since_last_login",
  "display_name": "Days Since Last Login",
  "description": "Calculates the number of days since the user last logged in.",
  "calculation_sql": "SELECT id, DATE_PART('day', CURRENT_DATE - last_login_at) AS days_since_last_login FROM users",
  "data_type": "integer",
  "usage_type": "calculated",
  "is_nullable": True,
  "is_primary_key": False,
  "is_foreign_key": False,
  "default_value": None,
  "ordinal_position": 0,
  "function_id": "calculate_days_since_last_login",
  "dependencies": ["last_login_at"],
  "json_metadata": {
    "refresh_frequency": "daily",
    "alerts": ["trigger if >30 for re-engagement"]
  }
}
,{"table_id":created_tables[0]['table_id']}
    )
    if not createCalculatedColumn:
        logger.error("[ERROR] Failed to create CalculatedColumn. Stopping execution.")
        return
    logger.info(f"[SUCCESS] created CalculatedColumn Successfully")


    createView = await add_view(
        {
    "name": "Active Users",
    "view_sql": "SELECT user_id, username, last_login FROM users WHERE last_login >= CURRENT_DATE - INTERVAL '30 days'",
    "description": "List of users active within the last 30 days",
    "view_type": "KPI"
  },{"table_id":created_tables[0]['table_id']}
    )
    if not createView:
        logger.error("[ERROR] Failed to create view. Stopping execution.")
        return
    logger.info(f"[SUCCESS] created view Successfully")

    commit_success = await commit_domain_active(createDomain['domain_id'])
    if not commit_success:
        logger.error("[ERROR] Failed to commit. Stopping execution.")
        return
    logger.info(f"[SUCCESS] Commited Successfully")

    createSQLPair = await create_sql_pair(
        {
    "domain_id": createDomain['domain_id'],
    "definition_type": "sql_pair",
    "name": "Order Details with Product Info",
    "question": "Retrieve orders joined with product details",
    "sql_query": "SELECT o.order_id, o.order_date, p.product_name, p.category FROM orders o JOIN products p ON o.product_id = p.product_id",
    "context": "Used to analyze order data along with product information",
    "document_reference": "null",
    "instructions": "Use for detailed sales reports.",
    "categories": ["reporting", "sales"],
    "samples": [{"order_id": 101, "order_date": "2025-07-01", "product_name": "Wireless Mouse", "category": "Electronics"}],
    "additional_context": {},
    "user_id": "reporting_team",
    "json_metadata": {"refresh_frequency": "daily"}
  }
    )
    if not createSQLPair:
        logger.error("[ERROR] Failed to create SQLPair. Stopping execution.")
        return
    logger.info(f"[SUCCESS] created SQLPair Successfully")

    createInstructions = await create_instructions(
        {
    "domain_id": createDomain['domain_id'],
    "definition_type": "instruction",
    "name": "Order Processing Guidelines",
    "question": "What are the steps for processing an order?",
    "sql_query": "",
    "context": "Instructions for the order fulfillment team",
    "document_reference": "order_process_manual.pdf",
    "instructions": "Follow these steps to ensure timely order delivery.",
    "categories": ["operations", "processes"],
    "samples": [],
    "additional_context": {"last_updated": "2025-07-01"},
    "user_id": "ops_manager",
    "json_metadata": {"priority": "high", "review_cycle": "yearly"}
  }
    )
    if not createInstructions:
        logger.error("[ERROR] Failed to create Instructions. Stopping execution.")
        return
    logger.info(f"[SUCCESS] created Instructions Successfully")


if __name__ == "__main__":
    asyncio.run(main())