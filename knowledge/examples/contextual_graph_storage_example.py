"""
Example usage of Contextual Graph Storage

Demonstrates how to:
1. Save context definitions
2. Save contextual edges
3. Save control-context profiles
4. Query and search the contextual graph
"""
import logging
import os
import chromadb
from langchain_openai import OpenAIEmbeddings
from datetime import datetime

from app.services.contextual_graph_storage import (
    ContextualGraphStorage,
    ContextDefinition,
    ContextualEdge,
    ControlContextProfile
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_save_contextual_graph():
    """Example of saving a complete contextual graph"""
    
    # Get OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return
    
    # Initialize storage
    chroma_client = chromadb.PersistentClient(path="./chroma_contextual_graph")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=openai_api_key
    )
    
    storage = ContextualGraphStorage(
        chroma_client=chroma_client,
        embeddings_model=embeddings
    )
    
    # ============================================================================
    # Step 1: Save Context Definitions
    # ============================================================================
    logger.info("=== Step 1: Saving Context Definitions ===")
    
    context1 = ContextDefinition(
        context_id="ctx_001",
        document="""
        Large healthcare organization with developing compliance maturity.
        Operates in United States with 1000-5000 employees. Manages electronic 
        Protected Health Information (ePHI) across Epic EHR, Workday HCM, and 
        PACS systems. Subject to HIPAA and state breach notification laws.
        Has medium automation capability with established IAM (Okta) and 
        SIEM (Splunk) platforms. Currently preparing for upcoming HIPAA 
        compliance audit scheduled within 90 days.
        """,
        context_type="organizational_situational",
        industry="healthcare",
        organization_size="large",
        employee_count_range="1000-5000",
        maturity_level="developing",
        regulatory_frameworks=["HIPAA", "state_breach_laws"],
        data_types=["ePHI", "PHI", "PII"],
        systems=["Epic_EHR", "Workday", "PACS", "Okta", "Splunk"],
        automation_capability="medium",
        current_situation="pre_audit",
        audit_timeline_days=90,
        active_status=True
    )
    
    context2 = ContextDefinition(
        context_id="ctx_002",
        document="""
        Small technology startup in rapid growth phase. Located in California
        with 50-200 employees. Primarily handles customer data (PII) and 
        payment information (PCI). Subject to SOC 2 Type II requirements 
        for B2B SaaS customers. Limited compliance maturity with basic 
        security controls in place. High automation capability using modern
        cloud infrastructure (AWS, Okta, Datadog). Planning SOC 2 audit
        for first time in 6 months.
        """,
        context_type="organizational_situational",
        industry="technology",
        organization_size="small",
        employee_count_range="50-200",
        maturity_level="nascent",
        regulatory_frameworks=["SOC2", "PCI_DSS_lite"],
        data_types=["PII", "payment_data"],
        systems=["AWS", "Okta", "Datadog", "Stripe"],
        automation_capability="high",
        current_situation="first_audit_prep",
        audit_timeline_days=180,
        active_status=True
    )
    
    storage.save_context_definitions([context1, context2])
    logger.info("Saved 2 context definitions")
    
    # ============================================================================
    # Step 2: Save Contextual Edges
    # ============================================================================
    logger.info("\n=== Step 2: Saving Contextual Edges ===")
    
    edge1 = ContextualEdge(
        edge_id="edge_001",
        document="""
        Control HIPAA-AC-001 (Access Control to ePHI Systems) has CRITICAL 
        priority for large healthcare organizations preparing for HIPAA audit.
        
        Reasoning: Access control is fundamental HIPAA requirement that auditors 
        scrutinize heavily. Large organizations with multiple systems (EHR, HCM, 
        PACS) face complexity in maintaining consistent access controls. During 
        pre-audit period, demonstrating access review compliance is essential.
        
        Implementation in this context: Leverage existing Workday HCM for role 
        management. Configure quarterly automated reviews using Okta workflows.
        Export access reports from Okta for audit trail. Estimated effort: 80 hours.
        
        Risk in this context: Likelihood=3 (moderate - manual processes prone to 
        delays), Impact=4 (high - audit finding, potential PHI exposure), 
        Risk Score=12 (HIGH).
        
        Evidence requirements: Access review reports from Okta, manager approval 
        documentation from Workday, access provisioning/deprovisioning logs from 
        all ePHI systems.
        """,
        source_entity_id="HIPAA-AC-001",
        source_entity_type="control",
        target_entity_id="access_reviews_requirement",
        target_entity_type="requirement",
        edge_type="HAS_REQUIREMENT_IN_CONTEXT",
        context_id="ctx_001",
        relevance_score=0.95,
        priority_in_context=1,
        risk_score_in_context=12.0,
        likelihood_in_context=3,
        impact_in_context=4,
        implementation_complexity="moderate",
        estimated_effort_hours=80,
        estimated_cost=15000.0,
        prerequisites=["IAM_system_exists", "RBAC_model_defined"],
        automation_possible=True,
        evidence_available=True,
        data_quality="high"
    )
    
    edge2 = ContextualEdge(
        edge_id="edge_002",
        document="""
        Control SOC2-CC6.1 (Logical Access - User Access) has HIGH priority 
        for small technology startups preparing for first SOC 2 audit.
        
        Reasoning: First-time SOC 2 audits focus heavily on access controls 
        as they're foundational. Small orgs often lack formal processes, making 
        this a common finding. However, with high automation capability and 
        cloud-native infrastructure, implementation is straightforward.
        
        Implementation in this context: Leverage Okta SSO for all applications.
        Configure automated provisioning/deprovisioning. Implement MFA across 
        all systems. Set up quarterly access reviews in Okta. Estimated effort: 
        40 hours (easier than healthcare due to fewer systems, modern tooling).
        
        Risk in this context: Likelihood=4 (high - startups often have informal 
        processes), Impact=3 (moderate - no PHI, but customer trust critical), 
        Risk Score=12 (HIGH).
        
        Evidence requirements: Okta access logs, MFA configuration screenshots,
        access review reports, onboarding/offboarding checklists.
        """,
        source_entity_id="SOC2-CC6.1",
        source_entity_type="control",
        target_entity_id="user_access_requirement",
        target_entity_type="requirement",
        edge_type="HAS_REQUIREMENT_IN_CONTEXT",
        context_id="ctx_002",
        relevance_score=0.90,
        priority_in_context=2,
        risk_score_in_context=12.0,
        likelihood_in_context=4,
        impact_in_context=3,
        implementation_complexity="simple",
        estimated_effort_hours=40,
        estimated_cost=8000.0,
        prerequisites=["Okta_SSO_deployed"],
        automation_possible=True,
        evidence_available=True,
        data_quality="high"
    )
    
    storage.save_contextual_edges([edge1, edge2])
    logger.info("Saved 2 contextual edges")
    
    # ============================================================================
    # Step 3: Save Control-Context Profiles
    # ============================================================================
    logger.info("\n=== Step 3: Saving Control-Context Profiles ===")
    
    profile1 = ControlContextProfile(
        profile_id="profile_hipaa_ac001_ctx001",
        document="""
        HIPAA Access Control (164.312(a)) implementation for large healthcare 
        organization with developing maturity in pre-audit state.
        
        Control Overview: Implement technical policies and procedures for 
        electronic information systems that maintain ePHI to allow access only 
        to authorized persons.
        
        Context-Specific Implementation: 
        - Complexity: MODERATE due to multiple legacy systems (Epic EHR from 2015,
          Workday implemented 2020, aging PACS system requiring special integration)
        - Systems in scope: Epic EHR (15,000 users), Workday (all employees), 
          PACS (500 radiologists), Patient Portal (50,000+ patients)
        - Current state: Okta SSO covers 60% of systems, legacy PACS uses 
          separate AD authentication
        - Gap: No centralized access review process, reviews ad-hoc by department
        
        Risk Assessment in Context:
        - Inherent risk: HIGH (Risk=12, L=3, I=4)
        - Current control effectiveness: 40% (some controls exist but inconsistent)
        - Residual risk: MEDIUM-HIGH (Risk=7.2)
        - Primary risk: Audit finding for inadequate access controls
        
        Implementation Roadmap (90-day audit timeline):
        Week 1-2: Configure Okta access review workflows for existing integrations
        Week 3-4: Integrate PACS with Okta (or document compensating controls)
        Week 5-6: Run first access review cycle, document processes
        Week 7-8: Generate historical access reports (last 12 months)
        Week 9-10: Remediate identified issues, prepare audit documentation
        Weeks 11-12: Buffer for audit prep, mock audit
        
        Effort: 80 hours (2 FTE weeks)
        Cost: $15,000 (internal effort + consulting for PACS integration)
        Success probability: 75% (some risk with PACS integration)
        
        Evidence Strategy:
        - Primary: Okta access review reports (automated quarterly)
        - Secondary: Workday manager approvals (workflow documentation)
        - Compensating: PACS manual access review logs (if integration not feasible)
        - Audit trail: Access provisioning/deprovisioning logs from all systems
        
        Metrics in this context:
        1. access_review_interval_days (Target: ≤90, Current: ~180)
        2. inappropriate_access_count (Target: 0, Current: Unknown)
        3. review_completion_rate (Target: 100%, Current: ~30%)
        4. time_to_provision_access (Target: ≤24hrs, Current: ~72hrs)
        5. time_to_deprovision_access (Target: ≤4hrs, Current: ~48hrs)
        """,
        control_id="HIPAA-AC-001",
        context_id="ctx_001",
        framework="HIPAA",
        control_category="access_control",
        inherent_risk_score=12.0,
        current_control_effectiveness=0.40,
        residual_risk_score=7.2,
        risk_level="MEDIUM_HIGH",
        implementation_complexity="moderate",
        estimated_effort_hours=80,
        estimated_cost=15000.0,
        success_probability=0.75,
        implementation_feasibility="feasible",
        timeline_weeks=12,
        automation_possible=True,
        automation_coverage=0.75,
        manual_effort_remaining=0.25,
        evidence_available=True,
        evidence_quality="good",
        evidence_gaps=["PACS_access_logs"],
        systems_in_scope=["Epic_EHR", "Workday", "PACS", "Patient_Portal"],
        systems_count=4,
        users_in_scope=15500,
        integration_maturity=0.60,
        metrics_defined=True,
        metrics_count=5,
        metrics_automated=0.80
    )
    
    storage.save_control_profile(profile1)
    logger.info("Saved 1 control-context profile")
    
    # ============================================================================
    # Step 4: Query the Contextual Graph
    # ============================================================================
    logger.info("\n=== Step 4: Querying the Contextual Graph ===")
    
    # Find relevant contexts
    logger.info("\n4.1 Finding relevant contexts...")
    user_description = """
    We're a healthcare provider with about 2000 employees. We use Epic for 
    our EHR and Workday for HR. We have a HIPAA audit coming up in about 
    3 months.
    """
    
    relevant_contexts = storage.find_relevant_contexts(
        description=user_description,
        top_k=3
    )
    
    logger.info(f"Found {len(relevant_contexts)} relevant contexts:")
    for ctx in relevant_contexts:
        logger.info(f"  - {ctx.context_id}: {ctx.industry} ({ctx.organization_size})")
    
    # Get edges for a context
    logger.info("\n4.2 Getting edges for context ctx_001...")
    edges = storage.get_edges_for_context(
        context_id="ctx_001",
        top_k=10
    )
    logger.info(f"Found {len(edges)} edges for ctx_001")
    for edge in edges:
        logger.info(f"  - {edge.edge_type}: {edge.source_entity_id} -> {edge.target_entity_id}")
    
    # Get control profiles for a context
    logger.info("\n4.3 Getting control profiles for context ctx_001...")
    profiles = storage.get_control_profiles_for_context(
        context_id="ctx_001",
        top_k=10
    )
    logger.info(f"Found {len(profiles)} profiles for ctx_001")
    for profile in profiles:
        logger.info(f"  - {profile.control_id}: {profile.risk_level} (effort: {profile.estimated_effort_hours}h)")
    
    # Search edges
    logger.info("\n4.4 Searching edges...")
    search_results = storage.search_edges(
        query="access control requirements for healthcare audit",
        context_id="ctx_001",
        top_k=5
    )
    logger.info(f"Found {len(search_results)} edges matching search query")
    
    # Get context statistics
    logger.info("\n4.5 Getting context statistics...")
    stats = storage.get_context_statistics("ctx_001")
    logger.info(f"Context ctx_001 statistics: {stats}")


if __name__ == "__main__":
    example_save_contextual_graph()

