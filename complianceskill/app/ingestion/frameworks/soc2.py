"""
SOC 2 (Trust Service Criteria) adapter.

Source files:
  - controls_soc2.yaml          → controls
  - requirements_soc2.yaml     → requirements
  - soc2_risk_controls.yaml    → risks
  - scenarios_soc2.yaml        → scenarios with mitigated_by controls
"""

import logging
from pathlib import Path
from typing import List, Optional, Any

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

# SOC2 TSC domain labels
TSC_DOMAIN_MAP = {
    "CC": "Common Criteria - Security",
    "A":  "Availability",
    "C":  "Confidentiality",
    "PI": "Processing Integrity",
    "P":  "Privacy",
}


class SOC2Adapter(BaseFrameworkAdapter):
    """
    Adapter for SOC 2 (Trust Service Criteria).
    """

    FRAMEWORK_ID = "soc2"

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)

    @property
    def framework_id(self) -> str:
        return self.FRAMEWORK_ID

    def load(self) -> FrameworkIngestionBundle:
        bundle = FrameworkIngestionBundle(
            framework=NormalizedFramework(
                id=self.FRAMEWORK_ID,
                name="SOC 2",
                version="2017",
                description=(
                    "SOC 2 defines criteria for managing customer data based on five "
                    "Trust Service Criteria: security, availability, processing integrity, "
                    "confidentiality, and privacy."
                ),
                source_url="https://www.aicpa.org/resources/article/system-and-organization-controls-soc-suite-of-services",
            )
        )

        bundle.controls = self._load_controls()
        bundle.requirements = self._load_requirements()
        bundle.risks = self._load_risks()
        bundle.scenarios = self._load_scenarios()

        logger.info(
            f"SOC2 adapter loaded: {len(bundle.controls)} controls, "
            f"{len(bundle.requirements)} requirements, "
            f"{len(bundle.risks)} risks, {len(bundle.scenarios)} scenarios"
        )
        return bundle

    def _load_controls(self) -> List[NormalizedControl]:
        path = self._find_file("controls_soc2")
        if not path:
            logger.warning("SOC2 controls file not found.")
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

            # Infer domain from control_id prefix (e.g., "CC6.1" -> "CC")
            tsc_cat = control_code[:2] if len(control_code) >= 2 else ""
            domain = TSC_DOMAIN_MAP.get(tsc_cat, tsc_cat) if tsc_cat in TSC_DOMAIN_MAP else None

            # Parse related_frameworks if present
            cross_refs = self.parse_cross_framework_refs(item.get("related_frameworks", {}))

            controls.append(NormalizedControl(
                control_code=control_code,
                name=self.clean_text(name),
                description=self.clean_text(item.get("description")),
                domain=domain,
                control_type=self.clean_text(item.get("type")),
                cross_framework_refs=cross_refs,
                metadata={
                    "tsc_category": tsc_cat,
                },
            ))
        return controls

    def _load_requirements(self) -> List[NormalizedRequirement]:
        path = self._find_file("requirements_soc2")
        if not path:
            logger.warning("SOC2 requirements file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, dict):
            return []

        requirements = []
        for item in (raw.get("requirements") or []):
            if not isinstance(item, dict):
                continue
            req_code = item.get("requirement_id")
            if not req_code:
                continue

            # Infer domain from requirement code prefix
            tsc_cat = req_code[:2] if len(req_code) >= 2 else ""
            domain = TSC_DOMAIN_MAP.get(tsc_cat) if tsc_cat in TSC_DOMAIN_MAP else None

            requirements.append(NormalizedRequirement(
                requirement_code=req_code,
                name=self.clean_text(item.get("name")),
                description=self.clean_text(item.get("description")),
                domain=domain,
                metadata={},
            ))
        return requirements

    def _load_risks(self) -> List[NormalizedRisk]:
        path = self._find_file("soc2_risk_controls")
        if not path:
            logger.warning("SOC2 risk_controls file not found.")
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

            # Controls list may be empty in risk_controls file
            # The actual mappings are in scenarios file
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
        path = self._find_file("scenarios_soc2")
        if not path:
            logger.warning("SOC2 scenarios file not found.")
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

            # Extract control codes from mitigated_by field
            mitigated_by = item.get("mitigated_by") or []
            control_codes = [str(c) for c in mitigated_by if isinstance(c, (str, int))]

            scenarios.append(NormalizedScenario(
                scenario_code=code,
                name=self.clean_text(name),
                description=self.clean_text(item.get("description")),
                asset=self.clean_text(item.get("asset")),
                trigger=self.clean_text(item.get("trigger")),
                loss_outcomes=[str(o) for o in (item.get("loss_outcomes") or [])],
                relevant_control_codes=control_codes,
                metadata={},
            ))
        return scenarios

    def _find_file(self, keyword: str) -> Optional[Path]:
        """Find the first YAML file in data_dir whose name contains keyword."""
        for p in sorted(self._dir.glob("*.yaml")):
            if keyword.lower() in p.name.lower():
                return p
        return None

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
