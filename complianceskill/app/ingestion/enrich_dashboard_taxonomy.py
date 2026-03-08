"""
Dashboard Taxonomy Enrichment — LLM-Based Improvement
=======================================================
Uses LLM to improve and enrich the dashboard domain taxonomy with better
goals, categories, purposes, and mappings based on actual dashboard templates
and metrics.

The taxonomy is used for dashboard generation decision trees, similar to
how control_domain_taxonomy.json is used for control mapping.

This script enriches a taxonomy that was either:
1. Generated from dashboard data using generate_dashboard_taxonomy.py
2. Manually created or pre-existing

Usage:
    # Enrich a generated taxonomy
    python -m app.ingestion.enrich_dashboard_taxonomy \
        --input dashboard_domain_taxonomy.json \
        --output dashboard_domain_taxonomy_enriched.json \
        --templates-dir data/dashboard \
        --method llm
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


def load_dashboard_templates(templates_dir: Path) -> Dict[str, Any]:
    """Load all dashboard templates from registry files."""
    templates_dir = Path(templates_dir)
    
    all_templates = {}
    
    # Load ld_templates_registry.json
    ld_file = templates_dir / "ld_templates_registry.json"
    if ld_file.exists():
        data = load_json_file(ld_file)
        if data and "templates" in data:
            for template in data["templates"]:
                if isinstance(template, dict) and "id" in template:
                    all_templates[template["id"]] = template
    
    # Load templates_registry.json
    templates_file = templates_dir / "templates_registry.json"
    if templates_file.exists():
        data = load_json_file(templates_file)
        if data and "templates" in data:
            for template in data["templates"]:
                if isinstance(template, dict) and "id" in template:
                    all_templates[template["id"]] = template
    
    # Load lms_dashboard_metrics.json (extract dashboard metadata)
    lms_file = templates_dir / "lms_dashboard_metrics.json"
    if lms_file.exists():
        data = load_json_file(lms_file)
        if data and "dashboards" in data:
            for dashboard in data["dashboards"]:
                if isinstance(dashboard, dict) and "dashboard_id" in dashboard:
                    all_templates[dashboard["dashboard_id"]] = dashboard
    
    logger.info(f"Loaded {len(all_templates)} dashboard templates")
    return all_templates


def build_taxonomy_enrichment_prompt(
    taxonomy: Dict[str, Any],
    templates: Dict[str, Any],
) -> str:
    """Build the prompt for taxonomy enrichment."""
    
    prompt = f"""You are a dashboard taxonomy expert. Your task is to improve and enrich the dashboard domain taxonomy based on actual dashboard templates and metrics.

Current taxonomy:
{json.dumps(taxonomy, indent=2)}

Available dashboard templates (sample):
{json.dumps({k: v for k, v in list(templates.items())[:10]}, indent=2)}

For each domain in the taxonomy, improve:
1. Goals: More specific, actionable goals that dashboards in this domain serve
2. Focus areas: Better categorization of what dashboards focus on
3. Use cases: More concrete use case scenarios
4. Audience levels: More specific audience personas
5. Complexity: Validate or adjust complexity level
6. Theme preference: Validate or adjust theme preference

Also suggest:
- New domains if templates don't fit existing ones
- Better domain names/descriptions
- Missing goals or focus areas

Return JSON in this format:
{{
  "domains": {{
    "domain_id": {{
      "domain": "domain_id",
      "display_name": "Improved Display Name",
      "goals": ["goal1", "goal2", ...],
      "focus_areas": ["focus1", "focus2", ...],
      "use_cases": ["use_case1", "use_case2", ...],
      "audience_levels": ["audience1", "audience2", ...],
      "complexity": "low|medium|high",
      "theme_preference": "light|dark",
      "improvements": ["what was improved", ...]
    }},
    ...
  }},
  "new_domains": {{
    "new_domain_id": {{
      "domain": "new_domain_id",
      "display_name": "New Domain Name",
      "goals": [...],
      "focus_areas": [...],
      "use_cases": [...],
      "audience_levels": [...],
      "complexity": "medium",
      "theme_preference": "light",
      "rationale": "why this domain is needed"
    }}
  }},
  "summary": {{
    "total_domains": N,
    "domains_improved": N,
    "new_domains_added": N,
    "key_improvements": ["improvement1", "improvement2", ...]
  }}
}}"""
    
    return prompt


def enrich_taxonomy_llm(
    taxonomy: Dict[str, Any],
    templates: Dict[str, Any],
    llm,
    prompt_template: str,
) -> Dict[str, Any]:
    """Enrich taxonomy using LLM."""
    
    human_message = build_taxonomy_enrichment_prompt(taxonomy, templates)
    
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
        logger.error(f"Response content: {response_content[:500]}")
        return {}
    except Exception as e:
        logger.error(f"Error enriching taxonomy: {e}", exc_info=True)
        return {}


def merge_enriched_taxonomy(
    original: Dict[str, Any],
    enriched: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge LLM-enriched taxonomy back into original structure."""
    
    result = {
        "meta": original.get("meta", {}),
        **original
    }
    
    # Update meta
    result["meta"]["enriched"] = True
    result["meta"]["enrichment_method"] = "llm"
    
    # Merge domain improvements
    if "domains" in enriched:
        for domain_id, domain_data in enriched["domains"].items():
            if domain_id in result:
                # Merge improvements into existing domain
                original_domain = result[domain_id]
                original_domain.update({
                    "goals": domain_data.get("goals", original_domain.get("goals", [])),
                    "focus_areas": domain_data.get("focus_areas", original_domain.get("focus_areas", [])),
                    "use_cases": domain_data.get("use_cases", original_domain.get("use_cases", [])),
                    "audience_levels": domain_data.get("audience_levels", original_domain.get("audience_levels", [])),
                    "complexity": domain_data.get("complexity", original_domain.get("complexity", "medium")),
                    "theme_preference": domain_data.get("theme_preference", original_domain.get("theme_preference", "light")),
                })
                if domain_data.get("display_name"):
                    original_domain["display_name"] = domain_data["display_name"]
                if domain_data.get("improvements"):
                    original_domain["_improvements"] = domain_data["improvements"]
            else:
                # New domain
                result[domain_id] = domain_data
    
    # Add new domains
    if "new_domains" in enriched:
        for domain_id, domain_data in enriched["new_domains"].items():
            result[domain_id] = domain_data
    
    # Add summary
    if "summary" in enriched:
        result["_enrichment_summary"] = enriched["summary"]
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Enrich dashboard domain taxonomy using LLM"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to dashboard_domain_taxonomy.json (default: app/config/dashboard/dashboard_domain_taxonomy.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write enriched taxonomy (default: app/config/dashboard/dashboard_domain_taxonomy_enriched.json)"
    )
    parser.add_argument(
        "--templates-dir",
        type=str,
        default=None,
        help="Directory containing dashboard registry files (default: data/dashboard)"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["llm"],
        default="llm",
        help="Enrichment method (currently only llm supported)"
    )
    
    args = parser.parse_args()

    # Resolve paths with defaults
    try:
        from app.config.dashboard_paths import DASHBOARD_DATA_DIR, DASHBOARD_CONFIG_DIR
        taxonomy_path = Path(args.input) if args.input else DASHBOARD_CONFIG_DIR / "dashboard_domain_taxonomy.json"
        output_path = Path(args.output) if args.output else DASHBOARD_CONFIG_DIR / "dashboard_domain_taxonomy_enriched.json"
        templates_dir = Path(args.templates_dir) if args.templates_dir else DASHBOARD_DATA_DIR
    except ImportError:
        taxonomy_path = Path(args.input or "app/config/dashboard/dashboard_domain_taxonomy.json")
        output_path = Path(args.output or "app/config/dashboard/dashboard_domain_taxonomy_enriched.json")
        templates_dir = Path(args.templates_dir or "data/dashboard")
    
    # Load taxonomy
    if not taxonomy_path.exists():
        logger.error(f"Taxonomy file not found: {taxonomy_path}")
        sys.exit(1)
    
    taxonomy = load_json_file(taxonomy_path)
    if not taxonomy:
        logger.error("Failed to load taxonomy")
        sys.exit(1)
    
    # Remove meta from taxonomy for processing
    taxonomy_data = {k: v for k, v in taxonomy.items() if k != "meta"}
    
    # Load templates (templates_dir set above)
    if not templates_dir.exists():
        logger.error(f"Templates directory not found: {templates_dir}")
        sys.exit(1)
    
    templates = load_dashboard_templates(templates_dir)
    if not templates:
        logger.warning("No templates found, enrichment will be based on taxonomy only")
    
    # Load prompt template
    prompts_dir = Path(__file__).parent.parent / "agents" / "decision_trees" / "prompts"
    try:
        prompt_template = load_prompt("15_enrich_dashboard_taxonomy", prompts_dir=str(prompts_dir))
    except FileNotFoundError:
        # Fallback to default prompt if file doesn't exist
        prompt_template = """You are a dashboard taxonomy expert. Analyze the provided taxonomy and dashboard templates to improve goals, focus areas, use cases, and audience levels for each domain. Return JSON with improved taxonomy structure."""
        logger.warning("Using fallback prompt template (prompt file not found)")
    
    if not prompt_template:
        # Fallback to default prompt
        prompt_template = "You are a dashboard taxonomy expert. Analyze the provided taxonomy and dashboard templates to improve goals, focus areas, use cases, and audience levels for each domain."
        logger.warning("Using fallback prompt template")
    
    # Get LLM
    llm = get_llm(temperature=0)
    
    # Enrich taxonomy
    logger.info("Enriching taxonomy using LLM...")
    enriched = enrich_taxonomy_llm(
        taxonomy_data,
        templates,
        llm,
        prompt_template,
    )
    
    if not enriched:
        logger.error("LLM enrichment failed")
        sys.exit(1)
    
    # Merge back
    result = merge_enriched_taxonomy(taxonomy, enriched)
    
    # Save output (output_path set above)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"✓ Enriched taxonomy written to {output_path}")
    
    # Print summary
    if "_enrichment_summary" in result:
        summary = result["_enrichment_summary"]
        logger.info("\n" + "=" * 60)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total domains: {summary.get('total_domains', 0)}")
        logger.info(f"Domains improved: {summary.get('domains_improved', 0)}")
        logger.info(f"New domains added: {summary.get('new_domains_added', 0)}")
        if summary.get("key_improvements"):
            logger.info("\nKey improvements:")
            for improvement in summary["key_improvements"]:
                logger.info(f"  - {improvement}")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
