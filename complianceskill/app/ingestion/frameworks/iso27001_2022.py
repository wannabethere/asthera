"""
ISO/IEC 27001:2022 adapter.

Source files:
  - controls_iso27001_2022.yaml          → controls
  - requirements_iso27001_2022.yaml      → requirements
  - iso27001_2022_risk_controls.yaml     → risks
  - scenarios_iso27001_2022.yaml         → scenarios with mitigated_by controls
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

# ISO 27001:2022 Annex A themes
THEME_MAP = {
    "5": "Organizational Controls",
    "6": "People Controls",
    "7": "Physical Controls",
    "8": "Technological Controls",
}


class ISO27001Adapter(BaseFrameworkAdapter):
    """
    Adapter for ISO/IEC 27001:2022.
    """

    FRAMEWORK_ID = "iso27001"

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)

    @property
    def framework_id(self) -> str:
        return self.FRAMEWORK_ID

    def load(self) -> FrameworkIngestionBundle:
        bundle = FrameworkIngestionBundle(
            framework=NormalizedFramework(
                id=self.FRAMEWORK_ID,
                name="ISO/IEC 27001",
                version="2022",
                description=(
                    "ISO/IEC 27001 specifies the requirements for establishing, implementing, "
                    "maintaining, and continually improving an information security management "
                    "system (ISMS)."
                ),
                source_url="https://www.iso.org/standard/82875.html",
            )
        )

        bundle.controls = self._load_controls()
        bundle.requirements = self._load_requirements()
        bundle.risks = self._load_risks()
        bundle.scenarios = self._load_scenarios()

        logger.info(
            f"ISO 27001:2022 adapter loaded: {len(bundle.controls)} controls, "
            f"{len(bundle.requirements)} requirements, "
            f"{len(bundle.risks)} risks, {len(bundle.scenarios)} scenarios"
        )
        return bundle

    def _load_controls(self) -> List[NormalizedControl]:
        path = self._find_file("controls_iso27001_2022")
        if not path:
            logger.warning("ISO 27001:2022 controls file not found.")
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

            # Derive theme from Annex A section number (e.g., "AST-65" -> "5" -> "Organizational Controls")
            # Control codes like "AST-65" don't directly map, so use domain field if available
            domain = self.clean_text(item.get("domain"))
            if not domain:
                # Try to infer from control_id if it follows pattern
                # For ISO 27001:2022, controls are numbered A.5.1, A.6.1, etc.
                # But the YAML uses codes like AST-65, so we rely on domain field
                pass

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
                    "annex_section": item.get("annex_section"),
                    "theme": item.get("theme"),
                },
            ))
        return controls

    def _load_requirements(self) -> List[NormalizedRequirement]:
        path = self._find_file("requirements_iso27001_2022")
        if not path:
            logger.warning("ISO 27001:2022 requirements file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, dict):
            return []

        iso_version = raw.get("iso_version", "2022")
        requirements = []
        for item in (raw.get("requirements") or []):
            if not isinstance(item, dict):
                continue
            req_code = item.get("requirement_id")
            if not req_code:
                continue
            requirements.append(NormalizedRequirement(
                requirement_code=req_code,
                name=self.clean_text(item.get("name")),
                description=self.clean_text(item.get("description")),
                metadata={"iso_version": iso_version},
            ))
        return requirements

    def _load_risks(self) -> List[NormalizedRisk]:
        path = self._find_file("iso27001_2022_risk_controls")
        if not path:
            logger.warning("ISO 27001:2022 risk_controls file not found.")
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
        path = self._find_file("scenarios_iso27001_2022")
        if not path:
            logger.warning("ISO 27001:2022 scenarios file not found.")
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
