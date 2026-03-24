"""
Base Analysis Skill — declarative skill definition for analysis types.

Each analysis type (gap_analysis, crown_jewel, anomaly_detection, …) is a
skill with four phases:
    1. Intent Identifier   — refines the classified intent, extracts skill params
    2. Analysis Planner    — produces a data plan (metrics, KPIs, transformations)
    3. Metric Recommender  — skill-specific instructions injected into recommender
    4. Validator           — post-recommendation relevance scoring & filtering

Skills are shared across csod_workflow and dt_workflow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# ── Nested config dataclasses ────────────────────────────────────────────────

@dataclass(frozen=True)
class IntentSignals:
    """Signals used to confirm a skill match after high-level classification."""
    keywords: List[str] = field(default_factory=list)
    question_patterns: List[str] = field(default_factory=list)
    analysis_requirements: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IntentSignals":
        return cls(
            keywords=d.get("keywords", []),
            question_patterns=d.get("question_patterns", []),
            analysis_requirements=d.get("analysis_requirements", []),
        )


@dataclass(frozen=True)
class DTConfig:
    """Decision-tree resolver parameters (mirrors DT_INTENT_CONFIG entry)."""
    use_case: Optional[str] = None
    goal: Any = None  # str | List[str] | None
    metric_type: Any = None  # str | List[str] | None
    audience: Optional[str] = None
    timeframe: Optional[str] = None
    dt_group_by: str = "goal"
    min_composite: float = 0.55
    # Special requirement flags
    requires_target_value: bool = False
    enforce_trend_only: bool = False
    requires_funnel_stages: bool = False
    requires_segment_dimension: bool = False
    requires_comparable_value: bool = False
    requires_deadline_dimension: bool = False
    requires_cost_and_outcome_pair: bool = False
    focus_area_override: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DTConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_intent_config_dict(self) -> Dict[str, Any]:
        """Export to the legacy DT_INTENT_CONFIG format."""
        out: Dict[str, Any] = {
            "use_case": self.use_case,
            "goal": self.goal,
            "metric_type": self.metric_type,
            "audience": self.audience,
            "timeframe": self.timeframe,
            "dt_group_by": self.dt_group_by,
            "min_composite": self.min_composite,
        }
        # Only include special flags that are truthy
        for flag in (
            "requires_target_value", "enforce_trend_only", "requires_funnel_stages",
            "requires_segment_dimension", "requires_comparable_value",
            "requires_deadline_dimension", "requires_cost_and_outcome_pair",
        ):
            val = getattr(self, flag)
            if val:
                out[flag] = val
        if self.focus_area_override:
            out["focus_area_override"] = self.focus_area_override
        return out


@dataclass(frozen=True)
class CCEConfig:
    """Causal graph (CCE) settings (mirrors CCE_INTENT_CONFIG entry)."""
    enabled: bool = False
    mode: str = "disabled"  # required | optional | disabled
    provides: str = ""
    uses: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CCEConfig":
        return cls(
            enabled=d.get("enabled", False),
            mode=d.get("mode", "disabled"),
            provides=d.get("provides", ""),
            uses=d.get("uses", ""),
        )

    def to_intent_config_dict(self) -> Dict[str, Any]:
        """Export to the legacy CCE_INTENT_CONFIG format."""
        out: Dict[str, Any] = {"enabled": self.enabled, "mode": self.mode}
        if self.provides:
            out["causal_graph_provides"] = self.provides
        if self.uses:
            out["executor_uses"] = self.uses
        if not self.enabled:
            out["rationale"] = "Disabled — no causal structure required"
        return out


@dataclass(frozen=True)
class DataPlan:
    """Declarative data-plan template for the skill."""
    metric_types: List[str] = field(default_factory=list)
    required_data_elements: List[str] = field(default_factory=list)
    kpi_focus: List[str] = field(default_factory=list)
    transformations: List[str] = field(default_factory=list)
    dt_config: Optional[DTConfig] = None
    cce_config: Optional[CCEConfig] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataPlan":
        dt = DTConfig.from_dict(d["dt_config"]) if "dt_config" in d else None
        cce = CCEConfig.from_dict(d["cce_config"]) if "cce_config" in d else None
        return cls(
            metric_types=d.get("metric_types", []),
            required_data_elements=d.get("required_data_elements", []),
            kpi_focus=d.get("kpi_focus", []),
            transformations=d.get("transformations", []),
            dt_config=dt,
            cce_config=cce,
        )


@dataclass(frozen=True)
class RecommenderInstructions:
    """Instructions injected into the metric recommender for this skill."""
    framing: str = ""
    metric_selection_bias: str = ""
    output_guidance: str = ""
    causal_usage: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RecommenderInstructions":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class ValidatorRules:
    """Post-recommendation validation rules specific to this skill."""
    required_fields_per_metric: List[str] = field(default_factory=list)
    relevance_threshold: float = 0.55
    max_metrics: int = 14
    penalty_rules: List[str] = field(default_factory=list)
    boost_rules: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidatorRules":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Main skill class ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AnalysisSkill:
    """
    A self-contained analysis skill definition.

    Loaded from a JSON file in ``skills/definitions/``.  Each skill carries
    its own intent signals, data plan, recommender instructions, and
    validator rules — everything a data-engineer "skill" needs to execute
    an analysis type end-to-end.
    """
    skill_id: str
    display_name: str
    description: str
    category: str  # diagnostic | exploratory | predictive | operational

    intent_signals: IntentSignals = field(default_factory=IntentSignals)
    data_plan: DataPlan = field(default_factory=DataPlan)
    recommender_instructions: RecommenderInstructions = field(default_factory=RecommenderInstructions)
    validator_rules: ValidatorRules = field(default_factory=ValidatorRules)

    # Which workflows can use this skill
    workflows: List[str] = field(default_factory=lambda: ["csod", "dt"])
    executor_compatibility: List[str] = field(default_factory=list)

    # Optional domain lock — when set, skill only activates for this domain
    domain: Optional[str] = None  # e.g., "lms", "security", or None (any domain)

    # Prompt template directory (resolved at load time)
    _prompt_dir: Optional[Path] = field(default=None, repr=False)

    # ── Factories ─────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: Dict[str, Any], prompt_dir: Optional[Path] = None) -> "AnalysisSkill":
        return cls(
            skill_id=d["skill_id"],
            display_name=d["display_name"],
            description=d["description"],
            category=d.get("category", "diagnostic"),
            intent_signals=IntentSignals.from_dict(d.get("intent_signals", {})),
            data_plan=DataPlan.from_dict(d.get("data_plan", {})),
            recommender_instructions=RecommenderInstructions.from_dict(d.get("recommender_instructions", {})),
            validator_rules=ValidatorRules.from_dict(d.get("validator_rules", {})),
            workflows=d.get("workflows", ["csod", "dt"]),
            executor_compatibility=d.get("executor_compatibility", []),
            domain=d.get("domain"),
            _prompt_dir=prompt_dir,
        )

    @classmethod
    def from_json(cls, path: Path) -> "AnalysisSkill":
        """Load from a JSON definition file."""
        with open(path) as f:
            d = json.load(f)
        # Resolve prompt directory relative to the definitions/ parent
        prompts_root = path.parent.parent / "prompts" / d["skill_id"]
        return cls.from_dict(d, prompt_dir=prompts_root if prompts_root.is_dir() else None)

    # ── Prompt loading ────────────────────────────────────────────────────

    def get_prompt(self, phase: str) -> Optional[str]:
        """
        Load a prompt template for a given phase.

        Resolution order:
          1. Dedicated prompt in ``prompts/<skill_id>/<phase>.md`` (verbatim)
          2. Generic template in ``prompts/_generic/<phase>.md`` (interpolated)
          3. None

        Args:
            phase: One of 'intent_identifier', 'analysis_planner',
                   'metric_instructions', 'validator'

        Returns:
            Prompt text (possibly rendered from generic template), or None.
        """
        # 1. Check for dedicated prompt file
        if self._prompt_dir and self._prompt_dir.is_dir():
            prompt_file = self._prompt_dir / f"{phase}.md"
            if prompt_file.is_file():
                return prompt_file.read_text(encoding="utf-8")

        # 2. Fall back to generic template via renderer
        try:
            from app.agents.skills.prompt_renderer import render_skill_prompt
            return render_skill_prompt(self, phase)
        except Exception:
            return None

    # ── Legacy config export ──────────────────────────────────────────────

    def to_dt_intent_config(self) -> Optional[Dict[str, Any]]:
        """Export data_plan.dt_config to legacy DT_INTENT_CONFIG format."""
        if self.data_plan.dt_config:
            return self.data_plan.dt_config.to_intent_config_dict()
        return None

    def to_cce_intent_config(self) -> Dict[str, Any]:
        """Export data_plan.cce_config to legacy CCE_INTENT_CONFIG format."""
        if self.data_plan.cce_config:
            return self.data_plan.cce_config.to_intent_config_dict()
        return {"enabled": False, "mode": "disabled"}

    def to_catalog_entry(self) -> Dict[str, Any]:
        """Export to legacy INTENT_CATALOG_ENTRIES format."""
        entry: Dict[str, Any] = {
            "description": self.description,
            "examples": self.intent_signals.question_patterns,
            "use_cases": [],
        }
        # Merge analysis_requirements as typical_analysis_flags
        if self.intent_signals.analysis_requirements:
            entry["typical_analysis_flags"] = {
                r: True for r in self.intent_signals.analysis_requirements
            }
        return entry

    # ── Skill context for injection into prompts ──────────────────────────

    def build_skill_context_block(self) -> str:
        """Build a markdown block summarizing this skill for prompt injection."""
        lines = [
            f"## Active Skill: {self.display_name}",
            f"**Category:** {self.category}",
            f"**Description:** {self.description}",
            "",
            "### Data Requirements",
            f"- **Metric types:** {', '.join(self.data_plan.metric_types) or 'any'}",
            f"- **Required data elements:** {', '.join(self.data_plan.required_data_elements) or 'none specified'}",
            f"- **KPI focus:** {', '.join(self.data_plan.kpi_focus) or 'any'}",
        ]
        if self.data_plan.transformations:
            lines.append("")
            lines.append("### Required Transformations")
            for t in self.data_plan.transformations:
                lines.append(f"- {t}")
        if self.recommender_instructions.framing:
            lines.append("")
            lines.append("### Recommender Framing")
            lines.append(f"- **Framing:** {self.recommender_instructions.framing}")
            if self.recommender_instructions.metric_selection_bias:
                lines.append(f"- **Selection bias:** {self.recommender_instructions.metric_selection_bias}")
            if self.recommender_instructions.output_guidance:
                lines.append(f"- **Output guidance:** {self.recommender_instructions.output_guidance}")
            if self.recommender_instructions.causal_usage:
                lines.append(f"- **Causal usage:** {self.recommender_instructions.causal_usage}")
        return "\n".join(lines)
