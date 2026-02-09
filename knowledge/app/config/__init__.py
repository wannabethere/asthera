"""
Configuration Module
Centralized configuration for the application.
Config files (YAML) live in knowledge/config/; .env stays in knowledge/.
Contains:
- mdl_store_mapping.py: MDL semantic layer store mappings
- mdl_store_mapping_simplified.py: Simplified MDL store mappings
- organization_config.py: Organization-specific configurations
- workforce_config.py: Workforce assistants configuration (Python)
- domain_config.py: Domain-specific indexing configurations
"""
import os
from pathlib import Path

# Path to assistants configuration YAML (knowledge/config/)
_KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent.parent
ASSISTANTS_CONFIG_PATH = str(_KNOWLEDGE_ROOT / "config" / "assistants_configuration.yaml")
from app.config.mdl_store_mapping import (
    MDLStoreType,
    MDLCollectionConfig,
    get_mdl_store_config
)
from app.config.mdl_store_mapping_simplified import (
    get_simplified_store_mapping,
    get_collection_metadata
)
from app.config.organization_config import (
    OrganizationConfig,
    get_organization_config
)
from app.config.workforce_config import (
    AssistantType,
    AssistantConfig,
    DataSourceConfig,
    get_assistant_config,
    list_assistant_types,
    PRODUCT_ASSISTANT_CONFIG,
    COMPLIANCE_ASSISTANT_CONFIG,
    DOMAIN_KNOWLEDGE_ASSISTANT_CONFIG
)
from app.config.domain_config import (
    DomainConfig,
    DomainSchema,
    DomainUseCase,
    get_domain_config,
    get_assets_domain_config
)

__all__ = [
    # Paths
    "ASSISTANTS_CONFIG_PATH",
    
    # MDL Store Mapping
    "MDLStoreType",
    "MDLCollectionConfig",
    "get_mdl_store_config",
    "get_simplified_store_mapping",
    "get_collection_metadata",
    
    # Organization Config
    "OrganizationConfig",
    "get_organization_config",
    
    # Workforce Config
    "AssistantType",
    "AssistantConfig",
    "DataSourceConfig",
    "get_assistant_config",
    "list_assistant_types",
    "PRODUCT_ASSISTANT_CONFIG",
    "COMPLIANCE_ASSISTANT_CONFIG",
    "DOMAIN_KNOWLEDGE_ASSISTANT_CONFIG",
    
    # Domain Config
    "DomainConfig",
    "DomainSchema",
    "DomainUseCase",
    "get_domain_config",
    "get_assets_domain_config",
]
