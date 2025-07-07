#!/usr/bin/env python3
"""
Test script to verify that the metadata field name conflict is resolved
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.service.models import ExampleCreate, ExampleUpdate, ExampleRead
    from app.service.models import InstructionCreate, InstructionUpdate, InstructionRead
    from app.service.models import KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead
    from app.service.models import CalculatedColumnCreate
    
    print("✅ Successfully imported all models with json_metadata field")
    
    # Test creating instances
    example_create = ExampleCreate(
        project_id="test_project",
        definition_type="sql_pair",
        name="Test Example",
        question="Test question?",
        sql_query="SELECT * FROM test_table",
        json_metadata={"test": "data"}
    )
    print("✅ Successfully created ExampleCreate instance")
    
    instruction_create = InstructionCreate(
        project_id="test_project",
        question="Test question",
        instructions="Test instructions",
        sql_query="SELECT * FROM test_table",
        json_metadata={"test": "data"}
    )
    print("✅ Successfully created InstructionCreate instance")
    
    kb_create = KnowledgeBaseCreate(
        project_id="test_project",
        name="Test KB",
        content_type="text",
        content="Test content",
        json_metadata={"test": "data"}
    )
    print("✅ Successfully created KnowledgeBaseCreate instance")
    
    calc_col_create = CalculatedColumnCreate(
        name="test_column",
        calculation_sql="1 + 1",
        data_type="INTEGER",
        json_metadata={"test": "data"}
    )
    print("✅ Successfully created CalculatedColumnCreate instance")
    
    print("\n🎉 All tests passed! The metadata field name conflict has been resolved.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1) 