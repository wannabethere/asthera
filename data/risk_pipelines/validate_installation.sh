#!/bin/bash

# Universal Risk Platform - Installation Validator
# Run this script to verify your installation is complete and correct

set -e

echo "🔍 Universal Risk Platform - Installation Validator"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Check function
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $1"
        ((FAILED++))
    fi
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo "Checking Python environment..."
python3 --version > /dev/null 2>&1
check "Python 3.10+ installed"

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null
check "Python version >= 3.10"

echo ""
echo "Checking Python dependencies..."
python3 -c "import anthropic" 2>/dev/null
check "anthropic package installed"

python3 -c "import openai" 2>/dev/null
check "openai package installed"

python3 -c "import psycopg2" 2>/dev/null
check "psycopg2 package installed"

python3 -c "import fastapi" 2>/dev/null
check "fastapi package installed"

python3 -c "import pandas" 2>/dev/null
check "pandas package installed"

python3 -c "import numpy" 2>/dev/null
check "numpy package installed"

echo ""
echo "Checking database..."
psql --version > /dev/null 2>&1
check "PostgreSQL client installed"

if [ -f ".env" ]; then
    source .env
    psql $DATABASE_URL -c "SELECT 1" > /dev/null 2>&1
    check "Database connection works"
    
    psql $DATABASE_URL -c "SELECT * FROM pg_extension WHERE extname='vector'" | grep vector > /dev/null 2>&1
    check "pgvector extension installed"
    
    psql $DATABASE_URL -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='risk_patterns'" | grep 1 > /dev/null 2>&1
    check "Database schema created"
else
    warn ".env file not found - skipping database checks"
fi

echo ""
echo "Checking API keys..."
if [ -f ".env" ]; then
    source .env
    
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        check "ANTHROPIC_API_KEY configured"
    else
        warn "ANTHROPIC_API_KEY not set in .env"
    fi
    
    if [ -n "$OPENAI_API_KEY" ]; then
        check "OPENAI_API_KEY configured"
    else
        warn "OPENAI_API_KEY not set in .env"
    fi
else
    warn ".env file not found - create from .env.example"
fi

echo ""
echo "Checking project files..."
[ -f "README.md" ] && check "README.md exists" || warn "README.md missing"
[ -f "ARCHITECTURE.md" ] && check "ARCHITECTURE.md exists" || warn "ARCHITECTURE.md missing"
[ -f "QUICK_START.md" ] && check "QUICK_START.md exists" || warn "QUICK_START.md missing"
[ -f "python/llm_risk_engine.py" ] && check "Core engine exists" || warn "Core engine missing"
[ -f "database/01_schema.sql" ] && check "Database schema exists" || warn "Database schema missing"

echo ""
echo "=================================================="
echo "Installation Validation Complete"
echo "=================================================="
echo -e "Passed:   ${GREEN}$PASSED${NC}"
echo -e "Failed:   ${RED}$FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ Everything looks good! You're ready to go.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Read QUICK_START.md for setup instructions"
    echo "  2. Run: uvicorn python.api:app --reload"
    echo "  3. Test: curl http://localhost:8000/health"
elif [ $FAILED -eq 0 ]; then
    echo -e "${YELLOW}⚠ Installation mostly complete but has warnings.${NC}"
    echo "Review warnings above and fix as needed."
else
    echo -e "${RED}✗ Installation has issues that need to be fixed.${NC}"
    echo "Review failed checks above."
    echo ""
    echo "Common fixes:"
    echo "  - Install missing packages: pip install -r config/requirements.txt"
    echo "  - Install PostgreSQL: brew install postgresql@15"
    echo "  - Install pgvector: see README.md"
    echo "  - Create .env file: cp config/.env.example .env"
    echo "  - Set API keys in .env"
    exit 1
fi

echo ""
echo "For detailed setup instructions, see:"
echo "  - QUICK_START.md (15 minute setup guide)"
echo "  - FILE_INVENTORY.md (navigation guide)"
echo "  - examples/use_cases.md (usage examples)"
