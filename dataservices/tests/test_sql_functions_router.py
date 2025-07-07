"""
Test script for the updated SQL Functions Router using the persistence service.

This script demonstrates how to:
1. Create global and project-specific SQL functions
2. List and search functions
3. Update and delete functions
4. Copy functions between projects
"""

import requests
import json
from typing import Dict, Any, List


class SQLFunctionsAPIClient:
    """Client for testing SQL Functions API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v1"
    
    def create_function(self, function_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new SQL function"""
        url = f"{self.api_base}/sql-functions/"
        response = requests.post(url, json=function_data)
        response.raise_for_status()
        return response.json()
    
    def create_batch_functions(self, functions_data: List[Dict[str, Any]], project_id: str = None) -> List[Dict[str, Any]]:
        """Create multiple SQL functions in batch"""
        url = f"{self.api_base}/sql-functions/batch"
        data = {
            "functions": functions_data,
            "project_id": project_id
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    def list_functions(self, project_id: str = None, name: str = None, return_type: str = None) -> Dict[str, Any]:
        """List SQL functions with optional filtering"""
        url = f"{self.api_base}/sql-functions/"
        params = {}
        if project_id:
            params["project_id"] = project_id
        if name:
            params["name"] = name
        if return_type:
            params["return_type"] = return_type
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def list_global_functions(self) -> Dict[str, Any]:
        """List global SQL functions"""
        url = f"{self.api_base}/sql-functions/global"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def search_functions(self, search_term: str, project_id: str = None, return_type: str = None, limit: int = 100) -> Dict[str, Any]:
        """Search SQL functions"""
        url = f"{self.api_base}/sql-functions/search"
        data = {
            "search_term": search_term,
            "project_id": project_id,
            "return_type": return_type,
            "limit": limit
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    def get_function(self, function_id: str) -> Dict[str, Any]:
        """Get a specific SQL function"""
        url = f"{self.api_base}/sql-functions/{function_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_summary(self, project_id: str = None) -> Dict[str, Any]:
        """Get SQL functions summary"""
        url = f"{self.api_base}/sql-functions/summary"
        params = {}
        if project_id:
            params["project_id"] = project_id
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def update_function(self, function_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a SQL function"""
        url = f"{self.api_base}/sql-functions/{function_id}"
        response = requests.patch(url, json=updates)
        response.raise_for_status()
        return response.json()
    
    def copy_function(self, function_id: str, target_project_id: str) -> Dict[str, Any]:
        """Copy a SQL function to another project"""
        url = f"{self.api_base}/sql-functions/{function_id}/copy"
        data = {
            "target_project_id": target_project_id
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    def delete_function(self, function_id: str) -> Dict[str, Any]:
        """Delete a SQL function"""
        url = f"{self.api_base}/sql-functions/{function_id}"
        response = requests.delete(url)
        response.raise_for_status()
        return response.json()


def test_sql_functions_api():
    """Test the SQL Functions API"""
    
    client = SQLFunctionsAPIClient()
    
    print("=== SQL Functions API Test ===\n")
    
    # Test 1: Create a global function
    print("1. Creating a global SQL function...")
    global_function = {
        "name": "safe_divide",
        "display_name": "Safe Division",
        "description": "Perform division with null check for zero denominator",
        "function_sql": """
        CREATE OR REPLACE FUNCTION safe_divide(numerator DECIMAL, denominator DECIMAL)
        RETURNS DECIMAL AS $$
        BEGIN
            IF denominator = 0 OR denominator IS NULL THEN
                RETURN NULL;
            ELSE
                RETURN numerator / denominator;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """,
        "return_type": "DECIMAL",
        "parameters": [
            {"name": "numerator", "type": "DECIMAL", "description": "Numerator"},
            {"name": "denominator", "type": "DECIMAL", "description": "Denominator"}
        ],
        "metadata": {
            "category": "math_utils",
            "tags": ["division", "safe", "null_check"]
        }
    }
    
    try:
        created_function = client.create_function(global_function)
        print(f"✅ Created global function: {created_function['function_id']}")
        global_function_id = created_function['function_id']
    except Exception as e:
        print(f"❌ Failed to create global function: {e}")
        return
    
    # Test 2: Create a project-specific function
    print("\n2. Creating a project-specific SQL function...")
    project_function = {
        "name": "calculate_revenue",
        "display_name": "Calculate Revenue",
        "description": "Calculate revenue for a specific project",
        "function_sql": """
        CREATE OR REPLACE FUNCTION calculate_revenue(project_id UUID, start_date DATE, end_date DATE)
        RETURNS DECIMAL AS $$
        DECLARE
            total_revenue DECIMAL;
        BEGIN
            SELECT COALESCE(SUM(amount), 0) INTO total_revenue
            FROM transactions
            WHERE project_id = $1
            AND transaction_date BETWEEN $2 AND $3;
            
            RETURN total_revenue;
        END;
        $$ LANGUAGE plpgsql;
        """,
        "return_type": "DECIMAL",
        "parameters": [
            {"name": "project_id", "type": "UUID", "description": "Project ID"},
            {"name": "start_date", "type": "DATE", "description": "Start date"},
            {"name": "end_date", "type": "DATE", "description": "End date"}
        ],
        "project_id": "test_project_123",
        "metadata": {
            "category": "finance",
            "tags": ["revenue", "project", "calculation"]
        }
    }
    
    try:
        created_project_function = client.create_function(project_function)
        print(f"✅ Created project function: {created_project_function['function_id']}")
        project_function_id = created_project_function['function_id']
    except Exception as e:
        print(f"❌ Failed to create project function: {e}")
        return
    
    # Test 3: Create multiple functions in batch
    print("\n3. Creating multiple functions in batch...")
    batch_functions = [
        {
            "name": "format_currency",
            "display_name": "Format Currency",
            "description": "Format number as currency",
            "function_sql": """
            CREATE OR REPLACE FUNCTION format_currency(amount DECIMAL, currency_code VARCHAR(3) DEFAULT 'USD')
            RETURNS VARCHAR AS $$
            BEGIN
                RETURN currency_code || ' ' || TO_CHAR(amount, 'FM999,999,999.00');
            END;
            $$ LANGUAGE plpgsql;
            """,
            "return_type": "VARCHAR",
            "parameters": [
                {"name": "amount", "type": "DECIMAL", "description": "Amount to format"},
                {"name": "currency_code", "type": "VARCHAR(3)", "description": "Currency code", "default": "USD"}
            ]
        },
        {
            "name": "get_month_name",
            "display_name": "Get Month Name",
            "description": "Get month name from date",
            "function_sql": """
            CREATE OR REPLACE FUNCTION get_month_name(input_date DATE)
            RETURNS VARCHAR AS $$
            BEGIN
                RETURN TO_CHAR(input_date, 'Month');
            END;
            $$ LANGUAGE plpgsql;
            """,
            "return_type": "VARCHAR",
            "parameters": [
                {"name": "input_date", "type": "DATE", "description": "Input date"}
            ]
        }
    ]
    
    try:
        batch_created = client.create_batch_functions(batch_functions)
        print(f"✅ Created {len(batch_created)} functions in batch")
        batch_function_ids = [f['function_id'] for f in batch_created]
    except Exception as e:
        print(f"❌ Failed to create batch functions: {e}")
        return
    
    # Test 4: List functions
    print("\n4. Listing functions...")
    
    try:
        # List all functions
        all_functions = client.list_functions()
        print(f"✅ Found {all_functions['total_count']} total functions")
        
        # List global functions
        global_functions = client.list_global_functions()
        print(f"✅ Found {global_functions['total_count']} global functions")
        
        # List project functions
        project_functions = client.list_functions(project_id="test_project_123")
        print(f"✅ Found {project_functions['total_count']} project functions")
        
    except Exception as e:
        print(f"❌ Failed to list functions: {e}")
    
    # Test 5: Search functions
    print("\n5. Searching functions...")
    
    try:
        # Search by term
        search_results = client.search_functions("calculate")
        print(f"✅ Found {search_results['total_count']} functions matching 'calculate'")
        
        # Search with filters
        filtered_search = client.search_functions("format", return_type="VARCHAR")
        print(f"✅ Found {filtered_search['total_count']} VARCHAR functions matching 'format'")
        
    except Exception as e:
        print(f"❌ Failed to search functions: {e}")
    
    # Test 6: Get function details
    print("\n6. Getting function details...")
    
    try:
        function_details = client.get_function(global_function_id)
        print(f"✅ Retrieved function: {function_details['name']}")
        print(f"   Description: {function_details['description']}")
        print(f"   Return type: {function_details['return_type']}")
        
    except Exception as e:
        print(f"❌ Failed to get function details: {e}")
    
    # Test 7: Get summary
    print("\n7. Getting summary...")
    
    try:
        global_summary = client.get_summary()
        print(f"✅ Global summary: {global_summary['total_functions']} functions")
        
        project_summary = client.get_summary(project_id="test_project_123")
        print(f"✅ Project summary: {project_summary['total_functions']} functions")
        
    except Exception as e:
        print(f"❌ Failed to get summary: {e}")
    
    # Test 8: Update function
    print("\n8. Updating function...")
    
    try:
        updates = {
            "description": "Updated description for the safe division function",
            "metadata": {
                "category": "updated_math_utils",
                "tags": ["updated", "division", "safe"]
            }
        }
        
        updated_function = client.update_function(global_function_id, updates)
        print(f"✅ Updated function: {updated_function['name']}")
        print(f"   New description: {updated_function['description']}")
        
    except Exception as e:
        print(f"❌ Failed to update function: {e}")
    
    # Test 9: Copy function
    print("\n9. Copying function...")
    
    try:
        copied_function = client.copy_function(global_function_id, "target_project_456")
        print(f"✅ Copied function to new ID: {copied_function['function_id']}")
        print(f"   Project ID: {copied_function['project_id']}")
        
    except Exception as e:
        print(f"❌ Failed to copy function: {e}")
    
    # Test 10: Delete function
    print("\n10. Deleting function...")
    
    try:
        # Delete one of the batch functions
        if batch_function_ids:
            delete_result = client.delete_function(batch_function_ids[0])
            print(f"✅ Deleted function: {delete_result['message']}")
        
    except Exception as e:
        print(f"❌ Failed to delete function: {e}")
    
    print("\n=== Test completed ===")


def create_sample_functions():
    """Create sample functions for testing"""
    
    sample_functions = [
        {
            "name": "is_weekend",
            "display_name": "Is Weekend",
            "description": "Check if a date falls on weekend",
            "function_sql": """
            CREATE OR REPLACE FUNCTION is_weekend(check_date DATE)
            RETURNS BOOLEAN AS $$
            BEGIN
                RETURN EXTRACT(DOW FROM check_date) IN (0, 6);
            END;
            $$ LANGUAGE plpgsql;
            """,
            "return_type": "BOOLEAN",
            "parameters": [
                {"name": "check_date", "type": "DATE", "description": "Date to check"}
            ],
            "metadata": {
                "category": "date_utils",
                "tags": ["weekend", "date", "boolean"]
            }
        },
        {
            "name": "calculate_age",
            "display_name": "Calculate Age",
            "description": "Calculate age from birth date",
            "function_sql": """
            CREATE OR REPLACE FUNCTION calculate_age(birth_date DATE)
            RETURNS INTEGER AS $$
            BEGIN
                RETURN EXTRACT(YEAR FROM AGE(birth_date));
            END;
            $$ LANGUAGE plpgsql;
            """,
            "return_type": "INTEGER",
            "parameters": [
                {"name": "birth_date", "type": "DATE", "description": "Birth date"}
            ],
            "metadata": {
                "category": "date_utils",
                "tags": ["age", "date", "calculation"]
            }
        }
    ]
    
    return sample_functions


if __name__ == "__main__":
    # Uncomment to run the test
    # test_sql_functions_api()
    
    print("SQL Functions API Test Script")
    print("To run the test, uncomment the test_sql_functions_api() call at the bottom of this file")
    print("Make sure your FastAPI server is running on http://localhost:8000") 