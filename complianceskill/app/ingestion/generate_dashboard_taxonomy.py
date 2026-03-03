"""
Generate Dashboard Taxonomy from Dashboard Data — LLM-Based Taxonomy Creation
==============================================================================
Analyzes actual dashboard templates and metrics to generate an initial dashboard
domain taxonomy. This taxonomy is then enriched using enrich_dashboard_taxonomy.py.

Uses LLM to analyze:
- ld_templates_registry.json: L&D dashboard templates
- lms_dashboard_metrics.json: LMS dashboard metrics
- templates_registry.json: Base security/compliance templates (optional)

The LLM identifies:
- Dashboard domains/categories
- Goals for each domain
- Focus areas
- Use cases
- Audience levels
- Complexity and theme preferences

Usage:
    python -m app.ingestion.generate_dashboard_taxonomy \
        --templates-dir app/dashboard_agent/registry_config \
        --output dashboard_domain_taxonomy.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def load_json_file(file_path: Path) -> Any:
    """Load a JSON file."""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None


def extract_dashboard_samples(templates_dir: Path, max_samples: int = 20) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract dashboard samples from registry files.
    
    Returns:
        Dictionary with keys: "ld_templates", "lms_dashboards", "base_templates"
    """
    templates_dir = Path(templates_dir)
    samples = {
        "ld_templates": [],
        "lms_dashboards": [],
        "base_templates": [],
    }
    
    # Load ld_templates_registry.json
    ld_file = templates_dir / "ld_templates_registry.json"
    if ld_file.exists():
        data = load_json_file(ld_file)
        if data and "templates" in data:
            templates = data["templates"][:max_samples]
            for template in templates:
                if isinstance(template, dict):
                    # Extract key fields for taxonomy generation
                    sample = {
                        "id": template.get("id", ""),
                        "name": template.get("name", ""),
                        "description": template.get("description", ""),
                        "category": template.get("category", ""),
                        "domains": template.get("domains", []),
                        "complexity": template.get("complexity", ""),
                        "best_for": template.get("best_for", []),
                        "chart_types": template.get("chart_types", []),
                        "primitives": template.get("primitives", []),
                        "theme_hint": template.get("theme_hint", ""),
                    }
                    samples["ld_templates"].append(sample)
            logger.info(f"Loaded {len(samples['ld_templates'])} L&D template samples")
    
    # Load lms_dashboard_metrics.json
    lms_file = templates_dir / "lms_dashboard_metrics.json"
    if lms_file.exists():
        data = load_json_file(lms_file)
        if data and "dashboards" in data:
            dashboards = data["dashboards"][:max_samples]
            for dashboard in dashboards:
                if isinstance(dashboard, dict):
                    # Extract key fields
                    sample = {
                        "dashboard_id": dashboard.get("dashboard_id", ""),
                        "dashboard_name": dashboard.get("dashboard_name", ""),
                        "dashboard_category": dashboard.get("dashboard_category", ""),
                        "description": dashboard.get("description", ""),
                        "layout_pattern": dashboard.get("layout_pattern", ""),
                        "metrics_count": len(dashboard.get("metrics", [])),
                        "metrics_sample": [
                            {
                                "id": m.get("id", ""),
                                "name": m.get("name", ""),
                                "type": m.get("type", ""),
                                "section": m.get("section", ""),
                                "chart_type": m.get("chart_type", ""),
                            }
                            for m in dashboard.get("metrics", [])[:10]  # First 10 metrics
                        ],
                    }
                    samples["lms_dashboards"].append(sample)
            logger.info(f"Loaded {len(samples['lms_dashboards'])} LMS dashboard samples")
    
    # Load templates_registry.json (optional, for security/compliance dashboards)
    templates_file = templates_dir / "templates_registry.json"
    if templates_file.exists():
        data = load_json_file(templates_file)
        if data and "templates" in data:
            templates = data["templates"][:max_samples]
            for template in templates:
                if isinstance(template, dict):
                    sample = {
                        "id": template.get("id", ""),
                        "name": template.get("name", ""),
                        "description": template.get("description", ""),
                        "category": template.get("category", ""),
                        "domains": template.get("domains", []),
                        "complexity": template.get("complexity", ""),
                        "best_for": template.get("best_for", []),
                        "primitives": template.get("primitives", []),
                        "theme_hint": template.get("theme_hint", ""),
                    }
                    samples["base_templates"].append(sample)
            logger.info(f"Loaded {len(samples['base_templates'])} base template samples")
    
    return samples


def build_taxonomy_generation_prompt(
    dashboard_samples: Dict[str, List[Dict[str, Any]]],
) -> str:
    """Build the prompt for taxonomy generation."""
    
    prompt = f"""You are a dashboard taxonomy expert. Your task is to analyze the provided dashboard templates and metrics to generate a comprehensive dashboard domain taxonomy.

The taxonomy will be used for dashboard generation decision trees, similar to how control domain taxonomies are used for compliance mapping.

## Dashboard Samples

### L&D Templates
{json.dumps(dashboard_samples.get("ld_templates", [])[:10], indent=2)}

### LMS Dashboards
{json.dumps(dashboard_samples.get("lms_dashboards", [])[:10], indent=2)}

### Base Templates (Security/Compliance)
{json.dumps(dashboard_samples.get("base_templates", [])[:10], indent=2)}

## Your Task

Analyze these dashboards and create a taxonomy that:

1. **Identifies Dashboard Domains**: Group dashboards into logical domains based on:
   - Category (e.g., "ld_training", "ld_operations", "security_operations", "compliance")
   - Purpose and use cases
   - Target audience
   - Data sources and systems

2. **For Each Domain, Define**:
   - `domain`: Unique domain identifier (snake_case, e.g., "ld_training", "security_operations")
   - `display_name`: Human-readable name
   - `goals`: List of 3-5 specific, actionable goals that dashboards in this domain serve
     - Examples: "training_completion", "incident_triage", "compliance_posture"
   - `focus_areas`: List of 3-5 specific focus areas/categories
     - Examples: "vulnerability_management", "learner_engagement", "vendor_analytics"
   - `use_cases`: List of 3-5 concrete use case scenarios
     - Examples: "lms_learning_target", "soc2_audit", "vendor_spend_analysis"
   - `audience_levels`: List of 3-5 target audience personas
     - Examples: "learning_admin", "security_ops", "l&d_director"
   - `complexity`: "low", "medium", or "high"
     - Low: Simple KPI dashboards, executive summaries
     - Medium: Standard operational dashboards with multiple charts
     - High: Complex multi-panel dashboards with drill-downs, graphs, AI chat
   - `theme_preference`: "light" or "dark"
     - Light: Compliance, executive, L&D dashboards (readability, reporting)
     - Dark: Security operations, SOC dashboards (reduced eye strain, alert focus)

## Output Format

Return a JSON object with this structure:

```json
{{
  "meta": {{
    "version": "1.0.0",
    "description": "Dashboard domain taxonomy for dashboard generation decision trees",
    "generated_from": "dashboard_templates_and_metrics",
    "generation_method": "llm_analysis"
  }},
  "domains": {{
    "domain_id": {{
      "domain": "domain_id",
      "display_name": "Display Name",
      "goals": ["goal1", "goal2", ...],
      "focus_areas": ["focus1", "focus2", ...],
      "use_cases": ["use_case1", "use_case2", ...],
      "audience_levels": ["audience1", "audience2", ...],
      "complexity": "low|medium|high",
      "theme_preference": "light|dark"
    }},
    ...
  }}
}}
```

## Guidelines

- **Be Comprehensive**: Cover all dashboard types you see in the samples
- **Be Specific**: Use domain-specific terminology, avoid generic terms
- **Be Actionable**: Goals and use cases should describe what users actually do
- **Be Consistent**: Use consistent naming conventions across domains
- **Group Logically**: Dashboards with similar purposes, audiences, or data sources should be in the same domain

## Examples

### Good Domain Structure
```json
{{
  "ld_training": {{
    "domain": "ld_training",
    "display_name": "Learning & Training",
    "goals": ["training_completion", "learner_analytics", "compliance_training"],
    "focus_areas": ["training_compliance", "learner_engagement", "certification_tracking"],
    "use_cases": ["lms_learning_target", "training_administration", "learner_profile"],
    "audience_levels": ["learning_admin", "training_coordinator", "team_manager"],
    "complexity": "medium",
    "theme_preference": "light"
  }}
}}
```

Generate the taxonomy now. Return JSON only."""
    
    return prompt


def generate_taxonomy_llm(
    dashboard_samples: Dict[str, List[Dict[str, Any]]],
    llm,
    prompt_template: str,
) -> Dict[str, Any]:
    """Generate taxonomy using LLM."""
    
    human_message = build_taxonomy_generation_prompt(dashboard_samples)
    
    try:
        system_prompt = prompt_template.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON response
        if "```json" in response_content:
            start = response_content.find("```json") + 7
            end = response_content.find("```", start)
            if end > start:
                response_content = response_content[start:end].strip()
        elif "```" in response_content:
            start = response_content.find("```") + 3
            end = response_content.find("```", start)
            if end > start:
                response_content = response_content[start:end].strip()
        
        result = json.loads(response_content)
        return result
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Response content: {response_content[:1000]}")
        return {}
    except Exception as e:
        logger.error(f"Error generating taxonomy: {e}", exc_info=True)
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="Generate dashboard domain taxonomy from dashboard data using LLM"
    )
    parser.add_argument(
        "--templates-dir",
        type=str,
        required=True,
        help="Directory containing dashboard registry files (ld_templates_registry.json, lms_dashboard_metrics.json, templates_registry.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to write generated taxonomy (dashboard_domain_taxonomy.json)"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=20,
        help="Maximum number of dashboard samples to analyze per source (default: 20)"
    )
    
    args = parser.parse_args()
    
    # Load dashboard samples
    templates_dir = Path(args.templates_dir)
    if not templates_dir.exists():
        logger.error(f"Templates directory not found: {templates_dir}")
        sys.exit(1)
    
    logger.info("Extracting dashboard samples...")
    dashboard_samples = extract_dashboard_samples(templates_dir, max_samples=args.max_samples)
    
    total_samples = (
        len(dashboard_samples["ld_templates"]) +
        len(dashboard_samples["lms_dashboards"]) +
        len(dashboard_samples["base_templates"])
    )
    
    if total_samples == 0:
        logger.error("No dashboard samples found in registry files")
        sys.exit(1)
    
    logger.info(f"Total dashboard samples: {total_samples}")
    logger.info(f"  - L&D templates: {len(dashboard_samples['ld_templates'])}")
    logger.info(f"  - LMS dashboards: {len(dashboard_samples['lms_dashboards'])}")
    logger.info(f"  - Base templates: {len(dashboard_samples['base_templates'])}")
    
    # Load prompt template
    prompts_dir = Path(__file__).parent.parent / "agents" / "decision_trees" / "prompts"
    try:
        prompt_template = load_prompt("16_generate_dashboard_taxonomy", prompts_dir=str(prompts_dir))
    except FileNotFoundError:
        # Fallback to default prompt
        prompt_template = """You are a dashboard taxonomy expert. Analyze the provided dashboard templates and metrics to generate a comprehensive dashboard domain taxonomy. Group dashboards into logical domains and define goals, focus areas, use cases, and audience levels for each domain."""
        logger.warning("Using fallback prompt template (prompt file not found)")
    
    # Get LLM
    llm = get_llm(temperature=0)
    
    # Generate taxonomy
    logger.info("Generating taxonomy using LLM...")
    taxonomy = generate_taxonomy_llm(
        dashboard_samples,
        llm,
        prompt_template,
    )
    
    if not taxonomy or "domains" not in taxonomy:
        logger.error("LLM taxonomy generation failed or returned invalid structure")
        sys.exit(1)
    
    # Ensure meta exists
    if "meta" not in taxonomy:
        taxonomy["meta"] = {
            "version": "1.0.0",
            "description": "Dashboard domain taxonomy for dashboard generation decision trees",
            "generated_from": "dashboard_templates_and_metrics",
            "generation_method": "llm_analysis"
        }
    
    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2)
    
    logger.info(f"✓ Generated taxonomy with {len(taxonomy.get('domains', {}))} domains")
    logger.info(f"✓ Written to {output_path}")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("GENERATED TAXONOMY SUMMARY")
    logger.info("=" * 60)
    for domain_id, domain_data in taxonomy.get("domains", {}).items():
        display_name = domain_data.get("display_name", domain_id)
        goals_count = len(domain_data.get("goals", []))
        use_cases_count = len(domain_data.get("use_cases", []))
        complexity = domain_data.get("complexity", "medium")
        logger.info(f"\n{display_name} ({domain_id})")
        logger.info(f"  Goals: {goals_count}, Use cases: {use_cases_count}, Complexity: {complexity}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
