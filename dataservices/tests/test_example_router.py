"""
Test file for the example router with persistence services
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.service.models import ExampleCreate, UserExampleCreate, DefinitionType
from app.service.example_service import create_example, create_user_example
from app.service.database import get_db
from app.routers.example_router import router


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


def test_create_example():
    """Test creating a standard example"""
    example_data = {
        "project_id": "test_project",
        "question": "How to calculate monthly revenue?",
        "sql_query": "SELECT DATE_TRUNC('month', sale_date) as month, SUM(amount) as revenue FROM sales GROUP BY month",
        "context": "Monthly revenue calculation for sales analysis",
        "categories": ["metric", "revenue"],
        "metadata": {"business_unit": "sales"}
    }
    
    response = client.post("/examples/", json=example_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == example_data["question"]
    assert data["sql_query"] == example_data["sql_query"]
    assert data["project_id"] == example_data["project_id"]


def test_create_user_example():
    """Test creating a user example"""
    user_example_data = {
        "project_id": "test_project",
        "definition_type": "metric",
        "name": "monthly_revenue",
        "description": "Calculate monthly revenue from sales table",
        "sql": "SELECT DATE_TRUNC('month', sale_date) as month, SUM(amount) as revenue FROM sales GROUP BY month",
        "additional_context": {
            "business_unit": "sales",
            "frequency": "monthly"
        },
        "user_id": "test_user"
    }
    
    response = client.post("/user-examples/", json=user_example_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == user_example_data["name"]
    assert data["sql_query"] == user_example_data["sql"]


def test_get_example():
    """Test retrieving an example"""
    # First create an example
    example_data = {
        "project_id": "test_project",
        "question": "Test question",
        "sql_query": "SELECT * FROM test_table"
    }
    
    create_response = client.post("/examples/", json=example_data)
    assert create_response.status_code == 200
    example_id = create_response.json()["example_id"]
    
    # Then retrieve it
    response = client.get(f"/examples/{example_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["example_id"] == example_id
    assert data["question"] == example_data["question"]


def test_update_example():
    """Test updating an example"""
    # First create an example
    example_data = {
        "project_id": "test_project",
        "question": "Original question",
        "sql_query": "SELECT * FROM test_table"
    }
    
    create_response = client.post("/examples/", json=example_data)
    assert create_response.status_code == 200
    example_id = create_response.json()["example_id"]
    
    # Then update it
    update_data = {
        "question": "Updated question",
        "sql_query": "SELECT * FROM updated_table"
    }
    
    response = client.patch(f"/examples/{example_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == update_data["question"]
    assert data["sql_query"] == update_data["sql_query"]


def test_delete_example():
    """Test deleting an example"""
    # First create an example
    example_data = {
        "project_id": "test_project",
        "question": "Test question",
        "sql_query": "SELECT * FROM test_table"
    }
    
    create_response = client.post("/examples/", json=example_data)
    assert create_response.status_code == 200
    example_id = create_response.json()["example_id"]
    
    # Then delete it
    response = client.delete(f"/examples/{example_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Example deleted successfully"
    
    # Verify it's deleted
    get_response = client.get(f"/examples/{example_id}")
    assert get_response.status_code == 404


def test_list_examples():
    """Test listing examples"""
    # Create multiple examples
    example_data_1 = {
        "project_id": "test_project",
        "question": "Question 1",
        "sql_query": "SELECT * FROM table1"
    }
    
    example_data_2 = {
        "project_id": "test_project",
        "question": "Question 2",
        "sql_query": "SELECT * FROM table2"
    }
    
    client.post("/examples/", json=example_data_1)
    client.post("/examples/", json=example_data_2)
    
    # List all examples
    response = client.get("/examples/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
    # List examples by project
    response = client.get("/examples/?project_id=test_project")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__]) 