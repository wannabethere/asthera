# Compliance Skill API Service

FastAPI service that exposes the compliance automation workflow as HTTP endpoints.

## Quick Start

### Option 1: Using the run script (Recommended)

```bash
cd genieml/complianceskill
python run_api.py
```

### Option 2: Using uvicorn directly

```bash
cd genieml/complianceskill
uvicorn app.api.main:app --host 0.0.0.0 --port 8002 --reload
```

### Option 3: Running the module directly

```bash
cd genieml/complianceskill
python -m app.api.main
```

### Option 4: Using Python directly

```bash
cd genieml/complianceskill
python app/api/main.py
```

## Configuration

Set environment variables to configure the service:

```bash
export HOST=0.0.0.0          # Server host (default: 0.0.0.0)
export PORT=8002             # Server port (default: 8002)
export DEBUG=True            # Enable auto-reload (default: True)
```

Or create a `.env` file:

```bash
HOST=0.0.0.0
PORT=8002
DEBUG=True
```

## API Endpoints

Once running, the service exposes:

- **API Documentation**: `http://localhost:8002/docs` (Swagger UI)
- **ReDoc Documentation**: `http://localhost:8002/redoc`
- **Health Check**: `http://localhost:8002/health`
- **Workflow Execute**: `POST http://localhost:8002/workflow/execute`
- **Workflow Invoke**: `POST http://localhost:8002/workflow/invoke`
- **Workflow Resume**: `POST http://localhost:8002/workflow/resume`

## Testing

### Health Check

```bash
curl http://localhost:8002/health
```

Expected response:
```json
{"status": "healthy", "service": "compliance-skill-api"}
```

### Execute Workflow (Streaming)

```bash
curl -X POST http://localhost:8002/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "Create SIEM rules for SOC 2 CC6.1",
    "session_id": "test-session-123"
  }'
```

### Execute Workflow (Synchronous)

```bash
curl -X POST http://localhost:8002/workflow/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "Create SIEM rules for SOC 2 CC6.1",
    "session_id": "test-session-123"
  }'
```

## Production Deployment

For production, use a production ASGI server like Gunicorn with Uvicorn workers:

```bash
pip install gunicorn

gunicorn app.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8002 \
  --timeout 300
```

Or use Uvicorn with production settings:

```bash
uvicorn app.api.main:app \
  --host 0.0.0.0 \
  --port 8002 \
  --workers 4 \
  --no-reload \
  --log-level info
```

## Troubleshooting

### Port Already in Use

If port 8002 is already in use:

```bash
# Find process using port
lsof -i :8002

# Kill process or use different port
export PORT=8003
python run_api.py
```

### Import Errors

Make sure you're running from the `genieml/complianceskill` directory:

```bash
cd genieml/complianceskill
python run_api.py
```

### Module Not Found

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

## Integration with Asthera Backend

The Asthera Backend service can connect to this API by setting:

```bash
export COMPLIANCE_SKILL_URL=http://localhost:8002
```

See `astherabackend/SERVICES_SETUP.md` for more details.


#TODO:
When resuming, astream_events() may restart from the beginning. The workflow nodes should check for user_checkpoint_input and skip already-completed steps. If nodes don't handle this, you may need to:
Modify workflow nodes to check for checkpoint input and skip completed work
Use a different resume mechanism that continues from the exact checkpoint
Store execution progress and resume from the last completed node
The workflow should now stream properly and pause at checkpoints. Test it and let me know if you see any issues with the resume functionality.
