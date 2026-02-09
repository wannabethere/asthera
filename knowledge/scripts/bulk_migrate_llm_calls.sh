#!/bin/bash

# Bulk migrate LLM calls to traced pattern
# This script helps identify and prioritize files for migration

echo "=================================================="
echo "LLM Call Migration Analysis"
echo "=================================================="
echo ""

# Set the knowledge app directory
APP_DIR="${1:-knowledge/app}"

if [ ! -d "$APP_DIR" ]; then
    echo "Error: Directory $APP_DIR not found"
    echo "Usage: $0 [app_directory]"
    exit 1
fi

echo "Analyzing directory: $APP_DIR"
echo ""

# Find all files with LLM calls
echo "Finding files with LLM calls..."
FILES_WITH_CHAINS=$(grep -rl "chain\.ainvoke\|chain\.invoke\|llm\.ainvoke\|llm\.invoke" "$APP_DIR" | grep "\.py$")

# Count total files
TOTAL_FILES=$(echo "$FILES_WITH_CHAINS" | wc -l | tr -d ' ')

echo "Found $TOTAL_FILES files with LLM calls"
echo ""

# Categorize by directory
echo "=================================================="
echo "Files by Category:"
echo "=================================================="
echo ""

echo "ASSISTANTS (High Priority):"
echo "$FILES_WITH_CHAINS" | grep "/assistants/" | sort
echo ""

echo "AGENTS (High Priority):"
echo "$FILES_WITH_CHAINS" | grep "/agents/" | grep -v "/extractors/" | sort
echo ""

echo "SERVICES (Medium Priority):"
echo "$FILES_WITH_CHAINS" | grep "/services/" | sort
echo ""

echo "PIPELINES (Medium Priority):"
echo "$FILES_WITH_CHAINS" | grep "/pipelines/" | sort
echo ""

echo "EXTRACTORS (Lower Priority):"
echo "$FILES_WITH_CHAINS" | grep "/extractors/" | sort
echo ""

echo "OTHER:"
echo "$FILES_WITH_CHAINS" | grep -v "/assistants/\|/agents/\|/services/\|/pipelines/\|/extractors/" | sort
echo ""

# Count calls per file
echo "=================================================="
echo "Top 10 Files by LLM Call Count:"
echo "=================================================="
echo ""

for file in $FILES_WITH_CHAINS; do
    count=$(grep -c "chain\.ainvoke\|chain\.invoke\|llm\.ainvoke\|llm\.invoke" "$file")
    echo "$count $file"
done | sort -rn | head -10

echo ""

# Already migrated check
echo "=================================================="
echo "Migration Status:"
echo "=================================================="
echo ""

MIGRATED_COUNT=$(grep -l "from app.utils import traced_llm_call\|from app.utils import get_llm_tracer" $FILES_WITH_CHAINS | wc -l | tr -d ' ')

echo "Migrated: $MIGRATED_COUNT / $TOTAL_FILES files"
echo ""

if [ "$MIGRATED_COUNT" -gt 0 ]; then
    echo "Already migrated:"
    grep -l "from app.utils import traced_llm_call\|from app.utils import get_llm_tracer" $FILES_WITH_CHAINS | sort
    echo ""
fi

# Suggest migration order
echo "=================================================="
echo "Suggested Migration Order:"
echo "=================================================="
echo ""

echo "Phase 1 - Critical (High traffic, user-facing):"
echo "  1. app/assistants/nodes.py (✅ DONE)"
echo "  2. app/assistants/knowledge_assistance_nodes.py"
echo "  3. app/assistants/data_assistance_nodes.py"
echo "  4. app/agents/contextual_graph_reasoning_agent.py (✅ PARTIALLY DONE)"
echo "  5. app/agents/contextual_graph_retrieval_agent.py"
echo ""

echo "Phase 2 - Services (Business logic):"
echo "  6. app/services/context_breakdown_service.py"
echo "  7. app/services/edge_pruning_service.py"
echo "  8. app/services/reasoning_plan_service.py"
echo "  9. app/assistants/deep_research_integration_node.py"
echo ""

echo "Phase 3 - Supporting (Lower frequency):"
echo "  11-20. app/agents/mdl_*.py"
echo "  21-30. app/services/*.py"
echo "  31-40. app/agents/extractors/*.py"
echo "  41+. app/pipelines/extractions/*.py"
echo ""

echo "=================================================="
echo "Migration Commands:"
echo "=================================================="
echo ""
echo "# Analyze specific file:"
echo "python scripts/migrate_llm_calls.py app/assistants/knowledge_assistance_nodes.py"
echo ""
echo "# See all LLM patterns in a file:"
echo "grep -n 'chain\.ainvoke\|chain\.invoke' app/assistants/knowledge_assistance_nodes.py"
echo ""
echo "# Count LLM calls in a file:"
echo "grep -c 'chain\.ainvoke\|chain\.invoke' app/assistants/knowledge_assistance_nodes.py"
echo ""

echo "=================================================="
echo "Testing:"
echo "=================================================="
echo ""
echo "# Test after migration:"
echo "pytest tests/ -v -k llm"
echo ""
echo "# View traces:"
echo "tail -f logs/app.log | grep OTEL_TRACE | jq"
echo ""

echo "Done!"
