"""
Example usage of the enhanced SQLFunctionPersistenceService with optional project_id support.

This script demonstrates how to:
1. Create global SQL functions (no project_id)
2. Create project-specific SQL functions
3. Search and retrieve functions
4. Copy functions between projects
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.service.persistence_service import SQLFunctionPersistenceService
from app.utils.history import ProjectManager
from app.schemas.dbmodels import SQLFunction, Project
from typing import Dict, Any, List


def example_usage():
    """Example usage of the SQL function persistence service"""
    
    # Example database connection (replace with your actual connection string)
    # engine = create_engine('postgresql://user:password@localhost/project_db')
    # Session = sessionmaker(bind=engine)
    # session = Session()
    
    # Initialize services
    # project_manager = ProjectManager(session)
    # sql_function_service = SQLFunctionPersistenceService(session, project_manager)
    
    print("=== SQL Function Persistence Service Example ===\n")
    
    # Example 1: Create a global SQL function (no project_id)
    print("1. Creating a global SQL function...")
    global_function_data = {
        'name': 'calculate_age',
        'display_name': 'Calculate Age',
        'description': 'Calculate age from birth date',
        'function_sql': '''
        CREATE OR REPLACE FUNCTION calculate_age(birth_date DATE)
        RETURNS INTEGER AS $$
        BEGIN
            RETURN EXTRACT(YEAR FROM AGE(birth_date));
        END;
        $$ LANGUAGE plpgsql;
        ''',
        'return_type': 'INTEGER',
        'parameters': [
            {'name': 'birth_date', 'type': 'DATE', 'description': 'Birth date'}
        ],
        'metadata': {
            'category': 'date_utils',
            'tags': ['age', 'date', 'calculation']
        }
    }
    
    # function_id = sql_function_service.persist_sql_function(
    #     function_data=global_function_data,
    #     created_by='admin'
    # )
    # print(f"Created global function with ID: {function_id}")
    
    # Example 2: Create a project-specific SQL function
    print("\n2. Creating a project-specific SQL function...")
    project_function_data = {
        'name': 'calculate_revenue',
        'display_name': 'Calculate Revenue',
        'description': 'Calculate revenue for a specific project',
        'function_sql': '''
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
        ''',
        'return_type': 'DECIMAL',
        'parameters': [
            {'name': 'project_id', 'type': 'UUID', 'description': 'Project ID'},
            {'name': 'start_date', 'type': 'DATE', 'description': 'Start date'},
            {'name': 'end_date', 'type': 'DATE', 'description': 'End date'}
        ],
        'metadata': {
            'category': 'finance',
            'tags': ['revenue', 'project', 'calculation']
        }
    }
    
    # project_id = 'example_project_123'
    # function_id = sql_function_service.persist_sql_function(
    #     function_data=project_function_data,
    #     created_by='admin',
    #     project_id=project_id
    # )
    # print(f"Created project function with ID: {function_id}")
    
    # Example 3: Create multiple functions in batch
    print("\n3. Creating multiple functions in batch...")
    batch_functions_data = [
        {
            'name': 'format_currency',
            'display_name': 'Format Currency',
            'description': 'Format number as currency',
            'function_sql': '''
            CREATE OR REPLACE FUNCTION format_currency(amount DECIMAL, currency_code VARCHAR(3) DEFAULT 'USD')
            RETURNS VARCHAR AS $$
            BEGIN
                RETURN currency_code || ' ' || TO_CHAR(amount, 'FM999,999,999.00');
            END;
            $$ LANGUAGE plpgsql;
            ''',
            'return_type': 'VARCHAR',
            'parameters': [
                {'name': 'amount', 'type': 'DECIMAL', 'description': 'Amount to format'},
                {'name': 'currency_code', 'type': 'VARCHAR(3)', 'description': 'Currency code', 'default': 'USD'}
            ]
        },
        {
            'name': 'get_month_name',
            'display_name': 'Get Month Name',
            'description': 'Get month name from date',
            'function_sql': '''
            CREATE OR REPLACE FUNCTION get_month_name(input_date DATE)
            RETURNS VARCHAR AS $$
            BEGIN
                RETURN TO_CHAR(input_date, 'Month');
            END;
            $$ LANGUAGE plpgsql;
            ''',
            'return_type': 'VARCHAR',
            'parameters': [
                {'name': 'input_date', 'type': 'DATE', 'description': 'Input date'}
            ]
        }
    ]
    
    # function_ids = sql_function_service.persist_sql_functions_batch(
    #     functions_data=batch_functions_data,
    #     created_by='admin'
    # )
    # print(f"Created batch functions with IDs: {function_ids}")
    
    # Example 4: Retrieve functions
    print("\n4. Retrieving functions...")
    
    # Get all global functions
    # global_functions = sql_function_service.get_global_sql_functions()
    # print(f"Found {len(global_functions)} global functions")
    
    # Get project-specific functions
    # project_functions = sql_function_service.get_sql_functions(project_id)
    # print(f"Found {len(project_functions)} project functions")
    
    # Get all functions (global + project-specific)
    # all_functions = sql_function_service.get_sql_functions()
    # print(f"Found {len(all_functions)} total functions")
    
    # Example 5: Search functions
    print("\n5. Searching functions...")
    
    # Search by name or description
    # search_results = sql_function_service.search_sql_functions('calculate')
    # print(f"Found {len(search_results)} functions matching 'calculate'")
    
    # Search within a specific project
    # project_search_results = sql_function_service.search_sql_functions('revenue', project_id)
    # print(f"Found {len(project_search_results)} project functions matching 'revenue'")
    
    # Example 6: Get function summary
    print("\n6. Getting function summary...")
    
    # Global summary
    # global_summary = sql_function_service.get_sql_function_summary()
    # print(f"Global summary: {global_summary}")
    
    # Project summary
    # project_summary = sql_function_service.get_sql_function_summary(project_id)
    # print(f"Project summary: {project_summary}")
    
    # Example 7: Copy function to another project
    print("\n7. Copying function to another project...")
    
    # source_function_id = "some_function_id"
    # target_project_id = "target_project_456"
    # copied_function_id = sql_function_service.copy_sql_function_to_project(
    #     function_id=source_function_id,
    #     target_project_id=target_project_id,
    #     created_by='admin'
    # )
    # print(f"Copied function to new ID: {copied_function_id}")
    
    # Example 8: Update function
    print("\n8. Updating function...")
    
    # updates = {
    #     'description': 'Updated description for the function',
    #     'metadata': {
    #         'category': 'updated_category',
    #         'tags': ['updated', 'tags']
    #     }
    # }
    # updated_function = sql_function_service.update_sql_function(
    #     function_id="some_function_id",
    #     updates=updates,
    #     modified_by='admin'
    # )
    # print(f"Updated function: {updated_function.name}")
    
    print("\n=== Example completed ===")


def create_sample_functions():
    """Create sample functions for testing"""
    
    sample_functions = [
        {
            'name': 'safe_divide',
            'display_name': 'Safe Division',
            'description': 'Perform division with null check for zero denominator',
            'function_sql': '''
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
            ''',
            'return_type': 'DECIMAL',
            'parameters': [
                {'name': 'numerator', 'type': 'DECIMAL', 'description': 'Numerator'},
                {'name': 'denominator', 'type': 'DECIMAL', 'description': 'Denominator'}
            ],
            'metadata': {
                'category': 'math_utils',
                'tags': ['division', 'safe', 'null_check']
            }
        },
        {
            'name': 'is_weekend',
            'display_name': 'Is Weekend',
            'description': 'Check if a date falls on weekend',
            'function_sql': '''
            CREATE OR REPLACE FUNCTION is_weekend(check_date DATE)
            RETURNS BOOLEAN AS $$
            BEGIN
                RETURN EXTRACT(DOW FROM check_date) IN (0, 6);
            END;
            $$ LANGUAGE plpgsql;
            ''',
            'return_type': 'BOOLEAN',
            'parameters': [
                {'name': 'check_date', 'type': 'DATE', 'description': 'Date to check'}
            ],
            'metadata': {
                'category': 'date_utils',
                'tags': ['weekend', 'date', 'boolean']
            }
        }
    ]
    
    return sample_functions


if __name__ == "__main__":
    example_usage() 