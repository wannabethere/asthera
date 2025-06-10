# GenieML Platform

GenieML is a comprehensive platform for AI-powered document processing and analysis, built with modern technologies and best practices.

## Architecture

The platform consists of several microservices:

### 1. Frontend Service
- React-based web application
- Port: 3000
- Features:
  - Modern UI for document management
  - Real-time collaboration
  - Interactive document analysis
  - User authentication and authorization

### 2. Backend Service
- FastAPI-based REST API
- Port: 8000
- Features:
  - User management and authentication
  - Document processing workflows
  - Team and workspace management
  - Integration with external services

### 3. Agents Service
- Python-based AI agents
- Features:
  - Document analysis and processing
  - Natural language understanding
  - Automated workflows
  - Integration with OpenAI and other AI services

### 4. Database Services
- PostgreSQL (Port: 5432)
  - Main application database
  - Stores user data, documents, and metadata
- Redis (Port: 6379)
  - Caching and message broker
  - Handles real-time updates and background tasks
- ChromaDB (Port: 8001)
  - Vector database for document embeddings
  - Enables semantic search and similarity matching

## Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- OpenAI API key
- Okta credentials (for authentication)

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
OKTA_ISSUER=your_okta_issuer
OKTA_CLIENT_ID=your_okta_client_id
OPENAI_API_KEY=your_openai_api_key
```

## Getting Started

1. Clone the repository:
```bash
git clone <repository-url>
cd genieml
```

2. Start the services:
```bash
docker-compose up -d
```

3. Access the services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Development

### Local Development Setup

1. Backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

2. Frontend:
```bash
cd frontend
npm install
npm start
```

3. Agents:
```bash
cd agents
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
python -m genimel.agents.main
```

### Database Migrations

To run database migrations:

```bash
cd backend
alembic upgrade head
```

## Project Structure

```
genieml/
├── backend/           # FastAPI backend service
├── frontend/         # React frontend application
├── agents/           # AI agents service
├── data/            # Shared data directory
├── docker-compose.yml
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]

## Support

For support, please [add support contact information] 