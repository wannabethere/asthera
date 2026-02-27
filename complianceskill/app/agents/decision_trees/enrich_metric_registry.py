"""
Metric Registry Enrichment — Unified Script

Enriches metrics registry with decision-tree fields using either:
1. Rule-based inference (fast, deterministic)
2. LLM-based enrichment (context-aware, more accurate)

Supports both approaches and can combine them (rule-based as fallback/initial pass,
LLM as refinement). Can process multiple metrics registry files in parallel.

Usage:
    # Process all metrics files in a directory (parallel)
    python -m app.agents.decision_trees.enrich_metric_registry \
        --input-dir path/to/metrics_registries \
        --output-dir path/to/enriched \
        --method rule-based \
        --max-workers 3

    # Process single file
    python -m app.agents.decision_trees.enrich_metric_registry \
        --input metrics_registry.json \
        --output metrics_registry_enriched.json \
        --method rule-based

    # LLM-based with context
    python -m app.agents.decision_trees.enrich_metric_registry \
        --input metrics_registry.json \
        --output metrics_registry_enriched.json \
        --method llm \
        --control-taxonomy control_taxonomy_enriched.json
"""
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# ============================================================================
# Rule-based Inference Rules
# ============================================================================

CATEGORY_TO_FOCUS_AREAS: Dict[str, List[str]] = {
    "vulnerabilities":      ["vulnerability_management"],
    "patch_compliance":     ["vulnerability_management"],
    "cve_exposure":         ["vulnerability_management"],
    "access_control":       ["access_control"],
    "authentication":       ["access_control"],
    "mfa_adoption":         ["access_control"],
    "audit_logging":        ["audit_logging"],
    "siem_events":          ["audit_logging"],
    "compliance_events":    ["audit_logging"],
    "incidents":            ["incident_response"],
    "mttr":                 ["incident_response"],
    "alert_volume":         ["incident_response"],
    "cloud_findings":       ["vulnerability_management"],
    "misconfigs":           ["vulnerability_management"],
    "endpoint_events":      ["incident_response"],
    "edr_alerts":           ["incident_response"],
    "network_events":       ["incident_response"],
    "anomalies":            ["incident_response"],
    "data_assets":          ["data_protection"],
    "classification":       ["data_protection"],
    "training_compliance":  ["training_compliance"],
    "certification":        ["training_compliance"],
    "detection_engineering": ["incident_response", "vulnerability_management"],
}

CATEGORY_TO_GOALS: Dict[str, List[str]] = {
    "vulnerabilities":      ["risk_exposure", "compliance_posture", "remediation_velocity"],
    "patch_compliance":     ["remediation_velocity", "compliance_posture"],
    "cve_exposure":         ["risk_exposure"],
    "access_control":       ["compliance_posture", "control_effectiveness"],
    "authentication":       ["control_effectiveness", "compliance_posture"],
    "mfa_adoption":         ["control_effectiveness"],
    "audit_logging":        ["compliance_posture"],
    "siem_events":          ["incident_triage", "compliance_posture"],
    "compliance_events":    ["compliance_posture"],
    "incidents":            ["incident_triage"],
    "mttr":                 ["incident_triage", "remediation_velocity"],
    "alert_volume":         ["incident_triage"],
    "cloud_findings":       ["risk_exposure", "compliance_posture"],
    "misconfigs":           ["risk_exposure"],
    "endpoint_events":      ["incident_triage"],
    "edr_alerts":           ["incident_triage"],
    "training_compliance":  ["training_completion", "compliance_posture"],
    "certification":        ["training_completion"],
    "detection_engineering": ["control_effectiveness", "incident_triage"],
}

CATEGORY_TO_GROUP_AFFINITY: Dict[str, List[str]] = {
    "vulnerabilities":      ["risk_exposure", "compliance_posture", "remediation_velocity"],
    "patch_compliance":     ["remediation_velocity", "compliance_posture"],
    "cve_exposure":         ["risk_exposure"],
    "access_control":       ["compliance_posture", "control_effectiveness"],
    "authentication":       ["control_effectiveness"],
    "mfa_adoption":         ["control_effectiveness"],
    "audit_logging":        ["compliance_posture"],
    "siem_events":          ["operational_security", "compliance_posture"],
    "compliance_events":    ["compliance_posture"],
    "incidents":            ["operational_security"],
    "mttr":                 ["operational_security", "remediation_velocity"],
    "alert_volume":         ["operational_security"],
    "cloud_findings":       ["risk_exposure"],
    "misconfigs":           ["risk_exposure"],
    "endpoint_events":      ["operational_security"],
    "edr_alerts":           ["operational_security"],
    "training_compliance":  ["training_completion"],
    "certification":        ["training_completion"],
    "detection_engineering": ["control_effectiveness", "operational_security"],
}

SOURCE_TO_USE_CASES: Dict[str, List[str]] = {
    "qualys":      ["soc2_audit", "risk_posture_report", "operational_monitoring"],
    "snyk":        ["soc2_audit", "risk_posture_report"],
    "wiz":         ["soc2_audit", "risk_posture_report", "operational_monitoring"],
    "okta":        ["soc2_audit", "executive_dashboard"],
    "crowdstrike": ["soc2_audit", "operational_monitoring"],
    "splunk":      ["soc2_audit", "operational_monitoring"],
    "sentinel":    ["soc2_audit", "operational_monitoring"],
    "cornerstone": ["lms_learning_target"],
    "sumtotal":    ["lms_learning_target"],
}

FOCUS_TO_CONTROL_DOMAINS: Dict[str, List[str]] = {
    "access_control":           ["CC6"],
    "audit_logging":            ["CC7"],
    "vulnerability_management": ["CC7", "CC8"],
    "incident_response":        ["CC7"],
    "change_management":        ["CC8"],
    "data_protection":          ["CC6", "CC9"],
    "training_compliance":      ["CC1", "CC2"],
}

FOCUS_TO_RISK_CATEGORIES: Dict[str, List[str]] = {
    "access_control":           ["unauthorized_access", "privilege_escalation"],
    "audit_logging":            ["undetected_breach", "log_tampering"],
    "vulnerability_management": ["unpatched_systems", "cve_exposure"],
    "incident_response":        ["delayed_response", "uncontained_breach"],
    "change_management":        ["unauthorized_changes", "configuration_drift"],
    "data_protection":          ["data_leak", "classification_gap"],
    "training_compliance":      ["untrained_staff", "compliance_gap"],
}


# ============================================================================
# Rule-based Type Inference
# ============================================================================

def _infer_metric_type(metric: Dict) -> str:
    """Infer metric_type from existing fields."""
    name = (metric.get("name") or "").lower()
    description = (metric.get("description") or "").lower()
    kpis = [str(k).lower() for k in metric.get("kpis", [])]
    text = f"{name} {description} {' '.join(kpis)}"

    if any(w in text for w in ["percentage", "percent", "%", "ratio", "proportion", "rate of"]):
        return "percentage"
    if any(w in text for w in ["score", "index", "composite", "weighted"]):
        return "score"
    if any(w in text for w in ["rate", "velocity", "per day", "per hour", "mttr", "mttd"]):
        return "rate"
    if any(w in text for w in ["distribution", "breakdown", "by severity", "by category"]):
        return "distribution"
    if any(w in text for w in ["trend", "over time", "historical"]):
        return "trend"
    if any(w in text for w in ["count", "total", "number of", "volume", "how many"]):
        return "count"

    return "count"  # default


def _infer_aggregation_windows(metric: Dict) -> List[str]:
    """Infer aggregation_windows from existing fields."""
    trends = metric.get("trends", [])
    if trends:
        windows = ["daily", "weekly"]
        for t in trends:
            t_lower = str(t).lower()
            if "month" in t_lower:
                windows.append("monthly")
            if "quarter" in t_lower:
                windows.append("quarterly")
        return list(set(windows))

    return ["daily", "weekly", "monthly"]  # default


def _infer_audience_levels(focus_areas: List[str], goals: List[str]) -> List[str]:
    """Infer audience_levels from focus areas and goals."""
    audiences = set()

    if "compliance_posture" in goals:
        audiences.update(["compliance_team", "auditor"])
    if "risk_exposure" in goals:
        audiences.update(["risk_management", "executive_board"])
    if "incident_triage" in goals:
        audiences.add("security_ops")
    if "training_completion" in goals:
        audiences.add("learning_admin")
    if "control_effectiveness" in goals:
        audiences.update(["compliance_team", "security_ops"])
    if "remediation_velocity" in goals:
        audiences.update(["security_ops", "compliance_team"])

    if not audiences:
        audiences = {"compliance_team"}

    return sorted(audiences)


# ============================================================================
# Rule-based Enrichment
# ============================================================================

def enrich_metric_rule_based(metric: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add decision-tree fields to a single metric entry using rule-based inference.

    Preserves all existing fields and adds:
        goals, focus_areas, use_cases, audience_levels, metric_type,
        aggregation_windows, mapped_control_domains, mapped_risk_categories,
        group_affinity
    """
    # Validate input
    if not isinstance(metric, dict):
        logger.error(f"enrich_metric_rule_based: Expected dict, got {type(metric)}: {str(metric)[:100]}")
        raise ValueError(f"Metric must be a dictionary, got {type(metric)}")
    
    enriched = dict(metric)
    category = metric.get("category", "")

    # focus_areas
    focus_areas = CATEGORY_TO_FOCUS_AREAS.get(category, [])
    enriched.setdefault("focus_areas", focus_areas)

    # goals
    goals = CATEGORY_TO_GOALS.get(category, ["compliance_posture"])
    enriched.setdefault("goals", goals)

    # group_affinity
    group_affinity = CATEGORY_TO_GROUP_AFFINITY.get(category, ["compliance_posture"])
    enriched.setdefault("group_affinity", group_affinity)

    # use_cases from source_capabilities
    source_caps = metric.get("source_capabilities", [])
    use_cases = set()
    for cap in source_caps:
        prefix = str(cap).split(".")[0].lower()
        for src_key, src_use_cases in SOURCE_TO_USE_CASES.items():
            if prefix.startswith(src_key) or src_key.startswith(prefix):
                use_cases.update(src_use_cases)
    if not use_cases:
        use_cases = {"soc2_audit"}  # default
    enriched.setdefault("use_cases", sorted(use_cases))

    # mapped_control_domains
    control_domains = set()
    for fa in focus_areas:
        control_domains.update(FOCUS_TO_CONTROL_DOMAINS.get(fa, []))
    enriched.setdefault("mapped_control_domains", sorted(control_domains))

    # mapped_risk_categories
    risk_categories = set()
    for fa in focus_areas:
        risk_categories.update(FOCUS_TO_RISK_CATEGORIES.get(fa, []))
    enriched.setdefault("mapped_risk_categories", sorted(risk_categories))

    # metric_type
    enriched.setdefault("metric_type", _infer_metric_type(metric))

    # aggregation_windows
    enriched.setdefault("aggregation_windows", _infer_aggregation_windows(metric))

    # audience_levels
    enriched.setdefault("audience_levels", _infer_audience_levels(focus_areas, goals))

    return enriched


# ============================================================================
# LLM-based Enrichment (from enrich_metric_attributes.py)
# ============================================================================

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


def load_control_taxonomy(
    taxonomy_path: Path,
    framework_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Load enriched control taxonomy.
    
    Args:
        taxonomy_path: Path to taxonomy JSON file
        framework_id: Optional framework ID to extract (if file contains multiple frameworks)
    
    Returns:
        Dictionary of control_code -> taxonomy_entry
    """
    data = load_json_file(taxonomy_path)
    if not data:
        return {}
    
    # If framework_id is specified and data has framework structure, extract only that framework
    if framework_id and isinstance(data, dict):
        # Check if data is organized by framework (e.g., {"soc2": {...}, "hipaa": {...}})
        if framework_id in data and isinstance(data[framework_id], dict):
            framework_controls = data[framework_id]
            logger.info(f"Loaded {len(framework_controls)} control taxonomy entries for {framework_id} from {taxonomy_path.name}")
            return framework_controls
    
    # Flatten framework structure (for combined files or single framework files)
    all_controls = {}
    for fw_id, framework_controls in data.items():
        if isinstance(framework_controls, dict):
            # Check if this is a control entry (has control_code) or a framework container
            if any("control_code" in v for v in framework_controls.values() if isinstance(v, dict)):
                # This is a framework container with control entries
                all_controls.update(framework_controls)
            elif isinstance(framework_controls, dict) and len(framework_controls) > 0:
                # Check if values are control entries
                first_value = next(iter(framework_controls.values()))
                if isinstance(first_value, dict) and "control_code" in first_value:
                    all_controls.update(framework_controls)
    
    logger.info(f"Loaded {len(all_controls)} control taxonomy entries from {taxonomy_path.name}")
    return all_controls


def find_control_taxonomy_file(
    taxonomy_path_or_dir: Path,
    framework_id: str,
) -> Optional[Path]:
    """
    Find control taxonomy file for a specific framework.
    
    Supports:
    - Single file path (returns as-is)
    - Directory with pattern: {framework_id}_enriched.json
    - Directory with pattern: control_taxonomy_enriched_{framework_id}.json
    - Combined file with all frameworks (extracts framework-specific entries)
    
    Args:
        taxonomy_path_or_dir: Path to taxonomy file or directory
        framework_id: Framework ID to match
    
    Returns:
        Path to taxonomy file, or None if not found
    """
    if not taxonomy_path_or_dir.exists():
        return None
    
    # If it's a file, return it
    if taxonomy_path_or_dir.is_file():
        return taxonomy_path_or_dir
    
    # If it's a directory, look for framework-specific files
    if taxonomy_path_or_dir.is_dir():
        # Try common patterns
        patterns = [
            f"{framework_id}_enriched.json",
            f"control_taxonomy_enriched_{framework_id}.json",
            f"{framework_id}_control_taxonomy_enriched.json",
        ]
        
        for pattern in patterns:
            candidate = taxonomy_path_or_dir / pattern
            if candidate.exists():
                return candidate
        
        # Try to find any file containing the framework_id
        for file_path in taxonomy_path_or_dir.glob("*.json"):
            if framework_id in file_path.stem.lower():
                return file_path
        
        # If no framework-specific file found, look for combined file
        combined_patterns = [
            "control_taxonomy_enriched.json",
            "*enriched*.json",
        ]
        for pattern in combined_patterns:
            for file_path in taxonomy_path_or_dir.glob(pattern):
                # Check if this file contains the framework
                data = load_json_file(file_path)
                if data and framework_id in data:
                    return file_path
    
    return None


def load_use_case_groups(groups_path: Path) -> List[Dict[str, Any]]:
    """Load use case metric groups."""
    data = load_json_file(groups_path)
    if not data:
        return []
    
    # Handle different structures
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        if "groups" in data:
            return data["groups"]
        # Try to extract from framework structure
        all_groups = []
        for value in data.values():
            if isinstance(value, list):
                all_groups.extend(value)
            elif isinstance(value, dict) and "groups" in value:
                all_groups.extend(value["groups"])
        return all_groups
    
    return []


def prepare_compliance_context(
    control_taxonomy: Dict[str, Dict[str, Any]],
    use_case_groups: List[Dict[str, Any]],
    use_case: str = "soc2_audit",
    framework_id: str = "soc2",
) -> Dict[str, Any]:
    """Prepare compliance context for metric enrichment."""
    
    # Extract controls from taxonomy
    controls = []
    for control_code, taxonomy_entry in control_taxonomy.items():
        controls.append({
            "code": control_code,
            "name": taxonomy_entry.get("sub_domain", ""),
            "type": taxonomy_entry.get("control_type_classification", {}).get("type", ""),
            "description": taxonomy_entry.get("measurement_goal", ""),
            "measurement_goal": taxonomy_entry.get("measurement_goal", ""),
            "affinity_keywords": taxonomy_entry.get("affinity_keywords", []),
            "evidence_requirements": taxonomy_entry.get("evidence_requirements", {}),
        })
    
    # Extract risks from taxonomy (if available)
    risks = []
    for taxonomy_entry in control_taxonomy.values():
        risk_categories = taxonomy_entry.get("risk_categories", [])
        for category in risk_categories:
            risks.append({
                "risk_code": f"R-{category}",
                "name": category.replace("_", " ").title(),
                "category": category,
                "likelihood": "",
                "impact": "",
                "risk_indicators": [],
            })
    
    # Extract scenarios (minimal - would need full scenario data)
    scenarios = []
    
    # Filter use case groups by use_case
    available_groups = [
        group for group in use_case_groups
        if group.get("use_case") == use_case or not use_case
    ]
    
    return {
        "controls": controls,
        "risks": risks,
        "scenarios": scenarios,
        "available_groups": available_groups,
    }


def build_metric_enrichment_prompt(
    use_case: str,
    framework_id: str,
    metrics: List[Dict[str, Any]],
    compliance_context: Dict[str, Any],
) -> str:
    """Build the human message for metric enrichment."""
    
    prompt = f"""use_case: {use_case}
framework_id: {framework_id}

metrics[]:
{json.dumps(metrics, indent=2)}

controls[]:
{json.dumps(compliance_context["controls"], indent=2)}

risks[]:
{json.dumps(compliance_context["risks"], indent=2)}

scenarios[]:
{json.dumps(compliance_context["scenarios"], indent=2)}

available_groups[]:
{json.dumps(compliance_context["available_groups"], indent=2)}

Enrich metric attributes for all metrics in the batch. Return JSON only."""
    
    return prompt


def enrich_metrics_batch_llm(
    use_case: str,
    framework_id: str,
    metrics: List[Dict[str, Any]],
    compliance_context: Dict[str, Any],
    llm,
    prompt_template: str,
) -> List[Dict[str, Any]]:
    """Enrich a batch of metrics using LLM."""
    
    human_message = build_metric_enrichment_prompt(
        use_case, framework_id, metrics, compliance_context
    )
    
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
        return result.get("enrichments", [])
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Response content: {response_content[:500]}")
        return []
    except Exception as e:
        logger.error(f"Error enriching metrics: {e}", exc_info=True)
        return []


# ============================================================================
# Unified Processing
# ============================================================================

def load_metrics_registry(registry_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load metrics from registry JSON file, return (metrics_list, original_structure)."""
    data = load_json_file(registry_path)
    if not data:
        return [], {}
    
    metrics = []
    original_structure = {}
    
    # Handle different registry structures
    if isinstance(data, list):
        # Filter to only include dict items (skip non-dict entries)
        metrics = [item for item in data if isinstance(item, dict)]
        original_structure = {"metrics": metrics}
        if len(metrics) < len(data):
            logger.warning(f"Filtered out {len(data) - len(metrics)} non-dict entries from list")
    elif isinstance(data, dict):
        original_structure = data
        
        # Priority 1: Check for direct metrics key (most common structure)
        # Structure: {"metrics": [...]} or {"metrics": {...}}
        if "metrics" in data:
            metrics_data = data["metrics"]
            if isinstance(metrics_data, list):
                # Filter to only include dict items
                metrics = [m for m in metrics_data if isinstance(m, dict)]
                if len(metrics) < len(metrics_data):
                    logger.warning(f"Filtered out {len(metrics_data) - len(metrics)} non-dict entries from metrics list")
            elif isinstance(metrics_data, dict):
                # If metrics is a dict, try to extract values
                metrics = [m for m in metrics_data.values() if isinstance(m, dict)]
            else:
                logger.warning(f"Unexpected metrics type: {type(metrics_data)}, expected list or dict")
        
        # Priority 2: Check for dashboards structure (LMS format)
        # Structure: {"dashboards": [{"dashboard_id": "...", "metrics": [...]}]}
        elif "dashboards" in data:
            dashboards = data["dashboards"]
            if isinstance(dashboards, list):
                for dashboard in dashboards:
                    if isinstance(dashboard, dict) and "metrics" in dashboard:
                        dashboard_metrics = dashboard["metrics"]
                        if isinstance(dashboard_metrics, list):
                            valid_metrics = [m for m in dashboard_metrics if isinstance(m, dict)]
                            metrics.extend(valid_metrics)
                            if len(valid_metrics) < len(dashboard_metrics):
                                logger.warning(f"Filtered out {len(dashboard_metrics) - len(valid_metrics)} non-dict entries from dashboard {dashboard.get('dashboard_id', 'unknown')}")
        
        # Priority 3: Check for categories structure
        # Structure: {"categories": {"category_id": {"metrics": [...]}}} or {"categories": [{"metrics": [...]}]}
        # Note: categories can also be a list of strings (category names), which we skip
        elif "categories" in data:
            categories_data = data["categories"]
            # Handle both dict and list structures for categories
            if isinstance(categories_data, dict):
                for category_id, category_data in categories_data.items():
                    if isinstance(category_data, dict) and "metrics" in category_data:
                        category_metrics = category_data["metrics"]
                        if isinstance(category_metrics, list):
                            # Filter to only include dict items
                            valid_metrics = [m for m in category_metrics if isinstance(m, dict)]
                            metrics.extend(valid_metrics)
                            if len(valid_metrics) < len(category_metrics):
                                logger.warning(f"Filtered out {len(category_metrics) - len(valid_metrics)} non-dict entries from category {category_id}")
            elif isinstance(categories_data, list):
                # Check if this is a list of category objects with metrics, or just category names (strings)
                if categories_data and isinstance(categories_data[0], dict):
                    # List of category objects
                    for category_entry in categories_data:
                        if isinstance(category_entry, dict):
                            if "metrics" in category_entry:
                                category_metrics = category_entry["metrics"]
                                if isinstance(category_metrics, list):
                                    valid_metrics = [m for m in category_metrics if isinstance(m, dict)]
                                    metrics.extend(valid_metrics)
                            # Also check if the category entry itself contains metric fields
                            elif "id" in category_entry or "name" in category_entry:
                                metrics.append(category_entry)
                # If categories is a list of strings (category names), skip it - metrics should be in "metrics" key
                elif categories_data and isinstance(categories_data[0], str):
                    logger.debug(f"Categories is a list of strings (category names), not extracting metrics from it")
            else:
                logger.warning(f"Unexpected categories type: {type(categories_data)}, expected dict or list")
        
        # Priority 4: Otherwise, assume flat structure with metric entries
        else:
            # Try to extract metrics from values
            for key, value in data.items():
                if isinstance(value, list):
                    # Filter to only include dict items
                    valid_metrics = [m for m in value if isinstance(m, dict)]
                    metrics.extend(valid_metrics)
                elif isinstance(value, dict):
                    if "metrics" in value:
                        metrics_list = value["metrics"]
                        if isinstance(metrics_list, list):
                            valid_metrics = [m for m in metrics_list if isinstance(m, dict)]
                            metrics.extend(valid_metrics)
                    # Also check if the value itself is a metric (has 'id' or 'name')
                    elif "id" in value or "name" in value:
                        metrics.append(value)
    
    # Final validation: ensure all metrics are dicts
    validated_metrics = []
    for i, metric in enumerate(metrics):
        if isinstance(metric, dict):
            validated_metrics.append(metric)
        else:
            logger.warning(f"Skipping non-dict metric at index {i}: {type(metric)} - {str(metric)[:100]}")
    
    logger.info(f"Loaded {len(validated_metrics)} valid metrics from registry (filtered from {len(metrics)} total items)")
    return validated_metrics, original_structure


def enrich_registry(
    registry_path: Path,
    method: str = "rule-based",
    control_taxonomy_path: Optional[Path] = None,
    control_taxonomy_dir: Optional[Path] = None,
    use_case_groups_path: Optional[Path] = None,
    use_case: str = "soc2_audit",
    framework_id: str = "soc2",
    batch_size: int = 10,
) -> Dict[str, Any]:
    """
    Enrich all metrics in a registry structure.

    Args:
        registry_path: Path to metrics registry JSON
        method: "rule-based", "llm", or "hybrid"
        control_taxonomy_path: Optional path to enriched control taxonomy
        use_case_groups_path: Optional path to use case groups
        use_case: Use case identifier
        framework_id: Framework ID
        batch_size: Batch size for LLM processing
    
    Returns:
        Enriched registry structure
    """
    # Load metrics
    metrics, original_structure = load_metrics_registry(registry_path)
    if not metrics:
        logger.error("No metrics found in registry")
        return {}
    
    enriched_metrics = []
    
    if method == "rule-based":
        # Rule-based only
        logger.info("Using rule-based enrichment")
        for i, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                logger.warning(f"Skipping invalid metric at index {i}: expected dict, got {type(metric)}")
                continue
            try:
                enriched_metrics.append(enrich_metric_rule_based(metric))
            except Exception as e:
                logger.error(f"Error enriching metric at index {i}: {e}", exc_info=True)
                # Skip this metric but continue processing
                continue
    
    elif method == "llm":
        # LLM-based only
        logger.info("Using LLM-based enrichment")
        
        # Load compliance context
        control_taxonomy = {}
        if control_taxonomy_path:
            control_taxonomy = load_control_taxonomy(control_taxonomy_path, framework_id=framework_id)
        elif control_taxonomy_dir:
            # Find framework-specific taxonomy file
            framework_taxonomy_path = find_control_taxonomy_file(
                control_taxonomy_dir, framework_id
            )
            if framework_taxonomy_path:
                control_taxonomy = load_control_taxonomy(framework_taxonomy_path, framework_id=framework_id)
                logger.info(f"Using taxonomy file: {framework_taxonomy_path.name} for framework {framework_id}")
            else:
                logger.warning(f"No taxonomy file found for framework {framework_id} in {control_taxonomy_dir}")
        
        use_case_groups = []
        if use_case_groups_path:
            use_case_groups = load_use_case_groups(use_case_groups_path)
        
        compliance_context = prepare_compliance_context(
            control_taxonomy, use_case_groups, use_case, framework_id
        )
        
        # Load prompt
        prompts_dir = Path(__file__).parent / "prompts"
        prompt_template = load_prompt("14_enrich_metric_attributes", prompts_dir=str(prompts_dir))
        
        # Get LLM
        llm = get_llm(temperature=0)
        
        # Process metrics in batches
        all_enrichments = {}
        total_batches = (len(metrics) + batch_size - 1) // batch_size
        
        for i in range(0, len(metrics), batch_size):
            batch = metrics[i:i + batch_size]
            batch_num = i // batch_size + 1
            batch_ids = [m.get("id", "") for m in batch]
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} metrics): {batch_ids[:3]}{'...' if len(batch_ids) > 3 else ''}")
            
            enrichments = enrich_metrics_batch_llm(
                use_case, framework_id, batch, compliance_context, llm, prompt_template
            )
            
            # Map enrichments to metrics by ID
            for enrichment in enrichments:
                metric_id = enrichment.get("metric_id", "")
                if metric_id:
                    all_enrichments[metric_id] = enrichment
            
            logger.info(f"✓ Batch {batch_num}/{total_batches} complete: {len(enrichments)} enrichments")
        
        # Merge enrichments back into metrics
        for i, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                logger.warning(f"Skipping invalid metric at index {i}: expected dict, got {type(metric)}")
                continue
            try:
                metric_id = metric.get("id", "")
                if metric_id in all_enrichments:
                    enrichment = all_enrichments[metric_id]
                    # Merge enrichment fields into metric
                    enriched_metric = dict(metric)
                    enriched_metric.update({
                        "goals": enrichment.get("goals", {}).get("values", []),
                        "focus_areas": enrichment.get("focus_areas", {}).get("values", []),
                        "use_cases": enrichment.get("use_cases", {}).get("values", []),
                        "audience_levels": enrichment.get("audience_levels", {}).get("values", []),
                        "metric_type": enrichment.get("metric_type", {}).get("value", metric.get("type", "count")),
                        "aggregation_windows": enrichment.get("aggregation_windows", {}).get("values", []),
                        "group_affinity": enrichment.get("group_affinity", {}).get("values", []),
                        "control_evidence_hints": enrichment.get("control_evidence_hints", {}),
                        "risk_quantification_hints": enrichment.get("risk_quantification_hints", {}),
                        "scenario_detection_hints": enrichment.get("scenario_detection_hints", {}),
                    })
                    enriched_metrics.append(enriched_metric)
                else:
                    # Fallback to rule-based if LLM enrichment failed
                    logger.warning(f"No LLM enrichment for metric {metric_id}, using rule-based fallback")
                    enriched_metrics.append(enrich_metric_rule_based(metric))
            except Exception as e:
                logger.error(f"Error processing metric at index {i}: {e}", exc_info=True)
                # Skip this metric but continue processing
                continue
    
    elif method == "hybrid":
        # Hybrid: rule-based first, then LLM refinement
        logger.info("Using hybrid enrichment (rule-based + LLM refinement)")
        
        # First pass: rule-based
        rule_based_metrics = []
        for i, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                logger.warning(f"Skipping invalid metric at index {i}: expected dict, got {type(metric)}")
                continue
            try:
                rule_based_metrics.append(enrich_metric_rule_based(metric))
            except Exception as e:
                logger.error(f"Error enriching metric at index {i}: {e}", exc_info=True)
                # Skip this metric but continue processing
                continue
        
        # Second pass: LLM refinement
        if control_taxonomy_path or control_taxonomy_dir:
            if control_taxonomy_path:
                control_taxonomy = load_control_taxonomy(control_taxonomy_path, framework_id=framework_id)
            elif control_taxonomy_dir:
                # Find framework-specific taxonomy file
                framework_taxonomy_path = find_control_taxonomy_file(
                    control_taxonomy_dir, framework_id
                )
                if framework_taxonomy_path:
                    control_taxonomy = load_control_taxonomy(framework_taxonomy_path, framework_id=framework_id)
                    logger.info(f"Using taxonomy file: {framework_taxonomy_path.name} for framework {framework_id}")
                else:
                    logger.warning(f"No taxonomy file found for framework {framework_id} in {control_taxonomy_dir}")
                    control_taxonomy = {}
            else:
                control_taxonomy = {}
            
            use_case_groups = []
            if use_case_groups_path:
                use_case_groups = load_use_case_groups(use_case_groups_path)
            
            compliance_context = prepare_compliance_context(
                control_taxonomy, use_case_groups, use_case, framework_id
            )
            
            prompts_dir = Path(__file__).parent / "prompts"
            prompt_template = load_prompt("14_enrich_metric_attributes", prompts_dir=str(prompts_dir))
            llm = get_llm(temperature=0)
            
            all_enrichments = {}
            total_batches = (len(rule_based_metrics) + batch_size - 1) // batch_size
            for i in range(0, len(rule_based_metrics), batch_size):
                batch = rule_based_metrics[i:i + batch_size]
                batch_num = i // batch_size + 1
                batch_ids = [m.get("id", "") for m in batch]
                logger.info(f"Refining batch {batch_num}/{total_batches} ({len(batch)} metrics): {batch_ids[:3]}{'...' if len(batch_ids) > 3 else ''}")
                
                enrichments = enrich_metrics_batch_llm(
                    use_case, framework_id, batch, compliance_context, llm, prompt_template
                )
                
                for enrichment in enrichments:
                    metric_id = enrichment.get("metric_id", "")
                    if metric_id:
                        all_enrichments[metric_id] = enrichment
                
                logger.info(f"✓ Batch {batch_num}/{total_batches} complete: {len(enrichments)} enrichments")
            
            # Merge LLM enrichments, keeping rule-based as fallback
            for metric in rule_based_metrics:
                metric_id = metric.get("id", "")
                if metric_id in all_enrichments:
                    enrichment = all_enrichments[metric_id]
                    # LLM enrichment overrides rule-based
                    enriched_metric = dict(metric)
                    enriched_metric.update({
                        "goals": enrichment.get("goals", {}).get("values", metric.get("goals", [])),
                        "focus_areas": enrichment.get("focus_areas", {}).get("values", metric.get("focus_areas", [])),
                        "use_cases": enrichment.get("use_cases", {}).get("values", metric.get("use_cases", [])),
                        "audience_levels": enrichment.get("audience_levels", {}).get("values", metric.get("audience_levels", [])),
                        "metric_type": enrichment.get("metric_type", {}).get("value", metric.get("metric_type", "count")),
                        "aggregation_windows": enrichment.get("aggregation_windows", {}).get("values", metric.get("aggregation_windows", [])),
                        "group_affinity": enrichment.get("group_affinity", {}).get("values", metric.get("group_affinity", [])),
                        "control_evidence_hints": enrichment.get("control_evidence_hints", {}),
                        "risk_quantification_hints": enrichment.get("risk_quantification_hints", {}),
                        "scenario_detection_hints": enrichment.get("scenario_detection_hints", {}),
                    })
                    enriched_metrics.append(enriched_metric)
                else:
                    # Keep rule-based if LLM failed
                    enriched_metrics.append(metric)
        else:
            # No LLM context, just use rule-based
            enriched_metrics = rule_based_metrics
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'rule-based', 'llm', or 'hybrid'")
    
    # Reorganize by original structure type
    if isinstance(original_structure, dict):
        # Handle dashboards structure (LMS format)
        if "dashboards" in original_structure:
            dashboards = original_structure["dashboards"]
            if isinstance(dashboards, list):
                enriched_dashboards = []
                for dashboard in dashboards:
                    if isinstance(dashboard, dict):
                        dashboard_id = dashboard.get("dashboard_id", "")
                        # Find metrics that belong to this dashboard
                        # Match by checking if metric has dashboard_id or section field
                        dashboard_metrics = [
                            m for m in enriched_metrics
                            if m.get("dashboard_id") == dashboard_id or
                            (dashboard_id and dashboard_id in str(m.get("section", "")))
                        ]
                        # If no explicit match, try to match by dashboard name or category
                        if not dashboard_metrics:
                            dashboard_name = dashboard.get("dashboard_name", "").lower()
                            dashboard_category = dashboard.get("dashboard_category", "").lower()
                            dashboard_metrics = [
                                m for m in enriched_metrics
                                if dashboard_name in str(m.get("name", "")).lower() or
                                dashboard_category in str(m.get("category", "")).lower()
                            ]
                        
                        enriched_dashboard = dict(dashboard)
                        enriched_dashboard["metrics"] = dashboard_metrics
                        enriched_dashboards.append(enriched_dashboard)
                
                result = {
                    "metadata": original_structure.get("metadata", {}),
                    "dashboards": enriched_dashboards,
                }
                result["metadata"]["enriched"] = True
                result["metadata"]["enrichment_method"] = method
            else:
                # Fallback to flat metrics structure
                result = {
                    "meta": {
                        "enriched": True,
                        "enrichment_method": method,
                    },
                    "metrics": enriched_metrics,
                }
        
        # Handle categories structure
        elif "categories" in original_structure:
            categories_data = original_structure["categories"]
            category_map = {}
            
            # Handle both dict and list structures
            if isinstance(categories_data, dict):
                for cat_id, cat_data in categories_data.items():
                    if isinstance(cat_data, dict):
                        cat_metrics = [m for m in enriched_metrics if m.get("category") == cat_id]
                        category_map[cat_id] = {
                            "display_name": cat_data.get("display_name", cat_id),
                            "description": cat_data.get("description", ""),
                            "metrics": cat_metrics,
                        }
            elif isinstance(categories_data, list):
                # If categories is a list, group metrics by their category field
                for metric in enriched_metrics:
                    cat_id = metric.get("category", "uncategorized")
                    if cat_id not in category_map:
                        category_map[cat_id] = {
                            "display_name": cat_id,
                            "description": "",
                            "metrics": [],
                        }
                    category_map[cat_id]["metrics"].append(metric)
            
            result = {
                "meta": original_structure.get("meta", {}),
                "categories": category_map,
            }
            result["meta"]["enriched"] = True
            result["meta"]["enrichment_method"] = method
        
        # Handle direct metrics structure or preserve original with enriched metrics
        else:
            # Preserve original structure but replace/update metrics
            result = dict(original_structure)
            result["metrics"] = enriched_metrics
            # Add enrichment metadata
            if "meta" not in result:
                result["meta"] = {}
            result["meta"]["enriched"] = True
            result["meta"]["enrichment_method"] = method
    else:
        # Fallback for non-dict structures
        result = {
            "meta": {
                "enriched": True,
                "enrichment_method": method,
            },
            "metrics": enriched_metrics,
        }
    
    return result


# ============================================================================
# CLI entry point
# ============================================================================

def infer_framework_from_filename(filename: str) -> str:
    """Infer framework ID from metrics registry filename."""
    filename_lower = filename.lower()
    
    # Common patterns
    if "soc2" in filename_lower or "soc_2" in filename_lower:
        return "soc2"
    elif "hipaa" in filename_lower:
        return "hipaa"
    elif "nist" in filename_lower or "csf" in filename_lower:
        return "nist_csf_2_0"
    elif "iso27001" in filename_lower or "iso_27001" in filename_lower:
        if "2013" in filename_lower:
            return "iso27001_2013"
        return "iso27001_2022"
    elif "cis" in filename_lower:
        return "cis_controls_v8_1"
    elif "lms" in filename_lower or "learning" in filename_lower or "ld" in filename_lower:
        # LMS metrics might not have a specific framework
        return "soc2"  # Default fallback
    
    # Default
    return "soc2"


def process_metrics_file_wrapper(
    input_path: Path,
    output_path: Path,
    method: str,
    control_taxonomy_path: Optional[Path],
    control_taxonomy_dir: Optional[Path],
    use_case_groups_path: Optional[Path],
    use_case: str,
    framework_id: Optional[str],
    batch_size: int,
) -> tuple[str, Dict[str, Any], Optional[str]]:
    """Wrapper for parallel processing of metrics files."""
    try:
        start_time = time.time()
        file_name = input_path.name
        logger.info(f"[{file_name}] Starting enrichment...")
        
        # Infer framework_id from filename if not provided
        actual_framework_id = framework_id
        if not actual_framework_id:
            actual_framework_id = infer_framework_from_filename(file_name)
            logger.info(f"[{file_name}] Inferred framework_id: {actual_framework_id}")
        
        enriched = enrich_registry(
            input_path,
            method=method,
            control_taxonomy_path=control_taxonomy_path,
            control_taxonomy_dir=control_taxonomy_dir,
            use_case_groups_path=use_case_groups_path,
            use_case=use_case,
            framework_id=actual_framework_id,
            batch_size=batch_size,
        )
        
        # Count metrics
        def _count_metrics(obj):
            if isinstance(obj, list):
                return len(obj)
            if isinstance(obj, dict):
                total = 0
                for v in obj.values():
                    if isinstance(v, dict) and "metrics" in v:
                        total += len(v["metrics"])
                    elif isinstance(v, list):
                        total += len(v)
                return total
            return 0
        
        count = _count_metrics(enriched)
        
        # Save output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, indent=2)
        
        elapsed = time.time() - start_time
        logger.info(f"[{file_name}] ✓ Enriched {count} metrics in {elapsed:.1f}s")
        
        return file_name, enriched, None
    except Exception as e:
        error_msg = f"Error processing {input_path.name}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return input_path.name, {}, error_msg


def find_metrics_registry_files(input_dir: Path) -> List[Path]:
    """Find all metrics registry JSON files in a directory."""
    metrics_files = []
    
    # Common patterns for metrics registry files
    patterns = [
        "*metrics*.json",
        "*registry*.json",
        "*dashboard*metrics*.json",
    ]
    
    for pattern in patterns:
        metrics_files.extend(input_dir.glob(pattern))
    
    # Remove duplicates and sort
    metrics_files = sorted(set(metrics_files))
    
    return metrics_files


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enrich metrics registry with decision tree fields")
    parser.add_argument(
        "--input",
        type=str,
        help="Path to single metrics_registry.json file"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        help="Directory containing metrics registry JSON files (processes all found files)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to write enriched registry (for single file)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to write enriched registries (for multiple files, creates one file per input)"
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["rule-based", "llm", "hybrid"],
        default="rule-based",
        help="Enrichment method: rule-based (fast), llm (accurate), or hybrid (both)"
    )
    parser.add_argument(
        "--control-taxonomy",
        type=str,
        help="Path to enriched control taxonomy JSON file (required for llm/hybrid methods). Can be single file or directory."
    )
    parser.add_argument(
        "--control-taxonomy-dir",
        type=str,
        help="Directory containing framework-specific control taxonomy files (e.g., soc2_enriched.json, hipaa_enriched.json). Auto-matches by framework_id."
    )
    parser.add_argument(
        "--use-case-groups",
        type=str,
        help="Path to metric_use_case_groups.json (optional for llm/hybrid methods)"
    )
    parser.add_argument(
        "--use-case",
        type=str,
        default="soc2_audit",
        help="Use case identifier (default: soc2_audit)"
    )
    parser.add_argument(
        "--framework-id",
        type=str,
        default="soc2",
        help="Framework ID (default: soc2)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of metrics per batch for LLM processing (default: 10)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="Maximum number of parallel file workers (default: 3)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without writing"
    )
    args = parser.parse_args()

    # Validate inputs
    if not args.input and not args.input_dir:
        logger.error("Either --input or --input-dir must be provided")
        sys.exit(1)
    
    if args.input and args.input_dir:
        logger.error("Cannot specify both --input and --input-dir")
        sys.exit(1)

    # Validate method requirements
    if args.method in ["llm", "hybrid"] and not args.control_taxonomy and not args.control_taxonomy_dir:
        logger.error(f"Method '{args.method}' requires --control-taxonomy or --control-taxonomy-dir")
        sys.exit(1)

    # Determine control taxonomy path/dir
    control_taxonomy_path = None
    control_taxonomy_dir = None
    
    if args.control_taxonomy:
        taxonomy_path = Path(args.control_taxonomy)
        if taxonomy_path.is_dir():
            control_taxonomy_dir = taxonomy_path
        else:
            control_taxonomy_path = taxonomy_path
    
    if args.control_taxonomy_dir:
        control_taxonomy_dir = Path(args.control_taxonomy_dir)
        if not control_taxonomy_dir.exists():
            logger.error(f"Control taxonomy directory not found: {control_taxonomy_dir}")
            sys.exit(1)
    
    use_case_groups_path = Path(args.use_case_groups) if args.use_case_groups else None
    
    # Determine files to process
    if args.input:
        input_files = [Path(args.input)]
        if not input_files[0].exists():
            logger.error(f"Input file not found: {input_files[0]}")
            sys.exit(1)
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            logger.error(f"Input directory not found: {input_dir}")
            sys.exit(1)
        input_files = find_metrics_registry_files(input_dir)
        if not input_files:
            logger.error(f"No metrics registry files found in {input_dir}")
            sys.exit(1)
        logger.info(f"Found {len(input_files)} metrics registry files: {[f.name for f in input_files]}")
    
    start_time = time.time()
    results = {}
    errors = {}
    
    if len(input_files) == 1:
        # Single file - process directly
        input_path = input_files[0]
        output_path = Path(args.output) if args.output else Path(f"{input_path.stem}_enriched.json")
        
        try:
            # Infer framework_id from filename if not provided
            framework_id = args.framework_id
            if not framework_id:
                framework_id = infer_framework_from_filename(input_path.name)
                logger.info(f"Inferred framework_id: {framework_id} from filename")
            
            enriched = enrich_registry(
                input_path,
                method=args.method,
                control_taxonomy_path=control_taxonomy_path,
                control_taxonomy_dir=control_taxonomy_dir,
                use_case_groups_path=use_case_groups_path,
                use_case=args.use_case,
                framework_id=framework_id,
                batch_size=args.batch_size,
            )
            
            # Count metrics
            def _count_metrics(obj):
                if isinstance(obj, list):
                    return len(obj)
                if isinstance(obj, dict):
                    total = 0
                    for v in obj.values():
                        if isinstance(v, dict) and "metrics" in v:
                            total += len(v["metrics"])
                        elif isinstance(v, list):
                            total += len(v)
                    return total
                return 0
            
            count = _count_metrics(enriched)
            logger.info(f"Enriched {count} metrics using method: {args.method}")
            
            if not args.dry_run:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(enriched, f, indent=2)
                logger.info(f"Written to {output_path}")
            else:
                # Print sample
                if isinstance(enriched, dict):
                    if "metrics" in enriched and enriched["metrics"]:
                        print(json.dumps(enriched["metrics"][0], indent=2))
                    elif "categories" in enriched:
                        categories_data = enriched["categories"]
                        if isinstance(categories_data, dict):
                            for k, v in categories_data.items():
                                if isinstance(v, dict) and "metrics" in v and v["metrics"]:
                                    print(f"\nSample from category '{k}':")
                                    print(json.dumps(v["metrics"][0], indent=2))
                                    break
                        elif isinstance(categories_data, list):
                            # If categories is a list, just print first metric
                            for cat in categories_data:
                                if isinstance(cat, dict) and "metrics" in cat and cat["metrics"]:
                                    print(f"\nSample from category '{cat.get('id', 'unknown')}':")
                                    print(json.dumps(cat["metrics"][0], indent=2))
                                    break
            
            results[input_path.name] = enriched
        except Exception as e:
            logger.error(f"Error enriching registry: {e}", exc_info=True)
            errors[input_path.name] = str(e)
    else:
        # Multiple files - process in parallel
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {len(input_files)} metrics registry files in parallel (max {args.max_workers} workers)")
        logger.info(f"{'='*60}\n")
        
        # Determine output directory
        output_dir = None
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        elif args.output:
            # If output is specified but multiple files, treat as directory
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all file processing tasks
            future_to_file = {}
            for input_path in input_files:
                # Determine output path
                if output_dir:
                    output_path = output_dir / f"{input_path.stem}_enriched.json"
                else:
                    output_path = input_path.parent / f"{input_path.stem}_enriched.json"
                
                # Infer framework_id from filename if not provided
                framework_id = args.framework_id
                if not framework_id:
                    framework_id = infer_framework_from_filename(input_path.name)
                
                future = executor.submit(
                    process_metrics_file_wrapper,
                    input_path,
                    output_path,
                    args.method,
                    control_taxonomy_path,
                    control_taxonomy_dir,
                    use_case_groups_path,
                    args.use_case,
                    framework_id,
                    args.batch_size,
                )
                future_to_file[future] = input_path.name
            
            # Process completed tasks as they finish
            completed = 0
            for future in as_completed(future_to_file):
                file_name = future_to_file[future]
                completed += 1
                try:
                    fname, result, error = future.result()
                    if error:
                        errors[fname] = error
                    else:
                        results[fname] = result
                    logger.info(f"[Progress] {completed}/{len(input_files)} files completed")
                except Exception as e:
                    error_msg = f"Unexpected error for {file_name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors[file_name] = error_msg
    
    # Summary
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info("ENRICHMENT SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total files: {len(input_files)}")
    logger.info(f"Successfully processed: {len(results)}")
    logger.info(f"Errors: {len(errors)}")
    logger.info(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    
    if errors:
        logger.warning("\nFiles with errors:")
        for fname, error in errors.items():
            logger.warning(f"  {fname}: {error}")
    
    # Count total metrics
    def _count_metrics(obj):
        if isinstance(obj, list):
            return len(obj)
        if isinstance(obj, dict):
            total = 0
            for v in obj.values():
                if isinstance(v, dict) and "metrics" in v:
                    total += len(v["metrics"])
                elif isinstance(v, list):
                    total += len(v)
            return total
        return 0

    total_metrics = sum(_count_metrics(result) for result in results.values())
    logger.info(f"\nTotal metrics enriched: {total_metrics}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
