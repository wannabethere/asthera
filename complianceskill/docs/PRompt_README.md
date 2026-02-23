# Compliance-to-Operations LangGraph Agent Prompts

This directory contains the system prompts for each specialized agent in the compliance automation pipeline.

## Agent Topology

```
User Query
    ↓
01_intent_classifier.md → Categorizes request
    ↓
02_planner.md → Creates multi-step execution plan
    ↓
[Execution Phase - Retrieval & Generation]
    ├→ 03_detection_engineer.md → SIEM rules
    ├→ 04_playbook_writer.md → IR playbooks
    └→ 09_test_generator.md → Test scripts
    ↓
[Validation Phase]
    ├→ 05_siem_rule_validator.md → Validates SIEM rules
    ├→ 06_playbook_validator.md → Validates playbooks
    └→ (test_script_validator.md) → Validates tests
    ↓
07_feedback_analyzer.md → Routes failures back to generators
    ↓ (if validation fails)
[Iterative Refinement - max 3 iterations]
    ↓
08_artifact_assembler.md → Packages final deliverables
```

## Prompt Design Principles

Each prompt follows a consistent structure:

### 1. ROLE & PHILOSOPHY
- Clear agent identity
- Core operating principle (one sentence)

### 2. CONTEXT & MISSION
- What inputs the agent receives
- What outputs it must produce

### 3. OPERATIONAL WORKFLOW
- Step-by-step process
- Multi-phase structure

### 4. CORE DIRECTIVES
- **MUST** (obligations)
- **MUST NOT** (prohibitions)
- **BEST PRACTICES** (recommendations)

### 5. OUTPUT FORMAT
- Exact JSON schema
- Mandatory fields
- Examples

### 6. EXAMPLES
- Good examples
- Bad examples (anti-patterns)
- Edge cases

## Usage in LangGraph

```python
from langchain_core.prompts import ChatPromptTemplate

# Load prompt
with open("prompts/03_detection_engineer.md") as f:
    detection_engineer_prompt = f.read()

# Create agent node
def detection_engineer_node(state):
    prompt = ChatPromptTemplate.from_messages([
        ("system", detection_engineer_prompt),
        ("human", "{scenarios}\n{controls}\n{risks}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "scenarios": state["scenarios"],
        "controls": state["controls"],
        "risks": state["risks"]
    })
    
    # Parse and update state
    ...
```

## Customization Guide

To adapt these prompts for your specific needs:

1. **Framework-Specific Tuning**
   - Edit compliance_mappings sections
   - Adjust requirement reference formats
   - Update domain/control_type vocabularies

2. **SIEM Platform Targeting**
   - Modify 03_detection_engineer.md for your SIEM
   - Change output format from Splunk SPL to Elastic EQL, etc.

3. **Validation Strictness**
   - Adjust confidence_score thresholds in validators
   - Modify error vs. warning classifications
   - Change max_iterations in feedback_analyzer

4. **Output Formatting**
   - Change Markdown structure in playbook_writer
   - Adjust JSON schemas for your downstream systems
   - Customize file naming conventions

## Testing Prompts

Before deploying to production:

1. **Unit Test Each Agent**
   ```bash
   python test_prompts.py --agent intent_classifier --input "test_queries.json"
   ```

2. **Integration Test Full Pipeline**
   ```bash
   python test_pipeline.py --scenario "hipaa_breach_detection"
   ```

3. **Validation Stress Test**
   ```bash
   python test_validators.py --inject-errors
   ```

## Quality Metrics

Track these metrics to improve prompts:

- **Intent Classification Accuracy**: >90% correct on test set
- **Planning Efficiency**: 5-10 steps for complex, 2-4 for simple
- **Artifact Quality Score**: >85/100 average
- **Validation Pass Rate**: >80% on first attempt
- **Iteration Count**: <2 average refinements needed

## Version History

- v1.0 (2024-12-20): Initial agent topology
- v1.1 (TBD): Add cross-framework mapping agent
- v2.0 (TBD): Add gap analysis agent

## Contributing

When modifying prompts:
1. Update version history
2. Test with representative queries
3. Document changes in CHANGELOG.md
4. Validate JSON schema compliance
