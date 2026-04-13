"""LLM-powered agent for generating RLS/CLS data-protection policies from database schemas."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from cachetools import TTLCache
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser

from app.agents.data_protection_prompts import (
    CLS_GENERATION_HUMAN_PROMPT,
    CLS_GENERATION_SYSTEM_PROMPT,
    COLUMN_CLASSIFICATION_HUMAN_PROMPT,
    COLUMN_CLASSIFICATION_SYSTEM_PROMPT,
    PREDICATE_VALIDATION_HUMAN_PROMPT,
    PREDICATE_VALIDATION_SYSTEM_PROMPT,
    RLS_GENERATION_HUMAN_PROMPT,
    RLS_GENERATION_SYSTEM_PROMPT,
)
from app.core.dependencies import get_llm
from app.schemas.data_protection_api import (
    CLSPolicyDefinition,
    ColumnClassification,
    DataProtectionConfig,
    PredicateValidationResponse,
    RLSPolicyDefinition,
    RoleDefinition,
    SessionPropertyDefinition,
)

logger = logging.getLogger(__name__)


def _schema_to_text(tables_data: List[Dict[str, Any]]) -> str:
    """Convert ERD-style table data into a text representation for the LLM."""
    lines: list[str] = []
    for table in tables_data:
        table_name = table.get("table_name", "unknown")
        pk = table.get("primary_key", [])
        lines.append(f"TABLE {table_name}")
        if pk:
            lines.append(f"  PRIMARY KEY: {', '.join(pk)}")
        for col in table.get("columns", []):
            field = col.get("fieldName", col.get("name", "?"))
            dtype = col.get("dataType", col.get("data_type", "?"))
            desc = col.get("description", "")
            suffix = f"  -- {desc}" if desc else ""
            lines.append(f"  {field}  {dtype}{suffix}")
        lines.append("")
    return "\n".join(lines)


def _columns_to_text(tables_data: List[Dict[str, Any]]) -> str:
    """Flatten all columns into a text list for the classification prompt."""
    lines: list[str] = []
    for table in tables_data:
        table_name = table.get("table_name", "unknown")
        for col in table.get("columns", []):
            field = col.get("fieldName", col.get("name", "?"))
            dtype = col.get("dataType", col.get("data_type", "?"))
            desc = col.get("description", "")
            lines.append(f"{table_name}.{field}  ({dtype})  {desc}")
    return "\n".join(lines)


def _roles_to_text(roles: List[RoleDefinition]) -> str:
    if not roles:
        return "No existing roles defined."
    return "\n".join(f"- {r.id}: {r.display_name} — {r.description}" for r in roles)


class DataProtectionAgent:
    """Generates RLS / CLS policy recommendations from database schemas using an LLM."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self.llm = get_llm(temperature=temperature, model=model)
        self.parser = JsonOutputParser()
        self._cache: Dict[str, Any] = TTLCache(maxsize=1_000_000, ttl=120)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_policies(
        self,
        connection_id: UUID,
        tables_data: List[Dict[str, Any]],
        business_context: str = "",
        existing_roles: Optional[List[RoleDefinition]] = None,
        generate_rls: bool = True,
        generate_cls: bool = True,
    ) -> DataProtectionConfig:
        """Full generation: RLS + CLS policies from a connection schema."""

        cache_key = f"gen:{connection_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        roles: List[RoleDefinition] = list(existing_roles or [])
        session_props: List[SessionPropertyDefinition] = []
        rls_policies: List[RLSPolicyDefinition] = []
        cls_policies: List[CLSPolicyDefinition] = []

        if generate_rls:
            rls_result = await self._generate_rls(tables_data, business_context, roles)
            rls_policies = rls_result.get("rls_policies", [])
            # Merge roles and session props from RLS
            roles = _merge_roles(roles, rls_result.get("roles", []))
            session_props = _merge_session_props(session_props, rls_result.get("session_properties", []))

        if generate_cls:
            cls_result = await self._generate_cls(tables_data, business_context, roles)
            cls_policies = cls_result.get("cls_policies", [])
            roles = _merge_roles(roles, cls_result.get("roles", []))
            session_props = _merge_session_props(session_props, cls_result.get("session_properties", []))

        config = DataProtectionConfig(
            version=1,
            summary=f"Auto-generated policies for connection {connection_id}",
            roles=roles,
            session_properties=session_props,
            rls_policies=[RLSPolicyDefinition(**p) if isinstance(p, dict) else p for p in rls_policies],
            cls_policies=[CLSPolicyDefinition(**p) if isinstance(p, dict) else p for p in cls_policies],
        )

        self._cache[cache_key] = config
        return config

    async def generate_rls_policies(
        self,
        tables_data: List[Dict[str, Any]],
        business_context: str = "",
        existing_roles: Optional[List[RoleDefinition]] = None,
    ) -> Dict[str, Any]:
        """Generate RLS policies only."""
        return await self._generate_rls(tables_data, business_context, existing_roles or [])

    async def generate_cls_policies(
        self,
        tables_data: List[Dict[str, Any]],
        business_context: str = "",
        existing_roles: Optional[List[RoleDefinition]] = None,
    ) -> Dict[str, Any]:
        """Generate CLS policies only."""
        return await self._generate_cls(tables_data, business_context, existing_roles or [])

    async def classify_columns(
        self, tables_data: List[Dict[str, Any]]
    ) -> List[ColumnClassification]:
        """Classify columns by sensitivity level."""
        columns_text = _columns_to_text(tables_data)
        messages = [
            SystemMessage(content=COLUMN_CLASSIFICATION_SYSTEM_PROMPT),
            HumanMessage(content=COLUMN_CLASSIFICATION_HUMAN_PROMPT.format(columns_text=columns_text)),
        ]
        try:
            raw = await (self.llm | self.parser).ainvoke(messages)
            return [
                ColumnClassification(**c)
                for c in raw.get("classifications", [])
            ]
        except Exception:
            logger.exception("Column classification failed")
            return []

    async def validate_predicate(
        self, predicate: str, session_properties: List[str]
    ) -> PredicateValidationResponse:
        """Validate an RLS predicate template."""
        messages = [
            SystemMessage(content=PREDICATE_VALIDATION_SYSTEM_PROMPT),
            HumanMessage(
                content=PREDICATE_VALIDATION_HUMAN_PROMPT.format(
                    predicate=predicate,
                    session_properties=json.dumps(session_properties),
                )
            ),
        ]
        try:
            raw = await (self.llm | self.parser).ainvoke(messages)
            return PredicateValidationResponse(**raw)
        except Exception:
            logger.exception("Predicate validation failed")
            return PredicateValidationResponse(valid=False, issues=["Agent invocation failed"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate_rls(
        self,
        tables_data: List[Dict[str, Any]],
        business_context: str,
        roles: List[RoleDefinition],
    ) -> Dict[str, Any]:
        schema_text = _schema_to_text(tables_data)
        messages = [
            SystemMessage(content=RLS_GENERATION_SYSTEM_PROMPT),
            HumanMessage(
                content=RLS_GENERATION_HUMAN_PROMPT.format(
                    schema_text=schema_text,
                    business_context=business_context or "No specific context provided.",
                    existing_roles=_roles_to_text(roles),
                )
            ),
        ]
        try:
            return await (self.llm | self.parser).ainvoke(messages)
        except Exception:
            logger.exception("RLS generation failed")
            return {"rls_policies": [], "session_properties": [], "roles": []}

    async def _generate_cls(
        self,
        tables_data: List[Dict[str, Any]],
        business_context: str,
        roles: List[RoleDefinition],
    ) -> Dict[str, Any]:
        schema_text = _schema_to_text(tables_data)
        messages = [
            SystemMessage(content=CLS_GENERATION_SYSTEM_PROMPT),
            HumanMessage(
                content=CLS_GENERATION_HUMAN_PROMPT.format(
                    schema_text=schema_text,
                    business_context=business_context or "No specific context provided.",
                    existing_roles=_roles_to_text(roles),
                )
            ),
        ]
        try:
            return await (self.llm | self.parser).ainvoke(messages)
        except Exception:
            logger.exception("CLS generation failed")
            return {"cls_policies": [], "session_properties": [], "roles": []}


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def _merge_roles(
    existing: List[RoleDefinition], new_raw: List[Any]
) -> List[RoleDefinition]:
    seen = {r.id for r in existing}
    merged = list(existing)
    for item in new_raw:
        role = RoleDefinition(**item) if isinstance(item, dict) else item
        if role.id not in seen:
            merged.append(role)
            seen.add(role.id)
    return merged


def _merge_session_props(
    existing: List[SessionPropertyDefinition], new_raw: List[Any]
) -> List[SessionPropertyDefinition]:
    seen = {p.name for p in existing}
    merged = list(existing)
    for item in new_raw:
        prop = SessionPropertyDefinition(**item) if isinstance(item, dict) else item
        if prop.name not in seen:
            merged.append(prop)
            seen.add(prop.name)
    return merged
