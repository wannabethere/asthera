"""
Ingestion Pipeline Package

This package provides a unified architecture for ingesting data from various sources
using the Abstract Factory pattern.

Available modules:
- factories: Abstract factory interfaces and concrete implementations
- pipeline: Main orchestration logic for running ingestion pipelines
"""

from .factories import get_factory
from .pipeline import IngestPipeline, run_pipeline

__all__ = ['get_factory', 'IngestPipeline', 'run_pipeline'] 