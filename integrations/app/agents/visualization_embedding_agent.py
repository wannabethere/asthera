"""
Vega-Lite to Embedding Visualization Agent
Produces a compact textual/JSON representation of a Vega-Lite chart suitable for embeddings
"""

from typing import Dict, List
import json
import re
from langchain_anthropic import ChatAnthropic


class VegaLiteToEmbeddingVisualizationAgent:
    """Converts Vega-Lite schema to a normalized text/JSON summary for embedding indexes."""

    def __init__(self, llm: ChatAnthropic | None = None):
        self.llm = llm or ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0)

    def convert(
        self,
        chart_schema: Dict,
        component: object | None = None,
        summary_text: str | None = None,
        business_context: Dict | str | None = None,
        actor: str | None = None,
        group: str | None = None,
    ) -> Dict:
        """Return an embedding-friendly payload summarizing the visualization intent and fields.

        Attempts LLM-based normalized summary; falls back to heuristic summary.
        Optionally includes a text_box with summary text for downstream UIs.
        """
        # LLM summary first
        llm_summary = self._llm_summarize(chart_schema, business_context, actor, group)
        summary = llm_summary or self._summarize(chart_schema)
        # Allow explicit override or component/schema-sourced executive overview
        resolved_summary = self._resolve_summary_text(summary_text, component, chart_schema) or summary

        fields = self._extract_fields(chart_schema)

        result: Dict = {
            "component_id": getattr(component, "component_id", ""),
            "title": chart_schema.get("title", ""),
            "summary_text": resolved_summary,
            "fields": fields,
            "vega_lite_mark": chart_schema.get("mark", {}),
        }

        if resolved_summary:
            result["text_box"] = {
                "text": resolved_summary,
                "position": {"x": 0, "y": 0, "w": 12, "h": 6},
                "style": {"fontSize": 12}
            }

        # Attach meta context if provided
        meta: Dict = {}
        if business_context is not None:
            meta["business_context"] = business_context
        if actor:
            meta["actor"] = actor
        if group:
            meta["group"] = group
        if meta:
            result["meta"] = meta

        return result

    def _extract_fields(self, chart_schema: Dict) -> List[Dict]:
        encoding = chart_schema.get("encoding", {})
        results: List[Dict] = []
        for channel, config in encoding.items():
            results.append({
                "channel": channel,
                "field": config.get("field", ""),
                "type": config.get("type", ""),
                "aggregate": config.get("aggregate", ""),
            })
        return results

    def _summarize(self, chart_schema: Dict) -> str:
        mark_type = chart_schema.get("mark", {}).get("type", "unknown")
        title = chart_schema.get("title", "")
        encoding = chart_schema.get("encoding", {})
        dims = [cfg.get("field", "") for ch, cfg in encoding.items() if cfg.get("type") in {"nominal", "ordinal", "temporal"}]
        meas = [cfg.get("field", "") for ch, cfg in encoding.items() if cfg.get("type") in {"quantitative"}]

        parts = [
            f"Chart: {mark_type}",
            f"Title: {title}" if title else "",
            f"Dimensions: {', '.join([d for d in dims if d])}" if dims else "",
            f"Measures: {', '.join([m for m in meas if m])}" if meas else "",
        ]
        return "; ".join([p for p in parts if p])

    def _llm_summarize(self, chart_schema: Dict, business_context: Dict | str | None, actor: str | None, group: str | None) -> str | None:
        """Use LLM to produce a compact, normalized summary string for embeddings.

        Returns a string on success, otherwise None.
        """
        if not self.llm:
            return None
        try:
            context_block = ""
            if business_context is not None or actor or group:
                context_dict = {
                    "business_context": business_context,
                    "actor": actor,
                    "group": group,
                }
                context_block = "Business Context:\n" + json.dumps(context_dict, ensure_ascii=False) + "\n\n"

            prompt = (
                "Summarize the following Vega-Lite JSON into a single-line description suitable for embeddings.\n"
                "Include chart type, key dimensions, and key measures.\n"
                "Use the business context, actor, and group to phrase the summary with domain relevance.\n"
                "Output plain text only with no prefix/suffix.\n\n"
                f"{context_block}"
                f"VegaLite:\n{json.dumps(chart_schema, ensure_ascii=False)}"
            )
            response = self.llm.invoke(prompt)
            content = getattr(response, "content", None) or (response if isinstance(response, str) else None)
            if not content:
                return None
            # If model returned fenced text, strip code fences
            match = re.search(r"```(?:text|md|markdown)?\s*([\s\S]*?)\s*```", content)
            text = match.group(1) if match else content
            text = str(text).strip()
            return text or None
        except Exception:
            return None

    def _resolve_summary_text(self, summary_text: str | None, component: object | None, chart_schema: Dict) -> str | None:
        if summary_text and isinstance(summary_text, str) and summary_text.strip():
            return summary_text.strip()
        if component is not None:
            comp_exec = getattr(component, "executive_summary", None)
            if isinstance(comp_exec, str) and comp_exec.strip():
                return comp_exec.strip()
            comp_overview = getattr(component, "overview", None)
            if isinstance(comp_overview, dict):
                text = comp_overview.get("overview")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        schema_overview = chart_schema.get("overview")
        if isinstance(schema_overview, dict):
            text = schema_overview.get("overview")
            if isinstance(text, str) and text.strip():
                return text.strip()
        return None


