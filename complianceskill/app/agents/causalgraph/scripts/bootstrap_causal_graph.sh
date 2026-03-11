#!/bin/bash
# Bootstrap Causal Graph Seed Data
# 
# This script runs the complete initialization sequence:
# 1. Create Postgres schema
# 2. Ingest seed edges into Postgres + vector store
#
# Prerequisites:
#   - CCE_DB_URL environment variable set
#   - Vector store configured (ChromaDB or Qdrant)
#   - Python dependencies installed
#
# Usage:
#   ./bootstrap_causal_graph.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "=== CCE Causal Graph Bootstrap ==="
echo ""

# Step 1: Create Postgres schema
echo "[1/2] Creating Postgres schema..."

# Try to get connection string from environment or build from .env settings
if [ -n "$CCE_DB_URL" ]; then
    DB_URL="$CCE_DB_URL"
    echo "Using CCE_DB_URL from environment"
elif [ -n "$POSTGRES_HOST" ] && [ -n "$POSTGRES_DB" ] && [ -n "$POSTGRES_USER" ]; then
    # Build from individual env vars
    if [ -n "$POSTGRES_PASSWORD" ]; then
        DB_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
    else
        DB_URL="postgresql://${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
    fi
    echo "Built connection string from POSTGRES_* environment variables"
else
    echo "ERROR: Database connection not available"
    echo "Set one of:"
    echo "  - CCE_DB_URL=postgresql://user:pass@host:5432/db"
    echo "  - POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER (and optionally POSTGRES_PASSWORD) in .env"
    exit 1
fi

psql "$DB_URL" -f "$SCRIPT_DIR/create_cce_schema.sql"
if [ $? -eq 0 ]; then
    echo "✓ Postgres schema created"
else
    echo "✗ Failed to create Postgres schema"
    exit 1
fi

# Step 2: Ingest seed data
echo ""
echo "[2/2] Ingesting seed edges into Postgres + vector store..."
cd "$PROJECT_ROOT"
python -m app.agents.causalgraph.scripts.ingest_causal_seed_data \
    --seed-file lms_causal_edge_seed.json

if [ $? -eq 0 ]; then
    echo "✓ Seed data ingestion complete"
else
    echo "✗ Failed to ingest seed data"
    exit 1
fi

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Verify ingestion: SELECT COUNT(*) FROM cce.causal_corpus;"
echo "  2. Test retrieval: Run a causal graph query"
echo "  3. Monitor vector store: Check cce_causal_edges collection"
