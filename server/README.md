# Building an AI Chatbot with LangGraph, FastAPI & Streamlit – An End-to-End Guide

## Overview

This project is a simple chatbot built with LangGraph, FastAPI, and Streamlit. It allows you to chat with a chatbot and save the chat history.

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- PostgreSQL 15 or higher
- Git

## Setup

1. **Clone the repository and navigate to the backend directory:**
```bash
cd genieml/backend
```

2. **Create and activate a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up PostgreSQL using Docker:**
```bash
docker run --name postgres-db \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=genieml \
    -p 5432:5432 \
    -d postgres:15
```

5. **Initialize the database:**
```bash
# Initialize base schema
psql -h localhost -U postgres -d AnalyticAgent -f scripts/init.sql

psql -h localhost -U postgres -d AnalyticAgent -c "
-- First create the default team
INSERT INTO teams (id, name, description, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000001', 'Default Team', 'Default team for all users', NOW(), NOW());

-- Then create the default workspace
INSERT INTO workspaces (id, name, description,team_id, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000002', 'Default Workspace', 'Default workspace for all users', '00000000-0000-0000-0000-000000000001',NOW(), NOW());

-- Create the default project
INSERT INTO projects (id, name, description, workspace_id, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000003', 'Default Project', 'Default project for all users', '00000000-0000-0000-0000-000000000002', NOW(), NOW());

-- Create default role
INSERT INTO roles (id, name, description, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000004', 'user', 'Default user role', NOW(), NOW());

-- Add team to workspace
INSERT INTO workspace_access (workspace_id, team_id, access_level, created_at, updated_at)
VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'admin', NOW(), NOW());
"
# Create default resources in the correct order
psql -h localhost -U postgres -d AnalyticAgent -f scripts/migrations/versions/create_default_resources.sql

# Add missing permissions
psql -h localhost -U postgres -d AnalyticAgent -f scripts/migrations/versions/add_missing_permissions.sql

#latest One

psql -h localhost -U postgres -d AnalyticAgent -f scripts/migrations/versions/update_workspace_permissions.sql

psql -h localhost -U postgres -d AnalyticAgent -f scripts/migrations/versions/workspaceaccess.sql

```

6. **Start the FastAPI server:**
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8008
```

## Default Resources

After initialization, the following default resources will be created:

- Default Team ID: `00000000-0000-0000-0000-000000000001`
- Default Workspace ID: `00000000-0000-0000-0000-000000000002`
- Default Project ID: `00000000-0000-0000-0000-000000000003`
- Default Role ID: `00000000-0000-0000-0000-000000000004`

These resources will be automatically assigned to new users upon registration.

## API Testing

The repository includes comprehensive API test scripts that demonstrate the full functionality of the application.

### Running the Tests

1. Make the test scripts executable:
```bash
chmod +x scripts/api_test.sh
chmod +x scripts/test_thread_collab.sh
```

2. Run the test scripts:
```bash
# Run the main API test
./scripts/api_test.sh

# Run the thread collaboration test
./scripts/test_thread_collab.sh
```

### What the Tests Cover

The test scripts perform the following operations:

1. **User Management**
   - User registration
   - User login
   - JWT token generation

2. **Team Management**
   - Team creation
   - Team member management

3. **Workspace Management**
   - Workspace creation
   - Team access management

4. **Project Management**
   - Project creation
   - Project access control

5. **Thread Management**
   - Thread creation
   - Thread collaboration
   - Thread configuration
   - Chat message handling

### Test Data

The scripts use the following test data:

- Admin User:
  - Email: admin@example.com
  - Password: Admin123!
  - Name: Admin User

- Regular User:
  - Email: user@example.com
  - Password: User123!
  - Name: Regular User

- Test Resources:
  - Team: "Test Team"
  - Workspace: "Test Workspace"
  - Project: "Test Project"
  - Thread: "Test Thread"

### Expected Output

The scripts provide colored output:
- Green: Successful operations
- Red: Failed operations

Each operation's status is clearly displayed, and the scripts will exit if any critical operation fails.

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

Create a `.env` file in the backend directory with the following variables:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/genieml
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=525600  # 1 year
```

## Troubleshooting

1. **Database Connection Issues**
   - Ensure PostgreSQL is running: `docker ps`
   - Check database credentials in `.env`
   - Verify database exists: `psql -h localhost -U postgres -l`

2. **Dependency Issues**
   - Ensure you're using Python 3.11
   - Try updating pip: `pip install --upgrade pip`
   - Reinstall requirements: `pip install -r requirements.txt --no-cache-dir`

3. **Permission Issues**
   - Check file permissions: `chmod +x scripts/*.sh`
   - Ensure database user has proper permissions

4. **Database Initialization Issues**
   - If you encounter foreign key constraint errors, try dropping and recreating the database:
     ```bash
     psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS genieml;"
     psql -h localhost -U postgres -c "CREATE DATABASE genieml;"
     ```
   - Then run the initialization steps again in order

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
