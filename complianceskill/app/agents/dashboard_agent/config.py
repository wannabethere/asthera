"""
CCE Layout Advisor — Configuration
===================================
Configuration schema for the layout agent. Passed at session start to control
dashboard goals, summary writer persona, business context, and constraints.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LayoutAdvisorConfig:
    """
    Configuration for the Layout Advisor agent.
    Controls how the agent interprets goals, writes summaries, and constrains output.
    """

    # Dashboard goals — what the dashboard should accomplish (used in prompts)
    dashboard_goals: list[str] = field(default_factory=lambda: ["Communicate compliance posture", "Surface key metrics"])

    # Summary writer persona — tone and audience for generated text
    # e.g. "auditor", "executive", "technical_analyst", "grc_manager"
    summary_writer_persona: str = "auditor"

    # Business context — freeform text about the organization, industry, or constraints
    business_context: str = ""

    # Maximum summary length (characters) for any generated text (rationale, strip labels, etc.)
    max_summary_length: int = 500

    # Maximum strip cell label length
    max_strip_label_length: int = 40

    # Whether to enable the data-tables human-in-the-loop (user can ask to add data)
    enable_data_tables_hitl: bool = True

    # Default output format when not specified by upstream
    default_output_format: str = "echarts"

    # Spec generation: when False, re-raise LLM/parse errors instead of using deterministic fallback.
    # Set False for demos/tests to ensure real LLM calls; True for production resilience.
    spec_gen_use_fallback_on_error: bool = True

    # LLM model for spec generation (passed to ChatAnthropic)
    spec_gen_model: str = "claude-sonnet-4-5-20250514"
    spec_gen_temperature: float = 0.1

    def to_dict(self) -> dict:
        """Serialize config for state/prompts."""
        return {
            "dashboard_goals": self.dashboard_goals,
            "summary_writer_persona": self.summary_writer_persona,
            "business_context": self.business_context,
            "max_summary_length": self.max_summary_length,
            "max_strip_label_length": self.max_strip_label_length,
            "enable_data_tables_hitl": self.enable_data_tables_hitl,
            "default_output_format": self.default_output_format,
            "spec_gen_use_fallback_on_error": self.spec_gen_use_fallback_on_error,
            "spec_gen_model": self.spec_gen_model,
            "spec_gen_temperature": self.spec_gen_temperature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LayoutAdvisorConfig:
        """Build config from dict (e.g. API payload)."""
        return cls(
            dashboard_goals=d.get("dashboard_goals", ["Communicate compliance posture", "Surface key metrics"]),
            summary_writer_persona=d.get("summary_writer_persona", "auditor"),
            business_context=d.get("business_context", ""),
            max_summary_length=int(d.get("max_summary_length", 500)),
            max_strip_label_length=int(d.get("max_strip_label_length", 40)),
            enable_data_tables_hitl=bool(d.get("enable_data_tables_hitl", True)),
            default_output_format=d.get("default_output_format", "echarts"),
            spec_gen_use_fallback_on_error=bool(d.get("spec_gen_use_fallback_on_error", True)),
            spec_gen_model=str(d.get("spec_gen_model", "claude-sonnet-4-5-20250514")),
            spec_gen_temperature=float(d.get("spec_gen_temperature", 0.1)),
        )
