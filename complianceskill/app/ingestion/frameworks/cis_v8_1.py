"""
CIS Controls v8.1 adapter.

Source files:
  - controls_cis_controls_v8_1.yaml      → controls + cross-framework refs
  - cis_controls_v8_1_risk_controls.yaml → risks with mitigating controls
  - cis_controls_v8_1_test_cases.yaml    → test cases grouped by risk
  - scenarios_cis_controls_v8_1.yaml     → risk scenarios

Note: The controls YAML shipped with only 1 item and appears to have inline
YAML embedded in the description field (a known export artifact). The adapter
handles this by attempting to parse embedded fields from the description text
when the top-level fields are absent. All other YAML files are well-formed.
"""

import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import yaml

from app.ingestion.base import (
    BaseFrameworkAdapter,
    FrameworkIngestionBundle,
    NormalizedFramework,
    NormalizedControl,
    NormalizedRisk,
    NormalizedTestCase,
    NormalizedScenario,
)

logger = logging.getLogger(__name__)


class CISv81Adapter(BaseFrameworkAdapter):
    """
    Adapter for CIS Controls v8.1.

    Args:
        data_dir: Directory containing the CIS YAML files.
                  File names are matched by prefix/keyword — exact file names
                  are not hardcoded so the adapter is resilient to timestamp prefixes.
    """

    FRAMEWORK_ID = "cis_v8_1"

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)

    @property
    def framework_id(self) -> str:
        return self.FRAMEWORK_ID

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def load(self) -> FrameworkIngestionBundle:
        bundle = FrameworkIngestionBundle(
            framework=NormalizedFramework(
                id=self.FRAMEWORK_ID,
                name="CIS Controls",
                version="v8.1",
                description=(
                    "The CIS Controls are a prioritized set of actions that collectively "
                    "form a defense-in-depth set of best practices to mitigate the most "
                    "common attacks against systems and networks."
                ),
                source_url="https://www.cisecurity.org/controls/v8",
            )
        )

        bundle.controls = self._load_controls()
        bundle.risks = self._load_risks()
        bundle.test_cases = self._load_test_cases()
        bundle.scenarios = self._load_scenarios()

        logger.info(
            f"CIS v8.1 adapter loaded: {len(bundle.controls)} controls, "
            f"{len(bundle.risks)} risks, {len(bundle.test_cases)} test cases, "
            f"{len(bundle.scenarios)} scenarios"
        )
        return bundle

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _load_controls(self) -> list[NormalizedControl]:
        path = self._find_file("controls_cis_controls")
        if not path:
            logger.warning("CIS controls file not found.")
            return []

        raw = self._read_yaml(path)
        if not isinstance(raw, list):
            logger.warning(f"CIS controls: expected list, got {type(raw)}")
            return []

        controls = []
        for item in raw:
            control = self._parse_control(item)
            if control:
                controls.append(control)
        return controls

    def _parse_control(self, item: Dict[str, Any]) -> Optional[NormalizedControl]:
        """
        Parse a single control record.

        The controls YAML has a known export issue where fields like domain,
        type, cis_control_id, and related_frameworks were concatenated into
        the description field as inline YAML text. This parser detects and
        recovers those fields.
        """
        if not isinstance(item, dict):
            return None

        control_id = item.get("control_id")
        name = item.get("name")
        if not control_id or not name:
            return None

        description_raw = item.get("description", "") or ""

        # Attempt to recover embedded fields from malformed description
        recovered = self._recover_embedded_fields(description_raw)

        # Build the clean description (everything before the embedded YAML block)
        clean_desc = self._extract_clean_description(description_raw)

        domain = item.get("domain") or recovered.get("domain")
        control_type = item.get("type") or recovered.get("type")
        cis_control_id = item.get("cis_control_id") or recovered.get("cis_control_id")
        related_frameworks_raw = item.get("related_frameworks") or recovered.get("related_frameworks", {})

        cross_refs = self.parse_cross_framework_refs(related_frameworks_raw)

        return NormalizedControl(
            control_code=control_id.strip(),
            name=self.clean_text(name),
            description=clean_desc,
            domain=self.clean_text(domain),
            control_type=self.clean_text(control_type),
            cis_control_id=self.clean_text(cis_control_id),
            cross_framework_refs=cross_refs,
            metadata={"source_control_id": control_id},
        )

    def _recover_embedded_fields(self, description: str) -> Dict[str, Any]:
        """
        The malformed controls YAML embeds structured fields inside the
        description string. Example:
          "...remediation. domain: VULNERABILITY_PATCH_MANAGEMENT type: detective
           cis_control_id: CIS-7 related_frameworks: soc2: "CC 2.1" ..."

        This method extracts those fields via regex and returns them as a dict.
        """
        recovered: Dict[str, Any] = {}

        domain_match = re.search(r'\bdomain:\s*([A-Z_]+)', description)
        if domain_match:
            recovered["domain"] = domain_match.group(1)

        type_match = re.search(r'\btype:\s*(\w+)', description)
        if type_match:
            recovered["type"] = type_match.group(1)

        cis_match = re.search(r'\bcis_control_id:\s*(CIS-\S+)', description)
        if cis_match:
            recovered["cis_control_id"] = cis_match.group(1)

        # Extract soc2 refs
        soc2_match = re.search(r'soc2:\s*"([^"]+)"', description)
        if soc2_match:
            recovered["related_frameworks"] = {"soc2": soc2_match.group(1)}

        # Extract nist refs (without quotes)
        nist_match = re.search(r'nist_csf_2_0:\s*(?:domain:[^c]+)?(?:([A-Z]{2}\.[A-Z]{2}-\d+))', description)
        if nist_match:
            rf = recovered.get("related_frameworks", {})
            rf["nist_csf_2_0"] = nist_match.group(1)
            recovered["related_frameworks"] = rf

        return recovered

    def _extract_clean_description(self, description: str) -> Optional[str]:
        """
        Return only the natural-language portion of the description,
        stripping any embedded YAML-like field declarations.
        """
        if not description:
            return None
        # Cut off at the first occurrence of an embedded field pattern
        cutoff = re.search(r'\s+domain:\s+[A-Z_]+', description)
        if cutoff:
            return description[:cutoff.start()].strip() or None
        return description.strip() or None

    def _load_risks(self) -> list[NormalizedRisk]:
        path = self._find_file("risk_controls")
        if not path:
            logger.warning("CIS risk_controls file not found.")
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

            # controls list in this file may be empty — populated later via test_cases linkage
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
                metadata={"source_scenario_id": risk_code},
            ))

        return risks

    def _load_test_cases(self) -> list[NormalizedTestCase]:
        path = self._find_file("test_cases")
        if not path:
            logger.warning("CIS test_cases file not found.")
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

    def _load_scenarios(self) -> list[NormalizedScenario]:
        path = self._find_file("scenarios_cis")
        if not path:
            logger.warning("CIS scenarios file not found.")
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
    # File helpers
    # ------------------------------------------------------------------

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
