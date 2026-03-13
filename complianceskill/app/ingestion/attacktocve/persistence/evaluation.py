"""
Evaluation & Scoring Module
============================
Computes quality metrics for the ATT&CK → CIS control mapping pipeline.

Metrics
-------
Per-mapping:
  - relevance_score          : LLM-assigned (0–1)
  - confidence               : high / medium / low
  - tactic_coverage          : % of ATT&CK tactics covered across mappings
  - scenario_diversity       : unique CIS asset domains hit

Per-scenario:
  - technique_count          : ATT&CK techniques mapped to this scenario
  - avg_relevance            : mean relevance_score of all mappings
  - loss_coverage            : % of loss_outcomes addressed by at least one technique

Aggregate:
  - scenario_coverage_pct    : % of 67 scenarios with ≥1 mapping
  - technique_diversity      : # of unique techniques across all mappings
  - tactic_breadth           : # of ATT&CK tactics represented
  - inter_rater_consistency  : placeholder for human-review alignment score

Usage
-----
    from evaluation import Evaluator, load_ground_truth

    evaluator = Evaluator()
    report = evaluator.evaluate(
        mappings=state["final_mappings"],
        scenarios=registry.all(),
        ground_truth=load_ground_truth("ground_truth.json"),  # optional
    )
    evaluator.print_report(report)
    evaluator.export_report(report, "eval_report.json")
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from ..state import ControlMapping
    from ..control_loader import CISRiskScenario
except ImportError:
    from app.ingestion.attacktocve.state import ControlMapping
    from app.ingestion.attacktocve.control_loader import CISRiskScenario

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ATT&CK tactic catalogue (14 enterprise tactics)
# ---------------------------------------------------------------------------

ALL_TACTICS: Set[str] = {
    "Reconnaissance", "Resource Development", "Initial Access",
    "Execution", "Persistence", "Privilege Escalation",
    "Defense Evasion", "Credential Access", "Discovery",
    "Lateral Movement", "Collection", "Command And Control",
    "Exfiltration", "Impact",
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PerMappingMetrics:
    technique_id: str
    scenario_id: str
    relevance_score: float
    confidence: str
    tactics: List[str]
    tactic_coverage: float    # fraction of 14 tactics covered (this mapping)
    is_verified: bool = False # True if matches ground truth


@dataclass
class PerScenarioMetrics:
    scenario_id: str
    scenario_name: str
    asset: str
    loss_outcomes: List[str]
    technique_count: int
    avg_relevance: float
    min_relevance: float
    max_relevance: float
    confidence_distribution: Dict[str, int]
    tactics_covered: List[str]
    loss_outcome_coverage: float  # % of declared loss outcomes addressed
    grade: str                    # A / B / C / D / F


@dataclass
class AggregateMetrics:
    total_scenarios: int
    mapped_scenarios: int
    scenario_coverage_pct: float
    total_mappings: int
    unique_techniques: int
    unique_tactics: int
    tactic_breadth_pct: float
    avg_relevance_score: float
    avg_techniques_per_scenario: float
    confidence_distribution: Dict[str, int]
    asset_domain_coverage: Dict[str, float]  # asset → % of scenarios covered
    precision_vs_ground_truth: Optional[float]  # only set if GT provided
    recall_vs_ground_truth: Optional[float]


@dataclass
class EvaluationReport:
    per_mapping: List[PerMappingMetrics] = field(default_factory=list)
    per_scenario: List[PerScenarioMetrics] = field(default_factory=list)
    aggregate: Optional[AggregateMetrics] = None
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _cvt(obj):
            if hasattr(obj, "__dict__"):
                return {k: _cvt(v) for k, v in obj.__dict__.items()}
            if isinstance(obj, list):
                return [_cvt(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _cvt(v) for k, v in obj.items()}
            return obj

        return {
            "aggregate": _cvt(self.aggregate),
            "per_scenario": [_cvt(s) for s in self.per_scenario],
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


# ---------------------------------------------------------------------------
# Ground truth helper
# ---------------------------------------------------------------------------

def load_ground_truth(path: str) -> Dict[str, List[str]]:
    """
    Load optional human-verified ground truth.

    Expected JSON format:
        {
          "CIS-RISK-001": ["T1078", "T1110"],
          "CIS-RISK-007": ["T1059.001", "T1486"]
        }

    Returns:
        Dict mapping scenario_id → list of expected technique IDs.
    """
    p = Path(path)
    if not p.exists():
        logger.warning(f"Ground truth file not found: {path}")
        return {}
    data = json.loads(p.read_text())
    logger.info(f"Loaded ground truth for {len(data)} scenarios")
    return data


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class Evaluator:
    """
    Computes structured quality metrics for a set of ATT&CK → CIS mappings.
    """

    def evaluate(
        self,
        mappings: List[ControlMapping],
        scenarios: List[CISRiskScenario],
        ground_truth: Optional[Dict[str, List[str]]] = None,
    ) -> EvaluationReport:
        report = EvaluationReport()

        # Index
        scenarios_by_id = {s.scenario_id: s for s in scenarios}
        mappings_by_scenario: Dict[str, List[ControlMapping]] = defaultdict(list)
        for m in mappings:
            mappings_by_scenario[m.scenario_id].append(m)

        # Per-mapping metrics
        all_tactic_sets: List[Set[str]] = []
        for m in mappings:
            tactic_set = set(m.attack_tactics)
            coverage = len(tactic_set & ALL_TACTICS) / len(ALL_TACTICS)
            verified = (
                m.technique_id in (ground_truth or {}).get(m.scenario_id, [])
                if ground_truth else False
            )
            report.per_mapping.append(
                PerMappingMetrics(
                    technique_id=m.technique_id,
                    scenario_id=m.scenario_id,
                    relevance_score=m.relevance_score,
                    confidence=m.confidence,
                    tactics=m.attack_tactics,
                    tactic_coverage=coverage,
                    is_verified=verified,
                )
            )
            all_tactic_sets.append(tactic_set)

        # Per-scenario metrics
        all_tactics_covered: Set[str] = set()
        for sid, smappings in mappings_by_scenario.items():
            scenario = scenarios_by_id.get(sid)
            if not scenario:
                continue

            tacts: Set[str] = set()
            for m in smappings:
                tacts.update(m.attack_tactics)
            all_tactics_covered |= tacts

            relevances = [m.relevance_score for m in smappings]
            conf_dist = {"high": 0, "medium": 0, "low": 0}
            for m in smappings:
                conf_dist[m.confidence] = conf_dist.get(m.confidence, 0) + 1

            # Loss outcome coverage: do any tactics address breach / compliance / ops?
            loss_addressed = 0
            for loss in scenario.loss_outcomes:
                loss_lower = loss.lower()
                if "breach" in loss_lower and any(
                    t in tacts for t in {"Initial Access", "Exfiltration", "Credential Access"}
                ):
                    loss_addressed += 1
                elif "compliance" in loss_lower and any(
                    t in tacts for t in {"Defense Evasion", "Impact", "Execution"}
                ):
                    loss_addressed += 1
                elif "operational" in loss_lower and any(
                    t in tacts for t in {"Impact", "Lateral Movement", "Persistence"}
                ):
                    loss_addressed += 1
            loss_coverage = (
                loss_addressed / len(scenario.loss_outcomes) if scenario.loss_outcomes else 0.0
            )

            avg_rel = sum(relevances) / len(relevances) if relevances else 0.0
            grade = self._grade(avg_rel, len(smappings), loss_coverage)

            report.per_scenario.append(
                PerScenarioMetrics(
                    scenario_id=sid,
                    scenario_name=scenario.name,
                    asset=scenario.asset,
                    loss_outcomes=scenario.loss_outcomes,
                    technique_count=len(smappings),
                    avg_relevance=round(avg_rel, 3),
                    min_relevance=round(min(relevances), 3) if relevances else 0.0,
                    max_relevance=round(max(relevances), 3) if relevances else 0.0,
                    confidence_distribution=conf_dist,
                    tactics_covered=sorted(tacts),
                    loss_outcome_coverage=round(loss_coverage, 3),
                    grade=grade,
                )
            )

        # Issues
        self._detect_issues(report, mappings, scenarios, ground_truth)

        # Aggregate
        report.aggregate = self._compute_aggregate(
            mappings, scenarios, report.per_scenario, all_tactics_covered, ground_truth
        )

        # Recommendations
        self._add_recommendations(report)

        return report

    # ------------------------------------------------------------------
    # Grading
    # ------------------------------------------------------------------

    @staticmethod
    def _grade(avg_relevance: float, technique_count: int, loss_coverage: float) -> str:
        score = (avg_relevance * 0.5) + (min(technique_count, 5) / 5 * 0.3) + (loss_coverage * 0.2)
        if score >= 0.85:
            return "A"
        elif score >= 0.70:
            return "B"
        elif score >= 0.55:
            return "C"
        elif score >= 0.40:
            return "D"
        return "F"

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------

    def _compute_aggregate(
        self,
        mappings: List[ControlMapping],
        scenarios: List[CISRiskScenario],
        per_scenario: List[PerScenarioMetrics],
        all_tactics: Set[str],
        ground_truth: Optional[Dict[str, List[str]]],
    ) -> AggregateMetrics:
        mapped_sids = {ps.scenario_id for ps in per_scenario if ps.technique_count > 0}
        unique_tids = {m.technique_id for m in mappings}
        conf_dist: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        for m in mappings:
            conf_dist[m.confidence] = conf_dist.get(m.confidence, 0) + 1

        # Asset domain coverage
        asset_total: Dict[str, int] = defaultdict(int)
        asset_mapped: Dict[str, int] = defaultdict(int)
        for s in scenarios:
            asset_total[s.asset] += 1
        for ps in per_scenario:
            if ps.technique_count > 0:
                asset_mapped[ps.asset] += 1
        asset_coverage = {
            asset: round(asset_mapped[asset] / total * 100, 1)
            for asset, total in asset_total.items()
        }

        avg_rel = (
            sum(m.relevance_score for m in mappings) / len(mappings) if mappings else 0.0
        )
        avg_tech = (
            sum(ps.technique_count for ps in per_scenario) / len(per_scenario)
            if per_scenario else 0.0
        )

        # Ground truth precision / recall
        precision, recall = None, None
        if ground_truth:
            tp = fp = fn = 0
            for m in mappings:
                expected = set(ground_truth.get(m.scenario_id, []))
                if m.technique_id in expected:
                    tp += 1
                else:
                    fp += 1
            for sid, tids in ground_truth.items():
                predicted = {m.technique_id for m in mappings if m.scenario_id == sid}
                fn += len(set(tids) - predicted)
            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
            recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0

        return AggregateMetrics(
            total_scenarios=len(scenarios),
            mapped_scenarios=len(mapped_sids),
            scenario_coverage_pct=round(len(mapped_sids) / len(scenarios) * 100, 1),
            total_mappings=len(mappings),
            unique_techniques=len(unique_tids),
            unique_tactics=len(all_tactics & ALL_TACTICS),
            tactic_breadth_pct=round(len(all_tactics & ALL_TACTICS) / len(ALL_TACTICS) * 100, 1),
            avg_relevance_score=round(avg_rel, 3),
            avg_techniques_per_scenario=round(avg_tech, 2),
            confidence_distribution=conf_dist,
            asset_domain_coverage=asset_coverage,
            precision_vs_ground_truth=precision,
            recall_vs_ground_truth=recall,
        )

    # ------------------------------------------------------------------
    # Issue detection
    # ------------------------------------------------------------------

    def _detect_issues(
        self,
        report: EvaluationReport,
        mappings: List[ControlMapping],
        scenarios: List[CISRiskScenario],
        ground_truth: Optional[Dict[str, List[str]]],
    ) -> None:
        mapped_sids = {m.scenario_id for m in mappings}
        for s in scenarios:
            if s.scenario_id not in mapped_sids:
                report.issues.append(f"UNMAPPED: {s.scenario_id} ({s.name[:50]}) has no control mappings")

        low_only = [
            m for m in mappings if m.confidence == "low" and m.relevance_score < 0.45
        ]
        if low_only:
            tids = list({m.technique_id for m in low_only})[:5]
            report.issues.append(
                f"LOW_QUALITY: {len(low_only)} mapping(s) have confidence=low AND relevance<0.45 "
                f"(sample techniques: {tids})"
            )

        # Duplicate technique-scenario pairs
        seen: set = set()
        for m in mappings:
            key = (m.technique_id, m.scenario_id)
            if key in seen:
                report.issues.append(f"DUPLICATE: {m.technique_id} → {m.scenario_id} appears more than once")
            seen.add(key)

        if ground_truth:
            for sid, expected in ground_truth.items():
                predicted = {m.technique_id for m in mappings if m.scenario_id == sid}
                missed = set(expected) - predicted
                if missed:
                    report.issues.append(f"MISSED_GT: {sid} missing expected techniques: {missed}")

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _add_recommendations(self, report: EvaluationReport) -> None:
        agg = report.aggregate
        if not agg:
            return

        if agg.scenario_coverage_pct < 80:
            report.recommendations.append(
                f"Coverage is {agg.scenario_coverage_pct}% — run batch_enricher.py "
                f"for the remaining {agg.total_scenarios - agg.mapped_scenarios} scenarios."
            )
        if agg.tactic_breadth_pct < 60:
            report.recommendations.append(
                "Tactic breadth is low — consider seeding the reverse mapper with "
                "techniques from underrepresented tactics (e.g. Reconnaissance, Collection)."
            )
        if agg.avg_relevance_score < 0.65:
            report.recommendations.append(
                "Average relevance score is below 0.65 — consider raising the "
                "score threshold in validate_mappings_node and re-running validation."
            )
        high_pct = (
            agg.confidence_distribution.get("high", 0) / agg.total_mappings * 100
            if agg.total_mappings else 0
        )
        if high_pct < 30:
            report.recommendations.append(
                f"Only {high_pct:.0f}% of mappings are high-confidence — "
                "consider adding domain-specific few-shot examples to the mapping prompt."
            )
        if not report.issues:
            report.recommendations.append("No issues detected — mapping quality looks solid.")

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_report(self, report: EvaluationReport) -> None:
        agg = report.aggregate
        if not agg:
            print("No aggregate metrics available.")
            return

        print("\n" + "═" * 68)
        print("  ATT&CK → CIS Control Mapping — Evaluation Report")
        print("═" * 68)
        print(f"  Scenario coverage  : {agg.mapped_scenarios}/{agg.total_scenarios} ({agg.scenario_coverage_pct}%)")
        print(f"  Total mappings     : {agg.total_mappings}")
        print(f"  Unique techniques  : {agg.unique_techniques}")
        print(f"  Tactic breadth     : {agg.unique_tactics}/14 ({agg.tactic_breadth_pct}%)")
        print(f"  Avg relevance score: {agg.avg_relevance_score}")
        print(f"  Avg tech/scenario  : {agg.avg_techniques_per_scenario}")
        cd = agg.confidence_distribution
        print(f"  Confidence dist    : high={cd.get('high',0)} medium={cd.get('medium',0)} low={cd.get('low',0)}")
        if agg.precision_vs_ground_truth is not None:
            print(f"  Precision vs GT    : {agg.precision_vs_ground_truth}")
            print(f"  Recall vs GT       : {agg.recall_vs_ground_truth}")
        print("─" * 68)

        grade_dist: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for ps in report.per_scenario:
            grade_dist[ps.grade] = grade_dist.get(ps.grade, 0) + 1
        print("  Scenario grade distribution:")
        for grade, count in sorted(grade_dist.items()):
            bar = "█" * count
            print(f"    {grade}  {bar} ({count})")

        print("─" * 68)
        if report.issues:
            print(f"  Issues ({len(report.issues)}):")
            for issue in report.issues[:8]:
                print(f"    ⚠  {issue}")
            if len(report.issues) > 8:
                print(f"    … and {len(report.issues)-8} more (see full JSON report)")
        print("─" * 68)
        print("  Recommendations:")
        for rec in report.recommendations:
            print(f"    → {rec}")
        print("═" * 68 + "\n")

    def export_report(self, report: EvaluationReport, output_path: str) -> None:
        Path(output_path).write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
        logger.info(f"Evaluation report exported → {output_path}")
