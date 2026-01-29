"""
Example: Using Context Breakdown API

Shows how to use the new streaming and non-streaming context breakdown endpoints.
"""
import requests
import json
import sseclient  # pip install sseclient-py


# API base URL
BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{BASE_URL}/api/context/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_breakdown_mdl():
    """Test MDL context breakdown (non-streaming)"""
    print("\n=== Testing MDL Breakdown (Non-Streaming) ===")
    
    payload = {
        "question": "What features does the Vulnerability table provide?",
        "domain": "mdl",
        "product_name": "Snyk"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/context/breakdown",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    print(f"Query Type: {result['query_type']}")
    print(f"Domains: {result['domains_involved']}")
    print(f"Product: {result['product_context']}")
    print(f"Total Search Questions: {len(result['search_questions'])}")
    print("\nSearch Questions:")
    for sq in result['search_questions']:
        print(f"  - {sq['entity']}: {sq['question']}")
        print(f"    Filters: {sq['metadata_filters']}")


def test_breakdown_compliance():
    """Test Compliance context breakdown (non-streaming)"""
    print("\n=== Testing Compliance Breakdown (Non-Streaming) ===")
    
    payload = {
        "question": "What evidence is needed for SOC2 access control?",
        "domain": "compliance",
        "frameworks": ["SOC2"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/context/breakdown",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    print(f"Query Type: {result['query_type']}")
    print(f"Domains: {result['domains_involved']}")
    print(f"Frameworks: {result['frameworks']}")
    print(f"Total Search Questions: {len(result['search_questions'])}")
    print("\nSearch Questions:")
    for sq in result['search_questions']:
        print(f"  - {sq['entity']}: {sq['question']}")


def test_breakdown_auto():
    """Test Auto-routing (planner decides MDL vs Compliance)"""
    print("\n=== Testing Auto-Routing (Planner) ===")
    
    payload = {
        "question": "How does Snyk vulnerability table support SOC2 controls?",
        "domain": "auto",  # Let planner decide
        "product_name": "Snyk",
        "frameworks": ["SOC2"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/context/breakdown",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    print(f"Query Type: {result['query_type']}")
    print(f"Domains: {result['domains_involved']}")
    print(f"Product: {result['product_context']}")
    print(f"Frameworks: {result['frameworks']}")
    print(f"Total Search Questions: {len(result['search_questions'])}")
    
    # Group by domain
    mdl_questions = [sq for sq in result['search_questions'] 
                     if 'table' in sq['entity'] or 'entities' in sq['entity']]
    compliance_questions = [sq for sq in result['search_questions'] 
                           if 'compliance' in sq['entity']]
    
    print(f"\nMDL Questions: {len(mdl_questions)}")
    for sq in mdl_questions:
        print(f"  - {sq['entity']}: {sq['question']}")
    
    print(f"\nCompliance Questions: {len(compliance_questions)}")
    for sq in compliance_questions:
        print(f"  - {sq['entity']}: {sq['question']}")


def test_breakdown_summary():
    """Test summary endpoint"""
    print("\n=== Testing Summary Endpoint ===")
    
    payload = {
        "question": "What features does Vulnerability table have?",
        "domain": "mdl",
        "product_name": "Snyk"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/context/breakdown/summary",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    print(f"Summary: {result['summary']}")
    print(f"Collections to Query: {result['collections_to_query']}")


def test_breakdown_streaming():
    """Test streaming endpoint"""
    print("\n=== Testing Streaming Endpoint ===")
    
    payload = {
        "question": "What vulnerability tables exist in Snyk?",
        "domain": "mdl",
        "product_name": "Snyk"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/context/breakdown/stream",
        json=payload,
        stream=True
    )
    
    print(f"Status: {response.status_code}")
    print("\nStreaming events:")
    
    client = sseclient.SSEClient(response)
    for event in client.events():
        print(f"\nEvent: {event.event}")
        data = json.loads(event.data)
        
        if event.event == "breakdown_started":
            print(f"  Started for: {data['question'][:50]}...")
        
        elif event.event == "analyzing":
            print(f"  Status: {data['status']}")
            print(f"  Progress: {data['progress']*100:.0f}%")
        
        elif event.event == "search_questions":
            print(f"  Generated {data['count']} search questions")
            for sq in data['search_questions'][:3]:  # Show first 3
                print(f"    - {sq['entity']}: {sq['question']}")
        
        elif event.event == "result":
            print(f"  Query Type: {data['query_type']}")
            print(f"  Domains: {data['domains_involved']}")
            print(f"  Collections: {data['collections_to_query']}")
        
        elif event.event == "complete":
            print(f"  Status: {data['status']}")
        
        elif event.event == "error":
            print(f"  Error: {data['error']}")


if __name__ == "__main__":
    # Test all endpoints
    test_health()
    test_breakdown_mdl()
    test_breakdown_compliance()
    test_breakdown_auto()
    test_breakdown_summary()
    test_breakdown_streaming()
    
    print("\n=== All Tests Complete ===")
