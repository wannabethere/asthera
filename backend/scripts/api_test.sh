#!/bin/bash

# Base URL
BASE_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[+] $1${NC}"
}

print_error() {
    echo -e "${RED}[-] $1${NC}"
}

# Function to extract JWT token from response
extract_token() {
    echo $1 | jq -r '.access_token'
}

# Function to extract user details from response
extract_user_details() {
    echo $1 | jq -r '.user'
}

# Function to extract ID from response
extract_id() {
    echo $1 | jq -r '.user.id'
}

# Function to clean up test data
cleanup() {
    echo -e "\n${GREEN}Starting cleanup...${NC}"
    
    # Delete thread
    if [ ! -z "$THREAD_ID" ]; then
        echo "Deleting thread..."
        curl -s -X DELETE "${BASE_URL}/threads/${THREAD_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Delete project
    if [ ! -z "$PROJECT_ID" ]; then
        echo "Deleting project..."
        curl -s -X DELETE "${BASE_URL}/projects/${PROJECT_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Remove team from workspace
    if [ ! -z "$WORKSPACE_ID" ] && [ ! -z "$TEAM_ID" ]; then
        echo "Removing team from workspace..."
        curl -s -X DELETE "${BASE_URL}/workspaces/${WORKSPACE_ID}/access/${TEAM_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Delete workspace
    if [ ! -z "$WORKSPACE_ID" ]; then
        echo "Deleting workspace..."
        curl -s -X DELETE "${BASE_URL}/workspaces/${WORKSPACE_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Remove user from team
    if [ ! -z "$TEAM_ID" ] && [ ! -z "$USER_ID" ]; then
        echo "Removing user from team..."
        curl -s -X DELETE "${BASE_URL}/teams/${TEAM_ID}/members/${USER_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Delete team
    if [ ! -z "$TEAM_ID" ]; then
        echo "Deleting team..."
        curl -s -X DELETE "${BASE_URL}/teams/${TEAM_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Delete regular user
    if [ ! -z "$USER_ID" ]; then
        echo "Deleting regular user..."
        curl -s -X DELETE "${BASE_URL}/users/${USER_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    # Delete admin user
    if [ ! -z "$ADMIN_ID" ]; then
        echo "Deleting admin user..."
        curl -s -X DELETE "${BASE_URL}/users/${ADMIN_ID}" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" > /dev/null
    fi
    
    echo -e "${GREEN}Cleanup completed!${NC}"
}

# Set up trap to run cleanup on script exit
trap cleanup EXIT

# 1. Register Admin User
print_status "Registering admin user..."
ADMIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "admin@example.com",
        "password": "Admin123!",
        "first_name": "Admin",
        "last_name": "User"
    }')

ADMIN_TOKEN=$(extract_token "$ADMIN_RESPONSE")
ADMIN_DETAILS=$(extract_user_details "$ADMIN_RESPONSE")
ADMIN_ID=$(extract_id "$ADMIN_RESPONSE")
if [ -z "$ADMIN_TOKEN" ]; then
    print_error "Failed to register admin user"
    exit 1
fi
print_status "Admin user registered successfully"
echo "Admin user details:"
echo $ADMIN_DETAILS | jq

# 2. Register Regular User
print_status "Registering regular user..."
USER_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "user@example.com",
        "password": "User123!",
        "first_name": "Regular",
        "last_name": "User"
    }')

USER_TOKEN=$(extract_token "$USER_RESPONSE")
USER_DETAILS=$(extract_user_details "$USER_RESPONSE")
USER_ID=$(extract_id "$USER_RESPONSE")
if [ -z "$USER_TOKEN" ]; then
    print_error "Failed to register regular user"
    exit 1
fi
print_status "Regular user registered successfully"
echo "Regular user details:"
echo $USER_DETAILS | jq

# 3. Create Team
print_status "Creating team..."
TEAM_RESPONSE=$(curl -s -X POST "${BASE_URL}/teams/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Team",
        "description": "A test team for API testing"
    }')

TEAM_ID=$(extract_id "$TEAM_RESPONSE")
if [ -z "$TEAM_ID" ]; then
    print_error "Failed to create team"
    exit 1
fi
print_status "Team created successfully with ID: ${TEAM_ID}"

# 4. Create Workspace
print_status "Creating workspace..."
WORKSPACE_RESPONSE=$(curl -s -X POST "${BASE_URL}/workspaces/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Test Workspace\",
        \"description\": \"A test workspace for API testing\",
        \"team_id\": \"${TEAM_ID}\"
    }")

WORKSPACE_ID=$(extract_id "$WORKSPACE_RESPONSE")
if [ -z "$WORKSPACE_ID" ]; then
    print_error "Failed to create workspace"
    exit 1
fi
print_status "Workspace created successfully with ID: ${WORKSPACE_ID}"

# 5. Add User to Team
print_status "Adding user to team..."
TEAM_MEMBER_RESPONSE=$(curl -s -X POST "${BASE_URL}/teams/${TEAM_ID}/members" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"${USER_ID}\",
        \"role\": \"member\"
    }")

if [ $? -ne 0 ]; then
    print_error "Failed to add user to team"
    exit 1
fi
print_status "User added to team successfully"

# 6. Add Team to Workspace
print_status "Adding team to workspace..."
WORKSPACE_ACCESS_RESPONSE=$(curl -s -X POST "${BASE_URL}/workspaces/${WORKSPACE_ID}/access" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"team_id\": \"${TEAM_ID}\",
        \"access_level\": \"admin\"
    }")

if [ $? -ne 0 ]; then
    print_error "Failed to add team to workspace"
    exit 1
fi
print_status "Team added to workspace successfully"

# 7. Create Project
print_status "Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST "${BASE_URL}/projects/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Test Project\",
        \"description\": \"A test project for API testing\",
        \"workspace_id\": \"${WORKSPACE_ID}\"
    }")

PROJECT_ID=$(extract_id "$PROJECT_RESPONSE")
if [ -z "$PROJECT_ID" ]; then
    print_error "Failed to create project"
    exit 1
fi
print_status "Project created successfully with ID: ${PROJECT_ID}"

# 8. Create Thread
print_status "Creating thread..."
THREAD_RESPONSE=$(curl -s -X POST "${BASE_URL}/threads/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"title\": \"Test Thread\",
        \"description\": \"A test thread for API testing\",
        \"project_id\": \"${PROJECT_ID}\"
    }")

THREAD_ID=$(extract_id "$THREAD_RESPONSE")
if [ -z "$THREAD_ID" ]; then
    print_error "Failed to create thread"
    exit 1
fi
print_status "Thread created successfully with ID: ${THREAD_ID}"

# 9. List All Resources (as admin)
print_status "Listing all resources as admin..."
echo "Teams:"
curl -s -X GET "${BASE_URL}/teams/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}"

echo -e "\nWorkspaces:"
curl -s -X GET "${BASE_URL}/workspaces/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}"

echo -e "\nProjects:"
curl -s -X GET "${BASE_URL}/projects/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}"

echo -e "\nThreads:"
curl -s -X GET "${BASE_URL}/threads/" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}"

# 10. List All Resources (as regular user)
print_status "Listing all resources as regular user..."
echo "Teams:"
curl -s -X GET "${BASE_URL}/teams/" \
    -H "Authorization: Bearer ${USER_TOKEN}"

echo -e "\nWorkspaces:"
curl -s -X GET "${BASE_URL}/workspaces/" \
    -H "Authorization: Bearer ${USER_TOKEN}"

echo -e "\nProjects:"
curl -s -X GET "${BASE_URL}/projects/" \
    -H "Authorization: Bearer ${USER_TOKEN}"

echo -e "\nThreads:"
curl -s -X GET "${BASE_URL}/threads/" \
    -H "Authorization: Bearer ${USER_TOKEN}"

print_status "API testing completed successfully!" 