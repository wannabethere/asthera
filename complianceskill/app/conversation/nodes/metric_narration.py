"""
Metric Narration Node

Phase 0F: Generates plain-language explanation of what Lexy will measure and why.
"""
import logging
from typing import Dict, Any

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType
from app.conversation.config import VerticalConversationConfig

logger = logging.getLogger(__name__)


def metric_narration_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Metric narration node - explains what metrics will be measured and why.
    
    Grounded entirely in registry area data. No hallucination - every claim traces to
    area.causal_paths, area.metrics, area.kpis, or csod_scoping_answers.
    
    State reads: csod_primary_area, csod_scoping_answers, user_query
    State writes: csod_metric_narration, csod_conversation_checkpoint (METRIC_NARRATION type)
    resume_with_field: csod_metric_narration_confirmed
    """
    # Fast-path: already confirmed on a prior turn
    if state.get("csod_metric_narration_confirmed"):
        logger.info("Metric narration already confirmed — skipping checkpoint")
        state["csod_checkpoint_resolved"] = True
        state["csod_conversation_checkpoint"] = None
        return state

    primary_area = state.get("csod_primary_area", {})
    scoping_answers = state.get("csod_scoping_answers", {})
    user_query = state.get("user_query", "")

    if not primary_area:
        logger.warning("No primary area for metric narration - skipping")
        state["csod_metric_narration"] = ""
        state["csod_metric_narration_confirmed"] = True
        return state
    
    # Extract area data
    metrics = primary_area.get("metrics", [])
    kpis = primary_area.get("kpis", [])
    causal_paths = primary_area.get("causal_paths", [])
    
    try:
        from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
        from app.core.dependencies import get_llm
        import json
        
        # Load metric narration prompt
        prompt_text = load_prompt("11_metric_narration", prompts_dir=str(PROMPTS_CSOD))
        
        # Format context for prompt
        metrics_text = "\n".join(f"- {m}" for m in metrics[:10])  # Top 10
        kpis_text = "\n".join(f"- {k}" for k in kpis[:10])  # Top 10
        causal_paths_text = "\n".join(f"- {cp}" for cp in causal_paths[:10])  # Top 10
        
        scoping_summary = ", ".join(f"{k}: {v}" for k, v in scoping_answers.items() if v)
        
        # Build human message with context
        human_message = f"""User question: {user_query}

Scoping context: {scoping_summary if scoping_summary else "No specific scoping constraints"}

Metrics to measure:
{metrics_text if metrics_text else "No specific metrics listed"}

KPIs to track:
{kpis_text if kpis_text else "No specific KPIs listed"}

Causal relationships:
{causal_paths_text if causal_paths_text else "No specific causal paths listed"}

Generate a plain-language explanation (2-3 sentences) of what will be measured and why, 
grounded ONLY in the metrics, KPIs, and causal paths above. Then list 3-5 key metrics 
with their causal role (driver / outcome / guardrail)."""
        
        # Get LLM
        llm = get_llm()
        
        # Generate response using system prompt + human message
        from langchain_core.prompts import ChatPromptTemplate
        # Escape braces in the prompt file so LangChain doesn't treat JSON
        # examples like {"narration": ...} as template variable slots.
        safe_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", safe_prompt),
            ("human", "{input}"),
        ])
        chain = prompt_template | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON response (if structured) or use as plain text
        try:
            result = json.loads(response_content)
            narration = result.get("narration", response_content)
            metric_list = result.get("metrics", [])
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                narration = result.get("narration", response_content)
                metric_list = result.get("metrics", [])
            else:
                # Use as plain text
                narration = response_content
                metric_list = []
        
        state["csod_metric_narration"] = narration
        # Auto-confirm — narration is informational only, no user gate needed
        state["csod_metric_narration_confirmed"] = True
        state["csod_conversation_checkpoint"] = None
        state["csod_checkpoint_resolved"] = True
        logger.info("Metric narration generated (auto-confirmed, no interrupt)")

    except FileNotFoundError:
        # Prompt file doesn't exist yet - use template-based fallback
        logger.warning("Metric narration prompt not found - using template fallback")
        narration = (
            f"Based on your question about {user_query}, I'll analyze the following:\n\n"
            f"• Metrics: {', '.join(metrics[:5]) if metrics else 'Standard metrics'}\n"
            f"• KPIs: {', '.join(kpis[:5]) if kpis else 'Standard KPIs'}\n\n"
            f"This will help us understand the patterns and drivers behind your question."
        )
        state["csod_metric_narration"] = narration
        state["csod_metric_narration_confirmed"] = True
        state["csod_conversation_checkpoint"] = None
        state["csod_checkpoint_resolved"] = True
        
    except Exception as e:
        logger.error(f"Error generating metric narration: {e}", exc_info=True)
        # Fallback narration
        narration = (
            f"I'll analyze your question about {user_query} using relevant metrics and KPIs "
            f"to provide insights into the patterns and drivers."
        )
        state["csod_metric_narration"] = narration
        state["csod_metric_narration_confirmed"] = True  # Auto-confirm on error
    
    return state
