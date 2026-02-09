"""
Organization Configuration
==========================

Static organization configuration that is NOT stored in ChromaDB.
Organization is included in metadata but lives in application configuration only.

Usage:
    from app.config.organization_config import get_organization, get_product_organization
    
    # Get default organization
    org = get_organization()
    
    # Get organization for a specific product
    org = get_product_organization("Snyk")
"""
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class OrganizationConfig:
    """Organization configuration"""
    organization_id: str
    organization_name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None


# ============================================================================
# DEFAULT ORGANIZATION
# ============================================================================

DEFAULT_ORGANIZATION = OrganizationConfig(
    organization_id="default_org",
    organization_name="Default Organization",
    description="Default organization for products",
    metadata={}
)


# ============================================================================
# PRODUCT TO ORGANIZATION MAPPING
# ============================================================================

PRODUCT_ORGANIZATION_MAPPING: Dict[str, OrganizationConfig] = {
    "Snyk": OrganizationConfig(
        organization_id="snyk_org",
        organization_name="Snyk Organization",
        description="Snyk security platform organization",
        metadata={"domain": "security", "industry": "cybersecurity"}
    ),
    "Cornerstone": OrganizationConfig(
        organization_id="cornerstone_org",
        organization_name="Cornerstone Analytics Organization",
        description="Cornerstone analytics platform organization",
        metadata={"domain": "analytics", "industry": "data_analytics"}
    ),
    # Add more product-organization mappings here
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_organization(organization_id: Optional[str] = None) -> OrganizationConfig:
    """
    Get organization by ID.
    
    Args:
        organization_id: Organization ID (defaults to default organization)
    
    Returns:
        OrganizationConfig
    """
    if not organization_id:
        return DEFAULT_ORGANIZATION
    
    # Search in product mappings
    for org in PRODUCT_ORGANIZATION_MAPPING.values():
        if org.organization_id == organization_id:
            return org
    
    return DEFAULT_ORGANIZATION


def get_organization_config(organization_id: Optional[str] = None) -> OrganizationConfig:
    return get_organization(organization_id)


def get_product_organization(product_name: str) -> OrganizationConfig:
    """
    Get organization for a product.
    
    Args:
        product_name: Product name (e.g., "Snyk")
    
    Returns:
        OrganizationConfig for the product, or default if not found
    """
    return PRODUCT_ORGANIZATION_MAPPING.get(product_name, DEFAULT_ORGANIZATION)


def add_product_organization(
    product_name: str,
    organization_id: str,
    organization_name: str,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> None:
    """
    Add a product-organization mapping.
    
    Args:
        product_name: Product name
        organization_id: Organization ID
        organization_name: Organization name
        description: Optional description
        metadata: Optional metadata
    """
    PRODUCT_ORGANIZATION_MAPPING[product_name] = OrganizationConfig(
        organization_id=organization_id,
        organization_name=organization_name,
        description=description,
        metadata=metadata or {}
    )


def get_organization_metadata(product_name: str) -> Dict[str, str]:
    """
    Get organization metadata for a product (to include in document metadata).
    
    Args:
        product_name: Product name
    
    Returns:
        Dictionary with organization metadata fields
    """
    org = get_product_organization(product_name)
    return {
        "organization_id": org.organization_id,
        "organization_name": org.organization_name,
    }


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "OrganizationConfig",
    "DEFAULT_ORGANIZATION",
    "PRODUCT_ORGANIZATION_MAPPING",
    "get_organization",
    "get_organization_config",
    "get_product_organization",
    "add_product_organization",
    "get_organization_metadata",
]
