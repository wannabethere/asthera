"""
Example Workflow Configuration
This file demonstrates how to configure a complete data modeling workflow
"""

import json
from typing import Dict, Any

# ============================================================================
# EXAMPLE 1: Network Device Monitoring
# ============================================================================

network_device_workflow = {
    "workflow_name": "network_device_analytics",
    "description": "Network device inventory and monitoring analytics",
    
    # Raw DDL inputs
    "raw_schemas": [
        {
            "table_name": "dev_network_devices",
            "table_ddl": """
-- Network device inventory and management system
CREATE TABLE dev_network_devices (
  id BIGINT NOT NULL,
  ip VARCHAR,
  subnet VARCHAR,
  site VARCHAR,
  mac VARCHAR,
  manufacturer VARCHAR,
  updated_at TIMESTAMP,
  nuid INTEGER,
  dev_id INTEGER,
  is_stale BOOLEAN NOT NULL,
  raw_created_at TIMESTAMP,
  store_created_at TIMESTAMP,
  store_updated_at TIMESTAMP,
  process_id VARCHAR,
  is_cloud_device BOOLEAN,
  is_virtual_machine BOOLEAN,
  subnet_class VARCHAR,
  days_since_last_seen INTEGER,
  device_age_category VARCHAR,
  ip_octets VARCHAR
);""",
            "relationships": [],
            "layer": "raw"
        }
    ],
    
    # LOD configurations for deduplication
    "lod_configurations": [
        {
            "table_name": "dev_network_devices",
            "lod_type": "FIXED",
            "dimensions": ["ip", "mac"],
            "description": "Deduplicate devices by unique IP and MAC address combination"
        }
    ],
    
    # Relationship mappings for silver/gold layers
    "relationship_mappings": [],
    
    # User query describing analytical needs
    "user_query": """
    Create a comprehensive network device monitoring dashboard that provides:
    
    1. Device Inventory Metrics:
       - Total devices by site
       - Device distribution by manufacturer
       - Cloud vs. on-premise device breakdown
       - Virtual vs. physical machine counts
    
    2. Device Health Monitoring:
       - Active vs. stale device counts
       - Average days since last seen
       - Device age category distribution
       - Devices by subnet classification
    
    3. Time-Series Analysis:
       - Daily device activity trends
       - Week-over-week changes
       - Monthly rollups for reporting
    
    4. Network Analysis:
       - Subnet utilization
       - IP address allocation
       - Device density by site
    
    Focus on performance optimization with appropriate pre-aggregations.
    """,
    
    # Data mart goals for silver human-in-the-loop
    "data_mart_goals": [
        "Create a comprehensive network device monitoring dashboard",
        "Show device health metrics by site and manufacturer",
        "Analyze device activity trends over time"
    ],
    
    # Expected outputs
    "expected_outputs": {
        "raw_cubes": ["raw_network_devices"],
        "silver_cubes": ["silver_network_devices_cleaned", "silver_network_devices_deduped"],
        "gold_cubes": [
            "gold_device_metrics_daily",
            "gold_device_metrics_by_site",
            "gold_device_metrics_by_manufacturer"
        ],
        "views": ["network_analytics_view"],
        "transformations": [
            "raw_to_silver_cleaning",
            "raw_to_silver_deduplication",
            "silver_to_gold_daily_rollup",
            "silver_to_gold_site_aggregation"
        ]
    },
    
    # Optional: Generate gold layer (default: True)
    "generate_gold": True
}


# ============================================================================
# EXAMPLE 2: Multi-Table E-commerce Analytics
# ============================================================================

ecommerce_workflow = {
    "workflow_name": "ecommerce_analytics",
    "description": "E-commerce order and customer analytics",
    
    "raw_schemas": [
        {
            "table_name": "customers",
            "table_ddl": """
CREATE TABLE customers (
  customer_id BIGINT NOT NULL,
  email VARCHAR,
  first_name VARCHAR,
  last_name VARCHAR,
  created_at TIMESTAMP,
  country VARCHAR,
  state VARCHAR,
  city VARCHAR,
  total_orders INTEGER,
  total_spent DECIMAL(10,2)
);""",
            "relationships": [
                {
                    "name": "customer_orders",
                    "models": ["customers", "orders"],
                    "joinType": "ONE_TO_MANY",
                    "condition": "customers.customer_id = orders.customer_id"
                }
            ],
            "layer": "raw"
        },
        {
            "table_name": "orders",
            "table_ddl": """
CREATE TABLE orders (
  order_id BIGINT NOT NULL,
  customer_id BIGINT,
  order_date TIMESTAMP,
  order_status VARCHAR,
  total_amount DECIMAL(10,2),
  discount_amount DECIMAL(10,2),
  shipping_amount DECIMAL(10,2),
  tax_amount DECIMAL(10,2),
  payment_method VARCHAR
);""",
            "relationships": [
                {
                    "name": "order_items",
                    "models": ["orders", "order_items"],
                    "joinType": "ONE_TO_MANY",
                    "condition": "orders.order_id = order_items.order_id"
                }
            ],
            "layer": "raw"
        },
        {
            "table_name": "order_items",
            "table_ddl": """
CREATE TABLE order_items (
  item_id BIGINT NOT NULL,
  order_id BIGINT,
  product_id BIGINT,
  quantity INTEGER,
  unit_price DECIMAL(10,2),
  line_total DECIMAL(10,2),
  discount_percent DECIMAL(5,2)
);""",
            "relationships": [],
            "layer": "raw"
        }
    ],
    
    "lod_configurations": [
        {
            "table_name": "customers",
            "lod_type": "FIXED",
            "dimensions": ["email"],
            "description": "Deduplicate customers by email address"
        },
        {
            "table_name": "orders",
            "lod_type": "FIXED",
            "dimensions": ["order_id"],
            "description": "One record per order"
        }
    ],
    
    "relationship_mappings": [
        {
            "child_table": "orders",
            "parent_table": "customers",
            "join_type": "MANY_TO_ONE",
            "join_condition": "orders.customer_id = customers.customer_id",
            "layer": "silver"
        },
        {
            "child_table": "order_items",
            "parent_table": "orders",
            "join_type": "MANY_TO_ONE",
            "join_condition": "order_items.order_id = orders.order_id",
            "layer": "silver"
        }
    ],
    
    "user_query": """
    Create an e-commerce analytics platform with:
    
    1. Customer Analytics:
       - Customer lifetime value (CLV)
       - Customer segmentation
       - Customer acquisition trends
       - Repeat purchase rate
    
    2. Order Analytics:
       - Daily/weekly/monthly order volumes
       - Average order value (AOV)
       - Order status distribution
       - Payment method breakdown
    
    3. Product Performance:
       - Top-selling products
       - Revenue by product
       - Quantity sold trends
    
    4. Revenue Metrics:
       - Total revenue by period
       - Revenue by geography
       - Discount impact analysis
       - Shipping revenue
    
    Create optimized pre-aggregations for dashboard performance.
    """,
    
    # Data mart goals for silver human-in-the-loop
    "data_mart_goals": [
        "Create customer lifetime value analysis data mart",
        "Build daily order analytics summary",
        "Generate product performance metrics dashboard"
    ],
    
    "expected_outputs": {
        "raw_cubes": ["raw_customers", "raw_orders", "raw_order_items"],
        "silver_cubes": [
            "silver_customers",
            "silver_orders_with_customer",
            "silver_order_details"
        ],
        "gold_cubes": [
            "gold_customer_metrics",
            "gold_order_metrics_daily",
            "gold_product_performance",
            "gold_revenue_analysis"
        ],
        "views": [
            "ecommerce_overview",
            "customer_analytics",
            "order_analytics"
        ]
    },
    
    # Optional: Generate gold layer (default: True)
    "generate_gold": True
}


# ============================================================================
# EXAMPLE 3: Learning Management System (LMS)
# ============================================================================

lms_workflow = {
    "workflow_name": "lms_analytics",
    "description": "Learning management system analytics",
    
    "raw_schemas": [
        {
            "table_name": "users",
            "table_ddl": """
CREATE TABLE users (
  user_id BIGINT NOT NULL,
  username VARCHAR,
  email VARCHAR,
  user_type VARCHAR,  -- learner, instructor, admin
  created_at TIMESTAMP,
  last_login TIMESTAMP,
  is_active BOOLEAN
);""",
            "relationships": [],
            "layer": "raw"
        },
        {
            "table_name": "courses",
            "table_ddl": """
CREATE TABLE courses (
  course_id BIGINT NOT NULL,
  course_name VARCHAR,
  course_code VARCHAR,
  instructor_id BIGINT,
  category VARCHAR,
  duration_hours INTEGER,
  difficulty_level VARCHAR,
  created_at TIMESTAMP
);""",
            "relationships": [],
            "layer": "raw"
        },
        {
            "table_name": "enrollments",
            "table_ddl": """
CREATE TABLE enrollments (
  enrollment_id BIGINT NOT NULL,
  user_id BIGINT,
  course_id BIGINT,
  enrolled_at TIMESTAMP,
  completed_at TIMESTAMP,
  status VARCHAR,  -- enrolled, in_progress, completed, dropped
  progress_percent DECIMAL(5,2),
  final_grade DECIMAL(5,2)
);""",
            "relationships": [],
            "layer": "raw"
        }
    ],
    
    "lod_configurations": [
        {
            "table_name": "enrollments",
            "lod_type": "FIXED",
            "dimensions": ["user_id", "course_id"],
            "description": "One enrollment per user per course"
        }
    ],
    
    "relationship_mappings": [
        {
            "child_table": "enrollments",
            "parent_table": "users",
            "join_type": "MANY_TO_ONE",
            "join_condition": "enrollments.user_id = users.user_id",
            "layer": "silver"
        },
        {
            "child_table": "enrollments",
            "parent_table": "courses",
            "join_type": "MANY_TO_ONE",
            "join_condition": "enrollments.course_id = courses.course_id",
            "layer": "silver"
        }
    ],
    
    "user_query": """
    Create a learning analytics platform with:
    
    1. Learner Metrics:
       - Active learners count
       - Enrollment trends
       - Completion rates
       - Average progress across courses
       - Time to completion
    
    2. Course Performance:
       - Enrollment by course
       - Completion rates by course
       - Average grades
       - Course popularity trends
       - Dropout analysis
    
    3. Instructor Analytics:
       - Courses taught
       - Student success rates
       - Average student grades
    
    4. Time-Series Analysis:
       - Daily active users
       - Weekly enrollment trends
       - Monthly completion rates
       - Quarter-over-quarter growth
    
    Optimize for real-time dashboard updates.
    """,
    
    # Data mart goals for silver human-in-the-loop
    "data_mart_goals": [
        "Create learner engagement analytics dashboard",
        "Build course performance metrics data mart",
        "Generate instructor analytics summary"
    ],
    
    "expected_outputs": {
        "raw_cubes": ["raw_users", "raw_courses", "raw_enrollments"],
        "silver_cubes": [
            "silver_users",
            "silver_courses",
            "silver_enrollments_complete"
        ],
        "gold_cubes": [
            "gold_learner_metrics",
            "gold_course_performance",
            "gold_instructor_analytics",
            "gold_engagement_trends"
        ],
        "views": [
            "learning_analytics_overview",
            "course_insights",
            "learner_journey"
        ]
    },
    
    # Optional: Generate gold layer (default: True)
    "generate_gold": True
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def save_workflow_config(workflow: Dict[str, Any], filename: str):
    """Save workflow configuration to JSON file"""
    with open(filename, 'w') as f:
        json.dump(workflow, f, indent=2)
    print(f"Workflow saved to {filename}")


def load_workflow_config(filename: str) -> Dict[str, Any]:
    """Load workflow configuration from JSON file"""
    with open(filename, 'r') as f:
        workflow = json.load(f)
    print(f"Workflow loaded from {filename}")
    return workflow


def validate_workflow_config(workflow: Dict[str, Any]) -> bool:
    """Validate workflow configuration structure"""
    required_fields = [
        "workflow_name",
        "raw_schemas",
        "lod_configurations",
        "relationship_mappings",
        "user_query"
    ]
    
    for field in required_fields:
        if field not in workflow:
            print(f"Missing required field: {field}")
            return False
    
    # Validate raw schemas
    for schema in workflow["raw_schemas"]:
        if "table_name" not in schema or "table_ddl" not in schema:
            print(f"Invalid schema: {schema}")
            return False
    
    print("Workflow configuration is valid")
    return True


def print_workflow_summary(workflow: Dict[str, Any]):
    """Print a summary of the workflow configuration"""
    print(f"\n{'='*80}")
    print(f"Workflow: {workflow['workflow_name']}")
    print(f"{'='*80}")
    print(f"\nDescription: {workflow['description']}")
    
    print(f"\nRaw Tables ({len(workflow['raw_schemas'])}):")
    for schema in workflow['raw_schemas']:
        print(f"  - {schema['table_name']}")
    
    print(f"\nLOD Configurations ({len(workflow['lod_configurations'])}):")
    for lod in workflow['lod_configurations']:
        print(f"  - {lod['table_name']}: {', '.join(lod['dimensions'])}")
    
    print(f"\nRelationships ({len(workflow['relationship_mappings'])}):")
    for rel in workflow['relationship_mappings']:
        print(f"  - {rel['child_table']} → {rel['parent_table']} ({rel['join_type']})")
    
    if "expected_outputs" in workflow:
        outputs = workflow["expected_outputs"]
        print(f"\nExpected Outputs:")
        print(f"  Raw Cubes: {len(outputs.get('raw_cubes', []))}")
        print(f"  Silver Cubes: {len(outputs.get('silver_cubes', []))}")
        print(f"  Gold Cubes: {len(outputs.get('gold_cubes', []))}")
        print(f"  Views: {len(outputs.get('views', []))}")
    
    print(f"\n{'='*80}\n")


# ============================================================================
# MAIN - Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example 1: Network Device Workflow
    print("Network Device Workflow Configuration:")
    print_workflow_summary(network_device_workflow)
    validate_workflow_config(network_device_workflow)
    save_workflow_config(network_device_workflow, "network_device_workflow.json")
    
    # Example 2: E-commerce Workflow
    print("\nE-commerce Workflow Configuration:")
    print_workflow_summary(ecommerce_workflow)
    validate_workflow_config(ecommerce_workflow)
    save_workflow_config(ecommerce_workflow, "ecommerce_workflow.json")
    
    # Example 3: LMS Workflow
    print("\nLearning Management System Workflow Configuration:")
    print_workflow_summary(lms_workflow)
    validate_workflow_config(lms_workflow)
    save_workflow_config(lms_workflow, "lms_workflow.json")
    
    print("\n✅ All workflow configurations saved!")
