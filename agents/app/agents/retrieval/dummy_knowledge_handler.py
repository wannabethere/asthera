"""
Dummy Knowledge Handler for Feature Engineering

This module provides dummy knowledge documents for feature engineering contexts,
such as compliance frameworks, security metrics, and best practices.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document

logger = logging.getLogger("lexy-ai-service")


class DummyKnowledgeHandler:
    """Handler for dummy knowledge documents related to feature engineering"""
    
    def __init__(self):
        """Initialize with dummy knowledge documents"""
        self._dummy_documents = self._create_dummy_documents()
    
    def _create_dummy_documents(self) -> List[Dict[str, Any]]:
        """Create dummy knowledge documents"""
        return [
            {
                "content": """
SOC2 Compliance Features for Vulnerability Management:

1. Access Control (CC6.1-6.8)
   - Track user access to vulnerability data
   - Monitor privileged access to remediation systems
   - Feature: privileged_access_violations_count
   - Feature: unauthorized_access_attempts_count

2. System Operations (CC7.1-7.5)
   - Monitor system availability and performance
   - Track vulnerability detection system uptime
   - Feature: system_uptime_percentage
   - Feature: detection_system_health_score

3. Change Management (CC8.1-8.2)
   - Track vulnerability remediation changes
   - Monitor patch deployment success rates
   - Feature: patch_deployment_success_rate
   - Feature: remediation_change_approval_time

4. Risk Assessment (CC3.2)
   - Assess vulnerability risk levels
   - Track risk mitigation effectiveness
   - Feature: critical_risk_vulnerability_count
   - Feature: risk_mitigation_effectiveness_score

5. Monitoring Activities (CC7.2)
   - Continuous monitoring of vulnerabilities
   - Alert on SLA breaches
   - Feature: sla_breach_count_by_severity
   - Feature: continuous_monitoring_coverage_percentage
""",
                "metadata": {
                    "framework": "SOC2",
                    "category": "compliance",
                    "topics": ["access_control", "system_operations", "change_management", "risk_assessment", "monitoring"],
                    "relevance_score": 1.0
                }
            },
            {
                "content": """
PCI-DSS Compliance Features for Vulnerability Management:

1. Requirement 6: Develop and Maintain Secure Systems
   - Track vulnerability patching within 30 days
   - Monitor critical vulnerabilities (CVSS >= 7.0)
   - Feature: critical_vuln_patch_rate_30days
   - Feature: cvss_7_plus_vulnerability_count

2. Requirement 11: Regularly Test Security Systems
   - Track vulnerability scanning frequency
   - Monitor penetration test findings
   - Feature: vulnerability_scan_frequency_score
   - Feature: penetration_test_finding_remediation_rate

3. Requirement 5: Protect Against Malicious Software
   - Track malware-related vulnerabilities
   - Monitor exploitability indicators
   - Feature: malware_exploitable_vuln_count
   - Feature: cisa_kev_exploited_count

4. Requirement 10: Track and Monitor Network Access
   - Monitor network-exposed vulnerabilities
   - Track asset reachability
   - Feature: network_exposed_critical_vuln_count
   - Feature: reachable_vulnerability_percentage
""",
                "metadata": {
                    "framework": "PCI-DSS",
                    "category": "compliance",
                    "topics": ["secure_systems", "security_testing", "malware_protection", "network_monitoring"],
                    "relevance_score": 1.0
                }
            },
            {
                "content": """
HIPAA Compliance Features for Vulnerability Management:

1. Security Management Process (§164.308(a)(1))
   - Risk analysis of vulnerabilities
   - Risk management and mitigation tracking
   - Feature: phi_exposure_risk_score
   - Feature: risk_mitigation_completion_rate

2. Information Access Management (§164.308(a)(4))
   - Track access to PHI-related systems
   - Monitor unauthorized access attempts
   - Feature: phi_system_access_violations
   - Feature: unauthorized_phi_access_count

3. Audit Controls (§164.312(b))
   - Comprehensive audit logging
   - Track vulnerability detection and remediation events
   - Feature: audit_log_coverage_percentage
   - Feature: vulnerability_event_audit_completeness

4. Integrity (§164.312(c)(1))
   - Ensure PHI data integrity
   - Monitor data corruption vulnerabilities
   - Feature: data_integrity_vulnerability_count
   - Feature: phi_data_corruption_risk_score
""",
                "metadata": {
                    "framework": "HIPAA",
                    "category": "compliance",
                    "topics": ["security_management", "access_management", "audit_controls", "data_integrity"],
                    "relevance_score": 1.0
                }
            },
            {
                "content": """
Exploitability Metrics and Features:

1. EPSS (Exploit Prediction Scoring System)
   - EPSS score > 0.5 indicates high exploitability
   - Feature: high_epss_vulnerability_count (epssScore > 0.5)
   - Feature: avg_epss_score_by_severity

2. CISA KEV (Known Exploited Vulnerabilities)
   - Track vulnerabilities in CISA KEV catalog
   - Feature: cisa_kev_exploited_count
   - Feature: cisa_kev_remediation_rate

3. Reachability Analysis
   - Network-reachable vulnerabilities are more exploitable
   - Feature: reachable_critical_vuln_count
   - Feature: reachability_exploitability_score

4. Public Exploit Availability
   - Track vulnerabilities with public exploits
   - Feature: public_exploit_available_count
   - Feature: exploit_availability_risk_score

5. Zero-Day Vulnerabilities
   - Track vulnerabilities with no patch available
   - Feature: zero_day_vulnerability_count
   - Feature: zero_day_exploitability_risk
""",
                "metadata": {
                    "framework": "general",
                    "category": "exploitability",
                    "topics": ["epss", "cisa_kev", "reachability", "public_exploits", "zero_day"],
                    "relevance_score": 1.0
                }
            },
            {
                "content": """
SLA Compliance Features:

1. Critical Severity SLAs
   - 7-day remediation SLA for Critical vulnerabilities
   - Feature: critical_sla_breached_count
   - Feature: critical_sla_compliance_percentage
   - Feature: avg_critical_remediation_time_days

2. High Severity SLAs
   - 30-day remediation SLA for High vulnerabilities
   - Feature: high_sla_breached_count
   - Feature: high_sla_compliance_percentage
   - Feature: avg_high_remediation_time_days

3. Medium Severity SLAs
   - 90-day remediation SLA for Medium vulnerabilities
   - Feature: medium_sla_breached_count
   - Feature: medium_sla_compliance_percentage

4. SLA Calculation Logic
   - Time measured from detected_time to remediation_time
   - Only count open vulnerabilities (state != 'remediated')
   - Feature: sla_breach_count_by_severity
   - Feature: time_to_remediation_by_severity
   - Feature: sla_compliance_overall_score
""",
                "metadata": {
                    "framework": "general",
                    "category": "sla_compliance",
                    "topics": ["critical_sla", "high_sla", "medium_sla", "remediation_time"],
                    "relevance_score": 1.0
                }
            },
            {
                "content": """
Risk Metrics and Features:

1. Raw Risk Score
   - Base risk calculation from CVSS scores
   - Feature: avg_raw_risk_score
   - Feature: max_raw_risk_score
   - Feature: raw_risk_distribution_by_severity

2. Effective Risk Score
   - Risk adjusted for exploitability and reachability
   - Feature: avg_effective_risk_score
   - Feature: effective_risk_percentile_90
   - Feature: effective_risk_trend_over_time

3. Asset Criticality Impact
   - Risk weighted by asset importance
   - Feature: critical_asset_vulnerability_count
   - Feature: asset_criticality_weighted_risk_score
   - Feature: bastion_impact_score

4. Unpatched Vulnerability Likelihood
   - Probability of unpatched vulnerabilities
   - Feature: unpatched_vulnerability_likelihood_score
   - Feature: patch_availability_rate
   - Feature: patch_lag_days_avg
""",
                "metadata": {
                    "framework": "general",
                    "category": "risk_metrics",
                    "topics": ["raw_risk", "effective_risk", "asset_criticality", "unpatched_likelihood"],
                    "relevance_score": 1.0
                }
            },
            {
                "content": """
Repository and Asset-Level Aggregation Features:

1. Repository-Level Metrics
   - Aggregate vulnerabilities by repository
   - Feature: repo_vulnerability_count
   - Feature: repo_critical_vuln_count
   - Feature: repo_sla_compliance_score
   - Feature: repo_risk_score_avg

2. Asset-Level Metrics
   - Aggregate vulnerabilities by asset/device
   - Feature: asset_vulnerability_count
   - Feature: asset_critical_vuln_count
   - Feature: asset_remediation_rate
   - Feature: asset_risk_score

3. Software Instance Metrics
   - Track vulnerabilities by software product
   - Feature: software_vulnerability_count
   - Feature: software_patch_availability_rate
   - Feature: software_version_risk_score

4. Time-Series Features
   - Track trends over time
   - Feature: vulnerability_trend_30days
   - Feature: remediation_rate_trend
   - Feature: risk_score_trend_over_time
""",
                "metadata": {
                    "framework": "general",
                    "category": "aggregation",
                    "topics": ["repository", "asset", "software", "time_series"],
                    "relevance_score": 1.0
                }
            }
        ]
    
    def get_knowledge_documents(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
        framework: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve knowledge documents based on query and filters
        
        Args:
            query: Search query to match against documents
            project_id: Optional project ID (not used for dummy, but kept for API consistency)
            top_k: Number of documents to return
            framework: Optional framework filter (e.g., "SOC2", "PCI-DSS", "HIPAA")
            category: Optional category filter (e.g., "compliance", "exploitability", "sla_compliance")
            
        Returns:
            List of knowledge documents with content and metadata
        """
        query_lower = query.lower()
        
        # Filter documents based on query and filters
        filtered_docs = []
        for doc in self._dummy_documents:
            doc_metadata = doc.get("metadata", {})
            doc_content = doc.get("content", "").lower()
            
            # Apply framework filter
            if framework and doc_metadata.get("framework", "").lower() != framework.lower():
                continue
            
            # Apply category filter
            if category and doc_metadata.get("category", "").lower() != category.lower():
                continue
            
            # Simple keyword matching (in production, use semantic search)
            relevance_score = 0.0
            query_keywords = query_lower.split()
            
            # Check if query keywords appear in content
            for keyword in query_keywords:
                if keyword in doc_content:
                    relevance_score += 0.2
            
            # Check framework mentions
            if framework and framework.lower() in doc_content:
                relevance_score += 0.5
            
            # Check category mentions
            if category and category.lower() in doc_content:
                relevance_score += 0.3
            
            # Boost score for compliance-related queries
            if any(word in query_lower for word in ["compliance", "soc2", "pci", "hipaa", "sla"]):
                if doc_metadata.get("category") == "compliance" or doc_metadata.get("category") == "sla_compliance":
                    relevance_score += 0.4
            
            # Boost score for exploitability queries
            if any(word in query_lower for word in ["exploit", "epss", "cisa", "reachability"]):
                if doc_metadata.get("category") == "exploitability":
                    relevance_score += 0.4
            
            if relevance_score > 0:
                filtered_docs.append({
                    "content": doc.get("content", ""),
                    "metadata": {
                        **doc_metadata,
                        "relevance_score": min(relevance_score, 1.0),
                        "query": query
                    }
                })
        
        # Sort by relevance score
        filtered_docs.sort(key=lambda x: x["metadata"].get("relevance_score", 0), reverse=True)
        
        # Return top_k documents
        return filtered_docs[:top_k]
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all dummy knowledge documents"""
        return self._dummy_documents

