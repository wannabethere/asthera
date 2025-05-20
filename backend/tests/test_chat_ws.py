import asyncio
import websockets
import json
import uuid
from datetime import datetime
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def get_jwt_token():
    """Get JWT token from the authentication endpoint"""
    # Get credentials from environment variables
    email = os.getenv("TEST_USER_EMAIL", "test@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "testpassword123")
    
    # Authentication endpoint
    auth_url = "http://localhost:8000/api/v1/auth/login"
    
    # Login credentials matching LoginRequest model
    data = {
        "email": email,
        "password": password
    }
    
    # Headers for JSON data
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make login request with JSON data
        response = requests.post(auth_url, json=data, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Extract token from response
        token_data = response.json()
        if "access_token" not in token_data:
            raise Exception("No access token in response")
            
        print(f"Successfully obtained JWT token for user: {email}")
        return token_data["access_token"]
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get JWT token: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error getting JWT token: {str(e)}")
        raise

async def create_test_thread(token: str) -> str:
    """Create a test thread using the JWT token"""
    # Thread creation endpoint
    thread_url = "http://localhost:8000/api/v1/threads"
    
    # Thread creation data
    data = {
         "title": "Test Thread",
         "description": "Test Description",
         "project_id": "00000000-0000-0000-0000-000000000003"
    }
    
    # Headers with JWT token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # Create thread
        response = requests.post(thread_url, json=data, headers=headers)
        response.raise_for_status()
        
        # Extract thread ID from response
        thread_data = response.json()
        thread_id = thread_data["id"]
        print(f"Successfully created thread: {thread_id}")
        return thread_id
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to create thread: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error creating thread: {str(e)}")
        raise

async def ensure_project_access(token: str, project_id: str) -> None:
    """Ensure the user has access to the project"""
    # Project access endpoint
    access_url = f"http://localhost:8000/api/v1/projects/{project_id}/access"
    
    # Headers with JWT token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # Add user to project access
        response = requests.post(access_url, headers=headers)
        response.raise_for_status()
        print(f"Successfully ensured project access for project: {project_id}")
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to ensure project access: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error ensuring project access: {str(e)}")
        raise

async def test_chat_websocket():
    try:
        # Get JWT token
        token = await get_jwt_token()
        
        # Ensure project access first
        #project_id = "00000000-0000-0000-0000-000000000003"
        #await ensure_project_access(token, project_id)
        
        # Create a test thread
        thread_id = await create_test_thread(token)
        
        # WebSocket URL with token as query parameter
        uri = f"ws://localhost:8000/api/v1/chat/ws/{thread_id}?token={token}"
        
        print(f"Connecting to WebSocket at: {uri}")
        
        # Connect with token in headers
        async with websockets.connect(
            uri,
            additional_headers={"Authorization": f"Bearer {token}"}
        ) as websocket:
            print("Connected to WebSocket")
            
            # Receive initial history
            history = await websocket.recv()
            print(f"Received history: {history}")
            
            # Send a test message
            message = {
                "type": "message",
                "message_id": str(uuid.uuid4()),
                "content": "Hello, this is a test message!"
            }
            await websocket.send(json.dumps(message))
            print(f"Sent message: {message}")
            
            # Receive acknowledgment
            ack = await websocket.recv()
            print(f"Received ack: {ack}")
            
            # Receive response
            response = await websocket.recv()
            print(f"Received response: {response}")
            
            # Send ping
            await websocket.send(json.dumps({"type": "ping"}))
            pong = await websocket.recv()
            print(f"Received pong: {pong}")
            
    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {str(e)}")
        if hasattr(e, 'status_code'):
            print(f"Status code: {e.status_code}")
        if hasattr(e, 'reason'):
            print(f"Reason: {e.reason}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e.code} - {e.reason}")
        if e.code == 4003:
            print("Access denied: User does not have permission to access this thread")
        elif e.code == 4004:
            print("Thread not found: The specified thread ID does not exist")
        elif e.code == 4001:
            print("Authentication failed: Invalid or missing token")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat_websocket()) 