"""
Chart Spec Store — Storage & Retrieval for LLM Chart Selection
===============================================================
Provides two modes:
  1. JSON file store — dump full catalog as JSON for direct LLM context
  2. Vector store — semantic search for "find the right chart" queries

The LLM workflow:
  User describes what they want → Search spec store → Get matching chart templates
  → LLM fills in the IntentSpec with actual data fields → Compiler generates option
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from chart_catalog import (
    CHART_CATALOG,
    INTENT_CHART_MAP,
    get_catalog_embedding_text,
    get_charts_by_intent,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# JSON STORE — For direct LLM context injection
# ═══════════════════════════════════════════════════════════════════════

class ChartSpecJsonStore:
    """
    Manages the chart catalog as JSON files for LLM context.
    
    Two outputs:
      1. Full catalog JSON — all chart specs with examples
      2. Compact prompt reference — minimal schema for system prompts
    """

    @staticmethod
    def export_full_catalog(path: str = "chart_catalog.json") -> str:
        """Export the full catalog as JSON."""
        with open(path, "w") as f:
            json.dump(CHART_CATALOG, f, indent=2, default=str)
        logger.info(f"Exported {len(CHART_CATALOG)} chart specs to {path}")
        return path

    @staticmethod
    def export_prompt_reference(path: str = "chart_prompt_reference.json") -> str:
        """
        Export a compact reference for LLM system prompts.
        Includes: id, name, family, intent, description, when_to_use,
        required encodings, and a minimal example.
        """
        compact = {}
        for cid, chart in CHART_CATALOG.items():
            compact[cid] = {
                "name": chart["name"],
                "family": chart["family"],
                "intent": chart["intent"],
                "description": chart["description"],
                "when_to_use": chart["when_to_use"],
                "encoding_required": chart["encoding_required"],
                "encoding_optional": chart.get("encoding_optional", {}),
                "example_spec": chart.get("example_spec"),
            }

        with open(path, "w") as f:
            json.dump(compact, f, indent=2, default=str)
        logger.info(f"Exported compact reference ({len(compact)} charts) to {path}")
        return path

    @staticmethod
    def export_intent_map(path: str = "intent_chart_map.json") -> str:
        """Export the intent → chart type mapping."""
        with open(path, "w") as f:
            json.dump(INTENT_CHART_MAP, f, indent=2)
        return path

    @staticmethod
    def get_llm_prompt_context(
        intent: Optional[str] = None,
        max_charts: int = 10,
    ) -> str:
        """
        Get a formatted text block for injection into LLM prompts.
        Optionally filtered by intent.
        
        Returns a string ready to paste into a system prompt.
        """
        if intent:
            chart_ids = INTENT_CHART_MAP.get(intent, [])
            charts = [CHART_CATALOG[cid] for cid in chart_ids if cid in CHART_CATALOG]
        else:
            charts = list(CHART_CATALOG.values())[:max_charts]

        lines = [f"## Available Chart Types ({len(charts)})\n"]
        for c in charts:
            lines.append(f"### {c['name']} (`{c['family']}`)")
            lines.append(f"Intent: {', '.join(c['intent'])}")
            lines.append(f"When: {c['when_to_use']}")
            req = c.get("encoding_required", {})
            lines.append(f"Required: {', '.join(req.keys())}")
            lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# VECTOR STORE — For semantic chart retrieval
# ═══════════════════════════════════════════════════════════════════════

class ChartSpecVectorStore:
    """
    Embeds chart catalog entries into a vector store for semantic retrieval.
    
    Usage:
        store = ChartSpecVectorStore.build(embeddings)
        results = store.search("I want to show risk trends over time with grouping by department")
        # → [{"id": "line_basic", "score": 0.92, ...}, {"id": "area_stacked", ...}]
    """

    def __init__(self, vectorstore):
        self._store = vectorstore

    @classmethod
    def build(
        cls,
        embeddings,
        backend: str = "faiss",
        persist_dir: Optional[str] = None,
    ) -> "ChartSpecVectorStore":
        """Build vector store from the chart catalog."""
        from langchain_core.documents import Document

        docs = []
        for cid, chart in CHART_CATALOG.items():
            text = get_catalog_embedding_text(chart)
            metadata = {
                "chart_id": cid,
                "name": chart["name"],
                "family": chart["family"],
                "intent": json.dumps(chart["intent"]),
                "coordinate": chart["coordinate"],
                "description": chart["description"],
                "when_to_use": chart["when_to_use"],
            }
            docs.append(Document(page_content=text, metadata=metadata))

        if backend == "faiss":
            from langchain_community.vectorstores import FAISS
            store = FAISS.from_documents(docs, embeddings)
        elif backend == "chroma":
            from langchain_chroma import Chroma
            store = Chroma.from_documents(
                docs, embeddings,
                collection_name="cce_chart_catalog",
                persist_directory=persist_dir or "./chroma_charts",
            )
        else:
            raise ValueError(f"Unknown backend: {backend}")

        logger.info(f"Built {backend} chart vector store with {len(docs)} entries")
        return cls(store)

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Semantic search for chart types matching a description."""
        results = self._store.similarity_search_with_score(query, k=k)
        output = []
        for doc, score in results:
            output.append({
                "chart_id": doc.metadata["chart_id"],
                "name": doc.metadata["name"],
                "family": doc.metadata["family"],
                "intent": json.loads(doc.metadata["intent"]),
                "description": doc.metadata["description"],
                "when_to_use": doc.metadata["when_to_use"],
                "similarity_score": round(1 - score, 4) if score <= 1 else round(score, 4),
                "full_spec": CHART_CATALOG.get(doc.metadata["chart_id"]),
            })
        return output

    def search_by_intent_and_data(
        self,
        intent: str,
        data_description: str,
        k: int = 5,
    ) -> list[dict]:
        """
        Hybrid search: combine intent filtering with semantic data description matching.
        """
        query = f"Intent: {intent}. Data: {data_description}"
        return self.search(query, k=k)


# ═══════════════════════════════════════════════════════════════════════
# LLM PROMPT BUILDER — Generates the system prompt for chart selection
# ═══════════════════════════════════════════════════════════════════════

def build_chart_selection_prompt(
    available_fields: list[str],
    data_description: str = "",
    user_intent: str = "",
) -> str:
    """
    Build a system prompt for LLMs to generate EChartsIntentSpec.
    
    This is the prompt you give to Claude/GPT to produce valid specs.
    
    Args:
        available_fields: Column names from the user's dataset
        data_description: Natural language description of the data
        user_intent: What the user wants to understand
    
    Returns:
        System prompt string
    """
    chart_reference = ChartSpecJsonStore.get_llm_prompt_context(max_charts=25)

    prompt = f"""\
You are a chart specification agent. Given data fields and user intent,
you generate valid ECharts Intent Spec (EPS v1.0) JSON.

## Rules
- Output ONLY valid EPS v1.0 JSON
- Use only fields from the provided dataset
- Choose chart_family based on the intent
- Use the chart catalog below to pick the right structure
- Include semantic metadata when the metric has known thresholds
- Do NOT invent fields. Use exact field names as provided.
- Do NOT output raw ECharts option. Output EPS only.

## Available Data Fields
{json.dumps(available_fields, indent=2)}

## Data Description
{data_description}

## User Intent
{user_intent}

## Intent → Chart Family Mapping
{json.dumps(INTENT_CHART_MAP, indent=2)}

{chart_reference}

## EPS v1.0 Schema (key fields)
{{
  "version": "eps/1.0",
  "title": "string",
  "intent": "trend_over_time|compare_categories|distribution|relationship|part_to_whole|ranking|geo|flow|hierarchy|composition|deviation|correlation|status_kpi|table",
  "dataset": {{"source": "ref|inline", "ref": "string", "time_field": "string|null"}},
  "encoding": {{
    "x": {{"field": "string", "type": "time|category|value", "time_grain": "day|week|month|quarter|year|null", "sort": "asc|desc|none"}},
    "y": [{{"field": "string", "aggregate": "sum|avg|min|max|count|count_distinct|none", "axis": "left|right|null", "format": "string|null", "label": "string|null"}}],
    "series": {{"field": "string"}} | null,
    "color": {{"field": "string", "type": "dimension|measure"}} | null,
    "size": {{"field": "string", "min_size": 4, "max_size": 40}} | null,
    "source_field": "string|null (sankey/graph)",
    "target_field": "string|null (sankey/graph)",
    "value_field": "string|null"
  }},
  "visual": {{
    "chart_family": "line|area|bar|scatter|heatmap|boxplot|pie|donut|radar|gauge|funnel|treemap|sunburst|tree|sankey|graph|dual_axis|combo|kpi_card|...",
    "coordinate": "cartesian2d|polar|geo|single|parallel|none",
    "orientation": "vertical|horizontal",
    "stack": "none|stacked|percent",
    "smooth": false,
    "show_area": false,
    "show_labels": false
  }},
  "interactions": {{"tooltip": "axis|item|none", "legend": true, "data_zoom": false}},
  "semantics": {{
    "metric_id": "string|null",
    "unit": "count|pct|usd|score_0_100|days|null",
    "good_direction": "up|down|neutral",
    "thresholds": {{"critical": number, "warning": number, "good": number}} | null
  }}
}}

Generate the spec now.
"""
    return prompt
