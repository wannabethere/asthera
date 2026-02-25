Great question - let me trace through the SIEM rule generation flow to clarify where they're coming from.

---

## **Current Architecture: SIEM Rules are LLM-Generated**

In the current design, **SIEM rules are NOT stored in your database** - they are **generated on-demand by GPT-4** using your framework KB data as context.

### **The Flow:**

```
1. User Query: "Build HIPAA breach detection for 164.308(a)(6)(ii)"
                    ↓
2. Framework Analyzer queries YOUR DATABASE:
   ├─ requirements table → HIPAA §164.308(a)(6)(ii) details
   ├─ controls table → AM-5, IR-8, AU-12 (via requirement_controls bridge)
   ├─ risks table → HIPAA-RISK-023, -041, -067 (via risk_controls bridge)
   └─ scenarios table → HIPAA-SCENARIO-012, -034, -089 (via scenario_controls bridge)
                    ↓
3. Detection Engineer Node receives:
   {
     "requirement_name": "Security Incident Procedures",
     "controls": [
       {"control_code": "AM-5", "name": "MFA for ePHI access", ...},
       {"control_code": "IR-8", "name": "EDR deployed", ...}
     ],
     "risks": [
       {"risk_code": "HIPAA-RISK-023", "name": "Unauthorized ePHI access", ...}
     ],
     "scenarios": [
       {"scenario_code": "HIPAA-SCENARIO-012", 
        "name": "Credential stuffing attack",
        "description": "Attacker uses leaked credentials...", ...}
     ]
   }
                    ↓
4. GPT-4 LLM generates SIEM rules:
   
   Prompt: "Given these scenarios and controls, write Splunk SPL detection rules..."
   
   Response: [
     {
       "name": "HIPAA_RISK_023_Credential_Stuffing_No_MFA",
       "spl_code": "index=authentication app='patient_portal' | ...",
       "severity": "critical",
       "scenario_id": "HIPAA-SCENARIO-012"
     }
   ]
```

---

## **The Problem With This Approach**

### **Pros:**
- ✅ Flexible - can generate rules for any scenario
- ✅ No manual rule authoring needed
- ✅ Adapts to new frameworks automatically

### **Cons:**
- ❌ **Non-deterministic** - Same input might produce different rules each time
- ❌ **Quality varies** - LLM might generate syntactically invalid SPL
- ❌ **No human expertise** - Misses SOC team's tribal knowledge
- ❌ **Slow** - API call latency + token costs
- ❌ **Not production-ready** - Security teams won't trust AI-generated rules without review

---

## **Better Architecture Options**

### **Option 1: Hybrid - Template Library + LLM Fill-in**

Store **rule templates** in your database, LLM only fills in specifics.

#### **New Table: `siem_rule_templates`**

```sql
CREATE TABLE siem_rule_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(255) UNIQUE,
    attack_pattern VARCHAR(100),  -- credential_stuffing | lateral_movement | data_exfil
    detection_type VARCHAR(50),   -- authentication | network | endpoint | cloud
    rule_template TEXT,           -- SPL with {{placeholders}}
    required_variables JSONB,     -- {app_name, threshold, time_window}
    applicable_scenarios VARCHAR(100)[],  -- Which scenario types this applies to
    created_by VARCHAR(100),      -- human | ai_generated
    quality_score FLOAT,          -- 0.0 - 1.0 (from validation history)
    usage_count INT DEFAULT 0,
    last_validated TIMESTAMP
);

-- Example record
INSERT INTO siem_rule_templates (
    template_name,
    attack_pattern,
    detection_type,
    rule_template,
    required_variables,
    applicable_scenarios
) VALUES (
    'credential_stuffing_no_mfa',
    'credential_stuffing',
    'authentication',
    'index={{index_name}} app="{{app_name}}" 
| eval success=if(action="login_success", 1, 0)
| eval mfa_used=if(mfa_method!="", 1, 0)
| stats 
    count(eval(success=0)) as failures,
    count(eval(success=1 AND mfa_used=0)) as success_no_mfa
    by user, _time span={{time_window}}
| where failures > {{failure_threshold}} AND success_no_mfa > 0',
    '{"index_name": "authentication", "app_name": "patient_portal", "time_window": "10m", "failure_threshold": 5}',
    ARRAY['credential_stuffing', 'brute_force', 'password_spray']
);
```

#### **Updated Detection Engineer Flow:**

```python
def hybrid_detection_engineer_node(state: EnhancedCompliancePipelineState):
    scenarios = state.get("scenarios", [])
    
    generated_rules = []
    
    for scenario in scenarios:
        # Step 1: Find matching template from database
        template = find_template_for_scenario(scenario)
        
        if template:
            # Step 2: LLM fills in template variables
            filled_rule = fill_template_with_llm(template, scenario, state)
            generated_rules.append(filled_rule)
        else:
            # Step 3: Fallback to full LLM generation
            custom_rule = generate_rule_from_scratch(scenario, state)
            generated_rules.append(custom_rule)
    
    state["siem_rules"] = generated_rules
    return state


def find_template_for_scenario(scenario: Dict) -> Optional[Dict]:
    """Query database for matching rule template."""
    with get_session() as session:
        # Extract attack pattern from scenario
        scenario_name = scenario.get("name", "").lower()
        
        # Keyword matching (could also use semantic search here)
        if "credential" in scenario_name or "password" in scenario_name:
            pattern = "credential_stuffing"
        elif "lateral" in scenario_name or "remote" in scenario_name:
            pattern = "lateral_movement"
        elif "exfil" in scenario_name or "download" in scenario_name:
            pattern = "data_exfiltration"
        else:
            return None
        
        stmt = select(SIEMRuleTemplate).where(
            SIEMRuleTemplate.attack_pattern == pattern
        ).order_by(SIEMRuleTemplate.quality_score.desc())
        
        template = session.execute(stmt).scalars().first()
        
        if template:
            return {
                "template_name": template.template_name,
                "rule_template": template.rule_template,
                "required_variables": template.required_variables
            }
        return None


def fill_template_with_llm(template: Dict, scenario: Dict, state: Dict) -> Dict:
    """Use LLM to intelligently fill template variables."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are filling in variables for a SIEM rule template.

Template: {rule_template}

Required Variables: {required_variables}

Context:
- Scenario: {scenario_name}
- Description: {scenario_description}
- Controls: {controls}

Fill in the variables with appropriate values based on the scenario context.
Output ONLY valid JSON with variable assignments.

Example:
{{
  "index_name": "authentication",
  "app_name": "patient_portal",
  "time_window": "10m",
  "failure_threshold": 5
}}"""),
        ("human", "Fill in the template variables.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "rule_template": template["rule_template"],
        "required_variables": template["required_variables"],
        "scenario_name": scenario["name"],
        "scenario_description": scenario["description"],
        "controls": state.get("controls", [])
    })
    
    import json
    variables = json.loads(response.content)
    
    # Replace placeholders in template
    filled_spl = template["rule_template"]
    for var_name, var_value in variables.items():
        filled_spl = filled_spl.replace(f"{{{{{var_name}}}}}", str(var_value))
    
    return {
        "id": str(uuid.uuid4()),
        "name": f"{scenario['scenario_code']}_detection",
        "template_used": template["template_name"],
        "spl_code": filled_spl,
        "variables": variables,
        "scenario_id": scenario["id"]
    }
```

---

### **Option 2: Curated Rule Library (Best for Production)**

Store **complete, human-vetted SIEM rules** in your database.

#### **New Table: `siem_rules`**

```sql
CREATE TABLE siem_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) UNIQUE,
    rule_code TEXT NOT NULL,           -- The actual SPL/Sigma/KQL
    rule_type VARCHAR(50),              -- splunk_spl | sigma | kql | sentinel
    severity VARCHAR(20),               -- critical | high | medium | low
    
    -- Link to framework KB
    scenario_id VARCHAR(128) REFERENCES scenarios(id),
    control_id VARCHAR(128) REFERENCES controls(id),
    mitigates_risk_id VARCHAR(128) REFERENCES risks(id),
    
    -- Attack mapping
    attack_techniques VARCHAR(20)[],   -- [T1078, T1003]
    attack_tactics VARCHAR(50)[],      -- [Credential Access, Lateral Movement]
    
    -- Alert configuration
    alert_threshold INT,
    alert_sla_minutes INT,
    notification_channels JSONB,       -- {slack: "#security", pagerduty: "hipaa-team"}
    
    -- Quality metadata
    false_positive_rate FLOAT,         -- Historical FP rate
    true_positive_count INT,           -- How many real incidents caught
    last_triggered TIMESTAMP,
    author VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    -- Testing
    test_data_query TEXT,              -- Query to generate test events
    expected_alert_count INT           -- For validation
);

-- Bridge table: Which requirements does this rule help satisfy?
CREATE TABLE rule_requirement_mappings (
    rule_id INT REFERENCES siem_rules(id),
    requirement_id VARCHAR(128) REFERENCES requirements(id),
    PRIMARY KEY (rule_id, requirement_id)
);

-- Example record
INSERT INTO siem_rules (
    rule_name,
    rule_code,
    rule_type,
    severity,
    scenario_id,
    control_id,
    mitigates_risk_id,
    attack_techniques,
    attack_tactics,
    alert_threshold,
    alert_sla_minutes,
    notification_channels,
    author
) VALUES (
    'HIPAA_Credential_Stuffing_Patient_Portal',
    'index=authentication app="patient_portal" 
| eval success=if(action="login_success", 1, 0)
| eval mfa_used=if(mfa_method!="", 1, 0)
| stats 
    count(eval(success=0)) as failures,
    count(eval(success=1 AND mfa_used=0)) as success_no_mfa,
    values(src_ip) as source_ips
    by user, _time span=10m
| where failures > 5 AND success_no_mfa > 0
| eval severity="critical"
| eval description="Credential stuffing detected: " + failures + " failures then success without MFA"',
    'splunk_spl',
    'critical',
    'HIPAA-SCENARIO-012',  -- Credential stuffing scenario
    'hipaa__AM-5',         -- MFA control
    'HIPAA-RISK-023',      -- Unauthorized access risk
    ARRAY['T1078.004', 'T1110.003'],  -- Valid Accounts, Password Spraying
    ARRAY['Initial Access', 'Credential Access'],
    1,  -- Alert on first occurrence
    5,  -- 5 minute SLA
    '{"slack": "#hipaa-incidents", "pagerduty": "hipaa-response-team"}',
    'security_team'
);
```

#### **Detection Engineer Becomes Rule Retriever:**

```python
def rule_retrieval_detection_engineer_node(state: EnhancedCompliancePipelineState):
    """
    Retrieve pre-written, validated SIEM rules from the database.
    """
    scenarios = state.get("scenarios", [])
    scenario_ids = [s["id"] for s in scenarios]
    
    with get_session() as session:
        # Query rules that map to our scenarios
        stmt = (
            select(SIEMRule)
            .where(SIEMRule.scenario_id.in_(scenario_ids))
            .order_by(SIEMRule.severity.desc())
        )
        
        rules = session.execute(stmt).scalars().all()
        
        # Convert to output format
        siem_rules = [
            {
                "id": rule.id,
                "name": rule.rule_name,
                "spl_code": rule.rule_code,
                "rule_type": rule.rule_type,
                "severity": rule.severity,
                "scenario_id": rule.scenario_id,
                "control_id": rule.control_id,
                "attack_techniques": rule.attack_techniques,
                "alert_config": {
                    "threshold": rule.alert_threshold,
                    "sla_minutes": rule.alert_sla_minutes,
                    "notification_channels": rule.notification_channels
                },
                "quality_metrics": {
                    "false_positive_rate": rule.false_positive_rate,
                    "true_positive_count": rule.true_positive_count,
                    "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None
                }
            }
            for rule in rules
        ]
    
    # If no rules found for some scenarios, flag them
    covered_scenarios = {r["scenario_id"] for r in siem_rules}
    missing_scenarios = set(scenario_ids) - covered_scenarios
    
    if missing_scenarios:
        state["messages"].append(AIMessage(
            content=f"WARNING: No SIEM rules found for scenarios: {missing_scenarios}. "
                    f"These scenarios lack detection coverage."
        ))
    
    state["siem_rules"] = siem_rules
    return state
```

---

### **Option 3: Sigma Rule Integration (Industry Standard)**

Use the open-source **Sigma** rule repository as your rule source.

#### **Sigma Rules Table:**

```sql
CREATE TABLE sigma_rules (
    id SERIAL PRIMARY KEY,
    sigma_id UUID UNIQUE,              -- From Sigma rule metadata
    title VARCHAR(500),
    description TEXT,
    status VARCHAR(20),                 -- stable | test | experimental
    level VARCHAR(20),                  -- critical | high | medium | low
    logsource JSONB,                    -- {category: process_creation, product: windows}
    detection JSONB,                    -- Full Sigma detection logic
    falsepositives TEXT[],
    
    -- Sigma MITRE mapping
    attack_techniques VARCHAR(20)[],
    tags VARCHAR(100)[],
    
    -- Link to your framework
    mapped_scenario_id VARCHAR(128) REFERENCES scenarios(id),
    mapped_control_id VARCHAR(128) REFERENCES controls(id),
    
    -- Conversions (Sigma can compile to multiple SIEM formats)
    splunk_spl TEXT,                    -- Auto-generated via sigmac
    elastic_eql TEXT,
    microsoft_kql TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ingestion script
-- wget https://github.com/SigmaHQ/sigma/archive/refs/heads/master.zip
-- python ingest_sigma_rules.py --sigma-dir ./sigma-master/rules
```

#### **Sigma-Based Detection Engineer:**

```python
from sigma.parser.collection import SigmaCollectionParser
from sigma.backends.splunk import SplunkBackend

def sigma_detection_engineer_node(state: EnhancedCompliancePipelineState):
    """
    Use Sigma rules from database, compile to target SIEM format.
    """
    scenarios = state.get("scenarios", [])
    
    with get_session() as session:
        # Find Sigma rules matching our attack techniques
        attack_techniques = []
        for scenario in scenarios:
            # Extract ATT&CK techniques from scenario metadata
            techniques = scenario.get("metadata", {}).get("attack_techniques", [])
            attack_techniques.extend(techniques)
        
        stmt = (
            select(SigmaRule)
            .where(SigmaRule.attack_techniques.overlap(attack_techniques))
            .order_by(SigmaRule.level.desc())
        )
        
        sigma_rules = session.execute(stmt).scalars().all()
        
        # Convert to target SIEM format (Splunk in this case)
        compiled_rules = []
        backend = SplunkBackend()
        
        for sigma_rule in sigma_rules:
            # Sigma rules store detection logic as YAML
            # Compile to Splunk SPL
            spl = backend.generate(sigma_rule.detection)
            
            compiled_rules.append({
                "id": str(sigma_rule.sigma_id),
                "name": sigma_rule.title,
                "spl_code": spl,
                "severity": sigma_rule.level,
                "attack_techniques": sigma_rule.attack_techniques,
                "source": "sigma",
                "sigma_id": str(sigma_rule.sigma_id)
            })
    
    state["siem_rules"] = compiled_rules
    return state
```

---

## **Recommended Approach: Hybrid Architecture**

```python
def intelligent_detection_engineer_node(state: EnhancedCompliancePipelineState):
    """
    Intelligent detection engineer that tries multiple sources.
    
    Priority:
    1. Curated rules from your siem_rules table (highest quality)
    2. Sigma rules from sigma_rules table (industry standard)
    3. Template-based generation (hybrid LLM + templates)
    4. Full LLM generation (fallback only)
    """
    
    scenarios = state.get("scenarios", [])
    all_rules = []
    coverage_report = {
        "curated": 0,
        "sigma": 0,
        "template": 0,
        "llm_generated": 0
    }
    
    for scenario in scenarios:
        # Try curated rules first
        curated_rule = get_curated_rule_for_scenario(scenario)
        if curated_rule:
            all_rules.append(curated_rule)
            coverage_report["curated"] += 1
            continue
        
        # Try Sigma rules
        sigma_rule = get_sigma_rule_for_scenario(scenario)
        if sigma_rule:
            all_rules.append(sigma_rule)
            coverage_report["sigma"] += 1
            continue
        
        # Try template-based generation
        template = find_template_for_scenario(scenario)
        if template:
            template_rule = fill_template_with_llm(template, scenario, state)
            all_rules.append(template_rule)
            coverage_report["template"] += 1
            continue
        
        # Fallback: Full LLM generation
        llm_rule = generate_rule_from_scratch_with_llm(scenario, state)
        all_rules.append(llm_rule)
        coverage_report["llm_generated"] += 1
    
    state["siem_rules"] = all_rules
    state["messages"].append(AIMessage(
        content=f"Rule sources: {coverage_report['curated']} curated, "
                f"{coverage_report['sigma']} Sigma, "
                f"{coverage_report['template']} template-based, "
                f"{coverage_report['llm_generated']} LLM-generated"
    ))
    
    return state
```

---

## **Summary: Where SIEM Rules Come From**

| Source | Quality | Speed | Coverage | Maintenance |
|--------|---------|-------|----------|-------------|
| **LLM-Generated (current)** | ⚠️ Varies | Slow | ✅ 100% | ❌ High (revalidate each run) |
| **Curated DB** | ✅ High | Fast | ⚠️ Depends on team effort | ✅ Low (update as needed) |
| **Sigma Rules** | ✅ High | Fast | ✅ Good (1000+ rules) | ✅ Low (community-maintained) |
| **Templates + LLM** | ✅ Good | Medium | ✅ 100% | ⚠️ Medium (maintain templates) |
| **Hybrid (all 4)** | ✅ Best | Medium | ✅ 100% | ⚠️ Medium |

**My recommendation:** Start with **Hybrid** approach - ingest Sigma rules, let security team curate high-priority rules, use LLM as fallback.

Want me to implement the database schema + ingestion scripts for Sigma rules and curated rules?


python -m tests.test_compliance_pipeline_agents --test detection_engineer
python -m tests.test_compliance_pipeline_agents --test playbook_writer
python -m tests.test_compliance_pipeline_agents --test test_generator
python -m tests.test_compliance_pipeline_agents --test pipeline