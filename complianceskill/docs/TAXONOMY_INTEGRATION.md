# Dashboard Taxonomy Integration with LLM Agent

## Overview

The enriched dashboard taxonomy is now integrated into the LLM agent to provide intelligent dashboard recommendations based on metrics and KPIs.

## How It Works

### 1. Taxonomy-Based Domain Matching

When the agent receives metrics and KPIs from upstream context, it uses the `match_domain_from_metrics_tool` to:

- Match metric names/types to taxonomy goals and focus areas
- Match KPIs to domain use cases
- Match data sources to appropriate domains
- Score domains by relevance and return top matches

### 2. Auto-Population of Decisions

The taxonomy recommendations automatically populate:
- **domain**: The best-fit dashboard domain (e.g., "ld_training", "security_operations")
- **category**: Template category derived from domain
- **complexity**: Domain's typical complexity level
- **theme**: Domain's theme preference (light/dark)

### 3. Enhanced Template Scoring

Templates are scored using both:
- Rule-based matching (existing logic)
- Taxonomy-informed domain matching (new)

## Usage Example

```python
from app.dashboard_agent.llm_agent import build_llm_layout_advisor_graph
from app.dashboard_agent.state import LayoutAdvisorState, Phase

# Upstream context with metrics and KPIs
upstream_context = {
    "use_case": "training compliance monitoring",
    "data_sources": ["cornerstone", "lms"],
    "persona": "Training Admin",
    "metrics": [
        {"name": "Training Completion Rate", "type": "percentage", "source_table": "training_completions"},
        {"name": "Assigned Trainings", "type": "count", "source_table": "training_assignments"},
        {"name": "Overdue Trainings", "type": "count", "source_table": "training_assignments"},
    ],
    "kpis": [
        {"label": "Total Completions", "value_expr": "SUM(completions)"},
        {"label": "Completion Rate", "value_expr": "completions / assigned"},
    ],
    "has_chat_requirement": False,
    "kpi_count": 4,
}

# Initialize state
state: LayoutAdvisorState = {
    "upstream_context": upstream_context,
    "messages": [],
    "phase": Phase.INTAKE,
    "decisions": {},
    "auto_resolved": {},
    "candidate_templates": [],
    "recommended_top3": [],
    "selected_template_id": "",
    "customization_requests": [],
    "layout_spec": {},
    "needs_user_input": False,
    "user_response": "",
    "error": "",
}

# The agent will:
# 1. Call match_domain_from_metrics_tool with the metrics/KPIs
# 2. Get recommendation: domain="ld_training", category=["hr_learning"], complexity="medium", theme="light"
# 3. Auto-populate decisions with these values
# 4. Score templates using the taxonomy-informed decisions
# 5. Recommend templates like "training-plan-tracker", "team-training-analytics"
```

## Taxonomy Matching Logic

The matcher scores domains based on:

1. **Goal Matching** (15-25 points)
   - If metric/KPI names contain domain goals (e.g., "training_completion")
   - If use case contains domain goals

2. **Focus Area Matching** (12-20 points)
   - If metrics align with domain focus areas (e.g., "learner_engagement")
   - If use case mentions focus areas

3. **Use Case Matching** (20 points)
   - Direct match between provided use case and domain use cases

4. **Data Source Matching** (15 points)
   - Maps data sources to domains:
     - "cornerstone"/"lms" → ld_training, ld_operations, ld_engagement
     - "workday" → hr_workforce, hr_learning
     - "siem" → security_operations, compliance
     - "qualys"/"snyk" → security_operations

5. **Keyword Matching** (5 points)
   - General keyword overlap in metric/KPI names

## Integration Points

### In `llm_agent.py`:

1. **System Prompt**: Updated to include taxonomy information and instructions
2. **Tool Binding**: `match_domain_from_metrics_tool` added to LAYOUT_TOOLS
3. **State Updates**: Auto-populates decisions when taxonomy tool is called
4. **Enhanced Context**: Adds taxonomy hints to upstream context

### In `tools.py`:

1. **New Tool**: `match_domain_from_metrics_tool` - matches metrics to domains
2. **Taxonomy Import**: Imports `get_domain_recommendations` from taxonomy_matcher

### New Module: `taxonomy_matcher.py`:

- `load_taxonomy()`: Loads enriched taxonomy from multiple possible locations
- `match_domain_from_metrics()`: Core matching logic
- `get_domain_recommendations()`: Returns top domains with recommendations

## Benefits

1. **Intelligent Recommendations**: Dashboards recommended based on actual metrics, not just user description
2. **Auto-Resolution**: Reduces conversation steps by auto-filling decisions from taxonomy
3. **Domain-Aware**: Understands differences between LMS dashboards and security dashboards
4. **Context-Aware**: Uses upstream metrics/KPIs to make informed recommendations

## Example Flow

```
User: "I need a dashboard for training compliance"

Upstream Context:
- metrics: [Training Completion Rate, Assigned Trainings, Overdue Trainings]
- kpis: [Total Completions, Completion Rate]
- use_case: "training compliance monitoring"
- data_sources: ["cornerstone", "lms"]

Agent Flow:
1. Calls match_domain_from_metrics_tool
   → Returns: domain="ld_training", score=85, reasons=["goal_match: training_completion", "data_source_match: cornerstone"]
   
2. Auto-populates decisions:
   - domain: "ld_training"
   - category: ["hr_learning"]
   - complexity: "medium"
   - theme: "light"

3. Scores templates with these decisions
   → Top matches: training-plan-tracker (95), team-training-analytics (88)

4. Recommends: "Based on your training metrics, I recommend the Training Plan Tracker dashboard..."
```
