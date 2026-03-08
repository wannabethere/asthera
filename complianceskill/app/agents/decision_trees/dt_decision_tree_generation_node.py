"""
Decision Tree Generation Node — LLM-Assisted Artifact Generation

Generates three types of artifacts using LLM:
1. Use case groups (from controls, risks, scenarios, metrics)
2. Control taxonomy (per-control measurement requirements)
3. Metric enrichment (per-metric attribute tags)

Results are cached and validated before being consumed by the scoring engine.
"""
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.prompt_loader import load_prompt, PROMPTS_DECISION_TREES

logger = logging.getLogger(__name__)


# ============================================================================
# Cache key generation
# ============================================================================

def _generate_cache_key(
    framework_id: str,
    use_case: str,
    control_codes: List[str],
    metric_ids: List[str],
    tenant_id: Optional[str] = None,
) -> str:
    """Generate a cache key for the generated artifacts."""
    components = [
        framework_id or "",
        use_case or "",
        ",".join(sorted(control_codes)),
        ",".join(sorted(metric_ids)),
        tenant_id or "",
    ]
    content = "|".join(components)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ============================================================================
# Validation functions
# ============================================================================

def _validate_groups(
    groups_output: Dict[str, Any],
    input_controls: List[Dict],
    input_risks: List[Dict],
    available_metrics: List[Dict],
) -> Tuple[bool, List[str]]:
    """Validate LLM-generated groups against input artifacts."""
    errors = []
    
    if "groups" not in groups_output:
        errors.append("Missing 'groups' field in output")
        return False, errors
    
    groups = groups_output.get("groups", [])
    if not isinstance(groups, list):
        errors.append("'groups' must be a list")
        return False, errors
    
    # G-V2: Control coverage
    input_control_codes = {c.get("code") or c.get("control_code", "") for c in input_controls if c.get("code") or c.get("control_code")}
    input_control_codes = {c for c in input_control_codes if c}
    
    evidenced_controls = set()
    for group in groups:
        evidenced = group.get("evidences_controls", [])
        if isinstance(evidenced, list):
            evidenced_controls.update(evidenced)
    
    missing_controls = input_control_codes - evidenced_controls
    if missing_controls:
        errors.append(f"Controls not in any group's evidences_controls: {missing_controls}")
    
    # G-V3: Risk coverage (critical/high only)
    high_impact_risks = {
        r.get("risk_code") or r.get("code", "")
        for r in input_risks
        if (r.get("impact", "").lower() in ("critical", "high") or
            r.get("likelihood", "").lower() == "high")
    }
    high_impact_risks = {r for r in high_impact_risks if r}
    
    quantified_risks = set()
    for group in groups:
        quantified = group.get("quantifies_risks", [])
        if isinstance(quantified, list):
            quantified_risks.update(quantified)
    
    missing_risks = high_impact_risks - quantified_risks
    if missing_risks:
        errors.append(f"High-impact risks not in any group's quantifies_risks: {missing_risks}")
    
    # G-V4: Group count bounds
    if len(groups) < 3:
        errors.append(f"Too few groups: {len(groups)} (minimum 3)")
    if len(groups) > 10:
        errors.append(f"Too many groups: {len(groups)} (maximum 10)")
    
    # G-V6: No hallucinated control codes
    for group in groups:
        evidenced = group.get("evidences_controls", [])
        for code in evidenced:
            if code not in input_control_codes:
                errors.append(f"Group {group.get('group_id', 'unknown')} references non-existent control: {code}")
    
    return len(errors) == 0, errors


def _validate_taxonomy(
    taxonomy_output: Dict[str, Any],
    input_controls: List[Dict],
) -> Tuple[bool, List[str]]:
    """Validate LLM-generated taxonomy entries."""
    errors = []
    
    if "taxonomy_entries" not in taxonomy_output:
        errors.append("Missing 'taxonomy_entries' field")
        return False, errors
    
    entries = taxonomy_output.get("taxonomy_entries", [])
    input_control_codes = {c.get("code") or c.get("control_code", "") for c in input_controls}
    input_control_codes = {c for c in input_control_codes if c}
    
    output_codes = {e.get("control_code", "") for e in entries}
    missing = input_control_codes - output_codes
    if missing:
        errors.append(f"Missing taxonomy entries for controls: {missing}")
    
    # T-V2: Focus area validity (basic check - full list would be from decision tree)
    valid_focus_areas = {
        "access_control", "audit_logging", "vulnerability_management",
        "incident_response", "change_management", "data_protection",
        "training_compliance"
    }
    
    for entry in entries:
        focus_areas = entry.get("focus_areas", [])
        invalid = [fa for fa in focus_areas if fa not in valid_focus_areas]
        if invalid:
            errors.append(f"Entry {entry.get('control_code')} has invalid focus_areas: {invalid}")
    
    return len(errors) == 0, errors


def _validate_enrichments(
    enrichments_output: Dict[str, Any],
    input_metrics: List[Dict],
) -> Tuple[bool, List[str]]:
    """Validate LLM-generated metric enrichments."""
    errors = []
    
    if "enrichments" not in enrichments_output:
        errors.append("Missing 'enrichments' field")
        return False, errors
    
    enrichments = enrichments_output.get("enrichments", [])
    input_metric_ids = {m.get("id") or m.get("metric_id", "") for m in input_metrics}
    input_metric_ids = {m for m in input_metric_ids if m}
    
    output_ids = {e.get("metric_id", "") for e in enrichments}
    missing = input_metric_ids - output_ids
    if missing:
        errors.append(f"Missing enrichments for metrics: {missing}")
    
    # E-V2: Value validity (basic check)
    valid_goals = {
        "compliance_posture", "incident_triage", "control_effectiveness",
        "risk_exposure", "training_completion", "remediation_velocity"
    }
    
    for enrichment in enrichments:
        goals = enrichment.get("goals", {}).get("values", [])
        invalid = [g for g in goals if g not in valid_goals]
        if invalid:
            errors.append(f"Metric {enrichment.get('metric_id')} has invalid goals: {invalid}")
    
    return len(errors) == 0, errors


# ============================================================================
# LLM generation functions
# ============================================================================

def _generate_use_case_groups(
    use_case: str,
    framework_id: str,
    controls: List[Dict],
    risks: List[Dict],
    scenarios: List[Dict],
    available_metrics: List[Dict],
    data_sources: List[str],
    tenant_context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Generate use case groups using LLM."""
    try:
        prompt_template = load_prompt("12_generate_use_case_groups", prompts_dir=str(PROMPTS_DECISION_TREES))
        
        # Build input message
        controls_str = json.dumps(controls[:50], indent=2)  # Limit for token budget
        risks_str = json.dumps(risks[:30], indent=2)
        scenarios_str = json.dumps(scenarios[:20], indent=2)
        metrics_str = json.dumps(available_metrics[:40], indent=2)
        
        human_message = f"""use_case: {use_case}
framework_id: {framework_id}
tenant_context: {json.dumps(tenant_context or {})}

controls[]:
{controls_str}

risks[]:
{risks_str}

scenarios[]:
{scenarios_str}

available_metrics[]:
{metrics_str}

data_sources: {json.dumps(data_sources)}
"""
        
        llm = get_llm(temperature=0)
        system_prompt = prompt_template.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON
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
        
    except Exception as e:
        logger.error(f"Error generating use case groups: {e}", exc_info=True)
        return {"groups": [], "group_relationships": [], "coverage_expectations": {}}


def _generate_control_taxonomy_batch(
    framework_id: str,
    controls_batch: List[Dict],
    associated_risks: List[Dict],
    associated_scenarios: List[Dict],
) -> Dict[str, Any]:
    """Generate taxonomy for a batch of controls."""
    try:
        prompt_template = load_prompt("13_generate_control_taxonomy", prompts_dir=str(PROMPTS_DECISION_TREES))
        
        controls_str = json.dumps(controls_batch, indent=2)
        risks_str = json.dumps(associated_risks, indent=2)
        scenarios_str = json.dumps(associated_scenarios, indent=2)
        
        valid_focus_areas = [
            "access_control", "audit_logging", "vulnerability_management",
            "incident_response", "change_management", "data_protection",
            "training_compliance"
        ]
        
        human_message = f"""framework_id: {framework_id}

controls[]:
{controls_str}

associated_risks[]:
{risks_str}

associated_scenarios[]:
{scenarios_str}

valid_focus_areas: {json.dumps(valid_focus_areas)}
valid_metric_types: ["count", "rate", "percentage", "score", "distribution", "comparison", "trend"]
"""
        
        llm = get_llm(temperature=0)
        system_prompt = prompt_template.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON
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
        
    except Exception as e:
        logger.error(f"Error generating control taxonomy batch: {e}", exc_info=True)
        return {"taxonomy_entries": []}


def _enrich_metrics_batch(
    use_case: str,
    framework_id: str,
    metrics_batch: List[Dict],
    controls: List[Dict],
    risks: List[Dict],
    scenarios: List[Dict],
    available_groups: List[Dict],
) -> Dict[str, Any]:
    """Enrich a batch of metrics using LLM."""
    try:
        prompt_template = load_prompt("14_enrich_metric_attributes", prompts_dir=str(PROMPTS_DECISION_TREES))
        
        metrics_str = json.dumps(metrics_batch, indent=2)
        controls_str = json.dumps(controls[:30], indent=2)  # Limit for token budget
        risks_str = json.dumps(risks[:20], indent=2)
        scenarios_str = json.dumps(scenarios[:15], indent=2)
        groups_str = json.dumps(available_groups, indent=2)
        
        human_message = f"""use_case: {use_case}
framework_id: {framework_id}

metrics[]:
{metrics_str}

controls[]:
{controls_str}

risks[]:
{risks_str}

scenarios[]:
{scenarios_str}

available_groups[]:
{groups_str}
"""
        
        llm = get_llm(temperature=0)
        system_prompt = prompt_template.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON
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
        
    except Exception as e:
        logger.error(f"Error enriching metrics batch: {e}", exc_info=True)
        return {"enrichments": []}


# ============================================================================
# Main node
# ============================================================================

def dt_decision_tree_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate LLM-assisted decision tree artifacts (groups, taxonomy, enrichments).
    
    Reads from state:
        framework_id, use_case (from decisions or auto-resolve), controls, risks,
        scenarios, resolved_metrics, selected_data_sources, tenant context
    
    Writes to state:
        dt_generated_groups, dt_generated_taxonomy, dt_generated_enrichments,
        dt_generation_cache_key, dt_generation_source (llm_generated | static_fallback)
    """
    try:
        # Check cache first
        framework_id = state.get("framework_id", "")
        resolved_metrics = state.get("resolved_metrics", [])
        controls = state.get("dt_retrieved_controls", []) or state.get("controls", [])
        risks = state.get("dt_retrieved_risks", []) or state.get("risks", [])
        scenarios = state.get("dt_retrieved_scenarios", []) or state.get("scenarios", [])
        
        # Try to get use_case from decisions if already resolved, else use default
        decisions = state.get("dt_metric_decisions", {})
        use_case = decisions.get("use_case") or "soc2_audit"
        
        # Check if we should skip generation (use static fallback)
        # Default to False since control taxonomy and metrics enrichment already exist
        use_llm_generation = state.get("dt_use_llm_generation", False)  # Default to False
        
        if not use_llm_generation or not resolved_metrics:
            logger.info("dt_decision_tree_generation: Skipping LLM generation (disabled or no metrics)")
            state["dt_generation_source"] = "static_fallback"
            state["dt_generated_groups"] = []
            state["dt_generated_taxonomy"] = []
            state["dt_generated_enrichments"] = []
            return state
        
        # Generate cache key
        control_codes = [c.get("code") or c.get("control_code", "") for c in controls]
        metric_ids = [m.get("id") or m.get("metric_id", "") for m in resolved_metrics]
        cache_key = _generate_cache_key(framework_id, use_case, control_codes, metric_ids)
        
        # Check in-memory cache (context_cache)
        context_cache = state.get("context_cache", {})
        gen_cache = context_cache.get("decision_tree_generation", {})
        if gen_cache.get("cache_key") == cache_key and gen_cache.get("artifacts"):
            logger.info("dt_decision_tree_generation: Cache hit, reusing artifacts")
            artifacts = gen_cache["artifacts"]
            state["dt_generated_groups"] = artifacts.get("groups", [])
            state["dt_generated_taxonomy"] = artifacts.get("taxonomy", [])
            state["dt_generated_enrichments"] = artifacts.get("enrichments", [])
            state["dt_generation_cache_key"] = cache_key
            state["dt_generation_source"] = artifacts.get("source", "llm_generated")
            return state
        
        # Generate artifacts
        # Log why we're generating (for debugging)
        use_llm_generation = state.get("dt_use_llm_generation", False)
        logger.info(
            f"dt_decision_tree_generation: Generating artifacts for use_case={use_case}, framework={framework_id} "
            f"(dt_use_llm_generation={use_llm_generation})"
        )
        
        data_sources = state.get("dt_data_sources_in_scope", []) or state.get("selected_data_sources", [])
        tenant_context = state.get("tenant_context", {})
        
        # Task 1: Generate groups
        groups_result = _generate_use_case_groups(
            use_case=use_case,
            framework_id=framework_id,
            controls=controls,
            risks=risks,
            scenarios=scenarios,
            available_metrics=resolved_metrics,
            data_sources=data_sources,
            tenant_context=tenant_context,
        )
        
        # Validate groups
        groups_valid, groups_errors = _validate_groups(groups_result, controls, risks, resolved_metrics)
        if not groups_valid:
            logger.warning(f"dt_decision_tree_generation: Group validation failed: {groups_errors}")
            # Fallback to static groups
            groups_result = {"groups": [], "group_relationships": [], "coverage_expectations": {}}
        
        # Task 2: Generate taxonomy (batched by control domain)
        taxonomy_entries = []
        if controls:
            # Group controls by domain prefix (e.g., CC6, CC7)
            controls_by_domain: Dict[str, List[Dict]] = {}
            for ctrl in controls:
                code = ctrl.get("code") or ctrl.get("control_code", "")
                prefix = code.split(".")[0] if "." in code else code[:3]
                if prefix not in controls_by_domain:
                    controls_by_domain[prefix] = []
                controls_by_domain[prefix].append(ctrl)
            
            # Generate taxonomy in parallel batches
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for domain, domain_controls in controls_by_domain.items():
                    # Batch size 8-12
                    for i in range(0, len(domain_controls), 10):
                        batch = domain_controls[i:i+10]
                        # Find associated risks and scenarios
                        batch_codes = {c.get("code") or c.get("control_code", "") for c in batch}
                        assoc_risks = [r for r in risks if any(
                            code in (r.get("mitigating_controls", []) or [])
                            for code in batch_codes
                        )]
                        assoc_scenarios = [s for s in scenarios if any(
                            code in (s.get("affected_controls", []) or [])
                            for code in batch_codes
                        )]
                        
                        future = executor.submit(
                            _generate_control_taxonomy_batch,
                            framework_id, batch, assoc_risks, assoc_scenarios
                        )
                        futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        # Add timeout to prevent hanging (5 minutes per batch)
                        batch_result = future.result(timeout=300)
                        taxonomy_entries.extend(batch_result.get("taxonomy_entries", []))
                    except FutureTimeoutError:
                        logger.error("Taxonomy batch generation timed out after 5 minutes - skipping batch")
                    except Exception as e:
                        logger.error(f"Error in taxonomy batch generation: {e}", exc_info=True)
        
        # Validate taxonomy
        taxonomy_valid, taxonomy_errors = _validate_taxonomy(
            {"taxonomy_entries": taxonomy_entries}, controls
        )
        if not taxonomy_valid:
            logger.warning(f"dt_decision_tree_generation: Taxonomy validation failed: {taxonomy_errors}")
        
        # Task 3: Enrich metrics (batched)
        enrichments = []
        available_groups = groups_result.get("groups", [])
        
        if resolved_metrics and available_groups:
            # Batch metrics by category
            metrics_by_category: Dict[str, List[Dict]] = {}
            for metric in resolved_metrics:
                category = metric.get("category", "other")
                if category not in metrics_by_category:
                    metrics_by_category[category] = []
                metrics_by_category[category].append(metric)
            
            # Generate enrichments in parallel batches
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for category, category_metrics in metrics_by_category.items():
                    # Batch size 5-8
                    for i in range(0, len(category_metrics), 6):
                        batch = category_metrics[i:i+6]
                        future = executor.submit(
                            _enrich_metrics_batch,
                            use_case, framework_id, batch, controls, risks, scenarios, available_groups
                        )
                        futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        # Add timeout to prevent hanging (5 minutes per batch)
                        batch_result = future.result(timeout=300)
                        enrichments.extend(batch_result.get("enrichments", []))
                    except FutureTimeoutError:
                        logger.error("Metric enrichment batch timed out after 5 minutes - skipping batch")
                    except Exception as e:
                        logger.error(f"Error in metric enrichment batch: {e}", exc_info=True)
        
        # Validate enrichments
        enrichments_valid, enrichments_errors = _validate_enrichments(
            {"enrichments": enrichments}, resolved_metrics
        )
        if not enrichments_valid:
            logger.warning(f"dt_decision_tree_generation: Enrichment validation failed: {enrichments_errors}")
        
        # Store results
        artifacts = {
            "groups": groups_result.get("groups", []),
            "group_relationships": groups_result.get("group_relationships", []),
            "taxonomy": taxonomy_entries,
            "enrichments": enrichments,
            "source": "llm_generated",
        }
        
        # Update cache
        context_cache["decision_tree_generation"] = {
            "cache_key": cache_key,
            "artifacts": artifacts,
            "generated_at": datetime.utcnow().isoformat(),
        }
        state["context_cache"] = context_cache
        
        # Store in state
        state["dt_generated_groups"] = artifacts["groups"]
        state["dt_generated_group_relationships"] = artifacts["group_relationships"]
        state["dt_generated_taxonomy"] = artifacts["taxonomy"]
        state["dt_generated_enrichments"] = artifacts["enrichments"]
        state["dt_generation_cache_key"] = cache_key
        state["dt_generation_source"] = "llm_generated"
        
        logger.info(
            f"dt_decision_tree_generation: Generated {len(artifacts['groups'])} groups, "
            f"{len(taxonomy_entries)} taxonomy entries, {len(enrichments)} enrichments"
        )
        
        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"Decision Tree Generation: Generated {len(artifacts['groups'])} groups, "
                f"{len(taxonomy_entries)} control taxonomy entries, "
                f"{len(enrichments)} metric enrichments"
            )
        ))
        
    except Exception as e:
        logger.error(f"dt_decision_tree_generation_node failed: {e}", exc_info=True)
        state["dt_generation_source"] = "static_fallback"
        state["dt_generated_groups"] = []
        state["dt_generated_taxonomy"] = []
        state["dt_generated_enrichments"] = []
    
    return state
