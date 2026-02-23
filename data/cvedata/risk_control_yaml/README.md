# Risk Control YAML Files - Organized by Framework

This directory contains risk scenarios, controls, requirements, and test cases organized by compliance framework.

## Directory Structure

```
risk_control_yaml/
├── nist_csf_2_0/          # NIST Cybersecurity Framework 2.0
├── cis_controls_v8_1/     # CIS Controls v8.1
├── hipaa/                 # HIPAA (Health Insurance Portability and Accountability Act)
├── soc2/                  # SOC 2 (Service Organization Control 2)
├── iso27001_2013/         # ISO 27001:2013
├── iso27001_2022/         # ISO 27001:2022
└── common/                 # Cross-framework files
```

## File Types

Each framework folder contains:

- **`controls_*.yaml`**: Control definitions with mappings to framework requirements
- **`scenarios_*.yaml`**: Risk scenarios with control mappings
- **`requirements_*.yaml`**: Framework requirements mapped to controls
- **`*_risk_controls.yaml`**: Risk scenarios with associated controls (FAIR format)
- **`*_test_cases.yaml`**: Test cases for validating controls (NIST/CIS only)

## Framework Details

### NIST CSF 2.0
- **Controls**: Comprehensive mapping of NIST CSF controls
- **Scenarios**: Risk scenarios mapped to NIST functions and categories
- **Risk Controls**: Agentic-generated risk scenarios with control mappings
- **Test Cases**: Test cases for risk validation

### CIS Controls v8.1
- **Controls**: CIS Controls v8.1 implementation groups
- **Scenarios**: Risk scenarios mapped to CIS controls
- **Risk Controls**: Agentic-generated risk scenarios with control mappings
- **Test Cases**: Test cases for risk validation

### HIPAA
- **Controls**: HIPAA security rule controls
- **Scenarios**: Risk scenarios for healthcare data protection
- **Requirements**: HIPAA requirements mapped to controls
- **Risk Controls**: Risk scenarios in FAIR format

### SOC 2
- **Controls**: SOC 2 trust service criteria controls
- **Scenarios**: Risk scenarios for service organizations
- **Requirements**: SOC 2 requirements mapped to controls
- **Risk Controls**: Risk scenarios in FAIR format

### ISO 27001:2013
- **Controls**: ISO 27001:2013 Annex A controls
- **Scenarios**: Risk scenarios mapped to ISO controls
- **Requirements**: ISO 27001:2013 requirements
- **Risk Controls**: Risk scenarios in FAIR format

### ISO 27001:2022
- **Controls**: ISO 27001:2022 Annex A controls (updated)
- **Scenarios**: Risk scenarios mapped to ISO controls
- **Requirements**: ISO 27001:2022 requirements
- **Risk Controls**: Risk scenarios in FAIR format

### Common
- **all_frameworks_risk_controls.yaml**: Consolidated risk controls across all frameworks

## Usage

### Accessing Framework Files

```python
from pathlib import Path

base_path = Path("risk_control_yaml")

# NIST CSF files
nist_controls = base_path / "nist_csf_2_0" / "controls_nist_csf_2_0.yaml"
nist_scenarios = base_path / "nist_csf_2_0" / "scenarios_nist_csf_2_0.yaml"
nist_risks = base_path / "nist_csf_2_0" / "nist_csf_2_0_risk_controls.yaml"

# HIPAA files
hipaa_controls = base_path / "hipaa" / "controls_hipaa.yaml"
hipaa_requirements = base_path / "hipaa" / "requirements_hipaa.yaml"
```

### Generating New Risk Files

Use the `generate_risks_agentic.py` script to generate or update risk files:

```bash
# Generate NIST and CIS risks with AI enhancement
python generate_risks_agentic.py

# Output files will be created in respective framework folders
```

## File Formats

### Controls Format
```yaml
-
  control_id: AST-66
  name: Inventory of information and other associated assets
  description: |
    An inventory of information and other associated assets...
  domain: ASSET_MANAGEMENT
  type: preventive
```

### Scenarios Format
```yaml
-
  scenario_id: NIST-RISK-001
  name: Unauthorized access to sensitive data
  asset: information_security_operations
  trigger: control failure
  mitigated_by:
    - AST-66
    - IAC-1
```

### Risk Controls Format (FAIR)
```yaml
-
  scenario_id: NIST-RISK-001
  name: Unauthorized access to sensitive data
  asset: information_security_operations
  trigger: control failure
  loss_outcomes:
    - breach
    - compliance violation
  controls:
    -
      control_id: AST-66
      name: Inventory of information and other associated assets
      type: preventive
```

## Notes

- Files are organized by framework for easy navigation
- Each framework maintains its own controls, scenarios, and requirements
- Risk control files follow the FAIR (Factor Analysis of Information Risk) methodology
- Test cases are available for NIST CSF and CIS Controls frameworks
