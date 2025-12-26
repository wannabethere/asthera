"""
Risk Feature Engineering Agent

This module contains:
- RiskFeatureEngineeringAgent: Generates risk, impact, and likelihood features from standard metrics
- Uses additional risk knowledge for deep research (separate from feature engineering knowledge)
"""

import re
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseChatModel

from app.agents.nodes.transform.feature_engineering_types import (
    FeatureEngineeringState,
    track_llm_call
)
from app.agents.nodes.transform.domain_config import DomainConfiguration, get_domain_config
from app.agents.retrieval.retrieval_helper import RetrievalHelper

logger = logging.getLogger("lexy-ai-service")


class RiskFeatureEngineeringAgent:
    """Agent that generates risk, impact, and likelihood features from standard metrics using risk model knowledge"""
    
    def __init__(
        self,
        llm: BaseChatModel,
        domain_config: DomainConfiguration,
        retrieval_helper: Optional[RetrievalHelper] = None
    ):
        self.llm = llm
        self.domain_config = domain_config
        self.retrieval_helper = retrieval_helper
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config
        
        If loading from state dict, the risk_knowledge_provider callable will be lost during
        serialization. We restore it by looking up the domain config from the registry using
        the domain_name, which preserves the risk_knowledge_provider.
        """
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            # Reconstruct from dict (risk_knowledge_provider will be None after serialization)
            domain_config = DomainConfiguration(**domain_config_dict)
            # Restore risk_knowledge_provider from registry if domain_name is available
            if domain_config.domain_name and not domain_config.risk_knowledge_provider:
                try:
                    registered_config = get_domain_config(domain_config.domain_name)
                    domain_config.risk_knowledge_provider = registered_config.risk_knowledge_provider
                    logger.debug(f"Restored risk_knowledge_provider for domain '{domain_config.domain_name}' from registry")
                except (ValueError, KeyError):
                    # Domain not in registry, keep as None
                    logger.debug(f"Domain '{domain_config.domain_name}' not found in registry, risk_knowledge_provider remains None")
            return domain_config
        return self.domain_config
    
    def _format_risk_knowledge(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format risk calculation knowledge from knowledge documents"""
        if not knowledge_documents:
            return "No risk calculation knowledge available."
        
        formatted = []
        formatted.append("\n=== RISK CALCULATION KNOWLEDGE ===\n")
        
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            category = metadata.get("category", "")
            
            # Filter for risk-related knowledge
            if any(keyword in content.lower() for keyword in ["risk", "impact", "likelihood", "breach", "vulnerability", "exploit"]):
                formatted.append(f"\n--- Knowledge {i} ---")
                if category:
                    formatted.append(f"Category: {category}")
                formatted.append(f"Content:\n{content[:1000]}...")  # Limit length
        
        return "\n".join(formatted)
    
    def _format_reasoning_plan_context(self, reasoning_plan: Dict[str, Any]) -> str:
        """Format reasoning plan as context for risk feature generation"""
        if not reasoning_plan:
            return ""
        
        context_parts = [
            "\n=== REASONING PLAN CONTEXT ===",
            f"Objective: {reasoning_plan.get('objective', 'N/A')}",
            f"Plan ID: {reasoning_plan.get('plan_id', 'N/A')}"
        ]
        
        # Add plan steps
        steps = reasoning_plan.get("steps", [])
        if steps:
            context_parts.append(f"\nPlan Steps ({len(steps)} total):")
            for i, step in enumerate(steps[:10], 1):  # Limit to first 10 steps
                step_desc = step if isinstance(step, str) else step.get("description", step.get("step", str(step)))
                context_parts.append(f"  {i}. {step_desc[:200]}")  # Limit length
        
        # Add data flow if available
        data_flow = reasoning_plan.get("data_flow", [])
        if data_flow:
            context_parts.append(f"\nData Flow: {' -> '.join(data_flow[:5])}")
        
        # Add feature dependencies if available
        feature_deps = reasoning_plan.get("feature_dependencies", {})
        if feature_deps:
            context_parts.append(f"\nFeature Dependencies: {len(feature_deps)} dependencies identified")
            # Show a few key dependencies
            dep_items = list(feature_deps.items())[:3]
            for feature, deps in dep_items:
                if isinstance(deps, list):
                    context_parts.append(f"  - {feature} depends on: {', '.join(deps[:3])}")
        
        # Add quality checks if available
        quality_checks = reasoning_plan.get("quality_checks", [])
        if quality_checks:
            context_parts.append(f"\nQuality Checks: {', '.join(quality_checks[:5])}")
        
        # Add raw plan if available (truncated)
        raw_plan = reasoning_plan.get("raw_plan", "")
        if raw_plan:
            context_parts.append(f"\nRaw Plan (excerpt):\n{raw_plan[:500]}...")
        
        context_parts.append("\nIMPORTANT: Use this reasoning plan to inform your risk feature generation decisions.")
        context_parts.append("Align risk features with the plan's data flow, dependencies, and quality requirements.")
        context_parts.append("Ensure risk features fit into the overall analytical workflow described in the plan.")
        
        return "\n".join(context_parts)
    
    def _get_risk_calculation_examples(self, domain_name: str) -> str:
        """Get domain-specific risk calculation examples"""
        # These examples are based on the vulnerability CVE knowledge from demo_transform_sql_rag_agent.py
        examples = {
            "cybersecurity": """
RISK CALCULATION EXAMPLES FOR CYBERSECURITY:

1. ASSET IMPACT CALCULATION:
   - "Calculate asset impact by first classifying impact_class (Mission Critical, Critical, Other) based on asset roles, services, and CMDB classification, then classify propagation_class (Perimeter, Core) based on network interfaces, then combine using formula: (impact_class_score * 0.7) + (propagation_class_score * 0.3)"
   - "For bastion devices, calculate enhanced impact: propagation_impact * 1.3 + asset_impact * 0.2"

2. BREACH LIKELIHOOD CALCULATION:
   - "Calculate breach likelihood from vulnerabilities by aggregating vulnerability risk scores weighted by severity: (critical_count * 1.0 + high_count * 0.75 + medium_count * 0.5 + low_count * 0.25) / total_vulns * 100"
   - "Calculate breach likelihood from unpatched vulnerabilities: (critical_unpatched * 15 + high_unpatched * 10 + medium_unpatched * 5), capped at 100"
   - "Calculate breach likelihood from CISA exploits: MIN(cisa_exploit_count * 25, 100.0)"
   - "Calculate breach likelihood by propagation class: calculate_asset_exposure_score(propagation_class) * asset_vulnerability_count / 100"

3. RISK CALCULATION:
   - "Calculate comprehensive asset risk: (asset_impact * 0.6) + (asset_breach_likelihood * 0.4), capped at 100.0"
   - "Calculate risk with context multipliers: base_risk * context_multiplier where context_multiplier accounts for bastion status, propagation impact, and exposure"

4. BREACH METHOD LIKELIHOOD:
   - "Calculate breach likelihood via unpatched vulnerability method using breach_method_metadata with method 'unpatched_vulnerability' (risk_score=85.0, weight=0.9)"
   - "Calculate breach likelihood via weak credentials using breach method 'weak_credentials' (risk_score=60.0, weight=0.65)"
   - "Calculate breach likelihood via compromised credentials using breach method 'compromised_credentials' (risk_score=90.0, weight=0.95)
""",
            "hr_compliance": """
RISK CALCULATION EXAMPLES FOR HR COMPLIANCE:

1. TRAINING COMPLETION RISK:
   - "Calculate training completion risk by combining: days_until_deadline (likelihood factor), training_complexity_score (likelihood factor), and employee_historical_completion_rate (likelihood factor)"
   - "Calculate impact of missed training: regulatory_penalty_tier * affected_employee_count * compliance_framework_severity"

2. CERTIFICATION EXPIRY RISK:
   - "Calculate certification expiry likelihood: days_until_expiry / average_renewal_time, where shorter time = higher likelihood"
   - "Calculate certification expiry impact: role_criticality_score * regulatory_requirement_level * business_function_impact"
""",
        }
        
        return examples.get(domain_name, """
RISK CALCULATION PRINCIPLES:

1. IMPACT = Consequence if control/entity fails
   - Consider: regulatory severity, financial impact, operational disruption, downstream dependencies
   - Use domain-specific impact classification (e.g., Mission Critical, Critical, Other for assets)

2. LIKELIHOOD = Probability of failure/breach
   - Consider: historical patterns, current state indicators, exposure factors
   - Use domain-specific likelihood drivers (e.g., vulnerability counts, exploitability scores)

3. RISK = Impact × Likelihood (or weighted combination)
   - Typically: Risk = (Impact * 0.6) + (Likelihood * 0.4) or Risk = SQRT(Impact * Likelihood)
   - Apply context multipliers for special circumstances
""")
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate risk, impact, and likelihood features from standard metrics using risk model knowledge"""
        
        domain_config = self._get_domain_config_from_state(state)
        standard_features = state.get("recommended_features", [])
        knowledge_documents = state.get("knowledge_documents", [])
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        schema_registry = state.get("schema_registry", {})
        relevant_schemas = state.get("relevant_schemas", [])
        project_id = state.get("project_id", "")
        
        if not standard_features:
            logger.warning("No standard features available for risk feature engineering")
            state["risk_features"] = []
            state["impact_features"] = []
            state["likelihood_features"] = []
            state["next_agent"] = "feature_dependency"
            return state
        
        # Load comprehensive risk knowledge (separate from feature engineering knowledge)
        # This is domain-specific risk calculation knowledge for deep research
        # Get risk knowledge from domain config (domain-specific)
        risk_knowledge_base = []
        if domain_config.risk_knowledge_provider:
            try:
                risk_knowledge_base = domain_config.risk_knowledge_provider()
                logger.info(f"Loaded {len(risk_knowledge_base)} risk knowledge items from domain config for {domain_config.domain_name}")
            except Exception as e:
                logger.warning(f"Error loading risk knowledge from domain config: {e}")
        else:
            logger.info(f"No risk_knowledge_provider configured for domain '{domain_config.domain_name}'. Risk features will use general knowledge only.")
        
        # Convert risk knowledge strings to document format for consistency
        risk_knowledge_docs = [
            {
                "content": knowledge_item,
                "metadata": {
                    "category": "risk_calculation",
                    "source": "domain_risk_knowledge",
                    "domain": domain_config.domain_name
                }
            }
            for knowledge_item in risk_knowledge_base
        ]
        
        # Also retrieve additional risk-specific knowledge from retrieval helper if available
        retrieved_risk_docs = []
        if self.retrieval_helper:
            try:
                # Search for additional risk calculation knowledge
                risk_queries = [
                    f"risk calculation {domain_config.domain_name}",
                    f"impact likelihood calculation {domain_config.domain_name}",
                    f"breach likelihood {domain_config.domain_name}",
                    f"asset risk calculation {domain_config.domain_name}",
                    f"vulnerability risk {domain_config.domain_name}"
                ]
                
                for query in risk_queries:
                    docs = await self.retrieval_helper.retrieve(
                        query=query,
                        project_id=project_id,
                        top_k=3
                    )
                    retrieved_risk_docs.extend(docs)
                
                # Deduplicate by content
                seen_content = set()
                unique_docs = []
                for doc in retrieved_risk_docs:
                    content_hash = hash(doc.get("content", ""))
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        unique_docs.append(doc)
                
                retrieved_risk_docs = unique_docs[:10]  # Limit to 10 docs
                logger.info(f"Retrieved {len(retrieved_risk_docs)} additional risk calculation knowledge documents")
            except Exception as e:
                logger.warning(f"Error retrieving additional risk knowledge: {e}")
        
        # Combine risk knowledge: base risk knowledge + retrieved risk docs + general knowledge documents
        # Note: General knowledge_documents may contain feature engineering knowledge, but risk knowledge takes priority
        all_knowledge = risk_knowledge_docs + retrieved_risk_docs + knowledge_documents
        logger.info(f"Using {len(risk_knowledge_docs)} base risk knowledge items + {len(retrieved_risk_docs)} retrieved + {len(knowledge_documents)} general knowledge documents")
        
        # Format standard features for context
        standard_features_text = "\n".join([
            f"{i+1}. {f.get('feature_name', 'Unknown')} ({f.get('feature_type', 'Unknown')}): {f.get('natural_language_question', 'N/A')[:200]}"
            for i, f in enumerate(standard_features[:20])
        ])
        
        # Format risk knowledge
        risk_knowledge = self._format_risk_knowledge(all_knowledge)
        
        # Get risk calculation examples
        risk_examples = self._get_risk_calculation_examples(domain_config.domain_name)
        
        # Format schema info
        schema_info = self._format_schema_info(schema_registry, relevant_schemas)
        
        # Get reasoning plan if available (may be created earlier or in resume scenarios)
        reasoning_plan = state.get("reasoning_plan", {})
        reasoning_plan_context = ""
        if reasoning_plan:
            reasoning_plan_context = self._format_reasoning_plan_context(reasoning_plan)
        
        system_prompt = f"""You are a risk modeling expert specializing in building risk, impact, and likelihood features from standard operational metrics.

GOAL: Generate risk, impact, and likelihood features that use the standard metrics/KPIs as building blocks. These features implement risk modeling principles to calculate:
1. IMPACT features: What is the consequence if this entity/control fails?
2. LIKELIHOOD features: What is the probability of failure/breach?
3. RISK features: Combined risk scores (typically Impact × Likelihood or weighted combination)

RISK MODELING PRINCIPLES:
- Impact = Consequence severity (regulatory, financial, operational, downstream effects)
- Likelihood = Probability of failure (historical patterns, current indicators, exposure)
- Risk = Impact × Likelihood (or weighted: Risk = (Impact * 0.6) + (Likelihood * 0.4))

MEDALLION ARCHITECTURE:
- These risk features are GOLD layer (require aggregations and multi-step calculations)
- They build upon SILVER and GOLD standard metrics

IMPORTANT: You have access to DOMAIN-SPECIFIC RISK CALCULATION KNOWLEDGE (loaded from domain configuration) that provides detailed methodologies for:
- Asset impact classification (Mission Critical, Critical, Other)
- Asset propagation classification (Perimeter, Core)
- Breach likelihood calculations from vulnerabilities, unpatched vulns, CISA exploits
- Risk calculations with context multipliers
- Cloud asset risk calculations
- Compliance and regulatory risk (GDPR, PCI-DSS, HIPAA, SOX)
- Industry-specific risk (financial services, healthcare, manufacturing, retail)
- Advanced threat-based risk (ransomware, APT, supply chain, data exfiltration)
- Insider threat risk
- Network segmentation and isolation risk
- Asset lifecycle risk
- Cryptographic and encryption risk
- Operational risk

This risk knowledge is SEPARATE from general feature engineering knowledge and provides deep research capabilities for building sophisticated risk features.

STANDARD METRICS AVAILABLE:
{standard_features_text}

COMPREHENSIVE RISK CALCULATION KNOWLEDGE:
{risk_knowledge}

DOMAIN-SPECIFIC RISK EXAMPLES:
{risk_examples}

AVAILABLE SCHEMAS:
{schema_info}

ANALYTICAL INTENT:
{analytical_intent}

USER QUERY:
{user_query}

{reasoning_plan_context}

Generate risk, impact, and likelihood features that:

1. USE STANDARD METRICS: Reference and build upon the standard metrics provided above
2. IMPLEMENT RISK PRINCIPLES: Follow impact × likelihood risk calculation patterns
3. USE DOMAIN KNOWLEDGE: Apply domain-specific risk calculation methods from the knowledge provided
4. ALIGN WITH REASONING PLAN: If a reasoning plan is provided above, ensure your risk features align with the plan's data flow, dependencies, and calculation steps
5. ARE DETAILED: Provide step-by-step natural language questions that can be executed

For each feature, provide:
1. Feature name (e.g., asset_risk_score, vulnerability_breach_likelihood, training_completion_impact)
2. Feature type (risk, impact, likelihood)
3. Natural language question (DETAILED step-by-step calculation using standard metrics and risk principles)
4. Calculation logic (How to combine standard metrics using risk formulas)
5. Required standard features (Which standard metrics this feature depends on)
6. Required schemas
7. Business context (Why this risk feature matters)
8. Transformation layer (MUST be 'gold' - these require aggregations)
9. Time series type (usually 'snapshot' for point-in-time risk assessment)

OUTPUT FORMAT:
Provide features in numbered lists, grouped by type:

=== IMPACT FEATURES ===
1. **Feature Name**: [name] - **Feature Type**: impact - **Natural Language Question**: [detailed question] - **Calculation Logic**: [logic] - **Depends on Standard Features**: [list] - **Required Schemas**: [schemas] - **Business Context**: [context] - **Transformation Layer**: gold - **Time Series Type**: [type]

=== LIKELIHOOD FEATURES ===
1. **Feature Name**: [name] - **Feature Type**: likelihood - **Natural Language Question**: [detailed question] - **Calculation Logic**: [logic] - **Depends on Standard Features**: [list] - **Required Schemas**: [schemas] - **Business Context**: [context] - **Transformation Layer**: gold - **Time Series Type**: [type]

=== RISK FEATURES ===
1. **Feature Name**: [name] - **Feature Type**: risk - **Natural Language Question**: [detailed question] - **Calculation Logic**: [logic] - **Depends on Standard Features**: [list] - **Required Schemas**: [schemas] - **Business Context**: [context] - **Transformation Layer**: gold - **Time Series Type**: [type]

Generate 3-5 impact features, 3-5 likelihood features, and 2-4 risk features."""

        response = await track_llm_call(
            agent_name="RiskFeatureEngineeringAgent",
            llm=self.llm,
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content="Generate risk, impact, and likelihood features from standard metrics")
            ],
            state=state,
            step_name="risk_feature_engineering"
        )
        
        # Parse the response to extract impact, likelihood, and risk features
        parsed_features = self._parse_risk_features(response.content)
        
        # Separate by type
        impact_features = [f for f in parsed_features if f.get("feature_type", "").lower() == "impact"]
        likelihood_features = [f for f in parsed_features if f.get("feature_type", "").lower() == "likelihood"]
        risk_features = [f for f in parsed_features if f.get("feature_type", "").lower() == "risk"]
        
        state["impact_features"] = impact_features
        state["likelihood_features"] = likelihood_features
        state["risk_features"] = risk_features
        
        # Keep standard features separate - don't combine yet
        # A separate combination agent will handle merging
        
        state["messages"].append(AIMessage(
            content=f"Generated {len(impact_features)} impact, {len(likelihood_features)} likelihood, and {len(risk_features)} risk features from standard metrics",
            name="RiskFeatureEngineeringAgent"
        ))
        
        # Route to combination agent or feature_dependency
        state["next_agent"] = "feature_combination"
        
        return state
    
    def _format_schema_info(self, schema_registry: Dict[str, Any], relevant_schemas: List[str]) -> str:
        """Format schema information for the prompt"""
        if not schema_registry:
            return ", ".join(relevant_schemas) if relevant_schemas else "No schemas available"
        
        info_parts = []
        for schema_name in relevant_schemas:
            if schema_name in schema_registry:
                schema_info = schema_registry[schema_name]
                desc = schema_info.get("description", "")
                fields = schema_info.get("key_fields", [])
                info_parts.append(f"{schema_name}: {desc}\n  Key fields: {', '.join(fields[:10])}")
        
        return "\n".join(info_parts) if info_parts else "No schema details available"
    
    def _parse_risk_features(self, content: str) -> List[Dict[str, Any]]:
        """Parse risk, impact, and likelihood features from LLM response"""
        features = []
        
        # Helper function to extract field value
        def extract_field(pattern, text):
            """Extract field value that may be between dashes or at end"""
            match = re.search(pattern + r'[:\*]?\s*(?:\*\*)?\s*(.+?)(?:\s*-\s*\*\*|$)', text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                value = re.sub(r'\*\*$', '', value).strip()
                return value
            return None
        
        # Split by feature type sections
        sections = {
            "impact": re.split(r'===?\s*IMPACT\s+FEATURES?\s*===?', content, flags=re.IGNORECASE),
            "likelihood": re.split(r'===?\s*LIKELIHOOD\s+FEATURES?\s*===?', content, flags=re.IGNORECASE),
            "risk": re.split(r'===?\s*RISK\s+FEATURES?\s*===?', content, flags=re.IGNORECASE)
        }
        
        for feature_type, parts in sections.items():
            if len(parts) > 1:
                section_content = parts[1]
                # Split by numbered items
                feature_parts = re.split(r'(?=\d+\.)', section_content)
                
                for part in feature_parts:
                    if not part.strip() or not re.match(r'^\d+\.', part.strip()):
                        continue
                    
                    feature = {}
                    part_clean = part.strip()
                    
                    # Extract feature name
                    name_match = re.search(r'^\d+\.\s*(?:\*\*)?(?:Feature\s+Name|Feature Name|Name)[:\*]?\s*(?:\*\*)?\s*([^-]+?)(?:\s*-\s*\*\*|$)', part_clean, re.IGNORECASE)
                    if name_match:
                        feature["feature_name"] = name_match.group(1).strip()
                    else:
                        # Try simpler pattern
                        name_match = re.search(r'^\d+\.\s*(?:[^\w]*)?([a-z_][a-z0-9_]*(?:_[a-z0-9_]+)*)', part_clean, re.IGNORECASE)
                        if name_match:
                            feature["feature_name"] = name_match.group(1).strip()
                    
                    # Clean up feature name
                    if "feature_name" in feature:
                        feature["feature_name"] = re.sub(r'^\s*\*+\s*:?\s*', '', feature["feature_name"]).strip()
                        feature["feature_name"] = re.sub(r'[:*]+\s*$', '', feature["feature_name"]).strip()
                    
                    # Set feature type
                    feature["feature_type"] = feature_type
                    
                    # Extract other fields
                    question_val = extract_field(r'(?:\*\*)?(?:Natural\s+Language\s+Question|Natural Language Question|Question|NLQ)', part_clean)
                    if question_val:
                        feature["natural_language_question"] = question_val
                    
                    calc_val = extract_field(r'(?:\*\*)?(?:Calculation\s+Logic|Calculation Logic|Logic)', part_clean)
                    if calc_val:
                        feature["calculation_logic"] = calc_val
                    
                    deps_val = extract_field(r'(?:\*\*)?(?:Depends\s+on\s+Standard\s+Features|Depends on Standard Features|Depends on)', part_clean)
                    if deps_val:
                        feature["depends_on_standard_features"] = [f.strip() for f in deps_val.split(",") if f.strip()]
                    
                    schema_val = extract_field(r'(?:\*\*)?(?:Required\s+Schemas|Required Schemas|Schemas)', part_clean)
                    if schema_val:
                        feature["required_schemas"] = [s.strip() for s in schema_val.split(",") if s.strip()]
                    
                    context_val = extract_field(r'(?:\*\*)?(?:Business\s+Context|Business Context|Context)', part_clean)
                    if context_val:
                        feature["business_context"] = context_val
                    
                    layer_val = extract_field(r'(?:\*\*)?(?:Transformation\s+Layer|Transformation Layer|Layer)', part_clean)
                    if layer_val:
                        feature["transformation_layer"] = layer_val.lower().strip()
                    else:
                        feature["transformation_layer"] = "gold"  # Default for risk features
                    
                    ts_val = extract_field(r'(?:\*\*)?(?:Time\s+Series\s+Type|Time Series Type|Time Series)', part_clean)
                    if ts_val:
                        ts_lower = ts_val.lower().strip()
                        if ts_lower == "none" or "not" in ts_lower:
                            feature["time_series_type"] = None
                        else:
                            feature["time_series_type"] = ts_lower
                    else:
                        feature["time_series_type"] = "snapshot"  # Default for risk features
                    
                    # Set defaults
                    if "feature_name" in feature and feature["feature_name"]:
                        feature.setdefault("natural_language_question", f"Calculate {feature['feature_name'].replace('_', ' ')}")
                        feature.setdefault("calculation_logic", "N/A")
                        feature.setdefault("depends_on_standard_features", [])
                        feature.setdefault("required_schemas", [])
                        feature.setdefault("business_context", f"Risk feature for {feature_type} assessment")
                        feature.setdefault("soc2_compliance_reasoning", feature.get("business_context", ""))
                        features.append(feature)
        
        # Fallback: if no features found, try using the standard feature parsing
        if not features:
            # Use similar parsing to FeatureRecommendationAgent
            parts = re.split(r'(?=\d+\.)', content)
            for part in parts:
                if not part.strip() or not re.match(r'^\d+\.', part.strip()):
                    continue
                
                # Try to infer type from content
                part_lower = part.lower()
                if "impact" in part_lower and "likelihood" not in part_lower and "risk" not in part_lower:
                    feature_type = "impact"
                elif "likelihood" in part_lower and "risk" not in part_lower:
                    feature_type = "likelihood"
                elif "risk" in part_lower:
                    feature_type = "risk"
                else:
                    continue  # Skip if can't determine type
                
                # Extract feature name
                name_match = re.search(r'^\d+\.\s*(?:[^\w]*)?([a-z_][a-z0-9_]*(?:_[a-z0-9_]+)*)', part, re.IGNORECASE)
                if name_match:
                    feature = {
                        "feature_name": name_match.group(1).strip(),
                        "feature_type": feature_type,
                        "natural_language_question": f"Calculate {name_match.group(1).strip().replace('_', ' ')}",
                        "calculation_logic": "N/A",
                        "depends_on_standard_features": [],
                        "required_schemas": [],
                        "business_context": f"Risk feature for {feature_type} assessment",
                        "transformation_layer": "gold",
                        "time_series_type": "snapshot"
                    }
                    features.append(feature)
        
        return features

