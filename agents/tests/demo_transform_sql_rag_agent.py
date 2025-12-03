import asyncio
import logging
from typing import Dict, List, Optional
import json

from app.agents.nodes.sql.transform_sql_rag_agent import create_transform_sql_rag_agent
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
    vulnerability_knowledge = [
        "sql_functions_for_impact_calculation: Use SQL functions from sql_functions.json for calculating impact scores. calculate_asset_impact_class_score(impact_class) returns numeric_score (0-100) from risk_impact_metadata. calculate_propagation_impact_score(propagation_class) returns numeric_score (0-100) from risk_impact_metadata. calculate_combined_asset_impact_score(impact_class, propagation_class, weight1, weight2) combines both with weighted average. calculate_asset_exposure_score(propagation_class) returns exposure score for breach method likelihood. calculate_asset_context_multiplier(combined_impact, asset_impact, bastion_impact, propagation_impact_score, propagation_impact, exposure_score) calculates weighted asset context multiplier. Always use these functions instead of manual joins when calculating impact scores.",
        "asset_network_to_propagation_risk: Calculate risk propagation through network relationships. Path: Asset -> Network_Relationships -> Asset -> HAS_VULNERABILITY -> Vulnerability. Nodes traversed: Asset, Asset, Vulnerability. Input attributes: propagation_class, is_bastion_device, propagation_impact, trust_relationships. Calculations performed: Identify bastion devices, Calculate lateral movement risk, Assess blast radius. Use calculate_propagation_impact_score(a.propagation_class) function to get propagation impact scores from risk_impact_metadata. For bastion devices, combine propagation_impact with bastion_impact using weighted formula. SQL pattern: SELECT asset, propagation_class, bastion_impact, calculate_propagation_impact_score(propagation_class) as propagation_impact FROM assets WHERE is_bastion_device = TRUE",
        "asset_classification_type_impact: Asset classification types (canonical_type, device_type, platform, os_type) have impact scores that affect vulnerability risk calculations. Use asset_classification_metadata table from mdl_knowledge_metadata.json to get classification descriptions, criticality_score, and risk_weight. Higher criticality scores increase risk multipliers. Join assets with asset_classification_metadata using classification_type and code to get criticality_score for calculations. For calculated fields, use SQL functions when available instead of manual joins.",
        "impact_class_calculation: Impact class (Mission Critical, Critical, Other) is determined using impact_class_enum logic from mdl_knowledge_metadata. Rules: If asset has admin roles -> CRITICAL. If is_bastion_device -> MISSION_CRITICAL. If device_impact > 70 -> CRITICAL. Otherwise -> OTHER. Use calculate_asset_impact_class_score(impact_class) function to get numeric_score (0-100) from risk_impact_metadata table. Join assets with roles_metadata to check for admin roles (is_admin_role=true). Example: CASE WHEN EXISTS (SELECT 1 FROM roles_metadata WHERE is_admin_role=true) THEN 'Critical' WHEN is_bastion_device THEN 'Mission Critical' WHEN device_impact > 70 THEN 'Critical' ELSE 'Other' END as impact_class, then use calculate_asset_impact_class_score(impact_class) to get score.",
        "calculated_impact_fields: Assets have calculated fields that need to be computed: raw_impact (raw impact score if asset were compromised), raw_likelihood (raw likelihood score of asset being compromised), raw_risk (raw risk score based on security factors), bastion_impact (impact score for bastion hosts), propagation_impact (impact score based on lateral movement potential). Use SQL functions: calculate_asset_impact_class_score(impact_class) for impact_class-based scores, calculate_propagation_impact_score(propagation_class) for propagation impact, calculate_combined_asset_impact_score(impact_class, propagation_class, 0.7, 0.3) for combined impact. For bastion_impact, combine is_bastion_device flag with impact_class score. For raw_impact, use calculate_combined_asset_impact_score. For raw_risk, combine impact and likelihood scores with asset context multiplier using calculate_asset_context_multiplier function.",
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
    ]
    
    # Test cases for transform SQL generation in vulnerability/risk analytics domain
    # These questions should trigger different types of transformations:
    # - Calculated columns (risk scores, impact calculations)
    # - Metrics (aggregated risk by dimensions)
    # - Column transformations (time calculations, classifications)
    # - Aggregation transformations (weighted averages, percentages)
    test_cases = [
        {
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
            "question": "Create a calculated field for raw_likelihood that estimates the likelihood of an asset being compromised based on breach method likelihoods and asset exposure",
            "project_id": "cve_data",
            "event_id": "transform_event_3",
            "description": "CALCULATED_COLUMN: Raw likelihood score using breach method and exposure calculations",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate raw_risk score for each asset by combining raw_impact and raw_likelihood with appropriate weighting",
            "project_id": "cve_data",
            "event_id": "transform_event_4",
            "description": "CALCULATED_COLUMN: Raw risk score combining impact and likelihood",
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
        """{
            "question": "Transform vulnerability detection dates to show days since detection and calculate time-weighted risk decay factor",
            "project_id": "cve_data",
            "event_id": "transform_event_9",
            "description": "COLUMN_TRANSFORMATION: Time calculations and decay factors",
            "knowledge": vulnerability_knowledge
        },
        {
            "question": "Calculate weighted average raw_risk score where weight is based on asset criticality score from asset_classification_metadata, grouped by device type",
            "project_id": "cve_data",
            "event_id": "transform_event_10",
            "description": "AGGREGATION_TRANSFORMATION: Weighted raw_risk by asset criticality",
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
            "question": "Show me monthly vulnerability risk metrics with calculated fields for month-over-month raw_risk change and cumulative risk exposure",
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
            "question": "Calculate the percentage of total raw_risk score for each asset classification type relative to all classifications",
            "project_id": "cve_data",
            "event_id": "transform_event_14",
            "description": "AGGREGATION_TRANSFORMATION: Raw risk distribution by classification",
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
            "question": "Show me time-weighted raw_risk by propagation class with calculated Gamma distribution parameters for trend forecasting",
            "project_id": "cve_data",
            "event_id": "transform_event_17",
            "description": "METRIC: Time-weighted raw_risk with Gamma parameters by propagation",
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
            "question": "Show me average raw_impact, raw_likelihood, and raw_risk by asset classification type (canonical_type, device_type) with calculated risk ratios",
            "project_id": "cve_data",
            "event_id": "transform_event_20",
            "description": "METRIC: Average risk scores by asset classification",
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

