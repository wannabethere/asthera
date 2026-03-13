"""
Reverse Mapper: CIS Scenario → ATT&CK Techniques
=================================================
The forward graph maps  technique  → CIS scenarios.
This module provides the inverse:  scenario  → ATT&CK techniques.

Why both directions?
  - Forward  (T-number in)  : "I received an alert for T1078 – what controls apply?"
  - Reverse  (scenario in)  : "CIS-RISK-007 is a malware risk – what techniques cause it?"

The reverse mapper is used by:
  1. The batch enricher to seed the forward graph for each scenario.
  2. The CCE triage pipeline to cross-reference scenario risk against live alert technique IDs.

Architecture
------------
  ScenarioToTechniqueMapper
    ├── _suggest_via_llm()        LLM call → candidate T-numbers
    ├── _validate_technique_ids() filter against known ATT&CK catalogue
    └── _rank_by_relevance()      second LLM pass → ranked, scored list

LangChain tool: create_reverse_mapper_tool()
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from ..attack_enrichment import ATTACKEnrichmentTool, _load_stix_bundle, _extract_attack_id
    from ..control_loader import CISRiskScenario
except ImportError:
    from app.ingestion.attacktocve.attack_enrichment import ATTACKEnrichmentTool, _load_stix_bundle, _extract_attack_id
    from app.ingestion.attacktocve.control_loader import CISRiskScenario

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SUGGEST_SYSTEM = """\
You are a MITRE ATT&CK threat intelligence analyst. Given a CIS Controls v8.1
risk scenario description, identify which MITRE ATT&CK Enterprise techniques
(or sub-techniques) could directly cause or exploit the described risk.

Rules:
- Return ONLY a JSON array of objects. No markdown, no prose before or after.
- Each object must include:
    "technique_id"  : string (e.g. "T1078", "T1059.001")
    "relevance"     : 0.0–1.0  (how directly this technique causes the scenario)
    "rationale"     : string (≤2 sentences explaining the link)
- Include 3–8 techniques. Prefer specific sub-techniques over parent techniques.
- Only include techniques where relevance ≥ 0.45.
- Cover the full MITRE ATT&CK tactic spectrum where applicable
  (initial access, execution, persistence, privilege escalation, etc.).

Output schema:
[{"technique_id": "T...", "relevance": 0.0, "rationale": "..."}]
"""

_SUGGEST_USER = """\
=== CIS Risk Scenario ===
ID:              {scenario_id}
Name:            {name}
Asset domain:    {asset}
Trigger:         {trigger}
Loss outcomes:   {loss_outcomes}
Description:
{description}

List the ATT&CK techniques that could directly cause this scenario.
Return a JSON array only.
"""


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class TechniqueSuggestion(BaseModel):
    technique_id: str
    technique_name: str = ""
    relevance: float = Field(ge=0.0, le=1.0)
    rationale: str
    tactics: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    validated: bool = False  # True once confirmed against ATT&CK catalogue


# ---------------------------------------------------------------------------
# Core mapper
# ---------------------------------------------------------------------------

class ScenarioToTechniqueMapper:
    """
    Suggests ATT&CK techniques for a given CIS risk scenario.
    Validates returned T-numbers against the live ATT&CK STIX catalogue.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        validate_ids: bool = True,
    ):
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        self.validate_ids = validate_ids
        self._enricher = ATTACKEnrichmentTool()
        self._known_ids: Optional[set] = None  # lazy-loaded from STIX

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def suggest(self, scenario: CISRiskScenario) -> List[TechniqueSuggestion]:
        raw = self._suggest_via_llm(scenario)
        if self.validate_ids:
            raw = self._validate_and_enrich(raw)
        return sorted(raw, key=lambda s: s.relevance, reverse=True)

    def suggest_from_dict(self, scenario_dict: Dict[str, Any]) -> List[TechniqueSuggestion]:
        scenario = CISRiskScenario(**scenario_dict)
        return self.suggest(scenario)

    # ------------------------------------------------------------------
    # LLM suggestion
    # ------------------------------------------------------------------

    def _suggest_via_llm(self, scenario: CISRiskScenario) -> List[TechniqueSuggestion]:
        user_prompt = _SUGGEST_USER.format(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            asset=scenario.asset,
            trigger=scenario.trigger,
            loss_outcomes=", ".join(scenario.loss_outcomes),
            description=scenario.description[:1200] if scenario.description else "No description available.",
        )
        messages = [
            SystemMessage(content=_SUGGEST_SYSTEM),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        raw_text = response.content.strip()

        try:
            items = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to extract JSON array from response
            match = re.search(r"\[.*\]", raw_text, re.DOTALL)
            if match:
                items = json.loads(match.group())
            else:
                logger.error(f"[reverse_mapper] Could not parse LLM response: {raw_text[:300]}")
                return []

        suggestions = []
        for item in items:
            tid = item.get("technique_id", "").strip().upper()
            if not re.match(r"^T\d{4}(\.\d{3})?$", tid):
                logger.debug(f"[reverse_mapper] Skipping invalid ID: {tid}")
                continue
            suggestions.append(
                TechniqueSuggestion(
                    technique_id=tid,
                    relevance=float(item.get("relevance", 0.5)),
                    rationale=item.get("rationale", ""),
                )
            )

        logger.info(
            f"[reverse_mapper] {scenario.scenario_id}: LLM suggested {len(suggestions)} techniques"
        )
        return suggestions

    # ------------------------------------------------------------------
    # Validation + enrichment
    # ------------------------------------------------------------------

    def _get_known_ids(self) -> set:
        """Lazily load all ATT&CK technique IDs from the STIX bundle."""
        if self._known_ids is not None:
            return self._known_ids

        bundle = _load_stix_bundle()
        known = set()
        for obj in bundle.get("objects", []):
            if obj.get("type") == "attack-pattern":
                aid = _extract_attack_id(obj)
                if aid:
                    known.add(aid)
        self._known_ids = known
        logger.info(f"[reverse_mapper] Loaded {len(known)} known ATT&CK IDs")
        return known

    def _validate_and_enrich(
        self, suggestions: List[TechniqueSuggestion]
    ) -> List[TechniqueSuggestion]:
        """Filter out hallucinated T-numbers; enrich valid ones with STIX metadata."""
        known = self._get_known_ids()
        enriched = []
        for s in suggestions:
            if s.technique_id not in known:
                logger.warning(f"[reverse_mapper] Unknown technique ID: {s.technique_id} – dropping")
                continue
            try:
                detail = self._enricher.get_technique(s.technique_id)
                s.technique_name = detail.name
                s.tactics = detail.tactics
                s.platforms = detail.platforms
                s.validated = True
            except Exception as exc:
                logger.warning(f"[reverse_mapper] Could not enrich {s.technique_id}: {exc}")
                s.validated = False
            enriched.append(s)
        return enriched


# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------

class ReverseMappingInput(BaseModel):
    scenario_id: str = Field(description="CIS risk scenario ID, e.g. 'CIS-RISK-007'")
    scenario_name: str = Field(description="Short name of the scenario")
    asset: str = Field(description="CIS asset domain, e.g. 'operations_security'")
    trigger: str = Field(description="What triggers the risk scenario")
    loss_outcomes: List[str] = Field(description="Expected loss types")
    description: str = Field(description="Full scenario description")


def create_reverse_mapper_tool(validate_ids: bool = True) -> StructuredTool:
    """
    Returns a LangChain StructuredTool that maps a CIS scenario → ATT&CK techniques.
    Can be added to the CCE toolset for bi-directional ATT&CK ↔ CIS reasoning.
    """
    mapper = ScenarioToTechniqueMapper(validate_ids=validate_ids)

    def _execute(
        scenario_id: str,
        scenario_name: str,
        asset: str,
        trigger: str,
        loss_outcomes: List[str],
        description: str,
    ) -> List[Dict[str, Any]]:
        try:
            scenario = CISRiskScenario(
                scenario_id=scenario_id,
                name=scenario_name,
                asset=asset,
                trigger=trigger,
                loss_outcomes=loss_outcomes,
                description=description,
            )
            suggestions = mapper.suggest(scenario)
            return [s.model_dump() for s in suggestions]
        except Exception as exc:
            logger.error(f"[reverse_mapper_tool] Error: {exc}")
            return [{"error": str(exc)}]

    return StructuredTool.from_function(
        func=_execute,
        name="cis_scenario_to_attack_techniques",
        description=(
            "Given a CIS Controls v8.1 risk scenario, returns a ranked list of "
            "MITRE ATT&CK techniques that could directly cause or exploit that scenario. "
            "Use this when you have a risk scenario and need to find related attack techniques "
            "for threat modelling or detection coverage analysis."
        ),
        args_schema=ReverseMappingInput,
    )
