#!/usr/bin/env python3
"""
Run the recommendation layout flow using examples/outputs data.
Loads metric_recommendations.json and generated_gold_model_sql.json.

Uses app.core.settings and app.core.dependencies (get_llm) for LLM config.
Supports OpenAI or Anthropic per LLM_PROVIDER. The demo is configured to fail
if the LLM path does not run (no fallback to deterministic spec).

Run from complianceskill dir:
  python examples/run_recommendation_layout_demo.py

Configure via .env: OPENAI_API_KEY (or ANTHROPIC_API_KEY), LLM_MODEL, LLM_TEMPERATURE, LLM_PROVIDER

Writes full output to examples/outputs/recommendation_layout_output.json
"""
import json
import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

OUTPUTS_DIR = base_dir / "examples" / "outputs"
OUTPUT_FILE = OUTPUTS_DIR / "recommendation_layout_output.json"


def _require_llm_config():
    """Ensure LLM is configured via settings — demo requires real LLM calls."""
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        # Spec generation uses get_llm from dependencies (OpenAI or Anthropic per LLM_PROVIDER)
        has_key = bool(settings.OPENAI_API_KEY) or bool(settings.ANTHROPIC_API_KEY)
        if not has_key:
            print("ERROR: LLM API key is required for this demo.")
            print("  Configure via .env: OPENAI_API_KEY=sk-... or ANTHROPIC_API_KEY=sk-...")
            print("  Use LLM_PROVIDER=openai or anthropic to select provider.")
            print("  The demo uses spec_gen_use_fallback_on_error=False to ensure LLM calls.")
            sys.exit(1)
    except ImportError as e:
        print(f"ERROR: Could not load settings: {e}")
        print("  Ensure app.core.settings is available.")
        sys.exit(1)


def _serialize(obj):
    """Make state JSON-serializable (Phase enums, etc)."""
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return obj


def main():
    _require_llm_config()

    from app.agents.dashboard_agent import LayoutAdvisorSession, LayoutAdvisorConfig
    from app.core.settings import get_settings

    settings = get_settings()
    metric_path = OUTPUTS_DIR / "metric_recommendations.json"
    gold_path = OUTPUTS_DIR / "generated_gold_model_sql.json"
    if not metric_path.exists() or not gold_path.exists():
        print(f"Missing outputs: {metric_path} or {gold_path}")
        sys.exit(1)

    with open(metric_path) as f:
        metric_recs = json.load(f)[:8]
    with open(gold_path) as f:
        gold_sql = json.load(f)[:5]

    print("=" * 72)
    print("  CCE LAYOUT ADVISOR — Recommendation Layout (from examples/outputs)")
    print("=" * 72)
    print(f"  Metrics: {len(metric_recs)} | Gold models: {len(gold_sql)}")

    # Use settings for spec gen (LLM_MODEL, LLM_PROVIDER from .env)
    spec_model = settings.LLM_MODEL
    config = LayoutAdvisorConfig(
        dashboard_goals=["Vulnerability management dashboard"],
        summary_writer_persona="security_ops",
        max_summary_length=400,
        enable_data_tables_hitl=False,
        spec_gen_use_fallback_on_error=False,  # Require real LLM calls — fail if spec falls back
        spec_gen_model=spec_model,
        spec_gen_temperature=settings.LLM_TEMPERATURE,
    )
    upstream = {
        "metric_recommendations": metric_recs,
        "gold_model_sql": gold_sql,
        "goal_statement": "Vulnerability management dashboard",
        "output_format": "echarts",
    }
    session = LayoutAdvisorSession(agent_config=config)

    # Run step-by-step, capturing each turn
    steps = []
    response = session.start(upstream)
    step_num = 0

    while not response.is_complete and response.needs_input and step_num < 50:
        step_num += 1
        step = {
            "step": step_num,
            "phase": response.phase,
            "agent_message": response.agent_message,
            "options": response.options,
            "recommended": response.recommended,
        }
        steps.append(step)
        print(f"\n--- Step {step_num}: {response.phase} ---")
        print(response.agent_message[:500] + ("..." if len(response.agent_message) > 500 else ""))
        if response.options:
            print(f"  Options: {response.options[:3]}...")
        if response.recommended:
            print(f"  Recommended: {[r.get('name') for r in response.recommended[:3]]}")

        # Pick next input
        if response.phase == "selection" and response.recommended:
            user_msg = "1"
        elif response.phase == "data_tables":
            user_msg = "skip"
        elif response.options:
            user_msg = response.options[0]
        else:
            user_msg = "looks good"
        print(f"  → Sending: {user_msg!r}")
        step["user_input"] = user_msg
        response = session.respond(user_msg)

    print(f"\n--- Final: {response.phase} (complete={response.is_complete}) ---")

    # Build full output
    full_state = _serialize(session.get_state())
    output = {
        "steps": steps,
        "final_phase": response.phase,
        "is_complete": response.is_complete,
        "layout_spec": response.layout_spec,
        "full_state": full_state,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ Full output written to {OUTPUT_FILE}")

    if response.layout_spec:
        print(f"\n  Template: {response.layout_spec.get('template_name', '?')}")
        print(f"  Output format: {response.layout_spec.get('output_format', 'echarts')}")
        if response.layout_spec.get("_fallback"):
            print("\n  ERROR: Spec was generated by fallback (LLM did not run). Expected real LLM output.")
            sys.exit(1)
    else:
        print(f"\n  Stopped at phase: {response.phase}")


if __name__ == "__main__":
    main()
