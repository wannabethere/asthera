"""
Vega-Lite to PowerBI Visualization Agent
Produces a PowerBI visual configuration from a Vega-Lite schema
"""

from typing import Dict, List
import json
import re
from langchain_anthropic import ChatAnthropic


class VegaLiteToPowerBIVisualizationAgent:
    """Converts Vega-Lite chart schema to a PowerBI visual configuration using simple mapping and LLM fallback."""

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
        """Convert Vega-Lite schema into a PowerBI visual config dict.

        Attempts LLM-based conversion; falls back to heuristic mapping.
        Optionally embeds a text_box with summary text (e.g., executive summary/overview).
        """
        chart_type = chart_schema.get("mark", {}).get("type", "bar")

        type_mapping = {
            "bar": "clusteredBarChart",
            "line": "lineChart",
            "point": "scatterChart",
            "text": "card",
            "area": "areaChart",
            "tick": "columnChart",
        }

        powerbi_type = type_mapping.get(chart_type, "table")

        # Try LLM conversion first
        llm_result: Dict | None = self._llm_convert_powerbi(chart_schema, business_context, actor, group)

        # Fallback basic mapping
        result: Dict = llm_result or {
            "component_id": getattr(component, "component_id", ""),
            "visual_type": powerbi_type,
            "title": chart_schema.get("title", ""),
            "config": {
                "dataRoles": self._extract_data_roles(chart_schema),
                "properties": self._extract_properties(chart_schema),
            },
        }

        # Attach a text box for summaries (e.g., executive summary or overview)
        text = self._resolve_summary_text(summary_text, component, chart_schema)
        if text:
            result["text_box"] = {
                "text": text,
                # Provide a sane default placement/size; downstream can override
                "position": {"x": 0, "y": 0, "w": 12, "h": 6},
                "style": {"fontSize": 12}
            }

        # Ensure component id is present even if produced by LLM
        if "component_id" not in result:
            result["component_id"] = getattr(component, "component_id", "")

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

    def _extract_data_roles(self, chart_schema: Dict) -> List[Dict]:
        encoding = chart_schema.get("encoding", {})
        roles = []
        for channel, config in encoding.items():
            roles.append({
                "name": channel,
                "field": config.get("field", ""),
                "type": config.get("type", ""),
                "aggregate": config.get("aggregate", ""),
            })
        return roles

    def _extract_properties(self, chart_schema: Dict) -> Dict:
        return {
            "title": chart_schema.get("title", ""),
            "legend": chart_schema.get("encoding", {}).get("color", {}),
            "axis": {
                "x": chart_schema.get("encoding", {}).get("x", {}).get("axis", {}),
                "y": chart_schema.get("encoding", {}).get("y", {}).get("axis", {}),
            },
        }

    def _llm_convert_powerbi(self, chart_schema: Dict, business_context: Dict | str | None, actor: str | None, group: str | None) -> Dict | None:
        """Ask the LLM to produce a PowerBI-oriented config from the Vega-Lite schema.

        Returns parsed dict on success, otherwise None.
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
                "You are a data visualization engineer. Convert the following Vega-Lite JSON into a PowerBI visual configuration.\n"
                "Output strict JSON only, with keys: visual_type, title, config (with dataRoles[], properties{}).\n"
                "- visual_type should be a PowerBI visual id (e.g., clusteredBarChart, lineChart, scatterChart, table, card, areaChart, columnChart).\n"
                "- config.dataRoles: array of {name, field, type, aggregate}.\n"
                "- config.properties: {title, legend, axis: {x, y}}.\n"
                "Use the business context, actor, and group to select appropriate encodings and defaults when ambiguous.\n"
                "Do not include explanations.\n\n"
                f"{context_block}"
                f"VegaLite:\n{json.dumps(chart_schema, ensure_ascii=False)}"
            )
            response = self.llm.invoke(prompt)  # LangChain ChatAnthropic compatible
            content = getattr(response, "content", None) or (response if isinstance(response, str) else None)
            if not content:
                return None
            json_text = self._extract_json_text(content)
            if not json_text:
                return None
            data = json.loads(json_text)
            # Light sanity
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    def _extract_json_text(self, text: str) -> str | None:
        """Extract the first JSON object from LLM text."""
        # Try fenced code block first
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if fence_match:
            return fence_match.group(1)
        # Fallback: first object-like substring
        brace_match = re.search(r"\{[\s\S]*\}", text)
        return brace_match.group(0) if brace_match else None

    def _resolve_summary_text(self, summary_text: str | None, component: object | None, chart_schema: Dict) -> str | None:
        """Resolve a summary string from provided sources.

        Priority:
        1) explicit summary_text arg
        2) component.executive_summary
        3) component.overview["overview"] if dict-like
        4) chart_schema["overview"]["overview"] if present
        """
        if summary_text and isinstance(summary_text, str) and summary_text.strip():
            return summary_text.strip()
        if component is not None:
            # executive_summary directly on component
            comp_exec = getattr(component, "executive_summary", None)
            if isinstance(comp_exec, str) and comp_exec.strip():
                return comp_exec.strip()
            # overview may be a dict with key "overview" per render payload
            comp_overview = getattr(component, "overview", None)
            if isinstance(comp_overview, dict):
                text = comp_overview.get("overview")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        # check chart_schema for embedded overview
        schema_overview = chart_schema.get("overview")
        if isinstance(schema_overview, dict):
            text = schema_overview.get("overview")
            if isinstance(text, str) and text.strip():
                return text.strip()
        return None


