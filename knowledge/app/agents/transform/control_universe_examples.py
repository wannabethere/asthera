"""
Complete Integration Examples - Document to Control Universe
============================================================

This demonstrates the complete flow:
1. Input: Compliance documents
2. Process: Reasoning agents analyze documents
3. Output: Control universe blueprint with measurable expectations

All outputs are REASONING PLANS ready for execution teams.
"""

from typing import Dict, List, Any
from document_analysis_agents import (
    ControlUniverseReasoningWorkflow,
    extract_blueprint
)
from control_universe_model import (
    create_sample_control_universe,
    ComplianceKnowledgeBase
)


# ============================================================================
# SAMPLE COMPLIANCE DOCUMENTS
# ============================================================================

def get_sample_hipaa_documents() -> List[Dict[str, str]]:
    """Sample HIPAA compliance documents for analysis."""
    
    return [
        {
            "title": "HIPAA Security Rule - Access Control Requirements",
            "source": "45 CFR 164.312(a)",
            "content": """
§164.312 Technical safeguards.

(a)(1) Standard: Access control. Implement technical policies and procedures for 
electronic information systems that maintain electronic protected health information 
to allow access only to those persons or software programs that have been granted 
access rights as specified in §164.308(a)(4).

(2) Implementation specifications:

(i) Unique user identification (Required). Assign a unique name and/or number for 
identifying and tracking user identity.

(ii) Emergency access procedure (Required). Establish (and implement as needed) 
procedures for obtaining necessary electronic protected health information during 
an emergency.

(iii) Automatic logoff (Addressable). Implement electronic procedures that terminate 
an electronic session after a predetermined time of inactivity.

(iv) Encryption and decryption (Addressable). Implement a mechanism to encrypt and 
decrypt electronic protected health information.

The covered entity must implement policies and procedures to prevent unauthorized 
access to electronic protected health information. Access to ePHI must be limited 
to authorized users who have a legitimate business need.

Regular reviews of user access rights must be conducted to ensure that access 
permissions remain appropriate. Access that is no longer needed must be promptly 
revoked.

System access logs must be maintained to track who accessed what information and when. 
These logs must be retained for at least six years and be available for audit purposes.
"""
        },
        {
            "title": "HIPAA Security Rule - Audit Controls",
            "source": "45 CFR 164.312(b)",
            "content": """
(b) Standard: Audit controls. Implement hardware, software, and/or procedural 
mechanisms that record and examine activity in information systems that contain or 
use electronic protected health information.

The covered entity must implement audit controls that:
1. Record access to ePHI systems
2. Track modifications to ePHI
3. Monitor disclosure of ePHI
4. Log security-relevant events
5. Detect anomalous access patterns

Audit logs must include:
- User identification
- Date and time of access
- Type of access (read, write, delete)
- Resource accessed
- Success or failure of access attempt

Audit logs must be:
- Protected from unauthorized modification or deletion
- Retained for a minimum of six years
- Regularly reviewed for security incidents
- Available for investigation and compliance verification

The organization must establish procedures for regular review of audit logs. Reviews 
should occur at least quarterly, with more frequent reviews for high-risk systems. 

Any suspicious activity detected in audit logs must be investigated and remediated 
within 72 hours of detection.
"""
        },
        {
            "title": "Organization Policies - Access Review Procedure",
            "source": "Internal Policy Document - IS-SEC-001",
            "content": """
Healthcare Organization - Information Security Policy
Access Review Procedure

Purpose:
This procedure ensures that user access to electronic Protected Health Information 
(ePHI) systems is reviewed regularly to maintain compliance with HIPAA Security Rule 
requirements.

Scope:
Applies to all systems that store, process, or transmit ePHI including:
- Electronic Health Record (EHR) system
- Practice Management System (PMS)
- Laboratory Information System (LIS)
- Radiology PACS
- Patient Portal
- Billing systems

Procedure:
1. Access reviews shall be conducted quarterly (every 90 days)

2. The Information Security team shall generate access reports from each system 
   showing all active user accounts and their permission levels

3. Department managers shall review access for their staff and certify that:
   - Each user requires access for their current job duties
   - Permission levels are appropriate
   - No terminated employees have access
   - Contractor/vendor access is still required

4. Managers must complete reviews within 15 business days of receiving reports

5. Any inappropriate access identified must be revoked within 24 hours

6. Completed access reviews with manager approvals must be documented and retained 
   for 7 years

7. The Security Officer shall audit access review completion monthly

Roles and Responsibilities:
- Information Security Team: Generate access reports, track review completion
- Department Managers: Review and certify access for their staff
- Security Officer: Oversee process, ensure compliance, audit completion
- System Administrators: Implement access changes based on review results

Non-Compliance:
Failure to complete access reviews on schedule is a violation of HIPAA requirements 
and may result in:
- Findings in security audits
- Potential HIPAA violations
- Civil monetary penalties
- Corrective action plans
"""
        }
    ]


def get_sample_soc2_documents() -> List[Dict[str, str]]:
    """Sample SOC2 compliance documents for analysis."""
    
    return [
        {
            "title": "SOC 2 Trust Services Criteria - CC2.1",
            "source": "AICPA TSC CC2.1",
            "content": """
CC2.1: The entity monitors the design and operating effectiveness of internal controls 
related to the entity's cybersecurity risk management program, including the security 
of its data center facilities, using a risk assessment process.

This criterion relates to the entity's processes to:
- Identify and assess cybersecurity threats
- Design and implement controls to address identified threats
- Monitor the effectiveness of those controls
- Update controls based on changes in the threat landscape

Required activities include:
1. Conduct risk assessments at least annually and when significant changes occur
2. Document identified risks and corresponding controls
3. Assign risk owners responsible for monitoring and mitigation
4. Track risk treatment plans and their implementation status
5. Report risk metrics to management quarterly
6. Update risk register as new threats emerge or business changes occur

Evidence of compliance includes:
- Risk assessment documentation
- Risk register with current risk levels
- Control design documentation
- Control testing results
- Risk committee meeting minutes
- Management risk reports
"""
        }
    ]


# ============================================================================
# EXAMPLE 1: HIPAA CONTROL UNIVERSE CREATION
# ============================================================================

class HIPAAControlUniverseExample:
    """
    Complete example: Analyze HIPAA documents and create control universe.
    """
    
    @staticmethod
    def run_analysis(api_key: str) -> Dict[str, Any]:
        """
        Run complete HIPAA control universe reasoning workflow.
        
        Returns:
            Control universe blueprint with all reasoning
        """
        
        print("="*70)
        print("HIPAA CONTROL UNIVERSE REASONING WORKFLOW")
        print("="*70)
        
        # Step 1: Get documents to analyze
        print("\n[Step 1] Loading HIPAA Compliance Documents...")
        documents = get_sample_hipaa_documents()
        print(f"✓ Loaded {len(documents)} documents:")
        for doc in documents:
            print(f"  - {doc['title']}")
        
        # Step 2: Prepare knowledge bases
        print("\n[Step 2] Preparing Knowledge Bases...")
        
        existing_patterns = [
            {
                "pattern_name": "Quarterly Access Reviews",
                "framework": "HIPAA",
                "typical_structure": "Control → Requirement (quarterly) → Evidence (review reports)",
                "common_metrics": "Days between reviews, review completion rate",
                "industry_standard": "90-day review cycles"
            },
            {
                "pattern_name": "Audit Logging",
                "framework": "HIPAA",
                "typical_structure": "Control → Requirement (comprehensive logs) → Evidence (log data)",
                "common_metrics": "Log completeness, retention compliance",
                "industry_standard": "6-year retention minimum"
            }
        ]
        
        benchmarks = {
            "access_review_frequency": {
                "healthcare_industry_average": "90 days",
                "high_security_orgs": "30 days",
                "minimum_hipaa": "No specific requirement, but 'regular' reviews expected"
            },
            "audit_log_retention": {
                "hipaa_minimum": "6 years",
                "industry_common": "7 years",
                "high_compliance": "10 years"
            }
        }
        
        examples = [
            {
                "organization": "Similar Healthcare Provider",
                "framework": "HIPAA",
                "lesson": "90-day access reviews proven effective, monthly too burdensome",
                "metric_used": "Days between reviews with 90-day target",
                "evidence_type": "Exported access review reports from IAM system",
                "outcome": "Successful audit, no findings"
            }
        ]
        
        print(f"✓ Loaded {len(existing_patterns)} control patterns")
        print(f"✓ Loaded {len(benchmarks)} benchmark categories")
        print(f"✓ Loaded {len(examples)} historical examples")
        
        # Step 3: Create and run workflow
        print("\n[Step 3] Running Reasoning Agent Workflow...")
        print("  (Each agent will analyze documents and produce reasoning)\n")
        
        workflow = ControlUniverseReasoningWorkflow(anthropic_api_key=api_key)
        
        result = workflow.run(
            source_documents=documents,
            compliance_framework="HIPAA",
            existing_patterns=existing_patterns,
            benchmarks=benchmarks,
            examples=examples
        )
        
        print("✓ Workflow complete - all agents have generated reasoning")
        
        # Step 4: Extract blueprint
        print("\n[Step 4] Extracting Control Universe Blueprint...")
        
        blueprint = extract_blueprint(result)
        
        print("✓ Blueprint extracted")
        
        # Step 5: Display results
        print("\n[Step 5] Displaying Reasoning Outputs...")
        print("="*70)
        
        print("\n📋 DOMAIN CONTEXT REASONING:")
        print("-"*70)
        print(blueprint["domain_reasoning"][:800] if blueprint["domain_reasoning"] else "N/A")
        print("...")
        
        print("\n🎯 CONTROL IDENTIFICATION REASONING:")
        print("-"*70)
        print(blueprint["control_reasoning"][:800] if blueprint["control_reasoning"] else "N/A")
        print("...")
        
        print("\n📊 MEASURABLE EXPECTATIONS REASONING:")
        print("-"*70)
        print(blueprint["expectations_reasoning"][:800] if blueprint["expectations_reasoning"] else "N/A")
        print("...")
        
        print("\n📁 EVIDENCE MAPPING REASONING:")
        print("-"*70)
        print(blueprint["evidence_reasoning"][:800] if blueprint["evidence_reasoning"] else "N/A")
        print("...")
        
        print("\n⚠️  RISK ASSESSMENT REASONING (using 5x5 matrix):")
        print("-"*70)
        print(blueprint["risk_reasoning"][:800] if blueprint["risk_reasoning"] else "N/A")
        print("...")
        
        print("\n🔗 CONTROL UNIVERSE BLUEPRINT:")
        print("-"*70)
        blueprint_data = blueprint.get("blueprint", {})
        print(f"Integration Reasoning:")
        print(blueprint_data.get("integration_reasoning", "N/A")[:800])
        print("...")
        
        print(f"\nBlueprint Status: {blueprint_data.get('blueprint_status', 'Unknown')}")
        print(f"Implementation Priority: {blueprint_data.get('implementation_priority', 'Not specified')}")
        
        print("\n" + "="*70)
        print("CONTROL UNIVERSE BLUEPRINT COMPLETE")
        print("="*70)
        print("\nThis blueprint contains:")
        print("✓ Domain context definition (from document analysis)")
        print("✓ Identified controls and sub-controls")
        print("✓ Measurable expectations with metrics")
        print("✓ Evidence types and collection methods")
        print("✓ Risk assessments using 5x5 matrix")
        print("✓ Implementation guidance")
        print("\nReady for:")
        print("→ Human expert review")
        print("→ Execution team implementation")
        print("→ Control universe instantiation")
        
        return blueprint


# ============================================================================
# EXAMPLE 2: SHOWING BLUEPRINT STRUCTURE
# ============================================================================

class BlueprintStructureExample:
    """
    Example showing the structure of a complete control universe blueprint.
    """
    
    @staticmethod
    def show_example_blueprint():
        """Display an example blueprint structure."""
        
        print("\n" + "="*70)
        print("EXAMPLE CONTROL UNIVERSE BLUEPRINT STRUCTURE")
        print("="*70)
        
        example_blueprint = {
            "domain_context": {
                "reasoning": """
Based on document analysis, this is a healthcare organization that:
- Processes Protected Health Information (PHI)
- Operates electronic health record systems
- Has multiple departments accessing patient data
- Subject to HIPAA Security Rule

Key business processes identified:
1. Patient registration and data entry
2. Clinical documentation and care delivery
3. Laboratory and radiology information management
4. Billing and claims processing

Data categories:
- Electronic Protected Health Information (ePHI) - HIGH sensitivity
- System access logs - MEDIUM sensitivity  
- Administrative data - LOW sensitivity

Systems identified:
- EHR (Electronic Health Record) system
- PMS (Practice Management System)
- LIS (Laboratory Information System)
- PACS (Radiology system)
- Patient Portal

Stakeholders:
- CISO (responsible for security program)
- Information Security Team (technical implementation)
- Department Managers (access governance)
- System Administrators (access provisioning)
""",
                "domain_name": "Healthcare Data Processing",
                "industry": "Healthcare",
                "applicable_frameworks": ["HIPAA"]
            },
            
            "controls": [
                {
                    "control_id": "HIPAA-AC-001",
                    "control_name": "Access Control to ePHI Systems",
                    "framework": "HIPAA",
                    "category": "Access Control",
                    "description": "Implement technical policies to allow access only to authorized users",
                    "source": "45 CFR 164.312(a)(1)",
                    "control_owner": "CISO",
                    "extraction_reasoning": """
Identified from §164.312(a)(1) which explicitly requires technical policies 
for access control. This is a foundational security control in HIPAA.
The document clearly states this is a 'Standard' requirement (not addressable).
                    """,
                    
                    "sub_controls": [
                        {
                            "subcontrol_id": "HIPAA-AC-001.1",
                            "requirement_statement": "User access reviews must be conducted quarterly",
                            "measurable_criteria": "Access reviews completed within 90-day intervals",
                            "success_criteria": "All ePHI systems reviewed every 90 days with documented approvals",
                            "failure_conditions": [
                                "Review interval exceeds 90 days",
                                "Reviews lack manager approval documentation",
                                "Identified inappropriate access not remediated"
                            ],
                            "extraction_reasoning": """
Derived from policy document IS-SEC-001 which specifies quarterly reviews.
While HIPAA requires 'regular' reviews, the organization has defined this
as quarterly (90 days), which aligns with industry practice.
                            """
                        }
                    ]
                }
            ],
            
            "measurable_expectations": [
                {
                    "expectation_id": "EXP-AC-001",
                    "subcontrol_id": "HIPAA-AC-001.1",
                    "expectation_statement": "Access reviews for all ePHI systems occur every 90 days",
                    
                    "metric_name": "Access Review Interval (days)",
                    "target_value": "≤90 days",
                    "measurement_method": "Calculate days between access review completion dates",
                    "data_source": "Access management system review logs",
                    
                    "pass_criteria": "All reviews completed within 90-day window",
                    "fail_criteria": "Any review interval >90 days OR missing reviews",
                    
                    "how_to_test": """
1. Query access management system for all review records
2. Calculate interval between consecutive reviews for each system
3. Identify any intervals exceeding 90 days
4. Verify manager approvals are documented for each review
                    """,
                    
                    "reasoning": """
METRIC SELECTION:
Chose 'days between reviews' rather than 'reviews per year' because:
- More precise measurement
- Easier to detect delays
- Matches how compliance is actually monitored

TARGET VALUE:
90 days chosen because:
- Organization policy specifies quarterly
- Industry standard is quarterly for healthcare
- Balances security needs with operational burden
- Historical example showed 90 days effective

DATA SOURCE:
Access management system selected because:
- Single source of truth for review data
- Automated logging reduces manual errors
- Supports auditability
- System already in use

ASSUMPTIONS:
- Review log is complete and accurate
- Timestamps reflect actual review completion
- Manager approvals are captured in system

LIMITATIONS:
- Measures that reviews occurred, not their quality
- Doesn't verify thoroughness of reviews
- Doesn't track remediation timeliness separately
                    """
                }
            ],
            
            "evidence_types": [
                {
                    "evidence_type_id": "EVD-AC-001",
                    "evidence_name": "Access Review Reports",
                    "evidence_category": "Reports",
                    "applicable_to": ["EXP-AC-001"],
                    
                    "what_it_demonstrates": "Proves that periodic access reviews are conducted",
                    
                    "collection_method": "Export from Identity Management System",
                    "collection_frequency": "Quarterly",
                    "retention_period": "7 years",
                    
                    "sufficiency_criteria": """
Report must contain:
- Review completion date
- Reviewer name/role
- Systems covered
- Users reviewed
- Manager approval
- Inappropriate access identified
- Remediation actions taken
                    """,
                    
                    "quality_indicators": [
                        "Complete coverage of all ePHI systems",
                        "Clear approval chain documented",
                        "Remediation actions tracked to completion",
                        "No gaps in review timeline"
                    ],
                    
                    "reasoning": """
EVIDENCE TYPE SELECTION:
Reports chosen over raw logs because:
- Summarize review activity clearly
- Show approval chain
- Document remediation
- Easier for auditors to review

COLLECTION METHOD:
Export from IAM system because:
- Automated, reduces manual effort
- Standardized format
- Version controlled
- Audit trail of export

RETENTION:
7 years chosen because:
- Exceeds HIPAA minimum (6 years)
- Aligns with organizational retention policy
- Common practice in healthcare
- Allows historical trend analysis
                    """
                }
            ],
            
            "risk_assessments": [
                {
                    "requirement_id": "HIPAA-AC-001.1",
                    "requirement": "Quarterly access reviews",
                    
                    "likelihood_assessment": {
                        "level": 3,  # Possible
                        "level_name": "Possible",
                        "reasoning": """
LIKELIHOOD: 3 (Possible)

Factors increasing likelihood:
- Manual process prone to delays (workload, priorities)
- Requires coordination across departments
- Historical data shows 30% late reviews in similar orgs
- Competing priorities during busy periods

Factors decreasing likelihood:
- Automated reminder system in place
- Security Officer monitors completion monthly
- Manager accountability established in policy
- Process relatively simple (not complex)

Confidence: MEDIUM
Based on industry patterns, limited org-specific historical data
                        """
                    },
                    
                    "impact_assessment": {
                        "level": 4,  # High
                        "level_name": "High",
                        "reasoning": """
IMPACT: 4 (High)

Financial Impact:
- HIPAA Tier 2 penalty potential (Article 164.308(a)(4) violations)
- Up to $1.5M per violation category per year
- Audit costs and remediation expenses

Operational Impact:
- Emergency access reviews required
- System access restrictions during remediation
- Staff time diverted to corrective actions

Reputational Impact:
- PHI exposure risk if unauthorized access exists
- Patient trust erosion
- Negative publicity if breach occurs

Legal/Regulatory Impact:
- Corrective Action Plan required
- Ongoing monitoring by regulators
- Potential restrictions on operations

NOT Catastrophic (5) because:
- Limited to access control (not full breach)
- Correctable through remediation
- No guarantee of actual PHI compromise
                        """
                    },
                    
                    "risk_score": 12,  # 3 × 4
                    "risk_classification": "Moderate Risk",
                    
                    "overall_risk_reasoning": """
RISK SCORE CALCULATION:
Likelihood (3) × Impact (4) = 12
Classification: MODERATE RISK (9-15 range)

RISK INTERPRETATION:
This is a material risk requiring attention but not crisis-level.

PRIORITY: MEDIUM-HIGH
Should be addressed proactively but not emergency

MITIGATION STRATEGIES:
1. Strengthen automated reminders
2. Add escalation for overdue reviews
3. Consider shorter review cycles for high-risk systems
4. Improve management accountability/consequences

MONITORING:
Track compliance monthly, report to leadership quarterly
                    """
                }
            ],
            
            "implementation_guidance": {
                "priority_sequence": [
                    "1. HIGH RISK controls (risk score 16-25) - Immediate",
                    "2. MODERATE RISK controls (risk score 9-15) - Within 90 days",
                    "3. LOW RISK controls (risk score 4-6) - Within 180 days"
                ],
                
                "dependencies": [
                    "Access Management System must be in place before implementing review process",
                    "Manager training must precede delegation of review responsibilities",
                    "Approval workflow must be configured in system"
                ],
                
                "resource_requirements": [
                    "Information Security team: 40 hours for process setup",
                    "System Administrator: 20 hours for report configuration",
                    "Department Managers: 8 hours per quarter for reviews",
                    "Security Officer: 4 hours per month for monitoring"
                ]
            },
            
            "gaps_identified": [
                "Audit log review requirement identified but not fully specified in documents",
                "Encryption requirements mentioned but no specific implementation guidance",
                "Emergency access procedures referenced but not detailed"
            ],
            
            "blueprint_completeness": {
                "status": "80% complete",
                "ready_for_implementation": True,
                "additional_reasoning_needed": [
                    "Audit log review measurable expectations",
                    "Encryption implementation requirements",
                    "Emergency access procedure details"
                ],
                "recommended_next_steps": [
                    "Obtain additional documents on audit logging",
                    "Review encryption requirements in detail",
                    "Define emergency access procedures"
                ]
            }
        }
        
        # Pretty print the blueprint
        import json
        print(json.dumps(example_blueprint, indent=2))
        
        print("\n" + "="*70)
        print("KEY BLUEPRINT COMPONENTS:")
        print("="*70)
        print("""
1. DOMAIN CONTEXT
   └─ Natural language reasoning about organizational domain
   └─ Business processes, data types, systems, stakeholders

2. CONTROLS (hierarchical)
   └─ High-level controls (e.g., "Access Control")
      └─ Sub-controls (e.g., "Quarterly reviews")
         └─ Extraction reasoning (why/how identified)

3. MEASURABLE EXPECTATIONS
   └─ Specific metrics with targets
   └─ Measurement methods
   └─ Pass/fail criteria
   └─ Data sources
   └─ Testing approaches
   └─ Reasoning for all choices

4. EVIDENCE TYPES
   └─ What evidence proves compliance
   └─ Collection methods
   └─ Retention periods
   └─ Quality indicators
   └─ Reasoning for evidence selection

5. RISK ASSESSMENTS (using 5x5 matrix)
   └─ Likelihood level (1-5) with reasoning
   └─ Impact level (1-5) with reasoning
   └─ Risk score calculation
   └─ Risk classification
   └─ Mitigation strategies

6. IMPLEMENTATION GUIDANCE
   └─ Priority sequence
   └─ Dependencies
   └─ Resource requirements

7. GAPS & COMPLETENESS
   └─ What's missing
   └─ Next steps needed
""")


# ============================================================================
# MAIN DEMONSTRATION
# ============================================================================

def main():
    """Main demonstration of control universe reasoning."""
    
    print("\n" + "="*70)
    print("CONTROL UNIVERSE REASONING - DEMONSTRATION")
    print("From Compliance Documents to Measurable Expectations")
    print("="*70)
    
    # Show example blueprint structure
    BlueprintStructureExample.show_example_blueprint()
    
    print("\n" + "="*70)
    print("TO RUN FULL WORKFLOW:")
    print("="*70)
    print("""
# Provide your Anthropic API key
API_KEY = "your-anthropic-api-key-here"

# Run HIPAA control universe reasoning
blueprint = HIPAAControlUniverseExample.run_analysis(API_KEY)

# The workflow will:
# 1. Analyze HIPAA compliance documents
# 2. Define domain context (healthcare, ePHI, systems)
# 3. Identify controls from documents
# 4. Create measurable expectations with metrics
# 5. Map evidence requirements
# 6. Assess risks using 5x5 matrix
# 7. Produce complete control universe blueprint

# The blueprint contains pure REASONING:
# - Natural language explanations
# - Structured plans
# - Measurable expectations
# - Risk assessments
# - Implementation guidance

# Ready for:
# - Human expert review
# - Execution team implementation
# - Control universe instantiation
""")
    
    print("\n" + "="*70)
    print("KEY FEATURES:")
    print("="*70)
    print("""
✓ Document Analysis - Extracts domain context from compliance docs
✓ Control Identification - Identifies controls and sub-controls
✓ Measurable Expectations - Defines metrics, targets, testing
✓ Evidence Mapping - Specifies what evidence proves compliance
✓ Risk Assessment - Uses 5x5 matrix (Likelihood × Impact)
✓ Integration - Synthesizes all reasoning into blueprint
✓ Pure Reasoning - No execution, just plans and reasoning
✓ Ready for Review - Human experts can validate before implementation
""")


if __name__ == "__main__":
    main()
