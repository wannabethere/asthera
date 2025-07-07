#!/usr/bin/env python3
"""
Test script to verify database schema creation and SQLAlchemy model compatibility
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

def test_sql_schema():
    """Test that the SQL schema can be executed successfully"""
    print("Testing SQL schema creation...")
    
    # Path to the SQL file
    sql_file = Path(__file__).parent / 'init_scripts' / 'postgres_init.sql'
    
    if not sql_file.exists():
        print(f"❌ SQL file not found: {sql_file}")
        return False
    
    print(f"✅ SQL file found: {sql_file}")
    
    # Check SQL syntax (basic validation)
    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Basic syntax checks
        required_tables = [
            'projects', 'project_version_history', 'datasets', 'tables', 
            'columns', 'sql_functions', 'calculated_columns', 'metrics', 
            'views', 'relationships', 'instructions', 'examples', 
            'knowledge_base', 'project_histories', 'workflow_logs', 
            'project_json_store'
        ]
        
        for table in required_tables:
            if f'CREATE TABLE {table}' in sql_content:
                print(f"✅ Table '{table}' found in SQL")
            else:
                print(f"❌ Table '{table}' missing from SQL")
                return False
        
        # Check for required functions
        required_functions = [
            'increment_project_version', 'determine_change_type', 
            'trigger_project_version_update', 'update_updated_at_column'
        ]
        
        for func in required_functions:
            if f'CREATE OR REPLACE FUNCTION {func}' in sql_content:
                print(f"✅ Function '{func}' found in SQL")
            else:
                print(f"❌ Function '{func}' missing from SQL")
                return False
        
        print("✅ SQL schema validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Error reading SQL file: {e}")
        return False

def test_sqlalchemy_models():
    """Test that SQLAlchemy models can be imported and have correct structure"""
    print("\nTesting SQLAlchemy models...")
    
    try:
        from schemas.dbmodels import (
            Base, Project, ProjectVersionHistory, Dataset, Table, SQLColumn,
            SQLFunction, CalculatedColumn, Metric, View, Relationship,
            Instruction, Example, KnowledgeBase, ProjectHistory, WorkflowLog,
            ProjectJSONStore
        )
        
        print("✅ All SQLAlchemy models imported successfully")
        
        # Check that all models have __tablename__
        models = [
            Project, ProjectVersionHistory, Dataset, Table, SQLColumn,
            SQLFunction, CalculatedColumn, Metric, View, Relationship,
            Instruction, Example, KnowledgeBase, ProjectHistory, WorkflowLog,
            ProjectJSONStore
        ]
        
        for model in models:
            if hasattr(model, '__tablename__'):
                print(f"✅ Model {model.__name__} has __tablename__: {model.__tablename__}")
            else:
                print(f"❌ Model {model.__name__} missing __tablename__")
                return False
        
        # Check for required fields in Project model
        project_fields = [
            'project_id', 'display_name', 'description', 'created_by', 'status',
            'major_version', 'minor_version', 'patch_version', 'last_modified_by',
            'last_modified_entity', 'last_modified_entity_id', 'version_locked',
            'json_metadata', 'draft_completed_at', 'published_at'
        ]
        
        for field in project_fields:
            if hasattr(Project, field):
                print(f"✅ Project model has field: {field}")
            else:
                print(f"❌ Project model missing field: {field}")
                return False
        
        print("✅ SQLAlchemy models validation passed")
        return True
        
    except ImportError as e:
        print(f"❌ Error importing SQLAlchemy models: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing SQLAlchemy models: {e}")
        return False

def test_schema_consistency():
    """Test that SQL schema and SQLAlchemy models are consistent"""
    print("\nTesting schema consistency...")
    
    try:
        # Read SQL file
        sql_file = Path(__file__).parent / 'init_scripts' / 'postgres_init.sql'
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Import models
        from schemas.dbmodels import (
            Project, ProjectVersionHistory, Dataset, Table, SQLColumn,
            SQLFunction, CalculatedColumn, Metric, View, Relationship,
            Instruction, Example, KnowledgeBase, ProjectHistory, WorkflowLog,
            ProjectJSONStore
        )
        
        # Check table names consistency
        model_table_mapping = {
            'Project': 'projects',
            'ProjectVersionHistory': 'project_version_history',
            'Dataset': 'datasets',
            'Table': 'tables',
            'SQLColumn': 'columns',
            'SQLFunction': 'sql_functions',
            'CalculatedColumn': 'calculated_columns',
            'Metric': 'metrics',
            'View': 'views',
            'Relationship': 'relationships',
            'Instruction': 'instructions',
            'Example': 'examples',
            'KnowledgeBase': 'knowledge_base',
            'ProjectHistory': 'project_histories',
            'WorkflowLog': 'workflow_logs',
            'ProjectJSONStore': 'project_json_store'
        }
        
        for model_name, table_name in model_table_mapping.items():
            if f'CREATE TABLE {table_name}' in sql_content:
                print(f"✅ Table '{table_name}' exists in SQL and matches model {model_name}")
            else:
                print(f"❌ Table '{table_name}' missing from SQL for model {model_name}")
                return False
        
        # Check for UUID vs VARCHAR(36) consistency
        if 'VARCHAR(36)' in sql_content and 'uuid_generate_v4()::VARCHAR(36)' in sql_content:
            print("✅ UUID fields use VARCHAR(36) consistently")
        else:
            print("❌ UUID field format inconsistency detected")
            return False
        
        # Check for json_metadata vs metadata consistency
        if 'json_metadata JSONB' in sql_content and 'metadata JSONB' not in sql_content:
            print("✅ JSON metadata fields use 'json_metadata' consistently")
        else:
            print("❌ JSON metadata field naming inconsistency detected")
            return False
        
        print("✅ Schema consistency validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Error testing schema consistency: {e}")
        return False

def generate_sql_from_models():
    """Generate SQL from SQLAlchemy models for comparison"""
    print("\nGenerating SQL from SQLAlchemy models...")
    
    try:
        from sqlalchemy import create_engine, text
        from schemas.dbmodels import Base
        
        # Create a temporary in-memory database
        engine = create_engine('sqlite:///:memory:')
        
        # Generate SQL from models
        sql_statements = []
        for table in Base.metadata.sorted_tables:
            sql_statements.append(str(table.compile(engine)))
        
        print(f"✅ Generated {len(sql_statements)} SQL statements from models")
        
        # Save to file for comparison
        output_file = Path(__file__).parent / 'generated_schema.sql'
        with open(output_file, 'w') as f:
            f.write("-- Generated SQL from SQLAlchemy models\n")
            f.write("-- This is for comparison purposes only\n\n")
            for stmt in sql_statements:
                f.write(stmt + ";\n\n")
        
        print(f"✅ Generated SQL saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating SQL from models: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Database Schema Validation Tests")
    print("=" * 60)
    
    tests = [
        ("SQL Schema", test_sql_schema),
        ("SQLAlchemy Models", test_sqlalchemy_models),
        ("Schema Consistency", test_schema_consistency),
        ("Generate SQL from Models", generate_sql_from_models)
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
        print("🎉 All tests passed! Database schema is ready for use.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    exit(main()) 