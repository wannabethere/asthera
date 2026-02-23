"""
NIST Cybersecurity Framework 2.0 adapter.

Source files:
  - controls_nist_csf_2_0.yaml          → controls
  - nist_csf_2_0_risk_controls.yaml    → risks
  - nist_csf_2_0_test_cases.yaml       → test cases grouped by risk
  - scenarios_nist_csf_2_0.yaml        → scenarios
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
    NormalizedTestCase,
    NormalizedScenario,
)

logger = logging.getLogger(__name__)

# NIST CSF 2.0 Functions
FUNCTION_MAP = {
    "GV": "GOVERN",
    "ID": "IDENTIFY",
    "PR": "PROTECT",
    "DE": "DETECT",
    "RS": "RESPOND",
    "RC": "RECOVER",
}


class NISTCSFAdapter(BaseFrameworkAdapter):
    """
    Adapter for NIST Cybersecurity Framework 2.0.
    """

    FRAMEWORK_ID = "nist_csf_2_0"

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)

    @property
    def framework_id(self) -> str:
        return self.FRAMEWORK_ID

    def load(self) -> FrameworkIngestionBundle:
        bundle = FrameworkIngestionBundle(
            framework=NormalizedFramework(
                id=self.FRAMEWORK_ID,
                name="NIST Cybersecurity Framework",
                version="2.0",
                description=(
                    "NIST CSF 2.0 provides a taxonomy of high-level cybersecurity outcomes "
                    "that can be used by any organization to better understand, assess, "
                    "prioritize, and communicate cybersecurity risks."
                ),
                source_url="https://www.nist.gov/cyberframework",
            )
        )

        bundle.controls = self._load_controls()
        bundle.risks = self._load_risks()
        bundle.test_cases = self._load_test_cases()
        bundle.scenarios = self._load_scenarios()

        logger.info(
            f"NIST CSF 2.0 adapter loaded: {len(bundle.controls)} controls, "
            f"{len(bundle.risks)} risks, {len(bundle.test_cases)} test cases, "
            f"{len(bundle.scenarios)} scenarios"
        )
        return bundle

    def _load_controls(self) -> List[NormalizedControl]:
        path = self._find_file("controls_nist_csf_2_0")
        if not path:
            logger.warning("NIST CSF 2.0 controls file not found.")
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

            # Derive function from code prefix e.g. "GV.OC-01" → "GOVERN"
            prefix = control_code.split(".")[0] if "." in control_code else ""
            domain = FUNCTION_MAP.get(prefix, prefix)

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
                    "function": FUNCTION_MAP.get(prefix, prefix),
                    "category": item.get("category"),
                },
            ))
        return controls

    def _load_risks(self) -> List[NormalizedRisk]:
        path = self._find_file("nist_csf_2_0_risk_controls")
        if not path:
            logger.warning("NIST CSF 2.0 risk_controls file not found.")
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

    def _load_test_cases(self) -> List[NormalizedTestCase]:
        path = self._find_file("nist_csf_2_0_test_cases")
        if not path:
            logger.warning("NIST CSF 2.0 test_cases file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, list):
            return []

        test_cases = []
        for risk_group in raw:
            if not isinstance(risk_group, dict):
                continue
            risk_code = risk_group.get("risk_id")
            nested = risk_group.get("test_cases") or []
            for tc in nested:
                if not isinstance(tc, dict):
                    continue
                test_id = tc.get("test_id")
                tc_name = tc.get("test_name") or tc.get("name")
                if not test_id or not tc_name:
                    continue
                test_cases.append(NormalizedTestCase(
                    test_id=test_id,
                    name=tc_name,
                    risk_code=risk_code,
                    test_type=tc.get("test_type"),
                    objective=self.clean_text(tc.get("objective")),
                    test_steps=[str(s) for s in (tc.get("test_steps") or [])],
                    expected_result=self.clean_text(tc.get("expected_result")),
                    evidence_required=list(tc.get("evidence_required") or []),
                    success_criteria=list(tc.get("success_criteria") or []),
                    metadata={"risk_name": risk_group.get("risk_name")},
                ))
        return test_cases

    def _load_scenarios(self) -> List[NormalizedScenario]:
        path = self._find_file("scenarios_nist_csf_2_0")
        if not path:
            logger.warning("NIST CSF 2.0 scenarios file not found.")
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
