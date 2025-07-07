"""
Test file for the instruction router with persistence services
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.service.models import InstructionCreate
from app.service.instruction_service import create_instruction
from app.service.database import get_db
from app.routers.instruction_router import router


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Create test client
client = TestClient(router)


def test_create_instruction():
    """Test creating an instruction"""
    instruction_data = {
        "project_id": "test_project",
        "question": "How to calculate customer lifetime value?",
        "instructions": "Use the customer_orders table and aggregate by customer_id to calculate total spend per customer",
        "sql_query": "SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id",
        "chain_of_thought": "CLV is calculated by summing all order amounts per customer over their lifetime",
        "json_metadata": {"business_unit": "sales", "priority": "high"}
    }
    
    response = client.post("/instructions/", json=instruction_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == instruction_data["question"]
    assert data["instructions"] == instruction_data["instructions"]
    assert data["sql_query"] == instruction_data["sql_query"]
    assert data["project_id"] == instruction_data["project_id"]


def test_get_instruction():
    """Test retrieving an instruction"""
    # First create an instruction
    instruction_data = {
        "project_id": "test_project",
        "question": "Test question",
        "instructions": "Test instructions",
        "sql_query": "SELECT * FROM test_table"
    }
    
    create_response = client.post("/instructions/", json=instruction_data)
    assert create_response.status_code == 200
    instruction_id = create_response.json()["instruction_id"]
    
    # Then retrieve it
    response = client.get(f"/instructions/{instruction_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["instruction_id"] == instruction_id
    assert data["question"] == instruction_data["question"]


def test_update_instruction():
    """Test updating an instruction"""
    # First create an instruction
    instruction_data = {
        "project_id": "test_project",
        "question": "Original question",
        "instructions": "Original instructions",
        "sql_query": "SELECT * FROM test_table"
    }
    
    create_response = client.post("/instructions/", json=instruction_data)
    assert create_response.status_code == 200
    instruction_id = create_response.json()["instruction_id"]
    
    # Then update it
    update_data = {
        "question": "Updated question",
        "instructions": "Updated instructions",
        "sql_query": "SELECT * FROM updated_table"
    }
    
    response = client.patch(f"/instructions/{instruction_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == update_data["question"]
    assert data["instructions"] == update_data["instructions"]
    assert data["sql_query"] == update_data["sql_query"]


def test_delete_instruction():
    """Test deleting an instruction"""
    # First create an instruction
    instruction_data = {
        "project_id": "test_project",
        "question": "Test question",
        "instructions": "Test instructions",
        "sql_query": "SELECT * FROM test_table"
    }
    
    create_response = client.post("/instructions/", json=instruction_data)
    assert create_response.status_code == 200
    instruction_id = create_response.json()["instruction_id"]
    
    # Then delete it
    response = client.delete(f"/instructions/{instruction_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Instruction deleted successfully"
    
    # Verify it's deleted
    get_response = client.get(f"/instructions/{instruction_id}")
    assert get_response.status_code == 404


def test_list_instructions():
    """Test listing instructions"""
    # Create multiple instructions
    instruction_data_1 = {
        "project_id": "test_project",
        "question": "Question 1",
        "instructions": "Instructions 1",
        "sql_query": "SELECT * FROM table1"
    }
    
    instruction_data_2 = {
        "project_id": "test_project",
        "question": "Question 2",
        "instructions": "Instructions 2",
        "sql_query": "SELECT * FROM table2"
    }
    
    client.post("/instructions/", json=instruction_data_1)
    client.post("/instructions/", json=instruction_data_2)
    
    # List all instructions
    response = client.get("/instructions/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
    # List instructions by project
    response = client.get("/instructions/?project_id=test_project")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_create_instructions_batch():
    """Test creating multiple instructions in batch"""
    instructions_batch = [
        {
            "question": "How to calculate revenue?",
            "instructions": "Sum all sales amounts",
            "sql_query": "SELECT SUM(amount) FROM sales",
            "chain_of_thought": "Revenue is total sales",
            "json_metadata": {"type": "calculation"}
        },
        {
            "question": "How to find top customers?",
            "instructions": "Group by customer and order by total spend",
            "sql_query": "SELECT customer_id, SUM(amount) FROM sales GROUP BY customer_id ORDER BY SUM(amount) DESC LIMIT 10",
            "chain_of_thought": "Top customers have highest total spend",
            "json_metadata": {"type": "analysis"}
        }
    ]
    
    response = client.post("/instructions/batch/?project_id=test_project", json=instructions_batch)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Successfully created 2 instructions"
    assert len(data["instruction_ids"]) == 2


def test_get_instruction_summary():
    """Test getting instruction summary"""
    # Create some instructions first
    instruction_data = {
        "project_id": "test_project",
        "question": "How to calculate revenue?",
        "instructions": "Sum all sales amounts",
        "sql_query": "SELECT SUM(amount) FROM sales",
        "chain_of_thought": "Revenue is total sales"
    }
    
    client.post("/instructions/", json=instruction_data)
    
    # Get summary
    response = client.get("/instructions/summary/test_project")
    assert response.status_code == 200
    data = response.json()
    assert "total_instructions" in data
    assert "recent_instructions" in data
    assert "instruction_types" in data
    assert data["total_instructions"] >= 1


def test_search_instructions():
    """Test searching instructions"""
    # Create an instruction with specific content
    instruction_data = {
        "project_id": "test_project",
        "question": "How to calculate monthly revenue?",
        "instructions": "Use DATE_TRUNC to group by month and sum amounts",
        "sql_query": "SELECT DATE_TRUNC('month', sale_date) as month, SUM(amount) FROM sales GROUP BY month"
    }
    
    client.post("/instructions/", json=instruction_data)
    
    # Search for "monthly"
    response = client.get("/instructions/search/?project_id=test_project&search_term=monthly")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    
    # Search for "revenue"
    response = client.get("/instructions/search/?project_id=test_project&search_term=revenue")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__]) 