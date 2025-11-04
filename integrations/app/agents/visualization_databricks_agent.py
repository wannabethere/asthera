"""
Vega-Lite to Databricks Visualization Agent
Produces a Databricks Lakeview dashboard-like configuration from a Vega-Lite schema
"""

from typing import Dict, List
import json
import re
from langchain_anthropic import ChatAnthropic


class VegaLiteToDatabricksVisualizationAgent:
    """Converts Vega-Lite schema to a Databricks Lakeview-style spec using simple mapping and LLM fallback."""

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
        """Convert Vega-Lite schema into a Databricks visualization widget config dict.

        Attempts LLM-based conversion; falls back to heuristic mapping.
        Optionally embeds a text_box with summary text.
        """
        chart_type = chart_schema.get("mark", {}).get("type", "bar")
        type_mapping = {
            "bar": "bar",
            "line": "line",
            "area": "area",
            "point": "scatter",
            "text": "single_value",
        }
        lakeview_type = type_mapping.get(chart_type, "table")

        # Try LLM conversion
        llm_result: Dict | None = self._llm_convert_databricks(chart_schema, business_context, actor, group)

        result: Dict = llm_result or {
            "component_id": getattr(component, "component_id", ""),
            "widget_type": lakeview_type,
            "title": chart_schema.get("title", ""),
            "fields": self._extract_fields(chart_schema),
            "options": self._extract_options(chart_schema),
        }

        # Attach a text box for summaries
        text = self._resolve_summary_text(summary_text, component, chart_schema)
        if text:
            result["text_box"] = {
                "text": text,
                "position": {"x": 0, "y": 0, "w": 12, "h": 6},
                "style": {"fontSize": 12}
            }

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

    def _extract_fields(self, chart_schema: Dict) -> Dict:
        encoding = chart_schema.get("encoding", {})
        return {
            "x": encoding.get("x", {}).get("field", ""),
            "y": encoding.get("y", {}).get("field", ""),
            "color": encoding.get("color", {}).get("field", ""),
            "size": encoding.get("size", {}).get("field", ""),
            "tooltip": encoding.get("tooltip", {}),
        }

    def _extract_options(self, chart_schema: Dict) -> Dict:
        encoding = chart_schema.get("encoding", {})
        return {
            "x_axis": encoding.get("x", {}).get("axis", {}),
            "y_axis": encoding.get("y", {}).get("axis", {}),
            "legend": encoding.get("color", {}).get("legend", {}),
        }

    def _llm_convert_databricks(self, chart_schema: Dict, business_context: Dict | str | None, actor: str | None, group: str | None) -> Dict | None:
        """Ask LLM to produce a Lakeview-style widget config from Vega-Lite.

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
                "You are a Databricks Lakeview expert. Convert the following Vega-Lite JSON into a Lakeview widget configuration.\n"
                "Output strict JSON only, with keys: widget_type, title, fields, options.\n"
                "- widget_type: one of bar, line, area, scatter, table, single_value.\n"
                "- fields: {x, y, color, size, tooltip}.\n"
                "- options: {x_axis, y_axis, legend}.\n"
                "Use the business context, actor, and group to inform widget_type and fields when ambiguous.\n"
                "Do not include explanations.\n\n"
                f"{context_block}"
                f"VegaLite:\n{json.dumps(chart_schema, ensure_ascii=False)}"
            )
            response = self.llm.invoke(prompt)
            content = getattr(response, "content", None) or (response if isinstance(response, str) else None)
            if not content:
                return None
            json_text = self._extract_json_text(content)
            if not json_text:
                return None
            data = json.loads(json_text)
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    def _extract_json_text(self, text: str) -> str | None:
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if fence_match:
            return fence_match.group(1)
        brace_match = re.search(r"\{[\s\S]*\}", text)
        return brace_match.group(0) if brace_match else None

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


