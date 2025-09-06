# Agents Service - AI-Powered Analytics Engine

## 🎯 Overview

The Agents Service is the core AI engine of the GenieML platform, providing intelligent SQL generation, dashboard creation, and report writing capabilities. Built with LangChain and FastAPI, it serves as the primary interface for natural language to structured data operations.

## 🏗️ Architecture

### Core Components

```mermaid
graph TB
    A[FastAPI Router] --> B[Service Layer]
    B --> C[Pipeline Orchestrator]
    C --> D[SQL RAG Agent]
    C --> E[Dashboard Agent]
    C --> F[Report Writing Agent]
    
    D --> G[ChromaDB Vector Store]
    E --> H[Conditional Formatting Engine]
    F --> I[Self-Correcting RAG]
    
    J[PostgreSQL] --> B
    K[Redis Cache] --> B
```

### Key Features

- **SQL RAG System**: Self-correcting SQL generation with vector search
- **Dashboard Orchestration**: Intelligent dashboard creation with conditional formatting
- **Report Writing**: AI-powered report generation with quality evaluation
- **Pipeline Architecture**: Modular, extensible pipeline system
- **Real-time Streaming**: WebSocket support for live updates

## 🔧 Technical Stack

- **Framework**: FastAPI with async/await support
- **AI/ML**: LangChain, OpenAI GPT models
- **Vector Database**: ChromaDB for RAG operations
- **Database**: PostgreSQL for metadata storage
- **Cache**: Redis for session management
- **Streaming**: WebSocket for real-time updates

## 📁 Project Structure

```
agents/
├── app/
│   ├── agents/           # LangChain agents and nodes
│   │   ├── nodes/        # Individual agent nodes
│   │   └── pipelines/    # Pipeline orchestration
│   ├── services/         # Business logic services
│   │   ├── sql/          # SQL-related services
│   │   └── writers/      # Report and dashboard services
│   ├── core/             # Core utilities and configurations
│   ├── routers/          # FastAPI route handlers
│   └── utils/            # Utility functions
├── docs/                 # Comprehensive documentation
└── tests/               # Test suites
```

## 🚀 Key Capabilities

### 1. SQL RAG System
- **Natural Language to SQL**: Convert plain English to optimized SQL queries
- **Self-Correcting**: Automatic error detection and correction
- **Schema-Aware**: Intelligent understanding of database schemas
- **Query Optimization**: Performance-optimized SQL generation

### 2. Dashboard Orchestration
- **Two-Step Architecture**: Rule generation and application separation
- **Conditional Formatting**: Natural language to formatting rules
- **Streaming Results**: Real-time dashboard updates
- **Multi-Chart Support**: Complex dashboard configurations

### 3. Report Writing Agent
- **Self-Correcting RAG**: Iterative quality improvement
- **Multiple Personas**: Executive, Analyst, Technical writing styles
- **Business Goal Alignment**: Context-aware report generation
- **Quality Evaluation**: Automatic content assessment

## 🔌 API Endpoints

### SQL Operations
- `POST /sql/ask` - Natural language to SQL conversion
- `POST /sql/breakdown` - SQL query explanation
- `POST /sql/correct` - SQL error correction
- `POST /sql/expand` - SQL query expansion

### Dashboard Operations
- `POST /dashboard/create` - Create new dashboard
- `POST /dashboard/format` - Apply conditional formatting
- `GET /dashboard/stream/{id}` - Stream dashboard results

### Report Operations
- `POST /reports/generate` - Generate AI report
- `POST /reports/evaluate` - Quality evaluation
- `GET /reports/{id}/stream` - Stream report generation

## ⚙️ Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/genieml

# AI Models
OPENAI_API_KEY=your_openai_key
MODEL_NAME=gpt-4o-mini

# Vector Store
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Cache
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Service Configuration
- **Port**: 8020
- **Workers**: 4 (configurable)
- **Timeout**: 300 seconds
- **Max Requests**: 1000 per worker

## 🔄 Integration Patterns

### With Frontend
- RESTful API for standard operations
- WebSocket for real-time streaming
- Server-Sent Events for progress updates

### With Other Services
- **Backend Service**: User authentication and session management
- **Insights Agents**: ML pipeline integration
- **Workflow Services**: Task orchestration
- **Data Services**: Data processing coordination

## 📊 Performance Characteristics

- **Response Time**: < 2 seconds for simple queries
- **Throughput**: 100+ concurrent requests
- **Memory Usage**: ~2GB per worker
- **CPU Usage**: Moderate (AI model inference)

## 🛠️ Development

### Local Setup
```bash
cd agents
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8020
```

### Testing
```bash
pytest tests/ -v
```

### Docker Deployment
```bash
docker build -t genieml-agents .
docker run -p 8020:8020 genieml-agents
```

## 📈 Monitoring & Observability

- **Logging**: Structured logging with correlation IDs
- **Metrics**: Prometheus-compatible metrics
- **Tracing**: OpenTelemetry integration
- **Health Checks**: `/health` endpoint for service status

## 🔒 Security

- **Authentication**: JWT token validation
- **Authorization**: Role-based access control
- **Input Validation**: Pydantic model validation
- **Rate Limiting**: Request throttling
- **SQL Injection**: Parameterized queries only

## 📚 Documentation

- [SQL RAG System](./docs/pipeline.md)
- [Dashboard Architecture](./docs/README_NEW_ARCHITECTURE.md)
- [Report Writing Agent](./docs/README_REPORT_SERVICE.md)
- [Enhanced Dashboard](./docs/README_ENHANCED_DASHBOARD.md)

---

*Service Port: 8020 | Last Updated: December 2024*
