"""
Pytest configuration and fixtures for compliance skill tests.

Uses app.core.settings and app.core.dependencies to:
- Load correct .env files (from project root via Settings)
- Provide settings fixture
- Validate Qdrant store availability and data
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on path before any app imports
base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

# Load .env via Settings (uses pydantic_settings env_file)
# Settings loads from BASE_DIR/.env; clear cache to pick up test overrides
_env_loaded = False


def _ensure_env_loaded():
    """Load settings once at test collection time to set os.environ."""
    global _env_loaded
    if _env_loaded:
        return
    try:
        from app.core.settings import get_settings, clear_settings_cache
        clear_settings_cache()
        get_settings()
        _env_loaded = True
    except Exception as e:
        # Fallback: try dotenv if settings fails (e.g. missing pydantic-settings)
        env_file = base_dir / ".env"
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file, override=True)
            except ImportError:
                pass
        _env_loaded = True


# Load env when conftest is imported
_ensure_env_loaded()


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def settings():
    """Application settings from app.core.settings (loads .env)."""
    from app.core.settings import get_settings, clear_settings_cache
    clear_settings_cache()
    return get_settings()


@pytest.fixture(scope="session")
def qdrant_available(settings):
    """Check if Qdrant is reachable. Use for skipif in Qdrant-dependent tests."""
    if settings.VECTOR_STORE_TYPE.value != "qdrant":
        return False
    try:
        from qdrant_client import QdrantClient
        host = settings.QDRANT_HOST or "localhost"
        port = settings.QDRANT_PORT or 6333
        client = QdrantClient(host=host, port=port, timeout=2.0)
        _ = client.get_collections()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def qdrant_client(settings, qdrant_available):
    """Qdrant client when Qdrant is available. Raises skip if not."""
    if not qdrant_available:
        pytest.skip("Qdrant not available (VECTOR_STORE_TYPE or connection)")
    from qdrant_client import QdrantClient
    host = settings.QDRANT_HOST or "localhost"
    port = settings.QDRANT_PORT or 6333
    return QdrantClient(host=host, port=port)


# ═══════════════════════════════════════════════════════════════════════
# HOOKS
# ═══════════════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Ensure env is loaded before test collection."""
    _ensure_env_loaded()
