#!/bin/bash

# Set the base URL for the API
API_URL="http://localhost:8000/api/v1"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        return 1
    fi
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to handle registration response
handle_registration_response() {
    local response=$1
    local error_msg=""
    
    # Check if response is valid JSON
    if ! echo "$response" | jq . >/dev/null 2>&1; then
        echo "Debug: Invalid JSON response from registration"
        return 1
    fi
    
    # Check for specific error messages
    if echo "$response" | jq -e '.detail' >/dev/null 2>&1; then
        error_msg=$(echo "$response" | jq -r '.detail')
        if [[ "$error_msg" == "Email already registered" ]]; then
            print_warning "User with this email already exists"
            return 1
        elif [[ "$error_msg" == "Username already taken" ]]; then
            print_warning "Username is already taken"
            return 1
        fi
    fi
    
    # Check if registration was successful
    if echo "$response" | jq -e '.id' >/dev/null 2>&1; then
        print_status 0 "User creation"
        return 0
    else
        echo -e "${RED}Failed to create user. Response:${NC}"
        echo "$response" | jq
        return 1
    fi
}

# Function to login user and get token
login_user() {
    local email=$1
    local password=$2
    echo "Debug: Attempting login for email: ${email}"
    
    local response=$(curl -s -X POST "${API_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d "{
            \"email\": \"${email}\",
            \"password\": \"${password}\"
        }")
    
    echo "Debug: Raw login response: ${response}"
    
    # Check if response is valid JSON
    if ! echo "$response" | jq . >/dev/null 2>&1; then
        echo "Debug: Invalid JSON response from login"
        echo "Debug: Response content: ${response}"
        return 1
    fi
    
    # Check for error response
    if echo "$response" | jq -e '.detail' >/dev/null 2>&1; then
        echo "Debug: Login error: $(echo "$response" | jq -r '.detail')"
        return 1
    fi
    
    # Check for access token
    if echo "$response" | jq -e '.access_token' >/dev/null 2>&1; then
        echo "Debug: Found access token in response"
        echo "$response"
        return 0
    else
        echo "Debug: No access token in response"
        echo "Debug: Response structure:"
        echo "$response" | jq .
        return 1
    fi
}

# Function to check for pending collaboration requests
check_collaboration_requests() {
    local thread_id=$1
    local auth_header=$2
    local response=$(curl -s -X GET "${API_URL}/threads/${thread_id}/collaborators" \
        -H "${auth_header}")
    
    if echo "$response" | jq -e '.[] | select(.status == "pending")' >/dev/null 2>&1; then
        echo $(echo "$response" | jq -r '.[] | select(.status == "pending") | .id')
        return 0
    else
        return 1
    fi
}

# Function to clean up test data
cleanup() {
    echo -e "\n${GREEN}Starting cleanup...${NC}"
    
    # Delete thread configurations
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread configurations..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD_ID}/configurations" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    if [ ! -z "$THREAD2_ID" ]; then
        echo "Deleting thread2 configurations..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD2_ID}/configurations" \
            -H "${AUTH_HEADER2}" > /dev/null || true
    fi
    
    # Delete thread collaborators
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread collaborators..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD_ID}/collaborators" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    if [ ! -z "$THREAD2_ID" ]; then
        echo "Deleting thread2 collaborators..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD2_ID}/collaborators" \
            -H "${AUTH_HEADER2}" > /dev/null || true
    fi
    
    # Delete threads
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    if [ ! -z "$THREAD2_ID" ]; then
        echo "Deleting thread2..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD2_ID}" \
            -H "${AUTH_HEADER2}" > /dev/null || true
    fi
    
    # Delete projects
    if [ ! -z "$PROJECT1_ID" ]; then
        echo "Deleting project1..."
        curl -s -X DELETE "${API_URL}/projects/${PROJECT1_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    if [ ! -z "$PROJECT2_ID" ]; then
        echo "Deleting project2..."
        curl -s -X DELETE "${API_URL}/projects/${PROJECT2_ID}" \
            -H "${AUTH_HEADER2}" > /dev/null || true
    fi
    
    # Delete workspaces
    if [ ! -z "$WORKSPACE1_ID" ]; then
        echo "Deleting workspace1..."
        curl -s -X DELETE "${API_URL}/workspaces/${WORKSPACE1_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    if [ ! -z "$WORKSPACE2_ID" ]; then
        echo "Deleting workspace2..."
        curl -s -X DELETE "${API_URL}/workspaces/${WORKSPACE2_ID}" \
            -H "${AUTH_HEADER2}" > /dev/null || true
    fi
    
    echo -e "${GREEN}Cleanup completed!${NC}"
}

# Set up trap to run cleanup on script exit
trap cleanup EXIT

# Attempt to login first user
echo "Attempting to login first user..."
LOGIN_RESPONSE=$(login_user "test@example.com" "testpassword123")

# Check if login was successful
if [ $? -eq 0 ]; then
    print_status 0 "First user login"
    echo "Debug: Processing successful login response"
    echo "Debug: Full login response: ${LOGIN_RESPONSE}"

    echo "Debug: Extracting and validating JSON response..."

    echo "Debug: Processing response with possible header information..."

    # First, check if this is a raw HTTP response with headers
    if echo "$LOGIN_RESPONSE" | grep -q "^HTTP/"; then
        echo "Debug: HTTP response with headers detected"
        
        # Extract Bearer token from Authorization header if present
        AUTH_HEADER=$(echo "$LOGIN_RESPONSE" | grep -i "^Authorization: Bearer" | head -1)
        if [ -n "$AUTH_HEADER" ]; then
            # Extract just the token part after "Bearer "
            JWT_TOKEN=$(echo "$AUTH_HEADER" | sed 's/^Authorization: Bearer //i' | tr -d '\r\n')
            JWT_TOKEN2=$JWT_TOKEN
            echo "Debug: Extracted JWT token from Authorization header"
        fi
        
        # Extract JSON part (everything after blank line in HTTP response)
        BODY=$(echo "$LOGIN_RESPONSE" | awk 'BEGIN{RS="\r\n\r\n|\n\n"} NR==2 {print}')
        EXTRACTED_JSON=$(echo "$BODY" | grep -o '{.*}' | head -1)
    else
        # Treat the whole response as JSON or JSON with trailing text
        EXTRACTED_JSON=$(echo "$LOGIN_RESPONSE" | grep -o '{.*}' | head -1)
    fi

    echo "Debug: Validating extracted JSON..."
    if [ -n "$EXTRACTED_JSON" ] && echo "$EXTRACTED_JSON" | jq . >/dev/null 2>&1; then
        echo "Debug: Valid JSON found in response"
        
        # If we didn't get a token from the header, try the JSON body
        if [ -z "$JWT_TOKEN" ] && echo "$EXTRACTED_JSON" | jq -e '.access_token' >/dev/null 2>&1; then
            # Extract token directly with cut to avoid any potential issues with jq output formatting
            JWT_TOKEN=$(echo "$EXTRACTED_JSON" | jq -r '.access_token' | head -1 | tr -d '\r\n')
            echo "Debug: Extracted JWT token from JSON body"
        fi
        
        # Extract user ID if available
        if echo "$EXTRACTED_JSON" | jq -e '.user.id' >/dev/null 2>&1; then
            USER_ID=$(echo "$EXTRACTED_JSON" | jq -r '.user.id' | head -1 | tr -d '\r\n')
            USERID2=$USER_ID
            echo "Debug: Extracted user ID: ${USER_ID}"
        fi
    else
        echo "Debug: No valid JSON found in response"
        # If no JSON, but we have a token from header, that's still okay
        if [ -z "$JWT_TOKEN" ]; then
            echo "Debug: No JWT token found in response"
            exit 1
        fi
    fi

    # Clean output for verification (no extra spaces, new lines, etc.)
    JWT_TOKEN=$(echo -n "$JWT_TOKEN" | tr -d '[:space:]')
    

    # Final output
    echo "Debug: JWT_TOKEN=${JWT_TOKEN}"
    
    echo "Debug: USER_ID=${USER_ID}"
    

    # Verify token length (should be a single token)
    echo "Debug: JWT_TOKEN length: $(echo -n "${JWT_TOKEN}" | wc -c) characters"
    # Verify the extracted values
    echo "Debug: Final extracted values:"
    echo "Debug: USER_ID: ${USER_ID}"
    echo "Debug: AUTH_HEADER: ${JWT_TOKEN}"
    echo "Debug: JWT_TOKEN (first 20 chars): ${JWT_TOKEN:0:20}..."
else
    echo "First user not found, creating new user..."
    USER_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser"
        }')
    
    if handle_registration_response "$USER_RESPONSE"; then
        USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
        # Login new user
        LOGIN_RESPONSE=$(login_user "test@example.com" "testpassword123")
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to login new user${NC}"
            exit 1
        fi
        JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    else
        echo -e "${RED}Failed to create first user${NC}"
        exit 1
    fi
fi

# Verify we have a valid user ID and token
if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
    echo -e "${RED}Failed to get first user ID${NC}"
    exit 1
fi

if [ -z "$JWT_TOKEN" ] || [ "$JWT_TOKEN" = "null" ]; then
    echo -e "${RED}Failed to get JWT token for first user${NC}"
    exit 1
fi

# Set authorization header for first user
AUTH_HEADER="Authorization: Bearer ${JWT_TOKEN}"
echo "Debug: Using auth header: ${AUTH_HEADER}"

# Attempt to login second user
echo "Attempting to login second user..."
LOGIN_RESPONSE2=$(login_user "test2@example.com" "testpassword123")

# Check if login was successful
if [ $? -eq 0 ]; then
    print_status 0 "Second user login"
    echo "Debug: Processing successful login response for second user"
    echo "Debug: Full login response: ${LOGIN_RESPONSE2}"
    
    echo "Debug: Trimming and validating JSON response..."
    
     # First, check if this is a raw HTTP response with headers
    if echo "$LOGIN_RESPONSE2" | grep -q "^HTTP/"; then
        echo "Debug: HTTP response with headers detected"
        
        # Extract Bearer token from Authorization header if present
        AUTH_HEADER2=$(echo "$LOGIN_RESPONSE2" | grep -i "^Authorization: Bearer" | head -1)
        if [ -n "$AUTH_HEADER2" ]; then
            # Extract just the token part after "Bearer "
            JWT_TOKEN2=$(echo "$AUTH_HEADER2" | sed 's/^Authorization: Bearer //i' | tr -d '\r\n')
            JWT_TOKEN2=$JWT_TOKEN2
            echo "Debug: Extracted JWT token from Authorization header"
        fi
        
        # Extract JSON part (everything after blank line in HTTP response)
        BODY=$(echo "$LOGIN_RESPONSE" | awk 'BEGIN{RS="\r\n\r\n|\n\n"} NR==2 {print}')
        EXTRACTED_JSON2=$(echo "$BODY" | grep -o '{.*}' | head -1)
    else
        # Treat the whole response as JSON or JSON with trailing text
        EXTRACTED_JSON2=$(echo "$LOGIN_RESPONSE2" | grep -o '{.*}' | head -1)
    fi

    echo "Debug: Validating extracted JSON..."
    if [ -n "$EXTRACTED_JSON2" ] && echo "$EXTRACTED_JSON2" | jq . >/dev/null 2>&1; then
        echo "Debug: Valid JSON found in response"
        
        # If we didn't get a token from the header, try the JSON body
        if [ -z "$JWT_TOKEN2" ] && echo "$EXTRACTED_JSON2" | jq -e '.access_token' >/dev/null 2>&1; then
            # Extract token directly with cut to avoid any potential issues with jq output formatting
            JWT_TOKEN2=$(echo "$EXTRACTED_JSON2" | jq -r '.access_token' | head -1 | tr -d '\r\n')
            echo "Debug: Extracted JWT token from JSON body"
        fi
        
        # Extract user ID if available
        if echo "$EXTRACTED_JSON2" | jq -e '.user.id' >/dev/null 2>&1; then
            USER2_ID=$(echo "$EXTRACTED_JSON2" | jq -r '.user.id' | head -1 | tr -d '\r\n')
            USERID2=$USER2_ID
            echo "Debug: Extracted user ID: ${USER2_ID}"
        fi
    else
        echo "Debug: No valid JSON found in response"
        # If no JSON, but we have a token from header, that's still okay
        if [ -z "$JWT_TOKEN2" ]; then
            echo "Debug: No JWT token found in response"
            exit 1
        fi
    fi

    # Clean output for verification (no extra spaces, new lines, etc.)
    JWT_TOKEN2=$(echo -n "$JWT_TOKEN2" | tr -d '[:space:]')
    

    # Final output
    echo "Debug: JWT_TOKEN2=${JWT_TOKEN2}"
    
    echo "Debug: USER2_ID=${USER2_ID}"
    

    # Verify token length (should be a single token)
    echo "Debug: JWT_TOKEN length: $(echo -n "${JWT_TOKEN}" | wc -c) characters"
    # Verify the extracted values
    echo "Debug: Final extracted values:"
    echo "Debug: USER_ID: ${USER_ID}"
    echo "Debug: AUTH_HEADER: ${JWT_TOKEN}"
    echo "Debug: JWT_TOKEN (first 20 chars): ${JWT_TOKEN:0:20}..."

else
    echo "Second user not found, creating new user..."
    USER2_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test2@example.com",
            "password": "testpassword123",
            "first_name": "Test2",
            "last_name": "User2",
            "username": "testuser2"
        }')
    
    if handle_registration_response "$USER2_RESPONSE"; then
        USER2_ID=$(echo $USER2_RESPONSE | jq -r '.id')
        # Login new user
        LOGIN_RESPONSE2=$(login_user "test2@example.com" "testpassword123")
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to login new second user${NC}"
            exit 1
        fi
        JWT_TOKEN2=$(echo "$LOGIN_RESPONSE2" | jq -r '.access_token')
    else
        echo -e "${RED}Failed to create second user${NC}"
        exit 1
    fi
fi

# Verify we have a valid second user ID and token
if [ -z "$USER2_ID" ] || [ "$USER2_ID" = "null" ]; then
    echo -e "${RED}Failed to get second user ID${NC}"
    exit 1
fi

if [ -z "$JWT_TOKEN2" ] || [ "$JWT_TOKEN2" = "null" ]; then
    echo -e "${RED}Failed to get JWT token for second user${NC}"
    exit 1
fi

# Set authorization header for second user
AUTH_HEADER2="Authorization: Bearer ${JWT_TOKEN2}"

# Verify user IDs are set
if [ -z "$USER_ID" ] || [ -z "$USER2_ID" ]; then
    echo -e "${RED}Error: User IDs are not properly set${NC}"
    echo "USER_ID: $USER_ID"
    echo "USER2_ID: $USER2_ID"
    exit 1
fi
echo "USER_ID: $USER_ID found"
echo "USER2_ID: $USER2_ID found"
# Function to validate JSON response
validate_json_response() {
    local response=$1
    local operation=$2
    
    if ! echo "$response" | jq . >/dev/null 2>&1; then
        echo -e "${RED}Invalid JSON response for ${operation}:${NC}"
        echo "$response"
        return 1
    fi
    return 0
}

# Function to make API request with validation
make_api_request() {
    local method=$1
    local endpoint=$2
    local auth_header=$3
    local data=$4
    local operation=$5
    
    # Clean up the auth header to remove any potential duplicates
    local clean_auth_header=$(echo "$auth_header" | sed 's/Bearer [^ ]* Bearer/Bearer/')
    
    local curl_cmd="curl -s -L -X ${method} \"${API_URL}${endpoint}\""
    
    if [ ! -z "$clean_auth_header" ]; then
        curl_cmd="${curl_cmd} -H \"${clean_auth_header}\""
        echo "Debug: Using auth header: ${clean_auth_header}"
    else
        echo "Debug: No auth header provided"
    fi
    
    if [ ! -z "$data" ]; then
        curl_cmd="${curl_cmd} -H \"Content-Type: application/json\" -d '${data}'"
    fi
    
    echo "Debug: Executing command: ${curl_cmd}"
    local response=$(eval "${curl_cmd}")
    echo "Debug: Raw response: ${response}"
    
    if ! validate_json_response "$response" "$operation"; then
        echo "Debug: Invalid JSON response"
        return 1
    fi
    
    echo "$response"
    return 0
}

# Create a thread
echo "Creating a thread..."
echo "Debug: Using auth header: ${AUTH_HEADER}"
THREAD_RESPONSE=$(make_api_request "POST" "/threads" "${AUTH_HEADER}" '{
    "title": "Test Thread",
    "description": "Test Description",
    "project_id": "00000000-0000-0000-0000-000000000003"
}' "Thread creation")

echo "Debug: Extracting thread ID with simplified approach..."

# Method 1: Use grep with Perl regex to extract just the first UUID after id field
# This only extracts the content between quotes in the "id":"uuid" pattern
THREAD_ID=$(echo "$THREAD_RESPONSE" | grep -m 1 -oP '"id":"\K[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

# Method 2 (alternative): If method 1 fails, try awk for precise field extraction
if [ -z "$THREAD_ID" ]; then
    THREAD_ID=$(echo "$THREAD_RESPONSE" | awk -F'"id":"' '{print $2}' | awk -F'"' '{print $1}' | head -1)
fi

# Method 3 (fallback): If all else fails, use sed with a minimal pattern
if [ -z "$THREAD_ID" ]; then
    THREAD_ID=$(echo "$THREAD_RESPONSE" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -1)
fi

echo "Debug: Extracted thread ID: ${THREAD_ID}"
echo "Debug: THREAD_ID length: $(echo -n "${THREAD_ID}" | wc -c) characters"

# Verify it matches UUID pattern (optional validation)
if [[ $THREAD_ID =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    echo "Debug: Valid UUID format confirmed"
else
    echo "Debug: WARNING - Extracted ID does not match UUID format"
fi



# Add second user as collaborator
echo "Adding second user as collaborator..."
echo "Debug: Using thread ID: ${THREAD_ID}"
echo "Debug: Using user ID: ${USER2_ID}"

# Validate thread ID again before using it
if [[ ! "$THREAD_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    echo -e "${RED}Invalid thread ID format before collaborator addition: ${THREAD_ID}${NC}"
    exit 1
fi

COLLAB_RESPONSE=$(make_api_request "POST" "/threads/${THREAD_ID}/collaborators" "${AUTH_HEADER}" '{
    "user_id": "'${USER2_ID}'",
    "role": "collaborator",
    "message": "Please join this thread as a collaborator"
}' "Add collaborator")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to add collaborator${NC}"
    echo "Debug: Collaborator response: ${COLLAB_RESPONSE}"
    exit 1
fi

echo "Debug: Collaborator response: ${COLLAB_RESPONSE}"

# Extract collaborator ID using jq
COLLABORATOR_ID=$(echo "$COLLAB_RESPONSE" | jq -r '.id')
if [ -n "$COLLABORATOR_ID" ] && [ "$COLLABORATOR_ID" != "null" ]; then
    print_status 0 "Add collaborator"
    echo "Debug: Collaborator ID: ${COLLABORATOR_ID}"
else
    echo -e "${RED}Failed to extract collaborator ID from response${NC}"
    echo "Debug: Full response:"
    echo "$COLLAB_RESPONSE" | jq
    
fi

# Check for pending collaboration requests for second user
echo "Checking for pending collaboration requests..."
PENDING_REQUEST_ID=$(check_collaboration_requests "$THREAD_ID" "$AUTH_HEADER2")

if [ $? -eq 0 ]; then
    print_warning "Found pending collaboration request, accepting it..."
    # Second user accepts the collaboration request
    ACCEPT_RESPONSE=$(make_api_request "PUT" "/threads/collaborators/${PENDING_REQUEST_ID}" "${AUTH_HEADER2}" '{
        "status": "accepted",
        "role": "collaborator",
        "message": "I accept the invitation to collaborate"
    }' "Accept collaboration request")

    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to accept collaboration request${NC}"
        exit 1
    fi

    print_status 0 "Accept collaboration request"
fi

# Add a chat message from second user
echo "Adding chat message from second user..."
CHAT_RESPONSE2=$(make_api_request "POST" "/chat/message" "${AUTH_HEADER2}" '{
    "thread_id": "'${THREAD_ID}'",
    "content": "Hello from the second user!",
    "message_type": "text"
}' "Add chat message from second user")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to add chat message from second user${NC}"
    exit 1
fi

print_status 0 "Add chat message from second user"

# Get chat history
echo "Getting chat history..."
CHAT_HISTORY=$(make_api_request "GET" "/chat/history/${THREAD_ID}" "${AUTH_HEADER}" "" "Get chat history")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to get chat history${NC}"
    exit 1
fi

print_status 0 "Get chat history"

# Get thread collaborators
echo "Getting thread collaborators..."
COLLABORATORS=$(make_api_request "GET" "/threads/${THREAD_ID}/collaborators" "${AUTH_HEADER}" "" "Get thread collaborators")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to get thread collaborators${NC}"
    exit 1
fi

print_status 0 "Get thread collaborators"

# Create thread configuration
echo "Creating thread configuration..."
CONFIG_RESPONSE=$(make_api_request "POST" "/threads/${THREAD_ID}/configurations" "${AUTH_HEADER}" '{
    "name": "Test Configuration",
    "config": {
        "allow_public_access": false,
        "max_collaborators": 10,
        "allowed_roles": ["owner", "collaborator", "viewer"],
        "default_role": "collaborator"
    },
    "is_default": true
}' "Create thread configuration")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create thread configuration${NC}"
    exit 1
fi

print_status 0 "Create thread configuration"

# Get thread configurations
echo "Getting thread configurations..."
CONFIGS=$(make_api_request "GET" "/threads/${THREAD_ID}/configurations" "${AUTH_HEADER}" "" "Get thread configurations")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to get thread configurations${NC}"
    exit 1
fi

print_status 0 "Get thread configurations"

# Get default configuration
echo "Getting default configuration..."
DEFAULT_CONFIG=$(make_api_request "GET" "/threads/${THREAD_ID}/configurations/default" "${AUTH_HEADER}" "" "Get default configuration")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to get default configuration${NC}"
    exit 1
fi

print_status 0 "Get default configuration"

# Get thread details
echo "Getting thread details..."
THREAD_DETAILS=$(make_api_request "GET" "/threads/${THREAD_ID}" "${AUTH_HEADER}" "" "Get thread details")

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to get thread details${NC}"
    exit 1
fi

print_status 0 "Get thread details"

echo -e "${GREEN}All tests completed successfully!${NC}" 