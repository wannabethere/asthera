#!/bin/bash

# Set the base URL for the API
API_URL="http://localhost:8000/api/v1"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        exit 1
    fi
}

# Function to clean up test data
cleanup() {
    echo -e "\n${GREEN}Starting cleanup...${NC}"
    
    # Delete project
    if [ ! -z "$PROJECT_ID" ]; then
        echo "Deleting project..."
        curl -s -X DELETE "${API_URL}/projects/${PROJECT_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    # Delete workspace
    if [ ! -z "$WORKSPACE_ID" ]; then
        echo "Deleting workspace..."
        curl -s -X DELETE "${API_URL}/workspaces/${WORKSPACE_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    # Delete team
    if [ ! -z "$TEAM_ID" ]; then
        echo "Deleting team..."
        curl -s -X DELETE "${API_URL}/teams/${TEAM_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    # Delete second test user
    if [ ! -z "$USER2_ID" ]; then
        echo "Deleting second test user..."
        curl -s -X DELETE "${API_URL}/users/${USER2_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    # Delete first test user
    if [ ! -z "$USER_ID" ]; then
        echo "Deleting first test user..."
        curl -s -X DELETE "${API_URL}/users/${USER_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    echo -e "${GREEN}Cleanup completed!${NC}"
}

# Set up trap to run cleanup on script exit
trap cleanup EXIT

# Create or login admin user
echo "Attempting to login admin user..."
TOKEN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "workspaceadmin@example.com",
        "password": "testpassword123"
    }')

# Check if login was successful
if echo "$TOKEN_RESPONSE" | jq -e '.access_token' >/dev/null 2>&1; then
    print_status 0 "Admin user login"
    # Extract admin user's ID from login response
    USER_ID=$(echo $TOKEN_RESPONSE | jq -r '.user.id')
else
    echo "Admin user not found, creating new admin user..."
    ADMIN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "workspaceadmin@example.com",
            "password": "testpassword123",
            "first_name": "Workspace",
            "last_name": "Admin",
            "username": "workspaceadmin"
        }')

    # Check if registration was successful
    if echo "$ADMIN_RESPONSE" | jq -e '.id' >/dev/null 2>&1; then
        print_status 0 "Admin user creation"
        # Extract admin user's ID from registration response
        USER_ID=$(echo $ADMIN_RESPONSE | jq -r '.id')
        
        # Login to get token for newly created user
        TOKEN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
            -H "Content-Type: application/json" \
            -d '{
                "email": "workspaceadmin@example.com",
                "password": "testpassword123"
            }')
    else
        echo -e "${RED}Failed to create admin user. Response:${NC}"
        echo "$ADMIN_RESPONSE" | jq
        exit 1
    fi
fi

# Verify we have a valid user ID
if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
    echo -e "${RED}Failed to get admin user ID${NC}"
    exit 1
fi

# Extract JWT token
JWT_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')
if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}Failed to get JWT token${NC}"
    exit 1
fi

# Set authorization header
AUTH_HEADER="Authorization: Bearer ${JWT_TOKEN}"

# Create or login team member user
echo "Attempting to login team member user..."
TOKEN2_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "teammember@example.com",
        "password": "testpassword123"
    }')

# Check if login was successful
if echo "$TOKEN2_RESPONSE" | jq -e '.access_token' >/dev/null 2>&1; then
    print_status 0 "Team member user login"
    # Extract team member's ID from login response
    USER2_ID=$(echo $TOKEN2_RESPONSE | jq -r '.user.id')
else
    echo "Team member user not found, creating new team member user..."
    MEMBER_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "teammember@example.com",
            "password": "testpassword123",
            "first_name": "Team",
            "last_name": "Member",
            "username": "teammember"
        }')

    # Check if registration was successful
    if echo "$MEMBER_RESPONSE" | jq -e '.id' >/dev/null 2>&1; then
        print_status 0 "Team member user creation"
        # Extract team member's ID from registration response
        USER2_ID=$(echo $MEMBER_RESPONSE | jq -r '.id')
        
        # Login to get token for newly created user
        TOKEN2_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
            -H "Content-Type: application/json" \
            -d '{
                "email": "teammember@example.com",
                "password": "testpassword123"
            }')
    else
        echo -e "${RED}Failed to create team member user. Response:${NC}"
        echo "$MEMBER_RESPONSE" | jq
        exit 1
    fi
fi

# Verify we have a valid team member ID
if [ -z "$USER2_ID" ] || [ "$USER2_ID" = "null" ]; then
    echo -e "${RED}Failed to get team member ID${NC}"
    exit 1
fi

# Extract team member's JWT token
JWT_TOKEN2=$(echo $TOKEN2_RESPONSE | jq -r '.access_token')
if [ -z "$JWT_TOKEN2" ]; then
    echo -e "${RED}Failed to get team member JWT token${NC}"
    exit 1
fi

# Set authorization header for team member
AUTH_HEADER2="Authorization: Bearer ${JWT_TOKEN2}"

# Create development team
echo "Creating development team..."
TEAM_RESPONSE=$(curl -s -X POST "${API_URL}/teams" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d "{
        \"name\": \"Development Team\",
        \"description\": \"Team for workspace management testing\",
        \"created_by\": \"${USER_ID}\",
        \"owner_id\": \"${USER_ID}\",
        \"is_active\": true
    }")

# Debug output
echo "Debug: Team creation response:"
echo "$TEAM_RESPONSE" | jq

# Check if team creation was successful
if echo "$TEAM_RESPONSE" | jq -e '.id' >/dev/null 2>&1; then
    print_status 0 "Team creation"
else
    echo -e "${RED}Failed to create team. Response:${NC}"
    echo "$TEAM_RESPONSE" | jq
    exit 1
fi

# Extract team ID
TEAM_ID=$(echo $TEAM_RESPONSE | jq -r '.id')
if [ -z "$TEAM_ID" ] || [ "$TEAM_ID" = "null" ]; then
    echo -e "${RED}Failed to get team ID${NC}"
    exit 1
fi

# Create workspace
echo "Creating workspace..."
WORKSPACE_RESPONSE=$(curl -s -X POST "${API_URL}/workspaces" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "name": "Test Workspace",
        "description": "Workspace for testing management features"
    }')
print_status $? "Workspace creation"

# Extract workspace ID
WORKSPACE_ID=$(echo $WORKSPACE_RESPONSE | jq -r '.id')
if [ -z "$WORKSPACE_ID" ] || [ "$WORKSPACE_ID" = "null" ]; then
    echo -e "${RED}Failed to get workspace ID${NC}"
    exit 1
fi

# Create project
echo "Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST "${API_URL}/workspaces/${WORKSPACE_ID}/projects" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "name": "Test Project",
        "description": "Project for testing workspace features",
        "team_id": "'${TEAM_ID}'"
    }')
print_status $? "Project creation"

# Extract project ID
PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.id')
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
    echo -e "${RED}Failed to get project ID${NC}"
    exit 1
fi

# Add team member to team
echo "Adding team member to team..."
curl -s -X POST "${API_URL}/teams/${TEAM_ID}/members" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "user_id": "'${USER2_ID}'",
        "role": "member"
    }' | jq
print_status $? "Add team member"

# Get workspace details
echo "Getting workspace details..."
curl -s -X GET "${API_URL}/workspaces/${WORKSPACE_ID}" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get workspace details"

# Get project details
echo "Getting project details..."
curl -s -X GET "${API_URL}/projects/${PROJECT_ID}" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get project details"

# Get team members
echo "Getting team members..."
curl -s -X GET "${API_URL}/teams/${TEAM_ID}/members" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get team members"

# Get workspace projects
echo "Getting workspace projects..."
curl -s -X GET "${API_URL}/workspaces/${WORKSPACE_ID}/projects" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get workspace projects"

# Team member tries to access workspace
echo "Team member accessing workspace..."
curl -s -X GET "${API_URL}/workspaces/${WORKSPACE_ID}" \
    -H "${AUTH_HEADER2}" | jq
print_status $? "Team member access workspace"

# Team member tries to access project
echo "Team member accessing project..."
curl -s -X GET "${API_URL}/projects/${PROJECT_ID}" \
    -H "${AUTH_HEADER2}" | jq
print_status $? "Team member access project"

echo -e "${GREEN}All tests completed successfully!${NC}" 