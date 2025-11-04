"""
Vega-Lite to Tableau Visualization Agent
Produces a Tableau worksheet/dashboard-friendly configuration from a Vega-Lite schema
"""

from typing import Dict, List
import json
import re
from langchain_anthropic import ChatAnthropic


class VegaLiteToTableauVisualizationAgent:
    """Converts Vega-Lite chart schema to a Tableau-oriented visualization spec using simple mapping and LLM fallback."""

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
        """Convert Vega-Lite schema into a Tableau worksheet-style config dict.

        Attempts LLM-based conversion; falls back to heuristic mapping.
        Optionally embeds a text_box with summary text.
        """
        worksheet_type = chart_schema.get("mark", {}).get("type", "bar")
        shelves = self._extract_shelves(chart_schema)

        # Try LLM conversion
        llm_result: Dict | None = self._llm_convert_tableau(chart_schema, business_context, actor, group)

        result: Dict = llm_result or {
            "component_id": getattr(component, "component_id", ""),
            "worksheet_type": worksheet_type,
            "title": chart_schema.get("title", ""),
            "shelves": shelves,
            "encodings": self._extract_encodings(chart_schema),
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

    def _extract_shelves(self, chart_schema: Dict) -> Dict:
        encoding = chart_schema.get("encoding", {})
        shelves = {"rows": [], "columns": [], "marks": "automatic"}
        if "x" in encoding:
            shelves["columns"].append(encoding["x"].get("field", ""))
        if "y" in encoding:
            shelves["rows"].append(encoding["y"].get("field", ""))
        return shelves

    def _extract_encodings(self, chart_schema: Dict) -> List[Dict]:
        encoding = chart_schema.get("encoding", {})
        encs = []
        for channel, config in encoding.items():
            encs.append({
                "channel": channel,
                "field": config.get("field", ""),
                "type": config.get("type", ""),
                "aggregate": config.get("aggregate", ""),
                "bin": config.get("bin", False),
                "timeUnit": config.get("timeUnit", ""),
            })
        return encs

    def _llm_convert_tableau(self, chart_schema: Dict, business_context: Dict | str | None, actor: str | None, group: str | None) -> Dict | None:
        """Ask the LLM to produce a Tableau-oriented config from the Vega-Lite schema.

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
                "You are a Tableau expert. Convert the following Vega-Lite JSON into a Tableau worksheet-style configuration.\n"
                "Output strict JSON only, with keys: worksheet_type, title, shelves (rows[], columns[], marks), encodings[].\n"
                "- encodings: array of {channel, field, type, aggregate, bin, timeUnit}.\n"
                "Use the business context, actor, and group to inform shelf placement and mark type when ambiguous.\n"
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
        """Extract the first JSON object from LLM text."""
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


