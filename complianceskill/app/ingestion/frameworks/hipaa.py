"""
HIPAA adapter.

Source files:
  - controls_hipaa.yaml          → controls (73 items, control_id + description)
  - hipaa_risk_controls.yaml     → risks (67 items, scenario_id pattern)
  - requirements_hipaa.yaml      → requirements (dict with nested requirements list)
  - scenarios_hipaa.yaml         → scenarios (67 items)

HIPAA-specific notes:
  - Requirements use CFR citation codes e.g. "164.308(a)(1)(i)"
  - Controls don't have explicit domain/type fields — inferred from control_id prefix
  - Required vs Addressable distinction tracked in compliance_type field
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import yaml

from app.ingestion.base import (
    BaseFrameworkAdapter,
    FrameworkIngestionBundle,
    NormalizedFramework,
    NormalizedControl,
    NormalizedRequirement,
    NormalizedRisk,
    NormalizedScenario,
)

logger = logging.getLogger(__name__)

# Domain prefix map derived from HIPAA control_id conventions in the YAMLs
CONTROL_DOMAIN_MAP = {
    "AST": "Asset Management",
    "AM":  "Access Management",
    "CM":  "Configuration Management",
    "IR":  "Incident Response",
    "RA":  "Risk Assessment",
    "SC":  "System and Communications Protection",
    "AU":  "Audit and Accountability",
    "CP":  "Contingency Planning",
    "PE":  "Physical and Environmental Protection",
    "PL":  "Planning",
    "PS":  "Personnel Security",
    "SA":  "System and Services Acquisition",
    "SI":  "System and Information Integrity",
    "AT":  "Awareness and Training",
}

# HIPAA safeguard category from CFR section prefix
REQUIREMENT_DOMAIN_MAP = {
    "164.308": "Administrative Safeguards",
    "164.310": "Physical Safeguards",
    "164.312": "Technical Safeguards",
    "164.314": "Organizational Requirements",
    "164.316": "Documentation Requirements",
}


class HIPAAAdapter(BaseFrameworkAdapter):
    """
    Adapter for HIPAA Security Rule (45 CFR Part 164).
    """

    FRAMEWORK_ID = "hipaa"

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)

    @property
    def framework_id(self) -> str:
        return self.FRAMEWORK_ID

    def load(self) -> FrameworkIngestionBundle:
        bundle = FrameworkIngestionBundle(
            framework=NormalizedFramework(
                id=self.FRAMEWORK_ID,
                name="HIPAA Security Rule",
                version="45 CFR Part 164",
                description=(
                    "The HIPAA Security Rule establishes national standards to protect "
                    "individuals' electronic personal health information (ePHI) that is "
                    "created, received, used, or maintained by a covered entity."
                ),
                source_url="https://www.hhs.gov/hipaa/for-professionals/security/index.html",
            )
        )

        bundle.controls = self._load_controls()
        bundle.requirements = self._load_requirements()
        bundle.risks = self._load_risks()
        bundle.scenarios = self._load_scenarios()

        logger.info(
            f"HIPAA adapter loaded: {len(bundle.controls)} controls, "
            f"{len(bundle.requirements)} requirements, "
            f"{len(bundle.risks)} risks, {len(bundle.scenarios)} scenarios"
        )
        return bundle

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _load_controls(self) -> List[NormalizedControl]:
        path = self._find_file("controls_hipaa")
        if not path:
            logger.warning("HIPAA controls file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, list):
            return []

        controls = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            control_code = item.get("control_id")
            name = item.get("name")
            if not control_code or not name:
                continue

            # Infer domain from control_id prefix
            prefix = control_code.split("-")[0] if "-" in control_code else ""
            domain = CONTROL_DOMAIN_MAP.get(prefix)

            controls.append(NormalizedControl(
                control_code=control_code,
                name=self.clean_text(name),
                description=self.clean_text(item.get("description")),
                domain=domain,
                control_type=None,  # HIPAA controls don't specify type explicitly
                metadata={"source_control_id": control_code},
            ))
        return controls

    def _load_requirements(self) -> List[NormalizedRequirement]:
        path = self._find_file("requirements_hipaa")
        if not path:
            logger.warning("HIPAA requirements file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, dict):
            return []

        requirements_raw = raw.get("requirements") or []
        requirements = []
        for item in requirements_raw:
            if not isinstance(item, dict):
                continue
            req_code = item.get("requirement_id")
            if not req_code:
                continue

            # Infer domain from CFR section prefix
            domain = self._infer_requirement_domain(req_code)
            # Infer compliance_type from description if mentioned
            description = item.get("description") or ""
            compliance_type = self._infer_compliance_type(description)

            requirements.append(NormalizedRequirement(
                requirement_code=req_code,
                name=self._build_requirement_name(req_code),
                description=self.clean_text(description),
                domain=domain,
                compliance_type=compliance_type,
                metadata={"framework_version": raw.get("framework_version")},
            ))
        return requirements

    def _load_risks(self) -> List[NormalizedRisk]:
        path = self._find_file("hipaa_risk_controls")
        if not path:
            logger.warning("HIPAA risk_controls file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, list):
            return []

        risks = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            risk_code = item.get("scenario_id")
            name = item.get("name")
            if not risk_code or not name:
                continue

            raw_controls = item.get("controls") or []
            control_codes = [c for c in raw_controls if isinstance(c, str)]

            risks.append(NormalizedRisk(
                risk_code=risk_code,
                name=self.clean_text(name),
                description=self.clean_text(item.get("description")),
                asset=self.clean_text(item.get("asset")),
                trigger=self.clean_text(item.get("trigger")),
                loss_outcomes=[str(o) for o in (item.get("loss_outcomes") or [])],
                mitigating_control_codes=control_codes,
                metadata={},
            ))
        return risks

    def _load_scenarios(self) -> List[NormalizedScenario]:
        path = self._find_file("scenarios_hipaa")
        if not path:
            logger.warning("HIPAA scenarios file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, list):
            return []

        scenarios = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            code = item.get("scenario_id")
            name = item.get("name")
            if not code or not name:
                continue
            scenarios.append(NormalizedScenario(
                scenario_code=code,
                name=self.clean_text(name),
                description=self.clean_text(item.get("description")),
                asset=self.clean_text(item.get("asset")),
                trigger=self.clean_text(item.get("trigger")),
                loss_outcomes=[str(o) for o in (item.get("loss_outcomes") or [])],
                metadata={},
            ))
        return scenarios

    # ------------------------------------------------------------------
    # HIPAA-specific helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_requirement_domain(req_code: str) -> Optional[str]:
        for prefix, domain in REQUIREMENT_DOMAIN_MAP.items():
            if req_code.startswith(prefix):
                return domain
        return None

    @staticmethod
    def _infer_compliance_type(description: str) -> Optional[str]:
        desc_lower = description.lower()
        if "addressable" in desc_lower:
            return "addressable"
        if "required" in desc_lower:
            return "required"
        return None

    @staticmethod
    def _build_requirement_name(req_code: str) -> str:
        """Produce a short human-readable name from the CFR code."""
        return f"HIPAA § {req_code}"

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def _find_file(self, keyword: str) -> Optional[Path]:
        for p in sorted(self._dir.glob("*.yaml")):
            if keyword.lower() in p.name.lower():
                return p
        return None

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
