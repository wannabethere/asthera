"""Pydantic models for RLS/CLS data protection API (no bundled policy defaults — tenant-defined)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core policy definitions (unchanged)
# ---------------------------------------------------------------------------

class RoleDefinition(BaseModel):
    id: str = Field(..., description="Stable slug")
    display_name: str = ""
    description: str = ""


class SessionPropertyDefinition(BaseModel):
    name: str
    description: str = ""
    value_type: str = Field(default="string")
    required: bool = True
    example: Optional[str] = None


class RLSPolicyDefinition(BaseModel):
    id: str
    display_name: str = ""
    model_ref: str
    description: str = ""
    predicate_template: str = ""
    session_properties_used: List[str] = Field(default_factory=list)


class CLSPolicyDefinition(BaseModel):
    id: str
    display_name: str = ""
    model_ref: str = ""
    protected_columns: List[str] = Field(default_factory=list)
    session_property: str = ""
    operator: str = Field(default="in")
    allowed_values: List[str] = Field(default_factory=list)
    restriction_message: str = Field(default="Restricted by policy")


class DataProtectionConfig(BaseModel):
    version: int = 1
    summary: str = ""
    roles: List[RoleDefinition] = Field(default_factory=list)
    session_properties: List[SessionPropertyDefinition] = Field(default_factory=list)
    rls_policies: List[RLSPolicyDefinition] = Field(default_factory=list)
    cls_policies: List[CLSPolicyDefinition] = Field(default_factory=list)


class DataProtectionStatusResponse(BaseModel):
    service: str = "data-protection"
    storage: str = "postgresql"
    api_key_configured: bool = False


# ---------------------------------------------------------------------------
# Connection-level policy models
# ---------------------------------------------------------------------------

class ConnectionPolicyConfig(BaseModel):
    """Policy configuration scoped to a single connection (connector)."""

    connection_id: UUID
    organization_id: UUID
    status: Literal["draft", "active", "inactive"] = "draft"
    inheritance_mode: Literal["inherit_override", "independent"] = "inherit_override"
    config: DataProtectionConfig = Field(default_factory=DataProtectionConfig)
    rls_overrides: List[RLSPolicyDefinition] = Field(default_factory=list)
    cls_overrides: List[CLSPolicyDefinition] = Field(default_factory=list)
    excluded_policy_ids: List[str] = Field(
        default_factory=list,
        description="Org-level policy IDs explicitly disabled for this connection",
    )
    generated_by: Literal["agent", "manual"] = "manual"
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Policy generation request / response
# ---------------------------------------------------------------------------

class PolicyGenerationRequest(BaseModel):
    """Request body for triggering LLM-based policy generation."""

    organization_id: UUID
    business_context: str = Field(
        default="",
        description="Free-text business context (e.g. compliance requirements, data domains)",
    )
    existing_roles: List[RoleDefinition] = Field(default_factory=list)
    generate_rls: bool = True
    generate_cls: bool = True


class PolicyGenerationResponse(BaseModel):
    """Response from the policy generation agent."""

    connection_id: UUID
    status: Literal["draft"] = "draft"
    config: DataProtectionConfig
    tables_analyzed: int = 0
    columns_classified: int = 0
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Column classification
# ---------------------------------------------------------------------------

class ColumnClassification(BaseModel):
    table_name: str
    column_name: str
    data_type: str = ""
    sensitivity_level: Literal["pii", "financial", "health", "confidential", "public"] = "public"
    reason: str = ""


class ColumnClassificationResponse(BaseModel):
    connection_id: UUID
    classifications: List[ColumnClassification] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Effective policy preview (org + connection merged)
# ---------------------------------------------------------------------------

class EffectivePolicyPreview(BaseModel):
    connection_id: UUID
    organization_id: UUID
    role: Optional[str] = None
    effective_config: DataProtectionConfig = Field(default_factory=DataProtectionConfig)
    inherited_rls_count: int = 0
    overridden_rls_count: int = 0
    inherited_cls_count: int = 0
    overridden_cls_count: int = 0


# ---------------------------------------------------------------------------
# Predicate validation
# ---------------------------------------------------------------------------

class PredicateValidationRequest(BaseModel):
    predicate_template: str
    session_properties: List[str] = Field(default_factory=list)


class PredicateValidationResponse(BaseModel):
    valid: bool = False
    issues: List[str] = Field(default_factory=list)
    suggestion: str = ""
