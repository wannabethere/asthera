#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# API endpoint
API_URL="http://localhost:8000"

# Test data
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="adminpassword123"
TEST_ORG_NAME="Test Organization"
TEST_ORG_DOMAIN="test.com"
TEST_CONTACT_EMAIL="contact@test.com"
TEST_CONTACT_NAME="Test Contact"
TEST_CONTACT_PHONE="1234567890"

# Helper function to print status
print_status() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Helper function to print error
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Helper function to validate JSON response
validate_json() {
    if ! echo "$1" | jq . >/dev/null 2>&1; then
        print_error "Invalid JSON response"
        return 1
    fi
    return 0
}

# Helper function to make API request
make_request() {
    local method=$1
    local endpoint=$2
    local data=$3
    local token=$4

    if [ -z "$token" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint"
    else
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $token" \
            -d "$data" \
            "$API_URL$endpoint"
    fi
}

# Helper function to login
login() {
    local email=$1
    local password=$2
    local response=$(make_request "POST" "/auth/login" "{\"email\":\"$email\",\"password\":\"$password\"}")
    validate_json "$response"
    echo "$response" | jq -r '.access_token'
}

# Helper function to cleanup
cleanup() {
    print_status "Cleaning up test data..."
    # Add cleanup logic here if needed
}

# Set up trap for cleanup
trap cleanup EXIT

echo "Starting organization tests..."

# Login as admin
print_status "Logging in as admin..."
ADMIN_TOKEN=$(login "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
if [ -z "$ADMIN_TOKEN" ]; then
    print_error "Failed to login as admin"
    exit 1
fi

# Test 1: Create application signup
print_status "Testing application signup creation..."
SIGNUP_DATA="{\"organization_name\":\"$TEST_ORG_NAME\",\"contact_email\":\"$TEST_CONTACT_EMAIL\",\"contact_name\":\"$TEST_CONTACT_NAME\",\"contact_phone\":\"$TEST_CONTACT_PHONE\"}"
SIGNUP_RESPONSE=$(make_request "POST" "/organizations/signup" "$SIGNUP_DATA")
validate_json "$SIGNUP_RESPONSE"
SIGNUP_ID=$(echo "$SIGNUP_RESPONSE" | jq -r '.id')
if [ -z "$SIGNUP_ID" ]; then
    print_error "Failed to create application signup"
    exit 1
fi

# Test 2: Approve signup
print_status "Testing signup approval..."
APPROVE_RESPONSE=$(make_request "POST" "/organizations/signup/$SIGNUP_ID/approve" "{}" "$ADMIN_TOKEN")
validate_json "$APPROVE_RESPONSE"
ORG_ID=$(echo "$APPROVE_RESPONSE" | jq -r '.id')
if [ -z "$ORG_ID" ]; then
    print_error "Failed to approve signup"
    exit 1
fi

# Test 3: Update organization info
print_status "Testing organization info update..."
INFO_DATA="{\"address\":\"123 Test St\",\"industry\":\"Technology\",\"website\":\"https://test.com\",\"description\":\"Test organization description\"}"
INFO_RESPONSE=$(make_request "PUT" "/organizations/$ORG_ID/info" "$INFO_DATA" "$ADMIN_TOKEN")
validate_json "$INFO_RESPONSE"

# Test 4: Get organization info
print_status "Testing get organization info..."
GET_INFO_RESPONSE=$(make_request "GET" "/organizations/$ORG_ID/info" "" "$ADMIN_TOKEN")
validate_json "$GET_INFO_RESPONSE"

# Test 5: Update additional info
print_status "Testing additional info update..."
ADDITIONAL_INFO="{\"social_media\":{\"twitter\":\"@testorg\",\"linkedin\":\"test-org\"},\"custom_fields\":{\"founded_year\":2024,\"employee_count\":100},\"preferences\":{\"theme\":\"dark\",\"notifications\":true}}"
ADDITIONAL_INFO_RESPONSE=$(make_request "PUT" "/organizations/$ORG_ID/additional-info" "$ADDITIONAL_INFO" "$ADMIN_TOKEN")
validate_json "$ADDITIONAL_INFO_RESPONSE"

# Test 6: Get additional info
print_status "Testing get additional info..."
GET_ADDITIONAL_INFO_RESPONSE=$(make_request "GET" "/organizations/$ORG_ID/additional-info" "" "$ADMIN_TOKEN")
validate_json "$GET_ADDITIONAL_INFO_RESPONSE"

# Test 7: Update organization configuration
print_status "Testing organization configuration update..."
CONFIG_DATA="{\"max_users\":20,\"max_threads\":200,\"features\":{\"chat\":true,\"collaboration\":true,\"analytics\":true,\"custom_feature\":true}}"
CONFIG_RESPONSE=$(make_request "PUT" "/organizations/$ORG_ID/config" "$CONFIG_DATA" "$ADMIN_TOKEN")
validate_json "$CONFIG_RESPONSE"

# Test 8: Get organization configuration
print_status "Testing get organization configuration..."
GET_CONFIG_RESPONSE=$(make_request "GET" "/organizations/$ORG_ID/config" "" "$ADMIN_TOKEN")
validate_json "$GET_CONFIG_RESPONSE"

# Test 9: Create organization invite
print_status "Testing organization invite creation..."
INVITE_DATA="{\"organization_id\":\"$ORG_ID\",\"email\":\"newuser@test.com\",\"role\":\"user\"}"
INVITE_RESPONSE=$(make_request "POST" "/organizations/invite" "$INVITE_DATA" "$ADMIN_TOKEN")
validate_json "$INVITE_RESPONSE"

# Test 10: Update organization details
print_status "Testing organization details update..."
UPDATE_DATA="{\"name\":\"Updated Test Organization\",\"domain\":\"updated-test.com\"}"
UPDATE_RESPONSE=$(make_request "PUT" "/organizations/$ORG_ID" "$UPDATE_DATA" "$ADMIN_TOKEN")
validate_json "$UPDATE_RESPONSE"

# Test 11: Get organization details
print_status "Testing get organization details..."
GET_ORG_RESPONSE=$(make_request "GET" "/organizations/$ORG_ID" "" "$ADMIN_TOKEN")
validate_json "$GET_ORG_RESPONSE"

# Test 12: Reject a signup (create new signup first)
print_status "Testing signup rejection..."
REJECT_SIGNUP_DATA="{\"organization_name\":\"Reject Test Org\",\"contact_email\":\"reject@test.com\",\"contact_name\":\"Reject Test\",\"contact_phone\":\"9876543210\"}"
REJECT_SIGNUP_RESPONSE=$(make_request "POST" "/organizations/signup" "$REJECT_SIGNUP_DATA")
validate_json "$REJECT_SIGNUP_RESPONSE"
REJECT_SIGNUP_ID=$(echo "$REJECT_SIGNUP_RESPONSE" | jq -r '.id')
REJECT_RESPONSE=$(make_request "POST" "/organizations/signup/$REJECT_SIGNUP_ID/reject" "{\"reason\":\"Test rejection\"}" "$ADMIN_TOKEN")
validate_json "$REJECT_RESPONSE"

print_status "All tests completed successfully!" 