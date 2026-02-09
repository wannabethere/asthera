"""
Domain Configuration System
Defines domain-specific configurations, schemas, and use cases for indexing.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class DomainSchema:
    """Schema definition for a domain."""
    table_name: str
    columns: List[Dict[str, Any]]
    description: str
    primary_key: Optional[str] = None
    foreign_keys: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)


@dataclass
class DomainUseCase:
    """Use case definition for a domain."""
    name: str
    description: str
    example_queries: List[str] = field(default_factory=list)
    example_data: Optional[Dict[str, Any]] = None
    business_value: Optional[str] = None


@dataclass
class DomainConfig:
    """Configuration for a domain."""
    domain_name: str
    description: str
    schemas: List[DomainSchema] = field(default_factory=list)
    use_cases: List[DomainUseCase] = field(default_factory=list)
    example_schema: Optional[DomainSchema] = None
    example_use_case: Optional[DomainUseCase] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "domain_name": self.domain_name,
            "description": self.description,
            "schemas": [
                {
                    "table_name": s.table_name,
                    "columns": s.columns,
                    "description": s.description,
                    "primary_key": s.primary_key,
                    "foreign_keys": s.foreign_keys,
                    "indexes": s.indexes
                }
                for s in self.schemas
            ],
            "use_cases": [
                {
                    "name": uc.name,
                    "description": uc.description,
                    "example_queries": uc.example_queries,
                    "example_data": uc.example_data,
                    "business_value": uc.business_value
                }
                for uc in self.use_cases
            ],
            "example_schema": {
                "table_name": self.example_schema.table_name,
                "columns": self.example_schema.columns,
                "description": self.example_schema.description,
                "primary_key": self.example_schema.primary_key,
                "foreign_keys": self.example_schema.foreign_keys,
                "indexes": self.example_schema.indexes
            } if self.example_schema else None,
            "example_use_case": {
                "name": self.example_use_case.name,
                "description": self.example_use_case.description,
                "example_queries": self.example_use_case.example_queries,
                "example_data": self.example_use_case.example_data,
                "business_value": self.example_use_case.business_value
            } if self.example_use_case else None,
            "metadata": self.metadata
        }


def get_assets_domain_config() -> DomainConfig:
    """Get Assets domain configuration with example schema and use case."""
    
    # Example schema for Assets domain
    example_schema = DomainSchema(
        table_name="assets",
        description="Stores information about organizational assets including hardware, software, and digital resources.",
        primary_key="asset_id",
        columns=[
            {
                "name": "asset_id",
                "type": "varchar",
                "notNull": True,
                "description": "Unique identifier for each asset",
                "properties": {
                    "format": "uuid",
                    "displayName": "Asset ID",
                    "business_significance": "Primary key for asset tracking and management"
                }
            },
            {
                "name": "asset_name",
                "type": "varchar",
                "notNull": True,
                "description": "Human-readable name of the asset",
                "properties": {
                    "displayName": "Asset Name",
                    "business_significance": "Used for identification and reporting"
                }
            },
            {
                "name": "asset_type",
                "type": "varchar",
                "notNull": True,
                "description": "Type of asset (hardware, software, digital, etc.)",
                "properties": {
                    "enum": "hardware,software,digital,physical",
                    "displayName": "Asset Type",
                    "business_significance": "Categorizes assets for management and compliance"
                }
            },
            {
                "name": "status",
                "type": "varchar",
                "notNull": True,
                "description": "Current status of the asset",
                "properties": {
                    "enum": "active,inactive,retired,maintenance",
                    "displayName": "Status",
                    "business_significance": "Tracks asset lifecycle and availability"
                }
            },
            {
                "name": "owner_id",
                "type": "varchar",
                "notNull": False,
                "description": "ID of the person or department that owns the asset",
                "properties": {
                    "displayName": "Owner ID",
                    "business_significance": "Enables accountability and access control"
                }
            },
            {
                "name": "location",
                "type": "varchar",
                "notNull": False,
                "description": "Physical or logical location of the asset",
                "properties": {
                    "displayName": "Location",
                    "business_significance": "Helps with asset tracking and security"
                }
            },
            {
                "name": "purchase_date",
                "type": "date",
                "notNull": False,
                "description": "Date when the asset was purchased or acquired",
                "properties": {
                    "displayName": "Purchase Date",
                    "business_significance": "Used for depreciation and lifecycle management"
                }
            },
            {
                "name": "value",
                "type": "decimal",
                "notNull": False,
                "description": "Monetary value of the asset",
                "properties": {
                    "displayName": "Asset Value",
                    "business_significance": "Important for financial reporting and insurance"
                }
            },
            {
                "name": "created_at",
                "type": "timestamp",
                "notNull": True,
                "description": "Timestamp when the asset record was created",
                "properties": {
                    "displayName": "Created At",
                    "business_significance": "Audit trail for asset management"
                }
            },
            {
                "name": "updated_at",
                "type": "timestamp",
                "notNull": True,
                "description": "Timestamp when the asset record was last updated",
                "properties": {
                    "displayName": "Updated At",
                    "business_significance": "Tracks asset record modifications"
                }
            }
        ],
        foreign_keys=[
            {
                "column": "owner_id",
                "references": "users.user_id",
                "description": "References the user or department that owns the asset"
            }
        ],
        indexes=["asset_id", "asset_type", "status", "owner_id"]
    )
    
    # Example use case for Assets domain
    example_use_case = DomainUseCase(
        name="Asset Inventory Management",
        description="Track and manage organizational assets including hardware, software, and digital resources. Provides visibility into asset lifecycle, ownership, location, and value for compliance and financial reporting.",
        example_queries=[
            "SELECT * FROM assets WHERE asset_type = 'hardware' AND status = 'active'",
            "SELECT asset_type, COUNT(*) as count, SUM(value) as total_value FROM assets GROUP BY asset_type",
            "SELECT owner_id, COUNT(*) as asset_count FROM assets WHERE status = 'active' GROUP BY owner_id",
            "SELECT * FROM assets WHERE purchase_date < '2020-01-01' AND status = 'active'",
            "SELECT location, COUNT(*) as count FROM assets WHERE status = 'active' GROUP BY location"
        ],
        example_data={
            "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "asset_name": "Laptop - Dell XPS 15",
            "asset_type": "hardware",
            "status": "active",
            "owner_id": "user_123",
            "location": "Office Building A, Floor 3",
            "purchase_date": "2023-06-15",
            "value": 1299.99,
            "created_at": "2023-06-15T10:30:00Z",
            "updated_at": "2024-01-20T14:22:00Z"
        },
        business_value="Enables organizations to maintain accurate asset inventories, track asset lifecycle, ensure compliance with asset management policies, support financial reporting, and optimize asset utilization."
    )
    
    # Additional schemas for Assets domain
    additional_schemas = [
        DomainSchema(
            table_name="asset_assignments",
            description="Tracks assignment of assets to users or departments over time",
            primary_key="assignment_id",
            columns=[
                {
                    "name": "assignment_id",
                    "type": "varchar",
                    "notNull": True,
                    "description": "Unique identifier for the assignment",
                    "properties": {"format": "uuid"}
                },
                {
                    "name": "asset_id",
                    "type": "varchar",
                    "notNull": True,
                    "description": "Reference to the asset",
                    "properties": {}
                },
                {
                    "name": "assigned_to",
                    "type": "varchar",
                    "notNull": True,
                    "description": "User or department ID",
                    "properties": {}
                },
                {
                    "name": "assigned_date",
                    "type": "date",
                    "notNull": True,
                    "description": "Date when asset was assigned",
                    "properties": {}
                },
                {
                    "name": "returned_date",
                    "type": "date",
                    "notNull": False,
                    "description": "Date when asset was returned",
                    "properties": {}
                }
            ],
            foreign_keys=[
                {
                    "column": "asset_id",
                    "references": "assets.asset_id",
                    "description": "References the asset being assigned"
                }
            ]
        ),
        DomainSchema(
            table_name="asset_maintenance",
            description="Tracks maintenance history and schedules for assets",
            primary_key="maintenance_id",
            columns=[
                {
                    "name": "maintenance_id",
                    "type": "varchar",
                    "notNull": True,
                    "description": "Unique identifier for maintenance record",
                    "properties": {"format": "uuid"}
                },
                {
                    "name": "asset_id",
                    "type": "varchar",
                    "notNull": True,
                    "description": "Reference to the asset",
                    "properties": {}
                },
                {
                    "name": "maintenance_type",
                    "type": "varchar",
                    "notNull": True,
                    "description": "Type of maintenance (preventive, corrective, upgrade)",
                    "properties": {"enum": "preventive,corrective,upgrade"}
                },
                {
                    "name": "maintenance_date",
                    "type": "date",
                    "notNull": True,
                    "description": "Date of maintenance",
                    "properties": {}
                },
                {
                    "name": "cost",
                    "type": "decimal",
                    "notNull": False,
                    "description": "Cost of maintenance",
                    "properties": {}
                },
                {
                    "name": "notes",
                    "type": "text",
                    "notNull": False,
                    "description": "Maintenance notes and details",
                    "properties": {}
                }
            ],
            foreign_keys=[
                {
                    "column": "asset_id",
                    "references": "assets.asset_id",
                    "description": "References the asset being maintained"
                }
            ]
        )
    ]
    
    # Additional use cases
    additional_use_cases = [
        DomainUseCase(
            name="Asset Lifecycle Tracking",
            description="Monitor assets through their entire lifecycle from acquisition to retirement",
            example_queries=[
                "SELECT asset_id, asset_name, purchase_date, status FROM assets ORDER BY purchase_date DESC",
                "SELECT status, COUNT(*) as count FROM assets GROUP BY status",
                "SELECT * FROM assets WHERE status = 'retired' AND purchase_date < '2018-01-01'"
            ],
            business_value="Helps organizations understand asset utilization, plan for replacements, and optimize asset investments."
        ),
        DomainUseCase(
            name="Compliance and Audit",
            description="Support compliance reporting and audits by tracking asset ownership, location, and status",
            example_queries=[
                "SELECT owner_id, COUNT(*) as asset_count FROM assets WHERE status = 'active' GROUP BY owner_id",
                "SELECT asset_type, location, COUNT(*) as count FROM assets WHERE status = 'active' GROUP BY asset_type, location",
                "SELECT * FROM assets WHERE owner_id IS NULL AND status = 'active'"
            ],
            business_value="Ensures organizations can demonstrate compliance with asset management policies and regulations."
        )
    ]
    
    return DomainConfig(
        domain_name="Assets",
        description="Asset management domain for tracking hardware, software, and digital resources throughout their lifecycle. Supports inventory management, compliance reporting, and financial tracking.",
        schemas=[example_schema] + additional_schemas,
        use_cases=[example_use_case] + additional_use_cases,
        example_schema=example_schema,
        example_use_case=example_use_case,
        metadata={
            "category": "IT Management",
            "related_domains": ["Users", "Departments", "Financial"],
            "common_integrations": ["HR Systems", "Financial Systems", "IT Service Management"],
            "compliance_frameworks": ["ISO 27001", "SOC 2", "ITIL"]
        }
    )


def get_domain_config(domain_name: str) -> Optional[DomainConfig]:
    """Get domain configuration by name."""
    domain_configs = {
        "Assets": get_assets_domain_config(),
        "assets": get_assets_domain_config()
    }
    
    return domain_configs.get(domain_name)


def list_available_domains() -> List[str]:
    """List all available domain configurations."""
    return ["Assets"]

