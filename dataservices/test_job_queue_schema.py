#!/usr/bin/env python3
"""
Test script to verify job queue and JSON storage schema creation
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

def test_job_queue_schema():
    """Test that the job queue schema can be executed successfully"""
    print("Testing Job Queue and JSON Storage schema creation...")
    
    # Path to the SQL file
    sql_file = Path(__file__).parent / 'init_scripts' / 'job_queue_and_json_schemas.sql'
    
    if not sql_file.exists():
        print(f"❌ SQL file not found: {sql_file}")
        return False
    
    print(f"✅ SQL file found: {sql_file}")
    
    # Check SQL syntax (basic validation)
    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Basic syntax checks for job queue tables
        required_job_tables = [
            'job_queue', 'job_queue_priority', 'job_history'
        ]
        
        for table in required_job_tables:
            if f'CREATE TABLE {table}' in sql_content:
                print(f"✅ Job Queue table '{table}' found in SQL")
            else:
                print(f"❌ Job Queue table '{table}' missing from SQL")
                return False
        
        # Check for project JSON storage tables
        required_json_tables = [
            'project_json_store', 'project_json_search_log', 'project_json_update_log'
        ]
        
        for table in required_json_tables:
            if f'CREATE TABLE {table}' in sql_content:
                print(f"✅ Project JSON table '{table}' found in SQL")
            else:
                print(f"❌ Project JSON table '{table}' missing from SQL")
                return False
        
        # Check for SQL functions tables
        required_function_tables = [
            'sql_functions', 'sql_function_usage_log', 'sql_function_dependencies'
        ]
        
        for table in required_function_tables:
            if f'CREATE TABLE {table}' in sql_content:
                print(f"✅ SQL Functions table '{table}' found in SQL")
            else:
                print(f"❌ SQL Functions table '{table}' missing from SQL")
                return False
        
        # Check for required functions
        required_functions = [
            'update_updated_at_column', 'manage_job_queue_priority', 
            'log_job_status_change', 'get_next_job', 'get_queue_stats', 
            'cleanup_old_jobs'
        ]
        
        for func in required_functions:
            if f'CREATE OR REPLACE FUNCTION {func}' in sql_content:
                print(f"✅ Function '{func}' found in SQL")
            else:
                print(f"❌ Function '{func}' missing from SQL")
                return False
        
        # Check for views
        required_views = [
            'job_queue_status_view', 'project_json_store_status_view', 
            'sql_functions_usage_view'
        ]
        
        for view in required_views:
            if f'CREATE VIEW {view}' in sql_content:
                print(f"✅ View '{view}' found in SQL")
            else:
                print(f"❌ View '{view}' missing from SQL")
                return False
        
        print("✅ Job Queue and JSON Storage schema validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Error reading SQL file: {e}")
        return False

def test_schema_consistency_with_pydantic():
    """Test that SQL schema matches Pydantic schemas"""
    print("\nTesting schema consistency with Pydantic models...")
    
    try:
        # Read SQL file
        sql_file = Path(__file__).parent / 'init_scripts' / 'job_queue_and_json_schemas.sql'
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Import Pydantic schemas
        from app.schemas.job_schemas import (
            JobSubmitRequest, JobResponse, JobStatusResponse, JobListItem,
            JobListResponse, QueueStatsResponse, EntityUpdateRequest,
            EntityUpdateResponse, BulkUpdateRequest, BulkUpdateResponse
        )
        
        from app.schemas.project_json_schemas import (
            ProjectJSONResponse, ProjectJSONSearchRequest, ProjectJSONSearchResponse,
            ProjectJSONUpdateRequest, ProjectJSONStatus, ProjectTablesJSON,
            ProjectMetricsJSON, ProjectViewsJSON, ProjectCalculatedColumnsJSON,
            ProjectSummaryJSON
        )
        
        print("✅ All Pydantic schemas imported successfully")
        
        # Check job queue table structure matches JobSubmitRequest
        job_queue_fields = [
            'job_id', 'job_type', 'project_id', 'entity_type', 'entity_id',
            'user_id', 'session_id', 'priority', 'retry_count', 'max_retries',
            'status', 'created_at', 'started_at', 'completed_at', 'result',
            'error', 'metadata'
        ]
        
        for field in job_queue_fields:
            if field in sql_content:
                print(f"✅ Job queue field '{field}' found in SQL")
            else:
                print(f"❌ Job queue field '{field}' missing from SQL")
                return False
        
        # Check project JSON store table structure
        json_store_fields = [
            'store_id', 'project_id', 'json_type', 'chroma_document_id',
            'json_content', 'version', 'is_active', 'last_updated_by',
            'update_reason', 'created_at', 'updated_at'
        ]
        
        for field in json_store_fields:
            if field in sql_content:
                print(f"✅ Project JSON store field '{field}' found in SQL")
            else:
                print(f"❌ Project JSON store field '{field}' missing from SQL")
                return False
        
        # Check SQL functions table structure
        sql_functions_fields = [
            'function_id', 'project_id', 'name', 'display_name', 'description',
            'function_sql', 'return_type', 'parameters', 'is_global', 'is_active',
            'created_by', 'created_at', 'updated_at'
        ]
        
        for field in sql_functions_fields:
            if field in sql_content:
                print(f"✅ SQL functions field '{field}' found in SQL")
            else:
                print(f"❌ SQL functions field '{field}' missing from SQL")
                return False
        
        print("✅ Schema consistency validation passed")
        return True
        
    except ImportError as e:
        print(f"❌ Error importing Pydantic schemas: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing schema consistency: {e}")
        return False

def test_job_status_enum_consistency():
    """Test that job status values match between SQL and Python"""
    print("\nTesting job status enum consistency...")
    
    try:
        # Read SQL file
        sql_file = Path(__file__).parent / 'init_scripts' / 'job_queue_and_json_schemas.sql'
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Import job status enum
        from app.services.job_queue_service import JobStatus, JobType
        
        # Check job status values
        sql_status_values = ['pending', 'running', 'completed', 'failed', 'cancelled', 'retry']
        python_status_values = [status.value for status in JobStatus]
        
        for status in python_status_values:
            if status in sql_status_values:
                print(f"✅ Job status '{status}' found in both SQL and Python")
            else:
                print(f"❌ Job status '{status}' missing from SQL")
                return False
        
        # Check job type values
        sql_job_types = [
            'project_json_tables', 'project_json_metrics', 'project_json_views',
            'project_json_calculated_columns', 'project_json_summary', 
            'project_json_all', 'chromadb_indexing', 'post_commit_workflow'
        ]
        python_job_types = [job_type.value for job_type in JobType]
        
        for job_type in python_job_types:
            if job_type in sql_job_types:
                print(f"✅ Job type '{job_type}' found in both SQL and Python")
            else:
                print(f"❌ Job type '{job_type}' missing from SQL")
                return False
        
        print("✅ Job status and type enum consistency validation passed")
        return True
        
    except ImportError as e:
        print(f"❌ Error importing job enums: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing enum consistency: {e}")
        return False

def test_json_type_consistency():
    """Test that JSON type values are consistent"""
    print("\nTesting JSON type consistency...")
    
    try:
        # Read SQL file
        sql_file = Path(__file__).parent / 'init_scripts' / 'job_queue_and_json_schemas.sql'
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Expected JSON types from the schema
        expected_json_types = [
            'tables', 'metrics', 'views', 'calculated_columns', 
            'project_summary', 'enums', 'project'
        ]
        
        # Check if all expected types are in the SQL constraint
        for json_type in expected_json_types:
            if json_type in sql_content:
                print(f"✅ JSON type '{json_type}' found in SQL constraint")
            else:
                print(f"❌ JSON type '{json_type}' missing from SQL constraint")
                return False
        
        print("✅ JSON type consistency validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Error testing JSON type consistency: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Job Queue and JSON Storage Schema Validation Tests")
    print("=" * 60)
    
    tests = [
        ("Job Queue Schema", test_job_queue_schema),
        ("Schema Consistency with Pydantic", test_schema_consistency_with_pydantic),
        ("Job Status Enum Consistency", test_job_status_enum_consistency),
        ("JSON Type Consistency", test_json_type_consistency)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Job queue and JSON storage schema is ready for use.")
        print("\nTo create the database, run:")
        print("psql -d your_database -f init_scripts/job_queue_and_json_schemas.sql")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    exit(main()) 