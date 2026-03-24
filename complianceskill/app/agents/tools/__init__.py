"""
Security intelligence tools for compliance and vulnerability analysis.

This module provides LangChain tools for:
- API-based intelligence (NVD, EPSS, CISA KEV, GitHub Advisory)
- Postgres-based mappings (CVE-ATT&CK, ATT&CK-Control, CPE resolution)
- Exploit intelligence (Exploit-DB, Metasploit, Nuclei)
- Compliance tools (Framework controls, CIS benchmarks, gap analysis)
- Threat intelligence (OTX, VirusTotal)
- ATT&CK framework tools
- Analysis tools (attack paths, risk calculation, remediation prioritization)
- Web search (Tavily)
"""

from typing import List
from langchain_core.tools import BaseTool

# Import tool creators
from app.agents.tools.api_tools import (
    create_cve_intelligence_tool,
    create_epss_lookup_tool,
    create_cisa_kev_tool,
    create_github_advisory_tool,
    create_cpe_lookup_tool,
)
from app.agents.tools.db_tools import (
    create_cve_to_attack_tool,
    create_attack_to_control_tool,
    create_cpe_resolver_tool,
)
from app.agents.tools.attack_control_mapping import create_attack_control_mapping_tool
from app.agents.tools.tactic_contextualiser import create_tactic_contextualiser_tool
from app.agents.tools.framework_item_retrieval import create_framework_item_retrieval_tool
from app.agents.tools.cve_enrichment import create_cve_enrichment_tool
from app.agents.tools.cve_attack_mapper import create_cve_to_attack_mapper_tool
from app.agents.tools.exploit_tools import (
    create_exploit_db_tool,
    create_metasploit_module_tool,
    create_nuclei_template_tool,
)
from app.agents.tools.attack_tools import (
    create_attack_technique_tool,
)
from app.agents.tools.compliance_tools import (
    create_framework_control_tool,
    create_cis_benchmark_tool,
    create_gap_analysis_tool,
)
from app.agents.tools.threat_intel_tools import (
    create_otx_pulse_tool,
    create_virustotal_tool,
)
from app.agents.tools.analysis_tools import (
    create_attack_path_builder_tool,
    create_risk_calculator_tool,
    create_remediation_prioritizer_tool,
)
from app.agents.tools.tavily_tool import create_tavily_search_tool
from app.agents.tools.cwe_capec_cis_tools import (
    create_attack_stored_control_risk_tool,
    create_capec_lookup_tool,
    create_cis_controls_search_tool,
    create_cwe_lookup_tool,
    create_cwe_to_attack_intel_tool,
)
from app.agents.tools.threat_intel_data_tools import (
    create_attack_enterprise_technique_db_tool,
    create_cisa_kev_db_tool,
    create_cwe_capec_attack_mappings_db_tool,
    create_nvd_cves_by_cwe_db_tool,
    create_semantic_attack_control_mapping_search_tool,
    create_semantic_attack_technique_search_tool,
    create_semantic_cwe_capec_attack_search_tool,
)

# Export base classes
from app.agents.tools.base import ToolResult, SecurityTool

__all__ = [
    # Base classes
    "ToolResult",
    "SecurityTool",
    # Tool creators
    "create_cve_intelligence_tool",
    "create_epss_lookup_tool",
    "create_cisa_kev_tool",
    "create_github_advisory_tool",
    "create_cpe_lookup_tool",
    "create_cve_to_attack_tool",
    "create_attack_to_control_tool",
    "create_cpe_resolver_tool",
    "create_exploit_db_tool",
    "create_metasploit_module_tool",
    "create_nuclei_template_tool",
    "create_attack_technique_tool",
    "create_framework_control_tool",
    "create_cis_benchmark_tool",
    "create_gap_analysis_tool",
    "create_otx_pulse_tool",
    "create_virustotal_tool",
    "create_attack_path_builder_tool",
    "create_risk_calculator_tool",
    "create_remediation_prioritizer_tool",
    "create_tavily_search_tool",
    "create_attack_control_mapping_tool",
    "create_tactic_contextualiser_tool",
    "create_framework_item_retrieval_tool",
    "create_cve_enrichment_tool",
    "create_cve_to_attack_mapper_tool",
    "create_cwe_lookup_tool",
    "create_capec_lookup_tool",
    "create_cis_controls_search_tool",
    "create_cwe_to_attack_intel_tool",
    "create_attack_stored_control_risk_tool",
    "create_nvd_cves_by_cwe_db_tool",
    "create_cisa_kev_db_tool",
    "create_attack_enterprise_technique_db_tool",
    "create_semantic_attack_technique_search_tool",
    "create_semantic_attack_control_mapping_search_tool",
    "create_cwe_capec_attack_mappings_db_tool",
    "create_semantic_cwe_capec_attack_search_tool",
    # Registry function
    "get_all_tools",
    "TOOL_REGISTRY",
]


# ============================================================================
# Tool Registry
# Matches the design document's TOOL_REGISTRY structure
# ============================================================================

TOOL_REGISTRY = {
    # === CVE & Vulnerability Intelligence ===
    "cve_details": create_cve_intelligence_tool,  # Alias for cve_intelligence
    "cve_intelligence": create_cve_intelligence_tool,
    "epss_lookup": create_epss_lookup_tool,
    "cisa_kev_check": create_cisa_kev_tool,
    "github_advisory_search": create_github_advisory_tool,
    "cpe_lookup": create_cpe_lookup_tool,
    
    # === Exploit Intelligence ===
    "exploit_db_search": create_exploit_db_tool,
    "metasploit_module_search": create_metasploit_module_tool,
    "nuclei_template_search": create_nuclei_template_tool,
    
    # === ATT&CK Framework ===
    "attack_technique_lookup": create_attack_technique_tool,
    "cve_to_attack_mapper": create_cve_to_attack_tool,
    "attack_to_control_mapper": create_attack_control_mapping_tool,
    "attack_control_map": create_attack_control_mapping_tool,
    "attack_tactic_contextualise": create_tactic_contextualiser_tool,
    "framework_item_retrieval": create_framework_item_retrieval_tool,
    "cve_enrich": create_cve_enrichment_tool,
    "cve_to_attack_map": create_cve_to_attack_mapper_tool,
    
    # === Asset & Infrastructure ===
    "cpe_resolver": create_cpe_resolver_tool,
    # Note: shodan_search and asset_vulnerability_lookup not yet implemented
    # "shodan_search": create_shodan_tool,
    # "asset_vulnerability_lookup": create_asset_vulnerability_tool,
    
    # === Detection Engineering ===
    # Note: sigma_rule_search and generate_sigma_rule not yet implemented
    # "sigma_rule_search": create_sigma_rule_tool,
    # "generate_sigma_rule": create_sigma_rule_generator_tool,
    
    # === Compliance & Frameworks ===
    "framework_control_search": create_framework_control_tool,
    "cis_benchmark_lookup": create_cis_benchmark_tool,
    "gap_analysis": create_gap_analysis_tool,
    
    # === Threat Intelligence ===
    "otx_pulse_search": create_otx_pulse_tool,
    "virustotal_lookup": create_virustotal_tool,
    "cwe_lookup": create_cwe_lookup_tool,
    "capec_lookup": create_capec_lookup_tool,
    "cwe_to_attack_intel": create_cwe_to_attack_intel_tool,
    # === CIS / stored mappings ===
    "cis_controls_search": create_cis_controls_search_tool,
    "attack_stored_control_risk": create_attack_stored_control_risk_tool,
    # threat_intel_data → Postgres + vector collections
    "nvd_cves_by_cwe_db": create_nvd_cves_by_cwe_db_tool,
    "cisa_kev_db": create_cisa_kev_db_tool,
    "attack_enterprise_technique_db": create_attack_enterprise_technique_db_tool,
    "semantic_attack_technique_search": create_semantic_attack_technique_search_tool,
    "semantic_attack_control_mapping_search": create_semantic_attack_control_mapping_search_tool,
    "cwe_capec_attack_mappings_db": create_cwe_capec_attack_mappings_db_tool,
    "semantic_cwe_capec_attack_search": create_semantic_cwe_capec_attack_search_tool,
    
    # === Analysis & Synthesis ===
    "attack_path_builder": create_attack_path_builder_tool,
    "risk_calculator": create_risk_calculator_tool,
    "remediation_prioritizer": create_remediation_prioritizer_tool,
    
    # === Web Search ===
    "tavily_search": create_tavily_search_tool,
}


def get_all_tools() -> List[BaseTool]:
    """
    Get all available security intelligence tools as LangChain tools.
    
    Returns:
        List of LangChain BaseTool instances ready for use with agents.
    """
    tools = []
    
    for tool_name, tool_creator in TOOL_REGISTRY.items():
        try:
            tool = tool_creator()
            tools.append(tool)
        except Exception as e:
            # Log error but continue loading other tools
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load tool {tool_name}: {e}")
    
    return tools


def get_tools_by_category(category: str) -> List[BaseTool]:
    """
    Get tools filtered by category.
    
    Args:
        category: One of "api", "database", "exploit", "compliance", 
                  "threat_intel", "attack", "analysis", "search"
    
    Returns:
        List of tools in the specified category
    """
    category_map = {
        "api": [
            "cve_intelligence",
            "epss_lookup",
            "cisa_kev_check",
            "github_advisory_search",
            "cpe_lookup",
        ],
        "database": [
            "cve_to_attack_mapper",
            "attack_to_control_mapper",
            "cpe_resolver",
            "framework_control_search",
            "cwe_lookup",
            "capec_lookup",
            "cwe_to_attack_intel",
            "attack_stored_control_risk",
            "nvd_cves_by_cwe_db",
            "cisa_kev_db",
            "attack_enterprise_technique_db",
            "cwe_capec_attack_mappings_db",
        ],
        "exploit": [
            "exploit_db_search",
            "metasploit_module_search",
            "nuclei_template_search",
        ],
        "compliance": [
            "framework_control_search",
            "cis_benchmark_lookup",
            "gap_analysis",
            "cis_controls_search",
        ],
        "threat_intel": [
            "otx_pulse_search",
            "virustotal_lookup",
            "cwe_lookup",
            "capec_lookup",
            "cwe_to_attack_intel",
            "nvd_cves_by_cwe_db",
            "cisa_kev_db",
            "attack_enterprise_technique_db",
            "semantic_attack_technique_search",
            "semantic_attack_control_mapping_search",
            "cwe_capec_attack_mappings_db",
            "semantic_cwe_capec_attack_search",
        ],
        "attack": [
            "attack_technique_lookup",
            "cve_to_attack_mapper",
            "attack_to_control_mapper",
            "attack_stored_control_risk",
            "cwe_to_attack_intel",
            "attack_enterprise_technique_db",
            "semantic_attack_technique_search",
            "semantic_attack_control_mapping_search",
            "semantic_cwe_capec_attack_search",
        ],
        "analysis": [
            "attack_path_builder",
            "risk_calculator",
            "remediation_prioritizer",
        ],
        "search": [
            "tavily_search",
            "semantic_attack_technique_search",
            "semantic_attack_control_mapping_search",
            "semantic_cwe_capec_attack_search",
        ],
    }
    
    tool_names = category_map.get(category, [])
    tools = []
    
    for tool_name in tool_names:
        if tool_name in TOOL_REGISTRY:
            try:
                tool = TOOL_REGISTRY[tool_name]()
                tools.append(tool)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to load tool {tool_name}: {e}")
    
    return tools
