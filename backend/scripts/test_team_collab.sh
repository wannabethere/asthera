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
    
    # Delete thread configurations
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread configurations..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD_ID}/configurations" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    # Delete thread collaborators
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread collaborators..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD_ID}/collaborators" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
    # Delete thread
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread..."
        curl -s -X DELETE "${API_URL}/threads/${THREAD_ID}" \
            -H "${AUTH_HEADER}" > /dev/null || true
    fi
    
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
    
    # Delete third test user
    if [ ! -z "$USER3_ID" ]; then
        echo "Deleting third test user..."
        curl -s -X DELETE "${API_URL}/users/${USER3_ID}" \
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

# Create first test user (Team Admin)
echo "Creating first test user (Team Admin)..."
USER_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "teamadmin@example.com",
        "password": "testpassword123",
        "first_name": "Team",
        "last_name": "Admin",
        "username": "teamadmin"
    }')

# Check if registration was successful
if echo "$USER_RESPONSE" | jq -e '.id' >/dev/null 2>&1; then
    print_status 0 "First user creation"
else
    echo -e "${RED}Failed to create first user. Response:${NC}"
    echo "$USER_RESPONSE" | jq
    exit 1
fi

# Extract first user's ID
USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
    echo -e "${RED}Failed to get first user ID${NC}"
    exit 1
fi

# Login and get JWT token for first user
echo "Logging in to get JWT token for first user..."
TOKEN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "teamadmin@example.com",
        "password": "testpassword123"
    }')

# Check if login was successful
if echo "$TOKEN_RESPONSE" | jq -e '.access_token' >/dev/null 2>&1; then
    print_status 0 "First user login"
else
    echo -e "${RED}Failed to login first user. Response:${NC}"
    echo "$TOKEN_RESPONSE" | jq
    exit 1
fi

# Extract JWT token and user details
JWT_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')
USER_DETAILS=$(echo $TOKEN_RESPONSE | jq -r '.user')
if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}Failed to get JWT token${NC}"
    exit 1
fi

# Set authorization header for first user
AUTH_HEADER="Authorization: Bearer ${JWT_TOKEN}"

# Create second test user (Team Member)
echo "Creating second test user (Team Member)..."
USER2_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "teammember@example.com",
        "password": "testpassword123",
        "first_name": "Team",
        "last_name": "Member",
        "username": "teammember"
    }')

# Check if registration was successful
if echo "$USER2_RESPONSE" | jq -e '.id' >/dev/null 2>&1; then
    print_status 0 "Second user creation"
else
    echo -e "${RED}Failed to create second user. Response:${NC}"
    echo "$USER2_RESPONSE" | jq
    exit 1
fi

# Extract second user's ID
USER2_ID=$(echo $USER2_RESPONSE | jq -r '.id')
if [ -z "$USER2_ID" ] || [ "$USER2_ID" = "null" ]; then
    echo -e "${RED}Failed to get second user ID${NC}"
    exit 1
fi

# Create third test user (New Team Member)
echo "Creating third test user (New Team Member)..."
USER3_RESPONSE=$(curl -s -X POST "${API_URL}/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "newmember@example.com",
        "password": "testpassword123",
        "first_name": "New",
        "last_name": "Member",
        "username": "newmember"
    }')

# Check if registration was successful
if echo "$USER3_RESPONSE" | jq -e '.id' >/dev/null 2>&1; then
    print_status 0 "Third user creation"
else
    echo -e "${RED}Failed to create third user. Response:${NC}"
    echo "$USER3_RESPONSE" | jq
    exit 1
fi

# Extract third user's ID
USER3_ID=$(echo $USER3_RESPONSE | jq -r '.id')
if [ -z "$USER3_ID" ] || [ "$USER3_ID" = "null" ]; then
    echo -e "${RED}Failed to get third user ID${NC}"
    exit 1
fi

# Create a team
echo "Creating a team..."
TEAM_RESPONSE=$(curl -s -X POST "${API_URL}/teams" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "name": "Test Team",
        "description": "A team for testing collaboration features"
    }')
print_status $? "Team creation"

# Extract team ID
TEAM_ID=$(echo $TEAM_RESPONSE | jq -r '.id')
if [ -z "$TEAM_ID" ] || [ "$TEAM_ID" = "null" ]; then
    echo -e "${RED}Failed to get team ID${NC}"
    exit 1
fi

# Add second user to the team
echo "Adding second user to the team..."
curl -s -X POST "${API_URL}/teams/${TEAM_ID}/members" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "user_id": "'${USER2_ID}'",
        "role": "member"
    }' | jq
print_status $? "Add team member"

# Create a workspace
echo "Creating a workspace..."
WORKSPACE_RESPONSE=$(curl -s -X POST "${API_URL}/workspaces" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "name": "Test Workspace",
        "description": "A workspace for testing team collaboration"
    }')
print_status $? "Workspace creation"

# Extract workspace ID
WORKSPACE_ID=$(echo $WORKSPACE_RESPONSE | jq -r '.id')
if [ -z "$WORKSPACE_ID" ] || [ "$WORKSPACE_ID" = "null" ]; then
    echo -e "${RED}Failed to get workspace ID${NC}"
    exit 1
fi

# Create a project in the workspace
echo "Creating a project..."
PROJECT_RESPONSE=$(curl -s -X POST "${API_URL}/workspaces/${WORKSPACE_ID}/projects" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "name": "Test Project",
        "description": "A project for testing team collaboration",
        "team_id": "'${TEAM_ID}'"
    }')
print_status $? "Project creation"

# Extract project ID
PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.id')
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "null" ]; then
    echo -e "${RED}Failed to get project ID${NC}"
    exit 1
fi

# Invite third user to the team
echo "Inviting third user to the team..."
INVITE_RESPONSE=$(curl -s -X POST "${API_URL}/teams/${TEAM_ID}/invitations" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "user_id": "'${USER3_ID}'",
        "role": "member",
        "message": "Please join our team!"
    }')
print_status $? "Team invitation"

# Extract invitation ID
INVITATION_ID=$(echo $INVITE_RESPONSE | jq -r '.id')
if [ -z "$INVITATION_ID" ] || [ "$INVITATION_ID" = "null" ]; then
    echo -e "${RED}Failed to get invitation ID${NC}"
    exit 1
fi

# Login as third user
echo "Logging in as third user..."
TOKEN3_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "newmember@example.com",
        "password": "testpassword123"
    }')

# Check if login was successful
if echo "$TOKEN3_RESPONSE" | jq -e '.access_token' >/dev/null 2>&1; then
    print_status 0 "Third user login"
else
    echo -e "${RED}Failed to login third user. Response:${NC}"
    echo "$TOKEN3_RESPONSE" | jq
    exit 1
fi

# Extract third user's JWT token
JWT_TOKEN3=$(echo $TOKEN3_RESPONSE | jq -r '.access_token')
if [ -z "$JWT_TOKEN3" ]; then
    echo -e "${RED}Failed to get third user JWT token${NC}"
    exit 1
fi

# Set authorization header for third user
AUTH_HEADER3="Authorization: Bearer ${JWT_TOKEN3}"

# Third user accepts team invitation
echo "Third user accepting team invitation..."
curl -s -X PUT "${API_URL}/teams/${TEAM_ID}/invitations/${INVITATION_ID}/respond" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER3}" \
    -d '{
        "status": "accepted"
    }' | jq
print_status $? "Accept team invitation"

# Create a thread in the project
echo "Creating a thread..."
THREAD_RESPONSE=$(curl -s -X POST "${API_URL}/threads/" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "title": "Team Collaboration Thread",
        "description": "A thread for team collaboration testing",
        "project_id": "'${PROJECT_ID}'"
    }')
print_status $? "Thread creation"

# Extract thread ID
THREAD_ID=$(echo $THREAD_RESPONSE | jq -r '.id')
if [ -z "$THREAD_ID" ] || [ "$THREAD_ID" = "null" ]; then
    echo -e "${RED}Failed to get thread ID${NC}"
    exit 1
fi

# Add chat messages from different team members
echo "Adding chat message from team admin..."
curl -s -X POST "${API_URL}/chat/message" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER}" \
    -d '{
        "thread_id": "'${THREAD_ID}'",
        "message": "Hello team! Welcome to our collaboration thread!"
    }' | jq
print_status $? "Add chat message from admin"

# Login as second user
echo "Logging in as second user..."
TOKEN2_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "teammember@example.com",
        "password": "testpassword123"
    }')

# Check if login was successful
if echo "$TOKEN2_RESPONSE" | jq -e '.access_token' >/dev/null 2>&1; then
    print_status 0 "Second user login"
else
    echo -e "${RED}Failed to login second user. Response:${NC}"
    echo "$TOKEN2_RESPONSE" | jq
    exit 1
fi

# Extract second user's JWT token
JWT_TOKEN2=$(echo $TOKEN2_RESPONSE | jq -r '.access_token')
if [ -z "$JWT_TOKEN2" ]; then
    echo -e "${RED}Failed to get second user JWT token${NC}"
    exit 1
fi

# Set authorization header for second user
AUTH_HEADER2="Authorization: Bearer ${JWT_TOKEN2}"

echo "Adding chat message from team member..."
curl -s -X POST "${API_URL}/chat/message" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER2}" \
    -d '{
        "thread_id": "'${THREAD_ID}'",
        "message": "Thanks for creating this thread! I'm excited to collaborate!"
    }' | jq
print_status $? "Add chat message from member"

echo "Adding chat message from new team member..."
curl -s -X POST "${API_URL}/chat/message" \
    -H "Content-Type: application/json" \
    -H "${AUTH_HEADER3}" \
    -d '{
        "thread_id": "'${THREAD_ID}'",
        "message": "Hello everyone! Glad to be part of the team!"
    }' | jq
print_status $? "Add chat message from new member"

# Get chat history
echo "Getting chat history..."
curl -s -X GET "${API_URL}/chat/history/${THREAD_ID}" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get chat history"

# Get team members
echo "Getting team members..."
curl -s -X GET "${API_URL}/teams/${TEAM_ID}/members" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get team members"

# Get project details
echo "Getting project details..."
curl -s -X GET "${API_URL}/projects/${PROJECT_ID}" \
    -H "${AUTH_HEADER}" | jq
print_status $? "Get project details"

echo -e "${GREEN}All tests completed successfully!${NC}" 