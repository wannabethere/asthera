"""
Workforce Assistants Configuration
Centralized configuration for Product, Compliance, and Domain Knowledge assistants.

Each assistant has:
- Model configuration
- Data sources with category breakdowns (mapped to actual vector store collections)
- Web search configuration

Note: System prompts are now in app/utils/prompts/workforce_prompts.py

Collection Mappings (from collection_factory.py and mdl_store_mapping_simplified.py):
====================================================================================

Existing Collections:
---------------------
1. domain_knowledge - Policies, risks, products (use metadata.type to distinguish)
2. entities - General entities (use entity_type + mdl_entity_type discriminators)
3. evidence - Evidence documents
4. fields - Fields/attributes
5. controls - Controls
6. compliance_controls - Compliance-specific controls
7. features - Feature knowledge base
8. instructions - Product instructions (already has retrieval code)
9. sql_pairs - SQL examples (already has retrieval code)
10. table_descriptions - Table schemas (already indexed)
11. column_metadata - Column metadata (already indexed)
12. contextual_edges - Relationship edges between entities

Metadata Discriminators:
------------------------
- domain_knowledge: type="product", "compliance", "risk", "policy"
- entities: entity_type="mdl", mdl_entity_type="product", "feature", "metric", "category"
- Standard filters: product_name, project_id, category_name
"""
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

from app.utils.prompts import (
    PRODUCT_SYSTEM_PROMPT,
    PRODUCT_HUMAN_PROMPT,
    COMPLIANCE_SYSTEM_PROMPT,
    COMPLIANCE_HUMAN_PROMPT,
    DOMAIN_KNOWLEDGE_SYSTEM_PROMPT,
    DOMAIN_KNOWLEDGE_HUMAN_PROMPT
)

if TYPE_CHECKING:
    from app.storage.query.collection_factory import CollectionFactory


class AssistantType(Enum):
    """Types of workforce assistants"""
    PRODUCT = "product"
    COMPLIANCE = "compliance"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


@dataclass
class DataSourceConfig:
    """
    Configuration for a data source used by an assistant.
    
    Attributes:
        source_name: Name of the data source (e.g., "chroma", "web", "postgres")
        enabled: Whether this data source is enabled
        categories: List of categories to filter by (if applicable)
        metadata_filters: Additional metadata filters for this source
        priority: Priority of this source (1-10, higher = more important)
    """
    source_name: str
    enabled: bool = True
    categories: List[str] = field(default_factory=list)
    metadata_filters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5


@dataclass
class AssistantConfig:
    """
    Configuration for a workforce assistant.
    
    Attributes:
        assistant_type: Type of assistant
        model_name: LLM model to use
        temperature: Model temperature
        system_prompt_template: System prompt template
        human_prompt_template: Human prompt template
        data_sources: List of data source configurations
        web_search_enabled: Whether web search is enabled
        max_edges: Maximum number of edges to retrieve
        enable_evidence_gathering: Whether to enable evidence gathering
    """
    assistant_type: AssistantType
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.2
    system_prompt_template: str = ""
    human_prompt_template: str = ""
    data_sources: List[DataSourceConfig] = field(default_factory=list)
    web_search_enabled: bool = True
    max_edges: int = 10
    enable_evidence_gathering: bool = False


# ============================================================================
# PRODUCT ASSISTANT CONFIGURATION
# ============================================================================
# Note: Prompts are imported from app/utils/prompts/workforce_prompts.py

PRODUCT_DATA_SOURCES = [
    DataSourceConfig(
        source_name="domain_knowledge",  # Actual collection: domain_knowledge with type="product"
        enabled=True,
        categories=["product_features", "api_docs", "user_guides"],
        metadata_filters={"type": "product"},
        priority=10
    ),
    DataSourceConfig(
        source_name="features",  # Actual collection: features (feature knowledge base)
        enabled=True,
        categories=["features"],
        metadata_filters={},
        priority=9
    ),
    DataSourceConfig(
        source_name="entities",  # Actual collection: entities with type discriminator
        enabled=True,
        categories=["product"],
        metadata_filters={"entity_type": "mdl", "mdl_entity_type": "product"},
        priority=8
    ),
    DataSourceConfig(
        source_name="instructions",  # Actual collection: instructions (product instructions)
        enabled=True,
        categories=["instructions"],
        metadata_filters={},
        priority=8
    ),
    DataSourceConfig(
        source_name="table_descriptions",  # Actual collection: table_descriptions (schema info)
        enabled=True,
        categories=["tables", "schema"],
        metadata_filters={},
        priority=7
    ),
    DataSourceConfig(
        source_name="sql_pairs",  # Actual collection: sql_pairs (SQL examples)
        enabled=True,
        categories=["examples"],
        metadata_filters={},
        priority=6
    ),
    DataSourceConfig(
        source_name="web_search",  # Web search tool
        enabled=True,
        categories=[],
        metadata_filters={},
        priority=6
    ),
]

PRODUCT_ASSISTANT_CONFIG = AssistantConfig(
    assistant_type=AssistantType.PRODUCT,
    model_name="gpt-4o-mini",
    temperature=0.2,
    system_prompt_template=PRODUCT_SYSTEM_PROMPT,
    human_prompt_template=PRODUCT_HUMAN_PROMPT,
    data_sources=PRODUCT_DATA_SOURCES,
    web_search_enabled=True,
    max_edges=10,
    enable_evidence_gathering=False
)


# ============================================================================
# COMPLIANCE ASSISTANT CONFIGURATION
# ============================================================================
# Note: Prompts are imported from app/utils/prompts/workforce_prompts.py

COMPLIANCE_DATA_SOURCES = [
    DataSourceConfig(
        source_name="compliance_controls",  # Actual collection: compliance_controls
        enabled=True,
        categories=["frameworks", "controls", "requirements"],
        metadata_filters={},
        priority=10
    ),
    DataSourceConfig(
        source_name="controls",  # Actual collection: controls (general controls)
        enabled=True,
        categories=["controls"],
        metadata_filters={},
        priority=9
    ),
    DataSourceConfig(
        source_name="domain_knowledge",  # Actual collection: domain_knowledge with type="compliance"
        enabled=True,
        categories=["compliance", "policy"],
        metadata_filters={"type": "compliance"},
        priority=9
    ),
    DataSourceConfig(
        source_name="evidence",  # Actual collection: evidence
        enabled=True,
        categories=["evidence"],
        metadata_filters={},
        priority=8
    ),
    DataSourceConfig(
        source_name="entities",  # Actual collection: entities (for compliance entities)
        enabled=True,
        categories=["compliance_entities"],
        metadata_filters={"type": "compliance"},
        priority=7
    ),
    DataSourceConfig(
        source_name="web_search",  # Web search tool
        enabled=True,
        categories=[],
        metadata_filters={},
        priority=8
    ),
]

COMPLIANCE_ASSISTANT_CONFIG = AssistantConfig(
    assistant_type=AssistantType.COMPLIANCE,
    model_name="gpt-4o-mini",
    temperature=0.2,
    system_prompt_template=COMPLIANCE_SYSTEM_PROMPT,
    human_prompt_template=COMPLIANCE_HUMAN_PROMPT,
    data_sources=COMPLIANCE_DATA_SOURCES,
    web_search_enabled=True,
    max_edges=10,
    enable_evidence_gathering=True
)


# ============================================================================
# DOMAIN KNOWLEDGE ASSISTANT CONFIGURATION
# ============================================================================
# Note: Prompts are imported from app/utils/prompts/workforce_prompts.py

DOMAIN_KNOWLEDGE_DATA_SOURCES = [
    DataSourceConfig(
        source_name="domain_knowledge",  # Actual collection: domain_knowledge (main knowledge store)
        enabled=True,
        categories=["concepts", "best_practices", "patterns", "risk"],
        metadata_filters={},  # No type filter - search all domain knowledge
        priority=10
    ),
    DataSourceConfig(
        source_name="web_search",  # Web search tool
        enabled=True,
        categories=[],
        metadata_filters={},
        priority=9
    ),
    DataSourceConfig(
        source_name="entities",  # Actual collection: entities (for domain entities)
        enabled=True,
        categories=["domain_entities"],
        metadata_filters={},
        priority=7
    ),
    DataSourceConfig(
        source_name="fields",  # Actual collection: fields (domain fields/attributes)
        enabled=True,
        categories=["fields"],
        metadata_filters={},
        priority=6
    ),
]

DOMAIN_KNOWLEDGE_ASSISTANT_CONFIG = AssistantConfig(
    assistant_type=AssistantType.DOMAIN_KNOWLEDGE,
    model_name="gpt-4o-mini",
    temperature=0.2,
    system_prompt_template=DOMAIN_KNOWLEDGE_SYSTEM_PROMPT,
    human_prompt_template=DOMAIN_KNOWLEDGE_HUMAN_PROMPT,
    data_sources=DOMAIN_KNOWLEDGE_DATA_SOURCES,
    web_search_enabled=True,
    max_edges=10,
    enable_evidence_gathering=False
)


# ============================================================================
# CONFIGURATION REGISTRY
# ============================================================================

ASSISTANT_CONFIGS: Dict[AssistantType, AssistantConfig] = {
    AssistantType.PRODUCT: PRODUCT_ASSISTANT_CONFIG,
    AssistantType.COMPLIANCE: COMPLIANCE_ASSISTANT_CONFIG,
    AssistantType.DOMAIN_KNOWLEDGE: DOMAIN_KNOWLEDGE_ASSISTANT_CONFIG,
}


def get_assistant_config(assistant_type: AssistantType) -> AssistantConfig:
    """
    Get configuration for a specific assistant type.
    
    Args:
        assistant_type: Type of assistant
        
    Returns:
        AssistantConfig for the specified type
    """
    return ASSISTANT_CONFIGS[assistant_type]


def list_assistant_types() -> List[AssistantType]:
    """
    List all available assistant types.
    
    Returns:
        List of AssistantType values
    """
    return list(ASSISTANT_CONFIGS.keys())


def get_collection_mapping() -> Dict[str, str]:
    """
    Get mapping of data source names to actual collection names.
    
    Returns:
        Dictionary mapping source names to collection names
    """
    return {
        # Product collections
        "domain_knowledge": "domain_knowledge",  # With type="product" filter
        "entities": "entities",  # With entity_type="mdl" filter
        "features": "features",
        "instructions": "instructions",
        "table_descriptions": "table_descriptions",  # Schema info
        "column_metadata": "column_metadata",  # Column info
        "sql_pairs": "sql_pairs",  # SQL examples
        
        # Compliance collections
        "compliance_controls": "compliance_controls",
        "controls": "controls",
        "evidence": "evidence",
        
        # Domain knowledge collections
        "fields": "fields",
        
        # Edges
        "contextual_edges": "contextual_edges",
        
        # Web search (not a collection)
        "web_search": None,
    }


def get_data_source_collection_name(source_name: str) -> Optional[str]:
    """
    Get actual collection name for a data source.
    
    Args:
        source_name: Data source name from config
        
    Returns:
        Actual collection name or None for non-collection sources (e.g., web_search)
    """
    mapping = get_collection_mapping()
    return mapping.get(source_name)


def get_collection_service_for_source(
    source_config: DataSourceConfig,
    collection_factory: "CollectionFactory"
) -> Optional[Any]:
    """
    Get collection service (HybridSearchService) for a data source.
    
    Args:
        source_config: Data source configuration
        collection_factory: CollectionFactory instance
        
    Returns:
        HybridSearchService instance or None if not found
    """
    source_name = source_config.source_name
    
    # Map to actual collection
    if source_name == "domain_knowledge":
        return collection_factory.domain_collections.get("domain_knowledge")
    elif source_name == "entities":
        return collection_factory.compliance_collections.get("entities")
    elif source_name == "features":
        return collection_factory.feature_collections.get("features")
    elif source_name == "instructions":
        return collection_factory.additional_collections.get("instructions")
    elif source_name == "sql_pairs":
        return collection_factory.additional_collections.get("sql_pairs")
    elif source_name == "compliance_controls":
        return collection_factory.compliance_collections.get("compliance_controls")
    elif source_name == "controls":
        return collection_factory.compliance_collections.get("controls")
    elif source_name == "evidence":
        return collection_factory.compliance_collections.get("evidence")
    elif source_name == "fields":
        return collection_factory.compliance_collections.get("fields")
    elif source_name == "table_descriptions":
        return collection_factory.schema_collections.get("table_descriptions")
    elif source_name == "column_metadata":
        return collection_factory.schema_collections.get("column_metadata")
    elif source_name == "contextual_edges":
        # Contextual edges are accessed via ContextualGraphService, not HybridSearchService
        return None
    elif source_name == "web_search":
        # Web search is not a collection
        return None
    
    return None
