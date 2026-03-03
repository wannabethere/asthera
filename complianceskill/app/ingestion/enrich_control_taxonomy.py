"""
Control Taxonomy Enrichment — LLM-Powered Batch Processing

Uses LangChain with prompt 13_generate_control_taxonomy.md to enrich control taxonomy
for all controls across all frameworks in risk_control_yaml.

Processes controls in batches grouped by domain prefix to ensure proper differentiation
between sibling controls. Supports parallel processing of multiple frameworks in background.

Usage:
    # Process all frameworks in parallel
    python -m app.ingestion.enrich_control_taxonomy \
        --yaml-dir ../../data/cvedata/risk_control_yaml \
        --output-dir control_taxonomy_enriched \
        --batch-size 10 \
        --max-workers 3

    # Process single framework
    python -m app.ingestion.enrich_control_taxonomy \
        --yaml-dir ../../data/cvedata/risk_control_yaml \
        --framework soc2 \
        --output control_taxonomy_enriched_soc2.json \
        --batch-size 10
"""
import json
import logging
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from app.core.dependencies import get_llm
from app.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# ============================================================================
# YAML Loading
# ============================================================================

def load_yaml_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load and parse a YAML file, returning a list of items."""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data is None:
                return []
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # Some YAML files might have a root key
                return list(data.values()) if data else []
            return []
    except yaml.YAMLError as e:
        logger.error(f"YAML parse error in {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return []


def load_framework_data(yaml_dir: Path, framework_id: str) -> Dict[str, Any]:
    """Load all YAML files for a framework."""
    framework_dir = yaml_dir / framework_id
    
    if not framework_dir.exists():
        logger.warning(f"Framework directory not found: {framework_dir}")
        return {}
    
    # Find control and scenario files
    controls_file = None
    scenarios_file = None
    risk_controls_file = None
    
    for file_path in framework_dir.glob("*.yaml"):
        filename = file_path.name.lower()
        if "control" in filename and "risk" not in filename:
            controls_file = file_path
        elif "scenario" in filename:
            scenarios_file = file_path
        elif "risk_control" in filename:
            risk_controls_file = file_path
    
    if not controls_file:
        logger.warning(f"No controls file found for {framework_id}")
        return {}
    
    controls = load_yaml_file(controls_file)
    scenarios = load_yaml_file(scenarios_file) if scenarios_file else []
    risk_controls = load_yaml_file(risk_controls_file) if risk_controls_file else []
    
    logger.info(f"Loaded {len(controls)} controls, {len(scenarios)} scenarios, {len(risk_controls)} risk controls for {framework_id}")
    
    return {
        "controls": controls,
        "scenarios": scenarios,
        "risk_controls": risk_controls,
    }


# ============================================================================
# Data Preparation
# ============================================================================

def extract_control_code(control: Dict[str, Any]) -> str:
    """Extract control code from control dict."""
    return control.get("control_id") or control.get("code") or control.get("id", "")


def group_controls_by_domain(controls: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group controls by domain prefix (e.g., CC7.x, CC8.x)."""
    groups = defaultdict(list)
    
    for control in controls:
        code = extract_control_code(control)
        if not code:
            continue
        
        # Extract domain prefix (e.g., "CC7" from "CC7.1" or "164.308" from "164.308(a)(1)")
        parts = code.split(".")
        if len(parts) > 0:
            domain_prefix = parts[0]
            # For HIPAA-style codes like "164.308(a)(1)", use "164.308" as domain
            if "(" in domain_prefix:
                domain_prefix = domain_prefix.split("(")[0]
            groups[domain_prefix].append(control)
        else:
            groups[code].append(control)
    
    return dict(groups)


def find_associated_risks(
    control_code: str,
    scenarios: List[Dict[str, Any]],
    risk_controls: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find risks and scenarios associated with a control."""
    associated = []
    
    # Check scenarios
    for scenario in scenarios:
        mitigated_by = scenario.get("mitigated_by", [])
        if control_code in mitigated_by:
            associated.append({
                "risk_code": scenario.get("scenario_id", ""),
                "name": scenario.get("name", ""),
                "category": scenario.get("category", ""),
                "likelihood": scenario.get("likelihood", ""),
                "impact": scenario.get("impact", ""),
                "risk_indicators": scenario.get("loss_outcomes", []),
            })
    
    # Check risk_controls
    for risk_control in risk_controls:
        controls = risk_control.get("controls", [])
        for ctrl in controls:
            ctrl_id = ctrl.get("control_id") if isinstance(ctrl, dict) else str(ctrl)
            if ctrl_id == control_code:
                associated.append({
                    "risk_code": risk_control.get("scenario_id", ""),
                    "name": risk_control.get("name", ""),
                    "category": risk_control.get("category", ""),
                    "likelihood": risk_control.get("likelihood", ""),
                    "impact": risk_control.get("impact", ""),
                    "risk_indicators": risk_control.get("loss_outcomes", []),
                })
                break
    
    return associated


def find_associated_scenarios(
    control_code: str,
    scenarios: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find scenarios associated with a control."""
    associated = []
    
    for scenario in scenarios:
        mitigated_by = scenario.get("mitigated_by", [])
        affected_controls = scenario.get("affected_controls", [])
        
        if control_code in mitigated_by or control_code in affected_controls:
            associated.append({
                "scenario_id": scenario.get("scenario_id", ""),
                "name": scenario.get("name", ""),
                "severity": scenario.get("severity", ""),
                "observable_indicators": scenario.get("observable_indicators", []),
            })
    
    return associated


# ============================================================================
# LLM Processing
# ============================================================================

def build_taxonomy_prompt(
    framework_id: str,
    controls: List[Dict[str, Any]],
    associated_risks: List[Dict[str, Any]],
    associated_scenarios: List[Dict[str, Any]],
) -> str:
    """Build the human message for taxonomy generation."""
    
    # Valid identifiers
    valid_focus_areas = [
        "access_control", "audit_logging", "vulnerability_management",
        "incident_response", "change_management", "data_protection",
        "training_compliance", "identity_and_access", "endpoint_security",
        "vulnerability_and_configuration", "application_security",
        "cloud_and_infrastructure_security", "logging_and_detection",
        "data_security", "governance_risk_compliance",
        "change_and_release_management", "network_security",
        "threat_intelligence", "human_risk_and_training", "security_automation"
    ]
    
    valid_metric_types = ["count", "rate", "percentage", "score", "distribution", "comparison", "trend"]
    
    # Format controls with test_criteria if available
    controls_formatted = []
    for ctrl in controls:
        ctrl_formatted = {
            "code": extract_control_code(ctrl),
            "name": ctrl.get("name", ""),
            "description": ctrl.get("description", ""),
            "type": ctrl.get("type", ""),
        }
        # Add test_criteria if available
        if "test_criteria" in ctrl:
            ctrl_formatted["test_criteria"] = ctrl["test_criteria"]
        controls_formatted.append(ctrl_formatted)
    
    prompt = f"""framework_id: {framework_id}

controls[]:
{json.dumps(controls_formatted, indent=2)}

associated_risks[]:
{json.dumps(associated_risks, indent=2)}

associated_scenarios[]:
{json.dumps(associated_scenarios, indent=2)}

valid_focus_areas: {json.dumps(valid_focus_areas)}
valid_metric_types: {json.dumps(valid_metric_types)}

Generate taxonomy entries for all controls in the batch. Return JSON only."""
    
    return prompt


def generate_taxonomy_batch(
    framework_id: str,
    controls: List[Dict[str, Any]],
    scenarios: List[Dict[str, Any]],
    risk_controls: List[Dict[str, Any]],
    llm,
    prompt_template: str,
) -> List[Dict[str, Any]]:
    """Generate taxonomy for a batch of controls."""
    
    # Collect all associated risks and scenarios for controls in this batch
    all_associated_risks = []
    all_associated_scenarios = []
    
    for control in controls:
        control_code = extract_control_code(control)
        risks = find_associated_risks(control_code, scenarios, risk_controls)
        scenarios_list = find_associated_scenarios(control_code, scenarios)
        all_associated_risks.extend(risks)
        all_associated_scenarios.extend(scenarios_list)
    
    # Deduplicate
    seen_risk_codes = set()
    unique_risks = []
    for risk in all_associated_risks:
        risk_code = risk.get("risk_code", "")
        if risk_code and risk_code not in seen_risk_codes:
            seen_risk_codes.add(risk_code)
            unique_risks.append(risk)
    
    seen_scenario_ids = set()
    unique_scenarios = []
    for scenario in all_associated_scenarios:
        scenario_id = scenario.get("scenario_id", "")
        if scenario_id and scenario_id not in seen_scenario_ids:
            seen_scenario_ids.add(scenario_id)
            unique_scenarios.append(scenario)
    
    # Build prompt
    human_message = build_taxonomy_prompt(
        framework_id, controls, unique_risks, unique_scenarios
    )
    
    # Invoke LLM
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
        # Try to extract JSON from markdown code blocks if present
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
        return result.get("taxonomy_entries", [])
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Response content: {response_content[:500]}")
        return []
    except Exception as e:
        logger.error(f"Error generating taxonomy: {e}", exc_info=True)
        return []


# ============================================================================
# Main Processing
# ============================================================================

def enrich_framework_controls(
    yaml_dir: Path,
    framework_id: str,
    batch_size: int = 10,
    output_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """Enrich all controls for a framework."""
    
    start_time = time.time()
    logger.info(f"[{framework_id}] Starting enrichment...")
    
    # Load data
    framework_data = load_framework_data(yaml_dir, framework_id)
    if not framework_data:
        logger.warning(f"[{framework_id}] No framework data found")
        return {}
    
    controls = framework_data["controls"]
    scenarios = framework_data["scenarios"]
    risk_controls = framework_data["risk_controls"]
    
    if not controls:
        logger.warning(f"[{framework_id}] No controls found")
        return {}
    
    logger.info(f"[{framework_id}] Loaded {len(controls)} controls, {len(scenarios)} scenarios, {len(risk_controls)} risk controls")
    
    # Load prompt
    prompts_dir = Path(__file__).parent.parent / "agents" / "decision_trees" / "prompts"
    prompt_template = load_prompt("13_generate_control_taxonomy", prompts_dir=str(prompts_dir))
    
    # Get LLM
    llm = get_llm(temperature=0)
    
    # Group controls by domain
    domain_groups = group_controls_by_domain(controls)
    logger.info(f"[{framework_id}] Grouped {len(controls)} controls into {len(domain_groups)} domain groups")
    
    # Process each domain group in batches
    all_taxonomy_entries = []
    total_batches = sum((len(domain_controls) + batch_size - 1) // batch_size for domain_controls in domain_groups.values())
    batch_num = 0
    
    for domain_prefix, domain_controls in domain_groups.items():
        logger.info(f"[{framework_id}] Processing domain {domain_prefix} with {len(domain_controls)} controls")
        
        # Process in batches
        for i in range(0, len(domain_controls), batch_size):
            batch_num += 1
            batch = domain_controls[i:i + batch_size]
            batch_codes = [extract_control_code(c) for c in batch]
            logger.info(f"[{framework_id}] Batch {batch_num}/{total_batches}: {batch_codes}")
            
            try:
                taxonomy_entries = generate_taxonomy_batch(
                    framework_id, batch, scenarios, risk_controls, llm, prompt_template
                )
                
                if taxonomy_entries:
                    all_taxonomy_entries.extend(taxonomy_entries)
                    logger.info(f"[{framework_id}] Generated {len(taxonomy_entries)} taxonomy entries for batch {batch_num}")
                else:
                    logger.warning(f"[{framework_id}] No taxonomy entries generated for batch {batch_num}")
            except Exception as e:
                logger.error(f"[{framework_id}] Error in batch {batch_num}: {e}", exc_info=True)
                continue
    
    # Organize by framework
    result = {
        framework_id: {
            entry["control_code"]: entry
            for entry in all_taxonomy_entries
        }
    }
    
    # Save if output file specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        elapsed = time.time() - start_time
        logger.info(f"[{framework_id}] ✓ Saved {len(all_taxonomy_entries)} entries to {output_file} ({elapsed:.1f}s)")
    
    elapsed = time.time() - start_time
    logger.info(f"[{framework_id}] ✓ Completed in {elapsed:.1f}s")
    
    return result


def process_framework_wrapper(
    yaml_dir: Path,
    framework_id: str,
    batch_size: int,
    output_dir: Optional[Path],
) -> tuple[str, Dict[str, Any], Optional[str]]:
    """Wrapper for parallel processing of frameworks."""
    try:
        output_file = None
        if output_dir:
            output_file = output_dir / f"{framework_id}_enriched.json"
        else:
            output_file = Path(f"control_taxonomy_enriched_{framework_id}.json")
        
        result = enrich_framework_controls(
            yaml_dir, framework_id, batch_size, output_file
        )
        return framework_id, result, None
    except Exception as e:
        error_msg = f"Error processing {framework_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return framework_id, {}, error_msg


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enrich control taxonomy using LLM")
    parser.add_argument(
        "--yaml-dir",
        type=str,
        required=True,
        help="Path to risk_control_yaml directory"
    )
    parser.add_argument(
        "--framework",
        type=str,
        help="Framework ID to process (e.g., soc2, hipaa). If not specified, processes all frameworks"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (for single framework) or directory (for multiple frameworks)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for multiple frameworks (creates one file per framework)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of controls per batch (default: 10)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="Maximum number of parallel framework workers (default: 3)"
    )
    args = parser.parse_args()
    
    yaml_dir = Path(args.yaml_dir)
    if not yaml_dir.exists():
        logger.error(f"YAML directory not found: {yaml_dir}")
        sys.exit(1)
    
    # Determine frameworks to process
    if args.framework:
        frameworks = [args.framework]
    else:
        # Find all framework directories
        frameworks = [
            d.name for d in yaml_dir.iterdir()
            if d.is_dir() and d.name not in ["common"]
        ]
        logger.info(f"Found {len(frameworks)} frameworks: {frameworks}")
    
    # Determine output directory
    output_dir = None
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    elif args.output and len(frameworks) > 1:
        # If output is specified but multiple frameworks, treat as directory
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    all_results = {}
    errors = {}
    
    if len(frameworks) == 1:
        # Single framework - process directly
        framework_id = frameworks[0]
        output_file = None
        if args.output:
            output_file = Path(args.output)
        elif output_dir:
            output_file = output_dir / f"{framework_id}_enriched.json"
        else:
            output_file = Path(f"control_taxonomy_enriched_{framework_id}.json")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing framework: {framework_id}")
        logger.info(f"{'='*60}\n")
        
        try:
            result = enrich_framework_controls(
                yaml_dir, framework_id, args.batch_size, output_file
            )
            all_results.update(result)
        except Exception as e:
            logger.error(f"Error processing {framework_id}: {e}", exc_info=True)
            errors[framework_id] = str(e)
    else:
        # Multiple frameworks - process in parallel
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {len(frameworks)} frameworks in parallel (max {args.max_workers} workers)")
        logger.info(f"{'='*60}\n")
        
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all framework processing tasks
            future_to_framework = {
                executor.submit(
                    process_framework_wrapper,
                    yaml_dir,
                    framework_id,
                    args.batch_size,
                    output_dir,
                ): framework_id
                for framework_id in frameworks
            }
            
            # Process completed tasks as they finish
            completed = 0
            for future in as_completed(future_to_framework):
                framework_id = future_to_framework[future]
                completed += 1
                try:
                    fw_id, result, error = future.result()
                    if error:
                        errors[fw_id] = error
                    else:
                        all_results.update(result)
                    logger.info(f"[Progress] {completed}/{len(frameworks)} frameworks completed")
                except Exception as e:
                    error_msg = f"Unexpected error for {framework_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors[framework_id] = error_msg
    
    # Save combined results if requested
    if len(frameworks) > 1 and args.output and not output_dir:
        combined_output = Path(args.output)
        with open(combined_output, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2)
        logger.info(f"\nSaved combined results to {combined_output}")
    
    # Summary
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info("ENRICHMENT SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total frameworks: {len(frameworks)}")
    logger.info(f"Successfully processed: {len(all_results)}")
    logger.info(f"Errors: {len(errors)}")
    logger.info(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    
    if errors:
        logger.warning("\nFrameworks with errors:")
        for fw_id, error in errors.items():
            logger.warning(f"  {fw_id}: {error}")
    
    total_entries = sum(len(entries) for entries in all_results.values())
    logger.info(f"\nTotal taxonomy entries generated: {total_entries}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
