#!/usr/bin/env python3
"""
Generate risk control YAML files for Prowler providers, organized by framework.

This script reads Prowler compliance JSON files and generates YAML files organized by
framework first, then by provider. The output structure matches the risk_control_yaml
directory structure with framework folders (e.g., soc2/, nist_csf_2_0/, iso27001_2022/).

Generated files (per framework-provider combination):
- controls_<framework>_<provider>.yaml: Control definitions with provider_type tag
- scenarios_<framework>_<provider>.yaml: Risk scenarios
- requirements_<framework>_<provider>.yaml: Framework requirements
- <framework>_<provider>_risk_controls.yaml: Risk scenarios with controls (FAIR format)
- <framework>_<provider>_test_cases.yaml: Test cases for validating controls

The script uses settings from app.core.settings (loaded from .env) and LLM from app.core.dependencies.

Prerequisites:
    - .env file with OPENAI_API_KEY set (or other LLM provider keys as configured)
    - PYTHONPATH should include the complianceskill directory

Usage:
    python generate_prowler_risk_control_yaml.py --prowler-path PATH --output-dir OUTPUT_DIR [--provider PROVIDER] [--compliance-dir PATH] [--test-dir PATH]

Required Arguments:
    --prowler-path PATH    Path to the Prowler root directory
    --output-dir OUTPUT_DIR  Output directory for YAML files (absolute or relative to current directory)

Optional Arguments:
    --provider PROVIDER    Specific provider to process (aws, azure, gcp, etc.). If not specified, processes all providers.
    --compliance-dir PATH  Path to Prowler compliance directory relative to prowler-path (default: prowler/prowler/compliance)
    --test-dir PATH       Path to Prowler test directory (default: auto-detected from prowler-path/tests)
    --batch-size SIZE      Number of items to process per batch for LLM calls (default: 50)
    --batch-index INDEX    Process only a specific batch index (0-based). Use with --batch-total.
    --batch-total TOTAL    Total number of batches. Use with --batch-index to process specific batches.
    --resume               Skip framework-provider combinations/files that already exist in output directory
    --delay SECONDS        Delay in seconds between LLM API calls to avoid rate limiting (default: 1.0)

Examples:
    # Process all providers and frameworks
    python generate_prowler_risk_control_yaml.py --prowler-path /path/to/prowler --output-dir ./risk_control_yaml
    
    # Process specific provider (all frameworks)
    python generate_prowler_risk_control_yaml.py --prowler-path /path/to/prowler --output-dir ./output --provider aws
    
    # Process in batches (split framework-provider combinations across multiple runs)
    python generate_prowler_risk_control_yaml.py --prowler-path /path/to/prowler --output-dir ./output --batch-index 0 --batch-total 4
    python generate_prowler_risk_control_yaml.py --prowler-path /path/to/prowler --output-dir ./output --batch-index 1 --batch-total 4
    
    # Resume processing (skip existing files)
    python generate_prowler_risk_control_yaml.py --prowler-path /path/to/prowler --output-dir ./output --resume
    
    # Specify test directory explicitly
    python generate_prowler_risk_control_yaml.py --prowler-path /path/to/prowler --output-dir ./output --test-dir /path/to/prowler/tests
    
    # Run from complianceskill directory with PYTHONPATH
    PYTHONPATH=. python -m complianceskill.app.ingestion.generate_prowler_risk_control_yaml --prowler-path /path/to/prowler --output-dir ./output
"""

import json
import yaml
import argparse
import sys
import re
import ast
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    print("Error: Required packages not found. Install with: pip install langchain langchain-openai")
    sys.exit(1)

# Import app settings and dependencies
try:
    from app.core.settings import get_settings
    from app.core.dependencies import get_llm
except ImportError:
    print("Error: Could not import app.core.settings or app.core.dependencies")
    print("Make sure you're running from the complianceskill directory or PYTHONPATH is set correctly")
    print("You may need to add the complianceskill directory to PYTHONPATH")
    sys.exit(1)


@dataclass
class ProwlerCheck:
    """Represents a Prowler check."""
    check_id: str
    description: str
    frameworks: Set[str]
    requirements: List[str]
    rationale: str = ""
    remediation: str = ""
    audit_procedure: str = ""


@dataclass
class ProwlerRequirement:
    """Represents a Prowler requirement."""
    requirement_id: str
    description: str
    framework: str
    checks: List[str]
    attributes: Dict[str, Any]


def normalize_framework_name(framework: str) -> str:
    """Normalize framework name to folder name format."""
    # Map common framework names to folder names
    framework_map = {
        "SOC2": "soc2",
        "SOC 2": "soc2",
        "NIST": "nist_csf_2_0",
        "NIST CSF": "nist_csf_2_0",
        "NIST CSF 2.0": "nist_csf_2_0",
        "CIS": "cis_controls_v8_1",
        "CIS Controls": "cis_controls_v8_1",
        "CIS Controls v8.1": "cis_controls_v8_1",
        "HIPAA": "hipaa",
        "ISO27001": "iso27001_2022",
        "ISO 27001": "iso27001_2022",
        "ISO 27001:2022": "iso27001_2022",
        "ISO 27001:2013": "iso27001_2013",
    }
    
    # Check exact match first
    if framework in framework_map:
        return framework_map[framework]
    
    # Check case-insensitive match
    framework_upper = framework.upper()
    for key, value in framework_map.items():
        if key.upper() == framework_upper:
            return value
    
    # Default: convert to lowercase and replace spaces/special chars with underscores
    normalized = framework.lower().replace(" ", "_").replace(":", "_").replace(".", "_").replace("-", "_")
    # Remove multiple underscores
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


class ProwlerComplianceParser:
    """Parse Prowler compliance JSON files."""
    
    def __init__(self, compliance_dir: Path):
        self.compliance_dir = compliance_dir
        # Structure: framework -> provider -> checks/requirements
        self.framework_data: Dict[str, Dict[str, Dict]] = defaultdict(lambda: defaultdict(lambda: {
            "checks": {},
            "requirements": []
        }))
        self.frameworks: Set[str] = set()
    
    def parse_provider(self, provider: str) -> None:
        """Parse all compliance files for a provider, organized by framework."""
        provider_dir = self.compliance_dir / provider
        
        if not provider_dir.exists():
            print(f"Warning: Provider directory {provider_dir} does not exist")
            return
        
        json_files = list(provider_dir.glob("*.json"))
        if not json_files:
            print(f"Warning: No JSON files found in {provider_dir}")
            return
        
        print(f"Parsing {len(json_files)} compliance files for {provider}...")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    self._parse_compliance_file(data, provider)
            except Exception as e:
                print(f"Error parsing {json_file}: {e}")
                continue
    
    def _parse_compliance_file(self, data: Dict, provider: str) -> None:
        """Parse a single compliance JSON file."""
        framework = data.get("Framework", "Unknown")
        framework_name = data.get("Name", "")
        normalized_framework = normalize_framework_name(framework)
        self.frameworks.add(normalized_framework)
        
        # Get framework-provider specific data
        framework_provider_data = self.framework_data[normalized_framework][provider]
        checks = framework_provider_data["checks"]
        requirements = framework_provider_data["requirements"]
        
        requirements_list = data.get("Requirements", [])
        
        for req in requirements_list:
            req_id = req.get("Id", "")
            req_desc = req.get("Description", "")
            check_ids = req.get("Checks", [])
            attributes = req.get("Attributes", [])
            
            # Create requirement
            requirement = ProwlerRequirement(
                requirement_id=f"{framework}-{req_id}",
                description=req_desc,
                framework=framework,
                checks=check_ids,
                attributes=attributes[0] if attributes else {}
            )
            requirements.append(requirement)
            
            # Process checks
            for check_id in check_ids:
                if check_id not in checks:
                    # Extract check information from attributes
                    attr = attributes[0] if attributes else {}
                    checks[check_id] = ProwlerCheck(
                        check_id=check_id,
                        description=attr.get("Description", req_desc),
                        frameworks={framework},
                        requirements=[f"{framework}-{req_id}"],
                        rationale=attr.get("RationaleStatement", ""),
                        remediation=attr.get("RemediationProcedure", ""),
                        audit_procedure=attr.get("AuditProcedure", "")
                    )
                else:
                    # Update existing check
                    checks[check_id].frameworks.add(framework)
                    checks[check_id].requirements.append(f"{framework}-{req_id}")
    
    def get_framework_provider_data(self, framework: str, provider: str) -> Tuple[Dict[str, ProwlerCheck], List[ProwlerRequirement]]:
        """Get checks and requirements for a specific framework-provider combination."""
        normalized_framework = normalize_framework_name(framework)
        if normalized_framework not in self.framework_data:
            return {}, []
        if provider not in self.framework_data[normalized_framework]:
            return {}, []
        
        data = self.framework_data[normalized_framework][provider]
        return data["checks"], data["requirements"]


class TestFileParser:
    """Parse test files to extract test information."""
    
    def __init__(self, provider: str, prowler_root: Path, test_dir: Optional[Path] = None):
        self.provider = provider
        self.prowler_root = prowler_root
        self.test_dir = test_dir
        self.test_info: List[Dict] = []
    
    def parse_test_files(self) -> List[Dict]:
        """Parse test files from test directories."""
        test_info = []
        
        # Determine test directory
        if self.test_dir:
            backend_test_dir = self.test_dir / "providers" / self.provider
        else:
            # Try default location first
            backend_test_dir = self.prowler_root / "tests" / "providers" / self.provider
            # If that doesn't exist, try absolute path
            if not backend_test_dir.exists():
                backend_test_dir = Path("/Users/sameerm/ComplianceSpark/byziplatform/prowler/tests/providers") / self.provider
        
        # Parse backend tests
        if backend_test_dir.exists():
            for test_file in backend_test_dir.rglob("*.py"):
                if test_file.name.endswith("_test.py") or test_file.name.endswith("test.py"):
                    tests = self._parse_python_test_file(test_file)
                    test_info.extend(tests)
        else:
            print(f"Warning: Test directory {backend_test_dir} does not exist")
        
        # Parse UI tests (if they exist)
        ui_test_dir = self.prowler_root / "ui" / "tests" / "providers"
        if ui_test_dir.exists():
            for test_file in ui_test_dir.rglob("*.ts"):
                if "spec" in test_file.name or "test" in test_file.name:
                    tests = self._parse_typescript_test_file(test_file)
                    test_info.extend(tests)
        
        self.test_info = test_info
        return test_info
    
    def _parse_python_test_file(self, test_file: Path) -> List[Dict]:
        """Parse Python test file to extract test functions."""
        tests = []
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract test function definitions
            test_pattern = r'def\s+(test_\w+)\s*\([^)]*\)\s*:'
            matches = re.finditer(test_pattern, content)
            
            for match in matches:
                test_name = match.group(1)
                # Extract docstring if present
                start_pos = match.end()
                docstring_match = re.search(r'"""([^"]*)"""', content[start_pos:start_pos+500])
                docstring = docstring_match.group(1) if docstring_match else ""
                
                tests.append({
                    "test_id": test_name,
                    "test_name": test_name.replace("_", " ").title(),
                    "description": docstring or f"Test for {test_name}",
                    "file_path": str(test_file.relative_to(self.prowler_root)),
                    "language": "python"
                })
        except Exception as e:
            print(f"Error parsing {test_file}: {e}")
        
        return tests
    
    def _parse_typescript_test_file(self, test_file: Path) -> List[Dict]:
        """Parse TypeScript test file to extract test functions."""
        tests = []
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract test/it/describe blocks
            test_pattern = r"(?:test|it|describe)\s*\(['\"]([^'\"]+)['\"]"
            matches = re.finditer(test_pattern, content)
            
            for match in matches:
                test_name = match.group(1)
                tests.append({
                    "test_id": test_name.replace(" ", "_").lower(),
                    "test_name": test_name,
                    "description": test_name,
                    "file_path": str(test_file.relative_to(self.prowler_root)),
                    "language": "typescript"
                })
        except Exception as e:
            print(f"Error parsing {test_file}: {e}")
        
        return tests


class YAMLGenerator:
    """Generate YAML files using LLM."""
    
    def __init__(self, provider: str, framework: str, checks: Dict[str, ProwlerCheck], requirements: List[ProwlerRequirement], test_info: List[Dict] = None, llm_instance=None, batch_size: int = 50):
        self.provider = provider
        self.framework = framework
        self.checks = checks
        self.requirements = requirements
        self.test_info = test_info or []
        self.batch_size = batch_size
        # Use provided LLM instance or get from dependencies
        if llm_instance:
            self.llm = llm_instance
        else:
            settings = get_settings()
            self.llm = get_llm(temperature=0.2, model=settings.LLM_MODEL)
    
    @staticmethod
    def _escape_json_for_prompt(json_str: str) -> str:
        """Escape curly braces in JSON string for use in LangChain ChatPromptTemplate."""
        return json_str.replace("{", "{{").replace("}", "}}")
    
    @staticmethod
    def _parse_yaml_with_fallback(yaml_content: str, fallback_data: List[Dict] = None) -> List[Dict]:
        """
        Parse YAML content with fallback handling for malformed YAML.
        
        Args:
            yaml_content: The YAML string to parse
            fallback_data: Fallback data to use if parsing fails completely
            
        Returns:
            List of parsed dictionaries
        """
        # First, try direct parsing
        try:
            parsed = yaml.safe_load(yaml_content)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                # Sometimes YAML might be wrapped in a dict
                if "controls" in parsed:
                    return parsed["controls"]
                elif len(parsed) == 1 and isinstance(list(parsed.values())[0], list):
                    return list(parsed.values())[0]
        except (yaml.YAMLError, Exception):
            pass
        
        # Try to extract YAML blocks (between --- markers or as list items)
        try:
            # Remove markdown code blocks if present
            content = yaml_content.strip()
            if content.startswith("```"):
                # Extract content between ```yaml and ```
                lines = content.split("\n")
                start_idx = 0
                end_idx = len(lines)
                for i, line in enumerate(lines):
                    if line.strip().startswith("```"):
                        if start_idx == 0:
                            start_idx = i + 1
                        else:
                            end_idx = i
                            break
                content = "\n".join(lines[start_idx:end_idx])
            
            # Try parsing again
            parsed = yaml.safe_load(content)
            if isinstance(parsed, list):
                return parsed
        except (yaml.YAMLError, Exception):
            pass
        
        # Try to extract individual YAML items (for list format)
        try:
            controls = []
            lines = yaml_content.split("\n")
            current_item = {}
            current_key = None
            current_value = []
            
            for line in lines:
                stripped = line.strip()
                # Skip empty lines and comments
                if not stripped or stripped.startswith("#"):
                    continue
                
                # Check if this is a new list item (starts with -)
                if stripped.startswith("- "):
                    # Save previous item if exists
                    if current_item:
                        if current_key and current_value:
                            current_item[current_key] = " ".join(current_value).strip()
                        controls.append(current_item)
                    
                    # Start new item
                    current_item = {}
                    current_key = None
                    current_value = []
                    
                    # Extract key-value from "- key: value" format
                    rest = stripped[2:].strip()  # Remove "- "
                    if ":" in rest:
                        parts = rest.split(":", 1)
                        current_key = parts[0].strip()
                        value_part = parts[1].strip()
                        if value_part:
                            current_value = [value_part]
                        else:
                            current_value = []
                    continue
                
                # Check if this is a key-value line (indented)
                if stripped and ":" in stripped and not stripped.startswith("-"):
                    # Save previous key-value pair
                    if current_key and current_value:
                        current_item[current_key] = " ".join(current_value).strip()
                    
                    # Extract new key-value
                    parts = stripped.split(":", 1)
                    current_key = parts[0].strip()
                    value_part = parts[1].strip() if len(parts) > 1 else ""
                    current_value = [value_part] if value_part else []
                elif current_key and stripped:
                    # Continuation of previous value
                    current_value.append(stripped)
            
            # Save last item
            if current_item:
                if current_key and current_value:
                    current_item[current_key] = " ".join(current_value).strip()
                controls.append(current_item)
            
            if controls:
                return controls
        except Exception as e:
            print(f"Warning: Failed to extract YAML items: {e}")
        
        # Final fallback
        if fallback_data:
            return fallback_data
        return []
    
    def generate_controls(self) -> List[Dict]:
        """Generate controls YAML from checks."""
        print(f"Generating controls for {self.framework} / {self.provider}...")
        
        # First, extract controls directly from checks (base controls)
        base_controls = []
        for check_id, check in self.checks.items():
            # Create control ID from check ID
            control_id = f"{self.provider.upper()}-{check_id.upper().replace('_', '-')}"
            
            # Extract name from description (first sentence or first 100 chars)
            name = check.description.split('.')[0].strip()[:100] if check.description else check_id.replace('_', ' ').title()
            if len(name) > 100:
                name = name[:97] + "..."
            
            base_controls.append({
                "control_id": control_id,
                "name": name,
                "check_id": check_id,
                "description": check.description,
                "rationale": check.rationale,
                "remediation": check.remediation,
                "provider_type": self.provider  # Add provider_type tag
            })
        
        # Group checks by service/domain for better organization
        check_data = base_controls[:200]  # Limit for LLM processing
        
        # Use LLM to enhance and normalize controls
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security compliance expert. Generate control definitions in YAML format matching the NIST CSF and HIPAA control formats.

Each control should have:
- control_id: The control identifier (keep the PROVIDER-CHECK-XXX format provided)
- name: A clear, concise name (extract from description, max 100 chars)
- description: (OPTIONAL) Detailed description if the control needs explanation beyond the name

The format should match:
- NIST format: Simple controls with just control_id and name
- HIPAA format: Controls with control_id, name, and detailed description

For most controls, use the simple format (control_id + name). Only add description for complex controls that need explanation.

IMPORTANT: If any value contains a colon (:) or other special YAML characters, you MUST quote it with double quotes. For example: name: "Policy: establishes reporting lines" instead of name: Policy: establishes reporting lines.

Return ONLY valid YAML array format. Preserve all provided control_ids."""),
            ("user", f"""Generate normalized controls for {self.framework} framework / {self.provider.upper()} provider based on these Prowler checks:

{self._escape_json_for_prompt(json.dumps(check_data, indent=2))}

Generate controls in YAML format. For each check:
1. Keep the control_id as provided
2. Extract a clear name from the description (max 100 chars)
3. Only add description field if the control is complex and needs detailed explanation

Return a YAML array of controls matching the NIST/HIPAA format."""),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({})
        
        # Parse YAML response with improved error handling
        fallback_controls = []
        for check in base_controls[:100]:  # Limit to top 100
            fallback_controls.append({
                "control_id": check["control_id"],
                "name": check["name"]
            })
        
        try:
            controls = self._parse_yaml_with_fallback(response.content, fallback_controls)
            
            if not controls or not isinstance(controls, list):
                print("Warning: LLM response not in expected format, using fallback")
                controls = fallback_controls
            else:
                # Ensure all controls have at least control_id and name
                valid_controls = []
                for control in controls:
                    if not isinstance(control, dict):
                        continue
                    
                    # Fix missing control_id
                    if "control_id" not in control:
                        # Try to find matching check
                        check_id = control.get("check_id", "")
                        if check_id:
                            control["control_id"] = f"{self.provider.upper()}-{check_id.upper().replace('_', '-')}"
                        else:
                            print(f"Warning: Control missing control_id, skipping: {control}")
                            continue
                    
                    # Fix missing name
                    if "name" not in control:
                        control["name"] = control.get("description", "Unnamed Control")[:100]
                    
                    # Clean up name and description (remove colons that might cause issues)
                    if "name" in control:
                        control["name"] = str(control["name"]).replace("\n", " ").strip()[:100]
                    if "description" in control:
                        control["description"] = str(control["description"]).replace("\n", " ").strip()
                    
                    # Ensure provider_type is set
                    if "provider_type" not in control:
                        control["provider_type"] = self.provider
                    
                    valid_controls.append(control)
                
                controls = valid_controls
            
            # Sort by control_id for consistency
            controls.sort(key=lambda x: x.get("control_id", ""))
            
            print(f"Generated {len(controls)} controls")
            return controls
        except Exception as e:
            print(f"Error parsing controls YAML: {e}")
            print(f"Response preview: {response.content[:500]}")
            # Use fallback controls
            controls = []
            for check_id, check in list(self.checks.items())[:100]:
                control_id = f"{self.provider.upper()}-{check_id.upper().replace('_', '-')}"
                name = check.description.split('.')[0].strip()[:100] if check.description else check_id.replace('_', ' ').title()
                controls.append({
                    "control_id": control_id,
                    "name": name,
                    "provider_type": self.provider
                })
            return controls
    
    def generate_requirements(self) -> List[Dict]:
        """Generate requirements YAML from Prowler requirements."""
        print(f"Generating requirements for {self.framework} / {self.provider}...")
        
        # Prepare requirement data
        req_data = []
        for req in self.requirements[:100]:  # Limit to 100
            req_data.append({
                "requirement_id": req.requirement_id,
                "description": req.description,
                "framework": req.framework,
                "checks": req.checks
            })
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security compliance expert. Generate requirement definitions in YAML format.

Each requirement should have:
- requirement_id: The requirement identifier
- description: Detailed description of the requirement, including regulatory intent, scope, and compliance rationale

Return ONLY valid YAML format."""),
            ("user", f"""Generate requirements for {self.framework} framework / {self.provider} provider based on these Prowler requirements:

{self._escape_json_for_prompt(json.dumps(req_data, indent=2))}

Return a YAML array of requirements."""),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({})
        
        try:
            requirements = yaml.safe_load(response.content)
            if not isinstance(requirements, list):
                requirements = []
            return requirements
        except Exception as e:
            print(f"Error parsing requirements YAML: {e}")
            return []
    
    def _get_control_id_from_check(self, check_id: str) -> str:
        """Convert check_id to control_id format."""
        return f"{self.provider.upper()}-{check_id.upper().replace('_', '-')}"
    
    def generate_scenarios(self) -> List[Dict]:
        """Generate risk scenarios YAML."""
        print(f"Generating scenarios for {self.framework} / {self.provider}...")
        
        # Prepare data with control IDs
        check_summaries = []
        for check_id, check in list(self.checks.items())[:50]:
            control_id = self._get_control_id_from_check(check_id)
            check_summaries.append({
                "check_id": check_id,
                "control_id": control_id,
                "description": check.description[:200] if check.description else ""  # Truncate for context
            })
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security risk analyst. Generate risk scenarios in YAML format.

Each scenario should have:
- scenario_id: Format as PROVIDER-RISK-XXX (e.g., AWS-RISK-001)
- name: Brief scenario name
- description: Detailed description of the risk scenario
- category: Risk category
- asset: One of: information_security_operations, asset_management, identity_management, network_security, data_protection, monitoring, compliance, incident_response, configuration_management, vulnerability_management, business_continuity_and_disaster_recovery, operations_security
- trigger: One of: control failure, human error, malicious actor, system failure, natural disaster
- loss_outcomes: List of outcomes (e.g., breach, compliance violation, operational impact, financial loss)
- mitigated_by: List of control_ids (use the control_id from the provided checks, e.g., AWS-CHECK-NAME)

IMPORTANT: Use the exact control_id values provided in the check_summaries for the mitigated_by field.

Generate realistic risk scenarios based on the checks. Return ONLY valid YAML array format."""),
            ("user", f"""Generate risk scenarios for {self.framework} framework / {self.provider.upper()} provider based on these security checks:

{self._escape_json_for_prompt(json.dumps(check_summaries, indent=2))}

Generate 20-30 diverse risk scenarios covering different security domains. 
For each scenario, use the control_id values from the checks above in the mitigated_by field.
Return a YAML array."""),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({})
        
        try:
            scenarios = yaml.safe_load(response.content)
            if not isinstance(scenarios, list):
                scenarios = []
            return scenarios
        except Exception as e:
            print(f"Error parsing scenarios YAML: {e}")
            return []
    
    def generate_risk_controls(self, scenarios: List[Dict], controls: List[Dict]) -> List[Dict]:
        """Generate risk controls YAML (FAIR format)."""
        print(f"Generating risk controls for {self.framework} / {self.provider}...")
        
        # Create control lookup
        control_lookup = {c.get("control_id", ""): c for c in controls}
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security risk analyst. Generate risk controls in FAIR format.

Each risk control should have:
- scenario_id: The scenario identifier
- name: Scenario name
- asset: Asset type
- trigger: Trigger type
- loss_outcomes: List of loss outcomes
- controls: List of control objects with control_id, name, type
- description: Detailed description including attack vectors, business impact, stakeholders, and real-world examples

Return ONLY valid YAML array format."""),
            ("user", f"""Generate risk controls for {self.framework} framework / {self.provider} provider.

Scenarios:
{self._escape_json_for_prompt(json.dumps(scenarios[:30], indent=2))}

Available Controls:
{self._escape_json_for_prompt(json.dumps(list(control_lookup.values())[:50], indent=2))}

For each scenario, map appropriate controls and write a comprehensive description. Return a YAML array."""),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({})
        
        try:
            risk_controls = yaml.safe_load(response.content)
            if not isinstance(risk_controls, list):
                risk_controls = []
            return risk_controls
        except Exception as e:
            print(f"Error parsing risk controls YAML: {e}")
            return []
    
    def generate_test_cases(self, scenarios: List[Dict], controls: List[Dict]) -> List[Dict]:
        """Generate test cases YAML based on scenarios and controls."""
        print(f"Generating test cases for {self.framework} / {self.provider}...")
        
        # Prepare test context
        test_context = ""
        if self.test_info:
            test_context = f"\n\nExisting test files found:\n{self._escape_json_for_prompt(json.dumps(self.test_info[:20], indent=2))}"
        
        # Group scenarios by risk
        scenario_data = []
        for scenario in scenarios[:30]:  # Limit to 30 scenarios
            scenario_id = scenario.get("scenario_id", "")
            scenario_name = scenario.get("name", "")
            mitigated_by = scenario.get("mitigated_by", [])
            
            # Find controls that mitigate this scenario
            related_controls = []
            for control_id in mitigated_by[:5]:  # Limit to 5 controls per scenario
                control = next((c for c in controls if c.get("control_id") == control_id), None)
                if control:
                    related_controls.append({
                        "control_id": control.get("control_id", ""),
                        "name": control.get("name", "")
                    })
            
            scenario_data.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "asset": scenario.get("asset", ""),
                "trigger": scenario.get("trigger", ""),
                "controls": related_controls
            })
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security testing expert. Generate test cases in YAML format matching the CIS test case structure.

Each test case entry should have:
- risk_id: The scenario_id from the risk scenario
- risk_name: The scenario name
- framework: The provider name (uppercase)
- test_cases: List of test cases, each with:
  - test_id: Format as RISK-ID-TEST-XX (e.g., AWS-RISK-001-TEST-01)
  - test_name: Name describing what the test verifies
  - test_type: One of: preventive_control_verification, detective_control_verification, corrective_control_verification
  - objective: Detailed objective describing what the test verifies
  - test_steps: List of numbered test steps (as strings)
  - expected_result: What should happen when the test passes
  - evidence_required: List of evidence types needed
  - success_criteria: List of criteria for test success

Generate test cases for each control that mitigates a risk scenario. Return ONLY valid YAML array format."""),
            ("user", f"""Generate test cases for {self.framework} framework / {self.provider.upper()} provider based on these risk scenarios and controls:

Risk Scenarios:
{self._escape_json_for_prompt(json.dumps(scenario_data, indent=2))}
{test_context}

For each risk scenario, generate test cases for each control that mitigates it. Each control should have at least one test case.
Return a YAML array following the exact format of CIS test cases."""),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({})
        
        try:
            test_cases = yaml.safe_load(response.content)
            if not isinstance(test_cases, list):
                test_cases = []
            return test_cases
        except Exception as e:
            print(f"Error parsing test cases YAML: {e}")
            print(f"Response content: {response.content[:500]}")
            return []


def main():
    parser = argparse.ArgumentParser(description="Generate Prowler risk control YAML files")
    parser.add_argument(
        "--prowler-path",
        type=str,
        required=True,
        help="Path to the Prowler root directory (required)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        help="Specific provider to process (aws, azure, gcp, etc.). If not specified, processes all providers."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory for YAML files (required)"
    )
    parser.add_argument(
        "--compliance-dir",
        type=str,
        default=None,
        help="Path to Prowler compliance directory relative to prowler-path (default: prowler/prowler/compliance)"
    )
    parser.add_argument(
        "--test-dir",
        type=str,
        default=None,
        help="Path to Prowler test directory (default: prowler-path/tests or auto-detected)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of items to process per batch for LLM calls (default: 50)"
    )
    parser.add_argument(
        "--batch-index",
        type=int,
        default=None,
        help="Process only a specific batch index (0-based). Use with --batch-total to process specific batches."
    )
    parser.add_argument(
        "--batch-total",
        type=int,
        default=None,
        help="Total number of batches. Use with --batch-index to process specific batches."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip providers/files that already exist in output directory"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between LLM API calls to avoid rate limiting (default: 1.0)"
    )
    
    args = parser.parse_args()
    
    # Initialize settings (loads from .env)
    try:
        settings = get_settings()
        print(f"✓ Settings loaded from .env")
        print(f"  LLM Model: {settings.LLM_MODEL}")
        print(f"  LLM Provider: {settings.LLM_PROVIDER}")
        print(f"  OpenAI API Key: {'Set' if settings.OPENAI_API_KEY else 'Not set'}")
    except Exception as e:
        print(f"Error loading settings: {e}")
        sys.exit(1)
    
    # Initialize LLM using app dependencies
    try:
        llm_instance = get_llm(temperature=0.2, model=settings.LLM_MODEL)
        print(f"✓ LLM initialized: {settings.LLM_MODEL}")
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        print("Make sure OPENAI_API_KEY is set in .env or environment variables")
        sys.exit(1)
    
    # Setup paths
    prowler_root = Path(args.prowler_path).resolve()
    if not prowler_root.exists():
        print(f"Error: Prowler path does not exist: {prowler_root}")
        sys.exit(1)
    
    # Set compliance directory
    if args.compliance_dir:
        compliance_dir = Path(args.compliance_dir).resolve()
        if not compliance_dir.is_absolute():
            compliance_dir = prowler_root / args.compliance_dir
    else:
        compliance_dir = prowler_root / "prowler" / "prowler" / "compliance"
    
    if not compliance_dir.exists():
        print(f"Error: Compliance directory does not exist: {compliance_dir}")
        sys.exit(1)
    
    # Set test directory
    if args.test_dir:
        test_dir = Path(args.test_dir).resolve()
        if not test_dir.is_absolute():
            test_dir = prowler_root / args.test_dir
    else:
        # Try default location first
        test_dir = prowler_root / "tests"
        # If that doesn't exist, try absolute path
        if not test_dir.exists():
            test_dir = Path("/Users/sameerm/ComplianceSpark/byziplatform/prowler/tests")
    
    # Set output directory
    output_dir = Path(args.output_dir).resolve()
    if not output_dir.is_absolute():
        # If relative, make it relative to current working directory
        output_dir = Path.cwd() / args.output_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine providers to process
    if args.provider:
        providers = [args.provider]
    else:
        # Get all providers from compliance directory
        providers = [d.name for d in compliance_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]
    
    # Filter providers by batch if batch processing is requested
    if args.batch_index is not None and args.batch_total is not None:
        total_providers = len(providers)
        batch_size = (total_providers + args.batch_total - 1) // args.batch_total
        start_idx = args.batch_index * batch_size
        end_idx = min(start_idx + batch_size, total_providers)
        providers = providers[start_idx:end_idx]
        print(f"Batch {args.batch_index + 1}/{args.batch_total}: Processing providers {start_idx + 1}-{end_idx} of {total_providers}")
        print(f"Providers in this batch: {providers}")
    else:
        print(f"Processing {len(providers)} providers: {providers}")
    
    # Parse all compliance files first to organize by framework
    print(f"\n{'='*60}")
    print("Parsing compliance files and organizing by framework...")
    print(f"{'='*60}\n")
    
    parser = ProwlerComplianceParser(compliance_dir)
    for provider in providers:
        parser.parse_provider(provider)
    
    # Get all framework-provider combinations
    framework_provider_combos = []
    for framework in sorted(parser.framework_data.keys()):
        for provider in sorted(parser.framework_data[framework].keys()):
            if args.provider and provider != args.provider:
                continue
            framework_provider_combos.append((framework, provider))
    
    print(f"Found {len(framework_provider_combos)} framework-provider combinations:")
    for framework, provider in framework_provider_combos:
        checks_count = len(parser.framework_data[framework][provider]["checks"])
        reqs_count = len(parser.framework_data[framework][provider]["requirements"])
        print(f"  - {framework} / {provider}: {checks_count} checks, {reqs_count} requirements")
    
    # Track overall progress
    total_combos = len(framework_provider_combos)
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    for combo_idx, (framework, provider) in enumerate(framework_provider_combos, 1):
        print(f"\n{'='*60}")
        print(f"[{combo_idx}/{total_combos}] Processing: {framework} / {provider}")
        print(f"{'='*60}\n")
        
        # Create framework output directory
        framework_output_dir = output_dir / framework
        framework_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get framework-provider specific data
        checks, requirements = parser.get_framework_provider_data(framework, provider)
        
        if not checks:
            print(f"No checks found for {framework} / {provider}, skipping...")
            skipped_count += 1
            continue
        
        # File names with framework and provider
        controls_file = framework_output_dir / f"controls_{framework}_{provider}.yaml"
        requirements_file = framework_output_dir / f"requirements_{framework}_{provider}.yaml"
        scenarios_file = framework_output_dir / f"scenarios_{framework}_{provider}.yaml"
        risk_controls_file = framework_output_dir / f"{framework}_{provider}_risk_controls.yaml"
        test_cases_file = framework_output_dir / f"{framework}_{provider}_test_cases.yaml"
        
        # Check if we should skip this combination (resume mode)
        if args.resume:
            required_files = [controls_file, requirements_file, scenarios_file, risk_controls_file, test_cases_file]
            existing_files = [f for f in required_files if f.exists()]
            if len(existing_files) == len(required_files):
                print(f"✓ All files already exist for {framework} / {provider}, skipping...")
                skipped_count += 1
                continue
            elif existing_files:
                print(f"⚠ Some files exist for {framework} / {provider}: {[f.name for f in existing_files]}")
                print(f"  Will regenerate missing files...")
        
        try:
            print(f"Found {len(checks)} unique checks and {len(requirements)} requirements")
            
            # Parse test files
            test_parser = TestFileParser(provider, prowler_root, test_dir)
            test_info = test_parser.parse_test_files()
            print(f"Found {len(test_info)} test functions in test files")
            
            # Generate YAML files with batch size
            generator = YAMLGenerator(
                provider,
                framework,
                checks,
                requirements,
                test_info,
                llm_instance=llm_instance,
                batch_size=args.batch_size
            )
            
            # Initialize variables for this combination
            controls = None
            scenarios = None
            
            # Generate controls
            if not args.resume or not controls_file.exists():
                print(f"\n--- Generating controls ---")
                controls = generator.generate_controls()
                time.sleep(args.delay)  # Rate limiting
                
                if not controls:
                    print(f"Warning: No controls generated for {framework} / {provider}")
                else:
                    with open(controls_file, 'w') as f:
                        yaml.dump(controls, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    print(f"✓ Wrote {len(controls)} controls to {controls_file}")
                    
                    # Validate controls format
                    valid_controls = sum(1 for c in controls if "control_id" in c and "name" in c)
                    if valid_controls < len(controls):
                        print(f"⚠ Warning: {len(controls) - valid_controls} controls missing required fields")
                    else:
                        print(f"✓ All {valid_controls} controls have required fields")
            else:
                print(f"⏭ Skipping controls (file exists)")
                # Load existing controls for use in risk_controls and test_cases
                with open(controls_file, 'r') as f:
                    controls = yaml.safe_load(f) or []
            
            # Generate requirements
            if not args.resume or not requirements_file.exists():
                print(f"\n--- Generating requirements ---")
                reqs = generator.generate_requirements()
                time.sleep(args.delay)  # Rate limiting
                
                with open(requirements_file, 'w') as f:
                    yaml.dump({
                        "framework": framework,
                        "framework_version": "1.0",
                        "provider_type": provider,
                        "requirements": reqs
                    }, f, default_flow_style=False, sort_keys=False)
                print(f"✓ Wrote {len(reqs)} requirements to {requirements_file}")
            else:
                print(f"⏭ Skipping requirements (file exists)")
            
            # Generate scenarios
            if not args.resume or not scenarios_file.exists():
                print(f"\n--- Generating scenarios ---")
                scenarios = generator.generate_scenarios()
                time.sleep(args.delay)  # Rate limiting
                
                with open(scenarios_file, 'w') as f:
                    yaml.dump(scenarios, f, default_flow_style=False, sort_keys=False)
                print(f"✓ Wrote {len(scenarios)} scenarios to {scenarios_file}")
            else:
                print(f"⏭ Skipping scenarios (file exists)")
                # Load existing scenarios for use in risk_controls and test_cases
                with open(scenarios_file, 'r') as f:
                    scenarios = yaml.safe_load(f) or []
            
            # Generate risk controls (requires scenarios and controls)
            if not args.resume or not risk_controls_file.exists():
                print(f"\n--- Generating risk controls ---")
                # Ensure we have scenarios and controls loaded
                if scenarios is None:
                    with open(scenarios_file, 'r') as f:
                        scenarios = yaml.safe_load(f) or []
                if controls is None:
                    with open(controls_file, 'r') as f:
                        controls = yaml.safe_load(f) or []
                
                risk_controls = generator.generate_risk_controls(scenarios, controls)
                time.sleep(args.delay)  # Rate limiting
                
                with open(risk_controls_file, 'w') as f:
                    yaml.dump(risk_controls, f, default_flow_style=False, sort_keys=False)
                print(f"✓ Wrote {len(risk_controls)} risk controls to {risk_controls_file}")
            else:
                print(f"⏭ Skipping risk controls (file exists)")
            
            # Generate test cases (requires scenarios and controls)
            if not args.resume or not test_cases_file.exists():
                print(f"\n--- Generating test cases ---")
                # Ensure we have scenarios and controls loaded
                if scenarios is None:
                    with open(scenarios_file, 'r') as f:
                        scenarios = yaml.safe_load(f) or []
                if controls is None:
                    with open(controls_file, 'r') as f:
                        controls = yaml.safe_load(f) or []
                
                test_cases = generator.generate_test_cases(scenarios, controls)
                time.sleep(args.delay)  # Rate limiting
                
                with open(test_cases_file, 'w') as f:
                    yaml.dump(test_cases, f, default_flow_style=False, sort_keys=False)
                print(f"✓ Wrote {len(test_cases)} test case entries to {test_cases_file}")
            else:
                print(f"⏭ Skipping test cases (file exists)")
            
            processed_count += 1
            print(f"\n✓ Completed processing {framework} / {provider} ({processed_count}/{total_combos} processed)")
            
        except Exception as e:
            error_count += 1
            print(f"\n✗ Error processing {framework} / {provider}: {e}")
            import traceback
            traceback.print_exc()
            print(f"\nContinuing with next combination...\n")
    
    print(f"\n{'='*60}")
    print(f"Batch processing complete!")
    print(f"  Processed: {processed_count}/{total_combos}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"  Output directory: {output_dir}")
    print(f"{'='*60}")
    
    if args.batch_index is not None and args.batch_total is not None:
        print(f"\nTo process other batches, run:")
        for i in range(args.batch_total):
            if i != args.batch_index:
                print(f"  --batch-index {i} --batch-total {args.batch_total}")


if __name__ == "__main__":
    main()
