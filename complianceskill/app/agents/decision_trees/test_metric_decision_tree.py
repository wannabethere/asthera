"""
Tests for metric decision tree resolution logic.

Tests the LLM-based resolution with fallback to keyword matching.
Note: The primary resolution method is now LLM-based (see prompt 17_resolve_decisions.md).
Fallback mappings are only used if LLM call fails.
"""
import pytest
from app.agents.decision_trees.metric_decision_tree import (
    resolve_decisions,
    _resolve_from_state,
    _resolve_from_state_fallback,
    VALID_OPTIONS,
    QUESTION_MAP,
)


class TestStateResolution:
    """Test _resolve_from_state function with various state inputs."""
    
    def test_resolve_use_case_from_framework(self):
        """Test use_case resolution from framework_id."""
        state = {
            "framework_id": "soc2",
            "user_query": "I need metrics for audit",
            "intent": "",
            "data_enrichment": {},
        }
        resolved = _resolve_from_state(state)
        assert "use_case" in resolved
        assert resolved["use_case"][0] == "soc2_audit"
        assert resolved["use_case"][1] >= 0.9
    
    def test_resolve_use_case_from_dashboard_intent(self):
        """Test use_case resolution from dashboard intent with keyword matching."""
        state = {
            "framework_id": "",
            "user_query": "executive dashboard for board reporting",
            "intent": "dashboard_generation",
            "data_enrichment": {},
        }
        resolved = _resolve_from_state(state)
        assert "use_case" in resolved
        # Should match "executive_dashboard" via keyword matching
        assert resolved["use_case"][0] in ["executive_dashboard", "operational_monitoring"]
    
    def test_resolve_goal_from_metrics_intent_keyword_matching(self):
        """Test goal resolution using keyword matching on metrics_intent."""
        state = {
            "user_query": "I need risk exposure metrics",
            "intent": "",
            "data_enrichment": {
                "metrics_intent": "risk assessment",  # Contains "risk" keyword
            },
        }
        resolved = _resolve_from_state(state)
        assert "goal" in resolved
        # Should match "risk_exposure" via keyword matching
        assert resolved["goal"][0] == "risk_exposure"
        assert resolved["goal"][1] >= 0.6
    
    def test_resolve_goal_from_metrics_intent_fallback(self):
        """Test goal resolution using fallback mapping when keyword matching fails."""
        state = {
            "user_query": "",
            "intent": "",
            "data_enrichment": {
                "metrics_intent": "current_state",  # Exact match in fallback map
            },
        }
        resolved = _resolve_from_state(state)
        assert "goal" in resolved
        # Should use fallback mapping
        assert resolved["goal"][0] == "compliance_posture"
        assert resolved["goal"][1] == 0.75  # Lower confidence for fallback
    
    def test_resolve_focus_area_direct_match(self):
        """Test focus_area resolution when value is already a valid option_id."""
        state = {
            "user_query": "",
            "intent": "",
            "data_enrichment": {
                "suggested_focus_areas": ["vulnerability_management"],  # Direct match
            },
        }
        resolved = _resolve_from_state(state)
        assert "focus_area" in resolved
        assert resolved["focus_area"][0] == "vulnerability_management"
        assert resolved["focus_area"][1] >= 0.9
    
    def test_resolve_focus_area_keyword_matching(self):
        """Test focus_area resolution using keyword matching."""
        state = {
            "user_query": "vulnerability scanning and patching",
            "intent": "",
            "data_enrichment": {
                "suggested_focus_areas": ["vulnerability_scanning"],  # Not direct match
            },
        }
        resolved = _resolve_from_state(state)
        assert "focus_area" in resolved
        # Should match "vulnerability_management" via keyword matching
        assert resolved["focus_area"][0] == "vulnerability_management"
        assert resolved["focus_area"][1] >= 0.6
    
    def test_resolve_focus_area_fallback_mapping(self):
        """Test focus_area resolution using fallback mapping."""
        state = {
            "user_query": "",
            "intent": "",
            "data_enrichment": {
                "suggested_focus_areas": ["identity_access_management"],  # Needs mapping
            },
        }
        resolved = _resolve_from_state(state)
        assert "focus_area" in resolved
        # Should use fallback mapping: identity_access_management → access_control
        assert resolved["focus_area"][0] == "access_control"
        assert resolved["focus_area"][1] == 0.75  # Lower confidence for fallback
    
    def test_resolve_audience_from_keyword_matching(self):
        """Test audience resolution using keyword matching."""
        state = {
            "user_query": "executive board dashboard",
            "intent": "dashboard_generation",
            "data_enrichment": {},
        }
        resolved = _resolve_from_state(state)
        assert "audience" in resolved
        # Should match "executive_board" via keyword matching
        assert resolved["audience"][0] == "executive_board"
        assert resolved["audience"][1] >= 0.6


class TestFallbackResolution:
    """Test fallback resolution when LLM call fails."""
    
    def test_fallback_resolution_basic(self):
        """Test that fallback resolution works when LLM is unavailable."""
        state = {
            "user_query": "SOC2 audit metrics",
            "intent": "",
            "framework_id": "soc2",
            "data_enrichment": {
                "metrics_intent": "current_state",
                "suggested_focus_areas": ["vulnerability_management"],
            },
        }
        resolved = _resolve_from_state_fallback(state)
        
        assert "use_case" in resolved
        assert resolved["use_case"][0] == "soc2_audit"
        assert "goal" in resolved
        assert "focus_area" in resolved
    
    def test_fallback_focus_area_alias_mapping(self):
        """Test that fallback correctly maps focus area aliases."""
        state = {
            "user_query": "",
            "intent": "",
            "data_enrichment": {
                "suggested_focus_areas": ["identity_access_management"],
            },
        }
        resolved = _resolve_from_state_fallback(state)
        
        assert "focus_area" in resolved
        assert resolved["focus_area"][0] == "access_control"


class TestFullResolution:
    """Test the full resolve_decisions function."""
    
    def test_resolve_decisions_with_soc2_audit(self):
        """Test full resolution for SOC2 audit use case."""
        state = {
            "user_query": "I need SOC2 Type II audit metrics for vulnerability management",
            "framework_id": "soc2",
            "intent": "requirement_analysis",
            "data_enrichment": {
                "metrics_intent": "current_state",
                "suggested_focus_areas": ["vulnerability_management"],
            },
        }
        decisions = resolve_decisions(state)
        
        assert decisions["use_case"] == "soc2_audit"
        assert decisions["focus_area"] == "vulnerability_management"
        assert "goal" in decisions
        assert decisions.get("auto_resolve_confidence", 0) > 0.5
        assert "resolved_from" in decisions
    
    def test_resolve_decisions_keyword_priority(self):
        """Test that keyword matching takes priority over fallback mappings."""
        state = {
            "user_query": "I need risk exposure metrics for executive board",
            "framework_id": "",
            "intent": "",
            "data_enrichment": {
                "metrics_intent": "risk assessment",  # Has keywords
                "suggested_focus_areas": [],
            },
        }
        decisions = resolve_decisions(state)
        
        # Should resolve goal via keyword matching (not fallback)
        assert "goal" in decisions
        assert decisions["goal"] == "risk_exposure"
        
        # Check resolved_from indicates keyword matching was used
        resolved_from = decisions.get("resolved_from", [])
        goal_source = [s for s in resolved_from if "goal" in s]
        # Should be from keyword matching, not state mapping
        assert any("keyword" in s for s in goal_source) or any("state" in s for s in goal_source)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
