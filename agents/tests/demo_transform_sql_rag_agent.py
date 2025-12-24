import asyncio
import logging
from typing import Dict, List, Optional
import json

from app.agents.nodes.transform.transform_sql_rag_agent import create_transform_sql_rag_agent
from app.core.dependencies import get_llm, get_doc_store_provider
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper

# Configure logging
logging.getLogger("app.storage.documents").setLevel(logging.WARNING)
logging.getLogger("agents.app.storage.documents").setLevel(logging.WARNING)

logger = logging.getLogger("lexy-ai-service")


class TransformSQLRAGAgentDemo:
    """Demo class for testing TransformSQLRAGAgent with local Chroma store"""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TransformSQLRAGAgentDemo, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                # Initialize dependencies using local Chroma store from dependencies.py
                self.llm = get_llm(temperature=0.0, model="gpt-4o-mini")
                self.doc_store_provider = get_doc_store_provider()
                self.engine = EngineProvider.get_engine()
                self.retrieval_helper = RetrievalHelper()
                
                # Create Transform SQL RAG Agent
                self.transform_agent = create_transform_sql_rag_agent(
                    llm=self.llm,
                    engine=self.engine,
                    document_store_provider=self.doc_store_provider,
                    retrieval_helper=self.retrieval_helper
                )
                
                self._initialized = True
                logger.info("TransformSQLRAGAgentDemo initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize TransformSQLRAGAgentDemo: {e}")
                self._initialization_failed = True
                self._initialized = True

    async def process_transform_question(
        self,
        user_question: str,
        project_id: str,
        knowledge: Optional[List[str]] = None,
        contexts: Optional[List[str]] = None,
        language: str = "English",
        **kwargs
    ) -> Dict:
        """
        Process a transform question and return the generated SQL with reasoning.
        
        Args:
            user_question: The user's question requiring transform SQL
            project_id: The project ID
            knowledge: Additional knowledge context (optional)
            contexts: Schema contexts (optional, will be retrieved if not provided)
            language: Language for generation (default: "English")
            **kwargs: Additional arguments
            
        Returns:
            Dict containing the transform SQL results
        """
        try:
            logger.info(f"Processing transform question: {user_question}")
            logger.info(f"Project ID: {project_id}")
            
            # Process transform request
            result = await self.transform_agent.process_transform_request(
                query=user_question,
                knowledge=knowledge or [],
                contexts=contexts or [],
                language=language,
                project_id=project_id,
                **kwargs
            )
            
            logger.info(f"Transform result success: {result.get('success', False)}")
            
            return {
                "status": "success" if result.get("success") else "error",
                "result": result,
                "question": user_question
            }
            
        except Exception as e:
            logger.error(f"Error processing transform question: {e}")
            return {
                "status": "error",
                "error": str(e),
                "question": user_question
            }


async def run_transform_demo():
    """Run a demo of the Transform SQL RAG Agent with multiple test cases"""
    
    # Initialize demo
    demo = TransformSQLRAGAgentDemo()
    
    # Enhanced knowledge context for vulnerability/risk analytics
    # All metadata tables are available in mdl_knowledge_metadata.json
    # SQL functions for calculations are available in sql_functions.json
    # Calculated fields (raw_impact, raw_likelihood, raw_risk, bastion_impact, propagation_impact) 
    # are computed using enum metadata tables, SQL functions, and impact_class_enum logic
    """vulnerability_knowledge = [
        "sql_functions_for_impact_calculation: Use SQL functions from sql_functions.json for calculating impact scores. calculate_asset_impact_class_score(impact_class) returns numeric_score (0-100) from risk_impact_metadata. calculate_propagation_impact_score(propagation_class) returns numeric_score (0-100) from risk_impact_metadata. calculate_combined_asset_impact_score(impact_class, propagation_class, weight1, weight2) combines both with weighted average. calculate_asset_exposure_score(propagation_class) returns exposure score for breach method likelihood. calculate_asset_context_multiplier(combined_impact, asset_impact, bastion_impact, propagation_impact_score, propagation_impact, exposure_score) calculates weighted asset context multiplier. Always use these functions instead of manual joins when calculating impact scores.",
        "asset_network_to_propagation_risk: Calculate risk propagation through network relationships. Path: Asset -> Network_Relationships -> Asset -> HAS_VULNERABILITY -> Vulnerability. Nodes traversed: Asset, Asset, Vulnerability. Input attributes: propagation_class, is_bastion_device, propagation_impact, trust_relationships. Calculations performed: Identify bastion devices, Calculate lateral movement risk, Assess blast radius. Use calculate_propagation_impact_score(a.propagation_class) function to get propagation impact scores from risk_impact_metadata. For bastion devices, combine propagation_impact with bastion_impact using weighted formula. SQL pattern: SELECT asset, propagation_class, bastion_impact, calculate_propagation_impact_score(propagation_class) as propagation_impact FROM assets WHERE is_bastion_device = TRUE",
        "asset_classification_type_impact: Asset classification types (canonical_type, device_type, platform, os_type) are used in the classification step to determine asset impact classes. Use asset_classification_metadata table from mdl_knowledge_metadata.json to get classification descriptions, criticality_score, and risk_weight for classification decisions. Higher criticality scores influence impact class classification. Join assets with asset_classification_metadata using classification_type and code to get criticality_score and other metadata attributes needed for classification. After classification, these scores can be used in impact calculations. For calculated fields, use SQL functions when available instead of manual joins.",
        "asset_impact_classification_methodology: Asset impact calculation follows a two-step methodology. Step 1 - Classification: Classify assets into impact classes (Mission Critical, Critical, Other) based on metadata-driven classification rules. Use asset metadata tables (roles_metadata, asset_classification_metadata, risk_impact_metadata) and asset attributes (is_bastion_device, device_impact, admin roles, etc.) to determine the appropriate impact_class. Classification should be driven by metadata rules and asset characteristics rather than hardcoded logic. Step 2 - Impact Calculation: Once impact_class is determined, calculate the numeric impact score using calculate_asset_impact_class_score(impact_class) function which returns numeric_score (0-100) from risk_impact_metadata table. The classification metadata (from mdl_knowledge_metadata.json) defines the mapping from impact_class enum values to numeric scores. Example workflow: First classify asset using metadata joins and CASE logic based on asset characteristics, then apply calculate_asset_impact_class_score(impact_class) to get the numeric impact score.",
        "calculated_impact_fields: Assets have calculated fields that need to be computed: raw_impact (raw impact score if asset were compromised), raw_likelihood (raw likelihood score of asset being compromised), raw_risk (raw risk score based on security factors), bastion_impact (impact score for bastion hosts), propagation_impact (impact score based on lateral movement potential). Calculation methodology: First classify assets based on metadata to determine impact_class and propagation_class, then calculate numeric scores using SQL functions. Use calculate_asset_impact_class_score(impact_class) for impact_class-based scores (requires impact_class to be classified first), calculate_propagation_impact_score(propagation_class) for propagation impact (requires propagation_class to be classified first), calculate_combined_asset_impact_score(impact_class, propagation_class, 0.7, 0.3) for combined impact. For bastion_impact, first classify asset, then combine is_bastion_device flag with impact_class score. For raw_impact, first classify asset to get impact_class, then use calculate_combined_asset_impact_score. For raw_risk, combine impact and likelihood scores with asset context multiplier using calculate_asset_context_multiplier function.",
        "propagation_risk_score_calculation: To calculate propagation_risk_score that combines propagation_class impact and bastion device status: Use calculate_propagation_impact_score(a.propagation_class) to get base propagation impact (0-100). For bastion devices, multiply by bastion multiplier (typically 1.2-1.5) or add bastion_impact score. Formula: CASE WHEN is_bastion_device THEN calculate_propagation_impact_score(propagation_class) * 1.3 + COALESCE(bastion_impact, 0) ELSE calculate_propagation_impact_score(propagation_class) END as propagation_risk_score. Alternatively, use calculate_combined_asset_impact_score with appropriate weights if both impact_class and propagation_class are available.",
        "vulnerability_risk_scoring: Comprehensive risk score combines CVSS base score, exploitability score, impact score, time urgency factors, CISA exploit multipliers, and asset context. Use calculate_base_risk_score(cvssv3_basescore, exploitability_score, impact_score, severity_weight, state_risk_score) function. Use calculate_comprehensive_risk_score(base_risk_score, cisa_multiplier, time_urgency_factor, patch_penalty, asset_context_multiplier) for final score. Use calculate_risk_category(risk_score) to categorize. Use cvss_metadata table from mdl_knowledge_metadata.json for CVSS component weights. Use risk_impact_metadata for impact_class and vuln_level scores. Time-weighted statistics use exponential decay with configurable tau_zero (default 30 days) via calculate_time_weighted_stats function.",
        "breach_method_likelihood: Breach method likelihoods are calculated at asset level considering exploitability, impact, CISA exploits, patch availability, and dwell time. Use calculate_breach_method_likelihood(cve_id, exploitability_score, impact_score, has_known_exploit, has_patch_available, dwell_time_days, asset_exposure_score) function which returns TABLE with breach_method and likelihood_score. Use calculate_asset_exposure_score(propagation_class) to get asset exposure score. Use breach_method_metadata table from mdl_knowledge_metadata.json to get risk_score, exploitability_score, impact_score, and weight for each breach method. Higher likelihood scores indicate greater attack vector probability.",
        "time_weighted_risk: Time-weighted risk uses exponential decay to emphasize recent vulnerabilities. Use calculate_time_weighted_stats(value, time_delta_days, tau_zero) function which returns TABLE with exp_factor, mu_hat, lambda_hat, n_hat. Gamma distribution parameters (alpha, beta) are calculated from time-weighted statistics for trend forecasting. Default tau_zero is 30.0 days.",
        "enum_metadata_usage: All enum metadata tables are in mdl_knowledge_metadata.json schema. Key tables: risk_impact_metadata (enum_type: impact_class, propagation_class, vuln_level), asset_classification_metadata (classification_type: canonical_type, device_type, platform, os_type), breach_method_metadata, roles_metadata, cvss_metadata, int_strength_level_metadata. Use these tables to get numeric_score, weight, priority_order, and criticality_score for calculations. Always join using enum_type/code or classification_type/code depending on table structure. Prefer using SQL functions (calculate_asset_impact_class_score, calculate_propagation_impact_score, etc.) over manual joins when available.",
        "risk_issues_enum_structure: Risk issues are categorized into BaseRiskIssues (base risk issues like weak passwords, vulnerable software, insecure services) and DerivedRiskIssues (combinations of base issues with asset classifications: MC_PERIMETER, PRIVILEGED, IMP_PERIMETER, PERIMETER, MC_CORE, IMP_CORE, CORE). RiskIssueLevels: CRITICAL (highest), HIGH, MEDIUM. RiskIssueStates: ACTIVE, ACCEPTED_BY_USER, ACCEPTED_ML_INFERENCE, MITIGATED, REMEDIATED, ERROR, DROP. Base risk issues include: WEAK_MODERATE_CLIENT_PASSWORDS, DEFAULT_CLIENT_PASSWORDS, NO_CLIENT_PASSWORDS, VULNERABLE_SW_OS, VULNERABLE_SW_APP, UNPATCHED_VULNERABLE_SW_OS, UNPATCHED_VULNERABLE_SW_APP, OBSOLETE_SW_OS, OBSOLETE_SW_APP, ADMIN_ACCESS_SEVERAL_DEVICES, RISKY_ADMIN_ACCESS, CACHED_ADMIN_CREDS, UNENCRYPTED_SAAS_SOCIAL, WEAK_ENCRYPTION_INTRA, WEAK_ENCRYPTION_INTER, BAD_CERT_CLICK_INTER, NON_CLIENT_WEB_BROWSING, MALWARE_DOMAINS_VISITED, SPEAR_PHISHING, DRIVEBY_PHISHING, PWD_REUSE, HIGH_LSC_SCORE_IMP_DEVICE, PWD_IN_CLEAR, BAD_CERT_USE, UNENCRYPTED_ADMIN_TRAFFIC, INSECURE_SERVICE_DETECTED, MISCONFIG_SERVICE_DETECTED, and various insecure protocol issues (UUCP_540, TELNET_23, FTP_21, LDAP_389, RSYNC_873, POP3_110, IMAP_143, HTTP_80_NETWORKING, X11_60XX), plus cloud security issues.",
        "device_impact_calculation_from_risk_issues: To calculate device_impact based on risk issues present on a device: Step 1: Identify all active risk issues for the device (state='ACTIVE' or state IS NULL). Step 2: Map each base risk issue to its impact score using risk_issues_metadata table (if available) or use default weights: CRITICAL risk issues=100.0, HIGH=70.0, MEDIUM=50.0. Step 3: For derived risk issues, extract base issue and asset classification, then apply classification multiplier: MC_PERIMETER=1.5, PRIVILEGED=1.4, IMP_PERIMETER=1.3, PERIMETER=1.2, MC_CORE=1.3, IMP_CORE=1.2, CORE=1.1. Step 4: Aggregate impact scores: SUM(risk_issue_score * classification_multiplier) / COUNT(DISTINCT risk_issue_type) for normalization, or use MAX(risk_issue_score * classification_multiplier) for worst-case impact. Step 5: Cap device_impact at 100.0. SQL pattern: SELECT dev_id, CASE WHEN MAX(rim.numeric_score * CASE WHEN ri.asset_classification LIKE '%MC_PERIMETER%' THEN 1.5 WHEN ri.asset_classification LIKE '%PRIVILEGED%' THEN 1.4 WHEN ri.asset_classification LIKE '%IMP_PERIMETER%' THEN 1.3 WHEN ri.asset_classification LIKE '%PERIMETER%' THEN 1.2 WHEN ri.asset_classification LIKE '%MC_CORE%' THEN 1.3 WHEN ri.asset_classification LIKE '%IMP_CORE%' THEN 1.2 WHEN ri.asset_classification LIKE '%CORE%' THEN 1.1 ELSE 1.0 END) > 100 THEN 100.0 ELSE MAX(rim.numeric_score * multiplier) END as device_impact FROM risk_issues ri JOIN risk_impact_metadata rim ON rim.enum_type='risk_level' AND rim.code=ri.risk_level WHERE ri.state='ACTIVE' GROUP BY dev_id.",
        "device_risk_calculation_from_risk_issues: To calculate device_risk combining device_impact and device_breach_likelihood: Step 1: Calculate device_impact using risk issues (see device_impact_calculation_from_risk_issues). Step 2: Calculate device_breach_likelihood using risk issues (see device_breach_likelihood_calculation_from_risk_issues). Step 3: Combine using formula: device_risk = (device_impact * 0.6) + (device_breach_likelihood * 0.4) for balanced risk, or device_risk = SQRT(device_impact * device_breach_likelihood) for multiplicative risk, or device_risk = MAX(device_impact, device_breach_likelihood) for worst-case risk. Step 4: Apply asset context multiplier if available: device_risk = device_risk * calculate_asset_context_multiplier(...). Step 5: Cap device_risk at 100.0. SQL pattern: SELECT dev_id, LEAST(100.0, (device_impact * 0.6 + device_breach_likelihood * 0.4) * COALESCE(asset_context_multiplier, 1.0)) as device_risk FROM (SELECT dev_id, device_impact, device_breach_likelihood, calculate_asset_context_multiplier(...) as asset_context_multiplier FROM device_metrics) dm.",
        "device_breach_likelihood_calculation_from_risk_issues: To calculate device_breach_likelihood based on risk issues present on a device: Step 1: Identify all active risk issues for the device (state='ACTIVE' or state IS NULL). Step 2: Categorize risk issues by attack vector: Password issues (WEAK_MODERATE_CLIENT_PASSWORDS, DEFAULT_CLIENT_PASSWORDS, NO_CLIENT_PASSWORDS, PWD_REUSE, PWD_IN_CLEAR) weight=0.25, Vulnerability issues (VULNERABLE_SW_OS, VULNERABLE_SW_APP, UNPATCHED_VULNERABLE_SW_OS, UNPATCHED_VULNERABLE_SW_APP, OBSOLETE_SW_OS, OBSOLETE_SW_APP) weight=0.30, Trust relationship issues (ADMIN_ACCESS_SEVERAL_DEVICES, RISKY_ADMIN_ACCESS, CACHED_ADMIN_CREDS) weight=0.20, Encryption/Protocol issues (UNENCRYPTED_SAAS_SOCIAL, WEAK_ENCRYPTION_INTRA, WEAK_ENCRYPTION_INTER, BAD_CERT_CLICK_INTER, BAD_CERT_USE, UNENCRYPTED_ADMIN_TRAFFIC, INSECURE_SERVICE_DETECTED, insecure protocols) weight=0.15, Phishing issues (NON_CLIENT_WEB_BROWSING, MALWARE_DOMAINS_VISITED, SPEAR_PHISHING, DRIVEBY_PHISHING) weight=0.10. Step 3: Calculate likelihood per category: SUM(risk_issue_likelihood_score * category_weight) for each category. Step 4: Combine categories: device_breach_likelihood = MAX(category_likelihoods) for worst-case, or AVG(category_likelihoods) for average, or SQRT(SUM(category_likelihoods^2)) for weighted combination. Step 5: Apply time-weighted factors if available (recent issues have higher weight). Step 6: Cap device_breach_likelihood at 100.0. SQL pattern: SELECT dev_id, LEAST(100.0, GREATEST(pwd_likelihood * 0.25, vuln_likelihood * 0.30, trust_likelihood * 0.20, enc_likelihood * 0.15, phish_likelihood * 0.10)) as device_breach_likelihood FROM (SELECT dev_id, SUM(CASE WHEN ri.risk_issue_type IN ('WEAK_MODERATE_CLIENT_PASSWORDS', 'DEFAULT_CLIENT_PASSWORDS', ...) THEN rim.numeric_score ELSE 0 END) as pwd_likelihood, ... FROM risk_issues ri JOIN risk_impact_metadata rim ON rim.enum_type='risk_level' AND rim.code=ri.risk_level WHERE ri.state='ACTIVE' GROUP BY dev_id) category_scores.",
        "risk_issues_metadata_usage: Risk issues enum metadata should be stored in risk_issues_metadata table (if available) or risk_impact_metadata table with enum_type='risk_issue'. Each risk issue has: risk_issue_code (enum value like 'WEAK_MODERATE_CLIENT_PASSWORDS'), risk_level (CRITICAL, HIGH, MEDIUM), numeric_score (0-100), weight (0-1), priority_order (1=highest), category (password, vulnerability, trust_relationship, encryption, phishing, misconfig, cloud), attack_vector_likelihood (0-100), impact_score (0-100). Join risk_issues table with risk_issues_metadata using risk_issue_code. For derived risk issues, parse asset_classification suffix (MC_PERIMETER, PRIVILEGED, etc.) and apply classification multiplier. Use risk_level to get numeric_score from risk_impact_metadata where enum_type='risk_level'. Aggregate risk issues per device using SUM, MAX, or AVG depending on calculation method. Filter by state='ACTIVE' to only count active risk issues. Use time-weighted factors if risk_issues table has detected_time or created_at fields."
    ]"""


    vulnerability_knowledge = [
        
        # =============================================================================
        # ASSET IMPACT CLASSIFICATION AND CALCULATION
        # =============================================================================
        
        "asset_impact_mission_critical_classification: To classify an asset as Mission Critical, check if any of these conditions are true: (1) The asset has impact_class explicitly set to 'Mission Critical' in the assets table, OR (2) The asset has admin roles - join assets.roles with the roles metadata table using appropriate relationship keys where is_admin_role=TRUE, check for roles like NW-ADMIN or WIN-ADMIN, OR (3) The asset has high-criticality services - join assets.roles with the roles metadata table where criticality_score >= 90, check for roles like DNS, DHCP, LDAP, Kerb, MSSQL, SAP-HANA, HYPERVISOR, Database-Instance, Kubernetes, BCA, OR (4) The asset has CMDB classification - check if roles contain BCA, CRITICAL, or VITAL from the roles metadata table where role_category='cmdb', OR (5) The asset is a bastion device - check if is_bastion_device=TRUE in assets table. If any condition is true, classify as Mission Critical. To calculate the numeric score for Mission Critical classification, identify and query the appropriate metadata tables that contain impact class definitions and their associated numeric scores. Use the metadata definitions for the 'Mission Critical' category to retrieve the numeric score dynamically using SQL - do not hardcode the score. The LLM should identify the best metadata tables that map impact class categories to their numeric scores.",
        
        "asset_impact_critical_classification: To classify an asset as Critical (when not Mission Critical), check if any of these conditions are true: (1) The asset has impact_class explicitly set to 'Critical' in assets table, OR (2) The asset has moderate-criticality services - join assets.roles with the roles metadata table where criticality_score >= 70 AND criticality_score < 90, check for roles like RDP, SSH, VPN, WEB-SRVR, MySQL, Postgres, EXCH, ADC, Hyper-V, Xen, SCCM, CODE-REPO, Compute-Instance, EC2, VPC, OR (3) The asset is a server - join assets with the asset classification metadata table using appropriate relationship keys where classification_type='canonical_type' and code='Servers', OR (4) The asset runs critical operating systems - check if platform in ('Windows', 'Linux/Unix') AND device_type='Servers'. If any condition is true, classify as Critical. To calculate the numeric score for Critical classification, identify and query the appropriate metadata tables that contain impact class definitions and their associated numeric scores. Use the metadata definitions for the 'Critical' category to retrieve the numeric score dynamically using SQL - do not hardcode the score. The LLM should identify the best metadata tables that map impact class categories to their numeric scores.",
        
        "asset_impact_other_classification: To classify an asset as Other (when not Mission Critical or Critical), this is the default classification for all remaining assets including desktops, laptops, mobile devices, IoT devices, and other endpoints. Assets classified as Other typically have device_type in ('Desktops/Laptops', 'Smartphones/Tablets', 'IoT', 'AV/VoIP') or have no high-criticality roles or services. To calculate the numeric score for Other classification, identify and query the appropriate metadata tables that contain impact class definitions and their associated numeric scores. Use the metadata definitions for the 'Other' category to retrieve the numeric score dynamically using SQL - do not hardcode the score. The LLM should identify the best metadata tables that map impact class categories to their numeric scores.",
        
        "asset_impact_cloud_classification: To classify an asset's impact based on cloud asset characteristics, first check if is_cloud_asset=TRUE in the assets table. For cloud assets, join assets with asset_classification_metadata table using appropriate relationship keys to get criticality_score and risk_weight for both device_type (where classification_type='device_type' or classification_type='canonical_type') and platform (where classification_type='platform'). Cloud assets have unique risk profiles: (1) Cloud compute instances (device_type='Servers' or 'Compute-Instance') with high-criticality platforms (Windows, Linux/Unix) should be classified as Mission Critical if criticality_score >= 90 from metadata, OR Critical if criticality_score >= 70 AND criticality_score < 90, (2) Cloud storage assets (device_type='Storage Assets') should be classified based on metadata criticality_score - if >= 85 then Mission Critical, if >= 70 then Critical, (3) Cloud networking assets (device_type='Networking Assets' or roles contain VPC, Load-Balancer) should be classified as Critical if criticality_score >= 75 from metadata, (4) Cloud containers (device_type='Container' or roles contain Kubernetes, Docker) should be classified based on metadata criticality_score - if >= 80 then Critical, otherwise Other, (5) For other cloud asset types, use the criticality_score from asset_classification_metadata to determine classification: Mission Critical if criticality_score >= 90, Critical if criticality_score >= 70 AND criticality_score < 90, Other if criticality_score < 70. The platform criticality_score should be combined with device_type criticality_score using weighted average: combined_criticality = (device_type_criticality * 0.6) + (platform_criticality * 0.4). To calculate the numeric score for cloud asset impact classification, identify and query the appropriate metadata tables that contain impact class definitions and their associated numeric scores. Use the metadata definitions for the determined impact class category (Mission Critical, Critical, or Other) to retrieve the numeric score dynamically using SQL - do not hardcode the score. The LLM should identify the best metadata tables that map impact class categories to their numeric scores. Cloud assets often have shared responsibility model implications and may require different risk weighting than on-premises assets.",
        
        "asset_propagation_perimeter_classification: To classify an asset as Perimeter network class, analyze the asset's network interfaces by joining the assets table with the network interfaces table using the appropriate relationship keys. For each interface, determine if it is perimeter-facing by examining the interface's access type: (1) Check subnet classification - interfaces with public IP subnets (not in private ranges 10.x.x.x, 172.16-31.x.x, 192.168.x.x, 127.x.x.x, or 100.x.x.x) indicate perimeter access, (2) Check IP address ranges - public IP addresses indicate external-facing interfaces, (3) Check site location - interfaces in DMZ, perimeter, or external sites indicate perimeter access, (4) Check subnet classification calculated field if available - 'Public/Other' indicates perimeter access. If any interface on the asset has perimeter access characteristics, classify the asset as Perimeter. To calculate the numeric score for Perimeter classification, identify and query the appropriate metadata tables that contain propagation class definitions and their associated numeric scores. Use the metadata definitions for the 'Perimeter' category to retrieve the numeric score dynamically using SQL - do not hardcode the score. The LLM should identify the best metadata tables that map propagation class categories to their numeric scores. Perimeter assets are at the network edge and have higher exposure to external threats.",
        
        "asset_propagation_core_classification: To classify an asset as Core network class (when not Perimeter), first check all network interfaces for the asset by joining the assets table with the network interfaces table using the appropriate relationship keys. If all interfaces have private IP ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x), are in internal sites, or have subnet classification indicating private networks, classify as Core. Core assets are internal-only and not exposed to the internet perimeter. To calculate the numeric score for Core classification, identify and query the appropriate metadata tables that contain propagation class definitions and their associated numeric scores. Use the metadata definitions for the 'Core' category to retrieve the numeric score dynamically using SQL - do not hardcode the score. The LLM should identify the best metadata tables that map propagation class categories to their numeric scores. Core classification is the default when asset does not meet Perimeter criteria based on interface analysis.",
        
        "asset_combined_impact_calculation: To calculate the final combined asset impact score, first classify the asset to determine its impact_class (Mission Critical, Critical, or Other) and propagation_class (Perimeter or Core). Then use calculate_combined_asset_impact_score(impact_class, propagation_class, 0.7, 0.3) function with weights 0.7 for impact_class and 0.3 for propagation_class. This gives formula: (impact_class_score * 0.7) + (propagation_class_score * 0.3). For example, a Mission Critical Perimeter asset gets (100 * 0.7) + (80 * 0.3) = 70 + 24 = 94.0 combined impact score.",
        
        "asset_bastion_impact_calculation: To calculate bastion_impact for bastion devices, first check if is_bastion_device=TRUE in assets table. For bastion devices, calculate enhanced impact by multiplying the propagation impact by a bastion multiplier. Use formula: bastion_impact = calculate_propagation_impact_score(propagation_class) * 1.3 + calculate_asset_impact_class_score(impact_class) * 0.2. This applies 30% increase for bastion status plus 20% of base impact. Bastion devices are jump hosts that provide access to other systems, so compromising them has cascading impact. Cap the final score at 100.0.",
        
        "asset_raw_impact_calculation: To calculate raw_impact representing the inherent impact if an asset were compromised regardless of current vulnerabilities, first classify the asset to get impact_class and propagation_class. Then use calculate_combined_asset_impact_score(impact_class, propagation_class, 0.7, 0.3). If the asset is a bastion device, add additional bastion_impact using formula: raw_impact = combined_impact + (bastion_impact * 0.2). For non-bastion devices, raw_impact equals combined_impact. This represents worst-case impact assuming the asset is fully compromised.",
        
        # =============================================================================
        # ASSET IMPACT BY LOCATION
        # =============================================================================
        
        "asset_impact_by_location_region: To calculate asset impact considering geographic location region, first get base impact using asset classification methodology. Then apply location-based risk weight. Query assets.location_region field and apply regional risk multipliers: High-risk regions (multiply by 1.2): Regions with high cyber threat activity or weak data protection laws. Standard regions (multiply by 1.0): Regions with moderate threat levels and adequate protections. Low-risk regions (multiply by 0.9): Regions with strong cybersecurity infrastructure and strict data protection. Formula: location_adjusted_impact = combined_impact * regional_risk_multiplier. This accounts for geopolitical and regulatory risk variations.",
        
        "asset_impact_by_location_site: To calculate asset impact considering specific site criticality, first get base impact using asset classification. Then join assets.site_name with an internal site_metadata table (if available) that contains site_criticality_score. Apply site-specific multiplier: Critical sites like headquarters, primary datacenters, financial centers (multiply by 1.3). Important sites like regional offices, secondary datacenters (multiply by 1.1). Standard sites like branch offices, remote locations (multiply by 1.0). Formula: site_adjusted_impact = combined_impact * site_criticality_multiplier. Sites housing critical infrastructure or sensitive operations have higher impact.",
        
        "asset_impact_by_location_network_zone: To calculate asset impact considering network zone, use assets.device_zone field to determine security zone placement. Apply zone-based impact adjustments: DMZ/Perimeter zone assets (multiply by 1.4): Highest impact due to external exposure and potential breach entry point. Core/Internal zone assets (multiply by 1.0): Standard impact for internal assets. Isolated/Quarantine zone assets (multiply by 0.8): Lower impact for segmented assets with restricted access. Management zone assets (multiply by 1.5): Highest impact for management network assets that control other systems. Formula: zone_adjusted_impact = combined_impact * zone_risk_multiplier.",
        
        # =============================================================================
        # ASSET IMPACT BY CLASSIFICATION TYPE
        # =============================================================================
        
        "asset_impact_by_device_type: To calculate asset impact considering device type, first classify using impact_class methodology, then apply device_type specific adjustments. Join assets with asset_classification_metadata where classification_type='canonical_type'. Use criticality_score and risk_weight from metadata. Apply formula: device_adjusted_impact = base_impact * device_risk_weight. Servers have highest weight (1.0), Networking Assets (0.95), Storage Assets (0.9), OT Assets (0.95), Containers (0.85), Desktops/Laptops (0.7), Mobile devices (0.6), IoT (0.4). This accounts for inherent device criticality independent of roles.",
        
        "asset_impact_by_platform: To calculate asset impact considering operating system platform, join assets.platform with asset_classification_metadata where classification_type='platform'. Apply platform-specific risk weights: Windows servers (1.0): Highest due to prevalence and attack surface. Linux/Unix servers (0.9): Slightly lower but still critical. macOS systems (0.8): Lower attack frequency. Unknown platforms (0.3): Cannot assess properly. Formula: platform_adjusted_impact = base_impact * platform_risk_weight. Different platforms have different threat landscapes and vulnerability patterns.",
        
        "asset_impact_by_os_type: To calculate asset impact considering detailed OS type, join assets.os_type with asset_classification_metadata where classification_type='os_type'. Apply OS-specific criticality scores: Windows (80.0), Linux/Unix (75.0), Cisco IOS (75.0), Panos (75.0) for network devices have high scores. Mobile OS like iOS (65.0), Android (65.0) have moderate scores. Embedded systems (50.0), Unknown (30.0) have lower scores. Formula: os_adjusted_impact = base_impact * (os_criticality_score / 100). This refines platform assessment with specific OS vulnerabilities.",
        
        # =============================================================================
        # ASSET BREACH LIKELIHOOD CALCULATIONS
        # =============================================================================
        
        "asset_breach_likelihood_from_vulnerabilities: To calculate breach likelihood from CVE vulnerabilities, aggregate vulnerability data per asset. For each asset, sum up vulnerability risk scores weighted by severity. Query vulnerability_instances table joined with assets on nuid and dev_id. Count active vulnerabilities (state='ACTIVE') per severity level. Apply severity weights from risk_impact_metadata where enum_type='vuln_level': CRITICAL (weight 1.0), HIGH (0.75), MEDIUM (0.5), LOW (0.25). Formula: vuln_likelihood = (critical_count * 1.0 + high_count * 0.75 + medium_count * 0.5 + low_count * 0.25) / total_vulns * 100, capped at 100.0. Assets with many critical vulnerabilities have higher breach likelihood.",
        
        "asset_breach_likelihood_from_unpatched_vulnerabilities: To calculate breach likelihood specifically from unpatched vulnerabilities, query vulnerability_instances where state='ACTIVE' AND has_patch_available=TRUE. These are vulnerable with available patches but not yet applied. Count unpatched critical, high, medium vulnerabilities per asset. Apply patch penalty multiplier: each unpatched CRITICAL vuln adds 15 points to likelihood, HIGH adds 10, MEDIUM adds 5. Formula: unpatched_likelihood = (critical_unpatched * 15 + high_unpatched * 10 + medium_unpatched * 5), capped at 100.0. Unpatched vulnerabilities significantly increase breach likelihood as attackers target known fixes.",
        
        "asset_breach_likelihood_from_cisa_exploits: To calculate breach likelihood from CISA Known Exploited Vulnerabilities, query vulnerability_instances where tags LIKE '%CISA Known Exploit%' AND state='ACTIVE'. These vulnerabilities have confirmed active exploitation in the wild. Each CISA exploit significantly increases likelihood. Formula: cisa_likelihood = MIN(cisa_exploit_count * 25, 100.0). If asset has 1 CISA exploit, likelihood is 25. If 2, it's 50. If 3, it's 75. If 4+, capped at 100. CISA exploits represent imminent threat requiring urgent remediation.",
        
        "asset_breach_likelihood_by_propagation_class: To calculate breach likelihood based on network propagation class and exposure, use calculate_asset_exposure_score(propagation_class) function. Perimeter assets have higher exposure scores (80.0) because they face the internet and external threats. Core assets have lower exposure (60.0) as they are internal. Formula: propagation_likelihood = calculate_asset_exposure_score(propagation_class) * asset_vulnerability_count / 100. Multiply exposure score by normalized vulnerability count. Perimeter assets with vulnerabilities are more likely to be breached than Core assets with same vulnerabilities.",
        
        "asset_breach_likelihood_by_dwell_time: To calculate breach likelihood based on vulnerability dwell time (how long vulnerabilities have existed), query vulnerability_instances.dwell_time_days or calculate as CURRENT_DATE - detected_time. Longer dwell time means more opportunity for exploitation. Apply time-based likelihood increase: 0-7 days (low increase, multiply by 1.0), 8-30 days (moderate increase, multiply by 1.2), 31-90 days (high increase, multiply by 1.5), 90+ days (critical increase, multiply by 2.0). Formula: dwell_likelihood = base_likelihood * dwell_time_multiplier. Old vulnerabilities represent persistent exposure and higher breach probability.",
        
        "asset_breach_likelihood_combined: To calculate comprehensive asset breach likelihood combining all factors, use weighted formula that includes: (1) Vulnerability-based likelihood (weight 0.3), (2) Unpatched vulnerability likelihood (weight 0.25), (3) CISA exploit likelihood (weight 0.25), (4) Propagation/exposure likelihood (weight 0.15), (5) Dwell time likelihood (weight 0.05). Formula: combined_breach_likelihood = (vuln_likelihood * 0.3) + (unpatched_likelihood * 0.25) + (cisa_likelihood * 0.25) + (propagation_likelihood * 0.15) + (dwell_likelihood * 0.05), capped at 100.0. This provides holistic breach probability assessment.",
        
        "asset_breach_likelihood_cloud_assets: To calculate breach likelihood for cloud assets, first identify cloud assets by checking is_cloud_asset=TRUE in assets table. For cloud assets, apply cloud-specific breach likelihood factors: (1) Cloud misconfiguration exposure - join with cloud_connector_vuln_metadata or misconfig_instances where cloud_service is not null, multiply base likelihood by 1.2 if misconfigurations present, (2) Public cloud exposure - check if asset has public IP or is in perimeter network, add 15 points to likelihood, (3) Shared responsibility model gaps - cloud assets may have different patching responsibilities, check if vulnerabilities are cloud-provider managed vs customer-managed, apply 0.9 multiplier for provider-managed, 1.1 multiplier for customer-managed, (4) Cloud service criticality - join assets with asset_classification_metadata for device_type and platform, use criticality_score to adjust likelihood: if criticality_score >= 85, multiply by 1.15, if >= 70, multiply by 1.1, otherwise multiply by 1.0, (5) Cloud-native attack vectors - check for cloud-specific risk issues like exposed S3 buckets, unencrypted cloud storage, misconfigured security groups, add 10 points per cloud-specific risk. Formula: cloud_breach_likelihood = (base_likelihood * cloud_misconfig_multiplier * shared_responsibility_multiplier * criticality_multiplier) + public_exposure_penalty + cloud_native_risk_penalty, capped at 100.0. Cloud assets have unique attack surfaces and shared responsibility considerations that affect breach probability.",
        
        # =============================================================================
        # ASSET BREACH LIKELIHOOD BY BREACH METHOD
        # =============================================================================
        
        "asset_breach_likelihood_by_method_unpatched_vulnerability: To calculate breach likelihood via unpatched vulnerability method, use calculate_breach_method_likelihood function with breach method 'unpatched_vulnerability' from breach_method_metadata. This method has base risk_score=85.0, exploitability_score=75.0, weight=0.9. For each asset, calculate: Count active unpatched vulnerabilities (has_patch_available=TRUE, state='ACTIVE'). Get average exploitability and impact scores for those vulnerabilities. Formula: method_likelihood = breach_method_weight * ((avg_exploitability * 0.4) + (avg_impact * 0.3) + (unpatched_count_normalized * 0.3)). Unpatched vulns are common breach method requiring immediate attention.",
        
        "asset_breach_likelihood_by_method_weak_credentials: To calculate breach likelihood via weak credentials method, use breach method 'weak_credentials' from breach_method_metadata (risk_score=60.0, weight=0.65). Check for weak credential indicators: (1) Join with security_strength_metadata where enum_type='credential' and code in ('WEAK', 'DEFAULT', 'EMPTY'), (2) Check for password-related risk issues in risk_issues table, (3) Look for clear password protocols (TELNET, FTP, HTTP) on asset. Formula: weak_cred_likelihood = breach_method_weight * (credential_weakness_score + protocol_weakness_score + risk_issue_score) / 3. Weak credentials are high-probability breach vector.",
        
        "asset_breach_likelihood_by_method_compromised_credentials: To calculate breach likelihood via compromised credentials method, use breach method 'compromised_credentials' from breach_method_metadata (risk_score=90.0, exploitability=85.0, weight=0.95). Check for compromise indicators: (1) Credential reuse across systems (check PWD_REUSE risk issue), (2) Credentials in clear text (check PWD_IN_CLEAR risk issue), (3) Lost/stolen credentials (check HIGH_LSC_SCORE risk issue). Formula: compromised_cred_likelihood = breach_method_weight * ((credential_exposure * 0.4) + (reuse_factor * 0.3) + (cleartext_factor * 0.3)). Compromised credentials are extremely dangerous as they provide direct access.",
        
        "asset_breach_likelihood_by_method_misconfiguration: To calculate breach likelihood via misconfiguration method, use breach method 'misconfiguration' from breach_method_metadata (risk_score=70.0, weight=0.75). Query misconfig_instances table for active misconfigurations on asset. Join with vulnerability_metadata where enum_type='subtype' and code='Misconfigured Services'. Count and score: (1) Security group misconfigurations, (2) Service misconfigurations, (3) Permission misconfigurations. Formula: misconfig_likelihood = breach_method_weight * (misconfig_count * avg_misconfig_severity) / 100. Misconfigurations are often overlooked but exploitable weaknesses.",
        
        "asset_breach_likelihood_by_method_phishing: To calculate breach likelihood via phishing method, use breach method 'phishing' from breach_method_metadata (risk_score=80.0, exploitability=75.0, weight=0.85). Assess phishing risk indicators: (1) Check for web browsing capability (user workstations, mobile devices), (2) Check for email services (SMTP, POP3, IMAP), (3) Review risk issues for NON_CLIENT_WEB_BROWSING, MALWARE_DOMAINS_VISITED, SPEAR_PHISHING. Formula: phishing_likelihood = breach_method_weight * ((web_exposure * 0.4) + (email_exposure * 0.3) + (user_behavior_risk * 0.3)). Phishing targets human users rather than technical vulnerabilities.",
        
        "asset_breach_likelihood_by_method_malicious_insider: To calculate breach likelihood via malicious insider method, use breach method 'malicious_insider' from breach_method_metadata (risk_score=95.0, exploitability=95.0, impact=90.0, weight=1.0). Assess insider risk factors: (1) Admin access privileges (join roles_metadata where is_admin_role=TRUE), (2) Access to sensitive data (high impact_class), (3) Privileged access across multiple systems (check ADMIN_ACCESS_SEVERAL_DEVICES risk issue). Formula: insider_likelihood = breach_method_weight * ((admin_privilege_level * 0.4) + (data_sensitivity * 0.3) + (access_breadth * 0.3)). Malicious insiders have highest impact due to authorized access.",
        
        "asset_breach_likelihood_by_method_trust_relationship: To calculate breach likelihood via trust relationship exploitation, use breach method 'trust_relationship' from breach_method_metadata (risk_score=75.0, weight=0.8). Identify trust relationships: (1) Domain joined systems (check domain_joined in assets), (2) Cached credentials (check CACHED_ADMIN_CREDS risk issue), (3) Privilege escalation paths (check RISKY_ADMIN_ACCESS), (4) Network trust configurations. Formula: trust_likelihood = breach_method_weight * ((domain_trust_exposure * 0.3) + (cached_cred_risk * 0.3) + (lateral_movement_paths * 0.4)). Trust relationships enable lateral movement after initial compromise.",
        
        # =============================================================================
        # ASSET RISK CALCULATIONS
        # =============================================================================
        
        "asset_comprehensive_risk_calculation: To calculate comprehensive asset risk combining impact and likelihood, use formula: asset_risk = (asset_impact * 0.6) + (asset_breach_likelihood * 0.4). This weights impact higher (60%) than likelihood (40%) because impact represents worst-case damage while likelihood is probabilistic. Alternative multiplicative formula: asset_risk = SQRT(asset_impact * asset_breach_likelihood) gives geometric mean. Cap final score at 100.0. Use calculate_risk_category(asset_risk) to classify as CRITICAL (>=90), HIGH (>=70), MEDIUM (>=50), LOW (>=30), or INFORMATIONAL (<30).",
        
        "asset_risk_with_context_multiplier: To calculate asset risk with context multipliers accounting for special circumstances, first calculate base risk as (impact * 0.6 + likelihood * 0.4). Then apply calculate_asset_context_multiplier(combined_impact, asset_impact, bastion_impact, propagation_impact_score, propagation_impact, exposure_score). This function returns multiplier between 0.8 and 1.5 based on: Bastion status (adds 0.3), High propagation impact (adds 0.2), High exposure (adds 0.2), Critical asset classification (adds 0.3). Formula: contextualized_risk = base_risk * context_multiplier, capped at 100.0. Context multipliers account for cascade effects and strategic importance.",
        
        "asset_risk_by_mission_critical_type: To calculate risk specifically for Mission Critical assets, first filter assets where impact_class='Mission Critical' using asset classification methodology. These assets get enhanced risk scoring: Apply Mission Critical multiplier of 1.3 to base risk. Add priority_escalation_factor of +10 points. Use stricter risk thresholds: Risk >=80 is CRITICAL (vs >=90 for normal assets), >=60 is HIGH (vs >=70), >=40 is MEDIUM (vs >=50). Formula: mc_risk = MIN((base_risk * 1.3) + 10, 100.0). Mission Critical assets require accelerated response and lower risk tolerance.",
        
        "asset_risk_by_critical_type: To calculate risk for Critical assets (not Mission Critical), filter assets where impact_class='Critical' using classification methodology. Apply Critical multiplier of 1.15 to base risk. Add priority_escalation_factor of +5 points. Use moderately strict thresholds: Risk >=85 is CRITICAL, >=65 is HIGH, >=45 is MEDIUM. Formula: critical_risk = MIN((base_risk * 1.15) + 5, 100.0). Critical assets are important but below Mission Critical urgency.",
        
        "asset_risk_by_location_sensitive_regions: To calculate risk for assets in sensitive geographic regions (data centers, HQ, financial centers), first identify sensitive locations from assets.location_region, location_city, site_name fields. Apply location_sensitivity_multiplier: Financial centers (1.4), Headquarters (1.3), Primary data centers (1.3), Research facilities (1.2), Standard locations (1.0). Also consider regulatory environment: GDPR regions need data protection (multiply by 1.2), High-compliance regions like healthcare/finance (1.3). Formula: location_risk = base_risk * location_sensitivity_multiplier * regulatory_multiplier, capped at 100.0. Geographic and regulatory factors affect risk posture.",
        
        "asset_risk_cloud_assets: To calculate risk for cloud assets, first identify cloud assets by checking is_cloud_asset=TRUE in assets table. For cloud assets, use the cloud asset impact classification methodology (see asset_impact_cloud_classification) to determine impact_class. Then calculate cloud-specific risk adjustments: (1) Cloud impact multiplier - use the impact_class determined from cloud classification (Mission Critical, Critical, or Other) and retrieve numeric_score from risk_impact_metadata where enum_type='impact_class', (2) Cloud breach likelihood - use asset_breach_likelihood_cloud_assets methodology to get cloud-adjusted likelihood, (3) Cloud shared responsibility risk - cloud assets have shared responsibility model where some security is provider-managed, apply 0.95 multiplier to base risk if provider-managed components are secure, 1.1 multiplier if customer-managed components have gaps, (4) Cloud misconfiguration risk - join with cloud_connector_vuln_metadata or misconfig_instances, add risk points: critical misconfigurations add 20 points, high add 15, medium add 10, (5) Cloud exposure risk - check if asset is publicly accessible or in perimeter, multiply by 1.15 for public cloud assets, (6) Cloud service criticality - join with asset_classification_metadata for device_type and platform, use risk_weight to adjust: cloud_risk = (cloud_impact * 0.6 + cloud_likelihood * 0.4) * shared_responsibility_multiplier * exposure_multiplier * service_risk_weight + misconfig_risk_penalty, capped at 100.0. Cloud assets require consideration of shared responsibility model, cloud-native attack vectors, and different exposure characteristics compared to on-premises assets.",
        
        # =============================================================================
        # SOFTWARE IMPACT AND RISK CALCULATIONS
        # =============================================================================
        
        "asset_software_impact_by_category: To calculate impact of software vulnerabilities by category, join software_instances with vulnerability_instances on sw_instance_id, then join with software_metadata where enum_type='category'. Apply category-based impact weights: OPERATING SYSTEM (1.0, score 90.0): Highest impact as OS compromise affects entire system. SECURITY software (0.95, score 85.0): Critical security tools. APPLICATION (0.8, score 70.0): Moderate impact. BROWSER (0.75, score 65.0): User-facing risk. Formula: sw_category_impact = base_impact * category_weight. Operating system vulnerabilities have cascading effect on all applications.",
        
        "asset_software_impact_by_product_state: To calculate impact based on software product state, join software_instances with software_metadata where enum_type='product_state'. Apply state-based impact multipliers: EOL/End-of-Life (1.0, score 95.0): No patches available, maximum risk. VULNERABLE (0.95, score 90.0): Active vulnerabilities. UNPATCHED (0.9, score 85.0): Patches available but not applied. UPDATABLE (0.5, score 50.0): Updates available. PATCHED (0.2, score 20.0): Minimal risk. Formula: product_state_impact = base_impact * state_risk_multiplier. EOL software should be highest priority for replacement.",
        
        "asset_software_risk_from_vulnerable_software: To calculate software risk from vulnerable software on asset, query software_instances joined with vulnerability_instances where product_state IN ('VULNERABLE', 'UNPATCHED', 'EOL'). For each asset, aggregate: Count vulnerable software packages. Calculate average CVE severity across vulnerable software. Check for critical software (OS, SECURITY category). Formula: sw_vuln_risk = (vuln_software_count * 10) + (avg_cve_severity * 0.5) + (critical_sw_flag * 20), capped at 100.0. Assets with vulnerable system software have highest risk.",
        
        "asset_software_risk_from_eol_software: To calculate risk from End-of-Life software, query software_instances where product_state='EOL'. EOL software receives no security updates. For each asset, count EOL packages and assess criticality. Formula: eol_risk = (eol_os_count * 40) + (eol_security_sw_count * 30) + (eol_app_count * 10), capped at 100.0. Single EOL operating system warrants 40 points. Multiple EOL applications accumulate risk. EOL software represents unmitigatable vulnerability requiring replacement.",
        
        "asset_software_risk_from_unpatched_with_available_patches: To calculate risk from unpatched software where patches exist, query software_instances where product_state='UNPATCHED' joined with vulnerability_instances where has_patch_available=TRUE. Calculate patch lag: days_since_patch_available = CURRENT_DATE - patch_release_time. Apply time-based penalty: 0-7 days (1.0x), 8-30 days (1.3x), 31-90 days (1.7x), 90+ days (2.5x). Formula: unpatched_risk = (unpatched_sw_count * severity_avg * time_multiplier), capped at 100.0. Long patch lag significantly increases risk.",
        
        "asset_total_software_risk: To calculate total software risk combining all software factors for an asset, use weighted combination: (1) Vulnerable software risk (weight 0.35), (2) EOL software risk (weight 0.30), (3) Unpatched software risk (weight 0.25), (4) Software category impact (weight 0.10). Formula: total_sw_risk = (vuln_sw_risk * 0.35) + (eol_risk * 0.30) + (unpatched_risk * 0.25) + (category_impact * 0.10), capped at 100.0. This provides comprehensive software security posture for asset.",
        
        # =============================================================================
        # TIME-WEIGHTED RISK AND TRENDING
        # =============================================================================
        
        "asset_risk_time_weighted_recent_focus: To calculate time-weighted risk emphasizing recent vulnerabilities, use calculate_time_weighted_stats(risk_value, time_delta_days, tau_zero=30.0) function with 30-day decay constant. For each vulnerability, calculate days_ago = CURRENT_DATE - detected_time. Apply exponential decay: weight = exp(-days_ago / 30.0). Recent vulnerabilities (0-7 days) get weight near 1.0. 30-day old vulnerabilities get weight 0.37. 90-day old get weight 0.05. Formula: weighted_risk = SUM(vuln_risk * exp(-days_ago/30)) / SUM(exp(-days_ago/30)). This prioritizes newly discovered vulnerabilities requiring urgent attention.",
        "asset_risk_trend_increasing_vulnerability_count: To detect assets with increasing vulnerability trend, query vulnerability_instances with time-series grouping. Compare vulnerability counts: current_month_count vs previous_month_count vs 3_months_ago_count. Calculate trend: trend_direction = (current - previous) / previous * 100 for percentage change. Flag as Increasing if trend > 20%, Stable if -20% to +20%, Decreasing if < -20%. Formula: trend_risk_adjustment = base_risk * (1 + (trend_percentage / 100)). Assets with increasing vulnerability counts need investigation for root cause.",
        "asset_risk_trend_aging_vulnerabilities: To detect assets with aging unresolved vulnerabilities, query vulnerability_instances where state='ACTIVE' and calculate average_dwell_time = AVG(dwell_time_days) per asset. Assets with high average dwell time indicate poor vulnerability management. Apply aging penalty: avg_dwell < 30 days (no penalty), 30-60 days (multiply by 1.1), 60-90 days (multiply by 1.3), 90+ days (multiply by 1.5). Formula: aging_risk = base_risk * dwell_time_multiplier. Persistent vulnerabilities indicate systemic remediation issues.",
        "asset_risk_forecast_gamma_distribution: To forecast future risk using Gamma distribution from time-weighted statistics, use calculate_time_weighted_stats function to get mu_hat, lambda_hat, n_hat parameters. Calculate Gamma distribution parameters: alpha = (SUM(mu_hat)^2) / SUM(lambda_hat), beta = SUM(mu_hat) / SUM(lambda_hat). Forecast next 30-day risk: forecasted_risk = alpha * beta. This statistical model predicts risk trajectory based on historical patterns, enabling proactive resource allocation.",
        
        # =============================================================================
        # CLOUD ASSET SPECIFIC CALCULATIONS
        # =============================================================================
        
        "cloud_asset_risk_aws_ec2: To calculate risk for AWS EC2 instances, first identify EC2 assets by checking roles_metadata where code='EC2' or checking cloud service indicators. Query cloud_connector_vuln_metadata where cloud_service='EC2'. Calculate EC2-specific risks: (1) Unencrypted EBS volumes (risk_score=85.0), (2) Public snapshots (risk_score=90.0), (3) SSH/RDP open to 0.0.0.0 (risk_score=80.0), (4) Unused security groups (risk_score=40.0). Formula: ec2_risk = (critical_count * 90) + (high_count * 75) + (medium_count * 50) / total_findings, capped at 100. Add this to base asset risk with weight 0.4.",
        "cloud_asset_risk_aws_s3: To calculate risk for AWS S3 buckets, identify S3 assets from roles or cloud service metadata. Query cloud_connector_vuln_metadata where cloud_service='S3'. Calculate S3-specific risks: (1) Public access via ACLs (risk_score=95.0, compliance impact), (2) Public bucket policies (risk_score=95.0), (3) No encryption (risk_score=80.0), (4) No MFA delete (risk_score=75.0), (5) No logging (risk_score=60.0), (6) No versioning (risk_score=65.0). Formula: s3_risk = MAX(public_access_risk * 1.5, encryption_risk, access_control_risk). Public S3 buckets are critical security failures.",
        "cloud_asset_risk_aws_vpc: To calculate risk for AWS VPC configurations, identify VPC assets and query cloud_connector_vuln_metadata where cloud_service='VPC'. Assess VPC security: (1) No flow logging (risk_score=70.0), (2) Default security group allows all traffic (risk_score=75.0), (3) Overly permissive NACLs, (4) No network segmentation. Formula: vpc_risk = (logging_risk * 0.4) + (security_group_risk * 0.4) + (segmentation_risk * 0.2). VPC is network foundation so misconfigurations have broad impact.",
        
        # =============================================================================
        # MULTI-DIMENSIONAL RISK ANALYSIS
        # =============================================================================
        
        "asset_risk_matrix_impact_likelihood: To create risk matrix classification, calculate both impact (Y-axis) and likelihood (X-axis) independently, then plot on 3x3 or 5x5 matrix. Impact levels: Low (0-40), Medium (41-70), High (71-100). Likelihood levels: Low (0-30), Medium (31-60), High (61-100). Matrix cells determine priority: High Impact + High Likelihood = Critical Priority (immediate action). High Impact + Medium Likelihood = High Priority (urgent action). Medium Impact + Medium Likelihood = Medium Priority (planned action). Low scores = Low Priority (monitor). This visual representation helps prioritize remediation efforts.",
        "asset_risk_prioritization_score: To calculate risk prioritization score for remediation ordering, combine multiple factors with priority weights: (1) Risk score (weight 0.30), (2) CISA exploit present (weight 0.20), (3) Mission Critical classification (weight 0.20), (4) Patch available but not installed (weight 0.15), (5) Vulnerability age/dwell time (weight 0.10), (6) Asset exposure (weight 0.05). Formula: priority_score = (risk * 0.30) + (cisa_flag * 20) + (mission_critical_flag * 20) + (unpatched_flag * 15) + (age_score * 0.10) + (exposure * 0.05), capped at 100. Sort assets by priority_score descending for remediation queue.",
        "asset_risk_aggregate_by_business_unit: To calculate aggregate risk by business unit or department, first map assets to business units using assets.location_region, site_name, or custom business_unit field. For each business unit: (1) Calculate average asset risk, (2) Count CRITICAL and HIGH risk assets, (3) Calculate total risk exposure = SUM(asset_risk * asset_impact) across all BU assets, (4) Identify highest risk asset. Formula: bu_risk_score = (avg_risk * 0.3) + (critical_count * 5) + (high_count * 2), capped at 100. This enables risk-based resource allocation across organization.",
        "asset_risk_aggregate_by_asset_owner: To calculate risk by asset owner or responsible team, join assets with asset_owner_metadata or responsibility assignments. For each owner: Calculate total_managed_risk = SUM(asset_risk) across owned assets, average_risk = AVG(asset_risk), worst_asset_risk = MAX(asset_risk), overdue_remediation_count = COUNT(assets with dwell_time > 90 days). Formula: owner_risk_score = (total_managed_risk / asset_count) + (overdue_count * 5), capped at 100. This provides accountability metrics for security ownership.",
        
        # =============================================================================
        # COMPLIANCE AND REGULATORY RISK
        # =============================================================================
        
        "asset_risk_compliance_gdpr: To calculate GDPR compliance risk for assets processing personal data, identify assets that handle EU customer data by checking location_region for EU countries or data_classification tags. Assess compliance factors: (1) Unencrypted data at rest (add 30 points), (2) Unencrypted data in transit (add 25 points), (3) Missing access controls (add 20 points), (4) No audit logging (add 15 points), (5) Data retention violations (add 10 points). Formula: gdpr_risk = base_risk + compliance_penalty_sum, capped at 100. GDPR violations carry significant fines up to 4% of global revenue, so compliance risk must be weighted heavily.",
        "asset_risk_compliance_pci_dss: To calculate PCI-DSS compliance risk for assets processing payment card data, identify assets in cardholder data environment by checking roles for payment processing services or data_classification for PCI scope. Assess PCI factors: (1) Missing encryption for card data (add 40 points), (2) Default credentials on payment systems (add 35 points), (3) Missing network segmentation (add 25 points), (4) Inadequate access controls (add 20 points), (5) Missing vulnerability scans (add 15 points). Formula: pci_risk = base_risk + pci_penalty_sum, capped at 100. Non-compliance results in loss of card processing privileges.",
        "asset_risk_compliance_hipaa: To calculate HIPAA compliance risk for healthcare assets handling Protected Health Information (PHI), identify healthcare assets by checking industry classification or data_classification tags for PHI. Assess HIPAA factors: (1) Unencrypted PHI (add 35 points), (2) Missing access audit logs (add 30 points), (3) Inadequate authentication (add 25 points), (4) No data backup/disaster recovery (add 20 points), (5) Missing business associate agreements for vendors (add 15 points). Formula: hipaa_risk = base_risk + hipaa_penalty_sum, capped at 100. HIPAA violations result in fines and legal liability for data breaches.",
        "asset_risk_compliance_sox: To calculate SOX compliance risk for financial reporting systems, identify assets involved in financial data processing, reporting, or controls by checking roles for financial systems (ERP, accounting software) or system_purpose tags. Assess SOX factors: (1) Inadequate change management controls (add 25 points), (2) Missing segregation of duties (add 30 points), (3) Insufficient audit trails (add 20 points), (4) Weak access controls to financial data (add 25 points), (5) No disaster recovery testing (add 15 points). Formula: sox_risk = base_risk + sox_penalty_sum, capped at 100. SOX non-compliance can result in criminal penalties for executives.",
        
        # =============================================================================
        # INDUSTRY-SPECIFIC RISK CALCULATIONS
        # =============================================================================
        
        "asset_risk_financial_services: To calculate risk for financial services industry assets, apply industry-specific multipliers and considerations. Financial institutions face: (1) Higher attack targeting (multiply base risk by 1.4), (2) Regulatory scrutiny (add compliance_risk * 0.3), (3) Reputational damage from breaches (multiply impact by 1.3), (4) Real-time transaction requirements making patching difficult (add 10 points for production financial systems). Check for financial service indicators: roles include banking systems, trading platforms, customer account databases. Formula: financial_risk = (base_risk * 1.4) + (compliance_risk * 0.3) + (reputational_factor * 10), capped at 100.",
        "asset_risk_healthcare: To calculate risk for healthcare industry assets, apply healthcare-specific factors. Healthcare organizations face: (1) PHI exposure risk (multiply impact by 1.4 for systems with patient data), (2) Ransomware targeting (add 15 points for critical medical systems), (3) Legacy medical device vulnerabilities that cannot be patched (add 25 points for EOL medical devices), (4) Life safety concerns (multiply by 1.5 for life-support or critical care systems). Identify healthcare systems by checking device_type for medical devices or roles for EHR, PACS, medical billing. Formula: healthcare_risk = base_risk * phi_multiplier * critical_care_multiplier + legacy_device_penalty, capped at 100.",
        "asset_risk_manufacturing_ot: To calculate risk for manufacturing and operational technology (OT) assets, apply OT-specific considerations. Manufacturing environments face: (1) Production downtime costs (multiply impact by 1.6 for production control systems), (2) Safety risks from compromised industrial controls (add 30 points for safety systems), (3) Legacy OT systems with no security updates (add 25 points for EOL SCADA/ICS), (4) IT/OT convergence creating new attack paths (add 15 points for systems with both IT and OT connectivity). Identify OT assets using asset_classification_metadata where canonical_type equals OT Assets or roles include industrial control systems. Formula: ot_risk = base_risk * downtime_multiplier + safety_penalty + legacy_penalty, capped at 100.",
        "asset_risk_retail_pos: To calculate risk for retail Point-of-Sale (POS) systems, apply retail-specific factors. Retail POS systems face: (1) Card data theft risk (add 35 points for payment terminals), (2) PCI-DSS compliance requirements (add pci_compliance_risk), (3) Store location vulnerability (multiply by 1.3 for remote store locations with limited IT support), (4) High-value targets during peak shopping seasons (add 10 points during Q4). Identify POS systems by checking roles for payment processing or device descriptions containing POS, terminal, card reader. Formula: pos_risk = base_risk + card_data_penalty + pci_risk + (location_risk * 1.3), capped at 100.",
        
        # =============================================================================
        # ADVANCED THREAT-BASED RISK CALCULATIONS
        # =============================================================================
        
        "asset_risk_ransomware_susceptibility: To calculate ransomware susceptibility risk, assess factors that make assets attractive ransomware targets. High susceptibility indicators: (1) Inadequate backup systems (add 25 points if no verified backups), (2) Vulnerable SMBv1 protocol enabled (add 20 points), (3) Weak or default credentials (add 20 points), (4) Missing endpoint protection (add 15 points), (5) High-value data present (add 15 points for databases, file servers), (6) Windows operating systems (add 10 points). Check for backup coverage by joining with backup_metadata, check for SMBv1 using service_detection data, check credential strength from security_strength_metadata. Formula: ransomware_risk = base_risk + susceptibility_factors_sum, capped at 100.",
        "asset_risk_apt_targeting: To calculate Advanced Persistent Threat (APT) targeting risk, identify assets attractive to nation-state actors. APT target indicators: (1) Intellectual property repositories (add 30 points for R&D systems, source code repos), (2) Executive access systems (add 25 points for C-level user devices), (3) Financial systems (add 25 points for accounting, treasury), (4) Strategic communications (add 20 points for email servers, collaboration platforms), (5) Industrial secrets (add 30 points for manufacturing specs, trade secrets). Use roles_metadata to identify high-value systems, check user_classification for executive users. Formula: apt_risk = base_risk + (target_value * 1.5), capped at 100. APT attacks are highly sophisticated and persistent.",
        "asset_risk_supply_chain_attack: To calculate supply chain attack risk, assess assets involved in software development and deployment pipelines. Supply chain risk factors: (1) Source code repositories (add 35 points for Git servers, version control), (2) Build systems (add 30 points for CI/CD pipelines, Jenkins, GitLab runners), (3) Package managers (add 25 points for internal artifact repositories, npm registries), (4) Development workstations (add 20 points for developer machines with elevated access), (5) Vendor integration points (add 20 points for third-party API connections). Identify by checking roles for CODE-REPO or system_purpose tags containing development, build, CI/CD. Formula: supply_chain_risk = base_risk + pipeline_exposure_sum, capped at 100.",
        "asset_risk_data_exfiltration: To calculate data exfiltration risk, identify assets with sensitive data and assess exfiltration vectors. Exfiltration risk factors: (1) Data classification level (add 40 points for highly confidential, 30 for confidential, 15 for internal), (2) Outbound network access (add 20 points for unrestricted internet access), (3) Removable media enabled (add 15 points for USB access enabled), (4) Cloud sync services (add 15 points for Dropbox, OneDrive on asset), (5) Missing DLP controls (add 20 points if no data loss prevention). Check data_classification field on assets, check for internet_facing flag, query installed_software for cloud storage apps. Formula: exfiltration_risk = base_risk + data_value + (access_vectors_sum * 1.2), capped at 100.",
        
        # =============================================================================
        # INSIDER THREAT RISK CALCULATIONS
        # =============================================================================
        
        "asset_risk_privileged_user_access: To calculate insider threat risk from privileged users, assess the damage potential from compromised privileged accounts. Privileged access risk factors: (1) Domain administrator access (add 40 points for domain admin privileges), (2) Database administrator access (add 35 points for DBA accounts), (3) Root/system access (add 35 points for Linux root or Windows SYSTEM), (4) Multi-system access (add 20 points if user has admin on 5+ systems), (5) No session monitoring (add 15 points if privileged sessions not logged). Query user_accounts joined with roles_metadata where is_admin_role equals TRUE, count systems per admin user. Formula: privileged_risk = base_risk + privilege_level + (access_breadth * 5), capped at 100.",
        "asset_risk_departing_employee: To calculate risk from departing employees with continued access, identify access that should be revoked. Departure risk factors: (1) Termination date passed but access still active (add 50 points for access beyond termination date), (2) Privileged access not revoked (add 40 points for admin access post-departure), (3) VPN access still enabled (add 30 points for remote access), (4) File share access maintained (add 20 points), (5) No exit interview completed (add 10 points). Check hr_system_data for termination_date, compare with last_login_date on assets, check vpn_access_logs. Formula: departure_risk = 100 if (days_since_termination > 0 AND access_active), else 0. Immediate risk requiring urgent attention.",
        "asset_risk_contractor_access: To calculate risk from third-party contractor access, assess external access scope and duration. Contractor risk factors: (1) Expired contract but access remains (add 40 points), (2) Over-provisioned access beyond job requirements (add 30 points), (3) Unmonitored contractor activity (add 25 points if no logging), (4) Contractor VPN or direct network access (add 20 points), (5) Access to sensitive data (add 25 points for confidential data access). Query user_accounts where user_type equals contractor, check contract_end_date from vendor_management_system, compare with account_expiration_date. Formula: contractor_risk = base_risk + access_scope_penalty + (days_overdue * 2), capped at 100.",
        
        # =============================================================================
        # NETWORK SEGMENTATION AND ISOLATION RISK
        # =============================================================================
        
        "asset_risk_network_segmentation_violation: To calculate risk from network segmentation violations where assets communicate across trust boundaries inappropriately, analyze network flow data. Segmentation violation indicators: (1) DMZ to internal zone communication (add 35 points), (2) Guest network to corporate network (add 40 points), (3) OT network to IT network without firewall (add 45 points for safety reasons), (4) Development environment to production (add 30 points), (5) Vendor zone to customer data zone (add 35 points). Query network_flow_logs for source_zone and destination_zone, check against security_policy for allowed flows. Formula: segmentation_risk = base_risk + SUM(violation_penalties), capped at 100. Segmentation violations enable lateral movement.",
        "asset_risk_flat_network_exposure: To calculate risk for assets on flat networks without segmentation, assess the blast radius of a single compromised asset. Flat network risk factors: (1) No VLANs or network segmentation (add 30 points for single broadcast domain), (2) All assets can reach all other assets (add 25 points for unrestricted routing), (3) Servers and workstations on same network (add 20 points), (4) Production and non-production mixed (add 25 points), (5) Critical and non-critical assets unsegmented (add 20 points). Check network_topology_data for VLAN assignments, check firewall_rules for segmentation policies. Formula: flat_network_risk = base_risk + segmentation_absence_penalty + (asset_count_on_network / 10), capped at 100.",
        "asset_risk_internet_exposed: To calculate risk for internet-facing assets with public IP addresses, assess external exposure and attack surface. Internet exposure risk factors: (1) Publicly accessible IP address (base internet_exposure equals 30 points), (2) Open high-risk ports like RDP 3389 or SSH 22 (add 25 points per exposed admin port), (3) Vulnerable web applications (add 20 points for web apps with critical CVEs), (4) No WAF or DDoS protection (add 15 points), (5) Listed in threat intelligence as actively scanned (add 20 points). Query network_interfaces for public_ip equals TRUE, check port_scan_results for open ports, check threat_intel_feeds for asset IP. Formula: internet_risk = base_risk + internet_exposure + (open_ports_penalty * 1.5) + threat_intel_penalty, capped at 100.",
        
        # =============================================================================
        # ASSET AGE AND LIFECYCLE RISK
        # =============================================================================
        
        "asset_risk_hardware_age: To calculate risk from aging hardware beyond manufacturer support, assess hardware lifecycle stage. Hardware age risk factors: (1) Asset age exceeds 5 years (add 15 points), (2) Asset age exceeds 7 years (add 30 points), (3) Manufacturer end-of-support reached (add 40 points), (4) No available hardware replacement parts (add 25 points), (5) Increased failure rate due to age (add 10 points per year beyond 5 years). Query assets.install_date or first_seen_date, calculate age as CURRENT_DATE minus install_date, check manufacturer_lifecycle_metadata for end_of_support dates. Formula: hardware_age_risk = base_risk + (CASE WHEN age > 7 THEN 30 WHEN age > 5 THEN 15 ELSE 0 END) + (years_beyond_support * 10), capped at 100.",
        "asset_risk_software_lifecycle: To calculate risk from software lifecycle stage, assess whether software is in mainstream support, extended support, or end-of-life. Lifecycle risk factors: (1) End-of-Life software with no security patches (add 50 points), (2) Extended support only (add 25 points, limited patches), (3) Approaching EOL within 6 months (add 15 points), (4) Custom or unsupported software (add 30 points), (5) Multiple EOL software packages on same asset (multiply by package count). Query software_instances joined with software_metadata where enum_type equals product_state and code equals EOL, check vendor_lifecycle_dates. Formula: lifecycle_risk = base_risk + eol_penalty * eol_package_count + extended_support_penalty, capped at 100.",
        "asset_risk_patch_lag: To calculate risk from delayed patching, measure time between patch availability and patch installation. Patch lag risk factors: (1) Critical patches available > 30 days (add 40 points), (2) High severity patches available > 60 days (add 30 points), (3) Medium patches available > 90 days (add 20 points), (4) No patching schedule defined (add 15 points), (5) Repeated pattern of delayed patching (add 20 points for habitual lag). Calculate patch lag as CURRENT_DATE minus patch_available_date for each vulnerability, aggregate per asset. Formula: patch_lag_risk = base_risk + (critical_lag_count * 10) + (high_lag_count * 7) + (medium_lag_count * 4), capped at 100. Patch lag increases exploitation window.",
        
        # =============================================================================
        # CRYPTO AND ENCRYPTION RISK CALCULATIONS
        # =============================================================================
        
        "asset_risk_weak_cryptography: To calculate risk from weak cryptographic implementations, assess cipher strength, key lengths, and protocol versions. Weak crypto indicators: (1) SSL 2.0 or SSL 3.0 enabled (add 45 points for POODLE vulnerability), (2) TLS 1.0 or TLS 1.1 enabled (add 30 points), (3) Weak ciphers like RC4, DES, 3DES (add 35 points), (4) RSA keys under 2048 bits (add 25 points), (5) SHA-1 certificates (add 20 points). Query ssl_tls_version_metadata for protocol versions, check security_strength_metadata where enum_type equals cipher or certificate for strength ratings. Formula: crypto_risk = base_risk + SUM(weak_crypto_penalties), capped at 100. Weak cryptography enables man-in-the-middle attacks.",
        "asset_risk_missing_encryption: To calculate risk from missing encryption for data at rest or in transit, identify unencrypted sensitive data. Missing encryption risk factors: (1) Database encryption disabled for sensitive data (add 40 points), (2) Disk encryption disabled on laptops (add 35 points for mobile devices), (3) Backup encryption disabled (add 30 points), (4) Email encryption not enforced (add 20 points for email servers), (5) File share encryption disabled (add 25 points). Check database_config for encryption_at_rest, check endpoint_protection_config for disk_encryption_status, verify backup_encryption_status. Formula: missing_encryption_risk = base_risk + unencrypted_data_value * data_classification_multiplier, capped at 100.",
        "asset_risk_certificate_expiration: To calculate risk from expiring or expired SSL/TLS certificates, assess certificate validity and renewal status. Certificate risk factors: (1) Certificate already expired (add 50 points, immediate outage risk), (2) Certificate expires within 7 days (add 40 points), (3) Certificate expires within 30 days (add 25 points), (4) Certificate expires within 90 days (add 10 points), (5) Self-signed certificate with no expiration (add 30 points). Query ssl_certificate_data for expiration_date, calculate days_until_expiration as expiration_date minus CURRENT_DATE. Formula: cert_expiration_risk = base_risk + CASE WHEN days_until_expiration < 0 THEN 50 WHEN days_until_expiration < 7 THEN 40 WHEN days_until_expiration < 30 THEN 25 ELSE 10 END, capped at 100.",
        
        # =============================================================================
        # OPERATIONAL RISK CALCULATIONS
        # =============================================================================
        
        "asset_risk_single_point_of_failure: To calculate risk for assets that are single points of failure with no redundancy, assess criticality and lack of failover. Single point of failure indicators: (1) No redundant hardware (add 30 points for single server), (2) No high availability configuration (add 25 points for no clustering/failover), (3) Mission Critical classification (multiply by 1.5 for MC assets), (4) No disaster recovery plan (add 20 points), (5) Critical business process dependency (add 25 points). Query high_availability_config for failover_status, check disaster_recovery_plans for asset coverage, assess business_process_dependencies. Formula: spof_risk = base_risk * criticality_multiplier + redundancy_absence_penalties, capped at 100. SPOFs create availability risk.",
        
        "asset_risk_insufficient_monitoring: To calculate risk from insufficient logging and monitoring, assess visibility gaps for security detection. Monitoring gap indicators: (1) No centralized logging (add 30 points), (2) Logs not sent to SIEM (add 25 points), (3) Log retention under 90 days (add 20 points), (4) No anomaly detection (add 20 points), (5) Security events not alerting (add 25 points), (6) No file integrity monitoring for critical systems (add 20 points). Check logging_config for log_destination, verify siem_integration_status, check log_retention_days. Formula: monitoring_risk = base_risk + SUM(visibility_gap_penalties), capped at 100. Insufficient monitoring delays breach detection.",
        
        "asset_risk_change_management_gaps: To calculate risk from inadequate change management controls, assess change process maturity. Change management risk factors: (1) No change approval process (add 35 points), (2) Changes made directly to production without testing (add 40 points), (3) No rollback plan for changes (add 25 points), (4) Inadequate change documentation (add 15 points), (5) No segregation of duties in change process (add 20 points). Query change_management_system for change_tickets, check if prod_changes_require_approval, verify testing_environment_exists. Formula: change_mgmt_risk = base_risk + process_maturity_penalties + (unauthorized_changes_count * 5), capped at 100.",
        
    ]
    
    # Test cases for transform SQL generation in vulnerability/risk analytics domain
    # These questions should trigger different types of transformations:
    # - Calculated columns (risk scores, impact calculations)
    # - Metrics (aggregated risk by dimensions)
    # - Column transformations (time calculations, classifications)
    # - Aggregation transformations (weighted averages, percentages)
    test_cases = [
        
        {
            "question": "Calculate raw_risk score for each asset by first calculating raw_impact, then calculating raw_likelihood from breach method likelihoods and asset exposure, then combining them with appropriate weighting",
            "project_id": "cve_data",
            "event_id": "transform_event_4",
            "description": "CALCULATED_COLUMN: Raw risk score combining calculated impact and likelihood",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "For each vulnerability based on the severity, vulnerability definition, vulnerability remediation availability and attack vector lets calculate the exploitability score, breach likelihood and risk scores",
            "project_id": "cve_data",
            "event_id": "transform_event_5",
            "description": "CALCULATED_COLUMN: Bastion impact score for bastion devices",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Create a calculated column for bastion_impact that calculates impact score specifically for bastion host devices using impact_class and propagation_class",
            "project_id": "cve_data",
            "event_id": "transform_event_5",
            "description": "CALCULATED_COLUMN: Bastion impact score for bastion devices",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Create a open vulnerability age for each vulnerability instance based on the publish_time and current date",
            "project_id": "cve_data",
            "event_id": "transform_event_5",
            "description": "CALCULATED_COLUMN: Bastion impact score for bastion devices",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Add exploitability score for each vulnerability based on the cvss_score, severity category and raw score",
            "project_id": "cve_data",
            "event_id": "transform_event_5",
            "description": "CALCULATED_COLUMN: Bastion impact score for bastion devices",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "For each asset I want to track open vulnerabilities and their age in days",
            "project_id": "cve_data",
            "event_id": "transform_event_5",
            "description": "CALCULATED_COLUMN: Bastion impact score for bastion devices",
            "knowledge": vulnerability_knowledge
        },
        """{
            "question": "Create a calculated column for asset propagation risk score that combines propagation_class impact and bastion device status and add it to the dev assets table",
            "project_id": "cve_data",
            "event_id": "transform_event_1",
            "description": "CALCULATED_COLUMN: Asset propagation risk calculation",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate the raw_impact score for each asset based on impact_class and asset classification criticality scores",
            "project_id": "cve_data",
            "event_id": "transform_event_2",
            "description": "CALCULATED_COLUMN: Raw impact score calculation using impact_class and classification metadata",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate propagation_impact score for each asset using propagation_class enum and network relationship factors",
            "project_id": "cve_data",
            "event_id": "transform_event_6",
            "description": "CALCULATED_COLUMN: Propagation impact based on propagation_class and network topology",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Show me vulnerability risk metrics by asset classification type with calculated risk per asset ratios",
            "project_id": "cve_data",
            "event_id": "transform_event_7",
            "description": "METRIC: Risk by asset classification with risk density",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Create a metric showing breach method likelihood by propagation class with calculated blast radius impact",
            "project_id": "cve_data",
            "event_id": "transform_event_8",
            "description": "METRIC: Breach likelihood by propagation with blast radius",
            "knowledge": vulnerability_knowledge
        },
        
        {
            "question": "Create a calculated field for raw_likelihood that estimates the likelihood of an asset being compromised based on breach method likelihoods and asset exposure",
            "project_id": "cve_data",
            "event_id": "transform_event_3",
            "description": "CALCULATED_COLUMN: Raw likelihood score using breach method and exposure calculations",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Transform vulnerability detection dates to show days since detection and calculate time-weighted risk decay factor",
            "project_id": "cve_data",
            "event_id": "transform_event_9",
            "description": "COLUMN_TRANSFORMATION: Time calculations and decay factors",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate weighted average risk score for each asset by first computing raw_risk from impact and likelihood calculations, where weight is based on asset criticality score from asset_classification_metadata, grouped by device type",
            "project_id": "cve_data",
            "event_id": "transform_event_10",
            "description": "AGGREGATION_TRANSFORMATION: Weighted risk by asset criticality after calculating raw_risk",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Create a calculated field for lateral movement risk that combines bastion device status, propagation class, and trust relationships using propagation_impact and bastion_impact",
            "project_id": "cve_data",
            "event_id": "transform_event_11",
            "description": "CALCULATED_COLUMN: Lateral movement risk calculation",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Show me monthly vulnerability risk metrics with calculated fields for month-over-month risk score change and cumulative risk exposure, where risk scores are calculated from impact and likelihood",
            "project_id": "cve_data",
            "event_id": "transform_event_12",
            "description": "METRIC: Monthly risk trends with cumulative exposure",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Transform asset classification codes to descriptions and create a calculated field for classification impact multiplier that affects raw_impact calculation",
            "project_id": "cve_data",
            "event_id": "transform_event_13",
            "description": "COLUMN_TRANSFORMATION: Classification enrichment and impact calculation",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate the percentage of total risk score for each asset classification type relative to all classifications, where risk scores are computed from impact and likelihood calculations",
            "project_id": "cve_data",
            "event_id": "transform_event_14",
            "description": "AGGREGATION_TRANSFORMATION: Risk distribution by classification after calculating risk scores",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Create a metric showing breach method likelihood by asset impact class with calculated propagation_impact score",
            "project_id": "cve_data",
            "event_id": "transform_event_15",
            "description": "METRIC: Breach likelihood by impact class with propagation impact",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate comprehensive risk score that combines CVSS score, exploitability, impact, time urgency, and asset classification impact multiplier to populate raw_risk",
            "project_id": "cve_data",
            "event_id": "transform_event_16",
            "description": "CALCULATED_COLUMN: Comprehensive risk score calculation for raw_risk",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Show me time-weighted risk scores by propagation class with calculated Gamma distribution parameters for trend forecasting, where risk scores are computed from impact and likelihood",
            "project_id": "cve_data",
            "event_id": "transform_event_17",
            "description": "METRIC: Time-weighted risk with Gamma parameters by propagation after calculating risk scores",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Create a calculated column that determines impact_class (Mission Critical, Critical, Other) based on admin roles, bastion device status, and device_impact, then calculate raw_impact using that impact_class",
            "project_id": "cve_data",
            "event_id": "transform_event_18",
            "description": "CALCULATED_COLUMN: Impact class determination and raw_impact calculation",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate bastion_impact for all assets where is_bastion_device is true, using impact_class score and propagation_class impact",
            "project_id": "cve_data",
            "event_id": "transform_event_19",
            "description": "CALCULATED_COLUMN: Bastion impact for bastion devices",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Show me average impact, likelihood, and risk scores by asset classification type (canonical_type, device_type) with calculated risk ratios, where impact is calculated from impact_class and propagation_class, likelihood is calculated from breach methods and exposure, and risk is calculated from impact and likelihood",
            "project_id": "cve_data",
            "event_id": "transform_event_20",
            "description": "METRIC: Average calculated risk scores by asset classification",
            "knowledge": vulnerability_knowledge
        }"""
    ]
    
    # Collect all results
    all_results = []
    
    # Process each test case
    for i, test_case in enumerate(test_cases):
        # Validate test_case is a dict
        if not isinstance(test_case, dict):
            logger.warning(f"Skipping invalid test case at index {i}: {type(test_case)}")
            all_results.append({
                "event_id": f"test_{i+1}",
                "status": "skipped",
                "error": f"Invalid test case type: {type(test_case)}"
            })
            continue
        
        event_id = test_case.get('event_id', f'test_{i+1}')
        logger.info(f"Processing test case {i+1}/{len(test_cases)}: {event_id}")
        
        # Process the transform question with knowledge context if provided
        knowledge = test_case.get('knowledge', None)
        result = await demo.process_transform_question(
            user_question=test_case['question'],
            project_id=test_case['project_id'],
            knowledge=knowledge,
            language="English"
        )
        
        # Collect result data
        result_data = {
            "event_id": event_id,
            "description": test_case.get('description', 'N/A'),
            "question": test_case.get('question', 'N/A'),
            "project_id": test_case.get('project_id', 'N/A'),
            "status": result.get("status", "unknown"),
            "success": False,
            "sql": "",
            "reasoning_plan": {},
            "reasoning": "",
            "transform_type": "",
            "parsed_entities": {},
            "error": None,
            "reasoning_error": None
        }
        
        if result["status"] == "success":
            transform_result = result.get("result", {})
            result_data["success"] = transform_result.get('success', False)
            
            if transform_result.get("success"):
                data = transform_result.get("data", {})
                result_data["sql"] = data.get("sql", "")
                result_data["reasoning_plan"] = data.get("reasoning_plan", {})
                result_data["reasoning"] = data.get("reasoning", "")
                result_data["transform_type"] = data.get("transform_type", "")
                result_data["parsed_entities"] = data.get("parsed_entities", {})
            else:
                result_data["error"] = transform_result.get("error", "Unknown error")
                result_data["reasoning_error"] = transform_result.get("reasoning_error")
        else:
            result_data["error"] = result.get("error", "Unknown error")
        
        all_results.append(result_data)
        
        # Add a small delay between test cases
        await asyncio.sleep(1)
    
    # Log all results at the end
    print("\n" + "="*80)
    print("="*80)
    print("FINAL RESULTS SUMMARY")
    print("="*80)
    print("="*80)
    
    # Statistics
    total_cases = len(all_results)
    successful = sum(1 for r in all_results if r.get("success", False))
    failed = sum(1 for r in all_results if r.get("status") == "error" or (r.get("status") == "success" and not r.get("success", False)))
    skipped = sum(1 for r in all_results if r.get("status") == "skipped")
    
    print(f"\n📊 Summary Statistics:")
    print(f"  Total Test Cases: {total_cases}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ⚠️  Skipped: {skipped}")
    print(f"  Success Rate: {(successful/total_cases*100):.1f}%" if total_cases > 0 else "N/A")
    
    # Detailed results
    print(f"\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)
    
    for i, result_data in enumerate(all_results, 1):
        print(f"\n{'='*80}")
        print(f"Test Case {i}: {result_data.get('event_id', 'N/A')}")
        print(f"{'-'*80}")
        print(f"Description: {result_data.get('description', 'N/A')}")
        print(f"Question: {result_data.get('question', 'N/A')}")
        print(f"Project ID: {result_data.get('project_id', 'N/A')}")
        print(f"Status: {result_data.get('status', 'unknown')}")
        print(f"Success: {result_data.get('success', False)}")
        
        if result_data.get("success"):
            # Print SQL
            sql = result_data.get("sql", "")
            if sql:
                print(f"\n📝 Generated SQL:")
                print(f"{sql}")
            else:
                print("\n⚠️  No SQL generated")
            
            # Print reasoning plan
            reasoning_plan = result_data.get("reasoning_plan", {})
            if reasoning_plan:
                print(f"\n🧠 Reasoning Plan:")
                print(f"  Transform Type: {reasoning_plan.get('transform_type', 'N/A')}")
                print(f"  Source Columns: {reasoning_plan.get('source_columns', [])}")
                print(f"  Target Columns: {reasoning_plan.get('target_columns', [])}")
                print(f"  SQL Functions Needed: {reasoning_plan.get('sql_functions_needed', [])}")
                print(f"  Is Metric: {reasoning_plan.get('is_metric', False)}")
                
                if reasoning_plan.get('is_metric'):
                    print(f"  Metric Dimensions: {reasoning_plan.get('metric_dimensions', [])}")
                    print(f"  Metric Measures: {reasoning_plan.get('metric_measures', [])}")
                
                calculation_steps = reasoning_plan.get('calculation_steps', [])
                if calculation_steps:
                    print(f"\n  📋 Calculation Steps:")
                    for step_idx, step in enumerate(calculation_steps, 1):
                        if isinstance(step, dict):
                            print(f"    Step {step_idx}: {step.get('description', 'N/A')}")
                            if step.get('sql_expression'):
                                print(f"      SQL: {step.get('sql_expression')}")
            
            # Print reasoning text (truncated)
            reasoning = result_data.get("reasoning", "")
            if reasoning:
                print(f"\n💭 Reasoning Text (first 500 chars):")
                reasoning_preview = reasoning[:500] + "..." if len(reasoning) > 500 else reasoning
                print(f"{reasoning_preview}")
            
            # Print transform type
            transform_type = result_data.get("transform_type", "")
            if transform_type:
                print(f"\n🔄 Transform Type: {transform_type}")
            
            # Print parsed entities if available
            parsed_entities = result_data.get("parsed_entities", {})
            if parsed_entities:
                print(f"\n📊 Parsed Entities:")
                print(json.dumps(parsed_entities, indent=2))
        else:
            error = result_data.get("error", "Unknown error")
            print(f"\n❌ Error: {error}")
            
            # Print reasoning error if available
            reasoning_error = result_data.get("reasoning_error")
            if reasoning_error:
                print(f"Reasoning Error: {reasoning_error}")
        
        print(f"{'='*80}")
    
    # Summary by transform type
    print(f"\n" + "="*80)
    print("RESULTS BY TRANSFORM TYPE")
    print("="*80)
    
    transform_type_counts = {}
    for result_data in all_results:
        if result_data.get("success"):
            transform_type = result_data.get("transform_type", "unknown")
            transform_type_counts[transform_type] = transform_type_counts.get(transform_type, 0) + 1
    
    for transform_type, count in sorted(transform_type_counts.items()):
        print(f"  {transform_type}: {count}")
    
    # Export results to JSON file
    import os
    from datetime import datetime
    
    results_file = f"transform_demo_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results_export = {
        "summary": {
            "total_cases": total_cases,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "success_rate": (successful/total_cases*100) if total_cases > 0 else 0,
            "timestamp": datetime.now().isoformat()
        },
        "results": all_results
    }
    
    try:
        with open(results_file, 'w') as f:
            json.dump(results_export, f, indent=2)
        print(f"\n💾 Results exported to: {results_file}")
    except Exception as e:
        logger.error(f"Error exporting results to file: {e}")
    
    print(f"\n{'='*80}")
    print("END OF RESULTS SUMMARY")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Configure logging level
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the demo
    print("="*80)
    print("Transform SQL RAG Agent Demo")
    print("="*80)
    print("This demo tests the TransformSQLRAGAgent with various transform questions.")
    print("It uses the local Chroma store from dependencies.py")
    print("="*80)
    
    asyncio.run(run_transform_demo())

