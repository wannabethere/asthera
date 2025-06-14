FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . /app/

# Add the project root to PYTHONPATH
ENV PYTHONPATH=/app

# Create necessary directories
RUN mkdir -p /app/data \
    /app/config \
    /app/initscripts

# Copy specific directories
COPY agents/config /app/config/
COPY agents/initscripts /app/initscripts/

# Command to run the application
CMD ["uvicorn", "genieml.agents.main:app", "--reload", "--host", "0.0.0.0", "--port", "8020", "--workers", "4"] 