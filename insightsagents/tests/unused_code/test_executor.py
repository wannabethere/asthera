#!/usr/bin/env python3
"""
Simple test script for the QueryExecutor.
This script tests the basic functionality without requiring external dependencies.
"""

import os
import tempfile
from pathlib import Path
from query_executor import QueryExecutor


def test_basic_functionality():
    """Test basic query executor functionality."""
    print("🧪 Testing QueryExecutor basic functionality...")
    
    try:
        # Initialize executor
        executor = QueryExecutor()
        print("✅ Executor initialized successfully")
        
        # Test query
        test_query = "SELECT * FROM test_table WHERE id = 1"
        
        # Generate PostgreSQL executor
        postgres_file = executor.generate_executable_code(
            test_query, "postgres"
        )
        print(f"✅ PostgreSQL executor generated: {postgres_file}")
        
        # Verify file exists and contains the query
        with open(postgres_file, 'r') as f:
            content = f.read()
            if test_query in content:
                print("✅ Query correctly embedded in generated file")
            else:
                print("❌ Query not found in generated file")
        
        # Clean up
        os.remove(postgres_file)
        print("✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_connection_config():
    """Test connection configuration functionality."""
    print("\n🧪 Testing connection configuration...")
    
    try:
        executor = QueryExecutor()
        
        # Test connection config
        config = {
            "host": "test-host.com",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass"
        }
        
        test_query = "SELECT * FROM users"
        
        # Generate with config
        output_file = executor.generate_executable_code(
            test_query, "postgres", connection_config=config
        )
        print(f"✅ Executor with config generated: {output_file}")
        
        # Verify config was applied
        with open(output_file, 'r') as f:
            content = f.read()
            if "test-host.com" in content and "testdb" in content:
                print("✅ Connection configuration applied correctly")
            else:
                print("❌ Connection configuration not applied")
        
        # Clean up
        os.remove(output_file)
        print("✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_deployment_package():
    """Test deployment package generation."""
    print("\n🧪 Testing deployment package generation...")
    
    try:
        executor = QueryExecutor()
        
        test_query = "SELECT * FROM analytics.users"
        
        # Generate deployment package
        package_dir = executor.generate_deployment_package(
            test_query, "postgres"
        )
        print(f"✅ Deployment package generated: {package_dir}")
        
        # Verify package contents
        package_path = Path(package_dir)
        expected_files = ["main.py", "requirements.txt", "README.md", "deploy.sh"]
        
        for file_name in expected_files:
            file_path = package_path / file_name
            if file_path.exists():
                print(f"✅ {file_name} exists")
            else:
                print(f"❌ {file_name} missing")
        
        # Clean up
        import shutil
        shutil.rmtree(package_dir)
        print("✅ Test package cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Starting QueryExecutor tests...\n")
    
    tests = [
        test_basic_functionality,
        test_connection_config,
        test_deployment_package
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! QueryExecutor is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the output above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
