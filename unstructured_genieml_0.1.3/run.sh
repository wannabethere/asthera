#!/bin/bash

# Read secrets from mounted files and export them
export DB_PASSWORD=$(cat /var/database-secrets/postgres)
export OPENAI_API_KEY=$(cat /tellius/secrets/openAiSecret)

# Start the application
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8080