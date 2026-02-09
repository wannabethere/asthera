"""
Comprehensive Indexing Module
Provides indexing services for API docs, help docs, product descriptions, schemas, and columns
with support for ChromaDB and Qdrant, domain filtering, and pipeline integration.
"""
from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.indexing.pipeline_orchestrator import PipelineOrchestrator
from app.config.domain_config import (
    DomainConfig,
    DomainSchema,
    DomainUseCase,
    get_assets_domain_config,
    get_domain_config,
    list_available_domains
)
from app.indexing.processors import (
    TableDescriptionProcessor,
    DBSchemaProcessor,
    DomainProcessor
)
from app.indexing.project_reader_qdrant import ProjectReaderQdrant

__all__ = [
    "ComprehensiveIndexingService",
    "PipelineOrchestrator",
    "DomainConfig",
    "DomainSchema",
    "DomainUseCase",
    "get_assets_domain_config",
    "get_domain_config",
    "list_available_domains",
    "TableDescriptionProcessor",
    "DBSchemaProcessor",
    "DomainProcessor",
    "ProjectReaderQdrant",
]

