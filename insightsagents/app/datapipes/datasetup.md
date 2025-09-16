# requirements.txt - Complete dependencies for the enhanced pipeline service
# TODO: fix recommendation questions.
,
    "reasoning": "```json\n{\n\"categories\": [\n{\n\"category_name\": \"Training Effectiveness\",\n\"questions\": [\n\"What is the average completion rate for training programs?\",\n\"Which training titles have the highest completion rates?\",\n\"How does the completion rate vary by training title?\",\n\"What is the average time taken to complete training after being assigned?\",\n\"Are there specific training titles that consistently have high drop-off rates?\",\n\"What percentage of employees complete their assigned training within the expected timeframe?\",\n\"How does the transcript status correlate with the completion date?\",\n\"What trends can be observed in training completion over the past year?\",\n\"Which employees have the highest number of incomplete training assignments?\",\n\"How does the assigned date impact the likelihood of training completion?\"\n]\n},\n{\n\"category_name\": \"Employee Engagement\",\n\"questions\": [\n\"Which employees have the most training assignments?\",\n\"What is the average number of training programs assigned to each employee?\",\n\"How does employee engagement in training correlate with their job performance?\",\n\"Are there specific departments with higher training completion rates?\",\n\"What factors contribute to an employee's decision to complete or not complete training?\",\n\"How does the training title affect employee engagement levels?\",\n\"What is the relationship between transcript status and employee retention?\",\n\"How often do employees request additional training opportunities?\",\n\"What is the impact of training on employee satisfaction scores?\",\n\"Which employees have the highest number of training completions in the last year?\"\n]\n},\n{\n\"category_name\": \"Training Management\",\n\"questions\": [\n\"How can we identify training programs that need improvement based on drop-off rates?\",\n\"What strategies can be implemented to reduce training drop-off rates?\",\n\"How does the timing of training assignments affect completion rates?\",\n\"What is the process for updating training titles and statuses in the system?\",\n\"How can we track the effectiveness of training programs over time?\",\n\"What metrics should be monitored to assess training program success?\",\n\"How can we ensure that training assignments are aligned with employee career goals?\",\n\"What role does management play in encouraging training completion?\",\n\"How can we leverage data to improve future training initiatives?\",\n\"What are the best practices for communicating training requirements to employees?\"\n]\n}\n]\n}\n```"
    
# Core FastAPI and async support
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
aiofiles==23.2.1

# HTTP client for API calls
httpx==0.25.2

# Database and ORM
sqlalchemy==2.0.23
alembic==1.12.1
asyncpg==0.29.0  # PostgreSQL async driver
psycopg2-binary==2.9.9  # PostgreSQL sync driver
aiosqlite==0.19.0  # SQLite async driver

# Data processing and ML
pandas==2.1.3
numpy==1.25.2
scikit-learn==1.3.2
matplotlib==3.8.2
seaborn==0.13.0
plotly==5.17.0
scipy==1.11.4

# Validation and serialization
pydantic==2.5.0
pydantic-settings==2.1.0

# Configuration management
python-dotenv==1.0.0
pyyaml==6.0.1

# Vector database (Chroma)
chromadb==0.4.18
sentence-transformers==2.2.2
transformers==4.35.2

# Caching and message queue
redis==5.0.1
celery==5.3.4

# Monitoring and logging
prometheus-client==0.19.0
structlog==23.2.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-mock==3.12.0
httpx==0.25.2  # For testing API endpoints

# Development tools
black==23.11.0
isort==5.12.0
flake8==6.1.0
mypy==1.7.1

# Security
cryptography==41.0.8
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Utilities
click==8.1.7
rich==13.7.0
typer==0.9.0

---

# alembic.ini - Database migration configuration
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = sqlite:///pipeline_codes.db

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S

---

# migrations/env.py - Alembic environment configuration
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import your models
from database_models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for 'autogenerate' support
target_metadata = Base.metadata

def get_url():
    """Get database URL from environment or config"""
    return os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_section_name)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

---

# .env.example - Environment variables template
# Copy this to .env and configure for your environment

# Service Configuration
PIPELINE_BASE_DIR=/app/pipeline_executions
DEFAULT_TIMEOUT=300
CLEANUP_AFTER_EXECUTION=false
LOG_LEVEL=INFO
PORT=8000

# Python Environment
ADDITIONAL_PYTHON_PATHS=/app:/app/app:/app/ml_tools
PYTHONPATH=/app:/app/app

# Database Configuration
DATABASE_URL=sqlite:///pipeline_codes.db
# For PostgreSQL: DATABASE_URL=postgresql://user:password@localhost:5432/pipeline_codes
# For MySQL: DATABASE_URL=mysql://user:password@localhost:3306/pipeline_codes

# Chroma Vector Database
ENABLE_CHROMA=true
CHROMA_COLLECTION=pipeline_codes
CHROMA_PERSIST_DIRECTORY=/app/chroma_data

# Pipeline Features
AUTO_SAVE_PIPELINES=true
ENABLE_MONITORING=false
ENABLE_CACHING=false

# Redis (for caching and task queue)
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here-change-in-production
API_KEY=your-api-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Authentication (optional)
ENABLE_AUTH=false
JWT_SECRET_KEY=your-jwt-secret-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# External Services
OPENAI_API_KEY=your-openai-key-for-embeddings
HUGGINGFACE_API_KEY=your-huggingface-key

# Monitoring
PROMETHEUS_ENABLED=false
GRAFANA_ENABLED=false

---

# config/development.yaml - Development configuration
database:
  url: "sqlite:///./dev_pipeline_codes.db"
  echo: true
  
service:
  base_directory: "./dev_pipeline_executions"
  timeout_seconds: 180
  cleanup_after_execution: true
  log_level: "DEBUG"
  
chroma:
  enabled: true
  collection: "dev_pipeline_codes"
  persist_directory: "./dev_chroma_data"
  
features:
  auto_save_pipelines: true
  enable_monitoring: false
  enable_caching: false
  
api:
  host: "localhost"
  port: 8000
  debug: true

---

# config/production.yaml - Production configuration
database:
  url: "${DATABASE_URL}"
  echo: false
  pool_size: 20
  max_overflow: 30
  
service:
  base_directory: "/app/pipeline_executions"
  timeout_seconds: 600
  cleanup_after_execution: false
  log_level: "INFO"
  
chroma:
  enabled: true
  collection: "pipeline_codes"
  persist_directory: "/app/chroma_data"
  
features:
  auto_save_pipelines: true
  enable_monitoring: true
  enable_caching: true
  
api:
  host: "0.0.0.0"
  port: 8000
  debug: false
  
security:
  enable_auth: true
  rate_limiting: true
  cors_origins: ["https://yourdomain.com"]

---

# config/test.yaml - Test configuration
database:
  url: "sqlite:///:memory:"
  echo: false
  
service:
  base_directory: "./test_pipeline_executions"
  timeout_seconds: 30
  cleanup_after_execution: true
  log_level: "ERROR"
  
chroma:
  enabled: false
  
features:
  auto_save_pipelines: true
  enable_monitoring: false
  enable_caching: false
  
api:
  host: "localhost"
  port: 8001
  debug: false

---

# docker-compose.yml - Updated with database services
version: '3.8'

services:
  # Main pipeline service
  pipeline-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://pipeline_user:pipeline_pass@postgres:5432/pipeline_codes
      - REDIS_URL=redis://redis:6379/0
      - CHROMA_PERSIST_DIRECTORY=/app/chroma_data
      - PIPELINE_BASE_DIR=/app/pipeline_executions
      - ADDITIONAL_PYTHON_PATHS=/app:/app/app:/app/ml_tools
      - ENABLE_CHROMA=true
      - AUTO_SAVE_PIPELINES=true
    volumes:
      - ./pipeline_executions:/app/pipeline_executions
      - ./chroma_data:/app/chroma_data
      - ./data:/app/data:ro
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # PostgreSQL database
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=pipeline_codes
      - POSTGRES_USER=pipeline_user
      - POSTGRES_PASSWORD=pipeline_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql:ro
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pipeline_user -d pipeline_codes"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis for caching and task queue
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # Optional: Adminer for database management
  adminer:
    image: adminer:latest
    ports:
      - "8080:8080"
    environment:
      - ADMINER_DEFAULT_SERVER=postgres
    depends_on:
      - postgres
    restart: unless-stopped

  # Optional: Redis Commander for Redis management
  redis-commander:
    image: rediscommander/redis-commander:latest
    ports:
      - "8081:8081"
    environment:
      - REDIS_HOSTS=local:redis:6379
    depends_on:
      - redis
    restart: unless-stopped

  # Optional: Prometheus for monitoring
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  # Optional: Grafana for visualization
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  default:
    name: pipeline_network

---

# docker-compose.dev.yml - Development override
version: '3.8'

services:
  pipeline-service:
    build:
      context: .
      dockerfile: Dockerfile.dev
    environment:
      - DATABASE_URL=sqlite:///./dev_pipeline_codes.db
      - LOG_LEVEL=DEBUG
      - CLEANUP_AFTER_EXECUTION=true
    volumes:
      - .:/app
      - /app/__pycache__
      - /app/.pytest_cache
    command: uvicorn enhanced_pipeline_api:app --host 0.0.0.0 --port 8000 --reload
    
  # Use SQLite in development, so no postgres service needed
  postgres:
    profiles: ["full"]  # Only start with --profile full
    
  redis:
    profiles: ["full"]  # Only start with --profile full

---

# Dockerfile.dev - Development dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-mock \
    black \
    isort \
    flake8 \
    mypy

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONPATH="/app:/app/app"
ENV PIPELINE_BASE_DIR="/app/dev_pipeline_executions"

# Create directories
RUN mkdir -p /app/dev_pipeline_executions
RUN mkdir -p /app/dev_chroma_data
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8000

# Development command (can be overridden)
CMD ["uvicorn", "enhanced_pipeline_api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]