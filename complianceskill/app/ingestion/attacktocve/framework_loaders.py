"""
Framework Loaders
=================
Loaders for all framework file types: scenarios, controls, requirements, risks, test_cases.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from .framework_helper import get_framework_path, find_framework_yaml, get_all_framework_files

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class FrameworkControl(BaseModel):
    """Control definition from controls_*.yaml"""
    control_id: str
    name: str
    description: str = Field(default="")
    domain: Optional[str] = None
    type: Optional[str] = None
    framework_requirement: Optional[str] = None
    framework_mappings: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    evidence_status: Optional[str] = None
    measured_by: List[str] = Field(default_factory=list)
    
    @property
    def full_text(self) -> str:
        """Concatenated text for embedding / LLM context."""
        parts = [f"Control: {self.control_id} – {self.name}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.domain:
            parts.append(f"Domain: {self.domain}")
        if self.type:
            parts.append(f"Type: {self.type}")
        return "\n".join(parts)


class FrameworkRequirement(BaseModel):
    """Requirement definition from requirements_*.yaml"""
    requirement_id: str
    description: str = Field(default="")
    framework: Optional[str] = None
    framework_version: Optional[str] = None
    
    @property
    def full_text(self) -> str:
        """Concatenated text for embedding / LLM context."""
        parts = [f"Requirement: {self.requirement_id}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        return "\n".join(parts)


class FrameworkRisk(BaseModel):
    """Risk definition (similar to scenario but may have different structure)"""
    risk_id: Optional[str] = None
    scenario_id: Optional[str] = None
    name: str
    description: str = Field(default="")
    asset: Optional[str] = None
    trigger: Optional[str] = None
    loss_outcomes: List[str] = Field(default_factory=list)
    mitigated_by: List[str] = Field(default_factory=list)
    controls: List[str] = Field(default_factory=list)
    
    @property
    def full_text(self) -> str:
        """Concatenated text for embedding / LLM context."""
        parts = [f"Risk: {self.risk_id or self.scenario_id} – {self.name}"]
        if self.asset:
            parts.append(f"Asset: {self.asset}")
        if self.trigger:
            parts.append(f"Trigger: {self.trigger}")
        if self.loss_outcomes:
            parts.append(f"Loss outcomes: {', '.join(self.loss_outcomes)}")
        if self.description:
            parts.append(f"Description: {self.description}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_framework_controls(framework: str, yaml_path: Optional[Path] = None) -> List[FrameworkControl]:
    """
    Load controls from controls_*.yaml file.
    
    Args:
        framework: Framework identifier
        yaml_path: Optional path to controls YAML (auto-discovered if not provided)
        
    Returns:
        List of FrameworkControl objects
    """
    if yaml_path is None:
        yaml_path = find_framework_yaml(framework, file_type="controls")
        if not yaml_path:
            logger.debug(f"No controls file found for {framework}")
            return []
    
    if not yaml_path.exists():
        logger.warning(f"Controls file not found: {yaml_path}")
        return []
    
    try:
        raw = yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        
        if not isinstance(data, list):
            logger.warning(f"Expected YAML list in {yaml_path}, got {type(data)}")
            return []
        
        controls = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                # Handle both direct control objects and nested structures
                if "control_id" in item:
                    control = FrameworkControl(**item)
                    controls.append(control)
            except Exception as exc:
                cid = item.get("control_id", "?")
                logger.warning(f"Skipping malformed control {cid}: {exc}")
        
        logger.info(f"Loaded {len(controls)} controls from {yaml_path.name}")
        return controls
    except Exception as e:
        logger.error(f"Failed to load controls from {yaml_path}: {e}")
        return []


def load_framework_requirements(framework: str, yaml_path: Optional[Path] = None) -> List[FrameworkRequirement]:
    """
    Load requirements from requirements_*.yaml file.
    
    Args:
        framework: Framework identifier
        yaml_path: Optional path to requirements YAML (auto-discovered if not provided)
        
    Returns:
        List of FrameworkRequirement objects
    """
    if yaml_path is None:
        yaml_path = find_framework_yaml(framework, file_type="requirements")
        if not yaml_path:
            logger.debug(f"No requirements file found for {framework}")
            return []
    
    if not yaml_path.exists():
        logger.warning(f"Requirements file not found: {yaml_path}")
        return []
    
    try:
        raw = yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        
        # Handle both list format and dict with requirements key
        if isinstance(data, dict):
            if "requirements" in data:
                data = data["requirements"]
            else:
                logger.warning(f"Unexpected requirements file structure in {yaml_path}")
                return []
        
        if not isinstance(data, list):
            logger.warning(f"Expected YAML list in {yaml_path}, got {type(data)}")
            return []
        
        requirements = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                if "requirement_id" in item:
                    requirement = FrameworkRequirement(**item)
                    requirements.append(requirement)
            except Exception as exc:
                rid = item.get("requirement_id", "?")
                logger.warning(f"Skipping malformed requirement {rid}: {exc}")
        
        logger.info(f"Loaded {len(requirements)} requirements from {yaml_path.name}")
        return requirements
    except Exception as e:
        logger.error(f"Failed to load requirements from {yaml_path}: {e}")
        return []


def load_framework_risks(framework: str, yaml_path: Optional[Path] = None) -> List[FrameworkRisk]:
    """
    Load risks from risk_controls or scenarios file.
    
    Args:
        framework: Framework identifier
        yaml_path: Optional path to risks YAML (auto-discovered if not provided)
        
    Returns:
        List of FrameworkRisk objects
    """
    if yaml_path is None:
        # Try risk_controls first, then scenarios
        yaml_path = find_framework_yaml(framework, file_type="risk_controls")
        if not yaml_path:
            yaml_path = find_framework_yaml(framework, file_type="scenarios")
        if not yaml_path:
            logger.debug(f"No risks/scenarios file found for {framework}")
            return []
    
    if not yaml_path.exists():
        logger.warning(f"Risks file not found: {yaml_path}")
        return []
    
    try:
        raw = yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        
        if not isinstance(data, list):
            logger.warning(f"Expected YAML list in {yaml_path}, got {type(data)}")
            return []
        
        risks = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                # Handle both scenario_id and risk_id
                if "scenario_id" in item or "risk_id" in item:
                    # Normalize to FrameworkRisk format
                    risk_data = {
                        "risk_id": item.get("risk_id") or item.get("scenario_id"),
                        "scenario_id": item.get("scenario_id") or item.get("risk_id"),
                        "name": item.get("name", ""),
                        "description": item.get("description", ""),
                        "asset": item.get("asset"),
                        "trigger": item.get("trigger"),
                        "loss_outcomes": item.get("loss_outcomes", []),
                        "mitigated_by": item.get("mitigated_by", []),
                        "controls": item.get("controls", []),
                    }
                    risk = FrameworkRisk(**risk_data)
                    risks.append(risk)
            except Exception as exc:
                rid = item.get("risk_id") or item.get("scenario_id", "?")
                logger.warning(f"Skipping malformed risk {rid}: {exc}")
        
        logger.info(f"Loaded {len(risks)} risks from {yaml_path.name}")
        return risks
    except Exception as e:
        logger.error(f"Failed to load risks from {yaml_path}: {e}")
        return []


def load_all_framework_data(framework: str) -> Dict[str, Any]:
    """
    Load all available data for a framework.
    
    Args:
        framework: Framework identifier
        
    Returns:
        Dict with keys: scenarios, controls, requirements, risks, test_cases
    """
    from .control_loader import load_cis_scenarios
    
    result = {
        "scenarios": [],
        "controls": [],
        "requirements": [],
        "risks": [],
        "test_cases": [],
    }
    
    # Load scenarios (prefer scenarios_*.yaml, fallback to *_risk_controls.yaml)
    scenario_path = find_framework_yaml(framework, file_type="scenarios")
    if not scenario_path:
        scenario_path = find_framework_yaml(framework, file_type="risk_controls")
    
    if scenario_path:
        try:
            result["scenarios"] = load_cis_scenarios(scenario_path)
            logger.info(f"Loaded {len(result['scenarios'])} scenarios for {framework}")
        except Exception as e:
            logger.warning(f"Failed to load scenarios for {framework}: {e}")
    
    # Load controls
    result["controls"] = load_framework_controls(framework)
    
    # Load requirements
    result["requirements"] = load_framework_requirements(framework)
    
    # Load risks (from risk_controls file if different from scenarios)
    risk_path = find_framework_yaml(framework, file_type="risk_controls")
    if risk_path and risk_path != scenario_path:
        result["risks"] = load_framework_risks(framework, risk_path)
    
    return result
