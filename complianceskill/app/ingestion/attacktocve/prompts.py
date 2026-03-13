"""
Prompt templates for the ATT&CK → Control Framework mapping pipeline.

All templates are framework-agnostic.  Every call site injects two variables
that carry the framework identity:

    {framework_name}   – human label, e.g. "CIS Controls v8.1", "NIST SP 800-53 Rev 5",
                         "ISO 27001:2022", "SOC 2 TSC", "PCI-DSS v4.0"
    {control_id_label} – how this framework labels its controls, e.g. "CIS-RISK-NNN",
                         "AC-2", "A.8.1", "CC6.1", "Req-8.3"

Pass these from graph state so the same compiled graph works across frameworks
without any prompt edits.  Default values below match the original CIS build.

Templates
---------
ATTACK_QUERY_BUILDER    – Build a semantic search query from technique metadata
CONTROL_MAPPING_SYSTEM  – System prompt for the core mapping LLM call
CONTROL_MAPPING_USER    – User turn: technique + candidate controls → JSON mappings
VALIDATION_SYSTEM       – Validate and score a set of mappings
VALIDATION_USER         – Validation user turn
SUMMARY_SYSTEM          – Summarise final mappings for human consumption

Framework presets (pass directly as {framework_name} / {control_id_label}):
    FRAMEWORKS["cis"]      FRAMEWORKS["nist_800_53"]   FRAMEWORKS["iso_27001"]
    FRAMEWORKS["soc2"]     FRAMEWORKS["pci_dss"]        FRAMEWORKS["hipaa"]
"""

# ---------------------------------------------------------------------------
# Framework presets – import and unpack into node kwargs
# ---------------------------------------------------------------------------

# Framework name mappings (for backward compatibility and fallback)
FRAMEWORK_NAMES: dict = {
    "cis_controls_v8_1": "CIS Controls v8.1",
    "nist_csf_2_0": "NIST CSF 2.0",
    "hipaa": "HIPAA",
    "soc2": "SOC 2",
    "iso27001_2013": "ISO 27001:2013",
    "iso27001_2022": "ISO 27001:2022",
}

# Prompt presets for control_id_label formatting
FRAMEWORKS: dict = {
    "cis": {
        "framework_name": "CIS Controls v8.1",
        "control_id_label": "CIS-RISK-NNN",
    },
    "nist_800_53": {
        "framework_name": "NIST SP 800-53 Rev 5",
        "control_id_label": "Control family + ID (e.g. AC-2, SI-3)",
    },
    "iso_27001": {
        "framework_name": "ISO/IEC 27001:2022",
        "control_id_label": "Annex A control ID (e.g. A.8.1, A.5.23)",
    },
    "soc2": {
        "framework_name": "SOC 2 Trust Services Criteria (2017)",
        "control_id_label": "TSC reference (e.g. CC6.1, A1.2)",
    },
    "pci_dss": {
        "framework_name": "PCI-DSS v4.0",
        "control_id_label": "Requirement ID (e.g. Req-8.3, Req-10.2)",
    },
    "hipaa": {
        "framework_name": "HIPAA Security Rule",
        "control_id_label": "Safeguard reference (e.g. §164.312(a)(1))",
    },
}

# Default – preserved for backward-compat with existing CIS call sites
_DEFAULT_FRAMEWORK = FRAMEWORKS["cis"]


def get_framework_preset(framework_id: str) -> dict:
    """
    Get framework preset from framework identifier.
    
    Maps framework identifiers (e.g., "cis_controls_v8_1", "nist_csf_2_0")
    to prompt presets (e.g., "cis", "nist_800_53").
    
    Args:
        framework_id: Framework identifier from framework_helper
        
    Returns:
        Dict with framework_name and control_id_label
    """
    # Try to get framework name from framework_helper first
    try:
        from .framework_helper import get_framework_info
        framework_info = get_framework_info(framework_id)
        framework_name = framework_info.get("name", framework_id.replace("_", " ").title())
    except (ImportError, ValueError):
        # Fallback to hardcoded mapping
        framework_name = FRAMEWORK_NAMES.get(framework_id, framework_id.replace("_", " ").title())
    
    # Map framework identifiers to prompt preset keys for control_id_label
    framework_map = {
        "cis_controls_v8_1": "cis",
        "nist_csf_2_0": "nist_800_53",  # Using NIST 800-53 preset for CSF
        "hipaa": "hipaa",
        "soc2": "soc2",
        "iso27001_2013": "iso_27001",
        "iso27001_2022": "iso_27001",
    }
    
    preset_key = framework_map.get(framework_id, "cis")
    preset = FRAMEWORKS.get(preset_key, _DEFAULT_FRAMEWORK)
    
    # Override framework_name with the discovered name
    return {
        "framework_name": framework_name,
        "control_id_label": preset["control_id_label"],
    }


def get_framework_info_from_yaml_path(yaml_path: str) -> dict:
    """
    Extract framework identifier from YAML path and return framework preset.
    
    Args:
        yaml_path: Path to framework YAML file
        
    Returns:
        Dict with framework_name and control_id_label
    """
    from pathlib import Path
    
    path = Path(yaml_path)
    # Try to extract framework from path (e.g., .../cis_controls_v8_1/...)
    for part in path.parts:
        if part in FRAMEWORKS or any(fw in part for fw in ["cis", "nist", "hipaa", "soc2", "iso27001"]):
            # Try to match framework identifier
            for fw_id in ["cis_controls_v8_1", "nist_csf_2_0", "hipaa", "soc2", "iso27001_2013", "iso27001_2022"]:
                if fw_id in part or fw_id in str(path):
                    return get_framework_preset(fw_id)
    
    # Default to CIS if can't determine
    return _DEFAULT_FRAMEWORK


# ---------------------------------------------------------------------------
# 1.  ATT&CK → Vector Store Query Builder
# ---------------------------------------------------------------------------

ATTACK_QUERY_BUILDER = """\
You are a cybersecurity analyst building a semantic search query to find \
relevant controls and risk scenarios inside a {framework_name} control library.

Given the ATT&CK technique details below, write a concise search query \
(2–4 sentences) that captures:
- What the attacker does (the core action)
- Which systems, data, or processes are targeted
- What the primary business or compliance impact would be
- Any {framework_name}-specific risk themes the technique is likely to trigger

Return ONLY the search query text — no preamble, no markdown.

Technique ID:    {technique_id}
Technique Name:  {technique_name}
Tactics:         {tactics}
Platforms:       {platforms}
Description:
{description}
"""


# ---------------------------------------------------------------------------
# 2.  Core Mapping Node
# ---------------------------------------------------------------------------

CONTROL_MAPPING_SYSTEM = """\
You are a cybersecurity compliance architect mapping MITRE ATT&CK techniques \
to controls and risk scenarios in the {framework_name} framework.

Your task: given one ATT&CK technique and a set of candidate {framework_name} \
controls or risk scenarios retrieved from a vector store, determine which items \
are genuinely relevant and return a structured mapping for each.

Rules:
1. Only map controls where there is TRUE relevance — the ATT&CK technique \
   must directly cause, enable, or exploit the control's risk or gap.
2. Score relevance 0.0–1.0.  Exclude any item scoring below 0.40.
3. Write a concrete rationale (1–3 sentences) grounded in {framework_name} \
   language — reference specific control objectives, safeguards, or clauses \
   where possible.
4. Set confidence based on how clearly the technique triggers the control gap:
   - "high"   → direct and unambiguous link
   - "medium" → plausible but requires an intermediate step
   - "low"    → tangential or highly context-dependent
5. The "mapped_controls" field must contain the ATT&CK technique ID — it \
   represents the technique being added to the control's coverage list.
6. Return VALID JSON only — no markdown fences, no prose before or after.

Output schema (JSON array):
[
  {{
    "technique_id": "<ATT&CK T-number>",
    "scenario_id": "<{control_id_label}>",
    "scenario_name": "<control or scenario title>",
    "relevance_score": <0.0–1.0>,
    "rationale": "<string — cite {framework_name} objectives where possible>",
    "mapped_controls": ["<technique_id>"],
    "attack_tactics": ["<tactic>"],
    "attack_platforms": ["<platform>"],
    "loss_outcomes": ["<outcome>"],
    "confidence": "high|medium|low"
  }}
]
"""

CONTROL_MAPPING_USER = """\
=== ATT&CK Technique ===
ID:           {technique_id}
Name:         {technique_name}
Tactics:      {tactics}
Platforms:    {platforms}
Description:  {description}
Mitigations:  {mitigations}
Data Sources: {data_sources}

=== Candidate {framework_name} Controls / Scenarios (top-{top_k} from vector store) ===
{scenarios_json}

Map the ATT&CK technique to the most relevant {framework_name} controls above.
Return a JSON array. If NO controls are relevant, return an empty array [].
"""


# ---------------------------------------------------------------------------
# 3.  Validation Node
# ---------------------------------------------------------------------------

VALIDATION_SYSTEM = """\
You are a senior cybersecurity compliance reviewer validating ATT&CK-to-control \
mappings against the {framework_name} framework, produced by an AI mapping agent.

Your job:
1. Verify each mapping is logically sound within {framework_name}'s control \
   objectives — not just superficially keyword-matched.
2. Flag mappings where the rationale is too vague or does not support the score.
3. Correct relevance_score or confidence where the reasoning is weak.
4. Remove mappings where relevance falls below 0.35 after review.
5. Return the corrected set as a JSON object — NEVER add new mappings.

Output schema (JSON object):
{{
  "is_valid": true|false,
  "issues": ["<issue description>", ...],
  "corrected_mappings": [ <same mapping schema as input> ],
  "validation_notes": "<overall assessment — note any {framework_name}-specific concerns>"
}}
"""

VALIDATION_USER = """\
=== Control Framework ===
{framework_name}

=== ATT&CK Technique Context ===
{technique_summary}

=== Proposed Mappings (from mapping agent) ===
{raw_mappings_json}

Validate against {framework_name} control objectives and return the corrected JSON object.
"""


# ---------------------------------------------------------------------------
# 4.  Summary Node
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM = """\
You are a cybersecurity analyst writing executive summaries of ATT&CK technique \
mappings to {framework_name} controls. Be concise, use plain language, reference \
{framework_name} terminology, and highlight the key risk themes.
"""

SUMMARY_USER = """\
Summarise the following ATT&CK → {framework_name} control mappings in 3–5 sentences.
Highlight: the attack technique, the primary controls or risk areas it maps to, \
and which {framework_name} domains or categories are most exposed.

Framework:  {framework_name}
Technique:  {technique_id} – {technique_name}
Tactics:    {tactics}

Final Mappings:
{final_mappings_json}
"""