"""
Embedding service using OpenAI text-embedding-3-small.
Provides batched embedding with retry logic and rate-limit handling.
"""

import os
import time
import logging
from typing import List, Optional

from openai import OpenAI
from openai import RateLimitError, APIError

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_BATCH_SIZE = 512        # OpenAI limit per request (tokens basis — safe batch count)
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2.0         # seconds, doubles each retry


class EmbeddingService:
    """
    Stateless embedding service. One instance per application is sufficient.

    Usage:
        embedder = EmbeddingService()
        vectors = embedder.embed(["text one", "text two"])
    """

    def __init__(self, api_key: Optional[str] = None):
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, texts: List[str], batch_size: int = MAX_BATCH_SIZE) -> List[List[float]]:
        """
        Embed a list of texts. Returns vectors in the same order as input.
        Handles batching and retries transparently.

        Args:
            texts: List of strings to embed.
            batch_size: Number of texts per API call.

        Returns:
            List of 1536-dimensional float vectors.
        """
        if not texts:
            return []

        # Clean texts: empty strings cause API errors
        cleaned = [t.strip() or " " for t in texts]

        all_vectors: List[List[float]] = []
        for i in range(0, len(cleaned), batch_size):
            batch = cleaned[i : i + batch_size]
            vectors = self._embed_batch_with_retry(batch)
            all_vectors.extend(vectors)
            if i + batch_size < len(cleaned):
                # Brief pause between batches to respect rate limits
                time.sleep(0.1)

        return all_vectors

    def embed_one(self, text: str) -> List[float]:
        """Convenience wrapper for a single text."""
        return self.embed([text])[0]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        delay = RETRY_BACKOFF
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                response = self._client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=texts,
                )
                # API returns embeddings ordered by index
                ordered = sorted(response.data, key=lambda e: e.index)
                return [e.embedding for e in ordered]

            except RateLimitError:
                if attempt == RETRY_ATTEMPTS:
                    raise
                logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt}/{RETRY_ATTEMPTS})")
                time.sleep(delay)
                delay *= 2

            except APIError as exc:
                if attempt == RETRY_ATTEMPTS:
                    raise
                logger.warning(f"OpenAI API error: {exc}, retrying in {delay}s")
                time.sleep(delay)
                delay *= 2

        raise RuntimeError("Embedding failed after all retries")  # should not reach here


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def build_control_embedding_text(
    name: str,
    description: Optional[str],
    domain: Optional[str],
    framework_name: Optional[str] = None,
    control_type: Optional[str] = None,
    cis_control_id: Optional[str] = None,
) -> str:
    """
    Compose the text that gets embedded for a control record.
    Including domain and framework context improves retrieval relevance
    for cross-framework queries.
    """
    parts = []
    if framework_name:
        parts.append(f"Framework: {framework_name}")
    if domain:
        parts.append(f"Domain: {domain}")
    if control_type:
        parts.append(f"Type: {control_type}")
    if cis_control_id:
        parts.append(f"CIS Control: {cis_control_id}")
    parts.append(f"Control: {name}")
    if description:
        # Truncate very long descriptions to avoid token limits
        parts.append(description[:1500])
    return "\n".join(parts)


def build_risk_embedding_text(
    name: str,
    description: Optional[str],
    asset: Optional[str] = None,
    loss_outcomes: Optional[List[str]] = None,
    framework_name: Optional[str] = None,
) -> str:
    parts = []
    if framework_name:
        parts.append(f"Framework: {framework_name}")
    if asset:
        parts.append(f"Asset: {asset}")
    if loss_outcomes:
        parts.append(f"Loss outcomes: {', '.join(loss_outcomes)}")
    parts.append(f"Risk: {name}")
    if description:
        parts.append(description[:1500])
    return "\n".join(parts)


def build_requirement_embedding_text(
    requirement_code: str,
    description: Optional[str],
    domain: Optional[str] = None,
    compliance_type: Optional[str] = None,
    framework_name: Optional[str] = None,
) -> str:
    parts = []
    if framework_name:
        parts.append(f"Framework: {framework_name}")
    if domain:
        parts.append(f"Domain: {domain}")
    if compliance_type:
        parts.append(f"Compliance type: {compliance_type}")
    parts.append(f"Requirement: {requirement_code}")
    if description:
        parts.append(description[:1500])
    return "\n".join(parts)


def build_test_case_embedding_text(
    name: str,
    objective: Optional[str],
    test_type: Optional[str] = None,
    success_criteria: Optional[List[str]] = None,
    framework_name: Optional[str] = None,
) -> str:
    parts = []
    if framework_name:
        parts.append(f"Framework: {framework_name}")
    if test_type:
        parts.append(f"Test type: {test_type}")
    parts.append(f"Test: {name}")
    if objective:
        parts.append(f"Objective: {objective[:500]}")
    if success_criteria:
        parts.append(f"Success criteria: {'; '.join(success_criteria[:3])}")
    return "\n".join(parts)


def build_scenario_embedding_text(
    name: str,
    description: Optional[str],
    asset: Optional[str] = None,
    framework_name: Optional[str] = None,
) -> str:
    parts = []
    if framework_name:
        parts.append(f"Framework: {framework_name}")
    if asset:
        parts.append(f"Asset: {asset}")
    parts.append(f"Scenario: {name}")
    if description:
        parts.append(description[:1500])
    return "\n".join(parts)
