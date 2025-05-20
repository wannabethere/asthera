#!/bin/bash

# This script starts the backend and frontend for local development/testing.
# Make sure you have run 'pip install -r backend/requirements.txt' and 'npm install' in frontend.

# Start backend
cd backend
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Start frontend
cd frontend
nohup npm start > frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Print info
sleep 2
echo "Backend started with PID $BACKEND_PID (log: backend/backend.log)"
echo "Frontend started with PID $FRONTEND_PID (log: frontend/frontend.log)"
echo "Access frontend at http://localhost:3000 and backend at http://localhost:8000"

echo "To stop, run: kill $BACKEND_PID $FRONTEND_PID" 