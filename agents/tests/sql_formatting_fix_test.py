#!/usr/bin/env python3
"""
Test to verify SQL formatting fixes and PostgreSQL execution improvements.

This test demonstrates:
1. SQL generation without unnecessary newlines
2. Proper SQL cleaning and formatting
3. PostgreSQL execution without immutabledict errors
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm


class SQLFormattingFixTest:
    """Test SQL formatting fixes and PostgreSQL execution improvements"""
    
    @staticmethod
    def create_test_queries() -> List[Dict[str, Any]]:
        """Create test queries that might have formatting issues"""
        return [
            {
                "query": "Show me the total assignments by division with late submission percentage",
                "expected_clean_sql": "SELECT division, COUNT(*) AS total_assignments, COUNT(CASE WHEN completed_date > assigned_date THEN 1 END) AS late_submissions, (COUNT(CASE WHEN completed_date > assigned_date THEN 1 END) * 100.0 / COUNT(*)) AS late_submission_percentage FROM csod_training_records GROUP BY division ORDER BY late_submission_percentage DESC LIMIT 1;",
                "description": "Complex query with multiple aggregations and case statements"
            },
            {
                "query": "What is the average completion time for each training type?",
                "expected_clean_sql": "SELECT training_type, AVG(EXTRACT(EPOCH FROM (completed_date - assigned_date))) AS avg_completion_time FROM csod_training_records WHERE completed_date IS NOT NULL GROUP BY training_type;",
                "description": "Query with date calculations and aggregations"
            },
            {
                "query": "Show me the top 5 employees by number of completed trainings",
                "expected_clean_sql": "SELECT employee_id, COUNT(*) AS completed_trainings FROM csod_training_records WHERE completed_date IS NOT NULL GROUP BY employee_id ORDER BY completed_trainings DESC LIMIT 5;",
                "description": "Simple aggregation with ordering and limit"
            }
        ]


async def test_sql_generation_formatting():
    """Test SQL generation with proper formatting"""
    print("🔧 Testing SQL Generation Formatting")
    print("=" * 50)
    
    try:
        # Initialize components
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        
        # Create SQL RAG agent
        agent = SQLRAGAgent(
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        # Test queries
        test_queries = SQLFormattingFixTest.create_test_queries()
        
        print(f"📊 Testing {len(test_queries)} queries for formatting issues")
        
        for i, test_case in enumerate(test_queries):
            print(f"\n--- Test Case {i+1}: {test_case['description']} ---")
            print(f"Query: {test_case['query']}")
            
            try:
                # Generate SQL using the agent
                result = await agent.process_sql_request_enhanced(
                    operation="GENERATION",
                    query=test_case["query"],
                    project_id="test_project"
                )
                
                if result.get("success"):
                    generated_sql = result.get("sql", "")
                    print(f"Generated SQL: {generated_sql}")
                    
                    # Check for formatting issues
                    issues = []
                    
                    # Check for unnecessary newlines
                    if '\n' in generated_sql and not generated_sql.strip().count('\n') <= 1:
                        issues.append("Contains unnecessary newlines")
                    
                    # Check for multiple spaces
                    if '  ' in generated_sql:
                        issues.append("Contains multiple consecutive spaces")
                    
                    # Check for proper semicolon
                    if not generated_sql.strip().endswith(';'):
                        issues.append("Missing semicolon at end")
                    
                    if issues:
                        print(f"⚠️  Formatting issues found: {', '.join(issues)}")
                    else:
                        print("✅ SQL formatting looks good")
                    
                    # Test SQL cleaning function
                    cleaned_sql = agent._clean_sql_query(generated_sql)
                    print(f"Cleaned SQL: {cleaned_sql}")
                    
                    # Verify cleaning worked
                    if cleaned_sql != generated_sql:
                        print("✅ SQL cleaning made improvements")
                    else:
                        print("ℹ️  SQL was already clean")
                        
                else:
                    print(f"❌ SQL generation failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Error in test case {i+1}: {e}")
        
        print(f"\n✅ SQL generation formatting test completed")
        
    except Exception as e:
        print(f"❌ Error in SQL generation formatting test: {e}")
        import traceback
        traceback.print_exc()


async def test_sql_cleaning_function():
    """Test the SQL cleaning function directly"""
    print(f"\n🧹 Testing SQL Cleaning Function")
    print("=" * 40)
    
    try:
        # Initialize components
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        
        # Create SQL RAG agent
        agent = SQLRAGAgent(
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        # Test cases for SQL cleaning
        test_cases = [
            {
                "input": "SELECT\n    division,\n    COUNT(*) AS total_assignments\nFROM\n    csod_training_records\nGROUP BY\n    division;",
                "description": "SQL with unnecessary newlines"
            },
            {
                "input": "SELECT  division,   COUNT(*)  AS  total_assignments  FROM  csod_training_records  GROUP  BY  division;",
                "description": "SQL with multiple spaces"
            },
            {
                "input": "SELECT division, COUNT(*) AS total_assignments FROM csod_training_records GROUP BY division",
                "description": "SQL without semicolon"
            },
            {
                "input": "SELECT\n\n\n    division,\n\n    COUNT(*) AS total_assignments\n\n\nFROM\n\n\n    csod_training_records\n\n\nGROUP BY\n\n\n    division\n\n\n;",
                "description": "SQL with excessive whitespace and newlines"
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            print(f"\n--- Cleaning Test {i+1}: {test_case['description']} ---")
            print(f"Input: {repr(test_case['input'])}")
            
            cleaned = agent._clean_sql_query(test_case['input'])
            print(f"Cleaned: {repr(cleaned)}")
            
            # Verify cleaning results
            if '\n' in cleaned and cleaned.count('\n') > 1:
                print("⚠️  Still contains multiple newlines")
            elif '  ' in cleaned:
                print("⚠️  Still contains multiple spaces")
            elif not cleaned.endswith(';'):
                print("⚠️  Missing semicolon")
            else:
                print("✅ Cleaning successful")
        
        print(f"\n✅ SQL cleaning function test completed")
        
    except Exception as e:
        print(f"❌ Error in SQL cleaning function test: {e}")
        import traceback
        traceback.print_exc()


async def test_postgresql_execution():
    """Test PostgreSQL execution with cleaned SQL"""
    print(f"\n🐘 Testing PostgreSQL Execution")
    print("=" * 35)
    
    try:
        # Initialize engine
        engine = EngineProvider.get_engine()
        
        # Test SQL queries
        test_sqls = [
            "SELECT 1 as test_column;",
            "SELECT\n    'test' as column1,\n    'value' as column2;",
            "SELECT  COUNT(*)  AS  total  FROM  (SELECT 1)  AS  subquery;"
        ]
        
        print(f"📊 Testing {len(test_sqls)} SQL queries for PostgreSQL execution")
        
        for i, sql in enumerate(test_sqls):
            print(f"\n--- PostgreSQL Test {i+1} ---")
            print(f"SQL: {repr(sql)}")
            
            try:
                # Test dry run first
                success, result = await engine.execute_sql(
                    sql=sql,
                    session=None,
                    dry_run=True
                )
                
                if success:
                    print("✅ Dry run successful")
                    
                    # Test actual execution
                    success, result = await engine.execute_sql(
                        sql=sql,
                        session=None,
                        dry_run=False,
                        limit=10
                    )
                    
                    if success:
                        print("✅ Execution successful")
                        if result and "data" in result:
                            print(f"   Rows returned: {len(result['data'])}")
                    else:
                        print(f"❌ Execution failed: {result.get('error', 'Unknown error')}")
                else:
                    print(f"❌ Dry run failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Error in PostgreSQL test {i+1}: {e}")
        
        print(f"\n✅ PostgreSQL execution test completed")
        
    except Exception as e:
        print(f"❌ Error in PostgreSQL execution test: {e}")
        import traceback
        traceback.print_exc()


async def run_all_sql_fixes_tests():
    """Run all SQL formatting and execution tests"""
    print("🚀 Starting SQL Formatting and Execution Fix Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: SQL generation formatting
    results["sql_generation"] = await test_sql_generation_formatting()
    
    # Test 2: SQL cleaning function
    results["sql_cleaning"] = await test_sql_cleaning_function()
    
    # Test 3: PostgreSQL execution
    results["postgresql_execution"] = await test_postgresql_execution()
    
    print("\n" + "=" * 60)
    print("🎉 All SQL formatting and execution tests completed!")
    
    # Summary
    print(f"\nSummary:")
    print(f"✅ SQL generation formatting: {'PASSED' if results.get('sql_generation') else 'FAILED'}")
    print(f"✅ SQL cleaning function: {'PASSED' if results.get('sql_cleaning') else 'FAILED'}")
    print(f"✅ PostgreSQL execution: {'PASSED' if results.get('postgresql_execution') else 'FAILED'}")
    
    return results


if __name__ == "__main__":
    # Run all SQL formatting and execution tests
    asyncio.run(run_all_sql_fixes_tests())
