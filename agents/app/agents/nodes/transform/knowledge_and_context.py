"""
Knowledge Base, Examples, and Instructions System
=================================================

This module manages:
1. Knowledge bases that agents read from
2. Historical examples that guide reasoning
3. Instructions and prompts for each agent
4. Context management for reasoning agents
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json


# ============================================================================
# KNOWLEDGE BASE STRUCTURES
# ============================================================================

@dataclass
class DataModelKnowledgeBase:
    """
    Knowledge base containing structured information about data models.
    Agents read from this to inform their reasoning.
    """
    
    tables_summary: str
    key_columns: List[Dict[str, Any]]
    relationships: List[Dict[str, str]]
    compliance_indicators: List[Dict[str, Any]]
    data_quality_notes: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for agent consumption."""
        return {
            "tables_summary": self.tables_summary,
            "key_columns": self.key_columns,
            "relationships": self.relationships,
            "compliance_indicators": self.compliance_indicators,
            "data_quality_notes": self.data_quality_notes,
            "metadata": self.metadata,
            "last_updated": self.last_updated
        }
    
    def get_summary(self) -> str:
        """Get a natural language summary for agents."""
        return f"""
Data Model Knowledge Base Summary:
==================================

Tables Overview:
{self.tables_summary}

Key Compliance-Relevant Columns:
{json.dumps(self.key_columns, indent=2)}

Data Relationships:
{json.dumps(self.relationships, indent=2)}

Compliance Indicators:
{json.dumps(self.compliance_indicators, indent=2)}

Data Quality Notes:
{self.data_quality_notes}

Last Updated: {self.last_updated}
"""


@dataclass
class ComplianceRulesKnowledgeBase:
    """
    Knowledge base containing compliance rules and regulations.
    Agents reference this when reasoning about requirements.
    """
    
    regulations: List[Dict[str, str]]
    requirements: List[Dict[str, Any]]
    data_protection_rules: List[str]
    penalties: Dict[str, Any]
    control_requirements: List[Dict[str, str]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for agent consumption."""
        return {
            "regulations": self.regulations,
            "requirements": self.requirements,
            "data_protection": self.data_protection_rules,
            "penalties": self.penalties,
            "control_requirements": self.control_requirements,
            "metadata": self.metadata,
            "last_updated": self.last_updated
        }
    
    def get_summary(self) -> str:
        """Get a natural language summary for agents."""
        return f"""
Compliance Rules Knowledge Base Summary:
========================================

Applicable Regulations:
{json.dumps(self.regulations, indent=2)}

Key Requirements:
{json.dumps(self.requirements, indent=2)}

Data Protection Rules:
{chr(10).join(f'- {rule}' for rule in self.data_protection_rules)}

Penalty Information:
{json.dumps(self.penalties, indent=2)}

Control Requirements:
{json.dumps(self.control_requirements, indent=2)}

Last Updated: {self.last_updated}
"""


# ============================================================================
# HISTORICAL EXAMPLES
# ============================================================================

@dataclass
class HistoricalExample:
    """
    A historical example of compliance analysis reasoning.
    Used to guide agents with similar patterns.
    """
    
    example_id: str
    scenario: str  # Description of the scenario
    compliance_framework: str  # GDPR, HIPAA, etc.
    
    # Reasoning examples for each agent type
    compliance_questions_generated: List[str]
    feature_importance_reasoning: str
    risk_reasoning_approach: str
    impact_reasoning_approach: str
    likelihood_reasoning_approach: str
    
    # Outcomes and lessons learned
    outcome: str
    lessons_learned: List[str]
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for agent consumption."""
        return {
            "example_id": self.example_id,
            "scenario": self.scenario,
            "framework": self.compliance_framework,
            "compliance_questions": self.compliance_questions_generated,
            "feature_reasoning": self.feature_importance_reasoning,
            "risk_reasoning": self.risk_reasoning_approach,
            "impact_reasoning": self.impact_reasoning_approach,
            "likelihood_reasoning": self.likelihood_reasoning_approach,
            "outcome": self.outcome,
            "lessons": self.lessons_learned,
            "tags": self.tags
        }
    
    def get_narrative(self) -> str:
        """Get narrative form for agents."""
        return f"""
Example: {self.example_id}
Scenario: {self.scenario}
Framework: {self.compliance_framework}

Compliance Questions Generated:
{chr(10).join(f'  - {q}' for q in self.compliance_questions_generated)}

Feature Importance Reasoning:
{self.feature_importance_reasoning}

Risk Reasoning Approach:
{self.risk_reasoning_approach}

Impact Reasoning Approach:
{self.impact_reasoning_approach}

Likelihood Reasoning Approach:
{self.likelihood_reasoning_approach}

Outcome: {self.outcome}

Lessons Learned:
{chr(10).join(f'  - {lesson}' for lesson in self.lessons_learned)}
"""


class ExamplesLibrary:
    """
    Library of historical examples for agent reference.
    """
    
    def __init__(self):
        self.examples: Dict[str, HistoricalExample] = {}
    
    def add_example(self, example: HistoricalExample) -> None:
        """Add an example to the library."""
        self.examples[example.example_id] = example
    
    def get_by_framework(self, framework: str) -> List[HistoricalExample]:
        """Get examples for a specific compliance framework."""
        return [
            ex for ex in self.examples.values()
            if ex.compliance_framework == framework
        ]
    
    def get_by_tags(self, tags: List[str]) -> List[HistoricalExample]:
        """Get examples matching specific tags."""
        return [
            ex for ex in self.examples.values()
            if any(tag in ex.tags for tag in tags)
        ]
    
    def get_relevant_examples(
        self,
        scenario_description: str,
        framework: Optional[str] = None,
        max_examples: int = 3
    ) -> List[HistoricalExample]:
        """
        Get most relevant examples for a scenario.
        In production, this would use semantic search.
        """
        candidates = list(self.examples.values())
        
        # Filter by framework if specified
        if framework:
            candidates = [ex for ex in candidates if ex.compliance_framework == framework]
        
        # In production: use embeddings and similarity search
        # For now, return first N
        return candidates[:max_examples]


# ============================================================================
# AGENT INSTRUCTIONS
# ============================================================================

@dataclass
class AgentInstructions:
    """
    Instructions and guidelines for a specific agent.
    """
    
    agent_name: str
    role_description: str
    primary_objectives: List[str]
    reasoning_guidelines: List[str]
    output_format_instructions: str
    dos_and_donts: Dict[str, List[str]]
    example_reasoning_pattern: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_full_instructions(self) -> str:
        """Get complete instructions as a formatted string."""
        return f"""
Agent: {self.agent_name}
Role: {role_description}

PRIMARY OBJECTIVES:
{chr(10).join(f'{i+1}. {obj}' for i, obj in enumerate(self.primary_objectives))}

REASONING GUIDELINES:
{chr(10).join(f'- {guideline}' for guideline in self.reasoning_guidelines)}

OUTPUT FORMAT:
{self.output_format_instructions}

DO:
{chr(10).join(f'✓ {item}' for item in self.dos_and_donts.get('do', []))}

DON'T:
{chr(10).join(f'✗ {item}' for item in self.dos_and_donts.get('dont', []))}

EXAMPLE REASONING PATTERN:
{self.example_reasoning_pattern}
"""


class InstructionsLibrary:
    """
    Library of instructions for different agent types.
    """
    
    def __init__(self):
        self.instructions: Dict[str, AgentInstructions] = {}
        self._initialize_default_instructions()
    
    def _initialize_default_instructions(self):
        """Initialize default instructions for standard agents."""
        
        # Compliance Reasoning Agent Instructions
        self.instructions["compliance_reasoning"] = AgentInstructions(
            agent_name="Compliance Reasoning Agent",
            role_description="Generate natural language questions about compliance requirements",
            primary_objectives=[
                "Identify critical compliance questions to investigate",
                "Explain why certain data features are important",
                "Reference knowledge bases to inform reasoning",
                "Use historical examples to guide thinking"
            ],
            reasoning_guidelines=[
                "Start broad, then get specific with questions",
                "Consider both direct and indirect compliance implications",
                "Think about data lifecycle: collection, storage, processing, deletion",
                "Consider cross-border and jurisdictional issues",
                "Identify gaps in current understanding"
            ],
            output_format_instructions="""
Provide:
1. List of specific compliance questions (natural language)
2. Feature importance explanation (why each feature matters)
3. References to knowledge base insights
4. Your reasoning process (how you arrived at these questions)
""",
            dos_and_donts={
                "do": [
                    "Generate clear, specific questions",
                    "Explain your reasoning transparently",
                    "Reference knowledge bases explicitly",
                    "Consider multiple compliance frameworks",
                    "Think about edge cases"
                ],
                "dont": [
                    "Execute queries or calculations",
                    "Write code or SQL",
                    "Make definitive compliance judgments",
                    "Ignore historical examples",
                    "Generate vague questions"
                ]
            },
            example_reasoning_pattern="""
Example:
Scenario: E-commerce platform with customer data
Questions generated:
1. "What personal data requires explicit consent vs legitimate interest?"
2. "Which fields contain data subject to right to erasure?"
3. "Are there fields that require data retention policies?"

Reasoning: I identified these questions because the knowledge base indicates
customer email and purchase history are stored. GDPR requires consent for
marketing use, while transactional data may fall under legitimate interest.
The historical example of a similar e-commerce case showed that unclear
consent mechanisms led to compliance issues, so clarifying this is critical.
"""
        )
        
        # Risk Data Scientist Instructions
        self.instructions["risk_scientist"] = AgentInstructions(
            agent_name="Risk Data Scientist Reasoning Agent",
            role_description="Develop reasoning plans for risk assessment",
            primary_objectives=[
                "Explain appropriate risk methodologies",
                "Describe analytical approach in natural language",
                "Identify required data points and explain why",
                "Create step-by-step reasoning plan"
            ],
            reasoning_guidelines=[
                "Think probabilistically about compliance violations",
                "Consider both inherent and residual risk",
                "Explain methodology trade-offs",
                "Consider data availability and quality",
                "Think about how to validate risk estimates"
            ],
            output_format_instructions="""
Provide:
1. Risk assessment approach (high-level strategy)
2. Methodology reasoning (why certain methods fit)
3. Data requirements (what data needed and why)
4. Step-by-step analytical plan
5. Assumptions and considerations
""",
            dos_and_donts={
                "do": [
                    "Explain statistical concepts in plain language",
                    "Discuss trade-offs between methodologies",
                    "Consider uncertainty explicitly",
                    "Reference historical patterns",
                    "Explain how to validate the approach"
                ],
                "dont": [
                    "Write formulas or code",
                    "Execute calculations",
                    "Claim certainty about risk levels",
                    "Ignore data limitations",
                    "Use jargon without explanation"
                ]
            },
            example_reasoning_pattern="""
Example:
Risk Assessment Approach: For assessing GDPR consent violation risk, I would
use a Bayesian framework because we have historical data on consent rates
and can update probabilities as we observe patterns. This makes sense given
the uncertainty around user behavior.

Methodology Reasoning: Bayesian approach is appropriate because:
- We have prior information from industry benchmarks
- We can incorporate observed consent rates
- We can update estimates as new data arrives
- It handles uncertainty explicitly through probability distributions

Data Requirements:
- Historical consent acceptance rates (to establish priors)
- Current consent mechanism data (to assess quality)
- Audit logs of consent collection (to identify gaps)
- User demographic data (to segment risk by population)

Each is needed because...
"""
        )
        
        # Impact Data Scientist Instructions
        self.instructions["impact_scientist"] = AgentInstructions(
            agent_name="Impact Data Scientist Reasoning Agent",
            role_description="Develop reasoning plans for impact assessment",
            primary_objectives=[
                "Identify relevant impact dimensions",
                "Explain severity assessment approach",
                "Describe stakeholder considerations",
                "Create multi-dimensional impact reasoning plan"
            ],
            reasoning_guidelines=[
                "Consider multiple impact dimensions (financial, operational, reputational, legal)",
                "Think about direct and indirect impacts",
                "Consider time horizons (immediate vs long-term)",
                "Think about cascading effects",
                "Consider stakeholder perspectives"
            ],
            output_format_instructions="""
Provide:
1. Impact assessment approach
2. Impact dimensions to consider (with justification)
3. Severity reasoning framework
4. Step-by-step analytical plan
5. Stakeholder considerations
""",
            dos_and_donts={
                "do": [
                    "Consider multiple types of impact",
                    "Explain severity classifications clearly",
                    "Think about secondary and tertiary impacts",
                    "Consider different stakeholder perspectives",
                    "Discuss aggregation challenges"
                ],
                "dont": [
                    "Calculate specific impact values",
                    "Write code or formulas",
                    "Focus only on financial impact",
                    "Ignore reputational considerations",
                    "Assume linear impact relationships"
                ]
            },
            example_reasoning_pattern="""
Example:
Impact Assessment Approach: For HIPAA violations involving patient data
disclosure, I would assess impact across four dimensions because each
represents a distinct type of harm.

Impact Dimensions:
1. Financial: HIPAA penalties ($100-$50,000 per violation), legal costs,
   potential class action settlements. Important because financial impact
   is most quantifiable and affects business viability.

2. Operational: Incident response costs, system remediation, additional
   compliance audits. Important because these divert resources from
   normal operations and may require staffing changes.

3. Reputational: Patient trust erosion, negative media coverage, difficulty
   recruiting new patients. Important because healthcare relies heavily
   on trust and reputation damage can persist for years.

4. Legal: Regulatory investigations, potential license restrictions,
   increased scrutiny on future activities. Important because this affects
   ability to operate and may limit business expansion.

Severity Reasoning: I would classify severity based on number of patients
affected and data sensitivity...
"""
        )
        
        # Likelihood Data Scientist Instructions
        self.instructions["likelihood_scientist"] = AgentInstructions(
            agent_name="Likelihood Data Scientist Reasoning Agent",
            role_description="Develop reasoning plans for likelihood estimation",
            primary_objectives=[
                "Explain probability estimation approach",
                "Identify historical patterns and trends",
                "Describe leading indicators",
                "Create probability assessment reasoning plan"
            ],
            reasoning_guidelines=[
                "Think about base rates and historical frequency",
                "Consider trend analysis over time",
                "Identify predictive factors",
                "Think about control effectiveness",
                "Consider scenario-specific vs general probability"
            ],
            output_format_instructions="""
Provide:
1. Likelihood assessment approach
2. Probability framework
3. Historical pattern analysis plan
4. Leading indicators identification
5. Step-by-step analytical plan
6. Time horizon considerations
""",
            dos_and_donts={
                "do": [
                    "Ground probability in historical data",
                    "Explain confidence in estimates",
                    "Identify leading indicators",
                    "Consider time-varying probability",
                    "Discuss how to handle missing data"
                ],
                "dont": [
                    "Calculate specific probabilities",
                    "Write code or statistical formulas",
                    "Claim precision beyond what data supports",
                    "Ignore control effectiveness",
                    "Assume static probabilities"
                ]
            },
            example_reasoning_pattern="""
Example:
Likelihood Assessment Approach: For estimating probability of data breach,
I would combine historical frequency analysis with predictive modeling of
control effectiveness.

Probability Framework: I'd think about likelihood in three categories:
- High (>30% annual probability): Multiple indicators present, weak controls
- Medium (10-30%): Some indicators, moderate controls
- Low (<10%): Few indicators, strong controls

Historical Pattern Analysis:
- Review past 5 years of security incidents
- Calculate baseline breach rate for similar organizations
- Identify seasonal patterns (e.g., higher during high-traffic periods)
- Analyze correlation between incidents and organizational changes

Leading Indicators:
- Patch management compliance rates (technical control effectiveness)
- Security training completion rates (human control effectiveness)
- Number of access policy exceptions (process control degradation)
- Time-to-detect metrics from previous incidents (detection capability)

Each indicator is predictive because...
"""
        )
    
    def get_instructions(self, agent_name: str) -> Optional[AgentInstructions]:
        """Get instructions for a specific agent."""
        return self.instructions.get(agent_name)
    
    def add_custom_instructions(
        self,
        agent_name: str,
        instructions: AgentInstructions
    ) -> None:
        """Add custom instructions for an agent."""
        self.instructions[agent_name] = instructions


# ============================================================================
# CONTEXT BUILDER
# ============================================================================

class ReasoningContextBuilder:
    """
    Builds complete context for reasoning agents including:
    - Knowledge bases
    - Historical examples
    - Instructions
    - Conversation history
    """
    
    def __init__(
        self,
        data_model_kb: Optional[DataModelKnowledgeBase] = None,
        compliance_kb: Optional[ComplianceRulesKnowledgeBase] = None,
        examples_library: Optional[ExamplesLibrary] = None,
        instructions_library: Optional[InstructionsLibrary] = None
    ):
        self.data_model_kb = data_model_kb or DataModelKnowledgeBase(
            tables_summary="",
            key_columns=[],
            relationships=[],
            compliance_indicators=[],
            data_quality_notes=""
        )
        self.compliance_kb = compliance_kb or ComplianceRulesKnowledgeBase(
            regulations=[],
            requirements=[],
            data_protection_rules=[],
            penalties={},
            control_requirements=[]
        )
        self.examples_library = examples_library or ExamplesLibrary()
        self.instructions_library = instructions_library or InstructionsLibrary()
    
    def build_context_for_agent(
        self,
        agent_name: str,
        scenario_description: str,
        compliance_framework: Optional[str] = None,
        conversation_history: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build complete context for a specific agent.
        
        Returns a dictionary containing:
        - Knowledge bases
        - Relevant examples
        - Agent instructions
        - Conversation history
        """
        
        # Get relevant examples
        examples = self.examples_library.get_relevant_examples(
            scenario_description,
            framework=compliance_framework,
            max_examples=3
        )
        
        # Get agent instructions
        instructions = self.instructions_library.get_instructions(agent_name)
        
        context = {
            "agent_name": agent_name,
            "data_model_knowledge": self.data_model_kb.to_dict(),
            "compliance_knowledge": self.compliance_kb.to_dict(),
            "relevant_examples": [ex.to_dict() for ex in examples],
            "instructions": instructions.get_full_instructions() if instructions else None,
            "conversation_history": conversation_history or [],
            "scenario": scenario_description
        }
        
        return context
    
    def get_formatted_context_string(
        self,
        agent_name: str,
        scenario_description: str,
        compliance_framework: Optional[str] = None
    ) -> str:
        """Get formatted context as a string for prompt inclusion."""
        
        context = self.build_context_for_agent(
            agent_name,
            scenario_description,
            compliance_framework
        )
        
        examples = context["relevant_examples"]
        example_narratives = "\n\n".join(
            self.examples_library.examples[ex["example_id"]].get_narrative()
            for ex in examples
            if ex["example_id"] in self.examples_library.examples
        )
        
        formatted = f"""
AGENT CONTEXT FOR: {agent_name}
{'='*70}

INSTRUCTIONS:
{context['instructions']}

DATA MODEL KNOWLEDGE BASE:
{self.data_model_kb.get_summary()}

COMPLIANCE KNOWLEDGE BASE:
{self.compliance_kb.get_summary()}

RELEVANT HISTORICAL EXAMPLES:
{example_narratives if example_narratives else 'No examples available'}

CURRENT SCENARIO:
{scenario_description}
"""
        
        return formatted


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_sample_data_model_kb() -> DataModelKnowledgeBase:
    """Create a sample data model knowledge base."""
    return DataModelKnowledgeBase(
        tables_summary="Customer database with 5 tables: customers, orders, payments, support_tickets, audit_logs",
        key_columns=[
            {"table": "customers", "column": "email", "type": "PII", "compliance": "GDPR Article 6"},
            {"table": "customers", "column": "phone", "type": "PII", "compliance": "GDPR Article 6"},
            {"table": "payments", "column": "card_number", "type": "Financial", "compliance": "PCI-DSS"},
            {"table": "support_tickets", "column": "ip_address", "type": "PII", "compliance": "GDPR Article 6"}
        ],
        relationships=[
            {"from": "orders.customer_id", "to": "customers.id", "type": "foreign_key"},
            {"from": "payments.order_id", "to": "orders.id", "type": "foreign_key"}
        ],
        compliance_indicators=[
            {"indicator": "consent_tracking", "present": True, "tables": ["customers"]},
            {"indicator": "data_retention_dates", "present": False, "recommendation": "Add retention policy fields"},
            {"indicator": "audit_logging", "present": True, "tables": ["audit_logs"]}
        ],
        data_quality_notes="Email validation present, phone number format inconsistent, missing consent timestamps for 15% of records"
    )


def create_sample_compliance_kb() -> ComplianceRulesKnowledgeBase:
    """Create a sample compliance knowledge base."""
    return ComplianceRulesKnowledgeBase(
        regulations=[
            {"name": "GDPR", "jurisdiction": "EU", "applicability": "All personal data of EU residents"},
            {"name": "CCPA", "jurisdiction": "California", "applicability": "California residents data"}
        ],
        requirements=[
            {"regulation": "GDPR", "article": "Article 6", "requirement": "Lawful basis for processing personal data"},
            {"regulation": "GDPR", "article": "Article 17", "requirement": "Right to erasure (right to be forgotten)"},
            {"regulation": "GDPR", "article": "Article 32", "requirement": "Security of processing"}
        ],
        data_protection_rules=[
            "Personal data must be processed lawfully, fairly, and transparently",
            "Data must be collected for specified, explicit, and legitimate purposes",
            "Data must be adequate, relevant, and limited to what is necessary",
            "Data must be accurate and kept up to date",
            "Data must not be kept longer than necessary"
        ],
        penalties={
            "tier_1": {"max": "€10 million or 2% of global revenue", "violations": ["Article 8, 11, 25-39"]},
            "tier_2": {"max": "€20 million or 4% of global revenue", "violations": ["Article 5, 6, 7, 9"]}
        },
        control_requirements=[
            {"control": "Access Controls", "requirement": "Implement role-based access to personal data"},
            {"control": "Encryption", "requirement": "Encrypt personal data at rest and in transit"},
            {"control": "Audit Logging", "requirement": "Log all access to personal data"}
        ]
    )


def create_sample_example() -> HistoricalExample:
    """Create a sample historical example."""
    return HistoricalExample(
        example_id="EX-001-ECOMMERCE-GDPR",
        scenario="E-commerce platform processing customer orders and payment data under GDPR",
        compliance_framework="GDPR",
        compliance_questions_generated=[
            "What is the lawful basis for processing customer email addresses for marketing?",
            "Which customer data fields require explicit consent vs legitimate interest?",
            "How long can we retain customer purchase history?",
            "What data must be deleted upon customer request (right to erasure)?"
        ],
        feature_importance_reasoning="""
Customer email is critical because it's used for both transactional and marketing purposes.
The lawful basis differs: transactional emails fall under legitimate interest (contract performance),
while marketing requires explicit consent under GDPR Article 6(1)(a). This distinction affects
data retention, deletion, and consent management requirements.
""",
        risk_reasoning_approach="""
Risk assessment focused on consent mechanism quality. Used Bayesian approach with:
- Prior: Industry baseline consent violation rate (12%)
- Evidence: Observed consent acceptance rate (45% - below industry average of 60%)
- Control: Presence of clear opt-in mechanism (yes)
- Likelihood updated to 8% based on evidence

Key risk factors: Low acceptance rate suggests unclear value proposition or confusing UI,
which correlates with consent violations in historical data.
""",
        impact_reasoning_approach="""
Multi-dimensional impact assessment:
- Financial: Tier 2 GDPR penalty (up to €20M or 4%), estimated at €500K-2M for this violation scale
- Operational: 2-3 months remediation, consent re-collection campaign affecting 100K users
- Reputational: Medium - e-commerce sensitive to trust, but isolated consent issue less severe than breach
- Legal: Regulatory investigation likely, but no litigation risk for consent violations

Weighted impact score: High (financial + operational burden significant)
""",
        likelihood_reasoning_approach="""
Likelihood estimation using:
- Historical frequency: 3 consent-related incidents in past 2 years
- Leading indicators: Low consent acceptance rate (45% vs 60% benchmark), recent UI changes
- Control effectiveness: Clear opt-in present (70% effective based on benchmarks)
- Time horizon: 6-month probability estimated at 15-20%

Confidence: Medium - limited historical data but clear leading indicators
""",
        outcome="Recommended consent mechanism redesign. Risk reduced from 15% to 5% after implementation.",
        lessons_learned=[
            "Low consent acceptance rate is a leading indicator of compliance risk",
            "UI/UX quality directly impacts consent validity and compliance",
            "Proactive consent mechanism testing reduces violation likelihood",
            "Clear value proposition in consent requests improves both acceptance and compliance"
        ],
        tags=["e-commerce", "gdpr", "consent", "marketing"]
    )