"""
Ingestion module for compliance frameworks.

Provides adapters, orchestrator, embedder, and service for ingesting
compliance framework data into PostgreSQL and Qdrant.
"""

from app.ingestion.frameworks import (
    BaseFrameworkAdapter,
    FrameworkIngestionBundle,
    NormalizedFramework,
    NormalizedControl,
    NormalizedRequirement,
    NormalizedRisk,
    NormalizedTestCase,
    NormalizedScenario,
    CISv81Adapter,
    HIPAAAdapter,
    SOC2Adapter,
    NISTCSFAdapter,
    ISO27001Adapter,
    get_adapter,
    ADAPTER_REGISTRY,
)
from app.ingestion.service import (
    IngestionService,
    IngestionResult,
    IngestionSummary,
)
from app.ingestion.orchestrator import IngestionOrchestrator
from app.ingestion.embedder import EmbeddingService

__all__ = [
    # Adapters
    "BaseFrameworkAdapter",
    "FrameworkIngestionBundle",
    "NormalizedFramework",
    "NormalizedControl",
    "NormalizedRequirement",
    "NormalizedRisk",
    "NormalizedTestCase",
    "NormalizedScenario",
    "CISv81Adapter",
    "HIPAAAdapter",
    "SOC2Adapter",
    "NISTCSFAdapter",
    "ISO27001Adapter",
    "get_adapter",
    "ADAPTER_REGISTRY",
    # Service
    "IngestionService",
    "IngestionResult",
    "IngestionSummary",
    # Components
    "IngestionOrchestrator",
    "EmbeddingService",
]
