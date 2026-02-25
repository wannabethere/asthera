"""
Common Deep Research Utility

Configuration-driven utility that:
1. Fetches data from configured URL sites (e.g. docs.snyk.io)
2. Asks LLM to extract/summarize and produce recommendations
3. Merges all information into a structured result for the assistant

Can be used by data assistance, compliance, or any assistant that needs
URL-based research. Contextual data search can be added later to enrich.
"""
import asyncio
import logging
import re
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# Default max chars per URL to avoid token overflow
DEFAULT_MAX_CONTENT_PER_URL = 40000
# Default timeout per URL (seconds)
DEFAULT_TIMEOUT_PER_URL = 15


# Goal types for deep research (drives prompt and output shape)
DEEP_RESEARCH_GOAL_DATA = "data_retrieval"
DEEP_RESEARCH_GOAL_COMPLIANCE = "compliance"


@dataclass
class DeepResearchConfig:
    """Configuration for a deep research run."""
    context_name: str
    """Short name for this context (e.g. 'Snyk data', 'Compliance')."""
    urls: List[str]
    """URLs to fetch (e.g. ['https://docs.snyk.io/product/...'])."""
    topic: Optional[str] = None
    """Optional topic description (e.g. 'Data related to Snyk')."""
    goal: str = DEEP_RESEARCH_GOAL_DATA
    """Research goal: 'data_retrieval' (features, KPIs, metrics) or 'compliance' (controls, evidence, gaps)."""
    next_node_after: Optional[str] = None
    """When set, deep research node routes to this node (e.g. 'compliance_qa' for compliance, 'metric_generation' for data)."""
    max_content_per_url: int = DEFAULT_MAX_CONTENT_PER_URL
    """Max characters to keep per URL content."""
    timeout_per_url: int = DEFAULT_TIMEOUT_PER_URL
    """Timeout in seconds per URL fetch."""
    user_agent: str = "Mozilla/5.0 (compatible; DeepResearch/1.0)"


def _strip_html(html: str) -> str:
    """Remove script/style tags and strip HTML tags to get plain text."""
    if not html:
        return ""
    # Remove script and style
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_url_sync(url: str, config: DeepResearchConfig) -> Dict[str, Any]:
    """Fetch a single URL and return {url, content, error}."""
    try:
        req = Request(url, headers={"User-Agent": config.user_agent})
        with urlopen(req, timeout=config.timeout_per_url) as resp:
            raw = resp.read()
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
            text = _strip_html(text)
            if len(text) > config.max_content_per_url:
                text = text[: config.max_content_per_url] + "\n... [truncated]"
            return {"url": url, "content": text, "error": None}
    except (URLError, HTTPError, OSError, Exception) as e:
        logger.warning(f"Deep research fetch failed for {url}: {e}")
        return {"url": url, "content": "", "error": str(e)}


async def fetch_urls(config: DeepResearchConfig) -> List[Dict[str, Any]]:
    """Fetch all URLs in config in parallel (run sync fetch in thread)."""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, _fetch_url_sync, url, config) for url in config.urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            out.append({"url": config.urls[i], "content": "", "error": str(r)})
        else:
            out.append(r)
    return out


def merge_fetched_content(fetched: List[Dict[str, Any]]) -> str:
    """Merge fetched URL contents into one blob for LLM."""
    parts = []
    for item in fetched:
        url = item.get("url", "")
        content = (item.get("content") or "").strip()
        err = item.get("error")
        if err:
            parts.append(f"[Source: {url}]\n(Fetch error: {err})\n")
        elif content:
            parts.append(f"[Source: {url}]\n{content}\n")
    return "\n---\n".join(parts) if parts else ""


# LLM output shape compatible with deep_research_review
DEEP_RESEARCH_SYSTEM = """You are a deep research expert. Given content fetched from configured URL sites and the user's question, you must:

1. Summarize what relevant information the URLs provide for the question.
2. Recommend features, KPIs, or metrics (as natural language questions) that the content suggests or that would help answer the question.
3. Suggest an evidence gathering plan (what to pull from which source).
4. Note any data or information gaps.

Return valid JSON only, with no markdown or preamble:
{
  "summary": "One or two paragraph summary of relevant information from the URLs for the user's question.",
  "recommended_features": [
    {
      "feature_name": "string",
      "natural_language_question": "string",
      "feature_type": "kpi|metric|aggregation|calculation",
      "related_tables": [],
      "purpose": "string",
      "evidence_type": "string"
    }
  ],
  "evidence_gathering_plan": [
    {
      "evidence_type": "string",
      "source_tables": [],
      "description": "string",
      "priority": "high|medium|low"
    }
  ],
  "data_gaps": ["string"]
}
"""

DEEP_RESEARCH_HUMAN = """Context: {context_name}
Topic: {topic}

User question: {query}

Fetched content from URLs:

{merged_content}

Produce the JSON object as specified. If content is empty or errors, still return valid JSON with summary explaining no content was available."""


# Compliance goal: controls, evidence, compliance gaps
DEEP_RESEARCH_COMPLIANCE_SYSTEM = """You are a compliance deep research expert. Given content fetched from configured URL sites and the user's compliance-related question, you must:

1. Summarize what relevant compliance, control, or policy information the URLs provide for the question.
2. Recommend controls or requirements (from frameworks like SOC2, NIST, etc.) that the content suggests or that would help answer the question.
3. Suggest an evidence gathering plan (what evidence to collect, from which source, for which control).
4. Note any compliance or information gaps.

Return valid JSON only, with no markdown or preamble:
{
  "summary": "One or two paragraph summary of relevant compliance/control information from the URLs for the user's question.",
  "recommended_controls": [
    {
      "control_id_or_name": "string",
      "description": "string",
      "framework": "SOC2|NIST|HIPAA|PCI-DSS|other",
      "evidence_type": "string",
      "purpose": "string"
    }
  ],
  "evidence_gathering_plan": [
    {
      "evidence_type": "string",
      "source": "string",
      "description": "string",
      "priority": "high|medium|low",
      "related_control": "string"
    }
  ],
  "compliance_gaps": ["string"]
}
"""

DEEP_RESEARCH_COMPLIANCE_HUMAN = """Context: {context_name}
Topic: {topic}

User question: {query}

Fetched content from URLs:

{merged_content}

Produce the JSON object as specified. If content is empty or errors, still return valid JSON with summary explaining no content was available."""


class DeepResearchUtility:
    """
    Common utility: fetch URLs from config, run LLM, return merged result.
    Reusable across data assistance, compliance, etc. Contextual data search can be wired in later.
    """

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)

    async def run(
        self,
        config: DeepResearchConfig,
        query: str,
    ) -> Dict[str, Any]:
        """
        Run deep research: fetch URLs -> merge content -> LLM -> structured result.

        Returns a dict compatible with deep_research_review:
        - summary, recommended_features, evidence_gathering_plan, data_gaps
        - fetched_sources: list of {url, content_snippet, error}
        - merged_content: full merged text (for debugging or downstream)
        """
        if not config.urls:
            return self._empty_result(
                getattr(config, "goal", DEEP_RESEARCH_GOAL_DATA),
                [],
                "No URLs configured for deep research.",
            )

        # 1. Fetch all URLs in parallel
        fetched = await fetch_urls(config)
        merged_content = merge_fetched_content(fetched)
        fetched_sources = [
            {
                "url": f.get("url", ""),
                "content_snippet": (f.get("content") or "")[:2000],
                "error": f.get("error"),
            }
            for f in fetched
        ]

        if not merged_content.strip():
            return self._empty_result(config.goal, fetched_sources, "No content could be fetched from the configured URLs.")

        # 2. LLM: choose prompt by goal
        is_compliance = getattr(config, "goal", DEEP_RESEARCH_GOAL_DATA) == DEEP_RESEARCH_GOAL_COMPLIANCE
        if is_compliance:
            system_prompt = DEEP_RESEARCH_COMPLIANCE_SYSTEM
            human_prompt = DEEP_RESEARCH_COMPLIANCE_HUMAN
        else:
            system_prompt = DEEP_RESEARCH_SYSTEM
            human_prompt = DEEP_RESEARCH_HUMAN

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ])
        chain = prompt | self.llm
        try:
            msg = await chain.ainvoke({
                "context_name": config.context_name,
                "topic": config.topic or config.context_name,
                "query": query,
                "merged_content": merged_content[:120000],  # cap for LLM
            })
            raw = msg.content if hasattr(msg, "content") else str(msg)
            raw = raw.strip()
            if "```json" in raw:
                start = raw.find("```json") + 7
                end = raw.find("```", start)
                raw = raw[start:end].strip()
            elif "```" in raw:
                start = raw.find("```") + 3
                end = raw.find("```", start)
                raw = raw[start:end].strip()
            result = json.loads(raw)
        except Exception as e:
            logger.warning(f"Deep research LLM parse failed: {e}")
            result = {
                "summary": f"Deep research LLM failed: {e}. Fetched {len(fetched_sources)} URL(s).",
                "recommended_features": [],
                "evidence_gathering_plan": [],
                "data_gaps": [],
            }

        result["fetched_sources"] = fetched_sources
        result["merged_content"] = merged_content

        # Normalize compliance output for shared state: recommended_controls -> recommended_features shape
        if is_compliance:
            recommended_controls = result.get("recommended_controls", [])
            result["recommended_features"] = [
                {
                    "feature_name": c.get("control_id_or_name", ""),
                    "natural_language_question": c.get("description", ""),
                    "feature_type": "control",
                    "related_tables": [],
                    "purpose": c.get("purpose", ""),
                    "evidence_type": c.get("evidence_type", ""),
                    "framework": c.get("framework", ""),
                }
                for c in recommended_controls
            ]
            result["data_gaps"] = result.get("compliance_gaps", result.get("data_gaps", []))

        return result

    def _empty_result(self, goal: str, fetched_sources: List[Dict], summary: str) -> Dict[str, Any]:
        is_compliance = goal == DEEP_RESEARCH_GOAL_COMPLIANCE
        return {
            "summary": summary,
            "recommended_features": [],
            "recommended_controls": [] if is_compliance else None,
            "evidence_gathering_plan": [],
            "data_gaps": [],
            "compliance_gaps": [] if is_compliance else None,
            "fetched_sources": fetched_sources,
            "merged_content": "",
        }


def default_snyk_config() -> DeepResearchConfig:
    """Example config for Snyk docs (data-related)."""
    return DeepResearchConfig(
        context_name="Snyk data",
        topic="Data related to Snyk",
        goal=DEEP_RESEARCH_GOAL_DATA,
        urls=[
            "https://docs.snyk.io/",
        ],
        max_content_per_url=DEFAULT_MAX_CONTENT_PER_URL,
        timeout_per_url=DEFAULT_TIMEOUT_PER_URL,
    )


def default_compliance_config() -> DeepResearchConfig:
    """Default config for compliance deep research (controls, evidence, frameworks)."""
    return DeepResearchConfig(
        context_name="Compliance",
        topic="Compliance, controls, and evidence (SOC2, NIST, etc.)",
        goal=DEEP_RESEARCH_GOAL_COMPLIANCE,
        next_node_after="compliance_qa",
        urls=[
            "https://www.aicpa-cima.com/resources/landing/trust-services-criteria",
        ],
        max_content_per_url=DEFAULT_MAX_CONTENT_PER_URL,
        timeout_per_url=DEFAULT_TIMEOUT_PER_URL,
    )
