# Quick Start Guide - Universal Risk Platform

Get up and running in 15 minutes!

## Prerequisites

- Python 3.10+
- PostgreSQL 15+
- Anthropic API key ([get one here](https://console.anthropic.com/))
- OpenAI API key ([get one here](https://platform.openai.com/))

## Step 1: Database Setup (5 minutes)

### Install PostgreSQL + pgvector

```bash
# macOS
brew install postgresql@15
brew services start postgresql@15

# Ubuntu/Debian
sudo apt-get install postgresql-15 postgresql-contrib-15

# Install pgvector extension
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Create Database

```bash
# Create database
createdb risk_platform_db

# Run schema creation
psql -d risk_platform_db -f database/01_schema.sql
psql -d risk_platform_db -f database/02_risk_functions.sql
psql -d risk_platform_db -f database/03_sample_data.sql
```

## Step 2: Python Environment (3 minutes)

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r config/requirements.txt
```

## Step 3: Configuration (2 minutes)

```bash
# Copy environment template
cp config/.env.example .env

# Edit .env with your API keys
nano .env  # or your preferred editor
```

**Required configuration**:
```bash
# Minimum required settings in .env
DATABASE_URL=postgresql://user:password@localhost:5432/risk_platform_db
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

## Step 4: Verify Installation (2 minutes)

```bash
# Test database connection
python -c "from python.llm_risk_engine import create_risk_engine; engine = create_risk_engine(); print('✅ Connected successfully'); engine.close()"

# Run tests
pytest tests/ -v
```

## Step 5: Start API Server (1 minute)

```bash
# Start the API
uvicorn python.api:app --reload

# You should see:
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## Step 6: First Risk Assessment (2 minutes)

### Using curl

```bash
curl -X POST "http://localhost:8000/assess-risk" \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "Calculate employee attrition risk based on training engagement",
    "entity_id": "USR12345",
    "domain": "hr"
  }'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/assess-risk",
    json={
        "specification": "Calculate employee attrition risk based on training engagement",
        "entity_id": "USR12345",
        "domain": "hr"
    }
)

result = response.json()
print(f"Risk Score: {result['risk_score']}")
print(f"Risk Level: {result['risk_level']}")
print(f"Explanation: {result['explanation']}")
```

### Using the Python SDK directly

```python
from python.llm_risk_engine import UniversalRiskEngine, RiskSpecification

engine = UniversalRiskEngine()

spec = RiskSpecification(
    description="Calculate employee attrition risk based on training engagement",
    domain="hr"
)

# Your schema context
schema_context = {
    "tables": {
        "User_csod": {...},
        "Transcript_csod": {...}
    }
}

# Analyze
analysis = engine.understand_risk_request(spec, schema_context)
print(analysis.model_dump_json(indent=2))

engine.close()
```

## Verification Checklist

- [ ] Database created and accessible
- [ ] pgvector extension installed
- [ ] Python dependencies installed
- [ ] API keys configured in .env
- [ ] API server starts without errors
- [ ] First risk assessment completes successfully

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'anthropic'"

**Solution**: Make sure you activated the virtual environment
```bash
source venv/bin/activate  # Run this first!
pip install -r config/requirements.txt
```

### Issue: "psycopg2.OperationalError: could not connect to server"

**Solution**: Verify PostgreSQL is running
```bash
# Check status
pg_ctl status

# Start if needed
brew services start postgresql@15  # macOS
sudo service postgresql start      # Linux
```

### Issue: "Extension 'vector' does not exist"

**Solution**: Install pgvector extension
```bash
# Follow installation instructions above
# Or use Docker (see below)
```

## Docker Alternative (Easiest!)

If you prefer Docker:

```bash
# Start everything with Docker Compose
docker-compose up -d

# API will be available at http://localhost:8000
# Database at localhost:5432
```

## Next Steps

Now that you're running:

1. **Try Different Domains**: Test with security, finance, operations
2. **Load Your Data**: Connect your actual data sources
3. **Customize Parameters**: Adjust weights and thresholds
4. **Monitor Performance**: Check logs and metrics
5. **Set Up Production**: Follow [Deployment Guide](docs/deployment_guide.md)

## Example Workflows

### Workflow 1: HR Attrition Risk

```python
# 1. Define risk
spec = RiskSpecification(
    description="Calculate attrition risk from training data",
    domain="hr"
)

# 2. Provide schema
schema = load_schema("csod_risk_attrition")

# 3. Assess specific employee
result = assess_risk("USR12345", spec, schema)

# 4. Review recommendations
for rec in result.recommendations:
    print(f"- {rec}")

# 5. Take action based on risk level
if result.risk_level == "CRITICAL":
    notify_manager(employee_id="USR12345")
    schedule_retention_interview()
```

### Workflow 2: Vulnerability Prioritization

```python
# Assess all CVEs affecting your environment
cves = ["CVE-2024-1234", "CVE-2024-5678", "CVE-2024-9012"]

for cve_id in cves:
    result = assess_risk(
        entity_id=cve_id,
        specification="Assess exploitation risk",
        domain="security"
    )
    
    if result.risk_score >= 70:
        schedule_emergency_patch(cve_id)
    elif result.risk_score >= 50:
        schedule_urgent_patch(cve_id)
```

### Workflow 3: Customer Churn Prevention

```python
# Daily churn risk monitoring
customers = get_active_customers()

high_risk_customers = []

for customer_id in customers:
    result = assess_risk(
        entity_id=customer_id,
        specification="Predict churn from usage and support data",
        domain="sales"
    )
    
    if result.risk_level in ["CRITICAL", "HIGH"]:
        high_risk_customers.append({
            "id": customer_id,
            "risk_score": result.risk_score,
            "recommendations": result.recommendations
        })

# Send to account managers
send_daily_report(high_risk_customers)
```

## Performance Tips

1. **Cache LLM Analysis**: Analysis rarely changes, cache for 1 hour
2. **Batch Assessments**: Use `/assess-risk/batch` for multiple entities
3. **Use Read Replicas**: Point read queries to replicas
4. **Monitor Costs**: LLM calls are main cost driver
5. **Optimize Queries**: Add indexes for your most frequent queries

## Security Reminders

1. ✅ Never commit `.env` with real API keys
2. ✅ Use environment variables in production
3. ✅ Enable authentication for production API
4. ✅ Set up audit logging for compliance
5. ✅ Rotate API keys regularly

## Getting Help

- **Documentation**: See [docs/](docs/) folder
- **Examples**: See [examples/use_cases.md](examples/use_cases.md)
- **Issues**: Open an issue on GitHub
- **Email**: support@yourcompany.com

## What's Next?

1. **Explore Examples**: [examples/use_cases.md](examples/use_cases.md)
2. **Read Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
3. **Understand Design**: [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)
4. **Deploy to Production**: [docs/deployment_guide.md](docs/deployment_guide.md)

---

**Congratulations!** 🎉 You now have a universal risk assessment platform running!

Try assessing risks in different domains and see how transfer learning adapts automatically.

---

**Need Help?**
- 📚 [Full Documentation](docs/)
- 💬 [Community Discord](#)
- 📧 support@yourcompany.com
