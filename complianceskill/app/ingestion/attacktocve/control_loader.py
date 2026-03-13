"""
CIS Controls Loader
====================
Parses the CIS Controls v8.1 risk scenario YAML and provides a registry
that the graph nodes can query by scenario_id, asset domain, or keyword.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class CISRiskScenario(BaseModel):
    scenario_id: str
    name: str
    asset: str
    trigger: str
    loss_outcomes: List[str] = Field(default_factory=list)
    description: str = Field(default="", description="Risk scenario description")
    controls: List[str] = Field(default_factory=list)

    @field_validator("name", "asset", "trigger", mode="before")
    @classmethod
    def clean_string(cls, v):
        """Strip YAML escape artefacts (backslash-quote wrapping)."""
        if isinstance(v, str):
            v = v.strip().strip('"').strip("'")
            v = re.sub(r'\\+"', '"', v)
            v = re.sub(r'\\+\'', "'", v)
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v):
        """Handle missing or empty descriptions."""
        if v is None:
            return ""
        return str(v).strip()

    @property
    def full_text(self) -> str:
        """Concatenated text for embedding / LLM context."""
        parts = [
            f"Scenario: {self.scenario_id} – {self.name}",
            f"Asset: {self.asset}",
            f"Trigger: {self.trigger}",
            f"Loss outcomes: {', '.join(self.loss_outcomes) if self.loss_outcomes else 'N/A'}",
        ]
        if self.description:
            parts.append(f"Description: {self.description}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_cis_scenarios(yaml_path: str | Path) -> List[CISRiskScenario]:
    """
    Parse CIS Controls YAML and return a list of CISRiskScenario models.

    Handles the malformed YAML escaping present in the source file
    (nested backslash/quote artefacts from the generator).
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"CIS controls YAML not found: {path}")

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list, got {type(data)}")

    scenarios: List[CISRiskScenario] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            s = CISRiskScenario(**item)
            scenarios.append(s)
        except Exception as exc:
            sid = item.get("scenario_id", "?")
            logger.warning(f"Skipping malformed scenario {sid}: {exc}")

    logger.info(f"Loaded {len(scenarios)} CIS risk scenarios from {path.name}")
    return scenarios


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class CISControlRegistry:
    """
    In-memory registry built from the loaded scenarios.
    Provides fast lookups used by LangGraph nodes.
    """

    def __init__(self, scenarios: List[CISRiskScenario]):
        self._by_id: Dict[str, CISRiskScenario] = {s.scenario_id: s for s in scenarios}
        self._by_asset: Dict[str, List[CISRiskScenario]] = {}
        for s in scenarios:
            self._by_asset.setdefault(s.asset.lower(), []).append(s)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, scenario_id: str) -> Optional[CISRiskScenario]:
        return self._by_id.get(scenario_id)

    def all(self) -> List[CISRiskScenario]:
        return list(self._by_id.values())

    def by_asset(self, asset: str) -> List[CISRiskScenario]:
        return self._by_asset.get(asset.lower(), [])

    def ids(self) -> List[str]:
        return list(self._by_id.keys())

    def search(self, keyword: str) -> List[CISRiskScenario]:
        kw = keyword.lower()
        return [
            s for s in self._by_id.values()
            if kw in s.name.lower()
            or (s.description and kw in s.description.lower())
            or kw in s.asset.lower()
        ]

    # ------------------------------------------------------------------
    # Update after mapping
    # ------------------------------------------------------------------

    def update_controls(self, scenario_id: str, controls: List[str]) -> None:
        """Merge newly mapped ATT&CK controls into a scenario."""
        s = self._by_id.get(scenario_id)
        if s:
            merged = list(dict.fromkeys(s.controls + controls))  # deduplicate, preserve order
            s.controls = merged

    def export_yaml(self, output_path: str | Path) -> None:
        """Serialize the enriched registry back to YAML."""
        import yaml

        data = [s.model_dump() for s in self._by_id.values()]
        Path(output_path).write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        logger.info(f"Exported enriched scenarios to {output_path}")

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def coverage_report(self) -> Dict[str, int]:
        """Return mapping coverage stats."""
        total = len(self._by_id)
        mapped = sum(1 for s in self._by_id.values() if s.controls)
        return {
            "total_scenarios": total,
            "mapped": mapped,
            "unmapped": total - mapped,
            "coverage_pct": round(mapped / total * 100, 1) if total else 0,
        }
