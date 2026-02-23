"""
Framework adapters.

Import adapters from here rather than directly from individual modules.
To register a new framework, add it to ADAPTER_REGISTRY.
"""

from app.ingestion.base import (
    BaseFrameworkAdapter,
    FrameworkIngestionBundle,
    NormalizedFramework,
    NormalizedControl,
    NormalizedRequirement,
    NormalizedRisk,
    NormalizedTestCase,
    NormalizedScenario,
)
from app.ingestion.frameworks.cis_v8_1 import CISv81Adapter
from app.ingestion.frameworks.hipaa import HIPAAAdapter
from app.ingestion.frameworks.soc2 import SOC2Adapter
from app.ingestion.frameworks.nist_csf_2_0 import NISTCSFAdapter
from app.ingestion.frameworks.iso27001_2022 import ISO27001Adapter

__all__ = [
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
]

# Maps framework_id → adapter class
# Instantiation requires a data_dir argument.
ADAPTER_REGISTRY = {
    "cis_v8_1":    CISv81Adapter,
    "hipaa":       HIPAAAdapter,
    "soc2":        SOC2Adapter,
    "nist_csf_2_0": NISTCSFAdapter,
    "iso27001":    ISO27001Adapter,
}


def get_adapter(framework_id: str, data_dir: str) -> BaseFrameworkAdapter:
    """
    Instantiate and return the adapter for the given framework_id.

    Args:
        framework_id: One of the keys in ADAPTER_REGISTRY.
        data_dir: Path to the directory containing the framework's YAML files.

    Raises:
        ValueError: If framework_id is not registered.
    """
    cls = ADAPTER_REGISTRY.get(framework_id)
    if cls is None:
        raise ValueError(
            f"Unknown framework_id '{framework_id}'. "
            f"Registered: {list(ADAPTER_REGISTRY.keys())}"
        )
    return cls(data_dir=data_dir)
