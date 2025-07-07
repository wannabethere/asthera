"""
Test file for the knowledge base router with persistence services
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.service.models import KnowledgeBaseCreate
from app.service.knowledge_base_service import create_knowledge_base
from app.service.database import get_db
from app.routers.knowledge_base_router import router


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


def test_create_knowledge_base():
    """Test creating a knowledge base entry"""
    kb_data = {
        "project_id": "test_project",
        "name": "business_rules",
        "display_name": "Business Rules",
        "description": "Project-specific business rules and constraints",
        "content": """
        Business Rules:
        1. All sales must be above $10
        2. Customer discounts cannot exceed 25%
        3. Orders must have valid customer_id
        4. Product prices must be positive
        """,
        "content_type": "text",
        "metadata": {"category": "rules", "priority": "high"}
    }
    
    response = client.post("/knowledge-bases/", json=kb_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == kb_data["name"]
    assert data["display_name"] == kb_data["display_name"]
    assert data["content"] == kb_data["content"]
    assert data["project_id"] == kb_data["project_id"]


def test_get_knowledge_base():
    """Test retrieving a knowledge base entry"""
    # First create a knowledge base entry
    kb_data = {
        "project_id": "test_project",
        "name": "test_kb",
        "display_name": "Test Knowledge Base",
        "content": "Test content",
        "content_type": "text"
    }
    
    create_response = client.post("/knowledge-bases/", json=kb_data)
    assert create_response.status_code == 200
    kb_id = create_response.json()["kb_id"]
    
    # Then retrieve it
    response = client.get(f"/knowledge-bases/{kb_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["kb_id"] == kb_id
    assert data["name"] == kb_data["name"]


def test_update_knowledge_base():
    """Test updating a knowledge base entry"""
    # First create a knowledge base entry
    kb_data = {
        "project_id": "test_project",
        "name": "original_kb",
        "display_name": "Original Knowledge Base",
        "content": "Original content",
        "content_type": "text"
    }
    
    create_response = client.post("/knowledge-bases/", json=kb_data)
    assert create_response.status_code == 200
    kb_id = create_response.json()["kb_id"]
    
    # Then update it
    update_data = {
        "name": "updated_kb",
        "display_name": "Updated Knowledge Base",
        "content": "Updated content",
        "content_type": "markdown"
    }
    
    response = client.patch(f"/knowledge-bases/{kb_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["display_name"] == update_data["display_name"]
    assert data["content"] == update_data["content"]
    assert data["content_type"] == update_data["content_type"]


def test_delete_knowledge_base():
    """Test deleting a knowledge base entry"""
    # First create a knowledge base entry
    kb_data = {
        "project_id": "test_project",
        "name": "test_kb",
        "display_name": "Test Knowledge Base",
        "content": "Test content",
        "content_type": "text"
    }
    
    create_response = client.post("/knowledge-bases/", json=kb_data)
    assert create_response.status_code == 200
    kb_id = create_response.json()["kb_id"]
    
    # Then delete it
    response = client.delete(f"/knowledge-bases/{kb_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Knowledge base entry deleted successfully"
    
    # Verify it's deleted
    get_response = client.get(f"/knowledge-bases/{kb_id}")
    assert get_response.status_code == 404


def test_list_knowledge_bases():
    """Test listing knowledge base entries"""
    # Create multiple knowledge base entries
    kb_data_1 = {
        "project_id": "test_project",
        "name": "kb_1",
        "display_name": "Knowledge Base 1",
        "content": "Content 1",
        "content_type": "text"
    }
    
    kb_data_2 = {
        "project_id": "test_project",
        "name": "kb_2",
        "display_name": "Knowledge Base 2",
        "content": "Content 2",
        "content_type": "markdown"
    }
    
    client.post("/knowledge-bases/", json=kb_data_1)
    client.post("/knowledge-bases/", json=kb_data_2)
    
    # List all knowledge base entries
    response = client.get("/knowledge-bases/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
    # List knowledge base entries by project
    response = client.get("/knowledge-bases/?project_id=test_project")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
    # List knowledge base entries by content type
    response = client.get("/knowledge-bases/?project_id=test_project&content_type=text")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_create_knowledge_bases_batch():
    """Test creating multiple knowledge base entries in batch"""
    kb_entries_batch = [
        {
            "name": "business_rules",
            "display_name": "Business Rules",
            "description": "Project business rules",
            "content": "All sales must be above $100",
            "content_type": "text",
            "metadata": {"category": "rules"}
        },
        {
            "name": "api_documentation",
            "display_name": "API Documentation",
            "description": "API endpoints documentation",
            "content": "# API Documentation\n\n## Endpoints\n- GET /users\n- POST /users",
            "content_type": "markdown",
            "metadata": {"category": "docs"}
        }
    ]
    
    response = client.post("/knowledge-bases/batch/?project_id=test_project", json=kb_entries_batch)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Successfully created 2 knowledge base entries"
    assert len(data["kb_ids"]) == 2


def test_get_knowledge_base_summary():
    """Test getting knowledge base summary"""
    # Create some knowledge base entries first
    kb_data = {
        "project_id": "test_project",
        "name": "test_kb",
        "display_name": "Test Knowledge Base",
        "content": "Test content",
        "content_type": "text"
    }
    
    client.post("/knowledge-bases/", json=kb_data)
    
    # Get summary
    response = client.get("/knowledge-bases/summary/test_project")
    assert response.status_code == 200
    data = response.json()
    assert "total_entries" in data
    assert "content_types" in data
    assert "recent_entries" in data
    assert data["total_entries"] >= 1


def test_search_knowledge_bases():
    """Test searching knowledge base entries"""
    # Create a knowledge base entry with specific content
    kb_data = {
        "project_id": "test_project",
        "name": "sales_rules",
        "display_name": "Sales Rules",
        "content": "Sales must be above $100 and customer discounts cannot exceed 25%",
        "content_type": "text"
    }
    
    client.post("/knowledge-bases/", json=kb_data)
    
    # Search for "sales"
    response = client.get("/knowledge-bases/search/?project_id=test_project&search_term=sales")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    
    # Search for "discount"
    response = client.get("/knowledge-bases/search/?project_id=test_project&search_term=discount")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_knowledge_base_by_content_type():
    """Test getting knowledge base entries by content type"""
    # Create knowledge base entries with different content types
    kb_data_1 = {
        "project_id": "test_project",
        "name": "text_kb",
        "content": "Text content",
        "content_type": "text"
    }
    
    kb_data_2 = {
        "project_id": "test_project",
        "name": "markdown_kb",
        "content": "# Markdown content",
        "content_type": "markdown"
    }
    
    client.post("/knowledge-bases/", json=kb_data_1)
    client.post("/knowledge-bases/", json=kb_data_2)
    
    # Get text content type entries
    response = client.get("/knowledge-bases/content-type/text?project_id=test_project")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(entry["content_type"] == "text" for entry in data)
    
    # Get markdown content type entries
    response = client.get("/knowledge-bases/content-type/markdown?project_id=test_project")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(entry["content_type"] == "markdown" for entry in data)


def test_get_content_types():
    """Test getting available content types for a project"""
    # Create knowledge base entries with different content types
    kb_data_1 = {
        "project_id": "test_project",
        "name": "text_kb",
        "content": "Text content",
        "content_type": "text"
    }
    
    kb_data_2 = {
        "project_id": "test_project",
        "name": "markdown_kb",
        "content": "# Markdown content",
        "content_type": "markdown"
    }
    
    client.post("/knowledge-bases/", json=kb_data_1)
    client.post("/knowledge-bases/", json=kb_data_2)
    
    # Get content types
    response = client.get("/knowledge-bases/project/test_project/content-types")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == "test_project"
    assert "text" in data["content_types"]
    assert "markdown" in data["content_types"]
    assert data["total_entries"] >= 2


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__]) 