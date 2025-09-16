#!/usr/bin/env python3
"""
Test script for the new document router
"""

import asyncio
import json
from pathlib import Path
from app.routers.document_router import router
from app.schemas.document_schemas import DocumentType, TestMode
from fastapi.testclient import TestClient
from app.main import app

def test_document_router():
    """Test the document router endpoints"""
    
    # Create test client
    client = TestClient(app)
    
    print("Testing Document Router...")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Testing health check...")
    response = client.get("/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    print()
    
    # Test 2: Get document schemas
    print("2. Testing document schemas...")
    response = client.get("/documents/generic/schemas")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Schema: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"   Error: {response.text}")
    print()
    
    # Test 3: Get all documents (should be empty initially)
    print("3. Testing get all documents...")
    response = client.get("/documents/generic/all?limit=5")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Documents found: {len(response.json())}")
    else:
        print(f"   Error: {response.text}")
    print()
    
    # Test 4: Upload a test document
    print("4. Testing document upload...")
    
    # Create a test text file
    test_content = """
    This is a test document for the document router.
    
    It contains some sample text that should be processed by the document ingestion service.
    
    Key topics:
    - Document processing
    - Text analysis
    - Metadata extraction
    - Business intelligence
    
    This document should be processed and stored with insights extracted.
    """
    
    # Create test file
    test_file_path = "/tmp/test_document.txt"
    with open(test_file_path, "w") as f:
        f.write(test_content)
    
    try:
        # Upload the test document
        with open(test_file_path, "rb") as f:
            files = {"file": ("test_document.txt", f, "text/plain")}
            data = {
                "document_type": DocumentType.GENERIC.value,
                "test_mode": TestMode.ENABLED.value,  # Use test mode to avoid database writes
                "user_context": "Test upload",
                "questions": "What are the key topics?, What is the main purpose?",
                "domain_id": "test_domain",
                "created_by": "test_user"
            }
            
            response = client.post("/documents/", files=files, data=data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 201:
                result = response.json()
                print(f"   Document ID: {result.get('document_id')}")
                print(f"   Filename: {result.get('filename')}")
                print(f"   Document Type: {result.get('document_type')}")
                print(f"   Success: {result.get('success')}")
                print(f"   Test Mode: {result.get('test_mode')}")
                
                # Store document ID for further tests
                document_id = result.get('document_id')
            else:
                print(f"   Error: {response.text}")
                document_id = None
    except Exception as e:
        print(f"   Upload error: {str(e)}")
        document_id = None
    finally:
        # Clean up test file
        Path(test_file_path).unlink(missing_ok=True)
    
    print()
    
    # Test 5: Search documents
    print("5. Testing document search...")
    response = client.post("/documents/search", data={
        "query": "document processing",
        "document_type": DocumentType.GENERIC.value,
        "domain_id": "test_domain",
        "limit": 5,
        "use_tfidf": "true"
    })
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"   Query: {result.get('query')}")
        print(f"   Total Results: {result.get('total_results')}")
        print(f"   Search Type: {result.get('search_type')}")
    else:
        print(f"   Error: {response.text}")
    print()
    
    # Test 6: Get document insights (if we have a document ID)
    if document_id:
        print("6. Testing document insights...")
        response = client.get(f"/documents/insights/{document_id}?domain_id=test_domain")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   Document ID: {result.get('document_id')}")
            print(f"   Key Phrases: {len(result.get('key_phrases', []))}")
            print(f"   Chunk Content Length: {len(result.get('chunk_content', ''))}")
            print(f"   Extraction Date: {result.get('extraction_date')}")
        else:
            print(f"   Error: {response.text}")
    else:
        print("6. Skipping insights test (no document ID)")
    print()
    
    print("Document Router Test Complete!")
    print("=" * 50)

if __name__ == "__main__":
    test_document_router()
